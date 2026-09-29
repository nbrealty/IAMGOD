"""Layout / pixel QA over every real session (no images are viewed): prints only a summary and problems."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np, chartlib as cl
MD = cl.load_minute(); EV = {s: cl.load_evals_daily(s) for s in cl.SYMS}
out = HERE / "_stress_tmp"
out.mkdir(exist_ok=True)
probs = []; n = 0
for sym in cl.SYMS:
    for day in [d for d in MD[sym]["days"] if cl.is_full_day(d)]:
        prior = EV[sym][EV[sym].index < day.date].iloc[-110:]
        s = cl.Session("T", "real", sym, day.date, day.o, day.h, day.l, day.c, day.v, prior.open.to_numpy(float), prior.high.to_numpy(float), prior.low.to_numpy(float), prior.close.to_numpy(float), prior.volume.to_numpy(float))
        for ch in "ABC":
            qa = cl.DRAW[ch](s, out / "stress.png"); n += 1
            tag = (sym, str(day.date), ch)
            if qa["text_outside"] or qa["text_overlaps"] or qa["legend_over_axes"]:
                probs.append(("LAYOUT",) + tag + (qa["text_outside"], qa["text_overlaps"], qa["legend_over_axes"]))
            c, v = qa["candles"], qa["volume"]
            if c[0] and (c[1] < c[0] or c[2] > 0): probs.append(("CANDLE",) + tag + (c,))
            if v[0] and v[1] < v[0]: probs.append(("VOLUME",) + tag + (v,))
            for lab, (chk, good) in qa["lines"].items():
                if good < chk: probs.append(("LINE",) + tag + (lab, chk, good))
print("rendered", n, "charts; problems:", len(probs))
for p in probs[:25]: print(p)
import shutil
shutil.rmtree(out)
