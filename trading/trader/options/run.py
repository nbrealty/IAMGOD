"""Book O's daily run: log chains, update the shadow book, build the one monthly spread, let Claude only skip it,
and (only when the owner has enabled O and the paper-start gate passed) send paper orders.

Source: reports/Options rulebook.md and OPERATION_INVEST.md owner decisions 6 and 10.

Flow of a day (all shadow-safe; nothing here sends an order unless `options_book.enabled` is true AND
`gate_status(...)["paper_start_ok"]` AND the run is not a dry run AND a broker is given):
1. `log_chains(cfg, state_dir, "close")` after the close (OPT-35), plus every held and shadow leg.
2. `prepare_options(cfg, state_dir)` builds the one spread (or none) and writes the Claude menu to
   `state_dir/options/pending/<date>/` (context.json, schema.json, instructions.md, menu.json). Skip only (OPT-33).
3. A Claude Code session writes `skip_<k>.json` files (independent samples).
4. `run_options(cfg, state_dir)` applies the skip (majority, OPT-33/34), runs the exits, the shadow book (OPT-36),
   the variants (OPT-20, OPT-25, OPT-39), the breakers (OPT-30/31) and writes a journal entry.
5. `log_chains(cfg, state_dir, "1545")` and `run_options(..., when="1545")` at 15:45 ET next session: the OPT-17
   order run (paper only, gated): the OPT-26 clean-up, the exits due and the entry are sent only here, never
   after the close. Also the 15:45 OPT-13 measurement.
6. `report_options(cfg, state_dir)` for OPT-38, the gates OPT-40/41/42 and the amount invested per trade.

Owner decision 10 (hold): no paper orders and no schedule without the owner's OK. `options_book.enabled` is false,
so every path below stays in shadow; the order path is built and tested with fake brokers only.
"""
from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, ValidationError

from ..config import STATE_DIR
from . import book as ob
from . import logger as chain_log
from . import risk as orisk
from . import shadow as osh
from .ledger import OptionsBook, o_pnl, o_value
from .models import MULTIPLIER, OptionQuote, is_occ

BOOK = "options"
CONTEXT_SCHEMA = "o-ctx-1"
SKIP_CODES = ("DATA_SUSPECT", "HALT_OR_ILLIQUID", "SCHEDULED_EVENT")  # CL-8 as amended for book O
PREDICTION_HORIZON = 20  # OPT-34
MIN_COMPLETE_SESSIONS = 40  # OPT-41
MIN_SHADOW_CYCLES = 2  # OPT-41
PROMOTION_MIN_SPREADS = 30  # OPT-40 (iv), OPT-8
MIN_OPTIONS_LEVEL = 3  # OPT-6
ACCOUNT_MAX_AGE_DAYS = 5  # a stored account read older than this is not used for shadow sizing
PAPER_FILE = "paper.json"
CLEANUP_INTENTS = ("stock_sale", "orphan_long")  # OPT-26 single-leg clean-up orders
CLEANUP_STOCK_OFFSET = 0.01  # OPT-26 marketable limit: sell O's assigned stock at most 1% under the 15:45 price
APPROVAL_FILE = "owner_approval.json"
REPORT_FILE = "report.json"
JOURNAL_FILE = "journal.jsonl"
FEED_NOTE = ("Quotes, IV and greeks come from Alpaca's free indicative feed, derived from OPRA but not real OPRA "
             "quotes (OPT-12).")
# OPT-41 item "OPT-35 to OPT-38 and the OPT-17 order run built and tested": these live in this package and its tests.
BUILT = {"OPT-35": "trader/options/logger.py", "OPT-36": "trader/options/shadow.py",
         "OPT-37": "trader/options/backtest.py", "OPT-38": "trader/options/shadow.py opt38_stats",
         "OPT-17": "trader/options/run.py recheck_entry", "separation": "broker.cancel_open_orders(prefixes)"}


# --- small helpers ---------------------------------------------------------------------------------------


def _dir(state_dir) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _policy(cfg) -> dict:
    return ob.ob_policy(getattr(cfg, "policy", cfg))


def _today(now=None) -> str:
    """The New York session date of `now` (default: the current time)."""
    t = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    t = t.tz_localize("UTC") if t.tzinfo is None else t
    return t.tz_convert("America/New_York").date().isoformat()


def _iso(d) -> str:
    return ob.to_date(d).isoformat()


def _exchange_holidays(first_year: int, last_year: int) -> set:
    """Regular NYSE full-day holidays (the calendar the stock ledger uses). Empty if it cannot be loaded."""
    try:
        from ..ledger import _holidays

        return set(_holidays(first_year, last_year))
    except Exception:  # noqa: BLE001 - weekdays only is the fallback
        return set()


def next_session(date) -> str:
    """The next trading session after `date` (the OPT-17 order session): skips weekends and regular NYSE
    full-day holidays (one-off closures are not known)."""
    d = pd.Timestamp(_iso(date))
    hol = _exchange_holidays(d.year, d.year + 1)
    d += pd.Timedelta(days=1)
    while d.weekday() >= 5 or d.date() in hol:
        d += pd.Timedelta(days=1)
    return d.date().isoformat()


def _read_json(path: Path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def _write_json(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str))
    tmp.replace(path)
    return path


def _journal(state_dir, entry: dict) -> None:
    p = _dir(state_dir) / "options" / JOURNAL_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


def pending_dir(date, state_dir=None) -> Path:
    """`state_dir/options/pending/<date>`: the day's Claude menu and skip files (OPT-33)."""
    return _dir(state_dir) / BOOK / "pending" / _iso(date)


# --- chain logging (OPT-35 wiring) --------------------------------------------------------------------------


def held_symbols(state_dir=None) -> list[str]:
    """Every leg O holds or tracks: paper ledger lots, paper orders not yet settled, and every shadow spread."""
    sd = _dir(state_dir)
    ledger = OptionsBook.load(sd)
    out = [s for l in ledger.open_lots() for s in (l.short_leg.symbol, l.long_leg.symbol)]
    for rec in _load_paper(sd).get("pending", []):
        out += [s for s in rec.get("legs", []) if is_occ(s)]
    return sorted(set(out) | set(osh.ShadowO.load(sd).held_symbols()))


def log_chains(cfg, state_dir=None, when: str = "close", *, now=None, fetch=None, cboe_fetch=True) -> dict:
    """OPT-35: snapshot SPY, QQQ and IWM (plus every held and shadow leg) with logger.log_chains.

    `fetch` and `cboe_fetch` are passed through (tests inject fakes; the defaults use Alpaca and Cboe, read-only).
    """
    kw = {"when": when, "now": now, "extra_symbols": held_symbols(state_dir), "cboe_fetch": cboe_fetch}
    if fetch is not None:
        kw["fetch"] = fetch
    return chain_log.log_chains(list(chain_log.DEFAULT_UNDERLYINGS), _dir(state_dir), **kw)


def load_chain(date, state_dir=None, when: str | None = None) -> tuple[dict | None, str | None]:
    """The day's snapshot: `when` if given, else the after-close run, else the 15:45 run. (None, None) if absent."""
    for w in ([when] if when else ["close", "1545"]):
        snap = chain_log.load_snapshot(_iso(date), w, _dir(state_dir))
        if snap:
            return snap, w
    return None, None


def all_quotes(snapshot: dict | None) -> list[OptionQuote]:
    out: list[OptionQuote] = []
    for u in ((snapshot or {}).get("underlyings") or {}):
        out += chain_log.snapshot_quotes(snapshot, u)
    return out


def spots_of(snapshot: dict | None, bars: dict | None = None, date=None) -> dict[str, float]:
    """Underlying prices from the snapshot's meta; a daily close from `bars` (raw) fills a gap."""
    out = {}
    for u, block in ((snapshot or {}).get("underlyings") or {}).items():
        v = ob.num(((block or {}).get("meta") or {}).get("spot"))
        if v is not None and v > 0:
            out[u] = v
    for u, df in (bars or {}).items():
        if u in out or df is None or "close" not in df or len(df) == 0:
            continue
        s = pd.to_numeric(df["close"], errors="coerce").dropna()
        if date is not None:
            s = s[pd.DatetimeIndex(s.index).normalize() <= pd.Timestamp(_iso(date))]
        if len(s) and float(s.iloc[-1]) > 0:
            out[u] = float(s.iloc[-1])
    return out


def _chain_problems(snapshot: dict | None, underlying: str = "SPY") -> list[str]:
    """OPT-27: no new entries when the chain for the underlying is missing or incomplete."""
    if not snapshot:
        return ["OPT-27: no chain snapshot for today; no new entries"]
    block = (snapshot.get("underlyings") or {}).get(underlying) or {}
    if not block:
        return [f"OPT-27: {underlying} missing from today's chain; no new entries"]
    if block.get("complete") is not True:
        why = "; ".join(block.get("reasons") or [])[:200]
        return [f"OPT-27: {underlying} chain incomplete ({why}); no new entries"]
    return []


# --- regime, account and ownership inputs --------------------------------------------------------------------


def regime_label_from_bars(bars: dict | None, date=None) -> tuple[str | None, str]:
    """REG-2 label from SPY closes (the same trend rule the stock books use). (None, why) when it cannot be computed:
    OPT-19 then gives permission 0 (the safe side)."""
    df = (bars or {}).get("SPY")
    if df is None or "close" not in df:
        return None, "no SPY bars"
    s = pd.to_numeric(df["close"], errors="coerce").dropna()
    if date is not None:
        s = s[pd.DatetimeIndex(s.index).normalize() <= pd.Timestamp(_iso(date))]
    if len(s) < 260:
        return None, f"only {len(s)} SPY closes (REG-2 needs about 260)"
    try:
        from ..regime import _trend_fields

        return _trend_fields(s)["label"], "REG-2 on SPY closes"
    except Exception as e:  # noqa: BLE001 - an unknown regime means no entry, never a crash
        return None, f"regime failed: {type(e).__name__}: {e}"[:160]


def other_books_stock(state_dir=None) -> dict[str, float]:
    """Stock the rules book's ledger owns in the shared account (owner decision 6). The Claude book trades in
    its own account (or the simulator), so it never counts here."""
    try:
        from ..state import BookState

        st = BookState.load("rules", _dir(state_dir))
    except Exception:  # noqa: BLE001 - an unreadable ledger owns nothing, so any stock becomes an incident
        return {}
    out: dict[str, float] = {}
    for held in (st.lots or {}).values():
        for sym, lot in (held or {}).items():
            out[sym] = out.get(sym, 0.0) + float(getattr(lot, "qty", 0.0) or 0.0)
    return {k: v for k, v in out.items() if abs(v) > 1e-9}


def rules_pending_buys(state_dir=None) -> float:
    """Cash the rules book has already committed to buy orders that have not settled yet."""
    try:
        from ..state import BookState

        st = BookState.load("rules", _dir(state_dir))
    except Exception:  # noqa: BLE001
        return 0.0
    return sum(float(ob.num(p.get("qty"), 0.0)) * float(ob.num(p.get("signal_close"), 0.0))
               for p in st.pending_orders or [] if str(p.get("side")) == "buy")


def rules_pending_stock(state_dir=None) -> dict[str, float]:
    """Signed shares of the rules book's orders that are not booked yet (buy +, sell -). A fill of one of these
    shows up at the broker before the rules run books it, so it is "pending booking", not unowned stock."""
    try:
        from ..state import BookState

        st = BookState.load("rules", _dir(state_dir))
    except Exception:  # noqa: BLE001
        return {}
    out: dict[str, float] = {}
    for o in st.pending_orders or []:
        left = float(ob.num(o.get("qty"), 0.0) or 0.0) - float(ob.num(o.get("settled_qty"), 0.0) or 0.0)
        sign = 1.0 if str(o.get("side")) == "buy" else -1.0 if str(o.get("side")) == "sell" else 0.0
        sym = str(o.get("symbol") or "")
        if sym and left > 1e-9 and sign:
            out[sym] = out.get(sym, 0.0) + sign * left
    return out


def explain_pending(positions, other: dict | None, pending: dict | None, o_stock: dict | None) -> tuple[dict, list]:
    """Stock the broker holds that lies between the rules ledger's lots and those lots plus the rules book's
    unbooked orders is the rules book's, pending booking. Returns (other books' stock including it, notes)."""
    out = {k: float(v) for k, v in (other or {}).items()}
    notes = []
    for pos in positions or []:
        sym = str(pos.get("symbol", ""))
        pend = float((pending or {}).get(sym, 0.0))
        if is_occ(sym) or not pend:
            continue
        q = float(ob._pos_qty(pos))
        mine = float((o_stock or {}).get(sym, 0.0))
        base = out.get(sym, 0.0) + mine
        if abs(q - base) > 1e-9 and min(base, base + pend) - 1e-9 <= q <= max(base, base + pend) + 1e-9:
            out[sym] = q - mine
            notes.append(f"{sym}: {q - base:+g} shares are the rules book's orders pending booking (not unowned)")
    return out, notes


def account_view(state_dir, shadow: osh.ShadowO, date, *, acct: dict | None = None, equity=None,
                 uncommitted_cash=None) -> dict:
    """E and the cash not committed to the rules book (OPT-8, OPT-9). Order of sources: explicit arguments, a
    broker read today (stored for later shadow runs), a stored read at most 5 days old. Unknown stays None, and
    OPT-9's assignment cover then blocks entries (reported, never bypassed: rulebook conflict 8)."""
    if acct and ob.num(acct.get("equity")) is not None:
        cash = ob.num(acct.get("cash"))
        unc = None if cash is None else max(0.0, cash - rules_pending_buys(state_dir))
        shadow.account = {"date": _iso(date), "equity": acct["equity"], "cash": cash, "uncommitted_cash": unc}
    stored = shadow.account or {}
    fresh = bool(stored.get("date")) and 0 <= ob.dte(_iso(date), stored["date"]) <= ACCOUNT_MAX_AGE_DAYS
    eq = ob.num(equity) if equity is not None else (ob.num(stored.get("equity")) if fresh else None)
    unc = ob.num(uncommitted_cash) if uncommitted_cash is not None else \
        (ob.num(stored.get("uncommitted_cash")) if fresh else None)
    src = "arguments" if equity is not None else ("broker/stored" if fresh else "unknown")
    return {"equity": eq, "uncommitted_cash": unc, "source": src}


def default_broker(cfg=None):
    """OPT-1: the rules book's paper account, with ALPACA_OPTIONS_KEY/SECRET if set, else the rules keys.
    Returns None when no keys are set (the run then stays shadow and says so)."""
    import os

    from ..broker import AlpacaPaperBroker

    for book in ("OPTIONS", "RULES"):
        key, secret = os.environ.get(f"ALPACA_{book}_KEY"), os.environ.get(f"ALPACA_{book}_SECRET")
        if key and secret:
            return AlpacaPaperBroker(key, secret, [])
    return None


# --- OPT-6 start-up checks -----------------------------------------------------------------------------------


def startup_checks(acct: dict | None, positions: list[dict] | None, other_stock: dict | None,
                   o_stock: dict | None) -> list[str]:
    """OPT-6, each run: paper account; options_trading_level >= 3; max_options_trading_level set to 3 in the account
    configuration; no stock held that neither book's ledger owns. Failures stop new entries; exits still run."""
    a = acct or {}
    out = [f"OPT-6: {p}" for p in a.get("problems") or []]
    if not a.get("paper"):
        out.append("OPT-6: account is not a paper account (or its host is unknown)")
    lvl = a.get("options_trading_level")
    if lvl is None or int(lvl) < MIN_OPTIONS_LEVEL:
        out.append(f"OPT-6: options_trading_level {lvl} < {MIN_OPTIONS_LEVEL}")
    if a.get("max_options_trading_level") != MIN_OPTIONS_LEVEL:
        out.append(f"OPT-6: max_options_trading_level is {a.get('max_options_trading_level')}, "
                   f"not set to {MIN_OPTIONS_LEVEL}")
    owned = {k: float(v) for k, v in (other_stock or {}).items()}
    for k, v in (o_stock or {}).items():
        owned[k] = owned.get(k, 0.0) + float(v)
    for p in positions or []:
        sym, q = str(p.get("symbol", "")), float(ob.num(p.get("qty"), 0.0))
        if not is_occ(sym) and abs(q - owned.get(sym, 0.0)) > 1e-9:
            out.append(f"OPT-6: {sym} stock {q:+g} is not owned by any book's ledger ({owned.get(sym, 0.0):+g})")
    return out


# --- gates (OPT-40, OPT-41, OPT-42) --------------------------------------------------------------------------


def owner_approval(state_dir, key: str) -> dict:
    """The owner's written yes: `state_dir/options/owner_approval.json` {key: {approved: true, date, note}}.
    Only a literal true with a date and a non-empty note counts."""
    rec = (_read_json(_dir(state_dir) / BOOK / APPROVAL_FILE, {}) or {}).get(key) or {}
    ok = rec.get("approved") is True and bool(str(rec.get("date") or "").strip()) and \
        bool(str(rec.get("note") or "").strip())
    return {"ok": ok, "record": rec}


def _item(ok: bool, detail) -> dict:
    return {"ok": bool(ok), "detail": detail}


def _ok_detail(check: dict) -> tuple[bool, dict]:
    return bool(check.get("ok")), check


TESTS_DIR = Path(__file__).resolve().parents[2] / "tests"
BUILT_TESTS = ("test_options_run.py", "test_options_backtest.py", "test_options_core.py", "test_options_chain.py")


def built_check() -> dict:
    """OPT-41 item "built and tested", checked: the modules import with the functions the gate relies on, and
    their test files are present. (Whether the tests pass is the build's job; this catches a missing piece.)"""
    missing = []
    try:
        from . import backtest as obt

        for mod, names in ((chain_log, ("log_chains", "complete_sessions")), (osh, ("opt38_stats", "open_shadow")),
                           (obt, ("replay", "full_report")), (orisk, ("validate_spread_order",))):
            missing += [f"{mod.__name__}.{n}" for n in names if not callable(getattr(mod, n, None))]
    except Exception as e:  # noqa: BLE001
        missing.append(f"import failed: {type(e).__name__}: {e}"[:160])
    missing += [f"tests/{t}" for t in BUILT_TESTS if not (TESTS_DIR / t).exists()]
    return {"ok": not missing, "missing": missing, "built": BUILT}


def separation_check(state_dir=None, prefix: str = "OPT-") -> dict:
    """OPT-41 item "separation built", checked (owner decision 6): the broker cancels by prefix, the stock books'
    own prefixes never match O's, the engine removes O's holdings through o_owned, and o_owned answers."""
    problems = []
    try:
        import inspect

        from .. import broker as brk
        from .. import engine as eng

        for cls in (brk.AlpacaPaperBroker, brk.SimBroker):
            if "prefixes" not in inspect.signature(cls.cancel_open_orders).parameters:
                problems.append(f"{cls.__name__}.cancel_open_orders takes no prefixes")
        own = getattr(eng, "_own_prefixes", None)
        if not callable(own):
            problems.append("engine has no per-book cancel prefixes")
        else:
            for book in ("rules", "claude"):
                pre = tuple(own(book, "2026-01-02"))
                if not pre or any(str(x).startswith(prefix) or prefix.startswith(str(x)) for x in pre):
                    problems.append(f"{book} cancel prefixes {pre} are empty or overlap {prefix!r}")
        if not callable(getattr(eng, "o_owned", None)):
            problems.append("engine does not read o_owned for the stock books")
        o_owned(state_dir)
    except Exception as e:  # noqa: BLE001 - the gate fails closed
        problems.append(f"check failed: {type(e).__name__}: {e}"[:160])
    return {"ok": not problems, "problems": problems}


def opt41_status(cfg, state_dir, shadow: osh.ShadowO) -> dict:
    """OPT-41 paper-start gate. Every item must pass; the count of complete chains uses the after-close run."""
    sd = _dir(state_dir)
    n_chain = chain_log.complete_sessions(sd, when="close")
    cycles = osh.completed_cycles(shadow.evaluations)
    ratio = osh.credit_ratio_check(shadow.evaluations, cycles)
    ntr = osh.no_trade_rate(shadow.evaluations)
    items = {
        "built_and_tested": _item(*_ok_detail(built_check())),
        "complete_chain_sessions": _item(n_chain >= MIN_COMPLETE_SESSIONS, f"{n_chain} of {MIN_COMPLETE_SESSIONS}"),
        "shadow_cycles": _item(len(cycles) >= MIN_SHADOW_CYCLES, f"{len(cycles)} of {MIN_SHADOW_CYCLES}: {cycles}"),
        "model_credit_ratio": _item(ratio["ok"], ratio),
        "no_trade_rate_reported": _item(ntr["rate"] is not None, ntr),
        "separation_built": _item(*_ok_detail(separation_check(sd, str(_policy(cfg).get("order_prefix", "OPT-"))))),
        "owner_yes": _item(owner_approval(sd, "paper_start")["ok"], "owner_approval.json paper_start"),
    }
    return {"items": items, "paper_start_ok": all(v["ok"] for v in items.values())}


def opt40_status(cfg, state_dir, shadow: osh.ShadowO, ledger: OptionsBook, now=None) -> dict:
    """OPT-40 promotion (TEST FIRST -> BUILD): backtest at the traded width, doubled costs, +-25% parameters,
    >= 30 shadow or paper spreads agreeing in sign, E_net > 0 and above BIL in both, owner sign-off."""
    sd = _dir(state_dir)
    bt = _read_json(sd / BOOK / "backtest" / "latest.json", {}) or {}
    lots = [l for l in shadow.book.all_lots() + ledger.all_lots()]
    traded = lots[-1].width if lots else None
    recs = list(shadow.book.closed) + list(ledger.closed)
    st = osh.opt38_stats(recs)
    base = (bt.get("base") or {}).get("E")
    sens = [ob.num(v.get("E")) for v in (bt.get("sensitivity") or {}).values()]
    items = {
        "backtest_at_traded_width": _item(bool(bt) and traded is not None
                                          and ob.num(bt.get("width_usd")) == ob.num(traded),
                                          {"backtest_width": bt.get("width_usd"), "traded_width": traded}),
        "doubled_costs_positive": _item((ob.num((bt.get("doubled_costs") or {}).get("E")) or -1) > 0,
                                        (bt.get("doubled_costs") or {}).get("E")),
        "sign_holds_pm25": _item(bool(sens) and base is not None and all(s is not None and (s > 0) == (base > 0)
                                                                           for s in sens), sens),
        "spreads_agree_in_sign": _item(st["n"] >= PROMOTION_MIN_SPREADS and st["E"] is not None and base is not None
                                       and (st["E"] > 0) == (base > 0), {"n": st["n"], "E": st["E"]}),
        "E_above_zero_and_bil": _item(bool(base is not None and base > 0 and base > (bt.get("bil_E") or 0.0)
                                           and st["benchmarks"]["E_above_bil"] and st["benchmarks"]["E_above_zero"]),
                                      {"backtest": base, "shadow": st["E"], "bil": st["benchmarks"]["bil_E"]}),
        "alpaca_option_bars_run": _item(*_alpaca_bars_item(bt, base)),
        "one_promotion_per_quarter": _item(*_quarter_item(sd, now)),
        "owner_sign_off": _item(owner_approval(sd, "promotion")["ok"], "owner_approval.json promotion"),
    }
    return {"items": items, "promotion_ok": all(v["ok"] for v in items.values()),
            "note": "At most one promotion per quarter; the cap may rise to 0.5% of E only (OPT-8)."}


def _alpaca_bars_item(bt: dict, base) -> tuple[bool, dict]:
    """OPT-40 (i): the backtest must also be run on real Alpaca option bars since Feb 2024 and agree in sign.
    That run is not built yet, so unless latest.json carries an `alpaca_option_bars` result this item fails."""
    run_ = bt.get("alpaca_option_bars") or {}
    e = ob.num(run_.get("E"))
    if e is None:
        return False, "OPT-40 (i): no run on real Alpaca option bars since Feb 2024 (not built yet)"
    return bool(base is not None and (e > 0) == (base > 0) and e > 0), {"E": e, "n": run_.get("n")}


def _quarter(d) -> tuple[int, int]:
    d = ob.to_date(d)
    return d.year, (d.month - 1) // 3


def _quarter_item(sd, now=None) -> tuple[bool, dict]:
    """OPT-40: at most one promotion per quarter. Promotions are dated in owner_approval.json
    `promotion_history` [{date}] (the owner's record); a promotion already this quarter fails the item."""
    hist = (_read_json(Path(sd) / BOOK / APPROVAL_FILE, {}) or {}).get("promotion_history") or []
    dates = []
    for r in hist if isinstance(hist, list) else []:
        try:
            dates.append(ob.to_date((r or {}).get("date")).isoformat())
        except Exception:  # noqa: BLE001 - an unreadable date counts as this quarter (fail closed)
            dates.append(None)
    today = _today(now)
    this_q = [d for d in dates if d is None or _quarter(d) == _quarter(today)]
    return not this_q, {"today": today, "promotions": dates, "this_quarter": this_q}


def gate_status(cfg, state_dir=None, *, shadow: osh.ShadowO | None = None,
                ledger: OptionsBook | None = None) -> dict:
    """OPT-40, OPT-41, OPT-42 in one place. `orders_allowed` = options_book.enabled AND paper_start_ok."""
    sd = _dir(state_dir)
    shadow = shadow or osh.ShadowO.load(sd)
    ledger = ledger or OptionsBook.load(sd)
    p = _policy(cfg)
    o41 = opt41_status(cfg, sd, shadow)
    return {"enabled": bool(p.get("enabled", False)), "paper_start_ok": o41["paper_start_ok"],
            "orders_allowed": bool(p.get("enabled", False)) and o41["paper_start_ok"], "opt41": o41,
            "opt40": opt40_status(cfg, sd, shadow, ledger),
            "opt42": {"live_ok": False, "reason": "OPT-42: no live options under this rulebook (M-10 needs >= 100 "
                                                  "closed spreads; a $100 account cannot hold one spread)"}}


# --- the menu (OPT-33) ------------------------------------------------------------------------------------------


def _blocks(breakers: dict | None, extra=()) -> list[str]:
    """Reasons that stop new entries today: broker/incident failures plus the OPT-30/31/32 breakers."""
    out = list(extra or [])
    if breakers and breakers.get("no_new_entries"):
        out += list(breakers.get("reasons") or ["breaker"])
    return out


def build_menu(cfg, date, snapshot, *, regime_label, account: dict, book_state: OptionsBook, blocks=(),
               underlying: str = "SPY", cap_mult: float = 1.0) -> dict:
    """OPT-18 candidate with every entry rule (book.build_candidate), for `book_state`'s lots. One or none."""
    p = _policy(cfg)
    quotes = all_quotes(snapshot)
    spots = spots_of(snapshot)
    missing = _chain_problems(snapshot, underlying)
    if missing:  # OPT-27: say why before anything else (the price check would hide it)
        return {"date": _iso(date), "underlying": underlying, "candidate": None, "reasons": list(blocks) + missing,
                "notes": [], "regime": regime_label, "account_source": account.get("source")}
    cand, reasons = ob.build_candidate(
        quotes, spots.get(underlying), date, p, regime_label, book_state.all_lots(), account.get("equity"),
        account.get("uncommitted_cash"), None, underlying=underlying, cap_mult=cap_mult, blocks=blocks,
        closed=book_state.closed)
    return {"date": _iso(date), "underlying": underlying, "candidate": cand,
            "reasons": list(reasons) if cand is None else [], "notes": list(reasons) if cand else [],
            "regime": regime_label, "account_source": account.get("source")}


def _leg_context(leg: dict | None) -> dict | None:
    keep = ("symbol", "strike", "bid", "ask", "mid", "delta", "iv", "vega", "open_interest", "volume", "quote_time")
    return {k: (leg or {}).get(k) for k in keep} if leg else None


def menu_context(menu: dict, snapshot: dict | None, when: str | None) -> dict:
    """What Claude sees (OPT-33): code-computed numbers and fixed labels only, never headlines (non-negotiable 3)."""
    c = menu.get("candidate")
    cboe = (snapshot or {}).get("cboe") or {}
    ctx = {"book": BOOK, "date": menu["date"], "context_schema": CONTEXT_SCHEMA,
           "order_session": next_session(menu["date"]), "reason_codes": list(SKIP_CODES),
           "menu": {"kind": "one spread" if c else "none", "choices": ["follow", "skip"] if c else ["follow"]},
           "regime": {"label": menu.get("regime")},
           "chain": {"feed": "indicative", "when": when, "note": FEED_NOTE,
                     "complete": bool((snapshot or {}).get("complete")),
                     "vix": (cboe.get("VIX") or {}).get("value"), "vix3m": (cboe.get("VIX3M") or {}).get("value")},
           "no_trade_reasons": list(menu.get("reasons") or [])}
    if c:
        keys = ("underlying", "expiry", "dte", "spot", "width", "contracts", "mid_credit", "natural_credit",
                "quoted_cost", "cost_share", "max_loss", "budgeted_loss", "min_credit", "permission")
        ctx["candidate"] = {**{k: c.get(k) for k in keys}, "short": _leg_context(c.get("short")),
                            "long": _leg_context(c.get("long"))}
        ctx["prediction_rule"] = prediction_template(c)
    return ctx


def prediction_template(candidate: dict) -> dict:
    """OPT-34: the only prediction a skip may carry. Code fixes everything except the probability."""
    short = candidate["short"]
    spot = float(candidate["spot"])
    return {"symbol": candidate.get("underlying", "SPY"), "horizon": PREDICTION_HORIZON, "direction": "below",
            "threshold_pct": round((float(short["strike"]) / spot - 1) * 100, 4),
            "min_probability_exclusive": round(abs(float(short["delta"])), 4)}


class SkipPrediction(BaseModel):
    """OPT-34 / CL-5: the skip's prediction. Only `probability` is Claude's; code fixes the rest."""

    model_config = ConfigDict(extra="ignore")
    probability: float
    symbol: str = "SPY"
    horizon: int = PREDICTION_HORIZON
    direction: str = "below"
    threshold_pct: float | None = None


class OptionsDecision(BaseModel):
    """One skip sample (OPT-33). `choice` "follow" keeps the code's spread; "skip" drops it for this run.
    Unknown keys (a strike, a width, a size) are allowed by the parser only so they can be logged and dropped."""

    model_config = ConfigDict(extra="allow")
    date: str
    choice: Literal["follow", "skip"]
    reason_code: Literal[("NONE",) + SKIP_CODES] = "NONE"  # type: ignore[valid-type]
    evidence: list[str] = []
    event_date: str = ""
    prediction: SkipPrediction | None = None
    rationale: str = ""
    meta: dict = {}


def decision_schema() -> dict:
    schema = OptionsDecision.model_json_schema()
    schema["additionalProperties"] = False
    return schema


def instructions_text(menu: dict) -> str:
    c = menu.get("candidate")
    lines = [
        f"# Book O menu for {menu['date']} (shadow; OPT-33)", "",
        "Code built ONE monthly SPY bull put spread (or none). You may only follow it or skip it.",
        "You never choose strikes, widths, sizes or exits, and never compute greeks or MaxLoss (OPT-33).",
        "Book O is a measurement experiment: the replay expects the affordable spread to lose slightly.",
        "Be skeptical of anything widely promoted; promotion or hype is never evidence (owner decision 8).", "",
        "Write `skip_<k>.json` (k = 1..samples) in this folder, each produced independently, matching schema.json:",
        '  {"date": "%s", "choice": "follow" | "skip", "reason_code": "NONE" | %s,' % (
            menu["date"], " | ".join(f'"{c_}"' for c_ in SKIP_CODES)),
        '   "evidence": ["candidate.short.bid", ...], "event_date": "", "prediction": {"probability": 0.3},',
        '   "rationale": "", "meta": {"model": "...", "sample": k}}', "",
        "A skip needs a reason code, evidence paths into context.json (CL-2) and a prediction that argues AGAINST the",
        "trade: SPY closes below the short strike after 20 sessions (see prediction_rule). Code drops a skip whose",
        "probability is not above the short put's |delta| (OPT-34). SCHEDULED_EVENT is allowed only when FOMC, CPI",
        "or payrolls falls on the order session (context.order_session), given as event_date.",
    ]
    if not c:
        lines += ["", "Today there is no spread, so there is nothing to skip: write choice \"follow\"."]
    return "\n".join(lines) + "\n"


def write_menu(menu: dict, snapshot, when, state_dir, samples: int = 3) -> dict[str, str]:
    """Write context.json, schema.json, instructions.md and menu.json (the full candidate, for run_options)."""
    folder = pending_dir(menu["date"], state_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stale = sorted(folder.glob("skip_*.json"))
    if stale:  # answers to an earlier menu of the same date no longer apply
        (folder / "stale").mkdir(exist_ok=True)
        for f in stale:
            f.replace(folder / "stale" / f.name)
    files = {"context": _write_json(folder / "context.json", menu_context(menu, snapshot, when)),
             "schema": _write_json(folder / "schema.json", decision_schema()),
             "menu": _write_json(folder / "menu.json", {**menu, "samples": int(samples)})}
    (folder / "instructions.md").write_text(instructions_text(menu))
    files["instructions"] = folder / "instructions.md"
    return {k: str(v) for k, v in files.items()} | {"dir": str(folder)}


def prepare_options(cfg, state_dir=None, *, date=None, samples: int = 3, now=None, bars: dict | None = None,
                    regime_label: str | None = None, equity=None, uncommitted_cash=None) -> dict:
    """OPT-33: build the day's one spread (or none) from the logged close snapshot and write the skip-only menu.

    Never touches a broker or places an order. `bars` ({"SPY": daily bars}) gives the REG-2 label when
    `regime_label` is not passed; an unknown regime means permission 0 (no spread).
    """
    sd = _dir(state_dir)
    day = _iso(date) if date is not None else _today(now)
    shadow = osh.ShadowO.load(sd)
    snap, when = load_chain(day, sd)
    label, why = (regime_label, "argument") if regime_label else regime_label_from_bars(bars, day)
    acct = account_view(sd, shadow, day, equity=equity, uncommitted_cash=uncommitted_cash)
    breakers = shadow.book.apply_breakers(day_pnl=_last_day_pnl(shadow.book), o_pnl=_last_o_pnl(shadow.book),
                                          equity=acct["equity"], date=day, policy=_policy(cfg))
    menu = build_menu(cfg, day, snap, regime_label=label, account=acct, book_state=shadow.book,
                      blocks=_blocks(breakers), cap_mult=breakers["cap_mult"])
    menu["regime_source"] = why
    files = write_menu(menu, snap, when, sd, samples)
    return {"date": day, "when": when, "candidate": menu["candidate"], "reasons": menu["reasons"],
            "regime": label, "files": files, "samples": int(samples)}


def _last_o_pnl(ledger: OptionsBook) -> float:
    return float(ledger.marks[-1]["o_pnl"]) if ledger.marks else 0.0


def _last_day_pnl(ledger: OptionsBook) -> float:
    return float(ledger.marks[-1]["day_pnl"]) if ledger.marks else 0.0


# --- skip decisions (OPT-33, OPT-34) ------------------------------------------------------------------------------


def find_decision_files(date, state_dir=None) -> list[Path]:
    return sorted(pending_dir(date, state_dir).glob("skip_*.json"))


def parse_decision_file(path, date) -> tuple[OptionsDecision | None, list[str]]:
    """Read one sample. Wrong date or unreadable -> dropped. Extra keys (strikes, sizes...) are dropped (OPT-33)."""
    try:
        raw = json.loads(Path(path).read_text())
        dec = OptionsDecision.model_validate(raw)
    except (OSError, ValueError, ValidationError) as e:
        return None, [f"{Path(path).name}: unreadable or invalid ({str(e)[:160]})"]
    problems = []
    if dec.date != _iso(date):
        return None, [f"{Path(path).name}: date {dec.date} is not {_iso(date)}"]
    extra = sorted((dec.model_extra or {}).keys())
    if extra:
        problems.append(f"{Path(path).name}: OPT-33 dropped keys Claude may not set: {', '.join(extra)}")
    return dec, problems


def validate_skip(dec: OptionsDecision, menu: dict, context: dict | None) -> tuple[dict | None, list[str]]:
    """A skip that survives OPT-33/34 and CL-2/CL-8, as a plain dict with the code-built prediction; else (None, why)."""
    c = menu.get("candidate")
    if dec.choice != "skip":
        return None, []
    if not c:
        return None, ["skip ignored: there is no spread today"]
    if dec.reason_code not in SKIP_CODES:
        return None, ["skip dropped: needs a reason code from " + ", ".join(SKIP_CODES) + " (CL-8)"]
    ok, why = _evidence_ok(context, dec.evidence)
    if not ok:
        return None, [f"skip dropped: {why}"]
    if dec.reason_code == "SCHEDULED_EVENT" and dec.event_date != next_session(menu["date"]):
        return None, [f"skip dropped: SCHEDULED_EVENT only when the event is on the order session "
                      f"{next_session(menu['date'])} (CL-8 for book O)"]
    return _skip_prediction(dec, c)


def _skip_prediction(dec: OptionsDecision, c: dict) -> tuple[dict | None, list[str]]:
    """OPT-34: code fixes symbol, horizon, direction and threshold; the probability must exceed the short |delta|."""
    if dec.prediction is None or ob.num(dec.prediction.probability) is None:
        return None, ["skip dropped: OPT-34 needs a prediction with a probability"]
    tpl = prediction_template(c)
    notes = []
    given = dec.prediction.model_dump()
    for k in ("symbol", "horizon", "direction", "threshold_pct"):
        if given.get(k) is not None and given[k] != tpl[k]:
            notes.append(f"OPT-34: prediction {k} {given[k]!r} replaced by code's {tpl[k]!r}")
    prob = min(0.95, max(0.05, float(dec.prediction.probability)))
    if prob <= tpl["min_probability_exclusive"]:
        return None, notes + [f"skip dropped: probability {prob:.2f} is not above the short put's |delta| "
                              f"{tpl['min_probability_exclusive']:.2f}, so it argues for the trade (OPT-34)"]
    pred = {k: tpl[k] for k in ("symbol", "horizon", "direction", "threshold_pct")}
    return {"reason_code": dec.reason_code, "evidence": list(dec.evidence), "event_date": dec.event_date,
            "rationale": dec.rationale[:500], "prediction": {**pred, "probability": prob},
            "model": (dec.meta or {}).get("model", "unknown")}, notes


def _evidence_ok(context, paths) -> tuple[bool, str]:
    try:
        from ..decisions import evidence_ok
    except Exception:  # noqa: BLE001 - without the checker only a non-empty list of strings passes
        ok = isinstance(paths, list) and bool(paths) and all(isinstance(p, str) and p.strip() for p in paths)
        return ok, "" if ok else "no evidence paths (CL-2)"
    return evidence_ok(context, paths)


def combine_skips(files, menu: dict, context: dict | None, date, samples_requested: int | None = None) -> dict:
    """Guide rule 8 / CL-8: the skip is applied only when a strict majority of the samples REQUESTED (the menu's
    `samples`, or the number of files if more were written) are valid skips. A missing or unreadable sample
    counts as "no skip", as in decisions.combine_options_skips. Returns {skip | None, samples, skips, problems}."""
    files = list(files or [])
    valid, skips, problems = 0, [], []
    for f in files or []:
        dec, why = parse_decision_file(f, date)
        problems += why
        if dec is None:
            continue
        valid += 1
        s, why = validate_skip(dec, menu, context)
        problems += why
        if s:
            skips.append(s)
    n = max(int(ob.num(samples_requested, 0) or 0), len(files), 1)
    skip = skips[0] if skips and len(skips) * 2 > n else None
    if skips and skip is None:
        problems.append(f"skip not applied: {len(skips)} of {n} samples skipped ({valid} readable; "
                        "no strict majority)")
    return {"skip": skip, "samples": valid, "requested": n, "skips": len(skips), "problems": problems}


def skip_base_rate(bars: dict | None, pred: dict, date) -> float | None:
    """M-7 Brier_ref for an OPT-34 prediction: how often SPY fell below the same threshold over the same horizon
    in its own history up to `date` (trader.shadow.base_rate). None without enough bars."""
    df = (bars or {}).get(pred.get("symbol", "SPY"))
    if df is None or "close" not in df:
        return None
    try:
        from ..shadow import base_rate

        c = pd.to_numeric(df["close"], errors="coerce").dropna()
        c = c[pd.DatetimeIndex(c.index).normalize() <= pd.Timestamp(_iso(date))]
        return base_rate(c, int(pred["horizon"]), str(pred["direction"]), float(pred["threshold_pct"]))
    except Exception:  # noqa: BLE001 - no reference, the score stays informational
        return None


def add_skip_prediction(shadow: osh.ShadowO, skip: dict, candidate: dict, date, lot_id: str | None,
                        bars: dict | None = None) -> dict | None:
    """Store the OPT-34 prediction once per date (a re-run never duplicates it), with its M-7 base rate."""
    pid = f"O-skip-{_iso(date)}"
    if any(p.get("id") == pid for p in shadow.predictions):
        return None
    rec = {"id": pid, "date": _iso(date), "book": BOOK, **skip["prediction"], "linked_decision": f"skip:O:{lot_id}",
           "base_close": candidate.get("spot"), "base_rate": skip_base_rate(bars, skip["prediction"], date),
           "outcome": None,
           "tags": {"reason_code": skip["reason_code"], "informational": True}}
    shadow.predictions.append(rec)
    return rec


# --- the daily run ----------------------------------------------------------------------------------------------


def run_options(cfg, state_dir=None, *, decision_files=(), dry_run: bool = True, now=None, when: str | None = None,
                broker=None, bars: dict | None = None, regime_label: str | None = None, equity=None,
                uncommitted_cash=None) -> dict:
    """Book O's run. Shadow always; paper orders only when enabled + OPT-41 gate + not dry_run + a broker.

    `decision_files` are the Claude skip samples; empty means the files in today's pending folder. `when` is
    "close" (default: shadow entries and exits on the after-close snapshot) or "1545" (the OPT-17 order run).
    `broker` (an AlpacaPaperBroker or a fake) is read for OPT-6 and OPT-26/27; without one the run is shadow only.
    Returns the journal entry that is also appended to `state_dir/options/journal.jsonl`.
    """
    sd = _dir(state_dir)
    p = _policy(cfg)
    day = _today(now)
    when = when or "close"
    ledger, shadow, paper = OptionsBook.load(sd), osh.ShadowO.load(sd), _load_paper(sd)
    snap, snap_when = load_chain(day, sd, when)
    quotes, spots = all_quotes(snap), spots_of(snap, bars, day)
    entry = {"date": day, "when": when, "dry_run": bool(dry_run), "snapshot": snap_when, "feed_note": FEED_NOTE,
             "enabled": bool(p.get("enabled", False)), "notes": []}
    label, why = (regime_label, "argument") if regime_label else regime_label_from_bars(bars, day)
    entry["regime"] = {"label": label, "source": why}
    if broker is not None:  # read-only: fills are booked whatever the gate says, so the ledger never drifts
        _settle_paper(broker, ledger, paper, day, p, entry)
    acct, broker_blocks = _read_broker(broker, ledger, sd, p, entry)
    account = account_view(sd, shadow, day, acct=acct, equity=equity, uncommitted_cash=uncommitted_cash)
    entry["account"] = account
    gate = gate_status(cfg, sd, shadow=shadow, ledger=ledger)
    orders_ok = gate["orders_allowed"] and not dry_run and broker is not None
    entry["orders_allowed"] = orders_ok
    entry["alerts"] = {"paper": ob.entry_freeze_alerts(ledger.open_lots(), day, p),  # OPT-15: tell the owner
                       "shadow": ob.entry_freeze_alerts(shadow.book.open_lots(), day, p)}
    if when == "close":
        _shadow_close_run(cfg, sd, day, snap, quotes, spots, label, account, shadow, broker_blocks,
                          decision_files, entry, bars)
    candidate = entry.pop("_candidate", None)
    _evaluate(cfg, shadow, day, when, snap, quotes, spots, label, account, entry, sd)
    _paper_run(cfg, sd, broker, ledger, paper, day, when, quotes, spots, account, broker_blocks, gate, orders_ok,
               candidate, entry)
    osh.resolve_predictions(shadow, bars, day)
    shadow.save(sd)
    ledger.save(sd)
    _save_paper(sd, paper)
    _journal(sd, entry)
    return entry


def _read_broker(broker, ledger: OptionsBook, sd: Path, p: dict, entry: dict) -> tuple[dict | None, list[str]]:
    """OPT-6 start-up checks and the OPT-26/27 incident detector from the broker. No broker -> nothing read."""
    if broker is None:
        entry["notes"].append("no broker read: shadow run (OPT-6 and OPT-26 not checked; paper entries impossible)")
        return None, []
    blocks: list[str] = []
    acct = broker.options_account()
    try:
        positions = broker.positions_detail()
    except Exception as e:  # noqa: BLE001 - unknown positions: freeze entries, exits still run
        positions = None
        blocks.append(f"OPT-27: positions unreadable ({str(e)[:120]}); no new entries")
    activities = []
    try:
        activities = broker.option_activities() or []
        entry["activities"] = activities
    except Exception as e:  # noqa: BLE001 - activities are informational (paper posts them a day late)
        entry["notes"].append(f"option activities unreadable: {str(e)[:120]}")
    other_raw = other_books_stock(sd)
    if positions is not None:
        booked = book_assignments(positions, ledger, other_raw, entry["date"], activities)
        if booked:
            entry["assignments"] = booked
    other, notes = explain_pending(positions or [], other_raw, rules_pending_stock(sd), ledger.o_stock)
    entry["notes"] += notes
    blocks += startup_checks(acct, positions or [], other, ledger.o_stock)
    if positions is not None:
        inc = ob.detect_incidents(positions, ledger.open_lots(), other_books_stock=other, o_stock=ledger.o_stock,
                                  maintenance_margin=acct.get("maintenance_margin"),
                                  check_margin=bool(ledger.open_lots()), policy=p)
        blocks += inc["incidents"] + inc["mismatches"]
        entry["incidents"] = {k: inc[k] for k in ("incidents", "mismatches", "stock_excess")}
        if inc["incidents"]:
            entry["cleanup_plan"] = ob.cleanup_plan(inc, ledger.open_lots(), entry["date"], p, o_stock=ledger.o_stock)
    entry["broker_blocks"] = blocks
    return acct, blocks


def book_assignments(positions, ledger: OptionsBook, other_stock: dict | None, date,
                     activities=None) -> list[dict]:
    """OPT-26: book an assignment of a short put into O's ledger (record_assignment -> o_stock).

    Detected from positions (paper posts OPASN a day late, so activities only corroborate): a lot's short leg
    has fewer contracts at the broker than in the ledger while its long leg is intact, and the broker holds stock
    of the underlying that neither the rules ledger nor O's o_stock explains, at least 100 shares per contract.
    Booking is idempotent: once booked, the ledger matches the broker and nothing more is found."""
    opt: dict[str, float] = {}
    stock: dict[str, float] = {}
    for pos in positions or []:
        sym, q = str(pos.get("symbol", "")), float(ob._pos_qty(pos))
        (opt if is_occ(sym) else stock)[sym] = (opt if is_occ(sym) else stock).get(sym, 0.0) + q
    held_short = {s: max(0.0, -q) for s, q in opt.items()}
    held_long = {s: max(0.0, q) for s, q in opt.items()}
    opasn = {str(a.get("symbol")) for a in activities or [] if str(a.get("activity_type", "")).upper() == "OPASN"}
    out = []
    for lot in sorted(ledger.open_lots(), key=lambda l: l.lot_id):
        s_sym, l_sym, u = lot.short_leg.symbol, lot.long_leg.symbol, lot.underlying
        have_s = min(float(lot.short_leg.qty), held_short.get(s_sym, 0.0))
        held_short[s_sym] = held_short.get(s_sym, 0.0) - have_s
        have_l = min(float(lot.long_leg.qty), held_long.get(l_sym, 0.0))
        held_long[l_sym] = held_long.get(l_sym, 0.0) - have_l
        shortfall = int(round(lot.short_leg.qty - have_s))
        if shortfall <= 0 or have_l < lot.long_leg.qty:  # both legs moved: an exit fill, not an assignment
            continue
        unexplained = stock.get(u, 0.0) - float((other_stock or {}).get(u, 0.0)) - float(ledger.o_stock.get(u, 0.0))
        k = min(shortfall, int(unexplained // MULTIPLIER + 1e-9))
        if k <= 0:
            continue
        ledger.record_assignment(lot.lot_id, k, date)
        stock[u] = stock.get(u, 0.0)  # o_stock now explains these shares
        out.append({"lot_id": lot.lot_id, "contracts": k, "shares": k * MULTIPLIER, "symbol": s_sym,
                    "opasn_seen": s_sym in opasn})
    return out


def _shadow_close_run(cfg, sd, day, snap, quotes, spots, label, account, shadow: osh.ShadowO, broker_blocks,
                      decision_files, entry, bars=None) -> None:
    """OPT-36 shadow book on the after-close snapshot: breakers, exits, the menu's spread, the skip, variants."""
    p = _policy(cfg)
    marks = osh.mark_book(shadow.book, quotes, spots, day)
    br = shadow.book.apply_breakers(day_pnl=marks["day_pnl"], o_pnl=marks["o_pnl"], equity=account["equity"],
                                    date=day, policy=p)
    entry["shadow_breakers"] = br
    close_all = "OPT-31 drawdown halt" if br["close_all"] else None
    closed = osh.update_exits(shadow.book, quotes, spots, day, p, close_all_reason=close_all)
    closed += osh.update_exits(shadow.skips, quotes, spots, day, p)
    closed += osh.update_exits(shadow.variants, quotes, spots, day, p)
    osh.update_trackers(shadow.trackers, quotes, spots, day, p)
    entry["shadow_exits"] = [{k: r.get(k) for k in ("lot_id", "underlying", "reason", "R", "R_paper")} for r in closed]
    blocks = _blocks(br, broker_blocks)
    # The rules' spread is rebuilt on this run's state (the shadow book follows the rules, not Claude).
    menu = build_menu(cfg, day, snap, regime_label=label, account=account, book_state=shadow.book, blocks=blocks,
                      cap_mult=br["cap_mult"])
    prepared = _load_menu(day, sd)
    entry["menu"] = {"candidate": bool(menu.get("candidate")), "reasons": menu.get("reasons"),
                     "prepared": prepared is not None}
    decision = _decisions(prepared, menu, day, sd, decision_files)
    entry["skip"] = decision
    _shadow_entry(cfg, shadow, menu, decision.get("skip"), day, snap, spots, account, blocks, br, quotes, entry, sd,
                  bars)
    entry["opt39"] = _opt39(cfg, shadow, day, snap, label, account, blocks)
    entry["_candidate"] = menu.get("candidate")


def _load_menu(day, sd) -> dict | None:
    m = _read_json(pending_dir(day, sd) / "menu.json", None)
    return m if isinstance(m, dict) and m.get("date") == _iso(day) else None


def same_spread(a: dict | None, b: dict | None) -> bool:
    """True when two candidates are the same two legs (a skip answers one exact spread)."""
    if not a or not b:
        return False
    return all((a.get(k) or {}).get("symbol") == (b.get(k) or {}).get("symbol") for k in ("short", "long"))


def _decisions(prepared: dict | None, menu: dict, day, sd, decision_files) -> dict:
    """Apply the session's skip samples to the prepared menu. A skip counts only for the exact spread it saw."""
    files = list(decision_files or []) or find_decision_files(day, sd)
    if prepared is None:
        return {"skip": None, "samples": 0, "skips": 0,
                "problems": ["no menu prepared today: nothing Claude could skip"] if files else []}
    context = _read_json(pending_dir(day, sd) / "context.json", None) or menu_context(prepared, None, None)
    out = combine_skips(files, prepared, context, day, samples_requested=prepared.get("samples"))
    if out["skip"] and not same_spread(prepared.get("candidate"), menu.get("candidate")):
        out["problems"].append("skip answered a different spread than this run's; the skip shadow is still kept")
        out["stale_spread"] = True
    return out


def _shadow_entry(cfg, shadow: osh.ShadowO, menu, skip, day, snap, spots, account, blocks, br, quotes, entry, sd,
                  bars=None):
    """Book the rules' spread in the shadow book (OPT-36) whatever Claude says, and a skip shadow (OPT-34).
    Both pass options.risk.validate_spread_order in shadow mode first (the same order rules as paper)."""
    c = menu.get("candidate")
    if not c:
        return
    p = _policy(cfg)
    order = orisk.spread_order(c, client_order_id=f"{p.get('order_prefix', 'OPT-')}shadow")
    common = {"mode": "shadow", "date": day, "equity": account["equity"],
              "uncommitted_cash": account["uncommitted_cash"], "quotes": quotes, "spot": spots.get(c["underlying"])}
    ok, why = orisk.validate_spread_order(order, shadow.book, p, cap_mult=br["cap_mult"], blocks=blocks, **common)
    tags = {"regime": menu.get("regime"), "opt20": osh.opt20_record(snap), "bil_rate": _bil_rate(day, sd),
            "skipped": bool(skip), "source": "OPT-36"}
    if ok:
        lot = osh.open_shadow(shadow.book, c, day, tags=tags, policy=p)
        if lot:
            shadow.trackers.append(osh.new_tracker(lot))
            entry["shadow_entry"] = {"lot_id": lot.lot_id, "contracts": lot.contracts,
                                     "credit": lot.entry_credit_per_share, "max_loss": lot.max_loss}
    else:
        entry["shadow_entry_rejected"] = why
    if skip:
        lot = None
        if orisk.validate_spread_order(order, shadow.skips, p, **common)[0]:
            lot = osh.open_shadow(shadow.skips, c, day, policy=p, id_prefix="K",
                                  tags={**tags, "source": "OPT-34 skip", "reason_code": skip["reason_code"]})
        if add_skip_prediction(shadow, skip, c, day, lot.lot_id if lot else None, bars) is not None:
            shadow.skip_log.append({"date": _iso(day), **skip, "lot_id": lot.lot_id if lot else None})


def _bil_rate(day, sd=None) -> float | None:
    """The logged T-bill rate for the BIL benchmark (OPT-38), from the local cache only (never the network here)."""
    try:
        from .pricing import fetch_tbill_rates, rate_on

        def offline(_url):
            raise OSError("offline: cache only")

        return rate_on(fetch_tbill_rates(state_dir=_dir(sd), fetch=offline, max_age_hours=1e9), day)
    except Exception:  # noqa: BLE001 - no cache: the report marks the BIL rate as assumed
        return None


def _opt39(cfg, shadow: osh.ShadowO, day, snap, label, account, blocks) -> dict:
    """OPT-39 shadow variants: the same put spread on QQQ and IWM, each with its own caps and cycles."""
    p = _policy(cfg)
    out = {}
    for u in osh.VARIANT_UNDERLYINGS:
        own = OptionsBook(lots={l.lot_id: l for l in shadow.variants.open_lots() if l.underlying == u},
                          closed=[r for r in shadow.variants.closed if r.get("underlying") == u])
        menu = build_menu(cfg, day, snap, regime_label=label, account=account, book_state=own, blocks=blocks,
                          underlying=u)
        c = menu["candidate"]
        lot = osh.open_shadow(shadow.variants, c, day, tags={"source": "OPT-39", "regime": label},
                              policy=p, id_prefix=f"V{u}") if c else None
        out[u] = {"lot_id": lot.lot_id if lot else None, "reasons": menu["reasons"][:3]}
    return out


def _evaluate(cfg, shadow: osh.ShadowO, day, when, snap, quotes, spots, label, account, entry, sd=None) -> None:
    """One evaluation row per run for OPT-13 (no-trade rate, also on 15:45 snapshots), OPT-41 and OPT-20."""
    p = _policy(cfg)
    spot = spots.get("SPY")
    eq = account["equity"]
    pair = osh.measurement_pair(quotes, spot, day, p, eq if eq is not None else _fallback_equity(cfg))
    vix = (((snap or {}).get("cboe") or {}).get("VIX") or {}).get("value")
    mc = osh.model_credit(pair, vix, rate=_bil_rate(day, sd))
    exps = ob.monthly_expiry_candidates([q for q in quotes if q.underlying == "SPY" and q.type == "put"], day, p)
    reasons = (entry.get("menu") or {}).get("reasons") or []
    row = {"date": day, "when": when, "underlying": "SPY", "in_window": bool(exps),
           "expiry": exps[0] if exps else None, "regime": label,
           "eligible": bool(exps and pair and ob.permission(label, p) > 0),
           "candidate": bool((entry.get("shadow_entry") or {}).get("lot_id"))
           or bool(exps and _cycle_entered(shadow.book, exps[0])),
           "opt13_blocked": bool(pair and pair["cost_share"] > float(p["max_quoted_cost_pct"]) + 1e-9),
           "reasons": reasons[:5], "pair": pair, **mc, "opt20": osh.opt20_record(snap)}
    osh.add_evaluation(shadow, row)
    entry["evaluation"] = {k: row[k] for k in ("in_window", "eligible", "opt13_blocked", "ratio")}


def _cycle_entered(book: OptionsBook, expiry: str) -> bool:
    """The shadow book holds (or held) a spread of this monthly cycle, so OPT-13 did not block it (both the
    after-close and the 15:45 rows use this, so the 15:45 no-trade rate is not overstated)."""
    if any(l.expiry == expiry and l.underlying == "SPY" for l in book.all_lots()):
        return True
    for r in book.closed:
        exp = r.get("expiry") or (r.get("lot") or {}).get("expiry")
        if exp == expiry and (r.get("underlying") or (r.get("lot") or {}).get("underlying")) == "SPY":
            return True
    return False


def _fallback_equity(cfg) -> float:
    """Measurement only (OPT-13/OPT-41 pair): the simulator's starting equity when no account was read."""
    try:
        return float(cfg.playbook["execution"]["starting_cash"])
    except (AttributeError, KeyError, TypeError, ValueError):
        return 100_000.0


# --- the paper path (never used while options_book.enabled is false; fake brokers in tests) --------------------


def _load_paper(sd) -> dict:
    d = _read_json(Path(sd) / BOOK / PAPER_FILE, {}) or {}
    return {"pending": list(d.get("pending") or []), "intents": list(d.get("intents") or []),
            "exit_tries": dict(d.get("exit_tries") or {}), "exits_due": dict(d.get("exits_due") or {}),
            "log": list(d.get("log") or [])[-500:]}


def _save_paper(sd, paper: dict) -> None:
    _write_json(Path(sd) / BOOK / PAPER_FILE, paper)


def _client_id(prefix: str, day, kind: str) -> str:
    """Owner decision 6: every O order carries the `OPT-` prefix; a random tail keeps reruns unique (<= 48)."""
    return f"{prefix}{_iso(day).replace('-', '')}-{kind}-{secrets.token_hex(3)}"[:48]


def recheck_entry(candidate: dict, quotes, spot_now, day, policy: dict, *, retry: bool = False) -> tuple[dict | None,
                                                                                                           list[str]]:
    """OPT-17 at the 15:45 order run: cancel when SPY moved > 1% from the decision close; re-check the short put's
    |delta| band, the OPT-12 leg filter and OPT-13 on fresh quotes; re-size (OPT-8/OPT-19, never up); re-price the
    limit (OPT-14: mid credit - 10% of the quoted cost, or - 25% on the one retry). The caps OPT-8..10 are then
    checked by options.risk.validate_spread_order. Returns (fresh candidate | None, reasons)."""
    p = ob.ob_policy(policy)
    why = ob.entry_recheck(candidate, spot_now, p)
    if why:
        return None, [why]
    qmap = ob._by_symbol(quotes)
    short, long = qmap.get(candidate["short"]["symbol"]), qmap.get(candidate["long"]["symbol"])
    probs = [f"short: {x}" for x in ob.leg_problems(short, day, p)] + \
            [f"long: {x}" for x in ob.leg_problems(long, day, p)]
    if probs:
        return None, ["OPT-17/OPT-12: " + "; ".join(probs)]
    lo, hi = (float(x) for x in p["target_short_delta"])
    if not lo - 1e-9 <= abs(short.delta) <= hi + 1e-9:
        return None, [f"OPT-17: short |delta| {abs(short.delta):.3f} left the {lo}-{hi} band"]
    px = ob.spread_prices(short, long)
    if px is None or px["mid_credit"] <= 0:
        return None, ["OPT-17: no positive mid credit on fresh quotes"]
    if px["quoted_cost"] / px["mid_credit"] > float(p["max_quoted_cost_pct"]) + 1e-9:
        return None, [f"OPT-17/OPT-13: quoted cost {px['quoted_cost'] / px['mid_credit']:.0%} of the mid credit"]
    return _fresh_candidate(candidate, short, long, px, p, retry, spot_now)


def _fresh_candidate(c, short, long, px, p, retry, spot_now) -> tuple[dict | None, list[str]]:
    risk = ob.per_contract_risk(c["width"], px["mid_credit"], px["quoted_cost"], float(p["fees_per_contract"]))
    n = min(int(c["contracts"]), ob.size_contracts(c["per_trade_cap"], risk["budgeted_loss_pc"], c["permission"]))
    if n <= 0:
        return None, ["OPT-17/OPT-8: fresh budgeted loss leaves 0 contracts"]
    share = p["retry_credit_cost_share"] if retry else p["min_credit_cost_share"]
    credit = round(px["mid_credit"] - float(share) * px["quoted_cost"], 2)
    if credit <= 0:
        return None, ["OPT-14: minimum credit is not positive"]
    fresh = {**c, "short": ob._leg_view(short), "long": ob._leg_view(long), **px, "contracts": n,
             "max_loss_per_contract": risk["max_loss_pc"], "budgeted_loss_per_contract": risk["budgeted_loss_pc"],
             "limit_price": -credit, "recheck_spot": ob.num(spot_now), "retry": retry}
    return fresh, []


def _paper_run(cfg, sd, broker, ledger: OptionsBook, paper: dict, day, when, quotes, spots, account, blocks, gate,
               orders_ok: bool, candidate: dict | None, entry: dict) -> None:
    """OPT-17: every paper order (exits, the OPT-26 clean-up and entries) is sent only at the 15:45 run; orders are
    never queued overnight. The after-close run decides: it records the exits that are due and the next entry
    intent. Nothing is sent unless orders are allowed; otherwise it logs why not."""
    p = _policy(cfg)
    br = _paper_marks(ledger, quotes, spots, day, account, p, entry)
    halt = "OPT-31 drawdown halt" if (br and br["close_all"]) or ledger.halted else None
    open_ids = {l.lot_id for l in ledger.open_lots()}
    due = {k: v for k, v in (paper.get("exits_due") or {}).items() if k in open_ids}
    exits = []
    for lot in ledger.open_lots():
        if lot.status == "incident":  # OPT-26: the clean-up closes what is left of a broken spread first
            entry["notes"].append(f"{lot.lot_id}: spread exit held; OPT-26 assignment clean-up first")
            continue
        reason = halt or ob.exit_signal(lot, quotes, spots.get(lot.underlying), day, p) or \
            (due.get(lot.lot_id) or {}).get("reason")
        if reason:
            exits.append((lot, reason))
            due.setdefault(lot.lot_id, {"reason": reason, "date": _iso(day)})
    paper["exits_due"] = due
    if not orders_ok:
        if exits:
            entry["notes"].append(f"{len(exits)} paper exit(s) due but orders are not allowed "
                                  f"(enabled={gate['enabled']}, gate={gate['paper_start_ok']}, dry run or no broker)")
        return
    if when == "close":
        if exits:
            entry["exits_due"] = [{"lot_id": l.lot_id, "reason": r} for l, r in exits]
            entry["notes"].append(f"{len(exits)} paper exit(s) due: sent at the next 15:45 run (OPT-17)")
        _queue_intent(paper, day, candidate, entry, _intent_blocks(ledger, day, p, br))
    elif when == "1545":
        _run_cleanup(broker, ledger, paper, entry.get("cleanup_plan") or [], day, quotes, spots, gate, p, entry)
        for lot, reason in exits:
            _paper_exit(broker, ledger, paper, lot, reason, day, quotes, spots, gate, p, entry)
        _submit_intents(broker, ledger, paper, day, quotes, spots, account, blocks, gate, p, entry)


def _intent_blocks(ledger: OptionsBook, day, p: dict, br: dict | None) -> list[str]:
    """What stops the after-close run from queuing an entry for the next session: the paper ledger's own OPT-30/31
    breakers on today's close mark (OPT-30: a loss today means no entry next session) and the OPT-15 freeze."""
    return _blocks(br, ob.entry_freeze_alerts(ledger.open_lots(), day, p))


def _prior_session_pnl(ledger: OptionsBook, day) -> float:
    """OPT-30 at the 15:45 run: the day P&L of the last completed session (the latest mark dated before today),
    not today's intraday change."""
    prior = [m for m in ledger.marks if str(m.get("date")) < _iso(day)]
    return float(prior[-1]["day_pnl"]) if prior else 0.0


def _paper_marks(ledger: OptionsBook, quotes, spots, day, account, p, entry) -> dict | None:
    """OPT-30/OPT-31 for the paper ledger: record today's mark and run the breakers (the halt latches).
    Skipped when a held leg has no quote today, so a missing chain never fakes a drawdown."""
    if not (ledger.open_lots() or ledger.marks):
        return None
    have = {q.symbol for q in quotes or []}
    if any(s not in have for l in ledger.open_lots() for s in (l.short_leg.symbol, l.long_leg.symbol)
           if l.short_leg.qty or l.long_leg.qty):
        entry["notes"].append("paper marks skipped: a held leg has no quote today")
        return None
    pnl = o_pnl(ledger, quotes, spots.get("SPY"))
    day_pnl = ledger.record_mark(day, pnl)
    br = ledger.apply_breakers(day_pnl=day_pnl, o_pnl=pnl, equity=account["equity"], date=day, policy=p)
    entry["paper_breakers"] = br
    return br


def _queue_intent(paper: dict, day, candidate: dict | None, entry: dict, blocks=()) -> None:
    """After the close: an unskipped spread becomes one entry intent for the next 15:45 run (OPT-17), unless the
    paper ledger's breakers or the OPT-15 freeze stop entries next session (logged)."""
    if not candidate or (entry.get("skip") or {}).get("skip"):
        return
    if blocks:
        entry["notes"].append("paper entry not queued: " + "; ".join(list(blocks)[:3]))
        return
    if any(it.get("decision_date") == _iso(day) for it in paper["intents"]):
        return
    paper["intents"].append({"decision_date": _iso(day), "session": next_session(day), "tries": 0,
                             "candidate": candidate})


def _submit_intents(broker, ledger, paper, day, quotes, spots, account, blocks, gate, p, entry) -> None:
    """OPT-17: each intent due today is re-checked on fresh quotes and sent once; nothing waits overnight."""
    keep = []
    for it in paper["intents"]:
        if it["session"] > _iso(day):
            keep.append(it)
            continue
        if it["session"] < _iso(day):
            entry["notes"].append(f"entry intent from {it['decision_date']} expired unsent (orders never queue)")
            continue
        res = _submit_entry(broker, ledger, paper, it, day, quotes, spots, account, blocks, gate, p)
        entry.setdefault("paper_orders", []).append(res)
    paper["intents"] = keep


def _entry_window_ok(c: dict, day, p: dict) -> str | None:
    days = ob.dte(c["expiry"], day)
    if days < int(p["entry_dte"]["last"]):
        return f"OPT-18: DTE {days} below the entry window; the cycle is lost"
    return None


def _submit_entry(broker, ledger, paper, it, day, quotes, spots, account, blocks, gate, p) -> dict:
    """Re-check (OPT-17), validate in paper mode (options.risk) and send one mleg entry through the broker."""
    c = it["candidate"]
    why = _entry_window_ok(c, day, p)
    fresh, reasons = (None, [why]) if why else recheck_entry(c, quotes, spots.get(c["underlying"]), day, p,
                                                              retry=it.get("tries", 0) > 0)
    if fresh is None:
        return {"status": "cancelled", "reasons": reasons}
    order = orisk.spread_order(fresh, client_order_id=_client_id(p.get("order_prefix", "OPT-"), day, "open"))
    br = ledger.apply_breakers(day_pnl=_prior_session_pnl(ledger, day), o_pnl=_last_o_pnl(ledger),
                               equity=account["equity"], date=day, policy=p)
    freeze = ob.entry_freeze_alerts(ledger.open_lots(), day, p)  # OPT-15: a paper spread open at DTE <= 2
    ok, why = orisk.validate_spread_order(order, ledger, p, mode="paper", date=day, equity=account["equity"],
                                          uncommitted_cash=account["uncommitted_cash"],
                                          gate_ok=gate["paper_start_ok"], cap_mult=br["cap_mult"],
                                          blocks=_blocks(br, list(blocks) + freeze), quotes=quotes,
                                          spot=spots.get(c["underlying"]))
    if not ok:
        return {"status": "rejected", "reasons": why}
    res = broker.submit_mleg(order, enabled=bool(p.get("enabled")), gate_ok=gate["paper_start_ok"],
                             prefix=p.get("order_prefix", "OPT-"))
    if res.get("status") not in ("refused", "error"):
        paper["pending"].append({"client_order_id": order["client_order_id"], "broker_order_id": res.get("id"),
                                 "intent": "open", "date": _iso(day), "qty": order["qty"], "candidate": fresh,
                                 "tries": int(it.get("tries", 0)) + 1, "decision_date": it["decision_date"],
                                 "legs": [fresh["short"]["symbol"], fresh["long"]["symbol"]],
                                 "decision_spot": c.get("spot")})
    paper["log"].append({"date": _iso(day), "order": order, "result": res})
    return res


def _paper_exit(broker, ledger, paper, lot, reason, day, quotes, spots, gate, p, entry) -> None:
    """OPT-15 ladder: one try per 15:45 order run, forced exits start at natural, never above the width."""
    if any(r.get("lot_id") == lot.lot_id for r in paper["pending"]):
        return  # an exit order is still working
    tries = int(paper["exit_tries"].get(lot.lot_id, 0)) + 1
    lad = ob.ladder_detail(lot, quotes, tries, p, forced=ob.is_forced(reason, ob.dte(lot.expiry, day), p), date=day)
    c = {"short": {"symbol": lot.short_leg.symbol}, "long": {"symbol": lot.long_leg.symbol}}
    order = orisk.spread_order(c, intent="close", qty=lot.contracts, limit_price=lad["limit_price"],
                               client_order_id=_client_id(p.get("order_prefix", "OPT-"), day, "close"))
    ok, why = orisk.validate_spread_order(order, ledger, p, mode="paper", gate_ok=gate["paper_start_ok"])
    res = broker.submit_mleg(order, enabled=bool(p.get("enabled")), gate_ok=gate["paper_start_ok"],
                             prefix=p.get("order_prefix", "OPT-")) if ok else {"status": "rejected", "reasons": why}
    paper["exit_tries"][lot.lot_id] = tries
    if res.get("status") not in ("refused", "error", "rejected"):
        paper["pending"].append({"client_order_id": order["client_order_id"], "broker_order_id": res.get("id"),
                                 "intent": "close", "lot_id": lot.lot_id, "reason": reason, "date": _iso(day),
                                 "qty": lot.contracts, "legs": [lot.short_leg.symbol, lot.long_leg.symbol],
                                 "decision_spot": spots.get(lot.underlying)})
    paper["log"].append({"date": _iso(day), "order": order, "result": res})
    entry.setdefault("paper_orders", []).append({**res, "ladder": lad, "reason": reason})


def _settle_paper(broker, ledger: OptionsBook, paper: dict, day, p: dict, entry: dict) -> None:
    """Book mleg fills (OPT-7: partial fills book only what filled; the rest is cancelled, never chased).
    An entry that ends unfilled is re-priced once at the next 15:45 run (OPT-14), then dropped for the month."""
    if not paper["pending"]:
        return
    rows = {r["client_order_id"]: r for r in broker.mleg_fills(paper["pending"])}
    keep = []
    for rec in paper["pending"]:
        row = rows.get(rec["client_order_id"]) or {}
        if rec["intent"] in CLEANUP_INTENTS:
            _settle_cleanup(ledger, rec, row, day, entry)
            if not row.get("final"):
                keep.append(rec)
            continue
        fill = _ledger_fill(rec, row)
        if fill and rec["intent"] == "open":
            ledger.open_spread(rec["candidate"], fill, day, shadow=False, policy=p)
        elif fill:
            ledger.close_spread(rec["lot_id"], fill, day, rec.get("reason", "exit"), policy=p)
        if not row.get("final"):
            keep.append(rec)
        elif rec["intent"] == "open" and not fill and int(rec.get("tries", 1)) < 2:
            paper["intents"].append({"decision_date": rec.get("decision_date", rec["date"]),
                                     "session": next_session(day), "tries": int(rec.get("tries", 1)),
                                     "candidate": rec["candidate"]})
    paper["pending"] = keep
    entry["paper_settled"] = len(rows)


def _settle_cleanup(ledger: OptionsBook, rec: dict, row: dict, day, entry: dict) -> None:
    """Book what an OPT-26 clean-up order filled since the last run (filled_qty is cumulative)."""
    filled = float(ob.num(row.get("filled_qty"), 0.0) or 0.0)
    price = ob.num(row.get("filled_avg_price"))
    new = filled - float(rec.get("booked", 0.0))
    if new <= 1e-9 or price is None or rec.get("lot_id") not in ledger.lots:
        return
    if rec["intent"] == "stock_sale":
        ledger.record_stock_sale(rec["lot_id"], new, abs(price), day)
    else:
        ledger.close_orphan_long(rec["lot_id"], int(round(new)), abs(price), day)
    rec["booked"] = filled
    entry.setdefault("cleanup_fills", []).append({"intent": rec["intent"], "lot_id": rec["lot_id"], "qty": new,
                                                  "price": abs(price)})


def _run_cleanup(broker, ledger: OptionsBook, paper: dict, plan: list[dict], day, quotes, spots, gate, p,
                 entry: dict) -> None:
    """OPT-26 at the 15:45 run, in the plan's order: (1) sell O's assigned stock with a marketable limit, then
    (2) once the stock is flat, SELL_TO_CLOSE the orphan long put (never let it reach expiry in the money).
    Steps O may not trade (owner_review_stock) or must wait (wait_stock_flat) are only logged."""
    working = {(r.get("intent"), r.get("symbol")) for r in paper["pending"]}
    qmap = ob._by_symbol(quotes)
    prefix = p.get("order_prefix", "OPT-")
    for step in plan:
        act, sym = step.get("action"), str(step.get("symbol"))
        if act == "sell_stock":
            if ("stock_sale", sym) in working:
                continue
            lot = next((l for l in ledger.open_lots() if l.underlying == sym
                        and float((l.tags.get("broken") or {}).get("shares_open", 0.0)) > 1e-9), None)
            spot = ob.num(spots.get(sym))
            if lot is None or not spot:
                entry["notes"].append(f"OPT-26: cannot sell {sym} stock now (no broken lot or no price)")
                continue
            qty = int(min(float(step["qty"]), float(lot.tags["broken"]["shares_open"])))
            limit = round(spot * (1 - CLEANUP_STOCK_OFFSET), 2)
            order = {"client_order_id": _client_id(prefix, day, "asn"), "symbol": sym, "qty": qty, "side": "sell",
                     "type": "limit", "time_in_force": "day", "limit_price": limit, "intent": "stock_sale"}
            _send_cleanup(broker, paper, order, lot.lot_id, day, gate, p, entry)
        elif act == "sell_to_close_long":
            if ("orphan_long", sym) in working:
                continue
            lot = next((l for l in ledger.open_lots() if l.long_leg.symbol == sym
                        and l.long_leg.qty > l.short_leg.qty), None)
            if lot is None:
                entry["notes"].append(f"OPT-26: orphan long {sym} is not in O's ledger; owner review")
                continue
            qty = int(min(float(step["qty"]), lot.long_leg.qty - lot.short_leg.qty))
            q = qmap.get(sym)
            bid = ob.num(getattr(q, "bid", None))
            # Marketable: at the bid (or a cent when no bid), so it fills at the best available price.
            limit = max(0.01, round(bid, 2)) if bid is not None and bid > 0 else 0.01
            order = {"client_order_id": _client_id(prefix, day, "orph"), "symbol": sym, "qty": qty, "side": "sell",
                     "position_intent": "sell_to_close", "type": "limit", "time_in_force": "day",
                     "limit_price": limit, "intent": "orphan_long"}
            _send_cleanup(broker, paper, order, lot.lot_id, day, gate, p, entry)
        else:
            entry["notes"].append(f"OPT-26: {act} {sym} {step.get('qty')}: no order ({step.get('note', 'waits')})")


def _send_cleanup(broker, paper, order, lot_id, day, gate, p, entry) -> None:
    if not order["qty"] or order["qty"] <= 0:
        return
    send = getattr(broker, "submit_single", None)
    if send is None:
        res = {"status": "error", "error": "broker cannot send single-leg orders (OPT-26 clean-up)"}
    else:
        res = send(order, enabled=bool(p.get("enabled")), gate_ok=gate["paper_start_ok"],
                   prefix=p.get("order_prefix", "OPT-"))
    if res.get("status") not in ("refused", "error", "rejected"):
        paper["pending"].append({"client_order_id": order["client_order_id"], "broker_order_id": res.get("id"),
                                 "intent": order["intent"], "lot_id": lot_id, "symbol": order["symbol"],
                                 "date": _iso(day), "qty": order["qty"], "booked": 0.0,
                                 "legs": [order["symbol"]] if is_occ(order["symbol"]) else []})
    paper["log"].append({"date": _iso(day), "order": order, "result": res})
    entry.setdefault("paper_orders", []).append({**res, "cleanup": order["intent"]})


def _ledger_fill(rec: dict, row: dict) -> dict | None:
    """Alpaca mleg fill row -> the ledger's fill dict (cumulative filled_qty, leg average prices)."""
    qty = ob.num(row.get("filled_qty"), 0.0)
    if not qty:
        return None
    legs = {l.get("symbol"): ob.num(l.get("filled_avg_price")) for l in row.get("legs") or []}
    short_sym, long_sym = rec["legs"][0], rec["legs"][1]
    fill = {"order_id": rec["client_order_id"], "filled_qty": qty, "requested": rec.get("qty"),
            "spot": rec.get("decision_spot")}
    if legs.get(short_sym) is not None and legs.get(long_sym) is not None:
        fill["legs"] = {"short": legs[short_sym], "long": legs[long_sym]}
    elif ob.num(row.get("filled_avg_price")) is not None:
        px = abs(float(row["filled_avg_price"]))  # sign conventions differ; the order's intent fixes it
        fill["credit_per_share" if rec["intent"] == "open" else "debit_per_share"] = px
    else:
        return None
    if rec["intent"] == "close":
        fill["decision_spot"] = rec.get("decision_spot")
    return fill


# --- report (OPT-38, OPT-11, gates, amount invested) -----------------------------------------------------------


def report_options(cfg, state_dir=None) -> dict:
    """OPT-38 for the shadow book, the skip shadows and the paper ledger; OPT-25/OPT-39/OPT-20 variants; OPT-13
    no-trade rate (close and 15:45 snapshots); OPT-11 delta display; the gates; owner decision 6 amount invested."""
    sd = _dir(state_dir)
    shadow, ledger = osh.ShadowO.load(sd), OptionsBook.load(sd)
    eq = (shadow.account or {}).get("equity")
    ntr = osh.no_trade_rate(shadow.evaluations)
    opt20_ok = [r for r in shadow.book.closed if ((r.get("tags") or {}).get("opt20") or {}).get("blocks_entry")
                is not True]
    out = {
        "feed_note": FEED_NOTE, "enabled": bool(_policy(cfg).get("enabled", False)),
        "shadow": osh.opt38_stats(shadow.book.closed, equity=eq, no_trade=ntr),
        "paper": osh.opt38_stats(ledger.closed, equity=eq, no_trade=ntr),
        "skips": {**osh.opt38_stats(shadow.skips.closed, equity=eq), "log": shadow.skip_log[-20:],
                  "predictions": shadow.predictions[-20:],
                  "note": "informational only (OPT-34; CL-9's code shrink does not apply to O)"},
        "no_trade": {"close": ntr, "1545": osh.no_trade_rate(shadow.evaluations, when="1545")},
        "variants": {"OPT-25": osh.variant_summary(shadow.trackers),
                     "OPT-39": {u: osh.opt38_stats([r for r in shadow.variants.closed if r.get("underlying") == u])
                                for u in osh.VARIANT_UNDERLYINGS},
                     "OPT-20_i": osh.opt38_stats(opt20_ok),
                     "OPT-39_signals": "B/C signal spreads not built (needs the stock books' signals)"},
        "invested_per_trade": {"paper": ledger.invested_per_trade(), "shadow": shadow.book.invested_per_trade()},
        "committed_max_loss": {"paper": ledger.committed_max_loss(), "shadow": shadow.book.committed_max_loss()},
        "delta_notional_OPT11": _delta_notional(shadow.book, sd),
        "halted": {"paper": ledger.halted, "shadow": shadow.book.halted},
        "gates": gate_status(cfg, sd, shadow=shadow, ledger=ledger),
    }
    _write_json(sd / BOOK / REPORT_FILE, out)
    return out


def _latest_snapshot(sd) -> dict | None:
    rows = chain_log.load_index(sd)
    for r in reversed(rows):
        snap = chain_log.load_snapshot(r.get("date"), r.get("when"), sd)
        if snap:
            return snap
    return None


def _delta_notional(ledger: OptionsBook, sd) -> dict:
    """OPT-11 display: O's SPY delta notional (shown next to the rules book's SPY holdings, never netted)."""
    snap = _latest_snapshot(sd)
    qmap = ob._by_symbol(all_quotes(snap))
    spot = spots_of(snap).get("SPY")
    total, missing = 0.0, 0
    for lot in ledger.open_lots():
        g = ob.lot_net_greeks(lot, qmap)
        if g is None or spot is None:
            missing += 1
            continue
        total += g["delta"] * MULTIPLIER * lot.contracts * spot
    return {"SPY_delta_notional": total, "lots_without_greeks": missing,
            "rules_book_SPY_shares": other_books_stock(sd).get("SPY", 0.0)}


def o_owned(state_dir=None) -> dict:
    """What the stock books must never reconcile, value, cancel or trade (non-negotiable 5, owner decision 6):
    O's OCC symbols (open lots and unsettled orders), the stock O owns after an assignment, O's value in the
    shared account (committed MaxLoss + P&L, from the latest logged chain) and O's client-order-id prefix."""
    sd = _dir(state_dir)
    ledger = OptionsBook.load(sd)
    syms = {s for l in ledger.open_lots() for s in (l.short_leg.symbol, l.long_leg.symbol)}
    for rec in _load_paper(sd).get("pending", []):
        syms |= {s for s in rec.get("legs", []) if is_occ(s)}
    snap = _latest_snapshot(sd) if ledger.open_lots() else None
    value = o_value(ledger, all_quotes(snap), spots_of(snap).get("SPY")) if ledger.open_lots() or ledger.closed \
        else 0.0
    prefix = "OPT-"
    try:
        from ..config import load_config

        prefix = str(_policy(load_config()).get("order_prefix", "OPT-"))
    except Exception:  # noqa: BLE001 - the default prefix is the rulebook's
        pass
    return {"symbols": syms, "stock": dict(ledger.o_stock), "value": float(value), "order_prefix": prefix}
