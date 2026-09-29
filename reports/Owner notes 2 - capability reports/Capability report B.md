# Capability report B: live paper minute bot vs handoff v4

Read-only run. No git, no repo edits, no broker/network. Nothing under `trading/` changed (checked with `find -newer`); other sessions edited docs under `reports/` and `MINUTE_TRADING.md` meanwhile.

**Commands actually run** (PASS/FAIL below refer to these)
- **CMD-ALL**: `cd /home/user/IAMGOD/trading && PYTHONDONTWRITEBYTECODE=1 python -m pytest -v -p no:cacheprovider tests/test_scalp_live_*.py tests/test_scalp_signals.py` -> **376 passed, 0 failed, 76 s** (log: `scratchpad/work/full_run.log`). Every repo test named below is inside this run and PASSED. `test_scalp_backtest.py` / `test_scalp_data.py` were not run (NOT_RUN).
- **Experiments** (my own, NOT in the repo, in `scratchpad/work/exp/`), run as `cd scratchpad/work/exp && PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -v -s <file>` or `python <file>`:
  X1 `test_exp_v4_08.py` 2 passed | X2 `test_exp_v4_12_13.py` 4 passed | X3 `test_exp_v4_13.py` 3 passed | X4 `x_two_timeline.py` (observational) | X5 `v4_15_child.py fsize|journal|state` (observational) | X6 `test_exp_misc.py` 3 passed (oracle, unknown-schema position, param smuggling) | X7 `test_exp_v4_23.py` 3 passed | X8 `test_exp_v4_17.py` 1 passed | X9 `x_journal_fail.py` | X10 `x_reservation.py` | X11 `x_imports.py`.

Test aliases: R=rules, E=engine, B=broker, I=integration, N=notes1, S=restartsafety, V=review, T3=round3, T4=round4, U=runtime, SG=signals (all `tests/test_scalp_live_<x>.py`, SG = `tests/test_scalp_signals.py`).
Status rule I used: NOT_APPLICABLE = the component does not exist by design (no learned policy, no probabilities, no LLM, no DB, no tax engine); MISSING = applies to the bot/lab and no code exists. Default applicability: US equities regular session, SPY/QQQ shares long-only, Alpaca PAPER, account SCALP ...GWRL, IEX live / SIP history, policies ORB5_QQQ v1, LAST30_MOM_SPY v1, NOISE_MOM_SPY v1 (forced SHADOW on IEX).

## 1. Facts record (Section A last paragraph)

| fact | effective value | reference |
|---|---|---|
| decision frequency | Loop and data poll 1 Hz. Signals are evaluated once per completed 1-min bar per symbol and acted on only at the latest bar. ORB5_QQQ once/day (09:34 bar, ~09:35:0x); LAST30_MOM_SPY once/day (15:29 bar, ~15:30:0x); NOISE_MOM_SPY 12 checks/day (bars 09:59,10:29..15:29). Reconcile 5 s busy / 30 s idle; watchdog 15 s; clock-offset check 60 s | `runner.Runner.loop`, `engine.Engine._signals`, `signals.orb5/_last30/NOISE_TIMES`, `config.RECONCILE_EVERY_S=5, RECONCILE_IDLE_EVERY_S=30, WATCHDOG_EVERY_S=15` |
| target horizon | No forecast horizon exists (no model). Implied: ORB5 09:35 -> stop / 10R / 15:50; LAST30 ~20 min (overlay stop 0.5%, target 1.0%); NOISE until band/VWAP exit or 15:50 | `registry.json` (`max_hold: "until_flatten"`, overlay params), `signals.py` |
| entry-expiry | Parent = DAY limit bracket, `extended_hours=False`; unfilled after `ENTRY_TIMEOUT_S=2` s -> cancel request, slot held until broker says canceled (`CANCEL_CONFIRM_S=5` re-request); late bar entry -> `BAR_STALE`; entries only while now < 15:31:00 (`ENTRY_CUTOFF_MIN_BEFORE_CLOSE=29`); lost ack: lookup by client id, give up after 10 s (`engine.UNCERTAIN_GIVE_UP_S`) | `engine._advance`, `_refresh`, `orders.validate` (tif must be day) |
| max holding time | Nothing overnight. Flatten 15:50 (`FLATTEN_MIN_BEFORE_CLOSE=10`), kill if anything open 15:55 (`KILL_MIN_BEFORE_CLOSE=5`), outside watchdog 15:57 (`WATCHDOG_FLAT_MIN_BEFORE_CLOSE=3`); half days refused | `clock.SessionTimes`, `engine._clock_rules` |
| multipliers | Shares, multiplier 1; no leverage (`GROSS_NOTIONAL_MAX_X_E0=1.0`); no futures/options code (no `multiplier` field anywhere) | `config`, `sizing.qty` |
| tick / lot | Prices in whole cents (Decimal; buys and stops rounded DOWN, sells UP, target half-up); whole shares only, `qty` int >= 1; `EXPLORATORY_MAX_QTY=1`; target must exceed limit + $0.01; sub-penny / half-penny tick (Nov 2027) not handled | `orders.round_down_cent/round_up_cent/round_cent`, `orders.validate` |
| order types | Limit only: BUY bracket (limit parent + take-profit limit + stop-LIMIT), simple SELL limit; TIF day. No market, stop-market, trailing, replace/modify call in the package | `orders.py`, `broker.AlpacaBroker.request_for`; R::test_mt_g21_order_builder_has_no_market_or_stop_order_path, U::test_runtime_modules_build_orders_only_through_the_order_builder |
| fee provenance | `FEE_TABLE` rows with start/end, source URL, verified flag: SEC s31 $0 to 2026-04-03 then $20.60 per $1M sales (verified); FINRA TAF $0.000195/sh sold, cap $9.79, round up (Q4-2026 pause row: pass-through UNVERIFIED, kept charging); CAT $0.000001 + $0.000002/sh both sides (verified; Alpaca rounding UNVERIFIED); Alpaca commission 0. Raises for a date no row covers. `HONEST_SLIP_PER_SHARE=0.01` per side. Sources read by the build session on 28 Sept; I could not re-check offline | `costs.py::FEE_TABLE, fee_breakdown` |
| data entitlements as used | Live: Alpaca Basic free IEX via REST polling (~2 data requests/s). History: SIP bars/quotes/trades, >=16 min old (`data.DELAY`). Halt/LULD status unavailable on IEX (treated as unknown). Every price carries `Feed` (IEX/SIP/SIM); `FEED_MISMATCH` label. `operating_costs.json`: data $0 with URL, no verification date. `data.keys()` may fall back to the RULES key pair for data | `market.LiveMarket`, `market.SipQuoteSource`, `model.Feed` |
| account restrictions checked | Paper lock before any network call (SCALP key names only, paper URL only); account number starts "PA", ends `GWRL`, equals `account.pin`; buying power from `non_marginable_buying_power` and settled cash; no short path (sell <= free long qty). READ BUT NOT GATED: `status`, `trading_blocked`, `shorting_enabled`, `pattern_day_trader` (only printed by `check-account`) | `broker.AlpacaBroker.__init__/account/submit`, `risk.settled_cash` |

Worked example (real builder, SPY 766.00x766.01): limit 766.03, stop 762.19, stop-limit 760.27, target 773.69, 1 share, risk/share $5.76, id `SCALP-L30S-260929-1529-E0-<h6>`.

## 2. Requirement table (handoff A-K)

Columns: id | requirement | status | code / config | test (result) | assumption -> minimal change.
IAT = IMPLEMENTED_AND_TESTED, IU = IMPLEMENTED_UNVERIFIED, MIS = MISSING, NA = NOT_APPLICABLE, CON = CONFLICT.

| id | requirement | status | code / config | test (all PASS in CMD-ALL unless X) | assumption -> change |
|---|---|---|---|---|---|
| S-1 | take market/broker/feed facts from code and metadata, no secrets | IU | section 1 | none | live account metadata comes from MINUTE_TRADING.md, not read (no network) -> run `check-account` |
| S-2 | reuse the app, do not rebuild | IAT | this package | n/a | none |
| S-3 | keep stricter safeguards and permissions | IAT | `config.py` constants | R::test_mt_g41_every_guardrail_constant_is_locked | none |
| S-4 | profit is not deployment authorization | IAT | VALIDATED lane refused (`config._registration`) | R::test_validated_lane_is_impossible_in_v1 | none |
| A-1 | per-requirement 8-field record | IU | this report | n/a | keep with the artifact log |
| A-2/A-3 | no reference = not IAT; unrun test = NOT_RUN | IAT | applied here | CMD-ALL | none |
| A-4 | report conflicts, do not resolve | IU | section 6 | n/a | none |
| A-5..A-14 | record frequency, horizon, expiry, max hold, multipliers, tick/lot, order types, fee provenance, entitlements, account restrictions | IU | section 1 | order types: R::test_mt_g21_order_builder_has_no_market_or_stop_order_path; fees: R::test_mt_g1_fee_table_refuses_a_date_no_row_covers | facts live in code, not in one "effective config" dump -> add a `config-dump` command |
| A-15 | separate concepts, no single "timeframe" | IAT | separate constants in section 1 | R::test_mt_g41_every_guardrail_constant_is_locked | none |
| B-1 | classify every rule | IU | section 4 | none | keep section 4 as the table |
| B-2 | hard controls immune to optimizers | IAT | constants + `risk_hash`; sizing has no free arg | R::test_mt_g14_sizing_signature_is_fixed_and_forbidden_keywords_raise, U::test_mt_g41_risk_hash_mismatch_disables_entries, X6 param smuggling PASS | no optimizer exists yet |
| B-3 | baseline versions preserved | IAT | `Registration.code_hash` | R::test_mt_g10_committed_registry_hashes_equal_the_code, R::test_mt_g10_a_changed_parameter_is_caught | guardrail changes (Patch C/G) kept version 1 (see 6A C-7) |
| B-4 | learnable variation inside an approved envelope | NA | no learned policy | none | define envelope when introduced |
| B-5 | scope each rule to policy ids | IU | per-setup keys (caps, cooldown, lane, max_hold); most hard constants global | E::test_mt_g40_restart_after_three_trades_and_0_9pct_loss_keeps_the_counts | section 4D lists global->per-policy items |
| B-6/B-7 | NEUTRAL-state trading only when hard gates pass; cannot bypass data/halt/account/event/risk | NA (states) / IAT (gates) | no ER20 router; `risk.entry_check` gates every candidate | R::test_every_failing_reason_is_listed_not_just_the_first | none |
| B-8 | keep versions with/without filters distinct | IU | MT-G10 hashes; risk_hash on `start` line only | N::test_patch_c_registry_max_hold_is_required_and_no_version_was_bumped | stamp risk_hash on each trade line |
| B-9 | docs/LLM prose cannot override effective config | IU | constants in code, DESIGN.md list matches config (67/67 by script) | R::test_mt_g41_every_guardrail_constant_is_locked | doc drift exists elsewhere (6C) |
| B-10 | reject unresolved conflicts at startup | IU | `config.load_registry` raises `RegistryError`; risk/code hash mismatch blocks | R::test_registry_refuses_unknown_setups_and_bad_fields, R::test_mt_g24_empty_source_is_refused | no generic conflict detector |
| B-11 | production unchanged unless approved | IAT | MT-G10, MT-G27 deploy guard | U::test_mt_g27_deploy_in_market_hours_with_changed_code_blocks_entries | none |
| B-12 | learned exit cannot modify an open baseline position's stops | IU | no replace/modify path exists; ownership in `Trade.setup_id` | E::test_mt_g16_stop_unconfirmed_goes_flat | add AST test: no `replace_order` in package |
| C-1..C-2 | opportunity != human signal minutes; common decision grid | MIS | decisions journalled only when a setup fires (`engine._journal_decision`) | none | add per-minute `grid` journal line |
| C-3 | record available state | IU | `market.Recorder` records every snapshot | U::test_live_market_records_every_poll_and_the_recording_plays_back | raw state only |
| C-4..C-8 | which strategies fired, feasible actions, costs, gate reasons, ordinary minutes and no-entry actions | MIS | reasons only for candidates | none | same grid line |
| C-9 | predictive labels where future exists | NA | no labeling | none | research |
| C-10 | executable outcomes marked observed/modeled/unknown | IU | real fills: PENDING_VERIFY / `tp_verified` / `tp_missed`; counterfactuals unlabeled | V::test_mt_g4_a_take_profit_fill_is_pending_verify_and_kept_out_of_the_gates, T3::test_v3_2_a_take_profit_the_sip_never_traded_through_is_a_missed_fill_at_0r | label shadow outcomes |
| C-11 | no real-money exploration; no imputed fills | IAT | paper lock | B::test_mt_g36_a_live_url_override_is_refused_before_any_network_call | none |
| C-12..C-14 | M1 and baseline same universe; scanner = selection experiment; top-volume universe study | NA | allowlist SPY/QQQ (MT-G23); trial counting MT-G7 not built | R::test_mt_g23_symbol_outside_the_allowlist_is_refused | see 6A C-5 |
| D-1..D-9, D-12, D-13 | calibration contract, reliability bins, Brier/log loss, coverage, selected-subset, no recalibration on test | NA | no probability or interval is produced or used | none | becomes MIS the day a probability feeds a trade (MT-G14 forbids it now) |
| D-10 | data-shift checks with predeclared response | IU | feed tags, `FEED_MISMATCH`, slippage vs model -> SHADOW, stale-data gates | V::test_mt_g35_volume_setup_with_feed_iex_is_shadow_only_and_with_sip_allowed, V::test_mt_g3_median_slippage_over_30_fills_above_1_5x_model_holds_the_setup_in_shadow | no feature-support monitor (no features) |
| D-11 | NO_NEW_RISK never disables exits | IAT | `risk.entry_check` refuses exits; MT-G38 | R::test_mt_g38_exits_never_go_through_the_entry_gate, E::test_mt_g38_setup_exit_is_never_blocked_by_entry_gates | none |
| E-1..E-3 | independent hand reference for fills, cash, P&L, fees, rounding | MIS in repo | existing tests call `costs.pnl_breakdown` itself (N::test_patch_e_excursions_are_measured_from_the_bid_and_journalled_apart_from_pnl, R::test_mt_g4_honest_pnl_marks_paper_down_and_never_subtracts_the_spread_twice) | X1 PASS (hand Decimal reference, Decimal typed, no `costs` call) | adopt X1 |
| E-4 | agreement is not proof | IU | noted | n/a | none |
| E-5 | verify causal order, liquidity, queue, fees in replay | IU | `SimBroker` bar mode legs after fill bar, stop first | E::test_replay_in_bar_mode_fills_the_stop_leg_on_a_later_bar, B::test_sim_bar_mode_checks_legs_on_later_bars_with_the_stop_first | no queue model |
| E-6 | no duplicate liquidity credit | MIS | `SimBroker` fills whole qty against an unchanged quote, ignores sizes | none | irrelevant at 1 share/1 order; add size cap before scaling |
| E-7 | joint fill/payoff (passive adverse selection) | NA | only marketable entries; take-profit needs a print strictly through the limit | I::test_mt_g4_buy_limit_500_fills_in_bar_replay_only_when_the_low_trades_through_it | none |
| E-8 | flat-price fixture with spread and fees | IU -> proposed | engine `_close_trade` | X1 PASS: expected honest P&L -0.060006 by hand equals journal | add X1 to the suite |
| E-9 | rejected / never-filled orders | IU | 403 blocks symbol; unfilled entry cancels | E::test_mt_g25_broker_403_on_entry_is_not_retried_and_blocks_the_symbol, E::test_a_slow_cancel_does_not_free_the_slot_early, X1 no-fill P&L 0 PASS | none |
| E-10 | partial entries and exits | IU | partial entry only (config monkeypatched to 2 shares; production 1 share cannot partial) | E::test_partial_fill_is_protected_at_once | no partial-exit test |
| E-11 | liquidation after interruption | IAT | watchdog, restore | I::test_mt_g39_bot_dies_with_a_position_open_and_the_watchdog_flattens_within_45_seconds, E::test_mt_g40_restore_flattens_a_position_without_a_live_stop | none |
| E-12 | no position, no fill = no gain | IU | none specific | X1 PASS | adopt |
| E-13 | future-informed oracle fails information test | IU | `no_look_ahead` on all 14 real setups | SG::test_no_look_ahead; X6 planted oracle caught PASS | add oracle negative control |
| E-14 | order-size range, capacity | NA | fixed 1 share | none | before any scaling |
| F-1 | risk check + reservation indivisible against authoritative state | IU | single-threaded engine; second proposal sees `Engine.trade` set synchronously; guard reads broker open parents. NO money reservation for pending orders | X2 PASS, X10 (two $70 on $100 both pass money gates while first pending) | slot rule is what protects; reserve pending notional before any 2nd slot |
| F-2 | release only reconciled reservations | IU | cancel is a request; slot held until "canceled"; but pending entry dropped after 10 s of "not found" | E::test_a_slow_cancel_does_not_free_the_slot_early, E::test_a_fill_that_arrives_while_the_cancel_is_pending_is_a_position, X2 | keep entries blocked after `entry_not_found` |
| F-3 | $100 budget, two $70 proposals | see V4-12 | | | |
| F-4 | single execution owner / fencing | MIS | no lock or pidfile in `runner.run` | X4: two processes -> kill + HALT, flat | flock lock (gap G2) |
| F-5 | client ids respect broker dedup contract | IU | deterministic ids; 409/422 -> lookup | B::test_mt_g25_duplicate_client_id_is_looked_up_and_returned, R::test_mt_g25_client_ids_are_deterministic_and_parseable | live uniqueness scope (open vs all orders) unverified; owner saw 422 once |
| F-6a | delayed/lost ack | IU | `engine._submit_entry` (BrokerUnavailable path) | B::test_sim_reject_unavailable_and_duplicate_ids, X3 PASS | add X3 to suite |
| F-6b | fill during cancel | IAT | | E::test_a_fill_that_arrives_while_the_cancel_is_pending_is_a_position | none |
| F-6c | duplicate/out-of-order events | IU | `_book` counts only increases of filled qty | none at engine level | add test |
| F-6d | simultaneous proposals | IU | | X2 PASS | add |
| F-6e | worker death after submission | IAT | restore + watchdog | E::test_mt_g40_restore_cancels_an_unfilled_entry_parent, I::test_mt_g39_bot_dies_with_a_position_open_and_the_watchdog_flattens_within_45_seconds | none |
| F-6f | clock discontinuity | IU | offset gate; watchdog blind if clock steps back (age<0 not stale) | U::test_mt_g22_clock_offset_measured_once_a_minute_and_none_when_the_clock_call_fails | treat age < -5 s as stale |
| F-6g | API rate limiting | IU | 429 -> BrokerUnavailable, entries fail closed; no backoff | B::test_mt_g25_4xx_is_a_reject_and_timeouts_are_unavailable | mapping only tested |
| F-6h | database unavailability | NA (no DB) / state-folder outage = V4-15 | | X5, X9 | see G4 |
| F-6i | rollback with open positions | IU | fail-closed kill on unparsable ids | X6 PASS (unknown id + position -> flat in 4 sim s) | write rollback runbook |
| F-6j | verify no-new-risk, protection, reconciliation, alert routing | IU | routing fails: engine alerts journal-only | see G3 | wire `alert=` |
| F-7 | alert recipient, acknowledgement, no-response action | MIS | `state.alert`; engine has `alert_fn=None` in production | none | G3 |
| F-8 | no guaranteed-liquidation claim | IU | alerts say "close by hand in the dashboard" | E::test_mt_g16_exit_whose_leg_cancels_never_confirm_alerts_and_escalates_to_the_kill | none |
| F-9 | reserve capacity for risk-reducing work; no retry storm | IAT | `guard.py` exit budget 30/min, entries 6/min | E::test_mt_g25_seventh_entry_in_60_s_is_blocked_while_8_exit_resends_are_not, E::test_mt_g25_exit_budget_delays_but_never_raises_runaway | none |
| F-10 | rollback compatible with persisted positions | IU | state rebuilt from broker; deploy guard | U::test_mt_g27_deploy_in_market_hours_with_changed_code_blocks_entries | no schema version, no runbook |
| G-1 | agent has no broker secrets | CON | owner decision 1 vs G-1 | env check: SCALP and RULES key names set here | 6A C-1 |
| G-2 | executor takes validated structured intent | IAT | `orders.entry_bracket`, `broker.check_spec`, `guard` | R::test_mt_g21_order_builder_has_no_market_or_stop_order_path | none |
| G-3..G-5 | no arbitrary tools, NL permission changes, embedded instructions | IU | no text path into orders; files are schema-checked | X8 PASS (hostile text + fake keys: no env read, limits unchanged, no leak) | add X8; no "prompt injection" log (no text feed) |
| G-6 | no needless raw account details | IU | `check-account` prints last 4; `account.pin` pushed by state-save | T3::test_v3_3_state_save_pushes_only_the_whitelist_to_scalp_state_and_restore_brings_it_back | hash the pin |
| G-7 | env/fs/network permissions, secret separation, immutable approvals | MIS | no env-level control in repo | none | owner |
| G-8 | isolated hostile-content test with fake credentials | IU | | X8 PASS | adopt |
| G-9..G-11 | pin model/prompt/tool versions; no stale invented trade; exits independent of model | NA | no model; package imports none (X11: only alpaca, numpy, pandas, requests, urllib3; no dynamic import) | R::test_package_never_imports_an_llm_the_trader_or_the_options_lab | test bans only `anthropic`; widen to an allowlist |
| H-1 | fixed review schedule | IU | reviews at 20/60 sessions (MINUTE_TRADING.md); `TEST_MAX_SESSIONS=60` | R::test_whole_test_stop_at_150_dollars_or_60_sessions | no per-experiment schedule object |
| H-2 | predeclared stop-spending | IAT | `TEST_STOP_USD=150`, `TEST_MAX_SESSIONS=60` locked | R::test_whole_test_stop_at_150_dollars_or_60_sessions | whole test only |
| H-3 | power / sensitivity analysis | MIS | MT-G42 not built | none | research |
| H-4 | no universal trade count; wide = inconclusive | IU | "INSUFFICIENT SAMPLE" below 100 trades / 40 sessions | R::test_mt_g11_insufficient_sample_below_100_trades_or_40_sessions | no interval-width verdict |
| H-5/H-6 | exposure attribution; risk premium vs forecasting | IU | SPY buy-and-hold, exposure-matched SPY, 15-min buckets | V::test_mt_g34_exposure_matched_spy_uses_the_same_dollars_and_minutes | no decomposition |
| H-7 | predeclare objective, tail limits, cost hurdle, dates, search budget | IU | constants locked; operating cost hurdle in report | N::test_v2_20_fixed_costs_above_trading_pnl_give_a_negative_operating_result_without_touching_pnl | no search budget |
| H-8 | retire without touching held-out data | IU | MT-G12 retire at n>=100, mean<=0 | R::test_mt_g12_retire_and_small_samples | holdout (MT-G6) not built |
| I-1..I-4 | data agreements, entitlement source + date, unknown = disabled | MIS / CON | no register | none | 6A C-2 |
| I-5 | exportable lots, cash flows, commissions, corporate actions | MIS | FIFO lots exist only inside `restore.rebuild`; stable ids = client order ids | none | add CSV export |
| I-6 | separate trading P&L, operating profit, tax | IU | `report.operating_block` splits trading vs operating; no tax | N::test_patch_h_committed_operating_costs_record_unknown_hosting_as_not_recorded | none |
| I-7 | no assumed s475(f) election | NA | no tax code (grep: no wash/475) | none | keep it that way |
| I-8 | no spoofing / flooding / defeating restrictions | IAT | entry rate caps, limit orders, genuine bracket | R::test_mt_g25_seventh_entry_submission_in_60_seconds_rejected | none |
| I-9 | venue self-trade prevention respected and tested | IU | exit waits until parent, legs and stray sells are gone; sells capped to free long qty | E::test_mt_g16_exit_whose_leg_cancels_never_confirm_alerts_and_escalates_to_the_kill, B::test_mt_g15_a_sell_larger_than_the_free_long_position_is_refused, X7 PASS | lingering sell does not block a new buy (X7); Alpaca rule text unread |
| I-10 | bona-fide cancels are fine | NA | | none | none |
| I-11 | do not conflate wash sale and wash trade | NA | no tax flag exists | none | none |
| K-1..K-3 | delivery order; no more named strategies; no auto promotion | IAT | VALIDATED impossible | R::test_validated_lane_is_impossible_in_v1 | none |

## 3. Fixtures V4-01 .. V4-24

| id | status | code and test (result) | if no test: sketch |
|---|---|---|---|
| V4-01 | NA | no ER20 router or learned candidate in code (grep). Hard gates bind every candidate: R::test_every_failing_reason_is_listed_not_just_the_first PASS | register a fake setup with router_state=NEUTRAL; assert only hard reasons appear |
| V4-02 | IAT | constants locked R::test_mt_g41_every_guardrail_constant_is_locked PASS; `sizing.qty` has no extra arg R::test_mt_g14_sizing_signature_is_fixed_and_forbidden_keywords_raise PASS; X6: extra registry param `daily_stop_usd=1e6` -> hash mismatch (shadow), `daily_limit` still 25 PASS | none |
| V4-03 | MIS | decisions only when a setup fires (`engine._signals`); raw snapshots in `Recorder` | run a quiet day; assert one `grid` line per completed minute per symbol |
| V4-04 | IU | real orders: PENDING_VERIFY / missed fill V::test_mt_g4_a_take_profit_fill_is_pending_verify_and_kept_out_of_the_gates, T3::test_v3_2_a_take_profit_the_sip_never_traded_through_is_a_missed_fill_at_0r PASS. Counterfactual (shadow) outcomes are never computed | score shadow candidates with a label modeled/unknown |
| V4-05 | NA | no probability output | |
| V4-06 | NA | no calibration | |
| V4-07 | NA | no calibration; sealed-holdout control (MT-G6) not built | |
| V4-08 | IU | engine books via `costs.pnl_breakdown`; repo tests recompute with the same helper (R::test_mt_g4_honest_pnl_marks_paper_down_and_never_subtracts_the_spread_twice uses `X.fees`; N::test_patch_e_excursions_are_measured_from_the_bid_and_journalled_apart_from_pnl uses `X.pnl_breakdown`), so NOT independent. **X1 PASS**: buy 651.01, sell 651.00 flat, hand Decimal: paper -0.01, slip 0.02, SEC 0.02 (0.0134 rounded up), TAF 0.01, CAT 0.000006, honest -0.060006 = journal `trade_closed` -0.0600059999 | adopt X1 |
| V4-09 | MIS | `SimBroker._match_quote` fills full qty, ignores displayed size | two buys on one 100-share ask; assert total fills <= 100 |
| V4-10 | NA | no passive entries; partial: bar fills need a print strictly through the limit I::test_mt_g4_buy_limit_500_fills_in_bar_replay_only_when_the_low_trades_through_it PASS | |
| V4-11 | IU | SG::test_no_look_ahead (14 setups) PASS; X6 planted oracle FAILS the same check, honest rule passes PASS | add X6 to SG |
| V4-12 | IU | No repo test. What stops the second proposal: `Engine._submit_entry` sets `self.trade` synchronously, so `_entry_candidate` adds `POSITION_OPEN` (`t is not None`, engine L1765), `risk.entry_check` adds POSITION_OPEN/NO_ADD/OPEN_PARENT, `GuardedBroker` refuses a 2nd open parent at the broker (kill), reconcile runs before submit. X2 PASS: LAST30 and NOISE on one 15:29 bar -> 1 order, 2nd refused `['POSITION_OPEN','NO_ADD']`; ack lost + never arrived -> 2nd refused, slot held 10 s; broker 403 -> symbol blocked; SPY+QQQ same tick -> 1 order. **But** X10: two $70 plans on $100 both pass the money gates while the first is pending (no cash reservation; `buy_notional` books on fills) | adopt X2; add reservation before any 2nd slot |
| V4-13 | IU | Pieces tested: B::test_sim_reject_unavailable_and_duplicate_ids, B::test_mt_g25_duplicate_client_id_is_looked_up_and_returned, E::test_mt_g40_restore_cancels_an_unfilled_entry_parent, E::test_mt_g40_restore_adopts_a_protected_position. X3 PASS: ack lost after arrival -> found by client id, 1 order, restart adopts protected position, re-fired signal not proposed; arrived unfilled -> restart cancels, re-fired signal reuses the same id and the broker returns the original (1 parent order; engine counter reads 2 submits); never arrived -> restart re-sends the SAME id | adopt X3 |
| V4-14 | CON/MIS (no lock) | No lock in `runner.run`. X4: two engines, one account: B refuses `RECONCILE_MISMATCH` (15:30:01), kills at 15:30:04 (cancel all, sell, HALT), A loses its exit (`exit_rejected`, `trade_unbooked`), account flat; if B starts later it adopts the same position and both kill at 15:50. Protections: deterministic ids, reconcile, guard open-parent check, broker sell cap, Alpaca no_shorting | flock lock (G2) + test |
| V4-15 | IU | X9/X5: entry with failing journal -> tick raises, 0 orders (fail closed); 15:50 exit with failing journal -> raises, position stays with bracket legs, 0 exits; `request_kill` raises. X5 fsize: runner dies on first heartbeat, watchdog flattens (~45 s) then dies (HALT never written); journal-only: runner died after 53 ticks at +1 min mark; state-only: watchdog flattens, HALT write fails repeatedly. No DB in this bot | wrap post-flatten writes in watchdog (G4) |
| V4-16 | IU | X6 PASS: position whose client id the code cannot parse is not adopted, reconcile halts, flat in 4 sim s. No versioned schema, no rollback runbook | write runbook + test |
| V4-17 | IU | X8 PASS (fake keys, hostile text in registry, events, KILL file, changes.log: engine read no env var, limits unchanged, no key in files). Boundary at environment level fails: real key names are set in this agent's environment (6A C-1) | adopt X8 |
| V4-18 | IU | X11: imports only alpaca, numpy, pandas, requests, urllib3; no LLM module loaded; no dynamic import/exec/eval. R::test_package_never_imports_an_llm_the_trader_or_the_options_lab PASS but bans only `anthropic` | AST allowlist test |
| V4-19 | IU | benchmarks only: V::test_mt_g34_exposure_matched_spy_uses_the_same_dollars_and_minutes PASS | add decomposition |
| V4-20 | IU | R::test_mt_g11_insufficient_sample_below_100_trades_or_40_sessions, R::test_whole_test_stop_at_150_dollars_or_60_sessions PASS; constants locked | add "INCONCLUSIVE" verdict |
| V4-21 | MIS/CON | no entitlement register (6A C-2) | |
| V4-22 | NA | no tax logic; nothing assumes an election | |
| V4-23 | IU | X7 PASS: at every exit-sell submit nothing else was open (fast and 4 s-delayed cancels). E::test_mt_g16_exit_whose_leg_cancels_never_confirm_alerts_and_escalates_to_the_kill, S/V::test_mt_g40_restart_while_an_exit_sell_rests_waits_for_its_cancel_and_never_oversells (V), B::test_mt_g15_a_sell_larger_than_the_free_long_position_is_refused PASS. Gap: a new BUY is accepted while a lingering SELL is open (X7) | see G8 |
| V4-24 | MIS | no capability-table tooling; MINUTE_TRADING.md "2056 tests" has no artifact; this report applies the rule (CMD-ALL log). No CI workflow for scalp tests | script that fails a row marked IAT without an existing artifact path |

## 4. Rule classification (Section B)

H = HARD_CONTROL, B = BASELINE_POLICY_RULE, L = LEARNABLE_POLICY. All 93 upper-case names in `config.py` were checked against my table (script asserts none missing); they fall in these groups.

| constants | class | scope | note |
|---|---|---|---|
| `ALLOWED_SYMBOLS, SHORTS_ENABLED` | H | all | shorts should be per policy and side (owner OK) |
| `MAX_ROUND_TRIPS_DAY, MAX_ENTRY_SUBMITS_DAY, MAX_ENTRY_SUBMITS_PER_MIN, MAX_OPEN_PARENTS, MAX_NOTIONAL_DAY_X_E0, MAX_EXIT_ORDERS_PER_MIN, GROSS_NOTIONAL_MAX_X_E0` | H | whole bot | global -> add per-policy sub-budgets under the ceiling |
| `MAX_ROUND_TRIPS_SETUP, STOPOUT_REENTRY_MIN` | H | per policy (and symbol) | already per policy |
| `MAX_OPEN_POSITIONS` | H | whole bot | locked by a test but read by no runtime code; the single `Engine.trade` slot enforces it; baseline and candidate would compete for it |
| `RISK_PCT, NOTIONAL_CAP_PCT, EXPLORATORY_MAX_QTY` | H | ceiling whole bot; qty by lane | a learned policy needs its own approved envelope |
| `DAILY_STOP_USD, DAILY_STOP_PCTS, WEEKLY_STOP_PCT, DRAWDOWN_HALT_PCT` | H | whole bot | at E0 = $1,000,000 only the $25 daily and $150 test stops can bind |
| `TEST_STOP_USD, TEST_MAX_SESSIONS` | H | whole test | per-experiment budgets missing (H-2) |
| `LOSS_STREAK_N, LOSS_STREAK_PAUSE_MIN` | H | whole bot | global -> count per policy, keep global backstop |
| `ENTRY_COLLAR_*, STOP_LIMIT_*, EXIT_COLLARS, KILL_COLLARS, STOP_ESCALATION_*, STOP_WATCHDOG_S, ENTRY_TIMEOUT_S, STOP_CONFIRM_S, EXIT_ACK_S, CANCEL_*, HTTP_TIMEOUT_S, LOCK_WAIT_S` | H | all | execution shape is global and in the risk hash; passive entries or other stops need a policy-scoped envelope; entry patience could be L only up to a hard max |
| clock/event: `OPEN_BLOCK_MIN, ENTRY_CUTOFF_*, FLATTEN_*, KILL_*, WATCHDOG_FLAT_*, RELEASE_BLOCK_*, FOMC_BLOCK, EVENT_*, FOMC_EVENT_TIMES, MAX_HOLD_UNTIL_FLATTEN` | H | all | per-policy data: `opening_window`, `tested_on_release_days`, `max_hold` (B for v1; L inside the 15:50 ceiling) |
| data: `CLOCK_OFFSET_MS, DATA_SILENCE_S, QUOTE_MAX_AGE_S, BAR_MAX_AGE_S, MAX_SPREAD_*, MAX_PRICE_VS_LAST_TRADE, WILD_MINUTE_*, LULD_PCT, MWCB_DROP, HALT_SUSPECT_*` | H | all | a learned policy may abstain at a narrower spread, never accept a wider one |
| `RECONCILE_*, MISMATCH_*, HEARTBEAT_STALE_S, WATCHDOG_EVERY_S, HONEST_SLIP_PER_SHARE` | H | all | slippage model is per policy (`model_slip_bps`) |
| `SLIP_MODEL_*, SLIP_MIN_FILLS, VERSION_MIN_SESSIONS, MIN_SAMPLE_*, SWITCH_OFF_N, RETIRE_N` | H | per policy version | already per policy |
| `ORDER_PREFIX, SETUP_CODES, RISK_FILES, MARGIN_FRAMEWORK*, LIVE_DIR, TRADING_DIR, REGISTRY_PATH, EVENTS_PATH, STATE_DIR` | H | all | margin items are record-only |
| registry per policy: entry/exit definitions, overlay 0.5%/1.0%, 10R target, noise band, `uses_volume`, `model_slip_bps` | B | per policy id | frozen by `code_hash` (signals.py, sizing.py, orders.py + params) |
| registry `lane`, `version`, `code_hash`, `source` | H | per policy | experiment-access boundary |
| L (future): features, actions, abstention, horizon inside 15:50, exit choice made before entry | L | separately approved envelope | nothing in config is L today |

MT-G rules built and their class: G2, G3, G4, G10-G13, G14, G15, G16, G17, G18, G19, G20, G21, G22, G23, G24, G25, G26, G27, G33, G34, G35, G36, G38, G39, G40, G41 = H (G16: bracket/never-widen H, each setup's stop/target definition B, a learned exit only if chosen BEFORE entry). Not built: G1 (as a gate), G5-G9, G28, G29-G32 (no LLM), G37, G42. Per-policy today: caps per setup, stop-out cooldown, lane, switch-offs, halt block per symbol. Global but should also be per policy: single slot, daily budgets, loss-streak pause, test budgets, shorts switch, execution shape.

## 5. Gaps ranked for Tue 29 Sept 2026, 08:30 ET start

Facts checked: calendar covers 29 Sept; ORB5 at 09:35:01 is refused `EVENT_HORIZON_OVERLAP` (Consumer Confidence + JOLTS 10:00); LAST30 at 15:30:01 has no clock/event reason; NOISE is SHADOW on IEX; shorts off, so a negative first-half-hour return means `SHORT_DISABLED` (about half of days). Current risk hash `e140c4299233ca8fe8215616e41bdfd48ccf24d4c0684c008d6269253d16b4dc`; registry hashes match.

| rank | severity | what could go wrong | minimal change | before 08:30? |
|---|---|---|---|---|
| G1 | blocker if unchecked | `SCALP_RISK_HASH` unset in this sandbox: an old stored value refuses every entry (`RISK_HASH_MISMATCH`), unset = tamper check empty. If the 28 Sept manual test order had a `SCALP-<code>-E` id, the broker shows a SCALP fill with no local paper journal -> that setup starts SHADOW ("STATE NOT RESTORED"); evaluated once at start | none in code: compare `python -m lab.scalp.live hash`, run `check-account`, read the start line "entry blocks at start" and `startup` journal; if needed `state-restore` or logged `accept-journal-gap --session 2026-09-28 --setup LAST30_MOM_SPY/SPY --reason ...`, then restart before 09:00 | yes, 10 min; do not edit config/risk/sizing/orders |
| G2 | major | Two bot copies: X4 shows kill + HALT, lost trade, missing P&L in one journal; account ends flat, no oversell | `runner.run`: non-blocking flock on `state/scalp/runner-<mode>.lock` (~15 lines + test) | yes with the owner's two-reviewer routine; else operational rule: one launcher, `pgrep -af 'lab.scalp.live run'` empty before start |
| G3 | major | Engine alerts (kill, daily stop, reconcile halt, "close by hand") reach only the journal; docs say alerts.log | pass `alert=lambda m,f: S.alert(state_dir, clock(), m, **f)` through `make_engine` (~8 lines + test) | yes; or tail journal for `"kind":"alert"` |
| G4 | major impact, low likelihood | State folder unwritable: bot dies at first heartbeat, no 15:50 exit, kill cannot start; watchdog flattens in ~45 s then dies without writing HALT (X5, X9) | wrap post-flatten writes in `watchdog.check/run_watchdog` (~15 lines + test) | yes, low priority |
| G5 | minor | Watchdog shares the host with the bot and its liveness is never checked (`start_watchdog` Popen unpolled; tests stub it); host death could leave a 1-share position overnight (next start would sell it) | poll `wd_proc` 2 s after start and block entries if dead (~8 lines) | yes for the poll; second host no |
| G6 | minor (expectation) | live IEX path has never run a full PAPER day; single chance can be refused by `QUOTE_STALE`, `SPREAD_TOO_WIDE`, `CLOCK_OFFSET`, `BAR_STALE`, late bar | none; do not loosen gates | n/a |
| G7 | minor | pending entry dropped after 10 s "not found" is not proof; late order handled by reconcile kill | block entries after `entry_not_found` (~6 lines) | yes, low priority |
| G8 | minor | new BUY accepted while an old SELL lingers (X7); Alpaca could reject as wash trade -> symbol blocked | add lingering sells to `EntryContext` (changes risk hash) | no |
| G9 | minor | clock stepped back makes heartbeat age negative; watchdog blind | treat age < -5 s as stale (2 lines) | yes |
| G10 | minor | no money reservation for pending orders (X10); safe with one slot | reserve pending notional (risk hash changes) | no |
| G11 | minor | no CI, no kept test artifact | `pytest --junitxml` before each start | yes |
| G12 | owner | paper + RULES keys in agent env; data terms unread; `account.pin` pushed; no rollback runbook; a deploy after 09:00 blocks entries | decisions | n/a |

## 6. Conflicts (reported, not resolved)

6A. Handoff vs MT-G rules / owner decisions
- **C-1** G-1 (no broker secrets for the code agent) vs owner decision 1 (SCALP keys put in the agent environment). Here ALPACA_SCALP_* and ALPACA_RULES_* names are both set (values never read); `lab/scalp/data.py::keys()` falls back to RULES keys. Paper keys are not read-only.
- **C-2** I-4/V4-21 (unknown data permission = disable path) vs the owner-approved paper session using Alpaca Basic IEX/SIP, local recordings and journals pushed to `scalp-state`. No entitlement register.
- **C-3** D/B (probabilities may size trades; learned exits/horizons) vs MT-G14 (fixed sizing, `confidence` argument raises), MT-G16/G33 (only pre-set exits), MT-G29, MT-G10. Adopt only offline/shadow.
- **C-4** F assumes a transactional DB; owner fact: no database. Do not add one; use a file lock plus the broker as authority.
- **C-5** C-13/C-14 scanner universe vs MT-G23 and owner verdict "Patch A skipped". Research only.
- **C-6** H-6 (risk premium is valuable) must not relax MT-G5(b) (beat exposure-matched SPY).
- **C-7** B-3/B-8 vs MT-G10 exemption: Patch C/G changed v1 behaviour without a version bump; tension only, since these are hard gates.
- **C-8** G-6 vs `state-save` pushing `account.pin` (full paper account number).
- **C-9** F-7 vs docs: engine alerts do not reach alerts.log.

6B. Where the code is already better than the handoff wording: exits never gated (MT-G38); cancel request is not a cancel and the slot is held (F-2); deterministic client ids with lookup before resend (F-5); fail-closed unknowns (calendar, hashes, journal gap, halt status); separate-process watchdog and HALT rebuilt from broker history; state rebuilt from the broker, unexplained order or position halts; dated, sourced fee table that raises on uncovered dates and PENDING_VERIFY for resting fills; feed tags with FEED_MISMATCH; guard module independent of decision code with a separate exit budget; paper lock before any network call; pre-open kill-switch self-test.

6C. Doc vs code (do not trust docs): alerts.log claim (above); `MAX_OPEN_POSITIONS` locked but unread; MT-G41 "CI test" but no workflow; MT-G19 shadow trades flagged but never scored; MT-G4 NBBO-size cap not built; MT-G1, G5-G9, G28, G29-G32, G37, G42 not built (owner knows).

## Not verified (no network / no broker)
Live Alpaca behaviour (duplicate-id scope, wash-trade rule text, rate limits, real IEX quote quality), the 28 Sept manual-test client id, the owner's runtime value of `SCALP_RISK_HASH`, fee/data sources (read by the build session only), and the full 2056-test repo suite (only the 376 scalp tests were run).
