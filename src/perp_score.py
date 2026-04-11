"""
perp_score.py — Auto-resolution for generic perpetual futures synthetic markets.

Resolves synthetic 5-minute markets by fetching the actual candle for that
window and checking if close > open (UP = outcome 1) or close < open (DOWN = 0).

Parameterized version of bybit_score.py / hl_score.py.
"""

from datetime import datetime, timezone

from score import mark_resolved
from config import DEFAULT_CANDLE_LIMIT


def auto_resolve_perp(db, symbol, exchange):
    """Resolve expired synthetic markets using actual candle data.

    Market ID format: {SYMBOL}-{EXCHANGE}-{timestamp}
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

        outcome = _resolve_from_candle(market_id, symbol, exchange)

        if outcome is not None:
            mark_resolved(db, market_id, outcome)
            resolved_count += 1

    return resolved_count


def _resolve_from_candle(market_id, symbol, exchange):
    """Resolve by fetching the actual 5m candle for this market's time window.

    Market ID format: {SYMBOL}-{EXCHANGE}-{timestamp}
    e.g., ETHUSDT-bybit-2026-04-11T14:15:00Z
    """
    try:
        from bybit_data import fetch_bybit_candles

        # Parse time from market ID: {SYMBOL}-{EXCHANGE}-{timestamp}
        prefix = f"{symbol}-{exchange}-"
        if prefix not in market_id:
            return None
        time_part = market_id.split(prefix)[1]
        market_start = datetime.fromisoformat(time_part.replace("Z", "+00:00"))

        # Fetch candles for the right symbol
        data = fetch_bybit_candles(symbol=symbol, interval="5",
                                   limit=DEFAULT_CANDLE_LIMIT)
        if not data or not data.get("candles"):
            return None

        # Find matching candle
        for candle in data["candles"]:
            if candle["time"] == market_start.strftime("%H:%M"):
                return 1 if candle["close"] > candle["open"] else 0

        return None

    except Exception as e:
        print(f"    [perp_score] Resolution failed for {market_id}: {e}")
        return None
