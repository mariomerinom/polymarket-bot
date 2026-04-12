# Spec: OBV Confirmation Filter for 0.50–0.70 Bucket

> **Status:** STILL RELEVANT — OBV computed but not used; price-bucket specific filter

**Status:** Proposed
**Pipeline:** 5-minute
**Problem:** The 0.50–0.70 price bucket is the highest-volume bucket but the most inconsistent performer. WR swings wildly by day: 75% → 52% → 56% → 91.7% → 83.3%. These contracts sit near fair value, making them hardest to predict on price alone. The model needs a secondary confirmation signal to distinguish real moves from noise in this range.
**Goal:** Use On-Balance Volume (OBV) as a confirmation filter. Only bet the 0.50–0.70 bucket when volume supports the predicted direction. Pass all other buckets through unchanged.

---

## How It Works

OBV tracks cumulative volume flow. When price moves up on increasing volume, OBV rises — the move has real participation behind it. When price moves up but OBV is flat or falling, the move is weak and likely to reverse.

The filter applies **only** to bets where the contract mid-price is 0.50–0.70. All other price buckets bypass this check entirely.

```
INPUT:  prediction direction (UP/DOWN), contract price, OBV trend, conviction
OUTPUT: bet / skip decision
```

### Rules

| Contract Price | OBV Trend | Prediction | Action |
|---------------|-----------|------------|--------|
| 0.50–0.70 | OBV rising (slope > 0) | UP | ✅ Allow bet |
| 0.50–0.70 | OBV rising (slope > 0) | DOWN | ❌ Skip — volume contradicts |
| 0.50–0.70 | OBV falling (slope < 0) | DOWN | ✅ Allow bet |
| 0.50–0.70 | OBV falling (slope < 0) | UP | ❌ Skip — volume contradicts |
| 0.50–0.70 | OBV flat (abs(slope) < threshold) | Any | ❌ Skip — no conviction in volume |
| < 0.50 or > 0.70 | Any | Any | ✅ Pass through (no filter) |

The core logic: in the 0.50–0.70 range, only bet when money flow agrees with direction. When OBV is flat, there's no real participation — skip.

### OBV Calculation

OBV is cumulative. On each candle:
```
if close > prev_close: OBV += volume
if close < prev_close: OBV -= volume
if close == prev_close: OBV unchanged
```

OBV trend is determined by linear regression slope over the lookback window.

### Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| OBV lookback | 14 candles | 70 minutes on 5-min. Matches RSI period for consistency |
| Slope threshold | ±0.5 std dev of rolling slope | Below this = "flat". Auto-calibrates to market conditions |
| Source | BTC spot volume (Binance/Coinbase) | Proxy for contract-level flow |
| Price range | 0.50–0.70 | Only bucket where filter is active |

---

## Integration Point

```
existing flow:
  prediction → conviction scorer → [RSI gate] → bet placer

new flow:
  prediction → conviction scorer → [RSI gate] → OBV filter → bet placer
                                                  ↑
                                          only fires for 0.50-0.70
```

OBV filter sits after the RSI gate. If RSI already downgraded conviction to 0 (skip), OBV never runs. If OBV skips a bet, it logs the skip reason for shadow analysis.

---

## Expected Impact

Based on Mar 25–29 data for the 0.50–0.70 bucket:

| Date | Bets | WR | P&L | Likely OBV action |
|------|------|----|-----|-------------------|
| Mar 25 | 16 | 75.0% | +$523.11 | Strong trend day — OBV confirms most bets |
| Mar 26 | 23 | 52.2% | +$230.32 | Mixed day — OBV would filter ~half |
| Mar 27 | 16 | 56.2% | -$180.38 | BTC declining — OBV likely filters bad UP bets |
| Mar 28 | 12 | 91.7% | +$1,398.29 | Clear trend — OBV confirms |
| Mar 29 | 12 | 83.3% | +$1,424.22 | Clear trend — OBV confirms |

The filter's main target is days like Mar 26 and 27 where WR drops below 60%. If OBV filters out even 5 losing bets on those days, that's ~$500 in avoided losses while keeping the high-WR days intact.

**Conservative estimate:** +$150–300/day improvement on weak days, minimal drag on strong days.

---

## Why Only 0.50–0.70?

| Bucket | Behavior | Why OBV doesn't help |
|--------|----------|---------------------|
| 0.15–0.30 | Low price, high payout. Small sample but high WR. | Edge comes from mispricing, not momentum |
| 0.30–0.50 | Moderate. Generally profitable. | Model already has decent edge here |
| **0.50–0.70** | **Near fair value. WR swings 52–92%.** | **Needs confirmation — price alone isn't enough** |
| 0.70–0.85 | High price, low payout. Small sample. | Too few bets to justify added complexity |

The 0.50–0.70 range is uniquely vulnerable because these contracts are priced near 50/50 — the market is uncertain. OBV adds the "is money backing this move?" check that pure price analysis misses.

---

## Data Requirements

| Data | Source | Frequency |
|------|--------|-----------|
| BTC 5-min OHLCV with volume | Exchange API (Binance/Coinbase) | Real-time |
| Contract mid-price | Polymarket CLOB | Already available |
| OBV calculation | pandas or numpy | Computed at prediction time |

```python
import numpy as np

def obv_filter(direction, contract_price, btc_closes, btc_volumes, lookback=14):
    """Returns True if bet should proceed, False to skip."""
    if contract_price < 0.50 or contract_price > 0.70:
        return True  # bypass for other buckets

    # Calculate OBV
    obv = [0]
    for i in range(1, len(btc_closes)):
        if btc_closes[i] > btc_closes[i-1]:
            obv.append(obv[-1] + btc_volumes[i])
        elif btc_closes[i] < btc_closes[i-1]:
            obv.append(obv[-1] - btc_volumes[i])
        else:
            obv.append(obv[-1])

    # OBV slope over lookback
    recent_obv = obv[-lookback:]
    x = np.arange(lookback)
    slope = np.polyfit(x, recent_obv, 1)[0]

    # Normalize slope by std dev
    rolling_std = np.std(recent_obv)
    if rolling_std == 0:
        return False  # no movement = no conviction

    normalized_slope = slope / rolling_std

    if normalized_slope > 0.5 and direction == "UP":
        return True
    if normalized_slope < -0.5 and direction == "DOWN":
        return True
    return False
```

---

## Risks

| Risk | Mitigation |
|------|-----------|
| BTC volume doesn't reflect Polymarket contract flow | Long-term: use CLOB order flow data. Short-term: BTC volume is a reasonable proxy for crypto binary contracts |
| Filter too aggressive — skips profitable bets | Shadow mode first. Tune threshold (0.5 std dev) based on results. Can loosen to 0.3 |
| Reduces bet count further (already declining) | Only applies to one bucket. Other buckets unaffected. Quality > quantity |
| OBV lags in fast reversals | Acceptable — the filter's job is to catch sustained moves, not reversals. Mean-reversion is handled by the VWAP spec |

---

## Validation Plan

```
name: obv_bucket_filter
type: shadow comparison
method:
  - On every 0.50-0.70 bet, log OBV state and filter decision
  - Track: bets that would be filtered vs bets that pass
  - Compare WR and P&L of filtered-out bets vs kept bets
threshold: 50 bets in the 0.50-0.70 bucket
success_criteria:
  - Filtered-out bets have WR < 55% (i.e., the filter is removing bad bets)
  - Kept bets have WR > 70% (i.e., remaining bets are high quality)
baseline: current 0.50-0.70 bucket WR (~67% aggregate)
```

---

## Decision

Add `obv_bucket_filter` to the decision alerts tracker in `docs/core/decisions.md`. Start shadow logging alongside RSI gate. Review at 50 bets in the 0.50–0.70 bucket.
