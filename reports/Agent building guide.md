# How to build the trading agents with Claude

This guide sums up two research notes, `research_notes/Building Claude agents/best_practices.md`
and `success_stories.md`, and turns them into design rules for the trading bot. Many of the
sources were only readable as search snippets, and the notes flag which ones.

## What the success stories have in common

No firm that uses Claude in finance lets it trade by itself. Claude does research, analysis, code,
document review and compliance checks, and fixed rules or a person approve anything that touches
money or clients:

- Norway's sovereign wealth fund (NBIM) connected Claude to its data systems and reported about
  20% of weekly time saved per employee.
- AIG reports underwriting reviews more than 5x faster.
- Bridgewater used Claude for early versions of an analyst assistant that writes Python and charts.
- Anthropic's May 2026 finance agent templates are narrow, one-job agents with human approval
  before output reaches a client or a filing.
- Man Group's AlphaGPT (snippet only) has AI propose ideas, write the code and backtest them.
  Humans then decide what trades live.

These are productivity figures reported by Anthropic and its customers, not trading profits, and
none has been independently audited.

The failures point the same way:

- In the Alpha Arena contest, Claude traded crypto on its own with borrowed money and lost somewhere
  between about 31% and 42%, depending on the source (UNVERIFIED; see `Why day traders lose.md`).
- In StockBench, 8 of 13 models beat buy-and-hold, but only by tiny margins.
- In Anthropic's Project Vend, a Claude-run shop lost money until it was forced to follow fixed
  procedures, such as checking cost and market price before quoting. A second Claude acting as the
  "boss" mostly failed to supervise it.

**The pattern:** narrow jobs, data supplied by code, fixed procedures, hard limits enforced
outside the AI, small test sets, and humans or rules owning the final action.

## Design rules for this bot

### Keep the math and the money in code

1. Code computes every number: prices, indicators, stops and position sizes. Claude never
   calculates; it chooses between options code gives it.
2. Where possible, Claude picks from a menu (for example candidate stop levels computed by code)
   instead of typing raw numbers.
3. The hard risk limits stay in `risk.py`. Don't use a second Claude as the risk manager. Project
   Vend showed an AI supervisor gives in too easily.
4. One bad field shouldn't sink the whole decision. Clip or reject that single action in code and
   keep the rest. Today one out-of-range number drops every action.

### Make Claude's output measurable

5. Every Claude action carries a reason code from a fixed list, plus a falsifiable prediction
   (direction, horizon and probability). Code scores these later for accuracy and calibration,
   using the Brier score.
6. Track every time Claude deviates from the rules, as if it were a separate trade, and score the
   total. If deviations lose money over enough trades, Claude's freedom is reduced automatically.
7. Tag every decision with the prompt version, schema version and the model that actually
   answered, so a prompt change counts as a new system.

### Make results consistent

8. Claude's answers vary from run to run, and temperature can't be set on current models. Run the
   decision 3 times and act only on changes that a majority of the runs agree on, using the median
   size. Measure how often the runs agree.

### Cost and model choice

9. The bot uses `claude-opus-5` by default. Switching to `claude-opus-5-5` would be cheaper ($4/$20
   per million input/output tokens against $5/$25), and Anthropic's docs recommend it for most work.
   Switching is the owner's decision (set `CLAUDE_MODEL`). Whichever model is used, pick the effort
   level with the test set rather than guessing.
10. Raise `max_tokens` to about 32,000 so long thinking isn't cut off.
11. Prompt caching doesn't pay here. The two daily calls have different prefixes, and runs are 24
    hours apart, far longer than the cache lifetime. Remove it, except when sampling the same
    decision several times in a row, where the repeats can reuse the cache.
12. Use the Batch API (50% off, results within 24 hours) for tests and historical replays, not for
    the live daily call.
13. Log the API cost of every run and report it as a percentage of the account, like a fund fee.

### Test the agent before trusting it

14. Build a test set of 20–50 frozen historical days. Code checks each output:
    - it matches the expected format;
    - the risk engine didn't need to clip anything;
    - every symbol is on the allowlist;
    - stops sit below the current price;
    - Claude does nothing on "control" days where nothing should happen.

    Only the written explanations get graded by a model, against a fixed rubric.
15. Run each test several times, keep API failures out of the scores, and rerun the set whenever
    the prompt or model changes.

### Watch for known Claude habits in trading

16. Claude tends toward long-only, low-variety ideas. Man Group found Claude's ideas more correlated
    with each other than another model's. Show Claude the rules' view and ask for a reason
    whenever it simply agrees.
17. Handle refusals and fallback models. If a different model answered, log it and treat that day's
    decision as lower confidence.

## What this means for the build

Most of these rules are small changes to `trader/llm.py` and `trader/engine.py`: new output
fields, per-action validation, sampling several runs, cost and version logging, a model change,
and a new `evals/` test set. They fit alongside the rulebook's rules and can be built in the same
pass.
