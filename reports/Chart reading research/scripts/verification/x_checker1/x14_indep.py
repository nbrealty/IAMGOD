"""Independent re-simulation for X14 (checker 1): random-walk noise floor for R-squared, ADX(14) and Mann-Kendall.
Written from scratch. Model: log price = cumulative sum of iid N(0,1) returns (zero drift) unless stated."""
import numpy as np, time, sys
from scipy.stats import kendalltau, norm
rng = np.random.default_rng(20260929)

# ---------- (a) R-squared of price (or log price) on time --------------------------------
def r2_time(paths):
    """paths: (P, m) array of prices along m time points -> R^2 of regressing each path on 0..m-1 (= squared correlation)."""
    P, m = paths.shape
    t = np.arange(m) - (m-1)/2.0
    y = paths - paths.mean(axis=1, keepdims=True)
    num = (y*t).sum(axis=1)**2
    den = (y**2).sum(axis=1) * (t**2).sum()
    return num/den

print("(a) R^2 of a straight-line fit of the *level* of a driftless Gaussian random walk (m prices = n returns + 1)")
print(f"{'n returns':>10} {'m prices':>9} {'paths':>8} | P(R2>0.8)  P(R2>0.9)  median R2")
for n in (12, 20, 60, 78, 390, 1950):
    Pn = 200000 if n <= 78 else (40000 if n == 390 else 6000)
    steps = rng.standard_normal((Pn, n))
    lvl = np.concatenate([np.zeros((Pn,1)), np.cumsum(steps, axis=1)], axis=1)
    r2 = r2_time(lvl)
    print(f"{n:>10} {n+1:>9} {Pn:>8} | {np.mean(r2>0.8):8.3f}  {np.mean(r2>0.9):8.3f}  {np.median(r2):8.3f}")
# Also with Student-t(3) shocks (fat tails)
print("   with Student-t(3) shocks (unit variance):")
for n in (12, 20, 60, 78, 390):
    Pn = 100000 if n <= 78 else 20000
    steps = rng.standard_t(3, size=(Pn, n))/np.sqrt(3)
    lvl = np.concatenate([np.zeros((Pn,1)), np.cumsum(steps, axis=1)], axis=1)
    print(f"   n={n:>4}: P(R2>0.8) = {np.mean(r2_time(lvl)>0.8):.3f}")

# ---------- (c) Mann-Kendall trend test on price levels ------------------------------------
def mk_S_small(x):
    """x: (P, m). S = sum_{i<j} sign(x_j - x_i), vectorised (fine for m <= ~100)."""
    P, m = x.shape
    S = np.zeros(P)
    for k in range(1, m):
        S += np.sign(x[:, k:] - x[:, :-k]).sum(axis=1)
    return S
def mk_z(S, m):
    var = m*(m-1)*(2*m+5)/18.0
    return np.where(S > 0, (S-1)/np.sqrt(var), np.where(S < 0, (S+1)/np.sqrt(var), 0.0))

print("\n(c) Mann-Kendall two-sided test at 5% (|Z|>1.96) applied to the price LEVELS of a driftless random walk")
print(f"{'n returns':>10} {'m prices':>9} | share of paths with |Z|>1.96   (m=n prices variant)")
for n in (12, 20, 60, 78, 390):
    Pn = 30000 if n <= 78 else 4000
    steps = rng.standard_normal((Pn, n))
    lvl = np.concatenate([np.zeros((Pn,1)), np.cumsum(steps, axis=1)], axis=1)   # n+1 prices
    if n <= 100:
        z1 = mk_z(mk_S_small(lvl), n+1); z2 = mk_z(mk_S_small(lvl[:, 1:]), n)
    else:
        def S_of(x):
            m = x.shape[1]; out = np.empty(x.shape[0])
            for i in range(x.shape[0]):
                tau = kendalltau(np.arange(m), x[i]).statistic
                out[i] = tau*m*(m-1)/2
            return out
        z1 = mk_z(S_of(lvl), n+1); z2 = mk_z(S_of(lvl[:, 1:]), n)
    print(f"{n:>10} {n+1:>9} | n+1 prices: {np.mean(np.abs(z1)>1.96):.3f}   n prices: {np.mean(np.abs(z2)>1.96):.3f}")
# theoretical check for large n: MK on a Brownian motion; the null distribution of Z has sd ~ 3-4x larger than 1
big = rng.standard_normal((3000, 2000)).cumsum(axis=1)
zb = np.empty(3000)
for i in range(3000):
    tau = kendalltau(np.arange(2000), big[i]).statistic
    zb[i] = tau*2000*1999/2
zb = mk_z(zb, 2000)
print(f"   n=2000: share |Z|>1.96 = {np.mean(np.abs(zb)>1.96):.3f} ; sd of Z = {zb.std():.2f} (should be 1.0 if the test were valid for an iid series)")
