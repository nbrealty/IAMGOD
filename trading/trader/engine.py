"""One daily run of one book (BUILD_SPEC "How a daily run flows").

1 settle last run's orders -> 2 account, positions, reconcile -> 3 marks and equity -> 4 breakers ->
5 regime -> 6 data checks -> 7 sleeve weights -> 8 rule plans and shadow rules -> 9 measurement ->
10 context -> 11 Claude (review or decision, several samples) -> 12 data block and risk engine ->
13 orders and pending bookkeeping -> 14 store records, journal, save.

`prepare_book` runs steps 1-10 without touching the broker's orders or the saved state and writes the
session's pending folder (Option B). `run_book` runs all 14 steps through the same code, so the context a
session answers is exactly the context the run checks the answer against.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import consensus, decisions, ledger, metrics, risk, session, shadow, shadow_rules
from . import strategies as strat
from .broker import Broker, make_client_order_id, new_suffix
from .config import CONFIG_DIR, STATE_DIR, Config
from .data import Bars, problem_symbols, validate
from .decisions import apply_review  # noqa: F401  (re-exported: the review lives in decisions.py)
from .ledger import reconcile, update_lots  # noqa: F401  (re-exported for old callers)
from .llm import BOOK_ROLE, ClaudeError, decision_tags, jsonable, prompt_version
from .models import Lot, SleevePlan, Target
from .regime import Regime, classify, classify_kwargs
from .risk import RiskEngine, breaker_status
from .schemas import (ACTION_CODES, CONTEXT_SCHEMA, DEVIATION_CODES, RESTRICTED_SKIP_CODES, SKIP_CODES,
                      WEIGHT_UP_CODES, ClaudeDecision, ResolvedDecision)
from .state import BookState, fingerprint, journal, kill_switch_on, log_experiment

BOOKS = ("rules", "claude")
SLEEVES = ("A", "B", "C", "D")
BENCH_CLOSES = ("SPY", "IEF", "EFA", "DBC", "VNQ", "BIL")  # M-1 benchmarks, M-4 (stored on every equity row)
EPS = 1e-9
SHADOW_REGIME_FIELDS = ("credit_canary",)  # REG-6 is TEST FIRST: journal only, never in Claude's context
C_INDICATORS_SHOWN = 15


# --- sleeve weights ---------------------------------------------------------------------------


def _basket_vol(bars: Bars, symbols: list[str], periods: int = 252) -> float:
    series = [bars[s]["close"].pct_change() for s in symbols if s in bars and len(bars[s])]
    if not series:
        return float("nan")
    rets = pd.concat(series, axis=1).iloc[-60:]
    if rets.empty:
        return float("nan")
    return float(rets.mean(axis=1).std() * np.sqrt(periods))


def normalize_weights(cfg: Config, weights: dict[str, float], promoted=(), demoted: dict | None = None
                      ) -> dict[str, float]:
    """Bound sleeve weights (RISK-7, RISK-8, D off, M-11, cash buffer). Delegates to decisions.cap_weights."""
    return decisions.cap_weights(cfg, weights, promoted, demoted)


def rules_sleeve_weights(cfg: Config, bars: Bars, promoted=(), demoted: dict | None = None) -> dict[str, float]:
    """Inverse-volatility weights inside each sleeve's [min, max] band, then every cap (normalize_weights)."""
    sl = cfg.sleeves
    vols = {
        "A": _basket_vol(bars, sl["A"]["assets"]),
        "B": _basket_vol(bars, sl["B"]["symbols"]),
        "C": _basket_vol(bars, sl["C"]["universe"]),
    }
    if cfg.sleeve_enabled("D"):
        vols["D"] = _basket_vol(bars, sl["D"]["symbols"], 365)
    finite = [v for v in vols.values() if math.isfinite(v) and v > 0]
    med = float(np.median(finite)) if finite else float("nan")
    weights = {}
    for s in SLEEVES:
        if s not in vols:
            weights[s] = 0.0
        elif not (math.isfinite(vols[s]) and vols[s] > 0 and math.isfinite(med)):
            weights[s] = sl[s]["default"]
        else:
            weights[s] = float(np.clip(sl[s]["default"] * med / vols[s], sl[s]["min"], sl[s]["max"]))
    return normalize_weights(cfg, weights, promoted, demoted)


# --- rule plans ---------------------------------------------------------------------------------


def build_plans(cfg: Config, bars: Bars, lots: dict[str, dict[str, Lot]], weights: dict[str, float],
                equity: float, regime: Regime, as_of: pd.Timestamp) -> dict[str, SleevePlan]:
    sl, pol, perm = cfg.sleeves, cfg.policy, regime.permissions
    plans = {
        "A": strat.sleeve_a(bars, sl["A"], equity * weights["A"], lots.get("A", {}), pol, as_of),
        "B": strat.sleeve_b(bars, sl["B"], equity * weights["B"], lots.get("B", {}), pol, equity, perm["B"]),
        "C": strat.sleeve_c(bars, sl["C"], equity * weights["C"], lots.get("C", {}), pol, equity, perm["C"],
                            sectors=cfg.sector_of, sector_max=pol["portfolio"].get("sector_max_positions")),
    }
    if cfg.sleeve_enabled("D"):
        plans["D"] = strat.sleeve_d(bars, sl["D"], equity * weights["D"], lots.get("D", {}), pol, perm["D"])
    return plans


def _plan_targets(plans: dict[str, SleevePlan]) -> list[Target]:
    return [t for p in plans.values() for t in p.targets.values()]


def _lot_qty(lots: dict[str, dict[str, Lot]], sleeve: str, sym: str) -> float:
    lot = lots.get(sleeve, {}).get(sym)
    return float(lot.qty) if lot is not None else 0.0


def _is_increase(t: Target, lots: dict[str, dict[str, Lot]]) -> bool:
    return float(t.qty) > _lot_qty(lots, t.sleeve, t.symbol) + EPS


# --- Claude book: one decision (kept for old callers and tests) --------------------------------------


def decision_to_targets(cfg: Config, decision: ClaudeDecision, lots: dict[str, dict[str, Lot]], bars: Bars,
                        equity: float, log: list[str], *, ctx: dict | None = None, rule_targets: Any = None,
                        weights: dict[str, float] | None = None, permissions: dict | None = None,
                        date: str = "") -> tuple[list[Target], dict[str, float]]:
    """One decision -> Targets, through the same functions the run uses (resolve_actions, resolved_to_targets).

    `weights` are the sleeve weights to fit into (default: the sleeve defaults, capped). Without `ctx` no
    evidence can be checked, so every action is dropped and every key follows `rule_targets`.
    """
    weights = decisions.cap_weights(cfg, weights or {s: cfg.sleeves[s]["default"] for s in SLEEVES})
    prices = risk.last_prices(bars)
    resolved = decisions.resolve_actions(decision, cfg=cfg, ctx=ctx, rule_targets=rule_targets or [], lots=lots,
                                         bars=bars, prices=prices, equity=equity, permissions=permissions,
                                         weights=weights)
    log += resolved.problems
    targets, _ = decisions.resolved_to_targets(
        resolved, lots=lots, prices=prices, equity=equity, weights=weights, date=date, log=log,
        position_limits=decisions.max_positions(cfg),
        deviation_threshold=float(cfg.policy["claude_limits"]["deviation_threshold"]))
    return targets, weights


# --- helpers for the context ----------------------------------------------------------------------


def _r(x, nd: int = 4):
    """Rounded finite float, else None (the context and journal never carry NaN)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, nd) if math.isfinite(v) else None


def _exposure(cfg: Config, lots: dict[str, dict[str, Lot]], prices: dict[str, float]) -> dict[str, float]:
    """M-4 / M-5 inputs: notional per sleeve, and per sleeve-A asset (A_cash is BIL held in A)."""
    a = cfg.sleeves["A"]
    out = {s: 0.0 for s in SLEEVES}
    out["A_cash"] = 0.0
    for sym in a["assets"]:
        out[f"A_{sym}"] = 0.0
    for sleeve, held in lots.items():
        for sym, lot in held.items():
            px = prices.get(sym) or lot.entry_price
            notional = float(lot.qty) * float(px)
            out[sleeve] = out.get(sleeve, 0.0) + notional
            if sleeve == "A":
                key = "A_cash" if sym == a["cash"] else f"A_{sym}"
                out[key] = out.get(key, 0.0) + notional
    return out


def _heat(lots: dict[str, dict[str, Lot]], prices: dict[str, float], equity: float) -> float | None:
    """Open risk: sum of (price - stop) x qty over stopped lots, as a share of equity."""
    if not equity or equity <= 0:
        return None
    total = 0.0
    for held in lots.values():
        for sym, lot in held.items():
            px = prices.get(sym)
            if lot.stop is not None and px is not None:
                total += max(0.0, px - lot.stop) * lot.qty
    return total / equity


def _weight_menu(cfg: Config, prev: dict[str, float], rule: dict[str, float], promoted, demoted) -> dict:
    """CL-10 menu numbers after every limit, one sleeve moved at a time (guide 2)."""
    step = float(cfg.policy["claude_limits"]["weight_step"])
    out = {}
    for s in SLEEVES:
        base = prev[s]
        wanted = {"keep": base, "up": base + step, "down": base - step, "rule": rule.get(s, base),
                  "default": float(cfg.sleeves[s]["default"])}
        out[s] = {}
        for choice, w in wanted.items():
            w = min(max(w, base - step), base + step)
            out[s][choice] = _r(decisions.cap_weights(cfg, {**prev, s: w}, promoted, demoted)[s])
    return out


def _not_eligible_why(cfg: Config, sleeve: str, sym: str, bars: Bars, permissions: dict) -> str:
    if sleeve == "D" and not cfg.sleeve_enabled("D"):
        return "sleeve D is off (D-1)"
    if sleeve != "A" and (permissions.get(sleeve) or 0.0) <= 0:
        return f"the regime gives sleeve {sleeve} no permission today (REG-3)"
    if sleeve == "A":
        return "sleeve A may only buy its assets and BIL (CL-11)"
    if sleeve == "B":
        if sym not in cfg.sleeves["B"]["symbols"]:
            return "not a sleeve B symbol"
        return "close is not above its 200-day average (CL-11)"
    if sleeve == "C":
        if sym not in cfg.sleeves["C"]["universe"]:
            return "not in the sleeve C universe"
        return "does not pass the trend template (C-2) today"
    return "not a sleeve D symbol or no price"


def _compact_stats(stats: dict) -> dict:
    keep = ("n", "n_without_R", "win_rate", "avg_win_R", "avg_loss_R", "E", "SQN", "SQN_label",
            "max_losing_streak", "best_R", "worst_R", "median_hold", "total_pnl", "boot_upper")
    return {s: {k: st.get(k) for k in keep} for s, st in stats.items()}


def build_context(book: str, cfg: Config, state: BookState, bars: Bars, equity: float, cash: float,
                  breakers, regime: Regime, weights: dict[str, float], plans: dict[str, SleevePlan],
                  problems: list[str], as_of: pd.Timestamp, *, broker_name: str = "", simulated: bool = False,
                  rule_weights: dict | None = None, since_change: dict | None = None,
                  eligible: dict | None = None, allowed_skip: tuple = SKIP_CODES, data_notes: dict | None = None,
                  stats: dict | None = None, demotion: dict | None = None, config_dir: Path = CONFIG_DIR) -> dict:
    """The context shown to Claude (schema ctx-2). Every number is computed here; JSON-safe (no NaN)."""
    date = as_of.date().isoformat()
    prices = risk.last_prices(bars)
    E = float(equity)
    pol = cfg.policy
    lim = pol["claude_limits"]
    promoted = tuple(state.promoted_sleeves)
    rule_weights = rule_weights or weights
    stats = stats if stats is not None else metrics.sleeve_stats(state.closed_trades, policy=pol)

    def pct(qty: float, sym: str):
        px = prices.get(sym)
        return _r(qty * px / E, 6) if px is not None and E > 0 else None

    positions = []
    for s, held in state.lots.items():
        for sym, lot in held.items():
            price = prices.get(sym)
            rps = lot.risk_per_share
            positions.append({
                "sleeve": s, "symbol": sym, "lot_id": lot.lot_id, "qty": _r(lot.qty, 6),
                "entry_price": _r(lot.entry_price, 4), "entry_date": lot.entry_date,
                "sessions_held": risk.sessions_held(bars.get(sym), lot.entry_date),
                "stop": _r(lot.stop, 4), "price": _r(price, 4), "pct_equity": pct(lot.qty, sym),
                "unrealized_R": _r((price - lot.entry_price) / rps, 3) if rps and price is not None else None,
            })

    rule_signals = {}
    for s, plan in plans.items():
        cands = list(plan.candidates)
        if s == "C":
            cands = sorted(cands, key=lambda c: -(c.get("rs_pct") or 0.0))[:C_INDICATORS_SHOWN]
        rule_signals[s] = {
            "sleeve_weight": _r(weights.get(s)),
            "targets": [{"symbol": t.symbol, "target_pct_equity": pct(t.qty, t.symbol),
                         "current_pct_equity": pct(_lot_qty(state.lots, s, t.symbol), t.symbol),
                         "stop": _r(t.stop, 4), "reason": t.reason} for t in plan.targets.values()],
            "indicators": cands,
            "notes": list(plan.notes),
            # TEST FIRST shadow signals are not shown: they may never change orders (rulebook, M-12), and a
            # deviation must not cite them as CL-2 evidence. The journal carries them (shadow_signals).
        }

    one_r = {s: _r(cfg.risk_pct(s) * E, 2) for s in ("B", "C", "D")}
    ctx: dict[str, Any] = {
        "context_schema": CONTEXT_SCHEMA,
        "prompt_version": prompt_version(BOOK_ROLE[book], config_dir),
        "date": date,
        "book": book,
        "broker": broker_name,
        "simulated": bool(simulated),
        "account": {
            "equity": _r(E, 2), "cash": _r(cash, 2), "peak_equity": _r(state.peak_equity, 2),
            "drawdown": _r(breakers.drawdown), "day_pnl_pct": _r(breakers.day_pnl_pct),
            "week_pnl_pct": _r(breakers.week_pnl_pct), "month_pnl_pct": _r(breakers.month_pnl_pct),
            "one_R_by_sleeve": one_r,  # RISK-2 per sleeve (a promoted sleeve's 1R differs from the default)
            "breakers": list(breakers.reasons), "halted": bool(breakers.halted),
            "no_new_entries": bool(breakers.no_new_entries), "risk_mult": _r(breakers.risk_mult),
            "watch": bool(breakers.watch), "monthly_block": bool(breakers.monthly_block),
            "sleeve_risk_mult": dict(breakers.sleeve_risk_mult),
            "sleeve_dd_pct": {k: _r(v) for k, v in (breakers.sleeve_dd_pct or {}).items()},
            "sleeve_blocked": dict(state.sleeve_blocked),
            "open_risk_heat_pct": _r(_heat(state.lots, prices, E)),
            "stress": metrics.stress_line(state.lots, prices, E, cfg),
        },
        "regime": {k: v for k, v in regime.to_dict().items() if k not in SHADOW_REGIME_FIELDS},
        "sleeve_bounds": {s: {"min": cfg.sleeves[s]["min"], "max": cfg.sleeves[s]["max"],
                              "default": cfg.sleeves[s]["default"],
                              "cap": _r(cfg.sleeve_weight_cap(s, promoted)), "enabled": cfg.sleeve_enabled(s)}
                          for s in SLEEVES},
    }

    if book == "claude":
        min_s = int(lim["weight_change_min_sessions"])
        since = {s: int((since_change or {}).get(s, decisions.NEVER)) for s in SLEEVES}
        ctx["weights"] = {
            "current": {s: _r(w) for s, w in weights.items()},
            "rules": {s: _r(w) for s, w in rule_weights.items()},
            "menu": _weight_menu(cfg, weights, rule_weights, promoted, demotion),
            "change_allowed": {s: since[s] >= min_s for s in SLEEVES},
            "sessions_since_change": {s: (None if since[s] >= decisions.NEVER else since[s]) for s in SLEEVES},
        }
    ctx["positions"] = positions
    ctx["rule_signals"] = rule_signals
    if book == "claude":
        ctx["menus"] = _menus(cfg, state, bars, plans, prices, E, regime.permissions, eligible)
    else:
        ctx["planned_increases"] = [
            {"sleeve": t.sleeve, "symbol": t.symbol, "current_qty": _r(_lot_qty(state.lots, t.sleeve, t.symbol), 6),
             "target_qty": _r(t.qty, 6), "target_pct_equity": pct(t.qty, t.symbol), "stop": _r(t.stop, 4),
             "reason": t.reason}
            for t in _plan_targets(plans) if t.sleeve in ("B", "C", "D") and _is_increase(t, state.lots)]
    ctx["allowlist"] = cfg.allowlist()
    ctx["reason_codes"] = {"action": list(ACTION_CODES), "deviation": list(DEVIATION_CODES),
                           "weight_up": list(WEIGHT_UP_CODES), "skip": list(allowed_skip)}
    ctx["limits"] = {"deviation_threshold": lim["deviation_threshold"], "weight_step": lim["weight_step"],
                     "weight_change_min_sessions": lim["weight_change_min_sessions"],
                     "max_predictions_per_day": lim["max_predictions_per_day"]}
    ctx["data_problems"] = list(problems)
    ctx["data_feed"] = {"feed_used": (data_notes or {}).get("feed_used"),
                        "notes": list((data_notes or {}).get("notes") or [])}
    hist = state.equity_history
    perf: dict[str, Any] = {"days": len(hist)}
    if len(hist) >= 2:
        perf["book_return"] = _r(hist[-1]["equity"] / hist[0]["equity"] - 1) if hist[0]["equity"] else None
        b0, b1 = hist[0].get("benchmark"), hist[-1].get("benchmark")
        perf["spy_return"] = _r(b1 / b0 - 1) if b0 and b1 else None
    perf["per_sleeve"] = _compact_stats(stats)
    perf["losing_streak_brief"] = metrics.losing_streak_table()
    ctx["performance"] = perf
    ctx["scorecard"] = {
        "predictions": metrics.prediction_scores(state.predictions,
                                                 int(pol["measurement"]["predictions_min_resolved"])),
        "deviations": metrics.deviation_attribution(state),
        "vetoes": metrics.override_report(state),
    }
    ctx["recent_notes"] = state.notes[-5:]
    return jsonable(ctx)


def _menus(cfg: Config, state: BookState, bars: Bars, plans: dict[str, SleevePlan], prices: dict, equity: float,
           permissions: dict, eligible: dict | None) -> dict:
    """CL-10/CL-14 menus per 'S:SYM': the numbers behind each size and stop choice (guide 2)."""
    eligible = eligible if eligible is not None else decisions.eligibility(cfg, bars, permissions)
    rules = {f"{t.sleeve}:{t.symbol}": t for t in _plan_targets(plans)}
    keys = list(rules) + [f"{s}:{sym}" for s, held in state.lots.items() for sym in held]
    keys += [f"{s}:{sym}" for s in SLEEVES for sym in sorted(eligible.get(s, ()))]
    out = {}
    for key in dict.fromkeys(keys):
        sleeve, sym = key.split(":", 1)
        px = prices.get(sym)
        if px is None or equity <= 0:
            continue
        lot = state.lots.get(sleeve, {}).get(sym)
        cur = float(lot.qty) if lot else 0.0
        rt = rules.get(key)
        rule_qty = float(rt.qty) if rt is not None and _r(rt.qty) is not None else cur
        ok = sym in eligible.get(sleeve, set())
        try:
            stops = decisions.stop_menu(sleeve, bars.get(sym), cfg.policy, lot)
        except (KeyError, IndexError, ValueError, TypeError):
            stops = {"rule": None, "tight": None, "keep": None}
        out[key] = {"sleeve": sleeve, "symbol": sym, "price": _r(px, 4), "current_pct": _r(cur * px / equity, 6),
                    "rule_pct": _r(rule_qty * px / equity, 6), "half_rule_pct": _r(0.5 * rule_qty * px / equity, 6),
                    "eligible_increase": ok,
                    "why_not_eligible": "" if ok else _not_eligible_why(cfg, sleeve, sym, bars, permissions),
                    "stops": {k: _r(v, 4) for k, v in stops.items()}}
    return out


# --- the day: steps 1-10, shared by prepare and run --------------------------------------------------------


@dataclass
class _Day:
    book: str
    cfg: Config
    state: BookState
    bars: Bars
    as_of: pd.Timestamp
    date: str
    dry_run: bool
    log: list[str] = field(default_factory=list)
    settled: list[dict] = field(default_factory=list)
    equity: float = 0.0
    cash: float = 0.0
    positions: dict = field(default_factory=dict)
    positions_ok: bool = True
    prices: dict = field(default_factory=dict)
    breakers: Any = None
    demotion: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)
    regime: Regime | None = None
    problems: list[str] = field(default_factory=list)
    bad: set = field(default_factory=set)
    rule_weights: dict = field(default_factory=dict)
    weights: dict = field(default_factory=dict)  # the weights today's plans use (Claude book: previous weights)
    since_change: dict = field(default_factory=dict)
    plans: dict = field(default_factory=dict)
    shadow_results: dict = field(default_factory=dict)
    eligible: dict | None = None
    allowed_skip: tuple = SKIP_CODES
    measurement: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    cost_bps: dict = field(default_factory=dict)
    data_notes: dict = field(default_factory=dict)
    suspect: set = field(default_factory=set)  # symbols whose broker quantity cannot be trusted today


def _slice(bars: Bars, as_of: pd.Timestamp) -> Bars:
    """Bars up to and including `as_of` (a run never sees a later bar)."""
    out = {}
    for s, df in bars.items():
        if df is None or not len(df):
            out[s] = df
            continue
        ts = as_of
        tz = getattr(df.index, "tz", None)
        if tz is not None and ts.tzinfo is None:
            ts = ts.tz_localize(tz)
        elif tz is None and ts.tzinfo is not None:
            ts = ts.tz_localize(None)
        out[s] = df if df.index[-1] <= ts else df[df.index <= ts]
    return out


def _data_notes(data_notes) -> dict:
    if isinstance(data_notes, dict):
        return {"feed_used": data_notes.get("feed_used"), "notes": list(data_notes.get("notes") or [])}
    return {"feed_used": None, "notes": list(data_notes or [])}


def _settle(day: _Day, broker: Broker) -> None:
    """Step 1 (EX-4): book last run's fills at their real prices; outside a dry run cancel what is left."""
    st, cfg = day.state, day.cfg
    fills_of = getattr(broker, "order_fills", None)
    if fills_of is not None and st.pending_orders:
        day.settled += ledger.settle_fills(st, fills_of(st.pending_orders), date=day.date,
                                           asset_class=cfg.asset_class, cost_bps=day.cost_bps, log=day.log)
    if day.dry_run:
        if st.pending_orders:
            day.log.append(f"{len(st.pending_orders)} order(s) from the last run still open (dry run: not cancelled)")
        return
    broker.cancel_open_orders()
    if fills_of is not None and st.pending_orders:
        day.settled += ledger.settle_fills(st, fills_of(st.pending_orders), date=day.date,
                                           asset_class=cfg.asset_class, cost_bps=day.cost_bps, log=day.log)


def _prev_claude_weights(state: BookState, rule_weights: dict) -> dict:
    for row in reversed(state.weight_history):
        w = row.get("weights") if isinstance(row, dict) else None
        if isinstance(w, dict) and w:
            return {s: w.get(s, rule_weights.get(s, 0.0)) for s in SLEEVES}
    return dict(rule_weights)


def _prepare_day(book: str, cfg: Config, bars: Bars, broker: Broker, as_of: pd.Timestamp, state: BookState,
                 state_dir: Path, dry_run: bool, data_notes=None, allow_all_zero: bool = False) -> _Day:
    """Steps 1-10. Only step 1 differs with dry_run (no cancel); nothing here saves or sends orders."""
    bars = _slice(bars, as_of)
    day = _Day(book, cfg, state, bars, as_of, as_of.date().isoformat(), dry_run, data_notes=_data_notes(data_notes))
    st, pol, date, log = state, cfg.policy, day.date, day.log
    bench = cfg.playbook["regime"]["benchmark"]

    # 0. splits: the bars are split-adjusted, so lots, pending orders and the simulator move to today's units
    splits = ledger.apply_splits(st, bars, date, log, simulated=_simulated(broker))

    # 1. settle (EX-5 cost model first: measured slippage may raise it)
    day.cost_bps = ledger.measured_cost_model(st, pol)
    _settle(day, broker)

    # 2. account and reconcile (never against a positions call that failed)
    day.equity, day.cash = broker.account()
    day.prices = risk.last_prices(bars)
    closes = risk.last_valid_closes(bars)
    try:
        day.positions = dict(broker.positions())
    except Exception as e:  # a failed call must never read as "the account is flat"
        day.positions, day.positions_ok = {}, False
        log.append(f"broker positions unavailable ({e}); reconcile skipped and no orders will be sent today")
    suspect: set = set()
    if day.positions_ok:
        lagging = set() if _simulated(broker) else ledger.split_lagging(st, splits, day.positions, log)
        suspect = ledger.reconcile(st.lots, day.positions, log, state=st, prices=closes, date=date,
                                   skip_symbols=lagging, allow_all_zero=allow_all_zero) | lagging
    else:
        suspect = {sym for held in st.lots.values() for sym in held}
    day.suspect = set(suspect)

    # 3. marks and equity (M-1, M-4, M-5, RISK-13 inputs)
    ledger.update_marks(st, bars, date, log=log)
    day_pnl, week_pnl = st.record_equity(
        date, day.equity, closes.get(bench, float("nan")),
        closes={s: closes[s] for s in BENCH_CLOSES if s in closes},
        exposure=_exposure(cfg, st.lots, closes))

    # 4. breakers (RISK-9 to RISK-13, M-11); latches live in memory and are saved only by a real run
    day.stats = metrics.sleeve_stats(st.closed_trades, policy=pol)
    day.demotion = metrics.demotion(day.stats, pol)
    reasons = metrics.demotion_reasons(day.stats, pol)
    for s, why in risk.sleeves_to_latch(cfg, day.equity, st.sleeve_pnl).items():
        if s not in st.sleeve_blocked:
            st.sleeve_blocked[s] = why
            log.append(f"sleeve {s}: new entries stopped until the owner runs `trader sleeve-reset {s}` ({why})")
    for s, level in day.demotion.items():
        if level == "stop" and s not in st.sleeve_blocked:
            st.sleeve_blocked[s] = f"M-11 demotion: {reasons.get(s, 'expectancy below the floor')}"
            log.append(f"sleeve {s}: demoted (M-11), new entries stopped until the owner reviews")
    day.breakers = breaker_status(cfg, day.equity, st.peak_equity, day_pnl, week_pnl, st.halted,
                                  kill_switch_on(state_dir), **risk.loss_inputs(st.equity_history, date, day.equity),
                                  sleeve_pnl=st.sleeve_pnl, sleeve_blocked=st.sleeve_blocked, demotion=day.demotion)
    if day.breakers.drawdown >= pol["breakers"]["drawdown_halt"] - 1e-12:
        st.halted = True
    row = st.equity_history[-1]
    row["sleeve_cum"] = {s: _r(r.get("cum"), 2) for s, r in st.sleeve_pnl.items() if isinstance(r, dict)}
    row["halted"] = bool(st.halted)

    # 5. regime
    rcfg = cfg.playbook["regime"]
    day.regime = classify(bars, bench, cfg.stock_universe(), rcfg["canaries"], **classify_kwargs(rcfg))

    # 6. data checks (EX-7): symbols with problems get no increases today
    dc = pol.get("data_checks", {})
    day.problems = validate(bars, cfg.allowlist(), as_of, max_stale_days=dc.get("max_stale_days", 5),
                            max_daily_move=dc.get("max_daily_move", 0.25))
    day.problems += [f"{s}: broker position looks wrong today, no increases (reconcile skipped)"
                     for s in sorted(suspect)]
    day.bad = problem_symbols(day.problems) | set(suspect)

    # 7. weights
    promoted = tuple(st.promoted_sleeves)
    day.rule_weights = rules_sleeve_weights(cfg, bars, promoted, day.demotion)
    if book == "claude":
        wproblems: list[str] = []
        day.weights = decisions.cap_weights(cfg, _prev_claude_weights(st, day.rule_weights), promoted, day.demotion)
        idx = bars[bench].index if bench in bars else None
        day.since_change = decisions.sessions_since_change(st.weight_history, idx, date, wproblems)
        log += wproblems
    else:
        day.weights = dict(day.rule_weights)

    # 8. rule plans (C-9 inside sleeve_c) and TEST FIRST shadow signals (never change targets)
    day.plans = build_plans(cfg, bars, st.lots, day.weights, day.equity, day.regime, as_of)
    day.shadow_results = shadow_rules.compute(bars, cfg, day.plans, st.lots, day.regime, as_of, state=st,
                                              weights=day.weights, equity=day.equity)

    # 9. measurement (CL-9, M-5, M-7) and the latches that follow from it
    day.measurement = {
        "veto_events": shadow.update_veto_lots(st, bars, cfg, date),
        "predictions_resolved": shadow.resolve_predictions(st, bars, date),
        "deviations_resolved": shadow.resolve_deviations(st, bars, date),
    }
    if book == "rules":
        if not st.veto_codes_restricted and shadow.should_restrict(st, policy=cfg):
            st.veto_codes_restricted = True
            log.append("CL-9: vetoes have lost money over the scored minimum; skips are now limited to "
                       f"{', '.join(RESTRICTED_SKIP_CODES)} until the owner runs `trader veto-reset`")
        day.allowed_skip = RESTRICTED_SKIP_CODES if st.veto_codes_restricted else SKIP_CODES
    else:
        if not st.deviations_restricted and shadow.should_restrict_deviations(st, policy=cfg):
            st.deviations_restricted = True
            log.append("guide rule 6: deviations have lost money over the scored minimum; the Claude book follows "
                       "the rule targets until the owner runs `trader deviation-reset`")
        day.eligible = decisions.eligibility(cfg, bars, day.regime.permissions)

    # 10. context
    day.context = build_context(
        book, cfg, st, bars, day.equity, day.cash, day.breakers, day.regime, day.weights, day.plans, day.problems,
        as_of, broker_name=getattr(broker, "name", type(broker).__name__), simulated=_simulated(broker),
        rule_weights=day.rule_weights, since_change=day.since_change, eligible=day.eligible,
        allowed_skip=day.allowed_skip, data_notes=day.data_notes, stats=day.stats, demotion=day.demotion)
    return day


def _simulated(broker) -> bool:
    return getattr(broker, "name", "") == "sim"


# --- prepare (Option B, step 1 of the session) ------------------------------------------------------------


def prepare_book(book: str, cfg: Config, bars: Bars, broker: Broker, as_of: pd.Timestamp,
                 state_dir: Path = STATE_DIR, state: BookState | None = None, samples: int | None = None, *,
                 data_notes=None) -> dict:
    """Steps 1-10 without cancelling, ordering or saving, then write state/<book>/pending/<date>/.

    Returns {book, date, dir, files, samples, summary}. The context is exactly the one `run_book` builds for
    the same state and data.
    """
    assert book in BOOKS
    state = state or BookState.load(book, state_dir)
    date = as_of.date().isoformat()
    if state.last_run_date == date:  # a holiday or a finished day: never rewrite or archive that day's files
        why = (f"already ran for {date} (market closed today, or today's run is done); nothing prepared, "
               "the pending folder is left as it is")
        return {"book": book, "date": date, "dir": "", "files": {}, "samples": 0, "summary": [why],
                "skipped": why, "log": []}
    day = _prepare_day(book, cfg, bars, broker, as_of, state, state_dir, dry_run=True, data_notes=data_notes)
    n = session._samples(cfg, samples)
    files = session.write_pending(book, day.date, day.context, cfg, state_dir, n)
    prefix = session.FILE_PREFIX[book]
    b = day.breakers
    summary = [
        f"{book} book, {day.date}: equity {day.equity:,.2f}, drawdown {b.drawdown:.1%}, regime {day.regime.label}"
        f" (temperature {day.regime.temperature_label})",
        f"{'SIMULATED broker' if _simulated(broker) else 'broker ' + getattr(broker, 'name', '?')}",
    ]
    if book == "rules":
        n_inc = len(day.context.get("planned_increases", []))
        summary.append(f"{n_inc} planned B/C/D increase(s) to review"
                       + ("" if n_inc else " (nothing to skip: an empty review is the right answer)"))
    else:
        summary.append(f"{len(day.context.get('menus', {}))} menu key(s); weights now "
                       + ", ".join(f"{s} {w:.0%}" for s, w in day.weights.items()))
    if b.reasons:
        summary.append("breakers: " + "; ".join(b.reasons))
    if day.problems:
        summary.append(f"{len(day.problems)} data problem(s): " + "; ".join(day.problems[:5]))
    summary.append(f"write {prefix}_1.json ... {prefix}_{n}.json into {files['dir']}")
    return {"book": book, "date": day.date, "dir": str(files["dir"]),
            "files": {k: str(v) for k, v in files.items()}, "samples": n, "summary": summary, "log": day.log}


# --- step 11: Claude --------------------------------------------------------------------------------------


def _samples_and_meta(result) -> tuple[list, dict]:
    samples, meta = result
    if not isinstance(samples, (list, tuple)):
        samples = [samples]
    return list(samples), dict(meta or {})


@dataclass
class _Outcome:
    proposed: list[Target]
    weights: dict
    meta: dict | None = None
    error: str | None = None
    claude: dict | None = None
    samples: list = field(default_factory=list)
    agreement: dict = field(default_factory=dict)
    vetoes: list = field(default_factory=list)
    deviations: list = field(default_factory=list)
    predictions: list = field(default_factory=list)
    cl15: dict | None = None
    weight_row: dict | None = None
    journal_note: str = ""
    tags: dict = field(default_factory=dict)


def _note_confidence(day: _Day, meta: dict) -> None:
    """Guide 17 / guide 8: say when a fallback model answered or too few samples were valid."""
    valid, wanted = meta.get("samples_valid"), meta.get("samples_requested")
    causes = []
    if meta.get("fallback_used"):
        causes.append("a fallback model answered at least one sample (it votes like the others)")
    if isinstance(valid, int) and isinstance(wanted, int) and valid < wanted:
        causes.append("the missing samples count as following the rules")
    if meta.get("low_confidence") or meta.get("fallback_used"):
        day.log.append(f"low confidence: {valid} of {wanted} samples valid; "
                       + ("; ".join(causes) or "too few samples agree"))


def _step(day: _Day, advisor) -> _Outcome:
    """Step 11. An unexpected failure while reading or resolving Claude's answer never stops the run: the
    Claude book holds (stops still enforced) and the rules book runs unreviewed, as for a missing answer."""
    try:
        return _rules_step(day, advisor) if day.book == "rules" else _claude_step(day, advisor)
    except Exception as e:  # noqa: BLE001 - the fallback is the designed safe state
        what = "the rules run unreviewed" if day.book == "rules" else "the Claude book holds (stops still enforced)"
        day.log.append(f"Claude's answer could not be processed ({type(e).__name__}: {e}); {what}")
        if day.book == "rules":
            return _Outcome(proposed=_plan_targets(day.plans), weights=day.weights, error=str(e),
                            tags={"book": "rules", "mode": "rules"})
        return _Outcome(proposed=[], weights=dict(day.weights), error=str(e), tags={"book": "claude", "mode": "hold"})


def _rules_step(day: _Day, advisor) -> _Outcome:
    proposed = _plan_targets(day.plans)
    out = _Outcome(proposed=proposed, weights=day.weights, tags={"book": "rules", "mode": "rules"})
    if advisor is None:
        return out
    try:
        samples, meta = _samples_and_meta(advisor.review_rules_plan(day.context))
    except ClaudeError as e:
        out.meta, out.error = getattr(e, "meta", None), str(e)
        day.log.append(f"Claude review unavailable, the rules run unreviewed: {e}")
        return out
    out.meta, out.tags = meta, decision_tags(meta, "rules")
    _note_confidence(day, meta)
    review, stats = consensus.combine_reviews(samples, samples_requested=meta.get("samples_requested"),
                                              cfg=day.cfg, ctx=day.context, allowed_codes=day.allowed_skip,
                                              date=day.date)
    out.proposed, vetoes = decisions.apply_review(proposed, review, day.state.lots, day.log, ctx=day.context,
                                                  allowed_codes=day.allowed_skip, date=day.date, cfg=day.cfg)
    out.vetoes = vetoes
    out.agreement = stats
    out.samples = [{"sample": i + 1, "skips": len(r.skip_entries), "halves": len(r.halve_sleeves)}
                   for i, r in enumerate(samples)]
    out.predictions = list(review.predictions)
    out.claude = review.model_dump()
    out.journal_note = review.journal_note
    return out


def _claude_step(day: _Day, advisor) -> _Outcome:
    st, cfg = day.state, day.cfg
    out = _Outcome(proposed=[], weights=dict(day.weights), tags={"book": "claude", "mode": "hold"})
    if st.deviations_restricted:
        day.log.append("deviations are restricted (guide rule 6): the Claude book follows the rule targets "
                       "and keeps its weights until the owner runs `trader deviation-reset`")
        empty = ClaudeDecision(market_view="", journal_note="", date=day.date)
        out.tags = {"book": "claude", "mode": "rules (deviations restricted)"}
        resolved = decisions.resolve_actions(empty, cfg=cfg, ctx=day.context, rule_targets=day.plans, lots=st.lots,
                                             bars=day.bars, prices=day.prices, equity=day.equity,
                                             permissions=day.regime.permissions, weights=day.weights,
                                             eligible=day.eligible)
        out.proposed, _ = decisions.resolved_to_targets(
            resolved, lots=st.lots, prices=day.prices, equity=day.equity, weights=day.weights, date=day.date,
            log=day.log, position_limits=decisions.max_positions(cfg),
            deviation_threshold=float(cfg.policy["claude_limits"]["deviation_threshold"]))
        return out
    if advisor is None:
        day.log.append("no Claude decision today: the Claude book holds (stops, the C-7 ratchet and the B time "
                       "stop are still enforced)")
        return out
    try:
        samples, meta = _samples_and_meta(advisor.decide(day.context))
    except ClaudeError as e:
        out.meta, out.error = getattr(e, "meta", None), str(e)
        day.log.append(f"Claude decision unavailable, holding positions (stops still enforced): {e}")
        return out
    out.meta, out.tags = meta, decision_tags(meta, "claude")
    _note_confidence(day, meta)
    n_req = meta.get("samples_requested")
    promoted = tuple(st.promoted_sleeves)
    prev = day.weights

    # CL-10/CL-12: each sample's weight menu -> numbers; the per-sleeve median -> capped final weights
    per_w = []
    for d in samples:
        w, reasons, problems = decisions.resolve_weights(
            d.sleeve_weights, cfg=cfg, prev=prev, rule=day.rule_weights, sessions_since_change=day.since_change,
            breakers=day.breakers, promoted=promoted, demoted=day.demotion, ctx=day.context)
        per_w.append((w, reasons, problems))
    final_w = consensus.combine_weights([w for w, _, _ in per_w], reference=prev, samples_requested=n_req,
                                        cfg=cfg, promoted=promoted, demoted=day.demotion)
    for s in SLEEVES:
        final_w.setdefault(s, prev.get(s, 0.0))
    out.weights = final_w

    # The rules' view for this book at the final weights, then each sample's actions against it
    plans = build_plans(cfg, day.bars, st.lots, final_w, day.equity, day.regime, day.as_of)
    day.shadow_results = shadow_rules.compute(day.bars, cfg, plans, st.lots, day.regime, day.as_of, state=st,
                                              weights=final_w, equity=day.equity)
    day.plans = plans
    resolved = []
    for k, (d, (w, reasons, problems)) in enumerate(zip(samples, per_w), start=1):
        r = decisions.resolve_actions(d, cfg=cfg, ctx=day.context, rule_targets=plans, lots=st.lots, bars=day.bars,
                                      prices=day.prices, equity=day.equity, permissions=day.regime.permissions,
                                      sample=k, weights=w, weight_reasons=reasons, eligible=day.eligible)
        r.problems = problems + r.problems
        resolved.append(r)
    combined = consensus.combine_resolved(resolved, final_w, samples_requested=n_req, cfg=cfg)
    out.cl15 = consensus.unanimous_pair(resolved, combined)
    out.proposed, out.deviations = decisions.resolved_to_targets(
        combined, lots=st.lots, prices=day.prices, equity=day.equity, weights=final_w, date=day.date, log=day.log,
        position_limits=decisions.max_positions(cfg),
        deviation_threshold=float(cfg.policy["claude_limits"]["deviation_threshold"]))
    out.predictions = list(combined.predictions)
    out.agreement = dict(combined.agreement)
    out.samples = [{"sample": r.sample, "weights": {s: _r(v) for s, v in r.weights.items()},
                    "actions": sum(1 for t in r.targets.values() if t.source == "action"),
                    "problems": list(r.problems)} for r in resolved]
    out.claude = _combined_summary(combined)
    out.journal_note = combined.journal_note
    base = decisions.cap_weights(cfg, prev, promoted, day.demotion)
    changed = [s for s in SLEEVES if abs(final_w.get(s, 0.0) - base.get(s, 0.0)) > 1e-9]
    rep = next((r for r in resolved if r.sample == combined.sample), resolved[0])
    out.weight_row = {"date": day.date, "weights": {s: round(final_w[s], 6) for s in SLEEVES}, "changed": changed,
                      "reasons": rep.weight_reasons}
    return out


def _combined_summary(c: ResolvedDecision) -> dict:
    return {
        "weights": {s: _r(w) for s, w in c.weights.items()},
        "market_view": c.market_view, "journal_note": c.journal_note, "temperature_ack": c.temperature_ack,
        "likely_error": c.likely_error.model_dump(), "flags": list(c.flags),
        "actions": [{"key": k, "pct": _r(t.pct, 6), "rule_pct": _r(t.rule_pct, 6), "stop": _r(t.stop, 4),
                     "reason_code": t.reason_code, "is_deviation": t.is_deviation, "sample": t.sample}
                    for k, t in c.targets.items() if t.source == "action"],
        "predictions": [p.model_dump() for p in c.predictions],
        "problems": list(c.problems),
    }


def _risk(day: _Day, proposed: list[Target], weights: dict, book: str):
    return RiskEngine(day.cfg).apply(proposed, day.state.lots, day.positions, day.bars, day.equity, day.breakers,
                                     permissions=day.regime.permissions, weights=weights,
                                     promoted=tuple(day.state.promoted_sleeves), book=book)


def _block_bad_data(day: _Day, proposed: list[Target]) -> list[Target]:
    """EX-7: never open or add to a position whose data failed the checks (exits and holds still go)."""
    safe = []
    for t in proposed:
        if t.symbol in day.bad and _is_increase(t, day.state.lots):
            day.log.append(f"{t.sleeve}/{t.symbol}: increase blocked, data problem")
            continue
        safe.append(t)
    return safe


def _deviations_traded(day: _Day, deviations: list[dict], approved: list[Target], unsent: set) -> list[dict]:
    """M-5 / guide rule 6: only a deviation the book actually made is stored and scored. After the risk engine,
    claude_pct is what was executed (claude_pct_requested keeps the ask); a deviation the risk engine or a
    stop on sending turned back to the rule size (kill switch, halt, blocks, caps) is dropped."""
    final = {(t.sleeve, t.symbol): float(t.qty) for t in approved}
    kept = []
    for dv in deviations:
        sleeve, sym = dv.get("sleeve"), dv.get("symbol")
        px, E = day.prices.get(sym), day.equity
        want, rule = float(dv.get("claude_pct") or 0.0), float(dv.get("rule_pct") or 0.0)
        if not px or E <= 0 or abs(want - rule) <= EPS:
            kept.append(dv)
            continue
        cur = _lot_qty(day.state.lots, sleeve, sym)
        qty = cur if sym in unsent else final.get((sleeve, sym), cur)
        done = qty * px / E
        moved = (done - rule) / (want - rule)
        if moved < 0.1:
            day.log.append(f"{sleeve}/{sym}: deviation not traded (risk limits or a stop on sending); not scored")
            continue
        kept.append({**dv, "claude_pct": round(rule + min(moved, 1.0) * (want - rule), 6),
                     "claude_pct_requested": dv.get("claude_pct")})
    return kept


def _vetoes_risk_allows(day: _Day, vetoes: list[dict], unvetoed: list[Target], weights: dict) -> list[dict]:
    """CL-9: a vetoed increase only counts if the risk engine would have let the rules book make it."""
    if not vetoes:
        return []
    allowed = {(t.sleeve, t.symbol): t.qty for t in _risk(day, _block_bad_data(day, unvetoed), weights, "rules").targets}
    kept = []
    for v in vetoes:
        qty = allowed.get((v["sleeve"], v["symbol"]), v["current_qty"])
        if qty <= v["current_qty"] + EPS:
            day.log.append(f"{v['sleeve']}/{v['symbol']}: vetoed increase would not have passed risk; no shadow lot")
            continue
        kept.append({**v, "rule_qty": min(v["rule_qty"], qty)})
    return kept


# --- orders ---------------------------------------------------------------------------------------------


_RUN_N = re.compile(r"-(\d+)(?:-[A-Za-z0-9]+)?$")


def _run_number(state: BookState, prefix: str) -> int:
    """1 + the highest run number already used in this date's client order ids."""
    n = 0
    ids = [o.get("client_order_id") for o in state.pending_orders] + [f.get("client_order_id") for f in state.fills]
    for cid in ids:
        if isinstance(cid, str) and cid.startswith(prefix + "-"):
            m = _RUN_N.search(cid)
            if m:
                n = max(n, int(m.group(1)))
    return n + 1


def client_prefix(book: str, date: str) -> str:
    return f"{book[:1]}{date.replace('-', '')}"


def _assign_ids(book: str, date: str, orders: list, state: BookState, suffix: str) -> None:
    """`{b}{yyyymmdd}-{SYM}-{side}-{run_n}-{suffix}` (<= 48 chars). The random suffix keeps ids unique at the
    broker even if a state file is lost and a run number repeats."""
    prefix = client_prefix(book, date)
    n = _run_number(state, prefix)
    for o in orders:
        o.client_order_id = make_client_order_id(prefix, o.symbol, o.side, n, suffix)


# --- the run --------------------------------------------------------------------------------------------


def run_book(book: str, cfg: Config, bars: Bars, broker: Broker, advisor, as_of: pd.Timestamp,
             state_dir: Path = STATE_DIR, dry_run: bool = False, force: bool = False,
             state: BookState | None = None, *, data_notes=None, allow_all_zero: bool = False) -> dict:
    """All 14 steps for one book. Returns the journal entry (also appended to the journal, dry runs included)."""
    assert book in BOOKS
    state = state or BookState.load(book, state_dir)
    date = as_of.date().isoformat()
    if state.last_run_date == date and not force:
        return {"book": book, "date": date, "skipped": f"already ran for {date} (use --force to rerun)"}
    if force and state.last_run_date == date:
        _drop_discarded_attempt(state, date)

    day = _prepare_day(book, cfg, bars, broker, as_of, state, state_dir, dry_run, data_notes, allow_all_zero)
    log = day.log

    # 11. Claude
    out = _step(day, advisor)
    if book == "rules" and out.vetoes:
        out.vetoes = _vetoes_risk_allows(day, out.vetoes, _plan_targets(day.plans), out.weights)

    # 12. data block, then the risk engine (nothing bypasses it)
    safe = _block_bad_data(day, out.proposed)
    result = _risk(day, safe, out.weights, book)
    log += result.log

    # 13. orders
    orders = result.orders
    submit_results: list[dict] = []
    if not day.positions_ok and orders:
        log.append(f"{len(orders)} order(s) not sent: broker positions were unavailable")
        orders = []
    if day.suspect and orders:
        held = [o for o in orders if o.symbol in day.suspect]
        if held:
            log.append(f"STOP: broker positions look wrong for {', '.join(sorted({o.symbol for o in held}))}; "
                       f"{len(held)} order(s) not sent. If the account really is empty, the owner reruns with "
                       "--confirm-empty-account")
            orders = [o for o in orders if o.symbol not in day.suspect]
    if out.deviations:
        unsent = {o.symbol for o in result.orders} - {o.symbol for o in orders}
        out.deviations = _deviations_traded(day, out.deviations, result.targets, unsent)
    if not dry_run:
        suffix = new_suffix()
        _assign_ids(book, date, orders, state, suffix)
        if orders:
            submit_results = broker.submit(orders, client_prefix(book, date), date=date, suffix=suffix)
        ledger.record_orders(state, result.targets, orders, submit_results, day.prices, date,
                             asset_class=cfg.asset_class, cost_bps=day.cost_bps, tags=out.tags, log=log,
                             min_notional=cfg.policy["turnover"]["min_order_notional"])
        now = ledger.immediate_fills(submit_results, date)  # simulator close mode fills at once
        if now:
            day.settled += ledger.settle_fills(state, now, date=date, asset_class=cfg.asset_class,
                                               cost_bps=day.cost_bps, log=log)

    # 14. store the day's records and save
    tags = out.tags
    if not dry_run:
        shadow.clear_pending(state, date)
        if out.vetoes:
            shadow.open_veto_lots(state, out.vetoes, date, tags=tags)
        if out.predictions:
            shadow.add_predictions(state, out.predictions, date=date, book=book, bars=day.bars, tags=tags)
        if out.deviations:
            shadow.add_deviations(state, out.deviations, tags)
        if out.meta:
            state.api_cost.append(_cost_row(date, book, out.meta))
        if out.weight_row:
            state.weight_history.append(out.weight_row)
        if out.journal_note:
            state.notes.append({"date": date, "note": out.journal_note})
            state.notes = state.notes[-60:]
        _log_experiments(cfg, book, date, out, state_dir)
        state.last_run_date = date
        state.save(state_dir)

    entry = _journal_entry(day, broker, out, result, orders, submit_results)
    journal(book, entry, state_dir)
    return entry


def _drop_discarded_attempt(state: BookState, date: str) -> None:
    """A --force rerun replaces the day: the discarded attempt's weight row and journal note must not feed
    step 7 (previous weights, sessions since a change) or the next context. Its API cost rows stay (that money
    was spent) but are marked superseded."""
    state.weight_history = [r for r in state.weight_history if not (isinstance(r, dict) and r.get("date") == date)]
    state.notes = [n for n in state.notes if not (isinstance(n, dict) and n.get("date") == date)]
    for r in state.api_cost:
        if isinstance(r, dict) and r.get("date") == date:
            r["superseded"] = True


def _cost_row(date: str, book: str, meta: dict) -> dict:
    """M-9: one row per run that asked Claude (session mode: usd 0)."""
    return {"date": date, "role": meta.get("role") or BOOK_ROLE[book], "mode": meta.get("mode"),
            "model": meta.get("model"), "input_tokens": int(meta.get("input_tokens") or 0),
            "output_tokens": int(meta.get("output_tokens") or 0), "usd": float(meta.get("usd") or 0.0),
            "samples": meta.get("samples_valid"), "samples_requested": meta.get("samples_requested")}


def _log_experiments(cfg: Config, book: str, date: str, out: _Outcome, state_dir: Path) -> None:
    """M-13: a line whenever the prompt or the parameter set changes."""
    role = BOOK_ROLE[book]
    pv = (out.meta or {}).get("prompt_version")
    if pv:
        log_experiment({"date": date, "kind": f"prompt:{role}", "version": pv, "book": book,
                        "reason": "prompt, brief or schema changed"}, state_dir)
    params = fingerprint(json.dumps(cfg.playbook, sort_keys=True, default=str),
                         json.dumps(cfg.policy, sort_keys=True, default=str))
    log_experiment({"date": date, "kind": "params", "version": params, "book": book,
                    "reason": "playbook.yaml or risk_policy.yaml changed"}, state_dir)


def _journal_entry(day: _Day, broker, out: _Outcome, result, orders: list, submit_results: list[dict]) -> dict:
    st = day.state
    b = day.breakers
    entry = {
        "date": day.date, "book": day.book, "dry_run": day.dry_run,
        "broker": getattr(broker, "name", type(broker).__name__), "simulated": _simulated(broker),
        "equity": day.equity, "cash": day.cash, "drawdown": b.drawdown, "regime": day.regime.label,
        "temperature": {"value": day.regime.temperature, "label": day.regime.temperature_label,
                        "note": day.regime.temperature_note},
        "breakers": b.to_dict(), "sleeve_weights": out.weights, "rule_weights": day.rule_weights,
        "claude": out.claude, "claude_meta": out.meta, "claude_error": out.error,
        "prompt_version": day.context.get("prompt_version"), "tags": out.tags,
        "samples": out.samples, "agreement": out.agreement, "cl15_shadow": out.cl15,
        "vetoes": out.vetoes, "deviations": out.deviations,
        "predictions": [p.model_dump() if hasattr(p, "model_dump") else p for p in out.predictions],
        "shadow_signals": shadow_rules.summarize(day.shadow_results), "shadow_results": day.shadow_results,
        "measurement": {k: len(v or []) for k, v in day.measurement.items()},
        "settled_fills": day.settled, "pending_orders": len(st.pending_orders),
        "data_feed": day.data_notes, "data_problems": day.problems,
        "risk_log": day.log,
        "orders": [dict(o.__dict__) for o in orders], "planned_orders": [dict(o.__dict__) for o in result.orders],
        "fills": submit_results,
    }
    return jsonable(entry)
