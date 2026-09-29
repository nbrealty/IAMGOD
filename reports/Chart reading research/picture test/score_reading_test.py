"""Score the blind chart-reading test: reader answers vs the answer key.

Run:  python3 score_reading_test.py
Reads  chart_reading_test/truth.json, chart_reading_test/manifest_blind.json, reader_answers/pass{1,2}_{A,B,C}.json
Writes reading_test_scores.md (tables) next to this file. Nothing here touches the repo.
"""
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
TRUTH = json.load(open(HERE / "chart_reading_test" / "truth.json"))
MANIFEST = {m["image"]: m for m in json.load(open(HERE / "chart_reading_test" / "manifest_blind.json"))}

ALLOWED = {
    "A1": {"up", "down", "flat"}, "A2": {"above", "below"}, "A3": {"0-1", "2-4", "5+"}, "A4": {"first", "second"},
    "A5": {"<0.25%", "0.25-0.50%", ">0.50%"}, "A6": {"yes", "no"},
    "A7": {"09:30-09:39", "09:40-09:49", "09:50-09:59", "10:00-10:09", "10:10-10:19", "10:20-10:29"},
    "B1": {"up", "down", "flat"}, "B2": {"trend", "range"}, "B3": {"up", "down"}, "B4": {"above", "below"},
    "B5": {"yes", "no"}, "C1": {"yes", "no"}, "C2": {"yes", "no"}, "C3": {"down", "flat", "up"},
}
SCORED = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "B1", "B2", "B3", "B4", "B5", "C1", "C2", "C3"]
COMPOUND = {"B7": ("direction",), "C4": ("direction", "third")}
RATINGS = ["A8", "B6", "C5"]


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def load_pass(p):
    out = {}
    for t in "ABC":
        f = HERE / "reader_answers" / f"pass{p}_{t}.json"
        if f.exists():
            try:
                for row in json.load(open(f)):
                    out[row["image"]] = row
            except Exception as e:  # noqa: BLE001
                print(f"! cannot read {f.name}: {e}")
    return out


P = {1: load_pass(1), 2: load_pass(2)}
lines = []


def out(s=""):
    lines.append(s)
    print(s)


out("# Blind chart-reading test: scores")
out()
out(f"Answers loaded: pass 1 = {len(P[1])} pictures, pass 2 = {len(P[2])} pictures (of {len(MANIFEST)}).")
invalid = Counter()
for p in (1, 2):
    for img, row in P[p].items():
        for q in MANIFEST[img]["questions"]:
            if q in ALLOWED and row.get(q) not in ALLOWED[q]:
                invalid[(p, q)] += 1
if invalid:
    out(f"Invalid or missing answer tokens (counted as wrong): {dict(invalid)}")
out()

# ----------------------------------------------------------------------------------- simple questions
out("## 1. Accuracy per question (exact match with the key)")
out()
out("`base` = accuracy of always answering the most common answer (all 36 pictures). `both` = both passes agree with the key. "
    "`agree` = the two passes gave the same answer. 95% ranges are Wilson intervals; real Chart C pictures share most of "
    "their candles, so read their ranges as too narrow.")
out()
out("| Q | n | base | pass 1 | pass 2 | mean acc [95% range] | real | synthetic | agree p1=p2 |")
out("|---|---|---|---|---|---|---|---|---|")
rows = {}
for q in SCORED:
    imgs = [i for i in MANIFEST if q in MANIFEST[i]["questions"]]
    truth = {i: TRUTH[i]["truth"][q] for i in imgs}
    base = Counter(truth.values()).most_common(1)[0][1] / len(imgs)
    acc = {}
    for p in (1, 2):
        ok = [P[p][i].get(q) == truth[i] for i in imgs if i in P[p]]
        acc[p] = (sum(ok), len(ok))
    tot = acc[1][0] + acc[2][0]
    n2 = acc[1][1] + acc[2][1]
    real_ok = sum(P[p][i].get(q) == truth[i] for p in (1, 2) for i in imgs if i in P[p] and TRUTH[i]["kind"] == "real")
    real_n = sum(1 for p in (1, 2) for i in imgs if i in P[p] and TRUTH[i]["kind"] == "real")
    syn_ok = sum(P[p][i].get(q) == truth[i] for p in (1, 2) for i in imgs if i in P[p] and TRUTH[i]["kind"] != "real")
    syn_n = sum(1 for p in (1, 2) for i in imgs if i in P[p] and TRUTH[i]["kind"] != "real")
    both = [i for i in imgs if i in P[1] and i in P[2]]
    agree = sum(P[1][i].get(q) == P[2][i].get(q) for i in both)
    lo, hi = wilson(tot, n2)
    f = lambda k, n: f"{k / n:.0%}" if n else "-"  # noqa: E731
    out(f"| {q} | {len(imgs)} | {base:.0%} | {f(*acc[1])} | {f(*acc[2])} | {f(tot, n2)} [{lo:.0%}-{hi:.0%}] | "
        f"{f(real_ok, real_n)} | {f(syn_ok, syn_n)} | {f(agree, len(both))} |")
    rows[q] = (tot / n2 if n2 else float("nan"), base)
better = sum(1 for a, b in rows.values() if a > b + 0.05)
worse = sum(1 for a, b in rows.values() if a < b - 0.05)
out()
out(f"Questions where the reader beat the always-the-majority answer by more than 5 points: {better} of {len(rows)}; "
    f"fell below it by more than 5 points: {worse}.")
out()

# ----------------------------------------------------------------------------------- compound
out("## 2. Two-part questions")
out()
for q, parts in COMPOUND.items():
    imgs = [i for i in MANIFEST if q in MANIFEST[i]["questions"]]
    out(f"### {q}")
    if q == "B7":
        out("Direction of the price 30 minutes after the picture ends. Real days are 2026 days after the model's "
            "knowledge cutoff; synthetic days are random walks with no drift (50% is the right answer for them). "
            "Only a coin-flip level is expected; a tiny sample is not evidence of skill either way.")
    out()
    out("| part | n | base | mean acc | real | synthetic | mean confidence (B7) |")
    out("|---|---|---|---|---|---|---|")
    for part in parts:
        truth = {i: (TRUTH[i]["truth"][q][part] if isinstance(TRUTH[i]["truth"][q], dict) else TRUTH[i]["truth"][q])
                 for i in imgs}
        base = Counter(truth.values()).most_common(1)[0][1] / len(imgs)
        oks, rk, rn, sk, sn, conf = 0, 0, 0, 0, 0, []
        n = 0
        for p in (1, 2):
            for i in imgs:
                if i not in P[p]:
                    continue
                a = P[p][i].get(q) or {}
                good = (a.get(part) == truth[i]) if isinstance(a, dict) else False
                n += 1
                oks += good
                if TRUTH[i]["kind"] == "real":
                    rn += 1
                    rk += good
                else:
                    sn += 1
                    sk += good
                if q == "B7" and isinstance(a, dict) and isinstance(a.get("confidence"), (int, float)):
                    conf.append(a["confidence"])
        f = lambda k, m: f"{k / m:.0%}" if m else "-"  # noqa: E731
        out(f"| {q}.{part} | {len(imgs)} | {base:.0%} | {f(oks, n)} | {f(rk, rn)} | {f(sk, sn)} | "
            f"{(np.mean(conf) if conf else float('nan')):.0f} |")
    out()

# ----------------------------------------------------------------------------------- clarity ratings
out("## 3. Do we see 'clear, tradeable' pictures in pure noise? (0-10 clarity rating)")
out()
out("Synthetic pictures are random walks with no structure. If the reader rated them as clear as real days, "
    "it would be seeing patterns that are not there. Difference = real minus synthetic; p from a permutation test "
    "over pictures (10,000 shuffles).")
out()
out("| chart | n real | n synthetic | mean rating real | mean rating synthetic | difference | p (perm.) | corr p1-p2 |")
out("|---|---|---|---|---|---|---|---|")
rng = np.random.default_rng(0)
for q in RATINGS:
    imgs = [i for i in MANIFEST if q in MANIFEST[i]["questions"]]
    vals = {}
    for i in imgs:
        rs = [P[p][i][q] for p in (1, 2) if i in P[p] and isinstance(P[p][i].get(q), (int, float))]
        if rs:
            vals[i] = float(np.mean(rs))
    real = np.array([v for i, v in vals.items() if TRUTH[i]["kind"] == "real"])
    syn = np.array([v for i, v in vals.items() if TRUTH[i]["kind"] != "real"])
    if len(real) == 0 or len(syn) == 0:
        out(f"| {q} | {len(real)} | {len(syn)} | - | - | - | - | - |")
        continue
    diff = real.mean() - syn.mean()
    allv = np.concatenate([real, syn])
    cnt = 0
    for _ in range(10000):
        rng.shuffle(allv)
        cnt += abs(allv[:len(real)].mean() - allv[len(real):].mean()) >= abs(diff)
    both = [i for i in imgs if all(isinstance(P[p].get(i, {}).get(q), (int, float)) for p in (1, 2))]
    corr = np.corrcoef([P[1][i][q] for i in both], [P[2][i][q] for i in both])[0, 1] if len(both) > 3 else float("nan")
    out(f"| {q} | {len(real)} | {len(syn)} | {real.mean():.2f} | {syn.mean():.2f} | {diff:+.2f} | {(cnt + 1) / 10001:.3f} | {corr:.2f} |")
out()

# ----------------------------------------------------------------------------------- near-threshold errors
out("## 4. Are the mistakes near the rule's cut-off, or on clear cases?")
out()
out("For rules with a numeric cut-off, a mistake on a picture whose true value sits close to the cut-off is forgivable "
    "(a person would also hesitate). A mistake far from it is a real misreading. 'Near' = within 25% of the cut-off "
    "(or, for yes/no rules on a difference, within 0.10 percentage points).")
out()
cut = {
    "A1": ("A1", "net_pct", None), "B1": ("B1", "chg_pct", None), "C3": ("C3", "net60_pct", None),
    "C1": ("C1", "close_vs_sma50_pct", None), "C2": ("C2", "sma20_vs_sma50_pct", None),
    "B4": ("B4", "close_vs_vwap_pct", None), "B3": ("B3", "ema_last_minus_5_earlier_pct", None),
}
out("| Q | metric | wrong far from cut-off | wrong near cut-off | right far | right near |")
out("|---|---|---|---|---|---|")
for q, (qq, key, _) in cut.items():
    stats = Counter()
    for i in MANIFEST:
        if q not in MANIFEST[i]["questions"]:
            continue
        m = TRUTH[i].get("metrics", {}).get(q, {})
        v = m.get(key)
        if v is None:
            # try any single numeric metric
            nums = [x for x in m.values() if isinstance(x, (int, float))]
            v = nums[0] if nums else None
        if v is None:
            continue
        if q in ("A1", "B1"):
            thr = 0.10 if q == "A1" else 0.15
            dist = min(abs(abs(v) - thr), abs(v)) / thr
            near = dist <= 0.25 or abs(v) < 0.5 * thr
            near = abs(abs(v) - thr) <= 0.25 * thr
        elif q == "C3":
            near = abs(abs(v) - 3.0) <= 0.75
        else:
            near = abs(v) <= 0.10
        for p in (1, 2):
            if i in P[p]:
                good = P[p][i].get(q) == TRUTH[i]["truth"][q]
                stats[("right" if good else "wrong", "near" if near else "far")] += 1
    if stats:
        out(f"| {q} | {key} | {stats[('wrong','far')]} | {stats[('wrong','near')]} | {stats[('right','far')]} | {stats[('right','near')]} |")
out()
Path(HERE / "reading_test_scores.md").write_text("\n".join(lines) + "\n")
print("\nwritten:", HERE / "reading_test_scores.md")
