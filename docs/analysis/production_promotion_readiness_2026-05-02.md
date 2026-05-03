# Production Promotion Readiness - 2026-05-02

Fresh analysis timestamp: 2026-05-02T13:56Z. Before analysis, code was pulled
from GitHub and live operational DBs were synced from the VPS with targeted
`tools/sync_data.sh` calls. Botsy MCP `pipeline_overview` then showed current
live prediction recency around 2026-05-02T13:50Z-13:51Z for active pipelines.

## Executive Read

No full pipeline should be promoted to production today. The healthiest evidence
is cohort-level, not pipeline-level:

1. BTC 5m remains the best Polymarket control signal, but live execution history
   is still the blocker.
2. BTC Bybit perps have the best active 7d perp read, but 30d edge is thin and
   recent 1d performance is negative.
3. Kalshi's post-parser forward run is clean so far, but it has only 12 current
   7d bets and the 30d history is parser-contaminated.
4. ETH/SOL/DOGE should not be production candidates as full pipelines. ETH has
   low-volatility sub-cohorts worth shadowing; SOL and ETH perps are currently
   negative.

## Promotion Board

| Rank | Candidate | Current Verdict | Evidence | Promotion Gate |
|------|-----------|-----------------|----------|----------------|
| 1 | BTC 5m TRENDING / judge-accepted cohorts | Closest signal candidate, not live-ready | 30d BTC 5m: 451 bets, 53.2% WR, +$886.60 estimated P&L. TRENDING regimes: 62/101 wins across LOW/MED/HIGH TRENDING buckets; judge accepted: 69 bets, 58.0% WR, +$256.42; judge rejected: 163 bets, 46.0% WR, -$259.50. | 50 forward observations per BTC5M triage shadow with positive P&L, no stale-pipeline incident, and execution issue #15 resolved or bypassed with a micro-canary. |
| 2 | BTC Bybit perp regime-filtered subset | Paper candidate only | 7d: 65 bets, 56.9% WR. 30d: 504 bets, 50.8% WR, +$200. Medium-vol trending: 71 bets, 62.0% WR. Low-vol neutral: 37 bets, 64.9% WR. High-vol trending is bad: 32 bets, 37.5% WR. | Register a regime-filtered shadow/counterfactual. Need 50 forward regime-qualified observations and a clean testnet execution audit before any live-capital step. |
| 3 | Kalshi strike-aware parser forward run | Sample-starved candidate | 7d: 12 bets, 100% WR. 30d aggregate is invalid for promotion: 432 bets, 20.4% WR, -$6146.25 because pre-parser history is contaminated. Config already requires 200 parser-versioned resolved predictions. | Do not promote before 200 parser-versioned resolved predictions and WR >55%; keep old parser history excluded. |
| 4 | ETH 5m low-vol cohorts | Shadow-only rehab candidate | 30d ETH 5m: 684 bets, 51.0% WR, +$826.49, but 7d is 82 bets, 42.7% WR. Low-vol neutral: 108 bets, 57.4% WR. Low-vol trending: 16 bets, 81.2% WR. High-vol buckets are poor. | Add ETH low-vol shadow criteria before any promotion. Need recent 7d recovery plus 50 forward low-vol observations above breakeven. |

## Disqualified Today

| Pipeline | Why Not Production |
|----------|--------------------|
| `eth_bybit` / `eth_hl` | 30d/7d both weak: around 41% 30d WR and about 40-41% 7d WR. |
| `sol_bybit` / `sol_hl` | 30d/7d weak: about 39-42% WR. |
| `doge_bybit` / `doge_hl` | 7d sample is only 4 bets each; 30d DOGE HL is 101 bets at 45.5% WR. |
| `btc_15m` | Paused and stale since 2026-04-09; no current production path. |

## Execution Risk

BTC 5m signal evidence is better than its execution evidence. MCP
`order_summary(days=30)` shows 197 BTC 5m orders: 146 paper settled, 25 live
settled, 15 failed, 11 expired, and total order P&L -$502.31. This is why the
next production path should be a tightly scoped canary, not a normal live flip.

Bybit paper execution is cleaner structurally but not yet economically proven:
`order_summary(days=30)` shows 116 paper orders and no live orders. Fill
diagnostics show paired `paper_would_fire` and `bybit_exit_time_ceiling` records,
so the next step is a testnet/live-equivalent execution audit rather than a
Polymarket-style fill-rate fix.

## Concrete Next Steps

1. Keep BTC 5m paper while BTC5M triage shadows from issue #95 accumulate forward
   observations. Do not change BTC prediction logic while the shadows are
   measuring.
2. Open a BTC 5m production-readiness decision that can trigger only when the
   BTC5M shadows and execution guardrails both clear.
3. Open a Bybit BTC regime-filter decision for medium/low-vol candidate regimes;
   this is paper/testnet validation, not immediate live promotion.
4. Open an ETH low-vol rehab decision; ETH full-pipeline promotion is explicitly
   out of scope until recent 7d performance recovers.
5. Keep Kalshi on the existing parser-versioned 200-sample gate.

## 2026-05-03 Sweep Update

Follow-up implementation registered the missing forward trackers rather than
changing production behavior:

| Tracker | Scope | Baseline |
|---------|-------|----------|
| `bybit_btc_regime_filter_shadow` | BTC Bybit LOW_VOL/NEUTRAL, LOW_VOL/TRENDING, MEDIUM_VOL/TRENDING | 127 bets, 63.8% WR, +$875.00 P&L |
| `eth5m_low_vol_shadow` | ETH 5m LOW_VOL/NEUTRAL and LOW_VOL/TRENDING | 129 bets, 61.2% WR, +$656.26 P&L |
| `btc5m_high_range_protection_shadow` | BTC 5m days where BTC `range_zscore >= 1.5` | 41 bets, 39.0% WR, -$220.05 P&L |

Promotion posture remains unchanged: #96, #97, #98, and #99 are not ready until
their forward samples reach gate size. Execution issue #15 still blocks normal
live-capital promotion; a canary needs explicit fill/adverse-selection reporting
or a documented bypass.

Operational playbook: `docs/plans/signal-terrain-execution-sweep-2026-05-03.md`.

## Non-Actions

- No pipeline mode changed.
- No prediction logic changed.
- No new production capital was enabled.
- No historical parser-contaminated Kalshi data was treated as live-ready edge.
