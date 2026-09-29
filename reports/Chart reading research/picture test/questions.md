# Chart-reading questions

You will be shown chart pictures named `c_XXXX.png` (1000 x 700 pixels). The file `manifest_blind.json` lists, for
every picture, its chart type (A, B or C) and the ids of the questions to answer for that picture. Answer exactly the
questions listed for a picture, using only what is drawn in that picture.

## Ground rules

1. Use only the picture. Do not try to work out which market, instrument or date it shows; nothing else is needed.
2. Every picture stands alone. Nothing you saw in another picture applies to it.
3. Read the picture the way a person would: from the axes, gridlines and legend. Estimating by eye is expected;
   nothing has to be measured to the pixel.
4. Every question has a fixed list of allowed answers. Give exactly one of them. If you are unsure, give the answer
   you think is most likely (do not skip, do not write "unclear").
5. Give your answers in the format under "Answer format", one JSON object per picture.

## How to read the pictures

**What every picture shows**

- **Candles.** One candle per time slot. The thick *body* runs from the candle's open to its close; the thin *wick*
  runs from its low to its high. A **green** candle closed at or above its open; a **red** candle closed below its open.
  "The close of a candle" is the end of its body (top of a green body, bottom of a red body); "the open" is the other end.
- **Price axis** (right side of the top panel): percent change relative to the OPEN OF THE FIRST CANDLE in the
  picture. The dotted horizontal line is 0.00%, which is that first open. Every price level below is read on this axis.
- **Volume panel** (bottom): one bar per candle, drawn as a multiple of the MEDIAN volume bar of that picture. The
  dashed line is 1x (the median bar); a bar that reaches twice as high as the dashed line traded twice the median volume.
- **Time axis** (bottom): clock times HH:MM. The label under a gridline is the START time of the candle that sits just
  to the right of that gridline.

**Chart A: 1-minute candles.** 60 candles, 09:30 to 10:29 (the last candle is the one that starts at 10:29). The blue
line is the VWAP: the volume-weighted average price since 09:30 (a running average of the traded price in which
heavy-volume minutes count more). The VWAP "at a candle" is the height of the blue line at that candle's position.
Faint vertical lines are drawn every 5 minutes; labelled ones every 10 minutes.

**Chart B: 5-minute candles.** 30 candles, 09:30 to 11:59 (the last candle starts at 11:55 and ends at 12:00). The blue
line is the VWAP since 09:30, read as in chart A. The orange line is the EMA20: the 20-period exponential moving average
of the 5-minute closes (a smoothed line that follows the closes with a lag; recent closes weigh more). Faint vertical
lines every 15 minutes; labelled ones every 30 minutes.

**Chart C: daily candles.** 60 candles, one per trading day, oldest on the left, newest on the right. The numbers under
the axis count the candles, 1 (oldest) to 60 (newest). The orange line is the 20-day simple average of the daily closes
and the purple line the 50-day simple average of the daily closes; both are drawn across all 60 candles. The two dashed
vertical lines split the picture into thirds of 20 candles: candles 1-20, 21-40 and 41-60.

## Answer format

One JSON object per picture, with the picture's file name and one entry for each question listed for it. Allowed values
are given with each question below.

```
Chart A: {"image": "c_XXXX.png", "A1": ..., "A2": ..., "A3": ..., "A4": ..., "A5": ..., "A6": ..., "A7": ..., "A8": ...}
Chart B: {"image": "c_XXXX.png", "B1": ..., "B2": ..., "B3": ..., "B4": ..., "B5": ..., "B6": ...,
          "B7": {"direction": ..., "confidence": ...}}
Chart C: {"image": "c_XXXX.png", "C1": ..., "C2": ..., "C3": ...,
          "C4": {"direction": ..., "third": ...}, "C5": ...}
```

Answer tokens are written exactly as shown in the "Allowed answers" lines (lower case, ASCII hyphens).

---

## Chart A questions (1-minute candles, 09:30-10:29)

**A1 trend.** "Over this picture, has the price gone up, gone down, or stayed flat?"
Allowed answers: `up`, `down`, `flat`.
Rule: compare the close of the LAST candle with the open of the FIRST candle (the 0.00% line). `up` if the last close is
at or above +0.10% on the price axis; `down` if it is at or below -0.10%; otherwise `flat`.

**A2 end_vs_vwap.** "Is the last candle's close above or below the VWAP line?"
Allowed answers: `above`, `below`.
Rule: compare the close of the last candle with the blue line at the last candle.

**A3 vwap_crosses.** "How many times do the candle closes move from one side of the VWAP line to the other?"
Allowed answers: `0-1`, `2-4`, `5+`.
Rule: for each candle, note whether its CLOSE is above or below the blue line at that candle. Every time a candle's
close is on the opposite side of the line from the previous candle's close, that is one crossing. Only closes count:
a wick or body that touches or pokes through the line while the close stays on the same side is not a crossing.
Count the crossings and give the range they fall in (0 or 1 crossing = `0-1`; 2, 3 or 4 = `2-4`; 5 or more = `5+`).

**A4 high_half.** "Which half of the picture contains the candle with the highest high?"
Allowed answers: `first`, `second`.
Rule: find the highest point reached by any wick (the highest high). `first` if it is in the first half (candles
09:30-09:59, left of the 10:00 gridline); `second` if it is in the second half (10:00-10:29).

**A5 range.** "How large is the total range of the picture, from the lowest low to the highest high?"
Allowed answers: `<0.25%`, `0.25-0.50%`, `>0.50%`.
Rule: range = (top of the highest wick) minus (bottom of the lowest wick), read on the percent axis (which is already
relative to the first open). Less than 0.25 percentage points = `<0.25%`; from 0.25 to 0.50 = `0.25-0.50%`; more than
0.50 = `>0.50%`.

**A6 breakout.** "Did any candle from 09:45 onward close above the highest high of the first 15 candles (09:30-09:44)?"
Allowed answers: `yes`, `no`.
Rule: find the highest point reached by any wick among the first 15 candles (left of the 09:45 gridline; that is the
faint gridline halfway between the 09:40 and 09:50 labels). `yes` if the CLOSE of at least one candle from 09:45 to
10:29 is above that level. A wick that pokes above the level without a close above it does not count.

**A7 volume_peak.** "In which 10-minute block is the single tallest volume bar?"
Allowed answers: `09:30-09:39`, `09:40-09:49`, `09:50-09:59`, `10:00-10:09`, `10:10-10:19`, `10:20-10:29`.
Rule: find the tallest bar in the volume panel and give the 10-minute block (between the labelled gridlines) that
contains it.

**A8 clarity.** "How clear and tradeable does this picture look?"
Allowed answers: an integer from 0 to 10.
Rule: your overall impression. 0 = nothing readable or usable, a picture you would never act on; 10 = an unmistakably
clear picture that would be easy to trade. There is no correct answer; give your honest impression.

---

## Chart B questions (5-minute candles, 09:30-11:59)

**B1 trend.** "Over this picture, has the price gone up, gone down, or stayed flat?"
Allowed answers: `up`, `down`, `flat`.
Rule: compare the close of the LAST candle with the open of the FIRST candle (the 0.00% line). `up` if the last close is
at or above +0.15%; `down` if it is at or below -0.15%; otherwise `flat`.

**B2 daytype.** "Is this a trend picture or a range picture?"
Allowed answers: `trend`, `range`.
Rule: take the distance between the last close and the first open (net move, ignoring direction) and the full range of
the picture (highest high minus lowest low). `trend` if the net move is at least 60% of the full range; otherwise
`range`. By eye: does the net move cover at least 60% of the vertical extent of everything drawn?

**B3 ema20_slope.** "Is the EMA20 (orange line) higher or lower at the last candle than it was 5 candles earlier?"
Allowed answers: `up` (higher now), `down` (lower now).
Rule: compare the height of the orange line at the last candle (the 30th) with its height at the 25th candle.

**B4 last_vs_vwap.** "Is the last candle's close above or below the VWAP line?"
Allowed answers: `above`, `below`.
Rule: compare the close of the last candle with the blue line at the last candle.

**B5 contraction.** "Is the price range of the 11:00-11:59 candles smaller than the price range of the 09:30-10:29
candles?"
Allowed answers: `yes`, `no`.
Rule: the range of a period is its highest high minus its lowest low. The early period is the 12 candles left of the
10:30 gridline; the late period is the 12 candles right of the 11:00 gridline. `yes` if the late range is smaller than
the early range, `no` otherwise.

**B6 clarity.** "How clear and tradeable does this picture look?"
Allowed answers: an integer from 0 to 10.
Rule: your overall impression. 0 = nothing readable or usable, a picture you would never act on; 10 = an unmistakably
clear picture that would be easy to trade. There is no correct answer; give your honest impression.

**B7 next30.** "Looking only at this picture, will the price at 12:30 be higher or lower than the last close shown, and how
confident are you?"
Allowed answers: `direction`: `up` or `down` (you must choose one); `confidence`: an integer from 0 to 100.
Rule: the last close shown is the close of the 11:55 candle (the price at 12:00). The price at 12:30 is the closing
price of the 12:29 minute, thirty minutes later. `up` means the price at 12:30 is higher than the last close shown,
`down` that it is lower. Confidence is your own estimate, in percent, of how likely your chosen direction is to be right
(50 = a coin flip, 100 = certain).

---

## Chart C questions (daily candles, 60 trading days)

**C1 above_50.** "Is the last candle's close above the 50-day average (purple line)?"
Allowed answers: `yes`, `no`.
Rule: compare the close of the last candle with the purple line at the last candle.

**C2 sma20_above_sma50.** "At the right-hand end of the picture, is the 20-day average (orange line) above the 50-day
average (purple line)?"
Allowed answers: `yes`, `no`.
Rule: compare the height of the two lines at the last candle.

**C3 net60.** "Over the 60 candles, has the price gone down, stayed flat, or gone up?"
Allowed answers: `down`, `flat`, `up`.
Rule: compare the close of the LAST candle with the open of the FIRST candle (the 0.00% line). `down` if the last close
is below -3% on the price axis; `up` if it is above +3%; otherwise `flat` (from -3% to +3%).

**C4 largest_gap.** "Which is the largest gap between neighbouring candles: does it point up or down, and in which third
of the picture does it sit?"
Allowed answers: `direction`: `up` or `down`; `third`: `first third`, `middle third` or `last third`.
Rule: a gap is the vertical distance between the CLOSE of one candle and the OPEN of the next candle. It is `up` if the
next candle opens ABOVE the previous close and `down` if it opens BELOW it. Only gaps between two candles that are both
in the picture count. Find the single largest gap (by size, ignoring direction). Its position is the position of the
candle that opens with the gap (the right-hand candle of the pair): `first third` = candles 1-20, `middle third` =
candles 21-40, `last third` = candles 41-60, as marked by the two dashed vertical lines.

**C5 clarity.** "How clear and tradeable does this picture look?"
Allowed answers: an integer from 0 to 10.
Rule: your overall impression. 0 = nothing readable or usable, a picture you would never act on; 10 = an unmistakably
clear picture that would be easy to trade. There is no correct answer; give your honest impression.
