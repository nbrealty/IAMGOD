# Independent check of Y14. Written from scratch (does not import the researchers' luck_table.py).
# Question: for N independent zero-skill strategies, what is the expected best annualised Sharpe
# after T = 2 years (~504 daily obs)?  Claim: E[max of N std normals]/sqrt(T)
# Claimed: N=8 -> ~1.0 ; N=240 -> ~2.0 (R2) ; N=28 -> ~1.45 (R7)
import numpy as np, math

# 1) EXACT expected maximum of N iid standard normals by numerical integration:
#    E[max] = integral x * N * phi(x) * Phi(x)^(N-1) dx
def phi(x): return np.exp(-0.5*x*x)/math.sqrt(2*math.pi)
_erf = np.vectorize(math.erf)
def Phi(x): return 0.5*(1+_erf(x/math.sqrt(2)))
def emax_exact(N):
    x = np.linspace(-9, 9, 360001)
    dx = x[1]-x[0]
    f = x * N * phi(x) * Phi(x)**(N-1)
    return float(np.sum(f)*dx)

Ns = [1, 2, 5, 8, 10, 14, 28, 45, 100, 240, 243, 1000, 7846]
T = 2.0
print("N | exact E[max of N normals] | /sqrt(2) (T=2y)")
for N in Ns:
    m = emax_exact(N)
    print(f"{N:6d} | {m:.4f} | {m/math.sqrt(T):.3f}")

# 2) Monte Carlo of the normal maximum (independent check of the integral)
rng = np.random.default_rng(12345)
print("\nMonte Carlo of E[max of N normals], 200000 reps")
for N in [8, 28, 240]:
    z = rng.standard_normal((200000, N)).max(axis=1)
    print(f"N={N}: MC mean max = {z.mean():.4f}  (se {z.std()/math.sqrt(len(z)):.4f})  -> /sqrt(2) = {z.mean()/math.sqrt(2):.3f}")

# 3) Direct simulation of Sharpe ratios from daily data: 504 daily iid N(0, 1%) returns, true skill zero,
#    annualised Sharpe = mean/std*sqrt(252), take max across N independent strategies, average over reps.
print("\nDirect simulation with 504 daily observations per strategy (annualised Sharpe = mean/sd*sqrt(252))")
days = 504
for N, reps in [(8, 20000), (28, 20000), (240, 5000)]:
    best = np.empty(reps)
    for r in range(reps):
        x = rng.standard_normal((N, days))
        sr = x.mean(axis=1)/x.std(axis=1, ddof=1)*math.sqrt(252)
        best[r] = sr.max()
    print(f"N={N}: mean best annualised Sharpe = {best.mean():.3f} (sd across reps {best.std():.3f}); "
          f"5th-95th pct {np.percentile(best,5):.2f}-{np.percentile(best,95):.2f}")

# 4) What sample SD does an annualised Sharpe have when true Sharpe = 0? (should be ~ 1/sqrt(T) = 0.707)
x = rng.standard_normal((100000, days))
sr = x.mean(axis=1)/x.std(axis=1, ddof=1)*math.sqrt(252)
print(f"\nSD of a single zero-skill annualised Sharpe with {days} daily obs: {sr.std():.4f} (theory 1/sqrt(2)={1/math.sqrt(2):.4f}; note 504/252 = 2.0 years)")

# 5) Approximation used by the researchers in R2/R7 (Bailey, Borwein, Lopez de Prado, Zhu 2014):
#    E[max] ~ (1-g)*Z^-1(1-1/N) + g*Z^-1(1-1/(N e)) - implemented by me with a bisection inverse normal CDF
from statistics import NormalDist
Zinv = NormalDist().inv_cdf
g = 0.5772156649015329
def emax_approx(N): return (1-g)*Zinv(1-1/N) + g*Zinv(1-1/(N*math.e))
print("\nApprox formula vs exact:")
for N in [8, 28, 240]:
    print(f"N={N}: approx {emax_approx(N):.4f} exact {emax_exact(N):.4f}  -> Sharpe(T=2y): approx {emax_approx(N)/math.sqrt(2):.3f}, exact {emax_exact(N)/math.sqrt(2):.3f}")

# 6) Which N gives exactly Sharpe 1.0 and 2.0 at T=2? (exact)
def solve_N(target, T):
    tgt = target*math.sqrt(T)
    lo, hi = 1, 10**7
    while lo < hi:
        mid = (lo+hi)//2
        # use the accurate approximation for very large N, exact integration for small
        v = emax_exact(mid) if mid < 5000 else emax_approx(mid)
        if v >= tgt: hi = mid
        else: lo = mid+1
    return lo
for target in [1.0, 1.45, 2.0]:
    print(f"N needed so that exact E[max]/sqrt(2) reaches {target}: {solve_N(target, 2.0)}")
