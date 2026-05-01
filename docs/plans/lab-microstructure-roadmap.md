# Lab And Microstructure Roadmap

**Date:** 2026-05-01
**Issue:** #92
**Status:** implementation shipped as research-only infrastructure

## Summary

Strategy Lab remains a candle-outcome discovery tool. Its win rate and P&L
must not be treated as executable trading edge without forward shadow or paper
validation. This roadmap adds deploy/timing partitioning, labels Lab P&L as
synthetic candle-score P&L, and starts a Polymarket orderbook snapshot dataset
for dislocation, order-flow, dead-hour, and execution-aware research.

## Backward

- No frozen BTC production files are changed.
- No conviction, order, sizing, or live-trading behavior changes.
- Rollback is to disable the microstructure writer in `botsy_engine.py` and
  leave `data/polymarket_microstructure.db` as disposable research data.
- Existing Lab rows remain readable; new columns are additive and nullable.

## Present

- `strategy_lab.py` writes `schema_version`, `engine_commit`, `deploy_epoch`,
  `cycle_close_at`, `offset_seconds`, `source_interval`, and synthetic P&L.
- Botsy MCP Lab tools expose deploy-date filters, use 50-sample defaults for
  bucket/matrix scans, and label Lab results as discovery-only.
- Daily reports call the Lab leaderboard synthetic P&L and include the
  promotion caveat.
- `polymarket_microstructure.py` records summarized live CLOB cache snapshots
  every 30 seconds with 30-day retention.
- Botsy MCP exposes `polymarket_microstructure_summary`.

## Future

- Tier 1 candidate: `market_price_dislocation`, shadow-only, after the
  microstructure dataset has forward data.
- Tier 2 candidate: `order_flow_imbalance`, after 3-5 days of snapshots.
- Tier 3 candidate: `dead_regime_harvesting`, only after contract price ranges
  can be measured.
- RSI/OBV remain low-risk shadow filters only.
- VWAP and volatility breakout do not graduate from Lab alone.

## Validation Gates

- `lab_reliability_v1`: Lab reports must show deploy/timing fields and
  synthetic-P&L labeling; no Lab-derived promotion without separate forward
  validation.
- `polymarket_microstructure_capture_v1`: after one running hour, MCP should
  show nonzero snapshots, fresh-cache rate, spread stats, imbalance stats, and
  missing-market-id rate.
- First dislocation shadow candidate requires at least 200 forward candidates,
  positive realistic EV after fees/spread, and stale-orderbook rows under 20%.

## Verification

- `pytest tests/test_strategy_lab.py tests/test_orderbook_cache.py tests/test_daily_report.py -q`
- `pytest tests/ -v`
- `git diff --check`
