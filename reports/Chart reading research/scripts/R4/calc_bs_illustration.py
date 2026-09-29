# Illustrative Black-Scholes numbers for a SPY-like underlying. My own arithmetic, not market quotes.
import math
def N(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
def n(x): return math.exp(-0.5*x*x)/math.sqrt(2*math.pi)
def bs_call(S,K,T,sig,r=0.04,q=0.012):
    if T<=0: return max(S-K,0),0,0,0
    d1=(math.log(S/K)+(r-q+0.5*sig*sig)*T)/(sig*math.sqrt(T)); d2=d1-sig*math.sqrt(T)
    price=S*math.exp(-q*T)*N(d1)-K*math.exp(-r*T)*N(d2)
    delta=math.exp(-q*T)*N(d1)
    gamma=math.exp(-q*T)*n(d1)/(S*sig*math.sqrt(T))
    theta_year=-(S*math.exp(-q*T)*n(d1)*sig)/(2*math.sqrt(T)) - r*K*math.exp(-r*T)*N(d2) + q*S*math.exp(-q*T)*N(d1)
    return price,delta,gamma,theta_year
S=766.0; sig=0.15
print("Underlying S=%.0f, flat IV=%.0f%%. 'T' in trading time: 252 days x 6.5 hours."%(S,sig*100))
hrs_per_year=252*6.5
print("\nA) ATM call, time left -> premium, gamma, and how much a 1-cent half-spread is, in % of premium and in bps of delta exposure")
print("%-16s %8s %8s %10s %14s %16s"%("time left","premium","delta","gamma/$1","1c as % prem","1c as bps expo"))
for label,hrs in [("6.5 h (open)",6.5),("3 h",3),("1 h",1),("30 min",0.5),("25 min",25/60)]:
    T=hrs/hrs_per_year
    p,d,g,th=bs_call(S,S,T,sig)
    print("%-16s %8.2f %8.3f %10.4f %13.2f%% %15.2f"%(label,p,d,g,100*0.01/p, 1e4*0.01/(d*S)))
print("\nB) Longer-dated ATM call (calendar days / 365)")
for days in [1,7,14,30]:
    T=days/365
    p,d,g,th=bs_call(S,S,T,sig)
    print("%2d DTE: premium %.2f, delta %.3f, gamma %.4f, theta/day %.3f (%.2f%% of premium/day), 1c as %% of prem %.2f%%, 1c as bps of exposure %.2f"%(days,p,d,g,th/365,100*(th/365)/p,100*0.01/p,1e4*0.01/(d*S)))
print("\nC) Ratio of ATM gamma: 1 hour left vs 1 month (30 calendar days) left")
g1=bs_call(S,S,1/hrs_per_year,sig)[2]; g30=bs_call(S,S,30/365,sig)[2]
print("gamma(1h)/gamma(30d) = %.1f (Dim, Eraker, Vilkov quote about 25 for IV 20%%)"%(g1/g30))
print("\nD) Debit vertical (call spread), 7 and 14 DTE: long ATM call, short call $5 above; 4 half-spreads of 1c for in+out")
for days in [7,14]:
    T=days/365
    p1,d1,g1_,th1=bs_call(S,S,T,sig); p2,d2,g2_,th2=bs_call(S,S+5,T,sig)
    debit=p1-p2; ndelta=d1-d2
    cost=0.04   # two legs in, two legs out, 1 cent half-spread each (if each leg quoted 2c wide)
    print("%d DTE: debit %.2f (=max loss per share), net delta %.3f, exposure $%.0f, 4 half-spreads=$%.2f = %.2f%% of debit = %.2f bps of delta exposure"%(days,debit,ndelta,ndelta*S,cost,100*cost/debit,1e4*cost/(ndelta*S)))
print("\nE) Expected 1-sd move of SPY in 25 minutes at 15%% IV: $%.2f (%.1f bps); SPY share round-trip cost at 1.5 bps/side (repo 'realistic') = %.1f bps"%(S*sig*math.sqrt(25/60/hrs_per_year), 1e4*sig*math.sqrt(25/60/hrs_per_year), 3.0))
