import sys
sys.path.insert(0,'.')
from ff_load import *
rows = load_monthly('F-F_Research_Data_Factors.csv')
df = pd.DataFrame(rows, columns=['ym','MktRF','SMB','HML','RF'])
df['ym'] = pd.PeriodIndex(df['ym'].astype(str), freq='M')
df = df.set_index('ym').astype(float)
r_m = (df['MktRF'] + df['RF'])/100.0
rf  = df['RF']/100.0

def cagr(x): return (1+x).prod()**(12/len(x))-1
def mdd(x):
    w = pd.concat([pd.Series([1.0], index=[x.index[0]-1]), (1+x).cumprod()])
    return (w/w.cummax()-1).min()

lvl = (1+r_m).cumprod()
base = pd.concat([pd.Series([1.0], index=[lvl.index[0]-1]), lvl])   # includes end-Jun-1926 base = 1
variants = {}
# V1: main -- 10 month-end levels from Jul-1926 on, incl. current, signal shifts one month
sma1 = lvl.rolling(10).mean(); sig1 = (lvl>sma1).where(sma1.notna())
variants['V1 main: SMA of last 10 month-end levels incl. current; base not used'] = sig1.shift(1)
# V2: base level counted as a month-end observation
sma2 = base.rolling(10).mean(); sig2 = (base>sma2).where(sma2.notna()).iloc[1:]
variants['V2 same but end-Jun-1926 base=1 counted as an observation'] = sig2.shift(1)
# V3: signal "price > SMA" where SMA uses 10 levels excluding current (i.e., prior 10)
sma3 = lvl.shift(1).rolling(10).mean(); sig3 = (lvl>sma3).where(sma3.notna())
variants['V3 SMA of the 10 PRIOR month-ends, compare to current'] = sig3.shift(1)
# V4: signal >= (ties as invested) -- irrelevant but check
sig4 = (lvl>=sma1).where(sma1.notna())
variants['V4 main with >= instead of >'] = sig4.shift(1)
# V5: no lag (look-ahead; NOT valid, just to show the size of the timing effect)
variants['V5 (INVALID look-ahead: signal applied to same month)'] = sig1
for k, s in variants.items():
    d = pd.DataFrame({'m':r_m,'rf':rf,'pos':s}).dropna(subset=['pos'])
    rule = np.where(d['pos'].astype(bool), d['m'], d['rf'])
    rule = pd.Series(rule, index=d.index)
    print(f"{k}\n   first={d.index[0]} n={len(d)} rule CAGR={cagr(rule):.4%} B&H CAGR={cagr(d['m']):.4%}  rule maxDD={mdd(rule):.2%} B&H maxDD={mdd(d['m']):.2%}")
    d['yr']=d.index.year
    yy = d.assign(rule=rule).groupby('yr').apply(lambda g: pd.Series({'n':len(g),'rule':(1+g['rule']).prod()-1,'bh':(1+g['m']).prod()-1}))
    yy = yy[yy['n']==12]
    print(f"   full yrs={len(yy)}; rule<B&H {int((yy['rule']<yy['bh']-1e-12).sum())}; rule>B&H {int((yy['rule']>yy['bh']+1e-12).sum())}")
    sub = pd.DataFrame({'rule':rule,'m':d['m']}).loc['2009-04':]
    print(f"   Apr-2009->Aug-2026: rule ${ (1+sub['rule']).prod():.3f}  B&H ${(1+sub['m']).prod():.3f}")
