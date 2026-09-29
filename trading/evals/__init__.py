"""Frozen evaluation set for the Claude side (Agent building guide rules 14-15).

`bars.csv.gz` holds the market data once (every data symbol, 2016 to the last frozen date, 2 decimals) and
`manifest.json` the chosen days. Every day is rebuilt from those bars with the same starting state (a flat
book on the simulator with the playbook's starting cash) through the engine's own code, so a context in the
test set is exactly what a live run on that day would have shown.

    python -m evals.build                     # network: fetch history, pick the days, freeze them
    python -m evals.prepare --out DIR         # write each day's pending folder (context, schema, instructions)
    python -m evals.check DIR                 # score the decision/review files written there, code only
"""
from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path

import pandas as pd

from trader import ledger, risk
from trader.broker import SimBroker
from trader.config import Config
from trader.engine import _prepare_day
from trader.state import BookState

EVALS_DIR = Path(__file__).resolve().parent
BARS_FILE = EVALS_DIR / "bars.csv.gz"
MANIFEST_FILE = EVALS_DIR / "manifest.json"
EVAL_FILE = "eval.json"  # written next to context.json: the day's manifest row (control flag, regime, why)
COLUMNS = ["open", "high", "low", "close", "volume"]
LABELS = ("bull_calm", "bull_volatile", "bear", "panic", "choppy")

Bars = dict[str, pd.DataFrame]


# --- frozen bars -----------------------------------------------------------------------------------


def round_bars(bars: Bars) -> Bars:
    """Prices to 2 decimals and whole-share volume: what is frozen is exactly what the evals replay."""
    out = {}
    for s, df in bars.items():
        if df is None or not len(df):
            continue
        df = df.reindex(columns=COLUMNS).astype(float)
        df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].round(2)
        df["volume"] = df["volume"].round(0)
        idx = pd.DatetimeIndex(df.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        df.index = idx.normalize()
        out[s] = df.sort_index()
    return out


def save_bars(bars: Bars, path: Path = BARS_FILE) -> Path:
    """One long CSV (date, symbol, open, high, low, close, volume), gzip with a fixed mtime (same bytes on rerun)."""
    rows = []
    for s, df in sorted(round_bars(bars).items()):
        d = df.copy()
        d.insert(0, "symbol", s)
        d.insert(0, "date", d.index.strftime("%Y-%m-%d"))
        rows.append(d)
    table = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["date", "symbol"] + COLUMNS)
    table["volume"] = table["volume"].astype("int64")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = table.to_csv(index=False, float_format="%.2f", lineterminator="\n").encode()
    with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        gz.write(text)
    return path


def load_bars(path: Path = BARS_FILE) -> Bars:
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"No frozen bars at {path}. Run `python -m evals.build` first (needs market data keys).")
    table = pd.read_csv(path, dtype={"symbol": str})
    out: Bars = {}
    for s, d in table.groupby("symbol", sort=True):
        df = d.set_index(pd.DatetimeIndex(pd.to_datetime(d["date"])))[COLUMNS].astype(float).sort_index()
        df.index.name = None
        out[str(s)] = df
    return out


def load_manifest(path: Path = MANIFEST_FILE) -> dict:
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"No manifest at {path}. Run `python -m evals.build` first.")
    return json.loads(path.read_text())


def history_sessions(cfg: Config) -> int:
    return int(cfg.playbook.get("data", {}).get("history_sessions", 1800))


def window(bars: Bars, as_of: pd.Timestamp, sessions: int | None) -> Bars:
    """What a live run on `as_of` would have fetched: bars up to that close, the last `sessions` of them."""
    out = {}
    for s, df in bars.items():
        d = df[df.index <= as_of]
        if sessions:
            d = d.iloc[-sessions:]
        if len(d):
            out[s] = d
    return out


# --- the fixed starting state and the rebuilt day -------------------------------------------------------


def fresh_state(book: str, cfg: Config) -> BookState:
    """A flat book on the simulator with the playbook's starting cash."""
    st = BookState(book=book)
    st.sim = {"cash": float(cfg.playbook.get("simulation", {}).get("starting_cash", 100_000)), "positions": {}}
    return st


def sim_broker(cfg: Config, state: BookState, bars: Bars) -> SimBroker:
    """The same simulator the CLI builds for `--sim` (next-open fills, cost charged once by the ledger)."""
    return SimBroker(state.sim, risk.last_prices(bars), ledger.cost_model(cfg, state), cfg.asset_class,
                     bars=bars, fill_mode="next_open", cost_in_price=False)


def rebuild_day(book: str, cfg: Config, bars: Bars, as_of: pd.Timestamp, state_dir: Path):
    """Engine steps 1-10 for the fixed starting state (dry-run semantics: nothing is sent or saved)."""
    state = fresh_state(book, cfg)
    view = window(bars, as_of, history_sessions(cfg))
    return _prepare_day(book, cfg, view, sim_broker(cfg, state, view), as_of, state, Path(state_dir), dry_run=True)


def copy_day(day):
    """A private copy of a rebuilt day (the bars and config are shared, they are never modified)."""
    return copy.deepcopy(day, memo={id(day.bars): day.bars, id(day.cfg): day.cfg})
