"""OPT-35 chain logger and the OPT-41 completeness count (Options rulebook phase O0).

Each run (after the close, `when="close"`, and the 15:45 ET order run, `when="1545"`) writes one gzip JSON
snapshot of SPY, QQQ and IWM to `state_dir/options/chains/<date>/<when>.json.gz`, plus one row in
`state_dir/options/chains/chain_log_index.json`: {date, when, n, complete, problems, ...}.
OPT-41 needs >= 40 sessions with a complete logged chain; `complete_sessions` counts them (a missing day does
not count and does not reset the count). A run is complete only when SPY, QQQ and IWM (OPT-35's required set)
are all logged and complete. The logged chains are our only history of option quotes, so they are protected:
a failed re-run never replaces a complete snapshot, and a corrupt index is set aside and rebuilt from the
snapshot files instead of being reset.

VIX, VIX3M, VIX9D and SKEW come from Cboe's public CSVs for display only: cached, never required, and a
failure never makes a snapshot incomplete. Owner decision 7: public data only, every source is recorded.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import math
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

from . import chain
from .models import OptionQuote, is_occ, parse_occ

NY = ZoneInfo("America/New_York")
DEFAULT_UNDERLYINGS = ("SPY", "QQQ", "IWM")
WHENS = ("close", "1545")
INDEX_FILE = "chain_log_index.json"
CBOE_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{name}_History.csv"
CBOE_NAMES = ("VIX", "VIX3M", "VIX9D", "SKEW")

# A snapshot is complete only when every underlying passes all of these (OPT-41 counts complete sessions).
MIN_CONTRACTS = 20  # per underlying; SPY/QQQ/IWM within 70 DTE have hundreds
MIN_QUOTE_SHARE = 0.90  # bid, ask and quote time present
MIN_FRESH_SHARE = 0.80  # quote dated the session day (catches holidays and stale feeds)
MIN_GREEKS_SHARE = 0.50  # IV and delta present (far wings often have none)
MIN_OI_SHARE = 0.80  # open interest present


def log_chains(underlyings: Iterable[str] = DEFAULT_UNDERLYINGS, state_dir: str | Path | None = None, *,
               when: str = "close", now: datetime | None = None, fetch: Callable = chain.fetch_chain,
               extra_symbols: Iterable[str] = (), spots: dict | None = None,
               cboe_fetch: Callable[[str], str] | bool | None = True,
               required: Iterable[str] = DEFAULT_UNDERLYINGS) -> dict:
    """OPT-35: fetch, save and index one chain snapshot. Returns the index record plus `path` and `cboe`.

    `extra_symbols` are held or shadow legs; they are always logged, and their underlying is added when it
    is not in `underlyings`. `spots` optionally gives {underlying: spot}. `cboe_fetch(url) -> csv text`
    fetches Cboe CSVs (None skips them; `fetch_url` is the real one). One failing underlying never stops the
    others; it only makes the snapshot incomplete. `state_dir=None` means the configured state directory.
    The snapshot is complete only when every name in `required` (OPT-35: SPY, QQQ, IWM) is logged and complete.

    Never downgrade: when a complete snapshot already exists for this (date, when) and this run is incomplete,
    the good file and index row are kept; this run is saved as `<when>.failed-<HHMMSS>.json.gz` and noted in
    the kept row (`failed_reruns`). The returned record then has `kept_previous=True`.
    """
    if when not in WHENS:
        raise ValueError(f"when must be one of {WHENS}, got {when!r}")
    now = chain._as_utc(now)
    session = now.astimezone(NY).date().isoformat()
    state_dir = _dir(state_dir)
    extras = _clean_extras(extra_symbols)
    names = _underlyings(underlyings, extras)
    per: dict[str, dict] = {}
    for u in names:
        per[u] = _log_one(u, fetch, session, now, [s for s in extras if parse_occ(s)["underlying"] == u],
                          (spots or {}).get(u))
    cboe = _maybe_cboe(state_dir, cboe_fetch, now)
    snapshot = _snapshot(session, when, now, per, cboe, _required(required))
    path = snapshot_path(session, when, state_dir)
    previous = _complete_row(state_dir, session, when)
    if previous is not None and not snapshot["complete"]:
        path = path.with_name(f"{when}.failed-{now.astimezone(NY):%H%M%S}.json.gz")
        _write_gzip_json(path, snapshot)
        record = _index_record(snapshot, path, state_dir)
        kept = {**previous, "failed_reruns": list(previous.get("failed_reruns") or [])
                + [{"taken_at": record["taken_at"], "file": record["file"], "problems": record["problems"]}]}
        _update_index(state_dir, kept)
        return {**record, "path": str(path), "cboe": cboe, "kept_previous": True}
    _write_gzip_json(path, snapshot)
    record = _index_record(snapshot, path, state_dir)
    _update_index(state_dir, record)
    return {**record, "path": str(path), "cboe": cboe, "kept_previous": False}


def load_snapshot(date_: str | date, when: str, state_dir: str | Path | None = None) -> dict | None:
    """A saved snapshot with each underlying's `quotes` as `OptionQuote`s; None if missing or unreadable.

    Returning None (not raising) matters: exits must still work when the chain is missing.
    """
    try:
        path = snapshot_path(_iso(date_), when, state_dir)
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            snap = json.load(fh)
        for block in (snap.get("underlyings") or {}).values():
            block["quotes"] = [OptionQuote.from_dict(d) for d in block.get("quotes") or []]
    except (OSError, ValueError, TypeError, AttributeError, EOFError):
        return None
    return snap


def snapshot_quotes(snapshot: dict | None, underlying: str) -> list[OptionQuote]:
    """The `OptionQuote`s of one underlying in a loaded snapshot ([] when absent)."""
    if not snapshot:
        return []
    return list(((snapshot.get("underlyings") or {}).get(underlying.upper()) or {}).get("quotes") or [])


def snapshot_path(date_: str | date, when: str, state_dir: str | Path | None = None) -> Path:
    if when not in WHENS:
        raise ValueError(f"when must be one of {WHENS}, got {when!r}")
    return _dir(state_dir) / "options" / "chains" / _iso(date_) / f"{when}.json.gz"


def index_path(state_dir: str | Path | None = None) -> Path:
    return _dir(state_dir) / "options" / "chains" / INDEX_FILE


def load_index(state_dir: str | Path | None = None) -> list[dict]:
    """All completeness records, oldest first ([] when none or unreadable)."""
    rows = _read_index(_dir(state_dir))
    return rows or []


def complete_sessions(state_dir: str | Path | None = None, *, when: str | None = None,
                      through: str | date | None = None, required: Iterable[str] = DEFAULT_UNDERLYINGS) -> int:
    """OPT-41: number of distinct session dates with a complete logged chain.

    A row counts only when it is complete, every `required` underlying (OPT-35: SPY, QQQ, IWM) is in its
    `per_underlying` and complete, and its snapshot file still exists. `when` restricts the count to one run
    ("close" or "1545"); None counts a date when any run that day was complete. `through` ignores later dates.
    Missing days simply do not count; they never reset the count.
    """
    base = _dir(state_dir)
    need = _required(required)
    last = _iso(through) if through is not None else None
    dates = {r.get("date") for r in load_index(base)
             if _counts(r, need, base) and (when is None or r.get("when") == when)
             and (last is None or str(r.get("date")) <= last)}
    return len({d for d in dates if d})


def _counts(row: dict, need: list[str], base: Path) -> bool:
    per = row.get("per_underlying")
    if row.get("complete") is not True or not isinstance(per, dict):
        return False
    if not all(isinstance(per.get(u), dict) and per[u].get("complete") is True for u in need):
        return False
    file = row.get("file")
    return bool(file) and (base / str(file)).is_file()


def assess(quotes: list[OptionQuote], session: str, meta: dict | None = None) -> list[str]:
    """Reasons one underlying's chain is incomplete ([] means complete). See the MIN_* thresholds."""
    meta = meta or {}
    reasons = [f"fetch problem: {p}" for p in meta.get("fatal") or []]
    n = len(quotes)
    if n < MIN_CONTRACTS:
        return reasons + [f"only {n} contracts (need {MIN_CONTRACTS})"]
    checks = (
        ("bid/ask/quote time", MIN_QUOTE_SHARE,
         lambda q: q.bid is not None and q.ask is not None and q.quote_time is not None),
        ("quotes dated today", MIN_FRESH_SHARE, lambda q: _ny_date(q.quote_time) == session),
        ("IV and delta", MIN_GREEKS_SHARE, lambda q: q.iv is not None and q.delta is not None),
        ("open interest", MIN_OI_SHARE, lambda q: q.open_interest is not None),
    )
    for label, need, ok in checks:
        share = sum(1 for q in quotes if ok(q)) / n
        if share < need:
            reasons.append(f"{label} on {share:.0%} of contracts (need {need:.0%})")
    return reasons


# --- Cboe display values ----------------------------------------------------------------------------


def cboe_values(state_dir: str | Path | None, *, fetch: Callable[[str], str] | None = None,
                now: datetime | None = None, names: Iterable[str] = CBOE_NAMES) -> dict:
    """{name: {value, date, source, cached, stale?, error?}} for display only (REG-9, OPT-20 logging).

    Fetched on every call until the cached row is dated today (so the after-close run picks up the day's
    close even when the 15:45 run cached the previous one), cached in `state_dir/cache/cboe/`. On failure the last
    cached value is returned marked `stale`; with no cache the entry has only `error`. Never raises.
    """
    fetch = fetch or fetch_url
    today = chain._as_utc(now).astimezone(NY).date().isoformat()
    out = {}
    for name in names:
        out[name] = _cboe_one(_dir(state_dir), name, fetch, today)
    return out


def fetch_url(url: str, timeout: float = 10.0) -> str:
    """Plain HTTPS GET of a public CSV (read-only market data; used only outside tests)."""
    from urllib.request import Request, urlopen

    with urlopen(Request(url, headers={"User-Agent": "trader-chain-logger"}), timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_cboe_csv(text: str) -> tuple[str, float]:
    """(date ISO, value) of the last valid row. VIX-style files use CLOSE; SKEW uses its own column."""
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        raise ValueError("empty Cboe CSV")
    header = [h.strip().upper() for h in rows[0]]
    col = header.index("CLOSE") if "CLOSE" in header else len(header) - 1
    for row in reversed(rows[1:]):
        if len(row) > col:
            value = chain._num(row[col])
            day = _parse_us_date(row[0])
            if value is not None and value > 0 and day:
                return day, value
    raise ValueError("no valid row in Cboe CSV")


def _cboe_one(state_dir: Path, name: str, fetch, today: str) -> dict:
    cache = state_dir / "cache" / "cboe" / f"{name}.json"
    cached = _read_json(cache)
    if cached and cached.get("date") == today:  # already holds today's close: nothing newer to fetch
        return {**_public(cached), "cached": True}
    url = CBOE_URL.format(name=name)
    try:
        day, value = parse_cboe_csv(fetch(url))
    except Exception as e:
        if cached:
            return {**_public(cached), "cached": True, "stale": True, "error": chain._short(e)}
        return {"source": url, "error": chain._short(e)}
    entry = {"value": value, "date": day, "source": url, "fetched": today}
    _write_json(cache, entry)
    return {**_public(entry), "cached": False}


def _maybe_cboe(state_dir: Path, cboe_fetch, now: datetime) -> dict:
    """True -> the real fetcher; None/False -> skipped; a callable -> used (tests). Never raises."""
    if cboe_fetch is None or cboe_fetch is False:
        return {}
    try:
        return cboe_values(state_dir, fetch=None if cboe_fetch is True else cboe_fetch, now=now)
    except Exception as e:  # display only: never block the chain log
        return {"error": chain._short(e)}


def _public(entry: dict) -> dict:
    return {k: entry.get(k) for k in ("value", "date", "source")}


# --- snapshot building ------------------------------------------------------------------------------


def _log_one(underlying: str, fetch, session: str, now: datetime, extras: list[str], spot) -> dict:
    """Fetch one underlying; any exception becomes an incomplete block, never a crash."""
    try:
        got = fetch(underlying, extra_symbols=tuple(extras), spot=spot, now=now)
    except Exception as e:
        return {"n": 0, "complete": False, "reasons": [f"fetch failed ({chain._short(e)})"], "problems": [],
                "meta": {}, "quotes": []}
    quotes = [q for q in (got or []) if isinstance(q, OptionQuote)]
    meta = dict(getattr(got, "meta", {}) or {})
    problems = list(getattr(got, "problems", []) or [])
    reasons = assess(quotes, session, meta)
    missing = [s for s in extras if s not in {q.symbol for q in quotes}]
    if missing:  # OPT-35: every held/shadow leg is logged; an expired one is only noted
        problems.append(f"held/shadow legs not logged: {', '.join(missing)}")
        live = [s for s in missing if parse_occ(s)["expiry"] >= session]
        if live:  # the shadow book and the exits would have no quote for a live leg
            reasons.append(f"live held/shadow legs not logged: {', '.join(live)}")
    return {"n": len(quotes), "complete": not reasons, "reasons": reasons, "problems": problems, "meta": meta,
            "quotes": quotes}


def _snapshot(session: str, when: str, now: datetime, per: dict, cboe: dict,
              required: Iterable[str] = DEFAULT_UNDERLYINGS) -> dict:
    absent = [u for u in required if u not in per]
    complete = bool(per) and not absent and all(b["complete"] for b in per.values())
    return {
        "date": session, "when": when, "taken_at": now.isoformat(), "feed": chain.FEED,
        "source": dict(chain.SOURCE), "complete": complete, "n": sum(b["n"] for b in per.values()),
        "required": list(required), "reasons": [f"required underlying {u} not logged (OPT-35)" for u in absent],
        "underlyings": {u: {**{k: v for k, v in b.items() if k != "quotes"},
                            "quotes": [q.to_dict() for q in b["quotes"]]} for u, b in per.items()},
        "cboe": cboe,
    }


def _index_record(snapshot: dict, path: Path, state_dir: Path) -> dict:
    problems = list(snapshot.get("reasons") or [])
    for u, b in snapshot["underlyings"].items():
        problems += [f"{u}: {r}" for r in b["reasons"]]
    try:
        rel = str(path.relative_to(state_dir))
    except ValueError:
        rel = str(path)
    return {"date": snapshot["date"], "when": snapshot["when"], "taken_at": snapshot["taken_at"],
            "n": snapshot["n"], "complete": snapshot["complete"], "problems": problems,
            "required": list(snapshot.get("required") or []),
            "per_underlying": {u: {"n": b["n"], "complete": b["complete"], "contract_problems": len(b["problems"])}
                               for u, b in snapshot["underlyings"].items()},
            "feed": snapshot["feed"], "file": rel}


def _update_index(state_dir: Path, record: dict) -> None:
    """One row per (date, when): a re-run replaces the earlier row. Kept sorted oldest first.

    An index that exists but cannot be read is never overwritten blindly (that would reset the OPT-41
    count): it is moved to `chain_log_index.corrupt-<ts>.json` and the rows are rebuilt from the snapshots.
    """
    rows = _read_index(state_dir)
    if rows is None:
        rows = _rebuild_index(state_dir)
    rows = [r for r in rows if (r.get("date"), r.get("when")) != (record["date"], record["when"])]
    rows.append(record)
    rows.sort(key=lambda r: (str(r.get("date")), WHENS.index(r["when"]) if r.get("when") in WHENS else 9))
    _write_json(index_path(state_dir), rows)


def _read_index(state_dir: Path) -> list[dict] | None:
    """Index rows; [] when there is no index yet; None when the file exists but is unreadable or not a list."""
    path = index_path(state_dir)
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else None


def _rebuild_index(state_dir: Path) -> list[dict]:
    """Set the unreadable index aside and rebuild its rows from `<date>/<when>.json.gz` snapshot files."""
    path = index_path(state_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    try:
        os.replace(path, path.with_name(f"chain_log_index.corrupt-{stamp}.json"))
    except OSError:
        pass
    rows = []
    for when in WHENS:
        for snap_path in sorted(path.parent.glob(f"*/{when}.json.gz")):
            try:
                with gzip.open(snap_path, "rt", encoding="utf-8") as fh:
                    raw = json.load(fh)
                rows.append({**_index_record(raw, snap_path, state_dir), "rebuilt": True})
            except (OSError, ValueError, TypeError, KeyError, AttributeError, EOFError):
                continue
    return rows


def _complete_row(state_dir: Path, session: str, when: str) -> dict | None:
    """The index row for (session, when) if it is complete and its file still exists."""
    for r in _read_index(state_dir) or []:
        if (r.get("date"), r.get("when")) == (session, when) and r.get("complete") is True:
            file = r.get("file")
            if file and (state_dir / str(file)).is_file():
                return r
    return None


def _required(required: Iterable[str] | None) -> list[str]:
    if isinstance(required, str):
        required = [required]
    return list(dict.fromkeys(str(u).strip().upper() for u in (required or ()) if str(u or "").strip()))


def _underlyings(underlyings: Iterable[str], extras: list[str]) -> list[str]:
    if isinstance(underlyings, str):  # "SPY" is one underlying, not S, P and Y
        underlyings = [underlyings]
    names = [str(u).strip().upper() for u in (underlyings or ()) if str(u or "").strip()]
    names += [parse_occ(s)["underlying"] for s in extras]
    return list(dict.fromkeys(names))


def _clean_extras(extra_symbols: Iterable[str]) -> list[str]:
    syms = [str(s or "").strip().upper() for s in (extra_symbols or ())]
    return list(dict.fromkeys(s for s in syms if is_occ(s)))


# --- file helpers -------------------------------------------------------------------------------------


def _dir(state_dir) -> Path:
    if state_dir is None:
        from ..config import STATE_DIR

        return Path(STATE_DIR)
    return Path(state_dir)


def _json_safe(obj: Any) -> Any:
    """NaN and infinities become None anywhere in the structure (strict JSON on disk)."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def _write_gzip_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    os.close(fd)
    try:
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            json.dump(_json_safe(obj), fh, allow_nan=False, default=str)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(_json_safe(obj), fh, indent=1, allow_nan=False, default=str)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _iso(d) -> str:
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return date.fromisoformat(str(d).strip()[:10]).isoformat()


def _ny_date(ts: str | None) -> str | None:
    if not ts:
        return None
    try:
        return chain._as_utc(ts).astimezone(NY).date().isoformat()
    except (TypeError, ValueError):
        return None


def _parse_us_date(text: str) -> str | None:
    """Cboe dates are MM/DD/YYYY; ISO is accepted too."""
    text = str(text).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None
