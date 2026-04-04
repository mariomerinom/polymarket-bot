"""
clob_depth.py — Read-only Polymarket CLOB order book queries.

Phase 6a: No auth, no wallet, no orders. Just measuring liquidity.
Uses public REST endpoint: GET https://clob.polymarket.com/book?token_id=X

Logs alongside each prediction:
  - Best bid/ask and spread
  - Depth at key dollar levels
  - Slippage estimate for various bet sizes
  - $MAX_BET (dollar amount where slippage exceeds 2%)
"""

import requests
from typing import Optional

from config import API_TIMEOUT_CLOB

CLOB_BASE = "https://clob.polymarket.com"
SLIPPAGE_LEVELS = [25, 50, 100, 200, 300, 500, 1000]


def get_order_book(token_id: str) -> Optional[dict]:
    """
    Fetch order book for a CLOB token. No auth required.
    Returns raw book dict or None on failure.
    """
    try:
        resp = requests.get(
            f"{CLOB_BASE}/book",
            params={"token_id": token_id},
            timeout=API_TIMEOUT_CLOB,
        )
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"  [CLOB] Order book fetch failed: {e}")
        return None


def analyze_depth(book: dict, side: str = "buy") -> dict:
    """
    Analyze order book depth for a given side.

    side="buy"  → we're buying YES tokens (hitting asks)
    side="sell" → we're selling YES tokens (hitting bids)

    Returns:
        {
            "best_bid": float,
            "best_ask": float,
            "spread": float,
            "spread_pct": float,
            "mid": float,
            "slippage_curve": {25: {...}, 50: {...}, ...},
            "max_bet_2pct": float,   # $ before 2% slippage
            "max_bet_5pct": float,   # $ before 5% slippage
            "depth_levels": int,     # total price levels on our side
        }
    """
    bids = sorted(book.get("bids", []), key=lambda x: -float(x["price"]))
    asks = sorted(book.get("asks", []), key=lambda x: float(x["price"]))

    if not bids or not asks:
        return {"error": "empty_book"}

    best_bid = float(bids[0]["price"])
    best_ask = float(asks[0]["price"])
    spread = best_ask - best_bid
    mid = (best_bid + best_ask) / 2
    spread_pct = spread / mid * 100 if mid > 0 else 0

    # Choose which side of the book we're consuming
    if side == "buy":
        levels = asks
        reference_price = best_ask
    else:
        levels = bids
        reference_price = best_bid

    # Compute slippage curve
    slippage_curve = {}
    for target in SLIPPAGE_LEVELS:
        result = _fill_simulation(levels, target, side)
        if result["shares"] > 0:
            slippage = abs(result["avg_price"] - reference_price) / reference_price * 100
            result["slippage_pct"] = round(slippage, 3)
        else:
            result["slippage_pct"] = None
        slippage_curve[target] = result

    # Find max bet before 2% and 5% slippage
    max_bet_2pct = _find_max_bet(levels, reference_price, 0.02, side)
    max_bet_5pct = _find_max_bet(levels, reference_price, 0.05, side)

    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": round(spread, 4),
        "spread_pct": round(spread_pct, 2),
        "mid": round(mid, 4),
        "slippage_curve": slippage_curve,
        "max_bet_2pct": round(max_bet_2pct, 2),
        "max_bet_5pct": round(max_bet_5pct, 2),
        "depth_levels": len(levels),
    }


def _fill_simulation(levels, target_dollars, side):
    """
    Simulate filling an order for $target_dollars against the book.
    Returns avg fill price and total shares.
    """
    total_cost = 0
    total_shares = 0

    for level in levels:
        price = float(level["price"])
        size = float(level["size"])

        if side == "buy":
            level_cost = price * size
        else:
            level_cost = price * size  # proceeds from selling

        if total_cost + level_cost <= target_dollars:
            total_cost += level_cost
            total_shares += size
        else:
            remaining = target_dollars - total_cost
            fill_shares = remaining / price if price > 0 else 0
            total_shares += fill_shares
            total_cost += remaining
            break

    avg_price = total_cost / total_shares if total_shares > 0 else 0
    return {
        "dollars": target_dollars,
        "avg_price": round(avg_price, 4),
        "shares": round(total_shares, 1),
    }


def _find_max_bet(levels, reference_price, max_slippage_pct, side):
    """
    Find the maximum dollar amount we can bet before slippage
    exceeds max_slippage_pct from reference price.
    """
    if side == "buy":
        price_limit = reference_price * (1 + max_slippage_pct)
    else:
        price_limit = reference_price * (1 - max_slippage_pct)

    total_cost = 0
    for level in levels:
        price = float(level["price"])
        size = float(level["size"])

        if side == "buy" and price > price_limit:
            break
        if side == "sell" and price < price_limit:
            break

        total_cost += price * size

    return total_cost


def get_liquidity_summary(token_id_yes: str, token_id_no: str,
                          direction: str = "UP") -> dict:
    """
    High-level liquidity summary for a prediction.

    direction="UP"   → we want to buy YES tokens (hit asks on YES book)
    direction="DOWN" → we want to buy NO tokens (hit asks on NO book)

    Returns a dict suitable for storing in reasoning JSON.
    """
    if direction == "UP":
        book = get_order_book(token_id_yes)
        side = "buy"
        token_label = "YES"
    else:
        book = get_order_book(token_id_no)
        side = "buy"
        token_label = "NO"

    if not book:
        return {"error": "book_unavailable", "token": token_label}

    depth = analyze_depth(book, side=side)
    if "error" in depth:
        return depth

    # Compact summary for logging
    return {
        "token": token_label,
        "best_bid": depth["best_bid"],
        "best_ask": depth["best_ask"],
        "spread": depth["spread"],
        "spread_pct": depth["spread_pct"],
        "mid": depth["mid"],
        "max_bet_2pct": depth["max_bet_2pct"],
        "max_bet_5pct": depth["max_bet_5pct"],
        "depth_levels": depth["depth_levels"],
        "slippage_at_50": depth["slippage_curve"].get(50, {}),
        "slippage_at_200": depth["slippage_curve"].get(200, {}),
        "slippage_at_500": depth["slippage_curve"].get(500, {}),
    }


def format_liquidity_log(summary: dict) -> str:
    """Human-readable one-liner for console output."""
    if "error" in summary:
        return f"[CLOB] {summary['error']}"

    max2 = summary.get("max_bet_2pct", 0)
    spread = summary.get("spread_pct", 0)
    s200 = summary.get("slippage_at_200", {})
    slip = s200.get("slippage_pct", "?")

    return (
        f"[CLOB] spread={spread:.2f}% | "
        f"$200 slip={slip}% | "
        f"max@2%=${max2:,.0f} | "
        f"levels={summary.get('depth_levels', 0)}"
    )


def get_clob_tokens(market_id):
    """
    Look up CLOB token IDs for a Polymarket market.
    Queries Gamma API by condition ID. Returns {"yes": ..., "no": ...} or None.
    """
    try:
        resp = requests.get(
            f"https://gamma-api.polymarket.com/markets/{market_id}",
            timeout=API_TIMEOUT_CLOB,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        raw_clob = data.get("clobTokenIds", "[]")
        if isinstance(raw_clob, str):
            import json
            clob_ids = json.loads(raw_clob)
        else:
            clob_ids = raw_clob
        if len(clob_ids) >= 2:
            return {"yes": clob_ids[0], "no": clob_ids[1]}
    except Exception as e:
        print(f"  [clob_depth] get_clob_tokens failed: {e}")
    return None
