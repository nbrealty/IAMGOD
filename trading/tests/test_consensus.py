"""Guide 8 consensus (majority, median sizes) and the CL-15 shadow. Synthetic samples only."""
import copy
import math
from dataclasses import replace

import pytest

from trader import decisions
from trader.consensus import combine_resolved, combine_reviews, combine_weights, unanimous_pair
from trader.models import Target
from trader.schemas import (
    Halve,
    LikelyError,
    Prediction,
    ResolvedDecision,
    ResolvedTarget,
    RulesReview,
    Skip,
)


def pred(pid, symbol="NVDA", prob=0.6, linked="action:C:NVDA"):
    return Prediction(id=pid, symbol=symbol, horizon=20, direction="above", threshold_pct=0.0,
                      probability=prob, linked_decision=linked)


def rule_t(sleeve, symbol, rule_pct, current_pct=0.0, rule_stop=None):
    return ResolvedTarget(sleeve=sleeve, symbol=symbol, pct=rule_pct, stop=rule_stop, rule_pct=rule_pct,
                          current_pct=current_pct, rule_stop=rule_stop)


def action_t(base, pct, *, stop=None, code="TREND_WEAKENING", pid="", deviation=True, sample=None):
    return ResolvedTarget(sleeve=base.sleeve, symbol=base.symbol, pct=pct,
                          stop=base.rule_stop if stop is None else stop, rule_pct=base.rule_pct,
                          current_pct=base.current_pct, rule_stop=base.rule_stop, reason_code=code,
                          evidence=[f"rule_signals.{base.sleeve}.indicators[{base.symbol}].close"],
                          prediction_id=pid, rationale="because", is_deviation=deviation, source="action",
                          sample=sample)


def decision(targets, *, preds=(), note="note", sample=None, weights=None, reasons=None, problems=()):
    return ResolvedDecision(weights=weights or {"A": 0.55, "B": 0.20, "C": 0.15, "D": 0.0},
                            targets={t.key: t for t in targets}, weight_reasons=reasons or {},
                            predictions=list(preds), journal_note=note, market_view=f"view {note}",
                            temperature_ack=f"temp {note}", likely_error=LikelyError(kind="none", note=note),
                            flags=[f"flag {note}"], problems=list(problems), sample=sample)


NVDA = rule_t("C", "NVDA", 0.04, current_pct=0.0, rule_stop=90.0)
SPY_A = rule_t("A", "SPY", 0.11, current_pct=0.11)
QQQ = rule_t("B", "QQQ", 0.0, current_pct=0.05, rule_stop=400.0)


# --- combine_weights ------------------------------------------------------------------------------------


def test_combine_weights_median_per_sleeve():
    w = combine_weights([{"A": 0.55, "B": 0.20, "C": 0.15}, {"A": 0.60, "B": 0.15, "C": 0.10},
                         {"A": 0.50, "B": 0.25, "C": 0.15}])
    assert w == pytest.approx({"A": 0.55, "B": 0.20, "C": 0.15})


def test_combine_weights_even_count_needs_a_majority():
    samples = [{"B": 0.20}, {"B": 0.25}]
    # no reference: the lower middle value, never a weight no sample chose (0.225)
    assert combine_weights(samples)["B"] == pytest.approx(0.20)
    assert combine_weights(samples, reference={"B": 0.20})["B"] == pytest.approx(0.20)
    assert combine_weights(samples, reference={"B": 0.30})["B"] == pytest.approx(0.25)  # both below: closer
    # one sample went down and one went up from 0.225: no majority, the previous weight stays
    assert combine_weights(samples, reference={"B": 0.225})["B"] == pytest.approx(0.225)


def test_combine_weights_missing_samples_count_as_keep():
    # 1 valid of 3 requested: the lone "up" is out-voted by the two missing samples (keep)
    w = combine_weights([{"B": 0.25}], reference={"B": 0.20}, samples_requested=3)
    assert w["B"] == pytest.approx(0.20)
    # a sample without a value for a sleeve also counts as keep when there is a reference
    w = combine_weights([{"B": 0.25, "C": 0.10}, {"B": 0.25}, {"B": 0.20}], reference={"B": 0.20, "C": 0.15})
    assert w == pytest.approx({"B": 0.25, "C": 0.15})


def test_combine_weights_can_break_the_cash_budget_unless_capped(cfg):
    samples = [{"A": 0.60, "B": 0.20, "C": 0.15, "D": 0.0}, {"A": 0.55, "B": 0.25, "C": 0.15, "D": 0.0},
               {"A": 0.60, "B": 0.25, "C": 0.10, "D": 0.0}]
    assert all(sum(w.values()) <= 0.95 + 1e-9 for w in samples)
    raw = combine_weights(samples)
    assert sum(raw.values()) == pytest.approx(1.0)  # medians sleeve by sleeve: over the 5% cash buffer
    capped = combine_weights(samples, cfg=cfg)
    budget = 1.0 - cfg.policy["portfolio"]["min_cash_buffer"]
    assert sum(capped.values()) <= budget + 1e-9
    assert capped == pytest.approx(decisions.cap_weights(cfg, raw))
    out = combine_resolved([decision([NVDA], weights=w) for w in samples], cfg=cfg)
    assert sum(out.weights.values()) <= budget + 1e-9


def test_combine_weights_skips_missing_and_nan():
    w = combine_weights([{"A": 0.5, "B": float("nan")}, {"A": 0.6}, {}, None, {"A": 0.55, "D": 0.0}])
    assert w["A"] == pytest.approx(0.55)
    assert "B" not in w
    assert w["D"] == 0.0
    assert combine_weights([]) == {}


# --- combine_resolved: majority and medians ----------------------------------------------------------


def test_lone_deviating_sample_is_outvoted():
    s1 = decision([NVDA, SPY_A], note="one")
    s2 = decision([NVDA, SPY_A], note="two")
    s3 = decision([action_t(NVDA, 0.0, code="REGIME_RISK", pid="p1"), SPY_A], preds=[pred("p1")], note="three")
    out = combine_resolved([s1, s2, s3], s1.weights)
    t = out.targets["C:NVDA"]
    assert t.pct == pytest.approx(0.04)
    assert t.source == "rule" and not t.is_deviation and t.reason_code == "FOLLOW_RULE"
    assert t.sample in (1, 2)
    assert out.agreement["n"] == 3
    assert out.agreement["keys"] == 2
    assert out.agreement["unanimous_keys"] == 1
    assert out.agreement["agreement_rate"] == pytest.approx(0.5)
    assert out.agreement["deviation_keys_combined"] == []
    assert out.agreement["split"]["C:NVDA"] == [0.04, 0.04, 0.0]
    # The representative is the first rule-following sample; its (empty) predictions are used.
    assert out.journal_note == "one"
    assert out.predictions == []


def test_majority_deviation_kept_with_its_prediction():
    s1 = decision([NVDA], note="one")
    s2 = decision([action_t(NVDA, 0.0, code="REGIME_RISK", pid="p1")], preds=[pred("p1", prob=0.7)], note="two")
    s3 = decision([action_t(NVDA, 0.0, code="CONCENTRATION", pid="x")], preds=[pred("x", prob=0.65)], note="three")
    out = combine_resolved([s1, s2, s3], s1.weights)
    t = out.targets["C:NVDA"]
    assert t.pct == 0.0 and t.is_deviation and t.source == "action"
    assert t.reason_code == "REGIME_RISK" and t.sample == 2  # first action sample with that pct
    assert out.journal_note == "two"  # sample 2 is the representative (lowest index among the closest)
    assert [p.id for p in out.predictions] == ["p1"]
    assert t.prediction_id == "p1"
    assert out.agreement["deviation_keys_combined"] == ["C:NVDA"]


def test_median_size_is_used():
    s1 = decision([action_t(QQQ, 0.05, code="MEAN_REVERSION_SETUP", pid="a")], preds=[pred("a", "QQQ")])
    s2 = decision([QQQ])
    s3 = decision([action_t(QQQ, 0.025, code="MEAN_REVERSION_SETUP", pid="b")], preds=[pred("b", "QQQ")])
    out = combine_resolved([s1, s2, s3], s1.weights)
    t = out.targets["B:QQQ"]
    assert t.pct == pytest.approx(0.025)
    assert t.sample == 3 and t.prediction_id == "b"


def test_even_count_uses_middle_value_closer_to_rule():
    dev = action_t(NVDA, 0.0, code="REGIME_RISK", pid="p1")
    out = combine_resolved([decision([dev], preds=[pred("p1")]), decision([NVDA])])
    assert out.targets["C:NVDA"].pct == pytest.approx(0.04)
    assert out.targets["C:NVDA"].source == "rule"
    # n = 4: middle values 0.02 and 0.04 -> 0.04 (the rule)
    samples = [decision([action_t(NVDA, v, code="REGIME_RISK", pid="p1")], preds=[pred("p1")])
               for v in (0.0, 0.02)] + [decision([NVDA]), decision([NVDA])]
    assert combine_resolved(samples).targets["C:NVDA"].pct == pytest.approx(0.04)


def test_even_count_opposite_deviations_follow_the_rule():
    # Two valid samples (the third was dropped): one exits, one adds. Neither side is a majority.
    base = rule_t("C", "NVDA", 0.05, current_pct=0.05, rule_stop=95.0)
    lo = action_t(base, 0.0, code="TREND_WEAKENING", pid="p1")
    hi = action_t(base, 0.08, code="TREND_STRENGTHENING", pid="p2")
    for order in ([lo, hi], [hi, lo]):
        out = combine_resolved([decision([t], preds=[pred(t.prediction_id)]) for t in order])
        t = out.targets["C:NVDA"]
        assert t.pct == pytest.approx(0.05) and t.source == "rule" and not t.is_deviation
        assert t.reason_code == "FOLLOW_RULE" and t.prediction_id == "" and t.stop == pytest.approx(95.0)
        assert out.predictions == [] or all(p.id in ("p1", "p2") for p in out.predictions)
        assert out.agreement["deviation_keys_combined"] == []
    # both below the rule: a majority for a cut, the one closer to the rule wins
    mid = action_t(base, 0.02, code="TREND_WEAKENING", pid="p3")
    out = combine_resolved([decision([lo], preds=[pred("p1")]), decision([mid], preds=[pred("p3")])])
    assert out.targets["C:NVDA"].pct == pytest.approx(0.02) and out.targets["C:NVDA"].prediction_id == "p3"


def test_missing_samples_count_as_following_the_rule():
    dev = action_t(NVDA, 0.0, code="REGIME_RISK", pid="p1")
    lone = decision([dev], preds=[pred("p1")], note="solo")
    out = combine_resolved([lone], samples_requested=3)  # two of three samples were invalid
    t = out.targets["C:NVDA"]
    assert t.pct == pytest.approx(0.04) and t.source == "rule" and not t.is_deviation
    assert out.agreement["samples_requested"] == 3
    assert any("each missing one counts as following the rules" in p for p in out.problems)
    # two valid samples that agree still form a majority of three
    out = combine_resolved([lone, decision([dev], preds=[pred("p1")])], samples_requested=3)
    assert out.targets["C:NVDA"].pct == 0.0 and out.targets["C:NVDA"].is_deviation


def test_combined_stop_never_below_the_rule_floor_for_an_increase():
    base = rule_t("C", "NVDA", 0.05, current_pct=0.03, rule_stop=95.0)
    add = replace(base, pct=0.05, stop=95.0)  # the rule adds, stop 95
    hold = action_t(base, 0.03, stop=88.0, code="TREND_WEAKENING", pid="p1")  # hold, keeps the old lot stop 88
    out = combine_resolved([decision([add]), decision([hold], preds=[pred("p1")])])
    t = out.targets["C:NVDA"]
    assert t.pct == pytest.approx(0.05) and t.stop == pytest.approx(95.0)
    # n = 3: rule add with no stop, add with a tight stop, hold with the old stop -> an increase, stop >= 95
    no_stop = replace(base, pct=0.05, stop=None)
    tight = action_t(base, 0.05, stop=97.0, code="FOLLOW_RULE", deviation=False)
    out = combine_resolved([decision([no_stop]), decision([tight]), decision([hold], preds=[pred("p1")])])
    t = out.targets["C:NVDA"]
    assert t.pct == pytest.approx(0.05) and t.stop >= 95.0
    assert t.stop == pytest.approx(97.0)  # the only stop among the samples that chose this size
    # even count of backers: the upper (tighter) middle stop
    a = action_t(base, 0.05, stop=96.0, code="FOLLOW_RULE", deviation=False)
    b = action_t(base, 0.05, stop=98.0, code="FOLLOW_RULE", deviation=False)
    out = combine_resolved([decision([a]), decision([b]), decision([hold], preds=[pred("p1")])])
    assert out.targets["C:NVDA"].stop == pytest.approx(98.0)


def test_stop_is_median_of_sample_stops_and_none_when_all_none():
    s1 = decision([action_t(NVDA, 0.04, stop=95.0, code="FOLLOW_RULE", deviation=False), SPY_A])
    s2 = decision([action_t(NVDA, 0.04, stop=97.0, code="FOLLOW_RULE", deviation=False), SPY_A])
    s3 = decision([NVDA, SPY_A])  # rule stop 90
    out = combine_resolved([s1, s2, s3])
    assert out.targets["C:NVDA"].stop == pytest.approx(95.0)
    assert out.targets["A:SPY"].stop is None
    assert out.targets["C:NVDA"].source == "rule"  # combined pct is the rule pct: rule metadata preferred


def test_missing_key_in_a_sample_follows_the_rule():
    new = rule_t("C", "AMD", 0.0, current_pct=0.0, rule_stop=100.0)
    lone = action_t(new, 0.03, code="TREND_STRENGTHENING", pid="p1")
    out = combine_resolved([decision([NVDA, lone], preds=[pred("p1", "AMD")]), decision([NVDA]), decision([NVDA])])
    t = out.targets["C:AMD"]
    assert t.pct == 0.0 and t.source == "rule" and not t.is_deviation
    assert out.agreement["split"]["C:AMD"] == [0.03, 0.0, 0.0]
    # two samples agree that AMD should be bought: the buy survives
    out2 = combine_resolved([decision([NVDA, lone], preds=[pred("p1", "AMD")]),
                             decision([NVDA, action_t(new, 0.03, code="TREND_STRENGTHENING", pid="q")],
                                      preds=[pred("q", "AMD")]),
                             decision([NVDA])])
    assert out2.targets["C:AMD"].pct == pytest.approx(0.03)


def test_prediction_ids_stay_unique_across_samples():
    s1 = decision([action_t(NVDA, 0.0, code="REGIME_RISK", pid="p1"), SPY_A], preds=[pred("p1", prob=0.7)],
                  note="one")
    s2 = decision([action_t(NVDA, 0.0, code="REGIME_RISK", pid="p1"),
                   action_t(QQQ, 0.05, code="MEAN_REVERSION_SETUP", pid="p1b")],
                  preds=[pred("p1", prob=0.7), pred("p1b", "QQQ")], note="two")
    s3 = decision([NVDA, action_t(QQQ, 0.05, code="MEAN_REVERSION_SETUP", pid="p1")],
                  preds=[pred("p1", "QQQ", prob=0.55, linked="action:B:QQQ")], note="three")
    out = combine_resolved([s1, s2, s3])
    ids = [p.id for p in out.predictions]
    assert len(ids) == len(set(ids))
    qqq = out.targets["B:QQQ"]
    assert qqq.pct == pytest.approx(0.05)
    linked = {p.id: p for p in out.predictions}[qqq.prediction_id]
    assert linked.symbol == "QQQ"
    nv = out.targets["C:NVDA"]
    assert {p.id: p for p in out.predictions}[nv.prediction_id].symbol == "NVDA"


def test_prediction_collision_is_renamed_with_sample_prefix():
    a = action_t(NVDA, 0.0, code="REGIME_RISK", pid="p1")
    q = action_t(QQQ, 0.05, code="MEAN_REVERSION_SETUP", pid="p1")
    s1 = decision([a, QQQ], preds=[pred("p1")], note="one")
    s2 = decision([a, QQQ], preds=[pred("p1")], note="two")
    s3 = decision([NVDA, q], preds=[pred("p1", "QQQ", linked="action:B:QQQ")], note="three", sample=3)
    s4 = decision([NVDA, q], preds=[pred("p1", "QQQ", linked="action:B:QQQ")], note="four", sample=4)
    s5 = decision([a, q], preds=[pred("p1", "QQQ", linked="action:B:QQQ")], note="five", sample=5)
    out = combine_resolved([s1, s2, s3, s4, s5])
    # Sample 5 matches the combined decision exactly, so it is the representative and keeps "p1" (QQQ);
    # sample 3's identical QQQ prediction is not duplicated; sample 1's NVDA prediction is renamed.
    assert out.agreement["representative"] == 5
    assert out.targets["B:QQQ"].prediction_id == "p1"
    assert out.targets["C:NVDA"].prediction_id == "s1-p1"
    assert [p.id for p in out.predictions] == ["s1-p1", "p1"]  # linked ones, most supported first
    assert {p.id: p.symbol for p in out.predictions} == {"p1": "QQQ", "s1-p1": "NVDA"}


def test_identical_predictions_are_not_duplicated():
    a = action_t(NVDA, 0.0, code="REGIME_RISK", pid="p1")
    out = combine_resolved([decision([a], preds=[pred("p1")]), decision([a], preds=[pred("p1")]),
                            decision([NVDA])])
    assert [p.id for p in out.predictions] == ["p1"]


def test_max_predictions_keeps_linked_ones():
    a = action_t(NVDA, 0.0, code="REGIME_RISK", pid="p3")
    preds = [pred("p1", "SPY", linked="weight:B"), pred("p2", "IWM", linked="weight:C"), pred("p3")]
    out = combine_resolved([decision([a], preds=preds), decision([a], preds=preds)], max_predictions=2)
    assert [p.id for p in out.predictions] == ["p3", "p1"]  # linked first, then free ones while room is left
    assert any("daily limit" in p for p in out.problems)


def test_default_limit_is_three_predictions_and_the_representative_keeps_its_own():
    nv = rule_t("C", "NVDA", 0.04, current_pct=0.0, rule_stop=90.0)
    am = rule_t("C", "AMD", 0.03, current_pct=0.0, rule_stop=80.0)
    s1 = decision([action_t(nv, 0.0, code="REGIME_RISK", pid="a1"), am], preds=[pred("a1")])
    s2 = decision([action_t(nv, 0.0, code="REGIME_RISK", pid="b1"), action_t(am, 0.0, code="REGIME_RISK", pid="b2")],
                  preds=[pred("b1"), pred("b2", "AMD"), pred("b3", "SPY", linked="weight:B")])
    s3 = decision([nv, action_t(am, 0.0, code="REGIME_RISK", pid="c1")], preds=[pred("c1", "AMD")])
    out = combine_resolved([s1, s2, s3])  # no max_predictions and no cfg: CL-5's 3
    assert out.agreement["representative"] == 2
    assert out.targets["C:NVDA"].prediction_id == "b1" and out.targets["C:AMD"].prediction_id == "b2"
    assert [p.id for p in out.predictions] == ["b1", "b2", "b3"]


def test_more_linked_deviations_than_the_limit_follow_the_rule():
    names = ["K1", "K2", "K3", "K4"]
    bases = {k: rule_t("C", k, 0.05, current_pct=0.05, rule_stop=90.0) for k in names}
    votes = [{"K1", "K2", "K3"}, {"K1", "K2", "K4"}, {"K3", "K4"}]
    samples = []
    for k, chosen in enumerate(votes, 1):
        targets, preds = [], []
        for name in names:
            if name in chosen:
                preds.append(pred(f"p{len(preds) + 1}", name))
                targets.append(action_t(bases[name], 0.0, pid=preds[-1].id, sample=k))
            else:
                targets.append(bases[name])
        samples.append(decision(targets, preds=preds, sample=k))
    out = combine_resolved(samples, max_predictions=3)
    kept = out.agreement["deviation_keys_combined"]
    assert len(kept) == 3 and len(out.predictions) == 3
    linked = {t.prediction_id for t in out.targets.values() if t.prediction_id}
    assert linked == {p.id for p in out.predictions}
    dropped = [k for k in ("C:K1", "C:K2", "C:K3", "C:K4") if k not in kept]
    assert len(dropped) == 1 and out.targets[dropped[0]].pct == pytest.approx(0.05)
    assert any("over the daily limit" in p for p in out.problems)


def test_samples_sharing_a_number_do_not_mislink_predictions():
    nv = rule_t("C", "NVDA", 0.05, current_pct=0.05, rule_stop=90.0)
    aa = rule_t("C", "AAPL", 0.05, current_pct=0.05, rule_stop=90.0)
    s1 = decision([action_t(nv, 0.0, pid="p1", sample=1)], preds=[pred("p1", "NVDA")], sample=1)
    s2 = decision([nv, action_t(aa, 0.0, pid="p1", sample=1)], preds=[pred("p1", "AAPL")], sample=1)
    s3 = decision([action_t(nv, 0.0, pid="p9", sample=1), action_t(aa, 0.0, pid="p1", sample=1)],
                  preds=[pred("p1", "AAPL"), pred("p9", "NVDA")], sample=1)
    out = combine_resolved([s1, s2, s3])
    by_id = {p.id: p for p in out.predictions}
    for key, t in out.targets.items():
        assert by_id[t.prediction_id].symbol == t.symbol, key


def test_combined_deviation_without_prediction_follows_rule():
    a = action_t(NVDA, 0.0, code="REGIME_RISK", pid="missing")
    out = combine_resolved([decision([a]), decision([a]), decision([NVDA])])
    t = out.targets["C:NVDA"]
    assert t.pct == pytest.approx(0.04) and t.source == "rule" and not t.is_deviation
    assert any("no prediction" in p for p in out.problems)


def test_narrative_from_representative_and_problems_tagged():
    s1 = decision([action_t(NVDA, 0.0, code="REGIME_RISK", pid="p1")], preds=[pred("p1")], note="one",
                  problems=["actions[X]: dropped"])
    s2 = decision([NVDA], note="two")
    s3 = decision([NVDA], note="three")
    out = combine_resolved([s1, s2, s3])
    assert out.journal_note == "two" and out.market_view == "view two" and out.temperature_ack == "temp two"
    assert out.likely_error.note == "two" and out.flags == ["flag two"]
    assert out.agreement["representative"] == 2
    assert "sample 1: actions[X]: dropped" in out.problems
    assert out.sample is None


def test_weights_default_to_median_and_reasons_follow_matching_sample():
    r1 = {"B": {"choice": "up", "reason_code": "REGIME_CHANGE", "evidence": ["regime.label"]}}
    r2 = {"B": {"choice": "keep", "reason_code": "NONE", "evidence": []}}
    s1 = decision([NVDA], weights={"A": 0.55, "B": 0.25}, reasons=r1, note="one")
    s2 = decision([NVDA], weights={"A": 0.55, "B": 0.20}, reasons=r2, note="two")
    s3 = decision([NVDA], weights={"A": 0.55, "B": 0.20}, reasons=r2, note="three")
    out = combine_resolved([s1, s2, s3])
    assert out.weights == pytest.approx({"A": 0.55, "B": 0.20})
    assert out.weight_reasons["B"]["choice"] == "keep"
    out2 = combine_resolved([s1, s2, s3], {"A": 0.55, "B": 0.25})
    assert out2.weights["B"] == 0.25 and out2.weight_reasons["B"]["choice"] == "up"


def test_single_sample_passes_through():
    s = decision([action_t(NVDA, 0.02, code="REGIME_RISK", pid="p1"), SPY_A], preds=[pred("p1")], note="solo")
    out = combine_resolved([s])
    assert out.targets["C:NVDA"].pct == pytest.approx(0.02)
    assert out.targets["C:NVDA"].prediction_id == "p1"
    assert out.agreement["agreement_rate"] == 1.0 and out.agreement["n"] == 1
    assert out.journal_note == "solo"


def test_inputs_are_not_modified_and_output_is_independent():
    a = action_t(NVDA, 0.0, code="REGIME_RISK", pid="p1")
    samples = [decision([a], preds=[pred("p1")]), decision([NVDA]), decision([a], preds=[pred("p1")])]
    before = copy.deepcopy(samples)
    out = combine_resolved(samples)
    assert samples == before
    out.targets["C:NVDA"].evidence.append("x")
    out.predictions[0].probability = 0.1
    assert samples == before


def test_empty_samples_raise():
    with pytest.raises(ValueError):
        combine_resolved([])
    with pytest.raises(ValueError):
        combine_reviews([])


def test_empty_targets_combine_to_empty():
    out = combine_resolved([decision([]), decision([])])
    assert out.targets == {} and out.agreement["agreement_rate"] == 1.0


def test_nan_pct_is_treated_as_rule():
    bad = ResolvedTarget(sleeve="C", symbol="NVDA", pct=math.nan, stop=90.0, rule_pct=0.04, current_pct=0.0,
                         rule_stop=90.0)
    out = combine_resolved([decision([bad]), decision([NVDA]), decision([NVDA])])
    assert out.targets["C:NVDA"].pct == pytest.approx(0.04)


# --- combine_reviews ------------------------------------------------------------------------------------


def skip(symbol, pid="p1", code="EARNINGS_IN_WINDOW", sleeve="C"):
    return Skip(symbol=symbol, sleeve=sleeve, reason_code=code, evidence=["data_problems[0]"], prediction_id=pid,
                event_date="2026-09-30")


def review(skips=(), halves=(), preds=(), note="n", date="2026-09-25"):
    return RulesReview(date=date, journal_note=note, temperature_ack=f"t {note}", flags=[f"f {note}"],
                       skip_entries=list(skips), halve_sleeves=list(halves), predictions=list(preds))


def halve(sleeve="B", pid="h1"):
    return Halve(sleeve=sleeve, reason_code="DATA_SUSPECT", evidence=["data_problems[0]"], prediction_id=pid)


def test_review_skip_needs_strict_majority():
    r1 = review([skip("NVDA")], preds=[pred("p1")], note="one")
    r2 = review([skip("NVDA", pid="q")], preds=[pred("q")], note="two")
    r3 = review([], note="three")
    combined, stats = combine_reviews([r1, r2, r3])
    assert [s.symbol for s in combined.skip_entries] == ["NVDA"]
    assert combined.skip_entries[0].prediction_id == "p1"  # the representative's (sample 1) own item
    assert [p.id for p in combined.predictions] == ["p1"]
    assert stats["votes"] == {"skip:C:NVDA": 2}
    assert stats["deviation_keys_combined"] == ["skip:C:NVDA"]
    # a lone skip is out-voted
    combined, stats = combine_reviews([r1, r3, review([], note="four")])
    assert combined.skip_entries == [] and combined.predictions == []
    assert stats["agreement_rate"] == 0.0 and stats["unanimous_keys"] == 0
    assert combined.journal_note == "three"  # representative: closest to "no skips", lowest index


def test_review_even_count_one_of_two_is_not_majority():
    r1 = review([skip("NVDA")], preds=[pred("p1")])
    r2 = review([])
    combined, stats = combine_reviews([r1, r2])
    assert combined.skip_entries == []
    combined, stats = combine_reviews([r1, r1.model_copy(deep=True)])
    assert [s.symbol for s in combined.skip_entries] == ["NVDA"]
    assert stats["unanimous_keys"] == 1 and stats["agreement_rate"] == 1.0


def test_review_missing_samples_count_as_no_skip():
    r1 = review([skip("NVDA")], preds=[pred("p1")])
    combined, stats = combine_reviews([r1], samples_requested=3)  # two of three samples were invalid
    assert combined.skip_entries == [] and stats["samples_requested"] == 3
    assert any("each missing one counts as following the rules" in p for p in stats["problems"])
    combined, _ = combine_reviews([r1, r1.model_copy(deep=True)], samples_requested=3)
    assert [s.symbol for s in combined.skip_entries] == ["NVDA"]  # 2 of 3 is a majority


def test_review_halve_majority_and_repeated_key_counts_once():
    h = halve()
    r1 = review(halves=[h, h], preds=[pred("h1", "SPY", linked="halve:B")])
    r2 = review(skips=[skip("nvda"), skip("NVDA")], preds=[pred("p1")])
    r3 = review(skips=[skip("NVDA")], halves=[h], preds=[pred("p1"), pred("h1", "SPY", linked="halve:B")])
    combined, stats = combine_reviews([r1, r2, r3])
    assert stats["votes"] == {"halve:B": 2, "skip:C:NVDA": 2}
    assert [x.sleeve for x in combined.halve_sleeves] == ["B"]
    assert len(combined.skip_entries) == 1


def test_review_votes_are_per_sleeve_and_symbol():
    # SPY is in sleeves A and B. A sleeve-A skip is not allowed (CL-7) and is no vote for the B skip.
    r1 = review([skip("SPY", sleeve="B", code="HALT_OR_ILLIQUID")], preds=[pred("p1", "SPY")])
    r2 = review([skip("SPY", sleeve="A", code="HALT_OR_ILLIQUID")], preds=[pred("p1", "SPY")])
    combined, stats = combine_reviews([r1, r2, review([])])
    assert combined.skip_entries == []
    assert stats["votes"] == {"skip:B:SPY": 1}
    assert any(p.startswith("sample 2:") for p in stats["problems"])


def test_invalid_review_items_do_not_vote():
    bad = review([skip("NVDA", pid="missing")], note="one")  # no matching prediction (CL-5)
    wrong_sleeve = review([skip("NVDA", sleeve="B")], preds=[pred("p1")], note="b")  # earnings is C only
    good = review([skip("NVDA", pid="p2")], preds=[pred("p2")], note="two")
    combined, stats = combine_reviews([bad, good, review([], note="three")])
    assert combined.skip_entries == []  # one valid vote of three
    assert stats["votes"] == {"skip:C:NVDA": 1}
    assert any(p.startswith("sample 1:") and "prediction" in p for p in stats["problems"])
    combined, _ = combine_reviews([bad, good, good.model_copy(deep=True)])
    assert combined.skip_entries[0].prediction_id == "p2"
    assert {p.id for p in combined.predictions} == {"p2"}
    combined, stats = combine_reviews([wrong_sleeve, wrong_sleeve.model_copy(deep=True), good])
    assert combined.skip_entries == [] and "skip:B:NVDA" not in stats["votes"]
    # with the context, a bad evidence path does not vote either
    ctx = {"date": "2026-09-25", "data_problems": ["NVDA: stale close"]}
    lost = review([skip("NVDA", pid="p2", code="DATA_SUSPECT").model_copy(update={"evidence": ["nope.x"]})],
                  preds=[pred("p2")])
    ok = review([skip("NVDA", pid="p2", code="DATA_SUSPECT")], preds=[pred("p2")])
    combined, _ = combine_reviews([lost, lost.model_copy(deep=True), ok], ctx=ctx)
    assert combined.skip_entries == []
    combined, _ = combine_reviews([ok, ok.model_copy(deep=True), lost], ctx=ctx)
    assert [s.symbol for s in combined.skip_entries] == ["NVDA"]
    # a code restricted after CL-9 does not vote
    combined, _ = combine_reviews([good, good.model_copy(deep=True)],
                                  allowed_codes=("DATA_SUSPECT", "HALT_OR_ILLIQUID"))
    assert combined.skip_entries == []


def test_review_skip_whose_prediction_no_sample_has_is_dropped():
    s1 = review([skip("NVDA", pid="p2", code="HALT_OR_ILLIQUID"), skip("TSLA", pid="p3", code="HALT_OR_ILLIQUID")])
    s2 = review([skip("NVDA", pid="p9", code="HALT_OR_ILLIQUID")], preds=[pred("p2", "AAPL", linked="x:AAPL")])
    combined, stats = combine_reviews([s1, s2, review([])])
    assert combined.skip_entries == []
    log = []
    _, vetoes = decisions.apply_review([Target("NVDA", "C", 10.0, 90.0, "rule")], combined, {}, log,
                                       ctx={"date": "2026-09-25", "data_problems": ["NVDA: stale"]})
    assert vetoes == []


def test_review_representative_item_is_used_and_limit_holds(cfg):
    def ds(sym, pid):
        return skip(sym, pid=pid, code="DATA_SUSPECT").model_copy(update={"evidence": [f"data_problems[{sym}]"]})
    r1 = review([ds("NVDA", "p1")], preds=[pred("p1")], note="one")
    r2 = review([ds("NVDA", "n1"), ds("AMD", "a1")],
                preds=[pred("n1"), pred("a1", "AMD"), pred("z1", "SPY", linked="weight:B")], note="two")
    r3 = review([ds("AMD", "b1")], preds=[pred("b1", "AMD")], note="three")
    ctx = {"date": "2026-09-25", "data_problems": ["NVDA: stale", "AMD: stale"]}
    combined, stats = combine_reviews([r1, r2, r3], ctx=ctx)  # no limit passed: CL-5's 3
    assert stats["representative"] == 2
    assert {s.symbol: s.prediction_id for s in combined.skip_entries} == {"NVDA": "n1", "AMD": "a1"}
    assert [p.id for p in combined.predictions] == ["n1", "a1", "z1"]
    targets = [Target("NVDA", "C", 10.0, 90.0, "rule"), Target("AMD", "C", 10.0, 80.0, "rule")]
    log = []
    _, vetoes = decisions.apply_review(targets, combined, {}, log, ctx=ctx, date="2026-09-25", cfg=cfg)
    assert sorted(v["symbol"] for v in vetoes) == ["AMD", "NVDA"]


def test_review_more_linked_skips_than_the_limit():
    syms = ["NVDA", "AMD", "TSLA", "AAPL"]
    items = [skip(s, pid=f"p{i}", code="HALT_OR_ILLIQUID") for i, s in enumerate(syms)]
    preds = [pred(f"p{i}", s) for i, s in enumerate(syms)]
    r = review(items, preds=preds)
    combined, stats = combine_reviews([r, r.model_copy(deep=True), review([])], max_predictions=3)
    assert len(combined.skip_entries) == 3 and len(combined.predictions) == 3
    assert {s.prediction_id for s in combined.skip_entries} == {p.id for p in combined.predictions}
    assert any("over the daily limit" in p for p in stats["problems"])


def test_review_prediction_carried_over_from_the_skipping_sample():
    r1 = review([], preds=[pred("w1", "SPY", linked="weight:B")], note="one")
    r2 = review([skip("NVDA", pid="p1")], preds=[pred("p1", linked="skip:NVDA")], note="two")
    r3 = review([skip("NVDA", pid="p9")], preds=[pred("p9", linked="skip:NVDA")], note="three")
    combined, stats = combine_reviews([r1, r2, r3])
    assert combined.journal_note == "two"  # its set of skips equals the combined set
    assert combined.skip_entries[0].prediction_id == "p1"
    assert [p.id for p in combined.predictions] == ["p1"]
    # 2 of 5 is not a majority: nothing is skipped and the representative has no skips
    combined, stats = combine_reviews([r1, review([], note="four"), r2, r3, review([], note="five")])
    assert combined.skip_entries == [] and combined.journal_note == "one"
    assert [p.id for p in combined.predictions] == ["w1"]


def test_review_rename_when_representative_owns_the_id():
    r1 = review([skip("AMD", pid="p1", code="DATA_SUSPECT")],
                preds=[pred("p1", "AMD", linked="skip:AMD")], note="one")
    r2 = review([skip("AMD", pid="p1", code="DATA_SUSPECT"), skip("NVDA", pid="p1x")],
                preds=[pred("p1", "AMD", linked="skip:AMD"), pred("p1x", linked="skip:NVDA")], note="two")
    r3 = review([skip("NVDA", pid="p1")], preds=[pred("p1", linked="skip:NVDA")], note="three")
    combined, _ = combine_reviews([r3, r1, r2])
    ids = {s.symbol: s.prediction_id for s in combined.skip_entries}
    pmap = {p.id: p.symbol for p in combined.predictions}
    assert pmap[ids["AMD"]] == "AMD" and pmap[ids["NVDA"]] == "NVDA"
    assert len(pmap) == len(combined.predictions)
    # a skip whose prediction is about another symbol is not valid, so it does not vote
    odd = review([skip("NVDA", pid="p1")], preds=[pred("p1", "AMD", linked="x")], note="odd")
    combined, _ = combine_reviews([odd, r3, review([])])
    assert combined.skip_entries == []
    combined, _ = combine_reviews([odd, r3, r3.model_copy(deep=True)])
    pmap = {p.id: p.symbol for p in combined.predictions}
    assert pmap[combined.skip_entries[0].prediction_id] == "NVDA"


def test_review_trims_journal_note_and_likely_error(cfg):
    long = "One. Two. Three. Four. Five. Six. Seven."
    r = review([]).model_copy(update={"journal_note": long,
                                      "likely_error": LikelyError(kind="omission", note="First. Second.")})
    combined, _ = combine_reviews([r])
    assert combined.journal_note == "One. Two. Three. Four. Five."
    assert combined.likely_error.note == "First." and combined.likely_error.kind == "omission"
    policy = copy.deepcopy(cfg.policy)
    policy["claude_limits"]["journal_max_sentences"] = 2
    combined, _ = combine_reviews([r], cfg=type(cfg)(playbook=cfg.playbook, policy=policy))
    assert combined.journal_note == "One. Two."


def test_review_date_and_inputs_untouched():
    r1 = review([skip("NVDA")], preds=[pred("p1")], date="")
    r2 = review([skip("NVDA")], preds=[pred("p1")])
    before = copy.deepcopy([r1, r2])
    combined, _ = combine_reviews([r1, r2])
    assert combined.date == "2026-09-25"
    combined.skip_entries[0].evidence.append("x")
    assert [r1, r2] == before


# --- CL-15 shadow ----------------------------------------------------------------------------------------


def test_unanimous_pair_agreement_and_disagreement():
    up = action_t(NVDA, 0.06, code="TREND_STRENGTHENING", pid="p1")  # rule 0.04 from 0: both "up"
    down = action_t(QQQ, 0.05, code="MEAN_REVERSION_SETUP", pid="p2")  # hold vs rule's exit
    s1 = decision([up, QQQ], preds=[pred("p1")])
    s2 = decision([NVDA, down], preds=[pred("p2", "QQQ")])
    out = unanimous_pair([s1, s2])
    assert out["rule"] == "CL-15"
    assert out["detail"]["agree_keys"] == ["C:NVDA"]
    assert out["detail"]["disagree"] == [{"key": "B:QQQ", "sample_1": "down", "sample_2": "hold"}]
    assert out["fires"] is True
    assert out["would_change"] == []


def test_unanimous_pair_would_change_against_combined():
    down = action_t(QQQ, 0.05, code="MEAN_REVERSION_SETUP", pid="p2")
    s1 = decision([QQQ])
    s2 = decision([down], preds=[pred("p2", "QQQ")])
    s3 = decision([QQQ])
    combined = combine_resolved([s1, s2, s3])
    before = copy.deepcopy([s1, s2, s3, combined])
    out = unanimous_pair([s1, s2, s3], combined)
    # the pair disagrees on QQQ, so CL-15 does nothing there: the rule's exit, same as the combined decision
    assert out["detail"]["on_disagreement"] == "rule"
    assert out["would_change"] == [] and out["fires"] is False
    assert [s1, s2, s3, combined] == before  # shadow only: nothing changes


def test_unanimous_pair_disagreement_follows_the_rule_exit():
    hold = action_t(QQQ, 0.05, code="MEAN_REVERSION_SETUP", pid="p2")  # the rule exits QQQ; this holds it
    s1 = decision([hold], preds=[pred("p2", "QQQ")])
    s2 = decision([QQQ])
    s3 = decision([hold], preds=[pred("p2", "QQQ")])
    combined = combine_resolved([s1, s2, s3])
    assert combined.targets["B:QQQ"].pct == pytest.approx(0.05)  # 2 of 3 hold
    out = unanimous_pair([s1, s2, s3], combined)
    assert out["would_change"] == [{"key": "B:QQQ", "combined": "hold", "cl15": "down", "combined_pct": 0.05,
                                    "current_pct": 0.05}]
    assert out["fires"] is True


def test_unanimous_pair_key_only_in_third_sample():
    new = rule_t("C", "AMD", 0.0, current_pct=0.0, rule_stop=100.0)
    buy = action_t(new, 0.03, code="TREND_STRENGTHENING", pid="p1")
    s3 = decision([NVDA, buy], preds=[pred("p1", "AMD")])
    combined = combine_resolved([decision([NVDA]), decision([NVDA]), s3])
    out = unanimous_pair([decision([NVDA]), decision([NVDA]), s3], combined)
    assert out["fires"] is False and out["would_change"] == []
    assert out["detail"]["agreement_rate"] == 1.0


def test_unanimous_pair_needs_two_samples():
    out = unanimous_pair([decision([NVDA])])
    assert out["fires"] is False and "skipped" in out["detail"]
    assert unanimous_pair([])["fires"] is False
