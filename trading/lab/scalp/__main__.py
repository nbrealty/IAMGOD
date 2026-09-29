"""Command line for the scalp lab (run from trading/):

    python -m lab.scalp download --symbols SPY QQQ --start 2024-09-03 --end 2026-09-25
    python -m lab.scalp backtest --symbols SPY QQQ --start 2024-09-03 --end 2026-09-25 [--setups ORB5_QQQ ...]
    python -m lab.scalp report [--cost realistic=1.5 ...]

Costs are per side: --cost quoted=0.25 low=0.5 realistic=1.5 pessimistic=4 (bps of notional),
opt_realistic=2 opt_pessimistic=5 (% of option premium), opt_tick_realistic=0.01 opt_tick_pessimistic=0.02
($ per share half-spread; an option pays the larger of the two).
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from . import backtest as bt
from . import data as dt
from . import report as rp
from .signals import SETUPS


def _date(s: str) -> date:
    return date.fromisoformat(s)


def _costs(pairs: list[str] | None) -> dict[str, float]:
    costs = dict(bt.COSTS)
    for p in pairs or []:
        k, _, v = p.partition("=")
        if k not in costs:
            raise SystemExit(f"unknown cost '{k}'; known: {', '.join(costs)}")
        costs[k] = float(v)
    return costs


def cmd_download(a: argparse.Namespace) -> int:
    counts = dt.download([s.upper() for s in a.symbols], a.start, a.end, Path(a.cache), adjustment=a.adjustment)
    print("rows cached (regular session, incl. warm-up):", counts)
    return 0


def _print_table(m: pd.DataFrame, split: str = "all", scenario: str = "realistic") -> None:
    if m.empty:
        print("no trades")
        return
    t = m[(m["split"] == split) & (m["scenario"] == scenario)]
    if t.empty:
        print("no trades")
        return
    cols = ["setup", "symbol", "trades", "win_rate", "expectancy_bps", "ci_lo_bps", "ci_hi_bps", "usd_per_trade",
            "total_usd", "avg_hold_min", "vs_random_bps", "p_vs_random"]
    with pd.option_context("display.width", 200, "display.max_columns", 20, "display.float_format", "{:.3f}".format):
        print(t[[c for c in cols if c in t]].to_string(index=False))


def _report(trades: pd.DataFrame, meta: dict, costs: dict[str, float], out: Path, boot: int) -> dict:
    meta = {**meta, "costs": costs, "boot": boot, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    m = bt.metrics(trades, meta["split_mid"], costs, boot=boot, seed=int(meta.get("seed", 0)))
    paths = rp.write(m, meta, out)
    _print_table(m)
    alpha = rp.alpha_for(m)
    if rp.boot_too_small(boot, alpha):
        print(f"\nWARNING: --boot {boot} cannot give p below the verdict bar {alpha:.5f}; "
              f"use --boot {int(1 / alpha) + 1} or more")
    print("\nwrote:", *[str(p) for p in paths.values()], sep="\n  ")
    return paths


def cmd_backtest(a: argparse.Namespace) -> int:
    syms = [s.upper() for s in a.symbols]
    cache, out = Path(a.cache), Path(a.out)
    if a.download:
        dt.download(syms, a.start, a.end, cache, adjustment=a.adjustment)
    cal = dt.load_calendar(cache)
    s0 = a.start - timedelta(days=dt.WARMUP_DAYS)
    bars = {s: dt.load_bars(s, s0, a.end, cache) for s in syms}
    closes = {s: dt.load_official_closes(s, s0, a.end, cache) for s in syms}
    for s, df in bars.items():
        if df.empty:
            raise SystemExit(f"no cached bars for {s}: run `python -m lab.scalp download --symbols {s} ...` first")
    setups = [SETUPS[k] for k in a.setups] if a.setups else list(SETUPS.values())
    trades = bt.run(bars, cal, a.start, a.end, setups, seed=a.seed, closes=closes)
    days = [d for df in bars.values() for d in bt.to_days(df, cal) if a.start <= d.date <= a.end]
    full = {d.date.isoformat() for d in days if bt.tradable(d)}
    partial = sorted({d.date.isoformat() for d in days if not d.complete and not d.half_day})
    if partial:
        print(f"skipped {len(partial)} session(s) whose data stop before the 15:55 time exit "
              f"(in progress or cut short): {', '.join(partial[:10])}")
    meta = {"symbols": syms, "start": a.start.isoformat(), "end": a.end.isoformat(), "sessions": len(full),
            "split_mid": bt.split_date(full), "seed": a.seed, "setups": [s.id for s in setups],
            "adjustment": a.adjustment, "incomplete_sessions_skipped": partial}
    rp.save_trades(trades, meta, out)
    n = trades[trades["kind"] == "setup"].groupby(["setup", "symbol"]).size() if not trades.empty else {}
    print(f"{len(full)} sessions; setup trades per setup/symbol:\n{n}\n")
    _report(trades, meta, _costs(a.cost), out, a.boot)
    return 0


def cmd_report(a: argparse.Namespace) -> int:
    out = Path(a.out)
    trades, meta = rp.load_trades(out)
    _report(trades, meta, _costs(a.cost), out, a.boot)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m lab.scalp", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser, dates: bool = True) -> None:
        if dates:
            sp.add_argument("--symbols", nargs="+", default=["SPY", "QQQ"])
            sp.add_argument("--start", type=_date, required=True)
            sp.add_argument("--end", type=_date, required=True)
            sp.add_argument("--adjustment", default="all", choices=["all", "split"])
        sp.add_argument("--cache", default=str(dt.CACHE_DIR))

    d = sub.add_parser("download", help="fetch and cache regular-session SIP 1-minute bars")
    common(d)
    d.set_defaults(fn=cmd_download)

    b = sub.add_parser("backtest", help="run every setup and baseline on cached bars, then report")
    common(b)
    b.add_argument("--setups", nargs="+", choices=sorted(SETUPS))
    b.add_argument("--seed", type=int, default=0)
    b.add_argument("--boot", type=int, default=bt.BOOT)
    b.add_argument("--cost", nargs="+", metavar="NAME=VALUE")
    b.add_argument("--out", default=str(rp.OUT_DIR))
    b.add_argument("--download", action="store_true", help="download missing bars first")
    b.set_defaults(fn=cmd_backtest)

    r = sub.add_parser("report", help="recompute metrics from the saved trades (e.g. with other costs)")
    common(r, dates=False)
    r.add_argument("--boot", type=int, default=bt.BOOT)
    r.add_argument("--cost", nargs="+", metavar="NAME=VALUE")
    r.add_argument("--out", default=str(rp.OUT_DIR))
    r.set_defaults(fn=cmd_report)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
