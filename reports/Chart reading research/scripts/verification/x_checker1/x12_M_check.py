"""Independent recomputation of mean absolute k-minute moves from the researcher's cached 1-min bars (read-only use of the data)."""
import pandas as pd, numpy as np
bars = pd.read_pickle("/tmp/claude-0/-home-user-IAMGOD/6e4d9533-109b-52a4-b160-33463d24abe1/scratchpad/research/work/SPY_df.pkl")
bars = bars.sort_values("ts").reset_index(drop=True)
bars["d"] = bars["ts"].dt.date
print("median close: %.1f   sessions: %d" % (bars.close.median(), bars.d.nunique()))
lp = np.log(bars["close"].values)
# 1-minute close-to-close log returns inside each session (no cross-session/overnight)
ret1 = np.diff(lp); same_day = (bars["d"].values[1:] == bars["d"].values[:-1])
r1 = ret1[same_day]*1e4
print("1-min: n=%d mean|r|=%.3f bp  sd=%.3f bp  -> annualised vol (sqrt(390*252)) = %.2f%%" % (len(r1), np.abs(r1).mean(), r1.std(), r1.std()*1e-4*np.sqrt(390*252)*100))
def kmin(k, overlapping):
    out = []
    for d, g in bars.groupby("d"):
        c = np.log(g["close"].values)
        if overlapping:
            out.append((c[k:] - c[:-k]))
        else:
            idx = np.arange(0, len(c), k)
            out.append(np.diff(c[idx]))
    return np.concatenate(out)*1e4
for k in (1, 5, 15, 30, 60):
    a = kmin(k, True); b = kmin(k, False)
    print(f"{k:>3}-min: overlapping mean|r|={np.abs(a).mean():6.2f} bp (n={len(a)}), sd={a.std():6.2f} ; non-overlapping mean|r|={np.abs(b).mean():6.2f} bp (n={len(b)}), sd={b.std():6.2f}")
# using close(t-k) -> close(t) vs open(t-k+1)->close(t)
