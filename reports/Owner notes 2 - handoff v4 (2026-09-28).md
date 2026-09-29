# Owner notes 2: handoff v4, remaining gaps and specification reconciliation (28 Sept 2026)

The owner shared this file with the minute-trading session on 29 Sept 2026 ("take anything that's useful"). It is an **input**,
not an instruction that overrides `MINUTE_TRADING.md` or the MT-G rules: where it is stricter it wins, where it is looser the
stricter existing rule wins. It says itself that it audits the *written* handoffs, not our code.

## Verdict (minute-trading session, 29 Sept 2026)

Two independent helpers each mapped the handoff onto the live bot's code and tests, ran the 376 scalp tests (all pass) and
built scratch experiments for the fixtures. Their full reports are in `Owner notes 2 - capability reports/`. They agree on the
main points. **No blocker for the paper session.** Two small gaps were worth fixing now; most of the rest is already covered,
does not apply (the bot has no model, no database and no tax logic), or needs your decision.

| Handoff section | Verdict |
|---|---|
| A. Capability report | Done twice (about 110 requirement rows each, every status backed by a test name and command). The two reports differ a little on fixture statuses (helper A: 2 tested, 10 unverified, 7 missing, 5 not applicable; helper B: 1, 12, 4, 6, plus 1 conflict). The gap is judgment about what counts as "tested"; both are kept. |
| B. Hard controls vs learnable policies | **Adopt as vocabulary.** Every current rule is a HARD control or a BASELINE rule (the three setups, frozen by code hash). No learnable policy and no trend/range router exists yet (V4-01 not applicable). A learned policy would need its own envelope and the MT-G5 to G7 gates, which are not built. The class table is in the capability reports (section 4). |
| C. Every eligible minute in the dataset | **Missing in the live bot (V4-03: 780 eligible minutes, 0 decision lines). Adopt for the Reader and forward logging** (synthesis 7.3), not for the live bot, which only records its own decisions. |
| D. Calibration | Not applicable now (no probabilities). Adopt as a rule for any future model: name the target, horizon and cost convention; score on earlier data only; report the selected subset. |
| E. Simulator audit | **Partly done.** A hand-computed round trip (V4-08) now runs as a repo test and matches the app to the cent. Known limits of the simulator, unchanged: it credits no displayed-liquidity limit (V4-09) and has no joint model of fills and later prices (V4-10). Real paper fills are the test of both. |
| F. Atomic risk, recovery | **Two gaps fixed** (below). One position slot and one thread already stop two entries in the same tick (V4-12, now a repo test, also while the first order is unfilled). No cash reservation for pending orders exists; it is safe with one slot. No database exists and none is needed (a file lock plus the broker as the authority). Unwritable or full state disk still stops the bot at its first journal write and can block the 15:50 exit (the outside watchdog then flattens): check free disk, not fixed. A position with ids the code cannot parse is flattened and halted, not adopted (safe, not a compatible rollback: V4-16). |
| G. AI permissions | The live bot has no AI. The handoff's G-1 (broker keys kept away from the research/code agent) **conflicts with your decision 1** (the SCALP keys live in this agent's environment); it needs your decision. Injection fixtures (V4-17) are unverified. |
| H. Evaluation plan | **Adopt as guidance** for Wave 1 and the 20/60-session reviews: fixed schedule, a stop-spending rule, exposure attribution (MT-G5(b) already requires beating exposure-matched SPY), inconclusive counts as a result. |
| I. Data rights, tax, conduct | **Data rights register done** (`reports/Chart reading research/Data rights register.md`). Urgent finding: **the GitHub repository is public**. Alpaca's terms are silent on sending market data to an AI model. Cboe and Yahoo are restricted. Tax: no tax logic; paper account (V4-22 not applicable). Conduct: the bot sends only limit orders of 1 share and cannot flood or spoof; self-trade rejection (V4-23) is untested. |
| J. Fixtures V4-01 to V4-24 | V4-08 and V4-12 are now tests. V4-14 (two active runners) is mitigated by the new lock. The others are unverified, missing, or not applicable; each is listed with a sketch in the capability reports. |
| K. Do not add more named chart strategies | Agreed. Nothing was added. |

## What changed in the bot (tested, reviewed by two independent reviewers)

1. **Single-instance lock.** A second `run` of the same mode on the same state folder now refuses to start (exit 2) before it
   touches anything. Before, a second copy made the two bots kill each other and set HALT until the next day.
2. **Engine alerts reach the alerts file** (and stderr) as well as the journal (kill switch, halts, daily stop, "close by hand").
3. New tests in `tests/test_scalp_live_round5.py`: the lock (same process, other process, freed on death or error), alert
   routing, the V4-08 hand-computed round trip and the two V4-12 same-bar cases.

The risk hash is unchanged (`runner.py` is not one of its files).

## Owner decisions this raises

1. **Repository visibility** (public today). Please check GitHub Settings, General, Danger Zone. I changed nothing.
2. **G-1:** keep the SCALP and RULES key names out of the agent's environment? That would mean the bot runs somewhere else.
3. **I-4:** "unknown data permission means switch the dependent path off" would switch off the IEX/SIP feed the bot uses. Alpaca's
   free plan is meant for this, but the register lists a document conflict to clear with Alpaca in writing.
4. **Where the watchdog runs.** It shares the machine with the bot; if the machine dies nothing flattens and a 1-share position
   could sit overnight (the next start would sell it). Hosting is "not recorded".
5. **Who is told, and how fast** (handoff F): today alerts go to a file that I read on scheduled check-ins.

## Conflicts (do not adopt as written)

Learned or LLM policies producing entries (MT-G29 to G32); extra symbols or order-size ranges on the live account (MT-G23, MT-G14);
a database, tax lots or calibration machinery for a paper bot; a scanner universe as anything but research.

---

## The handoff as shared

Claude handoff v4 — remaining gaps and specification reconciliation

Prepared: 28 September 2026, America/New_York.
Companions: Claude_Trading_Strategy_Addons_v1.md; Claude_Trading_Addendum_v2.md; Claude_Evidence_and_AI_Outperformance_v3.md.

Status and scope

This is a gap audit of the three written handoffs, not an audit of the application’s code, financial accounts, live deployment, or profitability. The user’s actual market, broker, data feed, architecture, and account profile have not been established in these materials. Retrieve these from existing code/configuration and authoritative account/adapter metadata without exposing secrets. Do not silently assume the U.S.-equity example applies.

No new strategy has been backtested, no test below has been executed by preparing this file, and no production change is authorized. This addendum clarifies research contracts and specifies verification tasks. Reuse the existing application; do not rebuild its stack or introduce components that already exist. Preserve stricter existing safeguards and all current live permissions. A profitable research result is not deployment authorization.

A. Required first deliverable: a code-backed capability report

For every requirement, return:

requirement_id
status: IMPLEMENTED_AND_TESTED | IMPLEMENTED_UNVERIFIED | MISSING |
        NOT_APPLICABLE | CONFLICT
code_reference: actual path + symbol/function
configuration_reference: actual key and effective setting, with secrets redacted
test_reference: actual test + command + result artifact
applicability: market, broker, feed, account and strategy policy IDs
remaining_assumption
minimal_proposed_change

A checklist answer without an implementation reference is not IMPLEMENTED_AND_TESTED. A test that exists but was not run is NOT_RUN. Conflicting assumptions are reported, not silently resolved in whichever direction yields a better backtest.

Record the actual decision frequency, target horizon, entry-expiry policy, maximum holding time, instrument multipliers, tick/lot rules, supported order types, fee schedule provenance, data entitlements, and broker account restrictions. These are different concepts and must not share one vague ‘timeframe’ setting.

B. Reconcile safety controls with learnable trading policies

Ambiguity found

V2 defines a trend/range router using human-selected ER20/VWAP thresholds and optional persistence. V3 allows learned policies that need not resemble human chart patterns. Applying the router universally could unintentionally constrain the learned candidates to the human rules they are meant to challenge.

Resolution

Classify each effective rule:

1. HARD_CONTROL: approved capital/exposure limits, authentic data availability, account and market permissions, verified order state, security, protective-exit integrity, and experiment-access boundaries. Research optimizers cannot alter these controls.
2. BASELINE_POLICY_RULE: the ORB, reversion and retest definitions and their version-specific entries/exits, trend thresholds, volume filters, selection policy, and optional persistence. Preserve exact versions for fair comparisons.
3. LEARNABLE_POLICY: features, nonlinear interactions, statistical regime representations, abstention and action choices, horizons, and exit choices within a separately approved research-policy envelope. Such variation is not a change to the frozen baseline or permission to relax a HARD_CONTROL.

Scope each rule to explicit policy IDs. A learned strategy can test trading during a human-defined NEUTRAL state only when hard gates pass and its predeclared research scope permits it. It cannot bypass genuine missing-data, halt, account, event, or risk restrictions. Keep versions with and without experimental shock/regime filters distinct.

Do not let ‘last document wins’ or an LLM’s prose override the effective configuration. Reject unresolved conflicts at startup. Existing production behavior must remain unchanged unless separately approved through the established release process.

A learned exit policy is not permission to modify stops on an already-open baseline position. Position ownership and the entry-time management contract persist until completion.

C. Remove the hidden human ceiling from opportunity sampling

V3 already requires losing, rejected and unfilled opportunities. Refine the definition of ‘opportunity’: it must not mean only timestamps when a human strategy fires.

For the matched-information experiment, define a common point-in-time universe and decision grid before evaluation. For a minute-based research experiment, this can be every eligible completed, received minute for each already-authorized instrument. Other grids require separate versions.

At each eligible decision point, record the available state, which human strategies fired (possibly none), feasible actions, relevant costs, and why hard gates allowed or rejected new risk. Include ordinary minutes and no-entry actions. Predictive labels can be calculated at those points if the required future evaluation observations exist; executable outcome labels require the stated fill model and must be marked observed, modeled, or unknown.

This does not authorize exploration with real money or claim that hypothetical orders would have filled. Trade logs alone do not establish the execution outcome of actions never taken. Do not impute unobserved fills as fact.

Keep M1 and its baseline on the same universe and data availability. An expanded scanner/universe is an additional-information/selection experiment, not an unexplained advantage given only to the AI. Track selection changes as trials. The selected top-volume universe itself may be studied separately without granting new instrument permissions.

D. Calibrate uncertainty at the decision point and after selection

Existing requirement refined

V3 mentions calibration and predictive distributions. Specify an actual evaluation contract before using probabilities to trade or size.

Every probability or interval must name its target, horizon, action/exit policy, cost convention, and calibration version. ‘80% confident’ generated in prose is not a measured event probability. P(midpoint increases) is not P(net executed trade profit > 0).

Using earlier validation data only, assess probability calibration with predeclared reliability bins, proper scores such as Brier/log loss where appropriate, and uncertainty that respects dependence. For return intervals, check observed coverage, interval width, label definition and data support. Do not turn a predictive return interval into a confidence interval for the mean edge.

Evaluate the whole eligible sample AND the subset the policy actually selects. Report important predeclared states and order-size bands when supported by sufficient data; sparse groups remain inconclusive. Fit recalibration on earlier observations; the final evaluation set is not another calibration window.

Data-shift checks should identify unfamiliar feature support, new feed/schema conditions, and deterioration of calibration or costs. Predeclare the supported range and response. Warning or NO_NEW_RISK does not disable necessary exits. A documented, already validated fallback is permitted only under its existing authorization; arbitrary substitution of another model is not.

Research leads: Gibbs and Candes (JMLR 2024) investigate online predictive intervals under distribution shifts [S1]. Bao et al. (JMLR 2025) address post-selection online predictive inference [S2]. Their publisher abstracts were checked, not a full reproduction. Their guarantees are not unconditional probabilities that a trade makes money; assumptions and target definitions must be inspected before implementation.

E. Audit the simulator independently of the strategy

Known limitation

HftBacktest’s own documentation states that replay cannot change the historical market and therefore does not represent the market’s response to the test trader; even some partial-fill scenarios remain unrealistic [S3]. This is an illustrative limitation of a replay method, not evidence that this application uses that library.

Required verification

Build a small transparent reference calculation for event sequences with hand-verifiable fills and cash flows. Do not call the production simulator’s own accounting helpers from the reference calculation. Compare cash, quantity, remaining orders, realized P&L, liquidation-value equity, explicit fees and rounding at each event. Agreement between implementations is a useful check, not independent proof that the shared assumptions are true.

Use the existing event-replay engine when possible, but verify its causal ordering, available liquidity accounting, queue assumptions, fees and model version. Repeated orders cannot each consume the same simulated displayed quantity without any accounting for intervening replenishment; conservative adjustments still do not simulate unknown reactions of other participants.

Evaluate the joint distribution of fills and subsequent prices. Passive fill probability cannot be assumed independent of the future payoff. A policy may be filled mainly on adverse moves and miss favorable ones. Model these states jointly or disclose the missing relationship; random fill deletion alone is not sufficient evidence of realistic adverse selection.

Include hand-built flat-price fixtures with positive spread/fees, rejected and never-filled orders, partial entries and exits, and liquidation after an interruption. A no-position, no-fill strategy cannot receive a trading gain. A deliberately future-informed oracle must fail information-availability tests even if it has excellent statistical scores.

Simulate a predeclared range of order sizes to assess where costs and fills invalidate scaling. Historical volume participation alone does not establish capacity. Report per-unit results and total dollars; do not multiply a small-size return linearly into an unsupported large account. Any actual-money execution experiment requires separate authorization.

F. Make portfolio risk reservations atomic; rehearse recovery

The earlier files already require pending-order risk reservations and order reconciliation. Add concurrency and fault-injection requirements rather than another high-level instruction to ‘manage risk.’

A risk check and its reservation must behave as one indivisible operation against authoritative shared state. Use the existing transactional or equivalent concurrency mechanism. Release only reconciled residual reservations; a timeout or cancel request alone does not establish that an order cannot fill.

Hand-verifiable fixture: remaining budget = $100; two simultaneous proposals each require $70. They cannot both pass based on the same old snapshot. At most the permitted subset proceeds; an unacknowledged order retains its reservation until reconciled.

Use a single authoritative execution owner or equivalently fenced leadership so a restarted or partitioned worker cannot trade alongside a replacement. Stable client IDs are useful only when the actual broker’s deduplication/query contract is respected; do not assume reusing an ID universally guarantees exactly-once submission.

Fault-inject in an isolated environment: delayed/lost acknowledgments, fill during cancel, duplicate/out-of-order events, simultaneous proposals, worker death after submission, clock discontinuity, API rate limiting, database unavailability, and a deployment rollback with open positions. Verify the expected no-new-risk behavior, continuing protection, actual broker-state reconciliation and human alert routing. Do not deliberately cause production incidents.

Define who receives a material alert, how it is acknowledged, and the approved response when no operator responds. No procedure may claim guaranteed liquidation during a halt, network outage or inaccessible venue. Reserve operational capacity for risk-reducing work where the broker/API supports it; do not generate an unbounded retry storm.

Keep rollback artifacts compatible with persisted positions and order schemas. A code downgrade that cannot understand the existing position state is not a safe rollback.

Historical failure reference: the SEC’s 2013 Knight Capital action describes deployment/control failures in the August 2012 incident [S5]. This supports testing the full release and recovery path; it does not make all broker-dealer obligations applicable to a personal application.

G. Constrain AI permissions outside its prompt

V2 already treats external content as data. Turn that principle into enforceable boundaries.

The research/code agent must not have access to live broker secrets, withdrawals, production database writes, live trading endpoints, production deployment tokens or final-test outcomes. If the broker cannot scope a credential sufficiently, keep it outside the research environment rather than declaring it ‘read only’ in a prompt.

The execution process receives validated structured intent from approved policy versions and enforces hard controls. It does not execute arbitrary tool requests, accept natural-language permission changes, or follow instructions embedded in news, a README, paper, file, model memory or tool response. Avoid needless raw account details in external model inputs and logs.

Use environment/filesystem/network permissions, allowed endpoints and actions, secret separation, immutable approval artifacts, dependency review and existing protected deployment controls. No single filter is claimed perfect. Anthropic’s May 2026 containment guidance describes why environmental controls are needed in addition to probabilistic model defenses [S4].

Test malicious-looking content only against fake credentials and harmless local test targets in an isolated environment. Expected result: no privileged action, no secret read, no permission change, and a logged rejection. Never use real secrets in a security fixture.

Pin exact model versions when available, plus prompts, tool schemas, preprocessing and code/config hashes. Record actual inputs, outputs and receipt times needed for replay. Hosted version IDs do not automatically guarantee bit-for-bit reproducibility. Undisclosed aliases or model changes require reevaluation; timeouts, malformed output, rate limits or retired models must not silently generate a stale or invented trade. Existing risk exits operate independently of model availability.

H. Explain apparent improvement and plan a test that can detect it

V3 already defines paired prospective comparisons and a minimum meaningful improvement. Refine that into an evaluation plan with a fixed review schedule or a statistically justified sequential procedure, a predeclared stop-spending condition, and a sensitivity/power analysis based on earlier pilot data and defensible dependence assumptions.

Do not promise that a universal number of trades proves an edge. Many trades in one session can be strongly dependent. Wide uncertainty is inconclusive. No decision threshold should be relaxed merely because the research budget is running out.

Add exposure attribution to the existing matched comparisons: is the difference mainly market/sector direction, time in the market, volatility, carry, concentration, additional data, lower execution cost, or incremental forecasting? Use relevant references for the actual asset class. Estimate any live exposure adjustments using prior data only. Retrospective attribution is descriptive, not proof of causality or grounds to rewrite the winning policy.

A strategy earning a genuine risk premium can be valuable. The audit must simply distinguish it from evidence of superior forecasting. Do not require every profitable model to have zero market exposure, and do not compare an intraday sleeve with overnight buy-and-hold without describing the different exposure.

Predeclare a primary objective, tail-risk constraints, incremental operating-cost hurdle, evaluation dates, all allowed selection/retraining rules, review frequency, search budget, and termination/inconclusive criteria. Research experiments that cannot demonstrate useful improvement may be retired without modifying the held-out evidence.

I. Data rights, tax records, and market-conduct gates

Data permissions

Inspect actual vendor/exchange agreements for automated/non-display usage, historical storage, research, model training, external-model processing, derived outputs and redistribution. Display access alone is not blanket permission for every use. Nasdaq’s rulebook explicitly distinguishes display/non-display use and lists automated trading among non-display examples [S6]. Different feeds, delivery arrangements, exemptions and contracts require their own review. No particular additional fee or entitlement is inferred for this unknown application.

Record source and verification date for each material entitlement. Unknown permission does not become approval; disable the dependent processing path pending clarification rather than instructing the agent to bypass restrictions.

Tax-ready records

Keep lots, actual cash flows, commissions, corporate actions and corrections exportable with stable identifiers. Separate fill-based trading P&L, operating profit and tax reporting. For U.S. securities, IRS Topic 429 explains that calling oneself a trader is not sufficient for trader tax treatment, and that wash-sale/capital-loss treatment can depend on a timely valid section 475(f) election [S7]. This is not a tax-status determination for the user. A qualified tax professional should review applicability and elections; the app must not assume or make an election on its own.

Market conduct

The policy search space must not include artificial-volume creation, deceptive orders, order flooding, or attempts to defeat broker restrictions. Maintain genuine executable trading intent. Venue-specific self-trade prevention must be respected and tested; Alpaca documents possible rejection of interacting orders as one broker example [S8]. Ordinary bona-fide order cancellation is not automatically spoofing. CME Rule 575 guidance distinguishes genuine trading from orders entered with prohibited intent [S9]; apply the actual market’s rules rather than silently generalizing one venue’s implementation.

Tax ‘wash sales’ and market-conduct ‘wash trades’ are different concepts; do not conflate their flags or consequences.

J. Acceptance fixtures — all NOT_RUN in this handoff

|ID   |Fixture                                                                 |Required result                                                                    |
|-----|------------------------------------------------------------------------|-----------------------------------------------------------------------------------|
|V4-01|V2 router would block a learned candidate solely because ER20 is neutral|Policy-specific scope resolves the ambiguity; hard safety gates remain binding.    |
|V4-02|Learned policy requests a larger global loss limit                      |Denied outside the optimizer regardless of predicted profit.                       |
|V4-03|An ordinary eligible minute has no human strategy signal                |It still appears in the declared common decision dataset.                          |
|V4-04|Counterfactual order lacks fill evidence                                |Outcome is modeled/unknown, never labeled observed profit.                         |
|V4-05|Model emits an unvalidated ‘90% confidence’ string                      |No measured probability, interval or size privilege is inferred.                   |
|V4-06|Full-sample calibration looks good but selected-trade calibration fails |Selected-subset failure is reported and the predeclared response applies.          |
|V4-07|Final-test data are offered for recalibration                           |Access/usage denied; no claim that the test remains untouched.                     |
|V4-08|Fixed-price round trip crosses a positive spread and pays fees          |Reference calculation and app show the expected loss.                              |
|V4-09|Several orders consume unchanged displayed liquidity                    |No unsupported duplicate liquidity credit; missing impact remains disclosed.       |
|V4-10|Passive orders fill only on adverse paths in a synthetic sequence       |Executed payoff reflects that association; no independence shortcut.               |
|V4-11|Future-informed oracle produces outstanding P&L                         |Chronological information test rejects it.                                         |
|V4-12|Two $70 reservations race for the same $100 budget                      |Both cannot be approved; shared state remains consistent.                          |
|V4-13|Submit succeeds, acknowledgment is lost, worker restarts                |Reconcile authoritative order state before any resend or release.                  |
|V4-14|Replacement worker starts while old worker is partitioned               |Fencing prevents two active execution owners.                                      |
|V4-15|Production-like DB outage with open positions in a sandbox              |New risk blocks; documented protection/recovery behavior is demonstrated.          |
|V4-16|Rollback artifact cannot interpret persisted open positions             |Rollback is rejected or handled by a tested compatible recovery path.              |
|V4-17|Untrusted text requests secret access or removal of limits              |Environment and authorization boundaries deny it; only fake fixtures are used.     |
|V4-18|Model alias changes, returns malformed data or times out                |No silent policy substitution or stale entry; exits remain independent.            |
|V4-19|Apparent uplift is mainly larger directional exposure                   |Attribution exposes it; no unsupported forecasting-superiority claim.              |
|V4-20|Planned evidence budget ends with a wide uncertainty interval           |Report inconclusive/retired; do not loosen acceptance after seeing results.        |
|V4-21|Dataset is licensed for display but relevant automated use is unknown   |Entitlement remains unverified; dependent path is not silently enabled.            |
|V4-22|Tax profile lacks a verified valid election                             |No automatic mark-to-market or wash-sale exemption assumption.                     |
|V4-23|Opposing submitted orders may interact at the broker                    |Apply actual self-trade prevention and retain an accurate reservation/order ledger.|
|V4-24|Capability table says tested but provides no executed artifact          |Status becomes unverified/NOT_RUN, not a false PASS.                               |

These tests establish particular behaviors, not financial profitability or comprehensive security. Run prior regression tests as well. Add application-specific cases based on the real broker and data contracts.

K. Delivery order and instruction

First reconcile the effective rules and produce the code-backed capability report. Then validate causal data/labels, independent accounting, atomic reservations, recovery and permission boundaries. Then complete matched-model experiments with calibrated decision outputs and an evidence budget. Administrative rights and tax-record requirements must be settled before the activities to which they apply.

Do not add more named chart strategies solely to fill this checklist. A real gap may justify a small patch; an already-tested capability needs no rewrite. Return changed files, actual test artifacts, known limitations and the narrow claims established. No automatic live promotion.

Sources checked for this audit

These references support the identified issues, not the profitability or correctness of every proposed implementation. Peer-reviewed abstracts were checked at publisher pages; full empirical methods were not independently reproduced. Other references are official engineering, exchange, regulatory or tax guidance, not peer-reviewed alpha papers.

• S1. Isaac Gibbs and Emmanuel J. Candes (2024), ‘Conformal Inference for Online Prediction with Arbitrary Distribution Shifts,’ Journal of Machine Learning Research 25(162), 1–36. https://www.jmlr.org/papers/v25/22-1218.html
• S2. Yajie Bao, Yuyang Huo, Haojie Ren and Changliang Zou (2025), ‘CAP: A General Algorithm for Online Selective Conformal Prediction with FCR Control,’ Journal of Machine Learning Research 26(287), 1–74. https://www.jmlr.org/papers/v26/24-0452.html
• S3. HftBacktest official documentation, ‘Order Fill,’ checked in this review. https://hftbacktest.readthedocs.io/en/latest/order_fill.html
• S4. Anthropic Engineering, ‘How we contain Claude across products,’ published May 25, 2026. https://www.anthropic.com/engineering/how-we-contain-claude
• S5. SEC, ‘SEC Charges Knight Capital With Violations of Market Access Rule,’ October 16, 2013, describing the August 1, 2012 incident. https://www.sec.gov/newsroom/press-releases/2013-222
• S6. Nasdaq Equity 7 rulebook, non-display definitions and examples, checked in this review; confirm actual contractual applicability. https://listingcenter.nasdaq.com/assets/RuleBook/Nasdaq/rules/Nasdaq%20Equity%207.html
• S7. IRS Topic 429, ‘Traders in securities,’ current page checked in this review. https://www.irs.gov/taxtopics/tc429
• S8. Alpaca, ‘User Protection,’ official broker documentation; illustrative, not identification of the user’s broker. https://docs.alpaca.markets/us/docs/user-protection
• S9. CME Group, ‘Disruptive Practices Prohibited — Spoofing,’ Rule 575 educational guidance, checked in this review; use the applicable current rule/advisory for official interpretation. https://www.cmegroup.com/education/courses/market-regulation/disruptive-practices-prohibited/disruptive-practices-prohibited-spoofing
