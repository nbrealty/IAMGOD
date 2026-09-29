# Cross-check of Y10 and Y13 with a different code path (pandas vectorised) to rule out loop/indexing bugs.
import pandas as pd, numpy as np, io, re

# ---- Y13 daily
rows=[]
for line in open("frenchdata/F-F_Research_Data_Factors_daily.csv"):
    m=re.match(r"^\s*(\d{8})\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)",line)
    if m: rows.append((m.group(1),float(m.group(2)),float(m.group(5))))
d=pd.DataFrame(rows,columns=["date","mktrf","rf"]); d["date"]=pd.to_datetime(d["date"],format="%Y%m%d")
d["mkt"]=(d.mktrf+d.rf)/100; d=d.set_index("date")
for a,b in [("1946","1969"),("1970","1989"),("2010","2026"),("2010","2019"),("2020","2026"),("1990","1999"),("1926","1999")]:
    s=d.loc[a:b,"mkt"]
    print(f"pandas autocorr {a}-{b}: {s.autocorr(1):+.3f}  n={len(s)}")

# ---- Y10 monthly (vectorised)
rows=[]
for line in open("frenchdata/F-F_Research_Data_Factors.csv"):
    m=re.match(r"^\s*(\d{6})\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)",line)
    if m: rows.append((m.group(1),float(m.group(2)),float(m.group(5))))
    elif rows and not m: break
mth=pd.DataFrame(rows,columns=["ym","mktrf","rf"]); mth["ym"]=pd.PeriodIndex(mth["ym"],freq="M"); mth=mth.set_index("ym")
mth["mkt"]=(mth.mktrf+mth.rf)/100; mth["rf"]=mth.rf/100
lvl=(1+mth.mkt).cumprod()
sma=lvl.rolling(10).mean()
sig=(lvl>sma)                     # signal known at end of month t
pos=sig.shift(1)                  # applied to month t+1 => shift by one month
pos=pos.dropna().astype(bool)
r=pd.Series(np.where(pos, mth.mkt.loc[pos.index], mth.rf.loc[pos.index]), index=pos.index)
b=mth.mkt.loc[pos.index]
n=len(r); cagr=lambda x:(1+x).prod()**(12/len(x))-1
dd=lambda x:((1+x).cumprod()/(1+x).cumprod().cummax()-1).min()
print(f"\nvectorised rule: start {r.index[0]} end {r.index[-1]} n={n}: rule CAGR {cagr(r)*100:.2f}% maxDD {dd(r)*100:.1f}% | B&H CAGR {cagr(b)*100:.2f}% maxDD {dd(b)*100:.1f}%")
yr=pd.DataFrame({"rule":r,"bh":b}); yr["y"]=yr.index.year
g=yr.groupby("y").apply(lambda z: pd.Series({"rule":(1+z.rule).prod()-1,"bh":(1+z.bh).prod()-1,"n":len(z)}),include_groups=False)
full=g[g.n==12]; print("full years:",len(full),"rule lagged B&H:", int((full.rule<full.bh).sum()))
sub=yr.loc["2009-04":]
print("Apr-2009..Aug-2026: rule $%.2f  B&H $%.2f" % ((1+sub.rule).prod(), (1+sub.bh).prod()))
