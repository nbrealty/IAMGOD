"""X14 independent re-simulation (checker2): R-squared of log-price on time, and Mann-Kendall on levels, pure random walks.
Written from scratch; does not import or reuse the researcher's code."""
import numpy as np
from math import erf, sqrt
rng = np.random.default_rng(20260929)

def norm_sf2(z):  # two-sided p from |z|
    return 1 - erf(abs(z) / sqrt(2))

def gen_steps(kind, paths, n):
    if kind == "gauss":
        return rng.standard_normal((paths, n))
    if kind == "t3":
        return rng.standard_t(3, size=(paths, n)) / sqrt(3.0)
    if kind == "t5":
        return rng.standard_t(5, size=(paths, n)) / sqrt(5/3)
    raise ValueError

def r2_of_paths(P):
    """P shape (paths, m) price levels (log price). R^2 of OLS of P on 0..m-1 = corr^2."""
    m = P.shape[1]
    t = np.arange(m) - (m - 1) / 2.0
    Pc = P - P.mean(axis=1, keepdims=True)
    cov = (Pc * t).sum(axis=1)
    return cov**2 / ((t**2).sum() * (Pc**2).sum(axis=1))

def mk_S(P):
    """Mann-Kendall S for each row: sum_{i<j} sign(P_j - P_i)."""
    paths, m = P.shape
    S = np.zeros(paths)
    for k in range(1, m):
        S += np.sign(P[:, k:] - P[:, :-k]).sum(axis=1)
    return S

def mk_p_reject(P, alpha_z=1.959964):
    paths, m = P.shape
    S = mk_S(P)
    var = m * (m - 1) * (2 * m + 5) / 18.0
    Z = np.where(S > 0, (S - 1) / sqrt(var), np.where(S < 0, (S + 1) / sqrt(var), 0.0))
    return np.mean(np.abs(Z) > alpha_z), Z

print("== R-squared of log price on time; P(R2 > x); paths are independent random walks (start at 0), N points per window ==")
for kind in ("gauss", "t3"):
    print("model:", kind)
    for npts in (10, 13, 21, 30, 61, 100, 250, 391, 1000, 3000):
        paths = 100000 if npts <= 400 else (20000 if npts <= 1000 else 5000)
        st = gen_steps(kind, paths, npts - 1)
        P = np.concatenate([np.zeros((paths, 1)), np.cumsum(st, axis=1)], axis=1)
        r2 = r2_of_paths(P)
        print(f" points={npts:5d} paths={paths:6d} | median R2={np.median(r2):.3f}  P(R2>0.7)={np.mean(r2>0.7):.3f}  P(R2>0.8)={np.mean(r2>0.8):.3f}  P(R2>0.9)={np.mean(r2>0.9):.3f}  p95={np.percentile(r2,95):.3f}")

print()
print("== Rolling windows of one very long random walk (Gaussian): fraction of windows with R2>0.8 ==")
N = 400000
walk = np.cumsum(rng.standard_normal(N))
from numpy.lib.stride_tricks import sliding_window_view
for w in (13, 21, 61, 391):
    W = sliding_window_view(walk, w)[::3]  # every 3rd window to keep memory ok
    r2 = r2_of_paths(np.ascontiguousarray(W))
    print(f" rolling window={w:4d} points, {len(r2)} windows | P(R2>0.8)={np.mean(r2>0.8):.3f}")

print()
print("== Mann-Kendall on price LEVELS of a pure random walk; share of paths with |Z|>1.96 (classic no-tie variance) ==")
for npts in (10, 12, 13, 20, 21, 30, 60, 61, 100, 250, 390, 391, 500):
    paths = 40000 if npts <= 100 else (10000 if npts <= 250 else 3000)
    st = rng.standard_normal((paths, npts - 1))
    P = np.concatenate([np.zeros((paths, 1)), np.cumsum(st, axis=1)], axis=1)
    frac, Z = mk_p_reject(P)
    print(f" points={npts:4d} paths={paths:6d} | P(|Z|>1.96)={frac:.3f}")

print()
print("== Sanity: Mann-Kendall on iid RETURNS (not prices) should reject ~5% ==")
for npts in (12, 60, 390):
    paths = 20000 if npts <= 60 else 3000
    R = rng.standard_normal((paths, npts))
    frac, Z = mk_p_reject(R)
    print(f" iid returns, n={npts:4d} | P(|Z|>1.96)={frac:.3f}")
