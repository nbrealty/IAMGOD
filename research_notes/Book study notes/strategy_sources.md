# Strategy sources: study notes and code comparison

Sources: four partial files in the owner's scratchpad `books/` folder. Each section below covers:
(1) what the file is, (2) key lessons, (3) codeable rules, (4) comparison with
`trading/trader/strategies.py` plus `config/playbook.yaml` and `config/risk_policy.yaml`, and (5) claims to check.

The notes are paraphrased. Rules and numbers are restated as the files give them. If a number is **not in the
file** and comes from general knowledge of the full book, it is marked *(not in file; verify in the full book)*.

Code facts used throughout (checked in the repo):
- Bars come from Alpaca with `Adjustment.ALL` (split- and dividend-adjusted), so momentum is total-return-like.
- RSI is Wilder's RSI (`indicators.rsi`, EWM with alpha = 1/n).
- The engine computes targets from the **last daily close**. Stock and ETF orders are DAY orders that queue for
  the **next open** (`broker.py`). So every "buy on the close" rule in the sources is filled at the next open in
  the bot.
- `risk.py` clips each order by per-trade risk, a per-symbol notional cap summed across sleeves (ETF 30%), the
  cash buffer, and open-risk heat (6%).

---

## 1. Connors & Alvarez, *Short Term Trading Strategies That Work* (2009): summary file

### 1.1 What the file is
- A short slide-style summary of the book (369 lines). It is not the book.
- It lists the chapter headings, the rule for each strategy in one or two lines, and the 16-point "Finale".
- It includes **no** performance tables: no win rates, trade counts, average gains or drawdowns. It says only
  that the strategies were backtested on 1995–2007 data.
- Some thresholds are given loosely. For example, the RSI(2) entry is described as "below 10", and then
  "below 5" in the Finale.

### 1.2 Key lessons
- **Mean reversion on the short horizon, inside a long-term uptrend.**
  - Buy weakness (down days, low RSI(2), closes at N-day lows, VIX spikes) only when the instrument is above its
    200-day moving average.
  - Sell into the bounce. Do not buy strength.
- **Buy pullbacks, not breakouts.** For the index, three down days in a row were followed by five-day returns of
  more than 4× the average weekly gain. Three up days in a row were followed by a small average loss over the
  next five days.
- **Stops cost money in this style.** The tighter the stop, the worse the results; the summary says wider is
  better. It says to control risk with position size and money management instead of stops. The Finale calls
  stops "potentially an expensive form of insurance."
- **Exits should be dynamic, not fixed-time.**
  - Connors dislikes fixed-time exits and prefers selling into strength.
  - Best exits: a close above the 5-day SMA (first choice, then the 10-day), or RSI(2) closing above 65, 70 or 75.
  - Other valid exits: the first up close (Larry Williams), or a close at a new high.
  - Trailing stops: few showed consistent results, and tighter ones did worse.
- **The overnight edge.**
  - Over the test period, buying SPY at the open and selling at the same day's close lost 70.88 points.
  - Buying at the close and selling at the next open gained 171.40 points.
  - The strategies are designed to **enter on the close**.
- **Intraday selloffs strengthen the edge.** A bigger intraday drop gave better five-day forward returns, and
  strong intraday momentum gave worse ones.
- **Psychology.** Plan ahead for a new system that starts badly or starts too well, for losing streaks, and for
  fat-finger errors.

### 1.3 Codeable rules (as stated in the file)
Every long rule has the same trend filter: **close > SMA(200)** of the traded instrument (for market timing, SPY).

| # | Strategy | Entry (on the close) | Exit |
|---|---|---|---|
| 1 | 3-day pullback | Index closes down 3 days in a row, above SMA200 | Horizon studied: 5 days. Exit not specified; use the dynamic exits below |
| 2 | RSI(2) | RSI(2) < 10 (Finale: < 5 is better; "the lower the better"); never buy RSI(2) > 90 | Studied up to 1 week; holding the full week beat shorter holds. Exit on close > SMA5 or RSI(2) > 65–75 |
| 3 | Double 7s | SPY (or index/ETF) above SMA200 **and** closes at a 7-day low | Close at a 7-day high |
| 4 | VIX 5% rule | VIX close ≥ 5% **above** its 10-day SMA, with SPY above SMA200 | Lock in gains and don't buy when VIX ≥ 5% **below** its 10-day SMA |
| 5 | VIX stretches | SPY > SMA200 **and** VIX ≥ 5% above its 10-day MA for **3 or more days** | SPY RSI(2) closes ≥ 65 |
| 6 | VIX RSI | SPY > SMA200, **RSI(2) of VIX > 90**, today's VIX open > yesterday's VIX close, **SPY RSI(2) < 30** | SPY RSI(2) closes > 65 |
| 7 | TRIN | SPY > SMA200, SPY RSI(2) < 50, **TRIN > 1.00 for 3 days in a row** | RSI(2) closes > 65 |
| 8 | Cumulative RSI | SPY > SMA200, **sum of the last 2 days' RSI(2) < 45** (this file's number) | RSI(2) closes > 65 |
| 9 | S&P short | SPY **below** SMA200 and up 4+ days in a row: short on the close | Cover on close < SMA5 |
| 10 | End of month | Stocks above SMA200 did best on trading days 25, 24, 1, 27, 26, 29, 28, 30 and worst on days 3–8. After a 1-day drop: 25, 30, 27, 26, 24, 28, 29, 22, 1, 31 | Not specified |
| 11 | Intraday drop | Prefer entries after a large intraday selloff | 5-day horizon |

Notes on the rules:
- The cumulative RSI threshold for the SPY market-timing version is **45** in this file. Other published
  versions of Connors' cumulative RSI use 35 for ETFs *(not in file; verify in the full book)*.
- Double 7s has no stop in the source.
- Strategy 9 (the short) is not usable: the bot is long-only by policy.
- The file does not define "day of month". Days 25–31 look like **calendar** days.

### 1.4 Comparison with sleeve B (`sleeve_b`)

| Item | Source | Bot | Verdict |
|---|---|---|---|
| Trend filter | Close > SMA200 of the instrument | `close > sma200`, per symbol | **Match** |
| Entry trigger | RSI(2) < 10, better < 5 | `rsi2 < cfg["rsi_entry"]`, `rsi_entry: 10` | **Match** (the looser of the two stated levels) |
| Ranking when too many signals | "Lower is better" | Sorted ascending by RSI2 | **Match** |
| Entry timing | **On the close** | Signal on the close, filled at the **next open** | **Mismatch.** The bot gives up the close-to-open move that the file says holds most of the index's return. After an oversold close, that gap is often up |
| Profit exit | Close > SMA5 (first choice) or RSI(2) > 65–75 | Close > SMA5 | **Match** (the preferred exit) |
| Fixed-time exit | Disliked | 10-day time stop (`time_stop_days.B: 10`) | **Differs.** It is mild: 10 days is more than the ≤1-week horizon tested |
| Stop loss | Stops hurt; wider is better; control risk with size | 3×ATR(20) "disaster" stop, used for sizing, never widened | **Differs in spirit.** See the sizing note below |
| Other entries | Cumulative RSI, Double 7s, VIX, TRIN, 3 down days | Not implemented | Gap |
| Regime | Per-instrument SMA200 only | Also gated by the regime classifier: B = 0 in bear/panic, 0.5 in choppy/bull_volatile | Stricter than the source. It cuts trades in high-VIX periods, which is exactly when the file says the edge is largest (VIX rules) |

**How the stop interacts with sizing (worked example).**
- Sizing is `qty = min(risk / (3·ATR), sleeve_capital / max_positions / close)`, with risk = 0.5% of equity.
- For SPY, ATR(20) is roughly 1–1.5% of price, so the 3×ATR stop sits about 3–4.5% below entry.
- Risk-based size is then 0.5% / 3.6% ≈ 14% of equity. The sleeve cap is 20% / 2 = 10% of equity.
- So the **notional cap is what binds**. The stop mostly acts as a catastrophe exit, not a sizing input.
- That is close to Connors' advice (size small, keep any stop wide).
- Widening the stop to 5×ATR would make the **risk** cap bind (0.5% / 6% ≈ 8% notional) and shrink positions.
  Do not widen it without also changing the sizing rule.

**Proposed changes (to test in the backtester before switching on):**
1. **Enter on the close.**
   - Evaluate sleeve B about 10–15 minutes before the close, using the last trade as a proxy close.
   - Submit market-on-close orders (Alpaca `time_in_force="cls"`) for B entries and exits.
   - Reason: the tested edge includes the overnight move. This is the largest mismatch.
   - If this is not feasible, backtest "signal at close, fill at next open" explicitly and compare it with the
     book version. Expect a weaker edge.
2. **Make the time stop configurable and test a longer value or none.**
   - For example, `time_stop_days.B: 0` (disabled) versus 10 versus 15.
   - Reason: Connors dislikes fixed-time exits. His exits are dynamic.
3. **Keep a wide disaster stop but decouple it from sizing.**
   - Size B on a fixed notional (e.g. `capital / max_positions`, already the binding term).
   - Set the stop at max(3×ATR, the level that keeps risk ≤ 0.5%).
   - Record a note that Connors found tight stops hurt, so the stop must never be tightened below 3×ATR.
   - `risk.py` needs a stop for heat accounting, so keep the stop, just keep it wide.
4. **Add an RSI(2) exit option.** `exit_rule: sma5 | rsi2_gt: 70`. Connors lists both as best; test both.
5. **Add optional entry triggers** as alternatives in the same sleeve, sharing slots:
   - `cum_rsi2_2d < 35..45` (the file says 45 for SPY)
   - Double 7s (close = 7-day low of closes; exit at the 7-day high)
   - VIX 5% stretch. This needs a VIX series; Alpaca has no index data, so pull `^VIX` from another feed or skip it.
6. **Relax the regime gate for B when SPY > SMA200.**
   - "bull_volatile" halves B; a high-VIX, above-200 market is where the VIX rules say to buy.
   - Consider `bull_volatile: {B: 1.0}`. Keep B at 0 when SPY < SMA200 (that matches Connors).
7. **Optional: tighten `rsi_entry` to 5**, or scale size (full size < 5, half size 5–10).
   - Test both. Fewer trades means noisier statistics.
   - The four symbols are highly correlated, so the effective sample is small either way.

### 1.5 Claims to check
- Backtest period 1995–2007 only. That is a strong mean-reverting era for US indexes.
  - Check out-of-sample from 2008 to now, including 2008 (the SMA200 filter should keep it out), 2020, and 2022.
- No commissions, slippage or taxes are mentioned in the file. RSI(2) trades are short with small average gains,
  so check the edge net of 5 bps per side (the bot's cost model for ETFs).
- The overnight numbers (−70.88 vs +171.40 SPY points) are for a specific period. Re-check them on recent data.
- "Stops hurt": verify with the bot's own backtest at 2, 3, 5 ATR and no stop, measuring CAGR, max DD and worst trade.
- Publication decay: the RSI(2) edge is widely known since about 2008. Measure post-2009 expectancy separately.
- End-of-month day rankings are one sample's ordering and are prone to data mining. Treat them as weak evidence.

---

## 2. Minervini, *Trade Like a Stock Market Wizard*: third-party summary (Bookey)

### 2.1 What the file is
- A Bookey app summary: chapter synopses, "critical thinking" boxes, quote lists, Q&A and quizzes (2,770 lines).
  It is not the book.
- Several chapters are cut off at an "Install Bookey App to Unlock Full Text" marker: Ch 3 (SEPA), Ch 6, Ch 9
  and Ch 12.
- It does **not** list the exact 8-point Trend Template, VCP measurements, or stop-loss percentages. Only
  fragments appear.
- Treat any precise Minervini number below as coming from the full book (marked) unless it is quoted from this file.

### 2.2 Key lessons
- **SEPA** (Specific Entry Point Analysis) has five elements that should line up at the same time:
  trend, fundamentals, catalyst, entry point, exit point. The summary calls this "probability convergence".
- **Stage analysis.**
  - Only buy in Stage 2 (advancing).
  - Never buy Stage 1 (neglect) no matter how good the fundamentals look.
  - Avoid Stage 3 (topping) and Stage 4 (declining).
  - Only consider stocks above the 200-day MA.
- **Trend Template.** The file describes it only loosely:
  - price above the 150- and 200-day MAs
  - at least 25–30% above the 52-week low
  - higher highs and higher lows
  - strong relative strength
  - volume expanding on up moves
- **Fundamentals.**
  - Earnings and sales growth, preferably accelerating.
  - Meaningful earnings surprises, and upward estimate revisions of 5% or more.
  - "Code 33": three quarters of acceleration in EPS, sales and margins at once.
  - Growth managers target ≥20–25% year-on-year EPS growth, ideally 30–40%+.
  - Avoid growth that comes from cost cuts or one-offs.
- **Leaders.**
  - The biggest winners are often young companies (IPO within about 8–10 years) and small or mid caps.
  - More than 90% of superperformers emerge from bear markets or corrections.
  - True leaders make new highs in the first 4–8 weeks off a market low.
  - Fewer than 25% of one cycle's leaders lead the next.
- **Entry.**
  - Buy from a proper base with **volatility contraction (VCP)**: the pullbacks get smaller and volatility dries up.
  - Enter at a **pivot**: a break above recent highs on increasing volume.
  - Watch for failed breakouts ("squat" or reversal) and wait for follow-through.
  - Primary base: at least 3–5 weeks of consolidation, with corrections not deeper than 25–35%.
  - Power play: a sharp run on huge volume, then a tight flag that corrects no more than 20–25%.
- **Risk** (Ch 12–13).
  - Set the stop before buying and treat it as an absolute maximum.
  - Sell immediately when it is hit, even on a gap.
  - Raise the stop to protect profits after a good gain.
  - Never average down. Scaling in is only for winners.
  - Cut size in a losing streak and rebuild slowly.
  - Keep losses smaller than the average gain.
  - Concentrate: about 4–6 stocks, at most 10–12.
  - Minervini also argues that paper trading gives a false sense of security (relevant to this bot's owner).

### 2.3 Codeable rules
From the file (explicit or near-explicit):
- `close > SMA200` (hard screen); `close > SMA150 and close > SMA200`.
- `close >= 1.25..1.30 × low_52w`.
- Higher highs and higher lows (e.g. the last two swing lows rising).
- Breakout: `close > pivot_high` and `volume > avg_volume` (the file says "increasing volume").
- Base ≥ 3–5 weeks, depth ≤ 25–35% (primary base). Power-play flag depth ≤ 20–25%.
- Portfolio: 4–6 positions, max 10–12.
- Stops: predetermined, never widened, no averaging down, halve size after a losing streak.
- Fundamentals (need data the bot doesn't have): EPS growth ≥ 20–25% y/y, accelerating over the last 2–3 quarters,
  with sales growth and margin expansion (Code 33 = 3 quarters of all three accelerating).

From the full book, as commonly cited *(not in file; verify in the full book)*:
1. Price > SMA150 and > SMA200.
2. SMA150 > SMA200.
3. SMA200 rising for at least 1 month (preferably 4–5 months).
4. SMA50 > SMA150 and > SMA200.
5. Price > SMA50.
6. Price ≥ **30%** above the 52-week low.
7. Price within 25% of the 52-week high.
8. RS rating ≥ 70 (preferably 80s–90s).

Other book figures, same caveat:
- VCP: usually 2–6 contractions, each roughly half the depth of the previous one, with volume drying up in the
  last contraction.
- Maximum stop around 10%, with average losses much smaller.

### 2.4 Comparison with sleeve C (`trend_template`, `sleeve_c`)

| Item | Source | Bot | Verdict |
|---|---|---|---|
| Price > 150 & 200, 150 > 200, 50 > 150 & 200, price > 50 | Book template | Implemented exactly | **Match** |
| 200-day rising | ≥1 month (prefer 4–5) | `s200[-1] > s200[-22]` (≈1 month) | **Match (minimum)**. Could require about 80–100 bars |
| Above 52w low | 25–30% in this file; 30% in the book | `close >= 1.25 × lo52` | **Looser** than the book |
| Within 25% of 52w high | Book | `close >= 0.75 × hi52` | **Match** |
| RS ≥ 70 | IBD-style RS versus the whole market, weighted to recent quarters | Percentile of 12-month return **inside a 40-stock mega-cap list** | **Differs.** The 70th percentile of 40 hand-picked leaders is the top 12 of an already strong group. That is not the same as RS 70 against the whole market |
| VCP / base | Contracting pullbacks, drying volume, base 3–5+ weeks | Not implemented. Pivot = 50-day high; breakout = close > pivot with volume ≥ 1.5× the 50-day average | **Gap.** The bot buys any 50-day-high breakout inside the template |
| Fundamentals / catalyst | Core of SEPA | None | **Gap.** Data not available |
| Universe | Young, small/mid-cap leaders | 40 fixed mega-caps | **Differs.** Also a survivorship and look-ahead bias for backtests, because the list was chosen by today's size |
| Initial stop | Predetermined max (book about 10%) | `max(close − 2·ATR, 0.92·close)`, so the stop is never more than 8% below entry | **Match in spirit**; tighter than the book's maximum |
| Protect profits | Raise the stop after a good gain | Stop never raised. Exits on close < 10-day low or < SMA50 | **Partial.** The 10-day-low exit does trail |
| No averaging down | Yes | `no_averaging_down: true` | **Match** |
| Positions | 4–6, max 10–12 | `max_positions: 5` | **Match** |
| Losing streak | Cut size | Only drawdown breakers (10% halves risk) | Partial |
| Market gate | Leaders often break out early in new bull markets | C = 0 in bear/panic/choppy | Conservative. It will miss the early leaders Minervini emphasizes, but it is safer |

**Proposed changes:**
1. **VCP proxy filter** (config `vcp: true`). Require all three before a breakout counts:
   - **Tight base:** `(max(high[-15:]) − min(low[-15:])) / close <= 0.10–0.12`.
   - **Contraction:** `ATR(10)/ATR(50) < 0.8` on the day before the breakout, or the depth of the last three
     10-day pullbacks is decreasing.
   - **Volume dry-up:** `mean(volume[-10:-1]) < mean(volume[-50:-1])`.

   Reason: VCP is the core of Minervini's timing, and without it the sleeve is a generic 50-day breakout.
   Backtest with and without the filter.
2. **Low threshold to 30%:** `pct_above_52w_low: 0.30` (config, default 0.30). This matches the book's template.
3. **RS versus a benchmark, not the peer list.**
   - Compute a weighted RS: 0.4·r63 + 0.2·r126 + 0.2·r189 + 0.2·r252, which approximates IBD's weighting.
   - Rank it against a broad list (e.g. S&P 500 members), **or** require `RS_line = close/SPY` to be at a
     52-week high or within 5% of it.
   - Keep `rs_min_percentile: 70`, but it then means what Minervini meant.
4. **Breakeven stop:** once `close >= entry + 2R` (or +10%), raise the stop to entry.
   - It never moves down (`never_widen_stop` already enforces this).
   - Reason: the file says to raise the stop to protect profits after a gain.
5. **Streak rule:** after 3 consecutive losing sleeve-C trades, halve C's risk until the next winner.
   - Reason: Minervini's scale-back advice. This sits on top of the global drawdown breakers.
6. **Universe:** widen it to liquid mid caps (e.g. S&P 400/500 members with price > $10 and ADV > $20M), or
   document that the sleeve is a large-cap variant.
   - Use point-in-time membership in backtests to avoid survivorship bias.
7. **Fundamentals (optional, Claude layer):** before a C entry, have Claude check the last two quarters of EPS
   and sales growth from filings or news and veto if they are decelerating or negative. Log this as a
   discretionary overlay, separate from the rules book.

### 2.5 Claims to check
- "More than 90% of superperformers emerge from bear markets or corrections" and "Amazon rose 2,500% in 16 months
  from its primary base": both are selected anecdotes and survivorship-biased. The file has no base rate for
  failed breakouts.
- The 1997 US Investing Championship return of 155% is a single audited-contest year. It says nothing about the
  rules' expectancy.
- No backtest, costs or slippage appear. Breakout systems on single stocks have low win rates (often 30–45%) and
  depend on a few big winners, so check the bot's realized payoff ratio after 100+ trades.
- The Antonacci slides (below) show stock-momentum funds lagging their benchmarks after costs:
  DWA −2.1%/yr and AQR −1.5%/yr to Jan 2017. That is a reminder that single-stock momentum is cost-sensitive.

---

## 3. Antonacci, *Dual Momentum Investing*: slide presentation

### 3.1 What the file is
- The text of a conference slide deck by Gary Antonacci (1,854 lines). It is not the book.
- About 60% of the lines are chart axis labels (years split into digits).
- The useful content: definitions, the GEM components, lookback and rebalance frequency, summary tables, and the
  Zakamulin moving-average comparison.
- It does **not** spell out the T-bill comparison step or the exact ordering of the rules. Those are in the book.

### 3.2 Key lessons
- Momentum is the most robust anomaly. It works across stocks, sectors, bonds, commodities and currencies, from
  1800 to today (Geczy & Samonov). Jegadeesh & Titman found 3–12 month formation periods work.
- Why it works: underreaction first (anchoring, slow information diffusion, the disposition effect), then
  overreaction (herding, recency bias, overconfidence).
- **Stock-level momentum is hard to capture after costs and scale.**
  - Returns fall as the portfolio widens: 17.0% for 50 stocks with a 1-month hold, down to 9.8% for the
    500-stock universe.
  - Live momentum funds lagged their growth benchmarks.
  - So apply momentum to **asset-class indices** instead.
- There are two kinds of momentum:
  - **Relative (cross-sectional):** pick the stronger of US versus non-US stocks.
  - **Absolute (time-series):** own stocks only if their own trend is positive; otherwise hold bonds.
  - Relative momentum raises returns. Absolute momentum cuts drawdowns. Combining them does both.
- In a 155-year S&P study (Zakamulin 2015), 12-month **absolute momentum was the best** trend rule. SMA,
  reverse-EMA and dual-EMA crossover rules came after it; only MOM and REMA were statistically significant.
- The risks are tracking error and whipsaws. Holding on takes patience, discipline and understanding.

### 3.3 Codeable rules (GEM, as the slides state)
- Universe: S&P 500 (US), MSCI ACWI ex-US (international), Barclays US Aggregate (bonds).
  The book uses T-bills as the absolute-momentum hurdle *(the slides only say "switches between stocks and
  bonds"; the T-bill hurdle is from the book)*.
- Lookback **12 months**, **monthly** rebalance, total returns.
- Rule, in the book's usual form:
  1. If the S&P 500's 12-month total return is greater than the T-bill 12-month return:
     hold whichever of S&P 500 or ACWI ex-US has the higher 12-month return.
  2. Otherwise hold aggregate bonds.
- Reported 1971–2016 results (hypothetical, index level, no fees):

| Strategy | CAGR | Standard deviation | Sharpe | Max drawdown (month-end) |
|---|---|---|---|---|
| Dual momentum | 17.0% | 12.5% | 0.92 | −17.8% |
| Absolute momentum only | 12.9% | 11.9% | 0.66 | −29.6% |
| Relative momentum only | 13.5% | 15.9% | 0.56 | −54.6% |
| S&P 500 | 10.7% | 15.1% | 0.42 | −51.0% |
| ACWI ex-US | 10.2% | 17.2% | 0.37 | −57.4% |

- S&P absolute momentum (1927–2016) in the worst drawdowns:
  - 2007–09: +5.0% versus −50.9% for the S&P.
  - 2000–02: +17.4% versus −43.8%.
  - 1929–32: −27.2% versus −83.4%.
- Trend-up months (66% of months) averaged 14.2% a year at 14.8% vol. Trend-down months averaged 7.7% at 24.9% vol.

### 3.4 Comparison with sleeve A (`gem_pick`, `sleeve_a`)

| Item | Source | Bot | Verdict |
|---|---|---|---|
| Lookback | 12 months, monthly | `m[-1]/m[-13] − 1` on completed month-ends | **Match** |
| Total return | Yes | `Adjustment.ALL` bars | **Match** (dividend-adjusted) |
| Absolute filter | US 12m versus T-bill 12m | `us <= tbill → bonds` (BIL as T-bill) | **Match** (book form) |
| Relative step | US versus ACWI ex-US | `us >= intl ? SPY : VEU` | **Match**. VEU tracks FTSE All-World ex-US; ACWX is the exact MSCI ACWI ex-US proxy. The difference is small |
| Bonds | Barclays US Aggregate | AGG | **Match** |
| Enabled | Core strategy | `gem_blend: false` (off by default); when on, 50/50 with Faber GTAA-5 | Choice |
| Vol scaling | None in GEM | The Faber half is vol-scaled to 10%; **the GEM half is not** | Inconsistent with the `vol_target_annual` comment in `risk_policy.yaml` ("sleeve A ETFs") |
| Concentration | n/a | With the blend on, SPY can be 0.5 (GEM) + ~0.1 (Faber) = about 60% of sleeve A = about 33–36% of equity | Above the 30% ETF cap. `risk.py` clips it, so GEM silently becomes under-weight |

**Proposed changes:**
1. **Decide on GEM explicitly.** The slides support blending absolute momentum with the SMA rule:
   - Zakamulin ranks 12-month MOM above the SMA.
   - Both GEM and GTAA are trend rules on different assets, so the blend adds signal diversity at little cost.
   - Suggest turning `gem_blend: true` on in paper mode and logging both halves' P&L separately.
2. **Avoid the notional clip.** Either:
   - raise `max_single_etf_notional` for sleeve A's core index ETF to 0.40, or
   - map the GEM US leg to a **different** ticker than Faber's US leg. For example, GEM US = VOO or IVV while
     GTAA keeps SPY, and give the clip a sleeve-A exception.

   Otherwise GEM's intended 50% can be cut without anyone noticing.
3. **Use ACWX instead of VEU** if the goal is to follow the source exactly. It is optional, and VEU has lower fees
   and a longer history.
4. **Treat vol scaling consistently.** Either leave GEM unscaled (as Antonacci does; document that choice) or
   scale it like Faber. Mixing the two makes the sleeve's risk depend on which half is active.
5. **Optional: add a second GTAA vote.** Use 12-month absolute momentum next to the 10-month SMA:
   full weight if both are positive, half weight if only one is, zero if neither. Reason: Zakamulin's result
   that MOM is the stronger single rule.

### 3.5 Claims to check
- All figures are hypothetical index backtests: no fees, costs or taxes, and month-end drawdowns (intra-month
  drawdowns are deeper).
- The disclosures in the slides say this themselves.
- GEM was published in 2014. Check post-publication performance (2015–now) using ETFs.
  - GEM had well-known whipsaws, e.g. in 2015–16, late 2018, and the 2020 crash/rebound.
  - The 2022 stock and bond drawdown hit the "bonds" leg.
- The 1971–2016 ex-US series before ETFs is MSCI index data. Real implementation starts around 2007–08 (VEU/ACWX).
- The ~17% CAGR period overlaps the design period, so there is a risk of in-sample bias. The sample has only
  about 45 years of monthly decisions and a few dozen switches.

---

## 4. Covel, *Trend Following* (5th ed., 2017): partial extraction

### 4.1 What the file is
- A fragmentary text extraction (9,502 lines).
- Almost none of the narrative text survived. What remains:
  - performance tables of trend-following CTAs (Winton, Dunn, Campbell, Chesapeake and others)
  - chart axis labels and sidebar quotes
  - tables and captions from the research chapters: Greyserman & Kaminski multi-century study; Lempérière /
    Bouchaud et al. "Two Centuries of Trend Following"; Aspect Capital's model comparison; Harvey & Liu on
    backtest overfitting; the "Black Box Trend Following" chapter with CB50 and MA10×100 rules; the risk
    management chapter on Kelly and fixed fraction; the GRAB system code; the tactical macro and carry-and-trend
    chapters
- So the "principles" part of the book is essentially missing. The concrete rules come from the research appendix.

### 4.2 Key lessons (from what survived)
- **Trend following makes money in a few big moves and goes sideways in between.**
  - In the Babe Ruth versus Dave Kingman sidebar, profits "come in bunches".
  - The job between home runs is to lose little.
- **Crisis alpha.** In the S&P 500's worst quarters, the Barclay CTA index was mostly positive:
  - Q4 1987: +13.8% versus −22.5% for the S&P.
  - Q3 1998: +9.0%.
  - Q1 2008: +6.9%.
  - Not always: Q3 2008 was −3.0%, and Q3 2015 −0.3%.
- **The difference between managers is in portfolio and risk management, not entries.** Big trend followers are
  highly correlated with each other (about 0.6–0.8).
- **Drawdowns are part of it.**
  - Dunn warns every investor about seven drawdowns of 25% or more.
  - The recovery table: −20% needs +25%, −50% needs +100%.
  - Don't overhaul a program after one bad year.
- **Size by risk, not by value.**
  - Use fixed-fraction betting, and watch "portfolio heat" (total open risk).
  - Kelly gives an optimum, but betting beyond it destroys wealth ("Bold Trader Rule"). Betting too little makes
    too little ("Timid Trader Rule").
  - A sidebar (Kovner) says novices trade 5–10× too big, and should risk 1–2% per trade.
- **The evidence is robust across lookbacks and centuries.**
  - The Bouchaud trend signal has Sharpe ≈ 0.8 for 2–10 month horizons, falling at 15–20 months.
  - Results hold per sector and per decade.
  - The signal **saturates** (a tanh fit): very strong trends add little extra expected return.
  - Warnings: a 3-day trend on futures "seems to have completely disappeared since 2003", and the aggregate trend
    strategy was "virtually flat" from 2011.
- **Combining trend models improves risk-adjusted return.**
  - Aspect's 13 models (Turtle Donchian, MA crossover, TSMOM, RSI and others) were 67–97% correlated with each
    other.
  - The information ratio rises as more models are combined.
- **Long versus short.** In the black-box study, most of the return came from the long side:
  - MA10×100: 12.7% long versus 2.3% short.
  - CB50: 11.6% long versus 1.2% short.
  - The short side was valuable mainly as a hedge (correlation to the S&P about −0.42).
- **Beware of backtest overfitting.** Harvey & Liu's figures on false discoveries: with many trials, a good-looking
  Sharpe is often luck.

### 4.3 Codeable rules found in the file
- **CB50 (channel breakout).**
  - C = today's close; HC50 and LC50 = the highest and lowest close of the last 50 days, including today.
  - If C = HC50, go long at tomorrow's open. If C = LC50, go short at tomorrow's open. Always in the market.
- **MA10×100.**
  - Long if SMA10 > SMA100, short if SMA10 < SMA100, executed at tomorrow's open.
- **Results on a 24-market futures basket, 1990 to about 2010:**
  - MA10×100: 15.1% CAGR, −28.2% max DD, Sharpe 0.68 (fees: 11.2%, −24.3%).
  - CB50: 12.8%, −33.7%, Sharpe 0.56 (fees: 9.5%, −29.9%).
  - S&P 500: 5.4%, −52.6%.
  - Trades: about 3–4 per market per year, lasting 60–81 days on average.
- **Parameter stability:**
  - MA10×{75…200}: CAGR 13.0–16.3%, Sharpe 0.58–0.75.
  - CB{25…150}: CAGR 12.1–19.2%, Sharpe 0.56–0.89. Longer channels did better and traded less.
- **GRAB (two-box) system:**
  - Far box X = 80 days (trend); near box Y = 40 days.
  - Trend = +1 when the high breaks yesterday's 80-day high, −1 when the low breaks yesterday's 80-day low.
  - In an uptrend, buy on a limit at the 40-day low (fade the near box) and sell on a limit at the 40-day high.
  - The last trade exits on a stop at the 80-day low (trend flip).
- **Sizing:**
  - `shares = (equity × risk%) / (risk per share)` (risk basis, not value basis).
  - Kelly optimum for a 2:1 payoff coin with p = 0.5: b = (P − 1)/(2P) = 25% (as an illustration, not a
    recommendation).

### 4.4 Comparison with sleeve D (`donchian_score`, `sleeve_d`) and the rest of the bot

| Item | Source | Bot | Verdict |
|---|---|---|---|
| Signal type | Donchian/closing-high breakout (CB) or MA crossover | Vote = share of 7 lookbacks where close > the channel midpoint ((max high + min low)/2) | **Different mechanics, same family.** A midpoint vote is a "position within channel" signal. It flips at the midpoint, earlier than a breakout/opposite-breakout pair, so expect more turnover |
| Multiple lookbacks | Combining models raises IR; lookbacks 25–150 all worked | 20, 30, 50, 80, 120, 180, 250 | **Consistent** with the ensemble evidence |
| Long/flat | The long side carried most of the return | Long/flat | **Consistent** |
| Signal saturation | tanh: strength beyond a point adds little | Score bounded in [0, 1] | **Consistent** |
| Vol targeting | Risk-based sizing | min(1, 25%/vol30) scaling | **Consistent** |
| Diversification | The edge comes from many uncorrelated markets | Two highly correlated coins (BTC, ETH) | **Weak point.** Covel's evidence is not about crypto, and two correlated assets give little diversification |
| Stop | Exit on the opposite signal | Fixed initial 3×ATR stop that is never trailed, plus the score falling to 0 | OK. The stop is a backstop and the score does the exiting |
| Per-trade risk | Sidebars: 1–2% (Kovner) | 0.5% default, 1% validated, 2% cap | More conservative. Fine while unvalidated |
| Portfolio heat | Concept named in the file | `max_open_risk_heat: 0.06` | **Match** |
| Sleeve A | 10-month horizon has t-stat 5.6 in Bouchaud's table | Faber 10-month SMA | Supported |

**Proposed changes:**
1. **Test a CB-style exit in sleeve D.** Enter or raise the weight on the midpoint vote, but require the close to
   break the N-day **low** (not the midpoint) before cutting to zero. Alternatively, use votes on
   `close > SMA(n)` for n in {20, 50, 100, 200}. Reason: less churn. The book's systems hold 60–80+ days per trade.
   With the 25 bps crypto cost model, midpoint flips cost more.
2. **Optional: extend sleeve A with a sleeve-A-style trend vote on more asset classes** (gold GLD, long bonds TLT,
   dollar UUP), long/flat. Reason: Covel's edge comes from diversification across sectors. The crypto sleeve
   alone does not provide it.
3. **Record regime-decay warnings in the Claude prompt.** The 3-day trend died after 2003, and trend was flat
   2011–2016. Claude should not "fix" D after one bad year; the Eclipse Capital sidebar warns against this.
4. **Backtest discipline (Harvey & Liu).** Keep a log of every parameter set tried. Prefer round, stable
   parameters (as in the MA10×75–200 table) over the single best one.

### 4.5 Claims to check
- CTA tables show **selected, surviving** managers. The only failure shown is Niederhoffer's −99.99% in 1997.
  Look for the full CTA database return (e.g. SG Trend Index) for a fair base rate.
- Multi-century results (1223 or 1300 to 2013: trend 13.0% a year, Sharpe 1.16, versus buy-and-hold 4.8%) are
  reconstructed from sparse historical prices. Transaction costs, financing and slippage assumptions are not
  visible in the extract.
- The black-box CB50/MA10×100 results cover 1990 to about 2010 on futures. The "with fees" figures cut about 3–4%
  a year, but the fee assumptions were not in the extract. The results also depend on the chosen 24 markets.
- The "Recent Performance of the Trend" figure says the strategy was flat after 2011. Check 2017–2025 CTA
  performance (strong in 2022, weak in several other years).
- Crisis alpha is not guaranteed. Q3 2008 and Q3 2015 were negative for the CTA index in the book's own table.

---

## 5. Cross-source tensions to keep in mind
- **Pullbacks (Connors) versus breakouts (Minervini, Covel).** They are not contradictory:
  - Connors measures index and ETF returns over 1–5 days.
  - Minervini and Covel measure multi-week to multi-month moves in leaders and trends.
  - The bot keeps them in separate sleeves with separate exits, which is right.
  - Do not let Claude apply Connors' "don't buy breakouts" to sleeve C, or trend logic to sleeve B.
- **Stops.**
  - Connors: stops hurt short-term mean reversion.
  - Minervini and Covel: stops are essential for trend and breakout trading.
  - Sleeve-specific stop policy (already in `risk_policy.yaml`) is the right structure. B's stop should stay wide.
- **Paper trading.** Minervini warns it can give false confidence. Keep the bot's paper results separate from
  any claim about live readiness, and model costs and slippage conservatively.

## 6. Priority list of proposed changes
1. Sleeve B: signal before the close and fill market-on-close, or at least backtest the next-open fill against
   the tested on-close fill. (Largest source mismatch.)
2. Sleeve C: add a VCP proxy filter, and compute RS against SPY or a broad universe rather than the 40-name peer list.
3. Sleeve A: if the GEM blend is enabled, fix the SPY notional clip (30% ETF cap) and make vol scaling of the two
   halves consistent.
4. Sleeve B: make the time stop and exit rule configurable (SMA5 versus RSI(2) > 70). Test without the 10-day
   time stop.
5. Sleeve C: set `pct_above_52w_low` to 0.30; add a breakeven stop at +2R; add a losing-streak size cut.
6. Sleeve B: add cumulative RSI and Double 7s as extra triggers. Reconsider the halving of B in "bull_volatile"
   regimes while SPY is above its 200-day.
7. Sleeve D: test a less churny exit (channel low instead of midpoint). Consider adding non-crypto trend markets
   for diversification.
