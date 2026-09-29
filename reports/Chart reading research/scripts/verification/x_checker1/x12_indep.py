"""Independent re-derivation of claim X12 (checker 1). Written from scratch; does not import or read the researcher's scripts."""
from math import sqrt
from scipy.stats import norm

S = 766.0                  # SPY price, $
spread = 0.02              # quoted spread, $
sec_fee_per_mm = 20.60     # $ per $1,000,000 of SALES (SEC Section 31, effective 4 Apr 2026)
bp = 1e-4

# --- 1. Round-trip cost of a long trade: buy at the ask, sell at the bid ---
spread_cost_bp = spread / S / bp          # paying the full spread once per round trip (half at each end)
sec_fee_bp     = sec_fee_per_mm / 1e6 / bp   # fee is a fixed fraction of the sale value, price-independent
total_bp       = spread_cost_bp + sec_fee_bp
print(f"1. spread cost = {spread_cost_bp:.4f} bp ; SEC fee = {sec_fee_bp:.4f} bp ; total = {total_bp:.4f} bp")
print(f"   in cents/share: spread {spread*100:.2f} c + SEC fee {S*sec_fee_per_mm/1e6*100:.3f} c = {(spread + S*sec_fee_per_mm/1e6)*100:.3f} c")
# FINRA TAF (sales): 0.000166 $/share in 2025-26 (check), CAT ~ tiny
for taf in (0.000166, 0.000195):
    print(f"   FINRA TAF at ${taf}/share on a sale of one share = {taf/S/bp:.4f} bp")

# --- 2. Break-even hit rate p = 0.5 + C/(2M) ---
# Derivation: a trade earns +|r| if direction right, -|r| if wrong. E[gross] = (2p-1)*M where M = E|r|
# (assuming the size of the move is independent of whether the call was right).  Break-even: (2p-1)*M = C.
print("\n2. break-even hit rate p = 0.5 + C/(2M)")
for label, M in (("1 min", 1.54), ("5 min", 3.46), ("30 min", 8.62)):
    for C in (0.47, 1.0):
        p = 0.5 + C/(2*M)
        # cross-check by brute-force: solve (2p-1)*M - C = 0 numerically
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo+hi)/2
            if (2*mid-1)*M - C > 0: hi = mid
            else: lo = mid
        print(f"   {label:>6}  M={M:5.2f} bp  C={C:4.2f} bp  ->  p = {p*100:6.2f}%  (numeric {mid*100:6.2f}%)")

# --- 3. Sample size for a +1 bp net edge, sd 12 bp per trade ---
print("\n3. trades needed to detect a true mean of 1 bp when per-trade sd = 12 bp")
delta = 1.0
for sd in (12.0, 12.04):
    print(f"   sd = {sd}")
    # (a) two-sided test at 5% (|t|>1.96), power 80%
    n_a = ((norm.ppf(0.975)+norm.ppf(0.80))*sd/delta)**2
    # (b) one-sided test at 5%, power 80%
    n_b = ((norm.ppf(0.95)+norm.ppf(0.80))*sd/delta)**2
    # (c) critical value t = 3 (|z|>3), power 80%
    n_c = ((3.0+norm.ppf(0.80))*sd/delta)**2
    # (d) expected t-statistic equal to 3: delta*sqrt(n)/sd = 3
    n_d = (3.0*sd/delta)**2
    # (e) two-sided p < 0.0018 (z=3.123), power 80%
    z_e = norm.ppf(1-0.0018/2)
    n_e = ((z_e+norm.ppf(0.80))*sd/delta)**2
    print(f"   (a) two-sided 5% (critical z=1.96), 80% power : {n_a:8.0f}")
    print(f"   (b) one-sided 5% (critical z=1.645), 80% power: {n_b:8.0f}")
    print(f"   (c) critical z = 3.0, 80% power               : {n_c:8.0f}")
    print(f"   (d) EXPECTED t-stat = 3.0 (50% power at z=3)  : {n_d:8.0f}")
    print(f"   (e) two-sided p<0.0018 (z={z_e:.3f}), 80% power : {n_e:8.0f}")
# years at 250 trades/year
for n in (1136, 1300, 2139, 2273):
    print(f"   {n} trades = {n/250:.1f} years at 250 trades a year")
