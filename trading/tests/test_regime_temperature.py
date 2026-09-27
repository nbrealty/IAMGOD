"""REG-1..REG-8: regime label unchanged, temperature, stock-bond monitor, credit and DAA canaries."""
import json
import time
from functools import lru_cache

import numpy as np
import pandas as pd
import pytest

from conftest import make_bars
from trader import indicators as ind
from trader.regime import (FILL_GAP_SESSIONS, PERMISSIONS, TEMPERATURE_COMPONENTS, Regime, _temperature_label,
                           classify, classify_kwargs, stock_bond)

END = "2026-09-25"
UNIV = [f"S{i}" for i in range(40)]
RISING = [(1500, 0.0, 0.012), (300, 0.003, 0.004)]   # flat and noisy, then a calm rally
FALLING = [(1500, 0.0, 0.008), (300, -0.003, 0.02)]  # flat, then a volatile slide


@lru_cache(maxsize=None)
def _dates(n, end=END):
    return pd.bdate_range(end=end, periods=n)


def _frame(close, end=END):
    close = np.asarray(close, dtype=float)
    idx = _dates(len(close), end)
    return pd.DataFrame({"open": close, "high": close * 1.005, "low": close * 0.995, "close": close,
                         "volume": 1e6}, index=idx)


def _market(phases, seed=0, hyg_beta=0.8):
    """SPY from `phases` (sessions, drift, vol); 40 stocks and HYG follow it; IEF is independent noise."""
    rng = np.random.default_rng(seed)
    m = np.concatenate([rng.normal(d, v, n) for n, d, v in phases])
    n = len(m)
    noise = np.random.default_rng(seed + 1000)
    bars = {"SPY": _frame(100 * np.exp(np.cumsum(m)))}
    for s in UNIV:
        bars[s] = _frame(50 * np.exp(np.cumsum(m + noise.normal(0, 0.01, n))))
    bars["HYG"] = _frame(80 * np.exp(np.cumsum(hyg_beta * m + noise.normal(0, 0.002, n))))
    bars["IEF"] = _frame(95 * np.exp(np.cumsum(noise.normal(0, 0.003, n))))
    return bars


def _old_classify(bars, benchmark, universe, canaries):
    """The classifier as it was before REG-4..7 (verbatim logic), to prove REG-2/REG-3 did not change."""
    spy = bars[benchmark]["close"].dropna()
    sma200 = ind.sma(spy, 200)
    vol20 = ind.realized_vol(spy, 20)
    above = (spy > sma200).dropna()
    last60 = above.iloc[-60:]
    crossings = int((last60.astype(int).diff().abs() == 1).sum())
    vol_now = float(vol20.iloc[-1])
    vol_median = float(vol20.iloc[-252:].median())
    vol_hist = vol20.iloc[-756:].dropna()
    vol_top_quintile = bool(vol_now >= np.nanpercentile(vol_hist, 80)) if len(vol_hist) > 20 else False
    ret24 = ind.total_return(spy, 504)
    members = [s for s in universe if s in bars and len(bars[s]) >= 200]
    breadth = float(np.mean([bars[s]["close"].iloc[-1] > ind.sma(bars[s]["close"], 200).iloc[-1]
                             for s in members])) if members else float("nan")
    canary_ok = None
    if all(c in bars for c in canaries):
        scores = [ind.momentum_13612w(ind.completed_month_closes(bars[c]["close"])) for c in canaries]
        if not any(np.isnan(scores)):
            canary_ok = all(s > 0 for s in scores)
    spy_above = bool(spy.iloc[-1] > sma200.iloc[-1])
    if not np.isnan(ret24) and ret24 < 0 and vol_top_quintile:
        label = "panic"
    elif not spy_above:
        label = "bear"
    elif crossings >= 3:
        label = "choppy"
    elif vol_now > vol_median:
        label = "bull_volatile"
    else:
        label = "bull_calm"
    return {"label": label, "spy_close": float(spy.iloc[-1]), "spy_sma200": float(sma200.iloc[-1]),
            "vol20": vol_now, "vol20_median_1y": vol_median, "crossings_60d": crossings,
            "return_24m": float(ret24), "vol_top_quintile": vol_top_quintile, "breadth_above_200d": breadth,
            "canary_ok": canary_ok}


def _oracle_series(bars, universe, credit=("HYG", "IEF")):
    """Each REG-4 component written out directly in pandas (clean data: one shared calendar, no gaps)."""
    spy = bars["SPY"]["close"]
    closes = pd.DataFrame({s: bars[s]["close"] for s in universe})
    sma = closes.rolling(200).mean()
    ratio = bars[credit[0]]["close"] / bars[credit[1]]["close"]
    return {
        "spy_return_504d": spy / spy.shift(504) - 1.0,
        "spy_vol20_inverted": np.log(spy).diff().rolling(20).std(),
        "breadth_above_200d": (closes > sma).mean(axis=1).where(sma.notna().all(axis=1)),
        "spy_vs_sma200": spy / spy.rolling(200).mean() - 1.0,
        "credit_hyg_ief_126d": ratio / ratio.shift(126) - 1.0,
    }


def _oracle_components(bars, universe, lookback=1260):
    out = {}
    for name, s in _oracle_series(bars, universe).items():
        pct = s.iloc[-lookback:].dropna().rank(pct=True).iloc[-1]
        out[name] = 1.0 - pct if name == "spy_vol20_inverted" else pct
    return out


def _share_above(closes, n):
    """Share of columns whose last close is above the mean of their last n closes."""
    last = closes.iloc[-1]
    return float((last > closes.iloc[-n:].mean()).mean())


def _same(a, b):
    if isinstance(a, float) and isinstance(b, float) and np.isnan(a) and np.isnan(b):
        return True
    return a == b


# --- indicators --------------------------------------------------------------------------------


def test_percentile_rank_matches_pandas_rank():
    s = pd.Series(np.random.default_rng(3).normal(size=500))
    for lookback in (1, 10, 252, 500, 800):
        expected = s.iloc[-lookback:].rank(pct=True).iloc[-1]
        assert ind.percentile_rank(s, lookback) == pytest.approx(expected)


def test_percentile_rank_extremes_and_ties():
    s = pd.Series(np.arange(100, dtype=float))
    assert ind.percentile_rank(s, 100) == 1.0                       # new high
    assert ind.percentile_rank(s[::-1].reset_index(drop=True), 100) == pytest.approx(0.01)  # new low
    flat = pd.Series([5.0] * 10)
    assert ind.percentile_rank(flat, 10) == pytest.approx(11 / 20)   # all tied: about the middle
    # Values older than the lookback do not count.
    s2 = pd.Series([1000.0] + [1.0, 2.0, 3.0])
    assert ind.percentile_rank(s2, 3) == 1.0
    assert ind.percentile_rank(s2, 4) == pytest.approx(0.75)


def test_percentile_rank_edge_cases():
    nan = float("nan")
    assert np.isnan(ind.percentile_rank(pd.Series(dtype=float), 10))
    assert np.isnan(ind.percentile_rank(pd.Series([1.0, 2.0, nan]), 10))          # today missing
    assert ind.percentile_rank(pd.Series([1.0, nan, np.inf, 2.0]), 10) == 1.0     # gaps ignored
    assert ind.percentile_rank(pd.Series([3.0, nan, 1.0, 2.0]), 10) == pytest.approx(2 / 3)
    assert np.isnan(ind.percentile_rank(pd.Series([1.0, 2.0, 3.0]), 10, min_periods=4))
    assert ind.percentile_rank(pd.Series([1.0, 2.0, 3.0]), 10, min_periods=3) == 1.0
    assert np.isnan(ind.percentile_rank(pd.Series([1.0, 2.0]), 0))
    assert ind.percentile_rank([1.0, 3.0, 2.0], 3) == pytest.approx(2 / 3)       # plain lists work


def test_share_above_sma():
    idx = pd.bdate_range(end=END, periods=6)
    closes = pd.DataFrame({"up": [1, 2, 3, 4, 5, 6], "down": [6, 5, 4, 3, 2, 1],
                           "late": [np.nan] * 4 + [1.0, 2.0]}, index=idx, dtype=float)
    share = ind.share_above_sma(closes, 3)
    assert share.iloc[:2].isna().all()            # no SMA yet
    assert share.iloc[-1] == pytest.approx(0.5)   # "late" has no SMA3 yet, so 1 of 2 counts
    # With min_valid=1.0 every column must count, so the last day is NaN.
    assert np.isnan(ind.share_above_sma(closes, 3, min_valid=1.0).iloc[-1])
    assert ind.share_above_sma(closes[[]], 3).isna().all()


def test_return_correlation():
    a = make_bars(n=200, seed=1)["close"]
    assert ind.return_correlation(a, a * 2.0, 60) == pytest.approx(1.0)
    inverse = pd.Series(1.0 / a.to_numpy(), index=a.index)
    assert ind.return_correlation(a, inverse, 60) < -0.99
    assert np.isnan(ind.return_correlation(a.iloc[:30], a.iloc[:30], 60))   # too short
    flat = pd.Series(10.0, index=a.index)
    assert np.isnan(ind.return_correlation(a, flat, 60))
    # Only common dates count; a repeated date does not crash.
    b = pd.concat([a.iloc[::2], a.iloc[-1:]])
    assert np.isfinite(ind.return_correlation(a, b, 60))


# --- REG-2 / REG-3: unchanged label and permissions -----------------------------------------------


SCENARIOS = {
    "rising": RISING, "falling": FALLING,
    "calm": [(1700, 0.0008, 0.01), (100, 0.0012, 0.003)],
    "volatile": [(1700, 0.0008, 0.006), (100, 0.0015, 0.015)],
    "slide": [(1000, 0.0003, 0.008), (800, -0.0006, 0.008)],
}


def test_label_logic_unchanged_across_scenarios():
    seen = set()
    for phases in SCENARIOS.values():
        for seed in range(3):
            bars = _market(phases, seed)
            old = _old_classify(bars, "SPY", UNIV, ["VWO", "BND"])
            new = classify(bars, "SPY", UNIV, ["VWO", "BND"])
            for k, v in old.items():
                assert _same(getattr(new, k), v), (k, getattr(new, k), v)
            assert new.permissions == PERMISSIONS[old["label"]]
            seen.add(new.label)
    assert seen == set(PERMISSIONS)  # every label was exercised


def test_label_unchanged_with_real_config_bars(cfg, bars):
    new = classify(bars, "SPY", cfg.stock_universe(), ["VWO", "BND"])
    old = _old_classify(bars, "SPY", cfg.stock_universe(), ["VWO", "BND"])
    assert new.label == old["label"] and new.breadth_above_200d == old["breadth_above_200d"]


def test_permissions_table_is_reg3():
    assert PERMISSIONS == {
        "bull_calm": {"A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0},
        "bull_volatile": {"A": 1.0, "B": 0.5, "C": 0.5, "D": 0.5},
        "bear": {"A": 1.0, "B": 0.0, "C": 0.0, "D": 1.0},
        "panic": {"A": 1.0, "B": 0.0, "C": 0.0, "D": 0.5},
        "choppy": {"A": 1.0, "B": 0.5, "C": 0.0, "D": 1.0},
    }


def test_permissions_are_a_copy():
    r = classify(_market(RISING), "SPY", UNIV, [])
    r.permissions["B"] = 99.0
    assert PERMISSIONS[r.label]["B"] != 99.0


def test_regime_old_positional_construction():
    r = Regime("bear", 1.0, 2.0, 0.1, 0.1, 0, -0.1, False, 0.5, None, {"A": 1.0})
    assert r.temperature is None and r.temperature_label == "unknown"
    assert r.temperature_components == {} and r.credit_canary is None
    assert r.stock_bond_corr is None and r.bonds_not_hedging is False
    assert np.isnan(r.breadth_above_50d)
    json.dumps(r.to_dict(), allow_nan=False)


# --- REG-4: temperature ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(4))
def test_rising_market_reads_hot(seed):
    r = classify(_market(RISING, seed), "SPY", UNIV, ["VWO", "BND"])
    assert r.temperature_label == "hot" and r.temperature >= 0.80
    assert r.temperature_components["n_used"] == 5
    assert r.temperature_components["n_sessions"] == 1800
    assert r.temperature_note.startswith("hot: T ") and "5 of 5" in r.temperature_note


@pytest.mark.parametrize("seed", range(4))
def test_falling_market_reads_cold(seed):
    r = classify(_market(FALLING, seed), "SPY", UNIV, ["VWO", "BND"])
    assert r.temperature_label == "cold" and r.temperature <= 0.20
    assert r.temperature_components["spy_vol20_inverted"] < 0.3   # high volatility reads cold


def test_temperature_is_mean_of_components():
    r = classify(_market(RISING, 1), "SPY", UNIV, [])
    parts = [r.temperature_components[k] for k in TEMPERATURE_COMPONENTS]
    assert r.temperature == pytest.approx(np.mean(parts), abs=1e-4)
    assert all(0.0 <= p <= 1.0 for p in parts)
    # Component 2 is inverted: its input is the raw vol20 of SPY.
    assert r.temperature_inputs["spy_vol20_inverted"] == pytest.approx(r.vol20, rel=1e-5)


def test_breadth_component_matches_breadth_display():
    r = classify(_market(RISING, 2), "SPY", UNIV, [])
    assert r.temperature_inputs["breadth_above_200d"] == pytest.approx(r.breadth_above_200d)
    assert 0.0 <= r.breadth_above_50d <= 1.0


@pytest.mark.parametrize("phases,seed", [(RISING, 0), (FALLING, 1), (SCENARIOS["slide"], 2)])
def test_components_match_independent_oracle(phases, seed):
    """Each component's horizon (504, 20, 200, 126 sessions) and window (1,260) is pinned by a pandas oracle."""
    bars = _market(phases, seed)
    r = classify(bars, "SPY", UNIV, [])
    oracle = _oracle_components(bars, UNIV)
    for name in TEMPERATURE_COMPONENTS:
        assert r.temperature_components[name] == pytest.approx(oracle[name], abs=1e-4), name
    assert r.temperature == pytest.approx(np.mean(list(oracle.values())), abs=1e-4)
    assert r.temperature_components["n_values"] == {k: 1260 for k in TEMPERATURE_COMPONENTS}
    closes = pd.DataFrame({s: bars[s]["close"] for s in UNIV})
    assert r.breadth_above_50d == pytest.approx(_share_above(closes, 50))
    assert r.breadth_above_200d == pytest.approx(_share_above(closes, 200))
    # A shorter window gives a different answer, so the 1,260 window is really used.
    assert r.temperature_components["spy_return_504d"] != pytest.approx(
        _oracle_components(bars, UNIV, lookback=600)["spy_return_504d"], abs=1e-3)


def test_breadth_divergence_50d_vs_200d():
    """REG-4: a long rally, then a 30-session drop: most names still above SMA200, few above SMA50."""
    bars = _market([(1400, 0.0, 0.01), (370, 0.003, 0.004), (30, -0.004, 0.004)], seed=1)
    r = classify(bars, "SPY", UNIV, [])
    closes = pd.DataFrame({s: bars[s]["close"] for s in UNIV})
    assert r.breadth_above_200d >= 0.9 and r.breadth_above_50d <= 0.2
    assert r.breadth_above_50d == pytest.approx(_share_above(closes, 50))
    assert r.breadth_above_200d == pytest.approx(_share_above(closes, 200))


def test_breadth_displays_skip_stale_and_bridge_short_gaps():
    """Both breadth displays use the benchmark-aligned closes, like the temperature component."""
    bars = _market(RISING, 3)
    stale, gapped = UNIV[:10], UNIV[10:15]
    for s in stale:
        bars[s] = bars[s].iloc[:-20]                     # feed stopped 20 sessions ago: left out
    for s in gapped:
        bars[s] = bars[s].copy()
        bars[s].iloc[-3:, bars[s].columns.get_loc("close")] = np.nan   # 3 missing closes: bridged
    r = classify(bars, "SPY", UNIV, [])
    fresh = pd.DataFrame({s: bars[s]["close"] for s in UNIV[10:]}).ffill()
    assert r.breadth_above_50d == pytest.approx(_share_above(fresh, 50))
    assert r.breadth_above_200d == pytest.approx(_share_above(fresh, 200))
    assert r.breadth_above_200d == pytest.approx(r.temperature_inputs["breadth_above_200d"])


def test_temperature_label_boundaries():
    """REG-4 thresholds are inclusive: T >= hot is hot, T <= cold is cold."""
    assert _temperature_label(0.80, 0.80, 0.20) == "hot"
    assert _temperature_label(0.20, 0.80, 0.20) == "cold"
    assert _temperature_label(0.79999999, 0.80, 0.20) == "neutral"
    assert _temperature_label(0.20000001, 0.80, 0.20) == "neutral"
    assert _temperature_label(None, 0.80, 0.20) == "unknown"


def test_label_uses_unrounded_temperature():
    """Rounding is for display: a threshold a hair above the true T must not read hot."""
    bars = _market(RISING, 1)
    t = float(np.mean(list(_oracle_components(bars, UNIV).values())))
    assert classify(bars, "SPY", UNIV, [], hot=t + 1e-9).temperature_label == "neutral"
    assert classify(bars, "SPY", UNIV, [], hot=t - 1e-9).temperature_label == "hot"
    assert classify(bars, "SPY", UNIV, [], hot=1.1, cold=t - 1e-9).temperature_label == "neutral"
    assert classify(bars, "SPY", UNIV, [], hot=1.1, cold=t + 1e-9).temperature_label == "cold"


def test_short_window_is_reported():
    """900 sessions: every component ranks on fewer than 1,260 values, and the note says so."""
    bars = _market([(600, 0.0, 0.012), (300, 0.003, 0.004)], seed=1)
    r = classify(bars, "SPY", UNIV, [])
    assert r.temperature_components["n_values"] == {
        "spy_return_504d": 396, "spy_vol20_inverted": 880, "breadth_above_200d": 701,
        "spy_vs_sma200": 701, "credit_hyg_ief_126d": 774}
    assert "5 of 5" in r.temperature_note
    assert "short history: spy_return_504d ranked on 396 of 1260 sessions" in r.temperature_note
    full = classify(_market(RISING, 1), "SPY", UNIV, [])
    assert "short history" not in full.temperature_note
    json.dumps(r.to_dict(), allow_nan=False)


def test_hot_and_cold_thresholds_are_parameters():
    bars = _market(RISING, 1)
    base = classify(bars, "SPY", UNIV, [])
    stricter = classify(bars, "SPY", UNIV, [], hot=0.999)
    assert base.temperature_label == "hot" and stricter.temperature_label == "neutral"
    assert classify(bars, "SPY", UNIV, [], hot=1.1, cold=0.99).temperature_label == "cold"
    assert stricter.label == base.label and stricter.permissions == base.permissions


def test_temperature_uses_lookback_window():
    bars = _market(RISING, 1)
    short = classify(bars, "SPY", UNIV, [], lookback=300)
    assert short.temperature_components["n_used"] == 5
    none = classify(bars, "SPY", UNIV, [], lookback=100)   # fewer than 252 values in every window
    assert none.temperature is None and none.temperature_label == "unknown"


def test_missing_hyg_leaves_credit_component_out():
    bars = _market(RISING, 1)
    full = classify(bars, "SPY", UNIV, ["VWO", "BND"])
    del bars["HYG"]
    r = classify(bars, "SPY", UNIV, ["VWO", "BND"])
    assert r.temperature_components["credit_hyg_ief_126d"] is None
    assert r.temperature_inputs["credit_hyg_ief_126d"] is None
    assert r.temperature_components["n_used"] == 4 and "4 of 5" in r.temperature_note
    assert "credit_hyg_ief_126d" in r.temperature_note
    assert r.credit_canary is None
    assert r.stock_bond_corr is not None           # IEF is still there
    assert r.label == full.label and r.permissions == full.permissions
    others = [r.temperature_components[k] for k in TEMPERATURE_COMPONENTS[:4]]
    assert r.temperature == pytest.approx(np.mean(others), abs=1e-4)


def test_credit_none_and_bad_credit_config():
    bars = _market(RISING, 1)
    for credit in (None, (), ("HYG",), ("HYG", "IEF", "X"), ("HYG", "NOPE"), ("IEF", "IEF")):
        r = classify(bars, "SPY", UNIV, [], credit=credit)
        assert r.temperature_components["credit_hyg_ief_126d"] is None
        assert r.credit_canary is None


def test_missing_universe_leaves_breadth_out():
    bars = _market(RISING, 1)
    r = classify(bars, "SPY", ["NOT_THERE"], [])
    assert r.temperature_components["breadth_above_200d"] is None
    assert np.isnan(r.breadth_above_50d) and np.isnan(r.breadth_above_200d)
    d = r.to_dict()
    assert d["breadth_above_50d"] is None and d["breadth_above_200d"] is None


def test_short_history():
    bars = _market([(300, 0.001, 0.01)], seed=5)
    r = classify(bars, "SPY", UNIV, ["VWO", "BND"])
    comps = r.temperature_components
    assert comps["spy_vol20_inverted"] is not None            # 280 vol values
    assert all(comps[k] is None for k in TEMPERATURE_COMPONENTS if k != "spy_vol20_inverted")
    assert comps["n_used"] == 1 and r.temperature == comps["spy_vol20_inverted"]
    assert r.label == _old_classify(bars, "SPY", UNIV, ["VWO", "BND"])["label"]

    tiny = _market([(60, 0.001, 0.01)], seed=5)
    r = classify(tiny, "SPY", UNIV, ["VWO", "BND"])
    assert r.temperature is None and r.temperature_label == "unknown"
    assert r.temperature_components["n_used"] == 0 and r.temperature_note.startswith("unknown")
    assert r.label == "bear" and r.permissions == PERMISSIONS["bear"]   # no SMA200 yet: not above it
    assert r.stock_bond_corr is None and r.bonds_not_hedging is False   # 59 returns < 60
    json.dumps(r.to_dict(), allow_nan=False)


def test_single_bar_and_empty_benchmark():
    one = {"SPY": _frame([100.0])}
    r = classify(one, "SPY", UNIV, [])
    assert r.label == "bear" and r.temperature is None
    with pytest.raises(ValueError, match="SPY"):
        classify({"SPY": _frame([])}, "SPY", UNIV, [])
    with pytest.raises(ValueError, match="SPY"):
        classify({}, "SPY", UNIV, [])
    all_nan = _frame([np.nan] * 5)
    with pytest.raises(ValueError):
        classify({"SPY": all_nan}, "SPY", UNIV, [])


def test_nan_gaps_and_zero_prices_do_not_crash():
    bars = _market(RISING, 3)
    for s in UNIV[:10]:
        bars[s] = bars[s].copy()
        bars[s].iloc[-3:, bars[s].columns.get_loc("close")] = np.nan   # short gap: bridged
    bars["S11"] = bars["S11"].iloc[:-20]                                 # stale: left out today
    bars["HYG"] = bars["HYG"].copy()
    bars["HYG"].iloc[-400, bars["HYG"].columns.get_loc("close")] = 0.0   # bad print
    bars["IEF"] = bars["IEF"].copy()
    bars["IEF"].iloc[-500:-490, bars["IEF"].columns.get_loc("close")] = np.nan
    bars["SPY"] = bars["SPY"].copy()
    bars["SPY"].iloc[-700, bars["SPY"].columns.get_loc("close")] = np.nan
    r = classify(bars, "SPY", UNIV, ["VWO", "BND"])
    assert r.temperature_components["n_used"] == 5
    assert r.temperature_label in ("hot", "neutral", "cold")
    assert r.stock_bond_corr is not None
    json.dumps(r.to_dict(), allow_nan=False)


def test_duplicate_dates_do_not_crash():
    bars = _market(RISING, 1)
    for s in ("S0", "HYG", "IEF"):
        bars[s] = pd.concat([bars[s], bars[s].iloc[-1:]])
    r = classify(bars, "SPY", UNIV, [])
    assert r.temperature_components["n_used"] == 5


def test_to_dict_is_json_safe():
    r = classify(_market(FALLING, 0), "SPY", UNIV, ["VWO", "BND"])
    d = r.to_dict()
    text = json.dumps(d, allow_nan=False)
    assert json.loads(text)["temperature_label"] == r.temperature_label
    assert isinstance(d["vol_top_quintile"], bool) and isinstance(d["crossings_60d"], int)
    assert set(TEMPERATURE_COMPONENTS) <= set(d["temperature_components"])


def test_performance_1800_sessions_45_symbols(cfg):
    syms = ["SPY", "HYG", "IEF", "VWO", "BND"] + cfg.stock_universe()
    assert len(syms) == 45
    bars = {s: make_bars(n=1800, seed=i + 1, drift=0.0004) for i, s in enumerate(syms)}
    classify(bars, "SPY", cfg.stock_universe(), ["VWO", "BND"])  # warm-up
    t0 = time.perf_counter()
    r = classify(bars, "SPY", cfg.stock_universe(), ["VWO", "BND"], **classify_kwargs(cfg.playbook["regime"]))
    assert time.perf_counter() - t0 < 1.0
    assert r.temperature_components["n_used"] == 5


def test_classify_kwargs_reads_playbook(cfg):
    kw = classify_kwargs(cfg.playbook["regime"])
    assert kw == {"credit": ("HYG", "IEF"), "lookback": 1260, "hot": 0.80, "cold": 0.20, "corr_flag": 0.30}
    assert classify_kwargs({})["lookback"] == 1260
    assert classify_kwargs(None) == classify_kwargs({})


def test_classify_kwargs_tolerates_null_and_bad_values():
    assert classify_kwargs({"credit": None})["credit"] is None          # null turns the pair off
    assert classify_kwargs({"credit": "HYG"})["credit"] is None         # not a list: off, not ('H','Y','G')
    assert classify_kwargs({"credit": ["HYG", "IEF"]})["credit"] == ("HYG", "IEF")
    kw = classify_kwargs({"temperature_lookback": None, "hot": None, "cold": 0, "stock_bond_corr_flag": None})
    assert kw == {"credit": ("HYG", "IEF"), "lookback": 1260, "hot": 0.80, "cold": 0.0, "corr_flag": 0.30}
    r = classify(_market(RISING, 1), "SPY", UNIV, [], **classify_kwargs({"credit": None}))
    assert r.temperature_components["credit_hyg_ief_126d"] is None and r.credit_canary is None


# --- REG-7: stock-bond monitor --------------------------------------------------------------------


def test_stock_bond_correlation_flags_bonds_not_hedging():
    bars = _market(RISING, 1)
    bars["IEF"] = bars["SPY"].copy()                          # moves with stocks
    r = classify(bars, "SPY", UNIV, [])
    assert r.stock_bond_corr == pytest.approx(1.0) and r.bonds_not_hedging is True
    inverse = bars["SPY"].copy()
    inverse["close"] = 10_000.0 / inverse["close"]
    bars["IEF"] = inverse                                     # moves against stocks
    r2 = classify(bars, "SPY", UNIV, [])
    assert r2.stock_bond_corr < -0.9 and r2.bonds_not_hedging is False
    assert r2.label == r.label and r2.permissions == r.permissions   # no trade effect


def test_stock_bond_threshold_and_missing_bond():
    bars = _market(RISING, 1)
    noise = np.random.default_rng(9).normal(0, 0.004, len(bars["SPY"]))
    spy_rets = np.log(bars["SPY"]["close"]).diff().fillna(0).to_numpy()
    bars["IEF"] = _frame(95 * np.exp(np.cumsum(spy_rets + noise)))  # correlated about 0.7
    corr = classify(bars, "SPY", UNIV, []).stock_bond_corr
    assert 0.3 < corr < 0.95
    assert classify(bars, "SPY", UNIV, [], corr_flag=corr + 0.01).bonds_not_hedging is False
    assert classify(bars, "SPY", UNIV, [], corr_flag=corr - 0.01).bonds_not_hedging is True
    del bars["IEF"]
    r = classify(bars, "SPY", UNIV, [])
    assert r.stock_bond_corr is None and r.bonds_not_hedging is False
    assert r.temperature_components["credit_hyg_ief_126d"] is None


def test_stock_bond_uses_bond_parameter():
    bars = _market(RISING, 1)
    bars["TLT"] = bars["SPY"].copy()
    r = classify(bars, "SPY", UNIV, [], bond="TLT")
    assert r.bonds_not_hedging is True


def test_stock_bond_window_and_strict_threshold():
    """REG-7: the last 60 sessions of returns, and the flag needs corr strictly above the threshold."""
    bars = _market(RISING, 1)
    noise = np.random.default_rng(9).normal(0, 0.004, len(bars["SPY"]))
    spy_rets = np.log(bars["SPY"]["close"]).diff().fillna(0).to_numpy()
    bars["IEF"] = _frame(95 * np.exp(np.cumsum(spy_rets * np.linspace(-1, 1, len(spy_rets)) + noise)))
    spy, ief = bars["SPY"]["close"], bars["IEF"]["close"]
    r_spy, r_ief = spy.pct_change(), ief.pct_change()
    c60 = r_spy.iloc[-60:].corr(r_ief.iloc[-60:])
    c120 = r_spy.iloc[-120:].corr(r_ief.iloc[-120:])
    assert abs(c60 - c120) > 0.01                                  # the window length matters here
    c = ind.return_correlation(spy, ief, 60)
    assert c == pytest.approx(c60, abs=1e-12)
    assert classify(bars, "SPY", UNIV, []).stock_bond_corr == pytest.approx(c60, abs=1e-4)
    assert stock_bond(bars, spy, "IEF", c) == (round(c, 4), False)          # equal is not above
    assert stock_bond(bars, spy, "IEF", c - 1e-9)[1] is True


def test_zero_bond_print_does_not_flip_the_flag():
    """A single zero close is bad data: that date is dropped, not read as a -100% day."""
    bars = _market(RISING, 1)
    day = bars["SPY"].index[-10]
    bars["SPY"] = bars["SPY"].copy()
    bars["SPY"].loc[day, "close"] *= 0.97
    clean = classify(bars, "SPY", UNIV, [])
    bars["IEF"] = bars["IEF"].copy()
    bars["IEF"].loc[day, "close"] = 0.0
    r = classify(bars, "SPY", UNIV, [])
    spy, ief = bars["SPY"]["close"], bars["IEF"]["close"]
    assert ind.return_correlation(spy, ief, 60) == pytest.approx(ind.return_correlation(spy, ief.drop(day), 60))
    assert r.bonds_not_hedging is False and abs(r.stock_bond_corr - clean.stock_bond_corr) < 0.05
    neg = ief.copy()
    neg.loc[day] = -5.0
    assert ind.return_correlation(spy, neg, 60) == pytest.approx(ind.return_correlation(spy, ief.drop(day), 60))


@pytest.mark.parametrize("behind", [FILL_GAP_SESSIONS + 1, 40])
def test_stale_bond_gives_no_reading(behind):
    """REG-7/REG-6/REG-4: when IEF stopped updating, no reading is shown as today's."""
    bars = _market(RISING, 1)
    bars["IEF"] = bars["SPY"].copy().iloc[:-behind]                 # would read 1.0 and flag
    r = classify(bars, "SPY", UNIV, [])
    assert r.stock_bond_corr is None and r.bonds_not_hedging is False
    assert r.temperature_components["credit_hyg_ief_126d"] is None and r.credit_canary is None


def test_bond_trailing_nan_closes_count_as_stale():
    bars = _market(RISING, 1)
    bars["IEF"] = bars["SPY"].copy()
    bars["IEF"].iloc[-(FILL_GAP_SESSIONS + 1):, bars["IEF"].columns.get_loc("close")] = np.nan
    assert classify(bars, "SPY", UNIV, []).stock_bond_corr is None


def test_bond_a_few_sessions_behind_still_reads():
    """Up to FILL_GAP_SESSIONS missing sessions are tolerated, the same as for the temperature."""
    bars = _market(RISING, 1)
    bars["IEF"] = bars["SPY"].copy().iloc[:-FILL_GAP_SESSIONS]
    r = classify(bars, "SPY", UNIV, [])
    assert r.stock_bond_corr == pytest.approx(1.0) and r.bonds_not_hedging is True
    assert r.temperature_components["credit_hyg_ief_126d"] is not None and r.credit_canary is not None


# --- REG-6: credit canary, shadow value only ------------------------------------------------------


def _calm_bull_with_credit(hyg_drift, ief_drift, seed=1):
    bars = _market([(1700, 0.0008, 0.01), (100, 0.0012, 0.003)], seed)
    n = len(bars["SPY"])
    bars["HYG"] = _frame(80 * np.exp(np.arange(n) * hyg_drift))
    bars["IEF"] = _frame(95 * np.exp(np.arange(n) * ief_drift))
    return bars


def test_credit_canary_never_changes_label():
    bars = _calm_bull_with_credit(-0.001, 0.001)
    r = classify(bars, "SPY", UNIV, ["VWO", "BND"])
    assert r.label == "bull_calm" and r.permissions == PERMISSIONS["bull_calm"]
    cc = r.credit_canary
    assert cc["hyg_13612w"] < 0 < cc["ief_13612w"]
    assert cc["signal_negative"] is True and cc["would_downgrade"] is True
    assert cc["label_if_applied"] == "bull_volatile"
    assert set(cc) >= {"hyg_13612w", "ief_13612w", "would_downgrade"}


def test_credit_canary_positive_spread():
    r = classify(_calm_bull_with_credit(0.001, -0.001), "SPY", UNIV, [])
    assert r.credit_canary["signal_negative"] is False and r.credit_canary["would_downgrade"] is False
    assert r.credit_canary["label_if_applied"] == r.label


def test_credit_canary_only_downgrades_bull_calm():
    bars = _market(FALLING, 0)
    n = len(bars["SPY"])
    bars["HYG"] = _frame(80 * np.exp(np.arange(n) * -0.001))
    bars["IEF"] = _frame(95 * np.exp(np.arange(n) * 0.001))
    r = classify(bars, "SPY", UNIV, [])
    assert r.label != "bull_calm"
    assert r.credit_canary["signal_negative"] is True and r.credit_canary["would_downgrade"] is False
    assert r.credit_canary["label_if_applied"] == r.label


def test_credit_canary_zero_spread_is_not_negative():
    """REG-6 fires only when the spread is strictly below zero."""
    bars = _calm_bull_with_credit(0.001, 0.001)
    bars["IEF"] = bars["HYG"].copy()                                   # identical scores
    cc = classify(bars, "SPY", UNIV, []).credit_canary
    assert cc["spread"] == 0.0 and cc["signal_negative"] is False and cc["would_downgrade"] is False


def test_credit_canary_uses_benchmark_date_for_month_ends():
    """HYG/IEF bars after SPY's last date (here crossing a month end) must not count."""
    bars = _market(RISING, 1)
    n = len(bars["SPY"])
    rng = np.random.default_rng(4)
    for s, start in (("HYG", 80.0), ("IEF", 95.0)):
        path = start * np.exp(np.cumsum(rng.normal(0, 0.01, n + 5)))
        path[-5:] *= 1.3 if s == "HYG" else 0.8                       # a big move after SPY's last bar
        bars[s] = _frame(path, end="2026-10-02")                       # SPY ends 2026-09-25
    cc = classify(bars, "SPY", UNIV, []).credit_canary
    as_of = bars["SPY"].index[-1]
    hyg = ind.momentum_13612w(ind.completed_month_closes(bars["HYG"]["close"], as_of))
    ief = ind.momentum_13612w(ind.completed_month_closes(bars["IEF"]["close"], as_of))
    assert cc["hyg_13612w"] == pytest.approx(hyg, abs=1e-4) and cc["ief_13612w"] == pytest.approx(ief, abs=1e-4)
    late = ind.momentum_13612w(ind.completed_month_closes(bars["HYG"]["close"]))  # would include September
    assert abs(late - hyg) > 1e-2


def test_credit_canary_ignores_zero_month_end_print():
    bars = _calm_bull_with_credit(-0.001, 0.001)
    clean = classify(bars, "SPY", UNIV, []).credit_canary
    bars["HYG"] = bars["HYG"].copy()
    bars["HYG"].loc[pd.Timestamp("2026-08-31"), "close"] = 0.0       # last completed month-end
    cc = classify(bars, "SPY", UNIV, []).credit_canary
    ref = ind.momentum_13612w(ind.completed_month_closes(bars["HYG"]["close"].drop(pd.Timestamp("2026-08-31")),
                                                         bars["SPY"].index[-1]))
    assert cc["hyg_13612w"] == pytest.approx(ref, abs=1e-4)
    assert abs(cc["hyg_13612w"] - clean["hyg_13612w"]) < 0.05


def test_stale_credit_pair_gives_no_canary():
    bars = _market(RISING, 1)
    assert classify(bars, "SPY", UNIV, []).credit_canary is not None
    bars["HYG"] = bars["HYG"].iloc[:-60]
    r = classify(bars, "SPY", UNIV, [])
    assert r.credit_canary is None and r.temperature_components["credit_hyg_ief_126d"] is None
    assert r.stock_bond_corr is not None                               # IEF itself is current


def test_credit_canary_needs_13_month_ends():
    bars = _market([(200, 0.001, 0.01)], seed=2)
    assert classify(bars, "SPY", UNIV, []).credit_canary is None


# --- REG-8: DAA canary stays display only ---------------------------------------------------------


def test_daa_canary_display():
    bars = _market(RISING, 1)
    n = len(bars["SPY"])
    up, down = _frame(50 * np.exp(np.arange(n) * 0.001)), _frame(50 * np.exp(np.arange(n) * -0.001))
    bars.update({"VWO": up, "BND": up})
    ok = classify(bars, "SPY", UNIV, ["VWO", "BND"])
    assert ok.canary_ok is True
    bars["BND"] = down
    bad = classify(bars, "SPY", UNIV, ["VWO", "BND"])
    assert bad.canary_ok is False
    assert bad.label == ok.label and bad.permissions == ok.permissions   # never traded
    del bars["BND"]
    assert classify(bars, "SPY", UNIV, ["VWO", "BND"]).canary_ok is None
    bars["BND"] = up.iloc[-100:]
    assert classify(bars, "SPY", UNIV, ["VWO", "BND"]).canary_ok is None   # < 13 month-ends
