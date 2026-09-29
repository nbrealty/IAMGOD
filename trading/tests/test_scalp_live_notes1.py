"""Live paper minute trader: the owner-approved items of `reports/Owner notes 1 - intraday addendum v2 and v3
(2026-09-28).md` (Patch C event horizon, Patch G halts and margin framework, Patch E excursions, Patch F execution
health vs strategy performance, Patch H operating result). All offline: SimBroker, fake clocks, memory journals,
temporary state folders. No network, no keys, no order sent anywhere."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from lab.scalp.live import clock as K
from lab.scalp.live import config as C
from lab.scalp.live import costs as X
from lab.scalp.live import events as E
from lab.scalp.live import gates as G
from lab.scalp.live import journal as J
from lab.scalp.live import market as M
from lab.scalp.live import report as REP
from lab.scalp.live import risk as R
from lab.scalp.live import runner as RUN
from lab.scalp.live.engine import Engine
from lab.scalp.live.model import (Bar, Candidate, DayCounters, Feed, Lane, LastTrade, MarketSnapshot, Mode, Quote,
                                  Reason, SlotState, as_ny)

import test_scalp_live_engine as TE
import test_scalp_live_rules as TR

LIVE = Path(C.__file__).resolve().parent
REG = C.load_registry()
ORB5, LAST30, NOISE = REG.get("ORB5_QQQ", "QQQ"), REG.get("LAST30_MOM_SPY", "SPY"), REG.get("NOISE_MOM_SPY", "SPY")
CAL = E.load_events()
RELEASE_DAY = date(2026, 9, 29)        # 10:00 Consumer Confidence + JOLTS (the first paper session)
QUIET = date(2026, 10, 6)              # nothing scheduled
FOMC_DAY = date(2026, 10, 28)


def ts(hms, d=TR.D):
    return as_ny(f"{d.isoformat()} {hms}")


def rctx(now, reg, d, events, **kw):
    """test_scalp_live_rules.ctx on another date (a clean context: every other gate passes)."""
    t = ts(now, d)
    minute = (t - pd.Timedelta(seconds=61)).floor("min")
    sym = reg.symbol
    px = 560.0 if sym == "QQQ" else 650.0
    bars = [Bar(sym, minute - pd.Timedelta(minutes=5 - k), px, px + 0.05, px - 0.05, px, 1e4, Feed.IEX)
            for k in range(6)]
    base = dict(now=t, candidate=Candidate(reg.setup_id, reg.version, sym, "enter", 1, minute), reg=reg,
                counters=DayCounters(d, 100_000.0, cash_prev_close=100_000.0), session=TR.session(d), events=events,
                quote=Quote(sym, px, px + 0.01, 100, 100, t, t, Feed.IEX),
                last_trade=LastTrade(sym, px + 0.005, 100, t - pd.Timedelta(milliseconds=500), Feed.IEX),
                recent_bars=bars, last_data_ok=t, clock_offset_ms=20.0, halted=False, prior_close=px - 2.0,
                slot_state=SlotState.FLAT, open_parents=0, open_position=False, flags=frozenset(),
                unrealized_honest=0.0, settled_cash=100_000.0, broker_nonmarginable_bp=100_000.0,
                gross_notional_open=0.0, planned_notional=px + 0.03, spy_price=650.0, spy_prior_close=648.0)
    base.update(kw)
    return R.EntryContext(**base)


# ============================================================================================ constants (MT-G41)
def test_notes1_constants_are_locked():
    assert (C.EVENT_WINDOW_BEFORE_MIN, C.EVENT_WINDOW_AFTER_MIN, C.EVENT_EXIT_ALLOWANCE_S) == (5, 10, 60)
    assert C.FOMC_EVENT_TIMES == (("14:00", "FOMC statement"), ("14:30", "FOMC press conference"))
    assert (C.HALT_SUSPECT_S, C.HALT_SUSPECT_FROM_MIN) == (60, 5)
    assert C.MAX_HOLD_UNTIL_FLATTEN == "until_flatten"
    assert (C.MARGIN_FRAMEWORK, C.MARGIN_FRAMEWORK_EFFECTIVE, C.MARGIN_FRAMEWORK_CHECKED) == \
        ("MARGIN_INTRADAY_FRAMEWORK", "2026-06-04", "2026-09-28")
    assert C.MARGIN_FRAMEWORK_SOURCE == "https://docs.alpaca.markets/us/docs/the-intraday-margin-rule"
    assert Reason.EVENT_HORIZON_OVERLAP.value == "EVENT_HORIZON_OVERLAP"
    assert Reason.HALT_SUSPECTED.value == "HALT_SUSPECTED"
    # the MT-G20 blocks are kept as they were (the stricter rule wins, nothing was loosened)
    assert (C.RELEASE_BLOCK_BEFORE_MIN, C.RELEASE_BLOCK_AFTER_MIN, C.FOMC_BLOCK) == (2, 5, ("13:58", "15:30:59"))


# ============================================================================================ Patch C
def test_v2_05_a_1350_candidate_with_a_15_minute_hold_overlaps_a_1400_event():
    ev = E.DayEvents(known=True, release_times=[(ts("14:00"), "14:00 event")])
    reg = replace(NOISE, max_hold=15)
    st = TR.session()
    assert K.clock_reasons(ts("13:50"), st, reg, ev) == []            # 13:50 itself is outside every blackout
    assert K.hold_horizon(ts("13:50"), st, reg) == (ts("13:50"), ts("14:06:02"))   # +2 s entry, 15 min, 60 s exit
    r, notes = R.entry_check(rctx("13:50:00", reg, TR.D, ev))
    assert r == [Reason.EVENT_HORIZON_OVERLAP]
    assert notes["event_horizon"]["events"] == ["14:00 event 14:00"]
    # a shorter hold that ends before 13:55 is clear; H is never shortened to squeeze a trade through
    assert R.entry_reasons(rctx("13:30:00", replace(NOISE, max_hold=15), TR.D, ev)) == []


def test_patch_c_window_endpoints_are_inclusive():
    ev = E.DayEvents(known=True, release_times=[(ts("14:00"), "x")])
    reg = replace(NOISE, max_hold=10)
    # the horizon ends at d + 2 s + 10 min + 60 s: exactly 13:55:00 (the window's start) overlaps, a second less not
    assert K.event_horizon_hits(ts("13:43:58"), TR.session(), reg, ev) == ["x 14:00"]
    assert K.event_horizon_hits(ts("13:43:57"), TR.session(), reg, ev) == []
    # and the window's end (14:10:00) still overlaps a decision taken right then
    assert K.event_horizon_hits(ts("14:10:00"), TR.session(), reg, ev) == ["x 14:00"]
    assert K.event_horizon_hits(ts("14:10:01"), TR.session(), reg, ev) == []


def test_patch_c_orb5_at_0935_on_a_day_with_a_1000_release_is_rejected():
    ev = CAL.day(RELEASE_DAY)
    assert ev.known and [n for _, n in ev.release_times] == ["Consumer Confidence", "JOLTS"]
    r, notes = R.entry_check(rctx("09:35:01", ORB5, RELEASE_DAY, ev))
    assert r == [Reason.EVENT_HORIZON_OVERLAP]
    assert notes["event_horizon"]["events"] == ["Consumer Confidence + JOLTS 10:00"]
    # the same entry on a day with nothing scheduled goes
    assert R.entry_reasons(rctx("09:35:01", ORB5, QUIET, CAL.day(QUIET))) == []


def test_patch_c_last30_at_1530_on_a_normal_day_is_allowed():
    assert R.entry_reasons(rctx("15:30:01", LAST30, QUIET, CAL.day(QUIET))) == []
    # a 10:00 release is long over by 15:30: still allowed on the release day
    assert R.entry_reasons(rctx("15:30:01", LAST30, RELEASE_DAY, CAL.day(RELEASE_DAY))) == []


def test_patch_c_fomc_statement_and_press_conference_come_from_the_calendar():
    ev = CAL.day(FOMC_DAY)
    assert [(t.strftime("%H:%M"), n) for t, n in ev.fomc_times] == [("14:00", "FOMC statement"),
                                                                     ("14:30", "FOMC press conference")]
    st = TR.session(FOMC_DAY)
    wins = K.event_windows(st, ev)
    assert [(a.strftime("%H:%M"), b.strftime("%H:%M")) for a, b, _ in wins] == [("13:55", "14:10"), ("14:25", "14:40")]
    # NOISE at 11:00 (hold to the 15:50 flatten) meets both; the FOMC blackout covers the afternoon as before
    r = R.entry_reasons(rctx("11:00:01", NOISE, FOMC_DAY, ev))
    assert r == [Reason.EVENT_HORIZON_OVERLAP]
    # an FOMC day given without times (a hand-made DayEvents) uses the standard 14:00 / 14:30: never "clear"
    bare = E.DayEvents(known=True, fomc=True)
    assert [n for _, _, n in K.event_windows(st, bare)] == ["FOMC statement 14:00", "FOMC press conference 14:30"]


def test_patch_c_a_bare_releases_1000_without_names_still_gets_a_window():
    # a hand-made DayEvents with releases_1000 only (no release_times) is not "clear": a window named "release"
    ev = E.DayEvents(known=True, releases_1000=[ts("10:00")])
    st = TR.session()
    assert [(a.strftime("%H:%M"), b.strftime("%H:%M"), n) for a, b, n in K.event_windows(st, ev)] == \
        [("09:55", "10:10", "release 10:00")]
    assert K.event_horizon_hits(ts("09:35:01"), st, ORB5, ev) == ["release 10:00"]
    # a time already named in release_times is not added twice under "release"
    both = E.DayEvents(known=True, releases_1000=[ts("10:00")], release_times=[(ts("10:00"), "JOLTS")])
    assert [n for _, _, n in K.event_windows(st, both)] == ["JOLTS 10:00"]


def test_patch_c_unknown_calendar_stays_event_calendar_unknown():
    r = R.entry_reasons(rctx("11:00:01", NOISE, QUIET, E.DayEvents(known=False)))
    assert r == [Reason.EVENT_CALENDAR_UNKNOWN]
    assert Reason.EVENT_CALENDAR_UNKNOWN in R.entry_reasons(rctx("11:00:01", NOISE, QUIET, None))


def test_patch_c_registry_max_hold_is_required_and_no_version_was_bumped(tmp_path):
    import json
    for r in REG:
        assert r.max_hold == "until_flatten" and r.version == 1 and r.hash_ok()
        assert any("EVENT_HORIZON_OVERLAP" in x and "20-session" in x for x in r.deviations)
        assert any("HALT_SUSPECTED" in x for x in r.deviations)
    raw = json.loads((LIVE / "registry.json").read_text())
    for bad in ("forever", 0, True, None):
        raw2 = json.loads(json.dumps(raw))
        raw2["setups"][0]["max_hold"] = bad
        p = tmp_path / "r.json"
        p.write_text(json.dumps(raw2))
        with pytest.raises(C.RegistryError):
            C.load_registry(p)
    raw2 = json.loads(json.dumps(raw))
    del raw2["setups"][0]["max_hold"]
    p.write_text(json.dumps(raw2))
    with pytest.raises(C.RegistryError):
        C.load_registry(p)
    raw2["setups"][0]["max_hold"] = 15
    p.write_text(json.dumps(raw2))
    assert C.load_registry(p).setups[0].max_hold == 15


def test_patch_c_replay_of_a_release_day_refuses_orb5_but_still_trades_last30(tmp_path):
    import test_scalp_live_integration as TI
    d = date(2026, 10, 1)                                   # ISM Manufacturing at 10:00
    shift = pd.Timedelta(days=(d - TI.D).days)
    bars = {s: [replace(b, start=b.start + shift) for b in bl] for s, bl in TI.synthetic_day().items()}
    st = K.SessionTimes.from_calendar(d, ts("09:30", d), ts("16:00", d))
    market = M.ReplayMarket(d, bars, M.bar_quote_fn(bars), M.SimClock(st.open), open_ts=st.open, close_ts=st.close)
    RUN.replay(d, e0=TI.E0, market=market, ctx_by_symbol=TI.ctxs(), session=st, state_dir=tmp_path,
               out=lambda s: None)
    lines = J.read_journal(J.journal_path(tmp_path, d, Mode.REPLAY))
    dec = {x["setup_id"]: x for x in lines if x["kind"] == "decision"}
    assert not dec["ORB5_QQQ"]["accepted"] and dec["ORB5_QQQ"]["reasons"] == ["EVENT_HORIZON_OVERLAP"]
    assert dec["LAST30_MOM_SPY"]["accepted"]
    closed = [x for x in lines if x["kind"] == "trade_closed"]
    assert [(x["setup_id"], x["how"]) for x in closed] == [("LAST30_MOM_SPY", "TIME_EXIT")]


# ============================================================================================ Patch G halts
def snap(h, trade_age_s=0.5, fresh=True, halted=None):
    """One tick of the engine harness with every symbol's last trade `trade_age_s` old."""
    h.t = h.t + pd.Timedelta(seconds=1)
    if fresh:
        h.last_ok = h.t
    tr = {s: LastTrade(s, p + 0.005, 100, h.t - pd.Timedelta(seconds=trade_age_s), Feed.IEX) for s, p in h.px.items()}
    s = MarketSnapshot(h.t, h.quotes() if fresh else {}, tr, {}, h.last_ok, h.clock_offset,
                       dict(halted if halted is not None else h.halted))
    return h.eng.tick(s)


def noise_decision(h, px=651.0):
    h.px["SPY"] = px
    decs = h.step(1, {"SPY": TE.mkbars("SPY", "09:30", "09:59", 650.0, px, d=h.d)})
    return next(x for x in decs if x.candidate.setup_id == "NOISE_MOM_SPY")


def test_patch_g_a_halt_blocks_the_symbol_for_the_rest_of_the_session_and_survives_a_restart(tmp_path):
    h = TE.H(tmp_path, start="09:59:57")
    h.halted["SPY"] = True
    h.step(1)                                                       # 09:59:58: SPY halted
    assert h.c.halt_blocks == {"SPY": "HALTED"} and h.j.of("halt_block")[0]["reason"] == "HALTED"
    h.halted["SPY"] = False
    h.step(1)                                                       # 09:59:59: trading again (says the feed)
    d = noise_decision(h)                                           # 10:00:00 ... the 9:59 bar closes: a signal
    assert not d.accepted and Reason.HALTED in d.reasons and not h.sim.positions()
    # a restart the same day keeps the block (state/scalp/blocked-DATE-MODE), a reopening is never assumed
    h2 = TE.H(tmp_path, start="09:59:59")
    assert h2.c.halt_blocks == {"SPY": "HALTED"}
    d2 = noise_decision(h2)
    assert not d2.accepted and Reason.HALTED in d2.reasons
    # QQQ is untouched
    assert "QQQ" not in h2.c.halt_blocks


def test_patch_g_a_stale_last_trade_with_fresh_data_after_0935_is_a_suspected_halt(tmp_path):
    h = TE.H(tmp_path, start="09:59:57")
    snap(h, trade_age_s=C.HALT_SUSPECT_S)                           # exactly 60 s: not yet
    assert not h.c.halt_blocks
    snap(h, trade_age_s=C.HALT_SUSPECT_S + 1)
    assert h.c.halt_blocks == {"SPY": "HALT_SUSPECTED", "QQQ": "HALT_SUSPECTED"}
    line = h.j.of("halt_block")[0]
    assert line["reason"] == "HALT_SUSPECTED" and line["last_trade_age_s"] == pytest.approx(61.0)
    d = noise_decision(h)                                           # trades are fresh again: still blocked today
    assert not d.accepted and Reason.HALT_SUSPECTED in d.reasons
    # a restart the same day keeps each block with its recorded reason (a suspicion is not turned into HALTED)
    h2 = TE.H(tmp_path, start="09:59:59")
    assert h2.c.halt_blocks == {"SPY": "HALT_SUSPECTED", "QQQ": "HALT_SUSPECTED"}
    assert h2.j.of("blocked_restored")[0]["halts"] == {"SPY": "HALT_SUSPECTED", "QQQ": "HALT_SUSPECTED"}
    d2 = noise_decision(h2)
    assert not d2.accepted and Reason.HALT_SUSPECTED in d2.reasons and Reason.HALTED not in d2.reasons


def test_patch_g_the_suspicion_watch_ends_at_the_close(tmp_path):
    h = TE.H(tmp_path / "a", start="15:59:58")
    snap(h, trade_age_s=120)                                       # 15:59:59: still inside the watch
    assert h.c.halt_blocks == {"SPY": "HALT_SUSPECTED", "QQQ": "HALT_SUSPECTED"}
    h = TE.H(tmp_path / "b", start="15:59:59")
    snap(h, trade_age_s=120)                                       # 16:00:00, the close: no more trades is normal
    snap(h, trade_age_s=300)                                       # 16:00:01
    assert not h.c.halt_blocks and not h.j.of("halt_block")


def test_patch_g_no_suspicion_before_0935_or_when_our_own_data_is_stale(tmp_path):
    h = TE.H(tmp_path, start="09:33:00")
    for _ in range(5):
        snap(h, trade_age_s=300)                                   # 09:33:01 .. 09:33:05, before 09:35
    assert not h.c.halt_blocks
    h = TE.H(tmp_path / "b", start="11:00:00")
    for _ in range(5):
        snap(h, trade_age_s=300, fresh=False)                      # our polls fail: a data gap, not a halt
    assert not h.c.halt_blocks and not h.j.of("halt_block")


def test_patch_g_a_symbol_whose_quote_is_not_coming_in_is_not_suspected(tmp_path):
    h = TE.H(tmp_path, start="11:00:00")
    for _ in range(5):                                             # polls fine, but only QQQ's quote comes back
        h.t = h.t + pd.Timedelta(seconds=1)
        h.last_ok = h.t
        q = {"QQQ": h.quotes()["QQQ"]}
        tr = {s: LastTrade(s, p, 100, h.t - pd.Timedelta(seconds=120), Feed.IEX) for s, p in h.px.items()}
        h.eng.tick(MarketSnapshot(h.t, q, tr, {}, h.last_ok, h.clock_offset, dict(h.halted)))
    assert h.c.halt_blocks == {"QQQ": "HALT_SUSPECTED"}


def test_patch_g_mt_g38_a_halt_block_never_touches_the_open_position_or_its_exit(tmp_path):
    h = TE.H(tmp_path)
    TE.enter_noise(h)
    h.step(1)
    assert h.eng.slot_state is SlotState.OPEN
    for _ in range(3):
        snap(h, trade_age_s=120)                                    # SPY looks halted while we hold it
    assert h.c.halt_blocks["SPY"] == "HALT_SUSPECTED" and h.j.of("halt_block")[0]["position_open"]
    assert h.eng.trade is not None and h.eng.trade.qty == 1 and h.sim.positions()[0].qty == 1   # never marked flat
    assert h.eng.slot_state is SlotState.OPEN and not h.j.of("exit_start")                     # nothing forced
    h.eng.request_flatten("test: the way out")                     # an exit still goes out and fills
    for _ in range(10):
        snap(h, trade_age_s=120)
        if h.flat():
            break
    assert h.flat() and h.j.of("exit_start")[0]["reason"] == "SHUTDOWN" and h.j.of("trade_closed")


# ============================================================================================ Patch E
def test_patch_e_excursions_are_measured_from_the_bid_and_journalled_apart_from_pnl(tmp_path):
    h = TE.H(tmp_path)
    d = TE.enter_noise(h)                                          # 10:00:01, buys 1 SPY at the ask 651.01
    spec = d.order
    per = spec.limit_price - spec.stop_limit_price
    entry = h.eng.trade.avg_buy()
    h.step(1)
    up = round(entry + 0.6 * per, 2)                               # bid +0.6R (below the 1% take-profit)
    h.px["SPY"] = up
    h.step(1)                                                      # 10:00:03
    h.feed = False                                                 # 5 s without a new quote: the last one
    for _ in range(5):                                             # counts for QUOTE_MAX_AGE_S, then 3 s unseen
        h.step(1)
    h.feed = True
    down = round(entry - 0.3 * per, 2)
    h.px["SPY"] = down
    h.step(1)                                                      # 10:00:09
    h.eng.request_flatten("test")
    while h.eng.trade is not None:
        h.step(1)
    closed = h.j.of("trade_closed")[0]
    dg = closed["diag"]
    assert dg["basis"] == "bid (long)" and dg["entry"] == pytest.approx(entry)
    assert dg["r_per_share"] == pytest.approx(per, abs=1e-4)
    assert dg["mfe_r"] == pytest.approx((up - entry) / per, abs=1e-3)
    assert dg["mae_r"] == pytest.approx((entry - down) / per, abs=1e-3)
    assert dg["t_plus_025r_s"] == dg["t_plus_05r_s"] == pytest.approx(2.0)    # first fill 10:00:01, seen 10:00:03
    assert dg["t_plus_1r_s"] is None and dg["gaps"] and dg["no_quote_s"] == pytest.approx(3.0)
    # measurement only: the realized P&L is the fills' P&L, nothing from the quote path
    br = X.pnl_breakdown([tuple(x) for x in closed["buys"]], [tuple(x) for x in closed["sells"]], h.d)
    assert closed["honest_pnl"] == pytest.approx(br["honest_pnl"]) and closed["paper_pnl"] == pytest.approx(
        br["paper_pnl"])
    # and the report shows it per setup, under strategy performance
    text = REP.build_report(h.j.lines, REG)
    line = next(x for x in text.splitlines() if x.startswith("[EXPLORATORY] NOISE_MOM_SPY  excursions"))
    assert "measurement only, not P&L" in line and "reached +0.25R 1/1, +0.5R 1/1, +1R 0/1" in line
    assert "1 trade(s) with seconds without a quote" in line


def test_patch_e_a_long_pause_between_ticks_counts_as_unobserved_even_with_a_fresh_quote_at_the_end(tmp_path):
    h = TE.H(tmp_path)
    TE.enter_noise(h)                                              # 10:00:01
    h.step(1)                                                      # 10:00:02: seen
    h.step(C.DATA_SILENCE_S + 3)                                   # 10:00:07: fresh quote, but 5 s not looked at
    dg = h.eng.trade.diag
    assert dg["quote_ticks"] == 2 and dg["no_quote_s"] == pytest.approx(C.DATA_SILENCE_S + 3)
    h.step(1)                                                      # a normal 1 s tick adds nothing unobserved
    assert h.eng.trade.diag["no_quote_s"] == pytest.approx(C.DATA_SILENCE_S + 3)
    h.eng.request_flatten("test")
    while h.eng.trade is not None:
        h.step(1)
    out = h.j.of("trade_closed")[0]["diag"]
    assert out["gaps"] is True and out["no_quote_s"] == pytest.approx(C.DATA_SILENCE_S + 3)


def test_patch_e_the_tick_that_closes_the_trade_is_still_measured(tmp_path):
    h = TE.H(tmp_path)
    d = TE.enter_noise(h)                                          # 10:00:01
    spec = d.order
    per, entry = spec.limit_price - spec.stop_limit_price, h.eng.trade.avg_buy()
    h.step(1)                                                      # 10:00:02: bid flat
    h.px["SPY"] = up = round(max(entry + 1.2 * per, spec.take_profit + 0.05), 2)
    h.step(1)                                                      # 10:00:03: the take-profit fills on this tick
    assert h.eng.trade is None
    closed = h.j.of("trade_closed")[0]
    dg = closed["diag"]
    assert closed["how"] == "target" and dg["quote_ticks"] == 2
    assert dg["t_plus_1r_s"] == pytest.approx(2.0) and dg["mfe_r"] == pytest.approx((up - entry) / per, abs=1e-3)


def test_patch_e_report_says_none_measured_without_diagnostics():
    lines = [{"kind": "trade_closed", "ts": "2026-10-01T11:00:00-04:00", "setup_id": "ORB5_QQQ", "symbol": "QQQ",
              "lane": "EXPLORATORY", "how": "stop", "paper_pnl": -1.0, "honest_pnl": -1.05, "qty": 1}]
    text = REP.build_report(lines, REG)
    assert "[EXPLORATORY] ORB5_QQQ  excursions (Notes 1 Patch E, measurement only, not P&L): none measured " \
           "(1 closed trades)" in text


# ============================================================================================ Patch F
def test_patch_f_engine_journals_quote_age_ack_latency_fill_latency_and_data_gaps(tmp_path):
    h = TE.H(tmp_path)
    TE.enter_noise(h)
    dec = h.j.of("decision")[0]
    assert dec["notes"]["quote_age_s"] == pytest.approx(0.0)
    ws = h.j.of("would_submit")[0]
    assert ws["ack_ms"] == pytest.approx(0.0) and ws["ack_status"]
    fill = h.j.of("fill")[0]
    assert fill["order_qty"] == 1 and fill["filled_total"] == 1 and fill["cancel_race"] is False
    assert fill["latency"]["seen_after_submit_s"] == pytest.approx(0.0)
    h.feed = False
    for _ in range(5):
        h.step(1)
    h.feed = True
    h.step(1)
    gap = h.j.of("data_gap")
    # from the last good poll (10:00:01) to the next one (10:00:07)
    assert len(gap) == 1 and gap[0]["seconds"] == pytest.approx(6.0) and h.j.of("data_gap_start")
    h.eng.request_flatten("test")
    while h.eng.trade is not None:
        h.step(1)
    xo = h.j.of("exit_order")[0]
    assert xo["ack_ms"] == pytest.approx(0.0) and xo["ack_status"]


def test_patch_f_a_fill_that_raced_the_cancel_request_is_marked(tmp_path):
    h = TE.H(tmp_path, sim_kw={"fill_delay_s": 3, "cancel_delay_s": 4})
    TE.enter_noise(h)
    h.until("10:00:06")
    fill = next(x for x in h.j.of("fill") if x["role"] == "entry")
    assert fill["cancel_race"] is True and fill["latency"]["seen_after_submit_s"] == pytest.approx(3.0)


def _trades(n, honest, day="2026-10-01"):
    out = []
    for i in range(n):
        out.append({"kind": "trade_closed", "ts": f"{day}T11:{i:02d}:01-04:00", "setup_id": "LAST30_MOM_SPY",
                    "symbol": "SPY", "lane": "EXPLORATORY", "how": "stop", "paper_pnl": honest + 0.03,
                    "honest_pnl": honest, "r": honest, "risk_usd": 1.0, "qty": 1, "buys": [[1, 650.0]]})
    return out


INCIDENTS = [
    {"kind": "broker_reject", "ts": "2026-10-01T10:00:01-04:00", "setup_id": "LAST30_MOM_SPY", "symbol": "SPY"},
    {"kind": "exit_rejected", "ts": "2026-10-01T10:00:02-04:00", "setup_id": "LAST30_MOM_SPY"},
    {"kind": "data_gap_start", "ts": "2026-10-01T10:01:00-04:00"},
    {"kind": "data_gap", "ts": "2026-10-01T10:01:09-04:00", "seconds": 9.0},
    {"kind": "cancel_failed", "ts": "2026-10-01T10:02:00-04:00"},
    {"kind": "submit", "ts": "2026-10-01T10:03:00-04:00", "ack_ms": 180.0, "setup_id": "LAST30_MOM_SPY"},
    {"kind": "exit_order", "ts": "2026-10-01T10:04:00-04:00", "ack_ms": 95.0, "setup_id": "LAST30_MOM_SPY"},
    {"kind": "fill", "ts": "2026-10-01T10:03:01-04:00", "setup_id": "LAST30_MOM_SPY", "symbol": "SPY", "side": "buy",
     "role": "entry", "qty": 1, "order_qty": 2, "filled_total": 1, "cancel_race": True, "price": 650.0,
     "latency": {"seen_after_submit_s": 1.0, "broker_submit_to_fill_s": 0.6},
     "slippage": {"cents": 1.0, "bps": 0.15}, "feed": "IEX"},
    {"kind": "decision", "ts": "2026-10-01T10:03:00-04:00", "setup_id": "LAST30_MOM_SPY", "action": "enter",
     "accepted": True, "reasons": [], "notes": {"quote_age_s": 2.5}},
    {"kind": "halt_block", "ts": "2026-10-01T10:05:00-04:00", "symbol": "QQQ", "reason": "HALT_SUSPECTED"},
]


def test_patch_f_report_keeps_execution_health_apart_and_says_uncalibrated():
    text = REP.build_report(_trades(3, -0.5) + INCIDENTS, REG, operating_costs=[])
    ex, st = text.index("EXECUTION HEALTH"), text.index("STRATEGY PERFORMANCE")
    assert text.index("Changes log") < ex < st
    health = text[ex:st]
    assert "quote age at entry decisions: median 2.50 s, max 2.50 s over 1; 1 older than 2 s" in health
    assert "data gaps in the session (no data for more than 2 s): 1, 9 s in all" in health
    assert "entries median 180 ms" in health and "exits median 95 ms" in health
    assert "broker submitted -> filled: median 0.60 s" in health
    assert "partial fills: 1 entry order(s)" in health and "fills that raced a cancel request: 1" in health
    assert "cancel requests the broker refused: 1" in health
    assert "broker rejections: entries 1, exits 1, kill orders 0" in health
    assert "QQQ HALT_SUSPECTED x1" in health
    assert health.count("uncalibrated: no registered baseline") >= 4
    assert "[EXPLORATORY] LAST30_MOM_SPY  median slippage 1.00 cents / 0.15 bps over 1 fills [FEED=IEX] vs model " \
           "1.5 bps per side (MT-G3)" in health
    strat = text[st:]
    assert "[EXPLORATORY] LAST30_MOM_SPY (SPY v1): 3 closed trades" in strat and "median slippage" not in strat


def test_patch_f_execution_incidents_never_feed_the_mt_g12_switch_off(tmp_path):
    def g12(lines):
        return [x for x in REP.build_report(lines, REG, operating_costs=[]).splitlines()
                if "LAST30_MOM_SPY" in x and "MT-G12" in x]
    losers, winners = _trades(30, -0.5), _trades(30, 0.4)
    assert g12(losers) == g12(losers + INCIDENTS * 20) and "-> SHADOW" in g12(losers)[0]
    assert g12(winners) == g12(winners + INCIDENTS * 20) and "keep (30 R values" in g12(winners)[0]
    # the engine's own switch-off history (runner.lane_history) reads closed trades only, too
    jp = J.journal_path(tmp_path, date(2026, 10, 1), Mode.DRY)
    jp.parent.mkdir(parents=True)
    jp.write_text("\n".join(__import__("json").dumps({**x, "version": 1}) for x in winners + INCIDENTS * 20) + "\n")
    h = RUN.lane_history(REG, None, tmp_path, Mode.DRY)[("LAST30_MOM_SPY", "SPY")]
    assert h["r"] == [0.4] * 30
    assert G.lane_check_pending(h["r"], [], [], None, None)[0] is None


# ============================================================================================ Patch H
def test_patch_h_committed_operating_costs_record_unknown_hosting_as_not_recorded():
    costs = REP.load_operating_costs()
    by = {c["name"]: c for c in costs}
    assert by["Alpaca market data"]["usd_per_month"] == 0.0
    assert by["LLM / API usage"]["usd_per_month"] == 0.0
    assert by["Hosting and monitoring"]["usd_per_month"] is None and by["Hosting and monitoring"]["source"] == "unknown"
    text = REP.build_report(_trades(2, 1.0), REG)
    op = text[text.index("TRADING P&L AND OPERATING RESULT"):]
    assert "trading P&L (honest: fees and honest slippage included): $2.00 over 2 closed trades" in op
    assert "Hosting and monitoring not recorded" in op and "Hosting and monitoring $" not in op
    assert "operating result (trading P&L - recorded costs): $2.00  <- incomplete: Hosting and monitoring not " \
           "recorded" in op


def test_v2_20_fixed_costs_above_trading_pnl_give_a_negative_operating_result_without_touching_pnl():
    costs = [{"name": "VPS", "usd_per_month": 304.375, "source": "invoice", "note": ""}]
    lines = _trades(2, 1.0)                                         # one calendar day: $304.375 / 30.4375 = $10
    text = REP.build_report(lines, REG, operating_costs=costs)
    assert "trading P&L (honest: fees and honest slippage included): $2.00 over 2 closed trades" in text
    assert "VPS $10.00 ($304.38/month)" in text
    assert "operating result (trading P&L - recorded costs): $-8.00" in text and "incomplete" not in text
    # the strategy lines are the same with or without running costs
    strat = lambda t: t[t.index("STRATEGY PERFORMANCE"):t.index("TRADING P&L")]  # noqa: E731
    assert strat(text) == strat(REP.build_report(lines, REG, operating_costs=[]))


def test_patch_h_bad_cost_files_are_refused(tmp_path):
    p = tmp_path / "c.json"
    for bad in ({"costs": [{"name": "x", "usd_per_month": -1, "source": "s"}]},
                {"costs": [{"name": "", "usd_per_month": 1, "source": "s"}]},
                {"costs": [{"name": "x", "usd_per_month": "5", "source": "s"}]},
                {"costs": [{"name": "x", "usd_per_month": 1, "source": ""}]}):
        p.write_text(__import__("json").dumps(bad))
        with pytest.raises(ValueError):
            REP.load_operating_costs(p)
    text = REP.build_report(_trades(1, 1.0), REG, operating_costs=None)
    assert "operating_costs.json missing or unreadable: not recorded; no operating result" in text


def test_patch_h_nothing_but_the_report_reads_the_operating_costs():
    for f in LIVE.glob("*.py"):
        src = f.read_text()
        if f.name != "report.py":
            assert "operating_costs" not in src and "load_operating_costs" not in src, f.name
    assert "operating" not in (LIVE / "sizing.py").read_text()


# ============================================================================================ Patch G margin record
def test_patch_g_margin_framework_is_a_dated_record():
    mf = C.margin_framework(date(2026, 9, 29))
    assert mf["framework"] == "MARGIN_INTRADAY_FRAMEWORK" and mf["source"] == C.MARGIN_FRAMEWORK_SOURCE
    assert mf["checked"] == "2026-09-28" and mf["effective"] == "2026-06-04" and mf["age_days"] == 1
    assert "record only" in mf["use"]
    assert C.margin_framework(date(2026, 6, 3))["framework"] == "UNKNOWN"
    assert C.margin_framework(date(2026, 9, 29), "https://api.example.com")["framework"] == "UNKNOWN"


def test_patch_g_check_account_prints_the_margin_framework(tmp_path):
    import lab.scalp.live.__main__ as cli
    from test_scalp_live_runtime import FakeTC
    env = {"ALPACA_SCALP_KEY": "sk", "ALPACA_SCALP_SECRET": "ss", "ALPACA_RULES_KEY": "rk",
           "ALPACA_RULES_SECRET": "rs"}
    nums = {"sk": "PA3SCALPGWRL", "rk": "PA9RULESXXXX"}
    msgs = []
    assert cli.check_account(env, lambda k, s: FakeTC(nums[k]), tmp_path, msgs.append) == 0
    line = next(m for m in msgs if "margin framework" in m)
    assert "MARGIN_INTRADAY_FRAMEWORK" in line and C.MARGIN_FRAMEWORK_SOURCE in line and "checked 2026-09-28" in line


def test_patch_g_startup_journal_records_the_margin_framework(tmp_path, monkeypatch):
    from lab.scalp.live import broker as B
    from lab.scalp.live.model import AccountView
    from lab.scalp.signals import Ctx
    from test_scalp_live_runtime import QUIET as RQ, Clock, FakeIEX, FakeTime
    from test_scalp_live_runtime import ts as rts
    clock = Clock(rts("15:58:30", RQ))

    class Trading:
        def get_clock(self):
            return SimpleNamespace(timestamp=clock().tz_convert("UTC").to_pydatetime())

    class Reader:
        def __init__(self, mode=Mode.DRY, **k):
            assert Mode(mode) is Mode.DRY

        def account(self):
            return AccountView("PA0TESTGWRL", "ACTIVE", 100_050.0, 100_000.0, 100_000.0, 200_000.0, 100_000.0,
                               False, False, "https://paper-api.alpaca.markets")

    monkeypatch.setattr(RUN, "scalp_clients", lambda env=None: (FakeIEX(clock), Trading()))
    monkeypatch.setattr(B, "AlpacaBroker", Reader)
    monkeypatch.setattr(M, "build_context", lambda sym, d, *a, **k: (
        Ctx(prev_close=649.0), M.CalendarRow(d, rts("09:30", d), rts("16:00", d)), []))
    monkeypatch.setattr(RUN, "now_ny", clock)
    monkeypatch.setattr(RUN, "time", FakeTime(clock))
    assert RUN.run("dry", no_watchdog=True, state_dir=tmp_path, env={}, out=lambda s: None) == 0
    start = next(x for x in J.read_journal(J.journal_path(tmp_path, RQ, Mode.DRY)) if x["kind"] == "startup")
    mf = start["margin_framework"]
    assert mf["framework"] == "MARGIN_INTRADAY_FRAMEWORK" and mf["source"] == C.MARGIN_FRAMEWORK_SOURCE
    assert mf["checked"] == "2026-09-28"
