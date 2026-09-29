"""X13 independent Black-Scholes recomputation (checker2). scipy used for the normal CDF only; formula written from scratch."""
from math import log, sqrt, exp
from scipy.stats import norm

def bs_call(S, K, T, sig, r=0.0, q=0.0):
    if T <= 0: return max(S - K, 0.0)
    d1 = (log(S / K) + (r - q + 0.5 * sig**2) * T) / (sig * sqrt(T)); d2 = d1 - sig * sqrt(T)
    return S * exp(-q * T) * norm.cdf(d1) - K * exp(-r * T) * norm.cdf(d2)

S = 766.0
TRADING_YEAR_MIN = 252 * 390          # 98,280 trading minutes
CAL_YEAR_MIN = 365 * 24 * 60           # 525,600 calendar minutes
print("ATM call (K = S = 766), 1-cent half-spread as % of premium")
print("Convention A = 'trading time' (252 days x 390 min, the researcher's convention); B = calendar minutes / 525,600 (what Cboe's VIX1D method uses for time to expiry)")
for label, conv in (("A trading-time", TRADING_YEAR_MIN), ("B calendar-time", CAL_YEAR_MIN)):
    print(f"\n{label}:")
    print(f"{'min to expiry':>14} | " + " | ".join(f"IV {iv:>2d}%: prem, 1c%" for iv in (12, 15, 20)))
    for mins in (25, 30, 60, 120, 180, 240, 390):
        row = []
        for iv in (12, 15, 20):
            T = mins / conv
            p0 = bs_call(S, S, T, iv / 100)                # r = q = 0
            row.append(f"${p0:6.3f}, {0.01/p0*100:5.2f}%")
        print(f"{mins:>14d} | " + " | ".join(row))

print("\nResearcher's exact inputs (r = 4%, q = 1.2%, K = S, 25 trading-minutes, IV 15%):", round(bs_call(S, S, 25/TRADING_YEAR_MIN, 0.15, 0.04, 0.012), 4))
print("Same with r=q=0:", round(bs_call(S, S, 25/TRADING_YEAR_MIN, 0.15), 4))
print("Rule-of-thumb check: 0.3989 * S * sigma * sqrt(T) =", round(0.3989422804 * S * 0.15 * sqrt(25/TRADING_YEAR_MIN), 4))
print("\nSensitivity of the 25-minute (trading-time) call to IV 12-20%:")
for iv in (12, 13, 14, 15, 16, 17, 18, 19, 20):
    p = bs_call(S, S, 25/TRADING_YEAR_MIN, iv/100, 0.04, 0.012)
    print(f"  IV {iv}%: premium ${p:.3f}; 1c = {0.01/p*100:.2f}% of premium; round trip (2 x 1c) = {0.02/p*100:.2f}%")
print("\nSame, calendar-time convention (25 min / 525,600):")
for iv in (12, 15, 20):
    p = bs_call(S, S, 25/CAL_YEAR_MIN, iv/100, 0.04, 0.012)
    print(f"  IV {iv}%: premium ${p:.3f}; 1c = {0.01/p*100:.2f}% of premium; round trip (2 x 1c) = {0.02/p*100:.2f}%")

# What if the option is bought with 6 hours left and held only 25 minutes? Premium paid = 6h call; cost share of 1c
print("\nSame-day option bought at ~10:00 (about 360 min to expiry) and held 25 min: premium paid, IV 15%:")
for label, conv in (("trading-time", TRADING_YEAR_MIN), ("calendar-time", CAL_YEAR_MIN)):
    p = bs_call(S, S, 360/conv, 0.15, 0.04, 0.012)
    print(f"  {label}: ${p:.3f}; 1c = {0.01/p*100:.2f}% of premium")
# expected 1-sd 25-min move in bps
print("\n1-sd SPY move over 25 min at 15% IV (trading-time):", round(S*0.15*sqrt(25/TRADING_YEAR_MIN), 3), "dollars =", round(1e4*0.15*sqrt(25/TRADING_YEAR_MIN),2), "bp")
