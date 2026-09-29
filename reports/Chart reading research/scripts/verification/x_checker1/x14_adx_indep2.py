"""X14 ADX(14) - corrected independent simulation (my first attempt double-counted the previous close; fixed here)."""
import numpy as np, pandas as pd
rng = np.random.default_rng(777001)

def make_bars_correct(paths, bars, sub):
    """Arithmetic Gaussian random walk, `sub` iid N(0,1/sub) steps per bar (so a bar's close-to-close sd = 1)."""
    steps = rng.standard_normal((paths, bars*sub)) / np.sqrt(sub)
    lvl = np.cumsum(steps, axis=1)
    lvl = np.concatenate([np.zeros((paths, 1)), lvl], axis=1)          # level at each sub-step incl. the start
    grid = lvl[:, 1:].reshape(paths, bars, sub)                        # sub-step levels inside each bar
    open_ = lvl[:, :-1:sub][:, :bars]                                  # level at the bar's open = previous close
    H = np.maximum(grid.max(axis=2), open_); L = np.minimum(grid.min(axis=2), open_); C = grid[:, :, -1]
    return H + 1000, L + 1000, C + 1000

def adx_wilder(H, L, C, n=14):
    P, T = C.shape
    up = H[:, 1:] - H[:, :-1]; dn = L[:, :-1] - L[:, 1:]
    pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = np.maximum.reduce([H[:,1:]-L[:,1:], np.abs(H[:,1:]-C[:,:-1]), np.abs(L[:,1:]-C[:,:-1])])
    m = T-1
    def wsum(x):
        s = np.full((P, m), np.nan); s[:, n-1] = x[:, :n].sum(axis=1)
        for i in range(n, m): s[:, i] = s[:, i-1] - s[:, i-1]/n + x[:, i]
        return s
    st, sp, sm = wsum(tr), wsum(pdm), wsum(mdm)
    pdi, mdi = 100*sp/st, 100*sm/st
    dx = 100*np.abs(pdi-mdi)/(pdi+mdi)
    adx = np.full((P, m), np.nan)
    adx[:, 2*n-2] = dx[:, n-1:2*n-1].mean(axis=1)
    for i in range(2*n-1, m): adx[:, i] = (adx[:, i-1]*(n-1) + dx[:, i])/n
    return adx

# sanity check 1: lag-1 autocorrelation of bar closes must be ~0 for a random walk
H, L, C = make_bars_correct(2000, 200, 5)
r = np.diff(C, axis=1)
print("sanity: lag-1 autocorr of bar returns = %.4f (should be ~0); sd of bar returns = %.3f (should be ~1)" % (np.corrcoef(r[:,1:].ravel(), r[:,:-1].ravel())[0,1], r.std()))

for sub, label in ((5, "bars of 5 sub-steps (5-min bars from 1-min)"), (30, "bars of 30 sub-steps (near-continuous)"), (1, "close-only bars (H=max(open,close), L=min(open,close))")):
    s25, s20, vals = [], [], []
    for chunk in range(6):
        H, L, C = make_bars_correct(1500, 260, sub)
        a = adx_wilder(H, L, C, 14)
        seg = a[:, 80:]
        s25.append((seg > 25).mean(axis=1)); s20.append((seg > 20).mean(axis=1)); vals.append(seg.ravel())
    s25 = np.concatenate(s25); s20 = np.concatenate(s20); v = np.concatenate(vals)
    print(f"{label}:\n   share of bars with ADX>25: mean {s25.mean():.3f} (per-path p10 {np.percentile(s25,10):.2f}, p90 {np.percentile(s25,90):.2f}); ADX>20: {s20.mean():.3f}; ADX quantiles p50/p90/p95/p99 = " + "/".join(f"{np.percentile(v,q):.1f}" for q in (50,90,95,99)))
