# Spec: Stochastic Entry Timing

> **Status:** STILL RELEVANT — Deferred; toxic flow was root cause, not entry timing

**Status:** Proposed
**Pipeline:** 5-minute (execution layer, applies to all bets)
**Problem:** The pipeline currently executes bets immediately when a signal fires. On Polymarket's CLOB, timing matters — entering at a bad moment within a 5-min window costs spread and slippage. The Mar 29 liquidity data showed 1.44% avg spread and 0.97% slippage at $200. With average bet size now at $219 (up from $84), execution cost is a growing concern as Part 6 (live paper trading) approaches.
**Goal:** Use the Stochastic Oscillator to time the exact entry within the execution window, reducing effective spread and slippage by entering at short-term price extremes.

---

## How It Works

The Stochastic Oscillator (%K and %D) measures where the current price sits relative to its recent range. It's faster than RSI — it reacts to intra-candle price swings, making it ideal for timing entries within a narrow window.

The key insight: **Stochastic doesn't decide what to bet or how much. It decides when to execute.**

The model has already decided direction, conviction, and sizing. RSI has gated conviction. OBV has confirmed volume. The bet is ready. Stochastic's job is to wait for the best fill within a short execution window.

```
INPUT:  confirmed bet (direction, conviction, size), stochastic %K, %D
OUTPUT: execute now / wait / cancel (if window expires)
```

### Entry Logic

**For UP bets (buying YES contracts):**

| Stochastic State | Action | Rationale |
|-----------------|--------|-----------|
| %K < 20 (oversold) | Execute immediately | Price is at short-term low — best fill for a long entry |
| %K < 20 and %K crosses above %D | Execute immediately (priority) | Oversold AND turning up — optimal entry |
| %K 20–80 and falling | Wait | Price still declining — better entry coming |
| %K 20–80 and rising | Execute | Price turning — acceptable entry |
| %K > 80 (overbought) | Execute with caution | Worst timing for a long entry, but don't miss the trade |

**For DOWN bets (buying NO contracts):**

| Stochastic State | Action | Rationale |
|-----------------|--------|-----------|
| %K > 80 (overbought) | Execute immediately | Price at short-term high — best fill for a short entry |
| %K > 80 and %K crosses below %D | Execute immediately (priority) | Overbought AND turning down — optimal entry |
| %K 20–80 and rising | Wait | Price still rising — better entry coming |
| %K 20–80 and falling | Execute | Price turning — acceptable entry |
| %K < 20 (oversold) | Execute with caution | Worst timing for a short entry, but don't miss the trade |

### Execution Window

The timing logic operates within a bounded window. If the optimal condition isn't met within the window, the bet executes anyway — missing a trade entirely is worse than a slightly suboptimal entry.

| Parameter | Value | Notes |
|-----------|-------|-------|
| Max wait time | 60 seconds | Don't hold a signal for more than 1 minute |
| Check interval | 5 seconds | Poll stochastic every 5 seconds within window |
| Force-execute threshold | 60 seconds | If window expires, execute at market |
| Cancel threshold | None | Never cancel a confirmed bet — always execute |

### Stochastic Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| %K period | 5 | Fast. On 1-min candles = 5 minutes of lookback |
| %D period (smoothing) | 3 | Standard |
| Candle timeframe | 1-minute | Faster than the 5-min pipeline candles — we need intra-signal granularity |
| Overbought | 80 | Standard |
| Oversold | 20 | Standard |

Note: The pipeline uses 5-min candles for signal generation, but Stochastic uses **1-min candles** for entry timing. This is intentional — timing requires finer granularity than signal detection.

---

## Integration Point

```
existing flow (with all filters):
  signal → RSI gate → OBV filter → bet placer (immediate execution)

new flow:
  signal → RSI gate → OBV filter → stochastic timer → bet placer (timed execution)
                                         ↑
                                   max 60s window
                                   1-min candle data
```

Stochastic is the **last step** before execution. It receives a fully confirmed, sized, filtered bet and optimizes the fill.

---

## Expected Impact

### Spread Savings

From Mar 29 CLOB data:
- Avg spread: 1.44%
- Avg bet size: $219

If Stochastic timing captures even 30% of the spread by entering at a better price:

```
Savings per bet:  $219 × 1.44% × 30% = $0.95
Daily savings:    $0.95 × 16 bets = $15.14
Monthly savings:  $15.14 × 30 = $454
```

This seems small, but it compounds. At higher volumes or larger bet sizes (conv=5 at $300), the savings scale proportionally.

### Slippage Reduction

Current slippage at $200: 0.97%. If Stochastic timing enters when the book is temporarily thicker (after a price extreme attracts limit orders):

```
Slippage reduction: 0.97% × 20% improvement = 0.19% saved
Per bet: $219 × 0.19% = $0.42
Daily: $0.42 × 16 = $6.72
```

### Combined Estimate

**$20–25/day in execution savings.** Not transformative, but this is pure edge preservation — it doesn't require better signals, just better fills. Over time it adds up to $600–750/month.

### Win Rate Impact

Beyond cost savings, better entry timing can marginally improve WR. Entering a UP bet at the bottom of a micro-dip (Stochastic < 20) gives more room for the trade to work vs. entering mid-range. Estimated impact: +1–2pp WR, difficult to measure precisely.

---

## Implementation

```python
import numpy as np
import time

def stochastic(highs, lows, closes, k_period=5, d_period=3):
    """Calculate Stochastic %K and %D."""
    lowest_low = np.array([min(lows[max(0,i-k_period+1):i+1]) for i in range(len(lows))])
    highest_high = np.array([max(highs[max(0,i-k_period+1):i+1]) for i in range(len(highs))])

    denom = highest_high - lowest_low
    denom[denom == 0] = 1  # avoid division by zero

    k = 100 * (closes - lowest_low) / denom

    # %D = SMA of %K
    d = np.convolve(k, np.ones(d_period)/d_period, mode='valid')
    d = np.pad(d, (d_period-1, 0), mode='edge')

    return k, d


def timed_entry(direction, btc_1m_highs, btc_1m_lows, btc_1m_closes,
                max_wait=60, check_interval=5):
    """
    Returns optimal execution timing within the window.
    In live mode, this polls every check_interval seconds.
    In backtest mode, iterates over 1-min candles within the window.
    """
    k, d = stochastic(btc_1m_highs, btc_1m_lows, btc_1m_closes)
    current_k = k[-1]
    current_d = d[-1]
    prev_k = k[-2] if len(k) > 1 else current_k
    crossover_up = prev_k < current_d and current_k > current_d
    crossover_down = prev_k > current_d and current_k < current_d

    if direction == "UP":
        # Best: oversold + crossover
        if current_k < 20 and crossover_up:
            return "EXECUTE_NOW", "optimal: oversold + K crossed above D"
        if current_k < 20:
            return "EXECUTE_NOW", "good: oversold"
        if current_k < 50 and crossover_up:
            return "EXECUTE_NOW", "acceptable: mid-range + turning up"
        if current_k > 80:
            return "EXECUTE_CAUTIOUS", "suboptimal: overbought entry for long"
        return "WAIT", f"K={current_k:.0f}, waiting for better entry"

    if direction == "DOWN":
        # Best: overbought + crossover
        if current_k > 80 and crossover_down:
            return "EXECUTE_NOW", "optimal: overbought + K crossed below D"
        if current_k > 80:
            return "EXECUTE_NOW", "good: overbought"
        if current_k > 50 and crossover_down:
            return "EXECUTE_NOW", "acceptable: mid-range + turning down"
        if current_k < 20:
            return "EXECUTE_CAUTIOUS", "suboptimal: oversold entry for short"
        return "WAIT", f"K={current_k:.0f}, waiting for better entry"
```

### Execution Loop (Live Mode)

```python
async def execute_with_timing(bet, max_wait=60):
    """Execute a confirmed bet with stochastic timing."""
    start = time.time()

    while time.time() - start < max_wait:
        candles_1m = await fetch_btc_1m_candles(lookback=10)
        action, reason = timed_entry(
            bet.direction,
            candles_1m.highs, candles_1m.lows, candles_1m.closes
        )

        if action == "EXECUTE_NOW":
            await place_order(bet)
            log_entry(bet, reason, wait_time=time.time()-start)
            return

        if action == "EXECUTE_CAUTIOUS":
            # Still execute, but log the suboptimal timing
            await place_order(bet)
            log_entry(bet, reason, wait_time=time.time()-start, cautious=True)
            return

        # WAIT — check again after interval
        await asyncio.sleep(5)

    # Window expired — force execute
    await place_order(bet)
    log_entry(bet, "forced: window expired", wait_time=max_wait, forced=True)
```

---

## Data Requirements

| Data | Source | Already Available? |
|------|--------|--------------------|
| BTC 1-min OHLCV | Exchange API (Binance/Coinbase) | New — need 1-min feed in addition to existing 5-min |
| Stochastic calculation | numpy | New — ~15 lines |
| Execution timestamps | Bet placer logs | Need to add timing metadata to bet logs |

The 1-min candle feed is the only new data requirement. All other specs use 5-min data.

---

## Interaction with Other Specs

| Spec | Relationship |
|------|-------------|
| RSI Gate | No interaction — RSI runs before Stochastic. RSI decides sizing, Stochastic decides timing |
| OBV Filter | No interaction — OBV decides whether to bet, Stochastic decides when |
| VWAP Mean-Reversion | **Complementary.** VWAP signals in MEAN_REVERTING regimes benefit the most from Stochastic timing. A mean-reversion bet entered at a Stochastic extreme has the highest probability of catching the actual turning point |

### Full Pipeline with All Four Specs

```
MEAN_REVERTING regime:
  VWAP signal → RSI gate → OBV filter (if 0.50-0.70) → stochastic timer → execute

Other regimes:
  existing model → RSI gate → OBV filter (if 0.50-0.70) → stochastic timer → execute
```

---

## Risks

| Risk | Mitigation |
|------|-----------|
| 60-second delay causes missed opportunities | Window is short. Force-execute at expiry. In backtesting, measure how many bets would have been better without the delay |
| 1-min candle data adds infrastructure complexity | Single additional websocket subscription. Minimal overhead |
| Stochastic whipsaws in choppy conditions | The window is bounded. Even with whipsaw, worst case = execute at 60s timeout (same as no timing) |
| Overoptimization of entry timing | Stochastic is the simplest timing tool. Not trying to predict micro-moves — just avoiding the worst entries within a 60s window |
| Backtest unreliable for execution timing | True — backtesting execution is always optimistic. Shadow mode in live environment is the real test. Log what timing would have done vs. immediate execution |

---

## Validation Plan

```
name: stochastic_entry_timing
type: dual logging (immediate + timed)
method:
  - On every bet, log two prices:
    1. Price at signal time (what immediate execution would get)
    2. Price at stochastic-timed execution (what the timer gets)
  - Compare effective fill prices
threshold: 100 bets (need larger sample for execution timing)
success_criteria:
  - Timed entries get better avg fill price than immediate entries
  - Improvement > 0.3% (meaningful after Polymarket spread)
  - No increase in missed trades or execution failures
baseline: immediate execution fill prices
```

---

## Priority and Sequencing

This spec is **lowest priority** of the four. The other three (RSI, OBV, VWAP) improve signal quality. Stochastic improves execution quality. Signal quality has a much larger impact at current volumes.

**Recommended implementation order:**
1. RSI Conviction Gate (HIGH — fixes conv=4 inconsistency)
2. OBV Bucket Filter (HIGH — fixes 0.50–0.70 bucket)
3. VWAP Mean-Reversion (MEDIUM — new edge source)
4. Stochastic Entry Timing (LOW — execution optimization, most relevant when Part 6 goes live)

Stochastic becomes higher priority once the pipeline is executing real orders in Part 6, where every basis point of fill improvement matters.

---

## Decision

Add `stochastic_entry_timing` to the decision alerts tracker in `docs/core/decisions.md`. Begin dual logging (immediate vs. timed price) when Part 6 paper trading starts. Not needed during the current shadow/simulation phase.
