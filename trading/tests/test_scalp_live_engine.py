"""Live paper minute trader, section B execution: engine, guard and restore (lab/scalp/live). All offline: a
SimBroker, a fake clock and a memory journal. No network, no keys, no system clock, no real state directory."""
from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from lab.scalp import backtest as bt
from lab.scalp import signals as sg
from lab.scalp.live import clock as K
from lab.scalp.live import config as C
from lab.scalp.live import events as E
from lab.scalp.live import orders as O
from lab.scalp.live import restore as RS
from lab.scalp.live import state as S
from lab.scalp.live import risk as R
from lab.scalp.live.broker import SimBroker
from lab.scalp.live.engine import Engine
from lab.scalp.live.guard import ExitDelayed, GuardedBroker
from lab.scalp.live.journal import MemoryJournal
from lab.scalp.live.model import (Bar, BrokerReject, Candidate, DayCounters, Feed, Kind, LastTrade, MarketSnapshot,
                                  Mode, PositionView, Quote, Reason, RunawayOrders, SlotState, as_ny)

D = date(2026, 10, 1)
REG = C.load_registry()
ORB5, LAST30, NOISE = REG.get("ORB5_QQQ", "QQQ"), REG.get("LAST30_MOM_SPY", "SPY"), REG.get("NOISE_MOM_SPY", "SPY")
KNOWN = E.DayEvents(known=True)


def ts(hms, d=D):
    return as_ny(f"{d.isoformat()} {hms}")


def session(d=D):
    return K.SessionTimes.from_calendar(d, ts("09:30", d), ts("16:00", d))


def ctxs():
    return {"SPY": sg.Ctx(prev_close=648.0, sigma=np.full(391, 0.001), daily_vol=0.01),
            "QQQ": sg.Ctx(prev_close=558.0, sigma=np.full(391, 0.001), daily_vol=0.01)}


def mkbars(sym, start, end, p0, p1, wick=0.05, d=D):
    s, e = ts(start, d), ts(end, d)
    n = int((e - s).total_seconds() // 60) + 1
    closes = np.linspace(p0, p1, n)
    opens = np.r_[p0, closes[:-1]]
    return [Bar(sym, s + pd.Timedelta(minutes=k), float(o), float(max(o, c) + wick), float(min(o, c) - wick),
                float(c), 10_000.0, Feed.IEX) for k, (o, c) in enumerate(zip(opens, closes))]


class H:
    """A fake clock, a SimBroker, a memory journal and an Engine in DRY mode."""

    def __init__(self, tmp_path, start="10:00:00", e0=100_000.0, registry=REG, counters=None, adopted=None,
                 sim=None, sim_kw=None, px=None, d=D, mode=Mode.DRY):
        self.d = d
        self.t = ts(start, d)
        self.clock = lambda: self.t
        self.px = dict(px or {"SPY": 650.0, "QQQ": 560.0})
        self.feed = True
        self.clock_offset = 20.0
        self.halted = {s: False for s in self.px}
        self.last_ok = self.t
        self.sim = sim if sim is not None else SimBroker(self.clock, **(sim_kw or {}))
        if sim is not None:
            sim.clock = self.clock
        self.j = MemoryJournal(Mode.DRY, self.clock)
        self.c = counters or DayCounters(d, e0, cash_prev_close=e0)
        self.state = tmp_path / "state"
        self.sim.update(self.t, self.quotes())
        self.eng = Engine(self.sim, self.j, registry, self.c, session(d), KNOWN, ctxs(), mode, self.clock,
                          adopted=adopted, state_dir=self.state)

    def quotes(self):
        return {s: Quote(s, p, round(p + 0.01, 2), 100, 100, self.t, self.t, Feed.IEX) for s, p in self.px.items()}

    def step(self, secs=1.0, bars=None):
        self.t = self.t + pd.Timedelta(seconds=secs)
        if self.feed:
            self.last_ok = self.t
        q = self.quotes() if self.feed else {}
        tr = {s: LastTrade(s, p + 0.005, 100, self.t - pd.Timedelta(milliseconds=500), Feed.IEX)
              for s, p in self.px.items()} if self.feed else {}
        snap = MarketSnapshot(self.t, q, tr, bars or {}, self.last_ok, self.clock_offset, dict(self.halted))
        out = self.eng.tick(snap)
        assert all(p.qty >= 0 for p in self.sim.positions()), "MT-G15: a short position appeared"
        return out

    def until(self, hms, secs=1.0):
        end = ts(hms, self.d)
        out = []
        while self.t + pd.Timedelta(seconds=secs) <= end:
            out += self.step(secs)
        return out

    def flat(self):
        return not self.sim.positions() and not self.sim.open_orders()

    def flag(self, name):
        """This engine's flag file: the plain name in PAPER, `<name>-dry` in DRY (state.flag_name, MT-G27)."""
        return self.state / S.flag_name(name, self.eng.mode)


def enter_noise(h, px=651.0):
    """NOISE_MOM_SPY goes long at 10:00:01 (the 9:59 bar closed above the noise band)."""
    assert h.t == ts("10:00:00", h.d)
    h.px["SPY"] = px
    decs = h.step(1, {"SPY": mkbars("SPY", "09:30", "09:59", 650.0, px, d=h.d)})
    noise = [x for x in decs if x.candidate.setup_id == "NOISE_MOM_SPY"]
    assert len(noise) == 1 and noise[0].accepted, noise
    return noise[0]


# ============================================================================================ basic flow
def test_entry_is_a_bracket_that_fills_and_gets_its_stop_confirmed(tmp_path):
    h = H(tmp_path)
    d = enter_noise(h)
    spec = d.order
    assert spec.order_class == "bracket" and spec.kind is Kind.ENTRY and spec.qty == 1
    assert spec.stop_price < spec.limit_price < spec.take_profit and spec.stop_limit_price < spec.stop_price
    assert h.sim.positions()[0].qty == 1
    h.step(1)
    assert h.eng.slot_state is SlotState.OPEN and h.eng.trade.stop_confirmed
    assert h.j.of("would_submit") and not h.j.of("submit")          # DRY mode: nothing sent anywhere
    assert h.c.entry_submits == 1 and h.c.round_trips == 1 and h.c.round_trips_by_setup == {"NOISE_MOM_SPY": 1}
    fill = h.j.of("fill")[0]
    assert fill["lane"] == "EXPLORATORY" and fill["setup_id"] == "NOISE_MOM_SPY" and fill["slippage"] is not None
    dec = h.j.of("decision")[0]
    assert dec["accepted"] and dec["lane"] == "EXPLORATORY" and dec["feed"] == "IEX"
    st = h.eng.status()
    assert st["slot"] == "OPEN" and st["position"]["qty"] == 1 and st["counters"]["round_trips"] == 1


def test_dry_mode_trades_on_a_simbroker_only(tmp_path):
    class NotSim:
        mode = Mode.PAPER
    with pytest.raises(ValueError):
        Engine(NotSim(), MemoryJournal(), REG, DayCounters(D, 1e5), session(), KNOWN, ctxs(), Mode.DRY,
               lambda: ts("10:00"))


def test_mt_g2_second_signal_while_the_slot_is_taken_is_rejected(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.until("10:30:00", 30)
    h.px["SPY"] = 651.5
    decs = h.step(1, {"SPY": mkbars("SPY", "10:00", "10:29", 651.0, 651.5)})
    assert all(not x.accepted or Reason.SETUP_EXIT in x.reasons for x in decs)
    assert len(h.sim.submits) == 1


def test_short_signal_is_rejected_and_never_sent(tmp_path):
    h = H(tmp_path)
    h.px["SPY"] = 646.0
    decs = h.step(1, {"SPY": mkbars("SPY", "09:30", "09:59", 650.0, 646.0)})
    noise = [x for x in decs if x.candidate.setup_id == "NOISE_MOM_SPY"]
    assert noise and noise[0].candidate.side == -1 and not noise[0].accepted
    assert Reason.SHORT_DISABLED in noise[0].reasons and h.sim.submits == []
    assert h.j.of("decision")[0]["shadow"] is True


# ============================================================================================ MT-G18 daily stop
def test_mt_g18_daily_stop_at_1102_is_flat_within_10_seconds(tmp_path):
    h = H(tmp_path, counters=DayCounters(D, 100_000.0, cash_prev_close=100_000.0, realized_honest=-24.0))
    enter_noise(h)
    h.until("11:01:59", 30)
    h.until("11:01:59")
    assert h.eng.slot_state is SlotState.OPEN
    h.px["SPY"] = 650.0                     # -1.01 paper, about -1.06 honest: -25.06 <= -$25
    h.step(1)
    assert h.t == ts("11:02:00") and h.c.daily_stopped and h.j.of("daily_stop")
    h.until("11:02:10")
    assert h.flat() and h.eng.trade is None
    assert h.eng.slot_state is SlotState.DISABLED
    closed = h.j.of("trade_closed")[-1]
    assert closed["how"] == "DAILY_STOP"
    n = len(h.sim.submits)
    h.until("11:30:00", 10)
    h.px["SPY"] = 652.0
    decs = h.step(1, {"SPY": mkbars("SPY", "11:00", "11:29", 651.0, 652.0)})   # a new NOISE entry signal
    assert decs and all(Reason.DAILY_STOP in x.reasons for x in decs if x.candidate.action == "enter")
    assert len(h.sim.submits) == n                                                 # no orders after the stop
    # the stop is written for today only: tomorrow's engine starts fresh
    assert h.flag(f"daily_stop-{D.isoformat()}").exists()
    d2 = D + timedelta(days=1)
    h2 = H(tmp_path, d=d2)
    assert not h2.c.daily_stopped and h2.eng.slot_state is SlotState.FLAT


# ============================================================================================ MT-G40 restart
def _round_trip(sim, clk, setup_id, sym, bar_hhmm, buy, sell, how="exit", e0=7_000.0):
    """One SCALP round trip straight on the SimBroker (a history the bot left before a crash)."""
    reg = REG.get(setup_id, sym)
    t0 = clk["t"]
    sim.set_quote(sym, buy - 0.01, buy)
    cand = Candidate(setup_id, reg.version, sym, "enter", 1, ts(bar_hhmm), stop=None if reg.overlay_stop_pct else
                     buy - 2.0, target_r=None if reg.overlay_stop_pct else 10.0)
    spec, reasons, _ = O.entry_bracket(cand, reg, sim.quotes[sym], e0, D, 0)
    assert spec is not None, reasons
    parent = sim.submit(spec)
    assert parent.status == "filled"
    clk["t"] = t0 + pd.Timedelta(minutes=2)
    if how == "stop":
        sl = [x for x in sim.get_order(parent.id).legs if x.order_type == "stop_limit"][0]
        sim.set_quote(sym, sl.stop_price - 0.01, sl.stop_price)
    else:
        for leg in sim.get_order(parent.id).legs:
            sim.cancel(leg.id)
        sim.set_quote(sym, sell, sell + 0.01)
        sim.submit(O.exit_limit(sym, 1, sim.quotes[sym], None, 0.0005, Kind.EXIT, setup_id=setup_id,
                                version=reg.version, session_date=D, bar_start=ts(bar_hhmm), leg="X", attempt=0))
    assert not sim.positions()
    clk["t"] = t0 + pd.Timedelta(minutes=5)


def _history(trades):
    clk = {"t": ts("10:00:01")}
    sim = SimBroker(lambda: clk["t"])
    for setup_id, sym, hhmm, buy, sell, how in trades:
        clk["t"] = ts(hhmm) + pd.Timedelta(seconds=61)
        _round_trip(sim, clk, setup_id, sym, hhmm, buy, sell, how)
    return sim, clk


def test_mt_g40_restart_after_three_trades_and_0_9pct_loss_keeps_the_counts(tmp_path):
    e0 = 7_000.0                         # 0.9% = $63; the daily limit is min($25, 0.5% x E0) = $25
    sim, clk = _history([("NOISE_MOM_SPY", "SPY", "10:00", 650.0, 629.0, "exit"),
                         ("NOISE_MOM_SPY", "SPY", "10:30", 650.0, 629.0, "exit"),
                         ("ORB5_QQQ", "QQQ", "11:00", 560.0, 539.2, "exit")])
    now = ts("11:40:00")
    cnt, st = RS.rebuild(sim, D, e0, e0, D - timedelta(days=3), D, REG, now)
    assert cnt.round_trips == 3 and cnt.entry_submits == 3
    assert cnt.round_trips_by_setup == {"NOISE_MOM_SPY": 2, "ORB5_QQQ": 1}
    assert cnt.realized_honest == pytest.approx(-(21.01 + 21.01 + 20.81) - 0.06 * 3 - 0.03 * 3, abs=0.2)
    assert cnt.realized_honest <= -0.009 * e0 + 0.5
    assert cnt.loss_streak == 3 and cnt.loss_pause_until is not None
    assert cnt.week_honest == pytest.approx(cnt.realized_honest) and cnt.test_sessions == 1
    assert cnt.e0 == e0 and R.daily_limit(cnt.e0) == 25.0
    assert st.trade is None and st.pending_entry is None and st.cancel_ids == []
    # the restarted engine still refuses: the daily stop sits at -$25 of the ORIGINAL E0, NOISE used its 2
    h = H(tmp_path, start="12:00:00", counters=cnt, sim=sim, e0=e0)
    h.px["SPY"] = 652.0
    decs = h.step(1, {"SPY": mkbars("SPY", "11:30", "11:59", 650.5, 652.0)})
    noise = [x for x in decs if x.candidate.setup_id == "NOISE_MOM_SPY"]
    assert noise and not noise[0].accepted
    assert {Reason.DAILY_STOP, Reason.MAX_TRADES_SETUP} <= set(noise[0].reasons)
    assert len(sim.submits) == 6 and h.eng.broker.entry_count == 3


def test_mt_g40_restart_after_four_trades_rejects_the_fifth(tmp_path):
    sim, _ = _history([("NOISE_MOM_SPY", "SPY", "10:00", 650.0, 650.10, "exit"),
                       ("ORB5_QQQ", "QQQ", "10:10", 560.0, 560.10, "exit"),
                       ("LAST30_MOM_SPY", "SPY", "10:20", 650.0, 650.10, "exit"),
                       ("ORB5_QQQ", "QQQ", "10:40", 560.0, 560.10, "exit")])
    cnt, _ = RS.rebuild(sim, D, 100_000.0, 100_000.0, None, None, REG, ts("11:59:00"))
    assert cnt.round_trips == 4 and cnt.loss_streak == 0 and not cnt.daily_stopped
    h = H(tmp_path, start="12:00:00", counters=cnt, sim=sim)
    h.px["SPY"] = 652.0
    decs = h.step(1, {"SPY": mkbars("SPY", "11:30", "11:59", 650.5, 652.0)})
    noise = [x for x in decs if x.candidate.setup_id == "NOISE_MOM_SPY"]
    assert noise and Reason.MAX_TRADES_DAY in noise[0].reasons and Reason.DAILY_STOP not in noise[0].reasons


def test_mt_g17_restore_rebuilds_the_stopout_timer_from_a_stop_leg_fill():
    sim, _ = _history([("NOISE_MOM_SPY", "SPY", "10:00", 650.0, 0.0, "stop")])
    cnt, _ = RS.rebuild(sim, D, 100_000.0, 100_000.0, None, None, REG, ts("10:10:00"))
    until = cnt.stopout_until[("NOISE_MOM_SPY", "SPY")]
    assert until == ts("10:03:01") + pd.Timedelta(minutes=C.STOPOUT_REENTRY_MIN) and cnt.loss_streak == 1


def test_mt_g40_restore_adopts_a_protected_position(tmp_path):
    clk = {"t": ts("10:00:01")}
    sim = SimBroker(lambda: clk["t"])
    sim.set_quote("SPY", 650.0, 650.01)
    cand = Candidate("NOISE_MOM_SPY", 1, "SPY", "enter", 1, ts("09:59"))
    spec, _, _ = O.entry_bracket(cand, NOISE, sim.quotes["SPY"], 100_000.0, D, 0)
    sim.submit(spec)
    clk["t"] = ts("10:05:00")
    cnt, st = RS.rebuild(sim, D, 100_000.0, 100_000.0, None, None, REG, clk["t"])
    assert st.trade is not None and st.trade.protected and st.trade.setup_id == "NOISE_MOM_SPY"
    assert cnt.round_trips == 1 and cnt.entry_submits == 1
    h = H(tmp_path, start="10:05:00", counters=cnt, adopted=st, sim=sim, px={"SPY": 650.0, "QQQ": 560.0})
    assert h.eng.slot_state is SlotState.OPEN
    h.until("10:05:40")
    assert h.eng.trade is not None and not h.j.of("reconcile_halt") and not h.j.of("kill_start")
    h.t = ts("15:49:59")
    h.step(1)
    h.step(1)
    assert h.flat() and h.j.of("trade_closed")[-1]["how"] == "TIME_EXIT"


def test_mt_g40_restore_flattens_a_position_without_a_live_stop(tmp_path):
    clk = {"t": ts("10:00:01")}
    sim = SimBroker(lambda: clk["t"])
    sim.set_quote("SPY", 650.0, 650.01)
    spec, _, _ = O.entry_bracket(Candidate("NOISE_MOM_SPY", 1, "SPY", "enter", 1, ts("09:59")), NOISE,
                                 sim.quotes["SPY"], 100_000.0, D, 0)
    p = sim.submit(spec)
    sl = [x for x in sim.get_order(p.id).legs if x.order_type == "stop_limit"][0]
    sim.cancel(sl.id)                                  # the stop leg is gone
    clk["t"] = ts("10:05:00")
    cnt, st = RS.rebuild(sim, D, 100_000.0, 100_000.0, None, None, REG, clk["t"])
    assert st.trade is not None and not st.trade.protected
    h = H(tmp_path, start="10:05:00", counters=cnt, adopted=st, sim=sim, px={"SPY": 650.0, "QQQ": 560.0})
    h.step(1)
    h.step(1)
    assert h.flat()
    assert h.j.of("exit_start")[0]["reason"] == "UNPROTECTED_POSITION"
    assert h.j.of("exit_order")[0]["cid"].split("-")[4].startswith("P")


def test_mt_g40_restore_cancels_an_unfilled_entry_parent(tmp_path):
    clk = {"t": ts("10:00:01")}
    sim = SimBroker(lambda: clk["t"], fill_delay_s=1e9)
    sim.set_quote("SPY", 650.0, 650.01)
    spec, _, _ = O.entry_bracket(Candidate("NOISE_MOM_SPY", 1, "SPY", "enter", 1, ts("09:59")), NOISE,
                                 sim.quotes["SPY"], 100_000.0, D, 0)
    sim.submit(spec)
    clk["t"] = ts("10:00:30")
    cnt, st = RS.rebuild(sim, D, 100_000.0, 100_000.0, None, None, REG, clk["t"])
    assert st.pending_entry is not None and cnt.entry_submits == 1 and cnt.round_trips == 0
    h = H(tmp_path, start="10:00:30", counters=cnt, adopted=st, sim=sim)
    assert any(x["reason"] == "ORDER_STATE_UNCERTAIN" for x in h.j.of("cancel_request"))
    h.step(1)
    assert h.flat() and h.eng.trade is None and h.eng.slot_state is SlotState.FLAT


# ============================================================================================ MT-G26 reconcile
def test_mt_g26_phantom_10_spy_shares_halt_within_10_seconds(tmp_path):
    h = H(tmp_path, start="09:35:00")
    h.px["QQQ"] = 561.0
    decs = h.step(1, {"QQQ": mkbars("QQQ", "09:30", "09:34", 560.0, 561.0)})
    assert [x.accepted for x in decs if x.candidate.setup_id == "ORB5_QQQ"] == [True]
    h.until("09:35:05")
    h.sim.inject_position("SPY", 10, 650.0)             # shares at the broker that the bot never bought
    t0 = h.t
    while h.t < t0 + pd.Timedelta(seconds=10) and not h.j.of("kill_done"):
        h.step(1)
    assert h.j.of("reconcile_halt") and h.j.of("kill_done"), h.j.kinds()
    assert h.t - t0 <= pd.Timedelta(seconds=10) and h.flat()
    assert h.flag("HALT").exists() and Reason.RECONCILE_MISMATCH in h.eng.flags
    assert h.eng.slot_state is SlotState.DISABLED


class LaggyPositions(SimBroker):
    """The broker's positions endpoint shows a fill 2 s late (the order already says filled)."""

    def positions(self):
        now = self.now()
        qty = {p.symbol: p.qty for p in super().positions()}
        for f in self.fills:
            if now - f["ts"] < pd.Timedelta(seconds=2):
                qty[f["symbol"]] = qty.get(f["symbol"], 0.0) - (f["qty"] if f["side"] == "buy" else -f["qty"])
        return [PositionView(s, q, 650.0) for s, q in sorted(qty.items()) if abs(q) > 1e-9]


def test_mt_g26_a_fill_arriving_2_seconds_late_does_not_halt(tmp_path):
    h = H(tmp_path, sim=LaggyPositions(lambda: ts("10:00:00")))
    enter_noise(h)                                      # the entry fill shows up 2 s late: explained by the legs
    h.until("10:01:00")
    assert h.eng.slot_state is SlotState.OPEN and not h.j.of("reconcile_halt")
    h.t = ts("15:49:59")
    h.step(1)                                           # time exit fills; the position lingers 2 s at the broker
    h.until("15:50:30")
    assert h.j.of("reconcile_mismatch"), "the check must have seen the lag, or the test proves nothing"
    assert h.j.of("reconcile_cleared") and not h.j.of("reconcile_halt") and not h.j.of("kill_start")
    assert h.flat() and h.eng.slot_state is SlotState.FLAT


def test_mt_g26_a_foreign_open_order_halts(tmp_path):
    h = H(tmp_path)
    h.sim.add_foreign_order("SPY", "buy", 1, 600.0)
    h.until("10:00:45")
    assert h.j.of("reconcile_halt") and h.j.of("kill_done") and h.flat()


# ============================================================================================ MT-G27, G38 kill switch
def test_mt_g27_g38_kill_flattens_a_book_with_the_quote_feed_down_and_the_entry_cap_used(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.step(1)
    h.c.entry_submits = C.MAX_ENTRY_SUBMITS_DAY                     # entry caps used up
    h.eng.broker.entry_count = C.MAX_ENTRY_SUBMITS_DAY
    h.eng.broker.entry_times = [h.t] * C.MAX_ENTRY_SUBMITS_PER_MIN
    h.feed = False                                                  # no quotes, no trades, data going stale
    h.step(3)
    h.eng.request_kill("owner pressed kill")
    t0 = h.t
    while not h.j.of("kill_done") and h.t < t0 + pd.Timedelta(seconds=10):
        h.step(1)
    assert h.j.of("kill_done") and h.flat() and h.t - t0 <= pd.Timedelta(seconds=10)
    order = h.j.of("kill_order")[0]
    assert "NO_QUOTE" in order["tags"] and order["cid"].startswith("SCALP-BOT-")
    assert h.flag("HALT").exists() and h.j.of("trade_closed")[-1]["how"].startswith("kill")


def test_mt_g27_kill_file_flattens_and_only_a_person_clears_halt(tmp_path):
    h = H(tmp_path, mode=Mode.PAPER)                                  # the owner's `kill` is for the paper bot
    enter_noise(h)
    h.state.mkdir(parents=True, exist_ok=True)
    h.flag("KILL").write_text("owner test\n")
    h.step(1)
    h.step(1)
    assert h.flat() and h.j.of("kill_done") and not h.flag("KILL").exists() and h.flag("HALT").exists()
    h.until("10:30:00", 30)
    h.px["SPY"] = 652.0
    decs = h.step(1, {"SPY": mkbars("SPY", "10:00", "10:29", 651.0, 652.0)})
    entries = [x for x in decs if x.candidate.action == "enter"]
    assert entries and all(Reason.KILLED in x.reasons and Reason.HALTED_MANUAL in x.reasons for x in entries)


# ============================================================================================ MT-G25 runaway guard
def _entry_spec(sim, k, sym="SPY"):
    reg = REG.get("NOISE_MOM_SPY", "SPY")
    cand = Candidate(reg.setup_id, 1, sym, "enter", 1, ts("10:00") + pd.Timedelta(minutes=k))
    spec, reasons, _ = O.entry_bracket(cand, reg, sim.quotes[sym], 100_000.0, D, 0)
    assert spec is not None, reasons
    return spec


def test_mt_g25_seventh_entry_in_60_s_is_blocked_while_8_exit_resends_are_not():
    clk = {"t": ts("10:00:01")}
    sim = SimBroker(lambda: clk["t"])
    sim.set_quote("SPY", 650.0, 650.01)
    j = MemoryJournal(Mode.DRY, lambda: clk["t"])
    g = GuardedBroker(sim, lambda: clk["t"], j, e0=100_000.0)
    for k in range(6):
        g.submit(_entry_spec(sim, k))                   # each fills at once, so no parent stays open
        clk["t"] += pd.Timedelta(seconds=5)
    with pytest.raises(RunawayOrders):
        g.submit(_entry_spec(sim, 6))
    assert len(sim.submits) == 6 and j.of("runaway_blocked")
    for leg in [x for x in sim.open_orders()]:
        sim.cancel(leg.id)
    far = Quote("SPY", 700.0, 700.01, 100, 100, clk["t"], clk["t"], Feed.SIM)   # sells rest above the market
    for a in range(8):
        spec = O.exit_limit("SPY", 1, far, None, C.EXIT_COLLARS[min(a, 2)], Kind.EXIT, setup_id="NOISE_MOM_SPY",
                            version=1, session_date=D, bar_start=ts("10:00"), leg="X", attempt=a)
        v = g.submit(spec)
        g.cancel(v.id)
        clk["t"] += pd.Timedelta(seconds=2)
    assert len(sim.submits) == 14


def test_mt_g25_exit_budget_delays_but_never_raises_runaway():
    clk = {"t": ts("10:00:01")}
    sim = SimBroker(lambda: clk["t"], positions=[])
    sim.inject_position("SPY", 1, 650.0)
    sim.set_quote("SPY", 650.0, 650.01)
    g = GuardedBroker(sim, lambda: clk["t"], MemoryJournal(Mode.DRY, lambda: clk["t"]), e0=100_000.0)
    far = Quote("SPY", 700.0, 700.01, 100, 100, clk["t"], clk["t"], Feed.SIM)
    for a in range(C.MAX_EXIT_ORDERS_PER_MIN):
        v = g.submit(O.exit_limit("SPY", 1, far, None, 0.0005, Kind.EXIT, setup_id=None, version=0, session_date=D,
                                  bar_start=ts("10:00"), leg="K", attempt=a))
        g.cancel(v.id)
    with pytest.raises(ExitDelayed):
        g.submit(O.exit_limit("SPY", 1, far, None, 0.0005, Kind.EXIT, setup_id=None, version=0, session_date=D,
                              bar_start=ts("10:00"), leg="K", attempt=99))
    clk["t"] += pd.Timedelta(seconds=61)
    g.submit(O.exit_limit("SPY", 1, far, None, 0.0005, Kind.EXIT, setup_id=None, version=0, session_date=D,
                          bar_start=ts("10:00"), leg="K", attempt=100))


def test_mt_g25_guard_blocks_a_second_open_parent_and_oversize():
    clk = {"t": ts("10:00:01")}
    sim = SimBroker(lambda: clk["t"], fill_delay_s=1e9)
    sim.set_quote("SPY", 650.0, 650.01)
    g = GuardedBroker(sim, lambda: clk["t"], MemoryJournal(Mode.DRY, lambda: clk["t"]), e0=100_000.0)
    g.submit(_entry_spec(sim, 0))
    with pytest.raises(RunawayOrders, match="already open"):
        g.submit(_entry_spec(sim, 1))
    with pytest.raises(RunawayOrders, match="qty"):
        g.submit(replace(_entry_spec(sim, 2), qty=5))
    assert len(sim.submits) == 1


def test_mt_g25_runaway_entry_at_the_guard_fires_the_kill_switch(tmp_path):
    """A counter bug upstream (risk sees 0 recent entries, the guard saw 6): the guard refuses and the engine
    kills. The Knight Capital case."""
    h = H(tmp_path)
    h.eng.broker.entry_times = [h.t] * C.MAX_ENTRY_SUBMITS_PER_MIN
    h.px["SPY"] = 651.0
    decs = h.step(1, {"SPY": mkbars("SPY", "09:30", "09:59", 650.0, 651.0)})
    assert [x.reasons for x in decs if x.candidate.setup_id == "NOISE_MOM_SPY"] == [(Reason.KILLED,)]
    assert h.sim.submits == [] and h.j.of("runaway_orders") and h.j.of("kill_done")
    assert h.flag("HALT").exists()


# ============================================================================================ MT-G25 broker rejects
def test_mt_g25_broker_403_on_entry_is_not_retried_and_blocks_the_symbol(tmp_path):
    h = H(tmp_path, sim_kw={"reject_next": 403})
    h.px["SPY"] = 651.0
    decs = h.step(1, {"SPY": mkbars("SPY", "09:30", "09:59", 650.0, 651.0)})
    noise = [x for x in decs if x.candidate.setup_id == "NOISE_MOM_SPY"][0]
    assert noise.reasons == (Reason.SYMBOL_BLOCKED_BROKER_REJECT,)
    assert h.sim.submits == [] and h.c.blocked_symbols == {"SPY"} and h.c.entry_submits == 1
    h.until("10:30:00", 30)
    h.px["SPY"] = 651.5
    decs = h.step(1, {"SPY": mkbars("SPY", "10:00", "10:29", 651.0, 651.5)})
    noise = [x for x in decs if x.candidate.setup_id == "NOISE_MOM_SPY"][0]
    assert Reason.SYMBOL_BLOCKED_BROKER_REJECT in noise.reasons and h.sim.submits == []
    assert len(h.j.of("broker_reject")) == 1


def test_mt_g38_exit_still_goes_out_after_a_403_and_is_retried_at_the_next_collar(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.c.blocked_symbols.add("SPY")                      # as after a broker rejection on an entry
    h.sim.reject_next = 403
    h.t = ts("15:49:59")
    h.step(1)
    h.step(1)
    assert h.j.of("exit_rejected") and h.flat()
    orders = h.j.of("exit_order")                        # the retry went out at the next collar
    assert orders and orders[0]["collar"] == C.EXIT_COLLARS[1] and h.j.of("trade_closed")[-1]["how"] == "TIME_EXIT"


# ============================================================================================ slot machine
def test_partial_fill_is_protected_at_once(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "EXPLORATORY_MAX_QTY", 2)    # v1 is 1 share; paper fills 10% partially (MT-G4)
    h = H(tmp_path, sim_kw={"partial_fill_qty": 1})
    d = enter_noise(h)
    assert d.order.qty == 2
    assert h.eng.slot_state in (SlotState.PARTIALLY_FILLED, SlotState.EXIT_PENDING)
    assert any(x["reason"] == "PARTIAL_FILL_PROTECT" for x in h.j.of("cancel_request"))
    t0 = h.t
    while not h.flat() and h.t < t0 + pd.Timedelta(seconds=C.STOP_CONFIRM_S + 1):
        h.step(1)
    assert h.flat() and h.eng.trade is None
    assert h.j.of("exit_start")[0]["reason"] == "PARTIAL_FILL_PROTECT"
    assert h.c.round_trips == 1 and h.j.of("trade_closed")[0]["qty"] == 1


def test_a_slow_cancel_does_not_free_the_slot_early(tmp_path):
    h = H(tmp_path, sim_kw={"fill_delay_s": 1e9, "cancel_delay_s": 4})
    enter_noise(h)
    assert h.eng.slot_state is SlotState.ENTRY_PENDING
    h.until("10:00:03")
    assert any(x["reason"] == "ENTRY_TIMEOUT" for x in h.j.of("cancel_request"))
    for _ in range(3):                                  # 10:00:04 .. 10:00:06: cancel requested, not confirmed
        h.step(1)
        assert h.eng.slot_state is SlotState.ENTRY_PENDING and h.eng.status()["open_orders"]
    h.step(1)                                           # 10:00:07: the broker confirms the cancel
    assert h.eng.slot_state is SlotState.FLAT and h.eng.trade is None and h.flat()
    assert h.c.round_trips == 0 and h.c.entry_submits == 1


def test_a_fill_that_arrives_while_the_cancel_is_pending_is_a_position(tmp_path):
    h = H(tmp_path, sim_kw={"fill_delay_s": 3, "cancel_delay_s": 4})
    enter_noise(h)
    h.until("10:00:03")
    assert h.eng.trade.cancel_requested_at is not None
    h.until("10:00:06")
    assert h.eng.slot_state is SlotState.OPEN and h.sim.positions()[0].qty == 1 and h.c.round_trips == 1


class BadStopLeg(SimBroker):
    """The broker shows a stop leg whose price is not the one we registered (a widened stop)."""

    def _fill(self, o, qty, price, now):
        super()._fill(o, qty, price, now)
        if o.role == "parent" and o.status == "filled":
            for x in o.legs:
                if self.orders[x].role == "sl":
                    self.orders[x].stop_price -= 1.0


def test_mt_g16_stop_unconfirmed_goes_flat(tmp_path):
    h = H(tmp_path, sim=BadStopLeg(lambda: ts("10:00:00")))
    enter_noise(h)
    t0 = h.t
    while not h.flat() and h.t < t0 + pd.Timedelta(seconds=C.STOP_CONFIRM_S + 2):
        h.step(1)
    assert h.flat() and h.j.of("stop_unconfirmed") and h.j.of("exit_start")[0]["reason"] == "STOP_UNCONFIRMED"
    assert h.t - t0 <= pd.Timedelta(seconds=C.STOP_CONFIRM_S + 1)


def test_mt_g21_stop_watchdog_sells_after_10_s_below_the_stop_limit_and_pauses_while_halted(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.step(1)
    stop_limit = h.eng.trade.stop_limit
    h.px["SPY"] = stop_limit - 1.0                      # gapped through: the stop-limit cannot fill
    h.halted["SPY"] = True
    h.until("10:00:30")
    assert h.eng.trade is not None and not h.j.of("exit_start")      # halted: the count is paused
    h.halted["SPY"] = False
    t0 = h.t
    while h.eng.trade is not None and h.t < t0 + pd.Timedelta(seconds=15):
        h.step(1)
    assert h.flat() and h.j.of("exit_start")[0]["reason"] == "STOP_ESCALATION"
    assert pd.Timedelta(seconds=9) <= h.t - t0 <= pd.Timedelta(seconds=C.STOP_WATCHDOG_S + 2)
    assert h.c.stopout_until.get(("NOISE_MOM_SPY", "SPY")) is not None


# ============================================================================================ MT-G20 clock
def test_mt_g20_time_exit_at_1550_then_nothing_open(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.t = ts("15:49:58")
    h.step(1)
    assert h.eng.trade is not None
    h.step(1)
    assert h.flat() and h.j.of("trade_closed")[-1]["how"] == "TIME_EXIT"


def test_mt_g16_unfilled_exit_escalates_through_the_collars_then_kills(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.sim.fill_delay_s = 1e9                              # from now on nothing fills
    h.t = ts("15:49:59")
    h.until("15:50:20")
    collars = [x["collar"] for x in h.j.of("exit_order")]
    assert collars == list(C.EXIT_COLLARS)
    assert h.j.of("kill_start") and "exit not filled" in h.j.of("kill_start")[0]["reason"]


def test_mt_g20_anything_still_open_at_1555_fires_the_kill_switch(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.sim.fill_delay_s = 1e9                              # the exit sell rests unfilled ...
    h.halted["SPY"] = True                                # ... and a halt pauses its escalation (MT-G21)
    h.t = ts("15:49:59")
    h.until("15:55:05", 5)
    reasons = [x["reason"] for x in h.j.of("kill_start")]
    assert reasons == ["OPEN_AT_KILL_TIME"]


def test_mt_g16_exit_whose_leg_cancels_never_confirm_alerts_and_escalates_to_the_kill(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.sim.cancel_delay_s = 10_000                         # the legs' cancels never come back
    h.t = ts("15:49:59")
    h.until("15:50:30", 1)
    starts = h.j.of("kill_start")
    assert len(starts) == 1 and "cancels not confirmed" in starts[0]["reason"]
    k = as_ny(starts[0]["ts"])
    assert k - ts("15:50:00") <= pd.Timedelta(seconds=C.CANCEL_GIVE_UP_X * C.CANCEL_CONFIRM_S + 1)
    assert any("not confirmed" in a["message"] for a in h.j.of("alert"))
    assert len(h.j.of("cancel_request")) < 30               # re-requested every 5 s, not every tick
    h.until("15:51:00", 1)                                  # the kill cannot sell over the stuck legs: says so once
    stuck = [a for a in h.j.of("alert") if "by hand" in a["message"] and "cannot sell" in a["message"]]
    assert len(stuck) == 1 and not h.j.of("kill_order")


# ============================================================================================ live = backtest
def _spy_day():
    """SPY: up in the first half hour (LAST30 long), above the noise band at 10:00 (NOISE long), back inside
    the band by 11:00 (NOISE exit). Moves stay far from the 0.5% overlay stop and the 1% target."""
    parts = [("09:30", "09:59", 650.0, 651.5), ("10:00", "10:29", 651.5, 651.5), ("10:30", "10:59", 651.5, 650.3),
             ("11:00", "15:59", 650.3, 650.4)]
    return [b for p in parts for b in mkbars("SPY", *p, wick=0.02)]


def _qqq_day():
    parts = [("09:30", "09:34", 560.0, 561.0), ("09:35", "15:59", 561.0, 561.5)]
    return [b for p in parts for b in mkbars("QQQ", *p, wick=0.02)]


@pytest.mark.parametrize("setup_id,sym", [("ORB5_QQQ", "QQQ"), ("LAST30_MOM_SPY", "SPY"),
                                          ("NOISE_MOM_SPY", "SPY")])
def test_live_decision_equals_the_backtest_intent_on_the_same_bars(tmp_path, setup_id, sym):
    reg = REG.get(setup_id, sym)
    bars = _qqq_day() if sym == "QQQ" else _spy_day()
    h = H(tmp_path, start="09:30:00", registry=C.Registry((reg,), REG.account_last4))
    decs = []
    for b in bars:
        h.t = as_ny(b.start) + pd.Timedelta(seconds=60)
        h.px[sym] = b.close
        decs += h.step(1, {sym: [b]})
    df = pd.DataFrame({"open": [b.open for b in bars], "high": [b.high for b in bars],
                       "low": [b.low for b in bars], "close": [b.close for b in bars],
                       "volume": [b.volume for b in bars]}, index=pd.DatetimeIndex([b.start for b in bars]))
    day = sg.Day.from_frame(df, ts("09:30"), ts("16:00"))
    want = [(day.ts(i.m), i.action, i.side, i.stop, i.target_r) for i in sg.SETUPS[setup_id].fn(day, ctxs()[sym])]
    got = [(x.candidate.bar_start, x.candidate.action, x.candidate.side, x.candidate.stop, x.candidate.target_r)
           for x in decs]
    assert want and got == want
    assert all(x.accepted for x in decs), [x.reasons for x in decs]
    if setup_id == "NOISE_MOM_SPY":
        assert [w[1] for w in want] == ["enter", "exit"]
        assert h.j.of("trade_closed")[0]["how"] == "SETUP_EXIT"
    # the backtest trades the same intents: same entry minutes
    trades = bt.execute(day, sg.SETUPS[setup_id].fn(day, ctxs()[sym]))
    assert [day.ts(t.entry_m - 1) for t in trades] == [w[0] for w in want if w[1] == "enter"]


# ============================================================================================ misc
def test_status_is_a_plain_heartbeat(tmp_path):
    import json
    from lab.scalp.live.journal import plain
    h = H(tmp_path)
    enter_noise(h)
    st = h.eng.status()
    json.dumps(plain(st))
    assert set(st) >= {"slot", "position", "open_orders", "counters", "killing", "flags"}


def test_mt_g38_setup_exit_is_never_blocked_by_entry_gates(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.until("10:59:00", 30)
    # every entry gate fails at once: clock unverified, data silent (no quotes or trades), symbol blocked, the day's
    # entry submissions used up, a loss-streak pause running
    h.clock_offset = None
    h.feed = False
    h.c.blocked_symbols.add("SPY")
    h.c.entry_submits = C.MAX_ENTRY_SUBMITS_DAY
    h.c.loss_pause_until = ts("12:00")
    h.t = ts("11:00:00")
    decs = h.step(1, {"SPY": mkbars("SPY", "10:00", "10:59", 651.0, 650.3)})
    ex = [x for x in decs if x.candidate.action == "exit"]
    assert ex and ex[0].accepted and ex[0].reasons == (Reason.SETUP_EXIT,)
    assert h.eng.clock_offset_ms is None and h.eng._fresh_quote("SPY") is None      # the gates really were down
    assert h.flat() and h.j.of("exit_order")[0]["tags"].find("NO_QUOTE") >= 0


def test_replay_in_bar_mode_fills_the_stop_leg_on_a_later_bar(tmp_path):
    h = H(tmp_path, sim_kw={"fill_mode": "bar"}, mode=Mode.REPLAY)
    enter_noise(h)
    stop = h.eng.trade.stop
    h.t = ts("10:02:00")
    drop = Bar("SPY", ts("10:01"), 651.0, 651.1, stop - 0.10, stop + 0.05, 5_000.0, Feed.SIP)
    h.step(1, {"SPY": [drop]})
    assert h.flat() and h.j.of("trade_closed")[0]["how"] == "stop"
    assert h.c.stopout_until[("NOISE_MOM_SPY", "SPY")] == ts("10:02:01") + pd.Timedelta(minutes=15)
    assert [f["price"] for f in h.j.of("fill") if f["side"] == "sell"] == [stop]


def test_a_replay_of_a_date_without_fee_rows_keeps_running_and_says_so(tmp_path):
    d = date(2025, 10, 1)
    h = H(tmp_path, d=d)
    enter_noise(h)
    h.t = ts("15:49:59", d)
    h.step(1)
    h.step(1)
    assert h.flat() and h.j.of("trade_closed")
    assert any("no fee row" in a["message"] for a in h.j.of("alert"))
