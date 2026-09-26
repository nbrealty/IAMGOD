"""One daily run of one book: account -> regime -> signals -> decision -> risk -> orders -> journal."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import indicators as ind
from . import strategies as strat
from .broker import Broker
from .config import STATE_DIR, Config
from .data import Bars, validate
from .llm import ClaudeAdvisor, ClaudeDecision, ClaudeError, RulesReview
from .models import Lot, SleevePlan, Target
from .regime import Regime, classify
from .risk import RiskEngine, breaker_status
from .state import BookState, journal, kill_switch_on

BOOKS = ("rules", "claude")
SLEEVES = ("A", "B", "C", "D")


# --- sleeve weights ---------------------------------------------------------------------------


def _basket_vol(bars: Bars, symbols: list[str], periods: int = 252) -> float:
    rets = pd.concat([bars[s]["close"].pct_change() for s in symbols if s in bars], axis=1).iloc[-60:]
    if rets.empty:
        return float("nan")
    return float(rets.mean(axis=1).std() * np.sqrt(periods))


def rules_sleeve_weights(cfg: Config, bars: Bars) -> dict[str, float]:
    """Inverse-volatility weights inside each sleeve's [min, max] band."""
    sl = cfg.sleeves
    vols = {
        "A": _basket_vol(bars, sl["A"]["assets"]),
        "B": _basket_vol(bars, sl["B"]["symbols"]),
        "C": _basket_vol(bars, sl["C"]["universe"]),
    }
    if cfg.sleeve_enabled("D"):
        vols["D"] = _basket_vol(bars, sl["D"]["symbols"], 365)
    med = float(np.nanmedian(list(vols.values())))
    weights = {}
    for s in SLEEVES:
        if s not in vols or np.isnan(vols[s]):
            weights[s] = sl[s]["default"] if s in vols else 0.0
            continue
        w = sl[s]["default"] * med / vols[s]
        weights[s] = float(np.clip(w, sl[s]["min"], sl[s]["max"]))
    return normalize_weights(cfg, weights)


def normalize_weights(cfg: Config, weights: dict[str, float]) -> dict[str, float]:
    sl = cfg.sleeves
    out = {s: float(np.clip(weights.get(s, 0.0), sl[s]["min"], sl[s]["max"])) for s in SLEEVES}
    if not cfg.sleeve_enabled("D"):
        out["D"] = 0.0
    budget = 1.0 - cfg.policy["portfolio"]["min_cash_buffer"]
    total = sum(out.values())
    if total > budget:
        out = {s: w * budget / total for s, w in out.items()}
    return out


# --- rule plans ---------------------------------------------------------------------------------


def build_plans(cfg: Config, bars: Bars, lots: dict[str, dict[str, Lot]], weights: dict[str, float],
                equity: float, regime: Regime, as_of: pd.Timestamp) -> dict[str, SleevePlan]:
    sl, pol, perm = cfg.sleeves, cfg.policy, regime.permissions
    plans = {
        "A": strat.sleeve_a(bars, sl["A"], equity * weights["A"], lots.get("A", {}), pol, as_of),
        "B": strat.sleeve_b(bars, sl["B"], equity * weights["B"], lots.get("B", {}), pol, equity, perm["B"]),
        "C": strat.sleeve_c(bars, sl["C"], equity * weights["C"], lots.get("C", {}), pol, equity, perm["C"]),
    }
    if cfg.sleeve_enabled("D"):
        plans["D"] = strat.sleeve_d(bars, sl["D"], equity * weights["D"], lots.get("D", {}), pol, perm["D"])
    return plans


def _is_increase(t: Target, lots: dict[str, dict[str, Lot]]) -> bool:
    lot = lots.get(t.sleeve, {}).get(t.symbol)
    return t.qty > (lot.qty if lot else 0.0) + 1e-9


def apply_review(targets: list[Target], review: RulesReview, lots: dict[str, dict[str, Lot]],
                 log: list[str]) -> list[Target]:
    """Claude may only shrink or skip increases in the rules book."""
    skip = {s.upper() for s in review.skip_entries}
    out = []
    for t in targets:
        if _is_increase(t, lots):
            cur = lots.get(t.sleeve, {}).get(t.symbol)
            cur_qty = cur.qty if cur else 0.0
            if t.symbol.upper() in skip:
                log.append(f"{t.sleeve}/{t.symbol}: entry skipped by Claude review")
                t = Target(t.symbol, t.sleeve, cur_qty, cur.stop if cur else None, "skipped by review")
            elif t.sleeve in review.halve_sleeves:
                log.append(f"{t.sleeve}/{t.symbol}: increase halved by Claude review")
                t = Target(t.symbol, t.sleeve, cur_qty + (t.qty - cur_qty) * 0.5, t.stop, t.reason + " (halved)")
        out.append(t)
    return out


# --- Claude book ----------------------------------------------------------------------------------


def decision_to_targets(cfg: Config, decision: ClaudeDecision, lots: dict[str, dict[str, Lot]], bars: Bars,
                        equity: float, log: list[str]) -> tuple[list[Target], dict[str, float]]:
    weights = normalize_weights(cfg, decision.sleeve_weights.model_dump())
    prices = {s: float(df["close"].iloc[-1]) for s, df in bars.items() if len(df)}
    allowed_class = {"A": {"etf"}, "B": {"etf", "stock"}, "C": {"etf", "stock"}, "D": {"crypto"}}

    actions = []
    for a in decision.actions:
        sym = a.symbol.upper()
        if sym not in prices:
            log.append(f"{a.sleeve}/{sym}: Claude action ignored, no price data")
            continue
        if cfg.asset_class(sym) not in allowed_class[a.sleeve]:
            log.append(f"{a.sleeve}/{sym}: Claude action ignored, {cfg.asset_class(sym)} not allowed in sleeve {a.sleeve}")
            continue
        if a.sleeve == "D" and not cfg.sleeve_enabled("D"):
            log.append(f"D/{sym}: Claude action ignored, crypto sleeve is disabled")
            continue
        actions.append((a, sym))

    # Scale each sleeve so its positions fit inside its weight.
    targets = []
    for s in SLEEVES:
        mine = [(a, sym) for a, sym in actions if a.sleeve == s]
        mentioned = {sym for _, sym in mine}
        untouched = sum(l.qty * prices.get(sym, 0.0) for sym, l in lots.get(s, {}).items() if sym not in mentioned)
        wanted = sum(a.target_pct_equity for a, _ in mine) * equity
        budget = max(0.0, weights[s] * equity - untouched)
        scale = min(1.0, budget / wanted) if wanted > 0 else 1.0
        if scale < 1.0:
            log.append(f"sleeve {s}: Claude targets scaled by {scale:.2f} to fit its {weights[s]:.0%} weight")
        for a, sym in mine:
            qty = a.target_pct_equity * scale * equity / prices[sym]
            stop = a.stop_price if a.stop_price > 0 else None
            targets.append(Target(sym, s, qty, stop, f"claude: {a.rationale[:160]}"))
    return targets, weights


# --- context shown to Claude ----------------------------------------------------------------


def build_context(book: str, cfg: Config, state: BookState, bars: Bars, equity: float, cash: float,
                  breakers, regime: Regime, weights: dict[str, float], plans: dict[str, SleevePlan],
                  problems: list[str], as_of: pd.Timestamp) -> dict:
    prices = {s: float(df["close"].iloc[-1]) for s, df in bars.items() if len(df)}
    positions = []
    for s, held in state.lots.items():
        for sym, l in held.items():
            price = prices.get(sym, float("nan"))
            risk = (l.entry_price - l.initial_stop) if l.initial_stop else None
            positions.append({
                "sleeve": s, "symbol": sym, "qty": round(l.qty, 6), "entry_price": round(l.entry_price, 2),
                "entry_date": l.entry_date, "stop": round(l.stop, 2) if l.stop else None, "price": round(price, 2),
                "pct_equity": round(l.qty * price / equity, 4),
                "unrealized_R": round((price - l.entry_price) / risk, 2) if risk else None,
            })
    rule_signals = {}
    for s, plan in plans.items():
        cands = plan.candidates
        if s == "C":
            cands = sorted(cands, key=lambda c: -c["rs_pct"])[:15]
        rule_signals[s] = {
            "sleeve_weight": round(weights[s], 3),
            "targets": [{"symbol": t.symbol, "target_pct_equity": round(t.qty * prices[t.symbol] / equity, 4),
                         "stop": round(t.stop, 2) if t.stop else None, "reason": t.reason}
                        for t in plan.targets.values() if t.symbol in prices],
            "indicators": cands,
            "notes": plan.notes,
        }
    hist = state.equity_history
    perf = {}
    if len(hist) >= 2:
        perf = {"book_return": round(hist[-1]["equity"] / hist[0]["equity"] - 1, 4),
                "spy_return": round(hist[-1]["benchmark"] / hist[0]["benchmark"] - 1, 4),
                "days": len(hist)}
    trades = state.closed_trades
    if trades:
        rs = [t["R"] for t in trades if t.get("R") is not None]
        perf.update({"closed_trades": len(trades), "win_rate": round(np.mean([t["pnl"] > 0 for t in trades]), 2),
                     "avg_R": round(float(np.mean(rs)), 2) if rs else None})
    bounds = {s: {"min": cfg.sleeves[s]["min"], "max": cfg.sleeves[s]["max"]} for s in SLEEVES}
    bounds["D"]["enabled"] = cfg.sleeve_enabled("D")
    return {
        "date": as_of.date().isoformat(),
        "book": book,
        "account": {"equity": round(equity, 2), "cash": round(cash, 2), "peak_equity": round(state.peak_equity, 2),
                    "drawdown": round(breakers.drawdown, 4), "day_pnl_R": round(breakers.day_pnl_R, 2),
                    "week_pnl_R": round(breakers.week_pnl_R, 2), "breakers": breakers.reasons,
                    "one_R_dollars": round(cfg.policy["per_trade"]["risk_pct_default"] * equity, 2)},
        "regime": regime.to_dict(),
        "sleeve_bounds": bounds,
        "positions": positions,
        "rule_signals": rule_signals,
        "allowlist": cfg.allowlist(),
        "data_problems": problems,
        "performance": perf,
        "recent_notes": state.notes[-5:],
    }


# --- bookkeeping ------------------------------------------------------------------------------


def reconcile(lots: dict[str, dict[str, Lot]], positions: dict[str, float], log: list[str]) -> None:
    """Make sleeve lots agree with what the broker actually holds (orders can fail or fill partially)."""
    totals: dict[str, float] = {}
    for held in lots.values():
        for sym, l in held.items():
            totals[sym] = totals.get(sym, 0.0) + l.qty
    for sym, total in totals.items():
        have = max(0.0, positions.get(sym, 0.0))
        if total <= 0 or abs(have - total) <= 0.01 * total:
            continue
        factor = have / total
        log.append(f"{sym}: broker holds {have:.4f}, book expected {total:.4f}; lots scaled by {factor:.3f}")
        for s in list(lots):
            if sym in lots[s]:
                if factor == 0:
                    del lots[s][sym]
                else:
                    lots[s][sym].qty *= factor


def update_lots(state: BookState, targets: list[Target], prices: dict[str, float], date: str) -> None:
    for t in targets:
        held = state.lots.setdefault(t.sleeve, {})
        lot = held.get(t.symbol)
        price = prices[t.symbol]
        if t.qty <= 1e-9:
            if lot:
                risk = (lot.entry_price - lot.initial_stop) if lot.initial_stop else None
                pnl = (price - lot.entry_price) * lot.qty
                state.closed_trades.append({
                    "date": date, "sleeve": t.sleeve, "symbol": t.symbol, "entry_date": lot.entry_date,
                    "entry_price": round(lot.entry_price, 4), "exit_price": round(price, 4), "qty": lot.qty,
                    "pnl": round(pnl, 2), "R": round((price - lot.entry_price) / risk, 2) if risk else None,
                    "reason": t.reason,
                })
                del held[t.symbol]
            continue
        if lot is None:
            held[t.symbol] = Lot(t.qty, price, date, t.stop, t.stop)
        else:
            if t.qty > lot.qty:
                lot.entry_price = (lot.entry_price * lot.qty + price * (t.qty - lot.qty)) / t.qty
            lot.qty = t.qty
            lot.stop = t.stop
    state.lots = {s: h for s, h in state.lots.items() if h}


# --- the run ------------------------------------------------------------------------------------


def run_book(book: str, cfg: Config, bars: Bars, broker: Broker, advisor: ClaudeAdvisor | None,
             as_of: pd.Timestamp, state_dir: Path = STATE_DIR, dry_run: bool = False,
             force: bool = False, state: BookState | None = None) -> dict:
    assert book in BOOKS
    state = state or BookState.load(book, state_dir)
    date = as_of.date().isoformat()
    if state.last_run_date == date and not force:
        return {"book": book, "skipped": f"already ran for {date} (use --force to rerun)"}

    log: list[str] = []
    if not dry_run:
        broker.cancel_open_orders()
    equity, cash = broker.account()
    positions = broker.positions()
    reconcile(state.lots, positions, log)

    bench = cfg.playbook["regime"]["benchmark"]
    prices = {s: float(df["close"].iloc[-1]) for s, df in bars.items() if len(df)}
    day_pnl, week_pnl = state.record_equity(date, equity, prices[bench])
    breakers = breaker_status(cfg, equity, state.peak_equity, day_pnl, week_pnl, state.halted,
                              kill_switch_on(state_dir))
    if breakers.drawdown >= cfg.policy["breakers"]["drawdown_halt"]:
        state.halted = True

    regime = classify(bars, bench, cfg.stock_universe(), cfg.playbook["regime"]["canaries"])
    problems = validate(bars, cfg.allowlist(), as_of)
    bad = {p.split(":")[0] for p in problems}

    weights = rules_sleeve_weights(cfg, bars)
    plans = build_plans(cfg, bars, state.lots, weights, equity, regime, as_of)
    claude_out, claude_meta, claude_error = None, None, None

    if book == "rules":
        proposed = [t for p in plans.values() for t in p.targets.values()]
        if advisor is not None:
            ctx = build_context(book, cfg, state, bars, equity, cash, breakers, regime, weights, plans, problems, as_of)
            try:
                review, claude_meta = advisor.review_rules_plan(ctx)
                proposed = apply_review(proposed, review, state.lots, log)
                claude_out = review.model_dump()
            except ClaudeError as e:
                claude_error = str(e)
                log.append(f"Claude review unavailable, rules run unreviewed: {e}")
    else:
        if advisor is None:
            proposed = []
            log.append("no Claude advisor: the Claude book only enforces stops today")
        else:
            ctx = build_context(book, cfg, state, bars, equity, cash, breakers, regime, weights, plans, problems, as_of)
            try:
                decision, claude_meta = advisor.decide(ctx)
                proposed, weights = decision_to_targets(cfg, decision, state.lots, bars, equity, log)
                claude_out = decision.model_dump()
            except ClaudeError as e:
                claude_error = str(e)
                proposed = []
                log.append(f"Claude decision unavailable, holding positions (stops still enforced): {e}")

    # Never open or add to a position whose data failed validation.
    safe = []
    for t in proposed:
        if t.symbol in bad and _is_increase(t, state.lots):
            log.append(f"{t.sleeve}/{t.symbol}: increase blocked, data problem")
            continue
        safe.append(t)

    result = RiskEngine(cfg).apply(safe, state.lots, positions, bars, equity, breakers)
    log += result.log
    fills = [] if dry_run else broker.submit(result.orders, f"{book}-{date}")

    if claude_out and claude_out.get("journal_note"):
        state.notes.append({"date": date, "note": claude_out["journal_note"]})
        state.notes = state.notes[-60:]
    if not dry_run:
        update_lots(state, result.targets, prices, date)
        state.last_run_date = date
        state.save(state_dir)

    entry = {
        "date": date, "book": book, "dry_run": dry_run, "equity": equity, "cash": cash,
        "drawdown": breakers.drawdown, "regime": regime.label, "sleeve_weights": weights,
        "claude": claude_out, "claude_meta": claude_meta, "claude_error": claude_error,
        "risk_log": log, "data_problems": problems,
        "orders": [o.__dict__ for o in result.orders], "fills": fills,
    }
    journal(book, entry, state_dir)
    return entry
