"""Append-only JSON-lines journal (MT-G3, MT-G27, owner decision 3).

One line per event: {"ts", "mode", "kind", ...fields}. Values are made plain JSON: numpy numbers become Python
numbers, NaN/inf become null, enums their value, Timestamps/dates ISO strings, dataclasses dicts, sets and tuples
lists. Every line about a setup (any line with `setup_id`) carries `setup_id, version, lane, feed`; a missing
one is written as null and listed under `labels_missing`, so a gap shows up in the report instead of crashing
the bot mid-trade. `FileJournal` flushes and fsyncs every line (a crash must not lose the record);
`MemoryJournal` keeps lines in a list for tests, dry runs and the self-test.
"""
from __future__ import annotations

import dataclasses
import json
import math
import os
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from .model import Mode

SETUP_LABELS = ("setup_id", "version", "lane", "feed")


def plain(v: Any) -> Any:
    """A JSON-safe copy of v."""
    if v is None or isinstance(v, (bool, str)):
        return v
    if isinstance(v, Enum):
        return plain(v.value)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating, Decimal)):
        f = float(v)
        return f if math.isfinite(f) else None
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.isoformat()
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, pd.Timedelta):
        return v.total_seconds()
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return {f.name: plain(getattr(v, f.name)) for f in dataclasses.fields(v)}
    if isinstance(v, dict):
        return {str(plain(k)) if not isinstance(k, str) else k: plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set, frozenset, np.ndarray)):
        items = sorted(v, key=str) if isinstance(v, (set, frozenset)) else list(v)
        return [plain(x) for x in items]
    return str(v)


def make_line(ts: Any, mode: Mode | str, kind: str, fields: dict[str, Any]) -> dict[str, Any]:
    line = {"ts": plain(ts), "mode": plain(Mode(mode)), "kind": str(kind)}
    for k, v in fields.items():
        if k in line:
            raise ValueError(f"journal field {k!r} is reserved")
        line[k] = plain(v)
    if "setup_id" in line:
        missing = [k for k in SETUP_LABELS if line.get(k) is None]
        for k in missing:
            line.setdefault(k, None)
        if missing:
            line["labels_missing"] = missing
    return line


class MemoryJournal:
    def __init__(self, mode: Mode | str = Mode.DRY, clock: Callable[[], Any] | None = None):
        self.mode, self.clock = Mode(mode), clock or (lambda: pd.Timestamp.now(tz="America/New_York"))
        self.lines: list[dict[str, Any]] = []

    def write(self, kind: str, **fields: Any) -> None:
        self.lines.append(make_line(self.clock(), self.mode, kind, fields))

    def of(self, kind: str) -> list[dict[str, Any]]:
        return [x for x in self.lines if x["kind"] == kind]

    def kinds(self) -> list[str]:
        return [x["kind"] for x in self.lines]


class FileJournal:
    """Appends to `path` (created with its folders). `clock()` gives the timestamp of each line."""

    def __init__(self, path: str | Path, mode: Mode | str, clock: Callable[[], Any]):
        self.path, self.mode, self.clock = Path(path), Mode(mode), clock
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, kind: str, **fields: Any) -> None:
        text = json.dumps(make_line(self.clock(), self.mode, kind, fields), separators=(",", ":"),
                          allow_nan=False) + "\n"
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())


def journal_path(state_dir: str | Path, session_date: date, mode: Mode | str) -> Path:
    """state/scalp/journal/YYYY-MM-DD-<mode>.jsonl"""
    return Path(state_dir) / "journal" / f"{session_date.isoformat()}-{Mode(mode).value}.jsonl"


def read_journal(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
