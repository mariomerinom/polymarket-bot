"""
fetch_markets.py — Pull "Bitcoin Up or Down" 5-minute markets from Polymarket.

Searches the Gamma API for upcoming, unresolved Bitcoin 5-minute interval
markets and stores them in the local SQLite database.
"""

import re
import requests
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

GAMMA_API = "https://gamma-api.polymarket.com"
DB_PATH = Path(__file__).parent.parent / "data" / "predictions.db"

# Regex to capture a hyphenated time range like "11:55AM-12:00PM"
TIME_RANGE_RE = re.compile(r"(\d{1,2}:\d{2}[AP]M)\s*-\s*(\d{1,2}:\d{2}[AP]M)")


def _is_5min_window(title):
    """Check if the title contains a 5-minute time window."""
    match = TIME_RANGE_RE.search(title)
    if not match:
        return False
    try:
        t1 = datetime.strptime(match.group(1), "%I:%M%p")
        t2 = datetime.strptime(match.group(2), "%I:%M%p")
        diff = (t2 - t1).total_seconds()
        if diff < 0:
            diff += 12 * 3600  # handle AM/PM wrap
        return diff == 300  # exactly 5 minutes
    except ValueError:
        return False


def init_db():
    db = sqlite3.connect(DB_PATH)
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
            FOREIGN KEY (market_id) REFERENCES markets(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS evolution_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle INTEGER,
            agent TEXT,
            change_description TEXT,
            brier_before REAL,
            brier_after REAL,
            kept INTEGER,
            timestamp TEXT
        )
    """)
    db.commit()
    return db


def _is_15min_window(title):
    """Check if the title contains a 15-minute time window."""
    match = TIME_RANGE_RE.search(title)
    if not match:
        return False
    try:
        t1 = datetime.strptime(match.group(1), "%I:%M%p")
        t2 = datetime.strptime(match.group(2), "%I:%M%p")
        diff = (t2 - t1).total_seconds()
        if diff < 0:
            diff += 12 * 3600
        return diff == 900  # exactly 15 minutes
    except ValueError:
        return False


DB_PATH_15M = Path(__file__).parent.parent / "data" / "predictions_15m.db"


def init_db_15m():
    """Initialize the 15-minute database (identical schema, separate file)."""
    db = sqlite3.connect(DB_PATH_15M)
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


def fetch_active_markets_15m():
    """Fetch upcoming, unresolved 'Bitcoin Up or Down' 15-minute markets."""
    return _fetch_btc_markets(window_check=_is_15min_window)


def fetch_active_markets():
    """Fetch upcoming, unresolved 'Bitcoin Up or Down' 5-minute markets."""
    return _fetch_btc_markets(window_check=_is_5min_window)


def _fetch_btc_markets(window_check):
    """Shared logic for fetching Bitcoin Up or Down markets with a given time window filter."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=24)

    params = {
        "limit": 200,
        "order": "endDate",
        "ascending": "true",
        "end_date_min": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    resp = requests.get(f"{GAMMA_API}/events", params=params)
    resp.raise_for_status()
    events = resp.json()

    markets = []
    for event in events:
        title = event.get("title", "")

        # Must contain "Bitcoin Up or Down" and match the time window
        if "Bitcoin Up or Down" not in title:
            continue
        if not window_check(title):
            continue

        for market in event.get("markets", []):
            try:
                end_date = market.get("endDate") or market.get("end_date_iso")
                if not end_date:
                    continue

                end_dt = datetime.fromisoformat(
                    end_date.replace("Z", "+00:00")
                )

                # Skip already-resolved markets
                if market.get("resolved", False):
                    continue

                # Only keep markets ending within the next few hours
                if end_dt <= now or end_dt > cutoff:
                    continue

                # Verify outcomes are ["Up", "Down"]
                outcomes = market.get("outcomes", "[]")
                if isinstance(outcomes, str):
                    outcomes = json.loads(outcomes)
                if outcomes != ["Up", "Down"]:
                    continue

                # Parse outcome prices — index 0 is "Up"
                raw_prices = market.get("outcomePrices", '["0","0"]')
                if isinstance(raw_prices, str):
                    prices = json.loads(raw_prices)
                else:
                    prices = raw_prices
                price_up = float(prices[0])
                price_down = float(prices[1]) if len(prices) > 1 else round(1 - price_up, 4)

                volume = float(market.get("volume", 0) or 0)

                markets.append({
                    "id": market["id"],
                    "question": market.get("question", title),
                    "category": event.get("category", "crypto"),
                    "end_date": end_date,
                    "volume": volume,
                    "price_yes": price_up,       # "Up" price
                    "price_no": price_down,      # "Down" price
                })
            except (ValueError, KeyError, IndexError, json.JSONDecodeError):
                continue

    # Sort by soonest end_date first
    markets.sort(key=lambda m: m["end_date"])
    return markets


def store_markets(db, markets):
    """Upsert markets into the database."""
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


def get_unresolved_markets(db, limit=5):
    """Get markets that haven't resolved yet, ordered by soonest resolution."""
    cursor = db.execute("""
        SELECT id, question, category, end_date, volume, price_yes
        FROM markets
        WHERE resolved = 0
        ORDER BY end_date ASC
        LIMIT ?
    """, (limit,))
    return [dict(zip(["id", "question", "category", "end_date", "volume", "price_yes"], row))
            for row in cursor.fetchall()]


if __name__ == "__main__":
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = init_db()
    markets = fetch_active_markets()
    store_markets(db, markets)
    print(f"Fetched and stored {len(markets)} Bitcoin 5-min markets")
    for m in markets:
        print(f"  Up {m['price_yes']:.1%} / Down {m['price_no']:.1%} | {m['question'][:80]}")
    db.close()
