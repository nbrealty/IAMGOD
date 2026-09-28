"""Sample, switch-off and drift gates on a setup version's closed trades (MT-G11, MT-G12, MT-G13).

All three read R multiples of HONEST P&L per closed trade (MT-G4), oldest first. They only ever remove risk: a
good-looking result below the minimum sample is "INSUFFICIENT SAMPLE" and changes nothing, while bad news acts
from 30 trades.

- MT-G11 `sample_label`: fewer than 100 closed trades or 40 sessions -> "INSUFFICIENT SAMPLE".
- MT-G12 `switch_off`: n >= 100 and mean <= 0 -> RETIRED; n >= 30 and the one-sided 90% bootstrap upper bound of
  the mean < 0 -> SHADOW. Seeded, so the same trades always give the same answer. Honest limit: at n = 30 it
  only catches clearly bad setups (true mean about -0.4R or worse).
- MT-G13 `cusum_trip`: one-sided lower CUSUM of net R against the backtest mean. With the baseline mu0, the
  shift to detect `shift_r` (default 0.4R: +0.2R -> -0.2R) and the R standard deviation `sd_r` (default 1R, the
  report's calibration; None = the sample SD of the trades given):
      S_0 = 0,  S_t = max(0, S_{t-1} + (mu0 - x_t)/sd - k),  k = 0.5 x |shift_r| / sd
  and it trips when S_t > h (h = 10, in SD units) at any trade t from 30 on. The report's simulation (4,000
  runs, sd 1R) put this at about 7% false trips over trades 30-100 for a +0.2R setup, catching a -0.2R setup
  within 90 trades about 94% of the time; tests re-check both with seeds. Inactive (False) below 30 trades or
  without a baseline. The win-rate trigger needs the backtest's win rate and is inactive without it too; the
  slippage trigger (median of the last 30 fills > 2 x the model) runs whenever a model is registered.
- MT-G3 `slippage_raise_trip`: median slippage over >= 30 fills > 1.5 x the model -> shadow.
- `lane_check` runs all of them for one setup version (the engine calls it at startup and after every closed
  trade) and returns the lane to demote to (RETIRED beats SHADOW) with the reasons.
- `lane_check_pending` is what the engine and the report call: `lane_check` on the RESOLVED series (verified trades
  at their honest R, MT-G4 missed fills at 0R) and, while take-profits are still PENDING_VERIFY, the same check with
  every pending take-profit added at its GATE value (min(R, 0): the missed-fill outcome). It demotes when either
  view trips (RETIRED beats SHADOW): an unverified win is never counted at its paper R, and a pending take-profit is
  counted at its gate value only when that makes the decision more conservative. The choice is deliberate: while
  anything is pending the decision is taken on the pessimistic side (it may hold a winning setup in shadow for the
  rest of a run), and the MT-G4 SIP re-mark (at every start and `report --remark`) resolves each pending
  take-profit within a day, after which the series is exactly the honest one (no one-sided exclusion of wins).
v1 registers no backtest baseline in R (the backtest has no R for the live bracket), so the CUSUM and win-rate
triggers are OFF and the runner journals that at every start (`mt_g13_cusum_off`).
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

from . import config as C
from .model import Lane

INSUFFICIENT = "INSUFFICIENT SAMPLE"
OK = "OK"
BOOT = 2000
CONF = 0.90
CUSUM_SHIFT_R = 0.4
CUSUM_H = 10.0


def sample_label(n_trades: int, n_sessions: int) -> str:
    return OK if n_trades >= C.MIN_SAMPLE_TRADES and n_sessions >= C.MIN_SAMPLE_SESSIONS else INSUFFICIENT


def sample_ok(n_trades: int, n_sessions: int) -> bool:
    """MT-G11 part of any promotion: never True below the minimum sample (other gates still apply)."""
    return sample_label(n_trades, n_sessions) == OK


def bootstrap_upper(r_values: Sequence[float], seed: int = 0, boot: int = BOOT, conf: float = CONF) -> float:
    """One-sided upper bound of the mean: the `conf` quantile of `boot` resampled means."""
    x = np.asarray(r_values, dtype=float)
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), size=(boot, len(x)))].mean(axis=1)
    return float(np.quantile(means, conf))


def switch_off(r_values: Sequence[float], seed: int = 0, boot: int = BOOT) -> Lane | None:
    """MT-G12 after a closed trade: RETIRED, SHADOW or None (keep going)."""
    x = np.asarray(r_values, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n >= C.RETIRE_N and x.mean() <= 0:
        return Lane.RETIRED
    # an upper bound below 0 needs a sample mean below 0, so a non-negative mean skips the bootstrap
    if n >= C.SWITCH_OFF_N and x.mean() < 0 and bootstrap_upper(x, seed, boot) < 0:
        return Lane.SHADOW
    return None


def cusum_path(r_values: Sequence[float], baseline_mean: float, shift_r: float = CUSUM_SHIFT_R,
               sd_r: float | None = 1.0) -> np.ndarray:
    """S_t for t = 1..n (see the module docstring)."""
    x = np.asarray(r_values, dtype=float)
    sd = float(np.std(x, ddof=1)) if sd_r is None and len(x) > 1 else float(sd_r or 1.0)
    sd = max(sd, 1e-6)
    k = 0.5 * abs(shift_r) / sd
    s, out = 0.0, np.empty(len(x))
    for i, v in enumerate(x):
        s = max(0.0, s + (baseline_mean - v) / sd - k)
        out[i] = s
    return out


def cusum_trip(r_values: Sequence[float], baseline_mean: float | None, shift_r: float = CUSUM_SHIFT_R,
               h: float = CUSUM_H, sd_r: float | None = 1.0, min_n: int = C.SWITCH_OFF_N) -> bool:
    """MT-G13: True = live has drifted below the backtest; the setup goes to shadow."""
    if baseline_mean is None or len(r_values) < min_n:
        return False
    s = cusum_path(r_values, baseline_mean, shift_r, sd_r)
    return bool((s[min_n - 1:] > h).any())


WINRATE_WINDOW = 30
WINRATE_DROP = 0.15
SLIP_WINDOW = 30
SLIP_STOP_X_MODEL = C.SLIP_MODEL_STOP_X


def winrate_trip(wins: Sequence[bool], backtest_win_rate: float | None, window: int = WINRATE_WINDOW,
                 drop: float = WINRATE_DROP) -> bool:
    """MT-G13 win-rate trigger: two CONSECUTIVE (non-overlapping) 30-trade windows each more than 15 points
    below the backtest's win rate. One bad window does not trip."""
    if backtest_win_rate is None:
        return False
    w = np.asarray(wins, dtype=float)
    rates = [w[i:i + window].mean() for i in range(0, len(w) - window + 1, window)]
    bad = [r < backtest_win_rate - drop - 1e-12 for r in rates]
    return any(a and b for a, b in zip(bad, bad[1:]))


def slippage_trip(slippage_bps: Sequence[float], model_bps: float, window: int = SLIP_WINDOW) -> bool:
    """MT-G13 slippage trigger: median slippage over the last 30 fills above 2 x the cost model."""
    s = np.asarray(slippage_bps, dtype=float)
    if len(s) < window:
        return False
    return bool(np.median(s[-window:]) > SLIP_STOP_X_MODEL * model_bps)


def slippage_raise_trip(slippage_bps: Sequence[float], model_bps: float | None,
                        min_fills: int = C.SLIP_MIN_FILLS) -> bool:
    """MT-G3 'one slippage rule': median slippage over all (>= 30) fills above 1.5 x the model -> hold the setup in
    shadow until a re-run of MT-G1 with the raised model passes. Inactive without a model."""
    s = np.asarray([v for v in slippage_bps if v is not None and np.isfinite(v)], dtype=float)
    if model_bps is None or len(s) < min_fills:
        return False
    return bool(np.median(s) > C.SLIP_MODEL_RAISE_X * model_bps)


def lane_check(r_values: Sequence[float], slippage_bps: Sequence[float], backtest_mean_r: float | None,
               model_slip_bps: float | None) -> tuple[Lane | None, list[str]]:
    """Every automatic switch-off for one setup version, after each closed trade and at startup (MT-G3, MT-G12,
    MT-G13): (the lane to demote to, or None to keep going; why). RETIRED beats SHADOW. Each check only ever
    removes risk; a check without its baseline says so instead of passing silently."""
    why: list[str] = []
    lane = switch_off(r_values)
    if lane is not None:
        why.append(f"MT-G12: {len(r_values)} closed trades, mean {float(np.mean(r_values)):+.2f}R -> {lane.value}")
    if backtest_mean_r is not None and cusum_trip(r_values, backtest_mean_r):
        why.append(f"MT-G13: CUSUM of net R against the backtest mean {backtest_mean_r:+.2f}R tripped")
        lane = lane or Lane.SHADOW
    s = [v for v in slippage_bps if v is not None]
    if model_slip_bps is not None and slippage_raise_trip(s, model_slip_bps):
        why.append(f"MT-G3: median slippage {float(np.median(s)):.2f} bps over {len(s)} fills > "
                   f"{C.SLIP_MODEL_RAISE_X:g} x model {model_slip_bps:g} bps")
        lane = lane or Lane.SHADOW
    if model_slip_bps is not None and slippage_trip(s, model_slip_bps):
        why.append(f"MT-G13: median slippage over the last {SLIP_WINDOW} fills > {C.SLIP_MODEL_STOP_X:g} x model")
        lane = lane or Lane.SHADOW
    return lane, why


_SEVERITY = {None: 0, Lane.SHADOW: 1, Lane.RETIRED: 2}


def lane_check_pending(r_values: Sequence[float], pending_gate_r: Sequence[float], slippage_bps: Sequence[float],
                       backtest_mean_r: float | None, model_slip_bps: float | None) -> tuple[Lane | None, list[str]]:
    """`lane_check` with MT-G4 take-profits still PENDING_VERIFY (see the module docstring): demote when the resolved
    series trips, or when it trips with each pending take-profit added at its gate value (min(R, 0)). The stricter
    answer wins; the reasons say which view tripped."""
    lane, why = lane_check(r_values, slippage_bps, backtest_mean_r, model_slip_bps)
    pend = [float(v) for v in pending_gate_r if v is not None and np.isfinite(v)]
    if not pend:
        return lane, why
    lane2, why2 = lane_check(list(r_values) + pend, [], backtest_mean_r, None)
    if _SEVERITY[lane2] > _SEVERITY[lane]:
        lane = lane2
        why = why + [f"{w} (counting {len(pend)} unverified take-profit(s) at their gate value, at most 0R, "
                     "until the MT-G4 SIP re-mark resolves them)" for w in why2]
    return lane, why
