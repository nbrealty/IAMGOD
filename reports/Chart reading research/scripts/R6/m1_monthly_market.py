from lib import *
f = read_french_block(D+"F-F_Research_Data_Factors.csv", monthly=True)
f = f[["Mkt-RF","RF"]]
mkt = f["Mkt-RF"] + f["RF"]   # total market return
rf = f["RF"]
print("Monthly data:", f.index[0].date(), "->", f.index[-1].date(), len(f))

def sma_rule(mkt, rf, n, cost=0.0):
    idx = (1 + mkt).cumprod()
    sma = idx.rolling(n).mean()
    sig = (idx > sma).astype(float)
    sig[sma.isna()] = np.nan
    pos = sig.shift(1)   # signal at end of month t -> position during month t+1
    ret = pos * mkt + (1 - pos) * rf
    turn = pos.diff().abs().fillna(0)
    ret = ret - turn * cost
    return ret.where(pos.notna()), pos

def tsmom_rule(mkt, rf, n, cost=0.0):
    ex = mkt - rf
    lookback = (1 + ex).rolling(n).apply(np.prod, raw=True) - 1
    sig = (lookback > 0).astype(float); sig[lookback.isna()] = np.nan
    pos = sig.shift(1)
    ret = pos * mkt + (1 - pos) * rf
    turn = pos.diff().abs().fillna(0)
    ret = ret - turn * cost
    return ret.where(pos.notna()), pos

periods = {"1927-2026.08 (all)": ("1927-01-01","2026-08-31"),
           "1927-1972": ("1927-01-01","1972-12-31"),
           "1973-2012 (Faber sample)": ("1973-01-01","2012-12-31"),
           "2007-2026.08 (after Faber pub)": ("2007-01-01","2026-08-31"),
           "2013-2026.08": ("2013-01-01","2026-08-31"),
           "2000-2009": ("2000-01-01","2009-12-31"),
           "2020-2026.08": ("2020-01-01","2026-08-31")}

for cost in (0.0, 0.0010):
    print(f"\n######## cost per switch = {cost*1e4:.0f} bps (one-way, applied to each change in position)")
    strat = {}
    strat["Buy&hold US market"] = mkt
    r10, p10 = sma_rule(mkt, rf, 10, cost); strat["10-month SMA (Faber)"] = r10
    r12, p12 = tsmom_rule(mkt, rf, 12, cost); strat["12-month TSMOM (excess>0)"] = r12
    for n in (6, 8, 12):
        rr, _ = sma_rule(mkt, rf, n, cost); strat[f"{n}-month SMA"] = rr
    for pname, (a, b) in periods.items():
        print(f"\n--- {pname}")
        for k, r in strat.items():
            rr = r.loc[a:b]
            s = stats(rr, rf, 12, k)
            print(fmt(s))
    # switches per year
    for k, p in (("10m SMA", p10), ("12m TSMOM", p12)):
        pp = p.dropna()
        sw = pp.diff().abs().sum()
        yrs = len(pp)/12
        print(f"{k}: position changes {sw:.0f} in {yrs:.1f} years = {sw/yrs:.2f}/yr ({sw/yrs/2:.2f} round trips/yr); invested {pp.mean()*100:.0f}% of months")
    if cost == 0.0:
        # annual table 2018-2026
        yr = pd.DataFrame({k: (1+v).groupby(v.index.year).prod() - 1 for k, v in strat.items() if k in ("Buy&hold US market","10-month SMA (Faber)","12-month TSMOM (excess>0)")})
        print("\nCalendar-year returns (%)"); print((yr.loc[2015:2026]*100).round(1).to_string())
        # 10m SMA state in 2022, 2025, 2026 (monthly positions)
        pos = pd.DataFrame({"pos10": p10, "mkt": mkt})
        print("\nMonthly positions and market returns 2021-12..2026-08 (10m SMA)"); print(pos.loc["2021-12":"2026-08"].assign(mkt=lambda d: (d.mkt*100).round(2)).to_string())
    # worst years timing vs bh
    if cost == 0.0:
        yr_all = pd.DataFrame({"BH": (1+mkt).groupby(mkt.index.year).prod()-1, "SMA10": (1+r10.dropna()).groupby(r10.dropna().index.year).prod()-1})
        yr_all["diff"] = yr_all["SMA10"]-yr_all["BH"]
        print("\nShare of calendar years SMA10 beat BH:", (yr_all["diff"]>0).mean().round(3), "of", yr_all["diff"].notna().sum(), "years")
        print("Years with SMA10 underperformance worse than -10pts:", list(yr_all.index[yr_all["diff"]<-0.10]))
