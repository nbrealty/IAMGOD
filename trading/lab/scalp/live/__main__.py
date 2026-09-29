"""Command line for the live paper minute trader. Run from trading/:

    python -m lab.scalp.live check-account            read-only: prove the SCALP account is paper and not RULES
    python -m lab.scalp.live run --mode dry           live data, simulated broker, no orders anywhere
    python -m lab.scalp.live run --mode paper --confirm-paper    real orders on the SCALP paper account
    python -m lab.scalp.live replay --date 2026-09-28 [--recording PATH] [--e0 10000]
    python -m lab.scalp.live kill --reason "why"      KILL flag; flattens itself if no bot is running
    python -m lab.scalp.live reset-halt --reason "why"   clears HALT/KILL, logged in changes.log (MT-G41)
    python -m lab.scalp.live accept-journal-gap --session D [--setup ORB5_QQQ/QQQ] --reason "why"
                                                      a paper journal lost for good (logged in changes.log)
    python -m lab.scalp.live watchdog --mode dry|paper
    python -m lab.scalp.live report [--date D | --since D] [--mode dry|paper|replay] [--remark] [--broker]
    python -m lab.scalp.live hash                     code and risk hashes
    python -m lab.scalp.live state-save [--remote origin]      journals, pins, changes.log -> branch scalp-state
    python -m lab.scalp.live state-restore [--remote origin]   the same files back (a fresh container)

Only the ALPACA_SCALP_* keys are used for trading and data. `check-account` alone also reads the RULES account's
NUMBER (read-only, never printed in full) to prove the two accounts differ. Nothing prints a key.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from . import config as C
from . import journal as J
from . import state as S
from .broker import PAPER_URL, SCALP_KEYS, _norm_url, with_timeout
from .model import NY, Mode


def _now() -> pd.Timestamp:
    return pd.Timestamp.now(tz=NY)


def _date(s: str) -> date:
    return date.fromisoformat(s)


# ------------------------------------------------------------------------------------------ check-account
def _trading_client(key: str, secret: str) -> Any:
    from alpaca.trading.client import TradingClient
    return with_timeout(TradingClient(key, secret, paper=True))


def check_account(env: dict[str, str] | None = None, make_client: Callable[[str, str], Any] = _trading_client,
                  state_dir: str | Path | None = None, out: Callable[[str], None] = print) -> int:
    """Read-only proof that the SCALP keys open a PAPER account that is not the RULES account (MT-G26, MT-G36).
    Prints only the last 4 characters of any account number. Pins the full SCALP number in state/scalp/account.pin
    (gitignored) the first time. Returns 0 when every proof passes, 1 otherwise."""
    env = dict(os.environ if env is None else env)
    k, s = env.get(SCALP_KEYS[0]), env.get(SCALP_KEYS[1])
    if not k or not s:
        out("FAIL: ALPACA_SCALP_KEY and/or ALPACA_SCALP_SECRET are not set in this session. Add both in the "
            "environment settings, then start a NEW session (variables are read when a session starts).")
        return 1
    override = env.get("APCA_API_BASE_URL", "").strip()
    if override and override.rstrip("/") != PAPER_URL:
        out(f"FAIL: APCA_API_BASE_URL points somewhere other than the paper host ({PAPER_URL}). Remove it.")
        return 1
    try:
        client = make_client(k, s)
        # alpaca-py keeps the URL as an enum (str() of it is 'BaseURL.TRADING_PAPER'): read its value
        base = _norm_url(getattr(client, "_base_url", None) or getattr(client, "base_url", None))
        if base != PAPER_URL:
            out(f"FAIL: the client's base URL is not the paper host ({PAPER_URL}); nothing was requested.")
            return 1
        acct = client.get_account()
    except Exception as e:  # noqa: BLE001 - show the kind of failure, never the keys
        out(f"FAIL: could not read the SCALP account ({type(e).__name__}: {str(e)[:200]}). Check that the two "
            f"ALPACA_SCALP_* values are the PAPER key and secret of the new account (Alpaca dashboard, Paper).")
        return 1
    num = str(acct.account_number)
    rules_num, rules_note = None, ""
    rk, rs = env.get("ALPACA_RULES_KEY"), env.get("ALPACA_RULES_SECRET")     # read-only, number only
    if rk and rs:
        try:
            rules_num = str(make_client(rk, rs).get_account().account_number)
        except Exception as e:  # noqa: BLE001
            rules_note = f"could not read the RULES account number ({type(e).__name__})"
    else:
        rules_note = "RULES keys not set here, so the comparison could not be made"
    reg_last4 = C.load_registry().account_last4
    checks = {
        "base URL is the paper host": base == PAPER_URL,
        "account number starts with PA (paper)": num.upper().startswith("PA"),
        "different from the RULES account": rules_num is not None and rules_num != num,
        f"last 4 match the registry ({reg_last4})": num[-4:] == reg_last4,
    }
    pin = S.path(state_dir, S.ACCOUNT_PIN)
    if pin.exists():
        checks["same account as the pinned one"] = pin.read_text().strip() == num
    opt = getattr(acct, "options_trading_level", None) or getattr(acct, "options_approved_level", None)

    def f(x: Any) -> str:
        try:
            return f"${float(x):,.2f}"
        except (TypeError, ValueError):
            return "n/a"

    status = getattr(acct.status, "value", acct.status)
    out(f"SCALP paper account ...{num[-4:]}")
    out(f"  status {status}; equity {f(acct.equity)}; last close equity {f(acct.last_equity)}; cash {f(acct.cash)}")
    out(f"  buying power {f(acct.buying_power)}; non-marginable buying power "
        f"{f(getattr(acct, 'non_marginable_buying_power', None))}; options level {opt if opt is not None else 'n/a'}")
    out(f"  trading blocked: {bool(getattr(acct, 'trading_blocked', False))}; shorting enabled: "
        f"{bool(getattr(acct, 'shorting_enabled', False))}; pattern day trader: "
        f"{bool(getattr(acct, 'pattern_day_trader', False))}")
    out(f"  base URL {base}")
    mf = C.margin_framework(_now().date(), base)                 # Notes 1 Patch G: a record, never a gate
    out(f"  margin framework: {mf['framework']} (source {mf['source']}, checked {mf['checked']}, effective "
        f"{mf['effective']}; {mf['use']})")
    out(f"  RULES account ...{rules_num[-4:] if rules_num else '????'}" + (f" ({rules_note})" if rules_note else ""))
    for name, ok in checks.items():
        out(f"  [{'ok' if ok else 'FAIL'}] {name}")
    try:
        equity = float(acct.equity)
        if equity < 6600:
            out(f"  NOTE: equity {f(equity)} is below about $6,600: the 10%-of-equity size cap gives 0 SPY shares "
                f"(one share is about $650), so every trade would be rejected SIZE_ZERO.")
    except (TypeError, ValueError):
        pass
    if all(checks.values()) and not pin.exists():
        pin.parent.mkdir(parents=True, exist_ok=True)
        pin.write_text(num + "\n")
        out("  pinned this account number in state/scalp/account.pin")
    return 0 if all(checks.values()) else 1


# ------------------------------------------------------------------------------------------ commands
def cmd_check_account(a: argparse.Namespace) -> int:
    return check_account()


def _refused(e: Exception) -> int:
    print(f"Refused: {e}", file=sys.stderr)
    return 1


def cmd_run(a: argparse.Namespace) -> int:
    from . import runner
    from .model import PaperLockError
    try:
        return runner.run(a.mode, confirm_paper=a.confirm_paper, no_watchdog=a.no_watchdog)
    except (PaperLockError, C.RegistryError, RuntimeError, ValueError) as e:
        return _refused(e)


def cmd_replay(a: argparse.Namespace) -> int:
    from . import runner
    from .model import PaperLockError
    try:
        runner.replay(a.date, recording=a.recording, e0=a.e0, events_path=a.events)
    except (PaperLockError, C.RegistryError, RuntimeError, ValueError) as e:
        return _refused(e)
    return 0


def _paper_broker() -> Any:
    from .broker import AlpacaBroker
    return AlpacaBroker(mode=Mode.PAPER)


def _quote_fn() -> Any:
    from . import runner
    data_client, _ = runner.scalp_clients()
    return runner.latest_quote_fn(data_client)


def _aux_journal(name: str, mode: Mode) -> J.FileJournal:
    d = _now().date()
    return J.FileJournal(C.STATE_DIR / "journal" / f"{d.isoformat()}-{mode.value}-{name}.jsonl", mode, _now)


def cmd_kill(a: argparse.Namespace, *, state_dir: Path | None = None, broker_factory: Callable[[], Any] | None = None,
             quote_fn: Any = None, clock: Callable[[], pd.Timestamp] = _now, journal: Any = None,
             out: Callable[[str], None] = print) -> int:
    from . import watchdog
    try:
        res = watchdog.kill_command(a.reason, state_dir or C.STATE_DIR, clock, broker_factory or _paper_broker,
                                    journal or _aux_journal("kill", Mode.PAPER),
                                    quote_fn=quote_fn if broker_factory is not None else _lazy_quote_fn(), out=out)
    except Exception as e:  # noqa: BLE001 - the KILL flag is written first; say plainly what did not work
        if S.read_flag(state_dir or C.STATE_DIR, S.KILL) is None:
            out(f"Refused: {e}")
            return 1
        out(f"KILL flag written, but the account could not be flattened from here: {type(e).__name__}: {e}. "
            f"Close positions in the Alpaca paper dashboard and check the account.")
        return 1
    return 0 if not res.get("acted") or res.get("flat") else 1


def _lazy_quote_fn() -> Any:
    fn: list[Any] = []

    def q(symbol: str) -> Any:
        if not fn:
            try:
                fn.append(_quote_fn())
            except Exception:  # noqa: BLE001 - no data client: exits price off the position instead
                fn.append(lambda s: None)
        return fn[0](symbol)
    return q


def cmd_reset_halt(a: argparse.Namespace, *, state_dir: Path | None = None,
                   clock: Callable[[], pd.Timestamp] = _now, out: Callable[[str], None] = print) -> int:
    cleared = S.reset_halt(state_dir or C.STATE_DIR, a.reason, clock())
    what = [k.upper() for k, v in cleared.items() if v]
    out(f"Cleared {', '.join(what) or 'nothing (no HALT or KILL was set)'}; logged in changes.log with your reason.")
    return 0


def cmd_accept_journal_gap(a: argparse.Namespace, *, state_dir: Path | None = None,
                           clock: Callable[[], pd.Timestamp] = _now, out: Callable[[str], None] = print) -> int:
    """V3-3 exit: the owner accepts that a session's paper journal is lost for good (state-restore cannot bring
    back a journal that was never saved). Logged with the reason in changes.log (MT-G41)."""
    from . import runner
    try:
        runner.accept_journal_gap(state_dir or C.STATE_DIR, a.session, a.reason, clock(), a.setup)
    except ValueError as e:
        out(f"Refused: {e}")
        return 1
    out(f"Accepted the lost paper journal of {a.session} for {a.setup or 'every setup'}; logged in changes.log with "
        "your reason. From the next start that session no longer holds the setup in shadow; its fills stay missing "
        "from the MT-G3 / G13 slippage history. Try `state-restore` first if the journal might still exist.")
    return 0


def cmd_watchdog(a: argparse.Namespace) -> int:
    from . import watchdog
    mode = Mode(a.mode)
    broker = _paper_broker() if mode is Mode.PAPER else None
    qf = _lazy_quote_fn() if mode is Mode.PAPER else None
    wd = watchdog.Watchdog(mode, C.STATE_DIR, _now, _aux_journal("watchdog", mode), broker=broker, quote_fn=qf)
    return watchdog.run_watchdog(wd, parent_pid=a.parent_pid, max_checks=a.max_checks)


def cmd_report(a: argparse.Namespace) -> int:
    from . import report
    qf = tf = None
    if a.remark:
        from . import market, runner
        data_client, _ = runner.scalp_clients()
        qf = market.SipQuoteSource(data_client)
        tf = market.SipTradeSource(data_client)       # MT-G4: resolves PENDING_VERIFY take-profits
    broker = None
    if a.broker:
        from .broker import AlpacaBroker
        broker = AlpacaBroker(mode=Mode.DRY)          # read-only
    report.report(day=a.date, since=a.since, mode=a.mode, quote_fn=qf, broker=broker, trades_fn=tf)
    return 0


def cmd_state_save(a: argparse.Namespace, *, state_dir: Path | None = None, repo: Path | None = None,
                   env: dict[str, str] | None = None, out: Callable[[str], None] = print) -> int:
    from . import statesync
    try:
        statesync.save(state_dir or C.STATE_DIR, repo or C.TRADING_DIR.parent, remote=a.remote, env=env, out=out)
    except (statesync.GitError, ValueError, OSError) as e:
        out(f"state-save failed: {e}")
        return 1
    return 0


def cmd_state_restore(a: argparse.Namespace, *, state_dir: Path | None = None, repo: Path | None = None,
                      env: dict[str, str] | None = None, out: Callable[[str], None] = print) -> int:
    from . import statesync
    try:
        statesync.restore(state_dir or C.STATE_DIR, repo or C.TRADING_DIR.parent, remote=a.remote, env=env, out=out)
    except (statesync.GitError, RuntimeError, ValueError, OSError) as e:
        out(f"state-restore failed: {e}")
        return 1
    return 0


def cmd_hash(a: argparse.Namespace, out: Callable[[str], None] = print) -> int:
    from . import runner
    reg = C.load_registry()
    out(f"risk hash    {C.risk_hash()}  (store it as SCALP_RISK_HASH outside the repo)")
    out(f"package hash {runner.package_hash()}")
    for r in reg.setups:
        cur = r.current_hash()
        out(f"{r.setup_id}/{r.symbol} v{r.version} [{r.lane.value}] registered {r.code_hash[:12]} current {cur[:12]} "
            f"{'ok' if cur == r.code_hash else 'CODE_HASH_MISMATCH (runs shadow-only)'}")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m lab.scalp.live", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check-account").set_defaults(fn=cmd_check_account)
    r = sub.add_parser("run")
    r.add_argument("--mode", choices=["dry", "paper"], required=True)
    r.add_argument("--no-watchdog", action="store_true", help="dry mode only: paper always runs the MT-G39 watchdog")
    r.add_argument("--confirm-paper", action="store_true", help="required for --mode paper")
    r.set_defaults(fn=cmd_run)
    rp = sub.add_parser("replay")
    rp.add_argument("--date", type=_date, required=True)
    rp.add_argument("--recording", type=Path)
    rp.add_argument("--e0", type=float, help="starting equity for sizing (default: the SCALP account's)")
    rp.add_argument("--events", type=Path, help="a verified event calendar covering the date (default: the "
                                                "committed one, which starts on 2026-09-29)")
    rp.set_defaults(fn=cmd_replay)
    k = sub.add_parser("kill")
    k.add_argument("--reason", required=True)
    k.set_defaults(fn=cmd_kill)
    rh = sub.add_parser("reset-halt")
    rh.add_argument("--reason", required=True)
    rh.set_defaults(fn=cmd_reset_halt)
    ag = sub.add_parser("accept-journal-gap", help="the owner accepts a paper session journal as lost for good "
                                                   "(the V3-3 shadow rule's logged exit, MT-G41)")
    ag.add_argument("--session", type=_date, required=True)
    ag.add_argument("--setup", help="SETUP_ID/SYMBOL (default: every setup of that session)")
    ag.add_argument("--reason", required=True)
    ag.set_defaults(fn=cmd_accept_journal_gap)
    w = sub.add_parser("watchdog")
    w.add_argument("--mode", choices=["dry", "paper"], required=True)
    w.add_argument("--parent-pid", type=int)
    w.add_argument("--max-checks", type=int)
    w.set_defaults(fn=cmd_watchdog)
    rep = sub.add_parser("report")
    g = rep.add_mutually_exclusive_group()
    g.add_argument("--date", type=_date)
    g.add_argument("--since", type=_date)
    rep.add_argument("--mode", choices=["dry", "paper", "replay"])
    rep.add_argument("--remark", action="store_true", help="re-mark fills against historical SIP quotes (MT-G4)")
    rep.add_argument("--broker", action="store_true", help="compare with the paper account's order history")
    rep.set_defaults(fn=cmd_report)
    sub.add_parser("hash").set_defaults(fn=cmd_hash)
    for name, fn in (("state-save", cmd_state_save), ("state-restore", cmd_state_restore)):
        ss = sub.add_parser(name, help="copy state/scalp journals, pins and changes.log to / from the scalp-state "
                                       "branch (a separate worktree; never forced)")
        ss.add_argument("--remote", default="origin")
        ss.set_defaults(fn=fn)
    return p


def main(argv: list[str] | None = None) -> int:
    a = parser().parse_args(argv)
    return int(a.fn(a) or 0)


if __name__ == "__main__":
    sys.exit(main())
