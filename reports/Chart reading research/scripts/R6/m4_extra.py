from lib import *
import sys
sys.argv=["x","5"]
exec(open("d1_daily.py").read().split("for sym, start in")[0])
# ---- (1) relative performance of 10m SMA vs buy&hold on US market (French monthly): longest "lagging" spell
f = read_french_block(D+"F-F_Research_Data_Factors.csv", monthly=True)
mkt = f["Mkt-RF"]+f["RF"]; rf = f["RF"]
idx = (1+mkt).cumprod(); sma = idx.rolling(10).mean(); pos = (idx>sma).astype(float).shift(1); pos[sma.shift(1).isna()] = np.nan
tim = (pos*mkt+(1-pos)*rf).where(pos.notna())
w_t = (1+tim.dropna()).cumprod(); w_b = (1+mkt.loc[w_t.index]).cumprod()
ratio = w_t/w_b
peak = ratio.cummax(); rel_dd = ratio/peak-1
print("Timing/BH wealth ratio: worst relative drawdown", round(rel_dd.min()*100,1), "% at", rel_dd.idxmin().date())
# longest spell below prior ratio peak
uw = (ratio < peak); longest=0; cur=0; cs=None; best=None
for t,v in uw.items():
    if v:
        if cur==0: cs=t
        cur+=1
        if cur>longest: longest=cur; best=(cs,t)
    else: cur=0
print("Longest spell when timing wealth was below its best relative level vs BH:", longest/12, "years", best[0].date(), "->", best[1].date())
print("Final wealth ratio timing/BH (1927.. 2026.08):", round(ratio.iloc[-1],3), " BH final $ per $1:", round(w_b.iloc[-1],0), " timing:", round(w_t.iloc[-1],0))
# since 2009-03
r2 = ratio.loc["2009-03-31":]; print("Ratio timing/BH since Mar 2009:", round(r2.iloc[-1]/r2.iloc[0],3))
r3 = ratio.loc["1994-12-31":"2000-03-31"]; print("Ratio timing/BH Dec 1994..Mar 2000:", round(r3.iloc[-1]/r3.iloc[0],3))
# calendar years: below/equal/above
ann = pd.DataFrame({"BH": (1+mkt).groupby(mkt.index.year).prod()-1, "T": (1+tim.dropna()).groupby(tim.dropna().index.year).prod()-1}).dropna()
ann = ann.loc[1928:2025]
d = ann["T"]-ann["BH"]
print("Calendar years 1928-2025: timing beat BH by >0.5pt:", (d>0.005).sum(), "| within +-0.5pt:", (d.abs()<=0.005).sum(), "| lagged by >0.5pt:", (d<-0.005).sum(), "of", len(d))
print("Median lag in years when it lagged (pts):", round(d[d<-0.005].median()*100,1), " median gain when it beat:", round(d[d>0.005].median()*100,1))
# spells lengths
p = pos.dropna(); spells=[]; cur=0
for v in p.values:
    if v==1: cur+=1
    else:
        if cur>0: spells.append(cur); cur=0
if cur>0: spells.append(cur)
spells=np.array(spells); print("Number of in-market spells:", len(spells), " share lasting >12 months:", round((spells>12).mean(),2), " median months:", np.median(spells))
# ---- (2) Signal switch dates for SPY rules A,B,C in 2025-2026 and 2022
df = prep("SPY").loc[:END]
rules = {"A 200d": sma_flag(df,200), "B 30w": weekly_flag(df,30), "C 10m": monthly_flag(df,10)}
for name, sig in rules.items():
    s = sig.dropna()
    ch = s[s.diff().fillna(0)!=0]
    print(f"\nSPY {name}: signal changes (close date -> new state) from 2021-12 to 2026-08")
    for t,v in ch.loc["2021-12-01":].items():
        print("   ", t.date(), "ON " if v==1 else "OFF", f"SPY adj close {df.loc[t,'adjclose']:.2f}")
