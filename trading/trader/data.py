"""Daily bar providers. Every provider returns {symbol: DataFrame[open, high, low, close, volume]}.

Stocks and ETFs come from Alpaca's SIP feed (the whole market's tape; free for bars older than 15 minutes)
with IEX as the automatic fallback. `validate` holds the EX-7 data checks.
"""
from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol

import numpy as np
import pandas as pd

Bars = dict[str, pd.DataFrame]
COLUMNS = ["open", "high", "low", "close", "volume"]
NY = "America/New_York"
SIP_DELAY = timedelta(minutes=16)  # the free plan only serves SIP bars older than 15 minutes


class DataProvider(Protocol):
    def daily_bars(self, symbols: list[str], days: int, start=None, end=None) -> Bars: ...


class AlpacaData:
    """Alpaca market data: SIP first, then the fallback feed if SIP fails.

    After each fetch, `feed_used` names the stock feed that answered and `notes` explains any fallback in
    plain English (the journal shows it). Clients can be injected for tests.
    """

    def __init__(self, key: str, secret: str, feed: str = "sip", fallback_feed: str | None = "iex", *,
                 stock_client: Any = None, crypto_client: Any = None,
                 now: Callable[[], datetime] | None = None):
        if stock_client is None or crypto_client is None:
            from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient

            stock_client = stock_client or StockHistoricalDataClient(key, secret)
            crypto_client = crypto_client or CryptoHistoricalDataClient(key, secret)
        self._stocks = stock_client
        self._crypto = crypto_client
        self.feed = _feed_name(feed) or "sip"
        self.fallback_feed = _feed_name(fallback_feed)
        self.feed_used: str | None = None
        self.notes: list[str] = []
        self._now = now or (lambda: datetime.now(timezone.utc))

    @classmethod
    def from_env(cls, cfg=None) -> "AlpacaData":
        """Keys from ALPACA_DATA_* (else the rules book's paper keys); feeds from `cfg.playbook["data"]`."""
        key, secret = _env_key_pair()
        data_cfg = (cfg.playbook.get("data") or {}) if cfg is not None else {}
        return cls(key, secret, feed=data_cfg.get("feed") or "sip",
                   fallback_feed=data_cfg.get("fallback_feed", "iex"))

    def daily_bars(self, symbols: list[str], days: int, start=None, end=None, adjustment: str = "all") -> Bars:
        """At least `days` sessions per symbol, ending at `end` (default now), when the feed has them.

        The calendar padding (1.5 x days + 10) covers weekends and holidays. `start` overrides the window start.
        `adjustment="raw"` returns traded prices (no split/dividend adjustment) for anything strike-related
        (Options rulebook phase O0, OPT-37); the default "all" keeps the stock books' adjusted bars.
        """
        if start is None:
            now = self._now()
            anchor = min(_as_utc(end, end_of_day=True), now) if end is not None else now
            start = anchor - timedelta(days=int(days * 1.5) + 10)
        return self._fetch(symbols, start, end, adjustment)

    def history(self, symbols: list[str], start, end=None, adjustment: str = "all") -> Bars:
        """Bars between two dates (inclusive) for the backtester and evals. Dates may be 'YYYY-MM-DD' strings."""
        return self._fetch(symbols, start, end, adjustment)

    # --- internals ---------------------------------------------------------------------------

    def _fetch(self, symbols: list[str], start, end, adjustment: str = "all") -> Bars:
        adjustment = _adjustment_name(adjustment)
        self.notes, self.feed_used = [], None
        start_utc = _as_utc(start, end_of_day=False)
        end_utc = _as_utc(end, end_of_day=True) if end is not None else None
        symbols = list(dict.fromkeys(symbols))
        stocks = [s for s in symbols if "/" not in s]
        crypto = [s for s in symbols if "/" in s]
        out: Bars = {}
        if stocks:
            out.update(self._stock_bars(stocks, start_utc, end_utc, adjustment))
        if crypto:
            out.update(self._crypto_bars(crypto, start_utc, end_utc))
        return out

    def _stock_bars(self, symbols: list[str], start: datetime, end: datetime | None,
                    adjustment: str = "all") -> Bars:
        """Try the main feed, then the fallback once, on any exception or an empty answer."""
        feeds = [self.feed]
        if self.fallback_feed and self.fallback_feed != self.feed:
            feeds.append(self.fallback_feed)
        error: Exception | None = None
        for i, feed in enumerate(feeds):
            try:
                bars = _split(self._stocks.get_stock_bars(self._stock_request(symbols, start, end, feed, adjustment)).df)
            except Exception as e:  # any failure: try the fallback feed
                error = e
                self.notes.append(f"The {feed.upper()} data request failed ({_short(e)}).")
                continue
            if not bars and i + 1 < len(feeds):
                self.notes.append(f"The {feed.upper()} feed returned no bars.")
                continue
            self.feed_used = feed
            if i > 0:
                self.notes.append(_fallback_note(feed))
            return bars
        tried = " and ".join(f.upper() for f in feeds)
        raise RuntimeError(f"No stock data from {tried}: {_short(error)}") from error

    def _stock_request(self, symbols: list[str], start: datetime, end: datetime | None, feed: str,
                       adjustment: str = "all"):
        from alpaca.data.enums import Adjustment, DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        if feed == "sip":
            latest = self._now() - SIP_DELAY
            end = latest if end is None or end > latest else end
        return StockBarsRequest(symbol_or_symbols=symbols, timeframe=TimeFrame.Day, start=start, end=end,
                                adjustment=Adjustment(_adjustment_name(adjustment)), feed=DataFeed(feed))

    def _crypto_bars(self, symbols: list[str], start: datetime, end: datetime | None) -> Bars:
        from alpaca.data.requests import CryptoBarsRequest
        from alpaca.data.timeframe import TimeFrame

        req = CryptoBarsRequest(symbol_or_symbols=symbols, timeframe=TimeFrame.Day, start=start, end=end)
        return _split(self._crypto.get_crypto_bars(req).df)


def _env_key_pair() -> tuple[str, str]:
    """Take key and secret from the same pair, so a data key is never mixed with a trading secret."""
    for prefix in ("ALPACA_DATA", "ALPACA_RULES"):
        key, secret = os.environ.get(f"{prefix}_KEY"), os.environ.get(f"{prefix}_SECRET")
        if key and secret:
            return key, secret
    raise RuntimeError("Set ALPACA_DATA_KEY and ALPACA_DATA_SECRET (a free Alpaca paper key works), "
                       "or ALPACA_RULES_KEY and ALPACA_RULES_SECRET.")


def _feed_name(x) -> str | None:
    """'SIP' -> 'sip'; None or blank -> None (a blank config value must not crash the fetch)."""
    text = str(x).strip().lower() if x is not None else ""
    return text or None


ADJUSTMENTS = ("all", "raw", "split", "dividend")


def _adjustment_name(x) -> str:
    """'RAW' -> 'raw'; None or blank -> 'all' (the old default). Unknown names raise instead of silently
    returning adjusted prices where raw ones were asked for (phase O0: strikes need traded prices)."""
    text = str(getattr(x, "value", x)).strip().lower() if x is not None else ""
    text = text or "all"
    if text not in ADJUSTMENTS:
        raise ValueError(f"unknown bar adjustment {x!r}; use one of {', '.join(ADJUSTMENTS)}")
    return text


def _fallback_note(feed: str) -> str:
    if feed == "iex":
        return ("Used the IEX feed instead. IEX sees only a small part of market volume, "
                "so volume-based signals are noisier today.")
    return f"Used the {feed.upper()} feed instead."


def _short(e: Exception | None, limit: int = 160) -> str:
    text = f"{type(e).__name__}: {e}" if e is not None else "no answer"
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _as_utc(x, *, end_of_day: bool) -> datetime:
    """Datetime in UTC. A bare date means New York time; as an end date it covers that whole day."""
    ts = pd.Timestamp(x)
    if ts.tzinfo is None:
        date_only = ts == ts.normalize()
        ts = ts.tz_localize(NY)
        if date_only and end_of_day:
            ts = ts + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return ts.tz_convert("UTC").to_pydatetime()


def _naive_index(index) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(index)
    if idx.tz is not None:
        idx = idx.tz_convert(NY).tz_localize(None)
    return idx.normalize()


def _split(df: pd.DataFrame) -> Bars:
    """Alpaca's (symbol, timestamp) frame -> one frame per symbol, indexed by New York dates, oldest first."""
    out: Bars = {}
    if df is None or df.empty:
        return out
    for symbol, frame in df.groupby(level="symbol"):
        frame = frame.droplevel("symbol")
        frame.index = _naive_index(frame.index)
        frame = frame.reindex(columns=COLUMNS).astype(float).sort_index()
        out[str(symbol)] = frame[~frame.index.duplicated(keep="last")]
    return out


# --- EX-7 data checks -------------------------------------------------------------------------


def validate(bars: Bars, required: list[str], as_of, max_stale_days: int | None = 5,
             max_daily_move: float | None = 0.25, crypto_ok_zero_volume: bool = False) -> list[str]:
    """EX-7: problems as "SYM: problem" lines. The runner refuses new entries (never exits) in these symbols.

    Checks: no data; last bar older than `max_stale_days`; a close <= 0 or infinite, or a missing last close;
    missing open/high/low on the last bar; zero volume on the last bar; a last-bar move above `max_daily_move`
    against the last valid earlier close. The rulebook's zero-volume check has no crypto exemption, so
    `crypto_ok_zero_volume` defaults to False (True skips the volume check for crypto pairs).
    """
    as_of = _naive_day(as_of)
    problems: list[str] = []
    for s in required:
        zero_volume_ok = crypto_ok_zero_volume and "/" in s
        problems += _symbol_problems(s, bars.get(s), as_of, max_stale_days, max_daily_move, zero_volume_ok)
    return problems


def problem_symbols(problems: list[str]) -> set[str]:
    """Symbols named in `validate` output."""
    return {p.split(":", 1)[0].strip() for p in problems}


def _symbol_problems(s: str, df: pd.DataFrame | None, as_of: pd.Timestamp, max_stale_days, max_daily_move,
                     zero_volume_ok: bool) -> list[str]:
    if df is None or len(df) == 0 or "close" not in df:
        return [f"{s}: no data"]
    df = df.copy()
    df.index = _naive_index(df.index)
    df = df.sort_index()
    last_day = df.index[-1]
    day = last_day.date()
    close = pd.to_numeric(df["close"], errors="coerce")
    out = []
    if max_stale_days is not None and (as_of - last_day).days > max_stale_days:
        out.append(f"{s}: stale, last bar {day}")
    if ((close <= 0) | np.isinf(close)).any() or not _positive(close.iloc[-1]):
        out.append(f"{s}: bad close values")
    if any(not _finite(df[c].iloc[-1]) if c in df else True for c in ("open", "high", "low")):
        out.append(f"{s}: missing open/high/low on the last bar {day}")
    if not zero_volume_ok and not _positive(df["volume"].iloc[-1] if "volume" in df else None):
        out.append(f"{s}: zero or missing volume on the last bar {day} (halted or bad data)")
    move = _last_move(close)
    if max_daily_move is not None and move is not None and abs(move) > max_daily_move:
        out.append(f"{s}: close moved {move:+.1%} on {day} (limit {max_daily_move:.0%}); bars are split and "
                   "dividend adjusted, so no known corporate action explains it")
    return out


def _last_move(close: pd.Series) -> float | None:
    """Change of the last close against the last valid earlier close (a NaN gap must not hide a jump)."""
    if len(close) < 2 or not _positive(close.iloc[-1]):
        return None
    earlier = close.iloc[:-1]
    earlier = earlier[np.isfinite(earlier) & (earlier > 0)]
    if earlier.empty:
        return None
    return float(close.iloc[-1] / earlier.iloc[-1] - 1)


def _naive_day(ts) -> pd.Timestamp:
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(NY).tz_localize(None)
    return ts.normalize()


def _finite(x) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _positive(x) -> bool:
    return _finite(x) and float(x) > 0
