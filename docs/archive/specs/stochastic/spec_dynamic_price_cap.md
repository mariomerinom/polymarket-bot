# Spec: Dynamic Price Cap — Volume & Depth Aware

> **Status:** REDUNDANT — Merged into spec_fill_adverse_selection.md

**Status:** Proposed
**Pipeline:** All live pipelines (BTC 5m, ETH 5m)
**Problem:** Static 7¢ price cap (`MAX_SLIPPAGE_SPREAD` 5¢ + `FILL_PRIORITY_SPREAD` 2¢) causes orders to expire or partially fill when the estimate is far above market price. The cap is the same whether the book is deep with $100k volume or paper-thin. In thick markets we leave money on the table. In thin markets we're arguably too aggressive.
**Goal:** Replace the static slippage spread with a dynamic value that widens in thick/liquid markets and tightens in thin ones, using data already flowing through the order path.

---

## Evidence

| Order | Market | Estimate | Static Cap | Limit | Result |
|-------|--------|----------|-----------|-------|--------|
| 59 | 0.275 | 0.564 | 0.345 | 0.345 | Expired |
| 60 | ~0.47 | ~0.55 | 0.54 | 0.475 | Expired (would have won) |
| 56 | 0.435 | 0.593 | 0.505 | 0.505 | Expired |
| 61 | ~0.55 | ~0.56 | 0.62 | 0.555 | Filled — won $45 |

Orders only fill when estimate is close to market. When the model has a strong signal (estimate >> market), the cap prevents crossing the spread. Reconciliation data: 53% fill rate, 8/8 expired orders were winners, $165 missed profit (2026-04-02).

An $8 loss on a $25 bet (partial fill) further shows that thin-book pricing isn't calibrated — the order size exceeded what the book could absorb at the limit price.

---

## How It Works

### Current (Static)

```
price_limit = min(estimate + 0.02, market + 0.05 + 0.02)
                                    ^^^^^^^^^^^^^^^^^^^^
                                    always 7¢, regardless of book
```

### Proposed (Dynamic)

```
slippage_spread = compute_dynamic_slippage(liquidity, volume, bet_size)
price_limit = min(estimate + 0.02, market + slippage_spread + 0.02)
                                    ^^^^^^^^^^^^^^^^^^^^^^^^
                                    3¢ to 15¢, based on book conditions
```

### The Formula

Three additive signals on a conservative base:

```
BASE    = 0.03  (3¢ floor — tighter than current 5¢ for thin markets)
CEILING = 0.15  (15¢ hard cap — safety valve)

depth_bonus  = min(max_bet_2pct / bet_size, 4) / 4 × 0.06    → 0 to 6¢
spread_bonus = max(0, 1 - spread_pct / 5) × 0.03              → 0 to 3¢
volume_bonus = min(volume / 50000, 1) × 0.03                   → 0 to 3¢

dynamic_slippage = clamp(BASE + depth_bonus + spread_bonus + volume_bonus, BASE, CEILING)
```

| Signal | What It Measures | Max Bonus | Saturates At |
|--------|-----------------|-----------|-------------|
| Depth | How many $25 bets fit in 2% slippage depth | 6¢ | 4× bet size ($100) |
| Spread | Bid-ask tightness (inverted: tight = liquid) | 3¢ | 0% spread |
| Volume | 24h market trading volume | 3¢ | $50k volume |

### Fallback

If no liquidity data available → returns current `MAX_SLIPPAGE_SPREAD` (5¢). Zero regression.

---

## Worked Examples

### Thick market ($50k vol, depth 4×, 1% spread)
```
depth_bonus  = 4/4 × 0.06 = 0.06
spread_bonus = (1 - 0.01/5) × 0.03 = 0.029
volume_bonus = 1.0 × 0.03 = 0.03
dynamic = 0.03 + 0.06 + 0.029 + 0.03 = 0.149 → 0.15 (ceiling)
```
Cap: market + 0.17 — crosses spread easily, fills.

### Thin market (low vol, depth 0.5×, 4% spread)
```
depth_bonus  = 0.5/4 × 0.06 = 0.0075
spread_bonus = (1 - 4/5) × 0.03 = 0.006
volume_bonus = 0.1 × 0.03 = 0.003
dynamic = 0.03 + 0.0075 + 0.006 + 0.003 = 0.047 → 0.047
```
Cap: market + 0.067 — tighter than current 7¢, protects against slippage.

### Order 60 replay (moderate depth)
```
Market 0.47, estimate 0.55. Assume depth 2×, spread 2%, vol $20k:
depth_bonus  = 2/4 × 0.06 = 0.03
spread_bonus = (1 - 0.4) × 0.03 = 0.018
volume_bonus = 0.4 × 0.03 = 0.012
dynamic = 0.03 + 0.03 + 0.018 + 0.012 = 0.09

Cap: 0.47 + 0.09 + 0.02 = 0.58
price_limit = min(0.55 + 0.02, 0.58) = 0.57
```
Would have filled. Currently expired at 0.475.

---

## Data Already Available

| Data | Source | At Order Time? |
|------|--------|---------------|
| `max_bet_2pct` | `liquidity` dict (via reasoning JSON) | Yes |
| `spread_pct` | `liquidity` dict | Yes |
| `depth_levels` | `liquidity` dict | Yes |
| `volume` | `markets` table | **No** — needs to be added to SQL query |

The only new data pipe is adding `m.volume` to the `execute_trades()` query and passing it through to `compute_order()`.

---

## Implementation

### Files

| File | Change |
|------|--------|
| `src/config.py` | Add 8 dynamic slippage constants (base, ceiling, bonuses, thresholds) |
| `src/trade.py` | Add `compute_dynamic_slippage()`, modify `compute_order()` signature + price logic, modify `execute_trades()` SQL query + logging |
| `tests/test_trade.py` | Add ~10 new tests for dynamic slippage |

### Key Design Decisions

- **Base tighter than current**: 3¢ vs 5¢ for thin markets — protects more in illiquid books
- **Ceiling at 15¢**: Even in the thickest market, never overpay more than 17¢ above market (15¢ + 2¢ fill priority)
- **All signals clamped**: Garbage data cannot produce negative or infinite slippage
- **Env-overridable bounds**: `DYNAMIC_SLIPPAGE_BASE` and `DYNAMIC_SLIPPAGE_CEILING` tunable at runtime
- **Size computation moves before price**: Required because depth_ratio depends on bet_size

---

## Validation

### Before shipping
- Snapshot current fill rate, expired-would-win count, slippage cost over last 50 bets

### Revert criteria
- Fill rate drops below 50% over 50 bets (currently ~53%)
- Average slippage cost increases by more than 3¢ per bet
- Any order fills at > 20¢ above market mid

### Success criteria
- Fill rate improves to > 70% over 50 bets
- expired_would_win count decreases
- No increase in average slippage cost per filled bet

### Counterfactual
- Log what the static cap would have produced alongside the dynamic cap, so we can compare without risk
