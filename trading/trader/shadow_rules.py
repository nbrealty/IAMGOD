"""TEST FIRST rules as shadow signals (rulebook status TEST FIRST; promotion needs gate M-12).

Each `shadow_*` function reads today's bars, plans and lots and says what its rule *would* have done.
Nothing here changes a target, a lot, a weight or an order: results go to `plan.shadow` and the journal,
and M-12 (v) later asks whether at least 30 live shadow signals agree with the backtest.

Every result is a small JSON-safe dict:

    {"rule": "C-11", "fires": bool, "detail": {...}, "would_change": [...]}

`would_change` lists the concrete differences from what the live rules do today, one small dict each
(usually `{"sleeve", "symbol", "action", ...}`). `fires` is True exactly when that list is not empty.
Missing data never raises: the result is `{"fires": False, "detail": {"skipped": "why"}}`.

Exit rules (C-10, C-15, C-16, D-5) replay the bars since the entry, so the shadow position remembers what
already happened to it. Each exit is reported once, as `action: "exit"` on the day it happens; while the live
book still holds the lot afterwards, it is listed under `detail["exited_earlier"]` with its date instead, so
M-12 (v) counts each lot once and later days never contradict the first signal.
"""
from __future__ import annotations

import functools
import math
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

from . import indicators as ind
from . import strategies as strat
from .models import Lot, SleevePlan, Target
from .regime import PERMISSIONS

TINY = 1e-9
WEIGHT_TOL = 1e-4  # 0.01% of equity: smaller weight gaps are rounding (equity stored to the cent), not a signal


class Skip(Exception):
    """Raised inside a shadow function when an input it needs is missing."""


@dataclass
class ShadowInputs:
    """Everything a shadow rule may read. Never written to."""

    bars: dict = field(default_factory=dict)
    cfg: Any = None
    plans: dict = field(default_factory=dict)
    lots: dict = field(default_factory=dict)  # sleeve -> symbol -> Lot
    regime: Any = None
    as_of: Any = None
    state: Any = None
    weights: dict | None = None  # sleeve weights (fractions of equity), when the caller knows them
    equity: float | None = None

    def __post_init__(self) -> None:
        self.bars = self.bars or {}
        self.plans = self.plans or {}
        self.lots = self.lots or {}
        self.as_of = pd.Timestamp(self.as_of).normalize() if self.as_of is not None else None


# --- small helpers ---------------------------------------------------------------------------------


def _r(x, nd: int = 4) -> float | None:
    """Round for the log; NaN, inf and None become None."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return round(f, nd) if math.isfinite(f) else None


def _nan(x) -> bool:
    return x is None or (isinstance(x, (float, np.floating)) and not math.isfinite(float(x)))


def _clean(obj):
    """Make a result JSON-safe: plain Python types, NaN -> None, dates -> ISO strings."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return f if math.isfinite(f) else None
    if isinstance(obj, pd.Timestamp):
        return obj.date().isoformat()
    if obj is None or isinstance(obj, str):
        return obj
    return str(obj)


def _rget(obj, name: str, default=None):
    """Read a field from a Regime object or a plain dict."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _df(inp: ShadowInputs, sym: str, min_len: int = 1) -> pd.DataFrame:
    """Bars for `sym` up to as_of, or Skip when missing or too short."""
    df = inp.bars.get(sym)
    if df is None or len(df) == 0:
        raise Skip(f"no bars for {sym}")
    if inp.as_of is not None:
        df = df[df.index <= inp.as_of]
    if len(df) < min_len:
        raise Skip(f"{sym}: {len(df)} bars, need {min_len}")
    if _nan(df["close"].iloc[-1]):
        raise Skip(f"{sym}: last close missing")
    return df


def _try_df(inp: ShadowInputs, sym: str, min_len: int, skipped: list) -> pd.DataFrame | None:
    """Like _df but records the problem and returns None, for rules that look at many symbols."""
    try:
        return _df(inp, sym, min_len)
    except Skip as e:
        skipped.append(str(e))
        return None


def _close(df: pd.DataFrame) -> float:
    return float(df["close"].iloc[-1])


def _as_lot(lot) -> Lot:
    return lot if isinstance(lot, Lot) else Lot.from_dict(lot)


def _lot_qty(lot) -> float:
    """A lot's quantity, read even from a lot too broken to rebuild (0 when unreadable)."""
    try:
        q = float(lot.get("qty") if isinstance(lot, dict) else lot.qty)
    except (AttributeError, TypeError, ValueError):
        return 0.0
    return q if math.isfinite(q) else 0.0


def _held(inp: ShadowInputs, sleeve: str, skipped: list | None = None) -> dict[str, Lot]:
    """Open lots of one sleeve (qty > 0). A lot without a usable entry date or price is left out (and noted
    in `skipped`), so one bad lot never switches off a rule for the others."""
    out = {}
    for sym, raw in (inp.lots.get(sleeve) or {}).items():
        if _lot_qty(raw) <= TINY:
            continue
        try:
            lot = _as_lot(raw)
            if pd.isna(pd.Timestamp(lot.entry_date)) or _nan(float(lot.entry_price)):
                raise ValueError("entry date or price missing")
        except Exception as e:  # old or corrupted state
            if skipped is not None:
                skipped.append(f"{sym}: unusable lot ({type(e).__name__}: {e})")
            continue
        out[sym] = lot
    return out


def _held_syms(inp: ShadowInputs, sleeve: str) -> set[str]:
    """Symbols the sleeve holds, broken lots included (a held name is never a new entry)."""
    return {sym for sym, lot in (inp.lots.get(sleeve) or {}).items() if _lot_qty(lot) > TINY}


def _cur_qty(inp: ShadowInputs, sleeve: str, sym: str) -> float:
    lot = (inp.lots.get(sleeve) or {}).get(sym)
    return _lot_qty(lot) if lot is not None else 0.0


def _plan(inp: ShadowInputs, sleeve: str) -> SleevePlan:
    plan = inp.plans.get(sleeve)
    if plan is None:
        raise Skip(f"no sleeve {sleeve} plan today")
    return plan


def _entries(inp: ShadowInputs, sleeve: str) -> list[tuple[str, Target]]:
    """Today's new positions in a sleeve: a target above zero where the sleeve holds nothing."""
    plan = inp.plans.get(sleeve)
    if plan is None:
        return []
    return [(sym, t) for sym, t in plan.targets.items() if t.qty > TINY and _cur_qty(inp, sleeve, sym) <= TINY]


def _live_holds(inp: ShadowInputs, sleeve: str, sym: str) -> bool:
    """True when the live plan keeps the position today (no exit)."""
    plan = inp.plans.get(sleeve)
    t = plan.targets.get(sym) if plan is not None else None
    return t.qty > TINY if t is not None else _cur_qty(inp, sleeve, sym) > TINY


def _candidate(inp: ShadowInputs, sleeve: str, sym: str) -> dict | None:
    plan = inp.plans.get(sleeve)
    for c in plan.candidates if plan is not None else []:
        if c.get("symbol") == sym:
            return c
    return None


def _perm(inp: ShadowInputs, sleeve: str) -> float:
    perms = _rget(inp.regime, "permissions")
    if not perms:
        raise Skip("regime permissions unknown")
    return float(perms.get(sleeve, 0.0))


def _positive(x) -> float | None:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) and f > 0 else None


def _equity(inp: ShadowInputs) -> float | None:
    if _positive(inp.equity):
        return float(inp.equity)
    hist = getattr(inp.state, "equity_history", None) if inp.state is not None else None
    if hist and isinstance(hist[-1], dict) and _positive(hist[-1].get("equity")):
        return float(hist[-1]["equity"])
    for s, w in (inp.weights or {}).items():
        if _positive(w) and s in inp.plans:
            return float(inp.plans[s].capital / w)
    return None


def _weights(inp: ShadowInputs) -> dict[str, float] | None:
    if inp.weights:
        return {s: float(w) for s, w in inp.weights.items() if not _nan(w)}
    e = _equity(inp)
    if not e:
        return None
    return {s: float(p.capital / e) for s, p in inp.plans.items()}


def _rescaled_qty(inp: ShadowInputs, sleeve: str, sym: str, t: Target, factor: float) -> tuple[float, bool]:
    """Entry size if the sleeve's risk budget were multiplied by `factor` (B-3 / C-6 sizing).

    Exact when equity is known: min(factor x 1R x E x perm / (close - stop), notional cap), with 1R from
    `strategies.risk_pct`, the same source the live sleeves size with. Otherwise approximate:
    min(live qty x factor, notional cap). Returns (qty, approximate?).
    """
    try:
        close = _close(_df(inp, sym))
    except Skip:
        return t.qty * factor, True
    plan = inp.plans[sleeve]
    max_pos = inp.cfg.sleeves[sleeve].get("max_positions") or 1
    cap_qty = plan.capital / max_pos / close
    e, perm = _equity(inp), _perm(inp, sleeve)
    if e and perm > 0 and t.stop is not None and close > t.stop:
        risk_qty = strat.risk_pct(inp.cfg.policy, sleeve) * e * perm / (close - t.stop)
        return min(risk_qty * factor, cap_qty), False
    return min(t.qty * factor, cap_qty), True


def _resize_change(inp: ShadowInputs, sleeve: str, sym: str, t: Target, factor: float, action: str,
                   **extra) -> dict | None:
    qty, approx = _rescaled_qty(inp, sleeve, sym, t, factor)
    if abs(qty - t.qty) <= 1e-6 * max(1.0, t.qty):
        return None
    return {"sleeve": sleeve, "symbol": sym, "action": action, "qty_from": _r(t.qty, 6), "qty_to": _r(qty, 6),
            "approx": approx, **extra}


def _r12_monthly(inp: ShadowInputs, sym: str) -> float:
    """12-month return on completed month-end closes (NaN when missing or short)."""
    try:
        df = _df(inp, sym)
    except Skip:
        return float("nan")
    m = ind.completed_month_closes(df["close"], inp.as_of)
    return float(m.iloc[-1] / m.iloc[-13] - 1) if len(m) >= 13 else float("nan")


def _rps(lot: Lot) -> float | None:
    """Risk per share of a lot (1R), from its bookkeeping or its initial stop."""
    rps = lot.risk_per_share
    if rps is None and lot.initial_stop is not None and lot.entry_price > lot.initial_stop:
        rps = lot.entry_price - lot.initial_stop
    return rps if rps and rps > 0 else None


def _first(index: pd.Index):
    return index[0] if len(index) else None


def _exit_once(inp: ShadowInputs, sleeve: str, sym: str, df: pd.DataFrame, exit_on, why: str,
               changes: list, earlier: list) -> bool:
    """Report a shadow exit once: as a change on its own day (when the live plan still holds), else under
    `exited_earlier` with its date. Returns True when the shadow position is closed by today."""
    if exit_on is None:
        return False
    if exit_on < df.index[-1]:
        earlier.append({"sleeve": sleeve, "symbol": sym, "exit_date": exit_on, "why": why})
    elif _live_holds(inp, sleeve, sym):
        changes.append({"sleeve": sleeve, "symbol": sym, "action": "exit", "why": why})
    return True


def _finish(detail: dict, skipped: list, earlier: list) -> dict:
    if earlier:
        detail["exited_earlier"] = earlier
    if skipped:
        detail["skipped_symbols"] = skipped
    return detail


def _live_c_stop(lot: Lot, df: pd.DataFrame, n: int) -> float | None:
    """The stop risk.py enforces for a C lot today: max(stop, lowest low of the prior n sessions) (C-7)."""
    low_n = float(df["low"].iloc[-n - 1:-1].min()) if len(df) > n else float("nan")
    stops = [s for s in (lot.stop, low_n) if not _nan(s)]
    return max(stops) if stops else None


def _faber_rows(inp: ShadowInputs, symbols: list[str]) -> dict[str, dict]:
    vt = inp.cfg.policy["portfolio"]["vol_target_annual"]
    return {s: strat.faber_asset(_df(inp, s)["close"], inp.as_of, vt) for s in symbols}


def _weight_changes(live: dict[str, float], shadow: dict[str, float], cash: str, tol: float = 1e-3) -> list:
    """Sleeve A weight differences (fractions of the sleeve), plus the cash remainder."""
    out = []
    for sym in dict.fromkeys(list(live) + list(shadow)):
        a, b = live.get(sym, 0.0), shadow.get(sym, 0.0)
        if abs(a - b) > tol:
            out.append({"sleeve": "A", "symbol": sym, "action": "reweight", "weight_from": _r(a),
                        "weight_to": _r(b)})
    cash_live, cash_shadow = max(0.0, 1 - sum(live.values())), max(0.0, 1 - sum(shadow.values()))
    if abs(cash_live - cash_shadow) > tol:
        out.append({"sleeve": "A", "symbol": cash, "action": "reweight", "weight_from": _r(cash_live),
                    "weight_to": _r(cash_shadow)})
    return out


def _faber_fraction(inp: ShadowInputs) -> float:
    return 0.5 if inp.cfg.sleeves["A"].get("gem_blend") else 1.0


def _skipped(rule_id: str, why: str) -> dict:
    return {"rule": rule_id, "fires": False, "detail": {"skipped": why}, "would_change": []}


def _rule(rule_id: str) -> Callable:
    """Wrap a shadow function: build the result dict and turn any failure into a 'skipped' result.

    The wrapped function returns (detail, would_change). It may be called with a ShadowInputs or with the
    same arguments as `compute`.
    """
    def wrap(fn):
        @functools.wraps(fn)
        def run(*args, **kwargs) -> dict:
            if len(args) == 1 and not kwargs and isinstance(args[0], ShadowInputs):
                inp = args[0]
            else:
                inp = ShadowInputs(*args, **kwargs)
            try:
                detail, changes = fn(inp)
            except Skip as e:
                return _skipped(rule_id, str(e))
            except Exception as e:  # a shadow signal must never stop a trading run
                return _skipped(rule_id, f"error: {type(e).__name__}: {e}")
            return _clean({"rule": rule_id, "fires": bool(changes), "detail": detail, "would_change": changes})
        run.rule_id = rule_id
        return run
    return wrap


# --- (a) regime --------------------------------------------------------------------------------------


@_rule("REG-5")
def shadow_reg5(inp: ShadowInputs):
    """REG-5 hot cap: when temperature T >= hot (0.80), B and C weights are capped at their default.
    Prefers the caller's final `weights`; otherwise plan capital / equity, where a gap under WEIGHT_TOL is
    rounding, not a weight above default."""
    t = _rget(inp.regime, "temperature")
    if _nan(t):
        raise Skip("temperature unknown")
    hot = float(inp.cfg.playbook["regime"].get("hot", 0.80))
    detail = {"temperature": _r(t, 3), "hot": hot, "is_hot": float(t) >= hot}
    changes = []
    if float(t) >= hot:
        weights = _weights(inp)
        if weights is None:
            detail["note"] = "sleeve weights unknown"
        for s in ("B", "C"):
            w, cap = (weights or {}).get(s), float(inp.cfg.sleeves[s]["default"])
            if w is not None and w - cap > WEIGHT_TOL:
                changes.append({"sleeve": s, "action": "cap weight", "weight_from": _r(w), "weight_to": cap})
    return detail, changes


@_rule("REG-6")
def shadow_reg6(inp: ShadowInputs):
    """REG-6 credit canary: 13612W(HYG) - 13612W(IEF) < 0 on month-end closes turns bull_calm into
    bull_volatile (B, C and D permissions 1 -> 0.5)."""
    hyg, ief = (list(inp.cfg.playbook["regime"].get("credit") or []) + ["HYG", "IEF"])[:2]
    scores = {s: ind.momentum_13612w(ind.completed_month_closes(_df(inp, s)["close"], inp.as_of))
              for s in (hyg, ief)}
    if any(_nan(v) for v in scores.values()):
        raise Skip(f"need 13 completed month-ends of {hyg} and {ief}")
    spread = scores[hyg] - scores[ief]
    label = _rget(inp.regime, "label")
    downgrade = spread < 0 and label == "bull_calm"
    detail = {f"{hyg.lower()}_13612w": _r(scores[hyg]), f"{ief.lower()}_13612w": _r(scores[ief]),
              "spread": _r(spread), "credit_weak": spread < 0, "label": label,
              "shadow_label": "bull_volatile" if downgrade else label}
    changes: list[dict] = []
    if not downgrade:
        return detail, changes
    changes.append({"action": "regime label", "from": label, "to": "bull_volatile"})
    new = PERMISSIONS["bull_volatile"]
    for s in ("B", "C", "D"):
        if s not in inp.plans:
            continue
        old = _perm(inp, s)
        if old <= 0 or abs(new[s] - old) <= TINY:
            continue
        factor = new[s] / old
        changes.append({"sleeve": s, "action": "permission", "from": old, "to": new[s]})
        if s == "D":  # D sizes by weight, so the whole target scales
            for sym, t in inp.plans["D"].targets.items():
                if t.qty > TINY:
                    changes.append({"sleeve": "D", "symbol": sym, "action": "scale target",
                                    "qty_from": _r(t.qty, 6), "qty_to": _r(t.qty * factor, 6)})
            continue
        for sym, t in _entries(inp, s):
            ch = _resize_change(inp, s, sym, t, factor, "smaller entry")
            if ch:
                changes.append(ch)
    return detail, changes


# --- (b) sleeve A ------------------------------------------------------------------------------------


@_rule("A-6")
def shadow_a6(inp: ShadowInputs):
    """A-6 shadow GEM: US leg held in VOO; the bond leg is AGG only if AGG's 12-month return beats BIL's,
    else BIL. Blended 50/50 with the Faber legs (GEM itself stays off)."""
    gem = inp.cfg.sleeves["A"].get("gem", {})
    us, intl = "VOO", gem.get("intl", "VEU")
    bonds, tbill = gem.get("bonds", "AGG"), gem.get("tbill", "BIL")
    r = {s: _r12_monthly(inp, s) for s in dict.fromkeys((us, gem.get("us", "SPY"), intl, bonds, tbill))}
    if _nan(r[us]) or _nan(r[tbill]):
        raise Skip(f"need 13 completed month-ends of {us} and {tbill}")
    if r[us] > r[tbill]:
        pick = us if _nan(r[intl]) or r[us] >= r[intl] else intl
    else:
        pick = bonds if not _nan(r[bonds]) and r[bonds] > r[tbill] else tbill
    plain = _plain_gem(r, gem)
    detail = {"r12": {s: _r(v) for s, v in r.items()}, "pick": pick, "plain_gem_pick": plain,
              "gem_blend_live": bool(inp.cfg.sleeves["A"].get("gem_blend"))}
    same_as_live = detail["gem_blend_live"] and _same_asset(pick, plain, gem)
    if same_as_live:
        return detail, []
    changes = [{"sleeve": "A", "symbol": pick, "action": "hold GEM leg", "weight_in_sleeve": 0.5}]
    if not detail["gem_blend_live"]:
        changes.append({"sleeve": "A", "action": "scale Faber legs", "factor": 0.5})
    return detail, changes


def _plain_gem(r: dict, gem: dict) -> str | None:
    """The configured GEM rule (strategies.gem_pick) on the same 12-month returns, for comparison."""
    us, intl, bonds, tbill = (gem.get(k) for k in ("us", "intl", "bonds", "tbill"))
    ru, rt = r.get(us, float("nan")), r.get(tbill, float("nan"))
    if _nan(ru) or _nan(rt) or ru <= rt:
        return bonds
    ri = r.get(intl, float("nan"))
    return us if _nan(ri) or ru >= ri else intl


def _same_asset(a: str, b: str | None, gem: dict) -> bool:
    us = gem.get("us", "SPY")
    norm = {us: "VOO"}
    return norm.get(a, a) == norm.get(b, b)


@_rule("A-7")
def shadow_a7(inp: ShadowInputs):
    """A-7 second vote: w_i = 1/5 x scale_i x (0.5 [close > SMA10m] + 0.5 [r12_i > r12_BIL])."""
    a = inp.cfg.sleeves["A"]
    r_cash = _r12_monthly(inp, a["cash"])
    if _nan(r_cash):
        raise Skip(f"need 13 completed month-ends of {a['cash']}")
    rows, share, ff = _faber_rows(inp, a["assets"]), 1.0 / len(a["assets"]), _faber_fraction(inp)
    live, shadow, votes = {}, {}, {}
    for sym, row in rows.items():
        r12 = _r12_monthly(inp, sym)
        vote2 = not _nan(r12) and r12 > r_cash  # unknown r12 counts as a "no" vote (less exposure)
        live[sym] = ff * share * row["scale"] * (1.0 if row["in"] else 0.0)
        shadow[sym] = ff * share * row["scale"] * (0.5 * row["in"] + 0.5 * vote2)
        votes[sym] = {"above_10m_sma": bool(row["in"]), "r12": _r(r12), "beats_cash": bool(vote2)}
    detail = {"cash_r12": _r(r_cash), "votes": votes}
    return detail, _weight_changes(live, shadow, a["cash"])


@_rule("A-8")
def shadow_a8(inp: ShadowInputs):
    """A-8: vol-target the whole sleeve at 10% (60-session covariance of the held assets) instead of
    scaling each ETF on its own."""
    a = inp.cfg.sleeves["A"]
    vt = inp.cfg.policy["portfolio"]["vol_target_annual"]
    rows, share, ff = _faber_rows(inp, a["assets"]), 1.0 / len(a["assets"]), _faber_fraction(inp)
    live = {s: ff * share * row["scale"] * (1.0 if row["in"] else 0.0) for s, row in rows.items()}
    held = [s for s, row in rows.items() if row["in"]]
    if not held:
        return {"held": [], "note": "no A asset above its 10-month SMA"}, []
    rets = _month_end_returns(inp, held)
    if len(rets) < 60:
        raise Skip(f"need 60 sessions of returns for {', '.join(held)}")
    cov = rets.iloc[-60:].cov().to_numpy() * 252
    w = np.full(len(held), share)
    vol_p = float(np.sqrt(w @ cov @ w))
    scale = min(1.0, vt / vol_p) if vol_p > 0 else 1.0
    shadow = {s: ff * share * scale if s in held else 0.0 for s in rows}
    detail = {"held": held, "sleeve_vol": _r(vol_p), "scale": _r(scale), "vol_target": vt}
    return detail, _weight_changes(live, shadow, a["cash"])


def _month_end_returns(inp: ShadowInputs, symbols: list[str]) -> pd.DataFrame:
    """Aligned daily log returns up to the last completed month-end shared by all symbols (as A-3)."""
    cols, cutoff = {}, None
    for s in symbols:
        close = _df(inp, s)["close"]
        me = ind.completed_month_closes(close, inp.as_of).index
        if len(me):
            cutoff = me[-1] if cutoff is None else min(cutoff, me[-1])
        cols[s] = np.log(close).diff()
    rets = pd.concat(cols, axis=1, sort=True).dropna()
    return rets[rets.index <= cutoff] if cutoff is not None else rets


@_rule("A-9")
def shadow_a9(inp: ShadowInputs):
    """A-9: GLD as a sixth asset under A-2 and A-3 (each asset 1/6 of the sleeve)."""
    a = inp.cfg.sleeves["A"]
    gld = "GLD"
    rows = _faber_rows(inp, list(a["assets"]) + [gld])
    ff = _faber_fraction(inp)
    live_share, shadow_share = 1.0 / len(a["assets"]), 1.0 / (len(a["assets"]) + 1)
    live = {s: ff * live_share * r["scale"] * (1.0 if r["in"] else 0.0) for s, r in rows.items() if s != gld}
    shadow = {s: ff * shadow_share * r["scale"] * (1.0 if r["in"] else 0.0) for s, r in rows.items()}
    g = rows[gld]
    detail = {"gld_above_10m_sma": bool(g["in"]), "gld_month_close": _r(g["month_close"], 2),
              "gld_sma10m": _r(g["sma10m"], 2), "gld_scale": _r(g["scale"])}
    return detail, _weight_changes(live, shadow, a["cash"])


# --- (b) sleeve B ------------------------------------------------------------------------------------


@_rule("B-7")
def shadow_b7(inp: ShadowInputs):
    """B-7: B trades as market-on-close orders from a 15:45 ET run instead of next-open market orders."""
    plan = _plan(inp, "B")
    changes = []
    for sym, t in plan.targets.items():
        delta = t.qty - _cur_qty(inp, "B", sym)
        if abs(delta) <= TINY:
            continue
        try:
            close = _close(_df(inp, sym))
        except Skip:
            close = None
        side = "buy" if delta > 0 else "sell"
        changes.append({"sleeve": "B", "symbol": sym, "action": f"{side} market-on-close", "qty": _r(abs(delta), 6),
                        "price": _r(close)})
    detail = {"trades": len(changes),
              "note": "daily bars only: the official close stands in for the 15:45 IEX proxy; "
                      "compare with the next open (B-6 gap_R) to score it"}
    return detail, changes


def _exit_b_variant(df: pd.DataFrame, lot: Lot, *, time_stop: int | None, rsi_exit: float | None = None):
    """B-4 with one part swapped (B-8). None means hold."""
    close = _close(df)
    if rsi_exit is None:
        if close > strat._last(ind.sma(df["close"], 5)):
            return "close above 5-day SMA"
    else:
        rsi2 = strat._last(ind.rsi(df["close"], 2))
        if rsi2 > rsi_exit:
            return f"RSI2 {rsi2:.0f} > {rsi_exit:.0f}"
    held = strat._bars_held(df, lot.entry_date)
    if time_stop is not None and held >= time_stop:
        return f"time stop after {held} sessions"
    if lot.stop is not None and close <= lot.stop:
        return "disaster stop"
    return None


@_rule("B-8")
def shadow_b8(inp: ShadowInputs):
    """B-8 variants, each alone: exit on RSI2 > 70 instead of close > SMA5; time stop off; time stop 15
    sessions; full size only when RSI2 < 5 (half size for 5 to 10)."""
    time_stop = inp.cfg.policy["per_trade"]["time_stop_days"]["B"]
    variants = {"rsi2_exit_70": {"time_stop": time_stop, "rsi_exit": 70.0},
                "time_stop_off": {"time_stop": None}, "time_stop_15": {"time_stop": 15}}
    changes, skipped, counts = [], [], dict.fromkeys(list(variants) + ["size_by_rsi2"], 0)
    for sym, lot in _held(inp, "B", skipped).items():
        df = _try_df(inp, sym, 6, skipped)
        if df is None:
            continue
        live = strat.exit_b(df, lot.stop, lot.entry_date, time_stop)
        for name, kw in variants.items():
            alt = _exit_b_variant(df, lot, **kw)
            if (alt is None) != (live is None):
                counts[name] += 1
                changes.append({"variant": name, "sleeve": "B", "symbol": sym, "action": "exit" if alt else "hold",
                                "why": alt or f"live rule exits ({live})"})
    for sym, t in _entries(inp, "B"):
        df = _try_df(inp, sym, 3, skipped)
        if df is None:
            continue
        rsi2 = strat._last(ind.rsi(df["close"], 2))
        if not _nan(rsi2) and rsi2 >= 5:
            counts["size_by_rsi2"] += 1
            changes.append({"variant": "size_by_rsi2", "sleeve": "B", "symbol": sym, "action": "half size",
                            "rsi2": _r(rsi2, 1), "qty_from": _r(t.qty, 6), "qty_to": _r(t.qty / 2, 6)})
    detail = {"changes_by_variant": counts}
    if skipped:
        detail["skipped_symbols"] = skipped
    return detail, changes


@_rule("B-9")
def shadow_b9(inp: ShadowInputs):
    """B-9: in bull_volatile (SPY above its SMA200), B runs at full permission instead of half. Tested
    against a gate that keeps full permission only while SPY vol20 < 25%."""
    label, vol20 = _rget(inp.regime, "label"), _rget(inp.regime, "vol20")
    spy, sma = _rget(inp.regime, "spy_close"), _rget(inp.regime, "spy_sma200")
    spy_above = not _nan(spy) and not _nan(sma) and float(spy) > float(sma)
    detail = {"label": label, "spy_above_sma200": spy_above, "vol20": _r(vol20)}
    if label != "bull_volatile":
        return detail, []
    perm = _perm(inp, "B")
    if perm <= 0 or not spy_above:
        return detail, []
    full = {"no_halving": True, "vol20_gate_25": not _nan(vol20) and float(vol20) < 0.25}
    changes = []
    for name, on in full.items():
        if not on or perm >= 1.0:
            continue
        changes.append({"variant": name, "sleeve": "B", "action": "permission", "from": perm, "to": 1.0})
        for sym, t in _entries(inp, "B"):
            ch = _resize_change(inp, "B", sym, t, 1.0 / perm, "larger entry", variant=name)
            if ch:
                changes.append(ch)
    return detail, changes


@_rule("B-10")
def shadow_b10(inp: ShadowInputs):
    """B-10: one extra entry trigger sharing B's slots, each tested alone: 2-day cumulative RSI2 < 35, or
    Double 7s (close at a 7-session low). Both need close > SMA200 and permission > 0."""
    plan = _plan(inp, "B")
    bcfg = inp.cfg.sleeves["B"]
    perm = _perm(inp, "B")
    slots = max(0, bcfg["max_positions"] - sum(1 for t in plan.targets.values() if t.qty > TINY))
    detail: dict = {"open_slots": slots, "permission": perm}
    if perm <= 0:
        detail["note"] = "regime gate: B entries off"
        return detail, []
    busy = set(plan.targets) | _held_syms(inp, "B")
    skipped: list[str] = []
    triggers: dict[str, list] = {"cum_rsi2_35": [], "double_7s": []}
    for sym in bcfg["symbols"]:
        if sym in busy:
            continue
        df = _try_df(inp, sym, 200, skipped)
        if df is None:
            continue
        close = df["close"]
        if not _close(df) > strat._last(ind.sma(close, 200)):
            continue
        rsi2 = ind.rsi(close, 2).dropna()
        if len(rsi2) >= 2 and rsi2.iloc[-1] + rsi2.iloc[-2] < 35:
            triggers["cum_rsi2_35"].append((float(rsi2.iloc[-1] + rsi2.iloc[-2]), sym))
        if len(close) >= 7 and close.iloc[-1] <= close.iloc[-7:].min():
            triggers["double_7s"].append((float(rsi2.iloc[-1]) if len(rsi2) else 50.0, sym))
    changes = []
    for name, found in triggers.items():
        for score, sym in sorted(found)[:slots]:
            changes.append({"variant": name, "sleeve": "B", "symbol": sym, "action": "enter",
                            "why": f"{name} (score {score:.1f})"})
    detail["triggered"] = {name: [s for _, s in sorted(found)] for name, found in triggers.items()}
    if skipped:
        detail["skipped_symbols"] = skipped
    return detail, changes


# --- (b) sleeve C ------------------------------------------------------------------------------------


def _pivot(inp: ShadowInputs, sym: str, df: pd.DataFrame) -> float:
    """C-4 pivot: from today's candidate snapshot, else the prior `pivot_lookback` sessions' high."""
    c = _candidate(inp, "C", sym)
    if c and not _nan(c.get("pivot")):
        return float(c["pivot"])
    n = inp.cfg.sleeves["C"]["pivot_lookback"]
    if len(df) < n + 1:
        raise Skip(f"{sym}: need {n + 1} bars for the pivot")
    return float(df["high"].iloc[-n - 1:-1].max())


@_rule("C-10")
def shadow_c10(inp: ShadowInputs):
    """C-10 failed breakout: the first close below the entry pivot within sessions 1 to 10 exits."""
    n = inp.cfg.sleeves["C"]["pivot_lookback"]
    checked, changes, skipped, earlier = [], [], [], []
    for sym, lot in _held(inp, "C", skipped).items():
        df = _try_df(inp, sym, 2, skipped)
        if df is None:
            continue
        entry = pd.Timestamp(lot.entry_date)
        pre, first10 = df[df.index <= entry], df[df.index > entry].iloc[:10]
        if len(pre) < n + 1:
            skipped.append(f"{sym}: need {n + 1} bars before the entry for the pivot")
            continue
        pivot = float(pre["high"].iloc[-n - 1:-1].max())
        exit_on = _first(first10.index[first10["close"] < pivot])
        held = strat._bars_held(df, lot.entry_date)
        if held > 10 and exit_on is None:
            continue  # passed its first 10 sessions: C-10 is done with this lot
        checked.append({"symbol": sym, "sessions_held": held, "pivot": _r(pivot, 2), "close": _r(_close(df), 2)})
        if exit_on is not None:
            session = int((first10.index <= exit_on).sum())
            why = f"close {float(df.at[exit_on, 'close']):.2f} below pivot {pivot:.2f} on session {session}"
            _exit_once(inp, "C", sym, df, exit_on, why, changes, earlier)
    return _finish({"checked": checked}, skipped, earlier), changes


@_rule("C-11")
def shadow_c11(inp: ShadowInputs):
    """C-11 extension: skip a breakout entry when close > 1.05 x pivot."""
    checked, changes, skipped = [], [], []
    for sym, _t in _entries(inp, "C"):
        df = _try_df(inp, sym, 1, skipped)
        if df is None:
            continue
        try:
            pivot = _pivot(inp, sym, df)
        except Skip as e:
            skipped.append(str(e))
            continue
        close = _close(df)
        ext = close / pivot - 1 if pivot > 0 else float("nan")
        checked.append({"symbol": sym, "pivot": _r(pivot, 2), "close": _r(close, 2), "extension": _r(ext)})
        if pivot > 0 and close > 1.05 * pivot:
            changes.append({"sleeve": "C", "symbol": sym, "action": "skip entry",
                            "why": f"close {ext:.1%} above the pivot (limit 5%)"})
    detail: dict = {"checked": checked}
    if skipped:
        detail["skipped_symbols"] = skipped
    return detail, changes


@_rule("C-12")
def shadow_c12(inp: ShadowInputs):
    """C-12 stricter template: close >= 1.30 x the 52-week low, and SMA200 above its value 84 sessions ago."""
    checked, changes, skipped = [], [], []
    for sym, _t in _entries(inp, "C"):
        df = _try_df(inp, sym, 200 + 85, skipped)
        if df is None:
            continue
        close, lo52 = _close(df), float(df["low"].iloc[-252:].min())
        s200 = ind.sma(df["close"], 200).dropna()
        rising84 = len(s200) > 84 and bool(s200.iloc[-1] > s200.iloc[-85])
        above_130 = close >= 1.30 * lo52
        checked.append({"symbol": sym, "above_1_30x_52w_low": above_130, "sma200_rising_84": rising84})
        if not (above_130 and rising84):
            failed = [k for k, ok in (("close < 1.30 x 52-week low", above_130),
                                      ("SMA200 not rising over 84 sessions", rising84)) if not ok]
            changes.append({"sleeve": "C", "symbol": sym, "action": "skip entry", "why": "; ".join(failed)})
    detail: dict = {"checked": checked}
    if skipped:
        detail["skipped_symbols"] = skipped
    return detail, changes


def _c_breakout(inp: ShadowInputs, sym: str, df: pd.DataFrame) -> bool:
    """C-4 trigger today (from the candidate snapshot when there is one)."""
    c = _candidate(inp, "C", sym)
    if c and "breakout_today" in c:
        return bool(c["breakout_today"])
    ccfg = inp.cfg.sleeves["C"]
    n = ccfg["pivot_lookback"]
    pivot = float(df["high"].iloc[-n - 1:-1].max())
    vol_ratio = float(df["volume"].iloc[-1] / df["volume"].iloc[-n - 1:-1].mean())
    return _close(df) > pivot and vol_ratio >= ccfg["volume_multiple"]


@_rule("C-13")
def shadow_c13(inp: ShadowInputs):
    """C-13 market-relative RS, each variant alone in place of peer RS (C-3): (1) close/SPY within 5% of its
    252-session high; (2) 0.4 r63 + 0.2 r126 + 0.2 r189 + 0.2 r252, percentile within the universe >= 70.

    Each variant's breakouts are ranked by its own RS measure and fill the live open slots under the C-9
    sector cap (`strategies._pick_entries`), exactly as sleeve_c fills them with peer RS."""
    ccfg = inp.cfg.sleeves["C"]
    spy = _df(inp, inp.cfg.playbook["regime"]["benchmark"], 253)["close"]
    universe = [s for s in ccfg["universe"] if s in inp.bars and len(_upto(inp, s)) >= 260]
    if not universe:
        raise Skip("no C universe names with 260 bars")
    rs_line, score, base_ok, breakout = {}, {}, {}, {}
    for sym in universe:
        df = _upto(inp, sym)
        close = df["close"]
        ratio = (close / spy).dropna()
        rs_line[sym] = float(ratio.iloc[-1] / ratio.iloc[-252:].max()) if len(ratio) >= 252 else float("nan")
        score[sym] = (0.4 * ind.total_return(close, 63) + 0.2 * ind.total_return(close, 126)
                      + 0.2 * ind.total_return(close, 189) + 0.2 * ind.total_return(close, 252))
        _, checks = strat.trend_template(df, 100.0, 0.0)
        base_ok[sym] = all(v for k, v in checks.items() if k != "rs_ok")
        breakout[sym] = _c_breakout(inp, sym, df)
    pct = pd.Series(score, dtype=float).dropna().rank(pct=True) * 100
    # variant -> {symbol passing its RS test: ranking key}
    variants = {"rs_line_near_high": {s: v for s, v in rs_line.items() if not _nan(v) and v >= 0.95},
                "weighted_rs": {s: float(v) for s, v in pct.items() if v >= ccfg["rs_min_percentile"]}}
    live_entries = [sym for sym, _ in _entries(inp, "C")]
    held = _held_syms(inp, "C")
    plan = inp.plans.get("C")
    if plan is not None:
        staying = {s: t for s, t in plan.targets.items() if t.qty > TINY and s not in live_entries}
    else:
        staying = {s: Target(s, "C", _cur_qty(inp, "C", s), None) for s in held}
    slots = max(0, ccfg["max_positions"] - len(staying))
    group_of = strat.sector_lookup(ccfg.get("sectors"))
    sector_max = inp.cfg.policy.get("portfolio", {}).get("sector_max_positions")
    can_enter = _perm(inp, "C") > 0
    changes, picks = [], {}
    for name, rank in variants.items():
        ok = {s for s in universe if s in rank and base_ok[s]}
        ranked = sorted(((rank[s], s) for s in ok if breakout[s] and s not in held), reverse=True)
        chosen = strat._pick_entries(ranked, slots, staying, group_of, sector_max, []) if can_enter else []
        picks[name] = [s for _, s in chosen]
        for sym in live_entries:
            if sym not in picks[name]:
                why = "ranked out (open slots or the C-9 sector cap)" if sym in ok else f"fails {name}"
                changes.append({"variant": name, "sleeve": "C", "symbol": sym, "action": "skip entry", "why": why})
        for sym in picks[name]:
            if sym not in live_entries:
                changes.append({"variant": name, "sleeve": "C", "symbol": sym, "action": "enter",
                                "why": f"{name} breakout"})
    detail = {"open_slots": slots, "passing": {name: sorted(s for s in universe if s in r and base_ok[s])
                                               for name, r in variants.items()}, "picks": picks}
    return detail, changes


def _upto(inp: ShadowInputs, sym: str) -> pd.DataFrame:
    df = inp.bars[sym]
    return df[df.index <= inp.as_of] if inp.as_of is not None else df


@_rule("C-14")
def shadow_c14(inp: ShadowInputs):
    """C-14 VCP proxy: 15-session range/close <= 0.12, ATR10/ATR50 < 0.8, and 10-session mean volume <
    50-session mean volume. Entries failing it are skipped.

    Interpretation (the rule text does not say): all three are measured on the base, the bars before today,
    and the range is divided by yesterday's close. Today's breakout bar is wide and heavy by design, so
    counting it would fail most real breakouts. Logged as detail["measured_on"]."""
    checked, changes, skipped = [], [], []
    for sym, _t in _entries(inp, "C"):
        df = _try_df(inp, sym, 52, skipped)
        if df is None:
            continue
        base = df.iloc[:-1]  # today's breakout bar is wide and heavy by design
        rng = float(base["high"].iloc[-15:].max() - base["low"].iloc[-15:].min()) / float(base["close"].iloc[-1])
        atr_ratio = strat._last(ind.atr(base, 10)) / strat._last(ind.atr(base, 50))
        dry = float(base["volume"].iloc[-10:].mean()) < float(base["volume"].iloc[-50:].mean())
        tight, calm = rng <= 0.12, not _nan(atr_ratio) and atr_ratio < 0.8
        checked.append({"symbol": sym, "range15": _r(rng), "atr10_atr50": _r(atr_ratio), "volume_dry": dry})
        if not (tight and calm and dry):
            failed = [k for k, ok in (("range", tight), ("atr", calm), ("volume", dry)) if not ok]
            changes.append({"sleeve": "C", "symbol": sym, "action": "skip entry",
                            "why": "no VCP: " + ", ".join(failed)})
    detail: dict = {"measured_on": "the base: bars before today (today's breakout bar left out)", "checked": checked}
    if skipped:
        detail["skipped_symbols"] = skipped
    return detail, changes


@_rule("C-15")
def shadow_c15(inp: ShadowInputs):
    """C-15: once any close since entry reaches entry + 2R, the stop stays at or above the entry price from
    then on. The shadow exits at the first later close at or below entry; until then it reports 'raise stop'
    on each day the live C-7 stop sits below entry."""
    n = inp.cfg.policy["per_trade"].get("trail_low_sessions", {}).get("C", 10)
    checked, changes, skipped, earlier = [], [], [], []
    for sym, lot in _held(inp, "C", skipped).items():
        df = _try_df(inp, sym, 2, skipped)
        rps = _rps(lot)
        if df is None or rps is None:
            if rps is None:
                skipped.append(f"{sym}: 1R unknown")
            continue
        entry, e = pd.Timestamp(lot.entry_date), float(lot.entry_price)
        after = df[df.index > entry]
        armed_on = _first(after.index[after["close"] >= e + 2 * rps])
        exit_on = None
        if armed_on is not None:
            later = after[after.index > armed_on]  # the arming close is above entry by definition
            exit_on = _first(later.index[later["close"] <= e])
        close, stop = _close(df), _live_c_stop(lot, df, n)
        checked.append({"symbol": sym, "R_now": _r((close - e) / rps, 2),
                        "best_close_R": _r((after["close"].max() - e) / rps, 2) if len(after) else None,
                        "reached_2R_on": armed_on, "stop": _r(stop, 2), "entry": _r(e, 2)})
        why = f"close at or below the breakeven stop {e:.2f} after reaching +2R on {_clean(armed_on)}"
        if _exit_once(inp, "C", sym, df, exit_on, why, changes, earlier):
            continue
        if armed_on is not None and (stop is None or stop < e) and _live_holds(inp, "C", sym):
            changes.append({"sleeve": "C", "symbol": sym, "action": "raise stop", "stop_from": _r(stop, 4),
                            "stop_to": _r(e, 4)})
    return _finish({"checked": checked}, skipped, earlier), changes


@_rule("C-16")
def shadow_c16(inp: ShadowInputs):
    """C-16: exit at the close of session 20 when no high in sessions 1 to 20 reached entry + 1R.
    Measured by the daily high (+1R touched counts); highs after session 20 never undo the exit."""
    checked, changes, skipped, earlier = [], [], [], []
    for sym, lot in _held(inp, "C", skipped).items():
        df = _try_df(inp, sym, 2, skipped)
        rps = _rps(lot)
        if df is None or rps is None:
            if rps is None:
                skipped.append(f"{sym}: 1R unknown")
            continue
        first20 = df[df.index > pd.Timestamp(lot.entry_date)].iloc[:20]
        if len(first20) < 20:
            continue
        best_r = (float(first20["high"].max()) - lot.entry_price) / rps
        held = strat._bars_held(df, lot.entry_date)
        checked.append({"symbol": sym, "sessions_held": held, "best_R_by_session_20": _r(best_r, 2),
                        "measured_by": "high"})
        if best_r < 1:
            why = f"best {best_r:.2f}R by session 20 (needs +1R)"
            _exit_once(inp, "C", sym, df, first20.index[-1], why, changes, earlier)
    return _finish({"checked": checked}, skipped, earlier), changes


def losing_streak(trades: list[dict], sleeve: str = "C") -> int:
    """C-17: losing lots since the sleeve's last winner (net R, else net P&L). Scratch trades neither
    count nor reset, so the half-risk state lasts until a real winner."""
    rows = sorted((t for t in trades if t.get("sleeve") == sleeve), key=lambda t: str(t.get("date") or ""))
    streak = 0
    for t in reversed(rows):
        v = t.get("R") if t.get("R") is not None else t.get("pnl")
        if v is None or _nan(v):
            continue
        if v > 0:
            break
        if v < 0:
            streak += 1
    return streak


@_rule("C-17")
def shadow_c17(inp: ShadowInputs):
    """C-17: after 5 consecutive losing C lots, C risk is halved until the next winner."""
    if inp.state is None:
        raise Skip("needs closed trades from the book state")
    streak = losing_streak(list(getattr(inp.state, "closed_trades", []) or []), "C")
    detail = {"losing_streak": streak, "threshold": 5, "half_risk": streak >= 5}
    changes: list[dict] = []
    if streak < 5:
        return detail, changes
    changes.append({"sleeve": "C", "action": "half risk on new entries", "losing_streak": streak})
    for sym, t in _entries(inp, "C"):
        ch = _resize_change(inp, "C", sym, t, 0.5, "smaller entry")
        if ch:
            changes.append(ch)
    return detail, changes


# --- (b) sleeve D ------------------------------------------------------------------------------------


@_rule("D-5")
def shadow_d5(inp: ShadowInputs):
    """D-5: go to zero only on a close below the N-session low, not the Donchian midpoint; trail the stop at
    max(stop, close - 3 x ATR20), a ratchet over every close since entry.

    N is the shortest D lookback (20); the rule text does not name it. The bars since entry are replayed: each
    session exits on close < the prior N-session low or close <= the stop set at the previous close (from the
    initial stop; today also the live stop). The first such session is the shadow exit."""
    if "D" not in inp.plans:
        raise Skip("sleeve D is off (D-1)")
    dcfg, pt = inp.cfg.sleeves["D"], inp.cfg.policy["per_trade"]
    n, k = min(dcfg["lookbacks"]), pt["stop_atr_multiple"]["D"]
    checked, changes, skipped, earlier = [], [], [], []
    for sym, lot in _held(inp, "D", skipped).items():
        df = _try_df(inp, sym, n + 1, skipped)
        if df is None:
            continue
        path = _d5_path(df, lot, n, k, pt["atr_period"])
        checked.append({"symbol": sym, "close": _r(_close(df), 2), "low_n": _r(path["low_n"].iloc[-1], 2),
                        "shadow_stop": _r(path["stop_in_force"].iloc[-1], 2), "next_stop": _r(path["next_stop"], 2)})
        exits = path["exits"]
        exit_on = _first(exits.index[exits])
        if exit_on is not None:
            if float(df.at[exit_on, "close"]) < float(path["low_n"].loc[exit_on]):
                why = f"close below the {n}-session low"
            else:
                why = f"close at or below the trailed stop {float(path['stop_in_force'].loc[exit_on]):.2f}"
            _exit_once(inp, "D", sym, df, exit_on, why, changes, earlier)
        elif not _live_holds(inp, "D", sym):
            changes.append({"sleeve": "D", "symbol": sym, "action": "hold",
                            "why": f"close above the {n}-session low and the trailed stop"})
        elif not _nan(path["next_stop"]) and (_nan(lot.stop) or path["next_stop"] > lot.stop + TINY):
            changes.append({"sleeve": "D", "symbol": sym, "action": "raise stop", "stop_from": _r(lot.stop),
                            "stop_to": _r(path["next_stop"])})
    return _finish({"n": n, "checked": checked}, skipped, earlier), changes


def _d5_path(df: pd.DataFrame, lot: Lot, n: int, k: float, atr_n: int) -> dict:
    """D-5 replayed over the bars since entry (only sessions after the entry date can exit)."""
    entry = pd.Timestamp(lot.entry_date)
    close = df["close"]
    since = df.index >= entry  # the entry bar's trail is the entry stop itself
    trail = (close - k * ind.atr(df, atr_n))[since].cummax()
    base = lot.initial_stop if not _nan(lot.initial_stop) else lot.stop
    base = None if _nan(base) else float(base)
    set_at = trail.clip(lower=base) if base is not None else trail  # the stop set at each close
    stop_in_force = set_at.shift(1).reindex(df.index)
    if base is not None:
        stop_in_force = stop_in_force.where(stop_in_force.notna() | ~since, base)
    if not _nan(lot.stop):  # today the live stop is in force too
        prev = stop_in_force.iloc[-1]
        stop_in_force.iloc[-1] = float(lot.stop) if _nan(prev) else max(float(prev), float(lot.stop))
    low_n = df["low"].rolling(n, min_periods=n).min().shift(1)
    exits = ((close < low_n) | (close <= stop_in_force)) & (df.index > entry)
    last = [s for s in (set_at.iloc[-1] if len(set_at) else float("nan"), lot.stop) if not _nan(s)]
    return {"low_n": low_n, "stop_in_force": stop_in_force, "exits": exits,
            "next_stop": max(last) if last else float("nan")}


# --- (d) execution -----------------------------------------------------------------------------------


@_rule("EX-6")
def shadow_ex6(inp: ShadowInputs):
    """EX-6: B and C entries as DAY limit buys at close + 0.5 x ATR20. Today: the limit each entry would
    use. Entries filled today: would that limit have filled (open <= limit fills at the open; else a low at or
    below the limit fills at the limit)?"""
    atr_n = inp.cfg.policy["per_trade"]["atr_period"]
    today, resolved, changes, skipped = [], [], [], []
    for s in ("B", "C"):
        for sym, _t in _entries(inp, s):
            df = _try_df(inp, sym, atr_n + 1, skipped)
            if df is None:
                continue
            close, atr = _close(df), strat._last(ind.atr(df, atr_n))
            if _nan(atr):
                skipped.append(f"{sym}: ATR{atr_n} unknown")
                continue
            limit = close + 0.5 * atr
            today.append({"sleeve": s, "symbol": sym, "close": _r(close, 2), "limit": _r(limit, 4)})
            changes.append({"sleeve": s, "symbol": sym, "action": "DAY limit buy", "limit": _r(limit, 4)})
        for sym, lot in _held(inp, s, skipped).items():
            row = _limit_outcome(inp, sym, lot, atr_n, skipped)
            if row is None:
                continue
            resolved.append({"sleeve": s, **row})
            if not row["would_fill"]:
                changes.append({"sleeve": s, "symbol": sym, "action": "no position",
                                "why": f"limit {row['limit']} not reached (low {row['low']})"})
    detail: dict = {"today": today, "resolved": resolved}
    if skipped:
        detail["skipped_symbols"] = skipped
    return detail, changes


def _limit_outcome(inp: ShadowInputs, sym: str, lot: Lot, atr_n: int, skipped: list) -> dict | None:
    """For a lot whose first session after the signal is today: would the EX-6 limit have filled?"""
    df = inp.bars.get(sym)
    if df is None or not lot.entry_date:
        return None
    df = df[df.index <= inp.as_of] if inp.as_of is not None else df
    signal = pd.Timestamp(lot.entry_date)
    after, sig = df[df.index > signal], df[df.index <= signal]
    if len(after) != 1:
        return None
    if len(sig) < atr_n + 1:
        skipped.append(f"{sym}: need {atr_n + 1} bars before the entry for ATR")
        return None
    limit = float(sig["close"].iloc[-1]) + 0.5 * strat._last(ind.atr(sig, atr_n))
    bar = after.iloc[0]
    o, lo = float(bar["open"]), float(bar["low"])
    if _nan(limit) or _nan(o) or _nan(lo):
        skipped.append(f"{sym}: limit, open or low unknown")
        return None
    fill = o if o <= limit else (limit if lo <= limit else None)
    return {"symbol": sym, "signal_date": signal.date().isoformat(), "limit": _r(limit, 4), "open": _r(o, 4),
            "low": _r(lo, 4), "would_fill": fill is not None, "limit_fill": _r(fill, 4),
            "market_fill": _r(lot.entry_price, 4)}


# --- the daily entry point ---------------------------------------------------------------------------

SHADOW_RULES: dict[str, Callable[..., dict]] = {
    "REG-5": shadow_reg5, "REG-6": shadow_reg6,
    "A-6": shadow_a6, "A-7": shadow_a7, "A-8": shadow_a8, "A-9": shadow_a9,
    "B-7": shadow_b7, "B-8": shadow_b8, "B-9": shadow_b9, "B-10": shadow_b10,
    "C-10": shadow_c10, "C-11": shadow_c11, "C-12": shadow_c12, "C-13": shadow_c13, "C-14": shadow_c14,
    "C-15": shadow_c15, "C-16": shadow_c16, "C-17": shadow_c17,
    "D-5": shadow_d5, "EX-6": shadow_ex6,
}

# Which sleeve plans each rule's result is attached to (plan.shadow).
RULE_SLEEVES: dict[str, tuple[str, ...]] = {
    "REG-5": ("B", "C"), "REG-6": ("B", "C", "D"),
    "A-6": ("A",), "A-7": ("A",), "A-8": ("A",), "A-9": ("A",),
    "B-7": ("B",), "B-8": ("B",), "B-9": ("B",), "B-10": ("B",),
    "C-10": ("C",), "C-11": ("C",), "C-12": ("C",), "C-13": ("C",), "C-14": ("C",),
    "C-15": ("C",), "C-16": ("C",), "C-17": ("C",),
    "D-5": ("D",), "EX-6": ("B", "C"),
}


def compute(bars, cfg, plans, lots, regime, as_of, *, state=None, weights=None, equity=None) -> dict[str, dict]:
    """Run every TEST FIRST shadow rule for today and attach each result to the relevant `plan.shadow`.

    Returns {rule_id: result}. Reads only: targets, lots, state and bars are never modified. Calling it
    twice replaces the earlier results instead of adding duplicates.
    """
    inp = ShadowInputs(bars=bars, cfg=cfg, plans=plans, lots=lots, regime=regime, as_of=as_of, state=state,
                       weights=weights, equity=equity)
    results: dict[str, dict] = {}
    for rule_id, fn in SHADOW_RULES.items():
        res = fn(inp)
        results[rule_id] = res
        for s in RULE_SLEEVES[rule_id]:
            plan = (plans or {}).get(s)
            if plan is not None:
                plan.shadow[:] = [x for x in plan.shadow if x.get("rule") != rule_id]
                plan.shadow.append(res)
    return results


def summarize(results: dict[str, dict]) -> list[str]:
    """One plain-English line per rule that fired, for the journal and the dry-run report."""
    lines = []
    for rule_id, res in results.items():
        if not res.get("fires"):
            continue
        parts = []
        for ch in res.get("would_change", [])[:4]:
            who = "/".join(x for x in (ch.get("sleeve"), ch.get("symbol")) if x)
            parts.append(f"{who} {ch.get('action', '')}".strip())
        more = len(res["would_change"]) - len(parts)
        lines.append(f"{rule_id} would: " + "; ".join(parts) + (f" (+{more} more)" if more > 0 else ""))
    return lines
