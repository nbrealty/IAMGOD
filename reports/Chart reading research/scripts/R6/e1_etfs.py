from lib import *
import warnings; warnings.filterwarnings("ignore")
tick = ["SPY","QQQ","MTUM","SPMO","QMOM","FFTY","DBMF","KMLM","CTA"]
px = {t: load_yahoo(t)["adjclose"] for t in tick}
# annual returns (calendar), 2026 = to last date
tab = {}
for t, s in px.items():
    yr = s.groupby(s.index.year).last()
    first = s.groupby(s.index.year).first()
    prev_end = yr.shift(1)
    r = yr/prev_end - 1
    # first year partial: from first available price
    r.iloc[0] = yr.iloc[0]/first.iloc[0]-1
    tab[t] = r
T = pd.DataFrame(tab).loc[2013:2026]*100
print("Calendar-year total returns % (Yahoo adjusted close; first year partial from first trading day; 2026 = to 2026-09-28)")
print(T.round(1).to_string())
print()
for t, s in px.items():
    yrs = (s.index[-1]-s.index[0]).days/365.25
    cagr = (s.iloc[-1]/s.iloc[0])**(1/yrs)-1
    r = s.pct_change().dropna()
    dd = (s/s.cummax()-1).min()
    print(f"{t:5s} {s.index[0].date()} -> {s.index[-1].date()}  CAGR {cagr*100:5.1f}%  vol {r.std()*np.sqrt(252)*100:5.1f}%  maxDD {dd*100:6.1f}%")
# relative to SPY over each ETF's own life
print()
for t in ["MTUM","SPMO","QMOM","FFTY","DBMF","KMLM","CTA","QQQ"]:
    s = px[t]; b = px["SPY"].reindex(s.index).ffill()
    rel = (s/s.iloc[0])/(b/b.iloc[0])
    print(f"{t:5s} growth of $1: {s.iloc[-1]/s.iloc[0]:.2f}x vs SPY {b.iloc[-1]/b.iloc[0]:.2f}x  (ratio {rel.iloc[-1]:.2f})")
