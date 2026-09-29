"""The four playbook sleeves as pure functions of daily bars.

Each function returns a SleevePlan: target quantities for symbols the sleeve
wants to hold (or exit), plus indicator snapshots that Claude gets to see.
"""
from __future__ import annotations

from collections import Counter
from typing import Callable

import numpy as np
import pandas as pd

from . import indicators as ind
from .data import Bars
from .models import Lot, SleevePlan, Target


def _last(series: pd.Series) -> float:
    s = series.dropna()
    return float(s.iloc[-1]) if len(s) else float("nan")


def _bars_held(df: pd.DataFrame, entry_date: str) -> int:
    return int((df.index > pd.Timestamp(entry_date)).sum())


def _has_bars(bars: Bars, sym: str) -> bool:
    df = bars.get(sym)
    return df is not None and len(df) > 0


def risk_pct(policy: dict, sleeve: str) -> float:
    """RISK-2: a sleeve's 1R as a fraction of equity (per-sleeve value, never above the hard cap).
    The same rule as Config.risk_pct and the cap risk.py enforces, for code that holds only the policy."""
    pt = policy["per_trade"]
    r = (pt.get("risk_pct_by_sleeve") or {}).get(sleeve, pt["risk_pct_default"])
    return float(min(r, pt.get("risk_pct_hard_cap", r)))


def _band(target: float, current: float, band: float) -> float:
    """Keep the current quantity when the change is inside the rebalance band."""
    if target > 0 and current > 0 and abs(target - current) / max(target, current) < band:
        return current
    return target


# --- Sleeve A: Faber GTAA-5, optional GEM blend -------------------------------------------


def faber_in(close: pd.Series, as_of: pd.Timestamp) -> tuple[bool, float, float]:
    monthly = ind.completed_month_closes(close, as_of)
    if len(monthly) < 10:
        return False, float("nan"), float("nan")
    sma10 = float(monthly.iloc[-10:].mean())
    return bool(monthly.iloc[-1] > sma10), float(monthly.iloc[-1]), sma10


def faber_asset(close: pd.Series, as_of: pd.Timestamp, vol_target: float) -> dict:
    """A-2 and A-3 for one asset: in or out versus the 10-month SMA, and the scale min(1, target / vol60)
    with vol60 measured up to the last completed month-end."""
    is_in, last_m, sma10 = faber_in(close, as_of)
    month_end = ind.completed_month_closes(close, as_of).index
    vol_close = close[close.index <= month_end[-1]] if len(month_end) else close
    vol60 = _last(ind.realized_vol(vol_close, 60))
    scale = min(1.0, vol_target / vol60) if vol60 and not np.isnan(vol60) else 1.0
    return {"in": is_in, "month_close": last_m, "sma10m": sma10, "vol60": vol60, "scale": scale}


def gem_pick(bars: Bars, gem: dict, as_of: pd.Timestamp) -> str:
    def r12(sym: str) -> float:
        if not _has_bars(bars, sym):
            return float("nan")
        m = ind.completed_month_closes(bars[sym]["close"], as_of)
        return float(m.iloc[-1] / m.iloc[-13] - 1) if len(m) >= 13 else float("nan")

    us, intl, tbill = r12(gem["us"]), r12(gem["intl"]), r12(gem["tbill"])
    if np.isnan(us) or np.isnan(tbill) or us <= tbill:
        return gem["bonds"]
    return gem["us"] if np.isnan(intl) or us >= intl else gem["intl"]


def sleeve_a(bars: Bars, cfg: dict, capital: float, lots: dict[str, Lot], policy: dict,
             as_of: pd.Timestamp) -> SleevePlan:
    plan = SleevePlan("A", capital)
    vol_target = policy["portfolio"]["vol_target_annual"]
    band = policy["turnover"]["rebalance_band"]
    faber_capital = capital * (0.5 if cfg.get("gem_blend") else 1.0)
    weights: dict[str, float] = {}
    reserved = 0.0  # held assets with no bars keep their slice instead of it going to cash

    share = 1.0 / len(cfg["assets"])
    for sym in cfg["assets"]:
        if not _has_bars(bars, sym):
            if sym in lots and lots[sym].qty > 0:
                reserved += share * faber_capital / capital
                plan.targets[sym] = Target(sym, "A", lots[sym].qty, None, "hold (no data)")
            plan.notes.append(f"{sym}: no bars today")
            continue
        fa = faber_asset(bars[sym]["close"], as_of, vol_target)
        is_in, last_m, sma10, vol60, scale = fa["in"], fa["month_close"], fa["sma10m"], fa["vol60"], fa["scale"]
        w = share * scale if is_in else 0.0
        weights[sym] = weights.get(sym, 0.0) + w * faber_capital / capital
        plan.candidates.append({
            "symbol": sym, "month_close": round(last_m, 2), "sma10m": round(sma10, 2),
            "above_10m_sma": is_in, "vol60": round(vol60, 3), "weight_in_sleeve": round(w, 3),
        })
    if cfg.get("gem_blend"):
        pick = gem_pick(bars, cfg["gem"], as_of)
        weights[pick] = weights.get(pick, 0.0) + 0.5
        plan.notes.append(f"GEM holds {pick}")

    weights[cfg["cash"]] = max(0.0, 1.0 - sum(weights.values()) - reserved)
    for sym, w in weights.items():
        current = lots[sym].qty if sym in lots else 0.0
        if not _has_bars(bars, sym):
            if current > 0:
                plan.targets[sym] = Target(sym, "A", current, None, "hold (no data)")
            continue
        price = _last(bars[sym]["close"])
        target = w * capital / price
        plan.targets[sym] = Target(sym, "A", _band(target, current, band), None,
                                   f"faber weight {w:.2f} of sleeve")
    for sym in lots:
        if sym not in plan.targets:
            plan.targets[sym] = Target(sym, "A", 0.0, None, "no longer in sleeve A")
    return plan


# --- Sleeve B: Connors RSI(2) ---------------------------------------------------------------


def sleeve_b(bars: Bars, cfg: dict, capital: float, lots: dict[str, Lot], policy: dict,
             equity: float, size_mult: float) -> SleevePlan:
    plan = SleevePlan("B", capital)
    k = policy["per_trade"]["stop_atr_multiple"]["B"]
    time_stop = policy["per_trade"]["time_stop_days"]["B"]
    risk = risk_pct(policy, "B") * equity * size_mult
    entries = []
    for sym in cfg["symbols"]:
        lot = lots.get(sym)
        if not _has_bars(bars, sym):
            if lot:
                plan.targets[sym] = Target(sym, "B", lot.qty, lot.stop, "hold (no data)")
            continue
        df = bars[sym]
        close = float(df["close"].iloc[-1])
        sma200 = _last(ind.sma(df["close"], 200))
        sma5 = _last(ind.sma(df["close"], 5))
        rsi2 = _last(ind.rsi(df["close"], 2))
        atr = _last(ind.atr(df, policy["per_trade"]["atr_period"]))
        snap = {"symbol": sym, "close": round(close, 2), "sma200": round(sma200, 2), "sma5": round(sma5, 2),
                "rsi2": round(rsi2, 1), "atr20": round(atr, 2)}
        plan.candidates.append(snap)
        if lot:
            why = exit_b(df, lot.stop, lot.entry_date, time_stop)
            plan.targets[sym] = Target(sym, "B", 0.0 if why else lot.qty, lot.stop, why or "hold")
        elif close > sma200 and rsi2 < cfg["rsi_entry"]:
            entries.append((rsi2, sym, close, atr))

    open_slots = cfg["max_positions"] - sum(1 for t in plan.targets.values() if t.qty > 0)
    if size_mult <= 0:
        if entries:
            plan.notes.append("regime gate: RSI2 entries off")
        return plan
    for rsi2, sym, close, atr in sorted(entries)[: max(0, open_slots)]:
        stop = close - k * atr
        qty = min(risk / (close - stop), capital / cfg["max_positions"] / close)
        plan.targets[sym] = Target(sym, "B", qty, stop, f"RSI2 entry: rsi2 {rsi2:.1f} < {cfg['rsi_entry']}")
    return plan


# --- Sleeve C: trend template breakouts -----------------------------------------------------


def trend_template(df: pd.DataFrame, rs_pct: float, rs_min: float) -> tuple[bool, dict]:
    c = df["close"]
    close = float(c.iloc[-1])
    s50, s150, s200 = (_last(ind.sma(c, n)) for n in (50, 150, 200))
    s200_prev = ind.sma(c, 200).dropna()
    s200_rising = len(s200_prev) > 21 and s200_prev.iloc[-1] > s200_prev.iloc[-22]
    hi52, lo52 = float(df["high"].iloc[-252:].max()), float(df["low"].iloc[-252:].min())
    checks = {
        "above_150_200": close > s150 and close > s200,
        "150_above_200": s150 > s200,
        "200_rising": bool(s200_rising),
        "50_above_150_200": s50 > s150 and s50 > s200,
        "above_50": close > s50,
        "25pct_above_52w_low": close >= 1.25 * lo52,
        "within_25pct_of_52w_high": close >= 0.75 * hi52,
        "rs_ok": rs_pct >= rs_min,
    }
    return all(checks.values()), checks


def sector_lookup(sectors) -> Callable[[str], str | None]:
    """C-9: turn a sector map into `symbol -> group`.

    Accepts the playbook shape `{group: [symbols]}`, a flat `{symbol: group}` map, a function
    (for example `Config.sector_of`) or None (no groups, so no cap).
    """
    if sectors is None:
        return lambda sym: None
    if callable(sectors):
        return sectors
    flat: dict[str, str] = {}
    for key, value in dict(sectors).items():
        if isinstance(value, str):
            flat[key] = value
        else:
            for sym in value:
                flat.setdefault(sym, key)
    return flat.get


def _open_by_sector(targets: dict[str, Target], group_of: Callable[[str], str | None]) -> Counter:
    """C-9: open C positions per group (held and staying, or entering today)."""
    return Counter(g for sym, t in targets.items() if t.qty > 0 and (g := group_of(sym)) is not None)


def _pick_entries(entries: list, slots: int, targets: dict[str, Target], group_of, sector_max: int | None,
                  notes: list[str]) -> list:
    """Take ranked entries until the slots are full, skipping names whose group is at the C-9 cap."""
    counts = _open_by_sector(targets, group_of)
    chosen = []
    for entry in entries:
        if len(chosen) >= slots:
            break
        sym = entry[1]
        group = group_of(sym)
        if sector_max is not None and group is not None and counts[group] >= sector_max:
            notes.append(f"C-9 sector cap: skipped {sym} ({group} already has {counts[group]} open C position(s))")
            continue
        if group is not None:
            counts[group] += 1
        chosen.append(entry)
    return chosen


def sleeve_c(bars: Bars, cfg: dict, capital: float, lots: dict[str, Lot], policy: dict,
             equity: float, size_mult: float, sectors=None, sector_max: int | None = None) -> SleevePlan:
    """Trend-template breakouts (C-2 to C-6) with the C-9 sector cap.

    `sectors` / `sector_max` default to the playbook `sectors` map and policy
    `portfolio.sector_max_positions`, so an old call without them still applies the cap.
    """
    plan = SleevePlan("C", capital)
    k = policy["per_trade"]["stop_atr_multiple"]["C"]
    max_dist = policy["per_trade"]["max_stop_distance_pct"]["C"]
    risk = risk_pct(policy, "C") * equity * size_mult
    lookback = cfg["pivot_lookback"]
    group_of = sector_lookup(sectors if sectors is not None else cfg.get("sectors"))
    if sector_max is None:
        sector_max = policy.get("portfolio", {}).get("sector_max_positions")

    universe = [s for s in cfg["universe"] if s in bars and len(bars[s]) >= 260]
    r12 = pd.Series({s: ind.total_return(bars[s]["close"], 252) for s in universe}).dropna()
    rs_pct = r12.rank(pct=True) * 100

    for sym, lot in lots.items():
        if not _has_bars(bars, sym):
            plan.targets[sym] = Target(sym, "C", lot.qty, lot.stop, "hold (no data)")
            continue
        df = bars[sym]
        why = exit_c(df, lot.stop)
        plan.targets[sym] = Target(sym, "C", 0.0 if why else lot.qty, lot.stop, why or "hold")

    entries = []
    for sym in universe:
        df = bars[sym]
        ok, checks = trend_template(df, float(rs_pct.get(sym, 0)), cfg["rs_min_percentile"])
        close = float(df["close"].iloc[-1])
        pivot = float(df["high"].iloc[-lookback - 1:-1].max())
        vol_ratio = float(df["volume"].iloc[-1] / df["volume"].iloc[-lookback - 1:-1].mean())
        breakout = close > pivot and vol_ratio >= cfg["volume_multiple"]
        if ok:
            plan.candidates.append({"symbol": sym, "close": round(close, 2), "pivot": round(pivot, 2),
                                    "volume_ratio": round(vol_ratio, 2), "rs_pct": round(float(rs_pct[sym]), 1),
                                    "return_12m": round(float(r12[sym]), 3), "breakout_today": breakout,
                                    "sector": group_of(sym)})
        if ok and breakout and sym not in lots:
            entries.append((float(rs_pct[sym]), sym, close, _last(ind.atr(df, policy["per_trade"]["atr_period"]))))

    open_slots = cfg["max_positions"] - sum(1 for t in plan.targets.values() if t.qty > 0)
    if size_mult <= 0:
        if entries:
            plan.notes.append(f"regime gate: {len(entries)} breakout(s) skipped")
        return plan
    ranked = sorted(entries, reverse=True)
    for _, sym, close, atr in _pick_entries(ranked, max(0, open_slots), plan.targets, group_of, sector_max,
                                            plan.notes):
        stop = max(close - k * atr, close * (1 - max_dist))
        qty = min(risk / (close - stop), capital / cfg["max_positions"] / close)
        plan.targets[sym] = Target(sym, "C", qty, stop, "breakout entry")
    if len(entries) > max(0, open_slots):
        plan.notes.append(f"{len(entries)} breakouts for {max(0, open_slots)} slot(s); ranked by RS")
    return plan


# --- Sleeve D: crypto Donchian ensemble -----------------------------------------------------


def donchian_score(df: pd.DataFrame, lookbacks: list[int]) -> float:
    close = float(df["close"].iloc[-1])
    votes = []
    for n in lookbacks:
        if len(df) < n:
            continue
        mid = (df["high"].iloc[-n:].max() + df["low"].iloc[-n:].min()) / 2
        votes.append(close > mid)
    return float(np.mean(votes)) if votes else 0.0


def sleeve_d(bars: Bars, cfg: dict, capital: float, lots: dict[str, Lot], policy: dict,
             size_mult: float) -> SleevePlan:
    plan = SleevePlan("D", capital)
    k = policy["per_trade"]["stop_atr_multiple"]["D"]
    band = policy["turnover"]["rebalance_band"]
    n = len(cfg["symbols"])
    for sym in cfg["symbols"]:
        df = bars.get(sym)
        if df is None:
            continue
        close = float(df["close"].iloc[-1])
        score = donchian_score(df, cfg["lookbacks"])
        vol = _last(ind.realized_vol(df["close"], 30, 365))
        scale = min(1.0, cfg["vol_target_annual"] / vol) if vol and not np.isnan(vol) else 0.0
        w = score * scale * size_mult / n
        atr = _last(ind.atr(df, policy["per_trade"]["atr_period"]))
        plan.candidates.append({"symbol": sym, "close": round(close, 2), "trend_score": round(score, 2),
                                "vol30": round(vol, 3), "weight_in_sleeve": round(w, 3)})
        lot = lots.get(sym)
        current = lot.qty if lot else 0.0
        if lot and lot.stop is not None and close <= lot.stop:
            plan.targets[sym] = Target(sym, "D", 0.0, lot.stop, "crypto stop hit")
            continue
        stop = lot.stop if lot and lot.stop is not None else close - k * atr
        plan.targets[sym] = Target(sym, "D", _band(w * capital / close, current, band), stop,
                                   f"donchian score {score:.2f}")
    return plan


# --- exits shared by the sleeves, the shadow veto lots (CL-9) and the backtester -----------------


def exit_b(df: pd.DataFrame, stop: float | None, entry_date: str, time_stop: int) -> str | None:
    """B-4: first of close > SMA5, `time_stop` sessions held, close <= stop. None means hold."""
    close = float(df["close"].iloc[-1])
    sma5 = _last(ind.sma(df["close"], 5))
    held = _bars_held(df, entry_date)
    if close > sma5:
        return "RSI2 exit: close above 5-day SMA"
    if held >= time_stop:
        return f"RSI2 time stop after {held} days"
    if stop is not None and close <= stop:
        return "RSI2 disaster stop"
    return None


def exit_c(df: pd.DataFrame, stop: float | None) -> str | None:
    """C exits: close <= stop, close < lowest low of the prior 10 sessions (C-7), close < SMA50 (C-8)."""
    close = float(df["close"].iloc[-1])
    low10 = float(df["low"].iloc[-11:-1].min())
    sma50 = _last(ind.sma(df["close"], 50))
    if stop is not None and close <= stop:
        return "breakout stop hit"
    if close < low10:
        return "closed below 10-day low"
    if close < sma50:
        return "closed below 50-day SMA"
    return None


def exit_d(df: pd.DataFrame, stop: float | None, lookbacks: list[int]) -> str | None:
    """D-4: exit on the stop or when the Donchian score is 0."""
    close = float(df["close"].iloc[-1])
    if stop is not None and close <= stop:
        return "crypto stop hit"
    if donchian_score(df, lookbacks) == 0:
        return "donchian score 0"
    return None


def exit_signal(sleeve: str, df: pd.DataFrame, stop: float | None, entry_date: str, sleeve_cfg: dict,
                policy: dict) -> str | None:
    """The sleeve's own exit rule for one position (A has none: it rebalances monthly)."""
    if sleeve == "B":
        return exit_b(df, stop, entry_date, policy["per_trade"]["time_stop_days"]["B"])
    if sleeve == "C":
        return exit_c(df, stop)
    if sleeve == "D":
        return exit_d(df, stop, sleeve_cfg["lookbacks"])
    return None


def rule_stop(sleeve: str, df: pd.DataFrame, policy: dict) -> float | None:
    """The rule stop for a new position at today's close: B and D close - 3*ATR20; C max(close - 2*ATR20,
    0.92*close). Also the floor for Claude's stops (CL-14). None for sleeve A (no stops, A-5)."""
    if sleeve not in ("B", "C", "D"):
        return None
    pt = policy["per_trade"]
    close = float(df["close"].iloc[-1])
    a = _last(ind.atr(df, pt["atr_period"]))
    stop = close - pt["stop_atr_multiple"][sleeve] * a
    max_dist = pt.get("max_stop_distance_pct", {}).get(sleeve)
    if max_dist:
        stop = max(stop, close * (1 - max_dist))
    return float(stop)
