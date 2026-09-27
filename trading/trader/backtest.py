"""Rules-only backtester (rulebook phase 7, M-12 (i) and (iii)).

Replays each session with the live code path of the rules book, never Claude:
settle yesterday's orders at today's open (EX-4, next-open fills) with the EX-5 cost model -> mark to today's
close -> breakers (RISK-9..13, M-11) -> regime -> EX-7 data checks -> rules sleeve weights -> `build_plans` ->
`RiskEngine.apply` -> orders into a simulated broker. Lots, R and costs go through `ledger`; statistics come
from `metrics`. Signals only ever see bars dated on or before the session (each day gets a trailing `window`).

CLI (run from `trading/`):
    python -m trader.backtest --start 2017-01-01 --end 2026-09-25 [--set k=v ...] [--out path]
History comes from `AlpacaData.history` (market data only) and is cached under `<state dir>/cache/`.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import inspect
import json
import math
import pickle
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from . import ledger
from . import metrics
from .broker import SimBroker
from .config import STATE_DIR, Config, load_config
from .data import Bars, problem_symbols, validate
from .decisions import cap_weights
from .models import Target
from .regime import classify, classify_kwargs
from .risk import RiskEngine, breaker_status, loss_inputs, sleeves_to_latch
from .state import BookState, fingerprint

BOOK = "backtest"
SLEEVES = ("A", "B", "C", "D")
CLOSE_SYMBOLS = ("SPY", "IEF", "EFA", "DBC", "VNQ", "BIL")  # M-1 benchmark closes kept on every row
DATA_START = "2016-01-01"  # SIP daily history starts 2016-01-04
VALIDATE_TAIL = 20  # bars handed to the EX-7 checks (staleness and the last move need only the recent tail)


# --- overrides (M-12 iii) --------------------------------------------------------------------------------

# Policy keys where a larger number is looser (more risk, fewer checks). Matched on the dotted path.
_HIGHER_LOOSER = (
    "per_trade.risk_pct", "per_trade.stop_atr_multiple", "per_trade.max_stop_distance_pct",
    "per_trade.time_stop_days", "per_trade.trail_low_sessions",
    "portfolio.vol_target_annual", "portfolio.max_", "portfolio.correlated_positions.",
    "portfolio.cluster_heat.", "portfolio.sector_max_positions",
    "breakers.", "turnover.max_orders_per_day", "data_checks.",
)
# Policy keys where a smaller number is looser (less cash kept back, cheaper assumed trading).
_LOWER_LOOSER = ("portfolio.min_cash_buffer", "turnover.cost_model_per_side_bps")
# Policy keys that change trading frequency, not risk.
_NEUTRAL = ("turnover.rebalance_band", "turnover.min_order_notional")
# Playbook keys that raise risk when larger (RISK-8 caps are read from the sleeve bands; D-1 opt-in).
_PLAYBOOK_HIGHER_LOOSER = ("max", "default")


class OverrideError(ValueError):
    """An override names an unknown key or would loosen a risk limit without permission."""


def parse_overrides(items) -> dict[str, object]:
    """`["sleeves.B.rsi_entry=5", ...]` or a dict -> {dotted key: value}. Values are read as YAML scalars."""
    if items is None:
        return {}
    if isinstance(items, dict):
        return dict(items)
    out: dict[str, object] = {}
    for item in items:
        if "=" not in str(item):
            raise OverrideError(f"override {item!r} must look like key=value")
        key, raw = str(item).split("=", 1)
        out[key.strip()] = yaml.safe_load(raw.strip())
    return out


def _walk(root: dict, parts: list[str]):
    node = root
    for p in parts[:-1]:
        if not isinstance(node, dict) or p not in node:
            return None
        node = node[p]
    return node if isinstance(node, dict) and parts[-1] in node else None


def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _loosens(where: str, key: str, old, new) -> str | None:
    """Why this change loosens a limit, or None when it keeps or tightens it."""
    if old == new:
        return None
    if where == "playbook":
        parts = key.split(".")
        if parts[0] == "sleeves" and parts[-1] == "enabled" and bool(new) and not bool(old):
            return "turns a sleeve on (D-1 is the owner's call)"
        if parts[0] == "sleeves" and parts[-1] in _PLAYBOOK_HIGHER_LOOSER and _is_number(old) and _is_number(new) \
                and new > old:
            return "raises a sleeve weight cap (RISK-8)"
        return None
    if any(key.startswith(p) for p in _NEUTRAL) and _is_number(old) and _is_number(new):
        return None
    if not (_is_number(old) and _is_number(new)):
        return "changes a non-numeric risk setting"
    if any(key.startswith(p) for p in _LOWER_LOOSER):
        return "lowers a limit where lower is looser" if new < old else None
    if any(key.startswith(p) for p in _HIGHER_LOOSER):
        return "raises a limit where higher is looser" if new > old else None
    return "changes a risk setting whose safe direction is not known"


def apply_overrides(cfg: Config, overrides=None, *, allow_risk_changes: bool = False) -> Config:
    """A new Config with dotted-key overrides into the playbook or the risk policy (M-12 iii sensitivity).

    The first part of the key picks the file (a key present in both is ambiguous and refused; prefix it with
    `playbook.` or `policy.`). Overrides that loosen `risk_policy.yaml` limits (non-negotiable 1) are refused
    unless `allow_risk_changes=True`; unknown keys are refused so a typo never runs a silent baseline.
    """
    ov = parse_overrides(overrides)
    if not ov:
        return cfg
    playbook, policy = copy.deepcopy(cfg.playbook), copy.deepcopy(cfg.policy)
    for key, value in ov.items():
        parts = key.split(".")
        if parts[0] in ("playbook", "policy") and len(parts) > 1:
            where, parts = parts[0], parts[1:]
        else:
            in_pb, in_pol = _walk(playbook, parts) is not None, _walk(policy, parts) is not None
            if in_pb and in_pol:
                raise OverrideError(f"{key}: found in both files; write playbook.{key} or policy.{key}")
            where = "playbook" if in_pb else "policy" if in_pol else None
        root = playbook if where == "playbook" else policy
        node = _walk(root, parts) if where else None
        if node is None:
            raise OverrideError(f"{key}: no such setting in playbook.yaml or risk_policy.yaml")
        old = node[parts[-1]]
        why = _loosens(where, ".".join(parts), old, value)
        if why and not allow_risk_changes:
            raise OverrideError(f"{key}: {old!r} -> {value!r} {why}; pass allow_risk_changes=True "
                                "(--allow-risk-changes) to test it")
        node[parts[-1]] = value
    return Config(playbook=playbook, policy=policy)


def params_version(cfg: Config) -> str:
    """M-13: fingerprint of the parameter set actually used."""
    return fingerprint(json.dumps(cfg.playbook, sort_keys=True, default=str),
                       json.dumps(cfg.policy, sort_keys=True, default=str))


# --- result ------------------------------------------------------------------------------------------------


@dataclass
class BacktestResult:
    start: str
    end: str
    starting_cash: float
    equity: pd.Series  # equity at each session's close
    summary: dict  # book: cagr, total_return, vol, sharpe, max_drawdown, final_equity, days, years
    benchmarks: dict  # metrics.benchmarks over the same dates (SPY, 60/40, GTAA-5) plus CAGRs
    sleeve_stats: dict  # metrics.sleeve_stats per sleeve (M-2), net of costs
    exposure: dict  # average share of equity per sleeve (and cash)
    turnover: dict  # traded notional, annual turnover, costs
    trades: list[dict]  # closed lots (ledger records, without the event lists)
    fills: list[dict]
    latches: list[dict]  # halts and sleeve blocks with their dates
    yearly: dict  # calendar-year returns: book and SPY
    params: dict  # overrides and the parameter fingerprint (M-13)
    open_lots: dict
    pending_orders: int
    reconcile_events: int
    orders: list[dict] = field(default_factory=list)  # every order sent: {date (signal), symbol, side, qty, status}
    log: list[str] = field(default_factory=list)

    def to_dict(self, include_log: bool = False) -> dict:
        d = {k: getattr(self, k) for k in ("start", "end", "starting_cash", "summary", "benchmarks", "sleeve_stats",
                                           "exposure", "turnover", "latches", "yearly", "params", "open_lots",
                                           "pending_orders", "reconcile_events")}
        d["equity"] = {ts.date().isoformat(): round(float(v), 2) for ts, v in self.equity.items()}
        d["trades"] = self.trades
        d["n_fills"] = len(self.fills)
        d["n_orders"] = len(self.orders)
        if include_log:
            d["log"] = self.log
        return _json_safe(d)

    def headline(self) -> str:
        s, b = self.summary, self.benchmarks
        lines = [f"Backtest {self.start} to {self.end} (rules book, next-open fills, EX-5 costs; "
                 f"params {self.params.get('version')})"]
        lines.append(f"  Book: CAGR {_pct(s.get('cagr'))}, vol {_pct(s.get('vol'))}, Sharpe {s.get('sharpe')}, "
                     f"max drawdown {_pct(s.get('max_drawdown'))}, final equity ${s.get('final_equity'):,.0f}")
        for name, label in (("spy", "SPY"), ("sixty_forty", "60/40"), ("gtaa5", "GTAA-5")):
            x = b.get(name)
            if x:
                lines.append(f"  {label}: CAGR {_pct(x.get('cagr'))}, vol {_pct(x.get('vol'))}, "
                             f"Sharpe {x.get('sharpe')}, max drawdown {_pct(x.get('max_drawdown'))}")
        for sl, st in self.sleeve_stats.items():
            if st.get("n"):
                lines.append(f"  Sleeve {sl}: {st['n']} lots, win rate {_pct(st.get('win_rate'))}, E {st.get('E')}R, "
                             f"SQN {st.get('SQN')}, worst streak {st.get('max_losing_streak')}")
        ex = self.exposure
        lines.append("  Average exposure: " + ", ".join(f"{k} {_pct(v)}" for k, v in ex.items()))
        t = self.turnover
        lines.append(f"  Turnover {t.get('annual_turnover')}x a year, costs ${t.get('costs'):,.0f} "
                     f"({_pct(t.get('costs_pct_of_start'))} of starting cash), {t.get('fills')} fills")
        for la in self.latches:
            lines.append(f"  {la['date']}: {la['what']}")
        return "\n".join(lines)


def _pct(x) -> str:
    return "n/a" if x is None else f"{x:.2%}"


def _json_safe(x):
    if isinstance(x, dict):
        return {str(k): _json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_json_safe(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        v = float(x)
        return v if math.isfinite(v) else None
    if isinstance(x, (pd.Timestamp,)):
        return x.date().isoformat()
    return x


# --- the replay ---------------------------------------------------------------------------------------------


def _day_views(bars: Bars, dates: pd.DatetimeIndex, window: int):
    """For each session, {symbol: the trailing `window` bars dated on or before it}. Symbols with no bar yet
    are left out, so nothing after the session is ever visible (no look-ahead)."""
    frames = {s: df.sort_index() for s, df in bars.items() if df is not None and len(df)}
    ends = {s: df.index.searchsorted(dates, side="right") for s, df in frames.items()}
    for i, d in enumerate(dates):
        view = {}
        for s, df in frames.items():
            hi = int(ends[s][i])
            if hi > 0:
                view[s] = df.iloc[max(0, hi - window):hi]
        yield d, view


def _closes(view: Bars) -> dict[str, float]:
    """Last valid close per symbol (a stale symbol keeps its last close)."""
    out = {}
    for s, df in view.items():
        c = pd.to_numeric(df["close"], errors="coerce")
        c = c[c > 0]
        if len(c):
            out[s] = float(c.iloc[-1])
    return out


def _exposure(state: BookState, prices: dict[str, float], cfg: Config) -> dict[str, float]:
    """Notional per sleeve plus A_<SYM> for every A asset and A_cash (BIL), as the engine stores it (M-4)."""
    a = cfg.sleeves["A"]
    out = {s: 0.0 for s in SLEEVES}
    out.update({f"A_{s}": 0.0 for s in a["assets"]})
    out["A_cash"] = 0.0
    for sleeve, held in state.lots.items():
        for sym, lot in held.items():
            v = lot.qty * prices.get(sym, lot.entry_price)
            out[sleeve] = out.get(sleeve, 0.0) + v
            if sleeve == "A":
                key = "A_cash" if sym == a["cash"] else f"A_{sym}"
                out[key] = out.get(key, 0.0) + v
    return out


def _rules_weights(cfg: Config, view: Bars, promoted, demoted) -> dict[str, float]:
    """Rules weights (inverse vol in bands) bounded by `decisions.cap_weights`, as the engine does."""
    from . import engine
    fn = engine.rules_sleeve_weights
    params = inspect.signature(fn).parameters
    if "promoted" in params and "demoted" in params:
        return fn(cfg, view, promoted=promoted, demoted=demoted)
    return cap_weights(cfg, fn(cfg, view), promoted, demoted)


def _block_problem_increases(targets: list[Target], lots, blocked: set[str], log: list[str]) -> list[Target]:
    """EX-7: no increases in symbols with data problems (exits and holds go through)."""
    out = []
    for t in targets:
        lot = lots.get(t.sleeve, {}).get(t.symbol)
        cur = lot.qty if lot else 0.0
        if t.symbol in blocked and t.qty > cur + 1e-9:
            log.append(f"{t.sleeve}/{t.symbol}: increase blocked, data problem (EX-7)")
            t = Target(t.symbol, t.sleeve, cur, lot.stop if lot else t.stop, "hold: data problem (EX-7)")
        out.append(t)
    return out


class _Demotion:
    """M-11 from closed trades, recomputed only when the trade count changes (the bootstrap is not free)."""

    def __init__(self, policy: dict):
        self.policy, self.n, self.value = policy, -1, {}

    def __call__(self, trades: list[dict]) -> dict[str, str]:
        if len(trades) != self.n:
            self.n = len(trades)
            self.value = metrics.demotion(metrics.sleeve_stats(trades, policy=self.policy), self.policy)
        return self.value


def run_backtest(cfg: Config, bars: Bars, start, end=None, *, starting_cash: float = 100_000,
                 overrides=None, window: int = 900, allow_risk_changes: bool = False,
                 progress=None) -> BacktestResult:
    """Replay the rules book over the benchmark's sessions in [start, end]. Never calls Claude.

    Each session d: settle orders from d-1 at d's open (+ cost) -> account, reconcile, marks, equity row ->
    breakers (same functions and latches as the engine) -> regime -> data checks -> weights -> `build_plans`
    -> `RiskEngine.apply(book="rules")` -> orders queued for d+1's open. Orders still open after the last
    session are reported, not filled.
    """
    from . import engine
    base_cfg = cfg
    cfg = apply_overrides(cfg, overrides, allow_risk_changes=allow_risk_changes)
    bench = cfg.playbook["regime"]["benchmark"]
    if bench not in bars or bars[bench] is None or not len(bars[bench]):
        raise ValueError(f"no bars for the benchmark {bench}")
    spy_idx = pd.DatetimeIndex(bars[bench].sort_index().index)
    lo, hi = pd.Timestamp(start), pd.Timestamp(end) if end is not None else spy_idx[-1]
    dates = spy_idx[(spy_idx >= lo) & (spy_idx <= hi)]
    if len(dates) == 0:
        raise ValueError(f"no {bench} sessions between {lo.date()} and {hi.date()}")

    state = BookState(book=BOOK)
    state.sim = {"cash": float(starting_cash), "positions": {}}
    bps = ledger.cost_model(cfg, None)  # EX-5 policy model; fills already sit at the next open, so no gap charge
    risk = RiskEngine(cfg)
    rk = classify_kwargs(cfg.playbook["regime"])
    dc = cfg.policy.get("data_checks", {})
    demotion_of = _Demotion(cfg.policy)
    universe, canaries = cfg.stock_universe(), cfg.playbook["regime"]["canaries"]
    min_notional = cfg.policy["turnover"].get("min_order_notional", 25)
    log: list[str] = []
    latches: list[dict] = []
    orders: list[dict] = []

    for n, (d, view) in enumerate(_day_views(bars, dates, window)):
        day = d.date().isoformat()
        day_log: list[str] = []
        prices = _closes(view)
        broker = SimBroker(state.sim, prices, bps, cfg.asset_class, bars=view, fill_mode="next_open",
                           cost_in_price=False)

        # 1. Settle yesterday's orders at today's open; what cannot fill today is cancelled (DAY orders).
        if state.pending_orders:
            ledger.settle_fills(state, broker.order_fills(state.pending_orders), date=day,
                                asset_class=cfg.asset_class, cost_bps=bps, log=day_log)
            broker.cancel_open_orders()
            ledger.settle_fills(state, broker.order_fills(state.pending_orders), date=day,
                                asset_class=cfg.asset_class, cost_bps=bps, log=day_log)

        # 2-3. Account, reconcile, marks, equity row.
        equity, _cash = broker.account()
        positions = broker.positions()
        ledger.reconcile(state.lots, positions, day_log, state=state, prices=prices, date=day,
                         skip_symbols=ledger.pending_symbols(state))
        ledger.update_marks(state, view, day, log=day_log)
        closes = {s: prices[s] for s in CLOSE_SYMBOLS if s in prices}
        day_pnl, week_pnl = state.record_equity(day, equity, prices.get(bench, 0.0), closes=closes,
                                                exposure=_exposure(state, prices, cfg))

        # 4. Breakers, with the engine's latches (RISK-9 halt, RISK-13 sleeve blocks, M-11 "stop").
        demotion = demotion_of(state.closed_trades)
        for s, why in sleeves_to_latch(cfg, equity, state.sleeve_pnl).items():
            if s not in state.sleeve_blocked:
                state.sleeve_blocked[s] = why
                latches.append({"date": day, "what": f"sleeve {s} blocked: {why}"})
        for s, level in demotion.items():
            if level == "stop" and s not in state.sleeve_blocked:
                state.sleeve_blocked[s] = f"M-11 demotion ({level})"
                latches.append({"date": day, "what": f"sleeve {s} blocked: M-11 demotion"})
        breakers = breaker_status(cfg, equity, state.peak_equity, day_pnl, week_pnl, state.halted, False,
                                  **loss_inputs(state.equity_history, day, equity), sleeve_pnl=state.sleeve_pnl,
                                  sleeve_blocked=state.sleeve_blocked, demotion=demotion)
        if breakers.halted and not state.halted:
            state.halted = True
            latches.append({"date": day, "what": f"book halted (RISK-9): drawdown {breakers.drawdown:.1%}"})
        row = state.equity_history[-1]
        row["sleeve_cum"] = {s: round(r.get("cum", 0.0), 2) for s, r in state.sleeve_pnl.items()}
        row["halted"] = state.halted

        # 5-8. Regime, data checks, weights, plans.
        regime = classify(view, bench, universe, canaries, **rk)
        tails = {s: df.iloc[-VALIDATE_TAIL:] for s, df in view.items()}  # EX-7 reads only the last bars
        problems = validate(tails, cfg.allowlist(), d, max_stale_days=dc.get("max_stale_days", 5),
                            max_daily_move=dc.get("max_daily_move", 0.25))
        weights = _rules_weights(cfg, view, tuple(state.promoted_sleeves), demotion)
        plans = engine.build_plans(cfg, view, state.lots, weights, equity, regime, d)
        proposed = [t for p in plans.values() for t in p.targets.values()]
        proposed = _block_problem_increases(proposed, state.lots, problem_symbols(problems), day_log)

        # 12-13. Risk, orders (queued for the next open), ledger.
        result = risk.apply(proposed, state.lots, positions, view, equity, breakers,
                            permissions=regime.permissions, weights=weights,
                            promoted=tuple(state.promoted_sleeves), book="rules")
        day_log += result.log
        submitted = broker.submit(result.orders, f"bt{day.replace('-', '')}", date=day, suffix="") \
            if result.orders else []
        ledger.record_orders(state, result.targets, result.orders, submitted, prices, day,
                             asset_class=cfg.asset_class, cost_bps=bps, tags={"book": BOOK, "mode": "rules"},
                             log=day_log, min_notional=min_notional)
        orders += [{"date": day, "symbol": o.symbol, "side": o.side, "qty": round(o.qty, 6),
                    "status": r.get("status")} for o, r in zip(result.orders, submitted)]
        state.last_run_date = day
        log += [f"{day} {line}" for line in day_log]
        if progress and (n % 250 == 0 or n == len(dates) - 1):
            progress(f"{day}: equity ${equity:,.0f} ({n + 1}/{len(dates)} sessions)")

    return _result(cfg, base_cfg, state, dates, float(starting_cash), overrides, allow_risk_changes, latches, log,
                   orders)


# --- results ------------------------------------------------------------------------------------------------


def _cagr(values: pd.Series) -> float | None:
    v = pd.to_numeric(values, errors="coerce").dropna()
    v = v[v > 0]
    if len(v) < 2:
        return None
    years = (v.index[-1] - v.index[0]).days / 365.25
    return float((v.iloc[-1] / v.iloc[0]) ** (1 / years) - 1) if years > 0 else None


def _yearly(series: pd.Series) -> dict[str, float]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return {}
    ends = s.groupby(s.index.year).last()
    starts = s.groupby(s.index.year).first()
    prev = ends.shift(1)
    base = prev.fillna(starts)
    return {str(y): round(float(ends[y] / base[y] - 1), 4) for y in ends.index}


def _result(cfg, base_cfg, state, dates, starting_cash, overrides, allow_risk_changes, latches, log, orders):
    frame = metrics.history_frame(state.equity_history)
    equity = frame["equity"]
    bench = metrics.benchmarks(state.equity_history)
    book = dict(bench.get("book") or {})
    book.update({"cagr": _cagr(equity), "final_equity": round(float(equity.iloc[-1]), 2),
                 "total_return": book.get("return"),
                 "years": round((equity.index[-1] - equity.index[0]).days / 365.25, 2)})
    paths = metrics.benchmark_paths(frame)
    bm = {}
    for name in ("spy", "sixty_forty", "gtaa5"):
        x = bench.get(name)
        bm[name] = dict(x, cagr=_cagr(paths[name])) if x and paths.get(name) is not None else None
    bm["book_same_dates"] = bench.get("book_same_dates")
    bm["note"] = ("Benchmarks use the same adjusted closes the backtest trades on (dividends included when the "
                  "feed adjusts for them); no costs.")

    eq = equity.to_numpy(dtype=float)
    xs = {s: frame.get(f"x_{s}") for s in SLEEVES}
    exposure = {s: round(float(np.nanmean(x.to_numpy(dtype=float) / eq)), 4) for s, x in xs.items() if x is not None}
    exposure["cash"] = round(1.0 - sum(exposure.values()), 4)

    fills = state.fills
    traded = sum(abs(f.get("qty", 0.0) * f.get("fill", 0.0)) for f in fills)
    costs = sum(f.get("cost", 0.0) for f in fills)
    years = max(book["years"], 1 / 252)
    turnover = {"traded_notional": round(traded, 2), "annual_turnover": round(traded / float(np.mean(eq)) / years, 2),
                "costs": round(costs, 2), "costs_pct_of_start": round(costs / starting_cash, 4),
                "costs_bps_per_year_of_equity": round(costs / float(np.mean(eq)) / years * 1e4, 1),
                "fills": len(fills), "cost_model_bps": ledger.cost_model(cfg, None)}

    ov = parse_overrides(overrides)
    trades = [{k: v for k, v in t.items() if k != "events"} for t in state.closed_trades]
    open_lots = {s: {sym: {"qty": round(lot.qty, 6), "entry_date": lot.entry_date,
                           "entry_price": round(lot.entry_price, 4), "stop": lot.stop} for sym, lot in h.items()}
                 for s, h in state.lots.items() if h}
    events = [e for t in state.closed_trades for e in t.get("events", [])]
    events += [e for h in state.lots.values() for lot in h.values() for e in lot.events]
    recon = sum(1 for e in events if e.get("reason") == ledger.RECONCILE)  # sim and ledger should agree: 0
    return BacktestResult(
        start=dates[0].date().isoformat(), end=dates[-1].date().isoformat(), starting_cash=starting_cash,
        equity=equity, summary=book, benchmarks=bm,
        sleeve_stats=metrics.sleeve_stats(state.closed_trades, policy=cfg.policy),
        exposure=exposure, turnover=turnover, trades=trades, fills=list(fills), latches=latches,
        yearly={"book": _yearly(equity), "spy": _yearly(frame["c_SPY"]) if "c_SPY" in frame else {}},
        params={"overrides": {k: v for k, v in ov.items()}, "allow_risk_changes": allow_risk_changes,
                "version": params_version(cfg), "baseline_version": params_version(base_cfg)},
        open_lots=open_lots, pending_orders=len(state.pending_orders), reconcile_events=recon, orders=orders,
        log=log)


# --- CLI ----------------------------------------------------------------------------------------------------


def _cache_path(cache_dir: Path, symbols: list[str], start: str, end: str, feed: str) -> Path:
    key = hashlib.sha256(json.dumps([sorted(symbols), start, end, feed]).encode()).hexdigest()[:12]
    return cache_dir / f"bars_{start}_{end}_{feed}_{key}.pkl"


def load_history(cfg: Config, start: str, end: str, *, cache_dir: Path | None = None, data=None,
                 refresh: bool = False, say=print) -> Bars:
    """History of `cfg.data_symbols()` from `start` to `end`, cached as a pickle (never committed)."""
    cache_dir = Path(cache_dir or STATE_DIR / "cache")
    feed = (cfg.playbook.get("data") or {}).get("feed") or "sip"
    symbols = cfg.data_symbols()
    path = _cache_path(cache_dir, symbols, start, end, feed)
    if path.exists() and not refresh:
        with open(path, "rb") as f:
            say(f"Using cached bars from {path}")
            return pickle.load(f)
    if data is None:
        from .data import AlpacaData
        data = AlpacaData.from_env(cfg)
    say(f"Fetching daily bars for {len(symbols)} symbols, {start} to {end} ...")
    bars = data.history(symbols, start, end)
    for note in getattr(data, "notes", []) or []:
        say(f"  data: {note}")
    if getattr(data, "feed_used", None):
        say(f"  feed used: {data.feed_used}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(bars, f)
    return bars


def main(argv=None, *, data=None) -> int:
    p = argparse.ArgumentParser(prog="python -m trader.backtest",
                                description="Replay the rules book (never Claude) with next-open fills and costs.")
    p.add_argument("--start", default="2017-01-01")
    p.add_argument("--end", default=None, help="last session (default: the latest bar)")
    p.add_argument("--set", dest="overrides", action="append", default=[], metavar="KEY=VALUE",
                   help="override a playbook/policy setting, e.g. sleeves.B.rsi_entry=5 (repeatable)")
    p.add_argument("--allow-risk-changes", action="store_true", help="allow overrides that loosen risk limits")
    p.add_argument("--cash", type=float, default=None, help="starting cash (default: playbook simulation)")
    p.add_argument("--window", type=int, default=900, help="trailing sessions each day sees")
    p.add_argument("--out", default=None, help="write the full result as JSON here")
    p.add_argument("--refresh", action="store_true", help="ignore the bar cache")
    a = p.parse_args(argv)
    cfg = load_config()
    try:
        apply_overrides(cfg, a.overrides, allow_risk_changes=a.allow_risk_changes)
    except OverrideError as e:
        print(f"Refused: {e}")
        return 2
    end = a.end or pd.Timestamp.now(tz="America/New_York").date().isoformat()
    fetch_start = max(pd.Timestamp(DATA_START), pd.Timestamp(a.start) - pd.Timedelta(days=int(a.window * 1.5)))
    bars = load_history(cfg, fetch_start.date().isoformat(), end, data=data, refresh=a.refresh)
    cash = a.cash or float(cfg.playbook.get("simulation", {}).get("starting_cash", 100_000))
    res = run_backtest(cfg, bars, a.start, a.end, starting_cash=cash, overrides=a.overrides, window=a.window,
                       allow_risk_changes=a.allow_risk_changes, progress=print)
    print(res.headline())
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(res.to_dict(), indent=1, default=str))
        print(f"Full result written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
