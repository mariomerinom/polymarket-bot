# Spec: Market Price Dislocation Strategy

> **Status:** STILL RELEVANT — Basis trade between spot and Polymarket not built

**Status:** Proposed
**Pipeline:** BTC 5m (primary), ETH 5m (after Phase 1 validates)
**Category:** New strategy — arbitrage-adjacent. Independent from momentum.
**Problem:** The pipeline has two price sources that should be in sync but aren't always: BTC spot price (Coinbase) and Polymarket contract price. When BTC moves quickly, the Polymarket contract price lags — it takes time for market participants to update their orders. This lag creates a pricing dislocation where the contract is temporarily mispriced relative to the information already reflected in spot.
**Goal:** Detect when the Polymarket contract price hasn't caught up to a BTC spot move and bet on convergence.

---

## Why This Is Different from Momentum

| Aspect | Momentum | Market Price Dislocation |
|--------|----------|------------------------|
| Signal source | BTC candle streaks | BTC spot vs Polymarket contract price divergence |
| What it detects | Trend continuation | Temporary mispricing |
| Requires streak | Yes (3+ candles) | No — single candle move is enough |
| Speed | 15+ min after move starts | 1-5 min after move |
| Works when | Trends persist | Any fast move where Polymarket lags spot |
| Regime dependency | Best in TRENDING/NEUTRAL | Works in any regime if the move is fast enough |

The core difference: momentum bets that a trend continues. Dislocation bets that two prices converge. These are different economic bets — dislocation can profit even if the trend reverses, as long as the contract catches up to where spot already is.

---

## Signal Logic

### Step 1: Compute Implied vs Actual Contract Price

The Polymarket contract resolves based on whether BTC is above or below a reference price at expiry. The BTC spot price implies what the contract *should* be worth. The actual contract price is what the CLOB says.

```
implied_probability = f(btc_spot, reference_price, time_to_expiry, volatility)
actual_price = polymarket_contract_mid_price

dislocation = implied_probability - actual_price
```

For short-term contracts (5-min), the implied probability simplifies: if BTC spot has already moved decisively past the reference, the implied probability is near 1.0 or 0.0. The contract price should reflect this but may not have updated.

### Step 2: Simplified Dislocation (No Options Math Needed)

For 5-min binary contracts, we don't need Black-Scholes. A simpler heuristic:

```
btc_move = (btc_current - btc_5min_ago) / btc_5min_ago
contract_move = contract_price_now - contract_price_5min_ago

expected_contract_move = btc_move × sensitivity
dislocation = expected_contract_move - contract_move
```

Where `sensitivity` is the empirical relationship between BTC spot moves and contract price moves. This can be calibrated from historical data.

### Step 3: Signal Generation

| Dislocation | Signal | Meaning |
|------------|--------|---------|
| > +threshold | Buy YES (predict UP) | Contract hasn't priced in the BTC move up |
| < -threshold | Buy NO (predict DOWN) | Contract hasn't priced in the BTC move down |
| Within ±threshold | No signal | Prices are in sync |

### Threshold Calibration

The threshold must exceed trading costs:

```
min_dislocation = spread + slippage + margin_of_safety
BTC: 1.5% + 1% + 1% = 3.5% contract price dislocation
ETH: 5% + 2% + 1.5% = 8.5% contract price dislocation
```

Only trade when the mispricing exceeds what it costs to capture it.

---

## Sensitivity Calibration

The relationship between BTC spot moves and contract price moves varies by:

- **Contract price level:** Near 0.50, contracts are most sensitive to BTC moves. Near 0.10 or 0.90, they're less sensitive (already priced in).
- **Time to expiry:** More time = more uncertainty = less sensitivity to current spot.
- **Volatility regime:** HIGH_VOL = each spot move matters less (noise). LOW_VOL = each move matters more (signal).

### Empirical Approach

Regress contract price changes on BTC spot changes over historical data:

```
contract_Δ = α + β × btc_Δ + ε

Group by:
  - contract_price bucket (0.15-0.30, 0.30-0.50, 0.50-0.70, 0.70-0.85)
  - volatility regime
  - time bucket within contract life
```

This gives per-bucket sensitivity coefficients. A 1% BTC move when the contract is at 0.50 in LOW_VOL should move the contract by X%. If it moved less than X%, there's a dislocation.

---

## Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| BTC spot lookback | 1 candle (5 min) | How far back to measure the spot move |
| Min BTC move | 0.3% | Below this, spot move is too small to create detectable dislocation |
| Min dislocation | 3.5% (BTC), 8.5% (ETH) | Must exceed round-trip trading cost |
| Sensitivity source | Empirical regression per bucket | Calibrated from historical data |
| Max time to trade | 2 minutes after detection | Dislocation closes quickly — must act fast |
| Cooldown | 5 minutes | Don't re-enter the same dislocation |

---

## Data Requirements

| Data | Source | Currently Available? |
|------|--------|---------------------|
| BTC 5-min OHLCV | Coinbase | Yes |
| BTC 1-min OHLCV | Coinbase | Needed for faster detection (shared with stochastic spec) |
| Polymarket contract mid-price | CLOB | Yes — in liquidity profile |
| Historical contract price series | Internal logs | Partially — need higher frequency logging |
| Contract reference price / expiry | Polymarket API (Gamma) | Yes — fetched in `_get_clob_tokens()` |

### New Infrastructure Needed

1. **Contract price time series:** Store contract mid-price at every prediction cycle (already happening) AND at higher frequency if CLOB polling loop (from order flow spec) is deployed.
2. **Sensitivity table:** Pre-compute β coefficients per price bucket × regime. Update weekly.
3. **Fast execution path:** Dislocation signals are time-sensitive. The stochastic entry timing spec's 60-second window may be too slow here. Consider immediate execution for dislocation signals.

---

## Interaction with Other Strategies

| Strategy | Relationship |
|----------|-------------|
| Momentum | **Complementary but independent.** Momentum needs 3+ candles. Dislocation fires on the first candle if the move is large enough. They may overlap on the same trade, but dislocation enters earlier |
| Order Flow | **Strongly complementary.** Order flow sees positioning before the move. Dislocation sees the move after it happens but before the contract updates. Together: order flow signals "something is about to happen," dislocation confirms "it happened and the contract hasn't caught up" |
| RSI/OBV/VWAP | **Minimal interaction.** These are filters on existing signals. Dislocation generates its own signal from a different source |

---

## Expected Impact

Dislocation events are rare but high-conviction. On volatile days, BTC can move 1-2% in a single 5-min candle. If Polymarket takes 2-3 minutes to reprice:

```
Estimated signals: 2-5 per day on volatile days, 0-1 on calm days
Average: ~2 signals/day
At conv=3 ($75) × 70% WR (high conviction — mispricing is structural) = ~$30/day
Monthly: ~$900
```

The WR estimate is aggressive (70%) but justified: this isn't predicting direction — it's capturing a known mispricing. The main risk is that the dislocation closes before the bet settles, not that the direction is wrong.

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Dislocation closes before bet fills | Fast execution path (skip stochastic timing). Use limit orders at the dislocated price, not market orders |
| Sensitivity coefficients are wrong | Calibrate from data, not theory. Update weekly. Start conservative (higher thresholds) |
| False dislocations from CLOB noise | Require BTC spot move > 0.3% as a precondition. A "dislocation" without a spot move is just CLOB noise |
| Strategy is front-runnable by faster bots | Possible, but Polymarket's CLOB is less competitive than traditional exchanges. First-mover advantage is less critical than in HFT |
| Works only on volatile days | True — this is a conditional strategy. Zero signals on calm days is fine. It's additive edge, not the primary strategy |

---

## Validation Plan

```
name: market_price_dislocation
type: data collection → shadow → small stakes

Phase 1 — Calibration (1 week):
  - Log BTC spot moves alongside contract price changes at every prediction cycle
  - Compute sensitivity coefficients per price bucket × regime
  - Identify historical dislocation events retroactively
  - Estimate: how many signals per day? What WR would they have achieved?

Phase 2 — Shadow (30 signals):
  - Generate shadow predictions from dislocation events
  - Lower threshold than planned: 30 signals will take time at 2/day
  - Track: WR, time-to-convergence, actual vs predicted contract move
  - Success: WR > 60%, average convergence < 3 minutes

Phase 3 — Small Stakes (30 bets):
  - Enable at conv=3 ($75)
  - Fast execution (no stochastic delay)
  - Circuit breaker: $225 max drawdown
  - Success: positive P&L net of spread/slippage
```

---

## Decision

This strategy shares infrastructure needs with the order flow spec (higher-frequency CLOB snapshots). Deploy the CLOB polling loop first, then both strategies benefit. Begin sensitivity calibration immediately using existing per-prediction CLOB data — this requires no new infrastructure, just analysis of data already being logged.
