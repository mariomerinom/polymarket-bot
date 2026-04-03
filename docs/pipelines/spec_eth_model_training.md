# Spec: ETH-Specific Model Training

**Status:** Partially superseded — see update below
**Pipeline:** ETH 5-minute
**Problem:** The ETH pipeline launched on Mar 30 using what appears to be the BTC model applied to ETH markets. Results: 105 predictions, 0 bets, conv=0 at 60.2% WR, conv=2 at 47.1% WR (below coin flip). The model doesn't generalize — ETH has different volatility structure, correlation dynamics, and market microstructure than BTC. Additionally, ETH Polymarket liquidity is 4x worse than BTC (3.98% avg spread vs 1.50%, $149 max bet vs $910).
**Goal:** Train a dedicated ETH model that accounts for ETH-specific dynamics and the tighter liquidity constraints of ETH prediction markets.

> **2026-04-01 UPDATE:** The ETH pipeline has been flipped from contrarian to **momentum** (ride streaks). The original contrarian signal lost at 33.3% WR on 54 resolved predictions; momentum counterfactual on the same bets: 66.7%. Same V3→V4 pattern as BTC. The Option B adaptation layer (regime recalibration, cross-asset features, ETH conviction scoring) remains the plan for Phase 2, but the signal direction is now momentum, not contrarian. See `docs/pipelines/eth_pipeline_acceptance_criteria.md` for the current phased rollout plan.

---

## Why the BTC Model Fails on ETH

### 1. Different Volatility Profile

ETH is structurally more volatile than BTC. On Mar 30, 93% of ETH predictions fell in HIGH_VOL regimes vs. ~30% for BTC. The BTC model's regime thresholds are calibrated to BTC's volatility distribution — what BTC considers HIGH_VOL is ETH's baseline. The model is permanently in "cautious mode" on ETH because it thinks conditions are always extreme.

### 2. Different Market Microstructure

| Factor | BTC Polymarket | ETH Polymarket |
|--------|---------------|----------------|
| Avg spread | 1.50% | 3.98% |
| Max bet @2% slippage | $910 | $149 |
| Slippage at $200 | 0.78% | 6.09% |
| Wide spreads (>3%) | 0% | 56% |
| YES/NO liquidity asymmetry | YES 4x deeper | Less pronounced |

The BTC model assumes tight spreads and deep books. ETH markets are thinner, wider, and more fragile. The model needs to internalize these constraints — both as features (spread width as an input) and as sizing limits.

### 3. ETH-BTC Correlation Dynamics

ETH doesn't move independently. It has a strong but variable correlation with BTC, typically ranging 0.6–0.9. Key dynamics the model needs to capture:

- **Beta effect:** ETH tends to amplify BTC moves (ETH beta ~1.2-1.5x). A 2% BTC move often means a 2.5-3.5% ETH move.
- **Lag effect:** ETH sometimes lags BTC by 1-5 minutes on large moves. This creates a predictable catch-up window.
- **Decorrelation events:** During ETH-specific catalysts (Ethereum upgrades, DeFi events, ETH ETF flows), correlation drops and the BTC model becomes irrelevant.
- **ETH/BTC ratio:** The ETH/BTC pair itself trends. When it's falling, ETH underperforms BTC on rallies and drops harder on selloffs.

### 4. Conviction Calibration Mismatch

Conv=2 at 47.1% WR means the model's second confidence tier is net negative on ETH. The conviction scorer was calibrated on BTC data. ETH needs its own calibration — what constitutes a "confident" signal is different when the underlying is more volatile and the markets are thinner.

---

## Proposed Architecture

### Option A: Independent ETH Model

Train a completely separate model on ETH data with ETH-specific features.

```
ETH price data → ETH feature engineering → ETH model → ETH conviction scorer → bet
```

**Pros:** Clean separation. No BTC assumptions leak in. Can be optimized purely for ETH dynamics.
**Cons:** Requires enough ETH training data. Cold start problem — the BTC model had months of data before going live.

### Option B: BTC Model + ETH Adaptation Layer

Keep the core BTC model but add an ETH-specific translation layer that adjusts predictions for ETH dynamics.

```
BTC model prediction → ETH adapter (beta, lag, correlation, spread) → adjusted prediction → ETH conviction scorer → bet
```

**Pros:** Leverages proven BTC model. Faster to ship. Can start with simple rules and iterate.
**Cons:** Inherits BTC model weaknesses. The adapter may not capture ETH-specific edges.

### Option C: Multi-Asset Model (Recommended for v2)

Single model trained on both BTC and ETH data with asset-specific features.

```
[BTC + ETH] data → shared feature engineering → asset-aware model → asset-specific conviction → bet
```

**Pros:** Learns cross-asset relationships natively. Can detect when ETH is about to decorrelate from BTC. Shared training data improves both.
**Cons:** Most complex. Requires careful feature engineering to prevent BTC signal from dominating.

### Recommendation: Start with Option B, evolve to Option C

Option B can ship in days. Option C is the long-term target but requires significantly more data and engineering.

---

## ETH Feature Engineering

### Features to Add (Not in BTC Model)

| Feature | Type | Rationale |
|---------|------|-----------|
| ETH/BTC ratio (current) | Continuous | Captures relative strength. Low ratio = ETH weak, may underperform |
| ETH/BTC ratio slope (5-min) | Continuous | Direction of relative strength shift |
| BTC 5-min return (lagged) | Continuous | Captures ETH lag effect. If BTC moved 2% in last 5 min and ETH hasn't caught up, high-probability signal |
| ETH-BTC rolling correlation (1h) | Continuous | When correlation drops, BTC-derived signals are less reliable — reduce conviction |
| ETH funding rate | Continuous | High funding = crowded long. Low = crowded short. Contrarian signal |
| ETH open interest change (5-min) | Continuous | Rapid OI increase = new positions entering. Confirms move conviction |
| Polymarket ETH spread | Continuous | Wider spread = less liquid = smaller sizing. Should be a feature AND a constraint |
| Polymarket ETH book depth | Continuous | Thin book = unreliable price. Model should factor in execution feasibility |
| Hour of day | Categorical | ETH liquidity varies by hour more than BTC. Asian hours may be particularly thin |
| Day of week | Categorical | Weekend ETH liquidity drops more than BTC |

### Features to Recalibrate from BTC

| Feature | BTC Calibration | ETH Calibration Needed |
|---------|----------------|----------------------|
| Volatility regime thresholds | Based on BTC vol distribution | Shift upward — ETH is structurally more volatile |
| RSI period | 14 (70 min lookback) | Consider 10-12. ETH moves faster, RSI needs to be more responsive |
| VWAP deviation σ | Based on BTC deviation range | Wider bands. ETH deviates further from VWAP before reverting |
| OBV significance threshold | Based on BTC volume norms | Adjust for ETH's different volume profile and exchange distribution |

---

## Training Data Requirements

### Minimum Data for Option B (Adaptation Layer)

| Data | Source | Period |
|------|--------|--------|
| ETH 5-min OHLCV | Coinbase | 90+ days |
| BTC 5-min OHLCV (aligned) | Same source | Same period |
| ETH/BTC pair | Derived or Binance | Same period |
| ETH Polymarket contract outcomes | Internal logs | All available (since launch) |
| ETH Polymarket CLOB snapshots | Internal logs | All available |

### Minimum Data for Option C (Multi-Asset Model)

All of the above, plus:

| Data | Source | Period |
|------|--------|--------|
| ETH funding rates | Binance/Bybit | 90+ days |
| ETH open interest | Binance/Bybit | 90+ days |
| ETH on-chain metrics (gas, active addresses) | Etherscan/Dune | 90+ days |
| Cross-exchange ETH price (for consensus) | Multiple CEXes | 90+ days |

---

## ETH-Specific Conviction Scoring

The BTC conviction scorer needs to be replaced for ETH. Key differences:

### Regime Thresholds

```python
# BTC regime thresholds (current)
BTC_VOL_THRESHOLDS = {
    "LOW": (0, 0.8),      # annualized vol
    "MEDIUM": (0.8, 1.5),
    "HIGH": (1.5, float('inf'))
}

# ETH regime thresholds (proposed)
ETH_VOL_THRESHOLDS = {
    "LOW": (0, 1.2),       # shifted up — ETH baseline vol is higher
    "MEDIUM": (1.2, 2.2),
    "HIGH": (2.2, float('inf'))
}
```

### Conviction Adjustments

```python
def eth_conviction_adjustments(conviction, features):
    """ETH-specific adjustments on top of base model conviction."""

    # Correlation gate: reduce conviction when ETH decorrelates from BTC
    if features['eth_btc_correlation_1h'] < 0.5:
        conviction = max(conviction - 1, 0)

    # Lag detector: boost conviction when BTC moved and ETH hasn't caught up
    btc_5m_return = features['btc_return_5m']
    eth_5m_return = features['eth_return_5m']
    if abs(btc_5m_return) > 0.01 and abs(eth_5m_return) < abs(btc_5m_return) * 0.3:
        conviction = min(conviction + 1, 5)  # ETH likely to catch up

    # Spread gate: cap conviction when market is too wide
    if features['polymarket_spread'] > 3.0:
        conviction = min(conviction, 3)  # never conv=4/5 on wide spreads

    # Liquidity cap: hard ceiling based on book depth
    max_bet_2pct = features['max_bet_at_2pct_slippage']
    if max_bet_2pct < 100:
        conviction = min(conviction, 2)  # shadow only

    return conviction
```

---

## ETH Sizing Constraints

Given the liquidity profile, ETH needs its own sizing table:

| Conviction | BTC Bet Size | ETH Bet Size | Rationale |
|-----------|-------------|-------------|-----------|
| conv=3 | $75 | $25 | ETH max bet @2% slippage is $149. Stay well under |
| conv=4 | $200 | $50 | $200 would cost 6% slippage on ETH |
| conv=5 | $300 | $75 | Still under the $149 ceiling |

These sizes should be **dynamic**, adjusted by the CLOB liquidity data available at prediction time:

```python
def eth_bet_size(conviction, max_bet_at_2pct_slippage):
    """Size ETH bets based on available liquidity."""
    base_sizes = {3: 25, 4: 50, 5: 75}
    base = base_sizes.get(conviction, 0)

    # Never exceed 50% of available liquidity at 2% slippage
    ceiling = max_bet_at_2pct_slippage * 0.5
    return min(base, ceiling)
```

---

## Validation Plan

### Phase 1: Shadow Mode (Option B — Adaptation Layer)

```
name: eth_adapted_model
duration: 50 shadow bets (~2-4 weeks at current prediction volume)
method:
  - Apply BTC model + ETH adapter to all ETH predictions
  - Log adjusted conviction, direction, and what the bet would have been
  - Track shadow WR and P&L
success_criteria:
  - Shadow WR > 55% (lower bar than BTC — ETH markets are harder)
  - Shadow P&L positive at ETH sizing ($25-75 bets)
  - Conviction distribution: conv=3+ signals on at least 10% of predictions
baseline: current conv=0 WR (60.2%)
```

### Phase 2: Small Stakes Live

```
duration: 50 live bets
sizing: $25 flat (conv=3 equivalent)
circuit_breaker: $150 max drawdown (6 consecutive losses)
success_criteria:
  - Live WR > 55%
  - Positive P&L after slippage and spread
  - Actual slippage < 3% on average
```

### Phase 3: Full Integration

```
sizing: dynamic ($25-75 based on conviction and liquidity)
review: weekly
success_criteria:
  - Consistent positive P&L over 4 weeks
  - No circuit breaker triggers
```

---

## Implementation Priority

| Step | Effort | Dependencies |
|------|--------|-------------|
| 1. Recalibrate volatility regime thresholds for ETH | Low (config change) | None |
| 2. Add ETH/BTC correlation and lag features | Medium (new data feed) | ETH + BTC aligned price data |
| 3. Implement ETH conviction adjustments | Low (code) | Step 1 + 2 |
| 4. Implement ETH-specific sizing table | Low (config) | CLOB data (already available) |
| 5. Deploy shadow mode | Low (logging) | Steps 1-4 |
| 6. Collect 50 shadow bets and evaluate | Time (2-4 weeks) | Step 5 |
| 7. Train multi-asset model (Option C) | High | 90+ days of ETH data |

Steps 1-5 can be shipped in 1-2 days. The adaptation layer approach is fast because it reuses the existing BTC model infrastructure.

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Not enough ETH Polymarket contract volume | Start with shadow mode. If < 5 predictions/day with conviction, the market isn't ready |
| Liquidity dries up further | Dynamic sizing + CLOB-based circuit breaker. If max bet < $25, auto-pause |
| ETH-specific events cause model failure (upgrades, forks) | Add ETH event calendar as a feature. Skip trading during known events |
| BTC model overfits to BTC patterns | Option B adapter partially mitigates. Option C (multi-asset) solves properly |
| Spread is too wide to be profitable | At 4% spread, model needs ~57% WR just to break even on ETH. Shadow mode will reveal if edge exceeds cost |

---

## Break-Even Analysis

```
Avg ETH spread:     3.98%
Avg ETH slippage:   ~2% at $50 bet size (estimated, smaller than $200 benchmark)
Total cost per bet: ~5%
Required WR to break even (at fair-value contracts): ~55%
Current conv=0 WR:  60.2%

Margin of safety: ~5pp
```

The raw predictions (conv=0) at 60.2% WR technically clear the break-even hurdle, but that's before accounting for the conviction filter's role in selecting the best predictions. If the ETH-adapted conviction scorer can push selected-bet WR above 60%, the pipeline should be profitable even with ETH's wide spreads — at small sizing.

---

## Decision

Implement Option B (adaptation layer) as steps 1-5 above. Begin shadow logging. Revisit Option C (multi-asset model) after 90 days of ETH data collection. Do not deploy live ETH bets until shadow mode clears 50 bets at > 55% WR.
