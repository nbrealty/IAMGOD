"""Runtime state files under trading/state/scalp/ (gitignored): heartbeat, HALT and KILL flags, the session file,
the append-only changes log and the alerts log (MT-G27, MT-G39, MT-G40, MT-G41).

- heartbeat-<mode>.json (heartbeat-paper.json, heartbeat-dry.json): written by the runner every tick ({ts, pid,
  mode, status}); the watchdog and the kill command read the age of THEIR mode's file only, so a running dry bot
  can never make the paper watchdog or `kill` believe the paper bot is alive. Written atomically (temp file +
  rename) so a reader never sees half a file.
- KILL: a request (from `kill`) that the running engine acts on at its next tick. HALT: set by any kill switch,
  watchdog flatten or drawdown halt; only `reset-halt` clears it (MT-G27: only a person clears a halt).
  These plain names (and daily_stop-DATE) belong to the PAPER bot. A dry run's engine uses its own names
  (KILL-dry, HALT-dry, daily_stop-DATE-dry, see flag_name): a simulated kill must never flatten the paper account,
  and a dry bot must never swallow the owner's `kill` meant for the paper bot. A dry engine still obeys the paper
  HALT (read-only, the stricter choice) but never writes or removes it.
- changes.log: one JSON line per guardrail change, halt reset or accepted lost journal (accept-journal-gap), with
  the reason (MT-G41). Never rewritten.
- test_start.pin: the first paper session of the whole test (written once, logged in changes.log), so the $150 /
  60-session whole-test stop and the 5% drawdown halt see every session since, not just today.
- deploy_block-DATE.json: MT-G27, written when a start between 09:00 and 16:15 is flagged; it blocks entries for
  the rest of that session, whatever later restarts run.
- alerts.log: one line per alert (the owner reads it; stderr gets the same text).
- broker.lock: the exclusive lock shared by the bot, the watchdog and the kill command around order actions.
Nothing here talks to a broker or reads keys.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from .config import STATE_DIR
from .journal import plain
from .model import as_ny

HEARTBEAT = "heartbeat.json"          # (v1 name, no longer written: see heartbeat_path)
HALT = "HALT"
KILL = "KILL"
CHANGES = "changes.log"
ALERTS = "alerts.log"
LOCK = "broker.lock"
RISK_PIN = "risk_hash.pin"
ACCOUNT_PIN = "account.pin"
TEST_START_PIN = "test_start.pin"      # the whole test's first paper session (paper caps: $150 / 60 sessions)


def path(state_dir: str | Path | None, name: str) -> Path:
    return Path(state_dir or STATE_DIR) / name


def write_json_atomic(p: Path, data: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(plain(data), indent=1, sort_keys=True))
    os.replace(tmp, p)


def read_json(p: Path) -> dict | None:
    try:
        v = json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return None
    return v if isinstance(v, dict) else None


# ------------------------------------------------------------------------------------------ heartbeat (MT-G39)
def _mode(mode: Any) -> str:
    return str(getattr(mode, "value", mode))


def heartbeat_path(state_dir: str | Path | None, mode: Any) -> Path:
    return path(state_dir, f"heartbeat-{_mode(mode)}.json")


def write_heartbeat(state_dir: str | Path | None, now: pd.Timestamp, mode: str, status: dict[str, Any]) -> None:
    write_json_atomic(heartbeat_path(state_dir, mode), {"ts": as_ny(now).isoformat(), "pid": os.getpid(),
                                                         "mode": _mode(mode), "status": status})


def read_heartbeat(state_dir: str | Path | None, mode: Any = None) -> dict | None:
    """That mode's heartbeat; with no mode, the newest of any mode (for reports and tests only)."""
    if mode is not None:
        hb = read_json(heartbeat_path(state_dir, mode))
        return hb if hb is not None and hb.get("mode") == _mode(mode) else None
    beats = [hb for p in sorted(Path(state_dir or STATE_DIR).glob("heartbeat-*.json")) if (hb := read_json(p))]
    return max(beats, key=lambda h: str(h.get("ts") or "")) if beats else None


def heartbeat_age_s(state_dir: str | Path | None, now: pd.Timestamp, mode: Any = None) -> float | None:
    """Seconds since the last heartbeat of `mode` (any mode when None); None when there is none."""
    hb = read_heartbeat(state_dir, mode)
    try:
        return (as_ny(now) - as_ny(hb["ts"])).total_seconds() if hb else None
    except (KeyError, ValueError, TypeError):
        return None


# ------------------------------------------------------------------------------------------ KILL / HALT (MT-G27)
def write_flag(state_dir: str | Path | None, name: str, reason: str, now: pd.Timestamp, by: str) -> None:
    write_json_atomic(path(state_dir, name), {"reason": reason, "ts": as_ny(now).isoformat(), "by": by})


def read_flag(state_dir: str | Path | None, name: str) -> dict | None:
    p = path(state_dir, name)
    if not p.exists():
        return None
    return read_json(p) or {"reason": "unreadable flag file", "ts": None}


def flag_name(base: str, mode: Any = "paper") -> str:
    """The file name of a flag for one mode: the plain name for PAPER (what `kill`, the watchdog and `reset-halt`
    use), `<name>-<mode>` for every other mode, so a dry run can never trip or clear the paper bot's flags."""
    m = _mode(mode)
    return base if m == "paper" else f"{base}-{m}"


def halted(state_dir: str | Path | None, mode: Any = "paper") -> bool:
    """HALT for this mode: the paper HALT always counts (a dry run obeys it too); a dry run's own HALT-dry also."""
    return path(state_dir, HALT).exists() or path(state_dir, flag_name(HALT, mode)).exists()


def append_line(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(plain(data), separators=(",", ":")) + "\n")
        f.flush()
        os.fsync(f.fileno())


def alert(state_dir: str | Path | None, now: pd.Timestamp, text: str, **fields: Any) -> None:
    append_line(path(state_dir, ALERTS), {"ts": as_ny(now).isoformat(), "alert": text, **fields})
    print(f"ALERT {as_ny(now):%H:%M:%S}: {text}", file=sys.stderr)


def append_change(state_dir: str | Path | None, now: pd.Timestamp, action: str, reason: str, **fields: Any) -> None:
    """MT-G41: every guardrail change and every halt reset, with its reason, append-only."""
    if not str(reason or "").strip():
        raise ValueError("a reason is required (MT-G41)")
    append_line(path(state_dir, CHANGES), {"ts": as_ny(now).isoformat(), "action": action, "reason": reason,
                                           **fields})


def read_changes(state_dir: str | Path | None) -> list[dict]:
    p = path(state_dir, CHANGES)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


RESET_MODES = ("paper", "dry")


def reset_halt(state_dir: str | Path | None, reason: str, now: pd.Timestamp) -> dict:
    """Clear HALT and KILL (the paper ones and a dry run's own) after writing the reset (and what it cleared) to
    changes.log. Returns what was cleared."""
    names = {"halt": HALT, "kill": KILL}
    names.update({f"{k}-{m}": flag_name(v, m) for m in RESET_MODES if m != "paper"
                  for k, v in (("halt", HALT), ("kill", KILL))})
    cleared = {k: read_flag(state_dir, n) for k, n in names.items()}
    append_change(state_dir, now, "reset-halt", reason, cleared=cleared)
    for name in names.values():
        with contextlib.suppress(FileNotFoundError):
            path(state_dir, name).unlink()
    return cleared


# ------------------------------------------------------------------------------------------ session file (MT-G40)
def session_path(state_dir: str | Path | None, d: date) -> Path:
    return path(state_dir, f"session-{d.isoformat()}.json")


def read_session(state_dir: str | Path | None, d: date) -> dict | None:
    return read_json(session_path(state_dir, d))


def write_session(state_dir: str | Path | None, d: date, info: dict) -> None:
    write_json_atomic(session_path(state_dir, d), info)


def last_package_hash(state_dir: str | Path | None, before: date) -> str | None:
    """MT-G27 deploy baseline: the package hash of the last start of the latest session file before `before`."""
    for p in sorted(Path(state_dir or STATE_DIR).glob("session-*.json"), reverse=True):
        try:
            d = date.fromisoformat(p.stem[len("session-"):])
        except ValueError:
            continue
        if d >= before:
            continue
        info = read_json(p) or {}
        starts = [x for x in info.get("starts") or [] if isinstance(x, dict) and x.get("package_hash")]
        h = starts[-1]["package_hash"] if starts else info.get("package_hash")
        if h:
            return str(h)
    return None


# ------------------------------------------------------------------------------------------ whole-test start
def read_test_start(state_dir: str | Path | None) -> date | None:
    p = path(state_dir, TEST_START_PIN)
    try:
        return date.fromisoformat(p.read_text().strip())
    except (OSError, ValueError):
        return None


def pin_test_start(state_dir: str | Path | None, d: date, now: pd.Timestamp, reason: str) -> date:
    """Write the test's start date once (never moved later: an existing pin wins) and log it (MT-G41)."""
    have = read_test_start(state_dir)
    if have is not None:
        return have
    p = path(state_dir, TEST_START_PIN)
    if p.exists():
        raise RuntimeError(f"{p} is unreadable: put the test's first paper date (YYYY-MM-DD) back by hand")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(d.isoformat() + "\n")
    append_change(state_dir, now, "test-start", reason, test_start=d.isoformat())
    return d


def move_test_start_earlier(state_dir: str | Path | None, d: date, now: pd.Timestamp, reason: str) -> date:
    """Move the pin to an EARLIER date only (the broker's history shows SCALP orders before it: a lost state folder
    must never restart the whole-test count). Logged in changes.log (MT-G41). Returns the pin now in force."""
    have = read_test_start(state_dir)
    if have is not None and have <= d:
        return have
    p = path(state_dir, TEST_START_PIN)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(d.isoformat() + "\n")
    append_change(state_dir, now, "test-start", reason, test_start=d.isoformat(),
                  previous=have.isoformat() if have is not None else None)
    return d


# ------------------------------------------------------------------------------------------ deploy block (MT-G27)
def deploy_block_path(state_dir: str | Path | None, d: date) -> Path:
    return path(state_dir, f"deploy_block-{d.isoformat()}.json")


def read_deploy_block(state_dir: str | Path | None, d: date) -> dict | None:
    """Today's sticky deploy block: once a start in 09:00-16:15 was flagged, every later start today is blocked
    too (a restart must not clear it). None when there is none."""
    p = deploy_block_path(state_dir, d)
    if not p.exists():
        return None
    return read_json(p) or {"reason": "unreadable deploy block file"}


def write_deploy_block(state_dir: str | Path | None, d: date, data: dict) -> None:
    if not deploy_block_path(state_dir, d).exists():
        write_json_atomic(deploy_block_path(state_dir, d), data)


# ------------------------------------------------------------------------------------------ broker lock
def flock_wait(fh: Any, wait_s: float | None) -> bool:
    """Take an exclusive flock on an open file. wait_s None: block until free (True). Otherwise try until the
    deadline and return False if another holder never lets go (a hung bot must not hang the watchdog, MT-G39)."""
    if wait_s is None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        return True
    deadline = time.monotonic() + max(float(wait_s), 0.0)
    while True:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)


@contextlib.contextmanager
def broker_lock(state_dir: str | Path | None, wait_s: float | None = None) -> Iterator[bool]:
    """Exclusive advisory lock on state/scalp/broker.lock. Yields True when held; with `wait_s` it gives up after
    that many seconds and yields False (the caller goes on without it and says so)."""
    p = path(state_dir, LOCK)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a+") as f:
        got = flock_wait(f, wait_s)
        try:
            yield got
        finally:
            if got:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
