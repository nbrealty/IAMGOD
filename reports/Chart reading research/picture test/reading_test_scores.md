# Blind chart-reading test: scores

Answers loaded: pass 1 = 108 pictures, pass 2 = 108 pictures (of 108).

## 1. Accuracy per question (exact match with the key)

`base` = accuracy of always answering the most common answer (all 36 pictures). `both` = both passes agree with the key. `agree` = the two passes gave the same answer. 95% ranges are Wilson intervals; real Chart C pictures share most of their candles, so read their ranges as too narrow.

| Q | n | base | pass 1 | pass 2 | mean acc [95% range] | real | synthetic | agree p1=p2 |
|---|---|---|---|---|---|---|---|---|
| A1 | 36 | 36% | 100% | 100% | 100% [95%-100%] | 100% | 100% | 100% |
| A2 | 36 | 50% | 100% | 100% | 100% [95%-100%] | 100% | 100% | 100% |
| A3 | 36 | 58% | 97% | 100% | 99% [93%-100%] | 98% | 100% | 97% |
| A4 | 36 | 61% | 100% | 100% | 100% [95%-100%] | 100% | 100% | 100% |
| A5 | 36 | 50% | 100% | 100% | 100% [95%-100%] | 100% | 100% | 100% |
| A6 | 36 | 53% | 97% | 97% | 97% [90%-99%] | 96% | 100% | 100% |
| A7 | 36 | 78% | 100% | 100% | 100% [95%-100%] | 100% | 100% | 100% |
| B1 | 36 | 36% | 100% | 100% | 100% [95%-100%] | 100% | 100% | 100% |
| B2 | 36 | 72% | 100% | 100% | 100% [95%-100%] | 100% | 100% | 100% |
| B3 | 36 | 56% | 100% | 100% | 100% [95%-100%] | 100% | 100% | 100% |
| B4 | 36 | 56% | 100% | 100% | 100% [95%-100%] | 100% | 100% | 100% |
| B5 | 36 | 78% | 97% | 100% | 99% [93%-100%] | 98% | 100% | 97% |
| C1 | 36 | 72% | 97% | 97% | 97% [90%-99%] | 96% | 100% | 100% |
| C2 | 36 | 69% | 100% | 100% | 100% [95%-100%] | 100% | 100% | 100% |
| C3 | 36 | 44% | 97% | 97% | 97% [90%-99%] | 100% | 92% | 100% |

Questions where the reader beat the always-the-majority answer by more than 5 points: 15 of 15; fell below it by more than 5 points: 0.

## 2. Two-part questions

### B7
Direction of the price 30 minutes after the picture ends. Real days are 2026 days after the model's knowledge cutoff; synthetic days are random walks with no drift (50% is the right answer for them). Only a coin-flip level is expected; a tiny sample is not evidence of skill either way.

| part | n | base | mean acc | real | synthetic | mean confidence (B7) |
|---|---|---|---|---|---|---|
| B7.direction | 36 | 53% | 39% | 42% | 33% | 53 |

### C4

| part | n | base | mean acc | real | synthetic | mean confidence (B7) |
|---|---|---|---|---|---|---|
| C4.direction | 36 | 75% | 86% | 90% | 79% | nan |
| C4.third | 36 | 56% | 88% | 90% | 83% | nan |

## 3. Do we see 'clear, tradeable' pictures in pure noise? (0-10 clarity rating)

Synthetic pictures are random walks with no structure. If the reader rated them as clear as real days, it would be seeing patterns that are not there. Difference = real minus synthetic; p from a permutation test over pictures (10,000 shuffles).

| chart | n real | n synthetic | mean rating real | mean rating synthetic | difference | p (perm.) | corr p1-p2 |
|---|---|---|---|---|---|---|---|
| A8 | 24 | 12 | 5.52 | 5.79 | -0.27 | 0.688 | 0.90 |
| B6 | 24 | 12 | 5.73 | 6.21 | -0.48 | 0.452 | 0.90 |
| C5 | 24 | 12 | 4.52 | 6.96 | -2.44 | 0.000 | 0.90 |

## 4. Are the mistakes near the rule's cut-off, or on clear cases?

For rules with a numeric cut-off, a mistake on a picture whose true value sits close to the cut-off is forgivable (a person would also hesitate). A mistake far from it is a real misreading. 'Near' = within 25% of the cut-off (or, for yes/no rules on a difference, within 0.10 percentage points).

| Q | metric | wrong far from cut-off | wrong near cut-off | right far | right near |
|---|---|---|---|---|---|
| A1 | net_pct | 0 | 0 | 60 | 12 |
| B1 | chg_pct | 0 | 0 | 58 | 14 |
| C3 | net60_pct | 0 | 2 | 52 | 18 |
| C1 | close_vs_sma50_pct | 0 | 2 | 70 | 0 |
| C2 | sma20_vs_sma50_pct | 0 | 0 | 72 | 0 |
| B4 | close_vs_vwap_pct | 0 | 0 | 50 | 22 |
| B3 | ema_last_minus_5_earlier_pct | 0 | 0 | 6 | 66 |

