import pandas as pd

from conftest import make_bars
from trader import strategies as strat
from trader.models import Lot
from trader.regime import classify


def test_regime_bull_and_bear(cfg, bars):
    bars = dict(bars)
    bars["SPY"] = make_bars(drift=0.0008, vol=0.005, seed=11)
    r = classify(bars, "SPY", cfg.stock_universe(), ["VWO", "BND"])
    assert r.label in ("bull_calm", "bull_volatile")
    bars["SPY"] = make_bars(drift=-0.002, vol=0.005, seed=12)
    r = classify(bars, "SPY", cfg.stock_universe(), ["VWO", "BND"])
    assert r.label in ("bear", "panic")
    assert r.permissions["B"] == 0 and r.permissions["C"] == 0


def _pullback(df, days=3, pct=0.02):
    df = df.copy()
    for i in range(days, 0, -1):
        f = (1 - pct) ** (days - i + 1)
        df.iloc[-i, df.columns.get_loc("close")] = df["close"].iloc[-days - 1] * f
        df.iloc[-i, df.columns.get_loc("low")] = min(df["low"].iloc[-i], df["close"].iloc[-i])
    return df


def test_rsi2_entry_and_exit(cfg, bars):
    bars = dict(bars)
    bars["SPY"] = _pullback(make_bars(drift=0.001, vol=0.004, seed=21))
    plan = strat.sleeve_b(bars, cfg.sleeves["B"], 2000, {}, cfg.policy, 10000, 1.0)
    t = plan.targets.get("SPY")
    assert t is not None and t.qty > 0 and t.stop < bars["SPY"]["close"].iloc[-1]
    risk = (bars["SPY"]["close"].iloc[-1] - t.stop) * t.qty
    assert risk <= 0.005 * 10000 + 1e-6

    # Regime gate off: no entries.
    plan = strat.sleeve_b(bars, cfg.sleeves["B"], 2000, {}, cfg.policy, 10000, 0.0)
    assert "SPY" not in plan.targets

    # Held position closes above its 5-day SMA -> exit.
    up = make_bars(drift=0.001, vol=0.004, seed=21)
    bars["SPY"] = up
    lot = Lot(5, float(up["close"].iloc[-5]), str(up.index[-3].date()), 1.0, 1.0)
    plan = strat.sleeve_b(bars, cfg.sleeves["B"], 2000, {"SPY": lot}, cfg.policy, 10000, 1.0)
    if up["close"].iloc[-1] > up["close"].iloc[-5:].mean():
        assert plan.targets["SPY"].qty == 0


def test_faber_goes_to_cash_in_downtrend(cfg, bars):
    bars = dict(bars)
    for i, s in enumerate(cfg.sleeves["A"]["assets"]):
        bars[s] = make_bars(drift=-0.002, vol=0.005, seed=100 + i)
    plan = strat.sleeve_a(bars, cfg.sleeves["A"], 5000, {}, cfg.policy, bars["SPY"].index[-1])
    risky = sum(t.qty for s, t in plan.targets.items() if s != "BIL")
    assert risky == 0
    assert plan.targets["BIL"].qty > 0


def test_breakout_needs_trend_template(cfg, bars):
    bars = dict(bars)
    df = make_bars(drift=0.0015, vol=0.008, seed=31)
    df.iloc[-1, df.columns.get_loc("close")] = df["high"].iloc[-51:-1].max() * 1.03
    df.iloc[-1, df.columns.get_loc("high")] = df["close"].iloc[-1]
    df.iloc[-1, df.columns.get_loc("volume")] = df["volume"].iloc[-51:-1].mean() * 3
    bars["NVDA"] = df
    plan = strat.sleeve_c(bars, cfg.sleeves["C"], 1500, {}, cfg.policy, 10000, 1.0)
    t = plan.targets.get("NVDA")
    assert t is not None and t.qty > 0
    close = df["close"].iloc[-1]
    assert close * 0.92 - 1e-9 <= t.stop < close
