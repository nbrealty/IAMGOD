import copy

import pandas as pd
import pytest

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


# --- C-9 sector cap ---------------------------------------------------------------------------------

SEMIS = ["NVDA", "AVGO", "AMD", "AMAT"]


def _breakout_bars(seed: int) -> pd.DataFrame:
    """A strong uptrend that breaks out today on 3x volume (passes the C-2 template)."""
    df = make_bars(drift=0.0015, vol=0.008, seed=seed)
    col = df.columns.get_loc
    df.iloc[-1, col("close")] = df["high"].iloc[-51:-1].max() * 1.03
    df.iloc[-1, col("high")] = df["close"].iloc[-1]
    df.iloc[-1, col("volume")] = df["volume"].iloc[-51:-1].mean() * 3
    return df


def _c_bars(bars, names):
    out = dict(bars)
    for i, sym in enumerate(names):
        out[sym] = _breakout_bars(31 + i)
    return out


def _held_lot(df, stop=1.0):
    return Lot(10, float(df["close"].iloc[-5]), str(df.index[-5].date()), stop, stop)


def _semis_in(plan):
    return sorted(s for s, t in plan.targets.items() if t.qty > 0 and s in SEMIS)


def test_c9_caps_entries_entering_today(cfg, bars):
    bars = _c_bars(bars, SEMIS + ["JPM", "MSFT"])
    plan = strat.sleeve_c(bars, cfg.sleeves["C"], 15000, {}, cfg.policy, 100000, 1.0)
    rs = {c["symbol"]: c["rs_pct"] for c in plan.candidates}
    assert all(c["breakout_today"] for c in plan.candidates if c["symbol"] in SEMIS + ["JPM", "MSFT"])
    entered = _semis_in(plan)
    assert len(entered) == 2
    assert entered == sorted(sorted(SEMIS, key=lambda s: -rs[s])[:2])  # the two best-ranked semis win
    assert plan.targets["JPM"].qty > 0 and plan.targets["MSFT"].qty > 0  # other groups still enter
    skipped = [s for s in SEMIS if s not in entered]
    for sym in skipped:
        assert any(n.startswith("C-9") and sym in n and "semis_ai" in n for n in plan.notes)


def test_c9_counts_held_positions(cfg, bars):
    bars = _c_bars(bars, SEMIS + ["JPM"])
    lots = {"NVDA": _held_lot(bars["NVDA"]), "AVGO": _held_lot(bars["AVGO"])}
    plan = strat.sleeve_c(bars, cfg.sleeves["C"], 15000, lots, cfg.policy, 100000, 1.0)
    assert plan.targets["NVDA"].qty == 10 and plan.targets["AVGO"].qty == 10  # held, not exiting
    assert "AMD" not in plan.targets and "AMAT" not in plan.targets
    assert any("C-9" in n and "AMD" in n for n in plan.notes)
    assert plan.targets["JPM"].qty > 0


def test_c9_exiting_position_frees_its_group_slot(cfg, bars):
    bars = _c_bars(bars, SEMIS)
    nvda_close = float(bars["NVDA"]["close"].iloc[-1])
    lots = {"NVDA": _held_lot(bars["NVDA"], stop=nvda_close * 1.01), "AVGO": _held_lot(bars["AVGO"])}
    plan = strat.sleeve_c(bars, cfg.sleeves["C"], 15000, lots, cfg.policy, 100000, 1.0)
    assert plan.targets["NVDA"].qty == 0  # stop hit: exits today
    new_semis = [s for s in ("AMD", "AMAT") if s in plan.targets and plan.targets[s].qty > 0]
    assert len(new_semis) == 1  # AVGO held + one new name = 2


def test_c9_explicit_arguments_and_old_call(cfg, bars):
    bars = _c_bars(bars, SEMIS)
    old = strat.sleeve_c(bars, cfg.sleeves["C"], 15000, {}, cfg.policy, 100000, 1.0)
    assert len(_semis_in(old)) == 2  # old positional call still applies the configured cap
    one = strat.sleeve_c(bars, cfg.sleeves["C"], 15000, {}, cfg.policy, 100000, 1.0, sector_max=1)
    assert len(_semis_in(one)) == 1
    fn = strat.sleeve_c(bars, cfg.sleeves["C"], 15000, {}, cfg.policy, 100000, 1.0, sectors=cfg.sector_of,
                        sector_max=2)
    assert _semis_in(fn) == _semis_in(old)
    flat = {s: "chips" for s in SEMIS}
    by_flat = strat.sleeve_c(bars, cfg.sleeves["C"], 15000, {}, cfg.policy, 100000, 1.0, sectors=flat,
                             sector_max=3)
    assert len(_semis_in(by_flat)) == 3
    no_groups = strat.sleeve_c(bars, cfg.sleeves["C"], 15000, {}, cfg.policy, 100000, 1.0, sectors={})
    assert len(_semis_in(no_groups)) == 4  # no groups known: only the 5 slots limit
    assert not any("C-9" in n for n in no_groups.notes)


def test_c9_regime_gate_and_candidates_show_sector(cfg, bars):
    bars = _c_bars(bars, SEMIS)
    plan = strat.sleeve_c(bars, cfg.sleeves["C"], 15000, {}, cfg.policy, 100000, 0.0)
    assert not plan.targets and not any("C-9" in n for n in plan.notes)
    assert {c["symbol"]: c["sector"] for c in plan.candidates}["NVDA"] == "semis_ai"


def test_sector_lookup_shapes(cfg):
    groups = strat.sector_lookup(cfg.sleeves["C"]["sectors"])
    assert groups("NVDA") == "semis_ai" and groups("JPM") == "financials" and groups("SPY") is None
    assert strat.sector_lookup({"NVDA": "x"})("NVDA") == "x"
    assert strat.sector_lookup(None)("NVDA") is None
    assert strat.sector_lookup(cfg.sector_of)("AAPL") == "hardware_auto"


def test_sleeves_hold_positions_whose_bars_are_missing(cfg, bars):
    """A symbol dropped by the data fetch never crashes a sleeve: held lots stay as they are."""
    no_iwm = {k: v for k, v in bars.items() if k != "IWM"}
    held = Lot(4, 180.0, "2026-09-20", 170.0, 170.0)
    plan = strat.sleeve_b(no_iwm, cfg.sleeves["B"], 2000, {"IWM": held}, cfg.policy, 10000, 1.0)
    t = plan.targets["IWM"]
    assert (t.qty, t.stop, t.reason) == (4, 170.0, "hold (no data)")
    assert "IWM" not in {c["symbol"] for c in plan.candidates}
    empty = dict(bars, IWM=bars["IWM"].iloc[:0])
    assert strat.sleeve_b(empty, cfg.sleeves["B"], 2000, {}, cfg.policy, 10000, 1.0).targets.get("IWM") is None

    as_of = bars["SPY"].index[-1]
    no_dbc = {k: v for k, v in bars.items() if k != "DBC"}
    full = strat.sleeve_a(bars, cfg.sleeves["A"], 50000, {}, cfg.policy, as_of)
    plan = strat.sleeve_a(no_dbc, cfg.sleeves["A"], 50000, {"DBC": Lot(20, 25.0, "2026-01-02")}, cfg.policy, as_of)
    assert plan.targets["DBC"].qty == 20 and plan.targets["DBC"].reason == "hold (no data)"
    cash = cfg.sleeves["A"]["cash"]
    assert plan.targets[cash].qty <= full.targets[cash].qty + 1e-9  # the held slice is not also given to cash
    unheld = strat.sleeve_a(no_dbc, cfg.sleeves["A"], 50000, {}, cfg.policy, as_of)
    assert "DBC" not in unheld.targets and any("DBC" in n for n in unheld.notes)


def test_b_and_c_size_with_the_per_sleeve_1r(cfg, bars):
    """RISK-2: sleeve_b and sleeve_c size a new entry with risk_pct_by_sleeve, the same 1R risk.py caps at."""
    policy = copy.deepcopy(cfg.policy)
    policy["per_trade"]["risk_pct_by_sleeve"].update({"B": 0.0025, "C": 0.004})
    assert strat.risk_pct(policy, "B") == 0.0025 and strat.risk_pct(cfg.policy, "C") == cfg.risk_pct("C")
    bars = dict(bars)
    bars["SPY"] = _pullback(make_bars(drift=0.001, vol=0.004, seed=21))
    b = strat.sleeve_b(bars, cfg.sleeves["B"], 1e6, {}, policy, 10000, 1.0).targets["SPY"]
    assert (bars["SPY"]["close"].iloc[-1] - b.stop) * b.qty == pytest.approx(0.0025 * 10000)
    bars = _c_bars(bars, ["NVDA"])
    c = strat.sleeve_c(bars, cfg.sleeves["C"], 1e6, {}, policy, 10000, 1.0).targets["NVDA"]
    assert (bars["NVDA"]["close"].iloc[-1] - c.stop) * c.qty == pytest.approx(0.004 * 10000)
    policy["per_trade"]["risk_pct_by_sleeve"]["C"] = 0.5  # never above the hard cap
    assert strat.risk_pct(policy, "C") == policy["per_trade"]["risk_pct_hard_cap"]


def test_faber_asset_matches_sleeve_a(cfg, bars):
    as_of = bars["SPY"].index[-1]
    plan = strat.sleeve_a(bars, cfg.sleeves["A"], 50000, {}, cfg.policy, as_of)
    for c in plan.candidates:
        fa = strat.faber_asset(bars[c["symbol"]]["close"], as_of, cfg.policy["portfolio"]["vol_target_annual"])
        assert fa["in"] == c["above_10m_sma"] and round(fa["vol60"], 3) == c["vol60"]
