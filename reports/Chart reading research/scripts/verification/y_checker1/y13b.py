import sys
sys.path.insert(0,'.')
from ff_load import *
rows = load_daily('F-F_Research_Data_Factors_daily.csv')
d = pd.DataFrame(rows, columns=['date','MktRF','SMB','HML','RF'])
d['date'] = pd.to_datetime(d['date'], format='%Y%m%d'); d = d.set_index('date').astype(float)
r = (d['MktRF'] + d['RF'])/100.0
def rho(x): 
    x=np.asarray(x,float); return np.corrcoef(x[1:],x[:-1])[0,1], len(x)
print("2010-2026 all:", rho(r.loc['2010':'2026']))
ex2020 = r.loc['2010':'2026']; ex2020 = ex2020[ex2020.index.year!=2020]
print("2010-2026 excluding calendar 2020 (pairs across the gap are slightly off):", rho(ex2020))
# proper: drop 2020 by computing lag within each other year then pooling
def pooled(years):
    num=0; den=0; xs=[]; ys=[]
    for y in years:
        x=r.loc[str(y)].values; xs.append(x[1:]); ys.append(x[:-1])
    xs=np.concatenate(xs); ys=np.concatenate(ys); return np.corrcoef(xs,ys)[0,1], len(xs)
print("2010-2026 excluding 2020 (within-year pairs only):", pooled([y for y in range(2010,2027) if y!=2020]))
print("\nYear by year rho1 since 2000 (single-year estimates are noisy, se ~0.063):")
for y in range(2000, 2027):
    a,n = rho(r.loc[str(y)]); print(y, f"{a:+.3f} (N={n})", end=' | ')
print()
print("\nRolling 5-yr windows (non-overlapping):")
for lo in range(1926, 2026, 5):
    hi = min(lo+4, 2026)
    a,n = rho(r.loc[f'{lo}':f'{hi}']); print(f"{lo}-{hi}: {a:+.3f} (N={n})", end='  ')
print()
# Robustness: Mkt-RF only for a Newey-West-like t (block bootstrap) for eras
rng = np.random.default_rng(1)
def block_boot_rho(x, block=60, B=2000):
    x=np.asarray(x); n=len(x); nb=int(np.ceil(n/block)); out=[]
    for _ in range(B):
        starts = rng.integers(0, n-block, size=nb)
        xb = np.concatenate([x[s:s+block] for s in starts])[:n]
        out.append(np.corrcoef(xb[1:], xb[:-1])[0,1])
    return np.percentile(out,[2.5,97.5])
for lo,hi in [(1946,1969),(1970,1989),(1990,2009),(2010,2026)]:
    x = r.loc[f'{lo}':f'{hi}'].values
    print(lo,hi, "rho1=%+.3f"%rho(x)[0], "block-bootstrap 95%% CI (60-day blocks): [%+.3f, %+.3f]"%tuple(block_boot_rho(x)))
