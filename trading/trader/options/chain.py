"""Option chain fetch for book O (Options rulebook phase O0; OPT-12 inputs, OPT-35).

`fetch_chain` joins three public Alpaca sources into one `OptionQuote` per contract:
- quotes, implied volatility and greeks from `OptionHistoricalDataClient.get_option_chain`, always on the free
  **indicative** feed (derived from OPRA, not real OPRA quotes; every quote is tagged `feed="indicative"`);
- open interest and its date, and the `tradable` flag, from `TradingClient.get_option_contracts` (the figure is
  the prior day's, so its date is kept);
- today's volume from `get_option_bars` (the snapshot has no volume). No bar today means no trades: volume 0.

It never raises for one bad contract: the problem is written to `result.problems` and the rest is kept.
Fetch-level failures (a whole source down) go to `result.meta["fatal"]`, which makes the logged chain
incomplete (OPT-41 counts only complete sessions). Owner decision 7: public data only, source recorded.
"""
from __future__ import annotations

import math
import time as _time
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from .models import OptionQuote, is_occ, parse_occ

NY = ZoneInfo("America/New_York")
FEED = "indicative"
SOURCE = {
    "quotes_iv_greeks": "alpaca get_option_chain (indicative feed)",
    "open_interest": "alpaca get_option_contracts (prior-day open interest)",
    "volume": "alpaca get_option_bars (daily bar)",
    "spot": "alpaca latest stock trade (IEX)",
}
BAR_BATCH = 100  # symbols per option-bars request (Alpaca's option endpoints take at most 100 symbols)
BAR_RETRY_WAITS = (10.0, 30.0, 60.0)  # seconds before each retry of a failed bars batch (429 rate limit)
BAR_PACE = 0.35  # seconds between bars batches on big chains: stays under the free plan's 200 requests/minute
BAR_PACE_AFTER = 50  # chains needing more batches than this are paced (small ones are not)
MAX_PAGES = 50  # safety stop for the contracts pagination
_sleep = _time.sleep  # tests replace it


class ChainQuotes(list):
    """A plain list of `OptionQuote`s that also carries `problems` (per-contract notes) and `meta`.

    It is a real list, so callers that expect `list[OptionQuote]` keep working.
    """

    def __init__(self, quotes: Iterable[OptionQuote] = (), problems: list[str] | None = None,
                 meta: dict | None = None):
        super().__init__(quotes)
        self.problems: list[str] = list(problems or [])
        self.meta: dict = dict(meta or {})


def fetch_chain(underlying: str, *, client: Any = None, contracts_client: Any = None, dte_max: int = 70,
                put_range: tuple[float, float] = (0.70, 1.05), call_max: float = 1.15, spot: float | None = None,
                extra_symbols: Iterable[str] = (), stock_client: Any = None,
                now: datetime | None = None) -> ChainQuotes:
    """OPT-35 chain for one underlying: 0..`dte_max` DTE, puts at `put_range` x spot, calls from
    `put_range[0]` x spot up to `call_max` x spot, plus every symbol in `extra_symbols` whatever its range.

    `client` is an `OptionHistoricalDataClient`, `contracts_client` a `TradingClient`, `stock_client` a
    `StockHistoricalDataClient` (only used when `spot` is not given). Missing clients are built from the
    ALPACA_DATA_* keys. Returns a `ChainQuotes` list sorted by expiry, type and strike.
    """
    underlying = str(underlying).strip().upper()
    now = _as_utc(now)
    session = now.astimezone(NY).date()
    problems: list[str] = []
    meta = {"underlying": underlying, "session_date": session.isoformat(), "feed": FEED, "source": dict(SOURCE),
            "fatal": [], "spot": None, "spot_source": None, "dte_max": dte_max, "put_range": list(put_range),
            "call_max": call_max}
    try:
        client, contracts_client, stock_client = _clients(client, contracts_client, stock_client, spot is None)
    except Exception as e:  # no keys or no SDK: nothing can be fetched
        meta["fatal"].append(f"no Alpaca clients ({_short(e)})")
        return ChainQuotes([], problems, meta)

    spot = _resolve_spot(underlying, spot, stock_client, meta)
    extras, extra_problems = _own_extras(underlying, extra_symbols)
    problems += extra_problems
    snaps = _chain_snapshots(client, underlying, session, dte_max, put_range, call_max, spot, meta)
    snaps.update(_extra_snapshots(client, [s for s in extras if s not in snaps], meta, problems))
    quotes = _to_quotes(snaps, underlying, session, dte_max, put_range, call_max, spot, extras, problems)
    _add_contract_info(contracts_client, quotes, underlying, session, dte_max, extras, meta, problems)
    _add_volume(client, quotes, session, now, meta, problems)
    quotes.sort(key=lambda q: (q.expiry, q.type, q.strike, q.symbol))
    meta["n"] = len(quotes)
    return ChainQuotes(quotes, problems, meta)


MISSING_FIELDS = ("bid", "ask", "quote_time", "iv", "delta", "gamma", "theta", "vega", "open_interest",
                  "open_interest_date", "volume")


def missing_fields(q: OptionQuote) -> list[str]:
    """Names of the OPT-12 / OPT-27 inputs this quote lacks: bid, ask, quote time, IV, every greek (delta, gamma,
    theta, vega; OPT-10's short-vega cap needs vega), open interest with its date, and day volume.

    The book's leg filter and the OPT-27 data guard use it: a leg with a missing input is not eligible.
    """
    wanted = MISSING_FIELDS
    return [name for name in wanted if getattr(q, name) is None]


# --- clients and spot ---------------------------------------------------------------------------------


def _clients(client, contracts_client, stock_client, need_stock: bool):
    """Build only the clients that were not injected (tests always inject fakes)."""
    if client is not None and contracts_client is not None and (stock_client is not None or not need_stock):
        return client, contracts_client, stock_client
    from ..data import _env_key_pair

    key, secret = _env_key_pair()
    if client is None:
        from alpaca.data.historical import OptionHistoricalDataClient

        client = OptionHistoricalDataClient(key, secret)
    if contracts_client is None:
        from alpaca.trading.client import TradingClient

        contracts_client = TradingClient(key, secret, paper=True)
    if stock_client is None and need_stock:
        from alpaca.data.historical import StockHistoricalDataClient

        stock_client = StockHistoricalDataClient(key, secret)
    return client, contracts_client, stock_client


def _resolve_spot(underlying: str, spot, stock_client, meta: dict) -> float | None:
    """The given spot, else the latest IEX trade. A missing spot is fatal (the range cannot be applied)."""
    if _positive(spot):
        meta["spot"], meta["spot_source"] = float(spot), "caller"
        return float(spot)
    if spot is not None:
        meta["fatal"].append(f"spot {spot!r} is not a positive number")
        return None
    try:
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockLatestTradeRequest

        req = StockLatestTradeRequest(symbol_or_symbols=[underlying], feed=DataFeed.IEX)
        trade = _pick(stock_client.get_stock_latest_trade(req), underlying)
        price = _num(_attr(trade, "price"))
    except Exception as e:
        meta["fatal"].append(f"spot fetch failed ({_short(e)})")
        return None
    if not _positive(price):
        meta["fatal"].append("spot fetch returned no price")
        return None
    meta["spot"], meta["spot_source"] = price, SOURCE["spot"]
    return price


def _own_extras(underlying: str, extra_symbols: Iterable[str]) -> tuple[list[str], list[str]]:
    """OPT-35: held/shadow legs of this underlying. Bad symbols are reported, other underlyings skipped."""
    keep, problems = [], []
    for raw in extra_symbols or ():
        sym = str(raw or "").strip().upper()
        if not is_occ(sym):
            problems.append(f"{raw!r}: extra symbol is not an OCC option symbol")
        elif parse_occ(sym)["underlying"] == underlying and sym not in keep:
            keep.append(sym)
    return keep, problems


# --- snapshots (quotes, IV, greeks) ----------------------------------------------------------------------


def _chain_snapshots(client, underlying, session, dte_max, put_range, call_max, spot, meta) -> dict:
    """{symbol: snapshot} for puts and calls in range. No spot means no chain request (fatal already noted)."""
    if spot is None:
        return {}
    ranges = {"put": (put_range[0] * spot, put_range[1] * spot), "call": (put_range[0] * spot, call_max * spot)}
    out: dict = {}
    for opt_type, (lo, hi) in ranges.items():
        try:
            answer = client.get_option_chain(_chain_request(underlying, opt_type, session, dte_max, lo, hi))
            out.update(_as_dict(answer))
        except Exception as e:
            meta["fatal"].append(f"{opt_type} chain request failed ({_short(e)})")
    return out


def _chain_request(underlying, opt_type, session: date, dte_max, lo, hi):
    from alpaca.data.enums import OptionsFeed
    from alpaca.data.requests import OptionChainRequest
    from alpaca.trading.enums import ContractType

    return OptionChainRequest(
        underlying_symbol=underlying, feed=OptionsFeed.INDICATIVE, type=ContractType(opt_type),
        strike_price_gte=round(lo, 2), strike_price_lte=round(hi, 2),
        expiration_date_gte=session.isoformat(),
        expiration_date_lte=(session + timedelta(days=dte_max)).isoformat())


def _extra_snapshots(client, symbols: list[str], meta: dict, problems: list[str]) -> dict:
    """Snapshots for held/shadow legs outside the chain window (OPT-35: always logged)."""
    if not symbols:
        return {}
    try:
        from alpaca.data.enums import OptionsFeed
        from alpaca.data.requests import OptionSnapshotRequest

        req = OptionSnapshotRequest(symbol_or_symbols=symbols, feed=OptionsFeed.INDICATIVE)
        got = _as_dict(client.get_option_snapshot(req))
    except Exception as e:
        meta["fatal"].append(f"snapshot request for held/shadow legs failed ({_short(e)})")
        return {}
    for sym in symbols:
        if sym not in got:
            problems.append(f"{sym}: held/shadow leg has no snapshot (expired or unknown)")
    return got


def _to_quotes(snaps: dict, underlying, session, dte_max, put_range, call_max, spot, extras, problems) -> list:
    """One OptionQuote per snapshot inside the window (extras always kept); a bad one is reported, not raised."""
    quotes = []
    for sym, snap in snaps.items():
        try:
            q = _quote_from_snapshot(str(sym), snap)
        except Exception as e:
            problems.append(f"{sym}: bad snapshot ({_short(e)})")
            continue
        if q.underlying != underlying:
            continue
        if sym in extras or _in_window(q, session, dte_max, put_range, call_max, spot):
            quotes.append(q)
    return quotes


def _quote_from_snapshot(symbol: str, snap) -> OptionQuote:
    info = parse_occ(symbol)
    quote, greeks = _attr(snap, "latest_quote"), _attr(snap, "greeks")
    return OptionQuote(
        symbol=symbol, underlying=info["underlying"], expiry=info["expiry"], type=info["type"],
        strike=info["strike"], bid=_price(_attr(quote, "bid_price")), ask=_price(_attr(quote, "ask_price")),
        quote_time=_iso(_attr(quote, "timestamp")), iv=_positive_or_none(_attr(snap, "implied_volatility")),
        delta=_num(_attr(greeks, "delta")), gamma=_num(_attr(greeks, "gamma")),
        theta=_num(_attr(greeks, "theta")), vega=_num(_attr(greeks, "vega")),
        open_interest=None, open_interest_date=None, volume=None, tradable=False, feed=FEED)


def _in_window(q: OptionQuote, session: date, dte_max, put_range, call_max, spot) -> bool:
    """OPT-35 range: 0..dte_max DTE; puts 70-105% of spot; calls up to 115% of spot."""
    dte = (date.fromisoformat(q.expiry) - session).days
    if dte < 0 or dte > dte_max or not spot:
        return False
    m = q.strike / spot
    if q.type == "put":
        return put_range[0] - 1e-9 <= m <= put_range[1] + 1e-9
    return put_range[0] - 1e-9 <= m <= call_max + 1e-9


# --- open interest and tradable (get_option_contracts) ----------------------------------------------------


def _add_contract_info(contracts_client, quotes, underlying, session, dte_max, extras, meta, problems) -> None:
    """Fill open_interest, open_interest_date and tradable. Unknown contracts stay tradable=False (safer)."""
    if not quotes:
        return
    try:
        info = _contracts(contracts_client, underlying, session, dte_max, quotes, meta)
    except Exception as e:
        meta["fatal"].append(f"option contracts request failed ({_short(e)})")
        return
    for sym in [q.symbol for q in quotes if q.symbol not in info and q.symbol in extras]:
        try:
            info[sym] = contracts_client.get_option_contract(sym)
        except Exception as e:
            problems.append(f"{sym}: contract lookup failed ({_short(e)})")
    for q in quotes:
        c = info.get(q.symbol)
        if c is None:
            problems.append(f"{q.symbol}: not in the contracts list (open interest unknown, not tradable)")
            continue
        q.tradable = bool(_attr(c, "tradable"))
        q.open_interest = _count(_attr(c, "open_interest"))
        q.open_interest_date = _iso_date(_attr(c, "open_interest_date"))


def _contracts(contracts_client, underlying, session: date, dte_max, quotes, meta: dict | None = None) -> dict:
    """{symbol: contract} over every page of `get_option_contracts` for the window of `quotes`.

    A list still unfinished after MAX_PAGES is kept but recorded as fatal (never cut short silently)."""
    from alpaca.trading.requests import GetOptionContractsRequest

    strikes = [q.strike for q in quotes]
    out, token = {}, None
    for _ in range(MAX_PAGES):
        req = GetOptionContractsRequest(
            underlying_symbols=[underlying], expiration_date_gte=session.isoformat(),
            expiration_date_lte=(session + timedelta(days=dte_max)).isoformat(),
            strike_price_gte=f"{min(strikes):.2f}", strike_price_lte=f"{max(strikes):.2f}",
            limit=10000, page_token=token)
        answer = contracts_client.get_option_contracts(req)
        for c in _attr(answer, "option_contracts") or []:
            out[str(_attr(c, "symbol"))] = c
        token = _attr(answer, "next_page_token")
        if not token:
            break
    else:
        if token and meta is not None:  # the unread contracts would look untradable with no open interest
            meta["fatal"].append(f"option contracts list truncated after {MAX_PAGES} pages "
                                 f"({len(out)} contracts read)")
    return out


# --- day volume (get_option_bars) ---------------------------------------------------------------------------


_AUTH_WORDS = ("not signed", "forbidden", "unauthorized", "not authorized", "not entitled", "subscription")


def _status_code(e) -> int | None:
    """The HTTP status of an alpaca-py APIError (or anything with `status_code` / `response.status_code`)."""
    try:
        code = getattr(e, "status_code", None)
        if code is None:
            code = getattr(getattr(e, "response", None), "status_code", None)
        return int(code) if code is not None else None
    except Exception:  # noqa: BLE001 - a broken error object is treated as "no status"
        return None


def _auth_error(e) -> bool:
    """401/403 or entitlement wording ("OPRA agreement is not signed"): retrying cannot help."""
    code = _status_code(e)
    if code in (401, 403):
        return True
    return code is None and any(w in str(e).lower() for w in _AUTH_WORDS)


def _retryable(e) -> bool:
    """Only transient errors are retried: 429, 5xx, or a network error with no HTTP answer."""
    if _auth_error(e):
        return False
    code = _status_code(e)
    if code is None:
        return not isinstance(e, (TypeError, ValueError))
    return code == 429 or code >= 500


def _add_volume(client, quotes, session: date, now: datetime, meta, problems: list[str] | None = None) -> None:
    """Today's volume per contract. A missing bar means no trades (0); a failed request leaves None.

    A transient failure (429 when a big chain goes over the free plan's 200 requests a minute, 5xx, network) is
    retried after BAR_RETRY_WAITS, and big chains are paced. Only a batch that still fails is fatal. A permanent
    4xx is not retried, and an auth/entitlement error (401/403, e.g. "OPRA agreement is not signed") stops the
    remaining batches at once with one fatal entry that says how to fix it (it used to cost 100 s per batch).
    """
    from alpaca.data.requests import OptionBarsRequest
    from alpaca.data.timeframe import TimeFrame

    problems = problems if problems is not None else []
    start = datetime.combine(session, time(0, 0), NY).astimezone(timezone.utc)
    symbols = [q.symbol for q in quotes]
    batches = [symbols[i:i + BAR_BATCH] for i in range(0, len(symbols), BAR_BATCH)]
    pace = BAR_PACE if len(batches) > BAR_PACE_AFTER else 0.0
    volumes: dict[str, int | None] = {}
    failed: set[str] = set()
    abort = None
    for n, batch in enumerate(batches):
        if abort is not None:
            failed.update(batch)
            continue
        if n and pace:
            _sleep(pace)
        req = OptionBarsRequest(symbol_or_symbols=batch, timeframe=TimeFrame.Day, start=start, end=now)
        error, tries = None, 0
        for wait in (0.0, *BAR_RETRY_WAITS):
            if wait:
                _sleep(wait)
            try:
                tries += 1
                answer = client.get_option_bars(req)
            except Exception as e:
                error = e
                if not _retryable(e):
                    break
                continue
            error = None
            volumes.update(_day_volumes(answer, session, problems))
            break
        if error is None:
            continue
        failed.update(batch)
        if _auth_error(error):
            abort = error
            meta["fatal"].append(f"option bars not authorized ({_short(error)}); volume unknown for all "
                                 f"{len(symbols) - n * BAR_BATCH} remaining contracts, no more requests sent. If it "
                                 "says 'OPRA agreement is not signed', the owner signs it in the Alpaca dashboard")
        else:
            meta["fatal"].append(f"option bars request failed for {len(batch)} contracts after "
                                 f"{tries - 1} retries ({_short(error)})")
    for q in quotes:
        if q.symbol not in failed:
            q.volume = volumes.get(q.symbol, 0)


def _day_volumes(answer, session: date, problems: list[str] | None = None) -> dict[str, int | None]:
    """{symbol: volume of today's bar}. A bad bar gives that contract None and a problem; it never voids the
    batch."""
    problems = problems if problems is not None else []
    data = _attr(answer, "data")
    data = data if isinstance(data, dict) else (answer if isinstance(answer, dict) else {})
    out = {}
    for sym, bars in data.items():
        for bar in bars or []:
            try:
                ts = _attr(bar, "timestamp")
                if ts is not None and _as_utc(ts).astimezone(NY).date() != session:
                    continue
                vol = _count(_attr(bar, "volume"))
            except Exception as e:  # volume unknown for this contract only
                problems.append(f"{sym}: bad option bar, volume unknown ({_short(e)})")
                out.setdefault(str(sym), None)
                continue
            if vol is not None:
                out[str(sym)] = vol
    return out


# --- small helpers --------------------------------------------------------------------------------------------


def _attr(obj, name):
    """Attribute of an SDK object, or key of a dict (raw-data mode and test fakes)."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _as_dict(answer) -> dict:
    if answer is None:
        return {}
    if isinstance(answer, dict):
        return answer
    raise TypeError(f"expected a dict of snapshots, got {type(answer).__name__}")


def _pick(answer, symbol):
    return answer.get(symbol) if isinstance(answer, dict) else answer


def _num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _positive(x) -> bool:
    v = _num(x)
    return v is not None and v > 0


def _positive_or_none(x) -> float | None:
    v = _num(x)
    return v if v is not None and v > 0 else None


def _price(x) -> float | None:
    """A quote price: finite and >= 0, else None (a zero bid is real and kept; OPT-12 filters it)."""
    v = _num(x)
    return v if v is not None and v >= 0 else None


def _count(x) -> int | None:
    v = _num(x)
    return int(v) if v is not None and v >= 0 else None


def _iso(ts) -> str | None:
    if ts is None:
        return None
    try:
        return _as_utc(ts).isoformat()
    except Exception:
        return None


def _iso_date(d) -> str | None:
    if d is None:
        return None
    if isinstance(d, (date, datetime)):
        return (d.date() if isinstance(d, datetime) else d).isoformat()
    text = str(d).strip()
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def _as_utc(ts) -> datetime:
    """Aware UTC datetime. Naive datetimes are taken as UTC (alpaca-py's convention); None means now."""
    if ts is None:
        return datetime.now(timezone.utc)
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if not isinstance(ts, datetime):
        raise TypeError(f"not a timestamp: {ts!r}")
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)


def _short(e: Exception, limit: int = 160) -> str:
    text = f"{type(e).__name__}: {e}"
    return text if len(text) <= limit else text[: limit - 3] + "..."
