# Polymarket Orderbook Robustness Plan

## Summary

This plan replaces incremental freshness patches with an end-to-end execution evidence contract. BTC 5m production is blocked until orderbook freshness, delayed FAK evidence, terminal execution classification, and canary readiness all agree from fresh runtime data.

No BTC 5m signal logic, sizing, timing thresholds, or live mode changes are included here.

## Goal

Make this invariant true:

> Every eligible BTC 5m execution candidate proves the exact side token had a fresh executable book at decision time, records one terminal execution classification, and surfaces a fresh READY/BLOCKED verdict in reports.

## Phase 1 - Fix The Cache Freshness Contract

### Changes

- Split `live_orderbook.json` flushing from the 60 second metrics writer.
- Add an `orderbook_cache_writer` task that flushes dirty cache entries every 1-5 seconds.
- Keep `ws_metrics.json` on the slower metrics cadence.
- Call pending resubscribe checks from a timer, not only inside the websocket message loop.
- Add `schema_version`, `metrics_written_at`, and `orderbook_cache_written_at` to metrics/cache artifacts.
- Add canary blockers for stale metrics, missing schema, zero orderbook samples, stale Polymarket `last_event`, and weak fresh-token coverage.

### Tests

- Dirty orderbook cache flushes before the metrics interval.
- Consumer-read age p95 uses disk write timestamps and falls below the flush interval in a controlled test.
- Pending debounced resubscribe executes even if no new websocket message arrives.
- Canary readiness blocks stale metrics, old schema, zero samples, and stale Polymarket events.

### Acceptance Criteria

- `ws_metrics.json` includes the new schema fields after deployment.
- `live_orderbook.json` updates within the configured flush interval while WS events are flowing.
- Daily report names stale metrics/schema as blockers when deployment has not actually taken effect.

## Phase 2 - Fix Delayed BTC 5m Evidence

### Changes

- Fix `entry.age_ms` call sites to store numeric ages.
- Capture both YES and NO token book fields in `multi_poll_predictions`.
- Update delayed execution to gate on the exact token/side it would trade.
- Stop deriving NO book freshness from YES complement fields.
- On delayed processing exception, write `btc5m_timing_candidates` with `state=blocked`, `skip_reason=unexpected_error`.
- Derive `paper_ordered`, `live_ordered`, `live_failed`, and blocked states from actual order status.

### Tests

- Multi-poll writes numeric `orderbook_age_ms`.
- DOWN/NO delayed candidates fail when NO token is missing or stale, even if YES is fresh.
- UP/YES delayed candidates fail when YES token is missing or stale.
- Delayed processing exceptions create terminal candidate rows.
- Delayed candidate state follows order status and records failed live submissions.

### Acceptance Criteria

- No delayed opportunity disappears before classification.
- Missing-book skips are separated by side/token.
- Delayed BTC 5m evidence can be trusted as execution evidence, not just timing research.

## Phase 3 - Fix Execution Classification

### Changes

- Record terminal diagnostics for all immediate-path `should_trade()` skips.
- Keep compute-order skip diagnostics, but normalize reason names across immediate and delayed paths.
- Reconcile FAK responses so partial fills, no fills, killed remainders, rejected orders, and failed submissions are distinct.
- Preserve existing FAK/IOC execution path; do not add strategy logic.

### Tests

- Every `conviction_score >= 3` prediction has exactly one terminal classification.
- System-state blockers create terminal diagnostic rows.
- FAK partial-fill responses are not marked `filled_full`.
- Missing CLOB token creates failed/blocked candidate state, not ordered success.

### Acceptance Criteria

- Unexplained conv>=3/no-order cases are zero.
- Fill diagnostics and delayed candidate states use the same terminal vocabulary.
- Execution EHR is computed from confirmed fill state, not optimistic requested size.

## Phase 4 - Operator Readiness Surface

### Changes

- Add daily/consolidated `BTC 5m Production Readiness` section.
- Render `READY` only when all blockers are empty.
- List live canary blockers and delayed-policy blockers verbatim.
- Show metrics schema/version/timestamps, Polymarket last event age, orderbook sample count, fresh/stale token coverage, and dominant stale reason.
- Add a deploy-done checklist to deployment docs:
  - full tests pass;
  - push succeeds;
  - VPS hook log confirms restart for source/config changes;
  - process start is newer than the source/config commit;
  - one fresh runtime cycle writes new-schema metrics;
  - daily/consolidated report shows the expected readiness verdict.

### Tests

- Reports show `BLOCKED` when any canary blocker exists.
- Reports show stale metrics/schema as blockers.
- Reports include delayed policy blockers.
- Reports do not show `READY` without fresh sample-backed metrics.

### Acceptance Criteria

- An operator can answer “why are we blocked?” from one report section.
- Old metrics schema cannot be mistaken for a healthy quiet system.
- Production promotion has an auditable GO/NO-GO trail.

## Phase 5 - Production Promotion Recheck

Only after Phases 1-4:

- Run delayed BTC 5m paper FAK until at least 50 attempts.
- Require delayed orderbook age p95 `<2s`.
- Require non-negative delayed execution EHR and P&L.
- Require zero unexplained delayed candidates.
- Require no material stale-book/REST-fallback rate.
- Only then consider `$5-$10` BTC 5m live canary with the existing stop rules.

## Anti-Practices Retired By This Plan

- Pushing source without proving runtime activation.
- Treating report visibility as execution repair.
- Treating paper orders as live execution proof.
- Allowing warnings without terminal execution state.
- Reading a slow disk IPC cache as if it were realtime.
- Letting old metrics schemas default to benign-looking zeroes.
- Using synthetic complement books as side-token freshness evidence.

## Rollback

Each phase is independently revertible:

- Cache writer changes can revert to metrics-loop flushing.
- Delayed schema additions should be additive and nullable.
- Readiness/report gates can be disabled by reverting report/canary changes, but promotion should remain manually blocked until the root cause is understood.
- No phase changes signal logic or bet sizing.
