from lib import *
# ---- monthly momentum data from Ken French
f = read_french_block(D+"F-F_Research_Data_Factors.csv", monthly=True)
mkt = f["Mkt-RF"] + f["RF"]; rf = f["RF"]
mom = read_french_block(D+"F-F_Momentum_Factor.csv", monthly=True)
mom.columns = ["Mom"]; mom = mom["Mom"]
vw = read_french_block(D+"10_Portfolios_Prior_12_2.csv", header_contains="Value Weight Returns -- Monthly", monthly=True)
ew = read_french_block(D+"10_Portfolios_Prior_12_2.csv", header_contains="Average Equal Weighted Returns -- Monthly", monthly=True)
print("Mom factor", mom.index[0].date(), mom.index[-1].date(), len(mom))
print("Deciles VW", vw.index[0].date(), vw.index[-1].date(), list(vw.columns)[:3], "...", "EW", ew.index[0].date(), ew.index[-1].date())

def per(r, a, b): return r.loc[a:b]

print("\n=== Momentum factor (long-short, Fama-French UMD/Mom), value-weighted, before any trading cost ===")
for name, (a,b) in {"1927-1993 (before Jegadeesh-Titman pub. Mar 1993)":("1927-01-01","1993-02-28"),
                    "1993.03-2026.08 (after publication)":("1993-03-01","2026-08-31"),
                    "2000-2026.08":("2000-01-01","2026-08-31"),
                    "2010-2026.08":("2010-01-01","2026-08-31"),
                    "2020-2026.08":("2020-01-01","2026-08-31"),
                    "1927-2026.08":("1927-01-01","2026-08-31")}.items():
    r = mom.loc[a:b]
    s = stats(r, None, 12, name)
    t = r.mean()/r.std()*np.sqrt(len(r))
    print(fmt(s), f" mean {r.mean()*1200:5.1f}%/yr  t={t:4.1f}")
print("\nWorst 12 months of Mom factor:")
print((mom.sort_values().head(12)*100).round(1).to_string())
print("\nMom by calendar year (%), 2015-2026(Aug):")
ym = (1+mom).groupby(mom.index.year).prod()-1
print((ym.loc[2015:2026]*100).round(1).to_string())

# drawdown of Mom since 2019
m2 = mom.loc["2019-01-01":]
eq = (1+m2).cumprod(); print("\nMom cumulative since 2019-01 (index=1 at start):"); print(eq.iloc[[0,12,24,36,48,60,72,-7,-6,-5,-4,-3,-2,-1]].round(3).to_string())
dd = eq/eq.cummax()-1
print("Mom max drawdown since 2019:", round(dd.min()*100,1), "at", dd.idxmin().date(), "; current drawdown (Aug 2026):", round(dd.iloc[-1]*100,1))

print("\n=== Long-only decile portfolios (Prior 12-2 return deciles): Hi = winners, Lo = losers; CRSP incl. delisted stocks, before trading costs ===")
for wname, W in (("VALUE-weighted", vw), ("EQUAL-weighted", ew)):
    print("\n--", wname)
    for name, (a,b) in {"1927-2026.08":("1927-01-01","2026-08-31"),"1927-1993.02":("1927-01-01","1993-02-28"),"1993.03-2026.08":("1993-03-01","2026-08-31"),"2013-2026.08":("2013-01-01","2026-08-31"),"2020-2026.08":("2020-01-01","2026-08-31")}.items():
        print(f"  [{name}]")
        for lab, r in (("Market", mkt), ("Hi PRIOR (top decile)", W["Hi PRIOR"]), ("PRIOR 9 (2nd decile)", W["PRIOR 9"]), ("Lo PRIOR (bottom decile)", W["Lo PRIOR"])):
            s = stats(r.loc[a:b], rf, 12, "   "+lab)
            print("  "+fmt(s))
print("\nTop-decile (VW) minus market, by calendar year (pts), 2015-2026:")
hi = vw["Hi PRIOR"]
yy = pd.DataFrame({"Mkt": (1+mkt).groupby(mkt.index.year).prod()-1, "HiVW": (1+hi).groupby(hi.index.year).prod()-1, "HiEW": (1+ew["Hi PRIOR"]).groupby(ew.index.year).prod()-1})
yy["HiVW-Mkt"] = yy["HiVW"]-yy["Mkt"]
print((yy.loc[2015:2026]*100).round(1).to_string())
print("Share of years top decile VW beat market (all years):", round((yy["HiVW-Mkt"]>0).mean(),3), " since 1993:", round((yy.loc[1993:,"HiVW-Mkt"]>0).mean(),3), " since 2013:", round((yy.loc[2013:,"HiVW-Mkt"]>0).mean(),3))

# long-only top decile + market trend filter (10m SMA of market): hold Hi decile if market above SMA10 else T-bills
idx = (1+mkt).cumprod(); sma = idx.rolling(10).mean(); pos = (idx>sma).astype(float).shift(1); pos[sma.shift(1).isna()] = np.nan
for cost in (0.0, 0.0020):
    for lab, W in (("VW",vw),("EW",ew)):
        r = pos*W["Hi PRIOR"] + (1-pos)*rf - pos.diff().abs().fillna(0)*cost
        r = r.where(pos.notna())
        for name,(a,b) in {"1927-2026.08":("1927-01-01","2026-08-31"),"1993.03-2026.08":("1993-03-01","2026-08-31"),"2013-2026.08":("2013-01-01","2026-08-31")}.items():
            s = stats(r.loc[a:b], rf, 12, f"Hi {lab} + mkt 10m filter, cost {cost*1e4:.0f}bp [{name}]")
            print(fmt(s))
