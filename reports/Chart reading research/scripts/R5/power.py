import numpy as np
from math import sqrt
z = lambda p: {0.05: 1.959964, 0.0027: 2.9998, 0.01: 2.5758}[p]
z80 = 0.841621
print("Minimum detectable correlation r between a predictor and the next-period return (two-sided test, 80% power)")
print("n_eff   r@alpha=0.05   r@alpha=0.0027 (t>=3)")
for n in (500, 1000, 2500, 5000, 12500, 25000):
    print(f"{n:6d}   {(z(0.05)+z80)/sqrt(n):.3f}         {(z(0.0027)+z80)/sqrt(n):.3f}")
# translate to bps for SPY: 1-min sd 2.19 bps (cache, Aug-Sep 2026) -> h-min sd under random walk
sd1 = 2.19
for h in (30, 60):
    sdh = sd1 * sqrt(h)
    print(f"forward {h}-min return sd (random-walk scaling of 2.19 bps/min) = {sdh:.1f} bps")
    for n in (2500, 12500):
        r = (z(0.0027)+z80)/sqrt(n)
        print(f"   n_eff={n}: detectable effect = r*sd = {r*sdh:.2f} bps per +1 SD of the predictor")
