"""
candle_buffer.py — Rolling ring buffer of OHLCV candles per (symbol, timeframe).

Populated from Bybit WS kline events. Seeded from Bybit REST on startup.
Used by the TA Engine to compute indicators without external API calls.

Candle dict format (matches btc_data.py / bybit_data.py):
    {"time": "HH:MM", "open": float, "high": float, "low": float,
     "close": float, "volume": float, "direction": "UP"|"DOWN",
     "body_pct": float, "wick_ratio": float}
"""

from __future__ import annotations

import requests
from collections import deque
from datetime import datetime, timezone


class CandleBuffer:
    """Rolling ring buffer of confirmed OHLCV candles."""

    def __init__(self, maxlen: int = 100):
        self.maxlen = maxlen
        self._buffers: dict = {}        # (symbol, tf) → deque of candle dicts
        self._pending: dict = {}         # (symbol, tf) → in-progress candle dict

    def on_kline_event(self, symbol: str, timeframe: str, kline: dict) -> dict | None:
        """Process a Bybit WS kline event.

        Tracks incomplete candles (confirm=false). On confirm=true, finalizes
        the candle and appends to the ring buffer.

        Args:
            symbol: e.g. "BTCUSDT"
            timeframe: e.g. "5" (minutes)
            kline: Bybit kline data dict with keys:
                   start, end, open, high, low, close, volume, confirm

        Returns:
            Finalized candle dict on confirm=true, else None.
        """
        key = (symbol, timeframe)
        confirmed = kline.get("confirm", False)

        open_price = float(kline["open"])
        high = float(kline["high"])
        low = float(kline["low"])
        close = float(kline["close"])
        volume = float(kline["volume"])

        candle = _build_candle_dict(
            open_ts_ms=int(kline["start"]),
            open_price=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )

        if not confirmed:
            self._pending[key] = candle
            return None

        # Confirmed — append to buffer
        self._pending.pop(key, None)
        self._ensure_buffer(key)
        self._buffers[key].append(candle)
        return candle

    def get_candles(self, symbol: str, timeframe: str, limit: int | None = None) -> list:
        """Return list of candle dicts (oldest first)."""
        key = (symbol, timeframe)
        buf = self._buffers.get(key, deque())
        candles = list(buf)
        if limit:
            candles = candles[-limit:]
        return candles

    def get_closes(self, symbol: str, timeframe: str) -> list:
        """Return list of close prices (oldest first). Convenience for TA."""
        return [c["close"] for c in self.get_candles(symbol, timeframe)]

    def depth(self, symbol: str, timeframe: str) -> int:
        """Number of candles currently in the buffer."""
        key = (symbol, timeframe)
        return len(self._buffers.get(key, []))

    def seed_from_rest(self, symbol: str = "BTCUSDT", timeframe: str = "5",
                       category: str = "spot", limit: int = 100,
                       base_url: str = "https://api.bybit.com"):
        """Backfill buffer from Bybit REST /v5/market/kline.

        Called once on engine startup to populate history before WS events flow.
        """
        url = f"{base_url}/v5/market/kline"
        resp = requests.get(url, params={
            "category": category,
            "symbol": symbol,
            "interval": timeframe,
            "limit": limit,
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("retCode") != 0:
            raise Exception(f"Bybit seed error: {data.get('retMsg')}")

        raw = data.get("result", {}).get("list", [])
        if not raw:
            return 0

        # Bybit returns newest first — reverse to chronological
        raw.sort(key=lambda x: int(x[0]))

        key = (symbol, timeframe)
        self._ensure_buffer(key)

        count = 0
        for k in raw:
            # Bybit: [startTime, open, high, low, close, volume, turnover]
            candle = _build_candle_dict(
                open_ts_ms=int(k[0]),
                open_price=float(k[1]),
                high=float(k[2]),
                low=float(k[3]),
                close=float(k[4]),
                volume=float(k[5]),
            )
            self._buffers[key].append(candle)
            count += 1

        return count

    def _ensure_buffer(self, key: tuple):
        """Create buffer deque if it doesn't exist."""
        if key not in self._buffers:
            self._buffers[key] = deque(maxlen=self.maxlen)


def _build_candle_dict(open_ts_ms: int, open_price: float, high: float,
                       low: float, close: float, volume: float) -> dict:
    """Build a standardized candle dict matching btc_data.py format."""
    open_time = datetime.fromtimestamp(open_ts_ms / 1000, tz=timezone.utc)

    body = abs(close - open_price)
    full_range = high - low
    direction = "UP" if close >= open_price else "DOWN"
    wick_ratio = round(1.0 - (body / full_range), 2) if full_range > 0 else 0.0
    body_pct = round(
        (close - open_price) / open_price * 100, 4
    ) if open_price > 0 else 0.0

    return {
        "time": open_time.strftime("%H:%M"),
        "timestamp_ms": open_ts_ms,
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": round(volume, 2),
        "direction": direction,
        "body_pct": body_pct,
        "wick_ratio": wick_ratio,
    }
