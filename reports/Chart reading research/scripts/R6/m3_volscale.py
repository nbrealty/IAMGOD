from lib import *
fd = read_french_block(D+"F-F_Research_Data_Factors_daily.csv", monthly=False)
md = read_french_block(D+"F-F_Momentum_Factor_daily.csv", monthly=False); md.columns=["Mom"]
fm = read_french_block(D+"F-F_Research_Data_Factors.csv", monthly=True)
mkt_m = fm["Mkt-RF"]+fm["RF"]; rf_m = fm["RF"]
# realized variance by month from daily market excess returns
ex_d = fd["Mkt-RF"]
rv = (ex_d**2).groupby(ex_d.index.to_period("M")).sum()   # sum of squared daily excess returns (Moreira-Muir style)
rv.index = rv.index.to_timestamp("M")
rv = rv.reindex(mkt_m.index)
# ---- (1) long-only, no-leverage volatility targeting on the market
def volmanaged(target_ann, cap=1.0, cost=0.0):
    sig_prev = np.sqrt(rv.shift(1)*12)   # annualised realized vol of previous month (approx)
    w = (target_ann/sig_prev).clip(upper=cap)
    r = w*mkt_m + (1-w)*rf_m
    r = r - w.diff().abs().fillna(0)*cost
    return r.where(w.notna()), w
print("=== Volatility-managed US market, long-only (weight = min(1, target vol / last month's realized vol)), monthly, Ken French data ===")
for tgt in (0.10, 0.15):
    for cost in (0.0, 0.0005):
        r, w = volmanaged(tgt, 1.0, cost)
        for nm,(a,b) in {"1927-2026.08":("1927-02-01","2026-08-31"),"1927-1972":("1927-02-01","1972-12-31"),"1973-2012":("1973-01-01","2012-12-31"),"2013-2026.08":("2013-01-01","2026-08-31"),"2020-2026.08":("2020-01-01","2026-08-31")}.items():
            print(fmt(stats(r.loc[a:b], rf_m, 12, f"target {tgt*100:.0f}% cost {cost*1e4:.0f}bp/turn [{nm}]")), f" avg weight {w.loc[a:b].mean():.2f}")
        if tgt==0.10 and cost==0.0:
            bh = stats(mkt_m.loc["1927-02-01":"2026-08-31"], rf_m, 12, "B&H 1927-2026.08"); print(fmt(bh))
            for nm,(a,b) in {"1927-1972":("1927-02-01","1972-12-31"),"1973-2012":("1973-01-01","2012-12-31"),"2013-2026.08":("2013-01-01","2026-08-31"),"2020-2026.08":("2020-01-01","2026-08-31")}.items():
                print(fmt(stats(mkt_m.loc[a:b], rf_m, 12, f"B&H [{nm}]")))
# ---- (2) Moreira-Muir original: f = c/RV_{t-1} * excess return, c set so full-sample vol equals B&H (look-ahead in c!), leverage allowed
c_look = None
exm = fm["Mkt-RF"]
raw = exm/rv.shift(1)
c_look = exm.loc["1927-02-01":].std()/raw.loc["1927-02-01":].std()
mm = c_look*raw
print("\nMoreira-Muir style (leverage allowed, c fixed with look-ahead): Sharpe of excess return:")
for nm,(a,b) in {"1927-2026.08":("1927-02-01","2026-08-31"),"1927-1972":("1927-02-01","1972-12-31"),"1973-2012":("1973-01-01","2012-12-31"),"2013-2026.08":("2013-01-01","2026-08-31")}.items():
    m1 = mm.loc[a:b].dropna(); m0 = exm.loc[m1.index]
    print(f"  [{nm}] managed Sharpe {m1.mean()/m1.std()*np.sqrt(12):.2f} vs B&H {m0.mean()/m0.std()*np.sqrt(12):.2f}; max weight {(c_look/rv.shift(1)).loc[a:b].max():.1f}x, months with weight>2x: {(c_look/rv.shift(1)).loc[a:b].gt(2).sum()}")
# expanding-window c (real time)
c_rt = []
vals = []
r_ = raw.dropna()
cs = pd.Series(index=r_.index, dtype=float)
for i, t in enumerate(r_.index):
    if i < 60: continue
    hist = r_.iloc[:i]      # information up to t-1 only
    exh = exm.loc[hist.index]
    cs.loc[t] = exh.std()/hist.std()
mm_rt = (cs*r_).dropna()
print("Real-time expanding-window c (no look-ahead in c), leverage allowed:")
for nm,(a,b) in {"1932-2026.08":("1932-01-01","2026-08-31"),"1973-2012":("1973-01-01","2012-12-31"),"2013-2026.08":("2013-01-01","2026-08-31")}.items():
    m1 = mm_rt.loc[a:b]; m0 = exm.loc[m1.index]
    print(f"  [{nm}] managed Sharpe {m1.mean()/m1.std()*np.sqrt(12):.2f} vs B&H {m0.mean()/m0.std()*np.sqrt(12):.2f}")

# ---- (3) Barroso & Santa-Clara style vol-scaled momentum using daily Mom factor
print("\n=== Momentum (Mom factor) scaled by inverse of trailing 126-day realized vol, target 12% ann.; scale capped at 2x ===")
mom_d = md["Mom"].dropna()
vol126 = mom_d.rolling(126).std()*np.sqrt(252)
# monthly: scale for month t determined by the last day of month t-1
mom_m = read_french_block(D+"F-F_Momentum_Factor.csv", monthly=True); mom_m.columns=["Mom"]; mom_m = mom_m["Mom"]
vol_me = vol126.groupby(vol126.index.to_period("M")).last(); vol_me.index = vol_me.index.to_timestamp("M")
scale = (0.12/vol_me.shift(1)).clip(upper=2.0)
scaled = (scale*mom_m).dropna()
for nm,(a,b) in {"1930-2026.08":("1930-01-01","2026-08-31"),"1930-1993.02":("1930-01-01","1993-02-28"),"1993.03-2026.08":("1993-03-01","2026-08-31"),"2010-2026.08":("2010-01-01","2026-08-31"),"2020-2026.08":("2020-01-01","2026-08-31")}.items():
    print(fmt(stats(mom_m.loc[scaled.loc[a:b].index], None, 12, f"Mom raw [{nm}]")))
    print(fmt(stats(scaled.loc[a:b], None, 12, f"Mom vol-scaled [{nm}]")))
print("\nJuly/August 2026 and 2009 for raw vs scaled:")
tmp = pd.DataFrame({"raw":mom_m, "scale":scale, "scaled":scaled}).loc[["2009-03-31","2009-04-30","2009-05-31","2023-01-31","2026-05-31","2026-06-30","2026-07-31","2026-08-31"]]
print((tmp).round(3).to_string())
