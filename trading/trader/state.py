"""Per-book state (JSON) and an append-only audit journal (JSONL)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, fields
from pathlib import Path

import pandas as pd

from .config import STATE_DIR
from .models import Lot

KILL_FILE = "KILL"
EXPERIMENTS_FILE = "experiments.jsonl"


@dataclass
class BookState:
    book: str
    last_run_date: str | None = None
    peak_equity: float = 0.0
    halted: bool = False
    # {date, equity, benchmark, closes: {SPY, IEF, EFA, DBC, VNQ, BIL}, exposure: {sleeve: notional}}
    equity_history: list[dict] = field(default_factory=list)
    lots: dict[str, dict[str, Lot]] = field(default_factory=dict)  # sleeve -> symbol -> Lot
    # One record per lot when it reaches zero: {date, sleeve, symbol, lot_id, entry_date, entry_price, exit_price,
    # qty (bought_qty), pnl (realized - costs), realized_pnl, costs, initial_risk_dollars, R (net), mae_R, mfe_R,
    # sessions_held, reason, tags}
    closed_trades: list[dict] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)  # Claude's journal notes {date, note}
    sim: dict = field(default_factory=dict)  # simulator cash/positions/open orders

    # EX-4: orders sent last run that settle into lots at the start of the next run.
    # {client_order_id, broker_order_id, date, symbol, side, qty, signal_close, asset_class,
    #  alloc: [{sleeve, delta_qty, stop, reason, tags}]}
    pending_orders: list[dict] = field(default_factory=list)
    # EX-4/EX-5/B-6: one row per settled fill {date, symbol, side, sleeve, asset_class, qty, signal_close, fill,
    #  slippage_bps (positive = worse for us), gap_R (B entries only)}
    fills: list[dict] = field(default_factory=list)
    # CL-9: shadow lots for vetoed entries {id, date, sleeve, symbol, fraction, qty, stop, status, entry_price, ...}
    shadow_lots: list[dict] = field(default_factory=list)
    # CL-5 / M-7: {id, date, book, symbol, horizon, direction, threshold_pct, probability, linked_decision,
    #  base_close, base_rate, resolve_after_date|None, outcome|None, brier|None, brier_ref|None, tags}
    predictions: list[dict] = field(default_factory=list)
    # CL-13 / M-5: {date, symbol, sleeve, rule_pct, claude_pct, reason_code, evidence, prediction_id,
    #  fill_ref|None, value_20d|None, resolved_date|None, tags}
    deviations: list[dict] = field(default_factory=list)
    # RISK-13: {sleeve: {"realized": float, "cum": float, "peak": float, "date": str}}
    sleeve_pnl: dict = field(default_factory=dict)
    # RISK-13 / M-11 latches: sleeve -> reason. New entries in these sleeves stop until the owner resets.
    sleeve_blocked: dict = field(default_factory=dict)
    promoted_sleeves: list[str] = field(default_factory=list)  # RISK-8: sleeves that passed M-10 (owner sets)
    # M-12: owner promotions {date, sleeve}; at most one promotion per sleeve per calendar quarter
    promotions: list[dict] = field(default_factory=list)
    # M-9: {date, role, mode ("api"|"session"), model, input_tokens, output_tokens, usd, samples}
    api_cost: list[dict] = field(default_factory=list)
    # CL-12: Claude book weights per run {date, weights: {A..D}, changed: [sleeves], reasons: {...}}
    weight_history: list[dict] = field(default_factory=list)
    veto_codes_restricted: bool = False  # CL-9 latch, reset by the owner
    cost_model_bps: dict = field(default_factory=dict)  # EX-5: measured overrides of the policy cost model
    veto_reset_date: str | None = None  # CL-9: owner reset; vetoes before this date no longer count
    # Guide rule 6: deviations lost money -> the Claude book follows the rule targets until the owner resets.
    deviations_restricted: bool = False
    deviations_reset_date: str | None = None
    # Owner decision 8: shadow lots for increases blocked by the active hype vetoes (NEWS-4, NEWS-13, NEWS-18
    # promotion). Same fields as `shadow_lots` (built by shadow.open_veto_lots) plus `kind: "news_veto"` and
    # `news_reasons`. Kept apart from `shadow_lots` so code vetoes never count toward Claude's CL-9 latch.
    news_veto_lots: list[dict] = field(default_factory=list)
    # NEWS-18 promotion memory {symbol: {last_promo, sessions_left, updated}} (news_signals.update_promo_history)
    news_promo_history: dict = field(default_factory=dict)

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
        known = {f.name for f in fields(cls)}
        d = {k: v for k, v in d.items() if k in known}  # tolerate fields from newer or older versions
        d["lots"] = {s: {sym: Lot.from_dict(l) for sym, l in held.items()} for s, held in d.get("lots", {}).items()}
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

    def record_equity(self, date: str, equity: float, benchmark: float, closes: dict | None = None,
                      exposure: dict | None = None) -> tuple[float, float]:
        """Store today's equity; return (day_pnl, week_pnl) measured against earlier runs."""
        hist = [h for h in self.equity_history if h["date"] != date]
        prev = hist[-1]["equity"] if hist else equity
        week = pd.Timestamp(date).isocalendar()[:2]
        before_week = [h for h in hist if pd.Timestamp(h["date"]).isocalendar()[:2] < week]
        week_start = before_week[-1]["equity"] if before_week else (hist[0]["equity"] if hist else equity)
        row = {"date": date, "equity": round(equity, 2), "benchmark": round(benchmark, 4)}
        if closes:
            row["closes"] = {k: round(float(v), 4) for k, v in closes.items()}
        if exposure:
            row["exposure"] = {k: round(float(v), 2) for k, v in exposure.items()}
        hist.append(row)
        self.equity_history = hist
        self.peak_equity = max(self.peak_equity, equity)
        return equity - prev, equity - week_start

    def month_pnl(self, date: str, equity: float) -> tuple[float, float | None]:
        """RISK-12: (month-to-date P&L, prior month-end equity). Uses equity_history before `date`'s month."""
        month = pd.Timestamp(date).to_period("M")
        before = [h for h in self.equity_history if pd.Timestamp(h["date"]).to_period("M") < month]
        if not before:
            return 0.0, None
        base = float(before[-1]["equity"])
        return equity - base, base


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


def fingerprint(*parts: str) -> str:
    """Short stable hash, used for prompt_version (CL-3) and parameter sets (M-13)."""
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode())
        h.update(b"\x00")
    return h.hexdigest()[:12]


def log_experiment(entry: dict, state_dir: Path = STATE_DIR) -> bool:
    """M-13: append {date, kind, version, reason, ...} unless the last entry of that kind has the same version.

    Returns True when a new line was written.
    """
    p = state_dir / EXPERIMENTS_FILE
    last = None
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("kind") == entry.get("kind"):
                last = e
    if last is not None and last.get("version") == entry.get("version"):
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    return True
