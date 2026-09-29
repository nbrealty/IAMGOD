"""What Claude may return, as pydantic models, and a tolerant parser.

Both paths use these models: the API path (structured JSON output) and the session path
(a Claude Code session writes decision_<k>.json / review_<k>.json files).

Design (reports/Agent building guide.md rules 1-5, rulebook section (e)):
- Code computes every number. Claude picks from menus: sizes ("rule", "half_rule", "hold", "exit"),
  stops ("rule", "tight", "keep") and weight moves ("keep", "up", "down", "rule", "default").
  "pct" with target_pct_equity is the one free-form size, and it is always recorded as a deviation.
- Every action, skip and weight increase carries a reason code from a fixed list and evidence paths
  into today's context (CL-2). Deviations and skips also need a falsifiable prediction (CL-5).
- One bad item never sinks the whole decision: parse_decision / parse_review drop only that item.
"""
from __future__ import annotations

import copy
import json
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

SCHEMA_VERSION = "2"
CONTEXT_SCHEMA = "ctx-3"  # ctx-3: TEST FIRST shadow signals removed (M-12)

Sleeve = Literal["A", "B", "C", "D"]

# CL-8: the only reasons the rules book's review may skip or halve an entry.
SKIP_CODES = ("EARNINGS_IN_WINDOW", "DATA_SUSPECT", "SCHEDULED_EVENT", "HALT_OR_ILLIQUID", "CORPORATE_ACTION")
# CL-9: what is left once vetoes have lost money over >= 30 scored vetoes.
RESTRICTED_SKIP_CODES = ("DATA_SUSPECT", "HALT_OR_ILLIQUID")
# CL-12: the only reasons to raise a B, C or D weight. There is no performance code.
WEIGHT_UP_CODES = ("SIGNAL_COUNT_CHANGE", "REGIME_CHANGE", "VOLATILITY_CHANGE", "RETURN_TO_DEFAULT")
# CL-13: reasons for a Claude-book deviation from the rule target. FOLLOW_RULE means no deviation.
DEVIATION_CODES = SKIP_CODES + (
    "REGIME_RISK",  # regime, temperature, breadth or stock-bond evidence
    "CONCENTRATION",  # sector, correlation, heat or cluster evidence
    "TREND_WEAKENING",  # price against SMA, pivot, low or stop
    "TREND_STRENGTHENING",  # template, peer RS or breakout evidence
    "MEAN_REVERSION_SETUP",  # RSI(2) evidence, sleeve B only
)
ACTION_CODES = ("FOLLOW_RULE",) + DEVIATION_CODES

SkipCode = Literal[SKIP_CODES]  # type: ignore[valid-type]
WeightCode = Literal[("NONE",) + WEIGHT_UP_CODES]  # type: ignore[valid-type]
ActionCode = Literal[ACTION_CODES]  # type: ignore[valid-type]


class DecisionError(ValueError):
    """The whole decision is unusable (not JSON, wrong date, missing top-level fields)."""


class LikelyError(BaseModel):
    """CL-4: which mistake Claude thinks it is most likely making today."""

    kind: Literal["commission", "omission", "none"] = "none"
    note: str = ""


class Prediction(BaseModel):
    """CL-5: a falsifiable call, resolved from closes and Brier-scored (M-7).

    The event is: close after `horizon` sessions is above (or below) today's close * (1 + threshold_pct / 100).
    """

    id: str
    symbol: str
    horizon: Literal[5, 20, 60]
    direction: Literal["above", "below"]
    threshold_pct: float  # percent, e.g. 2.0 means +2%; clipped to [-50, 50] in code
    probability: float  # clipped to [0.05, 0.95] in code
    linked_decision: str  # e.g. "action:C:NVDA", "skip:NVDA", "halve:B", "weight:B"


# --- rules book review ------------------------------------------------------------------------


class Skip(BaseModel):
    """Skip one symbol's new entry or increase today (B, C or D only; CL-7)."""

    symbol: str
    sleeve: Sleeve
    reason_code: SkipCode
    evidence: list[str]
    prediction_id: str
    event_date: str = ""  # EARNINGS_IN_WINDOW and SCHEDULED_EVENT: the stated date
    verified: bool = False  # forced to false by code until an earnings calendar exists (C-18)


class Halve(BaseModel):
    """Halve one sleeve's new-entry sizes today (B, C or D only; CL-7)."""

    sleeve: Sleeve
    reason_code: SkipCode
    evidence: list[str]
    prediction_id: str
    event_date: str = ""


class RulesReview(BaseModel):
    schema_version: str = SCHEMA_VERSION
    date: str = ""  # must equal the context date in session mode
    journal_note: str
    temperature_ack: str = ""
    likely_error: LikelyError = Field(default_factory=LikelyError)
    flags: list[str] = Field(default_factory=list)
    skip_entries: list[Skip] = Field(default_factory=list)
    halve_sleeves: list[Halve] = Field(default_factory=list)
    predictions: list[Prediction] = Field(default_factory=list)


# --- Claude book decision ---------------------------------------------------------------------


class WeightChoice(BaseModel):
    """CL-10/CL-12: a move from the menu; code turns it into a number inside every limit."""

    choice: Literal["keep", "up", "down", "rule", "default"] = "keep"
    reason_code: WeightCode = "NONE"  # required (not NONE) when the result raises B, C or D
    evidence: list[str] = Field(default_factory=list)


class SleeveWeightChoices(BaseModel):
    A: WeightChoice = Field(default_factory=WeightChoice)
    B: WeightChoice = Field(default_factory=WeightChoice)
    C: WeightChoice = Field(default_factory=WeightChoice)
    D: WeightChoice = Field(default_factory=WeightChoice)


class Action(BaseModel):
    """Change one symbol in one sleeve. Symbols without an action follow the rule target.

    size: "rule" = the rules' target for this book today; "half_rule" = half of it; "hold" = keep the current
    quantity; "exit" = 0; "pct" = target_pct_equity (share of total equity after the trade).
    stop: "rule" = the rule stop (also the floor, CL-14); "tight" = halfway between price and the rule stop;
    "keep" = the current stop; "none" = sleeve A only.
    """

    symbol: str
    sleeve: Sleeve
    size: Literal["rule", "half_rule", "hold", "exit", "pct"]
    target_pct_equity: float = 0.0
    stop: Literal["rule", "tight", "keep", "none"] = "rule"
    reason_code: ActionCode
    evidence: list[str]
    prediction_id: str = ""
    rationale: str = ""
    event_date: str = ""  # EARNINGS_IN_WINDOW and SCHEDULED_EVENT: the stated date, checked as for a skip (CL-8)


class ClaudeDecision(BaseModel):
    schema_version: str = SCHEMA_VERSION
    date: str = ""  # must equal the context date in session mode
    market_view: str
    temperature_ack: str = ""
    likely_error: LikelyError = Field(default_factory=LikelyError)
    flags: list[str] = Field(default_factory=list)
    sleeve_weights: SleeveWeightChoices = Field(default_factory=SleeveWeightChoices)
    actions: list[Action] = Field(default_factory=list)
    predictions: list[Prediction] = Field(default_factory=list)
    journal_note: str


# --- tolerant parsing ---------------------------------------------------------------------------

_ITEM_LISTS = {
    RulesReview: {"skip_entries": Skip, "halve_sleeves": Halve, "predictions": Prediction},
    ClaudeDecision: {"actions": Action, "predictions": Prediction},
}


def _load(raw: str | bytes | dict) -> dict:
    if isinstance(raw, dict):
        return copy.deepcopy(raw)
    try:
        d = json.loads(raw)
    except (TypeError, ValueError) as e:
        raise DecisionError(f"not valid JSON: {e}") from e
    if not isinstance(d, dict):
        raise DecisionError("top level must be a JSON object")
    return d


def _parse(model: type[BaseModel], raw: str | bytes | dict, expected_date: str | None) -> tuple[Any, list[str]]:
    d = _load(raw)
    problems: list[str] = []
    kept: dict[str, list] = {}
    for key, item_model in _ITEM_LISTS[model].items():
        items = d.pop(key, [])
        if not isinstance(items, list):
            problems.append(f"{key}: not a list, ignored")
            items = []
        good = []
        for i, item in enumerate(items):
            try:
                good.append(item_model.model_validate(item))
            except ValidationError as e:
                label = item.get("symbol") or item.get("sleeve") or item.get("id") if isinstance(item, dict) else i
                problems.append(f"{key}[{label}]: dropped, {_short(e)}")
        kept[key] = good
    if model is ClaudeDecision and isinstance(d.get("sleeve_weights"), dict):
        weights = {}
        for s, choice in d["sleeve_weights"].items():
            if s not in ("A", "B", "C", "D"):
                problems.append(f"sleeve_weights.{s}: unknown sleeve, ignored")
                continue
            try:
                weights[s] = WeightChoice.model_validate(choice)
            except ValidationError as e:
                problems.append(f"sleeve_weights.{s}: invalid, kept as 'keep' ({_short(e)})")
        d["sleeve_weights"] = SleeveWeightChoices(**weights)
    try:
        parsed = model.model_validate({**d, **kept})
    except ValidationError as e:
        raise DecisionError(f"invalid {model.__name__}: {_short(e)}") from e
    if expected_date and parsed.date and parsed.date != expected_date:
        raise DecisionError(f"decision is for {parsed.date}, today's context is {expected_date}")
    if expected_date and not parsed.date:
        problems.append("no date in the decision; accepted for the context date")
    return parsed, problems


def _short(e: ValidationError) -> str:
    errs = e.errors()
    first = errs[0] if errs else {}
    loc = ".".join(str(x) for x in first.get("loc", ()))
    more = f" (+{len(errs) - 1} more)" if len(errs) > 1 else ""
    return f"{loc}: {first.get('msg', str(e))}{more}"


def parse_decision(raw: str | bytes | dict, expected_date: str | None = None) -> tuple[ClaudeDecision, list[str]]:
    """Validate a Claude-book decision. Bad actions or predictions are dropped one by one.

    Raises DecisionError only when the whole thing is unusable (the caller then holds; stops still run).
    """
    return _parse(ClaudeDecision, raw, expected_date)


def parse_review(raw: str | bytes | dict, expected_date: str | None = None) -> tuple[RulesReview, list[str]]:
    """Validate a rules-book review. Bad skips, halves or predictions are dropped one by one."""
    return _parse(RulesReview, raw, expected_date)


# --- JSON schema for structured outputs and for the session's schema.json ------------------------


def strict_schema(model: type[BaseModel]) -> dict:
    """Pydantic's schema with $refs inlined, every property required and no extra properties.

    Strict structured outputs need additionalProperties false everywhere. Numeric ranges are not in the
    schema; code clips them per item instead.
    """
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def fix(node: Any) -> Any:
        if isinstance(node, list):
            return [fix(n) for n in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return fix(copy.deepcopy(defs[node["$ref"].split("/")[-1]]))
        out = {k: fix(v) for k, v in node.items() if k not in ("title", "default", "description")}
        if out.get("type") == "object" and "properties" in out:
            out["required"] = list(out["properties"])
            out["additionalProperties"] = False
        return out

    return fix(raw)


# --- code-side result of turning one decision's menu choices into numbers ------------------------

from dataclasses import dataclass, field as dc_field  # noqa: E402


@dataclass
class ResolvedTarget:
    """One (sleeve, symbol) after code resolved Claude's menu choice (or the rule default) into numbers."""

    sleeve: str
    symbol: str
    pct: float  # target share of equity
    stop: float | None
    rule_pct: float  # the rules' target for this book today
    current_pct: float  # what the book holds now
    rule_stop: float | None = None
    reason_code: str = "FOLLOW_RULE"
    evidence: list[str] = dc_field(default_factory=list)
    prediction_id: str = ""
    rationale: str = ""
    is_deviation: bool = False  # CL-13: > deviation_threshold of the larger target, or a different direction
    source: str = "rule"  # "rule" (no valid action, the rule applies) or "action"
    sample: int | None = None  # which sample's action this came from (consensus)

    @property
    def key(self) -> str:
        return f"{self.sleeve}:{self.symbol}"


@dataclass
class ResolvedDecision:
    weights: dict[str, float]
    targets: dict[str, ResolvedTarget]  # key "C:NVDA"
    weight_reasons: dict[str, dict] = dc_field(default_factory=dict)  # sleeve -> {choice, reason_code, evidence}
    predictions: list[Prediction] = dc_field(default_factory=list)
    journal_note: str = ""
    market_view: str = ""
    temperature_ack: str = ""
    likely_error: LikelyError = dc_field(default_factory=LikelyError)
    flags: list[str] = dc_field(default_factory=list)
    problems: list[str] = dc_field(default_factory=list)  # every dropped or clipped item, with the reason
    sample: int | None = None
    agreement: dict = dc_field(default_factory=dict)  # consensus stats when combined from samples
