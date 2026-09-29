"""R5: null distributions of trend-quality metrics under a pure random walk (own simulation, not a published result)."""
import numpy as np, sys
rng = np.random.default_rng(12345)

def metrics_from_logprice(P):
    """P: (paths, n+1) log prices. returns dict of arrays (paths,)"""
    p, n1 = P.shape
    n = n1 - 1
    d = np.diff(P, axis=1)
    net = P[:, -1] - P[:, 0]
    er = np.abs(net) / np.maximum(np.abs(d).sum(axis=1), 1e-300)
    t = np.arange(n1, dtype=float)
    tc = t - t.mean()
    Pc = P - P.mean(axis=1, keepdims=True)
    slope = (Pc * tc).sum(axis=1) / (tc ** 2).sum()
    ss_tot = (Pc ** 2).sum(axis=1)
    ss_reg = slope ** 2 * (tc ** 2).sum()
    r2 = ss_reg / np.maximum(ss_tot, 1e-300)
    # t-stat of mean return (net move / (sd*sqrt(n)))
    sd = d.std(axis=1, ddof=1)
    tstat = np.abs(d.mean(axis=1)) / (sd / np.sqrt(n))
    upfrac = (d > 0).mean(axis=1)
    # sign persistence: share of consecutive bar pairs with the same sign
    s = np.sign(d)
    same = (s[:, 1:] == s[:, :-1]).mean(axis=1)
    return dict(ER=er, R2=r2, tstat=tstat, absupdev=np.abs(upfrac - 0.5), same_sign=same, slope=slope)

def mk_z(P, maxn=None):
    """Mann-Kendall S and Z (no tie correction needed for continuous data) applied to price levels."""
    p, n1 = P.shape
    S = np.zeros(p)
    for i in range(n1 - 1):
        S += np.sign(P[:, i + 1:] - P[:, [i]]).sum(axis=1)
    n = n1
    var = n * (n - 1) * (2 * n + 5) / 18.0
    z = np.where(S > 0, (S - 1) / np.sqrt(var), np.where(S < 0, (S + 1) / np.sqrt(var), 0.0))
    return z

def rs_hurst(r):
    """naive R/S Hurst estimate from one window of returns via a few sub-block sizes (simple version)"""
    n = len(r)
    sizes = [s for s in (8, 16, 32, 64, 128, 256) if s <= n // 2]
    logs, logn = [], []
    for s in sizes:
        k = n // s
        rs = []
        for j in range(k):
            x = r[j * s:(j + 1) * s]
            y = np.cumsum(x - x.mean())
            R = y.max() - y.min()
            S = x.std(ddof=0)
            if S > 0:
                rs.append(R / S)
        logs.append(np.log(np.mean(rs))); logn.append(np.log(s))
    return np.polyfit(logn, logs, 1)[0]

def gen_returns(kind, paths, n):
    if kind == "gauss":
        return rng.standard_normal((paths, n))
    if kind == "t3":  # fat tails, unit variance
        x = rng.standard_t(3, size=(paths, n))
        return x / np.sqrt(3.0)
    if kind == "sv":  # stochastic-vol-ish: lognormal AR(1) log-vol, fat tails through mixing
        h = np.zeros((paths, n))
        e = rng.standard_normal((paths, n))
        u = rng.standard_normal((paths, n))
        h[:, 0] = 0
        for i in range(1, n):
            h[:, i] = 0.97 * h[:, i - 1] + 0.15 * e[:, i]
        return np.exp(h / 1.0) * u / np.sqrt(np.exp(2 * (0.15 ** 2 / (1 - 0.97 ** 2)) / 2.0))
    raise ValueError(kind)

def q(x, ps=(50, 90, 95, 99)):
    return [np.percentile(x, p) for p in ps]

out = []
def line(s):
    print(s); out.append(s)

for kind in ("gauss", "t3", "sv"):
    line(f"\n##### return model: {kind}   (window = n bars of log returns; {20000} paths; quantiles p50/p90/p95/p99)")
    for n in (12, 20, 30, 60, 78, 390):
        paths = 20000 if n <= 78 else 4000
        r = gen_returns(kind, paths, n)
        P = np.concatenate([np.zeros((paths, 1)), np.cumsum(r, axis=1)], axis=1)
        m = metrics_from_logprice(P)
        z = mk_z(P) if n <= 78 else mk_z(P[:2000])
        line(f"n={n:4d} | ER {q(m['ER'])[0]:.2f}/{q(m['ER'])[1]:.2f}/{q(m['ER'])[2]:.2f}/{q(m['ER'])[3]:.2f}"
             f" | R2 {q(m['R2'])[0]:.2f}/{q(m['R2'])[1]:.2f}/{q(m['R2'])[2]:.2f}/{q(m['R2'])[3]:.2f}"
             f" | |t| {q(m['tstat'])[0]:.2f}/{q(m['tstat'])[1]:.2f}/{q(m['tstat'])[2]:.2f}/{q(m['tstat'])[3]:.2f}"
             f" | P(R2>0.8)={np.mean(m['R2']>0.8):.3f} P(ER>0.3)={np.mean(m['ER']>0.3):.3f}"
             f" | P(|MKz|>1.96)={np.mean(np.abs(z)>1.96):.3f}"
             f" | same-sign share p50={np.median(m['same_sign']):.3f} sd={m['same_sign'].std():.3f}")
open("out_null_part1.txt", "w").write("\n".join(out))
