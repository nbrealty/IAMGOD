# Teaching the agent to read charts: what we found, and the plan (29 Sept 2026)

*For the owner, who is new to trading and to code. Written by the minute-trading session. It pulls together seven research
reports (R1 to R7), a small blind picture-reading test (R8) and four independent fact-checks. **Read
`00 Fact-check corrections (read first).md` first: it supersedes some numbers in R1 to R7.** Nothing here changes the live
paper bot, and no order was placed for this work. A short glossary is at the end. "bp" means a basis point, 0.01%; on one SPY share (about $766) 1 bp is about 7.7 cents.*

## If you read nothing else

1. **Code should read the charts. The AI may explain and veto, but it should not pick trades or read numbers off pictures** (one
   exception worth trying: turning your cousin's screenshots into notes, with every number checked by code).
2. **We found no chart technique with strong proof of working after costs at the minute level on SPY or QQQ.** Our searches
   ran out, so "found no test" is not "proved useless".
3. **A minute bot struggles because costs are as big as the moves.** A round trip costs about 1 to 3 bp and a typical 1-minute
   move is about 1.5 bp, so a 1-minute trade cannot pay for itself; only holds of about 30 minutes or more have a chance.
4. **"10X more efficient than humans" is a fair description of the design** for watching many charts, following rules, keeping
   records and testing ideas quickly, but none of it is measured yet. For profit it is undefined.
5. **The most likely honest result of the next tests is "no net edge found".** The value is clean records, a map of when *not*
   to trade, and finding out early what does not work. Nothing changes in the live bot. The next step is Wave 1 (at least 114
   small tests on old data); it needs your OK, and most will probably say "not shown".
6. **What I need from you** is in section 7.5: your cousin's screens, rules and a journal of trades he skipped, and a short
   list of decisions. **Urgent, unrelated to charts:** the data-rights check found that this GitHub repository is public
   (section 7.5, item 9).

---

## 1. The findings

1. **Traders who watch many screens usually work as a funnel, not as ten separate opinions** (common practice according to R1).
   We do not yet know whether your cousin does; that is the first thing to ask him. The funnel: a risk-and-news check, then
   the weekly and daily trend, then a map of important prices, then the type of day, then a 5-minute setup, then a 1-minute
   entry. The higher chart can veto; the lower chart only times the entry. (R1)
2. **No chart technique has strong proof of working after costs at the minute level on SPY or QQQ.** The ideas with the most
   support are slow trends over 1 to 12 months (a way to cut big losses, not to earn more), forecasting *how big* moves will
   be (not which way), and one small late-day effect worth about 1 bp a trade before costs, about what it costs to get in and
   out (our own test of it lost money after costs). For candlesticks, Fibonacci, Elliott waves and hand-drawn trendlines we
   found no test showing a profit after costs. For classic chart patterns, one careful study found a little information but
   no stand-alone profit. (R2, R3)
3. **Real trend versus hype.** Randomness often looks like a trend: about 1 random price path in 7 gets a good straight-line fit
   (R-squared above 0.8), and a popular trend gauge (ADX above 25, meant to say "strong trend") false-alarms on about 4 bars in
   10. A "trend quality" score has not been shown to predict the next hour or day for SPY or QQQ. In stocks, attention spikes
   are usually followed by a fade or by nothing, but not always. Social-media text has small, short-lived value, mostly
   measured before 2021, and manipulation is documented. (R5)
4. **Options numbers say how big a move might be, not which way.** "Gamma level" maps rest on a guess about which side the
   option dealers are on. Retail option buyers lost money on average in the studies we found; how much, and why, is disputed,
   and sellers of short-dated options did better in two of them. Our own rough pricing-model test says same-day options on
   these signals lose (the direction is not in doubt; the size, about 4% to 38% of the premium at realistic costs, is uncertain). (R4)
5. **Long-term stocks: a trend rule cuts big losses at the price of lagging in most good years. It is not a money machine.**
   Looking back (in hindsight, before trading costs and taxes), owning the market only while it is above its 10-month
   average would have made 9.8% a year against 10.3% for simply holding (1927 to 2026), with a worst loss of -43% instead of -84%. It was behind in 44 of 98 years, and fast V-shaped
   drops (April 2025, March-April 2026) made it sell low. (R6)
6. **Can the AI read charts?** On clean charts with the rule written in the question: yes. 97.8% of 1,224 answers were right,
   and two passes by the same model agreed. Predicting the next 30 minutes from a picture: we saw no skill (28 right out of 72
   answers, which is only 36 pictures read twice, so a small skill could hide). Its 0-to-10 "clear and tradeable" ratings of
   random-walk pictures came out about as high as for real days (5.8 against 5.5 on the 1-minute charts; 24 real against 12
   random pictures, so a gap of about a point could hide). So code reads the charts; the AI may veto and explain. (R7, R8)
7. **"10X more efficient than humans."** By design, in code: coverage, consistency, record-keeping, research speed and cost per
   decision. Not yet measured. Undefined for profit. Testing 1,000 times more ideas does not by itself find an edge; it makes a lucky result more
   likely. With no skill at all, the best of 28 tries already scores 1.42 on the Sharpe scale (return per unit of ups and
   downs) over two years, 258 tries give 2.0 and 1,000 give about 2.3, so each new idea must clear a higher bar. (R7)
8. **The cost hurdle.** Getting in and out of one SPY share costs about 0.5 bp if the spread (the gap between the buy and
   sell price) is 2 cents (the spread plus a regulatory fee). We saw that on one day of quotes and still have to measure it on our own fills. We plan for 1 bp to
   3 bp, and the lab's headline results use 3 bp. In the 40 calm sessions we measured, the average size of a 1-minute move, up or down, was
   only 1.5 bp. If wins and losses are each about one average move, at 1 bp you must be right 82% of the time on a 1-minute trade just
   to break even. At 3 bp it cannot be done at 1 minute, and even a 60-minute hold needs 63%. In a normal, more volatile year
   the moves are bigger and these hurdles are lower (the "typical 15% a year" volatility is R3's assumption; nobody checked
   it). (R3)
9. **How long it takes to tell luck from an edge.** For a trade held about 30 minutes, telling a real +1 bp edge from luck (at
   our bar of t = 3) takes about 2,100 trades, which is about 8.5 years at one trade a day. Sixty paper sessions could only
   reveal an edge of about 4 bp at the usual 1-in-20 luck test, or about 6 bp at our stricter bar. That is why paper trading here
   teaches mechanics and measures costs but cannot prove an edge. (R3)
10. **Published edges tend to fade, but our evidence for minute setups is thin.** Three 2026 preprints (each by one author, not
   peer reviewed, and we read them as abstracts only) point the same way. The popular SPY momentum system's Sharpe score fell
   from 1.34 to 0.39 after the original data ended, and one shows it down about 8% from Sep 2025 to Aug 2026. Another found none
   of 225 opening-range variants beat costs, on nine futures markets rather than SPY or QQQ. Our own 2024-26 test shows the
   same fade for the 5-minute opening range breakout (that is the same stretch of time, not a separate check). One author
   allows that the drop may just be an ordinary bad patch. Treat this as a warning, not a measurement. (R3, corrections file)
11. **So the plan is measurement first:** build a code-only Reader, a complete log, and a small set of tests on old data that
    can drop ideas (only fresh, forward data can confirm them). A bot with no edge does not break even; it slowly loses the
    cost of each trade. So the value of this work is clean records, a map of when not to trade, and finding out early that
    something does not work.

---

## 2. How a person reads many charts (R1)

*This describes how people read charts, not what makes money (see section 3). Chart reading is mostly about deciding where you
would be proved wrong, not a crystal ball.*

| Chart | Question it answers | Typical tools |
|---|---|---|
| Weekly / monthly | What is the big trend and where are the big shelves? | 10/30-week averages, last week's and month's high and low |
| Daily | Trend, how big is a normal day, what is the plan? | 20/50/200-day averages, ATR (the typical daily range), yesterday's high, low and close, gaps |
| 1-hour / 15-minute | What setup is forming, where is the opening range? | Averages, VWAP, opening-range edges |
| 5-minute | The trigger and management chart | 9/20 EMA, VWAP, bar patterns |
| 1-minute | Exact entry and stop placement | Previous bar's high and low, VWAP reclaim |

**Order of authority:** (1) risk rules and the news calendar (a hard veto; in our bot this is code); (2) the higher-timeframe
trend (can veto a *direction*, never creates a trade); (3) the setup chart (is there a valid setup?); (4) the trigger chart
(decides *when*, never overrides 1 to 3); (5) if the timeframes disagree and the higher one has no clear view, **stand
aside**.

What the research adds:
- **Ten indicators built from the same prices are one opinion said ten ways.** Nested time windows agree by construction, so
  "the 5-minute and the 15-minute agree" is not independent confirmation (R5). We found no evidence that combining
  timeframes helps (R2), and a weekly-plus-daily combination did worse than simple rules in R6's test.
- Of the roughly 90 items R1 catalogued, about half are exact formulas, about a third need judgment calls, and the rest are
  largely discretionary. Most of the sources claiming these methods work sell books, courses or data. None is shown by our
  data to make money.
- **R1's untested hypothesis:** if a discretionary trader has an edge, it is more likely in *which days and moments he
  refuses to trade* and *how he exits* than in his entry pattern. Both can be recorded and tested, which is why the plan asks
  for your cousin's journal, including the trades he skipped.
- **What humans do that is hard to code:** judging the "best" pullback, tape feel, reading exhaustion versus strength. Until
  written as rules or logged in a journal, these cannot be tested.

## 3. Evidence scoreboard: what to teach the agent

*Only volatility forecasting is rated strong, and it says how big a move will be, not which way. Every other row is a limited
yes, log-only, or no.*

| Idea | Evidence found | What to do |
|---|---|---|
| Forecasting the size of moves (volatility clustering and the VIX level; VIX1D and term structure are mixed, SKEW and VVIX weak: log only) | **Strong for volatility clustering and the VIX level as forecasts** (not direction) | **Yes:** as gates that skip a day or a trade (changing trade *size* with volatility would break the fixed-size rule MT-G14 and needs a new registered version and your written OK) |
| Trend following, 1 to 12 months | Mixed and contested; cuts big losses, does not add return | Yes, as a slow overlay, in shadow first |
| Relative-strength / momentum stocks | Mixed, decaying; costs take 34% to 53% of gross profit; crash risk | Not now (needs survivorship-free data) |
| 52-week-high nearness | Mixed | Later |
| Intraday momentum, first to last half hour | Mixed; about 1 bp; still found in 2000-2020 in futures, before costs (Baltussen); our own LAST30 gross rose from -1.5 bp (2024) to +1.3 bp (2026) but stays negative after costs at the lab's 3 bp. The systems that appear to have faded are the noise-band and opening-range ones (two 2026 preprints and our own ORB5 test) | Test one version (big-move days) |
| Support, resistance and round numbers | Orders do cluster there; no profit test found | Test "real levels versus fake levels" |
| Volume confirmation | Little added information | Log time-of-day-normalised volume only |
| VWAP rules | Vendor and educator claims only | A feature, not a signal |
| Predicting trend day versus range day | Nothing rigorous found | Descriptive tag only |
| Classic chart patterns (head and shoulders, flags, triangles) | Weak to mixed: some information in one study, little or no stand-alone profit in follow-ups | **No** (as triggers) |
| Candlesticks, Fibonacci, Elliott, hand-drawn trendlines, stand-alone RSI/MACD/Stochastic/Bollinger | Candlesticks: the careful test (5-minute Dow stocks, after allowing for the number of rules tried) found no rule that beat buy-and-hold after costs; a few small positive studies (Taiwan, the Dow 30) did not state costs. RSI, MACD: weak; a few variants beat buy-and-hold after costs in old samples, with no allowance for trying many. Bollinger: no supportive test found. Stochastic: barely tested. Fibonacci, Elliott, drawn trendlines: barely tested or subjective. We found no profit after costs that held up once the number of tries is allowed for (our searches ran out) | **No** |
| "Multi-timeframe agreement" as proof | No test found; worse in one test | **No** |
| Order flow, ES-SPY lead-lag, news speed | Real, but it lives at milliseconds | **No** (out of reach) |
| Gamma levels, put/call, skew or "unusual options activity" as direction | Weak or none | **No** (VIX gauges as volatility: yes) |
| Social-media or news text as an input | Small, short-lived, manipulable | Shadow only, quarantined |
| Machine learning on chart images | Mixed: strong on paper for equal-weighted small stocks (Sharpe about 2.2 to 2.4), weak value-weighted (about 0.45 to 0.49); much of it is rescaling; turnover about 175% to 187% a month | Research candidate only; not for SPY or QQQ minute charts |
| AI reading pictures to predict | None (39% in a tiny test here; 49% to 53% direction accuracy in one 2026 paper, coin-flip AUC in another) | **No** |

## 4. Real trend versus hype: what the agent should measure (R5)

- **Judge a "trend quality" score against a simpler number:** how big the move was compared with the normal wobble over the
  same time. A score is only useful if it tells us something that number does not. Fixed textbook cut-offs are met by pure
  noise often: about 15% of windows (R-squared above 0.8), 37% to 40% of bars (ADX above 25) and 56% to 92% of paths (a
  Mann-Kendall trend test), depending on the test and window length. There is also a limit to what two years of data can
  show: we could only notice a trend-quality signal that moves the next hour's price by at least about 1.3 bp for each
  normal-sized change in the signal (our own rough estimate). That is about what a round trip costs, so a signal we could just
  notice would barely pay for itself, and a smaller one we could not notice at all.
- **Hype**, measured from price and volume only: an unscheduled volume spike, an unexplained gap, a spike-and-fade shape. In
  stocks, attention spikes are usually followed by a fade or by nothing, but not always: some rise for a few weeks first, and
  moves backed by real news tend to continue. (For example, the stocks Robinhood users bought most each day did 4.7% worse
  than expected over the next 20 days.) That is why hype is used here only as a warning sign, never as a signal. We expect
  SPY and QQQ to show these features rarely, so there may be too few events to test; we will count them first.
- **Social text:** we would collect it only through the platforms' official interfaces, and only after checking their terms
  (not yet done). It is stored apart from the bot and never read by the order code (MT-G23, MT-G24). If an AI ever scores it,
  company names and tickers are masked first and only data after the AI's training cutoff is used (MT-G30). Its value was
  mostly measured before 2021; an LLM headline-trading result fell from an annualised Sharpe of 6.5 in one quarter to 1.2 in
  early 2024, and loses money at 20 bp of cost. Not part of Wave 1; needs your OK (section 7.5).
- Yesterday's move in the whole US stock market (not SPY alone) used to help predict today's (before about 1995). It no
  longer does: since 2000 the link is near zero or slightly negative (the -0.10 for 2010-26 is mostly the 2020 crash year; without it, -0.03).

## 5. Minute trading and options: the honest numbers (R3, R4)

| Holding time | Average move | Win rate needed to break even at 0.47 bp cost | at 1 bp | at 3 bp (the lab's cautious level) |
|---|---|---|---|---|
| 1 minute | 1.54 bp | 65% | 82% | impossible |
| 5 minutes | 3.46 bp | 57% | 64% | 93% |
| 30 minutes | 8.62 bp | 53% | 56% | 67% |

*These averages are SPY's, from 40 calm sessions (Aug to Sep 2026; realised volatility about 6.9% a year against a
"typical" 15%, which is R3's assumption and was not checked). In a typical year moves would be about twice as large and the
hurdles correspondingly lower. They also assume a win and a loss are each about one
average move.*

*Reading it: a 1-minute trade needs a win rate no published pattern comes near. A 30-minute trade needs 53% to 56% at low
costs, and 67% at 3 bp.* A pattern that explains about 2% of price moves would be right about 54% of the time (R3's own
conversion of the best-documented effect, late-day momentum), so it only just clears the cost of a 30-minute trade if costs
are at the low end, and published patterns have been fading. **Faster things, such as order flow and futures lead-lag, are won
at millisecond speed by firms with direct feeds; a cloud bot on a free IEX feed cannot play that game.**

For options, the useful *free* information is a volatility yardstick (Cboe's VIX and VIX1D
files, used only to skip quiet or wild days; VIX9D, VIX3M, VVIX and SKEW are logged only). Costs are higher than R4 first said: in our pricing model an at-the-money SPY call that expires 25
minutes after purchase costs about 30 cents (a model price, not a quote). If the half-spread is 1 cent (an assumption; we have no real option quotes),
paying it each way costs about 3% going in and 3% going out, 5% to 7% in all. Cboe's terms are restrictive (personal,
non-commercial use, and no clear permission for scheduled downloads), so the files stay private and are never committed
(decision 8 in section 7.5).

## 6. Long-term stocks (R6)

We re-ran these rules on public data. Two independent checkers reproduced the first row (month-end data from Kenneth French's
library) and the July-August 2026 momentum fall in the last row; the other rows are R6's own calculations. Rows 2 and 3 use Yahoo prices
that R6 itself marks unverified; row 4 uses French data that nobody re-ran. All are hindsight back-tests and none includes
taxes. Rows 1 and 4 are before trading costs (row 1 would make about 9.7% a year with 10 bp charged per switch); rows 2 and 3
already charge 5 to 10 bp a switch. About 30 variants were tried, and some periods were chosen after looking,
so they describe history; they do not test the rules. Orders are sent for the next open.

| Rule | Honest result | When it lagged |
|---|---|---|
| Hold the index only while it is above its 10-month average (month-end closes) | Would have made 9.8% a year against 10.3% for holding (1927 to Aug 2026); worst loss -43% instead of -84% | Behind in 44 of 98 years (ahead in 22, level in 32); $1 became $5.6 against $13.2 since April 2009 |
| Hold SPY or QQQ only while above the 200-day average | SPY 1993-2026: 8.6% vs 10.9%, worst loss -24.5% vs -55.2% | QQQ 2010-2019: 8.1% vs 17.9% a year. SPY flipped in and out nine times between 21 Jan and 11 Apr 2022 (a cost) but finished 2022 ahead (SPY -12.5% vs -18.2%; QQQ -16.4% vs -32.6%) |
| Hold each of five broad ETFs only while it is above its own 10-month average (the 12-month version was tested on US stocks only) | Five ETFs 2007-2026: 5.5% a year against 11.0% for SPY, worst loss -11% against -51%; US stocks with the 12-month rule 1927-2026: 10.0% a year, worst loss -44% | 2013-2019 for the five-ETF version (about 4.6% a year against 14.6% for SPY) |
| Scale exposure to volatility (no leverage) | Smaller drawdowns (-45% vs -84% on US stocks since 1927), but since 2013 no better risk-adjusted return and 10.4% vs 15.0% a year | Long bull markets |
| Buy recent winners (12-1 momentum) with a market filter | Highest costs and crash risk (July-August 2026: the top group fell 15.5% value-weighted while the market rose 2.6%) | Needs data we do not have |

CAN SLIM, Minervini, Weinstein and Darvas: no independent test found. **Expect a trend rule to look worse than buying SPY in
most bull years.** It also leaves you under water for two to seven years in a real bear market, and it cannot be proven in a
60-session paper run. A rule-following bot's real advantage here is discipline, not extra return: applying the same rule every day,
rebalancing on schedule, never chasing top gainers, and logging every skipped signal. (Scanning 500+ stocks would be a job for
the stock books, not this bot.)

## 7. The plan

### 7.1 What the agent should be: three layers

1. **Reader (plain code).** A program that, after each finished bar, writes a fixed report for SPY and QQQ at five chart
   speeds (1, 5, 15 and 60 minutes, and daily). Each report says whether the price is trending up, down or sideways and how
   strongly; whether it is above or below the day's volume-weighted average price (VWAP); how big today's range is compared with
   normal; how far it is from yesterday's high and low; whether volume is normal for this time of day; how wide the spread is;
   whether a news release is close; and which data feed and how old the data is. Each report gets a fingerprint (a hash) so we
   can replay exactly what the bot saw. R1 listed 59 such measurements (38 free and live, 16 needing the delayed full feed, 5
   not on Alpaca). We log all of them and let at most about six touch a decision, and only as gates. Because it is plain code
   it is exact, free, and can be tested against charts whose answers we planted (R8 did something similar for the AI's picture
   reading: it scored the AI's answers against answers computed by code).
2. **Deciders (compete under the rules we already have).** Cash, frozen human-inspired rules, a simple statistical rule
   (moving-average or volatility timing, on/off only; trade size never changes, MT-G14) and buy-and-hold. Everything is frozen before evaluation and every variant is
   counted. A learned model is a separate, later project with strict access control to the final test (your decision of
   28 Sept); stop rule 3 below applies only if that project is ever started.
3. **AI (veto and explain only, MT-G29).** It is never in the order path and is not asked about single trades. Before the open,
   and at most every 30 minutes, it reads the Reader's numbers and may post a standing veto ("no ORB5 today", "no QQQ until
   11:00") or raise a flag, each with a reason code and an expiry time. Each question is asked three times and a veto counts
   only if two of three agree (MT-G32). The order code only reads the list of vetoes. If the AI is down or late there is no
   veto and the bot carries on. It may not write prices, sizes or levels. Every trade a veto blocks is still simulated so the
   veto can be scored. R7's design goes further (an ALLOW or VETO on every candidate trade, its Test D). That is not part of Wave 1 or the
   first build. It would need an amendment to MT-G29 and your written OK, and would start as shadow scoring only. The live bot has no AI in v1: this layer is a later step and needs your OK, an API
   budget and, per the data-rights register, Alpaca's written answer on sending market data to an AI model. Pictures are not
   used for decisions.

### 7.2 Wave 1: a pre-registered set of tests on old data (at least 114 new trials)

Rules for the wave: each test is written down, stamped with a fingerprint (a hash) so it cannot be changed quietly, and counted
before it runs (MT-G6, MT-G7). We run it on 2016 to Aug 2024 prices, charging 1 bp and 3 bp for a round trip (0.5 and 1.5 bp
each way), and re-shuffle whole trading days to see how much luck alone could produce. An idea that fails drops off the list
as "not shown". An idea that survives becomes a candidate, nothing more. The Sept 2024 to Sept 2026 data is not a clean final
test: the earlier 14-setup run already used it and part of it is inside the AI's training period, so we use it only as an extra
check that can knock an idea out. **Old data can drop an idea only if its effect would have been big enough to see. A +1 bp
edge needs about 2,100 trades to see. The late-day test will have only about 490 trades and can see effects of about 2 bp or
more (more at our stricter bar), and the gap-fade test only above about 8 bp. Smaller real effects would be missed. Nothing
is confirmed until an idea, registered in advance, works on data that arrives after it was registered (MT-G6).** The AI plays
no part in Wave 1 (MT-G30 forbids scoring an AI on data from before its training cutoff).

Wave 1 is at least 114 *new* trials (the list and how they are counted are in Appendix A). The "deflated" bar must
count them on top of everything already tried across the whole minute project (MT-G7): at least the 28 from the first
backtest and the rule variants R5 and R6 tried while looking, plus the two ChatGPT-spec strategies once they are
registered. Surviving Wave 1 makes an idea a candidate, not a pass: it still has to clear MT-G1, G5 and G7 (t of at
least 3, deflated-Sharpe probability at least 0.95, PBO at most 0.20, and a reality-check p below 0.05) on forward data. The Wave 1 build
includes the test machinery that does not exist yet (MT-G5, G6, G7, G42) and the two known random-baseline fixes from the
brief. All Wave 1 exits are set at 15:50 or earlier (MT-G20).

Not tested in Wave 1: order flow, futures lead-lag, gamma levels, unusual options activity (no data), the day-type-at-10:30 and
breadth tests (R1 T6 and T7, later), the top-20 stock scanner (against MT-G23), a state router and a breakout-retest strategy
(new registered versions later).

**Expected outcome, stated now so nobody loosens a rule later:** most of these will come back "not shown". The value is a map
of when *not* to trade, a ranked list of survivors to watch forward, and a test machine we can trust.

### 7.3 Forward logging that can start without touching the live bot

Most Reader features use only completed bars, so they can be computed each evening from that day's full-market (SIP) bars,
15 minutes after they exist. A nightly job can write those context snapshots and the forward outcomes (+5, +30, +60 minutes
and the close) into a folder of its own, with **no change to the running bot**. Some features need data that are not Alpaca
bars (earnings calendar, VIX-family, futures, Cboe statistics), SIP trade data, or option open-interest and chain snapshots
that Alpaca serves only as "current" and that must be saved every day; those need a small daily capture job. The AI-veto
scoring and the spread features need real-time capture and come later. What cannot be recovered later is real-time
information: live quotes and spreads, and the AI's answers and delays. Price bars can be downloaded again any time. But a test
only counts as forward evidence if it was registered before the data arrived, so registering early starts that clock.

### 7.4 The "10X" scorecard and the stop rules

| Dimension | Human, typically | Bot, plausibly | Better by design? |
|---|---|---|---|
| Charts watched at once | About 4 things in working memory (R7's citation) | Every timeframe of every allowed symbol on every bar | Yes for code, but the universe is only SPY and QQQ (MT-G23), and watching more charts only helps if each one has skill (R7) |
| Reaction time | Seconds | Milliseconds for code. The AI is kept out of the order path (MT-G29) | Yes for code; not applicable to the AI |
| Following its own rules | Sells winners early, chases losses | Rules are enforced by code, so a broken rule shows up as a bug we can find, not a lapse of willpower (code can still have bugs, which is why there are tests, dry runs and an outside watchdog) | Yes for code; not for an AI's judgement |
| Ideas tested per week | A few (R7's assumption) | Hundreds, but each raises the bar | Yes, but it is not edge |
| Cost per decision | Time and attention | Code: nothing. AI: the cost per run is unverified (R7 guesses a few cents at most), and there are three runs per check (MT-G32). We log the real cost and keep the AI only if its vetoes save more than it costs (MT-G34) | Unproven |
| Record keeping | Partial (R7's assumption) | Every input, code version, reason and latency, replayable | Yes, a genuine and cheap advantage |
| Profit after all costs | Most lose (97% of persistent Brazilian day traders lost; under 1% of Taiwanese day traders were predictably profitable) | A small net loss (each trade pays costs), unless a real edge is found | **Undefined** |

*These "Yes" answers say what the design allows. None is measured yet; R7 section 4.3 lists how each would be measured.
Bottom line: by design, code should be far better than a person at coverage, record-keeping and rule-following. That is
unmeasured, unproven for the AI, and undefined for profit.*

**Stop rules (need your OK, section 7.5):**
1. If a model fails the planted-truth reading audit (it states numbers that are not in the data, or scores under 98% on
   the questions about what a chart shows), no model gets a numeric role. The picture reader (R8) was above the line pooled over the 15
   core questions (99.3%; three of the fifteen were 97.2% each) and clearly below it on the hardest (largest gap, 86.8%).
2. After 100 AI decisions the veto stays on only if its scored value exceeds its cost (MT-G34). Separately, if after at least
   40 sessions (MT-G11) the trades it blocked were not clearly worse than the trades it allowed, remove it.
3. If a learned-model project is ever started, it must beat frozen rules on paired daily net results with the lower 95% bound
   above zero, or it stops.
4. If all-in running costs (data, AI, hosting) exceed what the measurements show they add compared with doing nothing (cash), stop.
5. If a planted fake passes a test, or results halve from old to new data, stop and audit.
6. Time box: two quarters from the day Wave 1 starts, or sooner if the number of ideas tried makes the bar higher than our
   data can ever clear.

### 7.5 What I need from you

1. **Your cousin.** His layout (a screenshot), the indicators on each chart, what makes him call a trend day, one real entry
   with the chart at that moment (for writing his rules down, not as proof; we may ask the AI to turn a screenshot into notes, with code checking every number: untested, R8 section 5), where he puts stops and targets, and, possibly the most valuable (R1's untested idea), a journal of the trades he *skipped* and why. Please write each skipped trade at the moment he skips it, with the
   time, before he knows how it turned out. No report may call his rules "working" until there are at least 100 closed paper
   trades over at least 40 sessions (MT-G11); at about one trade a day that is roughly five months, and the paper test's own
   rule reports to you after 60 trading days, so you would need to extend it. His claimed results and
   screenshots of winning trades are not evidence (MT-G24).
2. **OK to build and run Wave 1.** It needs no data fees and places no orders, but it is a real build (two independent
   reviewers, as before) including the test machinery that is missing (MT-G5, G6, G7, G42) and the two random-baseline fixes.
   Time and effort are not yet estimated. Suggested answer: yes.
3. **Optional, later:** one month of real options data ($99) to measure what a compliant defined-risk options spread really
   costs. Not needed for anything above.
4. **Nightly forward logging (7.3):** OK to start? No orders, no change to the bot; it writes to a folder of its own. Suggested answer: yes.
5. **The stop rules and the two-quarter time box (7.4):** OK as written, or changed?
6. **Social-text collection (section 4):** in or out? If in, we first check each platform's terms and cost (not yet
   verified); nothing is collected until you say yes. Suggested answer: out for now.
7. **Stock-book notes (7.6):** OK to pass these two notes to the operations session?
8. **Cboe files:** the checkers found the terms do not clearly allow scheduled downloads even for private use. Email
   permissions@cboe.com first, or accept that for private research? My suggestion: email first. Until Cboe answers, the files
   are not downloaded on a schedule and block B's three Cboe trials wait. The files are never committed either way.
9. **Data rights (urgent part):** the data-rights register (`Data rights register.md`, read its section 0) found that this GitHub
   repository is **public**, not private, and that it holds market-data files and copyrighted book PDFs from earlier work that
   others can download. Please check Settings, General, Danger Zone in GitHub today and make it private if you meant it to be.
   It also says Alpaca's terms are silent on sending market data (or pictures made from it) to an AI model, so the AI layer and
   any repeat of the picture test wait for Alpaca's written answer. I have not changed any repository setting.

### 7.6 For the operations session (not touched here)

- Slow trend overlay on SPY and QQQ as a code-only risk overlay for the stock books: in shadow first, with 3 to 5
  pre-registered rules and an honest note that it cuts losses, does not add return, and cannot be proven in a short paper
  run (R6).
- Splitting the options lab's proxy loss into spread, volatility assumption and signal (R4 H3), which needs their saved
  trades; R4 says the 33% average loss is larger than spreads alone explain.

### 7.7 Unchanged

The live paper bot (ORB5_QQQ and LAST30_MOM_SPY placing orders in the exploratory lane; NOISE_MOM_SPY watch-only), all
guardrails, all caps and the schedule. Nothing in this plan is enabled in the bot without independent review and your OK.

---

## 8. Limits of this work

- The seven researchers each ran out of web searches (200), so 2024-2026 academic coverage is thinner than it
  looks; several sources were abstract-only. Details are in each report's "could not verify" section.
- The four checkers went through 28 key claims, two checkers each; the rest of R1 to R7 is as written by one researcher.
- The 2-cent stock spread and the option half-spread are assumptions until measured on our own fills.
- `Data rights register.md` is one researcher's reading of published terms, with quotes and addresses; it is not legal advice, and
  it has had no second check.
- Several key results are single-author, unrefereed 2026 preprints on short windows.
- The picture test was made easy on purpose and used one model, on clean charts with stated rules and 24 real days from a
  single 8-week window (plus 12 random twins of them). Its prediction and real-versus-random parts rest on 36 pictures.
- Nothing here is a claim that any strategy makes money. No claim of profitability or live readiness follows.

## 9. Contents of this folder

`00 Fact-check corrections (read first).md` · `01 Synthesis and plan.md` (this file) · `R1` chart readers and the 59-feature
spec (`R1_features.json`) · `R2` evidence by technique · `R3` intraday evidence · `R4` options · `R5` trend versus hype · `R6`
long-horizon trends · `R7` AI versus humans · `R8` picture-reading test (data and code in `picture test/`) · `Fact-check reports/`
(the four checker reports) · `Data rights register.md` (what the published data terms say, and what is unclear) · `Reviews/` (the
independent reviews and re-checks of this document) · `scripts/` (the calculations behind the numbers; they expect data files downloaded separately
and are kept small).

## Appendix A. The Wave 1 test list and how the trials are counted

| Block | Question | Trials |
|---|---|---|
| A. Controls first | Does the test harness catch a planted cheat and ignore noise? What is the overnight-versus-intraday drift by year (this also fixes the random baseline)? What is the noise floor on real SPY and QQQ? **MT-G42 report:** how often would the whole set of gates pass a real edge of three sizes? Shown to you before any Wave 1 result. | (controls) |
| B. When to stand aside | Do a narrow prior day, a narrow first hour, low volume at 10:00, high prior-day VIX or a Cboe yardstick predict a small or large rest-of-day range (9 trials: 6 from R1, 3 from R4; the R4 ones need the Cboe files, and VIX1D only starts in May 2022, so they must use 2022 to 2026 data, including the window that is not clean; they are volatility forecasts, not trade tests, and they wait for your answer on the Cboe files, item 8)? Do news days hurt the three baseline setups ORB5_QQQ, LAST30_MOM_SPY and NOISE_MOM_SPY (3)? How often do gaps fill (4)? Does a daily-trend filter beat a random filter with the same number of trades (6)? | 22 |
| C. Do levels matter at all? | After price touches yesterday's high, low or close, the opening-range edges, VWAP, round numbers or pivots, does the next 15 to 30 minutes differ from what happens at a *fake* level? If real levels behave like fake ones, the "map of levels" step is decoration. (R1 T4) | 9 |
| D. Directional ideas (R3) | Late-day continuation on big-move days (SPY, then QQQ as replication); long-side fade of a big gap-down; post-selloff 5-minute rebound; a high-volatility gate on the first two. We put the first two first because they have the most support, published or in our own results. Even so, R3 expects none of the five to be a reliable edge, and for the gap-down fade "not shown" will mean "not testable" (only edges above about 8 bp net can be detected). | 7 |
| E. Trend quality | Does smoothness or agreement add information beyond the size of the move (R5 T3)? Counted with every window, quality variant, horizon, symbol and era as its own test (2 x 3 x 3 x 2 x 2). | 72 |
| F. Slow trend overlay | 10-month and 200-day rules on SPY and QQQ with an exposure-matched baseline (holds the market for the same share of the time, so "holding less" is not mistaken for skill) and a random-switching baseline (the same rule switching at random dates) (R6) | 4 |
| **Total** | | **at least 114** |

**Counting convention** (fixed when the tests are registered). MT-G7 says the count can never be lower than the number of result
series the test machine stores, and the owner cannot waive it, so we count the larger number. Block E counts every window,
quality variant, horizon, symbol and era as its own test (2 x 3 x 3 x 2 x 2 = 72; R5 itself says "dozens"). Block D counts R3's
hypotheses H1 to H4 as 7 (R3 itself counts about 8 with an overnight control that is not counted here); block F is two rules on
two symbols (R6 allows up to five rules). Blocks B and C are R1's and R4's own counts, which pool SPY with QQQ and the look-ahead
times; if the build stores those separately the total is higher (block C alone would be 36: 9 level types x 2 symbols x 2
horizons). So 114 is a floor. Testing fewer things separately would be a change to the test design, written down before the run,
and the count would still be the number of results stored. R1's T6 and T7 are not counted here.

## Glossary

| Term | Plain meaning |
|---|---|
| spread, half-spread, round trip | the gap between the price you can buy at and the price you can sell at (you pay it on each trade); half of it is what you pay each way; a round trip is one buy plus one sell |
| VWAP | the day's average price weighted by volume, roughly where most trading happened |
| EMA | an average of recent prices that counts newer prices more |
| ATR | the typical size of a day's (or bar's) range |
| R-squared | how well a straight line fits the prices (0 = not at all, 1 = perfectly) |
| ADX | a 0-100 trend-strength gauge; above 25 is read as "trending" |
| Mann-Kendall | a statistical test that says whether prices trend |
| Sharpe | average return divided by how bumpy it is; about 0.5 is decent, 1 is good, above 2 is rarely real after costs |
| deflated Sharpe | a Sharpe score marked down for how many things we tried; the "probability" version is how likely it is that the marked-down score is still above zero |
| t of 3 | a result far enough from luck that luck alone would produce it about once in 370 tries |
| exposure-matched, random-switching baseline | comparisons that stop "holding less" or "switching more" being mistaken for skill |
| pre-registered, hash | written down before the test, with a digital fingerprint so it cannot be changed quietly |
| trial | one question or setting we test; each one counts because the more you test, the likelier a lucky result |
| gate | a yes/no filter that can only block a trade, never create one |
| shadow | logged and scored as if traded, but no order is sent |
| IEX, SIP | IEX is one small exchange (the free live feed, about 2-3% of trading); SIP is the full-market feed (free only when 15 minutes old) |
| at-the-money option | an option whose strike is close to today's price |
| opening range, gap fill | the high and low of the first minutes; whether the price returns to yesterday's close |
| 12-1 momentum, value-weighted, survivorship-free | buying the last 12 months' winners while ignoring the latest month; big companies count for more; data that includes companies that later failed |
| autocorrelation | whether yesterday's move helps predict today's |
| VIX, VIX1D, VVIX, SKEW, gamma level | Cboe's "fear" and volatility gauges from option prices; a gamma level is a guess at where option dealers must buy or sell |
| PBO | probability of backtest overfitting: how often the best-looking version of many that were tried turns out below average on fresh data; we want 0.20 or less |
| reality check (SPA) | a test of whether the best of many rules really beats luck |
| planted-truth reading audit | we put known answers into test charts and check that the reader gets them right |
| absolute momentum | hold an asset only if it rose over the last 12 months, otherwise hold cash |
| term structure | short-term against longer-term volatility readings; short-term higher than long-term signals stress |
| put/call, skew | put/call: the ratio of bearish to bullish option bets; skew: how much more crash insurance costs than upside bets |
| lead-lag, order flow | lead-lag: one market moving a fraction of a second before another; order flow: the stream of buy and sell orders |
| rescaling | putting every chart on the same scale, which is where much of the "picture" advantage in the research came from |
| ORB5, LAST30_MOM_SPY, NOISE_MOM_SPY | our three test setups: the 5-minute opening-range breakout (on QQQ); momentum into the last half hour (on SPY); a band-breakout strategy that trades when price leaves its usual "noise" range (on SPY, watch-only) |
| drawdown, "worst loss" | the fall from a peak to the next low point |
| exposure, overlay | exposure: how much of your money is in the market at a given time; overlay: a rule laid on top of what you already hold, such as "sell when the trend turns down" |
| ETF, preprint | ETF: a fund that trades like a stock (SPY and QQQ are ETFs); preprint: a research paper shared before other experts have checked it |
| volatility, fade, long, short | volatility: how much prices move; fade: an edge that fades gets weaker, and to "fade" a gap is to bet against it; long: buy first; short: sell first (the bot is long-only) |
| back-test, candidate | back-test: running a rule on past prices; candidate: an idea that survived Wave 1, nothing more |
| RSI, MACD, stochastic, Bollinger, Fibonacci, Elliott | popular indicators and drawing methods built from past prices |
| MT-G1 to MT-G42 | the numbered guardrails in `reports/Why day traders lose.md` |
