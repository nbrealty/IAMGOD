"""Live paper minute trader: fixes from the fourth verification round (the V3-3 journal-gap rule reads only the
engine's own journal lines and has a logged owner exit; tests for the V3-2 startup re-mark, the V3-1 kill settle and
the in-process MT-G4 pending view).

All offline: SimBroker look-alikes, fake clients, fake clocks, memory journals, tmp_path state. No network, no keys."""
from __future__ import annotations

import json
from argparse import Namespace
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from lab.scalp.live import __main__ as cli
from lab.scalp.live import config as C
from lab.scalp.live import journal as J
from lab.scalp.live import report as REP
from lab.scalp.live import runner as RUN
from lab.scalp.live import state as S
from lab.scalp.live.broker import SimBroker
from lab.scalp.live.model import Bar, Feed, Lane, Mode, as_ny

from test_scalp_live_engine import H, enter_noise, ts
from test_scalp_live_review import _trade
from test_scalp_live_round3 import FakeAlpaca, _write

GAP_DAY = date(2026, 10, 1)


def _tp_trade(setup="ORB5_QQQ", sym="QQQ", day=GAP_DAY):
    """A SCALP bracket whose take-profit leg filled, as the broker's history shows it (no exit order of ours)."""
    px = 560.0 if sym == "QQQ" else 650.0
    return _trade(day, 0, px, px + 6.5, setup=setup, sym=sym, tp_filled=True)


def _through(*_a, **_k):
    """A historical SIP trade source whose prints go through any take-profit limit."""
    return lambda sym, start, end: [99_999.0]


# =================================================================================== V4-1-1 / V4-2-1: gap coverage
def test_v4_1_1_a_remark_file_or_line_naming_the_entry_does_not_cover_a_journal_gap(tmp_path):
    reg = C.load_registry()
    hist = _tp_trade()
    cid = hist[0].client_order_id
    assert RUN.journal_gaps(hist, tmp_path, reg) == {"ORB5_QQQ/QQQ": [GAP_DAY]}           # a fresh container
    # the startup re-mark resolves the take-profit from the BROKER's history: the remark file names the entry's cid
    out = REP.resolve_take_profits(tmp_path, "paper", _through(), as_ny("2026-10-02 09:00:00"), hist)
    assert any("VERIFIED" in x for x in out)
    remark = REP.remark_path(tmp_path, GAP_DAY, "paper")
    assert cid in remark.read_text()
    assert RUN.journal_gaps(hist, tmp_path, reg) == {"ORB5_QQQ/QQQ": [GAP_DAY]}           # still a gap
    # a same-day restart: the run journal holds a `tp_remark` line quoting the cid, and the kill / watchdog files
    # (written from the broker too) may name it: none of them is the engine's record of the entry
    _write(J.journal_path(tmp_path, GAP_DAY, Mode.PAPER),
           [{"ts": "2026-10-01T10:20:00-04:00", "kind": "tp_remark", "line": f"take-profit ({cid}): too recent"},
            {"ts": "2026-10-01T10:20:00-04:00", "kind": "tp_verified", "parent_cid": cid},
            {"ts": "2026-10-01T10:20:00-04:00", "kind": "state_not_restored", "note": cid}])
    _write(tmp_path / "journal" / f"{GAP_DAY}-paper-kill.jsonl",
           [{"ts": "2026-10-01T10:20:00-04:00", "kind": "decision", "order": {"client_order_id": cid}}])
    assert RUN.journal_gaps(hist, tmp_path, reg) == {"ORB5_QQQ/QQQ": [GAP_DAY]}
    # the engine's own lines do cover it: the accepted decision (written before the submit), the submit, the fill
    for line in ({"kind": "decision", "order": {"client_order_id": cid}}, {"kind": "submit", "cid": cid},
                 {"kind": "fill", "cid": cid}):
        j = J.journal_path(tmp_path, GAP_DAY, Mode.PAPER)
        keep = j.read_text()
        _write(j, [{"ts": "2026-10-01T10:00:01-04:00", **line}])
        assert RUN.journal_gaps(hist, tmp_path, reg) == {}, line
        j.write_text(keep)
    # an unreadable line (a crash mid-write) is skipped, never a reason to lift the gap
    with open(J.journal_path(tmp_path, GAP_DAY, Mode.PAPER), "a") as f:
        f.write('{"kind": "decision", "order": {"client_order_id": "' + cid + '"\n')
    assert RUN.journal_gaps(hist, tmp_path, reg) == {"ORB5_QQQ/QQQ": [GAP_DAY]}


# =================================================================================== run('paper') helper
def _run_paper(tmp_path, monkeypatch, hist):
    from lab.scalp.live import broker as B
    from lab.scalp.live import market as M
    from lab.scalp.signals import Ctx
    from test_scalp_live_runtime import QUIET, Clock, FakeIEX, FakeTime
    from test_scalp_live_runtime import ts as rts
    FakeAlpaca.history, FakeAlpaca.submits = list(hist), []
    clock = Clock(rts("15:58:30", QUIET))

    class Trading:
        def get_clock(self):
            return SimpleNamespace(timestamp=clock().tz_convert("UTC").to_pydatetime())

    monkeypatch.setattr(RUN, "scalp_clients", lambda env=None: (FakeIEX(clock), Trading()))
    monkeypatch.setattr(B, "AlpacaBroker", FakeAlpaca)
    monkeypatch.setattr(M, "build_context", lambda sym, d, *a, **k: (
        Ctx(prev_close=649.0), M.CalendarRow(d, rts("09:30", d), rts("16:00", d)), []))
    monkeypatch.setattr(M, "SipTradeSource", _through)
    monkeypatch.setattr(RUN, "now_ny", clock)
    monkeypatch.setattr(RUN, "time", FakeTime(clock))
    monkeypatch.setattr(RUN, "start_watchdog", lambda mode, sd: SimpleNamespace(terminate=lambda: None))
    msgs: list[str] = []
    before = len(J.read_journal(J.journal_path(tmp_path, QUIET, Mode.PAPER)))
    rc = RUN.run("paper", confirm_paper=True, state_dir=tmp_path, env={}, out=msgs.append)
    assert rc == 0, msgs
    assert not FakeAlpaca.submits
    return J.read_journal(J.journal_path(tmp_path, QUIET, Mode.PAPER))[before:], msgs


# =================================================================================== V4-1-2: the startup re-mark
def test_v4_1_2_every_paper_start_re_marks_the_brokers_take_profits_before_the_switch_offs(tmp_path, monkeypatch):
    hist = _tp_trade()
    cid = hist[0].client_order_id
    # the session is covered locally (its decision line), but no local journal holds the take-profit close: only the
    # broker's history has it
    _write(J.journal_path(tmp_path, GAP_DAY, Mode.PAPER), [{"ts": "2026-10-01T10:00:01-04:00", "kind": "decision",
                                                           "order": {"client_order_id": cid}}])
    lines, _ = _run_paper(tmp_path, monkeypatch, hist)
    kinds = [x["kind"] for x in lines]
    # the re-mark ran at startup, from the broker's history, and wrote its verdict for the next start
    remark = J.read_journal(REP.remark_path(tmp_path, GAP_DAY, "paper"))
    assert [(x["kind"], x["parent_cid"], x["source"]) for x in remark] == [("tp_verified", cid, "SIP_REMARK")]
    assert any(x["kind"] == "tp_remark" and "VERIFIED" in x["line"] for x in lines)
    # ... BEFORE the switch-offs read the series: nothing is left PENDING_VERIFY for that setup
    assert kinds.index("tp_remark") < kinds.index("startup")
    assert not [x for x in lines if x["kind"] == "lane_history_pending_verify" and x["setup_id"] == "ORB5_QQQ"]
    assert not [x for x in lines if x["kind"] == "state_not_restored"]


# =================================================================================== V4-2-1 / V4-2-2 end to end
def test_v4_2_fresh_container_stays_shadow_after_the_remark_until_restore_or_the_owners_logged_acceptance(
        tmp_path, monkeypatch):
    hist = _tp_trade()
    lanes = []
    for _ in range(2):                                    # two starts in a fresh container: the re-mark in between
        lines, msgs = _run_paper(tmp_path, monkeypatch, hist)
        start = next(x for x in lines if x["kind"] == "startup")
        lanes.append(start["lanes"]["ORB5_QQQ/QQQ"])
        assert [x["setup_id"] for x in lines if x["kind"] == "state_not_restored"] == ["ORB5_QQQ"]
        assert any("state-restore" in m and "accept-journal-gap" in m for m in msgs)
    assert REP.remark_path(tmp_path, GAP_DAY, "paper").exists()          # the re-mark ran and named the entry
    assert lanes == ["SHADOW", "SHADOW"]
    # the journal is lost for good: the owner's logged exit (MT-G41), then the setup trades again
    rc = cli.cmd_accept_journal_gap(Namespace(session=GAP_DAY, setup="ORB5_QQQ/QQQ", reason="container recycled "
                                              "before state-save; journal lost"), state_dir=tmp_path,
                                    clock=lambda: as_ny("2026-10-06 08:00:00"), out=lambda s: None)
    assert rc == 0
    ch = [x for x in S.read_changes(tmp_path) if x["action"] == "accept-journal-gap"]
    assert len(ch) == 1 and ch[0]["session"] == "2026-10-01" and "journal lost" in ch[0]["reason"]
    lines, _ = _run_paper(tmp_path, monkeypatch, hist)
    start = next(x for x in lines if x["kind"] == "startup")
    assert start["lanes"]["ORB5_QQQ/QQQ"] == "EXPLORATORY"
    acc = [x for x in lines if x["kind"] == "journal_gap_accepted"]
    assert acc and acc[0]["setup"] == "ORB5_QQQ/QQQ" and acc[0]["sessions"] == ["2026-10-01"]
    assert not [x for x in lines if x["kind"] == "state_not_restored"]


def test_v4_2_2_only_the_accepted_session_and_setup_are_released(tmp_path):
    reg = C.load_registry()
    d2 = date(2026, 10, 2)
    hist = _tp_trade() + _tp_trade(day=d2) + _tp_trade("LAST30_MOM_SPY", "SPY")
    now = as_ny("2026-10-06 08:00:00")
    both = {"ORB5_QQQ/QQQ": [GAP_DAY, d2], "LAST30_MOM_SPY/SPY": [GAP_DAY]}
    assert RUN.journal_gaps(hist, tmp_path, reg) == both
    # a reason is required (MT-G41) and the setup must be SETUP/SYMBOL
    assert cli.cmd_accept_journal_gap(Namespace(session=GAP_DAY, setup=None, reason="  "), state_dir=tmp_path,
                                      clock=lambda: now, out=lambda s: None) == 1
    with pytest.raises(ValueError):
        RUN.accept_journal_gap(tmp_path, GAP_DAY, "lost", now, setup="ORB5_QQQ")
    assert RUN.journal_gaps(hist, tmp_path, reg) == both                    # nothing was logged, nothing released
    RUN.accept_journal_gap(tmp_path, GAP_DAY, "lost", now, setup="ORB5_QQQ/QQQ")
    acc: dict = {}
    assert RUN.journal_gaps(hist, tmp_path, reg, acc) == {"ORB5_QQQ/QQQ": [d2], "LAST30_MOM_SPY/SPY": [GAP_DAY]}
    assert acc == {"ORB5_QQQ/QQQ": [GAP_DAY]}
    RUN.accept_journal_gap(tmp_path, d2, "lost", now)                        # the whole session, every setup
    assert RUN.journal_gaps(hist, tmp_path, reg) == {"LAST30_MOM_SPY/SPY": [GAP_DAY]}
    # the acceptance lives in changes.log only: a state folder without it still fails closed
    assert RUN.journal_gaps(hist, tmp_path / "other", reg) == both


# =================================================================================== V4-1-3: the kill settle
class RaceBroker(SimBroker):
    """SimBroker where chosen orders cancel slowly (pending_cancel until they fill) and something can happen at the
    broker at the moment the engine first reads the positions inside a tick (a fill racing the kill's cancels)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.slow_cancel: set[str] = set()
        self.on_positions = None

    def cancel(self, order_id):
        if order_id in self.slow_cancel:
            o = self.orders[order_id]
            self.cancels.append(order_id)
            if not o.done:
                o.status, o.updated_at = "pending_cancel", self.now()
            return
        super().cancel(order_id)

    def positions(self):
        if self.on_positions is not None:
            fn, self.on_positions = self.on_positions, None
            fn()
        return super().positions()

    def fill_now(self, oid):
        o = self.orders[oid]
        self._fill(o, o.left, o.limit_price if o.role == "tp" else self.quotes[o.symbol].bid, self.now())


def _open(tmp_path):
    h = H(tmp_path, sim=RaceBroker(lambda: ts("10:00:00")))
    enter_noise(h)
    h.step(1)
    assert h.eng.trade is not None and h.eng.trade.stop_confirmed and h.sim.positions()[0].qty == 1
    return h


def test_v4_1_3_a_take_profit_that_fills_while_the_kill_cancels_it_is_booked_on_that_tick(tmp_path):
    h = _open(tmp_path)
    tp = h.eng.trade.legs["tp"].id
    h.sim.slow_cancel.add(tp)
    h.eng.request_kill("test: take-profit races the kill")
    h.sim.on_positions = lambda: h.sim.fill_now(tp)
    h.step(1)
    assert h.flat() and h.eng.killed                    # settled on the tick that found the account flat
    fills = [x for x in h.j.of("fill") if x["side"] == "sell"]
    assert [(x["order_id"], x["role"]) for x in fills] == [(tp, "target")]
    closed = h.j.of("trade_closed")
    assert len(closed) == 1 and closed[0]["how"].startswith("kill: test") and closed[0]["pending_verify"]
    assert h.c.realized_honest == pytest.approx(closed[0]["gate_honest_pnl"])
    assert not h.j.of("trade_unbooked")


def test_v4_1_3_b_a_lingering_stray_sell_that_fills_on_the_kill_tick_is_booked(tmp_path):
    h = _open(tmp_path)
    stray = h.sim.add_foreign_order("SPY", "sell", 1, 700.0, cid="stray-exit-1")     # e.g. an exit from before a restart
    h.eng.lingering[stray] = h.t
    h.sim.slow_cancel.add(stray)
    h.eng.request_kill("test: stray sell races the kill")
    h.sim.on_positions = lambda: h.sim.fill_now(stray)
    h.step(1)
    assert h.flat() and h.eng.killed
    fills = [x for x in h.j.of("fill") if x["side"] == "sell"]
    assert [(x["order_id"], x["role"]) for x in fills] == [(stray, "exit")]
    closed = h.j.of("trade_closed")
    assert len(closed) == 1 and closed[0]["how"].startswith("kill: test") and closed[0]["sells"]
    assert h.c.realized_honest == pytest.approx(closed[0]["gate_honest_pnl"]) and h.c.realized_honest != 0.0
    assert not h.j.of("trade_unbooked")


def test_v4_1_3_c_shares_no_order_explains_wait_the_gap_then_trade_unbooked_and_an_alert(tmp_path):
    h = _open(tmp_path)
    h.eng.request_kill("test: shares sold by an order the bot cannot read")
    h.sim.on_positions = lambda: h.sim.pos.pop("SPY")
    gap = int(C.MISMATCH_MIN_GAP_S)
    for _ in range(gap):                                  # flat at the broker, but the books still hold the share
        h.step(1)
        assert not h.eng.killed and not h.j.of("trade_unbooked") and h.eng.trade is not None
    h.step(1)                                             # MISMATCH_MIN_GAP_S after the first flat read
    assert h.eng.killed and h.eng.trade is None
    unb = h.j.of("trade_unbooked")
    assert len(unb) == 1 and unb[0]["qty"] == 1 and unb[0]["symbol"] == "SPY"
    assert any("could not read" in x["message"] for x in h.j.of("alert"))
    assert h.j.kinds().index("trade_unbooked") < h.j.kinds().index("kill_done")
    assert not h.j.of("trade_closed")


# =================================================================================== V4-1-4: the in-process pend view
def test_v4_1_4_an_unverified_take_profit_closed_in_process_counts_at_its_gate_value_when_stricter(tmp_path):
    h = H(tmp_path)
    h.eng.hist[("NOISE_MOM_SPY", "SPY")] = {"r": [-0.6] * 29, "slip": [], "pend": {}}
    enter_noise(h)
    h.step(1)
    cid = h.eng.trade.parent_cid
    h.px["SPY"] = h.eng.trade.target + 0.05               # the resting take-profit fills: PENDING_VERIFY
    h.step(1)
    closed = h.j.of("trade_closed")[-1]
    assert closed["pending_verify"] and closed["r"] > 0
    hist = h.eng.hist[("NOISE_MOM_SPY", "SPY")]
    assert hist["r"] == [-0.6] * 29 and hist["pend"] == {cid: 0.0}
    # 29 resolved losses alone do not trip MT-G12; with the unverified win at its gate value (0R) they do
    assert h.eng.registry.get("NOISE_MOM_SPY", "SPY").lane is Lane.SHADOW
    dem = h.j.of("lane_demoted")
    assert len(dem) == 1 and any("unverified take-profit" in w for w in dem[0]["why"])


def test_v4_1_4_tp_verified_moves_the_trade_from_pend_to_its_real_r(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.step(1)
    cid, target = h.eng.trade.parent_cid, h.eng.trade.target
    h.px["SPY"] = target + 0.05
    h.step(1)
    closed = h.j.of("trade_closed")[-1]
    hist = h.eng.hist[("NOISE_MOM_SPY", "SPY")]
    assert hist["pend"] == {cid: 0.0} and hist["r"] == []
    fill_min = as_ny(h.t).floor("min")
    h.t = fill_min + pd.Timedelta(seconds=61)
    h.step(1, {"SPY": [Bar("SPY", fill_min, target - 0.2, target + 0.03, target - 0.3, target, 1e4, Feed.IEX)]})
    ver = h.j.of("tp_verified")
    assert len(ver) == 1 and ver[0]["parent_cid"] == cid
    assert hist["pend"] == {} and hist["r"] == [pytest.approx(closed["r"])]


def test_v4_2_1_a_mistyped_setup_is_refused_and_nothing_is_logged(tmp_path):
    """A typo in --setup would release nothing while changes.log said it did: refuse it (MT-G41)."""
    now = as_ny("2026-10-06 08:00:00")
    for bad in ("ORB5_QQQ/qqq", "ORB5/QQQ", "orb5_qqq/QQQ", "ORB5_QQQ/SPY"):
        rc = cli.cmd_accept_journal_gap(Namespace(session=GAP_DAY, setup=bad, reason="lost"), state_dir=tmp_path,
                                        clock=lambda: now, out=lambda s: None)
        assert rc == 1
    assert not [x for x in S.read_changes(tmp_path) if x["action"] == "accept-journal-gap"]
    RUN.accept_journal_gap(tmp_path, GAP_DAY, "lost", now, setup=" ORB5_QQQ/QQQ ")     # whitespace is trimmed
    ch = [x for x in S.read_changes(tmp_path) if x["action"] == "accept-journal-gap"]
    assert [x["setup"] for x in ch] == ["ORB5_QQQ/QQQ"]


def test_v4_2_1_b_a_session_not_yet_past_cannot_be_accepted(tmp_path):
    """An acceptance made before the loss would later release a lost journal silently: only past sessions."""
    now = as_ny("2026-10-06 08:00:00")
    for d in (date(2026, 10, 6), date(2026, 11, 6)):
        with pytest.raises(ValueError):
            RUN.accept_journal_gap(tmp_path, d, "lost", now, setup="ORB5_QQQ/QQQ")
    assert not [x for x in S.read_changes(tmp_path) if x["action"] == "accept-journal-gap"]
    RUN.accept_journal_gap(tmp_path, date(2026, 10, 5), "lost", now, setup="ORB5_QQQ/QQQ")
