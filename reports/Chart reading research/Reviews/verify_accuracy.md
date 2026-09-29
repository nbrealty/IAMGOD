# Independent accuracy verification of the rewritten "01 Synthesis and plan.md"

Verifier: independent, read-only (no repo file edited, no git, no trading API, no network). Recomputations were done in memory with
Python on `picture test/truth.json`, `reader_answers/*.json`, R3, R5, R6 raw outputs and the checker reports. I made one scratch copy
of the synthesis in the scratchpad (`verify_tmp/synth_0502.md`) only to diff against later edits.

## 0. Which version I checked, and the answer in brief

The synthesis changed twice while I worked. I read all three states in full.

| State | mtime (UTC) | Size | What it is |
|---|---|---|---|
| A | 04:49:38 | 36,742 B | The version the task describes: ten findings, Wave 1 = 22+9+7+6+4 = 48 |
| B | 05:00:32 | 39,639 B | Eleven findings, block E = 72, Wave 1 = about 114; R8 and MINUTE_TRADING.md changed at the same moment |
| C | 05:02:16 | 40,132 B, md5 2c24a593b472764c423042f52039fa47 | Same as B plus four glossary rows at the end (drawdown; exposure and overlay; ETF and preprint; MT-G1 to MT-G42), which is exactly the 493-byte difference. **This is the current file; everything below is checked against C** unless marked "(A)". The four new glossary rows are accurate. |

**Result: 31 of 31 defects in `review_accuracy.md` are fixed in C** (30 cleanly; B1 fixed on its main point with one residual
inaccuracy, see N1). I found **13 new or remaining defects**, none of which changes a conclusion or a headline number. Every number
you asked me to recompute is right (the trial arithmetic is 22+9+7+6+4 = 48 in A and 22+9+7+72+4 = 114 in C). Ranked top three:

1. **Section 6 lead-in** says all the back-tests are "before trading costs", but rows 2 and 3 already include 5 to 10 bp per switch; and row 4 is French data, not Yahoo (N1).
2. **Section 7.2 counting convention** offers the owner a block-E count of 18 or 6 (totals 60 or 48) as "your call", which contradicts the sentence before it, MT-G7 ("owner cannot waive") and R5 section 3.6 (N2).
3. **Section 3, machine-learning row** says "Strong" although the section's own lead-in says only volatility forecasting is rated strong, and R2/R7 grade it Mixed (N3).

Independence note: I read the first (34-defect) `review_honesty.md` before it was overwritten at 04:55:57; one line of the new version
appeared in a grep result. I did not use it. Every finding below was checked against the primary source myself.

---

## 1. The 31 defects, one by one (status in C, with the new sentence)

| ID | Status | New text in C (section) |
|---|---|---|
| A1 | FIXED | "Fixed textbook cut-offs are met by pure noise often: about 15% of windows (R-squared above 0.8), 37% to 40% of bars (ADX above 25) and 56% to 92% of paths (a Mann-Kendall trend test), depending on the test and window length." (s.4) |
| A2 | FIXED | "an at-the-money SPY call that expires 25 minutes after purchase costs about 30 cents. If the half-spread is 1 cent (an assumption; we have no real option quotes), paying it each way costs about 3% going in and 3% going out, 5% to 7% in all." (s.5) Half-spread, "expires", assumption all corrected. |
| B1 | FIXED (main point); residual in N1 | "Two independent checkers reproduced the first row (month-end data from Kenneth French's library) and the July-August 2026 momentum fall in the last row; the other rows are R6's own calculations, using Yahoo data that R6 itself marks unverified ... (the volatility-scaling row was not checked by anyone else)." (s.6). Scope of what was reproduced is now right. Residual: "using Yahoo data" is wrong for row 4, and the next sentence mislabels costs (N1). |
| B2 | FIXED | "It is never in the order path and is not asked about single trades. Before the open, and at most every 30 minutes, it reads the Reader's numbers and may post a standing veto ... or raise a flag, each with a reason code and an expiry time. Each question is asked three times and a veto counts only if two of three agree (MT-G32) ... R7's design goes further (an ALLOW or VETO on every candidate trade, its Test D). That is not part of Wave 1 or the first build. It would need an amendment to MT-G29 ..." (7.1) Matches MT-G29 (schema, 30 minutes, expiry, no veto if missing) and MT-G32. |
| B3 | FIXED | "If a model fails the planted-truth reading audit (it states numbers that are not in the data, or scores under 98% on the questions about what a chart shows), no model gets a numeric role." (7.4 stop rule 1) The audited thing is now a model, not the Reader. |
| C1 | FIXED | "Getting in and out of one SPY share costs about 0.5 bp if the spread ... is 2 cents. We saw that on one day of quotes and still have to measure it on our own fills." (Finding 8) |
| C2 | FIXED (convention stated); see N2 for a residual | "Counting convention (fixed when the tests are registered) ... block E counts every window, quality variant, horizon, symbol and era as its own test (2 x 3 x 3 x 2 x 2 = 72 ...) ... Block D is R3's hypotheses (H1 both sides and a long-only cut, the QQQ replication, H2, H3 twice, H4); block F is two rules on two symbols. R3's overnight-drift control and R1's T6 and T7 are not counted here." (7.2) |
| C3 | FIXED | "For a trade held about 30 minutes, telling a real +1 bp edge from luck (at our bar of t = 3) takes about 2,100 trades, which is about 8 years at one trade a day. Sixty paper sessions could only reveal an edge of about 4 bp at the ordinary 5% test, or about 6 bp at our stricter bar." (Finding 9; the mixed thresholds I saw in A are gone) |
| C4 | FIXED | "Most Reader features use only completed bars ... Some features need data that are not Alpaca bars (earnings calendar, VIX-family, futures, Cboe statistics), SIP trade data, or option open-interest and chain snapshots ... those need a small daily capture job." (7.3) Matches R1_features.json (F04, F52, F53, F55, F59, F24, F57, F58). |
| C5 | FIXED | "Its 0-to-10 'clear and tradeable' ratings of random-walk pictures came out about as high as for real days (5.8 against 5.5 on the 1-minute charts; 24 real against 12 random pictures, so a gap of about a point could hide)." (Finding 6) |
| C6 | FIXED | "Traders who watch many screens usually work as a funnel ... (common practice according to R1). We do not yet know whether your cousin does; that is the first thing to ask him." (Finding 1) |
| C7 | FIXED | "Forecasting the size of moves (volatility clustering and the VIX level; VIX1D and term structure are mixed, SKEW and VVIX weak: log only) \| Strong for volatility clustering and the VIX level as forecasts (not direction)" (s.3) Matches R4 F1/F3/F4/F6, R3 C4. |
| C8 | FIXED | "attention spikes are usually followed by a fade or by nothing, but not always: some rise for a few weeks first, and moves backed by real news tend to continue." (Finding 3 and s.4) |
| C9 | FIXED | "A pattern that explains about 2% of price moves would be right about 54% of the time (R3's own conversion of the best-documented effect, late-day momentum)" (s.5). R-squared 1.7% to 2.9% gives 54.2% to 55.5% (arcsine formula). |
| C10 | FIXED | "still found in 2000-2020 in futures, before costs (Baltussen); our own LAST30 gross rose from -1.5 bp (2024) to +1.3 bp (2026) but stays negative after costs. The systems that faded are the noise-band and opening-range ones (two 2026 preprints and our own ORB5 test)" (s.3). "Stays negative" holds at the lab's 3 bp level and for the whole out-of-sample year at 1 bp (-0.04); 2026 alone at 1 bp is +0.25 bp (n = 184), i.e. zero within noise. |
| C11 | FIXED | "These averages are SPY's, from 40 calm sessions (Aug to Sep 2026; realised volatility about 6.9% a year against a 'typical' 15%, which is R3's assumption and was not checked). In a typical year moves would be about twice as large and the hurdles correspondingly lower. They also assume a win and a loss are each about one average move." (s.5) |
| C12 | FIXED | "Nothing can be said about his rules until there are at least 100 closed paper trades over at least 40 sessions (MT-G11); at about one trade a day that is roughly five months." (7.5 #1) |
| C13 | FIXED | "for the gap-down fade 'not shown' will mean 'not testable' (only edges above about 8 bp net can be detected)." (7.2 block D) |
| D1 | FIXED | "Of the roughly 90 items R1 catalogued, about half are exact formulas, about a third need judgment calls, and the rest are largely discretionary." (s.2) = R1 summary 3. |
| D2 | FIXED | "Most of the sources claiming these methods work sell books, courses or data." (s.2) |
| D3 | FIXED | "24 real days from a single 8-week window (plus 12 random twins of them)." (s.8) |
| D4 | FIXED | "None (39% here; 49% to 53% direction accuracy in one 2026 paper, coin-flip AUC in another)" (s.3). Hu et al. accuracy 49.40% to 53.48%; Wang AUC 0.469 to 0.517. |
| D5 | FIXED | "an LLM headline-trading result fell from an annualised Sharpe of 6.5 in one quarter to 1.2 in early 2024, and loses money at 20 bp of cost." (s.4) Y_checker1 Y7a: 6.54 (2021Q4), 1.22 (Jan-May 2024), unprofitable at 20 bp round trip. |
| D6 | FIXED | "A few (R7's assumption)", "Partial (R7's assumption)", "Yes for code; not for an AI's judgement" (7.4 table) |
| D7 | FIXED | Chart patterns are no longer in the "no credible evidence" list: "For classic chart patterns, one careful study found a little information but no stand-alone profit." (Finding 2) and "Weak to mixed: some information in one study, little or no stand-alone profit in follow-ups" (s.3). The finding-2 sentence compresses two facts (Lo et al. tested information, not profit; the no-profit result is from follow-ups such as Savin et al.), the s.3 row is exact. |
| D8 | FIXED | Column header is now "Evidence found"; no ordering claimed. |
| D9 | FIXED | "Hold the index only while it is above its 10-month average (month-end closes)"; the "daily or weekly closes" phrase is gone. |
| D10 | FIXED | "the stocks Robinhood users bought most each day did 4.7% worse than expected over the next 20 days." (s.4) R5 B4: 20-day abnormal return -4.7%. |
| D11 | FIXED | "Our own rough pricing-model test says same-day options on these signals lose (the direction is not in doubt; the size, 4% to 47% of the premium, is uncertain)." (Finding 4) See N13 for the 47%. |
| D12 | FIXED | "Retail option buyers lost money on average in the studies we found; how much, and why, is disputed, and sellers of short-dated options did better in two of them." (Finding 4) R4 F16: Beckmeyer and Bryzgalova. |
| D13 | FIXED at source (R8) | R8 now says "The two passes gave the same answer 97% to 100% of the time on the 15 core questions, and 89% to 92% on the largest-gap and next-30-minutes questions" and "17 scored items per market day (7 ..., 5 ..., 5 ...)". Recomputed: core agreement 97.2% to 100%; B7 direction 88.9%; C4 direction 88.9%; C4 third 91.7%; 612 answers per pass, 1,224 in all. |

---

## 2. Recomputations you asked for

| Item | Text in C | My recomputation | Verdict |
|---|---|---|---|
| Section 5, 3 bp column (SPY; R3 s.2c, p = 0.5 + C / 2M) | 1 min "impossible"; 5 min 93%; 30 min 67%; text: 60 min 63% | M = 1.54, 3.46, 8.62, 11.39 bp gives 147% (impossible), 93.4%, 67.4%, 63.2% | correct, matches R3 |
| Same table, 0.47 bp and 1 bp columns | 65/57/53 and 82/64/56 | 65.3/56.8/52.7 and 82.5/64.5/55.8 (X_checker1: 82.47, 64.45, 55.80) | correct |
| Trial arithmetic | (A) 22+9+7+6+4 = 48; (C) 22+9+7+72+4 = 114 | 22+9=31, +7=38, +6=44, +4=48; with E = 72: 114. Alternatives quoted in C: E = 18 gives 60, E = 6 gives 48. 2x3x3x2x2 = 72; 6 x 3 horizons = 18; 9 x 2 x 2 = 36 | arithmetic correct. Sources of the parts: B = R1 T1 6 + T2 3 + T5 4 + T3 6 + R4 H1 2 + H2 1 = 22; C = R1 T4 9; D = 7 (derived); E = R5 s.3.6 lists two windows, three quality variants, three horizons, two symbols, two eras; F = 4 (derived). See N2 for the sourcing wording. |
| Expected maximum of N standard normals / sqrt(2 years) | 28 tries 1.42; 258 tries 2.0; 1,000 about 2.3 | E[max] = 2.0137, 2.8294, 3.2414, divided by 1.4142: **1.4239, 2.0007, 2.2920** (N for exactly 2.0 is 257.2). Matches Y_checker1 and Y_checker2 (Y_checker2: "2.0 needs N = 258"). | correct |
| Noise floor | about 15% / 37% to 40% / 56% to 92% | R5 s.2.2: R-squared above 0.8 in 14.8% to 16.0%; X_checker1 14.6% to 15.9%; X_checker2 14.4% to 15.9%. ADX above 25: 37.4% to 40.2% after the bar-building bug fix (X1: 37.4/37.7/39.7/40.2; X2: 37.6/37.9/40.1). Mann-Kendall: 55.7% to 92.2% (R5); 53.8% to 93.4% (X2) | correct |
| R8 core and hardest question | 99.3% and 86.8% | 15 core questions pooled: 1,072 / 1,080 = 99.26%. Largest gap (C4, both parts): 125 / 144 = 86.81% (direction 62/72 = 86.1%, third 63/72 = 87.5%). Overall 1,197 / 1,224 = 97.80%; wrong 27 = 8 core + 19 largest-gap | correct |
| R8 prediction | 28 of 72; 36 pictures; "small skill could hide" | 28/72 = 38.9% (two-sided p = 0.076); each pass alone 14/36 (p = 0.243); 24 real + 12 synthetic; trend followed 43/46; continued 22/46; mean confidence 53.2 | correct |
| R8 clarity | 5.8 vs 5.5 on 1-minute; "a point could hide" | 5.79 vs 5.52 (p = 0.69); 5-minute 6.21 vs 5.73 (p = 0.45); Welch 95% interval for the 1-minute difference (real minus random) -1.5 to +0.9; daily chart 4.52 vs 6.96 (set aside by R8 as not interpretable) | correct |
| Ahead 22, level 32, behind 44 | "Behind in 44 of 98 years (ahead in 22, level in 32)" | Y_checker1 (two implementations): 44 lagged, 22 ahead, 32 tied (fully invested), 98 calendar years 1928-2025. 9.82% vs 10.30%, -42.9% vs -83.7%, $5.575 vs $13.206 since April 2009 | correct |
| 2022 figures | SPY -12.5% vs -18.2%; QQQ -16.4% vs -32.6% | R6 raw output (`out_d1.txt`, 200-day rule, 5 bp per switch): SPY -12.53 vs -18.24; QQQ -16.4 vs -32.6. Also QQQ 2010-2019: 8.12% vs 17.86%; SPY 1993-2026: 8.63% vs 10.88%, -24.5% vs -55.2% | correct |
| Volatility scaling row | -45% vs -84%; 10.4% vs 15.0% | R6 `out_m3.txt`: -44.7% vs -83.7% (1927-2026); 2013-2026 10.37% (0 bp) vs 14.98% | correct |
| Momentum crash | -15.5% value-weighted vs market +2.6% | Y_checker1/2: -15.46%, market +2.56% (equal-weighted decile -11.58%) | correct |
| Sample size | 2,100 trades, about 8 years; 4 bp / 6 bp for 60 sessions | n = ((3 + 0.8416) x 12.04 / 1)^2 = 2,139 (2,125 with sd 12) = 8.5 years at 250 a year; 60 trades: 4.35 bp (5% bar), 5.97 bp (t = 3) | correct ("about 8 years" is a slight round-down of 8.4 to 8.6) |
| Late-day test size | about 490 trades, about 2 bp or more | R3 H1: about 490 trades detect about 1.8 bp; with sd 12 to 14 bp and t = 3 my figure is 2.1 to 2.4 bp | consistent |
| Option cost | 30 cents; 3% + 3%; 5% to 7% | 1 cent / $0.29 to $0.32 = 3.1% to 3.4% each way (E7 range 2.5% to 3.5%; 5% to 7% round trip) | correct |
| Reader feature counts | 59 = 38 + 16 + 5 | `R1_features.json`: available_free yes 38, delayed 16, no 5 | correct |
| Autocorrelation | -0.10 and -0.03 | Y_checker1/2: -0.102 and -0.031 | correct |
| LLM headline Sharpe | 6.5 then 1.2; 20 bp | Lopez-Lira and Tang: 6.54 (2021Q4), 1.22 (Jan-May 2024); unprofitable at 20 bp round trip | correct |

---

## 3. New or remaining defects in C, ranked

Only real defects. "Correct text" is my suggested replacement.

**N1. (Medium) Section 6 lead-in mislabels costs and the data source.**
Quote: "the other rows are R6's own calculations, using Yahoo data ... All are hindsight back-tests before trading costs and taxes".
- Rows 2 and 3 are after costs: R6 subtracts 5 bp per one-way switch for SPY/QQQ (`d1_daily.py` line 3 and 61; R6 item 08 "5 bps a switch") and 10 bp per switch for the ETF basket (R6 item 09: "5.5% (10 bps a switch)"). Row 1 is before costs (9.82% at 0 bp; 9.66% at 10 bp, R6 item 07, `out_m1.txt`), and so is row 4 (`out_m3.txt` 0 bp run, 10.37%). Nothing includes taxes.
- Row 4 (volatility scaling) is Ken French data (R6 item 19), not Yahoo.
- Correct text: "Rows 1 and 4 are before trading costs (row 1 would be 9.7% a year at 10 bp a switch); rows 2 and 3 already include 5 to 10 bp a switch; none includes taxes. Rows 2 and 3 use Yahoo prices that R6 marks unverified; row 4 uses French data but nobody re-ran it."
- The error is conservative (the reader thinks the numbers are gross when two rows are already net), but it mislabels which rows are net. Finding 5's "(in hindsight, before trading costs and taxes)" is correct because it is about the French 10-month rule.

**N2. (Medium) Section 7.2 counting convention contradicts itself, MT-G7 and R5.**
Quote: "If you would rather count it less finely, block E is 18 (each horizon as its own test) or 6 (one per window and quality variant), and Wave 1 is about 60 or 48; that is your call, because a lower count lowers the bar. Blocks B, C, D and F use the counts in their own reports (R1, R3, R4, R6)".
- The sentence before it says MT-G7 "says the count can never be lower than the number of result series the test machine stores". MT-G7's row in `Why day traders lose.md` also says "Code (gate); process (owner cannot waive)". R5 section 3.6: "Every feature, window, threshold and horizon that gets looked at is a trial", so 6 (which ignores horizons) is not a permitted count. Offering 48 or 60 as an owner's choice conflicts with all three.
- Block D (7) and block F (4) are derived in this document. R3 gives "about 8 variants" (4a item 5), which includes the H5 overnight control that the convention excludes although it says "when in doubt we count the larger number"; R6 says "no more than five rules" (s.3 step 2). Only B (R1, R4) and C (R1) are the reports' own counts.
- Correct text: drop "that is your call ...", say the count follows from what the test machine stores and cannot be lowered by choice, and say "D counts R3's H1 to H4 as 7 (R3 itself counts about 8 with the H5 control); F counts two rules on two symbols (R6 allows up to five rules)".

**N3. (Low to medium) Scoreboard grades machine learning on chart images "Strong".**
Quote: "Machine learning on chart images | Strong in tiny equal-weighted stocks, weaker value-weighted; much of it is rescaling; high turnover".
- The section's lead-in says "Only volatility forecasting is rated strong". R2 grades it "Mixed" (row 2L; scorecard "Mixed (cross-section only)"); R7 "Mixed (strong statistically, weak for us)". "Tiny" is in neither source (R7: "small and illiquid names").
- Correct text: "Mixed: equal-weighted Sharpe about 2.2 to 2.4 but only 0.45 to 0.49 value-weighted (momentum 0.36); much of it is rescaling; turnover about 175% to 187% a month; the published version reports net-of-cost Sharpe of 1.5 for monthly equal-weight (corrections E13)".

**N4. (Low to medium) Section 7.4 bottom line contradicts the note above it.**
Quote: "None is measured yet ... Bottom line: 10X is real for coverage, record-keeping and rule-following in code."
- "Real" states a measured fact right after "None is measured yet". R7's column says only "Yes for code" as a design claim with "how we would measure it".
- Correct text: "Bottom line: 10X looks achievable by design for coverage, record-keeping and rule-following in code; it is not yet measured, it is unproven for the AI, and undefined for profit."

**N5. (Low) Two unsupported statements in section 8.**
- "Seven researchers and four checkers each ran out of web searches (200)": R1 to R7 say so; none of the four checker reports mentions a search cap (X_checker2, line 247, describes running an additional web search near the end). The claim for the checkers exists only in the corrections file, section D. Correct: "Seven researchers ran out of web searches (200)", or cite where the checkers said it.
- "A separate check of Alpaca's, IEX's and the SIP data terms is in progress; its result will be added to this folder." No file, note or report in the materials records such a check (the only related text is the owner's handoff v4 section I, which asks for one). Name the owner/file or delete. (In A this was 7.5 item 9 with "see the data-rights register when it is finished"; there is no such register.)

**N6. (Low) Scoreboard row for candlesticks and oscillators.**
Quote: "RSI, MACD, Bollinger: weak; a few variants beat buy-and-hold after costs in old samples, with no allowance for trying many." and "a few small positive studies in other markets".
- R2 has this result for RSI and MACD only (Chong and Ng: a handful of variants beat buy-and-hold net of a 1% round-trip cost). For Bollinger R2 has only Leung and Chong 2003: "do not outperform the Moving Average Envelopes". One of the two positive candlestick studies (Lu and Shiu 2016) is on the Dow 30, not "other markets".
- Correct text: "RSI, MACD: weak; a few variants beat buy-and-hold after costs in old samples with no allowance for trying many. Bollinger: no supportive test found." and "in Taiwan and in the Dow 30".

**N7. (Low) "deflated Sharpe at least 0.95".**
MT-G7 requires the deflated Sharpe *probability* to be at least 0.95. The glossary defines "deflated Sharpe" as "a Sharpe score marked down for how many things we tried", so "at least 0.95" reads as a Sharpe of 0.95. Correct text: "deflated Sharpe probability at least 0.95 (the chance that the marked-down score is still above zero)".

**N8. (Low) Stop rule 1 uses a pooled figure.**
Quote: "The picture reader (R8) was above the line on the 15 core questions (99.3%)". Pooled it is 1,072 / 1,080. Question by question, A6, C1 and C3 are each 70 / 72 = 97.2%, under the 98% bar. Correct text: "above the line pooled over the 15 core questions (99.3%; three of the fifteen were 97.2% each)".

**N9. (Low) Block D "most published support".**
Quote: "We put the first two first because they have the most published support." R3 says only H1 and H2 "have peer-reviewed or repo evidence"; for H2 the cited paper (Grant, Wolf and Yu 2005) is "not re-verified" and the support is mostly the lab's own gap-fade results (+4.1, +6.1, +3.8 bp gross, very few trades). Correct text: "the most support, published or in our own results".

**N10. (Low) R4's trials are specified on windows that the "2016 to Aug 2024" rule excludes.**
7.2 says "We run it on 2016 to Aug 2024 prices" and block B counts 3 R4 trials. R4 H1 (2 trials) needs VIX1D, which starts 13 May 2022, and is specified as train 13 May 2022 to 31 Dec 2023, test 1 Jan 2024 to 28 Sep 2026; R4 H2 (1 trial) is specified as train 2016-2021, test 2022 to Sep 2026. Both put most of the test in the already-used window. Cut at Aug 2024, H2 still works (VIX history from 1990) but H1 keeps only about 8 months of test. Add "the two VIX-yardstick tests need re-cutting to end in Aug 2024; the VIX1D one will have very little test data".

**N11. (Low, inherited from R6) Section 6 rows 2 and 3.**
- Row 3 is titled "12-month absolute momentum on a few broad ETFs", but R6's five-asset ETF test used the 10-month average rule (R6 item 09 and section 4B "R4b: ... the R1 test ... this is the version I tested"). The 12-month rule was tested only on French data (10.0% a year, -44%).
- Row 2: "It flipped in and out nine times in early 2022" is SPY only (R6 Q7: "between 21 Jan and 11 Apr").

**N12. (Trivial) Small wording points.**
"costs about 30 cents" is a model price ($0.29 from realised moves, $0.32 calendar-time Black-Scholes), not an observed quote; the parenthesis covers only the half-spread. "About 8 years" for 2,100 to 2,139 trades is 8.4 to 8.6 years.

**N13. (Source-level, not a synthesis error) "4% to 47%".**
The synthesis repeats the lab report's headline. The lab report's own options table (`Minute trading backtest results.md` section 5) tops out at -38.0% (realistic) and -44.0% (pessimistic); 47% does not appear in any table.

---

## 4. Problems in state A that C already fixed (for the record)

- "the two ChatGPT-spec strategies" listed among things "already tried": now "once they are registered" (they exist only as specs; no code in `trading/lab`).
- Section 3 candlestick/oscillator row said "no rule survived costs" for RSI/MACD, contradicting R2's Chong-Ng row: rewritten (N6 is the small remainder).
- Finding 8 used a t = 3 figure (2,100 trades) beside a 5%-bar figure (4 bp) without saying so: now both are given.
- 7.2 "Small effects (about 1 bp) are invisible even in 8 years" sat beside "2,100 trades (about 8 years)": now tied to the actual test sizes (490 trades, about 2 bp).
- Intraday-momentum row said "still found in 2000-2020 (Baltussen)" without "futures, before costs": added.
- Stop rule 1 attributed the audit to "R7 Test A": now generic.

## 5. Companion files

- `R8 Picture-reading test.md` (05:00:32) now agrees with the synthesis: the old headline "It cannot tell a real day from random noise" is replaced by "Its clarity ratings did not separate real days from random noise in this small sample", and the agreement and item counts are corrected (D13).
- `MINUTE_TRADING.md` now says "about 114 ... (about 48 to 60 if counted more loosely ...)"; it inherits N2.
- `00 Fact-check corrections` is unchanged since 04:49:38; its E1 to E21 numbers agree with the checker reports. One sentence there ("Every researcher and checker ran out of web searches (200 each)") is the source of N5's first item.
