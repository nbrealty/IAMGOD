"""Live paper minute trader: fixes from the second verification round (a fresh state folder, cancels the broker
refuses, dry and paper bots sharing state/scalp, the sticky deploy block, unverified take-profits in the switch-off,
fills during a kill). All offline: SimBroker or fake history, fake clocks, memory journals and tmp_path state."""
import dataclasses
from datetime import date, timedelta

import pandas as pd

from lab.scalp.live import gates as G
from lab.scalp.live import journal as J
from lab.scalp.live import orders as O
from lab.scalp.live import restore as RS
from lab.scalp.live import runner as RUN
from lab.scalp.live import state as S
from lab.scalp.live.broker import SimBroker
from lab.scalp.live.clock import at
from lab.scalp.live.engine import Engine
from lab.scalp.live.model import (AccountView, Bar, BrokerReject, DayCounters, Feed, Mode, OrderView, Reason,
                                  SlotState, as_ny)

from test_scalp_live_engine import D, KNOWN, REG, H, ctxs, enter_noise, mkbars, session, ts
from test_scalp_live_review import HistBroker, _entry_reasons, _trade, restart

ACCT = AccountView("PA123GWRL", "ACTIVE", 100_000.0, 100_000.0, 100_000.0, 100_000.0, 100_000.0, False, False, "x")


def _nope(oid):
    raise BrokerReject(f"order {oid} not cancelable (status pending_cancel)", 422, "NOT_CANCELABLE")


# =================================================================================== whole-test stop from the broker
def test_paper_caps_fresh_state_folder_rebuilds_the_test_start_from_the_broker_and_hits_test_stop(tmp_path):
    days = list(pd.bdate_range("2026-10-01", periods=7).date)          # 7 sessions, -$30 each at the broker
    hist = HistBroker([o for i, d in enumerate(days) for o in _trade(d, i, 650.0, 620.0)])
    today = date(2026, 10, 12)
    now = ts("08:50", today)
    start = RUN.resolve_test_start(REG, tmp_path, Mode.PAPER, now, RUN.broker_history(hist, now))
    assert start == days[0] and S.read_test_start(tmp_path) == days[0]              # not today
    assert [x["action"] for x in S.read_changes(tmp_path)] == ["test-start"]
    c, _ = RS.rebuild(hist, today, 100_000.0, 100_000.0, today - timedelta(days=today.weekday()), start, REG,
                      ts("09:00", today))
    assert c.test_sessions == 7 and c.test_honest < -150.0
    assert Reason.TEST_STOP in _entry_reasons(dataclasses.replace(c, session_date=D))


def test_paper_caps_a_pin_later_than_the_broker_history_moves_earlier_never_later(tmp_path):
    days = list(pd.bdate_range("2026-10-01", periods=3).date)
    hist = HistBroker([o for i, d in enumerate(days) for o in _trade(d, i, 650.0, 649.0)])
    now = ts("08:50", date(2026, 10, 12))
    S.pin_test_start(tmp_path, date(2026, 10, 12), now, "a fresh container pinned today")
    h = RUN.broker_history(hist, now)
    assert RUN.resolve_test_start(REG, tmp_path, Mode.PAPER, now, h) == days[0]
    assert RUN.resolve_test_start(REG, tmp_path, Mode.PAPER, now, []) == days[0]         # never moved later
    assert RUN.resolve_test_start(REG, tmp_path / "dry", Mode.DRY, now, h) == days[0]   # dry reads, pins nothing
    assert S.read_test_start(tmp_path / "dry") is None


def _kill_order(day, hhmm="10:30"):
    t = as_ny(f"{day} {hhmm}:00")
    cid = O.client_id(None, 0, day, t, "K", 0)
    return OrderView(f"k{day}", cid, "SPY", "sell", 1, 1, 649.0, "filled", "limit", 648.0, submitted_at=t,
                     filled_at=t)


def test_mt_g27_a_halt_lost_with_the_state_folder_is_rebuilt_from_kill_orders_at_the_broker(tmp_path):
    d = date(2026, 10, 5)
    hist = [_kill_order(d)]
    now = ts("08:50", date(2026, 10, 6))
    why = RUN.broker_halt_reason(hist, tmp_path, now)
    assert why and "reset-halt" in why                                      # empty folder: HALT comes back
    S.write_flag(tmp_path, S.HALT, why, now, "startup")
    assert RUN.broker_halt_reason(hist, tmp_path, now) is None               # already halted
    S.reset_halt(tmp_path, "checked the account after the kill", now)        # a person reset it after the kill
    assert RUN.broker_halt_reason(hist, tmp_path, now) is None
    later = [_kill_order(date(2026, 10, 6), "10:00")]                        # a new kill after that reset
    assert RUN.broker_halt_reason(hist + later, tmp_path, ts("10:05", date(2026, 10, 6)))


# =================================================================================== cancels the broker refuses
def test_mt_g20_a_not_cancelable_pending_entry_still_gets_the_1555_kill(tmp_path):
    h = H(tmp_path, sim_kw={"fill_delay_s": 1e9})                            # the entry rests unfilled
    enter_noise(h)
    h.sim.cancel = _nope                                                     # every cancel: 422 NOT_CANCELABLE
    h.t = ts("15:49:55")
    h.until("15:55:05")
    kills = h.j.of("kill_start")
    assert kills and kills[0]["reason"] == Reason.OPEN_AT_KILL_TIME.value
    assert not [x for x in h.j.of("broker_error") if x.get("step") in ("_clock_rules", "_refresh")]
    assert h.j.of("cancel_failed") and Reason.KILLED in h.eng.flags


def test_mt_g40_a_restart_with_a_not_cancelable_pending_entry_still_builds_the_engine(tmp_path):
    h = H(tmp_path, sim_kw={"fill_delay_s": 1e9})
    enter_noise(h)
    h.sim.cancel = _nope
    h.step(1)
    restart(h, tmp_path)                                                     # used to raise BrokerReject
    assert h.eng.trade is not None and h.eng.trade.state is SlotState.ENTRY_PENDING
    assert h.eng.trade.cancel_requested_at is not None and h.j.of("cancel_failed")
    h.step(1)                                                                # and it ticks


# =================================================================================== dry and paper share state/scalp
def test_mt_g27_a_dry_kill_never_starts_a_paper_kill(tmp_path):
    dry = H(tmp_path)
    paper = H(tmp_path, mode=Mode.PAPER)                                     # same state folder
    enter_noise(paper)
    paper.step(1)
    dry.eng.request_kill("OPEN_AT_KILL_TIME (dry simulation)")
    for _ in range(15):
        dry.step(1)
        paper.step(1)
    assert not paper.j.of("kill_start") and paper.sim.positions()           # the paper position is untouched
    assert not (paper.state / "KILL").exists() and not (paper.state / "HALT").exists()
    assert (dry.state / "HALT-dry").exists() and dry.j.of("kill_done")
    assert Reason.HALTED_MANUAL not in paper.eng.flags


def test_mt_g27_the_owners_kill_is_not_swallowed_by_a_dry_bot(tmp_path):
    paper = H(tmp_path, mode=Mode.PAPER)
    enter_noise(paper)
    paper.step(1)
    dry = H(tmp_path, start="10:00:02")
    S.write_flag(paper.state, S.KILL, "owner kill", paper.t, "kill command")   # `kill`: the paper bot is running
    dry.step(1)
    assert (paper.state / "KILL").exists() and not dry.j.of("kill_start")
    for _ in range(15):
        paper.step(1)
    assert paper.j.of("kill_done") and paper.flat() and (paper.state / "HALT").exists()
    assert not (paper.state / "KILL").exists()
    dry.step(1)
    assert Reason.HALTED_MANUAL in dry.eng.flags                             # a dry run obeys the paper HALT
    S.write_flag(dry.state, S.flag_name(S.HALT, Mode.DRY), "dry halt", dry.t, "test")
    cleared = S.reset_halt(dry.state, "checked both", dry.t)
    assert cleared["halt"] and cleared["halt-dry"]
    assert not (dry.state / "HALT").exists() and not (dry.state / "HALT-dry").exists()


def test_mt_g18_a_dry_daily_stop_does_not_stop_the_paper_bot(tmp_path):
    dry = H(tmp_path)
    dry.c.realized_honest = -30.0
    dry.step(1)
    assert dry.c.daily_stopped and (dry.state / f"daily_stop-{D.isoformat()}-dry").exists()
    paper = H(tmp_path, mode=Mode.PAPER)
    assert not paper.c.daily_stopped


# =================================================================================== dry restart counters (MT-G40)
def test_mt_g40_a_dry_restart_after_a_broker_reject_counts_the_submit_once(tmp_path):
    h = H(tmp_path)
    h.sim.reject_next = 403
    h.px["SPY"] = 651.0
    h.step(1, {"SPY": mkbars("SPY", "09:30", "09:59", 650.0, 651.0)})
    assert h.j.of("broker_reject") and h.c.entry_submits == 1
    c = DayCounters(D, 100_000.0, cash_prev_close=100_000.0)                  # the new process
    assert RS.from_journal(h.j.lines, c)
    Engine(SimBroker(h.clock), h.j, REG, c, session(), KNOWN, ctxs(), Mode.DRY, h.clock, state_dir=h.state)
    assert c.entry_submits == 1 and len(c.entry_submit_times) == 1 and "SPY" in c.blocked_symbols


# =================================================================================== MT-G27 sticky deploy block
def _yesterday(sd, h="A"):
    y = date(2026, 10, 5)
    S.write_session(sd, y, {"e0": 100_000.0, "package_hash": h,
                            "starts": [{"ts": at(y, "08:40").isoformat(), "mode": "paper", "package_hash": h}]})


def test_mt_g27_a_deploy_block_survives_a_restart(tmp_path):
    d = date(2026, 10, 6)
    _yesterday(tmp_path)
    r1, _ = RUN.deploy_check(tmp_path, at(d, "10:00"), "B", Mode.PAPER)
    RUN.session_info(tmp_path, d, session(d), "B", at(d, "10:00"), Mode.PAPER, lambda: ACCT)
    assert r1 == [Reason.DEPLOY_IN_MARKET_HOURS]
    r2, _ = RUN.deploy_check(tmp_path, at(d, "10:01"), "B", Mode.PAPER)                 # restart, same code
    assert r2 == [Reason.DEPLOY_IN_MARKET_HOURS]
    r3, _ = RUN.deploy_check(tmp_path, at(d, "10:02"), "A", Mode.PAPER)                 # even the old code
    assert r3 == [Reason.DEPLOY_IN_MARKET_HOURS]
    # without the sticky file, a hash first seen inside the window is still never the reference
    prior = S.read_session(tmp_path, d)
    assert RUN.deploy_reasons(at(d, "10:01"), prior, "B", baseline_hash="A", require_baseline=True) == [
        Reason.DEPLOY_IN_MARKET_HOURS]
    r4, _ = RUN.deploy_check(tmp_path, at(date(2026, 10, 7), "08:50"), "B", Mode.PAPER)  # next day, before 09:00
    assert r4 == []


def test_mt_g27_a_dry_first_start_in_the_window_never_becomes_the_paper_baseline(tmp_path):
    d = date(2026, 10, 6)
    r1, _ = RUN.deploy_check(tmp_path, at(d, "10:00"), "B", Mode.DRY)          # no earlier session at all
    RUN.session_info(tmp_path, d, session(d), "B", at(d, "10:00"), Mode.DRY, lambda: ACCT)
    assert r1 == []
    r2, _ = RUN.deploy_check(tmp_path, at(d, "10:05"), "B", Mode.PAPER)
    assert r2 == [Reason.DEPLOY_IN_MARKET_HOURS]


def test_mt_g27_code_deployed_before_0900_may_trade_after_a_restart(tmp_path):
    d = date(2026, 10, 6)
    _yesterday(tmp_path)
    assert RUN.deploy_check(tmp_path, at(d, "08:50"), "B", Mode.PAPER)[0] == []
    RUN.session_info(tmp_path, d, session(d), "B", at(d, "08:50"), Mode.PAPER, lambda: ACCT)
    assert RUN.deploy_check(tmp_path, at(d, "10:00"), "B", Mode.PAPER)[0] == []
    assert RUN.deploy_check(tmp_path, at(d, "10:01"), "C", Mode.PAPER)[0] == [Reason.DEPLOY_IN_MARKET_HOURS]


# =================================================================================== MT-G12 with MT-G4 take-profits
def _closed(i, r, tp):
    t = as_ny(f"{D} 10:00") + pd.Timedelta(minutes=i)
    return RS.ClosedTrade("NOISE_MOM_SPY", "SPY", t, t, [(1, 650.0)], [(1, 650.0 + r)], not tp, r, r, 0.0,
                          pending_verify=tp, gate_honest=min(r, 0.0) if tp else r, r=r,
                          tp_order_id=f"tp{i}" if tp else None)


def test_mt_g12_thirty_alternating_2r_wins_and_1r_losses_do_not_demote_the_setup(tmp_path):
    trades = [_closed(i, 2.0 if i % 2 == 0 else -1.0, i % 2 == 0) for i in range(30)]
    adopted = RS.AdoptedState(trades=trades)
    # no win verified yet: the unverified take-profits are LEFT OUT (never counted as 0R)
    h = RUN.lane_history(REG, adopted, tmp_path, Mode.PAPER)[("NOISE_MOM_SPY", "SPY")]
    assert h["r"] == [-1.0] * 15 and h["pending_verify"] == 15
    assert G.lane_check(h["r"], [], None, None)[0] is None
    # the old series (every take-profit counted as min(R, 0)) would have switched a +0.5R setup off
    assert G.lane_check([min(t.r, 0.0) if t.pending_verify else t.r for t in trades], [], None, None)[0] is not None
    # the live bars proved the take-profits (journal `tp_verified`): they count at their real R
    j = J.FileJournal(J.journal_path(tmp_path, D, Mode.PAPER), Mode.PAPER, lambda: ts("16:00"))
    for t in trades:
        if t.pending_verify:
            j.write("tp_verified", order_id=t.tp_order_id, setup_id="NOISE_MOM_SPY", symbol="SPY", r=t.r)
    h = RUN.lane_history(REG, adopted, tmp_path, Mode.PAPER)[("NOISE_MOM_SPY", "SPY")]
    assert len(h["r"]) == 30 and sum(h["r"]) / 30 == 0.5 and h["pending_verify"] == 0
    assert G.lane_check(h["r"], [], None, None)[0] is None


def test_mt_g4_a_take_profit_joins_the_r_series_only_after_a_print_through_its_limit(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.step(1)
    target = h.eng.trade.target
    h.px["SPY"] = target + 0.05                                              # the resting take-profit fills
    h.step(1)
    closed = h.j.of("trade_closed")[-1]
    assert closed["pending_verify"] and closed["r"] > 0 and closed["gate_r"] == 0.0
    assert h.j.of("lane_gate_excluded") and h.eng.hist[("NOISE_MOM_SPY", "SPY")]["r"] == []
    fill_min = as_ny(h.t).floor("min")
    h.t = fill_min + pd.Timedelta(seconds=61)
    bar = Bar("SPY", fill_min, target - 0.2, target + 0.03, target - 0.3, target, 1e4, Feed.IEX)
    h.step(1, {"SPY": [bar]})
    assert h.j.of("tp_verified") and h.eng.hist[("NOISE_MOM_SPY", "SPY")]["r"] == [closed["r"]]


def test_mt_g4_a_take_profit_without_a_print_through_stays_out(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.step(1)
    target = h.eng.trade.target
    h.px["SPY"] = target + 0.05
    h.step(1)
    fill_min = as_ny(h.t).floor("min")
    h.t = fill_min + pd.Timedelta(seconds=61)
    h.step(1, {"SPY": [Bar("SPY", fill_min, target - 0.2, target, target - 0.3, target, 1e4, Feed.IEX)]})
    h.t = fill_min + pd.Timedelta(minutes=4)
    h.step(1)
    assert not h.j.of("tp_verified") and h.j.of("tp_unverified")
    assert h.eng.hist[("NOISE_MOM_SPY", "SPY")]["r"] == []


# =================================================================================== fills during a kill (MT-G16)
def test_mt_g16_an_exit_that_fills_during_the_kill_is_booked_and_the_trade_closed(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.step(1)
    assert h.eng.trade.stop_confirmed
    h.sim.fill_delay_s = 3.0
    h.eng.request_flatten("SIGTERM")
    h.step(1)                                                                # legs cancelled, the exit rests
    assert h.eng.trade.exit.order_id is not None
    h.sim.cancel_delay_s = 10.0
    h.eng.request_kill("test kill while the exit rests")
    for _ in range(20):
        h.step(1)
    assert h.flat() and h.eng.killed
    closed = h.j.of("trade_closed")
    assert len(closed) == 1 and closed[0]["how"].startswith("kill")
    assert [x["side"] for x in h.j.of("fill")] == ["buy", "sell"]
    assert h.c.realized_honest != 0.0 and h.c.realized_honest == closed[0]["gate_honest_pnl"]
