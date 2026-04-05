#!/usr/bin/env python3
"""
botsy_engine.py — Async websocket-driven trading engine.

Replaces vps-loop.sh (bash while-loop with sleep 300) with an event-driven
process that reacts to exchange candle-close events in real-time.

Three WS feeds:
  1. Polygon.io — BTC/ETH spot 5m candle triggers (sub-20ms latency)
  2. Bybit v5   — BTC linear 5m kline (perps pipeline)
  3. Polymarket  — Live CLOB orderbook (kills stale snapshot problem)

Pipelines (existing code, called as functions via asyncio.to_thread):
  - BTC 5m:  ci_run.main()       — triggered by Polygon BTC candle close
  - BTC 15m: ci_run_15m.main()   — triggered every 3rd BTC candle close
  - ETH 5m:  ci_run_eth.main()   — triggered by Polygon ETH candle close
  - Bybit:   ci_run_bybit.main() — triggered by Bybit linear candle close
  - Kalshi:  ci_run_kalshi.main() — triggered by Polygon BTC candle close

Usage:
    python src/botsy_engine.py
    # Or via systemd: systemctl start botsy
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure src/ is on the path for pipeline imports
SRC_DIR = Path(__file__).parent
REPO_DIR = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))

DATA_DIR = REPO_DIR / "data"
LOG_DIR = REPO_DIR / "logs"
LOG_FILE = LOG_DIR / "loop.log"
METRICS_FILE = DATA_DIR / "ws_metrics.json"
ORDERBOOK_CACHE = DATA_DIR / "live_orderbook.json"

# Routing: (source, symbol, interval) -> list of pipeline names
# Bybit WS v5 handles all candle triggers (241ms avg latency, validated 2026-04-05)
ROUTING = {
    ("bybit_spot", "BTCUSDT", "5"):   ["btc_5m", "btc_15m_check", "kalshi"],
    ("bybit_spot", "ETHUSDT", "5"):   ["eth_5m"],
    ("bybit_linear", "BTCUSDT", "5"): ["bybit"],
}

# Fallback timer: force-run if no WS event for this many seconds
FALLBACK_TIMEOUT_S = 360  # 6 minutes

# Metrics write interval
METRICS_INTERVAL_S = 60

# Git commit interval
GIT_COMMIT_INTERVAL_S = 300  # 5 minutes


def log(msg: str):
    """Log with UTC timestamp to both stdout and log file."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


class BotsyEngine:
    def __init__(self):
        self.cycle = 0
        self.last_report_date = ""
        self.fifteenth_min_counter = 0
        self.last_event_time = time.time()
        self._dispatched: set = set()  # dedup: (source, symbol, candle_ts)

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

    async def run(self):
        """Main entry point. Connect all WS feeds and run event loop."""
        log("=== Botsy Engine starting ===")
        log(f"Repo: {REPO_DIR}")
        log(f"Python: {sys.executable}")
        log(f"TRADING_ENABLED: {os.environ.get('TRADING_ENABLED', 'false')}")

        # Ensure data directory exists
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        tasks = [
            self.bybit_spot_feed(),
            self.bybit_linear_feed(),
            self.polymarket_feed(),
            self.git_commit_loop(),
            self.daily_report_check(),
            self.fallback_timer(),
            self.metrics_writer(),
            self.log_rotator(),
        ]
        await asyncio.gather(*tasks)

    # ── Bybit Spot WS Feed (BTC + ETH candle triggers) ─────────────────

    async def bybit_spot_feed(self):
        """Bybit WS v5 spot: BTC/ETH 5m kline triggers.

        Validated 2026-04-05: 241ms avg latency on AMS3 VPS.
        Replaces Polygon.io ($200/mo saved).
        """
        import websockets

        uri = "wss://stream.bybit.com/v5/public/spot"
        while True:
            try:
                log(f"[WS] Bybit spot connecting to {uri}...")
                async with websockets.connect(uri, ping_interval=20) as ws:
                    await ws.send(json.dumps({
                        "op": "subscribe",
                        "args": ["kline.5.BTCUSDT", "kline.5.ETHUSDT"],
                    }))
                    resp = await ws.recv()
                    log(f"[WS] Bybit spot subscribed: {resp[:200]}")

                    self.metrics["bybit_spot"]["status"] = "connected"

                    async for msg in ws:
                        try:
                            data = json.loads(msg)
                            topic = data.get("topic", "")
                            if topic.startswith("kline.5."):
                                kline = data["data"][0]
                                if kline.get("confirm"):
                                    symbol = topic.replace("kline.5.", "")
                                    candle_ts = int(kline["end"])
                                    latency = int(time.time() * 1000) - candle_ts
                                    log(f"[ENGINE] Bybit spot {symbol} 5m close | "
                                        f"latency={latency}ms")
                                    self.metrics["bybit_spot"]["last_event"] = \
                                        datetime.now(timezone.utc).isoformat()
                                    await self.dispatch(
                                        "bybit_spot", symbol, "5", candle_ts
                                    )
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

            except Exception as e:
                self.metrics["bybit_spot"]["status"] = "disconnected"
                self.metrics["bybit_spot"]["reconnects_24h"] += 1
                log(f"[WS] Bybit spot disconnected: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    # ── Bybit Linear WS Feed (perps pipeline) ─────────────────────────

    async def bybit_linear_feed(self):
        """Bybit WS v5 linear: BTCUSDT 5m kline for perps pipeline."""
        import websockets

        uri = "wss://stream.bybit.com/v5/public/linear"
        while True:
            try:
                log(f"[WS] Bybit linear connecting to {uri}...")
                async with websockets.connect(uri, ping_interval=20) as ws:
                    await ws.send(json.dumps({
                        "op": "subscribe",
                        "args": ["kline.5.BTCUSDT"],
                    }))
                    resp = await ws.recv()
                    log(f"[WS] Bybit linear subscribed: {resp[:200]}")

                    self.metrics["bybit_linear"]["status"] = "connected"

                    async for msg in ws:
                        try:
                            data = json.loads(msg)
                            topic = data.get("topic", "")
                            if topic == "kline.5.BTCUSDT":
                                kline = data["data"][0]
                                if kline.get("confirm"):
                                    candle_ts = int(kline["end"])
                                    latency = int(time.time() * 1000) - candle_ts
                                    log(f"[ENGINE] Bybit linear BTCUSDT 5m close | "
                                        f"latency={latency}ms")
                                    self.metrics["bybit_linear"]["last_event"] = \
                                        datetime.now(timezone.utc).isoformat()
                                    await self.dispatch(
                                        "bybit_linear", "BTCUSDT", "5", candle_ts
                                    )
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

            except Exception as e:
                self.metrics["bybit_linear"]["status"] = "disconnected"
                self.metrics["bybit_linear"]["reconnects_24h"] += 1
                log(f"[WS] Bybit linear disconnected: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

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

    def _get_active_token_ids(self) -> list:
        """Get CLOB token IDs for currently active (unresolved) markets."""
        import sqlite3
        token_ids = []
        db_path = DATA_DIR / "predictions.db"
        if not db_path.exists():
            return []
        try:
            db = sqlite3.connect(str(db_path))
            db.row_factory = sqlite3.Row
            # Get recent unresolved markets
            rows = db.execute("""
                SELECT DISTINCT m.id FROM markets m
                WHERE m.resolved = 0
                ORDER BY m.fetched_at DESC
                LIMIT 10
            """).fetchall()
            db.close()

            # Resolve token IDs via Gamma API
            from clob_depth import get_clob_tokens
            for row in rows:
                market_id = row["id"]
                try:
                    tokens = get_clob_tokens(market_id)
                    if tokens:
                        if tokens.get("yes"):
                            token_ids.append(tokens["yes"])
                        if tokens.get("no"):
                            token_ids.append(tokens["no"])
                except Exception:
                    continue
        except Exception as e:
            log(f"[WS] Polymarket token lookup failed: {e}")
        return token_ids

    def _update_orderbook_cache(self, data: dict):
        """Write live orderbook to data/live_orderbook.json for trade.py."""
        try:
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            best_bid = float(bids[0]["price"]) if bids else None
            best_ask = float(asks[0]["price"]) if asks else None
            mid = (best_bid + best_ask) / 2 if (best_bid and best_ask) else None
            spread = (best_ask - best_bid) if (best_bid and best_ask) else None

            cache = {
                "market": data.get("market", ""),
                "asset_id": data.get("asset_id", ""),
                "mid": mid,
                "spread": spread,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "bids": bids[:5],  # top 5 levels
                "asks": asks[:5],
            }

            # Atomic write via temp file
            tmp = ORDERBOOK_CACHE.with_suffix(".tmp")
            tmp.write_text(json.dumps(cache))
            tmp.rename(ORDERBOOK_CACHE)

            if mid:
                age_ms = 0  # just written
                self._orderbook_ages.append(age_ms)
                # Keep last 1000
                if len(self._orderbook_ages) > 1000:
                    self._orderbook_ages = self._orderbook_ages[-500:]

        except (IndexError, KeyError, ValueError, TypeError) as e:
            log(f"[WS] Polymarket orderbook cache update failed: {e}")

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

        dispatch_start = time.time()
        pipeline_names = [p for p in pipelines if p != "btc_15m_check"]
        log(f"[ENGINE] {source} {symbol} {interval}m close | "
            f"dispatching: {', '.join(pipeline_names)}")

        for pipeline in pipelines:
            self.cycle += 1
            self.metrics["cycles"] = self.cycle
            await self.run_pipeline(pipeline)

        # Track dispatch latency
        latency_ms = (time.time() - dispatch_start) * 1000
        self._latencies.append(latency_ms)
        if len(self._latencies) > 1000:
            self._latencies = self._latencies[-500:]

    async def run_pipeline(self, name: str):
        """Run a pipeline in a thread (they're synchronous)."""
        if name == "btc_15m_check":
            await asyncio.to_thread(self._maybe_run_15m)
            return

        runners = {
            "btc_5m": "ci_run",
            "eth_5m": "ci_run_eth",
            "bybit": "ci_run_bybit",
            "kalshi": "ci_run_kalshi",
        }
        module_name = runners.get(name)
        if not module_name:
            log(f"[ENGINE] Unknown pipeline: {name}")
            return

        try:
            import importlib
            mod = importlib.import_module(module_name)
            await asyncio.to_thread(mod.main)
            log(f"[{name}] OK")
        except Exception as e:
            log(f"[{name}] FAILED: {e}")

    def _maybe_run_15m(self):
        """Only run 15m every 3rd BTC 5m close."""
        self.fifteenth_min_counter += 1
        if self.fifteenth_min_counter % 3 == 0:
            try:
                import ci_run_15m
                ci_run_15m.main()
                log("[btc_15m] OK")
            except Exception as e:
                log(f"[btc_15m] FAILED: {e}")

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
                for name in ["btc_5m", "eth_5m", "bybit", "kalshi"]:
                    await self.run_pipeline(name)
                # Also run 15m check
                await asyncio.to_thread(self._maybe_run_15m)

    # ── Git Commit Loop ─────────���──────────────────────────────────────

    async def git_commit_loop(self):
        """Commit and push data/ every 5 minutes."""
        while True:
            await asyncio.sleep(GIT_COMMIT_INTERVAL_S)
            await asyncio.to_thread(self._git_commit_push)

    def _git_commit_push(self):
        """Synchronous git add + commit + push."""
        try:
            os.chdir(str(REPO_DIR))

            # Pull latest first
            subprocess.run(
                ["git", "pull", "--rebase"],
                capture_output=True, timeout=30,
            )

            # Stage data files
            subprocess.run(
                ["git", "add", "data/"],
                capture_output=True, timeout=10,
            )

            # Check if there are changes
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                capture_output=True,
            )
            if result.returncode == 0:
                log("No changes to commit")
                return

            # Commit
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            msg = f"Auto: cycle update {ts}"
            result = subprocess.run(
                ["git", "commit", "-m", msg],
                capture_output=True, timeout=30,
            )
            if result.returncode != 0:
                log(f"WARNING: Commit failed: {result.stderr.decode()[:200]}")
                return

            # Push
            result = subprocess.run(
                ["git", "push"],
                capture_output=True, timeout=60,
            )
            if result.returncode != 0:
                log("WARNING: Push failed — retrying with pull --rebase")
                subprocess.run(
                    ["git", "pull", "--rebase"],
                    capture_output=True, timeout=30,
                )
                subprocess.run(
                    ["git", "push"],
                    capture_output=True, timeout=60,
                )
            else:
                log("Pushed changes")

        except Exception as e:
            log(f"WARNING: git commit/push failed: {e}")

    # ── Daily Report ────────────────────────────────────���──────────────

    async def daily_report_check(self):
        """Run daily report at 12:00 UTC."""
        while True:
            now = datetime.now(timezone.utc)
            if now.hour == 12 and now.strftime("%Y-%m-%d") != self.last_report_date:
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
        """Write ws_metrics.json every 60s for dashboard + daily report."""
        while True:
            await asyncio.sleep(METRICS_INTERVAL_S)
            self._compute_percentiles()
            try:
                tmp = METRICS_FILE.with_suffix(".tmp")
                tmp.write_text(json.dumps(self.metrics, indent=2))
                tmp.rename(METRICS_FILE)
            except OSError as e:
                log(f"WARNING: metrics write failed: {e}")

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

    engine = BotsyEngine()
    asyncio.run(engine.run())


if __name__ == "__main__":
    main()
