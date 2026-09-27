# Reminiscences of a Stock Operator (Edwin Lefèvre, 1923): study notes

Source read in full: `scratchpad/books/edwin_lefevre_reminiscences_of_a_stock_operator.txt`
(24 chapters, about 8,980 lines). The file also has about 1,000 lines of material that is
**not part of the book**, added after "THE END": a 2014 TRADERS' interview with Michael
Covel, a Covel article in Active Trader ("Trend-following winners are not lucky monkeys"),
and a Covel MTA newsletter piece on "risk equalization". I read these too. They are
handled separately at the end of section 5 and in section 6, and they are not attributed to
Lefèvre.

Quotes are kept to single short phrases (10 in total). Everything else is paraphrased.

---

## 1. What the book is about

The book is a lightly fictionalised first-person memoir. "Larry Livingston" is a thinly
veiled Jesse Livermore, as told to the journalist Edwin Lefèvre. It follows him from a
14-year-old quotation-board boy beating the bucket shops, through several bankruptcies,
to the millions he made in the 1907 panic and the 1915-17 war boom. Its main argument is
that a speculator makes money by reading the overall trend ("general conditions"),
entering only when price confirms it, adding to positions that are already winning,
cutting losers at once and then sitting through the big swing. Most failures come from
the trader's own nature (hope, fear, impatience, a need for action, tips, persuasive
people, feeling obliged to someone), not from the market. The last third moves to
manipulation, pools, insider "news" and how promoters sell stock to the public. It works
as a warning about who is on the other side of a retail trade.

---

## 2. Key lessons (own words, with chapter)

1. **Price action comes first and the reason comes later.** Act on how prices behave. The
   explanation often arrives days or weeks afterwards (Ch I, X, XVII).
2. **Record your predictions and score them.** As a boy he wrote down what a stock "should"
   do and then checked it against the tape. It was a log of hits and misses, not paper
   trading for fun (Ch I).
3. **A method that works in one venue can fail in another.** His scalping edge was an
   artefact of bucket shops, which filled him at the printed price with no slippage and
   no market impact. With real execution, lag and his own order size, the same method lost
   money (Ch II, III). This is an early lesson about transaction costs and backtest realism.
4. **The urge to trade all the time is the main way intelligent people lose.** Most of the
   time there is no adequate reason to be in the market (Ch II, IV). He calls this person
   "the Wall Street fool, who thinks he must trade all the time" (Ch II).
5. **Be on the right side, not the bull or bear side.** You have no allegiance to either
   direction. There is only "the right side" (Ch III, XIV).
6. **Big money comes from sitting through the main trend, not from trading the wiggles.**
   Taking a quick 4-point profit in a bull market and waiting for a pullback that never
   comes is expensive (Ch V: Partridge's "it's a bull market"). In his words, "it never was
   my thinking that made the big money for me" (Ch V).
7. **Being right too early can ruin you.** In 1906 his bear thesis was correct, but he sold
   before the market confirmed it, and the rallies broke him. Wait for the tape to confirm
   before committing in size (Ch VIII).
8. **Buy strength, not cheapness.** Add only on a rising scale, and never add to a
   position that shows a loss. Stocks are "never too high for you to begin buying or too
   low to begin selling" (Ch VII, X).
9. **Probe with a small position and let the market prove you right before adding.** The
   losses on the probes are cheap insurance for having a full position in every real move
   (Ch VII, X: the cotton method).
10. **The line of least resistance.** Inside a trading range the direction is unknowable,
    so wait until price breaks out of the range (Ch X: the wheat at $1.20 example).
    Pushing a market to start the move yourself failed (Ch X: the cotton "push").
11. **Cut losers and keep winners, the opposite of instinct.** He violated this under
    Percy Thomas's influence: he sold the winning wheat, kept and added to the losing
    cotton, and lost most of his fortune (Ch XII). His rule: "Always sell what shows you a
    loss and keep what shows you a profit" (Ch XII).
12. **Hope and fear have to be reversed.** Fear that a loss will grow, and hope that a
    profit will grow (Ch X).
13. **Tips, persuasive experts and personal obligations are the most expensive inputs.**
    Examples are Ed Harding's warning on Union Pacific (Ch VI), Percy Thomas on cotton
    (Ch XII) and Dan Williamson's "help" (Ch XIII). Each overrode his own reading, and he
    lost money every time.
14. **Group and leader behaviour.** Do not buy a laggard just because its group has run
    (Ch XVII: Chester Motors). When market leaders stop making new highs while the rest of
    the market rises, the bull market is ending for those stocks (Ch XIV).
15. **Exit when the market can absorb your size.** Exit into strength or into a panic,
    when volume is big enough to take the position. Do not try to catch the top tick
    (Ch XI, XIV, XVII). As he puts it, sell after a reaction if there is no rally (Ch XIV).
16. **Your finances and mental state are part of the system.** Trading while in debt, ill
    or harassed by creditors produced a string of losses. Clearing the debt restored his
    judgment (Ch XIII, XIV). Trying to make the market pay for a specific purchase (the
    sable coat) turns speculation into gambling (Ch XII).
17. **Unforeseeable events will happen.** Examples are rule changes (the coffee price fix),
    wars and the sinking of the Lusitania. Size positions so that one of these cannot finish
    you (Ch XIV, XV).
18. **Lock away part of your winnings.** After paying his debts he put money into
    annuities and trusts that he could not touch (Ch XIV).
19. **Anonymous bullish news, and "bear raid" explanations for declines, are usually
    insiders selling.** A long, steady decline has a real cause (Ch XV, XXIII: New Haven).
20. **No one beats the market consistently.** He repeats this in Ch X and Ch XXIV:
    "no man living can beat the stock market". This comes from the book's hero, who went
    broke several times.

---

## 3. Codeable rules

The book gives almost no numeric parameters. Below, each rule states what the book says,
followed by one precise version a programmer could implement. The parameters are mine
and must be backtested before use. None of them are Lefèvre's own.

### 3.1 Entries: the line of least resistance and range breakouts (Ch X)
- Book: during a range-bound "get-nowhere" market, take no position. Act only when price
  closes through the range limit (the wheat $1.10-$1.20 example: buy when it crosses
  $1.20). Do not anticipate the breakout.
- Code:
  `range_hi = max(high[t-N..t-1])`, `range_lo = min(low[t-N..t-1])`, where N = 40-60 days.
  The market counts as "in a range" if `(range_hi - range_lo)/range_lo < W` (for example
  15%) or if ADX(14) < 20. Entry: `close[t] > range_hi` (long only). No entry while
  `range_lo <= close <= range_hi`.
- Optional confirmation from Ch VII/XVII: the breakout day's volume is at least k times
  the 50-day average, which approximates the market "absorbing" orders.

### 3.2 Entries: the "crossing par / new-high" rule (Ch IX, XIV)
- Book: when a stock crosses 100, 200 or 300 **for the first time**, it usually goes on
  another 30-50 points. Buy just as it crosses. Anaconda and Bethlehem Steel are the
  examples.
- Code (modern version, because round nominal prices are arbitrary after splits):
  `close[t] > max(close[0..t-1])` means a close at an all-time high or a new 52-week or
  multi-year high. The round-number version is testable only as a curiosity.
- Paired failure exit (Ch IX, Anaconda): if the breakout does not follow through and
  `close < breakout_level - x` within k days, exit everything. He expected 310 without a
  pause. When price fell back to 301, just above his ~300 entry, he treated it as a false
  move and sold it all at market.

### 3.3 Confirmation before size (Ch VIII, XIV)
- Book: even with a strong thesis, do not "sprint". Commit in size only once price
  confirms it. In 1916 he doubled his short line only after **every** position showed at
  least 4 points of profit.
- Code: `add_allowed = all(open_pnl_i >= m * ATR_i for i in sleeve_positions)`. As a
  portfolio-level rule, increase sleeve exposure only while the sleeve's open trades are
  collectively in profit.

### 3.4 Pyramiding (Ch VII, X)
- Book (stocks, Ch VII): buy 2,000, then 2,000 more after 1 point of profit, then 2,000
  more, then stop and watch the reaction. If it holds and rallies, add 4,000 more.
  Book (cotton, Ch X): if the full position is 40-50k bales, buy 10k first. Add 10k after
  a 10-point gain and 20k more after a 20-point gain. If a tranche shows a loss, sell out.
  Book (Ch X, general): the first purchase is one fifth of the full position.
- Code:
  - `full_size` = the risk-based size. Tranche 1 = 0.2 × full_size (or 0.25).
  - Add the next tranche only if `close >= last_fill + k × ATR` (k about 1).
  - Stop adding when size = full_size, or when `open_risk + new_risk` would exceed the cap.
  - Move the stop on the whole position to at least break-even on the first tranche (or
    `last_fill - 2×ATR`) so that total risk never exceeds the original 1R.
  - Never add below the average cost (already enforced).
- Pat Hearne's variant (Ch X): add one unit every +1%, with a stop 1% below the last
  purchase that trails upward. This is a rigid "lose at most 1 point" pyramid. It is
  precisely codeable, but with daily bars and 1% noise it is almost certain to get
  whipsawed.

### 3.5 Initial stops and loss cutting (Ch VII, X, XII, XVII)
- Book: if the first purchase shows a loss, you were wrong, at least for now, so get out.
  Do not add. Do not average down. There is **no numeric stop** in the book apart from the
  bucket-shop margin and Hearne's 1 point. Livermore mostly used mental exits based on
  "behaviour".
- Code, simplest version: exit if `close < entry - s×ATR` (the bot already has this), or
  if the probe tranche is below entry after n days (a "must work quickly" time test,
  n = 5-10 days).

### 3.6 Exits for winners (Ch V, XIV, XVII, XVIII)
- Book: there are no profit targets. Hold as long as the tape says "not yet". Exit when
  (a) the trend changes, (b) after a reaction if the next rally fails, or (c) into a big,
  liquid move near the end, including a panic when you are on the right side.
- Code options:
  - (b) Failed-rally exit: after a pullback from a high H to a low L, if the next rally
    peaks below H and then `close < L`, exit. This is a lower-high / swing-low break, and a
    10-20 day low exit approximates it.
  - (c) Climax exit, long-only analogue: if `close > SMA50 × (1 + z)` or the day's range
    is more than 3×ATR with high volume, sell part of the position. Weak evidence; test
    only.
- Leader-failure exit (Ch XIV): exit a stock if its drawdown from its own 60-day high is
  greater than X (for example 10%), it has made no new high for N days, **and** the
  benchmark is within Y% of its own high. The idea is that the stock has stopped leading
  while the market has not.

### 3.7 Group / sector filter (Ch XVII)
- Book: do not buy a stock whose group is not acting bullishly. Do not buy the laggard of
  a strong group. Sell a stock that refuses to follow its group leader.
- Code: require the sector ETF (XLK, XLF, …) to be above its 50-day and 200-day SMAs, and
  the stock's 3- to 6-month return to be at least the sector median. Exit or skip if the
  stock's return over the last 20 days trails its sector by more than X while the sector
  is rising.

### 3.8 Regime ("general conditions") (Ch V, VII, VIII, XIV)
- Book: in a bull market buy and hold, and in a bear market sell. Study general
  conditions, not individual stocks. The tape confirms timing.
- Code: this is already done by the bot's SPY 200-day gate and the Faber 10-month SMA. The
  book offers nothing more precise.

### 3.9 Stay out of choppy markets (Ch II, X, XIV)
- Book: there are long stretches (1911-14) when nothing works, and forcing trades then
  only builds losses.
- Code: when the index is range-bound (for example an efficiency ratio or ADX below a
  threshold, or no N-day high or low for M days), turn off breakout entries. The bot's
  "choppy" regime already does this for sleeve C.

### 3.10 Order type (Ch III, IX)
- Book: he never traded with limits. When you want out, get out at market. His one
  attempt at limits meant he missed the move.
- Code: stop exits and failure exits are sent as market orders (or market-on-open), never
  as limits.

### 3.11 Position sizing
- **The book has no position-sizing rule.** He "plunged", went broke several times, and
  the only sizing advice is the anecdote "sell down to the sleeping point" (Ch X) and the
  rule that big positions are for trades already proven in profit. The fixed-fractional
  and "risk equalization" material in the file comes from **Covel**, not Lefèvre (see
  section 5).

### 3.12 "Pivotal points"
- **The term does not appear in this book.** It comes from Livermore's own later book,
  *How to Trade in Stocks* (1940). The closest ideas here are the range limits of 3.1,
  the new-high or round-number crossings of 3.2, and the Anaconda "should reach 310 without
  stopping" failure test. If the owner wants real pivotal-point rules, they need to be
  taken from the 1940 book, not this one.

### 3.13 Areas with no codeable content
Volatility targeting, portfolio heat, correlation limits, drawdown breakers, rebalancing,
costs and taxes. The book covers none of these, apart from warnings that execution and
slippage matter (Ch II, III, IX).

---

## 4. Psychology and discipline

- **Hope and fear are backwards.** Hope keeps you in losers and fear takes you out of
  winners. Deliberately reverse both (Ch X).
- **Don't argue with the tape.** Anger at the market is pointless; he compares it to being
  angry at your lungs for having pneumonia (Ch III, VIII, XXI).
- **Don't let your holdings think for you.** Many people are bullish because they own
  stocks rather than the reverse (Ch VIII). He even lost money projecting his own logic
  onto the insiders in Tropical Trading (Ch XVIII).
- **Play a lone hand.** Ignore tips, expert forecasts and friends' "inside" information.
  The most dangerous input is a brilliant, plausible person: Percy Thomas did not convince
  him, but talked him into indecision (Ch VI, XII, XVI).
- **Obligation is a hidden position.** His gratitude to Williamson stopped him acting on
  his own judgment, and it cost him years (Ch XIII).
- **Patience for entries and patience in holds.** He waited six weeks without trading
  before the Bethlehem trade (Ch XIV) and held the Tropical Trading short through rallies
  (Ch XVIII), but he also took losses instantly when he was wrong (Ch IX, XVII: the
  $1M cotton loss, then a clean reversal).
- **The need for action and daily income.** Professionals who feel they must "take home
  wages" every day lose money (Ch II, VIII).
- **Losses are tuition.** Study every mistake, add a new "don't" to the list, and forget
  the money overnight (Ch IV, V, X).
- **A swelled head after big wins.** His biggest disasters followed his biggest successes:
  after 1901, after 1907, and with the coffee and cotton trades (Ch XIII).
- **Fitness and a clear mind.** He slept early and did not drink during trading. Worry,
  debt and illness visibly degraded his results (Ch V, XIII, XIV).
- **Don't trade to pay for something.** A trade with a deadline and a target price is a
  gamble (Ch XII).
- **Pre-commit to protecting your capital.** He used trusts that even he could not raid
  (Ch XIV).

---

## 5. Claims to check

| Claim (chapter) | Status / how to test | Tension with modern evidence |
|---|---|---|
| Tape reading was right "seven out of ten cases" (Ch I, II) | Unverifiable anecdote. The book itself shows the edge vanished once real execution applied. | Retail short-term traders overwhelmingly lose (97% of persistent Brazilian day traders; 74-89% of EU CFD accounts). Treat as survivorship. |
| A stock that crosses 100/200/300 for the first time keeps going 30-50 points (Ch IX, XIV) | Test as a new all-time-high / 52-week-high breakout on the bot's universe, measuring forward 20/60-day returns against matched non-breakouts. | Partly consistent with the 52-week-high momentum effect (George & Hwang 2004). Round nominal numbers are meaningless after splits. Published effects shrink (about 58% post-publication, McLean & Pontiff). |
| Unexpected news usually agrees with the line of least resistance (Ch X, XIV) | Test whether earnings or overnight gap direction correlates with the prior 3-6 month trend. | Weakly consistent with momentum and post-earnings drift. The memoir cherry-picks cases, and his own cotton peace bet and the Lusitania break went against him. |
| Leaders stop rising before the bull market ends (Ch XIV) | Test breadth or leader-divergence signals ahead of S&P 200-day breaks. | Narrowing breadth before tops is documented anecdotally. As a timing signal it produces many false alarms. |
| Market moves 6-9 months ahead of the economy (Ch XXIV) | Broadly accepted (stocks are part of the Conference Board LEI). | The lead time varies a lot, and the market signals recessions that never come. It is not a trading rule. |
| Long declines are never "bear raids"; they reflect insiders selling on real bad news (Ch XV, XXIII) | Consistent with short-seller studies (short sellers are informed on average). | Modern insider *sales* carry much less information than insider buys. Reg FD and the SEC era changed disclosure. |
| Taking small profits early in a bull market is costly (Ch V) | Consistent with the disposition effect (Odean 1998): investors sell winners too soon and hold losers. | Supports letting winners run. |
| Buying dips because a stock is "cheap vs the top" is a sucker's play (Ch V, XXI) | Applies to individual stocks after a top. | Conflicts on the surface with sleeve B (RSI(2) dip buying). B buys index ETFs only above the 200-day and for days, not falling individual stocks, so the conflict is limited but real. RSI(2) edges have also decayed since publication. |
| No one can beat the market consistently (Ch X, XXIV) | Fully consistent with modern evidence (SPIVA, retail trader studies). | The hero's career is the proof: bankrupt several times in the book, and in real life Livermore went bankrupt again in 1934 (outside knowledge, not in the text). |
| Personal results: "150% per week" for three weeks (Ch XIII), $3M in 1916, more than $1M on 24 Oct 1907, $250k from the earthquake short | Unaudited and ghost-written. Treat as illustrations, not a track record. | Classic survivorship and narrative bias. |
| A mathematician's chart system won "regularly" until WWI broke all precedents (Ch V) | Anecdote about regime change and overfitting. | Consistent with edge decay and structural breaks. It argues for halving backtests and for robustness checks. |
| Execution lag and slippage erase short-term edges (Ch II, III, IX) | Consistent with modern cost studies. | Supports the bot's cost model and its daily or monthly holding periods. |

**How 1900-1923 markets differ from today's.** Bucket shops (betting against the house at
printed prices), ticker lag, 10% margin, fixed 1/8 commissions, legal pools and wash
sales, corners, no SEC (1934) or insider-trading law, no index funds, few listed stocks
(about 275-900), no ETFs, and a dominant commodity-futures culture. Most of Ch XIX-XXII
(manipulation techniques) describes practices that are now illegal or impossible.
Behavioural lessons carry over. Microstructure lessons do not.

**Material appended to the file (not Lefèvre) that also needs checking:**
- AQR's "Century of Evidence" backtest, as quoted in the Covel interview: time-series
  momentum returned about 20%/yr before fees, 1903-2012, scaled to 10% volatility. It is a
  *hypothetical* backtest across 59 futures markets, using **leverage and shorts**. The
  last decade shown (2003-12) was 11.4% gross. Trend-following CTAs also struggled through
  much of the 2010s. The bot cannot short or use leverage, so these figures do not
  transfer.
- Covel's "trend followers are not lucky monkeys": the list of billionaire trend
  followers is pure survivorship. His own table (Dunn, Winton, etc.) shows monthly win
  rates of only 38-47% needed to break even. That is useful for setting expectations.
- Covel's MTA piece suggests **5% risk per trade**. That is 10× the bot's 0.5% default and
  2.5× its hard cap. Reject it.
- Covel attributes the book to Livermore. The author is Lefèvre.

---

## 6. Fit with the bot

Context: the bot is small (~$10k simulated), long-only, daily bars, systematic, and uses
four sleeves. Claude sets weights within bounds, and the risk policy is enforced in code.
Many of Livermore's methods (tape reading, shorting, commodities, plunging, manipulation)
cannot be used here.

| Lesson / rule | Bot today | Verdict |
|---|---|---|
| Trend / "general conditions" regime (L6, 3.8) | Yes. Faber 10-month SMA in A, SPY > 200-day gate for B/C, regime classifier. | **Already done.** Nothing to add. |
| Sit tight, no profit targets, let winners run (L6, 3.6) | Yes. A holds until the monthly signal flips. C exits on a 10-day low or 50-day SMA, with no target. | **Already done.** Don't add targets. |
| Cut losers fast, never average down, never widen stops (L11, 3.5) | Yes. ATR stops, `no_averaging_down`, `never_widen_stop`. | **Already done.** |
| Range breakout / line of least resistance (3.1) | Mostly. C buys a close above the 50-day pivot high on 1.5× volume. | **Already done.** Optional research: add a range-tightness filter (only breakouts from ranges narrower than W%) and compare. Don't change without a backtest. |
| New-high / "crossing par" entry (3.2) | Partly. C requires price within 25% of the 52-week high, plus the pivot. | **Research only.** Test "close at a new 52-week or all-time high" as C's trigger against the current 50-day pivot. Reject the round-number version. |
| Breakout-failure exit (Anaconda, 3.2) | No explicit rule. The 2-ATR stop and 10-day low catch failures later. | **Candidate for sleeve C (test).** Exit if price closes back below the pivot within 3-5 days of entry. It could cut average loss size, but it could also add whipsaw. Backtest before use. |
| Pyramiding: probe first, add only on profit (L8-9, 3.4) | No. C enters full size at once. | **Test, don't adopt yet.** C is on probation with few trades, so extra rules are premature and would muddy the ≥100-trade evaluation. If tested: tranche 1 = 50% of 0.5% risk, add 50% at +1 ATR, stop raised so total risk stays ≤ 1R, and heat must stay within 6%. **Reject for A and B.** A is allocation, not trades, and B is mean reversion, where adding to winners makes no sense. |
| Confirm before size (3.3) | Implicitly, through the rule that risk goes to 1% only after ≥100 trades with positive expectancy. | **Already done at the policy level.** Adding a rule to raise sleeve risk only when the sleeve's open trades are in profit is not worth the complexity at this size. |
| Group / sector confirmation, no laggards (3.7) | No. C uses RS ≥ 70th percentile across a 40-stock universe but has no sector check. | **Candidate for sleeve C (test).** Require the stock's sector ETF to be above its 50-day SMA. It is cheap to compute and matches Minervini's own practice. Needs a backtest, and with 40 stocks some sectors have only 1-3 names. |
| Leader-failure exit (3.6, Ch XIV) | No. | **Low priority.** It overlaps with the 10-day low and 50-day SMA exits. Skip unless the backtest shows C giving back big open profits. |
| Stay out of choppy markets (L4, 3.9) | Yes. The "choppy" regime turns C off and halves B. | **Already done.** |
| Don't trade all the time (L4) | Yes. `max_orders_per_day` 10, rebalance band 20%, monthly A signal. | **Already done.** Consistent with the playbook's own note that activity itself is the main source of loss. |
| Market orders for exits (3.10) | Check broker.py. | **Adopt if not already the case.** Stop and failure exits should be market or market-on-open, never limits. |
| Climax / panic exits (3.6c) | No. | **Reject.** They are mostly about covering shorts. For a long-only daily system the evidence is weak and it cuts the right tail that pays for C. |
| Shorting in bear markets, and short failed leaders (Ch VIII, XIV) | Not allowed (`shorts: false`). | **Reject.** It is outside the account's mandate. The bear-market response is cash or T-bills (A → BIL, B/C off), which is the long-only equivalent. |
| Tape reading, test orders, reading "absorption" | Not possible on daily bars. | **Reject.** The volume multiple on C's breakout day is the only usable proxy, and it already exists. |
| Sizing "down to the sleeping point", small probes | 0.5% risk per trade, 2% hard cap, 6% heat, drawdown breakers. | **Already stricter than the book.** Reject any Livermore-style plunging or Covel's 5% per trade. |
| Unforeseeable events (L17) | Drawdown breakers, stops, 5% cash buffer, per-name caps. | **Already done.** No more is needed. |
| Lock away profits (L18) | Not applicable to a paper account. | **Note only.** For a real account later, the owner could sweep profits above a high-water mark out of the trading account. That is a human decision, not bot code. |
| **Ignore tips, narratives and persuasive experts (L13)** | Partly. Rules are code-enforced, but Claude chooses weights within bands and reads context. | **Add to the Claude-book prompt or policy.** This is the most relevant lesson for an LLM trader. Claude reading news or analyst narratives is in Livingston's position with Percy Thomas. Proposed rule: Claude may not tilt a sleeve's weight for a reason that is not a price, volatility or regime signal the code computes, and each tilt must be logged with the numeric signal behind it. |
| **Score your predictions (L2)** | Unknown (check state.py / journal). | **Add if missing.** Have Claude write a dated, falsifiable expectation for each weight decision (direction and horizon), and have code score the hit rate over time. This is the book's "little book of hits and misses". It tells the owner whether Claude's discretion adds anything over the rules book. |
| Dip buying is a sucker's play (Ch V) | Sleeve B buys RSI(2) dips. | **Keep B, but watch it.** B is not what Livermore criticised: it trades index ETFs, requires an uptrend (close > 200-day) and holds for days. Still, the book and the decay literature both say B's edge is the least certain. Keep B at the lower end of its 15-25% band until live results justify more. |

### Bottom line for the bot
The bot already has the parts of Livermore's method that survive modern evidence: a
regime/trend filter, entries on confirmation, small fixed risk, fast loss-cutting, no
averaging down, no targets on trend trades, and low activity. The additions worth testing
are all in sleeve C: a breakout-failure exit, a sector-confirmation filter, and possibly
pyramiding. None should go live without a backtest that respects the playbook's "halve
the backtest" rule. The most valuable non-code lesson is about Claude itself: treat
narratives, news and confident expert opinion as the "tips" of the book, allow them no
weight except through price-based rules, and keep a scored log of Claude's own calls.
