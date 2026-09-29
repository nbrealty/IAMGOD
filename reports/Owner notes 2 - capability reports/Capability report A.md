# Capability report A: live paper minute bot vs handoff v4 (checked 2026-09-29, 01:00 ET)

Read-only on the repo. Nothing edited, no orders, no network. Disclosure: I ran one `git check-ignore` by mistake (read-only, changed nothing). The permitted test file `test_scalp_live_round3.py` itself runs git, but only on throwaway repos in pytest temp folders. A before/after file listing of the repo showed no changes after the test runs (later scratch runs were not re-diffed; they only write under the scratchpad).

## 0. Legend and what was actually run
Test command (from `/home/user/IAMGOD/trading`, `PYTHONDONTWRITEBYTECODE=1`): `python -m pytest -p no:cacheprovider tests/<file> -v`.
Combined run of all requested files: `python -m pytest -q -p no:cacheprovider tests/test_scalp_live_*.py tests/test_scalp_signals.py` gave **376 passed, 0 failed**. Extra runs: test_scalp_backtest.py 22 passed, test_scalp_data.py 10 passed. Whole suite was only collected (2057 tests), not run; the "2056 tests" claim in MINUTE_TRADING.md is therefore NOT_RUN by me.
Aliases (each = file with the command above, all PASS): [rules]=test_scalp_live_rules.py (100), [engine]=..._engine.py (38), [broker]=..._broker.py (30), [runtime]=..._runtime.py (47), [review]=..._review.py (38), [notes1]=..._notes1.py (31), [round3] (16), [round4] (11), [restart]=..._restartsafety.py (16), [integ]=..._integration.py (15), [signals]=test_scalp_signals.py (34).
Artifacts: `capability/runs/*.txt` (verbose outputs), `capability/exp/*.py` (scratch experiments X1..X12, run with `cd capability/exp; PYTHONDONTWRITEBYTECODE=1 python <file>`). Scratch experiments are NOT repo tests; where only a scratch run supports a row, status is IMPLEMENTED_UNVERIFIED.
X1=e1_v408, X2=e2_v412 + e2b (ablation), X3=e3_v413, X4=e4_v414 + e4b, X5=e5_v415, X6=e6_v416, X7=e7_v411, X8=e8_v409_v410, X9=e9_v423, X10=e10_nofill, X11=e11_alerts, X12=e12_v403.
APP = US equity SPY/QQQ, Alpaca paper account ending GWRL, IEX live feed + SIP history (16 min delayed), policies ORB5_QQQ v1, LAST30_MOM_SPY v1, NOISE_MOM_SPY v1 (all EXPLORATORY; NOISE forced SHADOW live because it uses volume on IEX).
Status meaning: AND_TESTED = code plus a repo test I ran and passed; UNVERIFIED = code exists but no repo test covers the row (or only partly); MISSING; N/A; CONFLICT.

## 1. Facts record
| Item | Effective value | Reference |
|---|---|---|
| Decision frequency | Engine ticks about 1 Hz; setups decide only on completed 1-minute bars. ORB5: 1/day (09:34 bar, order about 09:35:0x). LAST30: 1/day (15:29 bar, order about 15:30:0x). NOISE: 12/day (:00/:30, 10:00-15:30). Reconcile every 5 s busy, 30 s idle. | runner.py:Runner.loop; engine.py:_signals; signals.py:orb5, _last30, NOISE_TIMES; config RECONCILE_EVERY_S=5, RECONCILE_IDLE_EVERY_S=30 |
| Target horizon | Registry `max_hold`="until_flatten" for all three (ceiling used by the event check). Real holds: ORB5 to 15:50 (10R target/stop), LAST30 about 20 min (overlay stop 0.5%, target 1.0%), NOISE until band/VWAP exit or 15:50. | registry.json; config.py:Registration.max_hold; clock.py:hold_horizon |
| Entry-expiry | Entry is a DAY limit; engine asks to cancel after ENTRY_TIMEOUT_S=2; cancel must be confirmed within CANCEL_CONFIRM_S=5 (else re-request); a fill during the cancel counts. Unacknowledged submit dropped after UNCERTAIN_GIVE_UP_S=10. | engine.py:_advance, _cancel_entry, UNCERTAIN_GIVE_UP_S |
| Maximum holding | Flatten 15:50 (FLATTEN_MIN_BEFORE_CLOSE=10), kill if open at 15:55 (KILL_MIN_BEFORE_CLOSE=5), outside watchdog 15:57 (WATCHDOG_FLAT_MIN_BEFORE_CLOSE=3). Half days rejected. Nothing overnight (DAY orders). | engine.py:_clock_rules; watchdog.py:watchdog_reasons |
| Multipliers | 1 (shares). No field; no options/futures path. | ALLOWED_SYMBOLS=("SPY","QQQ") |
| Tick / lot | Prices to $0.01 with Decimal (buy limit and stops rounded down, sell limit up, target half-up). Whole shares, qty>=1, max 1 (EXPLORATORY_MAX_QTY=1). DAY, regular hours, extended_hours False. Size needs equity about $6,600+ (10% cap). | orders.py:_cents, validate; sizing.py:qty |
| Order types | Limit only: bracket entry (buy limit + take-profit limit + stop-limit) and simple sell limits. No market, stop-market, IOC, short. | orders.py; broker.py:request_for (LimitOrderRequest only) |
| Fee provenance | FEE_TABLE rows with URL and `verified` flag: SEC $20.60 per $1M sold from 2026-04-04; TAF $0.000195/share sold, cap $9.79 (Oct-Dec 2026 row verified=False, still charged); CAT $0.000001+$0.000002/share both sides from 2026-05-01. Commission $0 and "paper simulates no fees" are docstring claims only. No per-row verification date. HONEST_SLIP_PER_SHARE=$0.01/side. | costs.py:FEE_TABLE |
| Data entitlements as used | Live: free IEX real-time via REST polling (quotes, trades, bars). History/replay/re-mark: SIP at least 16 min old. Halt/LULD status unavailable (None). No licence or verification-date record. | market.py:LiveMarket, _iex, SipQuoteSource, SipTradeSource; data.py:DELAY |
| Account restrictions checked in code | Paper URL, key names, account starts "PA", ends "GWRL", equals pinned number (check-account also proves it differs from RULES). NOT gated: status, trading_blocked, shorting_enabled (owner set no_shorting at Alpaca), PDT, day-trade count (counted only). Buying power = min(settled cash, non-marginable BP, E0). | broker.py:AlpacaBroker.account; __main__.py:check_account; risk.py:entry_check |
Also: E0 = $1M (Alpaca default) so the dollar caps bind (daily stop $25, whole test $150); the 2%/5% percentage limits are inert at this size.

## 2. Requirement table (sections A-I, plus preamble and K)
Columns: id | one line | status | code | config (effective) | test (PASS = run this session) | remaining assumption | minimal change.

### Preamble / A
| id | requirement | status | code | config | test | remaining assumption | change |
|---|---|---|---|---|---|---|---|
| P-1 | Get market/broker/feed/account from code, no secrets shown | AND_TESTED | __main__.py:check_account | last 4 only | [runtime] test_mt_g36_check_account_proves_paper_and_not_rules_printing_only_last_4 | facts come from code, not live broker metadata | none |
| P-2 | Reuse app, keep stricter safeguards, no production change | N/A (process) | - | - | repo listing diff after test runs: no change | - | none |
| P-3 | Profit is not deployment authorization | AND_TESTED | config.py:_registration (VALIDATED refused) | no live path | [rules] test_validated_lane_is_impossible_in_v1 | - | none |
| A-1..A-4 | Report fields; no ref = not TESTED; unrun = NOT_RUN; conflicts reported | N/A (report rules) | - | - | applied here | - | none |
| A-5 | Decision frequency recorded as its own concept | UNVERIFIED | signals.py decision bars | no declared key | [signals] test_intents_are_decided_at_bar_closes_inside_the_session; [engine] test_live_decision_equals_the_backtest_intent_on_the_same_bars | not a registry field | none now |
| A-6 | Target horizon recorded | AND_TESTED | Registration.max_hold | "until_flatten" | [notes1] test_patch_c_registry_max_hold_is_required_and_no_version_was_bumped | max_hold is a ceiling, not a forecast horizon | none |
| A-7 | Entry-expiry policy | AND_TESTED | engine._advance | ENTRY_TIMEOUT_S=2 | [engine] test_a_slow_cancel_does_not_free_the_slot_early | - | none |
| A-8 | Maximum holding time | AND_TESTED | engine._clock_rules | 10/5/3 min before close | [engine] test_mt_g20_time_exit_at_1550_then_nothing_open, test_mt_g20_anything_still_open_at_1555_fires_the_kill_switch; [runtime] test_mt_g39_watchdog_flattens_an_open_position_at_1557_even_with_a_fresh_heartbeat | - | none |
| A-9 | Instrument multipliers | N/A | - | shares only | - | would be MISSING if futures/options added | none |
| A-10 | Tick/lot rules | AND_TESTED | orders._cents, validate | cent, int qty | [rules] test_mt_g21_rounding_helpers_have_no_float_drift, test_mt_g14_never_rounds_up_and_zero_means_no_trade | 2027 half-penny tick change not modelled | none |
| A-11 | Order types | AND_TESTED | orders.py, broker.request_for | limit only | [rules] test_mt_g21_order_builder_has_no_market_or_stop_order_path; [runtime] test_runtime_modules_build_orders_only_through_the_order_builder | - | none |
| A-12 | Fee schedule provenance | AND_TESTED | costs.FEE_TABLE | see facts | [rules] test_mt_g1_sec_fee_uses_the_rate_in_force_on_the_trade_date, test_taf_is_capped_rounded_up_and_cat_is_charged_both_sides | no verification date per row; TAF Q4 row unverified | add `verified_on` field (post-session) |
| A-13 | Data entitlements recorded with source and date | MISSING | Feed tags only | - | - | licence for automated use unknown | small entitlements.json printed at startup (post-session) |
| A-14 | Broker account restrictions | UNVERIFIED | broker.account reads trading_blocked/shorting_enabled | not gated | [broker] test_mt_g26_account_must_be_the_scalp_paper_account (identity only) | blocked account only shows as a reject | refuse entries if status not ACTIVE or trading_blocked (about 6 lines; not before 08:30) |
| A-15 | Decision frequency, horizon, expiry, hold not one vague setting | UNVERIFIED | separate constants | - | none asserts separation | decision frequency has no field | none |

### B (hard controls vs learnable policies)
| id | requirement | status | code | config | test | assumption | change |
|---|---|---|---|---|---|---|---|
| B-1 | Classify every rule HARD/BASELINE/LEARNABLE | MISSING (code); done in section 4 | - | - | - | - | `RULE_CLASS` map + completeness test (about 60 lines, post-session; config.py is under the risk hash) |
| B-2 | Optimizers cannot change hard controls | AND_TESTED | config constants, sizing.qty fixed signature, config.risk_hash | locked | [rules] test_mt_g41_every_guardrail_constant_is_locked, test_mt_g14_sizing_signature_is_fixed_and_forbidden_keywords_raise; [runtime] test_mt_g41_risk_hash_mismatch_disables_entries | risk_hash covers only config, risk, sizing, orders; MAX_OPEN_POSITIONS is locked but no code reads it; registry loader ignores unknown keys silently | reject unknown registry keys (post-session) |
| B-3 | Baseline versions preserved exactly | AND_TESTED | Registration.code_hash | 3 hashes match | [rules] test_mt_g10_committed_registry_hashes_equal_the_code; [runtime] test_mt_g10_a_changed_setup_runs_shadow_only | - | none |
| B-4 | Learnable variation only inside an approved envelope | MISSING | only overlay pct 0<x<0.05 check | - | - | no learned policy exists | later |
| B-5 | Scope each rule to policy ids | UNVERIFIED | per (setup,symbol): lane, round trips, stop-out cooldown, switch-offs; global: loss streak, day/week/test stops, slot | - | [rules] test_mt_g2_third_trade_for_one_setup_rejected | see section 4 | later |
| B-6 | Learned policy may trade a human NEUTRAL state only via hard gates | N/A | no ER20 router; Reason.STRATEGY_CONFLICT unused | - | - | - | none |
| B-7 | Learned policy cannot bypass data/halt/account/event/risk gates | AND_TESTED | engine._entry_candidate runs risk.entry_check for every candidate | - | [rules] test_every_failing_reason_is_listed_not_just_the_first; [notes1] test_patch_c_orb5_at_0935_on_a_day_with_a_1000_release_is_rejected | applies to any policy registered in SETUPS | none |
| B-8 | Filtered and unfiltered versions stay distinct | AND_TESTED | code_hash over signals.py | - | [review] test_mt_g10_v3_twenty_sessions_later_allowed_nineteen_refused_safety_fix_exempt | - | none |
| B-9 | Documents/LLM prose cannot override config | AND_TESTED | config in code, no LLM | - | [rules] test_mt_g41_every_guardrail_constant_is_locked | - | none |
| B-10 | Reject unresolved conflicts at startup | AND_TESTED | config.load_registry; runner.make_engine | - | [rules] test_registry_refuses_unknown_setups_and_bad_fields; [runtime] test_startup_flags_reach_the_engine_or_the_run_is_refused | a risk-hash mismatch blocks entries instead of refusing to start | none |
| B-11 | No production change without release process | UNVERIFIED | deploy guard, hashes, changes.log | 09:00-16:15 window | [runtime] test_mt_g27_deploy_in_market_hours_with_changed_code_blocks_entries | first start at 08:30 sets the baseline; engine/guard/clock changes are outside the owner-held hash | code freeze; extend risk_hash later |
| B-12 | Learned exit cannot alter stops of an open baseline trade | AND_TESTED | no modify/replace path; engine._stop_ok; owner-only exit (_signals) | - | [engine] test_mt_g16_stop_unconfirmed_goes_flat; [signals] test_live_flat_blocks_a_modelled_exit | - | none |

### C (opportunity sampling)
| id | requirement | status | code | test | assumption | change |
|---|---|---|---|---|---|---|
| C-1, C-2, C-5, C-6 | Opportunity is every eligible minute, a declared grid, no-entry actions, predictive labels | MISSING | only raw per-second recordings (market.Recorder) | X12: 780 quiet minutes gave 0 decision lines; [runtime] test_live_market_records_every_poll_and_the_recording_plays_back | recordings are not saved by state-save | per-minute `grid` journal line (about 40 lines; post-session) |
| C-3, C-10, C-12 | Other grids versioned; M1 vs baseline same universe; top-volume study | N/A | - | - | no learned model | none |
| C-4 | Record state, fired strategies, gate reasons | UNVERIFIED | engine._journal_decision (fired candidates only) | [integ] test_mt_g20_g16_g2_full_synthetic_session_replay_through_the_runner | no line when nothing fires | see C-1 |
| C-7 | Outcome labels observed/modeled/unknown | UNVERIFIED | take-profit PENDING_VERIFY, tp_verified, tp_missed; rejected candidates flagged shadow | [review] test_mt_g4_a_take_profit_fill_is_pending_verify_and_kept_out_of_the_gates | shadow outcomes never scored | later |
| C-8 | No real-money exploration | AND_TESTED | paper lock | [broker] test_mt_g36_paper_lock_refuses_the_rules_keys_before_any_network_call | - | none |
| C-9 | Do not impute unobserved fills | AND_TESTED | MT-G4 machinery | [round3] test_v3_2_a_take_profit_the_sip_never_traded_through_is_a_missed_fill_at_0r | dry-run quote mode fills on a touch (X8) | none |
| C-11a | Fixed universe | AND_TESTED | ALLOWED_SYMBOLS | [rules] test_mt_g23_symbol_outside_the_allowlist_is_refused | - | none |
| C-11b | Selection changes counted as trials | MISSING | MT-G7 ledger not built | - | - | later |

### D (calibration)
| id | requirement | status | note |
|---|---|---|---|
| D-1..D-6, D-8, D-11, D-12 | Probability/interval contracts, calibration bins, coverage, selected-subset checks, recalibration windows, fallback model rules | N/A | The bot emits no probabilities, intervals or model output. Closest analogue: a changed setup runs shadow only ([runtime] test_mt_g10_a_changed_setup_runs_shadow_only, PASS). |
| D-7 | Report states/size bands; sparse groups inconclusive | UNVERIFIED | INSUFFICIENT SAMPLE label ([runtime] test_mt_g11_report_labels_insufficient_sample_and_exploratory_on_every_setup_line, PASS); 15-minute buckets in report.buckets_block; no size bands (1 share). Gate bootstrap resamples trades, not sessions. |
| D-9 | Data-shift checks | UNVERIFIED | data gates and slippage switch-offs tested ([rules] test_mt_g22_*; [review] test_mt_g3_median_slippage_over_30_fills_above_1_5x_model_holds_the_setup_in_shadow); no schema or feature-support check. |
| D-10 | NO_NEW_RISK never disables exits | AND_TESTED | engine exits bypass risk.py. [engine] test_mt_g38_setup_exit_is_never_blocked_by_entry_gates; test_mt_g27_g38_kill_flattens_a_book_with_the_quote_feed_down_and_the_entry_cap_used |

### E (simulator audit)
| id | requirement | status | code / test | assumption / change |
|---|---|---|---|---|
| E-1 | Independent hand-built reference for cash, qty, orders, P&L, equity, fees, rounding | MISSING | X1 (hand Decimal calculation of a flat-price round trip) PASS; existing [rules] test_mt_g4_honest_pnl_marks_paper_down_and_never_subtracts_the_spread_twice takes its expected fee from the app's own X.fees | add `tests/test_scalp_live_reference.py` (about 80 lines) from X1 |
| E-2 | Causal ordering of the replay engine | AND_TESTED | signals.py; SimBroker bar mode. [signals] test_no_look_ahead (14 setups); [broker] test_sim_bar_mode_checks_legs_on_later_bars_with_the_stop_first; [review] test_replay_bar_gapping_above_the_target_fills_the_target_at_the_open_like_the_backtest | - |
| E-3 | Displayed-liquidity accounting; repeated orders cannot reuse the same size | MISSING | X8: SimBroker filled 25 shares against 1 displayed and re-used the same share | cannot bind at 1 share (guard blocks qty>1) |
| E-4 | Queue assumptions consistent | CONFLICT | bar mode needs a print strictly through the limit ([integ] test_mt_g4_buy_limit_500_fills_in_bar_replay_only_when_the_low_trades_through_it PASS); quote mode fills a take-profit on a touch (X8) | dry-run results are optimistic; align quote mode |
| E-5 | Fees and model version | fees AND_TESTED; model version MISSING | fee tests PASS; replay_start line has no simulator version | add code hash to replay_start |
| E-6 | Impact of others / adverse-selection joint model | MISSING | only live `post_fill_mark` at +1/+5 min | disclose in report |
| E-7 | Flat-price fixture with spread and fees | UNVERIFIED | X1 PASS: hand loss -0.060006 (paper -0.01, slippage 0.02, SEC 0.02, TAF 0.01, CAT 0.000006) matched journal and SimBroker cash | put in repo |
| E-8 | Rejected / never-filled orders | AND_TESTED | [engine] test_mt_g25_broker_403_on_entry_is_not_retried_and_blocks_the_symbol, test_a_slow_cancel_does_not_free_the_slot_early; X10 P&L exactly 0 | - |
| E-9 | Partial entries / partial exits | entries AND_TESTED, exits UNVERIFIED | [engine] test_partial_fill_is_protected_at_once; [review] test_partial_fill_never_counts_a_held_leg_as_protection; no partial-exit test (1 share) | - |
| E-10 | Liquidation after interruption | AND_TESTED | [integ] test_mt_g39_bot_dies_with_a_position_open_and_the_watchdog_flattens_within_45_seconds; [engine] test_mt_g40_restore_flattens_a_position_without_a_live_stop | - |
| E-11 | Future-informed oracle rejected | UNVERIFIED | X7: real setups pass the perturbation check, an oracle fails it; repo has no oracle control | add oracle to test_scalp_signals.py (about 25 lines) |
| E-12 | Range of order sizes; capacity | MISSING / N/A | fixed 1 share; backtest is $1,000 per trade | do not extrapolate |
| E-13 | Real-money experiments need authorization | AND_TESTED | paper lock. [broker] test_mt_g36_a_live_url_override_is_refused_before_any_network_call | - |

### F (atomic reservations, recovery)
| id | requirement | status | code | test | assumption / change |
|---|---|---|---|---|---|
| F-1 | Risk check and reservation atomic | UNVERIFIED | single-threaded engine, one slot; no money reservation ledger (settled cash and gross notional count fills only); broker.lock is per call | X2: only one order reaches the broker | holds for one process only; see F-5 |
| F-2 | Cancel request is not a cancel | AND_TESTED | engine._advance | [engine] test_a_slow_cancel_does_not_free_the_slot_early; [broker] test_sim_a_cancel_request_is_not_a_cancel | - |
| F-3 | Do not release on timeout alone | CONFLICT | engine._refresh drops an unfound submit after 10 s | X3-D: order appeared later, reconcile killed and HALTed | fail-closed but untested; make give-up query-then-kill or wait for reconcile |
| F-4 | Unacknowledged order keeps its slot | UNVERIFIED | Trade.uncertain_since | X3-C | add engine test |
| F-5 | Single execution owner / fencing | MISSING | no lock in runner.run; heartbeat holds a pid never checked | X4 | add non-blocking flock on `state/scalp/run-paper.lock` at start (about 20 lines + 2 tests) |
| F-6 | Stable ids respect the broker dedupe contract | AND_TESTED | orders.client_id; AlpacaBroker.submit looks up on 409/422 | [rules] test_mt_g25_client_ids_are_deterministic_and_parseable; [broker] test_mt_g25_duplicate_client_id_is_looked_up_and_returned | detection matches text "client_order_id" in the error; wording change would turn it into a reject |
| F-7 | Fault injection: fill during cancel; duplicate events; worker death; rate limit | AND_TESTED | - | [engine] test_a_fill_that_arrives_while_the_cancel_is_pending_is_a_position; [runtime] test_mt_g22_live_market_delivers_each_completed_bar_once_and_never_an_in_progress_bar; [restart]/[integ] restart tests; [broker] test_mt_g25_4xx_is_a_reject_and_timeouts_are_unavailable (429) | - |
| F-8 | Fault injection: lost acknowledgement; clock jump; simultaneous proposals; rollback | UNVERIFIED | X3, X2, X6 | no engine test; clock step backward stalls timers (not tested) | add tests |
| F-9 | Database outage | N/A | no database; analogue is V4-15 | - | - |
| F-10 | Human alert routing, acknowledgement, no-response plan | MISSING | Engine._alert only writes the journal; runner.make_engine has no alert argument (X11: no stderr, no alerts.log). Watchdog and kill command do write alerts.log | - | pass `alert=` to the engine in runner (about 10 lines + 1 test) |
| F-11 | No guaranteed-liquidation claim | AND_TESTED | alerts say close by hand | [engine] test_mt_g16_exit_whose_leg_cancels_never_confirm_alerts_and_escalates_to_the_kill | - |
| F-12 | Reserve capacity for exits; no retry storm | AND_TESTED | guard.py exit budget 30/min | [engine] test_mt_g25_seventh_entry_in_60_s_is_blocked_while_8_exit_resends_are_not | data polls have no backoff (1 Hz) |
| F-13 | Rollback compatible with persisted positions | MISSING | no schema version; unparseable ids give flatten + HALT | X6 | later |

### G (AI permissions)
| id | requirement | status | note |
|---|---|---|---|
| G-1, G-2 | Research/code agent holds no broker secrets; unscoped credentials stay out | CONFLICT | This coding session's environment holds ALPACA_SCALP_KEY/SECRET and ALPACA_RULES_KEY/SECRET (names only checked, values not read). Paper accounts, but trade-capable. Owner decision 1 put them there. Change: owner decides on a separate host for the bot. |
| G-3 | Execution takes only validated intents from approved versions | AND_TESTED | Candidate objects from registered pure functions. [rules] test_registration_and_lane_are_enforced |
| G-4, G-7 | Ignores instructions in text; malicious-content fixture | UNVERIFIED / MISSING | No text channel exists; no fixture. Add a KILL-file/registry text fixture only if a text input is ever added. |
| G-5 | No needless account details in logs | UNVERIFIED | last 4 in prints; full account number in `account.pin`, which `statesync.PATTERNS` (`*.pin`) pushes to branch scalp-state ([round3] test_v3_3_state_save_pushes_only_the_whitelist_to_scalp_state_and_restore_brings_it_back). Minor. |
| G-6 | Permission boundaries, dependency review | UNVERIFIED | paper-URL allowlist and key-name lock only; requirements.txt uses `>=` pins (alpaca-py 0.44.0 installed) |
| G-8 | No real secrets in fixtures | AND_TESTED | tests pass fake env dicts |
| G-9, G-12, G-13 | Pin model/prompt; alias changes; model timeouts | N/A | no model |
| G-10, G-11 | Code/config hashes and replay inputs recorded | AND_TESTED | registry hash, risk_hash, package_hash in `start` line; Recorder with receipt times. [integ] test_mt_g27_g37_replaying_a_recorded_session_gives_the_same_decisions. Recordings and broker events are not saved by state-save. |
| G-14 | Exits independent of model availability | AND_TESTED | no model; see D-10 |

### H, I, K
| id | requirement | status | note |
|---|---|---|---|
| H-1 | Fixed review schedule or sequential rule | UNVERIFIED | reviews at 20/60 sessions are text (MINUTE_TRADING.md); MT-G12 runs after every trade |
| H-2, H-5, H-10 | Stop-spending rule; no threshold loosening; retire losers | AND_TESTED | [rules] test_whole_test_stop_at_150_dollars_or_60_sessions, test_mt_g41_every_guardrail_constant_is_locked, test_mt_g12_retire_and_small_samples |
| H-3 | Power/sensitivity analysis | MISSING | MT-G42 not built; no pilot data yet |
| H-4 | Wide uncertainty is inconclusive | AND_TESTED | [rules] test_mt_g11_insufficient_sample_below_100_trades_or_40_sessions |
| H-6, H-8, H-9 | Exposure attribution, benchmarks, predeclared objective/costs | UNVERIFIED | MT-G34 lines and exposure-matched SPY ([review] test_mt_g34_exposure_matched_spy_uses_the_same_dollars_and_minutes); operating result ([notes1] test_v2_20_fixed_costs_above_trading_pnl_give_a_negative_operating_result_without_touching_pnl); no decomposition; hosting cost "not recorded" |
| H-7 | Live exposure adjustment from prior data | N/A | none |
| I-1..I-3 | Data agreements reviewed; entitlement source and date; unknown = disabled | MISSING | nothing recorded; IEX feed drives automated decisions; journals with quotes are pushed to a git branch |
| I-4, I-6, I-11 | Tax lots/exports; no election assumed; wash sale vs wash trade | N/A | paper only; no tax code (data for lots exists in the journal) |
| I-5 | Trading P&L separate from operating result | AND_TESTED | Patch H test above |
| I-7 | No order flooding / deceptive orders | flooding AND_TESTED, rest UNVERIFIED | [engine] test_mt_g25_runaway_entry_at_the_guard_fires_the_kill_switch; entries are marketable ([rules] test_mt_g21_entry_collar_is_the_smaller_of_2_cents_and_5_bps) |
| I-8 | Self-trade prevention respected and tested | UNVERIFIED | X9: no live buy and sell rest together in a symbol in four lifecycles (only a parent with its own legs); no wash-trade rejection test or emulation |
| I-9 | CME rule 575 | N/A | equities via Alpaca |
| K-1..K-5 | Order of work; no new strategies; small patches; no auto promotion | AND_TESTED for no promotion | lane VALIDATED impossible; no file changed by this audit |

## 3. Fixtures V4-01 to V4-24
| id | status | code and test | result / test sketch if missing |
|---|---|---|---|
| V4-01 | N/A | no ER20 router exists | If added, scope it to listed setup ids so hard gates still bind. |
| V4-02 | AND_TESTED | constants, sizing.qty, risk hash. [rules] test_mt_g41_every_guardrail_constant_is_locked; test_mt_g14_sizing_signature_is_fixed_and_forbidden_keywords_raise | PASS. Denied by absence: no API lets a policy ask for a limit. Registry unknown keys ignored silently. |
| V4-03 | MISSING | X12 | 780 eligible minutes, 0 decision lines. Sketch: replay a quiet day, assert one grid line per symbol-minute. |
| V4-04 | UNVERIFIED | MT-G4 labels for take-profit fills only | shadow candidates have no outcome label. |
| V4-05 | AND_TESTED (size only) | sizing.qty rejects `confidence`. [rules] test_mt_g14_same_qty_after_good_and_bad_mornings | no model exists. |
| V4-06 | N/A | no calibrated output | - |
| V4-07 | MISSING | MT-G6 sealed holdout not built | Sketch: registry of holdout dates; backtest raises on a second look. |
| V4-08 | UNVERIFIED | costs.py; X1 | PASS in scratch: hand loss -0.060006 equals app. Existing test uses app fee helper. |
| V4-09 | MISSING | SimBroker | X8 shows no liquidity accounting. |
| V4-10 | MISSING | - | quote mode fills on touch; no joint model. |
| V4-11 | UNVERIFIED | [signals] test_no_look_ahead[*] PASS (14); X7 | oracle fails the check in scratch. Add oracle control. |
| V4-12 | UNVERIFIED | Same-tick proposals: X2 (LAST30 and NOISE both EXPLORATORY, same 15:29 bar) sent exactly 1 order either registration order; the loser was refused POSITION_OPEN plus NO_ADD (first filled) or OPEN_PARENT (first unfilled). What stops it: (1) engine.trade is set synchronously by the first _submit_entry before the second candidate is evaluated (single thread); risk.entry_check reads that slot; (2) engine adds POSITION_OPEN itself; (3) GuardedBroker open-parent cap, only while the parent is unfilled, and it answers with the kill switch; (4) after-the-fact reconcile kills. Ablation (X2b): with (1),(2) removed and the first filled, the guard lets a 2nd share through and reconcile flattens it in seconds. Neighbours PASS: [rules] test_mt_g2_entry_while_any_position_is_open_rejected; [engine] test_mt_g25_guard_blocks_a_second_open_parent_and_oversize, test_mt_g2_second_signal_while_the_slot_is_taken_is_rejected (later tick only) | No dollar reservation exists (settled cash counts fills only). Sketch: two EXPLORATORY setups on one bar; assert len(sim.submits)==1. |
| V4-13 | UNVERIFIED | X3: lost ack with the order arrived: engine finds it by client id, 1 order, stop confirmed; restart via restore.rebuild adopts it, re-decision refused, submits stay 1. Lookup failing more than 10 s: engine drops it, reconcile finds it later, kill plus HALT (X3-D). Existing: [broker] test_sim_reject_unavailable_and_duplicate_ids (broker level); [engine] test_mt_g40_restore_cancels_an_unfilled_entry_parent | Add engine-level test from X3 A/B. |
| V4-14 | MISSING | No single-instance lock in runner.run (checked: no flock/pid file; `broker_lock` is held only per order call). X4: two engines on one account. Second engine refuses to enter (RECONCILE_MISMATCH, foreign order), then after 2 checks 3 s apart fires the kill switch, cancels the first's legs, sells the share, writes HALT; both end DISABLED. Race case: identical client id dedupes to one order. Replacement worker adopting the same position: 15:50 exit sent once, second worker's exit rejected three times, kill, HALT. Never short (sell guard). Heartbeat file is shared, so a live second process hides a dead first one. | Protects the account: deterministic ids, reconcile-then-kill, sell-size guard. Costs: HALT persists to the next day until reset-halt. |
| V4-15 | UNVERIFIED | No database; analogue is a full state disk (real ENOSPC on a tiny tmpfs, X5). FileJournal.write and heartbeat writes do not catch errors. Entry: decision is journalled before submit, so failure sends no order. Exit: journal write in _start_exit fails first, so the 15:50 sell is NOT sent; tick raises out of the runner and the process dies; bracket legs at the broker remain. Watchdog: flattens (broker call first), then its HALT write fails and run_watchdog's handler fails too, so it dies; HALT not written. Failed heartbeat leaves a stray .tmp file. | Not a repo test. Change: make journal/heartbeat writes best-effort (about 30 lines in journal.py, runner.py, watchdog.py); not before 08:30. |
| V4-16 | MISSING | X6: position with ids this code cannot parse is not adopted; reconcile kills, flat plus HALT. No schema version in any state file. Deploy guard blocks entries only. | Safe but not a compatible recovery path. |
| V4-17 | UNVERIFIED | no text-to-action channel; key-read tests: [runtime] test_mt_g36_rules_keys_are_read_only_inside_check_account; [rules] test_pure_rule_modules_never_read_keys_or_the_system_clock | no injection fixture or logging. |
| V4-18 | N/A | no model. Import check (X-scan): loading every live module loads no LLM client; requirements.txt lists anthropic for the other `trader` package. Tests only ban `anthropic`: [rules] test_package_never_imports_an_llm_the_trader_or_the_options_lab, [runtime] test_package_never_imports_anthropic_trader_or_the_options_lab (PASS); they scan live/*.py only, not signals.py, backtest.py, data.py. | Widen the ban list. |
| V4-19 | UNVERIFIED | MT-G34 benchmark lines | no attribution fixture. |
| V4-20 | UNVERIFIED | INSUFFICIENT SAMPLE label; locked thresholds | no interval in live report. |
| V4-21 | MISSING | - | nothing disabled or recorded. |
| V4-22 | N/A | no tax logic | - |
| V4-23 | UNVERIFIED | exits cancel legs, wait for confirmation, then sell (engine._exit_step); kill and watchdog cancel first; X9 never found opposite resting orders except a parent with its own legs; sell size guarded by broker.reserved_sell_qty ([broker] test_mt_g15_a_sell_larger_than_the_free_long_position_is_refused) | a wash-trade rejection would block that symbol for the day (entry) or step the collar (exit); untested. |
| V4-24 | N/A to code | this report's PASS entries all come from runs listed in section 0; MINUTE_TRADING.md "2056 tests" is NOT_RUN by me (2057 collected) | - |

## 4. Rule classification
Hard controls (everything not listed as baseline); scope = global unless stated.
| Rule / constants | Class | Scope now | Should be |
|---|---|---|---|
| ALLOWED_SYMBOLS, SHORTS_ENABLED, ORDER_PREFIX, paper lock, PAPER_URL, MARGIN_* (record only), MT-G23/G36 | HARD | global | global |
| MAX_ROUND_TRIPS_DAY, MAX_OPEN_POSITIONS (unused by code), MAX_OPEN_PARENTS, MAX_ENTRY_SUBMITS_DAY/_PER_MIN, MAX_NOTIONAL_DAY_X_E0, MAX_EXIT_ORDERS_PER_MIN, GROSS_NOTIONAL_MAX_X_E0 | HARD | global | global caps, plus per-policy sub-budgets when several policies share the slot |
| MAX_ROUND_TRIPS_SETUP, STOPOUT_REENTRY_MIN | HARD | per (setup, symbol) | as now |
| RISK_PCT, NOTIONAL_CAP_PCT, EXPLORATORY_MAX_QTY | HARD | global (lane cap per lane) | global |
| DAILY_STOP_USD/_PCTS, WEEKLY_STOP_PCT, DRAWDOWN_HALT_PCT, TEST_STOP_USD, TEST_MAX_SESSIONS | HARD | account-wide; one test_start for the whole bot | per-policy test window and P&L attribution needed |
| LOSS_STREAK_N, LOSS_STREAK_PAUSE_MIN | HARD | global counter | per policy |
| ENTRY_COLLAR_*, STOP_LIMIT_*, EXIT_COLLARS, KILL_COLLARS, STOP_ESCALATION_*, STOP_WATCHDOG_S, ENTRY_TIMEOUT_S, STOP_CONFIRM_S, EXIT_ACK_S, CANCEL_CONFIRM_S, CANCEL_GIVE_UP_X, HTTP_TIMEOUT_S, LOCK_WAIT_S | HARD (protective-exit integrity) | global | ENTRY_TIMEOUT_S could become a per-policy value inside an envelope |
| OPEN_BLOCK_MIN, ENTRY_CUTOFF_*, FLATTEN_*, KILL_*, WATCHDOG_FLAT_*, RELEASE_BLOCK_*, FOMC_BLOCK, EVENT_WINDOW_*, EVENT_EXIT_ALLOWANCE_S, FOMC_EVENT_TIMES, MAX_HOLD_UNTIL_FLATTEN | HARD | global; exemptions are per-policy flags (opening_window, tested_on_release_days, max_hold) | as now |
| CLOCK_OFFSET_MS, DATA_SILENCE_S, QUOTE_MAX_AGE_S, BAR_MAX_AGE_S, MAX_SPREAD_*, MAX_PRICE_VS_LAST_TRADE, WILD_MINUTE_*, LULD_PCT, MWCB_DROP, HALT_SUSPECT_* | HARD (data authenticity) | global per symbol | global |
| RECONCILE_*, MISMATCH_*, HEARTBEAT_STALE_S, WATCHDOG_EVERY_S | HARD | global | global |
| HONEST_SLIP_PER_SHARE (basis of every loss limit) | HARD | global | global |
| SLIP_MODEL_*, SLIP_MIN_FILLS, SWITCH_OFF_N, RETIRE_N, MIN_SAMPLE_*, VERSION_MIN_SESSIONS (MT-G3/10/11/12/13) | HARD (experiment access) | per (setup, symbol) history | as now |
| SETUP_CODES, RISK_FILES, REGISTRY_PATH, EVENTS_PATH, STATE_DIR, LIVE_DIR, TRADING_DIR | HARD (identity/paths) | global | RISK_FILES should cover engine, guard, clock, events, costs, restore, watchdog |
| ORB5, LAST30, NOISE logic in signals.py; overlay_stop_pct 0.5%, overlay_target_pct 1.0%; opening_window, tested_on_release_days, uses_volume, model_slip_bps, backtest_mean_r | BASELINE | per policy id and version, frozen by code hash | as now |
| max_hold, overlay pct (0<x<0.05), decision times, features, exit choice, abstention | LEARNABLE for a future policy (envelope: registry checks only) | none exist | per policy inside an approved envelope |
MT-G rules: G2, G14-G22, G23, G25-G27, G36, G38-G41 are hard controls (done, tested). G3/G4/G10-G13 are hard (experiment/accounting). G16 requirement of a bracket is hard; its values are baseline. G24 hard per registration. G29-G32 satisfied by having no LLM. G33/G34 report only. G35 hard, with per-policy `uses_volume`. G9 tested for all registered setups. Not built: G1 gate for the validated lane, G5-G8, G37 (use `replay`), G42. G28 has no options path.

## 5. Gaps for Tuesday 29 Sept, 08:30 ET (only LAST30 at 15:30 can trade; ORB5 refused by EVENT_HORIZON_OVERLAP on the two 10:00 releases: [notes1] test_patch_c_orb5_at_0935_on_a_day_with_a_1000_release_is_rejected and test_patch_c_last30_at_1530_on_a_normal_day_is_allowed PASS)
No blocker found. Preconditions the owner must do: set SCALP_RISK_HASH to today's `python -m lab.scalp.live hash` value (starts e140c4299233; a stale value refuses every entry); start before 09:00; confirm no other bot process; free disk (28 GB free now); no HALT/KILL file exists now.
| Rank | Severity | Gap and what could go wrong | Minimal change | Safe before 08:30? |
|---|---|---|---|---|
| 1 | major | Engine alerts (kill switch, reconcile halt, daily stop, "close by hand") go only to the journal file; nobody is told until the 16:20 wrap-up (X11). | runner.py: pass `alert=` to engine, calling state.alert (about 10 lines, 1 test) | Yes if reviewed; touches no risk file and 08:30 is before the deploy window. Zero-code option: watch the journal for `"kind":"alert"`. |
| 2 | major | No single-instance lock (X4). An accidental second start makes the two kill each other and set HALT, which also blocks Wednesday until reset-halt. | flock at start in runner.run (about 20 lines, 2 tests) | Reviewable in under an hour; otherwise check for other processes by hand. |
| 3 | major | Watchdog runs in the same container as the bot; if the host dies nothing flattens and DAY legs expire at 16:00 (1 share could sit overnight). Hosting is "not recorded". | none in code; owner decision and a manual 15:57 dashboard check | Not a code change. |
| 4 | major, low chance | Full or unwritable state disk stops the bot at its first journal write and can block the 15:50 exit; watchdog flattens then dies without HALT (X5). | best-effort journal, heartbeat and HALT writes (about 30 lines, 3 files) | No. Check `df -h` instead. |
| 5 | minor | Startup could put LAST30 in SHADOW ("STATE NOT RESTORED") if the broker shows an earlier filled order with a setup-coded SCALP id and no local paper journal; the 28 Sept manual test id format is unknown. | read the startup line; `accept-journal-gap` if needed | n/a |
| 6 | minor | Unacknowledged entry is released after 10 s; if it appears later the kill switch and HALT fire (X3-D). | wait for reconcile before release | No. |
| 7 | minor | Hash covers 4 of about 17 modules; guard, clock, engine edits are not caught by SCALP_RISK_HASH. | code freeze now; widen later | Do not change tonight. |
| 8 | minor | Account flags not gated; data licence not recorded; recordings not saved; full account number pushed by state-save; false HALT_SUSPECTED on a thin IEX minute would block the symbol for the day (fails closed). | later | - |

## 6. Conflicts
Would loosen or contradict our rules or owner decisions (do not adopt):
1. A learned or LLM policy producing entry intents: conflicts with MT-G29 to G32 (LLM may only veto) and owner decision 3 (registered setups with exact rules); MT-G5 to G7 gates are not built.
2. Universe expansion, order-size ranges or extra symbols on the live paper account: conflicts with MT-G23, MT-G14 and owner decision 4 (SPY and QQQ, 1 share). Fine offline only.
3. Building a database, tax lot exports, or calibration machinery: the handoff itself says reuse the app; the bot has no model, no database and is paper only.
4. G-1/G-2 (keys outside the research environment) is stricter than today: cannot be met tomorrow because the bot runs where the keys are. Owner decision needed.
5. I-3 (unknown data rights mean the path is disabled) would stop the live feed; owner must decide before Tuesday.
Our code already does better or equal: stable-id handling verified against the real Alpaca 422 duplicate behaviour; separate exit budget that never triggers the kill; a cancel request is never treated as a cancel; unverified take-profit fills counted as at most 0R; unknown event calendar blocks all entries; deploy-window guard and startup flags that must reach the engine; order flood caps outside the decision code; MT-G38 exits never gated.
Internal conflicts found: quote-mode vs bar-mode fill rule (E-4); release-on-timeout vs the handoff's F rule (F-3); the config comment and DESIGN say alerts are raised, but engine alerts reach only the journal.
