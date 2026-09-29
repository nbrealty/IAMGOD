"""Live paper minute trader: two small gaps from the v4 handoff audit. A second runner on the same state folder is
refused (single execution owner), and the engine's alerts reach the alerts file, not only the journal.

All offline: tmp_path state, no network, no keys."""
from __future__ import annotations

import select
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from lab.scalp.live import runner as RUN
from lab.scalp.live import state as S
from lab.scalp.live.model import Mode

TRADING = Path(__file__).resolve().parents[1]


def test_second_runner_on_the_same_state_folder_is_refused_before_anything_starts(tmp_path):
    held = RUN.acquire_runner_lock(tmp_path, Mode.DRY)
    assert held is not None
    try:
        msgs: list[str] = []
        rc = RUN.run("dry", no_watchdog=True, state_dir=tmp_path, env={}, out=msgs.append)
        assert rc == 2
        assert "already running" in msgs[0] and "runner-dry.lock" in msgs[0]
        assert sorted(p.name for p in tmp_path.iterdir()) == ["runner-dry.lock"]      # no journal, no clients, nothing
    finally:
        held.close()


def test_the_lock_is_per_mode_and_a_paper_run_is_refused_too(tmp_path):
    dry = RUN.acquire_runner_lock(tmp_path, Mode.DRY)
    paper = RUN.acquire_runner_lock(tmp_path, Mode.PAPER)              # a dry runner does not block a paper runner
    try:
        assert dry is not None and paper is not None
        assert RUN.acquire_runner_lock(tmp_path, Mode.PAPER) is None
        msgs: list[str] = []
        assert RUN.run("paper", confirm_paper=True, state_dir=tmp_path, env={}, out=msgs.append) == 2
        assert "paper runner is already running" in msgs[0]
    finally:
        for fh in (dry, paper):
            if fh is not None:
                fh.close()


def test_the_lock_is_held_by_another_process_and_freed_when_it_dies(tmp_path):
    code = ("import sys, time\nsys.path.insert(0, %r)\nfrom lab.scalp.live import runner as R\n"
            "from lab.scalp.live.model import Mode\nh = R.acquire_runner_lock(%r, Mode.PAPER)\n"
            "print('held' if h else 'none', flush=True)\ntime.sleep(60)\n") % (str(TRADING), str(tmp_path))
    child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True, cwd=str(TRADING))
    try:
        ready, _, _ = select.select([child.stdout], [], [], 30)          # never hang the suite on a broken child
        assert ready and child.stdout.readline().strip() == "held"
        assert RUN.acquire_runner_lock(tmp_path, Mode.PAPER) is None
    finally:
        child.kill()
        child.wait()
    again = RUN.acquire_runner_lock(tmp_path, Mode.PAPER)                  # the OS freed it with the process
    assert again is not None
    again.close()


def test_run_frees_the_lock_even_when_the_run_itself_raises(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")

    handles = []
    real_acquire = RUN.acquire_runner_lock

    def recording_acquire(*a, **k):
        fh = real_acquire(*a, **k)
        handles.append(fh)
        return fh

    monkeypatch.setattr(RUN, "_run", boom)
    monkeypatch.setattr(RUN, "acquire_runner_lock", recording_acquire)
    with pytest.raises(RuntimeError):
        RUN.run("dry", no_watchdog=True, state_dir=tmp_path, env={}, out=lambda s: None)
    assert len(handles) == 1 and handles[0].closed              # released by run() itself, not by garbage collection
    again = RUN.acquire_runner_lock(tmp_path, Mode.DRY)
    assert again is not None
    again.close()


def test_engine_alerts_are_written_to_the_alerts_file(tmp_path):
    seen: dict = {}

    class FakeEngine:
        def __init__(self, broker, journal, registry, counters, session, events, ctx, mode, clock, *, state_dir=None,
                     adopted=None, flags=(), alert=None, **k):
            seen["alert"], self.flags = alert, set(flags)

    now = pd.Timestamp("2026-09-29 10:00", tz="America/New_York")
    RUN.make_engine(None, None, None, None, None, None, {}, Mode.DRY, lambda: now, state_dir=tmp_path,
                    engine_cls=FakeEngine)
    seen["alert"]("KILL SWITCH: test", {"reason": "test"})
    assert "KILL SWITCH: test" in S.path(tmp_path, S.ALERTS).read_text()


def test_an_engine_without_an_alert_argument_still_builds(tmp_path):
    class Old:
        def __init__(self, broker, journal, registry, counters, session, events, ctx, mode, clock, *, state_dir=None,
                     adopted=None, flags=(), **k):
            self.flags = set(flags)

    now = pd.Timestamp("2026-09-29 10:00", tz="America/New_York")
    eng = RUN.make_engine(None, None, None, None, None, None, {}, Mode.DRY, lambda: now, state_dir=tmp_path,
                          engine_cls=Old)
    assert isinstance(eng, Old)


# =================================================================================== V4-08: hand-computed round trip
def test_v4_08_fixed_price_round_trip_loses_exactly_the_hand_computed_amount(tmp_path):
    """Bid 650.00 / ask 650.01, never moves. The expected numbers are worked out here by hand (Decimal, published
    constants) without costs.py, orders.py or sizing.py, then compared with the engine's journal and the simulated
    broker's own cash."""
    from decimal import ROUND_CEILING
    from decimal import Decimal as Dc

    import test_scalp_live_engine as T
    from lab.scalp.live import config as C

    reg = C.Registry((T.LAST30,), T.REG.account_last4)
    h = T.H(tmp_path, start="15:29:59", registry=reg, px={"SPY": 650.0, "QQQ": 560.0})
    cash0 = h.sim.cash
    h.step(1, {"SPY": T.mkbars("SPY", "09:30", "15:29", 650.0, 650.0, wick=0.0)})
    h.until("15:50:30", 1)
    buys = [x for x in h.j.lines if x["kind"] == "fill" and x["side"] == "buy"]
    sells = [x for x in h.j.lines if x["kind"] == "fill" and x["side"] == "sell"]
    closed = [x for x in h.j.lines if x["kind"] == "trade_closed"]
    assert len(buys) == len(sells) == len(closed) == 1
    assert buys[0]["qty"] == sells[0]["qty"] == 1               # the hand-worked fees below hold for exactly one share

    ask, bid = Dc("650.01"), Dc("650.00")                       # the buy fills at the ask, the exit sell at the bid
    paper = bid - ask
    slip = Dc("0.01") * 2                                       # $0.01 a share a side (the MT-G4 convention)

    def up_cent(x):
        return x.quantize(Dc("0.01"), rounding=ROUND_CEILING)

    sec = up_cent(bid * Dc("20.60") / Dc(1_000_000))            # SEC section 31, per $1M sold, rounded up to the cent
    taf = up_cent(Dc("0.000195"))                               # FINRA TAF per share sold, rounded up to the cent
    cat = Dc("0.000001") + Dc("0.000002")                       # CAT per share, each side
    fees = sec + taf + 2 * cat
    honest = paper - slip - fees
    assert float(buys[0]["price"]) == float(ask) and float(sells[0]["price"]) == float(bid)
    assert abs(closed[0]["paper_pnl"] - float(paper)) < 1e-9
    assert abs(closed[0]["fees"] - float(fees)) < 1e-9
    assert abs(closed[0]["honest_pnl"] - float(honest)) < 1e-9
    assert abs((h.sim.cash - cash0) - float(paper)) < 1e-9      # the simulated broker's own ledger
    assert float(honest) < 0                                    # a flat market plus a spread and fees is a loss


# =================================================================================== V4-12: two entries, one slot
def _two_setups_same_bar(tmp_path, order, fill_delay=None):
    import test_scalp_live_engine as T
    from lab.scalp.live import config as C

    reg = C.Registry(tuple(T.REG.get(s, "SPY") for s in order), T.REG.account_last4)
    sim_kw = {"fill_delay_s": fill_delay} if fill_delay else None
    h = T.H(tmp_path, start="15:29:59", registry=reg, px={"SPY": 650.0, "QQQ": 560.0}, sim_kw=sim_kw)
    h.px["SPY"] = 652.0
    decs = h.step(1, {"SPY": T.mkbars("SPY", "09:30", "15:29", 650.0, 652.0, wick=0.0)})
    return h, [d for d in decs if d.candidate.action == "enter"]


def test_v4_12_two_setups_that_fire_on_the_same_bar_send_exactly_one_order(tmp_path):
    for i, order in enumerate((["LAST30_MOM_SPY", "NOISE_MOM_SPY"], ["NOISE_MOM_SPY", "LAST30_MOM_SPY"])):
        h, ent = _two_setups_same_bar(tmp_path / f"a{i}", order)
        assert len(ent) == 2 and sum(d.accepted for d in ent) == 1
        assert len(h.sim.submits) == 1                          # whichever registers first wins; the other is refused


def test_v4_12_the_second_proposal_is_refused_while_the_first_parent_is_still_unfilled(tmp_path):
    h, ent = _two_setups_same_bar(tmp_path, ["LAST30_MOM_SPY", "NOISE_MOM_SPY"], fill_delay=1e9)
    assert len(h.sim.submits) == 1
    assert sum(d.accepted for d in ent) == 1 and not ent[1].accepted
    from lab.scalp.live.model import Reason
    why = set(ent[1].reasons)
    assert why & {Reason.POSITION_OPEN, Reason.OPEN_PARENT, Reason.NO_ADD}      # refused by the slot rules ...
    assert Reason.KILLED not in why and not h.j.of("runaway_orders")           # ... not by a kill-switch backstop
