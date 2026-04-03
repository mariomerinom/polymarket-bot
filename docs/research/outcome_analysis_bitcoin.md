# Outcome Analysis — Bitcoin

**Generated:** 2026-03-30 01:09 UTC
**Markets analyzed:** 8653

## Base Rate

| Direction | Count | % |
|-----------|-------|---|
| UP | 4299 | 49.7% |
| DOWN | 4354 | 50.3% |

**Assessment:** neutral (49.7% UP)

## Autocorrelation Profile

| Lag | Autocorrelation | Interpretation |
|-----|----------------|----------------|
| 1 | +0.0002 | NEUTRAL (no pattern) |
| 2 | -0.0069 | NEUTRAL (no pattern) |
| 3 | -0.0107 | NEUTRAL (no pattern) |
| 4 | -0.0015 | NEUTRAL (no pattern) |
| 5 | -0.0051 | NEUTRAL (no pattern) |

**Key finding:** Near-zero lag-1 autocorrelation (+0.0002) — no obvious directional persistence.

## Transition Probabilities

| After | P(next UP) | P(next DOWN) |
|-------|-----------|-------------|
| UP | 49.7% | 50.3% |
| DOWN | 49.7% | 50.3% |

- **Continuation rate:** 50.0%
- **Reversal rate:** 50.0%

## Streak Distribution

| Streak Length | Count | % of All Streaks |
|--------------|-------|-----------------|
| 1 | 2148 | 49.7% |
| 2 | 1070 | 24.7% |
| 3 | 588 | 13.6% |
| 4 | 271 | 6.3% |
| 5 | 119 | 2.8% |
| 6 | 60 | 1.4% |
| 7 | 37 | 0.9% |
| 8+ | 33 | 0.8% |

- Avg UP streak: 1.99 | Max: 15
- Avg DOWN streak: 2.01 | Max: 14

## Signal Candidates: Momentum vs Contrarian by Streak Length

After a streak of N, what happens next?

| Streak ≥ N | Occurrences | Momentum WR | Contrarian WR | Better Signal |
|-----------|-------------|-------------|---------------|---------------|
| ≥ 2 | 4326 | 49.7% | 50.3% | NEITHER (< 3pp gap) |
| ≥ 3 | 2149 | 48.4% | 51.6% | CONTRARIAN |
| ≥ 4 | 1041 | 50.0% | 50.0% | NEITHER (< 3pp gap) |
| ≥ 5 | 521 | 52.2% | 47.8% | MOMENTUM |

## Time-of-Day Pattern (UTC)

| UTC Hour | Markets | UP % | Dead Zone? |
|----------|---------|------|-----------|
| 00 | 372 | 48.9% |  |
| 01 | 362 | 51.4% |  |
| 02 | 360 | 48.1% |  |
| 03 | 360 | 50.6% |  |
| 04 | 360 | 49.4% |  |
| 05 | 360 | 49.7% |  |
| 06 | 360 | 42.8% |  |
| 07 | 359 | 53.2% |  |
| 08 | 360 | 46.7% |  |
| 09 | 360 | 50.0% |  |
| 10 | 360 | 51.7% |  |
| 11 | 360 | 51.9% |  |
| 12 | 360 | 48.9% |  |
| 13 | 360 | 53.1% |  |
| 14 | 360 | 51.1% |  |
| 15 | 360 | 49.7% |  |
| 16 | 360 | 49.4% |  |
| 17 | 360 | 48.6% |  |
| 18 | 360 | 49.2% |  |
| 19 | 360 | 47.5% |  |
| 20 | 360 | 51.9% |  |
| 21 | 360 | 49.7% |  |
| 22 | 360 | 51.1% |  |
| 23 | 360 | 47.8% |  |

## Volume Profile

- Average volume: $135486
- Median volume: $131906

---

## Summary & Next Steps

- Near-zero autocorrelation (+0.0002) → **no obvious directional edge** from streak-following alone
- Best raw signal: **momentum at streak ≥ 5** (52.2% WR on 521 occurrences)
- Continuation rate 50.0% → near 50/50 (no clear directional persistence)

**Decision gate:** Proceed to Phase 2 (pattern mining) if any signal candidate shows WR > 52% on 50+ occurrences.
