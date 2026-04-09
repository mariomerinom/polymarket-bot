from config import SHADOW_CANDLE_LIMIT, SETTLEMENT_DELAY_S, DEFAULT_CANDLE_LIMIT
"""
bybit_score.py — Auto-resolution for Bybit synthetic markets.

Resolves synthetic 5-minute markets by fetching the actual candle for that
window and checking if close > open (UP = outcome 1) or close < open (DOWN = 0).

PARALLEL PIPELINE — does NOT touch any BTC/ETH/Kalshi scoring code.
"""

import hashlib
import sqlite3
from datetime import datetime, timezone

from score import mark_resolved


def auto_resolve_bybit(db):
    """
    Resolve expired synthetic markets using actual candle data.

    For each unresolved market past its end_date, determines outcome from
    the actual BTC price movement in that 5-minute window.

    Falls back to mock mode (hash-deterministic) when candle data unavailable.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor = db.execute("""
        SELECT id, end_date FROM markets
        WHERE resolved = 0 AND end_date < ?
    """, (now_iso,))
    unresolved = cursor.fetchall()

    if not unresolved:
        return 0

    resolved_count = 0
    for row in unresolved:
        market_id = row[0]
        end_date = row[1]

        outcome = _resolve_from_candle(market_id, end_date)
        # Mock resolution removed — 7% of resolutions were hash-based random,
        # contaminating WR data. Leave unresolved until candle data is available.

        if outcome is not None:
            mark_resolved(db, market_id, outcome)
            resolved_count += 1

    return resolved_count


def _resolve_from_candle(market_id, end_date):
    """
    Resolve by fetching the actual 5m candle for this market's time window.

    The market_id encodes the start time: BTCUSDT-2026-04-02T14:15:00Z
    We need the candle that started at that time.
    """
    try:
        from bybit_data import fetch_bybit_candles

        # Parse the market start time from the ID
        # Format: BTCUSDT-2026-04-02T14:15:00Z
        time_part = market_id.split("BTCUSDT-")[1]
        market_start = datetime.fromisoformat(time_part.replace("Z", "+00:00"))

        # Fetch recent candles (enough to cover the market window)
        data = fetch_bybit_candles(interval="5", limit=DEFAULT_CANDLE_LIMIT)
        if not data or not data.get("candles"):
            return None

        # Find the candle that matches our market's time window
        for candle in data["candles"]:
            if candle["time"] == market_start.strftime("%H:%M"):
                # UP (close > open) = outcome 1, DOWN = outcome 0
                return 1 if candle["close"] > candle["open"] else 0

        # Candle not found in recent data — use last known price direction
        return None

    except Exception as e:
        print(f"    [bybit_score] Candle resolution failed for {market_id}: {e}")
        return None


def _mock_resolve(market_id, end_date):
    """
    Deterministic mock resolution (hash-based).

    Same pattern as kalshi_score._mock_resolve() — reproducible for tests.
    Only resolves if market end_date is > 2 minutes past (simulate settlement delay).
    """
    try:
        end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None

    now = datetime.now(timezone.utc)
    if (now - end_dt).total_seconds() < SETTLEMENT_DELAY_S:
        return None  # Too soon after expiry

    # Deterministic: hash of market_id
    h = int(hashlib.md5(market_id.encode()).hexdigest(), 16)
    return 1 if h % 2 == 0 else 0
