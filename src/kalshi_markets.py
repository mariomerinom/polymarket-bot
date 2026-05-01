"""
kalshi_markets.py — Kalshi BTC market discovery + DB initialization.

PARALLEL PIPELINE — does NOT touch any BTC/ETH/15m pipeline files.

Fetches active Kalshi BTC prediction markets via REST API.
Falls back to mock mode if KALSHI_API_KEY is not set.
"""

import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from config import DB_BUSY_TIMEOUT_MS

KALSHI_BASE_URL = os.getenv(
    "KALSHI_BASE_URL",
    "https://api.elections.kalshi.com/trade-api/v2"
)

DB_PATH_KALSHI = Path(__file__).parent.parent / "data" / "predictions_kalshi.db"


def init_db_kalshi():
    """Initialize the Kalshi database (identical schema to other pipelines)."""
    DB_PATH_KALSHI.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH_KALSHI)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute(f"PRAGMA busy_timeout={DB_BUSY_TIMEOUT_MS}")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            id TEXT PRIMARY KEY,
            question TEXT,
            category TEXT,
            end_date TEXT,
            volume REAL,
            price_yes REAL,
            price_no REAL,
            fetched_at TEXT,
            resolved INTEGER DEFAULT 0,
            outcome INTEGER DEFAULT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT,
            agent TEXT,
            estimate REAL,
            edge REAL,
            confidence TEXT,
            reasoning TEXT,
            predicted_at TEXT,
            cycle INTEGER,
            conviction_score INTEGER,
            regime TEXT,
            FOREIGN KEY (market_id) REFERENCES markets(id)
        )
    """)
    db.commit()
    return db


# ── Kalshi API auth ──

def _is_mock_mode():
    """Check if we should use mock data (no API credentials)."""
    return not (os.getenv("KALSHI_API_KEY") and os.getenv("KALSHI_API_SECRET"))


def _sign_request(method, path, body=""):
    """
    Sign a Kalshi API request with HMAC-SHA256.
    Reads KALSHI_API_SECRET as env var content (not file path) for CI compatibility.
    Adapted from kalshi-collector/feeds/kalshi.py.
    """
    api_key = os.getenv("KALSHI_API_KEY", "")
    api_secret = os.getenv("KALSHI_API_SECRET", "")

    timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    canonical = f"{method}\n{path}\n{timestamp}\n{body}"

    signature = hmac.new(
        api_secret.encode(),
        canonical.encode(),
        hashlib.sha256
    ).hexdigest()

    return {
        "Authorization": f"{api_key}:{signature}",
        "Kalshi-Request-Timestamp": timestamp,
        "Content-Type": "application/json",
    }


# ── Market discovery ──

def _infer_timeframe(expiry_str):
    """Infer timeframe from expiry timestamp. Returns 5m/15m/1h/daily/weekly."""
    try:
        expiry_dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        delta = (expiry_dt - datetime.now(timezone.utc)).total_seconds()
        if delta < 600:
            return "5m"
        elif delta < 1800:
            return "15m"
        elif delta < 3600:
            return "1h"
        elif delta < 86400:
            return "daily"
        else:
            return "weekly"
    except Exception:
        return "unknown"


def _mock_markets():
    """Return realistic mock Kalshi BTC markets for testing without credentials."""
    now = datetime.now(timezone.utc)
    # Generate markets at 15m and 1h intervals ahead
    markets = []
    for i, offset_min in enumerate([15, 30, 60, 120]):
        expiry = now + timedelta(minutes=offset_min)
        strike = 84000 + (i * 500)
        tf = "15m" if offset_min <= 30 else "1h"
        ticker = f"BTCUSD-{expiry.strftime('%y%m%d%H%M')}-{strike}"
        markets.append({
            "id": ticker,
            "ticker": ticker,
            "series_ticker": "BTCUSD",
            "strike": float(strike),
            "expiry": expiry.isoformat(),
            "status": "active",
            "category": "cryptocurrency",
            "subtitle": f"Will BTC be above ${strike:,} at {expiry.strftime('%H:%M')} UTC?",
            "timeframe": tf,
            "volume": 50000 + i * 10000,
        })
    return markets


def _mock_orderbook(ticker):
    """Return consistent mock orderbook for a given ticker."""
    ticker_hash = int(hashlib.md5(ticker.encode()).hexdigest(), 16) % 1000
    bid = 0.45 + (ticker_hash % 10) * 0.01
    ask = bid + 0.05
    return {
        "ticker": ticker,
        "yes": {"bid": round(bid, 2), "ask": round(ask, 2)},
        "no": {"bid": round(1.0 - ask, 2), "ask": round(1.0 - bid, 2)},
        "last_trade_price": round((bid + ask) / 2, 3),
        "volume": 1000000 + (ticker_hash * 50000),
        "open_interest": 500000 + (ticker_hash * 25000),
    }


def fetch_active_kalshi_markets(mock_mode=None):
    """
    Fetch active Kalshi BTC markets. Returns list of market dicts
    in the standard schema (id, question, end_date, price_yes, etc.).

    Filters to 15m and 1h timeframes only (Kalshi's shortest BTC windows).
    Falls back to mock mode if no API credentials.
    """
    if mock_mode is None:
        mock_mode = _is_mock_mode()

    if mock_mode:
        raw_markets = _mock_markets()
    else:
        try:
            path = "/markets"
            headers = _sign_request("GET", path)
            params = {"series_ticker": "BTCUSD", "status": "active"}
            url = f"{KALSHI_BASE_URL}{path}"
            resp = requests.get(url, headers=headers, params=params, timeout=API_TIMEOUT_KALSHI)
            resp.raise_for_status()
            raw_markets = resp.json().get("markets", [])
        except Exception as e:
            print(f"  [kalshi] API error: {e} — falling back to mock")
            raw_markets = _mock_markets()

    # Map to standard schema and filter to 15m/1h
    markets = []
    for m in raw_markets:
        expiry = m.get("expiry", "")
        tf = m.get("timeframe") or _infer_timeframe(expiry)
        if tf not in ("15m", "1h"):
            continue

        # Get orderbook mid for price_yes
        ticker = m.get("ticker", m.get("id", ""))
        ob = fetch_kalshi_orderbook(ticker, mock_mode=mock_mode)
        mid = ob.get("mid", 0.5) if ob else 0.5

        markets.append({
            "id": ticker,
            "question": m.get("subtitle", f"Kalshi BTC {tf} — {ticker}"),
            "category": "cryptocurrency",
            "end_date": expiry,
            "volume": m.get("volume", 0),
            "price_yes": round(mid, 3),
            "price_no": round(1.0 - mid, 3),
            "strike": m.get("strike"),
            "timeframe": tf,
        })

    markets.sort(key=lambda m: m["end_date"])
    return markets


def fetch_kalshi_orderbook(ticker, mock_mode=None):
    """
    Fetch orderbook snapshot for a Kalshi market.
    Returns {bid, ask, mid, spread, depth_bid, depth_ask, volume, open_interest}.
    """
    if mock_mode is None:
        mock_mode = _is_mock_mode()

    if mock_mode:
        raw = _mock_orderbook(ticker)
    else:
        try:
            path = f"/markets/{ticker}/orderbook"
            headers = _sign_request("GET", path)
            url = f"{KALSHI_BASE_URL}{path}"
            resp = requests.get(url, headers=headers, timeout=API_TIMEOUT_KALSHI)
            resp.raise_for_status()
            raw = resp.json()
        except Exception as e:
            print(f"  [kalshi] Orderbook error for {ticker}: {e}")
            return None

    yes_side = raw.get("yes", {})
    bid = yes_side.get("bid", 0)
    ask = yes_side.get("ask", 0)
    mid = (bid + ask) / 2 if bid and ask else 0.5
    spread = ask - bid if bid and ask else 0
    volume = raw.get("volume", 0)
    oi = raw.get("open_interest", 0)

    return {
        "bid": bid,
        "ask": ask,
        "mid": round(mid, 4),
        "spread": round(spread, 4),
        "depth_bid": (volume * spread) / 2 if volume and spread else 0,
        "depth_ask": (volume * spread) / 2 if volume and spread else 0,
        "volume": volume,
        "open_interest": oi,
    }


def store_markets_kalshi(db, markets):
    """Upsert Kalshi markets into the database."""
    for m in markets:
        db.execute("""
            INSERT INTO markets (id, question, category, end_date, volume, price_yes, price_no, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                volume = excluded.volume,
                price_yes = excluded.price_yes,
                price_no = excluded.price_no,
                fetched_at = excluded.fetched_at
        """, (
            m["id"], m["question"], m["category"], m["end_date"],
            m["volume"], m["price_yes"], m["price_no"],
            datetime.now(timezone.utc).isoformat()
        ))
    db.commit()


def get_market_by_id(db, market_id):
    """Fetch a single market by ID."""
    cursor = db.execute("SELECT * FROM markets WHERE id = ?", (market_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


if __name__ == "__main__":
    print("Kalshi Markets — mock mode test")
    markets = fetch_active_kalshi_markets(mock_mode=True)
    for m in markets:
        print(f"  {m['id']}: {m['question']} (expires {m['end_date'][:16]}, mid={m['price_yes']})")
    print(f"\n{len(markets)} markets found")

    db = init_db_kalshi()
    store_markets_kalshi(db, markets)
    print(f"Stored to {DB_PATH_KALSHI}")
    db.close()
