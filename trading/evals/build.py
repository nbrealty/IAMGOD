"""Pick and freeze the evaluation days (Agent building guide rule 14).

    python -m evals.build [--start 2018-01-01] [--end YYYY-MM-DD] [--n 30] [--every 5] [--offline]

Fetches every data symbol from 2016 with `AlpacaData.history` (market data only), rounds to 2 decimals and
saves `bars.csv.gz`; then replays candidate days (every `--every` sessions) from those frozen bars with the
fixed starting state and picks `--n` days that cover every regime label, at least 8 control days and days with
B entries and C breakouts. `--offline` skips the download and re-picks from the existing bars file.

A control day has no planned B, C or D entries and no data problems (a symbol that was not listed yet, shown
as "no data", does not count: that is history, not bad data). The flat starting book always buys its
sleeve A allocation, so "no rule trades" means no entries in the sleeves Claude may review or change; on such a
day the right answer is an empty decision (Claude book) or an empty review (rules book).
"""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from trader.config import Config, load_config

from . import BARS_FILE, LABELS, MANIFEST_FILE, Bars, history_sessions, load_bars, rebuild_day, save_bars

HISTORY_START = "2016-01-01"
MIN_CONTROL = 8
MIN_PER_LABEL = 2
MIN_B = 5
MIN_C = 5
CONTROL_DEFINITION = ("no planned B, C or D entries and no data problems for a flat starting book "
                      "(sleeve A still buys its allocation; a symbol not listed yet is not a data problem); "
                      "Claude should change nothing")


# --- scanning candidate days ----------------------------------------------------------------------


def candidate_dates(bars: Bars, benchmark: str, start, end, every: int = 5, min_history: int = 260) -> list:
    """Every `every`-th benchmark session in [start, end] that has at least `min_history` sessions before it."""
    idx = bars[benchmark].index
    ok = [i for i, d in enumerate(idx) if i >= min_history and pd.Timestamp(start) <= d <= pd.Timestamp(end)]
    return [idx[i] for i in ok[::max(1, int(every))]]


def scan_day(cfg: Config, bars: Bars, as_of: pd.Timestamp, state_dir: Path) -> dict:
    """One candidate day through the engine's steps 1-10 (rules book, flat starting state)."""
    day = rebuild_day("rules", cfg, bars, as_of, state_dir)
    inc = day.context.get("planned_increases", [])
    by = {s: sorted({p["symbol"] for p in inc if p.get("sleeve") == s}) for s in ("B", "C", "D")}
    # A symbol that was not listed yet (UBER before 2019, LIN before late 2018) is history, not a data problem.
    unlisted = sorted(s for s, df in bars.items() if len(df) and df.index[0] > as_of)
    problems = [p for p in day.problems if not any(p.startswith(f"{s}: no data") for s in unlisted)]
    return {
        "date": day.date,
        "regime": day.regime.label,
        "temperature_label": day.regime.temperature_label,
        "b_entries": by["B"], "c_entries": by["C"], "d_entries": by["D"],
        "data_problems": len(problems),
        "not_listed_yet": [s for s in unlisted if s in day.context.get("allowlist", [])],
        "control": not inc and not problems,
    }


def scan(cfg: Config, bars: Bars, dates: list, progress=None) -> list[dict]:
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, d in enumerate(dates):
            rows.append(scan_day(cfg, bars, pd.Timestamp(d), Path(tmp)))
            if progress:
                progress(i + 1, len(dates), rows[-1])
    return rows


# --- choosing the days ----------------------------------------------------------------------------------


def _spread_pick(pool: list[dict], chosen: list[dict]) -> dict | None:
    """The candidate farthest (in days) from every day already chosen; ties go to the earliest. Deterministic."""
    if not pool:
        return None
    taken = [pd.Timestamp(r["date"]) for r in chosen]
    if not taken:
        return pool[len(pool) // 2]

    def gap(r):
        d = pd.Timestamp(r["date"])
        return min(abs((d - t).days) for t in taken)

    best = max(gap(r) for r in pool)
    return next(r for r in pool if gap(r) == best)


def select(rows: list[dict], n: int = 30, min_control: int = MIN_CONTROL, min_per_label: int = MIN_PER_LABEL,
           min_b: int = MIN_B, min_c: int = MIN_C) -> tuple[list[dict], list[str]]:
    """Pick `n` days: every regime label (one control and one active day each when they exist), then enough
    control days, B-entry days and C-breakout days, then the rest spread over time. Returns (days sorted by
    date, notes on anything the history could not supply)."""
    rows = sorted(rows, key=lambda r: r["date"])
    chosen: list[dict] = []
    notes: list[str] = []

    def free(pred):
        dates = {r["date"] for r in chosen}
        return [r for r in rows if r["date"] not in dates and pred(r)]

    def take(pred, count, what, quiet=False):
        got = 0
        while got < count and len(chosen) < n:
            r = _spread_pick(free(pred), chosen)
            if r is None:
                if not quiet:
                    notes.append(f"only {got} more {what} available (wanted {count})")
                return
            chosen.append(r)
            got += 1

    for label in LABELS:
        have = [r for r in rows if r["regime"] == label]
        if not have:
            notes.append(f"no candidate day has the regime label {label}")
            continue
        take(lambda r, lb=label: r["regime"] == lb and r["control"], 1, "", quiet=True)
        need = max(0, min_per_label - sum(1 for r in chosen if r["regime"] == label))
        take(lambda r, lb=label: r["regime"] == lb and not r["control"], need, "", quiet=True)
        need = max(0, min_per_label - sum(1 for r in chosen if r["regime"] == label))
        if need:
            take(lambda r, lb=label: r["regime"] == lb, need, f"{label} day")

    take(lambda r: r["control"], max(0, min_control - sum(r["control"] for r in chosen)), "control day(s)")
    take(lambda r: bool(r["b_entries"]), max(0, min_b - sum(bool(r["b_entries"]) for r in chosen)),
         "B-entry day(s)")
    take(lambda r: bool(r["c_entries"]), max(0, min_c - sum(bool(r["c_entries"]) for r in chosen)),
         "C-breakout day(s)")
    take(lambda r: bool(r["b_entries"] or r["c_entries"]), n - len(chosen), "day(s) with entries")
    take(lambda r: not r["control"], n - len(chosen), "active day(s)")
    take(lambda r: True, n - len(chosen), "day(s)")
    return sorted(chosen, key=lambda r: r["date"]), notes


def why(row: dict) -> str:
    parts = [f"regime {row['regime']}, temperature {row.get('temperature_label', 'unknown')}"]
    if row["control"]:
        parts.append("control: no B/C/D entries and clean data, Claude should change nothing")
    if row["b_entries"]:
        parts.append("B entries: " + ", ".join(row["b_entries"]))
    if row["c_entries"]:
        parts.append("C breakouts: " + ", ".join(row["c_entries"]))
    if row.get("d_entries"):
        parts.append("D entries: " + ", ".join(row["d_entries"]))
    if row.get("not_listed_yet"):
        parts.append("not listed yet (shown as 'no data'): " + ", ".join(row["not_listed_yet"]))
    if row.get("data_problems"):
        parts.append(f"{row['data_problems']} data problem(s)")
    if len(parts) == 1:
        parts.append("no B/C/D entries but data problems (not a control day)")
    return "; ".join(parts)


def manifest(cfg: Config, bars: Bars, chosen: list[dict], notes: list[str], *, scanned: int, every: int) -> dict:
    first = min(df.index[0] for df in bars.values()).date().isoformat()
    last = max(df.index[-1] for df in bars.values()).date().isoformat()
    counts = {lb: sum(1 for r in chosen if r["regime"] == lb) for lb in LABELS}
    return {
        "version": 1,
        "bars_file": BARS_FILE.name,
        "bars_start": first, "bars_end": last,
        "symbols": sorted(bars),
        "history_sessions": history_sessions(cfg),
        "starting_state": "flat book on the simulator, playbook simulation.starting_cash",
        "control_definition": CONTROL_DEFINITION,
        "scanned_days": scanned, "scan_every_sessions": every,
        "summary": {"days": len(chosen), "control": sum(1 for r in chosen if r["control"]),
                    "b_entry_days": sum(1 for r in chosen if r["b_entries"]),
                    "c_breakout_days": sum(1 for r in chosen if r["c_entries"]), "by_regime": counts},
        "notes": notes,
        "dates": [{"date": r["date"], "regime": r["regime"], "control": bool(r["control"]), "why": why(r),
                   "temperature_label": r.get("temperature_label"), "b_entries": r["b_entries"],
                   "c_entries": r["c_entries"], "data_problems": r.get("data_problems", 0),
                   "not_listed_yet": r.get("not_listed_yet", [])} for r in chosen],
    }


def build(cfg: Config, bars: Bars, *, start="2018-01-01", end=None, n: int = 30, every: int = 5,
          out_dir: Path | None = None, progress=None) -> dict:
    """Freeze `bars` (rounded) and pick the days from the frozen copy. Returns the manifest (also written)."""
    bars_path = (Path(out_dir) / BARS_FILE.name) if out_dir else BARS_FILE
    manifest_path = (Path(out_dir) / MANIFEST_FILE.name) if out_dir else MANIFEST_FILE
    save_bars(bars, bars_path)
    frozen = load_bars(bars_path)  # pick from exactly what the evals will replay
    bench = cfg.playbook["regime"]["benchmark"]
    end = end or frozen[bench].index[-1]
    dates = candidate_dates(frozen, bench, start, end, every)
    rows = scan(cfg, frozen, dates, progress)
    chosen, notes = select(rows, n)
    m = manifest(cfg, frozen, chosen, notes, scanned=len(rows), every=every)
    manifest_path.write_text(json.dumps(m, indent=2) + "\n")
    return m


# --- CLI --------------------------------------------------------------------------------------------------


def _fetch(cfg: Config, end: str) -> Bars:
    from trader.data import AlpacaData

    try:
        data = AlpacaData.from_env(cfg)
    except Exception as e:
        raise SystemExit(f"Market data is not set up: {e}")
    print(f"fetching {len(cfg.data_symbols())} symbols {HISTORY_START} -> {end} (market data only)")
    bars = data.history(cfg.data_symbols(), HISTORY_START, end)
    print(f"feed {data.feed_used or 'unknown'}; {len(bars)} symbols")
    for note in data.notes:
        print(f"  data note: {note}")
    missing = sorted(set(cfg.data_symbols()) - set(bars))
    if missing:
        print(f"  no bars for: {', '.join(missing)}")
    return bars


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="python -m evals.build", description=__doc__.split("\n\n")[0])
    p.add_argument("--start", default="2018-01-01", help="first candidate day")
    p.add_argument("--end", default=None, help="last bar date to freeze (default: yesterday)")
    p.add_argument("--n", type=int, default=30, help="how many days to pick")
    p.add_argument("--every", type=int, default=5, help="scan every N-th session")
    p.add_argument("--offline", action="store_true", help="re-pick from the existing bars.csv.gz")
    a = p.parse_args(argv)
    cfg = load_config()
    end = a.end or (date.today() - timedelta(days=1)).isoformat()
    bars = load_bars(BARS_FILE) if a.offline else _fetch(cfg, end)
    t0 = time.time()

    def progress(i, total, row):
        if i % 25 == 0 or i == total:
            print(f"  scanned {i}/{total} days ({time.time() - t0:.0f}s), last {row['date']} {row['regime']}")

    m = build(cfg, bars, start=a.start, end=a.end, n=a.n, every=a.every, progress=progress)
    s = m["summary"]
    print(f"wrote {BARS_FILE} and {MANIFEST_FILE}")
    print(f"{s['days']} days: {s['control']} control, {s['b_entry_days']} with B entries, "
          f"{s['c_breakout_days']} with C breakouts; by regime {s['by_regime']}")
    for note in m["notes"]:
        print(f"  note: {note}")


if __name__ == "__main__":
    main()
