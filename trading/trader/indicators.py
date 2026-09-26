"""Plain pandas indicators. Every function takes and returns pandas objects."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 2) -> pd.Series:
    """Wilder's RSI (Connors uses n=2)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss
    out = 100.0 - 100.0 / (1.0 + rs)
    # No losses in the window means RSI 100; no movement at all means 50.
    out = out.where(avg_loss != 0, 100.0)
    out = out.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)
    return out


def atr(bars: pd.DataFrame, n: int = 20) -> pd.Series:
    """Wilder's average true range from open/high/low/close bars."""
    prev_close = bars["close"].shift(1)
    tr = pd.concat(
        [
            bars["high"] - bars["low"],
            (bars["high"] - prev_close).abs(),
            (bars["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def realized_vol(close: pd.Series, n: int, periods_per_year: int = 252) -> pd.Series:
    """Annualized standard deviation of daily log returns."""
    rets = np.log(close).diff()
    return rets.rolling(n, min_periods=n).std() * np.sqrt(periods_per_year)


def completed_month_closes(close: pd.Series, as_of: pd.Timestamp | None = None) -> pd.Series:
    """Month-end closes for months that have finished as of `as_of`.

    The current month counts as finished only when `as_of` is its last business
    day (exchange holidays are ignored, so a holiday month-end closes a day late).
    """
    close = close.dropna()
    if close.empty:
        return close
    as_of = pd.Timestamp(as_of) if as_of is not None else close.index[-1]
    close = close[close.index <= as_of]
    monthly = close.groupby(close.index.to_period("M")).last()
    current = as_of.to_period("M")
    month_end = (as_of + pd.offsets.BMonthEnd(0)).normalize()
    if as_of.normalize() < month_end and len(monthly) and monthly.index[-1] == current:
        monthly = monthly.iloc[:-1]
    monthly.index = monthly.index.to_timestamp(how="end").normalize()
    return monthly


def momentum_13612w(monthly_close: pd.Series) -> float:
    """Keller's fast momentum score: 12*r1 + 4*r3 + 2*r6 + r12 (needs 13 month-ends)."""
    m = monthly_close.dropna()
    if len(m) < 13:
        return float("nan")
    p = m.iloc[-1]

    def r(k: int) -> float:
        return p / m.iloc[-1 - k] - 1.0

    return 12 * r(1) + 4 * r(3) + 2 * r(6) + r(12)


def total_return(close: pd.Series, days: int) -> float:
    c = close.dropna()
    if len(c) <= days:
        return float("nan")
    return float(c.iloc[-1] / c.iloc[-1 - days] - 1.0)
