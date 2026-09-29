"""X14 independent ADX(14) re-simulation (checker2). Own Wilder ADX + TA-Lib cross-check. Pure Gaussian random walk (arithmetic, no drift)."""
import numpy as np, talib
rng = np.random.default_rng(424242)

def my_adx(H, L, C, n=14):
    """Wilder ADX for one series (loop implementation, written from Wilder's definition)."""
    T = len(C)
    pdm = np.zeros(T); mdm = np.zeros(T); tr = np.zeros(T)
    for i in range(1, T):
        up = H[i] - H[i-1]; dn = L[i-1] - L[i]
        pdm[i] = up if (up > dn and up > 0) else 0.0
        mdm[i] = dn if (dn > up and dn > 0) else 0.0
        tr[i] = max(H[i] - L[i], abs(H[i] - C[i-1]), abs(L[i] - C[i-1]))
    adx = np.full(T, np.nan)
    # first smoothed values at index n (sum of bars 1..n)
    str_ = tr[1:n+1].sum(); sp = pdm[1:n+1].sum(); sm = mdm[1:n+1].sum()
    dx = np.full(T, np.nan)
    def dxf(sp, sm, str_):
        pdi = 100 * sp / str_; mdi = 100 * sm / str_
        return 100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) > 0 else 0.0
    dx[n] = dxf(sp, sm, str_)
    for i in range(n + 1, T):
        str_ = str_ - str_ / n + tr[i]; sp = sp - sp / n + pdm[i]; sm = sm - sm / n + mdm[i]
        dx[i] = dxf(sp, sm, str_)
    # ADX first = mean of first n DX values (indices n..2n-1), then Wilder smoothing
    adx[2*n - 1] = np.nanmean(dx[n:2*n])
    for i in range(2*n, T):
        adx[i] = (adx[i-1] * (n - 1) + dx[i]) / n
    return adx

def make_bars(paths, bars, m, sd_bar=10.0, base=1e4):
    steps = rng.standard_normal((paths, bars, m)) * (sd_bar / np.sqrt(m))
    lvl = np.cumsum(steps.reshape(paths, bars * m), axis=1).reshape(paths, bars, m) + base
    C = lvl[:, :, -1]
    prevC = np.concatenate([np.full((paths, 1), base), C[:, :-1]], axis=1)
    # continuous walk: bar k starts where bar k-1 ended, so shift each bar's sub-path by the end of previous bar
    # (lvl already cumulative over the whole path, so this is automatically continuous)
    O = np.concatenate([np.full((paths, 1), base), C[:, :-1]], axis=1)
    H = np.maximum(lvl.max(axis=2), O)
    L = np.minimum(lvl.min(axis=2), O)
    return H, L, C

# 1) Cross-check my ADX vs TA-Lib on a few series
H, L, C = make_bars(5, 600, 10)
for k in range(3):
    a = my_adx(H[k], L[k], C[k]); b = talib.ADX(H[k], L[k], C[k], timeperiod=14)
    ok = np.nanmax(np.abs(a[60:] - b[60:]))
    print(f"cross-check path {k}: max |mine - TA-Lib| after bar 60 = {ok:.2e}; first non-NaN idx mine={np.where(~np.isnan(a))[0][0]} talib={np.where(~np.isnan(b))[0][0]}")

# 2) Share of bars with ADX>25 (TA-Lib), long series, burn-in 100 bars
print()
print("Long series (1,500 bars, burn-in 100), 600 paths each; share of bars with ADX(14) > 25 / > 20; pooled ADX percentiles")
for m in (1, 5, 20, 60):
    paths = 600 if m <= 20 else 300
    H, L, C = make_bars(paths, 1500, m)
    shares25 = []; shares20 = []; pooled = []
    for k in range(paths):
        a = talib.ADX(H[k], L[k], C[k], timeperiod=14)[100:]
        shares25.append(np.mean(a > 25)); shares20.append(np.mean(a > 20)); pooled.append(a)
    pooled = np.concatenate(pooled)
    s25 = np.array(shares25)
    print(f" sub-steps per bar m={m:3d}: share ADX>25 mean {s25.mean():.3f} (path-level p10 {np.percentile(s25,10):.3f}, p90 {np.percentile(s25,90):.3f}) | share ADX>20 {np.mean(shares20):.3f} | ADX p50/p90/p95/p99 = " +
          "/".join(f"{np.percentile(pooled,q):.1f}" for q in (50, 90, 95, 99)))

# 3) Session-length series, like one trading day: 78 five-minute bars and 390 one-minute bars, ADX warm-up excluded (first 27 bars have no ADX)
print()
print("Session-length series; share of bars (where ADX exists) with ADX>25; 4000 paths")
for bars, m in ((78, 5), (390, 1), (390, 5)):
    H, L, C = make_bars(4000, bars, m)
    fr = []
    for k in range(4000):
        a = talib.ADX(H[k], L[k], C[k], timeperiod=14)
        a = a[~np.isnan(a)]
        fr.append(np.mean(a > 25))
    fr = np.array(fr)
    print(f" bars={bars:4d} m={m}: mean share {fr.mean():.3f}, p10 {np.percentile(fr,10):.3f}, p90 {np.percentile(fr,90):.3f}, share of sessions with ADX>25 at the last bar: ", end="")
    last = []
    for k in range(4000):
        a = talib.ADX(H[k], L[k], C[k], timeperiod=14)
        last.append(a[-1])
    print(f"{np.mean(np.array(last) > 25):.3f}")

# 4) Fat-tailed increments (Student t3, unit variance per sub-step) with m=5
print()
def make_bars_t(paths, bars, m, df=3, sd_bar=10.0, base=1e4):
    steps = rng.standard_t(df, size=(paths, bars, m)) / np.sqrt(df / (df - 2)) * (sd_bar / np.sqrt(m))
    lvl = np.cumsum(steps.reshape(paths, bars * m), axis=1).reshape(paths, bars, m) + base
    C = lvl[:, :, -1]
    O = np.concatenate([np.full((paths, 1), base), C[:, :-1]], axis=1)
    return np.maximum(lvl.max(axis=2), O), np.minimum(lvl.min(axis=2), O), C
H, L, C = make_bars_t(400, 1500, 5)
s = [np.mean(talib.ADX(H[k], L[k], C[k], 14)[100:] > 25) for k in range(400)]
print(f"Student-t(3) increments, m=5, long series: share ADX>25 mean {np.mean(s):.3f} (p10 {np.percentile(s,10):.3f}, p90 {np.percentile(s,90):.3f})")
