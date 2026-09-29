"""R5: does 'trend quality' today predict continuation tomorrow? Test on US daily market returns (Ken French data library, public).
Own calculation, not a published result. Total market return = Mkt-RF + RF (CRSP value-weighted, all US stocks)."""
import re, numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv

rows = []
for ln in open("../data/F-F_Research_Data_Factors_daily.csv"):
    m = re.match(r"^\s*(\d{8})\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)", ln)
    if m:
        rows.append((m.group(1), float(m.group(2)), float(m.group(5))))
df = pd.DataFrame(rows, columns=["d", "mktrf", "rf"])
df["date"] = pd.to_datetime(df["d"], format="%Y%m%d")
df = df.set_index("date")
df["r"] = (df["mktrf"] + df["rf"]) / 100.0
df["lr"] = np.log1p(df["r"])
print("rows", len(df), df.index[0].date(), "->", df.index[-1].date())

def ols_nw(y, X, L):
    y = np.asarray(y, float); X = np.asarray(X, float)
    n, k = X.shape
    XtXi = np.linalg.inv(X.T @ X)
    b = XtXi @ X.T @ y
    e = y - X @ b
    Xe = X * e[:, None]
    S = Xe.T @ Xe
    for l in range(1, L + 1):
        w = 1 - l / (L + 1)
        G = Xe[l:].T @ Xe[:-l]
        S += w * (G + G.T)
    V = XtXi @ S @ XtXi
    return b, np.sqrt(np.diag(V))

# ---------------------------------------------------------------- A. autocorrelation and variance ratios by sub-period
def acf(x, k):
    x = x - x.mean()
    return (x[k:] * x[:-k]).sum() / (x * x).sum()

def lm_vr(x, q):
    n = len(x); mu = x.mean()
    s1 = ((x - mu) ** 2).sum() / (n - 1)
    rq = np.convolve(x, np.ones(q), "valid")
    m = q * (n - q + 1) * (1 - q / n)
    sq = ((rq - q * mu) ** 2).sum() / m
    vr = sq / s1
    # heteroskedasticity-robust variance (Lo-MacKinlay 1988 z*)
    d = (x - mu) ** 2
    theta = 0.0
    for j in range(1, q):
        dj = (d[j:] * d[:-j]).sum() / (d.sum() ** 2) * n
        theta += (2 * (q - j) / q) ** 2 * dj
    z = (vr - 1) / np.sqrt(theta / n)
    return vr, z

periods = [("1926-1945", "1926-01-01", "1945-12-31"), ("1946-1969", "1946-01-01", "1969-12-31"),
           ("1970-1989", "1970-01-01", "1989-12-31"), ("1990-2009", "1990-01-01", "2009-12-31"),
           ("2010-2026", "2010-01-01", "2026-12-31"), ("2016-2026", "2016-01-01", "2026-12-31")]
print("\nA. Daily US market return: autocorrelation and variance ratios by period (log returns)")
print("period      n     rho1    rho2    rho3    rho5   VR(2) z*    VR(5) z*    VR(10) z*   VR(20) z*")
for name, a, b in periods:
    x = df.loc[a:b, "lr"].values
    vals = [acf(x, k) for k in (1, 2, 3, 5)]
    v = [lm_vr(x, q) for q in (2, 5, 10, 20)]
    print(f"{name}  {len(x):6d}  {vals[0]:+.3f}  {vals[1]:+.3f}  {vals[2]:+.3f}  {vals[3]:+.3f}  " + "  ".join(f"{vr:.2f} {z:+.1f}" for vr, z in v))

# ---------------------------------------------------------------- B. trend quality -> continuation
lr = df["lr"].values
dates = df.index
LP = np.cumsum(lr)          # log price
n_all = len(lr)

def rolling_metrics(N):
    W = swv(LP, N + 1)                      # windows of N+1 log prices ending at index i+N
    end = np.arange(N, n_all)               # index of the window's last price
    d = np.diff(W, axis=1)
    net = W[:, -1] - W[:, 0]
    er = np.abs(net) / np.abs(d).sum(axis=1)
    t = np.arange(N + 1, dtype=float); tc = t - t.mean()
    Wc = W - W.mean(axis=1, keepdims=True)
    slope = (Wc * tc).sum(axis=1) / (tc ** 2).sum()
    r2 = slope ** 2 * (tc ** 2).sum() / (Wc ** 2).sum(axis=1)
    sd = d.std(axis=1, ddof=1)
    tstat = d.mean(axis=1) / (sd / np.sqrt(N))
    up = (d > 0).mean(axis=1); dn = (d < 0).mean(axis=1)
    idx = np.sign(net) * (dn - up)          # Da-Gurun-Warachka information discreteness (low = smooth / continuous)
    S = np.zeros(len(W))
    for i in range(N):
        S += np.sign(W[:, i + 1:] - W[:, [i]]).sum(axis=1)
    nn = N + 1
    mkz = S / np.sqrt(nn * (nn - 1) * (2 * nn + 5) / 18.0)
    return end, dict(ER=er, R2=r2, absT=np.abs(tstat), ID=-idx, MKz=np.abs(mkz)), np.sign(net), net

def fwd(h):
    c = np.concatenate([[0.0], np.cumsum(lr)])
    out = np.full(n_all, np.nan)
    for i in range(n_all - h):
        out[i] = c[i + 1 + h] - c[i + 1]
    return out

fw = {h: fwd(h) for h in (1, 5, 20)}

def run(N, h, sub):
    end, M, dirn, net = rolling_metrics(N)
    y = dirn * fw[h][end]
    ok = ~np.isnan(y)
    a, b = sub
    inper = (dates[end] >= a) & (dates[end] <= b) & ok
    res = {}
    base = y[inper]
    L = max(h, 10)
    bb, se = ols_nw(base, np.ones((len(base), 1)), L)
    res["ALL"] = (bb[0] * 1e4, bb[0] / se[0], len(base))
    absnet = np.abs(net)
    for k, v in M.items():
        vv = v[inper]
        lo, hi = np.quantile(vv, [1 / 3, 2 / 3])
        Dh = (vv >= hi).astype(float); Dl = (vv <= lo).astype(float)
        X = np.column_stack([np.ones(len(vv)), Dh, Dl])
        bb, se = ols_nw(base, X, max(L, N))
        # High minus Low
        Xd = np.column_stack([np.ones(len(vv)), Dh - Dl])
        # simple: use difference of coefficients with HAC via re-parametrisation
        Xr = np.column_stack([np.ones(len(vv)), Dh - Dl, Dh + Dl])
        br, ser = ols_nw(base, Xr, max(L, N))
        res[k] = ((bb[0] + bb[2]) * 1e4, (bb[0] + bb[1]) * 1e4, br[1] * 1e4 * 2, br[1] / ser[1])
    return res

print("\nB. Aligned forward return = sign(past N-day return) x next-h-day return (bps per day-window).")
print("   'ALL' = unconditional (plain trend-following at that lookback). For each quality metric: Low-tercile mean, High-tercile mean, High-minus-Low, HAC t-stat.")
subs = [("1926-1969", ("1926-01-01", "1969-12-31")), ("1970-1999", ("1970-01-01", "1999-12-31")), ("2000-2026", ("2000-01-01", "2026-12-31")), ("2016-2026", ("2016-01-01", "2026-12-31"))]
for N in (20, 60):
    for h in (1, 5, 20):
        for sname, sub in subs:
            r = run(N, h, sub)
            all_ = r["ALL"]
            parts = []
            for k in ("ER", "R2", "absT", "ID", "MKz"):
                lo, hi, diff, t = r[k]
                parts.append(f"{k}: L{lo:+.1f} H{hi:+.1f} H-L{diff:+.1f}(t{t:+.1f})")
            print(f"N={N:2d} h={h:2d} {sname}: ALL {all_[0]:+.2f} bps (t{all_[1]:+.1f}, n={all_[2]}) | " + " | ".join(parts))


print("\nC. Does a quality metric add anything beyond the simple size of the move (|t-stat| of the past N-day return)?")
print("   Regression: aligned fwd return (bps) on z(absT) and z(metric). Reported: coefficient on the metric per +1 SD, HAC t-stat, in brackets the coefficient on absT.")
def multireg(N, h, sub):
    end, M, dirn, net = rolling_metrics(N)
    y = dirn * fw[h][end]
    ok = ~np.isnan(y)
    a, b = sub
    inper = (dates[end] >= a) & (dates[end] <= b) & ok
    yy = y[inper]
    z = lambda v: (v[inper] - v[inper].mean()) / v[inper].std()
    out = {}
    for k in ("ER", "R2", "MKz", "ID"):
        X = np.column_stack([np.ones(len(yy)), z(M["absT"]), z(M[k])])
        bb, se = ols_nw(yy, X, max(h, N))
        out[k] = (bb[2] * 1e4, bb[2] / se[2], bb[1] * 1e4)
    return out
for N in (20, 60):
    for h in (1, 5, 20):
        for sname, sub in (("1926-1999", ("1926-01-01", "1999-12-31")), ("2000-2026", ("2000-01-01", "2026-12-31"))):
            r = multireg(N, h, sub)
            print(f"N={N:2d} h={h:2d} {sname}: " + " | ".join(f"{k}: {v[0]:+.1f}bps (t{v[1]:+.1f}) [absT {v[2]:+.1f}]" for k, v in r.items()))
