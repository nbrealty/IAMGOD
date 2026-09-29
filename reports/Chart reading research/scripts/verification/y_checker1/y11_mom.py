import sys, re
sys.path.insert(0,'.')
from ff_load import *

# --- momentum factor (monthly)
rows = load_monthly('F-F_Momentum_Factor.csv')
mom = pd.DataFrame(rows, columns=['ym','Mom'])
mom['ym'] = pd.PeriodIndex(mom['ym'].astype(str), freq='M')
mom = mom.set_index('ym').astype(float)['Mom']
print("Mom sample:", mom.index[0], mom.index[-1], len(mom), " missing codes:", int((mom<=-99).sum()))

def desc(x, label):
    n=len(x); m=x.mean(); s=x.std(ddof=1)
    t = m/(s/np.sqrt(n))
    geo = (1+x/100).prod()**(12/n)-1
    print(f"{label:38s} n={n:4d}  mean/mo={m:6.3f}%  arith ann={12*m:5.2f}%  geo ann={100*geo:5.2f}%  vol ann={s*np.sqrt(12):5.2f}%  t={t:5.2f}  Sharpe(no rf)={12*m/(s*np.sqrt(12)):.2f}")

desc(mom.loc[:'1993-02'], 'Mom 1927-01..1993-02')
desc(mom.loc['1993-03':], 'Mom 1993-03..2026-08')
desc(mom.loc[:'1992-12'], 'Mom 1927-01..1992-12  (alt split)')
desc(mom.loc['1993-01':], 'Mom 1993-01..2026-08  (alt split)')
desc(mom.loc['2000-01':], 'Mom 2000-01..2026-08')
desc(mom, 'Mom full')

# --- market (FF3) for compare
rows = load_monthly('F-F_Research_Data_Factors.csv')
ff = pd.DataFrame(rows, columns=['ym','MktRF','SMB','HML','RF'])
ff['ym'] = pd.PeriodIndex(ff['ym'].astype(str), freq='M')
ff = ff.set_index('ym').astype(float)
mkt = ff['MktRF']+ff['RF']

# --- decile file: first block = Value Weight Returns -- Monthly
with open('10_Portfolios_Prior_12_2.csv') as f:
    lines = f.read().splitlines()
# locate block starts
starts = [i for i,l in enumerate(lines) if re.search(r'Returns -- Monthly|Returns -- Annual|Number of Firms|Average Firm Size|Value-Weighted Average of Prior', l)]
print([ (i, lines[i].strip()) for i in starts])
i0 = starts[0]
blk = []
for l in lines[i0+1:]:
    m = re.match(r'^\s*(\d{6})\s*,(.*)$', l)
    if m: blk.append([m.group(1)] + [x.strip() for x in m.group(2).split(',')])
    elif blk and l.strip()=='' : break
    elif blk and not m: break
dec = pd.DataFrame(blk, columns=['ym']+[f'D{i}' for i in range(1,11)])
dec['ym'] = pd.PeriodIndex(dec['ym'].astype(str), freq='M')
dec = dec.set_index('ym').astype(float)
print("Decile VW block:", dec.index[0], dec.index[-1], len(dec), "missing:", int((dec<=-99).sum().sum()))
print(dec.tail(10).round(2).to_string())

def comp(x): return (1+x/100).prod()-1
jul_aug = ['2026-07','2026-08']
for lab, ser in [('Hi PRIOR (D10, VW)', dec['D10']), ('Lo PRIOR (D1, VW)', dec['D1']), ('Market Mkt-RF+RF', mkt), ('Mom factor', mom)]:
    sub = ser.loc['2026-07':'2026-08']
    print(f"{lab:22s} Jul-2026 {sub.iloc[0]:7.2f}%  Aug-2026 {sub.iloc[1]:7.2f}%  compounded Jul-Aug {100*comp(sub):7.2f}%")
# H1 2026
h1 = dec['D10'].loc['2026-01':'2026-06']
print("D10 H1 2026 compounded:", round(100*comp(h1),1), "%  |  market H1 2026:", round(100*comp(mkt.loc['2026-01':'2026-06']),1), "%")
# rank of Aug 2026 factor and Jul 2026 in history
print("Mom Jul 2026:", mom.loc['2026-07'], " Aug 2026:", mom.loc['2026-08'], " Jul+Aug compounded:", round(100*comp(mom.loc['2026-07':'2026-08']),2))
print("rank of Jul-Aug-2026 two-month Mom compounding among all overlapping 2-month windows:")
two = ((1+mom/100)*(1+mom.shift(1)/100)-1)*100
print(two.sort_values().head(8).round(2).to_string())
print("rank of Aug 2026 alone among 1-month Mom returns (1=worst):", int((mom < mom.loc['2026-08']).sum()+1), "of", len(mom))
print("rank of Jul 2026 alone among 1-month Mom returns (1=worst):", int((mom < mom.loc['2026-07']).sum()+1), "of", len(mom))
