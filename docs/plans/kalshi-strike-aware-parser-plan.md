# Kalshi Strike-Aware Parser Plan

**Date:** 2026-05-01
**Status:** Implemented; paper validation pending
**Evidence:** [kalshi_parser_audit_2026-05-01.md](../analysis/kalshi_parser_audit_2026-05-01.md)
**Issue:** [#91](https://github.com/mariomerinom/polymarket-bot/issues/91)

## Backward — what could break

- Scope is Kalshi-only. No BTC 5m frozen files are touched.
- Existing Kalshi history remains in `data/predictions_kalshi.db`, but pre-`kalshi_strike_v1` rows are contaminated and excluded from edge claims.
- Rollback is config-only: set `config/pipelines.json::kalshi.mode` back to `paused`.
- If parser metadata is missing from any conv>=3 row, pause Kalshi immediately; that means the safety invariant failed.

## Present — what changes

Kalshi predictions now answer the actual contract question: "Will BTC be above strike K at expiry T?"

Implementation requirements:

- Persist `strike`, `timeframe`, and `market_type` in the Kalshi markets table.
- Parse BTC strike contracts from ticker format `BTCUSD-YYMMDDHHMM-STRIKE`, with question-text fallback for "above $X" markets.
- Reject unsupported or ambiguous markets instead of treating them as tradeable.
- Compute `current_btc`, `minutes_to_expiry`, and `required_move_pct` before any tradeable conviction is assigned.
- Map side explicitly:
  - UP momentum can become YES only if the strike is reachable.
  - DOWN momentum can become NO only if the strike relationship is reachable or already favorable.
  - unreachable or invalid contracts become conv=0 skips with a concrete reason.
- Store parser metadata in `predictions.reasoning`: `parser_version`, `strike`, `current_btc`, `minutes_to_expiry`, `required_move_pct`, `selected_side`, and `skip_reason`.
- API errors with credentials enabled must not silently fall back to mock markets.

## Future — validation

Forward validation is registered as `kalshi_strike_aware_parser` in `docs/optimizations.json`.

Decision gates:

- Minimum sample: 200 resolved parser-versioned predictions.
- GO: conv>=3 WR > 55% and positive estimated P&L after fee/slippage assumptions.
- NO-GO: WR < 50% on 200 resolved predictions, or fewer than 25 conv>=3 resolved predictions in one week.
- Revert/pause: any conv>=3 row missing parser metadata.

Live Kalshi trading is out of scope until the paper gate clears.

## Verification

- `pytest tests/test_kalshi.py -q`
- Relevant pipeline/integrity tests
- Full suite before commit: `pytest tests/ -v`
