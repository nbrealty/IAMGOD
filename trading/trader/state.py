"""Per-book state (JSON) and an append-only audit journal (JSONL)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .config import STATE_DIR
from .models import Lot

KILL_FILE = "KILL"


@dataclass
class BookState:
    book: str
    last_run_date: str | None = None
    peak_equity: float = 0.0
    halted: bool = False
    equity_history: list[dict] = field(default_factory=list)  # {date, equity, benchmark}
    lots: dict[str, dict[str, Lot]] = field(default_factory=dict)  # sleeve -> symbol -> Lot
    closed_trades: list[dict] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)  # Claude's journal notes {date, note}
    sim: dict = field(default_factory=dict)  # simulator cash/positions

    # --- persistence -----------------------------------------------------------------------

    @staticmethod
    def path(book: str, state_dir: Path = STATE_DIR) -> Path:
        return state_dir / book / "state.json"

    @classmethod
    def load(cls, book: str, state_dir: Path = STATE_DIR) -> "BookState":
        p = cls.path(book, state_dir)
        if not p.exists():
            return cls(book=book)
        d = json.loads(p.read_text())
        d["lots"] = {s: {sym: Lot.from_dict(l) for sym, l in held.items()} for s, held in d["lots"].items()}
        return cls(**d)

    def save(self, state_dir: Path = STATE_DIR) -> None:
        p = self.path(self.book, state_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        d = self.__dict__.copy()
        d["lots"] = {s: {sym: l.to_dict() for sym, l in held.items()} for s, held in self.lots.items() if held}
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=2, default=str))
        tmp.replace(p)

    # --- equity bookkeeping ----------------------------------------------------------------

    def record_equity(self, date: str, equity: float, benchmark: float) -> tuple[float, float]:
        """Store today's equity; return (day_pnl, week_pnl) measured against earlier runs."""
        hist = [h for h in self.equity_history if h["date"] != date]
        prev = hist[-1]["equity"] if hist else equity
        week = pd.Timestamp(date).isocalendar()[:2]
        before_week = [h for h in hist if pd.Timestamp(h["date"]).isocalendar()[:2] < week]
        week_start = before_week[-1]["equity"] if before_week else (hist[0]["equity"] if hist else equity)
        hist.append({"date": date, "equity": round(equity, 2), "benchmark": round(benchmark, 4)})
        self.equity_history = hist
        self.peak_equity = max(self.peak_equity, equity)
        return equity - prev, equity - week_start


def kill_switch_on(state_dir: Path = STATE_DIR) -> bool:
    return (state_dir / KILL_FILE).exists()


def set_kill_switch(on: bool, state_dir: Path = STATE_DIR) -> None:
    f = state_dir / KILL_FILE
    state_dir.mkdir(parents=True, exist_ok=True)
    if on:
        f.write_text("Trading halted by a human. Run `python -m trader kill off` to resume.\n")
    elif f.exists():
        f.unlink()


def journal(book: str, entry: dict, state_dir: Path = STATE_DIR) -> None:
    p = state_dir / book / "journal.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")
