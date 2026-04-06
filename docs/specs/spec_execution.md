# Execution Layer — Acceptance Criteria (v2)

**Status:** Ready for implementation
**Supersedes:** Original spec_execution.md
**Problem:** Adverse selection on the CLOB. Filled orders: 5W-9L (35.7% WR). Unfilled orders: 34W-3L (91.9% WR). Signal picks winners at 76.5% — execution destroys the edge. Every passive limit order that sits in the book self-selects for losers.
**Root cause:** GTC limit orders only fill when the market moves against the prediction.
**Design principle:** Never rest an order passively. Either take liquidity now or don't trade.

---

## Phase 1: Minimum Viable Fix (Ship First)

Phase 1 is the only thing that gets built initially. Phases 2 and 3 are layered on after Phase 1 validates.

### 1) Order Classification

**AC-1.1** Each signal MUST compute:

| Field | Definition |
|-------|-----------|
| `p` | Model probability (0-1) |
| `m` | Mid price: `(best_bid + best_ask) / 2` |
| `b` | Best bid |
| `a` | Best ask |
| `spread` | `a - b` |
| `edge` | See AC-1.2 |

**AC-1.2** Edge MUST be computed relative to execution cost, not mid:

```
For BUY (predicting UP):   edge = p - a
For SELL (predicting DOWN): edge = b - (1 - p)
```

Rationale: `edge = p - m` (original spec) overstates edge by ignoring the spread you'll pay. A signal with `p = 0.55` and `a = 0.54` has real edge of 0.01, not 0.05. Computing edge against the actual execution price prevents entering trades where spread eats the entire edge.

**AC-1.3** Edge thresholds MUST be asset-specific:

| Asset | Avg Spread | Min Edge (TAKE) | Min Edge (SKIP) |
|-------|-----------|-----------------|-----------------|
| BTC | ~2% | `spread + 0.02` (~0.04) | Below min = skip |
| ETH | ~4.5% | `spread + 0.02` (~0.065) | Below min = skip |

Formula: `min_edge = spread + 0.02`. The 2% buffer above spread ensures positive expected value after execution costs.

### 2) Order Decision: Take or Skip

**AC-2.1** IF `edge >= min_edge` THEN system MUST place a FOK (Fill-Or-Kill) order at the best ask (for BUY) or best bid (for SELL).

**AC-2.2** IF `edge < min_edge` THEN system MUST skip the trade. No order placed.

**AC-2.3** System MUST NOT place GTC or GTD orders. No resting orders. No passive entries.

**AC-2.4** System MUST NOT implement repricing ladders, escalation timers, or delayed chase in Phase 1.

Rationale: The data is unambiguous — passive orders cause adverse selection. The graduated approach (passive → hybrid → taker) optimizes for fill rate at the cost of fill quality. With 76.5% signal WR and ~2% spread, every FOK fill above min_edge is +EV. Simplicity is the feature.

### 3) Order Type Mapping

**AC-3.1** All orders in Phase 1 MUST use `OrderType.FOK` via `MarketOrderArgs` in py-clob-client.

**AC-3.2** IF the FOK order fails to fill (insufficient book depth at the price), system MUST NOT retry or fall back to GTC. The trade is skipped. Log it as `fok_rejected`.

**AC-3.3** IF FOK rejection rate exceeds 30% over a rolling 50-order window, system MUST alert for investigation (likely a book depth or pricing issue).

Rationale: FOK guarantees immediate execution or nothing. No partial fills resting in the book. No adverse selection. The trade-off is paying spread — but spread cost (~$0.50 on a $25 bet) is trivial compared to missed winners (~$165/day).

### 4) Position Sizing

**AC-4.1** All FOK orders MUST use base bet size ($25).

**AC-4.2** No size reduction for taker orders. The original spec's 80% TAKER sizing was designed to offset spread cost, but at $25 bets the spread cost is ~$0.50. The 20% reduction ($5) exceeds the spread cost and over-penalizes.

**AC-4.3** Position sizing MUST respect the existing circuit breaker ($300 max daily drawdown).

### 5) Order Lifetime

**AC-5.1** FOK orders have no lifetime management. They fill instantly or cancel. No timers needed.

**AC-5.2** System MUST NOT implement order lifetime, repricing, or re-entry logic in Phase 1.

### 6) Logging

**AC-6.1** System MUST log for every signal (whether traded or skipped):

| Field | Description |
|-------|-------------|
| `signal_direction` | UP or DOWN |
| `p` | Model probability |
| `m` | Mid price at signal time |
| `a` | Best ask at signal time |
| `b` | Best bid at signal time |
| `spread` | Spread at signal time |
| `edge` | Computed edge (against execution price, per AC-1.2) |
| `action` | `fok_filled`, `fok_rejected`, `skipped_low_edge` |
| `fill_price` | Actual fill price (if filled) |
| `slippage` | `fill_price - a` (if filled) |
| `outcome` | W or L (after contract resolves) |

**AC-6.2** System MUST log the anti-adverse-selection metrics daily:

```
filled_wr       = wins / (wins + losses) on filled orders
skipped_wr      = wins / (wins + losses) on skipped orders (hypothetical)
fok_rejected_wr = wins / (wins + losses) on rejected FOK orders (hypothetical)
missed_edge     = sum(edge) on skipped + rejected orders that would have won
captured_edge   = sum(edge) on filled orders
```

**AC-6.3** IF `filled_wr < skipped_wr - 0.10` over a rolling 50-order window THEN system MUST alert. This means adverse selection is recurring.

### 7) Success Criteria

**AC-7.1** Fill rate on submitted FOK orders MUST be ≥ 80%.

**AC-7.2** Win rate on filled orders MUST be ≥ 65%.

**AC-7.3** `filled_wr` and `skipped_wr` MUST converge to within 10 percentage points.

**AC-7.4** Daily `missed_edge` MUST decrease relative to pre-Phase-1 baseline.

**AC-7.5** Validation threshold: 50 filled FOK orders before declaring Phase 1 success or failure.

---

## Phase 2: Hybrid Execution (After Phase 1 Validates)

Phase 2 adds the graduated approach from the original spec, but ONLY for medium-edge signals that Phase 1 skips. It does NOT replace Phase 1's FOK logic for strong signals.

**Prerequisite:** Phase 1 passes all success criteria at 50+ orders.

### 8) Hybrid Regime for Medium Edge

**AC-8.1** Redefine edge bands:

| Band | Condition | Action |
|------|-----------|--------|
| Strong | `edge >= min_edge` | FOK (unchanged from Phase 1) |
| Medium | `spread <= edge < min_edge` | Hybrid execution (new) |
| Weak | `edge < spread` | Skip (unchanged) |

**AC-8.2** Hybrid execution flow:

```
T+0s:   Place FAK (Fill-And-Kill) order at mid price
         FAK fills what's available, cancels remainder immediately
         IF fully filled → done
         IF partially filled → log partial, done (do NOT rest remainder)
         IF nothing filled → start escalation timer

T+10s:  IF unfilled, recompute edge with latest data
         IF edge >= min_edge → escalate to FOK at best ask
         IF edge < spread → cancel, skip
         ELSE → place new FAK at mid + 0.25 * spread

T+20s:  IF still unfilled → escalate to FOK at best ask (force fill)

T+20s+: No further action. Either filled or skipped.
```

**AC-8.3** Maximum hybrid lifetime MUST be 20 seconds, not 60. The original spec's 60-second lifetime with 30-second cross is too slow. With WebSocket price feeds, 20 seconds is more than enough to determine if a fill is achievable.

**AC-8.4** At each escalation step, system MUST recompute edge. IF the signal has weakened (edge dropped below `spread`), system MUST cancel and skip — not escalate into a stale signal.

**AC-8.5** System MUST NOT use GTC at any point in the hybrid flow. FAK for initial entry, FOK for escalation. No resting orders.

### 9) Partial Fill Handling

**AC-9.1** IF a FAK order partially fills, system MUST treat the partial fill as a completed trade. Do NOT attempt to fill the remainder.

**AC-9.2** Log partial fills separately: `fak_partial` with `filled_pct` and `filled_size`.

Rationale: Attempting to fill the remainder reintroduces adverse selection on the leftover. Take what the book gives you and move on.

---

## Phase 3: Real-Time Monitoring (After Phase 2 Validates)

Phase 3 adds WebSocket-powered real-time features. These require the async monitoring infrastructure built on April 5.

**Prerequisite:** Phase 2 passes all success criteria. WebSocket feed to Polymarket CLOB is stable (0 reconnects/day for 7 consecutive days).

### 10) "Don't Miss the Move" Rule

**AC-10.1** IF a signal was skipped (edge < min_edge) AND within 30 seconds the contract price moves ≥ 0.5% in the predicted direction THEN system MUST:

1. Recompute edge with current data
2. IF new edge >= min_edge → place FOK
3. IF new edge < min_edge → log as `move_detected_no_entry` and do nothing

**AC-10.2** The 0.5% threshold (not 1.0% from original spec) reflects 5-minute binary contract dynamics where 1% is already a large move that erodes entry edge.

**AC-10.3** This rule MUST only fire once per signal. No repeated re-entries.

**AC-10.4** Implementation requires: WebSocket price subscription per active contract, async event handler that fires on threshold breach, edge recomputation with fresh order book snapshot.

### 11) Signal Cancellation

**AC-11.1** IF a FAK/hybrid order is pending AND the model signal reverses or weakens below `spread` THEN system MUST immediately cancel the pending order.

**AC-11.2** Signal reversal is detected via WebSocket candle updates. IF a new candle breaks the streak that triggered the signal, the signal is stale.

**AC-11.3** Implementation requires: signal validity subscription that monitors the underlying streak/pattern during order lifetime.

### 12) Adverse Selection Circuit Breaker

**AC-12.1** System MUST maintain a rolling 20-order window comparing filled WR to overall signal WR.

**AC-12.2** IF `filled_wr < signal_wr - 0.15` over the 20-order window THEN system MUST:

1. Pause all trading for 30 minutes
2. Alert operator
3. Log `adverse_selection_breaker_triggered`

**AC-12.3** After pause, system MUST resume with tightened min_edge (`spread + 0.04` instead of `spread + 0.02`) for the next 50 orders. IF filled WR recovers, revert to standard min_edge.

Rationale: This is the enforcement mechanism missing from the original spec's AC-7.1. "MUST NOT allow adverse selection" needs a concrete action, not just logging.

---

---

## Implementation Order

```
Phase 1:  Phase 1 — FOK or skip. Deploy. Validate on 50 fills.
Phase 2:  Assess. If Phase 1 passes → begin Phase 2. If fails → diagnose.
Phase 3:  Phase 2 — Add hybrid FAK for medium-edge band. Validate on 50 fills.
Phase 4:  Phase 3 — Add WebSocket-powered monitoring, "Don't Miss the Move", circuit breaker.
```

**The first deploy is ~30 lines of code:** Replace `OrderType.GTC` + `OrderArgs` with `OrderType.FOK` + `MarketOrderArgs`, add the edge computation against execution price, and set the min_edge threshold. Everything else comes later.
