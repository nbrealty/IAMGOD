"""Minute bars for the scalp lab: Alpaca SIP 1-minute bars, regular session only, cached by symbol and month.

- Read-only: this module requests market data and the trading calendar. It never touches orders.
- The free plan refuses SIP data from the last 15 minutes, so no request ever ends later than now - 16 min.
- Bars are adjusted for splits AND dividends (Adjustment.ALL) by default: dividend-only adjustment removes the
  fake 'gap' on ex-dividend mornings, which matters for rules that compare today's prices to yesterday's close.
- The regular session is taken from Alpaca's trading calendar (real open and close per day), so half days
  (13:00 close) are right. Minutes without a trade have no bar; nothing is filled in here.
- Adjusted prices change after every later dividend or split (Alpaca re-prices all earlier bars as of the day
  of the request). So that one symbol never mixes price bases, each download that fetches anything re-checks
  one bar of every older cached month against a fresh request and re-fetches the months whose basis moved.
- The official daily close (Alpaca daily bar, which includes the 16:00 closing auction) is cached next to the
  minute bars: the minute data stop at the 15:59 bar, whose close is the last regular trade, not the auction.
- Cache: state/scalp_cache/<SYM>_<YYYYMM>.csv.gz plus a small .json note of how far the month was fetched, its
  price basis date and the month's official closes (csv.gz because pyarrow is not installed). The trading
  calendar is cached as calendar.csv.
Keys: ALPACA_SCALP_KEY/SECRET if set, otherwise ALPACA_RULES_KEY/SECRET (data calls only). Never printed.
"""
from __future__ import annotations

import json
import os
import time
import warnings
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

import pandas as pd

NY = "America/New_York"
TRADING_DIR = Path(__file__).resolve().parents[2]
CACHE_DIR = TRADING_DIR / "state" / "scalp_cache"
DELAY = pd.Timedelta(minutes=16)   # SIP data must be at least this old on the free plan
WARMUP_DAYS = 45                   # calendar days loaded before the start (14-day noise band, EMAs, prior day)
COLS = ["open", "high", "low", "close", "volume", "trade_count", "vwap"]
# Alpaca's own texts for errors that retrying cannot fix (only used when no status code is available)
_PERMANENT = ("subscription does not permit", "forbidden", "unauthorized", "not authorized",
              "invalid api key", "access key verification failed")


def keys() -> tuple[str, str]:
    for k, s in (("ALPACA_SCALP_KEY", "ALPACA_SCALP_SECRET"), ("ALPACA_RULES_KEY", "ALPACA_RULES_SECRET")):
        if os.environ.get(k) and os.environ.get(s):
            return os.environ[k], os.environ[s]
    raise RuntimeError("no Alpaca keys: set ALPACA_SCALP_KEY/ALPACA_SCALP_SECRET or ALPACA_RULES_KEY/SECRET")


def clients() -> tuple[Any, Any]:
    """Market-data client and a paper trading client (used only for the calendar)."""
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.trading.client import TradingClient
    k, s = keys()
    return StockHistoricalDataClient(k, s), TradingClient(k, s, paper=True)


def cap_end(end: pd.Timestamp, now: pd.Timestamp | None = None) -> pd.Timestamp:
    """Never ask for SIP data newer than now - 16 minutes."""
    now = now if now is not None else pd.Timestamp.now(tz="UTC")
    return min(pd.Timestamp(end).tz_convert("UTC"), now.tz_convert("UTC") - DELAY)


def _transient_types() -> tuple[type, ...]:
    out: list[type] = [ConnectionError, TimeoutError]
    try:
        import requests
        out += [requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError]
    except ImportError:  # pragma: no cover - requests comes with alpaca-py
        pass
    try:
        import urllib3
        out += [urllib3.exceptions.ProtocolError, urllib3.exceptions.TimeoutError]
    except ImportError:  # pragma: no cover
        pass
    return tuple(out)


def _status(e: Exception) -> int | None:
    for get in (lambda: getattr(e, "status_code", None), lambda: e.response.status_code):  # type: ignore[attr-defined]
        try:
            v = get()
        except Exception:  # APIError.status_code can itself raise without an http_error
            v = None
        if isinstance(v, int):
            return v
    return None


def _transient(e: Exception) -> bool:
    """Retry network failures, timeouts, 429 and 5xx. Classify by exception type first, then by HTTP status;
    only when neither says anything, look for Alpaca's known permanent messages."""
    if isinstance(e, _transient_types()):
        return True
    status = _status(e)
    if status is not None:
        return status == 429 or status >= 500
    if isinstance(e, (ValueError, TypeError, KeyError, AttributeError)):
        return False   # a bug or a bad request: retrying will not help
    msg = str(e).lower()
    return not any(p in msg for p in _PERMANENT)


def with_retry(fn: Callable[[], Any], tries: int = 4, base: float = 2.0,
               sleep: Callable[[float], None] = time.sleep) -> Any:
    """Call fn, retrying transient errors (timeouts, 429, 5xx) with exponential backoff."""
    for attempt in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - decide below
            if attempt == tries - 1 or not _transient(e):
                raise
            sleep(base * 2 ** attempt)
    raise AssertionError("unreachable")


# -------------------------------------------------------------------------------------------------- calendar
def fetch_calendar(trading_client: Any, start: date, end: date) -> pd.DataFrame:
    from alpaca.trading.requests import GetCalendarRequest
    rows = with_retry(lambda: trading_client.get_calendar(GetCalendarRequest(start=start, end=end)))

    def ny(t: Any) -> pd.Timestamp:   # Alpaca returns naive New York times
        t = pd.Timestamp(t)
        return t.tz_localize(NY) if t.tzinfo is None else t.tz_convert(NY)

    return pd.DataFrame([{"date": pd.Timestamp(r.date).date(), "open": ny(r.open), "close": ny(r.close)}
                         for r in rows])


def save_calendar(cal: pd.DataFrame, cache_dir: Path = CACHE_DIR) -> pd.DataFrame:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / "calendar.csv"
    if path.exists():
        cal = pd.concat([load_calendar(cache_dir), cal]).drop_duplicates("date", keep="last")
    cal = cal.sort_values("date").reset_index(drop=True)
    out = cal.assign(open=cal["open"].map(lambda t: t.isoformat()), close=cal["close"].map(lambda t: t.isoformat()))
    out.to_csv(path, index=False)
    return cal


def load_calendar(cache_dir: Path = CACHE_DIR) -> pd.DataFrame:
    path = cache_dir / "calendar.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing: run `python -m lab.scalp download ...` first")
    cal = pd.read_csv(path)
    cal["date"] = pd.to_datetime(cal["date"]).dt.date
    for col in ("open", "close"):
        cal[col] = pd.to_datetime(cal[col], utc=True).dt.tz_convert(NY)
    return cal


def sessions(cal: pd.DataFrame) -> dict[date, tuple[pd.Timestamp, pd.Timestamp]]:
    return {d: (o, c) for d, o, c in zip(cal["date"], cal["open"], cal["close"])}


def keep_rth(df: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    """Keep bars whose START is within [session open, session close) of their calendar day (half days too)."""
    if df.empty:
        return df
    idx = df.index.tz_convert(NY)
    sess = sessions(cal)
    d = pd.Series(idx.date, index=df.index)
    o = d.map(lambda x: sess.get(x, (pd.NaT, pd.NaT))[0])
    c = d.map(lambda x: sess.get(x, (pd.NaT, pd.NaT))[1])
    keep = (o.notna() & (idx >= pd.DatetimeIndex(o)) & (idx < pd.DatetimeIndex(c))).to_numpy()
    out = df[keep].copy()
    out.index = idx[keep]
    out.index.name = "ts"
    return out


# ------------------------------------------------------------------------------------------------------ bars
def fetch_bars(client: Any, symbol: str, start: pd.Timestamp, end: pd.Timestamp, adjustment: str = "all",
               now: pd.Timestamp | None = None, daily: bool = False) -> pd.DataFrame:
    """SIP bars in [start, end), end capped at now - 16 min: 1-minute bars with extended hours included
    (filtered later), or daily bars (`daily=True`, official open/high/low/close incl. the auctions)."""
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    end = cap_end(end, now)
    if end <= start:
        return pd.DataFrame(columns=COLS)
    req = StockBarsRequest(symbol_or_symbols=[symbol], timeframe=TimeFrame.Day if daily else TimeFrame.Minute,
                           start=start.tz_convert("UTC").to_pydatetime(), end=end.to_pydatetime(),
                           feed=DataFeed.SIP, adjustment=Adjustment(adjustment))
    df = with_retry(lambda: client.get_stock_bars(req)).df
    if df is None or df.empty:
        return pd.DataFrame(columns=COLS)
    df = df.reset_index()
    if "symbol" in df:
        df = df[df["symbol"] == symbol]
    df = df.set_index(pd.DatetimeIndex(pd.to_datetime(df["timestamp"], utc=True)))
    return df[[c for c in COLS if c in df]].sort_index()


def _month_path(cache_dir: Path, symbol: str, month: pd.Timestamp) -> Path:
    return cache_dir / f"{symbol.upper()}_{month:%Y%m}.csv.gz"


def _meta_path(path: Path) -> Path:
    return path.with_name(path.name.replace(".csv.gz", ".json"))


def _months(start: date, end: date) -> list[pd.Timestamp]:
    first = pd.Timestamp(start).replace(day=1)
    return list(pd.date_range(first, pd.Timestamp(end), freq="MS"))


def _day_end_utc(d: date) -> pd.Timestamp:
    return (pd.Timestamp(d) + pd.Timedelta(days=1)).tz_localize(NY).tz_convert("UTC")


def _basis(meta: dict) -> str:
    """When the month's adjusted prices were last known to be current (fetch time, or last re-check)."""
    return str(meta.get("basis_as_of") or meta.get("fetched_at") or "")


def _fetch_month(client: Any, sym: str, ms: pd.Timestamp, want: pd.Timestamp, cal: pd.DataFrame,
                 adjustment: str, now: pd.Timestamp, cache_dir: Path) -> int:
    """Fetch one month of minute bars (regular session kept) and its official daily closes; write the cache."""
    m0 = ms.tz_localize(NY).tz_convert("UTC")
    path = _month_path(cache_dir, sym, ms)
    rth = keep_rth(fetch_bars(client, sym, m0, want, adjustment, now), cal)
    daily = fetch_bars(client, sym, m0, want, adjustment, now, daily=True)
    sess = sessions(cal)
    closes = {}
    for ts, px in zip(daily.index, daily["close"] if "close" in daily else []):
        d = ts.tz_convert(NY).date()
        if d in sess and sess[d][1] <= want:   # only sessions that had closed when the data were fetched
            closes[d.isoformat()] = float(px)
    out = rth.copy()
    out.index = out.index.tz_convert("UTC")
    out.to_csv(path, index_label="ts", compression="gzip")
    _meta_path(path).write_text(json.dumps({
        "symbol": sym, "month": f"{ms:%Y-%m}", "through": want.isoformat(), "adjustment": adjustment,
        "rows": len(rth), "feed": "sip", "fetched_at": now.isoformat(), "basis_as_of": now.isoformat(),
        "official_close": closes}))
    return len(rth)


def _probe_changed(client: Any, sym: str, path: Path, adjustment: str, now: pd.Timestamp) -> bool:
    """Re-request the month's first cached bar: a different price means a later dividend or split re-priced it."""
    f = pd.read_csv(path, index_col="ts", nrows=1)
    if f.empty:
        return False
    t0 = pd.Timestamp(f.index[0])
    t0 = t0.tz_localize("UTC") if t0.tzinfo is None else t0.tz_convert("UTC")
    fresh = fetch_bars(client, sym, t0, t0 + pd.Timedelta(minutes=1), adjustment, now)
    if fresh.empty:
        return True   # cannot confirm: re-fetch to be safe
    old, new = float(f["close"].iloc[0]), float(fresh["close"].iloc[0])
    return abs(new / old - 1.0) > 1e-7


def _align_basis(client: Any, sym: str, cal: pd.DataFrame, adjustment: str, now: pd.Timestamp,
                 cache_dir: Path, log: Callable[[str], None]) -> int:
    """After new months were fetched `now`, bring every older cached month of `sym` onto the same price basis.
    All months last checked at one time moved by the same factor (a dividend or split re-prices every earlier
    bar alike), so one probe per basis date decides for the whole group."""
    groups: dict[str, list[tuple[Path, dict]]] = {}
    for mp in sorted(cache_dir.glob(f"{sym}_[0-9][0-9][0-9][0-9][0-9][0-9].json")):
        meta = json.loads(mp.read_text())
        b = pd.Timestamp(_basis(meta)) if _basis(meta) else None
        if meta.get("adjustment") != adjustment or (b is not None and b >= now):
            continue
        groups.setdefault(_basis(meta), []).append((mp.with_name(mp.name.replace(".json", ".csv.gz")), meta))
    refetched = 0
    for basis, items in groups.items():
        probe = next((p for p, m in reversed(items) if p.exists() and m.get("rows", 0) > 0), None)
        if probe is not None and adjustment != "raw" and _probe_changed(client, sym, probe, adjustment, now):
            log(f"{sym}: prices cached as of {basis[:10]} were re-adjusted since; re-fetching {len(items)} month(s)")
            for path, meta in items:
                ms = pd.Timestamp(meta["month"] + "-01")
                _fetch_month(client, sym, ms, pd.Timestamp(meta["through"]), cal, adjustment, now, cache_dir)
                refetched += 1
        else:
            for path, meta in items:
                _meta_path(path).write_text(json.dumps({**meta, "basis_as_of": now.isoformat()}))
    return refetched


def download(symbols: list[str], start: date, end: date, cache_dir: Path = CACHE_DIR, client: Any = None,
             trading_client: Any = None, adjustment: str = "all", now: pd.Timestamp | None = None,
             log: Callable[[str], None] = print) -> dict[str, int]:
    """Fetch and cache regular-session bars for [start - WARMUP_DAYS, end]. Complete months already cached with
    the same adjustment are skipped; the current month is re-fetched only past what is cached. When anything was
    fetched, older cached months of the symbol are re-checked so all share one price basis."""
    now = now if now is not None else pd.Timestamp.now(tz="UTC")
    if client is None or trading_client is None:
        client, trading_client = clients()
    s0 = start - timedelta(days=WARMUP_DAYS)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cal = save_calendar(fetch_calendar(trading_client, pd.Timestamp(s0).replace(day=1).date(), end), cache_dir)
    stop = cap_end(_day_end_utc(end), now)
    counts: dict[str, int] = {}
    for sym in symbols:
        sym = sym.upper()
        counts[sym] = 0
        fetched = False
        for ms in _months(s0, end):
            m0 = ms.tz_localize(NY).tz_convert("UTC")
            m1 = (ms + pd.offsets.MonthBegin(1)).tz_localize(NY).tz_convert("UTC")
            want = min(m1, stop)
            if want <= m0:
                continue
            path = _month_path(cache_dir, sym, ms)
            meta_path = _meta_path(path)
            if path.exists() and meta_path.exists():
                meta = json.loads(meta_path.read_text())
                if (meta.get("adjustment") == adjustment and pd.Timestamp(meta["through"]) >= want
                        and "official_close" in meta):
                    counts[sym] += int(meta.get("rows", 0))
                    continue
            n = _fetch_month(client, sym, ms, want, cal, adjustment, now, cache_dir)
            fetched = True
            counts[sym] += n
            log(f"{sym} {ms:%Y-%m}: {n} regular-session bars (through {want:%Y-%m-%d %H:%M} UTC)")
        if fetched and adjustment != "raw":
            _align_basis(client, sym, cal, adjustment, now, cache_dir, log)
    return counts


def load_bars(symbol: str, start: date, end: date, cache_dir: Path = CACHE_DIR) -> pd.DataFrame:
    """Cached regular-session bars indexed by bar-start time (New York) for session dates in [start, end].
    Warns when the months loaded were priced on different adjustment dates (mixed price basis)."""
    frames, bases = [], set()
    for ms in _months(start, end):
        path = _month_path(cache_dir, symbol, ms)
        if path.exists():
            mp = _meta_path(path)
            if mp.exists():
                bases.add(_basis(json.loads(mp.read_text()))[:10])
            f = pd.read_csv(path, index_col="ts")
            if not f.empty:
                f.index = pd.to_datetime(f.index, utc=True).tz_convert(NY)
                frames.append(f)
    if len(bases) > 1:
        warnings.warn(f"{symbol}: cached months have different price-adjustment dates {sorted(bases)}; "
                      f"re-run `python -m lab.scalp download` so they share one basis", stacklevel=2)
    if not frames:
        return pd.DataFrame(columns=COLS, index=pd.DatetimeIndex([], tz=NY, name="ts"))
    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    d = df.index.date
    return df[(d >= start) & (d <= end)]


def load_official_closes(symbol: str, start: date, end: date, cache_dir: Path = CACHE_DIR) -> dict[date, float]:
    """Official daily closes (closing auction) cached with the minute bars, by session date."""
    out: dict[date, float] = {}
    for ms in _months(start, end):
        mp = _meta_path(_month_path(cache_dir, symbol, ms))
        if mp.exists():
            for d, px in json.loads(mp.read_text()).get("official_close", {}).items():
                dd = date.fromisoformat(d)
                if start <= dd <= end:
                    out[dd] = float(px)
    return out


def prior_day_levels(bars: pd.DataFrame, cal: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per session date: the day's RTH open/high/low/close and the previous session's high/low/close.
    With a calendar, prev_* is NaN when the previous calendar session is missing from the data."""
    if bars.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "prev_high", "prev_low", "prev_close"])
    g = bars.groupby(bars.index.date)
    daily = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                          "close": g["close"].last()})
    prev = daily.shift(1)
    daily["prev_high"], daily["prev_low"], daily["prev_close"] = prev["high"], prev["low"], prev["close"]
    if cal is not None:
        dates = sorted(cal["date"])
        before = {d: p for p, d in zip(dates[:-1], dates[1:])}
        idx = list(daily.index)
        ok = [i > 0 and before.get(d) == idx[i - 1] for i, d in enumerate(idx)]
        daily.loc[[not x for x in ok], ["prev_high", "prev_low", "prev_close"]] = float("nan")
    daily.index.name = "date"
    return daily
