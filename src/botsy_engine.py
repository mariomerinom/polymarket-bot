#!/usr/bin/env python3
"""
botsy_engine.py — Async websocket-driven trading engine.

Replaces vps-loop.sh (bash while-loop with sleep 300) with an event-driven
process that reacts to exchange candle-close events in real-time.

Three WS feeds:
  1. Bybit v5 spot  — BTC/ETH 1m/5m/15m kline triggers (241ms avg latency)
  2. Bybit v5 linear — BTC 1m/5m kline (perps pipeline)
  3. Polymarket       — Live CLOB orderbook (kills stale snapshot problem)

Candle Buffer + TA Engine:
  All kline events (including 1m) feed a rolling ring buffer (100 candles
  per symbol/timeframe). On 5m/15m close, the TA Engine computes indicators
  (RSI, BB, VWAP, OBV, Stoch, RVOL, Z-Score, EMA) from the buffer and
  passes them to the pipeline.

Pipelines (existing code, called as functions via asyncio.to_thread):
  - BTC 5m:  ci_run.main()       — triggered by Bybit spot BTC 5m close
  - BTC 15m: ci_run_15m.main()   — triggered by Bybit spot BTC 15m close
  - ETH 5m:  ci_run_eth.main()   — triggered by Bybit spot ETH 5m close
  - Bybit:   ci_run_bybit.main() — triggered by Bybit linear BTC 5m close
  - Kalshi:  ci_run_kalshi.main() — triggered by Bybit spot BTC 5m close

Usage:
    python src/botsy_engine.py
    # Or via systemd: systemctl start botsy
"""

import asyncio
import ctypes
import ctypes.util
import gc
import json
import os
import resource
import subprocess
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

# libc.malloc_trim(0) returns freed memory back to the OS (Linux/glibc only).
# Counters glibc malloc arena fragmentation from pandas/numpy short-lived allocs.
# See issue #77 — RSS grows while Python heap stays flat.
_LIBC_MALLOC_TRIM = None
if sys.platform.startswith("linux"):
    try:
        _libc_path = ctypes.util.find_library("c")
        if _libc_path:
            _libc = ctypes.CDLL(_libc_path)
            if hasattr(_libc, "malloc_trim"):
                _libc.malloc_trim.argtypes = [ctypes.c_size_t]
                _libc.malloc_trim.restype = ctypes.c_int
                _LIBC_MALLOC_TRIM = _libc.malloc_trim
    except (OSError, AttributeError):
        _LIBC_MALLOC_TRIM = None

# Ensure src/ is on the path for pipeline imports
SRC_DIR = Path(__file__).parent
REPO_DIR = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))

DATA_DIR = REPO_DIR / "data"
LOG_DIR = REPO_DIR / "logs"
LOG_FILE = LOG_DIR / "loop.log"
METRICS_FILE = DATA_DIR / "ws_metrics.json"
ORDERBOOK_CACHE = DATA_DIR / "live_orderbook.json"
PID_FILE = DATA_DIR / "engine.pid"


# ── PID Lock (Fix 2: prevent dual engine processes) ─────────────────────────


class PIDLockError(Exception):
    """Raised when another engine instance is already running."""
    pass


def acquire_pid_lock(pid_file=None):
    """Acquire PID lock file. Raises PIDLockError if another instance is alive."""
    if pid_file is None:
        pid_file = PID_FILE

    pid_file = Path(pid_file)
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
            # Check if PID is alive
            os.kill(old_pid, 0)  # Signal 0 = check existence
            raise PIDLockError(
                f"Engine already running (PID {old_pid}). "
                f"Kill it first or remove {pid_file}"
            )
        except (ProcessLookupError, ValueError):
            # PID is dead or invalid — safe to proceed
            pass

    pid_file.write_text(str(os.getpid()))

    import atexit
    atexit.register(lambda: pid_file.unlink(missing_ok=True))

# Routing: (source, symbol, interval) -> list of pipeline names
# Bybit WS v5 handles all candle triggers (241ms avg latency, validated 2026-04-05)
# 1m events feed the buffer + TA engine but do NOT trigger pipelines.
ROUTING = {
    ("bybit_spot", "BTCUSDT", "5"):    ["btc_5m", "kalshi", "hl"],
    ("bybit_spot", "BTCUSDT", "15"):   ["btc_15m"],       # native 15m, replaces counter
    ("bybit_spot", "ETHUSDT", "5"):    ["eth_5m", "eth_bybit", "eth_hl"],
    ("bybit_linear", "BTCUSDT", "5"):  ["bybit"],
    # Multi-pair perp feeds
    ("bybit_spot", "SOLUSDT", "5"):    ["sol_bybit", "sol_hl"],
    ("bybit_spot", "DOGEUSDT", "5"):   ["doge_bybit", "doge_hl"],
}

# Fallback timer: force-run if no WS event for this many seconds
FALLBACK_TIMEOUT_S = 360  # 6 minutes

# Metrics write interval
METRICS_INTERVAL_S = 60

# Git commit interval
GIT_COMMIT_INTERVAL_S = 300  # 5 minutes


def log(msg: str):
    """Log with UTC timestamp to stdout. systemd redirects to loop.log."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


class BotsyEngine:
    def __init__(self):
        self.cycle = 0
        self.last_report_date = ""
        self.last_event_time = time.time()
        self._dispatched: set = set()  # dedup: (source, symbol, candle_ts)

        # Candle buffer + TA engine (Stage 1-2 of Phase 3)
        from candle_buffer import CandleBuffer
        self.candle_buffer = CandleBuffer(maxlen=100)
        self.ta_engine = None  # initialized lazily after buffer seed

        # Metrics state
        self.metrics = {
            "bybit_spot": {
                "status": "disconnected",
                "last_event": None,
                "reconnects_24h": 0,
            },
            "bybit_linear": {
                "status": "disconnected",
                "last_event": None,
                "reconnects_24h": 0,
            },
            "polymarket": {
                "status": "disconnected",
                "last_event": None,
                "reconnects_24h": 0,
            },
            "dispatch_latency_ms": {"p50": 0, "p95": 0, "samples": 0},
            "orderbook_age_ms": {"p50": 0, "p95": 0, "samples": 0},
            "fallback_fires_24h": 0,
            "engine_start": datetime.now(timezone.utc).isoformat(),
            "cycles": 0,
        }
        self._latencies: list = []  # recent dispatch latencies in ms
        self._orderbook_ages: list = []  # recent orderbook ages in ms
        self._orderbook_cache: dict = {}  # in-memory: asset_id → entry dict
        self._orderbook_dirty = False     # flag: needs disk flush

        # Daily regime metrics: track last recorded UTC date per asset so we
        # only fire the rollover fetch once per asset per day. See asset_daily.py.
        self._asset_daily_last_date: dict = {}  # asset → "YYYY-MM-DD"

    async def run(self):
        """Main entry point. Connect all WS feeds and run event loop."""
        tracemalloc.start()
        self._tracemalloc_snapshot = tracemalloc.take_snapshot()
        log("=== Botsy Engine starting ===")
        log(f"Repo: {REPO_DIR}")
        log(f"Python: {sys.executable}")
        log(f"TRADING_ENABLED: {os.environ.get('TRADING_ENABLED', 'false')}")

        # Ensure data directory exists
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Load candle buffer: try disk first (instant), fall back to REST
        await asyncio.to_thread(self._load_or_seed_buffer)

        # Initialize TA engine after buffer has data (lazy import for pandas-ta)
        try:
            from ta_engine import TAEngine
            self.ta_engine = TAEngine(self.candle_buffer)
            log("[TA] Engine initialized with pandas-ta")
        except Exception as e:
            log(f"[TA] TA engine init failed, running without indicators: {e}")
            self.ta_engine = None

        tasks = [
            self._supervise(self.bybit_spot_feed, name="bybit_spot"),
            self._supervise(self.bybit_linear_feed, name="bybit_linear"),
            self._supervise(self.bybit_microstructure_feed, name="bybit_capture"),
            self._supervise(self.polymarket_feed, name="polymarket"),
            self._supervise(self.git_commit_loop, name="git_commit"),
            self._supervise(self.daily_report_check, name="daily_report"),
            self._supervise(self.fallback_timer, name="fallback"),
            self._supervise(self.metrics_writer, name="metrics"),
            self._supervise(self.memory_profiler, name="memory_profiler"),
            self._supervise(self.log_rotator, name="log_rotator"),
            self._verify_orderbook_cache_format(),  # one-shot, no supervision
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _supervise(self, coro_func, *args, name="task"):
        """Restart a coroutine on crash. Re-raises CancelledError for shutdown."""
        while True:
            try:
                await coro_func(*args)
                return  # Normal completion (one-shot tasks)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log(f"CRITICAL: {name} crashed: {e}. Restarting in 10s...")
                await asyncio.sleep(10)

    def _load_or_seed_buffer(self):
        """Load candle buffer from disk snapshot. Fall back to REST if stale."""
        snapshot_path = DATA_DIR / "candle_buffer.json"
        loaded = self.candle_buffer.load_from_disk(snapshot_path, max_age_s=900)
        if loaded > 0:
            log(f"[BUFFER] Loaded {loaded} buffers from disk snapshot")
            return

        log("[BUFFER] No fresh snapshot — seeding from Bybit REST")
        # (buffer_symbol, timeframe, api_category, api_symbol)
        # buffer_symbol uses _linear suffix to match WS feed keys
        seeds = [
            ("BTCUSDT", "1", "spot", "BTCUSDT"),
            ("BTCUSDT", "5", "spot", "BTCUSDT"),
            ("BTCUSDT", "15", "spot", "BTCUSDT"),
            ("ETHUSDT", "1", "spot", "ETHUSDT"),
            ("ETHUSDT", "5", "spot", "ETHUSDT"),
            ("BTCUSDT_linear", "1", "linear", "BTCUSDT"),
            ("BTCUSDT_linear", "5", "linear", "BTCUSDT"),
            ("SOLUSDT", "1", "spot", "SOLUSDT"),
            ("SOLUSDT", "5", "spot", "SOLUSDT"),
            ("DOGEUSDT", "1", "spot", "DOGEUSDT"),
            ("DOGEUSDT", "5", "spot", "DOGEUSDT"),
        ]
        for buf_symbol, tf, category, api_symbol in seeds:
            try:
                count = self.candle_buffer.seed_from_rest(
                    symbol=buf_symbol, timeframe=tf, category=category,
                    api_symbol=api_symbol,
                )
                log(f"[BUFFER] Seeded {buf_symbol}/{tf}m ({category}): {count} candles")
            except Exception as e:
                log(f"[BUFFER] Seed failed {buf_symbol}/{tf}m ({category}): {e}")
        # Save immediately so next restart can use disk
        self.candle_buffer.save_to_disk(snapshot_path)

    # ── Bybit Spot WS Feed (BTC + ETH candle triggers) ─────────────────

    async def bybit_spot_feed(self):
        """Bybit WS v5 spot: BTC/ETH 1m/5m/15m kline.

        1m events feed the buffer + TA engine only (no pipeline dispatch).
        5m/15m closes trigger pipeline dispatch with indicators.
        Validated 2026-04-05: 241ms avg latency on AMS3 VPS.
        """
        import websockets

        uri = "wss://stream.bybit.com/v5/public/spot"
        while True:
            try:
                log(f"[WS] Bybit spot connecting to {uri}...")
                async with websockets.connect(uri, ping_interval=20) as ws:
                    await ws.send(json.dumps({
                        "op": "subscribe",
                        "args": [
                            "kline.1.BTCUSDT", "kline.5.BTCUSDT", "kline.15.BTCUSDT",
                            "kline.1.ETHUSDT", "kline.5.ETHUSDT",
                            "kline.1.SOLUSDT", "kline.5.SOLUSDT",
                            "kline.1.DOGEUSDT", "kline.5.DOGEUSDT",
                        ],
                    }))
                    resp = await ws.recv()
                    log(f"[WS] Bybit spot subscribed: {resp[:200]}")

                    self.metrics["bybit_spot"]["status"] = "connected"

                    async for msg in ws:
                        try:
                            data = json.loads(msg)
                            topic = data.get("topic", "")
                            if not topic.startswith("kline."):
                                continue

                            # Parse topic: "kline.{interval}.{symbol}"
                            parts = topic.split(".")
                            if len(parts) != 3:
                                continue
                            interval = parts[1]
                            symbol = parts[2]
                            kline = data["data"][0]

                            # Feed ALL events to candle buffer
                            candle = self.candle_buffer.on_kline_event(
                                symbol, interval, kline
                            )

                            # Only dispatch on confirmed candles
                            if candle is not None:
                                candle_ts = int(kline["end"])
                                candle_ts = int(kline["end"])
                                latency = int(time.time() * 1000) - candle_ts
                                self.metrics["bybit_spot"]["last_event"] = \
                                    datetime.now(timezone.utc).isoformat()

                                # 1m events feed buffer only, no dispatch or log
                                if interval != "1":
                                    log(f"[ENGINE] Bybit spot {symbol} {interval}m close | "
                                        f"latency={latency}ms")
                                    await self.dispatch(
                                        "bybit_spot", symbol, interval, candle_ts
                                    )
                                    # Daily regime metrics rollover (once/day per asset)
                                    if interval == "5":
                                        asset = None
                                        if symbol == "BTCUSDT":
                                            asset = "BTC"
                                        elif symbol == "ETHUSDT":
                                            asset = "ETH"
                                        if asset:
                                            self._maybe_run_daily_rollover(
                                                asset, symbol, candle_ts
                                            )
                                            # Multi-poll Phase A — fire shadow predictions
                                            # at offsets T+30s..T+270s after close. Pure
                                            # observation; no behavior change. Plan:
                                            # docs/plans/multi_poll_predict_plan.md.
                                            try:
                                                self._spawn_multi_poll(
                                                    asset, symbol, candle_ts
                                                )
                                            except Exception as e:
                                                log(f"[multi_poll] spawn failed: {e}")
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

            except Exception as e:
                self.metrics["bybit_spot"]["status"] = "disconnected"
                self.metrics["bybit_spot"]["reconnects_24h"] += 1
                log(f"[WS] Bybit spot disconnected: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    # ── Bybit Linear WS Feed (perps pipeline) ─────────────────────────

    async def bybit_linear_feed(self):
        """Bybit WS v5 linear: BTCUSDT 1m/5m kline for perps pipeline."""
        import websockets

        uri = "wss://stream.bybit.com/v5/public/linear"
        while True:
            try:
                log(f"[WS] Bybit linear connecting to {uri}...")
                async with websockets.connect(uri, ping_interval=20) as ws:
                    await ws.send(json.dumps({
                        "op": "subscribe",
                        "args": ["kline.1.BTCUSDT", "kline.5.BTCUSDT"],
                    }))
                    resp = await ws.recv()
                    log(f"[WS] Bybit linear subscribed: {resp[:200]}")

                    self.metrics["bybit_linear"]["status"] = "connected"

                    async for msg in ws:
                        try:
                            data = json.loads(msg)
                            topic = data.get("topic", "")
                            if not topic.startswith("kline."):
                                continue

                            parts = topic.split(".")
                            if len(parts) != 3:
                                continue
                            interval = parts[1]
                            symbol = parts[2]
                            kline = data["data"][0]

                            # Feed to buffer (linear category)
                            candle = self.candle_buffer.on_kline_event(
                                f"{symbol}_linear", interval, kline
                            )

                            # Only dispatch 5m confirms
                            if candle is not None and interval == "5":
                                candle_ts = int(kline["end"])
                                latency = int(time.time() * 1000) - candle_ts
                                log(f"[ENGINE] Bybit linear {symbol} {interval}m close | "
                                    f"latency={latency}ms")
                                self.metrics["bybit_linear"]["last_event"] = \
                                    datetime.now(timezone.utc).isoformat()
                                await self.dispatch(
                                    "bybit_linear", symbol, interval, candle_ts
                                )
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

            except Exception as e:
                self.metrics["bybit_linear"]["status"] = "disconnected"
                self.metrics["bybit_linear"]["reconnects_24h"] += 1
                log(f"[WS] Bybit linear disconnected: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    # ── Bybit microstructure tape capture ─────────────────────────────

    async def bybit_microstructure_feed(self):
        """Dedicated WS connection capturing publicTrade, orderbook.50,
        liquidation, and tickers for BTCUSDT to gzipped JSONL on disk.

        Runs on its own connection so a stall on the capture side cannot
        starve the kline dispatch path that feeds live predictions. See
        `src/bybit_ws_capture.py` for details."""
        from bybit_ws_capture import BybitMicrostructureCapture
        cap = BybitMicrostructureCapture(log_fn=log)
        self._bybit_capture = cap
        await cap.run()

    # ── Polymarket CLOB WS Feed ─────���──────────────────────────────────

    async def polymarket_feed(self):
        """Polymarket CLOB WS: live orderbook for active markets."""
        import websockets

        uri = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        while True:
            try:
                log(f"[WS] Polymarket connecting to {uri}...")
                async with websockets.connect(uri, ping_interval=30) as ws:
                    # Get active token IDs from the DB
                    token_ids = self._get_active_token_ids()
                    if not token_ids:
                        log("[WS] Polymarket: no active token IDs found, "
                            "retrying in 60s...")
                        await asyncio.sleep(60)
                        continue

                    # Subscribe to orderbook for active markets
                    sub_msg = {
                        "assets_ids": token_ids,
                        "type": "market",
                    }
                    await ws.send(json.dumps(sub_msg))
                    log(f"[WS] Polymarket subscribed to {len(token_ids)} tokens")

                    self.metrics["polymarket"]["status"] = "connected"

                    async for msg in ws:
                        try:
                            raw = json.loads(msg)
                            # Polymarket sends arrays or single objects
                            events = raw if isinstance(raw, list) else [raw]
                            for data in events:
                                if not isinstance(data, dict):
                                    continue
                                event_type = data.get("event_type", "")
                                if event_type == "book":
                                    self._update_orderbook_cache(data)
                                    self.metrics["polymarket"]["last_event"] = \
                                        datetime.now(timezone.utc).isoformat()
                        except (json.JSONDecodeError, KeyError):
                            continue

            except Exception as e:
                self.metrics["polymarket"]["status"] = "disconnected"
                self.metrics["polymarket"]["reconnects_24h"] += 1
                log(f"[WS] Polymarket disconnected: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    # All Polymarket pipeline DBs — query each for active market tokens
    _POLYMARKET_DB_PATHS = [
        "predictions.db",       # BTC 5m
        "predictions_15m.db",   # BTC 15m
        "predictions_eth.db",   # ETH 5m
    ]

    def _get_active_token_ids(self) -> list:
        """Get CLOB token IDs for currently active (unresolved) markets.

        Queries all Polymarket pipeline DBs so the WS feed subscribes to
        BTC 5m, BTC 15m, AND ETH 5m tokens. Deduplicates (BTC 5m and 15m
        share the same underlying markets).
        """
        import sqlite3
        from clob_depth import get_clob_tokens

        market_ids = set()
        for db_name in self._POLYMARKET_DB_PATHS:
            db_path = DATA_DIR / db_name
            if not db_path.exists():
                continue
            try:
                db = sqlite3.connect(str(db_path))
                db.row_factory = sqlite3.Row
                rows = db.execute("""
                    SELECT DISTINCT m.id FROM markets m
                    WHERE m.resolved = 0
                    ORDER BY m.fetched_at DESC
                    LIMIT 10
                """).fetchall()
                db.close()
                for row in rows:
                    market_ids.add(row["id"])
            except Exception as e:
                log(f"[WS] Polymarket token lookup failed for {db_name}: {e}")

        # Resolve unique market IDs to token IDs via Gamma API
        token_ids = set()
        for market_id in market_ids:
            try:
                tokens = get_clob_tokens(market_id)
                if tokens:
                    if tokens.get("yes"):
                        token_ids.add(tokens["yes"])
                    if tokens.get("no"):
                        token_ids.add(tokens["no"])
            except Exception:
                continue

        return list(token_ids)

    def _update_orderbook_cache(self, data: dict):
        """Update in-memory orderbook cache from WS book event.

        Previous implementation read/parsed/wrote a 1.4MB JSON file on EVERY
        WS event — thousands of times per minute. Now updates an in-memory
        dict; disk flush happens periodically in _flush_orderbook_cache().

        Issue #77: this was likely a major contributor to the ~50MB/hour
        memory growth (transient json.loads/dumps allocations pressuring GC).
        """
        try:
            asset_id = data.get("asset_id", "")
            if not asset_id:
                return

            bids = data.get("bids", [])
            asks = data.get("asks", [])
            best_bid = float(bids[0]["price"]) if bids else None
            best_ask = float(asks[0]["price"]) if asks else None
            mid = (best_bid + best_ask) / 2 if (best_bid and best_ask) else None
            spread = (best_ask - best_bid) if (best_bid and best_ask) else None

            self._orderbook_cache[asset_id] = {
                "mid": mid,
                "spread": spread,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "bids": bids[:5],  # top 5 levels
                "asks": asks[:5],
            }
            self._orderbook_dirty = True

            if mid:
                self._orderbook_ages.append(0)  # just written
                if len(self._orderbook_ages) > 1000:
                    self._orderbook_ages = self._orderbook_ages[-500:]

        except (IndexError, KeyError, ValueError, TypeError) as e:
            log(f"[WS] Polymarket orderbook cache update failed: {e}")

    def _flush_orderbook_cache(self):
        """Write in-memory orderbook cache to disk. Called every 5s by metrics_writer."""
        if not self._orderbook_dirty:
            return
        try:
            cache = {"tokens": self._orderbook_cache}
            tmp = ORDERBOOK_CACHE.with_suffix(".tmp")
            tmp.write_text(json.dumps(cache))
            tmp.rename(ORDERBOOK_CACHE)
            self._orderbook_dirty = False
        except OSError as e:
            log(f"[WS] Polymarket orderbook cache flush failed: {e}")

    async def _verify_orderbook_cache_format(self):
        """Startup guard: seed in-memory cache from disk, verify format within 60s."""
        # Seed in-memory cache from existing disk file
        try:
            if ORDERBOOK_CACHE.exists():
                cache = json.loads(ORDERBOOK_CACHE.read_text())
                if "tokens" in cache:
                    self._orderbook_cache = cache["tokens"]
                    log(f"[CACHE] Seeded in-memory cache from disk: "
                        f"{len(self._orderbook_cache)} tokens")
        except (json.JSONDecodeError, OSError) as e:
            log(f"[CACHE] Could not seed from disk: {e}")

        await asyncio.sleep(60)
        n = len(self._orderbook_cache)
        if n > 0:
            log(f"[CACHE] Per-token orderbook format verified: {n} tokens")
        else:
            log("WARNING: No orderbook data after 60s — WS feed may not be writing")
            log("DIAG|cache_format=missing|age_s=60")

    # ── Event Dispatch ─────────────────────────────────────────────────

    async def dispatch(self, source: str, symbol: str, interval: str,
                       candle_ts: int):
        """Route candle-close event to pipelines. Dedup by (source, symbol, candle_ts)."""
        dedup_key = (source, symbol, candle_ts)
        if dedup_key in self._dispatched:
            return
        self._dispatched.add(dedup_key)

        # Prune old dedup keys
        if len(self._dispatched) > 100:
            self._dispatched = set(list(self._dispatched)[-50:])

        self.last_event_time = time.time()
        key = (source, symbol, interval)
        pipelines = ROUTING.get(key, [])

        if not pipelines:
            log(f"[ENGINE] No routing for {key}")
            return

        # Compute TA indicators from buffer
        indicators = None
        try:
            if self.ta_engine is None:
                raise RuntimeError("TA engine not initialized")
            indicators = self.ta_engine.compute(symbol, interval)
            if indicators:
                log(f"[TA] {symbol}/{interval}m: RSI={indicators.get('rsi_14', '?'):.1f} "
                    f"Z={indicators.get('z_score', '?'):.2f} "
                    f"RVOL={indicators.get('rvol', '?'):.2f} "
                    f"EMA9/21={'↑' if (indicators.get('ema_9') or 0) > (indicators.get('ema_21') or 0) else '↓'}")
            else:
                buf_depth = self.candle_buffer.depth(symbol, interval)
                log(f"[TA] {symbol}/{interval}m: insufficient data ({buf_depth} candles)")
        except Exception as e:
            log(f"[TA] {symbol}/{interval}m computation failed: {e}")

        # Build candle data dict from buffer (replaces REST fetch in pipelines)
        candle_data = None
        buf_candles = self.candle_buffer.get_candles(symbol, interval)
        if buf_candles and len(buf_candles) >= 2:
            closes = [c["close"] for c in buf_candles]
            current_price = closes[-1]
            first_open = buf_candles[0]["open"]
            hour_change = round((current_price - first_open) / first_open * 100, 3) if first_open else 0
            ups = sum(1 for c in buf_candles if c["direction"] == "UP")
            downs = len(buf_candles) - ups
            trend = "up" if ups > downs + 1 else ("down" if downs > ups + 1 else "neutral")
            candle_data = {
                "candles": buf_candles,
                "current_price": current_price,
                "1h_change_pct": hour_change,
                "trend": trend,
            }
            log(f"[BUFFER] {symbol}/{interval}m: {len(buf_candles)} candles → pipeline data built")

        dispatch_start = time.time()
        log(f"[ENGINE] {source} {symbol} {interval}m close | "
            f"dispatching: {', '.join(pipelines)}")

        for pipeline in pipelines:
            self.cycle += 1
            self.metrics["cycles"] = self.cycle
            await self.run_pipeline(pipeline, candle_data=candle_data,
                                    indicators=indicators)

        # Run Strategy Lab (shadow strategies, never affects production)
        try:
            from strategy_lab import strategy_lab_run
            await asyncio.to_thread(
                strategy_lab_run, pipelines, symbol, interval,
                candle_data, indicators,
            )
        except Exception as e:
            log(f"[STRATEGY_LAB] {e}")

        # Track dispatch latency
        latency_ms = (time.time() - dispatch_start) * 1000
        self._latencies.append(latency_ms)
        if len(self._latencies) > 1000:
            self._latencies = self._latencies[-500:]

    async def run_pipeline(self, name: str, candle_data: dict = None,
                           indicators: dict = None):
        """Run a pipeline in a thread (they're synchronous)."""
        runners = {
            "btc_5m": "ci_run",
            "btc_15m": "ci_run_15m",
            "eth_5m": "ci_run_eth",
            "bybit": "ci_run_bybit",
            "kalshi": "ci_run_kalshi",
            "hl": "ci_run_hl",
            # Multi-pair perps: (module, function) tuples
            "eth_bybit": ("ci_run_perp", "main_eth_bybit"),
            "eth_hl": ("ci_run_perp", "main_eth_hl"),
            "sol_bybit": ("ci_run_perp", "main_sol_bybit"),
            "sol_hl": ("ci_run_perp", "main_sol_hl"),
            "doge_bybit": ("ci_run_perp", "main_doge_bybit"),
            "doge_hl": ("ci_run_perp", "main_doge_hl"),
        }
        runner = runners.get(name)
        if not runner:
            log(f"[ENGINE] Unknown pipeline: {name}")
            return

        try:
            import importlib
            if isinstance(runner, tuple):
                # (module_name, function_name) — generic perp pipelines
                module_name, func_name = runner
                mod = importlib.import_module(module_name)
                func = getattr(mod, func_name)
                await asyncio.to_thread(func, candle_data=candle_data,
                                        indicators=indicators)
            else:
                # String — legacy pipelines with main()
                mod = importlib.import_module(runner)
                await asyncio.to_thread(mod.main, candle_data=candle_data,
                                        indicators=indicators)
            log(f"[{name}] OK")
        except Exception as e:
            log(f"[{name}] FAILED: {e}")

    # ── Fallback Timer ─────────────────────────────────────────────────

    async def fallback_timer(self):
        """If no WS event for 6 min, force-run all pipelines."""
        while True:
            await asyncio.sleep(30)
            elapsed = time.time() - self.last_event_time
            if elapsed > FALLBACK_TIMEOUT_S:
                log(f"WARN: No WS event for {int(elapsed)}s — "
                    f"fallback firing all pipelines")
                self.metrics["fallback_fires_24h"] += 1
                self.last_event_time = time.time()
                for name in ["btc_5m", "btc_15m", "eth_5m", "bybit", "kalshi", "hl",
                             "eth_bybit", "eth_hl", "sol_bybit", "sol_hl",
                             "doge_bybit", "doge_hl"]:
                    await self.run_pipeline(name)

    # ── Git Commit Loop ─────────���──────────────────────────────────────

    async def git_commit_loop(self):
        """Commit and push data/ every 5 minutes."""
        while True:
            await asyncio.sleep(GIT_COMMIT_INTERVAL_S)
            try:
                await asyncio.to_thread(self._git_commit_push)
            except Exception as e:
                log(f"WARNING: git commit loop error: {e}")

    def _spawn_multi_poll(self, asset: str, symbol: str, candle_ts_ms: int):
        """Fire shadow predictions at fixed offsets after a 5m close.

        Per docs/plans/multi_poll_predict_plan.md Phase A. Pure observation
        — does not affect production prediction, conviction gating, or
        trade execution. Logs to multi_poll_predictions table.

        Spawns as a background asyncio.Task so the WS feed loop continues
        processing other events while polls fire over the next 4.5 minutes.
        Failures inside the task are caught + logged in schedule_polls
        itself, so they cannot propagate to the WS handler.
        """
        from multi_poll_predict import schedule_polls

        # Per-asset DB path. BTC writes alongside the main predictions
        # table; ETH writes to its own DB. Multi-poll lives next to the
        # asset's existing prediction data for join convenience at
        # analysis time (Phase B).
        if asset == "BTC":
            db_path = str(DATA_DIR / "predictions.db")
        elif asset == "ETH":
            db_path = str(DATA_DIR / "predictions_eth.db")
        else:
            return  # Phase A scope: BTC + ETH 5m only

        cycle_close_at = datetime.fromtimestamp(
            candle_ts_ms / 1000, tz=timezone.utc
        ).isoformat()
        cycle = int(candle_ts_ms / 300_000)  # 5m cycle index

        asyncio.create_task(
            schedule_polls(
                self,
                db_path=db_path,
                cycle=cycle,
                cycle_close_at=cycle_close_at,
                asset=asset,
                symbol=symbol,
                interval="5",
            )
        )

    def _maybe_run_daily_rollover(self, asset: str, symbol: str, candle_ts_ms: int):
        """Fire asset_daily computation when UTC date rolls over for `asset`.

        Called from the bybit_spot dispatch path on every confirmed 5m candle.
        Idempotent per (asset, date) via _asset_daily_last_date guard. The
        actual REST fetch + DB write runs in a thread so we don't block the
        WS event loop.

        `candle_ts_ms` is the candle CLOSE time, so today's in-progress day is
        `today`. We want to compute metrics for the PRIOR day the first time
        we see a candle whose close is on a new UTC date.
        """
        current_date = datetime.fromtimestamp(
            candle_ts_ms / 1000, tz=timezone.utc
        ).strftime("%Y-%m-%d")

        last = self._asset_daily_last_date.get(asset)
        if last is None:
            # First candle for this asset this run: seed without triggering
            # a fetch (backfill tool handles history).
            self._asset_daily_last_date[asset] = current_date
            return
        if last == current_date:
            return  # same UTC day, nothing to do

        # Rollover detected: last → current_date. Compute for `last` (the
        # day that just ended) in a background thread.
        self._asset_daily_last_date[asset] = current_date
        log(f"[DAILY] {asset} UTC rollover {last} → {current_date}; "
            f"computing asset_daily for {last}")
        asyncio.create_task(
            asyncio.to_thread(self._compute_and_record_daily, asset, symbol, last)
        )

    def _compute_and_record_daily(self, asset: str, symbol: str, date: str):
        """Thread-safe: fetch prior day's 5m bars from Bybit and record metrics."""
        try:
            import sqlite3
            from asset_daily import (
                compute_daily, fetch_bybit_day_5m, init_table, record,
            )
            df = fetch_bybit_day_5m(symbol, date, category="linear")
            if len(df) < 10:
                log(f"[DAILY] {asset} {date}: only {len(df)} bars, skipping")
                return
            # Prior close for true_range_pct — fetch from DB if present.
            db_path = DATA_DIR / "asset_daily.db"
            db = sqlite3.connect(str(db_path))
            init_table(db)
            prior = db.execute(
                "SELECT close FROM asset_daily WHERE asset=? "
                "AND date < ? ORDER BY date DESC LIMIT 1",
                (asset, date),
            ).fetchone()
            prior_close = float(prior[0]) if prior else None
            metrics = compute_daily(df, prior_close=prior_close)
            record(db, asset=asset, date=date, metrics=metrics)
            db.close()
            log(
                f"[DAILY] {asset} {date} recorded: "
                f"body={metrics['body_pct']:+.4f} "
                f"rvol={metrics['realized_vol']:.4f} "
                f"label={metrics['trend_label']}"
            )
        except Exception as e:
            log(f"[DAILY] {asset} {date} failed: {e}")

    def _checkpoint_all_dbs(self):
        """Flush all WAL journals so .db files are self-contained for git.

        Opens a fresh connection per DB (doesn't interfere with pipeline
        connections), checkpoints with TRUNCATE mode (waits for writers,
        flushes all pages, deletes WAL file). Per-DB errors are logged
        but don't block other DBs or the commit.
        """
        import sqlite3
        for db_path in sorted(DATA_DIR.glob("*.db")):
            try:
                conn = sqlite3.connect(str(db_path))
                conn.execute("PRAGMA busy_timeout=3000")
                result = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                if result and result[0] == 1:
                    log(f"WAL checkpoint blocked for {db_path.name} (busy)")
                conn.close()
            except Exception as e:
                log(f"WARNING: WAL checkpoint failed for {db_path.name}: {e}")

    def _git_head(self) -> str:
        """Return current HEAD short SHA, or '?' on error."""
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, timeout=5, cwd=str(REPO_DIR),
            )
            return r.stdout.decode().strip() or "?"
        except Exception:
            return "?"

    def _git_commit_push(self):
        """Synchronous git add + commit + push.

        Order: checkpoint WALs → add → diff check → commit → push → on push
        fail, fetch+reset+cherry-pick (NOT pull --rebase, which silently
        clobbered state in the 2026-04-28 incident).

        Discipline (lessons from 2026-04-28):
          - HEAD is logged before and after every state-changing step
          - On unexpected divergence, write a marker file (do NOT try to
            auto-recover) — next cycle bails until human inspects
          - Never use -X theirs in retry; conflicts mean human attention
        """
        try:
            os.chdir(str(REPO_DIR))

            head_at_start = self._git_head()

            # If a marker file exists, a previous cycle bailed. Don't
            # commit until a human acknowledges (delete the marker).
            bail_marker = REPO_DIR / "data" / "GIT_COMMIT_BAIL"
            if bail_marker.exists():
                # Throttle the warning so we don't spam every cycle
                if int(time.time()) % 1800 < 6:  # once per ~30 min
                    log(f"WARNING: git commit loop is quiesced — "
                        f"{bail_marker} exists. Inspect, then delete to resume.")
                return

            # Flush WAL journals before snapshotting DBs
            self._checkpoint_all_dbs()

            # Stage data files
            subprocess.run(
                ["git", "add", "data/", "docs/daily/"],
                capture_output=True, timeout=10,
            )

            # Remove any accidentally tracked WAL/SHM files
            subprocess.run(
                ["git", "rm", "--cached", "--ignore-unmatch", "--quiet",
                 "data/*.db-wal", "data/*.db-shm"],
                capture_output=True, timeout=10,
            )

            # Check if there are changes to commit
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                capture_output=True,
            )
            if result.returncode == 0:
                return  # Nothing to commit

            # Commit FIRST (before fetch — keeps the working tree clean)
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            msg = f"Auto: cycle update {ts}"
            result = subprocess.run(
                ["git", "commit", "-m", msg],
                capture_output=True, timeout=30,
            )
            if result.returncode != 0:
                log(f"WARNING: Commit failed: {result.stderr.decode()[:200]}")
                return

            head_after_commit = self._git_head()

            # Push (first attempt)
            result = subprocess.run(
                ["git", "push"],
                capture_output=True, timeout=60,
            )
            if result.returncode == 0:
                log(f"Pushed {head_after_commit} (was {head_at_start})")
                return

            # Push failed — origin moved. Recover SAFELY:
            #   1. fetch origin
            #   2. compare: is local HEAD an ancestor of remote? If yes,
            #      we're behind and just need to fast-forward; reset hard
            #      to remote and re-apply our cycle commit on top.
            #   3. else: we and remote both moved. Conflict territory —
            #      do NOT auto-resolve. Write bail marker and quiesce.
            log(f"WARNING: Push failed at HEAD={head_after_commit}. "
                f"Investigating remote state.")
            subprocess.run(
                ["git", "fetch", "origin"],
                capture_output=True, timeout=30,
            )

            our_commit = head_after_commit
            # Drop our cycle commit so we can compare cleanly
            subprocess.run(
                ["git", "reset", "--soft", "HEAD~1"],
                capture_output=True, timeout=10,
            )
            head_pre_reapply = self._git_head()

            # Is HEAD now an ancestor of origin/main? If yes, fast-forward
            # is safe — remote has commits we don't, but we have nothing
            # they don't (other than the cycle commit we just unstacked).
            ancestor_check = subprocess.run(
                ["git", "merge-base", "--is-ancestor",
                 "HEAD", "origin/main"],
                capture_output=True, timeout=10,
            )
            if ancestor_check.returncode == 0:
                # Safe path: reset to origin/main, redo commit, push.
                # Our staged changes survive --soft reset.
                subprocess.run(
                    ["git", "reset", "--soft", "origin/main"],
                    capture_output=True, timeout=10,
                )
                # Re-stage everything (data/ may have changed under us
                # if origin commits touched data/, which auto-commits do)
                subprocess.run(
                    ["git", "add", "data/", "docs/daily/"],
                    capture_output=True, timeout=10,
                )
                # Re-check if anything to commit
                redo_check = subprocess.run(
                    ["git", "diff", "--cached", "--quiet"],
                    capture_output=True,
                )
                if redo_check.returncode == 0:
                    log(f"Push retry: nothing left to commit after "
                        f"fast-forward to origin/main "
                        f"(was {our_commit}, now {self._git_head()})")
                    return
                redo = subprocess.run(
                    ["git", "commit", "-m", msg],
                    capture_output=True, timeout=30,
                )
                if redo.returncode != 0:
                    log(f"WARNING: redo commit failed: "
                        f"{redo.stderr.decode()[:200]}")
                    return
                redo_push = subprocess.run(
                    ["git", "push"],
                    capture_output=True, timeout=60,
                )
                if redo_push.returncode == 0:
                    log(f"Pushed after fast-forward: HEAD={self._git_head()} "
                        f"(was {our_commit}, behind {head_pre_reapply})")
                else:
                    log(f"ERROR: redo push failed: "
                        f"{redo_push.stderr.decode()[:200]}")
                return

            # Unsafe path: local and remote both diverged. Don't guess.
            # Write a marker so the engine quiesces git_commit_loop until
            # a human inspects. Code+data still flow inside the engine;
            # only the commit loop is paused.
            log(f"ERROR: local HEAD ({head_pre_reapply}) is NOT an "
                f"ancestor of origin/main. Divergence detected. Writing "
                f"bail marker {bail_marker}; auto-commit quiesced.")
            try:
                bail_marker.write_text(
                    f"git divergence at {ts}\n"
                    f"local HEAD: {head_pre_reapply}\n"
                    f"unstacked cycle commit: {our_commit}\n"
                    f"head_at_start_of_cycle: {head_at_start}\n"
                    "delete this file after manual inspection to resume.\n"
                )
            except Exception as e:
                log(f"WARNING: bail marker write failed: {e}")

        except Exception as e:
            log(f"WARNING: git commit/push failed: {e}")

    # ── Daily Report ────────────────────────────────────���──────────────

    async def daily_report_check(self):
        """Run daily report shortly after UTC midnight (00:05 UTC).

        Previously fired at 12:00 UTC, which delayed the prior-day summary
        by 12 hours. The 5-minute buffer after midnight gives in-flight
        cycles and the asset_daily rollover hook time to settle.
        """
        while True:
            now = datetime.now(timezone.utc)
            if (now.hour == 0 and now.minute >= 5
                    and now.strftime("%Y-%m-%d") != self.last_report_date):
                log("[Daily Report] Generating...")
                self.last_report_date = now.strftime("%Y-%m-%d")
                try:
                    await asyncio.to_thread(self._run_daily_report)
                    log("[Daily Report] OK")
                except Exception as e:
                    log(f"[Daily Report] FAILED: {e}")
            await asyncio.sleep(60)

    def _run_daily_report(self):
        """Synchronous daily report generation."""
        import daily_report
        daily_report.generate_report()

    # ── Metrics Writer ─────────────────────────────────────────────────

    async def metrics_writer(self):
        """Write ws_metrics.json every 60s for dashboard + daily report.
        Also persists candle buffer and orderbook cache to disk."""
        while True:
            await asyncio.sleep(METRICS_INTERVAL_S)
            self._compute_percentiles()
            try:
                tmp = METRICS_FILE.with_suffix(".tmp")
                tmp.write_text(json.dumps(self.metrics, indent=2))
                tmp.rename(METRICS_FILE)
            except OSError as e:
                log(f"WARNING: metrics write failed: {e}")
            # Persist candle buffer for fast restart (no REST needed)
            try:
                self.candle_buffer.save_to_disk(DATA_DIR / "candle_buffer.json")
            except Exception as e:
                log(f"WARNING: buffer save failed: {e}")
            # Flush orderbook cache to disk (was per-event, now batched)
            try:
                self._flush_orderbook_cache()
            except Exception as e:
                log(f"WARNING: orderbook flush failed: {e}")

    def _compute_percentiles(self):
        """Compute p50/p95 from recent latency samples."""
        if self._latencies:
            sorted_lat = sorted(self._latencies)
            n = len(sorted_lat)
            self.metrics["dispatch_latency_ms"] = {
                "p50": round(sorted_lat[n // 2]),
                "p95": round(sorted_lat[int(n * 0.95)]) if n >= 20 else round(sorted_lat[-1]),
                "samples": n,
            }
        if self._orderbook_ages:
            sorted_ages = sorted(self._orderbook_ages)
            n = len(sorted_ages)
            self.metrics["orderbook_age_ms"] = {
                "p50": round(sorted_ages[n // 2]),
                "p95": round(sorted_ages[int(n * 0.95)]) if n >= 20 else round(sorted_ages[-1]),
                "samples": n,
            }

    # ── Log Rotation ──────────���────────────────────────────────────────

    # ── Memory Profiler (Issue #77) ──────────────────────────────────

    async def memory_profiler(self):
        """Log memory usage and top allocators every 30 min.

        Uses tracemalloc for Python heap analysis and RSS from resource
        module for total process memory. Helps identify the ~50MB/hour
        growth reported in issue #77.
        """
        while True:
            await asyncio.sleep(1800)  # every 30 min
            try:
                # Force glibc to release unused memory back to OS (issue #77).
                # Python heap stays ~90MB but RSS grows 500MB+ from fragmented
                # glibc arenas holding freed pandas/numpy buffers.
                if _LIBC_MALLOC_TRIM is not None:
                    gc.collect()
                    trimmed = _LIBC_MALLOC_TRIM(0)
                    log(f"[MEM] malloc_trim(0) returned {trimmed} "
                        f"({'freed memory' if trimmed else 'no-op'})")

                # RSS (total process memory)
                rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                # macOS returns bytes, Linux returns KB
                if sys.platform == "darwin":
                    rss_mb = rss_kb / (1024 * 1024)
                else:
                    rss_mb = rss_kb / 1024

                # tracemalloc: current snapshot vs baseline
                current = tracemalloc.take_snapshot()
                current = current.filter_traces((
                    tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
                    tracemalloc.Filter(False, "<frozen importlib._bootstrap_external>"),
                ))
                stats = current.compare_to(self._tracemalloc_snapshot, "lineno")

                # Python heap size
                traced_current, traced_peak = tracemalloc.get_traced_memory()

                log(f"[MEM] RSS={rss_mb:.0f}MB | "
                    f"Python heap={traced_current/1024/1024:.1f}MB "
                    f"(peak={traced_peak/1024/1024:.1f}MB) | "
                    f"GC objects={len(gc.get_objects())}")

                # Top 10 growth lines since engine start
                log("[MEM] Top 10 growth lines since start:")
                for stat in stats[:10]:
                    log(f"  {stat}")

                # Also log top 5 by current size (lineno grouping)
                top_current = current.statistics("lineno")
                log("[MEM] Top 5 current allocations:")
                for stat in top_current[:5]:
                    log(f"  {stat}")

            except Exception as e:
                log(f"[MEM] profiler error: {e}")

    # ── Log Rotation ─────────────────────────────────────────────────

    async def log_rotator(self):
        """Rotate log file when it exceeds 50k lines (keep last 10k)."""
        while True:
            await asyncio.sleep(3600)  # check every hour
            try:
                if LOG_FILE.exists():
                    lines = LOG_FILE.read_text().splitlines()
                    if len(lines) > 50000:
                        LOG_FILE.write_text("\n".join(lines[-10000:]) + "\n")
                        log("Log rotated (kept last 10k lines)")
            except OSError:
                pass


# ── Entry Point ────────��───────────────────────────────────────────────

def main():
    """Entry point for both CLI and systemd."""
    # Load .env
    env_file = REPO_DIR / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
        except ImportError:
            # Manual .env loading
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        os.environ[key.strip()] = value.strip().strip('"').strip("'")

    # PID lock — prevent dual engine processes (incident #66)
    try:
        acquire_pid_lock()
    except PIDLockError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)

    engine = BotsyEngine()
    asyncio.run(engine.run())


if __name__ == "__main__":
    main()
