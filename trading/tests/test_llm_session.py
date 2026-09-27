"""llm.py (role texts, prompt_version, API path with a fake client) and session.py (Option B files).

No network: the API client is a fake object with the same shape as the SDK's streaming call.
"""
import copy
import json
import shutil
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from trader import metrics
from trader.config import CONFIG_DIR, Config
from trader.llm import (
    FALLBACK_BETA,
    ClaudeAdvisor,
    ClaudeError,
    DECIDE_ROLE,
    REVIEW_ROLE,
    decision_tags,
    load_json,
    price_for,
    prompt_version,
    rates_for,
    same_model,
    usage_cost,
)
from trader.schemas import (
    ACTION_CODES,
    SKIP_CODES,
    WEIGHT_UP_CODES,
    ClaudeDecision,
    ResolvedTarget,
    RulesReview,
    parse_decision,
    parse_review,
    strict_schema,
)
from trader.session import (
    SessionAdvisor,
    example_file,
    find_decision_files,
    jsonable,
    pending_dir,
    session_schema,
    write_pending,
)

DATE = "2026-09-25"
CTX = {"date": DATE, "book": "claude", "regime": {"label": "bull_calm"}, "data_problems": ["NVDA: stale"],
       "rule_signals": {"C": {"indicators": [{"symbol": "NVDA", "close": 100.0, "volume_ratio": 1.8}]}}}


def with_claude(cfg, **changes):
    playbook = copy.deepcopy(cfg.playbook)
    playbook["claude"].update(changes)
    return Config(playbook=playbook, policy=cfg.policy)


def decision_json(note="follow the rules", date=DATE, **extra):
    d = example_file("claude", date, 1)
    d.pop("meta")
    d["journal_note"] = note
    d.update(extra)
    return json.dumps(d)


def review_json(note="skip nothing", date=DATE, **extra):
    d = example_file("rules", date, 1)
    d.pop("meta")
    d["journal_note"] = note
    d.update(extra)
    return json.dumps(d)


# --- fake API client -------------------------------------------------------------------------------------


def usage(inp=1000, out=500, cw=0, cr=0, iterations=None):
    return SimpleNamespace(input_tokens=inp, output_tokens=out, cache_creation_input_tokens=cw,
                           cache_read_input_tokens=cr, iterations=iterations)


def response(text, model="claude-opus-5", stop="end_turn", use=None, content=None, category=None):
    blocks = content if content is not None else [SimpleNamespace(type="thinking", thinking=""),
                                                  SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(model=model, stop_reason=stop, stop_details=SimpleNamespace(category=category),
                           content=blocks, usage=use or usage())


class FakeStream:
    def __init__(self, item):
        self.item = item

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        if isinstance(self.item, Exception):
            raise self.item
        return self.item


class FakeClient:
    def __init__(self, items):
        self.items = list(items)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **request):
        self.requests.append(request)
        return FakeStream(self.items.pop(0))


class AuthError(Exception):
    status_code = 401


# --- re-exports and role texts ------------------------------------------------------------------------------


def test_old_imports_still_work():
    from trader.llm import Action, ClaudeDecision as CD, RulesReview as RR  # noqa: F401
    from trader.llm import ClaudeAdvisor as CA, ClaudeError as CE  # noqa: F401
    from trader.llm import Prediction, Skip, Halve, WeightChoice, SleeveWeightChoices  # noqa: F401
    from trader.llm import parse_decision as pd_, parse_review as pr_, strict_schema as ss  # noqa: F401
    assert CD is ClaudeDecision and RR is RulesReview
    e = CE("boom")
    assert isinstance(e, RuntimeError) and str(e) == "boom" and e.meta is None
    assert CE("x", meta={"usd": 1.0}).meta == {"usd": 1.0}


def test_role_texts_carry_cl6_and_guide_rules():
    for text in (REVIEW_ROLE, DECIDE_ROLE):
        assert "Think in samples" in text
        assert "7-9" in text and "11-15" in text  # M-2 losing-streak brief
        assert "rule_signals.C.indicators[NVDA].volume_ratio" in text  # CL-2 evidence path format
        assert "News, remembered facts" in text
        assert "never blend" in text  # per-sleeve statistics
        assert "Agreement needs a reason" in text  # guide 16
        assert "Brier" in text and "0.05 to 0.95" in text and "0 to 3 a day" in text  # CL-5
        assert "likely_error" in text and "temperature_ack" in text and "at most 5" in text  # CL-4
        for code in SKIP_CODES:
            assert code in text
    assert "empty actions list means the" in DECIDE_ROLE and "book follows the rules" in DECIDE_ROLE
    assert "add no discretionary selling at the lows" in DECIDE_ROLE
    assert "bear or panic" in REVIEW_ROLE and "skip nothing" in REVIEW_ROLE
    for code in ACTION_CODES + WEIGHT_UP_CODES:
        assert code in DECIDE_ROLE
    for choice in ("half_rule", "hold", "exit", "pct", "tight", "keep", "default"):
        assert f'"{choice}"' in DECIDE_ROLE
    assert "There is no performance code" in DECIDE_ROLE
    assert "Sleeve A, exits, reductions and stops are never yours" in REVIEW_ROLE


def test_losing_streak_table_matches_metrics():
    # M-2: the prompt's table must be the one metrics computes exactly
    for text in (REVIEW_ROLE, DECIDE_ROLE):
        for rate in (0.35, 0.40, 0.45):
            q = metrics.streak_quantiles(rate, 100)
            row = f"| {rate:.0%}      | {q[0.25]}-{q[0.75]}"
            assert row in text, row
            assert f"{q[0.95]} or more" in text


def test_prompt_version_is_stable_and_changes_with_inputs(tmp_path):
    v = prompt_version("decide")
    assert v == prompt_version("decide") and len(v) == 12
    assert prompt_version("review") != v
    cfg_dir = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, cfg_dir)
    assert prompt_version("decide", cfg_dir) == v
    (cfg_dir / "playbook_brief.md").write_text("a different brief\n")
    assert prompt_version("decide", cfg_dir) != v
    with pytest.raises(ValueError):
        prompt_version("trade")


def test_decision_tags():
    tags = decision_tags({"mode": "api", "prompt_version": "abc", "model": "claude-opus-5", "effort": "high",
                          "fallback_used": False}, "claude")
    assert tags["book"] == "claude" and tags["prompt_version"] == "abc" and tags["model"] == "claude-opus-5"
    assert tags["effort"] == "high" and tags["schema_version"] == "2" and tags["context_schema"] == "ctx-2"
    assert decision_tags(None, "rules")["book"] == "rules"
    session_meta = {"mode": "session", "prompt_version": "abc", "model": "unknown", "instructions_version": "iv1"}
    assert decision_tags(session_meta, "claude")["instructions_version"] == "iv1"  # CL-3: the template read


# --- API path ------------------------------------------------------------------------------------------------


def test_api_three_samples_request_shape_and_cost(cfg):
    items = [response(decision_json(f"n{k}"), use=usage(100, 1000, cw=10000 if k == 1 else 0,
                                                          cr=0 if k == 1 else 10000)) for k in (1, 2, 3)]
    client = FakeClient(items)
    decisions, meta = ClaudeAdvisor(cfg, client).decide(CTX)
    assert [d.journal_note for d in decisions] == ["n1", "n2", "n3"]
    assert meta["mode"] == "api" and meta["samples_requested"] == 3 and meta["samples_valid"] == 3
    assert meta["models"] == ["claude-opus-5"] * 3 and meta["model"] == "claude-opus-5"
    assert meta["fallback_used"] is False and meta["low_confidence"] is False
    assert meta["prompt_version"] == prompt_version("decide") and meta["effort"] == "high"
    assert meta["model_requested"] == "claude-opus-5"
    # $5/$25 per million: first call writes the cache (1.25x), later calls read it (0.1x)
    first = (100 + 1.25 * 10000) * 5 / 1e6 + 1000 * 25 / 1e6
    later = (100 + 0.1 * 10000) * 5 / 1e6 + 1000 * 25 / 1e6
    assert meta["usd"] == pytest.approx(first + 2 * later)
    assert meta["input_tokens"] == 300 and meta["output_tokens"] == 3000
    assert meta["cache_write_tokens"] == 10000 and meta["cache_read_tokens"] == 20000
    req = client.requests[0]
    assert len(client.requests) == 3
    assert req["max_tokens"] == 32000
    assert req["thinking"] == {"type": "adaptive"}
    assert req["output_config"]["effort"] == "high"
    assert req["output_config"]["format"] == {"type": "json_schema", "schema": strict_schema(ClaudeDecision)}
    assert req["betas"] == [FALLBACK_BETA] and req["fallbacks"] == "default"
    assert req["system"][0]["text"] == DECIDE_ROLE
    assert "Risk policy" in req["system"][1]["text"]
    assert "cache_control" not in req["system"][0] and "cache_control" not in req["system"][1]
    user = req["messages"][0]["content"][0]
    assert user["cache_control"] == {"type": "ephemeral"}  # samples > 1: repeats reuse the cache
    assert json.loads(user["text"].split("\n", 1)[1])["date"] == DATE


def test_api_single_sample_has_no_prompt_caching(cfg):
    client = FakeClient([response(review_json())])
    reviews, meta = ClaudeAdvisor(with_claude(cfg, samples=1), client).review_rules_plan(CTX)
    assert len(reviews) == 1 and isinstance(reviews[0], RulesReview)
    req = client.requests[0]
    assert all("cache_control" not in b for b in req["system"])
    assert all("cache_control" not in b for b in req["messages"][0]["content"])
    assert req["system"][0]["text"] == REVIEW_ROLE
    assert req["output_config"]["format"]["schema"] == strict_schema(RulesReview)
    assert meta["samples_requested"] == 1 and meta["prompt_version"] == prompt_version("review")


def test_api_bad_samples_are_dropped_one_by_one(cfg):
    bad_action = {"symbol": "NVDA", "sleeve": "C", "size": "double", "reason_code": "FOLLOW_RULE", "evidence": []}
    items = [
        response("not json"),
        response("", stop="refusal", category="cyber", content=[]),
        response(decision_json("ok", actions=[bad_action])),
        response(decision_json("cut"), stop="max_tokens"),
        response(decision_json("old", date="2026-09-24")),
    ]
    decisions, meta = ClaudeAdvisor(with_claude(cfg, samples=5), FakeClient(items)).decide(CTX)
    assert [d.journal_note for d in decisions] == ["ok"]
    assert meta["samples_valid"] == 1 and meta["samples_requested"] == 5
    text = " | ".join(meta["problems"])
    assert "sample 1: invalid output" in text
    assert "sample 2: declined (cyber)" in text
    assert "sample 3: actions[NVDA]: dropped" in text
    assert "sample 4: answer cut off at max_tokens" in text
    assert "sample 5: invalid output" in text and "2026-09-24" in text
    assert [r["valid"] for r in meta["per_sample"]] == [False, False, True, False, False]


def test_api_zero_valid_raises_with_meta(cfg):
    items = [response("nope"), response("{}"), response("[1, 2]")]
    with pytest.raises(ClaudeError) as err:
        ClaudeAdvisor(cfg, FakeClient(items)).decide(CTX)
    meta = err.value.meta
    assert meta["samples_valid"] == 0 and len(meta["problems"]) == 3
    assert meta["usd"] > 0  # the cost is still reported so it can be logged (guide 13)


def test_api_call_errors_and_auth_stop(cfg):
    items = [RuntimeError("timeout"), response(decision_json("ok")), response(decision_json("ok2"))]
    decisions, meta = ClaudeAdvisor(cfg, FakeClient(items)).decide(CTX)
    assert len(decisions) == 2
    assert "sample 1: API call failed: RuntimeError: timeout" in meta["problems"]
    client = FakeClient([AuthError("bad key"), response(decision_json()), response(decision_json())])
    with pytest.raises(ClaudeError) as err:
        ClaudeAdvisor(cfg, client).decide(CTX)
    assert len(client.requests) == 1  # a bad key fails every sample the same way: stop early
    assert err.value.meta["usd"] == 0.0


def test_api_fallback_detected_from_iterations_and_priced_per_attempt(cfg):
    iters = [SimpleNamespace(type="message", model=None, input_tokens=5000, output_tokens=0,
                             cache_creation_input_tokens=0, cache_read_input_tokens=0),
             SimpleNamespace(type="fallback_message", model="claude-opus-4-8", input_tokens=5000,
                             output_tokens=800, cache_creation_input_tokens=0, cache_read_input_tokens=0)]
    items = [response(decision_json("fb"), model="claude-opus-4-8", use=usage(5000, 800, iterations=iters))]
    c = with_claude(cfg, samples=1)
    decisions, meta = ClaudeAdvisor(c, FakeClient(items)).decide(CTX)
    assert meta["fallback_used"] is True and meta["low_confidence"] is True  # guide 17
    assert meta["models"] == ["claude-opus-4-8"] and meta["model"] == "claude-opus-4-8"
    # claude-opus-4-8 is not in the pricing table: the highest listed price is used, never an undercount
    assert meta["usd"] == pytest.approx(5000 * 5 / 1e6 + (5000 * 5 + 800 * 25) / 1e6)
    assert any("no price for claude-opus-4-8" in p for p in meta["problems"])
    pricing = {**c.playbook["claude"]["pricing_per_mtok"], "claude-opus-4-8": [3.0, 15.0]}
    c2 = with_claude(cfg, samples=1, pricing_per_mtok=pricing)
    items = [response(decision_json("fb"), model="claude-opus-4-8", use=usage(5000, 800, iterations=iters))]
    _, meta2 = ClaudeAdvisor(c2, FakeClient(items)).decide(CTX)
    assert meta2["usd"] == pytest.approx(5000 * 5 / 1e6 + (5000 * 3 + 800 * 15) / 1e6)


def test_api_fallback_detected_from_model_name(cfg):
    items = [response(decision_json(), model="claude-opus-5-20260301"), response(decision_json("b")),
             response(decision_json("c"), model="claude-sonnet-5")]
    _, meta = ClaudeAdvisor(cfg, FakeClient(items)).decide(CTX)
    assert meta["fallback_used"] is True
    assert [r["fallback"] for r in meta["per_sample"]] == [False, False, True]
    # a three-way tie between answering models: the tag names them all
    assert meta["model"] == "claude-opus-5+claude-opus-5-20260301+claude-sonnet-5"


def test_api_uses_text_after_a_mid_answer_fallback(cfg):
    content = [SimpleNamespace(type="text", text='{"journal_note": "par'),
               SimpleNamespace(type="fallback", **{"from": SimpleNamespace(model="claude-opus-5")}),
               SimpleNamespace(type="text", text=decision_json("after switch"))]
    items = [response("", model="claude-opus-4-8", content=content)]
    decisions, meta = ClaudeAdvisor(with_claude(cfg, samples=1), FakeClient(items)).decide(CTX)
    assert decisions[0].journal_note == "after switch"


def test_price_and_model_helpers():
    table = {"claude-opus-5": [5.0, 25.0], "claude-opus-5-5": [4.0, 20.0]}
    assert price_for("claude-opus-5-5", table)[:2] == (4.0, 20.0)
    assert price_for("claude-opus-5", table)[:2] == (5.0, 25.0)
    assert price_for("claude-opus-5-20260101", table)[:2] == (5.0, 25.0)
    p_in, p_out, note = price_for("claude-opus-5-6", table)
    assert (p_in, p_out) == (5.0, 25.0) and note
    assert price_for("x", {})[2]
    assert same_model("claude-opus-5", "claude-opus-5") and same_model("claude-opus-5", None)
    assert not same_model("claude-opus-5", "claude-opus-5-5")


def test_api_non_finite_numbers_are_read_as_null(cfg):
    d = json.loads(decision_json("nan"))
    d["predictions"] = [{"id": "p1", "symbol": "NVDA", "horizon": 20, "direction": "above",
                         "threshold_pct": 1.0, "probability": 0.6, "linked_decision": "x"}]
    text = json.dumps(d).replace('"probability": 0.6', '"probability": NaN')
    decisions, meta = ClaudeAdvisor(with_claude(cfg, samples=1), FakeClient([response(text)])).decide(CTX)
    assert decisions[0].predictions == []
    assert any("NaN is not JSON" in p for p in meta["problems"])
    assert any("predictions[NVDA]: dropped" in p for p in meta["problems"])


def test_api_low_confidence_when_most_samples_fail(cfg):
    items = [response("nope"), response(decision_json("ok")), response("{}")]
    _, meta = ClaudeAdvisor(cfg, FakeClient(items)).decide(CTX)
    assert meta["samples_valid"] == 1 and meta["low_confidence"] is True
    assert any("low confidence" in p for p in meta["problems"])
    items = [response("nope"), response(decision_json("ok")), response(decision_json("ok2"))]
    _, meta = ClaudeAdvisor(cfg, FakeClient(items)).decide(CTX)
    assert meta["low_confidence"] is False  # 2 of 3 can still form a majority


def test_per_model_cache_rates():
    table = {"claude-opus-5": [5.0, 25.0], "claude-opus-5-5": [4.0, 20.0, 5.0, 0.2]}
    assert rates_for("claude-opus-5", table)[0] == pytest.approx((5.0, 25.0, 6.25, 0.5))
    assert rates_for("claude-opus-5-5", table)[0] == (4.0, 20.0, 5.0, 0.2)
    rates, note = rates_for("claude-other", table)
    assert rates == pytest.approx((5.0, 25.0, 6.25, 0.5)) and note  # highest of each: never undercount
    use = usage_cost(response("{}", model="claude-opus-5-5", use=usage(100, 10, cw=1000, cr=10000)),
                     "claude-opus-5-5", table)
    assert use["usd"] == pytest.approx((100 * 4.0 + 1000 * 5.0 + 10000 * 0.2 + 10 * 20.0) / 1e6)


def test_load_json_reports_non_finite_numbers():
    obj, odd = load_json('{"a": NaN, "b": [Infinity, -Infinity], "c": 1e999, "d": 1.5}')
    assert obj == {"a": None, "b": [None, None], "c": None, "d": 1.5}
    assert odd == ["NaN", "Infinity", "-Infinity", "1e999"]
    with pytest.raises(ValueError):
        load_json("{not json")


def test_api_context_is_strict_json(cfg):
    client = FakeClient([response(decision_json())])
    ctx = {**CTX, "vol": float("nan"), "n": np.int64(2), 3: "int key"}
    ClaudeAdvisor(with_claude(cfg, samples=1), client).decide(ctx)
    text = client.requests[0]["messages"][0]["content"][0]["text"].split("\n", 1)[1]
    sent = json.loads(text, parse_constant=lambda c: pytest.fail(f"non-JSON constant {c}"))
    assert sent["vol"] is None and sent["n"] == 2 and sent["3"] == "int key"


def test_api_client_is_optional_and_uses_config_max_tokens(cfg):
    client = FakeClient([response(decision_json())])
    ClaudeAdvisor(with_claude(cfg, samples=1, max_tokens=16000), client).decide(CTX)
    assert client.requests[0]["max_tokens"] == 16000


# --- session files (Option B) --------------------------------------------------------------------------------


def test_pending_dir(tmp_path):
    assert pending_dir("claude", DATE, tmp_path) == tmp_path / "claude" / "pending" / DATE
    for book, date in (("claude", "../../etc"), ("claude", "2026-9-25"), ("../x", DATE)):
        with pytest.raises(ValueError):
            pending_dir(book, date, tmp_path)


def test_write_pending_files(cfg, tmp_path):
    ctx = {**CTX, "nan": float("nan"), "inf": float("inf"), "np": np.float64(1.5), "n": np.int64(3),
           "flag": np.bool_(True), "when": pd.Timestamp("2026-09-25"), "stamp": pd.Timestamp("2026-09-25 10:30"),
           "nat": pd.NaT, "arr": np.array([1.0, np.nan]), "tags": {"b", "a"}, "pair": (1, 2),
           "target": ResolvedTarget(sleeve="C", symbol="NVDA", pct=0.04, stop=90.0, rule_pct=0.04,
                                    current_pct=0.0)}
    paths = write_pending("claude", DATE, ctx, cfg, tmp_path, 3)
    folder = pending_dir("claude", DATE, tmp_path)
    assert paths["dir"] == folder and "stale" not in paths
    assert {paths[k].name for k in ("context", "schema", "instructions")} == \
        {"context.json", "schema.json", "instructions.md"}
    got = json.loads(paths["context"].read_text())
    assert got["date"] == DATE and got["nan"] is None and got["inf"] is None and got["np"] == 1.5
    assert got["n"] == 3 and got["flag"] is True and got["when"] == "2026-09-25"
    assert got["stamp"].startswith("2026-09-25T10:30") and got["nat"] is None
    assert got["arr"] == [1.0, None] and got["tags"] == ["a", "b"] and got["pair"] == [1, 2]
    assert got["target"]["symbol"] == "NVDA"
    schema = json.loads(paths["schema"].read_text())
    base = strict_schema(ClaudeDecision)
    assert schema["required"] == base["required"] and "meta" not in schema["required"]
    assert schema["properties"]["meta"]["properties"]["model"] == {"type": "string"}
    assert {k: v for k, v in schema["properties"].items() if k != "meta"} == base["properties"]
    text = paths["instructions"].read_text()
    for needle in (DATE, "`decision_1.json`, `decision_2.json`, `decision_3.json`", '"date": "2026-09-25"',
                   '"meta"', "independently", "must NOT read", DECIDE_ROLE, "max_equity_like",
                   "Goal: beat a buy-and-hold", prompt_version("decide"), "holds its positions"):
        assert needle in text, needle
    assert list(folder.glob("*.tmp")) == []


def test_write_pending_rules_book_and_default_samples(cfg, tmp_path):
    paths = write_pending("rules", DATE, CTX, cfg, tmp_path)
    schema = json.loads(paths["schema"].read_text())
    assert "skip_entries" in schema["properties"] and "actions" not in schema["properties"]
    text = paths["instructions"].read_text()
    assert "`review_3.json`" in text and "`review_4.json`" not in text  # playbook samples = 3
    assert REVIEW_ROLE in text and "runs unreviewed" in text
    with pytest.raises(ValueError):
        write_pending("other", DATE, CTX, cfg, tmp_path)


def test_example_files_in_instructions_are_valid():
    d = example_file("claude", DATE, 2)
    assert d["meta"] == {"model": "<the model you are>", "sample": 2}
    parsed, problems = parse_decision(d, DATE)
    assert parsed.actions == [] and problems == []
    parsed, problems = parse_review(example_file("rules", DATE, 1), DATE)
    assert parsed.skip_entries == [] and problems == []
    assert "meta" in session_schema("review")["properties"]


def test_find_decision_files_natural_order_and_book_filter(tmp_path):
    folder = pending_dir("claude", DATE, tmp_path)
    (folder / "stale").mkdir(parents=True)
    for name in ("decision_10.json", "decision_2.json", "decision_1.json", "decision_x.json", "review_1.json",
                 "decision_3.json.tmp", "stale/decision_4.json", "context.json", "decision.json"):
        (folder / name).write_text("{}")
    names = [f.name for f in find_decision_files("claude", DATE, tmp_path)]
    assert names == ["decision_1.json", "decision_2.json", "decision_10.json", "decision.json", "decision_x.json"]
    assert [f.name for f in find_decision_files("rules", DATE, tmp_path)] == []
    assert find_decision_files("claude", "2020-01-01", tmp_path) == []


def test_prepare_again_moves_old_decision_files_to_stale(cfg, tmp_path):
    write_pending("claude", DATE, CTX, cfg, tmp_path, 3)
    folder = pending_dir("claude", DATE, tmp_path)
    (folder / "decision_1.json").write_text(decision_json())
    (folder / "stale").mkdir()
    (folder / "stale" / "decision_1.json").write_text("older")
    paths = write_pending("claude", DATE, CTX, cfg, tmp_path, 3)
    assert paths["stale"] == folder / "stale"
    assert find_decision_files("claude", DATE, tmp_path) == []
    assert (folder / "stale" / "decision_1.json").read_text() == "older"
    assert json.loads((folder / "stale" / "decision_1.2.json").read_text())["date"] == DATE


def _write_samples(tmp_path, notes, book="claude", models=("claude-opus-5-5",) * 3):
    folder = pending_dir(book, DATE, tmp_path)
    folder.mkdir(parents=True, exist_ok=True)
    prefix = "decision" if book == "claude" else "review"
    for k, (note, model) in enumerate(zip(notes, models), start=1):
        d = example_file(book, DATE, k)
        d["journal_note"] = note
        if model is None:
            d.pop("meta")
        else:
            d["meta"]["model"] = model
        (folder / f"{prefix}_{k}.json").write_text(json.dumps(d))
    return folder


def test_session_advisor_round_trip(cfg, tmp_path):
    write_pending("claude", DATE, CTX, cfg, tmp_path, 3)
    _write_samples(tmp_path, ["a", "b", "c"], models=("claude-opus-5-5", "claude-opus-5-5", None))
    advisor = SessionAdvisor.from_pending("claude", DATE, cfg, tmp_path)
    decisions, meta = advisor.decide(CTX)
    assert [d.journal_note for d in decisions] == ["a", "b", "c"]
    assert all(isinstance(d, ClaudeDecision) for d in decisions)
    assert meta["mode"] == "session" and meta["usd"] == 0.0
    assert meta["models"] == ["claude-opus-5-5", "claude-opus-5-5", "unknown"]
    assert meta["model"] == "claude-opus-5-5"
    assert meta["samples_requested"] == 3 and meta["samples_valid"] == 3
    assert meta["files"] == ["decision_1.json", "decision_2.json", "decision_3.json"]
    assert meta["prompt_version"] == prompt_version("decide") and meta["problems"] == []
    assert meta["context_schema"] == "ctx-2" and meta["instructions_version"]


def test_session_rules_book_review_with_a_skip(cfg, tmp_path):
    folder = _write_samples(tmp_path, ["a", "b"], book="rules")
    d = json.loads((folder / "review_2.json").read_text())
    d["skip_entries"] = [{"symbol": "NVDA", "sleeve": "C", "reason_code": "DATA_SUSPECT",
                          "evidence": ["data_problems[0]"], "prediction_id": "p1", "event_date": "",
                          "verified": False},
                         {"symbol": "AMD", "sleeve": "C", "reason_code": "BAD_MOOD", "evidence": [],
                          "prediction_id": "p2", "event_date": "", "verified": False}]
    d["predictions"] = [{"id": "p1", "symbol": "NVDA", "horizon": 5, "direction": "below", "threshold_pct": 0.0,
                         "probability": 0.6, "linked_decision": "skip:NVDA"}]
    (folder / "review_2.json").write_text(json.dumps(d))
    reviews, meta = SessionAdvisor.from_pending("rules", DATE, cfg, tmp_path).review_rules_plan(CTX)
    assert len(reviews) == 2 and [s.symbol for s in reviews[1].skip_entries] == ["NVDA"]
    assert any(p.startswith("review_2.json: skip_entries[AMD]: dropped") for p in meta["problems"])
    assert "2 valid file(s), 3 wanted" in meta["problems"]


def test_session_invalid_and_wrong_date_files_are_dropped(cfg, tmp_path):
    folder = _write_samples(tmp_path, ["a", "b", "c"])
    (folder / "decision_1.json").write_text("{not json")
    d = json.loads((folder / "decision_2.json").read_text())
    d["date"] = "2026-09-24"
    (folder / "decision_2.json").write_text(json.dumps(d))
    decisions, meta = SessionAdvisor(find_decision_files("claude", DATE, tmp_path), DATE, cfg).decide(CTX)
    assert [x.journal_note for x in decisions] == ["c"]
    text = " | ".join(meta["problems"])
    assert "decision_1.json: not valid JSON" in text
    assert "decision_2.json: dropped" in text and "2026-09-24" in text


def test_session_no_valid_file_raises_claude_error(cfg, tmp_path):
    with pytest.raises(ClaudeError) as err:
        SessionAdvisor([], DATE, cfg).decide(CTX)
    assert err.value.meta["samples_valid"] == 0
    folder = _write_samples(tmp_path, ["a"])
    (folder / "decision_1.json").write_text("[]")
    missing = folder / "decision_9.json"
    with pytest.raises(ClaudeError) as err:
        SessionAdvisor([folder / "decision_1.json", missing], DATE, cfg).decide(CTX)
    text = " | ".join(err.value.meta["problems"])
    assert "top level must be a JSON object" in text and "decision_9.json: unreadable" in text


def test_session_missing_required_field_drops_file(cfg, tmp_path):
    folder = _write_samples(tmp_path, ["a"])
    d = json.loads((folder / "decision_1.json").read_text())
    d.pop("journal_note")
    (folder / "decision_1.json").write_text(json.dumps(d))
    with pytest.raises(ClaudeError, match="no valid decision file"):
        SessionAdvisor.from_pending("claude", DATE, cfg, tmp_path).decide(CTX)


def test_session_review_does_not_accept_decision_files(cfg, tmp_path):
    _write_samples(tmp_path, ["a"])
    files = find_decision_files("claude", DATE, tmp_path)
    with pytest.raises(ClaudeError) as err:
        SessionAdvisor(files, DATE, cfg).review_rules_plan(CTX)
    assert "not a review file" in err.value.meta["problems"][0]


def test_session_identical_files_count_once(cfg, tmp_path):
    folder = _write_samples(tmp_path, ["same", "same", "other"])
    decisions, meta = SessionAdvisor.from_pending("claude", DATE, cfg, tmp_path).decide(CTX)
    assert [d.journal_note for d in decisions] == ["same", "other"]
    assert any("identical to an earlier file" in p for p in meta["problems"])
    assert meta["files"] == ["decision_1.json", "decision_3.json"]
    assert folder.exists()


def test_session_context_for_another_day_is_refused(cfg, tmp_path):
    _write_samples(tmp_path, ["a"])
    advisor = SessionAdvisor.from_pending("claude", DATE, cfg, tmp_path)
    with pytest.raises(ClaudeError, match="today's context is 2026-09-26"):
        advisor.decide({**CTX, "date": "2026-09-26"})
    decisions, _ = advisor.decide({})  # no date in the context: the files' date check still applies
    assert len(decisions) == 1


def test_session_file_without_date_is_dropped(cfg, tmp_path):
    folder = _write_samples(tmp_path, ["a", "b"])
    d = json.loads((folder / "decision_1.json").read_text())
    d.pop("date")
    (folder / "decision_1.json").write_text(json.dumps(d))
    d = json.loads((folder / "decision_2.json").read_text())
    d["date"] = ""
    (folder / "decision_2.json").write_text(json.dumps(d))
    with pytest.raises(ClaudeError) as err:
        SessionAdvisor.from_pending("claude", DATE, cfg, tmp_path).decide(CTX)
    text = " | ".join(err.value.meta["problems"])
    assert "decision_1.json: dropped, does not match schema.json" in text and "missing key(s) date" in text
    assert "decision_2.json: dropped, no date" in text


def _one_file(tmp_path, d, name="decision_1.json", book="claude"):
    folder = pending_dir(book, DATE, tmp_path)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(d))
    return folder / name


def _action(**changes):
    a = {"symbol": "NVDA", "sleeve": "C", "size": "exit", "target_pct_equity": 0.0, "stop": "rule",
         "reason_code": "TREND_WEAKENING", "evidence": ["regime.label"], "prediction_id": "p1", "rationale": "x"}
    a.update(changes)
    return a


def test_session_misspelled_or_missing_top_level_keys_drop_the_file(cfg, tmp_path):
    # CL-1: pydantic alone would ignore "action" and default "actions" to [], silently following the rules
    d = example_file("claude", DATE, 1)
    d["action"] = [_action()]
    d.pop("actions")
    f = _one_file(tmp_path, d)
    with pytest.raises(ClaudeError) as err:
        SessionAdvisor([f], DATE, cfg).decide(CTX)
    text = " | ".join(err.value.meta["problems"])
    assert "does not match schema.json (CL-1)" in text
    assert "unknown key(s) action" in text and "missing key(s) actions" in text
    d = example_file("claude", DATE, 1)
    d.pop("flags")
    with pytest.raises(ClaudeError, match="missing key"):
        SessionAdvisor([_one_file(tmp_path, d)], DATE, cfg).decide(CTX)


def test_session_item_with_a_bad_key_is_dropped_on_its_own(cfg, tmp_path):
    d = example_file("claude", DATE, 1)
    good = _action(symbol="AMD")
    typo = _action(size="pct", target_pct=0.02)  # misspelled: pydantic would default the size to 0 (an exit)
    typo.pop("target_pct_equity")
    d["actions"] = [typo, good]
    d["predictions"] = [{"id": "p1", "symbol": "NVDA", "horizon": 20, "direction": "below", "threshold_pct": 0.0,
                         "probability": 0.6, "linked_decision": "action:C:NVDA", "note": "extra"}]
    d["sleeve_weights"]["B"] = {"choice": "up", "reason": "REGIME_CHANGE", "evidence": ["regime.label"]}
    d["sleeve_weights"].pop("D")
    decisions, meta = SessionAdvisor([_one_file(tmp_path, d)], DATE, cfg).decide(CTX)
    dec = decisions[0]
    assert [a.symbol for a in dec.actions] == ["AMD"] and dec.predictions == []
    assert dec.sleeve_weights.B.choice == "keep" and dec.sleeve_weights.D.choice == "keep"
    text = " | ".join(meta["problems"])
    assert "actions[NVDA]: dropped, unknown key(s) target_pct; missing key(s) target_pct_equity" in text
    assert "predictions[NVDA]: dropped, unknown key(s) note" in text
    assert "sleeve_weights.B: kept as 'keep'" in text and "sleeve_weights.D: missing, kept as 'keep'" in text


def test_session_non_finite_numbers_are_read_as_null(cfg, tmp_path):
    d = example_file("claude", DATE, 1)
    d["actions"] = [_action(size="pct", target_pct_equity=0.02, symbol="AMD"), _action()]
    d["predictions"] = [{"id": "p1", "symbol": "NVDA", "horizon": 20, "direction": "below", "threshold_pct": 0.0,
                         "probability": 0.6, "linked_decision": "action:C:NVDA"}]
    text = json.dumps(d).replace('"target_pct_equity": 0.02', '"target_pct_equity": Infinity')
    text = text.replace('"probability": 0.6', '"probability": NaN')
    f = pending_dir("claude", DATE, tmp_path) / "decision_1.json"
    f.parent.mkdir(parents=True)
    f.write_text(text)
    decisions, meta = SessionAdvisor([f], DATE, cfg).decide(CTX)
    assert [a.symbol for a in decisions[0].actions] == ["NVDA"] and decisions[0].predictions == []
    problems = " | ".join(meta["problems"])
    assert "Infinity, NaN is not JSON; read as null" in problems or "NaN, Infinity is not JSON" in problems


def test_session_explicit_file_with_any_name_is_accepted(cfg, tmp_path):
    for name in ("decision.json", "my_answer.json"):
        f = _one_file(tmp_path, example_file("claude", DATE, 1), name=name)
        decisions, meta = SessionAdvisor([f], DATE, cfg).decide(CTX)
        assert len(decisions) == 1 and meta["samples_requested"] == 1 and meta["low_confidence"] is False
    # the other book's file name is still refused, and the other book's content fails the schema
    f = _one_file(tmp_path, example_file("rules", DATE, 1), name="answer.json")
    with pytest.raises(ClaudeError, match="unknown key"):
        SessionAdvisor([f], DATE, cfg).decide(CTX)
    f = _one_file(tmp_path, example_file("claude", DATE, 1), name="review_1.json", book="rules")
    with pytest.raises(ClaudeError, match="unknown key"):
        SessionAdvisor([f], DATE, cfg).review_rules_plan(CTX)


def test_session_placeholder_model_name_is_unknown(cfg, tmp_path):
    f = _one_file(tmp_path, example_file("claude", DATE, 1))  # meta.model is "<the model you are>"
    _, meta = SessionAdvisor([f], DATE, cfg).decide(CTX)
    assert meta["models"] == ["unknown"] and meta["model"] == "unknown"


def test_session_low_confidence_and_prepared_sample_count(cfg, tmp_path):
    write_pending("claude", DATE, CTX, cfg, tmp_path, 3)
    _write_samples(tmp_path, ["a"])
    decisions, meta = SessionAdvisor.from_pending("claude", DATE, cfg, tmp_path).decide(CTX)
    assert meta["samples_requested"] == 3 and meta["samples_valid"] == 1
    assert meta["low_confidence"] is True and any("low confidence" in p for p in meta["problems"])
    write_pending("claude", DATE, CTX, cfg, tmp_path, 1)  # an eval day asks for one sample
    _write_samples(tmp_path, ["a"])
    _, meta = SessionAdvisor.from_pending("claude", DATE, cfg, tmp_path).decide(CTX)
    assert meta["samples_requested"] == 1 and meta["low_confidence"] is False and meta["problems"] == []


def test_session_and_api_advisors_share_an_interface(cfg, tmp_path):
    _write_samples(tmp_path, ["a"])
    session = SessionAdvisor.from_pending("claude", DATE, cfg, tmp_path)
    api = ClaudeAdvisor(with_claude(cfg, samples=1), FakeClient([response(decision_json())]))
    for advisor in (session, api):
        samples, meta = advisor.decide(CTX)
        assert isinstance(samples, list) and isinstance(samples[0], ClaudeDecision)
        for key in ("mode", "model", "models", "samples_requested", "samples_valid", "problems",
                    "prompt_version", "usd", "fallback_used", "effort", "context_schema"):
            assert key in meta, key
    assert session.mode == "session" and api.mode == "api"


def test_jsonable_edge_cases():
    import decimal
    out = jsonable({"na": pd.NA, "dec": decimal.Decimal("1.5"), "bad": decimal.Decimal("NaN"),
                    pd.Timestamp("2026-09-25"): 1, "f32": np.float32("nan")})
    assert out == {"na": None, "dec": 1.5, "bad": None, "2026-09-25": 1, "f32": None}
    json.dumps(out, allow_nan=False)


def test_jsonable_leaves_inputs_alone():
    ctx = {"a": [1.0, float("nan")], "t": replace(ResolvedTarget("C", "X", 0.1, None, 0.1, 0.0))}
    before = copy.deepcopy(ctx)
    out = jsonable(ctx)
    assert out["a"] == [1.0, None]
    assert ctx["a"][0] == before["a"][0] and ctx["t"] == before["t"]


def test_role_texts_say_a_prediction_must_be_about_its_symbol():
    """decisions.py drops a skip or deviation whose prediction is about another symbol, so both roles say so."""
    from trader.llm import ROLE_TEXT

    for text in ROLE_TEXT.values():
        assert "must be about that same symbol, or name it in linked_decision" in text
