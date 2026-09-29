"""Shared data shapes for the live paper minute trader (lab/scalp/live). No logic, no network.

Every module in this package speaks in these types, so the pure rules (config, clock, events, sizing, orders,
costs, risk), the execution layer (broker, engine, restore) and the runtime (market, runner, watchdog, report)
can be tested apart. Times are tz-aware pandas Timestamps in America/New_York unless a name says _utc.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, Sequence

import pandas as pd

NY = "America/New_York"


class Feed(str, Enum):
    """Where a price came from (MT-G35). Every quote, bar and trade carries one."""
    IEX = "IEX"      # free real-time feed: IEX's own book and trades only (a few % of volume); not the NBBO
    SIP = "SIP"      # consolidated feed; free only when at least 15 minutes old
    SIM = "SIM"      # made up by the simulator or a test


class Lane(str, Enum):
    """Owner decision 3: which lane a registered setup version runs in (shown in every journal line)."""
    EXPLORATORY = "EXPLORATORY"   # paper, 1 share, results never count as proof of an edge
    VALIDATED = "VALIDATED"       # locked in v1: needs MT-G5..G7 + MT-G11 on forward data and the owner's OK
    SHADOW = "SHADOW"             # decisions logged, no orders
    RETIRED = "RETIRED"           # switched off (MT-G12)


class Mode(str, Enum):
    DRY = "dry"         # live data, simulated broker, no orders sent anywhere
    PAPER = "paper"     # live data, real orders on the ALPACA_SCALP paper account
    REPLAY = "replay"   # recorded or historical data, simulated broker


class Kind(str, Enum):
    """MT-G38: entry gates apply to ENTRY only. EXIT and PROTECT orders always go out."""
    ENTRY = "ENTRY"
    EXIT = "EXIT"         # setup exit, time exit, 15:50 flatten, daily stop, kill switch, watchdog
    PROTECT = "PROTECT"   # stop escalation, partial-fill protection, unprotected-position flatten


class SlotState(str, Enum):
    """ChatGPT spec section 8 order states. v1 has one position slot for the whole bot (MT-G2)."""
    FLAT = "FLAT"
    ARMED = "ARMED"                        # unused by the v1 setups (they fire in one bar)
    ENTRY_PENDING = "ENTRY_PENDING"        # parent sent, no fill yet
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # parent partly filled: cancel the rest, protect what filled
    OPEN = "OPEN"                          # filled, bracket legs confirmed
    EXIT_PENDING = "EXIT_PENDING"          # legs being cancelled and/or a closing order working
    COOLDOWN = "COOLDOWN"                  # flat, but a timer blocks new entries
    DISABLED = "DISABLED"                  # halted / killed / stopped for the day


class Reason(str, Enum):
    """Every rejected candidate and every forced action gets one of these (ChatGPT spec section 8)."""
    # data (MT-G22, MT-G35)
    DATA_STALE = "DATA_STALE"
    INPUT_GAP = "INPUT_GAP"
    QUOTE_STALE = "QUOTE_STALE"
    NO_QUOTE = "NO_QUOTE"
    BAR_STALE = "BAR_STALE"
    SPREAD_TOO_WIDE = "SPREAD_TOO_WIDE"
    CLOCK_OFFSET = "CLOCK_OFFSET"
    CLOCK_UNVERIFIED = "CLOCK_UNVERIFIED"
    PRICE_AWAY_FROM_LAST_TRADE = "PRICE_AWAY_FROM_LAST_TRADE"
    WILD_MINUTE_PAUSE = "WILD_MINUTE_PAUSE"
    HALTED = "HALTED"                      # halt status True, now or earlier today: no entries in it for the day
    HALT_SUSPECTED = "HALT_SUSPECTED"      # data fresh but no trade in the symbol for HALT_SUSPECT_S (Notes 1, G)
    LULD_BAND = "LULD_BAND"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    # calendar and clock (MT-G20)
    MARKET_CLOSED = "MARKET_CLOSED"
    HALF_DAY = "HALF_DAY"
    OPENING_BLOCK = "OPENING_BLOCK"
    AFTER_ENTRY_CUTOFF = "AFTER_ENTRY_CUTOFF"
    FLATTEN_WINDOW = "FLATTEN_WINDOW"
    EVENT_CALENDAR_UNKNOWN = "EVENT_CALENDAR_UNKNOWN"
    RELEASE_BLACKOUT = "RELEASE_BLACKOUT"
    FOMC_BLACKOUT = "FOMC_BLACKOUT"
    EVENT_HORIZON_OVERLAP = "EVENT_HORIZON_OVERLAP"   # the whole intended hold meets an event window (Notes 1, C)
    # caps and cooldowns (MT-G2, G17, G19, G25)
    MAX_TRADES_DAY = "MAX_TRADES_DAY"
    MAX_TRADES_SETUP = "MAX_TRADES_SETUP"
    POSITION_OPEN = "POSITION_OPEN"
    NO_ADD = "NO_ADD"
    OPEN_PARENT = "OPEN_PARENT"
    MAX_ENTRY_SUBMITS_DAY = "MAX_ENTRY_SUBMITS_DAY"
    ENTRY_RATE_MINUTE = "ENTRY_RATE_MINUTE"
    NOTIONAL_DAY = "NOTIONAL_DAY"
    STOPOUT_COOLDOWN = "STOPOUT_COOLDOWN"
    LOSS_STREAK_COOLDOWN = "LOSS_STREAK_COOLDOWN"
    STRATEGY_CONFLICT = "STRATEGY_CONFLICT"
    # loss limits (MT-G18, whole-test stop)
    DAILY_STOP = "DAILY_STOP"
    WEEKLY_STOP = "WEEKLY_STOP"
    DRAWDOWN_HALT = "DRAWDOWN_HALT"
    TEST_STOP = "TEST_STOP"
    # sizing, money, instruments (MT-G14, G15, G21, G23, G28)
    SYMBOL_NOT_ALLOWED = "SYMBOL_NOT_ALLOWED"
    SHORT_DISABLED = "SHORT_DISABLED"
    SIZE_ZERO = "SIZE_ZERO"
    INVALID_STOP = "INVALID_STOP"
    TARGET_TOO_CLOSE = "TARGET_TOO_CLOSE"
    INSUFFICIENT_SETTLED_CASH = "INSUFFICIENT_SETTLED_CASH"
    GROSS_NOTIONAL = "GROSS_NOTIONAL"
    # registry and safety (MT-G10, G26, G27, G41, G25)
    SETUP_NOT_REGISTERED = "SETUP_NOT_REGISTERED"
    CODE_HASH_MISMATCH = "CODE_HASH_MISMATCH"
    RISK_HASH_MISMATCH = "RISK_HASH_MISMATCH"
    LANE_SHADOW = "LANE_SHADOW"
    LANE_RETIRED = "LANE_RETIRED"
    SYMBOL_BLOCKED_BROKER_REJECT = "SYMBOL_BLOCKED_BROKER_REJECT"
    ORDER_STATE_UNCERTAIN = "ORDER_STATE_UNCERTAIN"
    RECONCILE_MISMATCH = "RECONCILE_MISMATCH"
    SELFTEST_FAILED = "SELFTEST_FAILED"
    DEPLOY_IN_MARKET_HOURS = "DEPLOY_IN_MARKET_HOURS"
    KILLED = "KILLED"
    HALTED_MANUAL = "HALTED_MANUAL"
    # forced exits and protection (not rejections)
    TIME_EXIT = "TIME_EXIT"
    SETUP_EXIT = "SETUP_EXIT"
    STOP_UNCONFIRMED = "STOP_UNCONFIRMED"
    STOP_ESCALATION = "STOP_ESCALATION"
    PARTIAL_FILL_PROTECT = "PARTIAL_FILL_PROTECT"
    UNPROTECTED_POSITION = "UNPROTECTED_POSITION"
    ENTRY_TIMEOUT = "ENTRY_TIMEOUT"
    HEARTBEAT_STALE = "HEARTBEAT_STALE"
    OPEN_AT_KILL_TIME = "OPEN_AT_KILL_TIME"
    SHUTDOWN = "SHUTDOWN"                  # SIGTERM: no new entries, exit the position through the normal path


# ------------------------------------------------------------------------------------------------ market data
@dataclass(frozen=True)
class Quote:
    symbol: str
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    ts: pd.Timestamp          # exchange/feed timestamp
    recv: pd.Timestamp        # when this process received it
    feed: Feed

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def valid(self) -> bool:
        """Positive and not crossed."""
        return self.bid > 0 and self.ask > 0 and self.ask >= self.bid


@dataclass(frozen=True)
class LastTrade:
    symbol: str
    price: float
    size: float
    ts: pd.Timestamp
    feed: Feed


@dataclass(frozen=True)
class Bar:
    """A COMPLETED 1-minute bar; `start` is the bar's start time (the 9:30 bar covers 9:30:00-9:30:59)."""
    symbol: str
    start: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float
    feed: Feed
    recv: pd.Timestamp | None = None


@dataclass(frozen=True)
class MarketSnapshot:
    """What the runner hands the engine on every tick (about once a second live)."""
    now: pd.Timestamp
    quotes: dict[str, Quote]                  # latest quote per symbol (may be missing)
    trades: dict[str, LastTrade]              # latest trade per symbol (may be missing)
    new_bars: dict[str, list[Bar]]            # bars completed since the previous tick, oldest first
    last_data_ok: pd.Timestamp | None         # time of the last successful data poll / message
    clock_offset_ms: float | None             # |local - reference| + uncertainty; None = unverified
    halted: dict[str, bool | None] = field(default_factory=dict)   # None = status unavailable on this feed


# ------------------------------------------------------------------------------------------------ orders
@dataclass(frozen=True)
class OrderSpec:
    """An order we want to send. Built ONLY by orders.py (which has no market or stop-market path, MT-G21).
    order_class "simple": one limit order. "bracket": limit parent + take-profit limit + stop-limit stop."""
    client_order_id: str
    symbol: str
    side: str                       # "buy" | "sell"
    qty: int
    kind: Kind
    limit_price: float
    order_class: str = "simple"     # "simple" | "bracket"
    take_profit: float | None = None
    stop_price: float | None = None
    stop_limit_price: float | None = None
    setup_id: str = ""
    version: int = 0
    reason: str = ""
    tif: str = "day"
    extended_hours: bool = False


@dataclass(frozen=True)
class OrderView:
    """A broker's view of one order (Alpaca statuses, lower case: new, accepted, pending_new, held,
    partially_filled, filled, canceled, expired, rejected, pending_cancel, replaced, done_for_day ...)."""
    id: str
    client_order_id: str
    symbol: str
    side: str
    qty: float
    filled_qty: float
    filled_avg_price: float | None
    status: str
    order_type: str                 # "limit" | "stop_limit" | ...
    limit_price: float | None = None
    stop_price: float | None = None
    order_class: str = "simple"
    legs: tuple["OrderView", ...] = ()
    submitted_at: pd.Timestamp | None = None
    filled_at: pd.Timestamp | None = None
    updated_at: pd.Timestamp | None = None
    reject_reason: str | None = None

    @property
    def open(self) -> bool:
        return self.status in OPEN_STATUSES


OPEN_STATUSES = frozenset({"new", "accepted", "pending_new", "accepted_for_bidding", "held", "partially_filled",
                           "pending_cancel", "pending_replace", "calculated", "stopped", "suspended"})
DONE_STATUSES = frozenset({"filled", "canceled", "expired", "rejected", "done_for_day", "replaced"})


@dataclass(frozen=True)
class PositionView:
    symbol: str
    qty: float                  # signed: negative = short (must never happen: MT-G15)
    avg_entry_price: float


@dataclass(frozen=True)
class AccountView:
    account_number: str
    status: str
    equity: float
    last_equity: float          # equity at the previous close = E0 (MT-G40)
    cash: float
    buying_power: float
    non_marginable_buying_power: float
    trading_blocked: bool
    shorting_enabled: bool
    base_url: str


class BrokerReject(Exception):
    """The broker refused an order (restricted, halted, insufficient funds, duplicate id, PDT...). Never
    retried automatically (MT-G25)."""

    def __init__(self, message: str, status: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status, self.code = status, code


class BrokerUnavailable(Exception):
    """Timeout or network failure: the request may or may not have reached the broker. Query by client id
    before trying again (MT-G25)."""


class RunawayOrders(Exception):
    """guard.GuardedBroker refused an ENTRY that breaks an order-rate or size cap (MT-G25): kill switch."""


class PaperLockError(Exception):
    """MT-G36: anything but the ALPACA_SCALP paper account. Raised before any network call where possible."""


class Broker(Protocol):
    """Implemented by broker.AlpacaBroker (paper only) and broker.SimBroker (dry run, replay, tests)."""
    mode: Mode

    def account(self) -> AccountView: ...
    def positions(self) -> list[PositionView]: ...
    def open_orders(self) -> list[OrderView]: ...                       # nested: parents carry their legs
    def orders_since(self, since: pd.Timestamp) -> list[OrderView]: ...  # all statuses, nested
    def get_order(self, order_id: str) -> OrderView: ...
    def get_by_client_id(self, client_order_id: str) -> OrderView | None: ...
    def submit(self, spec: OrderSpec) -> OrderView: ...                 # raises BrokerReject / BrokerUnavailable
    def cancel(self, order_id: str) -> None: ...                        # a REQUEST; poll for "canceled"


# ------------------------------------------------------------------------------------------------ decisions
@dataclass(frozen=True)
class Candidate:
    """A setup intent at the latest bar, before any gate."""
    setup_id: str
    version: int
    symbol: str
    action: str                     # "enter" | "exit"
    side: int                       # +1 long, -1 short (enter only)
    bar_start: pd.Timestamp         # the bar whose close decided it
    stop: float | None = None
    stop_dist: float | None = None
    target: float | None = None
    target_r: float | None = None
    target_dist: float | None = None
    reason: str = ""


@dataclass(frozen=True)
class Decision:
    """The outcome for one candidate: accepted (with the order it produced) or rejected with ALL reasons."""
    candidate: Candidate
    accepted: bool
    reasons: tuple[Reason, ...] = ()
    order: OrderSpec | None = None
    notes: dict[str, Any] = field(default_factory=dict)


@dataclass
class DayCounters:
    """Everything the entry gate needs that must survive a restart (MT-G40). Rebuilt from the broker's
    SCALP- order history by restore.py, never trusted from a local file alone."""
    session_date: Any                                   # datetime.date
    e0: float                                           # Alpaca last_equity at the start of the session
    entry_submits: int = 0                              # parent entry orders sent today (MT-G2: 8)
    entry_submit_times: list[pd.Timestamp] = field(default_factory=list)   # for the rolling-minute cap
    round_trips: int = 0                                # entries with any fill today (MT-G2: 4)
    round_trips_by_setup: dict[str, int] = field(default_factory=dict)     # (MT-G2: 2 each)
    loss_streak: int = 0                                # consecutive losing closed trades (honest P&L)
    loss_pause_until: pd.Timestamp | None = None        # MT-G19
    stopout_until: dict[tuple[str, str], pd.Timestamp] = field(default_factory=dict)  # (setup, symbol) MT-G17
    realized_pnl: float = 0.0                           # paper dollars today
    realized_honest: float = 0.0                        # honest dollars today (MT-G4)
    notional_traded: float = 0.0                        # both sides, today (MT-G25: 4 x E0)
    buy_notional: float = 0.0                           # today's buys, for settled cash (MT-G15)
    cash_prev_close: float | None = None                # settled-cash base (MT-G15)
    week_honest: float = 0.0                            # honest P&L since Monday (MT-G18)
    week_e0: float | None = None                        # Monday's E0
    test_honest: float = 0.0                            # honest P&L since the test started (whole-test stop)
    test_sessions: int = 0                              # sessions traded or run since the test started
    test_peak: float = 0.0                              # high-water mark of test_honest (MT-G18 drawdown)
    blocked_symbols: set[str] = field(default_factory=set)   # broker rejections block entries (MT-G25)
    halt_blocks: dict[str, str] = field(default_factory=dict)  # symbol -> HALTED / HALT_SUSPECTED, rest of the day
    wild_pause_until: dict[str, pd.Timestamp] = field(default_factory=dict)  # MT-G22 1% minute
    daily_stopped: bool = False
    day_trades_5d: int = 0                              # MT-G15: our own day trades, last 5 sessions incl. today


class Journal(Protocol):
    def write(self, kind: str, **fields: Any) -> None: ...


def as_ny(t: Any) -> pd.Timestamp:
    t = pd.Timestamp(t)
    return t.tz_localize(NY) if t.tzinfo is None else t.tz_convert(NY)


def seq(x: Sequence[Any] | None) -> tuple[Any, ...]:
    return tuple(x or ())
