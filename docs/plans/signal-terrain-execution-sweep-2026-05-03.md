# Signal, Terrain, And Execution Sweep - 2026-05-03

## Summary

This sprint turns the promotion conversation into three measurable lanes:

1. Signal: BTC5M cohorts continue forward shadow collection before any logic
   change.
2. Terrain: daily and intraday regime cohorts are registered in
   `docs/optimizations.json` so decision gates can check forward evidence.
3. Execution: live-capital promotion remains blocked by issue #15 until a
   micro-canary or execution fix proves fills are not selecting losers.

No production prediction logic, sizing, or trading mode changes are included.

## Newly Registered Trackers

| Tracker | Pipeline DB | Baseline | Gate |
|---------|-------------|----------|------|
| `bybit_btc_regime_filter_shadow` | `bybit` | 127 bets, 63.8% WR, +$875.00 P&L | 50 forward observations in LOW_VOL/NEUTRAL, LOW_VOL/TRENDING, or MEDIUM_VOL/TRENDING before issue #97 can move to canary design. |
| `eth5m_low_vol_shadow` | `eth_5m` | 129 bets, 61.2% WR, +$656.26 P&L | 50 forward low-vol observations plus 7d aggregate recovery before issue #98 can move to rehab design. |
| `btc5m_high_range_protection_shadow` | `5m` | 41 bets, 39.0% WR, -$220.05 P&L | 50 forward BTC high-range observations. This is a protection lane, not a promotion lane. |

These are measured by `src/optimization_tracker.py check`; they do not affect
conviction, estimates, order routing, or paper/live mode.

## Promotion Posture

| Lane | Current Posture | What Would Move It Forward |
|------|-----------------|----------------------------|
| BTC5M quiet daily tape | Best production thesis; sample not started | `btc5m_quiet_daily_tape_shadow` reaches 50 forward observations above breakeven. |
| BTC5M judge-accepted | Promising but thin | Forward judge-accepted shadow reaches 50 observations and keeps P&L positive. |
| BTC5M high range | Risk/protection candidate | Forward high-range cohort remains weak; then propose a protective gate with rollback criteria. |
| BTC Bybit favorable regimes | Paper/testnet candidate | Issue #97 clears 50 forward regime-qualified observations and execution audit. |
| ETH low-vol | Rehab candidate only | Issue #98 clears low-vol forward sample and recent aggregate stops deteriorating. |

## Execution Gate

Issue #15 remains the production blocker. The historical failure mode is adverse
selection: filled orders underperformed while expired orders were disproportionately
would-have-won. A promotion package must include one of:

- A micro-canary that caps size, duration, and daily loss while reporting filled
  WR, expired would-have-won WR, fill rate, and adverse selection.
- An execution-layer change with a regression test and a rollback plan.
- A documented bypass approval that explicitly treats issue #15 as acceptable
  residual risk for the scoped canary.

Until then, healthy signal cohorts can graduate only to paper or shadow readiness,
not normal production capital.

## Daily Sweep

Run this sweep before any production-promotion decision:

1. Pull from GitHub and sync live DBs from the VPS.
2. Run `python3 src/optimization_tracker.py check`.
3. Review issues #96, #97, #98, #99, #85, and #15.
4. Confirm `data/HEALTH.log` reports fresh predictions and active botsy service.
5. Update the relevant decision issue with forward sample count, WR, P&L, and
   execution status.

## Non-Actions

- No source files that define BTC signal behavior were changed.
- No paper data collection was paused.
- No production capital was enabled.
- No hard terrain threshold was added to prediction logic.

## Evening Register

Detailed evening gate posture and the proposed #15 micro-canary shape now live
in `docs/plans/evening-promotion-sprint-2026-05-03.md`. The key change is not
signal behavior; it is decision hygiene:

- BTC5M judge-accepted and quiet-tape remain promotion lanes, but not ready.
- Bybit BTC favorable regimes are a testnet/live-equivalent execution lane.
- ETH low-vol is rehab only while the 7d aggregate is weak.
- BTC high-range remains a protection lane.
- Issue #15 remains the live-capital blocker until execution metrics are
  explicit enough to approve or reject a canary.
