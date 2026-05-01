# Kalshi Parser Audit — 2026-05-01

## Summary

Kalshi's historical BTC pipeline results are contaminated by a contract-mapping bug. The pipeline applied one generic BTC momentum direction to every active Kalshi strike market, but Kalshi asks a different question: "Will BTC be above strike K at expiry T?"

The bad sample must not be used to evaluate Kalshi venue edge.

## Evidence

Fresh Botsy MCP reads on 2026-05-01:

| Slice | Bets | Wins | WR |
|-------|-----:|-----:|---:|
| Kalshi conv>=3 | 420 | 76 | 18.1% |
| conv>=3 UP | 344 | 0 | 0.0% |
| conv>=3 DOWN | 76 | 76 | 100.0% |

All 420 conv>=3 resolved markets settled NO. The full Kalshi DB is not all-NO: it contains 2,845 YES outcomes and 7,524 NO outcomes globally, so the result shape is selection/mapping failure rather than an all-broken outcome column.

Prior investigation documented the same signature in [regime_correlation_2026-04-16.md](regime_correlation_2026-04-16.md): BTC was near $72k while the bot logged YES-style momentum estimates against $84k-$85.5k strikes.

## Root Cause

`src/ci_run_kalshi.py` computed one BTC momentum signal from candles, then stored that signal directly against each unresolved Kalshi market. The code did not require:

- parsed strike
- current BTC price at prediction time
- minutes to expiry
- selected contract side (YES/NO)
- reachability check for the required move to strike

That made an UP streak become a YES-like prediction even when BTC was too far below the strike for the contract to be realistically reachable within the window.

## Findings

1. **Strike-blind mapping:** generic BTC UP/DOWN was treated as equivalent to Kalshi YES/NO.
2. **Schema gap:** Kalshi markets did not persist strike/timeframe/market type, so downstream code could not safely reason about contract semantics.
3. **Real API fallback risk:** credentials-on API errors could silently fall back to mock markets because `API_TIMEOUT_KALSHI` was not imported.
4. **Timeframe inference risk:** product class was inferred from time-to-expiry, so longer-duration contracts near expiry could be mislabeled as short-window markets.
5. **Skip diagnostic pollution:** skipped rows used market price as estimate, making reports infer UP/DOWN from YES mid instead of model direction.

## Action

Kalshi was paused in [config/pipelines.json](../../config/pipelines.json). The rebuild now requires a strike-aware parser and reachability gate before paper mode resumes. See [kalshi-strike-aware-parser-plan.md](../plans/kalshi-strike-aware-parser-plan.md).

Historical Kalshi performance before parser version `kalshi_strike_v1` is invalid for edge claims. Forward validation starts only from parser-versioned predictions. Tracking issue: [#91](https://github.com/mariomerinom/polymarket-bot/issues/91).
