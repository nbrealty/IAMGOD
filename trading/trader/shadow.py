"""Records that are scored but never traded: shadow veto lots (CL-9), predictions (CL-5, M-7) and
Claude-book deviations (CL-13, M-5).

Every function reads daily bars and writes plain dicts into `BookState` lists. Nothing here changes a
target, a stop or an order. A bad record is skipped with a `problem` note; measurement never stops a run.
"""
from __future__ import annotations

import math
import numbers

import numpy as np
import pandas as pd

from . import strategies

WEIGHT_CAP_CODE = "WEIGHT_CAP"  # decisions.WEIGHT_CAP_CODE: a rule target cut by code to fit the sleeve weight

VETO_SLEEVES = ("B", "C", "D")  # CL-7: only increases in B, C and D can be vetoed
BASE_RATE_LOOKBACK = 1260  # M-7: Brier_ref uses the event's frequency over the last 1,260 sessions
BASE_RATE_MIN_OBS = 60  # fewer past cases than this and the base rate is unknown (no skill score)
DEVIATION_SESSIONS = 20  # M-5: value_20d
HORIZONS = (5, 20, 60)  # CL-5
PROB_RANGE = (0.05, 0.95)  # CL-5
THRESHOLD_RANGE = (-50.0, 50.0)
FALLBACK_RISK_FRAC = 0.01  # shadow 1R per share when neither the fill nor the signal close is above the stop
# A vetoed DAY order would expire; a lot with no clean open this many business days after the signal (a halted
# name, missing data) expires unscored instead of entering weeks later.
MAX_ENTRY_DELAY_BDAYS = 3
MIN_SCORED_DEFAULT = 30  # CL-9 and guide rule 6 when the policy gives no number


# --- small helpers ----------------------------------------------------------------------------------


def _iso(d) -> str:
    return pd.Timestamp(d).date().isoformat()


def _num(x, default: float | None = None) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def _clip(x: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, x))


def _policy(policy) -> dict:
    return (policy.policy if hasattr(policy, "policy") else policy) or {}


def _min_scored(min_scored, policy, *keys: str) -> int:
    """An explicit number wins; else the first of `keys` found under the policy's claude_limits; else 30."""
    if min_scored is not None:
        return int(min_scored)
    limits = _policy(policy).get("claude_limits", {}) if policy is not None else {}
    for k in keys:
        if limits.get(k) is not None:
            return int(limits[k])
    return MIN_SCORED_DEFAULT


def _bdays(a, b) -> int:
    """Business days from `a` up to (not including) `b`: 1 for Friday → Monday."""
    return int(np.busday_count(pd.Timestamp(a).date(), pd.Timestamp(b).date()))


def _clean_opens(df: pd.DataFrame) -> pd.Series:
    o = pd.to_numeric(df["open"], errors="coerce")
    return o[np.isfinite(o) & (o > 0)]


def _upto(bars: dict, symbol: str, date) -> pd.DataFrame | None:
    """The symbol's bars up to and including `date` (no look-ahead), or None."""
    df = bars.get(symbol) if bars else None
    if df is None or len(df) == 0:
        return None
    return df[df.index <= pd.Timestamp(date)]


def _after(df: pd.DataFrame, date) -> pd.DataFrame:
    return df[df.index > pd.Timestamp(date)]


def _cost_bps(cost_bps, cfg, state, symbol: str) -> float:
    """EX-5 per-side cost in bps: a number applies to every symbol; a dict is per asset class; None uses
    the state's measured overrides, else the policy model."""
    if isinstance(cost_bps, numbers.Real) and not isinstance(cost_bps, bool):
        return float(cost_bps)
    cls = cfg.asset_class(symbol)
    if isinstance(cost_bps, dict) and cls in cost_bps:
        return float(cost_bps[cls])
    measured = (getattr(state, "cost_model_bps", None) or {}).get(cls)
    if measured is not None:
        return float(measured)
    return float(cfg.policy["turnover"]["cost_model_per_side_bps"].get(cls, 0.0))


# --- CL-9: shadow lots for vetoed entries -------------------------------------------------------------


def veto_lot_id(book: str, date: str, sleeve: str, symbol: str) -> str:
    return f"veto:{book}:{date}:{sleeve}:{symbol}"


def open_veto_lots(state, vetoes: list[dict], date: str, *, tags: dict | None = None) -> list[dict]:
    """CL-9: each vetoed increase becomes a shadow lot that enters at the next open with the rule's stop.

    `vetoes` are the records from `decisions.apply_review`: {date, sleeve, symbol, fraction, rule_qty,
    current_qty, stop, reason_code, prediction_id}. qty = fraction × (rule_qty − current_qty).
    A rerun on the same date replaces a lot that has not entered yet; an entered lot is never replaced.
    Returns the lots added.
    """
    added = []
    for v in vetoes or []:
        sleeve, symbol = v.get("sleeve"), v.get("symbol")
        if sleeve not in VETO_SLEEVES or not symbol:
            continue  # CL-7: sleeve A is never vetoed
        fraction = _clip(_num(v.get("fraction"), 1.0), 0.0, 1.0)
        rule_qty, current_qty = _num(v.get("rule_qty"), 0.0), _num(v.get("current_qty"), 0.0)
        qty = fraction * (rule_qty - current_qty)
        if not qty > 0:
            continue
        signal_date = _iso(v.get("date") or date)
        lot_id = veto_lot_id(state.book, signal_date, sleeve, symbol)
        existing = next((i for i, lt in enumerate(state.shadow_lots) if lt.get("id") == lot_id), None)
        if existing is not None and state.shadow_lots[existing].get("status") != "pending_entry":
            continue
        lot = {
            "id": lot_id, "book": state.book, "date": signal_date, "sleeve": sleeve, "symbol": symbol,
            "fraction": fraction, "rule_qty": rule_qty, "current_qty": current_qty, "qty": qty,
            "stop": _num(v.get("stop")), "status": "pending_entry",
            "reason_code": v.get("reason_code", ""), "prediction_id": v.get("prediction_id", ""),
            "signal_close": None, "entry_date": None, "entry_price": None, "initial_stop": None,
            "initial_risk": None, "costs": 0.0, "checked_through": None,
            "exit_signal_date": None, "exit_reason": None, "exit_date": None, "exit_price": None,
            "sessions_held": None, "pnl_net": None, "R_net": None, "veto_value": None, "value_usd": None,
            "tags": dict(tags or v.get("tags") or {}),
        }
        if existing is None:
            state.shadow_lots.append(lot)
        else:
            state.shadow_lots[existing] = lot
        added.append(lot)
    return added


def update_veto_lots(state, bars: dict, cfg, date: str, cost_bps=None) -> list[dict]:
    """CL-9: move each shadow lot along pending_entry → open → pending_exit → closed using bars up to `date`.

    Entry: the open of the first bar after the signal date, plus the cost model. A lot with no clean open
    within `MAX_ENTRY_DELAY_BDAYS` business days expires unscored (the rule's DAY order would have lapsed).
    Exits: the sleeve's own rules (`strategies.exit_signal`, with the C-7 ratchet for C) checked on every
    close since the last check; an exit signal fills at the next clean open. Closed lots get
    R_net = ((exit − entry) × qty − costs) / initial_risk and veto_value = −R_net × fraction.
    Returns one event dict per change.
    """
    events: list[dict] = []
    for lot in state.shadow_lots:
        if lot.get("status") in ("closed", "expired"):
            continue
        df = _upto(bars, lot.get("symbol", ""), date)
        if df is None or len(df) == 0:
            continue
        try:
            bps = _cost_bps(cost_bps, cfg, state, lot["symbol"])
            if lot["status"] == "pending_entry":
                events += _enter(lot, df, cfg, bps)
            if lot["status"] == "open":
                events += _check_exits(lot, df, cfg)
            if lot["status"] == "pending_exit":
                events += _exit(lot, df, bps)
        except Exception as e:  # noqa: BLE001 - one bad lot must not stop the daily run
            lot["problem"] = f"{type(e).__name__}: {e}"
    return events


def _risk_per_share(entry: float, stop: float, signal_close: float | None) -> float:
    """1R per share of a shadow lot: entry − stop, floored at the planned risk (signal close − stop) that the
    rule sized the lot on. A gap down to just above (or below) the stop therefore cannot turn one lot into a
    huge R that swamps the CL-9 sum. (Deliberate change from the spec's max(entry − stop, tiny).)"""
    planned = signal_close - stop if signal_close is not None and signal_close - stop > 0 else 0.0
    actual = entry - stop if entry - stop > 0 else 0.0
    if max(planned, actual) > 0:
        return max(planned, actual)
    return entry * FALLBACK_RISK_FRAC


def _expire(lot: dict, when, why: str) -> list[dict]:
    lot.update({"status": "expired", "expired_date": _iso(when), "expired_reason": why})
    return [{"id": lot["id"], "event": "expired", "date": lot["expired_date"], "reason": why}]


def _enter(lot: dict, df: pd.DataFrame, cfg, bps: float) -> list[dict]:
    after = _after(df, lot["date"])
    if after.empty:
        return []
    window = after[[_bdays(lot["date"], d) <= MAX_ENTRY_DELAY_BDAYS for d in after.index]]
    past_window = len(window) < len(after)
    late = after.index[len(window)] if past_window else None
    before = df[df.index <= pd.Timestamp(lot["date"])]
    signal_close = _num(before["close"].iloc[-1]) if len(before) else None
    if _num(lot.get("stop")) is None and len(before):
        lot["stop"] = _num(strategies.rule_stop(lot["sleeve"], before, cfg.policy))  # the rule's stop (CL-9)
    stop = _num(lot.get("stop"))
    if stop is None:
        lot["problem"] = "no stop for the shadow lot (too little history for the rule stop)"
        return _expire(lot, late, lot["problem"]) if past_window else []
    opens = _clean_opens(window)
    if opens.empty:
        if past_window:
            return _expire(lot, late, f"no clean open within {MAX_ENTRY_DELAY_BDAYS} business days of the "
                                      "signal (halted or missing data)")
        return []  # bad or missing bar: wait for clean data
    lot.pop("problem", None)
    entry_day, entry = opens.index[0], float(opens.iloc[0])
    if entry_day != after.index[0]:
        lot["note"] = "the first bar after the signal had no clean open; entered at the next clean open"
    qty = lot["qty"]
    lot.update({
        "status": "open", "signal_close": signal_close, "entry_date": _iso(entry_day), "entry_price": entry,
        "initial_stop": stop, "initial_risk": qty * _risk_per_share(entry, stop, signal_close),
        "costs": lot.get("costs", 0.0) + qty * entry * bps / 1e4, "checked_through": lot["date"],
    })
    return [{"id": lot["id"], "event": "entered", "date": lot["entry_date"], "price": entry}]


def _ratchet_c(stop: float, df: pd.DataFrame, policy: dict) -> float:
    """C-7: stop = max(stop, lowest low of the prior N sessions). Only ever raises."""
    n = int(policy["per_trade"].get("trail_low_sessions", {}).get("C", 10))
    low = _num(df["low"].iloc[-(n + 1):-1].min()) if len(df) > 1 else None
    return max(stop, low) if low is not None else stop


def _check_exits(lot: dict, df: pd.DataFrame, cfg) -> list[dict]:
    start = pd.Timestamp(lot.get("checked_through") or lot["date"])
    dates = df.index[(df.index > start) & (df.index >= pd.Timestamp(lot["entry_date"]))]
    sleeve_cfg = cfg.sleeves.get(lot["sleeve"], {})
    for d in dates:
        sub = df.loc[:d]
        if lot["sleeve"] == "C":
            lot["stop"] = _ratchet_c(lot["stop"], sub, cfg.policy)
        why = strategies.exit_signal(lot["sleeve"], sub, lot["stop"], lot["date"], sleeve_cfg, cfg.policy)
        lot["checked_through"] = _iso(d)
        if why:
            lot.update({"status": "pending_exit", "exit_signal_date": _iso(d), "exit_reason": why})
            return [{"id": lot["id"], "event": "exit_signal", "date": _iso(d), "reason": why}]
    return []


def _exit(lot: dict, df: pd.DataFrame, bps: float) -> list[dict]:
    after = _after(df, lot["exit_signal_date"])
    opens = _clean_opens(after)
    if opens.empty:
        return []  # no clean open yet: exit at the next one
    exit_date, price = opens.index[0], float(opens.iloc[0])
    if exit_date != after.index[0]:
        lot["note"] = "the bar after the exit signal had no clean open; exited at the next clean open"
    qty, entry = lot["qty"], lot["entry_price"]
    costs = lot["costs"] + qty * price * bps / 1e4
    pnl_net = (price - entry) * qty - costs
    r_net = pnl_net / lot["initial_risk"] if lot["initial_risk"] else None
    lot.update({
        "status": "closed", "exit_date": _iso(exit_date), "exit_price": price, "costs": costs,
        "sessions_held": int(((df.index > pd.Timestamp(lot["date"])) & (df.index <= exit_date)).sum()),
        "pnl_net": pnl_net, "R_net": r_net,
        "veto_value": -r_net * lot["fraction"] if r_net is not None else None,
        "value_usd": -pnl_net,  # dollars the veto saved (positive) or cost (negative), for G-4
    })
    return [{"id": lot["id"], "event": "closed", "date": lot["exit_date"], "price": price, "R_net": r_net,
             "veto_value": lot["veto_value"]}]


def _scored(state, since: str | None = None) -> list[dict]:
    out = []
    for lot in state.shadow_lots:
        if lot.get("status") != "closed" or _num(lot.get("veto_value")) is None:
            continue
        if since and lot.get("date", "") < since:
            continue
        out.append(lot)
    return out


def veto_summary(state, *, since: str | None = None) -> dict:
    """M-6 / CL-9: {n_scored, sum_value, by_code: {code: {n, sum}}} over closed shadow lots.

    `since` (ISO date) counts only vetoes on or after that date, e.g. after the owner resets the CL-9 latch.
    """
    lots = _scored(state, since)
    by_code: dict[str, dict] = {}
    for lot in lots:
        c = by_code.setdefault(lot.get("reason_code") or "UNKNOWN", {"n": 0, "sum": 0.0})
        c["n"] += 1
        c["sum"] += float(lot["veto_value"])
    for c in by_code.values():
        c["sum"] = round(c["sum"], 4)
    return {
        "n_scored": len(lots),
        "sum_value": round(float(sum(float(lt["veto_value"]) for lt in lots)), 4),
        "sum_value_usd": round(float(sum(_num(lt.get("value_usd"), 0.0) for lt in lots)), 2),
        "by_code": by_code,
        "n_open": sum(1 for lt in state.shadow_lots if lt.get("status") not in ("closed", "expired")
                      and (not since or lt.get("date", "") >= since)),
        "n_expired": sum(1 for lt in state.shadow_lots if lt.get("status") == "expired"
                         and (not since or lt.get("date", "") >= since)),
    }


def should_restrict(state, min_scored: int | None = None, *, since: str | None = None, policy=None) -> bool:
    """CL-9: vetoes have lost over at least `min_scored` scored lots → restrict the allowed skip codes.

    `min_scored` defaults to the policy's `claude_limits.veto_min_scored` (30). `since` defaults to
    `state.veto_reset_date` when the state has one, so an owner reset starts a fresh count instead of
    re-latching at once on the old lots.
    """
    n_min = _min_scored(min_scored, policy, "veto_min_scored")
    since = since or getattr(state, "veto_reset_date", None)
    s = veto_summary(state, since=since)
    return s["n_scored"] >= n_min and s["sum_value"] < 0


def clear_pending(state, date: str) -> dict[str, int]:
    """Drop records a discarded attempt on `date` left behind (a same-day rerun), so they are never scored:
    veto lots dated `date` that have not entered, and unresolved predictions and deviations dated `date`.
    Call it before storing a run's records. Returns how many of each were dropped."""
    date = _iso(date)
    counts = {}
    for name, keep in (("shadow_lots", lambda r: not (r.get("date") == date and r.get("status") == "pending_entry")),
                       ("predictions", lambda r: not (r.get("date") == date and r.get("outcome") is None)),
                       ("deviations", lambda r: not (r.get("date") == date and r.get("value_20d") is None))):
        rows = list(getattr(state, name, []) or [])
        kept = [r for r in rows if keep(r)]
        setattr(state, name, kept)
        counts[name] = len(rows) - len(kept)
    return counts


# --- CL-5 / M-7: predictions -----------------------------------------------------------------------------


def event_hits(close: pd.Series, horizon: int, direction: str, threshold_pct: float) -> pd.Series:
    """For each past close, whether `horizon` sessions later the close was above (below) close × (1 + thr)."""
    c = close.dropna()
    c = c[c > 0]
    fwd = (c.shift(-horizon) / c - 1.0).dropna()
    thr = threshold_pct / 100.0
    return fwd > thr if direction == "above" else fwd < thr


def base_rate_stats(close: pd.Series, horizon: int, direction: str, threshold_pct: float,
                    lookback: int = BASE_RATE_LOOKBACK, min_obs: int = BASE_RATE_MIN_OBS) -> tuple[float | None, int]:
    """(base rate, number of past cases used). The rate is None below `min_obs` cases. Fewer than `lookback`
    cases means the history was shorter than the rule's 1,260 sessions."""
    c = close.dropna()
    c = c.iloc[-(lookback + horizon):]
    hits = event_hits(c, horizon, direction, threshold_pct)
    n = int(len(hits))
    return (float(hits.mean()) if n >= min_obs else None), n


def base_rate(close: pd.Series, horizon: int, direction: str, threshold_pct: float,
              lookback: int = BASE_RATE_LOOKBACK, min_obs: int = BASE_RATE_MIN_OBS) -> float | None:
    """M-7 Brier_ref: how often the same event happened over the last `lookback` sessions (None when short)."""
    return base_rate_stats(close, horizon, direction, threshold_pct, lookback, min_obs)[0]


def _prediction_dict(p) -> dict:
    if hasattr(p, "model_dump"):
        return p.model_dump()
    return dict(p)


def add_predictions(state, predictions, *, date: str, book: str | None = None, bars: dict | None = None,
                    tags: dict | None = None) -> list[dict]:
    """CL-5: store today's predictions with the base close and the base rate, ready to be resolved (M-7).

    Probability is clipped to [0.05, 0.95] and the threshold to [−50, 50]; a horizon outside {5, 20, 60} or an
    unknown direction is dropped. A rerun on the same date replaces an unresolved prediction with the same id.
    Returns the stored records.
    """
    date = _iso(date)
    book = book or state.book
    stored = []
    for raw in predictions or []:
        p = _prediction_dict(raw)
        horizon = int(_num(p.get("horizon"), 0) or 0)
        direction = p.get("direction")
        prob, thr = _num(p.get("probability")), _num(p.get("threshold_pct"))
        if horizon not in HORIZONS or direction not in ("above", "below") or prob is None or thr is None:
            continue
        symbol = p.get("symbol", "")
        rec = {
            "id": str(p.get("id", "")), "uid": f"{book}:{date}:{p.get('id', '')}", "date": date, "book": book,
            "symbol": symbol, "horizon": horizon, "direction": direction,
            "threshold_pct": _clip(thr, *THRESHOLD_RANGE), "probability": _clip(prob, *PROB_RANGE),
            "linked_decision": p.get("linked_decision", ""), "base_close": None, "base_date": None,
            "base_rate": None, "base_rate_n": 0, "resolve_after": horizon, "resolve_after_date": None,
            "resolved_date": None,
            "resolved_close": None, "outcome": None, "brier": None, "brier_ref": None, "tags": dict(tags or {}),
        }
        _fill_base(rec, bars)
        existing = next((i for i, q in enumerate(state.predictions) if q.get("uid") == rec["uid"]), None)
        if existing is not None:
            if state.predictions[existing].get("outcome") is not None:
                continue
            state.predictions[existing] = rec
        else:
            state.predictions.append(rec)
        stored.append(rec)
    return stored


def _fill_base(rec: dict, bars: dict | None) -> None:
    df = _upto(bars or {}, rec["symbol"], rec["date"])
    if df is None:
        return
    close = df["close"].dropna()
    if close.empty:
        return
    rec["base_close"] = float(close.iloc[-1])
    rec["base_date"] = _iso(close.index[-1])
    rec["base_rate"], rec["base_rate_n"] = base_rate_stats(close, rec["horizon"], rec["direction"],
                                                           rec["threshold_pct"])


def resolve_predictions(state, bars: dict, date: str) -> list[dict]:
    """M-7: once `horizon` bars exist after the prediction date, outcome ∈ {0, 1}, brier = (p − o)² and
    brier_ref = (base_rate − o)². A malformed record gets a `problem` note and is skipped.
    Returns the predictions resolved in this call."""
    done = []
    for p in state.predictions:
        if p.get("outcome") is not None:
            continue
        try:
            if _resolve_prediction(p, bars, date):
                p.pop("problem", None)
                done.append(p)
        except Exception as e:  # noqa: BLE001 - measurement never stops a run
            p["problem"] = f"{type(e).__name__}: {e}"
    return done


def _resolve_prediction(p: dict, bars: dict, date: str) -> bool:
    df = _upto(bars, p.get("symbol", ""), date)
    if df is None:
        return False
    if p.get("base_close") is None:
        _fill_base(p, bars)
        if p.get("base_close") is None:
            return False
    after = df["close"][df.index > pd.Timestamp(p["date"])].dropna()
    h = int(p["horizon"])
    if len(after) < h:
        return False
    close_h = float(after.iloc[h - 1])
    level = float(p["base_close"]) * (1 + float(p["threshold_pct"]) / 100.0)
    o = int(close_h > level) if p["direction"] == "above" else int(close_h < level)
    prob, rate = float(p["probability"]), _num(p.get("base_rate"))
    when = _iso(after.index[h - 1])
    p.update({"outcome": o, "resolved_close": close_h, "resolve_after_date": when, "resolved_date": when,
              "brier": (prob - o) ** 2, "brier_ref": (rate - o) ** 2 if rate is not None else None})
    return True


# --- CL-13 / M-5: deviations ----------------------------------------------------------------------------


def add_deviations(state, records: list[dict], tags: dict | None = None) -> list[dict]:
    """CL-13: store the Claude book's deviation records to be valued after 20 sessions (M-5).

    One record per (date, sleeve, symbol); a rerun replaces an unresolved one. Returns the stored records.
    """
    stored = []
    for r in records or []:
        claude_pct, rule_pct = _num(r.get("claude_pct")), _num(r.get("rule_pct"))
        if claude_pct is None or rule_pct is None or not r.get("symbol") or not r.get("date"):
            continue
        rec = {
            "date": _iso(r["date"]), "symbol": r["symbol"], "sleeve": r.get("sleeve", ""),
            "rule_pct": rule_pct, "claude_pct": claude_pct, "reason_code": r.get("reason_code", ""),
            "evidence": list(r.get("evidence") or []), "prediction_id": r.get("prediction_id", ""),
            "fill_ref": None, "fill_date": None, "value_20d": None, "resolved_date": None,
            "tags": dict(tags or r.get("tags") or {}),
        }
        if _num(r.get("claude_pct_requested")) is not None:  # the ask, when the risk engine clipped it
            rec["claude_pct_requested"] = _num(r.get("claude_pct_requested"))
        key = (rec["date"], rec["sleeve"], rec["symbol"])
        existing = next((i for i, d in enumerate(state.deviations)
                         if (d.get("date"), d.get("sleeve"), d.get("symbol")) == key), None)
        if existing is not None:
            if state.deviations[existing].get("value_20d") is not None:
                continue
            state.deviations[existing] = rec
        else:
            state.deviations.append(rec)
        stored.append(rec)
    return stored


def resolve_deviations(state, bars: dict, date: str, *, sessions: int = DEVIATION_SESSIONS) -> list[dict]:
    """M-5: fill_ref = open of the first bar after the decision date (bar t; the next clean open if that bar's
    open is bad). Once bar t+20 exists, value_20d = (claude_pct − rule_pct) × (close_{t+20} / fill_ref − 1),
    a share of equity. A malformed record gets a `problem` note and is skipped.
    Returns the deviations resolved in this call."""
    done = []
    for d in state.deviations:
        if d.get("value_20d") is not None:
            continue
        try:
            if _resolve_deviation(d, bars, date, sessions):
                d.pop("problem", None)
                done.append(d)
        except Exception as e:  # noqa: BLE001 - measurement never stops a run
            d["problem"] = f"{type(e).__name__}: {e}"
    return done


def _resolve_deviation(d: dict, bars: dict, date: str, sessions: int) -> bool:
    df = _upto(bars, d.get("symbol", ""), date)
    if df is None:
        return False
    after = _after(df, d["date"])
    if after.empty:
        return False
    if d.get("fill_ref") is None:
        opens = _clean_opens(after)
        if opens.empty:
            return False
        d["fill_ref"], d["fill_date"] = float(opens.iloc[0]), _iso(opens.index[0])
    from_fill = df[df.index >= pd.Timestamp(d["fill_date"])]
    closes = pd.to_numeric(from_fill["close"].iloc[sessions:], errors="coerce")
    closes = closes[np.isfinite(closes) & (closes > 0)]
    if closes.empty:
        return False
    d["value_20d"] = (float(d["claude_pct"]) - float(d["rule_pct"])) * (float(closes.iloc[0]) / d["fill_ref"] - 1.0)
    d["resolved_date"] = _iso(closes.index[0])
    return True


# --- guide rule 6: automatic cut in the Claude book's freedom when deviations lose ------------------------------


def deviation_summary(state, *, since: str | None = None, exclude_codes=()) -> dict:
    """{n, n_resolved, sum_value_20d, by_code: {code: {n, sum}}} over the Claude book's deviations dated on or
    after `since`, leaving out records whose reason_code is in `exclude_codes`."""
    devs = [d for d in getattr(state, "deviations", []) or []
            if (not since or str(d.get("date", "")) >= since) and d.get("reason_code") not in exclude_codes]
    done = [d for d in devs if _num(d.get("value_20d")) is not None]
    by_code: dict[str, dict] = {}
    for d in done:
        c = by_code.setdefault(d.get("reason_code") or "UNKNOWN", {"n": 0, "sum": 0.0})
        c["n"] += 1
        c["sum"] += float(d["value_20d"])
    for c in by_code.values():
        c["sum"] = round(c["sum"], 6)
    return {"n": len(devs), "n_resolved": len(done),
            "sum_value_20d": round(float(sum(float(d["value_20d"]) for d in done)), 6), "by_code": by_code}


def should_restrict_deviations(state, min_resolved: int | None = None, *, since: str | None = None,
                               policy=None) -> bool:
    """Guide rule 6: deviations have lost (Σ value_20d < 0) over at least `min_resolved` resolved ones → the
    engine latches the Claude book to the rules' targets until the owner resets it.

    `min_resolved` defaults to the policy's `claude_limits.deviation_min_scored`, else `veto_min_scored` (30).
    `since` defaults to `state.deviations_reset_date` when the state has one.
    """
    n_min = _min_scored(min_resolved, policy, "deviation_min_scored", "veto_min_scored")
    since = since or getattr(state, "deviations_reset_date", None)
    # WEIGHT_CAP records are code's own cuts to fit a sleeve weight, not Claude's choices: M-5 reports them,
    # but they never move the latch on Claude's freedom.
    s = deviation_summary(state, since=since, exclude_codes=(WEIGHT_CAP_CODE,))
    return s["n_resolved"] >= n_min and s["sum_value_20d"] < 0
