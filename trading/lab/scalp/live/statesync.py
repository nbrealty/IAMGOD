"""Durable state across fresh cloud containers: `state-save` and `state-restore` (MT-G3, G4, G12, G13, G40, G41).

A cloud container starts with an empty trading/state/scalp. The broker's order history rebuilds the counters, the
whole-test start and a lost HALT, but some records live only in the local files: the journals (decision mids for
the MT-G3 / G13 slippage history, MT-G4 take-profit resolutions), changes.log (MT-G41), the pins and the session
files (E0, the MT-G27 deploy baseline). These two commands copy exactly those to and from the git branch
`scalp-state`, the one branch MINUTE_TRADING.md allows for runtime state (never `trading-state`).

What travels is a WHITELIST (nothing else, ever): journal/*.jsonl, *.pin, changes.log, session-*.json and
deploy_block-*.json, under `scalp/` on the branch. Never keys or .env, heartbeats, locks, KILL / HALT flags,
recordings or caches. A file is refused if it contains the value of the SCALP key or secret.

Both commands work in a SEPARATE git worktree (a temporary folder, removed afterwards): the owner's checkout (its
branch, index and files) is never touched and no local branch is created.
- state-save: reads the branch tip (it may not exist yet), merges the local files onto it, commits, and pushes
  `<commit>:refs/heads/scalp-state` WITHOUT force. If the branch moved meanwhile the push is refused; it then
  reads the new tip and tries once more.
- state-restore: checks the branch tip out in a worktree and merges its files into state/scalp. Refused while a
  bot heartbeat is fresh (a running bot writes these files). Logged in changes.log (MT-G41).
Merging never loses a record: append-only line files (journal/*.jsonl, changes.log) become the union of both sides'
lines in time order; test_start.pin keeps the EARLIER date (the whole-test stop must never restart); any other file
is copied only where it is missing, and a different copy on both sides is reported as a conflict and left alone.
"""
from __future__ import annotations

import fnmatch
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from . import config as C
from . import state as S
from .model import as_ny

BRANCH = "scalp-state"                 # MINUTE_TRADING.md: runtime state goes here, never to `trading-state`
PREFIX = "scalp"                       # folder on the branch
PATTERNS = ("journal/*.jsonl", "*.pin", S.CHANGES, "session-*.json", "deploy_block-*.json")
LINE_FILES = ("journal/*.jsonl", S.CHANGES)
SECRET_ENV = ("ALPACA_SCALP_KEY", "ALPACA_SCALP_SECRET")


def _allowed(rel: str) -> bool:
    return "/" not in rel.replace("journal/", "", 1) and any(fnmatch.fnmatch(rel, p) for p in PATTERNS) \
        and ".." not in rel.split("/")


def _is_lines(rel: str) -> bool:
    return any(fnmatch.fnmatch(rel, p) for p in LINE_FILES)


def state_files(state_dir: str | Path) -> list[str]:
    """The whitelisted files under state_dir, as paths relative to it (sorted)."""
    root = Path(state_dir)
    if not root.exists():
        return []
    out = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
    return sorted(r for r in out if _allowed(r))


def _check_branch(branch: str) -> None:
    if branch != BRANCH:
        raise ValueError(f"runtime state goes only to the branch {BRANCH!r} (MINUTE_TRADING.md), not {branch!r}")


def _secrets(env: dict[str, str]) -> list[bytes]:
    return [v.encode() for k in SECRET_ENV if len(v := (env.get(k) or "").strip()) >= 8]


# ------------------------------------------------------------------------------------------ merging
def _ts_key(line: bytes) -> pd.Timestamp:
    try:
        return as_ny(json.loads(line)["ts"])
    except (ValueError, KeyError, TypeError):
        return pd.Timestamp.min.tz_localize("UTC")


def merge_lines(a: bytes, b: bytes) -> bytes:
    """Union of two append-only JSON-lines files: every line of `a`, then b's lines that `a` lacks, in time order
    (stable, so lines with the same time keep their order). Nothing is ever dropped."""
    la = [x for x in a.splitlines() if x.strip()]
    have = set(la)
    lb = [x for x in b.splitlines() if x.strip() and x not in have]
    if not lb:
        return a
    merged = sorted(la + lb, key=_ts_key)
    return b"\n".join(merged) + b"\n"


def merge_file(rel: str, dest: bytes | None, src: bytes) -> tuple[bytes | None, str]:
    """What `dest` becomes when `src` is merged into it: (new bytes or None for no change, what happened)."""
    if dest == src:
        return None, "same"
    if dest is None:
        return src, "new"
    if _is_lines(rel):
        out = merge_lines(dest, src)
        return (None, "same") if out == dest else (out, "merged")
    if rel == S.TEST_START_PIN:
        try:
            a, b = pd.Timestamp(dest.decode().strip()), pd.Timestamp(src.decode().strip())
        except ValueError:
            return None, "conflict"
        return (src, "earlier test start") if b < a else (None, "kept the earlier test start")
    return None, "conflict"


# ------------------------------------------------------------------------------------------ git
class GitError(RuntimeError):
    pass


def _env(env: dict[str, str] | None) -> dict[str, str]:
    return {**os.environ, **(env or {})}


def _git(cwd: str | Path, *args: str, env: dict[str, str] | None = None, check: bool = True,
         binary: bool = False) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", *args], cwd=str(cwd), env=_env(env), capture_output=True, text=not binary)
    if check and r.returncode != 0:
        err = r.stderr if not binary else r.stderr.decode(errors="replace")
        raise GitError(f"git {' '.join(args[:3])} failed: {str(err).strip()[:300]}")
    return r


def _remote_tip(repo: Path, remote: str, env: dict[str, str] | None) -> str | None:
    """The branch's tip at the remote (fetched, so its objects are here), or None when the branch does not exist."""
    r = _git(repo, "ls-remote", "--heads", remote, f"refs/heads/{BRANCH}", env=env)
    line = r.stdout.strip().splitlines()
    if not line:
        return None
    tip = line[0].split()[0]
    _git(repo, "fetch", "--quiet", remote, f"refs/heads/{BRANCH}", env=env)     # objects only; no ref is moved
    return tip


def _show(repo: Path, tip: str, path: str, env: dict[str, str] | None) -> bytes | None:
    r = _git(repo, "cat-file", "-p", f"{tip}:{path}", env=env, check=False, binary=True)
    return r.stdout if r.returncode == 0 else None


def _ident(repo: Path, env: dict[str, str] | None) -> dict[str, str]:
    """A commit identity when git has none configured (a fresh container)."""
    e = dict(env or {})
    if not _git(repo, "config", "user.email", env=env, check=False).stdout.strip():
        for k, v in (("GIT_AUTHOR_NAME", "scalp-state"), ("GIT_AUTHOR_EMAIL", "scalp-state@localhost"),
                     ("GIT_COMMITTER_NAME", "scalp-state"), ("GIT_COMMITTER_EMAIL", "scalp-state@localhost")):
            e.setdefault(k, v)
    return e


class _Worktree:
    """A temporary worktree of `repo` at `rev` (detached; with checkout=False no file is written, only the index)."""

    def __init__(self, repo: Path, rev: str, env: dict[str, str] | None, checkout: bool):
        self.repo, self.rev, self.env, self.checkout = repo, rev, env, checkout
        self.path = Path(tempfile.mkdtemp(prefix="scalp-state-wt-"))

    def __enter__(self) -> Path:
        args = ["worktree", "add", "--detach"] + ([] if self.checkout else ["--no-checkout"])
        _git(self.repo, *args, str(self.path), self.rev, env=self.env)
        return self.path

    def __exit__(self, *exc: Any) -> None:
        _git(self.repo, "worktree", "remove", "--force", str(self.path), env=self.env, check=False)
        shutil.rmtree(self.path, ignore_errors=True)
        _git(self.repo, "worktree", "prune", env=self.env, check=False)


# ------------------------------------------------------------------------------------------ commands
def save(state_dir: str | Path, repo: str | Path, *, remote: str = "origin", branch: str = BRANCH,
         env: dict[str, str] | None = None, now: pd.Timestamp | None = None,
         out: Callable[[str], None] = print) -> dict[str, Any]:
    """`state-save`: merge the whitelisted state files onto the scalp-state branch and push it (never forced)."""
    _check_branch(branch)
    repo, state_dir = Path(repo), Path(state_dir)
    now = as_ny(now) if now is not None else pd.Timestamp.now(tz="America/New_York")
    files = state_files(state_dir)
    secrets = _secrets(_env(env))
    bad = [r for r in files if any(s in (state_dir / r).read_bytes() for s in secrets)]
    if bad:
        raise ValueError(f"refused: {bad} contain the SCALP key or secret; nothing was saved")
    if not files:
        out(f"Nothing to save: no journal, pin, changes.log or session file in {state_dir}.")
        return {"pushed": False, "changed": [], "conflicts": []}
    env_c = _ident(repo, env)
    for attempt in (1, 2):
        tip = _remote_tip(repo, remote, env)
        changed: list[str] = []
        conflicts: list[str] = []
        with _Worktree(repo, tip or "HEAD", env, checkout=False) as wt:
            _git(wt, "read-tree", *([tip] if tip else ["--empty"]), env=env)
            for rel in files:
                dst = f"{PREFIX}/{rel}"
                new, what = merge_file(rel, _show(repo, tip, dst, env) if tip else None, (state_dir / rel).read_bytes())
                if what == "conflict":
                    conflicts.append(rel)
                if new is None:
                    continue
                p = wt / dst
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(new)
                _git(wt, "add", "--force", "--", dst, env=env)
                changed.append(rel)
            if not changed:
                out(f"scalp-state is up to date ({len(files)} files checked"
                    + (f"; conflicts left alone: {conflicts}" if conflicts else "") + ").")
                return {"pushed": False, "changed": [], "conflicts": conflicts, "tip": tip}
            tree = _git(wt, "write-tree", env=env).stdout.strip()
            msg = f"scalp state {now:%Y-%m-%d %H:%M} ET: {len(changed)} file(s)"
            sign = ["-S"] if _git(repo, "config", "--bool", "commit.gpgsign", env=env,
                                  check=False).stdout.strip() == "true" else []   # commit-tree ignores the setting
            commit = _git(wt, "commit-tree", *sign, tree, *(["-p", tip] if tip else []), "-m", msg,
                          env=env_c).stdout.strip()
            # never forced: a branch that moved meanwhile refuses this push, and the next attempt merges onto it
            r = _git(wt, "push", "--quiet", remote, f"{commit}:refs/heads/{BRANCH}", env=env, check=False)
        if r.returncode == 0:
            out(f"Saved {len(changed)} file(s) to {remote}/{BRANCH} ({commit[:10]})"
                + (f"; conflicts left alone: {conflicts}" if conflicts else "") + ".")
            return {"pushed": True, "changed": changed, "conflicts": conflicts, "commit": commit, "tip": tip}
        if attempt == 2:
            raise GitError(f"push to {remote}/{BRANCH} refused twice: {r.stderr.strip()[:300]}")
    raise AssertionError("unreachable")


def restore(state_dir: str | Path, repo: str | Path, *, remote: str = "origin", branch: str = BRANCH,
            env: dict[str, str] | None = None, now: pd.Timestamp | None = None,
            out: Callable[[str], None] = print) -> dict[str, Any]:
    """`state-restore`: merge the scalp-state branch's files into state/scalp (see the module docstring)."""
    _check_branch(branch)
    repo, state_dir = Path(repo), Path(state_dir)
    now = as_ny(now) if now is not None else pd.Timestamp.now(tz="America/New_York")
    for mode in ("paper", "dry"):
        age = S.heartbeat_age_s(state_dir, now, mode)
        if age is not None and 0 <= age <= C.HEARTBEAT_STALE_S:
            raise RuntimeError(f"refused: the {mode} bot's heartbeat is {age:.0f} s old (a running bot writes these "
                               "files). Stop it first.")
    tip = _remote_tip(repo, remote, env)
    if tip is None:
        out(f"No {BRANCH} branch at {remote} yet: nothing to restore.")
        return {"restored": [], "conflicts": [], "tip": None}
    restored: list[str] = []
    conflicts: list[str] = []
    skipped: list[str] = []
    with _Worktree(repo, tip, env, checkout=True) as wt:
        root = wt / PREFIX
        for p in sorted(root.rglob("*")) if root.exists() else []:
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            if not _allowed(rel):
                skipped.append(rel)                     # never copy anything outside the whitelist
                continue
            dst = state_dir / rel
            new, what = merge_file(rel, dst.read_bytes() if dst.exists() else None, p.read_bytes())
            if what == "conflict":
                conflicts.append(rel)
            if new is None:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(f".{dst.name}.restore.tmp")
            tmp.write_bytes(new)
            os.replace(tmp, dst)
            restored.append(rel)
    S.append_change(state_dir, now, "state-restore", f"merged {len(restored)} file(s) from {remote}/{BRANCH}",
                    commit=tip, restored=restored, conflicts=conflicts, skipped=skipped)
    out(f"Restored {len(restored)} file(s) from {remote}/{BRANCH} ({tip[:10]})"
        + (f"; conflicts left alone (local copy kept): {conflicts}" if conflicts else "")
        + (f"; ignored (not whitelisted): {skipped}" if skipped else "") + ".")
    return {"restored": restored, "conflicts": conflicts, "skipped": skipped, "tip": tip}
