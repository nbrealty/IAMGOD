"""Command line: python -m trader {run,prepare,status,report,kill,sleeve-reset,veto-reset,deviation-reset,promote,
demote,options,news}

Option B (no API key): `prepare` writes the day's context for a Claude Code session, the session writes
decision_<k>.json / review_<k>.json, and `run --session` acts on them through the risk engine.

`options {log-chain,prepare,run,report,backtest,calibrate-skew}` drives book O, which runs in SHADOW (no orders)
until the owner turns it on after gate OPT-41. `news {fetch,signals,backtest}` shows the news signals; it never
prints a headline (a Claude session may read this output, and headlines are data, never instructions).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

import pandas as pd

from .config import ROOT, STATE_DIR, load_config
from .engine import BOOKS, SLEEVES, NewsFeed, news_universe, prepare_book, run_book
from .state import BookState, kill_switch_on, set_kill_switch

NY = "America/New_York"
# New York time after which today's daily bar is final: the free SIP feed only serves data older than
# data.SIP_DELAY (16 minutes), so before about 16:16 today's bar lacks the closing auction. 16:30 leaves margin.
CLOSE_SETTLED = (16, 30)
PASS_THROUGH = ("backtest", "calibrate-skew")  # `options` actions whose extra arguments go to their own main()
# Calendar days of headlines per run: about 45 sessions, enough for NEWS-4's z20 of counts and NEWS-18. NEWS-10/12
# want 252 sessions of news, so they stay skipped or partial in live runs (shadow only; see README "Limits").
NEWS_DAYS = 70


def load_dotenv(path=ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip())


def today_ny() -> str:
    return pd.Timestamp.now(tz=NY).date().isoformat()


# --- market data and brokers ----------------------------------------------------------------------


def drop_partial_bar(bars: dict, now: datetime | None = None) -> tuple[dict, str | None]:
    """Before the close has settled, today's bar is still moving: signals are only taken on final closes."""
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz=NY)
    now = now.tz_convert(NY) if now.tzinfo is not None else now.tz_localize(NY)
    if (now.hour, now.minute) >= CLOSE_SETTLED:
        return bars, None
    today = pd.Timestamp(now.date())
    out, dropped = {}, False
    for s, df in bars.items():
        if df is not None and len(df) and pd.Timestamp(df.index[-1]).tz_localize(None).normalize() >= today:
            out[s] = df[df.index.tz_localize(None).normalize() < today] if df.index.tz is not None \
                else df[df.index.normalize() < today]
            dropped = True
        else:
            out[s] = df
    note = (f"today's bars were dropped because the market has not closed yet (New York time "
            f"{now:%H:%M}); signals use yesterday's close") if dropped else None
    return out, note


def fetch_bars(cfg):
    """(bars, data notes). Plain-English errors name the env var or host to fix."""
    from .data import AlpacaData

    try:
        data = AlpacaData.from_env(cfg)
    except Exception as e:
        raise SystemExit(f"Market data is not set up: {e}\nSet ALPACA_DATA_KEY/ALPACA_DATA_SECRET or "
                         "ALPACA_RULES_KEY/ALPACA_RULES_SECRET (in trading/.env or the environment).")
    sessions = int(cfg.playbook.get("data", {}).get("history_sessions", 1800))
    try:
        bars = data.daily_bars(cfg.data_symbols(), sessions)
    except Exception as e:
        raise SystemExit(f"Could not fetch daily bars from data.alpaca.markets: {e}\n"
                         "Check the network access to data.alpaca.markets and the data keys.")
    bars, note = drop_partial_bar(bars)
    notes = list(data.notes) + ([note] if note else [])
    print(f"market data: {len(bars)} symbols, feed {data.feed_used or 'unknown'}")
    for n in notes:
        print(f"  data note: {n}")
    return bars, {"feed_used": data.feed_used, "notes": notes}


def news_feed(cfg, as_of, days: int = NEWS_DAYS, fetch=None, today: str | None = None) -> NewsFeed:
    """Today's headlines for the hype vetoes (decision 8). A failed fetch is not fatal to the run: the engine blocks
    new B/C/D longs for the day (fail closed) and sleeve A still runs; the TEST FIRST NEWS-4/NEWS-13 rows are still
    computed on bars for the shadow record."""
    from .news import fetch_news

    ts = pd.Timestamp(as_of)
    ts = ts.tz_localize(None) if ts.tzinfo is not None else ts
    start = (ts.normalize() - pd.Timedelta(days=int(days))).date().isoformat()
    end = today or today_ny()  # through today, so a promotion after the close is seen (no look-ahead: code cuts)
    try:
        items = (fetch or fetch_news)(news_universe(cfg), start, end, policy=cfg.policy)
    except Exception as e:  # noqa: BLE001
        why = f"news fetch failed ({type(e).__name__}); no new B/C/D longs today, sleeve A still runs (decision 8)"
        print(f"  news note: {why}: {e}")
        return NewsFeed(items=None, notes=[why])
    print(f"news: {len(items)} headline(s) from {start} to {end} (alpaca_benzinga; headlines are never printed)")
    return NewsFeed(items=list(items), start=start, notes=[f"{len(items)} headlines {start} to {end}"])


def sim_books(arg, books) -> set[str]:
    """--sim with no value = every book; --sim claude = only that book; absent = none."""
    if arg is None:
        return set()
    return set(books) if len(arg) == 0 else set(arg)


def make_broker(book: str, cfg, state: BookState, bars: dict, simulate: bool):
    from . import ledger, risk
    from .broker import AlpacaPaperBroker, SimBroker

    # A book's lots must come from one broker: mixing simulator and Alpaca state would re-buy or close lots.
    if simulate and not state.sim and (state.lots or state.pending_orders):
        raise SystemExit(f"[{book}] this book's state holds positions from Alpaca; it cannot switch to the "
                         f"simulator. Drop --sim for {book}, or move {STATE_DIR / book} aside first.")
    if not simulate and state.sim:
        raise SystemExit(f"[{book}] this book's state was built on the simulator; it cannot switch to Alpaca. "
                         f"Keep --sim for {book}, or move {STATE_DIR / book} aside first.")
    if simulate:
        if not state.sim:
            state.sim = {"cash": float(cfg.playbook["simulation"]["starting_cash"]), "positions": {}}
        # The sim takes the cost from cash and fills at the raw open; the ledger charges the same bps once.
        return SimBroker(state.sim, risk.last_valid_closes(bars), ledger.cost_model(cfg, state), cfg.asset_class,
                         bars=bars, fill_mode="next_open", cost_in_price=False)
    try:
        return AlpacaPaperBroker.for_book(book, cfg.crypto_symbols())
    except RuntimeError as e:
        raise SystemExit(f"[{book}] {e}")


def choose_advisor(book: str, args, cfg, date: str):
    """Decision files / session -> SessionAdvisor; API mode with a key -> ClaudeAdvisor; else none."""
    from .session import SessionAdvisor

    if args.no_claude:
        return None, "Claude skipped (--no-claude)"
    if args.decision_file:
        return SessionAdvisor(args.decision_file, date, cfg), f"decision files: {', '.join(args.decision_file)}"
    if args.session:
        adv = SessionAdvisor.from_pending(book, date, cfg, STATE_DIR)
        found = ", ".join(f.name for f in adv.files) or "none found"
        return adv, f"session files in {STATE_DIR / book / 'pending' / date}: {found}"
    if cfg.playbook.get("claude", {}).get("mode") == "api":
        if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            from .llm import ClaudeAdvisor

            return ClaudeAdvisor(cfg), "Claude API"
        return None, "claude.mode is 'api' but ANTHROPIC_API_KEY is not set"
    what = "the Claude book holds (stops still enforced)" if book == "claude" else "the rules book runs unreviewed"
    return None, f"no decision files (use --session or --decision-file): {what}"


# --- commands --------------------------------------------------------------------------------------


def cmd_run(args) -> int:
    cfg = load_config()
    books = BOOKS if args.book == "both" else (args.book,)
    if args.decision_file and len(books) != 1:
        raise SystemExit("--decision-file needs a single --book (rules or claude)")
    sims = sim_books(args.sim, books)
    bars, notes = fetch_bars(cfg)
    bench = cfg.playbook["regime"]["benchmark"]
    as_of = bars[bench].index[-1]
    date = as_of.date().isoformat()
    news = news_feed(cfg, as_of, args.news_days)
    failed = []
    for book in books:
        try:  # one book failing never stops the other (they share no state)
            state = BookState.load(book, STATE_DIR)
            broker = make_broker(book, cfg, state, bars, book in sims)
            advisor, why = choose_advisor(book, args, cfg, date)
            print(f"[{book}] advisor: {why}")
            entry = run_book(book, cfg, bars, broker, advisor, as_of, STATE_DIR, dry_run=args.dry_run,
                             force=args.force, state=state, data_notes=notes,
                             allow_all_zero=args.confirm_empty_account, news=news)
        except (Exception, SystemExit) as e:  # noqa: BLE001
            if len(books) == 1:
                raise
            import traceback

            traceback.print_exc()
            print(f"[{book}] FAILED: {type(e).__name__}: {e} (the other book still runs)")
            failed.append(book)
            continue
        print_entry(entry)
    if failed:
        print(f"FAILED books: {', '.join(failed)}")
        return 1
    return 0


def cmd_prepare(args) -> int:
    cfg = load_config()
    books = BOOKS if args.book == "both" else (args.book,)
    sims = sim_books(args.sim, books)
    bars, notes = fetch_bars(cfg)
    as_of = bars[cfg.playbook["regime"]["benchmark"]].index[-1]
    news = news_feed(cfg, as_of, args.news_days)
    for book in books:
        state = BookState.load(book, STATE_DIR)
        broker = make_broker(book, cfg, state, bars, book in sims)
        out = prepare_book(book, cfg, bars, broker, as_of, STATE_DIR, state=state, samples=args.samples,
                           data_notes=notes, news=news)
        print(f"\n=== prepare {book} book, {out['date']}{' (SIMULATED)' if book in sims else ''} ===")
        for line in out["summary"]:
            print(f"  {line}")
        if out.get("skipped"):
            continue
        print(f"  pending folder: {out['dir']}")
        print(f"  samples wanted: {out['samples']} (one independent subagent per file)")
    return 0


MAX_PROBLEM_LINES = 12


def claude_problem_lines(e: dict) -> list[str]:
    """How many samples were valid and every dropped file, dropped item or ignored skip (runbook steps 5, 9)."""
    m = e.get("claude_meta") or {}
    out = []
    if m.get("samples_requested"):
        files = ", ".join(m.get("files") or [])
        out.append(f"samples: {m.get('samples_valid', 0)} of {m['samples_requested']} valid"
                   + (f" ({files})" if files else ""))
    probs = list(m.get("problems") or []) + list((e.get("agreement") or {}).get("problems") or [])
    for smp in e.get("samples") or []:
        if isinstance(smp, dict):
            probs += [f"sample {smp.get('sample')}: {p}" for p in smp.get("problems") or []]
    probs += list((e.get("claude") or {}).get("problems") or [])
    probs = list(dict.fromkeys(str(p) for p in probs))
    out += [f"  claude problem: {p}" for p in probs[:MAX_PROBLEM_LINES]]
    if len(probs) > MAX_PROBLEM_LINES:
        out.append(f"  claude problem: ... {len(probs) - MAX_PROBLEM_LINES} more in the journal")
    return out


def print_entry(e: dict) -> None:
    if "skipped" in e:
        print(f"[{e['book']}] skipped: {e['skipped']}")
        return
    sim = "  SIMULATED" if e.get("simulated") else ""
    print(f"\n=== {e['book']} book, {e['date']}{' (dry run)' if e['dry_run'] else ''}{sim} ===")
    print(f"broker {e.get('broker')}  equity {e['equity']:,.2f}  drawdown {e['drawdown']:.1%}  regime {e['regime']}"
          f"  temperature {(e.get('temperature') or {}).get('label')}")
    print("sleeve weights: " + ", ".join(f"{k} {v:.0%}" for k, v in e["sleeve_weights"].items()))
    if e.get("claude"):
        print(f"claude: {e['claude'].get('journal_note', '')}")
    if e.get("claude_error"):
        print(f"claude error: {e['claude_error']}")
    for line in claude_problem_lines(e):
        print(line)
    for line in e["risk_log"]:
        print(f"  log: {line}")
    for line in e.get("shadow_signals") or []:
        print(f"  shadow (not traded): {line}")
    for f in e.get("settled_fills") or []:
        print(f"  filled: {f['side']} {f['qty']:.6g} {f['symbol']} ({f['sleeve']}) at {f['fill']:.2f}")
    verb = "planned (not sent)" if e["dry_run"] else "order"
    for o in e["orders"]:
        print(f"  {verb}: {o['side']} {o['qty']} {o['symbol']} @~{o['price']:.2f}  {o['reason']}")
    for r in e.get("fills") or []:
        if r.get("status") in ("error", "unconfirmed", "rejected"):
            print(f"  ORDER PROBLEM: {r.get('symbol')} {r.get('side')} {r.get('status')}: {r.get('error', '')}")
    if not e["orders"]:
        print("  no orders")


def cmd_status(args) -> int:
    from . import risk

    cfg = load_config()
    print(f"kill switch: {'ON' if kill_switch_on(STATE_DIR) else 'off'}")
    for book in BOOKS:
        s = BookState.load(book, STATE_DIR)
        if not s.equity_history:
            print(f"\n[{book}] no runs yet")
            continue
        last = s.equity_history[-1]
        dd = 1 - last["equity"] / s.peak_equity if s.peak_equity else 0
        flags = []
        if s.halted:
            flags.append("HALTED")
        if dd >= cfg.policy["breakers"]["watch_drawdown"]:
            flags.append("WATCH (no B/C/D weight increases)")
        li = risk.loss_inputs(s.equity_history, last["date"], last["equity"])
        if li["month_base"] and li["month_pnl"] / li["month_base"] <= -cfg.policy["breakers"]["monthly_loss_pct"]:
            flags.append("MONTHLY LOSS BLOCK (no new B/C/D entries)")
        print(f"\n[{book}]{' SIMULATED' if s.sim else ''} last run {s.last_run_date}  equity {last['equity']:,.2f}"
              f"  drawdown {dd:.1%}  {'  '.join(flags)}")
        for sleeve, why in s.sleeve_blocked.items():
            print(f"  sleeve {sleeve} BLOCKED: {why}  (owner: trader sleeve-reset {sleeve} --book {book})")
        if s.veto_codes_restricted:
            print("  review skips restricted to DATA_SUSPECT / HALT_OR_ILLIQUID (CL-9; owner: trader veto-reset)")
        if s.deviations_restricted:
            print("  Claude deviations restricted: the book follows the rules (owner: trader deviation-reset)")
        if s.promoted_sleeves:
            print(f"  promoted sleeves: {', '.join(s.promoted_sleeves)}")
        for o in s.pending_orders:
            print(f"  pending order: {o.get('side')} {o.get('qty')} {o.get('symbol')} from {o.get('date')} "
                  f"({o.get('status')})")
        for sleeve, held in sorted(s.lots.items()):
            for sym, lot in held.items():
                stop = f"stop {lot.stop:.2f}" if lot.stop else "no stop"
                print(f"  {sleeve} {sym:8s} qty {lot.qty:.4f}  entry {lot.entry_price:.2f} on {lot.entry_date}  {stop}")
        if s.notes:
            print(f"  last note ({s.notes[-1]['date']}): {s.notes[-1]['note']}")
    return 0


def _fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def _section(title: str, fn) -> dict | None:
    print(f"\n--- {title} ---")
    try:
        return fn()
    except Exception as e:  # one broken section never hides the rest of the report
        print(f"  could not compute: {type(e).__name__}: {e}")
        return None


def last_journal_entry(book: str) -> dict | None:
    """The newest journal line of a book (for today's data problems in G-5), or None."""
    p = STATE_DIR / book / "journal.jsonl"
    if not p.exists():
        return None
    for line in reversed(p.read_text().splitlines()):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def build_report(cfg, states: dict, since: str | None = None, rehearsed: bool | None = None,
                 data_problems: list[str] | None = None, o_report: dict | None = None) -> dict:
    """Every measurement for both books (M-1, M-2, M-4 to M-11, G-1..G-5), the hype-veto scores (decision 8) and,
    when `o_report` (options.run.report_options) is given, book O's OPT-38 report and the OPT-11 SPY line.
    Pure: reads the states and o_report only."""
    from . import metrics

    pol = cfg.policy
    out = {"books": {}}
    for book, s in states.items():
        eq = s.equity_history[-1]["equity"] if s.equity_history else 0.0
        stats = metrics.sleeve_stats(s.closed_trades, policy=pol)
        out["books"][book] = {
            "simulated": bool(s.sim), "days": len(s.equity_history),
            "benchmarks": metrics.benchmarks(s.equity_history),
            "sleeve_stats": stats,
            "sleeve_a": metrics.sleeve_a_report(s.equity_history),
            "capture": metrics.capture_ratios(s.equity_history),
            "api_cost": metrics.api_cost_report(s, eq),
            "predictions": metrics.prediction_scores(s.predictions,
                                                     int(pol["measurement"]["predictions_min_resolved"])),
            "promotion_gate": metrics.promotion_gate(metrics.sleeve_stats(s.closed_trades, policy=pol, since=since),
                                                     s, pol),
            "demotion": metrics.demotion_reasons(stats, pol),
            "news_vetoes": metrics.news_veto_report(s),
        }
    rules, claude = states.get("rules"), states.get("claude")
    if claude is not None:
        out["deviations"] = metrics.deviation_attribution(claude, rules)
    if rules is not None:
        out["vetoes"] = metrics.override_report(rules)
    if rules is not None and claude is not None:
        out["going_live"] = metrics.going_live_report(rules, claude, pol, since=since, rehearsed=rehearsed,
                                                      data_problems=data_problems)
    if o_report is not None:
        out["options"] = o_report
        host = states.get(_o_host(cfg))
        if host is not None:
            out["opt11_spy"] = metrics.spy_exposure(host, o_report)
    return out


def _o_host(cfg) -> str:
    from .engine import o_host_book

    return o_host_book(cfg)


def options_report_or_none(cfg) -> tuple[dict | None, str]:
    """book O's report (OPT-38, gates OPT-40/41/42) from trader.options.run, or None with the reason."""
    try:
        from .options import run as orun

        return orun.report_options(cfg, STATE_DIR), ""
    except Exception as e:  # noqa: BLE001 - the stock report never depends on book O
        return None, f"{type(e).__name__}: {e}"


def cmd_report(args) -> int:
    from .llm import jsonable

    cfg = load_config()
    states = {b: BookState.load(b, STATE_DIR) for b in BOOKS}
    last = last_journal_entry("rules")
    o_rep, o_why = options_report_or_none(cfg)
    rep = build_report(cfg, states, since=args.since, rehearsed=True if args.rehearsed else None,
                       data_problems=last.get("data_problems") if last else None, o_report=o_rep)
    if o_rep is None:
        rep["options_unavailable"] = o_why
    if args.json:
        print(json.dumps(jsonable(rep), indent=2))
        return 0
    for book, r in rep["books"].items():
        label = " (SIMULATED broker)" if r["simulated"] else ""
        print(f"\n===== {book} book{label}: {r['days']} daily runs =====")
        if r["days"] < 2:
            print("  not enough history yet: at least two daily runs are needed")
            continue
        b = r["benchmarks"]
        print("M-1 book vs benchmarks (price returns):")
        for k in ("book", "spy", "sixty_forty", "gtaa5"):
            v = b.get(k)
            print(f"  {k:12s} " + ("-" if not v else "  ".join(f"{m} {_fmt(v.get(m))}" for m in
                                                               ("return", "vol", "sharpe", "max_drawdown"))))
        print("M-2 per-sleeve closed lots (R net of costs):")
        print("  sleeve     n  win%    E_R   SQN  streak  boot_upper")
        for s, st in r["sleeve_stats"].items():
            print(f"  {s:6s} {st['n']:5d}  {_fmt(st['win_rate']):>5s} {_fmt(st['E']):>6s} {_fmt(st['SQN']):>5s}"
                  f"  {st['max_losing_streak']:6d}  {_fmt(st['boot_upper'])}")
        a = r["sleeve_a"]
        print(f"M-4 sleeve A: return {_fmt(a.get('return'))}, max drawdown {_fmt(a.get('max_drawdown'))}, "
              f"average cash share {_fmt(a.get('avg_cash_share'))}")
        c = r["capture"]
        print(f"M-8 capture: up {_fmt(c.get('up_capture'))}, down {_fmt(c.get('down_capture'))}")
        k = r["api_cost"]
        print(f"M-9 Claude cost: total ${_fmt(k.get('total_usd'))}, annualised {_fmt(k.get('annual_pct_equity'))} of equity")
        p = r["predictions"]
        print(f"M-7 predictions: {p.get('n_resolved', 0)} resolved, Brier {_fmt(p.get('brier'))}, "
              f"skill {_fmt(p.get('skill'))}")
        for s, g in r["promotion_gate"].items():
            print(f"M-10 promotion gate {s}: {'PASSED' if g.get('passed') else 'not passed'}")
        for s, why in r["demotion"].items():
            print(f"M-11 demotion {s}: {why}")
        print_news_vetoes(r.get("news_vetoes") or {})
    if "deviations" in rep:
        d = rep["deviations"]
        print(f"\nM-5 Claude deviations: {d.get('n_resolved')} resolved, "
              f"sum value_20d {_fmt(d.get('sum_value_20d'))}")
    if "vetoes" in rep:
        v = rep["vetoes"]
        print(f"M-6 review vetoes: {v['n_vetoes']} total, {v['n_scored']} scored, sum value {_fmt(v['sum_value'])}"
              f"{', RESTRICTED' if v['restricted'] else ''}")
    if "going_live" in rep:
        g = rep["going_live"]
        print(f"G-1..G-5 going-live gate: rules {'passed' if g['rules_passed'] else 'not passed'}, "
              f"claude {'passed' if g['claude_passed'] else 'not passed'} ({g['note']})")
        for b, checks in g["books"].items():
            g7 = checks.get("G-7_slippage") or {}
            if g7.get("breached"):
                print(f"G-7 [{b}]: median slippage above 2x the cost model in {', '.join(g7['breached'])}"
                      " (G-7 says go back to paper)")
    print_options_report(rep)
    print("\n(use --json for every number)")
    return 0


def print_news_vetoes(v: dict) -> None:
    """Decision 8: what the hype vetoes blocked, and whether blocking paid (veto_value > 0 = money saved)."""
    if not v.get("n_vetoes"):
        print("hype vetoes (decision 8): none blocked an increase yet")
        _print_test_first(v)
        return
    print(f"hype vetoes (decision 8): {v['n_vetoes']} blocked, {v['n_scored']} scored, sum value "
          f"{_fmt(v.get('sum_value'))} R (${_fmt(v.get('sum_value_usd'))}), hit rate {_fmt(v.get('hit_rate'))}")
    for sid, g in sorted((v.get("by_signal") or {}).items()):
        print(f"  {sid}: {g['n_vetoes']} blocked, {g['n_scored']} scored, sum {_fmt(g.get('sum_value'))} R")
    _print_test_first(v)


def _print_test_first(v: dict) -> None:
    """Decision 8 update: NEWS-4/NEWS-13 are TEST FIRST; what they would have blocked, shadow-scored."""
    tf = v.get("test_first") or {}
    if not tf.get("n_vetoes"):
        return
    print(f"TEST FIRST hype flags (NEWS-4/NEWS-13, not blocking): {tf['n_vetoes']} flagged increases, "
          f"{tf['n_scored']} scored, sum value {_fmt(tf.get('sum_value'))} R (> 0 = a block would have saved money)")
    for sid, g in sorted((tf.get("by_signal") or {}).items()):
        print(f"  {sid}: {g['n_vetoes']} flagged, {g['n_scored']} scored, sum {_fmt(g.get('sum_value'))} R")


def print_options_report(rep: dict) -> None:
    """Book O (shadow): OPT-38 numbers, the gates and the OPT-11 SPY line, as report_options gives them."""
    print("\n===== book O (options, SHADOW until the owner turns it on after OPT-41) =====")
    if "options" not in rep:
        print(f"  not available: {rep.get('options_unavailable') or 'no report'}")
        return
    o = rep["options"]
    print(f"  paper orders enabled: {o.get('enabled')}")
    for part in ("shadow", "paper", "skips"):
        stats = o.get(part)
        if isinstance(stats, dict):
            print(f"  OPT-38 {part}: " + ", ".join(f"{k} {_fmt(v)}" for k, v in stats.items()
                                                    if not isinstance(v, (dict, list)))[:400])
    gates = o.get("gates")
    if isinstance(gates, dict):
        print("  gates: " + ", ".join(f"{k} {_fmt(v)}" for k, v in gates.items()
                                      if not isinstance(v, (dict, list)))[:400])
    x = rep.get("opt11_spy")
    if x:
        print(f"  OPT-11 SPY: rules book {_fmt(x.get('rules_notional'))}, book O delta notional "
              f"{_fmt(x.get('o_delta_notional'))}, combined {_fmt(x.get('combined'))} (display only)")


def cmd_kill(args) -> int:
    set_kill_switch(args.state == "on", STATE_DIR)
    if args.state == "off" and args.reset_halt:
        for book in BOOKS:
            s = BookState.load(book, STATE_DIR)
            if s.halted or args.reset_peak:
                s.halted = False
                if args.reset_peak and s.equity_history:
                    s.peak_equity = s.equity_history[-1]["equity"]
                s.save(STATE_DIR)
    print(f"kill switch {'ON: no new entries, exits only' if args.state == 'on' else 'off'}")
    return 0


def cmd_sleeve_reset(args) -> int:
    """Owner action (RISK-13 / M-11): allow a blocked sleeve's new entries again; its drawdown restarts today."""
    s = BookState.load(args.book, STATE_DIR)
    why = s.sleeve_blocked.pop(args.sleeve, None)
    if why is None:
        print(f"[{args.book}] sleeve {args.sleeve} was not blocked; nothing changed")
        return 0
    rec = s.sleeve_pnl.get(args.sleeve)
    if isinstance(rec, dict) and "cum" in rec:
        rec["peak"] = rec["cum"]  # otherwise the same drawdown would latch the block again on the next run
    s.save(STATE_DIR)
    print(f"[{args.book}] sleeve {args.sleeve} unblocked (was: {why}); its P&L drawdown is measured from today")
    return 0


def cmd_veto_reset(args) -> int:
    s = BookState.load(args.book, STATE_DIR)
    s.veto_codes_restricted = False
    s.veto_reset_date = today_ny()
    s.save(STATE_DIR)
    print(f"[{args.book}] review skip codes unrestricted; vetoes are counted again from {s.veto_reset_date} (CL-9)")
    return 0


def cmd_deviation_reset(args) -> int:
    s = BookState.load(args.book, STATE_DIR)
    s.deviations_restricted = False
    s.deviations_reset_date = today_ny()
    s.save(STATE_DIR)
    print(f"[{args.book}] deviations allowed again; scored from {s.deviations_reset_date} (guide rule 6)")
    return 0


def cmd_promote(args, promote: bool) -> int:
    """RISK-8 / M-10: the owner moves a sleeve on or off the promoted list. Shows the gate first."""
    from . import metrics

    cfg = load_config()
    s = BookState.load(args.book, STATE_DIR)
    stats = metrics.sleeve_stats(s.closed_trades, policy=cfg.policy, since=args.since)
    gate = metrics.promotion_gate(stats, s, cfg.policy).get(args.sleeve, {})
    print(f"M-10 gate for sleeve {args.sleeve} in the {args.book} book: "
          f"{'PASSED' if gate.get('passed') else 'NOT passed'}")
    for name, check in (gate.get("checks") or {}).items():
        print(f"  {name}: {check}")
    if not args.i_am_the_owner:
        print("Nothing changed. Only the owner may do this: add --i-am-the-owner.")
        return 1
    if promote and args.sleeve not in s.promoted_sleeves:
        date = today_ny()
        quarter = pd.Timestamp(date).to_period("Q")
        earlier = [p for p in s.promotions if p.get("sleeve") == args.sleeve and p.get("date")
                   and pd.Timestamp(p["date"]).to_period("Q") == quarter]
        if earlier:
            print(f"Refused: sleeve {args.sleeve} was already promoted on {earlier[-1]['date']} this quarter "
                  f"({quarter}). M-12 allows at most one promotion per sleeve per quarter.")
            return 1
        s.promoted_sleeves.append(args.sleeve)
        s.promotions.append({"date": date, "sleeve": args.sleeve})
    if not promote and args.sleeve in s.promoted_sleeves:
        s.promoted_sleeves.remove(args.sleeve)
    s.save(STATE_DIR)
    print(f"[{args.book}] promoted sleeves now: {', '.join(s.promoted_sleeves) or 'none'}")
    return 0


# --- book O (options, shadow) ------------------------------------------------------------------------


def _options_run():
    """trader.options.run, imported only when an options command runs (it is built separately)."""
    try:
        from .options import run as orun
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"book O is not available yet: trader.options.run failed to load ({type(e).__name__}: {e})")
    return orun


def _print_dict(d, indent: str = "  ", depth: int = 0) -> None:
    """A readable dump of a result dict (nested one level; long lists are counted, not printed)."""
    if not isinstance(d, dict):
        print(f"{indent}{d}")
        return
    for k, v in d.items():
        if isinstance(v, dict) and depth < 1:
            print(f"{indent}{k}:")
            _print_dict(v, indent + "  ", depth + 1)
        elif isinstance(v, (list, tuple)) and (len(v) > 8 or any(isinstance(x, (dict, list)) for x in v)):
            print(f"{indent}{k}: {len(v)} item(s)")
        else:
            print(f"{indent}{k}: {_fmt(v) if not isinstance(v, (dict, list, tuple)) else v}")


def _bars_kw(fn, cfg, args) -> dict:
    """Daily bars for book O's REG-2 regime label (OPT-19: an unknown regime means no spread), when the function
    takes them. No broker is ever passed from here: this command line runs book O in shadow only (decision 10)."""
    import inspect

    try:
        takes = "bars" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        takes = False
    if not takes or args.no_bars:
        return {}
    bars, _ = fetch_bars(cfg)
    return {"bars": bars}


def _o_account_kw(fn, orun) -> dict:
    """Book O's E and uncommitted cash (OPT-8, OPT-9, OPT-31) from a READ-ONLY account read (GET /account), when
    the function takes them. The broker object itself is never passed on, so the shadow run cannot settle, check
    or send anything; without keys (or on any error) nothing is passed and the run reports the account unknown."""
    import inspect

    try:
        takes = "equity" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        takes = False
    if not takes:
        return {}
    try:
        br = orun.default_broker()
        if br is None:
            return {}
        eq, cash = br.account()  # read-only
        eq, cash = float(eq), float(cash)
    except Exception as e:  # noqa: BLE001 - an unknown account blocks shadow entries; it never stops the run
        print(f"  book O note: account read failed ({type(e).__name__}); equity unknown, no shadow entries")
        return {}
    if not (eq > 0 and cash == cash):
        return {}
    return {"equity": eq, "uncommitted_cash": max(0.0, cash - float(orun.rules_pending_buys(STATE_DIR)))}


def cmd_options(args) -> int:
    """Book O (reports/Options rulebook.md). SHADOW: nothing here sends an order while options_book.enabled is
    false, and the order code also needs gate OPT-41 (trader.options.run enforces both)."""
    cfg = load_config()
    if args.action == "backtest":
        from .options import backtest as obt

        return int(obt.main(list(args.rest or [])) or 0)
    if args.action == "calibrate-skew":
        from .options import pricing

        return int(pricing.main(["calibrate", *list(args.rest or [])]) or 0)
    orun = _options_run()
    if args.action == "log-chain":
        out = orun.log_chains(cfg, STATE_DIR, args.when)
    elif args.action == "prepare":
        out = orun.prepare_options(cfg, STATE_DIR, date=args.date, samples=args.samples or 3,
                                   **_bars_kw(orun.prepare_options, cfg, args),
                                   **_o_account_kw(orun.prepare_options, orun))
    elif args.action == "run":
        out = orun.run_options(cfg, STATE_DIR, decision_files=tuple(args.decision_file or ()), dry_run=args.dry_run,
                               when=args.when, **_bars_kw(orun.run_options, cfg, args),
                               **_o_account_kw(orun.run_options, orun))
    else:
        out = orun.report_options(cfg, STATE_DIR)
    if getattr(args, "json", False):
        from .llm import jsonable

        print(json.dumps(jsonable(out), indent=2))
    else:
        print(f"=== book O {args.action} (SHADOW unless the owner enabled it after OPT-41) ===")
        _print_dict(out)
    return 0


# --- news (decision 8; news report section 6) ------------------------------------------------------------


def cmd_news(args) -> int:
    """fetch: headline counts per symbol. signals: today's NEWS-1..18 events and the active hype vetoes.
    backtest: forward returns of one signal's past events (M-12 inputs). Headline text is never printed."""
    from collections import Counter

    cfg = load_config()
    if args.action == "fetch":
        from .news import fetch_news

        end = today_ny()
        start = (pd.Timestamp(end) - pd.Timedelta(days=int(args.days))).date().isoformat()
        items = fetch_news(news_universe(cfg), start, end, policy=cfg.policy, refresh=args.refresh)
        counts = Counter(sym for it in items for sym in it.get("symbols") or [] if sym in set(news_universe(cfg)))
        print(f"{len(items)} headline(s) from {start} to {end} (alpaca_benzinga); per symbol:")
        for sym, n in counts.most_common():
            print(f"  {sym:6s} {n}")
        return 0
    bars, _ = fetch_bars(cfg)
    as_of = bars[cfg.playbook["regime"]["benchmark"]].index[-1]
    if args.action == "signals":
        return _news_signals(cfg, bars, as_of, args)
    return _news_backtest(cfg, bars, args)


def _news_signals(cfg, bars, as_of, args) -> int:
    from . import news_signals as ns
    from .engine import _clean_vetoes, _compact_signals

    feed = news_feed(cfg, as_of, args.days)
    uni = news_universe(cfg)
    signals = ns.compute(bars, feed.items or [], uni, as_of, cfg.policy, c_universe=cfg.stock_universe(),
                         news_start=feed.start if feed.items is not None else None)
    state = BookState.load("rules", STATE_DIR)
    vetoes = ns.active_vetoes(signals, cfg.policy, dict(state.news_promo_history or {}), as_of=as_of)[0]
    allowed = set(uni) | {ns.BENCHMARK}
    compact, vetoes = _compact_signals(signals, allowed), _clean_vetoes(vetoes, allowed)
    if args.json:
        from .llm import jsonable

        print(json.dumps(jsonable({"as_of": as_of.date().isoformat(), "signals": compact, "vetoes": vetoes}),
                         indent=2))
        return 0
    print(f"news signals for {as_of.date()} (shadow unless marked active; data: alpaca_benzinga + alpaca_bars)")
    for sid in ns.SIGNAL_IDS:
        rows = compact.get(sid) or {}
        events = sorted(s for s, r in rows.items() if r.get("event"))
        print(f"  {sid:8s} {len(events)} event(s)" + (f": {', '.join(events[:12])}" if events else ""))
    print("active hype vetoes (no new longs in either book, decision 8):")
    for sym, reasons in sorted(vetoes.items()):
        print(f"  {sym}: {'; '.join(reasons)}")
    if not vetoes:
        print("  none")
    return 0


def _news_backtest(cfg, bars, args) -> int:
    from . import news_signals as ns
    from .news import fetch_news

    start, end = args.start, args.end or today_ny()
    fetch_from = (pd.Timestamp(start) - pd.Timedelta(days=45)).date().isoformat()
    items = fetch_news(news_universe(cfg), fetch_from, end, policy=cfg.policy)
    events = ns.backtest_signal(args.signal, bars, items, start, end, universe=news_universe(cfg),
                                policy=cfg.policy, news_start=fetch_from, c_universe=cfg.stock_universe())
    out_dir = STATE_DIR / "news"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"backtest_{args.signal}_{start}_{end}.json"
    from .llm import jsonable

    path.write_text(json.dumps(jsonable(events), indent=2))
    print(f"{args.signal}: {len(events)} event(s) from {start} to {end}; saved to {path}")
    for h in (1, 5, 10, 20):
        vals = [e.get(f"ar_fwd_open_net_{h}") for e in events if e.get(f"ar_fwd_open_net_{h}") is not None]
        mean = sum(vals) / len(vals) if vals else None
        print(f"  {h:2d} sessions: n {len(vals)}, mean AR after costs {_fmt(mean)} (next-open fill, 10 bps/side)")
    print("  (M-12: a signal is promoted only after >= 30 events agree in sign out of sample and the owner signs off)")
    return 0


def main(argv=None) -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="trader", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run today's cycle")
    r.add_argument("--book", choices=[*BOOKS, "both"], default="both")
    r.add_argument("--sim", nargs="*", choices=list(BOOKS), metavar="BOOK",
                   help="use the local simulator (no value = every book; e.g. --sim claude)")
    r.add_argument("--dry-run", action="store_true",
                   help="compute everything, place no orders, save no state (only a journal line is written)")
    r.add_argument("--no-claude", action="store_true", help="skip Claude (the Claude book then only enforces stops)")
    r.add_argument("--force", action="store_true", help="run again even if this date already ran")
    r.add_argument("--decision-file", action="append", metavar="PATH",
                   help="a decision/review file to act on (repeatable; single book only)")
    r.add_argument("--session", action="store_true",
                   help="act on the decision_*/review_* files in today's pending folder")
    r.add_argument("--confirm-empty-account", action="store_true",
                   help="owner: the broker account really is empty, so reconcile may close every lot")
    r.add_argument("--news-days", type=int, default=NEWS_DAYS, help="calendar days of headlines for the hype vetoes")
    r.set_defaults(func=cmd_run)

    p = sub.add_parser("prepare", help="write today's context for a Claude Code session (no orders, no save)")
    p.add_argument("--book", choices=[*BOOKS, "both"], default="both")
    p.add_argument("--sim", nargs="*", choices=list(BOOKS), metavar="BOOK")
    p.add_argument("--samples", type=int, default=None, help="independent decision files wanted (default 3)")
    p.add_argument("--news-days", type=int, default=NEWS_DAYS, help="calendar days of headlines for the hype vetoes")
    p.set_defaults(func=cmd_prepare)

    sub.add_parser("status", help="positions, pending orders, blocks and flags per book").set_defaults(func=cmd_status)
    rp = sub.add_parser("report", help="measurement report: benchmarks, sleeves, predictions, gates")
    rp.add_argument("--json", action="store_true")
    rp.add_argument("--since", default=None, help="date the phase 1 fixes went live (M-10, G-1..G-4)")
    rp.add_argument("--rehearsed", action="store_true", help="owner confirms the kill-switch rehearsal (G-5)")
    rp.set_defaults(func=cmd_report)

    k = sub.add_parser("kill", help="turn the kill switch on or off")
    k.add_argument("state", choices=["on", "off"])
    k.add_argument("--reset-halt", action="store_true", help="also clear a drawdown halt (human decision)")
    k.add_argument("--reset-peak", action="store_true", help="with --reset-halt, restart drawdown from today")
    k.set_defaults(func=cmd_kill)

    sr = sub.add_parser("sleeve-reset", help="owner: allow a blocked sleeve's new entries again (RISK-13, M-11)")
    sr.add_argument("sleeve", choices=[s for s in SLEEVES if s != "A"])
    sr.add_argument("--book", choices=list(BOOKS), required=True)
    sr.set_defaults(func=cmd_sleeve_reset)
    vr = sub.add_parser("veto-reset", help="owner: lift the CL-9 restriction on review skip codes")
    vr.add_argument("--book", choices=["rules"], default="rules")
    vr.set_defaults(func=cmd_veto_reset)
    dr = sub.add_parser("deviation-reset", help="owner: let the Claude book deviate from the rules again")
    dr.add_argument("--book", choices=["claude"], default="claude")
    dr.set_defaults(func=cmd_deviation_reset)
    for name, promote in (("promote", True), ("demote", False)):
        pr = sub.add_parser(name, help=f"owner: {name} a sleeve (RISK-8 cap; shows the M-10 gate first)")
        pr.add_argument("sleeve", choices=list(SLEEVES))
        pr.add_argument("--book", choices=list(BOOKS), required=True)
        pr.add_argument("--since", default=None, help="count closed lots entered on or after this date")
        pr.add_argument("--i-am-the-owner", action="store_true")
        pr.set_defaults(func=lambda a, _p=promote: cmd_promote(a, _p))
    o = sub.add_parser("options", help="book O (options, SHADOW): log-chain, prepare, run, report, backtest")
    o.add_argument("action", choices=["log-chain", "prepare", "run", "report", "backtest", "calibrate-skew"])
    o.add_argument("--when", choices=["close", "1545"], default="close", help="log-chain / run: which snapshot (OPT-35; 1545 = the OPT-13 15:45 measurement / OPT-17 run)")
    o.add_argument("--date", default=None, help="prepare: the session date (default: today)")
    o.add_argument("--samples", type=int, default=None, help="prepare: independent review files wanted (default 3)")
    o.add_argument("--decision-file", action="append", metavar="PATH", help="run: a review file (repeatable)")
    o.add_argument("--dry-run", action="store_true", help="run: compute everything, save nothing")
    o.add_argument("--json", action="store_true")
    o.add_argument("--no-bars", action="store_true", help="prepare/run: do not fetch daily bars (regime unknown)")
    o.set_defaults(func=cmd_options)  # backtest / calibrate-skew: unknown arguments are passed through

    n = sub.add_parser("news", help="news signals (decision 8): fetch, signals, backtest; never prints headlines")
    n.add_argument("action", choices=["fetch", "signals", "backtest"])
    n.add_argument("--days", type=int, default=NEWS_DAYS, help="fetch/signals: calendar days of headlines")
    n.add_argument("--refresh", action="store_true", help="fetch: ignore the cache")
    n.add_argument("--json", action="store_true", help="signals: print the rows Claude would see")
    n.add_argument("--signal", default="NEWS-4", help="backtest: NEWS-1 .. NEWS-18")
    n.add_argument("--start", default="2024-01-01", help="backtest: first event date")
    n.add_argument("--end", default=None, help="backtest: last event date (default: today)")
    n.set_defaults(func=cmd_news)
    args, extra = ap.parse_known_args(argv)
    if extra and not (args.cmd == "options" and args.action in PASS_THROUGH):
        ap.error(f"unrecognized arguments: {' '.join(extra)}")
    args.rest = extra
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
