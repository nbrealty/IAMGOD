# Independent check of Y13: first-order daily autocorrelation of US total market return
# Data: Kenneth French library, "Fama/French 3 Factors [Daily]" (downloaded by me from mba.tuck.dartmouth.edu).
# market = Mkt-RF + RF (percent -> decimal). Own parsing code, own formulas.
import numpy as np, math, re, datetime as dt

rows = []
with open("frenchdata/F-F_Research_Data_Factors_daily.csv") as f:
    for line in f:
        m = re.match(r"^\s*(\d{8})\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)", line)
        if m:
            d = dt.datetime.strptime(m.group(1), "%Y%m%d").date()
            mkt_rf, smb, hml, rf = map(float, m.groups()[1:])
            rows.append((d, mkt_rf, rf))
dates = np.array([r[0] for r in rows])
mk = np.array([(r[1]+r[2])/100.0 for r in rows])
print("rows:", len(rows), "first", dates[0], "last", dates[-1])

def rho1(x):
    # first-order autocorrelation: pearson correlation of (x_t, x_{t-1}) over the window (pairs fully inside the window)
    a, b = x[1:], x[:-1]
    return float(np.corrcoef(a, b)[0,1])

def rho1_acf(x):
    # textbook sample autocorrelation: sum((x_t-m)(x_{t-1}-m)) / sum((x_t-m)^2)
    m = x.mean(); d = x - m
    return float((d[1:]*d[:-1]).sum()/(d*d).sum())

def window(y0, y1):
    idx = np.array([(d.year >= y0 and d.year <= y1) for d in dates])
    return mk[idx]

def report(label, y0, y1):
    x = window(y0, y1)
    n = len(x)
    r = rho1(x); r2 = rho1_acf(x)
    se = 1/math.sqrt(n)
    # heteroskedasticity-robust t-stat for rho1 (White-type): sqrt(n)*sum(d_t d_{t-1}) / sqrt(sum(d_t^2 d_{t-1}^2))
    d = x - x.mean()
    num = (d[1:]*d[:-1]).sum()
    den = math.sqrt(((d[1:]**2)*(d[:-1]**2)).sum())
    t_rob = num/den
    print(f"{label:<22}{n:>7} days  rho1={r:+.3f} (acf {r2:+.3f})  naive 95% CI +/-{1.96*se:.3f}  robust t={t_rob:+.1f}")
    return r

print("\n=== BY CALENDAR DECADE ===")
for y0 in range(1920, 2030, 10):
    y1 = y0+9
    lab = f"{max(y0,1926)}-{min(y1,2026)}"
    report(lab, y0, y1)

print("\n=== BY ERA (the researcher's windows, re-derived) ===")
for lab, y0, y1 in [("1926-1945",1926,1945),("1946-1969",1946,1969),("1970-1989",1970,1989),("1990-2009",1990,2009),("2010-2026",2010,2026),("2016-2026",2016,2026)]:
    report(lab, y0, y1)

print("\n=== Claim wording: 'decades before 2000' and 'since 2010' ===")
report("1926-1999 (all pre-2000)", 1926, 1999)
report("1946-1999", 1946, 1999)
report("1950-1999", 1950, 1999)
report("1960-1999", 1960, 1999)
report("1970-1999", 1970, 1999)
report("2000-2009", 2000, 2009)
report("2010-2026 (since 2010)", 2010, 2026)
report("2010-2019", 2010, 2019)
report("2020-2026", 2020, 2026)
report("2000-2026", 2000, 2026)
report("2024-2026 (recent)", 2024, 2026)

print("\n=== Year-by-year rho1 (noisy; ~250 obs/yr; se ~0.063) - count of years > +0.10 and < -0.10 by era ===")
yr = {}
for y in range(1926, 2027):
    x = window(y, y)
    yr[y] = rho1(x)
for lab, y0, y1 in [("1926-1945",1926,1945),("1946-1969",1946,1969),("1970-1989",1970,1989),("1990-1999",1990,1999),("2000-2009",2000,2009),("2010-2026",2010,2026)]:
    vals = [yr[y] for y in range(y0, y1+1)]
    print(f"{lab}: mean of yearly rho1 = {np.mean(vals):+.3f}, min {min(vals):+.2f}, max {max(vals):+.2f}, years>0: {sum(v>0 for v in vals)}/{len(vals)}")

# Sensitivity: is it a pre-1952 6-day-week artefact / nonsynchronous trading? use Mkt-RF only for 2010-2026
print("\n=== Sensitivity: excess return Mkt-RF only (no RF added) ===")
mk_ex = np.array([r[1]/100.0 for r in rows])
for lab,y0,y1 in [("1946-1969",1946,1969),("1970-1989",1970,1989),("2010-2026",2010,2026)]:
    idx = np.array([(d.year >= y0 and d.year <= y1) for d in dates])
    print(lab, f"{rho1(mk_ex[idx]):+.3f}")
