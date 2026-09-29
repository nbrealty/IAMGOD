"""One daily run of one book (BUILD_SPEC "How a daily run flows").

1 settle last run's orders -> 2 account, positions, reconcile -> 3 marks and equity -> 4 breakers ->
5 regime -> 5b news signals and hype vetoes -> 6 data checks -> 7 sleeve weights -> 8 rule plans and shadow
rules -> 9 measurement -> 10 context -> 11 Claude (review or decision, several samples) -> 12 data block,
hype-veto block and risk engine -> 13 orders and pending bookkeeping -> 14 store records, journal, save.

Book O (options) shares the rules book's Alpaca account (owner decision 6). The stock books never see its
option positions (OPT-2), its assigned stock or its orders: step 1 cancels only the book's own client-id
prefixes and step 2 removes O's holdings and value before reconcile and equity (see "book O separation").

`prepare_book` runs steps 1-10 without touching the broker's orders or the saved state and writes the
session's pending folder (Option B). `run_book` runs all 14 steps through the same code, so the context a
session answers is exactly the context the run checks the answer against.
"""
from __future__ import annotations

import inspect
import json
import math
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import consensus, decisions, ledger, metrics, news_signals, risk, session, shadow, shadow_rules
from . import strategies as strat
from .broker import Broker, make_client_order_id, new_suffix
from .config import CONFIG_DIR, STATE_DIR, Config
from .data import Bars, problem_symbols, validate
from .decisions import apply_review  # noqa: F401  (re-exported: the review lives in decisions.py)
from .ledger import reconcile, update_lots  # noqa: F401  (re-exported for old callers)
from .llm import BOOK_ROLE, ClaudeError, decision_tags, jsonable, prompt_version
from .models import Lot, SleevePlan, Target
from .options.models import is_occ, parse_occ
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
                  stats: dict | None = None, demotion: dict | None = None, config_dir: Path = CONFIG_DIR,
                  news: dict | None = None) -> dict:
    """The context shown to Claude. Every number is computed here; JSON-safe (no NaN).

    `news` ({meta, signals, vetoes} from step 5b) adds `news_signals.<ID>[SYMBOL].<field>` (shadow, numbers and
    fixed labels only: news report section 6), `news_meta` and `news_vetoes` (decision 8, enforced by code)."""
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
    vetoed = dict((news or {}).get("vetoes") or {})
    news_block = str(((news or {}).get("meta") or {}).get("blocked") or "")
    if book == "claude":
        ctx["menus"] = _menus(cfg, state, bars, plans, prices, E, regime.permissions, eligible, vetoed, news_block)
    else:
        ctx["planned_increases"] = [
            {"sleeve": t.sleeve, "symbol": t.symbol, "current_qty": _r(_lot_qty(state.lots, t.sleeve, t.symbol), 6),
             "target_qty": _r(t.qty, 6), "target_pct_equity": pct(t.qty, t.symbol), "stop": _r(t.stop, 4),
             "reason": t.reason, "blocked_by_hype_veto": t.symbol in vetoed or bool(news_block)}
            for t in _plan_targets(plans) if t.sleeve in ("B", "C", "D") and _is_increase(t, state.lots)]
    if news is not None:
        ctx["news_meta"] = dict(news.get("meta") or {})
        ctx["news_signals"] = dict(news.get("signals") or {})
        ctx["news_vetoes"] = vetoed
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
           permissions: dict, eligible: dict | None, vetoed: dict | None = None, news_block: str = "") -> dict:
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
        why = "" if ok else _not_eligible_why(cfg, sleeve, sym, bars, permissions)
        if sleeve in NEWS_VETO_SLEEVES and sym in (vetoed or {}):
            ok, why = False, decisions.HYPE_VETO_LABEL + ", no new long today (decision 8): " + "; ".join(vetoed[sym])
        elif sleeve in NEWS_VETO_SLEEVES and news_block:
            ok, why = False, news_block
        try:
            stops = decisions.stop_menu(sleeve, bars.get(sym), cfg.policy, lot)
        except (KeyError, IndexError, ValueError, TypeError):
            stops = {"rule": None, "tight": None, "keep": None}
        out[key] = {"sleeve": sleeve, "symbol": sym, "price": _r(px, 4), "current_pct": _r(cur * px / equity, 6),
                    "rule_pct": _r(rule_qty * px / equity, 6), "half_rule_pct": _r(0.5 * rule_qty * px / equity, 6),
                    "eligible_increase": ok,
                    "why_not_eligible": why,
                    "stops": {k: _r(v, 4) for k, v in stops.items()}}
    return out


# --- book O separation (owner decision 6, OPT-2, OPT-11) -----------------------------------------------

O_PREFIX_DEFAULT = "OPT-"


def o_host_book(cfg: Config) -> str:
    """The stock book whose Alpaca account book O shares (owner decision 6: the rules book)."""
    return str((cfg.policy.get("options_book") or {}).get("shared_account_book", "rules"))


def _clean_o(raw: Any, *, complete: bool, note: str = "") -> dict:
    """A JSON-safe copy of `o_owned`: symbols (upper case), stock {sym: shares > 0}, value (float or None)."""
    raw = raw if isinstance(raw, dict) else {}
    stock = {}
    for sym, q in (raw.get("stock") or {}).items():
        v = _r(q, 6)
        if v is not None and v > EPS:
            stock[str(sym).upper()] = v
    value = raw.get("value")
    value = _r(value, 2) if value is not None else None
    if raw and value is None:
        complete = False  # O says it owns something but gives no value: the rules equity cannot be trusted
    legs = {}
    for sym, q in (raw.get("legs") or {}).items():
        v = _r(q, 6)
        if v is not None and abs(v) > EPS:
            legs[str(sym).upper()] = v
    return {"symbols": sorted({str(s).upper() for s in (raw.get("symbols") or ())}), "stock": stock,
            "value": value, "order_prefix": str(raw.get("order_prefix") or O_PREFIX_DEFAULT),
            "legs": legs, "pending_stock": sorted({str(s).upper() for s in (raw.get("pending_stock") or ())}),
            "complete": bool(complete), "note": note}


def _o_from_ledger(state_dir: Path, why: str) -> dict:
    """Fallback when `trader.options.run.o_owned` is missing or fails: read O's paper ledger (shadow spreads live
    elsewhere and never reach the account). Any open spread or assigned stock in it makes the answer incomplete
    (its value is unknown), which blocks the host book's increases for the day."""
    note = f"trader.options.run.o_owned unavailable ({why}); O's ledger read directly"
    try:
        from .options.ledger import OptionsBook

        ob = OptionsBook.load(state_dir)
    except Exception as e:  # noqa: BLE001 - a corrupt ledger means "unknown", never "O owns nothing"
        exists = (Path(state_dir) / "options").exists()
        return _clean_o({}, complete=not exists, note=f"{note}; ledger unreadable ({type(e).__name__}: {e})")
    live = list(ob.open_lots())  # safer: without run.py a spread's shadow flag is not trusted
    syms = {leg.symbol for lot in live for leg in (lot.short_leg, lot.long_leg)}
    legs: dict[str, float] = {}
    for lot in live:
        legs[lot.short_leg.symbol] = legs.get(lot.short_leg.symbol, 0.0) - float(lot.short_leg.qty)
        legs[lot.long_leg.symbol] = legs.get(lot.long_leg.symbol, 0.0) + float(lot.long_leg.qty)
    raw = {"symbols": syms, "stock": dict(ob.o_stock or {}), "value": None if (live or ob.o_stock) else 0.0,
           "legs": legs}
    return _clean_o(raw, complete=not (live or ob.o_stock), note=note)


def o_owned(state_dir: Path = STATE_DIR) -> dict:
    """What book O owns in the shared account: {symbols, stock, value, order_prefix, complete, note}.

    Calls `trader.options.run.o_owned` (Wave 2 interface), imported only here so the stock books still run
    while that module is being built or broken. `complete` False means O's value is unknown."""
    try:
        from .options import run as orun

        return _clean_o(orun.o_owned(state_dir), complete=True)
    except Exception as e:  # noqa: BLE001
        return _o_from_ledger(state_dir, f"{type(e).__name__}: {e}")


def separate_o(positions: dict, o: dict, log: list[str], *, host: bool) -> tuple[dict, set[str]]:
    """OPT-2 / decision 6: the stock books' view of broker positions. Option symbols (OCC) and O's legs are
    removed for every book; on the shared (host) account O's assigned stock is also subtracted.

    Returns (positions, suspect symbols). A symbol where the broker holds less stock than O owns cannot be
    split between the books, so it is suspect (no orders, no reconcile) today. So is the underlying of an O short
    leg the broker holds less of than O's ledger (a possible assignment O has not booked yet: the new shares are
    O's, not this book's), and a symbol with an unsettled O stock order (the split is unknown until O books it)."""
    out, dropped, suspect = {}, [], set()
    o_syms = set(o.get("symbols") or ())
    for sym, q in (positions or {}).items():
        if is_occ(sym) or str(sym).upper() in o_syms:
            dropped.append(sym)
            continue
        out[sym] = q
    if dropped:
        log.append(f"{len(dropped)} option position(s) belong to book O and are left alone (OPT-2, decision 6)")
    if not host:
        return out, suspect
    held = {str(s).upper(): (decisions._num(q) or 0.0) for s, q in (positions or {}).items() if is_occ(s)}
    for occ, exp in (o.get("legs") or {}).items():
        if exp < 0 and held.get(occ, 0.0) > exp + 1e-6:  # O's short leg smaller or gone at the broker
            try:
                u = parse_occ(occ)["underlying"]
            except ValueError:
                continue
            if u not in suspect:
                log.append(f"{u}: book O's short leg {occ} is {held.get(occ, 0.0):g} at the broker vs {exp:g} in O's "
                           "ledger: possible unbooked assignment, the stock books leave it alone today")
            suspect.add(u)
    for u in o.get("pending_stock") or ():
        u = str(u).upper()
        if u not in suspect:
            log.append(f"{u}: book O has an unsettled stock order; the stock books leave it alone today")
        suspect.add(u)
    for sym, shares in (o.get("stock") or {}).items():
        have = decisions._num(out.get(sym, 0.0))
        if have is None:
            continue  # reconcile flags a non-numeric position itself
        if have + 1e-6 < shares:
            log.append(f"{sym}: broker holds {have:.6g} but book O owns {shares:.6g} assigned shares; "
                       "the stock books leave it alone today")
            suspect.add(sym)
        out[sym] = max(0.0, have - shares)
        log.append(f"{sym}: {shares:.6g} share(s) belong to book O (assignment), not to this book")
    return out, suspect


def _own_prefixes(book: str, date: str) -> tuple[str, ...]:
    """Client-order-id prefixes of this book's orders (`client_prefix`), this year and last (never O's `OPT-`)."""
    year = int(str(date)[:4])
    return (f"{book[:1]}{year}", f"{book[:1]}{year - 1}")


def _cancel_own_orders(day: "_Day", broker: Broker) -> None:
    """Step 1: cancel only this book's leftover orders (decision 6: never book O's). A real broker that cannot
    filter by prefix is not asked to cancel at all while O may have orders (DAY orders lapse by themselves)."""
    fn = broker.cancel_open_orders
    try:
        takes_prefixes = "prefixes" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        takes_prefixes = False
    if takes_prefixes:
        fn(prefixes=_own_prefixes(day.book, day.date))
        return
    o = day.o or {}
    if not _simulated(broker) and day.o_host and (o.get("symbols") or o.get("stock") or not o.get("complete", True)):
        day.hold_symbols = {str(o.get("symbol")) for o in day.state.pending_orders if isinstance(o, dict)}
        day.log.append("open orders not cancelled: this broker cannot cancel by client-id prefix and book O may "
                       "have orders in the shared account (decision 6)"
                       + (f"; no new orders today in {', '.join(sorted(day.hold_symbols))}, whose last orders may "
                          "still be open" if day.hold_symbols else ""))
        return
    fn()


def _apply_o(day: "_Day", broker: Broker, state_dir: Path) -> None:
    """Step 2 for the stock books: O's positions out of the positions, O's value out of equity and cash."""
    if _simulated(broker):
        day.o = _clean_o({}, complete=True, note="simulated broker: book O is not in this account")
        return
    if not day.o:
        day.o = o_owned(state_dir)
    if day.o.get("note"):
        day.log.append(day.o["note"])
    if day.o_host:
        value = day.o.get("value")
        if value is None or not day.o.get("complete", True):
            # Unknown: take out O's last known value (a conservative stand-in, never "O owns nothing"), block every
            # increase in every sleeve, and keep this day out of the high-water mark (_record_equity).
            value = _last_o_value(day.state)
            day.o["value_used"] = value
            day.block_increases = ("book O's value in the shared account is unknown, so this book's equity is not "
                                   "reliable: no new entries or increases today, in any sleeve (decision 6)")
            day.log.append(day.block_increases)
            if value is not None:
                day.log.append(f"book O's last known value {value:,.2f} taken out of this book's equity instead")
        if value is not None:
            day.equity -= float(value)
            day.cash -= max(0.0, float(value))
            if abs(float(value)) > EPS and day.o.get("complete", True):
                day.log.append(f"book O's value {value:,.2f} taken out of this book's equity (decision 6)")


def _last_o_value(state: BookState) -> float | None:
    """Book O's value on the latest equity row where it was known (None if never recorded)."""
    for row in reversed(state.equity_history):
        if isinstance(row, dict) and row.get("o_value") is not None and not row.get("o_value_unknown"):
            return float(row["o_value"])
    return None


def _record_equity(day: "_Day", closes: dict, bench: str) -> tuple[float, float]:
    """Step 3: store today's equity row with book O's value on it. When O's value is unknown on the host the row
    is marked `o_value_unknown` and the peak (high-water mark) is not raised from it, so O's money can never
    become this book's peak, and the next day's drawdown and loss limits do not see a false loss."""
    st = day.state
    peak = st.peak_equity
    out = st.record_equity(day.date, day.equity, closes.get(bench, float("nan")),
                           closes={s: closes[s] for s in BENCH_CLOSES if s in closes},
                           exposure=_exposure(day.cfg, st.lots, closes))
    row = st.equity_history[-1]
    if day.o_host:
        unknown = day.o.get("value") is None or not day.o.get("complete", True)
        used = day.o.get("value_used") if unknown else day.o.get("value")
        row["o_value"] = _r(used, 2)
        if unknown:
            row["o_value_unknown"] = True
            st.peak_equity = peak
    return out


# --- news signals and the active hype vetoes (owner decision 8, news report section 6) -----------------

# Owner decision 8 scope (OPERATION_INVEST.md, 28 Sept 2026): the hype vetoes block new buys and increases in
# sleeves B, C and D only, never sleeve A's broad ETF trend rebalances. If the news fetch or the signal computation
# fails, B/C/D increases are blocked that day (fail closed) and sleeve A still runs. Exits, reductions and stops are
# never vetoed.
NEWS_VETO_SLEEVES = ("B", "C", "D")
NEWS_VETO_CODE = "NEWS_HYPE_VETO"  # stored on the shadow lot; not a Claude reason code (section 6)
# Decision 8 update (28 Sept): NEWS-4 and NEWS-13 are TEST FIRST. When the policy does not list them as active, a
# B/C/D increase they flag is NOT blocked; it is followed as a shadow lot under this code (what the veto would have
# saved), so the owner can judge them before they ever block.
NEWS_TEST_FIRST_CODE = "NEWS_TEST_FIRST"
NEWS_TEST_FIRST_IDS = ("NEWS-4", "NEWS-13")
_SAFE_KEY = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")
_SAFE_TEXT = re.compile(r"^[A-Za-z0-9 _.:%+\-/()=<>,]*$")
NEWS_NOTE = ("shadow: code-computed numbers and fixed labels only (no headline text). You may cite these in "
             "journal_note or a prediction; they are not evidence for any skip, halve, action or weight change "
             "(CL-2, M-12). news_vetoes are already enforced by code: new longs in those names are blocked.")


@dataclass
class NewsFeed:
    """News input for one run. `items` are `news.fetch_news` items; None means the fetch failed or was not
    attempted. `start` is the fetch window start (so a quiet day counts 0 headlines, not 'unknown')."""

    items: list[dict] | None = None
    start: Any = None
    notes: list[str] = field(default_factory=list)


def news_universe(cfg: Config) -> list[str]:
    """News report section 5: the C universe plus the B ETFs (no crypto)."""
    syms = list(cfg.sleeves["B"]["symbols"]) + list(cfg.stock_universe())
    return [s for s in dict.fromkeys(syms) if "/" not in s]


def _safe_text(value: Any, limit: int = 60) -> str | None:
    """A code label is kept only if short and plain (defence in depth: no text can reach Claude's context)."""
    text = str(value)
    return text if len(text) <= limit and _SAFE_TEXT.match(text) else None


def safe_news_row(row: Any, depth: int = 0) -> dict:
    """Section 6 guard: numbers, booleans and short fixed labels only; anything else is dropped."""
    out: dict[str, Any] = {}
    for k, v in (row.items() if isinstance(row, dict) else ()):
        if not (isinstance(k, str) and _SAFE_KEY.match(k)):
            continue
        if v is None or isinstance(v, (bool, np.bool_)):
            out[k] = None if v is None else bool(v)
        elif isinstance(v, (int, float, np.integer, np.floating)):
            out[k] = _r(v, 6)
        elif isinstance(v, str):
            t = _safe_text(v)
            if t is not None:
                out[k] = t
        elif isinstance(v, dict) and depth < 2:
            out[k] = safe_news_row(v, depth + 1)
    return out


def _compact_signals(signals: dict, allowed: set[str]) -> dict:
    """The rows Claude sees: every computed event or veto row, and the market-wide rows (key SPY)."""
    out: dict[str, dict] = {}
    for sid, rows in (signals or {}).items():
        keep = {}
        for sym, row in (rows or {}).items():
            if sym not in allowed or not isinstance(row, dict) or "skipped" in row:
                continue
            if row.get("event") or row.get("veto") or sid in ("NEWS-9", "NEWS-10", "NEWS-11", "NEWS-12"):
                keep[sym] = safe_news_row(row)
        if keep:
            out[sid] = keep
    return out


def _clean_vetoes(vetoes: dict, allowed: set[str]) -> dict[str, list[str]]:
    out = {}
    for sym, reasons in (vetoes or {}).items():
        if sym in allowed:
            texts = [t for t in (_safe_text(r, 160) for r in reasons or ()) if t]
            out[sym] = texts or ["hype veto (decision 8)"]
    return out


def _news_step(day: "_Day", feed: NewsFeed | None) -> None:
    """Step 5b: NEWS-1..18 for today and the active vetoes (by default only the NEWS-18 promotion veto; NEWS-4 and
    NEWS-13 are TEST FIRST and only flag shadow lots unless `news.active_vetoes` lists them).

    `feed` None is the old call (tests, evals): nothing is computed and the run says so. The CLI always passes a
    NewsFeed. A failed fetch (items None) or a failed computation sets `day.news_block`: the promotion check is
    impossible, so new B/C/D longs are blocked today (fail closed) while sleeve A still runs (decision 8)."""
    cfg, st = day.cfg, day.state
    if feed is None:
        day.log.append("hype vetoes not checked: no news feed was passed to the engine (the CLI always passes one)")
        return
    uni = news_universe(cfg)
    allowed = set(uni) | {news_signals.BENCHMARK}
    items = list(feed.items) if feed.items is not None else []
    start = feed.start if feed.items is not None else None
    notes = [_safe_text(n, 200) or "news note withheld (not plain text)" for n in feed.notes or []]
    if feed.items is None:
        day.news_block = ("news fetch failed: no new B/C/D longs today, sleeve A still runs (decision 8)")
        day.log.append(day.news_block)
    try:
        signals = news_signals.compute(day.bars, items, uni, day.as_of, cfg.policy, news_start=start,
                                       c_universe=cfg.stock_universe(), regime_label=day.regime.label)
        vetoes, history = news_signals.active_vetoes(signals, cfg.policy, dict(st.news_promo_history or {}),
                                                     as_of=day.as_of)
        active = set(news_signals.news_policy(cfg.policy)["active_vetoes"])
        test_first = [i for i in NEWS_TEST_FIRST_IDS if i not in active]
        flagged = news_signals.active_vetoes(signals, {"active_vetoes": test_first}) if test_first else {}
    except Exception as e:  # noqa: BLE001 - fail closed for B/C/D, never silently open
        day.news_block = (f"news signals failed ({type(e).__name__}: {e}): no new B/C/D longs today, sleeve A "
                          "still runs (decision 8)")
        day.log.append(day.news_block)
        day.news = {"meta": {"status": "failed", "note": NEWS_NOTE, "notes": notes + [day.news_block],
                             "blocked": day.news_block, "blocked_sleeves": list(NEWS_VETO_SLEEVES)},
                    "signals": {}, "vetoes": {}}
        return
    day.news_vetoes = _clean_vetoes(vetoes, allowed)
    day.news_test_first = _clean_vetoes(flagged, allowed)
    day.news_history = history
    try:  # section 6 audit record: headline text and scorer version per score, for a file only (_save_score_log)
        day.score_log = list(news_signals.score_log(day.bars, items, uni, day.as_of, cfg.policy))
    except Exception as e:  # noqa: BLE001 - the audit file is not a trading input
        day.log.append(f"news score log not written ({type(e).__name__}: {e})")
    pol = news_signals.news_policy(cfg.policy)
    day.news = {"meta": {"status": "shadow", "note": NEWS_NOTE, "as_of": day.date, "source": pol["source"],
                         "headlines": len(items) if feed.items is not None else None,
                         "active_vetoes": list(pol["active_vetoes"]), "veto_sleeves": list(NEWS_VETO_SLEEVES),
                         "notes": notes},
                "signals": _compact_signals(signals, allowed), "vetoes": day.news_vetoes}
    if day.news_block:
        day.news["meta"].update(status="blocked", blocked=day.news_block, blocked_sleeves=list(NEWS_VETO_SLEEVES))
    if day.news_test_first:
        day.log.append("TEST FIRST hype flags (not blocking, shadow-scored): " + ", ".join(sorted(day.news_test_first)))
    if day.news_vetoes:
        day.log.append("hype vetoes (decision 8, no new longs): " + ", ".join(sorted(day.news_vetoes)))


def _test_first_records(day: "_Day", proposed: list[Target]) -> list[dict]:
    """Decision 8 update: a B/C/D increase that a TEST FIRST signal (NEWS-4, NEWS-13) flags is not blocked; it gets
    a shadow record (reason_code NEWS_TEST_FIRST) so the veto it would have made is scored. A name an active veto
    already blocks is scored by that veto's own lot (its reasons gain the test-first ones instead)."""
    out = []
    for t in proposed:
        reasons = day.news_test_first.get(t.symbol)
        if (not reasons or t.sleeve not in NEWS_VETO_SLEEVES or t.symbol in day.news_vetoes
                or not _is_increase(t, day.state.lots)):
            continue
        out.append({"date": day.date, "sleeve": t.sleeve, "symbol": t.symbol, "fraction": 1.0,
                    "rule_qty": float(t.qty), "current_qty": _lot_qty(day.state.lots, t.sleeve, t.symbol),
                    "stop": t.stop, "reason_code": NEWS_TEST_FIRST_CODE, "prediction_id": "",
                    "news_reasons": list(reasons), "blocked": False})
    return out


def _block_news(day: "_Day", proposed: list[Target], quiet: bool = False) -> tuple[list[Target], list[dict]]:
    """Step 12, decision 8: an increase in a vetoed name in sleeves B, C or D is held at today's quantity. Sleeve A,
    exits, reductions and stops pass untouched. Returns (targets, one veto record per blocked increase)."""
    if not day.news_vetoes:
        return list(proposed), []
    out, records = [], []
    for t in proposed:
        reasons = day.news_vetoes.get(t.symbol)
        if not reasons or t.sleeve not in NEWS_VETO_SLEEVES or not _is_increase(t, day.state.lots):
            out.append(t)
            continue
        cur = _lot_qty(day.state.lots, t.sleeve, t.symbol)
        ids = sorted({r.split(" ", 1)[0] for r in reasons})
        out.append(replace(t, qty=cur, reason=f"{t.reason} (blocked by hype veto {', '.join(ids)})"))
        if not quiet:
            day.log.append(f"{t.sleeve}/{t.symbol}: increase blocked by hype veto ({'; '.join(reasons)})")
        records.append({"date": day.date, "sleeve": t.sleeve, "symbol": t.symbol, "fraction": 1.0,
                        "rule_qty": float(t.qty), "current_qty": cur, "stop": t.stop,
                        "reason_code": NEWS_VETO_CODE, "prediction_id": "", "blocked": True,
                        "news_reasons": list(reasons) + list(day.news_test_first.get(t.symbol) or ())})
    return out, records


class _NewsLots:
    """Lets shadow.py's CL-9 veto-lot functions score `state.news_veto_lots` (a separate list, so code vetoes
    never feed Claude's CL-9 latch or the M-6 review report)."""

    def __init__(self, state: BookState):
        self.book = state.book
        self.shadow_lots = state.news_veto_lots
        self.cost_model_bps = state.cost_model_bps
        self.veto_reset_date = None


def _store_news(state: BookState, day: "_Day", records: list[dict], tags: dict) -> None:
    """Step 14: a same-day rerun replaces lots that have not entered; then one shadow lot per blocked increase."""
    state.news_veto_lots[:] = [lt for lt in state.news_veto_lots
                               if not (lt.get("date") == day.date and lt.get("status") == "pending_entry")]
    for lot in shadow.open_veto_lots(_NewsLots(state), records, day.date, tags=tags):
        rec = next((r for r in records if r["sleeve"] == lot["sleeve"] and r["symbol"] == lot["symbol"]), {})
        blocked = rec.get("reason_code", NEWS_VETO_CODE) != NEWS_TEST_FIRST_CODE
        lot.update({"kind": "news_veto" if blocked else "news_test_first", "blocked": blocked,
                    "news_reasons": list(rec.get("news_reasons") or [])})
    if day.news_history is not None:
        state.news_promo_history = day.news_history


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
    o: dict = field(default_factory=dict)  # what book O owns in the shared account (o_owned)
    o_host: bool = False  # this book shares its Alpaca account with book O (decision 6)
    block_increases: str = ""  # non-empty: every increase (all sleeves) is blocked today, with this reason
    news_block: str = ""  # non-empty: news fetch/signals failed, B/C/D increases blocked today (decision 8)
    news_test_first: dict = field(default_factory=dict)  # symbol -> TEST FIRST reasons (NEWS-4/13, never block)
    hold_symbols: set = field(default_factory=set)  # symbols with possibly open old orders: no new orders today
    score_log: list = field(default_factory=list)  # section 6 audit rows (headline text): a file only, never context
    news: dict = field(default_factory=dict)  # {meta, signals, vetoes} for the context and the journal
    news_vetoes: dict = field(default_factory=dict)  # symbol -> reasons (decision 8)
    news_history: dict | None = None  # the updated NEWS-18 promotion memory, saved by a real run


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
    _cancel_own_orders(day, broker)
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
                 state_dir: Path, dry_run: bool, data_notes=None, allow_all_zero: bool = False,
                 news: NewsFeed | None = None) -> _Day:
    """Steps 1-10. Only step 1 differs with dry_run (no cancel); nothing here saves or sends orders."""
    bars = _slice(bars, as_of)
    day = _Day(book, cfg, state, bars, as_of, as_of.date().isoformat(), dry_run, data_notes=_data_notes(data_notes))
    st, pol, date, log = state, cfg.policy, day.date, day.log
    day.o_host = book == o_host_book(cfg) and not _simulated(broker)
    if not _simulated(broker):
        day.o = o_owned(state_dir)  # read before step 1: the cancel must know whether O may have orders
    bench = cfg.playbook["regime"]["benchmark"]

    # 0. splits: the bars are split-adjusted, so lots, pending orders and the simulator move to today's units
    splits = ledger.apply_splits(st, bars, date, log, simulated=_simulated(broker))

    # 1. settle (EX-5 cost model first: measured slippage may raise it)
    day.cost_bps = ledger.measured_cost_model(st, pol)
    _settle(day, broker)

    # 2. account and reconcile (never against a positions call that failed); book O's share taken out first
    day.equity, day.cash = broker.account()
    _apply_o(day, broker, state_dir)
    day.prices = risk.last_prices(bars)
    closes = risk.last_valid_closes(bars)
    try:
        day.positions = dict(broker.positions())
    except Exception as e:  # a failed call must never read as "the account is flat"
        day.positions, day.positions_ok = {}, False
        log.append(f"broker positions unavailable ({e}); reconcile skipped and no orders will be sent today")
    suspect: set = set()
    if day.positions_ok:
        day.positions, o_suspect = separate_o(day.positions, day.o, log, host=day.o_host)
        suspect |= o_suspect
        lagging = set() if _simulated(broker) else ledger.split_lagging(st, splits, day.positions, log)
        suspect |= ledger.reconcile(st.lots, day.positions, log, state=st, prices=closes, date=date,
                                    skip_symbols=lagging | suspect, allow_all_zero=allow_all_zero) | lagging
    else:
        suspect = {sym for held in st.lots.values() for sym in held}
    day.suspect = set(suspect)

    # 3. marks and equity (M-1, M-4, M-5, RISK-13 inputs)
    ledger.update_marks(st, bars, date, log=log)
    day_pnl, week_pnl = _record_equity(day, closes, bench)

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

    # 5b. news signals (shadow) and the active hype vetoes (decision 8: block new longs only)
    _news_step(day, news)

    # 6. data checks (EX-7): symbols with problems get no increases today
    dc = pol.get("data_checks", {})
    day.problems = validate(bars, cfg.allowlist(), as_of, max_stale_days=dc.get("max_stale_days", 5),
                            max_daily_move=dc.get("max_daily_move", 0.25))
    day.problems += [f"{s}: broker position looks wrong today, no increases (reconcile skipped)"
                     for s in sorted(suspect)]
    day.bad = problem_symbols(day.problems) | set(suspect)
    if day.block_increases:
        day.problems.append(f"all symbols: {day.block_increases}")
    if day.news_block:
        day.problems.append(f"sleeves {'/'.join(NEWS_VETO_SLEEVES)}: {day.news_block}")

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
        "news_veto_events": shadow.update_veto_lots(_NewsLots(st), bars, cfg, date),
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
        for s in NEWS_VETO_SLEEVES:  # decision 8: a vetoed name is not an eligible increase today
            if s in day.eligible:
                day.eligible[s] = (set() if day.news_block else
                                   {sym for sym in day.eligible[s] if sym not in day.news_vetoes})

    # 10. context
    day.context = build_context(
        book, cfg, st, bars, day.equity, day.cash, day.breakers, day.regime, day.weights, day.plans, day.problems,
        as_of, broker_name=getattr(broker, "name", type(broker).__name__), simulated=_simulated(broker),
        rule_weights=day.rule_weights, since_change=day.since_change, eligible=day.eligible,
        allowed_skip=day.allowed_skip, data_notes=day.data_notes, stats=day.stats, demotion=day.demotion,
        news=day.news or None)
    return day


def _simulated(broker) -> bool:
    return getattr(broker, "name", "") == "sim"


# --- prepare (Option B, step 1 of the session) ------------------------------------------------------------


def prepare_book(book: str, cfg: Config, bars: Bars, broker: Broker, as_of: pd.Timestamp,
                 state_dir: Path = STATE_DIR, state: BookState | None = None, samples: int | None = None, *,
                 data_notes=None, news: NewsFeed | None = None) -> dict:
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
    day = _prepare_day(book, cfg, bars, broker, as_of, state, state_dir, dry_run=True, data_notes=data_notes,
                       news=news)
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
    if day.news_vetoes:
        summary.append("hype vetoes (no new longs, decision 8): " + ", ".join(sorted(day.news_vetoes)))
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


def _block_bad_data(day: _Day, proposed: list[Target], quiet: bool = False) -> list[Target]:
    """EX-7: never open or add to a position whose data failed the checks (exits and holds still go).
    `day.block_increases` (an unknown book-O value) blocks every increase the same way; `day.news_block` (a failed
    news fetch or hype check) blocks increases in sleeves B, C and D only (decision 8: sleeve A still runs)."""
    safe = []
    for t in proposed:
        news_hit = bool(day.news_block) and t.sleeve in NEWS_VETO_SLEEVES
        if _is_increase(t, day.state.lots) and (
                t.symbol in day.bad or day.block_increases or news_hit):
            if not quiet:
                day.log.append(f"{t.sleeve}/{t.symbol}: increase blocked, "
                               + ("data problem" if t.symbol in day.bad else
                                  day.block_increases or day.news_block))
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


def _vetoes_risk_allows(day: _Day, vetoes: list[dict], unvetoed: list[Target], weights: dict,
                        book: str = "rules") -> list[dict]:
    """CL-9: a vetoed increase only counts if the risk engine would have let the book make it."""
    if not vetoes:
        return []
    allowed = {(t.sleeve, t.symbol): t.qty
               for t in _risk(day, _block_bad_data(day, unvetoed, quiet=True), weights, book).targets}
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
             state: BookState | None = None, *, data_notes=None, allow_all_zero: bool = False,
             news: NewsFeed | None = None) -> dict:
    """All 14 steps for one book. Returns the journal entry (also appended to the journal, dry runs included).

    `news` is today's news fetch (NewsFeed); without it the hype vetoes still run on bars (step 5b)."""
    assert book in BOOKS
    state = state or BookState.load(book, state_dir)
    date = as_of.date().isoformat()
    if state.last_run_date == date and not force:
        return {"book": book, "date": date, "skipped": f"already ran for {date} (use --force to rerun)"}
    if force and state.last_run_date == date:
        _drop_discarded_attempt(state, date)

    day = _prepare_day(book, cfg, bars, broker, as_of, state, state_dir, dry_run, data_notes, allow_all_zero,
                       news=news)
    log = day.log

    # 11. Claude
    out = _step(day, advisor)

    # 12. hype vetoes (decision 8), data block, then the risk engine (nothing bypasses it). The hype vetoes are
    # recorded against the book's targets BEFORE Claude's review (rules book: the plan), so a review skip or halve
    # of a vetoed name can neither hide the veto's shadow lot nor earn CL-9 credit for a block code makes anyway.
    pre = _plan_targets(day.plans) if book == "rules" else list(out.proposed)
    _, news_vetoes = _block_news(day, pre)
    news_vetoes = _vetoes_risk_allows(day, news_vetoes + _test_first_records(day, pre), pre, out.weights, book)
    if book == "rules" and out.vetoes:
        out.vetoes = _drop_hype_blocked(day, out.vetoes)
        out.vetoes = _vetoes_risk_allows(day, out.vetoes, _plan_targets(day.plans), out.weights)
    out.proposed, _ = _block_news(day, out.proposed, quiet=True)
    safe = _block_bad_data(day, out.proposed)
    result = _risk(day, safe, out.weights, book)
    log += result.log

    # 13. orders
    orders = result.orders
    submit_results: list[dict] = []
    alerts: list[str] = []
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
    for t in safe:  # an exit, stop or reduction this book wants but cannot make in a suspect symbol is an ALERT
        cur = _lot_qty(state.lots, t.sleeve, t.symbol)
        if t.symbol in day.suspect and float(t.qty) < cur - EPS:
            alerts.append(f"ALERT: {t.sleeve}/{t.symbol} sell to {float(t.qty):g} of {cur:g} (an exit, stop or "
                          "reduction) not sent: the broker position cannot be split from book O's or looks wrong; "
                          "the owner checks the position and book O's ledger today")
    log += alerts
    if day.hold_symbols and orders:
        held = [o for o in orders if o.symbol in day.hold_symbols]
        if held:
            log.append(f"{len(held)} order(s) not sent in {', '.join(sorted({o.symbol for o in held}))}: the last "
                       "run's orders there could not be cancelled and may still be open (no duplicates)")
            orders = [o for o in orders if o.symbol not in day.hold_symbols]
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
        _store_news(state, day, news_vetoes, tags)
        _save_score_log(day, state_dir)
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
    entry["news"] = jsonable(day.news)
    entry["news_vetoes"] = jsonable(news_vetoes)
    entry["book_o"] = jsonable({"host": day.o_host, **{k: v for k, v in (day.o or {}).items()}})
    if alerts:
        entry["alerts"] = alerts
    journal(book, entry, state_dir)
    return entry


def _drop_hype_blocked(day: _Day, vetoes: list[dict]) -> list[dict]:
    """A review skip or halve of an increase that a hype veto already blocks changes nothing, so it is not a CL-9
    veto: no CL-9 shadow lot, no credit or blame (decision 8's own shadow lot scores the block)."""
    kept = []
    for v in vetoes:
        if (v.get("symbol") in day.news_vetoes and v.get("sleeve") in NEWS_VETO_SLEEVES):
            day.log.append(f"{v.get('sleeve')}/{v.get('symbol')}: review {v.get('reason_code')} ignored for CL-9, the "
                           "increase is already blocked by code (hype veto, decision 8)")
            continue
        kept.append(v)
    return kept


def _save_score_log(day: _Day, state_dir: Path) -> None:
    """News report section 6: the headline text and scorer version behind every score, so a veto can be traced and
    reproduced. Written to state/news/score_log/<date>.jsonl, never to a context or pending folder."""
    if not day.score_log:
        return
    try:
        folder = Path(state_dir) / "news" / "score_log"
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / f"{day.date}.jsonl", "w") as f:
            for row in day.score_log:
                f.write(json.dumps(jsonable(row), sort_keys=True) + "\n")
    except Exception as e:  # noqa: BLE001 - the audit file is not a trading input
        day.log.append(f"news score log not written ({type(e).__name__}: {e})")


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
