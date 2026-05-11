# Promotion Readiness Sprint — 2026-05-11

## Summary

This sprint addressed two infrastructure blockers that were preventing any
clean production-promotion read:

1. Polymarket websocket subscriptions could include expired-but-unresolved
   markets, causing the engine to subscribe to stale token IDs and report huge
   true orderbook ages.
2. Routed pipelines for the same candle event ran sequentially, so one slow
   runner inflated production dispatch latency for every downstream candidate.

No signal logic changed. No pipeline mode changed. This only improves the
decision surface and runtime path used to evaluate promotion readiness.

## Changes

### Orderbook Freshness

`BotsyEngine._get_active_token_ids()` now filters unresolved Polymarket markets
by actual tradable time:

- `end_date > now`
- `end_date <= now + 24h`

Expired rows that failed settlement can no longer poison websocket
subscriptions. If market discovery is broken, the websocket should now surface
that as missing/current-token coverage instead of silently subscribing to old
markets.

The engine also prunes the in-memory/disk orderbook cache to the active
subscription set on connect or token-set change. That keeps historical token
books out of runtime diagnostics and reduces the stale cache footprint.

### Dispatch Latency

Pipeline fanout now runs independent pipeline runners concurrently with bounded
fanout. Default concurrency is `4`, configurable via
`PIPELINE_FANOUT_CONCURRENCY`.

This should reduce production dispatch wall time for routed groups such as:

- BTC spot 5m: `btc_5m`, `kalshi`, `hl`
- ETH spot 5m: `eth_5m`, `eth_bybit`, `eth_hl`
- SOL/DOGE spot 5m perp pairs

The implementation still keeps each individual pipeline's DB work inside that
pipeline runner; it does not parallelize writes inside a single DB.

## Gate Impact

| Gate | Expected Impact | Still Need |
|------|-----------------|------------|
| True orderbook age p95 < 2s | Expired unresolved markets no longer enter the active subscription set | One post-deploy daily report proving active-token p95 is actually fresh |
| Production dispatch p95 < 30s | Sequential fanout bottleneck reduced by bounded concurrency | One post-deploy daily report showing p95 under gate or naming the remaining slow pipeline |
| No unexplained conv>=3 orphans | Not directly changed in this sprint | Continue using terminal-classification integrity checks |
| Candidate promotion | Still blocked until infrastructure gates clear | BTC 5m selected cohort remains the first canary candidate |

## Promotion Posture

No normal live promotion is approved by this change alone. The next decision
point is after the deployed engine has produced fresh metrics:

- If orderbook age p95 is below `2s` and dispatch p95 is below `30s`, prepare a
  BTC 5m selected-cohort micro-canary.
- If Polymarket orderbook freshness is still bad, do not run a Polymarket live
  canary; shift the promotion lane to a Bybit BTC favorable-terrain execution
  audit.

## Validation

Focused tests:

```text
pytest tests/test_engine.py tests/test_multi_pipeline_fok.py tests/test_engine_resilience.py -q
34 passed
```
