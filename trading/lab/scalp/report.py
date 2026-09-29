"""Scalp lab report: results.json + results.csv (machine-readable) and summary.md (for people).

Files go to state/scalp_results/ (gitignored): trades.csv.gz (every setup/baseline trade, gross),
meta.json (the run's settings), results.csv / results.json (metrics) and summary.md.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from .data import TRADING_DIR
from .signals import SETUPS

OUT_DIR = TRADING_DIR / "state" / "scalp_results"
FAMILY_SYMBOLS = ("SPY", "QQQ")   # the pre-registered symbols; the multiple-testing family is every setup on these
                                  # (plus any other symbol a run adds), whatever subset one run happens to test

HOW_TO_READ = """\
How to read this (every trade is $1,000 of stock; 1 bp = 0.01% = $0.10 on $1,000):
- **Exp bps** is the average result per trade after costs, with a 95% range from a bootstrap over days. If the
  range includes 0, the average could be luck.
- **vs random** compares the setup with random entries of the same count and holding time, with a random
  (coin-flip) direction, on the same days. A small p (for example under 0.05) means the setup beat random entries with a
  random direction more often than luck would. The coin baseline is the test of direction at the setup's own entry times.
  With many setups tested at once, some will look good by chance, so the verdict uses a stricter bar.
- **Verdict** (fixed before seeing results): *candidate* only if, at realistic costs and in the out-of-sample
  half, the 95% range is above 0 AND p vs random is below 0.05 / (every pre-registered setup x symbol pair,
  counted in full even when a run tests only some of them). A candidate whose range is not above 0 at the
  pessimistic cost is flagged. Everything else is *no edge shown* (or *too few days* under 10 sessions). A
  candidate is a reason for paper trading, not for real money.
- **vs coin** trades the setup's own entry times with a random direction (stops and targets mirrored).
- Paper and backtest fills are optimistic: no queue, no latency, no market impact. Costs here are estimates.
"""

DEVIATIONS = """\
Deviations from the papers (pre-declared, not tuned):
- Time exit at the open of the 15:55 bar, not the 16:00 close. LAST30_MOM_SPY_CLOSE exits at the official
  close (Alpaca's daily bar, which includes the closing auction) when it is cached, else at the 15:59 bar close.
- "Yesterday's close" in LAST30 and GAP is the official close (closing auction) when cached, else the 15:59 bar
  close. NOISE uses the 15:59 bar close, as its rule says (last regular-session bar). The two differ by ~1 bp.
- Fixed $1,000 notional per trade. The papers' own sizing (ORB5: 1% risk, leverage <= 4x; NOISE: min(4,
  2%/daily vol)) is shown only as `pub_sizing_pct` (sum of returns on equity, not compounded).
- Costs are the spec's per-side scenarios (0.5 / 1.5 / 4 bps) plus the memo's quoted-spread floor (0.25 bps),
  not the papers' commission-only costs.
- Any entry whose fill price is already past its stop or target is skipped (the papers state this for ORB5).
- Half days are skipped as trading days, and so are sessions whose data stop before the time exit (a
  session still in progress). Bars are adjusted for splits and dividends (Adjustment.ALL), all on one basis.
"""

OPTIONS_NOTE = """\
Options proxy (rough order of magnitude only, not an options backtest): a same-day at-the-money call for a long
signal or put for a short one, priced with a Bachelier model at entry and exit, so it includes time decay.
Volatility = max(1.2 x realised 14-day vol, 10%/yr) because 0DTE implied vol usually sits above realised. Cost per
side = max($0.01 half-spread, 2% of premium) realistic, max($0.02, 5%) pessimistic. Limits: no skew, no
intraday IV changes, no real strike grid, and paper-account option fills come from randomised 'indicative'
quotes, so paper option results are not evidence either. Results are bps of premium ($ per $1,000 of premium).
"""



def save_trades(trades: pd.DataFrame, meta: dict, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "trades.csv.gz"
    trades.to_csv(path, index=False, compression="gzip")
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, default=str))
    return path


def load_trades(out_dir: Path = OUT_DIR) -> tuple[pd.DataFrame, dict]:
    path = out_dir / "trades.csv.gz"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing: run `python -m lab.scalp backtest ...` first")
    return pd.read_csv(path), json.loads((out_dir / "meta.json").read_text())


def _clean(v):
    if isinstance(v, float) and not math.isfinite(v):
        return None if math.isnan(v) else ("inf" if v > 0 else "-inf")
    return v


def family_size(symbols: "pd.Series | list[str]") -> int:
    """Number of pre-registered setup x symbol tests: every setup on SPY, QQQ and any other symbol run."""
    return len(SETUPS) * len(set(FAMILY_SYMBOLS) | set(symbols))


def alpha_for(m: pd.DataFrame) -> float:
    """Bonferroni bar for the verdict, fixed by the pre-registered family, not by what this run included."""
    return 0.05 / family_size(list(m["symbol"]) if not m.empty else [])


def boot_too_small(boot: int | None, alpha: float) -> bool:
    """The smallest bootstrap p is 1 / (boot + 1): at or above alpha, no setup could ever pass."""
    return boot is not None and 1.0 / (int(boot) + 1) >= alpha


def verdicts(m: pd.DataFrame, boot: int | None = None) -> pd.DataFrame:
    """The pre-declared pass rule, per setup x symbol."""
    cols = ["setup", "symbol", "verdict", "alpha", "pessimistic_ok"]
    if m.empty:
        return pd.DataFrame(columns=cols)
    pairs = m[["setup", "symbol"]].drop_duplicates()
    alpha = alpha_for(m)
    oos = m[m["split"] == "OOS"].set_index(["setup", "symbol", "scenario"])
    out = []
    for setup, sym in pairs.itertuples(index=False):
        v, pess_ok = "too few days", None
        if (setup, sym, "realistic") in oos.index:
            r = oos.loc[(setup, sym, "realistic")]
            lo, p = r.get("ci_lo_bps", float("nan")), r.get("p_vs_random", float("nan"))
            if pd.notna(lo) and pd.notna(p):
                if boot_too_small(boot, alpha):
                    v = "undecidable (--boot too small)"
                else:
                    v = "candidate" if lo > 0 and p < alpha else "no edge shown"
            if (setup, sym, "pessimistic") in oos.index:
                lo_p = oos.loc[(setup, sym, "pessimistic")].get("ci_lo_bps", float("nan"))
                pess_ok = bool(pd.notna(lo_p) and lo_p > 0)
            if v == "candidate" and not pess_ok:
                v = "candidate (fails at pessimistic cost)"
        out.append({"setup": setup, "symbol": sym, "verdict": v, "alpha": alpha, "pessimistic_ok": pess_ok})
    return pd.DataFrame(out, columns=cols)


def write(m: pd.DataFrame, meta: dict, out_dir: Path = OUT_DIR) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"csv": out_dir / "results.csv", "json": out_dir / "results.json", "md": out_dir / "summary.md"}
    m.to_csv(paths["csv"], index=False)
    v = verdicts(m, meta.get("boot"))
    records = [{k: _clean(val) for k, val in r.items()} for r in m.to_dict("records")]
    paths["json"].write_text(json.dumps({"meta": {**meta, "alpha": alpha_for(m)}, "verdicts": v.to_dict("records"),
                                         "metrics": records}, indent=1, default=str))
    paths["md"].write_text(summary_md(m, meta, v))
    return paths


def _f(x, nd: int = 1, pct: bool = False) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    if isinstance(x, float) and math.isinf(x):
        return "inf"
    return f"{x * 100:.0f}%" if pct else f"{x:,.{nd}f}"


def _table(m: pd.DataFrame, split: str, scenario: str, v: pd.DataFrame | None = None) -> str:
    if m.empty:
        return "_no trades_\n"
    t = m[(m["split"] == split) & (m["scenario"] == scenario)].copy()
    if t.empty:
        return "_no trades_\n"
    t = t.sort_values(["primary", "setup", "symbol"], ascending=[False, True, True])
    vd = {} if v is None else {(r.setup, r.symbol): r.verdict for r in v.itertuples()}
    head = ("| Setup | Sym | Trades | Win | Exp bps [95% range] | $/trade | PF | Total $ | Max DD $ | Hold min "
            "| vs random bps (p) | vs coin bps (p) |" + (" Verdict |" if v is not None else ""))
    lines = [head, "|" + "---|" * (head.count("|") - 1)]
    for r in t.to_dict("records"):
        tag = r["setup"] + ("" if r["primary"] else " (check)")
        row = (f"| {tag} | {r['symbol']} | {r['trades']} | {_f(r.get('win_rate'), pct=True)} | "
               f"{_f(r.get('expectancy_bps'), 2)} [{_f(r.get('ci_lo_bps'), 2)}, {_f(r.get('ci_hi_bps'), 2)}] | "
               f"{_f(r.get('usd_per_trade'), 3)} | {_f(r.get('profit_factor'), 2)} | {_f(r.get('total_usd'), 2)} | "
               f"{_f(r.get('max_dd_usd'), 2)} | {_f(r.get('avg_hold_min'), 0)} | "
               f"{_f(r.get('vs_random_bps'), 2)} ({_f(r.get('p_vs_random'), 3)}) | "
               f"{_f(r.get('vs_coin_bps'), 2)} ({_f(r.get('p_vs_coin'), 3)}) |")
        if v is not None:
            row += f" {vd.get((r['setup'], r['symbol']), '-')} |"
        lines.append(row)
    return "\n".join(lines) + "\n"


def _pivot(m: pd.DataFrame, split: str, scen: list[str], label: dict[str, str] | None = None) -> str:
    if m.empty:
        return "_no trades_\n"
    t = m[(m["split"] == split) & (m["scenario"].isin(scen))]
    if t.empty:
        return "_no trades_\n"
    p = t.pivot_table(index=["setup", "symbol"], columns="scenario", values="expectancy_bps", aggfunc="first")
    cols = [c for c in scen if c in p.columns]
    head = "| Setup | Sym | " + " | ".join((label or {}).get(c, c) for c in cols) + " |"
    lines = [head, "|" + "---|" * (len(cols) + 2)]
    for (setup, sym), r in p.iterrows():
        lines.append(f"| {setup} | {sym} | " + " | ".join(_f(r[c], 2) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def _years(m: pd.DataFrame) -> str:
    if m.empty:
        return "_no trades_\n"
    t = m[m["split"].astype(str).str.startswith("Y") & (m["scenario"] == "realistic")]
    if t.empty:
        return "_no trades_\n"
    p = t.pivot_table(index=["setup", "symbol"], columns="split", values="expectancy_bps", aggfunc="first")
    n = t.pivot_table(index=["setup", "symbol"], columns="split", values="trades", aggfunc="first")
    cols = sorted(p.columns)
    lines = ["| Setup | Sym | " + " | ".join(c[1:] for c in cols) + " |", "|" + "---|" * (len(cols) + 2)]
    for key, r in p.iterrows():
        cells = [f"{_f(r[c], 2)} (n={int(n.loc[key, c])})" if pd.notna(r[c]) else "-" for c in cols]
        lines.append(f"| {key[0]} | {key[1]} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def summary_md(m: pd.DataFrame, meta: dict, v: pd.DataFrame | None = None) -> str:
    v = verdicts(m, meta.get("boot")) if v is None else v
    c = meta.get("costs", {})
    alpha = alpha_for(m)
    skipped = meta.get("incomplete_sessions_skipped") or []
    parts = [
        "# Scalp lab: minute-setup backtest\n",
        f"- Symbols: {', '.join(meta.get('symbols', []))}; sessions {meta.get('start')} to {meta.get('end')} "
        f"({meta.get('sessions', '?')} full sessions with data; half days skipped)",
        f"- In-sample = sessions up to {meta.get('split_mid')}; out-of-sample = after. No parameter was searched.",
        f"- Costs per side: quoted {c.get('quoted')} / low {c.get('low')} / realistic {c.get('realistic')} / "
        f"pessimistic {c.get('pessimistic')} bps of notional; options max(${c.get('opt_tick_realistic')}, "
        f"{c.get('opt_realistic')}% of premium) / max(${c.get('opt_tick_pessimistic')}, {c.get('opt_pessimistic')}%)",
        f"- Data: Alpaca SIP 1-minute bars, regular session, adjustment={meta.get('adjustment')}; "
        f"seed {meta.get('seed')}; bootstrap {meta.get('boot')} resamples over days; generated {meta.get('generated')}",
        f"- Verdict bar: p vs random < {alpha:.5f} (0.05 / {family_size(list(m['symbol']) if not m.empty else [])} "
        f"pre-registered setup x symbol tests)",
    ]
    if boot_too_small(meta.get("boot"), alpha):
        parts.append(f"- **WARNING: with {meta.get('boot')} bootstrap resamples the smallest possible p is "
                     f"{1 / (int(meta['boot']) + 1):.5f}, not below the bar, so no setup can pass. Re-run with "
                     f"--boot {math.ceil(1 / alpha)} or more.**")
    if skipped:
        parts.append(f"- Skipped {len(skipped)} session(s) whose data stop before the time exit (in progress or "
                     f"cut short): {', '.join(skipped[:10])}")
    parts += [
        "", HOW_TO_READ,
        "## All sessions, realistic costs\n", _table(m, "all", "realistic", v),
        "## Out-of-sample half, realistic costs (the verdict is based on this table)\n",
        _table(m, "OOS", "realistic", v),
        "## In-sample half, realistic costs\n", _table(m, "IS", "realistic"),
        "## Cost sensitivity: expectancy in bps per trade, all sessions\n",
        _pivot(m, "all", ["gross", "quoted", "low", "realistic", "pessimistic"]),
        "## Options proxy (0DTE ATM, Bachelier with time decay), realistic option costs, all sessions\n",
        OPTIONS_NOTE, _table(m, "all", "opt_bach"),
        "### Options proxy: out-of-sample half\n", _table(m, "OOS", "opt_bach"),
        "### Options proxy by cost, all sessions (bps of premium per trade)\n",
        "The last column ignores time decay and overstates: it is the spec's first rough idea, shown only to "
        "make that visible. Do not use it.\n",
        _pivot(m, "all", ["opt_bach", "opt_bach_pess", "opt_delta_no_decay"],
               {"opt_bach": "Bachelier, realistic cost", "opt_bach_pess": "Bachelier, pessimistic cost",
                "opt_delta_no_decay": "delta 0.5, IGNORES DECAY (overstates, do not use)"}),
        "## By calendar year: expectancy in bps per trade, realistic costs\n", _years(m),
        DEVIATIONS,
    ]
    return "\n".join(parts)
