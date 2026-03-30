# Outcome Analysis — Ethereum

**Generated:** 2026-03-30 01:13 UTC
**Markets analyzed:** 8654

## Base Rate

| Direction | Count | % |
|-----------|-------|---|
| UP | 4332 | 50.1% |
| DOWN | 4322 | 49.9% |

**Assessment:** neutral (50.1% UP)

## Autocorrelation Profile

| Lag | Autocorrelation | Interpretation |
|-----|----------------|----------------|
| 1 | -0.0165 | NEUTRAL (no pattern) |
| 2 | -0.0282 | NEUTRAL (no pattern) |
| 3 | -0.0265 | NEUTRAL (no pattern) |
| 4 | -0.0148 | NEUTRAL (no pattern) |
| 5 | -0.0036 | NEUTRAL (no pattern) |

**Key finding:** Near-zero lag-1 autocorrelation (-0.0165) — no obvious directional persistence.

## Transition Probabilities

| After | P(next UP) | P(next DOWN) |
|-------|-----------|-------------|
| UP | 49.2% | 50.8% |
| DOWN | 50.9% | 49.1% |

- **Continuation rate:** 49.2%
- **Reversal rate:** 50.8%

## Streak Distribution

| Streak Length | Count | % of All Streaks |
|--------------|-------|-----------------|
| 1 | 2175 | 49.4% |
| 2 | 1121 | 25.5% |
| 3 | 608 | 13.8% |
| 4 | 264 | 6.0% |
| 5 | 123 | 2.8% |
| 6 | 62 | 1.4% |
| 7 | 22 | 0.5% |
| 8+ | 24 | 0.5% |

- Avg UP streak: 1.97 | Max: 11
- Avg DOWN streak: 1.96 | Max: 13

## Signal Candidates: Momentum vs Contrarian by Streak Length

After a streak of N, what happens next?

| Streak ≥ N | Occurrences | Momentum WR | Contrarian WR | Better Signal |
|-----------|-------------|-------------|---------------|---------------|
| ≥ 2 | 4255 | 47.7% | 52.3% | CONTRARIAN |
| ≥ 3 | 2031 | 45.7% | 54.3% | CONTRARIAN |
| ≥ 4 | 928 | 46.7% | 53.3% | CONTRARIAN |
| ≥ 5 | 433 | 46.7% | 53.3% | CONTRARIAN |

## Time-of-Day Pattern (UTC)

| UTC Hour | Markets | UP % | Dead Zone? |
|----------|---------|------|-----------|
| 00 | 372 | 53.2% |  |
| 01 | 363 | 54.8% |  |
| 02 | 360 | 46.9% |  |
| 03 | 360 | 47.5% |  |
| 04 | 360 | 51.7% |  |
| 05 | 360 | 48.9% |  |
| 06 | 360 | 45.6% |  |
| 07 | 359 | 52.6% |  |
| 08 | 360 | 48.6% |  |
| 09 | 360 | 50.3% |  |
| 10 | 360 | 51.1% |  |
| 11 | 360 | 51.9% |  |
| 12 | 360 | 47.2% |  |
| 13 | 360 | 52.2% |  |
| 14 | 360 | 47.2% |  |
| 15 | 360 | 51.9% |  |
| 16 | 360 | 48.6% |  |
| 17 | 360 | 49.4% |  |
| 18 | 360 | 49.4% |  |
| 19 | 360 | 51.7% |  |
| 20 | 360 | 51.4% |  |
| 21 | 360 | 52.5% |  |
| 22 | 360 | 49.4% |  |
| 23 | 360 | 46.9% |  |

## Volume Profile

- Average volume: $14607
- Median volume: $13884

---

## Summary & Next Steps

- Near-zero autocorrelation (-0.0165) → **no obvious directional edge** from streak-following alone
- Best raw signal: **contrarian at streak ≥ 3** (54.3% WR on 2031 occurrences)
- Continuation rate 49.2% → near 50/50 (no clear directional persistence)

**Decision gate:** Proceed to Phase 2 (pattern mining) if any signal candidate shows WR > 52% on 50+ occurrences.
