"""
kalshi_score.py — Resolve Kalshi predictions via settlement API or candle data.

PARALLEL PIPELINE — does NOT touch score.py (BTC/ETH resolution).

Resolution strategy:
  1. Live mode (KALSHI_API_KEY set): query Kalshi API for settlement result.
  2. Mock mode (no credentials): resolve strike-price markets using actual BTC
     candle data. Market ID encodes the strike (e.g. BTCUSD-2604021350-84000
     means strike $84,000). Fetch BTC price at expiry and compare to strike.
  3. If candle data is unavailable, leave unresolved (never hash-resolve).
"""

import os
import re
from datetime import datetime, timezone

import requests

from kalshi_markets import _sign_request, _is_mock_mode, KALSHI_BASE_URL
from score import mark_resolved
from config import API_TIMEOUT_KALSHI, SETTLEMENT_DELAY_S


def auto_resolve_kalshi(db):
    """
    Check Kalshi for settled markets and update the database.
    Returns count of newly resolved markets.

    In mock mode (no Kalshi API credentials), fetches BTC candle data ONCE
    and resolves all eligible markets against it. Markets whose expiry falls
    outside the available candle window are left unresolved.
    """
    cursor = db.execute("SELECT id, question, end_date FROM markets WHERE resolved = 0")
    unresolved = cursor.fetchall()
    if not unresolved:
        return 0

    mock_mode = _is_mock_mode()
    resolved_count = 0
    now = datetime.now(timezone.utc)

    # Pre-fetch candle data once for all markets (mock mode only)
    candle_data = None
    if mock_mode:
        candle_data = _fetch_candle_data_once()

    for row in unresolved:
        market_id = row[0] if not isinstance(row, dict) else row["id"]
        end_date = row[2] if not isinstance(row, dict) else row["end_date"]

        # Only try to resolve markets past their end_date + settlement delay
        try:
            expiry = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            if (now - expiry).total_seconds() < SETTLEMENT_DELAY_S:
                continue
        except (ValueError, TypeError):
            continue

        if mock_mode:
            outcome = _resolve_from_candle(market_id, end_date, candle_data=candle_data)
        else:
            outcome = _live_resolve(market_id)

        if outcome is not None:
            mark_resolved(db, market_id, outcome)
            resolved_count += 1

    return resolved_count


def _fetch_candle_data_once():
    """Fetch BTC candle data once for batch resolution."""
    try:
        from btc_data import fetch_btc_candles
        from config import DEFAULT_CANDLE_LIMIT
        return fetch_btc_candles(interval="5m", limit=DEFAULT_CANDLE_LIMIT)
    except Exception as e:
        print(f"  [kalshi_score] Failed to fetch candle data: {e}")
        return None


def _live_resolve(market_id):
    """Query Kalshi API for market settlement. Returns 1 (UP), 0 (DOWN), or None."""
    try:
        path = f"/markets/{market_id}"
        headers = _sign_request("GET", path)
        url = f"{KALSHI_BASE_URL}{path}"
        resp = requests.get(url, headers=headers, timeout=API_TIMEOUT_KALSHI)
        resp.raise_for_status()
        market = resp.json()

        status = market.get("status", "")
        if status != "settled":
            return None

        result = market.get("result", "")
        if result == "yes":
            return 1
        elif result == "no":
            return 0

        return None
    except Exception as e:
        print(f"  [kalshi] Resolution error for {market_id}: {e}")
        return None


def parse_strike_from_market_id(market_id):
    """
    Extract the strike price from a Kalshi market ID.

    Format: BTCUSD-YYMMDDHHMM-STRIKE (e.g. BTCUSD-2604021350-84000)
    Returns the strike as a float, or None if parsing fails.
    """
    match = re.match(r"^BTCUSD-\d+-(\d+)$", market_id)
    if match:
        return float(match.group(1))
    return None


def _resolve_from_candle(market_id, end_date, candle_data=None):
    """
    Resolve a strike-price market using actual BTC candle data.

    Parses the strike from the market ID, uses BTC price around the
    market's expiry time, and checks if BTC was at or above the strike.

    IMPORTANT: Candle data only contains HH:MM times (no date), so we can
    only resolve markets that expired within the current candle window
    (typically the last ~1 hour). Markets older than that are left unresolved
    rather than being matched against wrong-day prices.

    Args:
        market_id: Kalshi market ID (e.g. BTCUSD-2604021350-84000)
        end_date: Market expiry ISO timestamp
        candle_data: Pre-fetched candle data dict (from _fetch_candle_data_once).
                     If None, fetches fresh data (for standalone calls/tests).

    Returns 1 (yes/above strike), 0 (no/below strike), or None if data
    is unavailable. Never falls back to hash-based mock resolution.
    """
    strike = parse_strike_from_market_id(market_id)
    if strike is None:
        print(f"    [kalshi_score] Cannot parse strike from {market_id}")
        return None

    try:
        # Use pre-fetched data or fetch fresh
        if candle_data is None:
            candle_data = _fetch_candle_data_once()

        if not candle_data or not candle_data.get("candles"):
            return None

        # Parse expiry time
        expiry = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)

        # Guard: only resolve markets that expired within the candle window.
        # Candle data has HH:MM times only (no date). Resolving a market from
        # yesterday against today's prices would produce wrong outcomes.
        # The candle window is ~(limit * interval) minutes; we use 90 minutes
        # as a safe upper bound for 12 x 5m candles.
        candle_window_seconds = candle_data.get("_window_seconds", 90 * 60)
        age_seconds = (now - expiry).total_seconds()
        if age_seconds > candle_window_seconds:
            return None  # Too old — no matching candle data available

        expiry_hhmm = expiry.strftime("%H:%M")

        # Find the candle at or just before the expiry time
        # Candles are in chronological order with 'time' field (HH:MM)
        best_candle = None
        for candle in candle_data["candles"]:
            candle_time = candle.get("time", "")
            if candle_time <= expiry_hhmm:
                best_candle = candle
            elif candle_time > expiry_hhmm:
                break

        if best_candle is None:
            # Expiry is before all candles — cannot resolve
            return None

        btc_price = best_candle["close"]

        # Market question: "Will BTC be above $STRIKE at TIME?"
        # Yes (1) if BTC >= strike, No (0) otherwise
        return 1 if btc_price >= strike else 0

    except Exception as e:
        print(f"    [kalshi_score] Candle resolution failed for {market_id}: {e}")
        return None


if __name__ == "__main__":
    from kalshi_markets import init_db_kalshi
    db = init_db_kalshi()
    resolved = auto_resolve_kalshi(db)
    print(f"Resolved {resolved} Kalshi market(s)")
    db.close()
