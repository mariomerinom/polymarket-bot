"""
V3 Stage 1 — Data Pipeline

Fetches:
1. Active 5-min BTC markets from Gamma API
2. BTC OHLCV candles from Kraken (fallback Coinbase)
3. CLOB order book snapshots (midpoint, spread, depth)

Stores everything in SQLite for feature engineering (Stage 2).
"""

import json
import sqlite3
import time
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Reuse existing infrastructure
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.btc_data import fetch_btc_candles, format_for_prompt
from src.fetch_markets import _is_5min_window

from src.v3.config import (
    GAMMA_API, CLOB_API, CANDLE_LOOKBACK, DB_NAME,
    POLL_INTERVAL_S, MIN_MARKET_VOLUME,
)

DB_PATH = Path(__file__).parent.parent.parent / "data" / DB_NAME


# ── Database ────────────────────────────────────────────────────────────

def init_db(db_path=None):
    """Create V3 schema."""
    db = sqlite3.connect(db_path or DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")

    db.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            id TEXT PRIMARY KEY,
            question TEXT,
            category TEXT,
            end_date TEXT,
            event_start_time TEXT,
            volume REAL,
            price_yes REAL,
            price_no REAL,
            clob_token_yes TEXT,
            clob_token_no TEXT,
            fetched_at TEXT,
            resolved INTEGER DEFAULT 0,
            outcome INTEGER DEFAULT NULL
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS order_book_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT,
            midpoint REAL,
            best_bid REAL,
            best_ask REAL,
            spread_pct REAL,
            bid_depth_5pct REAL,
            ask_depth_5pct REAL,
            depth_imbalance REAL,
            captured_at TEXT,
            FOREIGN KEY (market_id) REFERENCES markets(id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS candle_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT,
            current_price REAL,
            hour_change_pct REAL,
            trend TEXT,
            volatility REAL,
            consecutive_direction INTEGER,
            consecutive_dir_label TEXT,
            range_position REAL,
            last_volume_ratio REAL,
            last_range_ratio REAL,
            compression INTEGER,
            last_candle_pattern TEXT,
            candles_json TEXT
        )
    """)

    db.commit()
    return db


# ── Gamma API ───────────────────────────────────────────────────────────

def fetch_active_markets():
    """Fetch active BTC 5-min markets from Gamma API with CLOB token IDs."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=2)

    resp = requests.get(f"{GAMMA_API}/events", params={
        "limit": 200,
        "order": "endDate",
        "ascending": "true",
        "end_date_min": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, timeout=10)
    resp.raise_for_status()

    markets = []
    for event in resp.json():
        title = event.get("title", "")
        if "Bitcoin Up or Down" not in title:
            continue
        if not _is_5min_window(title):
            continue

        for m in event.get("markets", []):
            try:
                end_date = m.get("endDate") or m.get("end_date_iso")
                if not end_date:
                    continue

                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                if m.get("resolved", False) or m.get("closed", False):
                    continue
                if end_dt <= now or end_dt > cutoff:
                    continue

                outcomes = m.get("outcomes", "[]")
                if isinstance(outcomes, str):
                    outcomes = json.loads(outcomes)
                if outcomes != ["Up", "Down"]:
                    continue

                raw_prices = m.get("outcomePrices", '["0","0"]')
                if isinstance(raw_prices, str):
                    prices = json.loads(raw_prices)
                else:
                    prices = raw_prices
                price_up = float(prices[0])
                price_down = float(prices[1]) if len(prices) > 1 else round(1 - price_up, 4)

                # Extract CLOB token IDs
                raw_ids = m.get("clobTokenIds", "[]")
                if isinstance(raw_ids, str):
                    clob_ids = json.loads(raw_ids)
                else:
                    clob_ids = raw_ids
                token_yes = clob_ids[0] if clob_ids else None
                token_no = clob_ids[1] if len(clob_ids) > 1 else None

                volume = float(m.get("volume", 0) or 0)

                markets.append({
                    "id": str(m["id"]),
                    "question": m.get("question", title),
                    "category": event.get("category", "crypto"),
                    "end_date": end_date,
                    "event_start_time": m.get("eventStartTime", ""),
                    "volume": volume,
                    "price_yes": price_up,
                    "price_no": price_down,
                    "clob_token_yes": token_yes,
                    "clob_token_no": token_no,
                    "best_bid": float(m.get("bestBid", 0) or 0),
                    "best_ask": float(m.get("bestAsk", 0) or 0),
                })
            except (ValueError, KeyError, IndexError, json.JSONDecodeError):
                continue

    markets.sort(key=lambda m: m["end_date"])
    return markets


# ── CLOB API ────────────────────────────────────────────────────────────

def fetch_clob_book(token_id):
    """Fetch order book from CLOB API. Returns book summary dict."""
    if not token_id:
        return None

    try:
        resp = requests.get(f"{CLOB_API}/book", params={
            "token_id": token_id,
        }, timeout=5)
        resp.raise_for_status()
        book = resp.json()

        bids = book.get("bids", [])
        asks = book.get("asks", [])

        # Best bid/ask
        # Bids are sorted descending by price (highest first for YES side)
        # But CLOB returns them in arbitrary order — sort ourselves
        bid_prices = sorted(
            [(float(b["price"]), float(b["size"])) for b in bids],
            key=lambda x: -x[0]
        )
        ask_prices = sorted(
            [(float(a["price"]), float(a["size"])) for a in asks],
            key=lambda x: x[0]
        )

        best_bid = bid_prices[0][0] if bid_prices else 0
        best_ask = ask_prices[0][0] if ask_prices else 1

        # Midpoint
        midpoint = (best_bid + best_ask) / 2 if best_bid and best_ask else 0.5

        # Spread
        spread_pct = (best_ask - best_bid) / midpoint if midpoint > 0 else 0

        # Depth within ±5% of midpoint (dollar value = size since shares are $1)
        bid_depth = sum(
            size for price, size in bid_prices
            if price >= midpoint - 0.05
        )
        ask_depth = sum(
            size for price, size in ask_prices
            if price <= midpoint + 0.05
        )

        # Depth imbalance: positive = more bids (bullish), negative = more asks
        total_depth = bid_depth + ask_depth
        imbalance = (bid_depth - ask_depth) / total_depth if total_depth > 0 else 0

        return {
            "midpoint": round(midpoint, 4),
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread_pct": round(spread_pct, 4),
            "bid_depth_5pct": round(bid_depth, 2),
            "ask_depth_5pct": round(ask_depth, 2),
            "depth_imbalance": round(imbalance, 4),
        }

    except Exception as e:
        print(f"  CLOB book error for {token_id[:20]}...: {e}")
        return None


# ── Storage ─────────────────────────────────────────────────────────────

def store_markets(db, markets):
    """Upsert markets into DB."""
    now = datetime.now(timezone.utc).isoformat()
    for m in markets:
        db.execute("""
            INSERT INTO markets (id, question, category, end_date, event_start_time,
                                 volume, price_yes, price_no, clob_token_yes, clob_token_no, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                volume = excluded.volume,
                price_yes = excluded.price_yes,
                price_no = excluded.price_no,
                fetched_at = excluded.fetched_at
        """, (
            m["id"], m["question"], m["category"], m["end_date"],
            m["event_start_time"], m["volume"], m["price_yes"], m["price_no"],
            m["clob_token_yes"], m["clob_token_no"], now,
        ))
    db.commit()


def store_book_snapshot(db, market_id, book):
    """Store order book snapshot."""
    if not book:
        return
    db.execute("""
        INSERT INTO order_book_snapshots
        (market_id, midpoint, best_bid, best_ask, spread_pct,
         bid_depth_5pct, ask_depth_5pct, depth_imbalance, captured_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        market_id, book["midpoint"], book["best_bid"], book["best_ask"],
        book["spread_pct"], book["bid_depth_5pct"], book["ask_depth_5pct"],
        book["depth_imbalance"], datetime.now(timezone.utc).isoformat(),
    ))


def store_candle_snapshot(db, btc_data):
    """Store BTC candle summary for later feature computation."""
    if not btc_data:
        return
    db.execute("""
        INSERT INTO candle_snapshots
        (captured_at, current_price, hour_change_pct, trend, volatility,
         consecutive_direction, consecutive_dir_label, range_position,
         last_volume_ratio, last_range_ratio, compression, last_candle_pattern,
         candles_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now(timezone.utc).isoformat(),
        btc_data["current_price"],
        btc_data["1h_change_pct"],
        btc_data["trend"],
        btc_data["volatility"],
        btc_data["consecutive_direction"],
        btc_data["consecutive_dir_label"],
        btc_data.get("range_position", 0.5),
        btc_data.get("last_volume_ratio", 1.0),
        btc_data.get("last_range_ratio", 1.0),
        1 if btc_data.get("last_3_range_shrinking") else 0,
        btc_data.get("last_candle_pattern", "none"),
        json.dumps(btc_data.get("candles", [])),
    ))


# ── Poll Cycle ──────────────────────────────────────────────────────────

def poll_cycle(db):
    """
    Run one complete data fetch cycle:
    1. Fetch active markets from Gamma
    2. Fetch BTC candles from Kraken
    3. Fetch CLOB book for each market
    4. Store everything
    Returns dict with cycle stats.
    """
    t0 = time.time()

    # 1. Markets
    markets = fetch_active_markets()
    store_markets(db, markets)

    # 2. BTC candles
    btc = fetch_btc_candles(limit=CANDLE_LOOKBACK)
    store_candle_snapshot(db, btc)

    # 3. CLOB books for each market
    book_count = 0
    for m in markets:
        book = fetch_clob_book(m["clob_token_yes"])
        if book:
            store_book_snapshot(db, m["id"], book)
            m["book"] = book
            book_count += 1

    db.commit()
    elapsed = time.time() - t0

    return {
        "markets": len(markets),
        "books": book_count,
        "btc_price": btc["current_price"] if btc else None,
        "elapsed_s": round(elapsed, 2),
    }


# ── CLI ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="V3 Data Pipeline")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL_S, help="Poll interval (seconds)")
    args = parser.parse_args()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = init_db()

    print("V3 Data Pipeline — Stage 1")
    print(f"DB: {DB_PATH}")
    print()

    while True:
        try:
            stats = poll_cycle(db)
            print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] "
                  f"Markets: {stats['markets']}, Books: {stats['books']}, "
                  f"BTC: ${stats['btc_price']:,.0f}, "
                  f"Latency: {stats['elapsed_s']:.1f}s")

            # Print first few markets with book data on first run
            if not args.loop:
                markets = fetch_active_markets()
                btc = fetch_btc_candles(limit=CANDLE_LOOKBACK)

                print(f"\n{'='*80}")
                if btc:
                    print(f"BTC: ${btc['current_price']:,.0f} | "
                          f"1h: {btc['1h_change_pct']:+.3f}% | "
                          f"Trend: {btc['trend']} | "
                          f"Vol: {btc['volatility']:.4f}% | "
                          f"Pattern: {btc.get('last_candle_pattern', 'none')}")
                print(f"{'='*80}\n")

                for m in markets[:10]:
                    book = fetch_clob_book(m["clob_token_yes"])
                    gamma_up = m["price_yes"]
                    bid = m["best_bid"]
                    ask = m["best_ask"]

                    line = f"  {m['question'][:55]:<55s}"
                    line += f"  Gamma: {gamma_up:.2f}"

                    if book:
                        mid = book["midpoint"]
                        spread = book["spread_pct"]
                        bid_d = book["bid_depth_5pct"]
                        ask_d = book["ask_depth_5pct"]
                        imb = book["depth_imbalance"]
                        line += f"  CLOB mid: {mid:.3f}  spread: {spread:.1%}"
                        line += f"  depth: ${bid_d:.0f}/${ask_d:.0f}"
                        line += f"  imb: {imb:+.2f}"
                    else:
                        line += "  (no CLOB data)"

                    print(line)

                # DB stats
                print(f"\n--- DB Stats ---")
                for table in ["markets", "order_book_snapshots", "candle_snapshots"]:
                    count = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    print(f"  {table}: {count} rows")

        except Exception as e:
            print(f"[ERROR] {e}")

        if not args.loop:
            break

        time.sleep(args.interval)

    db.close()
