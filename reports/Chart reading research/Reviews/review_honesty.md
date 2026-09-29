# Independent review: honesty, clarity and rules lens

**Version reviewed:** `01 Synthesis and plan.md` and `00 Fact-check corrections` as saved at 04:49:38, `R8 Picture-reading test.md` as saved at 04:46:00, `MINUTE_TRADING.md` as saved at 04:49:38.
History: I read the 04:25 version first, wrote a full review, then re-read after two revisions (04:45 and 04:49). The 04:49 revision adopted almost all of my earlier wording, so this file lists only what is still open against that version. Fixed points are in section 3. If the files change again, re-check the quoted sentences before acting.
Also read for source-checking: `Why day traders lose.md` section 4, R1 to R7 and the four checker reports. Read-only: no repo file edited, no git, no trading API. I did not open the other reviewer's file.

## 0. Tally and top three

**9 open defects: 4 overclaiming, 1 rules, 3 clarity, 1 missing.**

Top three:
1. **Trial counting (7.2):** the convention says "count the larger number" but counts block E at 6 while R5 lists 18 to 72; the Wave 1 total would be about 60 to 114, not 48 (defect 1).
2. **"Small effects (about 1 bp) are invisible even in 8 years" (7.2)** contradicts item 8's own "about 2,100 trades (about 8 years)". This is wording I suggested; it needs the fix in defect 2.
3. **Section 3's candlestick and oscillator row now over-corrects** ("no rule survived costs"): R2 records RSI/MACD variants that beat buy-and-hold after a 1% round-trip cost in old samples (defect 3).

Overall: the document is now much more honest than the 04:25 version. The AI section follows MT-G29, the Wave 1 paragraph no longer calls anything a "pass" or gives the used window a "final look", the cost table includes the lab's 3 bp level, and the picture and preprint claims carry their limits. What is left is small.

## 1. Direct answers to your questions

- **"Old data can reject but not confirm": consistent with MT-G6 and MT-G30?** Yes, in the 04:49 text. MT-G6's last sentence (only forward data after registration is a clean holdout for AI-designed ideas) is followed; the Sept 2024 to Sept 2026 window is now called "not a clean final test"; "pass" became "candidate". MT-G30 covers LLM signals and vetoes, which Wave 1 does not use. One sentence needs repair (defect 2).
- **Picture-test result described with its limits?** In the synthesis, yes (item 6 and section 8). R8 itself still carries the old wording (defect 4).
- **Sentences that promise profit, an edge or "10X"?** None. "Zero violations by design" became "a broken rule shows up as a bug we can find", and the 10X table has a "these are what the design allows, none measured" note.
- **Advice to trade?** None.
- **Rule conflicts:** only the trial count (defect 1). No LLM in the order path (7.1 item 3 now follows MT-G29 and MT-G32), no social or hype input to orders, nothing outside the exploratory lane, no stock-book or options-lab edits.

---

## 2. Open defects, ranked

Tags: RULES, HON (overclaiming or certainty), CLARITY, MISSING.

**1. [RULES] The counting convention contradicts itself, and the ChatGPT strategies are listed as already tried.**
Quotes (7.2): "**Counting convention** (fixed when the tests are registered; if in doubt, count the larger number, because an undercount weakens the bar) ... block E counts R5's T3 as three quality variants by two windows, with horizons, symbols and eras treated as one test each (R5 itself says "dozens" if they are counted separately)". And: "on top of everything already tried across the whole minute project (MT-G7): at least the 28 from the first backtest, the two ChatGPT-spec strategies, and the rule variants R5 and R6 tried while looking".
Problems:
- The rule says count the larger number, then counts E at the smaller. MT-G7 counts "every parameter set, variant and prompt version". R5 section 3.6 lists two windows, three quality variants, three horizons, two symbols and two eras, which is 72. Counting each outcome horizon (+30 minutes, +60 minutes, the close) as its own test, with symbols pooled, gives 18. So block E is 18 to 72, not 6, and the Wave 1 total is about 60 to 114, not 48. The same question applies to block C (R1 T4: 9 level types, SPY and QQQ, next 15 to 30 minutes) and block B (SPY and QQQ). An undercount lowers the deflated bar, which is what MT-G7 exists to prevent.
- "The two ChatGPT-spec strategies" have not been run: MINUTE_TRADING.md says they must still be added to the backtester as new registered versions.
Suggested wording: either follow the convention or change it, and tell the owner which:
> Block E counts R5's T3 with every window, quality variant, horizon, symbol and era as its own test (72), because our convention is to count the larger number. That makes Wave 1 about 114 new trials, not 48. (If you prefer to count a pooled regression once, block E is 18 and the total is about 60; that is your call, because a lower count lowers the bar.) Blocks B and C are counted the same way.
And: "at least the 28 from the first backtest and the rule variants R5 and R6 tried while looking, plus the two ChatGPT-spec strategies once they are registered".
If the total changes, update every "about 48" (7.2 heading, block table, "Wave 1 is about 48 *new* trials", MINUTE_TRADING.md).

**2. [HON] "Small effects (about 1 bp) are invisible even in 8 years" contradicts item 8.** (This is wording I suggested in my first pass. It was too loose.)
Quote (7.2): "Old data can drop an idea only if its effect would have been big enough to see. Small effects (about 1 bp) are invisible even in 8 years, and the gap-fade test can only see effects above about 8 bp."
Item 8 says a +1 bp edge takes "about 2,100 trades (about 8 years at one trade a day)". A one-trade-a-day setup over 2016 to Aug 2024 (about 2,170 sessions) can just see 1 bp. What is true is that setups that trade rarely see much less: R3 estimates about 490 trades for the late-day test (able to see about 1.8 bp at the ordinary 5% test) and about 350 for the gap fade (about 8 bp).
Suggested wording: "Old data can drop an idea only if its effect would have been big enough to see. A +1 bp edge needs about 2,100 trades to see. The late-day test will have only about 490 trades and can see effects of about 2 bp or more (more at our stricter bar), and the gap-fade test only above about 8 bp. Smaller real effects would be missed."

**3. [HON] The section 3 row for candlesticks and oscillators now over-corrects.**
Quote: "Candlesticks and the oscillators were tested and no rule survived costs or added value; Fibonacci, Elliott and drawn trendlines are barely tested or subjective. We found no test showing a profit after costs (our searches ran out)".
Problem: R2 records that Chong and Ng (2008) and Chong, Ng and Liew (2014) found MACD and RSI variants that beat buy-and-hold in Italy, Canada and (RSI) the Dow, after a 1% round-trip cost, for the best variants only, in old samples with no allowance for having tried many variants ("Weak"). Lu et al. found profitable bullish candlestick patterns in Taiwan and the Dow (costs not stated). The stochastic oscillator was only tested as a filter. What failed is the careful test: Duvinage et al. (5-minute Dow stocks) found that after correcting for the number of rules tried, none beat buy-and-hold after costs. So "no rule survived costs" is too strong for RSI/MACD, and "no test showing a profit after costs" is false for them.
Suggested wording (evidence cell):
> Candlesticks: the careful test (5-minute Dow stocks, after allowing for the number of rules tried) found no rule that beat buy-and-hold after costs; a few small positive studies in other markets did not state costs. RSI, MACD, Bollinger: weak; a few variants beat buy-and-hold after costs in old samples, with no allowance for trying many. Stochastic: barely tested. Fibonacci, Elliott, drawn trendlines: barely tested or subjective. We found no profit after costs that held up once the number of tries is allowed for (our searches ran out).
Item 2 in section 1 is fine as written.

**4. [HON] R8 still carries the wording the synthesis dropped.**
R8 section 1: "**Predicting what comes next: no skill.**" and "**It cannot tell a real day from random noise by looking.**" R8 section 5: "It extends trends and finds noise as tradeable as real days." The synthesis (item 6) now says "we saw no skill ... a small skill could hide" and that a gap of about a point "could hide". R8 sits in the same folder and will be read.
Suggested wording: R8 section 1: "**Predicting what comes next: we saw no skill** ... (a sample this small cannot rule out modest skill either way)." and "**Its clarity ratings did not separate real days from random noise in this small sample** (a gap of about one point could hide)." R8 section 5: "It extends trends, and its clarity ratings did not separate real from random days in this small sample."

**5. [MISSING] The per-trade AI check has no decision status, and 7.5 item 9 asks the owner for nothing.**
Quotes: 7.1 item 3: "R7's design goes further (an ALLOW or VETO on every candidate trade, its Test D); that would need an MT-G29 amendment and starts as shadow scoring only." 7.5 item 9: "**Data rights in general:** a separate check of Alpaca's, IEX's and the SIP terms is in progress (see the data-rights register when it is finished)."
Problems: the reader cannot tell whether the per-trade check is planned. It is in neither Wave 1 nor the decision list, it would cost API money (three runs each, MT-G32; value must exceed cost, MT-G34), and an MT-G29 amendment needs the owner's written OK (MT-G41 logs guardrail changes). Item 9 asks for nothing, and points to a file that is not in the folder or in section 9.
Suggested wording: 7.1 item 3, last sentences: "R7's design goes further (an ALLOW or VETO on every candidate trade, its Test D). That is not part of Wave 1 or the first build. It would need an amendment to MT-G29 and your written OK, and would start as shadow scoring only." Move 7.5 item 9 to section 8: "A separate check of Alpaca's, IEX's and the SIP data terms is in progress; its result will be added to this folder." List the register in section 9 when it exists.

**6. [HON] Assumptions stated as facts, and figures on different bars.**
- Section 5 note and item 8: "against a typical 15%. In a typical year moves are about twice as large and the hurdles correspondingly lower" and "In a normal, more volatile year the moves are bigger and these hurdles are lower". The 15% is R3's own assumption ("if typical SPY volatility is about 15% a year (my assumption)"); no checker verified it. Add "(R3's assumption, not checked)".
- Item 8: "about 2,100 trades" is at a t of 3; "about 4 bp" for 60 sessions is at the ordinary 5% test. At our own bar it is about 6 bp (my arithmetic on R3's numbers: 3.84 x 12.04 / sqrt(60)). Suggested: "Sixty paper sessions could only reveal an edge of about 4 bp at the ordinary 5% test, or about 6 bp at our stricter bar."
- Item 5 says "would have made 9.8% a year" but only section 6 adds "before trading costs and taxes". Add "(in hindsight, before trading costs and taxes)" to item 5.
- Section 3, intraday momentum row: "still found in 2000-2020 (Baltussen)". That result is for stock-index and other futures, before costs. Add "in futures, before costs".
- Section 4 last bullet ("Yesterday's market move used to help predict today's...") is for the whole US stock market, not SPY. Add "(whole US market, not SPY)".
- Item 6: "rated random-walk pictures as 'clear and tradeable' about as often as real days". It was a 0-10 rating. Say "about as high as real days (5.8 against 5.5 out of 10 on the 1-minute charts)".

**7. [CLARITY] The fixes introduced jargon that the glossary does not cover.**
Used with no gloss: PBO and "reality-check p" (7.2); "planted-truth reading audit", "R7 Test A", "qualitative questions" (stop rule 1); "absolute momentum" (section 6); "term structure", "put/call", "skew" (section 3); "lead-lag", "order flow" (section 3); "rescaling" (section 3); "ORB5", "LAST30_MOM_SPY", "NOISE_MOM_SPY" (7.1, block B). The names "Paz, Delgado" (section 3, intraday momentum row) appear nowhere else.
Suggested glossary rows:

| Term | Plain meaning |
|---|---|
| PBO | the chance that our best result is just the luckiest of many tries; we want 0.20 or less |
| reality check (SPA) | a test of whether the best of many rules really beats luck |
| planted-truth reading audit | we put known answers into test charts and check the reader gets them right |
| absolute momentum | hold an asset only if it rose over the last 12 months, otherwise hold cash |
| term structure | short-term against longer-term volatility readings; short-term higher than long-term signals stress |
| put/call, skew | put/call: the ratio of bearish to bullish option bets; skew: how much more crash insurance costs than upside bets |
| lead-lag, order flow | lead-lag: one market moving a fraction of a second before another; order flow: the stream of buy and sell orders |
| rescaling | putting every chart on the same scale, which is where much of the "picture" advantage in the research came from |
| ORB5, LAST30_MOM_SPY, NOISE_MOM_SPY | our three test setups: the 5-minute opening range breakout; momentum into the last half hour; a trend-following band strategy |

Replace "(Paz, Delgado, our ORB5)" with "(two 2026 preprints and our own ORB5 test)". Replace "R7 Test A" in stop rule 1 with "the reading audit".

**8. [CLARITY] SKEW and VVIX: section 3 says "log only", section 5 puts them in the yardstick.**
Section 5: "a volatility yardstick (Cboe's VIX, VIX1D, VIX9D, VIX3M, VVIX and SKEW files), used only to skip quiet or wild days". Section 3: "VIX1D and term structure are mixed, SKEW and VVIX weak: log only".
Suggested wording: "a volatility yardstick (Cboe's VIX and VIX1D files, used only to skip quiet or wild days; VIX9D, VIX3M, VVIX and SKEW are logged only)".

**9. [CLARITY] Item 8 is dense, the document has grown by about 70%, and the header carries process talk.**
Item 8 is 202 words with about 23 numbers; the whole document went from about 3,900 to about 6,600 words. The brief says "plain, short English". The "If you read nothing else" box helps.
Suggestions: split item 8 into "8. The cost hurdle" and "9. How long it takes to tell luck from an edge" (renumber the rest). Move the block table and the counting convention in 7.2 to a short appendix if the owner only needs the answer. The header sentence "Two independent reviewers then went through this document and their fixes are in" is process detail for an owner who is new to trading, and it must be true when read (defects 1 to 6 are still open). Delete it, or write "Two independent reviews of this document are kept in the folder."

---

## 3. Fixed since my earlier passes (checked against the 04:49 text)

AI veto now follows MT-G29 and MT-G32 and the 7.4 rows and stop rules match; Wave 1 rules paragraph (no "pass", no "final look", used window called not clean, "drop" not "reject"); whole-project trial count, the pass bar (MT-G1, G5, G7), the missing machinery and the two random-baseline fixes; "Published edges fade" now hedged; "measured" spread, calm sessions, 3 bp column, "detecting" wording, 54-55% called R3's conversion; item 2 wording and "toll"; item 6 and the picture limits in section 8; scoreboard "None" rows split into tested and not tested; "Zero violations" and the "Yes" column; item 7 wording and "score"; section 6 (what was reproduced, hindsight, costs and taxes, level and ahead years, 2022, insurance, "edge"); R-squared "a third"; 1.3 bp "our own rough estimate"; "almost never"; "a side"; option half-spread; MT-G11 sessions; cousin funnel; retail dataset wording; attention spikes; 7.3 forward-data sentence; MT-G14 size caps; MT-G42 report; learned-model track; 15:50 exits; "not testable" for the gap fade; owner decisions 4 to 8; hindsight in the skipped-trade journal; 28 checked claims; social-text pipeline; glossary; "so what" lines; the corrections file E14 wording; MINUTE_TRADING.md summary lines.

## 4. Checked and found clean

- No order input from social, news or hype data. Hype is defined from price and volume only, text is shadow-only, quarantined and needs the owner's OK (MT-G23, MT-G24, MT-G30).
- Nothing is enabled in the bot without review and the owner's OK (7.7). No untested setup is placed outside the exploratory lane (owner decision 3). The learned-model and per-trade AI tracks are "later".
- No stock-book or options-lab edits. Section 7.6 hands its notes to the operations session. Wave 1 uses read-only data from the scalp account (owner decision 1). Options stay shadow-first with no 0DTE (decision 5, MT-G28).
- Numbers that match their sources: 97.8%, 27 of 1,224, 99.3% and 86.8% (R8), 59 features (38, 16, 5), about half formulas, a third judgment (R1 tags), 82/64/56, 65/57/53 and 93/67/63 at 3 bp, 44 of 98 years (ahead 22, level 32), $5.6 and $13.2, -43% and -84%, SPY 200-day 8.6% against 10.9%, 2022 figures, 10.4% against 15.0%, LAST30 gross -1.5 to +1.3 bp, the block totals (22+9+7+6+4 = 48 as counted), 28 checked claims, 1.42 / 2.0 / 2.3.
- Section 8's last bullet ("Nothing here is a claim that any strategy makes money. No claim of profitability or live readiness follows.") is good and should stay.
