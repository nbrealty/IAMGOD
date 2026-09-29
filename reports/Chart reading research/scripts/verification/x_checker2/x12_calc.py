"""X12 independent recomputation (checker2)."""
from math import sqrt
from scipy.stats import norm
S = 766.0
spread_c = 0.02
spread_bp = spread_c / S * 1e4
sec_fee_bp = 20.60 / 1e6 * 1e4          # $20.60 per $1,000,000 of sales, on the sale leg only
print(f"spread cost (full 2c crossed once round trip = 2 half-spreads): {spread_bp:.4f} bp")
print(f"SEC fee (rate 20.60 per $1M, sale leg): {sec_fee_bp:.4f} bp")
print(f"round trip total: {spread_bp+sec_fee_bp:.4f} bp = {(spread_bp+sec_fee_bp)/1e4*S*100:.2f} cents per share")
# FINRA TAF: $0.000195/share on sales (rate as quoted by researcher); tiny
print(f"FINRA TAF at $0.000195/share on sale: {0.000195/S*1e4:.4f} bp")
# QQQ
Sq = 716.6
print(f"QQQ (716.6): spread 2c {0.02/Sq*1e4:.4f} bp; round trip {0.02/Sq*1e4+sec_fee_bp:.4f} bp")
print()
print("Hit rate needed p = 0.5 + C/(2M), derived by: E[net] = p*M - (1-p)*M - C = (2p-1)M - C = 0")
for label, M in (("1 min", 1.54), ("5 min", 3.46), ("30 min", 8.62)):
    row = []
    for C in (0.47, 1.0, 3.0):
        p = 0.5 + C / (2 * M)
        row.append(f"C={C}: {p*100:5.1f}%" if p <= 1 else f"C={C}: impossible (>100%)")
    print(f"  {label:7s} M={M:5.2f} bp | " + " | ".join(row))
print()
print("Alternative model check: if a win/loss is +/- M exactly, p above is exact. If instead moves are Normal(0, s) with mean|move|=M, and you get the sign right w.p. p, gain when right = E|move|=M anyway -> same formula.")
print()
print("Power: n = ((z_alpha + z_beta) * sd / edge)^2, 80 pct power, z_beta =", round(norm.ppf(0.8), 4))
zb = norm.ppf(0.8)
for sd in (12.0, 12.04):
    for label, za in (("two-sided 5% (t crit 1.96)", norm.ppf(0.975)),
                      ("one-sided 5% (t crit 1.645)", norm.ppf(0.95)),
                      ("t crit = 3.0 exactly", 3.0),
                      ("researcher's 'strict' p<0.0018 two-sided (z=3.12)", norm.ppf(1 - 0.0018/2)),
                      ("t crit 3.0 one-sided-ish p=0.00135", norm.ppf(1 - 0.00135))):
        n = ((za + zb) * sd / 1.0) ** 2
        print(f"  sd={sd:5.2f} bp, edge=1 bp, {label:52s}: n = {n:7.0f} trades = {n/250:4.1f} years at 250/yr")
print()
print("Expected-t reading: if 'true t = 3' means the expected t-statistic of the mean equals 3 (about 85% power at 1.96):")
print(f"  n = (3*12/1)^2 = {(3*12)**2}  trades")
print("Minimum detectable edge (80% power, two-sided 5%) at sd 12.04 for N trades:")
for N in (60, 250, 500, 2300):
    print(f"  N={N}: {(norm.ppf(0.975)+zb)*12.04/sqrt(N):.2f} bp")
