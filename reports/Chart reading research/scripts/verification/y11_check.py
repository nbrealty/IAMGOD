# Independent check of Y11 (own code). Data: Kenneth French library files I downloaded myself.
import numpy as np, re, math

def read_monthly_block(path, start_marker, ncols):
    """Read the monthly block that follows a line containing start_marker; returns dict yyyymm -> list of floats."""
    out = {}
    with open(path) as f:
        lines = f.read().splitlines()
    i = 0
    if start_marker:
        while i < len(lines) and start_marker not in lines[i]:
            i += 1
        i += 1
    for line in lines[i:]:
        m = re.match(r"^\s*(\d{6})\s*,(.*)$", line)
        if m:
            vals = [float(x) for x in m.group(2).split(",")]
            out[int(m.group(1))] = vals[:ncols]
        elif out and line.strip()=="" :
            break
        elif out and not m:
            break
    return out

mom = read_monthly_block("frenchdata/F-F_Momentum_Factor.csv", None, 1)
mom = {k: v[0] for k, v in mom.items()}
print("Mom months:", len(mom), min(mom), max(mom))

ff = read_monthly_block("frenchdata/F-F_Research_Data_Factors.csv", None, 4)  # Mkt-RF,SMB,HML,RF
print("FF3 months:", len(ff), min(ff), max(ff))

dec_vw = read_monthly_block("frenchdata/10_Portfolios_Prior_12_2.csv", "Value Weight Returns -- Monthly", 10)
print("Decile VW months:", len(dec_vw), min(dec_vw), max(dec_vw))
dec_ew = read_monthly_block("frenchdata/10_Portfolios_Prior_12_2.csv", "Average Equal Weighted Returns -- Monthly", 10)
print("Decile EW months:", len(dec_ew), min(dec_ew), max(dec_ew))

def stats(label, keys):
    x = np.array([mom[k] for k in keys])/100.0
    n = len(x); mu = x.mean(); sd = x.std(ddof=1)
    t = mu/(sd/math.sqrt(n))
    cagr = np.prod(1+x)**(12/n)-1
    print(f"{label:<34} n={n:4d} months  mean*12={mu*12*100:6.2f}%/yr  geometric={cagr*100:6.2f}%/yr  ann.vol={sd*math.sqrt(12)*100:5.1f}%  t={t:5.2f}  Sharpe(mean/vol, excess-neutral)={mu*12/(sd*math.sqrt(12)):.2f}")

allk = sorted(mom)
print("\n--- Momentum factor (Mom = avg of 2 high prior-return portfolios minus avg of 2 low) ---")
stats("Full 1927-01..2026-08", allk)
stats("1927-01..1992-12 ('before 1993')", [k for k in allk if k <= 199212])
stats("1993-01..2026-08 ('after' Jan-1993)", [k for k in allk if k >= 199301])
stats("1927-01..1993-02", [k for k in allk if k <= 199302])
stats("1993-03..2026-08 (researcher split?)", [k for k in allk if k >= 199303])
stats("1927-01..1993-02 (Feb 1993 end)", [k for k in allk if k <= 199302])
stats("1927-01..1999-12", [k for k in allk if k <= 199912])
stats("2000-01..2026-08", [k for k in allk if k >= 200001])
stats("1993-03..1999-12", [k for k in allk if 199303 <= k <= 199912])
stats("2010-01..2026-08", [k for k in allk if k >= 201001])
print("\nJul/Aug 2026 Mom:", mom[202607], mom[202608])
# rank of Jul-Aug 2026 among 2-month...? and rank of individual months
worst = sorted(allk, key=lambda k: mom[k])[:20]
print("Worst 20 months of Mom:", [(k, mom[k]) for k in worst])
rank_aug = sorted(allk, key=lambda k: mom[k]).index(202608)+1
rank_jul = sorted(allk, key=lambda k: mom[k]).index(202607)+1
print("rank of Jul 2026 (1=worst):", rank_jul, "rank of Aug 2026:", rank_aug, "of", len(allk))

# ---- July-Aug 2026: top prior-return decile vs market
print("\n--- Jul-Aug 2026 ---")
top_vw = [dec_vw[k][9] for k in (202607, 202608)]
top_ew = [dec_ew[k][9] for k in (202607, 202608)]
lo_vw = [dec_vw[k][0] for k in (202607, 202608)]
def comp(l): 
    p=1.0
    for v in l: p*= (1+v/100.0)
    return (p-1)*100
print("Hi PRIOR (top) decile, value-weighted: Jul %.2f, Aug %.2f -> two-month compound %.2f%%" % (top_vw[0], top_vw[1], comp(top_vw)))
print("Hi PRIOR (top) decile, equal-weighted: Jul %.2f, Aug %.2f -> two-month compound %.2f%%" % (top_ew[0], top_ew[1], comp(top_ew)))
print("Lo PRIOR (bottom) decile, value-weighted: Jul %.2f, Aug %.2f -> two-month compound %.2f%%" % (lo_vw[0], lo_vw[1], comp(lo_vw)))
mkt = [ff[k][0]+ff[k][3] for k in (202607, 202608)]
print("Market total return (Mkt-RF+RF): Jul %.2f, Aug %.2f -> compound %.2f%%" % (mkt[0], mkt[1], comp(mkt)))
mkt_ex = [ff[k][0] for k in (202607, 202608)]
print("Market excess (Mkt-RF only):    Jul %.2f, Aug %.2f -> compound %.2f%%" % (mkt_ex[0], mkt_ex[1], comp(mkt_ex)))
# H1 2026 for top decile
h1 = [dec_vw[k][9] for k in range(202601, 202607)]
print("Top decile VW, Jan-Jun 2026 compound: %.1f%%" % comp(h1), " months:", h1)
h1m = [ff[k][0]+ff[k][3] for k in range(202601, 202607)]
print("Market, Jan-Jun 2026 compound: %.1f%%" % comp(h1m))
# Also check whether decile 10 minus decile 1 (WML from deciles) ~ Mom factor
wml = {k: dec_vw[k][9]-dec_vw[k][0] for k in dec_vw}
ks = sorted(set(wml)&set(mom))
a = np.array([wml[k] for k in ks]); b = np.array([mom[k] for k in ks])
print("corr(top-minus-bottom decile VW, Mom factor) = %.3f ; mean D10-D1 *12 = %.1f%% vs Mom %.1f%% (full sample)" % (np.corrcoef(a,b)[0,1], a.mean()*12, b.mean()*12))
