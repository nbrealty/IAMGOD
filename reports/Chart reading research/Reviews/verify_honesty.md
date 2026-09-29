# Independent verification: honesty, clarity and rules

Verifier report on the rewritten `01 Synthesis and plan.md`. Read-only work; this is the only file I wrote.

## 0. Read this first (versions and process)

- **Version verified ("v3").** `01 Synthesis and plan.md`, 40,132 bytes, saved 05:02:16 (md5 2c24a593...). The copy in `reports/Chart reading research/` is identical. Also read: `R8 Picture-reading test.md` (05:00:32, md5 c9863ba7...), `00 Fact-check corrections` (04:49:38, unchanged), `MINUTE_TRADING.md` (05:00:32, md5 311883d9...). Nothing changed between 05:02 and 05:07. If any file changes later, re-check the quoted lines.
- **The document moved while I worked.** I started on the 04:49 text and finished on the 05:02 text. Everything below is judged against v3. The differences that matter to you: block E is now counted at 72 and Wave 1 at about 114 trials; old item 8 is split into items 8 and 9; the header sentence about two reviewers is gone; the glossary grew to 34 rows; **the 7.5 decision list now has eight items, not nine** (the old item 9, data rights, moved to section 8 as a status note).
- **`review_honesty.md` was overwritten twice while I worked.** I read the 34-defect version (saved 04:46, 45,534 bytes) in full at the start. It was replaced at 04:51 by a 28-defect review of an intermediate text, and again at 04:55 by a 9-defect review (17,314 bytes, on disk now). My numbers 1 to 34 are those of the first version. Each row in section 2 repeats the defect's title so it can be matched. Please keep a copy of the 34-defect version if you still need it.
- **One slip on my side.** Early on I ran a single read-only `git status --short` before I re-read the "no git" instruction. It changed nothing. No other git use, no network, no API.

## 1. Result

**Of the 34 defects: 32 FIXED, 2 PARTLY FIXED (#8 and #27), 0 NOT FIXED, 0 DISPUTED.** One sentence that the review itself suggested (under #24, "10X is real for ...") is the cause of the remaining part of #8; I dispute that sentence, not the defect.

No hard rule conflict is left. There are two near-misses (R3 and R4 in section 3). The document promises no profit, gives no advice to trade, and puts no AI in the order path.

Top remaining defects, ranked (details and suggested wording in section 3):

1. **R1. 10X is still stated as "real"** one sentence after "None is measured yet" (7.4 note; also box item 3 and finding 7). The "Charts watched at once = Yes" row drops R7's own caveat.
2. **R2. R8, in the same folder, still overclaims:** "essentially solved", "good enough to help with messy screenshots" (never tested), "Extending a trend earned nothing". It also conflicts with box item 1.
3. **R3. Block B's three R4 trials cannot follow the stated 2016 to Aug 2024 plan** (VIX1D starts May 2022; R4 tests through Sep 2026), and they depend on the unresolved Cboe decision.
4. **R4. Trial count.** The heading says "counted the cautious way" but blocks B, C, D and F are counted at the pooled figures; "that is your call" clashes with MT-G7.
5. **R5. Section 6:** "before trading costs" is wrong for the SPY, QQQ and ETF rows; the closing "AI's real advantage ... scanning 500+ stocks" does not fit a two-symbol bot.
6. **R6. A few sentences a beginner still cannot follow** (counting convention, "ordinary 5% test", the detection-limit sentence in section 4) and glossary gaps (volatility, fade, long/short, back-test).

## 2. The 34 defects, one by one

Quotes are from v3. "Note" gives any residual point (numbered R-items are in section 3).

| # | Defect (title) | Verdict | New text in v3 | Note |
|---|---|---|---|---|
| 1 | AI is a per-trade ALLOW/VETO (breaks MT-G29) | FIXED | 7.1 item 3: "It is never in the order path and is not asked about single trades. Before the open, and at most every 30 minutes, it reads the Reader's numbers and may post a standing veto ... each with a reason code and an expiry time. Each question is asked three times and a veto counts only if two of three agree (MT-G32)." 7.4: "The AI is kept out of the order path (MT-G29)"; "Yes for code; not applicable to the AI"; cost cell "Unproven" | R7's per-trade design is now "not part of Wave 1 or the first build", needing "an amendment to MT-G29 and your written OK". |
| 2 | "pass", "final look" at a used window, "reject" | FIXED | 7.2: "An idea that survives becomes a candidate, nothing more. The Sept 2024 to Sept 2026 data is not a clean final test ... Old data can drop an idea only if its effect would have been big enough to see. ... Nothing is confirmed until an idea, registered in advance, works on data that arrives after it was registered (MT-G6)." | New: R3 (R4's trials cannot follow this split). |
| 3 | Trial count and pass bar do not match MT-G7 | FIXED | 7.2: "Wave 1 is about 114 *new* trials ... on top of everything already tried across the whole minute project (MT-G7): at least the 28 from the first backtest and the rule variants R5 and R6 tried while looking, plus the two ChatGPT-spec strategies once they are registered. Surviving Wave 1 makes an idea a candidate, not a pass: it still has to clear MT-G1, G5 and G7 (t of at least 3, deflated Sharpe at least 0.95, PBO at most 0.20, and a reality-check p below 0.05) on forward data." Missing machinery and the two random-baseline fixes are named. | Block E now 72 (2 x 3 x 3 x 2 x 2); 22+9+7+72+4 = 114 checks. Residual wording issue: R4. |
| 4 | "Published edges fade" stated as settled | FIXED | Finding 10: "Published edges tend to fade, but our evidence for minute setups is thin. Three 2026 preprints (each by one author, not peer reviewed, and we read them as abstracts only) ... Treat this as a warning, not a measurement." Own ORB5 result flagged as "the same stretch of time, not a separate check". | |
| 5 | Picture test: "we saw nothing" became "there is nothing"; limits missing | FIXED (synthesis) | Finding 6: "we saw no skill (28 right out of 72 answers, which is only 36 pictures read twice, so a small skill could hide). Its 0-to-10 'clear and tradeable' ratings of random-walk pictures came out about as high as for real days (5.8 against 5.5 ...; 24 real against 12 random pictures, so a gap of about a point could hide)." Section 8: "Its prediction and real-versus-random parts rest on 36 pictures." | R8 itself still has leftovers: R2. Scoreboard row 134 says "None (39% here ...)" with no small-sample note (R9). |
| 6 | Cost hurdle called "measured", lab's 3 bp level missing, calm sample | FIXED | Finding 8: "We saw that on one day of quotes and still have to measure it on our own fills. We plan for 1 bp to 3 bp, and the lab's headline results use 3 bp. ... In a normal, more volatile year the moves are bigger and these hurdles are lower (the 'typical 15% a year' volatility is R3's assumption; nobody checked it)." Section 5 table has the 3 bp column (impossible / 93% / 67%). | I confirmed the lab's "realistic" cost is 1.5 bp a side (backtest report line 29). I recomputed all nine hurdle cells: correct. Small clarity point in R9. |
| 7 | "Best-supported" and "no credible after-cost evidence" | FIXED | Finding 2: "... we found no test showing a profit after costs. For classic chart patterns, one careful study found a little information but no stand-alone profit." Row 128 now separates candlesticks (careful test found no rule beating buy-and-hold after costs), RSI/MACD/Bollinger ("weak; a few variants beat buy-and-hold after costs in old samples, with no allowance for trying many"), stochastic, Fibonacci/Elliott. "toll" is gone. | Checked against R2 (Duvinage; Chong and Ng): accurate. |
| 8 | 10X scorecard states hopes as facts; "Yes" reads as measured | **PARTLY FIXED** | 7.4: "Rules are enforced by code, so a broken rule shows up as a bug we can find, not a lapse of willpower (code can still have bugs ...)"; "*These 'Yes' answers say what the design allows. None is measured yet ...*" | The next sentence reintroduces certainty: "Bottom line: 10X is real for coverage, record-keeping and rule-following in code." Box item 3 and finding 7 say "honest for". The "Charts watched at once" row drops R7's caveat. See R1. |
| 9 | "Retail traders lose on average in every dataset" | FIXED | Finding 4: "Retail option buyers lost money on average in the studies we found; how much, and why, is disputed, and sellers of short-dated options did better in two of them." | |
| 10 | "Attention spikes: reversal or nothing" | FIXED | Finding 3 and section 4: "usually followed by a fade or by nothing, but not always: some rise for a few weeks first, and moves backed by real news tend to continue. (... did 4.7% worse than expected over the next 20 days.)" | |
| 11 | "Forty sessions" understates MT-G11 | FIXED | 7.5 item 1: "at least 100 closed paper trades over at least 40 sessions (MT-G11); at about one trade a day that is roughly five months." | Wording nit and the 60-day whole-test stop: R9. |
| 12 | States how the cousin works before seeing his screens | FIXED | Finding 1: "usually work as a funnel ... (common practice according to R1). We do not yet know whether your cousin does; that is the first thing to ask him." | |
| 13 | Soft spins ("better than most day traders", "about zero net") | FIXED | Box 4: "The most likely honest result ... is 'no net edge found'." Finding 11: "A bot with no edge does not break even; it slowly loses the cost of each trade." 7.4 profit row: "A small net loss (each trade pays costs), unless a real edge is found". | |
| 14 | Section 6 overstates what was checked; soft endorsement | FIXED (one new slip) | Section 6: "Two independent checkers reproduced the first row ... the other rows are R6's own calculations, using Yahoo data that R6 itself marks unverified ... All are hindsight back-tests before trading costs and taxes"; "Behind in 44 of 98 years (ahead in 22, level in 32)"; 2022 shown as "a cost" but "finished 2022 ahead"; "under water for two to seven years"; "edge" replaced by "advantage". Finding 5 now says "in hindsight, before trading costs and taxes". | I verified 44/22/32 in the checker reports. Two slips in the adopted wording: R5. |
| 15 | Stop rules (2) and (6) vs MT-G34 | FIXED (nit) | Stop rule 2: "After 100 AI decisions (MT-G34) and at least 40 sessions ..." Rule 6: "two quarters from the day Wave 1 starts, or sooner if the number of ideas tried makes the bar higher than our data can ever clear." | Rule 2's extra "40 sessions" is looser than MT-G34: R7. |
| 16 | "Testing 1,000 times more ideas does not find an edge" | FIXED | Finding 7: "does not by itself find an edge; it makes a lucky result more likely ... 1.42 ... 258 tries give 2.0 and 1,000 give about 2.3" | I recomputed 1.42, 2.0 and 2.3 (expected maximum of N normals times 0.707): correct. |
| 17 | "A side" undefined; option half-spread slip | FIXED | 7.2: "charging 1 bp and 3 bp for a round trip (0.5 and 1.5 bp each way)". Section 5: "expires 25 minutes after purchase costs about 30 cents. If the half-spread is 1 cent (an assumption ...), paying it each way costs about 3% going in and 3% going out, 5% to 7% in all." | "than the first report said": name the report (R9). |
| 18 | Four certainty slips in section 4 | FIXED | Section 4: "about 15% of windows (R-squared above 0.8), 37% to 40% of bars (ADX above 25) and 56% to 92% of paths"; "(our own rough estimate)"; "We expect SPY and QQQ to show these features rarely ... we will count them first."; "did 4.7% worse than expected". | The 1.3 bp sentence is still hard to follow: R6. |
| 19 | Sample-size numbers hide their assumptions | FIXED | Finding 9: "For a trade held about 30 minutes, telling a real +1 bp edge from luck (at our bar of t = 3) takes about 2,100 trades, which is about 8 years at one trade a day. Sixty paper sessions could only reveal an edge of about 4 bp at the ordinary 5% test, or about 6 bp at our stricter bar." | I recomputed 3.84 x 12.04 / sqrt(60) = 5.97 bp. "ordinary 5% test" is jargon: R6. |
| 20 | Decisions missing from 7.5 | FIXED | 7.5 now lists nightly logging (4), stop rules and time box (5), social text (6), stock-book notes (7), Cboe files (8); item 2 says "It needs no data fees ... Time and effort are not yet estimated." | Now eight items (data rights moved to section 8). Default for item 8 and AI-layer status: R8. |
| 21 | Caveats a reader needs | FIXED | Section 8: "The four checkers went through 28 key claims, two checkers each; the rest of R1 to R7 is as written by one researcher." 7.5: "Please write each skipped trade at the moment he skips it, with the time, before he knows how it turned out"; "one real entry ... (for writing his rules down, not as proof)". | |
| 22 | Social-text collector not framed against decision 4, MT-G30 | FIXED | Section 4: "only through the platforms' official interfaces, and only after checking their terms (not yet done). It is stored apart from the bot and never read by the order code (MT-G23, MT-G24). If an AI ever scores it, company names and tickers are masked first and only data after the AI's training cutoff is used (MT-G30) ... Not part of Wave 1; needs your OK." | |
| 23 | Jargon left unexplained | FIXED (residual gaps) | 34-row glossary at the end, including PBO, reality check (SPA), planted-truth audit, absolute momentum, term structure, put/call and skew, lead-lag and order flow, rescaling, ORB5/LAST30/NOISE, drawdown, exposure/overlay, ETF/preprint, and "MT-G1 to MT-G42". Inline glosses for Sharpe, R-squared, ADX, spread. | Still missing: volatility, fade, long/short, back-test, indicator names. See R6. |
| 24 | Tables need a one-line "so what" | FIXED | Section 2 note; section 3 note ("Only volatility forecasting is rated strong ..."); section 5 "Reading it: ..."; 7.4 "Bottom line ...". | The 7.4 bottom-line sentence is the review's own wording and is the cause of #8's remainder (R1). |
| 25 | Undefined shorthand | FIXED | Block B now "(9 trials: 6 from R1, 3 from R4) ... the three baseline setups ORB5_QQQ, LAST30_MOM_SPY and NOISE_MOM_SPY (3)"; "Paz, Delgado" replaced by "two 2026 preprints and our own ORB5 test"; autocorrelation sentence rewritten. | "R1 T4", "R5 T3" and "H1 ... H3 twice, H4" in the convention paragraph are still codes only the R-reports explain: R6. |
| 26 | 7.3 wrong about what cannot be recovered | FIXED | "What cannot be recovered later is real-time information: live quotes and spreads, and the AI's answers and delays. Price bars can be downloaded again any time. But a test only counts as forward evidence if it was registered before the data arrived, so registering early starts that clock." | |
| 27 | The "ten lines" are not short | **PARTLY FIXED** | Five-line "If you read nothing else" box added; old item 8 split into 8 and 9. | The box works. But the document is now 7,227 words; the findings run 76 to 153 words each (item 8: 153, item 10: 132); the 7.2 counting convention is one dense paragraph. See R6. |
| 28 | "Size caps" and "scale risk" vs MT-G14 | FIXED | Row 118: "**Yes:** as gates that skip a day or a trade (changing trade *size* with volatility would break the fixed-size rule MT-G14 and needs a new registered version and your written OK)". Section 5: "used only to skip quiet or wild days". | Section 3 and 5 now agree on SKEW and VVIX ("logged only"). "volatility timing" in 7.1 item 2: R7. |
| 29 | No MT-G42 report | FIXED | Block A: "**MT-G42 report:** how often would the whole set of gates pass a real edge of three sizes? Shown to you before any Wave 1 result." | |
| 30 | Learned-model track vs owner's verdict | FIXED | 7.1 item 2: "A learned model is a separate, later project with strict access control to the final test (your decision of 28 Sept); stop rule 3 below applies only if that project is ever started." | Source is the session's verdict that the owner agreed (Owner notes 1). Fine. |
| 31 | Exit times vs MT-G20 | FIXED | 7.2: "All Wave 1 exits are set at 15:50 or earlier (MT-G20)." | |
| 32 | "Only the first two have any real chance" | FIXED | Block D: "We put the first two first because they have the most published support. Even so, R3 expects none of the five to be a reliable edge, and for the gap-down fade 'not shown' will mean 'not testable' (only edges above about 8 bp net can be detected)." | |
| 33 | "R8 already did this" | FIXED | 7.1 item 1: "(R8 did something similar for the AI's picture reading: it scored the AI's answers against answers computed by code)." | |
| 34 | Corrections file elevates R8 | FIXED | `00`, E14: "our own small blind picture test (R8: 36 pictures, easy questions, one model) is the only direct evidence we have." | |

## 3. Remaining defects, ranked

Severity is my judgement: MED = an owner could be misled or a rule is brushed; LOW = wording, clarity or a small slip.

### R1 (MED). "10X is real" after "none is measured yet"

**Where:** 7.4 note (lines 303-305); box item 3 (lines 13-14); finding 7 (line 52); 7.4 row "Charts watched at once" (line 295).
**Quote:** "*These 'Yes' answers say what the design allows. None is measured yet ... Bottom line: 10X is real for coverage, record-keeping and rule-following in code.*"
**Problem:** "Real" contradicts "none is measured yet". "10X" is a ratio nobody has measured, and it is the owner's own headline phrase. The row "Charts watched at once ... Yes, for code" leaves out R7 section 4.3's caveat: "our universe is fixed at SPY and QQQ (MT-G23), and breadth only helps if each independent bet has skill". With two symbols and five chart speeds the bot watches ten charts against a person's "about 4 things", which is not obviously ten times. The bottom-line sentence was suggested by the earlier review itself (its #24) and conflicts with its own #8.
**Suggested wording:**
- Box 3: "**"10X more efficient than humans" is a fair description of the design for watching many charts, following rules, keeping records and testing ideas quickly, but none of it is measured yet. For profit it is undefined.**"
- Finding 7, first sentence: "**"10X more efficient than humans."** By design, in code: coverage, consistency, record-keeping, research speed and cost per decision. Not yet measured. Undefined for profit."
- 7.4 note: "Bottom line: by design, code should be far better than a person at coverage, record-keeping and rule-following. That is unmeasured, unproven for the AI, and undefined for profit."
- 7.4 header "Ten times better?" becomes "Better by design?". Row 1, last cell: "Yes for code, but the universe is only SPY and QQQ (MT-G23), and watching more charts only helps if each one has skill (R7)".
- `MINUTE_TRADING.md` line 71: "'10X' is a fair description of the design (not yet measured) for coverage, consistency, records and research speed; undefined for profit."

### R2 (MED). R8 (same folder) still overclaims, and conflicts with box item 1

**Where:** `R8 Picture-reading test.md` line 9, lines 22-24, line 76.
**Quotes:** "**Reading a clean chart by eye: essentially solved.**"; "The AI's picture-reading is good enough to help with messy screenshots (for example transcribing your cousin's screens)"; "Extending a trend earned nothing."
**Problem:** R8's own limit 1 says the task was "clean charts ... not 'read a messy trading-platform screenshot with hand-drawn lines'", and section 5 lists messy screenshots as a next test. So "good enough" for messy screenshots is untested. "Essentially solved" is one model on an easy synthetic task. "Earned nothing" is stated as fact on 36 pictures (on real days the trend call was right 18 of 32, 56%). The synthesis fixed these; the companion did not (the 05:00 edit fixed bullets 2 and 3 and section 5's last bullet only). Also, box item 1 says the AI "should not ... read numbers off pictures", while R8 section 5 proposes exactly that for the cousin's screenshots (with code checking every number). The synthesis never mentions this use.
**Suggested wording:**
- R8 line 9: "**Reading a clean chart by eye worked very well in this easy test.**"
- R8 lines 22-24: "The AI may be able to help with messy screenshots (for example turning your cousin's screens into journal notes), but that is untested: try it on his real screenshots first, and check every number by code."
- R8 line 76: "Extending a trend earned nothing in this tiny sample."
- Synthesis box item 1: "... but it should not pick trades or read numbers off pictures (one exception under test: turning your cousin's screenshots into notes, with every number checked by code)."
- Synthesis 7.5 item 1, after "a screenshot": "(We may ask the AI to turn it into notes; code then checks every number. This is untested, R8 section 5.)"

### R3 (MED). Block B's three R4 trials cannot follow the stated old-data plan

**Where:** 7.2 rules paragraph (lines 234-242) and block B ("9 trials: 6 from R1, 3 from R4").
**Problem:** 7.2 says every test runs "on 2016 to Aug 2024 prices", with the later window used only "to knock an idea out". R4's H1 uses VIX1D, which only starts in May 2022 (R4 F3 and data table), with train 13 May 2022 to 31 Dec 2023 and test 1 Jan 2024 to 28 Sep 2026. R4's H2 trains 2016 to 2021 and tests 2022 to Sep 2026. Both test windows run through the Sept 2024 to Sept 2026 window the document calls "not a clean final test", and inside the AI's training period (MT-G6). They also need the Cboe files, whose use is still open (7.5 item 8). This is a near-miss on MT-G6, not a breach: they are volatility forecasts, not trade tests.
**Suggested wording (add to block B):** "The three R4 trials use the Cboe files. VIX1D only starts in May 2022, so these tests must use 2022 to 2026 data, including the window that is not clean. They are volatility forecasts, not trade tests, and they wait for your answer on the Cboe files (item 8)."

### R4 (MED-LOW). Trial count: heading and "your call" vs MT-G7

**Where:** 7.2 heading (line 232) and the counting convention (lines 262-271).
**Quotes:** "about 114 new trials, counted the cautious way"; "If you would rather count it less finely, block E is 18 ... or 6 ... that is your call, because a lower count lowers the bar."
**Problem:** (a) "Cautious" is not true of blocks B, C, D and F, which use the reports' pooled counts. The paragraph itself says block C alone would be 36 if stored per symbol and look-ahead time, so 114 is a floor. (b) MT-G7's enforcement is "Code (gate); process (owner cannot waive)" and "the report fails if N_trials is lower than the number of stored return series". The owner can choose how the tests are designed (pooled or separate). The owner cannot choose what counts. Block E's arithmetic is right (2 x 3 x 3 x 2 x 2 = 72; 18; 6; totals 114, 60, 48).
**Suggested wording:** heading "(at least 114 new trials)". Convention, last part: "We recommend the 72-way count. If you prefer fewer separate tests (a single pooled test, for example), that is a change to the test design which we would write down before the run. The count can never be lower than the number of results the test machine stores (MT-G7). If blocks B, C, D and F are stored per symbol and look-ahead time the total is higher than 114 (block C alone would be 36)."

### R5 (LOW-MED). Section 6: two slips

1. **Line 189-190:** "All are hindsight back-tests before trading costs and taxes". R6 charged 5 bp a switch on the SPY and QQQ rules (R6 item 08) and 10 bp a switch on the ETF row (item 09). Only row 1's 9.8% is before costs (R6 item 07: 9.66% after 10 bp a switch). The error is on the cautious side but it is still wrong. Suggested: "All are hindsight back-tests, and none includes taxes. Row 1 is before trading costs (9.66% a year after 10 bp a switch); the SPY, QQQ and ETF rows already charge 5 to 10 bp a switch."
2. **Lines 203-204:** "The AI's real advantage here is discipline, not extra return: scanning 500+ stocks the same way every day ..." The minute bot trades SPY and QQQ only (MT-G23), stock books belong to the operations session, and the document's own rule is that code, not the AI, does the reading. Suggested: "A rule-following bot's real advantage here is discipline, not extra return: applying the same rule every day, rebalancing on schedule, never chasing top gainers and logging every skipped signal. (Scanning 500+ stocks would be a job for the stock books, not this bot.)"

### R6 (LOW-MED). Sentences a beginner still cannot follow; glossary gaps; length

- **Finding 9 (line 65):** "the ordinary 5% test" is not in the glossary. Suggested: "the usual 1-in-20 luck test".
- **Section 4, lines 141-144:** "a signal that moves the next hour by less than about 1.3 bp for each normal-sized change in the signal would be invisible to us ... Being detectable is not the same as being tradable." The last sentence does not follow from the one before. Suggested: "With two years of data we could only notice a trend-quality signal that moves the next hour's price by at least about 1.3 bp for each normal-sized change in the signal (our own rough estimate). That is about what a round trip costs, so a signal we could just notice would barely pay for itself, and a smaller one we could not notice at all."
- **7.2 counting convention (lines 262-271):** "result series", "look-ahead times", "H1 both sides ... H3 twice, H4", "(R1 T4)", "(R5 T3)". Nobody without R1, R3 and R5 can decode it. Suggest moving the block table and this paragraph to an appendix, keeping in 7.2 only: "Wave 1 is at least 114 trials; each counts against the bar."
- **Glossary gaps:** volatility ("how much prices move"); fade (two senses: "an edge fades" = weakens; "fade a gap" = bet against it); long and short ("buy first" and "sell first"; the bot is long-only); back-test ("running a rule on past prices"); RSI, MACD, stochastic, Bollinger, Fibonacci, Elliott ("popular indicators and drawing methods"); candidate (survived Wave 1, nothing more).
- **Length:** 7,227 words (about 35 minutes). Findings 8 to 10 are 153, 89 and 132 words. The box carries a reader who stops early, but consider a one-page front summary and moving 7.2's table to an appendix.

### R7 (LOW). Stop rules and Deciders

- **Stop rule 2** (lines 311-312): "After 100 AI decisions (MT-G34) and at least 40 sessions ..." MT-G34 has no 40-session wait: after 100 decisions the veto "stays on only if its shadow-scored value exceeds its API cost". At up to about 13 checks a day, 100 decisions arrive in under 10 sessions, so the rule as written keeps a costly veto on longer than MT-G34 allows. Suggested: "(2) After 100 AI decisions the veto stays on only if its scored value exceeds its cost (MT-G34). The separate 'clearly worse' test also needs at least 40 sessions (MT-G11)."
- **Stop rule 4** (line 315): "exceed the measured improvement" - improvement over what? Suggested: "exceed what the measurements show they add compared with doing nothing (cash)".
- **7.1 item 2** (line 220): "volatility timing" could be read as changing trade size, which MT-G14 forbids. Suggested: "(on/off only; trade size never changes, MT-G14)".

### R8 (LOW). Decision list

- **Item 8 (Cboe)** offers "accept that for private research" as an equal option. The owner's own v4 handoff (section I) says "Unknown permission does not become approval", and owner decision 4 says "Nothing illegal". Suggested: "My suggestion: email first. Until Cboe answers, the files are not downloaded on a schedule and block B's three Cboe trials wait."
- **AI layer status.** 7.1 item 3 describes the ordinary MT-G29 veto, but the live bot has no AI in v1 (`live/DESIGN.md` line 9-10: a test asserts the package never imports `anthropic`), and 7.5 has no item for it. Suggested sentence at the end of 7.1 item 3: "The live bot has no AI in v1. This layer is a later step and needs your OK and an API budget."
- **Give a suggested answer per decision** (for a beginner owner): e.g. item 2 "suggested: yes, no data fees, no orders"; item 4 "suggested: yes"; item 6 "suggested: out for now".
- **Item 9 (data rights) moved to section 8** ("A separate check of Alpaca's, IEX's and the SIP data terms is in progress; its result will be added to this folder."). I found no such file or register anywhere in the repo or scratchpad. Keep the sentence only if that check really is under way.

### R9 (LOW). Small wording and number points

1. Finding 8, line 56-57: "costs about 0.5 bp if the spread ... is 2 cents". A 2-cent spread is 0.26 bp; the rest is the sales fee (R3 section 2c: 0.26 + 0.21 = 0.47). Add "(the spread plus a regulatory fee)".
2. Finding 8, line 58-59: "the average 1-minute move was only 1.5 bp" means the average size (absolute) of a move. Say "the average size of a 1-minute move, up or down".
3. 7.2 bold sentence: "about 490 trades", "about 2 bp", "about 8 bp" are R3's own estimates ("my estimate"); add "(R3's estimates)".
4. Row 122: "The systems that faded are the noise-band and opening-range ones" reads as settled; use "appear to have faded". Row 133: "Strong in tiny equal-weighted stocks" contradicts the note "Only volatility forecasting is rated strong"; use "Large in tiny ...". Row 134: add "(a tiny test)" after "39% here".
5. Row 122: "stays negative after costs" is true at the lab's 3 bp; at 1 bp the 2026 figure (+1.3 gross) would be about +0.3. Add "at the lab's 3 bp".
6. 7.5 item 1: "most valuable, a journal of the trades he skipped" rests on R1's untested hypothesis (section 2 says so). Say "possibly the most valuable (R1's untested idea)". "Nothing can be said about his rules until ..." is stronger than MT-G11 ("no report may call a version working"; bad news acts sooner, MT-G12). Say "No report may call his rules 'working' until ...". At one trade a day the paper bot's own 60-trading-day whole-test stop arrives before 100 trades; mention that the owner would need to extend it.
7. Section 5, line 179: "Costs are higher than the first report said" - name it ("than R4 first said").
8. `00` E5 says "p < 0.0018 (our bar) about 2,270" trades; the synthesis says "our bar of t = 3 ... about 2,100". Two bars are both called "our bar". Harmless, but say which.
9. Section 4, lines 155-157: a stray line break in the autocorrelation bullet (cosmetic).

### R10 (LOW). `MINUTE_TRADING.md` "Chart-reading research" paragraph (lines 65-75)

Consistent with v3 on: no strong after-cost proof; code Reader with AI limited to veto and explain (MT-G29); 97.8% and "no skill predicting (small sample)"; Wave 1 "about 114 ... counted the cautious way (about 48 to 60 if counted more loosely ...)", "old data can drop ideas, not confirm them: MT-G6", "add to the trials already counted under MT-G7", "awaits the owner's OK"; the cousin request. The knock-on edits the earlier review asked for (no "coin flip", no "reject") are done. The folder `reports/Chart reading research/` now exists and its three key files match the staged copies.
Three points:
1. "Cboe VIX-family files are for private use only: never commit them." Add "(scheduled downloads await the owner's decision, synthesis 7.5 item 8)". The synthesis says even private scheduled use is unclear.
2. Line 71 repeats the "10X is honest for ..." wording (see R1).
3. "(about 48 to 60 if counted more loosely ...)" invites a lower count; see R4. Also "on 2016-2024 data" is not true of the three R4 trials (R3).

## 4. The box, the glossary and the decision list

**"If you read nothing else" box: clear, five items, plain.** Fixes needed: item 3 (R1) and item 1 (R2). Missing, in my view:
- The reason a minute bot struggles, in one line: "A round trip costs about 1 to 3 bp and a typical 1-minute move is about 1.5 bp, so a 1-minute trade cannot pay for itself; only holds of about 30 minutes or more have a chance."
- "Nothing changes in the live bot. The next step is Wave 1 (at least 114 small tests on old data); it needs your OK. Expect most to say 'not shown'."

**Glossary: good, 34 rows, all new rows accurate** (I checked PBO, SPA, absolute momentum, term structure, rescaling against the sources). Gaps: see R6.

**7.5 decision list: eight items, not nine.** Items 2, 4, 5, 6, 7 and 8 are real decisions; item 1 is a request; item 3 is "optional, later". All five decisions the earlier review asked for are present. Wave 1 (item 2) depends on item 8 for block B's Cboe trials (R3, R8). Suggested defaults would help (R8).

## 5. Rules and owner decisions: what I checked

No LLM in the order path (7.1 item 3 follows MT-G29 and MT-G32; R7's per-trade design is outside Wave 1 and the first build). No untested setup outside the exploratory lane (7.7). No size change (MT-G14 stated in row 118). Exits at 15:50 or earlier (MT-G20). MT-G11 stated correctly. MT-G23 and MT-G24: social, news and hype text are shadow-only and never read by order code. MT-G30 is cited for social text. For the AI veto the document implies forward-only scoring (7.3: "The AI-veto scoring ... need real-time capture and come later") and the AI plays no part in Wave 1, but it never says either in one line. Optional add to 7.1 item 3: "The AI plays no part in Wave 1: MT-G30 forbids scoring an AI on data from before its training cutoff." MT-G42 report present. Owner decisions 1 to 6 not contradicted. No promise of profit anywhere; section 8's last bullet is clear. No trading advice.

## 6. Numbers I re-derived or re-checked against sources

Hurdle table (65/82/impossible; 57/64/93; 53/56/67) from p = 0.5 + C/(2M); 60-minute 63% (R3 table); luck table 1.42, 2.0, 2.3; block totals 22+9+7+72+4 = 114 (and 60, 48); 72 = 2 x 3 x 3 x 2 x 2; 2,100 trades at t = 3 is 8.4 years at 250 a year; 4 bp versus 5.97 bp for 60 sessions; 97.8% = 27 wrong of 1,224; 44 + 22 + 32 = 98; LLM headline Sharpe 6.54 (2021 Q4) to 1.22 (Y_checker2); the lab's "realistic" cost is 1.5 bp a side; R6's cost treatment (5 to 10 bp a switch in rows 2 and 3); R2 sources for the candlestick and oscillator row; R4's H1 and H2 date ranges; R1 counts; 59 = 38 + 16 + 5.
Not verifiable from here: whether a data-rights check is really in progress; R3's typical-volatility assumption (15%), which the document now labels as an assumption.
