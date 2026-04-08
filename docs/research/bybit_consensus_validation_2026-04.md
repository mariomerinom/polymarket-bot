# Bybit consensus boost validation — Phase 6

Compares WR on bets where the perps-vs-spot consensus
triggered a conviction boost (score == 2, sources >= 2)
vs bets without the boost. Filter: conv >= 3, resolved.

| Bucket | N | Wins | WR |
|---|---:|---:|---:|
| Boosted (score=2) | 4 | 2 | 50.0% |
| Unboosted         | 33 | 27 | 81.8% |
| No consensus data | 223 | — | — |

**Lift: -31.8pp**

## Verdict
⚠️ Boosted sample too small (N=4). Need more data before a kill decision. Leave boost in place.

