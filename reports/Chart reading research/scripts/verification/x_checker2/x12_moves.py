"""Recompute mean |return| and sd for SPY 1/5/15/30/60-min horizons from the researcher's cached 1-min bars (SPY_df.pkl). Own code."""
import pandas as pd, numpy as np
df = pd.read_pickle("/tmp/claude-0/-home-user-IAMGOD/6e4d9533-109b-52a4-b160-33463d24abe1/scratchpad/research/work/SPY_df.pkl")
print(df.columns.tolist(), len(df), df['date'].nunique() if 'date' in df else '')
print("median close:", df.close.median())
df = df.sort_values('ts').copy()
df['d'] = df['ts'].dt.date
res = {}
for m in (1, 5, 15, 30, 60):
    rets = []
    for d, g in df.groupby('d'):
        s = g.set_index('ts')['close']
        # session bars from 09:30 to 16:00: take closes at k*m minutes after 09:30 boundary. Use bars whose label minute-of-day index (from 09:30) is multiple of m, taking close of bar ending at that boundary.
        idx = (g['ts'].dt.hour * 60 + g['ts'].dt.minute) - (9 * 60 + 30)   # 0 for 09:30 bar (bar open time)
        # close of the bar at open-time minute (k*m - 1) is the price at boundary k*m
        pts = g[(idx + 1) % m == 0]
        px = pts['close'].values
        # include the price at 09:30 open as the starting point: use the open of the first bar
        p0 = g['open'].iloc[0]
        px = np.concatenate([[p0], px])
        r = np.diff(np.log(px)) * 1e4
        rets.append(r)
    r = np.concatenate(rets)
    res[m] = (np.mean(np.abs(r)), np.std(r, ddof=1), len(r))
    print(f"{m:3d}-min: mean|ret| = {res[m][0]:.2f} bp, sd = {res[m][1]:.2f} bp, n = {res[m][2]}")
