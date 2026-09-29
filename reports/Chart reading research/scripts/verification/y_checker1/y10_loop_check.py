# Independent second implementation of Y10: plain-Python loops, no pandas. Same data file.
import re, math
rows=[]
for ln in open('F-F_Research_Data_Factors.csv'):
    m=re.match(r'^\s*(\d{6})\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*$',ln)
    if m: rows.append((m.group(1), float(m.group(2)), float(m.group(5))))
    elif rows and 'Annual' in ln: break
ym=[r[0] for r in rows]; mkt=[(r[1]+r[2])/100 for r in rows]; rf=[r[2]/100 for r in rows]
n=len(rows); print("months:", n, ym[0], ym[-1])
# level index, base 1.0 before first month
lvl=[]; w=1.0
for r in mkt: w*=1+r; lvl.append(w)
sig=[None]*n
for t in range(9,n):
    sma=sum(lvl[t-9:t+1])/10
    sig[t]=lvl[t]>sma
ret_rule=[]; ret_bh=[]; idx=[]
for t in range(10,n):     # month t uses signal from t-1 (first signal at t=9 -> first position month t=10)
    inmkt=sig[t-1]
    ret_rule.append(mkt[t] if inmkt else rf[t]); ret_bh.append(mkt[t]); idx.append(t)
def cagr(r): 
    g=1.0
    for x in r: g*=1+x
    return g**(12/len(r))-1
def mdd(r):
    w=1.0; peak=1.0; worst=0.0
    for x in r:
        w*=1+x; peak=max(peak,w); worst=min(worst,w/peak-1)
    return worst
print("first position month:", ym[idx[0]], "n=",len(idx))
print("CAGR rule %.4f  B&H %.4f ; maxDD rule %.4f  B&H %.4f" % (cagr(ret_rule),cagr(ret_bh),mdd(ret_rule),mdd(ret_bh)))
# calendar years
from collections import defaultdict
yr_r=defaultdict(lambda:[1.0,1.0,0]); 
for k,t in enumerate(idx):
    y=ym[t][:4]; yr_r[y][0]*=1+ret_rule[k]; yr_r[y][1]*=1+ret_bh[k]; yr_r[y][2]+=1
full=[y for y,v in yr_r.items() if v[2]==12]
lag=sum(1 for y in full if yr_r[y][0]<yr_r[y][1]-1e-12); tie=sum(1 for y in full if abs(yr_r[y][0]-yr_r[y][1])<=1e-12)
print("full calendar years:",len(full),min(full),max(full)," rule lagged in",lag,"tied in",tie,"beat in",len(full)-lag-tie)
# Apr 2009 -> Aug 2026
g_rule=g_bh=1.0
for k,t in enumerate(idx):
    if ym[t]>='200904': g_rule*=1+ret_rule[k]; g_bh*=1+ret_bh[k]
print("Apr-2009..Aug-2026: rule $%.3f  B&H $%.3f"%(g_rule,g_bh))
# annual T-bill (RF) sanity: compare to the annual section of the file for 2025
