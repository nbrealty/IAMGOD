"""Report for the live paper minute trader, from its journals (MT-G3, G4, G11, G12, G13, G33, G34, G35, G41).

`python -m lab.scalp.live report [--date D | --since D] [--mode dry|paper|replay] [--remark]`

Every block is per setup and lane, and every line about a setup carries its lane (EXPLORATORY results never count
as proof of an edge). In order:
1. MT-G41: the append-only changes log (guardrail changes, halt resets) comes FIRST.
2. EXECUTION HEALTH (Notes 1 Patch F), kept apart from the strategy's results: quote age at each entry decision, data
   gaps in the session, order acknowledgement latency (submit -> the broker's answer) and submit -> fill, partial
   fills, fills that raced a cancel request, cancels the broker refused, broker rejections, halt blocks, and per
   setup the median slippage against the decision mid with its FEED tag next to the registered model (MT-G3, G35).
   Where nothing registered says what "normal" is, the line says "uncalibrated" (a missing baseline is not
   "healthy"). None of these incidents is ever an R value: the MT-G12 / G13 lines below read the closed trades only.
2b. STRATEGY PERFORMANCE: per setup closed trades, sessions, win rate, paper P&L next to honest P&L (MT-G4), cost /
   gross over the last 50 trades, the MT-G11 sample label, the MT-G12 switch-off check, the MT-G13 drift check
   (inactive without a backtest baseline), FEED_MISMATCH when live and backtest feeds differ, and the Notes 1
   Patch E excursions (MFE_R / MAE_R on the bid, time to +0.25R / +0.5R / +1R): measurement only, never P&L.
2c. TRADING P&L AND OPERATING RESULT (Notes 1 Patch H): honest trading P&L, the running costs from
   `operating_costs.json` pro-rated over the report's calendar days, and trading P&L minus them. A cost recorded as
   null prints "not recorded" (never 0). Nothing sizes a trade from this.
3. MT-G33 bias checks: exits that were not a standard exit (must be 0; a SIGTERM mid-trade shows as a manual stop),
   the disposition (profit vs loss taking) of every exit that was not a pre-set one, qty different from the sizing
   function (must be 0), trades per day after red vs green days, entries in top-decile volume minutes (> 20% flags).
4. MT-G34: honest P&L by 15-minute entry bucket next to SPY buy-and-hold, SPY open-to-close, exposure-matched SPY
   and cash (from the cached SIP bars, when present; nothing is downloaded).
5. Every rejected candidate counted by reason; the dry-run / replay "would have" list.
`--remark` (MT-G4): each fill older than 15 minutes is compared with the historical SIP quote at its fill time, and
every take-profit still PENDING_VERIFY is RESOLVED against the historical SIP trades of its fill minute and the next
(a trade strictly through the limit -> `tp_verified`, its R counts; none -> `tp_missed`, 0R), written to
journal/<date>-<mode>-remark.jsonl for the next start (paper: with --broker also the take-profits only the broker's
history still has). The MT-G12 / G13 lines read the same series as the engine (runner.lane_history) and say how
many take-profits were verified, missed or left out.

Journal lines read (written by the engine): `decision` (setup_id, lane, symbol, accepted, reasons), `submit` /
`would_submit` (cid, qty, limit, stop, stop_limit, target, numbers = every sizing input), `fill` (symbol, side,
qty, price, slippage {cents, bps}, feed) and `trade_closed` (setup_id, lane, symbol, qty, how, paper_pnl,
honest_pnl, risk_usd, r). A trade's entry time is its last buy fill. Missing fields show as n/a, never guessed.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np
import pandas as pd

from . import config as C
from . import gates as G
from . import journal as J
from . import state as S
from .model import Lane, as_ny

# MT-G33 check 1: exits by stop, target, time exit, 15:50 flatten, daily stop or kill switch (the stop mechanism's
# PROTECT sells count as stops). A SIGTERM / SHUTDOWN exit is a person stopping the bot mid-trade: NOT standard.
STANDARD_EXITS = frozenset({"STOP", "STOP_LOSS", "TARGET", "TAKE_PROFIT", "TIME_EXIT", "FLATTEN", "FLATTEN_WINDOW",
                            "DAILY_STOP", "KILL", "KILLED", "KILL_SWITCH", "SETUP_EXIT", "STOP_ESCALATION",
                            "PARTIAL_FILL_PROTECT", "UNPROTECTED_POSITION", "STOP_UNCONFIRMED", "OPEN_AT_KILL_TIME",
                            "HEARTBEAT_STALE", "WATCHDOG", "RECONCILE_MISMATCH", "DRAWDOWN_HALT",
                            "LEG_DURING_EXIT", "ENTRY_TIMEOUT", "EXIT_BEFORE_RESTART"})
# MT-G33 check 2: the pre-set exits (stop, target, time exit, the setup's own exit and the stop mechanism). Every
# other exit (daily stop, kill switch, watchdog, shutdown, anything manual) gets the disposition check.
PRESET_EXITS = frozenset({"STOP", "STOP_LOSS", "TARGET", "TAKE_PROFIT", "TIME_EXIT", "FLATTEN", "FLATTEN_WINDOW",
                          "SETUP_EXIT", "STOP_ESCALATION", "PARTIAL_FILL_PROTECT", "UNPROTECTED_POSITION",
                          "STOP_UNCONFIRMED", "LEG_DURING_EXIT", "ENTRY_TIMEOUT"})
MANUAL_EXITS = frozenset({"SIGTERM", "SHUTDOWN"})
VOLUME_LOOKBACK = 20                    # MT-G33 check 5: same minute of day over the last 20 sessions
VOLUME_FLAG_SHARE = 0.20
TRADE_KINDS = ("trade_closed",)
OPERATING_COSTS_PATH = C.LIVE_DIR / "operating_costs.json"
DAYS_PER_MONTH = 365.25 / 12
UNCALIBRATED = "uncalibrated: no registered baseline"
RUNNER_LOOKBACK_DAYS = 400             # the broker history the re-mark reads (the runner's TEST_LOOKBACK_DAYS)
EXPLORATORY_NOTE = "EXPLORATORY lane: paper, 1 share; results never count as proof of an edge."


def _f(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _money(x: float | None) -> str:
    return "n/a" if x is None else f"${x:,.2f}"


def _num(x: float | None, fmt: str = "{:.2f}") -> str:
    return "n/a" if x is None else fmt.format(x)


def _trades(lines: list[dict]) -> list[dict]:
    """The engine's `trade_closed` lines, oldest first, each with `entry_ts` (the last buy fill of that setup and
    symbol before it), `exit_ts` (the line's time) and `exit_reason` (the engine's `how`)."""
    last_buy: dict[tuple[str, str], str] = {}
    out = []
    for x in lines:
        key = (str(x.get("setup_id") or ""), str(x.get("symbol") or ""))
        if x.get("kind") == "fill" and x.get("side") == "buy":
            last_buy[key] = x.get("ts")
        elif x.get("kind") in TRADE_KINDS:
            out.append({"entry_ts": last_buy.get(key), "exit_ts": x.get("ts"),
                        "exit_reason": x.get("how"), **x})
    return out


def r_multiple(t: dict) -> float | None:
    """Honest P&L in R: honest dollars / the dollars at risk when the entry was planned (qty x (limit -
    stop-limit)). The engine writes it as `r`; otherwise computed from `risk_usd`."""
    r = _f(t.get("r"))
    if r is not None:
        return r
    h, risk_usd = _f(t.get("honest_pnl")), _f(t.get("risk_usd"))
    return None if h is None or not risk_usd else h / risk_usd


# ------------------------------------------------------------------------------------------ MT-G4 resolutions
TP_RESOLVED = ("tp_verified", "tp_missed")
SRC = "_src"                       # the journal file a line was read from (added by read_lines, never written)


def read_lines(files: Iterable[Path]) -> list[dict]:
    """Every line of the journal files, each tagged with the file it came from (SRC). A SimBroker's order ids
    repeat across processes (sim-00002), so an order id only identifies a take-profit inside one file."""
    return [{**x, SRC: Path(p).name} for p in files for x in J.read_journal(p)]


class TpIndex:
    """MT-G4 resolutions of take-profit fills (`tp_verified` from a live bar or the SIP re-mark, `tp_missed` from the
    re-mark). A trade is found by its entry's client id (parent_cid: deterministic, unique per trade, the same in
    every process), else by the take-profit's order id INSIDE the same journal file (`src`), or anywhere when the
    ids are the broker's own (`unique_ids`, Alpaca paper). A verification beats a missed fill."""

    def __init__(self, lines: Iterable[dict]):
        self.by_key: dict[tuple, dict] = {}
        self.by_oid: dict[str, dict] = {}
        for x in lines:
            if x.get("kind") not in TP_RESOLVED:
                continue
            keys = []
            if x.get("parent_cid"):
                keys.append(("cid", str(x["parent_cid"])))
            if x.get("order_id"):
                keys.append(("oid", str(x.get("src") or x.get(SRC) or ""), str(x["order_id"])))
            for k in keys:
                self._put(self.by_key, k, x)
            if x.get("order_id"):
                self._put(self.by_oid, str(x["order_id"]), x)

    @staticmethod
    def _put(d: dict, k: Any, x: dict) -> None:
        if k not in d or (d[k].get("kind") == "tp_missed" and x.get("kind") == "tp_verified"):
            d[k] = x

    def find(self, close: dict, unique_ids: bool = False) -> dict | None:
        cid, oid = close.get("parent_cid"), close.get("tp_order_id")
        if cid and ("cid", str(cid)) in self.by_key:
            return self.by_key[("cid", str(cid))]
        if oid:
            if unique_ids:
                return self.by_oid.get(str(oid))
            return self.by_key.get(("oid", str(close.get(SRC) or ""), str(oid)))
        return None


def r_series(closes: Iterable[dict], index: TpIndex, unique_ids: bool = False) -> dict[str, Any]:
    """A setup version's MT-G12 / G13 series from its closed trades (oldest first; dicts with r, gate_r,
    pending_verify, parent_cid, tp_order_id): {"r": the resolved series (a trade not closed by a take-profit, or a
    VERIFIED one, at its honest R; an MT-G4 missed fill at 0R), "pend": {key: gate R (min(R, 0))} of take-profits
    still PENDING_VERIFY, "verified", "missed", "pending" (counts)}. gates.lane_check_pending decides on both."""
    rs: list[float] = []
    pend: dict[str, float] = {}
    n_ver = n_miss = 0
    for c in closes:
        r = _f(c.get("r"))
        if r is None:
            continue
        if not c.get("pending_verify"):
            rs.append(r)
            continue
        hit = index.find(c, unique_ids)
        if hit is not None and hit.get("kind") == "tp_verified":
            rs.append(r)
            n_ver += 1
        elif hit is not None:
            rs.append(0.0)                               # MT-G4: an honestly unfilled take-profit books 0
            n_miss += 1
        else:
            g = _f(c.get("gate_r"))
            key = str(c.get("parent_cid") or f"{c.get(SRC) or ''}:{c.get('tp_order_id') or len(pend)}")
            pend[key] = min(g if g is not None else r, 0.0)
    return {"r": rs, "pend": pend, "verified": n_ver, "missed": n_miss, "pending": len(pend)}


def _slip(x: dict, unit: str) -> float | None:
    s = x.get("slippage")
    return _f(s.get(unit)) if isinstance(s, dict) else None


def size_checks(lines: list[dict]) -> list[str]:
    """MT-G33 check 3: every entry sent (or that would have been sent) must have exactly the qty the sizing
    function gives for the numbers journalled with it. Returns one text per mismatch."""
    from . import sizing
    bad = []
    for x in lines:
        if x.get("kind") not in ("submit", "would_submit"):
            continue
        n = x.get("numbers") or {}
        try:
            want = sizing.qty(float(n["e0"]), float(n["limit"]), float(n["stop"]), float(n["stop_limit"]),
                              Lane(n.get("lane") or x.get("lane")))
        except (KeyError, TypeError, ValueError):
            bad.append(f"{x.get('cid')}: sizing inputs missing from the journal")
            continue
        if _f(x.get("qty")) != float(want):
            bad.append(f"{x.get('cid')}: qty {x.get('qty')} but sizing gives {want}")
    return bad


def _day(t: dict, key: str = "exit_ts") -> str:
    v = t.get(key) or t.get("entry_ts") or t.get("ts") or ""
    return str(v)[:10]


# ------------------------------------------------------------------------------------------ blocks
def setup_block(setup_id: str, lane: str, trades: list[dict], reg: C.Registration | None,
                fills: list[dict], line_feeds: Iterable[str] = (), index: TpIndex | None = None) -> list[str]:
    n = len(trades)
    sessions = len({_day(t) for t in trades})
    paper = [v for v in (_f(t.get("paper_pnl")) for t in trades) if v is not None]
    honest = [v for v in (_f(t.get("honest_pnl")) for t in trades) if v is not None]
    wins = [h > 0 for h in honest]
    # MT-G12 / G13 read the same series as the engine (runner.lane_history): take-profits still PENDING_VERIFY are
    # left out of it (and counted at their gate value only when that is stricter), MT-G4 missed fills count 0R
    ser = r_series([{**t, "r": r_multiple(t)} for t in trades], index or TpIndex(()))
    rs = ser["r"]
    label = G.sample_label(n, sessions)
    out = [f"[{lane}] {setup_id} ({reg.symbol if reg else '?'} v{reg.version if reg else '?'}): {n} closed trades "
           f"over {sessions} sessions -> {label}"]
    out.append(f"    win rate {_num(100 * np.mean(wins) if wins else None, '{:.0f}%')}; paper P&L "
               f"{_money(sum(paper) if paper else None)} vs honest P&L {_money(sum(honest) if honest else None)}")
    last = trades[-50:]
    gross = sum(v for v in (_f(t.get("paper_pnl")) for t in last) if v is not None)
    cost = sum((_f(t.get("paper_pnl")) or 0.0) - (_f(t.get("honest_pnl")) or 0.0) for t in last)
    out.append(f"    cost / gross over the last {len(last)} trades: "
               + ("n/a (no trades)" if not last else f"{cost / gross:.0%}" if gross > 0 else "n/a (gross profit <= 0)"))
    pend = list(ser["pend"].values())
    lane_now = G.lane_check_pending(rs, pend, [], None, None)[0] if (rs or pend) else None
    out.append(f"    MT-G12 switch-off check: " + (f"-> {lane_now.value}" if lane_now else
                                                   f"keep ({len(rs)} R values; acts from {C.SWITCH_OFF_N})"))
    out.append(f"    MT-G4 take-profits: {ser['verified']} verified, {ser['missed']} missed fill(s) at 0R, "
               f"{ser['pending']} PENDING_VERIFY left out of the R series"
               + (" (also counted at their gate value, at most 0R, where that is stricter; run `report --remark`)"
                  if ser["pending"] else ""))
    base = reg.backtest_mean_r if reg else None
    if base is None:
        out.append("    MT-G13 drift (CUSUM): inactive (no backtest baseline in R)")
    else:
        trip = G.cusum_trip(rs, base) or (bool(pend) and G.cusum_trip(rs + pend, base))
        out.append("    MT-G13 drift (CUSUM): " + ("TRIPPED -> shadow" if trip else "ok"))
    if reg is not None:
        # MT-G35: the feed the journalled run actually used (each line's `feed` label: IEX live, SIP for a historical
        # replay, SIM for synthetic data), against the backtest's feed; the registry's live feed only when the
        # lines carry none
        used = sorted({str(f) for f in line_feeds if f} | {str(t.get("feed")) for t in trades if t.get("feed")}) \
            or [reg.feed_live]
        diff = [f for f in used if f != reg.feed_backtest]
        if diff:
            out.append(f"    FEED_MISMATCH: live {'/'.join(diff)} vs backtest {reg.feed_backtest} (MT-G35)")
    out.append("    " + excursion_line(trades))
    tag = f"[{lane}] {setup_id}"
    return [out[0]] + [f"{tag}  {x.strip()}" for x in out[1:]]


def slippage_line(fills: list[dict], reg: C.Registration | None) -> str:
    """MT-G3 / G35 execution health: median slippage against the decision mid, with the feed and the registered
    model (the one baseline v1 has)."""
    sc = [v for v in (_slip(x, "cents") for x in fills) if v is not None]
    sb = [v for v in (_slip(x, "bps") for x in fills) if v is not None]
    feeds = sorted({str(x.get("feed") or "?") for x in fills}) or ["?"]
    model = reg.model_slip_bps if reg is not None else None
    return (f"median slippage {_num(float(np.median(sc)) if sc else None)} cents / "
            f"{_num(float(np.median(sb)) if sb else None)} bps over {len(sc)} fills [FEED={'/'.join(feeds)}]"
            + (f" vs model {model:g} bps per side (MT-G3)" if model is not None else f" ({UNCALIBRATED})"))


def excursion_line(trades: list[dict]) -> str:
    """Notes 1 Patch E, per setup, from each trade_closed `diag`: median MFE_R / MAE_R (bid-based, long), how many
    reached +0.25R / +0.5R / +1R and the median seconds to +0.5R, and how many had seconds without a quote (a target
    never reached while quotes were missing is 'not seen', not 'never reached'). Measurement only: not P&L."""
    ds = [t.get("diag") for t in trades]
    ok = [d for d in ds if isinstance(d, dict) and _f(d.get("mfe_r")) is not None]
    head = "excursions (Notes 1 Patch E, measurement only, not P&L): "
    if not ok:
        return head + f"none measured ({len(trades)} closed trades)"
    mfe = [float(d["mfe_r"]) for d in ok]
    mae = [float(d["mae_r"]) for d in ok]
    hits = {k: [_f(d.get(k)) for d in ok] for k in ("t_plus_025r_s", "t_plus_05r_s", "t_plus_1r_s")}
    t05 = [v for v in hits["t_plus_05r_s"] if v is not None]
    gaps = sum(1 for d in ok if d.get("gaps"))
    return (head + f"median MFE {np.median(mfe):.2f}R / MAE {np.median(mae):.2f}R over {len(ok)} trades; reached "
            + ", ".join(f"{lbl} {sum(v is not None for v in hits[k])}/{len(ok)}" for lbl, k in
                        (("+0.25R", "t_plus_025r_s"), ("+0.5R", "t_plus_05r_s"), ("+1R", "t_plus_1r_s")))
            + f"; median time to +0.5R {_num(float(np.median(t05)) if t05 else None, '{:.0f} s')}"
            + f"; {gaps} trade(s) with seconds without a quote (targets not reached there are 'not seen')")


# ------------------------------------------------------------------------------------------ execution health (F)
def _med_max(xs: list[float], unit: str, fmt: str = "{:.2f}") -> str:
    if not xs:
        return "n/a (none)"
    return f"median {fmt.format(float(np.median(xs)))} {unit}, max {fmt.format(max(xs))} {unit} over {len(xs)}"


def execution_block(lines: list[dict], groups: dict[tuple[str, str], list[dict]], registry: C.Registry,
                    fills: list[dict]) -> list[str]:
    """Notes 1 Patch F: execution incidents, apart from the strategy's results. Read from the engine's journal
    lines only; nothing here is an R value or reaches gates.switch_off (MT-G12) or the CUSUM (MT-G13)."""
    kinds: dict[str, list[dict]] = defaultdict(list)
    for x in lines:
        kinds[str(x.get("kind"))].append(x)
    ages = [v for v in (_f((x.get("notes") or {}).get("quote_age_s")) for x in kinds["decision"]
                        if x.get("action") == "enter" and isinstance(x.get("notes"), dict)) if v is not None]
    stale = sum(1 for v in ages if v > C.QUOTE_MAX_AGE_S)
    gaps = [v for v in (_f(x.get("seconds")) for x in kinds["data_gap"]) if v is not None]
    open_gaps = max(len(kinds["data_gap_start"]) - len(kinds["data_gap"]), 0)
    ack = {k: [v for v in (_f(x.get("ack_ms")) for x in kinds[k]) if v is not None]
           for k in ("submit", "exit_order", "kill_order")}
    entry_fills = [x for x in fills if x.get("role") == "entry"]
    seen = [v for v in (_f((x.get("latency") or {}).get("seen_after_submit_s")) for x in entry_fills
                        if isinstance(x.get("latency"), dict)) if v is not None]
    brk = [v for v in (_f((x.get("latency") or {}).get("broker_submit_to_fill_s")) for x in fills
                       if isinstance(x.get("latency"), dict)) if v is not None]
    partial = {str(x.get("cid") or x.get("order_id")): x.get("role") for x in fills
               if _f(x.get("order_qty")) and _f(x.get("filled_total")) is not None
               and float(x["filled_total"]) < float(x["order_qty"]) - 1e-9}
    races = sum(1 for x in fills if x.get("cancel_race"))
    halts = Counter(f"{x.get('symbol')} {x.get('reason')}" for x in kinds["halt_block"])
    out = ["EXECUTION HEALTH (Notes 1 Patch F: incidents are kept apart from strategy results and never enter the "
           "MT-G12 / G13 R series)",
           f"    quote age at entry decisions: {_med_max(ages, 's')}; {stale} older than {C.QUOTE_MAX_AGE_S} s "
           f"({UNCALIBRATED})",
           f"    data gaps in the session (no data for more than {C.DATA_SILENCE_S} s): {len(gaps)}, "
           f"{sum(gaps):.0f} s in all" + (f", longest {max(gaps):.0f} s" if gaps else "")
           + (f"; {open_gaps} still open at the end of the journal" if open_gaps else "") + f" ({UNCALIBRATED})",
           f"    order acknowledgement (submit -> broker answer): entries {_med_max(ack['submit'], 'ms', '{:.0f}')}; "
           f"exits {_med_max(ack['exit_order'], 'ms', '{:.0f}')}; kill orders {_med_max(ack['kill_order'], 'ms', '{:.0f}')}"
           f" ({UNCALIBRATED})",
           f"    submit -> entry fill seen: {_med_max(seen, 's')}; broker submitted -> filled: {_med_max(brk, 's')} "
           f"({UNCALIBRATED})",
           f"    partial fills: {sum(1 for r in partial.values() if r == 'entry')} entry order(s), "
           f"{sum(1 for r in partial.values() if r != 'entry')} other order(s); fills that raced a cancel request: "
           f"{races}; cancel requests the broker refused: {len(kinds['cancel_failed'])}",
           f"    broker rejections: entries {len(kinds['broker_reject'])}, exits {len(kinds['exit_rejected'])}, kill "
           f"orders {len(kinds['kill_order_rejected'])}; submits with an unknown outcome: "
           f"{len(kinds['submit_uncertain']) + len(kinds['exit_uncertain'])}",
           "    halt blocks (no entries in the symbol for the rest of that session): "
           + (", ".join(f"{k} x{v}" for k, v in sorted(halts.items())) if halts else "none")]
    for (sid, lane) in sorted(groups):
        reg = next((r for r in registry.setups if r.setup_id == sid), None)
        f = [x for x in fills if x.get("setup_id") == sid]
        out.append(f"[{lane}] {sid}  {slippage_line(f, reg)}")
    return out


# ------------------------------------------------------------------------------------------ operating result (H)
def load_operating_costs(path: str | Path = OPERATING_COSTS_PATH) -> list[dict]:
    """The committed running costs: [{name, usd_per_month (a number >= 0, or None = not recorded), source, note}].
    A missing or broken file raises: the report then says so instead of pretending the costs are 0."""
    import json
    raw = json.loads(Path(path).read_text())
    out = []
    for e in raw.get("costs") or []:
        name = str(e.get("name") or "").strip()
        v = e.get("usd_per_month")
        if not name or not str(e.get("source") or "").strip():
            raise ValueError(f"operating cost entry without a name or source: {e!r}")
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not v >= 0):
            raise ValueError(f"{name}: usd_per_month must be a number >= 0 or null (not recorded)")
        out.append({"name": name, "usd_per_month": None if v is None else float(v), "source": str(e["source"]),
                    "note": str(e.get("note") or "")})
    return out


def operating_block(trades: list[dict], lines: list[dict], costs: list[dict] | None) -> list[str]:
    """Notes 1 Patch H: trading P&L (honest, after fees and honest slippage) and the operating result = trading P&L
    minus the running costs pro-rated over the report's calendar days (first to last journal date). A cost recorded
    as null is "not recorded": left out of the sum and named, never counted as 0. Sizing never reads any of this."""
    honest = [v for v in (_f(t.get("honest_pnl")) for t in trades) if v is not None]
    paper = [v for v in (_f(t.get("paper_pnl")) for t in trades) if v is not None]
    pnl = sum(honest)
    out = ["TRADING P&L AND OPERATING RESULT (Notes 1 Patch H; nothing here changes a trade's size)",
           f"    trading P&L (honest: fees and honest slippage included): {_money(pnl)} over {len(honest)} closed "
           f"trades (paper {_money(sum(paper) if paper else 0.0)})"]
    dates = sorted({str(x.get("ts", ""))[:10] for x in lines if x.get("ts")})
    if costs is None:
        return out + ["    operating costs: operating_costs.json missing or unreadable: not recorded; no operating "
                      "result"]
    if not dates:
        return out + ["    operating costs: no journal dates, nothing to pro-rate; no operating result"]
    days = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days + 1
    parts, known, missing = [], 0.0, []
    for c in costs:
        v = c["usd_per_month"]
        if v is None:
            parts.append(f"{c['name']} not recorded")
            missing.append(c["name"])
        else:
            amt = v * days / DAYS_PER_MONTH
            known += amt
            parts.append(f"{c['name']} {_money(amt)} (${v:,.2f}/month)")
    out.append(f"    operating costs over {days} calendar day(s), pro-rated: " + ("; ".join(parts) or "none listed"))
    out.append(f"    operating result (trading P&L - recorded costs): {_money(pnl - known)}"
               + (f"  <- incomplete: {', '.join(missing)} not recorded" if missing else ""))
    return out


def _standard_exit(how: Any) -> bool:
    h = str(how or "").upper()
    return h in STANDARD_EXITS or h.startswith("KILL")


def disposition(trades: list[dict]) -> tuple[int, int, int]:
    """MT-G33 check 2 on every exit that was not a pre-set one: (exits, taken at a profit, taken at a loss)."""
    odd = [t for t in trades if str(t.get("exit_reason") or "").upper() not in PRESET_EXITS]
    h = [_f(t.get("honest_pnl")) for t in odd]
    return len(odd), sum(1 for v in h if v is not None and v > 0), sum(1 for v in h if v is not None and v < 0)


def volume_share(trades: list[dict], bars: dict[str, pd.DataFrame] | None) -> tuple[int, int] | None:
    """MT-G33 check 5: (entries in a top-decile volume minute, entries checked). A minute is top-decile when its
    SIP volume is at or above the 90th percentile of the same minute of day over the previous 20 sessions. None
    when no cached SIP bars cover the entries."""
    if not bars:
        return None
    hits = n = 0
    for t in trades:
        ts, sym = t.get("entry_ts"), str(t.get("symbol") or "")
        df = bars.get(sym)
        if not ts or df is None or df.empty:
            continue
        e = as_ny(ts).floor("min")
        if e not in df.index:
            continue
        same = df[(df.index.time == e.time()) & (df.index.date < e.date())]["volume"].tail(VOLUME_LOOKBACK)
        if len(same) < VOLUME_LOOKBACK:
            continue
        n += 1
        hits += int(float(df.loc[e, "volume"]) >= float(np.quantile(same.to_numpy(dtype=float), 0.9)))
    return (hits, n) if n else None


def bias_block(trades: list[dict], lines: list[dict] = (), bars: dict[str, pd.DataFrame] | None = None
               ) -> list[str]:
    odd = [t for t in trades if not _standard_exit(t.get("exit_reason"))]
    manual = [t for t in odd if str(t.get("exit_reason") or "").upper() in MANUAL_EXITS]
    size_bugs = size_checks(list(lines))
    n_disp, n_win, n_loss = disposition(trades)
    out = ["MT-G33 bias checks:",
           f"    exits that were not stop/target/time/flatten/daily stop/kill: {len(odd)} (must be 0)"
           + ("  <- BUG" if len(odd) > len(manual) else "")
           + (f"  <- {len(manual)} manual stop(s) (SIGTERM / shutdown mid-trade)" if manual else ""),
           f"    disposition of exits that were not a pre-set stop/target/time exit: {n_disp} exits, "
           + (f"{n_win} at a profit ({n_win / n_disp:.0%}), {n_loss} at a loss ({n_loss / n_disp:.0%})" if n_disp
              else "none (pass)"),
           f"    entries whose qty differs from the sizing function: {len(size_bugs)} (must be 0)"
           + ("  <- BUG: " + "; ".join(size_bugs[:5]) if size_bugs else "")]
    vs = volume_share(trades, bars)
    out.append("    entries in a top-decile volume minute (vs the same minute over 20 sessions, SIP): "
               + ("n/a (no cached SIP bars for 20 earlier sessions)" if vs is None else
                  f"{vs[0]} of {vs[1]} ({vs[0] / vs[1]:.0%})"
                  + ("  <- FLAG (above 20%)" if vs[0] / vs[1] > VOLUME_FLAG_SHARE else "")))
    by_day: dict[str, float] = defaultdict(float)
    count: Counter = Counter()
    for t in trades:
        by_day[_day(t)] += _f(t.get("honest_pnl")) or 0.0
        count[_day(t)] += 1
    days = sorted(by_day)
    after_red = [count[b] for a, b in zip(days, days[1:]) if by_day[a] < 0]
    after_green = [count[b] for a, b in zip(days, days[1:]) if by_day[a] > 0]
    msg = (f"    trades per day after red days {_num(np.mean(after_red) if after_red else None)} "
           f"({len(after_red)} days) vs after green days {_num(np.mean(after_green) if after_green else None)} "
           f"({len(after_green)} days)")
    if len(after_red) >= 20 and len(after_green) >= 20:
        a, b = np.mean(after_red), np.mean(after_green)
        if b > 0 and abs(a / b - 1) > 0.25:
            msg += "  <- FLAG (differs by more than 25%)"
    else:
        msg += " (flagged only once each group has 20 days)"
    out.append(msg)
    return out


def buckets_block(trades: list[dict], spy_bars: pd.DataFrame | None) -> list[str]:
    out = ["MT-G34 honest P&L by 15-minute entry bucket (vs doing nothing):"]
    b: dict[str, list[float]] = defaultdict(list)
    for t in trades:
        ts = t.get("entry_ts")
        h = _f(t.get("honest_pnl"))
        if ts and h is not None:
            e = as_ny(ts)
            b[f"{e.hour:02d}:{(e.minute // 15) * 15:02d}"].append(h)
    for k in sorted(b):
        out.append(f"    {k}  {len(b[k]):3d} trades  {_money(sum(b[k]))}")
    if not b:
        out.append("    no closed trades")
    if spy_bars is not None and not spy_bars.empty:
        g = spy_bars.groupby(spy_bars.index.date)
        o, c = g["open"].first(), g["close"].last()
        bh = float(c.iloc[-1] / o.iloc[0] - 1)
        oc = float((c / o - 1).mean())
        out.append(f"    SPY buy-and-hold {bh:+.2%} over {len(o)} sessions; SPY open-to-close {oc:+.3%} per day "
                   f"on average; cash 0.00%")
        em = exposure_matched_spy(trades, spy_bars)
        out.append("    exposure-matched SPY (same dollars, same minutes held): "
                   + ("n/a (no SPY bars at the trades' minutes)" if em is None else
                      f"{_money(em[0])} over {em[1]} trades"))
    else:
        out.append("    SPY benchmarks: no cached SIP bars for these dates (run the lab download); cash 0.00%")
    return out


def exposure_matched_spy(trades: list[dict], spy_bars: pd.DataFrame) -> tuple[float, int] | None:
    """MT-G34 / MT-G5: what the same dollars in SPY would have made over the same minutes: for each trade, buy
    notional x (SPY close of the exit minute / SPY open of the entry minute - 1). (dollars, trades counted)."""
    total, n = 0.0, 0
    for t in trades:
        a, b = t.get("entry_ts"), t.get("exit_ts")
        buys = t.get("buys") or []
        if not a or not b or not buys:
            continue
        ea, eb = as_ny(a).floor("min"), as_ny(b).floor("min")
        if ea not in spy_bars.index or eb not in spy_bars.index:
            continue
        notional = sum((_f(q) or 0.0) * (_f(p) or 0.0) for q, p in buys)
        total += notional * (float(spy_bars.loc[eb, "close"]) / float(spy_bars.loc[ea, "open"]) - 1.0)
        n += 1
    return (total, n) if n else None


def rejects_block(lines: list[dict]) -> list[str]:
    rej = Counter()
    per_setup: dict[str, Counter] = defaultdict(Counter)
    for x in lines:
        if x.get("kind") == "decision" and not x.get("accepted"):
            for r in x.get("reasons") or ["(no reason given)"]:
                rej[r] += 1
                per_setup[f"[{x.get('lane') or '?'}] {x.get('setup_id') or '?'}"][r] += 1
    out = [f"Rejected candidates: {sum(1 for x in lines if x.get('kind') == 'decision' and not x.get('accepted'))}"]
    for k, v in rej.most_common():
        out.append(f"    {k}: {v}")
    for s in sorted(per_setup):
        out.append(f"    {s}: " + ", ".join(f"{k} x{v}" for k, v in per_setup[s].most_common()))
    return out


def would_block(lines: list[dict]) -> list[str]:
    ws = [x for x in lines if x.get("kind") == "would_submit"]
    out = [f"Would have sent (dry run / replay): {len(ws)} orders"]
    for x in ws:
        out.append(f"    {str(x.get('ts', ''))[11:19]} [{x.get('lane') or '?'}] {x.get('setup_id') or '?'}: buy "
                   f"{x.get('qty', '?')} {x.get('symbol', '?')} at limit {x.get('limit', '?')}, stop "
                   f"{x.get('stop', '-')} (stop-limit {x.get('stop_limit', '-')}), target {x.get('target', '-')}")
    return out


_COSTS_DEFAULT = object()


def build_report(lines: list[dict], registry: C.Registry, *, changes: Iterable[dict] = (),
                 spy_bars: pd.DataFrame | None = None, title: str = "",
                 bars: dict[str, pd.DataFrame] | None = None, operating_costs: Any = _COSTS_DEFAULT) -> str:
    out = [f"Minute trader report {title}".rstrip(), EXPLORATORY_NOTE, ""]
    ch = list(changes)
    out.append(f"Changes log (MT-G41): {len(ch)} entries" + (":" if ch else ""))
    for c in ch:
        out.append(f"    {str(c.get('ts', ''))[:19]} {c.get('action')}: {c.get('reason')}")
    out.append("")
    trades = _trades(lines)
    fills = [x for x in lines if x.get("kind") == "fill"]
    index = TpIndex(lines)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for t in trades:
        groups[(str(t.get("setup_id") or "?"), str(t.get("lane") or "?"))].append(t)
    for r in registry.setups:
        groups.setdefault((r.setup_id, r.lane.value), [])
    run_feeds = {x.get("feed") for x in lines if x.get("setup_id") and x.get("kind") != "fill"} - {None}
    out += execution_block(lines, groups, registry, fills)
    out.append("")
    out.append("STRATEGY PERFORMANCE (honest net outcomes per setup version: MT-G11 sample, MT-G12 switch-off, MT-G13 "
               "drift)")
    for (sid, lane) in sorted(groups):
        reg = next((r for r in registry.setups if r.setup_id == sid), None)
        f = [x for x in fills if x.get("setup_id") == sid]
        # MT-G35: the feed each line says it ran on (a fill's `feed` is its quote's); a setup with no line of its
        # own takes the run's feed from the other setups' lines
        feeds = {x.get("feed") for x in lines if x.get("setup_id") == sid and x.get("kind") != "fill"} - {None} \
            or run_feeds
        out += setup_block(sid, lane, sorted(groups[(sid, lane)], key=lambda t: str(t.get("exit_ts") or "")), reg, f,
                           feeds, index)
    out.append("")
    if operating_costs is _COSTS_DEFAULT:
        try:
            operating_costs = load_operating_costs()
        except (OSError, ValueError):
            operating_costs = None
    out += operating_block(trades, lines, operating_costs)
    out.append("")
    out += bias_block(trades, lines, bars)
    out.append("")
    out += buckets_block(trades, spy_bars)
    out.append("")
    out += rejects_block(lines)
    out.append("")
    out += would_block(lines)
    return "\n".join(out)


# ------------------------------------------------------------------------------------------ broker cross-check
def broker_block(orders: Iterable[Any], lines: list[dict]) -> list[str]:
    """Paper mode: the broker's own SCALP- order history next to the journal (they must agree, MT-G26)."""
    from . import orders as O
    mine = [o for o in orders if O.parse_client_id(o.client_order_id) is not None]
    others = [o for o in orders if O.parse_client_id(o.client_order_id) is None]
    entries = [o for o in mine if O.parse_client_id(o.client_order_id)["leg"] == "E"]
    filled = [o for o in entries if (o.filled_qty or 0) > 0]
    sent = sum(1 for x in lines if x.get("kind") == "submit")
    out = ["Broker history (paper account, read-only):",
           f"    SCALP entry orders at the broker: {len(entries)} ({len(filled)} with a fill); journal 'submit' "
           f"lines: {sent}" + ("" if len(entries) == sent else "  <- DIFFERENT: check the journal and reconcile"),
           f"    other SCALP orders (exits, protects, kills, watchdog): {len(mine) - len(entries)}"]
    if others:
        out.append(f"    orders without a SCALP- id: {len(others)}  <- not the bot's (MT-G26)")
    return out


# ------------------------------------------------------------------------------------------ MT-G4 re-mark
def remark(lines: list[dict], quote_fn: Callable[[str, pd.Timestamp], Any], now: pd.Timestamp) -> list[str]:
    """Each fill older than 15 minutes against the SIP quote at its fill time. A buy above the SIP ask or a sell
    below the SIP bid is flagged: paper filled at a price the consolidated market did not show."""
    out = ["MT-G4 re-mark against historical SIP quotes:"]
    for x in lines:
        if x.get("kind") != "fill" or not x.get("ts"):
            continue
        ts = as_ny(x["ts"])
        if as_ny(now) - ts < pd.Timedelta(minutes=16):
            out.append(f"    {ts:%H:%M:%S} {x.get('symbol')}: too recent (SIP needs 16 minutes)")
            continue
        q = quote_fn(str(x.get("symbol")), ts)
        px = _f(x.get("price"))
        if q is None or px is None:
            out.append(f"    {ts:%H:%M:%S} {x.get('symbol')}: no SIP quote (PENDING_VERIFY)")
            continue
        side = str(x.get("side") or "")
        bad = (side == "buy" and px > q.ask + 1e-9) or (side == "sell" and px < q.bid - 1e-9)
        out.append(f"    {ts:%H:%M:%S} {side} {x.get('symbol')} @ {px:.2f}: SIP bid {q.bid:.2f} / ask {q.ask:.2f}"
                   + ("  <- better than the SIP quote (optimistic paper fill)" if bad else ""))
    return out


# ------------------------------------------------------------------------------------------ MT-G4 evening re-mark
REMARK_WINDOW_MIN = 2              # the fill minute and the next (the engine's live check, engine.TP_VERIFY_BARS)


def broker_take_profits(orders: Iterable[Any]) -> list[dict]:
    """Take-profit fills in the broker's SCALP history (read-only): one dict per entry parent whose take-profit leg
    filled, with what the re-mark needs. A fresh container has no journal, but the broker still has these."""
    from . import orders as O
    out = []
    for o in orders:
        p = O.parse_client_id(getattr(o, "client_order_id", ""))
        if p is None or p["leg"] != "E":
            continue
        for g in getattr(o, "legs", ()) or ():
            if g.order_type != "stop_limit" and (g.filled_qty or 0) > 0:
                out.append({"parent_cid": o.client_order_id, "tp_order_id": g.id, "symbol": o.symbol,
                            "setup_id": p["setup_id"], "tp_limit": g.limit_price,
                            "tp_filled_at": g.filled_at or g.updated_at, "pending_verify": True, SRC: "broker"})
    return out


def _pending_closes(lines: list[dict], index: TpIndex, unique_ids: bool, extra: Iterable[dict] = ()) -> list[dict]:
    """Take-profit closes not resolved yet, from the journal (trade_closed) and the broker (`extra`), one per trade."""
    fills = {(x.get(SRC), str(x.get("order_id"))): x for x in lines if x.get("kind") == "fill"}
    out, seen = [], set()
    for c in [x for x in lines if x.get("kind") == "trade_closed" and x.get("pending_verify")] + list(extra):
        if index.find(c, unique_ids) is not None:
            continue
        key = c.get("parent_cid") or (c.get(SRC), c.get("tp_order_id"))
        if key in seen:
            continue
        seen.add(key)
        f = fills.get((c.get(SRC), str(c.get("tp_order_id"))))
        limit = _f(c.get("tp_limit"))
        if limit is None and f is not None:
            limit = _f(f.get("price"))                 # a sell limit fills at or above its limit: the stricter test
        at_ = c.get("tp_filled_at") or (f or {}).get("ts") or c.get("ts")
        out.append({**c, "tp_limit": limit, "tp_filled_at": at_})
    return out


def remark_take_profits(pending: list[dict], trades_fn: Callable[[str, pd.Timestamp, pd.Timestamp], Any],
                        now: pd.Timestamp, write: Callable[..., None]) -> list[str]:
    """MT-G4: each PENDING_VERIFY take-profit older than 16 minutes against the historical SIP trades of its fill
    minute and the next. A trade strictly above the limit -> `tp_verified` (source SIP_REMARK: its R joins the
    series); none -> `tp_missed` (an honestly unfilled take-profit books 0: 0R in the series). No data -> it stays
    pending (nothing is guessed). `write(day, kind, **fields)` journals the verdict."""
    out = []
    for c in pending:
        sym, limit = str(c.get("symbol") or ""), _f(c.get("tp_limit"))
        try:
            at_ = as_ny(c.get("tp_filled_at"))
        except (TypeError, ValueError):
            at_ = None
        label = f"{c.get('setup_id')} {sym} take-profit {c.get('tp_order_id')} ({c.get('parent_cid') or '?'})"
        if at_ is None or limit is None:
            out.append(f"    {label}: no fill time or limit in the records: stays PENDING_VERIFY")
            continue
        start = at_.floor("min")
        end = start + pd.Timedelta(minutes=REMARK_WINDOW_MIN)
        if as_ny(now) - end < pd.Timedelta(minutes=16):
            out.append(f"    {label}: too recent (SIP needs 16 minutes): stays PENDING_VERIFY")
            continue
        prices = trades_fn(sym, start, end)
        if prices is None:
            out.append(f"    {label}: no SIP trades available: stays PENDING_VERIFY")
            continue
        top = max(prices) if prices else None
        fields = {"order_id": c.get("tp_order_id"), "parent_cid": c.get("parent_cid"), "src": c.get(SRC),
                  "symbol": sym, "limit": limit, "window_start": start, "window_end": end, "sip_trades": len(prices),
                  "sip_high": top, "source": "SIP_REMARK", "setup_id": c.get("setup_id"),
                  "version": c.get("version"), "lane": c.get("lane"), "feed": "SIP"}
        if top is not None and top > limit + 1e-9:
            write(at_.date(), "tp_verified", **fields)
            out.append(f"    {label}: VERIFIED (SIP traded {top:.2f} > limit {limit:.2f})")
        else:
            write(at_.date(), "tp_missed", **fields, r_honest=0.0,
                  note="MT-G4: no SIP trade strictly through the limit: a missed fill, booked at 0 P&L (0R)")
            out.append(f"    {label}: MISSED FILL (SIP high {'n/a' if top is None else f'{top:.2f}'} <= limit "
                       f"{limit:.2f}): counts 0R")
    return out


def remark_path(state_dir: str | Path, day: date, mode: str) -> Path:
    """journal/YYYY-MM-DD-<mode>-remark.jsonl: read back with that mode's journals (journal_files)."""
    return Path(state_dir) / "journal" / f"{day.isoformat()}-{mode}-remark.jsonl"


def resolve_take_profits(state_dir: str | Path, mode: str, trades_fn: Callable[..., Any], now: pd.Timestamp,
                         broker_orders: Iterable[Any] | None = None) -> list[str]:
    """MT-G4 evening re-mark for one mode: every take-profit still PENDING_VERIFY (from that mode's journals and, in
    paper, the broker's history) is resolved against historical SIP trades; verdicts go to that day's
    `<date>-<mode>-remark.jsonl`, which runner.lane_history and the report read back. Returns report lines."""
    lines = read_lines(journal_files(state_dir, mode=mode))
    unique = mode == "paper"
    index = TpIndex(lines)
    extra = broker_take_profits(broker_orders) if broker_orders is not None else []
    pending = _pending_closes(lines, index, unique, extra)
    out = [f"MT-G4 re-mark of {len(pending)} PENDING_VERIFY take-profit(s) ({mode}) against historical SIP trades:"]

    def write(day: date, kind: str, **fields: Any) -> None:
        J.FileJournal(remark_path(state_dir, day, mode), mode, lambda: as_ny(now)).write(kind, **fields)

    return out + remark_take_profits(pending, trades_fn, now, write)


# ------------------------------------------------------------------------------------------ files
def journal_files(state_dir: str | Path, day: date | None = None, since: date | None = None,
                  mode: str | None = None) -> list[Path]:
    files = []
    for p in sorted((Path(state_dir) / "journal").glob("*.jsonl")):
        try:
            d = date.fromisoformat(p.name[:10])
        except ValueError:
            continue
        if day is not None and d != day or since is not None and d < since:
            continue
        if mode is not None and p.stem[11:].split("-")[0] != mode:
            continue
        files.append(p)
    return files


def report(*, day: date | None = None, since: date | None = None, mode: str | None = None,
           state_dir: str | Path | None = None, quote_fn: Callable | None = None, broker: Any = None,
           trades_fn: Callable | None = None, now: pd.Timestamp | None = None,
           out: Callable[[str], None] = print) -> str:
    state_dir = Path(state_dir or C.STATE_DIR)
    now = as_ny(now) if now is not None else pd.Timestamp.now(tz="America/New_York")
    remarked: list[str] = []
    if trades_fn is not None:
        # MT-G4 evening re-mark FIRST, so the report (and the next start) read the resolved take-profits
        for m in ([mode] if mode else ["paper", "dry"]):
            orders = None
            if broker is not None and m == "paper":
                orders = broker.orders_since(now.normalize() - pd.Timedelta(days=RUNNER_LOOKBACK_DAYS))
            remarked += resolve_take_profits(state_dir, m, trades_fn, now, orders)
    files = journal_files(state_dir, day, since, mode)
    lines = read_lines(files)
    spy, bars = None, {}
    dates = sorted({str(x.get("ts", ""))[:10] for x in lines if x.get("ts")})
    if dates:
        first, last = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
        try:
            from .. import data as dt
            spy = dt.load_bars("SPY", first, last)
            for sym in C.ALLOWED_SYMBOLS:                # cached SIP only, for MT-G33 check 5 (nothing downloaded)
                bars[sym] = dt.load_bars(sym, first - timedelta(days=35), last)
        except (OSError, ValueError, KeyError):
            pass                                         # the checks that need bars say n/a
    title = f"({day or ('since ' + str(since) if since else 'all dates')}{', ' + mode if mode else ''}; " \
            f"{len(files)} journal files)"
    text = build_report(lines, C.load_registry(), changes=S.read_changes(state_dir), spy_bars=spy, title=title,
                        bars=bars or None)
    if broker is not None and dates:
        since_ts = as_ny(pd.Timestamp(dates[0]))
        text += "\n\n" + "\n".join(broker_block(broker.orders_since(since_ts), lines))
    if quote_fn is not None:
        text += "\n\n" + "\n".join(remark(lines, quote_fn, now))
    if remarked:
        text += "\n\n" + "\n".join(remarked)
    out(text)
    return text
