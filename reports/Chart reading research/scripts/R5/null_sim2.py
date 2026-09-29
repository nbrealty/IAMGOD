import numpy as np
rng = np.random.default_rng(777)

def wilder_adx(H, L, C, n=14):
    """H,L,C: (paths, bars). returns ADX (paths, bars) with NaN before warm-up. Wilder's smoothing."""
    p, T = C.shape
    up = H[:, 1:] - H[:, :-1]
    dn = L[:, :-1] - L[:, 1:]
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pc = C[:, :-1]
    tr = np.maximum(H[:, 1:] - L[:, 1:], np.maximum(np.abs(H[:, 1:] - pc), np.abs(L[:, 1:] - pc)))
    T1 = T - 1
    def rma_sum(x):
        s = np.full_like(x, np.nan)
        s[:, n - 1] = x[:, :n].sum(axis=1)
        for i in range(n, T1):
            s[:, i] = s[:, i - 1] - s[:, i - 1] / n + x[:, i]
        return s
    str_, spdm, smdm = rma_sum(tr), rma_sum(pdm), rma_sum(mdm)
    pdi = 100 * spdm / str_
    mdi = 100 * smdm / str_
    dx = 100 * np.abs(pdi - mdi) / (pdi + mdi + 1e-300)
    adx = np.full_like(dx, np.nan)
    adx[:, 2 * n - 2] = dx[:, n - 1:2 * n - 1].mean(axis=1)
    for i in range(2 * n - 1, T1):
        adx[:, i] = (adx[:, i - 1] * (n - 1) + dx[:, i]) / n
    return adx

def sim_ohlc(paths, bars, m):
    # each bar = m sub-steps of a Gaussian random walk (log price); returns H,L,C (log-price levels, then exp for price)
    steps = rng.standard_normal((paths, bars, m)) * (1.0 / np.sqrt(m))
    lp = np.cumsum(steps.reshape(paths, bars * m), axis=1).reshape(paths, bars, m)
    # add previous bar close as offset
    close = lp[:, :, -1]
    prev = np.concatenate([np.zeros((paths, 1)), close[:, :-1]], axis=1)
    lp = lp + prev[:, :, None]
    H = lp.max(axis=2); L = lp.min(axis=2); C = close
    # scale to price ~ 100 with 1% per-bar vol so that log ~ linear
    sc = 0.01
    return 100 * np.exp(sc * H), 100 * np.exp(sc * L), 100 * np.exp(sc * C)

res = []
for m, label in ((5, "bars built from 5 sub-steps (e.g. 5-min bar from 1-min)"), (30, "bars built from 30 sub-steps (close to continuous)")):
    fr25 = []; fr20 = []; last = []
    for chunk in range(6):
        H, L, C = sim_ohlc(2000, 160, m)
        adx = wilder_adx(H, L, C, 14)
        seg = adx[:, 60:]
        fr25.append(np.mean(seg > 25, axis=1)); fr20.append(np.mean(seg > 20, axis=1)); last.append(adx[:, -1])
    fr25 = np.concatenate(fr25); fr20 = np.concatenate(fr20); last = np.concatenate(last)
    s = (f"ADX(14) on a pure random walk, {label}: share of bars with ADX>25 = mean {fr25.mean():.3f} (p10 {np.percentile(fr25,10):.3f}, p90 {np.percentile(fr25,90):.3f});"
         f" ADX>20 = {fr20.mean():.3f}; ADX value p50/p90/p95/p99 = {np.percentile(last,50):.1f}/{np.percentile(last,90):.1f}/{np.percentile(last,95):.1f}/{np.percentile(last,99):.1f}")
    print(s); res.append(s)

# Hurst (naive R/S) and variance-ratio noise on one session
def rs_h(r):
    n = len(r)
    sizes = [s for s in (8, 16, 32, 64, 128) if s <= n // 2]
    lx, ly = [], []
    for s in sizes:
        k = n // s
        rs = []
        for j in range(k):
            x = r[j * s:(j + 1) * s]
            y = np.cumsum(x - x.mean())
            S = x.std()
            if S > 0:
                rs.append((y.max() - y.min()) / S)
        lx.append(np.log(s)); ly.append(np.log(np.mean(rs)))
    return np.polyfit(lx, ly, 1)[0]

def vr(r, q):
    n = len(r)
    mu = r.mean()
    s1 = ((r - mu) ** 2).sum() / (n - 1)
    rq = np.convolve(r, np.ones(q), mode="valid")
    sq = ((rq - q * mu) ** 2).sum() / (len(rq) * q)  # simple overlapping estimator
    return sq / s1

for n in (78, 390, 1950):
    hs = np.array([rs_h(rng.standard_normal(n)) for _ in range(1500)])
    line = f"Naive R/S Hurst estimate of iid noise, n={n} returns: mean {hs.mean():.3f}, 2.5%-97.5% range {np.percentile(hs,2.5):.3f} to {np.percentile(hs,97.5):.3f} (true value 0.5)"
    print(line); res.append(line)
for n in (78, 390, 1950):
    for qq in (5, 10):
        v = np.array([vr(rng.standard_normal(n), qq) for _ in range(4000)])
        line = f"Variance ratio VR({qq}) of iid noise, n={n} returns: mean {v.mean():.3f}, 2.5%-97.5% range {np.percentile(v,2.5):.3f} to {np.percentile(v,97.5):.3f}; LM asymptotic sd={np.sqrt(2*(2*qq-1)*(qq-1)/(3*qq*n)):.3f}"
        print(line); res.append(line)
open("out_null_part2.txt", "w").write("\n".join(res))
