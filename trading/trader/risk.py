"""Deterministic risk engine. Nothing an LLM says can get past this file.

Input: per-sleeve targets from the rules or from Claude.
Output: the targets that survive the policy, the orders that get there, and a
log of every rejection or clip with its reason.

`RiskEngine.apply` works in this order (rule IDs from reports/Agent rulebook.md):
0. Held B/C/D lots get a stop if they have none (RISK-3), C stops trail the prior 10-session
   low (C-7), and B lots held 10 sessions exit (B-4). Both books.
1. Every lot whose close is at or below its stop exits (RISK-4).
2. Reductions always pass. Increases must be in the sleeve's own universe, clear the breakers
   (RISK-9 to RISK-13, M-11), carry a stop no wider than the rule stop in the Claude book (CL-14)
   and fit the per-trade risk (RISK-2).
3. Portfolio caps clip the increase only, never below what is held (RISK-5 to RISK-8, B-5, C-9).
4. Orders: sells first, then buys by sleeve priority; the daily cap drops buys from the end (EX-3).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from . import strategies
from .config import Config
from .data import Bars
from .models import Lot, Order, Target
from .options.models import is_occ

STOPPED_SLEEVES = ("B", "C", "D")
SPECULATIVE_SLEEVES = ("C", "D")  # RISK-7
EPS = 1e-9
LIMIT_EPS = 1e-12  # float noise: a drawdown of exactly 10% must trip the 10% tier


# --- small helpers -------------------------------------------------------------------------------


def _num(x, default: float = 0.0) -> float:
    """A finite float, or `default` for None, NaN, inf and anything that is not a number."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def _hits(value: float, limit) -> bool:
    """value >= limit, counting float noise as a hit (the safer side)."""
    return limit is not None and value >= limit - LIMIT_EPS


def _stop_or_none(x) -> float | None:
    """A usable stop price, or None (None, NaN, zero and negative all mean "no stop")."""
    v = _num(x, float("nan"))
    return v if math.isfinite(v) and v > 0 else None


def _unit(x) -> float:
    """A multiplier clamped to [0, 1]: nothing here may ever scale risk up. Garbage counts as 0."""
    return min(1.0, max(0.0, _num(x, 0.0)))


def _lot(lots: dict[str, dict[str, Lot]] | None, sleeve: str, symbol: str) -> Lot | None:
    return (lots or {}).get(sleeve, {}).get(symbol)


def _lot_qty(lots: dict[str, dict[str, Lot]] | None, sleeve: str, symbol: str) -> float:
    lot = _lot(lots, sleeve, symbol)
    return _num(lot.qty) if lot else 0.0


def last_prices(bars: Bars) -> dict[str, float]:
    """Last close per symbol. A missing, zero or negative last close means no price today."""
    out = {}
    for sym, df in bars.items():
        if df is None or not len(df) or "close" not in df:
            continue
        v = _num(df["close"].iloc[-1], float("nan"))
        if math.isfinite(v) and v > 0:
            out[sym] = v
    return out


def last_valid_closes(bars: Bars) -> dict[str, float]:
    """The latest usable close per symbol, even if today's is missing. Only exits are priced with it:
    a bad bar blocks increases (EX-7) but never an exit."""
    out = {}
    for sym, df in bars.items():
        if df is None or not len(df) or "close" not in df:
            continue
        c = pd.to_numeric(df["close"], errors="coerce")
        c = c[np.isfinite(c) & (c > 0)]
        if len(c):
            out[sym] = float(c.iloc[-1])
    return out


def trail_low(df: pd.DataFrame | None, n: int) -> float | None:
    """C-7: lowest low of the `n` sessions before the last bar (fewer if history is short), or None."""
    if df is None or len(df) < 2 or n <= 0 or "low" not in df:
        return None
    v = pd.to_numeric(df["low"].iloc[-(n + 1):-1], errors="coerce").min()
    return float(v) if pd.notna(v) and v > 0 else None


def _index_ts(df: pd.DataFrame, date) -> pd.Timestamp | None:
    """`date` as a Timestamp comparable with the bars' index (same time zone), or None."""
    if not date:
        return None
    try:
        ts = pd.Timestamp(date)
        if pd.isna(ts):
            return None
        tz = getattr(df.index, "tz", None)
        if tz is not None and ts.tzinfo is None:
            ts = ts.tz_localize(tz)
        elif tz is None and ts.tzinfo is not None:
            ts = ts.tz_localize(None)
        return ts
    except (TypeError, ValueError):
        return None


def sessions_held(df: pd.DataFrame | None, entry_date) -> int | None:
    """Bars dated after the entry (signal) date, or None when that cannot be counted."""
    if df is None:
        return None
    ts = _index_ts(df, entry_date)
    try:
        return None if ts is None else int((df.index > ts).sum())
    except TypeError:
        return None


def bars_through(df: pd.DataFrame | None, date) -> pd.DataFrame | None:
    """The bars up to and including `date`, or None when the date cannot be placed."""
    if df is None:
        return None
    ts = _index_ts(df, date)
    try:
        return None if ts is None else df[df.index <= ts]
    except TypeError:
        return None


# --- breakers -------------------------------------------------------------------------------------


def _full_mult() -> dict[str, float]:
    return {s: 1.0 for s in STOPPED_SLEEVES}


@dataclass
class Breakers:
    """What the book may do today. Percentages are fractions of equity (0.01 = 1%)."""

    drawdown: float
    halted: bool
    no_new_entries: bool
    risk_mult: float  # RISK-9: 0.5 from a 10% drawdown
    day_pnl_R: float
    week_pnl_R: float
    reasons: list[str] = field(default_factory=list)
    day_pnl_pct: float = 0.0  # RISK-11
    week_pnl_pct: float = 0.0
    month_pnl_pct: float = 0.0  # RISK-12: against prior month-end equity
    watch: bool = False  # RISK-10: the Claude book may not raise B, C or D weights
    monthly_block: bool = False  # RISK-12: no new B, C or D entries this month; A is exempt
    sleeve_risk_mult: dict = field(default_factory=_full_mult)  # RISK-13 / M-11: B/C/D -> 1.0, 0.5 or 0.0
    sleeve_reasons: dict = field(default_factory=dict)  # sleeve -> plain-English reason when below 1.0
    sleeve_dd_pct: dict = field(default_factory=dict)  # RISK-13: sleeve P&L below its peak, share of equity

    def to_dict(self) -> dict:
        return asdict(self)


def sleeve_drawdown(record: dict | None, equity: float) -> float:
    """RISK-13: (peak - cum) / equity for one `state.sleeve_pnl` entry. Sleeve P&L starts at 0, so the
    peak is never below 0 or below today's cum."""
    eq = _num(equity)
    if not isinstance(record, dict) or eq <= 0:
        return 0.0
    cum = _num(record.get("cum", record.get("realized")))
    peak = max(0.0, _num(record.get("peak")), cum)
    return (peak - cum) / eq


def sleeves_to_latch(cfg: Config, equity: float, sleeve_pnl: dict | None) -> dict[str, str]:
    """RISK-13: sleeves whose P&L is `sleeve_dd_off` or more below peak. The engine stores these in
    `state.sleeve_blocked`, so their new entries stay off until the owner resets them."""
    off = cfg.policy["breakers"].get("sleeve_dd_off")
    out = {}
    for s in STOPPED_SLEEVES:
        dd = sleeve_drawdown((sleeve_pnl or {}).get(s), equity)
        if _hits(dd, off):
            out[s] = f"sleeve {s} P&L fell {dd:.1%} of equity below its peak (limit {off:.0%}, RISK-13)"
    return out


def _history(equity_history: list[dict] | None, date: str) -> list[tuple[pd.Timestamp, float]]:
    """(date, equity) rows on or before `date` with a usable date and equity, oldest first."""
    end, rows = pd.Timestamp(date), []
    for h in equity_history or []:
        if not isinstance(h, dict):
            continue
        try:
            ts = pd.Timestamp(h.get("date"))
        except (TypeError, ValueError):
            continue
        v = _num(h.get("equity"), float("nan"))
        if pd.notna(ts) and ts <= end and math.isfinite(v):
            rows.append((ts, v))
    return sorted(rows, key=lambda r: r[0])


def period_start_equity(equity_history: list[dict] | None, date: str, freq: str = "M") -> float | None:
    """RISK-11/12 base: equity at the last run before `date`'s month ("M") or week ("W"). With no
    earlier run (the book's first month or week), the first equity recorded in this period."""
    rows, period = _history(equity_history, date), pd.Timestamp(date).to_period(freq)
    before = [v for ts, v in rows if ts.to_period(freq) < period]
    if before:
        return before[-1]
    inside = [v for ts, v in rows if ts.to_period(freq) == period]
    return inside[0] if inside else None


def _worst_pnl(equity_history: list[dict] | None, date: str, freq: str, base: float | None) -> float | None:
    base = _num(base) or _num(period_start_equity(equity_history, date, freq))
    period = pd.Timestamp(date).to_period(freq)
    vals = [v for ts, v in _history(equity_history, date) if ts.to_period(freq) == period]
    return min(vals) - base if vals and base > 0 else None


def month_worst_pnl(equity_history: list[dict] | None, date: str, base: float | None = None) -> float | None:
    """RISK-12 latch input: the lowest month-to-date P&L recorded so far in `date`'s month.

    Pass it to `breaker_status(month_worst_pnl=...)` so the block holds for the rest of the month
    even if the loss recovers. `base` defaults to `period_start_equity(..., "M")`.
    """
    return _worst_pnl(equity_history, date, "M", base)


def week_worst_pnl(equity_history: list[dict] | None, date: str, base: float | None = None) -> float | None:
    """RISK-11 latch input: the lowest week-to-date P&L recorded so far in `date`'s week."""
    return _worst_pnl(equity_history, date, "W", base)


def loss_inputs(equity_history: list[dict] | None, date: str, equity: float) -> dict:
    """Keyword arguments for `breaker_status` (RISK-11 and RISK-12) from the equity history, after
    today's equity is recorded. Works in the first month too, where there is no prior month-end."""
    base = period_start_equity(equity_history, date, "M")
    return {"month_pnl": _num(equity) - base if base else 0.0, "month_base": base,
            "month_worst_pnl": month_worst_pnl(equity_history, date, base),
            "week_worst_pnl": week_worst_pnl(equity_history, date)}


def _drawdown(equity: float, peak: float) -> float:
    if not math.isfinite(equity) or peak <= 0:
        return 0.0
    return max(0.0, (peak - equity) / peak)


def _monthly(b: dict, equity: float, month_pnl, month_base, month_worst) -> tuple[float, bool, str | None]:
    """RISK-12: (month-to-date P&L as a share of prior month-end equity, block?, reason)."""
    pnl = _num(month_pnl)
    base = _num(month_base)
    if base <= 0 and pnl != 0 and equity - pnl > 0:
        base = equity - pnl  # no stored month-end: estimate it from today's equity
    if base <= 0:
        return 0.0, False, None
    pct = pnl / base
    worst = min(pnl, _num(month_worst, pnl)) / base
    limit = b.get("monthly_loss_pct")
    if not _hits(-worst, limit):
        return pct, False, None
    if _hits(-pct, limit):
        why = f"month-to-date loss {pct:.2%} of prior month-end equity"
    else:
        why = f"month-to-date loss reached {worst:.2%} of prior month-end equity earlier this month"
    return pct, True, f"{why} (limit -{limit:.0%}): no new B, C or D entries for the rest of the month; A is exempt"


def _sleeve_tiers(b: dict, equity: float, sleeve_pnl, sleeve_blocked, demotion
                  ) -> tuple[dict[str, float], dict[str, list[str]], dict[str, float]]:
    """RISK-13 and M-11 per sleeve: the lowest multiplier from every tier that applies."""
    mult, why, dds = _full_mult(), {s: [] for s in STOPPED_SLEEVES}, {}
    halve, off = b.get("sleeve_dd_halve"), b.get("sleeve_dd_off")

    def lower(s: str, m: float, reason: str) -> None:
        mult[s] = min(mult[s], m)
        why[s].append(reason)

    for s in STOPPED_SLEEVES:
        dd = sleeve_drawdown((sleeve_pnl or {}).get(s), equity)
        dds[s] = dd
        if _hits(dd, off):
            lower(s, 0.0, f"sleeve {s} P&L is {dd:.1%} of equity below its peak (>= {off:.0%}): "
                          "its new entries stop until the owner reviews")
        elif _hits(dd, halve):
            lower(s, 0.5, f"sleeve {s} P&L is {dd:.1%} of equity below its peak (>= {halve:.0%}): "
                          "its new entries run at half risk")
        blocked = (sleeve_blocked or {}).get(s)
        if blocked:
            lower(s, 0.0, f"sleeve {s} new entries stopped until the owner reviews: {blocked}")
        d = (demotion or {}).get(s)
        if d == "half":
            lower(s, 0.5, f"sleeve {s} demoted (M-11: expectancy below zero): min weight at half risk")
        elif d:
            lower(s, 0.0, f"sleeve {s} demoted (M-11, '{d}'): new entries stop pending review")
    return mult, why, dds


def breaker_status(cfg: Config, equity: float, peak: float, day_pnl: float, week_pnl: float,
                   halted_flag: bool, kill_switch: bool, *, month_pnl: float = 0.0,
                   month_base: float | None = None, sleeve_pnl: dict | None = None,
                   sleeve_blocked: dict | None = None, demotion: dict | None = None,
                   month_worst_pnl: float | None = None, week_worst_pnl: float | None = None) -> Breakers:
    """RISK-9 to RISK-13, RISK-15 and M-11 from today's numbers. Pure: the engine latches the halt
    (RISK-9) and the sleeve blocks (`sleeves_to_latch`). `loss_inputs` gives the month and week
    keywords, including the worst P&L so far, so the weekly and monthly blocks hold once hit."""
    b = cfg.policy["breakers"]
    eq = _num(equity, float("nan"))
    eq_ok = math.isfinite(eq) and eq > 0
    pk = _num(peak, float("nan"))
    peak_ok = math.isfinite(pk) and pk > 0
    dd = _drawdown(eq, pk) if peak_ok else 0.0
    reasons: list[str] = []

    # RISK-9 and RISK-15
    halt_dd = _hits(dd, b["drawdown_halt"])
    halted = bool(halted_flag or kill_switch or halt_dd)
    if kill_switch:
        reasons.append("kill switch is on")
    if halted_flag:
        reasons.append("book halted, needs a human to re-enable")
    if halt_dd:
        reasons.append(f"drawdown {dd:.1%} >= {b['drawdown_halt']:.0%}: halt, exits only")
    no_new_dd = _hits(dd, b["drawdown_no_new_entries"])
    no_new = halted or no_new_dd
    if no_new_dd and not halted:
        reasons.append(f"drawdown {dd:.1%}: no new entries")
    if not eq_ok and not halted:
        no_new = True
        reasons.append("equity is zero or unknown: no new entries")
    elif not peak_ok and not halted:
        # Without a high-water mark the drawdown tiers cannot be checked, so they must not pass silently.
        no_new = True
        reasons.append("high-water mark is zero or unknown, so drawdown cannot be checked: no new entries")

    # RISK-11, in % of equity (the R values stay for old readers)
    one_r = cfg.policy["per_trade"]["risk_pct_default"] * eq if eq_ok else 0.0
    day, week = _num(day_pnl), _num(week_pnl)
    day_r, week_r = (day / one_r, week / one_r) if one_r > 0 else (0.0, 0.0)
    day_pct, week_pct = (day / eq, week / eq) if eq_ok else (0.0, 0.0)
    worst_week_pct = min(week, _num(week_worst_pnl, week)) / eq if eq_ok else 0.0
    if _hits(-day_pct, b["daily_loss_pct"]):
        no_new = True
        reasons.append(f"daily loss {day_pct:.2%} of equity: no new entries today")
    if _hits(-week_pct, b["weekly_loss_pct"]):
        no_new = True
        reasons.append(f"weekly loss {week_pct:.2%} of equity: no new entries this week")
    elif _hits(-worst_week_pct, b["weekly_loss_pct"]):
        no_new = True
        reasons.append(f"weekly loss reached {worst_week_pct:.2%} of equity earlier this week: "
                       "no new entries for the rest of the week")

    risk_mult = 0.5 if _hits(dd, b["drawdown_halve_risk"]) else 1.0
    if risk_mult < 1 and not no_new:
        reasons.append(f"drawdown {dd:.1%}: risk per trade halved")

    # RISK-10
    watch = _hits(dd, b.get("watch_drawdown", 0.05))
    if watch:
        reasons.append(f"drawdown {dd:.1%} >= {b.get('watch_drawdown', 0.05):.0%} watch tier: "
                       "the Claude book may not raise B, C or D weights")

    # RISK-12
    month_pct, monthly_block, why = _monthly(b, eq if eq_ok else 0.0, month_pnl, month_base, month_worst_pnl)
    if why:
        reasons.append(why)

    # RISK-13 and M-11
    mult, sleeve_why, dds = _sleeve_tiers(b, eq if eq_ok else 0.0, sleeve_pnl, sleeve_blocked, demotion)
    sleeve_reasons = {s: "; ".join(w) for s, w in sleeve_why.items() if w}
    reasons.extend(sleeve_reasons.values())

    return Breakers(dd, halted, no_new, risk_mult, day_r, week_r, reasons,
                    day_pnl_pct=day_pct, week_pnl_pct=week_pct, month_pnl_pct=month_pct, watch=watch,
                    monthly_block=monthly_block, sleeve_risk_mult=mult, sleeve_reasons=sleeve_reasons,
                    sleeve_dd_pct=dds)


# --- the engine ---------------------------------------------------------------------------------


@dataclass
class RiskResult:
    targets: list[Target]
    orders: list[Order]
    log: list[str]


@dataclass
class _Day:
    """Everything one `apply` call works on, so each step can be a short method."""

    lots: dict[str, dict[str, Lot]]
    bars: Bars
    prices: dict[str, float]
    equity: float
    breakers: Breakers
    permissions: dict | None
    weights: dict | None
    promoted: tuple
    book: str
    allow: set[str]
    log: list[str]
    ref: dict[str, float] = field(default_factory=dict)  # last valid close, used only to price exits
    marks: dict[str, float] = field(default_factory=dict)  # for notional: today's close, else ref, else entry
    final: dict[tuple[str, str], Target] = field(default_factory=dict)


class RiskEngine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.p = cfg.policy

    def apply(self, proposed: list[Target], lots: dict[str, dict[str, Lot]], broker_qty: dict[str, float],
              bars: Bars, equity: float, breakers: Breakers, *, permissions: dict | None = None,
              weights: dict | None = None, promoted=(), book: str = "rules") -> RiskResult:
        """Turn proposed targets into the targets and orders the policy allows.

        permissions: regime permission per sleeve (REG-3), scales B/C/D per-trade risk; None means 1.
        weights: today's final sleeve weights; each sleeve's notional stays under min(weight, RISK-8 cap).
        promoted: sleeves that passed M-10 (RISK-8). book: "rules" or "claude"; the CL-14 stop floor
        applies to every book except "rules", whose stops already are the rule stops.
        """
        day = _Day(lots=lots, bars=bars, prices=last_prices(bars), equity=_num(equity), breakers=breakers,
                   permissions=permissions, weights=weights, promoted=tuple(promoted or ()), book=book,
                   allow=set(self.cfg.allowlist()), log=list(breakers.reasons), ref=last_valid_closes(bars))
        held = {sym: _num(lot.entry_price) for h in lots.values() for sym, lot in h.items()}
        day.marks = {**held, **day.ref, **day.prices}

        # Start from current holdings; every proposal is a change against them.
        for sleeve, h in lots.items():
            for sym, lot in h.items():
                day.final[(sleeve, sym)] = Target(sym, sleeve, _num(lot.qty), _stop_or_none(lot.stop), "unchanged")

        # 0-1. Exits no decider can override.
        self._ratchet_stops(day)
        enforced = self._time_stops(day)
        enforced |= self._stop_hits(day, enforced)
        held_stop = {k: t.stop for k, t in day.final.items()}

        # 2-3. Reductions first (always allowed), then increases in sleeve order.
        def delta(t: Target) -> float:
            cur = day.final.get((t.sleeve, t.symbol))
            return float(t.qty) - (cur.qty if cur else 0.0)

        for t in sorted(self._valid(proposed, day.log), key=lambda t: (delta(t) > 0, t.sleeve)):
            if (t.sleeve, t.symbol) not in enforced:
                self._apply_one(t, day)

        for sym in untracked_symbols(broker_qty, lots):
            day.log.append(f"{sym}: held at the broker but not opened by this book, left untouched")
        targets = [t for t in day.final.values() if t.qty > 0 or _lot(lots, t.sleeve, t.symbol)]

        # 4. Orders. Buys over the daily cap are dropped and their increases fall back to the lots. That
        # can turn a symbol's net buy into a sell (another sleeve's exit), which takes a slot, so repeat.
        dropped: list[str] = []
        while True:
            order_log: list[str] = []
            orders, over = self._orders(targets, broker_qty, day.prices, order_log, lots, day.ref)
            if not over:
                break
            dropped += over
            _undo_increases(targets, set(over), lots, held_stop)
        day.log += order_log
        self._log_order_cap(orders, dropped, day.log)
        targets = [t for t in targets if t.qty > 0 or _lot(lots, t.sleeve, t.symbol)]
        return RiskResult(targets, orders, day.log)

    def _log_order_cap(self, orders: list[Order], dropped: list[str], log: list[str]) -> None:
        """EX-3: say which buys the daily cap dropped, and when exits alone go over it (exits are never held)."""
        cap = self.p["turnover"]["max_orders_per_day"]
        if dropped:
            log.append(f"order cap: {len(dropped)} buy order(s) dropped (max {cap}/day): {', '.join(dropped)}")
        sold = {o.symbol for o in orders if o.side == "sell"}
        for sym in dropped:
            if sym in sold:
                log.append(f"{sym}: buy dropped by the order cap; other sleeves' reductions still sold")
        if len(sold) > cap:
            log.append(f"order cap: {len(sold)} sell orders are over the {cap}/day cap; exits are never held back")

    # --- step 0-1: exits in both books ---------------------------------------------------------

    def _ratchet_stops(self, day: _Day) -> None:
        """RISK-3 and C-7: every held B/C/D lot gets a stop; C stops trail the prior 10-session low.
        Stops only ever rise here, and the new stop travels in the targets so the ledger keeps it."""
        trail = self.p["per_trade"].get("trail_low_sessions") or {}
        for (sleeve, sym), t in day.final.items():
            if sleeve not in STOPPED_SLEEVES or t.qty <= 0:
                continue
            tag = f"{sleeve}/{sym}"
            if t.stop is None:
                t.stop, why = self._held_lot_stop(sleeve, sym, _lot(day.lots, sleeve, sym), day)
                day.log.append(f"{tag}: held without a stop, set to {why} (RISK-3)" if t.stop is not None
                               else f"{tag}: held without a stop and no rule stop can be computed: {why}")
            n = int(_num(trail.get(sleeve)))
            low = trail_low(day.bars.get(sym), n) if n > 0 else None
            if low is not None and (t.stop is None or low > t.stop):
                old = "none" if t.stop is None else f"{t.stop:.2f}"
                t.stop = low
                day.log.append(f"{tag}: stop raised {old} -> {low:.2f} (C-7: lowest low of the prior {n} sessions)")

    def _held_lot_stop(self, sleeve: str, sym: str, lot: Lot | None, day: _Day) -> tuple[float | None, str]:
        """RISK-3 for a held lot with no stop: the rule stop as of its entry date (B-4c: entry - 3 x ATR20,
        never trailed; C-6 likewise), so a losing lot does not get a looser stop from today's lower
        close. That stop may already be hit, and then the lot exits (RISK-4). Falls back to the rule
        stop at today's close when the entry date is not in the bars."""
        at_entry = self._rule_stop_df(sleeve, bars_through(day.bars.get(sym), lot.entry_date if lot else None))
        if at_entry is not None:
            return at_entry, f"the rule stop on its entry date {lot.entry_date}, {at_entry:.2f}"
        today = self._rule_stop(sleeve, sym, day.bars)
        if today is not None and today < day.prices.get(sym, math.inf):
            return today, f"the rule stop at today's close {today:.2f} (entry date not in the bars)"
        return None, "no usable bars for this symbol"

    def _time_stops(self, day: _Day) -> set[tuple[str, str]]:
        """B-4(b): a lot held for `time_stop_days` sessions exits, whoever is deciding."""
        limits = self.p["per_trade"].get("time_stop_days") or {}
        out = set()
        for key, t in day.final.items():
            sleeve, sym = key
            n = int(_num(limits.get(sleeve)))
            lot = _lot(day.lots, sleeve, sym)
            if n <= 0 or t.qty <= 0 or lot is None:
                continue
            held = sessions_held(day.bars.get(sym), lot.entry_date)
            tag = f"{sleeve}/{sym}"
            if held is None:
                day.log.append(f"{tag}: cannot count sessions held, time stop not checked")
            elif held >= n and sym not in day.ref:
                day.log.append(f"{tag}: held {held} sessions (limit {n}), time stop due but there is no price "
                               "to send the exit with: exit deferred")
            elif held >= n:
                day.final[key] = Target(sym, sleeve, 0.0, t.stop, "time stop (enforced)")
                note = ("" if sym in day.prices
                        else f"; no valid close today, sent at the last valid close {day.ref[sym]:.2f}")
                day.log.append(f"{tag}: held {held} sessions (limit {n}), time stop exit enforced (B-4){note}")
                out.add(key)
        return out

    def _stop_hits(self, day: _Day, skip: set) -> set[tuple[str, str]]:
        """RISK-4: a close at or below the (ratcheted) stop exits at the next open, in both books."""
        out = set()
        for key, t in day.final.items():
            if key in skip or t.stop is None or t.qty <= 0:
                continue
            price = day.prices.get(t.symbol)
            if price is None:
                day.log.append(f"{t.sleeve}/{t.symbol}: no valid close today, stop not checked")
            elif price * 2 < t.stop and self._calm_close(day, t.symbol):
                # A close under half the stop on an ordinary day is a stop on another price scale (a split
                # the ledger missed), not a stop hit: selling would book a fake loss. Hold and block increases.
                day.allow.discard(t.symbol)
                day.log.append(f"DATA PROBLEM {t.sleeve}/{t.symbol}: close {price:.2f} is under half the stop "
                               f"{t.stop:.2f} after an ordinary day (unhandled split?); stop not enforced, no "
                               "increases; the owner must check the lot")
            elif price <= t.stop:
                day.final[key] = Target(t.symbol, t.sleeve, 0.0, t.stop, "stop hit (enforced)")
                day.log.append(f"{t.sleeve}/{t.symbol}: close {price:.2f} <= stop {t.stop:.2f}, exit enforced")
                out.add(key)
        return out

    def _calm_close(self, day: _Day, sym: str) -> bool:
        """The last close moved less than the data check's daily limit (EX-7) from the one before. A real
        crash through the stop moves more than that; an unhandled split does not (the bars are adjusted)."""
        df = day.bars.get(sym)
        if df is None or "close" not in df:
            return False
        c = pd.to_numeric(df["close"], errors="coerce")
        c = c[np.isfinite(c) & (c > 0)]
        if len(c) < 2:
            return False
        limit = _num(self.p.get("data_checks", {}).get("max_daily_move"), 0.25)
        return abs(float(c.iloc[-1]) / float(c.iloc[-2]) - 1) <= limit

    # --- step 2: one proposal ------------------------------------------------------------------

    def _valid(self, proposed: list[Target], log: list[str]) -> list[Target]:
        """Drop proposals no step can handle: unknown sleeves and quantities that are not numbers."""
        out = []
        for t in proposed:
            if t.sleeve not in self.cfg.sleeves:
                log.append(f"{t.sleeve}/{t.symbol}: rejected, unknown sleeve")
            elif not math.isfinite(_num(t.qty, float("nan"))):
                log.append(f"{t.sleeve}/{t.symbol}: rejected, target quantity is not a number")
            else:
                out.append(t)
        return out

    def _apply_one(self, t: Target, day: _Day) -> None:
        key, tag = (t.sleeve, t.symbol), f"{t.sleeve}/{t.symbol}"
        cur = day.final.get(key)
        cur_qty = cur.qty if cur else 0.0
        qty = max(0.0, float(t.qty))  # long only (RISK-1)
        stop = _stop_or_none(t.stop)
        if cur and cur.stop is not None and self.p["per_trade"]["never_widen_stop"]:
            stop = cur.stop if stop is None else max(stop, cur.stop)  # RISK-3
        increase = qty > cur_qty
        if is_occ(t.symbol):  # OPT-2: account.options is false for books A-D; only book O trades options
            day.log.append(f"{tag}: rejected, OCC option symbol (OPT-2: the stock path never trades options)")
            return
        if increase and t.symbol not in day.allow:
            day.log.append(f"{tag}: rejected, not on the allowlist")
            return
        if increase and t.symbol not in day.prices:
            day.log.append(f"{tag}: increase rejected, no valid close today")
            return
        if t.symbol not in day.ref:
            day.log.append(f"{tag}: rejected, no price")
            return
        if not increase:
            if t.symbol not in day.prices and qty < cur_qty:
                day.log.append(f"{tag}: no valid close today; the reduction is sent at the last valid close "
                               f"{day.ref[t.symbol]:.2f}")
            day.final[key] = Target(t.symbol, t.sleeve, qty, stop, t.reason)
            return
        sized = self._size_increase(t, qty, stop, cur_qty, day)
        if sized is None:
            return
        qty, stop = sized
        qty = self._clip_portfolio(t, qty, cur_qty, stop, day)
        if qty > cur_qty + EPS:
            day.final[key] = Target(t.symbol, t.sleeve, qty, stop, t.reason)

    def _size_increase(self, t: Target, qty: float, stop: float | None, cur_qty: float,
                       day: _Day) -> tuple[float, float | None] | None:
        """Breakers, stop and per-trade risk for one increase. None means rejected (holding unchanged)."""
        tag, b, price = f"{t.sleeve}/{t.symbol}", day.breakers, day.prices[t.symbol]
        why = self._increase_blocked(t.sleeve, t.symbol, day)
        if why:
            day.log.append(f"{tag}: increase rejected ({why})")
            return None
        if t.sleeve not in STOPPED_SLEEVES:  # sleeve A: no stops (A-5); a drawdown scales the increase
            mult = _unit(b.risk_mult)
            return (cur_qty + (qty - cur_qty) * mult if mult < 1 else qty), stop
        lot = _lot(day.lots, t.sleeve, t.symbol)
        if self.p["per_trade"]["no_averaging_down"] and lot and lot.qty > 0 and price < lot.entry_price:
            day.log.append(f"{tag}: rejected, no averaging down")
            return None
        cur = day.final.get((t.sleeve, t.symbol))
        stop = self._entry_stop(t, stop, price, day, cur.stop if cur else None)
        if stop is None:
            return None
        return self._per_trade_cap(t, qty, stop, price, day), stop

    def _universe(self, sleeve: str) -> set[str]:
        """The symbols a sleeve may buy (CL-11 backstop): A its assets and cash (and GEM when blended),
        B its ETFs, C its stock universe, D its coins."""
        s = self.cfg.sleeves.get(sleeve) or {}
        out = set(s.get("assets", [])) | set(s.get("symbols", [])) | set(s.get("universe", []))
        if s.get("cash"):
            out.add(s["cash"])
        if s.get("gem_blend"):
            out |= set((s.get("gem") or {}).values())
        return out

    def _increase_blocked(self, sleeve: str, symbol: str, day: _Day) -> str | None:
        """Why no increase is allowed in this sleeve and symbol today, or None."""
        b = day.breakers
        if b.no_new_entries:
            return "; ".join(b.reasons) or "breakers: no new entries"
        if day.equity <= 0:
            return "equity is zero or unknown"
        if not self.cfg.sleeve_enabled(sleeve):
            return f"sleeve {sleeve} is disabled (D-1)"
        # A symbol bought under another sleeve's label would skip that sleeve's stop, caps and blocks.
        if symbol not in self._universe(sleeve):
            return f"{symbol} is not in sleeve {sleeve}'s universe"
        if sleeve not in STOPPED_SLEEVES:
            return None
        if getattr(b, "monthly_block", False):
            return "monthly loss cap: no new B, C or D entries this month (RISK-12)"
        if self._sleeve_mult(sleeve, day) <= 0:
            reason = (getattr(b, "sleeve_reasons", None) or {}).get(sleeve, "sleeve tier")
            return f"sleeve {sleeve} new entries stopped: {reason}"
        if self._permission(sleeve, day) <= 0:
            return f"regime permission for sleeve {sleeve} is 0"
        return None

    def _entry_stop(self, t: Target, stop: float | None, price: float, day: _Day,
                    held: float | None = None) -> float | None:
        """RISK-3 and CL-14: the stop an increase must carry, or None (rejected, logged).

        A missing stop or one at/above the price becomes the rule stop, but never below the stop the
        lot already holds (`held`, after the C-7 ratchet). Outside the rules book a stop below the rule
        stop is raised to it: tighter is allowed, wider never.
        """
        tag = f"{t.sleeve}/{t.symbol}"
        rule = self._rule_stop(t.sleeve, t.symbol, day.bars)
        rule = rule if rule is not None and rule < price else None
        if stop is None or stop >= price:
            if rule is None:
                day.log.append(f"{tag}: increase rejected, no valid stop and the rule stop cannot be computed")
                return None
            new = rule if held is None else max(rule, held)
            if new >= price:
                day.log.append(f"{tag}: increase rejected, the held stop {new:.2f} is at or above the price")
                return None
            day.log.append(f"{tag}: missing or invalid stop, set to {new:.2f}")
            return new
        if day.book == "rules":
            return stop
        if rule is None:
            day.log.append(f"{tag}: increase rejected, the rule stop cannot be computed to check the stop (CL-14)")
            return None
        if stop < rule:
            day.log.append(f"{tag}: stop {stop:.2f} raised to the rule stop {rule:.2f} (CL-14)")
            return rule
        return stop

    def _per_trade_cap(self, t: Target, qty: float, stop: float, price: float, day: _Day) -> float:
        """RISK-2: (price - stop) x qty <= min(1R x drawdown mult x sleeve tier x regime permission,
        hard cap) x equity."""
        b = day.breakers
        pct = (self.cfg.risk_pct(t.sleeve) * _unit(b.risk_mult) * self._sleeve_mult(t.sleeve, day)
               * self._permission(t.sleeve, day))
        pct = min(pct, self.p["per_trade"]["risk_pct_hard_cap"])
        cap = pct * day.equity / (price - stop)
        if qty > cap:
            day.log.append(f"{t.sleeve}/{t.symbol}: qty {qty:.4f} clipped to {cap:.4f} by per-trade risk "
                           f"({pct:.2%} of equity)")
            qty = cap
        return qty

    def _sleeve_mult(self, sleeve: str, day: _Day) -> float:
        """RISK-13 / M-11 multiplier for a sleeve (1.0 when the breakers do not mention it)."""
        return _unit((getattr(day.breakers, "sleeve_risk_mult", None) or {}).get(sleeve, 1.0))

    def _permission(self, sleeve: str, day: _Day) -> float:
        """REG-3 regime permission for a sleeve; 1.0 when no permissions are given."""
        if day.permissions is None:
            return 1.0
        return _unit(day.permissions.get(sleeve, 1.0))

    # --- step 3: portfolio caps -------------------------------------------------------------------

    def _clip_portfolio(self, t: Target, qty: float, cur_qty: float, stop: float | None, day: _Day) -> float:
        """Portfolio caps. Each clips only the increase, never below the current quantity."""
        tag = f"{t.sleeve}/{t.symbol}"
        others = [o for k, o in day.final.items() if k != (t.sleeve, t.symbol) and o.qty > 0]
        why = self._rejects_new_position(t, cur_qty, others, day)
        if why:
            day.log.append(f"{tag}: {why}")
            return cur_qty
        for limit, label in self._caps(t, stop, day.prices[t.symbol], others, day):
            if qty > limit + EPS:
                qty = max(cur_qty, limit)
                day.log.append(f"{tag}: clipped {label}")
        return max(qty, cur_qty)

    def _rejects_new_position(self, t: Target, cur_qty: float, others: list[Target], day: _Day) -> str | None:
        """C-9 sector cap and the RISK-5 correlation limit, both only for new positions."""
        if cur_qty > 0:
            return None
        pf, cfg = self.p["portfolio"], self.cfg
        group, limit = cfg.sector_of(t.symbol), pf.get("sector_max_positions")
        if t.sleeve == "C" and group and limit is not None:
            n = sum(1 for o in others if o.sleeve == "C" and cfg.sector_of(o.symbol) == group)
            if n >= limit:
                return f"rejected, {n} open C positions already in sector group '{group}' (C-9 max {limit})"
        if cfg.asset_class(t.symbol) == "stock":
            corr = pf["correlated_positions"]
            rets = day.bars[t.symbol]["close"].pct_change().iloc[-60:]
            n = 0
            for o in others:
                if cfg.asset_class(o.symbol) == "stock" and o.symbol in day.bars:
                    with np.errstate(invalid="ignore", divide="ignore"):  # flat prices: rho is NaN, skipped
                        rho = rets.corr(day.bars[o.symbol]["close"].pct_change().iloc[-60:])
                    if not np.isnan(rho) and rho > corr["rho_60d"]:
                        n += 1
            if n >= corr["max_count"]:
                return f"rejected, {n} held stocks with 60d correlation > {corr['rho_60d']}"
        return None

    def _caps(self, t: Target, stop: float | None, price: float, others: list[Target], day: _Day):
        """Yield (largest total qty allowed, label) for every cap that applies to this increase."""
        pf, cfg, eq = self.p["portfolio"], self.cfg, day.equity

        def notional(items) -> float:
            return sum(o.qty * day.marks.get(o.symbol, 0.0) for o in items)

        def heat(items) -> float:
            return sum(max(0.0, day.marks.get(o.symbol, 0.0) - o.stop) * o.qty for o in items if o.stop is not None)

        # RISK-5: per-symbol notional summed across sleeves, cash buffer, open-risk heat.
        cls = cfg.asset_class(t.symbol)
        cap = {"etf": pf["max_single_etf_notional"], "stock": pf["max_single_stock_notional"],
               "crypto": pf["max_single_crypto_notional"]}[cls]
        same = sum(o.qty for o in others if o.symbol == t.symbol) * price
        yield (cap * eq - same) / price, f"to {cap:.0%} {cls} notional cap"
        yield ((1 - pf["min_cash_buffer"]) * eq - notional(others)) / price, \
            f"by {pf['min_cash_buffer']:.0%} cash buffer"
        if stop is not None and price > stop:
            yield (pf["max_open_risk_heat"] * eq - heat(others)) / (price - stop), \
                f"by {pf['max_open_risk_heat']:.0%} open-risk heat"
            # B-5: correlated index ETFs in one sleeve share a smaller heat budget.
            for name, c in (pf.get("cluster_heat") or {}).items():
                sleeve, members = c.get("sleeve", "B"), set(c.get("symbols", []))
                if t.sleeve == sleeve and t.symbol in members:
                    inside = [o for o in others if o.sleeve == sleeve and o.symbol in members]
                    yield (c["max"] * eq - heat(inside)) / (price - stop), f"by {c['max']:.2%} {name} cluster heat (B-5)"
        # RISK-6: equity-like ETFs and all single stocks, every sleeve.
        if "max_equity_like" in pf and cfg.is_equity_like(t.symbol):
            eq_like = notional([o for o in others if cfg.is_equity_like(o.symbol)])
            yield (pf["max_equity_like"] * eq - eq_like) / price, f"by {pf['max_equity_like']:.0%} equity-like cap (RISK-6)"
        # RISK-8 (and today's weight): the sleeve's notional. Holdings that drifted above a cap with
        # prices are never cut (only increases are clipped), but new money never goes past it.
        w = self._sleeve_cap(t.sleeve, day)
        sleeve_notional = notional([o for o in others if o.sleeve == t.sleeve])
        yield (w * eq - sleeve_notional) / price, f"by sleeve {t.sleeve} weight cap {w:.0%} (RISK-8)"
        # RISK-7: C + D together.
        if t.sleeve in SPECULATIVE_SLEEVES and "max_speculative_weight" in pf:
            spec = notional([o for o in others if o.sleeve in SPECULATIVE_SLEEVES])
            yield (pf["max_speculative_weight"] * eq - spec) / price, \
                f"by {pf['max_speculative_weight']:.0%} speculative cap on C + D (RISK-7)"

    def _sleeve_cap(self, sleeve: str, day: _Day) -> float:
        """RISK-7/RISK-8 backstop: min(today's weight, probation cap). A sleeve missing from a given
        weights dict gets 0 (nothing was allocated to it)."""
        cap = self.cfg.sleeve_weight_cap(sleeve, list(day.promoted))
        if day.weights is None:
            return cap
        return max(0.0, min(cap, _num(day.weights.get(sleeve), 0.0)))

    # --- step 4: orders -----------------------------------------------------------------------------

    def _orders(self, targets: list[Target], broker_qty: dict[str, float], prices: dict, log: list[str],
                lots: dict[str, dict[str, Lot]] | None = None, ref: dict | None = None
                ) -> tuple[list[Order], list[str]]:
        """EX-2/EX-3: net each symbol across sleeves against the broker. Sells first (priority 0); buys
        ranked by the best sleeve increasing them (turnover.buy_priority, A=1 ... D=4), then by notional,
        largest first. Returns the orders that fit max_orders_per_day and the symbols of the buys
        dropped from the end. Sells are never dropped. A symbol with no valid close today may only be
        sold, priced at its last valid close (`ref`)."""
        t_cfg = self.p["turnover"]
        rank = {s: i + 1 for i, s in enumerate(t_cfg.get("buy_priority") or ["A", "B", "C", "D"])}
        last = len(rank) + 1
        want: dict[str, float] = {}
        reasons: dict[str, list[str]] = {}
        prio: dict[str, int] = {}
        lot_exit: set[str] = set()
        for t in targets:
            want[t.symbol] = want.get(t.symbol, 0.0) + t.qty
            if t.reason and t.reason not in ("hold", "unchanged"):
                reasons.setdefault(t.symbol, []).append(f"{t.sleeve}: {t.reason}")
            held = _lot_qty(lots, t.sleeve, t.symbol)
            if t.qty > held + EPS:
                prio[t.symbol] = min(prio.get(t.symbol, last), rank.get(t.sleeve, last))
            if t.qty <= EPS < held:
                lot_exit.add(t.symbol)
        orders = []
        for sym, qty in want.items():
            have = _num(broker_qty.get(sym))
            price = prices.get(sym)
            if price is None:
                price = (ref or {}).get(sym)
                if price is None or qty >= have - EPS:
                    if abs(qty - have) > EPS:
                        log.append(f"{sym}: no valid close today, order to go from {have:g} to {qty:g} not sent")
                    continue
            o = self._order(sym, qty, have, price, "; ".join(reasons.get(sym, [])), sym in lot_exit)
            if o:
                o.priority = 0 if o.side == "sell" else prio.get(sym, last)
                orders.append(o)
        sells = [o for o in orders if o.side == "sell"]
        buys = sorted((o for o in orders if o.side == "buy"), key=lambda o: (o.priority, -o.qty * o.price))
        room = max(0, t_cfg["max_orders_per_day"] - len(sells))
        return sells + buys[:room], [o.symbol for o in buys[room:]]

    def _order(self, sym: str, want: float, have: float, price: float | None, reason: str,
               lot_exit: bool = False) -> Order | None:
        """One net order, or None. A full exit is always sent, even under the minimum notional: of the
        whole symbol, or of one sleeve's lot (`lot_exit`) when another sleeve still holds the symbol."""
        if price is None:
            return None
        diff = want - have
        if want <= EPS and have > EPS:
            diff = -have
        elif abs(diff) * price < self.p["turnover"]["min_order_notional"] and not (lot_exit and diff < 0):
            return None
        if diff < 0:
            diff = -min(-diff, max(have, 0.0))  # never sell more than held: no shorts
        qty = round(abs(diff), 6)
        if qty <= 0:
            return None
        return Order(sym, "buy" if diff > 0 else "sell", qty, price, reason)

    # --- kept for old callers -------------------------------------------------------------------

    def _rule_stop(self, sleeve: str, sym: str, bars: Bars) -> float | None:
        """strategies.rule_stop for B/C/D, or None (sleeve A, no bars, or too little history for ATR)."""
        return self._rule_stop_df(sleeve, bars.get(sym))

    def _rule_stop_df(self, sleeve: str, df: pd.DataFrame | None) -> float | None:
        if df is None or not len(df):
            return None
        try:
            return _stop_or_none(strategies.rule_stop(sleeve, df, self.p))
        except (KeyError, IndexError, ValueError, TypeError):
            return None

    def _default_stop(self, sleeve: str, sym: str, bars: Bars, price: float) -> float:
        """The rule stop (CL-14 floor). Falls back to price - k x ATR for sleeves without a rule stop."""
        stop = self._rule_stop(sleeve, sym, bars)
        if stop is not None:
            return stop
        from .indicators import atr

        k = self.p["per_trade"]["stop_atr_multiple"].get(sleeve, 3.0)
        a = float(atr(bars[sym], self.p["per_trade"]["atr_period"]).iloc[-1])
        stop = price - k * a
        max_dist = self.p["per_trade"].get("max_stop_distance_pct", {}).get(sleeve)
        if max_dist:
            stop = max(stop, price * (1 - max_dist))
        return stop


def _undo_increases(targets: list[Target], dropped: set[str], lots: dict[str, dict[str, Lot]],
                    held_stop: dict[tuple[str, str], float | None]) -> None:
    """EX-3: when a symbol's buy is dropped, its increases go back to the lot quantity and stop.
    Reductions and enforced exits in the same symbol stay."""
    for t in targets:
        base = _lot_qty(lots, t.sleeve, t.symbol)
        if t.symbol in dropped and t.qty > base + EPS:
            t.qty, t.reason = base, "order dropped by daily cap"
            t.stop = held_stop.get((t.sleeve, t.symbol), t.stop)


def untracked_symbols(broker_qty: dict[str, float], lots: dict[str, dict[str, Lot]]) -> list[str]:
    tracked = {s for held in lots.values() for s in held}
    return [s for s, q in broker_qty.items() if q > 0 and s not in tracked]


def as_frame(targets: list[Target]) -> pd.DataFrame:
    return pd.DataFrame([t.__dict__ for t in targets])
