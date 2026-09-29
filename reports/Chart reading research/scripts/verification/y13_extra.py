import numpy as np, math, re, datetime as dt
rows=[]
with open("frenchdata/F-F_Research_Data_Factors_daily.csv") as f:
    for line in f:
        m = re.match(r"^\s*(\d{8})\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)", line)
        if m:
            d = dt.datetime.strptime(m.group(1), "%Y%m%d").date()
            rows.append((d, (float(m.group(2))+float(m.group(5)))/100.0))
dates=np.array([r[0] for r in rows]); mk=np.array([r[1] for r in rows])
def sel(y0,y1,excl=()):
    return np.array([(y0<=d.year<=y1 and d.year not in excl) for d in dates])
def rho1_idx(idx):
    # keep consecutive pairs only if both days in selection
    x=mk; ok=idx[1:]&idx[:-1]
    a=x[1:][ok]; b=x[:-1][ok]
    return float(np.corrcoef(a,b)[0,1]), int(ok.sum())
for y in range(2008,2027):
    r,n=rho1_idx(sel(y,y))
    print(y, f"{r:+.3f}", n)
print()
for lab,args in [("2010-2026",(2010,2026,())),("2010-2026 ex 2020",(2010,2026,(2020,))),("2010-2026 ex 2020,2025",(2010,2026,(2020,2025))),("2010-2019",(2010,2019,())),("2021-2026",(2021,2026,()))]:
    r,n=rho1_idx(sel(*args)); print(lab, f"{r:+.3f}", n)
# top-level: pre-2000 by half-decade for the window ranges
print()
for y0 in range(1926,2026,5):
    y1=min(y0+4,2026)
    r,n=rho1_idx(sel(y0,y1)); print(f"{y0}-{y1}", f"{r:+.3f}", n)
