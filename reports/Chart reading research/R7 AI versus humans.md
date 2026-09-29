# R7: Can an AI read charts, and what could "a bot 10 times more efficient than humans" honestly mean?

> **Read `00 Fact-check corrections (read first).md` alongside this file.** Written on 28 Sept 2026 by a research agent; four independent fact-checkers then reviewed its main claims, and where they differ from the text below, the corrections file wins. Scripts behind the researcher's own calculations are in `scripts/` (paths such as `work/`, `r5/` or `research/` in the text point there; they expect data files downloaded separately). Terms like verified / UNVERIFIED are the researcher's own tags.


*Research note for the IAMGOD minute-trading project. Written 28 Sept 2026 (system clock shows 29 Sept). Research only: no orders, no broker or trading API calls, no repo edits, no git. Everything below comes from papers, filings and vendor pages I opened, or from arithmetic I did on their numbers.*

**How to read the tags.** `verified` = I read it in the paper text, the official page or the abstract page myself (the note says which). `UNVERIFIED` = I only saw it in a search snippet, a fetch summary I could not cross-check, a blog, or the repo's own reports, or I could not open the primary page. Evidence strength labels: **Strong / Mixed / Weak / None / Not testable**. "Preprint" = not peer reviewed as far as I could tell.

**Terms in one line each.**
- bp / bps: 0.01%. On one SPY share (about $766) 1 bp is about 7.7 cents.
- Sharpe ratio: yearly average return divided by its ups and downs. Around 0.5 is decent, 1 is good, and numbers above 2 are rarely real after costs.
- IC (information coefficient): the correlation between a forecast and what happened. 0.02 to 0.05 is tiny but can matter if you make thousands of independent bets.
- Out-of-sample R2: the share of surprise the model explains on data it never saw. Below zero means worse than guessing the average.
- VLM: an AI that reads pictures plus text. LLM: text-only AI.
- SIP / IEX: the full consolidated US price feed versus one small exchange's feed (IEX is about 2 to 3% of volume).
- Deflated Sharpe: a Sharpe ratio marked down for how many things you tried.
- Co-location: putting your computer inside the exchange's own data centre.

---

## 1. Plain-English summary

1. AI can describe a chart in words but reads charts worse than people. On CharXiv (2024) the best model scored 47.1% on hard questions against 80.5% for humans; on financial charts open questions top out at about 60 to 64% and "estimate a value" at about 41%.
2. Two 2026 candlestick tests found the models follow the recent trend instead of reading the candles: injected candle signals were not recovered (AUC 0.47 to 0.52; 0.50 is a coin flip) and direction accuracy on real stocks was 49 to 53%. New preprints, not yet replicated.
3. I found no controlled real-market test showing a picture beats a clean table of code-computed numbers. In the best chart-image paper (Jiang, Kelly, Xiu) a key part of the picture's advantage is rescaling the data; a linear model on rescaled numbers gives a reasonable copy of it.
4. LLM and VLM trading agents have no proven edge: a 20-year re-test (FINSABER), a live 2026 study of thousands of agents, and an audit of 77 studies (only 1 in 19 modelled costs) all say so or say the evidence is too weak.
5. Machine learning that learns from prices finds signal only in big stock panels at daily or longer horizons, mostly small illiquid stocks, and costs kill it: one 2025 study's daily Sharpe goes from +6.4 to -3.6 at 20 bps. SPY and QQQ are probably the hardest ground (my inference).
6. Humans mostly lose: 97% of persistent Brazilian day traders lost money and under 1% of Taiwanese ones were predictably profitable. So "10X better than humans" is either easy (stay flat) or undefined (10 times a loss).
7. The machines that win (Virtu: one losing day in 1,238; Renaissance Medallion) win on speed, co-location, direct feeds, rebates and volume, measured in microseconds, not by reading charts. A cloud bot on a free IEX feed with an LLM in the loop cannot play that game.
8. "Efficiency" can honestly be 10X for coverage, consistency, record keeping, research speed and cost per decision. But more tests raise the bar: 28 zero-skill tries on 2 years of data already give a luck-only best Sharpe of about 1.45.
9. Design: code reads the charts into a structured multi-timeframe report; the LLM may only explain and veto, with a scorecard; learned models must beat frozen rules under the Notes v3 M1/B1 plan; pictures get one controlled side test.
10. Realistic result: about zero net return, better discipline and records, faster research. Even a true Sharpe of 0.5 needs 11 to 15 years of daily data to detect at even odds. Stop rules are in section 4.7.

---

## 2. Findings table

Columns: item | what it is | evidence and strength | horizon and market | after costs? | source | verified?

### 2A. Can an AI read a chart? (benchmarks and known failure modes)

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| ChartQA (Masry et al., ACL Findings 2022) | 9.6K human-written plus 23.1K generated chart questions | **Not testable** for trading. Later called "saturated" by modern models (ChartQAPro abstract), so high scores here say little | general charts | n/a | [arXiv 2203.10244](https://arxiv.org/abs/2203.10244) | verified (abstract) |
| CharXiv (Wang et al., NeurIPS 2024 D&B) | 2,323 real charts from arXiv papers; descriptive and reasoning questions | **Strong** that hard chart reasoning lagged humans in 2024: GPT-4o 47.1%, best open model 29.2%, humans 80.5%; small chart or question changes cut older-benchmark scores by up to 34.5%. Project README (older models only) lists Claude 3.5 Sonnet 60.2% reasoning and 84.3% descriptive against humans 80.5% and 92.1% | scientific charts | n/a | [arXiv 2406.18521](https://arxiv.org/abs/2406.18521); [README](https://github.com/princeton-nlp/CharXiv) | verified (abstract); README digits via page summary; 2025-26 frontier scores UNVERIFIED |
| ChartQAPro (Masry et al., ACL Findings 2025) | 1,341 charts, 157 sources, 1,948 questions incl. dashboards and unanswerable ones; 21 models | **Strong**: one leading model drops from 90.5% (ChartQA) to 55.81% here | general | n/a | [arXiv 2504.05506](https://arxiv.org/abs/2504.05506) | verified (abstract) |
| "Vision language models are blind" (Rahmanzadehgervi et al., ACCV 2024) | 7 elementary tasks (line crossings, circle overlap, counting) | **Strong** that low-level perception is shaky: 4 leading VLMs 58.07% on average, best 77.84%; fail when shapes overlap or sit close | synthetic shapes | n/a | [arXiv 2407.06581](https://arxiv.org/abs/2407.06581) | verified (abstract) |
| FinChart-Bench (Shu et al., Jul 2025; ACL 2026) | 1,200 financial chart images (2015-2024), 7,016 true/false, multiple-choice and open questions; 25 models | **Mixed**: easy formats fine (multiple choice up to about 84%; GPT-4o average 76.62%) but open questions top out near 60% (best closed model 63.59%, best open 59.78%). Models fail to map bars and lines to values unless numbers are printed on the chart. Not candlestick-specific (no "candlestick" in the text) | financial charts | n/a | [arXiv 2507.14823](https://arxiv.org/abs/2507.14823) | verified (read text) |
| MME-Finance (HiThink Research et al., 2024) | Finance visual Q&A with candlestick and indicator charts, screenshots and phone photos; 19 models | **Mixed/Weak**: best open model 65.69%, best closed (GPT-4o) 63.18%; "particularly poor" on candlestick and indicator charts; estimate-a-number accuracy 40.95% versus exact calculation 83.76%; spatial awareness best 30.31% (e.g. telling close moving-average lines apart). Caveat: authors at a financial-data firm; questions drafted and answers graded with GPT-4o; preprint | financial screenshots | n/a | [arXiv 2411.03314](https://arxiv.org/abs/2411.03314) | verified (read text) |
| "Do VLMs Truly Read Candlesticks?" (Hu et al., Apr 2026) | 193,524 daily and weekly candlestick images (50 bars, moving averages, volume) of HS300 and S&P 500 stocks; 30-day forward return; 7 commercial VLMs against XGBoost; test window 1 Jan 2023 to 1 Jan 2025 | **Weak**: direction accuracy 49.4% to 53.5% (HS300); mean IC from -0.018 to +0.047 (HS300), best single 0.090 (Gemini 2.5 Pro on S&P 500); authors say models work only in persistent up or down trends. Authors also claim charts beat "equivalent tabular data", but that compares a VLM on charts with XGBoost on tables (different models), so it is not a controlled picture-versus-numbers test. Chart headers show stock code and date. The authors ran a limited "peeping" check (two GPT-4o snapshots over May-Nov 2024, no sign of leakage), which does not cover the 2025 models; those were probably trained on data that includes the 2023-2024 test window (my inference), so leakage is not excluded | daily and weekly; China and US large caps | No trading, no costs | [arXiv 2604.12659](https://arxiv.org/abs/2604.12659) | verified (read text) |
| Martingale Doppelganger-Eval (Z. Wang, Jun 2026) | Synthetic "shadow market" with injected candlestick rules; 7 frozen VLMs (GPT-5.3, GPT-4.1, a Claude Sonnet API model, GPT-4o, Qwen2.5-VL-7B, LLaVA-OV-7B, InternVL3-8B) | **Weak** for VLM candle reading: injected-signal AUC 0.469 to 0.517 (chance 0.5); every model leans on past trend (log-odds +0.20 to +0.41); candlestick-evidence coefficient about zero for open models and significantly negative for all four commercial APIs (e.g. -0.17); a fine-tuned control reaches 0.91, so the task is learnable. Caveats: single-author preprint; synthetic charts are recognisable (generator AUC 0.93); 60-bar windows, 5-bar horizon | synthetic plus public OHLCV | No | [arXiv 2606.17423](https://arxiv.org/abs/2606.17423) | verified (read PDF) |
| Confidence estimation for financial VLMs (Khanmohammadi et al., Aug 2026) | 7 confidence estimators on 5 open-weight VLMs, financial chart and document Q&A | **Mixed**: plain inference baselines are "severely overconfident"; only trained probes give usable scores; at a strict 5% error budget almost none of the hardest cases can be automated | financial Q&A | n/a | [arXiv 2608.06532](https://arxiv.org/abs/2608.06532) | verified (abstract) |
| AgentFinVQA (Narayanan and Raza, Jun 2026) | Multi-agent checking pipeline for financial chart Q&A on FinMME | **Mixed**: 71.24% versus 63.56% for the plain model; answers the verifier confirmed were 68.2% right versus 55.6% for revised ones; about two thirds of failures are misunderstanding, legend confusion and extraction errors, which the verifier misses most | financial charts | n/a | [arXiv 2606.19782](https://arxiv.org/abs/2606.19782) | verified (abstract) |
| Chart data extraction benchmark (He et al., Jun 2026) | MLLMs asked to rebuild the data table from an unlabelled chart | **Mixed**: models "reliably reconstruct table structures" but "struggle with precise value recovery" | general charts | n/a | [arXiv 2606.29808](https://arxiv.org/abs/2606.29808) | verified (abstract) |
| Vendor vision documentation (API provider, current) | How images are billed and the vendor's own limits | The vendor says the model "might hallucinate or make mistakes" on low-quality or small images, spatial and coordinate outputs are approximate, counts are approximate, and it should not be used "for tasks requiring perfect precision" without human oversight. Cost = ceil(width/28) x ceil(height/28) tokens (a 1000x1000 image = 1,296 tokens). Vendor source (sells tokens) | n/a | n/a | [platform.claude.com vision docs](https://platform.claude.com/docs/en/build-with-claude/vision) | verified (read page); example prices may change |
| "Plots unlock time-series understanding" (Daswani et al., Google, 2024) | Give a multimodal model a plot instead of the numbers as text | **Mixed**: plots beat text by up to 120% on synthetic zero-shot tasks and up to 150% on real health tasks (fall detection, activity), and cut API cost by up to 90%. No financial data | non-finance | n/a | [arXiv 2410.02637](https://arxiv.org/abs/2410.02637) | verified (abstract) |
| "Are language models actually useful for time series forecasting?" (Tan et al., NeurIPS 2024) | Ablation of three LLM-based forecasters | **Strong (negative)**: removing the LLM or swapping in a basic attention layer does not hurt, "in most cases the results even improve"; pretrained LLMs are no better than models trained from scratch | general series | n/a | [arXiv 2406.16964](https://arxiv.org/abs/2406.16964) | verified (abstract) |

**Reading the block.** Qualitative shape (up, down, sideways) is where models do best; exact levels, dates, line crossings and "which of these close lines is highest" are where they fail (FinChart-Bench, MME-Finance, He et al., Vision-language-models-are-blind). Candlestick logic specifically is not being read: models follow the recent trend (Hu, Wang). Overconfidence is documented (Khanmohammadi; the vendor's own warning). I looked for a benchmark that gives the same model the same information as a picture, as a raw table and as a summary on real market data, and found none.

### 2B. LLM and VLM trading agents (including ones that use chart images)

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| FinAgent (Zhang et al., KDD 2024) | Multimodal agent using numbers, news and Kline chart images, with reflection and memory | **Weak (claim to test)**: authors report over 36% average profit improvement against 9 baselines on 6 datasets and a 92.27% return on one. Independent re-test by FINSABER over 2004-2024: FinAgent Sharpe 0.12 in bull and -0.38 in bear regimes, behind rule-based benchmarks (FINSABER does not say whether the chart input was used) | daily to intraday; stocks and crypto | not stated in abstract | [arXiv 2402.18485](https://arxiv.org/abs/2402.18485) | verified (abstract, authors' claims); FINSABER read |
| QuantAgent / QuantHarness (Xiong et al., Sep 2025, v4 Jul 2026) | LLM agents (indicator, pattern, trend, risk) on price signals and pattern charts | **Weak**: better directional accuracy than baselines at 1-hour and 4-hour bars on 9 instruments. The authors' own limits section: precision drops on 1 to 15 minute candles ("dominated by noise"), and one LLM inference cycle "can exceed the window in which a 1-minute opportunity remains exploitable". No cost or slippage modelling found in the text | 1h and 4h; commodities, equities, crypto, volatility index | No | [arXiv 2509.09995](https://arxiv.org/abs/2509.09995) | verified (read text) |
| Agent Trading Arena (Ma et al., EMNLP Findings 2025) | LLM agents in a virtual zero-sum stock market; text versus chart inputs; plus a 2-month NASDAQ and 1-year CSI backtest | **Weak**: GPT-4o total return 33.65% with text and 47.70% with visual input. It is a simulated market; the NASDAQ test ran 3 Sep to 29 Oct 2024 (two months); no realistic costs. Not evidence for real markets | daily; simulated | No | [arXiv 2502.17967](https://arxiv.org/abs/2502.17967) | verified (read text) |
| StockBench (Chen et al., Oct 2025, v2 Mar 2026) | Contamination-free multi-month stock trading benchmark (prices, fundamentals, news) | **Mixed**: "most models struggle to outperform the simple buy-and-hold baseline". The repo report quotes -2.8% to +2.5% against +0.4% over 82 days on 20 Dow stocks; I did not re-check those figures | daily; US large caps | not checked | [arXiv 2510.02209](https://arxiv.org/abs/2510.02209) | verified (abstract); figures UNVERIFIED by me |
| FINSABER (Li et al., KDD 2026 D&B, oral) | 2004-2024 backtest, 100+ symbols; re-tests FinMem and FinAgent | **Strong against LLM alpha**: "previously reported LLM advantages deteriorate significantly under broader cross-section and over a longer-term evaluation"; too cautious in bull markets, too aggressive in bear markets. Commissions modelled ($0.0049 per share, $0.99 minimum), no spread or slippage | daily; US stocks | Partly (commissions) | [arXiv 2505.07078](https://arxiv.org/abs/2505.07078) | verified (abstract and text) |
| LiveTradeBench (Yu et al., Nov 2025) | 50-day live test of 21 LLMs on US stocks and Polymarket | **Weak**: high chatbot-leaderboard scores do not imply better trading; 50 days is too short to show skill | live; daily | not stated | [arXiv 2511.03628](https://arxiv.org/abs/2511.03628) | verified (abstract) |
| Audit of LLM trading studies (Xia et al., May 2026) | 77 studies screened, 19 with closed-loop evaluation | **Strong about evidence quality**: only 2 of 19 use time-consistent splits, 1 of 19 an explicit transaction-cost model, 1 of 19 handles survivorship, 15 of 19 rated R0, none reach R3 reproducibility | various | 1 of 19 | [arXiv 2605.19337](https://arxiv.org/abs/2605.19337) | verified (abstract) |
| DX Terminal Pro and DXAP production record (Barton et al., 4 Sep 2026) | 3,505 user-funded vaults (Qwen3-235B agents, real ETH, memecoins, 21 days) plus 500-599 agents on Hyperliquid perpetuals (mostly paper accounts, Jun-Aug 2026) | **Mixed to Strong for a negative**: "neither fleet shows a directional edge"; 16.2% of vaults finished profitable; DXAP fleet not profitable, 41% versus 50% roundtrip win rate for a retail benchmark, 15% of active agents net-positive versus 53% of retail; agents keep almost none of the upside they reach (median capture 2.0%); frontier models statistically indistinguishable in a 416-scenario replay; agents invented funding income on a venue that pays none. Caveats: crypto, preprint by the platform operators, most fills are paper with zero slippage | hours to days; crypto | Mixed (fees restated; paper slippage zero) | [arXiv 2609.05663](https://arxiv.org/abs/2609.05663) | verified (read text) |
| Alpha Arena (nof1, Season 1 Oct-Nov 2025) | Live tournament: six models, $10K each, Hyperliquid perpetuals | **None as evidence**. The DX paper calls such leaderboards "tournaments rather than measurement programs". Per-model results (repo notes 4 of 6 lost) | crypto | n/a | [nof1.ai](https://nof1.ai) (returned HTTP 403 to me) | description verified; all numbers UNVERIFIED |
| TradeTrap (Yan et al., Dec 2025) | Stress tests of LLM trading agents on real US equity history | Small perturbations in one component "can propagate through the agent decision loop" into concentration, runaway exposure and large drawdowns | historical; US equities | n/a | [arXiv 2512.02261](https://arxiv.org/abs/2512.02261) | verified (abstract) |
| SoK on academic LLM trading schemes (Wang and Saxena, 17 Sep 2026) | 15 academic schemes tested for robustness and security | "80% fail at least one core robustness metric and 100% exhibit security vulnerabilities" | n/a | n/a | [arXiv 2609.19705](https://arxiv.org/abs/2609.19705) | verified (abstract) |
| LLM memorisation (Lopez-Lira, Tang and Zhu, 2025) | LLMs recall exact economic and financial values from before their cutoff | **Strong contamination risk**: telling the model to respect historical boundaries fails; masking fails; no recall after the cutoff | n/a | n/a | [arXiv 2504.14765](https://arxiv.org/abs/2504.14765) | verified (abstract) |
| BlindTrade (Jeon and Lee, Mar 2026) | Anonymise tickers so agents cannot use memorised names; GNN plus RL policy | **Weak (claim to test)**: Sharpe 1.40 (+/-0.22 over 20 seeds) on 2025 to 1 Aug; extended 2024-2025 test shows regime dependence | daily; US stocks | not stated | [arXiv 2603.17692](https://arxiv.org/abs/2603.17692) | verified (abstract) |
| TiMi "Trade in Minutes" (Song et al., 2025-26) | LLM designs the strategy and writes code; a deterministic bot trades at minute level | Design idea matches "code executes, model designs". Claims of "stable profitability" on 200+ pairs are unverified; abstract does not state costs | minute; stocks and crypto | not stated | [arXiv 2510.04787](https://arxiv.org/abs/2510.04787) | verified (abstract); results UNVERIFIED |

**Reading the block (what was measured and what was not).** Measured: returns, Sharpe ratios or direction accuracy over short windows, mostly daily bars, mostly US large caps or crypto. Not measured, or rarely: transaction costs (1 of 19 studies in the audit; FINSABER adds commissions only), multiple-testing corrections, training-data leakage (BlindTrade, Martingale and, partly, Hu et al. are the exceptions), real latency, capacity, and any picture-versus-numbers ablation on real markets. The longest independent tests (FINSABER 2004-2024; the DX 2026 record) find no edge; the positive papers are short, uncosted or simulated. Live tournaments are contests, not measurements (the DX paper's wording).

### 2C. Machine learning that learns patterns straight from data

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| Jiang, Kelly and Xiu (J Finance 78(6):3193-3249, 2023) | CNN on images of OHLC bars, volume and a moving average over 5, 20 and 60 days; trained 1993-2000, tested 2001-2019 on US stocks | **Mixed (strong statistically, weak for us)**: accuracy above 53% at one month; monthly decile-spread Sharpe up to 2.4 equal-weight and 0.5 value-weight; weekly equal-weight up to 7.2, which the authors say should not be read as "trading results that are achievable in practice". One-month turnover about the same as short-term reversal (168% a month). The CNN signal correlates with dollar volume, size, reversal and illiquidity. **One key reason the image helps:** it rescales every stock's recent high and low to the same frame; after that rescaling "a linear model can produce a reasonable approximation to the CNN", though the CNN improves on it | daily bars; thousands of US stocks | No net-of-cost returns | [working paper PDF](https://www.aidf.nus.edu.sg/wp-content/uploads/2022/02/Xiu-Re-Imagining-Price-Trends.pdf); [journal abstract](https://ideas.repec.org/a/bla/jfinan/v78y2023i6p3193-3249.html) | verified (read working-paper version); published-version numbers may differ (a snippet says 7.2 and 1.7 for weekly) UNVERIFIED. Kelly works at AQR (asset manager) |
| Replications of the CNN paper in Korea and China | Titles surfaced in search only | Not read | equities | ? | (titles only) | UNVERIFIED |
| DeepLOB (Zhang, Zohren and Roberts, IEEE TSP 2019) | CNN plus LSTM on limit-order-book snapshots | **Mixed**: beats earlier models on the FI-2010 data set and shows "stable out-of-sample prediction accuracy" on one year of London quotes; the abstract makes no profit claim | order-book updates; equities | No | [arXiv 1808.03668](https://arxiv.org/abs/1808.03668) | verified (abstract) |
| LOBCAST (Prata et al., 2023) | Benchmark of 15 deep order-book models | "All models exhibit a significant performance drop when exposed to new data" | order book | profit analysis included (not read) | [arXiv 2308.01915](https://arxiv.org/abs/2308.01915) | verified (abstract) |
| Briola, Bartolucci and Aste (Quantitative Finance 25(7):1101-1131, 2025) | DeepLOB on 15 NASDAQ stocks, 2017-2019, tick-by-tick | **Strong for "forecast is not profit"**: large-tick stocks reach accuracy above 0.7 and F1 above 0.45 with no threshold (F1 above 0.7, accuracy above 0.9 with probability thresholds), yet "high forecasting power does not necessarily correspond to actionable trading signals"; the utility of the signal is "significantly dependent on the presence of low-latency hardware infrastructures" | tick level; NASDAQ large caps | No (they propose a "probability of completing a correct transaction" measure instead) | [arXiv 2403.09267](https://arxiv.org/abs/2403.09267) | verified (read v4); journal record from search |
| Rahimikia, Ni and Wang (Nov 2025 working paper) | Chronos, TimesFM and 12 other time-series foundation models on daily excess returns of US stocks 2001-2023, plus global | **Strong that off-the-shelf models do not forecast returns**: zero-shot Chronos-large R2 -1.37% (direction just above 51%), TimesFM-500M R2 -2.80% (direction just below 50%); models pretrained from scratch on finance do better. The best benchmark model's daily long-short Sharpe averages 6.44 at 0 bps, **-3.62 at 20 bps and -13.59 at 40 bps**; performance also decays over time. Small caps are more predictable than large caps | daily; broad US stocks | Yes, shown | [FoFI 2026 PDF](http://wp.lancs.ac.uk/fofi2026/files/2026/03/FoFI-2026-020-Eghbal-Rahimikia.pdf) | verified (read text); working paper |
| Alonso and Franklin (Jun 2026) | TimeGPT, TimesFM-2.5, Moirai-2.0, Chronos against NBEATS, NHITS, PatchTST, iTransformer, KAN on AAPL, AMZN, GOOG, JPM, META | **Weak**: pretrained models win 8 of 10 model-versus-model tasks, but gains over a random walk are "small and sparse" (significant in 2 cases); "not universal engines for statistically reliable alpha generation" | daily returns; 5 large caps | No | [arXiv 2606.27100](https://arxiv.org/abs/2606.27100) | verified (abstract) |
| TimesFM (Das et al., ICML 2024) and Chronos (Ansari et al., TMLR 2024) | General time-series foundation models; Chronos pretrained on public data plus synthetic series | **Not testable** for trading by themselves; the papers measure non-financial benchmarks | non-finance | n/a | [arXiv 2310.10688](https://arxiv.org/abs/2310.10688); [arXiv 2403.07815](https://arxiv.org/abs/2403.07815) | verified (abstracts) |
| Kelly, Malamud and Zhou "virtue of complexity" (J Finance 79(1):459-503, 2024) and Nagel critique (NBER WP 34104, 2025) | Thousands of random features to time the US market; Nagel shows the forecast is a recency-weighted average of past returns | **Weak/Mixed**: the paper claims complex models beat simple ones; Nagel shows the forecast reduces to a recency-weighted average of past returns, "essentially a momentum strategy", which does poorly on artificial data with return reversals, so the historical success may reflect favourable market conditions rather than real predictive power | monthly-type; US market index | No | [KMZ abstract](https://ideas.repec.org/a/bla/jfinan/v79y2024i1p459-503.html); [Nagel](https://www.nber.org/papers/w34104) | verified (abstracts) |
| Gu, Kelly and Xiu (RFS 33(5):2223-2273, 2020) | Trees and neural nets on about 30,000 US stocks, 1957-2016 | **Mixed**: monthly stock-level R2 only 0.33% to 0.40%; value-weight decile long-short Sharpe 1.35 (equal-weight 2.45); timing the S&P 500 gives 0.77 versus 0.51 buy-and-hold | monthly; US stocks | No (costs discussed) | [PDF](https://dachxiu.chicagobooth.edu/download/ML.pdf); [abstract](https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2223-2273..html) | verified (read text) |
| Avramov, Cheng and Metzker (Management Science 69(5):2587-2619, 2023) | Economic restrictions on deep-learning strategies | **Strong**: profits come from "difficult-to-arbitrage stocks" and high limits-to-arbitrage periods; excluding microcaps, distressed stocks or volatile episodes "considerably attenuates profitability"; "further deteriorates in the presence of reasonable trading costs" | monthly; US stocks | Yes | [EconPapers](https://econpapers.repec.org/RePEc:inm:ormnsc:v:69:y:2023:i:5:p:2587-2619) | verified (abstract) |
| Human technical analysis: Lo, Mamaysky and Wang (J Finance 2000); Menkhoff and Taylor (J Econ Literature 2007); Bajgrowicz and Scaillet (JFE 2012) | Systematic tests of chart patterns and technical rules | **Weak** for a retail chart-reading edge: some patterns carried "incremental information" in US stocks 1962-1996 (Lo et al.); technical analysis is widespread among FX professionals and "may be profitable" (Menkhoff and Taylor); on the Dow 1897-2011 an investor "would never have been able to select ex ante the future best-performing rules" and even in-sample gains are "completely offset" by low costs (Bajgrowicz and Scaillet) | daily; stocks, FX, Dow index | Bajgrowicz-Scaillet yes | [Lo et al.](https://doi.org/10.1111/0022-1082.00265); [Menkhoff-Taylor](https://doi.org/10.1257/jel.45.4.936); [Bajgrowicz-Scaillet](https://ideas.repec.org/a/eee/jfinec/v106y2012i3p473-491.html) | verified (abstracts) |

**Reading the C block.** Signals learned from data are real in research settings but sit where we are weakest: thousands of stocks (breadth), daily or longer horizons, small and illiquid names, and no or light costs. They shrink out of sample and after publication, and they flip sign when costs are added. Tick-level order-book models need low-latency infrastructure to be usable. A key part of the image advantage in the CNN paper is rescaling the data. None of this was tested on two ETFs.

### 2D. Humans versus the machines that win

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| Barber, Lee, Liu and Odean (J Financial Markets 18:1-24, 2014) | All Taiwanese day traders 1992-2006, ranked by prior-year return | **Strong**: top 500 earn 61.3 bps a day before fees, 37.9 after; bottom-ranked -11.5 before, -28.9 after; "less than 1%" predictably and reliably profitable net of fees | daily; Taiwan | Yes | [RePEc](https://ideas.repec.org/a/eee/finmar/v18y2014icp1-24.html) | verified (abstract) |
| Chague, De-Losso and Giovannetti, "Day trading for a living?" (SSRN 3423101, June 2020 draft) | Every Brazilian who began day trading equity futures 2013-2015 (19,646); 1,551 persisted over 300 days | **Strong**: 97% of persisters lost money net of exchange and brokerage fees; 1.1% (17 people) earned more than the minimum wage; 0.5% (8) more than a bank teller's starting salary; taxes ignored | daily; Brazil futures | Yes (fees) | [PDF](https://ebicapital.nl/wp-content/uploads/2022/05/day-trading.pdf) | verified (read text) |
| Jordan and Diltz (Financial Analysts Journal 59(6), 2003) | US day traders | **Mixed**: "about twice as many day traders lose money as make money"; about 20% were more than marginally profitable. Sample (324 traders, Feb 1998 to Oct 1999) | 1998-99 US | unclear | [CFA Institute page](https://rpc.cfainstitute.org/research/financial-analysts-journal/2003/the-profitability-of-day-traders) | summary verified; sample details UNVERIFIED (snippet) |
| Baron, Brogaard, Hagstromer and Kirilenko (JFQA 54(3):993-1024, 2019) | Latency and profits of high-frequency firms | **Strong**: "differences in relative latency account for large differences in HFT firms' trading performance"; firms that upgrade co-location improve their results | very short horizons | not stated in abstract | [EconPapers](https://econpapers.repec.org/RePEc:cup:jfinqa:v:54:y:2019:i:03:p:993-1024_00) | verified (abstract) |
| Brogaard, Hendershott and Riordan (RFS 27(8):2267-2306, 2014) | HFT and price discovery | HFT orders that take liquidity are informed and predict price changes over seconds; HFT orders that supply liquidity are adversely selected | seconds; equities | n/a | [RePEc](https://ideas.repec.org/a/oup/rfinst/v27y2014i8p2267-2306..html) | verified (abstract) |
| Budish, Cramton and Shim (QJE 130(4):1547-1621, 2015) | Millisecond direct-feed data | Mechanical arbitrage opportunities are built into continuous markets; competition raised "the bar for how fast one has to be", not the size or frequency of the opportunities | ms; US | n/a | [DOI](https://doi.org/10.1093/qje/qjv027) | verified (abstract) |
| Aquilina, Budish and O'Neill (QJE 137(1):493-564, 2022) | Exchange message data, FTSE 100 | Latency-arbitrage races: about one per minute per symbol, modal race 5 to 10 millionths of a second, about 20% of volume, top 6 firms over 80% of wins and losses, about 0.5 bp "tax" on trading, about $5 billion a year in global equities | microseconds; UK | n/a | [NBER](https://www.nber.org/papers/w29011) | verified (abstract) |
| Chordia, Green and Kottimukkalur (RFS 2018; SSRN abstract) | SPY and E-mini reaction to macro news | Prices respond "within five milliseconds"; speed profits small (about $19,000 per event for SPY, $50,000 for E-mini); "speed of information incorporation has increased ... profits have not" | ms; US index | n/a | [SSRN record](https://doi.org/10.2139/ssrn.3062161) | verified (abstract via Crossref) |
| Virtu Financial S-1 (10 Mar 2014) | IPO prospectus of a market maker | "Only one losing trading day during the period depicted, a total of 1,238 trading days" (1 Jan 2009 to 31 Dec 2013), which it credits to real-time risk management. Adjusted Net Trading Income (ANTI, non-GAAP, after exchange and clearing fees) $414.5M in 2013; leases co-location space and custom network; no asset class over 30% of ANTI. **Mixed**: company self-report in a sales document, includes a firm acquired in 2011 | equities, FX, commodities, options; global | ANTI is net of fees | [SEC filing](https://www.sec.gov/Archives/edgar/data/0001592386/000104746914002070/a2218589zs-1.htm) | verified (read text) |
| Virtu FY2025 10-K (20 Feb 2026) | Annual report | ANTI $2,145.3M in 2025 (+34.3%), or $8.6M a day over 248.5 days (2024: $6.4M); volume discounts and exchange rebates are netted against exchange fees; co-location and market-data costs are fixed expenses; the "losing days" statistic is not repeated (phrase not found) | global | net of fees | [SEC filing](https://www.sec.gov/Archives/edgar/data/1592386/000159238626000009/virt-20251231.htm) | verified (read text) |
| Renaissance Medallion: US Senate PSI report (Jul 2014) | Basket-option investigation | RenTec's options at Deutsche Bank (MAPS) produced about $17B and at Barclays (COLT) about $18.5B in trading profits; RenTec estimated 100,000 to 150,000 trades a day with each bank (26 to 39 million a year combined); a Barclays document called Medallion a "very high frequency trader". This shows scale and style, not an investor return series | short-term; many markets | n/a | [PSI report](https://www.hsgac.senate.gov/wp-content/uploads/imo/media/doc/REPORT-Abuse%20of%20Structured%20Financial%20Products%20(Basket%20Options)%20(7-22-14,%20updated%209-30-14).pdf) | verified (read text) |
| Medallion returns: Cornell (JPM 46(4):156, 2020) and Guo and Liu (preprint) | Two views of the fund's compound return | Cornell's abstract (as seen in a search snippet): $100 became $398.7M, 63.3% compound 1988-2018, never a losing year, negative factor loadings. Guo and Liu argue compounding yearly returns overstates it: their estimate is about 31.8% before fees and "probably under 35%" | 1988-2018 | Cornell gross/net mix unclear | [Cornell (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3504766) (blocked); [Guo-Liu](https://arxiv.org/abs/2405.10917) | Cornell UNVERIFIED (snippet); Guo-Liu verified (read). Fund is closed to outsiders and no audited series is public |
| Khandani and Lo (NBER WP 14465, 2008) | The August 2007 quant crash | Crowded quant trades unwound together; at 8:1 leverage a book-to-market portfolio lost 24% by 7 Aug, "sharp reversals" on 10 Aug erased nearly all losses, but a fund that had cut leverage could not recoup them | days; US stocks | n/a | [NBER PDF](https://www.nber.org/system/files/working_papers/w14465/w14465.pdf) | verified (read text); working paper |
| McLean and Pontiff (J Finance 71(1):5-32, 2016) | 97 published return predictors | Returns "26% lower out-of-sample and 58% lower post-publication" | monthly; US stocks | n/a | [Crossref record](https://doi.org/10.1111/jofi.12365) | verified (abstract) |
| Hou, Xue and Zhang (RFS 33(5):2019-2133, 2020) | Replication of 452 anomalies | With microcaps mitigated, 65% fail the usual test; 82% fail a stricter multiple-test hurdle | monthly; US stocks | n/a | [RePEc](https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2019-2133..html) | verified (abstract) |
| Systematic funds' Sharpe ratios (CTAs, multi-strategy) | | I could not open a primary, net-of-fee Sharpe series. The Sharpe numbers I did verify are academic and before costs (1.35 to 2.45 monthly, up to 7.2 weekly, 6.4 to 6.8 daily) | | | | Net-of-fee fund Sharpe ratios UNVERIFIED |

**Reading the D block.** The human base rate is poor and well documented (Taiwan, Brazil, US). The firms that win do so with speed, position and scale, and their published results are self-reported, partial or from a different market. Nothing here shows that faster or cleverer chart reading is what makes them money. Signals also decay when published or crowded (McLean-Pontiff, Hou-Xue-Zhang, Khandani-Lo).

### 2E. Testing traps, human limits and the price of running an AI

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| Harvey, Liu and Zhu (RFS 29(1):5-68, 2016) | Multiple-testing framework for factors | **Strong**: a new factor "needs to clear a much higher hurdle, with a t-statistic greater than 3.0"; "most claimed research findings in financial economics are likely false" | monthly; US stocks | n/a | [RePEc](https://ideas.repec.org/a/oup/rfinst/v29y2016i1p5-68..html) | verified (abstract) |
| Bailey and Lopez de Prado, Deflated Sharpe Ratio (J Portfolio Management 40(5):94-107, 2014) | Sharpe ratio corrected for number of trials and non-normal returns | **Strong (method)**: the expected best Sharpe among N tries of zero-skill strategies rises with N, "even if the true SR is zero". My table below applies their formula | any | n/a | [PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf) | verified (read paper); my numbers are my arithmetic |
| Working-memory limit (Cowan, Behavioral and Brain Sciences 24:87-114, 2001) | How many things a person holds at once | "A single, central capacity limit averaging about four chunks" | human | n/a | [DOI](https://doi.org/10.1017/S0140525X01003922) | verified (abstract) |
| Human simple reaction time (Woods et al., Frontiers in Human Neuroscience 2015) | 1,469 adults | Mean simple visual reaction time 231 ms (213 ms after hardware correction); decision and click time come on top | human | n/a | [article](https://www.frontiersin.org/articles/10.3389/fnhum.2015.00131/full) | verified (page) |
| Alpaca market-data FAQ | Free plan data | Free plan real-time data is IEX only; AAPL example: 12,630 IEX trades against 535,000+ on all exchanges (about 2 to 3%); historical SIP queries on the free plan need an end time at least 15 minutes old | our stack | n/a | [Alpaca FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) | verified (page) |
| SEC Market Data Infrastructure release (86 FR 18596, Apr 2021) | Consolidated versus proprietary feeds | The SEC describes "a two-tiered market in which certain market participants that can afford and choose to pay for proprietary data feeds receive content-rich data faster". Footnote: Nasdaq SIP 99th-percentile quote latency fell to 28 microseconds after 2016; the other SIP got below 100 microseconds only in Q3 2020 | US equities | n/a | [Federal Register PDF](https://www.govinfo.gov/content/pkg/FR-2021-04-09/pdf/2020-28370.pdf) | verified (read text) |
| SEC 2024 tick-size and access-fee rule (Rel. 34-101070) | Exchange fee caps | Search snippet only: current cap 30 mils a share; compliance from early Nov 2025. New cap and any delay not confirmed (SEC site blocked automated access) | US equities | n/a | [SEC PDF](https://www.sec.gov/files/rules/final/2024/34-101070.pdf) (blocked) | UNVERIFIED |

**Conflicts of interest to keep in mind.** Kelly (JKX) works at AQR, a quant asset manager. MME-Finance authors work at a financial-data company. The DX Terminal paper is written by the people who run those agent platforms. Virtu's S-1 is a sales document. Vendor documentation sells tokens, and Alpaca's documentation sells data plans. Cornell's Medallion paper and the Guo-Liu challenge disagree by a factor of two. I did not find a trading-course seller among the authors of the sources used. The educators named in Notes v3 (Warrior Trading, ICT, Minervini, Sykes) and practitioner books on candlestick patterns are "claims to test", not evidence, and I did not rely on them.

### 2F. What the machines have that a cloud bot on free IEX data and REST calls does not

| Advantage | Market makers and high-frequency firms | Our bot | Evidence |
|---|---|---|---|
| Speed | Races settle in 5 to 10 microseconds; prices react to news in about 5 ms | LLM call in seconds (unmeasured here; the QuantHarness authors say it can outlast a one-minute opportunity); REST round trip unmeasured | Aquilina et al.; Chordia et al.; QuantHarness |
| Co-location and direct links | Lease space next to the exchange with custom network; fixed cost | Cloud container | Virtu S-1 and 10-K |
| Full proprietary depth-of-book feeds | Pay for faster, richer data (the SEC's "two-tiered market") | IEX only in real time (about 2 to 3% of volume) or 15-minute-old SIP | SEC MDI release; Alpaca FAQ |
| Rebates and fee tiers | Volume discounts and exchange rebates netted against fees | Retail pays the spread and fees, and crosses the spread | Virtu 10-K; Barber et al. 2009 in the repo (not re-read) |
| Being the passive side | Post quotes and earn the spread, with queue priority (though their liquidity-supplying orders are adversely selected, per Brogaard et al.) | Marketable limit orders; paper fills ignore queues | repo notes on Alpaca paper trading |
| Volume and breadth | 100,000+ trades a day at RenTec per bank; no asset class over 30% of income at Virtu (2013) | At most 4 round trips a day on 2 symbols | Senate PSI; Virtu S-1 |
| Scale economics | $8.6M of net trading income a day at Virtu (2025); my reading: a tiny edge times enormous volume | 1 share, about 7.7 cents per bp | Virtu 10-K; MINUTE_TRADING.md |
| Automated risk control | Credited by the company (its claim) for one losing day in 1,238 | Our guardrails (MT-G rules) can match discipline, not speed | Virtu S-1 |

The point: what the winners own is speed, position in the queue, data access and scale. Reading a candlestick faster does not create any of these.

---

## 3. What we can test with our data

**What we have.** Cached SIP 1-minute bars for SPY and QQQ from Aug 2024 to Sep 2026; free historical SIP daily and minute bars back to 2016 (the free plan only requires the end time to be at least 15 minutes old, verified in the Alpaca FAQ); live real-time IEX only; option quotes only "indicative". The 14 setups already used the Aug 2024 to Sep 2026 data, so that window is partly consumed as a final test (Notes v3 section 9).

**Statistical reality first (my arithmetic, assuming independent daily returns and normal shapes; real markets need more data than this).**

| Best "Sharpe" you should expect from N zero-skill strategies, purely by luck (formula of Bailey and Lopez de Prado) | 1 year | 2 years | 5 years | 10 years |
|---|---|---|---|---|
| N = 10 | 1.57 | 1.11 | 0.70 | 0.50 |
| N = 28 (our first backtest) | 2.04 | 1.45 | 0.91 | 0.65 |
| N = 1,000 | 3.26 | 2.30 | 1.46 | 1.03 |
| N = 28,000 (1000x more hypotheses than 28) | n/a | 2.90 | 1.84 | 1.30 |
| N = 1,000,000 | 4.87 | 3.44 | 2.18 | 1.54 |

| Years of data needed before a true annual Sharpe of S clears the bar (50% power) | S = 0.5 | S = 1.0 | S = 2.0 |
|---|---|---|---|
| one-sided 95% (z = 1.645) | 10.8 | 2.7 | 0.7 |
| two-sided 95% (z = 1.96) | 15.4 | 3.8 | 1.0 |
| the repo's pass bar, p < 0.0018 (z = 2.91) | 33.9 | 8.5 | 2.1 |
| Harvey-Liu-Zhu t > 3 | 36 | 9 | 2.2 |

Same idea for forecasts: the standard error of an IC estimate is about 1 / sqrt(N). With about 513 daily observations on two almost identical series (SPY and QQQ) that is about 0.04, so an IC of 0.03 (which could still matter) cannot be seen; seeing it at t = 3 needs about 10,000 independent daily observations (about 40 years).

**Tests, in the order I would run them.**

| # | Test | Data and cost | What it answers | Pass or fail rule (set before running) |
|---|---|---|---|---|
| A | **Planted-truth chart-reading audit.** Take 1,000 random 60-bar windows from 2016-2023 SPY/QQQ (not the 2024-26 window). Strip tickers and dates. Code computes the truth (net direction, slope quintile, above or below VWAP, did the last bar break the prior 20-bar high, exact high and low value and bar index, largest bar range). Ask the same model the same questions in three formats: (i) rendered candlestick picture, (ii) raw OHLCV table as text, (iii) code-computed JSON. Repeat 3 times and with 2 renderers | Free historical bars; about 10,000 model calls of roughly 1,500 input tokens each, so my estimate is $15 to $100 at the vendor's two example prices (a 1000x1000 picture is about 1,300 tokens) | Does a picture add anything over numbers or a summary? How often does the model state a number that is not in the data? Is it stable across runs and renderers? Fills the gap I could not find in the literature | Qualitative questions: at least 98% correct for any format allowed near a decision. Exact values: model may not supply any (code does). Any hallucinated number in more than 1% of answers = model gets no numeric role |
| B | **Does the code-made reading predict anything?** JSON features (multi-timeframe trend, distance to VWAP and prior-day levels in ATR units, range percentile, time of day, volume versus normal, gap, spread) against forward net R after realistic costs. Logistic regression and gradient boosting, walk-forward with purging | 2016-2023 for development; 2024-26 as a second check only | Is there any signal at all in SPY/QQQ for these features at 5-minute, 30-minute and daily horizons? | Log N variants; report IC, accuracy, net paired difference against B1 and buy-and-hold; must pass deflated Sharpe at the ledger's N |
| C | **Fresh backtest of the frozen human rules (B1) on 2016-2023.** Already promised in the backtest report ("not yet run") | Free bars | Did ORB5, LAST30 and the others ever work? Same rules, frozen | Same pre-set bars as the first backtest |
| D | **LLM veto scorecard on shadow signals.** Feed the JSON only (dates and tickers stripped). Let it output ALLOW or VETO with an enumerated reason. Still simulate every vetoed trade | Post-cutoff data only, or anonymised earlier data (memorisation risk) | Do vetoed trades do worse than taken trades? | At least 100 vetoes and 40 sessions (MT-G11); vetoed mean net R below taken mean with a 95% interval that excludes zero, else remove the LLM |
| E | **Picture-versus-table ablation for a learned model.** JKX-style CNN on OHLC images against the same window as rescaled numbers in a tabular model, same labels and costs | SPY/QQQ only gives about 5,000 daily images over 10 years against millions in the paper, so expect overfitting | Do pictures add information beyond scaling? | Image model must beat the tabular model on paired daily net difference; otherwise drop images |
| F | **Latency and cost log.** Time bar close to decision to order acknowledgement; tokens and dollars per LLM call | Paper account, dry runs | Real speed, real cost per decision | Report p50, p95, p99; compare with cost per decision below |
| G | **Overnight versus intraday split and buy-and-hold benchmark** from the cached bars | Free | A bot that is flat overnight gives up the overnight drift; buy-and-hold is the honest hurdle | Report next to every result |

**What we cannot test.** Microsecond or order-book edges (no depth data; live feed is IEX only). Anything option-based (indicative quotes only). Social-media or hype signals (banned by MT-G23 and MT-G24). "Better than humans" head to head (we have no human trading records on the same signals).

---

## 4. Recommendations for the agent design

### 4.1 What the "chart-reading agent" should be

Three layers, with the model kept out of the number-making:

1. **Reader (plain code).** A deterministic function turns bars into a structured, versioned, hashed reading: for each of 1m, 5m, 15m, 60m and daily, per symbol: trend state and strength, position against VWAP and key moving averages in ATR units, range percentile, opening-range status, distance to prior-day high and low, volatility percentile, volume against time-of-day norm, gap, spread, event calendar flags, feed tag (IEX or SIP), data age. This is the "multi-timeframe reading of many charts". It is exact by construction, costs nothing per call, and can be unit-tested against planted-truth charts.
2. **Deciders (compete under Notes v3).** B0 cash, B1 frozen human-inspired rules, B2 a simple statistical rule (e.g. moving-average or volatility timing), buy-and-hold, and M1 learned models fed the same Reader output and the same constraints. M2 (extra data) only later and with separate access. Everything frozen before evaluation; every variant counted.
3. **LLM (veto and explain only, MT-G29).** Input: the Reader's JSON plus the candidate trade. Output: strict schema, ALLOW or VETO plus an enumerated reason code and a short note for the owner. It may not emit prices, sizes or levels; code rejects any output containing a number that is not in the input. Every vetoed trade is still simulated, so we can score the veto. Run 3 samples and veto only on agreement to reduce noise (formatting alone has moved LLM accuracy by tens of points in other studies, per the repo's AI-13 entry, not re-read by me).

**Pictures.** Do not feed pictures into decisions. If a picture is ever shown, render it from the Reader's data with a fixed renderer (Wang 2026 found renderer and prompt fragility). Keep one controlled arm (Test E) to find out whether pictures add anything.

### 4.2 Include, avoid

**Include**
- The Reader, the planted-truth audit as a permanent regression test, and the experiment ledger with the trial count N and an automatic deflated-Sharpe and t > 3 check.
- Baselines B0, B1, B2 and buy-and-hold next to every learned result; report the paired daily net difference with a block bootstrap (Notes v3 section 10).
- Latency, token and dollar counters; operating-cost line next to trading P&L (Patch H).
- Date-blind, ticker-blind inputs for any LLM step, and evaluation on post-cutoff data (memorisation).
- A log outside the model. The DX study found agents kept "ghost" strategies and fabricated observations in memory; do not let the model be the record.

**Avoid**
- Letting any model produce a number, a stop, a size or a trade.
- Images or raw price lists as the main input to a decision.
- Minute-frequency machine learning with high turnover (costs flip the sign, section 2C).
- Treating a leaderboard, a competition or a "the AI made 40%" screenshot as evidence (Alpha Arena, LiveTradeBench are tournaments; Notes v3 already says this).
- Complexity for its own sake (Nagel's critique; Tan et al.).
- Comparing only against a weak baseline, and claiming a victory over "humans" from a victory over encoded rules (Notes v3 acceptance test 17).
- Trying to compete on speed, order-book signals or rebates (section 2F).

### 4.3 The efficiency scorecard ("10X" made measurable)

| Dimension | What a human typically does | What a bot can plausibly do | Evidence | Can it be 10X? | How we would measure it |
|---|---|---|---|---|---|
| Charts watched at once | Holds about 4 things in working memory (Cowan); a handful of charts on screen (UNVERIFIED norm) | Code re-reads every timeframe of every allowed symbol on every bar. A model reading pictures is the bottleneck: 6 pictures a cycle is about 7,800 input tokens | Cowan 2001; vendor docs | **Yes for code.** But our universe is fixed at SPY and QQQ (MT-G23), and breadth only helps if each independent bet has skill (textbook "fundamental law", not verified here) | Charts x timeframes evaluated per bar; share of bars with a complete valid reading |
| Reaction time (signal to order) | About 0.23 s to react plus seconds to decide and click | Code: milliseconds plus a REST round trip (unmeasured). With an LLM in the loop: seconds | Woods et al.; QuantHarness limits | **Yes against a human for the code path; no with an LLM in the loop.** Orders of magnitude too slow for the firms earning speed rents (5 ms news reaction, 5 to 10 microsecond races) | p50/p95/p99 from bar close to order acknowledgement; slippage against decision price |
| Consistency and rule-following | Sells winners early, chases losses, overtrades (repo MT-1 to MT-8, verified there) | Code follows its rules identically every time. LLM answers vary with wording: prompt and renderer effects up to about 1.1 log-odds in one open model versus about 0.10 for the most stable commercial model; choice stability "differs sharply across model families" | Wang 2026; DX paper; repo AI-13 | **Yes for code (zero rule violations by design). Not for LLM judgement** unless limited to enumerated vetoes with repeat sampling | Rule-violation count per 100 decisions; LLM agreement across repeats and paraphrases; exact replay from logs |
| Hypotheses tested per week | A few (assumption) | Hundreds or thousands, limited by compute | Deflated Sharpe: table above | **Yes, even 1000x, but it is not edge.** 28 tries on 2 years already show a luck-only best of 1.45; 28,000 tries show 2.90 | Count of registered hypotheses N; deflated Sharpe at that N; "hypotheses that survive a pre-registered forward test per quarter" |
| Cost per decision | Time, attention; no cash at 1 share | Code about zero. LLM: a 6-picture decision is about 7,800 tokens, about $0.008 at $1 per million tokens and $0.039 at $5 per million (the two example prices on the vendor page), against about $0.077 for a 1 bp edge on one SPY share. Text JSON instead of pictures is far cheaper (my estimate, UNVERIFIED) | Vendor docs; MINUTE_TRADING.md (SPY about $766) | **Yes, if the LLM is used only on the few candidate signals a day, not on every bar** | All-in dollars (data, LLM, hosting) per decision and per trade, next to net edge per trade |
| Record keeping | Partial journals (assumption) | Every input, code hash, output, rejection reason and latency logged; fully replayable | MT-G3 and MT-G4; the audit of 77 studies found almost none reproducible | **Yes, a genuine and cheap advantage** | Share of decisions with a complete replayable record; replay gives identical decisions |
| Accuracy of reading a chart | Humans 80.5% on hard chart reasoning (CharXiv) | Code: exact for computed facts. Models: about 47 to 60% on hard chart reasoning (2024 models), about 60 to 64% on open financial-chart questions, about 41% on estimating values | CharXiv; FinChart-Bench; MME-Finance | **Numbers: yes, by using code. Pattern judgement: no evidence models beat people, and 2026 tests say they mostly follow the trend** | Planted-truth audit (Test A) |
| Risk-adjusted net return after all costs | Most lose: 97% of persistent Brazilian day traders; under 1% of Taiwanese predictably profitable | Our own backtest: every minute setup lost $0.03 to $0.45 per $1,000 trade at realistic costs; literature edges sit in illiquid stocks at daily horizons and decay 26% out of sample and 58% after publication | Chague; Barber; McLean-Pontiff; repo backtest | **Undefined.** "10X" of a negative or zero number means nothing. Use a paired test instead | Paired daily net difference of M1 minus B1 (and versus buy-and-hold) with block-bootstrap interval, deflated Sharpe, drawdown, and operating costs |

**The trap, stated once.** Being 1000 times faster at testing ideas does not make any idea better. It raises the bar each idea must clear (Harvey-Liu-Zhu, Bailey-Lopez de Prado). Speed of research is worth having only if the trial count is logged and the bar rises with it.

### 4.4 What to test first

1. Test A (planted-truth chart-reading audit). Cheap, decisive for "can the AI read charts", and it also sets the rules for what the model is allowed to touch.
2. The power and deflated-Sharpe calculator (section 3), so nobody promises an edge the data cannot show.
3. Test C then B on 2016-2023 (frozen rules first, then code-read features).
4. Test D (veto scorecard) only after A has passed.
5. Test E (pictures versus table) last, as pure science.

### 4.5 What would be a fair test of "better than humans"

- Say exactly what is being compared. Notes v3 already requires "improved this baseline in these prospective observations", not "superhuman trader".
- **Level 1, process:** count the human failure modes the bot cannot commit (overtrading, widening stops, revenge sizing) and the ones an LLM adds (invented numbers, inconsistent answers). This is measurable now.
- **Level 2, paired against frozen rules:** M1 minus B1 daily net return on a fixed capital allocation, zero-trade days kept, block bootstrap, deflated Sharpe at the ledger's N, forward paper data as the final test, with at least the MT-G11 minimum of 100 trades and 40 sessions before any good news.
- **Level 3, against real people:** a small panel (the owner, volunteers, possibly a skilled discretionary trader) trades the same signals on paper with the same cost model at the same times; compare paired daily net results. Small sample, so it can show a large gap or nothing.
- Always add buy-and-hold and cash as hurdles. Day traders as a group lose to them; a bot that is flat every night also gives up the overnight return.

### 4.6 What is realistic to expect

- Reader and logging: works, 10X on coverage, consistency and records.
- LLM as chart reader from pictures: not reliable enough to touch numbers; possibly useful as a veto, which is unproven and must be scored.
- Learned model on SPY/QQQ features: my expectation is no reliable net edge at minute horizons (14 setups at about zero gross; every study above), and at daily horizons an effect too small to see in two years. This is inference, not a measured result.
- Best honest payoff: fewer bad trades, cleaner evidence, faster and more honest research, and a system that can say "no trade".

### 4.7 What would make us stop

Set these before running anything, and record the date they were set.

1. Test A fails (model states numbers not in the data, or fails qualitative questions): no model gets a numeric or price role; LLM stays as an optional explainer.
2. Veto scorecard: after at least 100 vetoes and 40 sessions, vetoed trades are not clearly worse (95% interval touches zero): remove the LLM veto.
3. M1 versus B1: after the pre-set sample, the lower 95% bound of the paired daily net difference is at or below zero, or the deflated Sharpe at the logged N is below 0.95: stop the learned-model track.
4. Costs: all-in operating cost (data, LLM, hosting) exceeds the measured improvement.
5. Leakage or contamination: a planted fake passes, or performance collapses (say by half) from pre-cutoff to post-cutoff data: stop and audit.
6. Paper-versus-backtest replay drifts beyond the MT-G13 tolerance.
7. Time box: two quarters, or earlier if the trial count makes the required Sharpe larger than the data can ever resolve.

### 4.8 What a beginner should be told

- Reading a chart and knowing what happens next are different skills. AI is only sometimes good at the first and has not been shown to be good at the second.
- A chart picture is just numbers drawn as shapes. The computer already has the numbers, so we let code do the reading and use the AI only as a second pair of eyes that can say "wait".
- Most human day traders lose money, so "10 times better than a human" needs a definition. We will count things we can measure and test profit separately.
- Every extra idea we test makes a lucky result more likely, so each idea has to clear a higher bar. Testing fast is not the same as finding an edge.
- The firms that win at this do it with speed, position and scale that a free feed and a cloud bot do not have. We should not play their game.
- "No edge found" is a real and useful answer. A system that keeps honest records and refuses bad trades is already better than the average trader.
- Never trust a screenshot, a leaderboard or a story that "an AI made 40%". Ask for the period, the costs, the number of tries and whether it was forward or backtested.

---

## 5. Open questions and things I could not verify

1. **Newest chart-reading scores.** The CharXiv README I could open lists only 2024 models. I could not confirm 2026 frontier scores on CharXiv or ChartQAPro. The finance-specific 2025-26 papers above are more relevant, but they use their own model lists.
2. **Picture versus numbers on real markets.** I found no controlled test (same model, same information, image versus table versus summary, with costs). My search tool hit its 200-call session limit part-way through, so I may have missed one. Test A is designed to fill this gap.
3. **Alpha Arena.** nof1.ai returned HTTP 403; all per-model results remain UNVERIFIED. Seasons after the first were not checked.
4. **Jiang-Kelly-Xiu.** I read the working paper, not the published text (SSRN blocked); some published numbers differ. Independent replications in Korea and China were seen as titles only. Whether the CNN edge survives 2020-2026 in the US is not established.
5. **Systematic-fund Sharpe ratios.** No primary net-of-fee series obtained (AQR page returned only boilerplate; the trend-following papers were not accessible). Medallion's Sharpe and Cornell's return figures are UNVERIFIED; Guo and Liu dispute the compounding.
6. **SEC 2024 access-fee rule.** The final rule PDF and the Federal Register page were blocked. The new fee cap and whether compliance was delayed are not verified.
7. **Our own latency and REST timings.** I cannot call any API. The QuantHarness authors' statement that an LLM cycle can outlast a one-minute window is theirs, not ours. Test F measures ours.
8. **StockBench numbers and the repo's own AI-13, AI-16 figures** are taken from the repo's reports and not re-read by me.
9. **Other finance chart benchmarks** surfaced in search (VisFinEval, CFMME) were not opened.
10. **Human decision time and journal quality** (rows in the scorecard) are assumptions, not measured.
11. **Model knowledge cutoffs versus our data.** Whether a chosen model has seen 2024-2026 SPY/QQQ history is unknown; design for it (anonymise, use post-cutoff data).
12. **Recency and independence.** The two candlestick papers (April and June 2026) and the DX study (Sept 2026) are new, single-team preprints and have not been replicated. The Martingale test uses synthetic charts.
13. **Example prices** on the vendor page may change; the per-decision cost lines are my arithmetic on those examples.
14. **Overnight versus intraday drift** in our own cache was not computed (Test G).
15. **Other market makers.** I examined only Virtu's SEC filings. Citadel Securities and Jane Street are private, and I did not check Flow Traders or other listed firms.
16. **Moirai and the fundamental law of active management** (information ratio = IC x square root of breadth) were not opened or verified; the breadth remark in section 4.3 is textbook, not checked here.

---

## 6. Sources

Access notes: "read" = I downloaded the full text or page and searched it; "abstract" = abstract or landing page only; "snippet" = search-result text only; "blocked" = the page refused automated access. My search tool stopped working at 200 calls per session, so later checks used direct fetches.

**Chart reading**
1. ChartQA, Masry et al. 2022. https://arxiv.org/abs/2203.10244 (abstract)
2. CharXiv, Wang et al. 2024. https://arxiv.org/abs/2406.18521 (abstract); https://github.com/princeton-nlp/CharXiv (README summary)
3. ChartQAPro, Masry et al. 2025. https://arxiv.org/abs/2504.05506 (abstract)
4. Vision language models are blind, Rahmanzadehgervi et al. https://arxiv.org/abs/2407.06581 (abstract)
5. FinChart-Bench, Shu et al. https://arxiv.org/abs/2507.14823 (read)
6. MME-Finance, HiThink Research et al. https://arxiv.org/abs/2411.03314 (read)
7. Do VLMs Truly Read Candlesticks?, Hu et al. https://arxiv.org/abs/2604.12659 (read)
8. Martingale Doppelganger-Eval, Z. Wang. https://arxiv.org/abs/2606.17423 (read)
9. Confidence estimation for financial VLMs, Khanmohammadi et al. https://arxiv.org/abs/2608.06532 (abstract)
10. AgentFinVQA, Narayanan and Raza. https://arxiv.org/abs/2606.19782 (abstract)
11. Chart data extraction, He et al. https://arxiv.org/abs/2606.29808 (abstract)
12. Vendor vision documentation. https://platform.claude.com/docs/en/build-with-claude/vision (read)
13. Plots unlock time-series understanding, Daswani et al. https://arxiv.org/abs/2410.02637 (abstract)
14. Are language models actually useful for time series forecasting?, Tan et al. https://arxiv.org/abs/2406.16964 (abstract)

**Trading agents**
15. FinAgent, Zhang et al. https://arxiv.org/abs/2402.18485 (abstract)
16. QuantAgent / QuantHarness, Xiong et al. https://arxiv.org/abs/2509.09995 (read)
17. Agent Trading Arena, Ma et al. https://arxiv.org/abs/2502.17967 (read)
18. StockBench, Chen et al. https://arxiv.org/abs/2510.02209 (abstract)
19. FINSABER, Li et al. https://arxiv.org/abs/2505.07078 (abstract and read)
20. LiveTradeBench, Yu et al. https://arxiv.org/abs/2511.03628 (abstract)
21. Agentic Trading audit, Xia et al. https://arxiv.org/abs/2605.19337 (abstract)
22. DX Terminal Pro / DXAP, Barton et al. https://arxiv.org/abs/2609.05663 (read)
23. Alpha Arena, nof1. https://nof1.ai (blocked, HTTP 403)
24. TradeTrap, Yan et al. https://arxiv.org/abs/2512.02261 (abstract)
25. SoK trading agents, Wang and Saxena. https://arxiv.org/abs/2609.19705 (abstract)
26. The Memorization Problem, Lopez-Lira, Tang and Zhu. https://arxiv.org/abs/2504.14765 (abstract)
27. BlindTrade, Jeon and Lee. https://arxiv.org/abs/2603.17692 (abstract)
28. TiMi, Song et al. https://arxiv.org/abs/2510.04787 (abstract)

**Learning from data**
29. (Re-)Imag(in)ing Price Trends, Jiang, Kelly and Xiu. Working paper https://www.aidf.nus.edu.sg/wp-content/uploads/2022/02/Xiu-Re-Imagining-Price-Trends.pdf (read); journal abstract https://ideas.repec.org/a/bla/jfinan/v78y2023i6p3193-3249.html
30. DeepLOB, Zhang, Zohren and Roberts. https://arxiv.org/abs/1808.03668 (abstract)
31. LOBCAST, Prata et al. https://arxiv.org/abs/2308.01915 (abstract)
32. Deep Limit Order Book Forecasting, Briola, Bartolucci and Aste. https://arxiv.org/abs/2403.09267 (read); Quantitative Finance 25(7):1101-1131, DOI 10.1080/14697688.2025.2522911 (search record)
33. Re(Visiting) Time Series Foundation Models in Finance, Rahimikia, Ni and Wang. http://wp.lancs.ac.uk/fofi2026/files/2026/03/FoFI-2026-020-Eghbal-Rahimikia.pdf (read)
34. Pretrained Time-Series Foundation Models for Financial Return Forecasting, Alonso and Franklin. https://arxiv.org/abs/2606.27100 (abstract)
35. TimesFM, Das et al. https://arxiv.org/abs/2310.10688 (abstract); Chronos, Ansari et al. https://arxiv.org/abs/2403.07815 (abstract)
36. The Virtue of Complexity in Return Prediction, Kelly, Malamud and Zhou. https://ideas.repec.org/a/bla/jfinan/v79y2024i1p459-503.html (abstract)
37. Seemingly Virtuous Complexity in Return Prediction, Nagel. https://www.nber.org/papers/w34104 (abstract)
38. Empirical Asset Pricing via Machine Learning, Gu, Kelly and Xiu. https://dachxiu.chicagobooth.edu/download/ML.pdf (read); https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2223-2273..html
39. Machine Learning vs. Economic Restrictions, Avramov, Cheng and Metzker. https://econpapers.repec.org/RePEc:inm:ormnsc:v:69:y:2023:i:5:p:2587-2619 (abstract)
40. Lo, Mamaysky and Wang 2000, https://doi.org/10.1111/0022-1082.00265; Menkhoff and Taylor 2007, https://doi.org/10.1257/jel.45.4.936; Bajgrowicz and Scaillet 2012, https://ideas.repec.org/a/eee/jfinec/v106y2012i3p473-491.html (abstracts)

**Humans and machines**
41. Barber, Lee, Liu and Odean 2014. https://ideas.repec.org/a/eee/finmar/v18y2014icp1-24.html (abstract)
42. Chague, De-Losso and Giovannetti 2020. https://ebicapital.nl/wp-content/uploads/2022/05/day-trading.pdf (read); SSRN 3423101
43. Jordan and Diltz 2003. https://rpc.cfainstitute.org/research/financial-analysts-journal/2003/the-profitability-of-day-traders (summary)
44. Baron, Brogaard, Hagstromer and Kirilenko 2019. https://econpapers.repec.org/RePEc:cup:jfinqa:v:54:y:2019:i:03:p:993-1024_00 (abstract)
45. Brogaard, Hendershott and Riordan 2014. https://ideas.repec.org/a/oup/rfinst/v27y2014i8p2267-2306..html (abstract)
46. Budish, Cramton and Shim 2015. https://doi.org/10.1093/qje/qjv027 (abstract via Crossref)
47. Aquilina, Budish and O'Neill 2022. https://www.nber.org/papers/w29011 (abstract)
48. Chordia, Green and Kottimukkalur. https://doi.org/10.2139/ssrn.3062161 (abstract via Crossref)
49. Virtu Financial S-1, 10 Mar 2014. https://www.sec.gov/Archives/edgar/data/0001592386/000104746914002070/a2218589zs-1.htm (read)
50. Virtu Financial 10-K FY2025. https://www.sec.gov/Archives/edgar/data/1592386/000159238626000009/virt-20251231.htm (read)
51. US Senate PSI, Abuse of Structured Financial Products (basket options), 2014. https://www.hsgac.senate.gov/wp-content/uploads/imo/media/doc/REPORT-Abuse%20of%20Structured%20Financial%20Products%20(Basket%20Options)%20(7-22-14,%20updated%209-30-14).pdf (read)
52. Cornell, Medallion Fund: The Ultimate Counterexample?, JPM 46(4). https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3504766 (blocked; snippet only)
53. Guo and Liu, Is the annualized compounded return of Medallion over 35%? https://arxiv.org/abs/2405.10917 (read)
54. Khandani and Lo, NBER WP 14465. https://www.nber.org/system/files/working_papers/w14465/w14465.pdf (read)
55. McLean and Pontiff 2016. https://doi.org/10.1111/jofi.12365 (abstract via Crossref)
56. Hou, Xue and Zhang 2020. https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2019-2133..html (abstract)

**Testing traps and limits**
57. Harvey, Liu and Zhu 2016. https://ideas.repec.org/a/oup/rfinst/v29y2016i1p5-68..html (abstract)
58. Bailey and Lopez de Prado 2014. https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf (read)
59. Cowan 2001. https://doi.org/10.1017/S0140525X01003922 (abstract)
60. Woods et al. 2015. https://www.frontiersin.org/articles/10.3389/fnhum.2015.00131/full (page)
61. Alpaca market-data FAQ. https://docs.alpaca.markets/us/docs/market-data-faq (page); Alpaca real-time data page https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data (feed names only)
62. SEC Market Data Infrastructure release. https://www.govinfo.gov/content/pkg/FR-2021-04-09/pdf/2020-28370.pdf (read)
63. SEC Regulation NMS tick-size and access-fee final rule. https://www.sec.gov/files/rules/final/2024/34-101070.pdf (blocked; snippet only)

**Repo files read (read-only)**: `MINUTE_TRADING.md`; `reports/Why day traders lose.md` sections 1-3; `reports/Minute trading backtest results.md` sections 1-3 and 8; `reports/Owner notes 1 - intraday addendum v2 and v3 (2026-09-28).md` (verdict table and v3 sections 1-11); headings and first lines of `reports/Where AI can beat human traders.md`.
