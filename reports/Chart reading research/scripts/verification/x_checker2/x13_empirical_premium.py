"""X13 extra: what does the realised SPY movement (researcher's 40 cached sessions, Aug-Sep 2026) imply for the fair price of a 25-minute ATM call?
Fair value of an ATM call with zero drift/rates ~= S * E[max(R,0)] = 0.5 * S * E|R| (R = return over the option's remaining life). Own code."""
import pandas as pd, numpy as np
df = pd.read_pickle("/tmp/claude-0/-home-user-IAMGOD/6e4d9533-109b-52a4-b160-33463d24abe1/scratchpad/research/work/SPY_df.pkl").sort_values('ts').reset_index(drop=True)
df['d'] = df['ts'].dt.date
S = 766.0
mins_from_open = (df['ts'].dt.hour*60 + df['ts'].dt.minute) - (9*60+30)   # bar open time offset, 0..389
rows = []
for d, g in df.groupby('d'):
    g = g.set_index(mins_from_open[g.index].values)   # index = minute offset of bar open
    if len(g) < 380: continue
    close = g['close']
    # price at time t (end of bar with offset t-1) => close of offset t-1
    def px(t): return close.get(t-1, np.nan)
    rows.append(dict(d=d,
                     last25=np.log(px(390)/px(365)),            # 15:35 -> 16:00
                     r_1000=np.log(px(60)/px(35)),               # 10:05 -> 10:30
                     r_1130=np.log(px(150)/px(125)),
                     r_1300=np.log(px(210)/px(185)),
                     r_1430=np.log(px(300)/px(275))))
R = pd.DataFrame(rows).set_index('d')
print("sessions:", len(R))
for c, lab in (('r_1000','10:05-10:30'),('r_1130','11:35-12:00'),('r_1300','13:35-14:00'),('r_1430','15:05-15:30'),('last25','15:35-16:00 (to expiry)')):
    x = R[c].dropna().values
    ea = np.mean(np.abs(x))
    print(f"25-min return {lab:24s}: mean|R| = {ea*1e4:5.2f} bp -> fair ATM call (0.5*S*E|R|) = ${0.5*S*ea:.3f}; 1c = {0.01/(0.5*S*ea)*100:.1f}% ; sd = {x.std()*1e4:.2f} bp")
# generic 25-min windows across the whole day (overlapping every 5 minutes), all sessions
allw = []
for d, g in df.groupby('d'):
    g = g.set_index(mins_from_open[g.index].values)
    c = g['close']
    for t in range(30, 391, 5):
        a, b = c.get(t-1-25, np.nan), c.get(t-1, np.nan)
        if not np.isnan(a) and not np.isnan(b): allw.append(np.log(b/a))
allw = np.array(allw)
ea = np.mean(np.abs(allw))
print(f"All 25-min windows in the day (every 5 min): mean|R| = {ea*1e4:.2f} bp -> fair ATM call = ${0.5*S*ea:.3f}; equivalent trading-time vol = {allw.std()/np.sqrt(25/98280)*100:.1f}% (sd of 25-min return / sqrt(25/98,280))")
# realised vol of 1-min returns
m1 = (df.groupby('d')['close'].transform(lambda s: np.log(s).diff())).dropna()
print(f"1-min realised vol, annualised in trading time (252 x 390 min): {m1.std()*np.sqrt(252*390)*100:.1f}%")
