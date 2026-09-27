"""Write each frozen day's session folder (Agent building guide rules 14-15).

    python -m evals.prepare --out DIR [--book claude|rules|both] [--samples 1] [--date YYYY-MM-DD ...]

For every manifest day the context is rebuilt from the frozen bars with the fixed starting state (a flat
book on the simulator) through `engine.prepare_book`, the same code a live `prepare` runs. The folders land
in DIR/<book>/pending/<date>/ (context.json, schema.json, instructions.md, plus eval.json with the day's
manifest row). Answer each one exactly as a live session would (decision_<k>.json or review_<k>.json, each
sample written independently), then score them with `python -m evals.check DIR`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from trader.config import Config, load_config
from trader.engine import prepare_book

from . import (BARS_FILE, EVAL_FILE, MANIFEST_FILE, Bars, fresh_state, history_sessions, load_bars, load_manifest,
               sim_broker, window)

BOOKS = ("claude", "rules")


def prepare_all(out_dir: Path, cfg: Config, bars: Bars, manifest: dict, *, book: str = "claude",
                samples: int = 1, dates: list[str] | None = None) -> list[dict]:
    """One pending folder per manifest day (and per book when book == "both"). Returns prepare_book's results."""
    out_dir = Path(out_dir)
    books = BOOKS if book == "both" else (book,)
    rows = [r for r in manifest["dates"] if not dates or r["date"] in dates]
    results = []
    for b in books:
        for row in rows:
            as_of = pd.Timestamp(row["date"])
            state = fresh_state(b, cfg)
            view = window(bars, as_of, history_sessions(cfg))
            res = prepare_book(b, cfg, view, sim_broker(cfg, state, view), as_of, out_dir, state=state,
                               samples=samples)
            if res["date"] != row["date"]:
                raise SystemExit(f"{row['date']}: the frozen bars have no session on that date (got {res['date']})")
            (Path(res["dir"]) / EVAL_FILE).write_text(json.dumps({**row, "book": b, "samples": res["samples"]},
                                                                  indent=2) + "\n")
            results.append(res)
    return results


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="python -m evals.prepare", description=__doc__.split("\n\n")[0])
    p.add_argument("--out", required=True, help="folder for the pending day folders (not the live state folder)")
    p.add_argument("--book", choices=("claude", "rules", "both"), default="claude")
    p.add_argument("--samples", type=int, default=1, help="independent answers wanted per day (guide rule 15)")
    p.add_argument("--date", action="append", default=None, help="only these manifest days (repeatable)")
    p.add_argument("--bars", default=str(BARS_FILE))
    p.add_argument("--manifest", default=str(MANIFEST_FILE))
    a = p.parse_args(argv)
    cfg = load_config()
    results = prepare_all(Path(a.out), cfg, load_bars(Path(a.bars)), load_manifest(Path(a.manifest)),
                          book=a.book, samples=a.samples, dates=a.date)
    for r in results:
        print(f"{r['book']} {r['date']}: {r['dir']}")
    n = results[0]["samples"] if results else a.samples
    print(f"{len(results)} day folder(s) written. In each, write "
          + " / ".join(f"{'decision' if b == 'claude' else 'review'}_1.json ... _{n}.json"
                       for b in (BOOKS if a.book == "both" else (a.book,)))
          + f" (independently), then run `python -m evals.check {a.out}`.")


if __name__ == "__main__":
    main()
