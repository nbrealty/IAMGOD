"""Scalp lab backtest: replay each setup day by day, then add costs, baselines and statistics.

Fill model (the same `Tracker` the setups use): an intent decided at a bar's close fills at the NEXT bar's
open; stops and targets are checked on every later bar's high/low (and on the fill bar itself), and when both
fall inside one bar the STOP is assumed first; everything is flat at the open of the 15:55 bar (5 minutes before
an early close); one position per setup per symbol at a time. Half days are skipped as trading days (they
still count as history for yesterday's levels, the noise band and the EMAs). A session whose data stop before
the time exit (still in progress, or cut short) is skipped too: its trades would be closed at a fake 'eod'.

Every trade is $1,000 of notional so setups compare on the same footing. Results are in basis points (bps,
1/100 of a percent) of notional; dollars per $1,000 trade = bps / 10.

Costs are charged per side in bps of notional (round trip = 2x). Defaults are the spec's scenarios: low 0.5,
realistic 1.5, pessimistic 4.0 bps per side, plus `quoted` 0.25 bps from the mechanics research: half of the
measured median SPY/QQQ quoted spread (0.26-0.27 bps full) plus half of the SEC fee on sells (0.206 bps), with
no slippage, no latency and no bid-ask bounce, i.e. the cheapest plausible cost. `gross` is no cost.

Options proxy: what the same signal might earn through a same-day (0DTE) at-the-money option, long premium only
(a call for a long signal, a put for a short one), per $1,000 of premium:
- `opt_bach` (the headline): a Bachelier (normal-model) ATM option priced at entry and exit, so it includes
  time decay (theta) and convexity. Volatility = max(1.2 x yesterday's 14-day realised close-to-close vol,
  10%/yr): 0DTE implied volatility usually trades above realised, so plain realised vol makes options too cheap.
- `opt_delta_no_decay`: the spec's first idea, 0.5 x underlying move / premium. It IGNORES time decay, which is
  most of a 0DTE option's cost late in the day, so it overstates; it is kept only for comparison. Do not use it.
Costs per side = max(a fixed half-spread in $ per share, a % of premium) divided by the modelled premium
(realistic $0.01 or 2%, pessimistic $0.02 or 5%): a 1-cent half-spread is more than 2% of a small late-day
premium. Limits: no skew, no intraday IV changes, the real contract grid (strikes $1 apart, not exactly at the
money), and paper-account option fills come from randomised 'indicative' quotes. Treat these numbers as a
rough order of magnitude, not as an options backtest. Mega-cap option spreads are wider than SPY/QQQ's.

Baselines (the honesty check), seeded and reproducible:
- random: the same number of trades per day and the same holding times, at random entry minutes with a
  coin-flip side (copying the setup's side to an earlier minute would leak the future into the baseline);
- coin: the setup's own entry intents with a coin-flip direction; a flipped entry gets its stop and target
  mirrored around the fill and then follows its own stop, target and time exits (the setup's own exit
  decisions still apply). Its trade count per day can be lower than the setup's, because a flipped position
  can still be open when the setup's next entry comes.
"""
from __future__ import annotations

import math
import zlib
from dataclasses import replace
from datetime import date
from typing import Iterable

import numpy as np
import pandas as pd

from . import data as dt
from .signals import SETUPS, Ctx, Day, Intent, Setup, Trade, Tracker, ema_after_day, noise_moves, noise_sigma

NOTIONAL = 1000.0
COSTS: dict[str, float] = {"quoted": 0.25, "low": 0.5, "realistic": 1.5, "pessimistic": 4.0,  # bps/side
                           "opt_realistic": 2.0, "opt_pessimistic": 5.0,            # % of premium per side
                           "opt_tick_realistic": 0.01, "opt_tick_pessimistic": 0.02}  # $/share half-spread
STOCK_SCENARIOS = ("gross", "quoted", "low", "realistic", "pessimistic")
IV_MARKUP = 1.2                        # 0DTE implied vol vs realised vol
IV_FLOOR = 0.10 / math.sqrt(252.0)     # 10%/yr as a daily vol
BOOT = 2000
MIN_BOOT_DAYS = 10   # fewer trading days than this: no 95% range or p-value (the bootstrap would be meaningless)
PHI0 = 1.0 / math.sqrt(2.0 * math.pi)
ROW_COLS = ["kind", "setup", "symbol", "date", "year", "side", "entry_time", "exit_time", "entry_m", "exit_m",
            "entry", "exit", "reason", "hold_min", "gross_bps", "r_mult", "pub_mult", "opt_delta_bps", "opt_bach_bps",
            "opt_premium"]
METRIC_KEYS = ["setup", "symbol", "primary", "split", "scenario", "cost_per_side", "opt_tick_usd", "trades", "days"]

def scenarios(costs: dict[str, float] = COSTS) -> list[tuple[str, str, float | tuple[float, float]]]:
    """(name, trade column, cost per side): bps of notional for stock, (% of premium, $/share) for options."""
    return [("gross", "gross_bps", 0.0),
            ("quoted", "gross_bps", costs["quoted"]),
            ("low", "gross_bps", costs["low"]),
            ("realistic", "gross_bps", costs["realistic"]),
            ("pessimistic", "gross_bps", costs["pessimistic"]),
            ("opt_bach", "opt_bach_bps", (costs["opt_realistic"], costs["opt_tick_realistic"])),
            ("opt_bach_pess", "opt_bach_bps", (costs["opt_pessimistic"], costs["opt_tick_pessimistic"])),
            ("opt_delta_no_decay", "opt_delta_bps", (costs["opt_realistic"], costs["opt_tick_realistic"]))]


def net_bps(gross_bps: float | np.ndarray, cost_per_side_bps: float | np.ndarray) -> float | np.ndarray:
    """Round trip: pay the per-side cost on entry and on exit."""
    return gross_bps - 2.0 * cost_per_side_bps


def option_cost_bps(premium: float | np.ndarray, pct: float, tick: float) -> float | np.ndarray:
    """Per-side option cost in bps of premium: the larger of a fixed half-spread and a % of premium."""
    prem = np.asarray(premium, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        by_tick = np.where(prem > 0, tick / prem * 1e4, np.nan)
    return np.fmax(pct * 100.0, by_tick)


def _net(df: pd.DataFrame, col: str, cost: float | tuple[float, float]) -> pd.Series:
    if isinstance(cost, tuple):
        prem = df["opt_premium"] if "opt_premium" in df else pd.Series(np.nan, index=df.index)
        return net_bps(df[col], pd.Series(option_cost_bps(prem.to_numpy(), *cost), index=df.index))
    return net_bps(df[col], cost)


def usd_per_1000(bps: float | np.ndarray) -> float | np.ndarray:
    return bps * NOTIONAL / 1e4


# ------------------------------------------------------------------------------------------------ execution
def execute(day: Day, intents: Iterable[Intent], exit_mode: str = "open", flip=None) -> list[Trade]:
    """Fill intents on the day's bars; an intent is submitted after the bar it was decided on closes.
    `flip(intent) -> bool` reverses chosen entries (see Tracker)."""
    by_m: dict[int, list[Intent]] = {}
    for it in intents:
        by_m.setdefault(int(it.m), []).append(it)
    tr = Tracker(day, exit_mode, flip)
    for i in range(day.n):
        tr.step(i)
        if tr.done:
            break
        for it in by_m.get(int(day.m[i]), ()):
            tr.submit(it)
    return tr.finish()


def _exit_at(day: Day, minute: int, exit_mode: str) -> tuple[int, float]:
    """Exit at the open of the first bar at or after `minute`, never later than the time exit."""
    if exit_mode == "open":
        k = int(np.searchsorted(day.m, min(minute, day.exit_m)))
        return (int(day.m[k]), float(day.o[k])) if k < day.n else (int(day.m[-1]) + 1, float(day.c[-1]))
    k = int(np.searchsorted(day.m, minute))
    if minute >= day.close_min or k >= day.n:
        if day.auction_close is not None and day.complete:
            return day.close_min, float(day.auction_close)
        return int(day.m[-1]) + 1, float(day.c[-1])
    return int(day.m[k]), float(day.o[k])


def random_baseline(day: Day, trades: list[Trade], exit_mode: str, rng: np.random.Generator
                    ) -> list[tuple[int, int, float, int, float]]:
    """Same count and holding minutes as the setup's trades that day, at random entry minutes with a
    coin-flip side. The side is NOT copied from the setup: it was decided with prices up to the setup's own
    entry, so reusing it at an earlier random minute would give the baseline a look at the future (a momentum
    setup's side put before its entry 'predicts' the move that triggered it)."""
    limit = day.exit_m if exit_mode == "open" else day.close_min
    out = []
    for t in trades:
        side = 1 if rng.integers(2) else -1
        hold = max(1, t.exit_m - t.entry_m)
        cand = np.flatnonzero((day.m >= 1) & (day.m + hold <= limit))
        if cand.size == 0:
            cand = np.flatnonzero((day.m >= 1) & (day.m < limit))
        if cand.size == 0:
            continue
        j = int(rng.choice(cand))
        xm, xp = _exit_at(day, int(day.m[j]) + hold, exit_mode)
        out.append((side, int(day.m[j]), float(day.o[j]), xm, xp))
    return out


def coin_baseline(day: Day, intents: list[Intent], exit_mode: str, rng: np.random.Generator) -> list[Trade]:
    """The setup's own entry intents, each with a coin-flip direction; a flipped entry gets mirrored stop and
    target levels and runs through the same fill model."""
    draws = {id(it): bool(rng.integers(2)) for it in intents if it.action == "enter"}
    return execute(day, intents, exit_mode, flip=lambda it: draws.get(id(it), False))


def option_iv(vol: float) -> float:
    """Daily volatility used to price the proxy option: realised vol marked up, with a floor."""
    return max(vol * IV_MARKUP, IV_FLOOR)


def option_proxy(side: int, s0: float, s1: float, m0: int, m1: int, close_min: int, vol: float | None
                 ) -> tuple[float, float, float]:
    """(delta-0.5 proxy without time decay, Bachelier proxy, entry premium in $ per share) for a 0DTE ATM long
    option; the returns are gross, in bps of premium. `vol` is realised daily vol (marked up by option_iv)."""
    if not vol or vol <= 0 or not np.isfinite(vol):
        return float("nan"), float("nan"), float("nan")
    t0 = max(close_min - m0, 1) / 390.0
    t1 = max(close_min - m1, 0) / 390.0
    sa = s0 * option_iv(vol)
    p0 = sa * math.sqrt(t0) * PHI0
    move = side * (s1 - s0)
    delta = max(0.5 * move / p0, -1.0) * 1e4
    s = sa * math.sqrt(t1)
    if s <= 0:
        v1 = max(move, 0.0)
    else:
        z = move / s
        v1 = move * 0.5 * (1.0 + math.erf(z / math.sqrt(2.0))) + s * PHI0 * math.exp(-0.5 * z * z)
    return delta, (v1 / p0 - 1.0) * 1e4, p0


def _row(kind: str, setup: str, sym: str, day: Day, side: int, em: int, ep: float, xm: int, xp: float,
         reason: str, risk: float | None, pub: float | None, vol: float | None) -> dict:
    d_bps, b_bps, prem = option_proxy(side, ep, xp, em, xm, day.close_min, vol)
    return {"kind": kind, "setup": setup, "symbol": sym, "date": day.date.isoformat(), "year": day.date.year,
            "side": side, "entry_time": day.ts(em).strftime("%H:%M"), "exit_time": day.ts(xm).strftime("%H:%M"),
            "entry_m": em, "exit_m": xm, "entry": ep, "exit": xp, "reason": reason, "hold_min": xm - em,
            "gross_bps": side * (xp / ep - 1.0) * 1e4,
            "r_mult": side * (xp - ep) / risk if risk else float("nan"),
            "pub_mult": pub if pub is not None else float("nan"), "opt_delta_bps": d_bps, "opt_bach_bps": b_bps,
            "opt_premium": prem}


# -------------------------------------------------------------------------------------------- day contexts
def to_days(bars: pd.DataFrame, cal: pd.DataFrame, closes: dict[date, float] | None = None) -> list[Day]:
    """Split cached bars (indexed by New York bar-start time) into sessions using the calendar; `closes` are
    the official daily closes (data.load_official_closes), attached as `Day.auction_close`."""
    sess = dt.sessions(cal)
    days = []
    if bars.empty:
        return days
    for d, g in bars.groupby(bars.index.date, sort=True):
        if d in sess:
            day = Day.from_frame(g, *sess[d])
            if closes and d in closes:
                day = replace(day, auction_close=float(closes[d]))
            days.append(day)
    return days


def tradable(day: Day, skip_half_days: bool = True) -> bool:
    """A session the backtest trades: data through the time exit, and not a half day (unless asked)."""
    return day.complete and not (skip_half_days and day.half_day)


def contexts(days: list[Day], cal: pd.DataFrame | None = None) -> list[Ctx]:
    """What is known before each session: yesterday's levels, the 14-day noise band, the 14-day daily
    volatility and the carried EMAs. Uses only earlier sessions."""
    prev_of: dict[date, date] = {}
    if cal is not None:
        ds = sorted(cal["date"])
        prev_of = {d: p for p, d in zip(ds[:-1], ds[1:])}
    moves = [noise_moves(d) for d in days]
    closes = np.array([d.c[-1] for d in days]) if days else np.array([])
    ema = None
    out = []
    for k, d in enumerate(days):
        prev = days[k - 1] if k > 0 else None
        if prev is not None and prev_of and prev_of.get(d.date) != prev.date:
            prev = None   # the previous calendar session is missing from the data
        vol = None
        if k >= 15:
            r = closes[k - 15:k][1:] / closes[k - 15:k][:-1] - 1.0
            vol = float(np.std(r, ddof=1))
        out.append(Ctx(prev_close=float(prev.c[-1]) if prev else None,
                       prev_close_auction=prev.auction_close if prev else None,
                       prev_high=float(prev.h.max()) if prev else None,
                       prev_low=float(prev.l.min()) if prev else None,
                       sigma=noise_sigma(moves[max(0, k - 14):k]), daily_vol=vol, ema=ema))
        ema = ema_after_day(ema, d)
    return out


def run(bars: dict[str, pd.DataFrame], cal: pd.DataFrame, start: date, end: date,
        setups: list[Setup] | None = None, seed: int = 0, skip_half_days: bool = True,
        closes: dict[str, dict[date, float]] | None = None) -> pd.DataFrame:
    """All trades (setup, random and coin rows) for tradable session dates in [start, end]."""
    setups = setups or list(SETUPS.values())
    rows: list[dict] = []
    for sym, df in bars.items():
        days = to_days(df, cal, (closes or {}).get(sym))
        for d, ctx in zip(days, contexts(days, cal)):
            if not start <= d.date <= end or not tradable(d, skip_half_days):
                continue
            for st in setups:
                intents = st.fn(d, ctx)
                trades = execute(d, intents, st.exit_mode)
                if not trades:
                    continue
                rng = np.random.default_rng([seed, zlib.crc32(f"{st.id}|{sym}|{d.date}".encode())])
                for t in trades:
                    rows.append(_row("setup", st.id, sym, d, t.side, t.entry_m, t.entry, t.exit_m, t.exit,
                                     t.reason, t.risk, t.pub_mult, ctx.daily_vol))
                for s, em, ep, xm, xp in random_baseline(d, trades, st.exit_mode, rng):
                    rows.append(_row("random", st.id, sym, d, s, em, ep, xm, xp, "random", None, None, ctx.daily_vol))
                for t in coin_baseline(d, intents, st.exit_mode, rng):
                    rows.append(_row("coin", st.id, sym, d, t.side, t.entry_m, t.entry, t.exit_m, t.exit,
                                     t.reason, None, None, ctx.daily_vol))
    return pd.DataFrame(rows, columns=ROW_COLS)


def split_date(dates: Iterable[date | str]) -> str:
    """Last date of the in-sample half (the first half of the sessions tested)."""
    ds = sorted({str(d) for d in dates})
    if not ds:
        return ""
    return ds[(len(ds) - 1) // 2]


# ---------------------------------------------------------------------------------------------- statistics
def _day_sums(df: pd.DataFrame, col: str, cost: float | tuple[float, float], days: list[str]
              ) -> tuple[np.ndarray, np.ndarray]:
    x = _net(df, col, cost)
    ok = x.notna()
    g = x[ok].groupby(df.loc[ok, "date"])
    return (g.sum().reindex(days, fill_value=0.0).to_numpy(dtype=float),
            g.count().reindex(days, fill_value=0).to_numpy(dtype=float))


def _boot_mean(s: np.ndarray, n: np.ndarray, idx: np.ndarray) -> np.ndarray:
    tot, cnt = s[idx].sum(axis=1), n[idx].sum(axis=1)
    return np.where(cnt > 0, tot / np.where(cnt > 0, cnt, 1.0), np.nan)


def _stats(g: pd.DataFrame, col: str, cost: float | tuple[float, float], days: list[str], idx: np.ndarray) -> dict:
    s = g[g["kind"] == "setup"].sort_values(["date", "entry_m"])
    x = _net(s, col, cost)
    ok = x.notna()
    x, s = x[ok].to_numpy(dtype=float), s[ok]
    out: dict = {"trades": len(x), "days": len(days)}
    if len(x) == 0:
        return out
    wins, losses = x[x > 0], x[x <= 0]
    cum = np.cumsum(usd_per_1000(x))
    peak = np.maximum.accumulate(np.r_[0.0, cum])[1:]
    loss_sum = -x[x < 0].sum()
    out.update({
        "win_rate": float(len(wins) / len(x)),
        "avg_win_bps": float(wins.mean()) if len(wins) else float("nan"),
        "avg_loss_bps": float(losses.mean()) if len(losses) else float("nan"),
        "expectancy_bps": float(x.mean()),
        "usd_per_trade": float(usd_per_1000(x.mean())),
        "profit_factor": float(wins.sum() / loss_sum) if loss_sum > 0 else float("inf"),
        "total_usd": float(cum[-1]),
        "max_dd_usd": float((peak - cum).max()),
        "avg_hold_min": float(s["hold_min"].mean()),
        "eod_exits": int((s["reason"] == "eod").sum()) if "reason" in s else 0,
        "avg_r_gross": float(s["r_mult"].mean()) if s["r_mult"].notna().any() else float("nan"),
        "pub_sizing_pct": float((s["pub_mult"] * x / 100.0).sum()) if s["pub_mult"].notna().any()
        else float("nan"),
    })
    ss, sn = _day_sums(s, col, cost, days)
    enough = len(days) >= MIN_BOOT_DAYS
    mb = _boot_mean(ss, sn, idx) if enough else None
    if enough:
        out["ci_lo_bps"], out["ci_hi_bps"] = (float(np.nanpercentile(mb, 2.5)), float(np.nanpercentile(mb, 97.5)))
    for kind in ("random", "coin"):
        b = g[g["kind"] == kind]
        bs, bn = _day_sums(b, col, cost, days)
        if bn.sum() == 0:
            continue
        out[f"{kind}_expectancy_bps"] = float(bs.sum() / bn.sum())
        out[f"vs_{kind}_bps"] = float(x.mean() - bs.sum() / bn.sum())
        if enough:
            diff = mb - _boot_mean(bs, bn, idx)
            out[f"p_vs_{kind}"] = float((1 + np.sum(diff <= 0)) / (1 + np.sum(np.isfinite(diff))))
    return out


def metrics(trades: pd.DataFrame, split_mid: str, costs: dict[str, float] = COSTS, boot: int = BOOT,
            seed: int = 0) -> pd.DataFrame:
    """One row per setup x symbol x split (all, IS, OOS, Yyyyy) x cost scenario. The 95% interval and the
    p-values come from a bootstrap over DAYS (trades on the same day are not independent); p is one-sided:
    the share of resamples where the setup did not beat the baseline."""
    rows = []
    if trades.empty:
        return pd.DataFrame(columns=METRIC_KEYS)
    t = trades.copy()
    t["date"] = t["date"].astype(str)
    is_mask = t["date"] <= split_mid
    for (setup, sym), g in t.groupby(["setup", "symbol"], sort=True):
        ism = is_mask[g.index]
        parts = [("all", g), ("IS", g[ism]), ("OOS", g[~ism])] + [(f"Y{y}", gy) for y, gy in g.groupby("year")]
        for split, gs in parts:
            days = sorted(gs.loc[gs["kind"] == "setup", "date"].unique())
            if not days:
                continue
            rng = np.random.default_rng([seed, zlib.crc32(f"{setup}|{sym}|{split}".encode())])
            idx = rng.integers(0, len(days), size=(boot, len(days)))
            spec = SETUPS.get(setup)
            for name, col, cost in scenarios(costs):
                row = {"setup": setup, "symbol": sym, "primary": bool(spec and sym in spec.primary),
                       "split": split, "scenario": name,
                       "cost_per_side": cost[0] * 100.0 if isinstance(cost, tuple) else cost,
                       "opt_tick_usd": cost[1] if isinstance(cost, tuple) else float("nan")}
                row.update(_stats(gs, col, cost, days, idx))
                rows.append(row)
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=METRIC_KEYS)
