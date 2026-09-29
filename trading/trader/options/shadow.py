"""Book O's shadow measurements: nothing here sends an order or changes a paper position.

- OPT-36 shadow book: the full O rules run on the logged chain snapshots and book shadow spreads under the cost
  model (entry at mid credit - half the quoted cost, exit at mid debit + half the quoted cost, plus model fees),
  with the same exits (OPT-22, OPT-23, the OPT-15 alert) and the same R as a real spread.
- OPT-34 skip shadows: every Claude skip opens its own shadow spread at the modelled fill, scored for
  information only (CL-9's code shrink does not apply to O).
- OPT-25 exit variants (take profit 50%, 21 DTE, stops at 2x and 1x the credit, hold to 7 DTE only) and
  OPT-39 variants (the same put spread on QQQ and IWM), logged only.
- OPT-20 variant (i) (VIX/VIX3M > 1 blocks) is logged on every evaluation; variant (ii) has no rule text to build.
- OPT-13 no-trade rate and the OPT-41 model-vs-logged credit check, from one evaluation row per run.
- OPT-38 statistics (n, win rate, average win/loss in R, E, SQN, worst R, slippage, max drawdown, no-trade rate)
  against zero and against BIL earned on the collateral.

State lives in `state_dir/options/shadow.json`, separate from O's paper ledger (`ledger.json`).
Money is in dollars for the whole position unless a name ends in `_per_share` or `_pc` (per contract).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, fields
from pathlib import Path
from types import SimpleNamespace

from ..config import STATE_DIR
from . import book as ob
from .ledger import DEFAULT_MODEL_FEE, OptionsBook
from .models import MULTIPLIER, OptionQuote, SpreadLot

SHADOW_FILE = "shadow.json"
MAX_EVALUATIONS = 5000  # one row per run; about 20 years of daily runs
EXIT_VARIANTS = ("tp50", "time21", "stop2x", "stop1x", "hold7")  # OPT-25
VARIANT_UNDERLYINGS = ("QQQ", "IWM")  # OPT-39 (shadow only)
DEFAULT_BIL_RATE = 0.04  # used only when no T-bill rate was logged; the report labels it "assumed"
# JSON types each stored field must have; anything else means a corrupt file (set aside at load).
_FIELD_TYPES = {"book": dict, "skips": dict, "variants": dict, "trackers": list, "evaluations": list,
                "predictions": list, "skip_log": list, "account": dict}


# --- state --------------------------------------------------------------------------------------------


@dataclass
class ShadowO:
    """Everything book O measures without trading. JSON-safe through to_dict/from_dict."""

    book: OptionsBook = field(default_factory=OptionsBook)  # OPT-36 rules shadow book
    skips: OptionsBook = field(default_factory=OptionsBook)  # OPT-34 skip shadows
    variants: OptionsBook = field(default_factory=OptionsBook)  # OPT-39 QQQ / IWM
    trackers: list[dict] = field(default_factory=list)  # OPT-25 exit variants, one per shadow spread
    evaluations: list[dict] = field(default_factory=list)  # one per run: candidate or no-trade reasons
    predictions: list[dict] = field(default_factory=list)  # OPT-34 CL-5 predictions of skips
    skip_log: list[dict] = field(default_factory=list)  # every skip decision, kept or dropped
    account: dict = field(default_factory=dict)  # last account read {date, equity, cash, uncommitted_cash}

    @staticmethod
    def path(state_dir: Path = STATE_DIR) -> Path:
        return Path(state_dir) / "options" / SHADOW_FILE

    def to_dict(self) -> dict:
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        for k in ("book", "skips", "variants"):
            d[k] = d[k].to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict | None) -> "ShadowO":
        d = dict(d or {})
        known = {f.name for f in fields(cls)}
        d = {k: v for k, v in d.items() if k in known}
        for k in ("book", "skips", "variants"):
            d[k] = OptionsBook.from_dict(d.get(k))
        return cls(**d)

    @classmethod
    def load(cls, state_dir: Path = STATE_DIR) -> "ShadowO":
        """Load the shadow state. A corrupt file is set aside (never silently reset over) and a new one starts."""
        p = cls.path(state_dir)
        if not p.exists():
            return cls()
        try:
            raw = json.loads(p.read_text())
            if not isinstance(raw, dict):
                raise TypeError("shadow state is not an object")
            for k, kind in _FIELD_TYPES.items():
                if k in raw and not isinstance(raw[k], kind):
                    raise TypeError(f"shadow field {k} is {type(raw[k]).__name__}, not {kind.__name__}")
            return cls.from_dict(raw)
        except Exception:  # noqa: BLE001 - any corrupt shape is set aside, never crashes every run
            p.replace(p.with_suffix(".corrupt.json"))
            return cls()

    def save(self, state_dir: Path = STATE_DIR) -> None:
        p = self.path(state_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2, default=str))
        tmp.replace(p)

    def held_symbols(self) -> list[str]:
        """Every leg of every open shadow, skip or variant spread (OPT-35 logs them whatever their range)."""
        out = []
        for b in (self.book, self.skips, self.variants):
            for lot in b.open_lots():
                out += [lot.short_leg.symbol, lot.long_leg.symbol]
        for t in self.trackers:
            if not _tracker_done(t):
                out += [t["short_symbol"], t["long_symbol"]]
        return sorted(set(out))


# --- model fills (OPT-36 cost model) --------------------------------------------------------------------


def _leg_quotes(short: OptionQuote | dict | None, long: OptionQuote | dict | None) -> dict | None:
    """{"short": {bid, ask}, "long": {bid, ask}} for the ledger's cost log, or None if a side is missing."""
    out = {}
    for name, q in (("short", short), ("long", long)):
        bid = ob.num(q.get("bid") if isinstance(q, dict) else getattr(q, "bid", None))
        ask = ob.num(q.get("ask") if isinstance(q, dict) else getattr(q, "ask", None))
        if bid is None or ask is None or bid < 0 or ask <= 0 or ask < bid:
            return None
        out[name] = {"bid": bid, "ask": ask}
    return out


def model_entry_fill(candidate: dict) -> dict | None:
    """OPT-36: the shadow entry fills at mid credit - half the quoted cost, for the candidate's contracts."""
    n = int(ob.num(candidate.get("contracts"), 0) or 0)
    mid, qc = ob.num(candidate.get("mid_credit")), ob.num(candidate.get("quoted_cost"))
    if n <= 0 or mid is None or qc is None:
        return None
    credit = mid - 0.5 * qc
    if credit <= 0:
        return None
    return {"contracts": n, "requested": n, "credit_per_share": credit, "fees": 0.0,
            "quotes": _leg_quotes(candidate.get("short"), candidate.get("long")), "spot": candidate.get("spot")}


def model_exit_price(lot: SpreadLot, quotes) -> dict:
    """OPT-36 exit price per share: mid debit + half the quoted cost, never above the width (OPT-15 cap).

    With a leg quote missing the spread is closed at the width (the worst case, flagged `unmarked`): exits never
    wait for option data. Returns {debit, uncapped, capped, unmarked, quotes}.
    """
    qmap = ob._by_symbol(quotes)
    s, lg = qmap.get(lot.short_leg.symbol), qmap.get(lot.long_leg.symbol)
    legs = _leg_quotes(s, lg)
    width = float(lot.width)
    if legs is None:
        return {"debit": width, "uncapped": None, "capped": True, "unmarked": True, "quotes": None}
    mid = s.mid - lg.mid
    qc = (s.ask - s.bid) + (lg.ask - lg.bid)
    raw = max(0.0, mid + 0.5 * qc)
    return {"debit": min(width, raw), "uncapped": raw, "capped": raw > width, "unmarked": False, "quotes": legs}


def expiry_value(lot: SpreadLot, spot) -> float:
    """Intrinsic value per share of a put (or call) vertical at expiry, clipped to 0..width; no spot = width."""
    s = ob.num(spot)
    if s is None:
        return float(lot.width)
    if lot.type == "call":
        raw = max(0.0, s - lot.short_leg.strike)
    else:
        raw = max(0.0, lot.short_leg.strike - s)
    return min(float(lot.width), raw)


# --- opening and closing shadow spreads ------------------------------------------------------------------


def open_shadow(ledger: OptionsBook, candidate: dict, date, *, tags: dict | None = None,
                policy: dict | None = None, id_prefix: str = "S") -> SpreadLot | None:
    """Book one shadow spread at the modelled fill (OPT-36 / OPT-34 / OPT-39). None when it cannot be priced.
    Lot ids read `<id_prefix>-<date>-<n>` (S shadow book, K skip shadow, V variant) so they never look like paper."""
    fill = model_entry_fill(candidate)
    if fill is None:
        return None
    ledger.seq += 1
    lot_id = f"{id_prefix}-{ob.to_date(date).isoformat()}-{ledger.seq}"
    return ledger.open_spread(candidate, fill, date, shadow=True, lot_id=lot_id, tags=dict(tags or {}),
                              policy=policy)


def close_shadow(ledger: OptionsBook, lot: SpreadLot, quotes, date, reason: str, *, spot=None,
                 policy: dict | None = None) -> dict | None:
    """Close a shadow spread at the modelled exit price; at or after expiry it settles at intrinsic value."""
    if ob.dte(lot.expiry, date) <= 0:
        fill = {"contracts": lot.contracts, "debit_per_share": expiry_value(lot, spot), "fees": 0.0,
                "settlement": True, "decision_spot": spot}
        return ledger.close_spread(lot.lot_id, fill, date, reason + " (settled at expiry)", policy=policy)
    px = model_exit_price(lot, quotes)
    fill = {"contracts": lot.contracts, "debit_per_share": px["debit"], "fees": 0.0, "quotes": px["quotes"],
            "decision_spot": spot}
    lot.tags["exit_model"] = {k: px[k] for k in ("uncapped", "capped", "unmarked")}
    return ledger.close_spread(lot.lot_id, fill, date, reason, policy=policy)


def update_exits(ledger: OptionsBook, quotes, spots: dict, date, policy: dict | None = None, *,
                 close_all_reason: str | None = None) -> list[dict]:
    """Run O's exits on every open shadow spread (OPT-22, OPT-23, OPT-15 alert; OPT-31 close-all when given).

    Exits never wait for option data: a missing quote closes at the width. Returns the closed records.
    """
    closed = []
    for lot in list(ledger.open_lots()):
        spot = (spots or {}).get(lot.underlying)
        reason = close_all_reason or ob.exit_signal(lot, quotes, spot, date, policy)
        if ob.dte(lot.expiry, date) <= 0 and reason is None:
            reason = "expiry"
        if reason is None:
            continue
        rec = close_shadow(ledger, lot, quotes, date, reason, spot=spot, policy=policy)
        if rec:
            closed.append(rec)
    return closed


def mark_book(ledger: OptionsBook, quotes, spots: dict, date) -> dict:
    """Record the shadow book's cumulative P&L for the breakers (OPT-30, OPT-31) and return today's change."""
    from .ledger import lot_unrealized

    total = ledger.realized_pnl_actual()
    unmarked = False
    for lot in ledger.open_lots():
        u = lot_unrealized(lot, quotes, (spots or {}).get(lot.underlying))
        total += u["unrealized"]
        unmarked = unmarked or u["unmarked"]
    day = ledger.record_mark(date, total)
    return {"o_pnl": total, "day_pnl": day, "unmarked": unmarked}


# --- OPT-25 exit variants ---------------------------------------------------------------------------------


def new_tracker(lot: SpreadLot) -> dict:
    """One OPT-25 tracker per shadow spread: the same entry, five alternative exits, R per contract."""
    credit = float(lot.entry_credit_per_share)
    return {"lot_id": lot.lot_id, "underlying": lot.underlying, "expiry": lot.expiry,
            "short_symbol": lot.short_leg.symbol, "long_symbol": lot.long_leg.symbol,
            "short_strike": lot.short_leg.strike, "width": float(lot.width), "credit": credit,
            "max_loss_pc": (float(lot.width) - credit) * MULTIPLIER, "entry_date": lot.entry_date,
            "fee": float(lot.tags.get("model_fee", DEFAULT_MODEL_FEE)), "variants": {v: None for v in EXIT_VARIANTS}}


def _tracker_done(t: dict) -> bool:
    return all(v is not None for v in (t.get("variants") or {}).values())


def _variant_hit(name: str, debit: float | None, credit: float, days: int, below: bool, policy: dict) -> bool:
    """OPT-25 triggers. Every variant still exits at DTE <= exit_dte (never hold into expiry week).
    tp50/time21/stop2x/stop1x also keep OPT-23; hold7 exits only at DTE <= exit_dte.
    stopNx: the loss (debit - credit) reaches N x the credit."""
    if days <= int(policy["exit_dte"]):
        return True
    if name == "hold7":
        return False
    if below:
        return True
    if debit is None:
        return False
    if name == "tp50":
        return debit <= 0.5 * credit + 1e-12
    if name == "time21":
        return days <= 21
    if name == "stop2x":
        return debit - credit >= 2 * credit - 1e-12
    if name == "stop1x":
        return debit - credit >= credit - 1e-12
    return False


def update_trackers(trackers: list[dict], quotes, spots: dict, date, policy: dict | None = None) -> int:
    """Resolve OPT-25 variants that trigger today. A missing quote is only a problem once an exit is due:
    then it is closed at the width like the base book. Returns how many variants resolved today."""
    p = ob.ob_policy(policy)
    qmap = ob._by_symbol(quotes)
    n = 0
    for t in trackers:
        if _tracker_done(t):
            continue
        days = ob.dte(t["expiry"], date)
        spot = ob.num((spots or {}).get(t["underlying"]))
        below = spot is not None and spot < float(t["short_strike"])
        s, lg = qmap.get(t["short_symbol"]), qmap.get(t["long_symbol"])
        debit = None
        if _leg_quotes(s, lg) is not None:
            debit = min(t["width"], max(0.0, s.mid - lg.mid + 0.5 * ((s.ask - s.bid) + (lg.ask - lg.bid))))
        for name, res in t["variants"].items():
            if res is None and _variant_hit(name, debit, t["credit"], days, below, p):
                d = t["width"] if debit is None else debit
                pnl = (t["credit"] - d) * MULTIPLIER - 4 * t["fee"]
                t["variants"][name] = {"date": ob.to_date(date).isoformat(), "debit": d, "unmarked": debit is None,
                                       "R": pnl / t["max_loss_pc"] if t["max_loss_pc"] > 0 else None}
                n += 1
    return n


def variant_summary(trackers: list[dict]) -> dict:
    """OPT-25 report: per exit variant, n, mean R and win rate (logged only, TEST FIRST)."""
    out = {}
    for v in EXIT_VARIANTS:
        rs = [t["variants"][v]["R"] for t in trackers if (t.get("variants") or {}).get(v)
              and ob.num(t["variants"][v].get("R")) is not None]
        out[v] = {"n": len(rs), "E": _mean(rs), "win_rate": _share(rs, lambda r: r > 0)}
    return out


# --- evaluations: OPT-13 no-trade rate, OPT-41 credit check, OPT-20 -------------------------------------


def opt20_record(snapshot: dict | None) -> dict:
    """OPT-20 variant (i), logged only: VIX / VIX3M from the snapshot's Cboe values (points). None = no data."""
    from .pricing import vix_term_ratio

    cboe = (snapshot or {}).get("cboe") or {}
    vix, v3 = (cboe.get("VIX") or {}), (cboe.get("VIX3M") or {})
    ratio = vix_term_ratio(vix.get("value"), v3.get("value"))
    ratio = None if ratio is None else round(ratio, 4)
    return {"vix": vix.get("value"), "vix3m": v3.get("value"), "vix_date": vix.get("date"),
            "vix3m_date": v3.get("date"), "ratio": ratio, "blocks_entry": None if ratio is None else ratio > 1.0,
            "stale": bool(vix.get("stale") or v3.get("stale")), "source": "cboe",
            "variant_ii": "not built: the rulebook gives no rule text for 'enter after volatility spikes'"}


def measurement_pair(quotes, spot, date, policy: dict | None, equity, *, underlying: str = "SPY") -> dict | None:
    """The spread the rules would look at today, ignoring book gates: OPT-18 short put and the OPT-8 width.

    Used for the OPT-13 cost share and the OPT-41 model-vs-logged credit even on days the book cannot trade.
    """
    p = ob.ob_policy(policy)
    puts = [q for q in (quotes or []) if isinstance(q, OptionQuote) and q.underlying == underlying and q.type == "put"]
    exps = ob.monthly_expiry_candidates(puts, date, p)
    eq = ob.num(equity)
    if not exps or eq is None or eq <= 0:
        return None
    chain = [q for q in puts if q.expiry == exps[0]]
    short, _ = ob.pick_short(chain, date, p)
    if short is None:
        return None
    pick, _ = ob.pick_width(short, chain, date, p, float(p["max_budgeted_loss_per_trade_pct"]) * eq)
    if pick is None:
        return None
    return {"expiry": exps[0], "dte": ob.dte(exps[0], date), "short_strike": short.strike,
            "long_strike": pick["long"].strike, "width": pick["width"], "logged_mid_credit": pick["mid_credit"],
            "quoted_cost": pick["quoted_cost"], "cost_share": pick["quoted_cost"] / pick["mid_credit"],
            "short_delta": short.delta, "spot": ob.num(spot)}


def model_credit(pair: dict | None, vix, *, rate=None, underlying: str = "SPY", table: dict | None = None) -> dict:
    """OPT-41: the pricing model's gross mid credit for the same strikes and DTE, and its ratio to the logged one."""
    from . import pricing

    if not pair or ob.num(vix) is None or ob.num(pair.get("spot")) is None:
        return {"model_mid_credit": None, "ratio": None}
    try:
        tab = table or pricing.load_skew_table()
        k = {"skew_table": tab, "rate": rate, "underlying": underlying}
        s = pricing.model_quote(pair["spot"], pair["short_strike"], pair["dte"], vix, "put", **k)["price"]
        lg = pricing.model_quote(pair["spot"], pair["long_strike"], pair["dte"], vix, "put", **k)["price"]
    except (ValueError, OSError, KeyError, TypeError) as e:
        return {"model_mid_credit": None, "ratio": None, "error": f"{type(e).__name__}: {e}"[:160]}
    m = s - lg
    logged = ob.num(pair.get("logged_mid_credit"))
    return {"model_mid_credit": m, "ratio": (m / logged) if logged and logged > 0 else None}


def add_evaluation(state: ShadowO, row: dict) -> dict:
    """One evaluation row per (date, when, underlying); a re-run replaces the earlier row."""
    key = (row.get("date"), row.get("when"), row.get("underlying"))
    state.evaluations = [r for r in state.evaluations
                         if (r.get("date"), r.get("when"), r.get("underlying")) != key] + [row]
    state.evaluations = state.evaluations[-MAX_EVALUATIONS:]
    return row


def _window_rows(evaluations, underlying: str = "SPY", when: str | None = "close") -> list[dict]:
    return [r for r in evaluations or [] if r.get("underlying") == underlying and r.get("in_window")
            and (when is None or r.get("when") == when)]


def no_trade_rate(evaluations, underlying: str = "SPY", when: str | None = "close") -> dict:
    """OPT-13 no-trade rate: share of eligible monthly cycles that OPT-13 alone blocked.

    A cycle (expiry) is eligible when some run in its entry window had regime permission and a usable pair;
    it is blocked by OPT-13 when no spread was opened in that cycle and some eligible run failed OPT-13.
    """
    cycles: dict[str, dict] = {}
    for r in _window_rows(evaluations, underlying, when):
        c = cycles.setdefault(r.get("expiry"), {"eligible": False, "opt13": False, "entered": False})
        c["eligible"] |= bool(r.get("eligible"))
        c["opt13"] |= bool(r.get("eligible") and r.get("opt13_blocked"))
        c["entered"] |= bool(r.get("candidate"))
    elig = [c for c in cycles.values() if c["eligible"]]
    blocked = [c for c in elig if c["opt13"] and not c["entered"]]
    return {"eligible_cycles": len(elig), "blocked_by_opt13": len(blocked),
            "rate": (len(blocked) / len(elig)) if elig else None}


def completed_cycles(evaluations, underlying: str = "SPY") -> list[str]:
    """OPT-41: monthly cycles whose whole entry window was evaluated in shadow (a run inside the window and a
    later run past its end, DTE < entry_dte.last)."""
    rows = [r for r in evaluations or [] if r.get("underlying") == underlying]
    last = max((str(r.get("date")) for r in rows), default=None)
    out = []
    for exp in sorted({r.get("expiry") for r in _window_rows(rows, underlying, None) if r.get("expiry")}):
        if last and ob.dte(exp, last) < int(ob.DEFAULTS["entry_dte"]["last"]):
            out.append(exp)
    return out


def credit_ratio_check(evaluations, cycles, underlying: str = "SPY") -> dict:
    """OPT-41: median of model / logged gross mid credit over every entry-window SESSION of `cycles` (n >= 10).

    One ratio per session: the after-close run's row (the 15:45 row of the same date is not a second sample).
    A session with only a 15:45 row counts once with that row."""
    per_day: dict[str, float] = {}
    for r in _window_rows(evaluations, underlying, None):
        if r.get("expiry") not in set(cycles) or ob.num(r.get("ratio")) is None:
            continue
        d = str(r.get("date"))
        if d not in per_day or r.get("when") == "close":
            per_day[d] = float(r["ratio"])
    ratios = sorted(per_day.values())
    med = _median(ratios)
    return {"n": len(ratios), "median": med,
            "ok": bool(len(ratios) >= 10 and med is not None and 0.8 <= med <= 1.25)}


# --- OPT-34 predictions (CL-5) ----------------------------------------------------------------------------


def resolve_predictions(state: ShadowO, bars: dict | None, date) -> list[dict]:
    """Score skip predictions once 20 sessions have passed (M-7 via trader.shadow; informational, OPT-34)."""
    if not bars:
        return []
    from .. import shadow as stock_shadow

    return stock_shadow.resolve_predictions(SimpleNamespace(predictions=state.predictions), bars,
                                            ob.to_date(date).isoformat())


# --- OPT-38 statistics --------------------------------------------------------------------------------------


def _mean(xs) -> float | None:
    xs = [float(x) for x in xs if ob.num(x) is not None]
    return sum(xs) / len(xs) if xs else None


def _median(xs) -> float | None:
    xs = sorted(float(x) for x in xs if ob.num(x) is not None)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def _share(xs, cond) -> float | None:
    xs = [x for x in xs if ob.num(x) is not None]
    return sum(1 for x in xs if cond(x)) / len(xs) if xs else None


def bil_r(rec: dict, default_rate: float = DEFAULT_BIL_RATE) -> tuple[float | None, bool]:
    """OPT-38 benchmark: BIL earned on the collateral (width x 100 x contracts) over the holding days, in R.
    Returns (R, assumed) where `assumed` says no T-bill rate was logged for this spread."""
    ml = ob.num(rec.get("max_loss"))
    if not ml or ml <= 0:
        return None, False
    rate = ob.num((rec.get("tags") or {}).get("bil_rate"))
    assumed = rate is None
    rate = default_rate if assumed else rate
    days = max(0, ob.dte(rec["date"], rec["entry_date"]))
    collateral = float(rec.get("width", 0.0)) * MULTIPLIER * int(ob.num(rec.get("contracts"), 0) or 0)
    return collateral * rate * days / 365.0 / ml, assumed


def max_drawdown_r(rs) -> float | None:
    """Largest peak-to-trough fall of the cumulative R curve (in R, as a positive number)."""
    xs = [float(x) for x in rs if ob.num(x) is not None]
    if not xs:
        return None
    cum = peak = dd = 0.0
    for r in xs:
        cum += r
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return dd


SQN_MIN_N = 30  # M-2: SQN is shown only from n >= 30
SQN_CAP_N = 100  # M-2: sqrt(min(n, 100))


def sqn(rs) -> float | None:
    """M-2 (as trader.metrics.sqn): sqrt(min(n, 100)) * mean / sd, shown only from n >= 30."""
    xs = [float(x) for x in rs if ob.num(x) is not None]
    if len(xs) < SQN_MIN_N:
        return None
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))
    return None if sd == 0 else math.sqrt(min(len(xs), SQN_CAP_N)) * m / sd


def _slippage_dollars(rec: dict) -> float | None:
    rows = ((rec.get("lot") or {}).get("events") or [])
    vals = [ob.num(r.get("slippage_dollars")) for r in rows if isinstance(r, dict)]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def opt38_stats(records: list[dict], *, equity=None, no_trade: dict | None = None,
                r_key: str = "R") -> dict:
    """OPT-38 (M-2) over closed-spread records: n, win rate, average win and loss in R, E = mean R_net, SQN,
    worst R, slippage in % of E, max drawdown (R), OPT-13's no-trade rate; benchmarks zero and BIL."""
    recs = [r for r in records or [] if ob.num(r.get(r_key)) is not None]
    rs = [float(r[r_key]) for r in recs]
    wins, losses = [r for r in rs if r > 0], [r for r in rs if r <= 0]
    bil = [bil_r(r) for r in recs]
    bil_rs = [b for b, _ in bil if b is not None]
    e = _mean(rs)
    slip = [s for s in (_slippage_dollars(r) for r in recs) if s is not None]
    eq = ob.num(equity)
    return {
        "n": len(rs), "win_rate": _share(rs, lambda r: r > 0), "avg_win_R": _mean(wins),
        "avg_loss_R": _mean(losses), "E": e, "E_paper": _mean(r.get("R_paper") for r in recs),
        "sqn": sqn(rs), "worst_R": min(rs) if rs else None, "max_drawdown_R": max_drawdown_r(rs),
        "slippage_dollars": sum(slip) if slip else None,
        "slippage_pct_of_E": (100.0 * sum(slip) / eq) if slip and eq else None,  # percent of equity E
        "no_trade_rate": (no_trade or {}).get("rate"),
        "benchmarks": {"zero": 0.0, "bil_E": _mean(bil_rs),
                       "bil_rate_assumed": any(a for _, a in bil),
                       "E_above_zero": None if e is None else e > 0,
                       "E_above_bil": None if e is None or not bil_rs else e > _mean(bil_rs)},
        "invested": [{"lot_id": r.get("lot_id"), "entry_date": r.get("entry_date"), "invested": r.get("max_loss")}
                     for r in recs],
    }
