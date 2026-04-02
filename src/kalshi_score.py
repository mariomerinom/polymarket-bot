"""
kalshi_score.py — Resolve Kalshi predictions via settlement API.

PARALLEL PIPELINE — does NOT touch score.py (BTC/ETH resolution).

In mock mode, resolves markets based on time-based staleness: if a market's
end_date has passed, resolve it using the BTC price direction from candle data.
In live mode, queries the Kalshi API for settlement results.
"""

import os
from datetime import datetime, timezone

import requests

from kalshi_markets import _sign_request, _is_mock_mode, KALSHI_BASE_URL
from score import mark_resolved


def auto_resolve_kalshi(db):
    """
    Check Kalshi for settled markets and update the database.
    Returns count of newly resolved markets.
    """
    cursor = db.execute("SELECT id, question, end_date FROM markets WHERE resolved = 0")
    unresolved = cursor.fetchall()
    if not unresolved:
        return 0

    mock_mode = _is_mock_mode()
    resolved_count = 0
    now = datetime.now(timezone.utc)

    for row in unresolved:
        market_id = row[0] if not isinstance(row, dict) else row["id"]
        end_date = row[2] if not isinstance(row, dict) else row["end_date"]

        # Only try to resolve markets past their end_date
        try:
            expiry = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            if expiry > now:
                continue
        except (ValueError, TypeError):
            continue

        if mock_mode:
            outcome = _mock_resolve(market_id, end_date)
        else:
            outcome = _live_resolve(market_id)

        if outcome is not None:
            mark_resolved(db, market_id, outcome)
            resolved_count += 1

    return resolved_count


def _live_resolve(market_id):
    """Query Kalshi API for market settlement. Returns 1 (UP), 0 (DOWN), or None."""
    try:
        path = f"/markets/{market_id}"
        headers = _sign_request("GET", path)
        url = f"{KALSHI_BASE_URL}{path}"
        resp = requests.get(url, headers=headers, timeout=10)
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


def _mock_resolve(market_id, end_date):
    """
    Mock resolution for testing. Uses a deterministic hash of the market_id
    to produce a consistent outcome (so tests are reproducible).
    """
    now = datetime.now(timezone.utc)
    try:
        expiry = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        # Only resolve if at least 2 minutes past expiry (simulate settlement delay)
        if (now - expiry).total_seconds() < 120:
            return None
    except (ValueError, TypeError):
        pass

    # Deterministic: hash the market_id to get a consistent outcome
    import hashlib
    h = int(hashlib.md5(market_id.encode()).hexdigest(), 16)
    return 1 if h % 2 == 0 else 0


if __name__ == "__main__":
    from kalshi_markets import init_db_kalshi
    db = init_db_kalshi()
    resolved = auto_resolve_kalshi(db)
    print(f"Resolved {resolved} Kalshi market(s)")
    db.close()
