import glob, numpy as np, pandas as pd
C = "/home/user/IAMGOD/trading/state/scalp_cache"
for sym in ("SPY", "QQQ"):
    fs = sorted(glob.glob(f"{C}/{sym}_2026*.csv.gz"))
    df = pd.concat([pd.read_csv(f, parse_dates=["ts"]) for f in fs])
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_convert("America/New_York")
    df = df.sort_values("ts").drop_duplicates("ts").set_index("ts").between_time("09:30", "15:59")
    same, tot, zeros, n = 0, 0, 0, 0
    for d, x in df.groupby(df.index.date):
        if len(x) < 380: continue
        r = np.diff(np.log(x["close"].values))
        n += len(r); zeros += (r == 0).sum()
        s = np.sign(r); s = s[s != 0]
        same += (s[1:] == s[:-1]).sum(); tot += len(s) - 1
    print(sym, "share of 1-min close changes that are exactly zero: %.3f" % (zeros / n), "| same-sign share among consecutive NONZERO moves: %.3f (null 0.5; se over %d pairs = %.4f)" % (same / tot, tot, 0.5 / np.sqrt(tot)))
