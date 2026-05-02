# Daily Triage - 2026-05-02

Fresh MCP snapshot after pulling `origin/main` on 2026-05-02. This note separates
runtime/reporting health from signal quality so cleanup work does not accidentally
become a strategy change.

## Pipeline Classification

| Pipeline | Classification | Evidence | Action |
|----------|----------------|----------|--------|
| btc_5m | healthy control | Last prediction 2026-05-01T12:50:30Z; 65 7d bets; 52.3% WR; +$136.90 estimated P&L; judge-accepted subset 7/10, +$111.64 | Keep collecting paper data; do not change signal logic today. |
| eth_5m | weak/stale | Last prediction 2026-04-30T13:15:39Z; 48 7d bets; 43.8% WR; -$129.91 estimated P&L; judge coverage 0% | Treat as weak signal plus coverage gap; investigate before any promotion. |
| bybit | stale/low sample | Last prediction 2026-04-28T23:15:05Z; 1 7d bet | Do not infer edge from 100% WR on one bet; check why pipeline is quiet. |
| eth_bybit | stale/low sample | Last prediction 2026-04-28T23:15:49Z; 4 7d bets; 50.0% WR; no judge coverage | Classify separately from ETH 5m; not enough fresh data for a signal verdict. |
| eth_hl | stale/low sample | Last prediction 2026-04-28T23:15:51Z; 4 7d bets; 50.0% WR | Same as `eth_bybit`; verify runtime cadence before signal work. |
| sol_bybit | stale/no fresh bets | Last prediction 2026-04-28T23:15:54Z; 0 7d bets | Treat May 1 daily loss snapshot as historical until current cadence is explained. |
| sol_hl | stale/no fresh bets | Last prediction 2026-04-28T23:15:56Z; 0 7d bets | Same as `sol_bybit`; runtime recency is the first question. |
| doge_bybit | stale/no fresh bets | Last prediction 2026-04-28T23:15:05Z; 0 7d bets | Monitor only. |
| doge_hl | stale/no fresh bets | Last prediction 2026-04-28T23:15:07Z; 0 7d bets | Monitor only. |
| kalshi | paused/stale experiment | Last prediction 2026-04-17T14:30:10Z; parser rebuild requires forward validation | Keep historical Kalshi data excluded from edge claims. |
| btc_15m | intentionally paused | Config mode paused; last prediction 2026-04-09T21:45:02Z | No action unless reprioritized. |
| hl | stale/no resolved history | Last prediction 2026-04-28T23:15:29Z; 0 total resolved bets in MCP overview | Verify pipeline state before relying on daily report rows. |

## Cleanup Priorities

1. Reporting truthfulness: rename "Active pipelines" to "Pipelines with resolved bets" so report readers do not confuse same-day bets with runtime liveness.
2. Safety semantics: render circuit breaker false as `No`, not a bare success mark under a `Tripped?` column.
3. Alert hygiene: group repeated integrity alerts such as `orphaned_predictions` by check name.
4. Git safety: block unattended `Auto:` commits if staged paths include source, tests, config, or docs plans.

## Non-Actions

- No prediction thresholds changed.
- No paper pipelines paused from this cleanup.
- No live-capital posture changed.
