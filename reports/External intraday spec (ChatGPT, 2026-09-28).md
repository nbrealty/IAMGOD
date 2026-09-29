# External intraday spec (from ChatGPT, 28 Sept 2026)

The owner pasted this spec into the operations session on 28 Sept 2026. It is an **input for the minute-trading session**,
not an instruction that overrides `MINUTE_TRADING.md`, `reports/Why day traders lose.md` (MT-G rules) or the owner's
decisions. Where it is stricter, it wins; where it is looser, the stricter existing rule wins.

## Assessment (operations session)

- **References:** all six DOIs resolve to real journal articles (checked 28 Sept 2026). The rule set itself says it is
  original and unvalidated; the papers support *investigating* these ideas, not these exact thresholds.
- **Adopt now (execution and integrity, sections 2, 7, 8, 9):** explicit order states and partial-fill protection;
  Alpaca bracket children activate only after the parent fills completely; a cancel request is not a cancel;
  entry filters never block exits; log every rejected candidate with an enumerated reason; missing event calendar =
  UNKNOWN, not "no events"; the two cost conventions (never subtract spread twice); ablation of every filter;
  day-block bootstrap; every trial counts. Session loss trigger 0.50% (stricter than MT-G18's 1%).
- **Test in the backtester as new pre-registered variants:** ORB_MOMENTUM_V1 and VWAP_REVERSION_V1. They add many
  thresholds (ER20, RVOL5, Slope5, chase cap, 3-minute progress test), so each one counts toward the MT-G7 trial
  count. Holds of 3 to 10 minutes put costs at a large share of the typical move, so the pessimistic-cost result
  decides. Shorts stay off unless the owner enables them.
- **Data mismatch to handle:** live real-time data on the free plan is IEX only (a small slice of volume), while
  history is SIP. RVOL5 and quote checks must use the same coverage in history and live (the spec says so too),
  so either use IEX-only history for these features or a paid SIP feed. Do not mix them silently.
- **Defer:** CROSS_MARKET_FORECAST_V1 needs a frozen, audited model and synchronized reference data; it is a
  separate research project, not a V1 module.
- **Do not build:** OFI_CONFIRMATION_V1. It needs sequenced order-book events and a delay far below what a cloud
  session gets over REST and websockets; the cited papers say the signal lasts only a few price changes.

---

## The spec as pasted

Claude handoff: intraday strategy add-ons, version 1

Prepared 28 September 2026. Purpose: add independently testable strategy modules and shared controls to the user's existing trading application. Do not replace the application, introduce a new stack, or assume what is already implemented.

### 0. Implementation mandate and evidence boundary

First inspect the existing strategy interface, data adapters, execution/order state machine, risk controls, tests, and configuration. Produce a capability map identifying reusable components and missing dependencies. Implement only the smallest compatible changes. Preserve stricter existing safeguards. Do not change live-trading permissions, API credentials, instruments, or existing production strategy settings.

This is a proposed research specification, not a tested profitable system, a literal replication of a paper, or evidence of a universal "top 1%" trading method. All numerical defaults below are hypotheses for controlled testing. Recent peer-reviewed papers support investigating cross-market information, order flow, execution costs, and latency; they do not establish the profitability of these exact combined rules. The VWAP-reversion module is explicitly an experimental baseline. The cited opening-range study is older and market-specific.

Working scope: liquid US stocks and unleveraged ETFs, regular continuous trading, completed one-minute bars, and executable bid/ask quotes. This scope has NOT been confirmed by the user. Do not silently translate it to futures, options, leveraged ETFs, or crypto. Those require different sessions, multipliers, costs, margin, and shorting/funding assumptions. New modules are research-only and disabled in live mode by default. Enable research runs separately rather than automatically trading all modules together.

Do not replace missing fields with invented values. Emit DEPENDENCY_UNAVAILABLE and identify the missing dependency. Bar-only data can support preliminary signal research but not claims about executable performance.

### 1. Shared definitions

Let t identify the most recently completed, actually received one-minute bar. C, H, L, V denote close, high, low, and volume. All features use only information received by decision time. A bar ending at 10:01 is not available before 10:01 plus its actual publication/receipt delay. Do not use later corrections in replay unless the correction was available at that point.

Use an exchange calendar for session boundaries, holidays, daylight-saving time, and early closes. Times below are elapsed minutes from the scheduled regular-session open, not computer-local timestamps. No synthetic bars for missing observations. Store both exchange and receive timestamps and explicit data-source identifiers.

**VWAP.** Prefer trade-based regular-session VWAP: sum(price * trade_size) / sum(trade_size). Reset at session open. Use the feed's eligible-trade rules consistently in history and live operation. If only bars exist, use sum(((H+L+C)/3)*V)/sum(V) and label the result BAR_VWAP_PROXY. Do not call that exact trade-level VWAP. Zero cumulative volume makes the feature unavailable.

**A: ATR14.** Use the simple arithmetic average of the last 14 completed one-minute true ranges. TR_t = max(H_t-L_t, abs(H_t-C_(t-1)), abs(L_t-C_(t-1))). For the first regular-session bar, define TR=H-L, explicitly excluding the overnight gap. Require sufficient same-session observations. This simple-average convention is deliberate; do not silently substitute Wilder smoothing.

**RVOL5.** Sum volume in the latest five completed regular-session minutes. Divide by the median volume in the same elapsed five-minute window over the previous 20 eligible sessions. Require all 20 historical observations and a positive denominator. Do not include the current day in that historical denominator. Use the same venue/consolidation coverage for current and historical volume.

**ER20: directional efficiency.** ER20 = abs(C_t-C_(t-20)) / sum(abs(C_j-C_(j-1)), j=t-19,…,t). This requires 21 completed closes. A zero denominator gives ER20=0, but does not override other zero-volatility/data-quality blocks. ER measures how directly price moved, not profitability.

**Slope5.** Slope5 = (VWAP_t - VWAP_(t-5)) / A_t. A must be positive.

**Quote and price units.** mid=(bid+ask)/2; spread=ask-bid; spread_bps=10000*spread/mid. Require positive, uncrossed quotes from the intended data source. Read tick size and lot size from the instrument metadata; never hard-code a one-cent tick for every instrument.

**R and cost conventions.** For a long, E is the actual average entry fill, S the initial stop, and D=E-S. For a short D=S-E. One price-risk unit is D; initial dollar risk is quantity*D before gap/slippage/fees. Keep initial D immutable for performance reporting.

Maintain two distinct cost conventions:

1. Midpoint forecasting: subtract entry half-spread + expected exit half-spread + extra slippage/impact + fees + applicable borrow/funding from a midpoint-to-midpoint forecast.
2. Filled P&L: actual proceeds minus actual acquisition cost, minus explicit charges. Spread and price slippage already embedded in fills must NOT be subtracted again.

The geometry filter "distance to target >= 3 * estimated round-trip cost per share" is a conservative screening rule, not an expected-return estimate. Target distance is not a forecast of profit.

### 2. Shared entry eligibility

Apply these checks to NEW risk only; they must not prevent necessary exits or cancel existing protection.

- Completed and received input data; positive prices/volumes where required; no unresolved gaps or unsynchronized reference series.
- Quote age <=2 seconds and spread <=5 bps as initial research settings. Replace only through a logged, validated configuration change; these are not universal market constants.
- Instrument tradable; session eligible; no halt or active price-band restriction that prevents the proposed order. Broker permissions, buying power, position limits, and instrument rules must pass.
- New-module short entries OFF by default. Enable only after explicit approval and a working borrow/shortability/fee capability. Never use leveraged ETFs as an automatic substitute.
- No new entry inside the last 20 session minutes. Initiate scheduled liquidation of these intraday positions five minutes before close. Halts can prevent liquidation: record the exception and alert rather than mark the position flat.
- Configured high-impact event blackout: five minutes before through ten minutes after the event, inclusive. This is a proposed exclusion experiment, not a profitability finding. Missing/stale event-calendar data is UNKNOWN, not "no events." Do not claim this protection exists without a validated calendar. Event-filtered deployment requires that dependency.
- One position owner per symbol. Include pending orders in exposure and risk reservations. Two strategies agreeing do not create permission to double size. On contradictory simultaneous proposals, default to NO_ENTRY and log STRATEGY_CONFLICT.
- Baseline order participation <=1% of the last completed minute's observed volume, in addition to other limits. This is only a rough capacity screen, not proof of available liquidity.

Each module may run in its own isolated research ledger. Compare combined portfolio arbitration separately, including costs.

### 3. Strategy ORB_MOMENTUM_V1

**Hypothesis and evidence.** An unusual move beyond the opening range may continue when current price action and participation are directional. This particular filtered rule set is original and unvalidated. "Assessing the profitability of intraday opening range breakout strategies" (Finance Research Letters, 2013; DOI 10.1016/j.frl.2012.09.001) studies a different ORB definition using crude-oil futures and reports important subperiod instability. It does not validate these equity thresholds.

**Setup.** Freeze ORH=max(high) and ORL=min(low) over the first 15 regular-session one-minute bars. Freeze breakout buffer b=max(one tick, 0.10*ATR14 at the completion of that opening range). Do not recompute the opening range with later prices.

New signals are eligible from elapsed minute 21 through minute 120, after all warm-up requirements are met. The entire account/session eligibility layer still applies.

**Long entry.** All conditions must hold:

1. Previous completed close <= ORH+b and current completed close > ORH+b. This is a fresh crossing, not permission to re-enter every minute above the range.
2. Current close > current VWAP, Slope5>0, and ER20>=0.35.
3. RVOL5>=1.50.
4. Freeze A at signal creation. Reject if the worst allowed entry price is greater than ORH+0.75*A; do not chase a distant breakout.
5. Initial stop S=ORH-0.25A, rounded outward to a valid tick. Use the worst permitted entry fill to check planned risk. D must be positive, at least twice the current quoted spread, and no larger than 1.50A.
6. Planned target = entry + 1.50D. Target room must be at least 3*estimated round-trip cost per share. This filter does not substitute for actual expectancy testing.
7. Risk sizing, exposure, execution, and availability checks must pass.

Submit through the existing validated execution adapter. A marketable limit order with an explicit maximum price is the preferred candidate for testing, not a fill guarantee. Use IOC only when supported and correctly tested. Cancel unfilled entry intent after two seconds in this baseline; never resubmit while cancellation/execution state is unresolved. A new price requires revalidation, not automatic chasing. Signal expires no later than 60 seconds after generation or on an invalidating state change, whichever comes first.

Recompute D and the target from actual average fills, without widening the structural stop. Reserve risk using the worst allowed fill price before submission. Protect any partially filled quantity immediately; do not wait for the whole parent order to fill. Hold timer starts at the first fill.

**Exits.** Exit at the first applicable event:

- Protective stop.
- Target at E+1.50*D, using executable prices and a realistic order-fill model.
- A completed close falls below ORH: the breakout has failed by this definition.
- At three minutes from first fill, the maximum executable bid observed since entry remains below E+0.25*D: no progress.
- Ten minutes from first fill: time exit.
- Portfolio emergency or scheduled session liquidation.

No automatic break-even stop, partial profit-taking, trailing stop, averaging down, or overnight conversion in V1. Those are separately versioned experiments, not discretionary modifications.

**Short mirror, only when independently enabled.** Fresh cross below ORL-b; close<VWAP; Slope5<0; same ER and RVOL thresholds. Do not enter below ORL-0.75A. Stop=ORL+0.25A. Target=E-1.50D. Failure exit is a completed close above ORL. The three-minute progress test uses minimum executable ask <=E-0.25D. Borrow and short-specific costs must be included.

**Reset and failure modes.** Maximum one filled entry per direction per symbol per session for this strategy. After a completed trade, use a five-minute cooldown, without overriding the one-entry limit. Failed breakouts, news repricing, late fills, adverse spreads and regime changes can make the strategy lose. No filter is assumed beneficial until ablation-tested.

### 4. Strategy VWAP_REVERSION_V1

**Hypothesis and evidence status.** A temporary excursion might partially reverse when the local market remains range-like. This is an experimental baseline, NOT a recipe established by the reviewed recent papers. VWAP is an average transaction-price benchmark, not a guaranteed fair value or an attraction force.

**Eligible environment.** Require at least 60 completed regular-session bars. New entries end 20 minutes before close. Require ER20<=0.25, abs(Slope5)<=0.25, and 0.70<=RVOL5<=1.30. These research thresholds define the current state; they do not use the eventual day's high/low or future trend labels.

Let sigma60 be the sample standard deviation of the latest 60 completed closes. Require sigma60>0. The score (C-VWAP)/sigma60 is a distance measure, not a claim of Gaussian tail probabilities.

**Long setup, confirmation and entry.** At setup bar u, require C_u <= VWAP_u - 2*sigma60_u. Freeze Vstar=VWAP_u, sigmastar=sigma60_u, and Astar=ATR14_u. Move to ARMED, but do not buy yet.

During the next three completed bars only, trigger on the first close crossing upward through Vstar-1.50*sigmastar, with current close>previous close. Recheck range eligibility and shared eligibility at entry. If no valid trigger appears, expire the setup; do not extend the waiting window.

Let Lstar be the minimum low from setup u through the trigger bar. Set structural stop S=Lstar-0.25*Astar, rounded outward. Target is frozen Vstar, not a continuously moving future VWAP. Reject when target<=worst allowed entry price, D<2*spread, D>1.50*Astar, target distance / D <1.25, or target room<3*estimated round-trip cost per share.

Use the same capped, timeout-controlled execution and partial-fill protection as ORB. Revalidate reward/risk at the actual fill; an entry cap must prevent an adverse fill from making the permitted ratio fail.

**Exits.** Exit on the protective stop, executable arrival at the frozen target, ten minutes from first fill, or two consecutive completed bars failing the range-eligibility test. Global risk and session liquidation override these rules. A position is not permitted to morph into a trend trade when the reversion premise fails.

No averaging down. No widening stops. No repeated entries while the initial setup remains armed or an entry is pending.

**Short mirror, only when enabled.** Arm above Vstar+2*sigmastar, trigger the first downward close-cross of Vstar+1.50*sigmastar with a falling close, and place stop above the highest high of setup-through-trigger plus 0.25*Astar. Target is Vstar. Reverse quote sides and include borrow costs.

Maximum two filled entries per symbol/session across both directions, with a five-minute cooldown after each completed position. Main failure mode: a large deviation is genuine repricing rather than a temporary excursion. The regime filter is only a hypothesis and can fail.

### 5. Strategy CROSS_MARKET_FORECAST_V1

**Hypothesis and evidence.** Lagged information from related markets may improve prediction beyond an instrument's own history. Aleti, Bollerslev and Siggaard (Management Science, 2025; DOI 10.1287/mnsc.2023.01657) report out-of-sample intraday ETF performance under their cost model using a large factor universe. Their accessible author manuscript uses 15-minute returns. The smaller input set below is an adaptation, not their full factor-zoo replication.

Implement this module only when a frozen, auditable forecasting model and synchronized reference data exist. Reuse the app's existing validated model interface. If unavailable, expose an unmet dependency rather than manufacturing a probability or handwritten confidence score.

**Inputs and model.** Predeclare a small reference universe: the traded instrument, a broad market reference and an appropriate sector reference when relevant. Start with trailing 1-, 5-, 15- and 60-minute returns, 15-minute realized volatility, current spread, time of session, and volume relative to the historical same-time window. Avoid duplicate/self-reference features for ETFs. Fit scalers and parameters on training data only.

Compare the same simple regularized regression with and without cross-market features. No LLM-invented weights such as "sector strength 40%, RSI 30%". No use of a related asset's contemporaneous or future return if it was not available at decision time. Require at least 60 same-session minutes of needed history.

Baseline forecast horizon h=15 minutes. Evaluate new entry opportunities every five minutes, using only completed data. Parameterize other horizons as separate experiments.

**Cost-aware trigger.** Let mu be the predicted gross midpoint return over h in basis points. Let c_long and c_short be direction- and size-specific estimated total round-trip midpoint-based costs, including realistic execution delay and impact assumptions. Let buffer(c)=max(1 bp, 0.50*c).

Long candidate if mu>c_long+buffer(c_long). Short candidate if -mu>c_short+buffer(c_short), subject to independent short permission. Otherwise NO_ENTRY.

The buffer is a proposed safety margin, not a statistical confidence interval. mu-cost is a forecast margin, not a guarantee or a validated estimate of this stopped strategy's actual expectancy. Actual stops and fills alter the payoff distribution: evaluate the whole policy separately.

**Position and exits.** Freeze A=ATR14 at signal. Initial long stop is E-2A; short stop is E+2A. Reserve risk using the entry cap and outward-rounded stop. No profit cap in V1. Exit on stop, 15 minutes after first fill, portfolio emergency, or session liquidation. Ignore later entry predictions while this position remains open; do not flip or extend the timer automatically. Same instrument ownership and pending-order rules apply.

**Required evidence before promotion.** Cross-market features must improve the fully executed policy over the own-history baseline on locked chronological data. Evaluate forecast calibration using earlier validation observations and its deterioration prospectively. Never train, calibrate and claim performance on the same final sample. A related market moving first does not establish that the target must "catch up." This can fail through changing relationships, stale quotes, different fundamentals, or complete price adjustment before order arrival.

### 6. Optional OFI_CONFIRMATION_V1

This is an execution/confirmation experiment, not a required fourth strategy. Kolm, Turiel and Westray (Mathematical Finance, 2023; DOI 10.1111/mafi.12413) find useful order-flow representations, but useful horizons can be only about two average price changes. Ait-Sahalia and colleagues (online 2025, Management Science issue September 2026; DOI 10.1287/mnsc.2022.02435) directly investigate degradation with delay.

Requires sequenced quote/book events with clear feed/venue semantics. OHLCV alone cannot supply cancellation rates, queue position or event-level flow. Static book imbalance is not OFI. Do not relabel a snapshot volume ratio as message-based order flow.

For sequenced best-bid and best-ask updates n, define price p and displayed quantity q on each side:

e_n = 1[p_bid,n >= p_bid,n-1]*q_bid,n - 1[p_bid,n <= p_bid,n-1]*q_bid,n-1 - 1[p_ask,n <= p_ask,n-1]*q_ask,n + 1[p_ask,n >= p_ask,n-1]*q_ask,n-1.

Aggregate e_n over completed one-second intervals. A simple research normalization divides by the mean top-of-book depth in that interval; zero depth disables the feature. This measures changes in displayed best quotes, not a decomposition into cancellations and executions. That decomposition requires appropriate message data.

Candidate confirmation: for a proposed long momentum entry, positive OFI in at least two of the previous three completed one-second intervals; negative for shorts. Compare against no OFI filter with every other rule held fixed. For reversion, do not automatically apply the same filter or infer a reversal from imbalance alone.

Measure event-to-action delay. Disable this feature when the delay exceeds the useful signal lifetime found on earlier validation data. Reject sequences with gaps, stale states or incompatible venue aggregation. Do not wait indefinitely for confirmation and then enter a stale original signal. Thresholds, interval lengths and useful lifetimes are experimental.

### 7. Shared risk overlay: proposed research defaults

These are nominal risk budgets, not guaranteed loss caps or account-specific advice. Preserve any stricter existing controls. Changes to production limits require explicit approval.

- Per-position initial planned risk including modeled stop-execution buffer: 0.10% of min(session-start equity, current equity).
- Aggregate remaining stop-risk budget including pending entries: 0.30% of equity base. Count downside from CURRENT liquidation value to stop, not merely entry-to-stop loss; do not net away correlated exposures because some stops are at entry.
- Correlated instrument-group risk budget: 0.20% of equity base; use an explicit group map initially rather than assuming low historical correlation means no shared shock risk.
- Maximum symbol notional: 10% of equity base; maximum gross notional: 100% of equity base, with no added leverage for the new research sleeve.
- Session loss trigger: 0.50% of session-start equity, including realized and executable mark-to-market unrealized P&L and accrued charges. Adjust equity comparisons for external transfers; deposits do not repair trading losses. Reaching the trigger cancels pending entries and initiates controlled liquidation. Do not reactivate automatically that session.
- Three consecutive completed losses in one strategy: pause that strategy's new entries for 20 minutes and perform a data/execution check before resuming. This pause is a research/operational rule, not evidence that three losses predict another loss.

Sizing for linear per-share costs:

q_risk = floor(B / (abs(worst_entry_price - stop) + adverse_stop_fill_buffer_per_share + applicable_fee_allowance_per_share)).

Final quantity is the smallest quantity allowed by this risk budget, symbol/gross/group limits, buying power, lot size, short availability, volume participation, and actual executable liquidity modeling. Account for fixed/minimum fees with a monotonic quantity solver, not a constant per-share fiction. Skip if less than one tradable lot. Never increase quantity to reach a desired dollar profit.

A stop is not a guaranteed fill price. Stop-market orders can fill worse, stop-limit orders can fail to fill, and a halted market can prevent any immediate exit [O1]. Risk limits must be supplemented by outage, halt and gap procedures.

### 8. Execution integrity and module interface

Use the existing interface where possible. A logical signal should identify strategy_id, version, symbol, side, input/decision timestamps, expiry, required data, entry cap, initial stop, target or time horizon, estimated costs, intended risk, and machine-readable reasons.

Do not populate expected_net_return or probability fields for deterministic strategies unless a separately validated estimator supplies them. Do not substitute target distance for expected return. Include explicit null/unknown states.

Required order states: FLAT, ARMED, ENTRY_PENDING, PARTIALLY_FILLED, OPEN, EXIT_PENDING, COOLDOWN and DISABLED, mapped to existing equivalents. Persist owner and idempotency keys. Reconcile broker positions/orders after restarts before new risk is allowed. A cancellation request is not a cancellation acknowledgment. Never mark an order filled without a fill event.

Match the execution adapter's true stop trigger semantics in replay. A bid-triggered synthetic stop is not automatically identical to a broker stop triggered by last trade. Record the difference rather than silently changing semantics. Protect partial fills. Verify how the current broker activates bracket children; do not assume protection begins on the first partial fill. Alpaca's published bracket documentation, for example, describes activation after the parent is completely filled and warns that both exit orders can fill before cancellation during extreme conditions [O3].

A shutdown must not blindly cancel protective exits. Distinguish cancellation of new-entry risk from managed liquidation of existing risk. At disconnect, enter the documented broker-aware recovery procedure and alert; software cannot guarantee flattening without venue access.

Every rejected candidate gets a reason: DATA_STALE, INPUT_GAP, SPREAD_TOO_WIDE, INSUFFICIENT_HISTORY, EVENT_CALENDAR_UNKNOWN, EVENT_BLACKOUT, COST_TOO_HIGH, CHASE_LIMIT, INVALID_STOP, TARGET_TOO_CLOSE, MODEL_UNAVAILABLE, RISK_LIMIT, SESSION_LIMIT, STRATEGY_CONFLICT, ORDER_STATE_UNCERTAIN, SHORT_UNAVAILABLE, or another explicit enumerated cause. Log all candidates, not only fills or winners.

### 9. Validation and acceptance tests

Implement deterministic tests before performance optimization:

1. Appending future data cannot change historical decisions.
2. Features cannot read an unfinished bar, later quote or later correction.
3. Session resets, early closes and daylight-saving boundaries behave correctly.
4. Missing inputs block dependent modules; an unavailable OFI feed is never replaced with fabricated values.
5. Opening range freezes at minute 15; a crossing produces one idempotent intent.
6. Reversion must arm before triggering, expires after three bars, and retains its frozen target.
7. Worst-entry-price sizing respects caps; stop widening and averaging down are impossible in V1.
8. Costs are charged once; losses and missed fills remain in the ledger.
9. Partial fills, rejected orders, delayed cancels, duplicate callbacks, simultaneous stop/target events and restarts are handled without orphan or accidental reverse positions.
10. Entry filters never block required exits.
11. A daily loss trigger cannot be bypassed by switching strategy, model, prompt, account display, or session-reset code.
12. No final-test observation is accessible to training, feature selection or strategy generation.

Backtests must use chronological data with label-overlap purging at split boundaries and fitting of all preprocessing on the training subset. Apply a common time split across securities. Use realistic post-decision fills, measured delays and cost assumptions. For OHLC bars touching both stop and target, use finer event data; absent that, apply a documented conservative ordering and show sensitivity. If bar data cannot establish whether entry preceded a price touch, do not pretend the sequence is known.

Test each strategy alone, then every proposed filter by removing only that filter, then the combined arbitration policy. All trials count, including unsuccessful features, prompts and configurations. Log code/config/data hashes, split dates, seed, costs and trial count. Repeated final-test inspection invalidates its untouched status.

Report net expectancy, average gain/loss, trade count, turnover, fill/cancel rate, daily-return uncertainty, drawdown, worst day, tail losses, parameter sensitivity, and performance by intended market state. Resample blocks of days rather than treating correlated minute observations as independent. Positive average P&L with a wide interval is inconclusive, not certified alpha.

Stress costs at 1.5x and 2x, empirical tail delays, thinner liquidity, partial/missed fills, and outages. These stress multiples are proposed tests, not paper-certified standards. Examine dependence on a few days without automatically rejecting an event-specific strategy for being event-specific.

Paper trading checks behavior but does not prove executable profitability. Alpaca explicitly excludes queue position, latency slippage and market impact from its paper environment, among other limitations [O2]. Simulate missing frictions independently. Any tightly limited live execution experiment remains a separate, explicitly approved decision; no automated promotion from backtest to real money.

### 10. Output required from Claude

Return the capability map; minimal proposed changes; implemented strategy/config versions; reuse notes; data dependencies; deterministic test results; reproducible performance artifacts when actually run; ablation results; unresolved assumptions; and an explicit statement that live permissions were left unchanged. Never invent performance statistics or claim a backtest ran when it did not.

### Research and operational references

- [R1] Aleti, S.; Bollerslev, T.; Siggaard, M. (2025). Intraday Market Return Predictability Culled from the Factor Zoo. Management Science 71(9), 7731–7751. DOI: 10.1287/mnsc.2023.01657.
- [R2] Kolm, P. N.; Turiel, J.; Westray, N. (2023). Deep order flow imbalance: Extracting alpha at multiple horizons from the limit order book. Mathematical Finance 33(4), 1044–1081. DOI: 10.1111/mafi.12413.
- [R3] Briola, A.; Bartolucci, S.; Aste, T. (2025). Deep limit order book forecasting: a microstructural guide. Quantitative Finance 25(7), 1101–1131. DOI: 10.1080/14697688.2025.2522911.
- [R4] Ahabchane, C.; Cenesizoglu, T.; Grass, G.; Jena, S. D. (2024). Reducing transaction costs using intraday forecasts of limit order book slopes. Journal of Forecasting. DOI: 10.1002/for.3164.
- [R5] Assessing the profitability of intraday opening range breakout strategies (2013). Finance Research Letters 10(1), 27–33. DOI: 10.1016/j.frl.2012.09.001.
- [R6] Ait-Sahalia, Y.; Fan, J.; Xue, L.; Zhu, X. How and When Are High-Frequency Stock Returns Predictable? Management Science 72(9), 7792–7815. DOI: 10.1287/mnsc.2022.02435.
- [O1] US SEC, Investor.gov, Types of Orders.
- [O2] Alpaca documentation, Paper Trading.
- [O3] Alpaca documentation, Placing Orders / Bracket Orders.
