import numpy as np
import pandas as pd

from trader import indicators as ind


def test_rsi_extremes():
    up = pd.Series(np.arange(1, 30, dtype=float))
    down = up[::-1].reset_index(drop=True)
    assert ind.rsi(up, 2).iloc[-1] == 100.0
    assert ind.rsi(down, 2).iloc[-1] < 1.0


def test_rsi2_after_pullback_is_low():
    s = pd.Series(list(np.linspace(100, 120, 40)) + [118, 116, 114], dtype=float)
    assert ind.rsi(s, 2).iloc[-1] < 10


def test_atr_constant_range():
    idx = pd.date_range("2026-01-01", periods=60, freq="B")
    df = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0}, index=idx)
    assert abs(ind.atr(df, 20).iloc[-1] - 2.0) < 1e-9


def test_completed_months_drop_partial_month():
    idx = pd.date_range("2026-01-01", "2026-03-10", freq="B")
    s = pd.Series(range(len(idx)), index=idx, dtype=float)
    m = ind.completed_month_closes(s)
    assert list(m.index.month) == [1, 2]
    # On the last business day of March the month counts as complete.
    idx2 = pd.date_range("2026-01-01", "2026-03-31", freq="B")
    s2 = pd.Series(range(len(idx2)), index=idx2, dtype=float)
    assert list(ind.completed_month_closes(s2).index.month) == [1, 2, 3]


def test_momentum_13612w_sign():
    idx = pd.date_range("2025-01-31", periods=14, freq="ME")
    rising = pd.Series(np.linspace(100, 130, 14), index=idx)
    assert ind.momentum_13612w(rising) > 0
    assert ind.momentum_13612w(rising[::-1].set_axis(idx)) < 0
