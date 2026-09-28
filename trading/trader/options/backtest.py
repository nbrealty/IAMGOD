"""OPT-37 options backtester: the monthly SPY bull put spread replayed with model prices (the RPL method).

Method (reports/Options rulebook.md, source RPL): Black-Scholes on RAW (not dividend-adjusted) daily closes, the
Cboe volatility index for the underlying times the calibrated skew table (`config/options_skew.yaml`), the
3-month T-bill rate of each date, and the one cost model: each leg's quoted spread is 2.5% of its price
(at least $0.01), half of it paid on each side, plus $0.04 per contract per leg per side.

Per monthly cycle: enter at the first session with DTE <= 36 (and >= 30) to the standard monthly expiry; short put
at the $1 strike whose model |delta| is nearest 0.20 inside 0.15-0.25; long put `width` lower. Exit at the first
session with DTE <= 7 (OPT-22) or a close below the short strike (OPT-23), at the model mid + half the quoted cost.
R = (P&L - costs) / MaxLoss per contract, MaxLoss = (width - entry credit) x 100 (size does not change R).

It always prints, next to the base: the width actually traded (as a share of spot and as fixed dollars), the
doubled-cost run, the biased flat-volatility and realised-volatility runs, a cross-check against Cboe PUT for
2008, 2018, 2020 and 2022 (years without SPY bars say so), plus the OPT-19 regime run, the OPT-13 cost-filter run
and the OPT-40 (iii) +-25% parameter runs. Results are saved to `state_dir/options/backtest/latest.json`, which the
OPT-40 gate reads. In sample, model-priced: never a reason to trade by itself (OPT-40).

Run: `python -m trader.options.backtest [--start 2016-01-04] [--end YYYY-MM-DD] [--width-usd 2] [--json]`.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import STATE_DIR
from . import book as ob
from . import pricing
from . import shadow as osh
from .models import MULTIPLIER

QUOTED_SPREAD_SHARE = 0.025  # RPL: each leg's quoted spread = 2.5% of its price
MIN_LEG_SPREAD = 0.01
FEE_PER_CONTRACT = 0.04  # per contract per leg per side
CROSSCHECK_YEARS = (2008, 2018, 2020, 2022)
VOL_INDEX = {"SPY": "VIX", "QQQ": "VXN", "IWM": "RVX", "DIA": "VXD"}
REGIME_MIN_CLOSES = 260


@dataclass(frozen=True)
class Params:
    """One replay's settings. `width_pct` (share of spot) wins over `width_usd` when both are set."""

    width_usd: float | None = 2.0
    width_pct: float | None = None
    target_delta: float = 0.20
    delta_band: tuple = (0.15, 0.25)
    entry_first: int = 36
    entry_last: int = 30
    exit_dte: int = 7
    cost_mult: float = 1.0
    vol_mode: str = "skew"  # "skew" (base), "flat" (index, no skew), "realised" (20-day realised vol, no skew)
    regime_filter: bool = False  # True: OPT-19 at 1 contract (only bull_calm trades)
    cost_filter: float | None = None  # OPT-13: skip when quoted cost > this share of the mid credit
    short_strike_exit: bool = True  # OPT-23
    underlying: str = "SPY"
    strike_step: float = 1.0


# --- inputs ---------------------------------------------------------------------------------------------------


def clean_series(s: pd.Series | None) -> pd.Series:
    """Finite positive values on a naive, normalized, sorted, de-duplicated date index."""
    if s is None or len(s) == 0:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    idx = pd.DatetimeIndex(s.index)
    idx = idx.tz_convert("America/New_York").tz_localize(None) if idx.tz is not None else idx
    out = pd.Series(pd.to_numeric(pd.Series(np.asarray(s)), errors="coerce").to_numpy(float), index=idx.normalize())
    out = out[np.isfinite(out.to_numpy()) & (out.to_numpy() > 0)]
    return out[~out.index.duplicated(keep="last")].sort_index()


def monthly_expiry(year: int, month: int, sessions: pd.DatetimeIndex) -> pd.Timestamp:
    """Third Friday; the Thursday before when that Friday is not a session (holiday) and the Thursday is."""
    tf = pd.Timestamp(ob.third_friday(year, month))
    if len(sessions) and tf not in sessions and tf <= sessions[-1] and (tf - pd.Timedelta(days=1)) in sessions:
        return tf - pd.Timedelta(days=1)
    return tf


def realised_vol(closes: pd.Series, n: int = 20) -> pd.Series:
    """Annualised close-to-close volatility over `n` sessions (the biased realised-vol run of OPT-37)."""
    r = np.log(closes).diff()
    return r.rolling(n).std() * math.sqrt(252)


def regime_label(closes: pd.Series, day) -> str | None:
    """REG-2 label on closes up to `day` (None with too little history: OPT-19 then gives 0)."""
    s = closes[closes.index <= pd.Timestamp(day)]
    if len(s) < REGIME_MIN_CLOSES:
        return None
    from ..regime import _trend_fields

    return _trend_fields(s)["label"]


# --- pricing helpers -------------------------------------------------------------------------------------------


def leg_spread(price: float, cost_mult: float = 1.0) -> float:
    """RPL cost model: a leg's quoted spread (ask - bid) is 2.5% of its price, at least one cent."""
    return max(MIN_LEG_SPREAD, QUOTED_SPREAD_SHARE * max(0.0, price)) * cost_mult


def _vol_input(day, vix: pd.Series, rv: pd.Series, params: Params) -> float | None:
    src = rv if params.vol_mode == "realised" else vix
    return pricing.index_on(src, day, 5)


def price_put(spot, strike, dte, vol, params: Params, table: dict, rate) -> dict:
    mode = "skew" if params.vol_mode == "skew" else "flat"
    return pricing.model_quote(spot, strike, max(dte, 0), vol, "put", table, rate=rate,
                               underlying=params.underlying, mode=mode)


def choose_short(spot, dte, vol, params: Params, table: dict, rate) -> tuple[float, dict] | None:
    """OPT-18: the $1 strike whose model |delta| is nearest the target inside the band (ties: smaller |delta|)."""
    lo, hi = params.delta_band
    step = params.strike_step
    k = math.floor(spot / step) * step
    best = None
    while k > spot * 0.5:
        q = price_put(spot, k, dte, vol, params, table, rate)
        d = abs(q["delta"])
        if lo - 1e-9 <= d <= hi + 1e-9:
            key = (round(abs(d - params.target_delta), 6), d)
            if best is None or key < best[0]:
                best = (key, k, q)
        elif d < lo:
            break
        k -= step
    return (best[1], best[2]) if best else None


def spread_width(spot: float, params: Params) -> float:
    """The width in dollars: a share of spot (RPL) or fixed dollars, never below one strike step."""
    w = params.width_pct * spot if params.width_pct else float(params.width_usd or 0.0)
    return max(params.strike_step, w)


def spread_quote(spot, short_k, width, dte, vol, params, table, rate) -> dict:
    s = price_put(spot, short_k, dte, vol, params, table, rate)
    lg = price_put(spot, short_k - width, dte, vol, params, table, rate)
    qc = leg_spread(s["price"], params.cost_mult) + leg_spread(lg["price"], params.cost_mult)
    return {"mid": s["price"] - lg["price"], "quoted_cost": qc, "short_delta": s["delta"]}


# --- one replay ------------------------------------------------------------------------------------------------


def _entry_day(sessions: pd.DatetimeIndex, expiry: pd.Timestamp, params: Params) -> pd.Timestamp | None:
    for d in sessions[(sessions < expiry)]:
        days = (expiry - d).days
        if params.entry_last <= days <= params.entry_first:
            return d
    return None


def _one_cycle(expiry, closes, vix, rv, rates, params: Params, table: dict) -> dict:
    """Replay one monthly cycle. Returns a trade record or {"skipped": reason}."""
    sessions = closes.index
    day = _entry_day(sessions, expiry, params)
    if day is None:
        return {"skipped": "no session in the entry window", "expiry": expiry.date().isoformat()}
    spot, dte = float(closes[day]), (expiry - day).days
    vol, rate = _vol_input(day, vix, rv, params), pricing.index_on(rates, day, 7)
    if vol is None:
        return {"skipped": "no volatility input", "expiry": expiry.date().isoformat()}
    if params.regime_filter and ob.permission(regime_label(closes, day), {}) < 1.0:
        return {"skipped": "OPT-19 regime", "expiry": expiry.date().isoformat()}
    pick = choose_short(spot, dte, vol, params, pricing._table(table), rate)
    if pick is None:
        return {"skipped": "OPT-18 no strike in the delta band", "expiry": expiry.date().isoformat()}
    short_k, _ = pick
    width = spread_width(spot, params)
    q = spread_quote(spot, short_k, width, dte, vol, params, table, rate)
    credit = q["mid"] - 0.5 * q["quoted_cost"]
    if params.cost_filter is not None and (q["mid"] <= 0 or q["quoted_cost"] / q["mid"] > params.cost_filter):
        return {"skipped": "OPT-13 cost filter", "expiry": expiry.date().isoformat()}
    if credit <= 0 or credit >= width:
        return {"skipped": "no positive credit after costs", "expiry": expiry.date().isoformat()}
    return _hold(day, expiry, spot, short_k, width, credit, q, closes, vix, rv, rates, params, table)


def _hold(day, expiry, spot, short_k, width, credit, q, closes, vix, rv, rates, params, table) -> dict:
    """Walk the sessions after entry until OPT-22 or OPT-23 fires; exit at model mid + half the quoted cost."""
    fee = FEE_PER_CONTRACT * params.cost_mult
    max_loss = (width - credit) * MULTIPLIER
    for d in closes.index[closes.index > day]:
        s, dte = float(closes[d]), (expiry - d).days
        below = params.short_strike_exit and s < short_k
        if dte > params.exit_dte and not below:
            continue
        vol = _vol_input(d, vix, rv, params)
        if vol is None:
            continue
        x = spread_quote(s, short_k, width, dte, vol, params, table, pricing.index_on(rates, d, 7))
        debit = max(0.0, x["mid"]) + 0.5 * x["quoted_cost"]
        pnl = (credit - debit) * MULTIPLIER - 4 * fee
        return {"entry_date": day.date().isoformat(), "date": d.date().isoformat(),
                "expiry": expiry.date().isoformat(), "spot": spot, "short_strike": short_k, "width": width,
                "width_pct": width / spot, "entry_mid": q["mid"], "entry_quoted_cost": q["quoted_cost"],
                "entry_credit": credit, "exit_debit": debit, "exit_reason": "OPT-23" if below else "OPT-22",
                "max_loss": max_loss, "contracts": 1, "pnl": pnl, "R": pnl / max_loss, "R_paper": pnl / max_loss,
                "tags": {"bil_rate": pricing.index_on(rates, day, 7)}}
    return {"skipped": "still open at the end of the data", "expiry": expiry.date().isoformat()}


def replay(closes: pd.Series, vix: pd.Series, params: Params = Params(), *, rates: pd.Series | None = None,
           table: dict | None = None, start=None, end=None) -> dict:
    """Run one replay over every standard monthly expiry between start and end. Pure: no network.

    `closes` are RAW daily closes of the underlying, `vix` its volatility index (fraction or points), `rates`
    the T-bill rate (fraction; the table's default rate is used when missing). Returns {params, trades, skipped,
    stats (OPT-38)}.
    """
    closes, vix = clean_series(closes), clean_series(vix)
    rates = clean_series(rates) if rates is not None else None
    table = table or pricing.default_skew_table()
    if closes.empty:
        return {"params": asdict(params), "trades": [], "skipped": [], "stats": osh.opt38_stats([]),
                "problems": ["no closes"]}
    rv = realised_vol(closes)
    lo = pd.Timestamp(start) if start else closes.index[0]
    hi = pd.Timestamp(end) if end else closes.index[-1]
    trades, skipped = [], []
    for per in pd.period_range(lo, hi, freq="M"):
        exp = monthly_expiry(per.year, per.month, closes.index)
        if exp < lo or exp > hi + pd.Timedelta(days=40):
            continue
        rec = _one_cycle(exp, closes, vix, rv, rates, params, table)
        (skipped if "skipped" in rec else trades).append(rec)
    return {"params": asdict(params), "trades": trades, "skipped": skipped, "stats": osh.opt38_stats(trades)}


# --- the full OPT-37 report ---------------------------------------------------------------------------------------


def _pm25(base: Params) -> dict[str, Params]:
    """OPT-40 (iii): each parameter moved -25% and +25%."""
    out = {}
    for f in (0.75, 1.25):
        tag = "m25" if f < 1 else "p25"
        out[f"delta_{tag}"] = replace(base, target_delta=base.target_delta * f,
                                      delta_band=tuple(x * f for x in base.delta_band))
        out[f"dte_{tag}"] = replace(base, entry_first=round(base.entry_first * f), entry_last=round(base.entry_last * f))
        out[f"exit_dte_{tag}"] = replace(base, exit_dte=round(base.exit_dte * f))
        out[f"width_{tag}"] = replace(base, width_pct=base.width_pct * f if base.width_pct else None,
                                      width_usd=(base.width_usd or 0) * f if not base.width_pct else base.width_usd)
    return out


def yearly_r(trades: list[dict]) -> dict[int, float]:
    out: dict[int, float] = {}
    for t in trades:
        y = pd.Timestamp(t["date"]).year
        out[y] = out.get(y, 0.0) + float(t["R"])
    return out


def put_crosscheck(trades: list[dict], put_index: pd.Series | None, years=CROSSCHECK_YEARS) -> dict:
    """OPT-37: the strategy's summed R per year next to Cboe PUT's calendar-year return, and whether signs agree."""
    s = clean_series(put_index)
    ours = yearly_r(trades)
    out = {}
    for y in years:
        yr = s[s.index.year == y]
        prev = s[s.index.year == y - 1]
        put_ret = (float(yr.iloc[-1]) / float(prev.iloc[-1]) - 1) if len(yr) and len(prev) else None
        r = ours.get(y)
        out[str(y)] = {"put_return": put_ret, "strategy_sum_R": r,
                       "signs_agree": None if put_ret is None or r is None else (put_ret > 0) == (r > 0),
                       "note": None if r is not None else "no trades that year (no underlying bars?)"}
    return out


def full_report(closes: pd.Series, vix: pd.Series, *, rates=None, put_index=None, table=None, width_usd: float = 2.0,
                start=None, end=None, underlying: str = "SPY") -> dict:
    """Every OPT-37 run side by side (see the module docstring). Pure: no network."""
    c = clean_series(closes)
    last = float(c.iloc[-1]) if len(c) else None
    pct = (width_usd / last) if last else None
    base = Params(width_usd=None, width_pct=pct, underlying=underlying) if pct else Params(underlying=underlying)
    runs = {"base": base, "fixed_dollars": replace(base, width_pct=None, width_usd=width_usd),
            "doubled_costs": replace(base, cost_mult=2.0), "flat_vol": replace(base, vol_mode="flat"),
            "realised_vol": replace(base, vol_mode="realised"), "opt19_regime": replace(base, regime_filter=True),
            "opt13_filter": replace(base, cost_filter=0.20), "hold7_no_opt23": replace(base, short_strike_exit=False)}
    kw = {"rates": rates, "table": table, "start": start, "end": end}
    res = {name: replay(closes, vix, p, **kw) for name, p in runs.items()}
    sens = {name: replay(closes, vix, p, **kw)["stats"] for name, p in _pm25(base).items()}
    out = {"underlying": underlying, "width_usd": width_usd, "width_pct_of_last_spot": pct,
           "method": "RPL: Black-Scholes on raw closes, vol index x skew table, 2.5% leg spreads, $0.04 fees",
           "in_sample_warning": "model-priced and in sample; never a reason to trade by itself (OPT-40)",
           "sensitivity": sens, "put_crosscheck": put_crosscheck(res["base"]["trades"], put_index)}
    for name, r in res.items():
        out[name] = {**r["stats"], "n_skipped": len(r["skipped"]),
                     "avg_width_pct": _avg(t["width_pct"] for t in r["trades"]),
                     "avg_width_usd": _avg(t["width"] for t in r["trades"])}
    out["bil_E"] = out["base"]["benchmarks"]["bil_E"]
    out["trades"] = res["base"]["trades"]
    return out


def _avg(xs):
    xs = [float(x) for x in xs]
    return sum(xs) / len(xs) if xs else None


def summary_lines(rep: dict) -> list[str]:
    """Plain-English lines for the terminal."""
    def f(x, fmt="{:+.3f}"):
        return "n/a" if x is None else fmt.format(x)

    lines = [f"OPT-37 backtest {rep['underlying']} (model-priced, in sample; indicative only)",
             f"width traded: ${rep['width_usd']:g} = {f(rep['width_pct_of_last_spot'], '{:.2%}')} of the last spot"]
    for name in ("base", "fixed_dollars", "doubled_costs", "flat_vol", "realised_vol", "opt19_regime",
                 "opt13_filter", "hold7_no_opt23"):
        s = rep[name]
        lines.append(f"  {name:15s} n={s['n']:3d}  E={f(s['E'])}R  win={f(s['win_rate'], '{:.0%}')}  "
                     f"worst={f(s['worst_R'], '{:+.2f}')}R  SQN={f(s['sqn'], '{:.2f}')}  "
                     f"width=${f(s['avg_width_usd'], '{:.2f}')}")
    lines.append(f"  BIL on collateral: E={f(rep['bil_E'])}R")
    for name, s in rep["sensitivity"].items():
        lines.append(f"  +-25% {name:14s} n={s['n']:3d}  E={f(s['E'])}R")
    for y, v in rep["put_crosscheck"].items():
        lines.append(f"  PUT {y}: PUT {f(v['put_return'], '{:+.1%}')}  ours {f(v['strategy_sum_R'], '{:+.2f}')}R  "
                     f"agree={v['signs_agree']}")
    return lines


def save_report(rep: dict, state_dir=None) -> Path:
    p = Path(state_dir or STATE_DIR) / "options" / "backtest" / "latest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(rep, indent=2, default=str))
    tmp.replace(p)
    return p


# --- script entry point -------------------------------------------------------------------------------------------


def _load_inputs(args, closes, vix, rates, put_index, state_dir) -> tuple:
    """Fetch what was not injected: raw closes from Alpaca, the Cboe index, DTB3 and PUT (read-only)."""
    problems = []
    if closes is None:
        from ..data import AlpacaData

        bars = AlpacaData.from_env().history([args.underlying], args.start, args.end, adjustment="raw")
        closes = bars[args.underlying]["close"]
    if vix is None:
        vix = pricing.fetch_cboe_index(VOL_INDEX.get(args.underlying, "VIX"), state_dir=state_dir)
    if rates is None:
        try:
            rates = pricing.fetch_tbill_rates(state_dir=state_dir)
        except Exception as e:  # noqa: BLE001 - the table's default rate is used and reported
            problems.append(f"T-bill rates unavailable ({e}); default rate used")
    if put_index is None:
        try:
            put_index = pricing.fetch_cboe_index("PUT", state_dir=state_dir, units="points")
        except Exception as e:  # noqa: BLE001 - the cross-check then says unavailable
            problems.append(f"Cboe PUT unavailable ({e}); no cross-check")
    return closes, vix, rates, put_index, problems


def main(argv=None, *, closes=None, vix=None, rates=None, put_index=None, state_dir=None) -> int:
    """`python -m trader.options.backtest`: print every OPT-37 run and save latest.json for the OPT-40 gate."""
    ap = argparse.ArgumentParser(prog="python -m trader.options.backtest", description=__doc__.split("\n")[0])
    ap.add_argument("--start", default="2016-01-04")
    ap.add_argument("--end", default=None)
    ap.add_argument("--width-usd", type=float, default=2.0)
    ap.add_argument("--underlying", default="SPY")
    ap.add_argument("--json", action="store_true", help="print the full report as JSON")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)
    try:
        closes, vix, rates, put_index, problems = _load_inputs(args, closes, vix, rates, put_index, state_dir)
    except Exception as e:  # noqa: BLE001 - say what is missing instead of a traceback
        print(f"cannot load backtest inputs: {type(e).__name__}: {e}")
        return 2
    rep = full_report(closes, vix, rates=rates, put_index=put_index, width_usd=args.width_usd, start=args.start,
                      end=args.end, underlying=args.underlying)
    rep["problems"] = problems
    if not args.no_save:
        rep["saved_to"] = str(save_report(rep, state_dir))
    print(json.dumps(rep, indent=2, default=str) if args.json else "\n".join(summary_lines(rep) + problems))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
