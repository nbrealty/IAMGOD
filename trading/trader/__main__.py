"""Command line: python -m trader {run,status,report,kill}"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

from .config import ROOT, STATE_DIR, load_config
from .engine import BOOKS, run_book
from .state import BookState, kill_switch_on, set_kill_switch

HISTORY_DAYS = 900  # trading days: the regime needs 24 months of returns plus a volatility history


def load_dotenv(path=ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip())


def cmd_run(args) -> int:
    from .broker import AlpacaPaperBroker, SimBroker
    from .data import AlpacaData
    from .llm import ClaudeAdvisor

    cfg = load_config()
    bars = AlpacaData.from_env().daily_bars(cfg.allowlist(), HISTORY_DAYS)
    bench = cfg.playbook["regime"]["benchmark"]
    as_of = bars[bench].index[-1]
    prices = {s: float(df["close"].iloc[-1]) for s, df in bars.items() if len(df)}

    advisor = None
    if not args.no_claude:
        if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
            print("warning: no ANTHROPIC_API_KEY; running without Claude", file=sys.stderr)
        else:
            advisor = ClaudeAdvisor(cfg)

    books = BOOKS if args.book == "both" else (args.book,)
    for book in books:
        state = BookState.load(book)
        if args.sim:
            if not state.sim:
                state.sim = {"cash": float(cfg.playbook["simulation"]["starting_cash"]), "positions": {}}
            broker = SimBroker(state.sim, prices, cfg.policy["turnover"]["cost_model_per_side_bps"], cfg.asset_class)
        else:
            broker = AlpacaPaperBroker.for_book(book, cfg.crypto_symbols())
        entry = run_book(book, cfg, bars, broker, advisor, as_of, dry_run=args.dry_run, force=args.force,
                         state=state)
        print_entry(entry)
    return 0


def print_entry(e: dict) -> None:
    if "skipped" in e:
        print(f"[{e['book']}] skipped: {e['skipped']}")
        return
    print(f"\n=== {e['book']} book, {e['date']}{' (dry run)' if e['dry_run'] else ''} ===")
    print(f"equity {e['equity']:,.2f}  drawdown {e['drawdown']:.1%}  regime {e['regime']}")
    print("sleeve weights: " + ", ".join(f"{k} {v:.0%}" for k, v in e["sleeve_weights"].items()))
    if e.get("claude"):
        print(f"claude: {e['claude'].get('journal_note', '')}")
    if e.get("claude_error"):
        print(f"claude error: {e['claude_error']}")
    for line in e["risk_log"]:
        print(f"  risk: {line}")
    for o in e["orders"]:
        print(f"  order: {o['side']} {o['qty']} {o['symbol']} @~{o['price']:.2f}  {o['reason']}")
    if not e["orders"]:
        print("  no orders")


def cmd_status(args) -> int:
    print(f"kill switch: {'ON' if kill_switch_on() else 'off'}")
    for book in BOOKS:
        s = BookState.load(book)
        if not s.equity_history:
            print(f"\n[{book}] no runs yet")
            continue
        last = s.equity_history[-1]
        dd = 1 - last["equity"] / s.peak_equity if s.peak_equity else 0
        print(f"\n[{book}] last run {s.last_run_date}  equity {last['equity']:,.2f}  drawdown {dd:.1%}"
              f"{'  HALTED' if s.halted else ''}")
        for sleeve, held in sorted(s.lots.items()):
            for sym, l in held.items():
                stop = f"stop {l.stop:.2f}" if l.stop else "no stop"
                print(f"  {sleeve} {sym:8s} qty {l.qty:.4f}  entry {l.entry_price:.2f} on {l.entry_date}  {stop}")
        if s.notes:
            print(f"  last note ({s.notes[-1]['date']}): {s.notes[-1]['note']}")
    return 0


def _stats(values: list[float]) -> dict:
    v = pd.Series(values, dtype=float)
    if len(v) < 2:
        return {"return": 0.0, "max_drawdown": 0.0, "sharpe": float("nan")}
    rets = v.pct_change().dropna()
    dd = float((1 - v / v.cummax()).max())
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else float("nan")
    return {"return": float(v.iloc[-1] / v.iloc[0] - 1), "max_drawdown": dd, "sharpe": sharpe}


def cmd_report(args) -> int:
    rows = []
    bench_done = False
    for book in BOOKS:
        s = BookState.load(book)
        if len(s.equity_history) < 2:
            continue
        st = _stats([h["equity"] for h in s.equity_history])
        trades = s.closed_trades
        rs = [t["R"] for t in trades if t.get("R") is not None]
        rows.append({"book": book, "days": len(s.equity_history), **st, "trades": len(trades),
                     "win_rate": np.mean([t["pnl"] > 0 for t in trades]) if trades else float("nan"),
                     "avg_R": float(np.mean(rs)) if rs else float("nan")})
        if not bench_done:
            rows.append({"book": "SPY buy&hold", "days": len(s.equity_history),
                         **_stats([h["benchmark"] for h in s.equity_history])})
            bench_done = True
    if not rows:
        print("Not enough history yet: each book needs at least two daily runs.")
        return 0
    df = pd.DataFrame(rows).set_index("book")
    print(df.to_string(float_format=lambda x: f"{x:.3f}"))
    return 0


def cmd_kill(args) -> int:
    set_kill_switch(args.state == "on")
    if args.state == "off" and args.reset_halt:
        for book in BOOKS:
            s = BookState.load(book)
            if s.halted or args.reset_peak:
                s.halted = False
                if args.reset_peak and s.equity_history:
                    s.peak_equity = s.equity_history[-1]["equity"]
                s.save()
    print(f"kill switch {'ON: no new entries, exits only' if args.state == 'on' else 'off'}")
    return 0


def main(argv=None) -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="trader", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run today's cycle")
    r.add_argument("--book", choices=[*BOOKS, "both"], default="both")
    r.add_argument("--sim", action="store_true", help="use the local simulator instead of Alpaca paper accounts")
    r.add_argument("--dry-run", action="store_true", help="compute everything, place no orders, save nothing")
    r.add_argument("--no-claude", action="store_true", help="skip Claude (the Claude book then only enforces stops)")
    r.add_argument("--force", action="store_true", help="run again even if this date already ran")
    r.set_defaults(func=cmd_run)
    sub.add_parser("status", help="positions, drawdown and last note per book").set_defaults(func=cmd_status)
    sub.add_parser("report", help="compare both books with SPY buy-and-hold").set_defaults(func=cmd_report)
    k = sub.add_parser("kill", help="turn the kill switch on or off")
    k.add_argument("state", choices=["on", "off"])
    k.add_argument("--reset-halt", action="store_true", help="also clear a drawdown halt (human decision)")
    k.add_argument("--reset-peak", action="store_true", help="with --reset-halt, restart drawdown from today")
    k.set_defaults(func=cmd_kill)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
