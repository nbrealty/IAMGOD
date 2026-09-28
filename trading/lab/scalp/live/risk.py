"""The pre-trade gate for NEW entries (MT-G2, G14, G15, G17, G18, G19, G20, G22, G23, G25, G26, G27, G35, G41,
and the enforcement point of MT-G10). Pure: everything it needs is in one frozen EntryContext.

`entry_reasons(ec)` returns EVERY failing reason, not just the first, so the journal shows the full picture of
each rejected candidate (ChatGPT spec section 8). An empty list means the entry is allowed. EXIT and PROTECT
orders never go through this module (MT-G38): stale data, caps, cooldowns and loss limits only ever block new
risk, never the way out.

Money conventions: every loss limit uses HONEST P&L (MT-G4). `counters.realized_honest` is today's closed trades,
`counters.week_honest` and `counters.test_honest` include today's closed trades too; `ec.unrealized_honest` is
the open position marked at the bid minus honest slippage and fees, and is added to all three.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from . import config as C
from .clock import SessionTimes, clock_reasons
from .model import Bar, Candidate, DayCounters, LastTrade, Lane, Quote, Reason, SlotState, as_ny

BUSY_SLOTS = frozenset({SlotState.ARMED, SlotState.ENTRY_PENDING, SlotState.PARTIALLY_FILLED, SlotState.OPEN,
                        SlotState.EXIT_PENDING})
_EPS = 1e-9


@dataclass(frozen=True)
class EntryContext:
    now: pd.Timestamp
    candidate: Candidate
    reg: Any                                  # config.Registration | None
    counters: DayCounters
    session: SessionTimes
    events: Any                               # events.DayEvents
    quote: Quote | None
    last_trade: LastTrade | None
    recent_bars: list[Bar]                    # today's completed bars for the candidate's symbol, oldest first
    last_data_ok: pd.Timestamp | None
    clock_offset_ms: float | None
    halted: bool | None                       # None = status unavailable on this feed (a note, not a rejection)
    prior_close: float | None                 # the candidate symbol's previous regular-session close
    slot_state: SlotState
    open_parents: int
    open_position: bool
    flags: frozenset[Reason] | set[Reason] = frozenset()
    unrealized_honest: float = 0.0
    settled_cash: float = 0.0
    broker_nonmarginable_bp: float = 0.0
    gross_notional_open: float = 0.0
    planned_notional: float = 0.0
    open_symbol: str | None = None            # symbol of the open position, if any (MT-G17 NO_ADD)
    spy_price: float | None = None            # for the market-wide circuit breaker when the candidate is QQQ
    spy_prior_close: float | None = None


def daily_limit(e0: float) -> float:
    """MT-G18 + paper caps: the smallest of $25, 0.5% x E0 and 1% x E0 (dollars, positive)."""
    return min(C.DAILY_STOP_USD, *(p * e0 for p in C.DAILY_STOP_PCTS))


def settled_cash(counters: DayCounters) -> float:
    """MT-G15: cash at the previous close minus today's buys; today's sale proceeds are NOT added back (T+1)."""
    if counters.cash_prev_close is None:
        return 0.0
    return counters.cash_prev_close - counters.buy_notional


def _m(x: float) -> pd.Timedelta:
    return pd.Timedelta(minutes=x)


def _s(x: float) -> pd.Timedelta:
    return pd.Timedelta(seconds=x)


def wild_until(bars: list[Bar]) -> pd.Timestamp | None:
    """End of the latest MT-G22 wild-minute pause from today's bars: a bar whose high-low range exceeds 1% of its
    open pauses entries until 10 minutes after that bar ended."""
    out = None
    for b in bars:
        if b.open > 0 and (b.high - b.low) / b.open > C.WILD_MINUTE_RANGE + _EPS:
            t = as_ny(b.start) + _m(1) + _m(C.WILD_MINUTE_PAUSE_MIN)
            out = t if out is None or t > out else out
    return out


def entry_check(ec: EntryContext) -> tuple[list[Reason], dict[str, Any]]:
    """(every failing reason, notes). Notes carry facts that are not rejections (halt status unavailable...)."""
    cand, cnt, now = ec.candidate, ec.counters, as_ny(ec.now)
    if cand.action != "enter":
        raise ValueError("risk.entry_reasons is for entries only; exits are never gated (MT-G38)")
    r: list[Reason] = []
    notes: dict[str, Any] = {}

    def add(x: Reason) -> None:
        if x not in r:
            r.append(x)

    # instrument and registration (MT-G23, G10, G24, lanes)
    if cand.symbol not in C.ALLOWED_SYMBOLS:
        add(Reason.SYMBOL_NOT_ALLOWED)
    if cand.symbol in cnt.blocked_symbols:
        add(Reason.SYMBOL_BLOCKED_BROKER_REJECT)
    reg = ec.reg
    if reg is None or reg.setup_id != cand.setup_id or reg.symbol != cand.symbol or reg.version != cand.version:
        add(Reason.SETUP_NOT_REGISTERED)
        reg = None
    elif reg.lane is Lane.SHADOW:
        add(Reason.LANE_SHADOW)
    elif reg.lane is Lane.RETIRED:
        add(Reason.LANE_RETIRED)
    elif reg.lane is not Lane.EXPLORATORY:
        add(Reason.SETUP_NOT_REGISTERED)       # VALIDATED cannot exist in v1 (config refuses it)
    if cand.side == 0:
        raise ValueError("an entry candidate needs a side")
    if cand.side < 0:
        add(Reason.SHORT_DISABLED)             # v1 has no short path at all (SHORTS_ENABLED is False)

    # bot-wide flags (KILLED, HALTED_MANUAL, SELFTEST_FAILED, DEPLOY_IN_MARKET_HOURS, RISK_HASH_MISMATCH,
    # RECONCILE_MISMATCH, CODE_HASH_MISMATCH ... whatever applies now), each its own reason
    for f in sorted(ec.flags, key=lambda x: x.value):
        add(Reason(f))

    # clock (MT-G20)
    for x in clock_reasons(now, ec.session, reg, ec.events):
        add(x)

    # caps (MT-G2, G17, G25)
    if cnt.round_trips >= C.MAX_ROUND_TRIPS_DAY:
        add(Reason.MAX_TRADES_DAY)
    if cnt.round_trips_by_setup.get(cand.setup_id, 0) >= C.MAX_ROUND_TRIPS_SETUP:
        add(Reason.MAX_TRADES_SETUP)
    if ec.open_position or ec.slot_state in BUSY_SLOTS:
        add(Reason.POSITION_OPEN)
    if ec.open_symbol is not None and ec.open_symbol == cand.symbol:
        add(Reason.NO_ADD)
    if ec.slot_state is SlotState.DISABLED and not (ec.flags or cnt.daily_stopped):
        add(Reason.HALTED_MANUAL)              # a disabled slot always blocks, even if its cause was not passed
    if ec.open_parents >= C.MAX_OPEN_PARENTS:
        add(Reason.OPEN_PARENT)
    if cnt.entry_submits >= C.MAX_ENTRY_SUBMITS_DAY:
        add(Reason.MAX_ENTRY_SUBMITS_DAY)
    recent = [t for t in cnt.entry_submit_times if now - _s(60) < as_ny(t) <= now]
    if len(recent) >= C.MAX_ENTRY_SUBMITS_PER_MIN:
        add(Reason.ENTRY_RATE_MINUTE)
    # the entry commits to a round trip: both sides count toward today's notional cap
    if cnt.notional_traded + 2.0 * ec.planned_notional > C.MAX_NOTIONAL_DAY_X_E0 * cnt.e0 + _EPS:
        add(Reason.NOTIONAL_DAY)

    # cooldowns (MT-G17, G19, G22)
    until = cnt.stopout_until.get((cand.setup_id, cand.symbol))
    if until is not None and now < as_ny(until):
        add(Reason.STOPOUT_COOLDOWN)
    if cnt.loss_pause_until is not None and now < as_ny(cnt.loss_pause_until):
        add(Reason.LOSS_STREAK_COOLDOWN)
    wild = [t for t in (cnt.wild_pause_until.get(cand.symbol), wild_until(ec.recent_bars)) if t is not None]
    if any(now < as_ny(t) for t in wild):
        add(Reason.WILD_MINUTE_PAUSE)

    # loss limits (MT-G18, whole-test stop), honest P&L
    e0 = cnt.e0
    if cnt.daily_stopped or cnt.realized_honest + ec.unrealized_honest <= -daily_limit(e0) + _EPS:
        add(Reason.DAILY_STOP)
    week_base = cnt.week_e0 if cnt.week_e0 else e0
    if cnt.week_honest + ec.unrealized_honest <= -C.WEEKLY_STOP_PCT * week_base + _EPS:
        add(Reason.WEEKLY_STOP)
    test_now = cnt.test_honest + ec.unrealized_honest
    if max(cnt.test_peak, 0.0) - test_now >= C.DRAWDOWN_HALT_PCT * e0 - _EPS:
        add(Reason.DRAWDOWN_HALT)
    if test_now <= -C.TEST_STOP_USD + _EPS or cnt.test_sessions >= C.TEST_MAX_SESSIONS:
        add(Reason.TEST_STOP)

    # data (MT-G22, G35)
    if ec.last_data_ok is None or now - as_ny(ec.last_data_ok) > _s(C.DATA_SILENCE_S):
        add(Reason.DATA_STALE)
    q, lt = ec.quote, ec.last_trade
    if q is None or not q.valid:
        add(Reason.NO_QUOTE)
        q = None
    else:
        if now - as_ny(q.ts) > _s(C.QUOTE_MAX_AGE_S):
            add(Reason.QUOTE_STALE)
        if lt is not None and as_ny(lt.ts) - as_ny(q.ts) > _s(C.QUOTE_MAX_AGE_S):
            add(Reason.QUOTE_STALE)           # the quote is older than the last trade by more than 2 s
        spread = round(q.spread, 6)
        bps = spread / q.mid * 1e4 if q.mid > 0 else float("inf")
        notes.update(spread=spread, spread_bps=round(bps, 3), quote_feed=q.feed.value)
        if spread > C.MAX_SPREAD_USD + _EPS or bps > C.MAX_SPREAD_BPS + _EPS:
            add(Reason.SPREAD_TOO_WIDE)
    if not ec.recent_bars or now - (as_ny(ec.recent_bars[-1].start) + _m(1)) > _s(C.BAR_MAX_AGE_S):
        add(Reason.BAR_STALE)
    if ec.clock_offset_ms is None:
        add(Reason.CLOCK_UNVERIFIED)
    elif ec.clock_offset_ms > C.CLOCK_OFFSET_MS:
        add(Reason.CLOCK_OFFSET)
    if lt is None or not lt.price > 0:
        add(Reason.INPUT_GAP)                  # no last trade to check the decision price against
    elif q is not None and abs(q.ask / lt.price - 1.0) > C.MAX_PRICE_VS_LAST_TRADE + _EPS:
        add(Reason.PRICE_AWAY_FROM_LAST_TRADE)
    if q is not None and ec.recent_bars:
        ref = sum(b.close for b in ec.recent_bars[-5:]) / len(ec.recent_bars[-5:])
        if ref > 0 and abs(q.ask / ref - 1.0) > C.LULD_PCT + _EPS:
            add(Reason.LULD_BAND)
    if ec.halted is True:
        add(Reason.HALTED)
    elif ec.halted is None:
        notes["halt_status"] = "unavailable"
    # market-wide circuit breaker: SPY down 7% from its prior close (fail closed without a prior close)
    spy_px, spy_pc = ec.spy_price, ec.spy_prior_close
    if cand.symbol == "SPY":
        spy_px = spy_px if spy_px is not None else (lt.price if lt is not None else None)
        spy_pc = spy_pc if spy_pc is not None else ec.prior_close
    if ec.prior_close is None or not ec.prior_close > 0:
        add(Reason.INSUFFICIENT_HISTORY)
    if spy_px is not None and spy_pc and spy_px <= spy_pc * (1.0 - C.MWCB_DROP) + _EPS:
        add(Reason.HALTED)
        notes["mwcb"] = True
    if spy_px is None or not spy_pc:
        notes["mwcb_check"] = "unavailable"
        if cand.symbol != "SPY":
            add(Reason.INPUT_GAP)              # fail closed: no SPY inputs, no circuit-breaker check (a SPY entry
                                               # already fails on its own last trade / prior close above)

    # money (MT-G14, G15)
    if cand.side > 0 and not ec.planned_notional > 0:
        add(Reason.SIZE_ZERO)                  # (a short has no plan to size: SHORT_DISABLED says why)
    cash_cap = min(ec.settled_cash, ec.broker_nonmarginable_bp, e0)
    notes["buying_power_used"] = cash_cap
    if ec.planned_notional > cash_cap + _EPS:
        add(Reason.INSUFFICIENT_SETTLED_CASH)
    if ec.gross_notional_open + ec.planned_notional > C.GROSS_NOTIONAL_MAX_X_E0 * e0 + _EPS:
        add(Reason.GROSS_NOTIONAL)
    return r, notes


def entry_reasons(ec: EntryContext) -> list[Reason]:
    """Every reason this entry is refused; [] = allowed."""
    return entry_check(ec)[0]

