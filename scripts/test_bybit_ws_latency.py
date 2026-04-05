#!/usr/bin/env python3
"""Measure Bybit WS v5 kline candle-close latency.

Subscribe to BTCUSDT 5m spot kline, log wall-clock time when confirm=true arrives.
Compare to expected candle-close time (next 5-min boundary).
Run for 2-3 candles (~15 min) and report results.

Usage:
    pip install websockets
    python scripts/test_bybit_ws_latency.py
"""

import asyncio
import json
import time
from datetime import datetime, timezone


async def measure():
    import websockets

    uri = "wss://stream.bybit.com/v5/public/spot"
    print(f"[{datetime.now(timezone.utc).isoformat()}] Connecting to {uri}...")

    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({
            "op": "subscribe",
            "args": ["kline.5.BTCUSDT"]
        }))
        print("Subscribed to kline.5.BTCUSDT — waiting for candle closes...")
        print("(This will take up to 15 minutes to capture 3 closes)\n")

        closes = []
        msg_count = 0
        async for msg in ws:
            data = json.loads(msg)

            # Skip subscription confirmations and pings
            if data.get("op") == "subscribe" or data.get("ret_msg") == "pong":
                continue

            if data.get("topic") == "kline.5.BTCUSDT":
                msg_count += 1
                kline = data["data"][0]
                confirm = kline.get("confirm", False)

                if msg_count <= 3 or confirm:
                    ts = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
                    print(f"  [{ts}] open={kline.get('open')} "
                          f"close={kline.get('close')} "
                          f"confirm={confirm}")

                if confirm:
                    now_ms = int(time.time() * 1000)
                    candle_end_ms = int(kline["end"])
                    latency_ms = now_ms - candle_end_ms
                    print(f"  >>> CANDLE CLOSE latency: {latency_ms}ms "
                          f"(candle_end={candle_end_ms}, now={now_ms})")
                    closes.append(latency_ms)

                    if len(closes) >= 3:
                        break

        print(f"\n{'='*50}")
        print(f"Results ({len(closes)} candle closes):")
        print(f"  Latencies: {closes}")
        print(f"  Avg: {sum(closes) // len(closes)}ms")
        print(f"  Min: {min(closes)}ms")
        print(f"  Max: {max(closes)}ms")
        print(f"\nDecision gate:")
        max_lat = max(closes)
        if max_lat < 500:
            print(f"  < 500ms — Bybit-only viable (skip Polygon, save $200/mo)")
        elif max_lat < 2000:
            print(f"  < 2s — Bybit as backup trigger (Polygon primary)")
        else:
            print(f"  > 2s ��� Bybit perps only, no spot backup role")


if __name__ == "__main__":
    asyncio.run(measure())
