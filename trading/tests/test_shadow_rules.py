"""TEST FIRST shadow rules (trader/shadow_rules.py): each rule on synthetic data, targets never change,
missing data never raises."""
import copy
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from conftest import make_bars
from trader import indicators as ind
from trader import shadow_rules as sr
from trader import strategies as strat
from trader.config import Config, load_config
from trader.models import Lot, SleevePlan, Target
from trader.regime import PERMISSIONS

END = "2026-09-25"
AS_OF = pd.Timestamp(END)
EQUITY = 100_000.0


# --- helpers -------------------------------------------------------------------------------------------


def regime(label="bull_calm", **kw):
    base = dict(label=label, permissions=dict(PERMISSIONS[label]), temperature=0.5, vol20=0.15,
                spy_close=110.0, spy_sma200=100.0)
    base.update(kw)
    return SimpleNamespace(**base)


def from_closes(closes, end=END, volume=1_000_000.0, spread=0.005, freq="B"):
    closes = np.asarray(closes, dtype=float)
    idx = pd.date_range(end=end, periods=len(closes), freq=freq)
    open_ = np.r_[closes[0], closes[:-1]]
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, closes) * (1 + spread),
                         "low": np.minimum(open_, closes) * (1 - spread), "close": closes,
                         "volume": np.full(len(closes), float(volume))}, index=idx)


def plan(sleeve, capital, targets=(), candidates=()):
    p = SleevePlan(sleeve, capital)
    for t in targets:
        p.targets[t.symbol] = t
    p.candidates.extend(candidates)
    return p


def close_of(df):
    return float(df["close"].iloc[-1])


def inputs(cfg, bars, plans=None, lots=None, reg=None, **kw):
    return sr.ShadowInputs(bars=bars, cfg=cfg, plans=plans or {}, lots=lots or {},
                           regime=reg if reg is not None else regime(), as_of=AS_OF, **kw)


def with_playbook(cfg, **sleeve_a):
    pb = copy.deepcopy(cfg.playbook)
    pb["sleeves"]["A"].update(sleeve_a)
    return Config(playbook=pb, policy=cfg.policy)


UP = dict(drift=0.002, vol=0.001)
DOWN = dict(drift=-0.001, vol=0.001)
CASH = dict(drift=0.0002, vol=0.0001)


@pytest.fixture(scope="module")
def data():
    """Bars for every symbol the bot fetches (allowlist + data-only symbols such as HYG, VOO, GLD).

    Shared by the module: tests copy the dict (and any frame they edit), never change it in place.
    """
    syms = load_config().data_symbols()
    return {s: make_bars(seed=i + 1, drift=0.0005, crypto="/" in s) for i, s in enumerate(syms)}


def assert_result_shape(res, rule_id):
    assert set(res) == {"rule", "fires", "detail", "would_change"}
    assert res["rule"] == rule_id
    assert res["fires"] == bool(res["would_change"])
    json.dumps(res, allow_nan=False)


# --- REG-5 ---------------------------------------------------------------------------------------------


def test_reg5_hot_caps_weight_above_default(cfg, data):
    plans = {"B": plan("B", 25_000), "C": plan("C", 15_000)}
    res = sr.shadow_reg5(inputs(cfg, data, plans, reg=regime(temperature=0.9), equity=EQUITY))
    assert_result_shape(res, "REG-5")
    assert res["would_change"] == [{"sleeve": "B", "action": "cap weight", "weight_from": 0.25, "weight_to": 0.2}]
    explicit = sr.shadow_reg5(inputs(cfg, data, plans, reg=regime(temperature=0.85),
                                     weights={"B": 0.20, "C": 0.18}))
    assert [c["sleeve"] for c in explicit["would_change"]] == ["C"]


def test_reg5_quiet_when_not_hot_or_at_default(cfg, data):
    plans = {"B": plan("B", 25_000), "C": plan("C", 15_000)}
    assert not sr.shadow_reg5(inputs(cfg, data, plans, reg=regime(temperature=0.5), equity=EQUITY))["fires"]
    at_default = {"B": plan("B", 20_000), "C": plan("C", 15_000)}
    res = sr.shadow_reg5(inputs(cfg, data, at_default, reg=regime(temperature=0.95), equity=EQUITY))
    assert not res["fires"] and res["detail"]["is_hot"]


def test_reg5_missing_temperature_or_weights(cfg, data):
    res = sr.shadow_reg5(inputs(cfg, data, reg=regime(temperature=None)))
    assert res == {"rule": "REG-5", "fires": False, "detail": {"skipped": "temperature unknown"}, "would_change": []}
    assert sr.shadow_reg5(inputs(cfg, data, reg=regime(temperature=float("nan"))))["detail"]["skipped"]
    res = sr.shadow_reg5(inputs(cfg, data, {"B": plan("B", 25_000)}, reg=regime(temperature=0.9)))
    assert not res["fires"] and res["detail"]["note"] == "sleeve weights unknown"


def test_reg5_state_equity_rounding_is_not_a_signal(cfg):
    """Plans are sized from the broker's equity; the state stores it to the cent. B and C at their defaults
    must not read as 'above default' (0.2 -> 0.2) through compute's state fallback."""
    broker_equity = 100_000.004
    plans = {s: plan(s, broker_equity * w) for s, w in {"A": 0.55, "B": 0.20, "C": 0.15}.items()}
    state = SimpleNamespace(equity_history=[{"date": END, "equity": round(broker_equity, 2)}], closed_trades=[])
    res = sr.compute({}, cfg, plans, {}, regime(temperature=0.85), AS_OF, state=state)["REG-5"]
    assert res["detail"]["is_hot"] and not res["fires"]
    plans["C"] = plan("C", broker_equity * 0.18)
    res = sr.compute({}, cfg, plans, {}, regime(temperature=0.85), AS_OF, state=state)["REG-5"]
    assert res["would_change"] == [{"sleeve": "C", "action": "cap weight", "weight_from": 0.18, "weight_to": 0.15}]
    broken = SimpleNamespace(equity_history=[{"date": END}], closed_trades=[])  # no equity field: no crash
    res = sr.shadow_reg5(inputs(cfg, {}, plans, reg=regime(temperature=0.85), state=broken,
                                weights={"B": None, "C": 0.18}))
    assert [c["sleeve"] for c in res["would_change"]] == ["C"]


# --- REG-6 ---------------------------------------------------------------------------------------------


def _credit(data, hyg=DOWN, ief=UP):
    out = dict(data)
    out["HYG"] = make_bars(seed=501, **hyg)
    out["IEF"] = make_bars(seed=502, **ief)
    return out


def _b_entry(bars, sym="SPY", stop_frac=0.9, capital=20_000, perm=1.0):
    """A B entry sized exactly like sleeve_b (risk-bound when stop_frac is 0.9)."""
    c = close_of(bars[sym])
    stop = c * stop_frac
    qty = min(0.005 * EQUITY * perm / (c - stop), capital / 2 / c)
    return Target(sym, "B", qty, stop, "RSI2 entry")


def test_reg6_downgrades_bull_calm_and_halves_entries(cfg, data):
    bars = _credit(data)
    t = _b_entry(bars)
    nvda = close_of(bars["NVDA"])
    c_t = Target("NVDA", "C", 0.005 * EQUITY / (0.2 * nvda), nvda * 0.8, "breakout entry")
    plans = {"B": plan("B", 20_000, [t]), "C": plan("C", 15_000, [c_t])}
    res = sr.shadow_reg6(inputs(cfg, bars, plans, equity=EQUITY))
    assert_result_shape(res, "REG-6")
    d = res["detail"]
    assert d["credit_weak"] and d["spread"] < 0 and d["shadow_label"] == "bull_volatile"
    ch = res["would_change"]
    assert ch[0] == {"action": "regime label", "from": "bull_calm", "to": "bull_volatile"}
    assert {"sleeve": "B", "action": "permission", "from": 1.0, "to": 0.5} in ch
    b = next(c for c in ch if c.get("symbol") == "SPY")
    assert b["approx"] is False and b["qty_to"] == pytest.approx(t.qty / 2, rel=1e-4)
    cc = next(c for c in ch if c.get("symbol") == "NVDA")
    assert cc["qty_to"] == pytest.approx(c_t.qty / 2, rel=1e-4)


def test_reg6_approximate_size_without_equity_and_d_scaling(cfg, data):
    bars = _credit(data)
    t = _b_entry(bars)
    plans = {"B": plan("B", 20_000, [t]), "D": plan("D", 3_000, [Target("BTC/USD", "D", 0.5, 1.0)])}
    res = sr.shadow_reg6(inputs(cfg, bars, plans))
    b = next(c for c in res["would_change"] if c.get("symbol") == "SPY")
    assert b["approx"] is True and b["qty_to"] == pytest.approx(t.qty / 2, rel=1e-4)
    d = next(c for c in res["would_change"] if c.get("symbol") == "BTC/USD")
    assert d["qty_to"] == pytest.approx(0.25)


def test_reg6_no_change_outside_bull_calm_or_with_strong_credit(cfg, data):
    bars = _credit(data)
    plans = {"B": plan("B", 20_000, [_b_entry(bars)])}
    res = sr.shadow_reg6(inputs(cfg, bars, plans, reg=regime("bull_volatile")))
    assert not res["fires"] and res["detail"]["credit_weak"]
    strong = _credit(data, hyg=UP, ief=DOWN)
    res = sr.shadow_reg6(inputs(cfg, strong, plans))
    assert not res["fires"] and not res["detail"]["credit_weak"]


def test_reg6_missing_or_short_credit_data(cfg, data):
    bars = dict(data)
    del bars["HYG"]
    assert sr.shadow_reg6(inputs(cfg, bars))["detail"] == {"skipped": "no bars for HYG"}
    short = dict(data)
    short["HYG"] = make_bars(n=150, seed=3)
    assert "13 completed month-ends" in sr.shadow_reg6(inputs(cfg, short))["detail"]["skipped"]


# --- A-6 -----------------------------------------------------------------------------------------------


def _gem(data, voo=UP, veu=DOWN, agg=DOWN, bil=CASH, spy=None):
    out = dict(data)
    for i, (sym, kw) in enumerate((("VOO", voo), ("VEU", veu), ("AGG", agg), ("BIL", bil))):
        out[sym] = make_bars(seed=600 + i, **kw)
    out["SPY"] = make_bars(seed=610, **(spy or voo))
    return out


def test_a6_us_leg_held_in_voo(cfg, data):
    res = sr.shadow_a6(inputs(cfg, _gem(data)))
    assert_result_shape(res, "A-6")
    assert res["detail"]["pick"] == "VOO" and res["detail"]["plain_gem_pick"] == "SPY"
    assert res["would_change"] == [
        {"sleeve": "A", "symbol": "VOO", "action": "hold GEM leg", "weight_in_sleeve": 0.5},
        {"sleeve": "A", "action": "scale Faber legs", "factor": 0.5}]


def test_a6_bond_leg_needs_a_trend(cfg, data):
    res = sr.shadow_a6(inputs(cfg, _gem(data, voo=DOWN, agg=DOWN)))
    assert res["detail"]["pick"] == "BIL" and res["detail"]["plain_gem_pick"] == "AGG"
    res = sr.shadow_a6(inputs(cfg, _gem(data, voo=DOWN, agg=UP)))
    assert res["detail"]["pick"] == "AGG"
    res = sr.shadow_a6(inputs(cfg, _gem(data, voo=dict(drift=0.001, vol=0.001), veu=UP)))
    assert res["detail"]["pick"] == "VEU"


def test_a6_missing_data_and_live_gem_on(cfg, data):
    bars = _gem(data)
    no_voo = {k: v for k, v in bars.items() if k != "VOO"}
    assert "VOO" in sr.shadow_a6(inputs(cfg, no_voo))["detail"]["skipped"]
    no_veu = {k: v for k, v in bars.items() if k != "VEU"}
    assert sr.shadow_a6(inputs(cfg, no_veu))["detail"]["pick"] == "VOO"
    gem_on = with_playbook(cfg, gem_blend=True)
    res = sr.shadow_a6(inputs(gem_on, bars))
    assert not res["fires"]  # the live GEM holds SPY, the shadow VOO: the same exposure
    res = sr.shadow_a6(inputs(gem_on, _gem(data, voo=DOWN, agg=DOWN)))
    assert res["would_change"] == [{"sleeve": "A", "symbol": "BIL", "action": "hold GEM leg",
                                    "weight_in_sleeve": 0.5}]


# --- A-7 / A-8 / A-9 ---------------------------------------------------------------------------------


def _a_assets(cfg, data, bil=CASH, **asset_kw):
    out = dict(data)
    for i, sym in enumerate(cfg.sleeves["A"]["assets"]):
        out[sym] = make_bars(seed=700 + i, **(asset_kw or dict(drift=0.0015, vol=0.004)))
    out["BIL"] = make_bars(seed=720, **bil)
    return out


def test_a7_second_vote_halves_assets_that_trail_cash(cfg, data):
    bars = _a_assets(cfg, data, bil=dict(drift=0.004, vol=0.0005))  # cash beats every asset
    res = sr.shadow_a7(inputs(cfg, bars))
    assert_result_shape(res, "A-7")
    votes = res["detail"]["votes"]
    assert all(v["above_10m_sma"] and not v["beats_cash"] for v in votes.values())
    rows = {c["symbol"]: c for c in res["would_change"]}
    for sym in cfg.sleeves["A"]["assets"]:
        assert rows[sym]["weight_to"] == pytest.approx(rows[sym]["weight_from"] / 2, abs=1e-4)
    assert rows["BIL"]["weight_to"] > rows["BIL"]["weight_from"]


def test_a7_agrees_when_both_votes_agree_and_skips_without_cash(cfg, data):
    bars = _a_assets(cfg, data)
    res = sr.shadow_a7(inputs(cfg, bars))
    assert all(v["beats_cash"] for v in res["detail"]["votes"].values())
    assert not res["fires"]
    no_bil = {k: v for k, v in bars.items() if k != "BIL"}
    assert "BIL" in sr.shadow_a7(inputs(cfg, no_bil))["detail"]["skipped"]


def test_a8_sleeve_level_vol_target_reduces_cash_drag(cfg, data):
    bars = _a_assets(cfg, data, drift=0.0015, vol=0.009)  # each ETF ~14% vol, the mix much less
    res = sr.shadow_a8(inputs(cfg, bars))
    assert_result_shape(res, "A-8")
    d = res["detail"]
    assert d["held"] and d["sleeve_vol"] < 0.10 and d["scale"] == 1.0
    rows = {c["symbol"]: c for c in res["would_change"]}
    for sym in d["held"]:
        assert rows[sym]["weight_to"] == pytest.approx(0.2) and rows[sym]["weight_from"] < 0.2
    assert rows["BIL"]["weight_to"] < rows["BIL"]["weight_from"]


def test_a8_vol_target_binds_for_correlated_volatile_assets(cfg, data):
    """One ~32%-vol driver at different strengths (fully correlated): the sleeve's vol is well above 10%, so
    every held asset gets the same weight 1/5 x 0.10 / sleeve_vol instead of its own 1/5 x 0.10 / vol60."""
    bars = dict(data)
    driver = np.random.default_rng(740).normal(0, 0.02, 600)
    for sym, m in zip(cfg.sleeves["A"]["assets"], (1.0, 1.0, 0.5, 0.5, 0.6)):
        bars[sym] = from_closes(100 * np.exp(np.cumsum(0.003 + m * driver)))
    res = sr.shadow_a8(inputs(cfg, bars))
    assert_result_shape(res, "A-8")
    d = res["detail"]
    assert d["held"] == list(cfg.sleeves["A"]["assets"]) and d["sleeve_vol"] > 0.10
    assert d["scale"] < 1 and d["scale"] == pytest.approx(0.10 / d["sleeve_vol"], abs=1e-3)
    rows = {c["symbol"]: c for c in res["would_change"]}
    for sym in d["held"]:
        assert rows[sym]["weight_to"] == pytest.approx(0.2 * d["scale"], abs=1e-3)
        assert rows[sym]["weight_from"] != pytest.approx(rows[sym]["weight_to"], abs=1e-3)


def test_a8_all_out_and_missing_asset(cfg, data):
    bars = _a_assets(cfg, data, drift=-0.002, vol=0.004)
    res = sr.shadow_a8(inputs(cfg, bars))
    assert not res["fires"] and res["detail"]["held"] == []
    del bars["DBC"]
    assert sr.shadow_a8(inputs(cfg, bars))["detail"] == {"skipped": "no bars for DBC"}


def test_a9_gold_as_sixth_asset(cfg, data):
    bars = _a_assets(cfg, data)
    bars["GLD"] = make_bars(seed=730, drift=0.0015, vol=0.004)
    res = sr.shadow_a9(inputs(cfg, bars))
    assert_result_shape(res, "A-9")
    assert res["detail"]["gld_above_10m_sma"]
    rows = {c["symbol"]: c for c in res["would_change"]}
    assert rows["GLD"]["weight_from"] == 0 and rows["GLD"]["weight_to"] == pytest.approx(
        res["detail"]["gld_scale"] / 6, abs=1e-3)
    assert rows["SPY"]["weight_to"] == pytest.approx(rows["SPY"]["weight_from"] * 5 / 6, abs=1e-4)
    del bars["GLD"]
    assert sr.shadow_a9(inputs(cfg, bars))["detail"] == {"skipped": "no bars for GLD"}


def test_a9_quiet_when_everything_is_in_cash(cfg, data):
    bars = _a_assets(cfg, data, drift=-0.002, vol=0.004)
    bars["GLD"] = make_bars(seed=731, drift=-0.002, vol=0.004)
    assert not sr.shadow_a9(inputs(cfg, bars))["fires"]


# --- B-7 / B-8 / B-9 / B-10 ----------------------------------------------------------------------------


def test_b7_market_on_close_for_b_trades(cfg, data):
    qqq_lot = Lot(5, 100.0, "2026-09-20", 80.0, 80.0)
    plans = {"B": plan("B", 20_000, [Target("SPY", "B", 10, 90.0, "entry"), Target("QQQ", "B", 0.0, 80.0, "exit"),
                                    Target("IWM", "B", 3, 50.0, "hold")])}
    lots = {"B": {"QQQ": qqq_lot, "IWM": Lot(3, 50.0, "2026-09-20", 40.0, 40.0)}}
    res = sr.shadow_b7(inputs(cfg, data, plans, lots))
    assert_result_shape(res, "B-7")
    by_sym = {c["symbol"]: c for c in res["would_change"]}
    assert set(by_sym) == {"SPY", "QQQ"}
    assert by_sym["SPY"]["action"] == "buy market-on-close" and by_sym["SPY"]["qty"] == 10
    assert by_sym["SPY"]["price"] == pytest.approx(close_of(data["SPY"]), abs=1e-4)
    assert by_sym["QQQ"]["action"] == "sell market-on-close" and by_sym["QQQ"]["qty"] == 5
    assert not sr.shadow_b7(inputs(cfg, data, {"B": plan("B", 20_000)}))["fires"]
    assert sr.shadow_b7(inputs(cfg, data))["detail"]["skipped"] == "no sleeve B plan today"


def _dip_after_rise():
    """Close just above SMA5 after a small down day: live B exits, RSI2 stays below 70."""
    return from_closes(np.r_[np.linspace(100, 150, 300), 149.9])


def test_b8_time_stop_variants(cfg, data):
    bars = dict(data)
    df = from_closes(np.linspace(200, 150, 300))  # steady fall: close below SMA5, RSI2 near 0
    bars["SPY"] = df
    lot = Lot(10, 180.0, str(df.index[-13].date()), 1.0, 1.0)
    plans = {"B": plan("B", 20_000, [Target("SPY", "B", 0.0, 1.0, "RSI2 time stop")])}
    res = sr.shadow_b8(inputs(cfg, bars, plans, {"B": {"SPY": lot}}))
    assert_result_shape(res, "B-8")
    got = {(c["variant"], c["action"]) for c in res["would_change"]}
    assert got == {("time_stop_off", "hold"), ("time_stop_15", "hold")}


def test_b8_rsi2_exit_variant_and_size_variant(cfg, data):
    bars = dict(data)
    df = _dip_after_rise()
    rsi2 = float(ind.rsi(df["close"], 2).iloc[-1])
    assert close_of(df) > float(ind.sma(df["close"], 5).iloc[-1]) and 5 <= rsi2 < 70
    bars["SPY"], bars["QQQ"] = df, df
    lot = Lot(10, 148.0, str(df.index[-4].date()), 1.0, 1.0)
    plans = {"B": plan("B", 20_000, [Target("SPY", "B", 0.0, 1.0, "exit"), Target("QQQ", "B", 8.0, 140.0, "entry")])}
    res = sr.shadow_b8(inputs(cfg, bars, plans, {"B": {"SPY": lot}}))
    rows = {(c["variant"], c["symbol"]): c for c in res["would_change"]}
    assert rows[("rsi2_exit_70", "SPY")]["action"] == "hold"
    size = rows[("size_by_rsi2", "QQQ")]
    assert size["qty_from"] == 8.0 and size["qty_to"] == 4.0
    assert res["detail"]["changes_by_variant"]["size_by_rsi2"] == 1


def test_b8_full_size_below_rsi2_5_and_missing_bars(cfg, data):
    bars = dict(data)
    bars["SPY"] = from_closes(np.linspace(200, 150, 300))
    plans = {"B": plan("B", 20_000, [Target("SPY", "B", 8.0, 140.0, "entry")])}
    assert not sr.shadow_b8(inputs(cfg, bars, plans))["fires"]
    del bars["SPY"]
    res = sr.shadow_b8(inputs(cfg, bars, plans, {"B": {"SPY": Lot(1, 100.0, "2026-09-01", 90.0, 90.0)}}))
    assert not res["fires"] and res["detail"]["skipped_symbols"]


def test_b9_full_permission_in_bull_volatile(cfg, data):
    t = _b_entry(data, perm=0.5)
    plans = {"B": plan("B", 20_000, [t])}
    res = sr.shadow_b9(inputs(cfg, data, plans, reg=regime("bull_volatile", vol20=0.18), equity=EQUITY))
    assert_result_shape(res, "B-9")
    variants = {c["variant"] for c in res["would_change"]}
    assert variants == {"no_halving", "vol20_gate_25"}
    bigger = [c for c in res["would_change"] if c.get("symbol") == "SPY"]
    assert all(c["qty_to"] == pytest.approx(min(2 * t.qty, 20_000 / 2 / close_of(data["SPY"])), rel=1e-4)
               for c in bigger)
    hot_vol = sr.shadow_b9(inputs(cfg, data, plans, reg=regime("bull_volatile", vol20=0.30), equity=EQUITY))
    assert {c["variant"] for c in hot_vol["would_change"]} == {"no_halving"}


def test_b9_no_change_in_other_regimes(cfg, data):
    plans = {"B": plan("B", 20_000, [_b_entry(data)])}
    for label in ("bull_calm", "bear", "panic", "choppy"):
        assert not sr.shadow_b9(inputs(cfg, data, plans, reg=regime(label)))["fires"]
    below = regime("bull_volatile", spy_close=90.0, spy_sma200=100.0)
    assert not sr.shadow_b9(inputs(cfg, data, plans, reg=below))["fires"]


def _b10_bars(data):
    bars = dict(data)
    steady = from_closes(np.linspace(100, 160, 303))
    for sym in ("QQQ", "IWM", "DIA"):
        bars[sym] = steady
    bars["SPY"] = from_closes(np.r_[np.linspace(100, 160, 300), 158, 156, 154])
    return bars


def test_b10_extra_triggers_each_alone(cfg, data):
    bars = _b10_bars(data)
    res = sr.shadow_b10(inputs(cfg, bars, {"B": plan("B", 20_000)}))
    assert_result_shape(res, "B-10")
    assert res["detail"]["triggered"] == {"cum_rsi2_35": ["SPY"], "double_7s": ["SPY"]}
    assert {(c["variant"], c["symbol"], c["action"]) for c in res["would_change"]} == {
        ("cum_rsi2_35", "SPY", "enter"), ("double_7s", "SPY", "enter")}


def test_b10_respects_slots_permission_and_holdings(cfg, data):
    bars = _b10_bars(data)
    full = plan("B", 20_000, [Target("QQQ", "B", 1, 90.0), Target("IWM", "B", 1, 90.0)])
    res = sr.shadow_b10(inputs(cfg, bars, {"B": full}))
    assert not res["fires"] and res["detail"]["open_slots"] == 0 and res["detail"]["triggered"]["double_7s"] == ["SPY"]
    res = sr.shadow_b10(inputs(cfg, bars, {"B": plan("B", 20_000)}, reg=regime("bear")))
    assert not res["fires"] and "regime gate" in res["detail"]["note"]
    held = {"B": {"SPY": Lot(1, 150.0, "2026-09-01", 100.0, 100.0)}}
    res = sr.shadow_b10(inputs(cfg, bars, {"B": plan("B", 20_000)}, held))
    assert not res["fires"]


# --- C-10 to C-17 --------------------------------------------------------------------------------------


def _c10_df(last):
    return from_closes(np.r_[np.linspace(100, 150, 296), 160, 158, 152, last])


def test_c10_failed_breakout_exits(cfg, data):
    bars = dict(data)
    bars["NVDA"] = df = _c10_df(148)
    lot = Lot(10, 160.0, str(df.index[-4].date()), 147.0, 147.0)
    plans = {"C": plan("C", 15_000, [Target("NVDA", "C", 10, 147.0, "hold")])}
    res = sr.shadow_c10(inputs(cfg, bars, plans, {"C": {"NVDA": lot}}))
    assert_result_shape(res, "C-10")
    assert res["detail"]["checked"][0]["sessions_held"] == 3
    assert [(c["symbol"], c["action"]) for c in res["would_change"]] == [("NVDA", "exit")]


def test_c10_no_change_above_pivot_after_10_sessions_or_live_exit(cfg, data):
    bars = dict(data)
    bars["NVDA"] = df = _c10_df(155)
    lot = Lot(10, 160.0, str(df.index[-4].date()), 147.0, 147.0)
    hold = {"C": plan("C", 15_000, [Target("NVDA", "C", 10, 147.0, "hold")])}
    assert not sr.shadow_c10(inputs(cfg, bars, hold, {"C": {"NVDA": lot}}))["fires"]
    # sessions 1 to 12 close above the pivot, session 13 below it: too late for C-10
    bars["NVDA"] = df = from_closes(np.r_[np.linspace(100, 150, 280), 160, np.full(12, 158.0), 148])
    old = Lot(10, 160.0, str(df.index[-14].date()), 1.0, 1.0)
    res = sr.shadow_c10(inputs(cfg, bars, hold, {"C": {"NVDA": old}}))
    assert not res["fires"] and res["detail"]["checked"] == [] and "exited_earlier" not in res["detail"]
    bars["NVDA"] = df = _c10_df(148)
    exiting = {"C": plan("C", 15_000, [Target("NVDA", "C", 0.0, 147.0, "closed below 10-day low")])}
    assert not sr.shadow_c10(inputs(cfg, bars, exiting, {"C": {"NVDA": lot}}))["fires"]
    missing = {k: v for k, v in bars.items() if k != "NVDA"}
    res = sr.shadow_c10(inputs(cfg, missing, hold, {"C": {"NVDA": lot}}))
    assert not res["fires"] and res["detail"]["skipped_symbols"] == ["no bars for NVDA"]


def test_c10_exit_is_reported_once_and_remembered_after_a_recovery(cfg, data):
    """Session 2 closes below the pivot (exit), session 3 recovers: the shadow stays out, no second signal."""
    df = from_closes(np.r_[np.linspace(100, 150, 296), 160, 155, 148, 153])
    lot = Lot(10, 160.0, str(df.index[-4].date()), 140.0, 140.0)
    hold = {"C": plan("C", 15_000, [Target("NVDA", "C", 10, 140.0, "hold")])}
    day2 = sr.shadow_c10(inputs(cfg, {"NVDA": df.iloc[:-1]}, hold, {"C": {"NVDA": lot}}))
    assert [c["action"] for c in day2["would_change"]] == ["exit"] and "session 2" in day2["would_change"][0]["why"]
    day3 = sr.shadow_c10(inputs(cfg, {"NVDA": df}, hold, {"C": {"NVDA": lot}}))
    assert not day3["fires"]
    assert day3["detail"]["exited_earlier"] == [{"sleeve": "C", "symbol": "NVDA", "exit_date": str(df.index[-2].date()),
                                                 "why": day2["would_change"][0]["why"]}]


def _c_entry(bars, sym="NVDA", stop_frac=0.92, qty=5.0):
    c = close_of(bars[sym])
    return Target(sym, "C", qty, c * stop_frac, "breakout entry")


def test_c11_extension_skips_entry(cfg, data):
    c = close_of(data["NVDA"])
    t = _c_entry(data)
    far = {"C": plan("C", 15_000, [t], [{"symbol": "NVDA", "pivot": c / 1.06}])}
    res = sr.shadow_c11(inputs(cfg, data, far))
    assert_result_shape(res, "C-11")
    assert res["would_change"][0]["action"] == "skip entry" and res["detail"]["checked"][0]["extension"] == \
        pytest.approx(0.06, abs=1e-3)
    near = {"C": plan("C", 15_000, [t], [{"symbol": "NVDA", "pivot": c / 1.03}])}
    assert not sr.shadow_c11(inputs(cfg, data, near))["fires"]


def test_c11_pivot_from_bars_when_no_candidate(cfg, data):
    bars = dict(data)
    df = data["NVDA"].copy()
    df.iloc[-1, df.columns.get_loc("close")] = df["high"].iloc[-51:-1].max() * 1.10
    bars["NVDA"] = df
    res = sr.shadow_c11(inputs(cfg, bars, {"C": plan("C", 15_000, [_c_entry(bars)])}))
    assert res["fires"] and res["detail"]["checked"][0]["extension"] == pytest.approx(0.10, abs=1e-3)
    held = {"C": {"NVDA": Lot(5, 100.0, "2026-09-01", 90.0, 90.0)}}  # an add, not a new entry
    assert not sr.shadow_c11(inputs(cfg, bars, {"C": plan("C", 15_000, [_c_entry(bars)])}, held))["fires"]


def test_c12_stricter_template(cfg, data):
    bars = dict(data)
    bars["NVDA"] = make_bars(drift=0.0015, vol=0.008, seed=31)
    bars["KO"] = from_closes(100 + np.sin(np.arange(400) / 7.0))
    bars["PG"] = make_bars(n=250, seed=5)
    plans = {"C": plan("C", 15_000, [_c_entry(bars, "NVDA"), _c_entry(bars, "KO"), _c_entry(bars, "PG")])}
    res = sr.shadow_c12(inputs(cfg, bars, plans))
    assert_result_shape(res, "C-12")
    assert [c["symbol"] for c in res["would_change"]] == ["KO"]
    assert "1.30" in res["would_change"][0]["why"] and "84" in res["would_change"][0]["why"]
    assert any("PG" in s for s in res["detail"]["skipped_symbols"])


def _c13_bars(data):
    bars = dict(data)
    df = make_bars(drift=0.0015, vol=0.008, seed=31)
    col = df.columns.get_loc
    df.iloc[-1, col("close")] = df["high"].iloc[-51:-1].max() * 1.03
    df.iloc[-1, col("high")] = df["close"].iloc[-1]
    df.iloc[-1, col("volume")] = df["volume"].iloc[-51:-1].mean() * 3
    bars["NVDA"] = df
    bars["KO"] = make_bars(drift=-0.001, vol=0.008, seed=32)
    bars["SPY"] = make_bars(seed=900, drift=0.0003, vol=0.002)  # steady market: NVDA's RS line is at a high
    return bars


def test_c13_market_relative_rs_adds_and_skips(cfg, data):
    bars = _c13_bars(data)
    plans = {"C": plan("C", 15_000, [_c_entry(bars, "KO")])}  # the live book (hypothetically) buys weak KO
    res = sr.shadow_c13(inputs(cfg, bars, plans))
    assert_result_shape(res, "C-13")
    got = {(c["variant"], c["symbol"], c["action"]) for c in res["would_change"]}
    assert ("weighted_rs", "NVDA", "enter") in got and ("rs_line_near_high", "NVDA", "enter") in got
    assert ("weighted_rs", "KO", "skip entry") in got and ("rs_line_near_high", "KO", "skip entry") in got
    assert "NVDA" in res["detail"]["passing"]["weighted_rs"]


def test_c13_no_adds_when_gated_or_slots_full(cfg, data):
    bars = _c13_bars(data)
    gated = sr.shadow_c13(inputs(cfg, bars, {"C": plan("C", 15_000)}, reg=regime("bear")))
    assert not any(c["action"] == "enter" for c in gated["would_change"])
    held_names = ["JPM", "V", "MA", "LLY", "UNH"]  # five C positions staying: no open slot
    full = plan("C", 15_000, [Target(s, "C", 1.0, 1.0, "hold") for s in held_names])
    lots = {"C": {s: Lot(1.0, 100.0, "2026-06-01", 1.0, 1.0) for s in held_names}}
    res = sr.shadow_c13(inputs(cfg, bars, {"C": full}, lots))
    assert res["detail"]["open_slots"] == 0 and "NVDA" in res["detail"]["passing"]["weighted_rs"]
    assert not res["fires"] and res["detail"]["picks"] == {"rs_line_near_high": [], "weighted_rs": []}
    no_spy = {k: v for k, v in bars.items() if k != "SPY"}
    assert sr.shadow_c13(inputs(cfg, no_spy, {"C": full}))["detail"] == {"skipped": "no bars for SPY"}


def test_c13_variant_entries_obey_the_c9_sector_cap_and_slots(cfg, data):
    """Four semis break out and pass both variants: each variant enters two (C-9 cap), and a live entry the
    variant ranks out is reported as skipped."""
    bars = dict(data)
    semis = ["NVDA", "AVGO", "AMD", "AMAT"]
    col = data["SPY"].columns.get_loc
    for i, sym in enumerate(semis):
        df = make_bars(drift=0.0015, vol=0.008, seed=31 + i)
        df.iloc[-1, col("close")] = df["high"].iloc[-51:-1].max() * 1.03
        df.iloc[-1, col("high")] = df["close"].iloc[-1]
        df.iloc[-1, col("volume")] = df["volume"].iloc[-51:-1].mean() * 3
        bars[sym] = df
    bars["SPY"] = make_bars(seed=900, drift=0.0003, vol=0.002)
    res = sr.shadow_c13(inputs(cfg, bars, {"C": plan("C", 15_000)}))
    assert_result_shape(res, "C-13")
    for name, picks in res["detail"]["picks"].items():
        assert set(semis) <= set(res["detail"]["passing"][name])
        assert len([s for s in picks if s in semis]) == 2
        assert len([c for c in res["would_change"] if c["variant"] == name and c["action"] == "enter"]) == 2
    one_slot = plan("C", 15_000, [Target(s, "C", 1.0, 1.0, "hold") for s in ("JPM", "V", "MA", "LLY")])
    lots = {"C": {s: Lot(1.0, 100.0, "2026-06-01", 1.0, 1.0) for s in ("JPM", "V", "MA", "LLY")}}
    res = sr.shadow_c13(inputs(cfg, bars, {"C": one_slot}, lots))
    assert res["detail"]["open_slots"] == 1 and all(len(p) == 1 for p in res["detail"]["picks"].values())
    pick = res["detail"]["picks"]["weighted_rs"][0]
    other = next(s for s in semis if s != pick)
    one_slot.targets[other] = Target(other, "C", 2.0, 1.0, "breakout entry")  # the live book took another name
    res = sr.shadow_c13(inputs(cfg, bars, {"C": one_slot}, lots))
    rows = {(c["variant"], c["symbol"]): c for c in res["would_change"]}
    skip = rows[("weighted_rs", other)]
    assert skip["action"] == "skip entry" and "ranked out" in skip["why"]
    assert rows[("weighted_rs", pick)]["action"] == "enter"


def _vcp_df():
    """Uptrend, then a 50-session base that tightens with drying volume, then today's breakout."""
    n = 300
    close = np.r_[np.linspace(50, 100, n - 51), np.full(50, 100.0), 104.0]
    df = from_closes(close, spread=0.002)
    hi, lo, vol = df["high"].to_numpy().copy(), df["low"].to_numpy().copy(), df["volume"].to_numpy().copy()
    hi[n - 51:n - 13], lo[n - 51:n - 13], vol[n - 51:n - 13] = 103.0, 97.0, 2e6
    hi[n - 13:n - 1], lo[n - 13:n - 1], vol[n - 13:n - 1] = 100.1, 99.9, 1e6
    hi[-1], lo[-1], vol[-1] = 104.5, 100.0, 3e6
    df["high"], df["low"], df["volume"] = hi, lo, vol
    df["open"] = np.minimum(np.maximum(df["open"], df["low"]), df["high"])
    return df


def test_c14_vcp_proxy(cfg, data):
    bars = dict(data)
    bars["NVDA"] = _vcp_df()
    bars["AMD"] = make_bars(vol=0.03, seed=77)
    plans = {"C": plan("C", 15_000, [_c_entry(bars, "NVDA"), _c_entry(bars, "AMD")])}
    res = sr.shadow_c14(inputs(cfg, bars, plans))
    assert_result_shape(res, "C-14")
    rows = {c["symbol"]: c for c in res["detail"]["checked"]}
    assert rows["NVDA"]["range15"] <= 0.12 and rows["NVDA"]["atr10_atr50"] < 0.8 and rows["NVDA"]["volume_dry"]
    assert [(c["symbol"], c["action"]) for c in res["would_change"]] == [("AMD", "skip entry")]
    assert "range" in res["would_change"][0]["why"]
    assert "before today" in res["detail"]["measured_on"]


def _c14_only(cfg, data, df):
    bars = dict(data)
    bars["NVDA"] = df
    res = sr.shadow_c14(inputs(cfg, bars, {"C": plan("C", 15_000, [_c_entry(bars, "NVDA")])}))
    return res, res["detail"]["checked"][0]


def test_c14_each_condition_fails_on_its_own(cfg, data):
    n = 300
    widening = _vcp_df()  # a tight base whose last 12 sessions widen (98 to 102): volatility expands
    col = widening.columns.get_loc
    widening.iloc[n - 51:n - 13, col("high")], widening.iloc[n - 51:n - 13, col("low")] = 100.1, 99.9
    widening.iloc[n - 13:n - 1, col("high")], widening.iloc[n - 13:n - 1, col("low")] = 102.0, 98.0
    res, row = _c14_only(cfg, data, widening)
    assert row["range15"] <= 0.12 and row["volume_dry"] and row["atr10_atr50"] >= 0.8
    assert res["would_change"][0]["why"] == "no VCP: atr"
    heavy = _vcp_df()  # volume rises into the breakout instead of drying up
    heavy.iloc[n - 13:n - 1, heavy.columns.get_loc("volume")] = 3e6
    res, row = _c14_only(cfg, data, heavy)
    assert row["range15"] <= 0.12 and row["atr10_atr50"] < 0.8 and not row["volume_dry"]
    assert res["would_change"][0]["why"] == "no VCP: volume"


def _c15_df(last):
    return from_closes(np.r_[np.full(280, 98.0), last], spread=0.002)


def test_c15_breakeven_stop_after_2r(cfg, data):
    bars = dict(data)
    bars["NVDA"] = df = _c15_df(111.0)
    lot = Lot(10, 100.0, str(df.index[-20].date()), 96.0, 95.0)  # 1R = 5
    plans = {"C": plan("C", 15_000, [Target("NVDA", "C", 10, 96.0, "hold")])}
    res = sr.shadow_c15(inputs(cfg, bars, plans, {"C": {"NVDA": lot}}))
    assert_result_shape(res, "C-15")
    ch = res["would_change"][0]
    assert ch["action"] == "raise stop" and ch["stop_to"] == 100.0 and ch["stop_from"] < 100.0
    assert res["detail"]["checked"][0]["R_now"] == pytest.approx(2.2)


def test_c15_no_change_below_2r_or_when_ratchet_is_above_entry(cfg, data):
    bars = dict(data)
    bars["NVDA"] = df = _c15_df(105.0)
    lot = Lot(10, 100.0, str(df.index[-20].date()), 96.0, 95.0)
    hold = {"C": plan("C", 15_000, [Target("NVDA", "C", 10, 96.0, "hold")])}
    assert not sr.shadow_c15(inputs(cfg, bars, hold, {"C": {"NVDA": lot}}))["fires"]
    bars["NVDA"] = from_closes(np.r_[np.full(280, 98.0), np.full(12, 111.0)], spread=0.002)
    assert not sr.shadow_c15(inputs(cfg, bars, hold, {"C": {"NVDA": lot}}))["fires"]
    no_r = Lot(10, 100.0, "2026-09-01", None, None)
    res = sr.shadow_c15(inputs(cfg, bars, hold, {"C": {"NVDA": no_r}}))
    assert not res["fires"] and res["detail"]["skipped_symbols"] == ["NVDA: 1R unknown"]


def test_c15_remembers_2r_then_exits_at_breakeven_once(cfg, data):
    """+2R is reached, price pulls back (the raised stop stays), then closes below entry: the shadow exits
    that day and reports it under exited_earlier afterwards."""
    df = from_closes(np.r_[np.full(280, 98.0), 100, 104, 108, 111, 109, 105, 103, 99.5, 101], spread=0.002)
    lot = Lot(10, 100.0, str(df.index[-9].date()), 95.0, 95.0)  # entry on the 100 bar, 1R = 5
    hold = {"C": plan("C", 15_000, [Target("NVDA", "C", 10, 95.0, "hold")])}

    def on(k):  # the result with the bars up to k sessions before the last one
        sub = df.iloc[:len(df) - k]
        return sr.shadow_c15(inputs(cfg, {"NVDA": sub}, hold, {"C": {"NVDA": lot}}))

    pullback = on(4)  # close 109 (+1.8R) after 111 (+2.2R)
    assert pullback["detail"]["checked"][0]["reached_2R_on"] == str(df.index[-6].date())
    assert [(c["action"], c["stop_to"]) for c in pullback["would_change"]] == [("raise stop", 100.0)]
    assert on(3)["would_change"][0]["action"] == "raise stop"  # close 105 (+1R): still raised
    below = on(1)  # close 99.5: the breakeven stop is hit, the live C-7 stop (97.8) holds
    assert [c["action"] for c in below["would_change"]] == ["exit"] and "breakeven" in below["would_change"][0]["why"]
    after = on(0)
    assert not after["fires"] and after["detail"]["exited_earlier"][0]["exit_date"] == str(df.index[-2].date())
    exiting = {"C": plan("C", 15_000, [Target("NVDA", "C", 0.0, 95.0, "breakout stop hit")])}
    assert not sr.shadow_c15(inputs(cfg, {"NVDA": df.iloc[:-1]}, exiting, {"C": {"NVDA": lot}}))["fires"]


def test_c16_exit_when_1r_not_reached_by_session_20(cfg, data):
    bars = dict(data)
    bars["NVDA"] = df = from_closes(np.full(300, 100.0), spread=0.002)
    hold = {"C": plan("C", 15_000, [Target("NVDA", "C", 10, 95.0, "hold")])}
    today = Lot(10, 100.0, str(df.index[-21].date()), 95.0, 95.0)  # today is session 20
    res = sr.shadow_c16(inputs(cfg, bars, hold, {"C": {"NVDA": today}}))
    assert_result_shape(res, "C-16")
    assert res["would_change"][0]["action"] == "exit" and res["detail"]["checked"][0]["sessions_held"] == 20
    assert res["detail"]["checked"][0]["measured_by"] == "high"
    lot = Lot(10, 100.0, str(df.index[-25].date()), 95.0, 95.0)  # session 20 was 4 sessions ago
    res = sr.shadow_c16(inputs(cfg, bars, hold, {"C": {"NVDA": lot}}))
    assert not res["fires"] and res["detail"]["exited_earlier"][0]["exit_date"] == str(df.index[-5].date())
    young = Lot(10, 100.0, str(df.index[-11].date()), 95.0, 95.0)
    assert sr.shadow_c16(inputs(cfg, bars, hold, {"C": {"NVDA": young}}))["detail"]["checked"] == []


def test_c16_judges_only_the_first_20_sessions(cfg, data):
    hold = {"C": plan("C", 15_000, [Target("NVDA", "C", 10, 95.0, "hold")])}
    early = from_closes(np.r_[np.full(280, 100.0), 103, 106, np.full(22, 104.0)], spread=0.002)
    lot = Lot(10, 100.0, str(early.index[-25].date()), 95.0, 95.0)  # +1R (105) on session 2
    res = sr.shadow_c16(inputs(cfg, {"NVDA": early}, hold, {"C": {"NVDA": lot}}))
    assert not res["fires"] and "exited_earlier" not in res["detail"]
    late = from_closes(np.r_[np.full(280, 100.0), np.full(22, 100.5), 106.0, 106.0], spread=0.002)
    lot = Lot(10, 100.0, str(late.index[-25].date()), 95.0, 95.0)  # +1R first on session 23
    late_lot = copy.deepcopy(lot)
    late_lot.max_high = 106.2  # MFE bookkeeping includes the late high: it must not undo the exit
    res = sr.shadow_c16(inputs(cfg, {"NVDA": late}, hold, {"C": {"NVDA": late_lot}}))
    assert not res["fires"] and res["detail"]["exited_earlier"][0]["exit_date"] == str(late.index[-5].date())
    assert res["detail"]["checked"][0]["best_R_by_session_20"] < 1


def test_losing_streak_counts_since_last_winner():
    t = lambda d, r, s="C": {"date": d, "sleeve": s, "R": r, "pnl": r}  # noqa: E731
    trades = [t("2026-01-01", 1.0), t("2026-01-02", -1.0), t("2026-01-03", -0.5), t("2026-01-04", 0.0),
              t("2026-01-05", -1.0), t("2026-01-06", 2.0, "B"), t("2026-01-07", -1.0)]
    assert sr.losing_streak(trades) == 4  # the scratch trade neither counts nor resets; B is ignored
    assert sr.losing_streak(list(reversed(trades))) == 4  # sorted by date
    assert sr.losing_streak([{"date": "2026-01-01", "sleeve": "C", "R": None, "pnl": -5.0}]) == 1
    assert sr.losing_streak([]) == 0


def test_c17_half_risk_after_five_losers(cfg, data):
    losers = [{"date": f"2026-02-0{i}", "sleeve": "C", "R": -1.0, "pnl": -50.0} for i in range(1, 6)]
    state = SimpleNamespace(closed_trades=losers, equity_history=[{"equity": EQUITY}])
    c = close_of(data["NVDA"])
    risk_bound = Target("NVDA", "C", 0.005 * EQUITY / (0.2 * c), 0.8 * c, "breakout entry")
    cap_bound = Target("AMD", "C", 15_000 / 5 / close_of(data["AMD"]), 0.92 * close_of(data["AMD"]), "entry")
    plans = {"C": plan("C", 15_000, [risk_bound, cap_bound])}
    res = sr.shadow_c17(inputs(cfg, data, plans, state=state))
    assert_result_shape(res, "C-17")
    assert res["detail"]["losing_streak"] == 5
    rows = {c.get("symbol"): c for c in res["would_change"]}
    assert rows[None]["action"] == "half risk on new entries"
    assert rows["NVDA"]["qty_to"] == pytest.approx(risk_bound.qty / 2, rel=1e-4) and not rows["NVDA"]["approx"]
    assert "AMD" not in rows  # capped by notional: half the risk still buys the same quantity


def test_c17_halves_exactly_with_a_per_sleeve_1r(cfg, data):
    """risk_pct_by_sleeve.C differs from the default: the live sleeve and the shadow resize from the same 1R,
    so C-17 still halves the live entry exactly."""
    policy = copy.deepcopy(cfg.policy)
    policy["per_trade"]["risk_pct_by_sleeve"]["C"] = 0.0025
    tight = Config(playbook=cfg.playbook, policy=policy)
    bars = _c13_bars(data)
    capital = 100_000  # a wide notional cap, so the entry is sized by risk
    live = strat.sleeve_c(bars, tight.sleeves["C"], capital, {}, policy, EQUITY, 1.0)
    t = live.targets["NVDA"]
    c = close_of(bars["NVDA"])
    assert (c - t.stop) * t.qty == pytest.approx(0.0025 * EQUITY) and t.qty < capital / 5 / c
    losers = [{"date": f"2026-02-0{i}", "sleeve": "C", "R": -1.0} for i in range(1, 6)]
    res = sr.shadow_c17(inputs(tight, bars, {"C": live}, state=SimpleNamespace(closed_trades=losers), equity=EQUITY))
    row = next(r for r in res["would_change"] if r.get("symbol") == "NVDA")
    assert not row["approx"] and row["qty_to"] == pytest.approx(t.qty / 2, rel=1e-4)


def test_c17_quiet_below_five_and_skips_without_state(cfg, data):
    four = [{"date": f"2026-02-0{i}", "sleeve": "C", "R": -1.0} for i in range(1, 5)]
    res = sr.shadow_c17(inputs(cfg, data, state=SimpleNamespace(closed_trades=four)))
    assert not res["fires"] and res["detail"]["losing_streak"] == 4
    assert sr.shadow_c17(inputs(cfg, data))["detail"]["skipped"] == "needs closed trades from the book state"


# --- D-5 -----------------------------------------------------------------------------------------------


def test_d5_skipped_while_sleeve_d_is_off(cfg, data):
    assert sr.shadow_d5(inputs(cfg, data))["detail"]["skipped"] == "sleeve D is off (D-1)"


def test_d5_holds_above_the_low_when_the_live_rule_exits(cfg, data):
    bars = dict(data)
    df = from_closes(np.r_[np.linspace(200, 100, 280), 97, 96, 95, 95.5, 96, 96.5, 97, 98], freq="D")
    assert strat.donchian_score(df, cfg.sleeves["D"]["lookbacks"]) == 0
    bars["BTC/USD"] = df
    lot = Lot(0.1, 95.0, str(df.index[-6].date()), 60.0, 60.0)  # bought at the low, then a small rebound
    plans = {"D": plan("D", 3_000, [Target("BTC/USD", "D", 0.0, 60.0, "donchian score 0")])}
    res = sr.shadow_d5(inputs(cfg, bars, plans, {"D": {"BTC/USD": lot}}))
    assert_result_shape(res, "D-5")
    assert [(c["symbol"], c["action"]) for c in res["would_change"]] == [("BTC/USD", "hold")]
    # a lot bought before the slide was already out under D-5, days before the live exit
    old = Lot(0.1, 120.0, "2026-08-01", 60.0, 60.0)
    res = sr.shadow_d5(inputs(cfg, bars, plans, {"D": {"BTC/USD": old}}))
    assert not res["fires"] and res["detail"]["exited_earlier"][0]["exit_date"] < str(df.index[-6].date())


def test_d5_trailed_stop_ratchets_and_exits_above_the_low(cfg, data):
    """A rally to 200 sets the trail near 193.1; the 196 close would set only ~188.6, but the ratchet keeps
    193.1. A close of 192.8 is below it and above the 20-session low (~192.2): D-5 exits on the stop, once."""
    df = from_closes(np.r_[np.linspace(100, 200, 280), 196, 192.8, 194], freq="D")
    lot = Lot(0.1, 120.0, "2026-06-01", 60.0, 60.0)
    hold = {"D": plan("D", 3_000, [Target("BTC/USD", "D", 0.1, 60.0, "donchian score 1")])}
    trail = df["close"] - 3 * ind.atr(df, 20)
    peak_trail = float(trail.iloc[-4])
    assert float(trail.iloc[-3]) < 192.8 < peak_trail  # yesterday's trail alone would hold
    res = sr.shadow_d5(inputs(cfg, {"BTC/USD": df.iloc[:-1]}, hold, {"D": {"BTC/USD": lot}}))
    row = res["detail"]["checked"][0]
    assert row["low_n"] < 192.8 < row["shadow_stop"] == pytest.approx(peak_trail, abs=0.01)
    assert res["would_change"] == [{"sleeve": "D", "symbol": "BTC/USD", "action": "exit",
                                    "why": f"close at or below the trailed stop {peak_trail:.2f}"}]
    res = sr.shadow_d5(inputs(cfg, {"BTC/USD": df}, hold, {"D": {"BTC/USD": lot}}))
    assert not res["fires"] and res["detail"]["exited_earlier"][0]["exit_date"] == str(df.index[-2].date())


def test_d5_exits_below_the_low_and_trails_the_stop(cfg, data):
    bars = dict(data)
    bars["BTC/USD"] = from_closes(np.r_[np.linspace(100, 200, 280), 150], freq="D")
    lot = Lot(0.1, 120.0, "2026-06-01", 60.0, 60.0)
    hold = {"D": plan("D", 3_000, [Target("BTC/USD", "D", 0.1, 60.0, "donchian score 0.86")])}
    res = sr.shadow_d5(inputs(cfg, bars, hold, {"D": {"BTC/USD": lot}}))
    assert res["would_change"][0]["action"] == "exit"
    bars["BTC/USD"] = df = from_closes(np.linspace(100, 200, 281), freq="D")
    res = sr.shadow_d5(inputs(cfg, bars, hold, {"D": {"BTC/USD": lot}}))
    ch = res["would_change"][0]
    atr = float(ind.atr(df, 20).iloc[-1])
    assert ch["action"] == "raise stop" and ch["stop_to"] == pytest.approx(200 - 3 * atr, rel=1e-4)


# --- EX-6 ----------------------------------------------------------------------------------------------


def test_ex6_limit_price_for_todays_entries(cfg, data):
    plans = {"B": plan("B", 20_000, [_b_entry(data)]), "C": plan("C", 15_000, [_c_entry(data, "NVDA")])}
    res = sr.shadow_ex6(inputs(cfg, data, plans))
    assert_result_shape(res, "EX-6")
    rows = {c["symbol"]: c for c in res["would_change"]}
    for sym in ("SPY", "NVDA"):
        df = data[sym]
        expect = close_of(df) + 0.5 * float(ind.atr(df, 20).iloc[-1])
        assert rows[sym]["action"] == "DAY limit buy" and rows[sym]["limit"] == pytest.approx(expect, abs=1e-3)


def _gapped(df, open_mult, low_mult):
    """Today's bar opens/trades relative to yesterday's EX-6 limit."""
    df = df.copy()
    sig = df.iloc[:-1]
    limit = float(sig["close"].iloc[-1]) + 0.5 * float(ind.atr(sig, 20).iloc[-1])
    col = df.columns.get_loc
    df.iloc[-1, col("open")] = limit * open_mult
    df.iloc[-1, col("low")] = limit * low_mult
    df.iloc[-1, col("high")] = limit * 1.05
    df.iloc[-1, col("close")] = limit * 1.03
    return df, limit


def test_ex6_resolves_yesterdays_entries(cfg, data):
    bars = dict(data)
    df, limit = _gapped(data["NVDA"], 1.02, 1.01)
    bars["NVDA"] = df
    lot = Lot(5, limit * 1.02, str(df.index[-2].date()), 1.0, 1.0)
    res = sr.shadow_ex6(inputs(cfg, bars, {"C": plan("C", 15_000)}, {"C": {"NVDA": lot}}))
    row = res["detail"]["resolved"][0]
    assert row["would_fill"] is False and row["limit"] == pytest.approx(limit, abs=1e-3)
    assert res["would_change"][0]["action"] == "no position"
    bars["NVDA"], limit = _gapped(data["NVDA"], 0.99, 0.98)
    res = sr.shadow_ex6(inputs(cfg, bars, {"C": plan("C", 15_000)}, {"C": {"NVDA": lot}}))
    row = res["detail"]["resolved"][0]
    assert row["would_fill"] and row["limit_fill"] == pytest.approx(limit * 0.99, abs=1e-3) and not res["fires"]
    bars["NVDA"], limit = _gapped(data["NVDA"], 1.01, 0.99)
    row = sr.shadow_ex6(inputs(cfg, bars, {}, {"C": {"NVDA": lot}}))["detail"]["resolved"][0]
    assert row["would_fill"] and row["limit_fill"] == pytest.approx(limit, abs=1e-3)


def test_ex6_ignores_older_lots(cfg, data):
    lot = Lot(5, 100.0, str(data["NVDA"].index[-5].date()), 1.0, 1.0)
    res = sr.shadow_ex6(inputs(cfg, data, {}, {"C": {"NVDA": lot}}))
    assert not res["fires"] and res["detail"]["resolved"] == []


# --- compute: the daily entry point --------------------------------------------------------------------


def _full_day(cfg, data):
    """Real sleeve plans with entries and held lots in B and C, plus a D plan."""
    bars = _credit(dict(data))
    bars["SPY"] = _dip_after_rise()
    bars.update({k: v for k, v in _c13_bars(data).items() if k in ("NVDA", "KO")})
    as_of = bars["SPY"].index[-1]
    reg = regime("bull_calm", temperature=0.9)
    lots = {"B": {"QQQ": Lot(5, float(bars["QQQ"]["close"].iloc[-3]), str(bars["QQQ"].index[-3].date()), 1.0, 1.0)},
            "C": {"AMD": Lot(4, float(bars["AMD"]["close"].iloc[-25]), str(bars["AMD"].index[-25].date()),
                             1.0, float(bars["AMD"]["close"].iloc[-25]) * 0.9)}}
    plans = {
        "A": strat.sleeve_a(bars, cfg.sleeves["A"], 55_000, {}, cfg.policy, as_of),
        "B": strat.sleeve_b(bars, cfg.sleeves["B"], 25_000, lots["B"], cfg.policy, EQUITY, 1.0),
        "C": strat.sleeve_c(bars, cfg.sleeves["C"], 15_000, lots["C"], cfg.policy, EQUITY, 1.0),
        "D": plan("D", 3_000, [Target("BTC/USD", "D", 0.01, 1.0, "donchian")]),
    }
    plans["B"].targets["SPY"] = _b_entry(bars)
    state = SimpleNamespace(closed_trades=[{"date": "2026-01-01", "sleeve": "C", "R": -1.0}] * 5,
                            equity_history=[{"equity": EQUITY}])
    return bars, plans, lots, reg, as_of, state


def test_compute_never_modifies_targets_lots_state_or_bars(cfg, data):
    bars, plans, lots, reg, as_of, state = _full_day(cfg, data)
    targets_before = copy.deepcopy({s: p.targets for s, p in plans.items()})
    lots_before, state_before = copy.deepcopy(lots), copy.deepcopy(state)
    bars_before = {k: v.copy() for k, v in bars.items()}
    res = sr.compute(bars, cfg, plans, lots, reg, as_of, state=state, weights={"B": 0.25, "C": 0.15},
                     equity=EQUITY)
    assert {s: p.targets for s, p in plans.items()} == targets_before
    assert lots == lots_before and state == state_before
    assert all(bars[k].equals(v) for k, v in bars_before.items())
    assert res["REG-5"]["fires"] and res["C-17"]["fires"] and res["A-6"]["fires"]


def test_compute_returns_every_rule_and_attaches_to_plans(cfg, data):
    bars, plans, lots, reg, as_of, state = _full_day(cfg, data)
    res = sr.compute(bars, cfg, plans, lots, reg, as_of, state=state)
    assert list(res) == list(sr.SHADOW_RULES) and len(res) == 20
    for rule_id, r in res.items():
        assert_result_shape(r, rule_id)
    for s, p in plans.items():
        attached = [x["rule"] for x in p.shadow]
        assert attached == [r for r in sr.SHADOW_RULES if s in sr.RULE_SLEEVES[r]]
    assert {"C-10", "C-17", "REG-5", "REG-6", "EX-6"} <= {x["rule"] for x in plans["C"].shadow}
    sizes = {s: len(p.shadow) for s, p in plans.items()}
    sr.compute(bars, cfg, plans, lots, reg, as_of, state=state)
    assert {s: len(p.shadow) for s, p in plans.items()} == sizes  # a second call replaces, never duplicates


def test_compute_with_no_data_never_raises(cfg):
    res = sr.compute({}, cfg, {}, {}, None, AS_OF)
    assert len(res) == 20
    for rule_id, r in res.items():
        assert_result_shape(r, rule_id)
        assert not r["fires"]


def test_compute_with_missing_symbols_and_nan_prices(cfg, data):
    bars, plans, lots, reg, as_of, state = _full_day(cfg, data)
    thin = {k: v for k, v in bars.items() if k not in ("NVDA", "HYG", "VOO", "GLD", "QQQ", "AMD")}
    res = sr.compute(thin, cfg, plans, lots, reg, as_of, state=state)
    for rule_id, r in res.items():
        assert_result_shape(r, rule_id)
    assert "skipped" in res["REG-6"]["detail"] and "skipped" in res["A-6"]["detail"]
    nan_bars = {k: v.copy() for k, v in bars.items()}
    for df in nan_bars.values():
        df.iloc[-1, df.columns.get_loc("close")] = np.nan
    for rule_id, r in sr.compute(nan_bars, cfg, plans, lots, reg, as_of, state=state).items():
        assert_result_shape(r, rule_id)


def test_one_broken_lot_does_not_switch_off_a_rule(cfg, data):
    """A lot with an unparseable date, or one missing fields, is skipped on its own; the healthy NVDA lot is
    still checked (C-10 exit)."""
    bars = dict(data)
    bars["NVDA"] = df = _c10_df(148)
    good = Lot(10, 160.0, str(df.index[-4].date()), 147.0, 147.0)
    hold = {"C": plan("C", 15_000, [Target("NVDA", "C", 10, 147.0, "hold"), Target("AMD", "C", 1, 1.0, "hold"),
                                    Target("MSFT", "C", 1, 1.0, "hold")])}
    lots = {"C": {"AMD": {"qty": 1, "entry_price": 100.0, "entry_date": "not-a-date"}, "MSFT": {"qty": 1},
                  "NVDA": good}}
    res = sr.compute(bars, cfg, hold, lots, regime(), AS_OF)
    for rule_id in ("C-10", "C-13", "C-15", "C-16", "EX-6"):
        assert not str(res[rule_id]["detail"].get("skipped", "")).startswith("error"), rule_id
    assert [(c["symbol"], c["action"]) for c in res["C-10"]["would_change"]] == [("NVDA", "exit")]
    bad = res["C-10"]["detail"]["skipped_symbols"]
    assert any(s.startswith("AMD: unusable lot") for s in bad) and any(s.startswith("MSFT: unusable lot") for s in bad)
    assert not any(c.get("symbol") in ("AMD", "MSFT") and c["action"] == "enter" for c in res["C-13"]["would_change"])


def test_compute_accepts_a_regime_dict_and_empty_lots(cfg, data):
    reg = {"label": "bull_volatile", "permissions": dict(PERMISSIONS["bull_volatile"]), "vol20": 0.2,
           "spy_close": 110.0, "spy_sma200": 100.0, "temperature": None}
    plans = {"B": plan("B", 20_000, [_b_entry(data, perm=0.5)])}
    res = sr.compute(data, cfg, plans, {}, reg, AS_OF, equity=EQUITY)
    assert res["B-9"]["fires"] and res["REG-5"]["detail"]["skipped"] == "temperature unknown"


def test_bars_after_as_of_are_ignored(cfg, data):
    bars = dict(data)
    df = data["NVDA"].copy()
    df.iloc[-1, df.columns.get_loc("close")] = 1e6  # a bar dated after as_of must not be read
    bars["NVDA"] = df
    as_of = df.index[-2]
    c = float(df["close"].iloc[-2])
    plans = {"C": plan("C", 15_000, [Target("NVDA", "C", 5, c * 0.92)], [{"symbol": "NVDA", "pivot": c / 1.02}])}
    inp = sr.ShadowInputs(bars=bars, cfg=cfg, plans=plans, regime=regime(), as_of=as_of)
    res = sr.shadow_c11(inp)
    assert res["detail"]["checked"][0]["close"] == pytest.approx(c, abs=0.01) and not res["fires"]


def test_unexpected_errors_become_skipped_results(cfg, data, monkeypatch):
    def boom(*a, **k):
        raise ValueError("bad input")
    monkeypatch.setattr(sr.ind, "momentum_13612w", boom)
    res = sr.shadow_reg6(inputs(cfg, _credit(data)))
    assert res == {"rule": "REG-6", "fires": False, "detail": {"skipped": "error: ValueError: bad input"},
                   "would_change": []}


def test_shadow_functions_accept_compute_arguments(cfg, data):
    c = close_of(data["NVDA"])
    plans = {"C": plan("C", 15_000, [_c_entry(data)], [{"symbol": "NVDA", "pivot": c / 1.06}])}
    res = sr.shadow_c11(data, cfg, plans, {}, regime(), AS_OF)
    assert res["fires"] and sr.shadow_c11.rule_id == "C-11"


def test_summarize_lists_rules_that_fired(cfg, data):
    bars, plans, lots, reg, as_of, state = _full_day(cfg, data)
    res = sr.compute(bars, cfg, plans, lots, reg, as_of, state=state, weights={"B": 0.25, "C": 0.15})
    lines = sr.summarize(res)
    assert any(line.startswith("REG-5 would: B cap weight") for line in lines)
    assert len(lines) == sum(r["fires"] for r in res.values())
