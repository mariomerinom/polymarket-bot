# Spec: RSI Conviction Gate

> **Status:** STILL RELEVANT — RSI computed by TA engine but not used as conviction gate

**Status:** Proposed
**Pipeline:** 5-minute
**Problem:** conv=4/5 performance is regime-dependent. 50% WR and -$60.79 on Mar 27, then 75% WR and +$1,935 on Mar 28. No mechanism currently distinguishes good conv=4 conditions from bad ones.
**Goal:** Use RSI as a pre-bet filter to downgrade or block high-conviction bets when the indicator conflicts with the predicted direction.

---

## How It Works

Before placing any bet with conv ≥ 4, check the RSI of the underlying contract (or BTC if the contract tracks BTC price movement). If RSI conflicts with the predicted direction, downgrade conviction.

```
INPUT:  prediction direction (UP/DOWN), conviction level, RSI(14) value
OUTPUT: adjusted conviction level
```

### Rules

| Prediction | RSI | Action | Rationale |
|-----------|-----|--------|-----------|
| UP | > 70 | conv → max(conv-2, 3) | Overbought — crowd already long, upside priced in |
| UP | 30–70 | no change | Neutral — let model's conviction stand |
| UP | < 30 | conv → min(conv+1, 5) | Oversold — contrarian UP has strong edge |
| DOWN | < 30 | conv → max(conv-2, 3) | Oversold — crowd already short, downside priced in |
| DOWN | 30–70 | no change | Neutral — let model's conviction stand |
| DOWN | > 70 | conv → min(conv+1, 5) | Overbought — contrarian DOWN has strong edge |

The key insight: RSI doesn't change direction, it changes sizing. The model still decides UP or DOWN. RSI only modulates how much to risk.

### RSI Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Period | 14 | Standard. On 5-min candles this = 70 minutes of lookback |
| Overbought threshold | 70 | Standard |
| Oversold threshold | 30 | Standard |
| Source | Contract mid-price or BTC spot | Depends on data availability |

If contract-level OHLCV isn't available, use BTC 5-min candles as proxy. Most Polymarket crypto contracts correlate heavily with BTC spot.

---

## Integration Point

```
existing flow:
  prediction → conviction scorer → bet placer

new flow:
  prediction → conviction scorer → RSI gate → bet placer
```

The gate sits between scoring and execution. It only modifies conviction (and therefore bet size). It never changes direction or generates new signals.

---

## Expected Impact

Based on the Mar 25–29 data:

**Mar 27 (BTC dropping, HIGH_VOL):** The model bet UP 16 times at 50% WR (-$118). BTC was declining from $69.4K → $66.6K. RSI on BTC 5-min would likely have been < 30 for extended periods. An UP bet with RSI < 30 = *agreement* (oversold, bounce expected) so no downgrade. But if RSI was in the 40–50 range (not oversold, just drifting down), UP bets would pass through unchanged — and that's where the losses came from. The gate would have limited help here.

**Where it helps most:** When the model predicts UP with high conviction but the market is already overbought (RSI > 70). This is the "FOMO entry" scenario — the crowd is already long, the contract is priced up, and a conv=4 $200 bet into that is high risk. Downgrading to conv=3 ($75) or conv=2 ($0) prevents oversized bets at the worst time.

**Conservative estimate:** If the gate prevents 2–3 bad conv=4 bets per day ($200 each), that's $400–600 in reduced exposure on losing days. At ~50% WR on those filtered bets, that's ~$200–300/day in saved losses.

---

## Validation Plan

Run as a decision alert alongside existing optimizations:

```
name: rsi_conviction_gate
type: A/B shadow
method:
  - Log what conviction WOULD have been after RSI adjustment
  - Compare adjusted vs original on resolved bets
threshold: 50 bets
success_criteria:
  - Adjusted WR > original WR by ≥ 3pp
  - OR adjusted P&L > original P&L (same bets, different sizing)
baseline: current pipeline WR (67.4% as of Mar 29)
```

Shadow mode means no actual bet changes — just logging the adjustment and tracking what would have happened. This fits the existing decision alert framework (like direction_regime_filter at 24/50 bets).

---

## Data Requirements

| Data | Source | Frequency |
|------|--------|-----------|
| BTC 5-min OHLCV | Exchange API (Binance/Coinbase) | Real-time |
| Contract mid-price | Polymarket CLOB | Already available (new liquidity section) |
| RSI calculation | talib or pandas_ta | Computed at prediction time |

If you already pull BTC price for regime detection, RSI is a ~5 line addition:

```python
import pandas_ta as ta

def rsi_gate(direction, conviction, btc_closes):
    rsi = ta.rsi(btc_closes, length=14).iloc[-1]

    if direction == "UP" and rsi > 70:
        return max(conviction - 2, 3)
    if direction == "DOWN" and rsi < 30:
        return max(conviction - 2, 3)
    if direction == "UP" and rsi < 30:
        return min(conviction + 1, 5)
    if direction == "DOWN" and rsi > 70:
        return min(conviction + 1, 5)
    return conviction
```

---

## Risks

| Risk | Mitigation |
|------|-----------|
| RSI whipsaws in trending markets | Only modifies sizing, never blocks bets entirely. Worst case = slightly smaller bets on winners |
| RSI period too slow for 5-min contracts | Test period=7 (35 min lookback) as alternative. Add as a parameter to shadow test |
| BTC RSI doesn't reflect contract-level dynamics | Long-term: compute RSI on contract mid-price from CLOB data. Short-term: BTC proxy is sufficient for crypto contracts |
| Reduces profitable conv=4/5 volume | The gate boosts conviction too (RSI confirms direction). Net effect should be positive — fewer bad big bets, more good big bets |

---

## Decision

Add `rsi_conviction_gate` to the decision alerts tracker in `docs/core/decisions.md`. Start shadow logging immediately. Review at 50 bets.
