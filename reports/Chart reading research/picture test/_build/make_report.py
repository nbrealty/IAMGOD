#!/usr/bin/env python3
"""Write build_report.md from the actual outputs (truth.json, verification.json, build_log.json, render_qa.json)."""
from __future__ import annotations

import datetime as dt
import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
OUT = HERE.parent
sys.path.insert(0, str(HERE))

import numpy as np                                    # noqa: E402

import chartlib as cl                                 # noqa: E402

truth = json.loads((OUT / "truth.json").read_text())
ver = json.loads((HERE / "verification.json").read_text())["checks"]
blog = json.loads((HERE / "build_log.json").read_text())
rqa = json.loads((HERE / "render_qa.json").read_text())
pix = json.loads((HERE / "verify_pixels.json").read_text())

# ------------------------------------------------------------------ class balances
bal = defaultdict(lambda: {"all": Counter(), "real": Counter(), "synthetic": Counter()})
for name, rec in truth.items():
    for q, val in rec["truth"].items():
        if val is None:
            continue
        subs = ([("C4 direction", val["direction"]), ("C4 third", val["third"]),
                 ("C4 both", val["direction"] + " / " + val["third"])] if q == "C4" else [(q, val)])
        for sub, key in subs:
            bal[sub]["all"][key] += 1
            bal[sub][rec["kind"]][key] += 1


def order_key(q):
    return (q[0], int(q[1]) if q[1].isdigit() else 9, q)


def cell(c):
    n = sum(c.values())
    return n, max(c.values()) / n, ", ".join(f"{k}: {v}" for k, v in sorted(c.items()))


rows = []
for q in sorted(bal, key=order_key):
    na, ba, ca = cell(bal[q]["all"])
    nr, br, cr = cell(bal[q]["real"])
    ns, bs, cs = cell(bal[q]["synthetic"])
    rows.append(f"| {q} | {na} | {ca} | **{ba:.2f}** | {nr} | {br:.2f} | {ns} | {bs:.2f} |")
balance_table = "\n".join(rows)

# ------------------------------------------------------------------ sessions table
sess = {}
imgs = defaultdict(dict)
for name, rec in sorted(truth.items()):
    sess[rec["session"]] = rec
    imgs[rec["session"]][rec["chart_type"]] = name
srows = []
for sid in sorted(sess):
    r = sess[sid]
    srows.append(f"| {sid} | {r['kind']} | {r['symbol']} | {r['date']} | {r['matched_session'] or '-'} | "
                 f"{imgs[sid]['A']} | {imgs[sid]['B']} | {imgs[sid]['C']} |")
sessions_table = "\n".join(srows)

# ------------------------------------------------------------------ soft flags
sf = Counter()
n_soft = Counter()
for rec in truth.values():
    for f in rec["soft_flags"]:
        sf[f] += 1
    n_soft[rec["chart_type"]] += int(bool(rec["soft_flags"]))
soft_table = "\n".join(f"| {k} | {v} |" for k, v in sorted(sf.items()))

# ------------------------------------------------------------------ real Chart C overlap
ev = {s: cl.load_evals_daily(s) for s in cl.SYMS}
pos = {}
gaps = set()
for name, rec in truth.items():
    if rec["kind"] == "real" and rec["chart_type"] == "C":
        d = dt.date.fromisoformat(rec["date"])
        i = int(np.searchsorted(np.array(list(ev[rec["symbol"]].index)), d))
        pos[rec["session"]] = (rec["symbol"], i)
        gaps.add((rec["symbol"], round(rec["metrics"]["C4"]["gap_pct"], 3)))
ov = [max(0, 60 - abs(ia - ib)) for (a, (sa, ia)), (b, (sb, ib)) in itertools.combinations(pos.items(), 2) if sa == sb]

# ------------------------------------------------------------------ render QA totals
tot = Counter()
for q in rqa.values():
    tot["c_chk"] += q["candles"][0]; tot["c_ok"] += q["candles"][1]; tot["c_wrong"] += q["candles"][2]
    tot["v_chk"] += q["volume"][0]; tot["v_ok"] += q["volume"][1]
    for _, (a, b) in q["lines"].items():
        tot["l_chk"] += a; tot["l_ok"] += b
    tot["bad_layout"] += int(bool(q["text_outside"] or q["text_overlaps"] or q["legend_over_axes"]))

ir, sp, gc, dsc = ver["independent_recompute"], ver["synthetic_properties"], ver["generator_calibration"], ver["daily_source_comparison"]
im, ovk, leak = ver["images"], ver["order_vs_kind"], ver["reader_file_leak_scan"]
n_real = sum(1 for s in sess.values() if s["kind"] == "real")
n_syn = len(sess) - n_real
n_spy = sum(1 for s in sess.values() if s["kind"] == "real" and s["symbol"] == "SPY")
real_dates = sorted(s["date"] for s in sess.values() if s["kind"] == "real")
worst_open = max(dsc[s][f"{c}_max_abs_diff_pct"] for s in dsc for c in ("open", "high", "low"))
worst_close = max(dsc[s]["close_max_abs_diff_pct"] for s in dsc)
vr_lo = min(dsc[s]["volume_ratio_frozen_over_minute_sum_min_mean_max"][0] for s in dsc)
vr_hi = max(dsc[s]["volume_ratio_frozen_over_minute_sum_min_mean_max"][2] for s in dsc)

REPORT = f"""# Build report: blind chart-reading test

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
| 16 real sessions dated before 2026-07-01 and 8 dated 2026-07-01 or later | **0 before, {n_real} on or after** (dates {real_dates[0]} to {real_dates[-1]}) | no minute bars before 2026-08-03 exist |
| B7 skipped for pre-cutoff real sessions | B7 is asked for all {len(sess)} sessions | every real session is post-cutoff |
| Daily bars aggregated from minute bars, 110 earlier sessions | Daily bars taken from the repo's frozen official daily file `trading/evals/bars.csv.gz` (SPY and QQQ, 2016 to 2026-09-25) for all 60 candles and both averages of the real charts, and as the raw material for the synthetic daily paths | at most 39 earlier minute sessions exist; 110 are needed |

How close the substitute is: on the 39 sessions per symbol that both sources cover, the frozen daily bars match daily bars
built from the minute bars to within {worst_open:.3f}% on open/high/low and {worst_close:.3f}% on close (the official close
includes the closing auction); their volume is {100*(vr_lo-1):.0f}% to {100*(vr_hi-1):.0f}% higher (consolidated volume).
Volume is drawn as a multiple of the median, so this cannot show in the pictures. The aggregation code itself (first open,
max high, min low, last close, sum volume) is in `chartlib.daily_from_minutes` and produced those comparison numbers.

What this does to the test (more in section 9):

1. **All {n_real} real sessions come from one 8-week window.** Same market regime for every real picture. The real
   Chart C pictures share most of their history: two same-symbol Chart C pictures overlap by {np.mean(ov):.0f} of 60 candles on average
   (min {min(ov)}, max {max(ov)}). Across the {len(pos)} real Chart C pictures there are only **{len(gaps)} distinct largest-gap events**.
   Their answers are strongly correlated, so treat real Chart C results as a handful of independent observations, not {len(pos)}.
2. Nothing dated before the 2026-07-01 cutoff, so no old-versus-new comparison is possible; on the other hand a reader whose
   knowledge ends before that date cannot have seen any of these days.
3. Re-running `python3 _build/build_chart_test.py` is deterministic (seed 7). If the cache is later filled with the full history
   it switches by itself to minute-built daily bars and to the 8 pre + 4 post-cutoff quota per symbol. **That branch has not been
   run on real data (none exists);** only the daily-aggregation function was checked, against the frozen file, as above.

## 1. What was built

- {len(imgs)} sessions x 3 charts = **{len(truth)} pictures** `c_0001.png` ... `c_{len(truth):04d}.png`, 1000 x 700 px, RGB PNG, white background,
  no metadata, all with the same file time. Names are a random permutation of all pictures (order carries no information; permutation
  test on the position of synthetic pictures: p = {ovk['permutation_p_two_sided']:.2f}).
- Sessions: **{n_real} real** ({n_spy} SPY, {n_real - n_spy} QQQ; 0 dated before 2026-07-01, {n_real} on or after) and **{n_syn} synthetic**
  (6 matched to SPY sessions, 6 to QQQ sessions). Chart A, B and C of a session are three separate pictures.
- `questions.md` (reader-facing questions with plain definitions and the answer format), `manifest_blind.json`
  (list of `{{image, chart_type, questions}}`, nothing else), `truth.json` (the key), this report.
- `_build/`: code (`chartlib.py`, `build_chart_test.py`, `verify_key.py`, `make_report.py`, `questions_text.py`, `stress_layout.py`),
  the exact data behind every picture (`session_data.json`), name map (`names.json`), pixel-check results (`render_qa.json`),
  verification results (`verification.json`).
- Random streams (numpy `default_rng`, seed 7): `[7,1]` picks the real sessions, `[7,2]` the templates of the synthetic ones, `[7,3]` the
  picture names, `[7,100+j]` and `[7,200+j]` the intraday and daily paths of synthetic session j.

## 2. The sample ({len(sess)} sessions)

Sampling: from the full-day sessions of each symbol (all {40} of them), a seeded random order, first 12 per symbol that pass the rules,
**no two sessions share a date** (so no SPY and QQQ picture of the same market day; my choice, to avoid near-duplicate days).
A session is only skipped if a rule of the key would be undefined by an exact tie (highest high reached in both halves, equal
highest volume in two blocks, a close exactly on a level, equal EMA, equal price at 12:30, two equal largest gaps). Sessions
skipped: {len(blog['skipped'])}. Pre-cutoff shortfall against the quota of 16: {blog['pre_short']}.
For synthetic sessions `symbol` and `date` in `truth.json` are those of the matched real session.

| Session | Kind | Symbol | Date | Matched / twin | Chart A | Chart B | Chart C |
|---|---|---|---|---|---|---|---|
{sessions_table}

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

Checks on the {sp['n_synth']} synthetic sessions used (all passed unless noted): 390 bars each; bars valid (high >= open/close >= low, all
prices > 0, on the cent grid); the volumes of every 10-minute block equal the real block's volumes (as sets); the sizes of the
one-minute moves per block equal the real ones (within cent rounding); RMS one-minute move equals the real day's (ratio between
{sp['rms_ratio_synth_over_real_min']:.4f} and {sp['rms_ratio_synth_over_real_max']:.4f}); daily volume sets equal.
"No structure" statistics, from {gc['replicates']} extra replicates (300 per template, other seeds): the sum of one-minute returns divided by its root-sum-of-squares
has mean {gc['z_mean']:+.3f} and sd {gc['z_sd']:.3f} (fair-coin theory: 0 and 1); lag-1 autocorrelation of one-minute returns
{gc['lag1_autocorr_mean']:+.4f} (real templates: {sp['lag1_autocorr_template_real_mean']:+.3f}, a small negative bounce effect that the synthetic ones do not have;
too small to see); share of up minutes {gc['share_up_minutes_mean']:.3f}. Under this model B7 (next 30 minutes)
is a fair coin: P(up) = {gc['P(B7=up)']:.3f}; B3 (EMA slope up) = {gc['P(B3=up)']:.3f}. Because volatility is front-loaded like a real day, A4 "first half"
is {gc['P(A4=first)']:.2f} and A6 "breakout yes" is {gc['P(A6=yes)']:.2f} under the model (not the textbook 0.5 and 0.67 of a flat-volatility walk).
(In the 12 sessions actually drawn, the sd of the per-session score was {sp['sum_over_rss_z_per_session_sd']:.2f}, lower than the 1.0 expected; with 12 sessions that is roughly a 1-in-70 draw. The
{gc['replicates']}-replicate calibration shows the generator itself is right, so I take it as chance, but it is noted here.)

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
`{{direction, third}}`), `metrics` (the raw numbers behind each answer, e.g. `chg_pct`, `range_pct`, `crosses`, gap sizes), `flags`
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
{soft_table}

{n_soft['A']} of 36 chart A, {n_soft['B']} of 36 chart B and {n_soft['C']} of 36 chart C pictures carry at least one soft flag. Suggested use: score once on all
items and once without flagged items (or per flag). Thresholds: A1 within 0.02 points of +-0.10; A2/B4 close within 0.01% of VWAP; A3 count of 1, 2, 4 or 5
(next to a class boundary); A4 halves' highs within 0.01%; A5 within 0.03 points of 0.25 or 0.50; A6 margin under 0.01%; A7 runner-up block within 5%;
B1 within 0.03 points of +-0.15; B2 ratio within 0.05 of 0.6; B3 EMA change under 0.005%; B5 ranges within 5%; C1/C2 within 0.2%; C3 within 0.5 points of +-3;
C4 runner-up gap within 15% of the largest, or the gap straddling a thirds line (candle 21 or 41).

## 6. Checks run

- **Independent recomputation.** A second implementation written differently (pure Python loops, string-based crossing count, raw cache files
  re-read without the lab loaders, the daily file read with the `csv` module) recomputed every answer for every picture:
  **{ir['answers_compared']} answers compared, {ir['mismatches']} mismatches; {ir['numeric_metrics_compared']} numeric metrics compared, {ir['numeric_mismatches']} mismatches.**
  (The first run showed one mismatch on C4: an off-by-one in the checker, not in the key; the case is the gap opening at candle 21, which the rule
  places in the middle third. Fixed in the checker and re-run.) Data behind the real pictures equals the raw files: minute bars
  {ver['source_data_equal_to_raw_files']['minute_real'][1]}/{ver['source_data_equal_to_raw_files']['minute_real'][0]}, daily bars {ver['source_data_equal_to_raw_files']['daily_real'][1]}/{ver['source_data_equal_to_raw_files']['daily_real'][0]} (counted per real picture: 24 sessions x 3).
- **Pixel checks on the rendered pictures** (all {len(rqa)}): {tot['c_ok']}/{tot['c_chk']} candle bodies have the right colour at the right place ({tot['c_wrong']} wrong colours),
  {tot['v_ok']}/{tot['v_chk']} volume bars, {tot['l_ok']}/{tot['l_chk']} sampled points on the indicator lines; text never leaves the canvas or overlaps,
  legend never sits on the plot: {tot['bad_layout']} pictures with layout problems. The same checks ran over all 80 real sessions x 3 charts
  (240 pictures) during development, which found and fixed clipped axis labels.
- **Picture-to-key check** (`verify_pixels.py`): answers read straight off the finished PNGs by pixel geometry, with no access to the data, compared with `truth.json`:
  A2 {pix['A2']['agree']}/{pix['A2']['compared']}, A4 {pix['A4']['agree']}/{pix['A4']['compared']}, A7 {pix['A7']['agree']}/{pix['A7']['compared']}, B4 {pix['B4']['agree']}/{pix['B4']['compared']},
  C1 {pix['C1']['agree']}/{pix['C1']['compared']}, C2 {pix['C2']['agree']}/{pix['C2']['compared']} agree; {sum(v['ambiguous'] for v in pix.values())} readings were too close to a line to resolve (within 4 px) and are not counted.
  On the first pass (resolution limit 2 px) one C1 item disagreed: a close 0.03% above the 50-day line, less than one pixel, where the line is drawn over and hides the top edge of the
  candle body. The independent recomputation confirms the key (close 713.91 vs average 713.68); I set the pixel reader's limit to 4 px (line thickness) and it is flagged `C1_close_within_0.2pct_of_sma50`.
- **Files.** {im['count']} pictures, sizes {im['sizes']}, modes {im['modes']}, PNG text chunks {im['png_text_chunks']}, distinct file times {im['distinct_mtimes']}, names sequential {im['names_sequential']},
  manifest and key match the files ({im['manifest_matches_files']}, {im['truth_matches_files']}).
- **Leak scan** of `questions.md` and `manifest_blind.json` for words like real, synthetic, noise, random, template, symbols, years: hits {leak['questions.md']} and {leak['manifest_blind.json']};
  manifest keys {leak['manifest_keys']}.
- **Pictures I looked at: 3**, all scratch renders made with the same drawing code during layout work (a real 1-minute chart, a synthetic twin
  of it, a real daily chart), only to check that they render. None of the final pictures was viewed; I answered no question. After those views I changed
  label placement, the volume axis ticks (added "1x") and the plot width; those changes were checked programmatically only.

## 7. Class balance and majority-class baselines

`n` = pictures with a truth. "Baseline" = accuracy of always answering the most common class. Read the overall baseline first;
real and synthetic are shown separately because they differ (the real ones come from one 8-week window).

| Question | n | Classes (all) | Baseline (all) | n real | Baseline real | n synth | Baseline synth |
|---|---|---|---|---|---|---|---|
{balance_table}

Things to notice: **A7** (volume peak) is the first block in about {100*bal['A7']['all'].most_common(1)[0][1]/36:.0f}% of pictures, so it barely discriminates;
**B5** has a {100*bal['B5']['all'].most_common(1)[0][1]/36:.0f}% baseline; **C4 direction** is `down` in {bal['C4 direction']['real']['down']} of 24 real pictures (only {len(gaps)} distinct gap events behind those {len(pos)} pictures)
but split in the synthetic ones; C1/C2 are mostly `yes` for the real charts (uptrend in this window) and more even for the synthetic ones. A model that
says "up" or "above" by habit will look decent on some real items for reasons unrelated to reading. For the confidence-weighted B7, the synthetic
pictures are a fair coin by construction (the {sum(1 for r in truth.values() if r['kind']=='synthetic' and r['chart_type']=='B')} synthetic B pictures: up {bal['B7']['synthetic']['up']}, down {bal['B7']['synthetic']['down']}), so any edge there is chance.
The score for C4 can be taken on direction, on third, or both (`C4 both` above).

## 8. Answer format the readers were given

One JSON object per picture: `{{"image": "c_XXXX.png", "A1": ..., ...}}` with `B7` as `{{"direction", "confidence"}}` and `C4` as `{{"direction", "third"}}`
(details and allowed tokens in `questions.md`). Clarity ratings (A8, B6, C5) are integers 0-10 with no truth; compare their averages between real
and synthetic pictures, ideally by matched pair (`matched_session`).

## 9. Issues, limits and judgement calls

1. **Data range** (section 0): no pre-cutoff sessions, daily candles from the frozen daily file, one 8-week regime.
2. **Real Chart C is nearly one observation per symbol-regime** ({len(pos)} pictures, {len(gaps)} distinct largest gaps, on average {np.mean(ov):.0f} of 60 candles shared). Do not read {len(pos)} independent tests out of it.
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
"""

(OUT / "build_report.md").write_text(REPORT)
print("wrote", OUT / "build_report.md", len(REPORT), "chars")
