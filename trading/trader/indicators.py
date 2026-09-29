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


def percentile_rank(series: pd.Series, lookback: int, min_periods: int = 1) -> float:
    """Percentile rank (0 to 1) of the last value among the series' last `lookback` values (REG-4).

    Same convention as pandas `rank(pct=True)`: ties share their average rank, so a new high scores
    1.0 and a flat series scores about 0.5. NaN and infinite values in the window are ignored, but a
    missing last value, or fewer than `min_periods` usable values, gives NaN.
    """
    if lookback < 1:
        return float("nan")
    window = pd.Series(series).iloc[-lookback:].to_numpy(dtype=float, na_value=np.nan)
    if len(window) == 0 or not np.isfinite(window[-1]):
        return float("nan")
    values = window[np.isfinite(window)]
    if len(values) < max(min_periods, 1):
        return float("nan")
    today = window[-1]
    less = np.count_nonzero(values < today)
    equal = np.count_nonzero(values == today)
    return float((less + (equal + 1) / 2) / len(values))


def share_above_sma(closes: pd.DataFrame, n: int, min_valid: float = 0.5) -> pd.Series:
    """Per date, the share of columns whose close is above their own n-day SMA (REG-4 breadth).

    A column counts only on dates where both its close and its SMA exist. Dates where fewer than
    `min_valid` of the columns count give NaN, so a handful of early listings cannot swing the share.
    """
    if closes.shape[1] == 0:
        return pd.Series(np.nan, index=closes.index, dtype=float)
    avg = closes.rolling(n, min_periods=n).mean()
    valid = closes.notna() & avg.notna()
    above = (closes > avg) & valid
    n_valid = valid.sum(axis=1)
    share = above.sum(axis=1) / n_valid.where(n_valid > 0)
    return share.where(n_valid >= max(1.0, min_valid * closes.shape[1])).astype(float)


def return_correlation(a: pd.Series, b: pd.Series, n: int) -> float:
    """Correlation of the daily returns of two close series over their last `n` common sessions (REG-7).

    NaN when there are fewer than `n` return pairs or either series is flat. A zero or negative close
    is bad data, so that date is dropped rather than read as a -100% day.
    """
    both = pd.concat([_unique_index(a), _unique_index(b)], axis=1, join="inner")
    both = both.where(both > 0).dropna()
    rets = both.pct_change().replace([np.inf, -np.inf], np.nan).dropna().iloc[-n:]
    if n < 2 or len(rets) < n:
        return float("nan")
    x, y = rets.iloc[:, 0], rets.iloc[:, 1]
    if x.std() < 1e-12 or y.std() < 1e-12:
        return float("nan")
    return float(x.corr(y))


def _unique_index(series: pd.Series) -> pd.Series:
    """Drop repeated dates (keep the last bar) so series can be aligned side by side."""
    return series[~series.index.duplicated(keep="last")]
