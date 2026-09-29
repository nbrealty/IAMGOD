"""Guardrail constants, the symbol allowlist, setup codes and the setup registry (live paper minute trader).

Every number the bot obeys lives here as a module-level constant. `tests/test_scalp_live_rules.py` asserts each
value (MT-G41), so loosening one fails CI, and `risk_hash()` (config, risk, sizing, orders) is checked at startup
against a value the owner keeps outside the repo. Where two sources differ the stricter number wins; the source of
each number is in `reports/Why day traders lose.md` section 4, `MINUTE_TRADING.md` (paper caps) and the ChatGPT
spec (section 7).

The registry (`registry.json`, committed) freezes each setup version (MT-G10): lane, source (MT-G24), symbol
(MT-G23), parameters, data feeds (MT-G35), known differences from the backtest, and a code hash over the listed
files (its signal module, the sizing function and the order builder). A change to any of them without a new
registration shows up as CODE_HASH_MISMATCH at startup and that setup runs shadow-only.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any, Iterator

from .model import Lane

LIVE_DIR = Path(__file__).resolve().parent
TRADING_DIR = LIVE_DIR.parents[2]                    # trading/
REGISTRY_PATH = LIVE_DIR / "registry.json"
EVENTS_PATH = LIVE_DIR / "events_2026.json"
STATE_DIR = TRADING_DIR / "state" / "scalp"          # gitignored runtime state

# ------------------------------------------------------------------------------------------ instruments (MT-G23)
ALLOWED_SYMBOLS = ("SPY", "QQQ")
SHORTS_ENABLED = False                 # the owner has not OK'd shorts: short signals are shadow-only

# ------------------------------------------------------------------------------------------ caps (MT-G2, MT-G25)
MAX_ROUND_TRIPS_DAY = 4                # entries with any fill, whole bot
MAX_ROUND_TRIPS_SETUP = 2
MAX_OPEN_POSITIONS = 1                 # SPY and QQQ move together: one slot for the whole bot
MAX_ENTRY_SUBMITS_DAY = 8              # parent entry orders sent (filled or not)
MAX_ENTRY_SUBMITS_PER_MIN = 6          # rolling 60 s
MAX_OPEN_PARENTS = 1                   # open bracket parents (legs are not counted)
MAX_NOTIONAL_DAY_X_E0 = 4.0            # both sides traded today <= 4 x E0
MAX_EXIT_ORDERS_PER_MIN = 30           # exits have their own budget; exceeding it delays, never kills

# ------------------------------------------------------------------------------------------ sizing (MT-G14, G15)
RISK_PCT = 0.001                       # 1R = 0.10% of E0 (ChatGPT 0.10% is stricter than MT-G14's 0.25%)
NOTIONAL_CAP_PCT = 0.10                # symbol notional <= 10% of E0 (spec 10% < MT-G14's 25%)
EXPLORATORY_MAX_QTY = 1                # owner decision 3: 1 share per trade in the exploratory lane
GROSS_NOTIONAL_MAX_X_E0 = 1.0          # no leverage on any code path

# ------------------------------------------------------------------------------------------ loss limits (MT-G18)
DAILY_STOP_USD = 25.0
DAILY_STOP_PCTS = (0.005, 0.01)        # daily limit = min($25, 0.5% x E0, 1% x E0)
WEEKLY_STOP_PCT = 0.02                 # of Monday's E0
DRAWDOWN_HALT_PCT = 0.05               # from the test's high-water mark: halt until a person resets
TEST_STOP_USD = 150.0                  # whole-test stop (backtest report section 8)
TEST_MAX_SESSIONS = 60
LOSS_STREAK_N = 3                      # MT-G19
LOSS_STREAK_PAUSE_MIN = 30
STOPOUT_REENTRY_MIN = 15               # MT-G17, per (setup, symbol)

# ------------------------------------------------------------------------------------------ orders (MT-G21, G16)
ENTRY_COLLAR_USD = 0.02                # buy limit = ask + min($0.02, 0.05% x ask)
ENTRY_COLLAR_PCT = 0.0005
STOP_LIMIT_MIN_USD = 0.05              # stop-limit's limit = stop - max($0.05, 50% of the stop distance)
STOP_LIMIT_FRAC = 0.5
EXIT_COLLARS = (0.0005, 0.002, 0.005)  # sell limit = bid x (1 - collar), escalating each EXIT_ACK_S
KILL_COLLARS = (0.002, 0.005, 0.01)
STOP_WATCHDOG_S = 10                   # bid past the stop-limit for 10 s with the stop unfilled -> escalate
STOP_ESCALATION_TRIES = 3
STOP_ESCALATION_COLLARS = (0.002, 0.005, 0.01)   # MT-G21: the first resend is bid - 0.2%, then wider
ENTRY_TIMEOUT_S = 2                    # unfilled entry parent -> cancel request
STOP_CONFIRM_S = 5                     # stop leg confirmed within 5 s of the fill, else flatten
EXIT_ACK_S = 5
CANCEL_CONFIRM_S = 5
CANCEL_GIVE_UP_X = 3                   # an exit's cancels unconfirmed after 3 x CANCEL_CONFIRM_S -> alert + kill
HTTP_TIMEOUT_S = 5.0                   # every broker / data HTTP call: a hang becomes BrokerUnavailable
LOCK_WAIT_S = 10.0                     # watchdog and kill command: wait this long for the broker lock, then go on

# ------------------------------------------------------------------------------------------ clock (MT-G20)
OPEN_BLOCK_MIN = 15                    # no entries 09:30:00-09:44:59 unless registered on the opening window
ENTRY_CUTOFF_MIN_BEFORE_CLOSE = 29     # entries allowed while now < close - 29 min (through 15:30:59)
FLATTEN_MIN_BEFORE_CLOSE = 10          # 15:50: exit everything
KILL_MIN_BEFORE_CLOSE = 5              # 15:55: anything still open -> kill switch
WATCHDOG_FLAT_MIN_BEFORE_CLOSE = 3     # 15:57: the outside watchdog flattens (MT-G39)
RELEASE_BLOCK_BEFORE_MIN = 2           # scheduled 10:00 releases: no entries from t-2m to t+5m
RELEASE_BLOCK_AFTER_MIN = 5
FOMC_BLOCK = ("13:58", "15:30:59")     # FOMC statement days, press conference included
# Notes 1 Patch C (owner-approved 2026-09-28): the WHOLE intended hold is checked, not only the decision time. A new
# entry is refused (EVENT_HORIZON_OVERLAP) when [decision, decision + ENTRY_TIMEOUT_S + max hold + EVENT_EXIT_ALLOWANCE_S]
# meets [t - 5 min, t + 10 min] of any scheduled event t (every release in the calendar, the FOMC statement and the
# press conference), endpoints included. The MT-G20 blocks above stay as they are (the stricter rule wins).
EVENT_WINDOW_BEFORE_MIN = 5
EVENT_WINDOW_AFTER_MIN = 10
EVENT_EXIT_ALLOWANCE_S = 60            # B_exit: time the exit path may need after the hold ends
FOMC_EVENT_TIMES = (("14:00", "FOMC statement"), ("14:30", "FOMC press conference"))  # when the calendar has none
MAX_HOLD_UNTIL_FLATTEN = "until_flatten"   # registry max_hold: held at most until the 15:50 flatten (MT-G20)

# ------------------------------------------------------------------------------------------ data gates (MT-G22)
CLOCK_OFFSET_MS = 100
DATA_SILENCE_S = 2
QUOTE_MAX_AGE_S = 2
BAR_MAX_AGE_S = 65                     # the latest bar ended at most 65 s ago
MAX_SPREAD_USD = 0.02
MAX_SPREAD_BPS = 5.0
MAX_PRICE_VS_LAST_TRADE = 0.005
WILD_MINUTE_RANGE = 0.01               # a 1-minute range > 1% pauses that symbol's entries
WILD_MINUTE_PAUSE_MIN = 10
LULD_PCT = 0.05                        # decision price > 5% from the mean close of the last 5 bars
MWCB_DROP = 0.07                       # SPY down 7% from the prior close (level-1 circuit breaker): no entries
# Notes 1 Patch G (owner-approved): after a halt, no new entries in that symbol for the rest of the session, and
# never assume a reopening. The free IEX feed has no halt status, so a halt is also SUSPECTED when the data polls are
# fresh (last poll <= DATA_SILENCE_S old, the symbol's quote received) but its latest trade is older than
# HALT_SUSPECT_S, from HALT_SUSPECT_FROM_MIN after the open to the close. Entries only: exits are never affected.
HALT_SUSPECT_S = 60
HALT_SUSPECT_FROM_MIN = 5              # 09:35 on a normal day

# ------------------------------------------------------------------------------------------ reconcile, watchdog
RECONCILE_EVERY_S = 5                  # MT-G26, while anything is open or pending
RECONCILE_IDLE_EVERY_S = 30
MISMATCH_CONFIRM_CHECKS = 2
MISMATCH_MIN_GAP_S = 3
HONEST_SLIP_PER_SHARE = 0.01           # MT-G4, per side
SLIP_MODEL_RAISE_X = 1.5               # MT-G3: median slippage over >= 30 fills > 1.5 x model -> shadow
SLIP_MODEL_STOP_X = 2.0                # MT-G13: median slippage over the last 30 fills > 2 x model -> shadow
SLIP_MIN_FILLS = 30
VERSION_MIN_SESSIONS = 20              # MT-G10: at most 1 new version per setup per 20 sessions (safety fixes exempt)
HEARTBEAT_STALE_S = 30                 # MT-G39
WATCHDOG_EVERY_S = 15

# ------------------------------------------------------------------------------------------ samples (MT-G11..G13)
MIN_SAMPLE_TRADES = 100
MIN_SAMPLE_SESSIONS = 40
SWITCH_OFF_N = 30
RETIRE_N = 100

# ------------------------------------------------------------------------------------------ order ids (MT-G25)
ORDER_PREFIX = "SCALP-"
SETUP_CODES = {"ORB5_QQQ": "ORB5Q", "LAST30_MOM_SPY": "L30S", "NOISE_MOM_SPY": "NOISES"}

RISK_FILES = ("config.py", "risk.py", "sizing.py", "orders.py")   # MT-G41: files under risk_hash()

# ------------------------------------------------------------------------------------------ margin framework (record)
# Notes 1 Patch G (owner-approved, record only: the bot trades settled cash, so it is not an entry gate). FINRA
# Regulatory Notice 26-10 replaced the day-trading margin rules with an intraday margin standard from 4 June 2026
# (phase-in to 20 October 2027); Alpaca documents that it applies the intraday standard. check-account prints this
# and every startup journals it; a date before the effective date, or another broker host, is UNKNOWN.
MARGIN_FRAMEWORK = "MARGIN_INTRADAY_FRAMEWORK"
MARGIN_FRAMEWORK_SOURCE = "https://docs.alpaca.markets/us/docs/the-intraday-margin-rule"
MARGIN_FRAMEWORK_EFFECTIVE = "2026-06-04"   # Alpaca adopted FINRA 26-10's intraday standard
MARGIN_FRAMEWORK_CHECKED = "2026-09-28"     # when the source was read (minute-trading session)
MARGIN_FRAMEWORK_HOST = "https://paper-api.alpaca.markets"


def margin_framework(on: date, base_url: str | None = MARGIN_FRAMEWORK_HOST) -> dict[str, Any]:
    """The account's margin framework as a record (never a gate): MARGIN_INTRADAY_FRAMEWORK with its source, the
    date the source was checked and its effective date, or UNKNOWN (before the effective date, or not the Alpaca
    paper host). `age_days` says how old the check is on `on`."""
    eff, chk = date.fromisoformat(MARGIN_FRAMEWORK_EFFECTIVE), date.fromisoformat(MARGIN_FRAMEWORK_CHECKED)
    host_ok = str(base_url or "").rstrip("/") == MARGIN_FRAMEWORK_HOST
    known = host_ok and on >= eff
    return {"framework": MARGIN_FRAMEWORK if known else "UNKNOWN", "source": MARGIN_FRAMEWORK_SOURCE,
            "checked": MARGIN_FRAMEWORK_CHECKED, "effective": MARGIN_FRAMEWORK_EFFECTIVE,
            "age_days": (on - chk).days,
            "why": "Alpaca applies FINRA 26-10's intraday margin standard from 2026-06-04" if known else
                   ("not the Alpaca paper host" if not host_ok else "before the 2026-06-04 effective date"),
            "use": "record only (entries use settled cash, MT-G15)"}


# ------------------------------------------------------------------------------------------ hashes
def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else TRADING_DIR / p


def code_hash(files: list[str], params: dict) -> str:
    """MT-G10: sha256 over each listed file (its path as given, then its bytes, in the order given) and the
    canonical JSON of the parameters. Paths are relative to `trading/` (e.g. "lab/scalp/signals.py"). A
    missing file raises: a version cannot be frozen over code that is not there."""
    h = hashlib.sha256()
    for f in files:
        data = _resolve(f).read_bytes()
        h.update(str(f).encode() + b"\0" + str(len(data)).encode() + b"\0" + data + b"\0")
    h.update(json.dumps(params, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
    return h.hexdigest()


def risk_hash() -> str:
    """MT-G41: hash of the guardrail code (config, risk, sizing, orders). The runner compares it with the value
    the owner stores in the SCALP_RISK_HASH environment variable."""
    return code_hash([f"lab/scalp/live/{f}" for f in RISK_FILES], {})   # relative: same hash in any checkout


# ------------------------------------------------------------------------------------------ registry
class RegistryError(ValueError):
    """The registry breaks a rule (MT-G10, G23, G24, G5..G7): the bot refuses to start with it."""


@dataclass(frozen=True)
class Registration:
    """One frozen setup version on one symbol. `lane` is shown on every journal line (owner decision 3)."""
    setup_id: str
    symbol: str
    version: int
    lane: Lane
    source: str                              # MT-G24: paper URL, book, report id or "original"
    registered: str                          # ISO date
    params: dict[str, Any]
    code_hash: str
    code_files: tuple[str, ...]
    opening_window: bool = False             # registered AND tested on 9:30-9:44 (MT-G20)
    tested_on_release_days: bool = False     # the out-of-sample test included 08:30 release days
    feed_live: str = "IEX"
    feed_backtest: str = "SIP"
    backtest_mean_r: float | None = None     # MT-G13 baseline (None = CUSUM inactive)
    deviations: tuple[str, ...] = ()
    validated_report: dict[str, Any] | None = None
    uses_volume: bool = False                # MT-G35: decides on volume or trade counts (VWAP, RVOL ...)
    model_slip_bps: float | None = None      # MT-G3 / MT-G13 slippage model, bps per side (None = checks off)
    prior_registered: str | None = None      # MT-G10: when version N-1 was registered (versions > 1)
    safety_fix: bool = False                 # MT-G10: a safety or guardrail fix skips the 20-session wait
    max_hold: str | int = MAX_HOLD_UNTIL_FLATTEN   # Notes 1 Patch C: "until_flatten" or minutes from the first fill

    @property
    def code(self) -> str:
        return SETUP_CODES[self.setup_id]

    @property
    def overlay_stop_pct(self) -> float | None:
        v = self.params.get("overlay_stop_pct")
        return None if v is None else float(v)

    @property
    def overlay_target_pct(self) -> float | None:
        v = self.params.get("overlay_target_pct")
        return None if v is None else float(v)

    @property
    def feed_mismatch(self) -> bool:
        """MT-G35: live and backtest feeds differ; every report prints FEED_MISMATCH."""
        return self.feed_live != self.feed_backtest

    def current_hash(self) -> str:
        return code_hash(list(self.code_files), self.params)

    def hash_ok(self) -> bool:
        """MT-G10: the frozen hash still matches the code and parameters on disk."""
        try:
            return self.current_hash() == self.code_hash
        except OSError:
            return False

    def labels(self) -> dict[str, Any]:
        """The fields every journal line about this setup carries."""
        return {"setup_id": self.setup_id, "version": self.version, "lane": self.lane.value,
                "feed": self.feed_live, "code_hash": self.code_hash}         # MT-G10: stamped on every line


@dataclass(frozen=True)
class Registry:
    setups: tuple[Registration, ...]
    account_last4: str
    test_start: date | None = None
    path: str = ""

    def get(self, setup_id: str, symbol: str) -> Registration | None:
        for r in self.setups:
            if r.setup_id == setup_id and r.symbol == symbol:
                return r
        return None

    def for_symbol(self, symbol: str) -> list[Registration]:
        return [r for r in self.setups if r.symbol == symbol]

    def symbols(self) -> list[str]:
        return sorted({r.symbol for r in self.setups})

    def hash_mismatches(self) -> list[Registration]:
        """Registrations whose code or parameters changed since they were frozen (-> shadow-only)."""
        return [r for r in self.setups if not r.hash_ok()]

    def __iter__(self) -> Iterator[Registration]:
        return iter(self.setups)


_FIELDS = ("setup_id", "symbol", "version", "lane", "source", "registered", "params", "code_hash", "code_files",
           "opening_window", "tested_on_release_days", "feed_live", "feed_backtest", "backtest_mean_r",
           "deviations", "uses_volume", "max_hold")


def sessions_between(a: date, b: date) -> int:
    """Weekdays from a (inclusive) to b (exclusive): the MT-G10 version cadence counter. Exchange holidays count
    as sessions here (no calendar needed offline), so it is at most a day or two looser than trading days."""
    import numpy as np
    return int(np.busday_count(a, b))


def _registration(d: dict[str, Any]) -> Registration:
    from ..signals import SETUPS   # the setup functions live and backtest share

    missing = [k for k in _FIELDS if k not in d]
    if missing:
        raise RegistryError(f"registry entry {d.get('setup_id')!r} lacks {missing}")
    sid, sym = str(d["setup_id"]), str(d["symbol"])
    where = f"{sid}/{sym}"
    if not str(d["source"] or "").strip():
        raise RegistryError(f"{where}: empty source (MT-G24: every setup names where it came from)")
    if sym not in ALLOWED_SYMBOLS:
        raise RegistryError(f"{where}: symbol outside the allowlist {ALLOWED_SYMBOLS} (MT-G23)")
    if sid not in SETUPS:
        raise RegistryError(f"{where}: not a setup in lab/scalp/signals.py")
    if sid not in SETUP_CODES:
        raise RegistryError(f"{where}: no order-id code in SETUP_CODES (MT-G25)")
    try:
        lane = Lane(d["lane"])
    except ValueError as e:
        raise RegistryError(f"{where}: unknown lane {d['lane']!r}") from e
    report = d.get("validated_report")
    if lane is Lane.VALIDATED:
        # MT-G5..G7 and MT-G11 are not built in v1, so no report can pass them yet: VALIDATED is refused even
        # with a report that claims to pass.
        why = "no validated_report that passed" if not (isinstance(report, dict) and report.get("passed") is True) \
            else "the MT-G5..G7 validation gates are not built in v1"
        raise RegistryError(f"{where}: lane VALIDATED refused ({why})")
    version = d["version"]
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise RegistryError(f"{where}: version must be an integer >= 1")
    params = d["params"]
    if not isinstance(params, dict):
        raise RegistryError(f"{where}: params must be an object")
    for k in ("overlay_stop_pct", "overlay_target_pct"):
        v = params.get(k)
        if v is not None and not (isinstance(v, (int, float)) and 0 < float(v) < 0.05):
            raise RegistryError(f"{where}: {k} must be null or a fraction between 0 and 0.05")
    if (params.get("overlay_stop_pct") is None) != (params.get("overlay_target_pct") is None):
        raise RegistryError(f"{where}: overlay stop and target come as a pair (MT-G16 needs both)")
    files = d["code_files"]
    if not isinstance(files, list) or not files or not all(isinstance(f, str) for f in files):
        raise RegistryError(f"{where}: code_files must be a non-empty list of paths")
    h = d["code_hash"]
    if not (isinstance(h, str) and len(h) == 64):
        raise RegistryError(f"{where}: code_hash must be a sha256 hex string")
    bmr = d["backtest_mean_r"]
    if not isinstance(d["uses_volume"], bool):
        raise RegistryError(f"{where}: uses_volume must be true or false (MT-G35)")
    slip = d.get("model_slip_bps")
    if slip is not None and not (isinstance(slip, (int, float)) and not isinstance(slip, bool) and slip > 0):
        raise RegistryError(f"{where}: model_slip_bps must be null or a positive number (MT-G3)")
    mh = d["max_hold"]
    if not (mh == MAX_HOLD_UNTIL_FLATTEN or (isinstance(mh, int) and not isinstance(mh, bool) and mh >= 1)):
        raise RegistryError(f"{where}: max_hold must be {MAX_HOLD_UNTIL_FLATTEN!r} or whole minutes >= 1 "
                            "(Notes 1 Patch C: the event check covers the whole hold)")
    registered = str(d["registered"])
    prior, safety = d.get("prior_registered"), bool(d.get("safety_fix", False))
    if version > 1:
        # MT-G10: at most 1 new version per setup per 20 sessions; a safety or guardrail fix is exempt
        if not prior:
            raise RegistryError(f"{where}: version {version} needs prior_registered (MT-G10 version cadence)")
        try:
            gap = sessions_between(date.fromisoformat(str(prior)), date.fromisoformat(registered))
        except ValueError as e:
            raise RegistryError(f"{where}: registered / prior_registered must be ISO dates") from e
        if gap < VERSION_MIN_SESSIONS and not safety:
            raise RegistryError(f"{where}: v{version} registered {gap} sessions after v{version - 1} (MT-G10 needs "
                                f"{VERSION_MIN_SESSIONS}, unless safety_fix)")
    return Registration(
        setup_id=sid, symbol=sym, version=version, lane=lane, source=str(d["source"]),
        registered=registered, params=dict(params), code_hash=h, code_files=tuple(files),
        opening_window=bool(d["opening_window"]), tested_on_release_days=bool(d["tested_on_release_days"]),
        feed_live=str(d["feed_live"]), feed_backtest=str(d["feed_backtest"]),
        backtest_mean_r=None if bmr is None else float(bmr), deviations=tuple(str(x) for x in d["deviations"]),
        validated_report=report, uses_volume=d["uses_volume"], model_slip_bps=None if slip is None else float(slip),
        prior_registered=None if not prior else str(prior), safety_fix=safety, max_hold=mh)


def load_registry(path: str | Path = REGISTRY_PATH) -> Registry:
    """Read and check the registry. Raises RegistryError on any rule break; the bot must not start then."""
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, dict) or not isinstance(raw.get("setups"), list):
        raise RegistryError("registry must be an object with a 'setups' list")
    regs = tuple(_registration(d) for d in raw["setups"])
    seen: set[tuple[str, str]] = set()
    for r in regs:
        if (r.setup_id, r.symbol) in seen:
            raise RegistryError(f"{r.setup_id}/{r.symbol}: registered twice")
        seen.add((r.setup_id, r.symbol))
    last4 = raw.get("account_last4")
    if not (isinstance(last4, str) and len(last4) == 4):
        raise RegistryError("account_last4 must be the 4 last characters of the SCALP paper account number")
    ts = raw.get("test_start")
    return Registry(regs, last4, None if ts is None else date.fromisoformat(ts), str(path))


def rehash_registry(path: str | Path = REGISTRY_PATH) -> dict[str, str]:
    """BUILD-TIME helper: recompute every entry's code_hash and write the file back. Only for a version that has
    not traded yet, or together with a version bump (MT-G10: a changed hash is a new version with 0 trades).
    Returns {"SETUP/SYM": new_hash}."""
    p = Path(path)
    raw = json.loads(p.read_text())
    out = {}
    for d in raw["setups"]:
        d["code_hash"] = code_hash(d["code_files"], d["params"])
        out[f"{d['setup_id']}/{d['symbol']}"] = d["code_hash"]
    p.write_text(json.dumps(raw, indent=2) + "\n")
    return out


def with_lane(reg: Registration, lane: Lane) -> Registration:
    """A copy in another lane (CODE_HASH_MISMATCH or MT-G12/G13 switch-offs demote to SHADOW at runtime; the
    committed registry is never rewritten by the bot)."""
    return replace(reg, lane=lane)



def with_registration(registry: Registry, reg: Registration) -> Registry:
    """The registry with `reg` in place of the entry for the same setup and symbol (runtime demotions only)."""
    return replace(registry, setups=tuple(reg if (r.setup_id, r.symbol) == (reg.setup_id, reg.symbol) else r
                                          for r in registry.setups))
