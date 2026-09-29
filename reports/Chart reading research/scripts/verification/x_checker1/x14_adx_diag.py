"""Diagnostic: which bar-construction choice explains the gap between my ADX share (about 38-40%) and the researcher's (34-37%)?
Variants (all use MY ADX function and Gaussian arithmetic walks):
  A  correct construction, H/L include the bar's open, 260 bars/path, drop first 80
  B  correct construction, H/L from the bar's own sub-steps only (open excluded), 260 bars, drop 80
  C  correct construction, 160 bars/path, drop first 60 (the researcher's window layout)
  D  the researcher's construction pattern (offset added to an already-cumulative path for H and L but not for C)"""
import numpy as np
exec(open("x14_adx_indep2.py").read().split("# sanity check 1")[0])   # reuse make_bars_correct and adx_wilder (my code)
rng = np.random.default_rng(99)

def build(paths, bars, sub, include_open=True, buggy=False):
    steps = rng.standard_normal((paths, bars*sub)) / np.sqrt(sub)
    lvl = np.cumsum(steps, axis=1)
    grid = lvl.reshape(paths, bars, sub)
    close = grid[:, :, -1]
    prev = np.concatenate([np.zeros((paths, 1)), close[:, :-1]], axis=1)
    if buggy:
        g2 = grid + prev[:, :, None]              # adds previous close on top of an already cumulative path (H, L only)
        H = g2.max(axis=2); L = g2.min(axis=2); C = close
    else:
        H = grid.max(axis=2); L = grid.min(axis=2)
        if include_open:
            H = np.maximum(H, prev); L = np.minimum(L, prev)
        C = close
    return H+1000, L+1000, C+1000

def share(paths_bars, sub, drop, reps, **kw):
    out = []
    for _ in range(reps):
        H, L, C = build(2000, paths_bars, sub, **kw)
        a = adx_wilder(H, L, C, 14)[:, drop:]
        out.append((a > 25).mean(axis=1))
    return np.concatenate(out).mean()

for sub in (5, 30):
    print(f"sub-steps per bar = {sub}")
    print("  A correct, include open, 260 bars, drop 80 :  %.3f" % share(260, sub, 80, 4))
    print("  B correct, exclude open, 260 bars, drop 80 :  %.3f" % share(260, sub, 80, 4, include_open=False))
    print("  C correct, include open, 160 bars, drop 60 :  %.3f" % share(160, sub, 60, 6))
    print("  D researcher-style offset bug, 160 bars, drop 60: %.3f" % share(160, sub, 60, 6, buggy=True))
