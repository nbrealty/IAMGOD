import numpy as np, pandas as pd
exec(open("x14_adx_indep2.py").read().split("# sanity check 1")[0])   # make_bars_correct, adx_wilder (mine)
rng = np.random.default_rng(31337)

def adx_ewm(h, l, c, n=14):
    h, l, c = pd.Series(h), pd.Series(l), pd.Series(c)
    up = h.diff(); dn = -l.diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0)); mdm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0))
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    a = 1.0/n
    sm = lambda x: x.iloc[1:].ewm(alpha=a, adjust=False).mean()
    pdi = 100*sm(pdm)/sm(tr); mdi = 100*sm(mdm)/sm(tr)
    dx = 100*(pdi-mdi).abs()/(pdi+mdi)
    return dx.ewm(alpha=a, adjust=False).mean().values

for sub in (5, 30):
    H, L, C = make_bars_correct(1200, 260, sub)
    a_loop = adx_wilder(H, L, C, 14)[:, 80:]
    a_ewm = np.array([adx_ewm(H[i], L[i], C[i])[79:] for i in range(H.shape[0])])[:, :a_loop.shape[1]]
    print(f"sub={sub:>2}: share ADX>25  Wilder-loop {np.mean(a_loop>25):.3f}   pandas-ewm {np.mean(a_ewm>25):.3f}   (ADX>20: {np.mean(a_loop>20):.3f} / {np.mean(a_ewm>20):.3f})")
