# Build report: blind chart-reading test

(Key material. Do not show this file, `truth.json` or the `_build/` folder to the readers. Readers get only the
`c_XXXX.png` pictures, `questions.md` and `manifest_blind.json`.)

## 0. Read this first: the data did not match the brief

The brief said the cache holds SPY/QQQ 1-minute bars from Jul 2024 to Sep 2026. **It does not.**
`trading/state/scalp_cache` holds only **2026-08-03 to 2026-09-28**: SPY and QQQ, 40 complete full-day sessions each,
390 bars per session, no half days, no missing minutes. I searched the file system for other minute-bar files. The only ones found are
pytest fixtures with fake prices (about 101 with constant volume 100), which I did not use, and worktree copies holding the same
four monthly file names. I fetched nothing (no network, no keys, no trading or data API calls), so the test was built from what exists.
What that changed:

| Brief | What was built | Why |
|---|---|---|
| 16 real sessions dated before 2026-07-01 and 8 dated 2026-07-01 or later | **0 before, 24 on or after** (dates 2026-08-03 to 2026-09-25) | no minute bars before 2026-08-03 exist |
| B7 skipped for pre-cutoff real sessions | B7 is asked for all 36 sessions | every real session is post-cutoff |
| Daily bars aggregated from minute bars, 110 earlier sessions | Daily bars taken from the repo's frozen official daily file `trading/evals/bars.csv.gz` (SPY and QQQ, 2016 to 2026-09-25) for all 60 candles and both averages of the real charts, and as the raw material for the synthetic daily paths | at most 39 earlier minute sessions exist; 110 are needed |

How close the substitute is: on the 39 sessions per symbol that both sources cover, the frozen daily bars match daily bars
built from the minute bars to within 0.008% on open/high/low and 0.024% on close (the official close
includes the closing auction); their volume is 10% to 48% higher (consolidated volume).
Volume is drawn as a multiple of the median, so this cannot show in the pictures. The aggregation code itself (first open,
max high, min low, last close, sum volume) is in `chartlib.daily_from_minutes` and produced those comparison numbers.

What this does to the test (more in section 9):

1. **All 24 real sessions come from one 8-week window.** Same market regime for every real picture. The real
   Chart C pictures share most of their history: two same-symbol Chart C pictures overlap by 47 of 60 candles on average
   (min 22, max 59). Across the 24 real Chart C pictures there are only **4 distinct largest-gap events**.
   Their answers are strongly correlated, so treat real Chart C results as a handful of independent observations, not 24.
2. Nothing dated before the 2026-07-01 cutoff, so no old-versus-new comparison is possible; on the other hand a reader whose
   knowledge ends before that date cannot have seen any of these days.
3. Re-running `python3 _build/build_chart_test.py` is deterministic (seed 7). If the cache is later filled with the full history
   it switches by itself to minute-built daily bars and to the 8 pre + 4 post-cutoff quota per symbol. **That branch has not been
   run on real data (none exists);** only the daily-aggregation function was checked, against the frozen file, as above.

## 1. What was built

- 36 sessions x 3 charts = **108 pictures** `c_0001.png` ... `c_0108.png`, 1000 x 700 px, RGB PNG, white background,
  no metadata, all with the same file time. Names are a random permutation of all pictures (order carries no information; permutation
  test on the position of synthetic pictures: p = 0.28).
- Sessions: **24 real** (12 SPY, 12 QQQ; 0 dated before 2026-07-01, 24 on or after) and **12 synthetic**
  (6 matched to SPY sessions, 6 to QQQ sessions). Chart A, B and C of a session are three separate pictures.
- `questions.md` (reader-facing questions with plain definitions and the answer format), `manifest_blind.json`
  (list of `{image, chart_type, questions}`, nothing else), `truth.json` (the key), this report.
- `_build/`: code (`chartlib.py`, `build_chart_test.py`, `verify_key.py`, `make_report.py`, `questions_text.py`, `stress_layout.py`),
  the exact data behind every picture (`session_data.json`), name map (`names.json`), pixel-check results (`render_qa.json`),
  verification results (`verification.json`).
- Random streams (numpy `default_rng`, seed 7): `[7,1]` picks the real sessions, `[7,2]` the templates of the synthetic ones, `[7,3]` the
  picture names, `[7,100+j]` and `[7,200+j]` the intraday and daily paths of synthetic session j.

## 2. The sample (36 sessions)

Sampling: from the full-day sessions of each symbol (all 40 of them), a seeded random order, first 12 per symbol that pass the rules,
**no two sessions share a date** (so no SPY and QQQ picture of the same market day; my choice, to avoid near-duplicate days).
A session is only skipped if a rule of the key would be undefined by an exact tie (highest high reached in both halves, equal
highest volume in two blocks, a close exactly on a level, equal EMA, equal price at 12:30, two equal largest gaps). Sessions
skipped: 0. Pre-cutoff shortfall against the quota of 16: 16.
For synthetic sessions `symbol` and `date` in `truth.json` are those of the matched real session.

| Session | Kind | Symbol | Date | Matched / twin | Chart A | Chart B | Chart C |
|---|---|---|---|---|---|---|---|
| R01 | real | SPY | 2026-08-03 | - | c_0092.png | c_0098.png | c_0066.png |
| R02 | real | SPY | 2026-08-06 | X01 | c_0042.png | c_0080.png | c_0091.png |
| R03 | real | SPY | 2026-08-11 | X02 | c_0057.png | c_0015.png | c_0001.png |
| R04 | real | SPY | 2026-08-19 | - | c_0107.png | c_0068.png | c_0065.png |
| R05 | real | SPY | 2026-09-04 | X03 | c_0026.png | c_0033.png | c_0095.png |
| R06 | real | SPY | 2026-09-08 | - | c_0016.png | c_0103.png | c_0018.png |
| R07 | real | SPY | 2026-09-09 | - | c_0071.png | c_0021.png | c_0040.png |
| R08 | real | SPY | 2026-09-10 | - | c_0031.png | c_0078.png | c_0100.png |
| R09 | real | SPY | 2026-09-15 | X04 | c_0058.png | c_0049.png | c_0105.png |
| R10 | real | SPY | 2026-09-17 | - | c_0030.png | c_0086.png | c_0076.png |
| R11 | real | SPY | 2026-09-21 | X05 | c_0104.png | c_0046.png | c_0097.png |
| R12 | real | SPY | 2026-09-25 | X06 | c_0106.png | c_0079.png | c_0039.png |
| R13 | real | QQQ | 2026-08-07 | X07 | c_0093.png | c_0059.png | c_0007.png |
| R14 | real | QQQ | 2026-08-10 | X08 | c_0070.png | c_0032.png | c_0003.png |
| R15 | real | QQQ | 2026-08-14 | - | c_0034.png | c_0099.png | c_0023.png |
| R16 | real | QQQ | 2026-08-17 | - | c_0024.png | c_0101.png | c_0044.png |
| R17 | real | QQQ | 2026-08-20 | X09 | c_0019.png | c_0005.png | c_0090.png |
| R18 | real | QQQ | 2026-08-25 | - | c_0064.png | c_0035.png | c_0025.png |
| R19 | real | QQQ | 2026-08-27 | - | c_0062.png | c_0060.png | c_0020.png |
| R20 | real | QQQ | 2026-08-28 | X10 | c_0008.png | c_0029.png | c_0087.png |
| R21 | real | QQQ | 2026-08-31 | X11 | c_0088.png | c_0061.png | c_0074.png |
| R22 | real | QQQ | 2026-09-11 | - | c_0017.png | c_0041.png | c_0055.png |
| R23 | real | QQQ | 2026-09-14 | - | c_0082.png | c_0022.png | c_0053.png |
| R24 | real | QQQ | 2026-09-16 | X12 | c_0036.png | c_0108.png | c_0073.png |
| X01 | synthetic | SPY | 2026-08-06 | R02 | c_0085.png | c_0043.png | c_0089.png |
| X02 | synthetic | SPY | 2026-08-11 | R03 | c_0084.png | c_0081.png | c_0027.png |
| X03 | synthetic | SPY | 2026-09-04 | R05 | c_0069.png | c_0028.png | c_0050.png |
| X04 | synthetic | SPY | 2026-09-15 | R09 | c_0077.png | c_0013.png | c_0094.png |
| X05 | synthetic | SPY | 2026-09-21 | R11 | c_0096.png | c_0045.png | c_0054.png |
| X06 | synthetic | SPY | 2026-09-25 | R12 | c_0047.png | c_0083.png | c_0067.png |
| X07 | synthetic | QQQ | 2026-08-07 | R13 | c_0075.png | c_0012.png | c_0011.png |
| X08 | synthetic | QQQ | 2026-08-10 | R14 | c_0004.png | c_0048.png | c_0006.png |
| X09 | synthetic | QQQ | 2026-08-20 | R17 | c_0037.png | c_0102.png | c_0009.png |
| X10 | synthetic | QQQ | 2026-08-28 | R20 | c_0063.png | c_0056.png | c_0038.png |
| X11 | synthetic | QQQ | 2026-08-31 | R21 | c_0052.png | c_0002.png | c_0072.png |
| X12 | synthetic | QQQ | 2026-09-16 | R24 | c_0014.png | c_0010.png | c_0051.png |

## 3. How the synthetic sessions were made

Goal: same number of bars, same per-minute volatility, same volume profile as the matched real session, but a zero-drift random
walk with no structure.

**Intraday (charts A and B).** Take the matched real session's 390 one-minute bars. Each bar is turned into a unit: its open, high,
low and close as log-ratios to the previous bar's close, together with its volume. Then:
1. The units are shuffled at random **inside each 10-minute block** (09:30-09:39, 09:40-09:49, ...). The 09:30 bar and the 15:59 bar stay in
   place so the opening spike and the last minute keep their slots. Shuffling only inside blocks keeps the day's shape (big candles
   and big volume at the open, quieter middle) that a whole-day shuffle would flatten; it is the one departure from the plain
   "shuffle all minute returns" recipe, made so the pictures look the same in style.
2. Each unit is then flipped up/down by a fair coin (mirror image around the previous close; high and low swap). This removes any drift or trend.
3. The bars are chained from the real day's first open, and prices are rounded to whole cents (real bars sit on the cent grid).
So the sizes of the moves, wicks and volumes are the real day's; only the order (inside 10 minutes) and the direction are random.

**Daily (chart C).** The matched real session's 110 daily bars (as units relative to the previous close, with volume) are shuffled
over the whole 110 days and flipped by a fair coin, chained from the real series' start, rounded to cents. The 20-day and 50-day
averages are then computed on the synthetic series exactly like on the real one.

Checks on the 12 synthetic sessions used (all passed unless noted): 390 bars each; bars valid (high >= open/close >= low, all
prices > 0, on the cent grid); the volumes of every 10-minute block equal the real block's volumes (as sets); the sizes of the
one-minute moves per block equal the real ones (within cent rounding); RMS one-minute move equals the real day's (ratio between
0.9988 and 1.0004); daily volume sets equal.
"No structure" statistics, from 3600 extra replicates (300 per template, other seeds): the sum of one-minute returns divided by its root-sum-of-squares
has mean -0.011 and sd 0.989 (fair-coin theory: 0 and 1); lag-1 autocorrelation of one-minute returns
-0.0030 (real templates: -0.041, a small negative bounce effect that the synthetic ones do not have;
too small to see); share of up minutes 0.487. Under this model B7 (next 30 minutes)
is a fair coin: P(up) = 0.492; B3 (EMA slope up) = 0.498. Because volatility is front-loaded like a real day, A4 "first half"
is 0.56 and A6 "breakout yes" is 0.52 under the model (not the textbook 0.5 and 0.67 of a flat-volatility walk).
(In the 12 sessions actually drawn, the sd of the per-session score was 0.55, lower than the 1.0 expected; with 12 sessions that is roughly a 1-in-70 draw. The
3600-replicate calibration shows the generator itself is right, so I take it as chance, but it is noted here.)

## 4. The pictures

One drawing routine (`chartlib.render_chart`) for all pictures, real or synthetic; nothing in the pictures depends on the kind.
White background, green candle when close >= open, red otherwise, no ticker, no date, no dataset name. Title says only the timeframe.
Price axis (right): % change from the first open shown. Volume panel: multiple of the median bar of that picture, dashed line = 1x.
- **A**: 60 one-minute candles 09:30-10:29, VWAP line (blue). Labelled gridlines every 10 minutes, faint every 5.
- **B**: 30 five-minute candles 09:30-11:59, VWAP (blue) and EMA20 of the 5-minute closes (orange). Labelled every 30 minutes, faint every 15.
- **C**: 60 daily candles, 20-day (orange) and 50-day (purple) simple averages computed from 110 daily bars so both span the whole chart;
  x axis is the candle number 1-60 (no dates); two dashed lines mark the thirds.
Definitions: VWAP = running sum of (typical price x volume) / running volume from 09:30, typical price = (high+low+close)/3 of each
one-minute bar; chart B samples that same line at the end of each 5-minute candle. EMA20 = pandas `ewm(span=20, adjust=False)` on the 30
five-minute closes, seeded with the first one. Daily volume in the frozen file is consolidated volume.

## 5. The key (`truth.json`)

Keyed by picture name. Each record: `session`, `kind` (real/synthetic), `symbol`, `date`, `post_cutoff` (true for all: synthetic sessions
are counted as post-cutoff because they are new paths), `chart_type`, `daily_source` (`evals`), `matched_session` (real <-> synthetic twin),
`truth` (answers, exactly the tokens of `questions.md`; A8, B6, C5 are null because clarity has no truth; B7 is `up`/`down`, C4 is
`{direction, third}`), `metrics` (the raw numbers behind each answer, e.g. `chg_pct`, `range_pct`, `crosses`, gap sizes), `flags`
(exact ties; empty everywhere) and `soft_flags` (borderline items, below).
All truths are computed by code from the same arrays that were drawn (`chartlib.truth_A/B/C`). Rules as coded: A1/B1 last close vs first
open with thresholds +-0.10% / +-0.15% (>= and <=); A2/B4 last close > VWAP; A3 sign changes of (close - VWAP) over the 60 closes;
A4 first bar holding the highest high, index <= 29 is `first`; A5 (max high - min low)/first open; A6 any close of bars 15..59 strictly above
the highest high of bars 0..14; A7 block of the highest-volume bar; B2 |last close - first open| / (max high - min low) >= 0.6; B3 EMA20 at
candle 30 > candle 25; B5 range of candles 19-30 < range of candles 1-12; B7 close of the 12:29 minute vs close of the 11:59 minute; C1 last close > SMA50;
C2 SMA20 > SMA50; C3 last close / first open of the 60 candles, +-3% strict; C4 largest |open - previous close| / previous close among the 59
gaps between two visible candles, position = the candle that opens with the gap (1-20 first, 21-40 middle, 41-60 last).

**Soft flags** (informational, nothing was dropped for them; tolerances are my judgement of what an eye can settle):

| Flag | Pictures |
|---|---|
| A1_within_0.02pp_of_threshold | 5 |
| A3_count_next_to_a_class_boundary | 13 |
| A4_two_halves_within_0.01pct | 1 |
| A5_within_0.03pp_of_threshold | 7 |
| A6_close_within_0.01pct_of_level | 1 |
| B1_within_0.03pp_of_threshold | 7 |
| B2_within_0.05_of_threshold | 2 |
| B3_ema_change_below_0.005pct | 6 |
| B5_ranges_within_5pct | 2 |
| C1_close_within_0.2pct_of_sma50 | 2 |
| C2_averages_within_0.2pct | 2 |
| C3_within_0.5pp_of_threshold | 8 |
| C4_gap_straddles_a_thirds_line | 1 |
| C4_runner_up_gap_within_15pct | 15 |

19 of 36 chart A, 15 of 36 chart B and 19 of 36 chart C pictures carry at least one soft flag. Suggested use: score once on all
items and once without flagged items (or per flag). Thresholds: A1 within 0.02 points of +-0.10; A2/B4 close within 0.01% of VWAP; A3 count of 1, 2, 4 or 5
(next to a class boundary); A4 halves' highs within 0.01%; A5 within 0.03 points of 0.25 or 0.50; A6 margin under 0.01%; A7 runner-up block within 5%;
B1 within 0.03 points of +-0.15; B2 ratio within 0.05 of 0.6; B3 EMA change under 0.005%; B5 ranges within 5%; C1/C2 within 0.2%; C3 within 0.5 points of +-3;
C4 runner-up gap within 15% of the largest, or the gap straddling a thirds line (candle 21 or 41).

## 6. Checks run

- **Independent recomputation.** A second implementation written differently (pure Python loops, string-based crossing count, raw cache files
  re-read without the lab loaders, the daily file read with the `csv` module) recomputed every answer for every picture:
  **720 answers compared, 0 mismatches; 324 numeric metrics compared, 0 mismatches.**
  (The first run showed one mismatch on C4: an off-by-one in the checker, not in the key; the case is the gap opening at candle 21, which the rule
  places in the middle third. Fixed in the checker and re-run.) Data behind the real pictures equals the raw files: minute bars
  72/72, daily bars 72/72 (counted per real picture: 24 sessions x 3).
- **Pixel checks on the rendered pictures** (all 108): 4518/4518 candle bodies have the right colour at the right place (0 wrong colours),
  5344/5344 volume bars, 2750/2750 sampled points on the indicator lines; text never leaves the canvas or overlaps,
  legend never sits on the plot: 0 pictures with layout problems. The same checks ran over all 80 real sessions x 3 charts
  (240 pictures) during development, which found and fixed clipped axis labels.
- **Picture-to-key check** (`verify_pixels.py`): answers read straight off the finished PNGs by pixel geometry, with no access to the data, compared with `truth.json`:
  A2 35/35, A4 36/36, A7 36/36, B4 33/33,
  C1 33/33, C2 36/36 agree; 7 readings were too close to a line to resolve (within 4 px) and are not counted.
  On the first pass (resolution limit 2 px) one C1 item disagreed: a close 0.03% above the 50-day line, less than one pixel, where the line is drawn over and hides the top edge of the
  candle body. The independent recomputation confirms the key (close 713.91 vs average 713.68); I set the pixel reader's limit to 4 px (line thickness) and it is flagged `C1_close_within_0.2pct_of_sma50`.
- **Files.** 108 pictures, sizes {'(1000, 700)': 108}, modes {'RGB': 108}, PNG text chunks 0, distinct file times 1, names sequential True,
  manifest and key match the files (True, True).
- **Leak scan** of `questions.md` and `manifest_blind.json` for words like real, synthetic, noise, random, template, symbols, years: hits [] and [];
  manifest keys ['chart_type', 'image', 'questions'].
- **Pictures I looked at: 3**, all scratch renders made with the same drawing code during layout work (a real 1-minute chart, a synthetic twin
  of it, a real daily chart), only to check that they render. None of the final pictures was viewed; I answered no question. After those views I changed
  label placement, the volume axis ticks (added "1x") and the plot width; those changes were checked programmatically only.

## 7. Class balance and majority-class baselines

`n` = pictures with a truth. "Baseline" = accuracy of always answering the most common class. Read the overall baseline first;
real and synthetic are shown separately because they differ (the real ones come from one 8-week window).

| Question | n | Classes (all) | Baseline (all) | n real | Baseline real | n synth | Baseline synth |
|---|---|---|---|---|---|---|---|
| A1 | 36 | down: 11, flat: 13, up: 12 | **0.36** | 24 | 0.33 | 12 | 0.42 |
| A2 | 36 | above: 18, below: 18 | **0.50** | 24 | 0.58 | 12 | 0.67 |
| A3 | 36 | 0-1: 5, 2-4: 10, 5+: 21 | **0.58** | 24 | 0.62 | 12 | 0.50 |
| A4 | 36 | first: 22, second: 14 | **0.61** | 24 | 0.62 | 12 | 0.58 |
| A5 | 36 | 0.25-0.50%: 18, <0.25%: 2, >0.50%: 16 | **0.50** | 24 | 0.54 | 12 | 0.50 |
| A6 | 36 | no: 17, yes: 19 | **0.53** | 24 | 0.50 | 12 | 0.58 |
| A7 | 36 | 09:30-09:39: 28, 09:40-09:49: 1, 10:00-10:09: 2, 10:20-10:29: 5 | **0.78** | 24 | 0.79 | 12 | 0.75 |
| B1 | 36 | down: 11, flat: 13, up: 12 | **0.36** | 24 | 0.38 | 12 | 0.42 |
| B2 | 36 | range: 26, trend: 10 | **0.72** | 24 | 0.71 | 12 | 0.75 |
| B3 | 36 | down: 20, up: 16 | **0.56** | 24 | 0.58 | 12 | 0.50 |
| B4 | 36 | above: 20, below: 16 | **0.56** | 24 | 0.54 | 12 | 0.58 |
| B5 | 36 | no: 8, yes: 28 | **0.78** | 24 | 0.71 | 12 | 0.92 |
| B7 | 36 | down: 17, up: 19 | **0.53** | 24 | 0.54 | 12 | 0.50 |
| C1 | 36 | no: 10, yes: 26 | **0.72** | 24 | 0.79 | 12 | 0.58 |
| C2 | 36 | no: 11, yes: 25 | **0.69** | 24 | 0.75 | 12 | 0.58 |
| C3 | 36 | down: 9, flat: 11, up: 16 | **0.44** | 24 | 0.42 | 12 | 0.50 |
| C4 both | 36 | down / first third: 16, down / last third: 1, down / middle third: 10, up / first third: 4, up / last third: 3, up / middle third: 2 | **0.44** | 24 | 0.58 | 12 | 0.33 |
| C4 direction | 36 | down: 27, up: 9 | **0.75** | 24 | 0.92 | 12 | 0.58 |
| C4 third | 36 | first third: 20, last third: 4, middle third: 12 | **0.56** | 24 | 0.58 | 12 | 0.50 |

Things to notice: **A7** (volume peak) is the first block in about 78% of pictures, so it barely discriminates;
**B5** has a 78% baseline; **C4 direction** is `down` in 22 of 24 real pictures (only 4 distinct gap events behind those 24 pictures)
but split in the synthetic ones; C1/C2 are mostly `yes` for the real charts (uptrend in this window) and more even for the synthetic ones. A model that
says "up" or "above" by habit will look decent on some real items for reasons unrelated to reading. For the confidence-weighted B7, the synthetic
pictures are a fair coin by construction (the 12 synthetic B pictures: up 6, down 6), so any edge there is chance.
The score for C4 can be taken on direction, on third, or both (`C4 both` above).

## 8. Answer format the readers were given

One JSON object per picture: `{"image": "c_XXXX.png", "A1": ..., ...}` with `B7` as `{"direction", "confidence"}` and `C4` as `{"direction", "third"}`
(details and allowed tokens in `questions.md`). Clarity ratings (A8, B6, C5) are integers 0-10 with no truth; compare their averages between real
and synthetic pictures, ideally by matched pair (`matched_session`).

## 9. Issues, limits and judgement calls

1. **Data range** (section 0): no pre-cutoff sessions, daily candles from the frozen daily file, one 8-week regime.
2. **Real Chart C is nearly one observation per symbol-regime** (24 pictures, 4 distinct largest gaps, on average 47 of 60 candles shared). Do not read 24 independent tests out of it.
3. **Twins.** Each synthetic picture has a real twin with the same bar sizes and (chart A) the same volume per 10-minute block, in shuffled order inside the block;
   chart C twins have the same daily-move sizes and volumes across the 110 days. A reader who sees both may notice the similarity. Pair them in the analysis
   by `matched_session` (12 pairs). The synthetic record carries its real twin's symbol and date only as a label.
4. **Small differences left between real and synthetic** that I know of: real one-minute returns have lag-1 autocorrelation about -0.04, synthetic about 0 (invisible);
   synthetic daily paths have no volatility clustering or trend by design; real daily charts of this window mostly drift up.
5. **Volatility is front-loaded in the synthetic days by design** (see section 3), so their class balance for A4/A6 differs from a textbook random walk.
6. **Borderline items** exist in every question (soft flags, section 5); nothing was removed for them, so human-level ambiguity is part of the measured error.
7. **Definitions chosen by me where the brief was silent:** VWAP with typical price; EMA seeded from the first 5-minute close; SMAs from 110 daily bars; C4 counts only the 59
   gaps between visible candles; B7's "price at 12:30" is the close of the 12:29 minute; ties would have excluded a session (none did); doji candles are green (close >= open).
8. **Environment.** matplotlib was missing and was pip-installed into the Python environment (not the repo). The repo was only read: no repo file changed during
   the build (checked by file times), no bytecode written there, and under `trading/state/` I only read the four cached bar files, their `.json` notes and the calendar.
   Scratch renders for layout work went to a folder `scratchpad/smoke` that I created and deleted afterwards; I did not check beforehand that the name was free,
   but nothing else in the scratchpad refers to it.
9. **Not tested:** the full-history branch of the build script (needs data that does not exist here), and how readers behave. Rendering was verified by pixel checks, not by eye,
   apart from the three scratch pictures named in section 6.
