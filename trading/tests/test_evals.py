"""evals/: frozen days, the same context as a live prepare, and code-only scoring (guide rules 14-15)."""
import gzip
import json

import pandas as pd
import pytest

from conftest import make_bars
from evals import build, check, load_bars, load_manifest, prepare, round_bars, save_bars
from trader import decisions
from trader.session import example_file


@pytest.fixture(scope="module")
def world():
    from trader.config import load_config

    cfg = load_config()
    bars = round_bars({s: make_bars(n=900, seed=i + 1, drift=0.0005) for i, s in enumerate(cfg.data_symbols())})
    return cfg, bars


def upto(bars, d):
    return {s: df[df.index <= d] for s, df in bars.items()}


# --- frozen bars and the manifest ---------------------------------------------------------------------


def test_bars_round_trip_two_decimals(world, tmp_path):
    _, bars = world
    raw = {"SPY": make_bars(n=30, seed=3), "AAPL": make_bars(n=20, seed=4)}
    path = save_bars(raw, tmp_path / "bars.csv.gz")
    with gzip.open(path, "rt") as f:
        header = f.readline().strip()
        first = f.readline().strip().split(",")
    assert header == "date,symbol,open,high,low,close,volume"
    assert all(len(x.split(".")[1]) == 2 for x in first[2:6])
    back = load_bars(path)
    assert sorted(back) == ["AAPL", "SPY"] and len(back["SPY"]) == 30
    pd.testing.assert_frame_equal(back["SPY"], round_bars(raw)["SPY"], check_freq=False)
    assert save_bars(raw, tmp_path / "again.csv.gz").read_bytes() == path.read_bytes()  # same bytes on rerun


def _row(date, regime, control=False, b=(), c=()):
    return {"date": date, "regime": regime, "control": control, "b_entries": list(b), "c_entries": list(c),
            "d_entries": [], "data_problems": 0, "temperature_label": "neutral"}


def test_select_covers_every_label_controls_and_entries():
    days = pd.bdate_range("2018-01-02", periods=400, freq="5B")
    labels = build.LABELS
    rows = []
    for i, d in enumerate(days):
        lb = labels[i % 5]
        kind = i % 7
        rows.append(_row(d.date().isoformat(), lb, control=kind in (0, 3), b=["SPY"] if kind == 1 else (),
                         c=["NVDA"] if kind == 2 else ()))
    chosen, notes = build.select(rows, n=30)
    assert len(chosen) == 30 and len({r["date"] for r in chosen}) == 30
    assert [r["date"] for r in chosen] == sorted(r["date"] for r in chosen)
    for lb in labels:
        assert sum(r["regime"] == lb for r in chosen) >= 2
    assert sum(r["control"] for r in chosen) >= 8
    assert sum(bool(r["b_entries"]) for r in chosen) >= 5
    assert sum(bool(r["c_entries"]) for r in chosen) >= 5
    assert not notes
    assert build.select(rows, n=30) == (chosen, notes)  # deterministic
    years = {r["date"][:4] for r in chosen}
    assert len(years) >= 6  # spread over time, not bunched


def test_select_says_what_the_history_lacks():
    rows = [_row(f"2020-01-{d:02d}", "bull_calm", control=d % 2 == 0) for d in range(1, 29)]
    chosen, notes = build.select(rows, n=10)
    assert len(chosen) == 10
    assert any("bear" in n for n in notes) and any("B-entry" in n for n in notes)


def test_build_on_synthetic_bars(world, tmp_path):
    cfg, bars = world
    start = bars["SPY"].index[-120].date().isoformat()
    m = build.build(cfg, bars, start=start, n=4, every=30, out_dir=tmp_path)
    assert (tmp_path / "bars.csv.gz").exists() and (tmp_path / "manifest.json").exists()
    assert load_manifest(tmp_path / "manifest.json") == m
    assert len(m["dates"]) == 4 and m["scanned_days"] == 4
    assert set(m["symbols"]) == set(cfg.data_symbols())
    for r in m["dates"]:
        assert {"date", "regime", "control", "why"} <= set(r)
        assert r["regime"] in build.LABELS and isinstance(r["control"], bool) and r["why"]
        assert r["control"] == (not r["b_entries"] and not r["c_entries"] and not r["data_problems"])


# --- prepare -> answer -> check ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def prepared(world, tmp_path_factory):
    cfg, bars = world
    out = tmp_path_factory.mktemp("evals")
    d = bars["SPY"].index[-3]
    date = d.date().isoformat()
    manifest = {"dates": [{"date": date, "regime": "bull_calm", "control": True, "why": "test control day"}]}
    res = prepare.prepare_all(out, cfg, bars, manifest, book="both", samples=3)
    return cfg, bars, out, date, manifest, {r["book"]: r for r in res}


def test_prepare_writes_the_context_a_live_prepare_would(world, prepared, tmp_path):
    from evals import fresh_state, sim_broker, window
    from trader.engine import prepare_book

    cfg, bars, out, date, manifest, res = prepared
    folder = out / "claude" / "pending" / date
    assert {p.name for p in folder.iterdir()} >= {"context.json", "schema.json", "instructions.md", "eval.json"}
    ev = json.loads((folder / "eval.json").read_text())
    assert ev["control"] is True and ev["samples"] == 3
    ctx = json.loads((folder / "context.json").read_text())
    assert ctx["date"] == date and ctx["book"] == "claude" and ctx["simulated"] is True
    assert ctx["account"]["equity"] == pytest.approx(100_000)
    assert not ctx["positions"]  # the fixed flat starting state
    # the same engine call a live `prepare --sim` makes gives the same context
    st = fresh_state("claude", cfg)
    view = window(bars, pd.Timestamp(date), 1800)
    live = prepare_book("claude", cfg, view, sim_broker(cfg, st, view), pd.Timestamp(date), tmp_path, state=st,
                        samples=3)
    assert json.loads((tmp_path / "claude" / "pending" / date / "context.json").read_text()) == ctx
    assert live["date"] == date


def _good(book, date, k):
    d = example_file(book, date, k)
    d["meta"] = {"model": "test-model", "sample": k}
    d["journal_note"] = f"Sample {k}: nothing to change today."
    return d


def _eligible_b(cfg, bars, date):
    return sorted(decisions.eligibility(cfg, upto(bars, pd.Timestamp(date)), {"A": 1, "B": 1, "C": 1, "D": 1})["B"])[0]


def _write(folder, name, data):
    (folder / name).write_text(data if isinstance(data, str) else json.dumps(data))


def test_check_scores_a_good_and_a_bad_decision(prepared):
    cfg, bars, out, date, manifest, _ = prepared
    folder = out / "claude" / "pending" / date
    sym = _eligible_b(cfg, bars, date)
    bad = _good("claude", date, 2)
    bad["sleeve_weights"]["A"]["choice"] = "up"
    bad["actions"] = [
        {"symbol": "ZZZZ", "sleeve": "C", "size": "rule", "target_pct_equity": 0.0, "stop": "rule",
         "reason_code": "TREND_STRENGTHENING", "evidence": ["regime.label"], "prediction_id": "", "rationale": "",
         "event_date": ""},
        {"symbol": sym, "sleeve": "B", "size": "pct", "target_pct_equity": 0.5, "stop": "rule",
         "reason_code": "MEAN_REVERSION_SETUP", "evidence": [f"rule_signals.B.indicators[{sym}].rsi2"],
         "prediction_id": "p1", "rationale": "oversold", "event_date": ""},
    ]
    bad["predictions"] = [{"id": "p1", "symbol": sym, "horizon": 5, "direction": "above", "threshold_pct": 1.0,
                           "probability": 0.99, "linked_decision": f"action:B:{sym}"}]
    _write(folder, "decision_1.json", _good("claude", date, 1))
    _write(folder, "decision_2.json", bad)
    _write(folder, "decision_3.json", "{not json")
    rep = check.check_dir(out, cfg, bars, manifest, book="claude")
    day = rep["books"]["claude"]["days"][0]
    by = {s["file"]: s for s in day["samples"]}
    good = by["decision_1.json"]["checks"]
    assert all(v is not False for v in good.values())
    assert good["parses_clean"] and good["allowlist"] and good["no_risk_clip"] and good["control_quiet"]
    assert good["stops_below_price"] is None and good["predictions_valid"] is None  # nothing to check: n/a
    b = by["decision_2.json"]["checks"]
    assert b["allowlist"] is False and b["actions_accepted"] is False and b["control_quiet"] is False
    assert b["predictions_valid"] is False and b["no_risk_clip"] is False
    assert b["stops_below_price"] is True and b["parses_clean"] is True
    why = by["decision_2.json"]["why"]
    assert any("ZZZZ" in w for w in why["allowlist"]) and any("0.99" in w for w in why["predictions_valid"])
    assert any(sym in w for w in why["no_risk_clip"])
    # the unreadable file is a format failure, kept out of the scores
    assert [f["file"] for f in day["format_failures"]] == ["decision_3.json"] and day["missing"] == 0
    s = rep["books"]["claude"]["summary"]
    assert s["samples_scored"] == 2 and s["format_failures"] == 1 and s["api_failures"] == 0
    assert s["checks"]["allowlist"] == {"pass": 1, "fail": 1, "n/a": 0, "rate": 0.5}
    assert s["all_checks_pass_rate"] == 0.5 and s["control_quiet_rate"] == 0.5
    assert day["agreement"] and 0.0 <= day["agreement"]["agreement_rate"] <= 1.0
    assert day["agreement"]["identical_answers"] is False
    assert not day["context_drift"]
    assert (out / check.REPORT_FILE).exists()
    text = check.render(rep)
    assert "format failure" in text and "decision_2.json: failed" in text
    # guide rules 7 and 15: the report says which prompt, instructions, schema and model it scored
    v = rep["books"]["claude"]["versions"]
    assert v == {**check.current_versions("claude"), "prepared_prompt_versions": [v["prompt_version"]],
                 "models": v["models"], "prompt_changed_since_prepare": False}
    assert v["prompt_version"] and v["instructions_version"] and v["schema_version"] and v["context_schema"]
    assert v["models"] == sorted({s["model"] for s in day["samples"]})
    assert day["versions"]["prepared"]["prompt_version"] == v["prompt_version"]
    assert day["versions"]["scored"] == [{k: v[k] for k in check.VERSION_KEYS}]
    saved = json.loads((out / check.REPORT_FILE).read_text())
    assert saved["books"]["claude"]["versions"]["prompt_version"] == v["prompt_version"]
    assert f"prompt {v['prompt_version']}" in text and "prompt changed since prepare" not in text


def test_check_scores_reviews_and_counts_missing_answers(prepared):
    cfg, bars, out, date, manifest, _ = prepared
    folder = out / "rules" / "pending" / date
    bad = _good("rules", date, 2)
    bad["skip_entries"] = [{"symbol": "SPY", "sleeve": "A", "reason_code": "DATA_SUSPECT",
                            "evidence": ["data_problems"], "prediction_id": "q1", "event_date": "",
                            "verified": False}]
    _write(folder, "review_1.json", _good("rules", date, 1))
    _write(folder, "review_2.json", bad)
    rep = check.check_dir(out, cfg, bars, manifest, book="rules", write=False)
    day = rep["books"]["rules"]["days"][0]
    assert day["missing"] == 1  # 3 asked for, 2 written: an API/session failure, not a score
    by = {s["file"]: s["checks"] for s in day["samples"]}
    assert all(v is not False for v in by["review_1.json"].values())
    assert by["review_1.json"]["control_quiet"] is True
    b = by["review_2.json"]
    assert b["actions_accepted"] is False  # sleeve A can never be skipped (CL-7)
    assert b["control_quiet"] is False and b["predictions_valid"] is False
    assert b["stops_below_price"] is None and b["allowlist"] is True
    s = rep["books"]["rules"]["summary"]
    assert s["api_failures"] == 1 and s["samples_scored"] == 2


def test_check_flags_a_prompt_changed_since_prepare(prepared):
    cfg, bars, out, date, manifest, _ = prepared
    folder = out / "rules" / "pending" / date
    _write(folder, "review_1.json", _good("rules", date, 1))
    ctx = json.loads((folder / "context.json").read_text())
    ctx["prompt_version"] = "old-prompt"
    (folder / "context.json").write_text(json.dumps(ctx))
    rep = check.check_dir(out, cfg, bars, manifest, book="rules", write=False)
    v = rep["books"]["rules"]["versions"]
    assert v["prepared_prompt_versions"] == ["old-prompt"] and v["prompt_changed_since_prepare"] is True
    assert v["prompt_version"] == check.current_versions("rules")["prompt_version"] != "old-prompt"
    assert "prompt changed since prepare" in check.render(rep)


def test_wrong_date_is_a_format_failure(prepared):
    cfg, bars, out, date, manifest, _ = prepared
    folder = out / "rules" / "pending" / date
    for f in folder.glob("review_*.json"):
        f.unlink()
    _write(folder, "review_1.json", _good("rules", "2001-01-02", 1))
    rep = check.check_dir(out, cfg, bars, manifest, book="rules", write=False)
    day = rep["books"]["rules"]["days"][0]
    assert not day["samples"] and len(day["format_failures"]) == 1 and day["missing"] == 2
    assert rep["books"]["rules"]["summary"]["checks"]["allowlist"]["rate"] is None
