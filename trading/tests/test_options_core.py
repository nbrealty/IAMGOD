"""Book O core: candidate, exits, ladder, breakers, incidents (book.py), ledger (ledger.py), order check (risk.py).

Synthetic chains only; no network, no broker. Rule IDs refer to reports/Options rulebook.md.
"""
import copy
import json
import math

import pytest

from trader.options import book as B
from trader.options import risk as OR
from trader.options.ledger import OptionsBook, lot_unrealized, o_pnl, o_value, rules_equity
from trader.options.models import OptionLeg, OptionQuote, SpreadLot, occ_symbol

DATE = "2026-10-16"  # Friday; the Nov 20 2026 monthly is 35 DTE
MONTHLY = "2026-11-20"
SPOT = 770.0
EQ = 100_000.0
CASH = 100_000.0
QT = "2026-10-16T19:50:00Z"  # 15:50 ET


@pytest.fixture
def policy(cfg):
    return copy.deepcopy(cfg.policy)


def q(strike, expiry=MONTHLY, und="SPY", typ="put", spread=0.02, mid=None, delta=None, **kw):
    """One synthetic put: |delta| 0.20 at 741, +0.01 per $1; mid 5.00 at 741, +0.20 per $1."""
    mid = 5.0 + (strike - 741) * 0.2 if mid is None else mid
    delta = -(0.20 + (strike - 741) * 0.01) if delta is None else delta
    base = dict(symbol=occ_symbol(und, expiry, typ, strike), underlying=und, expiry=expiry, type=typ,
                strike=float(strike), bid=round(mid - spread / 2, 4), ask=round(mid + spread / 2, 4), quote_time=QT,
                iv=0.18, delta=delta, gamma=0.01, theta=-0.05, vega=0.5 + (strike - 741) * 0.01,
                open_interest=1000, volume=200)
    base.update(kw)
    return OptionQuote(**base)


def chain(expiries=(MONTHLY,), strikes=range(730, 752), **kw):
    return [q(k, e, **kw) for e in expiries for k in strikes]


def build(quotes=None, policy=None, regime="bull_calm", lots=(), equity=EQ, cash=CASH, week=0, **kw):
    return B.build_candidate(chain() if quotes is None else quotes, SPOT, DATE, policy, regime, list(lots), equity,
                             cash, week, **kw)


def make_lot(short=741, width=3, contracts=1, credit=0.6, expiry=MONTHLY, lot_id="L1", entry_date="2026-10-16",
             status="open", budget=None):
    s = OptionLeg(occ_symbol("SPY", expiry, "put", short), "put", float(short), expiry, "short", contracts)
    lg = OptionLeg(occ_symbol("SPY", expiry, "put", short - width), "put", float(short - width), expiry, "long",
                   contracts)
    ml = (width - credit) * 100 * contracts
    return SpreadLot(lot_id, "SPY", expiry, "put", s, lg, contracts, float(width), credit, ml,
                     budget if budget is not None else ml + 4 * contracts, entry_date, status=status)


# --- policy helpers ----------------------------------------------------------------------------------


def test_ob_policy_accepts_full_policy_block_or_none(policy):
    assert B.ob_policy(policy)["max_open_spreads"] == 3
    assert B.ob_policy(policy["options_book"])["exit_dte"] == 7
    assert B.ob_policy(None)["min_dte_entry"] == 25
    assert B.ob_policy({})["width_range"] == [2, 5]


def test_policy_block_values_match_rulebook(policy):
    ob = policy["options_book"]
    assert ob["enabled"] is False and ob["underlyings"] == ["SPY"]
    assert ob["max_budgeted_loss_per_trade_pct"] == 0.0025 and ob["max_open_budgeted_loss_pct"] == 0.010


def test_num_and_dte_helpers():
    assert B.num(float("nan")) is None and B.num("x", 1.0) == 1.0 and B.num(None) is None
    assert B.dte(MONTHLY, DATE) == 35
    assert B.floor_int(2.9999999999) == 3 and B.floor_int(2.99) == 2 and B.floor_int(float("nan")) == 0


# --- OPT-18 expiries -----------------------------------------------------------------------------------


def test_monthly_candidates_pick_standard_monthly_in_window(policy):
    exps = ["2026-11-13", MONTHLY, "2026-11-27", "2026-12-18", "2026-10-30"]
    assert B.monthly_expiry_candidates(exps, DATE, policy) == [MONTHLY]
    assert B.monthly_expiry_candidates(chain(expiries=exps, strikes=[741]), DATE, policy) == [MONTHLY]


def test_monthly_window_edges(policy):
    assert B.monthly_expiry_candidates([MONTHLY], "2026-10-15", policy) == [MONTHLY]  # DTE 36: first run
    assert B.monthly_expiry_candidates([MONTHLY], "2026-10-14", policy) == []  # DTE 37: too early
    assert B.monthly_expiry_candidates([MONTHLY], "2026-10-21", policy) == [MONTHLY]  # DTE 30: last retry
    assert B.monthly_expiry_candidates([MONTHLY], "2026-10-22", policy) == []  # DTE 29: cycle lost
    assert B.monthly_expiry_candidates([], DATE, policy) == []


def test_holiday_thursday_monthly():
    # April 2025: the third Friday (18th) was Good Friday; the monthly moved to Thursday the 17th.
    assert B.is_standard_monthly("2025-04-17", ["2025-04-17", "2025-04-25"])
    assert not B.is_standard_monthly("2025-04-17", ["2025-04-17", "2025-04-18"])
    assert B.is_standard_monthly("2026-11-20") and not B.is_standard_monthly("2026-11-13")


# --- OPT-12 leg filter -----------------------------------------------------------------------------------


@pytest.mark.parametrize("kw, word", [
    ({"tradable": False}, "tradable"), ({"open_interest": 499}, "open interest"),
    ({"open_interest": None}, "open interest"), ({"volume": 49}, "volume"), ({"volume": None}, "volume"),
    ({"bid": 0.0}, "bid"), ({"bid": None}, "bid"), ({"spread": 0.30}, "too wide"),
    ({"quote_time": "2026-10-16T19:00:00Z"}, "quote time"), ({"quote_time": "2026-10-15T20:00:00Z"}, "quote time"),
    ({"quote_time": None}, "quote time"), ({"delta": float("nan")}, "delta"), ({"iv": None}, "iv"),
    ({"vega": None}, "vega"),
])
def test_leg_filter_rejects(kw, word, policy):
    spread = kw.pop("spread", 0.02)
    delta = kw.pop("delta", None)
    leg = q(741, spread=spread, **({"delta": delta} if delta is not None else {}), **kw)
    probs = B.leg_problems(leg, DATE, policy)
    assert any(word in p for p in probs), probs


def test_leg_filter_passes_good_leg_and_spread_threshold(policy):
    assert B.leg_problems(q(741), DATE, policy) == []
    # max($0.05, 5% of mid): a $5 mid allows $0.25
    assert B.leg_problems(q(741, spread=0.25), DATE, policy) == []
    assert B.leg_problems(q(741, spread=0.26), DATE, policy) != []
    assert B.leg_problems(None, DATE, policy) == ["quote missing"]


def test_leg_filter_time_check_can_be_disabled(policy):
    policy["options_book"]["leg_filter"]["quote_after_et"] = None
    assert B.leg_problems(q(741, quote_time=None), DATE, policy) == []


# --- OPT-18 candidate ------------------------------------------------------------------------------------


def test_candidate_happy_path(policy):
    cand, reasons = build(policy=policy)
    assert cand is not None, reasons
    assert cand["expiry"] == MONTHLY and cand["dte"] == 35
    assert cand["short"]["strike"] == 741.0  # |delta| nearest 0.20
    # widest width whose budgeted loss fits $250: $3 (credit 0.60, MaxLoss 240, + quoted 4 = 244)
    assert cand["width"] == 3.0 and cand["long"]["strike"] == 738.0
    assert cand["contracts"] == 1
    assert cand["mid_credit"] == pytest.approx(0.6)
    assert cand["quoted_cost"] == pytest.approx(0.04)
    assert cand["max_loss"] == pytest.approx(240.0)
    assert cand["budgeted_loss"] == pytest.approx(244.0)
    assert cand["min_credit"] == pytest.approx(0.60 - 0.004, abs=0.006)
    assert cand["limit_price"] < 0  # OPT-14: credit entry is a negative limit
    assert cand["retry_limit_price"] < 0 and -cand["retry_limit_price"] <= -cand["limit_price"]
    assert cand["shadow_only"] is False and cand["feed"] == "indicative"
    json.dumps(cand)  # JSON-safe


def test_candidate_width_grows_with_cap(policy):
    cand, _ = build(policy=policy, equity=200_000, cash=200_000)
    assert cand["width"] == 5.0 and cand["contracts"] == 1  # cap 500 fits $5 (400 + 4)


def test_candidate_no_width_fits(policy):
    cand, reasons = build(policy=policy, equity=40_000, cash=CASH)  # cap 100 < $2 spread's 164
    assert cand is None and any("OPT-8" in r for r in reasons)


def test_sizing_uses_budget_and_rounds_down():
    assert B.size_contracts(250, 120) == 2
    assert B.size_contracts(250, 125) == 2
    assert B.size_contracts(250, 251) == 0
    assert B.size_contracts(250, 0) == 0 and B.size_contracts(250, float("nan")) == 0
    assert B.size_contracts(500, 120, 0.5) == 2  # 4 x 0.5
    assert B.size_contracts(250, 120, 0.5) == 1
    assert B.size_contracts(250, 244, 0.5) == 0  # OPT-19: 1 contract always becomes 0


@pytest.mark.parametrize("label", ["choppy", "bear", "panic", "nonsense", None])
def test_regime_permission_zero_blocks(label, policy):
    cand, reasons = build(policy=policy, regime=label)
    assert cand is None and any("OPT-19" in r for r in reasons)


def test_bull_volatile_one_contract_becomes_zero(policy):
    cand, reasons = build(policy=policy, regime="bull_volatile")
    assert cand is None and any("OPT-19" in r and "0" in r for r in reasons)
    assert B.permission("bull_volatile", policy) == 0.5 and B.permission("bull_calm", policy) == 1.0


def test_opt13_cost_filter_reports_no_trade(policy):
    quotes = chain(spread=0.08)  # quoted cost 0.16 on a 0.60 credit = 27%
    cand, reasons = build(quotes=quotes, policy=policy)
    assert cand is None and any(r.startswith("OPT-13") for r in reasons)


def test_short_delta_band_and_filter(policy):
    quotes = [x for x in chain() if not (736 <= x.strike <= 746)]  # nothing with |delta| 0.15-0.25
    cand, reasons = build(quotes=quotes, policy=policy)
    assert cand is None and any("OPT-18" in r for r in reasons)
    illiquid = [q(k, open_interest=10) if 736 <= k <= 746 else q(k) for k in range(730, 752)]
    cand, reasons = build(quotes=illiquid, policy=policy)
    assert cand is None and any("OPT-12" in r for r in reasons)


def test_short_falls_back_to_next_leg_in_band_when_nearest_fails(policy):
    quotes = [q(741, volume=1) if k == 741 else q(k) for k in range(730, 752)]
    cand, _ = build(quotes=quotes, policy=policy)
    assert cand["short"]["strike"] in (740.0, 742.0)
    assert cand["short"]["strike"] == 740.0  # tie goes to the smaller |delta| (further out of the money)


def test_long_leg_missing_narrows_width(policy):
    quotes = [x for x in chain() if x.strike != 738]
    cand, _ = build(quotes=quotes, policy=policy)
    assert cand["width"] == 2.0 and cand["long"]["strike"] == 739.0


def test_missing_greek_on_long_blocks(policy):
    quotes = [q(k, iv=None) if k < 741 else q(k) for k in range(730, 752)]
    cand, reasons = build(quotes=quotes, policy=policy)
    assert cand is None and any("iv missing" in r for r in reasons)


@pytest.mark.parametrize("spot, equity", [(float("nan"), EQ), (None, EQ), (0, EQ), (SPOT, 0), (SPOT, None)])
def test_bad_inputs_no_trade(spot, equity, policy):
    cand, reasons = B.build_candidate(chain(), spot, DATE, policy, "bull_calm", [], equity, CASH, 0)
    assert cand is None and reasons


def test_empty_chain_no_trade(policy):
    assert build(quotes=[], policy=policy)[0] is None
    assert build(quotes=None, policy=policy)[0] is not None  # helper default chain


def test_non_spy_is_shadow_only(policy):
    quotes = chain(und="QQQ")
    cand, _ = build(quotes=quotes, policy=policy, underlying="QQQ")
    assert cand is not None and cand["shadow_only"] is True
    assert build(quotes=quotes, policy=policy)[0] is None  # SPY requested, only QQQ quoted


# --- OPT-9 / OPT-10 caps --------------------------------------------------------------------------------


def test_open_budget_cap_clips(policy):
    lots = [make_lot(expiry="2026-12-18", lot_id="A", budget=800, entry_date="2026-10-01")]
    cand, reasons = build(policy=policy, lots=lots, quotes=chain() + chain(expiries=("2026-12-18",)))
    assert cand is None and any("OPT-9 open budgeted loss" in r for r in reasons)  # 800 + 244 > 1000


def test_three_open_spreads_block(policy):
    lots = [make_lot(expiry=e, lot_id=e, entry_date="2026-09-01") for e in ("2026-12-18", "2027-01-15", "2027-02-19")]
    cand, reasons = build(policy=policy, lots=lots, cash=10_000_000)
    assert cand is None and any("3 open spreads" in r for r in reasons)


def test_weekly_cap(policy):
    cand, reasons = build(policy=policy, week=1)
    assert cand is None and any("this week" in r for r in reasons)
    # week_count None: counted from the lots
    lots = [make_lot(expiry="2026-12-18", lot_id="A", entry_date="2026-10-13")]
    cand, reasons = build(policy=policy, lots=lots, week=None, cash=10_000_000,
                          quotes=chain() + chain(expiries=("2026-12-18",)))
    assert cand is None and any("this week" in r for r in reasons)


def test_assignment_cover(policy):
    cand, reasons = build(policy=policy, cash=50_000)  # 741 x 100 = 74,100 needed
    assert cand is None and any("assignment cover" in r for r in reasons)
    cand, reasons = build(policy=policy, cash=None)
    assert cand is None and any("unknown" in r for r in reasons)
    lots = [make_lot(expiry="2026-12-18", lot_id="A", entry_date="2026-10-01")]
    cand, reasons = build(policy=policy, lots=lots, cash=100_000, quotes=chain() + chain(expiries=("2026-12-18",)))
    assert cand is None and any("assignment cover" in r for r in reasons)  # 74,100 x 2 > 100k
    policy["options_book"]["require_assignment_cover"] = False
    assert build(policy=policy, cash=None)[0] is not None


def test_delta_and_vega_caps(policy):
    policy["options_book"]["max_delta_notional_pct"] = 0.001  # $100 on 100k
    cand, reasons = build(policy=policy)
    assert cand is None and any("OPT-10" in r for r in reasons)
    policy["options_book"]["max_delta_notional_pct"] = 0.20
    policy["options_book"]["max_short_vega_pct"] = 0.0000001
    cand, reasons = build(policy=policy)
    assert cand is None and any("OPT-10" in r for r in reasons)


def test_open_lot_without_greeks_blocks_entries(policy):
    lots = [make_lot(expiry="2026-12-18", lot_id="A", entry_date="2026-10-01")]
    cand, reasons = build(policy=policy, lots=lots, cash=10_000_000)  # December legs not quoted
    assert cand is None and any("greeks missing" in r for r in reasons)


# --- OPT-18 one per cycle, OPT-24, OPT-15 freeze, external blocks ------------------------------------------


def test_one_spread_per_cycle_and_no_second_after_loss(policy):
    lot = make_lot(lot_id="A", entry_date="2026-10-01")
    cand, reasons = build(policy=policy, lots=[lot], cash=10_000_000)
    assert cand is None and any("OPT-18" in r and "cycle" in r for r in reasons)
    closed = [{"expiry": MONTHLY, "pnl": -50.0}]
    cand, reasons = build(policy=policy, closed=closed)
    assert cand is None and any("OPT-24" in r for r in reasons)
    assert build(policy=policy, closed=[{"expiry": "2026-10-16", "pnl": -50.0}])[0] is not None


def test_dte_two_freezes_entries(policy):
    lot = make_lot(expiry="2026-10-16", lot_id="old", entry_date="2026-09-11")
    lot.expiry = "2026-10-18"
    cand, reasons = build(policy=policy, lots=[lot], cash=10_000_000)
    assert cand is None and any("OPT-15" in r for r in reasons)
    assert B.entry_freeze_alerts([lot], DATE, policy)


def test_external_blocks_and_cap_mult(policy):
    cand, reasons = build(policy=policy, blocks=["OPT-30: daily loss"])
    assert cand is None and reasons == ["OPT-30: daily loss"]
    cand, reasons = build(policy=policy, cap_mult=0.5)  # OPT-31 halves the cap to 125: nothing fits
    assert cand is None and any("OPT-8" in r for r in reasons)
    cand, _ = build(policy=policy, cap_mult=0.5, equity=200_000, cash=200_000)
    assert cand["per_trade_cap"] == pytest.approx(250.0) and cand["width"] == 3.0


def test_entry_recheck_cancels_after_one_percent_move(policy):
    cand, _ = build(policy=policy)
    assert B.entry_recheck(cand, SPOT * 1.005, policy) is None
    assert "OPT-17" in B.entry_recheck(cand, SPOT * 0.985, policy)
    assert "OPT-17" in B.entry_recheck(cand, SPOT * 1.0101, policy)
    assert "OPT-17" in B.entry_recheck(cand, float("nan"), policy)


# --- exits (OPT-22, OPT-23, OPT-15) --------------------------------------------------------------------


def test_exit_signal_rules(policy):
    lot = make_lot()
    assert B.exit_signal(lot, [], SPOT, "2026-11-12", policy) is None  # DTE 8, above strike
    assert B.exit_signal(lot, [], SPOT, "2026-11-13", policy) == B.EXIT_EXPIRY  # DTE 7
    assert B.exit_signal(lot, [], 740.0, DATE, policy) == B.EXIT_SHORT_STRIKE
    assert B.exit_signal(lot, [], 741.0, DATE, policy) is None  # at the strike is not below it
    assert B.exit_signal(lot, [], SPOT, "2026-11-18", policy) == B.EXIT_ALERT  # DTE 2
    assert B.exit_signal(lot, None, float("nan"), DATE, policy) is None
    assert B.exit_signal(lot, None, None, "2026-11-14", policy) == B.EXIT_EXPIRY  # no chain, no spot: still fires
    lot.status = "closed"
    assert B.exit_signal(lot, [], 700.0, "2026-11-19", policy) is None


def test_exit_fires_without_chain_entry_does_not(policy):
    lot = make_lot()
    assert B.exit_signal(lot, [], 730.0, DATE, policy) == B.EXIT_SHORT_STRIKE
    assert build(quotes=[], policy=policy)[0] is None


def _lot_quotes(short_mid=2.0, long_mid=1.5, spread=0.10, quote_time=QT):
    return [q(741, mid=short_mid, spread=spread, quote_time=quote_time),
            q(738, mid=long_mid, spread=spread, quote_time=quote_time)]


def test_ladder_steps(policy):
    lot = make_lot()
    qs = _lot_quotes()
    assert B.ladder_price(lot, qs, 1, policy) == pytest.approx(0.50)  # mid
    assert B.ladder_price(lot, qs, 2, policy) == pytest.approx(0.60)  # natural 2.05 - 1.45
    assert B.ladder_price(lot, qs, 3, policy) == pytest.approx(0.65)
    assert B.ladder_price(lot, qs, 5, policy) == pytest.approx(0.75)


def test_ladder_forced_starts_at_natural(policy):
    lot = make_lot()
    qs = _lot_quotes()
    assert B.ladder_price(lot, qs, 1, policy, forced=True) == pytest.approx(0.60)
    assert B.ladder_price(lot, qs, 2, policy, forced=True) == pytest.approx(0.65)
    q15 = _lot_quotes(quote_time="2026-11-15T19:50:00Z")
    q14 = _lot_quotes(quote_time="2026-11-14T19:50:00Z")
    assert B.ladder_price(lot, q15, 1, policy, date="2026-11-15") == pytest.approx(0.60)  # DTE 5
    assert B.ladder_price(lot, q14, 1, policy, date="2026-11-14") == pytest.approx(0.50)  # DTE 6
    assert B.is_forced(B.EXIT_SHORT_STRIKE) and not B.is_forced(B.EXIT_EXPIRY, 7)


def test_ladder_never_pays_more_than_width(policy):
    lot = make_lot()
    qs = _lot_quotes(short_mid=6.0, long_mid=2.8)
    d = B.ladder_detail(lot, qs, 9, policy)
    assert d["limit_price"] == 3.0 and d["capped"]
    missing = B.ladder_detail(lot, [], 1, policy)
    assert missing["limit_price"] == 3.0 and missing["capped"]  # quotes missing: price at the width cap
    tiny = B.ladder_price(lot, _lot_quotes(short_mid=0.01, long_mid=0.02, spread=0.0), 1, policy)
    assert tiny == 0.01  # a close is always a positive debit


# --- breakers (OPT-30, OPT-31, OPT-32) ------------------------------------------------------------------


def test_daily_loss_breaker(policy):
    assert "OPT-30" in B.daily_loss_breaker(-500, EQ, policy)
    assert B.daily_loss_breaker(-499, EQ, policy) is None
    assert B.daily_loss_breaker(100, EQ, policy) is None
    assert B.daily_loss_breaker(float("nan"), EQ, policy) is None


def test_drawdown_tiers(policy):
    assert B.drawdown_state(0, 0, EQ, policy)["cap_mult"] == 1.0
    assert B.drawdown_state(-1000, 0, EQ, policy)["cap_mult"] == 0.5
    halt = B.drawdown_state(-1500, 500, EQ, policy)
    assert halt["halt"] and halt["close_all"] and halt["cap_mult"] == 0.0
    assert B.drawdown_state(None, 0, EQ, policy)["cap_mult"] == 0.0


def test_demotion(policy):
    assert "OPT-32" in B.demotion_check([-0.3] * 30, policy)
    assert B.demotion_check([-0.3] * 29, policy) is None
    assert B.demotion_check([0.1] * 40, policy) is None
    assert B.demotion_check([], policy) is None
    assert B.demotion_check([float("nan")] * 40, policy) is None


def test_breaker_status_combines(policy):
    s = B.breaker_status(day_pnl=-600, o_pnl=-600, o_peak=0, equity=EQ, policy=policy)
    assert s["no_new_entries"] and s["cap_mult"] == 1.0 and not s["close_all"]
    s = B.breaker_status(day_pnl=0, o_pnl=0, o_peak=0, equity=EQ, halted=True, policy=policy)
    assert s["halt"] and s["no_new_entries"]
    s = B.breaker_status(day_pnl=0, o_pnl=0, o_peak=0, equity=EQ, policy=policy)
    assert not s["no_new_entries"] and s["reasons"] == []


# --- incidents (OPT-26, OPT-27) -------------------------------------------------------------------------


def _positions(lot, short_qty=None, long_qty=None):
    return [{"symbol": lot.short_leg.symbol, "qty": -(lot.contracts if short_qty is None else short_qty)},
            {"symbol": lot.long_leg.symbol, "qty": lot.contracts if long_qty is None else long_qty}]


def test_matching_positions_no_incident():
    lot = make_lot()
    pos = _positions(lot) + [{"symbol": "SPY", "qty": 10}]
    r = B.detect_incidents(pos, [lot], other_books_stock={"SPY": 10})
    assert not r["freeze"] and r["incidents"] == [] and r["mismatches"] == []


def test_stock_appearing_freezes_entries():
    lot = make_lot()
    r = B.detect_incidents(_positions(lot, short_qty=0) + [{"symbol": "SPY", "qty": 110}], [lot],
                           other_books_stock={"SPY": 10})
    assert r["freeze"] and any("stock" in i for i in r["incidents"]) and r["stock_excess"] == {"SPY": 100}
    r = B.detect_incidents([{"symbol": "AAPL", "qty": 5}], [])
    assert r["freeze"]


def test_naked_short_and_orphan_long_detected():
    lot = make_lot()
    r = B.detect_incidents(_positions(lot, long_qty=0), [lot])
    assert r["freeze"] and any("naked short" in i for i in r["incidents"])
    r = B.detect_incidents(_positions(lot, short_qty=0), [lot])
    assert any("orphan long" in i for i in r["incidents"])
    # long leg on the wrong side of the short (not protecting it)
    bad = [{"symbol": occ_symbol("SPY", MONTHLY, "put", 741), "qty": -1},
           {"symbol": occ_symbol("SPY", MONTHLY, "put", 745), "qty": 1}]
    assert any("not protected" in i for i in B.detect_incidents(bad, [])["incidents"])


def test_position_ledger_mismatch_blocks():
    lot = make_lot()
    r = B.detect_incidents(_positions(lot, short_qty=2, long_qty=2), [lot])
    assert r["freeze"] and r["mismatches"]
    r = B.detect_incidents([], [lot])
    assert r["freeze"] and r["mismatches"]


def test_short_side_field_is_read():
    lot = make_lot()
    pos = [{"symbol": lot.short_leg.symbol, "qty": 1, "side": "short"}, {"symbol": lot.long_leg.symbol, "qty": 1}]
    assert not B.detect_incidents(pos, [lot])["freeze"]


def test_margin_check(policy):
    lot = make_lot(contracts=2)
    assert B.margin_problem(600.0, [lot], policy) is None
    assert B.margin_problem(601.9, [lot], policy) is None  # within $1 per contract
    assert "OPT-27" in B.margin_problem(603.0, [lot], policy)
    assert "OPT-27" in B.margin_problem(None, [lot], policy)
    assert B.margin_problem(None, [], policy) is None
    r = B.detect_incidents(_positions(lot), [lot], maintenance_margin=900, check_margin=True, policy=policy)
    assert r["freeze"]


def test_cleanup_sells_stock_before_long_put():
    lot = make_lot()
    pos = [{"symbol": lot.long_leg.symbol, "qty": 1}, {"symbol": "SPY", "qty": 100}]
    inc = B.detect_incidents(pos, [lot], o_stock={"SPY": 100})
    steps = B.cleanup_plan(inc, [lot], DATE)
    assert steps[0]["action"] == "sell_stock" and steps[0]["qty"] == 100
    assert steps[1]["action"] == "wait_stock_flat" and steps[1]["symbol"] == lot.long_leg.symbol
    inc = B.detect_incidents([{"symbol": lot.long_leg.symbol, "qty": 1}], [lot])
    steps = B.cleanup_plan(inc, [lot], DATE)
    assert [s["action"] for s in steps] == ["sell_to_close_long"] and not steps[0]["urgent"]
    steps = B.cleanup_plan(inc, [lot], "2026-11-18")
    assert steps[0]["urgent"]  # never let an orphan long reach expiry


def test_cleanup_short_stock_is_covered():
    inc = B.detect_incidents([{"symbol": "SPY", "qty": -100}], [], o_stock={"SPY": -100})
    assert B.cleanup_plan(inc, [], DATE)[0]["action"] == "buy_to_cover_stock"


# --- ledger (OPT-7, OPT-16, owner decision 6) -------------------------------------------------------------


def _cand(policy):
    cand, _ = build(policy=policy)
    return cand


def _fill_quotes(short_mid, long_mid, spread=0.02):
    return {"short": {"bid": short_mid - spread / 2, "ask": short_mid + spread / 2},
            "long": {"bid": long_mid - spread / 2, "ask": long_mid + spread / 2}}


def test_partial_fill_books_only_filled(policy):
    led = OptionsBook()
    cand = dict(_cand(policy), contracts=2)
    lot = led.open_spread(cand, {"contracts": 1, "requested": 2, "credit_per_share": 0.58, "order_id": "OPT-1",
                                 "quotes": _fill_quotes(5.0, 4.4), "spot": 769.0}, DATE, policy=policy)
    assert lot.contracts == 1 and lot.short_leg.qty == 1 and lot.long_leg.qty == 1
    assert lot.max_loss == pytest.approx((3 - 0.58) * 100)  # OPT-7: from the actual fill
    assert lot.budgeted_loss == pytest.approx(lot.max_loss + 4.0)
    assert led.events[-1]["remainder_cancelled"] == 1
    row = lot.events[-1]
    assert row["slippage_per_share"] == pytest.approx(0.02) and row["spot_move_pct"] == pytest.approx(769 / 770 - 1)
    # another partial of the same order merges (not an add)
    led.open_spread(cand, {"contracts": 1, "credit_per_share": 0.62, "order_id": "OPT-1"}, DATE, policy=policy)
    assert len(led.lots) == 1 and lot.contracts == 2 and lot.entry_credit_per_share == pytest.approx(0.60)
    assert lot.max_loss == pytest.approx(480.0)


def test_no_fill_books_nothing(policy):
    led = OptionsBook()
    assert led.open_spread(_cand(policy), {"contracts": 0, "credit_per_share": 0.6}, DATE) is None
    assert led.open_spread(_cand(policy), {"contracts": float("nan"), "credit_per_share": 0.6}, DATE) is None
    assert led.open_spread(_cand(policy), {"contracts": 1}, DATE) is None
    assert led.lots == {} and led.events[-1]["kind"] == "entry_not_filled"


def test_credit_from_leg_prices_and_signed_net_price(policy):
    led = OptionsBook()
    a = led.open_spread(_cand(policy), {"contracts": 1, "legs": {"short": 5.0, "long": 4.45}}, DATE)
    assert a.entry_credit_per_share == pytest.approx(0.55)
    b = led.open_spread(_cand(policy), {"contracts": 1, "net_price": -0.57}, DATE)
    assert b.entry_credit_per_share == pytest.approx(0.57)


def test_full_round_trip_costs_twice(policy):
    led = OptionsBook()
    lot = led.open_spread(_cand(policy), {"contracts": 1, "credit_per_share": 0.60, "order_id": "OPT-2",
                                          "quotes": _fill_quotes(5.0, 4.4)}, DATE, policy=policy)
    rec = led.close_spread(lot.lot_id, {"contracts": 1, "debit_per_share": 0.30,
                                        "quotes": _fill_quotes(2.0, 1.7)}, "2026-11-13", B.EXIT_EXPIRY, policy=policy)
    assert rec is not None and led.lots == {} and led.closed == [rec]
    assert rec["realized_pnl"] == pytest.approx(30.0)
    # cost model: half of 0.04 x 100 each side + $0.04 x 2 legs each side
    assert rec["costs"] == pytest.approx(2.0 + 0.08 + 2.0 + 0.08)
    assert rec["pnl"] == pytest.approx(30.0 - 4.16)
    assert rec["R"] == pytest.approx((30.0 - 4.16) / 240.0)
    assert rec["R_paper"] == pytest.approx(30.0 / 240.0)  # paper charges no fees
    assert rec["R_model"] == pytest.approx((0.58 - 0.32) * 100 / 240 - 0.16 / 240)
    assert rec["invested"] == rec["max_loss"] == pytest.approx(240.0)
    assert led.closed_rs() == [pytest.approx(rec["R"])]
    json.dumps(led.to_dict())


def test_partial_close_keeps_rest_open(policy):
    led = OptionsBook()
    cand = dict(_cand(policy), contracts=2)
    lot = led.open_spread(cand, {"contracts": 2, "credit_per_share": 0.60}, DATE)
    assert led.close_spread(lot.lot_id, {"contracts": 1, "debit_per_share": 0.2}, "2026-11-13", "x") is None
    assert lot.contracts == 1 and lot.status == "open" and lot.realized_pnl == pytest.approx(40.0)
    assert lot.max_loss == pytest.approx(480.0)  # R keeps the initial MaxLoss
    rec = led.close_spread(lot.lot_id, {"contracts": 5, "debit_per_share": 0.4}, "2026-11-14", "x")
    assert rec["exit_debit"] == pytest.approx(0.3) and rec["realized_pnl"] == pytest.approx(60.0)


def test_close_unknown_or_unfilled(policy):
    led = OptionsBook()
    assert led.close_spread("nope", {"contracts": 1, "debit_per_share": 0.1}, DATE, "x") is None
    lot = led.open_spread(_cand(policy), {"contracts": 1, "credit_per_share": 0.6}, DATE)
    assert led.close_spread(lot.lot_id, {"contracts": 0, "debit_per_share": 0.1}, DATE, "x") is None
    assert lot.status == "open"


def test_loss_exit_blocks_same_expiry(policy):
    led = OptionsBook()
    lot = led.open_spread(_cand(policy), {"contracts": 1, "credit_per_share": 0.6}, DATE)
    led.close_spread(lot.lot_id, {"contracts": 1, "debit_per_share": 2.0}, "2026-10-20", B.EXIT_SHORT_STRIKE)
    assert led.loss_exit_expiries() == {MONTHLY}
    cand, reasons = build(policy=policy, lots=led.all_lots(), closed=led.closed, week=0)
    assert cand is None and any("OPT-24" in r for r in reasons)
    assert led.week_count(DATE) == 1 and led.week_count("2026-10-26") == 0


def test_save_load_roundtrip(tmp_path, policy):
    led = OptionsBook()
    lot = led.open_spread(_cand(policy), {"contracts": 1, "credit_per_share": 0.6}, DATE, shadow=True)
    led.record_mark(DATE, -10.0)
    led.save(tmp_path)
    assert (tmp_path / "options" / "ledger.json").exists()
    back = OptionsBook.load(tmp_path)
    assert back.lots[lot.lot_id].max_loss == lot.max_loss and back.marks == led.marks
    assert OptionsBook.load(tmp_path / "empty").lots == {}
    assert OptionsBook.from_dict({"unknown": 1}).lots == {}
    assert OptionsBook.from_dict(None).closed == []


def test_invested_and_committed(policy):
    led = OptionsBook()
    led.open_spread(_cand(policy), {"contracts": 1, "credit_per_share": 0.6}, DATE)
    assert led.committed_max_loss() == pytest.approx(240.0)
    assert led.invested_per_trade()[0]["invested"] == pytest.approx(240.0)
    assert led.open_budgeted_loss() == pytest.approx(244.0)


def test_o_value_and_rules_equity(policy):
    led = OptionsBook()
    lot = led.open_spread(_cand(policy), {"contracts": 1, "credit_per_share": 0.6}, DATE)
    at_entry = [q(741, mid=5.0), q(738, mid=4.4)]
    assert o_pnl(led, at_entry) == pytest.approx(0.0)
    assert o_value(led, at_entry) == pytest.approx(240.0)
    assert rules_equity(EQ, led, at_entry) == pytest.approx(EQ - 240.0)
    gained = [q(741, mid=2.0), q(738, mid=1.7)]
    assert o_pnl(led, gained) == pytest.approx(30.0)
    mark = lot_unrealized(lot, [], None)  # no quotes: marked at the width cap (worst case)
    assert mark["unmarked"] and mark["unrealized"] == pytest.approx(-240.0)
    assert o_value(OptionsBook(), []) == 0.0


def test_record_mark_and_peak():
    led = OptionsBook()
    assert led.record_mark("2026-10-16", 50.0) == pytest.approx(50.0)
    assert led.record_mark("2026-10-19", -20.0) == pytest.approx(-70.0)
    assert led.record_mark("2026-10-19", -10.0) == pytest.approx(-60.0)  # same day replaced
    assert led.peak_pnl == 50.0 and len(led.marks) == 2


def test_expiry_worthless(policy):
    led = OptionsBook()
    lot = led.open_spread(_cand(policy), {"contracts": 1, "credit_per_share": 0.6}, DATE)
    assert led.settle_expiry_worthless(lot.lot_id, "2026-11-19", 800) is None  # not expired yet
    assert led.settle_expiry_worthless(lot.lot_id, MONTHLY, 700) is None  # in the money: not worthless
    rec = led.settle_expiry_worthless(lot.lot_id, MONTHLY, 800)
    assert rec["realized_pnl"] == pytest.approx(60.0)


def test_assignment_flow_stock_first_then_long(policy):
    led = OptionsBook()
    lot = led.open_spread(_cand(policy), {"contracts": 1, "credit_per_share": 0.6}, DATE)
    led.record_assignment(lot.lot_id, 1, "2026-11-10")
    assert led.o_stock == {"SPY": 100} and lot.status == "incident" and lot.short_leg.qty == 0
    # O-owned stock is reconciled against the broker's unowned SPY
    pos = [{"symbol": lot.long_leg.symbol, "qty": 1}, {"symbol": "SPY", "qty": 100}]
    inc = B.detect_incidents(pos, led.open_lots(), o_stock=led.o_stock)
    assert inc["freeze"] and not any("ledger" in m for m in inc["mismatches"] if "SPY " in m)
    # the long put cannot be sold before the stock is flat
    assert led.close_orphan_long(lot.lot_id, 1, 1.5, "2026-11-10") is None and lot.long_leg.qty == 1
    mid_mark = lot_unrealized(lot, [q(738, mid=1.5)], 739.0)["unrealized"]
    assert mid_mark == pytest.approx(60 - 200 + 150)
    assert led.record_stock_sale(lot.lot_id, 100, 739.0, "2026-11-10") is None
    assert led.o_stock == {}
    rec = led.close_orphan_long(lot.lot_id, 1, 1.5, "2026-11-10")
    # credit 60 - stock loss 200 + long sale 150 = +10
    assert rec is not None and rec["realized_pnl"] == pytest.approx(10.0) and led.lots == {}


# --- risk.py order check (OPT-3, OPT-5, OPT-14, OPT-15, OPT-24, OPT-42) -----------------------------------


def _open_order(policy, **over):
    o = OR.spread_order(_cand(policy), client_order_id="OPT-2026-10-16-1")
    o.update(over)
    return o


def _check(order, policy, ledger=None, **kw):
    kw.setdefault("date", DATE)
    kw.setdefault("equity", EQ)
    kw.setdefault("uncommitted_cash", CASH)
    return OR.validate_spread_order(order, ledger, policy, **kw)


def test_valid_open_passes_in_shadow(policy):
    ok, reasons = _check(_open_order(policy), policy)
    assert ok, reasons


def test_paper_needs_enabled_and_gate_live_never(policy):
    ok, reasons = _check(_open_order(policy), policy, mode="paper", gate_ok=True)
    assert not ok and any("OPT-1" in r for r in reasons)
    policy["options_book"]["enabled"] = True
    ok, reasons = _check(_open_order(policy), policy, mode="paper")
    assert not ok and any("OPT-41" in r for r in reasons)
    assert _check(_open_order(policy), policy, mode="paper", gate_ok=True, quotes=chain(), spot=SPOT)[0]
    ok, reasons = _check(_open_order(policy), policy, mode="paper", gate_ok=True)
    assert not ok and any("OPT-10" in r for r in reasons)  # paper needs quotes + spot for the greek caps
    ok, reasons = _check(_open_order(policy), policy, mode="live", gate_ok=True)
    assert not ok and any("OPT-42" in r for r in reasons)
    assert not _check(_open_order(policy), policy, mode="bogus")[0]


def _leg(sym, intent, side=None):
    return {"symbol": sym, "position_intent": intent, "side": side or ("buy" if intent.startswith("buy") else "sell"),
            "ratio_qty": 1}


S741 = occ_symbol("SPY", MONTHLY, "put", 741)
S738 = occ_symbol("SPY", MONTHLY, "put", 738)


@pytest.mark.parametrize("legs, word", [
    ([_leg(S741, "sell_to_open"), _leg(S738, "sell_to_open")], "naked short"),
    ([_leg(S741, "sell_to_open")], "single-leg"),
    ([_leg(S741, "sell_to_open"), _leg(S738, "buy_to_open"), _leg(occ_symbol("SPY", MONTHLY, "put", 735),
                                                                   "buy_to_open")], "3 legs"),
    ([_leg(S741, "sell_to_open"), _leg(occ_symbol("SPY", "2026-12-18", "put", 738), "buy_to_open")], "expiry"),
    ([_leg(S741, "sell_to_open"), _leg(occ_symbol("SPY", MONTHLY, "call", 738), "buy_to_open")], "type"),
    ([_leg(S741, "sell_to_open"), _leg(occ_symbol("QQQ", MONTHLY, "put", 738), "buy_to_open")], "underlying"),
    ([_leg(S741, "sell_to_open"), _leg("SPY", "buy_to_open")], "equity legs"),
    ([_leg(S741, "sell_to_open"), _leg(S738, "buy_to_close")], "short leg"),
    ([_leg(S741, "sell_to_open"), _leg(S741, "buy_to_open")], "same strike"),
])
def test_bad_leg_shapes_rejected(legs, word, policy):
    ok, reasons = _check(_open_order(policy, legs=legs), policy)
    assert not ok and any(word in r for r in reasons), reasons


def test_ratio_must_be_one(policy):
    o = _open_order(policy)
    o["legs"][1]["ratio_qty"] = 2
    ok, reasons = _check(o, policy)
    assert not ok and any("1:1" in r for r in reasons)


def test_sign_checks(policy):
    ok, reasons = _check(_open_order(policy, limit_price=0.55), policy)
    assert not ok and any("negative limit" in r for r in reasons)
    ok, reasons = _check(_open_order(policy, limit_price=0), policy)
    assert not ok
    ok, reasons = _check(_open_order(policy, limit_price=-3.0), policy)
    assert not ok and any("width" in r for r in reasons)


def test_order_basics(policy):
    for over, word in [({"type": "market"}, "limit orders"), ({"time_in_force": "gtc"}, "DAY"),
                       ({"extended_hours": True}, "extended"), ({"qty": 1.5}, "whole"), ({"qty": 0}, "whole"),
                       ({"client_order_id": "rules-1"}, "OPT-"), ({"order_class": "simple"}, "mleg")]:
        ok, reasons = _check(_open_order(policy, **over), policy)
        assert not ok and any(word in r for r in reasons), (over, reasons)
    assert OR.validate_spread_order("junk", None, policy) == (False, ["order is not a dict"])


def test_entry_dte_and_date(policy):
    exp = "2026-11-06"
    legs = [_leg(occ_symbol("SPY", exp, "put", 741), "sell_to_open"), _leg(occ_symbol("SPY", exp, "put", 738),
                                                                           "buy_to_open")]
    ok, reasons = _check(_open_order(policy, legs=legs), policy)  # DTE 21
    assert not ok and any("OPT-5" in r for r in reasons)
    ok, reasons = _check(_open_order(policy), policy, date=None)
    assert not ok and any("date needed" in r for r in reasons)


def test_non_spy_paper_rejected_shadow_allowed(policy):
    legs = [_leg(occ_symbol("QQQ", MONTHLY, "put", 600), "sell_to_open"),
            _leg(occ_symbol("QQQ", MONTHLY, "put", 597), "buy_to_open")]
    assert _check(_open_order(policy, legs=legs), policy)[0]
    policy["options_book"]["enabled"] = True
    ok, reasons = _check(_open_order(policy, legs=legs), policy, mode="paper", gate_ok=True)
    assert not ok and any("OPT-4" in r for r in reasons)
    debit = [_leg(S741, "buy_to_open"), _leg(S738, "sell_to_open")]  # bear put debit spread
    assert _check(_open_order(policy, legs=debit, limit_price=1.0), policy)[0]
    ok, reasons = _check(_open_order(policy, legs=debit, limit_price=1.0), policy, mode="paper", gate_ok=True)
    assert not ok and any("OPT-18" in r for r in reasons)


def test_size_caps_in_order_check(policy):
    ok, reasons = _check(_open_order(policy, qty=2), policy)
    assert not ok and any("OPT-8" in r for r in reasons)
    ok, reasons = _check(_open_order(policy), policy, equity=None)
    assert not ok and any("equity unknown" in r for r in reasons)
    ok, reasons = _check(_open_order(policy), policy, uncommitted_cash=50_000)
    assert not ok and any("assignment" in r for r in reasons)
    lots = [make_lot(expiry=e, lot_id=e, budget=300) for e in ("2026-12-18", "2027-01-15", "2027-02-19")]
    ok, reasons = _check(_open_order(policy), policy, ledger=lots, uncommitted_cash=10_000_000)
    assert not ok and any("already 3 open" in r for r in reasons) and any("book cap" in r for r in reasons)
    o = _open_order(policy)
    o.pop("budgeted_loss_per_contract")
    o["quoted_cost"] = None
    assert _check(o, policy)[0]  # falls back to MaxLoss from the limit


def test_no_adding_or_second_after_loss(policy):
    lot = make_lot()
    ok, reasons = _check(_open_order(policy), policy, ledger=[lot], uncommitted_cash=10_000_000)
    assert not ok and any("OPT-24" in r for r in reasons)
    led = OptionsBook(closed=[{"expiry": MONTHLY, "pnl": -10.0, "lot_id": "x", "entry_date": DATE,
                               "max_loss": 1.0}])
    ok, reasons = _check(_open_order(policy), policy, ledger=led)
    assert not ok and any("loss exit" in r for r in reasons)


def _close_order(lot, qty=1, limit=0.5):
    return {"legs": [_leg(lot.short_leg.symbol, "buy_to_close"), _leg(lot.long_leg.symbol, "sell_to_close")],
            "qty": qty, "limit_price": limit, "intent": "close", "order_class": "mleg", "type": "limit",
            "time_in_force": "day", "client_order_id": "OPT-close-1"}


def test_close_orders(policy):
    lot = make_lot()
    assert _check(_close_order(lot), policy, ledger=[lot], equity=None, date=None)[0]
    ok, reasons = _check(_close_order(lot, limit=-0.5), policy, ledger=[lot])
    assert not ok and any("positive limit" in r for r in reasons)
    ok, reasons = _check(_close_order(lot, limit=3.05), policy, ledger=[lot])
    assert not ok and any("OPT-15" in r for r in reasons)
    ok, reasons = _check(_close_order(lot, qty=2), policy, ledger=[lot])
    assert not ok and any("exceeds" in r for r in reasons)
    ok, reasons = _check(_close_order(lot), policy, ledger=[])
    assert not ok and any("does not match" in r for r in reasons)
    flipped = _close_order(lot)
    flipped["legs"] = [_leg(lot.short_leg.symbol, "sell_to_close"), _leg(lot.long_leg.symbol, "buy_to_close")]
    ok, reasons = _check(flipped, policy, ledger=[lot])
    assert not ok and any("flip" in r for r in reasons)
    ok, reasons = _check(_close_order(lot), policy, ledger=[lot], mode="live")
    assert not ok and any("OPT-42" in r for r in reasons)
    wrong = _close_order(lot)
    wrong["intent"] = "open"
    assert not _check(wrong, policy, ledger=[lot])[0]


def test_close_accepts_options_book_ledger(policy):
    led = OptionsBook()
    lot = led.open_spread(_cand(policy), {"contracts": 1, "credit_per_share": 0.6}, DATE)
    assert _check(_close_order(lot), policy, ledger=led)[0]


def test_spread_order_shape(policy):
    o = OR.spread_order(_cand(policy), client_order_id="OPT-x")
    assert o["limit_price"] < 0 and o["qty"] == 1 and len(o["legs"]) == 2
    assert {l["position_intent"] for l in o["legs"]} == {"sell_to_open", "buy_to_open"}
    c = OR.spread_order(_cand(policy), intent="close", limit_price=0.4, client_order_id="OPT-y")
    assert {l["position_intent"] for l in c["legs"]} == {"buy_to_close", "sell_to_close"}


# --- OPT-2: the stock path still rejects OCC symbols ------------------------------------------------------


def test_stock_path_rejects_occ_symbols(cfg, bars):
    from trader.models import Target
    from trader.risk import RiskEngine, breaker_status
    brk = breaker_status(cfg, 10000, 10000, 0.0, 0.0, False, False)
    bars = dict(bars)
    bars[S741] = next(iter(bars.values()))  # a price exists, so only the allowlist can stop it
    res = RiskEngine(cfg).apply([Target(S741, "C", 1, 1.0)], {}, {S741: -1}, bars, 10000, brk)
    assert res.orders == []
    assert any(S741 in line and "not on the allowlist" in line for line in res.log), res.log
    assert cfg.policy["account"]["options"] is False


def test_spreadlot_from_old_dict_roundtrip():
    lot = make_lot()
    d = lot.to_dict()
    d["new_future_field"] = 1
    back = SpreadLot.from_dict(json.loads(json.dumps(d)))
    assert back.short_leg.strike == 741.0 and math.isclose(back.max_loss, lot.max_loss)


# --- review fixes ------------------------------------------------------------------------------------------


def test_opt23_inside_opt22_window_is_forced_to_natural(policy):
    lot = make_lot()
    day = "2026-11-14"  # DTE 6, SPY below the 741 short strike
    why = B.exit_signal(lot, [], 700.0, day, policy)
    assert why == B.EXIT_EXPIRY_ITM and B.is_forced(why, B.dte(lot.expiry, day), policy)
    qs = _lot_quotes(quote_time="2026-11-14T19:50:00Z")
    d = B.ladder_detail(lot, qs, 1, policy, forced=B.is_forced(why), date=day)
    assert d["limit_price"] == pytest.approx(0.60) and d["basis"] == "natural"
    assert B.exit_signal(lot, [], SPOT, day, policy) == B.EXIT_EXPIRY  # above the strike: plain OPT-22


def test_stale_exit_quotes_price_at_width_cap(policy):
    lot = make_lot()
    d = B.ladder_detail(lot, _lot_quotes(), 1, policy, date="2026-10-19")  # quotes from 10-16
    assert d["limit_price"] == 3.0 and "stale" in d["basis"]
    d = B.ladder_detail(lot, _lot_quotes(quote_time=None), 1, policy, date=DATE)
    assert d["limit_price"] == 3.0 and d["capped"]
    assert B.ladder_detail(lot, _lot_quotes(), 1, policy, date=DATE)["basis"] == "mid"


def test_ob_policy_never_uses_stock_breakers_and_merges_nested(policy):
    full = copy.deepcopy(policy)
    full.pop("options_book")
    assert B.ob_policy(full)["breakers"] == B.DEFAULTS["breakers"]
    assert "OPT-30" in B.daily_loss_breaker(-600, EQ, full)
    part = B.ob_policy({"breakers": {"dd_halve": 0.02}})
    assert part["breakers"]["daily_loss_pct"] == 0.005 and part["breakers"]["dd_halve"] == 0.02
    assert B.drawdown_state(-1000, 0, EQ, {"breakers": {"dd_halve": 0.015}})["cap_mult"] == 1.0  # no KeyError
    assert B.permission("bull_volatile", {"permission": {"bull_calm": 1.0}}) == 0.0  # not merged: missing -> 0


def test_second_spread_after_profitable_exit_is_blocked(policy):
    led = OptionsBook()
    lot = led.open_spread(_cand(policy), {"contracts": 1, "credit_per_share": 0.6}, DATE)
    rec = led.close_spread(lot.lot_id, {"contracts": 1, "debit_per_share": 0.1}, DATE, "x")
    assert rec["pnl"] > 0
    cand, reasons = build(policy=policy, lots=led.open_lots(), closed=led.closed, week=0)
    assert cand is None and any("OPT-18" in r for r in reasons), reasons


def test_week_count_none_counts_closed_records(policy):
    led = OptionsBook()
    lot = led.open_spread(_cand(policy), {"contracts": 1, "credit_per_share": 0.6}, "2026-10-13")
    led.close_spread(lot.lot_id, {"contracts": 1, "debit_per_share": 0.1}, "2026-10-14", "x")
    assert B.new_this_week(led.open_lots(), DATE, led.closed) == 1
    assert B.new_this_week(led.all_lots(), DATE, led.closed) == 1  # no double count
    cand, reasons = build(policy=policy, lots=led.open_lots(), closed=led.closed, week=None)
    assert cand is None and any("OPT-9" in r and "this week" in r for r in reasons)


def test_shadow_round_trip_r_equals_r_model_no_double_count(policy):
    led = OptionsBook()
    cand = _cand(policy)
    lot = led.open_spread(cand, {"contracts": 1, "credit_per_share": 0.58, "quotes": _fill_quotes(5.0, 4.4)},
                          DATE, policy=policy)  # OPT-36: mid 0.60 - half the quoted cost 0.04
    rec = led.close_spread(lot.lot_id, {"contracts": 1, "debit_per_share": 0.32, "quotes": _fill_quotes(2.0, 1.7)},
                           "2026-11-13", B.EXIT_EXPIRY, policy=policy)
    ml = (3 - 0.58) * 100
    assert rec["R"] == pytest.approx(rec["R_model"]) == pytest.approx((26.0 - 0.16) / ml)
    assert rec["R_paper"] == pytest.approx(26.0 / ml)
    assert rec["pnl"] == pytest.approx(25.84)  # not 26 - 4.16: the spread is not charged twice
    assert led.closed_rs() == [pytest.approx(rec["R_model"])]


def test_partial_close_releases_committed_maxloss(policy):
    led = OptionsBook()
    cand = dict(_cand(policy), contracts=2)
    lot = led.open_spread(cand, {"contracts": 2, "credit_per_share": 0.60}, DATE)
    at_entry = [q(741, mid=5.0), q(738, mid=4.4)]
    before = rules_equity(EQ, led, at_entry)
    assert led.committed_max_loss() == pytest.approx(480.0)
    led.close_spread(lot.lot_id, {"contracts": 1, "debit_per_share": 0.60}, DATE, "x")  # flat trade
    assert lot.max_loss == pytest.approx(480.0)  # R keeps the entry MaxLoss
    assert led.committed_max_loss() == pytest.approx(240.0)
    assert led.open_budgeted_loss() == pytest.approx(lot.budgeted_loss / 2)
    assert B.open_budgeted_loss(led.open_lots()) == pytest.approx(lot.budgeted_loss / 2)
    assert led.invested_per_trade()[0]["committed"] == pytest.approx(240.0)
    assert rules_equity(EQ, led, at_entry) == pytest.approx(before + 240.0)


def test_cumulative_filled_qty_and_duplicate_fills(policy):
    led = OptionsBook()
    cand = dict(_cand(policy), contracts=3)
    lot = led.open_spread(cand, {"order_id": "A", "filled_qty": 1, "requested": 3, "net_price": -0.60}, DATE)
    assert lot.contracts == 1
    # Alpaca running total 3 at an average credit 0.62: the new 2 contracts filled at 0.63
    assert led.open_spread(cand, {"order_id": "A", "filled_qty": 3, "net_price": -0.62}, DATE) is lot
    assert lot.contracts == 3 and lot.entry_credit_per_share == pytest.approx(0.62)
    assert lot.max_loss == pytest.approx((3 - 0.62) * 300)
    led.open_spread(cand, {"order_id": "A", "filled_qty": 3, "net_price": -0.62}, DATE)  # same report again
    assert lot.contracts == 3 and led.events[-1]["kind"] == "duplicate_fill"
    b = led.open_spread(cand, {"contracts": 1, "credit_per_share": 0.6, "fill_id": "F1"}, DATE)
    led.open_spread(cand, {"contracts": 1, "credit_per_share": 0.6, "fill_id": "F1"}, DATE)
    assert b.contracts == 1
    assert led.close_spread(lot.lot_id, {"order_id": "C", "filled_qty": 1, "net_price": 0.3}, DATE, "x") is None
    assert led.close_spread(lot.lot_id, {"order_id": "C", "filled_qty": 1, "net_price": 0.3}, DATE, "x") is None
    assert lot.contracts == 2
    rec = led.close_spread(lot.lot_id, {"order_id": "C", "filled_qty": 3, "net_price": 0.3}, DATE, "x")
    assert rec is not None and rec["contracts"] == 3


def test_halt_latch_holds_until_owner_reset(policy):
    led = OptionsBook()
    st = led.apply_breakers(day_pnl=0, o_pnl=-2500, equity=EQ, date=DATE, policy=policy)
    assert st["halt"] and led.halted
    st = led.apply_breakers(day_pnl=2500, o_pnl=0, equity=EQ, date=DATE, policy=policy)  # drawdown recovered
    assert st["halt"] and st["no_new_entries"] and led.halted
    led.reset_halt(DATE)
    assert not led.apply_breakers(day_pnl=0, o_pnl=0, equity=EQ, policy=policy)["halt"]


def test_fill_rows_log_leg_quotes_and_unknown_slippage(policy):
    led = OptionsBook()
    cand = _cand(policy)
    lot = led.open_spread(cand, {"contracts": 1, "credit_per_share": 0.6}, DATE)
    dec = lot.events[-1]["decision"]
    assert dec["short"]["bid"] == cand["short"]["bid"] and dec["long"]["ask"] == cand["long"]["ask"]
    assert dec["short"]["mid"] == pytest.approx(cand["short"]["mid"])
    led.close_spread(lot.lot_id, {"contracts": 1, "debit_per_share": 0.3, "decision_spot": 760.0,
                                  "decision_quotes": {"short": {"bid": 1.9, "ask": 2.1}, "long": None}}, DATE, "x")
    row = led.closed[-1]["lot"]["events"][-1]
    assert row["slippage_per_share"] is None and row["slippage_dollars"] is None
    assert row["decision"]["short"]["bid"] == 1.9 and row["decision"]["spot"] == 760.0


def test_cleanup_never_trades_stock_o_does_not_own():
    inc = B.detect_incidents([{"symbol": "AAPL", "qty": "10"}], [], other_books_stock={}, o_stock={})
    steps = B.cleanup_plan(inc, [], DATE)
    assert [s["action"] for s in steps] == ["owner_review_stock"]
    lot = make_lot()
    pos = [{"symbol": lot.long_leg.symbol, "qty": 1}, {"symbol": "SPY", "qty": 150}]
    steps = B.cleanup_plan(B.detect_incidents(pos, [lot], o_stock={"SPY": 100}), [lot], DATE)
    assert [(s["action"], s["qty"]) for s in steps] == [("sell_stock", 100), ("owner_review_stock", 50),
                                                        ("wait_stock_flat", 1)]
    # stock the ledger has not booked yet (an assignment not recorded): the long put still waits
    steps = B.cleanup_plan(B.detect_incidents(pos, [lot]), [lot], DATE)
    assert "sell_stock" not in [s["action"] for s in steps] and steps[-1]["action"] == "wait_stock_flat"


def test_validator_computes_budget_and_ignores_order_cap_mult(policy):
    ok, reasons = _check(_open_order(policy, qty=2, budgeted_loss_per_contract=1.0), policy)
    assert not ok and any("OPT-8" in r for r in reasons)
    ok, reasons = _check(_open_order(policy, qty=2, cap_mult=10), policy)
    assert not ok and any("OPT-8" in r for r in reasons)
    ok, reasons = _check(_open_order(policy, qty=2), policy, cap_mult=10)  # clamped to 1
    assert not ok and any("OPT-8" in r for r in reasons)
    ok, reasons = _check(_open_order(policy), policy, cap_mult=0.5)  # OPT-31 halves the cap to 125
    assert not ok and any("OPT-8" in r for r in reasons)
    o = _open_order(policy, budgeted_loss_per_contract=None, quoted_cost=None)
    assert _check(o, policy)[0]


def test_validator_book_gates(policy):
    led = OptionsBook(halted=True)
    ok, reasons = _check(_open_order(policy), policy, ledger=led)
    assert not ok and any("OPT-31" in r for r in reasons)
    ok, reasons = _check(_open_order(policy), policy, blocks=["OPT-30: daily loss"])
    assert not ok and any("OPT-30" in r for r in reasons)
    week = OptionsBook(closed=[{"expiry": "2026-12-18", "pnl": 5.0, "lot_id": "w", "entry_date": DATE}])
    ok, reasons = _check(_open_order(policy), policy, ledger=week)
    assert not ok and any("this week" in r for r in reasons)
    # one spread per cycle: a profitable exit in the same expiry, next week
    led = OptionsBook()
    lot = led.open_spread(_cand(policy), {"contracts": 1, "credit_per_share": 0.6}, DATE)
    led.close_spread(lot.lot_id, {"contracts": 1, "debit_per_share": 0.1}, DATE, "x")
    ok, reasons = _check(_open_order(policy), policy, ledger=led, date="2026-10-19")
    assert not ok and any("OPT-18" in r for r in reasons) and not any("this week" in r for r in reasons)
    # a second open spread in the same expiry with other strikes
    other = make_lot(short=735, lot_id="L2", entry_date="2026-10-09")
    ok, reasons = _check(_open_order(policy), policy, ledger=[other], uncommitted_cash=10_000_000)
    assert not ok and any("OPT-18" in r for r in reasons)


def test_validator_greek_caps(policy):
    order = _open_order(policy)
    assert _check(order, policy, quotes=chain(), spot=SPOT)[0]
    policy["options_book"]["max_delta_notional_pct"] = 0.01  # 1,000 < 0.03 x 100 x 770
    ok, reasons = _check(order, policy, quotes=chain(), spot=SPOT)
    assert not ok and any("OPT-10" in r for r in reasons)
    ok, reasons = _check(order, policy, quotes=[], spot=SPOT)
    assert not ok and any("missing" in r for r in reasons)


def test_paper_close_needs_enabled_and_gate(policy):
    lot = make_lot()
    ok, reasons = _check(_close_order(lot), policy, ledger=[lot], mode="paper", gate_ok=True)
    assert not ok and any("OPT-1" in r for r in reasons)
    policy["options_book"]["enabled"] = True
    ok, reasons = _check(_close_order(lot), policy, ledger=[lot], mode="paper")
    assert not ok and any("OPT-41" in r for r in reasons)
    assert _check(_close_order(lot), policy, ledger=[lot], mode="paper", gate_ok=True)[0]


def test_debit_spread_sign_and_size(policy):
    debit = [_leg(S741, "buy_to_open"), _leg(S738, "sell_to_open")]
    base = dict(legs=debit, limit_price=0.5, budgeted_loss_per_contract=None, quoted_cost=0.04)
    ok, reasons = _check(_open_order(policy, qty=4, **base), policy, uncommitted_cash=10_000_000)
    assert ok, reasons  # MaxLoss = debit: 4 x (50 + 4) = 216 <= 250
    ok, reasons = _check(_open_order(policy, qty=5, **base), policy, uncommitted_cash=10_000_000)
    assert not ok and any("OPT-8" in r for r in reasons)
    ok, reasons = _check(_open_order(policy, **dict(base, limit_price=3.0)), policy)
    assert not ok and any("width" in r for r in reasons)
    close = [_leg(S741, "sell_to_close"), _leg(S738, "buy_to_close")]
    ok, reasons = _check(_open_order(policy, legs=close, intent="close", limit_price=5.0), policy)
    assert not ok and any("closing a debit spread" in r for r in reasons)
    ok, reasons = _check(_open_order(policy, legs=close, intent="close", limit_price=-5.0), policy)
    assert not ok and any("above the width" in r for r in reasons)
