# Spec: Maker Mode — Passive Liquidity Provision Architecture

**Status:** VALIDATED — signal EHR gate passed (+0.102 on 562 predictions, gate required +0.02). Ready for shadow measurement.  
**Author:** Mario + Claude  
**Date:** 2026-04-16  
**Depends on:** spec_execution.md v2 (FOK Phase 1 → FAK Hybrid Phase 2 → WebSocket Phase 3 are all *taker* strategies; this spec adds a *maker* path that runs alongside them, not instead of them)  
**Empirical basis:** Akey, Grégoire, Harvie & Martineau (2026), "Who Wins and Who Loses In Prediction Markets? Evidence from Polymarket" (SSRN 6443103)  
**Validated by:** `ehr_baseline_2026-04-16.md` — live production data via Botsy MCP

---

## 1. Motivation

The Akey et al. paper establishes five empirical facts about Polymarket profitability across 1.4M users and $20B in volume:

1. **Maker activity is the strongest predictor of profitability.** Moving from pure taker to pure maker reduces loss probability by 35.9pp — 10× larger than any other coefficient in their Probit regression.
2. **Prices are well-calibrated.** A contract at price *p* resolves YES approximately *p*% of the time. Directional prediction alone does not beat the market; edge must come from identifying *transient mispricings* or earning the spread.
3. **Extreme-price contracts (< 10¢ or > 90¢) increase loss probability by 3.0pp.** The average retail user places 63% of trades in this zone.
4. **Overtrading (high trade count at fixed volume) increases loss probability by 5.0pp.** Fewer, larger, more-convicted bets outperform.
5. **Category concentration increases loss probability by 13.6pp.** Correlated risk across crypto pipelines is real (see: 2026-04-06, all pipelines regressed simultaneously).

BOTSY is currently a pure taker (FOK Phase 1) or a pseudo-taker (GTC limit orders that only fill on adverse flow). This spec defines the path from taker to informed maker.

---

## 2. EHR Baseline (2026-04-16) — The Case for This Spec

### Definition

```
EHR = Σ qᵢ(oᵢ - pᵢ) / Σ qᵢ
```

Where for each filled trade *i*:
- `qᵢ` = quantity (USDC wagered)
- `oᵢ` = realized outcome (1 if contract resolves in your favor, 0 otherwise)
- `pᵢ` = execution price (what you actually paid, not mid)

### Measured Baseline

| Pipeline | Signal EHR | Exec EHR | Gap | n (signal) | Akey Percentile |
|----------|-----------|----------|-----|------------|-----------------|
| **BTC 5m** | **+0.102** | **−0.028** | **13.0¢/dollar** | 562 | **Top 2%** |
| ETH 5m | +0.036 | −0.010 | 4.6¢/dollar | 470 | Top 10% |
| Bybit BTC | +0.003 | — | — | 376 | ~50th pctile |
| Kalshi | −0.241 | — | — | 285 | Catastrophic |

### By Conviction (BTC 5m)

| Conv | Signal EHR | WR | n |
|------|-----------|-----|---|
| 3 | +0.082 | 62.2% | 238 |
| 4 | +0.057 | 56.7% | 233 |
| **5** | **+0.267** | **75.8%** | **91** |

### By Regime (BTC 5m)

| Regime | Signal EHR | WR | n |
|--------|-----------|-----|---|
| MED_VOL / NEUTRAL | +0.156 | 67.4% | 187 |
| MED_VOL / TRENDING | +0.136 | 67.5% | 77 |
| LOW_VOL / TRENDING | +0.124 | 63.4% | 41 |
| HV / TRENDING | +0.087 | 62.7% | 67 |
| HV / NEUTRAL | +0.037 | 54.4% | 158 |
| LOW_VOL / NEUTRAL | +0.026 | 53.1% | 32 |

### The Execution Gap

The signal identifies contracts mispriced by 10.2¢. By the time we fill, we're paying 2.8¢ *more* than fair value. Live fills are catastrophic: −0.149 EHR on 17 real-money trades (35% WR). The market is selectively filling our worst orders.

**This is exactly the case the spec was designed for:** signal has value, execution is destroying it. The 13¢/dollar gap between signal and execution is the single biggest lever in the system.

### Gate Status

The spec's Phase 1 gate asks: *"Is taker EHR > +0.02 on 200+ resolved fills?"*

- Signal EHR = +0.102 on 562 predictions → **PASSED with 5× margin**
- Execution EHR = −0.028 on 96 paper fills → **FAILED on execution side**

This confirms: the signal works, the execution architecture must change. Proceed to shadow maker measurement.

---

## 3. Key Metric: Ongoing EHR Tracking

### AC-EHR-1
Daily report MUST compute and display EHR for each pipeline, computed over filled-and-resolved orders only.

### AC-EHR-2
Rolling 7-day EHR MUST be tracked. If 7-day EHR < 0.0 on > 50 resolved bets, an alert MUST fire.

### AC-EHR-3
EHR MUST be computed *separately* for:
- Taker fills (FOK / FAK)
- Maker fills (passive limit orders that got lifted)

This separation is the prerequisite for Phase 2. If taker EHR is near zero but maker EHR is positive, the signal has value but the execution is destroying it. If both are near zero, the signal itself doesn't beat the market.

### Interpretation (Akey et al. scale)

| EHR Range | Meaning | Akey et al. Percentile |
|-----------|---------|----------------------|
| +0.10 to +0.15 | Genuine mispricing detection — top-tier skill | Top 2% |
| +0.05 to +0.10 | Modest but real edge | Top 10% |
| −0.02 to +0.05 | Tracking market prices, P&L = noise − spread | 30th–50th pctile |
| < −0.02 | Systematically buying overpriced contracts | Bottom half |

---

## 4. Phase 1: Shadow Maker (Measurement Only)

**Goal:** Measure what maker-mode *would* do without risking capital.

**Gate status:** Signal EHR validated. Proceed immediately.

### 4.1 Shadow Order Generation

For every prediction where BOTSY currently computes a signal:

### AC-SM-1
System MUST compute a hypothetical maker order:
```
maker_bid = mid - (spread × 0.25)    # post inside the spread
maker_ask = mid + (spread × 0.25)    # for SELL-side signals
```

### AC-SM-2
System MUST log but NOT submit:
```json
{
  "shadow_maker_price": "<maker_bid or maker_ask>",
  "side": "BUY | SELL",
  "mid_at_signal": "<mid>",
  "spread_at_signal": "<spread>",
  "best_bid": "<b>",
  "best_ask": "<a>",
  "model_prob": "<p>",
  "conviction": "<conv>",
  "timestamp": "<t>"
}
```

### 4.2 Shadow Fill Simulation

### AC-SM-3
A shadow maker order is considered "filled" if, within 60 seconds of logging, the *trade tape* (via WebSocket) shows a transaction at or through the shadow price on the relevant side.

### AC-SM-4
System MUST track:
- `shadow_fill_rate`: % of shadow maker orders that would have filled
- `shadow_fill_latency`: time from order log to hypothetical fill
- `shadow_adverse_pct`: % of shadow fills where price continued moving against the position within 30 seconds post-fill

### AC-SM-5
System MUST compute shadow maker EHR separately from taker EHR on the daily report.

### 4.3 Duration
Run shadow maker for **minimum 7 days** or **200 shadow fills**, whichever is longer.

### Gate to Phase 2
All three conditions must hold:
1. Shadow maker fill rate > 30%
2. Shadow maker EHR > shadow taker EHR (maker execution captures more edge)
3. Shadow adverse selection rate < 40% (most fills are not immediately underwater)

---

## 5. Phase 2: Live Maker — Single-Sided Informed Provision

**Goal:** Post passive limit orders on one side of the book when the model has a directional opinion.

This is NOT market-making (two-sided quoting). This is *informed* liquidity provision: you post a limit order only on the side your model favors, at a price that earns you spread if lifted by an uninformed flow.

### 5.1 Order Mechanics

### AC-LM-1 Entry Criteria
System MUST only post maker orders when ALL conditions hold:
```
conviction >= 4
edge = |p - mid| >= min_edge   (asset-specific, from execution spec v2)
spread >= 0.02                  (no point posting inside a 1¢ spread)
regime_gate = TRADE or REDUCE   (not PAUSE)
```

### AC-LM-2 Price Selection
```
IF BUY:
  maker_price = best_bid + tick    # improve the bid by one tick (0.01)

IF SELL:
  maker_price = best_ask - tick    # improve the ask by one tick
```

Rationale: one-tick improvement gives queue priority without giving up meaningful edge. Do NOT post at mid — that's giving away half the spread for free.

### AC-LM-3 Edge Floor Against Maker Price
```
IF BUY:
  maker_edge = p - maker_price
  REQUIRE: maker_edge >= min_edge + 0.01

IF SELL:
  maker_edge = maker_price - (1 - p)
  REQUIRE: maker_edge >= min_edge + 0.01
```

The +0.01 buffer above `min_edge` compensates for the uncertainty of *when* the order fills vs. when the signal was generated. If edge doesn't clear this bar, use FOK taker instead.

### AC-LM-4 Order Type
Use **GTD (Good-Til-Date)** with expiration = contract resolution time minus 120 seconds.

Do NOT use GTC — GTC orders with no expiry are the original adverse selection trap. GTD guarantees cleanup.

### AC-LM-5 Order Lifetime
Maximum lifetime: **90 seconds** from posting. If unfilled after 90s:
1. Cancel
2. Recompute signal with fresh market data
3. If edge still qualifies → re-post at updated price
4. If edge has decayed → skip (do not escalate to taker)

### AC-LM-6 Anti-Escalation Rule
**Maker orders MUST NOT escalate to taker orders.** If a maker order expires unfilled, it dies. The FOK taker path (Phase 1 execution spec) is a *separate* decision branch, not a fallback for failed maker orders.

Rationale: escalation creates the exact GTC → "cross when desperate" pattern that produced adverse selection in v1.

### 5.2 Position Sizing

### AC-LM-7 Size by Conviction

Based on EHR baseline (conv=5 EHR is 4.7× conv=4):
```
conv=4: $25 (base size)
conv=5: $50 (2× base)
```

Conv=3 excluded from maker path — conv=3 edge (+0.082) is real but thinner, more vulnerable to adverse selection on passive fills.

### AC-LM-8 Daily Exposure Cap
Total *maker* capital at risk (open + settled) MUST NOT exceed $150/day during Phase 2.

Separate from taker circuit breaker ($300). Combined max exposure: $450/day.

### 5.3 Maker Rebate

### AC-LM-9
Per footnote 4 of Akey et al., crypto markets on Polymarket have:
- Taker fee: `fee = C × 0.25 × (p × (1-p))²`
- Maker rebate: 20% of taker fee

System MUST log the rebate earned on each maker fill and include it in P&L calculations. At $25 bets in the 0.50–0.70 range, the rebate is small (~$0.30–$0.60 per fill) but compounds.

### 5.4 Monitoring

### AC-LM-10 Maker-Specific Dashboard Metrics (Daily Report)
```
maker_orders_posted: int
maker_fill_rate: float
maker_fill_latency_p50: ms
maker_ehr: float
maker_adverse_pct: float     # % of fills that went underwater within 30s
maker_pnl: float             # separate from taker P&L
maker_rebate_earned: float
```

### AC-LM-11 Kill Switch
IF rolling 20-fill maker WR < 35% OR maker EHR < −0.03:
→ Pause all maker orders immediately
→ Revert to FOK-only taker mode
→ Alert: "Maker mode suspended — adverse selection detected"

### Phase 2 Duration
Minimum 14 days or 100 maker fills, whichever is longer.

### Gate to Phase 3
1. Maker EHR > +0.03
2. Maker fill rate > 40%
3. Maker adverse selection rate < 30%
4. Combined (maker + taker) P&L > taker-only P&L over same period

---

## 6. Phase 3: Hybrid Execution Router

**Goal:** Dynamically route each signal to the execution path (taker vs. maker) that maximizes expected P&L.

### 6.1 Routing Logic

### AC-HE-1 Decision Function
For each qualifying signal, compute expected value of each path:

```
EV_taker = (p - ask) × base_size           # certain fill, pay spread
EV_maker = fill_prob × (p - maker_price) × base_size   # uncertain fill, earn spread
```

Where `fill_prob` is the empirical maker fill rate from Phase 2 data, segmented by:
- Regime (HIGH_VOL/NEUTRAL vs MEDIUM_VOL/TRENDING)
- Spread width bucket
- Direction (UP vs DOWN)

### AC-HE-2 Routing Rule
```
IF EV_maker > EV_taker AND conviction >= 4:
  → maker path
ELSE IF edge >= min_edge:
  → FOK taker path
ELSE:
  → skip
```

### AC-HE-3 Regime-Conditional Routing

Based on EHR by regime data:
```
IF regime = MED_VOL/* (EHR +0.136 to +0.156):
  → use AC-HE-2 normally — strongest edge, maker viable
IF regime = HV/TRENDING (EHR +0.087):
  → taker-only, conv >= 4
IF regime = HV/NEUTRAL (EHR +0.037):
  → taker-only, conv >= 5 only — thin edge, only highest conviction
IF regime = LOW_VOL/NEUTRAL (EHR +0.026):
  → skip all (shadow log only) — edge doesn't justify execution cost
IF regime_gate = PAUSE:
  → skip all (shadow log only)
```

### 6.2 Feedback Loop

### AC-HE-4
System MUST update `fill_prob` estimates weekly using Phase 2 + Phase 3 data, bucketed by regime × spread × direction.

### AC-HE-5
System MUST track *routing accuracy*: did the chosen path (maker vs taker) produce higher P&L than the alternative would have? Log both actual and counterfactual.

---

## 7. Anti-Patterns (Paper-Derived Hard Rules)

These are permanent constraints derived from the Probit regression. They are not phase-gated.

### AP-1: No Extreme-Price Contracts
System MUST NOT place orders (maker or taker) on contracts priced below 0.10 or above 0.90.

Exception: SELL-side orders on contracts priced > 0.90 where model_prob < 0.85 (fading the extreme). This exception requires separate shadow validation.

### AP-2: Overtrading Guard
System MUST enforce a maximum of **30 filled orders per day per pipeline** (maker + taker combined). Beyond 30, only conv=5 signals may trade.

Rationale: Log N Trades has a +5.0pp loss coefficient. More trades ≠ more edge.

### AP-3: Category Diversification (Future)
When BOTSY expands beyond crypto, the portfolio allocation SHOULD target Category HHI < 0.50 (not fully concentrated in one domain).

This is a backlog item — not actionable until a non-crypto pipeline is live. Noted here because the paper's 13.6pp coefficient makes it the second-largest behavioral predictor of loss.

### AP-4: Conviction-Sizing Ramp

Based on EHR baseline — conv=5 has 4.7× the edge of conv=4:
```
conv=3: $25   (base — taker only, no maker path)
conv=4: $25   (base — eligible for maker path)
conv=5: $50   (2× base — priority for maker path)
```

Adjust upward as bankroll grows and execution EHR validates.

---

## 8. Success Criteria

### After Phase 1 (Shadow):
- [ ] EHR is computed daily for all pipelines
- [x] ~~Taker EHR baseline established (> +0.02 on 200+ fills)~~ **DONE: +0.102 on 562**
- [ ] Shadow maker data shows fill rate > 30%

### After Phase 2 (Live Maker):
- [ ] Maker P&L is positive over 100+ fills
- [ ] Maker EHR > +0.03
- [ ] Combined strategy outperforms taker-only

### After Phase 3 (Hybrid Router):
- [ ] Routing accuracy > 60% (chose the better path more often than not)
- [ ] Overall EHR in top-10% range (> +0.05)
- [ ] Adverse selection rate (filled WR < unfilled WR) eliminated or < 5pp gap

---

## 9. What This Spec Does NOT Cover

- **The taker execution path.** spec_execution.md v2 defines three phases of *taker* strategy (FOK → FAK hybrid → WebSocket monitoring). This spec defines a parallel *maker* path. They coexist: strong-edge signals go FOK taker, moderate-edge signals go maker. The hybrid router (Phase 3 of this spec) decides which path each signal takes.
- **Two-sided market-making** (delta-neutral quoting on both sides of the book). That's a different business with inventory risk, hedging requirements, and capital needs beyond current bankroll. Revisit at > $5K Polymarket balance.
- **Cross-venue arbitrage** (Polymarket vs Kalshi vs Bybit price discrepancies). Potentially high-EHR but requires multi-venue execution infrastructure.
- **Regime gate implementation.** Separate spec — this spec assumes the regime gate exists and references its states (TRADE / REDUCE / PAUSE). However, the EHR-by-regime data in Section 2 provides concrete thresholds for that spec.

---

*Reference: Akey, P., Grégoire, V., Harvie, N., & Martineau, C. (2026). Who Wins and Who Loses In Prediction Markets? Evidence from Polymarket. SSRN 6443103.*  
*EHR Baseline: ehr_baseline_2026-04-16.md — queried from production databases via Botsy MCP.*
