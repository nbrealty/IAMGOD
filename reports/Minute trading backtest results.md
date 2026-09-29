# Minute trading backtest results

*Scalp lab run, 28 Sep 2026. SPY and QQQ, 1-minute bars, 3 Sep 2024 to 25 Sep 2026. Paper research only: no order was placed. The companion report, `Minute trading research.md`, explains each setup and the published evidence.*

---

## 1. The short answer

- **No setup made money after costs in the test half (the most recent 12 months).** Not one passed our pre-set bar.
- **Most setups were close to zero before costs.** Costs then pushed them below zero.
- **Every setup lost money through the options proxy.** Same-day options lost about 4% to 38% of the premium per trade on average at realistic option costs (up to 44% at pessimistic costs). Time decay and the spread were the main reasons.
- **The famous 5-minute opening range breakout (ORB5) partly replicated.** It was positive in "R" terms in the first year. It faded to about zero in the second year. With the paper's 4x leverage, costs turned it into a loss.
- **No setup is worth a paper test *as an edge*.** A small paper test is still useful for two things: learning the mechanics, and measuring real fill costs. Section 8 gives three setups and strict caps for that.

1 bp (basis point) = 0.01%. On a $1,000 trade, 1 bp = **$0.10**. So "-3 bps" means you lose about 30 cents per $1,000 trade.

---

## 2. Method

| Item | What we did |
|---|---|
| Data | Alpaca SIP 1-minute bars for SPY and QQQ. Regular hours only, using Alpaca's trading calendar (so half days are correct). Prices adjusted for splits and dividends. 513 full sessions. Half days were skipped. |
| Period | 3 Sep 2024 to 25 Sep 2026. All of it comes **after** every paper was published, so all of it is a fair test of the papers. |
| Split | **In-sample (IS)** = 3 Sep 2024 to 16 Sep 2025 (257 sessions). **Out-of-sample (OOS)** = 17 Sep 2025 to 25 Sep 2026 (256 sessions). The OOS half is the one that counts. |
| Rules | Fixed in advance, from the research spec. **No number was tuned.** Setups whose paper names one symbol were also run on the other symbol as a "check". |
| Fills | A decision is made at a bar's close. The fill is at the **next bar's open**. Stops and targets are checked inside each bar. If the stop and the target are both inside one bar, we assume the **stop** hit first. Everything is flat at the **15:55** bar open. One position per setup per symbol. |
| Size | Every trade is **$1,000** of stock. That lets setups be compared fairly. The papers' own sizing is reported separately. |
| Costs per side | **gross** 0. **quoted** 0.25 bps (half the measured spread plus the SEC fee). **low** 0.5 bps. **realistic** 1.5 bps. **pessimistic** 4 bps. A round trip pays twice. |
| Options proxy | A same-day at-the-money call (long signal) or put (short signal). Priced with a simple model that includes time decay. Cost per side = the larger of $0.01 and 2% of premium (realistic), or $0.02 and 5% (pessimistic). A rough guide only. |
| Baselines | **random**: the same number of trades per day and the same holding times, at random minutes, with a coin-flip side. **coin**: the setup's own entry times, with a coin-flip direction. |
| Statistics | 95% ranges and p-values come from a bootstrap over **days** (2,000 resamples). Trades on the same day are not independent, so days are the unit. |
| Pass bar (set before the run) | OOS, at realistic cost: the 95% range must be above 0, **and** p vs random < 0.05 / 28 = **0.0018**. We divide by 28 because we ran 14 setups x 2 symbols. Testing many things makes some look good by luck. |

**Which cost is "realistic"?** Our own quote check (see the research report) found SPY and QQQ spreads of about 2 cents, or 0.26 bps. That makes **0.5 bps per side** a fair cost for a small market order in calm markets. The lab's "realistic" level is 1.5 bps, which is more cautious. We show both. **The verdict is the same at either level, and even at zero cost.**

---

## 3. Out-of-sample results (the test half, last 12 months)

Sorted by the setups the papers named first, then the retail setups, then the "check" runs on the other symbol.

- **Win** and **p** are at the 1.5 bps cost. **$ per trade** = dollars per $1,000 trade at 1.5 bps.
- **p vs random** below 0.0018 would pass. Below 0.05 is "maybe interesting", not proof.

| Setup | Sym | Trades | Win | Gross bps | At 0.5 bps/side | At 1.5 bps/side [95% range] | $ per trade | p vs random | p vs coin |
|---|---|---|---|---|---|---|---|---|---|
| ORB5_QQQ | QQQ | 255 | 27% | -0.23 | -1.23 | -3.23 [-8.80, 2.90] | -0.32 | 0.50 | 0.73 |
| NOISE_MOM_SPY | SPY | 253 | 34% | -1.53 | -2.53 | -4.53 [-8.60, -0.02] | -0.45 | 0.52 | 0.98 |
| VWAP_TREND_QQQ | QQQ | 4,013 | 14% | +0.26 | -0.74 | -2.74 [-3.37, -2.00] | -0.27 | 0.19 | 0.08 |
| LAST30_MOM_SPY | SPY | 256 | 39% | +0.96 | -0.04 | -2.04 [-3.68, -0.38] | -0.20 | 0.13 | 0.15 |
| LAST30_MOM_SPY_CLOSE (16:00 exit) | SPY | 256 | 38% | +0.05 | -0.95 | -2.95 [-4.96, -0.89] | -0.30 | 0.12 | 0.84 |
| LAST30_ROD_SPY (variant B) | SPY | 256 | 36% | -0.36 | -1.36 | -3.36 [-5.13, -1.62] | -0.34 | 0.28 | 0.59 |
| LAST30_ETA_SPY (variant C) | SPY | 144 | 39% | +1.18 | +0.18 | -1.82 [-4.14, 0.46] | -0.18 | 0.36 | 0.11 |
| ORB30_CLASSIC | SPY | 254 | 51% | -0.10 | -1.10 | -3.10 [-7.58, 1.60] | -0.31 | 0.49 | 0.70 |
| ORB30_CLASSIC | QQQ | 253 | 51% | -1.22 | -2.22 | -4.22 [-10.78, 2.58] | -0.42 | 0.76 | 0.28 |
| ORB15_CLASSIC | SPY | 255 | 54% | +0.24 | -0.76 | -2.76 [-6.59, 1.22] | -0.28 | 0.55 | 0.46 |
| ORB15_CLASSIC | QQQ | 256 | 51% | -0.21 | -1.21 | -3.21 [-9.50, 3.01] | -0.32 | 0.16 | 0.16 |
| EMA9_21_PULLBACK_5M | SPY | 637 | 41% | +2.06 | +1.06 | -0.94 [-2.89, 1.04] | -0.09 | 0.022 | 0.14 |
| EMA9_21_PULLBACK_5M | QQQ | 616 | 38% | +2.75 | +1.75 | -0.25 [-3.01, 2.55] | -0.03 | 0.40 | 0.21 |
| PDH_PDL_BREAK_5M | SPY | 138 | 38% | +1.48 | +0.48 | -1.52 [-5.73, 2.63] | -0.15 | 0.68 | 0.33 |
| PDH_PDL_BREAK_5M | QQQ | 126 | 34% | -1.51 | -2.51 | -4.51 [-10.71, 1.64] | -0.45 | 0.73 | 0.57 |
| VWAP_2SD_FADE_1M | SPY | 625 | 32% | +0.16 | -0.84 | -2.84 [-3.90, -1.75] | -0.28 | 0.21 | 0.16 |
| VWAP_2SD_FADE_1M | QQQ | 563 | 35% | -0.22 | -1.22 | -3.22 [-4.67, -1.73] | -0.32 | 0.53 | 0.92 |
| GAP_FADE_SPY | SPY | 74 | 49% | +6.94 | +5.94 | +3.94 [-8.72, 16.74] | +0.39 | 0.15 | 0.52 |
| GAP_FADE_SPY | QQQ | 131 | 47% | -1.71 | -2.71 | -4.71 [-16.45, 7.33] | -0.47 | 0.62 | 0.44 |
| GAP_GO_SPY (opposite of the fade) | SPY | 74 | 45% | -6.94 | -7.94 | -9.94 [-23.19, 2.36] | -0.99 | 0.57 | 0.68 |
| GAP_GO_SPY | QQQ | 131 | 50% | +1.71 | +0.71 | -1.29 [-13.85, 10.90] | -0.13 | 0.62 | 0.55 |
| *check:* ORB5 | SPY | 254 | 22% | -0.39 | -1.39 | -3.39 [-7.17, 0.40] | -0.34 | 0.49 | 0.72 |
| *check:* NOISE_MOM | QQQ | 222 | 37% | +3.01 | +2.01 | +0.01 [-6.75, 6.66] | +0.00 | 0.33 | 0.26 |
| *check:* VWAP_TREND | SPY | 4,142 | 12% | +0.08 | -0.92 | -2.92 [-3.37, -2.42] | -0.29 | 0.09 | 0.39 |
| *check:* LAST30_MOM | QQQ | 256 | 46% | +1.72 | +0.72 | -1.28 [-3.64, 1.14] | -0.13 | 0.008 | 0.50 |
| *check:* LAST30_MOM_CLOSE | QQQ | 256 | 45% | +1.73 | +0.73 | -1.27 [-4.18, 1.56] | -0.13 | 0.97 | 0.70 |
| *check:* LAST30_ROD | QQQ | 256 | 44% | +0.62 | -0.38 | -2.38 [-4.88, 0.08] | -0.24 | 0.39 | 0.43 |
| *check:* LAST30_ETA | QQQ | 133 | 49% | +2.72 | +1.72 | -0.28 [-3.40, 2.91] | -0.03 | 0.13 | 0.12 |

**How to read one row.** ORB5_QQQ made 255 trades in the test half. Before costs it averaged -0.23 bps per trade, which is about zero. At 1.5 bps per side it lost 3.23 bps per trade, or 32 cents per $1,000 trade. The 95% range runs from -8.80 to +2.90, so we cannot even be sure of the sign.

**Did any setup beat its random baseline?** Not at the pass bar (0.0018). Two came in under 0.05:
- **EMA9_21_PULLBACK_5M on SPY, p = 0.022.** It lost money in the first half, so this looks like luck.
- **LAST30_MOM on QQQ (a check run), p = 0.008.** It still lost money after costs, and it did no better than the coin-flip baseline (p = 0.50).

With 28 tests, about 1.4 results under 0.05 are expected from luck alone. Two is what luck looks like.

**The costs matter more than the signal.** A 1 bp round trip (0.5 bps per side) is about 80% of a typical 1-minute SPY move. VWAP_TREND trades about 16 times a day. It is almost exactly zero before costs and loses steadily after them.

---

## 4. All results at other cost levels (whole two years)

Average bps per trade over all 513 sessions. Each column subtracts a bigger cost from the same trades.

| Setup | Sym | Gross | 0.25 bps | 0.5 bps | 1.5 bps | 4 bps (pessimistic) |
|---|---|---|---|---|---|---|
| ORB5_QQQ | QQQ | +1.42 | +0.92 | +0.42 | -1.58 | -6.58 |
| NOISE_MOM_SPY | SPY | +0.52 | +0.02 | -0.48 | -2.48 | -7.48 |
| VWAP_TREND_QQQ | QQQ | +0.18 | -0.32 | -0.82 | -2.82 | -7.82 |
| LAST30_MOM_SPY | SPY | +0.52 | +0.02 | -0.48 | -2.48 | -7.48 |
| LAST30_MOM_SPY_CLOSE | SPY | +0.36 | -0.14 | -0.64 | -2.64 | -7.64 |
| LAST30_ROD_SPY | SPY | -0.83 | -1.33 | -1.83 | -3.83 | -8.83 |
| LAST30_ETA_SPY | SPY | +0.41 | -0.09 | -0.59 | -2.59 | -7.59 |
| ORB30_CLASSIC | SPY / QQQ | +0.32 / +2.02 | -0.18 / +1.52 | -0.68 / +1.02 | -2.68 / -0.98 | -7.68 / -5.98 |
| ORB15_CLASSIC | SPY / QQQ | +1.19 / +2.42 | +0.69 / +1.92 | +0.19 / +1.42 | -1.81 / -0.58 | -6.81 / -5.58 |
| EMA9_21_PULLBACK_5M | SPY / QQQ | +0.06 / +0.06 | -0.44 / -0.44 | -0.94 / -0.94 | -2.94 / -2.94 | -7.94 / -7.94 |
| PDH_PDL_BREAK_5M | SPY / QQQ | +1.59 / +2.18 | +1.09 / +1.68 | +0.59 / +1.18 | -1.41 / -0.82 | -6.41 / -5.82 |
| VWAP_2SD_FADE_1M | SPY / QQQ | -0.60 / -0.31 | -1.10 / -0.81 | -1.60 / -1.31 | -3.60 / -3.31 | -8.60 / -8.31 |
| GAP_FADE_SPY | SPY / QQQ | +4.96 / +0.99 | +4.46 / +0.49 | +3.96 / -0.01 | +1.96 / -2.01 | -3.04 / -7.01 |
| GAP_GO_SPY | SPY / QQQ | -4.96 / -0.99 | -5.46 / -1.49 | -5.96 / -1.99 | -7.96 / -3.99 | -12.96 / -8.99 |

Some rows are slightly positive at 0.25 to 0.5 bps over the whole two years. None of them has a 95% range above zero. Most of them did better in the first half than in the second (section 6).

### The papers' own sizing

The ORB5 and NOISE papers used leverage. We re-scored the same trades with their sizing. The numbers are the sum of daily returns on the account, not compounded.

| Setup | Sizing | Gross | 0.25 bps | 0.5 bps | 1.5 bps |
|---|---|---|---|---|---|
| ORB5_QQQ, first year (IS) | risk 1% per trade, up to 4x leverage (about 3.5x on average) | +33.6% | +29.1% | +24.5% | +6.1% |
| ORB5_QQQ, second year (OOS) | same | +3.2% | -1.1% | -5.5% | -22.7% |
| NOISE_MOM_SPY, first year (IS) | min(4x, 2% / daily volatility) | +14.0% | +11.1% | +8.3% | -3.2% |
| NOISE_MOM_SPY, second year (OOS) | same | -9.9% | -13.5% | -17.2% | -31.6% |

**What this shows.** At 4x leverage, every basis point of cost is paid four times. ORB5 on QQQ earned **+0.15R per trade** before costs over the two years. The paper found +0.13R, so the pattern itself replicated. But it was +0.21R in the first year, +0.10R in the second, and about 0R in 2026. At our measured cost (0.5 bps) the second year lost 5.5%. This matches the independent CFD replication: the gross pattern is real, and the net result is about zero.

---

## 5. Options proxy (same-day at-the-money options)

This is what the same signals might earn if you bought a same-day call or put instead of shares. Numbers are % of the premium paid per trade, out-of-sample, at realistic option costs. **-15% means you lose $150 per $1,000 of premium, per trade, on average.**

| Setup | Sym | OOS trades | Avg per trade (% of premium) | 95% range | Pessimistic cost |
|---|---|---|---|---|---|
| ORB5_QQQ | QQQ | 255 | -14.6% | -22.0% to -6.9% | -20.6% |
| NOISE_MOM_SPY | SPY | 253 | -22.1% | -32.9% to -8.4% | -28.1% |
| VWAP_TREND_QQQ | QQQ | 4,013 | -7.3% | -8.5% to -5.9% | -13.3% |
| LAST30_MOM_SPY | SPY | 256 | -32.9% | -42.6% to -22.3% | -38.9% |
| ORB30_CLASSIC | SPY / QQQ | 254 / 253 | -25.6% / -31.9% | all below 0 | -31.6% / -37.9% |
| ORB15_CLASSIC | SPY / QQQ | 255 / 256 | -13.1% / -21.1% | all below 0 | -19.1% / -27.1% |
| EMA9_21_PULLBACK_5M | SPY / QQQ | 637 / 616 | -11.6% / -11.8% | all below 0 | -17.6% / -17.8% |
| PDH_PDL_BREAK_5M | SPY / QQQ | 138 / 126 | -4.1% / -11.0% | SPY -15.1% to +8.6%; QQQ -20.9% to +0.3% | -10.1% / -17.0% |
| VWAP_2SD_FADE_1M | SPY / QQQ | 625 / 563 | -5.4% / -7.4% | all below 0 | -11.4% / -13.4% |
| GAP_FADE_SPY | SPY / QQQ | 74 / 131 | -24.4% / -30.2% | all below 0 | -30.4% / -36.2% |
| GAP_GO_SPY | SPY / QQQ | 74 / 131 | -38.0% / -23.8% | all below 0 | -44.0% / -29.8% |

**Why options did so badly.** A same-day option loses value every minute (time decay), and it loses fastest near the close. LAST30 buys at 15:30 and sells at 15:55, the worst window for decay: -33% per trade. Setups with only a tiny edge in shares cannot pay for decay plus a 2% spread.

**Limits of this proxy.** It uses a simple model with no volatility smile, no intraday volatility changes and no real strike grid. Real results could differ by a lot. The direction of the answer (strongly negative) is not in doubt. **Do not scalp same-day options with these setups.**

---

## 6. Year by year (realistic cost, 1.5 bps per side)

bps per trade, with the number of trades. 2024 is Sep to Dec only, and 2026 is Jan to 25 Sep. Add 2.0 to get the 0.5 bps cost, or 3.0 to get the gross result.

| Setup | Sym | 2024 | 2025 | 2026 |
|---|---|---|---|---|
| ORB5_QQQ | QQQ | +5.99 (n=82) | -1.81 (n=245) | -4.64 (n=183) |
| NOISE_MOM_SPY | SPY | -0.61 (n=77) | -1.85 (n=223) | -4.03 (n=182) |
| VWAP_TREND_QQQ | QQQ | -2.46 (n=1,355) | -2.80 (n=3,971) | -3.02 (n=2,945) |
| LAST30_MOM_SPY | SPY | -4.45 (n=82) | -2.37 (n=247) | -1.75 (n=184) |
| LAST30_MOM_SPY_CLOSE | SPY | -4.92 (n=82) | -2.24 (n=247) | -2.17 (n=184) |
| ORB30_CLASSIC | SPY | -3.99 (n=82) | -2.29 (n=247) | -2.62 (n=182) |
| ORB30_CLASSIC | QQQ | -1.13 (n=82) | +1.93 (n=245) | -4.85 (n=181) |
| ORB15_CLASSIC | QQQ | +1.70 (n=82) | +0.49 (n=247) | -3.04 (n=184) |
| EMA9_21_PULLBACK_5M | SPY | -3.99 (n=209) | -3.42 (n=628) | -1.80 (n=454) |
| EMA9_21_PULLBACK_5M | QQQ | -5.87 (n=215) | -3.96 (n=616) | -0.03 (n=434) |
| PDH_PDL_BREAK_5M | SPY | +0.14 (n=42) | -2.85 (n=127) | -0.18 (n=96) |
| VWAP_2SD_FADE_1M | SPY | -3.47 (n=212) | -4.03 (n=611) | -3.09 (n=451) |
| GAP_FADE_SPY | SPY | +1.14 (n=15) | +3.08 (n=71) | +0.78 (n=57) |
| GAP_FADE_SPY | QQQ | -5.45 (n=28) | +3.60 (n=101) | -6.76 (n=99) |
| *check:* NOISE_MOM | QQQ | +6.35 (n=66) | +2.22 (n=214) | +1.10 (n=158) |

**Stable winners: none.** The only setup that was positive in all three years at 1.5 bps is GAP_FADE on SPY. It has just 143 trades, and its 95% range is very wide (-8.7 to +16.7 bps in the test half). It does not work on QQQ. NOISE_MOM on QQQ was also positive every year, but QQQ is not the paper's symbol, and its test-half result was exactly 0.00 bps. Both are worth watching, not trading. ORB5 and ORB15 on QQQ show a clear fade: positive in 2024 and negative in 2026.

---

## 7. Sanity checks (what we verified, and one bug fixed)

| Check | Result |
|---|---|
| Trade counts | ORB5, ORB15, ORB30 and LAST30: about 1 trade a day (the rules allow at most 1). GAP: 74 to 131 days per half with a gap of 0.5% or more. EMA and VWAP fade: 2.3 to 2.5 a day (the cap is 3). VWAP_TREND: about 16 a day, up to 55. NOISE: 0.9 a day, up to 5. All plausible. |
| Nothing open past 15:55 | Confirmed for every setup and both baselines. The one exception is the 16:00-close variant, which is designed to exit at 16:00. |
| Entry times | Inside each setup's window (for example ORB5 always 9:35, LAST30 always 15:30, EMA 10:00 to 15:00). |
| Baselines near zero | After the fix below: random baseline average **-0.10 bps** gross, coin-flip baseline **-0.31 bps** gross. Both are about zero, as they should be. |
| Test suite | 1,612 passed, 1 skipped. |
| Run time | Download about 2 minutes. Backtest about 43 seconds. No speed-up was needed. |

**Bug found and fixed: the random baseline could see the future.** The old random baseline copied each setup trade's **side** (long or short) onto a random minute, often an earlier one. But a momentum setup picks its side *after* seeing a move. For example, ORB30 goes long at 10:30 because price broke out. A random "long" at 9:40 then earns that breakout for free.
- Before the fix, random trades placed *before* the setup's entry averaged **+9.6 bps** gross. Those placed after averaged **-0.5 bps**. For NOISE on QQQ, the random baseline earned **+24 bps** per trade.
- This made momentum setups look worse than random and mean-reversion setups look better. VWAP_2SD_FADE on SPY showed a misleading p = 0.002.
- **Fix:** the random baseline now uses a coin-flip side (`trading/lab/scalp/backtest.py`, `random_baseline`). The setup trades themselves did not change at all. Only the "vs random" columns changed.
- **Test:** `tests/test_scalp_backtest.py::test_random_baseline_does_not_borrow_the_setups_side_from_the_future`. It uses a price path that rises, then goes flat. Copying the side there would earn about +225 bps; the fixed baseline averages about 0. The older test that required "same side as the setup" was updated.

**Known differences from the papers (not bugs).**
- All exits are at 15:55, not 16:00. The LAST30 16:00-close variant shows this does not rescue it.
- ORB5 hit its 10R target only 24 times in 1,020 trades. It mostly exits at the stop (765) or at 15:55 (231).
- NOISE_MOM made about 0.9 trades a day. The paper reports about 1.8. We traded on 60% of days and made 1.6 trades on each of those days. The paper may count trades differently. We could not settle this from the paper text.

---

## 8. Verdict, and what to paper-test next

**Verdict: no setup earned a paper test as an edge.** At every cost level, including zero, no setup's out-of-sample 95% range was above zero together with a p-value below 0.0018. The evidence says these minute setups on SPY and QQQ are **coin flips that pay the spread**.

**Still worth a small paper forward test, for two honest reasons:**
1. **Measure real fill costs.** Our costs are estimates. A paper account shows the price actually offered at the moment you trade. Remember that paper fills are *optimistic*: no queue, no latency, no fees.
2. **Learn the mechanics safely.** Placing, stopping and flattening a minute trade on time is a skill. It is better to learn it where mistakes cost nothing.

**Expect about zero, or a small loss.** If paper results look great for a few weeks, treat that as luck until 60+ sessions say otherwise.

**The three setups to paper-test (and why these three):**

| Setup | Why | Trades a day |
|---|---|---|
| ORB5_QQQ | The most taught setup. Its gross R-pattern replicated in year one and faded in year two. Paper trading shows whether the fade continues. | 1 |
| LAST30_MOM_SPY | The strongest peer-reviewed evidence. It is simple and makes 1 trade a day, at 15:30. | 1 |
| NOISE_MOM_SPY | The only paper that modelled commission *and* slippage. On the paper's own symbol, SPY, it lost in our test. | about 1 |

**Do not paper-test** VWAP_TREND (16 trades a day, a cost machine), VWAP_2SD_FADE, EMA 9/21, PDH/PDL or ORB30. They lose steadily after costs. **Do not use options** for any of them (section 5).

**Proposed paper-test caps (small amounts):**

| Cap | Value |
|---|---|
| Account | **A separate Alpaca paper account only** (keys `ALPACA_SCALP_KEY` / `ALPACA_SCALP_SECRET`). Never the rules-book account. See the research report, section 9. |
| Starting balance | $2,000 to $10,000 of paper money |
| Size per trade | **1 share** (about $740 to $770), close to the backtest's $1,000. No leverage. |
| Open positions | At most 1 per setup, at most 3 in total (about $2,300 of stock) |
| Instruments | SPY and QQQ shares only. No options. |
| Daily loss stop | **$25** across all three setups. When it is hit, flatten and stop for the day. |
| Whole-test stop | **$150** total loss, or **60 trading days**, whichever comes first |
| Time exit | Flat by **15:55 ET**. Nothing held overnight. |
| Orders | Market orders at the next bar open (like the backtest). Client order ids start with `SCALP-`. |
| Record for every fill | The bid and ask when the order is sent, the fill price, and the 1-minute bar open the backtest would have used |
| Reviews | After 20 and 60 sessions: compare the paper fills with a backtest replay of the same days. The key question is "is our 0.5 bps cost right?", not "did it make money?" |
| To go further | Real money only if a setup is positive after measured costs over 60+ paper sessions **and** a fresh backtest on 2016–2024 data (not yet run) agrees. Based on these results, that is unlikely. |

---

## 9. How to re-run it

From `trading/` (the keys are read from the environment and never printed):

```bash
# 1. Download and cache the bars (about 2 minutes the first time; later runs reuse the cache)
python -m lab.scalp download --symbols SPY QQQ --start 2024-09-03 --end 2026-09-25

# 2. Run every setup, both baselines, all cost levels, the options proxy, the IS/OOS split and the years (about 45 s)
python -m lab.scalp backtest --symbols SPY QQQ --start 2024-09-03 --end 2026-09-25

# 3. Optional: re-score the saved trades at other costs without re-running (e.g. realistic = 0.5 bps per side)
python -m lab.scalp report --cost realistic=0.5
```

- Outputs go to `trading/state/scalp_results/`: `summary.md` (all tables), `results.csv` / `results.json` (every metric), `trades.csv.gz` (every setup and baseline trade) and `meta.json` (settings).
- The bar cache is `trading/state/scalp_cache/`. Both folders are gitignored.
- The results are fixed by seed 0 and 2,000 bootstrap resamples. A re-run gives the same numbers.
- **Next useful run:** SIP history goes back to 2016. Running `--start 2016-01-04 --end 2024-08-30` would test the papers' own periods and show whether the edges were real then and have since faded.
