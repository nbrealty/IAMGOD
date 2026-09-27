"""Rulebook risk rules in trader/risk.py: RISK-2..13, B-4, B-5, C-7, C-9, CL-14, EX-3, M-11 inputs.

Bars are synthetic and deterministic. `flat(100)` has high 101, low 99 and ATR20 2, so the rule stops are
C 96 (max(100 - 2*2, 92)) and B/D 94 (100 - 3*2), and the prior 10-session low is 99.
"""
import copy
import json
import math

import numpy as np
import pandas as pd
import pytest

from trader import strategies
from trader.config import Config
from trader.models import Lot, Target
from trader.risk import (Breakers, RiskEngine, bars_through, breaker_status, last_prices, last_valid_closes,
                         loss_inputs, month_worst_pnl, period_start_equity, sessions_held, sleeve_drawdown,
                         sleeves_to_latch, trail_low, week_worst_pnl)

E = 100_000.0
END = "2026-09-25"


# --- helpers -------------------------------------------------------------------------------------


def frame(closes, spread=0.01, end=END):
    closes = np.asarray(closes, dtype=float)
    idx = pd.date_range(end=end, periods=len(closes), freq="B")
    open_ = np.r_[closes[0], closes[:-1]]
    return pd.DataFrame({"open": open_, "high": np.maximum(closes, open_) * (1 + spread),
                         "low": np.minimum(closes, open_) * (1 - spread), "close": closes,
                         "volume": np.full(len(closes), 1e6)}, index=idx)


def flat(price=100.0, n=260):
    return frame([price] * n)


def bars_for(*symbols, price=100.0):
    return {s: flat(price) for s in symbols}


RECENT = flat().index[-2].date().isoformat()  # one session held
OLD = "2026-01-02"


def calm(cfg, equity=E, peak=E, **kw):
    return breaker_status(cfg, equity, peak, 0.0, 0.0, False, False, **kw)


def tweak(cfg, changes: dict) -> Config:
    """A copy of cfg with dotted keys changed, e.g. {"policy.turnover.max_orders_per_day": 2}."""
    roots = {"playbook": copy.deepcopy(cfg.playbook), "policy": copy.deepcopy(cfg.policy)}
    for path, value in changes.items():
        root, *keys = path.split(".")
        d = roots[root]
        for k in keys[:-1]:
            d = d[k]
        d[keys[-1]] = value
    return Config(playbook=roots["playbook"], policy=roots["policy"])


def run(cfg, proposed, lots=None, broker=None, bars=None, equity=E, breakers=None, **kw):
    lots = lots or {}
    if broker is None:
        broker = {}
        for held in lots.values():
            for sym, lot in held.items():
                broker[sym] = broker.get(sym, 0.0) + lot.qty
    return RiskEngine(cfg).apply(proposed, lots, broker, bars or {}, equity, breakers or calm(cfg), **kw)


def target(res, sleeve, symbol):
    found = [t for t in res.targets if t.sleeve == sleeve and t.symbol == symbol]
    return found[0] if found else None


def orders_by_symbol(res):
    return {o.symbol: o for o in res.orders}


def logged(res, text):
    return any(text in line for line in res.log)


# --- Breakers and breaker_status ---------------------------------------------------------------


def test_breakers_old_positional_construction_gets_safe_defaults():
    b = Breakers(0.0, False, False, 1.0, 0.0, 0.0, [])
    assert b.watch is False and b.monthly_block is False
    assert b.sleeve_risk_mult == {"B": 1.0, "C": 1.0, "D": 1.0}
    assert b.day_pnl_pct == b.week_pnl_pct == b.month_pnl_pct == 0.0
    json.dumps(b.to_dict())


def test_breaker_status_old_call_and_percent_fields(cfg):
    b = breaker_status(cfg, 10000, 10000, -50, -100, False, False)
    assert b.day_pnl_R == pytest.approx(-1.0) and b.week_pnl_R == pytest.approx(-2.0)
    assert b.day_pnl_pct == pytest.approx(-0.005) and b.week_pnl_pct == pytest.approx(-0.01)
    assert not b.no_new_entries and not b.watch and not b.monthly_block


def test_daily_and_weekly_loss_in_percent_of_equity(cfg):  # RISK-11
    assert breaker_status(cfg, E, E, -1000, 0, False, False).no_new_entries
    assert not breaker_status(cfg, E, E, -990, 0, False, False).no_new_entries
    b = breaker_status(cfg, E, E, 0, -2500, False, False)
    assert b.no_new_entries and any("weekly loss -2.50% of equity" in r for r in b.reasons)
    assert any("daily loss -1.00% of equity" in r for r in breaker_status(cfg, E, E, -1000, 0, False, False).reasons)


def test_drawdown_tiers(cfg):  # RISK-9
    assert breaker_status(cfg, 90_000, E, 0, 0, False, False).risk_mult == 0.5
    b = breaker_status(cfg, 85_000, E, 0, 0, False, False)
    assert b.no_new_entries and not b.halted
    assert breaker_status(cfg, 80_000, E, 0, 0, False, False).halted


@pytest.mark.parametrize("peak", [10_000, 12_345.67, 1_000_003.0])
def test_exact_thresholds_trip_despite_float_noise(cfg, peak):
    assert breaker_status(cfg, peak * 0.9, peak, 0, 0, False, False).risk_mult == 0.5
    assert breaker_status(cfg, peak * 0.8, peak, 0, 0, False, False).halted
    assert breaker_status(cfg, peak * 0.95, peak, 0, 0, False, False).watch
    assert breaker_status(cfg, peak, peak, -0.01 * peak, 0, False, False).no_new_entries


def test_watch_tier_flags_without_blocking(cfg):  # RISK-10
    b = breaker_status(cfg, 95_000, E, 0, 0, False, False)
    assert b.watch and not b.no_new_entries and b.risk_mult == 1.0
    assert any("watch tier" in r and "5.0%" in r for r in b.reasons)
    assert not breaker_status(cfg, 95_100, E, 0, 0, False, False).watch


def test_monthly_cap(cfg):  # RISK-12
    b = calm(cfg, month_pnl=-4000, month_base=E)
    assert b.monthly_block and b.month_pnl_pct == pytest.approx(-0.04)
    assert not b.no_new_entries  # A is exempt, so this is not a book-wide block
    assert any("A is exempt" in r and "-4.00%" in r for r in b.reasons)
    assert not calm(cfg, month_pnl=-3999, month_base=E).monthly_block


def test_monthly_cap_holds_for_the_rest_of_the_month(cfg):  # RISK-12 latch
    b = calm(cfg, month_pnl=-1000, month_base=E, month_worst_pnl=-4500)
    assert b.monthly_block and any("earlier this month" in r for r in b.reasons)
    assert not calm(cfg, month_pnl=-1000, month_base=E, month_worst_pnl=-3000).monthly_block


def test_month_worst_pnl_helper():
    hist = [{"date": "2026-08-31", "equity": 100_000}, {"date": "2026-09-10", "equity": 95_000},
            {"date": "2026-09-20", "equity": 99_000}, {"date": "2026-09-30", "equity": 90_000}]
    assert month_worst_pnl(hist, "2026-09-25", 100_000) == -5000  # rows after the date are ignored
    assert month_worst_pnl(hist, "2026-09-25", None) == -5000  # base from the prior month-end row
    assert month_worst_pnl([], "2026-09-25", 100_000) is None
    assert month_worst_pnl([{"date": "bad", "equity": 1}, {"date": "2026-09-02", "equity": None}],
                           "2026-09-25") is None


def test_first_month_has_a_monthly_cap(cfg):  # RISK-12 with no prior month-end stored
    hist = [{"date": "2026-09-01", "equity": 100_000}, {"date": "2026-09-14", "equity": 95_500},
            {"date": "2026-09-25", "equity": 96_500}]
    assert period_start_equity(hist, "2026-09-25", "M") == 100_000
    kw = loss_inputs(hist, "2026-09-25", 96_500)
    assert kw["month_base"] == 100_000 and kw["month_pnl"] == -3500 and kw["month_worst_pnl"] == -4500
    b = breaker_status(cfg, 96_500, E, 0.0, 0.0, False, False, **kw)
    assert b.monthly_block and any("earlier this month" in r for r in b.reasons)
    assert loss_inputs([], "2026-09-25", E) == {"month_pnl": 0.0, "month_base": None,
                                                "month_worst_pnl": None, "week_worst_pnl": None}


def test_weekly_loss_block_holds_for_the_rest_of_the_week(cfg):  # RISK-11
    b = calm(cfg, week_worst_pnl=-3000)
    assert b.no_new_entries and any("earlier this week" in r for r in b.reasons)
    assert not calm(cfg, week_worst_pnl=-2000).no_new_entries
    # Monday 2026-09-21 closed at -3%, Tuesday recovered to -2%: still blocked on Tuesday.
    hist = [{"date": "2026-09-18", "equity": 100_000}, {"date": "2026-09-21", "equity": 97_000},
            {"date": "2026-09-22", "equity": 98_000}]
    assert week_worst_pnl(hist, "2026-09-22") == -3000
    kw = loss_inputs(hist, "2026-09-22", 98_000)
    b = breaker_status(cfg, 98_000, E, 0.0, -2000, False, False, **kw)
    assert b.no_new_entries and any("rest of the week" in r for r in b.reasons)
    assert week_worst_pnl(hist, "2026-09-28") is None  # a new week starts clean


def test_monthly_cap_without_stored_month_end(cfg):
    assert calm(cfg, equity=95_000, peak=95_000, month_pnl=-5000, month_base=None).monthly_block
    assert not calm(cfg, month_pnl=0.0, month_base=None).monthly_block


def test_sleeve_tiers(cfg):  # RISK-13
    b = calm(cfg, sleeve_pnl={"C": {"cum": -3000, "peak": 0}, "B": {"cum": 1000, "peak": 6000}})
    assert b.sleeve_risk_mult == {"B": 0.0, "C": 0.5, "D": 1.0}
    assert b.sleeve_dd_pct["C"] == pytest.approx(0.03) and b.sleeve_dd_pct["B"] == pytest.approx(0.05)
    assert "3.0% of equity" in b.sleeve_reasons["C"] and "half risk" in b.sleeve_reasons["C"]
    assert "until the owner reviews" in b.sleeve_reasons["B"]
    assert "D" not in b.sleeve_reasons
    assert not b.no_new_entries  # sleeve tiers never block the whole book


def test_sleeve_drawdown_edge_cases():
    assert sleeve_drawdown({"cum": -3500}, E) == pytest.approx(0.035)  # sleeve P&L starts at 0
    assert sleeve_drawdown({"cum": 500, "peak": 100}, E) == 0.0  # stale peak
    assert sleeve_drawdown({"cum": float("nan"), "peak": None}, E) == 0.0
    assert sleeve_drawdown(None, E) == 0.0
    assert sleeve_drawdown({"cum": -5000, "peak": 0}, 0) == 0.0


def test_sleeve_blocked_and_demotion(cfg):  # RISK-13 latch and M-11
    b = calm(cfg, sleeve_blocked={"C": "owner review pending"}, demotion={"B": "half", "D": "stop"})
    assert b.sleeve_risk_mult == {"B": 0.5, "C": 0.0, "D": 0.0}
    assert "owner review pending" in b.sleeve_reasons["C"] and "M-11" in b.sleeve_reasons["B"]
    both = calm(cfg, sleeve_pnl={"C": {"cum": -3000, "peak": 0}}, demotion={"C": "stop"})
    assert both.sleeve_risk_mult["C"] == 0.0  # the strictest tier wins
    assert calm(cfg, demotion={"C": "something new"}).sleeve_risk_mult["C"] == 0.0


def test_sleeves_to_latch(cfg):
    latch = sleeves_to_latch(cfg, E, {"C": {"cum": -5000, "peak": 0}, "B": {"cum": -4000, "peak": 0}})
    assert set(latch) == {"C"} and "RISK-13" in latch["C"]
    assert sleeves_to_latch(cfg, E, None) == {}


def test_breakers_with_bad_equity_do_not_crash(cfg):
    b = breaker_status(cfg, float("nan"), E, float("nan"), None, False, False)
    assert b.no_new_entries and any("equity is zero or unknown" in r for r in b.reasons)
    assert breaker_status(cfg, 0.0, E, 0, 0, False, False).halted  # a real 100% drawdown
    assert breaker_status(cfg, 0.0, 0.0, 0, 0, False, False).no_new_entries


@pytest.mark.parametrize("peak", [float("nan"), None, 0.0, -5.0, "junk"])
def test_bad_peak_blocks_new_entries_instead_of_hiding_drawdown(cfg, peak):  # RISK-9, RISK-10
    b = breaker_status(cfg, 70_000, peak, 0, 0, False, False)
    assert b.no_new_entries and not b.halted
    assert any("high-water mark is zero or unknown" in r for r in b.reasons)
    assert not breaker_status(cfg, 70_000, 70_000, 0, 0, False, False).no_new_entries


# --- step 0-1: exits in both books ---------------------------------------------------------------


def test_c_ratchet_raises_stop_and_persists_without_proposals():  # C-7, RISK-4
    from trader.config import load_config
    cfg = load_config()
    bars = {"MSFT": frame(np.linspace(100, 130, 260))}
    low10 = trail_low(bars["MSFT"], 10)
    assert 100 < low10 < 130
    lots = {"C": {"MSFT": Lot(10, 100, OLD, 100.0, 100.0)}}
    res = run(cfg, [], lots, bars=bars, book="claude")
    t = target(res, "C", "MSFT")
    assert t.qty == 10 and t.stop == pytest.approx(low10)
    assert res.orders == [] and logged(res, "C-7")
    assert lots["C"]["MSFT"].stop == 100.0  # the input lot is untouched; the ledger persists the target


def test_c_ratchet_never_lowers(cfg):
    lots = {"C": {"MSFT": Lot(10, 90, OLD, 99.5, 96)}}
    res = run(cfg, [Target("MSFT", "C", 10, 50.0, "hold")], lots, bars=bars_for("MSFT"))
    assert target(res, "C", "MSFT").stop == 99.5


def test_c_ratchet_exit_enforced_in_claude_book(cfg):
    bars = {"NVDA": frame([100.0] * 259 + [95.0])}  # prior 10 lows are 99; today closes at 95
    lots = {"C": {"NVDA": Lot(10, 90, OLD, 85.0, 85.0)}}
    res = run(cfg, [Target("NVDA", "C", 10, 50.0, "claude hold")], lots, bars=bars, book="claude")
    t = target(res, "C", "NVDA")
    assert t.qty == 0 and t.reason == "stop hit (enforced)" and t.stop == pytest.approx(99.0)
    assert [(o.symbol, o.side, o.qty) for o in res.orders] == [("NVDA", "sell", 10)]


def test_ratchet_only_for_c_and_short_history(cfg):
    lots = {"B": {"SPY": Lot(10, 95, RECENT, 90.0, 90.0)}}
    res = run(cfg, [], lots, bars=bars_for("SPY"))
    assert target(res, "B", "SPY").stop == 90.0  # B's disaster stop is never trailed (B-4)
    assert trail_low(flat(n=1), 10) is None and trail_low(None, 10) is None
    assert trail_low(flat(n=5), 10) == pytest.approx(99.0)
    df = flat()
    df.iloc[-5, df.columns.get_loc("low")] = np.nan
    assert trail_low(df, 10) == pytest.approx(99.0)


def test_b_time_stop_enforced_in_both_books(cfg):  # B-4(b)
    idx = flat().index
    for book in ("rules", "claude"):
        lots = {"B": {"QQQ": Lot(10, 95, idx[-11].date().isoformat(), 90.0, 90.0)}}
        res = run(cfg, [Target("QQQ", "B", 10, 90.0, "hold")], lots, bars=bars_for("QQQ"), book=book)
        t = target(res, "B", "QQQ")
        assert t.qty == 0 and t.reason == "time stop (enforced)"
        assert [(o.symbol, o.side) for o in res.orders] == [("QQQ", "sell")]
    lots = {"B": {"QQQ": Lot(10, 95, idx[-10].date().isoformat(), 90.0, 90.0)}}  # 9 sessions held
    res = run(cfg, [], lots, bars=bars_for("QQQ"))
    assert target(res, "B", "QQQ").qty == 10 and res.orders == []


def test_time_stop_with_bad_entry_date_is_logged_not_crashed(cfg):
    lots = {"B": {"QQQ": Lot(10, 95, "not a date", 90.0, 90.0)}}
    res = run(cfg, [], lots, bars=bars_for("QQQ"))
    assert target(res, "B", "QQQ").qty == 10 and logged(res, "cannot count sessions held")


def test_sessions_held_helper():
    df = flat(n=20)
    assert sessions_held(df, df.index[-4].date().isoformat()) == 3
    assert sessions_held(df, None) is None and sessions_held(None, "2026-09-01") is None
    tz = df.tz_localize("America/New_York")
    assert sessions_held(tz, df.index[-4].date().isoformat()) == 3


def test_held_lot_without_stop_gets_the_rule_stop(cfg):  # RISK-3
    lots = {"B": {"SPY": Lot(10, 95, RECENT)}}
    res = run(cfg, [], lots, bars=bars_for("SPY"))
    assert target(res, "B", "SPY").stop == pytest.approx(94.0)


def test_held_lot_without_stop_uses_the_stop_from_its_entry_date(cfg):  # RISK-3, B-4(c)
    df = frame([100.0] * 250 + list(np.linspace(100, 93, 10)))
    entry = df.index[-9].date().isoformat()
    at_entry = strategies.rule_stop("B", bars_through(df, entry), cfg.policy)
    assert at_entry > strategies.rule_stop("B", df, cfg.policy)  # today's lower close would loosen it
    res = run(cfg, [], {"B": {"SPY": Lot(10, 100, entry)}}, bars={"SPY": df})
    t = target(res, "B", "SPY")
    assert t.stop == pytest.approx(at_entry) and t.qty == 0 and t.reason == "stop hit (enforced)"
    assert logged(res, "entry date") and [(o.symbol, o.side) for o in res.orders] == [("SPY", "sell")]
    res = run(cfg, [], {"C": {"AAPL": Lot(10, 100, OLD)}}, bars={})
    assert target(res, "C", "AAPL").stop is None and logged(res, "no rule stop can be computed")
    assert bars_through(df, "not a date") is None and len(bars_through(df, entry)) == 252


def test_nan_last_close_means_no_price(cfg):
    df = flat()
    df.iloc[-1, df.columns.get_loc("close")] = np.nan
    assert "AAPL" not in last_prices({"AAPL": df, "EMPTY": df.iloc[:0]})
    assert last_valid_closes({"AAPL": df, "EMPTY": df.iloc[:0]}) == {"AAPL": 100.0}
    lots = {"C": {"AAPL": Lot(10, 90, OLD, 200.0, 200.0)}}  # a stop above any price, but no close today
    res = run(cfg, [], lots, bars={"AAPL": df})
    assert res.orders == [] and logged(res, "no valid close today")


def _no_close_today(price=100.0):
    df = flat(price)
    df.iloc[-1, df.columns.get_loc("close")] = np.nan
    return df


@pytest.mark.parametrize("book", ["rules", "claude"])
def test_reductions_pass_without_a_valid_close_today(cfg, book):  # "reductions always allowed", EX-7
    lots = {"C": {"AAPL": Lot(10, 90, OLD, 50.0, 50.0)}}
    res = run(cfg, [Target("AAPL", "C", 0, None, "exit")], lots, bars={"AAPL": _no_close_today()}, book=book)
    assert target(res, "C", "AAPL").qty == 0
    assert [(o.symbol, o.side, o.qty, o.price) for o in res.orders] == [("AAPL", "sell", 10, 100.0)]
    assert logged(res, "last valid close 100.00")
    res = run(cfg, [Target("MSFT", "C", 10, None, "entry")], bars={"MSFT": _no_close_today()}, book=book)
    assert res.orders == [] and logged(res, "increase rejected, no valid close today")


def test_no_buy_is_sent_without_a_valid_close_today(cfg):
    lots = {"C": {"AAPL": Lot(10, 90, OLD, 50.0, 50.0)}}  # the broker holds less than the lot
    res = run(cfg, [], lots, broker={"AAPL": 5}, bars={"AAPL": _no_close_today()})
    assert res.orders == [] and logged(res, "no valid close today, order to go from 5 to 10 not sent")


def test_time_stop_without_a_valid_close_today(cfg):  # B-4(b)
    df = _no_close_today()
    lots = {"B": {"QQQ": Lot(10, 95, df.index[-15].date().isoformat(), 90.0, 90.0)}}
    res = run(cfg, [], lots, bars={"QQQ": df})
    assert target(res, "B", "QQQ").reason == "time stop (enforced)"
    assert [(o.symbol, o.side, o.qty, o.price) for o in res.orders] == [("QQQ", "sell", 10, 100.0)]
    assert logged(res, "sent at the last valid close 100.00")
    df["close"] = np.nan  # no usable close at all: the exit cannot be priced, so it is not claimed
    res = run(cfg, [], lots, bars={"QQQ": df})
    t = target(res, "B", "QQQ")
    assert t.qty == 10 and t.reason == "unchanged" and res.orders == [] and logged(res, "exit deferred")


# --- step 2: increases -------------------------------------------------------------------------


def test_cl14_stop_floor_in_the_claude_book(cfg):
    bars = bars_for("MSFT")
    res = run(cfg, [Target("MSFT", "C", 50, 90.0, "entry")], bars=bars, book="claude")
    assert target(res, "C", "MSFT").stop == pytest.approx(96.0) and logged(res, "CL-14")
    res = run(cfg, [Target("MSFT", "C", 50, 98.0, "entry")], bars=bars, book="claude")
    assert target(res, "C", "MSFT").stop == 98.0  # tighter is allowed
    res = run(cfg, [Target("MSFT", "C", 50, 90.0, "entry")], bars=bars, book="rules")
    assert target(res, "C", "MSFT").stop == 90.0  # the rules book's stops are the rule stops already


def test_cl14_floor_on_an_add_raises_the_lot_stop(cfg):
    lots = {"B": {"SPY": Lot(10, 95, RECENT, 80.0, 80.0)}}
    res = run(cfg, [Target("SPY", "B", 20, 85.0, "add")], lots, bars=bars_for("SPY"), book="claude")
    t = target(res, "B", "SPY")
    assert t.qty == 20 and t.stop == pytest.approx(94.0)


@pytest.mark.parametrize("stop", [None, 0.0, -5.0, float("nan"), 100.0, 120.0])
def test_missing_or_invalid_stop_becomes_the_rule_stop(cfg, stop):
    for book in ("rules", "claude"):
        res = run(cfg, [Target("MSFT", "C", 50, stop, "entry")], bars=bars_for("MSFT"), book=book)
        assert target(res, "C", "MSFT").stop == pytest.approx(96.0)


@pytest.mark.parametrize("book", ["rules", "claude"])
@pytest.mark.parametrize("bad_stop", [100.0, 150.0, 1e9, None])
def test_add_with_a_bad_stop_never_lowers_the_held_stop(cfg, book, bad_stop):  # RISK-3, C-7
    lots = {"C": {"MSFT": Lot(10, 90, OLD, 99.0, 96.0)}, "B": {"SPY": Lot(10, 95, RECENT, 97.0, 97.0)}}
    res = run(cfg, [Target("MSFT", "C", 20, bad_stop, "add"), Target("SPY", "B", 20, bad_stop, "add")], lots,
              bars=bars_for("MSFT", "SPY"), book=book)
    c, b = target(res, "C", "MSFT"), target(res, "B", "SPY")
    assert c.qty == 20 and c.stop == pytest.approx(99.0)  # not the 96 rule stop
    assert b.qty == 20 and b.stop == pytest.approx(97.0)  # not the 94 rule stop


def test_uncheckable_stop_is_rejected_in_the_claude_book(cfg):
    bars = {"MSFT": flat(n=5)}  # too short for ATR20, so no rule stop
    res = run(cfg, [Target("MSFT", "C", 50, 90.0, "entry")], bars=bars, book="claude")
    assert target(res, "C", "MSFT") is None and res.orders == [] and logged(res, "rule stop cannot be computed")
    res = run(cfg, [Target("MSFT", "C", 50, None, "entry")], bars=bars, book="rules")
    assert target(res, "C", "MSFT") is None and logged(res, "no valid stop")


def test_per_sleeve_risk_and_hard_cap(cfg):  # RISK-2
    low = tweak(cfg, {"policy.per_trade.risk_pct_by_sleeve.C": 0.0025})
    res = run(low, [Target("MSFT", "C", 1000, 98.0, "entry")], bars=bars_for("MSFT"))
    t = target(res, "C", "MSFT")
    assert (100 - t.stop) * t.qty <= 0.0025 * E + 1e-6 and logged(res, "(0.25% of equity)")
    high = tweak(cfg, {"policy.per_trade.risk_pct_by_sleeve.C": 0.5})
    res = run(high, [Target("MSFT", "C", 5000, 98.0, "entry")], bars=bars_for("MSFT"))
    assert logged(res, "(2.00% of equity)")  # never above risk_pct_hard_cap


def test_sleeve_tier_halves_or_blocks_new_entries(cfg):  # RISK-13, M-11
    half = calm(cfg, sleeve_pnl={"C": {"cum": -3000, "peak": 0}})
    res = run(cfg, [Target("MSFT", "C", 1000, 98.0, "entry")], bars=bars_for("MSFT"), breakers=half)
    assert logged(res, "(0.25% of equity)")
    off = calm(cfg, sleeve_pnl={"C": {"cum": -5000, "peak": 0}})
    res = run(cfg, [Target("MSFT", "C", 10, 98.0, "entry")], bars=bars_for("MSFT"), breakers=off)
    assert res.orders == [] and logged(res, "new entries stopped")
    demoted = calm(cfg, demotion={"C": "stop"})
    assert run(cfg, [Target("MSFT", "C", 10, 98.0, "e")], bars=bars_for("MSFT"), breakers=demoted).orders == []
    # the other sleeves are unaffected
    res = run(cfg, [Target("QQQ", "B", 10, None, "entry")], bars=bars_for("QQQ"), breakers=off)
    assert [o.symbol for o in res.orders] == ["QQQ"]


def test_regime_permission_scales_and_blocks(cfg):
    bars = bars_for("MSFT")
    res = run(cfg, [Target("MSFT", "C", 1000, 98.0, "e")], bars=bars, permissions={"A": 1, "C": 0.5})
    assert logged(res, "(0.25% of equity)")
    res = run(cfg, [Target("MSFT", "C", 1000, 98.0, "e")], bars=bars, permissions={"C": 0.0})
    assert res.orders == [] and logged(res, "regime permission for sleeve C is 0")
    res = run(cfg, [Target("MSFT", "C", 1000, 98.0, "e")], bars=bars, permissions={"C": 2.0})
    assert logged(res, "(0.50% of equity)")  # a permission can never scale risk up
    res = run(cfg, [Target("MSFT", "C", 1000, 98.0, "e")], bars=bars, permissions={"C": float("nan")})
    assert res.orders == []


def test_all_risk_multipliers_combine(cfg):  # RISK-2 x RISK-9 x RISK-13 x REG-3
    eq = 90_000.0
    b = breaker_status(cfg, eq, E, 0, 0, False, False, sleeve_pnl={"C": {"cum": -3000, "peak": 0}})
    assert b.risk_mult == 0.5 and b.sleeve_risk_mult["C"] == 0.5 and not b.no_new_entries
    res = run(cfg, [Target("MSFT", "C", 1000, 98.0, "e")], bars=bars_for("MSFT"), equity=eq, breakers=b,
              permissions={"C": 0.5})
    t = target(res, "C", "MSFT")
    assert (100 - t.stop) * t.qty == pytest.approx(0.005 * 0.5 * 0.5 * 0.5 * eq)
    assert logged(res, "(0.06% of equity)")


def test_symbols_must_belong_to_the_proposing_sleeve(cfg):  # CL-11 backstop
    blocked = calm(cfg, month_pnl=-6000, month_base=E, sleeve_blocked={"C": "owner review"})
    res = run(cfg, [Target("NVDA", "C", 50, None, "e"), Target("NVDA", "A", 100, None, "relabelled")],
              bars=bars_for("NVDA"), breakers=blocked, book="claude")
    assert res.orders == [] and target(res, "A", "NVDA") is None
    assert logged(res, "NVDA is not in sleeve A's universe")
    lots = {"C": {"NVDA": Lot(20, 100, OLD, 96.0, 96.0), "AMD": Lot(20, 100, OLD, 96.0, 96.0)}}
    res = run(cfg, [Target("AVGO", "B", 50, None, "relabelled"), Target("MSFT", "B", 5, None, "x"),
                    Target("QQQ", "C", 5, None, "x"), Target("BIL", "A", 10, None, "cash")],
              lots, bars=bars_for("NVDA", "AMD", "AVGO", "MSFT", "QQQ", "BIL"))
    assert [(o.symbol, o.side) for o in res.orders] == [("BIL", "buy")]
    for sym, sleeve in (("AVGO", "B"), ("MSFT", "B"), ("QQQ", "C")):
        assert logged(res, f"{sym} is not in sleeve {sleeve}'s universe")
    # a lot already held under the wrong label may still be sold
    res = run(cfg, [Target("NVDA", "A", 0, None, "exit")], {"A": {"NVDA": Lot(5, 100, OLD)}}, bars=bars_for("NVDA"))
    assert [(o.symbol, o.side) for o in res.orders] == [("NVDA", "sell")]


def test_monthly_block_stops_b_c_d_but_not_a(cfg):  # RISK-12
    b = calm(cfg, month_pnl=-5000, month_base=E)
    bars = bars_for("MSFT", "SPY", "QQQ")
    res = run(cfg, [Target("MSFT", "C", 10, None, "e"), Target("QQQ", "B", 10, None, "e"),
                    Target("SPY", "A", 50, None, "faber")], bars=bars, breakers=b)
    assert [o.symbol for o in res.orders] == ["SPY"]
    assert logged(res, "RISK-12")


def test_watch_tier_does_not_block_the_risk_engine(cfg):  # RISK-10 is enforced on weights, not here
    b = breaker_status(cfg, 94_000, E, 0, 0, False, False)
    res = run(cfg, [Target("MSFT", "C", 10, None, "e")], bars=bars_for("MSFT"), equity=94_000, breakers=b)
    assert [o.symbol for o in res.orders] == ["MSFT"]


def test_no_new_entries_blocks_sleeve_a_too(cfg):
    b = breaker_status(cfg, E, E, 0, 0, False, True)
    res = run(cfg, [Target("SPY", "A", 50, None, "faber")], bars=bars_for("SPY"), breakers=b)
    assert res.orders == [] and logged(res, "kill switch")


def test_sleeve_a_increase_scaled_by_drawdown(cfg):  # RISK-9
    b = breaker_status(cfg, 88_000, E, 0, 0, False, False)
    res = run(cfg, [Target("SPY", "A", 100, None, "faber")], bars=bars_for("SPY"), equity=88_000, breakers=b)
    assert target(res, "A", "SPY").qty == pytest.approx(50)


def test_disabled_sleeve_rejects_increases(cfg):  # D-1 backstop
    res = run(cfg, [Target("SPY", "D", 10, None, "odd")], bars=bars_for("SPY"))
    assert res.orders == [] and logged(res, "sleeve D is disabled")


def test_no_averaging_down(cfg):  # RISK-3
    lots = {"C": {"MSFT": Lot(10, 110, OLD, 80.0, 80.0)}}
    res = run(cfg, [Target("MSFT", "C", 20, None, "add")], lots, bars=bars_for("MSFT"))
    assert target(res, "C", "MSFT").qty == 10 and logged(res, "no averaging down")


# --- step 3: portfolio caps --------------------------------------------------------------------


def _mixed_book():
    return {
        "A": {"SPY": Lot(300, 100, OLD)},
        "B": {"QQQ": Lot(200, 100, RECENT, 94.0, 94.0)},
        "C": {"AAPL": Lot(90, 100, OLD, 96.0, 96.0), "MSFT": Lot(60, 100, OLD, 96.0, 96.0)},
    }


def test_equity_like_cap(cfg):  # RISK-6
    bars = bars_for("SPY", "QQQ", "AAPL", "MSFT", "VNQ", "IEF")
    res = run(cfg, [Target("VNQ", "A", 200, None, "faber"), Target("IEF", "A", 200, None, "faber")],
              _mixed_book(), bars=bars)
    assert target(res, "A", "VNQ").qty == pytest.approx(100)  # 75% - 65% held = 10% of equity
    assert target(res, "A", "IEF").qty == pytest.approx(200)  # bonds are not equity-like
    assert logged(res, "equity-like cap (RISK-6)")


def test_b_index_cluster_heat(cfg):  # B-5
    one_r_qty = 0.005 * E / 6  # B stop 94 on a price of 100
    lots = {"B": {"SPY": Lot(one_r_qty, 100, RECENT, 94.0, 94.0)}, "A": {"SPY": Lot(100, 100, OLD)}}
    bars = bars_for("SPY", "QQQ", "IWM")
    res = run(cfg, [Target("QQQ", "B", one_r_qty, 94.0, "rsi2")], lots, bars=bars)
    t = target(res, "B", "QQQ")
    assert (100 - 94) * t.qty == pytest.approx(0.0025 * E)  # 0.75% cluster budget - 0.5% already used
    assert logged(res, "cluster heat (B-5)")
    lots["B"]["QQQ"] = Lot(t.qty, 100, RECENT, 94.0, 94.0)
    res = run(cfg, [Target("IWM", "B", 10, 94.0, "rsi2")], lots, bars=bars)
    assert target(res, "B", "IWM") is None  # the budget is spent


def test_open_risk_heat_cap(cfg):  # RISK-5
    # B lot: 116 sh, 50 risk/share = 5.8% heat on 11.6% notional. The 6% budget leaves 0.2% = 200.
    # The new C stock gets rule stop 96, so 4 risk/share -> 50 shares, under the notional, sleeve and cash caps.
    lots = {"B": {"SPY": Lot(116, 100, RECENT, 50.0, 50.0)}}
    res = run(cfg, [Target("LLY", "C", 80, None, "breakout")], lots, bars=bars_for("SPY", "LLY"))
    t = target(res, "C", "LLY")
    assert t.qty == pytest.approx(50) and (100 - 96) * t.qty == pytest.approx(0.002 * E)
    assert logged(res, "6% open-risk heat")


def test_correlated_stock_limit(cfg):  # RISK-5
    rng = np.random.default_rng(0)
    base = rng.normal(0, 0.01, 260)
    corr = lambda: frame(100 * np.exp(np.cumsum(base + rng.normal(0, 0.001, 260))))  # noqa: E731
    bars = {"AAPL": corr(), "MSFT": corr(), "NVDA": corr(),
            "XOM": frame(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 260))))}
    lots = {"C": {"AAPL": Lot(10, 100, OLD, 90.0, 90.0), "MSFT": Lot(10, 100, OLD, 90.0, 90.0)}}
    res = run(cfg, [Target("NVDA", "C", 10, None, "breakout"), Target("XOM", "C", 10, None, "breakout")],
              lots, bars=bars)
    assert target(res, "C", "NVDA") is None and logged(res, "held stocks with 60d correlation > 0.7")
    assert target(res, "C", "XOM") is not None


def test_sector_cap(cfg):  # C-9
    lots = {"C": {"NVDA": Lot(20, 100, OLD, 96.0, 96.0), "AMD": Lot(20, 100, OLD, 96.0, 96.0)}}
    bars = bars_for("NVDA", "AMD", "AVGO", "MSFT")
    res = run(cfg, [Target("AVGO", "C", 50, None, "breakout"), Target("MSFT", "C", 50, None, "breakout")],
              lots, bars=bars)
    assert target(res, "C", "AVGO") is None and logged(res, "sector group 'semis_ai' (C-9 max 2)")
    assert target(res, "C", "MSFT").qty == 50
    res = run(cfg, [Target("NVDA", "C", 0, None, "exit"), Target("AVGO", "C", 50, None, "breakout")],
              lots, bars=bars)
    assert target(res, "C", "AVGO").qty == 50  # exits are processed first and free the slot


def test_sector_cap_still_allows_adds_to_a_held_name(cfg):  # C-9 limits new positions only
    lots = {"C": {"NVDA": Lot(20, 100, OLD, 96.0, 96.0), "AMD": Lot(20, 100, OLD, 96.0, 96.0)}}
    res = run(cfg, [Target("NVDA", "C", 30, None, "add")], lots, bars=bars_for("NVDA", "AMD"))
    assert target(res, "C", "NVDA").qty == 30 and not logged(res, "C-9")


def test_equity_like_cap_when_already_over_it(cfg):  # RISK-6 clips new money, never cuts holdings
    lots = {"A": {"SPY": Lot(300, 100, OLD), "EFA": Lot(300, 100, OLD)},
            "B": {"QQQ": Lot(200, 100, RECENT, 94.0, 94.0)}}  # 80% of equity is equity-like
    res = run(cfg, [Target("AAPL", "C", 50, None, "breakout"), Target("QQQ", "B", 210, None, "add")],
              lots, bars=bars_for("SPY", "EFA", "QQQ", "AAPL"))
    assert target(res, "C", "AAPL") is None and target(res, "B", "QQQ").qty == 200
    assert target(res, "A", "SPY").qty == 300 and target(res, "A", "EFA").qty == 300
    assert res.orders == [] and logged(res, "equity-like cap (RISK-6)")


def test_sleeve_weight_cap(cfg):  # RISK-8 and today's weights
    lots = {"C": {"MSFT": Lot(80, 100, OLD, 96.0, 96.0)}}
    bars = bars_for("MSFT", "AAPL")
    prop = [Target("AAPL", "C", 100, None, "breakout")]
    assert target(run(cfg, prop, lots, bars=bars), "C", "AAPL").qty == pytest.approx(70)  # 15% - 8% held
    w = {"A": 0.55, "B": 0.20, "C": 0.10, "D": 0.0}
    assert target(run(cfg, prop, lots, bars=bars, weights=w), "C", "AAPL").qty == pytest.approx(20)
    assert target(run(cfg, prop, lots, bars=bars, promoted=["C"]), "C", "AAPL").qty == pytest.approx(100)
    assert target(run(cfg, prop, lots, bars=bars, weights={"A": 0.55}), "C", "AAPL") is None


def test_speculative_cap(cfg):  # RISK-7
    on = tweak(cfg, {"playbook.sleeves.D.enabled": True})
    lots = {"C": {"AAPL": Lot(90, 100, OLD, 96.0, 96.0), "MSFT": Lot(70, 100, OLD, 96.0, 96.0)},
            "D": {"BTC/USD": Lot(30, 100, OLD)}}
    bars = bars_for("AAPL", "MSFT", "NVDA", "BTC/USD")
    res = run(on, [Target("NVDA", "C", 50, None, "breakout")], lots, bars=bars, promoted=["C"])
    assert target(res, "C", "NVDA").qty == pytest.approx(10)  # 20% of C + D minus 19% held
    assert logged(res, "speculative cap on C + D (RISK-7)")


def test_new_money_never_exceeds_the_speculative_cap(cfg):  # RISK-7, no tolerance for new buys
    on = tweak(cfg, {"playbook.sleeves.D.enabled": True})
    w = {"A": 0.55, "B": 0.2, "C": 0.2, "D": 0.05}
    prop = [Target(s, "C", 26, None, "breakout") for s in ("AAPL", "MSFT", "NVDA", "GOOGL", "JPM", "XOM")]
    prop.append(Target("BTC/USD", "D", 60, None, "trend"))
    bars = bars_for("AAPL", "MSFT", "NVDA", "GOOGL", "JPM", "XOM", "BTC/USD")
    res = run(on, prop, bars=bars, weights=w, promoted=["C", "D"])
    spec = sum(t.qty * 100 for t in res.targets if t.sleeve in ("C", "D"))
    assert spec <= 0.20 * E + 1e-6


def test_caps_never_cut_existing_holdings(cfg):
    lots = {"C": {"AAPL": Lot(100, 100, OLD, 96.0, 96.0), "MSFT": Lot(80, 100, OLD, 96.0, 96.0)}}
    res = run(cfg, [Target("AAPL", "C", 110, None, "add")], lots, bars=bars_for("AAPL", "MSFT"))
    assert target(res, "C", "AAPL").qty == 100 and target(res, "C", "MSFT").qty == 80
    assert res.orders == []


def test_price_drift_is_never_cut_but_new_money_stops_at_the_cap(cfg):  # RISK-8
    lots = {"C": {"MSFT": Lot(100, 100, OLD, 96.0, 96.0)}}
    res = run(cfg, [Target("AAPL", "C", 50.5, None, "breakout")], lots, bars=bars_for("MSFT", "AAPL"))
    assert target(res, "C", "AAPL").qty == pytest.approx(50)  # exactly 15%, not 15.05%
    drifted = {"C": {"MSFT": Lot(100, 60, OLD, 96.0, 96.0), "AAPL": Lot(60, 60, OLD, 96.0, 96.0)}}  # now 16%
    res = run(cfg, [Target("AAPL", "C", 60, None, "hold"), Target("NVDA", "C", 10, None, "breakout")], drifted,
              bars=bars_for("MSFT", "AAPL", "NVDA"))
    assert target(res, "C", "MSFT").qty == 100 and target(res, "C", "AAPL").qty == 60
    assert target(res, "C", "NVDA") is None and res.orders == []


# --- step 4: orders ------------------------------------------------------------------------------


def _many_buys():
    return [Target("AAPL", "C", 50, None, "breakout"), Target("SPY", "A", 20, None, "faber"),
            Target("IEF", "A", 50, None, "faber"), Target("MSFT", "C", 60, None, "breakout"),
            Target("QQQ", "B", 30, None, "rsi2")]


def test_buy_priority_when_the_order_cap_bites(cfg):  # EX-3
    bars = bars_for("AAPL", "SPY", "IEF", "MSFT", "QQQ", "EFA")
    two = tweak(cfg, {"policy.turnover.max_orders_per_day": 2})
    res = run(two, _many_buys(), bars=bars)
    assert [(o.symbol, o.priority) for o in res.orders] == [("IEF", 1), ("SPY", 1)]
    assert {t.symbol for t in res.targets} == {"IEF", "SPY"}  # dropped entries fall back to no position
    assert logged(res, "3 buy order(s) dropped")
    three = tweak(cfg, {"policy.turnover.max_orders_per_day": 3})
    assert [o.symbol for o in run(three, _many_buys(), bars=bars).orders] == ["IEF", "SPY", "QQQ"]
    four = tweak(cfg, {"policy.turnover.max_orders_per_day": 4})
    assert [o.symbol for o in run(four, _many_buys(), bars=bars).orders][-1] == "MSFT"  # larger C buy first
    lots = {"A": {"EFA": Lot(50, 100, OLD)}}
    res = run(two, _many_buys() + [Target("EFA", "A", 0, None, "exit")], lots, bars=bars)
    assert [(o.symbol, o.side, o.priority) for o in res.orders] == [("EFA", "sell", 0), ("IEF", "buy", 1)]


def test_dropped_buy_keeps_an_enforced_exit_in_the_same_symbol(cfg):
    zero = tweak(cfg, {"policy.turnover.max_orders_per_day": 0})
    lots = {"B": {"SPY": Lot(10, 100, RECENT, 101.0, 101.0)}}  # stop above the close: exit enforced
    res = run(zero, [Target("SPY", "A", 100, None, "faber")], lots, bars=bars_for("SPY"))
    assert [(o.symbol, o.side, o.qty) for o in res.orders] == [("SPY", "sell", 10)]
    b = target(res, "B", "SPY")
    assert b.qty == 0 and b.reason == "stop hit (enforced)"
    assert target(res, "A", "SPY") is None
    assert logged(res, "exits are never held back")


def test_exits_uncovered_by_a_dropped_buy_count_against_the_cap(cfg):  # EX-3
    two = tweak(cfg, {"policy.turnover.max_orders_per_day": 2})
    lots = {"B": {"SPY": Lot(10, 100, RECENT, 101.0, 101.0)}}  # stop above the close: exit enforced
    prop = [Target(s, "A", 50, None, "faber") for s in ("SPY", "IEF", "EFA")]
    res = run(two, prop, lots, bars=bars_for("SPY", "IEF", "EFA"))
    assert [(o.symbol, o.side, o.priority) for o in res.orders] == [("SPY", "sell", 0), ("IEF", "buy", 1)]
    assert logged(res, "2 buy order(s) dropped (max 2/day): SPY, EFA")
    assert logged(res, "SPY: buy dropped by the order cap; other sleeves' reductions still sold")
    assert target(res, "A", "EFA") is None and target(res, "A", "IEF").qty == 50


def test_small_lot_exit_is_sent_when_another_sleeve_holds_the_symbol(cfg):  # RISK-4, EX-3 $25 minimum
    lots = {"A": {"SPY": Lot(100, 100, OLD)}, "B": {"SPY": Lot(0.2, 100, RECENT, 101.0, 101.0)}}
    res = run(cfg, [], lots, bars=bars_for("SPY"))
    assert [(o.symbol, o.side, o.qty) for o in res.orders] == [("SPY", "sell", 0.2)]
    lots = {"A": {"SPY": Lot(100, 100, OLD)}, "B": {"SPY": Lot(1, 100, RECENT, 94.0, 94.0)}}
    res = run(cfg, [Target("SPY", "B", 0.9, None, "trim")], lots, bars=bars_for("SPY"))
    assert res.orders == []  # a partial trim under $25 is still skipped


def test_dropped_buy_restores_the_lot_stop(cfg):
    zero = tweak(cfg, {"policy.turnover.max_orders_per_day": 0})
    lots = {"B": {"SPY": Lot(10, 95, RECENT, 80.0, 80.0)}}
    res = run(zero, [Target("SPY", "B", 20, 90.0, "add")], lots, bars=bars_for("SPY"), book="claude")
    t = target(res, "B", "SPY")
    assert t.qty == 10 and t.stop == 80.0 and t.reason == "order dropped by daily cap"


def test_full_exit_is_sent_below_the_minimum_notional(cfg):
    lots = {"C": {"AAPL": Lot(0.1, 90, OLD, 96.0, 96.0)}}
    res = run(cfg, [Target("AAPL", "C", 0, None, "exit")], lots, bars=bars_for("AAPL"))
    assert [(o.symbol, o.side, o.qty) for o in res.orders] == [("AAPL", "sell", 0.1)]
    lots = {"C": {"AAPL": Lot(1, 90, OLD, 96.0, 96.0)}}
    assert run(cfg, [Target("AAPL", "C", 0.9, None, "trim")], lots, bars=bars_for("AAPL")).orders == []


def test_sells_never_exceed_broker_holdings(cfg):  # RISK-1
    lots = {"C": {"AAPL": Lot(10, 90, OLD, 96.0, 96.0)}}
    res = run(cfg, [Target("AAPL", "C", 0, None, "exit")], lots, broker={"AAPL": 5}, bars=bars_for("AAPL"))
    assert [(o.side, o.qty) for o in res.orders] == [("sell", 5)]


def test_reductions_pass_for_symbols_off_the_allowlist(cfg):
    lots = {"C": {"XYZ": Lot(10, 90, OLD, 50.0, 50.0)}}
    res = run(cfg, [Target("XYZ", "C", 0, None, "exit")], lots, bars=bars_for("XYZ"))
    assert [(o.symbol, o.side) for o in res.orders] == [("XYZ", "sell")]
    res = run(cfg, [Target("XYZ", "B", 5, None, "entry")], lots, bars=bars_for("XYZ"))
    assert logged(res, "not on the allowlist") and res.orders == []


# --- robustness and compatibility --------------------------------------------------------------


def test_bad_quantities_and_stops(cfg):
    bars = bars_for("AAPL", "MSFT")
    res = run(cfg, [Target("AAPL", "C", float("nan"), None, "x"), Target("MSFT", "C", 10, float("nan"), "e")],
              bars=bars)
    assert target(res, "C", "AAPL") is None and logged(res, "not a number")
    assert target(res, "C", "MSFT").stop == pytest.approx(96.0)
    lots = {"C": {"AAPL": Lot(10, 90, OLD, 96.0, 96.0)}}
    res = run(cfg, [Target("AAPL", "C", -5, None, "short?")], lots, bars=bars)
    assert [(o.side, o.qty) for o in res.orders] == [("sell", 10)]  # long only: negative means flat


def test_zero_equity_blocks_increases(cfg):
    b = Breakers(0.0, False, False, 1.0, 0.0, 0.0, [])
    res = RiskEngine(cfg).apply([Target("SPY", "A", 10, None, "x")], {}, {}, bars_for("SPY"), 0.0, b)
    assert res.orders == [] and logged(res, "equity is zero or unknown")


def test_unknown_sleeve_and_empty_inputs(cfg):
    res = run(cfg, [Target("SPY", "Z", 10, None, "x")], bars=bars_for("SPY"))
    assert res.orders == [] and logged(res, "unknown sleeve")
    res = RiskEngine(cfg).apply([], {}, {}, {}, E, calm(cfg))
    assert res.targets == [] and res.orders == []


def test_inputs_are_not_mutated(cfg):
    lots = _mixed_book()
    proposed = [Target("VNQ", "A", 200, None, "faber"), Target("AAPL", "C", 0, None, "exit")]
    before = (copy.deepcopy(lots), copy.deepcopy(proposed))
    run(cfg, proposed, lots, bars=bars_for("SPY", "QQQ", "AAPL", "MSFT", "VNQ"), book="claude")
    assert (lots, proposed) == before


def test_old_positional_apply_call_still_works(cfg):
    res = RiskEngine(cfg).apply([Target("MSFT", "C", 10, None, "e")], {}, {}, bars_for("MSFT"), E, calm(cfg))
    assert [o.symbol for o in res.orders] == ["MSFT"]


def test_default_stop_delegates_to_rule_stop(cfg):
    bars = bars_for("MSFT", "SPY")
    engine = RiskEngine(cfg)
    assert engine._default_stop("C", "MSFT", bars, 100.0) == pytest.approx(
        strategies.rule_stop("C", bars["MSFT"], cfg.policy))
    a = engine._default_stop("A", "SPY", bars, 100.0)
    assert math.isfinite(a) and a < 100
