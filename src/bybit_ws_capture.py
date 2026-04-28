"""
bybit_ws_capture.py — Microstructure tape capture for Bybit v5 linear.

After seven signal classes derived from kline+REST data all failed on
BTCUSDT 5m perps, the only data stack we haven't tested is the
microstructure tape that the Bybit WebSocket publishes in real time.
This module opens a dedicated WS connection (separate from the kline
feed so it can't destabilize prediction dispatch) and captures four
public topics to rotating gzipped JSONL files on disk.

Topics captured (all public, no auth):
  - publicTrade.BTCUSDT    — every taker print with side+size+price.
                              Source for Cumulative Volume Delta (CVD),
                              taker aggression, trade imbalance.
  - orderbook.50.BTCUSDT   — L2 top-50 snapshots + deltas (~20ms).
                              Source for book imbalance, spoof detection,
                              depth-at-price, real-time support/resistance.
  - liquidation.BTCUSDT    — every forced close. Bybit publishes this
                              stream explicitly; it's the single most
                              documented retail-accessible edge on Bybit.
  - tickers.BTCUSDT        — mark price, index price, funding rate,
                              open interest at ~100ms cadence. Gives
                              intra-bar funding instead of 8h snapshots.

Output layout:
  data/bybit_capture/
    publicTrade/2026-04-08T14.jsonl.gz
    orderbook/2026-04-08T14.jsonl.gz
    liquidation/2026-04-08T14.jsonl.gz
    tickers/2026-04-08T14.jsonl.gz

Files are rotated hourly (UTC). Each line is one raw WS payload plus a
local-receipt timestamp (`_rx_ms`) injected at capture time so downstream
analysis can measure our own processing latency without depending on
Bybit clocks.

Retention: engine process doesn't delete anything; a cron or manual
policy prunes files older than N days. Rough sizing (BTCUSDT linear):
  publicTrade:  ~100-200 MB/day
  orderbook:    ~200-400 MB/day (depth deltas)
  liquidation:  < 1 MB/day
  tickers:      ~20-40 MB/day
Total: ~350-650 MB/day uncompressed; ~50-100 MB/day after gzip-on-close.

This module is imported and supervised by botsy_engine.py alongside the
kline feeds. It has no dependency on anything else in src/ — it's a
pure writer.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
CAPTURE_DIR = ROOT / "data" / "bybit_capture"

# Retention discipline. The 2026-04-24 incident: 16 days of capture grew
# to 3.5 GB on a 24 GB disk that hit 100% full, crashlooping the engine
# for 5 days. The docstring above had always called for "a cron or manual
# policy" — never wired. We now self-prune at every hourly rotation.
# 7 days = ~1 GB at current sizing, well within disk headroom.
RETENTION_DAYS = 7

# Topics we subscribe to. Keep this list small — each topic is a
# separate file stream and adds to reconnect risk.
TOPICS = [
    ("publicTrade", "publicTrade.BTCUSDT"),
    ("orderbook", "orderbook.50.BTCUSDT"),
    # Bybit v5 renamed the old `liquidation.*` stream to `allLiquidation.*`
    # (batched, event-driven). Old name returns "handler not found".
    ("liquidation", "allLiquidation.BTCUSDT"),
    ("tickers", "tickers.BTCUSDT"),
]

WS_URI = "wss://stream.bybit.com/v5/public/linear"


def _purge_old_capture_files(
    topic_dir: Path, retention_days: int = RETENTION_DAYS
) -> int:
    """Delete capture files older than retention_days. Idempotent.

    Called from RotatingJSONLWriter._open_for_hour at every rotation, so
    the cost is one cheap directory scan per topic per hour. Both the
    uncompressed `.jsonl` (current/in-flight) and the rotated `.jsonl.gz`
    files in topic_dir are eligible — mtime drives the decision, not the
    extension.

    Returns the number of files deleted. Errors on individual files are
    logged and skipped (a parallel rotation/race is harmless).

    Without this, capture grows unbounded — see 2026-04-24 incident.
    """
    if not topic_dir.exists():
        return 0
    cutoff = time.time() - (retention_days * 86400)
    purged = 0
    for f in topic_dir.iterdir():
        if not f.is_file():
            continue
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                purged += 1
        except FileNotFoundError:
            pass  # race with a concurrent rotation; harmless
        except Exception as e:
            _log(f"[CAPTURE] purge failed for {f}: {e}")
    return purged


def _log(msg: str) -> None:
    """Tiny fallback logger — engine will usually override via import."""
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] {msg}", flush=True)


class RotatingJSONLWriter:
    """Writes one JSONL line per call; rotates on hour boundary.

    On rotation the previous file is closed and gzipped to `.jsonl.gz`
    in place (the uncompressed `.jsonl` is removed). Gzip is synchronous
    but only runs once per hour per topic, so the cost is negligible.

    Not thread-safe; intended to be called from a single async task.
    """

    def __init__(self, topic_dir: Path):
        self.topic_dir = topic_dir
        self.topic_dir.mkdir(parents=True, exist_ok=True)
        self._fh = None
        self._current_hour: Optional[str] = None
        self._current_path: Optional[Path] = None

    def _hour_key(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")

    def _open_for_hour(self, hour_key: str) -> None:
        # Close + gzip the previous file if rotating
        if self._fh is not None and self._current_path is not None:
            try:
                self._fh.close()
            except Exception:
                pass
            prev = self._current_path
            try:
                with prev.open("rb") as src, \
                        gzip.open(str(prev) + ".gz", "wb") as dst:
                    while True:
                        chunk = src.read(1 << 20)
                        if not chunk:
                            break
                        dst.write(chunk)
                prev.unlink(missing_ok=True)
            except Exception as e:
                _log(f"[CAPTURE] gzip rotate failed for {prev}: {e}")

        path = self.topic_dir / f"{hour_key}.jsonl"
        self._fh = path.open("a", encoding="utf-8")
        self._current_hour = hour_key
        self._current_path = path

        # Retention sweep at every rotation. One cheap dir listing per
        # topic per hour. Closes the unbounded-growth bug from 2026-04-24.
        try:
            n = _purge_old_capture_files(self.topic_dir)
            if n:
                _log(
                    f"[CAPTURE] purged {n} files >{RETENTION_DAYS}d old "
                    f"in {self.topic_dir.name}"
                )
        except Exception as e:
            _log(f"[CAPTURE] retention sweep failed: {e}")

    def write(self, obj: dict) -> None:
        hour = self._hour_key()
        if hour != self._current_hour:
            self._open_for_hour(hour)
        assert self._fh is not None
        self._fh.write(json.dumps(obj, separators=(",", ":")) + "\n")

    def flush(self) -> None:
        if self._fh is not None:
            try:
                self._fh.flush()
                os.fsync(self._fh.fileno())
            except Exception:
                pass

    def close(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            except Exception:
                pass
        self._fh = None


class BybitMicrostructureCapture:
    """Async WS client that maintains one connection, four topic
    subscriptions, and four rotating writers.

    Lives on its own supervised task so a crash/reconnect doesn't
    affect the kline pipeline that feeds predictions.
    """

    def __init__(self, capture_dir: Path = CAPTURE_DIR, log_fn=None):
        self.capture_dir = capture_dir
        self.log = log_fn or _log
        self.writers: dict[str, RotatingJSONLWriter] = {
            label: RotatingJSONLWriter(self.capture_dir / label)
            for label, _ in TOPICS
        }
        # Metric counters (used by engine /status readouts if wired in)
        self.metrics = {
            label: {"msgs": 0, "bytes": 0, "last_rx_ms": 0}
            for label, _ in TOPICS
        }
        self._last_flush = 0.0
        self._flush_every_s = 5.0

    def _topic_label(self, topic: str) -> Optional[str]:
        # Match on the full topic string (exact or prefix), since
        # label ("liquidation") and full ("allLiquidation.BTCUSDT") can
        # differ.
        for label, full in TOPICS:
            full_prefix = full.split(".")[0]  # e.g. "allLiquidation"
            if topic == full or topic.startswith(full_prefix + "."):
                return label
        return None

    async def run(self):
        """Main loop. Owned by engine supervisor; returns only on
        CancelledError (supervisor handles restart on other failures)."""
        import websockets  # local import to match engine pattern

        backoff = 1.0
        while True:
            try:
                self.log(f"[CAPTURE] connecting to {WS_URI}...")
                async with websockets.connect(
                    WS_URI, ping_interval=20, ping_timeout=10,
                    max_size=8 * 1024 * 1024,
                ) as ws:
                    # Subscribe per-topic without blocking on the ack —
                    # Bybit starts streaming data before each ack, so
                    # reading acks inline races against delta messages.
                    # Acks come back interleaved with data in the main
                    # loop below and are filtered on `op == subscribe`.
                    for _, full in TOPICS:
                        await ws.send(json.dumps({
                            "op": "subscribe", "args": [full],
                        }))
                    self.log(
                        f"[CAPTURE] sent {len(TOPICS)} subscribe requests"
                    )
                    backoff = 1.0

                    async for msg in ws:
                        rx_ms = int(time.time() * 1000)
                        try:
                            data = json.loads(msg)
                        except json.JSONDecodeError:
                            continue
                        # Handle subscribe acks inline
                        if data.get("op") == "subscribe":
                            ok = data.get("success", False)
                            if not ok:
                                self.log(
                                    f"[CAPTURE] sub rejected: "
                                    f"{data.get('ret_msg', '')}"
                                )
                            continue
                        topic = data.get("topic")
                        if not topic:
                            continue
                        label = self._topic_label(topic)
                        if label is None:
                            continue
                        # Inject our receipt timestamp so downstream
                        # analysis can measure our own latency without
                        # trusting the venue clock.
                        data["_rx_ms"] = rx_ms
                        try:
                            self.writers[label].write(data)
                        except Exception as e:
                            self.log(f"[CAPTURE] write failed {label}: {e}")
                            continue
                        m = self.metrics[label]
                        m["msgs"] += 1
                        m["bytes"] += len(msg) if isinstance(msg, (bytes, str)) else 0
                        m["last_rx_ms"] = rx_ms

                        # Periodic flush so a crash loses < 5s of tape.
                        now = time.time()
                        if now - self._last_flush >= self._flush_every_s:
                            for w in self.writers.values():
                                w.flush()
                            self._last_flush = now

            except asyncio.CancelledError:
                for w in self.writers.values():
                    w.close()
                raise
            except Exception as e:
                self.log(
                    f"[CAPTURE] disconnected: {e}. "
                    f"reconnecting in {backoff:.1f}s..."
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)


# Standalone entry point for dev runs outside the engine.
async def _main():
    cap = BybitMicrostructureCapture()
    await cap.run()


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
