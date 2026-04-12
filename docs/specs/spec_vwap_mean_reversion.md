# Spec: VWAP Mean-Reversion Strategy

> **Status:** STILL RELEVANT — In Strategy Lab as always-fire; spec describes production graduation version

**Status:** Proposed
**Pipeline:** 5-minute (new signal source within existing pipeline)
**Problem:** The model skips all MEAN_REVERTING regime predictions — 200+ per day, zero bets. This is by design: the current model is momentum-based and has no edge in mean-reverting conditions. But the skip rate is massive. If even a fraction of those predictions could be traded with a different strategy, it's a significant untapped source of P&L.
**Goal:** Use VWAP deviation to generate high-conviction bets specifically within the MEAN_REVERTING regime, where the existing model stays out.

---

## How It Works

VWAP (Volume Weighted Average Price) represents where most volume traded — the "fair value" line. In mean-reverting markets, price oscillates around fair value. When price deviates too far from VWAP, it tends to snap back.

This strategy **only activates in MEAN_REVERTING regimes**. It does not compete with or modify the existing momentum model. It's a parallel signal for a regime the current model ignores.

```
INPUT:  regime, BTC price, VWAP, standard deviation of VWAP deviation
OUTPUT: new prediction (direction + conviction) or skip
```

### Signal Logic

| VWAP Deviation | Signal | Rationale |
|---------------|--------|-----------|
| Price > VWAP + 2σ | DOWN (bet NO on UP) | Price overextended above fair value — reversion likely |
| Price > VWAP + 1.5σ | DOWN (lower conviction) | Moderately overextended |
| Price within ±1.5σ | Skip | Too close to fair value — no edge |
| Price < VWAP - 1.5σ | UP (lower conviction) | Moderately underextended |
| Price < VWAP - 2σ | UP (bet YES on UP) | Price overextended below fair value — bounce likely |

### Conviction Mapping

| Deviation | Conviction | Bet Size |
|-----------|-----------|----------|
| > 2.5σ | conv=4 | $200 |
| 2.0–2.5σ | conv=3 | $75 |
| 1.5–2.0σ | conv=2 | $0 (shadow only during validation) |
| < 1.5σ | Skip | — |

During the validation phase, only conv=2 (shadow) bets are generated. No real money is risked until the strategy proves itself at 50+ shadow bets.

---

## Why VWAP and Not Bollinger Bands?

Bollinger Bands use a simple moving average. VWAP weights by volume, which better represents where actual trading interest sits. In crypto markets where volume is spiky and uneven, VWAP is more stable and meaningful than SMA-based indicators.

Additionally, your CLOB liquidity data shows where orders cluster — VWAP aligns conceptually with order flow, making it a natural fit for Polymarket.

---

## Integration Point

```
existing flow (momentum):
  prediction → regime check → [MEAN_REVERTING? → skip]
                            → [other regimes → conviction scorer → filters → bet]

new flow:
  prediction → regime check → [MEAN_REVERTING? → VWAP strategy → filters → bet]
                            → [other regimes → conviction scorer → filters → bet]
```

The VWAP strategy is a **parallel path**, not a modification to the existing model. It activates exclusively when regime = MEAN_REVERTING. The existing momentum path is completely unchanged.

Both paths feed into the same downstream filters (RSI gate, OBV filter) before reaching the bet placer.

---

## VWAP Calculation

```
VWAP = Σ(Price × Volume) / Σ(Volume)
```

Calculated on a rolling intraday basis, reset daily at 00:00 UTC.

Standard deviation of the VWAP deviation:
```
deviation = price - VWAP
σ = rolling std(deviation, window=lookback)
```

### Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| VWAP period | Intraday (reset daily) | Standard practice |
| Deviation lookback | 50 candles (250 min) | Enough history to compute meaningful σ |
| Entry threshold | 1.5σ | Minimum deviation to consider a signal |
| High-conviction threshold | 2.0σ | Strong signal — likely reversion |
| Source | BTC 5-min OHLCV with volume | Same feed as RSI and OBV |
| Active regime | MEAN_REVERTING only | HIGH_VOL, MEDIUM_VOL, or LOW_VOL — all sub-types |

---

## Expected Impact

Based on Mar 25–29 data, MEAN_REVERTING predictions per day:

| Date | MEAN_REVERTING Predictions | Regimes |
|------|---------------------------|---------|
| Mar 25 | 46 | HIGH_VOL (33), MEDIUM_VOL (13) |
| Mar 26 | 73 | HIGH_VOL (24), MEDIUM_VOL (49) |
| Mar 27 | 102 | HIGH_VOL (37), MEDIUM_VOL (65) |
| Mar 28 | 55 | HIGH_VOL (7), MEDIUM_VOL (38), LOW_VOL (10) |
| Mar 29 | 100 | HIGH_VOL (4), MEDIUM_VOL (84), LOW_VOL (12) |

That's **376 predictions** over 5 days — all currently discarded. Even a 10% hit rate on VWAP signals (37 bets) at 60% WR would add meaningful P&L.

**Conservative estimate:** 5–10 VWAP bets per day at 60% WR on $75 sizing = +$30–75/day. Modest compared to the momentum model but it's pure incremental edge from an unused regime.

**Upside scenario:** If VWAP signals prove strong (>65% WR), conviction can be increased and this becomes a meaningful second strategy.

---

## Interaction with RSI Gate and OBV Filter

VWAP signals flow through the same downstream filters:

| Filter | Interaction |
|--------|------------|
| RSI Gate | **Complementary.** VWAP says "price is too far from fair value." RSI says "yes, the market is overextended." Agreement = higher confidence. Conflict (e.g., VWAP says buy but RSI isn't oversold) = RSI may downgrade conviction |
| OBV Filter | **Applies only to 0.50–0.70 bucket.** VWAP mean-reversion signals in this range must also pass OBV confirmation. This is appropriate — we want extra confirmation for fair-value contracts even in a mean-reversion context |

The three specs form a layered system:

```
MEAN_REVERTING regime:
  VWAP signal → RSI gate → OBV filter (if 0.50-0.70) → bet

Other regimes:
  Existing model → RSI gate → OBV filter (if 0.50-0.70) → bet
```

---

## Implementation

```python
import numpy as np

def vwap_strategy(regime, btc_closes, btc_highs, btc_lows, btc_volumes, lookback=50):
    """
    Generate mean-reversion signal for MEAN_REVERTING regime.
    Returns (direction, conviction) or None to skip.
    """
    if "MEAN_REVERTING" not in regime:
        return None  # only active in mean-reverting regimes

    # VWAP calculation (intraday, using typical price)
    typical_prices = (btc_highs + btc_lows + btc_closes) / 3
    cum_tp_vol = np.cumsum(typical_prices * btc_volumes)
    cum_vol = np.cumsum(btc_volumes)
    vwap = cum_tp_vol / cum_vol

    # Current deviation
    current_price = btc_closes[-1]
    current_vwap = vwap[-1]
    deviation = current_price - current_vwap

    # Standard deviation of recent deviations
    recent_devs = btc_closes[-lookback:] - vwap[-lookback:]
    sigma = np.std(recent_devs)

    if sigma == 0:
        return None

    z_score = deviation / sigma

    # Signal generation
    if z_score > 2.0:
        return ("DOWN", 3)   # strong overextension — bet on reversion
    elif z_score > 1.5:
        return ("DOWN", 2)   # moderate — shadow only
    elif z_score < -2.0:
        return ("UP", 3)     # strong underextension
    elif z_score < -1.5:
        return ("UP", 2)     # moderate — shadow only
    else:
        return None           # within normal range — no signal
```

---

## Data Requirements

| Data | Source | Already Available? |
|------|--------|--------------------|
| BTC 5-min OHLCV with volume | Exchange API | Yes (shared with RSI/OBV) |
| Regime classification | Existing pipeline | Yes |
| VWAP calculation | numpy | New — ~10 lines |
| Contract price | Polymarket CLOB | Yes |

No new data sources required. All three specs (RSI, OBV, VWAP) share the same BTC 5-min feed.

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Mean-reversion fails in regime transition | Regime detector catches the shift. Strategy only runs while MEAN_REVERTING is active. If regime flips to TRENDING mid-trade, the bet is already placed — but sizing is conservative (conv=3 max during validation) |
| VWAP reset at midnight creates edge cases | Don't generate signals in the first 30 minutes after reset (< 6 candles of VWAP data). Require minimum lookback |
| Overfitting σ thresholds | Start with standard 1.5/2.0σ levels. These are widely used in quantitative finance. Adjust only after 100+ shadow bets |
| Strategy generates too many signals | MEAN_REVERTING regime is already a strong filter. Adding the 1.5σ threshold further narrows to only extreme deviations. Expect 5–10 signals/day, not 50 |
| Interferes with momentum model | Impossible — VWAP strategy only runs in regimes the momentum model explicitly skips. Zero overlap |

---

## Validation Plan

```
name: vwap_mean_reversion
type: shadow (conv=2, no real bets)
method:
  - On every MEAN_REVERTING prediction, compute VWAP deviation
  - Log signal (direction, conviction, z-score, VWAP, price)
  - Track resolution outcome as if bet were placed
threshold: 50 shadow bets
success_criteria:
  - Shadow WR > 58% (above chance, below momentum model)
  - Positive shadow P&L at conv=3 sizing
  - Signal distribution across HIGH/MEDIUM/LOW_VOL sub-regimes
baseline: 0% (currently no bets in this regime)
```

The bar is deliberately lower than the momentum model (66%+ WR). This is a new strategy in an untested regime — 58% WR with positive expected value is enough to justify proceeding to live testing.

---

## Phased Rollout

| Phase | Duration | Action |
|-------|----------|--------|
| 1. Shadow | 50 bets (~5-10 days) | Log signals, no money. Validate WR > 58% |
| 2. Small stakes | 50 bets | conv=3 only ($75). Confirm real P&L matches shadow |
| 3. Full integration | Ongoing | Enable conv=3/4 based on z-score. Treat as standard signal |

---

## Decision

Add `vwap_mean_reversion` to the decision alerts tracker in `docs/core/decisions.md`. Start shadow logging. This is the only spec of the three that generates **new** signals (RSI and OBV modify existing ones), so it should be validated independently before combining with the other filters.
