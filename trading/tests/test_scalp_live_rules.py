"""Live paper minute trader, section A pure rules (lab/scalp/live): config, registry, clock, events, sizing,
orders, costs, risk, gates, journal. All offline: no network, no keys, no system clock."""
import dataclasses
import inspect
import json
import re
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lab.scalp.live import clock as K
from lab.scalp.live import config as C
from lab.scalp.live import costs as X
from lab.scalp.live import events as E
from lab.scalp.live import gates as G
from lab.scalp.live import journal as J
from lab.scalp.live import orders as O
from lab.scalp.live import risk as R
from lab.scalp.live import sizing as S
from lab.scalp.live.model import (Bar, Candidate, DayCounters, Feed, Kind, Lane, LastTrade, Mode, OrderSpec, Quote,
                                  Reason, SlotState, as_ny)

LIVE = Path(C.__file__).resolve().parent
D = date(2026, 10, 1)
REG = C.load_registry()
ORB5, LAST30, NOISE = REG.get("ORB5_QQQ", "QQQ"), REG.get("LAST30_MOM_SPY", "SPY"), REG.get("NOISE_MOM_SPY", "SPY")
KNOWN = E.DayEvents(known=True)


def ts(hms, d=D):
    return as_ny(f"{d.isoformat()} {hms}")


def session(d=D, close="16:00"):
    return K.SessionTimes.from_calendar(d, ts("09:30", d), ts(close, d))


# ============================================================================================ config (MT-G41)
EXPECTED = dict(
    ALLOWED_SYMBOLS=("SPY", "QQQ"), SHORTS_ENABLED=False, MAX_ROUND_TRIPS_DAY=4, MAX_ROUND_TRIPS_SETUP=2,
    MAX_OPEN_POSITIONS=1, MAX_ENTRY_SUBMITS_DAY=8, MAX_ENTRY_SUBMITS_PER_MIN=6, MAX_OPEN_PARENTS=1,
    MAX_NOTIONAL_DAY_X_E0=4.0, MAX_EXIT_ORDERS_PER_MIN=30, RISK_PCT=0.001, NOTIONAL_CAP_PCT=0.10,
    EXPLORATORY_MAX_QTY=1, GROSS_NOTIONAL_MAX_X_E0=1.0, DAILY_STOP_USD=25.0, DAILY_STOP_PCTS=(0.005, 0.01),
    WEEKLY_STOP_PCT=0.02, DRAWDOWN_HALT_PCT=0.05, TEST_STOP_USD=150.0, TEST_MAX_SESSIONS=60, LOSS_STREAK_N=3,
    LOSS_STREAK_PAUSE_MIN=30, STOPOUT_REENTRY_MIN=15, ENTRY_COLLAR_USD=0.02, ENTRY_COLLAR_PCT=0.0005,
    STOP_LIMIT_MIN_USD=0.05, STOP_LIMIT_FRAC=0.5, EXIT_COLLARS=(0.0005, 0.002, 0.005),
    KILL_COLLARS=(0.002, 0.005, 0.01), STOP_WATCHDOG_S=10, STOP_ESCALATION_TRIES=3, ENTRY_TIMEOUT_S=2,
    STOP_CONFIRM_S=5, EXIT_ACK_S=5, CANCEL_CONFIRM_S=5, OPEN_BLOCK_MIN=15, ENTRY_CUTOFF_MIN_BEFORE_CLOSE=29,
    FLATTEN_MIN_BEFORE_CLOSE=10, KILL_MIN_BEFORE_CLOSE=5, WATCHDOG_FLAT_MIN_BEFORE_CLOSE=3,
    RELEASE_BLOCK_BEFORE_MIN=2, RELEASE_BLOCK_AFTER_MIN=5, FOMC_BLOCK=("13:58", "15:30:59"), CLOCK_OFFSET_MS=100,
    DATA_SILENCE_S=2, QUOTE_MAX_AGE_S=2, BAR_MAX_AGE_S=65, MAX_SPREAD_USD=0.02, MAX_SPREAD_BPS=5.0,
    MAX_PRICE_VS_LAST_TRADE=0.005, WILD_MINUTE_RANGE=0.01, WILD_MINUTE_PAUSE_MIN=10, LULD_PCT=0.05,
    MWCB_DROP=0.07, RECONCILE_EVERY_S=5, RECONCILE_IDLE_EVERY_S=30, MISMATCH_CONFIRM_CHECKS=2,
    MISMATCH_MIN_GAP_S=3, HONEST_SLIP_PER_SHARE=0.01, HEARTBEAT_STALE_S=30, WATCHDOG_EVERY_S=15,
    MIN_SAMPLE_TRADES=100, MIN_SAMPLE_SESSIONS=40, SWITCH_OFF_N=30, RETIRE_N=100, ORDER_PREFIX="SCALP-",
    SETUP_CODES={"ORB5_QQQ": "ORB5Q", "LAST30_MOM_SPY": "L30S", "NOISE_MOM_SPY": "NOISES"},
    STOP_ESCALATION_COLLARS=(0.002, 0.005, 0.01), CANCEL_GIVE_UP_X=3, HTTP_TIMEOUT_S=5.0, LOCK_WAIT_S=10.0,
    SLIP_MODEL_RAISE_X=1.5, SLIP_MODEL_STOP_X=2.0, SLIP_MIN_FILLS=30, VERSION_MIN_SESSIONS=20)


def test_mt_g41_every_guardrail_constant_is_locked():
    for name, want in EXPECTED.items():
        got = getattr(C, name)
        assert got == want and type(got) is type(want), f"{name} changed: {got!r} != {want!r} (MT-G41)"


def test_mt_g41_risk_hash_is_stable_and_covers_the_risk_files():
    h = C.risk_hash()
    assert re.fullmatch(r"[0-9a-f]{64}", h) and h == C.risk_hash()
    assert C.RISK_FILES == ("config.py", "risk.py", "sizing.py", "orders.py")
    assert all((LIVE / f).exists() for f in C.RISK_FILES)


def test_mt_g10_code_hash_changes_with_params_and_files(tmp_path):
    a, b = tmp_path / "a.py", tmp_path / "b.py"
    a.write_text("x = 1\n")
    b.write_text("y = 2\n")
    h = C.code_hash([str(a), str(b)], {"p": 1})
    assert h == C.code_hash([str(a), str(b)], {"p": 1})
    assert h != C.code_hash([str(a), str(b)], {"p": 2})
    assert h != C.code_hash([str(b), str(a)], {"p": 1})
    a.write_text("x = 3\n")
    assert h != C.code_hash([str(a), str(b)], {"p": 1})
    with pytest.raises(OSError):
        C.code_hash([str(tmp_path / "missing.py")], {})


def test_mt_g10_committed_registry_hashes_equal_the_code():
    for r in REG:
        assert r.code_hash == C.code_hash(list(r.code_files), r.params), (
            f"{r.setup_id}: signals/sizing/orders changed since registration. A changed hash is a new version "
            "(MT-G10); during the v1 build run config.rehash_registry().")
    assert REG.hash_mismatches() == []


def test_mt_g10_a_changed_parameter_is_caught(tmp_path):
    raw = json.loads(C.REGISTRY_PATH.read_text())
    raw["setups"][1]["params"]["overlay_stop_pct"] = 0.004
    p = tmp_path / "reg.json"
    p.write_text(json.dumps(raw))
    reg = C.load_registry(p)
    assert [r.setup_id for r in reg.hash_mismatches()] == ["LAST30_MOM_SPY"]


# ============================================================================================ registry
def test_registry_holds_the_three_exploratory_v1_setups():
    assert [(r.setup_id, r.symbol) for r in REG] == [("ORB5_QQQ", "QQQ"), ("LAST30_MOM_SPY", "SPY"),
                                                     ("NOISE_MOM_SPY", "SPY")]
    for r in REG:
        assert r.version == 1 and r.lane is Lane.EXPLORATORY and r.source.strip() and r.deviations
        assert r.code_files == ("lab/scalp/signals.py", "lab/scalp/live/sizing.py", "lab/scalp/live/orders.py")
        assert r.feed_live == "IEX" and r.feed_backtest == "SIP" and r.feed_mismatch
        assert r.labels() == {"setup_id": r.setup_id, "version": 1, "lane": "EXPLORATORY", "feed": "IEX",
                              "code_hash": r.code_hash}                     # MT-G10: the hash on every line
        assert r.model_slip_bps == 1.5 and r.uses_volume is (r.setup_id == "NOISE_MOM_SPY")
    assert ORB5.opening_window and ORB5.tested_on_release_days
    assert ORB5.overlay_stop_pct is None and ORB5.overlay_target_pct is None
    assert not LAST30.opening_window and not NOISE.opening_window
    for r in (LAST30, NOISE):
        assert (r.overlay_stop_pct, r.overlay_target_pct) == (0.005, 0.01)
    assert REG.account_last4 == "GWRL" and REG.test_start is None
    assert REG.get("ORB5_QQQ", "SPY") is None and [r.setup_id for r in REG.for_symbol("SPY")] == [
        "LAST30_MOM_SPY", "NOISE_MOM_SPY"]


def _reg_file(tmp_path, **change):
    raw = json.loads(C.REGISTRY_PATH.read_text())
    raw["setups"][0].update(change)
    p = tmp_path / "reg.json"
    p.write_text(json.dumps(raw))
    return p


def test_mt_g24_empty_source_is_refused(tmp_path):
    with pytest.raises(C.RegistryError, match="MT-G24"):
        C.load_registry(_reg_file(tmp_path, source="  "))


def test_mt_g23_symbol_outside_the_allowlist_is_refused(tmp_path):
    with pytest.raises(C.RegistryError, match="MT-G23"):
        C.load_registry(_reg_file(tmp_path, symbol="GME"))


@pytest.mark.parametrize("report", [None, {"passed": False}, {"passed": True}])
def test_validated_lane_is_impossible_in_v1(tmp_path, report):
    with pytest.raises(C.RegistryError, match="VALIDATED"):
        C.load_registry(_reg_file(tmp_path, lane="VALIDATED", validated_report=report))


@pytest.mark.parametrize("change", [{"setup_id": "NOT_A_SETUP"}, {"setup_id": "VWAP_TREND_QQQ"},
                                    {"lane": "YOLO"}, {"version": 0},
                                    {"params": {"overlay_stop_pct": 0.005, "overlay_target_pct": None}}])
def test_registry_refuses_unknown_setups_and_bad_fields(tmp_path, change):
    with pytest.raises(C.RegistryError):
        C.load_registry(_reg_file(tmp_path, **change))


def test_registry_refuses_a_duplicate(tmp_path):
    raw = json.loads(C.REGISTRY_PATH.read_text())
    raw["setups"].append(raw["setups"][0])
    p = tmp_path / "reg.json"
    p.write_text(json.dumps(raw))
    with pytest.raises(C.RegistryError, match="twice"):
        C.load_registry(p)


# ============================================================================================ clock (MT-G20)
def test_mt_g20_session_times_on_a_normal_day():
    st = session()
    assert not st.half_day
    assert (st.open_block_end, st.entry_cutoff, st.flatten_at, st.kill_at, st.watchdog_flat_at) == (
        ts("09:45"), ts("15:31"), ts("15:50"), ts("15:55"), ts("15:57"))


def test_mt_g20_half_day_moves_the_flatten_to_1250():
    st = session(date(2026, 11, 27), close="13:00")
    assert st.half_day
    assert (st.entry_cutoff, st.flatten_at, st.kill_at) == (ts("12:31", st.date), ts("12:50", st.date),
                                                            ts("12:55", st.date))
    assert Reason.HALF_DAY in K.clock_reasons(ts("11:00", st.date), st, LAST30, KNOWN)


def test_mt_g20_0940_entry_rejected_without_an_opening_registration():
    assert K.clock_reasons(ts("09:40"), session(), NOISE, KNOWN) == [Reason.OPENING_BLOCK]
    assert K.clock_reasons(ts("09:44:59"), session(), NOISE, KNOWN) == [Reason.OPENING_BLOCK]
    assert K.clock_reasons(ts("09:45"), session(), NOISE, KNOWN) == []
    assert Reason.OPENING_BLOCK in K.clock_reasons(ts("09:40"), session(), None, KNOWN)


def test_mt_g20_orb5_at_0935_is_allowed():
    assert K.clock_reasons(ts("09:35:01"), session(), ORB5, KNOWN) == []


def test_mt_g20_opening_window_on_an_0830_release_day_needs_release_day_testing():
    ev = E.DayEvents(known=True, release_0830=["CPI"])
    assert K.clock_reasons(ts("09:35:01"), session(), ORB5, ev) == []
    untested = replace(ORB5, tested_on_release_days=False)
    assert K.clock_reasons(ts("09:35:01"), session(), untested, ev) == [Reason.OPENING_BLOCK]
    assert K.clock_reasons(ts("09:35:01"), session(), untested, KNOWN) == []


def test_mt_g20_1531_rejected_and_153030_allowed():
    st = session()
    assert K.clock_reasons(ts("15:30:30"), st, LAST30, KNOWN) == []
    assert K.clock_reasons(ts("15:30:59.999"), st, LAST30, KNOWN) == []
    assert K.clock_reasons(ts("15:31"), st, LAST30, KNOWN) == [Reason.AFTER_ENTRY_CUTOFF]
    assert K.clock_reasons(ts("15:50"), st, LAST30, KNOWN) == [Reason.AFTER_ENTRY_CUTOFF, Reason.FLATTEN_WINDOW]


def test_mt_g20_market_closed_outside_the_session():
    st = session()
    assert Reason.MARKET_CLOSED in K.clock_reasons(ts("09:29:59"), st, ORB5, KNOWN)
    assert Reason.MARKET_CLOSED in K.clock_reasons(ts("16:00"), st, LAST30, KNOWN)
    assert Reason.MARKET_CLOSED in K.clock_reasons(ts("12:00", date(2026, 10, 2)), st, LAST30, KNOWN)


def test_mt_g20_fomc_day_1445_rejected():
    fomc = E.DayEvents(known=True, fomc=True)
    st = session()
    assert K.clock_reasons(ts("14:45"), st, NOISE, fomc) == [Reason.FOMC_BLACKOUT]
    assert K.clock_reasons(ts("14:45"), st, NOISE, KNOWN) == []
    assert K.clock_reasons(ts("13:57:59"), st, NOISE, fomc) == []
    assert K.clock_reasons(ts("13:58"), st, NOISE, fomc) == [Reason.FOMC_BLACKOUT]
    assert K.clock_reasons(ts("15:30:01"), st, LAST30, fomc) == [Reason.FOMC_BLACKOUT]   # LAST30 skips FOMC days
    assert K.clock_reasons(ts("15:30:59"), st, LAST30, fomc) == [Reason.FOMC_BLACKOUT]


def test_mt_g20_release_blackout_around_a_1000_release():
    ev = E.DayEvents(known=True, releases_1000=[ts("10:00")])
    st = session()
    assert K.clock_reasons(ts("09:57:59"), st, NOISE, ev) == []
    assert K.clock_reasons(ts("09:58"), st, NOISE, ev) == [Reason.RELEASE_BLACKOUT]
    assert K.clock_reasons(ts("10:00:01"), st, NOISE, ev) == [Reason.RELEASE_BLACKOUT]
    assert K.clock_reasons(ts("10:05"), st, NOISE, ev) == [Reason.RELEASE_BLACKOUT]
    assert K.clock_reasons(ts("10:05:01"), st, NOISE, ev) == []


def test_mt_g20_unknown_event_calendar_blocks_entries():
    st = session()
    assert K.clock_reasons(ts("11:00"), st, NOISE, E.DayEvents(known=False)) == [Reason.EVENT_CALENDAR_UNKNOWN]
    assert K.clock_reasons(ts("11:00"), st, NOISE, None) == [Reason.EVENT_CALENDAR_UNKNOWN]


# ============================================================================================ events
def _cal(tmp_path, **raw):
    p = tmp_path / "ev.json"
    p.write_text(json.dumps(raw))
    return E.load_events(p)


def test_events_missing_coverage_is_unknown_never_no_events(tmp_path):
    cal = _cal(tmp_path, covers_from="2026-01-01", covers_through=None, fomc=[], releases=[])
    assert not cal.day(D).known
    cal = _cal(tmp_path, covers_from="2026-09-29", covers_through="2026-12-31", fomc=[], releases=[])
    assert cal.day(D).known and not cal.day(date(2026, 9, 28)).known and not cal.day(date(2027, 1, 4)).known
    missing = E.load_events_or_unknown(tmp_path / "nope.json")
    assert not missing.day(D).known
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    assert not E.load_events_or_unknown(broken).day(D).known


def test_events_only_verified_entries_count(tmp_path):
    cal = _cal(tmp_path, covers_from="2026-09-29", covers_through="2026-12-31",
               fomc=[{"date": "2026-10-28", "verified": True}, {"date": "2026-12-09", "verified": False}],
               releases=[{"date": "2026-10-01", "time": "10:00", "name": "ISM", "verified": True},
                         {"date": "2026-10-02", "time": "08:30", "name": "Payrolls", "verified": True},
                         {"date": "2026-10-27", "time": "10:00", "name": "Conf", "verified": False}])
    assert cal.day(date(2026, 10, 1)) == E.DayEvents(True, [], [ts("10:00")], False, [(ts("10:00"), "ISM")])
    assert cal.day(date(2026, 10, 2)) == E.DayEvents(True, ["Payrolls"], [], False,
                                                     [(ts("08:30", date(2026, 10, 2)), "Payrolls")])
    assert cal.day(date(2026, 10, 28)).fomc and cal.day(date(2026, 10, 28)).known
    assert not cal.day(date(2026, 10, 27)).known          # an unverified release makes the date unknown
    assert not cal.day(date(2026, 12, 9)).known and cal.day(date(2026, 12, 9)).fomc


def test_committed_2026_event_calendar():
    cal = E.load_events()
    fomc_2026 = sorted(d for d in cal.fomc if d.year == 2026)
    assert fomc_2026 == [date(2026, m, d) for m, d in ((1, 28), (3, 18), (4, 29), (6, 17), (7, 29), (9, 16),
                                                       (10, 28), (12, 9))]
    ev = cal.day(date(2026, 10, 28))
    assert ev.known and ev.fomc
    assert cal.day(date(2026, 10, 2)).release_0830 == ["Employment Situation"]
    assert not cal.day(date(2027, 1, 4)).known


# ============================================================================================ sizing (MT-G14)
def test_mt_g14_sizing_signature_is_fixed_and_forbidden_keywords_raise():
    assert list(inspect.signature(S.qty).parameters) == ["e0", "entry_limit", "stop", "stop_limit", "lane"]
    with pytest.raises(TypeError):
        S.qty(100000, 650.0, 649.0, 648.5, Lane.EXPLORATORY, confidence=0.9)
    with pytest.raises(TypeError):
        S.qty(100000, 650.0, 649.0, 648.5, Lane.EXPLORATORY, pnl_today=-300.0)


def test_mt_g14_property_10000_random_inputs():
    rng = np.random.default_rng(14)
    for i in range(10_000):
        e0 = float(np.exp(rng.uniform(np.log(500), np.log(5e7))))
        entry = float(np.round(rng.uniform(1.0, 2000.0), 2))
        stop = float(np.round(entry - rng.uniform(0.0, entry * 0.3), 2))
        stop_limit = float(np.round(stop - rng.uniform(0.0, 5.0), 2))
        for lane in (Lane.VALIDATED, Lane.EXPLORATORY):
            q = S.qty(e0, entry, stop, stop_limit, lane)
            assert isinstance(q, int) and q >= 0
            if q:
                assert q * (entry - stop_limit) <= C.RISK_PCT * e0 + 1e-9
                assert q * entry <= C.NOTIONAL_CAP_PCT * e0 + 1e-9
            if lane is Lane.EXPLORATORY:
                assert q <= C.EXPLORATORY_MAX_QTY
        for lane in (Lane.SHADOW, Lane.RETIRED):
            assert S.qty(e0, entry, stop, stop_limit, lane) == 0


def test_mt_g14_never_rounds_up_and_zero_means_no_trade():
    # E0 $100,000, entry $650, stop $0.30 below (stop-limit $0.15 further): 1R $100 -> 222; notional cap -> 15
    assert S.qty(100_000, 650.0, 649.70, 649.55, Lane.VALIDATED) == 15
    assert S.qty(100_000, 650.0, 649.70, 649.55, Lane.EXPLORATORY) == 1
    assert S.qty(30_000, 100.0, 99.0, 97.0, Lane.VALIDATED) == 10       # 30/3 = 10 exactly, not rounded up
    assert S.qty(29_999, 100.0, 99.0, 97.0, Lane.VALIDATED) == 9
    assert S.qty(5_000, 650.0, 649.0, 648.5, Lane.EXPLORATORY) == 0     # 10% of E0 < one share of SPY
    for bad in [(0, 650, 649, 648), (100_000, 650, 651, 648), (100_000, 650, 649, 650), (100_000, 650, 649, 649.5),
                (-1, 650, 649, 648), (float("nan"), 650, 649, 648), (100_000, float("inf"), 649, 648)]:
        assert S.qty(*bad, Lane.EXPLORATORY) == 0


def test_mt_g14_same_qty_after_good_and_bad_mornings():
    """Size has no input for the day's P&L: the same prices give the same size whatever happened before."""
    before = S.qty(100_000, 650.0, 649.0, 648.5, Lane.VALIDATED)
    for _ in range(3):   # +3R / -3R mornings change nothing the function can see
        assert S.qty(100_000, 650.0, 649.0, 648.5, Lane.VALIDATED) == before


# ============================================================================================ orders
def quote(sym="SPY", bid=650.00, ask=650.01, at="15:30:01", size=100):
    t = ts(at)
    return Quote(sym, bid, ask, size, size, t, t, Feed.IEX)


def cand(reg=LAST30, side=1, bar="15:29", **kw):
    return Candidate(reg.setup_id, reg.version, reg.symbol, "enter", side, ts(bar), **kw)


def test_mt_g21_rounding_helpers_have_no_float_drift():
    assert O.round_down_cent(651.23) == 651.23 and O.round_up_cent(651.23) == 651.23
    assert O.round_down_cent(1.15) == 1.15 and O.round_down_cent(0.1 + 0.2) == 0.3
    assert O.round_down_cent(30.015) == 30.01 and O.round_up_cent(30.011) == 30.02
    assert O.round_cent(656.5303) == 656.53 and O.round_cent(1.005) == 1.01


def test_mt_g16_overlay_bracket_is_complete_before_entry():
    spec, reasons, info = O.entry_bracket(cand(), LAST30, quote(), 100_000.0, D, 0)
    assert reasons == [] and isinstance(spec, OrderSpec)
    assert spec.order_class == "bracket" and spec.kind is Kind.ENTRY and spec.side == "buy" and spec.qty == 1
    assert spec.limit_price == 650.03                               # ask + min($0.02, 0.05% x ask), down
    assert spec.stop_price == O.round_down_cent(650.03 * 0.995) == 646.77
    assert spec.stop_limit_price == O.round_down_cent(646.77 - 0.5 * (650.03 - 646.77)) == 645.14
    assert spec.take_profit == 656.53
    assert spec.tif == "day" and not spec.extended_hours
    assert O.validate(spec) == []
    assert info["stop_source"] == "overlay" and info["target_source"] == "overlay"
    assert info["risk_per_share"] == pytest.approx(650.03 - 645.14) and info["qty"] == 1


def test_mt_g21_entry_collar_is_the_smaller_of_2_cents_and_5_bps():
    q = quote(bid=19.99, ask=20.00)
    spec, _, info = O.entry_bracket(cand(stop=19.80, target=20.40), LAST30, q, 100_000.0, D, 0)
    assert info["collar"] == pytest.approx(0.01) and spec.limit_price == 20.01
    spec, _, _ = O.entry_bracket(cand(stop=29.80, target=30.40), LAST30, quote(bid=29.99, ask=30.00),
                                 100_000.0, D, 0)
    assert spec.limit_price == 30.01                                 # 30.015 rounded DOWN


def test_orb5_bracket_uses_the_setup_stop_and_a_10r_target():
    c = Candidate("ORB5_QQQ", 1, "QQQ", "enter", 1, ts("09:34"), stop=560.004, target_r=10.0)
    spec, reasons, _ = O.entry_bracket(c, ORB5, quote("QQQ", 561.00, 561.02, "09:35:01"), 100_000.0, D, 0)
    assert reasons == []
    assert spec.limit_price == 561.04 and spec.stop_price == 560.00
    assert spec.stop_limit_price == O.round_down_cent(560.00 - max(0.05, 0.5 * 1.04)) == 559.48
    assert spec.take_profit == O.round_cent(561.04 + 10 * 1.04) == 571.44
    assert spec.client_order_id.startswith("SCALP-ORB5Q-261001-0934-E0-")


def test_mt_g16_entry_without_a_stop_or_target_is_rejected():
    spec, reasons, _ = O.entry_bracket(cand(ORB5, bar="09:34"), ORB5, quote("QQQ", at="09:35:01"), 1e5, D, 0)
    assert spec is None and reasons == [Reason.INVALID_STOP]
    spec, reasons, _ = O.entry_bracket(cand(ORB5, bar="09:34", stop=640.0), ORB5, quote("QQQ", at="09:35:01"),
                                       1e5, D, 0)
    assert spec is None and reasons == [Reason.TARGET_TOO_CLOSE]


def test_invalid_stop_and_target_too_close_are_rejected():
    spec, reasons, _ = O.entry_bracket(cand(stop=650.00, target=660.0), LAST30, quote(), 1e5, D, 0)
    assert spec is None and Reason.INVALID_STOP in reasons              # stop at the bid
    spec, reasons, _ = O.entry_bracket(cand(stop=649.0, target=650.04), LAST30, quote(), 1e5, D, 0)
    assert spec is None and reasons == [Reason.TARGET_TOO_CLOSE]        # limit 650.03 + 1 cent


def test_short_signal_is_rejected_short_disabled():
    spec, reasons, _ = O.entry_bracket(cand(side=-1), LAST30, quote(), 1e5, D, 0)
    assert spec is None and reasons == [Reason.SHORT_DISABLED]


def test_size_zero_for_shadow_lane_and_small_accounts():
    spec, reasons, _ = O.entry_bracket(cand(), replace(LAST30, lane=Lane.SHADOW), quote(), 1e5, D, 0)
    assert spec is None and reasons == [Reason.SIZE_ZERO]
    spec, reasons, _ = O.entry_bracket(cand(), LAST30, quote(), 5_000.0, D, 0)
    assert spec is None and reasons == [Reason.SIZE_ZERO]


def test_entry_bracket_needs_a_quote_and_a_registration():
    assert O.entry_bracket(cand(), LAST30, None, 1e5, D, 0)[1] == [Reason.NO_QUOTE]
    crossed = quote(bid=650.02, ask=650.01)
    assert O.entry_bracket(cand(), LAST30, crossed, 1e5, D, 0)[1] == [Reason.NO_QUOTE]
    assert O.entry_bracket(cand(), None, quote(), 1e5, D, 0)[1] == [Reason.SETUP_NOT_REGISTERED]
    assert O.entry_bracket(cand(), NOISE, quote(), 1e5, D, 0)[1] == [Reason.SETUP_NOT_REGISTERED]


def test_mt_g38_exit_limit_prices_off_the_bid_and_goes_out_without_a_quote():
    kw = dict(setup_id="LAST30_MOM_SPY", version=1, session_date=D, bar_start=ts("15:50"), leg="X", attempt=0)
    spec = O.exit_limit("SPY", 1, quote(), 650.0, C.EXIT_COLLARS[0], Kind.EXIT, reason="TIME_EXIT", **kw)
    assert spec.side == "sell" and spec.order_class == "simple" and spec.limit_price == 649.68   # 649.675 up
    assert spec.reason == "TIME_EXIT" and O.validate(spec) == []
    spec = O.exit_limit("SPY", 1, None, 650.0, C.EXIT_COLLARS[0], Kind.EXIT, **kw)
    assert spec.limit_price == O.round_up_cent(650.0 * 0.995) and "NO_QUOTE" in spec.reason
    kill = O.exit_limit("GME", 3, None, 20.0, C.KILL_COLLARS[2], Kind.PROTECT, setup_id=None, version=0,
                        session_date=D, bar_start=ts("11:02"), leg="K", attempt=2)
    assert kill.client_order_id.startswith("SCALP-BOT-261001-1102-K2-") and kill.limit_price == 19.8
    with pytest.raises(ValueError):
        O.exit_limit("SPY", 1, quote(), 650.0, 0.0005, Kind.ENTRY, **kw)
    with pytest.raises(ValueError):
        O.exit_limit("SPY", 0, quote(), 650.0, 0.0005, Kind.EXIT, **kw)
    with pytest.raises(ValueError):
        O.exit_limit("SPY", 1, None, None, 0.0005, Kind.EXIT, **kw)


def test_mt_g21_order_builder_has_no_market_or_stop_order_path():
    src = (LIVE / "orders.py").read_text()
    for banned in ("MarketOrderRequest", "StopOrderRequest", "TrailingStop", "OrderType.MARKET", '"market"',
                   "'market'", '"stop"', "stop_market"):
        assert banned not in src, banned
    public = {n for n, f in inspect.getmembers(O, inspect.isfunction) if f.__module__ == O.__name__
              and not n.startswith("_")}
    assert public == {"client_id", "parse_client_id", "entry_bracket", "exit_limit", "validate",
                      "round_down_cent", "round_up_cent", "round_cent"}
    assert "type" not in {f.name for f in dataclasses.fields(OrderSpec)}   # the broker only builds limit orders
    for py in LIVE.glob("*.py"):
        text = py.read_text()
        assert "MarketOrderRequest(" not in text and "OrderType.MARKET" not in text, py.name
    bad = OrderSpec("SCALP-L30S-261001-1529-E0-abcdef", "SPY", "buy", 1, Kind.ENTRY, 0.0, "bracket", 656.0,
                    646.0, 645.0)
    assert "limit price must be positive" in O.validate(bad)
    naked = OrderSpec("SCALP-L30S-261001-1529-E0-abcdef", "SPY", "buy", 1, Kind.ENTRY, 650.0)
    assert "entries are brackets only (MT-G16)" in O.validate(naked)


def test_mt_g25_client_ids_are_deterministic_and_parseable():
    a = O.client_id("LAST30_MOM_SPY", 1, D, ts("15:29"), "E", 0)
    assert a == O.client_id("LAST30_MOM_SPY", 1, D, ts("15:29"), "E", 0)        # same attempt, same id
    assert re.fullmatch(r"SCALP-L30S-261001-1529-E0-[0-9a-f]{6}", a) and len(a) <= 128
    others = {O.client_id("LAST30_MOM_SPY", 1, D, ts("15:29"), "E", 1),
              O.client_id("LAST30_MOM_SPY", 2, D, ts("15:29"), "E", 0),
              O.client_id("LAST30_MOM_SPY", 1, D, ts("15:29"), "X", 0),
              O.client_id("NOISE_MOM_SPY", 1, D, ts("15:29"), "E", 0)}
    assert a not in others and len(others) == 4
    p = O.parse_client_id(a)
    assert p == {"code": "L30S", "setup_id": "LAST30_MOM_SPY", "session_date": D, "hhmm": "1529", "leg": "E",
                 "attempt": 0, "h6": a[-6:]}
    assert O.parse_client_id(O.client_id(None, 0, D, ts("15:55"), "K", 3))["setup_id"] is None
    for junk in ("", "abc", "SCALP-XXXX-261001-1529-E0-abcdef", "RULES-L30S-261001-1529-E0-abcdef",
                 "SCALP-L30S-261001-1529-Q0-abcdef"):
        assert O.parse_client_id(junk) is None
    with pytest.raises(ValueError):
        O.client_id("VWAP_TREND_QQQ", 1, D, ts("10:00"), "E", 0)
    with pytest.raises(ValueError):
        O.client_id("LAST30_MOM_SPY", 1, D, ts("10:00"), "Z", 0)
    with pytest.raises(ValueError):
        O.client_id("LAST30_MOM_SPY", 1, D, ts("10:00"), "E", -1)


# ============================================================================================ costs (MT-G1, G3, G4)
def test_mt_g1_fee_table_refuses_a_date_no_row_covers():
    with pytest.raises(ValueError, match="no .* fee row"):
        X.fees("sell", 1, 650.0, date(2025, 6, 2))
    assert X.fees("sell", 1, 650.0, date(2026, 1, 2)) >= 0


def test_mt_g1_sec_fee_uses_the_rate_in_force_on_the_trade_date():
    assert X.fee_breakdown("sell", 1000, 1000.0, date(2026, 4, 3))["SEC"] == 0.0
    assert X.fee_breakdown("sell", 1000, 1000.0, date(2026, 4, 4))["SEC"] == pytest.approx(20.60)
    assert X.fee_breakdown("buy", 1000, 1000.0, date(2026, 4, 4))["SEC"] == 0.0
    assert X.fee_breakdown("sell", 1, 650.0, date(2026, 10, 1))["SEC"] == 0.02     # $0.0134 rounded up


def test_taf_is_capped_rounded_up_and_cat_is_charged_both_sides():
    assert X.fee_breakdown("sell", 100_000, 10.0, date(2026, 9, 1))["TAF"] == 9.79
    assert X.fee_breakdown("sell", 1, 650.0, date(2026, 9, 1))["TAF"] == 0.01
    assert X.fee_breakdown("buy", 1, 650.0, date(2026, 9, 1))["TAF"] == 0.0
    assert X.fee_breakdown("buy", 1000, 650.0, date(2026, 9, 1))["CAT"] == pytest.approx(0.003)
    assert X.fee_breakdown("sell", 1000, 650.0, date(2026, 3, 2))["CAT"] == 0.0
    for comp in X.COMPONENTS:
        assert any(r.component == comp for r in X.FEE_TABLE)
    assert all(r.source.startswith("https://") for r in X.FEE_TABLE)


def test_mt_g4_honest_pnl_marks_paper_down_and_never_subtracts_the_spread_twice():
    b = X.pnl_breakdown([(1, 650.03)], [(1, 651.00)], D)
    fee = X.fees("buy", 1, 650.03, D) + X.fees("sell", 1, 651.00, D)
    assert b["paper_pnl"] == pytest.approx(0.97)
    assert b["honest_slip"] == pytest.approx(0.02)
    assert b["honest_pnl"] == pytest.approx(0.97 - 0.02 - fee)
    assert X.honest_pnl([(1, 650.03)], [(1, 651.00)], D) == pytest.approx(b["honest_pnl"])
    assert set(b) == {"paper_pnl", "fees", "honest_slip", "honest_pnl", "buy_qty", "sell_qty"}


def test_mt_g3_slippage_mid_plus_a_cent_on_500_is_0_2_bps():
    assert X.slippage("buy", 500.01, 500.00) == pytest.approx((1.0, 0.2))
    assert X.slippage("sell", 499.99, 500.00) == pytest.approx((1.0, 0.2))
    assert X.slippage("buy", 499.99, 500.00) == pytest.approx((-1.0, -0.2))   # better than mid = negative


# ============================================================================================ risk
NOW = "15:30:01"


def bars_until(last_start="15:29", n=6, px=650.0, sym="SPY", wild_last=False):
    end = ts(last_start)
    out = []
    for k in range(n):
        s = end - pd.Timedelta(minutes=n - 1 - k)
        hi, lo = (px * 1.006, px * 0.994) if wild_last and k == n - 1 else (px + 0.05, px - 0.05)
        out.append(Bar(sym, s, px, hi, lo, px, 10_000.0, Feed.IEX))
    return out


def ctx(now=NOW, reg=LAST30, c=None, counters=None, **kw):
    t = ts(now)
    minute = (t - pd.Timedelta(seconds=61)).floor("min").strftime("%H:%M")
    sym = reg.symbol if reg is not None else "SPY"
    base = dict(now=t, candidate=c or Candidate(reg.setup_id, reg.version, sym, "enter", 1, ts(minute)),
                reg=reg, counters=counters or DayCounters(D, 100_000.0, cash_prev_close=100_000.0),
                session=session(), events=KNOWN,
                quote=Quote(sym, 650.00, 650.01, 100, 100, t, t, Feed.IEX),
                last_trade=LastTrade(sym, 650.005, 100, t - pd.Timedelta(milliseconds=500), Feed.IEX),
                recent_bars=bars_until(minute, sym=sym), last_data_ok=t, clock_offset_ms=20.0, halted=False,
                prior_close=648.0, slot_state=SlotState.FLAT, open_parents=0, open_position=False,
                flags=frozenset(), unrealized_honest=0.0, settled_cash=100_000.0,
                broker_nonmarginable_bp=100_000.0, gross_notional_open=0.0, planned_notional=650.03)
    base.update(kw)
    return R.EntryContext(**base)


def cnt(**kw):
    return DayCounters(D, 100_000.0, cash_prev_close=100_000.0, **kw)


def test_a_clean_context_is_allowed():
    assert R.entry_reasons(ctx()) == []
    assert R.entry_reasons(ctx("11:00", NOISE)) == []
    assert R.entry_reasons(ctx("09:35:01", ORB5, prior_close=560.0, spy_price=650.0, spy_prior_close=648.0)) == []


def test_mt_g22_qqq_entry_without_spy_inputs_fails_closed_on_the_circuit_breaker_check():
    for kw in ({}, {"spy_price": 650.0}, {"spy_prior_close": 648.0}):
        r, notes = R.entry_check(ctx("09:35:01", ORB5, prior_close=560.0, **kw))
        assert r == [Reason.INPUT_GAP] and notes["mwcb_check"] == "unavailable"


def test_mt_g38_exits_never_go_through_the_entry_gate():
    c = Candidate("LAST30_MOM_SPY", 1, "SPY", "exit", 0, ts("15:29"))
    with pytest.raises(ValueError, match="MT-G38"):
        R.entry_reasons(ctx(c=c))


def test_mt_g23_symbol_not_on_the_allowlist_is_rejected():
    c = Candidate("LAST30_MOM_SPY", 1, "GME", "enter", 1, ts("15:29"))
    r = R.entry_reasons(ctx(c=c))
    assert Reason.SYMBOL_NOT_ALLOWED in r and Reason.SETUP_NOT_REGISTERED in r


def test_registration_and_lane_are_enforced():
    assert R.entry_reasons(ctx(reg=LAST30, c=cand(NOISE, bar="15:29"))) == [Reason.SETUP_NOT_REGISTERED]
    assert Reason.SETUP_NOT_REGISTERED in R.entry_reasons(ctx(c=cand(LAST30, bar="15:29"), reg=None))
    assert R.entry_reasons(ctx(reg=replace(LAST30, lane=Lane.SHADOW))) == [Reason.LANE_SHADOW]
    assert R.entry_reasons(ctx(reg=replace(LAST30, lane=Lane.RETIRED))) == [Reason.LANE_RETIRED]
    v2 = Candidate("LAST30_MOM_SPY", 2, "SPY", "enter", 1, ts("15:29"))
    assert R.entry_reasons(ctx(c=v2)) == [Reason.SETUP_NOT_REGISTERED]


def test_short_entry_is_rejected():
    assert R.entry_reasons(ctx(c=cand(side=-1))) == [Reason.SHORT_DISABLED]


@pytest.mark.parametrize("flag", [Reason.KILLED, Reason.HALTED_MANUAL, Reason.SELFTEST_FAILED,
                                  Reason.DEPLOY_IN_MARKET_HOURS, Reason.RISK_HASH_MISMATCH,
                                  Reason.RECONCILE_MISMATCH, Reason.CODE_HASH_MISMATCH])
def test_bot_flags_each_block_with_their_own_reason(flag):
    assert R.entry_reasons(ctx(flags=frozenset({flag}))) == [flag]


def test_mt_g2_fifth_round_trip_rejected():
    assert R.entry_reasons(ctx(counters=cnt(round_trips=3))) == []
    assert R.entry_reasons(ctx(counters=cnt(round_trips=4))) == [Reason.MAX_TRADES_DAY]


def test_mt_g2_third_trade_for_one_setup_rejected():
    assert R.entry_reasons(ctx(counters=cnt(round_trips_by_setup={"LAST30_MOM_SPY": 1}))) == []
    assert R.entry_reasons(ctx(counters=cnt(round_trips_by_setup={"LAST30_MOM_SPY": 2}))) == [
        Reason.MAX_TRADES_SETUP]
    assert R.entry_reasons(ctx(counters=cnt(round_trips_by_setup={"NOISE_MOM_SPY": 2}))) == []


def test_mt_g2_entry_while_any_position_is_open_rejected():
    assert R.entry_reasons(ctx(open_position=True, slot_state=SlotState.OPEN, open_symbol="QQQ")) == [
        Reason.POSITION_OPEN]
    for st in (SlotState.ENTRY_PENDING, SlotState.PARTIALLY_FILLED, SlotState.EXIT_PENDING):
        assert R.entry_reasons(ctx(slot_state=st)) == [Reason.POSITION_OPEN]
    assert R.entry_reasons(ctx(slot_state=SlotState.COOLDOWN)) == []
    assert R.entry_reasons(ctx(slot_state=SlotState.DISABLED)) == [Reason.HALTED_MANUAL]


def test_mt_g17_adding_to_a_held_symbol_rejected_no_add():
    r = R.entry_reasons(ctx(open_position=True, slot_state=SlotState.OPEN, open_symbol="SPY"))
    assert r == [Reason.POSITION_OPEN, Reason.NO_ADD]


def test_mt_g2_ninth_entry_submission_rejected():
    assert R.entry_reasons(ctx(counters=cnt(entry_submits=7))) == []
    assert R.entry_reasons(ctx(counters=cnt(entry_submits=8))) == [Reason.MAX_ENTRY_SUBMITS_DAY]


def test_mt_g25_seventh_entry_submission_in_60_seconds_rejected():
    t = ts(NOW)
    six = [t - pd.Timedelta(seconds=s) for s in (1, 5, 10, 20, 40, 59)]
    assert R.entry_reasons(ctx(counters=cnt(entry_submits=6, entry_submit_times=six))) == [
        Reason.ENTRY_RATE_MINUTE]
    old = six[:-1] + [t - pd.Timedelta(seconds=60)]
    assert R.entry_reasons(ctx(counters=cnt(entry_submits=6, entry_submit_times=old))) == []


def test_mt_g25_one_open_parent_and_daily_notional_cap():
    assert R.entry_reasons(ctx(open_parents=1)) == [Reason.OPEN_PARENT]
    # 4 x E0 = $400,000 a day, both sides; a new entry commits to its buy and its sell (2 x $650.03)
    assert R.entry_reasons(ctx(counters=cnt(notional_traded=399_000.0))) == [Reason.NOTIONAL_DAY]
    assert R.entry_reasons(ctx(counters=cnt(notional_traded=400_000.0 - 2 * 650.03))) == []
    assert R.entry_reasons(ctx(counters=cnt(notional_traded=400_000.0 - 2 * 650.03 + 0.01))) == [
        Reason.NOTIONAL_DAY]


def test_mt_g17_reentry_10_min_after_a_stopout_rejected_16_allowed():
    stopped_at = ts("10:50")
    c = cnt(stopout_until={("NOISE_MOM_SPY", "SPY"): stopped_at + pd.Timedelta(minutes=C.STOPOUT_REENTRY_MIN)})
    assert R.entry_reasons(ctx("11:00", NOISE, counters=c)) == [Reason.STOPOUT_COOLDOWN]
    assert R.entry_reasons(ctx("11:06", NOISE, counters=c)) == []
    other = cnt(stopout_until={("ORB5_QQQ", "QQQ"): ts("11:30")})
    assert R.entry_reasons(ctx("11:00", NOISE, counters=other)) == []


def test_mt_g19_losses_at_1001_1007_1015_pause_until_1045():
    c = cnt(loss_streak=3, loss_pause_until=ts("10:15") + pd.Timedelta(minutes=C.LOSS_STREAK_PAUSE_MIN))
    assert R.entry_reasons(ctx("10:40", NOISE, counters=c)) == [Reason.LOSS_STREAK_COOLDOWN]
    assert R.entry_reasons(ctx("10:46", NOISE, counters=c)) == []


# ---------------------------------------------------------------------------------------- data gates (MT-G22)
def test_mt_g22_clock_offset_150ms_blocks():
    assert R.entry_reasons(ctx(clock_offset_ms=150.0)) == [Reason.CLOCK_OFFSET]
    assert R.entry_reasons(ctx(clock_offset_ms=100.0)) == []
    assert R.entry_reasons(ctx(clock_offset_ms=None)) == [Reason.CLOCK_UNVERIFIED]


def test_mt_g22_three_second_silent_feed_blocks():
    t = ts(NOW)
    assert R.entry_reasons(ctx(last_data_ok=t - pd.Timedelta(seconds=3))) == [Reason.DATA_STALE]
    assert R.entry_reasons(ctx(last_data_ok=t - pd.Timedelta(seconds=2))) == []
    assert R.entry_reasons(ctx(last_data_ok=None)) == [Reason.DATA_STALE]


def test_mt_g22_three_cent_spread_blocks():
    t = ts(NOW)
    wide = Quote("SPY", 649.99, 650.02, 100, 100, t, t, Feed.IEX)
    assert R.entry_reasons(ctx(quote=wide)) == [Reason.SPREAD_TOO_WIDE]
    two = Quote("SPY", 649.99, 650.01, 100, 100, t, t, Feed.IEX)
    assert R.entry_reasons(ctx(quote=two)) == []
    cheap = Quote("SPY", 20.00, 20.02, 100, 100, t, t, Feed.IEX)   # 2 cents but 10 bps
    r = R.entry_reasons(ctx(quote=cheap, last_trade=LastTrade("SPY", 20.01, 1, t, Feed.IEX),
                            recent_bars=bars_until(px=20.0), prior_close=20.0, planned_notional=20.03))
    assert r == [Reason.SPREAD_TOO_WIDE]


def test_mt_g22_halt_flag_blocks_and_unknown_halt_status_is_only_a_note():
    assert R.entry_reasons(ctx(halted=True)) == [Reason.HALTED]
    reasons, notes = R.entry_check(ctx(halted=None))
    assert reasons == [] and notes["halt_status"] == "unavailable"


def test_mt_g22_six_tenths_percent_from_the_last_trade_blocks():
    t = ts(NOW)
    far = LastTrade("SPY", 650.01 / 1.006, 100, t, Feed.IEX)
    assert R.entry_reasons(ctx(last_trade=far)) == [Reason.PRICE_AWAY_FROM_LAST_TRADE]
    assert R.entry_reasons(ctx(last_trade=None)) == [Reason.INPUT_GAP]


def test_mt_g22_one_point_two_percent_minute_pauses_the_symbol_for_10_minutes():
    wild = bars_until("15:10", wild_last=True)
    r = R.entry_reasons(ctx("15:11:01", NOISE, recent_bars=wild))
    assert r == [Reason.WILD_MINUTE_PAUSE]
    paused = wild + bars_until("15:19", n=9)                              # the pause ends at 15:21:00
    assert R.entry_reasons(ctx("15:20:59", NOISE, recent_bars=paused)) == [Reason.WILD_MINUTE_PAUSE]
    later = wild + bars_until("15:20", n=10)
    assert R.entry_reasons(ctx("15:21:01", NOISE, recent_bars=later)) == []
    c = cnt(wild_pause_until={"SPY": ts("11:05")})
    assert R.entry_reasons(ctx("11:00", NOISE, counters=c)) == [Reason.WILD_MINUTE_PAUSE]


def test_mt_g22_stale_quote_and_stale_bar_block():
    t = ts(NOW)
    old = Quote("SPY", 650.00, 650.01, 100, 100, t - pd.Timedelta(seconds=3), t, Feed.IEX)
    lt_old = LastTrade("SPY", 650.005, 1, t - pd.Timedelta(seconds=4), Feed.IEX)
    assert R.entry_reasons(ctx(quote=old, last_trade=lt_old)) == [Reason.QUOTE_STALE]
    behind = Quote("SPY", 650.00, 650.01, 100, 100, t - pd.Timedelta(seconds=1.5), t, Feed.IEX)
    lt_new = LastTrade("SPY", 650.005, 1, t + pd.Timedelta(seconds=1), Feed.IEX)
    assert R.entry_reasons(ctx(quote=behind, last_trade=lt_new)) == [Reason.QUOTE_STALE]
    assert R.entry_reasons(ctx(recent_bars=bars_until("15:28"))) == []          # ended 61 s ago
    assert R.entry_reasons(ctx(recent_bars=bars_until("15:27"))) == [Reason.BAR_STALE]   # 121 s
    assert R.entry_reasons(ctx(recent_bars=[])) == [Reason.BAR_STALE]
    assert R.entry_reasons(ctx(quote=None)) == [Reason.NO_QUOTE]


def test_mt_g22_luld_band_and_market_wide_circuit_breaker():
    t = ts(NOW)
    assert R.entry_reasons(ctx(recent_bars=bars_until(px=615.0), last_trade=LastTrade(
        "SPY", 650.005, 1, t, Feed.IEX))) == [Reason.LULD_BAND]
    q = Quote("SPY", 604.00, 604.01, 100, 100, t, t, Feed.IEX)
    r = R.entry_check(ctx(quote=q, last_trade=LastTrade("SPY", 604.0, 1, t, Feed.IEX),
                          recent_bars=bars_until(px=604.0), prior_close=650.0, planned_notional=604.03))
    assert r[0] == [Reason.HALTED] and r[1]["mwcb"]
    assert R.entry_reasons(ctx(prior_close=None)) == [Reason.INSUFFICIENT_HISTORY]
    orb = ctx("09:35:01", ORB5, prior_close=560.0, spy_price=600.0, spy_prior_close=650.0)
    assert R.entry_reasons(orb) == [Reason.HALTED]


# ---------------------------------------------------------------------------------------- loss limits (MT-G18)
def test_mt_g18_daily_limit_is_the_smallest_of_25_dollars_and_half_a_percent():
    assert R.daily_limit(100_000.0) == 25.0
    assert R.daily_limit(2_000.0) == pytest.approx(10.0)
    assert R.daily_limit(4_000.0) == pytest.approx(20.0)


def test_mt_g18_daily_stop_uses_realized_plus_unrealized_honest_pnl():
    assert R.entry_reasons(ctx(counters=cnt(realized_honest=-20.0), unrealized_honest=-4.99)) == []
    assert R.entry_reasons(ctx(counters=cnt(realized_honest=-20.0), unrealized_honest=-5.0)) == [Reason.DAILY_STOP]
    assert R.entry_reasons(ctx(counters=cnt(daily_stopped=True))) == [Reason.DAILY_STOP]


def test_mt_g18_weekly_stop_and_drawdown_halt():
    c = cnt(week_honest=-2_000.0, week_e0=100_000.0)
    assert R.entry_reasons(ctx(counters=c)) == [Reason.WEEKLY_STOP]
    assert R.entry_reasons(ctx(counters=cnt(week_honest=-1_999.0, week_e0=100_000.0))) == []
    r = R.entry_reasons(ctx(counters=cnt(test_peak=1_000.0, test_honest=-4_000.0)))
    assert Reason.DRAWDOWN_HALT in r


def test_whole_test_stop_at_150_dollars_or_60_sessions():
    assert R.entry_reasons(ctx(counters=cnt(test_honest=-149.0))) == []
    assert R.entry_reasons(ctx(counters=cnt(test_honest=-150.0))) == [Reason.TEST_STOP]
    assert Reason.TEST_STOP in R.entry_reasons(ctx(counters=cnt(test_honest=-100.0), unrealized_honest=-50.0))
    assert R.entry_reasons(ctx(counters=cnt(test_sessions=59))) == []
    assert R.entry_reasons(ctx(counters=cnt(test_sessions=60))) == [Reason.TEST_STOP]


# ---------------------------------------------------------------------------------------- money (MT-G15)
def test_mt_g15_settled_cash_ignores_todays_sales_and_broker_leverage():
    c = cnt(buy_notional=99_500.0)
    assert R.settled_cash(c) == 500.0
    r = R.entry_reasons(ctx(counters=c, settled_cash=R.settled_cash(c), broker_nonmarginable_bp=400_000.0))
    assert r == [Reason.INSUFFICIENT_SETTLED_CASH]
    assert R.entry_reasons(ctx(broker_nonmarginable_bp=600.0)) == [Reason.INSUFFICIENT_SETTLED_CASH]
    assert R.settled_cash(DayCounters(D, 1.0)) == 0.0


def test_mt_g15_gross_notional_never_above_e0():
    assert R.entry_reasons(ctx(gross_notional_open=99_500.0)) == [Reason.GROSS_NOTIONAL]
    assert R.entry_reasons(ctx(planned_notional=0.0)) == [Reason.SIZE_ZERO]


def test_every_failing_reason_is_listed_not_just_the_first():
    r = R.entry_reasons(ctx("15:31:30", counters=cnt(round_trips=4, entry_submits=8), clock_offset_ms=None,
                            halted=True, open_parents=1))
    for want in (Reason.AFTER_ENTRY_CUTOFF, Reason.MAX_TRADES_DAY, Reason.MAX_ENTRY_SUBMITS_DAY,
                 Reason.CLOCK_UNVERIFIED, Reason.HALTED, Reason.OPEN_PARENT):
        assert want in r
    assert len(r) == len(set(r))


# ============================================================================================ gates (MT-G11..G13)
def test_mt_g11_insufficient_sample_below_100_trades_or_40_sessions():
    assert G.sample_label(99, 40) == "INSUFFICIENT SAMPLE" and not G.sample_ok(99, 40)
    assert G.sample_label(100, 39) == "INSUFFICIENT SAMPLE"
    assert G.sample_label(100, 40) == "OK" and G.sample_ok(100, 40)


def test_mt_g12_bad_setup_switched_off_at_30_trades_in_most_seeded_runs():
    hits = sum(G.switch_off(np.random.default_rng(s).normal(-0.5, 1.0, 30), seed=s) is Lane.SHADOW
               for s in range(200))
    assert hits / 200 >= 0.80


def test_mt_g12_good_setup_rarely_switched_off_when_checked_after_every_trade():
    runs, off = 200, 0
    for s in range(runs):
        x = np.random.default_rng(1000 + s).normal(0.2, 1.0, 100)
        if any(G.switch_off(x[:n], seed=s) is not None for n in range(30, 101)):
            off += 1
    assert off / runs <= 0.10


def test_mt_g12_retire_and_small_samples():
    assert G.switch_off([-0.1] * 29) is None
    assert G.switch_off([0.0] * 100) is Lane.RETIRED
    assert G.switch_off(np.r_[np.full(50, 1.0), np.full(50, -1.0)]) is Lane.RETIRED   # mean exactly 0
    x = np.random.default_rng(3).normal(-0.5, 1.0, 40)
    assert G.switch_off(x, seed=7) == G.switch_off(x, seed=7)


def test_mt_g13_cusum_catches_a_minus_0_2r_setup_within_90_trades():
    hits = sum(G.cusum_trip(np.random.default_rng(s).normal(-0.2, 1.0, 90), 0.2) for s in range(500))
    assert hits / 500 >= 0.90


def test_mt_g13_cusum_false_trips_at_most_10_percent_for_a_good_setup():
    trips = sum(G.cusum_trip(np.random.default_rng(10_000 + s).normal(0.2, 1.0, 100), 0.2) for s in range(500))
    assert trips / 500 <= 0.10


def test_mt_g13_cusum_is_inactive_below_30_trades_or_without_a_baseline():
    assert not G.cusum_trip([-5.0] * 29, 0.2)
    assert G.cusum_trip([-5.0] * 30, 0.2)
    assert not G.cusum_trip([-5.0] * 50, None)


def test_mt_g13_win_rate_needs_two_bad_windows_in_a_row():
    good, bad = [True] * 12 + [False] * 18, [True] * 6 + [False] * 24     # 40% and 20% vs a 39% backtest
    assert not G.winrate_trip(bad + good, 0.39)
    assert not G.winrate_trip(bad + good + bad, 0.39)
    assert G.winrate_trip(good + bad + bad, 0.39)
    assert not G.winrate_trip(bad + bad, None)
    assert G.slippage_trip([2.1] * 30, 1.0) and not G.slippage_trip([2.1] * 29, 1.0)
    assert not G.slippage_trip([1.9] * 30, 1.0)


# ============================================================================================ journal
def test_journal_lines_are_plain_json_with_setup_labels(tmp_path):
    clock = lambda: ts("10:00:01")  # noqa: E731
    j = J.FileJournal(J.journal_path(tmp_path, D, Mode.DRY), Mode.DRY, clock)
    assert j.path == tmp_path / "journal" / "2026-10-01-dry.jsonl"
    j.write("decision", **LAST30.labels(), reasons=[Reason.DATA_STALE], price=np.float64(650.01), qty=np.int64(1),
            bar=ts("09:59"), nan=float("nan"), tags={"b", "a"}, spec=OrderSpec("SCALP-x", "SPY", "buy", 1,
                                                                               Kind.ENTRY, 650.0))
    j.write("heartbeat", slot="FLAT")
    lines = J.read_journal(j.path)
    assert [x["kind"] for x in lines] == ["decision", "heartbeat"]
    d = lines[0]
    assert d["ts"] == "2026-10-01T10:00:01-04:00" and d["mode"] == "dry"
    assert (d["setup_id"], d["version"], d["lane"], d["feed"]) == ("LAST30_MOM_SPY", 1, "EXPLORATORY", "IEX")
    assert d["reasons"] == ["DATA_STALE"] and d["price"] == 650.01 and d["qty"] == 1 and d["nan"] is None
    assert d["bar"] == "2026-10-01T09:59:00-04:00" and d["tags"] == ["a", "b"] and d["spec"]["kind"] == "ENTRY"
    assert "labels_missing" not in d and "setup_id" not in lines[1]


def test_journal_flags_a_setup_line_without_its_labels():
    m = J.MemoryJournal(Mode.PAPER, clock=lambda: ts("10:00"))
    m.write("decision", setup_id="NOISE_MOM_SPY", version=1)
    assert m.lines[0]["labels_missing"] == ["lane", "feed"] and m.lines[0]["lane"] is None
    assert m.kinds() == ["decision"] and m.of("decision") == m.lines
    with pytest.raises(ValueError):
        m.write("x", ts="y")


# ============================================================================================ package hygiene
SECTION_A = ("config.py", "clock.py", "events.py", "sizing.py", "orders.py", "costs.py", "risk.py", "gates.py",
             "journal.py")


def test_package_never_imports_an_llm_the_trader_or_the_options_lab():
    for py in LIVE.glob("*.py"):
        src = py.read_text()
        assert not re.search(r"^\s*(import|from)\s+anthropic", src, re.M), py.name
        assert not re.search(r"^\s*(from|import)\s+(trader|\.\.\.+trader|lab\.options_lab|\.\.options_lab)", src,
                             re.M), py.name


def test_pure_rule_modules_never_read_keys_or_the_system_clock():
    for name in SECTION_A:
        src = (LIVE / name).read_text()
        assert "ALPACA_" not in src and "os.environ" not in src and "getenv" not in src, name
        if name != "journal.py":   # MemoryJournal's default clock is the only wall-clock read
            assert "Timestamp.now" not in src and "datetime.now" not in src and "time.time" not in src, name
