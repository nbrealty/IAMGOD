"""V4-12 part B (scratch): which LAYER alone stops the second same-tick entry, and what happens when upstream layers are
removed (monkeypatches live only in this scratch process; the repo files are untouched)."""
import tempfile, pathlib
from common import *
from lab.scalp.live import risk as R, engine as EN

orig_check, orig_ec, orig_rec = R.entry_check, EN.Engine._entry_candidate, EN.Engine._reconcile

def run(first_filled, risk_off, slot_off, pre_reconcile_off):
    R.entry_check, EN.Engine._entry_candidate, EN.Engine._reconcile = orig_check, orig_ec, orig_rec
    if risk_off:
        R.entry_check = lambda ec: ([], {})
        EN.risk.entry_check = R.entry_check
    else:
        EN.risk.entry_check = orig_check
    if slot_off:
        def ec(self, now, c, reg):
            keep = self.trade
            self.trade = None                       # the engine believes the slot is free
            try:
                return orig_ec(self, now, c, reg)
            finally:
                if self.trade is None or self.trade is keep:
                    self.trade = keep               # (a new trade replaced the first: the first is now UNTRACKED)
        EN.Engine._entry_candidate = ec
    if pre_reconcile_off:
        def rec(self, now, force=False):
            if force:
                return []
            return orig_rec(self, now, force)
        EN.Engine._reconcile = rec
    tmp = pathlib.Path(tempfile.mkdtemp())
    reg = C.Registry((T.LAST30, T.NOISE), T.REG.account_last4)
    h = T.H(tmp, start="15:29:59", registry=reg, px={"SPY": 650.0, "QQQ": 560.0},
            sim_kw=None if first_filled else {"fill_delay_s": 1e9})
    h.px["SPY"] = 652.0
    decs = h.step(1, {"SPY": T.mkbars("SPY", "09:30", "15:29", 650.0, 652.0, wick=0.0)})
    ent = [d for d in decs if d.candidate.action == "enter"]
    res = [(d.candidate.setup_id[:6], d.accepted, [r.value for r in d.reasons]) for d in ent]
    subs_now = len(h.sim.submits)
    h.until("15:30:12", 1)
    out = dict(first_filled=first_filled, risk_off=risk_off, slot_off=slot_off, pre_reconcile_off=pre_reconcile_off,
               broker_submits_same_tick=subs_now, decisions=res,
               runaway=bool(h.j.of("runaway_orders")), reconcile_halt=bool(h.j.of("reconcile_halt")),
               kill_done=bool(h.j.of("kill_done")), shares_at_broker_after_12s=sum(p.qty for p in h.sim.positions()),
               total_broker_submits=len(h.sim.submits))
    return out

rows = [
    (True,  False, False, False),   # normal, first filled
    (False, False, False, False),   # normal, first unfilled
    (False, True,  False, False),   # risk.py off: engine slot line remains
    (False, True,  True,  False),   # risk off + slot line off: pre-submit reconcile remains (sees the first order as foreign only because slot_off hides it) -> artifact
    (False, True,  True,  True),    # risk off + slot off + pre-submit reconcile off: ONLY GuardedBroker remains (first parent unfilled)
    (True,  True,  True,  True),    # same but first parent FILLED: guard cannot count a filled parent -> after-the-fact reconcile only
]
for r in rows:
    o = run(*r)
    print(o)
R.entry_check, EN.Engine._entry_candidate, EN.Engine._reconcile = orig_check, orig_ec, orig_rec
