import csv, statistics as st, datetime as dt
def load(fn):
    rows={}
    with open(fn) as f:
        r=csv.DictReader(f)
        for x in r:
            d=dt.datetime.strptime(x['DATE'],'%m/%d/%Y').date()
            rows[d]={k:float(v) for k,v in x.items() if k!='DATE'}
    return rows
vix=load('_cache/VIX_History.csv'); v1d=load('_cache/VIX1D_History.csv'); skew=load('_cache/SKEW_History.csv')
start=dt.date(2024,9,3); end=dt.date(2026,9,28)
days=[d for d in sorted(v1d) if start<=d<=end and d in vix]
print("Days in window:",len(days),days[0],days[-1])
oc=[v1d[d]['CLOSE']-v1d[d]['OPEN'] for d in days]
print("VIX1D close minus open: mean %.2f pts, median %.2f, share of days close>open %.1f%%"%(st.mean(oc),st.median(oc),100*sum(1 for x in oc if x>0)/len(oc)))
print("VIX1D mean OPEN %.2f, mean CLOSE %.2f; VIX mean CLOSE %.2f"%(st.mean(v1d[d]['OPEN'] for d in days),st.mean(v1d[d]['CLOSE'] for d in days),st.mean(vix[d]['CLOSE'] for d in days)))
ratio=[v1d[d]['CLOSE']/vix[d]['CLOSE'] for d in days]
print("VIX1D close / VIX close: mean %.2f, min %.2f, max %.2f"%(st.mean(ratio),min(ratio),max(ratio)))
ratio_open=[v1d[d]['OPEN']/vix[d]['OPEN'] for d in days]
print("VIX1D open / VIX open: mean %.2f, min %.2f, max %.2f"%(st.mean(ratio_open),min(ratio_open),max(ratio_open)))
# by year
for y in (2024,2025,2026):
    dd=[d for d in days if d.year==y]
    if dd: print(y,"n=%d mean VIX1D open %.2f close %.2f | VIX mean close %.2f"%(len(dd),st.mean(v1d[d]['OPEN'] for d in dd),st.mean(v1d[d]['CLOSE'] for d in dd),st.mean(vix[d]['CLOSE'] for d in dd)))
# IV rank of VIX itself (rolling 252) as illustration for last date
vd=sorted(vix); last=vd[-1]; win=[vix[d]['CLOSE'] for d in vd[-252:]]
cur=vix[last]['CLOSE']; lo,hi=min(win),max(win)
print("VIX last %s = %.2f; 52w low %.2f high %.2f => 'VIX rank' %.0f ; percentile %.0f%%"%(last,cur,lo,hi,100*(cur-lo)/(hi-lo),100*sum(1 for x in win if x<cur)/len(win)))
sd=sorted(skew); print("SKEW last",sd[-1],skew[sd[-1]]['SKEW'],"| mean SKEW in window %.1f, min %.1f max %.1f"%(st.mean(skew[d]['SKEW'] for d in days if d in skew),min(skew[d]['SKEW'] for d in days if d in skew),max(skew[d]['SKEW'] for d in days if d in skew)))
# number of days VIX1D open below 0.6*VIX open
print("Days VIX1D open < 0.6*VIX open: %d of %d"%(sum(1 for d in days if v1d[d]['OPEN']<0.6*vix[d]['OPEN']),len(days)))
