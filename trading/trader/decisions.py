"""Turn Claude's menu choices into numbers inside every limit (rulebook section (e); guide rules 1, 2, 4).

Rules book: `apply_review` lets a review skip or halve new B, C and D entries, nothing else (CL-7, CL-8).
Claude book: `resolve_weights` (CL-10, CL-12, RISK-10), `resolve_actions` (CL-11, CL-13, CL-14) and
`resolved_to_targets` turn one decision into Targets. Those Targets still go through `RiskEngine.apply`.
`cap_weights` is the one place sleeve weights are bounded (RISK-7, RISK-8, M-11), for both books.

Code computes every number. A bad item is dropped with a plain-English reason and the rest is kept.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from datetime import date as Date, datetime, timedelta
from typing import Any, Iterable

import pandas as pd

from . import indicators as ind
from . import strategies as strat
from .ledger import sessions_between
from .models import Lot, Target
from .schemas import (ACTION_CODES, DEVIATION_CODES, SKIP_CODES, WEIGHT_UP_CODES, ClaudeDecision, DecisionError,
                      Halve, Prediction, ResolvedDecision, ResolvedTarget, Skip, WeightChoice, parse_decision,
                      parse_review)

SLEEVES = ("A", "B", "C", "D")
ENTRY_SLEEVES = ("B", "C", "D")  # CL-7: the only sleeves a review may skip or halve
PRICE_FIELDS = ("close", "open", "high", "low", "price", "volume")  # CL-8: DATA_SUSPECT evidence
CODE_SLEEVES = {"MEAN_REVERSION_SETUP": ("B",), "EARNINGS_IN_WINDOW": ("C",), "SCHEDULED_EVENT": ("B", "C")}
# CL-8: SCHEDULED_EVENT is on the next session; C-18: earnings within the next 5 sessions.
EVENT_SESSIONS = {"SCHEDULED_EVENT": 1, "EARNINGS_IN_WINDOW": 5}
POSITION_RULES = {"B": "B-1", "C": "C-5"}  # rule IDs behind each sleeve's max_positions
MAX_PREDICTIONS = 3  # CL-5, used when neither cfg nor the context gives the limit
WEIGHT_CAP_CODE = "WEIGHT_CAP"  # deviation record for a rule target cut by code to fit the sleeve weight
NEVER = 10**6  # sessions since a change that never happened
_TOL = 1e-9


# --- evidence paths (CL-2) ---------------------------------------------------------------------

_PATH_RE = re.compile(r"^[^.\[\]]+(\[[^\[\]]+\])*(\.[^.\[\]]+(\[[^\[\]]+\])*)*$")
_TOKEN_RE = re.compile(r"([^.\[\]]+)|\[([^\[\]]+)\]")
_INT_RE = re.compile(r"-?\d+")
_MISSING = object()


def _tokens(path: Any) -> list[str] | None:
    """Split `a.b[X].c` into ["a", "b", "X", "c"]; None when the path is malformed."""
    if not isinstance(path, str) or not _PATH_RE.match(path.strip()):
        return None
    out = []
    for m in _TOKEN_RE.finditer(path.strip()):
        tok = (m.group(1) if m.group(1) is not None else m.group(2)).strip().strip("'\"").strip()
        if not tok:
            return None
        out.append(tok)
    return out


def _step(node: Any, tok: str) -> Any:
    if isinstance(node, dict):
        return node.get(tok, _MISSING)
    if isinstance(node, (list, tuple)):
        if _INT_RE.fullmatch(tok):
            i = int(tok)
            return node[i] if -len(node) <= i < len(node) else _MISSING
        want = tok.upper()
        for item in node:
            if isinstance(item, dict) and str(item.get("symbol", "")).upper() == want:
                return item
            # data_problems is a list of "SYM: problem" strings
            if isinstance(item, str) and (item.upper() == want or item.upper().startswith(want + ":")):
                return item
    return _MISSING


def _lookup(ctx: Any, tokens: list[str]) -> Any:
    node = ctx
    for tok in tokens:
        node = _step(node, tok)
        if node is _MISSING:
            return _MISSING
    return node


def _present(value: Any) -> bool:
    """None, NaN and empty containers carry no evidence."""
    if value is _MISSING or value is None:
        return False
    if isinstance(value, (list, tuple, dict)):
        return len(value) > 0
    if isinstance(value, str):
        return bool(value.strip())
    try:
        return not bool(pd.isna(value))
    except (TypeError, ValueError):
        return True


def path_exists(ctx: Any, path: Any) -> bool:
    """CL-2: does `path` (e.g. `rule_signals.C.indicators[NVDA].volume_ratio`) point at a real value in ctx?

    Dots walk dict keys. `[X]` picks the list item whose `symbol` is X (or the dict key X); `[3]` indexes a list.
    """
    tokens = _tokens(path)
    return tokens is not None and _present(_lookup(ctx, tokens))


def evidence_ok(ctx: Any, paths: Any) -> tuple[bool, str]:
    """CL-2: a non-empty list of paths that all exist in today's context."""
    if not isinstance(paths, (list, tuple)) or not paths:
        return False, "no evidence paths (CL-2)"
    if not isinstance(ctx, dict):
        return False, "no context to check the evidence against (CL-2)"
    for p in paths:
        if not path_exists(ctx, p):
            return False, f"evidence path not in today's context: {str(p)[:120]!r} (CL-2)"
    return True, ""


def _evidence_check(ctx: Any, paths: Any) -> tuple[bool, str]:
    """Like evidence_ok, but without a context only a non-empty list of paths can be checked.

    Only for the review's skips and halves (the old 4-argument call), which can only lower risk.
    """
    if ctx is not None:
        return evidence_ok(ctx, paths)
    if isinstance(paths, (list, tuple)) and paths and all(isinstance(p, str) and p.strip() for p in paths):
        return True, ""
    return False, "no evidence paths (CL-2)"


def _mentions(value: Any, symbol: str) -> bool:
    if isinstance(value, dict):
        return str(value.get("symbol", "")).upper() == symbol
    if isinstance(value, str):
        return re.search(rf"(?<![A-Z0-9/.]){re.escape(symbol)}(?![A-Z0-9/])", value.upper()) is not None
    return False


def _data_suspect_ok(ctx: Any, paths: Iterable, symbol: str | None = None) -> bool:
    """CL-8: DATA_SUSPECT must cite `data_problems` or a price field, about the skipped symbol when there is one."""
    for p in paths or []:
        toks = _tokens(p)
        if not toks or not (toks[0] == "data_problems" or toks[-1].lower() in PRICE_FIELDS):
            continue
        if symbol is None or ctx is None:
            return True
        sym = symbol.upper()
        # "C:NVDA" is how the context keys the Claude book's menus
        if any(t.upper().split(":", 1)[-1] == sym for t in toks) or _mentions(_lookup(ctx, toks), sym):
            return True
    return False


def _backs(pred: Any, kind: str, sleeve: str, symbol: str) -> bool:
    """CL-5/CL-13: a prediction backs a skip or an action on its own symbol, or the one it names in
    linked_decision (e.g. "action:C:NVDA", "skip:NVDA"). So one prediction cannot justify changes elsewhere."""
    if str(_get(pred, "symbol", "")).strip().upper() == symbol:
        return True
    link = re.sub(r"\s+", "", str(_get(pred, "linked_decision", "") or "")).upper()
    return link in {f"{kind}:{symbol}", f"{kind}:{sleeve}:{symbol}"}


# --- small helpers ------------------------------------------------------------------------------


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _num(x: Any) -> float | None:
    """A finite float, or None."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _lot(lots: dict | None, sleeve: str, symbol: str) -> Lot | None:
    return ((lots or {}).get(sleeve) or {}).get(symbol)


def _qty(lot: Lot | None) -> float:
    return float(lot.qty) if lot is not None else 0.0


def _direction(x: float, current: float) -> int:
    if x > current + _TOL:
        return 1
    if x < current - _TOL:
        return -1
    return 0


def trim_sentences(text: str, n: int) -> str:
    """CL-4: keep the first `n` sentences."""
    parts = [p for p in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if p]
    return " ".join(parts[: max(0, int(n))])


def clean_predictions(predictions: Iterable, *, max_n: int, allowlist: Iterable[str] | None,
                      log: list[str] | None = None) -> list[Prediction]:
    """CL-5: at most `max_n` a day, symbol on the allowlist, probability in [0.05, 0.95], threshold in [-50, 50].

    `allowlist=None` skips only the allowlist check (no list to check against).
    """
    log = log if log is not None else []
    allow = None if allowlist is None else {str(s).upper() for s in allowlist}
    kept: list[Prediction] = []
    for p in predictions or []:
        if isinstance(p, dict):
            try:
                p = Prediction.model_validate(p)
            except ValueError:
                log.append("prediction dropped: not a valid prediction")
                continue
        if not isinstance(p, Prediction):
            log.append("prediction dropped: not a valid prediction")
            continue
        pid, sym = str(p.id).strip(), str(p.symbol).strip().upper()
        prob, thr = _num(p.probability), _num(p.threshold_pct)
        if not pid or pid in {k.id for k in kept}:
            log.append(f"prediction {pid or '?'} dropped: missing or duplicate id")
        elif allow is not None and sym not in allow:
            log.append(f"prediction {pid} dropped: {sym} is not on the allowlist (CL-5)")
        elif prob is None or thr is None:
            log.append(f"prediction {pid} dropped: probability or threshold is not a number")
        elif len(kept) >= max_n:
            log.append(f"prediction {pid} dropped: at most {max_n} predictions a day (CL-5)")
        else:
            clipped = {"id": pid, "symbol": sym, "probability": min(max(prob, 0.05), 0.95),
                       "threshold_pct": min(max(thr, -50.0), 50.0)}
            if clipped["probability"] != prob or clipped["threshold_pct"] != thr:
                log.append(f"prediction {pid}: probability or threshold clipped into range (CL-5)")
            kept.append(p.model_copy(update=clipped))
    return kept


# --- sleeve weights (CL-10, CL-12, RISK-7, RISK-8, RISK-10, M-11) -------------------------------


def cap_weights(cfg, weights: dict | None, promoted: Iterable[str] | None = (),
                demoted: dict | None = None) -> dict[str, float]:
    """The one place sleeve weights are bounded, for both books.

    Order: clip to [min, cap] (RISK-8 probation cap = default until M-10 passes); D = 0 when disabled;
    M-11 demotion ("half" or "stop") -> the sleeve's min; RISK-7 C + D <= max_speculative_weight (cut D, then C,
    down to their mins, and below them if the cap still binds); scale all down to 1 - min_cash_buffer.
    A missing or non-numeric weight counts as the sleeve's min.
    """
    pf = cfg.policy["portfolio"]
    promoted = tuple(promoted or ())
    out: dict[str, float] = {}
    for s in SLEEVES:
        lo, hi = float(cfg.sleeves[s]["min"]), cfg.sleeve_weight_cap(s, promoted)
        w = _num((weights or {}).get(s))
        out[s] = min(max(lo if w is None else w, lo), hi)
    if not cfg.sleeve_enabled("D"):
        out["D"] = 0.0
    for s, level in (demoted or {}).items():
        if s in out and level in ("half", "stop"):
            out[s] = min(out[s], float(cfg.sleeves[s]["min"]))
    _cap_speculative(cfg, out, float(pf.get("max_speculative_weight", 1.0)))
    budget = 1.0 - float(pf["min_cash_buffer"])
    total = sum(out.values())
    if total > budget:
        out = {s: w * budget / total for s, w in out.items()}
    return out


def _cap_speculative(cfg, out: dict[str, float], cap: float) -> None:
    """RISK-7: w_C + w_D <= cap. D is cut first, then C; the cap wins over the sleeve mins."""
    excess = out["C"] + out["D"] - cap
    for floor_at_min in (True, False):
        for s in ("D", "C"):
            if excess <= _TOL:
                return
            floor = min(float(cfg.sleeves[s]["min"]), out[s]) if floor_at_min else 0.0
            cut = min(excess, out[s] - floor)
            out[s] -= cut
            excess -= cut


def _on_watch(cfg, breakers: Any) -> bool:
    """RISK-10: the watch flag, or the drawdown itself when the flag is not there."""
    dd = _num(_get(breakers, "drawdown", 0.0)) or 0.0
    return bool(_get(breakers, "watch", False)) or dd >= float(cfg.policy["breakers"]["watch_drawdown"])


def _choice(choices: Any, s: str, problems: list[str]) -> WeightChoice:
    c = choices.get(s) if isinstance(choices, dict) else _get(choices, s)
    if c is None:
        return WeightChoice()
    if isinstance(c, WeightChoice):
        return c
    try:
        return WeightChoice.model_validate({"choice": c} if isinstance(c, str) else c)
    except ValueError:
        problems.append(f"weight {s}: invalid choice, kept as 'keep'")
        return WeightChoice()


def _menu_weight(choice: str, s: str, base: float, rule: dict, cfg) -> float:
    step = float(cfg.policy["claude_limits"]["weight_step"])
    wanted = {
        "keep": base,
        "up": base + step,
        "down": base - step,
        "rule": _num((rule or {}).get(s)),
        "default": float(cfg.sleeves[s]["default"]),
    }.get(choice, base)
    wanted = base if wanted is None else wanted
    return min(max(wanted, base - step), base + step)  # CL-12: at most one step per change


def _weight_refusal(s: str, c: WeightChoice, base: float, want: float, *, cfg, breakers: Any, ctx: Any,
                    since: int) -> str:
    """Why a requested weight change is refused, or "" when it may go ahead (CL-12, RISK-10)."""
    min_s = int(cfg.policy["claude_limits"]["weight_change_min_sessions"])
    if since < min_s:
        return f"last change {since} session(s) ago; at most one change per {min_s} sessions (CL-12)"
    if want <= base or s not in ENTRY_SLEEVES:
        return ""
    if _on_watch(cfg, breakers):
        return "drawdown watch tier: B, C and D weights may not rise (RISK-10)"
    if _get(breakers, "halted", False) or _get(breakers, "monthly_block", False):
        return "the book is halted or blocked for the month: no weight increases"
    if (_num((_get(breakers, "sleeve_risk_mult", None) or {}).get(s, 1.0)) or 0.0) < 1.0:
        return f"sleeve {s} is in a drawdown or demotion tier: its weight may not rise (RISK-13, M-11)"
    if c.reason_code not in WEIGHT_UP_CODES:
        return f"a B, C or D increase needs a reason code from {', '.join(WEIGHT_UP_CODES)} (CL-12)"
    ok, why = evidence_ok(ctx, c.evidence)  # no context: nothing can be verified, so no increase
    if not ok:
        return why
    if c.reason_code == "RETURN_TO_DEFAULT" and base >= float(cfg.sleeves[s]["default"]) - _TOL:
        return "RETURN_TO_DEFAULT cannot raise a weight above its default"
    return ""


def resolve_weights(choices: Any, *, cfg, prev: dict | None, rule: dict | None, sessions_since_change: dict | None,
                    breakers: Any, promoted: Iterable[str] | None = (), demoted: dict | None = None,
                    ctx: Any = None) -> tuple[dict[str, float], dict[str, dict], list[str]]:
    """CL-10/CL-12/RISK-10: menu moves -> sleeve weights, then `cap_weights`.

    keep = prev, up/down = prev +/- weight_step, rule = the rules' weight, default = the sleeve default; every move
    is clamped to one step. A change is ignored inside the rate limit. Raising B, C or D needs a WEIGHT_UP_CODES
    reason with evidence that exists in `ctx` (so without ctx it is refused) and is refused on the watch tier.
    Returns (weights, reasons per sleeve, problems).
    """
    problems: list[str] = []
    prev, rule, since_map = prev or {}, rule or {}, sessions_since_change or {}
    raw, reasons = {}, {}
    for s in SLEEVES:
        c = _choice(choices, s, problems)
        base = next((w for w in (_num(prev.get(s)), _num(rule.get(s))) if w is not None),
                    float(cfg.sleeves[s]["default"]))
        requested = _menu_weight(c.choice, s, base, rule, cfg)
        want, note = requested, ""
        if abs(requested - base) > _TOL:
            since = _num(since_map.get(s))
            since = NEVER if since is None else int(since)
            note = _weight_refusal(s, c, base, requested, cfg=cfg, breakers=breakers, ctx=ctx, since=since)
            if note:
                want = base
                problems.append(f"weight {s}: '{c.choice}' refused, {note}")
            elif c.reason_code == "RETURN_TO_DEFAULT" and s in ENTRY_SLEEVES and want > base:
                want = min(want, float(cfg.sleeves[s]["default"]))
        raw[s] = want
        reasons[s] = {"choice": c.choice, "reason_code": c.reason_code, "evidence": list(c.evidence),
                      "prev": base, "requested": requested, "note": note}
    final = cap_weights(cfg, raw, promoted, demoted)
    before = cap_weights(cfg, {s: reasons[s]["prev"] for s in SLEEVES}, promoted, demoted)
    for s in SLEEVES:
        applied = abs(raw[s] - reasons[s]["prev"]) > _TOL
        reasons[s].update(final=final[s], changed=bool(applied and abs(final[s] - before[s]) > _TOL))
    return final, reasons, problems


def _iso_day(value: Any) -> Date | None:
    """A calendar day from "YYYY-MM-DD" (a time or time zone after it is ignored), a date, a Timestamp, or
    an int like 20260918. Anything else is None (never read as nanoseconds since 1970)."""
    if isinstance(value, datetime):
        return None if pd.isna(value) else value.date()
    if isinstance(value, Date):
        return value
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip()
    if isinstance(value, int) and re.fullmatch(r"\d{8}", text):
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return Date.fromisoformat(text[:10])
    except ValueError:
        return None


def sessions_since(dates: Iterable[Any], bars_index: Any, date: str) -> int:
    """CL-12: sessions after the last change date, up to and including `date`. NEVER when there was no change.

    Dates that cannot be read are skipped. An unreadable run date gives 0 (no change today).
    """
    today = _iso_day(date)
    if today is None:
        return 0
    days = [d for d in (_iso_day(x) for x in (dates or [])) if d is not None]
    if not days:
        return NEVER
    last = max(days)
    if last >= today:
        return 0
    try:
        idx = pd.DatetimeIndex(bars_index) if bars_index is not None and len(bars_index) else None
    except (TypeError, ValueError):
        idx = None
    if idx is None:
        return sessions_between(last.isoformat(), today.isoformat())
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    idx = idx.normalize()
    return int(((idx > pd.Timestamp(last)) & (idx <= pd.Timestamp(today))).sum())


def sessions_since_change(weight_history: Iterable[dict], bars_index: Any, date: str,
                          problems: list[str] | None = None) -> dict[str, int]:
    """Per sleeve, `sessions_since` over the weight_history rows that list it under `changed`.

    Row shape (written by the engine): {"date": "YYYY-MM-DD", "changed": [sleeves], ...}. Rows that are not
    dicts, or whose date cannot be read, are skipped and noted in `problems`.
    """
    rows = []
    for h in weight_history or []:
        if not isinstance(h, dict):
            if problems is not None:
                problems.append("weight_history row ignored: not a dict")
            continue
        changed = h.get("changed") or []
        if not isinstance(changed, (list, tuple, set)):
            if problems is not None:
                problems.append("weight_history row ignored: 'changed' is not a list of sleeves")
            continue
        if changed and _iso_day(h.get("date")) is None and problems is not None:
            problems.append(f"weight_history row ignored: date {str(h.get('date'))[:30]!r} is not YYYY-MM-DD")
        rows.append((h.get("date"), changed))
    return {s: sessions_since([d for d, changed in rows if s in changed], bars_index, date) for s in SLEEVES}


# --- rules book review (CL-7, CL-8, CL-2, CL-5) -------------------------------------------------


def session_after(day: Date, n: int = 1) -> Date:
    """The n-th trading session after `day` (NYSE full-day holidays; one-off closures are not known)."""
    cand = day
    for _ in range(7 * max(1, n) + 14):
        cand += timedelta(days=1)
        if sessions_between(day.isoformat(), cand.isoformat()) >= n:
            return cand
    return cand


def _event_date_why(code: str, event_date: str, date: str) -> str:
    """CL-8: SCHEDULED_EVENT must be on the next session; EARNINGS_IN_WINDOW (C-18) from today up to the 5th
    session after it."""
    if code not in EVENT_SESSIONS:
        return ""
    try:
        ev = Date.fromisoformat(str(event_date).strip())
    except ValueError:
        return f"{code} needs event_date as YYYY-MM-DD (CL-8)"
    today = _iso_day(date) if date else None
    if today is None:
        return ""  # no usable run date: only the date format can be checked
    last = session_after(today, EVENT_SESSIONS[code])
    if code == "SCHEDULED_EVENT":
        if ev != last:
            return f"SCHEDULED_EVENT event_date {ev} is not the next session after {today} ({last}) (CL-8)"
    elif not today <= ev <= last:
        return f"EARNINGS_IN_WINDOW event_date {ev} is not within the next 5 sessions after {today} (C-18, CL-8)"
    return ""


def _veto_why(item: Skip | Halve, *, ctx: Any, allowed_codes: Iterable[str], preds: dict[str, Any], date: str,
              symbol: str | None) -> str:
    """Why one skip or halve is invalid, or "". A skip's prediction must be about the skipped symbol or name the
    skip in linked_decision; a sleeve-wide halve may use any kept prediction."""
    code = item.reason_code
    if item.sleeve not in ENTRY_SLEEVES:
        return f"sleeve {item.sleeve} cannot be skipped or halved; only new B, C and D entries can (CL-7)"
    if code not in tuple(allowed_codes):
        return f"reason code {code} is not allowed now (CL-8, CL-9)"
    if code in CODE_SLEEVES and item.sleeve not in CODE_SLEEVES[code]:
        return f"{code} is only for sleeve(s) {'/'.join(CODE_SLEEVES[code])} (CL-8)"
    why = _event_date_why(code, item.event_date, date)
    if why:
        return why
    ok, why = _evidence_check(ctx, item.evidence)
    if not ok:
        return why
    if code == "DATA_SUSPECT" and not _data_suspect_ok(ctx, item.evidence, symbol):
        return "DATA_SUSPECT must cite data_problems or a price field of this symbol (CL-8)"
    pred = preds.get(item.prediction_id) if item.prediction_id else None
    if pred is None:
        return "needs a prediction_id that matches one of the review's kept predictions (CL-5)"
    if symbol is not None and not _backs(pred, "SKIP", item.sleeve, symbol):
        return f"prediction {item.prediction_id} is about {_get(pred, 'symbol', '?')}, not {symbol} (CL-5)"
    return ""


def _prediction_limits(cfg, ctx: Any) -> tuple[int, list[str] | None]:
    """CL-5: (max predictions a day, allowlist) from cfg, else from the context, else (3, no allowlist)."""
    if cfg is not None:
        return int(cfg.policy["claude_limits"]["max_predictions_per_day"]), list(cfg.allowlist())
    ctx = ctx if isinstance(ctx, dict) else {}
    limit = _num(_get(ctx.get("limits"), "max_predictions_per_day"))
    allow = ctx.get("allowlist")
    return (max(0, int(limit)) if limit is not None else MAX_PREDICTIONS,
            list(allow) if isinstance(allow, (list, tuple, set)) else None)


def _as_review(review: Any, log: list[str]) -> Any:
    if isinstance(review, (str, bytes, dict)):
        try:
            parsed, problems = parse_review(review)
        except DecisionError as e:
            log.append(f"review unusable, the rules run unreviewed: {e}")
            return None
        log.extend(f"review: {p}" for p in problems)
        return parsed
    return review


def _valid_items(items: Iterable, model: type, label: str, check, log: list[str]) -> list:
    """Validate skip or halve items one by one; old-style bare strings have no reason code and are ignored."""
    good = []
    for item in items or []:
        if isinstance(item, dict):
            try:
                item = model.model_validate(item)
            except ValueError:
                log.append(f"review {label} dropped: not valid")
                continue
        if not isinstance(item, model):
            log.append(f"review {label} {item!r} ignored: no reason code, evidence or prediction (CL-8)")
            continue
        why = check(item)
        if why:
            name = f"{item.sleeve}/{item.symbol.upper()}" if isinstance(item, Skip) else f"sleeve {item.sleeve}"
            log.append(f"review {label} {name} ignored: {why}")
            continue
        good.append(item)
    return good


def apply_review(targets: list[Target], review: Any, lots: dict, log: list[str], *, ctx: Any = None,
                 allowed_codes: Iterable[str] = SKIP_CODES, date: str = "",
                 cfg=None) -> tuple[list[Target], list[dict]]:
    """CL-7/CL-8: the review may only skip or halve increases in B, C and D. A, exits and stops are never touched.

    Each skip or halve needs an allowed reason code (CL-8/CL-9), valid evidence (CL-2, checked when ctx is given)
    and a prediction_id from the review (CL-5; for a skip, about that symbol or linked to it); invalid ones are
    logged and ignored. Returns the targets and one veto record per skipped or halved increase (the input for
    CL-9 shadow lots; `verified` is always False until an earnings calendar exists, C-18). The review's
    predictions are first cleaned by `clean_predictions`, with the limit and allowlist from `cfg`, else from
    ctx["limits"] / ctx["allowlist"], else at most 3 and no allowlist check.
    """
    if review is None:
        return list(targets), []
    review = _as_review(review, log)
    if review is None:
        return list(targets), []
    if not date and isinstance(ctx, dict):
        date = str(ctx.get("date") or "")
    max_n, allow = _prediction_limits(cfg, ctx)
    preds = clean_predictions(_get(review, "predictions", []) or [], max_n=max_n, allowlist=allow, log=log)
    check = dict(ctx=ctx, allowed_codes=allowed_codes, preds={p.id: p for p in preds}, date=date)
    skips = _valid_items(_get(review, "skip_entries", []), Skip, "skip",
                         lambda k: _veto_why(k, symbol=k.symbol.upper(), **check), log)
    halves = _valid_items(_get(review, "halve_sleeves", []), Halve, "halve",
                          lambda h: _veto_why(h, symbol=None, **check), log)
    skip_by_key = {}
    for k in skips:
        skip_by_key.setdefault((k.sleeve, k.symbol.upper()), k)
    halve_by_sleeve = {}
    for h in halves:
        halve_by_sleeve.setdefault(h.sleeve, h)

    out, vetoes, used, used_halves = [], [], set(), set()
    for t in targets:
        cur_lot = _lot(lots, t.sleeve, t.symbol)
        cur, qty = _num(cur_lot.qty if cur_lot is not None else 0.0), _num(t.qty)
        key = (t.sleeve, t.symbol.upper())
        if t.sleeve not in ENTRY_SLEEVES or qty is None or cur is None or qty <= cur + _TOL:
            out.append(t)  # a quantity that is not a number is left for the risk engine to reject
            continue
        item, fraction = (skip_by_key[key], 1.0) if key in skip_by_key else (halve_by_sleeve.get(t.sleeve), 0.5)
        if item is None:
            out.append(t)
            continue
        if fraction == 1.0:
            used.add(key)
        else:
            used_halves.add(t.sleeve)
        word = "skipped" if fraction == 1.0 else "halved"
        out.append(replace(t, qty=cur + (qty - cur) * (1.0 - fraction),
                           reason=f"{t.reason} ({word} by review: {item.reason_code})"))
        log.append(f"{t.sleeve}/{t.symbol}: increase {word} by the review ({item.reason_code})")
        vetoes.append({"date": date, "sleeve": t.sleeve, "symbol": t.symbol, "fraction": fraction,
                       "rule_qty": qty, "current_qty": cur, "stop": t.stop, "reason_code": item.reason_code,
                       "prediction_id": item.prediction_id, "event_date": item.event_date,
                       "verified": False})  # CL-8: no earnings calendar yet (C-18), so never verified
    for key in skip_by_key:
        if key not in used:
            log.append(f"review skip {key[0]}/{key[1]}: no increase to skip today")
    for sleeve in halve_by_sleeve:
        if sleeve not in used_halves:
            log.append(f"review halve sleeve {sleeve}: no increase to halve today")
    return out, vetoes


# --- Claude book: eligibility and stops (CL-11, CL-14) ----------------------------------------


def _close(df: pd.DataFrame | None) -> float | None:
    if df is None or not len(df):
        return None
    c = df["close"].dropna()
    return _num(c.iloc[-1]) if len(c) else None


def c2_passers(cfg, bars: dict) -> set[str]:
    """C-2 today: names of the C universe that pass the trend template (same inputs as `strategies.sleeve_c`)."""
    c = cfg.sleeves["C"]
    universe = [s for s in c["universe"] if s in bars and len(bars[s]) >= 260]
    r12 = pd.Series({s: ind.total_return(bars[s]["close"], 252) for s in universe}, dtype=float).dropna()
    rs_pct = r12.rank(pct=True) * 100
    out = set()
    for s in universe:
        try:
            ok, _ = strat.trend_template(bars[s], float(rs_pct.get(s, 0.0)), c["rs_min_percentile"])
        except (IndexError, KeyError, ValueError):
            ok = False
        if ok:
            out.add(s)
    return out


def eligibility(cfg, bars: dict, permissions: dict | None) -> dict[str, set[str]]:
    """CL-11: which symbols each sleeve may increase today in the Claude book.

    A: A assets and BIL. B: B symbols with close > SMA200 and perm_B > 0. C: names passing C-2 today with
    perm_C > 0. D: enabled, D symbols, perm_D > 0. A missing permission counts as 0 for B, C and D.
    """
    perm = permissions or {}
    a = cfg.sleeves["A"]
    out: dict[str, set[str]] = {s: set() for s in SLEEVES}
    if (_num(perm.get("A", 1.0)) or 0.0) > 0:
        out["A"] = set(a["assets"]) | {a["cash"]} | (set(a["gem"].values()) if a.get("gem_blend") else set())
    if (_num(perm.get("B", 0.0)) or 0.0) > 0:
        for sym in cfg.sleeves["B"]["symbols"]:
            df = bars.get(sym)
            close = _close(df)
            sma200 = _num(ind.sma(df["close"], 200).iloc[-1]) if close is not None else None
            if close is not None and sma200 is not None and close > sma200:
                out["B"].add(sym)
    if (_num(perm.get("C", 0.0)) or 0.0) > 0:
        out["C"] = c2_passers(cfg, bars)
    if cfg.sleeve_enabled("D") and (_num(perm.get("D", 0.0)) or 0.0) > 0:
        out["D"] = {s for s in cfg.sleeves["D"]["symbols"] if _close(bars.get(s)) is not None}
    return out


def stop_menu(sleeve: str, df: pd.DataFrame | None, policy: dict, lot: Lot | None = None) -> dict:
    """CL-14 / guide 2: the stop numbers behind the menu. A has no stops (A-5).

    rule = `strategies.rule_stop` at today's close (also the floor for increases); tight = halfway between the
    price and the rule stop; keep = the lot's current stop, or the rule stop when there is none.
    """
    keep_lot = _num(lot.stop) if lot is not None else None  # a NaN stop from an odd state file counts as none
    price = _close(df)
    if sleeve not in ENTRY_SLEEVES or price is None:
        return {"rule": None, "tight": None, "keep": None if sleeve not in ENTRY_SLEEVES else keep_lot}
    fresh = _num(strat.rule_stop(sleeve, df, policy))
    if fresh is not None and fresh >= price:
        fresh = None  # zero ATR: no usable stop
    tight = price - 0.5 * (price - fresh) if fresh is not None else None
    return {"rule": fresh, "tight": tight, "keep": keep_lot if keep_lot is not None else fresh}


def is_deviation(claude_pct: float, rule_pct: float, current_pct: float, threshold: float) -> bool:
    """CL-13: more than `threshold` of the larger target apart, or a different direction versus current."""
    if abs(claude_pct - rule_pct) > threshold * max(claude_pct, rule_pct) + _TOL:
        return True
    return _direction(claude_pct, current_pct) != _direction(rule_pct, current_pct)


# --- Claude book: one decision -> resolved targets (CL-11, CL-13, CL-14, CL-2, CL-5) --------------


@dataclass
class _Inputs:
    cfg: Any
    ctx: Any
    rules: dict[str, Target]
    lots: dict
    bars: dict
    prices: dict[str, float]
    equity: float
    eligible: dict[str, set[str]]
    preds: dict[str, Prediction]
    sample: int | None
    allow: set[str] = field(default_factory=set)
    problems: list[str] = field(default_factory=list)

    def price(self, sym: str) -> float | None:
        p = _num(self.prices.get(sym))
        return p if p is not None and p > 0 else None


def _collect_targets(value: Any, out: list[Target], problems: list[str]) -> None:
    if isinstance(value, Target):
        out.append(value)
    elif isinstance(getattr(value, "targets", None), dict):  # a SleevePlan
        _collect_targets(list(value.targets.values()), out, problems)
    elif isinstance(value, dict):
        for v in value.values():
            _collect_targets(v, out, problems)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _collect_targets(v, out, problems)
    elif value is not None:
        problems.append(f"rule targets: a {type(value).__name__} is not a Target and was ignored")


def _index_targets(rule_targets: Any, problems: list[str] | None = None) -> dict[str, Target]:
    """Accept a list of Targets, a {key: Target} dict, the {sleeve: SleevePlan} plans, {sleeve: {sym: Target}}
    or {sleeve: [Target]}. Anything else is logged in `problems`, never skipped silently."""
    items: list[Target] = []
    _collect_targets(rule_targets, items, problems if problems is not None else [])
    out: dict[str, Target] = {}
    for t in items:
        out.setdefault(f"{t.sleeve}:{t.symbol}", t)
    return out


def _rule_qty(rt: Target | None, cur: float, key: str, problems: list[str]) -> float:
    """The rule's quantity. Not a number -> hold, as the risk engine rejects it in the rules book; negative -> 0,
    as the risk engine clips it (long only)."""
    if rt is None:
        return cur
    q = _num(rt.qty)
    if q is None:
        problems.append(f"{key}: the rule's target quantity is not a number; held at {cur:g}")
        return cur
    if q < 0:
        problems.append(f"{key}: the rule's target quantity {q:g} is negative; treated as 0 (long only)")
        return 0.0
    return q


def _baseline(sleeve: str, sym: str, inp: _Inputs) -> ResolvedTarget | None:
    """The rule's own target for one key (source "rule"); a held lot without a rule target holds."""
    price = inp.price(sym)
    if price is None:
        return None
    lot, rt = _lot(inp.lots, sleeve, sym), inp.rules.get(f"{sleeve}:{sym}")
    cur = _qty(lot)
    rule_qty = _rule_qty(rt, cur, f"{sleeve}:{sym}", inp.problems)
    # A NaN stop would slip past the risk engine's "missing stop" check, so it becomes None.
    stop = None if sleeve == "A" else _num(rt.stop if rt is not None else (lot.stop if lot is not None else None))
    reason = rt.reason if rt is not None else ("hold (no rule target)" if lot is not None else "no position")
    return ResolvedTarget(sleeve=sleeve, symbol=sym, pct=rule_qty * price / inp.equity, stop=stop,
                          rule_pct=rule_qty * price / inp.equity, current_pct=cur * price / inp.equity,
                          rule_stop=stop, rationale=reason, source="rule")


def _size_pct(a, base: ResolvedTarget, inp: _Inputs, notes: list[str]) -> float | None:
    """Size menu -> share of equity (guide 2). `pct` is clipped to [0, the symbol's notional cap]."""
    if a.size == "rule":
        return base.rule_pct
    if a.size == "half_rule":
        return 0.5 * base.rule_pct
    if a.size == "hold":
        return base.current_pct
    if a.size == "exit":
        return 0.0
    v = _num(a.target_pct_equity)
    if v is None:
        return None
    pf = inp.cfg.policy["portfolio"]
    cap = float(pf[f"max_single_{inp.cfg.asset_class(base.symbol)}_notional"])
    clipped = min(max(v, 0.0), cap)
    if clipped != v:
        notes.append(f"action {base.key}: target_pct_equity {v:.4f} clipped to {clipped:.4f}")
    return clipped


_INELIGIBLE = {
    "A": "sleeve A may only buy its assets and BIL (CL-11)",
    "B": "B increases need a B symbol with close above its 200-day average and a B permission above 0 (CL-11)",
    "C": "new C positions need a name that passes the trend template (C-2) today and a C permission above 0 (CL-11)",
    "D": "D increases need sleeve D enabled, a D symbol and a D permission above 0 (CL-11)",
}


def _action_stop(a, base: ResolvedTarget, increase: bool, inp: _Inputs,
                 notes: list[str]) -> tuple[float | None, str]:
    """Stop menu -> number. Never below the lot's stop (RISK-3); for increases never below the rule stop (CL-14)."""
    if a.sleeve == "A":
        return None, ""
    lot = _lot(inp.lots, a.sleeve, base.symbol)
    menu = stop_menu(a.sleeve, inp.bars.get(base.symbol), inp.cfg.policy, lot)
    choice = a.stop
    if choice == "none":
        notes.append(f"action {base.key}: stop 'none' is for sleeve A only; the rule stop is used")
        choice = "rule"
    stop = _num(menu.get(choice))
    lot_stop = _num(lot.stop) if lot is not None else None
    if lot_stop is not None:
        stop = lot_stop if stop is None else max(stop, lot_stop)
    if not increase:
        return stop, ""
    floor, price = _num(menu["rule"]), inp.price(base.symbol)
    if floor is None:
        return None, "no rule stop can be computed (short or flat history), so no increase (CL-14)"
    if stop is None or stop < floor:
        stop = floor
    if stop >= price:
        return None, "the stop is at or above the price"
    return stop, ""


def _action_why(a, base: ResolvedTarget, pct: float, inp: _Inputs) -> tuple[bool, str]:
    """Checks on one action after sizing. Returns (is_deviation, why dropped or "")."""
    increase = pct > base.current_pct + _TOL
    if increase and base.symbol not in inp.eligible.get(a.sleeve, set()):
        return False, _INELIGIBLE[a.sleeve]
    if not increase and base.current_pct <= _TOL and base.rule_pct <= _TOL:
        return False, "nothing held or planned in this sleeve to change"
    code = a.reason_code
    if code not in ACTION_CODES:
        return False, f"unknown reason code {code}"
    if code in CODE_SLEEVES and a.sleeve not in CODE_SLEEVES[code]:
        return False, f"{code} is only for sleeve(s) {'/'.join(CODE_SLEEVES[code])}"
    ok, why = evidence_ok(inp.ctx, a.evidence)
    if not ok:
        return False, why
    if code == "DATA_SUSPECT" and not _data_suspect_ok(inp.ctx, a.evidence, base.symbol):
        return False, "DATA_SUSPECT must cite data_problems or a price field of this symbol (CL-8)"
    threshold = float(inp.cfg.policy["claude_limits"]["deviation_threshold"])
    dev = a.size == "pct" or is_deviation(pct, base.rule_pct, base.current_pct, threshold)
    if dev and code not in DEVIATION_CODES:
        return dev, f"a deviation from the rule needs a deviation reason code, not {code} (CL-13)"
    if dev:
        pred = inp.preds.get(a.prediction_id) if a.prediction_id else None
        if pred is None:
            return dev, "a deviation needs a prediction_id that matches a kept prediction (CL-13, CL-5)"
        if not _backs(pred, "ACTION", a.sleeve, base.symbol):
            return dev, (f"prediction {a.prediction_id} is about {pred.symbol}, not {base.symbol}, and is not linked "
                         f"to action:{a.sleeve}:{base.symbol} (CL-13, CL-5)")
    return dev, ""


def _resolve_one(a, sym: str, base: ResolvedTarget | None, inp: _Inputs,
                 notes: list[str]) -> tuple[ResolvedTarget | None, str]:
    if sym not in inp.allow:
        return None, "symbol not on the allowlist"
    if base is None:
        return None, "no price for the symbol"
    pct = _size_pct(a, base, inp, notes)
    if pct is None:
        return None, "target_pct_equity is not a number"
    dev, why = _action_why(a, base, pct, inp)
    if why:
        return None, why
    stop, why = _action_stop(a, base, pct > base.current_pct + _TOL, inp, notes)
    if why:
        return None, why
    return replace(base, pct=pct, stop=stop, reason_code=a.reason_code, evidence=list(a.evidence),
                   prediction_id=a.prediction_id or "",
                   rationale=(a.rationale or "").strip()[:500], is_deviation=dev, source="action",
                   sample=inp.sample), ""


def _as_decision(decision: Any, problems: list[str]) -> ClaudeDecision:
    if isinstance(decision, (str, bytes, dict)):
        parsed, found = parse_decision(decision)
        problems.extend(found)
        return parsed
    return decision


def resolve_actions(decision: Any, *, cfg, ctx: Any, rule_targets: Any, lots: dict | None, bars: dict,
                    prices: dict | None, equity: float, permissions: dict | None, sample: int | None = None,
                    weights: dict | None = None, weight_reasons: dict | None = None,
                    eligible: dict | None = None) -> ResolvedDecision:
    """CL-11/CL-13/CL-14/CL-2: one decision -> a target share of equity and a stop for every key.

    Every key in rule targets, held lots and actions starts from the rule (source "rule"). A valid action replaces
    it; an invalid one is dropped with its reason in `problems` and the key follows the rule. Predictions are
    cleaned (CL-5) before deviations are checked against them; a deviation's prediction must be about its symbol
    or name it in linked_decision. New positions Claude opens beyond a sleeve's max_positions (B-1, C-5) are
    dropped, the last actions first. `eligible` (from `eligibility`) may be passed to
    reuse one computation across samples. `weights` / `weight_reasons` (this sample's `resolve_weights` output)
    are carried on the result for consensus. A raw decision (dict or JSON) that is unusable as a whole raises
    DecisionError, and the caller holds.
    """
    problems: list[str] = []
    decision = _as_decision(decision, problems)
    lim = cfg.policy["claude_limits"]
    preds = clean_predictions(decision.predictions, max_n=int(lim["max_predictions_per_day"]),
                              allowlist=cfg.allowlist(), log=problems)
    likely = decision.likely_error.model_copy(update={"note": trim_sentences(decision.likely_error.note, 1)})
    out = ResolvedDecision(weights=dict(weights or {}), targets={}, predictions=preds,
                           weight_reasons=dict(weight_reasons or {}),
                           journal_note=trim_sentences(decision.journal_note, lim["journal_max_sentences"]),
                           market_view=decision.market_view, temperature_ack=decision.temperature_ack,
                           likely_error=likely, flags=list(decision.flags), problems=problems, sample=sample)
    equity_f = _num(equity)
    if equity_f is None or equity_f <= 0:
        problems.append("equity is not positive: no targets, the book holds (stops still enforced)")
        return out
    prices = prices if prices is not None else {s: _close(df) for s, df in bars.items()}
    inp = _Inputs(cfg, ctx, _index_targets(rule_targets, problems), lots or {}, bars, prices, equity_f,
                  eligible if eligible is not None else eligibility(cfg, bars, permissions),
                  {p.id: p for p in preds}, sample, {s.upper() for s in cfg.allowlist()}, problems)

    keys = list(inp.rules) + [f"{s}:{sym}" for s, held in inp.lots.items() for sym in held]
    keys += [f"{a.sleeve}:{a.symbol.strip().upper()}" for a in decision.actions
             if a.symbol.strip().upper() in inp.allow]
    baselines: dict[str, ResolvedTarget] = {}
    for key in dict.fromkeys(keys):
        sleeve, sym = key.split(":", 1)
        base = _baseline(sleeve, sym, inp)
        if base is None:
            problems.append(f"{key}: no price today; left to the risk engine as it is")
        else:
            baselines[key] = out.targets[key] = base

    seen: dict[str, None] = {}  # keys in action order
    for a in decision.actions:
        sym = a.symbol.strip().upper()
        key = f"{a.sleeve}:{sym}"
        if key in seen:
            problems.append(f"action {key}: duplicate, only the first one counts")
            continue
        seen[key] = None
        resolved, why = _resolve_one(a, sym, out.targets.get(key), inp, problems)
        if why:
            problems.append(f"action {key}: dropped ({why}); the rule applies")
        else:
            out.targets[key] = resolved
    limits = max_positions(cfg)
    for key in cap_positions(out.targets, limits, order=seen):
        out.targets[key] = baselines[key]
        s = key.split(":", 1)[0]
        problems.append(f"action {key}: dropped (at most {limits[s]} positions in sleeve {s}, "
                        f"{POSITION_RULES.get(s, 'playbook')}); the rule applies")
    return out


def max_positions(cfg) -> dict[str, int]:
    """B-1 / C-5: the playbook's position limit per sleeve (sleeves without one are not listed)."""
    out = {}
    for s in SLEEVES:
        n = _num((cfg.sleeves.get(s) or {}).get("max_positions"))
        if n is not None:
            out[s] = int(n)
    return out


def _new_by_claude(rt: ResolvedTarget) -> bool:
    """A position neither the book nor the rule has: only a Claude action creates it."""
    return rt.source == "action" and rt.pct > _TOL and rt.current_pct <= _TOL and rt.rule_pct <= _TOL


def cap_positions(targets: dict[str, ResolvedTarget], limits: dict[str, int],
                  order: Iterable[str] | None = None) -> list[str]:
    """B-1 / C-5 for the Claude book: the keys of Claude-made new positions to undo so each sleeve holds at
    most its limit, the last ones in `order` (default: the targets' order) first. Held lots and the rule's own
    entries are never undone (the rule plan already respects the limit); a Claude exit frees a slot."""
    ranked = [k for k in dict.fromkeys(list(order or []) + list(targets)) if k in targets]
    drop = []
    for s, limit in limits.items():
        excess = sum(1 for rt in targets.values() if rt.sleeve == s and rt.pct > _TOL) - limit
        for k in reversed([k for k in ranked if targets[k].sleeve == s and _new_by_claude(targets[k])]):
            if excess <= 0:
                break
            drop.append(k)
            excess -= 1
    return drop


# --- resolved decision -> Targets -------------------------------------------------------------


def _sleeve_rows(items: list[ResolvedTarget], *, lots: dict, prices: dict, equity: float,
                 log: list[str]) -> list[tuple[ResolvedTarget, float, float, float]]:
    """(resolved, qty, current qty, price) for the keys with a price; holds snap to the exact lot quantity."""
    rows = []
    for rt in items:
        price = _num(prices.get(rt.symbol))
        if price is None or price <= 0:
            log.append(f"{rt.sleeve}/{rt.symbol}: no price, left to the risk engine as it is")
            continue
        cur = _qty(_lot(lots, rt.sleeve, rt.symbol))
        pct = _num(rt.pct)
        if pct is None:
            log.append(f"{rt.sleeve}/{rt.symbol}: target share is not a number; held")
            qty = cur
        else:
            qty = max(0.0, pct) * equity / price
        if abs(qty - cur) <= 1e-9 * max(1.0, cur):
            qty = cur
        rows.append((rt, qty, cur, price))
    return rows


def _scale_increases(sleeve: str, rows: list, cap: float, log: list[str]) -> list:
    """Fit the sleeve's notional into its weight by scaling increases only; holds and reductions stay.

    Claude's deviating increases give way first; increases that follow the rule are scaled only when the rule's
    own increases do not fit. Returns (resolved, qty, current qty, price, cut) rows, cut = a non-deviating
    increase was made smaller.
    """
    kept = sum(min(qty, cur) * price for _, qty, cur, price in rows)
    if kept > cap * (1 + 1e-9):
        log.append(f"sleeve {sleeve}: holdings (${kept:,.0f}) are above its weight (${cap:,.0f}); holds are not "
                   "sold, but nothing is added")
    adds_dev = sum(max(0.0, qty - cur) * price for rt, qty, cur, price in rows if rt.is_deviation)
    adds_rule = sum(max(0.0, qty - cur) * price for rt, qty, cur, price in rows if not rt.is_deviation)
    room = max(0.0, cap - kept)
    if adds_dev + adds_rule <= room * (1 + 1e-9):
        return [(*row, False) for row in rows]
    if adds_rule <= room:
        scale_dev, scale_rule = (room - adds_rule) / adds_dev, 1.0
        log.append(f"sleeve {sleeve}: Claude's deviating increases scaled by {scale_dev:.2f} to fit its weight "
                   f"(${cap:,.0f})")
    else:
        scale_dev, scale_rule = 0.0, room / adds_rule
        also = " and Claude's deviating increases by 0" if adds_dev > 0 else ""
        log.append(f"sleeve {sleeve}: increases that follow the rule scaled by {scale_rule:.2f}{also} to fit its "
                   f"weight (${cap:,.0f})")
    out = []
    for rt, qty, cur, price in rows:
        scale = scale_dev if rt.is_deviation else scale_rule
        if qty > cur and scale < 1.0:
            out.append((rt, cur + (qty - cur) * scale, cur, price, not rt.is_deviation))
        else:
            out.append((rt, qty, cur, price, False))
    return out


def _undo_new_positions(resolved: ResolvedDecision, limits: dict | None, log: list[str]) -> dict:
    """B-1 / C-5 again after consensus: combined samples can hold more new names than any one sample did."""
    items = dict(resolved.targets)
    for key in cap_positions(items, limits or {}):
        rt = items[key]
        items[key] = replace(rt, pct=rt.rule_pct, stop=rt.rule_stop, reason_code="FOLLOW_RULE", evidence=[],
                             prediction_id="", rationale="", is_deviation=False, source="rule")
        log.append(f"{rt.sleeve}/{rt.symbol}: new position undone, at most {limits[rt.sleeve]} positions in sleeve "
                   f"{rt.sleeve} ({POSITION_RULES.get(rt.sleeve, 'playbook')}); the rule applies")
    return items


def resolved_to_targets(resolved: ResolvedDecision, *, lots: dict | None, prices: dict, equity: float,
                        weights: dict | None, date: str, log: list[str], position_limits: dict | None = None,
                        deviation_threshold: float = 0.2) -> tuple[list[Target], list[dict]]:
    """Share of equity -> quantity. A sleeve whose total would exceed weights[s] x E has its increases scaled
    down, Claude's deviating ones first (holdings above the weight are logged, never sold).

    `position_limits` (from `max_positions(cfg)`) undoes Claude-made new positions over B-1 / C-5.
    Returns the Targets (reason "claude <CODE>: ..." or "rule: ...") and one deviation record per
    `is_deviation` target (CL-13, M-5): {date, symbol, sleeve, rule_pct, claude_pct, reason_code, evidence,
    prediction_id}. A target that followed the rule but was cut to fit the weight by more than
    `deviation_threshold` gets a record with reason_code WEIGHT_CAP, so M-5 sees every gap from the rule.
    """
    equity_f = _num(equity)
    if equity_f is None or equity_f <= 0:
        log.append("equity is not positive: no Claude targets")
        return [], []
    items = _undo_new_positions(resolved, position_limits, log)
    targets, deviations = [], []
    for s in SLEEVES:
        rows = _sleeve_rows([rt for rt in items.values() if rt.sleeve == s], lots=lots or {}, prices=prices,
                            equity=equity_f, log=log)
        cap = max(0.0, _num((weights or {}).get(s)) or 0.0) * equity_f
        for rt, qty, _, price, cut in _scale_increases(s, rows, cap, log):
            if rt.source == "action":
                reason = f"claude {rt.reason_code}: {rt.rationale[:160]}".rstrip(": ")
            else:
                reason = f"rule: {rt.rationale or 'follow the rule'}"
            final_pct = qty * price / equity_f
            if cut:
                reason += " (cut to fit the sleeve weight)"
            targets.append(Target(rt.symbol, s, qty, rt.stop, reason))
            if rt.is_deviation:
                code, evidence, pid = rt.reason_code, list(rt.evidence), rt.prediction_id
            elif cut and is_deviation(final_pct, rt.rule_pct, rt.current_pct, deviation_threshold):
                code, evidence, pid = WEIGHT_CAP_CODE, [], ""
            else:
                continue
            deviations.append({"date": date, "symbol": rt.symbol, "sleeve": s, "rule_pct": round(rt.rule_pct, 6),
                               "claude_pct": round(final_pct, 6), "reason_code": code, "evidence": evidence,
                               "prediction_id": pid})
    return targets, deviations
