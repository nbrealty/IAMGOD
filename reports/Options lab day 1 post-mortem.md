# Options lab, day 1 post-mortem (Mon 28 Sept 2026)

*Paper account only. Both trades used the committed lab code (`git show HEAD:trading/lab/options_lab.py`, commit cc92d47). Data: Alpaca 1-minute SIP stock bars and option trade bars for the full session, pulled after 16:16 ET. Fills come from the Alpaca orders API (read-only). No orders were placed or changed. No code was edited.*

*This version has been through two skeptic reviews. Every number they could not confirm is either fixed, removed, or marked. The box below lists what changed.*

> **Corrections made after review**
> - The dollar split in the summary was double-counted. Fixed: stock move −$15, time decay plus volatility +$4, costs −$19 (model).
> - "Costs were the biggest piece" held on only one of three yardsticks. It is now "costs were material and maybe the largest item; the size is uncertain."
> - The "$4 given away" at the QQQ exit is now an estimate, not a fact.
> - Fees were missing. All figures are **before fees**.
> - The chance of hitting the 50% target was about 30%, not 16% (a target can be touched at any time, not only at the close).
> - The "TP 10%" what-if was optimistic: +$17, not +$25.
> - The two-year exit test partly proves itself by construction (see 4c). It is consistent with "no edge", not independent proof.
> - "Neither signal predicts direction" became "no evidence of an edge".
> - The hold-to-expiry what-if and the "would have lost $0" line were hindsight. Both are removed.

## Summary in plain English

- **Result:** −$30 in total, before fees. The QQQ put spread lost $23 and the SPY call spread lost $7. Both closed on the 15:35 time exit. Neither the profit target nor the stop came close.
- **The QQQ trade was right for 30 minutes, then wrong for 5 hours.** QQQ fell another 0.6% after entry, to 731.63 at 10:48. The spread was then up about **+$61**. QQQ then rallied to 740.38 by 12:27 and the spread went to about **−$54**. The exit rule wanted +$114. That needed QQQ to fall **1.07%**, which is roughly a one-standard-deviation move for the rest of the session.
- **The SPY credit spread never worked.** Its best moment was +$4. SPY bounced 0.6% within an hour. The trade was built to earn time decay, and almost none arrives within one session.
- **Where the −$30 came from (model estimate):**
  - stock moving against us: about **−$15**;
  - time decay plus implied-volatility change: about **+$4**;
  - trading costs (fills compared with the model's fair value): about **−$19**.
- **The cost number is uncertain.** Against Alpaca's indicative mid, costs net to about **+$6** (a gain). Against the actual trade prints, the QQQ entry alone cost about **−$11**. So costs were material, and maybe the largest item. We cannot say how large until we have real quotes.
- **The bigger finding is the two-year check.** I replayed both signals on the 556 days of minute data the project has. Neither shows evidence of an edge. With realistic costs, **every exit rule tried loses about $4–9 per spread on average.** Part of that result is built into the test method (see 4c), but nothing in it suggests the signals work.
- **Code defects found (still in the working tree today):**
  1. The "60-minute move" at 10:15 is really a 45-minute move (line 484; line 148 in the committed file).
  2. The exit limit on a close where we receive money can sit below the natural price (line 695; line 295 committed).
  3. The entry limit came from an indicative quote about one minute stale.
  4. `trades.json` loses the original trade size after a close.
- **One day proves nothing.** This post-mortem is about mechanics and design, not skill.

---

## 1. What happened (facts)

**Fills (Alpaca orders API):**

| Trade | Order | Limit | Fill (net) | Leg fills | Time (ET) |
|---|---|---|---|---|---|
| QQQ 736/734 put debit ×2 | open | 0.92 debit | **0.855** | buy 736P 4.465, sell 734P 3.61 | 10:16:14 |
| | close | 0.74 credit | **0.74** | sell 736P 3.77, buy 734P 3.03 | 15:35:08 |
| SPY 770/772 call credit ×1 | open | 0.49 credit | **0.49** | sell 770C 1.34, buy 772C 0.85 | 11:30:08 |
| | close | 0.58 debit | **0.56** | buy 770C 1.51, sell 772C 0.95 | 15:35:08 |

P&L: QQQ (0.74 − 0.855) × 200 = **−$23**. SPY (0.49 − 0.56) × 100 = **−$7**.

- The SPY spread closed at **0.56**, not 0.58 (0.58 was the limit).
- QQQ leg deltas at entry were **long −0.49 / short −0.42**. The 0.28/0.20 deltas were the SPY call legs.
- **Fees:** Alpaca paper charges none, and the lab code has no fee model. The options rulebook assumes $0.04 per contract per side. On that assumption, today's 12 contract-sides would add about **$0.50**. That rate is not verified against Alpaca's current fee page (https://alpaca.markets/support/regulatory-fees).

**The day:** QQQ opened 740.46, fell to 731.63 (10:48), rallied to 740.38 (12:27), closed 736.66. SPY opened 768.38, fell to 763.72 (10:55), rallied to 769.54 (12:27), closed 765.58. **A V-shaped day.**

**Operations:** at 10:15:27 the lab crashed with `TypeError: Lab.log() got multiple values for argument 'kind'`. It restarted and entered at 10:16:14. The delay did not cost money: QQQ bounced in that minute and the spread was about 0.03 cheaper at 10:16.

## 2. Value path, minute by minute

**Method:** there are no historical option quotes, only trade prints. For each print I backed out implied volatility (IV) with Black-Scholes (r = 4%, no dividend, time to 16:00 on 30 Sept). I smoothed IV with a rolling median of the last 10 prints and repriced each leg every minute from the SIP stock price.

**Limits of the method:** this "model value" is steadier than raw prints, which are out of sync between legs. But a 10-print median **lags in fast moves**, so the model can be off by more than the ±$0.03–0.05 per spread I first assumed. At the QQQ exit, for example, the model said 0.789 while the indicative mid said 0.77 and the prints said about 0.745.

**QQQ put debit (2 spreads, entry 0.855)**

| Time | QQQ | Spread (model) | Spread (last prints) | P&L model | Spread delta |
|---|---|---|---|---|---|
| 10:16 entry | 736.41 | 0.832 | 0.77 | −$5 | −0.068 |
| 10:31 | 736.24 | 0.795 | 0.83 | −$12 | −0.068 |
| 10:47 **(best)** | 732.00 | 1.160 | ~1.1 | **+$61** | −0.070 |
| 11:31 | 734.53 | 0.907 | 0.76 | +$10 | −0.069 |
| 12:27 **(worst)** | ~740 | ~0.58 | ~0.43 | **−$54** | −0.062 |
| 13:31 | 738.31 | 0.680 | 0.69 | −$35 | −0.062 |
| 14:31 | 737.64 | 0.753 | 0.81 | −$20 | −0.068 |
| 15:34 exit | 737.13 | 0.789 | 0.79 | −$13 (fill gave −$23) | −0.069 |

Best: **+$61 at 10:47** (model; the noisier print path shows +$87 at 10:54). Worst: **−$54 at 12:27** (print path −$85 at 12:41). The stop at 50% of max loss (−$85.50, spread at 0.43) did not trigger on the lab's quotes.

**SPY call credit (1 spread, credit 0.49; a higher spread value is worse for us)**

| Time | SPY | Spread (model) | Spread (last prints) | P&L model |
|---|---|---|---|---|
| 11:30 entry | 765.06 | 0.504 | 0.50 | −$1 |
| 11:43 **(best)** | 764.69 | ~0.45 | ~0.45 | **+$4** |
| 12:30 | 768.25 | 0.787 | 0.78 | −$30 |
| 13:11 **(worst)** | ~768.5 | ~0.86 | ~0.94 | **−$37** |
| 14:00 | 767.15 | 0.659 | 0.59 | −$17 |
| 15:00 | 766.56 | 0.598 | 0.60 | −$11 |
| 15:34 exit | 765.87 | 0.528 | 0.53 | −$4 (fill gave −$7) |

The take-profit (spread ≤ 0.245) and the backstop (SPY above 770, or spread about 1.70) were never close.

## 3. Where each dollar came from

Method: stock move, time decay and IV change are summed minute by minute with Black-Scholes. "Costs" are the fill compared with the model's fair value.

| Piece | QQQ put debit (×2) | SPY call credit (×1) | Both |
|---|---|---|---|
| Stock move (delta + gamma) | −$8.4 | −$6.9 | **−$15.3** |
| Time decay (theta) | −$0.4 | +$1.7 | +$1.3 |
| IV change (vega) | +$0.1 | +$2.8 | +$2.9 |
| **Market total (model)** | **−$8.7** | **−$2.4** | **−$11.1** |
| Entry cost vs model fair | −$4.5 (paid 0.855 vs 0.832) | −$1.4 (0.49 vs 0.504) | −$5.9 |
| Exit cost vs model fair | −$9.8 (got 0.74 vs 0.789) | −$3.2 (paid 0.56 vs 0.528) | −$13.0 |
| **Actual P&L (before fees)** | **−$23.0** | **−$7.0** | **−$30.0** |

**The same costs on other yardsticks:**

| Yardstick | QQQ entry | QQQ exit | SPY entry | SPY exit | Total |
|---|---|---|---|---|---|
| Model fair value (above) | −$4.5 | −$9.8 | −$1.4 | −$3.2 | **−$18.9** |
| Alpaca indicative mid | +$13 (0.855 vs 0.92) | −$6 (0.74 vs 0.77) | $0 | −$1 (0.56 vs 0.55) | **+$6** |
| Trade prints that minute | −$11 (0.855 vs ~0.80) | about −$1 (vs ~0.745) | $0 | about −$1 (vs ~0.553) | **about −$13** |

**How to read this:**
- **The cost figure depends on the yardstick.** It ranges from a $6 gain to a $19 loss. The indicative mid is not a real quote, and the model lags fast moves. So "costs were material" is fair. "Costs were the biggest piece" is possible but not proven.
- **Theta was almost zero for the QQQ spread.** Both strikes are near the money, so each leg loses about $1.07 a day and they cancel.
- **The SPY credit spread earned about +$1.70 of decay in four hours.** That is less than one round trip of costs on any yardstick except the indicative mid.

## 4. What went wrong, point by point

### 4a. Signal quality

| Check | QQQ 10:15 "momentum down" | SPY 11:30 "below opening range and VWAP" |
|---|---|---|
| Value as the lab computed it | −0.495% (IEX; taken at 10:16 including a partial bar) | −0.321% (60-minute move), below OR low 767.0 and VWAP 766.39 |
| Did the move continue? | Yes for 30 min: −0.51% at +30 min, low 731.63 at 10:48 | No: flat 15 min, then **+0.42% by +60 min** |
| Where it ended (15:34) | +0.10% (against us) | +0.10% (against us) |
| **Two-year base rate** (556 days of SIP minute bars, Jul 2024 – Sep 2026, same rule) | 107 signal days: QQQ lower at 15:34 on **48%**; average move after entry **+0.003%** | 121 signal days: SPY lower at 15:34 on **51%**; average **+0.001%**; rallied ≥0.40% after entry on 28% |

**What this means:**
- There is **no evidence of an edge.** With 107 days, 48% has a margin of about ±5 points, so a small edge (say 55%) is not ruled out. It is just not shown.
- The QQQ rule does pick **more volatile** days: on 25% of signal days QQQ later fell ≥1.07%, against 16% on all days. That extra movement goes both ways.
- This matches the earlier minute backtest (`reports/Minute trading backtest results.md`): the ORB and VWAP-trend rules were about zero before costs.

**Code defect:** `mom60 = spot / close.iloc[-61] - 1 if len(close) > 61 else spot / close.iloc[0] - 1`. At 10:15 there are only about 45 bars, so the "60-minute move" is really the **move since the first minute's close**. The journal label is wrong. (Working tree line 484; committed file line 148.)

**Data note:** signals use the IEX feed (a small share of volume). Today SIP and IEX were close (OR low 737.22 vs 737.31), so it did not matter today.

### 4b. How much of a correct move a 2-day, $2-wide spread can capture

- The QQQ spread's delta at entry was **−0.068 per share**: about 7 cents of spread value per $1 of QQQ. QQQ's correct 4.4-point drop added only about +0.33 per spread (+$61 on 2). A short of 100 QQQ shares would have made about $440 on the same move.
- **Why so small:** with IV at 20% and 2.25 days left, QQQ's one-standard-deviation move to expiry is about $11.60. A $2 width is 0.17 of that, so both legs have nearly the same delta and cancel.

| Structure (model, same QQQ move) | Delta at entry | Gain at the 10:47 best | At 15:34 |
|---|---|---|---|
| **Actual: 2-DTE 736/734 ($2)** | −0.068 | **+39%** | −5% |
| 1-DTE 736/734 ($2) | −0.095 | +62% | −5% |
| 2-DTE 736/731 ($5) | −0.160 | +41% | −6% |
| 4-DTE 736/731 ($5) | −0.118 | +30% | −1% |
| Single 2-DTE 736 put | −0.476 | +57% | −10% |

**Structure changes how big the swings are. It does not create an edge.**

### 4c. Exit design

**Was +50% of max gain reachable?** Max gain was 2 − 0.855 = $1.145 per spread, so the target was a spread value of 1.4275.

| Target (share of max gain) | QQQ spread value | QQQ move needed (any time) | Past signal days that got there |
|---|---|---|---|
| 10% | 0.970 | −0.15% | 82% |
| 20% | 1.084 | −0.37% | 61% |
| 30% | 1.198 | −0.59% | 50% |
| **50% (lab rule)** | **1.4275** | **−1.07%** | **24%** |

For SPY, the 50% target (0.245) needed about −0.43% by 13:00. That happened on 26% of past signal days.

**Rough check:** at IV 20%, QQQ's expected move for the rest of the session was about 1.1%. So the target needed about a one-standard-deviation move our way. The chance of *touching* that level at some point is roughly **30%** (about twice the 16% chance of *ending* there). Past signal days gave 24%. Either way, it was a long shot.

**Other exits on today's path** (model value, 0.03 per spread exit cost, limit assumed to fill at the target):

| Exit rule | QQQ exit, P&L | SPY exit, P&L |
|---|---|---|
| Actual (TP 50%, stop, 15:35) | 15:34, −$19 model (**−$23 real**) | 15:34, **−$7** |
| TP at 10% of max gain | 10:43, **+$17** | never hit, −$7 |
| TP at 20% | 10:46, **+$40** | never hit, −$7 |
| TP at 30% | never hit, −$19 | never hit, −$7 |
| Trailing (arm at +15%, exit after giving back half) | 11:04, about +$20 | never armed, −$7 |
| Exit when price closes back above VWAP | 11:36, −$11 | 12:16, −$14 |
| Fixed 60-minute hold | 11:16, +$18 | 12:30, −$33 |

These run on the smoothed model path. A live system would see a noisier path and could exit at different times.

**The same exits over two years.** Model test: constant IV (20% QQQ, 13.5% SPY), 2-day expiry, 0.03 cost per spread each side ($6 round trip), the lab's stops included. P&L per spread, before fees.

| Exit rule | QQQ put debit, 107 days: mean (t) / win% | SPY call credit, 121 days: mean (t) / win% |
|---|---|---|
| TP 10% | −$7.2 (−2.9) / 61% | −$7.4 (−3.4) / 60% |
| TP 20% | −$5.2 (−1.7) / 51% | −$8.2 (−3.3) / 50% |
| TP 30% | −$5.2 (−1.6) / 46% | −$9.1 (−3.6) / 45% |
| TP 50% (actual) | −$4.2 (−1.1) / 41% | −$7.9 (−3.0) / 44% |
| Trailing | −$5.6 (−1.7) / 53% | −$8.8 (−3.7) / 52% |
| Exit on VWAP reclaim | −$4.8 (−1.8) / 24% | −$6.9 (−4.9) / 27% |
| Hold to 15:35 | −$4.4 (−1.1) / 43% | −$8.4 (−3.3) / 41% |
| *Same trade every day, no signal* | *−$5.7 to −$6.4* | *−$7.0 to −$8.6* |

**How much to trust this:**
- If prices move like a random walk, **no exit rule can change the average result before costs.** That is a standard maths result. The test uses real stock paths but constant IV, so "every exit loses about the $6 cost" is close to what the method must produce if the signal days behave randomly.
- So this is **consistent with no edge**. It is not independent proof from the market.
- It also leaves out IV moving with the stock (which matters for put spreads) and the day/night pattern in option prices (section 4f).

**Verdict:**
- The signal adds nothing visible over trading every day.
- A tight profit target raises the win rate, not the average. TP 10% won 61% of the time and still averaged −$7.2.
- Today's +$40 "TP 20%" result is one lucky draw.

### 4d. Strike choice

- **QQQ debit spread:** a long leg at about 0.50 delta and a short leg $2 away at 0.42 delta are almost the same option. Fine for learning how orders work, poor for an intraday view: 7 cents per $1 of QQQ, and the target needs a 1% move.
- **SPY credit spread:** a short leg at 0.28 and long at 0.20 is normal for credit spreads held for days. Intraday it is a small short-delta bet (−0.08) that earns about $2 of decay.

### 4e. Fills: were they realistic?

**QQQ entry:**
- The prints in the 10:16 bar imply a spread of about **0.80** (736P vwap 4.28, 734P vwap 3.48). The fill of **0.855** was about 0.05 worse ($11 on 2). That bar includes prints after our order, so this is approximate.
- The long leg filled at 4.465, above every print that minute (high 4.43). The short leg filled at 3.61, also above every print (high 3.56).
- The limit of 0.92 matched the **10:15** prints (4.55 − 3.64 = 0.91). So the indicative chain was about one minute behind a fast bounce.
- Paper then filled us 0.065 "better" than our limit. **That is a warning about the quote, not luck.** Alpaca's docs say paper fills against the "current market price (NBBO)" and do not model "slippage due to latency", "order queue position" or "market impact" ([Alpaca paper trading](https://docs.alpaca.markets/docs/paper-trading)). The free feed's quotes "are not actual OPRA quotes" ([Alpaca option data](https://docs.alpaca.markets/docs/historical-option-data)).

**QQQ exit:**
- `close_limit` set the limit at mid − 0.03 = **0.74**, below the quoted natural price of 0.76 (long bid − short ask).
- **Did that cost $4? Not proven.** Paper matches against the current NBBO. If the natural price really was 0.76 when the order arrived, a 0.74 sell limit should have filled at 0.76. It filled at exactly 0.74. So the market was probably at or below 0.74 by then, and a 0.76 limit might not have filled at 15:35. **Treat "$4 given away" as an upper estimate.** The 15:35 prints imply about 0.745, which supports this.
- **Code defect, still worth fixing:** for a close where we receive money, the first step should be `max(mid − step, natural)`, never below natural. (Working tree line 695; committed line 295. At the hard close the code crosses on purpose, which is fine.)

**SPY:** entry 0.49 matched the prints (1.35 − 0.85). The exit at 0.56 matched the 15:35 print vwaps (1.493 − 0.94 = 0.553), 0.01 over the indicative mid.

**Bookkeeping defect:** after the close, `trades.json` shows `qty: 0` and `max_loss: 0`, because the close handler counts them down. The original size (2 and 1) survives only in the journal. Keep it in the trade record.

### 4f. The credit spread relies on time decay that does not build up intraday

- The spread was sold for decay (about +$13 a day per contract by the model), held 4 hours and closed before 16:00. It earned about **+$1.70 of theta**.
- The research points the same way. Delta-hedged S&P 500 index options average about −0.7% a day for the holder. That splits into **−1% close-to-open** and **+0.3% open-to-close**. In plain words: option *sellers* earn their money **overnight**, and option *buyers* do slightly better during the day. The abstract says equity options show the same pattern (Muravyev & Ni, *J. Financial Economics* 136(1), 2020, 219–238: [RePEc](https://econpapers.repec.org/RePEc:eee:jfinec:v:136:y:2020:i:1:p:219-238), [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2820264)). These returns are before costs and may have shrunk since publication.
- A premium-selling trade that must be flat by the close sits on the wrong side of that pattern by design. **Not yet checked on SPY/QQQ weeklies in 2024–2026.** That is agenda item 3 in `Where AI can beat human traders.md`.

## 5. Rule changes worth testing (decidable at the time, but not yet tested)

**Hindsight warning:** these ideas came from looking at two losing trades. Any threshold below must be set in advance and tested on past data before use.

| Rule (checkable at the time) | Status | Why |
|---|---|---|
| **Exit limit never below natural** on a close where we receive money (never above natural when we pay) | Safe to adopt now | Code defect, 4e |
| **Fix `mom60`** (true 60-minute window, or rename it; no signal before 10:30) | Safe to adopt now | Code defect, 4a |
| **Keep original size** in `trades.json` | Safe to adopt now | Bookkeeping defect, 4e |
| **Log a no-signal control trade** every day | Safe to adopt now | The two-year test shows signal ≈ control |
| **Shadow-log every exit variant** (TP 10/20/30/50, trailing, VWAP, fixed holds) without trading them | Safe to adopt now | Judge on 100+ days, not one |
| **No intraday premium selling** while the lab must be flat by 16:00 | Strong reason; confirm with agenda item 3 | Theta arrives mostly overnight (4f) |
| **Reachability gate:** skip if the move needed for the target is more than *k* × the remaining-session expected move (IV × √time) | **Untested.** Today's ratios were 0.97 (QQQ) and about 0.72 (SPY). I first proposed k = 0.5 after seeing both; choose *k* in advance and backtest it | Avoids long-shot targets |
| **Fresh-quote check:** hold the order if the quote is older than *x* seconds or disagrees with recent prints by more than *y* | **Untested.** 30 seconds and $0.05 are guesses | Stale indicative quote, 4e |

## 6. Where code helps here, and where it does not

The fair comparison is with **retail option traders**. Professional market makers already do all of the "helps" list, and much faster.

**Code helps (all used in this post-mortem):**
- Repricing every leg every minute and logging fair value next to every fill. That is how the cost question was found.
- Running a base-rate check in under a minute before a trade. Few people do this.
- Doing the "is the target reachable?" maths before entry.
- Shadow-testing many exit rules at once, and **not trading** when the maths shows no edge.

**Code does not help with:**
- **Speed.** The lab checks every 30 seconds; Claude runs in scheduled sessions. HFT firms react in microseconds.
- **Real prices.** The feed is indicative, not OPRA. Paper fills are not market fills, in either direction.
- **A zero-edge signal.** No exit, strike or expiry tweak made either signal profitable in the two-year test.
- **Edge decay.** Published edges tend to shrink.

## 7. What to research next

Full detail, ranking and success/kill criteria are in `reports/Where AI can beat human traders.md`. In short:

1. **Measure real costs.** Buy or borrow one month of real OPRA quotes (Databento free credit, or ThetaData $80) and compare them with the indicative quotes. Until then, we cannot say how big today's costs were.
2. **Fix the defects** (`mom60`, exit floor, stale quote, trade size) before reading anything into more lab days.
3. **Test the day/night pattern** on SPY options with the bar data we have (from Jan 2024).
4. **Decide whether the 0DTE lab should run at all.** It switches to same-day expiry from 29 Sept with the same no-edge signals. Treat each day as a mechanics and cost test, or pause it until items 1–2 are done.

*Sources checked: [Alpaca paper trading](https://docs.alpaca.markets/docs/paper-trading); [Alpaca historical option data](https://docs.alpaca.markets/docs/historical-option-data); [Muravyev & Ni 2020](https://econpapers.repec.org/RePEc:eee:jfinec:v:136:y:2020:i:1:p:219-238). Fee rate not verified. Analysis scripts are in the session scratchpad, not the repo.*
