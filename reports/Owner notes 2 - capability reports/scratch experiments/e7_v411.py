"""V4-11 scratch negative control: a deliberately FUTURE-INFORMED oracle setup must FAIL the repo's information-availability check.
The check below is the logic of tests/test_scalp_signals.py::test_no_look_ahead (perturb every bar after k; cut the day at k),
run on (a) a real setup and (b) an oracle that reads bar i+1's close. Import of the repo's own helpers only."""
import sys
sys.path.insert(0, "/home/user/IAMGOD/trading"); sys.path.insert(0, "/home/user/IAMGOD/trading/tests")
sys.dont_write_bytecode = True
import numpy as np
from dataclasses import replace
import test_scalp_signals as TS
from lab.scalp import signals as sg
from lab.scalp.synth import random_day

def oracle(day, ctx, live=None):
    """Enters long at bar i when the NEXT bar closes higher (reads the future)."""
    out = []
    for i in range(day.n - 1):
        if day.c[i + 1] > day.c[i] + 0.02:
            out.append(sg.Intent(m=int(day.m[i]), action="enter", side=1, stop_dist=0.5, target_dist=0.5, reason="oracle"))
            break
    return out

def passes_information_test(fn):
    for seed in range(8):
        day, ctx = random_day(seed, bps=5.0), TS._ctx()
        full = fn(day, ctx)
        for k in (0, 3, 4, 5, 20, 29, 30, 44, 61, 200, 329, 359, 360, 384):
            upto = [it for it in full if it.m <= day.m[k]]
            if [it for it in fn(TS._perturb_after(day, k, seed + 50), ctx) if it.m <= day.m[k]] != upto:
                return False, f"decision at/before bar {k} changed when later bars changed (seed {seed})"
            if fn(day.upto(k), ctx) != upto:
                return False, f"decision changed when the day was cut at bar {k} (seed {seed})"
    return True, "all decisions at or before k identical"

for name, fn in (("ORB5_QQQ (real)", sg.SETUPS["ORB5_QQQ"].fn), ("LAST30_MOM_SPY (real)", sg.SETUPS["LAST30_MOM_SPY"].fn), ("ORACLE (reads bar i+1)", oracle)):
    ok, why = passes_information_test(fn)
    print(f"{name:26s} passes the chronological information test: {ok}  ({why})")
# is the oracle's P&L 'outstanding'? show it would look great without the test
import lab.scalp.backtest as bt
tot = 0.0; n = 0
for seed in range(40):
    day = random_day(seed, bps=5.0)
    trades = bt.execute(day, oracle(day, TS._ctx()))
    for t in trades:
        tot += (t.exit - t.entry); n += 1
print(f"oracle gross P&L over {n} trades on 40 random days (per share): {tot:+.2f}  (only useful to show why the test matters)")
