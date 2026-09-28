"""Options lab (lab/options_lab.py): offline checks that need no Alpaca connection."""
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location("options_lab", Path(__file__).resolve().parent.parent / "lab" / "options_lab.py")
options_lab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(options_lab)


def _bare_lab(tmp_path):
    lab = options_lab.Lab.__new__(options_lab.Lab)  # skip __init__: no network clients
    lab.dir, lab.trades, lab.done_checkpoints, lab.dry = tmp_path, [], set(), True
    lab.book_path = tmp_path / "trades.json"
    return lab


def test_entry_logging_accepts_a_signal_kind(tmp_path):
    """28 Sept 2026: log(kind, ..., kind=...) raised TypeError and lost the 10:15 checkpoint."""
    lab = _bare_lab(tmp_path)
    lab.signal = lambda sym: ("put_credit", {"spot": 500.0, "move_60m": 0.1})
    lab.build = lambda sym, kind, spot: (None, "no strike passed the quote filter")
    lab.try_entry("10:15")
    rows = [json.loads(ln) for ln in (tmp_path / "journal.jsonl").read_text().splitlines()]
    assert [r["event"] for r in rows] == ["signal", "no_trade", "signal", "no_trade"]
    assert rows[0]["kind"] == "put_credit" and rows[1]["why"] == "no strike passed the quote filter"
    assert lab.trades == []
