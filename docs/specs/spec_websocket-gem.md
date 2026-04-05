# Phase 3: Websocket Rewrite (Unified VPS + Websocket Architecture)

I have audited the current repository state and verified that Phase 1 (VPS loop consolidation) and Phase 2 (Fill diagnostic instrumentation via `src/fill_diagnostic.py` and `trade.py`) are fully implemented. 

The remaining work is **Phase 3 (Websocket Rewrite)**.

## User Review Required

> [!IMPORTANT]  
> The spec dictates that `compute_order()` must read from the live Polymarket WS orderbook instead of the DB snapshot to eliminate snapshot staleness. Because `botsy_engine.py` will manage the WS connections, and `src/trade.py` is invoked during prediction runs, how should `trade.py` retrieve the live orderbook data?
> **Option A (In-memory / Async Rewrite):** Refactor `predict.py` and `trade.py` to be async modules imported by `botsy_engine.py` so they share the same memory space. (High effort, breaks existing synchronous `ci_run.py` flow).
> **Option B (File-based Cache):** `botsy_engine.py` maintains the WS connection and constantly writes the latest `best_bid`/`best_ask`/`mid` for active markets to a fast in-memory tmp file (e.g., `data/live_orderbook.json`). `trade.py` reads this JSON to instantly get the <50ms stale mid price. (Lower effort, maintains existing `ci_run.py` compatibility).
> **Option C (Local Redis or HTTP Server):** `botsy_engine.py` serves the orderbook state on a local socket or HTTP server running on `localhost:8080`, and `trade.py` fetches the mid prices.

Please confirm if Option B or C is the preferred approach for IPC. Option B is proposed below based on the spec's requirement to keep `src/predict.py` and `src/trade.py` largely unchanged.

## Proposed Changes

### `botsy_engine.py`

#### [NEW] `src/botsy_engine.py`
A new async daemon script serving as the main event loop. It will:
1. Connect to Binance WS for 1m and 5m candle closes.
2. Connect to Bybit WS for BTC Perps 5m candle closes.
3. Connect to Polymarket WS to maintain live orderbook for targeted active markets.
4. On candle close: dispatch out to the appropriate bash script or `ci_run_*.py` script using `asyncio.create_subprocess_exec` to wrap the existing CLI pipelines without rewriting them to async.
5. Expose the live Polymarket orderbook state to `trade.py` (via Option B file-cache or Option C local socket).

#### [NEW] `scripts/start-engine.sh`
A wrapper script intended for `systemd` to keep `botsy_engine.py` running persistently, including environment variable sourcing.

---

### Shared Data / `src/trade.py`

#### [MODIFY] `src/trade.py`
Update `compute_order()` to check for the live WS orderbook feed (e.g., loading the temporary `data/live_orderbook.json` maintained by the engine). Fall back to the database snapshot `market_price_yes` only if the live feed is unavailable. 

#### [MODIFY] `requirements.txt`
Add `websockets` or `aiohttp` libraries if not already present.

## Open Questions

1. **Which markets should the WS orderbook subscribe to?** Polymarket has an connection limit and scaling issues. Subscribing to ALL live markets is heavy. Should we only subscribe to the subset of markets currently loaded in the database or currently targeted by active prediction markets?
2. **IPC choice (as specified in "User Review Required")** — Let me know which method you prefer for bridging data between the persistent engine and the transient pipeline scripts.

## Verification Plan

### Automated Tests
- Introduce a mock WebSocket server or test stub to ensure `botsy_engine.py` dispatches the right pipelines upon simulated candle closes (e.g., mock a 5m close and verify the BTC 5m pipeline is dispatched).

### Manual Verification (Phase 3 Shadow Mode)
- Run `botsy_engine.py` alongside the existing `scripts/vps-loop.sh` in paper-trading mode. 
- Verify the engine triggers right on the candle close via logs and compare the snapshot staleness diagnostic against the old sleep-loop method.
