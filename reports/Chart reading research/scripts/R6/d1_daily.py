from lib import *
import sys
COST = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0   # bps per one-way switch
rfd = read_french_block(D+"F-F_Research_Data_Factors_daily.csv", monthly=False)["RF"]   # daily rf (decimal per day)
END = "2026-08-31"

def prep(t):
    df = load_yahoo(t)
    df = df[["open","close","adjclose"]].dropna()
    df["id"] = df["close"]/df["open"] - 1
    cc = df["adjclose"].pct_change()
    df["ov"] = (1+cc)/(1+df["id"]) - 1
    return df

def weekly_flag(df, n=30):
    d = df["adjclose"]
    grp = d.index.to_period("W-FRI")
    last_dates = d.groupby(grp).apply(lambda x: x.index[-1])
    wk = d.loc[last_dates.values]
    sma = wk.rolling(n).mean()
    flag = (wk > sma).where(sma.notna())
    return flag.reindex(d.index).ffill()

def monthly_flag(df, n=10):
    d = df["adjclose"]
    grp = d.index.to_period("M")
    last_dates = d.groupby(grp).apply(lambda x: x.index[-1])
    mo = d.loc[last_dates.values]
    sma = mo.rolling(n).mean()
    flag = (mo > sma).where(sma.notna())
    return flag.reindex(d.index).ffill()

def sma_flag(df, n=200):
    d = df["adjclose"]; sma = d.rolling(n).mean()
    return (d > sma).where(sma.notna())

def donchian(df, n_in, n_out, gate=None):
    c = df["adjclose"].values
    hi = pd.Series(c, index=df.index).rolling(n_in).max().shift(1).values
    lo = pd.Series(c, index=df.index).rolling(n_out).min().shift(1).values
    g = gate.reindex(df.index).values if gate is not None else np.ones(len(c))
    st = np.full(len(c), np.nan); pos = 0.0; started = False
    for i in range(len(c)):
        if np.isnan(hi[i]) or np.isnan(lo[i]) or (gate is not None and np.isnan(g[i])):
            st[i] = np.nan; continue
        started = True
        if pos == 0.0:
            if c[i] > hi[i] and (gate is None or g[i] == 1): pos = 1.0
        else:
            if c[i] < lo[i] or (gate is not None and g[i] != 1): pos = 0.0
        st[i] = pos
    return pd.Series(st, index=df.index)

def run(df, sig, cost_bps=COST):
    s = sig.astype(float)
    s_prev = s.shift(1)      # decided at close d-1, executed at open d
    s_prev2 = s.shift(2)     # position held overnight into open d
    rf = rfd.reindex(df.index).fillna(0.0)
    ret = s_prev2*df["ov"] + s_prev*df["id"] + rf*(1 - (s_prev2 + s_prev)/2)
    sw = (s_prev - s_prev2).abs()
    ret = ret - sw*cost_bps/1e4
    valid = s_prev.notna() & s_prev2.notna()
    return ret.where(valid), sw.where(valid)

def report(sym, df, rules, periods):
    bh = (df["ov"] + 0)  # placeholder
    bh_ret = df["adjclose"].pct_change()
    rf = rfd.reindex(df.index).fillna(0.0)
    res = {}
    for name, sig in rules.items():
        r, sw = run(df, sig)
        res[name] = (r, sw, sig)
    for pname, (a, b) in periods.items():
        a = max(pd.Timestamp(a), df.index[0]); b = pd.Timestamp(b)
        first_valid = max(r.first_valid_index() for r, _, _ in res.values())
        a = max(a, first_valid)
        print(f"\n[{sym}] {pname}: {a.date()} .. {b.date()}")
        s = stats(bh_ret.loc[a:b], rf, 252, "Buy&hold "+sym); print(fmt(s, 252))
        for name, (r, sw, sig) in res.items():
            rr = r.loc[a:b]
            s = stats(rr, rf, 252, name); 
            yrs = len(rr)/252
            inmkt = (sig.shift(1).loc[a:b]).mean()
            print(fmt(s, 252) + f"  | switches/yr {sw.loc[a:b].sum()/yrs:4.1f}  in-market {inmkt*100:3.0f}%")
    return res

def calendar(sym, df, res, years):
    bh_ret = df["adjclose"].pct_change()
    tbl = {"B&H": (1+bh_ret).groupby(bh_ret.index.year).prod()-1}
    for name, (r, sw, sig) in res.items():
        rr = r.dropna(); tbl[name] = (1+rr).groupby(rr.index.year).prod()-1
    t = pd.DataFrame(tbl).loc[years]*100
    print(f"\n[{sym}] calendar-year returns %, cost {COST}bp/switch (2026 = Jan..Aug)")
    print(t.round(1).to_string())

for sym, start in (("SPY", "1993-01-01"), ("QQQ", "1999-01-01")):
    df = prep(sym).loc[:END]
    wk = weekly_flag(df, 30)
    rules = {
        "A: close>200d SMA": sma_flag(df, 200),
        "B: weekly close>30w SMA": wk,
        "C: monthly close>10m SMA": monthly_flag(df, 10),
        "D: Donchian 55d in / 20d out": donchian(df, 55, 20),
        "E: weekly 30w filter + 20d breakout / 10d exit": donchian(df, 20, 10, gate=wk),
    }
    if sym == "SPY":
        periods = {"full": ("1993-01-01", END), "1993-2006": ("1993-01-01","2006-12-31"), "2007-2019": ("2007-01-01","2019-12-31"), "2020-2026.08": ("2020-01-01", END), "2022 only": ("2022-01-01","2022-12-31"), "2025-01..2026-08": ("2025-01-01", END)}
    else:
        periods = {"full": ("1999-03-10", END), "1999-2009": ("1999-01-01","2009-12-31"), "2010-2019": ("2010-01-01","2019-12-31"), "2020-2026.08": ("2020-01-01", END), "2022 only": ("2022-01-01","2022-12-31"), "2025-01..2026-08": ("2025-01-01", END)}
    res = report(sym, df, rules, periods)
    calendar(sym, df, res, list(range(2018, 2027)))
    # current state (as of last Yahoo close)
    full = prep(sym)
    d = full["adjclose"]
    print(f"\n[{sym}] last Yahoo close {d.index[-1].date()}: adjclose {d.iloc[-1]:.2f}; 200d SMA {d.rolling(200).mean().iloc[-1]:.2f}; 52w-high(close) {d.iloc[-252:].max():.2f}")
