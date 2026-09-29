import numpy as np
from statistics import NormalDist
nd = NormalDist()
EULER = 0.5772156649015329

def emax_exact(N, lo=-10, hi=12, M=2_000_001):
    """E[max of N iid N(0,1)] = integral x * N * phi(x) * Phi(x)^(N-1) dx, by trapezoid rule."""
    x = np.linspace(lo, hi, M)
    # standard normal pdf and cdf (vectorised): use erf via numpy's math? use scipy-free approach
    from math import erf, sqrt, pi
    phi = np.exp(-0.5*x*x)/np.sqrt(2*np.pi)
    # Phi via erfc for accuracy: vectorised through np.frompyfunc is slow; use series with numpy's own special? 
    # numpy has no erf; use math.erf via vectorize on a coarser grid then interpolate
    xs = np.linspace(lo, hi, 200001)
    Phi_s = np.array([0.5*(1+erf(v/sqrt(2))) for v in xs])
    Phi = np.interp(x, xs, Phi_s)
    f = x * N * phi * Phi**(N-1)
    return np.trapezoid(f, x)

def emax_bailey(N):
    # Bailey & Lopez de Prado (2014) approximation:  E[max] ~ (1-g) Z^-1[1-1/N] + g Z^-1[1-1/(N e)]
    return (1-EULER)*nd.inv_cdf(1-1/N) + EULER*nd.inv_cdf(1-1/(N*np.e))

def emax_mc(N, B=400_000, seed=7):
    rng = np.random.default_rng(seed)
    tot = 0.0; cnt = 0
    chunk = max(1, 4_000_000//N)
    while cnt < B:
        m = min(chunk, B-cnt)
        tot += rng.standard_normal((m, N)).max(axis=1).sum(); cnt += m
    return tot/cnt

T = 2.0
print(f"T = {T} years (about {int(252*T)} daily observations): sd of a zero-skill annualised Sharpe estimate ~ 1/sqrt(T) = {1/np.sqrt(T):.4f}")
print(f"{'N':>8} {'E[max]exact':>12} {'E[max]MC':>10} {'BLdP approx':>12} | {'SR exact':>9} {'SR MC':>7} {'SR BLdP':>8}")
for N in [1, 2, 5, 8, 10, 14, 28, 100, 240, 243, 1000, 7846, 28000, 1_000_000]:
    ex = emax_exact(N)
    mc = emax_mc(N) if N <= 10000 else float('nan')
    ba = emax_bailey(N) if N > 1 else 0.0
    print(f"{N:>8} {ex:12.4f} {mc:10.4f} {ba:12.4f} | {ex/np.sqrt(T):9.3f} {mc/np.sqrt(T):7.3f} {ba/np.sqrt(T):8.3f}")

# Inverse question: how many tries N until the expected best SR (T=2y) reaches 1.0 and 2.0 ?
def N_for_SR(target, T=2.0):
    need = target*np.sqrt(T)
    lo, hi = 1, 10**9
    while lo < hi:
        mid = (lo+hi)//2
        if emax_bailey(mid) >= need: hi = mid
        else: lo = mid+1
    return lo
for tgt in (1.0, 1.45, 2.0):
    print(f"N such that BLdP-approx expected best SR (2y) reaches {tgt}: {N_for_SR(tgt)}")
