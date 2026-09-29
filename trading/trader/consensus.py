"""Combine several independent samples of one decision (guide 8) and measure how often they agree.

Claude's answers vary from run to run and temperature cannot be set, so each decision is sampled
several times. Code acts only on what a majority supports, using median sizes:
- combine_weights: per-sleeve median of the resolved sleeve weights.
- combine_resolved: per (sleeve, symbol) median target, metadata from a sample that chose it.
- combine_reviews: a skip or halve survives only with a strict majority.
- unanimous_pair: CL-15 (TEST FIRST) shadow: what "act only where two runs agree" would have done.

A sample that was asked for but came back invalid counts as "follow the rules" when the caller passes
`samples_requested`, so one valid sample out of three can never act alone.
Pure functions: the inputs are never modified.
"""
from __future__ import annotations

import copy
import math
from dataclasses import replace
from typing import Iterable

from . import decisions
from .models import Target
from .schemas import SKIP_CODES, Halve, Prediction, ResolvedDecision, ResolvedTarget, RulesReview, Skip

EPS = 1e-6  # two target shares closer than this are the same target
DIRECTION_EPS = 1e-4  # CL-15: a move smaller than 0.01% of equity counts as "hold"
MAX_PREDICTIONS = 3  # CL-5: 0-3 a day, used when neither max_predictions nor cfg is given
JOURNAL_MAX_SENTENCES = 5  # CL-4


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _k(sample, i: int) -> int:
    """The sample's number (1-based)."""
    k = getattr(sample, "sample", None)
    return k if isinstance(k, int) else i + 1


def _limits(cfg, max_predictions: int | None) -> tuple[int, int]:
    """(max predictions a day, max journal sentences): explicit value, else the policy, else CL-4/CL-5."""
    lim = (cfg.policy.get("claude_limits") or {}) if cfg is not None else {}
    n = max_predictions if max_predictions is not None else lim.get("max_predictions_per_day", MAX_PREDICTIONS)
    return max(0, int(n)), int(lim.get("journal_max_sentences", JOURNAL_MAX_SENTENCES))


def _missing(n: int, samples_requested: int | None, problems: list[str]) -> int:
    extra = max(0, int(samples_requested or 0) - n)
    if extra:
        problems.append(f"{n} valid sample(s) of {n + extra} requested: each missing one counts as "
                        "following the rules (guide 8)")
    return extra


def _middle(vals: list[float], ref: float | None) -> float:
    """Median; with an even count a change needs both middle values on the same side of `ref`.

    Otherwise (they straddle it) nothing has a majority and `ref` is kept. On the same side, the value
    closer to `ref` wins. Without `ref`, the lower middle value (never a size no sample chose).
    """
    vals = sorted(vals)
    n = len(vals)
    if n % 2:
        return vals[n // 2]
    a, b = vals[n // 2 - 1], vals[n // 2]
    if ref is None:
        return a
    if a < ref - EPS and b > ref + EPS:
        return ref
    return a if abs(a - ref) <= abs(b - ref) + EPS else b


# --- weights ---------------------------------------------------------------------------------------


def combine_weights(samples: list[dict[str, float]], reference: dict[str, float] | None = None, *,
                    samples_requested: int | None = None, cfg=None, promoted: Iterable[str] | None = (),
                    demoted: dict | None = None) -> dict[str, float]:
    """Guide 8: per-sleeve median of the samples' resolved weights.

    `reference` is the previous weights: with an even count a move needs a majority on one side of it
    (else the previous weight is kept), and a sample that is missing (or has no value for a sleeve,
    or was requested but invalid, with `samples_requested`) counts as "keep".
    Medians are taken sleeve by sleeve, so their sum can break the cash budget. With `cfg` the result
    goes through decisions.cap_weights (RISK-7, RISK-8, cash buffer); without it the caller must do that.
    """
    samples = list(samples or [])
    sleeves = list(dict.fromkeys(s for w in samples for s in (w or {})))
    extra = max(0, int(samples_requested or 0) - len(samples))
    out = {}
    for s in sleeves:
        ref = float(reference[s]) if reference and _finite(reference.get(s)) else None
        vals = [float(w[s]) for w in samples if w and _finite(w.get(s))]
        if not vals:
            continue
        if ref is not None:
            vals += [ref] * (len(samples) - len(vals) + extra)
        out[s] = float(_middle(vals, ref))
    if cfg is not None:
        out = decisions.cap_weights(cfg, out, promoted, demoted)
    return out


# --- predictions carried between samples ---------------------------------------------------------------


class _PredictionPool:
    """Predictions of the combined decision; ids stay unique (s<k>- prefix when two samples collide)."""

    def __init__(self) -> None:
        self.items: list[Prediction] = []
        self.origin: dict[str, tuple[int, str]] = {}  # pool id -> (sample position, id in that sample)

    def get(self, pid: str) -> Prediction | None:
        return next((p for p in self.items if p.id == pid), None)

    def add(self, pred: Prediction, i: int, k: int) -> str:
        """Add the prediction of the sample at position i (numbered k); return its id in the pool."""
        candidates = [pred.id, f"s{k}-{pred.id}"] + [f"s{k}-{pred.id}-{n}" for n in range(2, 100)]
        for pid in candidates:
            existing = self.get(pid)
            if existing is None:
                self.items.append(pred if pid == pred.id else pred.model_copy(update={"id": pid}))
                self.origin[pid] = (i, pred.id)
                return pid
            if self.origin[pid] == (i, pred.id) or _same_prediction(existing, pred):
                return pid
        raise ValueError(f"cannot find a free id for prediction {pred.id}")

    def select(self, max_n: int, linked: list[str], problems: list[str]) -> list[Prediction]:
        """CL-5: the linked predictions (they already fit the limit) first, then free ones while room is left."""
        free = [p.id for p in self.items if p.id not in linked]
        room = max(0, max_n - len(linked))
        if free[room:]:
            problems.append(f"predictions dropped over the daily limit of {max_n}: {', '.join(free[room:])}")
        return [self.get(pid) for pid in linked] + [self.get(pid) for pid in free[:room]]


def _same_prediction(a: Prediction, b: Prediction) -> bool:
    return a.model_dump(exclude={"id"}) == b.model_dump(exclude={"id"})


def _find(preds: list[Prediction], pid: str) -> Prediction | None:
    return next((p for p in preds if p.id == pid), None) if pid else None


def _over_limit(order: list[str], pid_of: dict[str, str], limit: int) -> tuple[list[str], set[str]]:
    """Linked prediction ids in priority order, and the ids that do not fit under the limit."""
    linked = list(dict.fromkeys(pid_of[key] for key in order if pid_of.get(key)))
    return linked[:limit], set(linked[limit:])


# --- Claude book: resolved targets ----------------------------------------------------------------------


def _as_rule(t: ResolvedTarget) -> ResolvedTarget:
    """What a sample that did not mention a key means: that key follows the rule."""
    return replace(t, pct=_num(t.rule_pct, t.current_pct), stop=t.rule_stop, reason_code="FOLLOW_RULE",
                   evidence=[], prediction_id="", rationale="", is_deviation=False, source="rule", sample=None)


def _key_table(samples: list[ResolvedDecision]) -> dict[str, list[ResolvedTarget]]:
    """key -> one target per sample (a missing key is filled in as 'follow the rule')."""
    keys = list(dict.fromkeys(key for s in samples for key in s.targets))
    table = {}
    for key in keys:
        template = next(s.targets[key] for s in samples if key in s.targets)
        base = next((s.targets[key] for s in samples if key in s.targets and s.targets[key].source == "rule"),
                    template)
        table[key] = [s.targets[key] if key in s.targets else _as_rule(base) for s in samples]
    return table


def _num(*values) -> float:
    """The first finite value (0.0 if none)."""
    return next((float(v) for v in values if _finite(v)), 0.0)


def _pct(t: ResolvedTarget) -> float:
    """A sample's target share; a missing or NaN share means 'follow the rule'."""
    return _num(t.pct, t.rule_pct, t.current_pct)


def _median_pct(targets: list[ResolvedTarget], extra: int = 0) -> float:
    """Median target share, `extra` missing samples voting for the rule.

    With an even count a deviation needs both middle values on the same side of the rule (a majority);
    then the one closer to the rule is used, and on a tie the one closer to the current holding.
    """
    rule, current = _num(targets[0].rule_pct), _num(targets[0].current_pct)
    vals = sorted([_pct(t) for t in targets] + [rule] * extra)
    n = len(vals)
    if n % 2:
        return vals[n // 2]
    a, b = vals[n // 2 - 1], vals[n // 2]
    if a < rule - EPS and b > rule + EPS:
        return rule
    return min((a, b), key=lambda v: (round(abs(v - rule) / EPS), round(abs(v - current) / EPS), v))


def _combined_stop(targets: list[ResolvedTarget], backers: list[int], pct: float) -> float | None:
    """Median of the stops of the samples that chose the combined size (the upper middle one when even).

    Every one of those stops already passed decisions' checks (never below the lot stop; for an
    increase never below the rule stop), so a stop picked from them keeps both. An increase is also
    floored at the rule stop here (CL-14), so a wider stop is impossible whatever the samples held.
    """
    stops = sorted(float(targets[i].stop) for i in backers if _finite(targets[i].stop))
    stop = stops[len(stops) // 2] if stops else None
    t0 = targets[backers[0]]
    if pct > _num(t0.current_pct) + EPS and _finite(t0.rule_stop):
        stop = float(t0.rule_stop) if stop is None else max(stop, float(t0.rule_stop))
    return stop


def _pick_meta(targets: list[ResolvedTarget], backers: list[int], pct: float, rep_i: int,
               samples: list[ResolvedDecision]) -> int:
    """The sample whose target supplies reason, evidence and prediction for the combined target.

    Among the samples that chose the combined size: the right source ("rule" when the combined size is
    the rule's, else "action"), then one whose prediction exists and is about this symbol, then the
    representative, then the lowest index.
    """
    wanted = "rule" if abs(pct - _num(targets[0].rule_pct)) <= EPS else "action"

    def rank(i: int) -> tuple:
        t = targets[i]
        pred = _find(samples[i].predictions, t.prediction_id)
        lost = t.source == "action" and bool(t.prediction_id) and pred is None
        return t.source != wanted, lost, not _about(pred, t.symbol), i != rep_i, i

    return min(backers, key=rank)


def _about(pred: Prediction | None, symbol: str) -> bool:
    """True unless the prediction exists and is about another symbol."""
    return pred is None or pred.symbol.strip().upper() == symbol.strip().upper()


def _representative(table: dict[str, list[ResolvedTarget]], combined: dict[str, float], n: int) -> int:
    """The sample closest to the combined decision (sum of |pct - combined| over keys); ties -> lowest index."""
    dist = [sum(abs(_pct(ts[i]) - combined[key]) for key, ts in table.items()) for i in range(n)]
    best = min(dist)
    return next(i for i, d in enumerate(dist) if d <= best + EPS)


def combine_resolved(samples: list[ResolvedDecision], weights: dict[str, float] | None = None, *,
                     max_predictions: int | None = None, samples_requested: int | None = None,
                     cfg=None) -> ResolvedDecision:
    """Guide 8: one ResolvedDecision from several samples, acting only on what a majority supports.

    For every key in any sample: pct = median across samples (a sample that did not mention the key, or
    that was requested but is missing, follows the rule); stop = median of the stops of the samples
    that chose that size, floored at the rule stop for an increase. Reason code, evidence, prediction and
    source come from a sample that chose the combined size (the representative when it did).
    Narrative fields and predictions come from the representative sample; a kept action's prediction is
    carried over from its own sample. A combined deviation whose prediction cannot be found, or does not
    fit under the daily limit (max_predictions, else cfg's policy, else 3; CL-5), follows the rule (CL-13).
    `weights` should be the final, capped weights; when None, the median of the samples' weights is used
    (capped through decisions.cap_weights only when `cfg` is given).
    """
    if not samples:
        raise ValueError("no samples to combine")
    n = len(samples)
    limit, _ = _limits(cfg, max_predictions)
    problems = [f"sample {_k(s, i)}: {p}" for i, s in enumerate(samples) for p in s.problems]
    extra = _missing(n, samples_requested, problems)
    table = _key_table(samples)
    combined_pct = {key: _median_pct(ts, extra) for key, ts in table.items()}
    rep_i = _representative(table, combined_pct, n)
    rep = samples[rep_i]
    pool = _PredictionPool()
    for p in rep.predictions:
        pool.add(p, rep_i, _k(rep, rep_i))

    targets: dict[str, ResolvedTarget] = {}
    support: dict[str, int] = {}
    for key, ts in table.items():
        pct = combined_pct[key]
        backers = [i for i, t in enumerate(ts) if abs(_pct(t) - pct) <= EPS]
        support[key] = len(backers)
        if not backers:  # no sample chose this size: it is the rule's (no majority for any change)
            targets[key] = _as_rule(next((t for t in ts if t.source == "rule"), ts[0]))
            continue
        i = _pick_meta(ts, backers, pct, rep_i, samples)
        t = replace(ts[i], pct=pct, stop=_combined_stop(ts, backers, pct), sample=_k(samples[i], i))
        if t.source == "action":
            pred = _find(samples[i].predictions, t.prediction_id)
            if pred is not None:
                t = replace(t, prediction_id=pool.add(pred, i, _k(samples[i], i)))
            elif t.is_deviation:
                problems.append(f"{key}: combined deviation has no prediction in sample {t.sample}; rule applies")
                t = _as_rule(t)
            elif t.prediction_id:
                t = replace(t, prediction_id="")
        targets[key] = t

    order = sorted(targets, key=lambda key: -support[key])  # stable: ties keep key order
    linked, over = _over_limit(order, {key: t.prediction_id for key, t in targets.items()}, limit)
    for key, t in targets.items():
        if t.prediction_id in over:
            if t.is_deviation:
                problems.append(f"{key}: its prediction is over the daily limit of {limit} (CL-5); rule applies")
                targets[key] = _as_rule(t)
            else:
                targets[key] = replace(t, prediction_id="")
    predictions = pool.select(limit, linked, problems)
    if weights is None:
        weights = combine_weights([s.weights for s in samples], cfg=cfg)
    unanimous = [key for key, ts in table.items() if max(map(_pct, ts)) - min(map(_pct, ts)) <= EPS]
    agreement = {
        "n": n,
        "samples_requested": n + extra,
        "keys": len(table),
        "unanimous_keys": len(unanimous),
        "agreement_rate": round(len(unanimous) / len(table), 4) if table else 1.0,
        "deviation_keys_combined": [key for key, t in targets.items() if t.is_deviation],
        "split": {key: [round(_pct(t), 6) for t in ts] for key, ts in table.items() if key not in unanimous},
        "representative": _k(rep, rep_i),
    }
    return copy.deepcopy(ResolvedDecision(
        weights=dict(weights),
        targets=targets,
        weight_reasons=_weight_reasons(samples, weights, rep),
        predictions=predictions,
        journal_note=rep.journal_note,
        market_view=rep.market_view,
        temperature_ack=rep.temperature_ack,
        likely_error=rep.likely_error.model_copy(),
        flags=list(rep.flags),
        problems=problems,
        sample=None,
        agreement=agreement,
    ))


def _weight_reasons(samples: list[ResolvedDecision], weights: dict[str, float], rep: ResolvedDecision) -> dict:
    """Per sleeve, the reason of a sample whose weight equals the combined weight (else the representative's)."""
    out = {}
    for s in dict.fromkeys(list(weights) + list(rep.weight_reasons)):
        source = next((x for x in samples if s in x.weight_reasons and _finite(x.weights.get(s))
                       and _finite(weights.get(s)) and abs(x.weights[s] - weights[s]) <= EPS), None)
        reason = (source or rep).weight_reasons.get(s)
        if reason is not None:
            out[s] = copy.deepcopy(reason)
    return out


# --- rules book: reviews ---------------------------------------------------------------------------------


def _item_key(item: Skip | Halve) -> str:
    """"skip:C:NVDA" (apply_review matches skips by sleeve and symbol) or "halve:B"."""
    if isinstance(item, Skip):
        return f"skip:{item.sleeve}:{item.symbol.strip().upper()}"
    return f"halve:{item.sleeve}"


def _skip_pred_ok(item: Skip | Halve, preds: list[Prediction]) -> bool:
    """A skip's prediction should be about the skipped symbol (a halve's may be about any symbol)."""
    return not isinstance(item, Skip) or _about(_find(preds, item.prediction_id), item.symbol)


def _clean_predictions(review: RulesReview, cfg, k: int, problems: list[str]) -> list[Prediction]:
    """With cfg, the same CL-5 cleaning apply_review does (allowlist, limit, ranges)."""
    if cfg is None:
        return list(review.predictions)
    log: list[str] = []
    preds = decisions.clean_predictions(review.predictions,
                                        max_n=int(cfg.policy["claude_limits"]["max_predictions_per_day"]),
                                        allowlist=cfg.allowlist(), log=log)
    problems += [f"sample {k}: {line}" for line in log]
    return preds


def _valid_items(review: RulesReview, preds: list[Prediction], k: int, *, ctx, allowed_codes, date: str,
                 problems: list[str]) -> dict[str, Skip | Halve]:
    """key -> the first valid item for that key, checked one by one exactly as decisions.apply_review does.

    Each item is offered a one-share increase in its own sleeve; it is valid when apply_review turns that
    into a veto. An invalid item (sleeve A, a code not allowed, a bad event date, bad evidence, no matching
    prediction) never votes.
    """
    base = review.model_copy(update={"predictions": preds, "skip_entries": [], "halve_sleeves": []})
    items: dict[str, Skip | Halve] = {}
    for item in list(review.skip_entries) + list(review.halve_sleeves):
        key = _item_key(item)
        if key in items:
            continue
        if isinstance(item, Skip):
            one, symbol = base.model_copy(update={"skip_entries": [item]}), item.symbol.strip().upper()
        else:
            one, symbol = base.model_copy(update={"halve_sleeves": [item]}), "*"
        log: list[str] = []
        _, vetoes = decisions.apply_review([Target(symbol=symbol, sleeve=item.sleeve, qty=1.0)], one, {}, log,
                                           ctx=ctx, allowed_codes=allowed_codes, date=date)
        if vetoes:
            items[key] = item
        else:
            problems += [f"sample {k}: {line}" for line in log] or [f"sample {k}: {key} is not valid"]
    return items


def combine_reviews(reviews: list[RulesReview], *, max_predictions: int | None = None,
                    samples_requested: int | None = None, cfg=None, ctx=None,
                    allowed_codes: Iterable[str] = SKIP_CODES, date: str = "") -> tuple[RulesReview, dict]:
    """Guide 8 for the rules book: a skip (per sleeve and symbol) or a halve (per sleeve) survives only
    with a strict majority of the samples (of `samples_requested` when fewer came back valid).

    Each sample's items are first checked with the same rules as decisions.apply_review (pass the same
    ctx and allowed_codes), so an invalid item never votes. A kept item and its prediction come from the
    representative sample when it voted for it, else from the first sample that did. At most
    max_predictions (else cfg's policy, else 3) predictions: a kept item whose prediction does not fit
    is dropped (the weakest-supported first). Narrative fields come from the representative sample (the
    one whose items are closest to the combined set), journal_note and the likely_error note trimmed (CL-4).
    """
    if not reviews:
        raise ValueError("no reviews to combine")
    n = len(reviews)
    limit, max_sentences = _limits(cfg, max_predictions)
    problems: list[str] = []
    extra = _missing(n, samples_requested, problems)
    codes = tuple(allowed_codes)
    preds = [_clean_predictions(r, cfg, _k(r, i), problems) for i, r in enumerate(reviews)]
    per_sample = [_valid_items(r, preds[i], _k(r, i), ctx=ctx, allowed_codes=codes, date=date or r.date,
                               problems=problems) for i, r in enumerate(reviews)]
    keys = list(dict.fromkeys(key for items in per_sample for key in items))
    votes = {key: [i for i, items in enumerate(per_sample) if key in items] for key in keys}
    majority = [key for key in keys if 2 * len(votes[key]) > n + extra]
    dist = [len(set(items) ^ set(majority)) for items in per_sample]
    rep_i = dist.index(min(dist))
    rep = reviews[rep_i]
    pool = _PredictionPool()
    for p in preds[rep_i]:
        pool.add(p, rep_i, _k(rep, rep_i))

    chosen: dict[str, Skip | Halve] = {}
    for key in majority:
        # the representative's item, unless another voter's prediction is about the skipped symbol and its is not
        i = min(votes[key], key=lambda j: (not _skip_pred_ok(per_sample[j][key], preds[j]), j != rep_i, j))
        item = per_sample[i][key]
        pred = _find(preds[i], item.prediction_id)
        if pred is None:  # never happens after the checks; CL-5 still wins
            problems.append(f"{key}: dropped, no prediction {item.prediction_id!r} in sample {_k(reviews[i], i)}")
            continue
        chosen[key] = item.model_copy(update={"prediction_id": pool.add(pred, i, _k(reviews[i], i))})
    order = sorted(chosen, key=lambda key: -len(votes[key]))
    linked, over = _over_limit(order, {key: x.prediction_id for key, x in chosen.items()}, limit)
    for key in order:
        if chosen[key].prediction_id in over:
            problems.append(f"{key}: dropped, its prediction is over the daily limit of {limit} (CL-5)")
            del chosen[key]
    predictions = pool.select(limit, linked, problems)
    kept = [key for key in majority if key in chosen]
    likely = rep.likely_error.model_copy(update={"note": decisions.trim_sentences(rep.likely_error.note, 1)})
    combined = rep.model_copy(update={
        "date": rep.date or next((r.date for r in reviews if r.date), ""),
        "skip_entries": [chosen[key] for key in kept if key.startswith("skip:")],
        "halve_sleeves": [chosen[key] for key in kept if key.startswith("halve:")],
        "predictions": predictions,
        "journal_note": decisions.trim_sentences(rep.journal_note, max_sentences),
        "likely_error": likely,
    }).model_copy(deep=True)
    unanimous = [key for key in keys if len(votes[key]) == n + extra]
    stats = {
        "n": n,
        "samples_requested": n + extra,
        "keys": len(keys),
        "unanimous_keys": len(unanimous),
        "agreement_rate": round(len(unanimous) / len(keys), 4) if keys else 1.0,
        "deviation_keys_combined": kept,
        "votes": {key: len(v) for key, v in votes.items()},
        "representative": _k(rep, rep_i),
        "problems": problems,
    }
    return combined, stats


# --- CL-15 (TEST FIRST): act only where two runs agree -------------------------------------------------------


def _direction(pct: float, current: float) -> str:
    if pct > current + DIRECTION_EPS:
        return "up"
    if pct < current - DIRECTION_EPS:
        return "down"
    return "hold"


def unanimous_pair(samples: list[ResolvedDecision], combined: ResolvedDecision | None = None) -> dict:
    """CL-15 shadow only: keys where samples 1 and 2 agree on the direction versus the current holding.

    CL-15 would act only on those keys; everywhere else it does nothing, which in the Claude book means
    following the rule (no deviation). With `combined`, `would_change` lists the keys where that differs
    from what the combined decision does. Never changes any target.
    """
    out = {"rule": "CL-15", "fires": False, "detail": {}, "would_change": []}
    if len(samples) < 2:
        out["detail"] = {"skipped": "needs at least 2 samples"}
        return out
    table = _key_table(samples[:2])
    agree, disagree = [], []
    for key, (t1, t2) in table.items():
        d1 = _direction(_pct(t1), _num(t1.current_pct))
        d2 = _direction(_pct(t2), _num(t2.current_pct))
        if d1 == d2:
            agree.append(key)
        else:
            disagree.append({"key": key, "sample_1": d1, "sample_2": d2})
    out["detail"] = {"pair": [_k(samples[0], 0), _k(samples[1], 1)], "keys": len(table), "agree_keys": agree,
                     "disagree": disagree, "on_disagreement": "rule",
                     "agreement_rate": round(len(agree) / len(table), 4) if table else 1.0}
    if combined is None:
        out["fires"] = bool(disagree)
        return out
    for key in dict.fromkeys(list(table) + list(combined.targets)):
        t = combined.targets.get(key)
        t1 = table[key][0] if key in table else t
        current = _num(t1.current_pct)
        if key in agree:
            cl15 = _direction(_pct(t1), current)
        else:  # the pair disagrees, or neither sample mentioned the key: the rule applies
            cl15 = _direction(_num(t1.rule_pct, t1.current_pct), current)
        actual = _direction(_pct(t), _num(t.current_pct)) if t is not None else "hold"
        if actual != cl15:
            out["would_change"].append({"key": key, "combined": actual, "cl15": cl15,
                                        "combined_pct": round(_pct(t), 6) if t is not None else None,
                                        "current_pct": round(current, 6)})
    out["fires"] = bool(out["would_change"])
    return out
