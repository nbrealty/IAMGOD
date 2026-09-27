"""Score the frozen days' decision and review files with code only (Agent building guide rules 14-15).

    python -m evals.check DIR [--book claude|rules] [--json]

For every DIR/<book>/pending/<date>/ written by `evals.prepare`, each sample file is read through the same
SessionAdvisor the live run uses and then replayed through the engine's own step 11 and the risk engine,
on the day rebuilt from the frozen bars. Checks per sample:

  parses_clean       the file parsed with no dropped item and no problem line
  allowlist          every symbol in actions, skips and predictions is on the allowlist
  stops_below_price  every stop Claude's actions produced sits below today's price (Claude book)
  no_risk_clip       the risk engine clipped nothing beyond what it clips on the plain rule plan
  actions_accepted   no action, weight move, skip or halve was refused by code
  control_quiet      on a control day: no actions, weight changes, deviations, skips or halves
  predictions_valid  predictions on the allowlist, inside the ranges and the daily limit, and every
                     deviation, skip or halve names one of them

A check that does not apply to a sample counts as n/a, not as a pass. Missing files (the session never
answered: an API or session failure) and files the reader rejects (format failures) are counted separately
and never enter the scores. With several samples per day, agreement across samples is the consensus
module's agreement rate. Only the journal text would need a model grader; that is not built.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from trader import engine
from trader.config import Config, load_config
from trader.llm import ClaudeError, jsonable
from trader.schemas import ClaudeDecision, RulesReview
from trader.session import SessionAdvisor, find_decision_files, prepared_samples

from . import BARS_FILE, EVAL_FILE, MANIFEST_FILE, Bars, copy_day, load_bars, rebuild_day

CHECKS = ("parses_clean", "allowlist", "stops_below_price", "no_risk_clip", "actions_accepted", "control_quiet",
          "predictions_valid")
REPORT_FILE = "eval_report.json"
EPS = 1e-6


class _Given:
    """An advisor that hands back already-parsed samples (so each file is read once)."""

    def __init__(self, samples: list, meta: dict):
        self.samples, self.meta = list(samples), dict(meta)

    def decide(self, ctx):
        return list(self.samples), dict(self.meta)

    def review_rules_plan(self, ctx):
        return list(self.samples), dict(self.meta)


@dataclass
class _Run:
    out: object
    result: object
    proposed: list
    clipped: dict = field(default_factory=dict)  # (sleeve, symbol) -> (proposed qty, qty after risk)
    prices: dict = field(default_factory=dict)


# --- replaying one answer through the engine ----------------------------------------------------------


def _replay(day0, book: str, advisor) -> _Run:
    """Engine step 11, the data block and the risk engine on a private copy of the rebuilt day."""
    d = copy_day(day0)
    out = engine._step(d, advisor)
    proposed = engine._block_bad_data(d, out.proposed)
    result = engine._risk(d, proposed, out.weights, book)
    after = {(t.sleeve, t.symbol): float(t.qty) for t in result.targets}
    clipped = {}
    for t in proposed:
        cur = engine._lot_qty(d.state.lots, t.sleeve, t.symbol)
        want = float(t.qty)
        if want <= cur + EPS:
            continue
        got = after.get((t.sleeve, t.symbol), cur)
        if got < want - max(EPS, 1e-4 * want):
            clipped[(t.sleeve, t.symbol)] = (want, got)
    return _Run(out, result, proposed, clipped)


def _baseline(day0, book: str) -> _Run:
    """The plain rules: the unreviewed plan (rules book) or an empty decision (Claude book)."""
    if book == "rules":
        return _replay(day0, book, None)
    empty = ClaudeDecision(date=day0.date, market_view="", journal_note="")
    return _replay(day0, book, _Given([empty], {"mode": "eval", "samples_requested": 1, "samples_valid": 1}))


def _new_clips(run: _Run, base: _Run) -> list[str]:
    """Clips the answer caused: a key clipped now that the plain rules did not ask for at this size."""
    out = []
    for key, (want, got) in run.clipped.items():
        b = base.clipped.get(key)
        if b is not None and want <= b[0] + max(EPS, 1e-4 * want):
            continue
        out.append(f"{key[0]}:{key[1]} {want:g} -> {got:g}")
    return out


# --- the checks ---------------------------------------------------------------------------------------


def _allow(ctx: dict) -> set[str]:
    return {str(s).upper() for s in ctx.get("allowlist", [])}


def _limits(ctx: dict, cfg: Config) -> int:
    lim = (ctx.get("limits") or {}).get("max_predictions_per_day")
    if lim is None:
        lim = cfg.policy.get("claude_limits", {}).get("max_predictions_per_day", 3)
    return int(lim)


def _prediction_check(ctx: dict, cfg: Config, preds: list, needs: list[tuple[str, str]]) -> tuple[bool | None, list]:
    """(pass/fail/None, why). `needs` = (item label, prediction_id) for every deviation, skip or halve."""
    if not preds and not needs:
        return None, []
    why = []
    allow = _allow(ctx)
    ids = [p.id for p in preds]
    if len(preds) > _limits(ctx, cfg):
        why.append(f"{len(preds)} predictions, the limit is {_limits(ctx, cfg)}")
    if len(set(ids)) != len(ids):
        why.append("duplicate prediction ids")
    for p in preds:
        if p.symbol.upper() not in allow:
            why.append(f"prediction {p.id}: {p.symbol} not on the allowlist")
        if not 0.05 <= p.probability <= 0.95:
            why.append(f"prediction {p.id}: probability {p.probability} outside [0.05, 0.95]")
        if not -50 <= p.threshold_pct <= 50:
            why.append(f"prediction {p.id}: threshold {p.threshold_pct}% outside [-50, 50]")
    for label, pid in needs:
        if not pid or pid not in ids:
            why.append(f"{label}: no matching prediction")
    return not why, why


def _score_decision(ctx, cfg, dec: ClaudeDecision, meta: dict, run: _Run, base: _Run, control: bool) -> dict:
    checks, why = {}, {}
    allow = _allow(ctx)
    out = run.out
    checks["parses_clean"] = not meta.get("problems")
    why["parses_clean"] = list(meta.get("problems") or [])

    bad = sorted({a.symbol for a in dec.actions if a.symbol.upper() not in allow}
                 | {p.symbol for p in dec.predictions if p.symbol.upper() not in allow})
    checks["allowlist"], why["allowlist"] = not bad, [f"{s} not on the allowlist" for s in bad]

    prices = run.prices
    action_keys = {(a["key"].split(":", 1)[0], a["key"].split(":", 1)[1]) for a in (out.claude or {}).get("actions", [])}
    stops = []
    for t in run.proposed:
        if (t.sleeve, t.symbol) not in action_keys or float(t.qty) <= EPS:
            continue
        price = prices.get(t.symbol)
        if t.sleeve == "A" and t.stop is None:
            continue
        if t.stop is None or price is None or not float(t.stop) < price:
            stops.append(f"{t.sleeve}:{t.symbol} stop {t.stop} vs price {price}")
    checks["stops_below_price"] = (not stops) if action_keys else None
    why["stops_below_price"] = stops

    clips = _new_clips(run, base)
    checks["no_risk_clip"], why["no_risk_clip"] = not clips, clips

    asked = bool(dec.actions) or any(getattr(dec.sleeve_weights, s).choice != "keep" for s in "ABCD")
    problems = [p for s in out.samples for p in s.get("problems", [])]
    if out.error:
        problems.append(f"engine: {out.error}")
    checks["actions_accepted"] = (not problems) if asked or out.error else None
    why["actions_accepted"] = problems

    if control:
        noisy = [f"action {a.sleeve}:{a.symbol} {a.size} {a.reason_code}" for a in dec.actions
                 if not (a.size == "rule" and a.reason_code == "FOLLOW_RULE")]
        noisy += [f"weight {s} changed" for s in ((out.weight_row or {}).get("changed") or [])]
        noisy += [f"deviation {r.get('sleeve')}:{r.get('symbol')}" for r in (out.deviations or [])]
        checks["control_quiet"], why["control_quiet"] = not noisy, noisy
    else:
        checks["control_quiet"], why["control_quiet"] = None, []

    needs = [(f"action {a.sleeve}:{a.symbol}", a.prediction_id) for a in dec.actions if a.reason_code != "FOLLOW_RULE"]
    checks["predictions_valid"], why["predictions_valid"] = _prediction_check(ctx, cfg, dec.predictions, needs)
    return {"checks": checks, "why": {k: v for k, v in why.items() if v},
            "deviations": len(out.deviations or []), "actions": len(dec.actions),
            "signature": sorted(f"{a.sleeve}:{a.symbol}:{a.size}" for a in dec.actions)
            + sorted(f"w{s}:{getattr(dec.sleeve_weights, s).choice}" for s in "ABCD"
                     if getattr(dec.sleeve_weights, s).choice != "keep")}


def _score_review(ctx, cfg, rev: RulesReview, meta: dict, run: _Run, base: _Run, control: bool) -> dict:
    checks, why = {}, {}
    allow = _allow(ctx)
    out = run.out
    checks["parses_clean"] = not meta.get("problems")
    why["parses_clean"] = list(meta.get("problems") or [])

    bad = sorted({k.symbol for k in rev.skip_entries if k.symbol.upper() not in allow}
                 | {p.symbol for p in rev.predictions if p.symbol.upper() not in allow})
    checks["allowlist"], why["allowlist"] = not bad, [f"{s} not on the allowlist" for s in bad]
    checks["stops_below_price"] = None  # a review never sets a stop

    clips = _new_clips(run, base)
    checks["no_risk_clip"], why["no_risk_clip"] = not clips, clips

    vetoes = out.vetoes or []
    refused = [f"skip {k.sleeve}:{k.symbol} ({k.reason_code}) refused" for k in rev.skip_entries
               if not any(v["symbol"].upper() == k.symbol.upper() and v["sleeve"] == k.sleeve
                          and v["fraction"] >= 1.0 for v in vetoes)]
    refused += [f"halve {h.sleeve} ({h.reason_code}) refused or had nothing to halve" for h in rev.halve_sleeves
                if not any(v["sleeve"] == h.sleeve and v["fraction"] < 1.0 for v in vetoes)]
    if out.error:
        refused.append(f"engine: {out.error}")
    asked = bool(rev.skip_entries or rev.halve_sleeves)
    checks["actions_accepted"] = (not refused) if asked or out.error else None
    why["actions_accepted"] = refused

    if control:
        noisy = [f"skip {k.sleeve}:{k.symbol}" for k in rev.skip_entries]
        noisy += [f"halve {h.sleeve}" for h in rev.halve_sleeves]
        checks["control_quiet"], why["control_quiet"] = not noisy, noisy
    else:
        checks["control_quiet"], why["control_quiet"] = None, []

    needs = [(f"skip {k.symbol}", k.prediction_id) for k in rev.skip_entries]
    needs += [(f"halve {h.sleeve}", h.prediction_id) for h in rev.halve_sleeves]
    checks["predictions_valid"], why["predictions_valid"] = _prediction_check(ctx, cfg, rev.predictions, needs)
    return {"checks": checks, "why": {k: v for k, v in why.items() if v}, "vetoes": len(vetoes),
            "signature": sorted(f"skip:{k.sleeve}:{k.symbol}" for k in rev.skip_entries)
            + sorted(f"halve:{h.sleeve}" for h in rev.halve_sleeves)}


# --- one day, one book ------------------------------------------------------------------------------


def check_day(folder: Path, book: str, cfg: Config, bars: Bars, manifest_rows: dict, work_dir: Path) -> dict:
    date = folder.name
    info = {}
    ef = folder / EVAL_FILE
    if ef.exists():
        info = json.loads(ef.read_text())
    info = {**manifest_rows.get(date, {}), **info}
    control = bool(info.get("control", False))
    expected = prepared_samples(folder) or int(info.get("samples") or 1)
    files = find_decision_files(book, date, folder.parent.parent.parent)

    day0 = rebuild_day(book, cfg, bars, pd.Timestamp(date), work_dir)
    saved = folder / "context.json"
    drift = saved.exists() and json.loads(saved.read_text()) != jsonable(day0.context)
    base = _baseline(day0, book)
    base_prices = {s: float(p) for s, p in day0.prices.items() if p is not None}
    role = "review" if book == "rules" else "decide"

    samples, format_failures, valid, metas = [], [], [], []
    for f in files:
        adv = SessionAdvisor([f], date, cfg, samples=1)
        try:
            parsed, meta = getattr(adv, "review_rules_plan" if book == "rules" else "decide")(day0.context)
        except ClaudeError as e:
            meta = getattr(e, "meta", None) or {}
            format_failures.append({"file": f.name, "why": list(meta.get("problems") or [str(e)])})
            continue
        run = _replay(day0, book, _Given(parsed, meta))
        run.prices = base_prices
        score = (_score_review if book == "rules" else _score_decision)(
            day0.context, cfg, parsed[0], meta, run, base, control)
        samples.append({"file": f.name, "model": (meta.get("models") or ["unknown"])[0], **score})
        valid.append(parsed[0])
        metas.append(meta)

    agreement = None
    if len(valid) >= 2:
        meta = {"mode": "session", "role": role, "samples_requested": max(expected, len(valid)),
                "samples_valid": len(valid), "problems": []}
        agreement = dict(_replay(day0, book, _Given(valid, meta)).out.agreement or {})
        sigs = [json.dumps(s["signature"]) for s in samples]
        agreement["identical_answers"] = len(set(sigs)) == 1
    return {
        "date": date, "book": book, "regime": info.get("regime"), "control": control, "why": info.get("why"),
        "samples_expected": expected, "files": len(files),
        "missing": max(0, expected - len(files)),
        "format_failures": format_failures,
        "context_drift": bool(drift),
        "samples": samples, "agreement": agreement,
    }


# --- the whole folder -------------------------------------------------------------------------------


def _rate(p: int, f: int) -> float | None:
    return round(p / (p + f), 4) if p + f else None


def summarize(days: list[dict]) -> dict:
    samples = [s for d in days for s in d["samples"]]
    checks = {}
    for name in CHECKS:
        vals = [s["checks"].get(name) for s in samples]
        p, f = sum(v is True for v in vals), sum(v is False for v in vals)
        checks[name] = {"pass": p, "fail": f, "n/a": sum(v is None for v in vals), "rate": _rate(p, f)}
    all_ok = [all(v is not False for v in s["checks"].values()) for s in samples]
    ctrl = [s for d in days if d["control"] for s in d["samples"]]
    rates = [d["agreement"]["agreement_rate"] for d in days
             if d.get("agreement") and d["agreement"].get("agreement_rate") is not None]
    return {
        "days": len(days),
        "control_days": sum(1 for d in days if d["control"]),
        "samples_expected": sum(d["samples_expected"] for d in days),
        "samples_scored": len(samples),
        # kept out of the scores (guide rule 15)
        "api_failures": sum(d["missing"] for d in days),
        "format_failures": sum(len(d["format_failures"]) for d in days),
        "context_drift_days": [d["date"] for d in days if d["context_drift"]],
        "checks": checks,
        "all_checks_pass_rate": round(sum(all_ok) / len(all_ok), 4) if all_ok else None,
        "control_quiet_rate": _rate(sum(s["checks"]["control_quiet"] is True for s in ctrl),
                                    sum(s["checks"]["control_quiet"] is False for s in ctrl)),
        "agreement": {"days": len(rates), "mean_rate": round(sum(rates) / len(rates), 4) if rates else None,
                      "identical_days": sum(1 for d in days if (d.get("agreement") or {}).get("identical_answers"))},
    }


def check_dir(out_dir: Path, cfg: Config | None = None, bars: Bars | None = None, manifest: dict | None = None,
              book: str | None = None, write: bool = True) -> dict:
    out_dir = Path(out_dir)
    cfg = cfg or load_config()
    bars = bars if bars is not None else load_bars(BARS_FILE)
    if manifest is None:
        manifest = json.loads(MANIFEST_FILE.read_text()) if MANIFEST_FILE.exists() else {"dates": []}
    rows = {r["date"]: r for r in manifest.get("dates", [])}
    books = [book] if book else [b for b in ("claude", "rules") if (out_dir / b / "pending").is_dir()]
    report = {"dir": str(out_dir), "books": {}}
    with tempfile.TemporaryDirectory() as tmp:
        for b in books:
            folders = sorted(p for p in (out_dir / b / "pending").iterdir()
                             if p.is_dir() and (p / "context.json").exists()) \
                if (out_dir / b / "pending").is_dir() else []
            days = [check_day(f, b, cfg, bars, rows, Path(tmp)) for f in folders]
            report["books"][b] = {"summary": summarize(days), "days": days}
    if write:
        (out_dir / REPORT_FILE).write_text(json.dumps(jsonable(report), indent=2) + "\n")
    return report


def render(report: dict) -> str:
    lines = []
    for b, r in report["books"].items():
        s = r["summary"]
        lines.append(f"{b} book: {s['days']} day(s) ({s['control_days']} control), "
                     f"{s['samples_scored']} of {s['samples_expected']} sample(s) scored")
        lines.append(f"  kept out of the scores: {s['api_failures']} missing answer(s) (API/session failures), "
                     f"{s['format_failures']} format failure(s)")
        for name, c in s["checks"].items():
            rate = "n/a" if c["rate"] is None else f"{c['rate']:.0%}"
            lines.append(f"  {name:<18} {rate:>5}  ({c['pass']} pass, {c['fail']} fail, {c['n/a']} n/a)")
        allp = s["all_checks_pass_rate"]
        lines.append(f"  every check passed: {'n/a' if allp is None else f'{allp:.0%}'} of scored samples")
        ag = s["agreement"]
        if ag["days"]:
            lines.append(f"  agreement across samples: {ag['mean_rate']:.0%} of keys on {ag['days']} day(s); "
                         f"identical answers on {ag['identical_days']} day(s)")
        if s["context_drift_days"]:
            lines.append(f"  note: the context changed since prepare on {len(s['context_drift_days'])} day(s) "
                         "(prompt, config or code changed): re-run evals.prepare and answer again")
        for d in r["days"]:
            for smp in d["samples"]:
                fails = [k for k, v in smp["checks"].items() if v is False]
                if fails:
                    lines.append(f"  {d['date']} {smp['file']}: failed {', '.join(fails)}")
                    for k in fails:
                        for w in smp["why"].get(k, [])[:3]:
                            lines.append(f"      {k}: {w}")
            for ff in d["format_failures"]:
                lines.append(f"  {d['date']} {ff['file']}: format failure: {'; '.join(ff['why'][:2])}")
    lines.append("journal text is not scored here (it would need a model grader against a fixed rubric)")
    return "\n".join(lines)


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="python -m evals.check", description=__doc__.split("\n\n")[0])
    p.add_argument("dir", help="the folder given to evals.prepare --out")
    p.add_argument("--book", choices=("claude", "rules"), default=None)
    p.add_argument("--bars", default=str(BARS_FILE))
    p.add_argument("--manifest", default=str(MANIFEST_FILE))
    p.add_argument("--json", action="store_true", help="print the full report as JSON")
    a = p.parse_args(argv)
    manifest = json.loads(Path(a.manifest).read_text()) if Path(a.manifest).exists() else {"dates": []}
    report = check_dir(Path(a.dir), load_config(), load_bars(Path(a.bars)), manifest, a.book)
    print(json.dumps(jsonable(report), indent=2) if a.json else render(report))
    print(f"full report: {Path(a.dir) / REPORT_FILE}")


if __name__ == "__main__":
    main()
