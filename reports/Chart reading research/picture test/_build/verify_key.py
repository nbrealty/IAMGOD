#!/usr/bin/env python3
"""Independent verification of the key. A second, deliberately different implementation (pure Python loops, raw files
re-read without the lab loaders, csv module for the daily file) recomputes every truth and compares it with truth.json.
Also checks the synthetic sessions, the image files and the reader-visible files for leaks.

Read-only on the repo; writes only verification.json next to this file."""
from __future__ import annotations

import csv
import glob
import gzip
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
import numpy as np                       # noqa: E402  (only for the permutation test and light statistics)
import pandas as pd                      # noqa: E402  (only to parse the raw timestamps)
from PIL import Image                    # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
CACHE = Path("/home/user/IAMGOD/trading/state/scalp_cache")
EVALS = Path("/home/user/IAMGOD/trading/evals/bars.csv.gz")
BLOCKS_A = ["09:30-09:39", "09:40-09:49", "09:50-09:59", "10:00-10:09", "10:10-10:19", "10:20-10:29"]


# ------------------------------------------------------------------------------- independent raw readers
def raw_minute_day(sym, iso):
    """The 390 regular-session bars of one date, straight from the cached csv.gz (no lab code)."""
    month = iso[:4] + iso[5:7]
    df = pd.read_csv(CACHE / f"{sym}_{month}.csv.gz")
    ts = pd.to_datetime(df["ts"], utc=True).dt.tz_convert("America/New_York")
    sel = df[(ts.dt.strftime("%Y-%m-%d") == iso).to_numpy()].copy()
    t = ts[(ts.dt.strftime("%Y-%m-%d") == iso).to_numpy()]
    order = np.argsort(t.dt.strftime("%H:%M").to_numpy())
    sel = sel.iloc[order]
    hhmm = t.dt.strftime("%H:%M").to_numpy()[order]
    assert len(sel) == 390 and hhmm[0] == "09:30" and hhmm[-1] == "15:59", (sym, iso, len(sel))
    return [sel[c].astype(float).tolist() for c in ("open", "high", "low", "close", "volume")]


def raw_daily_before(sym, iso, n=110):
    rows = []
    with gzip.open(EVALS, "rt", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["symbol"] == sym and r["date"] < iso:
                rows.append((r["date"], float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]),
                             float(r["volume"])))
    rows.sort()
    rows = rows[-n:]
    assert len(rows) == n
    return [[r[i] for r in rows] for i in (1, 2, 3, 4, 5)]


# ------------------------------------------------------------------------------- independent truth rules
def running_vwap(h, l, c, v, upto):
    out, pv, vv = [], 0.0, 0.0
    for i in range(upto):
        pv += ((h[i] + l[i] + c[i]) / 3.0) * v[i]
        vv += v[i]
        out.append(pv / vv)
    return out


def indep_A(o, h, l, c, v):
    a = {}
    num = {}
    vw = running_vwap(h, l, c, v, 60)
    chg = 100.0 * (c[59] - o[0]) / o[0]
    num["A1.chg_pct"] = chg
    a["A1"] = "up" if chg >= 0.10 else ("down" if chg <= -0.10 else "flat")
    a["A2"] = "above" if c[59] > vw[59] else "below"
    signs = "".join("+" if c[i] > vw[i] else "-" for i in range(60) if c[i] != vw[i])
    n_cross = signs.count("+-") + signs.count("-+")
    num["A3.crosses"] = n_cross
    a["A3"] = {0: "0-1", 1: "0-1", 2: "2-4", 3: "2-4", 4: "2-4"}.get(n_cross, "5+")
    top = max(h[:60])
    first_pos = [i for i in range(60) if h[i] == top][0]
    a["A4"] = "first" if first_pos <= 29 else "second"
    rng = 100.0 * (max(h[:60]) - min(l[:60])) / o[0]
    num["A5.range_pct"] = rng
    a["A5"] = "<0.25%" if rng < 0.25 else (">0.50%" if rng > 0.50 else "0.25-0.50%")
    ref = max(h[0:15])
    a["A6"] = "yes" if any(c[i] > ref for i in range(15, 60)) else "no"
    vmax = max(v[:60])
    a["A7"] = BLOCKS_A[[i for i in range(60) if v[i] == vmax][0] // 10]
    a["A8"] = None
    return a, num


def indep_B(o, h, l, c, v):
    a = {}
    num = {}
    O, H, L, C = [], [], [], []
    for k in range(30):
        s = 5 * k
        O.append(o[s])
        H.append(max(h[s:s + 5]))
        L.append(min(l[s:s + 5]))
        C.append(c[s + 4])
    chg = 100.0 * (C[29] - O[0]) / O[0]
    num["B1.chg_pct"] = chg
    a["B1"] = "up" if chg >= 0.15 else ("down" if chg <= -0.15 else "flat")
    net, full = abs(C[29] - O[0]), max(H) - min(L)
    num["B2.net_over_range"] = net / full
    a["B2"] = "trend" if net >= 0.6 * full else "range"
    alpha, e, ema = 2.0 / 21.0, C[0], [C[0]]
    for x in C[1:]:
        e = alpha * x + (1.0 - alpha) * e
        ema.append(e)
    a["B3"] = "up" if ema[29] > ema[24] else "down"
    pv = vv = 0.0
    for i in range(150):
        pv += ((h[i] + l[i] + c[i]) / 3.0) * v[i]
        vv += v[i]
    a["B4"] = "above" if C[29] > pv / vv else "below"
    early = max(H[0:12]) - min(L[0:12])
    late = max(H[18:30]) - min(L[18:30])
    a["B5"] = "yes" if late < early else "no"
    a["B6"] = None
    a["B7"] = "up" if c[179] > c[149] else "down"
    num["B7.move_pct"] = 100.0 * (c[179] - c[149]) / c[149]
    return a, num


def indep_C(do, dh, dl, dc):
    a = {}
    num = {}
    def mean_last(k, end):        # mean of the k closes ending at index `end` (inclusive)
        return sum(dc[end - k + 1:end + 1]) / k
    m20, m50 = mean_last(20, 109), mean_last(50, 109)
    a["C1"] = "yes" if dc[109] > m50 else "no"
    a["C2"] = "yes" if m20 > m50 else "no"
    net = 100.0 * (dc[109] - do[50]) / do[50]
    num["C3.net60_pct"] = net
    a["C3"] = "up" if net > 3.0 else ("down" if net < -3.0 else "flat")
    best, best_i = -1.0, None
    for i in range(51, 110):                   # candle i opens against candle i-1's close; both shown
        g = abs(do[i] - dc[i - 1]) / dc[i - 1]
        if g > best:
            best, best_i = g, i
    number = best_i - 49                       # 1-based candle number among the 60 shown (index 50 is candle 1)
    num["C4.candle_number"] = number
    num["C4.gap_pct"] = 100.0 * (do[best_i] - dc[best_i - 1]) / dc[best_i - 1]
    third = "first third" if number <= 20 else ("middle third" if number <= 40 else "last third")
    a["C4"] = {"direction": "up" if do[best_i] > dc[best_i - 1] else "down", "third": third}
    a["C5"] = None
    return a, num


# ------------------------------------------------------------------------------- run
def main():
    truth = json.loads((OUT / "truth.json").read_text())
    manifest = json.loads((OUT / "manifest_blind.json").read_text())
    data = json.loads((HERE / "session_data.json").read_text())
    res = {"checks": {}}

    # 1) raw-source equality + recomputation for every image
    n_cmp = n_bad = n_num = n_num_bad = 0
    bad_list = []
    data_equal = {"minute_real": [0, 0], "daily_real": [0, 0]}
    for name, rec in sorted(truth.items()):
        sid, ch = rec["session"], rec["chart_type"]
        d = data[sid]
        if rec["kind"] == "real":
            o, h, l, c, v = raw_minute_day(rec["symbol"], rec["date"])
            same = all(np.allclose(np.array(x), np.array(d[k]), rtol=0, atol=1e-9)
                       for x, k in zip((o, h, l, c, v), ("o", "h", "l", "c", "v")))
            data_equal["minute_real"][0] += 1
            data_equal["minute_real"][1] += int(same)
            do, dh, dl, dc, dv = raw_daily_before(rec["symbol"], rec["date"])
            same2 = all(np.allclose(np.array(x), np.array(d[k]), rtol=0, atol=1e-9)
                        for x, k in zip((do, dh, dl, dc, dv), ("d_o", "d_h", "d_l", "d_c", "d_v")))
            data_equal["daily_real"][0] += 1
            data_equal["daily_real"][1] += int(same2)
        else:
            o, h, l, c, v = (d[k] for k in ("o", "h", "l", "c", "v"))
            do, dh, dl, dc = (d[k] for k in ("d_o", "d_h", "d_l", "d_c"))
        ans, num = (indep_A(o, h, l, c, v) if ch == "A" else indep_B(o, h, l, c, v) if ch == "B"
                    else indep_C(do, dh, dl, dc))
        for q, val in ans.items():
            if q not in rec["truth"]:
                continue                         # B7 is absent for pre-cutoff real sessions (none here)
            n_cmp += 1
            if rec["truth"][q] != val:
                n_bad += 1
                bad_list.append((name, q, rec["truth"][q], val))
        for key, val in num.items():
            q, m = key.split(".")
            key_val = rec["metrics"][q][m]
            n_num += 1
            if abs(key_val - val) > 1e-8 * max(1.0, abs(val)):
                n_num_bad += 1
                bad_list.append((name, key, key_val, val))
    res["checks"]["independent_recompute"] = {"answers_compared": n_cmp, "mismatches": n_bad,
                                              "numeric_metrics_compared": n_num, "numeric_mismatches": n_num_bad,
                                              "detail": bad_list[:20]}
    res["checks"]["source_data_equal_to_raw_files"] = data_equal
    print("independent recomputation:", n_cmp, "answers compared,", n_bad, "mismatches;",
          n_num, "numeric metrics compared,", n_num_bad, "mismatches")
    print("raw-file equality (sessions matching / checked):", data_equal)

    # 2) synthetic sessions: matched-to-real properties and "no structure" statistics
    syn = {sid: d for sid, d in data.items() if d["kind"] == "synthetic"}
    stats = {"n_synth": len(syn), "bars_equal": True, "block_volume_multiset_equal": True,
             "block_abs_ret_multiset_equal": True, "pinned_bars_ok": True, "ohlc_valid": True, "same_symbol_date": True}
    z_syn, r_all_syn, r_all_real, rms_ratio, up_frac = [], [], [], [], []
    ac_syn, ac_real = [], []
    for sid, d in syn.items():
        t = data[d["matched"]]
        stats["same_symbol_date"] &= (t["symbol"] == d["symbol"] and t["date"] == d["date"])
        o, h, l, c, v = (np.array(d[k], float) for k in ("o", "h", "l", "c", "v"))
        to, th, tl, tc, tv = (np.array(t[k], float) for k in ("o", "h", "l", "c", "v"))
        stats["bars_equal"] &= (len(o) == len(to) == 390)
        stats["ohlc_valid"] &= bool(np.all(h >= np.maximum(o, c) - 1e-9) and np.all(l <= np.minimum(o, c) + 1e-9)
                                    and np.all(l > 0))
        stats.setdefault("on_cent_grid", True)
        stats["on_cent_grid"] &= bool(np.allclose(np.array([o, h, l, c]) * 100, np.round(np.array([o, h, l, c]) * 100), atol=1e-6))
        for b0 in range(0, 390, 10):
            sl = slice(b0, b0 + 10)
            stats["block_volume_multiset_equal"] &= bool(np.allclose(np.sort(v[sl]), np.sort(tv[sl])))
            rs = np.abs(np.diff(np.log(np.r_[o[0], c])))[sl]
            rt = np.abs(np.diff(np.log(np.r_[to[0], tc])))[sl]
            stats["block_abs_ret_multiset_equal"] &= bool(np.allclose(np.sort(rs), np.sort(rt), rtol=0, atol=3e-5))
        stats["pinned_bars_ok"] &= bool(v[0] == tv[0] and v[389] == tv[389])
        r = np.diff(np.log(np.r_[o[0], c]))
        rt_ = np.diff(np.log(np.r_[to[0], tc]))
        z_syn.append(float(r.sum() / math.sqrt((r ** 2).sum())))
        rms_ratio.append(float(math.sqrt((r ** 2).mean()) / math.sqrt((rt_ ** 2).mean())))
        up_frac.append(float((r > 0).mean()))
        ac_syn.append(float(np.corrcoef(r[:-1], r[1:])[0, 1]))
        ac_real.append(float(np.corrcoef(rt_[:-1], rt_[1:])[0, 1]))
        r_all_syn.append(r)
        r_all_real.append(rt_)
    pooled = np.concatenate(r_all_syn)
    stats.update({
        "sum_over_rss_z_per_session_mean": float(np.mean(z_syn)), "sum_over_rss_z_per_session_sd": float(np.std(z_syn, ddof=1)),
        "rms_ratio_synth_over_real_min": float(min(rms_ratio)), "rms_ratio_synth_over_real_max": float(max(rms_ratio)),
        "share_of_up_minutes_synth_mean": float(np.mean(up_frac)),
        "lag1_autocorr_synth_mean": float(np.mean(ac_syn)), "lag1_autocorr_template_real_mean": float(np.mean(ac_real)),
        "lag1_autocorr_se": float(1.0 / math.sqrt(len(pooled)))})
    # daily context of the synthetic sessions: same multiset of daily moves and volumes as the matched real context
    d_ok = True
    for sid, d in syn.items():
        t = data[d["matched"]]
        rs = np.abs(np.diff(np.log(np.array(d["d_c"], float))))       # close-to-close moves of the synthetic series
        # (units are open/high/low/close relative to the previous close; compare the close ratio multiset)
        d_ok &= bool(np.allclose(np.sort(np.array(d["d_v"], float)), np.sort(np.array(t["d_v"], float))))
    stats["daily_volume_multiset_equal"] = d_ok
    res["checks"]["synthetic_properties"] = stats
    print("synthetic properties:", json.dumps(stats, indent=1))


    # 2b) generator calibration: many replicates of every template, statistics that must look like "no structure"
    sys.path.insert(0, str(HERE))
    import chartlib as cl
    reps, zs, acs, ups, a6, a1, a4, b7, b3 = 300, [], [], [], [], [], [], [], []
    for sid, d in data.items():
        if d["kind"] != "real" or not any(x["matched"] == sid for x in syn.values()):
            continue
        for r in range(reps):
            rg = np.random.default_rng([7, 900, int(sid[1:]), r])
            so, sh, sl, sc, sv, _, _ = cl.synth_intraday(*(np.array(d[k], float) for k in ("o", "h", "l", "c", "v")), rg)
            rr = np.diff(np.log(np.r_[so[0], sc]))
            zs.append(rr.sum() / math.sqrt((rr ** 2).sum()))
            acs.append(np.corrcoef(rr[:-1], rr[1:])[0, 1])
            ups.append((rr > 0).mean())
            ta, _, _ = cl.truth_A(so, sh, sl, sc, sv)
            tb, _, _ = cl.truth_B(so, sh, sl, sc, sv)
            a6.append(ta["A6"] == "yes")
            a1.append(ta["A1"])
            a4.append(ta["A4"] == "first")
            b7.append(tb["B7"] == "up")
            b3.append(tb["B3"] == "up")
    calib = {"replicates": len(zs), "z_mean": float(np.mean(zs)), "z_sd": float(np.std(zs, ddof=1)),
             "lag1_autocorr_mean": float(np.mean(acs)), "share_up_minutes_mean": float(np.mean(ups)),
             "P(B7=up)": float(np.mean(b7)), "P(B3=up)": float(np.mean(b3)), "P(A4=first)": float(np.mean(a4)),
             "P(A6=yes)": float(np.mean(a6)), "A1_shares": {k: float(np.mean([x == k for x in a1])) for k in ("up", "down", "flat")}}
    res["checks"]["generator_calibration"] = calib
    print("generator calibration:", json.dumps(calib, indent=1))


    # 2c) daily-source comparison: daily bars built from the minute bars vs the repo's frozen daily bars (overlap)
    sys.path.insert(0, str(HERE))
    import chartlib as cl
    MDs = cl.load_minute()
    cmp_ = {}
    for sym in cl.SYMS:
        md = cl.daily_from_minutes(MDs[sym]["bars"])
        ev = cl.load_evals_daily(sym)
        j = ev.join(md, how="inner", rsuffix="_m")
        cmp_[sym] = {"overlap_sessions": int(len(j))}
        for col in ("open", "high", "low", "close"):
            rel = (j[col] / j[col + "_m"] - 1.0) * 100.0
            cmp_[sym][col + "_max_abs_diff_pct"] = float(rel.abs().max())
        vr = j["volume"] / j["volume_m"]
        cmp_[sym]["volume_ratio_frozen_over_minute_sum_min_mean_max"] = [float(vr.min()), float(vr.mean()), float(vr.max())]
    res["checks"]["daily_source_comparison"] = cmp_
    print("daily source comparison:", json.dumps(cmp_, indent=1))

    # 3) files the readers can see: leak scan
    forbidden = [r"\breal\b", r"\bsynthetic", r"\bfake", r"\bnoise", r"\brandom", r"\bsimulat", r"\bgenerated",
                 r"\bshuffl", r"\btemplate", r"\bSPY\b", r"\bQQQ\b", r"\bNasdaq", r"S&P", r"\b20\d\d\b", r"\bcutoff",
                 r"\bkind\b", r"\bsymbol\b", r"post_cutoff", r"\btruth\b", r"\bkey\b"]
    leaks = {}
    for fname in ("questions.md", "manifest_blind.json"):
        txt = (OUT / fname).read_text()
        hits = [p for p in forbidden if re.search(p, txt, flags=re.I)]
        leaks[fname] = hits
    mk = set()
    for m in manifest:
        mk |= set(m.keys())
    leaks["manifest_keys"] = sorted(mk)
    res["checks"]["reader_file_leak_scan"] = leaks
    print("leak scan (forbidden-word hits; manifest keys):", leaks)

    # 4) image files
    imgs = sorted(glob.glob(str(OUT / "c_*.png")))
    sizes, modes, textchunks, mtimes = Counter(), Counter(), 0, set()
    for p in imgs:
        im = Image.open(p)
        sizes[im.size] += 1
        modes[im.mode] += 1
        textchunks += len(getattr(im, "text", {}) or {})
        mtimes.add(int(Path(p).stat().st_mtime))
    names_ok = [Path(p).name for p in imgs] == [f"c_{i:04d}.png" for i in range(1, len(imgs) + 1)]
    man_names = [m["image"] for m in manifest]
    res["checks"]["images"] = {"count": len(imgs), "sizes": {str(k): v for k, v in sizes.items()}, "modes": dict(modes),
                               "png_text_chunks": textchunks, "distinct_mtimes": len(mtimes), "names_sequential": names_ok,
                               "manifest_matches_files": man_names == [Path(p).name for p in imgs],
                               "truth_matches_files": sorted(truth) == [Path(p).name for p in imgs]}
    print("images:", res["checks"]["images"])

    # 5) does the file order carry information about real/synthetic? (permutation test on mean position)
    kinds = [truth[Path(p).name]["kind"] == "synthetic" for p in imgs]
    pos = np.arange(1, len(imgs) + 1)
    obs = pos[np.array(kinds)].mean()
    rng = np.random.default_rng(0)
    perm = np.array([pos[rng.permutation(len(kinds))[:sum(kinds)]].mean() for _ in range(20000)])
    p_two = float((np.abs(perm - pos.mean()) >= abs(obs - pos.mean())).mean())
    res["checks"]["order_vs_kind"] = {"mean_position_of_synthetic": float(obs), "expected": float(pos.mean()),
                                      "permutation_p_two_sided": p_two}
    print("order vs kind:", res["checks"]["order_vs_kind"])

    (HERE / "verification.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
