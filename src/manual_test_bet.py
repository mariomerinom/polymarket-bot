"""
manual_test_bet.py — Place a $5 smoke-test bet on Polymarket.

USER-INITIATED. Bypasses conviction, regime, and signal logic.
Uses the exact same CLOB execution path as production trades.
Records as agent="manual_test_user" for clear audit trail.

Usage:
    python src/manual_test_bet.py --direction UP
    python src/manual_test_bet.py --direction DOWN
"""

import argparse
import json
import sys
from datetime import datetime, timezone

from fetch_markets import fetch_active_markets, init_db, store_markets
from predict import _get_clob_tokens_safe
from trade import place_order, ensure_orders_table, TRADING_ENABLED

TEST_BET_SIZE = 5  # $5 — hardcoded, not configurable


def _get_next_cycle(db):
    """Derive cycle number from the highest cycle recorded."""
    cursor = db.execute("SELECT COALESCE(MAX(cycle), 0) + 1 FROM predictions")
    return cursor.fetchone()[0]


def main():
    parser = argparse.ArgumentParser(
        description="Place a $5 smoke-test bet on Polymarket. "
                    "User-initiated — bypasses all signal logic."
    )
    parser.add_argument(
        "--direction", choices=["UP", "DOWN"], required=True,
        help="YOUR call — no default, no agent bias",
    )
    args = parser.parse_args()

    # Guard: must have trading enabled
    if not TRADING_ENABLED:
        print("ERROR: TRADING_ENABLED is not true. Cannot place live test bet.")
        print("Set TRADING_ENABLED=true and POLYMARKET_PRIVATE_KEY to run.")
        sys.exit(1)

    # 1. Open production DB
    db = init_db()
    ensure_orders_table(db)

    # 2. Fetch active markets
    print("Fetching active BTC 5-minute markets...")
    markets = fetch_active_markets()
    if not markets:
        print("ERROR: No active BTC 5-minute markets found.")
        db.close()
        sys.exit(1)

    market = markets[0]  # Soonest market
    store_markets(db, [market])  # Ensure it's in DB for FK

    # 3. Get CLOB tokens (same path as production)
    print("Resolving CLOB tokens...")
    tokens = _get_clob_tokens_safe(market["id"])
    if not tokens:
        print(f"ERROR: Could not get CLOB tokens for market {market['id']}")
        db.close()
        sys.exit(1)

    # 4. Build order params (bypass all signal logic)
    if args.direction == "UP":
        token_key, price = "yes", market["price_yes"]
    else:
        token_key, price = "no", market["price_no"]

    clob_token_id = tokens[token_key]

    order_params = {
        "direction": args.direction,
        "side": "buy",
        "token": token_key,
        "size": TEST_BET_SIZE,
        "price_limit": round(price, 2),
        "slippage": 0,
    }

    # 5. Store synthetic prediction (audit trail)
    cycle = _get_next_cycle(db)
    now = datetime.now(timezone.utc).isoformat()
    reasoning = json.dumps({
        "type": "manual_test_bet",
        "initiated_by": "user",
        "note": "User-initiated $5 smoke test — NOT signal-derived",
        "direction": args.direction,
        "market_price": price,
    })

    db.execute("""
        INSERT INTO predictions
        (market_id, agent, estimate, edge, confidence, reasoning,
         predicted_at, cycle, conviction_score, regime)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        market["id"], "manual_test_user",
        price,       # estimate = market price (no edge claim)
        0.0,         # zero edge
        "manual",
        reasoning, now, cycle, 0,  # conviction 0
        "manual_test",
    ))
    db.commit()
    pred_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # 6. Confirm with user before placing
    print(f"\n{'=' * 50}")
    print(f"  MANUAL TEST BET — $5 SMOKE TEST")
    print(f"{'=' * 50}")
    print(f"  Market:    {market['question']}")
    print(f"  Direction: {args.direction}")
    print(f"  Size:      ${TEST_BET_SIZE}")
    print(f"  Price:     {price:.2f}")
    print(f"  Token:     {clob_token_id[:12]}...")
    print(f"  Cycle:     {cycle}")
    print(f"{'=' * 50}")
    confirm = input("\n  Type YES to place this bet: ")
    if confirm.strip() != "YES":
        print("  Aborted.")
        db.close()
        sys.exit(0)

    # 7. Place order via production path
    print("\n  Submitting to CLOB...")
    result = place_order(
        db, market["id"], pred_id, order_params, cycle,
        clob_token_id=clob_token_id,
    )

    status = result.get("status", "unknown")
    order_id = result.get("order_id", "none")
    print(f"\n  Result: {status}")
    print(f"  Order ID: {order_id}")

    if status == "submitted":
        print("  PASS — CLOB execution path is working.")
    else:
        print(f"  FAIL — Order failed: {result.get('reason', 'unknown')}")

    db.close()


if __name__ == "__main__":
    main()
