# Fix Catastrophic Adverse Selection in Order Execution

The daily report correctly identified a massive P&L bleed: **11 expired orders would have won (100% WR), while filled orders took heavy losses (36% WR).** 

This is textbook **adverse selection (toxic flow)**. Your momentum signals are highly accurate, meaning when they trigger, the broader market also reacts quickly. By the time `src/trade.py` submits the order, the real-time liquidity has moved. 

## The Root Cause
In `src/trade.py -> compute_order()`, the limit price is artificially leashed to a stale `market_price` snapshot from the database:
```python
max_price = market_price_yes + MAX_SLIPPAGE_SPREAD + FILL_PRIORITY_SPREAD
price_limit = min(fill_adjusted, max_price)
```
Even if your algorithm generates a dynamic `estimate` of **0.80** (meaning an 80% Win Rate), `max_price` strictly caps the limit order at `market_price + 0.07`. If the market was at $0.50, your order is capped at **$0.57**. The real-time order book has already shifted to $0.60, so your order sits unfilled and expires. Conversely, if the signal is *wrong*, the price drops, and your $0.57 bid is eagerly taken by someone who knows it's dropping.

## Proposed Changes

> [!CAUTION]
> This will result in the bot mathematically paying more per share on average for winning trades. However, securing a win at $0.65 is infinitely better than taking an expiration at $0.57 while getting filled at $0.57 on losers. EV strictly increases.

### 1. `src/trade.py`
We will introduce **Dynamic Slippage Spreads** tied to your Conviction Tiers. Instead of a flat leashing metric, we will trust the high-conviction predictions:

#### [MODIFY] `src/trade.py`
Modify `compute_order(prediction_row, market_row, liquidity=None)` to scale the allowable spread based on the conviction score:

```python
    conviction = prediction_row.get("conviction_score", 3)
    
    # Scale max slippage: higher conviction = willing to heavily cross the spread
    # Conv 3: 5¢ (default)
    # Conv 4: 10¢ 
    # Conv 5: 15¢ 
    dynamic_max_slip = MAX_SLIPPAGE_SPREAD + (max(0, conviction - 3) * 0.05)
```
Then replace `MAX_SLIPPAGE_SPREAD` with `dynamic_max_slip` when calculating `max_price`:
```python
        max_price = market_price_yes + dynamic_max_slip + FILL_PRIORITY_SPREAD
```

## User Review Required
Does scaling the max slippage by 5 cents per conviction tier (allowing up to a 15-cent leash on Tier 5 bets) align with your risk tolerance? Given Tier 5 bets have a 76.7% win-rate, paying up to $0.65 for a market sitting at $0.50 mathematically retains strong positive EV, but I want your explicit approval before modifying the core trading math.

## Verification Plan
1. **Manual Output Verification:** Look at the terminal output logs for future executions. Orders should be logged passing wider limit calculations. 
2. **Slippage Analytics:** The daily report's "liquidity profile" and "fill rate" will instantly improve inside CLOB. The 0% fill-rate will climb, and the adverse selection gap will close.
