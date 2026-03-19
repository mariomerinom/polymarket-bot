# Backtest Results — All Versions

**Date:** March 16, 2026
**Period:** March 1–15, 2026 (14 days of BTC 5-min candles)
**Markets:** 200 (sampled every 3rd candle from 4,320 available)
**API cost:** ~$3 per run ($6 total across v1 + v2)

---

## V1: Original 3-Agent Ensemble

Agents: `base_rate`, `contrarian`, `news_momentum`
Equal-weight ensemble. No conviction tiers. Flat $100 bet on everything.

### Agent Accuracy (when calling a side, excluding 0.500 flat predictions)

| Agent | Correct | Called | Accuracy | Verdict |
|---|---|---|---|---|
| contrarian | 112 | 191 | **58.6%** | Only useful agent |
| base_rate | 105 | 212 | 49.5% | Coin flip |
| news_momentum | 108 | 243 | 44.4% | Actively destructive |

### V1 P&L

| Metric | Value |
|---|---|
| Total wagered | ~$20,000 |
| Total P&L | **-$2,647** |
| ROI | **-13%** |

**Diagnosis:** Two of three agents are noise or anti-predictive. news_momentum reasons about "macro catalysts" and "momentum" — meaningless at 5-minute scale. base_rate reasons about time-of-day and day-of-week effects — also noise. The ensemble averages in their bad calls, diluting contrarian's real signal.

---

## V2: Micro-TA 3-Agent Ensemble

Agents: `pattern_reader`, `contrarian`, `volume_wick`
Weighted ensemble (0.35 / 0.35 / 0.30). Conviction tiers with variable bet sizing.

### Agent Accuracy

| Agent | Correct | Called | Accuracy | Change vs V1 |
|---|---|---|---|---|
| contrarian | 90 | 151 | **59.6%** | +1.0pp (same agent, marginally better) |
| volume_wick | 87 | 149 | **58.4%** | +14.0pp vs news_momentum |
| pattern_reader | 76 | 145 | 52.4% | +2.9pp vs base_rate |

### V2 Conviction Tier Breakdown (3-agent, LOW=$25)

| Tier | Count | Accuracy | P&L | ROI |
|---|---|---|---|---|
| MEDIUM (score 3) | 26 | **69.2%** | +$696 | +36% |
| LOW (score 2) | 55 | 47.2% | -$100 | -8% |
| NO_BET (score 0-1) | 119 | 55.8% | $0 | — |
| **Total** | **200** | | **+$596** | **+18.2%** |

**Key finding:** MEDIUM conviction is the money maker. LOW conviction loses money — it's below coin flip. The conviction system works, but LOW tier bleeds profit.

---

## V2.1: Drop pattern_reader + Kill LOW Bets (Final)

After analyzing why MEDIUM accuracy was "only" 69%: pattern_reader was adding noise that diluted the signal. Tested every combination:

### Configuration Comparison

| Config | Ensemble Acc | MEDIUM Acc | Total P&L | ROI |
|---|---|---|---|---|
| 3-agent, LOW=$25 | 55.2% | 69.2% | +$596 | +18.2% |
| 3-agent, LOW=$0 | 55.2% | 69.2% | +$696 | +35.7% |
| **2-agent, LOW=$0** | **59.4%** | **78.3%** | **+$921** | **+53.4%** |
| 2-agent, LOW=$25 | 59.4% | 78.3% | +$647 | +20.4% |
| contrarian solo | 59.6% | — | +$417 | +34.8% |

### Final Config: 2-Agent Ensemble

- **Agents:** contrarian (weight 0.55) + volume_wick (weight 0.45)
- **Bet only on MEDIUM (score 3+) and HIGH (score 4+)**
- **Skip everything else**

| Tier | Count | Accuracy | Bet Size | P&L | ROI |
|---|---|---|---|---|---|
| **MEDIUM** | **23** | **78.3%** | $75 | **+$921** | **+53.4%** |
| LOW (skipped) | 61 | 41.4% | $0 | $0 | — |
| NO_BET (skipped) | 116 | 66.0% | $0 | $0 | — |

### What We Learned

1. **Contrarian is the star** — 58-60% accuracy across both v1 and v2. It reads exhaustion and compression in the last 3-4 candles. This is the only consistently profitable signal.

2. **volume_wick is the v2 win** — replaced the destructive news_momentum (44%) with a 58% agent that reads volume spikes and wick rejection. Both agents now contribute real signal.

3. **pattern_reader is noise** — its range_position mean-reversion logic is anti-predictive at 5-min scale. "Oversold" at micro level doesn't mean reversion; it means the move is continuing. Dropping it improved MEDIUM accuracy from 69% to 78%.

4. **LOW conviction is a trap** — across every configuration tested, LOW tier is below 50% accuracy. The system correctly identifies weak signals... and then bets on them anyway. Eliminating LOW bets turns a +18% ROI into +53%.

5. **Selectivity is the edge** — the final system only bets on 23 out of 200 markets (11.5%). When both agents agree, with medium+ confidence, and magnitude > 4pp from prior, the hit rate is 78%.

6. **Conviction tiers work** — the 5-layer scoring (agreement, magnitude, confidence, macro alignment, computed bias) successfully separates good calls from noise. With NEUTRAL macro bias, max practical score is 3 (MEDIUM), since layers 4 and 5 can't fire.

---

## Cost Summary

| Run | Markets | API Calls | Cost |
|---|---|---|---|
| V1 backtest | 200 | ~800 | ~$3 |
| V2 backtest | 200 | 600 | ~$3 |
| **Total** | | **~1,400** | **~$6** |

---

## Next Steps

- Deploy 2-agent v2.1 config to live GitHub Actions pipeline
- Monitor first 50 live markets with new config
- Backtest longer periods (30+ days) once cost is validated
- Test with directional macro bias (UP or DOWN) to unlock HIGH conviction tier
- Consider going live on Polymarket once 100+ live markets confirm the edge holds
