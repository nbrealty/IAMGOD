# Fact-check corrections to the chart-reading research (read this first)

*29 Sept 2026. Seven research reports (R1 to R7) were written on 28 Sept 2026 by separate researchers. Four independent
fact-checkers then went through the claims the plan leans on, in two pairs (group X: costs, intraday evidence, options;
group Y: technical analysis, AI, hype, long-term trends). Each pair checked the same list without seeing the other's work.
Where a claim was the researcher's own calculation, the checker redid it with their own code. The four checker reports are
in `Fact-check reports/`. This file **supersedes the numbers in R1 to R7** where they differ. The reports themselves are
kept as written.*

**Score:** X checkers 30 and 14 claims: X1 contradicted (both checkers, same finding); Y checkers 31 sub-claims and 14
claims: none contradicted, none unfindable. Nothing that changes a conclusion, but one date, a few numbers and several
attributions were wrong. Both checkers in each pair made the same corrections, which is a good sign.

## A. The one that matters: a date that would have driven a cost re-check

| # | Report | What the report said | What the sources say |
|---|---|---|---|
| E1 | R3 (summary 12, section 2c, 4a item 7, 5) | The SEC half-penny tick and lower access-fee cap start on the first business day of November 2026 (Mon 2 Nov) | **SEC Release 34-105656 (11 Jun 2026) delayed them to the first business day of November 2027**, and the SEC has asked its staff to review Rules 610(c) and 612 by year-end, so they could change again. The $0.015 test (time-weighted average quoted spread) is right. SEC's own 2023 figures had SPY at $0.0105 and QQQ at $0.0116, so both would probably qualify when it starts. **Do not plan a November 2026 cost re-check.** Keep measuring spreads on real fills. |

## B. Numbers that changed

| # | Report | Report said | Correct |
|---|---|---|---|
| E2 | R3 | "NY Fed staff report: overnight drift about 3.7% a year before 2021, about zero since" | It is a NY Fed *Liberty Street Economics blog post* (Boyarchenko, Larsen, Whelan, 1 Jul 2026) about the **2:00-3:00 a.m. ET hour in S&P 500 E-mini futures** (1998-2020 versus 2021-2025). Not a Staff Report, and not about stock-index returns in general. The Sharpe of -0.5 after spreads (RFS 2023) is for the one-hour version; the 1:30-3:30 window goes 1.3 to 0.3, and a "buy the dip" variant kept 1.1 after costs (2004-2020). It cannot be traded in regular-hours SPY or QQQ. |
| E3 | R3 | "Pre-FOMC drift (49 bp) gone after 2015" | 49 bp is the 1994-2011 figure (Lucca and Moench). "Gone after 2015" rests on one paper that ends in 2019. Say "faded after 2015 in one study; later evidence mixed". |
| E4 | R3 | Gao et al. R-squared 1.7% | Gao et al.'s own figure is 1.6% (2.6% combined); 1.7% comes from a replication (Limkriangkrai). Baltussen et al. (slope 0.066, t 4.78 on negative-gamma days versus 0.008, t 1.03; R-squared about 3.6%) confirmed. |
| E5 | R3 | "About 1,100 trades to detect a +1 bp edge at t = 3" | 1,100 is for the usual 5% bar (t = 1.96). For **t = 3 it is about 2,100 to 2,130** trades, and for p < 0.0018 (a stricter bar R3 also mentions) about 2,270. Cost arithmetic (0.47 bp round trip; needed hit rates 82%, 64%, 56%) confirmed by both checkers. |
| E6 | R5 | ADX(14) above 25 in 34-37% of noise bars | **37-40%** (a bar-building bug in the simulation). R-squared above 0.8 in about 15% of windows and Mann-Kendall "finding" a trend in 56-92% of paths reproduced. |
| E7 | R4 (H3 note) | A 25-minute at-the-money SPY call costs about $0.73, so a 1-cent half-spread is 1.4% | $0.73 is the price of a call that **expires 25 minutes after purchase**, counting trading time only. In calendar time (Cboe's VIX1D convention) it is about $0.32, and from SPY's realised moves about $0.29. So a 1-cent half-spread is about **2.5-3.5%** and a round trip **5-7%**, about double. R4's conclusion (a 33% average loss is not explained by spreads alone) stands. |
| E8 | R4 (F20) | Vilkov 0DTE paper: after the August 2026 fix no strategy keeps a positive net Sharpe | The conditional put-ratio rule went from +0.93 to -0.75. One unconditional structure ("Risk Reversal") is still **+0.10**. The SSRN abstract has not been revised. |
| E9 | R4 (F16) | Beckmeyer et al.: about 60% of retail 0DTE losses are costs | The text says about 60%, but the paper's own Table 2 implies **76%** (70% since May 2022). "Costs" means spreads only. |
| E10 | R4 (data table) | Six Cboe files, all open/high/low/close | VVIX and SKEW have **one value column**. VIX1D rows before 3 Apr 2023 have no separate open (open = high = low = close). The 90.8% (471 of 519 days; 92.1% on the 875 days with real open/high/low/close) reproduced. Use `cdn-api.cboe.com` (the old host redirects). |
| E11 | R2, R5 | Round-number trading costs about $1 billion a year (Bhattacharya, Holden, Jacobsen 2012) | About **$813 million a year** (range $606M to $1,021M; the abstract says "approaching $1 billion"): US stocks 2001-2006, a rough scale-up from 100 stocks. |
| E12 | R2 | Rink (2023): profits vanish at 20 bp costs | At 20 bp per trade **9 of 41 markets** (5 of 23 developed, 4 of 18 emerging) still had significant rules. Predictability faded and vanished in the last years of the sample (data end May 2016). |
| E13 | R2, R7 | Jiang-Kelly-Xiu costs "not netted out"; 175% turnover; rescaling "critique" | The published paper does report net-of-cost Sharpe ratios "as high as 4.0, 1.5 and 0.9 for weekly, monthly and quarterly **equal-weight** strategies" (Internet Appendix). 175% turnover is the equal-weight figure; value-weighted turnover is 181-187% and value-weighted Sharpe 0.45-0.49 (momentum 0.36). The finding that a linear model on the rescaled numbers gets much of the edge is the **authors' own** result, not an outside critique. |
| E14 | R7 | CharXiv: best model 47.1% versus humans 80.5% | A **June 2024** snapshot. In 2026 the top 20 models self-report 82-93% on the same test. The "AI reads charts worse than people" headline is out of date; our own small blind picture test (R8: 36 pictures, easy questions, one model) is the only direct evidence we have. The Wang (2026) fragility paper and the "AUC 0.47-0.52" candlestick paper are the same study. |
| E15 | R6, R7 | Medallion's 63% compound return "disputed by a critic" | **Cornell (2020) is the source of 63.3%** (gross, 1988-2018). Guo and Liu dispute it (about 32% before fees, probably under 35%). |
| E16 | R6 | Trading costs take 40-45% of momentum's gross profit (Novy-Marx and Velikov) | **34%-53%** depending on design (49% for plain decile momentum), 1973-2012. |
| E17 | R5 | US daily autocorrelation "flipped from +0.2 to -0.1" | About +0.16 to +0.20 in 1946-89, about +0.08 in the 1990s, slightly negative since 2000. The -0.10 for 2010-26 is **mostly the 2020 crash year** (excluding 2020: -0.03). Single pre-2000 decades run +0.05 to +0.29. |
| E18 | R5, R7 | Bollen et al.: 87.6% accuracy | The preprint said 87.6%; the published figure is **86.7%** (13 of 15 days). |
| E19 | R6 | July-August 2026 momentum crash: -15.5% | -15.5% is the **value-weighted** top decile; equal-weighted it is -11.6% (market +2.6%). |
| E20 | R2, R7 | Luck table: 28 tries give 1.45; 240 tries give 2.0 | Exact: **28 tries give 1.42**; **2.0 needs about 258** tries. The reports are consistent with each other. |
| E21 | R3 (section 5) | The SEC fee rate resets every October | It does not reset every October. |

## C. Confirmed (checked in the source or recomputed independently)

- R6's own trend-rule results reproduced from Kenneth French's data by both group-Y checkers: 10-month rule 9.8% a year versus 10.3% buy-and-hold, worst loss about -43% versus -84%, lagging in 44 of 98 years; $1 to $5.6 versus $13.2 since April 2009.
- The independent replications of the popular SPY momentum system: Paz (SSRN 7290621: Sharpe 1.34 in sample, 0.39 out of sample, about May 2024-Mar 2026), Fetna (SSRN 7428398: 0 of 225 opening-range cells survive costs; **nine US futures markets**, not SPY/QQQ), and a third, Delgado (SSRN 7323419): pooled Sharpe 0.35, strong to Aug 2025, then -8.1% (Sharpe -0.46) for Sep 2025-Aug 2026. All are single-author, unrefereed preprints on short out-of-sample windows.
- Alpaca's real-time options data (OPRA, in the $99 a month bundle); the free options quotes are "indicative"; Bulkowski's own test of IBD distribution days; SpotGamma's statement that GEX is a model output with a sign assumption; order-flow forecasts lasting about two price changes; ES-SPY correlation near zero at 1 ms; news priced in 5 ms.
- SEC actions on social-media manipulation (Dec 2022; 6 Feb 2026); Boudoukh et al. (news explains 49.6% of overnight but 12.4% of intraday idiosyncratic volatility); FINSABER; Hurst-Ooi-Pedersen's signal-speed result.

## D. Not verified, or limits of the checks

- Real SPY/QQQ quotes and real option spreads: no data source was available to the checkers, so the 2-cent stock spread and 1-cent option half-spread remain assumptions until measured on our own fills.
- SSRN pages were blocked (HTTP 403); abstracts came via Crossref and the authors' GitHub repositories. The full texts of Paz and Fetna were not read.
- The published (not working-paper) tables of Jiang-Kelly-Xiu were partly blocked.
- **Cboe's terms are restrictive**: personal non-commercial use of the downloads; no explicit permission for programmatic use. Fine for private research; **do not commit or share the Cboe files**; write to permissions@cboe.com if the use grows.
- Alpha Arena results, systematic-fund Sharpe ratios and the final SEC access-fee rule text remain unverified.
- Every researcher and checker ran out of web searches (200 each), so 2024-2026 academic coverage is thinner than it looks.
