"""Live paper minute trader: fixes from the third verification round (kill fills booked, MT-G4 take-profit
re-mark and unbiased switch-off series, durable state on the scalp-state branch, feed labels, startup paths).

All offline: SimBroker look-alikes, fake clients, fake clocks, memory journals, tmp_path state. The git tests use
a LOCAL bare repository created under /tmp only (never the project's remote)."""
from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from lab.scalp.live import config as C
from lab.scalp.live import gates as G
from lab.scalp.live import journal as J
from lab.scalp.live import orders as O
from lab.scalp.live import report as REP
from lab.scalp.live import restore as RS
from lab.scalp.live import runner as RUN
from lab.scalp.live import state as S
from lab.scalp.live.broker import SimBroker
from lab.scalp.live.model import AccountView, Bar, Feed, Lane, Mode, OrderView, Reason, as_ny

from test_scalp_live_engine import REG, H, enter_noise, ts


# =================================================================================== V3-1: kill fills are booked
class AckThenFillBroker(SimBroker):
    """Real Alpaca paper (confirmed on the SCALP account): a submit comes back pending_new with filled_qty 0 and the
    marketable limit fills about 0.6 s later, i.e. by the NEXT read of anything. Everything else is SimBroker."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._acking = False
        self._late: list[str] = []

    def submit(self, spec):
        self._acking = True
        try:
            v = super().submit(spec)
        finally:
            self._acking = False
        return dataclasses.replace(v, status="pending_new") if v.filled_qty == 0 else v

    def _match_quote(self, o, now):
        if self._acking and o.role in ("simple", "parent"):
            if o.id not in self._late:
                self._late.append(o.id)                  # acknowledged, not filled yet
            return
        if o.id in self._late:
            return
        super()._match_quote(o, now)

    def _settle(self):
        late, self._late = self._late, []
        for oid in late:
            super()._match_quote(self.orders[oid], self.now())

    def positions(self):
        self._settle()
        return super().positions()

    def open_orders(self):
        self._settle()
        return super().open_orders()

    def get_order(self, order_id):
        self._settle()
        return super().get_order(order_id)


def _open_long(tmp_path):
    h = H(tmp_path, sim=AckThenFillBroker(lambda: ts("10:00:00")))
    enter_noise(h)
    for _ in range(3):
        h.step(1)
    assert h.eng.trade is not None and h.eng.trade.stop_confirmed and h.sim.positions()[0].qty == 1
    return h


def test_v3_1_a_kill_order_that_fills_after_its_acknowledgement_is_booked_and_the_trade_closed(tmp_path):
    h = _open_long(tmp_path)
    h.eng.request_kill("test: kill with a broker that fills after the acknowledgement")
    for _ in range(10):
        h.step(1)
        if h.eng.killed:
            break
    assert h.eng.killed and h.flat()
    kill_fills = [x for x in h.j.of("fill") if x["role"] == "kill"]
    assert len(kill_fills) == 1 and kill_fills[0]["side"] == "sell"          # the K fill is in the ledger
    closed = h.j.of("trade_closed")
    assert len(closed) == 1 and closed[0]["how"].startswith("kill: test")
    assert h.c.realized_honest == pytest.approx(closed[0]["gate_honest_pnl"]) and h.c.realized_honest != 0.0
    assert h.c.test_honest == pytest.approx(h.c.realized_honest)
    assert h.j.kinds().index("trade_closed") < h.j.kinds().index("kill_done")
    assert not h.j.of("trade_unbooked")


def test_v3_1_exit_and_protect_paths_book_a_fill_that_arrives_after_the_acknowledgement(tmp_path):
    h = _open_long(tmp_path)
    h.eng.request_flatten("SIGTERM")                                # the normal exit path (SHUTDOWN)
    for _ in range(5):
        h.step(1)
    assert h.eng.trade is None and h.flat()
    closed = h.j.of("trade_closed")
    assert len(closed) == 1 and closed[0]["how"] == "SHUTDOWN"
    assert [x["role"] for x in h.j.of("fill")] == ["entry", "exit"]
    assert h.c.realized_honest == pytest.approx(closed[0]["gate_honest_pnl"])


# =================================================================================== R1: the feed label is true
def test_r1_replay_on_sip_bars_labels_its_lines_sip_and_feed_mismatch_shows_only_when_feeds_differ(tmp_path):
    from lab.scalp.live import market as M
    from lab.scalp.live.clock import SessionTimes
    from lab.scalp.signals import Ctx
    from test_scalp_live_runtime import QUIET, _session_bars
    from test_scalp_live_runtime import ts as rts
    n = 390
    bars = {"QQQ": _session_bars("QQQ", [560.0 + 0.1 * min(k, 5) for k in range(n)]),
            "SPY": _session_bars("SPY", [650.0 + 0.05 * min(k, 30) for k in range(n)])}
    st = SessionTimes.from_calendar(QUIET, rts("09:30", QUIET), rts("16:00", QUIET))
    clock = M.SimClock(st.open)
    market = M.ReplayMarket(QUIET, bars, M.bar_quote_fn(bars), clock, open_ts=st.open, close_ts=st.close)
    j = J.MemoryJournal(Mode.REPLAY, clock)
    RUN.replay(QUIET, e0=100_000.0, market=market, journal=j, ctx_by_symbol={"QQQ": Ctx(prev_close=559.0),
               "SPY": Ctx(prev_close=649.0)}, session=st, state_dir=tmp_path, out=lambda s: None)
    labelled = [x for x in j.lines if x.get("setup_id") and x["kind"] != "fill"]     # a fill's feed is its quote's
    assert labelled and {x["feed"] for x in labelled} == {"SIP"}, {x["feed"] for x in labelled}
    assert j.of("trade_closed")
    text = REP.build_report(j.lines, C.load_registry())
    assert "FEED_MISMATCH" not in text                                  # SIP replay vs SIP backtest: same feed
    live = [{**x, "feed": "IEX"} if x.get("setup_id") else x for x in j.lines]
    assert "FEED_MISMATCH: live IEX vs backtest SIP (MT-G35)" in REP.build_report(live, C.load_registry())


def test_r1_live_runs_label_iex_and_the_self_test_labels_sim(tmp_path):
    reg, _ = RUN.registry_for_run(C.load_registry(), J.MemoryJournal(Mode.DRY), feed="IEX")
    assert {r.labels()["feed"] for r in reg.setups} == {"IEX"} and all(r.feed_mismatch for r in reg.setups)
    reg, _ = RUN.registry_for_run(C.load_registry(), J.MemoryJournal(Mode.REPLAY), feed="SIP")
    assert {r.labels()["feed"] for r in reg.setups} == {"SIP"} and not any(r.feed_mismatch for r in reg.setups)
    assert {r.feed_live for r in C.load_registry().setups} == {"IEX"}          # the committed file is unchanged
    from lab.scalp.live.engine import Engine
    seen = []

    class Spy(Engine):
        def __init__(self, broker, journal, registry, *a, **k):
            seen.append(registry)
            super().__init__(broker, journal, registry, *a, **k)

    ok, detail = RUN.self_test(ts("09:10"), C.load_registry(), tmp_path, engine_cls=Spy)
    assert ok, detail
    assert [r.labels()["feed"] for r in seen[0].setups] == ["SIM"]             # synthetic quotes: SIM


# =================================================================================== V3-3: scalp-state branch
@pytest.fixture
def git_repos():
    """A LOCAL bare repository in /tmp standing in for the remote, and a clone with one commit on main. Git runs
    with an empty global config (no signing, no credentials) and a fixed identity. Removed afterwards."""
    base = Path(tempfile.mkdtemp(dir="/tmp", prefix="scalp-state-test-"))
    (base / "gitconfig").write_text("")
    env = {"GIT_CONFIG_GLOBAL": str(base / "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_TERMINAL_PROMPT": "0"}
    import os
    full = {**os.environ, **env}

    def git(cwd, *args):
        return subprocess.run(["git", *args], cwd=str(cwd), env=full, check=True, capture_output=True,
                              text=True).stdout.strip()

    bare, work = base / "remote.git", base / "work"
    git(base, "init", "-q", "--bare", "-b", "main", str(bare))
    git(base, "init", "-q", "-b", "main", str(work))
    (work / "README").write_text("owner's checkout\n")
    git(work, "add", "README")
    git(work, "commit", "-q", "-m", "init")
    git(work, "remote", "add", "origin", str(bare))
    git(work, "push", "-q", "origin", "main")
    try:
        yield SimpleNamespace(base=base, bare=bare, work=work, env=env, git=git)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _state(root, day="2026-10-01"):
    st = root / "state"
    (st / "journal").mkdir(parents=True)
    (st / "journal" / f"{day}-paper.jsonl").write_text(json.dumps({"ts": f"{day}T10:00:00-04:00", "kind": "fill"})
                                                       + "\n")
    (st / "changes.log").write_text(json.dumps({"ts": f"{day}T08:00:00-04:00", "action": "test-start"}) + "\n")
    (st / S.TEST_START_PIN).write_text("2026-09-29\n")
    (st / S.ACCOUNT_PIN).write_text("PA0TESTGWRL\n")
    (st / f"session-{day}.json").write_text('{"e0": 100000.0}')
    for junk in ("HALT", "KILL", "heartbeat-paper.json", "broker.lock", "alerts.log", ".env"):
        (st / junk).write_text("x")
    (st / "recordings").mkdir()
    (st / "recordings" / f"{day}-paper.jsonl").write_text("{}\n")
    (st / "replay" / "journal").mkdir(parents=True)
    (st / "replay" / "journal" / "x.jsonl").write_text("{}\n")
    return st


def test_v3_3_state_save_pushes_only_the_whitelist_to_scalp_state_and_restore_brings_it_back(git_repos):
    from lab.scalp.live import statesync as SS
    g = git_repos
    st = _state(g.base)
    head = g.git(g.work, "rev-parse", "HEAD")
    res = SS.save(st, g.work, env=g.env, now=ts("16:30"), out=lambda s: None)
    assert res["pushed"]
    files = g.git(g.bare, "ls-tree", "-r", "--name-only", "scalp-state").splitlines()
    assert files == ["scalp/account.pin", "scalp/changes.log", "scalp/journal/2026-10-01-paper.jsonl",
                     "scalp/session-2026-10-01.json", "scalp/test_start.pin"]
    assert g.git(g.bare, "rev-parse", "main") == head                     # nothing else at the remote moved
    # the owner's checkout is untouched: same branch and commit, clean, no local scalp-state branch, no worktree
    assert g.git(g.work, "rev-parse", "--abbrev-ref", "HEAD") == "main" and g.git(g.work, "rev-parse", "HEAD") == head
    assert g.git(g.work, "status", "--porcelain") == "" and "scalp-state" not in g.git(g.work, "branch", "--list")
    assert len(g.git(g.work, "worktree", "list").splitlines()) == 1
    # a fresh container: restore brings exactly those files back
    fresh = g.base / "fresh"
    out = SS.restore(fresh, g.work, env=g.env, now=ts("09:00", date(2026, 10, 2)), out=lambda s: None)
    assert sorted(out["restored"]) == ["account.pin", "changes.log", "journal/2026-10-01-paper.jsonl",
                                       "session-2026-10-01.json", "test_start.pin"]
    for rel in out["restored"]:
        if rel != "changes.log":
            assert (fresh / rel).read_bytes() == (st / rel).read_bytes()
    assert [x["action"] for x in S.read_changes(fresh)] == ["test-start", "state-restore"]   # logged (MT-G41)
    assert not (fresh / "HALT").exists() and not (fresh / ".env").exists()


def test_v3_3_state_save_never_forces_and_merges_two_containers_records(git_repos):
    from lab.scalp.live import statesync as SS
    g = git_repos
    a = _state(g.base / "a")
    SS.save(a, g.work, env=g.env, now=ts("16:30"), out=lambda s: None)
    first = g.git(g.bare, "rev-parse", "scalp-state")
    # a second container wrote the same day's journal with another line and pinned a LATER test start
    b = _state(g.base / "b")
    p = b / "journal" / "2026-10-01-paper.jsonl"
    p.write_text(p.read_text() + json.dumps({"ts": "2026-10-01T11:00:00-04:00", "kind": "fill", "n": 2}) + "\n")
    (b / S.TEST_START_PIN).write_text("2026-10-01\n")
    SS.save(b, g.work, env=g.env, now=ts("16:40"), out=lambda s: None)
    tip = g.git(g.bare, "rev-parse", "scalp-state")
    assert g.git(g.bare, "rev-parse", f"{tip}^") == first                # a fast-forward on top: never forced
    lines = g.git(g.bare, "show", "scalp-state:scalp/journal/2026-10-01-paper.jsonl").splitlines()
    assert len(lines) == 2                                                # the union, no line lost
    assert g.git(g.bare, "show", "scalp-state:scalp/test_start.pin") == "2026-09-29"   # the earlier start wins
    # the push itself: never --force, never a '+' refspec, only the scalp-state branch
    import inspect
    src = inspect.getsource(SS)
    pushes = [x for x in src.splitlines() if '"push"' in x]
    assert pushes and all("--force" not in x and '"+' not in x and "BRANCH" in x for x in pushes)
    with pytest.raises(ValueError):
        SS.save(a, g.work, branch="trading-state", env=g.env, out=lambda s: None)
    with pytest.raises(ValueError):
        SS.restore(a, g.work, branch="trading-state", env=g.env, out=lambda s: None)


def test_v3_3_state_restore_refuses_while_a_bot_runs_and_never_saves_a_key(git_repos):
    from lab.scalp.live import statesync as SS
    g = git_repos
    st = _state(g.base)
    S.write_heartbeat(st, ts("10:00"), "paper", {})
    with pytest.raises(RuntimeError):
        SS.restore(st, g.work, env=g.env, now=ts("10:00:10"), out=lambda s: None)
    (st / "journal" / "2026-10-01-paper.jsonl").write_text("secret-value-123456\n")
    with pytest.raises(ValueError):
        SS.save(st, g.work, env={**g.env, "ALPACA_SCALP_SECRET": "secret-value-123456"}, out=lambda s: None)
    assert g.git(g.bare, "branch", "--list", "scalp-state") == ""          # nothing was pushed


# =================================================================================== V3-1a, V3-2, V3-2a: MT-G4
NOISE_L = {"setup_id": "NOISE_MOM_SPY", "version": 1, "lane": "EXPLORATORY", "feed": "IEX", "symbol": "SPY"}


def _close_line(day, i, r, tp=False, oid=None, cid=None, limit=660.0):
    t = f"{day}T10:{i:02d}:00-04:00"
    return {"ts": t, "mode": "dry", "kind": "trade_closed", "how": "target" if tp else "stop", "qty": 1,
            "paper_pnl": r + 0.03, "honest_pnl": r, "risk_usd": 1.0, "r": r, "gate_r": min(r, 0.0) if tp else r,
            "gate_honest_pnl": min(r, 0.0) if tp else r, "pending_verify": tp, "tp_order_id": oid, "parent_cid": cid,
            "tp_limit": limit if tp else None, "tp_filled_at": t if tp else None, **NOISE_L}


def _write(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        for x in lines:
            f.write(json.dumps(x) + "\n")


def test_v3_1a_a_sim_order_id_from_another_process_never_verifies_a_take_profit(tmp_path):
    d1, d2 = date(2026, 10, 1), date(2026, 10, 2)
    # process 1: a take-profit on SimBroker order sim-00002, never verified
    _write(J.journal_path(tmp_path, d1, Mode.DRY), [_close_line(d1, 1, 2.0, tp=True, oid="sim-00002",
                                                                cid="SCALP-NOISES-261001-0959-E0-aaaaaa")])
    # process 2 (next day, a fresh SimBroker): ITS sim-00002 take-profit was verified by a live bar
    _write(J.journal_path(tmp_path, d2, Mode.DRY), [
        _close_line(d2, 1, 1.5, tp=True, oid="sim-00002", cid="SCALP-NOISES-261002-0959-E0-bbbbbb"),
        {"ts": f"{d2}T10:03:00-04:00", "kind": "tp_verified", "order_id": "sim-00002",
         "parent_cid": "SCALP-NOISES-261002-0959-E0-bbbbbb", "r": 1.5, **NOISE_L}])
    h = RUN.lane_history(REG, None, tmp_path, Mode.DRY)[("NOISE_MOM_SPY", "SPY")]
    assert h["r"] == [1.5] and h["pending_verify"] == 1                  # day 1's win is still unverified
    # an older line without parent_cid is matched by order id inside its own file only
    p = J.journal_path(tmp_path, d2, Mode.DRY)
    p.write_text("\n".join(json.dumps({k: v for k, v in json.loads(x).items() if k != "parent_cid"})
                           for x in p.read_text().splitlines()) + "\n")
    h = RUN.lane_history(REG, None, tmp_path, Mode.DRY)[("NOISE_MOM_SPY", "SPY")]
    assert h["r"] == [1.5] and h["pending_verify"] == 1


def _pending_book(day=date(2026, 10, 1)):
    """15 losses at -1R and 15 take-profit wins at +2R still PENDING_VERIFY (a +0.5R setup on paper)."""
    out = []
    for i in range(30):
        tp = i % 2 == 0
        out.append(_close_line(day, i, 2.0 if tp else -1.0, tp=tp, oid=f"sim-{i:05d}" if tp else None,
                               cid=f"SCALP-NOISES-{day:%y%m%d}-0959-E{i}-cccccc" if tp else None))
    return out


def test_v3_2a_report_builds_the_r_series_like_the_engine_and_prints_what_it_left_out():
    lines = _pending_book()
    text = REP.build_report(lines, C.load_registry())
    noise = "\n".join(x for x in text.splitlines() if "NOISE_MOM_SPY" in x)
    assert "MT-G4 take-profits: 0 verified, 0 missed fill(s) at 0R, 15 PENDING_VERIFY left out of the R series" \
        in noise
    # the engine's view: 15 resolved losses plus 15 pending at their gate value (0R) -> the stricter answer
    assert "MT-G12 switch-off check: -> SHADOW" in noise
    h = {"r": [-1.0] * 15, "pend": {str(i): 0.0 for i in range(15)}}
    assert G.lane_check_pending(h["r"], list(h["pend"].values()), [], None, None)[0] is Lane.SHADOW
    # once the SIP re-mark verified them, both say keep
    ver = [{"kind": "tp_verified", "ts": "2026-10-01T18:00:00-04:00", "parent_cid": x["parent_cid"],
            "order_id": x["tp_order_id"], **NOISE_L} for x in lines if x["pending_verify"]]
    text = REP.build_report(lines + ver, C.load_registry())
    assert "MT-G12 switch-off check: keep (30 R values" in text and "15 verified, 0 missed" in text


def test_v3_2_pending_take_profits_are_counted_at_their_gate_value_only_when_stricter():
    # 25 resolved losses of -0.05R with a tiny spread: the resolved series alone trips; adding zeros would not
    rs = [-0.05 + 0.001 * (i % 3) for i in range(30)]
    assert G.lane_check_pending(rs, [], [], None, None)[0] is Lane.SHADOW
    assert G.lane_check_pending(rs, [0.0] * 10, [], None, None)[0] is Lane.SHADOW       # kept: the stricter view
    # 20 resolved losses (too few to act) + 10 pending take-profits: counting them at 0R makes 30 -> stricter
    lane, why = G.lane_check_pending([-1.0] * 20, [0.0] * 10, [], None, None)
    assert lane is Lane.SHADOW and "unverified take-profit" in why[0]
    assert G.lane_check_pending([-1.0] * 20, [], [], None, None)[0] is None
    # a pending win is never counted at its paper R
    assert G.lane_check_pending([0.5] * 30, [0.0] * 5, [], None, None)[0] is None


def _sip(prices):
    calls = []

    def fn(sym, start, end):
        calls.append((sym, start, end))
        return prices
    fn.calls = calls
    return fn


def test_v3_2_evening_sip_remark_resolves_pending_take_profits_and_the_engine_reads_it(tmp_path):
    from lab.scalp.live.engine import Engine
    from test_scalp_live_engine import KNOWN, ctxs, session
    d = date(2026, 10, 1)
    _write(J.journal_path(tmp_path, d, Mode.DRY), _pending_book(d))
    h = RUN.lane_history(REG, None, tmp_path, Mode.DRY)[("NOISE_MOM_SPY", "SPY")]
    assert h["pending_verify"] == 15 and len(h["pend"]) == 15
    # at startup the pending wins are counted at 0R where stricter: the setup starts in shadow (documented)
    hh = H(tmp_path / "e1")
    eng = Engine(hh.sim, hh.j, REG, hh.c, session(), KNOWN, ctxs(), Mode.DRY, hh.clock,
                 history={("NOISE_MOM_SPY", "SPY"): h})
    assert eng.registry.get("NOISE_MOM_SPY", "SPY").lane is Lane.SHADOW
    # too recent for SIP: nothing is decided
    early = as_ny("2026-10-01T10:17:00-04:00")
    out = REP.resolve_take_profits(tmp_path, "dry", _sip([700.0]), early)
    assert sum("too recent" in x for x in out) == 15 and not REP.remark_path(tmp_path, d, "dry").exists()
    # no SIP data: still pending
    REP.resolve_take_profits(tmp_path, "dry", _sip(None), as_ny("2026-10-01T18:00:00-04:00"))
    assert not REP.remark_path(tmp_path, d, "dry").exists()
    # the evening re-mark: a SIP trade strictly through 660.00 verifies; exactly at the limit is a missed fill
    fn = _sip([659.5, 660.01])
    out = REP.resolve_take_profits(tmp_path, "dry", fn, as_ny("2026-10-01T18:00:00-04:00"))
    assert sum("VERIFIED" in x for x in out) == 15
    s, a, b = fn.calls[0]
    assert s == "SPY" and b - a == pd.Timedelta(minutes=2) and a == as_ny("2026-10-01T10:00:00-04:00")
    h = RUN.lane_history(REG, None, tmp_path, Mode.DRY)[("NOISE_MOM_SPY", "SPY")]
    assert h["pending_verify"] == 0 and sorted(h["r"]) == [-1.0] * 15 + [2.0] * 15
    hh = H(tmp_path / "e2")
    eng = Engine(hh.sim, hh.j, REG, hh.c, session(), KNOWN, ctxs(), Mode.DRY, hh.clock,
                 history={("NOISE_MOM_SPY", "SPY"): h})
    assert eng.registry.get("NOISE_MOM_SPY", "SPY").lane is Lane.EXPLORATORY
    # nothing left to re-mark; a second run writes nothing new
    n = len(J.read_journal(REP.remark_path(tmp_path, d, "dry")))
    REP.resolve_take_profits(tmp_path, "dry", fn, as_ny("2026-10-01T19:00:00-04:00"))
    assert len(J.read_journal(REP.remark_path(tmp_path, d, "dry"))) == n


def test_v3_2_a_take_profit_the_sip_never_traded_through_is_a_missed_fill_at_0r(tmp_path):
    d = date(2026, 10, 1)
    _write(J.journal_path(tmp_path, d, Mode.DRY), _pending_book(d))
    out = REP.resolve_take_profits(tmp_path, "dry", _sip([659.0, 660.0]), as_ny("2026-10-01T18:00:00-04:00"))
    assert sum("MISSED FILL" in x for x in out) == 15
    h = RUN.lane_history(REG, None, tmp_path, Mode.DRY)[("NOISE_MOM_SPY", "SPY")]
    assert h["pending_verify"] == 0 and h["missed"] == 15 and sorted(h["r"]) == [-1.0] * 15 + [0.0] * 15
    text = REP.report(state_dir=tmp_path, mode="dry", out=lambda s: None)
    assert "0 verified, 15 missed fill(s) at 0R, 0 PENDING_VERIFY" in text


def test_v3_2_report_remark_resolves_paper_take_profits_from_the_broker_history_in_a_fresh_container(tmp_path):
    from test_scalp_live_review import HistBroker, _trade
    d = date(2026, 10, 1)
    orders = _trade(d, 0, 650.0, 656.5, tp_filled=True) + _trade(d, 1, 650.0, 649.0)
    broker = HistBroker(orders)
    _, st = RS.rebuild(broker, date(2026, 10, 2), 100_000.0, 100_000.0, None, d, REG, ts("09:00", date(2026, 10, 2)))
    tp = next(t for t in st.trades if t.pending_verify)
    assert tp.parent_cid == orders[0].client_order_id and tp.tp_limit is not None and tp.gate_r == 0.0
    h = RUN.lane_history(REG, st, tmp_path, Mode.PAPER)[("NOISE_MOM_SPY", "SPY")]
    assert h["pending_verify"] == 1                                       # no journal here: pending
    fn = _sip([tp.tp_limit + 0.02])
    text = REP.report(state_dir=tmp_path, mode="paper", broker=broker, trades_fn=fn,
                      now=as_ny("2026-10-02T09:00:00-04:00"), out=lambda s: None)
    assert "VERIFIED" in text
    h = RUN.lane_history(REG, st, tmp_path, Mode.PAPER)[("NOISE_MOM_SPY", "SPY")]
    assert h["pending_verify"] == 0 and tp.r in h["r"]


# =================================================================================== V3-3a: sticky deploy block
def test_v3_3a_a_flagged_start_writes_the_block_and_a_restart_with_the_reference_code_stays_blocked(tmp_path):
    from lab.scalp.live.clock import at
    d = date(2026, 10, 6)
    S.write_session(tmp_path, d, {"e0": 100_000.0, "package_hash": "A", "first_start": at(d, "08:40").isoformat(),
                                  "starts": [{"ts": at(d, "08:40").isoformat(), "mode": "paper",
                                              "package_hash": "A"}]})
    r1, info = RUN.deploy_check(tmp_path, at(d, "10:00"), "B", Mode.PAPER)       # a mid-session deploy of B
    assert r1 == [Reason.DEPLOY_IN_MARKET_HOURS] and info["reference"] == "A"
    assert S.read_deploy_block(tmp_path, d)["package_hash"] == "B"
    # the flagged start never reached the session file (it crashed right after the check)
    assert [x["package_hash"] for x in S.read_session(tmp_path, d)["starts"]] == ["A"]
    # a restart with the reference code A: only the sticky block remembers the deploy
    r2, _ = RUN.deploy_check(tmp_path, at(d, "10:05"), "A", Mode.PAPER)
    assert r2 == [Reason.DEPLOY_IN_MARKET_HOURS]


# =================================================================================== V3-3: fail closed in PAPER
def _bracket_trade(day, n, setup, sym, buy, sell, hhmm="10:00"):
    """A closed SCALP bracket round trip as the broker shows it: the entry parent with its (cancelled) legs, and
    our exit sell. Risk per share 1.02 (limit - stop-limit)."""
    t0 = as_ny(f"{day} {hhmm}:01") + pd.Timedelta(minutes=n)
    cid = O.client_id(setup, 1, day, t0.floor("min") - pd.Timedelta(minutes=1), "E", n)
    legs = (OrderView(f"tp-{day}-{setup}-{n}", f"leg-tp-{day}-{n}", sym, "sell", 1, 0, None, "canceled", "limit",
                      buy + 10, submitted_at=t0),
            OrderView(f"sl-{day}-{setup}-{n}", f"leg-sl-{day}-{n}", sym, "sell", 1, 0, None, "canceled", "stop_limit",
                      buy - 1.0, buy - 0.5, submitted_at=t0))
    entry = OrderView(f"e-{day}-{setup}-{n}", cid, sym, "buy", 1, 1, buy, "filled", "limit", buy + 0.02,
                      order_class="bracket", legs=legs, submitted_at=t0, filled_at=t0)
    xid = O.client_id(setup, 1, day, t0.floor("min") - pd.Timedelta(minutes=1), "X", n)
    ex = OrderView(f"x-{day}-{setup}-{n}", xid, sym, "sell", 1, 1, sell, "filled", "limit", sell,
                   submitted_at=t0 + pd.Timedelta(minutes=2), filled_at=t0 + pd.Timedelta(minutes=2))
    return [entry, ex]


def test_v3_3_paper_fills_no_local_journal_covers_make_that_setup_shadow_only(tmp_path):
    reg = C.load_registry()
    d = date(2026, 10, 1)
    hist = _bracket_trade(d, 0, "ORB5_QQQ", "QQQ", 560.0, 561.0, "09:35") + \
        _bracket_trade(d, 1, "LAST30_MOM_SPY", "SPY", 650.0, 651.0, "15:30")
    gaps = RUN.journal_gaps(hist, tmp_path, reg)
    assert gaps == {"ORB5_QQQ/QQQ": [d], "LAST30_MOM_SPY/SPY": [d]}             # a fresh container
    # the day's paper journal has the accepted decision (written before the submit) for ORB5 only
    _write(J.journal_path(tmp_path, d, Mode.PAPER), [{"ts": f"{d}T09:35:01-04:00", "kind": "decision",
                                                     "order": {"client_order_id": hist[0].client_order_id}}])
    gaps = RUN.journal_gaps(hist, tmp_path, reg)
    assert gaps == {"LAST30_MOM_SPY/SPY": [d]}
    j = J.MemoryJournal(Mode.PAPER)
    out = RUN.shadow_for_gaps(reg, gaps, j)
    assert out.get("LAST30_MOM_SPY", "SPY").lane is Lane.SHADOW and out.get("ORB5_QQQ", "QQQ").lane is Lane.EXPLORATORY
    assert j.of("state_not_restored")[0]["sessions"] == [d.isoformat()]
    # fills from before the version was registered do not count
    old = _bracket_trade(date(2026, 9, 25), 0, "ORB5_QQQ", "QQQ", 560.0, 561.0, "09:35")
    assert RUN.journal_gaps(old, tmp_path / "x", reg) == {}


# =================================================================================== V3-4a: the PAPER startup path
class FakeAlpaca:
    """Stands in for AlpacaBroker in run('paper'): the SCALP paper account with an order history (read-only). Any
    submit fails the test: HALT must keep every entry out."""
    history: list = []
    submits: list = []

    def __init__(self, mode=Mode.PAPER, **kw):
        self.mode = Mode(mode)

    def account(self):
        return AccountView("PA0TESTGWRL", "ACTIVE", 100_050.0, 100_000.0, 100_000.0, 200_000.0, 100_000.0, False,
                           False, "https://paper-api.alpaca.markets")

    def orders_since(self, since):
        return [o for o in self.history if o.submitted_at is None or o.submitted_at >= as_ny(since)]

    def positions(self):
        return []

    def open_orders(self):
        return []

    def get_order(self, oid):
        return next(o for o in self.history if o.id == oid)

    def get_by_client_id(self, cid):
        return next((o for o in self.history if o.client_order_id == cid), None)

    def submit(self, spec):
        FakeAlpaca.submits.append(spec)
        raise AssertionError("no order may be sent in this test")

    def cancel(self, oid):
        raise AssertionError("nothing to cancel")


def test_v3_4a_run_paper_startup_reads_the_broker_history_rebuilds_halt_and_restores(tmp_path, monkeypatch):
    from lab.scalp.live import broker as B
    from lab.scalp.live import market as M
    from lab.scalp.signals import Ctx
    from test_scalp_live_runtime import QUIET, Clock, FakeIEX, FakeTime
    from test_scalp_live_runtime import ts as rts
    days = [date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 5)]
    hist = [o for d in days for n in range(6) for o in _bracket_trade(d, n, "LAST30_MOM_SPY", "SPY", 650.0, 649.0,
                                                                       "10:00")]
    hist += _bracket_trade(date(2026, 10, 2), 0, "ORB5_QQQ", "QQQ", 560.0, 561.0, "09:35")
    k_at = as_ny("2026-10-05 15:55:00")
    hist.append(OrderView("k1", O.client_id(None, 0, date(2026, 10, 5), k_at, "K", 0), "SPY", "sell", 1, 0, None,
                          "canceled", "limit", 640.0, submitted_at=k_at))
    FakeAlpaca.history, FakeAlpaca.submits = hist, []
    # the LAST30 sessions are covered by local paper journals (their decisions); ORB5's session is not
    for d in days:
        _write(J.journal_path(tmp_path, d, Mode.PAPER), [{"ts": f"{d}T10:00:01-04:00", "kind": "decision",
                                                          "order": {"client_order_id": o.client_order_id}}
                                                         for o in hist if o.symbol == "SPY"])
    clock = Clock(rts("15:58:30", QUIET))

    class Trading:
        def get_clock(self):
            return SimpleNamespace(timestamp=clock().tz_convert("UTC").to_pydatetime())

    monkeypatch.setattr(RUN, "scalp_clients", lambda env=None: (FakeIEX(clock), Trading()))
    monkeypatch.setattr(B, "AlpacaBroker", FakeAlpaca)
    monkeypatch.setattr(M, "build_context", lambda sym, d, *a, **k: (
        Ctx(prev_close=649.0), M.CalendarRow(d, rts("09:30", d), rts("16:00", d)), []))
    monkeypatch.setattr(RUN, "now_ny", clock)
    monkeypatch.setattr(RUN, "time", FakeTime(clock))
    monkeypatch.setattr(RUN, "start_watchdog", lambda mode, sd: SimpleNamespace(terminate=lambda: None))
    msgs = []
    rc = RUN.run("paper", confirm_paper=True, state_dir=tmp_path, env={}, out=msgs.append)
    assert rc == 0, msgs
    lines = J.read_journal(J.journal_path(tmp_path, QUIET, Mode.PAPER))
    kinds = [x["kind"] for x in lines]
    # the broker's K order after the last reset-halt rebuilt HALT BEFORE the HALTED_MANUAL check
    assert "halt_rebuilt" in kinds and S.halted(tmp_path)
    start = next(x for x in lines if x["kind"] == "startup")
    assert "HALTED_MANUAL" in start["flags"]
    # the whole-test start came from the broker's first SCALP session and reached restore
    assert start["test_start"] == "2026-09-29" and S.read_test_start(tmp_path) == date(2026, 9, 29)
    assert start["test_sessions"] == 5 and start["test_honest"] < -30.0
    # the broker's closed trades reached the engine's switch-offs (MT-G12: 30 losers)
    dem = [x for x in lines if x["kind"] == "lane_demoted"]
    assert [(x["setup_id"], x["to_lane"]) for x in dem] == [("LAST30_MOM_SPY", "SHADOW")]
    assert any("MT-G12" in w for w in dem[0]["why"])
    # ORB5's paper fill is in no local journal: shadow-only, and the owner is told to restore the state
    assert [x["setup_id"] for x in lines if x["kind"] == "state_not_restored"] == ["ORB5_QQQ"]
    assert start["lanes"]["ORB5_QQQ/QQQ"] == "SHADOW" and any("state-restore" in m for m in msgs)
    assert not FakeAlpaca.submits
