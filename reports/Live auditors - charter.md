# Live auditors: charter (29 Sept 2026)

*Owner decision, 29 Sept 2026: "Auditors should always be present during any trade. In live real-money trades I'm going to
want way more auditors, because any wrong decision can cost me."*

## 1. The rule

**No trading session runs without an auditor panel watching it.** This applies to paper and, much more strictly, to real money.

- **Paper (now):** the panel is started together with the bot. Presence is an operator practice today (the minute-trading
  session starts both), not something the code enforces. A day the panel did not run is labelled **UNAUDITED** in the day report.
- **Real money (does not exist yet; MT-G36 says there is no live path):** presence must be **enforced by code**: no live panel
  heartbeat, no new entries. Exits are never blocked (MT-G38). That gate is new order-path code, so it needs a registered
  change, two independent reviewers and the owner's written OK before any live decision. It is on the going-live checklist.

## 2. What auditors are, and are not

An auditor is a read-only AI agent with **one question to answer**, a **fixed lens**, and a **duty to say plainly when
something is wrong**. Auditors:

- read the bot's own records (journal, heartbeat, alerts, recordings), the code, the rules and general market knowledge;
- judge decisions and conditions with common sense, as a careful, experienced human would;
- write dated notes, give a **colour (GREEN / AMBER / RED)** with a reason each round, and propose **testable lessons**.

Auditors **cannot**: place or cancel orders, run `kill` or `run`, hold or use API keys, edit code, config or state, change a
limit, or send our positions, prices or account data anywhere. The bot stays plain code with no AI in its order path (MT-G29).
Today this is enforced by their instructions and a read-only tool habit, not by a sandbox. A hard sandbox (no keys, read-only
mount) is the stronger design and is required before real money (handoff v4, section G).

**Nothing an auditor writes changes the bot.** A lesson becomes a hypothesis, then a test on old or forward data, then (only if it
survives) a new registered version with the owner's OK. That is how the bot's "reasoning" improves: the humans and tests learn,
and the code is changed on purpose.

## 3. The paper panel (4 auditors, running now)

| # | Auditor | Its question | Reads |
|---|---|---|---|
| 1 | **Strategy Reality Check** | Do our setups match how real traders and firms use these ideas, and does each decision fit the day? | code, research, journal |
| 2 | **Decision Reasoning** | For each decision and refusal: what did the bot think, what would a careful human think, what one-line lesson follows? | journal, code, rules |
| 3 | **Market and Execution** | Are today's conditions, data and orders realistic, and would fills beat the costs? | journal, recordings, order code |
| 4 | **Risk and Operations** | What can go wrong today, is it covered, and is the bot and its watchdog healthy right now? | heartbeat, processes, alerts, guardrails |

Their agent definitions are in `.claude/agents/live-auditor-*.md`. The **entity-analysis** agent (`reports/Entity analysis -
spec.md`) supplies a dated dossier on the fund and its biggest holdings before the open; auditors read it as context.

**Rounds:** pre-open; after each decision (ORB5 about 09:35, LAST30 about 15:30); midday; after the 15:50 flatten; after the
close; and at once when an alert fires or the heartbeat goes stale. **Output:** one note file per auditor and a plain-English
day report (`reports/Live audit <date>.md`) with each auditor's colour, the lessons, and anything the owner must decide.

**Colours:** GREEN = nothing to act on. AMBER = something a human should look at today. RED = a rule may be broken or money may
be at risk: the operator tells the owner at once and, on paper, considers `kill`.

## 4. The real-money panel (a proposal; needs the owner's OK; nothing live exists)

More money at risk means **more auditors and more independence**, not just more copies:

| Group | Auditors | Why |
|---|---|---|
| The four above | Strategy, Reasoning, Execution, Risk and Operations, **each run twice by differently-prompted instances** | one instance can share a blind spot with the bot's designers |
| Independent Reconciler | compares our journal with the broker's own records (positions, cash, fills, fees) every few minutes, part plain code, part AI reader | the bot must never be the only witness to its own trades |
| Red Team | every decision, argues the best case for **stopping today**, and tries to break the assumptions | somebody must be paid to say no |
| Data Integrity | feed age, symbol and corporate-action checks, clock drift, halts | wrong data makes every other check meaningless |
| Compliance and Conduct | pattern-day-trader and margin rules, wash-sale and tax lots, order behaviour that could look like spoofing, data-licence terms | rules that cost real money when broken |
| Cost and Tax | fees, slippage versus model, tax effect | edges die of costs |
| Deterministic checks (at least two, no AI) | plain code: position and cash equal to the broker, limits respected, orders match the plan | AI auditors can be wrong together; code checks do not tire |
| Entity analysis (input, not a judge) | dossier on every asset before it is traded, required before any new asset | knowing what you own |
| **A named human with kill authority** | is paged by the panel; has a written runbook | the last line of defence is a person |

**Design rules for a bigger panel:**

1. **Independence:** different prompts, different data views, ideally different models; auditors do not read each other's notes
   before writing theirs. Disagreement is kept and shown, not averaged away.
2. **Every auditor has a stop criterion** written down in advance (what makes it RED), not left to mood.
3. **Alerts go to the owner's phone**, with a rule for what happens if nobody answers. Today alerts go to a file (a known gap).
4. **No auditor gets the power to trade.** The only power worth considering is a narrow one: a request to **stop new entries**
   (never exits) through the existing HALT mechanism, for example when two independent auditors flag RED. That is a veto in the
   MT-G29 sense and would need the owner's written OK, three-run agreement per check (MT-G32) and cleared data rights.
5. **Cost is a design input:** every auditor's cost per day is logged; an auditor that never finds anything is reviewed, not
   silently kept (MT-G34 spirit).

**Honest limit: more auditors do not make a losing strategy safe.** They can catch mistakes, drift, bad data and broken rules.
They cannot create an edge, and they can share the same blind spots. Real-money safety rests first on tiny size, hard limits in
code, a tested kill switch, and evidence that the strategy works (MT-G1, G5 to G7, which are not built yet). Going live also
needs a separate written owner decision and the going-live gate (MT-G36).

## 5. Known limits today (29 Sept 2026)

- The panel runs on the same machine as the bot. If that machine sleeps (it did at 08:39 ET on day 1) the bot, its watchdog and
  the panel all stop. Keep the chat active during the session; move the watchdog off the machine before real money.
- Auditors are AI. They can be wrong, confident, or miss things. Their value is a second and third look, not a verdict.
- The audit uses the AI provider's usage; a usage limit can stop the panel mid-day. The bot itself keeps running while the
  machine is awake.
- Data rights: auditors read our own logs and summaries, not raw market-data files. The data-rights register
  (`reports/Chart reading research/Data rights register.md`) still has an open question with Alpaca about sending market data to an
  AI model; a live-money panel should not start until it is answered in writing.
