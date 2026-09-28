"""Book O decisions as pure functions: the one monthly candidate, exits, the exit ladder, breakers, incidents.

Source: reports/Options rulebook.md. Nothing here talks to a broker or the network. Every function takes
option quotes (`OptionQuote`), open spreads (`SpreadLot`) and the policy, and returns plain data plus
plain-English reasons, so the daily run can log exactly why something did or did not happen.

Units: money is in dollars for the whole position unless a name ends in `_per_share` or `_pc`
(per contract). Policy percentages are fractions of the shared account's equity E (0.0025 = 0.25%).
One contract controls 100 shares (MULTIPLIER).
"""
from __future__ import annotations

import math
from datetime import date as _date
from datetime import timedelta

import pandas as pd

from .models import MULTIPLIER, OptionQuote, SpreadLot, is_occ, parse_occ

# Exit reason codes returned by exit_signal (priority: alert > expiry > short strike).
EXIT_ALERT = "alert"  # OPT-15: still open at DTE <= alert_dte; freeze entries, tell the owner, close now
EXIT_EXPIRY = "OPT-22 expiry exit"
EXIT_SHORT_STRIKE = "OPT-23 short-strike exit"
# OPT-22 and OPT-23 both apply (DTE <= 7 and the close is below the short strike). The expiry exit keeps its
# priority as the label, but the OPT-23 condition makes it a forced exit that starts at the natural price (OPT-15).
EXIT_EXPIRY_ITM = "OPT-22 expiry exit (OPT-23 short strike breached)"
FORCED_EXITS = {EXIT_ALERT, EXIT_SHORT_STRIKE, EXIT_EXPIRY_ITM, "OPT-26 incident", "OPT-31 drawdown halt"}

OPEN_STATUSES = ("pending_entry", "open", "pending_exit", "incident")

# Defaults used only when the policy block lacks a key (they match config/risk_policy.yaml).
DEFAULTS = {
    "underlyings": ["SPY"],
    "max_budgeted_loss_per_trade_pct": 0.0025,
    "max_open_budgeted_loss_pct": 0.010,
    "max_open_spreads": 3,
    "max_new_per_week": 1,
    "require_assignment_cover": True,
    "max_delta_notional_pct": 0.20,
    "max_short_vega_pct": 0.0005,
    "target_short_delta": [0.15, 0.25],
    "target_dte": 35,
    "entry_dte": {"first": 36, "last": 30},
    "min_dte_entry": 25,
    "exit_dte": 7,
    "alert_dte": 2,
    "forced_natural_dte": 5,
    "width_range": [2, 5],
    "leg_filter": {"min_oi": 500, "min_volume": 50, "max_spread_pct": 0.05, "max_spread_abs": 0.05,
                   "quote_after_et": "15:45"},
    "max_quoted_cost_pct": 0.20,
    "min_credit_cost_share": 0.10,
    "retry_credit_cost_share": 0.25,
    "exit_ladder": {"try1": "mid", "try2": "natural", "step_abs": 0.05, "cap": "width"},
    "entry_recheck": {"max_spx_move_pct": 0.01},
    "permission": {"bull_calm": 1.0, "bull_volatile": 0.5, "choppy": 0, "bear": 0, "panic": 0},
    "breakers": {"daily_loss_pct": 0.005, "dd_halve": 0.01, "dd_halt": 0.02},
    "demotion": {"min_n": 30, "bootstrap_upper_q": 0.90},
    "fees_per_contract": 0.0,
    "margin_tolerance_per_contract": 1.0,
}


# --- small helpers ---------------------------------------------------------------------------------


# Top-level keys of the full stock risk policy. A dict with any of these is the whole policy, never the O block.
_STOCK_POLICY_KEYS = ("account", "per_trade", "portfolio", "turnover", "data_checks", "claude_limits",
                      "measurement", "news")
# Nested default blocks that are merged key by key, so a partial override keeps the other defaults.
# `permission` is NOT merged: a regime label the owner left out must get 0 (the safe side), not a default.
_MERGED_BLOCKS = ("entry_dte", "leg_filter", "exit_ladder", "entry_recheck", "breakers", "demotion")


def ob_policy(policy: dict | None) -> dict:
    """The `options_book` block with missing keys filled from DEFAULTS.

    Accepts the full risk policy (its `options_book` block is used), the block itself, or None. A full stock
    policy without an `options_book` block gives the defaults: the stock book's own keys (its `breakers` in
    particular) never leak into O's limits.
    """
    p = policy if isinstance(policy, dict) else {}
    if "options_book" in p:
        block = p.get("options_book") or {}
    elif any(k in p for k in _STOCK_POLICY_KEYS):
        block = {}
    else:
        block = p
    out = dict(DEFAULTS)
    out.update(block if isinstance(block, dict) else {})
    for k in _MERGED_BLOCKS:
        if isinstance(block, dict) and isinstance(block.get(k), dict):
            out[k] = {**DEFAULTS[k], **block[k]}
    return out


def num(x, default: float | None = None) -> float | None:
    """A finite float or `default` (None, NaN, inf and junk all count as missing)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def to_date(d) -> _date:
    """Accept a date, datetime, pandas Timestamp or ISO string."""
    if isinstance(d, _date) and not isinstance(d, pd.Timestamp):
        return d if type(d) is _date else d.date()
    return pd.Timestamp(d).date()


def dte(expiry, today) -> int:
    """Calendar days from `today` to the contract's expiration date (rulebook Conventions)."""
    return (to_date(expiry) - to_date(today)).days


def floor_int(x: float) -> int:
    """Round down to a whole number of contracts (OPT-8: never round up). Tiny float noise is forgiven."""
    v = num(x, 0.0)
    return max(0, int(math.floor(v + 1e-9)))


def _is_open(lot: SpreadLot) -> bool:
    return getattr(lot, "status", "open") in OPEN_STATUSES


def _by_symbol(quotes) -> dict[str, OptionQuote]:
    return {q.symbol: q for q in (quotes or []) if isinstance(q, OptionQuote)}


# --- expiries (OPT-18) -----------------------------------------------------------------------------


def third_friday(year: int, month: int) -> _date:
    d = _date(year, month, 15)
    return d + timedelta(days=(4 - d.weekday()) % 7)


def is_standard_monthly(expiry, available=()) -> bool:
    """True for the third Friday of its month, or the Thursday before it when that Friday is not listed

    (a holiday moves the monthly expiry to Thursday, rulebook Conventions).
    """
    d = to_date(expiry)
    tf = third_friday(d.year, d.month)
    if d == tf:
        return True
    listed = {to_date(a) for a in available}
    return d == tf - timedelta(days=1) and tf not in listed


def monthly_expiry_candidates(quotes, date, policy: dict | None = None) -> list[str]:
    """OPT-18: standard monthly expiries whose DTE is inside the entry window (first 36 .. last 30).

    `quotes` may be OptionQuotes or plain expiry strings. The result is sorted nearest to the target DTE first.
    """
    p = ob_policy(policy)
    first, last = int(p["entry_dte"]["first"]), int(p["entry_dte"]["last"])
    exps = sorted({(q.expiry if isinstance(q, OptionQuote) else str(q)) for q in (quotes or [])})
    out = [e for e in exps if is_standard_monthly(e, exps) and last <= dte(e, date) <= first]
    return sorted(out, key=lambda e: (abs(dte(e, date) - int(p["target_dte"])), e))


# --- per-leg filter (OPT-12, OPT-27) ----------------------------------------------------------------


def _quote_time_ok(q: OptionQuote, date, after_et: str | None) -> bool:
    """Quote stamped on `date` at or after `after_et` New York time. Naive stamps are read as UTC (Alpaca)."""
    if not after_et:
        return True
    if not q.quote_time:
        return False
    try:
        ts = pd.Timestamp(q.quote_time)
    except (ValueError, TypeError):
        return False
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts
    ny = ts.tz_convert("America/New_York")
    hh, mm = (int(x) for x in str(after_et).split(":"))
    return ny.date() == to_date(date) and (ny.hour, ny.minute) >= (hh, mm)


def leg_problems(q: OptionQuote | None, date, policy: dict | None = None) -> list[str]:
    """OPT-12 per-leg filter plus the OPT-27 data guard. Empty list = the leg may be used for an entry."""
    if q is None:
        return ["quote missing"]
    lf = {**DEFAULTS["leg_filter"], **(ob_policy(policy).get("leg_filter") or {})}
    out = []
    if not q.tradable:
        out.append("not tradable")
    bid, ask = num(q.bid), num(q.ask)
    if bid is None or bid <= 0:
        out.append("bid missing or zero")
    mid = q.mid if bid is not None and ask is not None else None
    if ask is None or mid is None:
        out.append("ask missing or crossed")
    elif ask - bid > max(float(lf["max_spread_abs"]), float(lf["max_spread_pct"]) * mid) + 1e-9:
        out.append(f"leg spread {ask - bid:.2f} too wide")
    oi = num(q.open_interest)
    if oi is None or oi < float(lf["min_oi"]):
        out.append(f"open interest {q.open_interest} < {lf['min_oi']}")
    vol = num(q.volume)
    if vol is None or vol < float(lf["min_volume"]):
        out.append(f"volume {q.volume} < {lf['min_volume']}")
    if not _quote_time_ok(q, date, lf.get("quote_after_et")):
        out.append(f"quote time {q.quote_time} not after {lf.get('quote_after_et')} ET today")
    for g in ("delta", "iv", "vega"):
        if num(getattr(q, g)) is None:
            out.append(f"{g} missing (OPT-27)")
    return out


# --- spread arithmetic (rulebook Conventions) -------------------------------------------------------


def spread_prices(short: OptionQuote, long: OptionQuote) -> dict | None:
    """Mid credit, natural credit and quoted cost of a credit spread, per share. None if a quote is unusable."""
    if short.mid is None or long.mid is None:
        return None
    return {
        "mid_credit": short.mid - long.mid,
        "natural_credit": short.bid - long.ask,
        "quoted_cost": (short.ask - short.bid) + (long.ask - long.bid),
    }


def per_contract_risk(width: float, credit: float, quoted_cost: float, fees_per_contract: float = 0.0) -> dict:
    """OPT-7/OPT-8: MaxLoss and budgeted loss for ONE contract, from strikes and a credit per share.

    MaxLoss = (width - credit) x 100. Budgeted = MaxLoss + quoted cost x 100 + fees (2 legs x 2 sides).
    """
    max_loss = (width - credit) * MULTIPLIER
    budget = max_loss + quoted_cost * MULTIPLIER + 4 * max(0.0, fees_per_contract)
    return {"max_loss_pc": max_loss, "budgeted_loss_pc": budget}


def lot_net_greeks(lot: SpreadLot, quotes_by_symbol: dict) -> dict | None:
    """Position delta and vega per share of one open spread (long leg minus short leg). None if a greek is missing."""
    s, lg = quotes_by_symbol.get(lot.short_leg.symbol), quotes_by_symbol.get(lot.long_leg.symbol)
    if s is None or lg is None:
        return None
    sd, ld, sv, lv = num(s.delta), num(lg.delta), num(s.vega), num(lg.vega)
    if None in (sd, ld, sv, lv):
        return None
    return {"delta": ld - sd, "vega": lv - sv}


# --- permission and sizing (OPT-19, OPT-8) ----------------------------------------------------------


def permission(regime_label: str | None, policy: dict | None = None) -> float:
    """OPT-19: regime multiplier. Unknown or missing labels get 0 (the safe side)."""
    perm = ob_policy(policy)["permission"] or {}
    return max(0.0, num(perm.get(str(regime_label)), 0.0))


def size_contracts(cap_dollars: float, budgeted_loss_pc: float, perm: float = 1.0) -> int:
    """OPT-8 then OPT-19: floor(cap / budgeted loss per contract), then floor(x perm). 0 means no trade."""
    b = num(budgeted_loss_pc)
    if b is None or b <= 0:
        return 0
    return floor_int(floor_int(num(cap_dollars, 0.0) / b) * max(0.0, num(perm, 0.0)))


# --- book caps (OPT-9, OPT-10) ----------------------------------------------------------------------


def open_fraction(lot: SpreadLot) -> float:
    """Share of the lot's entry contracts still at risk: open contracts plus any broken by an assignment.

    MaxLoss and the budgeted loss keep their entry values (R uses them), so committed amounts are taken pro
    rata with this fraction after a partial close. Lots without an entry count (built by hand) count in full.
    """
    tags = getattr(lot, "tags", None) or {}
    n0 = num(tags.get("entry_contracts"))
    if not n0 or n0 <= 0:
        return 1.0
    broken = num((tags.get("broken") or {}).get("contracts"), 0.0) or 0.0
    return min(1.0, max(0.0, (num(lot.contracts, 0.0) + broken) / n0))


def open_budgeted_loss(lots) -> float:
    """OPT-9: budgeted loss still committed by the open lots (pro rata after partial closes)."""
    return sum(num(l.budgeted_loss, 0.0) * open_fraction(l) for l in lots if _is_open(l))


def assignment_need(lots) -> float:
    """OPT-9: cash needed if every open short put were assigned at once (short strike x 100 x qty)."""
    return sum(num(l.short_leg.strike, 0.0) * MULTIPLIER * int(l.short_leg.qty) for l in lots if _is_open(l))


def _cap_book_budget(n, budget_pc, lots, equity, p, notes) -> int:
    room = float(p["max_open_budgeted_loss_pct"]) * equity - open_budgeted_loss(lots)
    k = floor_int(room / budget_pc) if room > 0 else 0
    if k < n:
        notes.append(f"OPT-9 open budgeted loss cap: {n} -> {k} contracts")
    return min(n, k)


def _cap_cover(n, strike, lots, cash, p, notes) -> int:
    if not p.get("require_assignment_cover", True):
        return n
    c = num(cash)
    if c is None:
        notes.append("OPT-9 assignment cover: uncommitted cash unknown, no entry")
        return 0
    room = c - assignment_need(lots)
    k = floor_int(room / (strike * MULTIPLIER)) if room > 0 else 0
    if k < n:
        notes.append(f"OPT-9 assignment cover: {n} -> {k} contracts (cash {c:,.0f})")
    return min(n, k)


def _cap_greeks(n, cand_greeks, lots, qmap, spot, equity, p, notes) -> int:
    """OPT-10: |delta notional| and short vega of the whole book, including the new spread."""
    d_open = v_open = 0.0
    for lot in (l for l in lots if _is_open(l)):
        g = lot_net_greeks(lot, qmap)
        if g is None:
            notes.append(f"OPT-10/OPT-27: greeks missing for open lot {lot.lot_id}, no entry")
            return 0
        d_open += g["delta"] * MULTIPLIER * lot.contracts
        v_open += g["vega"] * MULTIPLIER * lot.contracts
    k = n
    while k > 0:
        delta_notional = abs((d_open + cand_greeks["delta"] * MULTIPLIER * k) * spot)
        short_vega = max(0.0, -(v_open + cand_greeks["vega"] * MULTIPLIER * k))
        if delta_notional <= float(p["max_delta_notional_pct"]) * equity + 1e-9 and \
                short_vega <= float(p["max_short_vega_pct"]) * equity + 1e-9:
            break
        k -= 1
    if k < n:
        notes.append(f"OPT-10 greek caps: {n} -> {k} contracts")
    return k


# --- the candidate (OPT-18 with OPT-5, 8, 9, 10, 12, 13, 19, 24) ------------------------------------


def _gate_reasons(date, p, regime_label, lots, week_count, extra_blocks, closed=()) -> list[str]:
    """Book-level reasons that stop any new entry today (checked before looking at the chain)."""
    out = [str(b) for b in (extra_blocks or [])]
    if permission(regime_label, p) <= 0:
        out.append(f"OPT-19: regime {regime_label!r} has permission 0")
    open_lots = [l for l in lots if _is_open(l)]
    if len(open_lots) >= int(p["max_open_spreads"]):
        out.append(f"OPT-9: {len(open_lots)} open spreads (max {p['max_open_spreads']})")
    wk = new_this_week(lots, date, closed) if week_count is None else int(num(week_count, 0) or 0)
    if wk >= int(p["max_new_per_week"]):
        out.append(f"OPT-9: {wk} new spread(s) this week (max {p['max_new_per_week']})")
    for lot in open_lots:
        if dte(lot.expiry, date) <= int(p["alert_dte"]):
            out.append(f"OPT-15: lot {lot.lot_id} still open at DTE {dte(lot.expiry, date)}, entries frozen")
    return out


def new_this_week(lots, date, closed=()) -> int:
    """OPT-9: spreads opened in the ISO week of `date`: the lots given (any status) plus closed-spread records.

    A spread that appears both as a lot and as a closed record (same lot_id) counts once.
    """
    wk = pd.Timestamp(to_date(date)).isocalendar()[:2]
    dates: dict = {}
    for l in lots or []:
        dates[getattr(l, "lot_id", None) or id(l)] = l.entry_date
    for i, r in enumerate(closed or []):
        dates.setdefault(r.get("lot_id") or f"closed-{i}", r.get("entry_date"))
    return sum(1 for d in dates.values() if d and pd.Timestamp(d).isocalendar()[:2] == wk)


def cycle_blocked(expiry: str, lots, closed=(), underlying: str | None = None) -> str | None:
    """OPT-18 one spread per monthly cycle (open or closed, whatever its P&L); OPT-24 names a loss exit.

    `underlying` limits the check to one underlying (shadow variants on other underlyings keep their own cycle).
    """
    def same(und) -> bool:
        return underlying is None or und is None or und == underlying

    recs = [r for r in closed or [] if r.get("expiry") == expiry and same(r.get("underlying"))]
    if any(num(r.get("pnl"), 0.0) < 0 for r in recs):
        return f"OPT-24: loss exit already taken in expiry {expiry}"
    if recs:
        return f"OPT-18: a spread was already opened (and closed) for the {expiry} cycle"
    for lot in lots:
        if lot.expiry == expiry and same(getattr(lot, "underlying", None)):
            if lot.status == "closed" and num(lot.realized_pnl, 0.0) - num(lot.costs, 0.0) < 0:
                return f"OPT-24: loss exit already taken in expiry {expiry}"
            return f"OPT-18: a spread was already opened for the {expiry} cycle"
    return None


def pick_short(puts, date, p) -> tuple[OptionQuote | None, list[str]]:
    """OPT-18: the short put with |delta| inside the band and nearest the band's middle (0.20)."""
    lo, hi = (float(x) for x in p["target_short_delta"])
    target = (lo + hi) / 2
    band = [q for q in puts if num(q.delta) is not None and lo - 1e-9 <= abs(q.delta) <= hi + 1e-9]
    if not band:
        return None, [f"OPT-18: no put with |delta| in {lo}-{hi}"]
    usable = [q for q in band if not leg_problems(q, date, p)]
    if not usable:
        why = "; ".join(f"{q.symbol}: {', '.join(leg_problems(q, date, p))}" for q in band[:3])
        return None, [f"OPT-12: no short put in the delta band passes the leg filter ({why})"]
    # nearest 0.20; ties go to the smaller |delta| (further out of the money, lower risk)
    return min(usable, key=lambda q: (round(abs(abs(q.delta) - target), 6), abs(q.delta))), []


def pick_width(short, puts, date, p, cap) -> tuple[dict | None, list[str]]:
    """OPT-18: the widest $1-step width in the range whose budgeted loss fits OPT-8 for >= 1 contract."""
    by_strike = {round(q.strike, 2): q for q in puts}
    lo, hi = (int(x) for x in p["width_range"])
    notes = []
    for w in range(hi, lo - 1, -1):
        long = by_strike.get(round(short.strike - w, 2))
        probs = leg_problems(long, date, p)
        if probs:
            notes.append(f"width {w}: long leg {', '.join(probs)}")
            continue
        px = spread_prices(short, long)
        if px is None or px["mid_credit"] <= 0:
            notes.append(f"width {w}: no positive mid credit")
            continue
        risk = per_contract_risk(w, px["mid_credit"], px["quoted_cost"], float(p["fees_per_contract"]))
        if size_contracts(cap, risk["budgeted_loss_pc"]) >= 1:
            return {"width": float(w), "long": long, **px, **risk}, notes
        notes.append(f"width {w}: budgeted loss {risk['budgeted_loss_pc']:.0f} > cap {cap:.0f}")
    return None, [f"OPT-8/OPT-18: no width {lo}-{hi} fits the per-trade cap ({'; '.join(notes)})"]


def _leg_view(q: OptionQuote) -> dict:
    keep = ("symbol", "strike", "bid", "ask", "delta", "iv", "vega", "open_interest", "volume", "quote_time", "feed")
    return {**{k: getattr(q, k) for k in keep}, "mid": q.mid}


def build_candidate(quotes, spot, date, policy, regime_label, open_lots, equity, uncommitted_cash, week_count,
                    *, underlying: str | None = None, cap_mult: float = 1.0, blocks=(), closed=()):
    """OPT-18: the single monthly bull put spread for today, or None with the reasons.

    Returns (candidate dict | None, reasons list). Order of checks: book gates (OPT-19 regime, OPT-9 counts,
    OPT-15 freeze, any `blocks` such as breakers or incidents), the expiry window and cycle (OPT-18, OPT-24),
    the short put (OPT-18 delta, OPT-12 filter), the width (OPT-8 fit), OPT-13 cost filter, then sizing
    (OPT-8, OPT-19) and the caps (OPT-9 budget and assignment cover, OPT-10 greeks).
    `cap_mult` is OPT-31's multiplier (0.5 after a 1% drawdown). `closed` holds closed-spread records: they
    count toward the weekly cap when `week_count` is None, and any record in the chosen expiry blocks a second
    spread in that cycle (OPT-18; OPT-24 when it was a loss).
    Non-SPY underlyings are allowed only as shadow variants (OPT-4/OPT-39); the candidate says so.
    """
    p = ob_policy(policy)
    lots = [l for l in (open_lots or []) if isinstance(l, SpreadLot)]
    und = underlying or p["underlyings"][0]
    spot_v, eq = num(spot), num(equity)
    if spot_v is None or spot_v <= 0:
        return None, ["no usable underlying price"]
    if eq is None or eq <= 0:
        return None, ["equity is zero or unknown"]
    reasons = _gate_reasons(date, p, regime_label, lots, week_count, blocks, closed)
    if reasons:
        return None, reasons
    puts = [q for q in (quotes or []) if isinstance(q, OptionQuote) and q.underlying == und and q.type == "put"]
    exps = monthly_expiry_candidates(puts, date, p)
    if not exps:
        return None, [f"OPT-18: no standard monthly {und} expiry with DTE in the entry window"]
    expiry = exps[0]
    why = cycle_blocked(expiry, lots, closed, und)
    if why:
        return None, [why]
    if dte(expiry, date) < int(p["min_dte_entry"]):
        return None, [f"OPT-5: DTE {dte(expiry, date)} below {p['min_dte_entry']}"]
    chain = [q for q in puts if q.expiry == expiry]
    short, why = pick_short(chain, date, p)
    if short is None:
        return None, why
    cap = float(p["max_budgeted_loss_per_trade_pct"]) * eq * max(0.0, num(cap_mult, 0.0))
    pick, why = pick_width(short, chain, date, p, cap)
    if pick is None:
        return None, why
    return _finish(pick, short, und, expiry, spot_v, date, p, regime_label, lots, eq, uncommitted_cash, cap,
                   _by_symbol(quotes))


def _finish(pick, short, und, expiry, spot, date, p, regime_label, lots, equity, cash, cap, qmap):
    """OPT-13 filter, then sizing and caps; builds the candidate dict."""
    cost_share = pick["quoted_cost"] / pick["mid_credit"]
    if cost_share > float(p["max_quoted_cost_pct"]) + 1e-9:
        return None, [f"OPT-13: quoted cost {pick['quoted_cost']:.2f} is {cost_share:.0%} of the mid credit "
                      f"{pick['mid_credit']:.2f} (max {float(p['max_quoted_cost_pct']):.0%}); no trade"]
    perm = permission(regime_label, p)
    notes: list[str] = []
    n = size_contracts(cap, pick["budgeted_loss_pc"], perm)
    if n <= 0:
        return None, [f"OPT-8/OPT-19: {floor_int(cap / pick['budgeted_loss_pc'])} contract(s) x permission "
                      f"{perm} rounds down to 0; no trade"]
    long = pick["long"]
    greeks = {"delta": long.delta - short.delta, "vega": long.vega - short.vega}
    n = _cap_book_budget(n, pick["budgeted_loss_pc"], lots, equity, p, notes)
    n = _cap_cover(n, short.strike, lots, cash, p, notes) if n else n
    n = _cap_greeks(n, greeks, lots, qmap, spot, equity, p, notes) if n else n
    if n <= 0:
        return None, notes + ["caps leave 0 contracts; no trade"]
    min_credit = round(pick["mid_credit"] - float(p["min_credit_cost_share"]) * pick["quoted_cost"], 2)
    if min_credit <= 0:
        return None, notes + ["OPT-14: minimum credit is not positive; no trade"]
    cand = {
        "underlying": und, "expiry": expiry, "type": "put", "date": to_date(date).isoformat(),
        "dte": dte(expiry, date), "spot": spot, "regime": regime_label, "permission": perm,
        "short": _leg_view(short), "long": _leg_view(long), "width": pick["width"], "contracts": n,
        "mid_credit": pick["mid_credit"], "natural_credit": pick["natural_credit"],
        "quoted_cost": pick["quoted_cost"], "cost_share": cost_share,
        "max_loss_per_contract": pick["max_loss_pc"], "budgeted_loss_per_contract": pick["budgeted_loss_pc"],
        "max_loss": pick["max_loss_pc"] * n, "budgeted_loss": pick["budgeted_loss_pc"] * n,
        "per_trade_cap": cap, "min_credit": min_credit, "limit_price": -min_credit,
        "retry_limit_price": -retry_credit(pick, p),
        "net_delta_per_share": greeks["delta"], "net_vega_per_share": greeks["vega"],
        "delta_notional": greeks["delta"] * MULTIPLIER * n * spot,
        "feed": short.feed, "shadow_only": und not in p["underlyings"], "notes": notes,
    }
    return cand, notes


def retry_credit(pick: dict, policy: dict | None = None) -> float:
    """OPT-14: the one re-price after an unfilled entry: mid credit - 25% of the quoted cost (never below 0.01)."""
    p = ob_policy(policy)
    return max(0.01, round(pick["mid_credit"] - float(p["retry_credit_cost_share"]) * pick["quoted_cost"], 2))


def entry_recheck(candidate: dict, spot_now, policy: dict | None = None) -> str | None:
    """OPT-17: cancel the entry if the underlying moved more than 1% from the decision close."""
    p = ob_policy(policy)
    base, now = num(candidate.get("spot")), num(spot_now)
    if base is None or now is None or base <= 0:
        return "OPT-17: underlying price missing, entry cancelled"
    move = abs(now / base - 1)
    limit = float((p.get("entry_recheck") or {}).get("max_spx_move_pct", 0.01))
    if move > limit + 1e-12:
        return f"OPT-17: underlying moved {move:.2%} since the decision close (max {limit:.0%}), entry cancelled"
    return None


# --- exits (OPT-22, OPT-23, OPT-15 alert) -----------------------------------------------------------


def exit_signal(lot: SpreadLot, quotes, spot, date, policy: dict | None = None) -> str | None:
    """Why this open spread must be closed today, or None. Exits never wait for option data: they use DTE

    and the underlying close only (`quotes` is accepted for symmetry and ignored).
    EXIT_ALERT at DTE <= alert_dte (OPT-15: also freezes entries), EXIT_EXPIRY at DTE <= exit_dte (OPT-22),
    EXIT_SHORT_STRIKE when the close is below the short strike (OPT-23). When both OPT-22 and OPT-23 apply the
    reason is EXIT_EXPIRY_ITM, which is forced (starts at the natural price, OPT-15) like any OPT-23 exit.
    A missing close skips only OPT-23.
    """
    if not _is_open(lot):
        return None
    p = ob_policy(policy)
    days = dte(lot.expiry, date)
    s = num(spot)
    below = s is not None and s < float(lot.short_leg.strike)
    if days <= int(p["alert_dte"]):
        return EXIT_ALERT
    if days <= int(p["exit_dte"]):
        return EXIT_EXPIRY_ITM if below else EXIT_EXPIRY
    if below:
        return EXIT_SHORT_STRIKE
    return None


def entry_freeze_alerts(lots, date, policy: dict | None = None) -> list[str]:
    """OPT-15: lots still open at DTE <= alert_dte. Any entry here freezes entries and alerts the owner."""
    p = ob_policy(policy)
    return [f"OPT-15 alert: lot {l.lot_id} open at DTE {dte(l.expiry, date)}" for l in lots
            if _is_open(l) and dte(l.expiry, date) <= int(p["alert_dte"])]


def is_forced(reason: str | None, days: int | None = None, policy: dict | None = None) -> bool:
    """OPT-15: forced exits (OPT-23, OPT-31, OPT-26, alerts, and any exit at DTE <= 5) start at the natural price."""
    if reason in FORCED_EXITS:
        return True
    return days is not None and days <= int(ob_policy(policy)["forced_natural_dte"])


def _quote_on_date(q: OptionQuote, date) -> bool:
    """The quote is stamped on `date` (New York time). Missing or unreadable stamps count as stale."""
    if not q.quote_time:
        return False
    try:
        ts = pd.Timestamp(q.quote_time)
    except (ValueError, TypeError):
        return False
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts
    return ts.tz_convert("America/New_York").date() == to_date(date)


def _ceil_cent(x: float) -> float:
    return math.ceil(round(x * 100, 6)) / 100


def ladder_detail(lot: SpreadLot, quotes, try_n: int, policy: dict | None = None, *, forced: bool = False,
                  date=None) -> dict:
    """OPT-15 exit ladder, one try per run. Returns {limit_price, basis, capped}; limit_price is the DEBIT per share.

    Normal: try 1 mid, try 2 natural, then natural + $0.05 per further try. Forced (or DTE <= 5 when `date`
    is given): try 1 natural, then + $0.05 per try. Missing or unusable quotes price at the width cap, and so do
    stale ones: when `date` (the run date) is given, a leg quote not stamped on that New York date is stale
    (rulebook section (e), OPT-15). Callers should always pass `date`; without it freshness cannot be checked.
    Never above the width (the cap) and never below $0.01 (a close is a debit, OPT-14 sign).
    """
    p = ob_policy(policy)
    ladder = {**DEFAULTS["exit_ladder"], **(p.get("exit_ladder") or {})}
    width = float(lot.width)
    if date is not None and is_forced(None, dte(lot.expiry, date), p):
        forced = True
    qmap = _by_symbol(quotes)
    s, lg = qmap.get(lot.short_leg.symbol), qmap.get(lot.long_leg.symbol)
    if s is None or lg is None or s.mid is None or lg.mid is None:
        return {"limit_price": round(width, 2), "basis": "cap (quote missing)", "capped": True}
    if date is not None and not (_quote_on_date(s, date) and _quote_on_date(lg, date)):
        return {"limit_price": round(width, 2), "basis": "cap (quote stale)", "capped": True}
    n = max(1, int(num(try_n, 1) or 1))
    natural = s.ask - lg.bid
    if not forced and n == 1:
        raw, basis = s.mid - lg.mid, "mid"
    else:
        steps = (n - 2) if not forced else (n - 1)
        raw = natural + float(ladder["step_abs"]) * max(0, steps)
        basis = "natural" if steps <= 0 else f"natural + {float(ladder['step_abs']) * steps:.2f}"
    price = max(0.01, _ceil_cent(raw))
    if price >= width:
        return {"limit_price": round(width, 2), "basis": basis + " (capped at width)", "capped": True}
    return {"limit_price": price, "basis": basis, "capped": False}


def ladder_price(lot: SpreadLot, quotes, try_n: int, policy: dict | None = None, *, forced: bool = False,
                 date=None) -> float:
    """OPT-15: the debit limit per share for this exit try (see ladder_detail)."""
    return ladder_detail(lot, quotes, try_n, policy, forced=forced, date=date)["limit_price"]


# --- breakers (OPT-30, OPT-31, OPT-32) --------------------------------------------------------------


def daily_loss_breaker(day_pnl, equity, policy: dict | None = None) -> str | None:
    """OPT-30: O's mark-to-market loss today >= 0.5% of E -> no new entries next session (exits still run)."""
    p, pnl, eq = ob_policy(policy), num(day_pnl), num(equity)
    if pnl is None or eq is None or eq <= 0:
        return None
    lim = float(p["breakers"]["daily_loss_pct"]) * eq
    if -pnl >= lim - 1e-9:
        return f"OPT-30: O lost {-pnl:,.2f} today (limit {lim:,.2f}); no new entries next session"
    return None


def drawdown_state(o_pnl, o_peak, equity, policy: dict | None = None) -> dict:
    """OPT-31: drawdown from O's own high-water mark (cumulative P&L), in dollars against E.

    >= 1% of E halves OPT-8's cap (cap_mult 0.5); >= 2% closes every spread and halts O until the owner resets.
    Unknown inputs give the safe answer: no new entries (cap_mult 0) but no forced close.
    """
    p, pnl, peak, eq = ob_policy(policy), num(o_pnl), num(o_peak), num(equity)
    if pnl is None or eq is None or eq <= 0:
        return {"cap_mult": 0.0, "halt": False, "close_all": False, "drawdown": None,
                "reason": "OPT-31: O P&L or equity unknown; no new entries"}
    peak = max(pnl, peak if peak is not None else 0.0, 0.0)
    dd = peak - pnl
    b = p["breakers"]
    if dd >= float(b["dd_halt"]) * eq - 1e-9:
        return {"cap_mult": 0.0, "halt": True, "close_all": True, "drawdown": dd,
                "reason": f"OPT-31: drawdown {dd:,.2f} >= {float(b['dd_halt']):.0%} of E; close all and halt"}
    if dd >= float(b["dd_halve"]) * eq - 1e-9:
        return {"cap_mult": 0.5, "halt": False, "close_all": False, "drawdown": dd,
                "reason": f"OPT-31: drawdown {dd:,.2f} >= {float(b['dd_halve']):.0%} of E; per-trade cap halved"}
    return {"cap_mult": 1.0, "halt": False, "close_all": False, "drawdown": dd, "reason": None}


def _bootstrap_upper(rs, q: float, n_boot: int = 2000, seed: int = 0) -> float | None:
    try:
        from ..metrics import bootstrap_upper
        return bootstrap_upper(rs, q, n_boot, seed)
    except ImportError:  # pragma: no cover - metrics is part of the package
        import numpy as np
        a = np.asarray([x for x in rs if num(x) is not None], dtype=float)
        if len(a) == 0:
            return None
        rng = np.random.default_rng(seed)
        return float(np.quantile(a[rng.integers(0, len(a), size=(n_boot, len(a)))].mean(axis=1), q))


def demotion_check(closed_rs, policy: dict | None = None) -> str | None:
    """OPT-32 (M-11): n >= 30 closed spreads and a one-sided 90% bootstrap upper bound of mean R_net < 0

    -> stop new entries pending owner review.
    """
    p = ob_policy(policy)
    dem = {**DEFAULTS["demotion"], **(p.get("demotion") or {})}
    rs = [float(r) for r in (closed_rs or []) if num(r) is not None]
    if len(rs) < int(dem["min_n"]):
        return None
    ub = _bootstrap_upper(rs, float(dem["bootstrap_upper_q"]))
    if ub is not None and ub < 0:
        return f"OPT-32: {len(rs)} closed spreads, bootstrap upper bound of mean R_net {ub:.3f} < 0; entries stop"
    return None


def breaker_status(*, day_pnl, o_pnl, o_peak, equity, closed_rs=(), halted: bool = False,
                   policy: dict | None = None) -> dict:
    """OPT-30/31/32 together: {no_new_entries, cap_mult, close_all, halt, reasons}. Exits are never blocked."""
    reasons = []
    dd = drawdown_state(o_pnl, o_peak, equity, policy)
    if dd["reason"]:
        reasons.append(dd["reason"])
    for r in (daily_loss_breaker(day_pnl, equity, policy), demotion_check(closed_rs, policy)):
        if r:
            reasons.append(r)
    if halted:
        reasons.append("OPT-31: O is halted until the owner resets it")
    halt = bool(halted or dd["halt"])
    no_new = halt or dd["cap_mult"] <= 0 or any(r.startswith(("OPT-30", "OPT-32")) for r in reasons)
    return {"no_new_entries": no_new, "cap_mult": 0.0 if halt else dd["cap_mult"], "close_all": dd["close_all"],
            "halt": halt, "reasons": reasons}


# --- incidents and reconciliation (OPT-26, OPT-27) --------------------------------------------------


def _pos_qty(pos: dict) -> float:
    q = num(pos.get("qty"), 0.0)
    side = str(pos.get("side", "")).lower()
    return -abs(q) if side in ("short", "positionside.short") else q


def expected_option_positions(lots) -> dict[str, int]:
    """Signed contracts per OCC symbol that O's open lots should hold (long +, short -)."""
    out: dict[str, int] = {}
    for lot in (l for l in lots if _is_open(l) and l.status != "pending_entry"):
        for leg, sign in ((lot.long_leg, 1), (lot.short_leg, -1)):
            if int(leg.qty):
                out[leg.symbol] = out.get(leg.symbol, 0) + sign * int(leg.qty)
    return out


def orphan_legs(option_qty: dict[str, float]) -> list[str]:
    """OPT-3/OPT-26: short contracts not matched 1:1 by a long of the same underlying, expiry and type,

    further out of the money; and long contracts left without a short partner.
    """
    groups: dict[tuple, list] = {}
    for sym, q in option_qty.items():
        if q:
            o = parse_occ(sym)
            groups.setdefault((o["underlying"], o["expiry"], o["type"]), []).append((o["strike"], q, sym))
    out = []
    for (_, _, typ), legs in groups.items():
        shorts = sum(-q for _, q, _ in legs if q < 0)
        longs = sum(q for _, q, _ in legs if q > 0)
        if shorts > longs:
            out.append(f"naked short: {', '.join(s for _, q, s in legs if q < 0)} ({shorts:g} short vs {longs:g} long)")
        elif longs > shorts:
            out.append(f"orphan long: {', '.join(s for _, q, s in legs if q > 0)} ({longs:g} long vs {shorts:g} short)")
        else:
            out.extend(_protection_gaps(legs, typ))
    return out


def _protection_gaps(legs, typ) -> list[str]:
    """Each short must be covered by a long further out of the money (lower strike for puts, higher for calls)."""
    shorts = sorted([(k, -q) for k, q, _ in legs if q < 0], reverse=(typ == "put"))
    longs = sorted([(k, q) for k, q, _ in legs if q > 0], reverse=(typ == "put"))
    for (sk, sq), (lk, lq) in zip(shorts, longs):
        if (typ == "put" and lk > sk) or (typ == "call" and lk < sk):
            return [f"short {typ} {sk} is not protected by a further out-of-the-money long"]
    return []


MARGIN_SHARED_NOTE = ("OPT-27 exact margin match skipped: the shared account holds the other books' stock, whose "
                      "requirement is in Alpaca's account-wide figure; only 'at least the spread margin' is checked")


def margin_problem(maintenance_margin, lots, policy: dict | None = None, *, has_stock: bool = False) -> str | None:
    """OPT-27: Alpaca's maintenance margin must equal width x 100 x contracts within $1 per contract.

    Alpaca reports ONE maintenance margin for the whole account. When the shared account also holds stock (the
    rules book's ETFs, owner decision 6), that figure includes the stock's requirement, so exact equality cannot be
    checked: `has_stock` keeps only the lower bound (the spread requirement must at least be there)."""
    open_lots = [l for l in lots if _is_open(l) and l.status != "pending_entry"]
    expected = sum(float(l.width) * MULTIPLIER * int(l.contracts) for l in open_lots)
    n = sum(int(l.contracts) for l in open_lots)
    m = num(maintenance_margin)
    if m is None:
        return "OPT-27: maintenance margin unknown" if n else None
    tol = float(ob_policy(policy)["margin_tolerance_per_contract"]) * max(n, 1)
    if has_stock:
        if m < expected - tol - 1e-9:
            return f"OPT-27: maintenance margin {m:,.2f} below width x 100 x contracts {expected:,.2f}"
        return None
    if abs(m - expected) > tol + 1e-9:
        return f"OPT-27: maintenance margin {m:,.2f} differs from width x 100 x contracts {expected:,.2f}"
    return None


def detect_incidents(positions, lots, *, other_books_stock: dict | None = None, o_stock: dict | None = None,
                     maintenance_margin=None, check_margin: bool = False, policy: dict | None = None) -> dict:
    """OPT-26 incident detector and OPT-27 reconciliation guard, from the broker's positions.

    positions: [{symbol, qty, side?}] for the whole shared account. Stock is fine only when the other books'
    ledgers own it (`other_books_stock`); anything else (O's assigned stock `o_stock`, or unowned stock) is an
    incident. Any option leg without its partner is an incident. A mismatch with O's ledger or margin blocks entries.
    Returns {freeze, incidents, mismatches, stock_excess, option_qty}.
    """
    other = {k: num(v, 0.0) for k, v in (other_books_stock or {}).items()}
    opt_qty: dict[str, float] = {}
    stock_excess: dict[str, float] = {}
    has_stock = False
    for pos in positions or []:
        sym, q = str(pos.get("symbol", "")), _pos_qty(pos)
        if is_occ(sym):
            opt_qty[sym] = opt_qty.get(sym, 0.0) + q
        elif q:
            has_stock = True
            ex = q - other.get(sym, 0.0)
            if abs(ex) > 1e-9:
                stock_excess[sym] = stock_excess.get(sym, 0.0) + ex
    incidents = [f"OPT-26: {sym} stock {q:+g} not owned by the rules or Claude books"
                 for sym, q in stock_excess.items()]
    incidents += [f"OPT-26: {x}" for x in orphan_legs(opt_qty)]
    mismatches = _ledger_mismatches(opt_qty, lots, stock_excess, o_stock)
    notes: list[str] = []
    if check_margin:
        m = margin_problem(maintenance_margin, lots, policy, has_stock=has_stock)
        if m:
            mismatches.append(m)
        elif has_stock:
            notes.append(MARGIN_SHARED_NOTE)
    return {"freeze": bool(incidents or mismatches), "incidents": incidents, "mismatches": mismatches,
            "notes": notes,
            "stock_excess": stock_excess, "option_qty": opt_qty,
            "o_stock": {k: num(v, 0.0) for k, v in (o_stock or {}).items()}}


def _ledger_mismatches(opt_qty, lots, stock_excess, o_stock) -> list[str]:
    exp = expected_option_positions(lots)
    out = [f"OPT-27: {s} broker {opt_qty.get(s, 0):+g} vs ledger {exp.get(s, 0):+g}"
           for s in sorted(set(exp) | set(opt_qty)) if abs(opt_qty.get(s, 0) - exp.get(s, 0)) > 1e-9]
    for sym, q in (o_stock or {}).items():
        if abs(num(q, 0.0) - stock_excess.get(sym, 0.0)) > 1e-9:
            out.append(f"OPT-27: {sym} O stock ledger {q:+g} vs broker excess {stock_excess.get(sym, 0.0):+g}")
    return out


def cleanup_plan(incident: dict, lots, date, policy: dict | None = None, *, o_stock: dict | None = None) -> list[dict]:
    """OPT-26 clean-up order after an assignment: (1) sell (or cover) O's stock first with a marketable limit;

    (2) only once the stock is flat, close the orphan long put. The reverse order would leave unhedged stock.
    Only stock in O's own ledger (`o_stock`, or the incident's `o_stock`) is ever traded (non-negotiable 5):
    any other unowned stock gets an `owner_review_stock` step with no order. Long-put steps wait while any
    unexplained stock of their underlying is held (it may be an assignment O's ledger has not booked yet).
    Returns ordered steps [{step, action, symbol, qty, urgent}]. An orphan long put at DTE <= alert_dte is
    marked urgent (never let it reach expiry in the money).
    """
    p = ob_policy(policy)
    own = {k: num(v, 0.0) or 0.0 for k, v in ((incident.get("o_stock") if o_stock is None else o_stock)
                                             or {}).items()}
    steps, held = [], set()
    for sym, q in (incident.get("stock_excess") or {}).items():
        q = num(q, 0.0) or 0.0
        if abs(q) <= 1e-9:
            continue
        held.add(sym)
        mine = own.get(sym, 0.0)
        sell = math.copysign(min(abs(q), abs(mine)), q) if mine * q > 0 else 0.0
        if abs(sell) > 1e-9:
            steps.append({"step": len(steps) + 1, "action": "sell_stock" if sell > 0 else "buy_to_cover_stock",
                          "symbol": sym, "qty": abs(sell), "urgent": True})
        rest = q - sell
        if abs(rest) > 1e-9:
            steps.append({"step": len(steps) + 1, "action": "owner_review_stock", "symbol": sym, "qty": abs(rest),
                          "urgent": True, "note": "stock not in O's ledger: O never trades it; owner decides"})
    for sym, q in (incident.get("option_qty") or {}).items():
        if q <= 0 or not _is_orphan_long(sym, incident["option_qty"]):
            continue
        days = dte(parse_occ(sym)["expiry"], date)
        flat = parse_occ(sym)["underlying"] not in held
        steps.append({"step": len(steps) + 1, "action": "sell_to_close_long" if flat else "wait_stock_flat",
                      "symbol": sym, "qty": q, "urgent": days <= int(p["alert_dte"])})
    return steps


def _group(sym: str) -> tuple:
    o = parse_occ(sym)
    return o["underlying"], o["expiry"], o["type"]


def _is_orphan_long(sym: str, opt_qty: dict) -> bool:
    """More long than short contracts in this leg's underlying/expiry/type group."""
    same = [q for s, q in opt_qty.items() if _group(s) == _group(sym)]
    return sum(q for q in same if q > 0) > sum(-q for q in same if q < 0)
