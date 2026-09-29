"""V4-13 scratch experiment: entry submit SUCCEEDS at the broker but the acknowledgement is lost (BrokerUnavailable),
then the worker restarts. Uses SimBroker.unavailable_next='after' (order DID arrive). PAPER-mode engine + state dir so the
restart path is the real one (restore.rebuild + Engine(adopted=...))."""
import tempfile, pathlib
from common import *
from lab.scalp.live import restore as RS, orders as O
from lab.scalp.live.engine import Engine
from lab.scalp.live.journal import MemoryJournal

def base(fill_delay=None, mode=Mode.DRY):
    tmp = pathlib.Path(tempfile.mkdtemp())
    reg = C.Registry((T.LAST30,), T.REG.account_last4)
    sim_kw = {"fill_delay_s": fill_delay} if fill_delay else None
    h = T.H(tmp, start="15:29:59", registry=reg, sim_kw=sim_kw, mode=mode)
    h.px["SPY"] = 652.0
    return h

print("=== A. ack lost, order DID arrive and filled; engine finds it by client id in the same tick")
h = base()
h.sim.unavailable_next = "after"
decs = h.step(1, {"SPY": T.mkbars("SPY", "09:30", "15:29", 650.0, 652.0, wick=0.0)})
d = [x for x in decs if x.candidate.action == "enter"][0]
print("  decision accepted:", d.accepted, "reasons:", [r.value for r in d.reasons])
print("  kinds:", [k for k in h.j.kinds() if k in ("submit_uncertain","would_submit","submit","fill","stop_confirmed","entry_not_found")])
print("  broker submits:", len(h.sim.submits), " engine entry_submits:", h.c.entry_submits, " slot:", h.eng.slot_state.value)
h.step(1)
print("  after next tick slot:", h.eng.slot_state.value, "stop_confirmed:", h.eng.trade.stop_confirmed if h.eng.trade else None)
assert len(h.sim.submits) == 1

print("=== B. same, then the process RESTARTS (new Engine built from the broker's order history only)")
cnt, st = RS.rebuild(h.sim, T.D, 100_000.0, 100_000.0, None, None, C.Registry((T.LAST30,), T.REG.account_last4), h.t)
print("  restore: entry_submits", cnt.entry_submits, "round_trips", cnt.round_trips, "adopted trade:", st.trade is not None and (st.trade.symbol, st.trade.qty, st.trade.protected))
h2 = T.H(pathlib.Path(tempfile.mkdtemp()), start="15:30:10", registry=C.Registry((T.LAST30,), T.REG.account_last4), counters=cnt, adopted=st, sim=h.sim)
h2.px["SPY"] = 652.0
# the restarted process is delivered the SAME latest bar (the 15:29 bar) again: LAST30 would decide again
decs = h2.step(1, {"SPY": T.mkbars("SPY", "09:30", "15:29", 650.0, 652.0, wick=0.0)})
ent = [x for x in decs if x.candidate.action == "enter"]
print("  restarted engine re-decides the same bar:", [(x.accepted, [r.value for r in x.reasons]) for x in ent])
print("  broker submits after restart:", len(h2.sim.submits), " (must stay 1)")
assert len(h2.sim.submits) == 1

print("=== C. ack lost AND the lookup by client id also fails -> ORDER_STATE_UNCERTAIN, slot stays taken")
h = base(fill_delay=1e9)
orig_get = h.sim.get_by_client_id
calls = {"n": 0}
def flaky(cid):
    calls["n"] += 1
    if h.t < T.ts("15:30:20"):
        raise BrokerUnavailable("lookup also timed out")
    return orig_get(cid)
h.sim.get_by_client_id = flaky
h.sim.unavailable_next = "after"
decs = h.step(1, {"SPY": T.mkbars("SPY", "09:30", "15:29", 650.0, 652.0, wick=0.0)})
d = [x for x in decs if x.candidate.action == "enter"][0]
print("  decision accepted:", d.accepted, "reasons:", [r.value for r in d.reasons], "slot:", h.eng.slot_state.value, "uncertain_since set:", h.eng.trade.uncertain_since is not None)
for _ in range(5):
    h.step(1)
print("  5 s later slot:", h.eng.slot_state.value, "trade:", h.eng.trade is not None, "submits:", len(h.sim.submits), "kinds:", sorted(set(k for k in h.j.kinds() if k in ('entry_not_found','reconcile_mismatch','reconcile_halt','kill_start'))))
# a second candidate cannot be sent while the slot is uncertain:
print("  slot busy (POSITION_OPEN) while uncertain:", h.eng.slot_state.value in ("ENTRY_PENDING",))
h.until("15:30:35", 1)
print("  by 15:30:35: lookup works again; slot:", h.eng.slot_state.value, " broker submits:", len(h.sim.submits), " kinds:", sorted(set(k for k in h.j.kinds() if k in ('entry_not_found','reconcile_mismatch','reconcile_halt','kill_start','entry_done'))))

print("=== D. lookup keeps failing > UNCERTAIN_GIVE_UP_S (10 s): engine DROPS the tracked order, order exists at the broker")
h = base(fill_delay=1e9)
orig_get = h.sim.get_by_client_id
h.sim.get_by_client_id = lambda cid: (_ for _ in ()).throw(BrokerUnavailable("down")) if h.t < T.ts("15:30:30") else orig_get(cid)
h.sim.unavailable_next = "after"
decs = h.step(1, {"SPY": T.mkbars("SPY", "09:30", "15:29", 650.0, 652.0, wick=0.0)})
# NB: with the lookup RAISING the engine keeps uncertain_since; entry_not_found needs get_by_client_id to return None
h.sim.get_by_client_id = lambda cid: None if h.t < T.ts("15:30:30") else orig_get(cid)
h.until("15:30:14", 1)
print("  at", h.t.strftime("%H:%M:%S"), "slot:", h.eng.slot_state.value, "trade tracked:", h.eng.trade is not None, "entry_not_found lines:", len(h.j.of("entry_not_found")))
print("  order at broker (open):", [(o.client_order_id[-12:], o.status) for o in h.sim.open_orders()][:2])
h.until("15:30:40", 1)
print("  by 15:30:40: reconcile_halt:", bool(h.j.of("reconcile_halt")), " kill_done:", bool(h.j.of("kill_done")), " flat:", h.flat(), " HALT flag:", h.flag("HALT").exists(), " slot:", h.eng.slot_state.value)
