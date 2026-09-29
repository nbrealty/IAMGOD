# R8. Can the AI read a chart picture? A blind test (29 Sept 2026)

*Run by the minute-trading session. Nothing here touches orders or the account. The build code, questions, answer key, the
readers' answers and the scoring script are in `picture test/`. The pictures themselves (108 PNGs) are not stored: they are
rebuilt from the code and the cached bars (seed 7). Raw market data is not stored either.*

## 1. Short answer

- **Reading a clean chart by eye: essentially solved.** On 17 scored items per market day (7 for the 1-minute chart, 5 for the 5-minute chart, 5 for the daily chart), six readers
  (two independent passes over every picture) were right **97.8% of the time** (27 wrong of 1,224 answers; 99.3% on the 15
  core questions, 86.8% on the hardest, the largest gap). The two passes gave the same answer 97% to 100% of the time on the
  15 core questions, and 89% to 92% on the largest-gap and next-30-minutes questions.
- **Predicting what comes next: we saw no skill.** Asked whether the price would be higher or lower 30 minutes after the chart
  ended, the AI was right **28 of 72 times (39%)**, no better than a coin flip (two-sided p = 0.08; counting each picture
  once, 14 of 36, p = 0.24). It said "up" or "down" by extending the trend it saw: its answer followed the chart's own
  trend in **93%** of the pictures with a visible trend (43 of 46), yet the price continued that way only **48%** of the time
  (22 of 46). Its stated confidence was 53%, close to a coin flip. A sample this small cannot rule out modest skill either way.
- **Its clarity ratings did not separate real days from random noise in this small sample.** It rated the "clarity and
  tradeability" of pure random-walk pictures (same volatility and volume, no structure) about as high as real days (5.8
  versus 5.5 on the 1-minute charts, 6.2 versus 5.7 on the 5-minute charts; differences not significant, and a gap of about
  one point could hide).
- **So:** the agent's *reading* should be done by code, which is exact, free and testable, and already has the numbers.
  The AI's picture-reading is good enough to help with messy screenshots (for example transcribing your cousin's screens),
  but any number it reads must be checked by code. It must not be a source of trade ideas from pictures.

## 2. How the test worked

- **108 pictures = 36 market days x 3 charts.** 24 real days (12 SPY, 12 QQQ, 3 Aug to 25 Sep 2026, all after the model's
  knowledge cutoff) and 12 **synthetic twins**: each is a real day's bars reshuffled inside 10-minute blocks and flipped up or
  down by a fair coin, so it has the same move sizes, wicks and volumes but no trend or pattern.
- **Chart A:** 60 one-minute candles (09:30 to 10:29) with volume and VWAP. **Chart B:** 30 five-minute candles (09:30 to
  11:59) with volume, VWAP and a 20-period EMA. **Chart C:** 60 daily candles with volume and 20- and 50-day averages.
  All pictures look identical in style, with no ticker and no date; price is shown as percent change from the first open;
  volume as a multiple of the median bar.
- **Questions with plain rules** (for example "has the price gone up, down or stayed flat: up if the last close is at least
  +0.10%"; "how many times do closes cross the VWAP: 0-1, 2-4, 5+"; "which 10-minute block holds the tallest volume bar";
  "is the 20-day average above the 50-day"; "where is the largest gap"). The answer key was computed by code from the data,
  checked against an independent recomputation (720 of 720 answers) and against pixel readings of the pictures.
- **Blind readers.** Six separate AI agents (two independent passes over each chart type, the second pass in reverse
  order) saw only a folder with the pictures, the questions and a list with no labels. They were told to read by eye, not to
  write code to measure pixels, and not to open anything else. An audit of their tool calls shows **no reads outside the
  folder and no image-analysis code**; their only shell commands checked their own answer files.
- The exact questions, rules and answer format are in `picture test/questions.md`.

## 3. Results

| Question (chart) | Majority-answer baseline | Both passes: right | Real days | Random twins |
|---|---|---|---|---|
| Up, down or flat (A1) | 36% | 100% | 100% | 100% |
| Last close above or below VWAP (A2) | 50% | 100% | 100% | 100% |
| Crossings of VWAP: 0-1 / 2-4 / 5+ (A3) | 58% | 99% | 98% | 100% |
| Which half holds the high (A4) | 61% | 100% | 100% | 100% |
| Size of the range, 3 buckets (A5) | 50% | 100% | 100% | 100% |
| Breakout above the first-15-minute high (A6) | 53% | 97% | 96% | 100% |
| Block with the tallest volume bar (A7) | 78% | 100% | 100% | 100% |
| Up, down or flat, 5-minute (B1) | 36% | 100% | 100% | 100% |
| Trend day or range day by a stated rule (B2) | 72% | 100% | 100% | 100% |
| EMA20 higher or lower than 5 candles ago (B3) | 56% | 100% | 100% | 100% |
| Last close above or below VWAP (B4) | 56% | 100% | 100% | 100% |
| Is the late range smaller than the early range (B5) | 78% | 99% | 98% | 100% |
| Close above the 50-day average (C1) | 72% | 97% | 96% | 100% |
| 20-day average above the 50-day (C2) | 69% | 100% | 100% | 100% |
| 60-day change: down / flat / up (C3) | 44% | 97% | 100% | 92% |
| Largest gap: direction (C4) | 75% | 86% | 90% | 79% |
| Largest gap: which third of the chart (C4) | 56% | 88% | 90% | 83% |

**Where it went wrong.** 27 wrong answers in all: 19 on the hardest question (the largest gap out of 59, which needs
comparing every gap on a 60-candle chart), and 8 spread over the 60-day change, the 50-day average, the breakout, the
VWAP-crossing count and the range comparison. We checked the 4 mistakes on the 60-day change and the 50-day average against
their numeric cut-offs: all four were on pictures whose true value sat close to the cut-off, where a person would also
hesitate (and no mistake on the other cut-off questions was far from its cut-off either). The other 4 (breakout,
VWAP-crossing count, range comparison) were not analysed further. None looks like a gross misreading.

**Prediction question** (36 pictures, both passes = 72 answers): 28 right (39%). Real days: the chart's trend continued in
18 of 32 answers (56%); random twins: in 4 of 14 (29%). The AI followed the trend in all 32 real-day answers where a trend was visible.
Extending a trend earned nothing.

**"How clear and tradeable does it look?" (0 to 10)** The two passes agree closely (correlation 0.90) but the rating does
not separate real from random: 1-minute charts 5.52 real versus 5.79 random (p = 0.69); 5-minute charts 5.73 versus 6.21
(p = 0.45). With 24 real and 12 random pictures a difference of about one point cannot be ruled out. The daily-chart
rating (4.52 real versus 6.96 random) is **not interpretable**: the 24 real daily pictures share most of their candles
(only about 4 distinct events), so they are not 24 independent observations.

## 4. Limits (read before quoting any number)

1. **The task was easy on purpose.** Clean charts, one consistent style, every rule written in the question. This tests "apply a
   stated rule to a clear picture", not "read a messy trading-platform screenshot with hand-drawn lines", and not "judge like
   a trader".
2. **Small sample.** 24 real days (plus 12 random twins); all real days from one 8-week window (Aug to Sep 2026, a single market regime). The cache in
   this session held only those 40 sessions, so no old-versus-new comparison was possible.
3. **One model, read twice.** By R7's proposed bar (at least 98% right on qualitative questions for any format allowed near
   a decision), the picture format passes on the 15 core questions (99.3%) and fails on the largest-gap question (86.8%).
   The two passes are the same model, so their agreement shows consistency, not independent
   confirmation. Other models (and older ones) may read worse; the 2024 benchmark figures (47% versus 80% for humans, on hard
   chart questions) should not be applied to this task.
4. **The prediction result is a tiny sample.** It fits the 2026 candlestick papers (R7: models follow the recent trend), but
   72 answers on 36 days is a consistency check, not proof.
5. Daily charts of real days overlap heavily; their results count as a handful of independent cases.

## 5. What it means for the design

- Keep the **Reader in code** (R7 section 4.1): every fact the AI got right here, code gets right too, for free, in
  microseconds, and it can be unit-tested against planted-truth charts.
- Use the AI's picture-reading only where there is no data: turning **screenshots of the cousin's screens** into structured
  journal entries (levels, indicator states, notes), then **checking every number by code** against the real bars.
- Never take a trade idea, a direction or a "looks clean" judgement from a picture. It extends trends, and its clarity ratings
  did not separate real from random days in this small sample.
- Next tests worth doing: (a) real, messy screenshots (a platform layout with drawings) scored against the data;
  (b) the same test on other models; (c) a **picture-versus-table** comparison on forward paper data (R7 Test E), logged in
  shadow only; (d) scoring the AI's veto on every candidate trade going forward (MT-G29, MT-G32).

## 6. Files (`picture test/`)

`questions.md` (exact questions and rules), `manifest_blind.json` (what the readers saw), `truth.json` (answer key), `build_report.md`
(how it was built, class balances, the synthetic-day method), `_build/*.py` (code that builds the pictures and checks the key),
`reader_answers/pass{1,2}_{A,B,C}.json` (every answer), `score_reading_test.py` and `reading_test_scores.md` (scoring).
