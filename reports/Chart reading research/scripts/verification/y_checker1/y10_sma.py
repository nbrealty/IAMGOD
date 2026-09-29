import sys
sys.path.insert(0,'.')
from ff_load import *

rows = load_monthly('F-F_Research_Data_Factors.csv')
df = pd.DataFrame(rows, columns=['ym','MktRF','SMB','HML','RF'])
df['ym'] = pd.PeriodIndex(df['ym'].astype(str), freq='M')
df = df.set_index('ym').astype(float)/1.0
r_m = (df['MktRF'] + df['RF'])/100.0   # total US market return, monthly (simple)
rf  = df['RF']/100.0

def stats(ret, label, rf_ser=None, verbose=True):
    n = len(ret)
    yrs = n/12.0
    wealth = (1+ret).cumprod()
    cagr = wealth.iloc[-1]**(1/yrs)-1
    vol = ret.std(ddof=1)*np.sqrt(12)
    ex = ret - (rf_ser.loc[ret.index] if rf_ser is not None else 0)
    sharpe = ex.mean()*12/(ex.std(ddof=1)*np.sqrt(12)) if rf_ser is not None else np.nan
    peak = wealth.cummax()
    dd = wealth/peak-1
    # include the starting value 1 as first peak
    w0 = pd.concat([pd.Series([1.0], index=[ret.index[0]-1]), wealth])
    dd0 = w0/w0.cummax()-1
    return dict(label=label, months=n, years=yrs, cagr=cagr, vol=vol, sharpe=sharpe, maxdd=dd0.min(),
                maxdd_date=str(dd0.idxmin()), final=wealth.iloc[-1])

def run(window=10, include_current=True, start_after=None, tag=''):
    # total-return index; base = 1.0 at end of 1926-06 (before first return month)
    lvl = (1+r_m).cumprod()
    lvl_with_base = pd.concat([pd.Series([1.0], index=[lvl.index[0]-1]), lvl])
    # SMA of the last `window` month-end levels (incl. current month-end). Base counts as an observation only if base_ok
    sma = lvl.rolling(window).mean()   # first available after `window` month-ends (Jul-1926 .. Apr-1927)
    sig = (lvl > sma)                  # True/False; NaN-> False when SMA not defined
    sig = sig.where(sma.notna())       # keep NaN for undefined
    pos = sig.shift(1)                 # signal at end of month t applied to month t+1
    out = pd.DataFrame({'mkt': r_m, 'rf': rf, 'pos': pos})
    out = out.dropna(subset=['pos'])
    out['pos'] = out['pos'].astype(bool)
    out['rule'] = np.where(out['pos'], out['mkt'], out['rf'])
    return out

o = run(10)
print("First return month with a position:", o.index[0], " last:", o.index[-1], " n=", len(o))
sr = stats(o['rule'], 'SMA10 rule', rf)
sb = stats(o['mkt'], 'Buy&hold', rf)
for s in (sr, sb):
    print({k:(round(v,4) if isinstance(v,float) else v) for k,v in s.items()})
print("Fraction of months invested:", o['pos'].mean().round(3))

# switches per year: count changes of pos
sw = (o['pos'] != o['pos'].shift(1)).sum()-1
print("switches:", sw, " per year:", round(sw/(len(o)/12),2))

# Calendar years: full years only (12 months of positions), compare compounded returns
o['yr'] = o.index.year
g = o.groupby('yr')
yr_ret = g.apply(lambda d: pd.Series({'n':len(d), 'rule':(1+d['rule']).prod()-1, 'bh':(1+d['mkt']).prod()-1}))
full = yr_ret[yr_ret['n']==12]
print("Full calendar years:", full.index.min(), "-", full.index.max(), " count:", len(full))
lag = (full['rule'] < full['bh'] - 1e-12).sum()
tie = ((full['rule'] - full['bh']).abs() <= 1e-12).sum()
lead = (full['rule'] > full['bh'] + 1e-12).sum()
print(f"rule < B&H in {lag} yrs; equal in {tie}; rule > B&H in {lead}")
print("partial years:", yr_ret[yr_ret['n']!=12].to_dict('index'))

# April 2009 -> Aug 2026
def window_growth(start_label):
    s = pd.Period(start_label, 'M')
    sub = o.loc[s:]
    return (1+sub['rule']).prod(), (1+sub['mkt']).prod(), len(sub), sub.index[0], sub.index[-1]
for lab in ['2009-04','2009-05']:
    print(lab, [round(x,3) if isinstance(x,float) else str(x) for x in window_growth(lab)])
