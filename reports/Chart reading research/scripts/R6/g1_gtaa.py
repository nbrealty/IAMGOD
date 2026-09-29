from lib import *
import warnings; warnings.filterwarnings("ignore")
T = ["SPY","EFA","IEF","VNQ","DBC","SHY"]
px = {t: load_yahoo(t)["adjclose"] for t in T}
m = pd.DataFrame({t: s.groupby(s.index.to_period("M")).last() for t, s in px.items()})
m.index = m.index.to_timestamp("M")
m = m.loc[:"2026-08-31"]
ret = m.pct_change()
assets = ["SPY","EFA","IEF","VNQ","DBC"]
sma = m[assets].rolling(10).mean()
sig = (m[assets] > sma).astype(float).where(sma.notna())
pos = sig.shift(1)
start = "2007-01-31"
def run(cost):
    sleeve = pos*ret[assets] + (1-pos)*ret[["SHY"]].values
    turn = pos.diff().abs().fillna(0)
    sleeve = sleeve - turn*cost
    return sleeve.mean(axis=1).loc[start:]
bh = ret[assets].mean(axis=1).loc[start:]
spy = ret["SPY"].loc[start:]
sixty = (0.6*ret["SPY"]+0.4*ret["IEF"]).loc[start:]
rf = ret["SHY"].loc[start:]
periods = {"2007.01-2026.08":(start,"2026-08-31"), "2007-2012":("2007-01-01","2012-12-31"), "2013-2019":("2013-01-01","2019-12-31"), "2020-2026.08":("2020-01-01","2026-08-31"), "2022 only":("2022-01-01","2022-12-31")}
for nm,(a,b) in periods.items():
    print(f"\n[{nm}]")
    for lab, r in (("GTAA-5 10m SMA (cost 0)", run(0.0)), ("GTAA-5 10m SMA (cost 10bp/switch)", run(0.001)), ("Equal-weight 5 assets buy&hold (monthly rebal.)", bh), ("SPY buy&hold", spy), ("60/40 SPY/IEF", sixty)):
        print(fmt(stats(r.loc[a:b], rf, 12, lab)))
p = pos.loc[start:].dropna()
print("\nInvested share by asset:", (p.mean()*100).round(0).to_dict(), " avg number of sleeve switches per year:", round(p.diff().abs().sum().sum()/(len(p)/12),1))
yr = pd.DataFrame({"GTAA": (1+run(0.001)).groupby(run(0.001).index.year).prod()-1, "EW B&H": (1+bh).groupby(bh.index.year).prod()-1, "SPY": (1+spy).groupby(spy.index.year).prod()-1, "60/40": (1+sixty).groupby(sixty.index.year).prod()-1})
print((yr*100).round(1).loc[2015:].to_string())
