"""X7 independent analysis of Cboe history CSVs downloaded by checker2 on 2026-09-29 from cdn.cboe.com (own code)."""
import pandas as pd, numpy as np
D = "/tmp/c2/cboe/"
files = ["VIX", "VIX1D", "VIX9D", "VIX3M", "VVIX", "SKEW"]
dfs = {}
for s in files:
    df = pd.read_csv(f"{D}{s}_History.csv")
    df["DATE"] = pd.to_datetime(df["DATE"], format="%m/%d/%Y")
    dfs[s] = df
    # gaps: largest gap between consecutive dates
    gaps = df["DATE"].diff().dt.days
    print(f"{s:6s} rows={len(df):5d} first={df.DATE.iloc[0].date()} last={df.DATE.iloc[-1].date()} cols={list(df.columns[1:])} max gap days={int(gaps.max())} at {df.DATE[gaps.idxmax()].date()}; dup dates={int(df.DATE.duplicated().sum())}; null cells={int(df.isna().sum().sum())}")
print()
v = dfs["VIX1D"].copy()
print("VIX1D: rows where OPEN==CLOSE==HIGH==LOW:", int(((v.OPEN==v.CLOSE)&(v.HIGH==v.LOW)&(v.OPEN==v.HIGH)).sum()), "of", len(v))
flat = (v.OPEN==v.CLOSE)&(v.HIGH==v.LOW)&(v.OPEN==v.HIGH)
print("  first non-flat (real OHLC) date:", v.DATE[~flat].iloc[0].date(), "; last flat date:", v.DATE[flat].iloc[-1].date())
print("  flat rows by year:", v[flat].groupby(v.DATE.dt.year).size().to_dict())
print("  non-flat rows by year:", v[~flat].groupby(v.DATE.dt.year).size().to_dict())
print()
# share of days close > open: several windows
def share(df, label):
    up = (df.CLOSE > df.OPEN); dn = (df.CLOSE < df.OPEN); eq = (df.CLOSE == df.OPEN)
    print(f"  {label:58s} n={len(df):5d} close>open {up.sum():4d} ({up.mean()*100:5.1f}%)  close<open {dn.sum():4d}  equal {eq.sum():4d}  mean open {df.OPEN.mean():.2f} mean close {df.CLOSE.mean():.2f}")
share(v, "all rows in file")
share(v[~flat], "rows with genuine OHLC (not flat)")
share(v[v.DATE >= "2024-09-03"], "3 Sep 2024 to 28 Sep 2026 (researcher's window)")
print("  count of rows from 2024-09-03 through 2026-09-28:", int(((v.DATE>='2024-09-03')&(v.DATE<='2026-09-28')).sum()))
print("  count of days with non-null OPEN and CLOSE (whole file):", int(v[['OPEN','CLOSE']].notna().all(axis=1).sum()))
# find what start date gives exactly 519 rows to 2026-09-28
for start in ["2024-09-03","2024-09-04","2024-09-05","2024-09-02","2024-08-30"]:
    n=int(((v.DATE>=start)&(v.DATE<='2026-09-28')).sum()); print("   start",start,"->",n,"rows")
# year by year
print()
for y in sorted(v.DATE.dt.year.unique()):
    sub = v[v.DATE.dt.year==y]
    share(sub, f"year {y}")
# when did genuine OHLC begin? look at the first 20 non-flat and last 5 flat
print()
print(v[~flat].head(5).to_string(index=False))
print(v[flat].tail(3).to_string(index=False))
# Add sanity: what does the median close-open look like
d = (v.CLOSE - v.OPEN)[v.DATE >= "2024-09-03"]
print("\nWindow from 2024-09-03: mean (close-open) = %.2f pts, median = %.2f" % (d.mean(), d.median()))
