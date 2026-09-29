# Options horror stories, and how to protect us from going negative (29 Sept 2026)

*Owner request, 29 Sept 2026: "make sure we never hit the red in options trading; look up horror stories about people being in
the negatives and figure out exactly how to 100% protect us from it."*

*Safety research, not advice to trade. **No live trading exists (MT-G36); everything here is paper.** Section 7 applies only if
the owner ever decides in writing to go live, and this report does not recommend that. This report changed no code, no settings
and no account. Made by 4 web researchers and 1 internal auditor, re-checked by 2 independent verifiers and an honesty reviewer.*

## Words used

| Word | Plain meaning |
|---|---|
| option, premium | a contract giving the right to buy (call) or sell (put) 100 shares at a set price (strike) until a date (expiry); the premium is what you pay for it |
| long, short, sell to open | long = you bought it; short = you sold it first ("sell to open"), so **you** owe if the buyer uses it |
| assigned, exercise | the buyer uses their right (exercise); the seller is picked to deliver (assigned) |
| auto-exercise, do-not-exercise | at expiry, an option in the money by $0.01 or more is normally exercised automatically; a "do-not-exercise" instruction asks the broker not to |
| spread, leg | two options bought and sold together; each one is a leg |
| margin, multiplier | money borrowed from the broker; multiplier 1 means no borrowing |
| cash account | an account that can only spend money it has |
| options level | how much options trading the broker allows (Alpaca: 0 = none, 1 = covered calls and cash-secured puts, 2 = adds buying calls and puts, 3 = adds spreads) |
| covered call, cash-secured put | selling a call while owning the shares; selling a put while holding the cash to buy the shares |
| 0DTE | an option expiring the same day |
| gap, halt | a price jump with no trading in between; a halt is a pause in trading |
| kill switch, watchdog, fail closed | an emergency "cancel everything and sell"; a separate program that does it if the bot dies; when unsure, refuse |
| SCALP, RULES, the lab, Book O | our two Alpaca paper accounts (SCALP = this minute bot; RULES = the stock books and the options work), the options lab, the options book |

## 1. The short answer

**A 100% guarantee is not possible.** Only one thing is certain, and only under its conditions:

1. **Buying** a call or put outright, paid in full from cash, can lose at most what you paid (the premium) plus fees. It cannot
   by itself make the balance negative. That is arithmetic, not a promise, and it holds only while the option is not exercised.
2. **Selling** options can: a naked (uncovered) short call has no loss ceiling (cases 5 and 9 below).
3. A **buy-only rule** in a cash account, with the broker's options level capped and selling-to-open blocked in our code,
   **greatly reduces** the risk of owing the broker, **if every control in section 4 works**. It does not cover outages, halts,
   bugs, or anyone holding the keys. Alpaca has no "buy-only" level, so the block on selling rests on our own code.
4. Two side doors stay open even for a buyer: **automatic exercise at expiry** into 100 shares per contract you cannot pay for,
   and **no exit** during a halt or outage. That is why we never hold an option into its last trading day.
5. You can still lose **100% of every premium**, often. "Never owing the broker" can be made very unlikely; "never in the red"
   (never losing money) cannot be promised.
6. Keep a cash buffer for fees, and never size a trade so that losing the whole premium would hurt.

## 2. Horror stories (checked cases)

| # | Case and sources | What happened, amount, who bore it | Mechanism | Negative? | What would have prevented it |
|---|---|---|---|---|---|
| 1 | Swiss franc: FXCM and Alpari UK, 15 Jan 2015. [swissinfo](https://www.swissinfo.ch/eng/fxcm-faces-losses-as-swiss-shock-leaves-alpari-uk-insolvent/41219974); [FCA](https://www.fca.org.uk/news/statements/news-customers-alpari-uk-limited) | Clients ended with negative equity and owed FXCM about $225M; FXCM was left short of capital and needed an emergency loan (reported as about $300M from Leucadia, about $279M net; single secondary source). Alpari UK went into special administration on 19 Jan 2015. | Leveraged currency trading gapped past every stop order. | Yes | No leverage. (Note: a broker failing, as Alpari did, is a different risk from a negative balance.) |
| 2 | Swiss franc: Interactive Brokers, event 15 Jan 2015, statement 16 Jan. [Yahoo](https://finance.yahoo.com/news/interactive-brokers-lost-120-million-150612206.html) (single source) | Customers "suffered losses in excess of their deposit"; the broker absorbed about $120M of customer debits. | Same gap. | Yes | Same. |
| 3 | XIV, 5 Feb 2018. [CFA Institute](https://rpc.cfainstitute.org/research/financial-analysts-journal/2021/volmageddon-failure-short-volatility-products); [SEC filing](https://www.sec.gov/Archives/edgar/data/1053092/000095010318001572/dp86358_ex9901.htm) | Inverse-volatility products lost over 90% in a day; XIV was ended early. Holders bore it. | Products that were short VIX futures; their own rebalancing fed the spike. | No (holders lost what they paid) | Do not hold inverse or leveraged volatility products. |
| 4 | LJM Preservation and Growth fund, 5-6 Feb 2018. [Yahoo](https://finance.yahoo.com/news/u-ljm-fund-lost-most-152828038.html); [law-firm summary](https://www.investorlawyers.net/blog/ljm-preservation-growth-fund-plummets-value-vix-spike/) | Fund shares fell about 55.8% and then 54.6% on consecutive days; assets fell from $812M to $14M during February (partly redemptions). Shareholders bore it. | The fund sold S&P 500 options. | No | No uncapped short options. |
| 5 | OptionSellers.com clients at INTL FCStone, Nov 2018. [SEC filing](https://www.sec.gov/Archives/edgar/data/913760/000091376018000151/a8-kiff2018stmtoffincond.htm); [law-firm summary](https://www.silverlaw.com/blog/optionsellers-com-suffers-losses-after-natural-gas-declines/) | About 300 accounts fell below their margin requirement and were liquidated; customers still owed the broker $35.3M on 27 Nov 2018. | Naked short natural-gas options on margin; the price spiked. | Yes | No uncovered short options. |
| 6 | Negative oil price: Interactive Brokers, 20 Apr 2020. [CFTC](https://www.cftc.gov/PressRoom/PressReleases/8432-21); IBKR's own quarterly report via [Finance Magnates](https://www.financemagnates.com/forex/brokers/interactive-brokers-loss-from-oil-collapse-swelled-to-104-million/) | US oil futures settled at -$37.63; the broker's systems could not handle negative prices. Customers incurred losses beyond their account equity; IBKR bore about $104M by compensating them. The CFTC ordered $82.57M restitution (customers' initial trading losses) plus a $1.75M penalty. | Leveraged futures priced through zero. | Yes | No futures, no leverage. |
| 7 | Bank of China "Yuan You Bao" oil product, Apr 2020. [Bloomberg via Investing.com, 26 Apr 2020](https://investing.com/news/stock-market-news/bank-of-china-clients-said-to-have-1-billion-losses-on-oil-bet-2151313) | Over 60,000 clients lost their 4.2B yuan margin and were told they owed the bank a further 5.8B yuan (the article's figures differ: an earlier estimate said "more than 7B yuan"). Customers owed the bank; the bank bore the shortfall after a public outcry. | A retail product tied to oil futures that went below zero. | Yes | Only products whose worst case is the amount paid. |
| 8 | Allianz Structured Alpha, Mar 2020. [SEC](https://www.sec.gov/newsroom/press-releases/2022-84) | About $11B invested; over $5B lost. A risk figure of -42.15% was reported to investors as -4.15%. Investors bore it; Allianz later paid billions in settlements. | Hidden risk in option-based funds. | No | Loss limits enforced in code nobody can quietly edit. |
| 9 | Alex Kearns, Robinhood, June 2020. [FINRA AWC](https://www.finra.org/sites/default/files/2021-06/robinhood-financial-awc-063021.pdf); [CBS](https://www.cbsnews.com/news/alex-kearns-robinhood-trader-suicide-wrongful-death-suit/) | Age 20. The short leg of an options spread was assigned early. The app showed cash of -$730,165.72; FINRA says the real cash was -$365,530.60 (the AWC calls him "Customer A"; the name comes from press reports). His net loss once the long leg was used is unknown; his family's lawyers said he may not have lost money. He died by suicide; there was no phone number to call, only automated email replies. FINRA fined Robinhood $57M plus $12.6M restitution for many findings, not only this one. | Assignment shows a huge negative cash line while the long leg offsets it; the app doubled it. | Cash yes; real debt unknown | No short legs; compute our own worst case instead of trusting a broker screen; a human to call. |
| 10 | GameStop and Robinhood, 28 Jan 2021. [Tenev testimony](https://www.congress.gov/117/meeting/house/111207/witnesses/HHRG-117-BA00-Wstate-TenevV-20210218.pdf) | The price rose over 530% between 25 and 28 Jan. The clearing house told Robinhood Securities of a deposit deficit of about $3B (it had $696M on deposit). No verified individual negative balance. | Broker-level collateral demand, not a customer loss. | Unclear | No uncovered short options. |

Left out because they could not be checked in time: Valeant, a SEBI study of Indian traders, Knight Capital, Barings. We found no
documented 2024 to 2026 US case; that is not proof there was none.

## 3. How accounts go negative

| Mechanism | Tiny example | Can the loss exceed what you paid? |
|---|---|---|
| Naked short call or put | Sell a 50 call for $4 ($400); the stock gaps to $150: loss $9,600. Sell a 50 put for $2; the stock goes to 0: loss $4,800. ([OCC booklet, older copy](https://www.tradewex.com/tradewexdocs/WEXOptionsDisclosure.pdf)) | Call: no limit. Put: up to strike x 100; not negative if that cash is held. |
| Margin plus a gap | $3,000 equity, a naked 50 call sold for $200, the stock opens at $90: equity -$800, owed to the broker. ([Alpaca customer agreement](https://files.alpaca.markets/disclosures/library/AcctAppMarginAndCustAgmt.pdf), Appendix A, s.4) | Yes; a debt. |
| Early assignment of a short leg | Sell a 50 put and buy a 45 put for a $150 credit (worst case $350). The stock falls to $40 and the short put is assigned: cash shows about -$5,000 until the long put is used. ([FINRA](https://www.finra.org/investors/insights/trading-options-understanding-assignment)) | The screen shows a big negative; the real loss is capped only if the long leg is handled. |
| Automatic exercise of a long option | Buy a 50 call for $100; the stock ends at $50.50, so it is exercised: you now owe $5,000 for 100 shares; a gap to $44 costs $700. ([OIC](https://www.optionseducation.org/referencelibrary/faq/options-exercise)) | Yes, through an exercise you did not want. |

## 4. The protection plan (ranked)

**Certain (arithmetic, under stated conditions)**

1. **Buy to open only**: one call or put, paid in full from cash, no margin. Loss at most premium plus fees. Conditions: a listed
   option, no short legs, not exercised. Not covered: losing the whole premium; no exit in a halt.

**Best effort (software and procedure: they work only if they work)**

2. **Never hold into the last trading day**: sell to close at least a day before expiry; no 0DTE; a do-not-exercise instruction
   as a backstop (Alpaca's documentation is inconsistent about doing this through the API; test it in paper:
   [Alpaca](https://docs.alpaca.markets/us/reference/optiondonotexercise)). This closes the one path by which a buy-only book takes
   on an obligation. Not covered: the premium reaching zero first; bad exit prices.
3. **Account settings that fail closed**: cash account (or margin multiplier 1), the lowest options level needed, `no_shorting`
   on, checked by the bot at start-up, which refuses to start otherwise. Not covered: Alpaca has no buy-only level (level 2 also
   allows covered calls and cash-secured puts: [Alpaca](https://docs.alpaca.markets/us/docs/options-trading)), so our code must
   still block selling to open; anyone with the keys can change settings.
4. **A locked pre-trade check** of each order's worst case at every price from zero to very high: it must not exceed cash or a
   percentage-of-equity cap. A simulation only: no gaps, halts or assignment timing.
5. **Cap the total premium at risk.** Shrinks the red; does not prevent it.
6. **Kill switch, daily loss limit and an independent watchdog** with broker reconciliation and push alerts, none editable by the
   bot (cases 6 and 8; [FIA](https://www.fia.org/sites/default/files/2024-07/FIA_WP_AUTOMATED%20TRADING%20RISK%20CONTROLS_FINAL_0.pdf)).
7. **Compute our own worst case; never trust a broker screen** (case 9).

**Do not rely on** broker stop-loss orders, margin liquidation or "negative balance protection" (cases 1, 2, 5, 6): customer
agreements make the customer liable.

## 5. Our own exposure today (internal audit, read-only)

On paper, SCALP equity is about $1.0M, so negative equity is out of reach. The internal auditor read the RULES account at about
$100k equity and $40k cash from the broker on 29 Sept (not from a repo file); there, negative *cash* is reachable (one assigned SPY
contract is about -$77k). On a hypothetical $100 live account any assignment, short leg or margin use would go negative. Already
solid: **the SCALP bot cannot build an option order at all.**

**(a) Proposed changes to our minute bot (not made; each needs your OK and two reviewers)**

1. High. The bot never checks the account's settings at start-up; the "options level 3" that `check-account` prints may be the
   *approved* level, not the effective one (`lab/scalp/live/__main__.py`). Proposal: a fail-closed start-up gate (no entries unless
   options level is 0, shorting is off and the margin multiplier is 1), print both levels, add tests.
2. High. The going-live gate (MT-G36) does not require a cash account, no options approval, `no_shorting`, multiplier 1 or
   trade-only keys. Proposal: add that wording now.
3. Medium. No test bans option order types in the SCALP package, and the risk hash covers only `config.py`, `risk.py`, `sizing.py`
   and `orders.py` (`lab/scalp/live/config.py`, `RISK_FILES`). Proposal: add the test; widen the hash (you would re-store it).
4. Medium. The kill switch cannot close a short position (a person must, `watchdog.py`), and alerts stay in a local file.
   Proposal: push alerts; a one-page runbook ("buy to close by hand").

**(b) Broker-side settings (need your OK)**

1. SCALP, once, after the market closes: `max_options_trading_level = 0`, `no_shorting = true` (already on), `max_margin_multiplier
   = 1`; logged in `state/scalp/changes.log`; read back. A tripwire, not a lock against a key holder.
2. Decide key handling (handoff v4 section G-1): keep the SCALP and RULES keys out of any agent environment that can run commands.
3. RULES: `no_shorting` is not recorded there; that account belongs to the operations session.

**(c) For the operations session (recommendations only; they own the RULES account, the lab and Book O)**

1. High, can go negative: in the lab, an early assignment leaves stock, and the lab's "leg-out" then sells the protective long
   option, leaving unhedged shares. Suggest reading the stock position, an "assigned" state that freezes entries and forbids
   selling the long leg, and Book O's clean-up rule (OPT-26).
2. High, can go negative: the lab has no outside watchdog or real alerts; Alpaca starts closing expiring positions from 15:00 and
   can strip the long leg first. Suggest a separate watchdog, flat by 14:45, push alerts.
3. Medium: the lab never reads the account; its $250 per-trade cap is 2.5 times a $100 account. Suggest Book O's checks.
4. Medium: the lab defaults to 0DTE and to sending paper orders; the playbook contradicts the code in places. Suggest an explicit
   enable switch and dry run by default.
5. Medium: the playbook's section 8 "probe" orders could create a naked short if the broker accepted them. Suggest asking Alpaca
   support instead.
6. Medium: the RULES stock books send market orders without a position check. Suggest refusing sells larger than the position.
7. Low: levels 1 and 2 allow cash-secured puts and covered calls; the lab's leg-out price is uncapped; Book O's approval files can
   be changed by the session (hash them outside the repo).

## 6. What we still cannot promise

- Never losing money; surviving every outage, halt, broker failure, bug or fee. (A broker failing, like Alpari, is a different
  risk from owing it money.)
- That paper proves live: Alpaca's paper documentation is silent on margin calls, liquidation, negative balances and early
  assignment.
- That Alpaca keeps refusing naked short options (its statements on this date from March 2025).
- Safety against anyone who holds the keys.

## 7. Checklist before any real-money options trade (only if you ever decide in writing to go live)

1. Cash account (or multiplier 1) and `no_shorting` on, checked by the bot at start-up (fail closed).
2. Options level is the lowest needed, read back from the broker.
3. The code sends only buy-to-open and sell-to-close; sell-to-open is blocked and tested.
4. Locked code proves each order's worst case is at most the cash and the percentage cap.
5. Nothing held into the last trading day; 0DTE off; do-not-exercise tested in paper.
6. Kill switch, loss limit and independent watchdog proven by killing the bot on purpose.
7. Keys trade-only where possible, and kept out of agent environments that run commands.
8. You have read the broker's debit-balance clause; the deposit is money you can lose entirely.
9. A replay of the 2015 franc, 2018 volatility, 2020 oil and stock-to-zero scenarios passed in **our own simulator** (a paper
   account cannot replay history).
10. You signed off in writing; no agent ticks this list for you.
