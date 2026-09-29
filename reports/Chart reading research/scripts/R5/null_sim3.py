import numpy as np
rng = np.random.default_rng(2026)
for W in (12, 36):
    p = 200000
    r = rng.standard_normal((p, W))
    M = r.sum(axis=1); RV = (r ** 2).sum(axis=1)
    T = M / np.sqrt(RV)
    ER = np.abs(M) / np.abs(r).sum(axis=1)
    up = (r > 0).sum(axis=1); dn = (r < 0).sum(axis=1)
    ID = np.sign(M) * (dn - up) / W
    q = lambda x, ps: " / ".join(f"{np.percentile(x, pp):.2f}" for pp in ps)
    print(f"W={W}: abs(T) p50/p90/p95/p99 = {q(np.abs(T),(50,90,95,99))}; P(abs(T)>=1.65) = {np.mean(np.abs(T)>=1.65):.3f};"
          f" ER p50/p90/p95/p99 = {q(ER,(50,90,95,99))};"
          f" ID mean {ID.mean():+.3f}, sd {ID.std():.3f}, p5/p50/p95 = {q(ID,(5,50,95))}; P(ID<=-0.5) = {np.mean(ID<=-0.5):.3f}")
    # joint: how often do both high ER (given size quintile) ... skip
    # P(abs(T)>=1.65 and ER>=0.5)
    print(f"      P(abs(T)>=1.65 and ER>=0.5) = {np.mean((np.abs(T)>=1.65)&(ER>=0.5)):.3f}; P(ER>=0.5) = {np.mean(ER>=0.5):.3f}")
