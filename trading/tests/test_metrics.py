"""Report-only metrics (M-1 to M-11, G-1/G-2/G-4/G-5, RISK-14) with hand-checked numbers."""
import json

import numpy as np
import pandas as pd
import pytest

from trader import metrics
from trader.models import Lot
from trader.state import BookState

ALL6 = ("SPY", "IEF", "EFA", "DBC", "VNQ", "BIL")


def trade(r, date, sleeve="B", **kw):
    return {"sleeve": sleeve, "symbol": "SPY", "date": date, "R": r, "pnl": None if r is None else r * 100, **kw}


def days(n, start="2026-01-05"):
    return [d.date().isoformat() for d in pd.bdate_range(start=start, periods=n)]


def row(date, equity, closes=None, exposure=None, **kw):
    r = {"date": date, "equity": equity, "benchmark": (closes or {}).get("SPY", 0.0)}
    if closes:
        r["closes"] = closes
    if exposure:
        r["exposure"] = exposure
    r.update(kw)
    return r


def json_safe(obj):
    json.dumps(obj, allow_nan=False)
    return True


# --- M-2 ---------------------------------------------------------------------------------------------------

def test_sleeve_stats_hand_checked():
    rs = [2, -1, -1, 0.5, -1, 3]
    mae = [-0.2, -1, -1, -0.5, -1.1, -0.3]
    mfe = [2.5, 0.2, 0.1, 1, 0, 3.5]
    held = [3, 5, 2, 4, 6, 10]
    dates = days(6)
    trades = [trade(r, d, mae_R=a, mfe_R=f, sessions_held=h) for r, d, a, f, h in zip(rs, dates, mae, mfe, held)]
    trades = trades[::-1]  # stored out of order: streaks follow the dates
    trades += [trade(None, "2026-02-02", sleeve="C", sessions_held=4), trade(1.0, "2026-02-02", sleeve="A")]
    st = metrics.sleeve_stats(trades)
    assert set(st) == {"B", "C", "D"}  # A-5: A is not measured in R
    b = st["B"]
    assert b["n"] == 6 and b["win_rate"] == 0.5
    assert b["avg_win_R"] == pytest.approx((2 + 0.5 + 3) / 3, abs=1e-4)
    assert b["avg_loss_R"] == -1.0
    assert b["E"] == pytest.approx(2.5 / 6, abs=1e-4)
    assert b["sd"] == pytest.approx(np.std(rs, ddof=1), abs=1e-4)
    assert b["SQN"] is None and b["SQN_label"] == "t-stat of mean R"  # fewer than 30 lots
    assert b["max_losing_streak"] == 2
    assert b["best_R"] == 3 and b["worst_R"] == -1
    assert b["top5pct_share"] == pytest.approx(3 / 2.5)  # best 1 lot of 6 made 120% of the total R
    assert b["mean_MAE_R"] == pytest.approx(np.mean(mae), abs=1e-4)
    assert b["mean_MFE_R"] == pytest.approx(np.mean(mfe), abs=1e-4)
    assert b["median_hold"] == 4.5 and b["total_pnl"] == pytest.approx(250.0)
    c = st["C"]
    assert c["n"] == 0 and c["n_without_R"] == 1 and c["E"] is None and c["boot_upper"] is None
    assert st["D"]["n"] == 0 and st["D"]["max_losing_streak"] == 0
    assert json_safe(st)


def test_sqn_from_30_lots_and_capped_at_100():
    rs40 = [1.0, -0.5] * 20
    st = metrics.sleeve_stats([trade(r, d) for r, d in zip(rs40, days(40))])
    assert st["B"]["SQN"] == pytest.approx(np.sqrt(40) * np.mean(rs40) / np.std(rs40, ddof=1), abs=1e-3)
    rs150 = [1.0, -0.5] * 75
    assert metrics.sqn(rs150) == pytest.approx(10 * np.mean(rs150) / np.std(rs150, ddof=1))
    assert metrics.sqn([1.0] * 29) is None
    assert metrics.sqn([1.0] * 40) is None  # sd 0


def test_nan_r_is_ignored_and_output_is_json_safe():
    trades = [trade(float("nan"), "2026-01-05"), trade(1.0, "2026-01-06"), trade(float("inf"), "2026-01-07")]
    st = metrics.sleeve_stats(trades)
    assert st["B"]["n"] == 1 and st["B"]["n_without_R"] == 2
    assert json_safe(st)
    assert metrics.sleeve_stats([]) == metrics.sleeve_stats(None)


def test_streak_and_top_share_edges():
    assert metrics.max_losing_streak([]) == 0
    assert metrics.max_losing_streak([-1, -1, 0, -1, -1, -1, 2]) == 3  # a scratch trade breaks the run
    assert metrics.top_share([-1, -2]) is None  # no positive total
    assert metrics.top_share([]) is None
    assert metrics.top_share([1] * 40) == pytest.approx(2 / 40)  # 5% of 40 = 2 lots


# --- M-11 bootstrap and demotion --------------------------------------------------------------------------------

def test_bootstrap_upper():
    assert metrics.bootstrap_upper([]) is None
    assert metrics.bootstrap_upper([0.7]) == 0.7
    assert metrics.bootstrap_upper([0.3] * 10) == pytest.approx(0.3)
    rng = np.random.default_rng(1)
    rs = rng.normal(-0.3, 1.0, 60)
    ub = metrics.bootstrap_upper(rs)
    assert rs.mean() < ub  # an upper bound sits above the sample mean
    assert ub == metrics.bootstrap_upper(rs)  # seeded: the same every day
    assert metrics.bootstrap_upper(rs, q=0.99) > ub
    assert metrics.bootstrap_upper([float("nan"), 1.0, 2.0]) is not None


def test_demotion_half_and_stop(cfg):
    rng = np.random.default_rng(2)
    b = [trade(float(r), d, "B") for r, d in zip(rng.normal(-0.4, 0.5, 30), days(30))]
    c = [trade(float(r), d, "C") for r, d in zip(rng.normal(-0.6, 0.4, 50), days(50))]
    dd = [trade(-1.0, d, "D") for d in days(29)]
    st = metrics.sleeve_stats(b + c + dd, boot_q=cfg.policy["measurement"]["demotion"]["bootstrap_upper_q"])
    assert st["B"]["boot_upper"] < 0 and st["C"]["SQN"] <= -1.0
    assert metrics.demotion(st, cfg.policy) == {"B": "half", "C": "stop"}  # D has only 29 lots
    assert metrics.demotion(st, cfg) == {"B": "half", "C": "stop"}  # a Config works too
    reasons = metrics.demotion_reasons(st, cfg.policy)
    assert "half risk" in reasons["B"] and "new entries stop" in reasons["C"]


def test_demotion_leaves_good_or_small_sleeves(cfg):
    good = [trade(r, d) for r, d in zip([1.0, -0.5] * 30, days(60))]
    st = metrics.sleeve_stats(good)
    assert metrics.demotion(st, cfg.policy) == {}
    assert metrics.demotion({}, cfg.policy) == {}
    assert metrics.demotion({"A": {"n": 500, "SQN": -5, "boot_upper": -1}}, cfg.policy) == {}


# --- M-10 promotion gate ---------------------------------------------------------------------------------------

def test_promotion_gate(cfg):
    rs = [2.0, -1.0] * 50  # E 0.5, SQN about 3.3
    stats = metrics.sleeve_stats([trade(r, d) for r, d in zip(rs, days(100))] +
                                 [trade(1.0, d, "C") for d in days(20)])
    st = BookState(book="rules", equity_history=[row(d, 100000) for d in days(70)])
    gate = metrics.promotion_gate(stats, st, cfg.policy)
    assert gate["B"]["passed"] is True and gate["B"]["checks"]["vs_backtest"] is None
    assert gate["C"]["passed"] is False and gate["C"]["checks"]["closed_lots"] is False
    assert gate["D"]["checks"]["positive_E"] is False
    assert metrics.promotion_gate(stats, st, cfg.policy, backtest_E={"B": 2.0})["B"]["passed"] is False
    assert metrics.promotion_gate(stats, st, cfg.policy, backtest_E={"B": 0.8})["B"]["passed"] is True
    assert metrics.promotion_gate(stats, st, cfg.policy, backtest_E=0.8)["B"]["checks"]["vs_backtest"] is True


def test_promotion_gate_blocks_after_recent_halt(cfg):
    stats = metrics.sleeve_stats([trade(r, d) for r, d in zip([2.0, -1.0] * 50, days(100))])
    eq = [100000] * 10 + [79000] + [90000] * 20
    st = BookState(book="rules", equity_history=[row(d, e) for d, e in zip(days(31), eq)])
    assert metrics.promotion_gate(stats, st, cfg.policy)["B"]["checks"]["no_recent_halt"] is False
    st2 = BookState(book="rules", halted=True)
    assert metrics.promotion_gate(stats, st2, cfg.policy)["B"]["passed"] is False
    st3 = BookState(book="rules", equity_history=[row(d, e) for d, e in zip(days(100), [100000] * 5 + [79000] +
                                                                              [99000] * 94)])
    assert metrics.promotion_gate(stats, st3, cfg.policy)["B"]["checks"]["no_recent_halt"] is True  # > 63 ago


# --- M-1 benchmarks --------------------------------------------------------------------------------------------

def closes(spy, ief=100.0, efa=100.0, dbc=100.0, vnq=100.0, bil=100.0):
    return {"SPY": spy, "IEF": ief, "EFA": efa, "DBC": dbc, "VNQ": vnq, "BIL": bil}


def test_benchmarks_sixty_forty_monthly_rebalance_hand_checked():
    hist = [row("2026-01-29", 1000, closes(100)), row("2026-01-30", 1100, closes(110)),
            row("2026-02-02", 1050, closes(121))]
    bm = metrics.benchmarks(hist)
    # 60/40: 6 SPY + 4 IEF units = 1060 at the January close, rebalanced, then 5.7818 x 121 + 4.24 x 100.
    assert bm["sixty_forty"]["return"] == pytest.approx(0.1236, abs=1e-4)
    assert bm["spy"]["return"] == pytest.approx(0.21)
    assert bm["book"]["return"] == pytest.approx(0.05)
    assert bm["book"]["max_drawdown"] == pytest.approx(1 - 1050 / 1100, abs=1e-4)
    assert bm["gtaa5"]["return"] == pytest.approx((0.2 * 1.21 + 0.8) - 1)
    assert bm["book"]["days"] == 3 and bm["book"]["start"] == "2026-01-29"
    assert json_safe(bm)


def test_benchmarks_gtaa5_annual_rebalance_hand_checked():
    hist = [row("2025-12-30", 1000, closes(100)), row("2025-12-31", 1000, closes(200)),
            row("2026-01-02", 1000, closes(300))]
    # 2 units each; 1200 at year end, rebalanced to 240 each; then 1.2 x 300 + 4 x 240 = 1320.
    assert metrics.benchmarks(hist)["gtaa5"]["return"] == pytest.approx(0.32)


def test_benchmarks_sharpe_vol_with_cash_rate():
    rng = np.random.default_rng(3)
    eq = 100000 * np.cumprod(1 + rng.normal(0.0005, 0.005, 60))
    bil = 100 * np.cumprod(np.full(60, 1.0001))
    ds = days(60)
    hist = [row(d, float(e), closes(400.0, bil=float(b))) for d, e, b in zip(ds, eq, bil)]
    book = metrics.benchmarks(hist)["book"]
    r = pd.Series(eq).pct_change().dropna()
    ex = r - pd.Series(bil).pct_change().dropna()
    assert book["vol"] == pytest.approx(r.std() * np.sqrt(252), abs=1e-4)
    assert book["sharpe"] == pytest.approx(ex.mean() / ex.std() * np.sqrt(252), abs=1e-3)


def test_benchmarks_missing_closes_and_old_rows():
    old = [{"date": "2026-01-05", "equity": 1000, "benchmark": 100.0},
           {"date": "2026-01-06", "equity": 1010, "benchmark": 102.0}]
    bm = metrics.benchmarks(old)
    assert bm["spy"]["return"] == pytest.approx(0.02)  # the old benchmark field is SPY
    assert bm["sixty_forty"] is None and bm["gtaa5"] is None
    empty = metrics.benchmarks([])
    assert {k: empty[k] for k in ("book", "spy", "sixty_forty", "gtaa5")} == {
        "book": None, "spy": None, "sixty_forty": None, "gtaa5": None}
    assert empty["book_same_dates"] == {"spy": None, "sixty_forty": None, "gtaa5": None}
    assert "price returns" in empty["note"]
    assert metrics.benchmarks(old[:1])["book"] is None
    mixed = old + [row("2026-01-07", 1020, closes(104)), row("2026-01-08", 1030, closes(106))]
    bm = metrics.benchmarks(mixed)
    assert bm["sixty_forty"]["start"] == "2026-01-07" and bm["sixty_forty"]["days"] == 2
    nan_row = [row("2026-01-09", float("nan"), closes(float("nan")))]
    assert json_safe(metrics.benchmarks(mixed + nan_row))


# --- M-4 sleeve A ----------------------------------------------------------------------------------------------

def a_history(a_spy=(0, 500, 500, 0, 500, 0), a_total=1000.0, a_cash=None, extra=None):
    spy = [100.0]
    for r in (0.10, -0.10, 0.06, -0.02, 0.08):
        spy.append(spy[-1] * (1 + r))
    out = []
    for i, d in enumerate(days(6)):
        cash = a_total - a_spy[i] if a_cash is None else a_cash
        expo = {"A": a_total, "A_cash": cash, "A_SPY": a_spy[i], **(extra or {})}
        out.append(row(d, 10000, {"SPY": spy[i], "BIL": 100.0}, expo))
    return out


def test_sleeve_a_report_hand_checked():
    rep = metrics.sleeve_a_report(a_history(), top_n=2)
    # Best days: +10% (A out of SPY at the start of the day) and +8% (in SPY) -> 0.5.
    # Worst days: -10% (in SPY) and -2% (out) -> 0.5.
    assert rep["best_days_in_cash"] == 0.5 and rep["worst_days_in_cash"] == 0.5
    assert rep["avg_cash_share"] == pytest.approx(0.75)
    assert rep["days_mostly_cash"] == 1.0 and rep["days"] == 6
    # A = 50% SPY on days 2, 3 and 5: 1 x 0.95 x 1.03 x 1 x 1.04.
    assert rep["return"] == pytest.approx(0.95 * 1.03 * 1.04 - 1, abs=1e-4)
    assert rep["max_drawdown"] == pytest.approx(0.05, abs=1e-4)
    assert rep["gtaa5"] is None  # EFA/IEF/DBC/VNQ closes not stored
    assert "2026" in rep["by_year"] and json_safe(rep)


def test_sleeve_a_return_needs_every_asset():
    rep = metrics.sleeve_a_report(a_history(a_spy=(200,) * 6, a_cash=300.0), top_n=2)
    assert rep["return"] is None and any("every A asset" in n for n in rep["notes"])
    assert rep["best_days_in_cash"] == 0.0  # always holding some SPY


def test_sleeve_a_report_empty_and_missing():
    assert metrics.sleeve_a_report([])["days"] == 0
    rep = metrics.sleeve_a_report([row(d, 1000) for d in days(3)])
    assert rep["avg_cash_share"] is None and rep["notes"]


# --- M-5, M-6, M-7 ---------------------------------------------------------------------------------------------

def test_deviation_attribution_and_monthly_vs_rules():
    claude = BookState(book="claude", deviations=[
        {"date": "2026-02-02", "symbol": "NVDA", "sleeve": "C", "reason_code": "TREND_STRENGTHENING",
         "value_20d": 0.002},
        {"date": "2026-02-03", "symbol": "SPY", "sleeve": "B", "reason_code": "REGIME_RISK", "value_20d": -0.001},
        {"date": "2026-03-02", "symbol": "AMD", "sleeve": "C", "reason_code": "CONCENTRATION", "value_20d": None}])
    claude.equity_history = [row("2026-01-30", 1000, sleeve_cum={"B": 0.0}),
                             row("2026-02-27", 1000, sleeve_cum={"B": 10.0}),
                             row("2026-03-31", 1010, sleeve_cum={"B": 30.0})]
    rules = BookState(book="rules", equity_history=[row("2026-01-30", 1000, sleeve_cum={"B": 0.0}),
                                                    row("2026-02-27", 1000, sleeve_cum={"B": 5.0}),
                                                    row("2026-03-31", 1000, sleeve_cum={"B": 5.0})])
    rep = metrics.deviation_attribution(claude, rules)
    assert rep["n"] == 3 and rep["n_resolved"] == 2
    assert rep["sum_value_20d"] == pytest.approx(0.001) and rep["hit_rate"] == 0.5
    assert rep["by_sleeve"]["C"] == {"n": 1, "sum": 0.002, "hit_rate": 1.0}
    assert rep["by_code"]["REGIME_RISK"]["hit_rate"] == 0.0
    assert rep["monthly_vs_rules"]["2026-02"]["B"] == pytest.approx(0.01 - 0.005)
    assert rep["monthly_vs_rules"]["2026-03"]["B"] == pytest.approx(0.02 - 0.0)
    assert rep["basis"] == "sleeve_cum"
    alone = metrics.deviation_attribution(claude)
    assert alone["monthly_vs_rules"] is None and json_safe(alone)


def test_monthly_sleeve_returns_falls_back_to_realized():
    st = BookState(book="rules", equity_history=[row("2026-01-30", 1000), row("2026-02-27", 1100)],
                   closed_trades=[trade(1.0, "2026-02-10", "C")])
    months, basis = metrics.monthly_sleeve_returns(st)
    assert basis == "realized closed lots only" and months["2026-02"]["C"] == pytest.approx(100 / 1000)
    assert metrics.monthly_sleeve_returns(BookState(book="x")) == ({}, "none")


def test_override_report():
    st = BookState(book="rules", veto_codes_restricted=True, shadow_lots=[
        {"status": "closed", "veto_value": 0.5, "value_usd": 50, "reason_code": "DATA_SUSPECT", "sleeve": "C",
         "date": "2026-02-02"},
        {"status": "closed", "veto_value": -1.0, "value_usd": -100, "reason_code": "SCHEDULED_EVENT",
         "sleeve": "B", "date": "2026-02-03"},
        {"status": "pending_entry", "reason_code": "SCHEDULED_EVENT", "sleeve": "B", "date": "2026-02-04"},
        {"status": "open", "reason_code": "HALT_OR_ILLIQUID", "sleeve": "C", "date": "2026-02-04"}])
    rep = metrics.override_report(st)
    assert rep["n_vetoes"] == 4 and rep["n_scored"] == 2 and rep["n_open"] == 2 and rep["n_pending_entry"] == 1
    assert rep["n_expired"] == 0
    assert rep["sum_value"] == pytest.approx(-0.5) and rep["sum_value_usd"] == pytest.approx(-50)
    assert rep["by_code"]["SCHEDULED_EVENT"]["n_vetoes"] == 2 and rep["by_code"]["SCHEDULED_EVENT"]["n"] == 1
    assert rep["by_code"]["HALT_OR_ILLIQUID"]["n"] == 0
    assert rep["by_sleeve"]["C"]["sum"] == 0.5 and rep["restricted"] is True and rep["hit_rate"] == 0.5
    assert metrics.override_report(BookState(book="rules"))["n_vetoes"] == 0


def test_prediction_scores_minimum_and_calibration():
    preds = [{"probability": 0.15, "outcome": 0, "brier": 0.0225, "brier_ref": 0.04},
             {"probability": 0.15, "outcome": 1, "brier": 0.7225, "brier_ref": 0.64},
             {"probability": 0.75, "outcome": 1, "brier": 0.0625, "brier_ref": 0.25},
             {"probability": 0.95, "outcome": 1, "brier": 0.0025, "brier_ref": None},
             {"probability": 0.5, "outcome": None, "brier": None}]
    hidden = metrics.prediction_scores(preds)
    assert hidden["shown"] is False and hidden["brier"] is None and hidden["n_resolved"] == 4
    assert "50" in hidden["note"]
    s = metrics.prediction_scores(preds, min_resolved=4)
    assert s["brier"] == pytest.approx((0.0225 + 0.7225 + 0.0625 + 0.0025) / 4)
    assert s["n_with_ref"] == 3
    assert s["brier_ref"] == pytest.approx((0.04 + 0.64 + 0.25) / 3)
    assert s["skill"] == pytest.approx(1 - ((0.0225 + 0.7225 + 0.0625) / 3) / ((0.04 + 0.64 + 0.25) / 3), abs=1e-4)
    assert s["calibration"]["0.1-0.2"] == {"n": 2, "mean_prob": 0.15, "hit_rate": 0.5}
    assert s["calibration"]["0.9-1.0"]["n"] == 1
    assert metrics.prediction_scores([], min_resolved=0)["shown"] is True
    assert json_safe(s)


# --- M-8 capture ----------------------------------------------------------------------------------------------

def test_capture_ratios_hand_checked():
    month_ends = [d.date().isoformat() for d in pd.date_range("2025-01-31", periods=12, freq="BME")]
    spy_r = [0.04, -0.02] * 6
    spy, eq = [100.0], [1000.0]
    for r in spy_r:
        spy.append(spy[-1] * (1 + r))
        eq.append(eq[-1] * (1 + r / 2))
    hist = [row(d, e, {"SPY": s}) for d, e, s in zip(["2025-01-02"] + month_ends, eq, spy)]
    cap = metrics.capture_ratios(hist)
    assert cap["months"] == 12
    assert cap["up_capture"] == pytest.approx(0.5, abs=1e-3) and cap["down_capture"] == pytest.approx(0.5, abs=1e-3)
    assert cap["positive_6m"] == 1.0 and cap["positive_12m"] == 1.0
    short = metrics.capture_ratios(hist[:4])
    assert short["positive_6m"] is None and short["up_capture"] is not None
    assert metrics.capture_ratios([])["up_capture"] is None
    assert metrics.capture_ratios([{"date": "2026-01-05", "equity": 1}])["months"] == 0


# --- M-9 API cost ---------------------------------------------------------------------------------------------

def test_api_cost_report():
    ds = days(10)
    st = BookState(book="claude", equity_history=[row(d, 10000 + 100 * i / 9) for i, d in enumerate(ds)],
                   api_cost=[{"date": d, "role": "decide", "mode": "api", "usd": 0.5, "input_tokens": 1000,
                              "output_tokens": 200} for d in ds])
    rep = metrics.api_cost_report(st, 10000)
    assert rep["total_usd"] == 5.0 and rep["calls"] == 10 and rep["input_tokens"] == 10000
    assert rep["annual_usd"] == pytest.approx(5 / 10 * 252)
    assert rep["annual_pct_equity"] == pytest.approx(126 / 10000)
    assert rep["above_ceiling"] is True
    assert rep["return"] == pytest.approx(0.01) and rep["return_net_of_api"] == pytest.approx(0.0095)
    sess = BookState(book="claude", api_cost=[{"date": ds[0], "role": "decide", "mode": "session", "usd": 0.0}])
    rep = metrics.api_cost_report(sess, 100000)
    assert rep["total_usd"] == 0.0 and rep["above_ceiling"] is False and "subscription" in rep["note"]
    assert metrics.api_cost_report(BookState(book="x"), 0)["annual_pct_equity"] is None


# --- G-4 bootstrap and the going-live report --------------------------------------------------------------------

def test_block_bootstrap_p():
    rng = np.random.default_rng(4)
    assert metrics.block_bootstrap_p(0.001 + rng.normal(0, 0.0005, 300)) < 0.01
    noise = rng.normal(0, 0.001, 300)
    assert metrics.block_bootstrap_p(noise - noise.mean()) > 0.3
    assert metrics.block_bootstrap_p([]) is None
    x = rng.normal(0.0002, 0.001, 300)
    assert metrics.block_bootstrap_p(x) == metrics.block_bootstrap_p(x)  # seeded


def live_states(n=300, edge=0.0005):
    rng = np.random.default_rng(5)
    ds = days(n, "2025-01-02")
    spy = 400 * np.cumprod(1 + rng.normal(0.0003, 0.012, n))
    ief = 100 * np.cumprod(1 + rng.normal(0.0001, 0.004, n))
    base = rng.normal(0.0003, 0.002, n)
    rules_eq = 100000 * np.cumprod(1 + base)
    claude_eq = 100000 * np.cumprod(1 + base + edge + rng.normal(0, 0.0005, n))
    rules = BookState(book="rules", equity_history=[row(d, float(e), {"SPY": float(s), "IEF": float(i)})
                                                    for d, e, s, i in zip(ds, rules_eq, spy, ief)])
    claude = BookState(book="claude", equity_history=[row(d, float(e), {"SPY": float(s), "IEF": float(i)})
                                                      for d, e, s, i in zip(ds, claude_eq, spy, ief)])
    claude.deviations = [{"date": ds[10], "value_20d": 0.01}]
    claude.api_cost = [{"date": ds[0], "role": "decide", "mode": "session", "usd": 0.0}]
    rules.shadow_lots = [{"status": "closed", "veto_value": 0.4, "value_usd": 120.0, "date": ds[5]}]
    rules.api_cost = [{"date": ds[0], "role": "review", "mode": "api", "usd": 50.0}]
    return rules, claude


def test_going_live_report_passes_with_edge_and_owner_checks(cfg):
    rules, claude = live_states()
    rep = metrics.going_live_report(rules, claude, cfg.policy, data_problems=[], rehearsed=True)
    g4 = rep["G-4_claude_vs_rules"]
    assert g4["p_value"] < 0.10 and g4["ok"] is True and g4["days"] == 299
    assert g4["value_20d_usd"] == pytest.approx(0.01 * claude.equity_history[10]["equity"], abs=0.01)
    assert g4["rules_review_keeps_claude"] is True  # $120 saved by vetoes > $50 of review cost
    for b in ("rules", "claude"):
        assert rep["books"][b]["G-1_sessions"]["ok"] is True
        assert rep["books"][b]["G-2_beats_60_40"]["ok"] is True
    assert rep["claude_passed"] is True and rep["live_candidate"] == "claude"
    assert json_safe(rep)


def test_going_live_report_unknowns_do_not_pass(cfg):
    rules, claude = live_states()
    rep = metrics.going_live_report(rules, claude, cfg)
    assert rep["books"]["rules"]["G-5_rehearsed"]["ok"] is None
    assert rep["rules_passed"] is False and rep["live_candidate"] is None
    rules.lots = {"B": {"SPY": Lot(qty=1, entry_price=400, entry_date="2025-01-02",
                                   events=[{"date": rules.equity_history[-5]["date"], "kind": "reduce",
                                            "reason": "reconcile: broker had 0.5 fewer"}])}}
    rep = metrics.going_live_report(rules, claude, cfg, data_problems=[], rehearsed=True)
    assert rep["books"]["rules"]["G-5_reconcile"]["ok"] is False
    rep = metrics.going_live_report(rules, claude, cfg, data_problems=["SPY: stale"], rehearsed=True)
    assert rep["books"]["claude"]["G-5_data_clean"]["ok"] is False


def test_going_live_report_short_or_empty_history(cfg):
    rules, claude = live_states(n=40)
    rep = metrics.going_live_report(rules, claude, cfg.policy, data_problems=[], rehearsed=True)
    assert rep["books"]["rules"]["G-1_sessions"] == {"ok": False, "sessions": 40, "need": 252}
    assert rep["G-4_claude_vs_rules"]["p_value"] is None and rep["G-4_claude_vs_rules"]["ok"] is None
    assert rep["claude_passed"] is False
    rep = metrics.going_live_report(BookState(book="rules"), BookState(book="claude"), cfg.policy)
    assert rep["live_candidate"] is None and json_safe(rep)
    later = metrics.going_live_report(rules, claude, cfg.policy, since=rules.equity_history[30]["date"])
    assert later["books"]["rules"]["G-1_sessions"]["sessions"] == 10


def test_going_live_net_of_api_cost(cfg):
    rules, claude = live_states()
    claude.api_cost = [{"date": claude.equity_history[1]["date"], "role": "decide", "usd": 5000.0}]
    rep = metrics.going_live_report(rules, claude, cfg.policy, data_problems=[], rehearsed=True)
    g4 = rep["G-4_claude_vs_rules"]
    assert g4["claude_api_usd"] == 5000.0 and g4["ok"] is False  # the edge does not pay for its cost


# --- RISK-14 stress line -----------------------------------------------------------------------------------------

def test_stress_line_hand_checked(cfg):
    lots = {"A": {"SPY": Lot(qty=100, entry_price=380, entry_date="2026-01-05"),
                  "DBC": Lot(qty=1000, entry_price=19, entry_date="2026-01-05"),
                  "BIL": Lot(qty=100, entry_price=91, entry_date="2026-01-05")},
            "C": {"AAPL": Lot(qty=10, entry_price=190, entry_date="2026-01-05")},
            "D": {"BTC/USD": Lot(qty=0.1, entry_price=50000, entry_date="2026-01-05")},
            "B": {}}
    prices = {"SPY": 400.0, "DBC": 20.0, "BIL": 91.5, "BTC/USD": 60000.0}  # AAPL missing: entry price used
    s = metrics.stress_line(lots, prices, 100000, cfg)
    assert s["notional"] == {"equity_like": 41900.0, "DBC": 20000.0, "crypto": 6000.0}
    loss = 0.2 * 41900 + 0.1 * 20000 + 0.3 * 6000
    assert s["loss_usd"] == pytest.approx(loss) and s["loss_pct"] == pytest.approx(loss / 100000)
    assert "12.2%" in s["text"] or f"{loss / 100000:.1%}" in s["text"]
    flat = metrics.stress_line({"SPY": {"qty": 10, "entry_price": 400}}, {}, 0, cfg)
    assert flat["loss_usd"] == pytest.approx(800) and flat["loss_pct"] is None
    assert metrics.stress_line({}, {}, 100000, cfg)["loss_usd"] == 0.0


# --- M-2 brief ---------------------------------------------------------------------------------------------------

def test_streak_quantiles_exact_and_simulated():
    q = metrics.streak_quantiles(0.40)
    assert q == {0.25: 6, 0.5: 7, 0.75: 9, 0.95: 12}
    rng = np.random.default_rng(6)
    sims = [metrics.max_losing_streak(np.where(rng.random(100) < 0.4, 1, -1)) for _ in range(4000)]
    assert abs(np.median(sims) - q[0.5]) <= 1 and abs(np.quantile(sims, 0.95) - q[0.95]) <= 1
    assert metrics.streak_quantiles(0.35)[0.5] >= q[0.5] >= metrics.streak_quantiles(0.45)[0.5]


def test_losing_streak_table_text():
    t = metrics.losing_streak_table()
    assert "100 independent trades" in t and "35%" in t and "45%" in t and "12 or more" in t
    assert "not evidence the rule broke" in t


# --- review fixes ------------------------------------------------------------------------------------------------

def test_g5_finds_reconcile_events_inside_closed_trades(cfg):
    ds = days(30)
    st = BookState(book="rules", equity_history=[row(d, 100000) for d in ds])
    st.closed_trades = [{"sleeve": "B", "symbol": "SPY", "date": ds[-8], "reason": "RSI2 exit: close above 5-day SMA",
                         "events": [{"date": ds[-10], "kind": "reduce",
                                     "reason": "reconcile: broker holds 5, book expected 10"}]}]
    found = metrics._reconcile_events(st)
    assert len(found) == 1 and found[0]["symbol"] == "SPY" and found[0]["date"] == ds[-10]
    assert metrics._book_checks(st, cfg.policy, None)["G-5_reconcile"]["ok"] is False
    st.closed_trades[0]["events"][0]["explained"] = True
    assert metrics._reconcile_events(st) == []
    # a lot closed by reconcile itself is counted once, not twice
    st.closed_trades = [{"sleeve": "B", "symbol": "SPY", "date": ds[-3], "reason": "reconcile: broker holds 0",
                         "events": [{"date": ds[-3], "kind": "reduce", "reason": "reconcile: broker holds 0"}]},
                        {"sleeve": "C", "symbol": "AAPL", "date": ds[-2], "reason": "reconcile: broker holds 0"}]
    assert len(metrics._reconcile_events(st)) == 2


def test_g5_through_the_ledger(cfg):
    from trader import ledger
    ds = days(30, "2026-03-02")
    st = BookState(book="rules", equity_history=[row(d, 100000.0 + i) for i, d in enumerate(ds)])
    ledger.apply_fill(st, "B", "SPY", 10, 500.0, ds[0], stop=480.0, reason="RSI2 entry")
    ledger.reconcile(st.lots, {"SPY": 5}, [], state=st, prices={"SPY": 501.0}, date=ds[5])
    ledger.apply_fill(st, "B", "SPY", -5, 505.0, ds[8], reason="RSI2 exit: close above 5-day SMA")
    assert not st.lots.get("B") and st.closed_trades[-1]["reason"].startswith("RSI2 exit")
    assert metrics._book_checks(st, cfg.policy, None)["G-5_reconcile"]["ok"] is False


def test_g2_compares_book_and_benchmarks_on_the_same_dates(cfg):
    """Old rows without IEF: the book's early 26% fall must not be judged against a 60/40 that starts later."""
    ds = days(60)
    hist = []
    for i, d in enumerate(ds):
        if i < 30:
            hist.append(row(d, 100000 * (1 - 0.26 * i / 29), benchmark=400.0 + i))  # old rows: SPY only
        else:
            spy = 430.0 * (1 + 0.01 * np.sin(i))
            hist.append(row(d, 74000 * 1.001 ** (i - 29), closes(spy, ief=100 + 0.1 * i, bil=100 + 0.001 * i)))
    bm = metrics.benchmarks(hist)
    assert bm["book"]["max_drawdown"] == pytest.approx(0.26, abs=1e-3) and bm["book"]["days"] == 60
    same = bm["book_same_dates"]["sixty_forty"]
    assert same["start"] == bm["sixty_forty"]["start"] == ds[30] and same["days"] == 30
    assert same["max_drawdown"] == 0.0
    st = BookState(book="rules", equity_history=hist)
    g2 = metrics._book_checks(st, cfg.policy, None)["G-2_beats_60_40"]
    assert g2["window"] == {"start": ds[30], "end": ds[-1], "days": 30}
    assert g2["book_max_dd"] == 0.0 and g2["book_sharpe"] == same["sharpe"]
    spy_same = metrics.perf_stats(pd.Series([h["closes"]["SPY"] for h in hist[30:]]))
    assert g2["spy_max_dd"] == spy_same["max_drawdown"]


def test_promotion_gate_exact_limits(cfg):
    st = BookState(book="rules", equity_history=[row(d, 100000) for d in days(70)])
    ok = {"n": 100, "E": 0.1, "SQN": 2.0}
    assert metrics.promotion_gate({"B": ok}, st, cfg.policy)["B"]["passed"] is True
    assert metrics.promotion_gate({"B": {**ok, "n": 99}}, st, cfg.policy)["B"]["checks"]["closed_lots"] is False
    assert metrics.promotion_gate({"B": {**ok, "SQN": 1.9999}}, st, cfg.policy)["B"]["checks"]["sqn"] is False
    assert metrics.promotion_gate({"B": {**ok, "E": 0.0}}, st, cfg.policy)["B"]["checks"]["positive_E"] is False
    gate = metrics.promotion_gate({"B": ok}, st, cfg.policy, backtest_E=0.2)["B"]
    assert gate["checks"]["vs_backtest"] is True  # exactly 0.5 x backtest
    # SQN of exactly 2.0 from real trades: mean 0.2, sd 1 over 100 lots
    rs = [0.2 + np.sqrt(0.99), 0.2 - np.sqrt(0.99)] * 50
    stats = metrics.sleeve_stats([trade(float(r), d) for r, d in zip(rs, days(100))])
    assert stats["B"]["SQN"] == 2.0 and metrics.promotion_gate(stats, st, cfg.policy)["B"]["passed"] is True


def test_halt_window_is_exactly_63_sessions(cfg):
    ok = {"B": {"n": 100, "E": 0.1, "SQN": 2.5}}
    for halt_at, expect in ((100 - 63, False), (100 - 64, True)):
        hist = [row(d, 100000, halted=(i == halt_at)) for i, d in enumerate(days(100))]
        st = BookState(book="rules", equity_history=hist)
        assert metrics.promotion_gate(ok, st, cfg.policy)["B"]["checks"]["no_recent_halt"] is expect


def test_halt_flags_respect_the_owner_reset(cfg):
    ok = {"B": {"n": 100, "E": 0.1, "SQN": 2.5}}
    eq = [100000] * 100 + [78000] * 200
    flags = [False] * 100 + [True] * 5 + [False] * 195  # halted, then the owner reset the peak
    st = BookState(book="rules", peak_equity=78000,
                   equity_history=[row(d, e, halted=f) for d, e, f in zip(days(300), eq, flags)])
    assert metrics.promotion_gate(ok, st, cfg.policy)["B"]["checks"]["no_recent_halt"] is True
    old = BookState(book="rules", equity_history=[row(d, e) for d, e in zip(days(300), eq)])
    assert metrics.promotion_gate(ok, old, cfg.policy)["B"]["checks"]["no_recent_halt"] is False  # no flags: cautious


def test_blocked_sleeve_does_not_pass_promotion(cfg):
    ok = {"B": {"n": 100, "E": 0.1, "SQN": 2.5}, "C": {"n": 100, "E": 0.1, "SQN": 2.5}}
    st = BookState(book="rules", sleeve_blocked={"B": "RISK-13: sleeve 5% below its peak"})
    gate = metrics.promotion_gate(ok, st, cfg.policy)
    assert gate["B"]["passed"] is False and gate["B"]["checks"]["not_blocked"] is False
    assert gate["B"]["detail"]["blocked"].startswith("RISK-13") and gate["C"]["passed"] is True


def test_demotion_trusts_only_a_bound_at_the_policy_quantile(cfg):
    base = {"n": 30, "SQN": None, "boot_upper": -0.01}
    assert metrics.demotion({"B": {**base, "boot_q": 0.90}}, cfg.policy) == {"B": "half"}
    assert metrics.demotion({"B": {**base, "boot_q": 0.95}}, cfg.policy) == {"B": "half"}  # stricter: still proves it
    assert metrics.demotion({"B": {**base, "boot_q": 0.80}}, cfg.policy) == {}  # looser bound proves nothing
    assert metrics.demotion({"B": base}, cfg.policy) == {"B": "half"}  # no quantile stored: taken as given
    trades = [trade(r, d) for r, d in zip([1.0, -0.5] * 20, days(40))]
    assert metrics.sleeve_stats(trades, policy=cfg.policy)["B"]["boot_q"] == 0.9
    pol = {"measurement": {"demotion": {**cfg.policy["measurement"]["demotion"], "bootstrap_upper_q": 0.95}}}
    st95 = metrics.sleeve_stats(trades, policy=pol)["B"]
    assert st95["boot_q"] == 0.95 and st95["boot_upper"] == metrics.sleeve_stats(trades, boot_q=0.95)["B"]["boot_upper"]


def test_sleeve_stats_since_counts_lots_entered_after_the_fixes():
    trades = [trade(1.0, "2026-03-10", entry_date="2026-02-20"), trade(-1.0, "2026-03-11", entry_date="2026-03-02"),
              trade(0.5, "2026-03-12")]
    st = metrics.sleeve_stats(trades, since="2026-03-01")
    assert st["B"]["n"] == 2 and st["B"]["E"] == pytest.approx(-0.25)
    assert metrics.sleeve_stats(trades)["B"]["n"] == 3


def test_sleeve_a_gtaa5_with_the_engine_exposure_keys():
    """The engine records {A, B, C, D, A_cash, A_SPY}: A's own return is unknown, GTAA-5 is still shown."""
    ds = days(30)
    hist = [row(d, 100000, closes(100 + 10 * i / 29), {"A": 55000, "B": 20000, "C": 10000, "D": 0,
                                                        "A_cash": 11000, "A_SPY": 22000}) for i, d in enumerate(ds)]
    rep = metrics.sleeve_a_report(hist, top_n=2)
    assert rep["return"] is None and any("every A asset" in n for n in rep["notes"])
    assert rep["gtaa5"]["return"] == pytest.approx(0.2 * 0.10) and rep["gtaa5"]["max_drawdown"] == 0.0
    assert rep["gtaa5"]["start"] == ds[0] and rep["avg_cash_share"] == pytest.approx(0.2)
    assert json_safe(rep)


def test_going_live_since_filters_every_sum(cfg):
    rules, claude = live_states()
    ds = [h["date"] for h in rules.equity_history]
    claude.api_cost = [{"date": ds[1], "role": "decide", "usd": 5000.0}]
    rules.api_cost = [{"date": ds[0], "role": "review", "usd": 50.0}, {"date": ds[40], "role": "review", "usd": 2.0}]
    rep = metrics.going_live_report(rules, claude, cfg.policy, since=ds[30], data_problems=[], rehearsed=True)
    g4 = rep["G-4_claude_vs_rules"]
    assert g4["claude_api_usd"] == 0.0 and g4["review_api_usd"] == 2.0
    assert g4["value_20d_usd"] == 0.0 and g4["veto_value_usd"] == 0.0  # both dated before `since`
    assert rep["books"]["claude"]["api_cost_usd"] == 0.0 and rep["since"] == ds[30]
    net = metrics._net_equity(claude, ds[30])
    assert net.iloc[0] == pytest.approx(claude.equity_history[30]["equity"])  # the old cost is not subtracted


def test_api_cost_report_tolerates_missing_mode_and_role():
    st = BookState(book="claude", api_cost=[{"usd": 0, "mode": None, "role": None}, {"usd": 0, "mode": "session"}])
    rep = metrics.api_cost_report(st, 100000)
    assert rep["modes"] == ["api", "session"] and set(rep["by_role"]) == {"?"}


def test_deviation_attribution_flags_the_realized_fallback():
    claude = BookState(book="claude", equity_history=[row("2026-01-30", 1000), row("2026-02-27", 1000)])
    rules = BookState(book="rules", equity_history=[row("2026-01-30", 1000), row("2026-02-27", 1000)])
    rep = metrics.deviation_attribution(claude, rules)
    assert rep["basis"] == "realized closed lots only" and "open positions are missing" in rep["note"]
