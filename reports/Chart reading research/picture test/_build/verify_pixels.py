#!/usr/bin/env python3
"""Picture -> key check. Reads a few answers straight off the finished PNGs (pixel geometry only, no access to the data
arrays) and compares them with truth.json: A2, A4, A7 (chart A), B4 (chart B), C1, C2 (chart C).
A pixel reading that lands within RES (4) px of a decision boundary is counted as 'ambiguous', not as agreement or error."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
import numpy as np                       # noqa: E402
from PIL import Image                    # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE.parent

# layout constants of chartlib.render_chart (figure fractions -> pixels of the 1000x700 picture)
X0, XW = 35.0, 850.0
P_TOP, P_BOT = 700 * (1 - 0.885), 700 * (1 - 0.290)          # price panel rows
V_TOP, V_BOT = 700 * (1 - 0.260), 700 * (1 - 0.095)          # volume panel rows
GREEN, RED = np.array([0x2e, 0x9e, 0x44]) / 255, np.array([0xd6, 0x27, 0x28]) / 255
BLUE, ORANGE, PURPLE = (np.array([0x1f, 0x5f, 0xbf]) / 255, np.array([0xf2, 0x8e, 0x2b]) / 255,
                        np.array([0x8b, 0x3f, 0xbf]) / 255)
VOL_ALPHA = 0.70
RES = 4          # px: the indicator lines are ~2.6 px thick and are drawn over the candles, so smaller gaps cannot be read


def blend(c):
    return VOL_ALPHA * c + (1 - VOL_ALPHA) * np.ones(3)


def is_col(px, col, tol=0.10):
    return np.max(np.abs(px - col), axis=-1) <= tol


def slot_x(i, n):
    return X0 + (i + 0.5) * XW / n


def line_row(img, x, col, r0, r1, tol=0.16):
    """Mean row of pixels of a line colour in column x (searching x-1..x+1), or None."""
    rows = []
    for dx in (-1, 0, 1):
        column = img[int(r0):int(r1), int(round(x)) + dx]
        rows += list(np.flatnonzero(is_col(column, col, tol)) + int(r0))
    return float(np.mean(rows)) if rows else None


def body_close_row(img, x, n_body_px=-3):
    """(close row, colour name) of the candle whose body is at column x-3 (away from the wick), from candle-coloured pixels.
    The indicator lines end at the centre of the last candle, so everything is read to the LEFT of the centre."""
    xx = int(round(x)) + n_body_px
    column = img[int(P_TOP):int(P_BOT), xx]
    g = np.flatnonzero(is_col(column, GREEN)) + int(P_TOP)
    r = np.flatnonzero(is_col(column, RED)) + int(P_TOP)
    if len(g) + len(r) < 4:
        return None, None
    if len(g) >= len(r):
        return float(g.min()), "green"            # green: close is the top of the body
    return float(r.max()), "red"                  # red: close is the bottom of the body


def main():
    truth = json.loads((OUT / "truth.json").read_text())
    tally = {q: {"compared": 0, "agree": 0, "disagree": 0, "ambiguous": 0, "detail": []}
             for q in ("A2", "A4", "A7", "B4", "C1", "C2")}

    def record(q, name, key, pix, ambiguous):
        t = tally[q]
        if ambiguous or pix is None:
            t["ambiguous"] += 1
            return
        t["compared"] += 1
        if pix == key:
            t["agree"] += 1
        else:
            t["disagree"] += 1
            t["detail"].append((name, key, pix))

    for name, rec in sorted(truth.items()):
        img = np.asarray(Image.open(OUT / name).convert("RGB")).astype(float) / 255.0
        ch = rec["chart_type"]
        if ch == "A":
            n = 60
            # A4: topmost wick pixel of any candle -> which half
            tops = []
            for i in range(n):
                col = img[int(P_TOP) + 1:int(P_BOT), :, :]
                hit = []
                for dx in (-1, 0, 1):
                    c = col[:, int(round(slot_x(i, n))) + dx]
                    hit += list(np.flatnonzero(is_col(c, GREEN) | is_col(c, RED)))
                tops.append(min(hit) if hit else 10 ** 6)
            best = min(tops)
            near = [i for i, tp in enumerate(tops) if tp <= best + 1]
            halves = {i // 30 for i in near}
            record("A4", name, rec["truth"]["A4"], "first" if 0 in halves else "second", len(halves) > 1)
            # A7: tallest volume bar -> 10-minute block
            vtops = []
            for i in range(n):
                hit = []
                for dx in (-2, 0, 2):
                    c = img[int(V_TOP):int(V_BOT), int(round(slot_x(i, n))) + dx]
                    hit += list(np.flatnonzero(is_col(c, blend(GREEN)) | is_col(c, blend(RED))))
                vtops.append(min(hit) if hit else 10 ** 6)
            best = min(vtops)
            near = [i for i, tp in enumerate(vtops) if tp <= best + 1]
            blocks = {i // 10 for i in near}
            names = ["09:30-09:39", "09:40-09:49", "09:50-09:59", "10:00-10:09", "10:10-10:19", "10:20-10:29"]
            record("A7", name, rec["truth"]["A7"], names[min(blocks)], len(blocks) > 1)
            # A2: last close vs blue line
            x = slot_x(n - 1, n)
            cr, colname = body_close_row(img, x)
            br = line_row(img, x - 3, BLUE, P_TOP, P_BOT)
            if cr is None or br is None or abs(cr - br) <= RES:
                record("A2", name, rec["truth"]["A2"], None, True)
            else:
                record("A2", name, rec["truth"]["A2"], "above" if cr < br else "below", False)
        elif ch == "B":
            n = 30
            x = slot_x(n - 1, n)
            cr, colname = body_close_row(img, x, n_body_px=-5)
            br = line_row(img, x - 5, BLUE, P_TOP, P_BOT)
            if cr is None or br is None or abs(cr - br) <= RES:
                record("B4", name, rec["truth"]["B4"], None, True)
            else:
                record("B4", name, rec["truth"]["B4"], "above" if cr < br else "below", False)
        else:
            n = 60
            x = slot_x(n - 1, n)
            cr, colname = body_close_row(img, x)
            pr = line_row(img, x - 3, PURPLE, P_TOP, P_BOT)
            orr = line_row(img, x - 3, ORANGE, P_TOP, P_BOT)
            if cr is None or pr is None or abs(cr - pr) <= RES:
                record("C1", name, rec["truth"]["C1"], None, True)
            else:
                record("C1", name, rec["truth"]["C1"], "yes" if cr < pr else "no", False)
            if orr is None or pr is None or abs(orr - pr) <= RES:
                record("C2", name, rec["truth"]["C2"], None, True)
            else:
                record("C2", name, rec["truth"]["C2"], "yes" if orr < pr else "no", False)

    (HERE / "verify_pixels.json").write_text(json.dumps(tally, indent=1))
    for q, t in tally.items():
        print(f"{q}: compared {t['compared']}, agree {t['agree']}, disagree {t['disagree']}, ambiguous/skipped {t['ambiguous']}", t["detail"][:5])


if __name__ == "__main__":
    main()
