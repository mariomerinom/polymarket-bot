# Spec Index

Unimplemented feature designs. Each spec has a `> **Status:**` line after its title.

## Signal Strategies

| Spec | Status | Summary |
|------|--------|---------|
| [VWAP Mean Reversion](spec_vwap_mean_reversion.md) | STILL RELEVANT | VWAP z-score in mean-reverting regimes. In Strategy Lab as always-fire. |
| [Volatility Breakout](spec_volatility_breakout.md) | STILL RELEVANT | Bollinger compression→expansion. In Strategy Lab as always-fire. |
| [RSI Conviction Gate](spec_rsi_conviction_gate.md) | STILL RELEVANT | RSI as pre-bet filter to downgrade conflicting signals. |
| [OBV Bucket Filter](spec_obv_bucket_filter.md) | STILL RELEVANT | On-Balance Volume filter for 0.50-0.70 price bucket. |
| [Order Flow Imbalance](spec_order_flow_imbalance.md) | STILL RELEVANT | CLOB bid/ask imbalance as leading indicator. |
| [Cross-Exchange Lead-Lag](spec_cross_exchange_lead_lag.md) | STILL RELEVANT | Kraken/Coinbase temporal arbitrage. |
| [Dead Regime Harvesting](spec_dead_regime_harvesting.md) | STILL RELEVANT | Edge extraction from mean-reverting/dead-hour regimes. |
| [Market Price Dislocation](spec_market_price_dislocation.md) | STILL RELEVANT | Polymarket price lag vs BTC spot. |

## Infrastructure

| Spec | Status | Summary |
|------|--------|---------|
| [Regime Separation](regime_separation_ac.md) | STILL RELEVANT | Directional regime (UP vs DOWN) separation. |
| [Config Upgrades](spec_config_infrastructure_upgrades.md) | STILL RELEVANT | Pydantic validation, hot-reload, env injection. |

## Execution / Fill Problem (`stochastic/`)

| Spec | Status | Summary |
|------|--------|---------|
| [Stochastic Entry Timing](stochastic/spec_stochastic_entry_timing.md) | STILL RELEVANT | Stochastic oscillator for entry timing within 5-min windows. |
| [Fill Diagnostic](stochastic/spec_fill_diagnostic.md) | PARTIAL | Logging present, validation framework incomplete. |
| [Optimal Fill Hybrid](stochastic/Spec:%20Optimal%20Fill%20Strategy%20v1%20—%20Hybrid%20.md) | PARTIAL | Dynamic slippage live; Phase 2 stochastic timing deferred. |

## Archived (implemented, obsolete, or redundant)

Moved to `docs/archive/specs/`. Status headers preserved in each file.

| Spec | Status | Why Archived |
|------|--------|-------------|
| spec_execution.md | IMPLEMENTED | FOK orders + edge calculation in trade.py |
| spec_websocket-gem.md | IMPLEMENTED | botsy_engine.py Phases 1-3 |
| spec_unified_vps_websocket.md | IMPLEMENTED | VPS + WS all 3 phases |
| spec_bybit_vps_migration.md | IMPLEMENTED | VPS consolidated, systemd |
| spec_clob_token_pricing.md | IMPLEMENTED | Per-token CLOB cache |
| spec_fill_adverse_selection.md | IMPLEMENTED | FOK adverse selection in trade.py |
| instruction_widen_diag.md | IMPLEMENTED | DIAG logging in predict.py |
| spec_generic_conviction_engine.md | OBSOLETE | Replaced by Strategy Lab |
| spec_dynamic_price_cap.md | REDUNDANT | Merged into fill adverse selection |
| fill-implementation.md | REDUNDANT | Superseded by gemini synthesis |
| claude-fill-problem-consensus.md | REDUNDANT | One voice in resolved debate |
| gemini-fill-resolution.md | REDUNDANT | Logic implemented in trade.py |
| fill-problem-agreement-and-tension.md | REDUNDANT | Debate analysis; done |
