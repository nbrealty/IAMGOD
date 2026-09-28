"""Options lab: a one-day, paper-only, defined-risk options experiment (owner request, 28 Sept 2026).

This is NOT book O and never counts in its record. It exists to learn options mechanics and intraday behaviour
on paper money, with hard locks that do not depend on anyone's judgement.

Run: cd trading && python lab/options_lab.py [--dry] [--expiry 0dte|short]   (0dte is the default; a restart of a
short-mode day must pass --expiry short, or that day's short-mode trades are not managed: the start row warns).

v2 ("v2-0dte", the default from 29 Sept 2026) trades SAME-DAY (0DTE) spreads. On 28 Sept v1 ("v1-short") traded
1-10 DTE spreads with a same-day time exit, and a 2-day option barely reacted to intraday moves, so the owner chose
to test same-day expiry. What the backtest says (reports/Minute trading backtest results.md), quoted by source:
section 1's summary says same-day options lost "about 4% to 47%" of the premium per trade; section 5's out-of-sample
table shows averages from -4.1% to -38.0% (pessimistic cost -10.1% to -44.0%). That proxy modelled BUYING single ATM
options, so it is evidence against the lab's debit spreads only. The credit spreads are short premium (time decay
works for them), which that backtest did not model: their result is an open question for this experiment. This is a
paper experiment to measure that, not a strategy expected to make money. Every trade carries a "backtest_expectation".

Quotes: the account has no OPRA agreement, so strike selection, the quote-spread filter, stops, take profit and the
close ladder all use Alpaca's INDICATIVE option feed (derived prices, not the real best bid/offer). Fills and stops
must not be read as real-market behaviour; every trade and the start row record quote_feed="indicative".

Modes (EXPIRY_MODE default, or --expiry 0dte|short on the command line):
- "0dte": the expiry must be TODAY. If SPY/QQQ has no contract expiring today, the checkpoint logs no_trade with
  the reason; it never falls back to a later expiry. Entries end at 13:30 and the close ladder is timed so positions
  should be flat by 14:40 (an alert fires if any are still open after that), 20 minutes before Alpaca may start
  selling out ITM legs the account cannot exercise (from 15:00), and well before its 0DTE order cutoff (15:30 for
  SPY/QQQ) and its auto-liquidation (15:45). See ALPACA_0DTE_FACTS below. Early-close days are skipped (their 0DTE
  cutoffs are unverified).
- "short": v1 kept for comparison: expiry 1 to 10 calendar days away, time exit 15:35, flat by 15:50. It differs
  from v1 in three safety guards only: the last-resort close goes out without a fresh quote, a broken two-leg close
  (legs changed at the broker, repeated rejects, or still open at close_by) legs out one leg at a time, and a
  contract with neither greeks nor a computable delta is dropped from the chain (v1 treated a missing delta as 0.0).

Hard locks (both modes):
- paper account only (the client is created with paper=True and must point at the paper API);
- two-leg vertical spreads only (same underlying, expiry and type, 1:1, one long and one short leg), OPENED as ONE
  multi-leg LIMIT DAY order, so the worst case is known before entry: never a naked short option. A position is
  only ever closed leg by leg when the two-leg close cannot work, and then the short leg is always bought back
  before the long leg is sold (a single-leg order can never leave a naked short);
- no two live lab trades share an option symbol (Alpaca keeps ONE net position per symbol, so a shared strike would
  make the position checks misread both trades and could turn a leg-out into a naked short);
- underlyings SPY and QQQ only; never held overnight (flat by the mode's close_by time);
- worst case per trade on the two-leg path (including the budgeted exit cost) <= MAX_LOSS_PER_TRADE; the leg-by-leg
  fallback is an emergency path whose prices are NOT capped (getting flat before the broker's cutoffs comes first):
  its closed row reports the realised loss against the trade's max_loss and alerts when it is over;
- today's realized losses plus all live trades (including an opening order whose send result was lost) <= MAX_LOSS_TOTAL, at most MAX_OPENS a
  day; a leg with a bid-ask wider than MAX_QUOTE_SPREAD is never traded;
- every order id starts with "LAB-" (0dte trade ids also carry a "Z": LAB-0929Z1-open-0), so the stock books and
  book O never touch these orders, and a 0dte run can never pick up a short-mode order by its client id;
- a trade is written to trades.json BEFORE its opening order is sent, so a restart never rebuilds a checkpoint
  under an id that may already have an order at Alpaca;
- no new entries after the mode's last_entry; an unfilled or partly filled 0dte opening order is cancelled after
  OPEN_TTL_SEC; exits step through a close ladder (mid plus growing steps, then through the natural price at
  hard_close, then at last_resort a credit close bids up to the width plus the budgeted exit cost and a debit close
  offers 0.01). No price guarantees a fill.

Strike selection: short leg ~0.30 delta for credit spreads, long leg ~0.50 delta for debit spreads. Alpaca's delta
is used when the snapshot has a usable one (finite, nonzero, the right sign, inside (-1, 1)). When it has no greeks
or an unusable one (at 15:48 on 28 Sept EVERY 0DTE SPY/QQQ snapshot had none), the delta is COMPUTED, never
guessed: the implied volatility is solved from the leg's mid quote by inverting Black-Scholes (bisection between IV_BOUNDS), then delta follows from that IV (see bs_price / implied_vol /
computed_delta below). A contract whose delta can be neither read nor computed is never the delta-selected leg; in
0dte mode it may still be the width partner, in short mode it is dropped entirely. Every leg, trade and entry row
records delta_source ("alpaca" or "computed").

Entries are rule-based and checked at fixed times; each writes its reasons to the journal. Signals use completed
regular-session minute bars only; the momentum rule needs a true 60-minute window (MOM_BARS completed bars, so it
cannot fire before 10:31) and otherwise logs why it was not checked. Right before an open is sent both legs' quotes
are re-read (ENTRY_QUOTE_MAX_AGE_SEC / ENTRY_QUOTE_MAX_MOVE): stale or moved -> re-priced once under the same caps,
or no trade; quote timestamps are journaled. Exits: take profit at
50% of the maximum gain, stop at 50% of the maximum loss (credit spreads: the underlying crossing the short strike,
with an 80% value backstop), or the time exit. Every journal row and trade record carries "lab_version". Logs go to
state/options_lab/<date>/0dte[-dry]/journal.jsonl in 0dte mode and state/options_lab/<date>[-dry]/journal.jsonl in
short mode (under TRADER_STATE_DIR or trading/state).
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
PREFIX = "LAB-"  # not "OPT-": book O and the stock books never match it
UNDERLYINGS = ("SPY", "QQQ")
MAX_LOSS_PER_TRADE = 250.0
MAX_LOSS_TOTAL = 750.0
MAX_OPENS = 4
WIDTH = {"SPY": 2.0, "QQQ": 2.0}
MIN_DTE, MAX_DTE = 1, 10  # "short" mode only
QUOTE_FEED = "indicative"  # no OPRA agreement on this account (read-only check, 28 Sept 2026: "OPRA agreement is not signed")

# --- Alpaca's 0DTE rules, checked 28 Sept 2026 ---------------------------------------------------------------------
# ALPACA_0DTE_FACTS:
# 1. Order cutoff on expiration day: "orders must be submitted before 3:15 p.m. ET for stocks and options, and before
#    3:30 p.m. ET for broad-based ETFs like SPY and QQQ. Orders placed after these times will be rejected."
#    https://alpaca.markets/support/what-are-the-cutoff-times-for-trading-0dte-options-on-alpaca
#    The API docs word it as: "Starting at 3:30 pm EST on the date of expiration, Alpaca continuously evaluates any
#    open positions that expire that day and stops accepting new orders to open/extend any positions."
#    https://docs.alpaca.markets/us/docs/options-trading-overview
#    UNVERIFIED: whether CLOSING orders are also rejected after the cutoff (support says all orders; the API docs say
#    open/extend). We assume closes are rejected too.
# 2. Auto-liquidation: "Expiring positions are auto-liquidated at 3:30 p.m. ET (stocks/options) and 3:45 p.m. ET
#    (broad-based ETFs) for risk management." https://alpaca.markets/learn/how-to-trade-0dte-options-on-alpaca
#    The API docs add: "In the event the account does not have sufficient buying power to exercise an ITM position,
#    Alpaca will sell-out the position within 1 hour before expiry", i.e. from 15:00 for a 16:00 expiry; ATM/OTM
#    positions "typically expire worthless". https://docs.alpaca.markets/docs/options-trading . This account cannot
#    exercise even one SPY contract (read-only check 28 Sept: options buying power about $70k, cash about $40k,
#    against about $76k per SPY contract; only 11 SPY shares held), so ANY ITM long leg qualifies for that sell-out,
#    which would leave the other leg alone. Hence the lab plans to be flat before 15:00 (PLANNING_CUTOFF) and checks
#    the account's positions before every close. UNVERIFIED: how auto-liquidation prices an mleg spread.
# 3. Multi-leg: mleg orders (order_class "mleg", limit, day) are supported at options level 3, all legs covered in
#    the same order; Alpaca's own 0DTE guide submits a 0DTE vertical as one OrderClass.MLEG order.
#    https://docs.alpaca.markets/docs/options-level-3-trading ,
#    https://alpaca.markets/learn/how-to-trade-0dte-options-on-alpaca . No 0DTE-specific mleg restriction found
#    (UNVERIFIED beyond the cutoff above, which applies to all orders).
# 4. Expiry / exercise: SPY and QQQ options are American-style and physically settled. Alpaca auto-exercises any
#    long contract ITM by $0.01 or more; a short leg left open "is subject to being assigned"; "The only way to
#    guarantee that you will not be assigned to the short position is to close out the position prior to the market
#    close." https://alpaca.markets/support/what-happens-when-my-short-option-position-expires ,
#    https://docs.alpaca.markets/docs/options-trading . Assignment delivers 100 shares per contract; in this shared
#    rules-book account those shares would be seen by the stock book. On PAPER, assignment activities (NTAs) appear
#    only the next day. Hence: flat long before the cutoff.
# 5. UNVERIFIED: cutoffs on early-close (half) days. The lab does not trade 0DTE on a day that closes before 16:00.
# 6. Option quotes on this account are INDICATIVE ("not actual OPRA quotes, they're just indicative derivatives",
#    https://docs.alpaca.markets/us/docs/historical-option-data); OPRA returns "OPRA agreement is not signed".
BROKER_0DTE_CUTOFF = {"SPY": "15:30", "QQQ": "15:30"}  # no new orders accepted from here on expiration day
BROKER_0DTE_CUTOFF_OTHER = "15:15"                     # stocks/other underlyings; SPY/QQQ fall under the 15:30 rule
BROKER_0DTE_SELLOUT = "15:00"                          # ITM legs the account cannot exercise may be sold from here
BROKER_0DTE_LIQUIDATION = "15:45"                      # SPY/QQQ expiring positions auto-liquidated
PLANNING_CUTOFF = min(BROKER_0DTE_SELLOUT, BROKER_0DTE_CUTOFF_OTHER)  # "15:00": the earliest broker action we know of

# Timing per mode (New York time, HH:MM). The close ladder runs from time_exit to close_by; after close_by a
# position still open is closed leg by leg (short leg first).
TIMING = {
    "0dte": {
        "entry_times": ("10:15", "11:30", "12:15", "13:15"),
        "last_entry": "13:30",   # 90 minutes before the planning cutoff
        "open_cancel": "13:45",  # an unfilled open order is cancelled from here at the latest (never re-sent)
        "time_exit": "14:00",    # time exit starts: 40 minutes of ladder before close_by
        "hard_close": "14:20",   # from here the close pays through the natural price, re-priced every 30 s
        "last_resort": "14:30",  # credit close bids up to width + exit budget, debit close offers 0.01
        "close_by": "14:40",     # target flat time: 20 min before a possible 15:00 sell-out, 50 before 15:30
    },
    "short": {  # v1, 28 Sept 2026
        "entry_times": ("10:15", "11:30", "13:00", "14:15"),
        "last_entry": "14:30",
        "open_cancel": "14:45",
        "time_exit": "15:35",
        "hard_close": "15:45",
        "last_resort": "15:48",
        "close_by": "15:50",
    },
}
OPEN_TTL_SEC = {"0dte": 300, "short": None}  # 0dte: an opening order still working after 5 min is cancelled
OPEN_LOOKUP_GRACE_SEC = 60  # an open whose send result was lost counts as absent only if not found after this
EXPIRY_MODE = "0dte"  # default; "--expiry short" runs v1 for comparison
VERSION = {"0dte": "v2-0dte", "short": "v1-short"}
BACKTEST_EXPECTATION = {
    "0dte": ("reports/Minute trading backtest results.md: section 1 summary, same-day options lost about 4-47% of "
             "premium per trade; section 5 out-of-sample averages -4.1% to -38.0% (pessimistic -10.1% to -44.0%). "
             "That proxy BOUGHT single ATM options: evidence against debit spreads only; credit spreads (short "
             "premium) were not modelled, so their result is an open question"),
    "short": ("v1 comparison run (1-10 DTE); reports/Minute trading backtest results.md section 5 covers bought "
              "same-day single options only (out-of-sample averages -4.1% to -38.0% of premium per trade)"),
}
REPRICE_SEC = 60      # an unfilled close is cancelled and re-priced one step further after this
STEPS = (0.03, 0.06, 0.10, 0.15, 0.25, 0.40)
LAST_RESORT_OVER_NATURAL = 0.05  # last-resort credit close bids the natural price plus this (capped by the budget)
CLOSE_FAILS_TO_LEG_OUT = 3       # two-leg closes rejected / not accepted this many times -> close leg by leg
LEG_REPRICE_SEC = 30
LEG_STEPS = (0.05, 0.10, 0.20, 0.35, 0.50, 0.75, 1.00)
LEG_FAILS_ALERT = 4  # single-leg sends not accepted this many times in a row -> ALERT_LEG_STUCK
TERMINAL = {"filled", "canceled", "expired", "rejected", "done_for_day", "replaced", "stopped", "suspended"}
# verify_gone: both legs missing from the account on two reads; positions are re-read every pass until close_by.
LIVE = ("pending_open", "open", "pending_close", "legging_out", "verify_gone")
CAP_STATUSES = LIVE + ("id_conflict",)  # counted toward the total cap and max opens
TAKE_PROFIT, STOP = 0.5, 0.5
BACKSTOP = 0.8  # credit spreads stop on the underlying crossing the short strike; this value stop is the backstop
MAX_QUOTE_SPREAD = 0.20  # a leg with a bid-ask wider than this ($) is not traded
MOM_BARS = 61  # completed regular-session 1-minute bars a true 60-minute move needs (first possible at 10:31)
# Entry quote check (day-1 post-mortem: the 10:15 limit came from an indicative quote about a minute old). Right
# before an open is sent both legs' latest quotes are re-read. A fresh quote older than this -> no trade; a planned
# quote older than this (or of unknown age), or a fresh mid more than ENTRY_QUOTE_MAX_MOVE away from the planned
# net -> re-priced ONCE from the fresh quote under the same caps (never a bigger size), else no trade.
ENTRY_QUOTE_MAX_AGE_SEC = 30
ENTRY_QUOTE_MAX_MOVE = 0.05

# --- computed delta (only when the snapshot has no greeks) ---------------------------------------------------------
# Black-Scholes-Merton on the leg's mid quote. Inputs, and why they are good enough for a same-day delta:
# - spot: the underlying's latest trade (IEX); if that read fails, the last minute-bar close (recorded as spot_source);
# - T: calendar time to 16:00 ET on the expiry date, in years of 365 days, floored at MIN_T_YEARS. Delta depends on
#   sigma*sqrt(T) (plus r*T and q*T terms that are ~1e-5 on 0DTE), and the IV is solved with the same T, so the
#   calendar-vs-trading-time convention changes the reported IV but hardly the delta;
# - RISK_FREE_RATE: an approximate short T-bill yield (an assumption, not a live read). On 0DTE r*T is ~2.6e-5, but
#   the price term r*K*T is about $0.02 at 10:15 for SPY near 765 (0.04*765*5.75/8760), i.e. one to two ticks in the
#   morning and less later. Deltas in the 0.1-0.7 band move by at most ~0.003 between r=0.04 and r=0, so strike
#   picks are unaffected; only deep ITM contracts (extrinsic under ~2 cents) can come back "IV below 0.01";
# - DIVIDEND_YIELD: 0. SPY (~1.1%/yr) and QQQ (~0.6%/yr) yields move a same-day price by far less than a tick; the
#   model ignores discrete ex-dividend days (SPY/QQQ go ex on quarterly dates, not on a normal lab day);
# - SPY/QQQ options are American; with no dividend before expiry a call has no early-exercise value and a same-day
#   put's is at most ~r*K*T (about 1-2 cents, see above), so the European formula is used. The intrinsic check below
#   is the undiscounted (American) one, so it and the European model disagree by that 1-2 cents on deep ITM puts.
# A delta is computed only when bid > 0, ask > bid and the mid is at least MIN_EXTRINSIC above intrinsic value; the IV
# solve is bracketed by IV_BOUNDS and anything outside it, or not converged, gives delta None with a logged reason.
RISK_FREE_RATE = 0.04
DIVIDEND_YIELD = 0.0
TICK = 0.01
MIN_EXTRINSIC = TICK            # mid must exceed intrinsic by at least one tick
IV_BOUNDS = (0.01, 5.0)         # bisection bracket for the IV solve (annualised)
IV_PRICE_TOL = 1e-4             # $ difference between the model price and the mid that counts as solved
IV_MAX_ITER = 100
MIN_T_YEARS = 5 / (365 * 24 * 60)  # 5 minutes: the floor on time to expiry
EXPIRY_CLOCK = (16, 0)          # SPY/QQQ options expire at the 16:00 ET close (full days only in 0dte mode)


def ny_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(NY)


def hhmm(t: datetime) -> str:
    return t.strftime("%H:%M")


def minutes(a: str, b: str) -> int:
    """Minutes from HH:MM `a` to HH:MM `b` (negative when b is earlier)."""
    (ah, am), (bh, bm) = (map(int, a.split(":")), map(int, b.split(":")))
    return (bh * 60 + bm) - (ah * 60 + am)


def lab_dir(state_dir: Path, day: date, mode: str, dry: bool) -> Path:
    """0dte: options_lab/<date>/0dte[-dry]/ ; short (v1 layout): options_lab/<date>[-dry]/."""
    root = Path(state_dir) / "options_lab"
    if mode == "0dte":
        return root / day.isoformat() / ("0dte" + ("-dry" if dry else ""))
    return root / (day.isoformat() + ("-dry" if dry else ""))


def pick_expiry(exps, today: date, mode: str) -> tuple[date | None, str]:
    """The expiry to trade from the listed expiries, or None and why. 0dte: today or nothing (never a later one)."""
    exps = sorted(set(exps))
    if mode == "0dte":
        if today in exps:
            return today, "ok"
        later = [e for e in exps if e > today]
        return None, ("no contract expires today (0dte mode never falls back to a later expiry"
                      + (f"; nearest listed is {later[0].isoformat()})" if later else ")"))
    ok = [e for e in exps if MIN_DTE <= (e - today).days <= MAX_DTE]
    # 2+ calendar days gives the trade a little room; fall back to the nearest allowed expiry.
    for e in ok:
        if (e - today).days >= 2:
            return e, "ok"
    return (ok[0], "ok") if ok else (None, f"no expiry {MIN_DTE}-{MAX_DTE} days out")


def _err(e: Exception) -> str:
    return f"{type(e).__name__}: {str(e)[:300]}"


# --- Black-Scholes (computed delta) --------------------------------------------------------------------------------
def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _d1(s: float, k: float, t: float, sigma: float, r: float, q: float) -> float:
    return (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))


def bs_price(s: float, k: float, t: float, sigma: float, typ: str, r: float = RISK_FREE_RATE,
             q: float = DIVIDEND_YIELD) -> float:
    """European Black-Scholes-Merton price of a call or put."""
    d1 = _d1(s, k, t, sigma, r, q)
    d2 = d1 - sigma * math.sqrt(t)
    if typ == "call":
        return s * math.exp(-q * t) * _ncdf(d1) - k * math.exp(-r * t) * _ncdf(d2)
    return k * math.exp(-r * t) * _ncdf(-d2) - s * math.exp(-q * t) * _ncdf(-d1)


def bs_delta(s: float, k: float, t: float, sigma: float, typ: str, r: float = RISK_FREE_RATE,
             q: float = DIVIDEND_YIELD) -> float:
    """Black-Scholes-Merton delta: call in (0, 1), put in (-1, 0)."""
    n = _ncdf(_d1(s, k, t, sigma, r, q))
    return math.exp(-q * t) * (n if typ == "call" else n - 1.0)


def implied_vol(price: float, s: float, k: float, t: float, typ: str, r: float = RISK_FREE_RATE,
                q: float = DIVIDEND_YIELD, bounds: tuple[float, float] = IV_BOUNDS, tol: float = IV_PRICE_TOL,
                max_iter: int = IV_MAX_ITER) -> tuple[float | None, str]:
    """(IV, "ok") by bisection inside `bounds`, or (None, why). The price is increasing in sigma, so a price below
    the model price at the lower bound or above it at the upper bound has no IV in range."""
    lo, hi = bounds
    if not (price > 0 and s > 0 and k > 0 and t > 0):
        return None, "bad inputs (price, spot, strike and time must be > 0)"
    p_lo, p_hi = bs_price(s, k, t, lo, typ, r, q), bs_price(s, k, t, hi, typ, r, q)
    if price < p_lo - tol:
        return None, f"IV below {lo} (mid {price:.4f} < model {p_lo:.4f} at the floor)"
    if price > p_hi + tol:
        return None, f"IV above {hi} (mid {price:.4f} > model {p_hi:.4f} at the cap)"
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        diff = bs_price(s, k, t, mid, typ, r, q) - price
        if abs(diff) <= tol:
            return mid, "ok"
        if diff > 0:
            hi = mid
        else:
            lo = mid
    return None, f"IV solve did not converge in {max_iter} steps (bracket {lo:.6f}-{hi:.6f})"


def years_to_expiry(expiry: date, now: datetime) -> float:
    """Calendar years from `now` to 16:00 ET on `expiry`, floored at MIN_T_YEARS."""
    end = datetime.combine(expiry, datetime.min.time(), NY).replace(hour=EXPIRY_CLOCK[0], minute=EXPIRY_CLOCK[1])
    return max(MIN_T_YEARS, (end - now).total_seconds() / (365 * 24 * 3600))


def computed_delta(bid: float, ask: float, s: float, k: float, t: float, typ: str, r: float = RISK_FREE_RATE,
                   q: float = DIVIDEND_YIELD) -> tuple[float | None, float | None, str]:
    """(delta, iv, "ok") from the mid quote, or (None, None, why). Refuses rather than guesses."""
    if bid is None or ask is None or not bid > 0:
        return None, None, "bid is 0 or missing"
    if not ask > bid:
        return None, None, "ask is not above bid"
    if not s or s <= 0:
        return None, None, "no underlying price"
    mid = (bid + ask) / 2
    intrinsic = max(0.0, s - k) if typ == "call" else max(0.0, k - s)
    if mid - intrinsic < MIN_EXTRINSIC - 1e-9:
        return None, None, f"mid {mid:.3f} is not a tick above intrinsic {intrinsic:.3f}"
    iv, why = implied_vol(mid, s, k, t, typ, r, q)
    if iv is None:
        return None, None, why
    d = bs_delta(s, k, t, iv, typ, r, q)
    if not (0.0 < d < 1.0 if typ == "call" else -1.0 < d < 0.0):
        return None, None, f"computed delta {d:.4f} out of range"
    return d, iv, "ok"


def fill_deltas(rows: list[dict], s: float, t: float) -> dict:
    """Give every row without an Alpaca delta a computed one where possible (delta_source "computed"), else
    delta None with delta_why. Rows with Alpaca's delta are left as they are. Returns counts for the journal."""
    stats = {"alpaca": 0, "computed": 0, "none": 0, "reasons": {}}
    for r in rows:
        if r["delta"] is not None:
            stats["alpaca"] += 1
            continue
        d, iv, why = computed_delta(r["bid"], r["ask"], s, r["strike"], t, r["type"])
        if d is None:
            r.update({"delta_source": None, "delta_iv": None, "delta_why": why})
            stats["none"] += 1
            key = re.sub(r"-?\d+\.\d{3,}", "#", why.split(" (")[0])  # group reasons without their per-leg values
            stats["reasons"][key] = stats["reasons"].get(key, 0) + 1
        else:
            r.update({"delta": round(d, 4), "delta_source": "computed", "delta_iv": round(iv, 4), "delta_why": "ok"})
            stats["computed"] += 1
    return stats


def _delta_source(r: dict) -> str | None:
    return None if r.get("delta") is None else r.get("delta_source", "alpaca")


class Lab:
    mode = EXPIRY_MODE  # set per instance in __init__

    @property
    def tm(self) -> dict:
        return TIMING[self.mode]

    @property
    def version(self) -> str:
        return VERSION[self.mode]

    def __init__(self, state_dir: Path, *, dry: bool = False, mode: str = EXPIRY_MODE):
        if mode not in TIMING:
            raise ValueError(f"expiry mode must be one of {sorted(TIMING)}, not {mode!r}")
        self.mode = mode
        self.full_day: bool | None = None  # 0dte: today closes at 16:00 (checked once via the calendar)
        self.cutoff_alerted = False
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.trading.client import TradingClient

        key, secret = os.environ["ALPACA_RULES_KEY"], os.environ["ALPACA_RULES_SECRET"]
        self.trading = TradingClient(key, secret, paper=True)
        self.stocks = StockHistoricalDataClient(key, secret)
        self.options = OptionHistoricalDataClient(key, secret)
        self.dry = dry
        self.today = ny_now().date()
        self.state_dir = Path(state_dir)
        # short mode keeps v1's directory (and ids) so a restart finds its own trades; 0dte uses <date>/0dte/.
        self.dir = lab_dir(self.state_dir, self.today, mode, dry)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.book_path = self.dir / "trades.json"
        self.trades: list[dict] = json.loads(self.book_path.read_text()) if self.book_path.exists() else []
        self.done_checkpoints: set[str] = {t.get("checkpoint") for t in self.trades if t.get("checkpoint")}
        self.done_checkpoints |= set(json.loads((self.dir / "checkpoints.json").read_text())) \
            if (self.dir / "checkpoints.json").exists() else set()

    def realized_loss(self) -> float:
        """Today's realized losses (net of realized gains, never below 0). They count against MAX_LOSS_TOTAL,
        so the whole day, not just the trades open at once, can lose at most MAX_LOSS_TOTAL."""
        return max(0.0, -sum(t.get("pnl", 0.0) or 0.0 for t in self.trades if t.get("status") == "closed"))

    # --- logging -------------------------------------------------------------------------------------------
    def log(self, event: str, **data) -> None:
        # `event` (not `kind`): callers pass the signal's `kind=` as data.
        row = {"time": ny_now().isoformat(timespec="seconds"), "event": event, "lab_version": self.version, **data}
        with open(self.dir / "journal.jsonl", "a") as f:
            f.write(json.dumps(row, default=str) + "\n")
        print(f"[{hhmm(ny_now())}] {event}: {json.dumps(data, default=str)[:400]}", flush=True)

    def save(self) -> None:
        self.book_path.write_text(json.dumps(self.trades, indent=1, default=str))
        (self.dir / "checkpoints.json").write_text(json.dumps(sorted(self.done_checkpoints)))

    # --- market data ---------------------------------------------------------------------------------------
    def minute_bars(self, sym: str):
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        import pandas as pd

        start = datetime.combine(self.today, datetime.min.time(), NY).replace(hour=9, minute=30)
        if ny_now() <= start + timedelta(minutes=1):
            return pd.DataFrame()
        df = self.stocks.get_stock_bars(StockBarsRequest(symbol_or_symbols=sym, timeframe=TimeFrame.Minute,
                                                         start=start, feed=DataFeed.IEX)).df
        return df.xs(sym, level="symbol") if len(df) else df

    def chain(self, sym: str, expiry: date, spot: float) -> list[dict]:
        from alpaca.data.enums import OptionsFeed
        from alpaca.data.requests import OptionChainRequest

        snaps = self.options.get_option_chain(OptionChainRequest(
            underlying_symbol=sym, expiration_date=expiry, feed=OptionsFeed.INDICATIVE,
            strike_price_gte=round(spot * 0.93, 0), strike_price_lte=round(spot * 1.07, 0)))
        out = []
        for osym, s in snaps.items():
            q, g = getattr(s, "latest_quote", None), getattr(s, "greeks", None)
            if q is None or q.bid_price is None or q.ask_price is None:
                continue
            typ = "call" if osym[-9] == "C" else "put"
            # Alpaca's delta when present AND usable; missing greeks (common on 0DTE snapshots) or an unusable
            # value (NaN, 0.0, wrong sign, outside (-1, 1)) -> computed below, never a guessed 0.0.
            raw = getattr(g, "delta", None) if g is not None else None
            try:
                delta = None if raw is None else float(raw)
            except (TypeError, ValueError):
                delta = None
            bad = delta is not None and not (math.isfinite(delta) and (0.0 < delta < 1.0 if typ == "call"
                                                                        else -1.0 < delta < 0.0))
            row = {"symbol": osym, "type": typ, "strike": int(osym[-8:]) / 1000.0, "bid": float(q.bid_price),
                   "ask": float(q.ask_price), "delta": None if bad else delta,
                   "delta_source": None if (bad or delta is None) else "alpaca",
                   "iv": getattr(s, "implied_volatility", None)}
            qt = self._quote_time(q)
            row["quote_time"] = qt.isoformat() if qt else None  # the entry quote check measures its age
            if bad:
                row["alpaca_delta_rejected"] = str(raw)
            out.append(row)
        if any(r["delta"] is None for r in out):
            live = self.underlying_price(sym)
            s_used, s_src = (live, "latest_trade") if live else (spot, "minute_bar_close")
            t_years = years_to_expiry(expiry, ny_now())
            stats = fill_deltas(out, s_used, t_years)
            for r in out:  # what a computed delta needs to be reproduced from the journal
                if r.get("delta_source") == "computed":
                    r.update({"delta_spot": s_used, "delta_spot_source": s_src, "delta_t_years": t_years})
            self.log("delta_computed", underlying=sym, expiry=expiry.isoformat(), contracts=len(out),
                     alpaca=stats["alpaca"], computed=stats["computed"], none=stats["none"],
                     none_reasons=stats["reasons"], spot=s_used, spot_source=s_src, t_years=t_years,
                     minutes_to_expiry=round(t_years * 365 * 24 * 60, 2), r=RISK_FREE_RATE, q=DIVIDEND_YIELD,
                     iv_bounds=list(IV_BOUNDS),
                     alpaca_delta_rejected={r["symbol"]: r["alpaca_delta_rejected"] for r in out
                                            if "alpaca_delta_rejected" in r})
        return out

    def expiry_for(self, sym: str) -> tuple[date | None, str]:
        from alpaca.trading.requests import GetOptionContractsRequest

        if self.mode == "0dte":
            req = GetOptionContractsRequest(underlying_symbols=[sym], expiration_date=self.today, limit=1000)
        else:
            req = GetOptionContractsRequest(
                underlying_symbols=[sym], expiration_date_gte=self.today + timedelta(days=MIN_DTE),
                expiration_date_lte=self.today + timedelta(days=MAX_DTE), limit=1000)
        r = self.trading.get_option_contracts(req)
        exps = {c.expiration_date for c in (r.option_contracts or []) if c.expiration_date}
        return pick_expiry(exps, self.today, self.mode)

    def check_full_day(self) -> bool | None:
        """0dte: True when today's session closes at 16:00 (half-day cutoffs are not verified). Cached once known."""
        if self.full_day is None:
            from alpaca.trading.requests import GetCalendarRequest

            try:
                cal = self.trading.get_calendar(GetCalendarRequest(start=self.today, end=self.today))
                day = next((c for c in cal if c.date == self.today), None)
                self.full_day = bool(day and day.close.strftime("%H:%M") == "16:00")
            except Exception as e:  # unknown: this checkpoint refuses, the next one asks again
                self.log("calendar_error", error=_err(e))
        return self.full_day

    def minutes_to_cutoff(self, sym: str, now: str | None = None) -> int | None:
        """Minutes from now to the broker's 0DTE order cutoff for `sym` (0dte mode only)."""
        if self.mode != "0dte":
            return None
        return minutes(now or hhmm(ny_now()), BROKER_0DTE_CUTOFF.get(sym, BROKER_0DTE_CUTOFF_OTHER))

    # --- the rules that pick a trade ------------------------------------------------------------------------
    def regular_completed(self, df):
        """Only regular-session bars (from 09:30 ET today) that are COMPLETE: a bar is stamped with its start
        minute, so it is complete once its start + 1 minute <= now. Pre-market bars and the bar still forming
        are dropped (day 1 read a partial 10:16 bar)."""
        if not len(df):
            return df
        import pandas as pd

        start = datetime.combine(self.today, datetime.min.time(), NY).replace(hour=9, minute=30)
        idx = pd.DatetimeIndex(df.index)
        return df[(idx >= start) & (idx + pd.Timedelta(minutes=1) <= ny_now())]

    @staticmethod
    def momentum_60m(df) -> tuple[float | None, dict]:
        """A TRUE 60-minute move: the last completed close against the close of the bar stamped exactly 60 minutes
        earlier, which needs MOM_BARS (61) completed regular-session bars. Before that (e.g. at 10:15, when only 45
        exist) or when the bar 60 minutes back is missing (a feed gap), the momentum rule does not fire: (None, why).
        Day 1 fell back to the move since the first minute and journaled it as a 60-minute move."""
        import pandas as pd

        n = len(df)
        if n < MOM_BARS:
            return None, {"mom60_pct": None, "mom60_why": (
                f"only {n} completed regular-session bars; a true 60-minute move needs {MOM_BARS}: momentum rule "
                "not checked")}
        last_ts = df.index[-1]
        ref_ts = last_ts - pd.Timedelta(minutes=60)
        if ref_ts not in df.index:
            return None, {"mom60_pct": None, "mom60_why": (
                f"no bar at {ref_ts.isoformat()} (exactly 60 minutes before the last completed bar): momentum rule "
                "not checked")}
        ref = df.loc[ref_ts, "close"]
        ref = float(ref.iloc[-1] if hasattr(ref, "iloc") else ref)
        mom = float(df["close"].iloc[-1]) / ref - 1
        return mom, {"mom60_pct": round(mom * 100, 3), "mom60_window": [ref_ts.isoformat(), last_ts.isoformat()],
                     "mom60_minutes": 60, "mom60_ref_close": ref}

    def signal(self, sym: str) -> tuple[str | None, dict]:
        """Opening-range + VWAP trend rule. Up day -> bull put credit spread; down day -> bear call credit spread;
        strong 60-minute momentum -> a debit spread in its direction. Otherwise no trade."""
        df = self.regular_completed(self.minute_bars(sym))
        if len(df) < 45:
            return None, {"why": "not enough minute bars yet", "bars_completed": len(df)}
        close = df["close"]
        spot = float(close.iloc[-1])  # last COMPLETED bar's close (a bar still forming is never used)
        orh, orl = float(df["high"].iloc[:30].max()), float(df["low"].iloc[:30].min())
        vwap = float((df["close"] * df["volume"]).sum() / max(1.0, df["volume"].sum()))
        mom60, mom_info = self.momentum_60m(df)
        info = {"spot": spot, "opening_range": [orh, orl], "vwap": round(vwap, 2), "bars_completed": len(df),
                "last_bar": df.index[-1].isoformat(), **mom_info}
        if mom60 is not None and abs(mom60) >= 0.004:
            return ("call_debit" if mom60 > 0 else "put_debit"), {**info, "why": "60-minute move of 0.4% or more"}
        if spot > orh and spot > vwap:
            return "put_credit", {**info, "why": "above the 30-minute opening range and VWAP"}
        if spot < orl and spot < vwap:
            return "call_credit", {**info, "why": "below the 30-minute opening range and VWAP"}
        return None, {**info, "why": "inside the opening range or mixed signals: no trade"}

    def build(self, sym: str, kind: str, spot: float) -> tuple[dict | None, str]:
        expiry, why = self.expiry_for(sym)
        if expiry is None:
            return None, why
        rows = self.chain(sym, expiry, spot)
        typ = "put" if kind.startswith("put") else "call"
        legs = sorted([r for r in rows if r["type"] == typ], key=lambda r: r["strike"])
        width = WIDTH[sym]
        credit = kind.endswith("credit")
        # Short leg ~0.30 delta for credit spreads; long leg ~0.50 delta (near the money) for debit spreads.
        target = 0.30 if credit else 0.50
        with_greeks = [r for r in legs if r["delta"] is not None]  # Alpaca's delta or a computed one
        no_greeks = [r["symbol"] for r in legs if r["delta"] is None]
        if no_greeks:
            self.log("legs_skipped", underlying=sym, type=typ, expiry=expiry.isoformat(), count=len(no_greeks),
                     of=len(legs), sample=no_greeks[:6],
                     sample_why=[r.get("delta_why") for r in legs if r["delta"] is None][:6],
                     delta_sources={src: sum(1 for r in with_greeks if _delta_source(r) == src)
                                    for src in ("alpaca", "computed")},
                     why=("no greeks in the snapshot and no computable delta: never the delta-selected leg "
                          "(delta is never guessed)"
                          + ("; dropped from the chain in short mode" if self.mode == "short"
                             else "; may still be the width partner")))
        if self.mode == "short":  # v1 dropped contracts without greeks entirely
            legs = with_greeks
        by_strike = {r["strike"]: r for r in legs}
        if not legs and not no_greeks:
            return None, "no quotes"
        if not with_greeks:
            return None, (f"no {typ} contract has greeks or a computed delta ({len(no_greeks)} skipped): delta "
                          "target not checkable")
        pick = min(with_greeks, key=lambda r: abs(abs(r["delta"]) - target))
        if credit:
            short = pick
            far = short["strike"] - width if typ == "put" else short["strike"] + width
            long = by_strike.get(far)
        else:
            long = pick
            far = long["strike"] + width if typ == "call" else long["strike"] - width
            short = by_strike.get(far)
        if long is None or short is None:
            return None, f"no {width:.0f}-wide partner strike"
        clash = self.leg_overlap({"long": long["symbol"], "short": short["symbol"]})
        if clash:
            return None, (f"{', '.join(clash)} is already a leg of a live lab trade (Alpaca nets one position per "
                          "symbol: the position checks could not tell the trades apart)")
        priced, why = self.price_spread(long, short, credit, width, kind)
        if priced is None:
            return None, why
        now = hhmm(ny_now())
        return {"lab_version": self.version, "expiry_mode": self.mode, "quote_feed": QUOTE_FEED,
                "underlying": sym, "kind": kind, "expiry": expiry.isoformat(), "type": typ, "credit": credit,
                "long": long["symbol"], "short": short["symbol"], "long_strike": long["strike"],
                "short_strike": short["strike"], "width": width, **priced,
                "long_quote_time": long.get("quote_time"), "short_quote_time": short.get("quote_time"),
                "short_delta": short["delta"], "long_delta": long["delta"],
                "delta_source": _delta_source(pick),  # the delta-selected leg's source
                "short_delta_source": _delta_source(short), "long_delta_source": _delta_source(long),
                "short_delta_iv": short.get("delta_iv"), "long_delta_iv": long.get("delta_iv"),
                "short_alpaca_iv": short.get("iv"), "long_alpaca_iv": long.get("iv"),
                # spot and T behind the computed deltas (one chain read: the same for both legs; None if neither
                # leg's delta was computed)
                **{k: next((r[k] for r in (short, long) if r.get(k) is not None), None)
                   for k in ("delta_spot", "delta_spot_source", "delta_t_years")},
                "underlying_price": spot, "entry_clock": now, "minutes_to_broker_cutoff": self.minutes_to_cutoff(sym, now),
                "minutes_to_planning_cutoff": minutes(now, PLANNING_CUTOFF) if self.mode == "0dte" else None,
                "minutes_to_close_by": minutes(now, self.tm["close_by"]),
                "backtest_expectation": BACKTEST_EXPECTATION[self.mode]}, "ok"

    def price_spread(self, long: dict, short: dict, credit: bool, width: float, kind: str,
                     max_qty: int | None = None, exclude: dict | None = None) -> tuple[dict | None, str]:
        """Net price, size and risk of a spread from its legs' bid/ask (rows with "bid"/"ask"), under the per-trade
        and total caps (the trade `exclude`, if any, is left out of the total), never above `max_qty`."""
        for leg in (long, short):
            if leg["ask"] - leg["bid"] > MAX_QUOTE_SPREAD or leg["bid"] <= 0:
                return None, f"leg {leg['symbol']} quote too wide or empty ({leg['bid']}/{leg['ask']})"
        mid = (short["bid"] + short["ask"]) / 2 - (long["bid"] + long["ask"]) / 2  # >0 credit, <0 debit
        if (mid > 0) != credit:
            return None, f"mid {mid:.2f} has the wrong sign for a {kind} (bad quotes)"
        net = round(abs(mid), 2)
        if net <= 0.05:
            return None, "net price too small to trade"
        structural = (width - net) * 100 if credit else net * 100
        per_contract_gain = net * 100 if credit else (width - net) * 100
        if structural <= 0:
            return None, "bad quotes (no risk?)"
        # Budget the exit too: closing costs about half of each leg's quoted spread (research playbook, section 8).
        exit_cost = ((long["ask"] - long["bid"]) + (short["ask"] - short["bid"])) / 2 * 100
        per_contract_loss = structural + exit_cost
        qty = int(MAX_LOSS_PER_TRADE // per_contract_loss)
        room = MAX_LOSS_TOTAL - self.realized_loss() - sum(t["max_loss"] for t in self.trades
                                                           if t is not exclude and t["status"] in CAP_STATUSES)
        qty = min(qty, int(room // per_contract_loss))
        if max_qty is not None:
            qty = min(qty, max_qty)
        if qty < 1:
            return None, f"one contract risks ${per_contract_loss:.0f}, over the cap or the remaining room"
        return {"qty": qty, "net": net,
                "max_loss": round(per_contract_loss * qty, 2), "structural_max_loss": round(structural * qty, 2),
                "exit_cost_budget": round(exit_cost * qty, 2), "exit_cost_pc": round(exit_cost / 100, 4),
                "max_gain": round(per_contract_gain * qty, 2),
                "long_bid": long["bid"], "long_ask": long["ask"], "short_bid": short["bid"],
                "short_ask": short["ask"]}, "ok"

    @staticmethod
    def _quote_time(q) -> datetime | None:
        ts = getattr(q, "timestamp", None)
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                return None
        return ts if isinstance(ts, datetime) and ts.tzinfo is not None else None

    def refresh_entry_quote(self, t: dict) -> tuple[bool, str]:
        """Right before an open is sent: re-read both legs' latest quotes. (True, how) when the trade may be sent
        (its price possibly re-priced ONCE from the fresh quote, same caps, never a bigger size), (False, why) to
        skip. Everything checked is written to t["entry_quote_check"] for the journal."""
        now = ny_now()
        planned = {k: t.get(k) for k in ("net", "qty", "max_loss", "long_bid", "long_ask", "short_bid", "short_ask",
                                         "long_quote_time", "short_quote_time")}
        chk = t["entry_quote_check"] = {"checked_at": now.isoformat(timespec="seconds"), "planned": planned,
                                        "max_age_sec": ENTRY_QUOTE_MAX_AGE_SEC, "max_move": ENTRY_QUOTE_MAX_MOVE}

        def age(ts) -> float | None:
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts)
                except ValueError:
                    return None
            return None if ts is None else round((now - ts).total_seconds(), 1)

        try:
            q = self.quotes([t["long"], t["short"]])
            fresh = {}
            for leg in ("long", "short"):
                x = q[t[leg]]
                fresh[leg] = {"symbol": t[leg], "bid": float(x.bid_price), "ask": float(x.ask_price),
                              "time": self._quote_time(x)}
        except Exception as e:
            chk["result"] = "skip"
            return False, f"entry quote re-read failed ({_err(e)}): not sent on an unchecked price"
        ages = {leg: age(fresh[leg]["time"]) for leg in fresh}
        chk["fresh"] = {leg: {"bid": f["bid"], "ask": f["ask"],
                              "time": f["time"].isoformat() if f["time"] else None, "age_sec": ages[leg]}
                        for leg, f in fresh.items()}
        stale = [leg for leg, a in ages.items() if a is None or a > ENTRY_QUOTE_MAX_AGE_SEC]
        if stale:
            chk["result"] = "skip"
            return False, (f"fresh {'/'.join(stale)} quote older than {ENTRY_QUOTE_MAX_AGE_SEC}s or undated "
                           f"(ages {ages}): no trade on a stale price")
        lb, la, sb, sa = fresh["long"]["bid"], fresh["long"]["ask"], fresh["short"]["bid"], fresh["short"]["ask"]
        sign = 1 if t["credit"] else -1  # a credit is received (short - long), a debit paid (long - short)
        fresh_mid = round(sign * ((sb + sa) / 2 - (lb + la) / 2), 4)
        fresh_natural = round(sb - la, 2) if t["credit"] else round(la - sb, 2)
        move = round(fresh_mid - t["net"], 4)  # >0: a credit got richer (good) / a debit got dearer (bad)
        against = -move if t["credit"] else move
        planned_ages = {leg: age(t.get(f"{leg}_quote_time")) for leg in ("long", "short")}
        planned_stale = [leg for leg, a in planned_ages.items() if a is None or a > ENTRY_QUOTE_MAX_AGE_SEC]
        chk.update({"fresh_mid": fresh_mid, "fresh_natural": fresh_natural, "move": move, "move_against": against,
                    "planned_age_sec": planned_ages})
        # Re-price on a stale (or undated) planned quote, or on a move of more than max_move either way: a move
        # against us must not be chased by the old limit, and a move for us must not pay the old, worse price.
        why = []
        if planned_stale:
            why.append(f"planned {'/'.join(planned_stale)} quote older than {ENTRY_QUOTE_MAX_AGE_SEC}s or undated")
        if abs(move) > ENTRY_QUOTE_MAX_MOVE + 1e-9:
            why.append(f"fresh mid {fresh_mid:.3f} is {abs(move):.3f} {'against' if against > 0 else 'for'} us "
                       f"from the planned net {t['net']:.2f}")
        bad = [leg for leg, f in fresh.items() if f["bid"] <= 0 or f["ask"] - f["bid"] > MAX_QUOTE_SPREAD + 1e-9]
        if bad:  # the quote filter applies to the fresh quote too: price_spread (below) refuses it
            why.append(f"fresh {'/'.join(bad)} quote too wide or empty")
        if not why:
            chk["result"] = "kept"
            return True, "planned price kept (fresh quote within limits)"
        priced, pwhy = self.price_spread(fresh["long"], fresh["short"], t["credit"], t["width"], t["kind"],
                                         max_qty=t["qty"], exclude=t)
        if priced is None:
            chk.update({"result": "skip", "reprice_why": "; ".join(why)})
            return False, f"re-price from the fresh quote refused ({'; '.join(why)}): {pwhy}"
        t.update(priced)
        t.update({"long_quote_time": chk["fresh"]["long"]["time"], "short_quote_time": chk["fresh"]["short"]["time"],
                  "repriced": True})
        chk.update({"result": "repriced", "reprice_why": "; ".join(why), "new_net": t["net"], "new_qty": t["qty"],
                    "new_max_loss": t["max_loss"]})
        return True, f"re-priced once from the fresh quote ({'; '.join(why)})"

    # --- orders ------------------------------------------------------------------------------------------------
    def _is_paper(self) -> bool:
        return "paper-api" in str(getattr(self.trading._base_url, "value", self.trading._base_url))

    def leg_overlap(self, t: dict) -> list[str]:
        """Symbols of `t` that are also a leg of another live lab trade (either side). Alpaca keeps one net position
        per symbol, so held() / legs_ok() cannot tell two lab trades on the same symbol apart."""
        mine = {t["long"], t["short"]}
        return sorted({s for x in self.trades if x is not t and x.get("status") in CAP_STATUSES
                       for s in (x.get("long"), x.get("short")) if s in mine})

    def check_order(self, t: dict, intent: str) -> list[str]:
        """The lab's own locks, checked right before any two-leg order is sent. No network call: a close must never
        be blocked by an account read."""
        from trader.options.models import is_occ, parse_occ

        out = []
        if not self._is_paper():
            out.append("not a paper account")
        a, b = parse_occ(t["long"]) if is_occ(t["long"]) else None, parse_occ(t["short"]) if is_occ(t["short"]) else None
        if not a or not b:
            return out + ["legs are not option symbols"]
        if a["underlying"] != b["underlying"] or a["expiry"] != b["expiry"] or a["type"] != b["type"]:
            out.append("legs are not one vertical")
        if a["underlying"] not in UNDERLYINGS:
            out.append("underlying not allowed")
        if abs(a["strike"] - b["strike"]) != t["width"]:
            out.append("width mismatch")
        dte = (date.fromisoformat(a["expiry"]) - self.today).days
        if intent == "open":
            if self.mode == "0dte" and dte != 0:
                out.append(f"expiry {dte} days away is not today (0dte mode)")
            if self.mode == "short" and not (MIN_DTE <= dte <= MAX_DTE):
                out.append(f"expiry {dte} days away is outside {MIN_DTE}-{MAX_DTE}")
            if t["max_loss"] > MAX_LOSS_PER_TRADE + 1e-6:
                out.append("over the per-trade cap")
            others = [x for x in self.trades if x is not t]
            if self.realized_loss() + sum(x["max_loss"] for x in others if x["status"] in CAP_STATUSES) \
                    + t["max_loss"] > MAX_LOSS_TOTAL + 1e-6:
                out.append("over the total cap")
            if len([x for x in others if x.get("opened") or x["status"] in CAP_STATUSES]) >= MAX_OPENS:
                out.append("max opens reached")
            if hhmm(ny_now()) > self.tm["last_entry"]:
                out.append("after the last entry time")
            clash = self.leg_overlap(t)
            if clash:
                out.append(f"leg {', '.join(clash)} is already a leg of a live lab trade")
        if not isinstance(t["qty"], int) or t["qty"] < 1:
            out.append("bad quantity")
        return out

    @staticmethod
    def cid(t: dict, intent: str) -> str:
        return f"{PREFIX}{t['id']}-{intent}-{t.get('close_attempts', 0) if intent == 'close' else 0}"

    def order_mismatch(self, o, t: dict) -> str | None:
        """Why an order found by client id is not this trade's two-leg order (None when it matches)."""
        try:
            qty = int(float(o.qty)) if getattr(o, "qty", None) is not None else None
        except (TypeError, ValueError):
            qty = None
        if qty is not None and qty != t["qty"]:
            return f"found order qty {qty} != trade qty {t['qty']}"
        legs = getattr(o, "legs", None)
        if legs:
            syms = {getattr(x, "symbol", None) for x in legs}
            if syms != {t["long"], t["short"]}:
                return f"found order legs {sorted(map(str, syms))} != trade legs {[t['long'], t['short']]}"
        return None

    def send(self, t: dict, intent: str, limit_net: float) -> dict:
        """One multi-leg LIMIT DAY order. Alpaca sign: a negative limit is a net credit, a positive one a debit."""
        from alpaca.trading.enums import OrderClass, OrderSide, PositionIntent, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest

        why = self.check_order(t, intent)
        if why:
            return {"status": "refused", "why": why}
        if intent == "open":
            legs = [(t["long"], OrderSide.BUY, PositionIntent.BUY_TO_OPEN),
                    (t["short"], OrderSide.SELL, PositionIntent.SELL_TO_OPEN)]
            receive = t["credit"]
        else:
            legs = [(t["long"], OrderSide.SELL, PositionIntent.SELL_TO_CLOSE),
                    (t["short"], OrderSide.BUY, PositionIntent.BUY_TO_CLOSE)]
            receive = not t["credit"]
        limit = -abs(limit_net) if receive else abs(limit_net)
        cid = self.cid(t, intent)
        req = LimitOrderRequest(qty=t["qty"], order_class=OrderClass.MLEG, time_in_force=TimeInForce.DAY,
                                limit_price=round(limit, 2), client_order_id=cid, extended_hours=False,
                                legs=[OptionLegRequest(symbol=s, ratio_qty=1, side=sd, position_intent=pi)
                                      for s, sd, pi in legs])
        if self.dry:
            return {"status": "dry-run", "client_order_id": cid, "limit": round(limit, 2)}
        try:
            o = self.trading.submit_order(req)
        except Exception as e:  # it may have reached Alpaca anyway: the fixed client id finds it (and blocks dupes)
            try:
                o = self.trading.get_order_by_client_id(cid)
            except Exception:
                return {"status": "send_failed", "why": _err(e), "client_order_id": cid}
            bad = self.order_mismatch(o, t) if intent == "open" else None
            if bad:  # only possible if trades.json was lost: never adopt another order as this trade
                self.log("ALERT_ID_CONFLICT", id=t["id"], client_order_id=cid, found_id=str(o.id), why=bad,
                         note="an order with this client id exists with other legs/qty: check the account by hand")
                return {"status": "id_conflict", "why": bad, "found_id": str(o.id), "client_order_id": cid}
        return {"status": str(o.status.value), "id": str(o.id), "client_order_id": cid, "limit": round(limit, 2)}

    def order_state(self, order_id: str) -> dict:
        o = self.trading.get_order_by_id(order_id)
        return {"status": str(o.status.value), "filled_qty": float(o.filled_qty or 0),
                "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None}

    def close_limit(self, t: dict, mid: float, natural: float) -> float:
        """Mid plus a growing step per attempt, but never worse than the natural price on those first steps: a close
        that PAYS (buying back a credit spread) bids min(mid + step, natural), a close that RECEIVES (selling a debit
        spread) offers max(mid - step, natural) (day 1 offered 0.74 with the natural at 0.76). From attempt 3 or
        hard_close it goes through the natural price on purpose. Before last_resort a credit close never pays more
        than the width. At last_resort a credit close bids the
        natural price plus LAST_RESORT_OVER_NATURAL, at least the width, and never more than the width plus the
        budgeted exit cost per contract (so the loss stays inside the trade's recorded max_loss); a debit close
        offers 0.01. Neither is a guaranteed fill: the leg-by-leg fallback handles what is still open at close_by."""
        n = t.get("close_attempts", 0)
        step = STEPS[min(n, len(STEPS) - 1)]
        hard = hhmm(ny_now()) >= self.tm["hard_close"] or n >= 3
        last = hhmm(ny_now()) >= self.tm["last_resort"]
        extra = 0.10 * max(1, n - 2)
        if t["credit"]:  # we pay: higher is more aggressive
            if last:
                cap = t["width"] + float(t.get("exit_cost_pc") or 0.0)
                return round(min(cap, max(t["width"], natural + LAST_RESORT_OVER_NATURAL)), 2)
            px = max(mid + step, natural + extra) if hard else min(mid + step, natural)
            return round(min(t["width"], max(0.01, px)), 2)
        px = 0.01 if last else (min(mid - step, natural - extra) if hard else max(mid - step, natural))  # we receive
        return round(max(0.01, px), 2)

    def underlying_price(self, sym: str) -> float | None:
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockLatestTradeRequest

        try:
            return float(self.stocks.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=sym,
                                                                                    feed=DataFeed.IEX))[sym].price)
        except Exception:
            return None

    def quotes(self, syms: list[str]) -> dict:
        from alpaca.data.enums import OptionsFeed
        from alpaca.data.requests import OptionLatestQuoteRequest

        return self.options.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=syms,
                                                                             feed=OptionsFeed.INDICATIVE))

    def spread_mid(self, t: dict) -> tuple[float, float] | None:
        """(mid value of what we hold as a positive, natural price to close it), or None when the quote is
        missing OR the quote call fails: a data error must never block a close."""
        try:
            q = self.quotes([t["long"], t["short"]])
        except Exception as e:
            self.log("quote_error", id=t.get("id"), error=_err(e))
            return None
        try:
            lb, la = float(q[t["long"]].bid_price), float(q[t["long"]].ask_price)
            sb, sa = float(q[t["short"]].bid_price), float(q[t["short"]].ask_price)
        except (KeyError, TypeError):
            return None
        if la <= 0 or sa <= 0:
            return None
        if t["credit"]:
            return round((sb + sa) / 2 - (lb + la) / 2, 2), round(sa - lb, 2)
        return round((lb + la) / 2 - (sb + sa) / 2, 2), round(lb - sa, 2)

    # --- positions and the leg-by-leg fallback ---------------------------------------------------------------
    def held(self, t: dict) -> tuple[int, int] | None:
        """(long contracts held, short contracts held) for this trade's two symbols, read from the account;
        None when the account cannot be read (the caller then carries on with the two-leg close)."""
        if self.dry:
            return None
        try:
            pos = self.trading.get_all_positions()
        except Exception as e:
            self.log("positions_error", id=t.get("id"), error=_err(e))
            return None
        signed = {}
        for p in pos or []:
            if p.symbol in (t["long"], t["short"]):
                n = float(p.qty)
                if str(getattr(p.side, "value", p.side)).lower() == "short" and n > 0:
                    n = -n
                signed[p.symbol] = signed.get(p.symbol, 0.0) + n
        return max(0, int(round(signed.get(t["long"], 0.0)))), max(0, int(round(-signed.get(t["short"], 0.0))))

    def legs_ok(self, t: dict) -> bool:
        """Before a two-leg close: do both legs still sit in the account? False means this pass must not send the
        two-leg close (the trade was switched to legging_out, closed, or the mismatch is waiting for a 2nd read)."""
        h = self.held(t)
        if h is None:  # unreadable: the two-leg close goes out, and the "two reads in a row" count starts over
            t["leg_mismatch_hits"] = 0
            return True
        long_n, short_n = h
        if long_n >= t["qty"] and short_n >= t["qty"]:
            t["leg_mismatch_hits"] = 0
            return True
        # One read can lag a fill: act only when two reads in a row agree.
        t["leg_mismatch_hits"] = t.get("leg_mismatch_hits", 0) + 1
        self.log("legs_mismatch", id=t["id"], expected=t["qty"], long_held=long_n, short_held=short_n,
                 hits=t["leg_mismatch_hits"])
        if t["leg_mismatch_hits"] < 2:
            return False
        L, S = min(long_n, t["qty"]), min(short_n, t["qty"])
        if L == S == 0:
            self.mark_gone(t)
            return False
        if L == S:  # still a matched pair, just fewer: close the rest as a spread
            t["max_loss"] = round(t["max_loss"] * L / t["qty"], 2)
            t.update({"qty": L, "leg_mismatch_hits": 0, "pnl_incomplete": True})
            self.log("ALERT_LEGS_REDUCED", id=t["id"], qty=L, note="some spreads left the account outside the lab")
            return True
        self.start_leg_out(t, f"legs no longer match at the broker (long {L}, short {S}, expected {t['qty']})",
                           (L, S))
        return False

    def mark_gone(self, t: dict) -> None:
        """Neither leg shows in the account. Not closed yet: an empty read may be wrong, so the trade stays LIVE
        ("verify_gone") and positions are re-read every pass; it is closed only by a read at or after close_by."""
        t.update({"status": "verify_gone", "leg_mismatch_hits": 0})
        self.log("ALERT_LEGS_GONE", id=t["id"], note="neither leg shows in the account (liquidated, exercised or "
                 "closed by hand?): positions are re-read every pass until close_by; P&L unknown here, check the "
                 "account activities")

    def start_leg_out(self, t: dict, why: str, held: tuple[int, int] | None = None) -> None:
        """`held`: a read already confirmed by two reads in a row (legs_ok). Without it (close_by, repeated close
        failures) this pass's ONE read may lag or be partial: leg-out starts at the full qty on both legs, and the
        rejected / send-failed paths lower it only when two reads in a row agree (never a naked short). An empty
        read goes to verify_gone (stays LIVE and is re-read)."""
        h = held if held is not None else self.held(t)
        L, S = (min(h[0], t["qty"]), min(h[1], t["qty"])) if h is not None else (t["qty"], t["qty"])
        if h is not None and L == S == 0:
            self.mark_gone(t)
            return
        if held is None and h is not None and (L < t["qty"] or S < t["qty"]):
            self.log("legs_mismatch_one_read", id=t["id"], expected=t["qty"], long_held=h[0], short_held=h[1],
                     note="one read only: leg-out starts at the full qty; lowered only when two reads agree")
            L = S = t["qty"]
            h = None
        t.update({"status": "legging_out", "leg_out_reason": why, "legs_left": {"short": S, "long": L},
                  "leg_qty": t["qty"], "leg_cash": 0.0, "leg_attempts": 0, "leg_order": None,
                  "leg_max_loss": t["max_loss"], "leg_send_fails": 0, "leg_held_last": None,
                  "leg_reject_held": None})
        if h is not None and (L < t["qty"] or S < t["qty"]):
            t["pnl_incomplete"] = True
        self.log("ALERT_LEG_OUT", id=t["id"], why=why, short_left=S, long_left=L, max_loss=t["max_loss"],
                 note="closing leg by leg: short leg bought back first, then the long leg sold; leg prices are "
                      "not capped by max_loss (the closed row reports the realised loss against it)")

    def leg_limit(self, t: dict, leg: str) -> float | None:
        """Single-leg close price: sell the long leg at bid - step (0.01 floor, a marketable sell); buy the short
        leg back at ask + step, or with no quote at intrinsic value + 0.25 + step. None: no price this pass."""
        step = LEG_STEPS[min(t.get("leg_attempts", 0), len(LEG_STEPS) - 1)]
        bid = ask = None
        try:
            q = self.quotes([t[leg]])[t[leg]]
            bid, ask = float(q.bid_price or 0), float(q.ask_price or 0)
        except Exception as e:
            self.log("quote_error", id=t.get("id"), leg=leg, error=_err(e))
        if leg == "long":
            return round(max(0.01, (bid or 0) - step), 2)
        if ask and ask > 0:
            return round(ask + step, 2)
        spot = self.underlying_price(t["underlying"])
        if spot is None:
            return None
        k = t["short_strike"]
        intrinsic = max(0.0, k - spot) if t["type"] == "put" else max(0.0, spot - k)
        return round(intrinsic + 0.25 + step, 2)

    def check_leg(self, t: dict, leg: str, qty: int) -> list[str]:
        """Locks for a single-leg CLOSING order."""
        from trader.options.models import is_occ, parse_occ

        out = []
        if not self._is_paper():
            out.append("not a paper account")
        if leg not in ("long", "short"):
            return out + ["unknown leg"]
        sym = t[leg]
        a = parse_occ(sym) if is_occ(sym) else None
        if not a:
            return out + ["leg is not an option symbol"]
        if a["underlying"] not in UNDERLYINGS:
            out.append("underlying not allowed")
        if not isinstance(qty, int) or qty < 1 or qty > t["legs_left"][leg]:
            out.append("bad quantity")
        if leg == "long" and t["legs_left"]["short"] > 0:
            out.append("the long leg is sold only after the short leg is bought back (never a naked short)")
        return out

    def send_leg(self, t: dict, leg: str, qty: int, limit: float) -> dict:
        """One single-leg closing LIMIT DAY order: buy_to_close the short leg or sell_to_close the long leg."""
        from alpaca.trading.enums import OrderSide, PositionIntent, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest

        why = self.check_leg(t, leg, qty)
        if why:
            return {"status": "refused", "why": why}
        cid = f"{PREFIX}{t['id']}-leg{leg}-{t.get('leg_attempts', 0)}"
        side, intent = ((OrderSide.BUY, PositionIntent.BUY_TO_CLOSE) if leg == "short"
                        else (OrderSide.SELL, PositionIntent.SELL_TO_CLOSE))
        req = LimitOrderRequest(symbol=t[leg], qty=qty, side=side, time_in_force=TimeInForce.DAY,
                                limit_price=round(limit, 2), client_order_id=cid, position_intent=intent,
                                extended_hours=False)
        if self.dry:
            return {"status": "dry-run", "client_order_id": cid, "limit": round(limit, 2)}
        try:
            o = self.trading.submit_order(req)
        except Exception as e:
            try:
                o = self.trading.get_order_by_client_id(cid)
            except Exception as e2:
                # not_created: Alpaca ANSWERED the submit with a 4xx and has no order under this client id, so no
                # order exists and the next try may use a new client id. Otherwise (timeout, 5xx, lookup down) the
                # order may exist: the next try reuses this client id so Alpaca refuses a duplicate.
                sc = getattr(e, "status_code", None)
                absent = getattr(e2, "status_code", None) == 404 or "not found" in str(e2).lower()
                return {"status": "send_failed", "why": _err(e), "client_order_id": cid,
                        "not_created": isinstance(sc, int) and 400 <= sc < 500 and absent}
        return {"status": str(o.status.value), "id": str(o.id), "client_order_id": cid, "limit": round(limit, 2)}

    # --- the loop ------------------------------------------------------------------------------------------------
    def try_entry(self, checkpoint: str) -> None:
        self.done_checkpoints.add(checkpoint)
        now = hhmm(ny_now())
        if now > self.tm["last_entry"]:
            self.log("no_trade", checkpoint=checkpoint, why=f"after the last entry time {self.tm['last_entry']}")
            return
        if self.mode == "0dte" and self.check_full_day() is not True:
            self.log("no_trade", checkpoint=checkpoint,
                     why="0dte needs a full 16:00 session (half-day cutoffs unverified) or the calendar was unreadable")
            return
        for sym in UNDERLYINGS:
            kind, info = self.signal(sym)
            self.log("signal", checkpoint=checkpoint, underlying=sym, kind=kind, **info)
            if not kind:
                continue
            t, why = self.build(sym, kind, info["spot"])
            if t is None:
                self.log("no_trade", checkpoint=checkpoint, underlying=sym, kind=kind, why=why)
                continue
            ok, how = self.refresh_entry_quote(t)  # the chain quote can be a minute old (day 1): re-read it
            self.log("entry_quote_check", checkpoint=checkpoint, underlying=sym, kind=kind, ok=ok, how=how,
                     **t["entry_quote_check"])
            if not ok:
                self.log("no_trade", checkpoint=checkpoint, underlying=sym, kind=kind, why=how)
                continue
            tag ="Z" if self.mode == "0dte" else ""  # 0dte ids never collide with short-mode ids on the same day
            t.update({"id": f"{self.today:%m%d}{tag}{len(self.trades) + 1}", "checkpoint": checkpoint,
                      "status": "pending_open", "signal": info, "sent_at": time.time()})
            t["open_order"] = {"status": "sending", "client_order_id": self.cid(t, "open")}
            # Write-ahead: the trade (legs, qty, id) is on disk before any order can reach Alpaca, so a restart
            # finds it by id instead of rebuilding the checkpoint under the same client id.
            self.trades.append(t)
            self.save()
            try:
                r = self.send(t, "open", t["net"])
            except Exception as e:  # unknown whether it reached Alpaca: resolved by client id on the next passes
                r = {"status": "send_failed", "why": _err(e), "client_order_id": t["open_order"]["client_order_id"]}
            t["open_order"], t["sent_at"] = r, time.time()
            if "id" in r:
                t["opened"] = True
            elif r["status"] == "send_failed":
                # Unknown, not failed: it stays live (counted in the caps) until found or confirmed absent.
                t["opened"] = True
                self.log("ALERT_OPEN_UNKNOWN", id=t["id"], client_order_id=r["client_order_id"], why=r.get("why"))
            else:  # refused / dry-run / id_conflict
                t["status"] = r["status"]
            self.log("entry", id=t["id"], order_status=r["status"], underlying=sym, kind=kind, expiry=t["expiry"],
                     net=t["net"], long=[t["long"], t["long_bid"], t["long_ask"]],
                     short=[t["short"], t["short_bid"], t["short_ask"]], underlying_price=t["underlying_price"],
                     minutes_to_broker_cutoff=t["minutes_to_broker_cutoff"],
                     minutes_to_planning_cutoff=t["minutes_to_planning_cutoff"],
                     minutes_to_close_by=t["minutes_to_close_by"], qty=t["qty"], max_loss=t["max_loss"],
                     short_delta=t.get("short_delta"), long_delta=t.get("long_delta"),
                     delta_source=t.get("delta_source"), short_delta_source=t.get("short_delta_source"),
                     long_delta_source=t.get("long_delta_source"), quote_feed=QUOTE_FEED,
                     long_quote_time=t.get("long_quote_time"), short_quote_time=t.get("short_quote_time"),
                     quote_check=t["entry_quote_check"].get("result"), repriced=bool(t.get("repriced")),
                     planned_net=t["entry_quote_check"]["planned"]["net"])
            self.log("open_order", trade=t)
            self.save()
            break  # at most one new trade per checkpoint

    def _cancel(self, order_id: str) -> None:
        try:
            self.trading.cancel_order_by_id(order_id)
        except Exception as e:  # already filled / cancelled / pending_cancel: the next status read settles it
            self.log("cancel_failed", order_id=order_id, error=str(e)[:200])

    def manage(self) -> None:
        for t in self.trades:
            try:
                self._manage_one(t)
            except Exception as e:  # one trade's failure must never stop the other trades' exits
                self.log("error", id=t.get("id"), error=_err(e))
        self.save()

    def _find_open(self, t: dict) -> None:
        """An opening order whose send result was lost: look it up by its client id until found or absent."""
        cid = t["open_order"]["client_order_id"]
        try:
            o = self.trading.get_order_by_client_id(cid)
        except Exception as e:
            absent = getattr(e, "status_code", None) == 404 or "not found" in str(e).lower()
            if absent and time.time() - t.get("sent_at", 0) >= OPEN_LOOKUP_GRACE_SEC:
                t.update({"status": "send_failed", "opened": False})
                self.log("open_confirmed_absent", id=t["id"], client_order_id=cid)
            else:
                self.log("open_lookup_failed", id=t["id"], client_order_id=cid, error=_err(e))
            return
        bad = self.order_mismatch(o, t)
        if bad:
            t.update({"status": "id_conflict", "open_order": {**t["open_order"], "found_id": str(o.id), "why": bad}})
            self.log("ALERT_ID_CONFLICT", id=t["id"], client_order_id=cid, found_id=str(o.id), why=bad,
                     note="an order with this client id exists with other legs/qty: check the account by hand")
            return
        t["open_order"] = {**t["open_order"], "status": str(o.status.value), "id": str(o.id)}
        t["opened"] = True
        self.log("open_order_found", id=t["id"], order_id=str(o.id), status=t["open_order"]["status"])

    def _manage_one(self, t: dict) -> None:
        now = hhmm(ny_now())
        if t["status"] == "pending_open":
            if "id" not in t["open_order"]:
                self._find_open(t)
                return
            st = self.order_state(t["open_order"]["id"])
            ttl = OPEN_TTL_SEC.get(self.mode)
            if st["status"] in TERMINAL:
                filled = int(st["filled_qty"])
                if filled > 0:  # filled, or partly filled then cancelled: we hold `filled` spreads
                    t.update({"status": "open", "max_loss": round(t["max_loss"] * filled / t["qty"], 2),
                              "qty": filled, "entry_qty": filled,
                              "entry_net": abs(st["filled_avg_price"] or t["net"])})
                    # The trade's size as filled. qty / max_loss count down as spreads are closed (and are 0 once
                    # closed); these are set once here and never changed, so trades.json keeps the original size.
                    for k, v in (("orig_qty", t["qty"]), ("orig_max_loss", t["max_loss"]),
                                 ("orig_net", t["entry_net"])):
                        t.setdefault(k, v)
                    self.log("filled_open", id=t["id"], qty=filled, entry_net=t["entry_net"], order=st["status"],
                             orig_qty=t["orig_qty"], orig_max_loss=t["orig_max_loss"], orig_net=t["orig_net"])
                else:
                    t["status"] = "not_filled"
                    self.log("open_not_filled", id=t["id"], status=st["status"])
            elif now >= self.tm["open_cancel"] or (ttl and time.time() - t.get("sent_at", 0) >= ttl):
                # settles on a later pass; an open is never re-sent. A partial fill is then managed as a trade.
                self._cancel(t["open_order"]["id"])
        elif t["status"] == "open":
            q = self.spread_mid(t)
            if q is None:
                if now >= self.tm["last_resort"]:  # the last-resort price ignores the quote: never wait for one
                    v = t.get("last_value", t["entry_net"])
                    q = (v, v)
                elif now < self.tm["hard_close"] or "last_value" not in t:
                    return
                else:
                    q = (t["last_value"], t["last_value"])
            value, natural = q
            entry = t["entry_net"]
            pnl = (entry - value) if t["credit"] else (value - entry)
            max_gain = entry if t["credit"] else t["width"] - entry
            max_loss = t["width"] - entry if t["credit"] else entry
            reason = t.get("exit_reason")  # once an exit is decided it is never undecided
            if reason is None:
                spot = self.underlying_price(t["underlying"])
                crossed = spot is not None and t["credit"] and (
                    spot < t["short_strike"] if t["type"] == "put" else spot > t["short_strike"])
                value_stop = -pnl >= (BACKSTOP if t["credit"] else STOP) * max_loss
                # A stop must show on two checks in a row, so one bad quote cannot close a trade.
                t["stop_hits"] = t.get("stop_hits", 0) + 1 if (crossed or value_stop) else 0
                if pnl >= TAKE_PROFIT * max_gain:
                    reason = "take profit (50% of max gain)"
                elif t["stop_hits"] >= 2:
                    reason = (f"stop: {t['underlying']} {spot:.2f} crossed the short strike {t['short_strike']}"
                              if crossed else f"stop ({int((BACKSTOP if t['credit'] else STOP) * 100)}% of max loss)")
                elif now >= self.tm["time_exit"]:
                    reason = ("time exit before the 0DTE cutoff" if self.mode == "0dte"
                              else "time exit before the close")
            t["last_value"], t["last_pnl"] = value, round(pnl * 100 * t["qty"], 2)
            if reason:
                t["exit_reason"] = reason
                fails = t.get("close_rejects", 0) + t.get("close_send_fails", 0)
                if now >= self.tm["close_by"]:
                    self.start_leg_out(t, f"two-leg close still open at close_by {self.tm['close_by']}")
                    return
                if fails >= CLOSE_FAILS_TO_LEG_OUT:
                    self.start_leg_out(t, f"two-leg close rejected or not accepted {fails} times")
                    return
                if not self.legs_ok(t):  # the account no longer holds both legs (or the read must be repeated)
                    return
                limit = self.close_limit(t, value, natural)
                r = self.send(t, "close", limit)
                t.update({"close_order": r, "close_sent": time.time()})
                if "id" in r:
                    t["status"] = "pending_close"
                elif r["status"] in ("send_failed", "refused"):
                    t["close_send_fails"] = t.get("close_send_fails", 0) + 1
                self.log("close_order", id=t["id"], reason=reason, value=value, natural=natural, limit=limit,
                         attempt=t.get("close_attempts", 0), result=r)
        elif t["status"] == "pending_close":
            st = self.order_state(t["close_order"]["id"])
            if st["status"] in TERMINAL:
                done = int(st["filled_qty"])
                if done > 0:
                    exit_net = abs(st["filled_avg_price"] or 0)
                    per = (t["entry_net"] - exit_net) if t["credit"] else (exit_net - t["entry_net"])
                    t["pnl"] = round(t.get("pnl", 0.0) + per * 100 * done, 2)
                    t["max_loss"] = round(t["max_loss"] * (t["qty"] - done) / t["qty"], 2)
                    t["qty"] -= done
                elif st["status"] == "rejected":
                    t["close_rejects"] = t.get("close_rejects", 0) + 1
                t["close_attempts"] = t.get("close_attempts", 0) + 1  # next cid and a bigger step
                if t["qty"] <= 0:
                    t["status"] = "closed"
                    self.log("closed", id=t["id"], pnl=t["pnl"], reason=t.get("exit_reason"),
                             orig_qty=t.get("orig_qty"), orig_max_loss=t.get("orig_max_loss"))
                else:
                    t["status"] = "open"  # re-priced on the next pass, only now that the old order is dead
                    self.log("close_not_filled", id=t["id"], status=st["status"], left=t["qty"])
            elif time.time() - t.get("close_sent", 0) >= (30 if now >= self.tm["hard_close"] else REPRICE_SEC):
                self._cancel(t["close_order"]["id"])
        elif t["status"] == "legging_out":
            self._leg_out_step(t)
        elif t["status"] == "verify_gone":
            h = self.held(t)
            if h is None:  # unreadable: keep checking (the trade stays LIVE, so the run loop does not exit)
                return
            if h[0] > 0 or h[1] > 0:  # the legs are back: an earlier empty read was wrong, manage it again
                t.update({"status": "open", "leg_mismatch_hits": 0})
                self.log("ALERT_LEGS_BACK", id=t["id"], long_held=h[0], short_held=h[1],
                         note="positions show this trade's legs again: managed as an open trade")
            elif now >= self.tm["close_by"]:
                t.update({"status": "closed", "qty": 0, "max_loss": 0.0, "pnl_incomplete": True})
                self.log("ALERT_LEGS_GONE_CONFIRMED", id=t["id"], orig_qty=t.get("orig_qty"),
                         orig_max_loss=t.get("orig_max_loss"), note="neither leg in the account at close_by: "
                         "closed with P&L unknown here, check the account activities")

    def _leg_out_step(self, t: dict) -> None:
        left, lo = t["legs_left"], t.get("leg_order")
        if lo and "id" in lo:
            st = self.order_state(lo["id"])
            if st["status"] in TERMINAL:
                done = int(st["filled_qty"])
                if done > 0:
                    left[lo["leg"]] -= done
                    px = float(st["filled_avg_price"] or 0)
                    t["leg_cash"] = round(t["leg_cash"] + px * 100 * done * (1 if lo["leg"] == "long" else -1), 2)
                t["leg_attempts"] = t.get("leg_attempts", 0) + 1
                t["leg_order"] = None
                if st["status"] == "rejected":  # maybe we asked to close more than the account holds: re-read,
                    # and lower legs_left only when TWO rejects in a row both read less (like _leg_send_failed)
                    self._two_read_clamp(t, "leg_reject_held")
                else:
                    t["leg_reject_held"] = None
                self.log("leg_fill" if done else "leg_not_filled", id=t["id"], leg=lo["leg"], filled=done,
                         status=st["status"], left=dict(left))
            elif time.time() - t.get("leg_sent", 0) >= LEG_REPRICE_SEC:
                self._cancel(lo["id"])
            return
        leg = "short" if left["short"] > 0 else ("long" if left["long"] > 0 else None)
        if leg is None:
            q = t["leg_qty"]
            opened_cash = (t["entry_net"] if t["credit"] else -t["entry_net"]) * 100 * q
            leg_pnl = round(opened_cash + t["leg_cash"], 2)
            t["pnl"] = round(t.get("pnl", 0.0) + leg_pnl, 2)
            cap = t.get("leg_max_loss", t["max_loss"])
            over = -leg_pnl > cap + 1e-6
            t.update({"status": "closed", "qty": 0, "max_loss": 0.0, "leg_out_pnl": leg_pnl,
                      "leg_out_over_max_loss": over})
            self.log("closed", id=t["id"], pnl=t["pnl"], reason=t.get("exit_reason"), legged_out=True,
                     leg_out_pnl=leg_pnl, max_loss=cap, over_max_loss=over, orig_qty=t.get("orig_qty"),
                     orig_max_loss=t.get("orig_max_loss"),
                     pnl_incomplete=bool(t.get("pnl_incomplete")))
            if over:
                self.log("ALERT_LEG_OUT_OVER_MAX_LOSS", id=t["id"], leg_out_pnl=leg_pnl, max_loss=cap,
                         pnl_incomplete=bool(t.get("pnl_incomplete")),
                         note="the leg-by-leg fallback is not price-capped: this trade lost more than its max_loss")
            return
        limit = self.leg_limit(t, leg)
        if limit is None:
            self.log("leg_no_price", id=t["id"], leg=leg, why="no quote and no underlying price: retry next pass")
            return
        r = self.send_leg(t, leg, left[leg], limit)
        t["leg_order"], t["leg_sent"] = {**r, "leg": leg}, time.time()
        self.log("leg_order", id=t["id"], leg=leg, qty=left[leg], limit=limit, result=r)
        if "id" in r or r["status"] == "dry-run":
            t["leg_send_fails"], t["leg_held_last"] = 0, None
        else:
            self._leg_send_failed(t, leg, r)

    def _clamp_legs(self, t: dict, h: tuple[int, int]) -> bool:
        """Lower legs_left to what the account holds (never raise it). True when something was lowered."""
        left = t["legs_left"]
        if h[0] < left["long"] or h[1] < left["short"]:
            left["long"], left["short"] = min(left["long"], h[0]), min(left["short"], h[1])
            t["pnl_incomplete"] = True
            self.log("legs_clamped", id=t["id"], long_held=h[0], short_held=h[1], left=dict(left))
            return True
        return False

    def _two_read_clamp(self, t: dict, key: str) -> None:
        """Re-read positions; lower legs_left only by what TWO reads in a row (this one and t[key]) both show
        (their max), so one lagging or partial read never lets the long be sold while the short is held. When
        both legs would drop to 0 the trade is not closed but goes to verify_gone (stays LIVE, re-read)."""
        h = self.held(t)
        prev = t.get(key)
        t[key] = list(h) if h is not None else None
        if h is None or prev is None:
            return
        m = (max(h[0], prev[0]), max(h[1], prev[1]))
        left = t["legs_left"]
        if (left["long"] or left["short"]) and min(left["long"], m[0]) == 0 and min(left["short"], m[1]) == 0:
            t.update({"pnl_incomplete": True, "leg_order": None})
            self.mark_gone(t)
            return
        self._clamp_legs(t, m)

    def _leg_send_failed(self, t: dict, leg: str, r: dict) -> None:
        """A single-leg close that Alpaca did not accept (send_failed / refused). Re-sending the same order forever
        cannot help when legs_left overstates the account, so: re-read positions from the 2nd failure in a row and
        lower legs_left when TWO reads in a row both show less (one empty read must never let the long be sold
        while the short is still held); a new client id / bigger step only when no order can exist."""
        n = t["leg_send_fails"] = t.get("leg_send_fails", 0) + 1
        if r["status"] == "refused" or r.get("not_created"):
            t["leg_attempts"] = t.get("leg_attempts", 0) + 1
        if n >= 2:
            self._two_read_clamp(t, "leg_held_last")
        if n >= LEG_FAILS_ALERT and n % 2 == 0:
            self.log("ALERT_LEG_STUCK", id=t["id"], leg=leg, fails=n, left=dict(t["legs_left"]),
                     positions_read=t.get("leg_held_last"), last=r.get("why"),
                     note="single-leg close not accepted repeatedly: check the account by hand")

    def other_mode_live(self) -> list[str]:
        """Live trades in the OTHER mode's folder for today (a restart in the wrong mode would not manage them)."""
        other = "short" if self.mode == "0dte" else "0dte"
        p = lab_dir(self.state_dir, self.today, other, self.dry) / "trades.json"
        try:
            return [t.get("id") for t in json.loads(p.read_text()) if t.get("status") in LIVE] if p.exists() else []
        except Exception:
            return []

    def run(self) -> None:
        self.log("start", dry=self.dry, expiry_mode=self.mode, timing=self.tm, quote_feed=QUOTE_FEED,
                 broker_0dte_cutoff=BROKER_0DTE_CUTOFF if self.mode == "0dte" else None,
                 planning_cutoff=PLANNING_CUTOFF if self.mode == "0dte" else None,
                 caps={"per_trade": MAX_LOSS_PER_TRADE, "total": MAX_LOSS_TOTAL, "opens": MAX_OPENS},
                 computed_delta={"r": RISK_FREE_RATE, "q": DIVIDEND_YIELD, "iv_bounds": list(IV_BOUNDS),
                                 "min_extrinsic": MIN_EXTRINSIC, "min_t_years": MIN_T_YEARS,
                                 "used_when": "the snapshot has no greeks; Alpaca's delta is preferred"})
        stray = self.other_mode_live()
        if stray:
            other = "short" if self.mode == "0dte" else "0dte"
            self.log("ALERT_OTHER_MODE_LIVE", ids=stray, other_mode=other,
                     note=f"today's {other}-mode trades are still live and this {self.mode} run does not manage "
                          f"them: restart with --expiry {other} or close them by hand")
        while True:
            now = hhmm(ny_now())
            if now >= "16:00":
                break
            try:
                for cp in self.tm["entry_times"]:
                    if now >= cp and cp not in self.done_checkpoints and now <= self.tm["last_entry"]:
                        self.try_entry(cp)
            except Exception as e:  # an entry failure must never skip this pass's exits
                self.log("error", where="entry", error=_err(e))
            self.manage()
            live = [t["id"] for t in self.trades if t["status"] in LIVE]
            if not live and now > self.tm["close_by"]:
                break
            if live and self.mode == "0dte" and now > self.tm["close_by"] and not self.cutoff_alerted:
                self.cutoff_alerted = True
                cut = ", ".join(f"{s} {c}" for s, c in BROKER_0DTE_CUTOFF.items())
                self.log("ALERT_OPEN_PAST_CLOSE_BY", ids=live,
                         note=f"still open at {now} (target flat by {self.tm['close_by']}): Alpaca may sell out ITM "
                              f"legs from {BROKER_0DTE_SELLOUT}, rejects orders from {cut}, and auto-liquidates "
                              f"expiring SPY/QQQ positions at {BROKER_0DTE_LIQUIDATION}; an ITM short leg left open "
                              "can be assigned into shares. The lab keeps closing leg by leg; check the account now.")
            time.sleep(30)
        closed = [t for t in self.trades if t["status"] == "closed"]
        left = [t["id"] for t in self.trades if t["status"] in LIVE]
        if left:
            self.log("ALERT_STILL_OPEN", ids=left, note="close these by hand before 16:00 / check the account")
        self.log("summary", trades=len(self.trades), closed=len(closed),
                 pnl=round(sum(t.get("pnl", 0.0) for t in self.trades), 2), still_open=left)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    state = Path(os.environ.get("TRADER_STATE_DIR", Path(__file__).resolve().parent.parent / "state"))
    args, mode = sys.argv[1:], EXPIRY_MODE
    for i, a in enumerate(args):
        if a.startswith("--expiry="):
            mode = a.split("=", 1)[1]
        elif a == "--expiry":
            mode = args[i + 1] if i + 1 < len(args) else ""
    if mode not in TIMING:
        sys.exit(f"--expiry must be one of {sorted(TIMING)}, not {mode!r}")
    Lab(state, dry="--dry" in args, mode=mode).run()
