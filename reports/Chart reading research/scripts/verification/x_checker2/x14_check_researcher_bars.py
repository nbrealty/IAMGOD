"""Diagnostic only: does the researcher's bar construction (r5/null_sim2.py sim_ohlc) give valid bars (L <= C <= H)?
I copy the function body verbatim (read from their file) to test it, then compare with my own valid-bar ADX results."""
import numpy as np
rng = np.random.default_rng(777)
def sim_ohlc(paths, bars, m):
    steps = rng.standard_normal((paths, bars, m)) * (1.0 / np.sqrt(m))
    lp = np.cumsum(steps.reshape(paths, bars * m), axis=1).reshape(paths, bars, m)
    close = lp[:, :, -1]
    prev = np.concatenate([np.zeros((paths, 1)), close[:, :-1]], axis=1)
    lp = lp + prev[:, :, None]
    H = lp.max(axis=2); L = lp.min(axis=2); C = close
    sc = 0.01
    return 100 * np.exp(sc * H), 100 * np.exp(sc * L), 100 * np.exp(sc * C)
H, L, C = sim_ohlc(200, 160, 5)
bad = np.mean((C > H + 1e-9) | (C < L - 1e-9))
print("share of researcher-constructed bars where close lies outside [low, high]:", round(float(bad), 3))
print("mean (H - C)/C over bars, in %:", float(np.mean((H - C) / C) * 100))
