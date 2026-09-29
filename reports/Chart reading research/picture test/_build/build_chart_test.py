#!/usr/bin/env python3
"""Build the blind chart-reading test (images, key, manifest, questions). Deterministic: seed 7.

Run:  python3 build_chart_test.py            (writes next to this file's parent folder)
Read-only on the repo. No network. No trading calls.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np                                     # noqa: E402
from PIL import Image                                  # noqa: E402

import chartlib as cl                                  # noqa: E402
from questions_text import QUESTIONS_MD                # noqa: E402

OUT = HERE.parent
SEED = 7
N_PRE, N_POST = 8, 4                 # per symbol: 16 pre-cutoff + 8 post-cutoff real sessions = 24
N_TEMPLATES = 6                      # per symbol: 12 synthetic sessions
MTIME = 1_700_000_000                # every PNG gets this modification time (no build-order leak)

QUESTIONS = {"A": [f"A{i}" for i in range(1, 9)], "B": [f"B{i}" for i in range(1, 8)],
             "C": [f"C{i}" for i in range(1, 6)]}


def jd(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def main():
    log = []

    def say(msg):
        print(msg)
        log.append(msg)

    # ------------------------------------------------------------------ data
    MD = cl.load_minute()
    FULL = {s: [d for d in MD[s]["days"] if cl.is_full_day(d)] for s in cl.SYMS}
    MIN_D = {s: cl.daily_from_minutes(MD[s]["bars"]) for s in cl.SYMS}
    EV_D = {s: cl.load_evals_daily(s) for s in cl.SYMS}
    for s in cl.SYMS:
        say(f"{s}: minute bars {len(MD[s]['bars'])} rows, {len(MD[s]['days'])} sessions in calendar, "
            f"{len(FULL[s])} full-day sessions ({FULL[s][0].date} .. {FULL[s][-1].date}); "
            f"frozen daily bars {len(EV_D[s])} rows ({EV_D[s].index[0]} .. {EV_D[s].index[-1]})")

    def pools_for(source):
        src = MIN_D if source == "minute" else EV_D
        return {s: [d for d in FULL[s] if int((src[s].index < d.date).sum()) >= cl.CTX + 1] for s in cl.SYMS}

    pools = pools_for("minute")
    enough = all(sum(d.date < cl.CUTOFF for d in pools[s]) >= N_PRE and
                 sum(d.date >= cl.CUTOFF for d in pools[s]) >= N_POST for s in cl.SYMS)
    source = "minute"
    if not enough:
        say("minute cache does not hold enough sessions with >=111 earlier minute-built sessions "
            f"(eligible: { {s: len(pools[s]) for s in cl.SYMS} }); daily context falls back to the repo's frozen daily bars")
        source = "evals"
        pools = pools_for("evals")
    say(f"daily context source: {source}; eligible target sessions per symbol: { {s: len(pools[s]) for s in cl.SYMS} }")
    say("eligible pre-cutoff sessions per symbol: "
        f"{ {s: sum(d.date < cl.CUTOFF for d in pools[s]) for s in cl.SYMS} }")
    daily_src = MIN_D if source == "minute" else EV_D

    def prior111(sym, dte):
        df = daily_src[sym]
        df = df[df.index < dte].iloc[-(cl.CTX + 1):]
        assert len(df) == cl.CTX + 1, (sym, dte, len(df))
        return df

    def make_real(sid, sym, day):
        p = prior111(sym, day.date)
        d = p.iloc[1:]
        s = cl.Session(sid, "real", sym, day.date, day.o.copy(), day.h.copy(), day.l.copy(), day.c.copy(), day.v.copy(),
                       d["open"].to_numpy(float), d["high"].to_numpy(float), d["low"].to_numpy(float),
                       d["close"].to_numpy(float), d["volume"].to_numpy(float),
                       post_cutoff=bool(day.date >= cl.CUTOFF), daily_source=source)
        return s, p

    # ------------------------------------------------------------------ sample the real sessions
    rng_s = np.random.default_rng([SEED, 1])
    picked: dict[str, list] = {s: [] for s in cl.SYMS}
    used_dates, skipped = set(), []
    for stratum in ("pre", "post"):
        for sym in cl.SYMS:
            want = N_PRE if stratum == "pre" else (N_PRE + N_POST) - len(picked[sym])
            cand = [d for d in pools[sym] if ((d.date < cl.CUTOFF) == (stratum == "pre")) and d.date not in used_dates]
            got = 0
            for j in rng_s.permutation(len(cand)):
                if got >= want:
                    break
                day = cand[int(j)]
                s, _ = make_real("tmp", sym, day)
                flags = sum((v[2] for v in cl.all_truth(s).values()), [])
                if flags:
                    skipped.append((sym, str(day.date), flags))
                    continue
                picked[sym].append(day)
                used_dates.add(day.date)
                got += 1
            say(f"stratum {stratum} {sym}: wanted {want}, picked {got} (pool {len(cand)})")
    say(f"sessions skipped because a rule was undefined (exact tie): {skipped}")
    pre_short = N_PRE * 2 - sum(d.date < cl.CUTOFF for sym in cl.SYMS for d in picked[sym])

    reals: list[cl.Session] = []
    priors: dict[str, object] = {}
    n = 0
    for sym in cl.SYMS:
        for day in sorted(picked[sym], key=lambda d: d.date):
            n += 1
            s, p = make_real(f"R{n:02d}", sym, day)
            reals.append(s)
            priors[s.sid] = p
    assert len(reals) == 2 * (N_PRE + N_POST), len(reals)

    # ------------------------------------------------------------------ synthetic sessions
    rng_t = np.random.default_rng([SEED, 2])
    templates = []
    for sym in cl.SYMS:
        mine = [s for s in reals if s.symbol == sym]
        for k in sorted(rng_t.choice(len(mine), N_TEMPLATES, replace=False)):
            templates.append(mine[int(k)])
    synths: list[cl.Session] = []
    for j, t in enumerate(templates):
        for attempt in range(20):
            key = [SEED, 100 + j] if attempt == 0 else [SEED, 100 + j, attempt]
            key_d = [SEED, 200 + j] if attempt == 0 else [SEED, 200 + j, attempt]
            ri, rd = np.random.default_rng(key), np.random.default_rng(key_d)
            so, sh, sl, sc, sv, src, flip = cl.synth_intraday(t.o, t.h, t.l, t.c, t.v, ri)
            p = priors[t.sid]
            do, dh, dl, dc, dv = cl.synth_daily(p["open"].to_numpy(float), p["high"].to_numpy(float),
                                                p["low"].to_numpy(float), p["close"].to_numpy(float),
                                                p["volume"].to_numpy(float), rd)
            x = cl.Session(f"X{j + 1:02d}", "synthetic", t.symbol, t.date, so, sh, sl, sc, sv, do, dh, dl, dc, dv,
                           matched=t.sid, post_cutoff=True, daily_source=source,
                           info={"attempt": attempt, "intraday_source_index": src.tolist(),
                                 "intraday_flipped": flip.astype(int).tolist()})
            flags = sum((v[2] for v in cl.all_truth(x).values()), [])
            if not flags:
                break
        else:
            raise RuntimeError("could not build a tie-free synthetic session")
        synths.append(x)
        t.info = {"synthetic_twin": x.sid}
    sessions = reals + synths
    say(f"real sessions: {len(reals)} ({sum(s.symbol == 'SPY' for s in reals)} SPY, "
        f"{sum(s.symbol == 'QQQ' for s in reals)} QQQ); pre-cutoff {sum(not s.post_cutoff for s in reals)}, "
        f"post-cutoff {sum(s.post_cutoff for s in reals)}; synthetic sessions: {len(synths)}")

    # ------------------------------------------------------------------ opaque, shuffled image names
    items = [(s.sid, ch) for s in sessions for ch in "ABC"]
    order = np.random.default_rng([SEED, 3]).permutation(len(items))
    names = {}
    for k, idx in enumerate(order):
        names[items[int(idx)]] = f"c_{k + 1:04d}.png"
    by_sid = {s.sid: s for s in sessions}

    for old in OUT.glob("c_*.png"):
        old.unlink()

    # ------------------------------------------------------------------ render (in name order) + truth
    truth, manifest, qa_all = {}, [], {}
    tr_cache = {s.sid: cl.all_truth(s) for s in sessions}
    for name, (sid, ch) in sorted(((v, k) for k, v in names.items())):
        s = by_sid[sid]
        qa = cl.DRAW[ch](s, OUT / name)
        qa_all[name] = {"candles": qa["candles"], "volume": qa["volume"], "lines": qa["lines"],
                        "text_outside": qa["text_outside"], "text_overlaps": qa["text_overlaps"],
                        "legend_over_axes": qa["legend_over_axes"]}
        im = Image.open(OUT / name)
        assert im.mode == "RGBA" and int(np.asarray(im)[..., 3].min()) == 255 and im.size == (1000, 700)
        im.convert("RGB").save(OUT / name, format="PNG", optimize=True)
        os.utime(OUT / name, (MTIME, MTIME))
        ans, met, flags = tr_cache[sid][ch]
        asked = list(QUESTIONS[ch])
        if ch == "B" and not (s.post_cutoff or s.kind == "synthetic"):
            asked.remove("B7")
            ans = {k: v for k, v in ans.items() if k != "B7"}
            met = {k: v for k, v in met.items() if k != "B7"}
        rec = {"session": s.sid, "kind": s.kind, "symbol": s.symbol, "date": s.date.isoformat(),
               "post_cutoff": s.post_cutoff, "chart_type": ch, "daily_source": s.daily_source,
               "matched_session": s.matched if s.kind == "synthetic" else (s.info or {}).get("synthetic_twin"),
               "truth": ans, "metrics": met, "flags": flags, "soft_flags": cl.soft_flags(ch, met)}
        if s.kind == "synthetic":
            rec["note"] = "symbol/date are those of the matched real session; the price path itself is synthetic"
        truth[name] = rec
        manifest.append({"image": name, "chart_type": ch, "questions": asked})

    (OUT / "truth.json").write_text(json.dumps(truth, indent=1, default=jd))
    (OUT / "manifest_blind.json").write_text(json.dumps(manifest, indent=1))
    (OUT / "questions.md").write_text(QUESTIONS_MD)

    # ------------------------------------------------------------------ data used, for independent re-checking
    data = {}
    for s in sessions:
        data[s.sid] = {"kind": s.kind, "symbol": s.symbol, "date": s.date.isoformat(), "matched": s.matched,
                       "o": s.o, "h": s.h, "l": s.l, "c": s.c, "v": s.v,
                       "d_o": s.d_o, "d_h": s.d_h, "d_l": s.d_l, "d_c": s.d_c, "d_v": s.d_v,
                       "info": s.info if s.kind == "synthetic" else None}
    (HERE / "session_data.json").write_text(json.dumps(data, default=jd))
    (HERE / "names.json").write_text(json.dumps({f"{k[0]}|{k[1]}": v for k, v in names.items()}, indent=1))
    (HERE / "render_qa.json").write_text(json.dumps(qa_all, indent=1, default=jd))
    (HERE / "build_log.json").write_text(json.dumps({
        "log": log, "source": source, "skipped": skipped, "pre_short": pre_short,
        "seed": SEED, "cutoff": cl.CUTOFF.isoformat()}, indent=1, default=jd))

    # ------------------------------------------------------------------ render QA summary
    bad = 0
    tot = Counter()
    for name, q in qa_all.items():
        c, v = q["candles"], q["volume"]
        tot["candles_checked"] += c[0]
        tot["candles_ok"] += c[1]
        tot["candles_wrong_colour"] += c[2]
        tot["volume_checked"] += v[0]
        tot["volume_ok"] += v[1]
        for _, (chk, good) in q["lines"].items():
            tot["line_pts_checked"] += chk
            tot["line_pts_ok"] += good
        if q["text_outside"] or q["text_overlaps"] or q["legend_over_axes"]:
            bad += 1
    say(f"render QA over {len(qa_all)} images: {dict(tot)}; images with text/legend layout problems: {bad}")
    print("done:", len(list(OUT.glob('c_*.png'))), "images")


if __name__ == "__main__":
    main()
