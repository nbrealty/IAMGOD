import sys
sys.path.insert(0,'.')
from ff_load import *
rows = load_daily('F-F_Research_Data_Factors_daily.csv')
d = pd.DataFrame(rows, columns=['date','MktRF','SMB','HML','RF'])
d['date'] = pd.to_datetime(d['date'], format='%Y%m%d')
d = d.set_index('date').astype(float)
print("daily obs:", len(d), d.index[0].date(), d.index[-1].date(), " missing codes:", int((d<=-99).any(axis=1).sum()))
r = (d['MktRF'] + d['RF'])/100.0     # total market simple return
def rho1(x):
    x = np.asarray(x, float)
    # (a) Pearson corr of consecutive pairs inside the window
    a = np.corrcoef(x[1:], x[:-1])[0,1]
    # (b) sample ACF with global mean & full denominator
    xm = x - x.mean()
    b = (xm[1:]*xm[:-1]).sum()/(xm**2).sum()
    return a, b, len(x)
def show(label, x):
    a,b,n = rho1(x)
    print(f"{label:28s} N={n:6d}  rho1 (pairs)={a:+.3f}  rho1 (ACF)={b:+.3f}  approx t={a*np.sqrt(n):+.1f}")
print("\n--- by calendar decade")
for lo, hi in [(1926,1929),(1930,1939),(1940,1949),(1950,1959),(1960,1969),(1970,1979),(1980,1989),(1990,1999),(2000,2009),(2010,2019),(2020,2026)]:
    sub = r.loc[f'{lo}-01-01':f'{hi}-12-31']
    show(f"{lo}-{hi}", sub)
print("\n--- the eras quoted in the report R5")
for lo, hi in [(1946,1969),(1970,1989),(1990,2009),(2010,2026),(2016,2026)]:
    show(f"{lo}-{hi}", r.loc[f'{lo}-01-01':f'{hi}-12-31'])
print("\n--- other useful windows")
for lo, hi in [(1926,2026),(1926,1999),(1952,1999),(1980,1999),(2000,2026),(2010,2019),(2020,2026),(2021,2026)]:
    show(f"{lo}-{hi}", r.loc[f'{lo}-01-01':f'{hi}-12-31'])
# excess return (Mkt-RF) instead of total -- check tiny difference
print("\n--- using Mkt-RF (excess) instead of total")
for lo, hi in [(1946,1969),(1970,1989),(1990,2009),(2010,2026)]:
    show(f"{lo}-{hi} (Mkt-RF)", (d['MktRF']/100).loc[f'{lo}-01-01':f'{hi}-12-31'])
