"""Deterministic risk engine. Nothing an LLM says can get past this file.

Input: per-sleeve targets from the rules or from Claude.
Output: the targets that survive the policy, the orders that get there, and a
log of every rejection or clip with its reason.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import Config
from .data import Bars
from .models import Lot, Order, Target

STOPPED_SLEEVES = ("B", "C", "D")


@dataclass
class Breakers:
    drawdown: float
    halted: bool
    no_new_entries: bool
    risk_mult: float
    day_pnl_R: float
    week_pnl_R: float
    reasons: list[str] = field(default_factory=list)


def breaker_status(cfg: Config, equity: float, peak: float, day_pnl: float, week_pnl: float,
                   halted_flag: bool, kill_switch: bool) -> Breakers:
    b = cfg.policy["breakers"]
    one_r = cfg.policy["per_trade"]["risk_pct_default"] * equity
    dd = 0.0 if peak <= 0 else max(0.0, 1.0 - equity / peak)
    reasons = []
    halted = halted_flag or kill_switch or dd >= b["drawdown_halt"]
    if kill_switch:
        reasons.append("kill switch is on")
    if halted_flag:
        reasons.append("book halted, needs a human to re-enable")
    if dd >= b["drawdown_halt"]:
        reasons.append(f"drawdown {dd:.1%} >= {b['drawdown_halt']:.0%}: halt, exits only")
    no_new = halted or dd >= b["drawdown_no_new_entries"]
    if dd >= b["drawdown_no_new_entries"] and not halted:
        reasons.append(f"drawdown {dd:.1%}: no new entries")
    day_r, week_r = day_pnl / one_r, week_pnl / one_r
    if day_r <= -b["daily_loss_R"]:
        no_new = True
        reasons.append(f"daily loss {day_r:.1f}R: no new entries today")
    if week_r <= -b["weekly_loss_R"]:
        no_new = True
        reasons.append(f"weekly loss {week_r:.1f}R: no new entries this week")
    risk_mult = 0.5 if dd >= b["drawdown_halve_risk"] else 1.0
    if risk_mult < 1 and not no_new:
        reasons.append(f"drawdown {dd:.1%}: risk per trade halved")
    return Breakers(dd, halted, no_new, risk_mult, day_r, week_r, reasons)


@dataclass
class RiskResult:
    targets: list[Target]
    orders: list[Order]
    log: list[str]


class RiskEngine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.p = cfg.policy

    def apply(self, proposed: list[Target], lots: dict[str, dict[str, Lot]], broker_qty: dict[str, float],
              bars: Bars, equity: float, breakers: Breakers) -> RiskResult:
        p, cfg = self.p, self.cfg
        log: list[str] = list(breakers.reasons)
        prices = {s: float(df["close"].iloc[-1]) for s, df in bars.items() if len(df)}
        allow = set(cfg.allowlist())

        # Start from current holdings; every proposal is a change against them.
        final: dict[tuple[str, str], Target] = {}
        for sleeve, held in lots.items():
            for sym, lot in held.items():
                final[(sleeve, sym)] = Target(sym, sleeve, lot.qty, lot.stop, "unchanged")

        # 1. Stops are enforced on every held lot, whoever is deciding.
        for (sleeve, sym), t in final.items():
            if t.stop is not None and sym in prices and prices[sym] <= t.stop and t.qty > 0:
                final[(sleeve, sym)] = Target(sym, sleeve, 0.0, t.stop, "stop hit (enforced)")
                log.append(f"{sleeve}/{sym}: close {prices[sym]:.2f} <= stop {t.stop:.2f}, exit enforced")
        stopped_out = {k for k, t in final.items() if t.reason == "stop hit (enforced)"}

        # 2. Reductions first (always allowed), then increases in sleeve order.
        def delta(t: Target) -> float:
            cur = final.get((t.sleeve, t.symbol))
            return t.qty - (cur.qty if cur else 0.0)

        ordered = sorted(proposed, key=lambda t: (delta(t) > 0, t.sleeve))
        for t in ordered:
            key = (t.sleeve, t.symbol)
            cur = final.get(key)
            cur_qty = cur.qty if cur else 0.0
            cur_lot = lots.get(t.sleeve, {}).get(t.symbol)
            if key in stopped_out:
                continue
            if t.symbol not in allow:
                log.append(f"{t.sleeve}/{t.symbol}: rejected, not on the allowlist")
                continue
            if t.symbol not in prices:
                log.append(f"{t.sleeve}/{t.symbol}: rejected, no price")
                continue
            price = prices[t.symbol]
            qty = max(0.0, t.qty)  # long only
            stop = t.stop
            if cur and cur.stop is not None and p["per_trade"]["never_widen_stop"]:
                stop = cur.stop if stop is None else max(stop, cur.stop)

            if qty <= cur_qty:
                final[key] = Target(t.symbol, t.sleeve, qty, stop, t.reason)
                continue

            # --- increases ---
            if breakers.no_new_entries:
                log.append(f"{t.sleeve}/{t.symbol}: increase rejected ({'; '.join(breakers.reasons)})")
                if cur:
                    final[key] = Target(t.symbol, t.sleeve, cur_qty, stop, cur.reason)
                continue
            if t.sleeve in STOPPED_SLEEVES:
                if (p["per_trade"]["no_averaging_down"] and cur_lot and cur_lot.qty > 0
                        and price < cur_lot.entry_price):
                    log.append(f"{t.sleeve}/{t.symbol}: rejected, no averaging down")
                    continue
                if stop is None or stop >= price:
                    stop = self._default_stop(t.sleeve, t.symbol, bars, price)
                    log.append(f"{t.sleeve}/{t.symbol}: missing or invalid stop, set to {stop:.2f}")
                per_share = price - stop
                risk_pct = min(p["per_trade"]["risk_pct_default"] * breakers.risk_mult,
                               p["per_trade"]["risk_pct_hard_cap"])
                cap = risk_pct * equity / per_share
                if qty > cap:
                    log.append(f"{t.sleeve}/{t.symbol}: qty {qty:.4f} clipped to {cap:.4f} by per-trade risk")
                    qty = cap
            elif breakers.risk_mult < 1:
                qty = cur_qty + (qty - cur_qty) * breakers.risk_mult

            qty = self._clip_portfolio(t, qty, cur_qty, stop, price, final, prices, equity, bars, log)
            if qty <= cur_qty + 1e-9:
                if cur:
                    final[key] = Target(t.symbol, t.sleeve, cur_qty, stop, cur.reason)
                continue
            final[key] = Target(t.symbol, t.sleeve, qty, stop, t.reason)

        for sym in untracked_symbols(broker_qty, lots):
            log.append(f"{sym}: held at the broker but not opened by this book, left untouched")
        targets = [t for t in final.values() if t.qty > 0 or (t.sleeve in lots and t.symbol in lots[t.sleeve])]
        orders, dropped = self._orders(targets, broker_qty, prices, log)
        for t in targets:
            if t.symbol in dropped:
                lot = lots.get(t.sleeve, {}).get(t.symbol)
                t.qty, t.reason = (lot.qty if lot else 0.0), "order dropped by daily cap"
        return RiskResult(targets, orders, log)

    # --- helpers ---------------------------------------------------------------------------

    def _default_stop(self, sleeve: str, sym: str, bars: Bars, price: float) -> float:
        from .indicators import atr

        k = self.p["per_trade"]["stop_atr_multiple"].get(sleeve, 3.0)
        a = float(atr(bars[sym], self.p["per_trade"]["atr_period"]).iloc[-1])
        stop = price - k * a
        max_dist = self.p["per_trade"].get("max_stop_distance_pct", {}).get(sleeve)
        if max_dist:
            stop = max(stop, price * (1 - max_dist))
        return stop

    def _clip_portfolio(self, t: Target, qty: float, cur_qty: float, stop: float | None, price: float,
                        final: dict, prices: dict, equity: float, bars: Bars, log: list[str]) -> float:
        pf = self.p["portfolio"]
        others = [o for k, o in final.items() if k != (t.sleeve, t.symbol) and o.qty > 0]

        # Per-symbol notional cap, summed across sleeves.
        cls = self.cfg.asset_class(t.symbol)
        cap_pct = {"etf": pf["max_single_etf_notional"], "stock": pf["max_single_stock_notional"],
                   "crypto": pf["max_single_crypto_notional"]}[cls]
        same_sym = sum(o.qty for o in others if o.symbol == t.symbol) * price
        room = cap_pct * equity - same_sym
        if qty * price > room:
            new = max(cur_qty, room / price)
            log.append(f"{t.sleeve}/{t.symbol}: clipped to {cap_pct:.0%} {cls} notional cap")
            qty = new

        # Cash buffer on gross exposure.
        gross_others = sum(o.qty * prices.get(o.symbol, 0.0) for o in others)
        room = (1 - pf["min_cash_buffer"]) * equity - gross_others
        if qty * price > room:
            log.append(f"{t.sleeve}/{t.symbol}: clipped by {pf['min_cash_buffer']:.0%} cash buffer")
            qty = max(cur_qty, room / price)

        # Open-risk heat across stopped positions.
        if stop is not None:
            heat_others = sum(max(0.0, prices.get(o.symbol, 0.0) - o.stop) * o.qty
                              for o in others if o.stop is not None)
            room = pf["max_open_risk_heat"] * equity - heat_others
            if (price - stop) * qty > room:
                log.append(f"{t.sleeve}/{t.symbol}: clipped by {pf['max_open_risk_heat']:.0%} open-risk heat")
                qty = max(cur_qty, room / (price - stop))

        # Correlation: at most N highly correlated stock positions.
        if cls == "stock" and cur_qty == 0:
            corr = pf["correlated_positions"]
            rets = bars[t.symbol]["close"].pct_change().iloc[-60:]
            n = 0
            for o in others:
                if self.cfg.asset_class(o.symbol) == "stock" and o.symbol in bars:
                    other = bars[o.symbol]["close"].pct_change().iloc[-60:]
                    rho = rets.corr(other)
                    if not np.isnan(rho) and rho > corr["rho_60d"]:
                        n += 1
            if n >= corr["max_count"]:
                log.append(f"{t.sleeve}/{t.symbol}: rejected, {n} held stocks with 60d correlation > {corr['rho_60d']}")
                return cur_qty
        return max(qty, cur_qty)

    def _orders(self, targets: list[Target], broker_qty: dict[str, float], prices: dict,
                log: list[str]) -> tuple[list[Order], set[str]]:
        t_cfg = self.p["turnover"]
        want: dict[str, float] = {}
        reasons: dict[str, list[str]] = {}
        for t in targets:
            want[t.symbol] = want.get(t.symbol, 0.0) + t.qty
            if t.reason and t.reason not in ("hold", "unchanged"):
                reasons.setdefault(t.symbol, []).append(f"{t.sleeve}: {t.reason}")
        orders = []
        for sym, qty in want.items():
            have = broker_qty.get(sym, 0.0)
            diff = qty - have
            price = prices.get(sym)
            if price is None or abs(diff) * price < t_cfg["min_order_notional"]:
                continue
            if diff < 0:
                diff = -min(-diff, have)  # never sell more than held: no shorts
            orders.append(Order(sym, "buy" if diff > 0 else "sell", round(abs(diff), 6), price,
                                "; ".join(reasons.get(sym, []))))
        orders.sort(key=lambda o: o.side != "sell")
        sells = [o for o in orders if o.side == "sell"]
        buys = [o for o in orders if o.side == "buy"]
        room = max(0, t_cfg["max_orders_per_day"] - len(sells))
        if len(buys) > room:
            log.append(f"order cap: {len(buys) - room} buy order(s) dropped (max {t_cfg['max_orders_per_day']}/day)")
        return sells + buys[:room], {o.symbol for o in buys[room:]}


def untracked_symbols(broker_qty: dict[str, float], lots: dict[str, dict[str, Lot]]) -> list[str]:
    tracked = {s for held in lots.values() for s in held}
    return [s for s, q in broker_qty.items() if q > 0 and s not in tracked]


def as_frame(targets: list[Target]) -> pd.DataFrame:
    return pd.DataFrame([t.__dict__ for t in targets])
