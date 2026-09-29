"""V4-12 scratch experiment: TWO ENTRY PROPOSALS IN THE SAME TICK / SAME BAR against the one-position budget.
At 15:29 bar close both LAST30_MOM_SPY and NOISE_MOM_SPY (both EXPLORATORY here, as in the repo tests) go long on SPY.
Part A: normal engine, both registration orders -> exactly one order may reach the broker; print the loser's reasons.
Part B: ablation, to find which single layer stops the second order when the others are removed (scratch monkeypatch only)."""
import tempfile, pathlib, itertools, copy
from common import *
from lab.scalp.live import risk as R, engine as EN, guard as G

def scenario(order, ablate=None, budget_cash=None, qty_cap=None, fill_delay=None):
    tmp = pathlib.Path(tempfile.mkdtemp())
    regs = [T.REG.get(s, "SPY") for s in order]
    reg = C.Registry(tuple(regs), T.REG.account_last4)
    sim_kw = {"fill_delay_s": fill_delay} if fill_delay else None
    h = T.H(tmp, start="15:29:59", registry=reg, px={"SPY": 650.0, "QQQ": 560.0}, sim_kw=sim_kw)
    if budget_cash is not None:
        h.c.cash_prev_close = budget_cash
    bars = T.mkbars("SPY", "09:30", "15:29", 650.0, 652.0, wick=0.0)     # up in first half hour AND above the noise band at 15:30
    h.px["SPY"] = 652.0
    decs = h.step(1, {"SPY": bars})                                       # 15:30:00: both setups decide on the SAME bar
    ent = [d for d in decs if d.candidate.action == "enter"]
    return h, ent

def show(tag, h, ent):
    print(f"--- {tag}")
    for d in ent:
        print(f"   {d.candidate.setup_id:16s} accepted={d.accepted} reasons={[r.value for r in d.reasons]}")
    print(f"   broker submits={len(h.sim.submits)} positions={[(p.symbol,p.qty) for p in h.sim.positions()]} entry_submits={h.c.entry_submits} round_trips={h.c.round_trips}")

# ---------------- Part A: normal engine, both registration orders
for order in (["LAST30_MOM_SPY", "NOISE_MOM_SPY"], ["NOISE_MOM_SPY", "LAST30_MOM_SPY"]):
    h, ent = scenario(order)
    show("A normal engine, order " + "+".join(order), h, ent)
    assert len(ent) == 2 and sum(d.accepted for d in ent) == 1 and len(h.sim.submits) == 1

# ---------------- Part A2: first order still UNFILLED (broker slow) when the second proposal is evaluated in the same tick
h, ent = scenario(["LAST30_MOM_SPY", "NOISE_MOM_SPY"], fill_delay=1e9)
show("A2 first parent unfilled at the broker (slot=ENTRY_PENDING)", h, ent)
assert len(h.sim.submits) == 1

# ---------------- Part B: ablation
def ablated_run(name, patch):
    """Run the same scenario with some layer(s) disabled and report how many orders reached the broker."""
    undo = patch()
    try:
        h, ent = scenario(["LAST30_MOM_SPY", "NOISE_MOM_SPY"], fill_delay=1e9)
        subs = len(h.sim.submits)
        res = [(d.candidate.setup_id, d.accepted, [r.value for r in d.reasons]) for d in ent]
        killed = bool(h.j.of("runaway_orders"))
    finally:
        undo()
    print(f"   {name:75s} broker submits={subs}  runaway_kill={killed}  second={res[1][1:] }")
    return subs

print("--- B ablation (first parent unfilled), which layer alone stops the 2nd order?")
orig_check = R.entry_check
def strip(*drop):
    def patch():
        def wrapped(ec):
            r, n = orig_check(ec)
            return [x for x in r if x not in drop], n
        R.entry_check = wrapped
        EN.risk.entry_check = wrapped
        def undo():
            R.entry_check = orig_check
            EN.risk.entry_check = orig_check
        return undo
    return patch
Reason_ = Reason
ablated_run("none removed", lambda: (lambda: None))
ablated_run("risk.py POSITION_OPEN+OPEN_PARENT+NO_ADD stripped (engine extra POSITION_OPEN + guard remain)",
            strip(Reason_.POSITION_OPEN, Reason_.OPEN_PARENT, Reason_.NO_ADD))

# also strip the engine's explicit extra POSITION_OPEN rule: emulate by making risk return nothing at all
def strip_all():
    def wrapped(ec):
        return [], {}
    R.entry_check = wrapped
    EN.risk.entry_check = wrapped
    def undo():
        R.entry_check = orig_check
        EN.risk.entry_check = orig_check
    return undo
# with risk fully off, the engine's own "if t is not None: POSITION_OPEN" line is the next layer
ablated_run("risk.entry_check returns [] (engine's own 'slot taken' line + guard remain)", strip_all)
# remove that engine line too by faking self.trade -> None at the moment _entry_candidate runs (only the guard remains)
def strip_all_and_slot():
    undo1 = strip_all()
    orig = EN.Engine._entry_candidate
    def patched(self, now, c, reg):
        keep = self.trade
        self.trade = None            # pretend the slot is free: only GuardedBroker (asks the broker) is left
        try:
            return orig(self, now, c, reg)
        finally:
            if self.trade is None:
                self.trade = keep
    EN.Engine._entry_candidate = patched
    def undo():
        undo1()
        EN.Engine._entry_candidate = orig
    return undo
ablated_run("risk off AND engine slot line off (only GuardedBroker open-parent cap remains)", strip_all_and_slot)

# Same ablation but with the first parent FILLED (position open, legs live): guard cannot count a filled parent
def ablated_filled(name, patch):
    undo = patch()
    try:
        h, ent = scenario(["LAST30_MOM_SPY", "NOISE_MOM_SPY"])
        subs = len(h.sim.submits)
        res = [(d.candidate.setup_id, d.accepted, [r.value for r in d.reasons]) for d in ent]
        pos = [(p.symbol, p.qty) for p in h.sim.positions()]
        h.until("15:30:20", 1)
        kill = h.j.of("reconcile_halt")
    finally:
        undo()
    print(f"   {name:75s} broker submits={subs} positions={pos} reconcile_halt_after_20s={bool(kill)} second={res[1][1:]}")
print("--- B2 ablation with the FIRST PARENT FILLED (one share held, legs live)")
ablated_filled("risk off AND engine slot line off (guard + reconcile after the fact)", strip_all_and_slot)
print("DONE")
