# Independent check of Y10: 10-month simple moving average (SMA) timing rule on the total US market.
# Data: Kenneth French monthly Fama/French Research Data Factors (downloaded by me).
# Total market return r_m = Mkt-RF + RF (percent). Cash return = RF.
import numpy as np, re, math

rows = {}
with open("frenchdata/F-F_Research_Data_Factors.csv") as f:
    for line in f:
        m = re.match(r"^\s*(\d{6})\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)", line)
        if m:
            rows[int(m.group(1))] = (float(m.group(2)), float(m.group(5)))
        elif rows and line.strip()=="" :
            break
        elif rows and not m:
            break
months = sorted(rows)
print("months", len(months), months[0], months[-1])
mkt = np.array([(rows[k][0]+rows[k][1])/100.0 for k in months])
rf  = np.array([rows[k][1]/100.0 for k in months])
n = len(months)

# total return index at each month-end, P_0 = 1 at end of month "before" first month
P = np.cumprod(1+mkt)

def rule(L=10, include_current=True):
    """signal at end of month t: P_t > mean of last L month-end levels (including t if include_current).
       Position during month t+1 = market if signal else cash."""
    sig = np.full(n, False)
    valid = np.full(n, False)
    for t in range(n):
        if include_current:
            if t >= L-1:
                sma = P[t-L+1:t+1].mean(); sig[t] = P[t] > sma; valid[t] = True
        else:
            if t >= L:
                sma = P[t-L:t].mean(); sig[t] = P[t] > sma; valid[t] = True
    # return for month t+1 using signal at t
    strat = np.full(n, np.nan)
    for t in range(n-1):
        if valid[t]:
            strat[t+1] = mkt[t+1] if sig[t] else rf[t+1]
    return strat, sig, valid

def stats(r, label, months_sel):
    r = r[months_sel]
    k = len(r)
    growth = np.prod(1+r)
    cagr = growth**(12/k)-1
    curve = np.cumprod(1+r)
    peak = np.maximum.accumulate(np.concatenate([[1.0], curve]))[1:]
    dd = (curve/peak-1).min()
    vol = r.std(ddof=1)*math.sqrt(12)
    return cagr, dd, vol, growth

def run(L, include_current, start_key, end_key=202608, label=""):
    strat, sig, valid = rule(L, include_current)
    keys = np.array(months)
    sel = (keys >= start_key) & (keys <= end_key) & ~np.isnan(strat)
    c1, d1, v1, g1 = stats(strat, "rule", sel)
    c2, d2, v2, g2 = stats(mkt, "bh", sel)
    print(f"{label:<44} n={sel.sum():4d} first={keys[sel][0]} last={keys[sel][-1]} | RULE CAGR {c1*100:5.2f}% maxDD {d1*100:6.1f}% vol {v1*100:4.1f}% end$ {g1:8.2f} | B&H CAGR {c2*100:5.2f}% maxDD {d2*100:6.1f}% vol {v2*100:4.1f}% end$ {g2:8.2f}")
    return strat, sel

print("\n=== Main spec: signal at month-end t uses P_t and the 9 prior month-ends (10 levels incl. current); applied to month t+1 ===")
strat, sel = run(10, True, 192700, label="Faber 10m SMA (incl current), from first signal")
print("first strategy month is", np.array(months)[sel][0])

# --- calendar years
keys = np.array(months)
def calyear_table(strat, sel):
    yrs = {}
    for k, s, b, ok in zip(keys, strat, mkt, sel):
        if ok:
            y = k//100
            yrs.setdefault(y, [1.0, 1.0, 0])
            yrs[y][0] *= (1+s); yrs[y][1] *= (1+b); yrs[y][2] += 1
    return yrs
yrs = calyear_table(strat, sel)
full = {y: v for y, v in yrs.items() if v[2] == 12}
lag = [y for y, v in full.items() if v[0] < v[1]]
print(f"full calendar years: {len(full)} ({min(full)}-{max(full)}); rule lagged B&H in {len(lag)} of them; rule beat/tied in {len(full)-len(lag)}")
allyrs = {y: v for y, v in yrs.items()}
lag_all = [y for y, v in allyrs.items() if v[0] < v[1]]
print(f"including partial years ({len(allyrs)} calendar years incl. 1927 & 2026 partial): rule lagged in {len(lag_all)}")
print("partial years:", [(y, v[2]) for y, v in yrs.items() if v[2] != 12])
# 2026 YTD
for y in (2019, 2023, 2026):
    print(y, "rule %.1f%% vs B&H %.1f%%" % ((yrs[y][0]-1)*100, (yrs[y][1]-1)*100))

print("\n=== Since April 2009 ===")
for start in (200904, 200905):
    run(10, True, start, label=f"from month {start} (returns start {start})")
# what if invested at end of Mar-2009 signal etc - check sensitivity
strat, sel = run(10, True, 200904, label="April 2009 start")

print("\n=== Sensitivity of the headline numbers to timing choices ===")
run(10, True, 192700, label="SMA incl current month (Faber)")
run(10, False, 192700, label="SMA of prior 10 month-ends (excl. current)")
# Same rule but signal used in SAME month (look-ahead - to show it matters)
def lookahead():
    sig = np.full(n, False)
    for t in range(9, n):
        sig[t] = P[t] > P[t-9:t+1].mean()
    r = np.where(sig, mkt, rf); r[:9] = np.nan
    return r
r_la = lookahead()
sel_la = (~np.isnan(r_la)) & (keys<=202608)
c1,d1,v1,g1 = stats(r_la,"la",sel_la); print(f"LOOK-AHEAD (signal and return same month; NOT tradable): CAGR {c1*100:.2f}% maxDD {d1*100:.1f}%")
# start after 1928 to avoid partial-year distortion: 1928-01..2025-12 (98 full calendar years)
run(10, True, 192801, 202512, label="1928-01..2025-12 (98 full calendar years)")
run(10, True, 192700, 202512, label="1927..2025")
# arithmetic vs geometric
strat0, sel0 = run(10, True, 192700, label="(repeat) main")
r = strat0[sel0]; b = mkt[sel0]
print("arithmetic mean*12: rule %.2f%% ; B&H %.2f%%" % (r.mean()*1200, b.mean()*1200))
print("Sharpe (excess over RF): rule %.2f ; B&H %.2f" % (((r-rf[sel0]).mean()/(r-rf[sel0]).std(ddof=1))*math.sqrt(12), ((b-rf[sel0]).mean()/(b-rf[sel0]).std(ddof=1))*math.sqrt(12)))
# months invested, switches per year
sigm = np.array([ (P[t] > P[t-9:t+1].mean()) if t>=9 else False for t in range(n)])
sw = np.sum(sigm[10:] != sigm[9:-1]); yrs_len = (n-10)/12
print("in market share of months: %.1f%%; position changes per year: %.2f" % (sigm[9:-1].mean()*100, sw/yrs_len))
# worst drawdown dates for rule and B&H
def dd_dates(x, sel):
    xs = x[sel]; ks = keys[sel]
    curve = np.cumprod(1+xs); peak = np.maximum.accumulate(curve)
    dd = curve/peak-1; i = dd.argmin(); j = curve[:i+1].argmax()
    return ks[j], ks[i], dd[i]
print("rule worst drawdown peak/trough:", dd_dates(strat0, sel0))
print("B&H  worst drawdown peak/trough:", dd_dates(mkt, sel0))
