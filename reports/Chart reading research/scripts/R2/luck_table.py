# Own calculation. If N independent rules all have TRUE Sharpe = 0, what is the best in-sample annualised Sharpe you expect to see by luck alone?
# Approximation (Bailey, Borwein, Lopez de Prado, Zhu): E[max of N standard normals] ~ (1-g)*Z^-1(1-1/N) + g*Z^-1(1-1/(N*e)), g = Euler-Mascheroni.
# An annualised Sharpe estimated from Y years of daily P&L has standard error ~ 1/sqrt(Y) when true Sharpe is 0.
from statistics import NormalDist
import math
Z = NormalDist().inv_cdf
g = 0.5772156649
def emax(N):
    if N == 1: return 0.0
    return (1-g)*Z(1-1/N) + g*Z(1-1/(N*math.e))
Ns = [1, 5, 14, 28, 45, 100, 500, 1000, 7846]
Ys = [1, 2, 5, 10]
print("| N rules tried | E[max t-stat] by luck | " + " | ".join(f"best lucky Sharpe, {y}y data" for y in Ys) + " | P(at least one has t>2 by luck) |")
print("|---|---|" + "---|"*len(Ys) + "---|")
for N in Ns:
    m = emax(N)
    row = [f"{m/math.sqrt(y):.2f}" for y in Ys]
    p = 1-(1-0.0455)**N   # two-sided t>2 ~ p=0.0455
    print(f"| {N} | {m:.2f} | " + " | ".join(row) + f" | {p*100:.0f}% |")
print()
# Sharpe needed for t>=3.0 (Harvey-Liu-Zhu hurdle) and Bonferroni for N tests at 5% two-sided
print("Sharpe needed to reach t = 3.0:", {y: round(3.0/math.sqrt(y),2) for y in Ys})
print()
print("| N tests | Bonferroni p cutoff (0.05/N) | t needed (two-sided) | annualised Sharpe needed with 1y | 2y | 5y | 10y |")
print("|---|---|---|---|---|---|---|")
for N in [1, 14, 28, 45, 100, 1000, 7846]:
    p = 0.05/N
    t = Z(1-p/2)
    print(f"| {N} | {p:.5f} | {t:.2f} | " + " | ".join(f"{t/math.sqrt(y):.2f}" for y in [1,2,5,10]) + " |")
# Check vs. Bailey et al: N=45, 5 years => ~1.0
print()
print("check N=45, 5y:", round(emax(45)/math.sqrt(5),2))

# How many independent tries until luck alone is expected to produce an annualised Sharpe of X, given Y years of daily P&L?
print()
print("| Sharpe that looks impressive | 1 year of data | 2 years | 5 years | 10 years |")
print("|---|---|---|---|---|")
def n_for(target_sr, y):
    tgt = target_sr*math.sqrt(y)
    lo, hi = 1, 10**9
    if emax(2) > tgt: return 2
    while lo < hi:
        mid = (lo+hi)//2
        if emax(mid) >= tgt: hi = mid
        else: lo = mid+1
    return lo
for sr in [0.5, 1.0, 1.5, 2.0, 3.0]:
    print(f"| {sr} | " + " | ".join(f"{n_for(sr,y):,}" for y in [1,2,5,10]) + " |")
