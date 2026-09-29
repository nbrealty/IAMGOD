"""The main loop of the live paper minute trader, and the startup checks that must pass first.

Modes (model.Mode):
- DRY: live IEX data (LiveMarket) and a simulated broker (SimBroker, quote fills). E0 and cash are read, read-only,
  from the ALPACA_SCALP paper account. No order goes anywhere; the journal says `would_submit`.
- PAPER: live IEX data and real orders on the ALPACA_SCALP paper account (AlpacaBroker, wrapped in GuardedBroker).
  `__main__` refuses it without --confirm-paper.
- REPLAY: one historical session (ReplayMarket: SIP bars and SIP quotes) or a recording (RecordingMarket), with a
  SimBroker (bar fills for SIP bars, quote fills for recordings), on a simulated clock.

Startup (live modes), in this order; each failure blocks ENTRIES only (exits always work, MT-G38):
1. Context: the SIP history before today (market.build_context, same Ctx as the backtest) and today's calendar.
2. E0 (MT-G40): the account's `last_equity`, stored once per session in state/scalp/session-YYYY-MM-DD.json together
   with the package hash, the session times and the previous close's cash. A restart reuses the stored E0.
3. Deploy guard (MT-G27): a start between 09:00 and 16:15 ET whose package hash differs from the code that ran
   BEFORE the window (today's last start before 09:00, else the previous session's last start) ->
   DEPLOY_IN_MARKET_HOURS. A hash first seen inside the window never becomes that reference, and the block is
   sticky for the day (deploy_block-DATE.json): a restart does not clear it. In PAPER mode a start there with no
   reference at all is blocked too (start before 09:00 or dry-run a day first).
4. Risk hash (MT-G41): env SCALP_RISK_HASH, if set, must equal config.risk_hash(), else RISK_HASH_MISMATCH. If unset,
   the hash is pinned in state/scalp/risk_hash.pin (a later different hash is a mismatch) and RISK_HASH_UNPINNED is
   journalled.
5. Registry hashes (MT-G10): a setup whose code or parameters changed since it was frozen runs shadow-only
   (CODE_HASH_MISMATCH). A setup that decides on volume runs shadow-only when the run's live feed is not SIP
   (MT-G35: the free live feed is IEX). The engine then applies the automatic switch-offs (MT-G3, G12, G13) to each
   setup's history: closed-trade R from the broker (paper) or the journal (dry), fill slippage from the journals.
5b. Whole-test start (paper caps): registry `test_start`, else the earlier of state/scalp/test_start.pin and the
   session of the broker's first SCALP- order (PAPER reads ~400 days of history, read-only, and refuses to start
   without it); only a first PAPER run with no SCALP history pins today (logged in changes.log). So the $150 /
   60-session stop and the 5% drawdown halt see every session since, even in a fresh container. The same history
   rebuilds a lost HALT: a kill (K) or watchdog (W) order after the last reset-halt in changes.log, with no HALT file
   here, writes HALT again.
5c. PAPER, fail closed (MT-G3 / G13): a setup whose SCALP fills at the broker (since its version was registered) are
   in no local paper journal (a fresh container whose state was not restored) runs shadow-only, and the owner is
   told to run `state-restore` (journal_gaps: the client id must be on a decision / submit / fill line of the
   engine's own <date>-paper.jsonl). A journal lost for good is released only by the owner's logged
   `accept-journal-gap` (changes.log, MT-G41). Then the MT-G4 re-mark resolves older PENDING_VERIFY take-profits
   against historical SIP trades (report.resolve_take_profits; best effort, no data = still pending).
6. Pre-open self-test (MT-G27): a SimBroker holding 1 share with a live bracket is killed by a real Engine in
   simulated time; it must be flat with no open orders within 10 simulated seconds, else SELFTEST_FAILED for the day.
7. HALT file present (the paper HALT; a dry run also its own HALT-dry) -> HALTED_MANUAL until `reset-halt`.
8. Restore (MT-G40): counters and any open SCALP position rebuilt from the broker's order history.
Then the watchdog process starts (always in PAPER; `--no-watchdog` is for dry runs only, MT-G39) and the loop runs at
about 1 Hz: market snapshot -> SimBroker update (dry/replay) -> engine.tick -> heartbeat -> recording. It stops a
minute after the close with a short summary. SIGTERM asks the engine to exit every position; if it is not flat after
SIGTERM_GRACE_S the kill switch takes over, and the process ends only when flat or after SIGTERM_HARD_S (with an
alert: the watchdog is then the backstop).
"""
from __future__ import annotations

import dataclasses
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd

from . import config as C
from . import journal as J
from . import market as M
from . import state as S
from .broker import SCALP_KEYS
from .clock import SessionTimes, at
from .events import DayEvents, load_events_or_unknown
from .model import (NY, AccountView, Candidate, DayCounters, Feed, Kind, Lane, Mode, PositionView, Quote, Reason,
                    as_ny)

DEPLOY_WINDOW = ("09:00", "16:15")
SELFTEST_SECONDS = 10
STOP_AFTER_CLOSE = pd.Timedelta(minutes=1)
PREOPEN_START = pd.Timedelta(minutes=2)          # start polling data this long before the open
SIGTERM_GRACE_S = 20                             # then the kill switch takes over the shutdown
SIGTERM_HARD_S = 90                              # the process ends even if not flat (and says so loudly)
PACKAGE_FILES = ("lab/scalp/signals.py", "lab/scalp/backtest.py", "lab/scalp/data.py")


def now_ny() -> pd.Timestamp:
    return pd.Timestamp.now(tz=NY)


# ------------------------------------------------------------------------------------------ hashes and guards
def package_hash() -> str:
    """Hash of everything that decides or sends: every module of this package, its registry and event calendar,
    and the lab modules it reuses (signals, backtest, data)."""
    live = sorted(p.name for p in C.LIVE_DIR.glob("*.py")) + ["registry.json", C.EVENTS_PATH.name]
    files = [f"lab/scalp/live/{n}" for n in live if (C.LIVE_DIR / n).exists()] + list(PACKAGE_FILES)
    return C.code_hash(files, {})


def _ts(x: Any) -> pd.Timestamp | None:
    try:
        return as_ny(pd.Timestamp(x)) if x else None
    except (ValueError, TypeError):
        return None


def deploy_reference(now: pd.Timestamp, session_info: dict | None, baseline_hash: str | None) -> str | None:
    """MT-G27: the code hash a start inside 09:00-16:15 must match. Only code that ran BEFORE the window counts:
    today's last start before 09:00, else the previous session's last start (`baseline_hash`). A hash first seen
    inside the window (a mid-session deploy, or a dry run started there) never becomes the reference."""
    now = as_ny(now)
    a = at(now.date(), DEPLOY_WINDOW[0])
    if not session_info:
        return baseline_hash
    starts = [x for x in session_info.get("starts") or [] if isinstance(x, dict) and x.get("package_hash")]
    timed = [(t, x["package_hash"]) for x in starts if (t := _ts(x.get("ts"))) is not None]
    if timed:
        before = [h for t, h in sorted(timed, key=lambda z: z[0]) if t < a]
        return before[-1] if before else baseline_hash
    first = _ts(session_info.get("first_start"))
    if first is not None and first >= a:
        return baseline_hash                        # the session's first start was already inside the window
    return session_info.get("package_hash") or baseline_hash     # (a session file without start times)


def deploy_reasons(now: pd.Timestamp, session_info: dict | None, pkg_hash: str, *, baseline_hash: str | None = None,
                   require_baseline: bool = False, already_blocked: bool = False) -> list[Reason]:
    """MT-G27: no deploys 09:00-16:15 ET. A start in that window blocks entries for the day when its code differs
    from the code that ran before the window (deploy_reference). With `require_baseline` (paper) a start there
    with no such code at all is blocked too. `already_blocked` (today's deploy_block file) keeps the block for
    the rest of the session: a restart never clears it."""
    now = as_ny(now)
    a, b = at(now.date(), DEPLOY_WINDOW[0]), at(now.date(), DEPLOY_WINDOW[1])
    if not (a <= now < b):
        return []
    if already_blocked:
        return [Reason.DEPLOY_IN_MARKET_HOURS]
    ref = deploy_reference(now, session_info, baseline_hash)
    if ref is None and require_baseline:
        return [Reason.DEPLOY_IN_MARKET_HOURS]
    # the code must equal the reference AND every start already made inside the window today (a change between two
    # starts inside the window is a mid-session deploy even when no reference exists, e.g. a dry run's first day)
    must = {ref} if ref is not None else set()
    for x in (session_info or {}).get("starts") or []:
        t = _ts(x.get("ts")) if isinstance(x, dict) else None
        if t is not None and t >= a and x.get("package_hash"):
            must.add(x["package_hash"])
    return [Reason.DEPLOY_IN_MARKET_HOURS] if any(h != pkg_hash for h in must) else []


def deploy_check(state_dir: str | Path, now: pd.Timestamp, pkg_hash: str, mode: Mode) -> tuple[list[Reason], dict]:
    """The startup deploy guard as run() uses it: today's session file, the previous session's hash and today's
    sticky block. A flagged start writes deploy_block-DATE.json (any mode: the code differs either way), so every
    later start today stays blocked. Returns (reasons, details for the journal)."""
    now = as_ny(now)
    d = now.date()
    prior = S.read_session(state_dir, d)
    baseline = S.last_package_hash(state_dir, d)
    sticky = S.read_deploy_block(state_dir, d)
    reasons = deploy_reasons(now, prior, pkg_hash, baseline_hash=baseline, require_baseline=mode is Mode.PAPER,
                             already_blocked=sticky is not None)
    info = {"package_hash": pkg_hash, "baseline": baseline, "reference": deploy_reference(now, prior, baseline),
            "sticky": sticky}
    if reasons and sticky is None:
        S.write_deploy_block(state_dir, d, {"ts": now.isoformat(), "mode": mode.value, "package_hash": pkg_hash,
                                            "reference": info["reference"], "baseline": baseline})
    return reasons, info


def risk_hash_reasons(state_dir: str | Path | None, env: dict[str, str], journal: Any) -> list[Reason]:
    """MT-G41 startup check of the guardrail code hash (see the module docstring)."""
    current = C.risk_hash()
    want = (env.get("SCALP_RISK_HASH") or "").strip()
    if want:
        if want != current:
            journal.write("risk_hash_mismatch", expected=want, current=current)
            return [Reason.RISK_HASH_MISMATCH]
        return []
    pin = S.path(state_dir, S.RISK_PIN)
    if pin.exists():
        pinned = pin.read_text().strip()
        if pinned != current:
            journal.write("risk_hash_mismatch", expected=pinned, current=current, source=str(pin))
            return [Reason.RISK_HASH_MISMATCH]
    else:
        pin.parent.mkdir(parents=True, exist_ok=True)
        pin.write_text(current + "\n")
    journal.write("RISK_HASH_UNPINNED", current=current,
                  note="SCALP_RISK_HASH is not set: the hash is pinned in state/scalp/risk_hash.pin only. Store it "
                       "outside the repo (environment variable) so a change to the guardrail code is caught.")
    return []


def registry_for_run(registry: C.Registry, journal: Any, feed: str = "SIP") -> tuple[C.Registry, list[str]]:
    """MT-G10: setups whose frozen hash no longer matches run shadow-only. MT-G35: a setup that decides on volume
    runs shadow-only when this run's live feed is not SIP (live runs: IEX; a SIP replay may trade it). Every
    registration of the run carries the feed this run ACTUALLY uses as its `feed_live` (IEX live, SIP for a
    historical replay, SIM for synthetic data), so each journal line's `feed` label is true and FEED_MISMATCH
    shows only when that feed differs from the backtest's. The committed file is not changed. Returns (the
    registry for this run, the setups made shadow-only)."""
    run_feed = str(getattr(feed, "value", feed)).upper()
    bad = {(r.setup_id, r.symbol) for r in registry.hash_mismatches()}
    regs, shadow = [], set(bad)
    for r in registry.setups:
        r = dataclasses.replace(r, feed_live=run_feed)
        if (r.setup_id, r.symbol) in bad:
            journal.write("code_hash_mismatch", reason=Reason.CODE_HASH_MISMATCH, **r.labels(),
                          registered=r.code_hash, current=r.current_hash(), now_lane=Lane.SHADOW)
            r = C.with_lane(r, Lane.SHADOW)
        elif r.uses_volume and str(feed).upper() != "SIP" and r.lane is not Lane.SHADOW:
            journal.write("volume_setup_on_iex", reason="FEED_MISMATCH", **r.labels(), run_feed=str(feed),
                          now_lane=Lane.SHADOW, note="MT-G35: a volume setup stays shadow unless run on SIP")
            r = C.with_lane(r, Lane.SHADOW)
            shadow.add((r.setup_id, r.symbol))
        regs.append(r)
    return C.Registry(tuple(regs), registry.account_last4, registry.test_start, registry.path), \
        sorted(f"{a}/{b}" for a, b in shadow)


def lane_history(registry: C.Registry, adopted: Any, state_dir: str | Path | None, mode: Mode
                 ) -> dict[tuple[str, str], dict[str, Any]]:
    """Each setup version's history for the automatic switch-offs (MT-G3, G12, G13), oldest first, counted from the
    day the version was registered: closed-trade R (PAPER: the broker's SCALP history via restore.py; DRY: the dry
    journals) and fill slippage in bps (the journals of this mode: only they hold the decision mid).
    MT-G4: a take-profit close joins the resolved series "r" once verified (a live bar, `tp_verified`, or the SIP
    re-mark) at its R, or at 0R once the re-mark found it a missed fill (`tp_missed`); until then it is in "pend"
    (key -> gate R, at most 0), which gates.lane_check_pending counts only where that is stricter. Resolutions are
    matched by the entry's client id, or (older lines) by the take-profit's order id inside the same journal file:
    a SimBroker's ids repeat across processes. Paper order ids are the broker's own and unique."""
    from . import report as REP
    out: dict[tuple[str, str], dict[str, Any]] = {}
    if state_dir is None:
        return out
    for reg in registry.setups:
        try:
            since = date.fromisoformat(reg.registered)
        except ValueError:
            since = None
        lines = [x for x in REP.read_lines(REP.journal_files(state_dir, since=since, mode=mode.value))
                 if x.get("setup_id") == reg.setup_id and x.get("symbol") == reg.symbol]
        slip = [v for v in (REP._slip(x, "bps") for x in lines if x.get("kind") == "fill") if v is not None]
        index = REP.TpIndex(lines)
        if mode is Mode.PAPER:
            closes = [{"r": t.r, "gate_r": t.gate_r, "pending_verify": t.pending_verify, "parent_cid": t.parent_cid,
                       "tp_order_id": t.tp_order_id}
                      for t in sorted(getattr(adopted, "trades", None) or [], key=lambda t: t.closed)
                      if t.setup_id == reg.setup_id and t.symbol == reg.symbol and t.r is not None
                      and (since is None or t.closed.date() >= since)]
            ser = REP.r_series(closes, index, unique_ids=True)
        else:
            closes = [x for x in lines if x.get("kind") == "trade_closed"]
            ser = REP.r_series(closes, index)
        out[(reg.setup_id, reg.symbol)] = {"r": ser["r"], "slip": slip, "pend": ser["pend"],
                                           "pending_verify": ser["pending"], "missed": ser["missed"]}
    return out


TEST_LOOKBACK_DAYS = 400          # the broker history read to find the test's first SCALP order (a 60-session test)


COVER_KINDS = ("decision", "submit", "submit_uncertain", "fill")   # engine lines that name an entry's client id
GAP_ACCEPT = "accept-journal-gap"                                  # changes.log action (MT-G41)


def journal_cids(path: str | Path) -> set[str]:
    """The client ids the engine's own session journal records for orders it decided on, sent or saw fill: the
    accepted `decision` (its order, written BEFORE the submit), `submit` / `submit_uncertain` and `fill` lines. Only
    these structured fields count: a re-mark line (`tp_remark`, `tp_verified`, ...) names the same client id but is
    built from the broker's history, so it proves nothing about the local record. An unreadable line is skipped."""
    out: set[str] = set()
    p = Path(path)
    if not p.exists():
        return out
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            x = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(x, dict) or x.get("kind") not in COVER_KINDS:
            continue
        cid = (x.get("order") or {}).get("client_order_id") if x["kind"] == "decision" and \
            isinstance(x.get("order"), dict) else x.get("cid")
        if isinstance(cid, str) and cid:
            out.add(cid)
    return out


def accepted_gaps(state_dir: str | Path) -> dict[date, set[str | None]]:
    """{session: {"SETUP/SYM", ... or None = every setup}} the owner accepted as lost for good with
    `accept-journal-gap` (changes.log, MT-G41)."""
    out: dict[date, set[str | None]] = {}
    for x in S.read_changes(state_dir):
        if x.get("action") != GAP_ACCEPT:
            continue
        try:
            d = date.fromisoformat(str(x.get("session")))
        except ValueError:
            continue
        out.setdefault(d, set()).add(x.get("setup") or None)
    return out


def accept_journal_gap(state_dir: str | Path, session: date, reason: str, now: pd.Timestamp,
                       setup: str | None = None) -> None:
    """The owner's logged exit from the V3-3 shadow rule when a session's paper journal is lost for good (the
    container went before `state-save`): from the next start that session no longer holds the setup(s) in shadow.
    The fills of that session stay missing from the MT-G3 / G13 slippage history (it counts the covered sessions
    only). Written to changes.log with the reason (MT-G41); `state-restore` is always the first thing to try.
    Refused: a setup that is not exactly a registered SETUP_ID/SYMBOL (a typo would release nothing while the log
    said it did), and a session on or after today's (a loss cannot be accepted before it happened)."""
    if setup is not None:
        keys = {f"{r.setup_id}/{r.symbol}" for r in C.load_registry().setups}
        if setup.strip() not in keys:
            raise ValueError(f"--setup must be one of {', '.join(sorted(keys))} (SETUP_ID/SYMBOL, exact)")
        setup = setup.strip()
    if session >= as_ny(now).date():
        raise ValueError(f"session {session} is not in the past: only a journal already lost can be accepted")
    S.append_change(state_dir, now, GAP_ACCEPT, reason, session=session.isoformat(), setup=setup,
                    note="MT-G3 / G13: this session's paper journal is accepted as lost; its fills are missing from "
                         "the slippage history")


def journal_gaps(history: Iterable[Any], state_dir: str | Path, registry: C.Registry,
                 accepted: dict[str, list[date]] | None = None) -> dict[str, list[date]]:
    """PAPER, fail closed (MT-G3 / G13): {"SETUP/SYM": [session dates]} where the broker shows a SCALP entry that
    filled, on or after the version's registration, whose client id is in no `decision` / `submit` / `fill` line of
    the engine's own paper journal of that session (journal/<date>-paper.jsonl; never the -remark / -kill /
    -watchdog files, which are written from the broker's history). The engine journals every accepted decision
    (with the order and its client id) BEFORE it submits, so a covered session always has it; a fresh container
    whose state was not restored has none. A session the owner accepted as lost (`accept-journal-gap`, changes.log)
    is left out and, when `accepted` is given, listed there instead."""
    from . import orders as O
    cids: dict[date, set[str]] = {}
    ok = accepted_gaps(state_dir)
    gaps: dict[str, set[date]] = {}
    acc: dict[str, set[date]] = {}
    for o in history:
        p = O.parse_client_id(getattr(o, "client_order_id", ""))
        if p is None or p["leg"] != "E" or not (getattr(o, "filled_qty", 0) or 0) > 0 or not p["setup_id"]:
            continue
        reg = registry.get(p["setup_id"], o.symbol)
        if reg is None:
            continue
        try:
            if p["session_date"] < date.fromisoformat(reg.registered):
                continue
        except ValueError:
            pass
        d = p["session_date"]
        if d not in cids:
            cids[d] = journal_cids(J.journal_path(state_dir, d, Mode.PAPER))
        if o.client_order_id in cids[d]:
            continue
        key = f"{reg.setup_id}/{reg.symbol}"
        if None in ok.get(d, ()) or key in ok.get(d, ()):
            acc.setdefault(key, set()).add(d)
        else:
            gaps.setdefault(key, set()).add(d)
    if accepted is not None:
        accepted.update({k: sorted(v) for k, v in acc.items()})
    return {k: sorted(v) for k, v in gaps.items()}


def shadow_for_gaps(registry: C.Registry, gaps: dict[str, list[date]], journal: Any) -> C.Registry:
    """The setups `journal_gaps` found run SHADOW-only for this run (the committed registry is not changed)."""
    for r in registry.setups:
        key = f"{r.setup_id}/{r.symbol}"
        if key in gaps and r.lane not in (Lane.SHADOW, Lane.RETIRED):
            journal.write("state_not_restored", **r.labels(), sessions=gaps[key], now_lane=Lane.SHADOW,
                          note="MT-G3 / G13: the broker shows SCALP fills no local journal covers, so the slippage "
                               "history is incomplete: shadow-only until `state-restore` brings the journals back "
                               "(or, if a journal is lost for good, the owner runs `accept-journal-gap`)")
            registry = C.with_registration(registry, C.with_lane(r, Lane.SHADOW))
    return registry


def broker_history(broker: Any, now: pd.Timestamp, days: int = TEST_LOOKBACK_DAYS) -> list[Any]:
    """Every order of the last `days` days, read-only (for the test start and the halt check). Raises on failure:
    PAPER must not start without it (fail closed)."""
    return list(broker.orders_since(as_ny(now).normalize() - pd.Timedelta(days=days)))


def first_scalp_session(history: Iterable[Any]) -> date | None:
    """The session date of the earliest SCALP- order in the broker's history (None when there is none)."""
    from . import orders as O
    days = [p["session_date"] for o in history if (p := O.parse_client_id(getattr(o, "client_order_id", "")))]
    return min(days) if days else None


def resolve_test_start(registry: C.Registry, state_dir: str | Path, mode: Mode, now: pd.Timestamp,
                       history: Iterable[Any] | None = None) -> date | None:
    """The whole test's first session: the registry's, else the earlier of the pin and the broker's first SCALP
    order (`history`, read-only). The state folder is not trusted alone: a fresh container or a wiped folder must
    never restart the $150 / 60-session count or the drawdown high-water mark. The first PAPER run with no SCALP
    history at all pins today (logged). A PAPER run needs the history (fail closed)."""
    if registry.test_start is not None:
        return registry.test_start
    if mode is Mode.PAPER and history is None:
        raise RuntimeError("PAPER needs the broker's order history to find the whole test's first session")
    pinned = S.read_test_start(state_dir)
    first = first_scalp_session(history) if history is not None else None
    if first is not None and (pinned is None or first < pinned):
        if mode is not Mode.PAPER:
            return first                                 # a dry run reads, it pins nothing
        return S.move_test_start_earlier(state_dir, first, now,
                                         "whole-test start rebuilt from the broker's history: the first SCALP order "
                                         f"is from {first} (the state folder had {pinned or 'no pin'})")
    if pinned is None and mode is Mode.PAPER:
        pinned = S.pin_test_start(state_dir, as_ny(now).date(), now,
                                  "first paper session of the minute-trading test (whole-test stop $150 / 60 "
                                  "sessions and the 5% drawdown halt count from here)")
    return pinned


def broker_halt_reason(history: Iterable[Any], state_dir: str | Path, now: pd.Timestamp) -> str | None:
    """MT-G27 / G40: every kill-switch (leg K) and watchdog (leg W) order set HALT, and only a person clears it
    (`reset-halt`, logged in changes.log). When the broker shows such an order after the last reset in changes.log
    but no HALT file exists here (a new container, a wiped folder), the halt is rebuilt. Returns why, or None."""
    from . import orders as O
    if S.halted(state_dir):
        return None
    resets = [t for x in S.read_changes(state_dir) if x.get("action") == "reset-halt" and (t := _ts(x.get("ts")))]
    last_reset = max(resets) if resets else None
    hits = []
    for o in history:
        p = O.parse_client_id(getattr(o, "client_order_id", ""))
        t = _ts(getattr(o, "submitted_at", None))
        if p and p["leg"] in ("K", "W") and t is not None and (last_reset is None or t > last_reset):
            hits.append((t, o.client_order_id))
    if not hits:
        return None
    t, cid = max(hits)
    return (f"the broker shows kill/watchdog order {cid} at {t:%Y-%m-%d %H:%M} and no reset-halt after it in this "
            f"state folder: HALT rebuilt. Check the account, then run `reset-halt --reason ...`")


def session_info(state_dir: str | Path | None, session_date: date, st: SessionTimes, pkg_hash: str,
                 now: pd.Timestamp, mode: Mode, account_fn: Callable[[], AccountView]) -> tuple[dict, bool]:
    """(the session file, created now?). E0 = the account's last_equity, read once per session (MT-G40)."""
    info = S.read_session(state_dir, session_date)
    if info and info.get("e0"):
        info.setdefault("starts", []).append({"ts": as_ny(now).isoformat(), "mode": mode.value,
                                              "package_hash": pkg_hash})
        S.write_session(state_dir, session_date, info)
        return info, False
    acct = account_fn()
    if not acct.last_equity or acct.last_equity <= 0:
        raise RuntimeError("the account reports no last_equity: cannot fix E0 for the session")
    info = {"date": session_date.isoformat(), "e0": float(acct.last_equity), "e0_source": "account.last_equity",
            "cash_prev_close": float(acct.cash), "account_last4": acct.account_number[-4:],
            "package_hash": pkg_hash, "first_start": as_ny(now).isoformat(), "mode": mode.value,
            "open": st.open.isoformat(), "close": st.close.isoformat(), "half_day": st.half_day,
            "starts": [{"ts": as_ny(now).isoformat(), "mode": mode.value, "package_hash": pkg_hash}]}
    S.write_session(state_dir, session_date, info)
    return info, True


def week_e0(state_dir: str | Path | None, session_date: date, e0: float) -> float:
    """MT-G18 weekly stop base: E0 of this week's first session with a session file (Monday's when it ran), else
    today's E0."""
    monday = session_date - timedelta(days=session_date.weekday())
    for k in range((session_date - monday).days + 1):
        info = S.read_session(state_dir, monday + timedelta(days=k)) or {}
        if info.get("e0"):
            return float(info["e0"])
    return float(e0)


# ------------------------------------------------------------------------------------------ engine plumbing
def make_engine(broker: Any, journal: Any, registry: C.Registry, counters: DayCounters, session: SessionTimes,
                events: DayEvents, ctx_by_symbol: dict, mode: Mode, clock: Callable[[], pd.Timestamp], *,
                state_dir: str | Path | None = None, adopted: Any = None, flags: Iterable[Reason] = (),
                engine_cls: Any = None, history: dict | None = None) -> Any:
    """engine.Engine with the state directory (KILL / HALT / daily-stop files), the restored state (restore.py) and
    the startup flags. `broker` may be raw: the engine wraps it in guard.GuardedBroker itself. Refuses (raises) if
    a startup flag did not reach the engine: a failed check must never be dropped silently."""
    if engine_cls is None:
        from .engine import Engine as engine_cls   # noqa: N813
    flags = {Reason(f) for f in flags}
    kw = {"history": history} if history else {}
    eng = engine_cls(broker, journal, registry, counters, session, events, ctx_by_symbol, mode, clock,
                     state_dir=state_dir, adopted=adopted, flags=set(flags), **kw)
    if not flags <= set(getattr(eng, "flags", None) or ()):
        raise RuntimeError("the engine did not take the startup flags; refusing to run with failed checks")
    return eng


def engine_status(engine: Any) -> dict[str, Any]:
    try:
        st = engine.status()
    except Exception as e:  # noqa: BLE001 - the heartbeat must still go out
        return {"error": f"{type(e).__name__}: {e}"}
    return J.plain(st) if isinstance(st, dict) else {"status": J.plain(st)}


def _flat(status: dict) -> bool:
    return not status.get("position") and not status.get("positions") and not status.get("open_orders")


# ------------------------------------------------------------------------------------------ self-test (MT-G27)
def self_test(now: pd.Timestamp, registry: C.Registry, state_dir: str | Path, *, engine_cls: Any = None,
              sim_broker_cls: Any = None, journal: Any = None) -> tuple[bool, str]:
    """Kill a simulated 1-share SPY position with a live bracket through the real Engine, in simulated time.
    Passes when the SimBroker is flat with no open orders within SELFTEST_SECONDS. Uses a scratch state directory
    so the test's HALT never touches the real one. Returns (passed, detail)."""
    from . import orders as O
    if sim_broker_cls is None:
        from .broker import SimBroker as sim_broker_cls   # noqa: N813
    clock = M.SimClock(now)
    j = journal if journal is not None else J.MemoryJournal(Mode.DRY, clock)
    reg = next((r for r in registry.setups if r.symbol == "SPY" and r.overlay_stop_pct is not None), None)
    if reg is None:
        return False, "no SPY setup with an overlay bracket to build the test position"
    reg = dataclasses.replace(C.with_lane(reg, Lane.EXPLORATORY), feed_live=Feed.SIM.value)   # synthetic quotes
    e0 = 1_000_000.0
    d = as_ny(now).date()

    def quote(t: pd.Timestamp) -> Quote:
        return Quote("SPY", 500.00, 500.01, 100.0, 100.0, t, t, Feed.SIM)

    acct = AccountView("PA-SELFTEST", "ACTIVE", e0, e0, e0, e0, e0, False, False, "sim://selftest")
    broker = sim_broker_cls(clock, account=acct, positions=(), fill_mode="quote")
    cand = Candidate(reg.setup_id, reg.version, "SPY", "enter", 1, as_ny(now).floor("min"), reason="self-test")
    spec, why, _ = O.entry_bracket(cand, reg, quote(clock()), e0, d, 0)
    if spec is None:
        return False, f"could not build the test bracket: {[r.value for r in why]}"
    try:
        broker.submit(spec)
        broker.update(clock.advance(1), {"SPY": quote(clock())}, {})
        if not any(p.qty > 0 for p in broker.positions()) or not broker.open_orders():
            return False, "the simulated bracket did not fill with live legs"
        scratch = Path(state_dir) / "selftest"          # the test's own HALT lands here, never in state/scalp
        shutil.rmtree(scratch, ignore_errors=True)
        st = SessionTimes.from_calendar(d, at(d, "09:30"), at(d, "16:00"))
        counters = DayCounters(session_date=d, e0=e0, cash_prev_close=e0)
        eng = make_engine(broker, j, C.Registry((reg,), registry.account_last4, None, registry.path), counters, st,
                          DayEvents(known=True), {}, Mode.DRY, clock, state_dir=scratch, engine_cls=engine_cls)
        eng.request_kill("SELFTEST")
        from .model import MarketSnapshot
        for _ in range(SELFTEST_SECONDS):
            t = clock.advance(1)
            q = {"SPY": quote(t)}
            broker.update(t, q, {})
            eng.tick(MarketSnapshot(now=t, quotes=q, trades={}, new_bars={}, last_data_ok=t, clock_offset_ms=0.0,
                                    halted={"SPY": False}))
            broker.update(t, q, {})
            if not any(p.qty != 0 for p in broker.positions()) and not broker.open_orders():
                return True, f"flat after {(t - as_ny(now)).total_seconds() - 1:.0f} simulated s"
        return False, "not flat with no open orders within 10 simulated seconds"
    except Exception as e:  # noqa: BLE001 - any crash in the kill path fails the day's self-test
        return False, f"{type(e).__name__}: {e}"


# ------------------------------------------------------------------------------------------ the loop
@dataclass
class Runner:
    """One trading session's loop. `sim_broker` (dry/replay) is advanced before every engine tick."""
    engine: Any
    market: Any
    journal: Any
    mode: Mode
    clock: Callable[[], pd.Timestamp]
    state_dir: str | Path | None
    session: SessionTimes
    sim_broker: Any = None
    recorder: Any = None                 # LiveMarket records itself; set this for markets that do not
    sleep: Callable[[float], None] = time.sleep
    live: bool = True                    # pace the loop at 1 Hz on the wall clock
    heartbeat: bool = True
    decisions: list[Any] = field(default_factory=list)
    ticks: int = 0
    stop_reason: str | None = None
    _stop_at: pd.Timestamp | None = None
    _hard_stop_at: pd.Timestamp | None = None
    _escalated: bool = False

    def request_stop(self, why: str) -> None:
        """SIGTERM path: ask the engine to exit everything and keep ticking until flat. Not flat after
        SIGTERM_GRACE_S -> the kill switch; still not flat after SIGTERM_HARD_S -> stop anyway, with an alert."""
        if self.stop_reason is not None:
            return
        self.stop_reason = why
        t0 = as_ny(self.clock())
        self._stop_at = t0 + pd.Timedelta(seconds=SIGTERM_GRACE_S)
        self._hard_stop_at = t0 + pd.Timedelta(seconds=SIGTERM_HARD_S)
        flat = _flat(engine_status(self.engine))
        self.journal.write("stop_requested", reason=why, flat=flat)
        if flat:
            return                          # nothing open: just stop (no kill, no HALT)
        self.engine.request_flatten(why)    # no new entries; the position leaves through the normal exit path

    def step(self) -> Any:
        snap = self.market.poll()
        if snap is None:
            return None
        if self.sim_broker is not None:
            self.sim_broker.update(snap.now, snap.quotes, snap.new_bars)
        out = self.engine.tick(snap) or []
        self.decisions.extend(out)
        self.ticks += 1
        if self.heartbeat:
            S.write_heartbeat(self.state_dir, snap.now, self.mode.value, engine_status(self.engine))
        if self.recorder is not None:
            self.recorder.snapshot(snap)
        return snap

    def loop(self, max_ticks: int | None = None) -> dict[str, Any]:
        end = self.session.close + STOP_AFTER_CLOSE
        while max_ticks is None or self.ticks < max_ticks:
            t0 = time.monotonic()
            snap = self.step()
            if snap is None:
                break
            now = as_ny(snap.now)
            if now >= end:
                break
            if self.stop_reason is not None:
                status = engine_status(self.engine)
                if _flat(status):
                    break
                if now >= self._hard_stop_at:
                    msg = (f"stopping NOT flat {SIGTERM_HARD_S} s after {self.stop_reason}: the watchdog must flatten; "
                           "check the Alpaca paper dashboard")
                    self.journal.write("stop_not_flat", reason=self.stop_reason, status=status)
                    if self.mode is not Mode.REPLAY:
                        S.alert(self.state_dir, now, msg)
                    break
                if now >= self._stop_at and not self._escalated:
                    self._escalated = True       # the normal exit path did not make it: the kill switch takes over
                    fn = getattr(self.engine, "request_kill", None)
                    if callable(fn):
                        fn(f"SHUTDOWN: not flat {SIGTERM_GRACE_S} s after {self.stop_reason}")
            if self.live:
                self.sleep(max(0.0, 1.0 - (time.monotonic() - t0)))
        return {"ticks": self.ticks, "decisions": len(self.decisions), "stop": self.stop_reason}


# ------------------------------------------------------------------------------------------ summaries
def summarize(lines: list[dict], mode: str = "") -> str:
    """Plain-English end-of-day summary from the engine's journal lines: what it saw, what it would have done (or
    did) and why every other signal was refused."""
    from . import report as REP
    dec = [x for x in lines if x.get("kind") == "decision"]
    acc = [x for x in dec if x.get("accepted")]
    rej = [x for x in dec if not x.get("accepted")]
    reasons = Counter(r for x in rej for r in (x.get("reasons") or []))
    trades = REP._trades(lines)
    out = [f"Summary ({mode or 'all modes'}): {len(dec)} signals, {len(acc)} accepted, {len(rej)} refused. "
           f"EXPLORATORY lane: 1 share, never proof of an edge."]
    for x in rej:
        out.append(f"  refused {x.get('setup_id')} {x.get('symbol')} "
                   f"{'buy' if x.get('side', 1) > 0 else 'short'} at {str(x.get('ts', ''))[11:19]}: "
                   f"{', '.join(x.get('reasons') or []) or 'no reason given'}")
    if reasons:
        out.append("Refusals by reason: " + ", ".join(f"{k} x{v}" for k, v in reasons.most_common()))
    out += REP.would_block(lines)
    if trades:
        paper = sum(REP._f(t.get("paper_pnl")) or 0.0 for t in trades)
        honest = sum(REP._f(t.get("honest_pnl")) or 0.0 for t in trades)
        out.append(f"Closed trades: {len(trades)}; paper P&L ${paper:,.2f}; honest P&L ${honest:,.2f}")
        for t in trades:
            out.append(f"  {t.get('setup_id')} {t.get('symbol')} {REP._f(t.get('qty')) or 0:g} sh: in "
                       f"{str(t.get('entry_ts'))[11:19]} out {str(t.get('exit_ts'))[11:19]} ({t.get('exit_reason')}), honest "
                       f"${REP._f(t.get('honest_pnl')) or 0.0:,.2f}")
    else:
        out.append("Closed trades: none")
    kills = [x for x in lines if x.get("kind") in ("kill_start", "daily_stop", "reconcile_halt")]
    for x in kills:
        out.append(f"  {x.get('kind')} at {str(x.get('ts', ''))[11:19]}: {x.get('reason') or ''}")
    return "\n".join(out)


# ------------------------------------------------------------------------------------------ clients and brokers
def scalp_clients(env: dict[str, str] | None = None) -> tuple[Any, Any]:
    """(market-data client, paper trading client) from the ALPACA_SCALP_* keys ONLY (read-only use here)."""
    env = os.environ if env is None else env
    k, s = env.get(SCALP_KEYS[0]), env.get(SCALP_KEYS[1])
    if not k or not s:
        raise RuntimeError("ALPACA_SCALP_KEY / ALPACA_SCALP_SECRET are not set: add them to the environment "
                           "settings and start a new session")
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.trading.client import TradingClient

    from .broker import with_timeout
    return with_timeout(StockHistoricalDataClient(k, s)), with_timeout(TradingClient(k, s, paper=True))


def latest_quote_fn(data_client: Any) -> Callable[[str], Quote | None]:
    """symbol -> latest IEX quote (for the watchdog and the kill command), None on any failure."""
    def fn(symbol: str) -> Quote | None:
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockLatestQuoteRequest
        try:
            q = data_client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=[symbol],
                                                                           feed=DataFeed.IEX))[symbol]
        except Exception:  # noqa: BLE001
            return None
        t = now_ny()
        return Quote(symbol, float(q.bid_price or 0), float(q.ask_price or 0), float(q.bid_size or 0),
                     float(q.ask_size or 0), as_ny(pd.Timestamp(q.timestamp)), t, Feed.IEX)
    return fn


def _restore(broker: Any, session_date: date, e0: float, cash_prev_close: float | None, registry: C.Registry,
             now: pd.Timestamp, test_start: date | None = None) -> tuple[DayCounters, Any]:
    from . import restore
    week_start = session_date - timedelta(days=session_date.weekday())      # Monday of this week
    return restore.rebuild(broker, session_date, e0, cash_prev_close, week_start,
                           test_start if test_start is not None else registry.test_start, registry, now)


# ------------------------------------------------------------------------------------------ run (dry / paper)
def run(mode: Mode | str, *, confirm_paper: bool = False, no_watchdog: bool = False,
        state_dir: str | Path | None = None, env: dict[str, str] | None = None,
        out: Callable[[str], None] = print) -> int:
    """`python -m lab.scalp.live run --mode dry|paper`. Returns a process exit code."""
    mode = Mode(mode)
    if mode is Mode.REPLAY:
        raise ValueError("use replay() for REPLAY mode")
    if mode is Mode.PAPER and not confirm_paper:
        out("Refused: `run --mode paper` sends real orders to the SCALP paper account. Add --confirm-paper once the "
            "owner has said yes.")
        return 2
    if mode is Mode.PAPER and no_watchdog:
        out("Refused: a paper run always starts the outside watchdog (MT-G39: if the bot dies, something else "
            "flattens it). --no-watchdog is for dry runs only.")
        return 2
    env = dict(os.environ if env is None else env)
    state_dir = Path(state_dir or C.STATE_DIR)
    clock = now_ny
    now = clock()
    d = now.date()
    data_client, trading_client = scalp_clients(env)
    from .broker import AlpacaBroker, SimBroker
    pins = {"lock_path": state_dir / S.LOCK, "pin_path": state_dir / S.ACCOUNT_PIN}
    reader = AlpacaBroker(mode=Mode.DRY, **pins)              # read-only SCALP instance (E0, cash, restore in dry)
    registry = C.load_registry()
    journal = J.FileJournal(J.journal_path(state_dir, d, mode), mode, clock)
    journal.write("start", pid=os.getpid(), package_hash=package_hash(), risk_hash=C.risk_hash())

    ctx_by_symbol, row = {}, None
    for sym in registry.symbols():
        ctx, row, _ = M.build_context(sym, d, M.dt.CACHE_DIR, data_client, trading_client, log=lambda s: None)
        ctx_by_symbol[sym] = ctx
    st = SessionTimes.from_calendar(d, row.open, row.close)
    pkg = package_hash()
    dep, dep_info = deploy_check(state_dir, now, pkg, mode)
    flags: set[Reason] = set(dep)
    if Reason.DEPLOY_IN_MARKET_HOURS in flags:
        journal.write("deploy_in_market_hours", **dep_info,
                      note="MT-G27: code started 09:00-16:15 ET that differs from (or has no) code that ran before "
                           "09:00, or an earlier start today was already blocked: no entries today")
    info, _ = session_info(state_dir, d, st, pkg, now, mode, reader.account)
    e0, cash_prev = float(info["e0"]), info.get("cash_prev_close")
    flags |= set(risk_hash_reasons(state_dir, env, journal))
    registry, mism = registry_for_run(registry, journal, feed="IEX")     # live runs see the IEX feed (MT-G35)
    # PAPER: the broker's own history (read-only) decides the whole-test start and rebuilds a lost HALT; the local
    # state folder alone is not trusted (it is gone in a fresh container)
    history = broker_history(reader, now) if mode is Mode.PAPER else None
    orders_hist = history
    if history is not None:
        why_halt = broker_halt_reason(history, state_dir, now)
        if why_halt:
            S.write_flag(state_dir, S.HALT, why_halt, now, "startup (broker history)")
            journal.write("halt_rebuilt", reason=why_halt)
            S.alert(state_dir, now, why_halt)
    test_start = resolve_test_start(registry, state_dir, mode, now, history)
    if mode is Mode.PAPER and test_start is None:
        raise RuntimeError("no whole-test start date: the $150 / 60-session stop cannot be counted")
    registry = C.Registry(registry.setups, registry.account_last4, test_start, registry.path)
    restore_hint = None
    if orders_hist is not None:
        # MT-G3 / G13: the slippage history lives only in the local journals. SCALP fills the broker shows but no
        # local journal covers (a fresh container, state not restored) would restart it from zero: fail closed
        accepted: dict[str, list[date]] = {}
        gaps = journal_gaps(orders_hist, state_dir, registry, accepted)
        for k, v in sorted(accepted.items()):
            journal.write("journal_gap_accepted", setup=k, sessions=v,
                          note="accepted as lost by the owner (changes.log): those fills are missing from the "
                               "MT-G3 / G13 slippage history")
        registry = shadow_for_gaps(registry, gaps, journal)
        if gaps:
            restore_hint = (f"STATE NOT RESTORED: the broker shows SCALP fills that no local journal covers "
                            f"({'; '.join(f'{k}: {len(v)} session(s)' for k, v in sorted(gaps.items()))}). Those "
                            "setups run SHADOW-only today (their MT-G3 / G13 slippage history is incomplete). Run "
                            "`python -m lab.scalp.live state-restore`, then restart. Only if a session's journal is "
                            "lost for good: `python -m lab.scalp.live accept-journal-gap --session D --reason ...`.")
            S.alert(state_dir, now, restore_hint)
    # MT-G4: resolve older PENDING_VERIFY take-profits against historical SIP trades before the switch-offs read the
    # series (in paper also those only the broker's history still has). Best effort: no data = still pending.
    from . import report as REP
    try:
        for x in REP.resolve_take_profits(state_dir, mode.value, M.SipTradeSource(data_client), now, orders_hist):
            journal.write("tp_remark", line=x)
    except Exception as e:  # noqa: BLE001 - a failed re-mark leaves them pending (the stricter view)
        journal.write("tp_remark_failed", error=f"{type(e).__name__}: {str(e)[:200]}")
    for r in registry.setups:
        if r.backtest_mean_r is None:
            journal.write("mt_g13_cusum_off", **r.labels(), note="no backtest baseline in R is registered: the MT-G13 "
                          "CUSUM and win-rate triggers are OFF; the slippage triggers and MT-G12 still run")
    ok, detail = self_test(now, registry, state_dir)
    journal.write("self_test", passed=ok, detail=detail)
    if not ok:
        flags.add(Reason.SELFTEST_FAILED)
    if S.halted(state_dir, mode):
        flags.add(Reason.HALTED_MANUAL)
    events = load_events_or_unknown().day(d)
    if not events.known:
        journal.write("event_calendar_unknown", date=d, note="no entries today (EVENT_CALENDAR_UNKNOWN)")

    acct = reader.account()
    if mode is Mode.PAPER:
        broker = AlpacaBroker(mode=Mode.PAPER, **pins)
        acct = broker.account()                        # proves the paper account (and pin) before any order
        sim = None
    else:
        broker = SimBroker(clock, account=acct, positions=(), fill_mode="quote")
        sim = broker
    counters, adopted = _restore(broker, d, e0, cash_prev, registry, now, test_start)
    counters.week_e0 = week_e0(state_dir, d, e0)
    dry_note = None
    if mode is Mode.DRY:
        # the simulated broker starts empty: today's dry counters come back from today's dry journal (MT-G40)
        from . import restore
        dry_note = restore.from_journal(J.read_journal(J.journal_path(state_dir, d, mode)), counters)
        if dry_note:
            journal.write("dry_restart", note=dry_note)
    history = lane_history(registry, adopted, state_dir, mode)
    for (sid, sym), h in history.items():
        if h.get("pending_verify"):
            journal.write("lane_history_pending_verify", setup_id=sid, symbol=sym, left_out=h["pending_verify"],
                          note="MT-G4: unverified take-profit closes are left out of the resolved MT-G12 / G13 R "
                               "series and counted at their gate value (at most 0R) where that is stricter, until "
                               "the SIP re-mark resolves them")
    # the engine wraps the broker in guard.GuardedBroker (MT-G25) and seeds it with the restored counts (MT-G40)
    engine = make_engine(broker, journal, registry, counters, st, events, ctx_by_symbol, mode, clock,
                         state_dir=state_dir, adopted=adopted, flags=flags, history=history)
    journal.write("startup", flags=sorted(f.value for f in flags), e0=e0, shadow_only=mism,
                  session_open=st.open, session_close=st.close, account_last4=acct.account_number[-4:],
                  test_start=test_start, test_sessions=counters.test_sessions, test_honest=counters.test_honest,
                  day_trades_5_sessions=counters.day_trades_5d,
                  lanes={f"{r.setup_id}/{r.symbol}": r.lane.value for r in engine.registry.setups},
                  margin_framework=C.margin_framework(d, acct.base_url))    # Notes 1 Patch G: record only
    shadow_now = [r.setup_id for r in engine.registry.setups if r.lane in (Lane.SHADOW, Lane.RETIRED)]
    out(f"{mode.value.upper()} run for {d}: E0 ${e0:,.2f}; entry blocks at start: "
        f"{', '.join(sorted(f.value for f in flags)) or 'none'}; self-test: {'passed' if ok else 'FAILED'} "
        f"({detail}); shadow-only: {', '.join(shadow_now) or 'none'}." + (f" {dry_note}" if dry_note else ""))
    if restore_hint:
        out(restore_hint)

    wd_proc = None
    if not no_watchdog:
        wd_proc = start_watchdog(mode, state_dir)
    recorder = M.Recorder(M.recording_path(state_dir, d, mode.value))
    market = M.LiveMarket(data_client, registry.symbols(), clock, trading_client=trading_client, recorder=recorder,
                          journal=journal, session_open=st.open, session_close=st.close)
    runner = Runner(engine, market, journal, mode, clock, state_dir, st, sim_broker=sim, sleep=time.sleep)
    prev_handler = signal.signal(signal.SIGTERM, lambda *_: runner.request_stop("SIGTERM"))
    why = "session over"
    try:
        while clock() < st.open - PREOPEN_START and runner.stop_reason is None:   # idle until just before the open
            S.write_heartbeat(state_dir, clock(), mode.value, engine_status(engine))
            time.sleep(5)
        result = runner.loop() if runner.stop_reason is None else {"ticks": 0, "decisions": 0,
                                                                   "stop": runner.stop_reason}
        why = runner.stop_reason or why
    except BaseException as e:
        why = f"crash: {type(e).__name__}: {e}"
        raise
    finally:
        signal.signal(signal.SIGTERM, prev_handler)
        recorder.close()
        # a last heartbeat saying the bot stopped: the watchdog then leaves a FLAT account alone (it still
        # flattens anything left open)
        S.write_heartbeat(state_dir, clock(), mode.value, {**engine_status(engine), "stopped": why})
        if wd_proc is not None and clock() > st.close:
            wd_proc.terminate()
    lines = J.read_journal(J.journal_path(state_dir, d, mode))
    text = summarize(lines, mode.value)
    journal.write("end", **result)
    out(text)
    return 0


def start_watchdog(mode: Mode, state_dir: Path) -> subprocess.Popen:
    """The MT-G39 watchdog as its own OS process (its own session, so a crash or Ctrl-C of the bot does not take
    it down)."""
    log = open(Path(state_dir) / f"watchdog-{now_ny():%Y-%m-%d}.log", "a")
    return subprocess.Popen([sys.executable, "-m", "lab.scalp.live", "watchdog", "--mode", mode.value,
                             "--parent-pid", str(os.getpid())], cwd=str(C.TRADING_DIR), stdout=log,
                            stderr=subprocess.STDOUT, start_new_session=True)


# ------------------------------------------------------------------------------------------ replay
def replay(session_date: date, *, recording: str | Path | None = None, e0: float | None = None,
           state_dir: str | Path | None = None, env: dict[str, str] | None = None,
           out: Callable[[str], None] = print, market: Any = None, clients: tuple[Any, Any] | None = None,
           journal: Any = None, engine_cls: Any = None, sim_broker_cls: Any = None,
           ctx_by_symbol: dict | None = None, session: SessionTimes | None = None,
           events_path: str | Path | None = None) -> dict[str, Any]:
    """Replay one session through the real engine with a simulated broker. Historical SIP bars and SIP quotes by
    default (bar fills), or a recording (quote fills). E0 comes from --e0, else the SCALP account's last_equity
    (read-only). Nothing is sent to any broker."""
    state_dir = Path(state_dir or C.STATE_DIR)
    env = dict(os.environ if env is None else env)
    # a recording holds IEX bars (a volume setup is shadow-only there, MT-G35); a historical replay uses SIP bars
    registry, shadow_only = registry_for_run(C.load_registry(), J.MemoryJournal(Mode.REPLAY),
                                             feed="IEX" if recording is not None else "SIP")
    need_data = (market is None and recording is None) or ctx_by_symbol is None or session is None
    if clients is None and need_data:
        clients = scalp_clients(env)                 # read-only data calls with the SCALP keys
    data_client, trading_client = clients or (None, None)
    if e0 is None:
        from .broker import AlpacaBroker
        e0 = float(AlpacaBroker(mode=Mode.DRY, lock_path=state_dir / S.LOCK,
                                pin_path=state_dir / S.ACCOUNT_PIN).account().last_equity)
    if ctx_by_symbol is None or session is None:
        ctx_by_symbol, row = {}, None
        for sym in registry.symbols():
            ctx, row, _ = M.build_context(sym, session_date, M.dt.CACHE_DIR, data_client, trading_client,
                                          log=lambda s: None)
            ctx_by_symbol[sym] = ctx
        session = SessionTimes.from_calendar(session_date, row.open, row.close)
    if market is None and recording is not None:
        market = M.RecordingMarket(recording)          # its clock starts at the first recorded snapshot (pre-open)
    elif market is None:
        M.dt.download(registry.symbols(), session_date, session_date, M.dt.CACHE_DIR, client=data_client,
                      trading_client=trading_client, log=lambda s: None)
        bars = {s: M.dt.load_bars(s, session_date, session_date) for s in registry.symbols()}
        market = M.ReplayMarket(session_date, bars, M.SipQuoteSource(data_client), M.SimClock(session.open),
                                open_ts=session.open, close_ts=session.close)
    clock = market.clock
    # a recording holds the quotes the bot saw: fills at those quotes, as in the recorded run. SIP bars: bar fills.
    fill_mode = "quote" if isinstance(market, M.RecordingMarket) else "bar"
    if journal is None:
        jp = J.journal_path(state_dir, session_date, Mode.REPLAY)
        if jp.exists():
            jp.unlink()                                  # a replay journal describes one replay run
        journal = J.FileJournal(jp, Mode.REPLAY, clock)
    if sim_broker_cls is None:
        from .broker import SimBroker as sim_broker_cls   # noqa: N813
    acct = AccountView("PA-REPLAY", "ACTIVE", e0, e0, e0, e0, e0, False, False, "sim://replay")
    sim = sim_broker_cls(clock, account=acct, positions=(), fill_mode=fill_mode)
    # a replay's KILL / HALT / daily-stop files live in a scratch folder that starts empty on every replay, so an
    # earlier replay can never block this one (and a replay never touches the running bot's state/scalp files)
    scratch = state_dir / "replay"
    shutil.rmtree(scratch, ignore_errors=True)
    counters = DayCounters(session_date=session_date, e0=e0, cash_prev_close=e0)
    # the committed calendar starts on 2026-09-29: an older day is UNKNOWN (no entries) unless a verified calendar
    # covering it is given with --events
    events = load_events_or_unknown(events_path or C.EVENTS_PATH).day(session_date)
    engine = make_engine(sim, journal, registry, counters, session, events, ctx_by_symbol, Mode.REPLAY, clock,
                         state_dir=scratch, engine_cls=engine_cls)
    journal.write("replay_start", date=session_date, e0=e0, fill_mode=fill_mode, events_known=events.known,
                  events_file=str(events_path or C.EVENTS_PATH), shadow_only=shadow_only,
                  recording=str(recording) if recording else None)
    runner = Runner(engine, market, journal, Mode.REPLAY, clock, scratch, session, sim_broker=sim,
                    live=False, heartbeat=False)
    result = runner.loop()
    if isinstance(getattr(market, "quote_fn", None), M.SipQuoteSource):
        market.quote_fn.flush()
    journal.write("replay_end", **result)
    lines = getattr(journal, "lines", None)
    if lines is None:
        lines = J.read_journal(J.journal_path(state_dir, session_date, Mode.REPLAY))
    text = summarize(lines, "replay")
    out(text)
    return {**result, "summary": text, "decisions_list": runner.decisions}
