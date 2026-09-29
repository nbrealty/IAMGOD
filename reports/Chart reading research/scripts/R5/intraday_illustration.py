"""R5: illustration on the two months of cached SIP 1-minute bars in the repo (read-only). Own calculation; too short to prove anything."""
import glob, gzip, numpy as np, pandas as pd
C = "/home/user/IAMGOD/trading/state/scalp_cache"
def load(sym):
    fs = sorted(glob.glob(f"{C}/{sym}_2026*.csv.gz"))
    df = pd.concat([pd.read_csv(f, parse_dates=["ts"]) for f in fs])
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_convert("America/New_York")
    df = df.sort_values("ts").drop_duplicates("ts").set_index("ts")
    return df
def acf(x, k):
    x = x - x.mean()
    return (x[k:] * x[:-k]).sum() / (x * x).sum()
for sym in ("SPY", "QQQ"):
    df = load(sym)
    df = df.between_time("09:30", "15:59")
    days = sorted(set(df.index.date))
    print(f"\n=== {sym}: {len(df)} one-minute bars, {len(days)} sessions, {days[0]} .. {days[-1]}")
    rets, r5s = [], []
    sess = []
    for d in days:
        x = df[df.index.date == d]
        if len(x) < 380: continue
        lp = np.log(x["close"].values)
        r = np.diff(lp)
        rets.append(r)
        # 5-min returns from 5-min closes
        c5 = x["close"].values[4::5]
        r5s.append(np.diff(np.log(c5)))
        net = lp[-1] - lp[0]
        er = abs(net) / np.abs(r).sum()
        t = np.arange(len(lp)); tc = t - t.mean(); pc = lp - lp.mean()
        r2 = ((pc * tc).sum()) ** 2 / ((tc ** 2).sum() * (pc ** 2).sum())
        sess.append((d, len(lp) - 1, net * 1e4, er, r2, (r > 0).mean(), (np.sign(r[1:]) == np.sign(r[:-1])).mean()))
    S = pd.DataFrame(sess, columns=["date", "n", "net_bps", "ER", "R2", "upfrac", "same_sign_share"])
    print("session-level: median ER %.3f (null p50 0.04, p95 0.13) | share of sessions with ER > 0.13 (null 95th pct): %.2f" % (S.ER.median(), (S.ER > 0.13).mean()))
    print("               median R2 %.2f (null median 0.44) | share with R2>0.8: %.2f (null 0.15)" % (S.R2.median(), (S.R2 > 0.8).mean()))
    print("               same-sign share of consecutive 1-min returns: mean %.3f (null 0.500, sd 0.025 per session)" % S.same_sign_share.mean())
    R = np.concatenate(rets)
    print("pooled 1-min return autocorr (within session, n=%d): " % len(R) + " ".join(f"lag{k}={np.mean([acf(r,k) for r in rets]):+.3f}" for k in (1, 2, 3, 4, 5, 10)))
    print("   sd of 1-min return: %.2f bps" % (R.std() * 1e4))
    R5 = np.concatenate(r5s)
    print("pooled 5-min return autocorr (n=%d): " % len(R5) + " ".join(f"lag{k}={np.mean([acf(r,k) for r in r5s if len(r)>k+2]):+.3f}" for k in (1, 2, 3)))
    # variance ratios pooled (within-session sums)
    def vr(rlist, q):
        num = 0.0; den = 0.0; nq = 0; n1 = 0
        for r in rlist:
            rq = np.convolve(r, np.ones(q), "valid")
            num += (rq ** 2).sum(); nq += len(rq)
            den += (r ** 2).sum(); n1 += len(r)
        return (num / nq) / q / (den / n1)
    print("variance ratios (1-min returns, within sessions, mean not removed): " + " ".join(f"VR({q})={vr(rets,q):.3f}" for q in (2, 5, 10, 30)))
    # time-of-day volume profile (share of session volume by 30-min bucket)
    df["day"] = df.index.date
    df["bucket"] = ((df.index.hour * 60 + df.index.minute) - 570) // 30
    prof = df.groupby(["day", "bucket"])["volume"].sum().unstack()
    share = prof.div(prof.sum(axis=1), axis=0).mean()
    print("avg share of daily volume by 30-min bucket (09:30 first): " + " ".join(f"{v*100:.1f}" for v in share.values))
    # volume spike frequency: 1-min volume / median of same minute-of-day over prior 20 sessions
    df["mod"] = df.index.hour * 60 + df.index.minute
    piv = df.pivot_table(index="day", columns="mod", values="volume")
    base = piv.rolling(20, min_periods=15).median().shift(1)
    rv = (piv / base).stack().dropna()
    print("relative 1-min volume vs same-minute 20-day median: p50 %.2f p90 %.2f p99 %.2f p99.9 %.2f (n=%d)" % (rv.median(), rv.quantile(.9), rv.quantile(.99), rv.quantile(.999), len(rv)))
    avg_ts = (df["volume"] / df["trade_count"].replace(0, np.nan)).median()
    print("median shares per trade in a 1-min bar: %.1f" % avg_ts)
