"""Claude calls. Both return validated pydantic objects or raise ClaudeError.

- review_rules_plan: for the rules book. Claude can only skip entries or halve sleeves.
- decide: for the Claude book. Claude picks sleeve weights and target positions;
  the risk engine still enforces every hard limit afterwards.
"""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from .config import CONFIG_DIR, Config

Sleeve = Literal["A", "B", "C", "D"]


class ClaudeError(RuntimeError):
    pass


class RulesReview(BaseModel):
    journal_note: str
    flags: list[str] = Field(default_factory=list)
    skip_entries: list[str] = Field(default_factory=list)
    halve_sleeves: list[Sleeve] = Field(default_factory=list)


class Action(BaseModel):
    symbol: str
    sleeve: Sleeve
    target_pct_equity: float = Field(ge=0.0, le=1.0)
    stop_price: float = Field(ge=0.0)  # 0 means no stop (sleeve A only)
    rationale: str


class SleeveWeights(BaseModel):
    A: float
    B: float
    C: float
    D: float


class ClaudeDecision(BaseModel):
    market_view: str
    sleeve_weights: SleeveWeights
    actions: list[Action]
    journal_note: str


def _schema(model: type[BaseModel]) -> dict:
    """Hand-written JSON schemas: strict structured outputs need additionalProperties false everywhere."""
    sleeves = {"type": "string", "enum": ["A", "B", "C", "D"]}
    str_list = {"type": "array", "items": {"type": "string"}}
    if model is RulesReview:
        return {
            "type": "object",
            "properties": {
                "journal_note": {"type": "string"},
                "flags": str_list,
                "skip_entries": str_list,
                "halve_sleeves": {"type": "array", "items": sleeves},
            },
            "required": ["journal_note", "flags", "skip_entries", "halve_sleeves"],
            "additionalProperties": False,
        }
    return {
        "type": "object",
        "properties": {
            "market_view": {"type": "string"},
            "sleeve_weights": {
                "type": "object",
                "properties": {k: {"type": "number"} for k in "ABCD"},
                "required": list("ABCD"),
                "additionalProperties": False,
            },
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "sleeve": sleeves,
                        "target_pct_equity": {"type": "number"},
                        "stop_price": {"type": "number"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["symbol", "sleeve", "target_pct_equity", "stop_price", "rationale"],
                    "additionalProperties": False,
                },
            },
            "journal_note": {"type": "string"},
        },
        "required": ["market_view", "sleeve_weights", "actions", "journal_note"],
        "additionalProperties": False,
    }


REVIEW_ROLE = """You are the risk reviewer for a rules-based paper-trading book.
Deterministic code has already computed the market regime, each sleeve's signals and the planned
trades. You cannot add trades, raise size, move stops or change parameters. You may only:
- skip_entries: list symbols whose NEW entry today should be skipped, when you see a concrete reason
  the rules cannot see (an earnings report inside a breakout's holding window, bad or suspicious data,
  a known scheduled event, an obviously broken thesis). Do not skip on vague market opinions.
- halve_sleeves: halve the new-entry size of a sleeve for today, again only for a concrete reason.
- flags: short warnings for the human owner (data anomalies, positions to watch).
- journal_note: 2-5 sentences on the regime, what the rules did and why, in plain English.
Most days the right answer is to skip nothing. Rules followed consistently are the edge."""

DECIDE_ROLE = """You are the portfolio manager of a paper-trading book that competes with an identical
book run purely by fixed rules. You decide; deterministic code then enforces hard risk limits you
cannot override (listed in the risk policy below). Anything outside them is clipped or rejected.

Each day you receive the regime, your positions, account state and what the rules would do for every
sleeve. Return:
- sleeve_weights: share of equity for each sleeve, inside the bounds given (D must be 0 when disabled).
- actions: target holdings you want to CHANGE. target_pct_equity is the position's share of total
  equity after the trade (0 = exit). Positions you do not mention stay as they are. For sleeves B, C
  and D give a stop_price below the current price; stops can only be raised, never lowered, and the
  code exits any position whose close falls to its stop. For sleeve A use stop_price 0.
  Only symbols in the allowlist are accepted. No shorts, no leverage.
- market_view and journal_note: brief, concrete reasoning you would defend in a post-mortem.

You may follow the rules, deviate from them, or do nothing. Deviate only when you can name a specific
reason, and remember the evidence: trading more usually earns less. You are measured against the
rules book and against buy-and-hold SPY, on return and on drawdown, over months, not days."""


class ClaudeAdvisor:
    def __init__(self, cfg: Config, client=None):
        self.cfg = cfg
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client = client
        brief = (CONFIG_DIR / "playbook_brief.md").read_text()
        policy = (CONFIG_DIR / "risk_policy.yaml").read_text()
        self._reference = f"{brief}\n\n# Risk policy (enforced by code)\n```yaml\n{policy}```"

    def review_rules_plan(self, context: dict) -> tuple[RulesReview, dict]:
        return self._call(REVIEW_ROLE, context, RulesReview)

    def decide(self, context: dict) -> tuple[ClaudeDecision, dict]:
        return self._call(DECIDE_ROLE, context, ClaudeDecision)

    def _call(self, role: str, context: dict, model: type[BaseModel]):
        c = self.cfg.playbook["claude"]
        try:
            response = self.client.messages.create(
                model=c["model"],
                max_tokens=c["max_tokens"],
                system=[
                    {"type": "text", "text": role},
                    {"type": "text", "text": self._reference, "cache_control": {"type": "ephemeral"}},
                ],
                messages=[{"role": "user", "content": "Today's data:\n" + json.dumps(context, default=str)}],
                thinking={"type": "adaptive"},
                output_config={"effort": c["effort"], "format": {"type": "json_schema", "schema": _schema(model)}},
                # If a safety classifier declines, re-run on Anthropic's recommended fallback model.
                extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
                extra_body={"fallbacks": "default"},
            )
        except Exception as e:  # network, rate limit, auth: the caller falls back to safe behaviour
            raise ClaudeError(f"API call failed: {type(e).__name__}: {e}") from e
        if response.stop_reason == "refusal":
            raise ClaudeError(f"Claude declined: {getattr(response, 'stop_details', None)}")
        if response.stop_reason == "max_tokens":
            raise ClaudeError("response cut off at max_tokens")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise ClaudeError("no text block in response")
        try:
            parsed = model.model_validate_json(text)
        except Exception as e:
            raise ClaudeError(f"invalid output: {e}") from e
        u = response.usage
        meta = {"model": response.model, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                "cache_read_tokens": getattr(u, "cache_read_input_tokens", 0)}
        return parsed, meta
