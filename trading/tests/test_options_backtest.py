"""OPT-37 options backtester (RPL method): synthetic closes and volatility, no network."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from trader.options import backtest as bt
from trader.options import pricing


def series(n=560, drift=0.0004, vol=0.01, seed=3, start=400.0, end="2026-09-25"):
    idx = pd.bdate_range(end=end, periods=n)
    rng = np.random.default_rng(seed)
    closes = pd.Series(start * np.exp(np.cumsum(rng.normal(drift, vol, n))), index=idx)
    vix = pd.Series(18.0, index=idx)
    return closes, vix


@pytest.fixture(scope="module")
def data():
    return series()


def test_clean_series_drops_bad_values_and_timezones():
    idx = pd.DatetimeIndex(["2026-01-05 16:00", "2026-01-05 16:00", "2026-01-06 16:00", "2026-01-07 16:00",
                            "2026-01-08 16:00"]).tz_localize("America/New_York")
    s = bt.clean_series(pd.Series([1.0, 2.0, float("nan"), -3.0, 4.0], index=idx))
    assert list(s) == [2.0, 4.0] and s.index.tz is None and s.index[0] == pd.Timestamp("2026-01-05")
    assert bt.clean_series(None).empty and bt.clean_series(pd.Series(dtype=float)).empty


def test_monthly_expiry_moves_to_thursday_on_a_holiday():
    sessions = pd.bdate_range("2025-04-01", "2025-04-30").drop(pd.Timestamp("2025-04-18"))  # Good Friday
    assert bt.monthly_expiry(2025, 4, sessions) == pd.Timestamp("2025-04-17")
    assert bt.monthly_expiry(2025, 5, sessions) == pd.Timestamp("2025-05-16")  # beyond the data: third Friday


def test_leg_spread_is_rpl_share_with_a_cent_floor():
    assert bt.leg_spread(4.0) == pytest.approx(0.10)
    assert bt.leg_spread(0.1) == 0.01 and bt.leg_spread(-1.0) == 0.01
    assert bt.leg_spread(4.0, 2.0) == pytest.approx(0.20)


def test_choose_short_is_nearest_020_inside_the_band():
    table = pricing.default_skew_table()
    k, q = bt.choose_short(660.0, 35, 0.18, bt.Params(), table, 0.04)
    assert 0.15 <= abs(q["delta"]) <= 0.25 and k == int(k) and k < 660
    lower = pricing.model_quote(660, k - 1, 35, 0.18, "put", table, rate=0.04)["delta"]
    upper = pricing.model_quote(660, k + 1, 35, 0.18, "put", table, rate=0.04)["delta"]
    assert abs(abs(q["delta"]) - 0.2) <= min(abs(abs(lower) - 0.2), abs(abs(upper) - 0.2)) + 1e-12
    assert bt.choose_short(660.0, 35, 0.18, bt.Params(delta_band=(0.9, 0.95)), table, 0.04) is None


def test_width_share_of_spot_or_fixed_dollars():
    assert bt.spread_width(500.0, bt.Params(width_usd=2.0)) == 2.0
    assert bt.spread_width(500.0, bt.Params(width_pct=0.01)) == 5.0
    assert bt.spread_width(50.0, bt.Params(width_pct=0.01)) == 1.0  # never below one strike step


def test_replay_trades_are_consistent(data):
    closes, vix = data
    r = bt.replay(closes, vix, bt.Params(width_usd=2.0), rates=pd.Series(0.04, index=closes.index))
    assert r["trades"] and r["stats"]["n"] == len(r["trades"])
    for t in r["trades"]:
        assert t["max_loss"] == pytest.approx((t["width"] - t["entry_credit"]) * 100)
        assert t["pnl"] == pytest.approx((t["entry_credit"] - t["exit_debit"]) * 100 - 4 * 0.04)
        assert t["R"] == pytest.approx(t["pnl"] / t["max_loss"])
        assert 30 <= (pd.Timestamp(t["expiry"]) - pd.Timestamp(t["entry_date"])).days <= 36
        assert t["exit_reason"] in ("OPT-22", "OPT-23")
        if t["exit_reason"] == "OPT-22":
            assert (pd.Timestamp(t["expiry"]) - pd.Timestamp(t["date"])).days <= 7
        assert t["tags"]["bil_rate"] == 0.04


def test_short_strike_exit_on_a_crash():
    closes, vix = series(n=300, drift=0.0, vol=0.0001)
    exp = bt.monthly_expiry(2026, 8, closes.index)
    crash_day = closes.index[closes.index.get_indexer([exp - pd.Timedelta(days=20)], method="bfill")[0]]
    closes[closes.index >= crash_day] *= 0.85
    r = bt.replay(closes, vix, bt.Params(width_usd=2.0))
    t = [x for x in r["trades"] if x["expiry"] == exp.date().isoformat()][0]
    assert t["exit_reason"] == "OPT-23" and t["date"] == crash_day.date().isoformat() and t["R"] < -0.5


def test_doubled_costs_are_worse(data):
    closes, vix = data
    base = bt.replay(closes, vix, bt.Params(width_usd=2.0))["stats"]["E"]
    dbl = bt.replay(closes, vix, bt.Params(width_usd=2.0, cost_mult=2.0))["stats"]["E"]
    assert dbl < base


def test_edge_cases_empty_short_nan():
    assert bt.replay(pd.Series(dtype=float), pd.Series(dtype=float))["problems"] == ["no closes"]
    closes, vix = series(n=40)
    r = bt.replay(closes, vix * np.nan)
    assert r["trades"] == [] and any(s["skipped"] == "no volatility input" for s in r["skipped"])
    r = bt.replay(closes, vix, bt.Params(regime_filter=True))  # too little history for REG-2 -> no entry
    assert r["trades"] == [] and all(s["skipped"] in ("OPT-19 regime", "still open at the end of the data",
                                                      "no session in the entry window") for s in r["skipped"])


def test_cost_filter_blocks_most_small_spreads(data):
    closes, vix = data
    r = bt.replay(closes, vix, bt.Params(width_usd=2.0, cost_filter=0.20))
    assert any(s["skipped"] == "OPT-13 cost filter" for s in r["skipped"])


def test_put_crosscheck_signs_and_missing_years():
    trades = [{"date": "2018-05-18", "R": 0.1}, {"date": "2018-12-21", "R": -0.5}]
    idx = pd.to_datetime(["2017-12-29", "2018-12-31", "2019-12-31", "2020-12-31"])
    put = pd.Series([100.0, 94.0, 110.0, 112.0], index=idx)
    out = bt.put_crosscheck(trades, put)
    assert out["2018"]["put_return"] == pytest.approx(-0.06) and out["2018"]["signs_agree"] is True
    assert out["2020"]["strategy_sum_R"] is None and out["2020"]["signs_agree"] is None
    assert out["2008"]["put_return"] is None
    assert bt.put_crosscheck(trades, None)["2018"]["put_return"] is None
    # finding #19: a year before the closes start says why, instead of a bare "no trades"
    early = bt.put_crosscheck(trades, put, first_close="2016-01-04")
    assert "pre-2016 closes from another source" in early["2008"]["note"]
    assert early["2020"]["note"].startswith("no trades that year")


def test_summary_labels_the_runs_and_counts_no_credit_skips(data):
    """Finding #19: the report says the base includes OPT-23, which run the rulebook's RPL figure is, and how
    many cycles doubled costs dropped (its n is a different sample)."""
    closes, vix = data
    rep = bt.full_report(closes, vix, width_usd=2.0)
    for name in ("base", "doubled_costs", "hold7_no_opt23"):
        assert sum(rep[name]["skipped_reasons"].values()) == rep[name]["n_skipped"]
        assert rep[name]["n_no_credit"] == rep[name]["skipped_reasons"].get(bt.NO_CREDIT, 0)
    text = "\n".join(bt.summary_lines(rep))
    assert "OPT-23 short-strike exit" in text and "rulebook's RPL" in text
    assert "n differs from base" in text
    if rep["doubled_costs"]["n_no_credit"]:
        assert f"{rep['doubled_costs']['n_no_credit']} cycles skipped: no positive credit" in text
    rep["doubled_costs"]["n_no_credit"] = 36
    assert "36 cycles skipped: no positive credit after costs" in "\n".join(bt.summary_lines(rep))


def test_full_report_prints_every_required_run(data, tmp_path):
    closes, vix = data
    rep = bt.full_report(closes, vix, width_usd=2.0)
    for k in ("base", "fixed_dollars", "doubled_costs", "flat_vol", "realised_vol", "opt19_regime", "opt13_filter",
              "sensitivity", "put_crosscheck", "bil_E", "width_pct_of_last_spot"):
        assert k in rep
    assert rep["fixed_dollars"]["avg_width_usd"] == pytest.approx(2.0)
    assert rep["width_pct_of_last_spot"] == pytest.approx(2.0 / float(closes.iloc[-1]))
    assert len(rep["sensitivity"]) == 8
    lines = bt.summary_lines(rep)
    assert any("doubled_costs" in l for l in lines) and any("PUT 2008" in l for l in lines)
    path = bt.save_report(rep, tmp_path)
    assert json.loads(path.read_text())["width_usd"] == 2.0


def test_main_with_injected_data_saves_for_the_opt40_gate(data, tmp_path, capsys):
    closes, vix = data
    assert bt.main(["--start", str(closes.index[0].date()), "--width-usd", "2"], closes=closes, vix=vix,
                   rates=pd.Series(0.04, index=closes.index), put_index=pd.Series(dtype=float),
                   state_dir=tmp_path) == 0
    assert "OPT-37 backtest SPY" in capsys.readouterr().out
    saved = json.loads((tmp_path / "options" / "backtest" / "latest.json").read_text())
    assert saved["width_usd"] == 2.0 and "base" in saved


def test_main_reports_missing_inputs(monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("no keys")
    monkeypatch.setattr(bt, "_load_inputs", boom)
    assert bt.main([]) == 2 and "cannot load backtest inputs" in capsys.readouterr().out


def test_realised_vol_is_annualised():
    idx = pd.bdate_range("2026-01-01", periods=60)
    s = pd.Series(100 * np.exp(np.cumsum(np.tile([0.01, -0.01], 30))), index=idx)
    assert bt.realised_vol(s).iloc[-1] == pytest.approx(0.01 * np.sqrt(252) * np.sqrt(20 / 19), rel=1e-6)
