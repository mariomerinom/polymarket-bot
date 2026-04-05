"""
smoke_bet.py — End-to-end pipeline smoke test with a real $5 bet.

Zero input required. Uses the actual momentum signal to pick direction.
Fetches the next open BTC 5-minute market, runs the real signal pipeline,
and places a $5 bet through the production CLOB path.

Usage:
    python src/smoke_bet.py              # live $5 bet (TRADING_ENABLED must be true)
    python src/smoke_bet.py --paper      # paper mode — logs but doesn't submit
    python src/smoke_bet.py --dry-run    # print what would happen, touch nothing
"""

import json
import sys
from datetime import datetime, timezone

from btc_data import fetch_btc_candles
from fetch_markets import fetch_active_markets, init_db, store_markets
from predict import momentum_signal, _get_clob_tokens_safe
from trade import place_order, ensure_orders_table, TRADING_ENABLED

BET_SIZE = 5  # $5 — hardcoded smoke test size


def main():
    import argparse
    parser = argparse.ArgumentParser(description="$5 pipeline smoke test")
    parser.add_argument("--paper", action="store_true", help="Paper mode (no real order)")
    parser.add_argument("--dry-run", action="store_true", help="Print plan only, touch nothing")
    args = parser.parse_args()

    # 1. Fetch candles — same path as production
    print("[1/5] Fetching BTC candles...")
    btc_data = fetch_btc_candles(limit=12)
    if not btc_data or not btc_data.get("candles"):
        print("FAIL: Could not fetch BTC candle data.")
        sys.exit(1)

    candles = btc_data["candles"]
    price = btc_data["current_price"]
    print(f"  BTC ${price:,.0f} | {len(candles)} candles | "
          f"1h: {btc_data.get('1h_change_pct', 0):+.3f}%")

    # 2. Run momentum signal — same logic as production
    print("[2/5] Running momentum signal...")
    signal = momentum_signal(candles, config_key="btc_5m")
    if not signal.get("should_trade"):
        # No streak — force direction from last candle (smoke test doesn't skip)
        last = candles[-1]
        direction = "UP" if last["close"] >= last["open"] else "DOWN"
        print(f"  Signal: no trade ({signal.get('reason', '?')})")
        print(f"  Smoke override: using last candle direction → {direction}")
    else:
        direction = signal["direction"]
        print(f"  Signal: {direction} (streak={signal.get('streak')}, "
              f"confidence={signal.get('confidence')})")

    # 3. Fetch next market
    print("[3/5] Fetching next BTC 5-min market...")
    markets = fetch_active_markets()
    if not markets:
        print("FAIL: No active BTC 5-minute markets.")
        sys.exit(1)

    market = markets[0]
    print(f"  {market['question']}")
    print(f"  YES={market['price_yes']:.2f}  NO={market['price_no']:.2f}  "
          f"ends={market['end_date']}")

    # 4. Resolve CLOB tokens + get real orderbook price
    print("[4/5] Resolving CLOB tokens...")
    tokens = _get_clob_tokens_safe(market["id"])
    if not tokens:
        print(f"FAIL: Could not resolve CLOB tokens for {market['id']}")
        sys.exit(1)

    if direction == "UP":
        token_key, mkt_price = "yes", market["price_yes"]
    else:
        token_key, mkt_price = "no", market["price_no"]

    # Fetch real CLOB mid for the token we're buying (REST fallback for standalone)
    gamma_price = mkt_price
    try:
        from clob_depth import get_order_book, analyze_depth
        book = get_order_book(tokens[token_key])
        if book:
            analysis = analyze_depth(book)
            clob_mid = analysis.get("mid")
            if clob_mid:
                print(f"  CLOB mid: {clob_mid:.4f} (Gamma implied: {mkt_price:.4f})")
                mkt_price = clob_mid
    except Exception as e:
        print(f"  CLOB price fetch failed, using Gamma: {e}")

    order_params = {
        "direction": direction,
        "side": "buy",
        "token": token_key,
        "size": BET_SIZE,
        "price_limit": round(mkt_price + 0.02, 2),  # 2¢ fill priority
        "slippage": 0,
        "market_price": mkt_price,
    }

    print(f"\n  ORDER: {direction} ${BET_SIZE} @ {order_params['price_limit']:.2f} "
          f"(mkt {mkt_price:.2f})")

    if args.dry_run:
        print("\n  --dry-run: stopping here.")
        return

    clob_token_id = tokens[token_key]
    print(f"  Token: {clob_token_id[:16]}...")

    # Open DB, store audit trail
    db = init_db()
    ensure_orders_table(db)
    store_markets(db, [market])

    cycle = db.execute("SELECT COALESCE(MAX(cycle), 0) + 1 FROM predictions").fetchone()[0]
    now = datetime.now(timezone.utc).isoformat()

    reasoning = json.dumps({
        "type": "smoke_bet",
        "signal": signal.get("reason", "smoke_override"),
        "streak": signal.get("streak"),
        "direction": direction,
        "market_price": mkt_price,
        "btc_price": price,
    })

    db.execute("""
        INSERT INTO predictions
        (market_id, agent, estimate, edge, confidence, reasoning,
         predicted_at, cycle, conviction_score, regime)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        market["id"], "smoke_test",
        signal.get("estimate", 0.5),
        abs(signal.get("estimate", 0.5) - mkt_price),
        signal.get("confidence", "smoke"),
        reasoning, now, cycle, 0,  # conviction 0 — audit only
        "smoke_test",
    ))
    db.commit()
    pred_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Place via production path
    print("[5/5] Placing bet...")
    if args.paper:
        print("  --paper mode: recording as paper trade")
        # place_order in paper mode just logs
        import os
        old = os.environ.get("TRADING_ENABLED")
        os.environ["TRADING_ENABLED"] = "false"
        result = place_order(db, market["id"], pred_id, order_params, cycle,
                             clob_token_id=clob_token_id)
        if old is not None:
            os.environ["TRADING_ENABLED"] = old
        else:
            os.environ.pop("TRADING_ENABLED", None)
    else:
        if not TRADING_ENABLED:
            print("FAIL: TRADING_ENABLED is not true. Use --paper for paper mode.")
            db.close()
            sys.exit(1)
        result = place_order(db, market["id"], pred_id, order_params, cycle,
                             clob_token_id=clob_token_id)

    status = result.get("status", "unknown")
    print(f"\n  Status: {status}")
    if result.get("order_id"):
        print(f"  Order ID: {result['order_id']}")

    if status in ("submitted", "paper"):
        print("  PASS — pipeline smoke test succeeded.")
    else:
        print(f"  FAIL — {result.get('reason', 'unknown')}")

    db.close()


if __name__ == "__main__":
    main()
