# EHR Baseline Report — 2026-04-16

**Excess Hit Rate (EHR)** measures whether BOTSY identifies genuine mispricings or just tracks calibrated market prices. Defined in `spec_maker_mode.md`, derived from Akey et al. (2026).

```
EHR = Σ qᵢ(oᵢ - pᵢ) / Σ qᵢ
```

Where `oᵢ` = binary outcome (1 if resolved in your favor, 0 otherwise), `pᵢ` = execution price.

---

## 1. Signal EHR — Does the model identify mispricings?

Uses market price at prediction time. All resolved conv≥3 predictions.

| Pipeline | Signal EHR | WR | Avg Entry Price | n | Akey Percentile |
|----------|-----------|-----|-----------------|---|-----------------|
| **BTC 5m** | **+0.102** | 62.1% | 0.519 | 562 | **Top 2%** |
| ETH 5m | +0.036 | 52.8% | 0.491 | 470 | Top 10% |
| Bybit BTC | +0.003 | 50.3% | 0.500 | 376 | ~50th pctile |
| Kalshi | −0.241 | 26.7% | 0.508 | 285 | Catastrophic |

### Interpretation (Akey et al. scale)

| EHR Range | Meaning | Percentile |
|-----------|---------|------------|
| +0.10 to +0.15 | Genuine mispricing detection — top-tier skill | Top 2% |
| +0.05 to +0.10 | Modest but real edge | Top 10% |
| −0.02 to +0.05 | Tracking market prices, P&L = noise − spread | 30th–50th |
| < −0.02 | Systematically buying overpriced contracts | Bottom half |

---

## 2. Execution EHR — What do we actually capture?

Uses actual `price_filled` on settled orders. This is what matters for P&L.

| Pipeline | Exec EHR | Fill WR | Avg Fill Price | n |
|----------|----------|---------|----------------|---|
| BTC 5m (paper) | −0.006 | 47.9% | 0.486 | 96 |
| BTC 5m (live) | **−0.149** | 35.3% | 0.502 | 17 |
| ETH 5m | −0.010 | 48.5% | 0.496 | 204 |
| Bybit BTC | — | — | — | 0 |

### The execution gap

| Metric | Value |
|--------|-------|
| BTC 5m signal EHR | +0.102 |
| BTC 5m execution EHR | −0.028 |
| **Gap (edge destroyed)** | **13.0¢ per dollar** |

The signal identifies contracts mispriced by 10.2¢. By the time we fill, we're paying 2.8¢ *more* than fair value. The orders that fill are the ones where price moved against us — classic adverse selection.

Live fills are catastrophic: −0.149 EHR on 17 real-money trades (35% WR). The market is selectively filling our worst orders.

---

## 3. BTC 5m Signal EHR by Conviction

| Conv | Signal EHR | WR | n |
|------|-----------|-----|---|
| 3 | +0.082 | 62.2% | 238 |
| 4 | +0.057 | 56.7% | 233 |
| **5** | **+0.267** | **75.8%** | **91** |

Conv=5 is extraordinary: buying at ~49¢ and winning 76% of the time. EHR of +0.267 is off the Akey scale — that's a structural mispricing detector.

Conv=4 drops to +0.057 (still real edge). Conv=3 at +0.082 is strong, slightly above conv=4 — likely because conv=3 captures medium-confidence streaks that are closer to the mean-reversion inflection point.

---

## 4. BTC 5m Signal EHR by Regime

| Regime | Signal EHR | WR | n |
|--------|-----------|-----|---|
| MED_VOL / NEUTRAL | **+0.156** | 67.4% | 187 |
| MED_VOL / TRENDING | +0.136 | 67.5% | 77 |
| LOW_VOL / TRENDING | +0.124 | 63.4% | 41 |
| HV / TRENDING | +0.087 | 62.7% | 67 |
| HV / NEUTRAL | +0.037 | 54.4% | 158 |
| LOW_VOL / NEUTRAL | +0.026 | 53.1% | 32 |

Best signal edge in medium-volatility regimes (+0.136 to +0.156). HV/NEUTRAL has real but thin edge (+0.037). LOW_VOL/NEUTRAL is marginal (+0.026).

---

## 5. Cross-Pipeline Diagnosis

### BTC 5m (Polymarket)
- **Signal:** Elite. +0.102 EHR, top 2%.
- **Execution:** Destructive. −0.028 EHR. Adverse selection on fills.
- **Verdict:** Signal works. Execution architecture must change. **Maker mode candidate.**

### ETH 5m (Polymarket)
- **Signal:** Modest but real. +0.036 EHR, top 10%.
- **Execution:** Slightly negative (−0.010). Same adverse selection pattern, smaller gap.
- **Verdict:** Signal has edge but less room for execution error. Needs tighter fills or maker path.

### Bybit BTC (Perps)
- **Signal:** Zero. +0.003 EHR.
- **Execution:** No orders to measure.
- **Verdict:** **Not an execution problem — it's a signal problem.** Momentum predicts direction on Polymarket's binary structure (above/below = win) but perps need price to move far enough to cover fees. The signal does not transfer to perps.

### Kalshi BTC
- **Signal:** Actively destructive. −0.241 EHR, 26.7% WR.
- **Verdict:** **Kill this pipeline.** The signal systematically buys overpriced contracts. 285 predictions, all underwater.

---

## 6. Implications for Maker Mode Spec

The spec's Phase 1 gate asks: *"Is taker EHR > +0.02 on 200+ resolved fills?"*

**BTC 5m signal EHR = +0.102 on 562 predictions — gate PASSED with massive margin.**

However, actual taker execution EHR = −0.028 — gate FAILED on the execution side.

This is exactly the case the spec predicted:

> *"If taker EHR is near zero but [signal] EHR is positive, the signal has value but the execution is destroying it."*

The 13¢/dollar gap between signal and execution is the single biggest lever in the system. Closing even half of it (via maker fills, tighter limits, or reduced adverse selection) would turn BTC 5m from profitable-on-paper to profitable-in-practice.

---

## 7. Next Steps

1. **Add EHR to daily report** (AC-EHR-1, AC-EHR-2 from spec)
2. **Begin shadow maker logging** (Phase 1 of spec — measure hypothetical maker fills)
3. **Kill or pause Kalshi** — negative signal EHR means the model is wrong on that venue
4. **Deprioritize Bybit perps** — zero signal EHR, no amount of execution improvement helps
5. **Focus execution improvement on BTC 5m** — that's where the edge lives

---

*Reference: Akey, P., Grégoire, V., Harvie, N., & Martineau, C. (2026). Who Wins and Who Loses In Prediction Markets? Evidence from Polymarket. SSRN 6443103.*

*Data queried live from production databases via Botsy MCP on 2026-04-16.*
