"""Market data for the live paper minute trader: live IEX polling, historical SIP replay, recordings, and the
pre-session context (MT-G22, MT-G27, MT-G35).

- `LiveMarket` polls Alpaca's free real-time feed (IEX) about once a second: the latest quote and the latest trade
  for both symbols (one request each) and, only when a new minute bar should be complete, the minute bars since the
  last one delivered. A bar is delivered ONCE, when it is complete (start + 60 s <= now), oldest first; bars missed
  while the process was busy or down are backfilled from the last delivered bar (or the session open); a bar is
  never updated after delivery (a later correction is ignored, like the backtest never sees one). A failed poll
  leaves `last_data_ok` where it was, so the entry gate sees DATA_STALE after 2 s (MT-G22). Once a minute it
  measures the clock offset against Alpaca's /v2/clock (best of 3 by round trip; `offset_from_samples`). Halt and
  LULD status are not on the free REST feed: `halted` is None (a note, never "not halted"), journalled once as
  HALT_STATUS_UNAVAILABLE. Every snapshot goes to the recorder (MT-G27).
- `ReplayMarket` steps a simulated clock through one historical session: for every minute of the session it ticks at
  the minute's end + 1 s (that minute's SIP bar is delivered, with the real historical SIP quote at that instant),
  + 3 s and + 6 s (order handling). Data are always fresh (last_data_ok = now) and the clock offset is 0.
- `SipQuoteSource` gives the historical SIP quote at an instant (StockQuotesRequest, latest quote at or before it),
  cached on disk in state/scalp/quote_cache so a day is fetched once. SIP data younger than 16 minutes are refused by
  the free plan, so later instants give None (NO_QUOTE) and are not cached.
- `Recorder` writes each snapshot as one JSON line; `RecordingMarket` plays such a file back (the MT-G27 replay of a
  recorded session).
- `build_context` loads the SIP history before a session through `lab.scalp.data.download` (read-only data calls,
  cached in state/scalp_cache) and computes the pre-session `Ctx` with `lab.scalp.backtest.to_days/contexts`, so live
  decides with exactly the backtest's context. The caller passes explicit clients built from the ALPACA_SCALP_* keys
  (data.download never falls back to other keys when clients are given).
Nothing here places, cancels or reads orders.
"""
from __future__ import annotations

import gzip
import json
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

import numpy as np
import pandas as pd

from .. import backtest as bt
from .. import data as dt
from ..signals import Ctx, Day
from . import config as C
from .model import NY, Bar, Feed, LastTrade, MarketSnapshot, Quote, as_ny

MINUTE = pd.Timedelta(minutes=1)
OFFSET_EVERY_S = 60           # clock-offset check once a minute (MT-G22)
OFFSET_TRIES = 3
BAR_RETRY_FAST_S = 10         # keep asking every poll for this long after a bar is due, then every BAR_RETRY_SLOW_S
BAR_RETRY_SLOW_S = 5
REPLAY_TICKS_S = (61, 63, 66)  # after each minute's START: its end + 1 s (bar delivered), + 3 s, + 6 s
QUOTE_LOOKBACK_S = 10          # the historical quote is the latest one in [t - 10 s, t]
QUOTE_CACHE_DIR = C.STATE_DIR / "quote_cache"


class SimClock:
    """A settable clock for replay and tests: `clock()` gives the current New York time."""

    def __init__(self, t: Any):
        self.t = as_ny(t)

    def __call__(self) -> pd.Timestamp:
        return self.t

    def set(self, t: Any) -> None:
        t = as_ny(t)
        if t < self.t:
            raise ValueError(f"simulated time cannot go back ({t} < {self.t})")
        self.t = t

    def advance(self, seconds: float) -> pd.Timestamp:
        self.set(self.t + pd.Timedelta(seconds=seconds))
        return self.t


def _ts(x: Any) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_localize("UTC").tz_convert(NY) if t.tzinfo is None else t.tz_convert(NY)


# ------------------------------------------------------------------------------------------ recordings (MT-G27)
def _q(q: Quote) -> dict:
    return {"symbol": q.symbol, "bid": q.bid, "ask": q.ask, "bid_size": q.bid_size, "ask_size": q.ask_size,
            "ts": q.ts.isoformat(), "recv": q.recv.isoformat(), "feed": q.feed.value}


def _t(t: LastTrade) -> dict:
    return {"symbol": t.symbol, "price": t.price, "size": t.size, "ts": t.ts.isoformat(), "feed": t.feed.value}


def _b(b: Bar) -> dict:
    return {"symbol": b.symbol, "start": b.start.isoformat(), "open": b.open, "high": b.high, "low": b.low,
            "close": b.close, "volume": b.volume, "feed": b.feed.value,
            "recv": None if b.recv is None else b.recv.isoformat()}


def snapshot_to_dict(s: MarketSnapshot) -> dict:
    return {"now": s.now.isoformat(), "quotes": {k: _q(v) for k, v in s.quotes.items()},
            "trades": {k: _t(v) for k, v in s.trades.items()},
            "new_bars": {k: [_b(b) for b in v] for k, v in s.new_bars.items()},
            "last_data_ok": None if s.last_data_ok is None else s.last_data_ok.isoformat(),
            "clock_offset_ms": s.clock_offset_ms, "halted": dict(s.halted)}


def snapshot_from_dict(d: dict) -> MarketSnapshot:
    def q(x: dict) -> Quote:
        return Quote(x["symbol"], float(x["bid"]), float(x["ask"]), float(x["bid_size"]), float(x["ask_size"]),
                     _ts(x["ts"]), _ts(x["recv"]), Feed(x["feed"]))

    def t(x: dict) -> LastTrade:
        return LastTrade(x["symbol"], float(x["price"]), float(x["size"]), _ts(x["ts"]), Feed(x["feed"]))

    def b(x: dict) -> Bar:
        return Bar(x["symbol"], _ts(x["start"]), float(x["open"]), float(x["high"]), float(x["low"]),
                   float(x["close"]), float(x["volume"]), Feed(x["feed"]),
                   None if x.get("recv") is None else _ts(x["recv"]))

    return MarketSnapshot(now=_ts(d["now"]), quotes={k: q(v) for k, v in d["quotes"].items()},
                          trades={k: t(v) for k, v in d["trades"].items()},
                          new_bars={k: [b(x) for x in v] for k, v in d["new_bars"].items()},
                          last_data_ok=None if d.get("last_data_ok") is None else _ts(d["last_data_ok"]),
                          clock_offset_ms=d.get("clock_offset_ms"), halted=dict(d.get("halted") or {}))


def recording_path(state_dir: str | Path, session_date: date, mode: str) -> Path:
    """state/scalp/recordings/YYYY-MM-DD-<mode>.jsonl"""
    return Path(state_dir) / "recordings" / f"{session_date.isoformat()}-{mode}.jsonl"


class Recorder:
    """Appends every market snapshot the runner hands the engine (one JSON line each, flushed)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(self.path, "a", encoding="utf-8")
        self.count = 0

    def snapshot(self, snap: MarketSnapshot) -> None:
        self._f.write(json.dumps({"kind": "snapshot", **snapshot_to_dict(snap)}, separators=(",", ":")) + "\n")
        self._f.flush()
        self.count += 1

    def close(self) -> None:
        if not self._f.closed:
            self._f.close()


def read_recording(path: str | Path) -> Iterator[MarketSnapshot]:
    p = Path(path)
    opener = gzip.open if p.suffix == ".gz" else open
    with opener(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                if d.get("kind", "snapshot") == "snapshot":
                    yield snapshot_from_dict(d)


class RecordingMarket:
    """Plays a recorded session back, snapshot by snapshot, moving `clock` to each recorded time."""
    feed = None   # whatever was recorded (each price carries its own feed tag)

    def __init__(self, path: str | Path, clock: SimClock | None = None):
        self.snaps = list(read_recording(path))
        if not self.snaps:
            raise ValueError(f"{path}: empty recording")
        self.clock = clock or SimClock(self.snaps[0].now)
        self._i = 0

    @property
    def done(self) -> bool:
        return self._i >= len(self.snaps)

    def poll(self) -> MarketSnapshot | None:
        if self.done:
            return None
        s = self.snaps[self._i]
        self._i += 1
        self.clock.set(s.now)
        return s


# ------------------------------------------------------------------------------------------ clock offset
def offset_from_samples(samples: Iterable[tuple[float, float, float]]) -> float | None:
    """MT-G22 clock check from (local_send, server_time, local_receive) samples in epoch seconds: take the sample
    with the shortest round trip; offset_ms = |server - local midpoint| + half the round trip (the uncertainty).
    None when there is no usable sample (the entry gate then says CLOCK_UNVERIFIED)."""
    best = None
    for t0, server, t1 in samples:
        if server is None or not (np.isfinite(t0) and np.isfinite(t1) and np.isfinite(server)) or t1 < t0:
            continue
        rtt = t1 - t0
        if best is None or rtt < best[0]:
            best = (rtt, server, (t0 + t1) / 2.0)
    if best is None:
        return None
    rtt, server, mid = best
    return abs(server - mid) * 1000.0 + rtt * 1000.0 / 2.0


def measure_offset(trading_client: Any, wall: Callable[[], float] = time.time, tries: int = OFFSET_TRIES
                   ) -> float | None:
    """Ask Alpaca's /v2/clock `tries` times (read-only) and return the offset in ms, or None if every call fails."""
    samples = []
    for _ in range(tries):
        try:
            t0 = wall()
            c = trading_client.get_clock()
            t1 = wall()
            samples.append((t0, pd.Timestamp(c.timestamp).timestamp(), t1))
        except Exception:  # noqa: BLE001 - a failed check means "unverified", never "fine"
            continue
    return offset_from_samples(samples)


# ------------------------------------------------------------------------------------------ live (IEX)
def _iex() -> Any:
    from alpaca.data.enums import DataFeed
    return DataFeed.IEX


def _bars_frame(resp: Any) -> pd.DataFrame:
    df = getattr(resp, "df", None)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.reset_index()
    if "symbol" not in df:
        return pd.DataFrame()
    df["start"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(NY)
    return df


class LiveMarket:
    """Real-time IEX polling (see the module docstring). `clock()` returns the local New York time; `wall()` the
    local epoch seconds used for the offset check. `session_open`/`session_close` bound which bars are delivered
    (default 09:30-16:00 of the clock's date)."""
    feed = Feed.IEX

    def __init__(self, data_client: Any, symbols: Iterable[str], clock: Callable[[], pd.Timestamp], *,
                 trading_client: Any = None, recorder: Recorder | None = None, journal: Any = None,
                 session_open: pd.Timestamp | None = None, session_close: pd.Timestamp | None = None,
                 wall: Callable[[], float] = time.time, offset_every_s: float = OFFSET_EVERY_S):
        self.data, self.trading, self.clock, self.wall = data_client, trading_client, clock, wall
        self.symbols = [s.upper() for s in symbols]
        self.recorder, self.journal = recorder, journal
        today = as_ny(clock()).normalize()
        self.session_open = as_ny(session_open) if session_open is not None else today + pd.Timedelta(hours=9.5)
        self.session_close = as_ny(session_close) if session_close is not None else today + pd.Timedelta(hours=16)
        self.offset_every = pd.Timedelta(seconds=offset_every_s)
        self.quotes: dict[str, Quote] = {}
        self.trades: dict[str, LastTrade] = {}
        self.last_bar: dict[str, pd.Timestamp | None] = {s: None for s in self.symbols}   # start of last delivered
        self.last_data_ok: pd.Timestamp | None = None
        self.clock_offset_ms: float | None = None
        self._offset_at: pd.Timestamp | None = None
        self._bar_due_since: pd.Timestamp | None = None
        self._bar_tried: pd.Timestamp | None = None
        self._noted_halt = False
        self.errors: list[str] = []

    # -- helpers
    def _note(self, kind: str, **f: Any) -> None:
        if self.journal is not None:
            self.journal.write(kind, **f)

    def _next_start(self, sym: str) -> pd.Timestamp:
        last = self.last_bar[sym]
        return self.session_open if last is None else last + MINUTE

    def _bars_due(self, now: pd.Timestamp) -> bool:
        """Is a complete bar we have not delivered expected, and is it time to (re)ask?"""
        due = [self._next_start(s) for s in self.symbols
               if self._next_start(s) + MINUTE <= min(now, self.session_close)]
        if not due:
            self._bar_due_since = None
            return False
        if self._bar_due_since is None:
            self._bar_due_since = now
        waited = now - self._bar_due_since
        if self._bar_tried is not None and waited > pd.Timedelta(seconds=BAR_RETRY_FAST_S):
            return now - self._bar_tried >= pd.Timedelta(seconds=BAR_RETRY_SLOW_S)
        return True

    def _poll_quotes(self, now: pd.Timestamp) -> bool:
        from alpaca.data.requests import StockLatestQuoteRequest
        try:
            resp = self.data.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=self.symbols,
                                                                            feed=_iex()))
        except Exception as e:  # noqa: BLE001 - a failed poll is recorded and leaves the data stale
            self.errors.append(f"quote: {type(e).__name__}")
            return False
        for s in self.symbols:
            q = (resp or {}).get(s)
            if q is not None:
                self.quotes[s] = Quote(s, float(q.bid_price or 0.0), float(q.ask_price or 0.0),
                                       float(q.bid_size or 0.0), float(q.ask_size or 0.0), _ts(q.timestamp), now,
                                       Feed.IEX)
        return True

    def _poll_trades(self, now: pd.Timestamp) -> bool:
        from alpaca.data.requests import StockLatestTradeRequest
        try:
            resp = self.data.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=self.symbols,
                                                                            feed=_iex()))
        except Exception as e:  # noqa: BLE001
            self.errors.append(f"trade: {type(e).__name__}")
            return False
        for s in self.symbols:
            t = (resp or {}).get(s)
            if t is not None:
                self.trades[s] = LastTrade(s, float(t.price), float(t.size or 0.0), _ts(t.timestamp), Feed.IEX)
        return True

    def _poll_bars(self, now: pd.Timestamp) -> tuple[dict[str, list[Bar]], bool]:
        """(new complete bars per symbol, request ok). Only bars after the last delivered one, complete, and
        inside the session are kept; each is delivered once."""
        if not self._bars_due(now):
            return {}, True
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        start = min(self._next_start(s) for s in self.symbols)
        self._bar_tried = now
        try:
            resp = self.data.get_stock_bars(StockBarsRequest(
                symbol_or_symbols=self.symbols, timeframe=TimeFrame.Minute,
                start=start.tz_convert("UTC").to_pydatetime(), feed=_iex()))
        except Exception as e:  # noqa: BLE001
            self.errors.append(f"bars: {type(e).__name__}")
            return {}, False
        df = _bars_frame(resp)
        out: dict[str, list[Bar]] = {}
        for s in self.symbols:
            if df.empty:
                break
            g = df[df["symbol"] == s].sort_values("start")
            nxt = self._next_start(s)
            bars = []
            for r in g.itertuples(index=False):
                st = r.start
                if st < nxt or st < self.session_open or st >= self.session_close or st + MINUTE > now:
                    continue    # delivered already, outside the session, or still in progress
                bars.append(Bar(s, st, float(r.open), float(r.high), float(r.low), float(r.close),
                                float(r.volume), Feed.IEX, now))
                nxt = st + MINUTE
            if bars:
                out[s] = bars
                self.last_bar[s] = bars[-1].start
        if out:
            self._bar_due_since = None
            self._bar_tried = None
        return out, True

    def _check_offset(self, now: pd.Timestamp) -> None:
        if self._offset_at is not None and now - self._offset_at < self.offset_every:
            return
        self._offset_at = now
        self.clock_offset_ms = measure_offset(self.trading, self.wall) if self.trading is not None else None

    # -- the poll
    def poll(self) -> MarketSnapshot:
        t0 = as_ny(self.clock())
        ok_q = self._poll_quotes(t0)
        ok_t = self._poll_trades(t0)
        now = as_ny(self.clock())
        new_bars, ok_b = self._poll_bars(now)
        if ok_q and ok_t and ok_b:
            self.last_data_ok = now
        self._check_offset(now)
        if not self._noted_halt:
            self._noted_halt = True
            self._note("HALT_STATUS_UNAVAILABLE", feed=Feed.IEX,
                       note="halt and LULD status are not on the free IEX REST feed; treated as unknown, not as "
                            "'not halted' (MT-G22)")
        snap = MarketSnapshot(now=now, quotes=dict(self.quotes), trades=dict(self.trades), new_bars=new_bars,
                              last_data_ok=self.last_data_ok, clock_offset_ms=self.clock_offset_ms,
                              halted={s: None for s in self.symbols})
        if self.recorder is not None:
            self.recorder.snapshot(snap)
        return snap


# ------------------------------------------------------------------------------------------ historical SIP quotes
def _sip() -> Any:
    from alpaca.data.enums import DataFeed
    return DataFeed.SIP


class SipQuoteSource:
    """quote_fn(symbol, ts) -> the latest SIP quote at or before ts (None if none in the 10 s before it). Cached
    per symbol and day in `cache_dir` as {iso ts: [bid, ask, bid_size, ask_size, quote_ts] | null}."""

    def __init__(self, data_client: Any, cache_dir: str | Path = QUOTE_CACHE_DIR,
                 now_fn: Callable[[], pd.Timestamp] = lambda: pd.Timestamp.now(tz="UTC")):
        self.data, self.dir, self.now_fn = data_client, Path(cache_dir), now_fn
        self._mem: dict[tuple[str, date], dict[str, Any]] = {}
        self._dirty: set[tuple[str, date]] = set()
        self.requests = 0

    def _path(self, sym: str, d: date) -> Path:
        return self.dir / f"{sym}_{d.isoformat()}.json"

    def _day(self, sym: str, d: date) -> dict[str, Any]:
        key = (sym, d)
        if key not in self._mem:
            p = self._path(sym, d)
            self._mem[key] = json.loads(p.read_text()) if p.exists() else {}
        return self._mem[key]

    def flush(self) -> None:
        for sym, d in sorted(self._dirty):
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self._path(sym, d).with_suffix(".tmp")
            tmp.write_text(json.dumps(self._mem[(sym, d)], separators=(",", ":")))
            tmp.replace(self._path(sym, d))
        self._dirty.clear()

    def __call__(self, symbol: str, ts: pd.Timestamp) -> Quote | None:
        sym, ts = symbol.upper(), as_ny(ts)
        if ts > as_ny(self.now_fn()) - dt.DELAY:
            return None                    # the free plan refuses SIP data younger than 16 minutes
        day = self._day(sym, ts.date())
        k = ts.isoformat()
        if k not in day:
            from alpaca.common.enums import Sort
            from alpaca.data.requests import StockQuotesRequest
            req = StockQuotesRequest(symbol_or_symbols=sym, start=(ts - pd.Timedelta(seconds=QUOTE_LOOKBACK_S))
                                     .tz_convert("UTC").to_pydatetime(), end=ts.tz_convert("UTC").to_pydatetime(),
                                     limit=1, sort=Sort.DESC, feed=_sip())
            self.requests += 1
            try:
                resp = dt.with_retry(lambda: self.data.get_stock_quotes(req))
            except Exception:  # noqa: BLE001 - no quote = NO_QUOTE for that tick; not cached, so a re-run retries
                return None
            data = getattr(resp, "data", resp) or {}
            rows = list(data.get(sym, []) if hasattr(data, "get") else [])
            q = rows[0] if rows else None
            day[k] = None if q is None else [float(q.bid_price or 0), float(q.ask_price or 0), float(q.bid_size or 0),
                                             float(q.ask_size or 0), _ts(q.timestamp).isoformat()]
            self._dirty.add((sym, ts.date()))
            if len(self._dirty) and self.requests % 50 == 0:
                self.flush()
        v = day[k]
        if v is None:
            return None
        return Quote(sym, v[0], v[1], v[2], v[3], _ts(v[4]), ts, Feed.SIP)


class SipTradeSource:
    """trades_fn(symbol, start, end) -> the prices of every historical SIP trade in [start, end), for the MT-G4
    re-mark of resting take-profits (a resting limit counts as filled only if a SIP trade printed strictly through
    it). None when the data cannot be had: younger than the free plan's 16 minutes, or a failed request (the
    take-profit then stays PENDING_VERIFY; nothing is guessed). Read-only data calls."""

    def __init__(self, data_client: Any, now_fn: Callable[[], pd.Timestamp] = lambda: pd.Timestamp.now(tz="UTC")):
        self.data, self.now_fn = data_client, now_fn
        self.requests = 0

    def __call__(self, symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> list[float] | None:
        sym, start, end = symbol.upper(), as_ny(start), as_ny(end)
        if end > as_ny(self.now_fn()) - dt.DELAY:
            return None
        try:
            from alpaca.data.requests import StockTradesRequest
            req = StockTradesRequest(symbol_or_symbols=sym, start=start.tz_convert("UTC").to_pydatetime(),
                                     end=end.tz_convert("UTC").to_pydatetime(), feed=_sip())
            self.requests += 1
            resp = dt.with_retry(lambda: self.data.get_stock_trades(req))
        except Exception:  # noqa: BLE001 - no data: the take-profit stays PENDING_VERIFY
            return None
        data = getattr(resp, "data", resp) or {}
        rows = list(data.get(sym, []) if hasattr(data, "get") else [])
        return [float(t.price) for t in rows if getattr(t, "price", None) is not None]


# ------------------------------------------------------------------------------------------ replay (SIP)
def frame_to_bars(df: pd.DataFrame, symbol: str, feed: Feed = Feed.SIP) -> list[Bar]:
    """Cached bars (indexed by New York bar start) -> Bar objects."""
    if df is None or df.empty:
        return []
    idx = pd.DatetimeIndex(df.index)
    idx = idx.tz_localize(NY) if idx.tz is None else idx.tz_convert(NY)
    return [Bar(symbol, t, float(o), float(h), float(lo), float(c), float(v), feed)
            for t, o, h, lo, c, v in zip(idx, df["open"], df["high"], df["low"], df["close"], df["volume"])]


class ReplayMarket:
    """One historical session on a simulated clock (see the module docstring). `bars` maps symbol -> the day's
    SIP 1-minute bars (DataFrame indexed by bar start, or a list of Bar); `quote_fn(symbol, ts) -> Quote | None`."""
    feed = Feed.SIP

    def __init__(self, session_date: date, bars: dict[str, Any], quote_fn: Callable[[str, pd.Timestamp], Quote | None],
                 clock: SimClock | None = None, *, open_ts: pd.Timestamp | None = None,
                 close_ts: pd.Timestamp | None = None, recorder: Recorder | None = None):
        self.date = session_date
        self.open = as_ny(open_ts) if open_ts is not None else as_ny(pd.Timestamp(f"{session_date} 09:30"))
        self.close = as_ny(close_ts) if close_ts is not None else as_ny(pd.Timestamp(f"{session_date} 16:00"))
        self.bars: dict[str, dict[pd.Timestamp, Bar]] = {}
        for sym, b in bars.items():
            lst = b if isinstance(b, list) else frame_to_bars(b, sym.upper())
            self.bars[sym.upper()] = {as_ny(x.start): x for x in lst if x.start.date() == session_date}
        self.symbols = sorted(self.bars)
        self.quote_fn, self.recorder = quote_fn, recorder
        self.clock = clock or SimClock(self.open)
        self.last_close: dict[str, Bar] = {}
        self._ticks = self.ticks()
        self._i = 0

    def ticks(self) -> list[tuple[pd.Timestamp, pd.Timestamp | None]]:
        """[(tick time, minute whose bar is delivered at this tick or None)] for the whole session."""
        out = []
        t = self.open
        while t < self.close:
            for k, s in enumerate(REPLAY_TICKS_S):
                out.append((t + pd.Timedelta(seconds=s), t if k == 0 else None))
            t += MINUTE
        return out

    @property
    def done(self) -> bool:
        return self._i >= len(self._ticks)

    def poll(self) -> MarketSnapshot | None:
        if self.done:
            return None
        now, minute = self._ticks[self._i]
        self._i += 1
        self.clock.set(now)
        new_bars: dict[str, list[Bar]] = {}
        if minute is not None:
            for s in self.symbols:
                b = self.bars[s].get(minute)
                if b is not None:
                    b = Bar(b.symbol, b.start, b.open, b.high, b.low, b.close, b.volume, b.feed, now)
                    new_bars[s] = [b]
                    self.last_close[s] = b
        quotes = {}
        for s in self.symbols:
            q = self.quote_fn(s, now)
            if q is not None:
                quotes[s] = q
        # the last trade is the latest delivered bar's close (SIP), stamped at that bar's last second
        trades = {s: LastTrade(s, b.close, 0.0, b.start + pd.Timedelta(seconds=59), b.feed)
                  for s, b in self.last_close.items()}
        snap = MarketSnapshot(now=now, quotes=quotes, trades=trades, new_bars=new_bars, last_data_ok=now,
                              clock_offset_ms=0.0, halted={s: None for s in self.symbols})
        if self.recorder is not None:
            self.recorder.snapshot(snap)
        return snap


def bar_quote_fn(bars: dict[str, Any], half_spread: float = 0.005) -> Callable[[str, pd.Timestamp], Quote | None]:
    """A SIM quote for tests and offline replays without SIP quotes: the close of the latest bar that has ended,
    +/- half a cent. Tagged Feed.SIM so no report mistakes it for a real quote."""
    idx: dict[str, list[Bar]] = {}
    for sym, b in bars.items():
        idx[sym.upper()] = sorted(b if isinstance(b, list) else frame_to_bars(b, sym.upper()), key=lambda x: x.start)

    def fn(symbol: str, ts: pd.Timestamp) -> Quote | None:
        ts = as_ny(ts)
        done = [b for b in idx.get(symbol.upper(), []) if b.start + MINUTE <= ts]
        if not done:
            return None
        c = done[-1].close
        return Quote(symbol.upper(), round(c - half_spread, 4), round(c + half_spread, 4), 100.0, 100.0,
                     ts - pd.Timedelta(milliseconds=200), ts, Feed.SIM)

    return fn


# ------------------------------------------------------------------------------------------ pre-session context
@dataclass(frozen=True)
class CalendarRow:
    date: date
    open: pd.Timestamp
    close: pd.Timestamp


def _placeholder(d: date, open_ts: pd.Timestamp, close_ts: pd.Timestamp) -> Day:
    """A one-bar stand-in for today, appended so backtest.contexts computes today's Ctx from earlier days only
    (contexts never reads a day's own bars for that day's Ctx)."""
    one = np.array([1.0])
    return Day(d, open_ts, int((close_ts - open_ts).total_seconds() // 60), np.array([0]), one, one, one, one, one)


def build_context(symbol: str, session_date: date, cache_dir: str | Path, data_client: Any, trading_client: Any,
                  *, now: pd.Timestamp | None = None, log: Callable[[str], None] = print
                  ) -> tuple[Ctx, CalendarRow, list[Day]]:
    """(today's Ctx, today's calendar row, prior Day objects) for `symbol`, computed exactly as the backtest does.
    Raises ValueError if `session_date` is not a trading day. Uses only the clients given (ALPACA_SCALP_* keys)."""
    if data_client is None or trading_client is None:
        raise ValueError("build_context needs explicit data and trading clients (ALPACA_SCALP_* keys)")
    cache_dir = Path(cache_dir)
    cal0 = dt.fetch_calendar(trading_client, session_date - timedelta(days=dt.WARMUP_DAYS + 31), session_date)
    cal = dt.save_calendar(cal0, cache_dir)
    cal = cal[cal["date"] <= session_date].reset_index(drop=True)
    today = cal[cal["date"] == session_date]
    if today.empty:
        raise ValueError(f"{session_date} is not a trading day")
    row = CalendarRow(session_date, as_ny(today["open"].iloc[0]), as_ny(today["close"].iloc[0]))
    prior = [d for d in cal["date"] if d < session_date]
    if not prior:
        raise ValueError(f"no trading day before {session_date} in the calendar")
    prev = max(prior)
    dt.download([symbol], session_date, prev, cache_dir, client=data_client, trading_client=trading_client,
                now=now, log=log)
    s0 = session_date - timedelta(days=dt.WARMUP_DAYS)
    bars = dt.load_bars(symbol.upper(), s0, prev, cache_dir)
    closes = dt.load_official_closes(symbol.upper(), s0, prev, cache_dir)
    days = bt.to_days(bars, cal, closes)
    ctx = bt.contexts(days + [_placeholder(session_date, row.open, row.close)], cal)[-1]
    return ctx, row, days
