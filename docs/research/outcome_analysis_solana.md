# Outcome Analysis — Solana

**Generated:** 2026-03-30 01:09 UTC
**Markets analyzed:** 8653

## Base Rate

| Direction | Count | % |
|-----------|-------|---|
| UP | 4329 | 50.0% |
| DOWN | 4324 | 50.0% |

**Assessment:** neutral (50.0% UP)

## Autocorrelation Profile

| Lag | Autocorrelation | Interpretation |
|-----|----------------|----------------|
| 1 | -0.0053 | NEUTRAL (no pattern) |
| 2 | -0.0221 | NEUTRAL (no pattern) |
| 3 | -0.0150 | NEUTRAL (no pattern) |
| 4 | -0.0258 | NEUTRAL (no pattern) |
| 5 | +0.0060 | NEUTRAL (no pattern) |

**Key finding:** Near-zero lag-1 autocorrelation (-0.0053) — no obvious directional persistence.

## Transition Probabilities

| After | P(next UP) | P(next DOWN) |
|-------|-----------|-------------|
| UP | 49.8% | 50.2% |
| DOWN | 50.3% | 49.7% |

- **Continuation rate:** 49.7%
- **Reversal rate:** 50.3%

## Streak Distribution

| Streak Length | Count | % of All Streaks |
|--------------|-------|-----------------|
| 1 | 2139 | 49.2% |
| 2 | 1114 | 25.6% |
| 3 | 565 | 13.0% |
| 4 | 296 | 6.8% |
| 5 | 128 | 2.9% |
| 6 | 55 | 1.3% |
| 7 | 27 | 0.6% |
| 8+ | 26 | 0.6% |

- Avg UP streak: 1.99 | Max: 13
- Avg DOWN streak: 1.99 | Max: 15

## Signal Candidates: Momentum vs Contrarian by Streak Length

After a streak of N, what happens next?

| Streak ≥ N | Occurrences | Momentum WR | Contrarian WR | Better Signal |
|-----------|-------------|-------------|---------------|---------------|
| ≥ 2 | 4302 | 48.6% | 51.4% | NEITHER (< 3pp gap) |
| ≥ 3 | 2092 | 47.6% | 52.4% | CONTRARIAN |
| ≥ 4 | 995 | 46.5% | 53.5% | CONTRARIAN |
| ≥ 5 | 463 | 49.0% | 51.0% | NEITHER (< 3pp gap) |

## Time-of-Day Pattern (UTC)

| UTC Hour | Markets | UP % | Dead Zone? |
|----------|---------|------|-----------|
| 00 | 372 | 52.4% |  |
| 01 | 362 | 51.9% |  |
| 02 | 360 | 47.2% |  |
| 03 | 360 | 48.1% |  |
| 04 | 360 | 48.9% |  |
| 05 | 360 | 49.2% |  |
| 06 | 360 | 43.1% |  |
| 07 | 359 | 53.2% |  |
| 08 | 360 | 47.5% |  |
| 09 | 360 | 55.0% |  |
| 10 | 360 | 49.7% |  |
| 11 | 360 | 50.6% |  |
| 12 | 360 | 49.4% |  |
| 13 | 360 | 52.5% |  |
| 14 | 360 | 50.6% |  |
| 15 | 360 | 53.1% |  |
| 16 | 360 | 48.9% |  |
| 17 | 360 | 46.9% |  |
| 18 | 360 | 50.8% |  |
| 19 | 360 | 46.7% |  |
| 20 | 360 | 54.2% |  |
| 21 | 360 | 50.6% |  |
| 22 | 360 | 51.4% |  |
| 23 | 360 | 48.9% |  |

## Volume Profile

- Average volume: $6758
- Median volume: $6309

---

## Summary & Next Steps

- Near-zero autocorrelation (-0.0053) → **no obvious directional edge** from streak-following alone
- Best raw signal: **contrarian at streak ≥ 4** (53.5% WR on 995 occurrences)
- Continuation rate 49.7% → near 50/50 (no clear directional persistence)

**Decision gate:** Proceed to Phase 2 (pattern mining) if any signal candidate shows WR > 52% on 50+ occurrences.
