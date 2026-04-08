> **NOTE (2026-04-08):** GH Pages dashboards retired. Canonical view is local Streamlit (`streamlit run tools/diag.py`). Dashboard mentions below are historical.

# Kalshi Integration — Parallel Venue & Cross-Market Arbitrage

> **Status**: ACTIVE — Phase 0 infrastructure complete, mock mode analysis done (see `docs/analysis/kalshi_pipeline_review.md`). Needs real API credentials to proceed.
> **Date**: March 31, 2026 (plan) / April 2, 2026 (Phase 0 built) / April 6, 2026 (Phase 0 analysis)
> **Goal**: Add Kalshi as a parallel BTC trading venue and cross-market arbitrage counterparty against Polymarket.

---

## 1. Platform Comparison

Kalshi is a CFTC-regulated Designated Contract Market with centralized matching, USD settlement, and CF Benchmarks pricing. Polymarket is unregulated, blockchain-based, and settles via UMA/Chainlink oracles on Polygon. The structural gap between the two venues — different user bases, different settlement sources, different latency profiles — is what creates opportunity.

| Dimension | Kalshi | Polymarket |
|---|---|---|
| Regulation | CFTC-regulated DCM | Unregulated (Polygon/crypto) |
| Settlement | CF Benchmarks RTI (trimmed 60s avg) | UMA/Chainlink oracles |
| Currency | USD (bank/PayPal/crypto) | USDC on Polygon |
| Fee formula | `0.07 × contracts × price × (1−price)` | Variable curve, peaks ~1.56% at 50¢ (crypto) |
| Fee peak | 1.75% at 50¢ | ~1.80% at 50¢ |
| Maker incentive | Lower maker fees | 20% of taker fees as rebate |
| BTC markets | 15-min, hourly, daily | 5-min, 15-min |
| Latency | Centralized matching (sub-second) | Polygon ~2s blocks + CLOB |
| API | REST + WebSocket (JWT auth) | REST + WebSocket (API key) |

Both fee curves are parabolic, peaking at 50¢ and falling to near-zero at the extremes. The fee-avoidance strategy is the same on both platforms: trade where the price is far from 50¢. Cross-market positions combining a buy near 30¢ on one platform with a buy near 70¢ on the other achieve double fee minimization — both legs sit in low-fee zones.

Kalshi's BTC contracts settle to CF Benchmarks Real-Time Indices using a trimmed 1-minute average (excluding the top/bottom 20% of per-second observations). This is fundamentally different from Polymarket's oracle-based snapshots. The same BTC price movement can resolve differently on each platform, which creates both settlement divergence risk and arbitrage windows when CEX spot, CFB RTI, and Polymarket oracle temporarily disagree.

---

## 2. Three Strategies

Ordered from cheapest-to-test to most-complex.

### Strategy 1: Parallel Venue — Momentum on Kalshi

Run the production momentum signal against Kalshi BTC markets. Same regime filter, same conviction gates, same flat sizing — different venue.

This is the lowest-risk experiment. The signal is validated at 63% WR on 227 bets. If it transfers to Kalshi, we have a second revenue stream with minimal new code. If it doesn't, we learn whether the edge is Polymarket-specific, which determines whether cross-market strategies are even worth pursuing.

New code required: `src/kalshi_data.py` (candle fetch), `src/kalshi_trade.py` (order placement). The signal and regime logic are data-source agnostic and reuse as-is.

### Strategy 2: Fair Value Mispricing

When one platform deviates from CEX-derived fair value while the other is correctly priced, bet the stale side back toward fair value.

This requires paired data from both platforms but executes on a single leg at a time. Compute fair probability from Deribit IV + Binance momentum, then measure which platform is slower to reprice after a BTC spot move. Bet the lagging side.

Edge profile: 1–3% after fees, conditional on correctly identifying the stale platform. Win rate target: 55–60%.

### Strategy 3: Cross-Market Structural Arbitrage

When `kalshi_yes + polymarket_no < $1.00` after fees on the same underlying BTC event, buy both sides and lock in risk-free profit.

This is the most infrastructure-heavy strategy. It requires persistent dual-platform orderbook monitoring, simultaneous two-leg execution, leg risk management, and settlement divergence tracking. It depends on a dedicated server (VPS or Mac Mini) — it cannot run on GitHub Actions.

Edge profile: 3–5% gross pricing gaps, 1–3% net after fees. Windows last seconds to minutes.

Critical risk: settlement definition divergence. BTC price markets have lower semantic risk than event markets (price is price), but the trimmed-average vs oracle-snapshot methodologies can produce divergent resolutions during flash crashes.

---

## 3. Mathematical Framework

### 3.1 Cross-Market Arbitrage Model

For BTC contracts on both platforms with the same strike K and expiry T:

```
kalshi_yes_price = K_y
poly_no_price = P_n

arb_profit = 1.00 - K_y - P_n - fee_kalshi(K_y) - fee_poly(P_n) - slippage_buffer

fee_kalshi(p) = 0.07 × p × (1 − p)
fee_poly(p) = poly_fee_curve(p)         // variable, max ~1.80% at p=0.50

net_edge = arb_profit − execution_risk_buffer(0.5%)
```

The execution risk buffer accounts for leg risk (one side fills, the other doesn't), settlement divergence probability, and latency differential between platforms.

### 3.2 VPIN — Order Flow Toxicity

VPIN (Volume-Synchronized Probability of Informed Trading) measures adverse selection risk, adapted for prediction markets:

```
VPIN = Σ|V_buy − V_sell| / (n × V_bucket)
```

Trades are bucketed by volume, not time, to normalize for bursty prediction market flow. High VPIN means informed traders are active — avoid being a taker. Low VPIN means the market is balanced — safer to cross the spread.

Before placing any taker order, compute real-time VPIN on the target orderbook. If VPIN exceeds threshold (calibrated from Phase 1 data), skip the cycle.

### 3.3 Kyle's Lambda — Price Impact

Kyle's (1985) model: `ΔP = λ × OrderFlow`, where λ captures market depth and resilience.

For thin prediction market books ($1k–$15k depth per side), even small orders ($50–$200) can move the price. Estimate λ per platform per market:

```
λ_kalshi = regress(ΔP_kalshi, NetFlow_kalshi) over trailing 100 trades
λ_poly = regress(ΔP_poly, NetFlow_poly) over trailing 100 trades
```

Size each leg so expected price impact stays below 25% of gross edge. If λ is high (thin book), reduce size or skip. Compare λ between platforms and trade on the one with lower impact.

### 3.4 Multi-Leg Kelly with Correlated Outcomes

Cross-market arb legs are maximally correlated (they resolve on the same underlying BTC price). The generalized multi-bet Kelly:

```
f* = Σ⁻¹ × μ
```

Where `Σ` is the covariance matrix of bet outcomes and `μ` is the expected edge vector. For perfectly correlated legs, this simplifies to treating the combined position as a single bet with edge = net_arb_profit and variance derived from settlement divergence probability.

```
kelly_fraction = net_edge / variance_of_edge_estimate
position_size = min(0.25 × kelly_fraction × bankroll, $50, daily_budget_remaining)
```

Start at quarter-Kelly because edge estimates are noisy. Scale to half-Kelly only after 200+ profitable arb cycles with stable edge distribution.

### 3.5 Bayesian Edge Decay Detection

Rather than a fixed rolling-window win rate floor, use a Bayesian model to detect decay in real time:

```
Prior: edge ~ Beta(α₀, β₀)       // initialized from backtest
Update: after each trade, α += win, β += loss
Posterior mean: α / (α + β)
Posterior variance: αβ / ((α+β)²(α+β+1))

Pause if: P(edge < fee_drag | data) > 0.90
```

The Beta distribution's uncertainty shrinks naturally as data accumulates, handling small sample sizes gracefully.

---

## 4. MEV & DeFi Principles

### 4.1 Latency Arbitrage as MEV Extraction

Cross-platform arb is structurally analogous to DEX-CEX arbitrage. The "MEV" is the pricing inefficiency between a centralized venue (Kalshi) and a blockchain-based venue (Polymarket).

The bot that detects the mispricing first and executes both legs wins. Kalshi's centralized matching engine is fast; Polymarket's Polygon settlement (~2s blocks) is the bottleneck. Execute the slow leg first (Polymarket), then immediately execute the Kalshi leg. If the Polymarket leg doesn't fill, no Kalshi order is placed.

### 4.2 Sandwich Attack Awareness

On Polymarket (Polygon-based), limit orders are visible in the CLOB. Sophisticated actors can front-run by buying ahead of a resting order, moving the price, letting it fill at a worse price, then selling.

Mitigation: post-only orders with tight price limits. Cancel and re-place every 5–10s to reduce visibility window. On Kalshi (centralized), this risk is lower but not zero — other API users can see the book.

### 4.3 On-Chain Signal Integration

Polymarket lives on Polygon. On-chain data provides signals invisible to Kalshi-only traders:

- **Whale movements**: Large deposits to Polymarket's CLOB contract signal incoming large orders and imminent price impact. Detectable via Polygon event monitoring.
- **Gas price spikes**: High Polygon gas means other bots are competing and edges are being extracted. Skip or reduce size.
- **USDC flow**: Large USDC transfers to Polymarket's settlement contract may signal institutional positioning.

---

## 5. Architecture

### 5.1 Principle

The BTC 5m production pipeline is untouched. The following files have zero lines changed:

> `src/ci_run.py`, `src/btc_data.py`, `src/predict.py`, `src/score.py`, `src/clob_depth.py`, `.github/workflows/predict-and-score.yml`, `data/predictions.db`

Kalshi integration adds new files alongside the existing ones.

### 5.2 Module Map

| Existing Module | Kalshi Extension | Notes |
|---|---|---|
| `src/btc_data.py` — Kraken/Coinbase candles | **`src/kalshi_data.py`** (NEW) | Same interface: returns OHLCV dict. Pulls from Kalshi REST API + CF Benchmarks for settlement-grade pricing. |
| `src/predict.py` — Momentum signal + regime | **Reused as-is** | `compute_regime_from_candles()` and `momentum_signal()` are data-source agnostic. |
| `src/trade.py` — Polymarket order placement | **`src/kalshi_trade.py`** (NEW) | Same pattern: prediction + conviction → limit order. Kalshi REST API with JWT auth. Same circuit breakers, same kill switch. |
| `src/clob_depth.py` — Polymarket depth | **`src/kalshi_depth.py`** (NEW) | Same interface: `get_order_book()`, `analyze_depth()`, `compute_max_bet()`. |
| `src/score.py` — Resolve predictions | **`src/kalshi_score.py`** (NEW) | Query Kalshi settlement API. Same scoring logic. |
| `src/daily_report.py` — Analytics | **Extended** | Add Kalshi pipeline stats alongside existing pipelines. |
| `src/dashboard.py` — HTML generation | **Extended** | Add `docs/kalshi.html` to nav bar. |
| `src/optimization_tracker.py` — Decision registry | **Reused as-is** | Register Kalshi optimizations in `docs/optimizations.json`. |

### 5.3 New Modules (Phase 1+)

| Module | Purpose | Phase |
|---|---|---|
| `src/kalshi_ws.py` | WebSocket feed for real-time Kalshi orderbook | Phase 1 |
| `src/normalizer.py` | Map Kalshi ↔ Polymarket markets by strike/expiry | Phase 1 |
| `src/settlement_monitor.py` | CFB RTI vs oracle divergence tracker | Phase 1 |
| `src/vpin.py` | Real-time VPIN per platform | Phase 2 |
| `src/kyle_lambda.py` | Price impact estimation | Phase 2 |
| `src/arb_detector.py` | Cross-platform mispricing scanner | Phase 2 |
| `src/arb_executor.py` | Two-leg execution (slow leg first) | Phase 3 |
| `src/toxicity_gate.py` | Composite signal: skip trade if flow is toxic | Phase 2 |
| `src/deribit_data.py` | IV surface + index for fair value computation | Phase 1 |

### 5.4 Database

Each pipeline gets its own database, following the established pattern:

| Pipeline | DB | Dashboard | Workflow |
|---|---|---|---|
| BTC 5m (production) | `predictions.db` | `docs/index.html` | `predict-and-score.yml` |
| BTC 15m (paper) | `predictions_15m.db` | `docs/15m.html` | `predict-15m.yml` |
| ETH 5m (paper) | `predictions_eth.db` | `docs/eth.html` | `predict-eth-5m.yml` |
| **Kalshi BTC** | `predictions_kalshi.db` | `docs/kalshi.html` | `predict-kalshi.yml` |

Separate DB per pipeline means zero risk of contaminating production data.

### 5.5 Deployment

**Phase 0 (Kalshi momentum):** GitHub Actions. Kalshi hourly markets don't need sub-second execution. A 5-minute CI cycle provides minutes of edge window on hourly contracts.

**Phase 1+ (paired data, arb detection):** Persistent process on a VPS or Mac Mini.

| Option | Pros | Cons |
|---|---|---|
| **VPS** (Hetzner, DigitalOcean) | Always on, low latency, $5–20/mo | SSH security, hosting dependency |
| **Mac Mini** | Local control, no hosting cost | Hardware purchase, home network dependency |

Pick whichever is ready first. The codebase is identical — the persistent process is `python3 src/kalshi_ws.py` + `python3 src/arb_detector.py` running as systemd or launchd services.

**Hybrid model:** CI pipelines continue handling scoring, dashboards, and daily reports. The VPS/Mini runs only the real-time feed and arb execution. Results are git-pushed back to the repo so the dashboard remains the canonical view.

---

## 6. Implementation Phases

### Pre-Flight Blockers (Resolve Before Day 1)

- [ ] Kalshi account opened and API credentials obtained.
- [ ] State eligibility confirmed (Washington lawsuit, March 2026).
- [ ] Polymarket US access legality assessed. If unresolvable, the plan collapses to Kalshi-only from Phase 0 onward.
- [ ] Legal consultation on cross-platform arbitrage before Phase 3.

### Phase 0: Signal Transfer Test (Days 1–14)

The cheapest possible experiment. No new math, no WebSockets, no arb logic. Run the proven momentum signal against Kalshi markets and see if it transfers.

**Build:** _(completed 2026-04-02)_

1. [x] `src/kalshi_data.py` — Thin wrapper over `btc_data.fetch_btc_candles(interval="15m")`. BTC is BTC regardless of venue.
2. [x] `src/kalshi_markets.py` — Fetch active Kalshi BTC markets via REST API. HMAC-SHA256 auth. Mock mode fallback.
3. [x] `src/ci_run_kalshi.py` — CI entry point. Fetches candles → runs `predict.py` (unchanged) → logs prediction to `predictions_kalshi.db`. No orders.
4. [x] `.github/workflows/predict-kalshi.yml` — Runs every 15 minutes. Self-rescheduling via `next-cycle-kalshi` dispatch.
5. [x] `src/kalshi_score.py` — Query Kalshi settlement API, resolve predictions. Mock mode: deterministic hash resolution.
6. [x] `docs/kalshi.html` — Dashboard. Same template as existing pipelines, cross-linked via nav bar.
7. [x] `tests/test_kalshi.py` — 12 tests covering all Kalshi modules. All passing.
8. [x] `src/daily_report.py` — Extended to include Kalshi as 4th pipeline in daily reports.

**What we learn:**

- Does the momentum signal transfer to Kalshi's hourly/15-min timeframes?
- What is Kalshi's book depth? Is $25 executable at ≤ 2% slippage?
- How does Kalshi pricing compare to Polymarket mid at the same BTC price?

**Gates:**

- API integration working, predictions logging with > 95% uptime.
- 200+ resolved predictions accumulated.
- Momentum WR > 55% on Kalshi → proceed to Phase 0.5.
- Momentum WR < 50% on Kalshi → signal is venue-specific. Skip to Phase 1.

### Phase 0.5: Kalshi Paper Trading (Days 15–28, conditional)

Only enters this phase if Phase 0 shows > 55% WR on Kalshi.

- `src/kalshi_trade.py` — Prediction + conviction → Kalshi limit order (logged, not placed). `KALSHI_TRADING_ENABLED=false`.
- `src/kalshi_depth.py` — Orderbook depth analysis.
- Flat $25 bets, conviction ≥ 3 gate, $300 daily loss limit.
- Accumulate 50+ paper bets with fill simulation.

**Gate:** Paper P&L positive over 50+ simulated bets. Proceed to micro-live ($5) or proceed to Phase 1 regardless.

### Phase 1: Paired Data Collection (Days 15–28, parallel)

Runs in parallel with Phase 0.5. Even if momentum transfers to Kalshi, paired data is needed to evaluate cross-market strategies.

**Requires VPS/Mini.** Collect every 10 seconds:

- Kalshi orderbook: bid, ask, mid, depth per side — all active BTC hourly markets
- Polymarket orderbook: bid, ask, mid, depth per side — all active BTC 5-min/15-min/hourly markets
- Binance/Kraken: BTC spot
- Deribit: IV surface, index

**Store as paired observations** in `data/paired_observations.db`:

```
timestamp | kalshi_market_id | kalshi_mid | kalshi_depth_bid | kalshi_depth_ask |
poly_market_id | poly_mid | poly_depth_bid | poly_depth_ask |
binance_spot | deribit_iv_atm | outcome
```

`src/normalizer.py` maps Kalshi BTC hourly to equivalent Polymarket BTC hourly by strike and expiry. Every case where markets don't align is documented.

Deploy the data collector to VPS/Mini. Git-push the paired DB snapshot daily.

**Gates:**

- 14 days of paired data, > 95% feed uptime.
- Kalshi BTC hourly median depth ≥ $1k per side. If < $500, cross-market arb is dead — stay on single-venue strategies.
- Partial fill protocol documented: if Polymarket partially fills an arb leg, scale Kalshi to match or cancel.

### Phase 2: Offline Analysis (Days 29–42)

Run against Phase 1 paired data.

**2A — Cross-market arb frequency.** Compute `gross_arb = 1.00 − kalshi_best_ask − poly_best_ask` per paired market. After fees: `net_arb = gross_arb − fee_kalshi(p) − fee_poly(p) − 0.5% slippage`. Gate: net_arb > 0 in ≥ 5% of observations, or cross-market arb is dead.

**2B — Fair value mispricing.** Compute fair probability from Deribit IV + Binance momentum (calibrated from Phase 1 data). Measure repricing lag per platform. Gate: ≥ 3% mispricing frequency with ≥ 1% net edge after fees, or Strategy 2 is dead.

**2C — Microstructure characterization.** Compute VPIN and Kyle's λ for both platforms. Measure settlement divergence frequency: how often do CFB RTI and Polymarket oracle disagree on the same BTC event? Gate: divergence rate < 5% on 200+ paired settlements, or reclassify Strategy 3 from "structural arb" to "statistical arb."

**2D — Autoresearch hypothesis testing.** Generate 10–20 strategy variations. Replay against Phase 1 data, log to `results.tsv`. Gate: best strategy shows positive expectancy after realistic costs on an out-of-sample holdout (last 3 days of Phase 1 data).

### Phase 3: Sandbox Arb (Days 43–56)

All feeds live on VPS/Mini. Real-time arb detection, log-only mode.

- `src/arb_detector.py` scans paired orderbooks for net_arb > 0 opportunities.
- `src/arb_executor.py` runs would-be two-leg execution (SANDBOX=true). Slow leg first (Polymarket), fast leg second (Kalshi). Logs timestamps, hypothetical fills, slippage.
- `src/vpin.py` + `src/toxicity_gate.py` skip cycles with toxic flow.
- Track adverse selection rate, leg completion rate (both legs would have filled), hypothetical P&L.

**Gates:**

- Simulated positive P&L over 200+ would-be arb cycles.
- Adverse selection < 35%.
- Leg completion rate > 80%.
- If any gate fails, return to Phase 2 with new data.

### Phase 4: Micro-Live (Days 57–70)

SANDBOX=false. $5 per leg ($10 total per arb). Strategy 3 (cross-market arb) only.

- Max 2 arb cycles per hour. Manual review of first 20 trades.
- All alerting active (Telegram/Discord): feed drops, gas spikes, settlement divergence, drawdown.
- Track actual fill prices vs expected, actual fees vs estimated, actual P&L vs simulated.

**Gates:**

- Positive ROI over 100+ live trades.
- No single-day loss > 3% of account.
- Actual P&L within 50% of simulated P&L. If actual is much worse, there's a systematic execution problem.

### Phase 5: Scale & Optimize (Day 71+)

- Increase arb sizing to $20–$50 per leg.
- Add Strategy 2 (fair value mispricing) with separate $5 starting size.
- Activate Bayesian edge decay monitoring. Pause if P(edge < fee_drag) > 0.90.
- Activate the autoresearch loop: generate hypotheses, run experiments, log results, keep or revert.
- Recalibrate all models monthly from fresh data.
- Consider ETH and SOL markets if BTC edges remain stable for 4+ weeks.

---

## 7. Risk Management

### 7.1 Execution Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Leg risk (one side fills, other doesn't) | High | Execute slow leg first (Polymarket). Cancel fast leg if slow doesn't fill within 5s. Max exposure = one leg's cost. |
| Settlement divergence | High | `src/settlement_monitor.py` tracks CFB RTI vs oracle divergence. If divergence > 0.1% in trailing 24h, reduce arb sizing 50%. |
| API downtime | Medium | If either platform API is down, pause all trading. No manual overrides. |
| Rate limiting | Medium | Respect Kalshi's tiered limits. Polymarket: monitor for 429s, exponential backoff. |
| Polygon gas spike | Medium | If gas > 3× rolling 1h avg, skip Polymarket leg entirely. |
| Production pipeline contamination | High | CI gate: `git diff --name-only` before every commit. If any frozen file appears, block the push. Kalshi code lives in new files only. |

### 7.2 Financial Risks

| Rule | Threshold | Action |
|---|---|---|
| Phase 0 sizing | $25 flat, conviction ≥ 3 | Same as production Polymarket sizing |
| Phase 4 sizing | $5 per leg | Scale only after 100+ profitable cycles |
| Daily budget | $100 (Phase 4), $300 (Phase 5) | Stop trading when exhausted |
| Daily drawdown | −5% of account | Pause 24h, alert |
| Bayesian edge decay | P(edge < fees) > 0.90 | Reduce 50%, investigate. Persists 7 days → kill strategy. |
| Settlement divergence spike | > 3 divergent settlements in 24h | Pause all arb. Review settlement rules. |
| Cross-pipeline total loss | −$500 across all pipelines | Hard stop. Full review before further trading. |

### 7.3 Regulatory Risks

| Risk | Severity | Notes |
|---|---|---|
| Kalshi state lawsuits (Washington, March 2026) | Medium | CFTC has exclusive federal jurisdiction as of early 2026. State actions may disrupt but are unlikely to shut down. Monitor. |
| Polymarket US access | High | Not available to US persons. Using VPN or proxy introduces legal risk. Plan assumes non-US access or entity structure. |
| Cross-platform arb legality | Low | Arb between regulated and unregulated venues is not explicitly prohibited but is a legal gray area. Consult a lawyer before Phase 3. |

---

## 8. Kill Conditions

Every phase has explicit conditions under which the project is killed, not revised.

| Condition | Action |
|---|---|
| Pre-flight: Kalshi account or Polymarket access unresolvable | Kill cross-market. Kalshi-only momentum if account works. |
| Phase 0: Momentum WR < 50% on 200+ Kalshi predictions | Signal is venue-specific. Skip to Phase 1 (paired data). |
| Phase 1: Feeds cannot maintain > 95% uptime after 2 attempts | Kill. Infrastructure not viable. |
| Phase 2A: Net arb > 0 in < 5% of paired observations | Kill cross-market arb. Strategy 2 only. |
| Phase 2B: No platform shows > 3% mispricing frequency | Kill directional. Consider maker pivot or kill project. |
| Phase 2D: No strategy beats zero after realistic costs | Kill project. No edge exists. |
| Phase 3: Adverse selection > 50% on 200+ would-be trades | Kill. Market too efficient. |
| Phase 4: Negative ROI after 100 live trades | Kill live trading. Return to observation. |
| Any phase: Total losses exceed $500 | Hard stop. Full review before further trading. |

**Designated pivot:** If Strategies 2 and 3 both fail at their phase gates, the data from Phase 1–2 supports a maker strategy on one or both platforms. The pivot is to market-making — not to lowering thresholds.

---

## 9. Honest Assessment

Expected return is $5–$50/day on a $500–$2k bankroll at best. The infrastructure investment is significant relative to that.

What makes the plan viable despite modest expected returns: Phase 0 can generate revenue in two weeks with roughly 200 lines of new code. If momentum transfers to Kalshi, the project pays for itself while arb infrastructure is built in the background. If it doesn't, we learn that before committing to WebSocket feeds and execution engines.

The infrastructure also has option value. Paired cross-platform data collection, real-time microstructure analysis, and multi-venue execution transfer to any prediction market pair — not just BTC on Kalshi and Polymarket.

---

## Sources

- [Kalshi Fee Schedule](https://kalshi.com/fee-schedule)
- [Kalshi Crypto Markets](https://help.kalshi.com/en/articles/13823838-crypto-markets)
- [Kalshi API Documentation](https://docs.kalshi.com/welcome)
- [Kalshi Python SDK](https://github.com/Kalshi/kalshi-python)
- [Kalshi BTC Markets](https://kalshi.com/category/crypto/btc)
- [CF Benchmarks — Kalshi Crypto Settlement](https://www.cfbenchmarks.com/blog/kalshi-leads-surging-crypto-event-contract-market-powered-by-cf-benchmarks)
- [How Prediction Market Arbitrage Works](https://www.trevorlasn.com/blog/how-prediction-market-polymarket-kalshi-arbitrage-works)
- [Polymarket-Kalshi BTC Arbitrage Bot (GitHub)](https://github.com/CarlosIbCu/polymarket-kalshi-btc-arbitrage-bot)
- [py-clob-client (Polymarket SDK)](https://github.com/Polymarket/py-clob-client)
- [Prediction Market Fees Comparison](https://defirate.com/prediction-markets/fees/)
- [Prediction Market API Reference: Polymarket & Kalshi](https://agentbets.ai/guides/prediction-market-api-reference/)
- [VPIN and Order Flow Toxicity (Easley et al.)](https://www.quantresearch.org/VPIN.pdf)
- [Kyle's Lambda and Market Microstructure](https://www.stern.nyu.edu/sites/default/files/assets/documents/con_035928.pdf)
- [Kelly Criterion Applied to Prediction Markets](https://arxiv.org/html/2412.14144v1)
- [MEV Implications for Crypto Markets (ESMA)](https://www.esma.europa.eu/sites/default/files/2025-07/ESMA50-481369926-29744_Maximal_Extractable_Value_Implications_for_crypto_markets.pdf)
- [Washington Sues Kalshi (March 2026)](https://www.coindesk.com/policy/2026/03/28/washington-sues-kalshi-as-states-ramp-up-legal-pressure-against-prediction-markets)
- [Kalshi vs Polymarket Comparison](https://next.io/prediction-markets/guide/kalshi-vs-polymarket/)
