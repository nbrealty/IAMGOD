"""M3: data feed (SIP with IEX fallback), EX-7 data checks, and both brokers (EX-1, EX-2, EX-4). No network."""
import json
import math
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from conftest import make_bars
from trader import broker as broker_mod
from trader.broker import (FINAL_STATUSES, AlpacaPaperBroker, SimBroker, assign_client_ids, fill_row,
                           make_client_order_id, ny_date, status_str, time_in_force)
from trader.data import AlpacaData, problem_symbols, validate
from trader.models import Order

NOW = datetime(2026, 9, 25, 21, 35, tzinfo=timezone.utc)


def utc(dt):
    """alpaca-py stores request times as naive UTC; compare on that basis."""
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


# --- fakes ------------------------------------------------------------------------------------------


def alpaca_frame(symbols, days=5, end="2026-09-25", tz="UTC", volume=1_000_000.0):
    """Alpaca-style bars: MultiIndex (symbol, timestamp) with bars stamped at midnight New York time."""
    rows = []
    dates = pd.bdate_range(end=end, periods=days)
    for s in symbols:
        for i, d in enumerate(dates):
            ts = pd.Timestamp(d).tz_localize("America/New_York").tz_convert(tz)
            rows.append({"symbol": s, "timestamp": ts, "open": 100.0 + i, "high": 102.0 + i, "low": 99.0 + i,
                         "close": 101.0 + i, "volume": volume, "trade_count": 10, "vwap": 100.5})
    return pd.DataFrame(rows).set_index(["symbol", "timestamp"])


class FakeStockClient:
    """Records every request. `fail` maps feed name -> exception; `empty` lists feeds that answer nothing."""

    def __init__(self, fail=None, empty=()):
        self.fail, self.empty, self.requests = dict(fail or {}), set(empty), []

    def get_stock_bars(self, req):
        self.requests.append(req)
        feed = req.feed.value
        if feed in self.fail:
            raise self.fail[feed]
        syms = req.symbol_or_symbols if isinstance(req.symbol_or_symbols, list) else [req.symbol_or_symbols]
        return SimpleNamespace(df=pd.DataFrame() if feed in self.empty else alpaca_frame(syms))


class FakeCryptoClient:
    def __init__(self):
        self.requests = []

    def get_crypto_bars(self, req):
        self.requests.append(req)
        return SimpleNamespace(df=alpaca_frame(req.symbol_or_symbols, volume=0.0))


def make_data(**kw):
    stock, crypto = kw.pop("stock", FakeStockClient()), kw.pop("crypto", FakeCryptoClient())
    return AlpacaData("k", "s", stock_client=stock, crypto_client=crypto, now=lambda: NOW, **kw), stock, crypto


class NotFound(Exception):
    status_code = 404


class FakeTradingClient:
    def __init__(self, orders=None, errors=None, submit_errors=(), submit_status="accepted"):
        self.orders = dict(orders or {})  # client id -> order object
        self.by_id = {str(getattr(o, "id", "")): o for o in self.orders.values()}
        self.errors = dict(errors or {})  # client id -> exception
        self.submit_errors, self.submit_status = set(submit_errors), submit_status
        self.submitted, self.lookups, self.cancelled = [], [], 0

    def submit_order(self, req):
        self.submitted.append(req)
        if req.symbol in self.submit_errors:
            raise RuntimeError("insufficient buying power")
        from alpaca.trading.enums import OrderStatus
        return SimpleNamespace(status=OrderStatus(self.submit_status), id=f"uuid-{len(self.submitted)}",
                               client_order_id=req.client_order_id)

    def get_order_by_client_id(self, cid):
        self.lookups.append(("client", cid))
        if cid in self.errors:
            raise self.errors[cid]
        if cid not in self.orders:
            raise NotFound('{"code":40410000,"message":"order not found"}')
        return self.orders[cid]

    def get_order_by_id(self, oid):
        self.lookups.append(("id", oid))
        if oid not in self.by_id:
            raise NotFound("order not found")
        return self.by_id[oid]

    def cancel_orders(self):
        self.cancelled += 1

    def get_account(self):
        return SimpleNamespace(equity="100123.45", cash="5000.5")

    def get_all_positions(self):
        return [SimpleNamespace(symbol="SPY", qty="10"), SimpleNamespace(symbol="BTCUSD", qty="0.25")]


def alpaca_order(status, filled_qty="0", price=None, filled_at=None, updated_at=None, symbol="SPY", side="buy",
                 oid="uuid-1", cid="c1"):
    from alpaca.trading.enums import OrderSide, OrderStatus
    return SimpleNamespace(status=OrderStatus(status), filled_qty=filled_qty, filled_avg_price=price,
                           filled_at=filled_at, updated_at=updated_at, symbol=symbol, side=OrderSide(side),
                           id=oid, client_order_id=cid)


def alpaca_broker(**kw):
    client = FakeTradingClient(**kw)
    return AlpacaPaperBroker("k", "s", ["BTC/USD"], client=client), client


# --- data feed: SIP first, IEX fallback -----------------------------------------------------------------


def test_sip_request_ends_16_minutes_ago_and_splits_bars():
    data, stock, _ = make_data()
    bars = data.daily_bars(["SPY", "QQQ"], 10)
    [req] = stock.requests
    assert req.feed.value == "sip"
    assert utc(req.end) == utc(NOW - timedelta(minutes=16))
    assert data.feed_used == "sip" and data.notes == []
    assert set(bars) == {"SPY", "QQQ"}
    df = bars["SPY"]
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.tz is None and df.index[-1] == pd.Timestamp("2026-09-25")  # New York date, not UTC
    assert df.index.is_monotonic_increasing and df.dtypes.eq(float).all()


def test_daily_bars_keeps_calendar_padding():
    data, stock, _ = make_data()
    data.daily_bars(["SPY"], 100)
    start = stock.requests[0].start
    assert utc(start) == utc(NOW - timedelta(days=160))  # 1.5 x 100 + 10 calendar days


def test_sip_failure_retries_once_with_iex():
    data, stock, _ = make_data(stock=FakeStockClient(fail={"sip": RuntimeError("subscription does not permit")}))
    bars = data.daily_bars(["SPY"], 10)
    assert [r.feed.value for r in stock.requests] == ["sip", "iex"]
    assert stock.requests[1].end is None  # IEX has no 15-minute delay rule
    assert data.feed_used == "iex" and "SPY" in bars
    text = " ".join(data.notes)
    assert "SIP" in text and "failed" in text and "subscription does not permit" in text and "IEX" in text


def test_empty_sip_answer_also_falls_back():
    data, stock, _ = make_data(stock=FakeStockClient(empty={"sip"}))
    bars = data.daily_bars(["SPY"], 10)
    assert data.feed_used == "iex" and "SPY" in bars
    assert any("returned no bars" in n for n in data.notes)


def test_both_feeds_failing_raises_clear_error():
    stock = FakeStockClient(fail={"sip": RuntimeError("sip down"), "iex": RuntimeError("iex down")})
    data, _, _ = make_data(stock=stock)
    with pytest.raises(RuntimeError, match="SIP and IEX.*iex down"):
        data.daily_bars(["SPY"], 10)
    assert len(stock.requests) == 2  # retried once, not more
    assert data.feed_used is None


def test_no_fallback_when_feeds_match():
    stock = FakeStockClient(fail={"iex": RuntimeError("down")})
    data, _, _ = make_data(stock=stock, feed="iex", fallback_feed="iex")
    with pytest.raises(RuntimeError):
        data.daily_bars(["SPY"], 10)
    assert len(stock.requests) == 1


def test_notes_reset_each_fetch():
    stock = FakeStockClient(fail={"sip": RuntimeError("down")})
    data, _, _ = make_data(stock=stock)
    data.daily_bars(["SPY"], 10)
    assert data.notes
    stock.fail.clear()
    data.daily_bars(["SPY"], 10)
    assert data.notes == [] and data.feed_used == "sip"


def test_history_dates_are_inclusive_new_york_days():
    data, stock, crypto = make_data()
    out = data.history(["SPY", "BTC/USD", "SPY"], "2016-01-04", "2020-06-30")
    req = stock.requests[0]
    assert req.symbol_or_symbols == ["SPY"]  # de-duplicated, crypto separate
    assert utc(req.start) == datetime(2016, 1, 4, 5, 0)  # midnight New York (winter), in UTC
    assert utc(req.end) == datetime(2020, 7, 1, 3, 59, 59)  # end of 30 June in New York, in UTC
    [creq] = crypto.requests
    assert creq.start == req.start and creq.end == req.end
    assert {"SPY", "BTC/USD"} <= set(out)


def test_sip_end_in_the_future_is_clamped_but_past_end_is_kept():
    data, stock, _ = make_data()
    data.daily_bars(["SPY"], 10, end="2026-09-26")
    assert utc(stock.requests[-1].end) == utc(NOW - timedelta(minutes=16))
    data.daily_bars(["SPY"], 10, start="2026-01-02", end="2026-03-31")
    assert utc(stock.requests[-1].end) == datetime(2026, 4, 1, 3, 59, 59)
    assert utc(stock.requests[-1].start) == datetime(2026, 1, 2, 5, 0)


def test_crypto_path_uses_crypto_client_only():
    data, stock, crypto = make_data()
    out = data.daily_bars(["BTC/USD"], 10)
    assert stock.requests == [] and len(crypto.requests) == 1 and "BTC/USD" in out
    assert crypto.requests[0].end is None  # unchanged: open-ended request
    assert data.feed_used is None


def test_from_env_reads_feeds_from_config(cfg, monkeypatch):
    monkeypatch.delenv("ALPACA_DATA_KEY", raising=False)
    monkeypatch.delenv("ALPACA_DATA_SECRET", raising=False)
    monkeypatch.setenv("ALPACA_RULES_KEY", "rk")
    monkeypatch.setenv("ALPACA_RULES_SECRET", "rs")
    d = AlpacaData.from_env(cfg)
    assert (d.feed, d.fallback_feed) == (cfg.playbook["data"]["feed"], cfg.playbook["data"]["fallback_feed"])
    old = AlpacaData.from_env()  # old call without cfg
    assert (old.feed, old.fallback_feed) == ("sip", "iex")


def test_from_env_never_mixes_key_pairs(monkeypatch):
    captured = {}

    def fake_init(self, key, secret, feed="sip", fallback_feed="iex", **kw):
        captured.update(key=key, secret=secret)

    monkeypatch.setattr(AlpacaData, "__init__", fake_init)
    monkeypatch.setenv("ALPACA_DATA_KEY", "dk")  # data key without its secret
    monkeypatch.delenv("ALPACA_DATA_SECRET", raising=False)
    monkeypatch.setenv("ALPACA_RULES_KEY", "rk")
    monkeypatch.setenv("ALPACA_RULES_SECRET", "rs")
    AlpacaData.from_env()
    assert captured == {"key": "rk", "secret": "rs"}
    for v in ("ALPACA_DATA_KEY", "ALPACA_RULES_KEY", "ALPACA_RULES_SECRET"):
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(RuntimeError, match="ALPACA_DATA_KEY"):
        AlpacaData.from_env()


def test_daily_bars_with_only_an_end_counts_back_from_that_end():
    data, stock, _ = make_data()
    data.daily_bars(["SPY"], 100, end="2020-06-30")
    req = stock.requests[-1]
    end = datetime(2020, 7, 1, 3, 59, 59)  # end of 30 June in New York, in UTC
    assert utc(req.end) == end and utc(req.start) == end - timedelta(days=160)
    assert req.start < req.end
    data.daily_bars(["SPY"], 100, end="2026-12-31")  # a future end: count back from now
    assert utc(stock.requests[-1].start) == utc(NOW - timedelta(days=160))


def test_feed_names_are_normalised_and_blank_config_means_sip(cfg, monkeypatch):
    data, stock, _ = make_data(feed="SIP", fallback_feed=" IEX ")
    assert (data.feed, data.fallback_feed) == ("sip", "iex")
    data.daily_bars(["SPY"], 10)
    [req] = stock.requests
    assert req.feed.value == "sip" and utc(req.end) == utc(NOW - timedelta(minutes=16))  # clamp still applies
    blank, stock2, _ = make_data(feed=None)
    blank.daily_bars(["SPY"], 10)  # no AttributeError from a blank feed
    assert blank.feed == "sip" and blank.feed_used == "sip" and stock2.requests[0].feed.value == "sip"
    none_fb, _, _ = make_data(fallback_feed="")
    assert none_fb.fallback_feed is None
    monkeypatch.setenv("ALPACA_DATA_KEY", "dk")
    monkeypatch.setenv("ALPACA_DATA_SECRET", "ds")
    monkeypatch.setitem(cfg.playbook, "data", {**cfg.playbook["data"], "feed": None})
    assert AlpacaData.from_env(cfg).feed == "sip"


def test_old_constructor_signature_still_works():
    d = AlpacaData("k", "s", feed="iex", stock_client=FakeStockClient(), crypto_client=FakeCryptoClient())
    assert d.feed == "iex" and d.fallback_feed == "iex"
    real = AlpacaData("k", "s")  # builds real clients; constructing them makes no network call
    assert real.feed == "sip" and real.fallback_feed == "iex"


# --- EX-7 data checks ----------------------------------------------------------------------------------


AS_OF = pd.Timestamp("2026-09-25")


def clean(n=60, crypto=False):
    return make_bars(n=n, seed=3, crypto=crypto)


def test_clean_data_has_no_problems(cfg, bars):
    as_of = bars["SPY"].index[-1]
    assert validate(bars, cfg.allowlist(), as_of) == []
    assert validate({"SPY": clean()}, ["SPY"], AS_OF, 5, 0.25, True) == []


def test_missing_and_empty_data():
    empty = clean().iloc[:0]
    probs = validate({"A": empty, "B": clean()[["open"]]}, ["A", "B", "C"], AS_OF)
    assert probs == ["A: no data", "B: no data", "C: no data"]


def test_stale_bar():
    df = make_bars(n=60, seed=3, end="2026-09-18")
    assert validate({"X": df}, ["X"], AS_OF) == ["X: stale, last bar 2026-09-18"]
    assert validate({"X": df}, ["X"], AS_OF, max_stale_days=10) == []


def test_stale_boundary_is_more_than_five_days():
    df = make_bars(n=60, seed=3, end="2026-09-18")
    assert validate({"X": df}, ["X"], "2026-09-23") == []  # 5 days old: fine
    assert validate({"X": df}, ["X"], "2026-09-24") == ["X: stale, last bar 2026-09-18"]  # 6 days old


def test_infinite_close_is_a_bad_close():
    last = clean()
    last.iloc[-1, last.columns.get_loc("close")] = np.inf
    assert "X: bad close values" in validate({"X": last}, ["X"], AS_OF)
    mid = clean()
    mid.iloc[20, mid.columns.get_loc("close")] = -np.inf
    assert "X: bad close values" in validate({"X": mid}, ["X"], AS_OF)


def test_nan_previous_close_does_not_hide_a_big_move():
    df = clean()
    df.iloc[-2, df.columns.get_loc("close")] = np.nan
    df.iloc[-1, df.columns.get_loc("close")] = df["close"].iloc[-3] * 1.6
    probs = validate({"X": df}, ["X"], AS_OF)
    assert any(p.startswith("X: close moved +60.0%") for p in probs)


def test_bad_close_values():
    df = clean()
    df.iloc[10, df.columns.get_loc("close")] = 0.0
    assert "X: bad close values" in validate({"X": df}, ["X"], AS_OF)
    df2 = clean()
    df2.iloc[-1, df2.columns.get_loc("close")] = np.nan
    probs = validate({"X": df2}, ["X"], AS_OF)
    assert "X: bad close values" in probs
    assert not any("moved" in p for p in probs)  # NaN close: no move maths, no crash


def test_zero_volume_on_last_bar_blocks_stocks_and_crypto():
    df = clean()
    df.iloc[-1, df.columns.get_loc("volume")] = 0.0
    [p] = validate({"AAPL": df}, ["AAPL"], AS_OF)
    assert p.startswith("AAPL: zero or missing volume on the last bar 2026-09-25")
    c = clean(crypto=True)
    c.iloc[-1, c.columns.get_loc("volume")] = 0.0
    # EX-7 has no crypto exemption, so the default blocks it; the opt-out still exists.
    [pc] = validate({"BTC/USD": c}, ["BTC/USD"], AS_OF)
    assert pc.startswith("BTC/USD: zero or missing volume")
    assert validate({"BTC/USD": c}, ["BTC/USD"], AS_OF, crypto_ok_zero_volume=True) == []
    assert validate({"BTC/USD": clean(crypto=True)}, ["BTC/USD"], AS_OF) == []
    # Zero volume earlier in history is not a last-bar problem.
    old = clean()
    old.iloc[-5, old.columns.get_loc("volume")] = 0.0
    assert validate({"AAPL": old}, ["AAPL"], AS_OF) == []


def test_missing_volume_is_a_problem_for_stocks():
    df = clean()
    df.iloc[-1, df.columns.get_loc("volume")] = np.nan
    assert validate({"SPY": df}, ["SPY"], AS_OF)
    assert validate({"SPY": clean().drop(columns="volume")}, ["SPY"], AS_OF)


def test_big_last_move_is_flagged_both_ways():
    for factor, sign in ((1.31, "+"), (0.70, "-")):
        df = clean()
        df.iloc[-1, df.columns.get_loc("close")] = df["close"].iloc[-2] * factor
        [p] = validate({"NVDA": df}, ["NVDA"], AS_OF)
        assert p.startswith(f"NVDA: close moved {sign}") and "adjusted" in p and "corporate action" in p


def test_move_limit_is_strictly_greater():
    df = clean()
    df.iloc[-1, df.columns.get_loc("close")] = df["close"].iloc[-2] * 1.24
    assert validate({"X": df}, ["X"], AS_OF) == []
    assert validate({"X": df}, ["X"], AS_OF, max_daily_move=0.20)
    df.iloc[-1, df.columns.get_loc("close")] = df["close"].iloc[-2] * 1.25
    assert validate({"X": df}, ["X"], AS_OF) == []
    assert validate({"X": df}, ["X"], AS_OF, max_daily_move=None) == []


def test_only_last_bar_move_counts():
    df = clean()
    df.iloc[-10, df.columns.get_loc("close")] = df["close"].iloc[-11] * 1.6
    assert validate({"X": df}, ["X"], AS_OF) == []


def test_short_history_and_nan_previous_close():
    one = clean().iloc[-1:]
    assert validate({"X": one}, ["X"], AS_OF) == []
    df = clean()
    df.iloc[-2, df.columns.get_loc("close")] = np.nan
    assert validate({"X": df}, ["X"], AS_OF) == []


def test_missing_open_on_last_bar():
    df = clean()
    df.iloc[-1, df.columns.get_loc("open")] = np.nan
    assert validate({"X": df}, ["X"], AS_OF) == ["X: missing open/high/low on the last bar 2026-09-25"]


def test_as_of_forms_and_tz_aware_index():
    df = clean()
    aware = df.copy()
    aware.index = aware.index.tz_localize("America/New_York")
    for as_of in ("2026-09-25", AS_OF, pd.Timestamp("2026-09-25 21:35", tz="UTC")):
        assert validate({"X": df, "Y": aware}, ["X", "Y"], as_of) == []


def test_unsorted_bars_are_checked_on_the_real_last_bar():
    df = clean()
    df.iloc[-1, df.columns.get_loc("volume")] = 0.0
    shuffled = df.sample(frac=1.0, random_state=1)
    assert validate({"SPY": shuffled}, ["SPY"], AS_OF)


def test_problem_format_and_symbols():
    df = clean()
    df.iloc[-1, df.columns.get_loc("volume")] = 0.0
    probs = validate({"SPY": df}, ["SPY", "BTC/USD"], AS_OF)
    assert all(": " in p for p in probs)
    assert problem_symbols(probs) == {"SPY", "BTC/USD"}


# --- Alpaca broker -------------------------------------------------------------------------------------


def test_client_order_ids_are_short_unique_and_rerun_safe():
    orders = [Order("SPY", "buy", 1, 500), Order("SPY", "buy", 2, 500), Order("BTC/USD", "sell", 0.1, 60000)]
    ids = assign_client_ids(orders, "claude-2026-09-25", "a1b2c3")
    assert len(set(ids)) == 3 and all(len(i) <= 48 for i in ids)
    assert ids[0] == "claude-2026-09-25-SPY-buy-1-a1b2c3"
    assert ids[2] == "claude-2026-09-25-BTCUSD-sell-3-a1b2c3"
    again = assign_client_ids(orders, "claude-2026-09-25", "d4e5f6")
    assert not set(ids) & set(again)  # a --force rerun on the same date gets new ids
    long = make_client_order_id("x" * 80, "GOOGL", "sell", 12, "abcdef")
    assert len(long) == 48 and long.endswith("-GOOGL-sell-12-abcdef")


def test_explicit_client_order_id_is_used_once():
    orders = [Order("SPY", "buy", 1, 500, client_order_id="mine-1"),
              Order("QQQ", "buy", 1, 400, client_order_id="mine-1")]
    ids = assign_client_ids(orders, "rules-2026-09-25", "s")
    assert ids[0] == "mine-1" and ids[1] != "mine-1" and ids[1].startswith("rules-2026-09-25-QQQ-buy-2")


def test_long_suffix_never_hangs_and_ids_stay_unique():
    import signal

    def boom(*_):
        raise TimeoutError("assign_client_ids hung")

    old = signal.signal(signal.SIGALRM, boom)
    signal.alarm(2)
    try:
        orders = [Order("SPY", "buy", 1, 500), Order("SPY", "buy", 1, 500), Order("SPY", "buy", 1, 500)]
        ids = assign_client_ids(orders, "rules-2026-09-25", "x" * 60)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    assert len(set(ids)) == 3 and all(len(i) <= 48 for i in ids)
    assert ids[0].endswith("-SPY-buy-1-xxxxxxxx")  # the suffix is capped, the order number kept
    long = make_client_order_id("p" * 80, "A" * 30, "sell", 7, "z" * 30)
    assert len(long) <= 48 and "-sell-7-" in long


def test_order_with_no_symbol_is_an_error_not_a_crash():
    orders = [Order(None, "buy", 1, 500), Order("SPY", "buy", 1, 500)]
    b, client = alpaca_broker()
    res = b.submit(orders, "p", suffix="x")
    assert res[0]["status"] == "error" and res[1]["status"] == "accepted" and len(client.submitted) == 1
    sim = SimBroker({"cash": 1000.0, "positions": {}}, {"SPY": 100.0}, BPS, asset_class)
    sres = sim.submit(orders, "p", suffix="x")
    assert sres[0]["status"] == "error" and sres[1]["status"] == "filled"


def test_both_brokers_take_the_same_submit_keywords():
    b, client = alpaca_broker()
    [r] = b.submit([Order("SPY", "buy", 1, 500)], "rules-2026-09-25", date="2026-09-25", suffix="abc")
    assert r["status"] == "accepted" and r["client_order_id"] == "rules-2026-09-25-SPY-buy-1-abc"
    bars = sim_bars()
    sim = SimBroker({"cash": 1000.0, "positions": {}}, last_close(bars), BPS, asset_class, bars=bars)
    [s] = sim.submit([Order("SPY", "buy", 1, 100.0)], "rules-2026-09-25", date="2026-09-25", suffix="abc")
    assert s["status"] == "accepted" and s["client_order_id"] == r["client_order_id"]


class AcceptThenRaiseClient(FakeTradingClient):
    """Alpaca stored the order, but the call still raised (a 504 retried into a duplicate-id error)."""

    def __init__(self, lookup_error=None, **kw):
        super().__init__(**kw)
        self.lookup_error = lookup_error

    def submit_order(self, req):
        self.submitted.append(req)
        self.orders[req.client_order_id] = alpaca_order("accepted", oid="uuid-real", cid=req.client_order_id)
        raise RuntimeError('{"code":40010001,"message":"client_order_id must be unique"}')

    def get_order_by_client_id(self, cid):
        if self.lookup_error is not None:
            self.lookups.append(("client", cid))
            raise self.lookup_error
        return super().get_order_by_client_id(cid)


def test_submit_that_raises_after_the_broker_accepted_is_not_booked_as_not_placed():
    client = AcceptThenRaiseClient()
    b = AlpacaPaperBroker("k", "s", [], client=client)
    [r] = b.submit([Order("SPY", "buy", 1, 500)], "rules-2026-09-25", suffix="abc")
    assert r["status"] == "accepted" and r["id"] == "uuid-real"
    assert r["client_order_id"] == "rules-2026-09-25-SPY-buy-1-abc" and "must be unique" in r["note"]
    # The lookup fails too: we cannot tell, so it stays pending ("unconfirmed"), never "error".
    shaky = AcceptThenRaiseClient(lookup_error=ConnectionError("reset"))
    [u] = AlpacaPaperBroker("k", "s", [], client=shaky).submit([Order("SPY", "buy", 1, 500)], "p", suffix="x")
    assert u["status"] == "unconfirmed" and "reset" in u["error"]
    # A plain rejection (the broker never stored it) is still an error.
    b2, c2 = alpaca_broker(submit_errors={"SPY"})
    [e] = b2.submit([Order("SPY", "buy", 1, 500)], "p", suffix="x")
    assert e["status"] == "error" and "buying power" in e["error"] and c2.lookups == [("client", e["client_order_id"])]


def api_error(body, status=404):
    from alpaca.common.exceptions import APIError
    return APIError(body, SimpleNamespace(response=SimpleNamespace(status_code=status), request=None))


def test_only_alpacas_order_not_found_ends_a_pending_order():
    errors = {"html": api_error("<html>404 Not Found</html>"), "route": RuntimeError("route not found"),
              "gone": api_error('{"code":40410000,"message":"order not found"}')}
    b, _ = alpaca_broker(errors=errors)
    rows = {r["client_order_id"]: r for r in b.order_fills([{"client_order_id": k} for k in errors])}
    for cid in ("html", "route"):  # a wrong URL or proxy page proves nothing: keep it pending
        assert rows[cid]["status"] == "error" and rows[cid]["final"] is False
    assert rows["gone"]["status"] == "unknown" and rows["gone"]["final"] is True


def test_submit_sends_market_orders_with_ex1_time_in_force():
    b, client = alpaca_broker()
    orders = [Order("SPY", "buy", 3, 500), Order("AAPL", "sell", 1.5, 200, client_order_id="set-id"),
              Order("BTC/USD", "buy", 0.01, 60000)]
    res = b.submit(orders, "rules-2026-09-25", suffix="abc123")
    kinds = [(r.symbol, r.side.value, r.time_in_force.value, r.type.value) for r in client.submitted]
    assert kinds == [("SPY", "buy", "day", "market"), ("AAPL", "sell", "day", "market"),
                     ("BTC/USD", "buy", "gtc", "market")]
    assert client.submitted[1].client_order_id == "set-id"
    assert [r["status"] for r in res] == ["accepted"] * 3  # lowercase text, not "OrderStatus.ACCEPTED"
    assert res[0] == {"symbol": "SPY", "side": "buy", "qty": 3, "status": "accepted", "id": "uuid-1",
                      "client_order_id": "rules-2026-09-25-SPY-buy-1-abc123"}
    assert time_in_force("ETH/USD") == "gtc" and time_in_force("QQQ") == "day"


def test_submit_default_suffix_differs_between_calls():
    b, client = alpaca_broker()
    r1 = b.submit([Order("SPY", "buy", 1, 500)], "rules-2026-09-25")
    r2 = b.submit([Order("SPY", "buy", 1, 500)], "rules-2026-09-25")
    assert r1[0]["client_order_id"] != r2[0]["client_order_id"]
    assert all(len(r["client_order_id"]) <= 48 for r in r1 + r2)


def test_submit_error_does_not_stop_other_orders():
    b, client = alpaca_broker(submit_errors={"QQQ"})
    res = b.submit([Order("QQQ", "buy", 1, 400), Order("SPY", "buy", 1, 500)], "p", suffix="x")
    assert res[0]["status"] == "error" and "buying power" in res[0]["error"] and res[0]["client_order_id"]
    assert res[1]["status"] == "accepted"


@pytest.mark.parametrize("order", [Order("SPY", "buy", 0, 500), Order("SPY", "sell", -1, 500),
                                   Order("SPY", "buy", float("nan"), 500), Order("SPY", "hold", 1, 500),
                                   Order("", "buy", 1, 500)])
def test_invalid_orders_never_reach_the_broker(order):
    b, client = alpaca_broker()
    [r] = b.submit([order], "p", suffix="x")
    assert r["status"] == "error" and client.submitted == []


def test_order_fills_filled_order():
    order = alpaca_order("filled", "3", "501.25", filled_at=datetime(2026, 9, 28, 13, 30, 5, tzinfo=timezone.utc))
    b, client = alpaca_broker(orders={"c1": order})
    [row] = b.order_fills([{"client_order_id": "c1", "symbol": "SPY"}])
    assert row["client_order_id"] == "c1" and row["status"] == "filled" and row["final"] is True
    assert row["filled_qty"] == 3.0 and isinstance(row["filled_qty"], float)
    assert row["filled_avg_price"] == 501.25 and row["filled_at"] == "2026-09-28"
    assert row["side"] == "buy" and row["symbol"] == "SPY"


def test_order_fills_uses_new_york_date():
    # 01:30 UTC on the 29th is still the evening of the 28th in New York (crypto fills around the clock).
    order = alpaca_order("filled", "0.5", "60000", filled_at=datetime(2026, 9, 29, 1, 30, tzinfo=timezone.utc))
    b, _ = alpaca_broker(orders={"c1": order})
    assert b.order_fills([{"client_order_id": "c1"}])[0]["filled_at"] == "2026-09-28"
    assert ny_date("2026-09-29T01:30:00Z") == "2026-09-28" and ny_date(None) is None and ny_date("junk") is None


def test_ny_date_keeps_a_bare_date():
    from datetime import date
    assert ny_date("2026-09-28") == "2026-09-28" and ny_date(pd.Timestamp("2026-09-28")) == "2026-09-28"
    assert ny_date(date(2026, 9, 28)) == "2026-09-28"
    assert ny_date("2026-09-29 01:30") == "2026-09-28"  # naive with a time: the broker's UTC clock
    raw = {"status": "filled", "filled_qty": "1", "filled_avg_price": "20", "filled_at": "2026-09-28"}
    b, _ = alpaca_broker(orders={"c": raw})
    assert b.order_fills([{"client_order_id": "c"}])[0]["filled_at"] == "2026-09-28"


@pytest.mark.parametrize("status,final", [("new", False), ("accepted", False), ("partially_filled", False),
                                          ("pending_new", False), ("filled", True), ("canceled", True),
                                          ("expired", True), ("rejected", True), ("done_for_day", True),
                                          ("replaced", True), ("pending_cancel", False),
                                          ("pending_replace", False), ("calculated", False), ("stopped", False),
                                          ("suspended", False), ("held", False)])
def test_order_fills_final_flag(status, final):
    b, _ = alpaca_broker(orders={"c1": alpaca_order(status)})
    [row] = b.order_fills([{"client_order_id": "c1"}])
    assert row["status"] == status and row["final"] is final
    assert row["filled_qty"] == 0.0 and row["filled_avg_price"] is None and row["filled_at"] is None


def test_partial_fill_then_cancel_keeps_quantity_and_date():
    order = alpaca_order("canceled", "4", "99.5", filled_at=None,
                         updated_at=datetime(2026, 9, 28, 19, 0, tzinfo=timezone.utc))
    b, _ = alpaca_broker(orders={"c1": order})
    [row] = b.order_fills([{"client_order_id": "c1"}])
    assert row["final"] and row["filled_qty"] == 4.0 and row["filled_avg_price"] == 99.5
    assert row["filled_at"] == "2026-09-28"
    partial = alpaca_order("partially_filled", "2", "99.0", filled_at=None,
                           updated_at=datetime(2026, 9, 28, 14, 0, tzinfo=timezone.utc))
    b2, _ = alpaca_broker(orders={"c2": partial})
    [row2] = b2.order_fills([{"client_order_id": "c2"}])
    assert row2["final"] is False and row2["filled_qty"] == 2.0


def test_order_fills_unknown_and_errors_never_raise():
    good = alpaca_order("filled", "1", "10", filled_at="2026-09-28T13:30:00Z")
    b, _ = alpaca_broker(orders={"good": good}, errors={"flaky": ConnectionError("timeout")})
    rows = b.order_fills([{"client_order_id": "missing"}, {"client_order_id": "flaky"},
                          {"client_order_id": "good"}, {}])
    assert rows[0] == {"client_order_id": "missing", "status": "unknown", "final": True, "filled_qty": 0.0,
                       "filled_avg_price": None, "filled_at": None}
    assert rows[1]["status"] == "error" and rows[1]["final"] is False and "timeout" in rows[1]["error"]
    assert rows[2]["status"] == "filled" and rows[2]["filled_qty"] == 1.0
    assert rows[3]["status"] == "unknown" and rows[3]["final"] is True
    assert b.order_fills([]) == [] and b.order_fills(None) == []


def test_order_fills_falls_back_to_broker_order_id():
    order = alpaca_order("filled", "2", "50", filled_at="2026-09-28T14:00:00Z", oid="uuid-9", cid="other")
    b, client = alpaca_broker(orders={"other": order})
    [row] = b.order_fills([{"client_order_id": "lost", "broker_order_id": "uuid-9"}])
    assert row["status"] == "filled" and row["client_order_id"] == "lost" and row["filled_qty"] == 2.0
    assert client.lookups == [("client", "lost"), ("id", "uuid-9")]


def test_order_fills_handles_raw_dicts_and_text_numbers():
    raw = {"status": "filled", "filled_qty": "1.5", "filled_avg_price": "20.0",
           "filled_at": "2026-09-28T13:31:00Z", "id": "u", "symbol": "IEF", "side": "sell"}
    b, _ = alpaca_broker(orders={"c": raw})
    [row] = b.order_fills([{"client_order_id": "c"}])
    assert row["filled_qty"] == 1.5 and row["filled_avg_price"] == 20.0 and row["side"] == "sell"


def test_status_and_fill_row_helpers():
    from alpaca.trading.enums import OrderStatus
    assert status_str(OrderStatus.DONE_FOR_DAY) == "done_for_day"
    assert status_str("OrderStatus.FILLED") == "filled" and status_str(None) == ""
    assert FINAL_STATUSES == {"filled", "canceled", "expired", "rejected", "done_for_day", "replaced"}
    row = fill_row("c", "filled", filled_qty=float("nan"), filled_avg_price=5.0, filled_at="2026-09-28")
    assert row["filled_qty"] == 0.0 and row["filled_avg_price"] is None and row["filled_at"] is None


def test_alpaca_account_positions_cancel_and_name():
    b, client = alpaca_broker()
    assert b.name == "alpaca-paper" and SimBroker.name == "sim"
    assert b.account() == (100123.45, 5000.5)
    assert b.positions() == {"SPY": 10.0, "BTC/USD": 0.25}
    with pytest.raises(ValueError):  # owner decision 6: a bare cancel would hit book O's orders too
        b.cancel_open_orders()
    assert client.cancelled == 0
    b.cancel_open_orders(all_orders=True)
    assert client.cancelled == 1


def test_for_book_needs_both_keys(monkeypatch):
    monkeypatch.delenv("ALPACA_CLAUDE_KEY", raising=False)
    monkeypatch.delenv("ALPACA_CLAUDE_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="ALPACA_CLAUDE_KEY"):
        AlpacaPaperBroker.for_book("claude", [])


# --- simulator -----------------------------------------------------------------------------------------


BPS = {"etf": 5, "stock": 10, "crypto": 25}


def asset_class(sym):
    return "crypto" if "/" in sym else ("stock" if sym in ("AAPL", "MSFT") else "etf")


def sim_bars(end="2026-09-25", n=30):
    return {"SPY": make_bars(n=n, seed=1, end=end), "AAPL": make_bars(n=n, seed=2, end=end),
            "BTC/USD": make_bars(n=n, seed=3, end=end, crypto=True)}


def last_close(bars):
    return {s: float(df["close"].iloc[-1]) for s, df in bars.items()}


def test_sim_old_signature_fills_immediately_at_close():
    state = {"cash": 10000.0, "positions": {}}
    b = SimBroker(state, {"SPY": 100.0}, BPS, asset_class)
    assert b.fill_mode == "close"
    [r] = b.submit([Order("SPY", "buy", 10, 100.0)], "rules-2026-09-25")
    assert r["status"] == "filled" and r["fill_price"] == 100.05 and r["filled_qty"] == 10
    assert r["client_order_id"].startswith("rules-2026-09-25-SPY-buy-1-")
    assert state["positions"]["SPY"] == 10 and math.isclose(state["cash"], 10000 - 1000.5)
    equity, cash = b.account()
    assert math.isclose(equity, cash + 1000.0)
    [r2] = b.submit([Order("SPY", "sell", 4, 110.0)], "rules-2026-09-26")
    assert r2["fill_price"] == round(110 * (1 - 0.0005), 4) and state["positions"]["SPY"] == 6
    rows = b.order_fills([{"client_order_id": r["client_order_id"]}, {"client_order_id": r2["client_order_id"]}])
    assert [x["status"] for x in rows] == ["filled", "filled"] and all(x["final"] for x in rows)
    assert rows[0]["filled_avg_price"] == pytest.approx(100.05)


def test_sim_close_mode_never_goes_short():
    state = {"cash": 0.0, "positions": {"SPY": 2.0}}
    b = SimBroker(state, {"SPY": 100.0}, BPS, asset_class)
    [r] = b.submit([Order("SPY", "sell", 5, 100.0)], "p", suffix="x")
    assert r["status"] == "filled" and r["filled_qty"] == 2.0 and state["positions"]["SPY"] == 0
    [r2] = b.submit([Order("SPY", "sell", 1, 100.0)], "p", suffix="y")
    assert r2["status"] == "rejected" and r2["filled_qty"] == 0 and state["positions"]["SPY"] == 0


def test_sim_next_open_cycle():
    today = sim_bars("2026-09-25")
    state = {"cash": 10000.0, "positions": {}}
    b = SimBroker(state, last_close(today), BPS, asset_class, bars=today)
    assert b.fill_mode == "next_open"
    res = b.submit([Order("SPY", "buy", 10, 100.0), Order("AAPL", "buy", 5, 50.0)], "rules-2026-09-25",
                   suffix="s1")
    assert [r["status"] for r in res] == ["accepted", "accepted"]
    assert state["cash"] == 10000.0 and state["positions"] == {}
    assert [o["date"] for o in state["open_orders"]] == ["2026-09-25", "2026-09-25"]
    pending = [{"client_order_id": r["client_order_id"]} for r in res]
    # Same run, same bars: nothing is due yet.
    rows = b.order_fills(pending)
    assert [r["status"] for r in rows] == ["accepted", "accepted"] and not any(r["final"] for r in rows)
    # Next run: one more bar exists, so both orders fill at that bar's open plus cost.
    tomorrow = sim_bars("2026-09-28", n=31)
    b2 = SimBroker(state, last_close(tomorrow), BPS, asset_class, bars=tomorrow)
    rows = b2.order_fills(pending)
    spy_open = float(tomorrow["SPY"].loc["2026-09-28", "open"])
    aapl_open = float(tomorrow["AAPL"].loc["2026-09-28", "open"])
    assert rows[0]["status"] == "filled" and rows[0]["final"] and rows[0]["filled_at"] == "2026-09-28"
    assert rows[0]["filled_avg_price"] == pytest.approx(spy_open * 1.0005)
    assert rows[1]["filled_avg_price"] == pytest.approx(aapl_open * 1.0010)
    assert state["positions"] == {"SPY": 10.0, "AAPL": 5.0}
    assert state["cash"] == pytest.approx(10000 - 10 * spy_open * 1.0005 - 5 * aapl_open * 1.001)
    assert state["open_orders"] == []
    # Asking again returns the same answer and does not fill twice.
    again = b2.order_fills(pending)
    assert again == rows and state["positions"] == {"SPY": 10.0, "AAPL": 5.0}
    json.dumps(state)  # the sim state stays JSON safe


def test_sim_next_open_sells_before_buys_and_caps_sells():
    today = sim_bars("2026-09-25")
    state = {"cash": 0.0, "positions": {"SPY": 3.0}}
    b = SimBroker(state, last_close(today), BPS, asset_class, bars=today)
    res = b.submit([Order("AAPL", "buy", 1, 50.0), Order("SPY", "sell", 5, 100.0),
                    Order("MSFT", "sell", 1, 300.0)], "p", suffix="x")
    tomorrow = sim_bars("2026-09-28", n=31)
    tomorrow["MSFT"] = make_bars(n=31, seed=9, end="2026-09-28")
    b2 = SimBroker(state, last_close(tomorrow), BPS, asset_class, bars=tomorrow)
    rows = b2.order_fills([{"client_order_id": r["client_order_id"]} for r in res])
    assert rows[1]["filled_qty"] == 3.0 and state["positions"]["SPY"] == 0  # never short
    assert rows[2]["status"] == "rejected" and rows[2]["final"] and rows[2]["filled_qty"] == 0
    closed = list(state["closed_orders"].values())
    assert [c["side"] for c in closed[:2]] == ["sell", "sell"] and closed[-1]["side"] == "buy"


def test_sim_cancel_fills_due_orders_first_then_cancels_rest():
    today = sim_bars("2026-09-25")
    state = {"cash": 10000.0, "positions": {}}
    b = SimBroker(state, last_close(today), BPS, asset_class, bars=today)
    res = b.submit([Order("SPY", "buy", 1, 100.0), Order("AAPL", "buy", 1, 50.0)], "p", suffix="x")
    tomorrow = sim_bars("2026-09-28", n=31)
    tomorrow["AAPL"] = today["AAPL"]  # no new AAPL bar (stale data): its order cannot fill
    b2 = SimBroker(state, last_close(tomorrow), BPS, asset_class, bars=tomorrow)
    b2.cancel_open_orders()
    rows = b2.order_fills([{"client_order_id": r["client_order_id"]} for r in res])
    assert rows[0]["status"] == "filled" and rows[0]["filled_qty"] == 1.0
    assert rows[1]["status"] == "canceled" and rows[1]["final"] and rows[1]["filled_qty"] == 0.0
    assert state["open_orders"] == [] and "AAPL" not in state["positions"]


def test_sim_date_argument_and_missing_date():
    state = {"cash": 1000.0, "positions": {}}
    bars = sim_bars("2026-09-25")
    b = SimBroker(state, last_close(bars), BPS, asset_class, bars=bars)
    [r] = b.submit([Order("SPY", "buy", 1, 100.0)], "p", date="2026-09-24", suffix="x")
    assert state["open_orders"][0]["date"] == "2026-09-24"
    rows = b.order_fills([{"client_order_id": r["client_order_id"]}])  # the 25th's bar is after the 24th
    assert rows[0]["filled_at"] == "2026-09-25"
    assert rows[0]["filled_avg_price"] == pytest.approx(float(bars["SPY"]["open"].iloc[-1]) * 1.0005)
    nob = SimBroker({"cash": 1.0, "positions": {}}, {}, BPS, asset_class, fill_mode="next_open")
    with pytest.raises(ValueError):
        nob.submit([Order("SPY", "buy", 1, 100.0)], "p")
    [ok] = nob.submit([Order("SPY", "buy", 1, 100.0)], "p", date=pd.Timestamp("2026-09-25"))
    assert ok["status"] == "accepted"
    with pytest.raises(ValueError):
        SimBroker({}, {}, BPS, asset_class, fill_mode="instant")


def test_sim_signal_date_is_the_new_york_day_of_an_aware_date():
    bars = sim_bars("2026-09-25")
    state = {"cash": 100000.0, "positions": {}}
    b = SimBroker(state, last_close(bars), BPS, asset_class, bars=bars)
    # 01:30 UTC on the 26th is the evening of the 25th in New York.
    [r] = b.submit([Order("BTC/USD", "buy", 0.1, 100.0)], "p", date=pd.Timestamp("2026-09-26 01:30", tz="UTC"),
                   suffix="x")
    assert state["open_orders"][0]["date"] == "2026-09-25"
    weekend = sim_bars("2026-09-26", n=31)
    [row] = SimBroker(state, last_close(weekend), BPS, asset_class, bars=weekend).order_fills(
        [{"client_order_id": r["client_order_id"]}])
    assert row["filled_at"] == "2026-09-26"  # the next bar, not one bar late


def test_sim_buys_never_spend_more_than_the_cash():
    today = sim_bars("2026-09-25")
    state = {"cash": 1000.0, "positions": {}}
    b = SimBroker(state, last_close(today), BPS, asset_class, bars=today)
    [r] = b.submit([Order("SPY", "buy", 1000, 100.0)], "p", suffix="x")
    tomorrow = sim_bars("2026-09-28", n=31)
    [row] = SimBroker(state, last_close(tomorrow), BPS, asset_class, bars=tomorrow).order_fills(
        [{"client_order_id": r["client_order_id"]}])
    gross = float(tomorrow["SPY"].loc["2026-09-28", "open"]) * 1.0005
    assert row["status"] == "filled" and row["final"]
    assert 0 < row["filled_qty"] < 1000 and row["filled_qty"] == pytest.approx(1000.0 / gross, abs=1e-5)
    assert -1e-6 <= state["cash"] < 0.01 and state["positions"]["SPY"] == row["filled_qty"]
    assert "not enough cash" in state["closed_orders"][r["client_order_id"]]["note"]
    # No cash at all: rejected, nothing changes. Close mode caps the same way.
    broke = {"cash": 0.0, "positions": {}}
    [z] = SimBroker(broke, {"SPY": 100.0}, BPS, asset_class).submit([Order("SPY", "buy", 1, 100.0)], "p", suffix="y")
    assert z["status"] == "rejected" and z["filled_qty"] == 0 and broke == {"cash": 0.0, "positions": {},
                                                                            "closed_orders": broke["closed_orders"]}
    small = {"cash": 250.0, "positions": {}}
    [c] = SimBroker(small, {"SPY": 100.0}, BPS, asset_class).submit([Order("SPY", "buy", 5, 100.0)], "p", suffix="z")
    assert c["status"] == "filled" and c["filled_qty"] == pytest.approx(250 / 100.05, abs=1e-5)
    assert small["cash"] >= -1e-6 and "not enough cash" in c["note"]


def test_sim_cost_outside_price_matches_a_ledger_that_charges_model_cost():
    today = sim_bars("2026-09-25")
    state = {"cash": 10000.0, "positions": {}}
    b = SimBroker(state, last_close(today), BPS, asset_class, bars=today, cost_in_price=False)
    [buy] = b.submit([Order("SPY", "buy", 10, 100.0)], "p", suffix="b")
    day1 = sim_bars("2026-09-28", n=31)
    b1 = SimBroker(state, last_close(day1), BPS, asset_class, bars=day1, cost_in_price=False)
    [f1] = b1.order_fills([{"client_order_id": buy["client_order_id"]}])
    open1 = float(day1["SPY"].loc["2026-09-28", "open"])
    assert f1["filled_avg_price"] == pytest.approx(open1)  # raw open; the cost went to cash separately
    [sell] = b1.submit([Order("SPY", "sell", 10, 100.0)], "p", suffix="s")
    day2 = sim_bars("2026-09-29", n=32)
    [f2] = SimBroker(state, last_close(day2), BPS, asset_class, bars=day2, cost_in_price=False).order_fills(
        [{"client_order_id": sell["client_order_id"]}])
    open2 = float(day2["SPY"].loc["2026-09-29", "open"])
    assert f2["filled_avg_price"] == pytest.approx(open2)
    # What a ledger books: (sell fill - buy fill) x qty minus the model cost on each side.
    rate = 5 / 10_000
    ledger_pnl = 10 * (f2["filled_avg_price"] - f1["filled_avg_price"]) - 10 * (f1["filled_avg_price"]
                                                                              + f2["filled_avg_price"]) * rate
    assert state["cash"] - 10000.0 == pytest.approx(ledger_pnl) and state["positions"]["SPY"] == 0
    # The default keeps the cost inside the price (the spec's "open +/- bps").
    assert SimBroker({"cash": 1.0, "positions": {}}, {}, BPS, asset_class).cost_in_price is True


def test_sim_skips_bars_with_bad_open():
    today = sim_bars("2026-09-25")
    state = {"cash": 1000.0, "positions": {}}
    b = SimBroker(state, last_close(today), BPS, asset_class, bars=today)
    [r] = b.submit([Order("SPY", "buy", 1, 100.0)], "p", suffix="x")
    later = sim_bars("2026-09-29", n=32)
    later["SPY"].loc["2026-09-28", "open"] = np.nan
    b2 = SimBroker(state, last_close(later), BPS, asset_class, bars=later)
    [row] = b2.order_fills([{"client_order_id": r["client_order_id"]}])
    assert row["filled_at"] == "2026-09-29"


def test_sim_crypto_fills_next_calendar_day_with_crypto_cost():
    today = sim_bars("2026-09-25")
    state = {"cash": 100000.0, "positions": {}}
    b = SimBroker(state, last_close(today), BPS, asset_class, bars=today)
    [r] = b.submit([Order("BTC/USD", "buy", 0.5, 100.0)], "p", suffix="x")
    weekend = sim_bars("2026-09-26", n=31)  # crypto has a Saturday bar; stocks do not
    b2 = SimBroker(state, last_close(weekend), BPS, asset_class, bars=weekend)
    [row] = b2.order_fills([{"client_order_id": r["client_order_id"]}])
    assert row["filled_at"] == "2026-09-26"
    assert row["filled_avg_price"] == pytest.approx(float(weekend["BTC/USD"]["open"].iloc[-1]) * 1.0025)


def test_sim_rejects_bad_orders_and_duplicate_ids_without_state_change():
    bars = sim_bars()
    state = {"cash": 1000.0, "positions": {}}
    b = SimBroker(state, last_close(bars), BPS, asset_class, bars=bars)
    res = b.submit([Order("SPY", "buy", 0, 100.0), Order("SPY", "buy", 1, 100.0, client_order_id="dup")], "p",
                   suffix="x")
    assert res[0]["status"] == "error" and res[1]["status"] == "accepted"
    [dup] = b.submit([Order("SPY", "buy", 1, 100.0, client_order_id="dup")], "p", suffix="y")
    assert dup["status"] == "error" and "duplicate" in dup["error"]
    assert len(state["open_orders"]) == 1 and state["cash"] == 1000.0
    close_b = SimBroker({"cash": 1.0, "positions": {}}, {}, BPS, asset_class)
    [nan_px] = close_b.submit([Order("SPY", "buy", 1, float("nan"))], "p", suffix="z")
    assert nan_px["status"] == "error"


def test_sim_unknown_order_and_unknown_asset_class_cost():
    b = SimBroker({"cash": 1000.0, "positions": {}}, {"ZZZ": 10.0}, BPS, lambda s: "bond")
    assert b.order_fills([{"client_order_id": "nope"}])[0]["status"] == "unknown"
    [r] = b.submit([Order("ZZZ", "buy", 1, 10.0)], "p", suffix="x")
    assert r["filled_avg_price"] == pytest.approx(10 * 1.0025)  # the highest configured cost


def test_sim_closed_orders_are_trimmed(monkeypatch):
    monkeypatch.setattr(broker_mod, "SIM_CLOSED_KEEP", 3)
    state = {"cash": 1e6, "positions": {}}
    b = SimBroker(state, {"SPY": 100.0}, BPS, asset_class)
    res = b.submit([Order("SPY", "buy", 1, 100.0) for _ in range(5)], "p", suffix="x")
    assert list(state["closed_orders"]) == [r["client_order_id"] for r in res[-3:]]


def test_sim_account_and_positions_unchanged():
    state = {"cash": 500.0, "positions": {"SPY": 2.0, "QQQ": 0.0, "IEF": 1e-15}}
    b = SimBroker(state, {"SPY": 100.0, "QQQ": 50.0}, BPS, asset_class)
    assert b.account() == (700.0, 500.0)
    assert b.positions() == {"SPY": 2.0}
