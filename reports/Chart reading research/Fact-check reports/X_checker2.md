# Group X fact-check (costs, intraday evidence, options) - checker 2

Checked on 29 Sep 2026 against primary sources (regulator orders, papers, exchange and broker pages, original data files). Research only: nothing in the repo was touched, no broker or trading API was called. Where the claim is an "own calculation" I re-derived it with my own code (folder `checker2_scripts/`, outputs in `checker2_scripts/outputs/`, saved text of key pages in `checker2_evidence/`).

Working order was X14 down to X1. The report below is in normal order.

## 1. Scoreboard

| Verdict | Count | Claims |
|---|---|---|
| CONFIRMED | 7 | X3, X4, X6, X8, X10, X11, X13 (X13: arithmetic confirmed, but see its caveat) |
| CONFIRMED_BUT_DIFFERENT | 6 | X2, X5, X7, X9, X12, X14 |
| CONTRADICTED | 1 | X1 (the start date has been moved to November 2027) |
| NOT_FOUND | 0 | |
| UNREACHABLE | 0 (some pages were blocked, but every claim was reached through another route; see section 4) | |

Numbers that changed: X1 (date), X5 (Gao 1.6% not 1.7%), X9 (cost share 60% in the text, 70-76% in the paper's own table), X12 ("t = 3" needs about 2,130 trades, not 1,100), X14 (ADX share 37-40%, not 34-37%). X13 depends on the time convention (see below).

## 2. Summary table

| # | Claim (short) | Verdict | What the source really says (key numbers) | Primary source |
|---|---|---|---|---|
| X1 | Half-penny tick and lower access-fee cap start 2 Nov 2026; qualifies if time-weighted average quoted spread (TWAQS) is $0.015 or less | **CONTRADICTED** on the date. Qualification rule CONFIRMED | SEC order of 11 Jun 2026 moved both to "the first business day of November 2027" (Mon 1 Nov 2027). Rule: $0.005 tick if TWAQS is $0.015 or less | https://www.sec.gov/files/rules/exorders/2026/34-105656.pdf ; https://www.sec.gov/files/rules/final/2024/34-101070.pdf |
| X2 | NY Fed July 2026 staff report: overnight drift 3.7% a year before 2021, about zero since; Boyarchenko et al. Sharpe 1.1 before spreads, -0.5 after | CONFIRMED_BUT_DIFFERENT | Numbers right. But the 2026 item is a Liberty Street Economics blog post, it is about the 2:00-3:00 a.m. ET hour in E-mini futures, and the 2023 paper's other variants stay positive after costs (0.3 and 1.1) | https://libertystreeteconomics.newyorkfed.org/2026/07/the-disappearing-overnight-drift/ ; https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr917.pdf |
| X3 | Pre-FOMC drift (about 49 bp) gone after 2015 | CONFIRMED (with caveats) | Lucca-Moench: 49 bp (1994-2011). Kurov-Wolfe-Gilbert: "essentially disappeared after 2015"; press-conference meetings 44 bp (2011-15) then 9 bp (2016-19). Data end Dec 2019. Fed Board FEDS 2026-023: 16 bp, t 1.50, for Apr 2011-Dec 2023 | https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr512.pdf ; https://www.skidmore.edu/economics/documents/KurovWolfeGilbert-TheDisappearingPre-FOMC-Announce-Drift-200914.pdf |
| X4 | Paz 2026 replication: Sharpe 1.34 in sample, 0.39 out of sample; Fetna: 0 of 225 ORB variants survive costs | CONFIRMED | Both exist as 2026 SSRN preprints with exactly those numbers. Fetna is on 9 US futures at $25 a round trip, not SPY | https://doi.org/10.2139/ssrn.7290621 ; https://doi.org/10.2139/ssrn.7428398 |
| X5 | Baltussen et al.: slope 0.066 (t 4.78) on negative-gamma days vs 0.008 (t 1.03); R-squared 3.6%. Gao et al.: R-squared 1.7% | Baltussen CONFIRMED. Gao CONFIRMED_BUT_DIFFERENT | Baltussen Table 7 matches (3.58% is the R-squared on negative-gamma days only). Gao's own R-squared is 1.6%; 1.7% is an independent replication (1996-2013) | https://www3.nd.edu/~zda/intramom.pdf ; Gao et al. text (see X5) |
| X6 | Vilkov 0DTE: after Aug 2026 cost-units fix, no strategy keeps a positive net Sharpe (was +0.93) | CONFIRMED | Repo README and KNOWN-ISSUES say exactly this; +0.93 -> -0.75 is the conditional put-ratio strategy | https://github.com/vilkovgr/0dte-strategies |
| X7 | Cboe free history files to 28 Sep 2026; VIX1D closed above open on 90.8% of 519 days; terms of use | CONFIRMED_BUT_DIFFERENT | Files and dates confirmed; 471/519 = 90.8% reproduced exactly. But VVIX and SKEW files have one value column only, VIX1D open/high/low/close are flat before 3 Apr 2023, and Cboe's terms do not clearly allow programmatic use | https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX1D_History.csv ; https://www.cboe.com/terms |
| X8 | Alpaca OPRA about $99 a month; indicative feed not real OPRA; 0DTE options lack Greeks | CONFIRMED | $99/mo is the Algo Trader Plus bundle (also all-exchange stock data). Docs say indicative quotes "are not actual OPRA quotes" and 0DTE contracts "won't have Greeks" | https://alpaca.markets/data ; https://docs.alpaca.markets/docs/market-data-faq |
| X9 | Beckmeyer et al.: about 60% of retail 0DTE losses are costs; SEC staff (DERA): retail limit orders are cheap | CONFIRMED_BUT_DIFFERENT | The 60% sentence is in the paper, but its Table 2 implies 70-76%. The DERA paper is a working paper by 4 authors (2 at the SEC), about customer non-marketable limit orders in SPXW; it does not say retail makes money | https://wp.lancs.ac.uk/fofi2024/files/2024/04/FoFI-2024-146-Leander-Gayda.pdf ; https://www.sec.gov/files/dera-hope-reasonable-prc-2503.pdf |
| X10 | Bulkowski's test: distribution-day clusters do not predict declines in rising markets; SpotGamma: GEX is a model output with a sign assumption | CONFIRMED | Both quotes found word for word | https://www.thepatternsite.com/DistributionDay.html ; https://spotgamma.com/gamma-exposure-gex/ |
| X11 | Order-flow forecasts last about two price changes; ES-SPY correlation 0.008 at 1 ms; macro news priced within 5 ms | CONFIRMED (all three) | Kolm et al. abstract; Budish et al. 0.0080 at 1 ms (2011 data); Chordia et al. "within five milliseconds" | see X11 |
| X12 | OWN CALC: round trip 0.47 bp; hit rates 82/64/56%; about 1,100 trades to detect +1 bp "at t = 3" | CONFIRMED_BUT_DIFFERENT | Cost and hit-rate arithmetic right. The 1,100 is for p<0.05 (critical t = 1.96); a critical t of 3 needs about 2,130 trades | my scripts `x12_calc.py`, `x12_moves.py` |
| X13 | OWN CALC: 25-minute ATM SPY call about $0.73; 1 cent = 1.4% | CONFIRMED (arithmetic), assumption-sensitive | I get $0.731-0.734 and 1.36%. IV 12-20% gives $0.59-0.98 (1.7%-1.0%). Read in calendar time the same 15% gives $0.32 (3.2%); SPY's realised moves in the lab's own bars imply about $0.29 | `x13_bs.py`, `x13_empirical_premium.py` |
| X14 | OWN CALC: pure random walks give R-squared above 0.8 in about 15% of windows, ADX(14) above 25 in 34-37% of bars, Mann-Kendall "trend" in 56-92% of paths | CONFIRMED_BUT_DIFFERENT | R-squared and Mann-Kendall reproduce. ADX: I get 37-40% (49% if bars have no intrabar range). Their ADX simulation used invalid bars | `x14_*.py` |

## 3. Claim-by-claim notes

### X1. SEC half-penny tick and access-fee cap

**Verdict: CONTRADICTED (date). Qualification rule CONFIRMED.**

Timeline, all from SEC documents:
- 18 Sep 2024, Release 34-101070 (adopting release): compliance for the tick rule (Rules 600(b)(89)(i)(F) and 612) and the access-fee cap (Rule 610) "The first business day of November 2025."
- 12 Dec 2024: partial stay while a court challenge ran. 14 Oct 2025: the D.C. Circuit denied the petition for review.
- 31 Oct 2025, Release 34-104172 (90 FR 51418): relief "until the first business day of November 2026".
- **11 Jun 2026, Release No. 34-105656**, "Order Granting Temporary Exemptive Relief ... from Compliance with Rule 600(b)(89)(i)(F), Rule 610(c) and Rule 612": "the Commission is providing temporary exemptive relief until the first business day of November 2027", and in the ordering paragraph "... from compliance with Rules 600(b)(89)(i)(F), 610(c), and 612, as amended in the Adopting Release until the first business day of November 2027." Reason given: "to allow for an orderly implementation of these Rules in light of other regulatory initiatives scheduled for the balance of 2026." The first business day of November 2027 is Monday 1 Nov 2027 (I computed it).
- The SEC's list of exemptive orders (https://www.sec.gov/rules-regulations/exchange-act-exemptive-notices-orders) shows no later order on these rules as of 29 Sep 2026 (later entries are about other matters). The SEC's own 11 Jun 2026 statement (https://www.sec.gov/newsroom/speeches-statements/atkins-statement-minimum-pricing-increments-access-fee-caps-061126, text obtained through a page-reading tool, not raw HTML) also says the Chairman asked staff to look again at Rules 610(c) and 612 by year-end "to determine whether potential changes ... may be appropriate", so the rules themselves could change. A trade-press item (https://tradeinformer.com/regulations/sec-extends-nms-relief-rule-611-repeal-2027, 12 Jun 2026) agrees.
- The researcher's R3 text ("start on the first business day of November 2026 (Monday 2 Nov)") is out of date. R3 (open question 6, source 51) relied on the 20 Mar 2026 notice of the MEMX application (Release 34-105058) and said it had not checked whether the SEC acted afterwards; the SEC did act, on 11 Jun 2026.

Qualification rule (adopting release, Rule 612(b)(2)): "(ii) $0.005, if the Time Weighted Average Quoted Spread for the NMS stock during the Evaluation Period was equal to or less than $0.015" and "(i) $0.01, if ... greater than, $0.015". Definitions: TWAQS is "the average dollar value difference between the NBB and NBO during regular trading hours where each instance of a unique NBB and NBO is weighted by the length of time that the quote prevailed"; Evaluation Periods are January-March and July-September, with each result operative for six months from the first business day of May or November. It applies to quotes and orders priced at $1.00 or more. The release also says: "The Commission is not adopting a minimum pricing increment for trades." Access-fee cap: from 30 mils ($0.003) to $0.001 per share for quotes of $1.00 or more.

SPY and QQQ: the SEC names them. Footnote 801 of the adopting release (Bloomberg data): "These NMS stocks were ETFs: SPY and QQQ. As of Nov. 30, 2023, ... SPY ... average bid-ask spread over the previous 30 trading days was $0.0105. For QQQ ... $0.0116." So on the SEC's own 2023 numbers both would qualify for the half-penny tick. The lab's one-day sample (28 Sep 2026) had averages of 1.9 and 2.2 cents, which would not qualify, but that is one down day, sampled three times a minute; the real test is the time-weighted spread over a full three-month period. Unresolved until measured.

So what for us: do not plan around a November 2026 tick change; it is now November 2027 at the earliest and may be reworked. Keep costing trades with the spread we actually measure.

### X2. Overnight drift (NY Fed 2026; Boyarchenko et al. 2023)

**Verdict: CONFIRMED_BUT_DIFFERENT.**

- The 2026 source is "The Disappearing Overnight Drift", Liberty Street Economics (a NY Fed blog), 1 Jul 2026, by Nina Boyarchenko (NY Fed) with Lars Larsen and Paul Whelan (business-school academics). It is a blog post with a "views ... do not necessarily reflect the position of the New York Fed" disclaimer, not a Staff Report.
- Quote: "the 2:00-3:00 window that previously generated roughly 3.7 percent per annum has averaged close to zero since 2021." Sample: S&P 500 E-mini futures, 1998-2020 (5,691 days) versus Jan 2021-Dec 2025 (1,245 days). In 1998-2020 that hour was "responsible for more than 60 percent of the contract's 5.9 percent annualized close-to-close return". Same pattern in NQ and YM. The 3.7% is therefore about that one overnight hour in futures, not "US stock-index returns" in general.
- Paper: Boyarchenko, Larsen, Whelan, "The Overnight Drift", NY Fed Staff Report 917 (Feb 2020, revised Aug 2022), Review of Financial Studies 36(9):3502-3547 (2023). Quote: "Pre- transaction costs, a trading strategy that goes long the S&P 500 futures between 2:00 and 3:00 earns a Sharpe ratio of 1.1 and accounting for bid-ask spreads this reduces to -0.5." Sample 2004.1-2020.12. The same passage adds that the wider 1:30-3:30 window goes from 1.3 to 0.3 after costs, and the "buy the dip" version keeps a Sharpe of 1.1 after costs. So "-0.5" is right only for the simplest one-hour version.

So what for us: this futures-hour edge has vanished since 2021 and could not be traded in regular-hours SPY/QQQ anyway; do not build on it.

### X3. Pre-FOMC drift

**Verdict: CONFIRMED, with caveats.**

- Lucca and Moench (Journal of Finance 70(1):329-371, 2015; NY Fed Staff Report 512): "since 1994, the S&P500 index has on average increased 49 basis points in the 24 hours before scheduled FOMC announcements" (131 meetings, t above 4.5).
- Kurov, Wolfe, Gilbert, "The disappearing pre-FOMC announcement drift", Finance Research Letters 40, 101781 (2021): "the pre-FOMC drift essentially disappeared after 2015 in both announcements accompanied by press conferences and announcements not accompanied by press conferences." Their Table 2: press-conference meetings averaged 0.445% (about 44 bp) in Apr 2011-Dec 2015 and 0.092% in Jan 2016-Dec 2019; no-press-conference meetings were close to zero.
- More recent Federal Reserve Board evidence, found in my own search: Knox and Vissing-Jorgensen, "The Effect of the Federal Reserve on the Stock Market: Magnitudes, Channels and Shocks", FEDS 2026-023 (May 2026; https://www.federalreserve.gov/econres/feds/files/2026023pap.pdf), Table 4, 2:00 p.m.-to-2:00 p.m. pre-FOMC return on the S&P 500: 0.49% (t 4.61) for Sep 1994-Mar 2011, but 0.16% (t 1.50, not significant) for Apr 2011-Dec 2023. They do not split at 2015, and they also mention "the 20 bps per meeting overnight drift since March 2011". So through 2023 the drift is about a third of the original size and no longer statistically distinguishable from zero, which supports "faded", though "gone" is slightly stronger than the data.
- Caveats: Kurov et al.'s data stop in Dec 2019, and they note that Ben Dor and Rosa (2019) "do not find any change in the pre-FOMC drift after 2015". A later paper, Ignatieva and Ohashi (Applied Economics 57(17):2021-2037, 2025, https://ideas.repec.org/a/taf/applec/v57y2025i17p2021-2037.html), reports "a pre-FOMC announcement drift" for press-conference meetings (I could not see its sample period). So "gone" is one well-cited paper's finding, not a settled fact.

So what for us: published calendar patterns fade; do not treat the FOMC drift as a usable edge, and do not assume the reverse either.

### X4. Paz replication and Fetna study

**Verdict: CONFIRMED.**

- Sheimy Paz, "Out-of-Sample Evaluation of an Intraday Momentum Strategy for the S&P 500 ETF (SPY)", SSRN 7290621 (registered 19 Aug 2026; single author, not peer reviewed). Abstract: "Our in-sample replication closely matches the original results ... (Sharpe Ratio 1.34 over 2015-2024). However, out-of-sample performance deteriorates substantially: the strategy achieves a total return of only 9.4% versus 29.5% for a passive buy-and-hold, with a Sharpe Ratio of 0.39. The decline in risk-adjusted returns is statistically significant." Out-of-sample = about two years (May 2024-Mar 2026). The original (Zarattini, Aziz, Barbon, SSRN 4824172) was posted in May 2024; Paz cites it as 2025.
- Mulham Fetna, "Opening-Range Breakout Does Not Survive Trading Costs: A Pre-Registered 225-Cell Study on Sixteen Years of Futures Data", SSRN 7428398 (registered 14 Sep 2026; single author, not peer reviewed). Quote: "Zero of 225 cells meet the pre-registered positive bar (t >= 2.5 at $25 per round-trip ...)". The 225 cells are nine US futures markets x two session anchors x four range lengths x three exit rules, plus a volatility comparator; 2010-2026 one-minute data; "The median gross edge is -0.01 ticks per trade".
- Useful extra (not in the reports): a third independent preprint, Delgado, SSRN 7323419 (registered 21 Aug 2026), reproduces the original (Sharpe 1.317) and finds a pooled May 2024-Aug 2026 Sharpe of 0.35 (close to Paz's 0.39), but splits it: May 2024-Aug 2025 Sharpe 1.057, then Sep 2025-Aug 2026 return -8.1% with Sharpe -0.461. It concludes the data support "a strong initial post-publication period followed by a materially weak recent regime", not instant decay.

So what for us: strong warning that the popular SPY system has weakened and that opening-range breakouts earn nothing after costs, but these are unrefereed preprints on short out-of-sample windows.

### X5. Baltussen et al. (2021) and Gao et al. (2018)

**Verdict: Baltussen CONFIRMED. Gao CONFIRMED_BUT_DIFFERENT.**

- Baltussen, Da, Lammers, Martens, Journal of Financial Economics 142:377-403, Table 7 (S&P 500 futures, Jan 1996-May 2020; slopes and R-squared are printed multiplied by 100): when lagged net gamma exposure is negative, slope 6.63 (t 4.78), R-squared 3.58%; when it is zero or positive, slope 0.82 (t 1.03), R-squared 0.05%. So 0.0663 and 0.0082 as decimals. The 3.6% is the R-squared on negative-gamma days only. The gamma measure assumes market makers are short all puts and long all calls (OptionMetrics to 2017, SqueezeMetrics data after) and the authors thank SqueezeMetrics for data.
- Gao, Han, Li, Zhou, "Market intraday momentum" (June 2017 version, SSRN 2440866, https://assets.super.so/e46b77e7-ee08-445e-b43f-4ffd88ae0a0e/files/ee7dac49-530b-4950-b5d0-e0b5eee08f2e.pdf; the published JFE 129(2):394-414 page was blocked): "The predictive R2 of the first half-hour return on the last half-hour return is 1.6%", 2.6% with the twelfth half-hour added; out-of-sample 1.4% and 2.0%; SPY, Feb 1993-Dec 2013; slope 6.94, robust t 4.08. The 1.7% (out-of-sample 1.7% and 2.3%) comes from Limkriangkrai, Chai, Zheng, Pacific-Basin Finance Journal 80:102086 (2023), a replication on SPY 1996-2013 (https://researchmgt.monash.edu/ws/files/519509174/494419119_oa.pdf).

So what for us: the late-day link is real but small (R-squared under 4% even on the good days) and needs a dealer-gamma sign that we do not have.

### X6. Vilkov 0DTE trading rules

**Verdict: CONFIRMED.**

- Paper: Grigory Vilkov, "0DTE Trading Rules" (SSRN 4641356, first registered 1 Dec 2023; later titled "... Tail Risk, Implementation, and Tactical Timing"; sample Sep 2016 to early 2026).
- Repo README (https://raw.githubusercontent.com/vilkovgr/0dte-strategies/main/README.md, "Last updated August 2026"): "A transaction-cost unit-scale error caused the bid-ask half-spread to be charged at 1/100 of its true size (about 0.022 bp instead of 2.2 bp). ... the correction reverses the sign of the net-of-cost conclusions: no strategy or basket retains a positive net Sharpe ratio. ... Found by gex.live." It also says the paper PDF is "still being revised".
- KNOWN-ISSUES.md: "on the paper's full sample the put-ratio conditional net Sharpe goes from +0.93 to -0.75 and the top-three basket from +0.82 to -0.82." A second bug (May 2026, negative signs on short days) was reported by Victor Yoong in GitHub issue 1.
- Independent corroboration: a 26 Aug 2026 post by FirmTape/gex.live (a data vendor, so an interested party) quotes the author's reply: "You have read the units correctly, the finding stands ...". It also gives a headline conditional Sharpe of +1.55 falling to -0.70 after retraining.
- Nuances: (a) the +0.93 is one strategy's conditional figure, not "all strategies"; (b) the KNOWN-ISSUES table still shows Risk Reversal at +0.10 net Sharpe on the shipped 2024-05-01 unconditional panel, which the text calls not "materially positive"; (c) the SSRN abstract, as registered with Crossref and last indexed 14 Aug 2026, still says conditional rules "deliver economically meaningful net performance", so the public paper has not been corrected yet (SSRN itself was blocked, 403).

So what for us: do not cite the SSRN abstract or any pre-fix 0DTE rule as evidence; after costs none of them survive.

### X7. Cboe history files, terms, and the VIX1D calculation

**Verdict: CONFIRMED_BUT_DIFFERENT.**

Files downloaded 29 Sep 2026 (HTTP 200, `cdn.cboe.com/api/global/us_indices/daily_prices/<NAME>_History.csv`, which redirects to `cdn-api.cboe.com`; the two files I compared, VIX1D and SKEW, were byte-identical on both hosts). Linked from each index's dashboard page on cboe.com (e.g. https://www.cboe.com/us/indices/dashboard/vix1d/). The Cboe "VIX historical data" page itself lists VIX, VVIX, VIX9D and others but not VIX1D, VIX3M or SKEW.

| File | Rows | First date | Last date | Columns |
|---|---|---|---|---|
| VIX | 9,282 | 1990-01-02 | 2026-09-28 | open, high, low, close |
| VIX1D | 1,097 | 2022-05-13 | 2026-09-28 | open, high, low, close |
| VIX9D | 3,956 | 2011-01-04 | 2026-09-28 | open, high, low, close |
| VIX3M | 4,282 | 2009-09-18 | 2026-09-28 | open, high, low, close |
| VVIX | 5,113 | 2006-03-06 | 2026-09-28 | one value only |
| SKEW | 9,236 | 1990-01-02 | 2026-09-28 | one value only |

R4's data table lists all six files as open/high/low/close; VVIX and SKEW are single-value files.

VIX1D close above open (my own code, `x7_vix.py`): **471 of 519 days = 90.8%** for 3 Sep 2024-28 Sep 2026 (mean open 11.80, mean close 15.15), matching the researcher exactly. Caveat on the window: 222 of the 1,097 rows (13 May 2022 to 31 Mar 2023) have open = high = low = close, so they carry no real open. On the 875 days with genuine OHLC (3 Apr 2023 onward) it is 806 up days = 92.1%; by year 91.3% (2024), 90.4% (2025), 91.9% (2026). All 1,097 rows have both an open and a close value; 519 of them fall in the researcher's window. The upward drift is by construction: Albers and Kestner (Finance Research Letters 62:105186, 2024) find "a distinct overnight bias, that causes the index to consistently rise during trading hours and to fall overnight."

Terms of use: I found no licence text attached to the CSV files and nothing mentioning robots or scripts. The pages say:
- VIX page: "Cboe Volatility Index data is compiled for the convenience of site visitors and is furnished without responsibility for accuracy ..."
- Website Terms (https://www.cboe.com/terms, section 2): "You may view, print and download one copy of the Materials for your personal non-commercial use in connection with products and services offered by Cboe ... You may not otherwise copy, reproduce, alter, store either in hard copy or in an electronic retrieval system, ... or otherwise use in whole or in part in any other manner the Materials without Cboe's prior written consent except to the extent that such use constitutes 'fair use'."
- Use of Cboe Content (https://www.cboe.com/use-of-content): "In order to use any Cboe logo, data, photo/image or other content contained in Cboe websites ... you must receive approval in advance from Cboe" (permissions@cboe.com; a licence agreement follows approval).

Plain reading: free to download, but the written terms are restrictive, not permissive. Automated downloading into a private research tool is not clearly authorised; strict reading needs Cboe's permission or a fair-use argument. Low practical risk for a private, non-redistributed tool, but do not publish or commit the files to a public repo. This is not legal advice.

So what for us: the files work and are current; use them privately, ask permissions@cboe.com if the tool becomes anything more, and never compare a raw intraday VIX1D reading with a fixed threshold.

### X8. Alpaca options data

**Verdict: CONFIRMED.**

- Price: https://alpaca.markets/data (page footer 2026) lists "Free ... $0/mo" (US Options (Opra): "Yes, indicative") and "Algo Trader Plus ... $99/mo" (US Options (Opra): "Yes, real-time"). The docs (https://docs.alpaca.markets/docs/about-market-data-api) show Options "Real-time market coverage: Indicative Pricing Feed" versus "OPRA Feed", and "Pricing Free | $99 / month". The $99 is one plan that also gives all-exchange stock data, not an options-only price.
- Indicative feed (https://docs.alpaca.markets/docs/historical-option-data): "Indicative Pricing Feed is a free derivative of the original OPRA feed: the quotes are not actual OPRA quotes, they're just indicative derivatives. The trades are also derivatives and they're delayed by 15 minutes." An Alpaca-affiliated forum reply (3 Jul 2024, https://forum.alpaca.markets/t/what-is-the-indicative-pricing-feed-for-options/14595): the use case "is to debug ones code and not generally to be used for live trading or to test the efficacy of ones strategy."
- Greeks (https://docs.alpaca.markets/docs/market-data-faq): "contracts with 0DTE (i.e., that expire on the current day) won't have Greeks", because their Black-Scholes calculation divides by days to expiry; also "The issue is not the data plan, but rather how Alpaca calculates these values." So paying for OPRA does not fix the missing 0DTE Greeks.

So what for us: the free options feed is for debugging only; if we want real quotes it is $99 a month; compute our own Greeks for same-day options.

### X9. Beckmeyer et al. and the SEC (DERA) paper

**Verdict: CONFIRMED_BUT_DIFFERENT.**

- Beckmeyer, Branger, Gayda, "Retail Traders Love 0DTE Options... But Should They?" (version of 15 Dec 2023; the SSRN page was blocked, so I cannot rule out a newer version). Quote: "Roughly 60% of daily losses are the result of transaction costs, 60% are driven by investments in 0DTE put options, and retail buys show particularly poor performance." The paper's own numbers point higher: the introduction says "More than $90 million" of "more than $125 million" of losses come from transaction costs (about 72%), and Table 2 shows average daily loss $241k net versus $57k gross (76% costs; for the period from 16 May 2022, $350k versus $106k, 70%). Table 2 units are $100,000. So "about 60%" is the authors' rounded sentence, and the tables suggest more.
- Fu, Li, Musto, Pearson, "Hope at a Reasonable Price: Customer Use of Limit Orders in the 0DTE Market" (DERA Working Paper, 16 Mar 2025). Authors: Lei Fu (Purdue and SEC), Su Li (SEC), David Musto (Wharton), Neil Pearson (Illinois). It carries the disclaimer "This paper expresses the authors' views and does not necessarily reflect those of the Commission". Abstract: "Wide quoted spreads and the explosion of 0DTE option trading suggest possible exploitation of customers. In contrast, we find that customers' costs of trading with NMLOs are low." Introduction: "We conclude that any exploitation of customers by market makers is much less than first appears." Example: "the net effective spread of the MTO is less than half the $0.05 effective spread of the marketable order." It covers SPXW (index) options, July 2020-Sep 2023, and says of retail: "While we cannot directly identify the retail orders on the LOB, we can identify retail-sized orders." It also says that comparing trade prices with the quote that looks like it came before the trade, "as in Beckmeyer, Branger and Gayda (2023)", actually compares with the quote after it (a timestamp sequencing problem). It does not say retail traders make money.

So what for us: costs are the biggest single reason retail 0DTE loses; patient limit orders may cut the cost, but that is SPX evidence and not proof of profit.

### X10. Bulkowski and SpotGamma

**Verdict: CONFIRMED (both).**

- Bulkowski (https://www.thepatternsite.com/DistributionDay.html, copyright 2005-2026; page fetched raw): "A cluster of distribution days within 21 calendar days during a rising price trend is supposed to predict a price drop. It doesn't. Clusters of distribution days only work in a falling price trend, regardless of whether volume is heavy or light. This finding applies to individual stocks as well as the S&P 500 index. Rob Hanna found the same thing." Method: 568 stocks, 1 Jan 2005-1 Jul 2010 (over 58,800 samples); S&P 500 from Jan 1950 to 1 Jul 2010; a distribution day is a drop of more than 0.2% on higher volume; 10-day EMA for trend. Caveats: a single author who sells books, an old sample, not peer reviewed.
- SpotGamma (https://spotgamma.com/gamma-exposure-gex/, page fetched raw): "every public GEX figure depends on modeling assumptions"; "A call-positive/put-negative public-data formula is a simplifying inventory convention-not a rule of option mathematics and not a direct observation of every dealer book."; "Two legitimate GEX charts can disagree because GEX is a model output, not an exchange-published statistic."; and "It does not predict direction." SpotGamma sells paid plans (its page: "Every SpotGamma plan includes live GEX levels ..."; "see plans at spotgamma.com/subscribe"), so it has a commercial interest, though these statements cut against overselling.

So what for us: distribution-day rules and gamma "levels" are not evidence-backed triggers; the gamma sign is a guess.

### X11. Order flow, ES-SPY, macro news

**Verdict: CONFIRMED (all three).**

- Kolm, Turiel, Westray, "Deep order flow imbalance: Extracting alpha at multiple horizons from the limit order book", Mathematical Finance 33(4):1044-1081 (2023; DOI 10.1111/mafi.12413, abstract via Crossref): "Finally, we demonstrate that the effective horizon of stock specific forecasts is approximately two average price changes." Sample: 115 Nasdaq stocks; horizon is in event time, not minutes.
- Budish, Cramton, Shim, QJE 130(4):1547-1621 (2015) (Feb 2015 working-paper text checked): "Over all trading days in 2011, the median return correlation is just 0.1016 at 10 milliseconds and 0.0080 at 1 millisecond." Main specification, mid-quotes, 2011 data. At one minute the same table shows 0.9798, so the two move together at minute scale. Also: median arbitrage duration fell "from a median of 97 ms in 2005 to a median of 7 ms in 2011" (this matches R3's D4 row).
- Chordia, Green, Kottimukkalur, "Rent Seeking by Low-Latency Traders", RFS 31(12):4650-4687 (2018), abstract: "Prices of the highly liquid S&P 500 exchange-traded fund (SPY) and the E-mini future (ES) respond to macroeconomic announcement surprises within five milliseconds ... profits from trading quickly are relatively small, roughly $19,000 ($50,000) per event for SPY (ES)." (via IDEAS/RePEc and the Crossref record of the SSRN version; the OUP page did not display).

So what for us: these effects live at milliseconds and cannot be captured with one-minute bars.

### X12. Costs, break-even hit rates, and sample size (my own calculation)

**Verdict: CONFIRMED_BUT_DIFFERENT.** Code: `checker2_scripts/x12_calc.py`, `x12_moves.py`.

| Item | Researcher | Mine |
|---|---|---|
| Spread cost, 2 cents at $766 | 0.26 bp | 0.261 bp |
| SEC fee, $20.60 per $1M sold (sale leg only) | 0.21 bp | 0.206 bp |
| Long round trip | 0.47 bp (3.6 cents a share) | 0.467 bp (3.58 cents) |
| Hit rate needed, 1 minute (M 1.54 bp, C 1 bp) | 82% | 82.5% |
| 5 minutes (M 3.46) | 64% | 64.5% |
| 30 minutes (M 8.62) | 56% | 55.8% |
| Trades to detect +1 bp net, sd 12 bp, 80% power, critical t 1.96 (p<0.05) | 1,136 (sd 12.04) | 1,130 (sd 12); 1,138 (sd 12.04) |
| Same but critical t = 3.0 | not in the report; their "strict" line (z 3.12) is 2,273 | **2,125 (sd 12); 2,139 (sd 12.04)** |
| Expected-t reading (mean t of 3, n = (3 x 12 / 1)^2) | - | 1,296 |

- The formula p = 0.5 + C/(2M) is right: with a win or loss of size M and cost C per trade, expected net = (2p-1)M - C = 0. Note it treats M as the size of each win and loss and assumes the sign call is independent of the move size.
- Power: n = ((z_alpha + z_beta) x sd / edge)^2 with z_beta = 0.8416. The 1,100 in the claim is the p<0.05 figure (critical t of 1.96), which is what R3's table labels "p<0.05". Labelled "t = 3" it is wrong: a critical t of 3 needs about 2,130 trades (8.5 years at 250 a year). The wording in the claim, not the researcher's table, is off.
- The move sizes M come from the lab's cached SPY one-minute bars (40 sessions, 3 Aug-28 Sep 2026); I can only recompute them from that same file: 1.55, 3.55, 8.74 bp (1, 5, 30 minutes) against their 1.54, 3.46, 8.62. I have no independent source for the 2-cent spread; it is their one-day sample.
- Fee rates are real: Section 31 fee $20.60 per million dollars of covered sales from 4 Apr 2026 ("$0.00 per million" before that), staying until 60 days after the FY2027 appropriation is enacted (https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2; FINRA Information Notice 17 Mar 2026, https://www.finra.org/rules-guidance/notices/information-notice-20260317). FINRA's trading activity fee: I could not confirm the 2026 rate (the FINRA rulebook page I could open was an older version showing $0.000166 a share, maximum $8.30 a trade; search-result summaries mention $0.000195 from 1 Jan 2026 and a temporary pause for 1 Oct-31 Dec 2026, 91 FR 60435, but I did not open those documents). At any of these rates it is about 0.002 bp or less, so it does not affect the arithmetic.

So what for us: the cost arithmetic holds. A 1-minute trade needs roughly 82% accuracy to break even at a 1 bp all-in cost; a 30-minute trade needs about 56%; and proving a 1 bp edge takes roughly 1,100 trades at the lenient p<0.05 bar, or about 2,100 at t = 3.

### X13. Same-day at-the-money SPY call, 25 minutes (my own calculation)

**Verdict: CONFIRMED (arithmetic), but assumption-sensitive.** Code: `x13_bs.py`, `x13_empirical_premium.py`.

Black-Scholes, S = K = 766:

| Case | Premium | 1 cent as % of premium |
|---|---|---|
| Researcher's convention (25 trading minutes; T = 25/98,280 years), IV 15%, r = q = 0 | $0.731 | 1.37% |
| Same with r 4%, q 1.2% (their inputs) | $0.734 | 1.36% |
| IV 12% / 15% / 20% (trading-time) | $0.588 / $0.734 / $0.978 | 1.70% / 1.36% / 1.02% |
| Calendar-time (25/525,600 years, the way Cboe's VIX1D method counts time), IV 12% / 15% / 20% | $0.253 / $0.317 / $0.422 | 3.95% / 3.16% / 2.37% |
| Bought about 10:00 with 6 hours left, IV 15% (trading-time / calendar-time) | $2.81 / $1.21 | 0.36% / 0.83% |
| Fair value from what SPY actually did (0.5 x S x mean absolute 25-minute move, lab's 40 sessions) | about $0.29 for all 25-minute windows; $0.30 for the last 25 minutes; $0.21-0.39 by time of day | about 3.4% (2.5-4.7%) |

- Wording: the $0.73 is the price of a call that expires 25 minutes after purchase, not of a same-day call bought earlier and held for 25 minutes. A call bought at 10:00 costs far more, so the spread is a much smaller share of it.
- The number depends heavily on what "IV 15%" means. In the lab's bars SPY's one-minute realised volatility is 6.9% a year (trading-time), and its mean absolute 25-minute move is about 7.6 bp, so a realised-move price is about $0.29. A $0.73 premium implies the market charges more than double the realised movement (a large volatility premium), or that 15% is read in trading time when the market quotes it in calendar time. Either way a 1-cent half-spread is more likely 2.5-3.5% of a 25-minute call than 1.4%, and a round trip 5-7%.
- I have no real option quotes (no OPRA access), so I cannot say what the market actually charged.

So what for us: the "spread is only 1.4% of the premium" line is the optimistic end; at realistic volatility it is about twice that (a round trip of about 5-7% instead of 3%). That still leaves most of a 33% average loss unexplained by spreads, so R4's conclusion stands, but costs matter about twice as much as the report says.

### X14. Random-walk noise floor (my own re-simulation)

**Verdict: CONFIRMED_BUT_DIFFERENT (ADX figure).** Code: `x14_r2_mk.py`, `x14_mk_crosscheck.py`, `x14_adx.py`, `x14_check_researcher_bars.py`. Model: independent Gaussian steps (zero drift); fat-tailed Student-t(3) as a check. Number of points per window: 10 to 3,000 (12, 20, 60, 390 returns = 13, 21, 61, 391 points); 100,000 paths per case for windows up to about 400 points.

| Metric | Researcher | Mine |
|---|---|---|
| Share of windows with R-squared above 0.8 (log price on time) | 15.2-16.0% for 12-390 returns | Gaussian: 15.9% (13 points), 15.1% (21), 14.9% (61), 14.4% (391); 14.4-17.0% over 10-3,000 points. t(3): 14.2-16.5%. Rolling windows of one long walk: 16.0% (13), 15.1% (21), 14.5% (61), 14.6% (391). Continuous-time limit about 14.5% |
| Median R-squared | 0.43-0.45 | 0.44-0.48 |
| ADX(14) above 25, share of bars | 34.3% and 37.0% | **37.6% and 37.9% (bars built from 20 or 60 sub-steps), 40.1% (5 sub-steps), 49.5% (1 sub-step: range from close-to-close only), 46% (t(3), 5 sub-steps)** |
| ADX(14) above 20 | 55.1-58.0% | 58.8-59.4% (20-60 sub-steps), 61.6% (5) |
| ADX 95th percentile | about 42 | 42.8-44.1 |
| Mann-Kendall on price levels, share with abs(Z) above 1.96 | 55.7% / 67.2% / 81.9% / 92.2% (12, 20, 60, 390 returns) | 55.2% / 67.9% / 81.7% / 93.4% (13, 21, 61, 391 points); with 12, 20, 60, 390 points: 53.8% / 66.0% / 81.5% / 92.4% |
| Mann-Kendall on iid returns (sanity) | - | 4.6% / 4.7% / 5.4%, as it should be |

- My Mann-Kendall code agrees with the `pymannkendall` library on 100% of 1,500 paths at each of three lengths, and my ADX agrees with TA-Lib to within 0.15 ADX points (start-up conventions only).
- Why ADX differs: in `research/r5/null_sim2.py` the bar-building function adds the previous bar's cumulative close to each bar's sub-path even though the sub-path is already cumulative; high and low are shifted but the close is not. I ran the function: in 94% of the bars the close lies outside the [low, high] range, so the bars are invalid. The result, 34-37%, is therefore not a clean number; with valid bars it is 37-40%. The direction of the finding is unchanged (a pure random walk shows "ADX above 25" more than a third of the time).
- Their R-squared and Mann-Kendall code has no such problem and reproduces.

So what for us: on a random walk, "looks like a trend" is common: about 1 window in 7 has R-squared above 0.8, about 2 in 5 ADX readings exceed 25, and Mann-Kendall on prices "finds" a trend more than half the time. Fixed thresholds of these indicators are not evidence of a real trend.

## 4. Access notes and what I could not check

- Blocked (HTTP 403 or content not returned): SSRN abstract pages (Beckmeyer, Vilkov, Gao), ScienceDirect (Gao JFE), Wiley (Kolm), OUP (Chordia), Taylor & Francis (Ignatieva-Ohashi), Federal Register page (redirected). SEC pages returned 403 to command-line downloads; I obtained the SEC order, the adopting release and the DERA paper through the page-fetch tool, which saved the PDFs, and read the text myself. The SEC "statement" page (X1) and the SEC fee-rate page (X12) were read only through the tool's summary, so I rely on the order PDF and the FINRA notice for verbatim wording.
- Abstracts I quote from Crossref (the DOI registry) rather than the publisher page: Kolm et al., Paz, Fetna, Zarattini et al., Delgado, Vilkov (SSRN), Albers-Kestner (SSRN version). IDEAS/RePEc gave the Chordia et al. abstract.
- Not independently checkable: the 2-cent SPY spread and all spread-time-of-day figures (the lab's own one-day quotes); the SPY one-minute bars (I read the lab's cached file `research/work/SPY_df.pkl` only to re-compute move sizes).
- Sources with a commercial interest: gex.live/FirmTape (Vilkov write-up), SpotGamma, SqueezeMetrics (data supplier to Baltussen et al.), Bulkowski (sells books), Cboe (sells data and options).
- Nothing here is legal advice (Cboe terms).
- Independence note: the shared `verification/` folder also holds another person's work. A directory listing I ran near the end showed its file names; I opened none of those files. One file name (a Fed Board paper number) prompted me to run my own web search, which led to FEDS 2026-023 (used in X3); I read that paper directly from federalreserve.gov. Nothing else in this report was influenced by that listing, and all other checks were finished before it.

## 5. Suggested wording fixes for the repo text (for the research team; I edited nothing)

1. R3 section 2c and summary: replace "start on the first business day of November 2026 (Monday 2 Nov)" with "moved by SEC order 34-105656 (11 Jun 2026) to the first business day of November 2027; the SEC has also asked staff to review the rules".
2. R3 (B4/F1 and summary): call the 2026 overnight item a NY Fed Liberty Street Economics blog post (Boyarchenko, Larsen, Whelan, 1 Jul 2026) about the 2:00-3:00 a.m. ET hour in E-mini futures.
3. R3 A1: say Gao et al. report R-squared 1.6% (1.7% is the replication's figure).
4. R3 power table: keep "p<0.05" beside 1,136 trades; add "critical t = 3: about 2,130".
5. R4 (Cboe files): VVIX and SKEW files have one value column; VIX1D OHLC are real only from 3 Apr 2023; add the Cboe terms caveat.
6. R5 section 2.2: ADX figure to 37-40% after fixing the bar-building function.
7. R4 H3 note: state the time convention behind $0.73 and that realised-move pricing gives about $0.3.

## 6. Files

- `checker2_scripts/` : x14_r2_mk.py, x14_mk_crosscheck.py, x14_adx.py, x14_adx_mine_only.py, x14_check_researcher_bars.py, x13_bs.py, x13_empirical_premium.py, x12_calc.py, x12_moves.py, x7_vix.py (outputs in `outputs/`).
- `checker2_evidence/` : saved text of the key pages and files (SEC order and rule excerpts, Cboe terms and VIX1D file, Alpaca pages, Bulkowski, SpotGamma, NY Fed post, Vilkov README and KNOWN-ISSUES).
