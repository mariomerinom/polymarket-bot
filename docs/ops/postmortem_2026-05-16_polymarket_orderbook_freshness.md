# Postmortem - Polymarket Orderbook Freshness Blocker (May 2026)

**Severity:** Sev-2. No live capital loss, but BTC 5m production promotion remains blocked.
**Status:** Open. Diagnostics improved, but the execution/freshness blocker is not cleared.
**Primary impact:** BTC 5m delayed FAK and live-canary readiness cannot rely on fresh Polymarket orderbook evidence.
**Affected paths:** Polymarket orderbook cache, delayed BTC 5m timing candidates, canary readiness, daily/consolidated reports.

## What Happened

Across multiple iterations, we treated high true orderbook age and missing delayed BTC 5m books as a websocket subscription/freshness problem. We added `price_change` handling, REST seeding, reconnect debounce, freshness counters, and report surface area. Those were useful, but they did not resolve the blocker.

The deeper issue is that the pipeline still has several places where the runtime can appear healthy while execution evidence remains incomplete:

- The engine maintains fresh books in memory, but execution consumers read `data/live_orderbook.json` from disk.
- The cache writer says it flushes every 5 seconds, but the only actual call is inside the 60 second metrics loop.
- Delayed multi-poll book capture returns `entry.age_ms` as a method object instead of calling `entry.age_ms()`, which can make delayed candidate handling fail before a terminal row is written.
- Delayed DOWN/NO candidates derive a synthetic NO book from the YES book, so actual NO-token freshness is invisible.
- Canary readiness can evaluate an old or incomplete `ws_metrics.json` as if it were current evidence.

We did not lose production money because live/canary gates remained blocked. We did lose time and confidence: repeated patches improved visibility without forcing the runtime/execution contract to become true.

## Evidence

### Slow Disk IPC Can Masquerade As Stale Orderbooks

`botsy_engine.py` keeps an in-memory orderbook cache and writes `data/live_orderbook.json` via `_flush_orderbook_cache()`. The function comment says it is called every 5 seconds, but it is only called from `metrics_writer()`, which sleeps `METRICS_INTERVAL_S` before each write cycle:

- `src/botsy_engine.py:953` defines `_flush_orderbook_cache()`.
- `src/botsy_engine.py:1555` starts `metrics_writer()`.
- `src/botsy_engine.py:1559` sleeps on the metrics interval.
- `src/botsy_engine.py:1576` flushes the orderbook cache.

Execution consumers read disk:

- `src/orderbook_cache.py:21` defines `data/live_orderbook.json` as the default path.
- `src/trade.py:907` reads the cache through `OrderbookCache.load()`.
- `src/multi_poll_predict.py:368` reads the cache through `OrderbookCache.load()`.

That means fresh websocket updates can sit in memory while consumers see a disk snapshot that is up to one metrics interval old. This can explain persistent p95 values far above the `<2s` gate even when websocket events are flowing.

### Delayed Candidate Book Age Can Fail Before Classification

`multi_poll_predict._get_market_orderbook()` returns `entry.age_ms` rather than `entry.age_ms()`:

- `src/multi_poll_predict.py:372` returns `entry.mid`, bid, ask, spread, and `entry.age_ms`.
- `src/multi_poll_predict.py:557` stores that value into `orderbook_age_ms`.
- `src/multi_poll_predict.py:578` catches delayed candidate processing exceptions and only logs a warning.

The same method-object return exists in `src/arb_loggers.py:66`.

If SQLite binding or downstream integer conversion fails, the candidate can vanish before `btc5m_timing_candidates` records a terminal skip reason. That violates the intended invariant: every delayed opportunity must be recorded as ordered, skipped, blocked, failed, or expired.

### Delayed DOWN/NO Freshness Is Not Actually Measured

The delayed path captures YES-token orderbook fields for timing replay, then synthesizes NO bid/ask by complementing YES bid/ask:

- `src/multi_poll_predict.py:340` documents YES-token orderbook capture.
- `src/delayed_execution.py:247` marks both sides CLOB-verified and derives NO fields from YES fields.

Regular execution resolves both tokens separately:

- `src/trade.py:903` reads live token entries for each side.
- `src/trade.py:940` falls back to REST per token.

For BTC 5m promotion, this matters because DOWN/NO opportunities can look executable in delayed paper while the actual NO token is missing, stale, crossed, or thin.

### Readiness Can Trust Stale Metrics

`canary_readiness._metrics_blockers()` checks connection status, dispatch p95, and orderbook p95:

- `src/canary_readiness.py:169` starts metrics blocker evaluation.
- `src/canary_readiness.py:176` checks Polymarket status.
- `src/canary_readiness.py:179` checks dispatch p95.
- `src/canary_readiness.py:184` checks orderbook p95.

It does not currently require a fresh metrics write timestamp, minimum sample count, schema version, fresh-token coverage, or fresh Polymarket `last_event`. A stale file can be interpreted as evidence instead of becoming a blocker.

## Root Cause

The root cause is not a single bad counter. It is a broken execution evidence contract.

The system has been patching symptoms inside separate surfaces:

- Websocket freshness counters.
- Daily report phrasing.
- Delayed execution evidence.
- Canary gates.
- Git/runtime deployment rules.

But BTC 5m production readiness needs one end-to-end invariant:

> For every eligible prediction, the system must prove the exact side token had a fresh executable book at decision time, classify the terminal execution outcome, and expose the resulting readiness verdict from fresh runtime metrics.

That invariant is not yet enforced.

## Contributing Factors

1. **Disk IPC hides runtime truth.** The engine cache is in memory; consumers read disk. The write cadence was assumed rather than verified.
2. **Warnings were allowed to replace terminal state.** Delayed candidate exceptions can be logged without creating a candidate row.
3. **Synthetic book data leaked into execution evidence.** YES-derived NO fields were treated as verified enough for delayed execution.
4. **Metrics schema has no freshness contract.** Reports default missing counters to zero; readiness does not fail closed on stale or old-schema metrics.
5. **Deployment completion was inferred from push.** Current checked-in metrics can still show old schema after a code push, which means restart/runtime verification is part of the fix.
6. **Paper evidence was over-weighted.** Paper validates signal and routing shape, but it does not prove live CLOB fill semantics or actual side-token freshness.

## Anti-Practices To Stop

| Anti-practice | Why it hurts this pipeline | Replacement |
|---|---|---|
| Treating a pushed source change as deployed and active | Python imports and systemd runtime can remain stale | Verify deploy hook log, process start time, and one fresh runtime metrics cycle |
| Using paper orders as execution proof | Paper orders do not prove CLOB submission, fills, or side-token liquidity | Require delayed paper FAK plus live-canary fill reconciliation before promotion |
| Letting warnings substitute for terminal state | Warnings disappear from readiness math | Every eligible prediction/candidate gets exactly one terminal classification |
| Reading a disk cache as if it were realtime | Disk flush cadence can dominate p95 | Flush orderbook IPC on a tight loop or move consumers to in-process/shared service reads |
| Defaulting missing metrics fields to healthy-looking zeroes | Old schema and dead metrics look like quiet metrics | Add schema version, write timestamp, sample count, and fail-closed readiness checks |
| Using synthetic NO books for DOWN execution evidence | Actual side liquidity can be missing or stale | Capture and gate on the exact token being traded |
| Shipping observability without a decision line | Operators see numbers but not GO/NO-GO | Reports must render `READY` or `BLOCKED` with top blockers |
| Keeping generated runtime data and deployable source in one mutable worktree without strong gates | Auto-commit and deploy state can interfere | Preserve allowlist/bail behavior; longer term separate runtime artifacts from source |

## Practices To Keep

- Fail-closed BTC 5m canary gates.
- One regression test per incident.
- Shadow-first experimentation with registered gates.
- Git loop allowlist and bail marker for unexpected staged paths.
- Single `system_state.py` runtime state contract.
- Current decision to avoid BTC 5m signal/sizing changes while execution evidence is broken.

## Remediation Plan

### Immediate Fixes

1. Split orderbook IPC flushing from the 60 second metrics loop. Flush dirty `live_orderbook.json` every 1-5 seconds or on fresh book updates with a small throttle.
2. Fix `entry.age_ms` to `entry.age_ms()` in multi-poll and arb logging paths.
3. Ensure delayed candidate exceptions write `state=blocked`, `skip_reason=unexpected_error` instead of only logging.
4. Add `schema_version`, `metrics_written_at`, and sample-count checks to `ws_metrics.json`.
5. Make readiness block on stale metrics, missing diagnostics schema, zero orderbook samples, stale Polymarket `last_event`, and weak fresh-token coverage.

### Next Execution Fixes

1. Capture both YES and NO token books in multi-poll/delayed execution.
2. Gate delayed candidates on the exact token/side that would be traded.
3. Derive delayed candidate terminal state from the actual order status, not from the fact that `place_order()` returned.
4. Record fill diagnostics for all immediate-path `should_trade()` skips.
5. Parse/reconcile FAK response fills so `filled_full`, `filled_partial`, and killed/unfilled outcomes are not conflated.

### Operator Surface

1. Add a daily/consolidated `BTC 5m Production Readiness` section with verbatim blockers.
2. Show freshness root cause and cache coverage as a GO/NO-GO line.
3. Show stale metrics/schema as a blocker, not as missing detail.
4. Add a post-deploy verification checklist to the deployment docs.

## Decision

BTC 5m remains blocked from live canary until:

- `live_orderbook.json` disk IPC age is proven below 2s p95 from consumer-read timestamps.
- Delayed candidates capture actual side-token freshness.
- Delayed candidate failures cannot disappear before classification.
- Canary readiness fails closed on stale/old metrics.
- Reports show a single readiness verdict and blockers.

## Regression Tests Required

- Orderbook dirty cache flushes independently of the 60 second metrics writer.
- Multi-poll stores numeric `orderbook_age_ms`, not a method object.
- Delayed processing exceptions create terminal candidate rows.
- Delayed DOWN candidates require fresh NO-token book evidence.
- Canary readiness blocks old metrics schema, stale metrics timestamp, zero samples, and stale Polymarket last event.
- FAK response handling distinguishes full fill, partial fill, rejected, killed, and failed.

## Follow-Up Artifact

See `docs/plans/polymarket-orderbook-robustness-plan.md` for the implementation sequence.
