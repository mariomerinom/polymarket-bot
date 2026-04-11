"""
hl_score.py — Auto-resolution for Hyperliquid synthetic markets.

Resolves synthetic 5-minute markets by fetching the actual candle for that
window and checking if close > open (UP = outcome 1) or close < open (DOWN = 0).

Cloned from bybit_score.py. Identical resolution logic — only market ID
format differs (BTCUSDT-HL-* vs BTCUSDT-*).

PARALLEL PIPELINE — does NOT touch any other scoring code.
"""

import sqlite3
from datetime import datetime, timezone

from score import mark_resolved
from config import DEFAULT_CANDLE_LIMIT


def auto_resolve_hl(db):
    """
    Resolve expired synthetic markets using actual candle data.

    For each unresolved market past its end_date, determines outcome from
    the actual BTC price movement in that 5-minute window.
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

        if outcome is not None:
            mark_resolved(db, market_id, outcome)
            resolved_count += 1

    return resolved_count


def _resolve_from_candle(market_id, end_date):
    """
    Resolve by fetching the actual 5m candle for this market's time window.

    Market ID format: BTCUSDT-HL-2026-04-02T14:15:00Z
    We need the candle that started at that time.
    """
    try:
        from bybit_data import fetch_bybit_candles

        # Parse the market start time from the ID
        # Format: BTCUSDT-HL-2026-04-02T14:15:00Z
        time_part = market_id.split("BTCUSDT-HL-")[1]
        market_start = datetime.fromisoformat(time_part.replace("Z", "+00:00"))

        # Fetch recent candles (same source as Bybit — BTC is BTC)
        data = fetch_bybit_candles(interval="5", limit=DEFAULT_CANDLE_LIMIT)
        if not data or not data.get("candles"):
            return None

        # Find the candle that matches our market's time window
        for candle in data["candles"]:
            if candle["time"] == market_start.strftime("%H:%M"):
                # UP (close > open) = outcome 1, DOWN = outcome 0
                return 1 if candle["close"] > candle["open"] else 0

        return None

    except Exception as e:
        print(f"    [hl_score] Candle resolution failed for {market_id}: {e}")
        return None
