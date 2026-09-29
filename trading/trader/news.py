"""Read-only news fetch from Alpaca's News API (Benzinga headlines), sanitised and cached.

Source of truth: reports/Market psychology and news signals.md (definitions and section 6), owner decisions 7 and 8.

Safety rules this module follows (section 6, "Injection guards in code"):
- Public data only (owner decision 7): the only call is Alpaca's read-only `/news` endpoint.
- Headlines are data, never instructions. Each item is sanitised here, before it is cached or used:
  URLs, HTML markup and control characters are stripped and the text is cut to `max_headline_chars`
  (300 by default, `news.max_headline_chars` in config/risk_policy.yaml).
- Only these fields are kept: {id, created_at, symbols, headline, source}. No summary, body, author, URL or images.
- Nothing in this module passes text to Claude. `trader/news_signals.py` turns headlines into numbers and fixed labels.
- A headline cannot add a ticker: symbol tags must look like tickers, and the signal code only reads symbols that are
  on the caller's universe (the owner's allowlist).
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from .config import STATE_DIR

SOURCE = "alpaca_benzinga"
SANITIZER_VERSION = "news-sanitize-v1"
MAX_HEADLINE_CHARS = 300
MAX_PAGES = 1000  # hard stop so a broken page token can never loop forever

_URL = re.compile(r"(?:https?://|ftp://|www\.)\S+"
                  # bare domain with a path ("evil.example/pay"); the last label needs 2+ letters so "3.5/share" stays
                  r"|\b(?:[\w-]+\.)+[a-z]{2,}[\w-]*/\S*"
                  # bare domain on a common web TLD ("buy-now.io")
                  r"|\b(?:[\w-]+\.)+(?:com|net|org|io|co|info|biz|xyz|ly|me|app|gg|ru|cn|tk)\b\S*",
                  re.IGNORECASE)
_TAG = re.compile(r"<[^>]*>")
_SPACES = re.compile(r"\s+")
_TICKER = re.compile(r"^[A-Z][A-Z0-9.\-/]{0,11}$")


# --- sanitising ---------------------------------------------------------------------------------


def sanitize_headline(text: Any, max_chars: int = MAX_HEADLINE_CHARS) -> str:
    """Section 6 guard: plain text only, no URLs, markup or control characters, at most `max_chars` long."""
    if text is None:
        return ""
    text = html.unescape(str(text))
    text = _TAG.sub(" ", text)
    text = _URL.sub(" ", text)
    text = "".join(" " if unicodedata.category(ch).startswith("C") else ch for ch in text)
    text = _SPACES.sub(" ", text).strip()
    return text[: max(0, int(max_chars))].rstrip()


def clean_symbols(symbols: Any) -> list[str]:
    """Ticker-shaped symbol tags only, upper case, no duplicates. Anything else is dropped."""
    if isinstance(symbols, str):
        symbols = symbols.split(",")
    out: list[str] = []
    for s in symbols or []:
        s = str(s).strip().upper()
        if _TICKER.match(s) and s not in out:
            out.append(s)
    return out


def sanitize_item(raw: Any, max_chars: int = MAX_HEADLINE_CHARS) -> dict | None:
    """One API article (SDK object or dict) -> {id, created_at, symbols, headline, source}, or None if unusable.

    `created_at` is kept (never `updated_at`, per the report's definitions) as an ISO-8601 UTC string.
    """
    get = raw.get if isinstance(raw, dict) else (lambda k, d=None: getattr(raw, k, d))
    created = _iso_utc(get("created_at"))
    headline = sanitize_headline(get("headline"), max_chars)
    if created is None or not headline:
        return None
    source = sanitize_headline(get("source") or "benzinga", 40).lower() or "benzinga"
    return {"id": str(get("id") if get("id") is not None else ""), "created_at": created,
            "symbols": clean_symbols(get("symbols")), "headline": headline, "source": source}


def _iso_utc(x: Any) -> str | None:
    """Timestamp -> 'YYYY-MM-DDTHH:MM:SSZ' in UTC. A time without zone is taken as UTC (the API sends UTC)."""
    if x is None or x == "":
        return None
    try:
        ts = pd.Timestamp(x)
    except (ValueError, TypeError):
        return None
    if pd.isna(ts):
        return None
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


# --- fetching -----------------------------------------------------------------------------------


def fetch_news(symbols: list[str], start, end, *, client: Any = None, cache_dir: Path | str | None = None,
               max_headline_chars: int | None = None, policy: dict | None = None, refresh: bool = False,
               now: Callable[[], datetime] | None = None) -> list[dict]:
    """Sanitised Benzinga headlines tagged with any of `symbols`, from `start` to `end` (dates or datetimes).

    Pages through the API with `next_page_token`. Results are cached as JSON under `state/cache/news/`; a cached
    window is reused only when it ended before today (New York) AND the cached copy was itself fetched after the
    window's last day was over, so a copy written partway through a day is never frozen as final.
    `client` is an Alpaca `NewsClient` (or a fake with `get_news(request)`); without one, keys come from the
    environment like the bar data (ALPACA_DATA_* or ALPACA_RULES_*). Items are sorted by `created_at`, then id.
    """
    max_chars = _max_chars(max_headline_chars, policy)
    symbols = clean_symbols(symbols)
    if not symbols:
        return []
    now_fn = now or (lambda: datetime.now(timezone.utc))
    path = cache_path(symbols, start, end, cache_dir)
    if not refresh and _cache_is_final(end, now_fn()):
        cached = _read_cache(path, max_chars)
        if cached is not None and _fetched_after(cached[1].get("fetched_at"), end):
            return cached[0]
    items = _fetch_all(symbols, start, end, client or _default_client(), max_chars)
    _write_cache(path, items, symbols, start, end, max_chars, now_fn())
    return items


def _max_chars(max_headline_chars: int | None, policy: dict | None) -> int:
    if max_headline_chars is not None:
        return int(max_headline_chars)
    block = (policy or {}).get("news", policy or {})
    return int(block.get("max_headline_chars", MAX_HEADLINE_CHARS))


def _default_client():
    from alpaca.data.historical.news import NewsClient

    from .data import _env_key_pair

    key, secret = _env_key_pair()
    return NewsClient(key, secret)


def _request(symbols: list[str], start, end, page_token: str | None):
    """The SDK request object when alpaca-py is installed, else a plain dict (fakes accept either)."""
    from .data import _as_utc

    fields = {"symbols": ",".join(symbols), "start": _as_utc(start, end_of_day=False),
              "end": _as_utc(end, end_of_day=True), "sort": "asc", "include_content": False,
              "exclude_contentless": False, "limit": None, "page_token": page_token}
    try:
        from alpaca.data.requests import NewsRequest
    except ImportError:  # pragma: no cover - alpaca-py is a dependency
        return fields
    return NewsRequest(**{k: v for k, v in fields.items() if v is not None})


def _fetch_all(symbols: list[str], start, end, client: Any, max_chars: int) -> list[dict]:
    """Every page; each raw article is sanitised immediately and never stored raw."""
    items: dict[str, dict] = {}
    token: str | None = None
    for _ in range(MAX_PAGES):
        articles, token = _page(client.get_news(_request(symbols, start, end, token)))
        for raw in articles:
            item = sanitize_item(raw, max_chars)
            if item is not None:
                items[item["id"] or f"{item['created_at']}|{item['headline']}"] = item
        if not token:
            break
    return sorted(items.values(), key=lambda it: (it["created_at"], it["id"]))


def _page(response: Any) -> tuple[list, str | None]:
    """(articles, next_page_token) from an SDK NewsSet, a raw dict or a plain list."""
    if isinstance(response, list):
        return response, None
    if isinstance(response, dict):
        return list(response.get("news", [])), response.get("next_page_token")
    data = getattr(response, "data", None) or {}
    return list(data.get("news", [])), getattr(response, "next_page_token", None)


# --- cache --------------------------------------------------------------------------------------


def cache_path(symbols: list[str], start, end, cache_dir: Path | str | None = None) -> Path:
    """`<state>/cache/news/news_<start>_<end>_<hash of symbols>.json`."""
    base = Path(cache_dir) if cache_dir is not None else STATE_DIR / "cache" / "news"
    key = hashlib.sha1(",".join(sorted(clean_symbols(symbols))).encode()).hexdigest()[:10]
    return base / f"news_{_day(start)}_{_day(end)}_{key}.json"


def _day(x) -> str:
    return pd.Timestamp(x).strftime("%Y-%m-%d")


def _cache_is_final(end, now: datetime) -> bool:
    """A window is final once its last day is before today in New York."""
    now = pd.Timestamp(now)
    if now.tzinfo is not None:
        now = now.tz_convert("America/New_York").tz_localize(None)
    return pd.Timestamp(_day(end)) < now.normalize()


def _fetched_after(fetched_at, end) -> bool:
    """True when the cached copy was fetched on a New York day after the window's last day (so it is complete).
    A missing or unreadable `fetched_at` counts as not final."""
    ts = pd.Timestamp(fetched_at) if fetched_at else None
    if ts is None or pd.isna(ts):
        return False
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts
    return ts.tz_convert("America/New_York").tz_localize(None).normalize() > pd.Timestamp(_day(end))


def _read_cache(path: Path, max_chars: int) -> tuple[list[dict], dict] | None:
    """(cached items, meta), items re-sanitised on read (a hand-edited cache file cannot smuggle text past the guard)."""
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return None
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    clean = [sanitize_item(it, max_chars) for it in items if isinstance(it, dict)]
    return [it for it in clean if it is not None], meta


def _write_cache(path: Path, items: list[dict], symbols: list[str], start, end, max_chars: int,
                 now: datetime) -> None:
    meta = {"source": SOURCE, "sanitizer": SANITIZER_VERSION, "symbols": symbols, "start": _day(start),
            "end": _day(end), "max_headline_chars": max_chars, "fetched_at": _iso_utc(now)}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"meta": meta, "items": items}))
    except OSError:
        pass  # the cache is a convenience; a read-only disk must not stop the run
