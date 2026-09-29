# Accuracy review of "01 Synthesis and plan.md"

Reviewer: independent, accuracy lens. Read-only: no file edited, no git, no trading API. Every statement, number, table cell and
attribution in the synthesis was checked against `00 Fact-check corrections`, the four checker reports, R1 to R7 (the `../research/`
originals; the staged copies differ only by a banner line), R8 and `picture test/`, `MINUTE_TRADING.md` and `Why day traders lose.md`
section 4. R8's figures were re-derived from `truth.json` and `reader_answers/` (in memory only). Line numbers below are lines of
the synthesis file.

**Result: 31 defects. 2 wrong numbers, 3 wrong attributions or verification scopes, 13 overstatements, 13 nits (nit D13 is a
source-level note about R8, not a synthesis defect).**
Most numbers are right: the section 5 table, the section 6 table, the R8 figures, the corrections that were applied (E5, E6, E7 numbers,
E16, E17, E19, E20) and the arithmetic of the trial count (22 + 9 + 7 + 6 + 4 = 48) all check out.

Top three: A1 (R-squared "a third or more"), A2 ("1-cent spread" should be half-spread), and the pair C1 + B1 (things called
measured or reproduced that the corrections file says are assumptions or were not reproduced).

---

## A. Wrong numbers (2)

**A1. Line 99-100 (section 4, first bullet).** Says: "Fixed textbook cut-offs (ADX above 25, R-squared above 0.8, 'Mann-Kendall p below
0.05') are met by noise a third or more of the time."
- Wrong for R-squared. Pure noise gives R-squared above 0.8 in 14.8% to 16.0% of windows at every window length (R5 section 2.2
  table and Appendix A.1; corrections E6 "about 15% of windows"; both X checkers 14.4% to 15.9%). It also contradicts line 20-21 of
  the same synthesis ("about 1 window in 7"). ADX above 25 is 37% to 40% (E6, correct) and Mann-Kendall 56% to 92% (R5 A14, correct).
- Should say (R5 section 4.3 wording): "are met by pure noise anywhere from about 15% of windows (R-squared above 0.8) through 37% to 40%
  of bars (ADX above 25) to 56% to 92% of paths (Mann-Kendall), depending on the test and window length."

**A2. Line 126-127 (section 5).** Says: "a 1-cent spread is roughly 2.5% to 3.5% of a 25-minute at-the-money option, a round trip 5% to 7%."
- Corrections E7 and R4 section 3.3 (H3 note) are about a 1-cent **half**-spread. A 1-cent full spread is a half-cent half-spread, so
  each side would be about 1.3% to 1.7% and the round trip about 2.5% to 3.5%: the synthesis's percentages are twice too high for the words used.
- Two further slips in the same sentence. "25-minute option" means a call that **expires** 25 minutes after purchase, not one held 25
  minutes (E7; X_checker2 X13: "a call bought at 10:00 costs far more"). And the $0.29 to $0.32 premium behind 2.5% to 3.5% is a
  calendar-time price; the 1-cent half-spread itself is an assumption (no real option quotes: X_checker1 sections 5 and X13; line 245
  of the synthesis concedes this).
- Should say: "if the half-spread is 1 cent (assumed), it is roughly 2.5% to 3.5% of a call that expires 25 minutes after purchase
  (about $0.29 to $0.32); a round trip 5% to 7%."

---

## B. Wrong attribution or verification scope (3)

**B1. Line 132-133 (section 6 intro).** Says: "Both group-Y checkers reproduced R6's trend-rule numbers from Kenneth French's data
library. The rules with the best evidence, ..." and then a five-row table.
- What the corrections file (section C, first bullet) says was reproduced: the 10-month rule on French data (9.8% vs 10.3%, -43% vs
  -84%, 44 of 98 years, $5.6 vs $13.2). The Y checkers also reproduced the momentum-factor split, the July-August 2026 -15.5% (Y11),
  autocorrelation (Y13) and the luck table (Y14).
- Not reproduced by anyone: row 2 (SPY/QQQ 200-day: 8.6% vs 10.9%, -24.5% vs -55.2%, QQQ 8.1% vs 17.9%) and row 3 (five-asset ETF
  12-month rule) are R6's own computations on Yahoo's unofficial endpoint, which R6 itself marks "Yahoo data UNVERIFIED against
  issuer NAV" (R6 item 08; section 5 item 4: "I did not compare against Alpaca or issuer fact sheets"). Row 4 (volatility scaling:
  -44.7% vs -83.7%, 10.4% vs 15.0%) is French data but is not among the claims either Y checker checked (Y10 to Y14; a search of
  both reports finds no such figure).
- Should say: the checkers reproduced row 1 (and the row 5 crash figure); rows 2 to 4 are R6's own unreproduced calculations, with the
  SPY/QQQ and ETF numbers from Yahoo data.

**B2. Line 162 (section 7.1, layer 3).** Says: "AI (veto and explain only, MT-G29). It gets the Reader's numbers and a candidate trade and
answers ALLOW or VETO with an enumerated reason."
- MT-G29 as written (`Why day traders lose.md` section 4g): "No LLM call in the order path. Claude runs pre-open and at most every 30
  minutes. Its output schema allows only {veto_setup_today, veto_symbol_until, flag}". A per-candidate-trade ALLOW/VETO query is R7's
  design (section 4.1 point 3 and Test D, on shadow signals), not something MT-G29 authorises. Cite as "R7 Test D, which would need an
  MT-G29 amendment", or restate the layer to match MT-G29.

**B3. Line 210 (section 7.4, stop rule 1).** Says: "if the Reader fails its planted-truth audit, no model gets a numeric role".
- R7 section 4.7 item 1 and Test A: the thing audited is the **model** reading a picture, table or JSON ("Test A fails (model states
  numbers not in the data, or fails qualitative questions): no model gets a numeric or price role"). The Reader is deterministic code.
  Also worth knowing: R7 set the bar at 98% correct on qualitative questions; R8's picture reader scored 97.8% overall and 86% to 88%
  on the largest-gap question.

---

## C. Overstatements (13, most important first)

**C1. Line 35 (section 1 #8).** "A SPY round trip costs about 0.5 bp at the **measured** 2-cent spread."
- R3 measured it on **one day** of quotes (28 Sep 2026, three samples a minute; R3 section 2c and section 5 item 11). Corrections section D:
  "the 2-cent stock spread ... remain assumptions until measured on our own fills"; X_checker1 section 5 and X_checker2 section 4:
  "not independently checkable". The synthesis's own line 245 says "assumptions until measured". Should say "at a 2-cent spread seen
  in one day of quotes (not verified)".

**C2. Lines 166-182 (section 7.2), the trial count "about 48".** The arithmetic is right; the sourcing is only partly traceable.

| Block | Synthesis | Source check |
|---|---|---|
| B: T1 + R4 H1/H2 | 9 | R1 T1 = 6 hypotheses; R4 H1 = 2 trials, H2 = 1 trial. Match. |
| B: T2 | 3 | R1 T2 = 3. Match. |
| B: T5 | 4 | R1 T5 = 4. Match. |
| B: T3 | 6 | R1 T3 = 6 (3 replication + 3 filter). Match. |
| C: T4 | 9 | R1 T4 = 9 (Bonferroni over 9 level types). Match. |
| D: R3 | 7 | R3 gives no count. Derivable as H1 2 (both sides, long-only cut) + QQQ replication 1 + H2 1 + H3 2 + H4 1 = 7. But R3 section 4a(5) says "about 8 variants" (0.05/8), i.e. it counts H5; the synthesis lists H5 in block A as an uncounted "control". |
| E: R5 T3 | 6 | R5 gives no count. R5 section 3.6 says "the two windows, three quality variants, three horizons, two symbols and two eras already make dozens". 3 quality variants x 2 windows = 6 only if horizons (+30, +60, close), symbols and eras are treated as one test; counting the three horizons separately gives 18. The synthesis does not state its convention. |
| F: R6 | 4 | 2 rules x 2 symbols (R6 section 4E "test first"). R6 section 3 step 2 plans up to five rules run on 2016-2026 and on a long history. Not a contradiction, but a subset that is not labelled as one. |
| Not mentioned | - | R1 T6 (3) and T7 (2) are in R1's test order (section 4.3) and appear neither in Wave 1 nor in the "Not tested in Wave 1" list. |

- Under MT-G7 an undercount weakens the deflated-score bar, and "about 48" is repeated in `MINUTE_TRADING.md` line 72. State the
  counting convention (what is folded into one registered test) or use R5's own larger figure.

**C3. Lines 36-39 (section 1 #8).** "To confirm a real +1 bp edge takes about 2,100 trades, about 8 years of one trade a day. Sixty paper
sessions can only show effects above about 4 bp."
- Both numbers hold only for a 30-minute hold with a trade standard deviation of about 12 bp (R3 section 3 sample-size table; X_checker1
  X12). The sentence follows the 1-minute break-even sentence, so it reads as applying to 1-minute trades, where the standard deviation
  is 2.19 bp and the counts are about five times smaller (R3 table row "1 min": 150 trades for 0.5 bp; my arithmetic: roughly 40 to 70
  trades for 1 bp, and 60 trades detect about 0.8 bp). Add "for a 30-minute, one-trade-a-day setup". (Checkers give 2,125 to 2,139
  trades, 8.5 years at 250 a year; "about 8" is acceptable.)

**C4. Lines 192-195 (section 7.3).** "Every Reader feature uses only completed bars, so it can be computed each evening from that day's
full-market (SIP) bars ... Only the AI-veto scoring and the spread features need real-time capture."
- "Only completed bars" (R1 Appendix D) is a look-ahead rule, not a data-source statement. In `R1_features.json`, 5 of 59 features need
  data that is not Alpaca bars at all (F04 earnings calendar, F52 VIX, F53 VIX1D and term structure, F55 futures, F59 Cboe statistics);
  F24 needs SIP trades; F57 and F58 use option open interest and chain snapshots that Alpaca serves only as "current" and that must be
  saved every day (F57: "returns only current OI: save a snapshot every day"); F46 uses live snapshots. So "every" is wrong and "only
  ... real-time capture" omits the daily-capture features.

**C5. Line 30 (section 1 #6).** "... it cannot tell a real day from random noise by looking."
- R8 never asked the reader to tell real from synthetic; it compared "how clear and tradeable" ratings (1-minute 5.52 real vs 5.79
  synthetic, p 0.69; 5-minute 5.73 vs 6.21, p 0.45). R8 section 3 adds "a difference of about one point cannot be ruled out" (24 vs 12
  pictures), and the daily-chart ratings did differ (4.52 vs 6.96) but were set aside as not interpretable. Should say "its 'clarity and
  tradeability' ratings did not separate real days from random ones (small sample)".

**C6. Lines 13-15 (section 1 #1), repeated as fact in section 2.** "Your cousin's many screens are a decision funnel, not ten opinions."
- R1 labels the arrangement "common practice; described from general knowledge, not from a verified source" (Appendix B intro) and
  the timeframe ladder "efficacy UNVERIFIED" (R1 findings table A1). The cousin's actual screens are unknown; section 7.5 asks for them and
  R1 section 5 question 1 says so. Say "Multi-screen setups are usually run as a decision funnel (common practice, R1); we have not seen
  the cousin's".

**C7. Line 80 (section 3 row 1; also line 125 in section 5).** "Forecasting the size of moves (volatility clustering, VIX-family gauges) | Strong".
- R4 grades only the VIX level "Strong for volatility" (F1). VIX1D is "Mixed" (F3), term structure "Mixed" (F4), SKEW and VVIX "Weak" (F6), and R4
  section 4.4(b) says "log only" for SKEW and VVIX (R4 section 4.1 is less strict about SKEW, so R4 itself is uneven there). The Strong grade belongs to
  volatility clustering (Corsi/HAR: R2, R3 C4) and the VIX level, not to the whole family the row and section 5 name.

**C8. Lines 22 and 105 (section 1 #3; section 4).** "Attention spikes are followed by reversal or nothing." / "Stock studies find what follows is
reversal or nothing."
- R5 section 1 #4: "mostly reversal or nothing ... Counter-cases exist, so there is no clean rule" (R5 B2: attention predicts higher prices for
  about two weeks before reversal; B7: unusually high volume predicts a higher next month; B5: Welch's counter-evidence). Add "mostly".

**C9. Line 121 (section 5).** "Published patterns are right about 54% to 55% of the time."
- Not a published hit rate. R3 converts the best effect's R-squared of 1.7% to 2.9% (late-day momentum only) into a hit rate of 54% to 55%
  with a normal-distribution assumption (R3 section 2b point 2 and section 2c: R-squared 1.7% gives correlation 0.13 and 54.2%). Say
  "the best-documented effect (late-day momentum) implies about 54% to 55%".

**C10. Line 84 (section 3 row 5).** "Intraday momentum, first to last half hour | ... decayed since publication".
- R3 A4 says "Mixed, leaning weaker; Baltussen still finds it in 2000-2020". R3 section 2G shows the lab's LAST30_MOM_SPY gross **rising**
  (-1.5, +0.6, +1.3 bp for 2024, 2025, 2026). The documented decay (Paz, Delgado, our ORB5 and NOISE_MOM) belongs to the Noise Area and
  opening-range systems, not to the first-to-last-half-hour effect.

**C11. Lines 113-119 (section 5 table).** The 1.54, 3.46 and 8.62 bp averages and the hurdles built on them carry no caveat that they are
SPY-only and from 40 calm sessions (Aug-Sep 2026, realised volatility 6.9% a year against a typical ~15%; R3 section 3, last line;
X_checker1 X12b). In a typical year moves are about twice as large and the hurdles correspondingly lower.

**C12. Line 219-221 (section 7.5).** "Forty sessions are needed before anyone says anything about them."
- MT-G11 needs at least 100 closed trades **and** 40 sessions (R1 T8; `MINUTE_TRADING.md` line 179). At one trade a day, 40 sessions is 40 trades.

**C13. Lines 179-180 (section 7.2 block D).** "Only the first two have any real chance. Expect 'not shown'."
- R3's H2 "Power warning": only edges above about 8 bp net are detectable, so a "no" "would be inconclusive. Say so in the report". "Not
  shown" for H2 will mean "not testable", not "not there".

---

## D. Nits (13)

- **D1. Line 68 ("89 items ... half ... a third ... 14%").** R1 says "about 90 ... roughly half ... about a third ... the rest are essentially
  discretionary". The 89 and 14% are the synthesis's own count of each item's first-listed subjectivity score (my recount: 43 / 33 / 12 items scored
  0 / 1 / 2, i.e. 48% / 37% / 13.5% of 89; the R6 Bulkowski item has no tag). Counting any discretionary component instead, 27 of 89 (30%) qualify.
- **D2. Line 69.** "Most sources sell books, courses or data." R1 section 1 #5 says the sources **claiming otherwise** (claiming profit) do.
- **D3. Line 248 (section 8).** "36 days from a single 8-week window": 24 are real days (3 Aug to 25 Sep); 12 are synthetic reshuffles of them.
- **D4. Line 95.** "49% to 53% in 2026 papers": the 49.40% to 53.48% accuracies come from one paper (Hu et al., HS300, Y4a); the other 2026 paper
  (Wang) reports AUC 0.469 to 0.517, not accuracy (E14, Y4b). 53.48% rounds to 53%, fine.
- **D5. Line 108.** "fell from a score of 6.5 to 1.2": 6.54 is one quarter (2021Q4) and 1.22 is five months (Jan-May 2024); the whole-sample Sharpe
  is 2.97 (Y_checker1 Y7a). "Score" is an annualised Sharpe ratio.
- **D6. Section 7.4 table.** Human-column entries "A few" ideas a week and "Partial" record keeping are R7's stated assumptions (R7 section 5 item 10;
  R7 table says "(assumption)") shown without the label. The "Following its own rules ... Yes" cell drops R7's qualifier "Not for LLM
  judgement" (rows 1 and 2 keep "for code").
- **D7. Line 18-19.** Chart patterns are grouped with candlesticks, Fibonacci, Elliott and trendlines as having "no credible after-cost evidence". R2
  section 1 #5 deliberately separates them: Lo et al. found "some information", follow-ups "little or no stand-alone profit" (R2: Weak-Mixed).
- **D8. Line 78.** Column header "Evidence (strongest to weakest)" but rows are not in that order ("Order flow ... Real" and "Machine learning ... Strong"
  sit below "Little added information").
- **D9. Line 132-133.** "all applied on daily or weekly closes": the 10-month and 12-month rules use month-end closes (R6 section 4B: "Last trading day of each month").
- **D10. Line 105.** "the most-bought Robinhood stocks lost 4.7% over 20 days": the source figure is an average 20-day **abnormal** return of -4.7% for the top stocks
  bought each day (R5 B4).
- **D11. Line 25.** "Our own test says same-day options on these signals lose." It is a simple pricing-model proxy ("A rough guide only ... no volatility smile ...
  Real results could differ by a lot", `Minute trading backtest results.md` section 5). The lab says the direction "is not in doubt", so the claim stands; only
  the size (4% to 47%; 33% average) is unexplained by spreads (R4 section 1 #8, H3). "Proxy" appears only at line 231.
- **D12. Line 24-25.** "Retail traders lose on average in every dataset." R4 section 4.4(a) says "every retail dataset **I read**" and F16 "several independent datasets";
  one study (Bogousslavsky and Muravyev) finds only -0.9% per trade and calls severe-loss worries possibly "overstated", and sellers of short-dated options
  profited in two studies. Average retail results are still negative in all of them.
- **D13. Source-level, not in the synthesis.** R8 section 1 says the two passes agreed "97% to 100% ... on every question": recomputed agreement is 88.9% on
  B7 direction and C4 direction and 91.7% on C4 third (the 15 core questions are 97.2% to 100%). R8 also says "15 rule-based questions per
  picture": it is 7 (A), 5 (B), 5 (C) scored items per picture; 1,224 = 17 items per day x 36 x 2. The synthesis's "very consistent" is fine for
  the core questions.

---

## E. Section-by-section coverage (nothing more found)

- Header (bp, $766, 7.7 cents): correct (R3: $766.4).
- Section 1 #2: correct apart from D7. #3: numbers correct (37% to 40%, 1 in 7); see C8. #4: see D11, D12. #5: all numbers match R6 and the Y checkers. #7: 1.42, 258, two
  years match E20 and Y14. #9: Paz 1.34 to 0.39 and Delgado 1.317 to 0.35 with -8.1% (Sep 2025 to Aug 2026) match X_checker2; Fetna 0 of 225 on nine futures markets
  matches; "matches our own ORB5 fade" matches R3 section 2G (+9.0, +1.2, -1.6 bp). Delgado was seen by X_checker2 only, in abstract form, but the corrections file lists
  it as confirmed. #10: correct.
- Section 2: order of authority and the tools table match R1 Appendix B (see C6, D1, D2). The T-numbers cited match R1.
- Section 3: rows 2 to 4 and 6 to 16 match their sources (row 1: see C7; row 5: see C10); see also D4, D8.
- Section 4: the 1.3 bp per standard deviation over 60 minutes (n_eff 2,500, t = 3), the -0.10 and -0.03 autocorrelation and the 20 bp cost figure match R5, E17
  and Y7a. Defects: A1, C8, D5, D10.
- Section 5 table: all six cells recompute (82/65, 64/57, 56/53); Cboe file list matches R4/E10; see A2, C9, C11.
- Section 6 table: rows 1, 4, 5 match R6 and the checkers; rows 2 and 3 match R6 but see B1; "34% to 53%" matches E16; -15.5% value-weighted matches E19.
- Section 7.1: 59 = 38 + 16 + 5 matches R1 Appendix D and `R1_features.json`; "at most about six" matches R1 4.1(1). See B2.
- Section 7.2: rules (MT-G6, MT-G7, 0.5 and 1.5 bp a side, 2016 to Aug 2024, Sept 2024 to Sept 2026) match R3 4c and MINUTE_TRADING.md. See C2, C13. "Not tested" list
  matches the Owner notes verdict table (top-20 scanner is "Skip" for MT-G23; router and breakout-retest are "backtester first").
- Section 7.4 table: "About 4 things" (Cowan), 10% to 51% ($0.008 and $0.039 against $0.077), 97% Brazil, under 1% Taiwan all match R7. See B3, D6.
- Section 7.5 (except C12), 7.6 (33%; 3 to 5 rules), 7.7 (ORB5_QQQ and LAST30_MOM_SPY placing orders, NOISE_MOM_SPY shadow-only): match MINUTE_TRADING.md and R4/R6.
- Section 8 (except D3) and section 9: correct.
- R8 figures used in sections 1, 3 and 8, re-derived: 1,224 answers, 27 wrong (19 on the largest-gap question), 97.8%; prediction 28 of 72 = 38.9%, two-sided p 0.076,
  14 of 36 with p 0.243; followed the visible trend 43 of 46 (all 32 real-day answers), trend continued 22 of 46 (18 of 32 real, 4 of 14 synthetic); mean confidence 53.2.

## F. Corrections file: which items the synthesis applied

Applied correctly: E5 (2,100 trades), E6 (37% to 40%), E16 (34% to 53%), E17 (autocorrelation), E19 (value-weighted), E20 (1.42, 258). Applied with a wording slip: E7 (see A2).
Not used in the synthesis, so nothing to conflict: E1 to E4, E8 to E15, E18, E21. No superseded number survives in the synthesis.
