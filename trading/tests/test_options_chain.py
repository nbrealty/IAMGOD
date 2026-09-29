"""Book O phase O0: option chain fetch (OPT-12 inputs, OPT-35), chain logger and the OPT-41 completeness
count, Cboe display values, and raw bars in data.py. Synthetic data and fake clients only; no network."""
import gzip
import json
import math
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from trader.data import AlpacaData
from trader.options import chain, logger
from trader.options.chain import ChainQuotes, fetch_chain, missing_fields
from trader.options.models import OptionQuote, occ_symbol

NOW = datetime(2026, 9, 28, 20, 30, tzinfo=timezone.utc)  # Monday 16:30 New York
SESSION = "2026-09-28"
QUOTE_TS = datetime(2026, 9, 28, 19, 59, tzinfo=timezone.utc)  # 15:59 New York
SPOT = 600.0
EXPIRIES = ["2026-10-02", "2026-10-30", "2026-11-20", "2026-12-18"]  # 4, 32, 53 and 81 DTE
STRIKES = [float(k) for k in range(400, 730, 10)]
U3 = ["SPY", "QQQ", "IWM"]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Retries and pacing never really wait in tests; the waits are recorded instead."""
    waits = []
    monkeypatch.setattr(chain, "_sleep", waits.append)
    return waits


# --- fakes ------------------------------------------------------------------------------------------------


def snapshot(sym, *, bid=1.0, ask=1.1, ts=QUOTE_TS, iv=0.2, delta=-0.2, greeks=True):
    quote = SimpleNamespace(bid_price=bid, ask_price=ask, timestamp=ts)
    g = SimpleNamespace(delta=delta, gamma=0.01, theta=-0.05, vega=0.3, rho=0.0) if greeks else None
    return SimpleNamespace(symbol=sym, latest_quote=quote, implied_volatility=iv, greeks=g, latest_trade=None)


def universe(underlying="SPY"):
    """Every listed contract: {symbol: snapshot}."""
    out = {}
    for exp in EXPIRIES + ["2026-09-25"]:  # one already-expired date
        for k in STRIKES:
            for t in ("put", "call"):
                sym = occ_symbol(underlying, exp, t, k)
                out[sym] = snapshot(sym, delta=-0.2 if t == "put" else 0.2)
    return out


def day(x):
    return str(x)[:10] if x is not None else None


class FakeOptionClient:
    """Serves `snaps` like Alpaca's option chain, snapshot and bars endpoints, and records every request."""

    def __init__(self, snaps=None, volumes=None, fail=(), bar_ts=None):
        self.snaps = universe() if snaps is None else snaps
        self.volumes = {} if volumes is None else volumes  # {symbol: volume}; absent -> no bar today
        self.fail, self.bar_ts = set(fail), bar_ts or datetime(2026, 9, 28, 4, 0, tzinfo=timezone.utc)
        self.chain_requests, self.snapshot_requests, self.bar_requests = [], [], []

    def get_option_chain(self, req):
        self.chain_requests.append(req)
        if "chain" in self.fail or f"chain-{req.type.value}" in self.fail:
            raise RuntimeError("chain down")
        out = {}
        for sym, s in self.snaps.items():
            if not chain.is_occ(sym):  # a junk row still reaches the parser (test of the per-contract guard)
                out[sym] = s
                continue
            info = chain.parse_occ(sym)
            if info["underlying"] != req.underlying_symbol or info["type"] != req.type.value:
                continue
            if not (req.strike_price_gte <= info["strike"] <= req.strike_price_lte):
                continue
            if not (day(req.expiration_date_gte) <= info["expiry"] <= day(req.expiration_date_lte)):
                continue
            out[sym] = s
        return out

    def get_option_snapshot(self, req):
        self.snapshot_requests.append(req)
        if "snapshot" in self.fail:
            raise RuntimeError("snapshot down")
        return {s: self.snaps[s] for s in req.symbol_or_symbols if s in self.snaps}

    def get_option_bars(self, req):
        self.bar_requests.append(req)
        if "bars" in self.fail:
            raise RuntimeError("bars down")
        data = {s: [SimpleNamespace(timestamp=self.bar_ts, volume=self.volumes[s])]
                for s in req.symbol_or_symbols if s in self.volumes}
        return SimpleNamespace(data=data)


def contract(sym, oi="1200", oi_date=date(2026, 9, 25), tradable=True):
    return SimpleNamespace(symbol=sym, tradable=tradable, open_interest=oi, open_interest_date=oi_date)


class FakeTradingClient:
    """`get_option_contracts` in pages of `page` contracts; `get_option_contract` for single symbols."""

    def __init__(self, contracts=None, page=50, fail=False, single=None):
        self.contracts = contracts if contracts is not None else {s: contract(s) for s in universe()}
        self.page, self.fail, self.single = page, fail, dict(single or {})
        self.requests, self.single_requests = [], []

    def get_option_contracts(self, req):
        self.requests.append(req)
        if self.fail:
            raise RuntimeError("contracts down")
        syms = sorted(s for s in self.contracts
                      if chain.parse_occ(s)["underlying"] in req.underlying_symbols
                      and day(req.expiration_date_gte) <= chain.parse_occ(s)["expiry"] <= day(req.expiration_date_lte)
                      and float(req.strike_price_gte) <= chain.parse_occ(s)["strike"] <= float(req.strike_price_lte))
        start = int(req.page_token or 0)
        chunk = syms[start:start + self.page]
        token = str(start + self.page) if start + self.page < len(syms) else None
        return SimpleNamespace(option_contracts=[self.contracts[s] for s in chunk], next_page_token=token)

    def get_option_contract(self, sym):
        self.single_requests.append(sym)
        if sym in self.single:
            return self.single[sym]
        raise RuntimeError("not found")


class FakeStockClient:
    def __init__(self, price=SPOT, fail=False):
        self.price, self.fail, self.requests = price, fail, []

    def get_stock_latest_trade(self, req):
        self.requests.append(req)
        if self.fail:
            raise RuntimeError("stock down")
        return {s: SimpleNamespace(price=self.price) for s in req.symbol_or_symbols}


def fetch(**kw):
    kw.setdefault("client", FakeOptionClient())
    kw.setdefault("contracts_client", FakeTradingClient())
    kw.setdefault("spot", SPOT)
    kw.setdefault("now", NOW)
    return fetch_chain(kw.pop("underlying", "SPY"), **kw)


# --- fetch_chain: window (OPT-35) -----------------------------------------------------------------------


def test_window_puts_calls_and_dte():
    quotes = fetch()
    assert isinstance(quotes, list) and isinstance(quotes, ChainQuotes)
    assert quotes and all(isinstance(q, OptionQuote) for q in quotes)
    puts = [q for q in quotes if q.type == "put"]
    calls = [q for q in quotes if q.type == "call"]
    assert min(q.strike for q in puts) == 420 and max(q.strike for q in puts) == 630  # 70%..105% of 600
    assert min(q.strike for q in calls) == 420 and max(q.strike for q in calls) == 690  # up to 115%
    assert {q.expiry for q in quotes} == {"2026-10-02", "2026-10-30", "2026-11-20"}  # 81 DTE and expired out
    assert all(q.feed == "indicative" for q in quotes)
    assert quotes == sorted(quotes, key=lambda q: (q.expiry, q.type, q.strike, q.symbol))
    assert quotes.meta["fatal"] == [] and quotes.meta["spot"] == SPOT and quotes.meta["n"] == len(quotes)


def test_requests_use_indicative_feed_and_bounds():
    client = FakeOptionClient()
    fetch(client=client)
    assert len(client.chain_requests) == 2
    for req in client.chain_requests:
        assert req.feed.value == "indicative" and req.underlying_symbol == "SPY"
        assert day(req.expiration_date_gte) == SESSION and day(req.expiration_date_lte) == "2026-12-07"
    by_type = {r.type.value: r for r in client.chain_requests}
    assert by_type["put"].strike_price_gte == 420 and by_type["put"].strike_price_lte == 630
    assert by_type["call"].strike_price_gte == 420 and by_type["call"].strike_price_lte == 690


def test_custom_dte_and_ranges():
    quotes = fetch(dte_max=10, put_range=(0.9, 1.0), call_max=1.05)
    assert {q.expiry for q in quotes} == {"2026-10-02"}
    assert {q.strike for q in quotes if q.type == "put"} == {540, 550, 560, 570, 580, 590, 600}
    assert max(q.strike for q in quotes if q.type == "call") == 630


def test_dte_zero_is_included():
    snaps = universe()
    sym = occ_symbol("SPY", SESSION, "put", 600)
    snaps[sym] = snapshot(sym)
    quotes = fetch(client=FakeOptionClient(snaps), contracts_client=FakeTradingClient({s: contract(s) for s in snaps}))
    assert sym in {q.symbol for q in quotes}


def test_extra_symbols_always_included_whatever_range():
    far = occ_symbol("SPY", "2026-12-18", "put", 400)  # 81 DTE and 67% of spot: outside the window
    snaps = universe()
    client = FakeOptionClient(snaps)
    tc = FakeTradingClient(single={far: contract(far, oi="900")})
    quotes = fetch(client=client, contracts_client=tc, extra_symbols=[far, "spy261218p00400000"])
    q = {x.symbol: x for x in quotes}[far]
    assert q.open_interest == 900 and q.tradable is True
    assert client.snapshot_requests and client.snapshot_requests[0].symbol_or_symbols == [far]
    assert tc.single_requests == [far]


def test_extra_symbols_of_other_underlyings_and_garbage():
    qqq = occ_symbol("QQQ", "2026-10-30", "put", 500)
    quotes = fetch(extra_symbols=[qqq, "AAPL", None])
    assert qqq not in {q.symbol for q in quotes}
    assert any("'AAPL'" in p for p in quotes.problems) and any("None" in p for p in quotes.problems)


def test_extra_symbol_without_snapshot_is_reported():
    gone = occ_symbol("SPY", "2026-08-21", "put", 500)
    quotes = fetch(extra_symbols=[gone])
    assert gone not in {q.symbol for q in quotes}
    assert any(gone in p and "no snapshot" in p for p in quotes.problems)


def test_extra_symbols_inside_the_window_need_no_extra_request():
    inside = occ_symbol("SPY", "2026-10-30", "put", 560)
    client = FakeOptionClient()
    quotes = fetch(client=client, extra_symbols=[inside])
    assert inside in {q.symbol for q in quotes} and client.snapshot_requests == []


# --- fetch_chain: OPT-12 inputs -----------------------------------------------------------------------------


def test_opt12_fields_filled_from_three_sources():
    sym = occ_symbol("SPY", "2026-10-30", "put", 560)
    quotes = fetch(client=FakeOptionClient(volumes={sym: 321.0}))
    q = {x.symbol: x for x in quotes}[sym]
    assert (q.bid, q.ask, q.iv, q.delta, q.gamma, q.theta, q.vega) == (1.0, 1.1, 0.2, -0.2, 0.01, -0.05, 0.3)
    assert q.quote_time == QUOTE_TS.isoformat()
    assert q.open_interest == 1200 and q.open_interest_date == "2026-09-25" and q.tradable is True
    assert q.volume == 321
    assert missing_fields(q) == []
    assert q.underlying == "SPY" and q.expiry == "2026-10-30" and q.type == "put" and q.strike == 560


def test_no_bar_today_means_zero_volume_but_old_bar_is_ignored():
    a = occ_symbol("SPY", "2026-10-30", "put", 560)
    b = occ_symbol("SPY", "2026-10-30", "put", 570)
    client = FakeOptionClient(volumes={a: 10.0, b: 99.0}, bar_ts=datetime(2026, 9, 25, 4, tzinfo=timezone.utc))
    quotes = {q.symbol: q for q in fetch(client=client)}
    assert quotes[a].volume == 0 and quotes[b].volume == 0  # bar is from Friday, not today
    assert quotes[occ_symbol("SPY", "2026-10-30", "put", 580)].volume == 0


def test_bars_batched_and_failure_leaves_volume_unknown(no_sleep):
    client = FakeOptionClient(fail={"bars"})
    quotes = fetch(client=client)
    assert all(q.volume is None for q in quotes)
    assert any("option bars request failed" in f for f in quotes.meta["fatal"])
    assert all(len(r.symbol_or_symbols) <= chain.BAR_BATCH for r in client.bar_requests)
    batches = math.ceil(len(quotes) / chain.BAR_BATCH)
    assert len(client.bar_requests) == batches * (1 + len(chain.BAR_RETRY_WAITS))  # each batch retried
    assert no_sleep == list(chain.BAR_RETRY_WAITS) * batches
    assert "volume" in missing_fields(quotes[0])


class FlakyBars(FakeOptionClient):
    """Answers 429 to the first `fails` bars requests, like Alpaca's free-plan rate limit."""

    def __init__(self, fails, **kw):
        super().__init__(**kw)
        self.fails = fails

    def get_option_bars(self, req):
        if self.fails > 0:
            self.fails -= 1
            self.bar_requests.append(req)
            raise RuntimeError("429 Too Many Requests")
        return super().get_option_bars(req)


def test_rate_limited_bars_batch_is_retried_not_fatal(no_sleep):
    sym = occ_symbol("SPY", "2026-10-30", "put", 560)
    client = FlakyBars(2, volumes={sym: 7.0})
    quotes = {q.symbol: q for q in fetch(client=client)}
    assert quotes[sym].volume == 7 and all(q.volume is not None for q in quotes.values())
    assert no_sleep[:2] == list(chain.BAR_RETRY_WAITS[:2])
    assert fetch(client=FlakyBars(3)).meta["fatal"] == []  # three retries are enough
    still = fetch(client=FlakyBars(4))  # the first batch fails every attempt
    assert sum("option bars request failed" in f for f in still.meta["fatal"]) == 1
    assert sum(q.volume is None for q in still) == chain.BAR_BATCH


class _HTTPError(Exception):
    """Shaped like alpaca-py's APIError: `status_code` from the HTTP answer."""

    def __init__(self, msg, status_code):
        super().__init__(msg)
        self.status_code = status_code


class DeniedBars(FakeOptionClient):
    def __init__(self, error, **kw):
        super().__init__(**kw)
        self.error = error

    def get_option_bars(self, req):
        self.bar_requests.append(req)
        raise self.error


def _big_snaps(n=450):
    out = {}
    for k in range(n):
        sym = occ_symbol("SPY", "2026-10-30", "put", 300.0 + k)
        out[sym] = snapshot(sym)
    return out


@pytest.mark.parametrize("error", [_HTTPError('{"message":"OPRA agreement is not signed"}', 403),
                                   _HTTPError("unauthorized", 401),
                                   RuntimeError('{"message":"OPRA agreement is not signed"}')])
def test_opra_not_signed_is_not_retried_and_stops_all_batches(no_sleep, error):
    """Finding #26: a 403 'OPRA agreement is not signed' used to sleep 10+30+60 s per batch (15 minutes on SPY)."""
    snaps = _big_snaps()
    client = DeniedBars(error, snaps=snaps)
    quotes = fetch(client=client, contracts_client=FakeTradingClient({s: contract(s) for s in snaps}, page=10000))
    assert len(quotes) > chain.BAR_BATCH * 2  # three batches: only the first is sent
    assert len(client.bar_requests) == 1 and no_sleep == []  # one request, no retry waits, no pacing
    fatal = [f for f in quotes.meta["fatal"] if "option bars" in f]
    assert len(fatal) == 1 and "not authorized" in fatal[0] and "15 minutes" in fatal[0]
    assert all(q.volume is None for q in quotes)


def test_permanent_client_error_is_not_retried_but_5xx_is(no_sleep):
    sym = occ_symbol("SPY", "2026-10-30", "put", 560)
    bad = DeniedBars(_HTTPError("bad request", 422), volumes={sym: 1.0})
    quotes = fetch(client=bad)
    batches = math.ceil(len(quotes) / chain.BAR_BATCH)
    assert len(bad.bar_requests) == batches and no_sleep == []  # every batch tried once, none retried
    assert all("after 0 retries" in f for f in quotes.meta["fatal"] if "option bars" in f)
    no_sleep.clear()
    down = DeniedBars(_HTTPError("bad gateway", 502))
    fetch(client=down)
    assert no_sleep == list(chain.BAR_RETRY_WAITS) * batches


def test_realistic_chain_size_request_count_and_pacing(no_sleep):
    """About 15k contracts (SPY with daily expiries): bars go in batches of 100, paced under 200/minute."""
    snaps = {}
    for d in range(0, 71):
        exp = (date(2026, 9, 28) + timedelta(days=d)).isoformat()
        for k in range(420, 690):
            for t in ("put", "call"):
                if t == "put" and k > 630:
                    continue
                sym = occ_symbol("SPY", exp, t, float(k))
                snaps[sym] = snapshot(sym)
    snaps = dict(list(snaps.items())[:15000])
    client = FakeOptionClient(snaps)
    quotes = fetch(client=client, contracts_client=FakeTradingClient({s: contract(s) for s in snaps}, page=10000))
    assert len(quotes) == 15000 and quotes.meta["fatal"] == []
    assert len(client.bar_requests) == 150 and all(len(r.symbol_or_symbols) <= 100 for r in client.bar_requests)
    assert no_sleep == [chain.BAR_PACE] * 149 and 60 / chain.BAR_PACE < 200


def test_one_bad_bar_timestamp_does_not_void_the_batch():
    a = occ_symbol("SPY", "2026-10-30", "put", 560)
    b = occ_symbol("SPY", "2026-10-30", "put", 570)
    client = FakeOptionClient(volumes={b: 12.0})
    orig = client.get_option_bars

    def bars(req):
        out = orig(req)
        if a in req.symbol_or_symbols:
            out.data[a] = [SimpleNamespace(timestamp="garbage", volume=5)]
        return out

    client.get_option_bars = bars
    quotes = fetch(client=client)
    by = {q.symbol: q for q in quotes}
    assert by[a].volume is None and by[b].volume == 12 and quotes.meta["fatal"] == []
    assert any(a in p and "bad option bar" in p for p in quotes.problems)
    assert sum(1 for q in quotes if q.volume is None) == 1


def test_contracts_pagination_collects_every_page():
    tc = FakeTradingClient(page=7)
    quotes = fetch(contracts_client=tc)
    assert len(tc.requests) > 1 and tc.requests[0].page_token is None
    assert all(q.open_interest == 1200 for q in quotes)


def test_contracts_truncated_at_max_pages_is_fatal(monkeypatch):
    monkeypatch.setattr(chain, "MAX_PAGES", 2)
    quotes = fetch(contracts_client=FakeTradingClient(page=7))
    assert any("truncated after 2 pages" in f for f in quotes.meta["fatal"])
    assert sum(1 for q in quotes if q.open_interest == 1200) == 14  # the pages read are kept


def test_contracts_failure_is_fatal_and_legs_not_tradable():
    quotes = fetch(contracts_client=FakeTradingClient(fail=True))
    assert quotes and all(q.open_interest is None and q.tradable is False for q in quotes)
    assert any("contracts request failed" in f for f in quotes.meta["fatal"])


def test_contract_missing_from_list_is_not_tradable():
    snaps = universe()
    sym = occ_symbol("SPY", "2026-10-30", "put", 560)
    contracts = {s: contract(s) for s in snaps if s != sym}
    quotes = {q.symbol: q for q in fetch(contracts_client=FakeTradingClient(contracts))}
    assert quotes[sym].tradable is False and quotes[sym].open_interest is None
    assert quotes[sym] and any(sym in p for p in fetch(contracts_client=FakeTradingClient(contracts)).problems)


def test_open_interest_bad_values():
    snaps = universe()
    a, b, c = (occ_symbol("SPY", "2026-10-30", "put", k) for k in (560, 570, 580))
    contracts = {s: contract(s) for s in snaps}
    contracts[a] = contract(a, oi=None, oi_date=None)
    contracts[b] = contract(b, oi="abc", oi_date="2026-09-25")
    contracts[c] = contract(c, oi="0", tradable=False)
    quotes = {q.symbol: q for q in fetch(contracts_client=FakeTradingClient(contracts))}
    assert quotes[a].open_interest is None and quotes[a].open_interest_date is None
    assert quotes[b].open_interest is None and quotes[b].open_interest_date == "2026-09-25"
    assert quotes[c].open_interest == 0 and quotes[c].tradable is False


def test_nan_and_missing_quote_fields_become_none():
    snaps = universe()
    a, b, c, d = (occ_symbol("SPY", "2026-10-30", "put", k) for k in (560, 570, 580, 590))
    snaps[a] = snapshot(a, bid=float("nan"), ask=float("inf"), iv=float("nan"), delta=float("nan"))
    snaps[b] = SimpleNamespace(symbol=b, latest_quote=None, implied_volatility=None, greeks=None)
    snaps[c] = snapshot(c, bid=0.0, ask=0.05, iv=0.0, greeks=False)
    snaps[d] = snapshot(d, bid=-1.0, ts=None)
    quotes = {q.symbol: q for q in fetch(client=FakeOptionClient(snaps))}
    assert quotes[a].bid is None and quotes[a].ask is None and quotes[a].iv is None and quotes[a].delta is None
    assert quotes[b].bid is None and quotes[b].quote_time is None and quotes[b].delta is None
    assert quotes[c].bid == 0.0 and quotes[c].iv is None and quotes[c].delta is None  # zero bid is real (OPT-12)
    assert quotes[d].bid is None and quotes[d].quote_time is None
    assert set(missing_fields(quotes[b])) >= {"bid", "ask", "quote_time", "iv", "delta", "gamma", "theta", "vega"}


@pytest.mark.parametrize("field", ["bid", "ask", "quote_time", "iv", "delta", "gamma", "theta", "vega",
                                   "open_interest", "open_interest_date", "volume"])
def test_missing_fields_reports_every_opt12_and_opt27_input(field):
    """OPT-27: a missing greek (vega for OPT-10's cap included), IV or quote must block an entry."""
    q = {x.symbol: x for x in fetch(client=FakeOptionClient(volumes={}))}[occ_symbol("SPY", "2026-10-30", "put", 560)]
    assert missing_fields(q) == []
    setattr(q, field, None)
    assert missing_fields(q) == [field]


def test_one_bad_contract_never_raises():
    snaps = universe()
    bad = occ_symbol("SPY", "2026-10-30", "put", 560)

    class Exploding:
        @property
        def latest_quote(self):
            raise ValueError("broken")

    snaps[bad] = Exploding()
    snaps["NOTANOCC"] = snapshot("NOTANOCC")
    quotes = fetch(client=FakeOptionClient(snaps))
    syms = {q.symbol for q in quotes}
    assert bad not in syms and "NOTANOCC" not in syms and len(quotes) > 50
    assert any(bad in p and "bad snapshot" in p for p in quotes.problems)
    assert any("NOTANOCC" in p for p in quotes.problems)


def test_dict_shaped_raw_data_is_read():
    sym = occ_symbol("SPY", "2026-10-30", "put", 560)
    snaps = universe()
    snaps[sym] = {"latest_quote": {"bid_price": 2.0, "ask_price": 2.2, "timestamp": "2026-09-28T19:59:00Z"},
                  "implied_volatility": 0.25, "greeks": {"delta": -0.21}}
    q = {x.symbol: x for x in fetch(client=FakeOptionClient(snaps))}[sym]
    assert (q.bid, q.ask, q.iv, q.delta) == (2.0, 2.2, 0.25, -0.21) and q.quote_time.startswith("2026-09-28T19:59")


def test_empty_chain():
    quotes = fetch(client=FakeOptionClient({}), contracts_client=FakeTradingClient({}))
    assert quotes == [] and quotes.meta["fatal"] == [] and quotes.meta["n"] == 0


def test_chain_failure_is_recorded_not_raised():
    quotes = fetch(client=FakeOptionClient(fail={"chain-call"}))
    assert quotes and all(q.type == "put" for q in quotes)
    assert any("call chain request failed" in f for f in quotes.meta["fatal"])


# --- fetch_chain: spot ---------------------------------------------------------------------------------------


def test_spot_from_latest_iex_trade():
    stock = FakeStockClient(price=600.0)
    quotes = fetch(spot=None, stock_client=stock)
    assert quotes.meta["spot"] == 600.0 and "IEX" in quotes.meta["spot_source"]
    assert stock.requests[0].feed.value == "iex" and len(quotes) > 50


@pytest.mark.parametrize("stock", [FakeStockClient(fail=True), FakeStockClient(price=float("nan")),
                                   FakeStockClient(price=0.0)])
def test_spot_unknown_is_fatal_and_fetches_no_chain(stock):
    client = FakeOptionClient()
    quotes = fetch(spot=None, stock_client=stock, client=client)
    assert quotes == [] and quotes.meta["fatal"] and client.chain_requests == []


@pytest.mark.parametrize("bad", [0, -5, float("nan"), "x"])
def test_bad_given_spot_is_fatal(bad):
    quotes = fetch(spot=bad)
    assert quotes == [] and quotes.meta["fatal"]


def test_spot_unknown_still_logs_held_legs():
    held = occ_symbol("SPY", "2026-10-30", "put", 560)
    quotes = fetch(spot=None, stock_client=FakeStockClient(fail=True), extra_symbols=[held])
    assert [q.symbol for q in quotes] == [held] and quotes.meta["fatal"]


def test_missing_keys_do_not_raise(monkeypatch):
    for k in ("ALPACA_DATA_KEY", "ALPACA_DATA_SECRET", "ALPACA_RULES_KEY", "ALPACA_RULES_SECRET"):
        monkeypatch.delenv(k, raising=False)
    quotes = fetch_chain("SPY", spot=SPOT, now=NOW)
    assert quotes == [] and "no Alpaca clients" in quotes.meta["fatal"][0]


def test_meta_records_public_sources():
    meta = fetch().meta
    assert meta["feed"] == "indicative" and meta["session_date"] == SESSION
    assert set(meta["source"]) == {"quotes_iv_greeks", "open_interest", "volume", "spot"}
    assert all("alpaca" in v for v in meta["source"].values())


# --- logger: snapshots and index (OPT-35, OPT-41) --------------------------------------------------------------


def full_fetch(**over):
    """A fake `fetch` for the logger that builds a clean chain per underlying and records calls."""
    calls = []

    def f(underlying, **kw):
        calls.append((underlying, kw))
        client = FakeOptionClient(universe(underlying), **over.get("client", {}))
        tc = FakeTradingClient({s: contract(s) for s in universe(underlying)})
        return fetch_chain(underlying, client=client, contracts_client=tc,
                           spot=kw.get("spot") or SPOT, now=kw["now"], extra_symbols=kw["extra_symbols"])

    f.calls = calls
    return f


def test_log_chains_writes_gzip_snapshot_and_index(tmp_path):
    f = full_fetch()
    rec = logger.log_chains(["SPY", "QQQ", "IWM"], tmp_path, when="close", now=NOW, fetch=f, cboe_fetch=None)
    path = tmp_path / "options" / "chains" / SESSION / "close.json.gz"
    assert rec["path"] == str(path) and path.exists()
    assert rec["complete"] is True and rec["problems"] == [] and rec["date"] == SESSION and rec["when"] == "close"
    assert [c[0] for c in f.calls] == ["SPY", "QQQ", "IWM"]
    with gzip.open(path, "rt") as fh:
        raw = json.load(fh)
    assert raw["feed"] == "indicative" and set(raw["underlyings"]) == {"SPY", "QQQ", "IWM"}
    assert raw["n"] == rec["n"] == sum(b["n"] for b in raw["underlyings"].values())
    assert raw["source"]["open_interest"].startswith("alpaca")
    index = logger.load_index(tmp_path)
    assert len(index) == 1 and index[0]["n"] == rec["n"] and index[0]["complete"] is True
    assert index[0]["file"] == f"options/chains/{SESSION}/close.json.gz"


def test_load_snapshot_round_trip(tmp_path):
    logger.log_chains(["SPY"], tmp_path, when="1545", now=NOW, fetch=full_fetch(), cboe_fetch=None)
    snap = logger.load_snapshot(SESSION, "1545", tmp_path)
    quotes = logger.snapshot_quotes(snap, "spy")
    assert quotes and all(isinstance(q, OptionQuote) for q in quotes)
    assert quotes == fetch()  # same data after the JSON round trip
    assert logger.load_snapshot(date(2026, 9, 28), "1545", tmp_path)["date"] == SESSION
    assert logger.snapshot_quotes(snap, "QQQ") == [] and logger.snapshot_quotes(None, "SPY") == []


def test_load_snapshot_missing_or_corrupt_returns_none(tmp_path):
    assert logger.load_snapshot(SESSION, "close", tmp_path) is None
    assert logger.load_snapshot(SESSION, "noon", tmp_path) is None
    assert logger.load_snapshot("not-a-date", "close", tmp_path) is None
    path = logger.snapshot_path(SESSION, "close", tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not gzip")
    assert logger.load_snapshot(SESSION, "close", tmp_path) is None


def test_bad_when_is_refused(tmp_path):
    with pytest.raises(ValueError):
        logger.log_chains(["SPY"], tmp_path, when="noon", now=NOW, fetch=full_fetch(), cboe_fetch=None)


def test_nan_values_are_written_as_null(tmp_path):
    def f(underlying, **kw):
        q = fetch()
        q[0].delta = float("nan")
        q.meta["weird"] = float("inf")
        return q

    logger.log_chains(["SPY"], tmp_path, now=NOW, fetch=f, cboe_fetch=None)
    with gzip.open(logger.snapshot_path(SESSION, "close", tmp_path), "rt") as fh:
        text = fh.read()
    assert "NaN" not in text and "Infinity" not in text
    snap = logger.load_snapshot(SESSION, "close", tmp_path)
    assert logger.snapshot_quotes(snap, "SPY")[0].delta is None


def test_one_failing_underlying_does_not_stop_the_others(tmp_path):
    good = full_fetch()

    def f(underlying, **kw):
        if underlying == "QQQ":
            raise RuntimeError("boom")
        return good(underlying, **kw)

    rec = logger.log_chains(["SPY", "QQQ", "IWM"], tmp_path, now=NOW, fetch=f, cboe_fetch=None)
    assert rec["complete"] is False
    assert rec["per_underlying"]["SPY"]["complete"] and rec["per_underlying"]["IWM"]["complete"]
    assert rec["per_underlying"]["QQQ"] == {"n": 0, "complete": False, "contract_problems": 0}
    assert any(p.startswith("QQQ: fetch failed") and "boom" in p for p in rec["problems"])


def test_extra_symbols_route_to_their_underlying_and_add_it(tmp_path):
    f = full_fetch()
    spy_far = occ_symbol("SPY", "2026-12-18", "put", 400)
    iwm = occ_symbol("IWM", "2026-10-30", "put", 500)
    rec = logger.log_chains(["SPY"], tmp_path, now=NOW, fetch=f, extra_symbols=[spy_far, iwm, "junk"],
                            cboe_fetch=None)
    assert [c[0] for c in f.calls] == ["SPY", "IWM"]
    assert f.calls[0][1]["extra_symbols"] == (spy_far,) and f.calls[1][1]["extra_symbols"] == (iwm,)
    assert set(rec["per_underlying"]) == {"SPY", "IWM"}


def test_held_leg_not_logged_is_a_problem_but_not_incomplete(tmp_path):
    gone = occ_symbol("SPY", "2026-08-21", "put", 500)
    logger.log_chains(["SPY"], tmp_path, now=NOW, fetch=full_fetch(), extra_symbols=[gone], cboe_fetch=None)
    snap = logger.load_snapshot(SESSION, "close", tmp_path)
    block = snap["underlyings"]["SPY"]
    assert block["complete"] is True and any("not logged" in p and gone in p for p in block["problems"])


def test_live_held_leg_not_logged_makes_the_chain_incomplete(tmp_path):
    live = occ_symbol("SPY", "2026-10-16", "put", 555)  # not listed in the fake universe, not expired
    rec = logger.log_chains(U3, tmp_path, now=NOW, fetch=full_fetch(), extra_symbols=[live], cboe_fetch=None)
    assert rec["complete"] is False and rec["per_underlying"]["SPY"]["complete"] is False
    assert any("live held/shadow legs not logged" in p and live in p for p in rec["problems"])
    assert logger.complete_sessions(tmp_path) == 0


def test_spots_are_passed_through(tmp_path):
    f = full_fetch()
    logger.log_chains(["SPY", "QQQ"], tmp_path, now=NOW, fetch=f, spots={"SPY": 601.5}, cboe_fetch=None)
    assert f.calls[0][1]["spot"] == 601.5 and f.calls[1][1]["spot"] is None


def test_rerun_replaces_the_index_row(tmp_path):
    def broken(underlying, **kw):
        return ChainQuotes([], [], {"fatal": ["chain down"]})

    logger.log_chains(U3, tmp_path, now=NOW, fetch=broken, cboe_fetch=None)
    assert logger.load_index(tmp_path)[0]["complete"] is False
    logger.log_chains(U3, tmp_path, now=NOW, fetch=full_fetch(), cboe_fetch=None)
    index = logger.load_index(tmp_path)
    assert len(index) == 1 and index[0]["complete"] is True


def test_failed_rerun_never_replaces_a_complete_snapshot(tmp_path):
    first = logger.log_chains(U3, tmp_path, now=NOW, fetch=full_fetch(), cboe_fetch=None)
    assert first["kept_previous"] is False and logger.complete_sessions(tmp_path) == 1

    def boom(underlying, **kw):
        raise RuntimeError("feed down")

    later = NOW + timedelta(minutes=20)
    rec = logger.log_chains(U3, tmp_path, now=later, fetch=boom, cboe_fetch=None)
    assert rec["kept_previous"] is True and rec["complete"] is False and "failed-" in rec["path"]
    snap = logger.load_snapshot(SESSION, "close", tmp_path)
    assert snap["n"] == first["n"] and snap["complete"] is True
    index = logger.load_index(tmp_path)
    assert len(index) == 1 and index[0]["complete"] is True and index[0]["n"] == first["n"]
    assert index[0]["failed_reruns"][0]["taken_at"] == later.isoformat()
    assert logger.complete_sessions(tmp_path) == 1
    # a complete re-run still replaces the earlier complete one
    again = logger.log_chains(U3, tmp_path, now=later, fetch=full_fetch(), cboe_fetch=None)
    assert again["kept_previous"] is False and logger.load_index(tmp_path)[0]["taken_at"] == later.isoformat()


def test_subset_of_required_underlyings_does_not_count(tmp_path):
    """OPT-35 requires SPY, QQQ and IWM; a SPY-only or TSLA-only run never adds an OPT-41 session."""
    rec = logger.log_chains(["SPY"], tmp_path, now=NOW, fetch=full_fetch(), cboe_fetch=None)
    assert rec["per_underlying"]["SPY"]["complete"] is True and rec["complete"] is False
    assert any("QQQ not logged" in p for p in rec["problems"]) and any("IWM" in p for p in rec["problems"])
    rec = logger.log_chains(["TSLA"], tmp_path, when="1545", now=NOW, fetch=full_fetch(), cboe_fetch=None)
    assert rec["complete"] is False and logger.complete_sessions(tmp_path) == 0
    # a hand-written row that claims complete without the required names does not count either
    write_index(tmp_path, [{"date": SESSION, "when": "close", "complete": True, "file": rec["file"],
                            "per_underlying": {"SPY": {"complete": True}}}])
    assert logger.complete_sessions(tmp_path) == 0
    assert logger.complete_sessions(tmp_path, required=["SPY"]) == 1


def test_bare_string_underlying_is_one_symbol(tmp_path):
    f = full_fetch()
    logger.log_chains("spy", tmp_path, now=NOW, fetch=f, cboe_fetch=None)
    assert [c[0] for c in f.calls] == ["SPY"]


def test_corrupt_index_is_set_aside_and_rebuilt(tmp_path):
    f = full_fetch()
    for d in (28, 29, 30):
        now = datetime(2026, 9, d, 20, 30, tzinfo=timezone.utc)
        logger.log_chains(U3, tmp_path, now=now, fetch=fresh_fetch(f, now), cboe_fetch=None)
    assert logger.complete_sessions(tmp_path) == 3
    logger.index_path(tmp_path).write_text('[{"date": "2026-09-28", "wh')  # truncated
    now = datetime(2026, 10, 1, 20, 30, tzinfo=timezone.utc)
    logger.log_chains(U3, tmp_path, now=now, fetch=fresh_fetch(f, now), cboe_fetch=None)
    assert logger.complete_sessions(tmp_path) == 4
    assert list(logger.index_path(tmp_path).parent.glob("chain_log_index.corrupt-*.json"))
    assert [r["date"] for r in logger.load_index(tmp_path)] == ["2026-09-28", "2026-09-29", "2026-09-30",
                                                                "2026-10-01"]


def test_deleted_snapshot_file_does_not_count(tmp_path):
    logger.log_chains(U3, tmp_path, now=NOW, fetch=full_fetch(), cboe_fetch=None)
    assert logger.complete_sessions(tmp_path) == 1
    logger.snapshot_path(SESSION, "close", tmp_path).unlink()
    assert logger.complete_sessions(tmp_path) == 0


def test_session_date_is_new_york_date(tmp_path):
    late = datetime(2026, 9, 29, 2, 0, tzinfo=timezone.utc)  # still 28 Sep in New York
    rec = logger.log_chains(["SPY"], tmp_path, now=late, fetch=full_fetch(), cboe_fetch=None)
    assert rec["date"] == SESSION


def test_old_fetch_signature_list_without_meta(tmp_path):
    """A fetch returning a plain list (no problems/meta) still logs and is assessed."""
    rec = logger.log_chains(U3, tmp_path, now=NOW, fetch=lambda u, **kw: list(fetch()), cboe_fetch=None)
    assert rec["complete"] is True and rec["n"] == 3 * len(fetch())


def test_fetch_returning_none_or_junk(tmp_path):
    rec = logger.log_chains(["SPY"], tmp_path, now=NOW, fetch=lambda u, **kw: None, cboe_fetch=None)
    assert rec["complete"] is False and rec["n"] == 0
    rec = logger.log_chains(["SPY"], tmp_path, when="1545", now=NOW, fetch=lambda u, **kw: ["x", 1],
                            cboe_fetch=None)
    assert rec["complete"] is False and rec["n"] == 0


def test_no_underlyings_is_incomplete(tmp_path):
    rec = logger.log_chains([], tmp_path, now=NOW, fetch=full_fetch(), cboe_fetch=None)
    assert rec["complete"] is False and rec["n"] == 0


def test_default_state_dir_is_the_configured_one(tmp_path, monkeypatch):
    import trader.config as config

    monkeypatch.setattr(config, "STATE_DIR", tmp_path)
    logger.log_chains(now=NOW, fetch=full_fetch(), cboe_fetch=None)
    assert logger.load_snapshot(SESSION, "close") is not None
    assert logger.complete_sessions() == 1


# --- completeness rules ---------------------------------------------------------------------------------------


def quotes_n(n, **kw):
    out = []
    for i in range(n):
        q = OptionQuote(symbol=occ_symbol("SPY", "2026-10-30", "put", 500 + i), underlying="SPY", expiry="2026-10-30",
                        type="put", strike=500 + i, bid=1.0, ask=1.1, quote_time=QUOTE_TS.isoformat(), iv=0.2,
                        delta=-0.2, open_interest=900, open_interest_date="2026-09-25", volume=5)
        for k, v in kw.items():
            setattr(q, k, v(i) if callable(v) else v)
        out.append(q)
    return out


def test_assess_clean_chain_is_complete():
    assert logger.assess(quotes_n(40), SESSION, {"fatal": []}) == []
    assert logger.assess(quotes_n(40), SESSION) == []


def test_assess_too_few_contracts():
    assert "only 19 contracts" in logger.assess(quotes_n(19), SESSION)[0]
    assert "only 0 contracts" in logger.assess([], SESSION)[0]


def test_assess_fatal_problem():
    assert logger.assess(quotes_n(40), SESSION, {"fatal": ["bars down"]}) == ["fetch problem: bars down"]


@pytest.mark.parametrize("field,value,label", [
    ("bid", None, "bid/ask/quote time"),
    ("quote_time", "2026-09-25T19:59:00+00:00", "quotes dated today"),
    ("iv", None, "IV and delta"),
    ("open_interest", None, "open interest"),
])
def test_assess_coverage_thresholds(field, value, label):
    # 60% of contracts lose the field: below every threshold
    reasons = logger.assess(quotes_n(40, **{field: lambda i: value if i < 24 else getattr(quotes_n(1)[0], field)}),
                            SESSION)
    assert any(r.startswith(label) for r in reasons)


def test_assess_tolerates_a_few_gaps():
    reasons = logger.assess(quotes_n(40, iv=lambda i: None if i < 10 else 0.2,
                                     open_interest=lambda i: None if i < 4 else 900), SESSION)
    assert reasons == []


def test_stale_holiday_quotes_are_incomplete(tmp_path):
    friday = datetime(2026, 9, 25, 19, 59, tzinfo=timezone.utc)

    def f(u, **kw):
        q = fetch()
        for x in q:
            x.quote_time = friday.isoformat()
        return q

    rec = logger.log_chains(["SPY"], tmp_path, now=NOW, fetch=f, cboe_fetch=None)
    assert rec["complete"] is False and any("dated today" in p for p in rec["problems"])


def test_volume_failure_makes_chain_incomplete(tmp_path):
    rec = logger.log_chains(["SPY"], tmp_path, now=NOW, fetch=full_fetch(client={"fail": {"bars"}}),
                            cboe_fetch=None)
    assert rec["complete"] is False and any("option bars" in p for p in rec["problems"])


def fresh_fetch(f, now):
    """`f` with every quote dated `now` (so a run on another day is complete)."""
    def g(u, **kw):
        q = f(u, **kw)
        for x in q:
            x.quote_time = (now - timedelta(minutes=30)).isoformat()
        return q
    return g


def good_row(tmp_path, d, when, complete=True):
    """An index row as the logger writes it, with its snapshot file on disk."""
    rel = f"options/chains/{d}/{when}.json.gz"
    (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / rel).write_bytes(b"x")
    return {"date": d, "when": when, "complete": complete, "file": rel,
            "per_underlying": {u: {"n": 100, "complete": complete} for u in U3}}


def write_index(tmp_path, rows):
    path = logger.index_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows))


def test_complete_sessions_counts_distinct_dates_and_gaps_do_not_reset(tmp_path):
    rows = []
    d0 = date(2026, 9, 1)
    for i in range(50):
        d = (d0 + timedelta(days=i)).isoformat()
        rows.append(good_row(tmp_path, d, "close", i % 5 != 0))  # every 5th day incomplete
        rows.append(good_row(tmp_path, d, "1545"))
    write_index(tmp_path, rows)
    assert logger.complete_sessions(tmp_path) == 50  # any run complete that day
    assert logger.complete_sessions(tmp_path, when="close") == 40
    assert logger.complete_sessions(tmp_path, when="close", through="2026-09-10") == 8
    assert logger.complete_sessions(tmp_path, when="1545", through=date(2026, 9, 10)) == 10


def test_complete_sessions_ignores_junk_and_missing_index(tmp_path):
    assert logger.complete_sessions(tmp_path) == 0
    ok = good_row(tmp_path, "2026-09-02", "close")
    write_index(tmp_path, [{**good_row(tmp_path, "2026-09-01", "close"), "complete": "yes"}, "junk",
                           {**good_row(tmp_path, "2026-09-03", "close"), "date": None}, ok])
    assert logger.complete_sessions(tmp_path) == 1
    logger.index_path(tmp_path).write_text("{not json")
    assert logger.complete_sessions(tmp_path) == 0 and logger.load_index(tmp_path) == []
    logger.index_path(tmp_path).write_text('{"a": 1}')
    assert logger.load_index(tmp_path) == []


def test_complete_sessions_through_logger_runs(tmp_path):
    f = full_fetch()
    for d in [28, 29, 30]:
        now = datetime(2026, 9, d, 20, 30, tzinfo=timezone.utc)
        logger.log_chains(U3, tmp_path, now=now, fetch=fresh_fetch(f, now), cboe_fetch=None)
    assert logger.complete_sessions(tmp_path) == 3
    assert [r["date"] for r in logger.load_index(tmp_path)] == ["2026-09-28", "2026-09-29", "2026-09-30"]


# --- Cboe display values ---------------------------------------------------------------------------------------

VIX_CSV = "DATE,OPEN,HIGH,LOW,CLOSE\n09/24/2026,15.1,16.0,14.9,15.5\n09/25/2026,15.5,17.0,15.2,16.25\n"
SKEW_CSV = "DATE,SKEW\n09/24/2026,140.1\n09/25/2026,141.7\n"


def fake_cboe(fail=()):
    calls = []

    def f(url):
        calls.append(url)
        if any(n in url for n in fail):
            raise OSError("offline")
        return SKEW_CSV if "SKEW" in url else VIX_CSV

    f.calls = calls
    return f


def test_parse_cboe_csv():
    assert logger.parse_cboe_csv(VIX_CSV) == ("2026-09-25", 16.25)
    assert logger.parse_cboe_csv(SKEW_CSV) == ("2026-09-25", 141.7)
    assert logger.parse_cboe_csv(VIX_CSV + "09/26/2026,,,,\n") == ("2026-09-25", 16.25)  # blank last row skipped
    for bad in ("", "DATE,CLOSE\n", "DATE,CLOSE\nxx,yy\n"):
        with pytest.raises(ValueError):
            logger.parse_cboe_csv(bad)


def test_cboe_values_fetch_and_cache_once_today_is_in(tmp_path):
    f = fake_cboe()
    out = logger.cboe_values(tmp_path, fetch=f, now=NOW)
    assert out["VIX"] == {"value": 16.25, "date": "2026-09-25", "source": logger.CBOE_URL.format(name="VIX"),
                          "cached": False}
    assert out["SKEW"]["value"] == 141.7 and set(out) == {"VIX", "VIX3M", "VIX9D", "SKEW"}
    assert all(u.startswith("https://cdn.cboe.com/") for u in f.calls) and len(f.calls) == 4
    today = VIX_CSV + "09/28/2026,16.0,18.0,15.9,17.5\n"
    calls = []
    logger.cboe_values(tmp_path, fetch=lambda u: calls.append(u) or today, now=NOW, names=["VIX"])
    again = logger.cboe_values(tmp_path, fetch=lambda u: calls.append(u) or today, now=NOW, names=["VIX"])
    assert len(calls) == 1 and again["VIX"]["cached"] is True and again["VIX"]["value"] == 17.5


def test_cboe_close_run_refetches_after_the_1545_run(tmp_path):
    """The 15:45 run caches the previous close; the after-close run must pick up today's close."""
    at_1545 = datetime(2026, 9, 28, 19, 45, tzinfo=timezone.utc)
    logger.cboe_values(tmp_path, fetch=lambda u: VIX_CSV, now=at_1545, names=["VIX"])
    later = VIX_CSV + "09/28/2026,16.0,18.0,15.9,17.5\n"
    out = logger.cboe_values(tmp_path, fetch=lambda u: later, now=NOW, names=["VIX"])
    assert out["VIX"] == {"value": 17.5, "date": SESSION, "source": logger.CBOE_URL.format(name="VIX"),
                          "cached": False}


def test_cboe_offline_uses_stale_cache_or_reports_error(tmp_path):
    logger.cboe_values(tmp_path, fetch=fake_cboe(), now=NOW, names=["VIX"])
    tomorrow = NOW + timedelta(days=1)
    out = logger.cboe_values(tmp_path, fetch=fake_cboe(fail={"VIX"}), now=tomorrow, names=["VIX", "SKEW"])
    assert out["VIX"]["stale"] is True and out["VIX"]["value"] == 16.25 and "offline" in out["VIX"]["error"]
    assert out["SKEW"]["value"] == 141.7
    fresh = logger.cboe_values(tmp_path / "other", fetch=fake_cboe(fail={"VIX"}), now=NOW, names=["VIX"])
    assert "value" not in fresh["VIX"] and "offline" in fresh["VIX"]["error"]


def test_cboe_failure_never_makes_a_chain_incomplete(tmp_path):
    rec = logger.log_chains(U3, tmp_path, now=NOW, fetch=full_fetch(), cboe_fetch=fake_cboe(fail={"V", "S"}))
    assert rec["complete"] is True and "error" in rec["cboe"]["VIX"]
    snap = logger.load_snapshot(SESSION, "close", tmp_path)
    assert snap["cboe"]["SKEW"]["source"].endswith("SKEW_History.csv")


def test_cboe_values_in_snapshot(tmp_path):
    rec = logger.log_chains(["SPY"], tmp_path, now=NOW, fetch=full_fetch(), cboe_fetch=fake_cboe())
    assert rec["cboe"]["VIX"]["value"] == 16.25
    assert logger.load_snapshot(SESSION, "close", tmp_path)["cboe"]["VIX3M"]["value"] == 16.25


def test_cboe_skip_and_crashing_fetcher(tmp_path, monkeypatch):
    assert logger.log_chains(["SPY"], tmp_path, now=NOW, fetch=full_fetch(), cboe_fetch=False)["cboe"] == {}
    monkeypatch.setattr(logger, "cboe_values", lambda *a, **k: 1 / 0)
    rec = logger.log_chains(U3, tmp_path, now=NOW, fetch=full_fetch(), cboe_fetch=fake_cboe())
    assert "error" in rec["cboe"] and rec["complete"] is True


def test_cboe_default_uses_real_fetcher(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(logger, "fetch_url", lambda url: seen.append(url) or VIX_CSV)
    rec = logger.log_chains(["SPY"], tmp_path, now=NOW, fetch=full_fetch())
    assert len(seen) == 4 and rec["cboe"]["VIX"]["value"] == 16.25


# --- data.py: raw bars for strike work (phase O0) -------------------------------------------------------------


class RecordingStockClient:
    def __init__(self):
        self.requests = []

    def get_stock_bars(self, req):
        import pandas as pd

        self.requests.append(req)
        return SimpleNamespace(df=pd.DataFrame())


def make_data():
    stock = RecordingStockClient()
    return AlpacaData("k", "s", fallback_feed=None, stock_client=stock, crypto_client=object(),
                      now=lambda: NOW), stock


def test_daily_bars_default_adjustment_is_all():
    d, stock = make_data()
    d.daily_bars(["SPY"], 10)
    d.daily_bars(["SPY"], 10, None, None)  # old positional call signature
    d.history(["SPY"], "2026-01-02", "2026-02-02")
    assert [r.adjustment.value for r in stock.requests] == ["all", "all", "all"]


@pytest.mark.parametrize("name,expected", [("raw", "raw"), ("RAW", "raw"), (" split ", "split"),
                                           ("dividend", "dividend"), (None, "all"), ("", "all")])
def test_daily_bars_adjustment_option(name, expected):
    d, stock = make_data()
    d.daily_bars(["SPY"], 10, adjustment=name)
    d.history(["SPY"], "2026-01-02", adjustment=name)
    assert [r.adjustment.value for r in stock.requests] == [expected, expected]


def test_raw_adjustment_kept_on_the_fallback_feed():
    class FailingSip(RecordingStockClient):
        def get_stock_bars(self, req):
            if req.feed.value == "sip":
                self.requests.append(req)
                raise RuntimeError("sip down")
            return super().get_stock_bars(req)

    stock = FailingSip()
    d = AlpacaData("k", "s", fallback_feed="iex", stock_client=stock, crypto_client=object(), now=lambda: NOW)
    d.daily_bars(["SPY"], 10, adjustment="raw")
    assert [(r.feed.value, r.adjustment.value) for r in stock.requests] == [("sip", "raw"), ("iex", "raw")]


def test_adjustment_enum_accepted_and_unknown_refused():
    from alpaca.data.enums import Adjustment

    d, stock = make_data()
    d.daily_bars(["SPY"], 5, adjustment=Adjustment.RAW)
    assert stock.requests[-1].adjustment.value == "raw"
    with pytest.raises(ValueError):
        d.daily_bars(["SPY"], 5, adjustment="adjusted")
    assert len(stock.requests) == 1  # refused before any request


def test_option_bars_end_at_least_15_minutes_ago(no_sleep):
    """Free plan: bars ending 'now' are refused with 'OPRA agreement is not signed'; requests must end 16 min ago."""
    client = FakeOptionClient()
    fetch(client=client)
    ends = [r.end for r in client.bar_requests]
    assert ends and all(NOW - e.astimezone(timezone.utc) >= timedelta(minutes=15) for e in ends)


def test_before_the_open_volume_is_unknown_not_zero(no_sleep):
    """Before 00:16 NY on the session day there are no servable bars: volume stays None, one clear note, no request."""
    early = datetime(2026, 9, 28, 4, 5, tzinfo=timezone.utc)  # 00:05 New York
    meta = {"fatal": []}
    q = [type("Q", (), {"symbol": occ_symbol("SPY", "2026-10-30", "put", 560), "volume": 7})()]
    calls = []

    class C:
        def get_option_bars(self, req):
            calls.append(req)
            raise AssertionError("no request expected")

    chain._add_volume(C(), q, date(2026, 9, 28), early, meta)
    assert calls == [] and q[0].volume is None
    assert any("not available yet" in f for f in meta["fatal"])
