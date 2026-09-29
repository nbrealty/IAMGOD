# Infrastructure, Guardrails, and Legal Considerations for a Personal Autonomous AI Paper-Trading System

Research date: 2026-09-26. Not legal or tax advice. Several primary sites (finra.org, schwab.com, businesswire.com, cvm.gov.br) were blocked by the research proxy, so some figures come from search-result summaries of those pages. They are flagged where relevant.

## (a) Paper trading brokers/APIs and realism of fills

### Takeaway
Alpaca is the easiest starting point. Every new account is a free paper account by default, and live accounts are available to residents of Portugal and many other countries, with EEA passporting completed in July 2026. IBKR is the most complete multi-asset option but has more setup friction: a paper account needs market-data sharing from the live login. For crypto, Bybit Demo, which uses live mainnet prices, is the most realistic simulator. Binance and Kraken testnets are good for integration tests only, and the Coinbase sandbox returns static responses. No paper engine simulates realistic slippage or market impact.

### Cited Findings
**Alpaca**
- New Alpaca accounts are paper trading accounts by default — [Alpaca non-US guide](https://alpaca.markets/learn/live-trading-account-non-us)
- Alpaca paper trading **does not simulate** market impact, information leakage, slippage from latency, queue position for non-marketable limit orders, price improvement, or regulatory fees. Order size is **not checked against NBBO quantity**, so paper fills can be far larger than real liquidity. Partial fills are simulated at random 10% of the time — [Alpaca Docs: Paper Trading](https://docs.alpaca.markets/us/docs/paper-trading); [TradersPost analysis](https://blog.traderspost.io/article/alpaca-paper-trading)
- Alpaca serves 195+ countries. A Portuguese tax resident, including a Brazilian citizen who is tax-resident in Portugal, can open a live account as a Portugal resident — [Alpaca Support: countries](https://alpaca.markets/support/countries-alpaca-is-available); [Alpaca International](https://alpaca.markets/international)
- Press release (July 7, 2026): "Alpaca Completes EEA Passporting to 29 Countries." I could not fetch the full text, so the issuing entity and regulator are unverified — [BusinessWire headline](https://www.businesswire.com/news/home/20260707116782/en/Alpaca-Completes-EEA-Passporting-to-29-Countries-Expanding-Access-to-Regulated-Investment-Services-Across-Europe)
- Alpaca market data: the free "Basic" plan is the default for both paper and live accounts, with real-time equities from **IEX only** and 200 requests/min. Algo Trader Plus (about $99/mo) adds full SIP and 10,000 requests/min. Without a subscription, historical SIP queries must end at least 15 minutes in the past — [Alpaca Data](https://alpaca.markets/data); [Alpaca Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq); [About Market Data API](https://docs.alpaca.markets/us/docs/about-market-data-api)

**Interactive Brokers**
- To use IB data in a paper account, you share the live account's market-data subscriptions with it (Account Management → Settings → Paper Trading). Sharing can take up to 24 hours. Data subscriptions are tied to each username — [QuantConnect IB docs](https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/brokerages/interactive-brokers)
- API access does not include free real-time data, so you still need paid market-data subscriptions — [IBKR API solutions](https://www.interactivebrokers.com/en/trading/ib-api.php); [Quantt tutorial 2026](https://www.quantt.co.uk/resources/interactive-brokers-api-tutorial)
- `ib_async` (successor to `ib_insync`) is the common asyncio Python wrapper over the TWS API, used in place of IBKR's official event-driven `ibapi` — [PyPI ib_async](https://pypi.org/project/ib_async)

**Tradier**
- The Tradier sandbox is a paper account with the full trading API. All sandbox market data is **delayed 15 minutes** — [Tradier FAQ](https://docs.tradier.com/docs/faq); [Tradier endpoints](https://docs.tradier.com/docs/endpoints)

**Crypto testnets**
- **Binance Spot Testnet** (testnet.binance.vision) resets about monthly **without notice**. Orders are wiped and balances are refilled, but API keys persist — [Binance Dev Docs: testnet](https://developers.binance.com/docs/binance-spot-api-docs/testnet/general-info)
- **Bybit Demo Trading**: REST at `https://api-demo.bybit.com`, private WebSocket at `wss://stream-demo.bybit.com`. Public data is the same as mainnet. Accounts start with 50,000 USDT, 50,000 USDC, 1 BTC and 1 ETH — [Bybit API: Demo Trading](https://bybit-exchange.github.io/docs/v5/demo)
- **Coinbase Advanced Trade sandbox** (`api-sandbox.coinbase.com`): all responses are **static and pre-defined**, and only the Accounts and Orders endpoints exist. It is useful for testing code paths, not for simulating trading — [Coinbase Dev Docs: sandbox](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/sandbox)
- **Kraken**: a full demo environment exists for **Futures** only (demo-futures.kraken.com, separate API keys, periodic resets) — [Kraken Support: API testing environment](https://support.kraken.com/articles/360024809011-api-testing-environment-derivatives)
- **Hyperliquid testnet**: mock USDC from the faucet. The faucet requires that the same address has previously deposited on mainnet (up to 1,000 mock USDC) — [Hyperliquid Docs: testnet faucet](https://hyperliquid.gitbook.io/hyperliquid-docs/onboarding/testnet-faucet)

### Inferences
- A sensible default stack for a Portugal- or EU-based user is Alpaca paper (US equities/ETFs, IEX data) plus Bybit Demo or the Binance testnet for crypto. Use IBKR if EU-listed instruments or a broader asset range are needed.
- Paper P&L will overstate live results, especially for small caps, large orders, and frequent trading. Model slippage separately, for example with a fixed number of basis points plus a spread cost. Size orders against real quoted depth.
- IEX carries only a small share of consolidated volume, so IEX-only quotes and bars can differ from SIP. Strategies that are sensitive to intraday price levels should be checked against delayed SIP history.

### Gaps
- I could not verify current Alpaca rules for Brazil-resident live accounts, or which Alpaca entity and regulator covers EEA clients. The press release was blocked.
- I did not verify whether Alpaca's options and crypto paper trading are available to non-US accounts.
- I did not research Brazil-specific brokers with B3 APIs or simulators (for example, B3's simulator or MetaTrader-based brokers).

## (b) Market data sources: free vs paid, rate limits

### Takeaway
Free tiers are fine for development and end-of-day strategies, but they are tightly throttled. Use Alpaca IEX for real-time US equities and SEC EDGAR for fundamentals and filings, which is free and limited to 10 requests/second. Treat yfinance as unreliable.

### Cited Findings
- **Massive** (Polygon.io rebranded in October 2025): the free Basic tier allows 5 calls/min with end-of-day and 15-minute-delayed data. Stocks Starter costs $29/mo (unlimited calls, delayed), Developer $79/mo, and Advanced $199/mo (real-time). Rate limits apply per asset class — [Massive KB: request limit](https://massive.com/knowledge-base/article/what-is-the-request-limit-for-massives-restful-apis); [pricing summary](https://qveris.ai/guides/polygon-pricing-optimized/)
- **Alpha Vantage** free tier: 25 requests/day and about 1 request/second. Paid plans raise the limits — [Alpha Vantage Premium](https://www.alphavantage.co/premium/); [Alpha Vantage Support](https://www.alphavantage.co/support/)
- **SEC EDGAR**: at most 10 requests/second per user across all machines, and a descriptive User-Agent is required — [SEC: Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data); [SEC Developer Resources](https://www.sec.gov/about/developer-resources)
- **yfinance** is unofficial and scrapes Yahoo endpoints. Its limits are undocumented, and users frequently hit `YFRateLimitError` blocks — [yfinance issue #2422](https://github.com/ranaroussi/yfinance/issues/2422); [yfinance discussion #2431](https://github.com/ranaroussi/yfinance/discussions/2431)
- IEX Cloud has shut down, so it is no longer an option — [Alpha Vantage IEX Cloud shutdown analysis](https://www.alphavantage.co/iexcloud_shutdown_analysis_and_migration/)
- Alpaca data: see section (a). Free is IEX-only at 200 requests/min; SIP costs about $99/mo — [Alpaca Data](https://alpaca.markets/data)

### Inferences
- Cache aggressively and store bars locally (for example in Parquet or DuckDB) so the agent never re-fetches the same data and always sees a snapshot you can reproduce.
- For an LLM agent, EDGAR (10-K, 10-Q, 8-K, XBRL company facts) is the highest-value free source of fundamentals.

### Gaps
- Tiingo, Financial Modeling Prep, CoinGecko, and news-API free-tier limits were not verified this session because of the tool-call budget. Check their pricing pages directly.

## (c) Guardrails for autonomous agents, PDT rule, wash sales, testing

### Takeaway
The PDT $25,000 rule is gone. The SEC approved FINRA's Rule 4210 amendments on April 14, 2026, effective June 4, 2026, and brokers have until October 20, 2027 to implement them. Intraday margin monitoring replaces it, so broker behavior may differ during the transition. The main safety principle is that the LLM only proposes trades. Deterministic code outside the model validates and enforces every limit.

### Cited Findings
- SEC approval of SR-FINRA-2025-017 (Rule 4210 amendments) removes the $25k minimum equity requirement and the "pattern day trader" designation — [SEC Release 34-105226](https://www.sec.gov/files/rules/sro/finra/2026/34-105226.pdf); [FINRA Regulatory Notice 26-10](https://www.finra.org/rules-guidance/notices/26-10) (page blocked; details from search summary)
- The change takes effect June 4, 2026. Firms may implement until October 20, 2027. Firms can choose real-time intraday margin monitoring, which can block trades that create or increase an intraday margin deficit, or a single end-of-day check — [Schwab summary](https://www.schwab.com/learn/story/sec-approves-scrapping-25000-day-trader-minimum); [QuantInsti](https://www.quantinsti.com/articles/finra-pdt-rule-removal-2026/)
- Alpaca paper trading ignores liquidity and slippage (see (a)). Alpaca's own guide discusses when to move from paper to live — [Alpaca: paper vs live](https://alpaca.markets/learn/paper-trading-vs-live-trading-a-data-backed-guide-on-when-to-start-trading-real-money)
- Wash sale rule (US): a loss is disallowed if you buy substantially identical securities within 30 days before or after the sale. The disallowed loss is added to the cost basis of the replacement shares — [IRS Publication 550](https://www.irs.gov/publications/p550) (standard rule; page not re-fetched this session)

### Inferences (recommended guardrail design; practitioner consensus, not sourced to a single authority)
- **Order validation outside the LLM**: the model outputs a structured order proposal. A deterministic risk gate checks it before it reaches the broker API, and the model has no direct access to broker credentials.
- **Hard limits in code or config, not in the prompt**: maximum position as a percentage of equity (for example 5–10%), maximum gross exposure, maximum order notional, maximum orders per day, and a ticker allowlist (liquid large caps and ETFs). Initially: long-only, cash account, no margin, options, shorts or leverage.
- **Circuit breakers**: stop trading for the day after a daily loss of X%. Halt and require a human to re-enable after a peak-to-trough drawdown of Y%. Stop on repeated API errors or stale data (for example, a quote older than N seconds).
- **Kill switch**: one command or flag that cancels all open orders, optionally flattens positions, and disables the agent. Test it regularly.
- **Idempotency**: use deterministic `client_order_id` values (Alpaca and most brokers support them) so retries cannot place duplicate orders. Reconcile positions against the broker on every loop.
- **Audit log**: an append-only record of every prompt, input data snapshot, model version, rationale, proposed order, risk-gate verdict, and broker response. This supports debugging and also tax and regulatory record-keeping.
- **Human override and alerts**: push or Telegram/email alerts on fills, limit breaches, and errors. Optionally require human approval for orders above a size threshold, or during the first weeks of live trading.
- **Separation of environments**: separate keys and config for paper and live, a live mode that must be explicitly opted into, and a small capital cap at go-live.
- **Testing**: backtest with realistic costs and no look-ahead. LLM-specific risk: models may have "seen" historical prices in training, so backtests of LLM decisions are contaminated. Forward-test on paper for weeks or months, then go live with small size and compare live fills to paper.
- **PDT in the transition**: until your broker implements the new rule (as late as October 2027), check whether it still enforces the old PDT logic. A cash account avoids PDT, but you must track settled funds (T+1).
- **Wash sales**: an agent that frequently re-enters the same tickers will trigger wash sales often (US taxpayers). Log lots and flag re-buys within 30 days of a loss.

### Gaps
- I could not read the full text of FINRA Notice 26-10, including any residual minimum equity amounts (for example, whether the $2,000 margin minimum still applies) and the new intraday margin formula.
- I found no official regulator guidance specific to guardrails for retail LLM agents. The list above is engineering best practice.

## (d) Legal/regulatory: US, EU (MiFID II/ESMA), Brazil (CVM), taxes, broker ToS

### Takeaway
In the US, the EU, and Brazil, running an automated or AI strategy on your **own** account through a retail broker is generally lawful and does not require a license. It becomes regulated when you trade for others, give personalized advice, or sell signals (investment adviser/manager rules in the US, MiFID investment services in the EU, CVM Resolution 19/21 consultancy in Brazil). High-frequency techniques and direct market access in the EU also remove the own-account exemption.

### Cited Findings
**EU**
- MiFID II Art. 2(1)(d) exempts persons dealing on own account in non-commodity instruments who provide no other investment services. The exemption is lost for members of or participants in a regulated market or MTF, those with **direct electronic access**, those using **high-frequency algorithmic trading**, and those dealing on own account while executing client orders — [ESMA Interactive Single Rulebook, Art. 2](https://www.esma.europa.eu/publications-and-data/interactive-single-rulebook/mifid-ii/article-2-exemptions); [Euronext summary](https://www.corporatesolutions.euronext.com/blog/mifid-ii/dealing-on-own-account)
- ESMA's public statement of May 2024 on AI in retail investment services is aimed at **firms** (investment firms and credit institutions) using AI. It highlights organisational requirements, conduct, transparency and data quality under MiFID II — [ESMA statement](https://www.esma.europa.eu/document/public-statement-ai-and-investment-services); [ESMA press](https://www.esma.europa.eu/press-news/esma-news/esma-provides-guidance-firms-using-artificial-intelligence-investment-services)
- ESMA issued a supervisory briefing on algorithmic trading on February 26, 2026 for national regulators. It expects firms to consider AI's influence on their algorithms in their annual self-assessments — [Macfarlanes](https://www.macfarlanes.com/insights/102mpep/algorithmic-trading-and-artificial-intelligence-esma-supervisory-briefing/)

**US**
- Under the Advisers Act, advice for compensation generally requires registration. The "publisher's exclusion" (Lowe v. SEC, 1985) covers only impersonal, bona fide publications of general and regular circulation. Personalized or signal-for-pay services risk falling outside it — [Justia: Lowe v. SEC](https://supreme.justia.com/cases/federal/us/472/181/); [IBKR webinar PDF on publisher exclusion](https://www.interactivebrokers.com/webinars/spotlight-publisher-exclusion.pdf); [Greenberg Traurig on Seeking Alpha](https://www.gtlaw.com/en/insights/2024/8/no-need-for-seeking-alpha-to-seek-registration)

**Brazil**
- CVM Resolution 19/2021 (securities consultancy): consultancy delivered through automated systems or algorithms is still subject to the Resolution (Art. 17). Registration applies to pre-defined strategies where the investor has little or no control over parameters. It does **not** cover those who only sell automated systems that execute decisions the investor makes — [CVM Resolução 19](https://conteudo.cvm.gov.br/legislacao/resolucoes/resol019.html); [CVM investor portal: Robôs de Investimento](https://investidor.cvm.gov.br/menu/Menu_Investidor/prestadores_de_servicos/robos_investimento.html); [gov.br: robôs de investimentos](https://www.gov.br/investidor/pt-br/investir/como-investir/profissionais-do-mercado/robos-de-investimentos)

**Taxes (high level)**
- **Brazil**: stock gains are taxed at 15% (swing trade), with a R$20,000/month sales exemption, and 20% for day trades, which have no exemption. MP 1.303/2025, which proposed a flat 17.5%, was rejected, so the old rates remain for 2026 — [Daycoval on MP 1303](https://blog.daycoval.com.br/mp-1303/); [InfoMoney](https://www.infomoney.com.br/mercados/day-trade-pode-ter-queda-de-20-para-175-em-aliquota-mas-swing-trade-deve-ter-alta/); [XP](https://conteudos.xpi.com.br/aprenda-a-investir/relatorios/day-trade-no-imposto-de-renda/)
- **Portugal**: securities gains are taxed at a 28% flat rate, or optionally aggregated with other income. For short holdings (under 365 days), aggregation into progressive rates is **mandatory** when taxable income is at or above the top bracket (about €86,634 for 2026 income). Crypto held under 365 days is taxed at 28%; crypto held 365 days or more is exempt — [CGD](https://www.cgd.pt/Site/Saldo-Positivo/leis-e-impostos/Pages/impostos-investimentos.aspx); [Portal das Finanças: Criptoativos](https://info.portaldasfinancas.gov.pt/pt/apoio_contribuinte/Folhetos_informativos/Documents/Criptoativos.pdf); [ECO 2026](https://eco.sapo.pt/2026/04/27/como-preencher-o-irs-se-comprou-ou-vendeu-criptoativos/)
- **US**: see the wash sale note in (c) — [IRS Pub 550](https://www.irs.gov/publications/p550)

### Inferences
- High-frequency trading (co-location, sub-second order churn) is out of scope for a retail LLM agent anyway. An LLM system trading on a timescale of minutes to days through a retail broker API stays within "own account" in all three jurisdictions.
- The main legal triggers to avoid are: trading other people's money (including friends or family pooled accounts), selling or publishing personalized signals, or marketing the bot as an advisory product. Any of these calls for a lawyer in the relevant jurisdiction.
- Tax residency drives taxes, not where the broker is located. Portugal's rules favor holding periods of 365 days or more, which conflicts with high-turnover strategies. In Brazil, a US broker's gains are foreign-asset income under separate rules, which were not researched here.
- Broker terms of service: API trading is the intended use case at Alpaca, IBKR and Tradier. The usual prohibitions cover abusive order rates, manipulation (spoofing, wash trading, i.e. self-matching), and sharing credentials. Respect documented rate limits.

### Gaps
- I did not verify specific broker ToS clauses (Alpaca, IBKR) on automated trading. They were not fetched because of budget and proxy blocks.
- Brazil's tax treatment of gains from foreign brokers or offshore accounts (Law 14.754/2023) and crypto taxation were not verified.
- EU MiCA implications for crypto-asset service providers and retail crypto bots were not researched.
- I found no ESMA or CVM statement specifically addressing individuals using LLM agents on their own accounts. Existing guidance targets firms.
