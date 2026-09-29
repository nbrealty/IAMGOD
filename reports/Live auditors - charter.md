# Live auditors: charter (29 Sept 2026, revised after two independent reviews)

*Owner decision, 29 Sept 2026: "Auditors should always be present during any trade. In live real-money trades I'm going to
want way more auditors, because any wrong decision can cost me."*

## In plain words

A panel of AI "auditors" watches the trading bot while it trades. Each has one job (strategy, reasoning, execution, risk). They
read the bot's own records and say, in plain English, whether anything looks wrong, with a colour: GREEN, AMBER or RED. They
advise people; they never trade and never change the bot. On paper there are four. For real money there would be many more,
more independent, plus plain-code checks and a named person who can stop everything. **More auditors catch more mistakes; they
do not make a losing strategy win.**

## 1. The rule, and who does what

**No trading session runs without the panel watching it.**

- **Operator** = the minute-trading Claude session that starts the bot. It starts the panel, runs each round, writes the day
  report, and on paper may run `kill` when a rule is broken (it already has that duty from the start-up routine).
- **Owner** = the human. The owner decides anything that changes a rule, a limit, the account or the data terms.
- **Paper (now):** presence is an operator practice, not enforced by code. Coverage is labelled **per time window**: a window
  with no completed round is **UNAUDITED** in the day report. Day 1 (29 Sept): the panel started at 09:13 ET, after the bot's
  08:32 start and its 08:39 to 09:12 outage (the cloud machine slept), so 08:32 to 09:13 is UNAUDITED.
- **A round counts** only if the note cites at least one journal line newer than the last round (so a stuck or rubber-stamp
  panel shows as UNAUDITED). **Quorum:** a window is audited only if at least 3 of the 4 auditors completed their round.
- **Real money (does not exist; MT-G36):** presence must be enforced by code (no fresh panel heartbeat, no new entries; exits are
  never blocked, MT-G38). The heartbeat is written by plain code after each counted round, never by an AI. That gate is new
  order-path code: a registered change, two independent reviewers and the owner's written OK.

## 2. What auditors are, and are not

An auditor is an AI agent with **one question**, a **fixed lens**, a **written stop criterion** for RED, and a duty to say
plainly when something is wrong. Each round it writes a dated note with a colour and a reason:

- **GREEN** must name what it was checked against (the broker-side reconcile line, a code path, a rule). Otherwise it is
  written **GREEN-UNVERIFIED**.
- **AMBER:** a human should look today. AMBERs go into one daily digest; they never page anyone.
- **RED:** a rule may be broken or money may be at risk. RED is the first line of the note.

**Auditors are instructed not to** place or cancel orders, run `kill` or `run`, use API keys, edit code, config or state, change a
limit, or send our positions, prices or account data anywhere. **Nothing technical stops them yet:** they run with shell and write
tools on the machine where the paper keys live. That is acceptable for a paper account; before real money it must be a real
sandbox (no keys, read-only files, allowed web hosts only; handoff v4 section G).

**Web tools are split from our records.** The four auditors have no web search or web fetch: they judge from our records, the
code, the rules and the research already in the repo. Only the entity-analysis agent uses the web, and it does not read our
journal, state or recordings. Its dossiers are **untrusted text** for the auditors (a web page may contain planted instructions).

**Nothing an auditor writes changes the bot.** A lesson becomes a hypothesis, then a test on old or forward data, then (only if it
survives) a new registered version with the owner's OK.

**Human actions are logged.** If the owner or operator acts on an auditor's note or a dossier (skips a trade, stops the bot early),
it is logged as **DISCRETIONARY** and that day does not count as evidence for or against the strategy, because the rule was not
followed as written.

## 3. The paper panel (4 auditors)

| # | Auditor | Its question | Reads |
|---|---|---|---|
| 1 | **Strategy Reality Check** | Do our setups make sense next to how the ideas are used in practice, and does each decision fit the day? It **assumes zero edge** until a forward test net of costs says otherwise; "traders use this" is never support. | code, repo research, journal |
| 2 | **Decision Reasoning** | For each decision and refusal: what did the bot think, what would a careful human think, what one-line lesson follows? | journal, code, rules |
| 3 | **Market and Execution** | Are today's conditions and orders realistic, and would fills beat the costs? | journal, order code, costs |
| 4 | **Risk and Operations** | What can go wrong today, is it covered, and are the bot and its watchdog healthy right now? | heartbeat, processes, alerts, guardrails |

Agent files: `.claude/agents/live-auditor-*.md`. Auditors do **not** read the second-by-second quote recordings (`recordings/`);
see section 6 on data rights.

**Rounds:** pre-open; after each decision (ORB5 about 09:35, LAST30 about 15:30); midday; after the 15:50 flatten; after the
close. The operator also checks `alerts.log` at each round; there is no automatic trigger yet.

**Disagreement:** colours are shown side by side, never averaged. **One RED is enough** for the operator to tell the owner at once
and to check the claim against the bot's own records. On paper the operator runs `kill` only if the RED is confirmed there (a
broken rule, a position the bot should not have, a missed 15:50 exit). An unflattened position at 15:56 is always RED.

**Plain-code checks (no AI):** the bot already reconciles its own records with the broker every 5 to 30 seconds and stops itself on
an unexplained difference (MT-G26). Its outside watchdog flattens at 15:57 if the bot is gone (MT-G39). These are the first line;
the auditors are a second look.

**Output:** one note file per auditor and a plain-English day report (`reports/Live audit <date>.md`) written by the operator: each
auditor's colours, audited and UNAUDITED windows, lessons, DISCRETIONARY actions, and decisions for the owner.

## 4. The real-money panel (a proposal; needs the owner's OK; nothing live exists)

| Group | What | Why |
|---|---|---|
| The four above, **each run twice by differently prompted instances**, ideally on different models | same questions, independent | one instance shares blind spots with the designers |
| Independent Reconciler | compares our journal with the broker's records (positions, cash, fills, fees) every few minutes; mostly plain code | the bot must never be the only witness to its own trades |
| Red Team | argues the best case for stopping today | somebody must be paid to say no |
| Data Integrity | feed age, symbols, corporate actions (splits, dividends), clock drift, halts | wrong data breaks every other check |
| Compliance and Conduct | account-type limits (pattern-day-trader rule, cash settlement T+1, good-faith violations), wash-sale tax rule, order behaviour that could look like spoofing (placing orders you do not mean to fill), data-licence terms | rules that cost real money when broken |
| Cost and Tax | fees, slippage versus model, tax effect | edges die of costs |
| At least two plain-code checks | position and cash equal to the broker; limits respected; orders match the registered plan | AI auditors can be wrong together; code checks do not tire |
| Entity analysis (input, not a judge) | a dossier on every asset before it is traded | knowing what you own |
| **A named human with kill authority** | paged on RED, with a one-page runbook | the last line of defence is a person |

**Design rules:**

1. **Independence:** different prompts, data views and ideally models; auditors do not read each other's notes before writing.
2. **Every auditor's RED criterion is written down in advance.**
3. **RED pages the owner's phone.** If a RED is not acknowledged within 10 minutes: new entries stop (on paper, the operator may run
   `kill`). AMBER never pages.
4. **No auditor gets the power to trade.** The only power worth considering is narrow: a request to stop new entries (never exits)
   for one setup or one symbol, **with an expiry**, based on the bot's own records (never web text, MT-G24), at most every 30
   minutes. That would need an amendment to MT-G29 (which today allows only an AI veto of a setup for the day, of a symbol until a
   time, or a flag), three-run agreement (MT-G32), a plain-code corroboration, and the owner's written OK. It would not use HALT,
   which has no expiry and needs a logged reset (MT-G41).
5. **Cost is logged per auditor per day**, and an auditor that never finds anything is reviewed (MT-G34).
6. **The panel is tested:** once a month a past journal with a planted fault is replayed; if the panel misses it, it is not trusted
   until fixed.
7. **Panel size and GREEN counts are not evidence** and never enter the going-live gate. Going live needs a separate written owner
   decision, the going-live gate (MT-G36), and the strategy tests MT-G5 to G7 and G42, which are not built yet.

**Going-live hazards the panel must cover (checklist):** account type and the pattern-day-trader rule (verify the current FINRA rule
before going live; it was being changed); cash settlement and good-faith violations; wash sales on repeated losing re-entries in
the same fund within 30 days; trading halts and limit-up/limit-down pauses (a limit exit may not fill); broker or machine outage
with a position open (a second-host flatten job with a trade-only key); live keys never on the panel's machine or in any path an
agent can read.

## 5. Known limits today (29 Sept 2026)

- The bot, its watchdog and the panel share one cloud machine. When it slept at 08:39 ET, all stopped together. Keep the chat active
  during the session; move the watchdog off the machine before real money.
- Auditors are AI. They can be wrong, confident, or miss things, and the four share one model and much of their wording.
- A usage limit can stop the panel mid-day (it stopped other helpers in this session early on 29 Sept). The bot keeps running while the machine is
  awake; the missed windows are labelled UNAUDITED. If usage is short, the 15:30 round and alert rounds come first.
- Alerts go to `state/scalp/alerts.log` and the console. Nobody is paged yet.

## 6. Data rights

The data-rights register (`reports/Chart reading research/Data rights register.md`) calls sending Alpaca-derived market data to
an AI model **UNCLEAR** (Alpaca's terms are silent) and advises waiting for Alpaca's written answer. The bot's journal contains the
bid, ask and mid it saw at each decision, so an auditor reading it is an AI reading Alpaca-derived numbers. The paper panel runs
because the owner asked for it on 29 Sept; to keep the exposure small it does not read the quote recordings and does not copy
prices into notes or queries. **Owner decision needed:** continue the paper panel under this personal, non-commercial, no-sharing
exception until Alpaca answers, or pause it. A real-money panel does not start until Alpaca answers in writing.

## Glossary

| Term | Plain meaning |
|---|---|
| heartbeat | a small file the bot rewrites every few seconds to say "I am alive" |
| HALT, `kill` | HALT: a file that stops all new entries until a person resets it; `kill`: cancel everything, sell what is held, then HALT |
| order path | the code that decides and sends orders; no AI is allowed in it (MT-G29) |
| reconcile | comparing our own records with the broker's, and stopping on any difference |
| wash sale | a tax rule: a loss is not deductible if you buy the same thing back within 30 days |
| spoofing | placing orders you do not intend to fill, to mislead others; illegal |
| corporate action | a split, dividend or merger that changes a stock's price or share count |
| pattern-day-trader rule | a US broker rule limiting day trades in small margin accounts |
| MT-G1 to MT-G42 | the numbered guardrails in `reports/Why day traders lose.md` |
