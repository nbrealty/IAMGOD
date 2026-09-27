"""Option B: Claude's decisions come from files that a Claude Code session writes, not from API calls.

1. prepare -> write_pending(): state/<book>/pending/<date>/{context.json, schema.json, instructions.md}
2. the session -> decision_<k>.json (Claude book) or review_<k>.json (rules book), k = 1..samples,
   each written by an independent subagent that never reads the other samples (guide 8)
3. run -> find_decision_files() + SessionAdvisor: the file must match schema.json (CL-1: no unknown or
   missing keys), then the same pydantic validation as the API path.
   Missing or invalid files: the Claude book holds (stops still enforced); the rules book runs unreviewed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .config import CONFIG_DIR, STATE_DIR, Config
from .llm import (
    BOOK_ROLE,
    ROLE_MODEL,
    ROLE_TEXT,
    ClaudeError,
    jsonable,
    load_json,
    main_model,
    prompt_version,
    reference_text,
)
from .schemas import CONTEXT_SCHEMA, SCHEMA_VERSION, DecisionError, parse_decision, parse_review, strict_schema
from .state import fingerprint

FILE_PREFIX = {"claude": "decision", "rules": "review"}
STALE_DIR = "stale"
_LIST_KEYS = {"review": ("skip_entries", "halve_sleeves", "predictions"), "decide": ("actions", "predictions")}
_KEEP = {"choice": "keep", "reason_code": "NONE", "evidence": []}


def pending_dir(book: str, date: str, state_dir: Path = STATE_DIR) -> Path:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)) or not re.fullmatch(r"\w+", str(book)):
        raise ValueError(f"bad book or date for a pending folder: {book!r}, {date!r} (dates are YYYY-MM-DD)")
    return Path(state_dir) / book / "pending" / date


def _role(book: str) -> str:
    if book not in BOOK_ROLE:
        raise ValueError(f"unknown book {book!r}; use 'rules' or 'claude'")
    return BOOK_ROLE[book]


# --- writing the day's pending folder --------------------------------------------------------------


def write_pending(book: str, date: str, context: dict, cfg: Config, state_dir: Path = STATE_DIR,
                  samples: int | None = None, config_dir: Path = CONFIG_DIR) -> dict[str, Path]:
    """Write context.json, schema.json and instructions.md for today's session.

    Decision files left over from an earlier prepare of the same date are moved into `stale/`, because
    they answered a different context. Returns {"dir", "context", "schema", "instructions"} (+ "stale").
    """
    role = _role(book)
    n = _samples(cfg, samples)
    folder = pending_dir(book, date, state_dir)
    folder.mkdir(parents=True, exist_ok=True)
    out = {"dir": folder}
    moved = _archive_stale(book, date, state_dir)
    if moved:
        out["stale"] = folder / STALE_DIR
    out["context"] = _write(folder / "context.json", json.dumps(jsonable(context), indent=2, allow_nan=False))
    out["schema"] = _write(folder / "schema.json", json.dumps(session_schema(role), indent=2))
    out["instructions"] = _write(folder / "instructions.md", instructions_text(book, date, cfg, n, config_dir))
    return out


def session_schema(role: str) -> dict:
    """The strict schema of the role's model plus the optional "meta" object the session may add."""
    schema = strict_schema(ROLE_MODEL[role])
    schema["properties"]["meta"] = {
        "type": "object",
        "properties": {"model": {"type": "string"}, "sample": {"type": "integer"}},
        "additionalProperties": False,
    }
    return schema  # "meta" is deliberately not in "required"


def _samples(cfg: Config, samples: int | None) -> int:
    n = samples if samples is not None else cfg.playbook.get("claude", {}).get("samples", 3)
    return max(1, int(n))


def _archive_stale(book: str, date: str, state_dir: Path) -> list[Path]:
    folder = pending_dir(book, date, state_dir)
    moved = []
    for f in find_decision_files(book, date, state_dir):
        target = folder / STALE_DIR / f.name
        target.parent.mkdir(exist_ok=True)
        i = 2
        while target.exists():
            target = folder / STALE_DIR / f"{f.stem}.{i}{f.suffix}"
            i += 1
        f.replace(target)
        moved.append(target)
    return moved


def _write(path: Path, text: str) -> Path:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)
    return path


# --- instructions.md ------------------------------------------------------------------------------


def example_file(book: str, date: str, k: int) -> dict:
    """A minimal valid file: follow the rules today, no deviations (the usual right answer)."""
    common = {
        "schema_version": SCHEMA_VERSION,
        "date": date,
        "temperature_ack": "One sentence on the market temperature and what it means today.",
        "likely_error": {"kind": "none", "note": "One sentence."},
        "flags": [],
        "predictions": [],
        "journal_note": "Up to five plain-English sentences.",
    }
    if _role(book) == "review":
        body = {**common, "skip_entries": [], "halve_sleeves": []}
    else:
        body = {**common, "market_view": "One or two sentences.",
                "sleeve_weights": {s: dict(_KEEP) for s in "ABCD"}, "actions": []}
    return {**body, "meta": {"model": "<the model you are>", "sample": k}}


_ITEM_SHAPES = {
    "review": {
        "skip_entries[]": {"symbol": "<SYMBOL>", "sleeve": "C", "reason_code": "<one skip code>",
                           "evidence": ["<path into context.json>"], "prediction_id": "p1",
                           "event_date": "<YYYY-MM-DD or empty>", "verified": False},
        "halve_sleeves[]": {"sleeve": "B", "reason_code": "<one skip code>", "evidence": ["<path>"],
                            "prediction_id": "p2", "event_date": ""},
    },
    "decide": {
        "actions[]": {"symbol": "<SYMBOL>", "sleeve": "<A|B|C|D>", "size": "<rule|half_rule|hold|exit|pct>",
                      "target_pct_equity": 0.02, "stop": "<rule|tight|keep|none>", "reason_code": "<code>",
                      "evidence": ["<path into context.json>"], "prediction_id": "p1", "rationale": "<why>",
                      "event_date": ""},
        "sleeve_weights.<S>": {"choice": "<keep|up|down|rule|default>", "reason_code": "<NONE or a raise code>",
                               "evidence": []},
    },
}
_PREDICTION_SHAPE = {"id": "p1", "symbol": "<SYMBOL>", "horizon": 20, "direction": "<above|below>",
                     "threshold_pct": 0.0, "probability": 0.5, "linked_decision": "<e.g. action:C:SYMBOL>"}

_TEMPLATE = """# {title} for {date}

Book: {book}. Samples wanted: {samples}. Folder: this file's folder (state/{book}/pending/{date}/).
Code version tags: prompt_version {version}, schema_version {schema_version}, context_schema {context_schema}.

## How to write the files
1. Read `context.json` (today's data, computed by code), `schema.json` (the exact format) and this file.
   Nothing else is evidence: no news, no web, no memory of prices.
2. Write {samples} files in this folder: {names}.
   Each is ONE JSON object that matches `schema.json`. Valid JSON only: no comments, no trailing commas,
   no NaN or Infinity.
3. Every key in `schema.json` is required, in the file and in every list item, and no other key is
   allowed. A misspelled or missing top-level key throws the whole file away; a list item with a
   misspelled or missing key is dropped on its own.
4. Every file must contain `"date": "{date}"`. A file for another date, or with no date, is thrown away.
5. You may add `"meta": {{"model": "<the model you are>", "sample": <k>}}`. Nothing else outside the schema.
6. Produce every sample independently: one fresh subagent per file. It reads only context.json, schema.json
   and this file, and must NOT read or copy another {prefix}_*.json file. A file identical to another one
   that changes the plan is thrown away, because the point of several samples is to measure how much
   independent answers agree (guide 8).
   A change is acted on only when a majority of the {samples} samples makes it; a missing or invalid
   sample counts as following the rules.
7. Do not edit context.json, schema.json or this file, and do not run any trading command. The parent
   session runs `python -m trader run --book {book} --session` afterwards; code validates every file with
   the same rules as the API path. A bad item is dropped on its own; an unreadable file is thrown away;
   if no file is valid the {fallback}.

## The smallest valid file (following the rules, the usual right answer)
```json
{example}
```

## Shapes of the list items (placeholders in <angle brackets>; use real values from context.json)
```json
{shapes}
```

## Where things are in context.json
{layout}

## Your role
{role_text}

## Playbook brief and risk policy
{reference}
"""


_COMMON_LAYOUT = """- account: equity, cash, drawdown, breakers (plain-English reasons; an empty list means none tripped),
  open_risk_heat_pct and the sleeve latches. regime: label, temperature and the sleeve permissions.
- positions: every open lot with its qty, entry, stop, price and pct_equity.
- rule_signals.<S>: what the rules do today in sleeve S: targets (target_pct_equity is a fraction of equity),
  indicators (sleeve C shows only its 15 names with the highest peer RS, rs_pct) and notes.
- data_problems: symbols whose data failed a check today (no increases in them).
- TEST FIRST shadow signals are not in the context: they are never traded and never evidence.
- Evidence paths must point at a value that exists and is not null or empty; an empty list is not evidence.
- This file, schema.json and context.json replace the rulebook for you: do not read other files."""

_LAYOUT = {
    "decide": _COMMON_LAYOUT + """
- menus["S:SYM"] (for example menus["C:NVDA"]): the numbers behind each choice for one symbol in one sleeve:
  current_pct, rule_pct, half_rule_pct (fractions of equity), eligible_increase (false means an increase is
  dropped, with why_not_eligible) and stops {rule, tight, keep}. Today's C candidate list is the C menus with
  eligible_increase true.
- weights: current, rules, menu[S][choice] (the weight each choice would give, after every limit) and
  change_allowed[S] (false: the weight cannot move today).""",
    "review": _COMMON_LAYOUT + """
- planned_increases: the B, C and D entries and adds the rules will send today; only these can be skipped,
  and their sleeves halved.""",
}


def instructions_text(book: str, date: str, cfg: Config, samples: int, config_dir: Path = CONFIG_DIR) -> str:
    role = _role(book)
    prefix = FILE_PREFIX[book]
    shapes = {**_ITEM_SHAPES[role], "predictions[]": _PREDICTION_SHAPE}
    return _TEMPLATE.format(
        title="Claude book decision" if role == "decide" else "Rules book review",
        date=date, book=book, samples=samples, prefix=prefix,
        version=prompt_version(role, config_dir), schema_version=SCHEMA_VERSION, context_schema=CONTEXT_SCHEMA,
        names=", ".join(f"`{prefix}_{k}.json`" for k in range(1, samples + 1)),
        fallback=("Claude book holds its positions (stops still enforced)" if role == "decide"
                  else "rules book runs unreviewed"),
        example=json.dumps(example_file(book, date, 1), indent=2),
        shapes=json.dumps(shapes, indent=2),
        role_text=ROLE_TEXT[role],
        layout=_LAYOUT[role],
        reference=reference_text(config_dir),
    )


def instructions_version(book: str) -> str:
    """Hash of the fixed parts of instructions.md (the template, not today's data)."""
    return fingerprint(_TEMPLATE, _LAYOUT.get(_role(book), "") if book in FILE_PREFIX else "",
                       json.dumps(_ITEM_SHAPES, sort_keys=True), json.dumps(_PREDICTION_SHAPE),
                       FILE_PREFIX.get(book, ""))


def prepared_samples(folder: Path) -> int | None:
    """The number of samples the day's instructions.md asked for, if that file is there."""
    try:
        m = re.search(r"Samples wanted: (\d+)\.", (Path(folder) / "instructions.md").read_text())
    except OSError:
        return None
    return int(m.group(1)) if m else None


# --- finding and reading the session's files -------------------------------------------------------


def find_decision_files(book: str, date: str, state_dir: Path = STATE_DIR) -> list[Path]:
    """decision_*.json / decision.json (Claude book) or review_*.json / review.json (rules book), in sample order."""
    folder = pending_dir(book, date, state_dir)
    if not folder.is_dir():
        return []
    prefixes = [FILE_PREFIX[book]] if book in FILE_PREFIX else list(FILE_PREFIX.values())
    files = [f for p in prefixes for pattern in (f"{p}_*.json", f"{p}.json") for f in folder.glob(pattern)
             if f.is_file()]
    return sorted(files, key=_sample_order)


def _sample_order(path: Path) -> tuple:
    m = re.fullmatch(r"(\w+?)_(\d+)", path.stem)
    return (path.stem.split("_")[0], 0, int(m.group(2)), "") if m else (path.stem.split("_")[0], 1, 0, path.stem)


def _key_problems(value, schema: dict) -> list[str]:
    """CL-1: keys in `value` that break the strict schema (unknown or missing), at any depth.

    Types and allowed values are left to pydantic; this catches what pydantic lets through silently
    (an unknown key is ignored and a missing one gets a default).
    """
    out: list[str] = []
    if isinstance(value, dict) and schema.get("type") == "object" and "properties" in schema:
        props = schema["properties"]
        unknown = [str(k) for k in value if k not in props]
        missing = [k for k in schema.get("required", []) if k not in value]
        if unknown:
            out.append("unknown key(s) " + ", ".join(unknown))
        if missing:
            out.append("missing key(s) " + ", ".join(missing))
        for k, sub in props.items():
            if k in value:
                out += [f"{k}: {p}" for p in _key_problems(value[k], sub)]
    elif isinstance(value, list) and isinstance(schema.get("items"), dict):
        for i, v in enumerate(value):
            out += [f"[{i}] {p}" for p in _key_problems(v, schema["items"])]
    return out


def _label(item, i: int):
    return (item.get("symbol") or item.get("sleeve") or item.get("id") or i) if isinstance(item, dict) else i


def strict_filter(raw: dict, role: str, name: str, problems: list[str]) -> dict | None:
    """CL-1 on a session file (the API path gets this from strict structured outputs).

    A list item with an unknown or missing key is dropped on its own, and a sleeve_weights choice
    becomes "keep" (guide 4). Any other mismatch with the schema, or no date, drops the whole file (None).
    """
    schema = strict_schema(ROLE_MODEL[role])
    props = schema["properties"]
    out = dict(raw)
    for key in _LIST_KEYS[role]:
        if not isinstance(out.get(key), list):
            continue
        good = []
        for i, item in enumerate(out[key]):
            bad = _key_problems(item, props[key]["items"])
            if bad:
                problems.append(f"{name}: {key}[{_label(item, i)}]: dropped, {'; '.join(bad)}")
            else:
                good.append(item)
        out[key] = good
    if role == "decide" and isinstance(out.get("sleeve_weights"), dict):
        sw = props["sleeve_weights"]
        choices = {}
        for s, value in out["sleeve_weights"].items():
            if s not in sw["properties"]:
                problems.append(f"{name}: sleeve_weights.{s}: unknown sleeve, ignored")
                continue
            bad = _key_problems(value, sw["properties"][s])
            if bad:
                problems.append(f"{name}: sleeve_weights.{s}: kept as 'keep', {'; '.join(bad)}")
            choices[s] = dict(_KEEP) if bad else value
        for s in sw["properties"]:
            if s not in choices:
                problems.append(f"{name}: sleeve_weights.{s}: missing, kept as 'keep'")
                choices[s] = dict(_KEEP)
        out["sleeve_weights"] = choices
    bad = _key_problems(out, schema)
    if bad:
        problems.append(f"{name}: dropped, does not match schema.json (CL-1): {'; '.join(bad)}")
        return None
    if not isinstance(out.get("date"), str) or not out["date"].strip():
        problems.append(f"{name}: dropped, no date (every file must say which day it answers)")
        return None
    return out


def _model_name(file_meta) -> str:
    model = file_meta.get("model") if isinstance(file_meta, dict) else None
    if not isinstance(model, str) or not model.strip() or "<" in model or ">" in model:
        return "unknown"  # absent, or the placeholder copied from the example
    return model.strip()


def _changes_nothing(dump: dict) -> bool:
    """A parsed file that follows the rules: no actions, skips or halves, and every sleeve weight kept."""
    if dump.get("actions") or dump.get("skip_entries") or dump.get("halve_sleeves"):
        return False
    weights = dump.get("sleeve_weights") or {}
    return all((w or {}).get("choice", "keep") in (None, "keep") for w in weights.values())


class SessionAdvisor:
    """Reads the session's files. Same interface as llm.ClaudeAdvisor: (list of samples, meta).

    samples_requested is `samples` when given, else the number of files passed. from_pending uses the
    count the day's instructions.md asked for, so a sample that was never written still counts as missing.
    """

    mode = "session"

    def __init__(self, files: list[Path | str], expected_date: str, cfg: Config, config_dir: Path = CONFIG_DIR,
                 samples: int | None = None):
        self.files = [Path(f) for f in files]
        self.expected_date = expected_date
        self.cfg = cfg
        self.config_dir = config_dir
        self.samples = samples if samples is not None else (len(self.files) or None)

    @classmethod
    def from_pending(cls, book: str, date: str, cfg: Config, state_dir: Path = STATE_DIR,
                     config_dir: Path = CONFIG_DIR) -> "SessionAdvisor":
        folder = pending_dir(book, date, state_dir)
        return cls(find_decision_files(book, date, state_dir), date, cfg, config_dir,
                   samples=prepared_samples(folder) or _samples(cfg, None))

    def review_rules_plan(self, context: dict) -> tuple[list, dict]:
        return self._read("review", context)

    def decide(self, context: dict) -> tuple[list, dict]:
        return self._read("decide", context)

    def _read(self, role: str, context: dict | None) -> tuple[list, dict]:
        book = "rules" if role == "review" else "claude"
        prefix = FILE_PREFIX[book]
        parse = parse_review if role == "review" else parse_decision
        requested = _samples(self.cfg, self.samples)
        meta = {"mode": "session", "role": role, "model": None, "model_source": "self-reported", "models": [],
                "files": [],
                "fallback_used": None, "low_confidence": False, "input_tokens": 0, "output_tokens": 0,
                "usd": 0.0, "samples_requested": requested, "samples_valid": 0, "problems": [],
                "prompt_version": prompt_version(role, self.config_dir), "schema_version": SCHEMA_VERSION,
                "context_schema": CONTEXT_SCHEMA, "effort": None, "instructions_version": instructions_version(book)}
        ctx_date = (context or {}).get("date")
        if ctx_date and ctx_date != self.expected_date:
            meta["problems"].append(f"files are for {self.expected_date}, today's context is {ctx_date}")
            raise ClaudeError(meta["problems"][-1], meta=meta)
        valid, seen = [], []
        for f in self.files:
            parsed, model = self._read_one(f, role, parse, meta["problems"])
            if parsed is None:
                continue
            dump = parsed.model_dump()
            if dump in seen:
                if not _changes_nothing(dump):  # a copied change must never build a majority
                    meta["problems"].append(f"{f.name}: identical to an earlier file that changes the plan, "
                                            "dropped (samples must be independent)")
                    continue
                # Independent samples that all follow the rules can agree word for word; dropping them would
                # read unanimous agreement as low confidence (guide 8). Kept, and counted.
                meta["identical_samples"] = meta.get("identical_samples", 0) + 1
                meta["problems"].append(f"{f.name}: identical to an earlier file that follows the rules; kept")
            seen.append(dump)
            valid.append(parsed)
            meta["models"].append(model)
            meta["files"].append(f.name)
        meta["samples_valid"] = len(valid)
        meta["model"] = main_model(meta["models"], "unknown")
        if len(valid) < requested:
            meta["problems"].append(f"{len(valid)} valid file(s), {requested} wanted")
        if valid and len(valid) < requested // 2 + 1:  # guide 8: no majority can form among the valid ones
            meta["low_confidence"] = True
            meta["problems"].append(f"low confidence: only {len(valid)} of {requested} samples are valid; "
                                    "the missing ones count as following the rules")
        if not valid:
            where = self.files[0].parent if self.files else "the pending folder"
            raise ClaudeError(f"no valid {prefix} file in {where}: " + "; ".join(meta["problems"][-3:]), meta=meta)
        return valid, meta

    def _read_one(self, path: Path, role: str, parse, problems: list[str]):
        """(parsed, model) or (None, None) with a problem line. One bad file never sinks the others."""
        book = "rules" if role == "review" else "claude"
        other = FILE_PREFIX["claude" if book == "rules" else "rules"]
        if path.name.startswith(other + "_") or path.stem == other:
            problems.append(f"{path.name}: not a {FILE_PREFIX[book]} file, ignored")
            return None, None
        try:
            raw, odd = load_json(path.read_text())
        except OSError as e:
            problems.append(f"{path.name}: unreadable, dropped ({type(e).__name__})")
            return None, None
        except ValueError as e:
            problems.append(f"{path.name}: not valid JSON, dropped ({e})")
            return None, None
        if not isinstance(raw, dict):
            problems.append(f"{path.name}: top level must be a JSON object, dropped")
            return None, None
        if odd:
            problems.append(f"{path.name}: {', '.join(odd)} is not JSON; read as null")
        model = _model_name(raw.pop("meta", None))
        raw = strict_filter(raw, role, path.name, problems)
        if raw is None:
            return None, None
        try:
            parsed, item_problems = parse(raw, self.expected_date)
        except DecisionError as e:
            problems.append(f"{path.name}: dropped, {e}")
            return None, None
        problems += [f"{path.name}: {p}" for p in item_problems]
        return parsed, model
