"""NEWS-1..18: news and crowd signals computed by code from Benzinga headlines and daily bars.

Source of truth: reports/Market psychology and news signals.md, section 5 (exact rules) and section 6 (how Claude may
use them), owner decisions 7 and 8 in OPERATION_INVEST.md, and the `news:` block of config/risk_policy.yaml.

Every signal is TEST FIRST (shadow only). The one exception is owner decision 8 (as updated 28 Sept 2026): the
promotion part of NEWS-18 is active and blocks NEW longs or increases in sleeves B, C and D only (the engine applies
the sleeve scope). NEWS-4 (attention spike after a run-up) and NEWS-13 (lottery / MAX) are TEST FIRST: computed,
logged and shadow-scored, blocking only if `news.active_vetoes` lists them again. Nothing here creates, sizes or
sends an order.

Prompt-injection guard (section 6): the output holds only numbers, booleans and fixed labels. No headline text ever
leaves this module, so Claude can at most see a count or a tone score that a hostile headline changed.

Definitions used everywhere (report section 5):
- `r_t` close-to-close return; `AR_t = r_t(sym) - r_t(SPY)`; `sigma60` = std of AR over the PRIOR 60 sessions.
- `hl_t` = headlines tagged with the symbol, `created_at` after 16:00 ET of session t-1 and at or before 16:00 ET of
  session t (later ones belong to the next session). Near-duplicates (same symbol, same session, word-overlap
  similarity > 0.6) are dropped.
- `vr_t` = volume / mean volume of the prior 50 sessions.
- `neg_t` = mean headline tone (+1, 0, -1 per headline) from a fixed local word list (see TONE provenance below).

Output of `compute`: {signal_id: {symbol: row}}. Market-wide signals (NEWS-9..12) use the key "SPY". A row that cannot
be computed is {"skipped": "<reason>", "source": ...}. Every row records its "source" (owner decision 7: every signal
records where its data came from, skipped or not). Every computed row has "event" (bool) and "status": "active_veto"
only for the parts decision 8 makes binding AND that `news.active_vetoes` lists (by default NEWS-18's promotion
block only); everything else, including NEWS-18's single-headline guard, is "shadow" (section 6: shadow may not support a skip).

Fail-closed hype checks: NEWS-4 and NEWS-13 only block new longs, so when a name has a bar today but too little history
to score it (a new listing, a data gap), the row is a veto with `insufficient_history: True` instead of a silent skip.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd

BENCHMARK = "SPY"
NY = "America/New_York"
SIGNAL_IDS = [f"NEWS-{i}" for i in range(1, 19)]
# Owner decision 8 as updated 28 Sept 2026: only the (tightened) NEWS-18 promotion veto blocks; NEWS-4 and NEWS-13
# are TEST FIRST (computed, logged and shadow-scored, never blocking) unless the policy lists them again.
ACTIVE_VETO_DEFAULT = ["NEWS-18-PROMO"]
SOURCE_NEWS = "alpaca_benzinga+alpaca_bars"
SOURCE_BARS = "alpaca_bars"
SOURCE_IV = "alpaca_options_iv (not logged yet)"
SCORER_VERSION = "lm-subset-v1"
IV_SKIP = "needs IV history"
Z_CAP = 5.0  # z-scores are bounded, so one hostile headline can move a number only so far
MIN_RANK_NAMES = 10  # "top decile of the universe" needs at least 10 ranked names
DUP_SIMILARITY = 0.6
# Real paid-promotion wording only (decision 8, 28 Sept): the bare words "paid" / "sponsored" fired on ordinary
# headlines ("Apple paid $17bn in taxes", "30 million paid seats", "Sponsored Agents feature").
DEFAULT_PROMO_WORDS = ["paid promotion", "paid promotional", "paid advertisement", "paid advertising",
                       "sponsored content", "sponsored post", "sponsored article", "advertorial",
                       "investor awareness", "been compensated", "compensated to"]
DEFAULT_PROMO_SESSIONS = 20
HL_MIN_STD = 0.5  # z20(hl) std floor: one headline on a name with no news history gives z = 2, not the +5 cap
MIN_MAX21_RETURNS = 5  # MAX21 from the returns available in the last 21 sessions (a data gap must not hide a jump)
COST_PER_SIDE = 0.001  # EX-5: 10 bps per side for shadow entries filled at the next open

# --- fixed word lists -----------------------------------------------------------------------------
# TONE provenance: a small hand-picked subset of common words from the negative and positive categories of the
# Loughran-McDonald (2011) financial sentiment dictionary, plus plural/past forms. It is NOT the full dictionary.
# Frozen as SCORER_VERSION "lm-subset-v1"; changing a word means a new version (results must be reproducible).
NEGATIVE_WORDS = frozenset("""
loss losses lose losing lost decline declines declined declining drop drops dropped fell fall falls falling plunge
plunges plunged slump slumps slumped weak weaker weakness miss misses missed lawsuit lawsuits sued sue suing fraud
fraudulent probe probes investigation investigations recall recalls recalled bankruptcy bankrupt default defaults
downgrade downgrades downgraded layoffs layoff adverse warning warns warned delay delays delayed fail fails failed
failure negative penalty penalties fined halt halted crisis concern concerns disappoint disappoints disappointing
disappointed shortfall slowdown litigation violation violations deficit impairment unfavorable worst worse crash
crashes crashed tumble tumbles tumbled sink sinks sank sell-off selloff hack hacked breach
""".split())
POSITIVE_WORDS = frozenset("""
beat beats gain gains gained surge surges surged jump jumps jumped rally rallies rallied record strong stronger
strength growth grow grows upgrade upgrades upgraded raises raised approval approved profit profits profitable
outperform outperforms boost boosts boosted improve improves improved improvement exceed exceeds exceeded win wins
won success successful soar soars soared rebound rebounds rebounded favorable best
""".split())
# FUND keyword set (report section 5, verbatim).
FUND_WORDS = frozenset("""earnings eps revenue results guidance outlook downgrade upgrade recall deliveries fda
acquisition merger sec lawsuit bankruptcy""".split())
# Earnings-day words: NEWS-2 ("no FUND earnings words"), NEWS-14 and NEWS-16 ("results/EPS words").
EARNINGS_WORDS = frozenset({"earnings", "eps", "results", "revenue"})
# CEO name table for NEWS-8 (public figures, September 2026; the owner may edit). Multi-word names avoid common words.
CEO_NAMES = {
    "TSLA": [r"\bmusk\b"], "META": [r"\bzuckerberg\b"], "AMZN": [r"\bjassy\b", r"\bbezos\b"],
    "NVDA": [r"\bjensen huang\b", r"\bhuang\b"], "AAPL": [r"\btim cook\b"], "MSFT": [r"\bnadella\b"],
    "GOOGL": [r"\bpichai\b"], "JPM": [r"\bdimon\b"], "ORCL": [r"\bellison\b"], "AMD": [r"\blisa su\b"],
    "CRM": [r"\bbenioff\b"], "UBER": [r"\bkhosrowshahi\b"], "NFLX": [r"\bsarandos\b"],
}
# NEWS-18 extreme words, grouped by topic so "the only headline on that topic" can be counted.
EXTREME_TOPICS = {
    "explosion": r"\bexplo(?:sion|sions|de|des|ded)\b", "hack": r"\bhack(?:s|ed|er|ers|ing)?\b",
    "halt": r"\bhalt(?:s|ed|ing)?\b", "approved": r"\bapprov(?:al|als|e|ed|es)\b",
    "acquire": r"\bacqui(?:re|res|red|ring|sition|sitions)\b", "bankrupt": r"\bbankrupt(?:cy|cies)?\b",
    "fraud": r"\bfraud(?:s|ulent)?\b",
}
MACRO_PATTERN = re.compile(r"\btariffs?\b|\btrump\b|\btruth social\b", re.IGNORECASE)  # NEWS-9
RATING_DOWN = re.compile(r"\bdowngrad(?:e|es|ed|ing)\b|\bcuts? to\b|\b(?:lowers|lowered|cuts|cut|slashes|slashed|"
                         r"reduces|reduced) (?:its |fy |full-year |annual )?guidance\b", re.IGNORECASE)  # NEWS-15
RATING_UP = re.compile(r"\bupgrad(?:e|es|ed|ing)\b|\b(?:raises|raised|boosts|boosted|lifts|lifted) "
                       r"(?:its |fy |full-year |annual )?guidance\b", re.IGNORECASE)
STOP_WORDS = frozenset("a an the to of in on for and or at by with from as is are be its it this that".split())
_WORD = re.compile(r"[a-z0-9][a-z0-9'\-]*")


def tokens(text: str) -> list[str]:
    """Lower-case words of a headline."""
    return _WORD.findall(str(text).lower())


def headline_tone(text: str, symbols: Iterable[str] = ()) -> int:
    """+1, 0 or -1 for one headline: sign of (positive words - negative words) after anonymising names."""
    words = tokens(anonymise(text, symbols))
    pos = sum(w in POSITIVE_WORDS for w in words)
    neg = sum(w in NEGATIVE_WORDS for w in words)
    return int(np.sign(pos - neg))


def anonymise(text: str, symbols: Iterable[str] = ()) -> str:
    """Tickers and CEO names -> "the company" (report: score headlines with names replaced)."""
    for sym in symbols:
        text = re.sub(rf"(?<![A-Za-z0-9]){re.escape(sym)}(?![A-Za-z0-9])", "the company", text)
        for pattern in CEO_NAMES.get(sym, []):
            text = re.sub(pattern, "the company", text, flags=re.IGNORECASE)
    return text


def similarity(a: str, b: str) -> float:
    """Word-overlap similarity (Jaccard of word sets) used for near-duplicate removal."""
    wa, wb = set(tokens(a)), set(tokens(b))
    if not wa and not wb:
        return 1.0
    return len(wa & wb) / len(wa | wb)


def dedupe(headlines: list[str], threshold: float = DUP_SIMILARITY) -> list[str]:
    """Keep the first of any group of headlines with similarity > threshold (input in time order)."""
    kept: list[str] = []
    for h in headlines:
        if all(similarity(h, k) <= threshold for k in kept):
            kept.append(h)
    return kept


def novelty(today: list[str], previous: list[str]) -> float | None:
    """NEWS-5: 1 - max cosine(TF-IDF of today's headlines, each of the previous headlines). None if no news today."""
    if not today:
        return None
    if not previous:
        return 1.0
    docs = [_content(" ".join(today))] + [_content(p) for p in previous]
    df = Counter(w for d in docs for w in set(d))
    idf = {w: math.log((1 + len(docs)) / (1 + c)) + 1 for w, c in df.items()}
    vecs = [{w: n * idf[w] for w, n in Counter(d).items()} for d in docs]
    return float(1.0 - max(_cosine(vecs[0], v) for v in vecs[1:]))


def _content(text: str) -> list[str]:
    return [w for w in tokens(text) if w not in STOP_WORDS]


def _cosine(a: dict, b: dict) -> float:
    dot = sum(v * b.get(w, 0.0) for w, v in a.items())
    na, nb = math.sqrt(sum(v * v for v in a.values())), math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


def _has_any(text: str, words: frozenset) -> bool:
    return any(w in words for w in tokens(text))


def _phrase_hit(text: str, phrases: Iterable[str]) -> bool:
    low = text.lower()
    return any(re.search(rf"\b{re.escape(p.lower())}\b", low) for p in phrases)


def _rating(text: str) -> int:
    """NEWS-15: -1 for a downgrade / guidance cut, +1 for an upgrade / guidance raise, 0 otherwise."""
    return int(bool(RATING_UP.search(text))) - int(bool(RATING_DOWN.search(text)))


def _topics(text: str) -> set[str]:
    return {t for t, p in EXTREME_TOPICS.items() if re.search(p, text, re.IGNORECASE)}


# --- policy -------------------------------------------------------------------------------------


def news_policy(policy: dict | None) -> dict:
    """The `news:` block, whether given the whole risk policy or just the block. Missing -> decision-8 defaults."""
    policy = policy or {}
    block = policy.get("news") if isinstance(policy.get("news"), dict) else policy

    def get(key, default):  # a present-but-null YAML key means "use the default", an explicit [] is kept
        value = block.get(key)
        return default if value is None else value

    return {"active_vetoes": list(get("active_vetoes", ACTIVE_VETO_DEFAULT)),
            "promo_block_sessions": int(get("promo_block_sessions", DEFAULT_PROMO_SESSIONS)),
            "promo_words": list(get("promo_words", DEFAULT_PROMO_WORDS)),
            "source": str(get("source", "alpaca_benzinga"))}


# --- the panel: per-symbol daily features (no look-ahead: every window uses prior sessions only) ------------


@dataclass
class _Panel:
    dates: pd.DatetimeIndex
    sym: dict[str, pd.DataFrame]  # per-symbol features on `dates`
    market: pd.DataFrame  # benchmark and all-headline features on `dates`
    universe: list[str]
    c_universe: list[str]
    policy: dict
    regime: dict  # date string -> regime label (REG-2), optional


def _calendar(bars: dict, as_of) -> pd.DatetimeIndex:
    spy = bars.get(BENCHMARK)
    if spy is None or len(spy) == 0 or "close" not in spy:
        return pd.DatetimeIndex([])
    idx = _naive_index(spy.index)
    close = pd.to_numeric(pd.Series(spy["close"].to_numpy(), index=idx), errors="coerce")
    idx = close[np.isfinite(close) & (close > 0)].index.unique().sort_values()
    if as_of is not None:
        idx = idx[idx <= _day(as_of)]
    return idx


def _naive_index(index) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(index)
    if idx.tz is not None:
        idx = idx.tz_convert(NY).tz_localize(None)
    return idx.normalize()


def _day(x) -> pd.Timestamp:
    ts = pd.Timestamp(x)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(NY).tz_localize(None)
    return ts.normalize()


def _aligned(df: pd.DataFrame | None, dates: pd.DatetimeIndex, col: str) -> pd.Series:
    if df is None or len(df) == 0 or col not in df:
        return pd.Series(np.nan, index=dates)
    s = pd.to_numeric(pd.Series(df[col].to_numpy(), index=_naive_index(df.index)), errors="coerce")
    s = s[~s.index.duplicated(keep="last")]
    s = s.where(np.isfinite(s))
    if col in ("close", "open"):
        s = s.where(s > 0)
    return s.reindex(dates)


def _prior_z(s: pd.Series, window: int, min_periods: int = 20, min_std: float = 0.0) -> pd.Series:
    """z of today's value against the PRIOR `window` values, bounded to +-Z_CAP. A flat history gives 0 or +-cap.
    `min_std` floors the std (used for headline counts, where a quiet name has std 0)."""
    prior = s.shift(1).rolling(window, min_periods=min(min_periods, window))
    mean, std = prior.mean(), prior.std()
    if min_std > 0:
        std = std.clip(lower=min_std)
    z = (s - mean) / std.where(std > 0)
    flat = (std == 0) & s.notna() & mean.notna()
    z = z.where(~flat, np.sign(s - mean) * Z_CAP)
    return z.clip(-Z_CAP, Z_CAP)


def _price_frame(df: pd.DataFrame | None, spy_r: pd.Series, dates: pd.DatetimeIndex,
                 spy_oc: pd.Series | None = None) -> pd.DataFrame:
    """Per-symbol bar features. vr and MAX21 use the values AVAILABLE in their windows (vr needs 20 of the prior
    50 volumes, MAX21 5 of the last 21 returns), so one missing or NaN bar does not switch the hype vetoes off."""
    close, volume, open_ = _aligned(df, dates, "close"), _aligned(df, dates, "volume"), _aligned(df, dates, "open")
    r = close.pct_change(fill_method=None)
    ar = r - spy_r
    mean_vol = volume.shift(1).rolling(50, min_periods=20).mean()
    vr = volume / mean_vol.where(mean_vol > 0)
    out = pd.DataFrame({"close": close, "r": r, "ar": ar, "vr": vr}, index=dates)
    # open-to-close return of the day, minus SPY's: the first day of a shadow entry filled at the next open
    out["oc_ar"] = (close / open_ - 1) - (spy_oc if spy_oc is not None else 0.0)
    out["sigma60"] = ar.shift(1).rolling(60, min_periods=60).std()
    out["max21"] = r.rolling(21, min_periods=MIN_MAX21_RETURNS).max()
    out["sma50"] = close.rolling(50, min_periods=50).mean()
    out["z_vr"] = _prior_z(vr, 50)
    out["z_abs_ar"] = _prior_z(ar.abs(), 60)
    return out


def _session_closes(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """16:00 ET of each session, in UTC (the report's cutoff; early-close days use 16:00 too)."""
    return (dates + pd.Timedelta(hours=16)).tz_localize(NY).tz_convert("UTC")


def _assign(items: list[dict], dates: pd.DatetimeIndex) -> list[tuple[int, dict]]:
    """(session index, item) for each headline in (close_{t-1}, close_t]. After the last close -> next session
    (dropped); before the first session's window start (unknown) -> dropped."""
    closes = _session_closes(dates)
    out = []
    for it in items or []:
        ts = _utc(it.get("created_at") if isinstance(it, dict) else None)
        if ts is None:
            continue
        t = int(closes.searchsorted(ts, side="left"))
        if 1 <= t < len(dates):
            out.append((t, it))
    return out


def _utc(x) -> pd.Timestamp | None:
    try:
        ts = pd.Timestamp(x)
    except (ValueError, TypeError):
        return None
    if pd.isna(ts):
        return None
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def _coverage(items: list[dict], dates: pd.DatetimeIndex, news_start) -> np.ndarray:
    """known[t] is True when the whole window of session t lies inside the news we fetched. Without an explicit
    `news_start`, coverage starts at the earliest headline (conservative)."""
    known = np.zeros(len(dates), dtype=bool)
    if news_start is not None:
        start = _start_utc(news_start)
    else:
        stamps = [s for s in (_utc(it.get("created_at")) for it in items or [] if isinstance(it, dict)) if s]
        start = min(stamps) if stamps else None
    if start is None or len(dates) < 2:
        return known
    closes = _session_closes(dates)
    known[1:] = np.asarray(closes[:-1] >= start)
    return known


def _start_utc(x) -> pd.Timestamp:
    """Start of the news window in UTC; a time without zone (or a bare date) is New York time."""
    ts = pd.Timestamp(x)
    return (ts.tz_localize(NY) if ts.tzinfo is None else ts).tz_convert("UTC")


def _text_frame(heads: dict[int, list[str]], known: np.ndarray, sym: str, policy: dict,
                dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Per-session headline features for one symbol (`heads`: every assigned headline, in time order).

    Only the COUNT (hl) needs full coverage of the session window; a session we did not fully fetch has hl = NaN.
    The flags (promotion, FUND, earnings, CEO, extreme words), tone, rating and novelty describe the headlines we do
    have, so they are filled for every session that has any, whatever the coverage (a promotion headline must never
    be ignored because it happens to be the earliest item fetched). The promotion flag is read on ALL headlines,
    before near-duplicate removal, so "Sponsored: <copy of a real headline>" still counts; the other features use
    the de-duplicated list (a near-copy is the same story, not a second one)."""
    n = len(dates)
    cols = {k: np.full(n, np.nan) for k in ("hl", "neg", "rating", "novelty")}
    flags = {k: np.zeros(n, dtype=bool) for k in ("fund", "earn", "ceo", "promo", "single_extreme")}
    cols["hl"][known] = 0.0
    history: list[str] = []
    for t in range(n):
        everything = heads.get(t, [])
        today = dedupe(everything)
        if today:
            _fill_session(cols, flags, t, today, everything, history[-10:], sym, policy, bool(known[t]))
        history.extend(today)
    frame = pd.DataFrame({**cols, **flags}, index=dates)
    frame["z_hl"] = _prior_z(frame["hl"], 20, min_std=HL_MIN_STD)
    return frame


def _fill_session(cols, flags, t, today, everything, previous, sym, policy, known: bool) -> None:
    if known:
        cols["hl"][t] = len(today)
    cols["neg"][t] = float(np.mean([headline_tone(h, [sym]) for h in today]))
    cols["rating"][t] = float(np.sign(sum(_rating(h) for h in today)))
    cols["novelty"][t] = novelty(today, previous)
    flags["fund"][t] = any(_has_any(h, FUND_WORDS) for h in today)
    flags["earn"][t] = any(_has_any(h, EARNINGS_WORDS) for h in today)
    flags["ceo"][t] = any(re.search(p, h, re.IGNORECASE) for h in today for p in CEO_NAMES.get(sym, []))
    flags["promo"][t] = any(_phrase_hit(h, policy["promo_words"]) for h in everything)
    topic_counts = Counter(tp for h in today for tp in _topics(h))
    flags["single_extreme"][t] = any(c == 1 for c in topic_counts.values())


def _market_frame(assigned, known, spy: pd.DataFrame, c_frames: list[pd.DataFrame],
                  dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Benchmark returns and all-headline shares (NEWS-9, 10, 11, 12)."""
    n = len(dates)
    n_all, p_neg, macro = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    n_all[known] = 0.0
    by_t: dict[int, dict[str, str]] = {}
    for t, it in assigned:
        key = str(it.get("id") or "") or f"{it.get('created_at')}|{it.get('headline')}"
        by_t.setdefault(t, {})[key] = str(it.get("headline", ""))
    for t, heads in by_t.items():
        if known[t] and heads:
            texts = list(heads.values())
            n_all[t] = len(texts)
            p_neg[t] = float(np.mean([_has_any(h, NEGATIVE_WORDS) for h in texts]))
            macro[t] = float(np.mean([bool(MACRO_PATTERN.search(h)) for h in texts]))
    m = pd.DataFrame({"n_all": n_all, "p_neg": p_neg, "macro_share": macro}, index=dates)
    m["r"], m["vr"], m["close"], m["oc"] = spy["r"], spy["vr"], spy["close"], spy["oc_ar"]
    m["vol20"] = spy["r"].rolling(20, min_periods=20).std() * math.sqrt(252)
    m["ret252"] = spy["close"] / spy["close"].shift(252) - 1
    m["p_neg_z"] = _prior_z(m["p_neg"], 252, min_periods=60)
    m["vr_z"] = _prior_z(m["vr"], 252, min_periods=60)
    m["below_sma50"] = _share_below_sma50(c_frames, dates)
    return m


def _share_below_sma50(frames: list[pd.DataFrame], dates) -> pd.Series:
    if not frames:
        return pd.Series(np.nan, index=dates)
    below = pd.concat([(f["close"] < f["sma50"]).where(f["sma50"].notna() & f["close"].notna()) for f in frames],
                      axis=1).astype(float)
    return below.mean(axis=1, skipna=True)


def build_panel(bars: dict, news_items: list[dict], universe: list[str], as_of=None, policy: dict | None = None, *,
                c_universe: list[str] | None = None, news_start=None, regime_labels: dict | None = None) -> _Panel:
    """All daily features up to `as_of` (inclusive). Headline symbols outside `universe` are ignored."""
    pol = news_policy(policy)
    dates = _calendar(bars, as_of)
    universe = [s for s in dict.fromkeys(universe or []) if isinstance(s, str)]
    spy = _price_frame(bars.get(BENCHMARK), pd.Series(0.0, index=dates), dates)
    frames = {s: _price_frame(bars.get(s), spy["r"], dates, spy["oc_ar"]) for s in universe}
    assigned = _assign(news_items, dates)
    known = _coverage(news_items, dates, news_start)
    heads = _headlines_by_symbol(assigned, set(universe))
    after = _after_close_promo(news_items, dates, set(universe), pol["promo_words"])
    for s in universe:
        frames[s] = frames[s].join(_text_frame(heads.get(s, {}), known, s, pol, dates))
        frames[s]["promo_after_close"] = after.get(s, np.zeros(len(dates), dtype=bool))
        prev_earn = frames[s]["earn"].shift(1, fill_value=False).astype(bool)
        frames[s]["ear"] = (frames[s]["ar"].shift(1) + frames[s]["ar"]).where(prev_earn)  # NEWS-16 EAR on day +1
    c_univ = [s for s in (c_universe or universe) if s in frames]
    market = _market_frame(assigned, known, spy, [frames[s] for s in c_univ], dates)
    return _Panel(dates, frames, market, universe, c_univ, pol, dict(regime_labels or {}))


def _headlines_by_symbol(assigned, universe: set[str]) -> dict[str, dict[int, list[str]]]:
    """symbol -> session -> every headline (not yet de-duplicated), in time order. Only allowlisted symbols."""
    raw: dict[str, dict[int, list[tuple[str, str]]]] = {}
    for t, it in assigned:
        for sym in it.get("symbols") or []:
            if sym in universe:
                raw.setdefault(sym, {}).setdefault(t, []).append((str(it.get("created_at")), str(it.get("headline"))))
    return {s: {t: [h for _, h in sorted(v)] for t, v in by_t.items()} for s, by_t in raw.items()}


def _next_opens(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """09:30 ET of the session after each session, in UTC (after the last one: the next business day)."""
    nxt = list(dates[1:]) + ([dates[-1] + pd.offsets.BDay(1)] if len(dates) else [])
    return (pd.DatetimeIndex(nxt) + pd.Timedelta(hours=9, minutes=30)).tz_localize(NY).tz_convert("UTC")


def _after_close_promo(items, dates: pd.DatetimeIndex, universe: set[str], words) -> dict[str, np.ndarray]:
    """NEWS-18 promotion only: symbol -> flags[t] = a promotion headline arrived after the 16:00 close of session t
    and before the next open. For hl it belongs to the next session, but the run that sends the next-open buy is
    made in that gap, so the ACTIVE promotion block must already see it. Later headlines are never read."""
    out: dict[str, np.ndarray] = {}
    if len(dates) == 0:
        return out
    closes, opens = _session_closes(dates), _next_opens(dates)
    for it in items or []:
        if not isinstance(it, dict):
            continue
        ts = _utc(it.get("created_at"))
        if ts is None or not _phrase_hit(str(it.get("headline", "")), words):
            continue
        t = int(closes.searchsorted(ts, side="left")) - 1  # the last close strictly before ts
        if 0 <= t < len(dates) and ts <= opens[t]:
            for sym in it.get("symbols") or []:
                if sym in universe:
                    out.setdefault(sym, np.zeros(len(dates), dtype=bool))[t] = True
    return out


# --- small helpers for rows -------------------------------------------------------------------------


def _f(x, nd: int = 6) -> float | None:
    """JSON-safe number: None for missing, NaN or infinite."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if math.isfinite(x) else None


def _v(frame: pd.DataFrame, col: str, i: int):
    if i < 0 or i >= len(frame):
        return None
    return _f(frame[col].iat[i])


def _row(event: bool, status: str = "shadow", source: str = SOURCE_NEWS, **fields) -> dict:
    return {"event": bool(event), "status": status, "source": source, **fields}


def _skip(reason: str, source: str | None = None) -> dict:
    """A row that could not be computed. `_evaluate` adds the signal's source when none is given here."""
    return {"skipped": reason, **({"source": source} if source else {})}


def _status(p: "_Panel", veto_id: str) -> str:
    """'active_veto' only for a decision-8 veto that the policy's `news.active_vetoes` lists, else 'shadow'."""
    return "active_veto" if veto_id in p.policy["active_vetoes"] else "shadow"


def _move(p: _Panel, sym: str, i: int) -> tuple[dict | None, float, float]:
    """(skip row or None, AR_t, sigma60) - the shared inputs of the big-move signals."""
    f = p.sym[sym]
    ar, sigma = _v(f, "ar", i), _v(f, "sigma60", i)
    if ar is None:
        return _skip("no bar for this session"), 0.0, 0.0
    if sigma is None or sigma <= 0:
        return _skip("short price history (needs 60 prior sessions of AR)"), ar, 0.0
    return None, ar, sigma


def _ranked(values: dict[str, float | None], top: bool = True) -> set[str]:
    """Names in the top (or bottom) decile; needs at least MIN_RANK_NAMES valid values. Ties at the cutoff count."""
    valid = {k: v for k, v in values.items() if v is not None}
    if len(valid) < MIN_RANK_NAMES:
        return set()
    k = max(1, math.ceil(0.1 * len(valid)))
    ordered = sorted(valid.values(), reverse=top)
    cut = ordered[k - 1]
    return {s for s, v in valid.items() if (v >= cut if top else v <= cut)}


# --- the eighteen signals: each returns {symbol: row} at session index i --------------------------------


def _news1(p: _Panel, i: int) -> dict:
    """NEWS-1 news split (research log): |AR| > 2.5 sigma60 -> record has_news and direction (four cells)."""
    out = {}
    for s in p.universe:
        skip, ar, sigma = _move(p, s, i)
        hl = _v(p.sym[s], "hl", i)
        if skip or hl is None:
            out[s] = skip or _skip("no news coverage for this session")
            continue
        event = abs(ar) > 2.5 * sigma
        direction = ("up" if ar > 0 else "down") if event else None
        cell = f"{direction}_{'news' if hl >= 1 else 'no_news'}" if event else None
        out[s] = _row(event, direction=direction, has_news=hl >= 1, cell=cell, ar=ar, sigma60=sigma,
                      ar_z=_f(ar / sigma), hl=hl)
    return out


def _news2(p: _Panel, i: int) -> dict:
    """NEWS-2 news continuation: |AR| > 2 sigma60, hl >= 1, not an earnings day -> shadow trade with the move."""
    out = {}
    for s in p.universe:
        skip, ar, sigma = _move(p, s, i)
        hl = _v(p.sym[s], "hl", i)
        if skip or hl is None:
            out[s] = skip or _skip("no news coverage for this session")
            continue
        earn = bool(p.sym[s]["earn"].iat[i])
        event = abs(ar) > 2 * sigma and hl >= 1 and not earn
        out[s] = _row(event, direction=int(np.sign(ar)) if event else 0, long_eligible=event and ar > 0,
                      short_leg_logged=event and ar < 0, earnings_day=earn, ar=ar, sigma60=sigma, hl=hl,
                      hold_sessions="3-5")
    return out


def _news3(p: _Panel, i: int) -> dict:
    """NEWS-3 no-news reversal: |AR| > 2 sigma60 and hl_{t-1} + hl_t = 0 -> shadow trade against the move."""
    out = {}
    for s in p.universe:
        skip, ar, sigma = _move(p, s, i)
        hl, hl_prev = _v(p.sym[s], "hl", i), _v(p.sym[s], "hl", i - 1)
        if skip or hl is None or hl_prev is None:
            out[s] = skip or _skip("no news coverage for this session or the one before")
            continue
        vr = _v(p.sym[s], "vr", i)
        event = abs(ar) > 2 * sigma and hl + hl_prev == 0
        out[s] = _row(event, direction=-int(np.sign(ar)) if event else 0, ar=ar, sigma60=sigma,
                      attention=(vr > 3) if vr is not None else None, vr=vr, hold_sessions="5-20")
    return out


def _attention_scores(p: _Panel, i: int) -> dict[str, dict]:
    """NEWS-4 inputs: A_t = z20(hl) + z50(vr) + z60(|AR|). An unknown hl term (no news coverage) counts as 0, so the
    veto still works on price and volume alone (`hl_known` records it). z20(hl) uses a std floor of HL_MIN_STD
    headlines (design choice: the report does not say how to treat a flat history; without a floor one headline on
    a quiet name would score the +5 cap and swamp the other two terms)."""
    out = {}
    for s in p.universe:
        f = p.sym[s]
        z_hl, z_vr, z_ar = _v(f, "z_hl", i), _v(f, "z_vr", i), _v(f, "z_abs_ar", i)
        a = None if z_vr is None or z_ar is None else (z_hl or 0.0) + z_vr + z_ar
        out[s] = {"a": a, "z_hl": z_hl, "z_vr": z_vr, "z_ar": z_ar}
    return out


def _news4(p: _Panel, i: int) -> dict:
    """NEWS-4 attention-spike veto (ACTIVE, decision 8): A_t in the universe's top decile and AR_t > 0 -> no new long.
    A shadow 20-session fade is logged for every veto."""
    scores = _attention_scores(p, i)
    top = _ranked({s: v["a"] for s, v in scores.items()})
    out = {}
    status = _status(p, "NEWS-4")
    for s, v in scores.items():
        ar = _v(p.sym[s], "ar", i)
        if ar is None:
            out[s] = _skip("no bar for this session")
            continue
        if v["a"] is None:  # fail closed: a name we cannot score for hype may not be bought on an up day
            veto = ar > 0
            out[s] = _row(veto, status=status, attention_z=None, z_hl=v["z_hl"], z_vr=v["z_vr"], z_abs_ar=v["z_ar"],
                          hl_known=v["z_hl"] is not None, ar=ar, top_decile=False, veto=veto,
                          insufficient_history=True, shadow="fade 20 sessions" if veto else None)
            continue
        veto = s in top and ar > 0
        out[s] = _row(veto, status=status, attention_z=_f(v["a"], 4), z_hl=v["z_hl"], z_vr=v["z_vr"],
                      z_abs_ar=v["z_ar"], hl_known=v["z_hl"] is not None, ar=ar, top_decile=s in top, veto=veto,
                      insufficient_history=False, shadow="fade 20 sessions" if veto else None)
    return out


def _news5(p: _Panel, i: int) -> dict:
    """NEWS-5 stale-news fade: novelty < 0.3 with |AR| > 2 sigma60 -> log a fade; novelty > 0.7 -> a continuation."""
    out = {}
    for s in p.universe:
        skip, ar, sigma = _move(p, s, i)
        if skip:
            out[s] = skip
            continue
        nov = _v(p.sym[s], "novelty", i)
        big = abs(ar) > 2 * sigma
        label = None
        if big and nov is not None:
            label = "fade" if nov < 0.3 else ("continuation" if nov > 0.7 else None)
        out[s] = _row(label is not None, novelty=_f(nov, 4), label=label,
                      direction=(-int(np.sign(ar)) if label == "fade" else int(np.sign(ar))) if label else 0,
                      ar=ar, sigma60=sigma, hold_sessions=5)
    return out


def _news6(p: _Panel, i: int) -> dict:
    """NEWS-6 bad-news veto flag for B and C entries (shadow): tone of today's headlines <= -0.5."""
    out = {}
    for s in p.universe:
        hl = _v(p.sym[s], "hl", i)
        if hl is None:
            out[s] = _skip("no news coverage for this session")
            continue
        neg = _v(p.sym[s], "neg", i)
        bad = neg is not None and neg <= -0.5
        out[s] = _row(bad, neg=neg, hl=hl, has_news=hl >= 1, bad_news=bad, scorer=SCORER_VERSION)
    return out


def _news7(p: _Panel, i: int) -> dict:
    """NEWS-7 slow news tilt: mean daily tone over 20/60/120 sessions minus the C-universe mean (tie-break only)."""
    raw = {w: {} for w in (20, 60, 120)}
    for s in p.universe:
        neg = p.sym[s]["neg"].iloc[: i + 1]
        for w in raw:
            raw[w][s] = _f(neg.iloc[-w:].mean()) if len(neg) else None
    means = {w: _mean([raw[w].get(s) for s in p.c_universe]) for w in raw}
    out = {}
    for s in p.universe:
        tilt = {f"s{w}": _f(raw[w][s] - means[w]) if raw[w][s] is not None and means[w] is not None else None
                for w in raw}
        out[s] = _row(tilt["s60"] is not None, scorer=SCORER_VERSION, use="tie-break between C candidates only",
                      **tilt)
    return out


def _mean(values: list) -> float | None:
    vals = [v for v in values if v is not None]
    return float(np.mean(vals)) if vals else None


def _news8(p: _Panel, i: int) -> dict:
    """NEWS-8 celebrity-CEO controversy drop: r <= -8% (or AR <= -3 sigma60), a CEO-name headline, no FUND words
    in t-1..t. Drops with FUND words are the comparison group."""
    out = {}
    for s in p.universe:
        f = p.sym[s]
        r, ar, sigma = _v(f, "r", i), _v(f, "ar", i), _v(f, "sigma60", i)
        if r is None or _v(f, "hl", i) is None:
            out[s] = _skip("no bar or no news coverage for this session")
            continue
        drop = r <= -0.08 or (ar is not None and sigma is not None and ar <= -3 * sigma)
        fund = bool(f["fund"].iat[i]) or (i >= 1 and bool(f["fund"].iat[i - 1]))
        ceo = bool(f["ceo"].iat[i])
        group = ("controversy" if ceo and not fund else "fund_drop" if fund else None) if drop else None
        out[s] = _row(drop and ceo and not fund, drop=drop, ceo_mention=ceo, fund_words=fund, group=group, r=r,
                      ar=ar, sigma60=sigma, in_ceo_table=s in CEO_NAMES)
    return out


def _news9(p: _Panel, i: int) -> dict:
    """NEWS-9 macro-post selloff: SPY r <= -2% and >= 10% of the day's headlines match tariff|Trump|Truth Social."""
    m = p.market
    r, share = _v(m, "r", i), _v(m, "macro_share", i)
    if r is None or _v(m, "n_all", i) is None:
        return {BENCHMARK: _skip("no SPY bar or no news coverage for this session")}
    down = r <= -0.02
    event = down and share is not None and share >= 0.10
    return {BENCHMARK: _row(event, spy_r=r, macro_share=_f(share, 4), n_headlines=_v(m, "n_all", i),
                            down_2pct_day=down, regime=_regime(p, i))}


def _regime(p: _Panel, i: int) -> str | None:
    return p.regime.get(p.dates[i].strftime("%Y-%m-%d")) if 0 <= i < len(p.dates) else None


def _news10(p: _Panel, i: int) -> dict:
    """NEWS-10 media pessimism: share of the day's headlines with a negative word, z vs 252 sessions; z > 2 -> log."""
    m = p.market
    z = _v(m, "p_neg_z", i)
    if z is None:
        return {BENCHMARK: _skip("needs 60+ sessions of news history (252 for the full window)")}
    vz = _v(m, "vr_z", i)
    extreme = "high" if z > 2 else ("low" if z < -2 else None)
    return {BENCHMARK: _row(z > 2, p_neg=_v(m, "p_neg", i), p_neg_z=_f(z, 4), pessimism_extreme=extreme,
                            spy_vr=_v(m, "vr", i), spy_vr_z=vz, scorer=SCORER_VERSION)}


def _news11(p: _Panel, i: int) -> dict:
    """NEWS-11 panic state: REG-2 panic label, or SPY 252-session return < 0 and vol20 > 25% annualised."""
    m = p.market
    ret, vol = _v(m, "ret252", i), _v(m, "vol20", i)
    label = _regime(p, i)
    if (ret is None or vol is None) and label is None:
        return {BENCHMARK: _skip("short SPY history (needs 253 sessions)")}
    fast = ret is not None and vol is not None and ret < 0 and vol > 0.25
    panic = fast or label == "panic"
    return {BENCHMARK: _row(panic, source=SOURCE_BARS, spy_ret252=ret, spy_vol20=vol, fast_panic=fast,
                            reg2_panic=label == "panic", regime=label, iv_variant=_skip(IV_SKIP, SOURCE_IV),
                            shadow="halve C; log a SPY/QQQ rebound buy" if panic else None)}


def _pct_rank(s: pd.Series, i: int, window: int = 1260, min_periods: int = 252) -> float | None:
    """Percentile (0-100) of today's value among the prior `window` values."""
    today = _f(s.iat[i]) if 0 <= i < len(s) else None
    hist = s.iloc[max(0, i - window): i].dropna()
    if today is None or len(hist) < min_periods:
        return None
    return float(100.0 * (hist <= today).mean())


def _news12(p: _Panel, i: int) -> dict:
    """NEWS-12 fear/greed composite from the parts we can compute; the IV parts need logged IV history."""
    m = p.market
    parts = {"spy_vol20": _pct_rank(m["vol20"], i), "c_below_sma50": _pct_rank(m["below_sma50"], i),
             "p_neg": _pct_rank(m["p_neg"], i)}
    have = [v for v in parts.values() if v is not None]
    if not have:
        return {BENCHMARK: _skip("needs 252+ sessions of history")}
    comp = float(np.mean(have))
    extreme = "fear" if comp > 95 else ("greed" if comp < 5 else None)
    return {BENCHMARK: _row(extreme is not None, composite=_f(comp, 2), extreme=extreme, partial=True,
                            parts={k: _f(v, 2) for k, v in parts.items()},
                            iv_parts=_skip(IV_SKIP, SOURCE_IV), hold_sessions="5-60")}


def _news13(p: _Panel, i: int) -> dict:
    """NEWS-13 lottery (MAX) veto (ACTIVE, decision 8): MAX21 in the universe's top decile -> no new long."""
    maxes = {s: _v(p.sym[s], "max21", i) for s in p.universe}
    top = _ranked(maxes)
    status = _status(p, "NEWS-13")
    out = {}
    for s, mx in maxes.items():
        if mx is None:
            if _v(p.sym[s], "close", i) is None:
                out[s] = _skip("no bar for this session", SOURCE_BARS)
            else:  # fail closed: a bar today but under MIN_MAX21_RETURNS returns in 21 sessions (new listing, gap)
                out[s] = _row(True, status=status, source=SOURCE_BARS, max21=None, top_decile=False, veto=True,
                              insufficient_history=True)
            continue
        out[s] = _row(s in top, status=status, source=SOURCE_BARS, max21=mx, top_decile=s in top,
                      veto=s in top, insufficient_history=False)
    return out


def _cgo(f: pd.DataFrame, i: int, horizon: int = 260, min_n: int = 60) -> tuple[float | None, float | None]:
    """NEWS-14 capital gains overhang with the turnover proxy tau = min(0.2, 0.01 vr): (CGO, reference price)."""
    if i < 1:
        return None, None
    tau = np.minimum(0.2, 0.01 * f["vr"].to_numpy()[:i][::-1][:horizon])
    closes = f["close"].to_numpy()[:i][::-1][:horizon]
    bad = ~(np.isfinite(tau) & np.isfinite(closes))
    n = int(np.argmax(bad)) if bad.any() else len(tau)
    today = _f(f["close"].iat[i])
    if n < min_n or today is None:
        return None, None
    tau, closes = tau[:n], closes[:n]
    w = tau * np.concatenate([[1.0], np.cumprod(1 - tau[:-1])])
    if w.sum() <= 0:
        return None, None
    rp = float((w * closes).sum() / w.sum())
    return _f(today / rp - 1), _f(rp)


def _news14(p: _Panel, i: int) -> dict:
    """NEWS-14 gain-overhang alignment, evaluated on day +1 of an earnings-headline day (day 0), because the rule's
    sign(neg or AR_[0,+1]) needs AR_{+1}: aligned = sign(neg_0, or AR_0 + AR_{+1} when neg_0 is 0) == sign(CGO_0).
    The event fires on day +1 (like NEWS-16), so forward AR is measured from there with no look-ahead. On other days
    the row carries today's CGO for the record."""
    out = {}
    for s in p.universe:
        f = p.sym[s]
        event = i >= 1 and bool(f["earn"].iat[i - 1])
        day = i - 1 if event else i
        cgo, rp = _cgo(f, day)
        if cgo is None:
            out[s] = _skip("short price or volume history (needs 60+ prior sessions with volume ratios)")
            continue
        aligned = ar01 = None
        if event:
            neg, a0, a1 = _v(f, "neg", day), _v(f, "ar", day), _v(f, "ar", i)
            ar01 = _f(a0 + a1) if a0 is not None and a1 is not None else None
            news_sign = int(np.sign(neg)) if neg else (int(np.sign(ar01)) if ar01 is not None else 0)
            aligned = news_sign != 0 and news_sign == int(np.sign(cgo))
        out[s] = _row(event, cgo=cgo, reference_price=rp, cgo_date=p.dates[day].strftime("%Y-%m-%d"),
                      earnings_day=bool(f["earn"].iat[i]), earnings_yesterday=event, ar_0_1=ar01, aligned=aligned,
                      hold_sessions="20-60")
    return out


def _news15(p: _Panel, i: int) -> dict:
    """NEWS-15 downgrade/guidance drift: -1 for downgrade or guidance cut, +1 for upgrade or raise (log only)."""
    out = {}
    for s in p.universe:
        if _v(p.sym[s], "hl", i) is None:
            out[s] = _skip("no news coverage for this session")
            continue
        d = int(_v(p.sym[s], "rating", i) or 0)
        out[s] = _row(d != 0, direction=d, hold_sessions="20-60")
    return out


EAR_POOL_SESSIONS = 252


def _news16(p: _Panel, i: int) -> dict:
    """NEWS-16 earnings-drift control: yesterday was an earnings day -> EAR = AR_{t-1} + AR_t. Deciles are over
    EARNINGS EVENTS (every universe name's EAR in the last EAR_POOL_SESSIONS sessions, up to today; no look-ahead),
    not over all names that day, so a quiet day for other names cannot push an event into a decile. Needs at
    least MIN_RANK_NAMES events in the pool."""
    lo = max(0, i - EAR_POOL_SESSIONS + 1)
    pool = {(s, t): _f(p.sym[s]["ear"].iat[t]) for s in p.universe for t in range(lo, i + 1)}
    top, bottom = _ranked(pool, True), _ranked(pool, False)
    out = {}
    for s in p.universe:
        ear = _v(p.sym[s], "ear", i)
        decile = ("top" if (s, i) in top else "bottom" if (s, i) in bottom else None) if ear is not None else None
        out[s] = _row(decile is not None, earnings_day=bool(p.sym[s]["earn"].iat[i]), ear=ear, decile=decile,
                      events_in_pool=sum(v is not None for v in pool.values()), control=True)
    return out


def _news17(p: _Panel, i: int, triggers: dict[str, list[str]]) -> dict:
    """NEWS-17 IV after a shock: logging needs IV snapshots we do not have yet."""
    keys = list(p.universe) + ([BENCHMARK] if BENCHMARK not in p.universe else [])
    return {s: {**_skip(IV_SKIP, SOURCE_IV), "triggered_by": sorted(triggers.get(s, []))} for s in keys}


def _news18(p: _Panel, i: int) -> dict:
    """NEWS-18 in two parts with their own labels:
    - single-headline guard (SHADOW, `guard_status`): an extreme-word headline that is the only one on its topic
      and |AR_t| > 3 sigma60 -> log "no new entry tomorrow";
    - promotion words (ACTIVE under decision 8 when the policy lists NEWS-18-PROMO, `promo_status`): no new long
      for `promo_block_sessions` sessions. A promotion headline after today's close but before the next open
      (`promo_after_close`) starts the block now, since the next-open buy is decided in that gap.
    The row's `status` is 'active_veto' only while the promotion block is live and active; otherwise 'shadow'."""
    block = p.policy["promo_block_sessions"]
    promo_status = _status(p, "NEWS-18-PROMO")
    as_of = p.dates[i].strftime("%Y-%m-%d")
    out = {}
    for s in p.universe:
        f = p.sym[s]
        promo = f["promo"].to_numpy()[: i + 1]
        since = int(i - np.flatnonzero(promo)[-1]) if promo.any() else None
        left = max(0, block - since) if since is not None else 0
        pending = bool(f["promo_after_close"].iat[i])
        if pending:
            left = block
        ar, sigma = _v(f, "ar", i), _v(f, "sigma60", i)
        big = ar is not None and sigma is not None and sigma > 0 and abs(ar) > 3 * sigma
        single = bool(f["single_extreme"].iat[i])
        live = left > 0 and promo_status == "active_veto"
        out[s] = _row((single and big) or bool(promo[-1]) or pending, status="active_veto" if live else "shadow",
                      as_of=as_of, single_extreme_headline=single, big_move=big, no_entry_tomorrow=single and big,
                      guard_status="shadow", promo_today=bool(promo[-1]), promo_after_close=pending,
                      promo_sessions_left=left, promo_status=promo_status, ar=ar, sigma60=sigma)
    return out


_BUILDERS = {"NEWS-1": _news1, "NEWS-2": _news2, "NEWS-3": _news3, "NEWS-4": _news4, "NEWS-5": _news5,
             "NEWS-6": _news6, "NEWS-7": _news7, "NEWS-8": _news8, "NEWS-9": _news9, "NEWS-10": _news10,
             "NEWS-11": _news11, "NEWS-12": _news12, "NEWS-13": _news13, "NEWS-14": _news14, "NEWS-15": _news15,
             "NEWS-16": _news16, "NEWS-18": _news18}


_SOURCES = {sid: SOURCE_NEWS for sid in SIGNAL_IDS}
_SOURCES.update({"NEWS-11": SOURCE_BARS, "NEWS-13": SOURCE_BARS, "NEWS-17": SOURCE_IV})


def _with_source(sid: str, rows: dict) -> dict:
    """Owner decision 7: every row, computed or skipped, names its data source."""
    for row in rows.values():
        if isinstance(row, dict):
            row.setdefault("source", _SOURCES[sid])
    return rows


def _evaluate(p: _Panel, i: int, ids: Iterable[str] = SIGNAL_IDS) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for sid in ids:
        if sid != "NEWS-17":
            out[sid] = _BUILDERS[sid](p, i)
    if "NEWS-17" in ids:
        out["NEWS-17"] = _news17(p, i, _shock_triggers(p, i, out))
    return {sid: _with_source(sid, out[sid]) for sid in ids}


def _shock_triggers(p: _Panel, i: int, done: dict) -> dict[str, list[str]]:
    """Which of NEWS-1, 8, 9 fired for each symbol (inputs to NEWS-17)."""
    rows = {sid: done.get(sid) or _BUILDERS[sid](p, i) for sid in ("NEWS-1", "NEWS-8", "NEWS-9")}
    triggers: dict[str, list[str]] = {}
    for sid, by_sym in rows.items():
        for s, row in by_sym.items():
            if row.get("event"):
                triggers.setdefault(s, []).append(sid)
    return triggers


# --- public API ------------------------------------------------------------------------------------


def compute(bars: dict, news_items: list[dict], universe: list[str], as_of, policy: dict | None = None, *,
            c_universe: list[str] | None = None, news_start=None, regime_label: str | None = None
            ) -> dict[str, dict[str, dict]]:
    """Every NEWS-1..18 signal for session `as_of` (the last bar on or before it), as {signal: {symbol: row}}.

    `bars` must include SPY (the benchmark). `news_items` are `news.fetch_news` items covering at least the prior
    25 sessions (NEWS-4's z20 of headline counts; NEWS-10 wants 252). Pass `news_start` (the start of the fetch
    window) so sessions with no headlines count as zero, not as unknown. `regime_label` is REG-2's label for
    `as_of` (used by NEWS-9 and NEWS-11). Bars and headlines after `as_of` are ignored (no look-ahead).
    """
    universe = list(dict.fromkeys(universe or []))
    dates = _calendar(bars, as_of)
    if len(dates) == 0:
        return _all_skipped(universe, "needs SPY bars up to as_of")
    labels = {dates[-1].strftime("%Y-%m-%d"): regime_label} if regime_label else None
    panel = build_panel(bars, news_items, universe, dates[-1], policy, c_universe=c_universe,
                        news_start=news_start, regime_labels=labels)
    return _evaluate(panel, len(dates) - 1)


_MARKET_IDS = {"NEWS-9", "NEWS-10", "NEWS-11", "NEWS-12"}


def _all_skipped(universe: list[str], reason: str) -> dict:
    out = {}
    for sid in SIGNAL_IDS:
        keys = [BENCHMARK] if sid in _MARKET_IDS else list(universe)
        out[sid] = _with_source(sid, {s: _skip(IV_SKIP if sid == "NEWS-17" else reason) for s in keys})
    return out


def active_vetoes(signals: dict, policy: dict | None = None, promo_history: dict | None = None, *, as_of=None):
    """Owner decision 8: the hype vetoes that block NEW longs and increases (never exits, never orders).

    Returns {symbol: [reason, ...]} for NEWS-4, NEWS-13 and NEWS-18-PROMO, whichever are listed in
    `news.active_vetoes`. Each veto must still be shadow-scored by the caller (CL-9 veto shadow lots).

    NEWS-18-PROMO needs memory beyond the news window: pass `promo_history` (the dict returned last time, {} the
    first time) and you get `(vetoes, updated_history)` back instead of just `vetoes`. The history counts one
    session per distinct SESSION date: the NEWS-18 rows' own `as_of` (the last bar) is used whenever the rows carry
    one, so a run on a weekend or holiday does not count; a skipped run makes the block last longer, never shorter.
    Only symbols of the signals' universe (the allowlist) can be named, whatever keys the stored history holds.
    """
    pol = news_policy(policy)
    active = set(pol["active_vetoes"])
    vetoes: dict[str, list[str]] = {}
    if "NEWS-4" in active:
        _add_rows(vetoes, signals.get("NEWS-4"), _reason_news4)
    if "NEWS-13" in active:
        _add_rows(vetoes, signals.get("NEWS-13"), _reason_news13)
    history = None
    if promo_history is not None:
        history = update_promo_history(signals, promo_history, pol, as_of=as_of)
    if "NEWS-18-PROMO" in active:
        _add_promo(vetoes, signals.get("NEWS-18") or {}, history or {})
    return (vetoes, history) if promo_history is not None else vetoes


def _add_rows(vetoes: dict, rows: dict | None, reason) -> None:
    for s, row in (rows or {}).items():
        if isinstance(row, dict) and row.get("veto"):
            vetoes.setdefault(s, []).append(reason(row))


def _reason_news4(row: dict) -> str:
    if row.get("insufficient_history"):
        return "NEWS-4 hype check impossible (short price/volume history) on an up day: no new long"
    a = row.get("attention_z")
    return f"NEWS-4 attention spike after a run-up (A={a:.2f}, top decile, AR>0)" if a is not None \
        else "NEWS-4 attention spike after a run-up (top decile, AR>0)"


def _reason_news13(row: dict) -> str:
    if row.get("insufficient_history"):
        return "NEWS-13 lottery check impossible (short price history): no new long"
    mx = row.get("max21")
    return f"NEWS-13 lottery stock (MAX21={mx:.1%}, top decile)" if mx is not None \
        else "NEWS-13 lottery stock (top decile)"


_TICKER = re.compile(r"^[A-Z][A-Z0-9.\-/]{0,11}$")


def _allowed(sym, rows: dict) -> bool:
    """A history key may name a veto only if it is in the signals' universe (or, with no rows, ticker-shaped)."""
    return isinstance(sym, str) and bool(_TICKER.match(sym)) and (not rows or sym in rows)


def _add_promo(vetoes: dict, rows: dict, history: dict) -> None:
    for s in sorted(k for k in set(rows) | set(history) if _allowed(k, rows)):
        row = rows.get(s) if isinstance(rows.get(s), dict) else {}
        left = max(int(row.get("promo_sessions_left") or 0), int((history.get(s) or {}).get("sessions_left", 0)))
        if left > 0:
            vetoes.setdefault(s, []).append(f"NEWS-18 paid-promotion wording: no new long, "
                                            f"{left} sessions left")


def promo_words_version(words) -> str:
    """Short fingerprint of a promotion phrase list (case and order do not matter)."""
    import hashlib
    key = "\n".join(sorted({str(w).strip().lower() for w in words or ()}))
    return hashlib.sha256(key.encode()).hexdigest()[:10]


def update_promo_history(signals: dict, promo_history: dict, policy: dict | None = None, *, as_of=None) -> dict:
    """NEWS-18 promotion memory {symbol: {last_promo, sessions_left, updated, words}}; a new copy, entries at 0
    removed. `words` fingerprints the promotion phrase list that made the entry: an entry made under another list
    (or none, i.e. before 28 Sept when bare "paid"/"sponsored" matched ordinary headlines) is dropped, and a real
    promotion still inside the news window is found again from the headlines by today's rows."""
    pol = news_policy(policy)
    words = promo_words_version(pol["promo_words"])
    rows = signals.get("NEWS-18") or {}
    as_of = _signals_as_of(rows) or (str(pd.Timestamp(as_of).date()) if as_of is not None else None)
    new: dict[str, dict] = {}
    for s, entry in (promo_history or {}).items():
        if not (isinstance(s, str) and _TICKER.match(s)) or not isinstance(entry, dict):
            continue  # a hand-edited or corrupt history file cannot add a symbol
        if entry.get("words") != words:
            continue  # made by another phrase list (finding #24: stale false positives must not keep blocking)
        entry = dict(entry)
        left = int(entry.get("sessions_left", 0))
        if as_of and entry.get("updated") and str(entry["updated"]) < as_of:
            left -= 1
        entry.update(sessions_left=max(0, left), updated=as_of or entry.get("updated"))
        new[s] = entry
    for s, row in rows.items():
        if isinstance(row, dict) and (row.get("promo_today") or row.get("promo_after_close")):
            new[s] = {"last_promo": as_of, "sessions_left": pol["promo_block_sessions"], "updated": as_of,
                      "words": words}
        elif isinstance(row, dict) and int(row.get("promo_sessions_left") or 0) > new.get(s, {}).get("sessions_left", 0):
            new[s] = {"last_promo": new.get(s, {}).get("last_promo"), "sessions_left": int(row["promo_sessions_left"]),
                      "updated": as_of, "words": words}
    return {s: e for s, e in new.items() if e.get("sessions_left", 0) > 0}


def _signals_as_of(rows: dict) -> str | None:
    for row in rows.values():
        if isinstance(row, dict) and row.get("as_of"):
            return str(row["as_of"])
    return None


def backtest_signal(signal_id: str, bars: dict, news_history: list[dict], start, end, *,
                    universe: list[str] | None = None, policy: dict | None = None, news_start=None,
                    c_universe: list[str] | None = None, regime_labels: dict | None = None,
                    horizons: tuple[int, ...] = (1, 5, 10, 20)) -> list[dict]:
    """Gate M-12 inputs: every event of `signal_id` between `start` and `end`, with forward AR per horizon.

    Section 5: shadow entries fill at the NEXT OPEN with EX-5 costs of 10 bps per side. So the primary fields are
    `ar_fwd_open_<h>`: the open-to-close AR of session t+1 (symbol minus SPY), plus close-to-close AR of sessions
    t+2..t+h; and `ar_fwd_open_net_<h>` = that minus the 20 bps round trip. For the market-wide signals the SPY
    return itself is used. `ar_fwd_<h>` (close of t to close of t+h, which includes the overnight gap a next-open
    fill cannot capture) is kept only as a labelled extra. None when the bars end too early or a bar is missing.
    No look-ahead: each event uses only data up to its own session.
    """
    if signal_id not in SIGNAL_IDS:
        raise ValueError(f"unknown signal {signal_id!r}; use one of NEWS-1..NEWS-18")
    universe = list(universe) if universe is not None else sorted(s for s in bars if "/" not in s)
    panel = build_panel(bars, news_history, universe, None, policy, c_universe=c_universe, news_start=news_start,
                        regime_labels=regime_labels)
    lo, hi = _day(start), _day(end)
    events = []
    for i, day in enumerate(panel.dates):
        if lo <= day <= hi:
            rows = _evaluate(panel, i, [signal_id])[signal_id]
            events += _events(panel, signal_id, i, rows, horizons)
    return events


def _events(p: _Panel, sid: str, i: int, rows: dict, horizons) -> list[dict]:
    out = []
    for s, row in rows.items():
        if not row.get("event"):
            continue
        market = sid in _MARKET_IDS or s not in p.sym
        series = p.market["r"] if market else p.sym[s]["ar"]
        first = p.market["oc"] if market else p.sym[s]["oc_ar"]
        fwd: dict[str, Any] = {}
        for h in horizons:
            opened = _forward_open(first, series, i, h)
            fwd[f"ar_fwd_open_{h}"] = opened
            fwd[f"ar_fwd_open_net_{h}"] = _f(opened - 2 * COST_PER_SIDE) if opened is not None else None
            fwd[f"ar_fwd_{h}"] = _forward(series, i, h)
        out.append({"signal": sid, "date": p.dates[i].strftime("%Y-%m-%d"), "symbol": s, **row,
                    "fill": "next open, 10 bps/side", **fwd})
    return out


def _forward(series: pd.Series, i: int, h: int) -> float | None:
    """Close of session i to close of session i+h (sum of daily AR)."""
    window = series.iloc[i + 1: i + 1 + h]
    if len(window) < h or window.isna().any():
        return None
    return _f(window.sum())


def _forward_open(first: pd.Series, series: pd.Series, i: int, h: int) -> float | None:
    """Open of session i+1 to close of session i+h: open-to-close AR of i+1, then close-to-close AR of i+2..i+h."""
    if h < 1 or i + h > len(series) - 1:
        return None
    head = first.iat[i + 1]
    rest = series.iloc[i + 2: i + 1 + h]
    if not np.isfinite(head) or rest.isna().any():
        return None
    return _f(head + rest.sum())


def score_log(bars: dict, news_items: list[dict], universe: list[str], as_of=None,
              policy: dict | None = None) -> list[dict]:
    """Section 6 reproducibility record: one entry per (headline, allowlisted symbol) used by the scorers, with the
    headline id, its session, whether it survived near-duplicate removal, its tone, the promotion flag, and the
    SCORER_VERSION and SANITIZER_VERSION, plus the sanitised text itself.

    FOR THE AUDIT LOG FILE ONLY. This is the one function here that returns headline text; its output must never
    be put in Claude's context (the prompt-injection guard). `compute` output never contains text."""
    from .news import SANITIZER_VERSION

    pol = news_policy(policy)
    dates = _calendar(bars, as_of)
    allow = set(universe or [])
    per: dict[tuple[str, int], list[tuple[str, dict]]] = {}
    for t, it in _assign(news_items, dates):
        for sym in it.get("symbols") or []:
            if sym in allow:
                per.setdefault((sym, t), []).append((str(it.get("created_at")), it))
    out = []
    for (sym, t), rows in sorted(per.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        kept: list[str] = []
        for _, it in sorted(rows, key=lambda r: r[0]):
            text = str(it.get("headline", ""))
            dup = not all(similarity(text, k) <= DUP_SIMILARITY for k in kept)
            if not dup:
                kept.append(text)
            out.append({"id": str(it.get("id") or ""), "created_at": it.get("created_at"), "symbol": sym,
                        "session": dates[t].strftime("%Y-%m-%d"), "kept": not dup,
                        "tone": headline_tone(text, [sym]), "promo": _phrase_hit(text, pol["promo_words"]),
                        "scorer": SCORER_VERSION, "sanitizer": SANITIZER_VERSION, "headline": text})
    return out
