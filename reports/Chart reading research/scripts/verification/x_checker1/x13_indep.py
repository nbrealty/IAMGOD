"""Independent Black-Scholes check for X13 (checker 1)."""
import numpy as np
from scipy.stats import norm
from scipy import integrate

def bs_call(S, K, T, sig, r=0.0, q=0.0):
    if T <= 0: return max(S-K, 0.0)
    d1 = (np.log(S/K) + (r - q + 0.5*sig**2)*T) / (sig*np.sqrt(T))
    d2 = d1 - sig*np.sqrt(T)
    return S*np.exp(-q*T)*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)

def numeric_call(S, K, T, sig, r=0.0, q=0.0):
    # integrate the discounted payoff over the risk-neutral lognormal density (independent of the closed form)
    mu = (r - q - 0.5*sig**2)*T; s = sig*np.sqrt(T)
    f = lambda z: max(S*np.exp(mu + s*z) - K, 0.0)*norm.pdf(z)
    val, _ = integrate.quad(f, -12, 12, points=[(np.log(K/S)-mu)/s], limit=200)
    return np.exp(-r*T)*val

S = 766.0; K = 766.0
TRADING_MIN_PER_YEAR = 252*390      # 98,280
CAL_MIN_PER_YEAR = 365*24*60        # 525,600
print("S=K=766 ; r=q=0 unless stated\n")
print("convention: trading time (25 of 98,280 min) vs calendar time (25 of 525,600 min)")
print(f"{'IV':>5} | {'trading-time call $':>19} {'1c share':>9} | {'calendar-time call $':>21} {'1c share':>9}")
for iv in (0.12, 0.15, 0.20):
    ct = bs_call(S, K, 25/TRADING_MIN_PER_YEAR, iv)
    cc = bs_call(S, K, 25/CAL_MIN_PER_YEAR, iv)
    print(f"{iv*100:4.0f}% | {ct:19.4f} {0.01/ct*100:8.2f}% | {cc:21.4f} {0.01/cc*100:8.2f}%")
# numeric integration cross-check
print("\ncross-check (numeric integration vs closed form), IV 15%:",
      round(numeric_call(S,K,25/TRADING_MIN_PER_YEAR,0.15),5), round(bs_call(S,K,25/TRADING_MIN_PER_YEAR,0.15),5))
# rule of thumb: ATM call ~ 0.3989*S*sigma*sqrt(T)
print("rule of thumb 0.3989*S*sig*sqrt(T), 15%:", round(0.3989*S*0.15*np.sqrt(25/TRADING_MIN_PER_YEAR),4))
# with realistic rates: r=4.0%, q=1.2%
for (r,q) in ((0.04,0.012),(0.045,0.011)):
    print(f"with r={r}, q={q}: trading-time $ {bs_call(S,K,25/TRADING_MIN_PER_YEAR,0.15,r,q):.4f} ; calendar-time $ {bs_call(S,K,25/CAL_MIN_PER_YEAR,0.15,r,q):.4f}")
# What if the option has more time left than the 25-minute hold? (premium at purchase, 25-minute hold)
print("\npremium at purchase if the option has T minutes left (trading-time convention, IV 15%): 1c half-spread share of premium")
for Tm in (25, 60, 120, 240, 390):
    c = bs_call(S,K,Tm/TRADING_MIN_PER_YEAR,0.15)
    print(f"  T = {Tm:3d} min: call ${c:6.3f}  ; 1c = {0.01/c*100:5.2f}% of premium ; round trip (2c) = {0.02/c*100:5.2f}%")
# Also: premium moves with the stock: delta ~0.5 -> a 25-min hold's typical stock move is ~8 bp*766 ~ $0.6; the option gains/loses ~ 0.5*that
print("\nATM delta at 25 min, IV 15%:", round(norm.cdf((0.5*0.15**2*25/TRADING_MIN_PER_YEAR)/(0.15*np.sqrt(25/TRADING_MIN_PER_YEAR))),4))
# Breakeven: stock has to move up by X so that call gains 2c (round-trip half-spread each side): about 2c/delta
print("stock move needed to cover a 2c round-trip spread: ~ $%.3f = %.3f bp of S" % (0.02/0.5, 0.02/0.5/766*1e4))
