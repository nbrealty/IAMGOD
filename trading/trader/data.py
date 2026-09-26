"""Daily bar providers. Every provider returns {symbol: DataFrame[open, high, low, close, volume]}."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Protocol

import pandas as pd

Bars = dict[str, pd.DataFrame]
COLUMNS = ["open", "high", "low", "close", "volume"]


class DataProvider(Protocol):
    def daily_bars(self, symbols: list[str], days: int) -> Bars: ...


class AlpacaData:
    """Alpaca market data. The free plan uses the IEX feed for stocks."""

    def __init__(self, key: str, secret: str, feed: str = "iex"):
        from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient

        self._stocks = StockHistoricalDataClient(key, secret)
        self._crypto = CryptoHistoricalDataClient(key, secret)
        self._feed = feed

    @classmethod
    def from_env(cls) -> "AlpacaData":
        key = os.environ.get("ALPACA_DATA_KEY") or os.environ.get("ALPACA_RULES_KEY")
        secret = os.environ.get("ALPACA_DATA_SECRET") or os.environ.get("ALPACA_RULES_SECRET")
        if not key or not secret:
            raise RuntimeError("Set ALPACA_DATA_KEY and ALPACA_DATA_SECRET (a free Alpaca paper key works).")
        return cls(key, secret)

    def daily_bars(self, symbols: list[str], days: int) -> Bars:
        from alpaca.data.enums import Adjustment, DataFeed
        from alpaca.data.requests import CryptoBarsRequest, StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        start = datetime.now(timezone.utc) - timedelta(days=int(days * 1.5) + 10)
        stocks = [s for s in symbols if "/" not in s]
        crypto = [s for s in symbols if "/" in s]
        out: Bars = {}
        if stocks:
            req = StockBarsRequest(
                symbol_or_symbols=stocks,
                timeframe=TimeFrame.Day,
                start=start,
                adjustment=Adjustment.ALL,
                feed=DataFeed(self._feed),
            )
            out.update(_split(self._stocks.get_stock_bars(req).df))
        if crypto:
            req = CryptoBarsRequest(symbol_or_symbols=crypto, timeframe=TimeFrame.Day, start=start)
            out.update(_split(self._crypto.get_crypto_bars(req).df))
        return out


def _split(df: pd.DataFrame) -> Bars:
    out: Bars = {}
    if df is None or df.empty:
        return out
    for symbol, frame in df.groupby(level="symbol"):
        frame = frame.droplevel("symbol")
        idx = pd.DatetimeIndex(frame.index)
        if idx.tz is not None:
            idx = idx.tz_convert("America/New_York").tz_localize(None)
        frame.index = idx.normalize()
        out[str(symbol)] = frame[COLUMNS].astype(float)
    return out


def validate(bars: Bars, required: list[str], as_of: pd.Timestamp, max_stale_days: int = 5) -> list[str]:
    """Return a list of problems. The runner refuses new entries in a symbol with a problem."""
    problems = []
    for s in required:
        df = bars.get(s)
        if df is None or df.empty:
            problems.append(f"{s}: no data")
            continue
        if (as_of - df.index[-1]).days > max_stale_days:
            problems.append(f"{s}: stale, last bar {df.index[-1].date()}")
        if (df["close"] <= 0).any() or df["close"].isna().iloc[-1]:
            problems.append(f"{s}: bad close values")
    return problems
