"""Cross-check my Mann-Kendall implementation vs the pymannkendall library on random-walk paths."""
import numpy as np, pymannkendall as pmk
rng = np.random.default_rng(99)
for n in (13, 21, 61):
    rej_lib = 0; rej_mine = 0; agree = 0; N = 1500
    for _ in range(N):
        p = np.concatenate([[0], np.cumsum(rng.standard_normal(n - 1))])
        res = pmk.original_test(p, alpha=0.05)
        # mine
        S = 0.0
        for k in range(1, n):
            S += np.sign(p[k:] - p[:-k]).sum()
        var = n * (n - 1) * (2 * n + 5) / 18.0
        Z = (S - np.sign(S)) / np.sqrt(var) if S != 0 else 0.0
        mine = abs(Z) > 1.959964
        lib = res.h
        rej_lib += lib; rej_mine += mine; agree += (bool(lib) == bool(mine))
    print(f"n={n}: library rejects {rej_lib/N:.3f}, mine {rej_mine/N:.3f}, agreement {agree/N:.4f}")
