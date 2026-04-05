from config import DEFAULT_CANDLE_LIMIT
from config import DB_BUSY_TIMEOUT_MS
from config import SHADOW_CANDLE_LIMIT
"""
trade.py — Order execution for Polymarket CLOB.

Converts predictions with conviction >= 3 into limit orders.
Two modes controlled by TRADING_ENABLED env var:
  - False (default): Log what we WOULD trade, no orders placed. Paper stays.
  - True: Place real limit orders via py-clob-client SDK.

Production sizing: flat $25 per bet (medium grind phase).
Conviction tiers gate WHICH bets fire, not HOW MUCH.

Thin book constraint: never bet more than the CLOB can absorb at <= 2% slippage.
"""

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "predictions.db"

# ── Configuration (from centralized config.py, env-overridable) ──────────────

from config import (
    BET_SIZE, DAILY_LOSS_LIMIT, CONSECUTIVE_LOSS_MAX,
    MIN_CONVICTION, MAX_SLIPPAGE_PCT, EDGE_THRESHOLD, MAX_SLIPPAGE_SPREAD,
    ETH_BET_SIZES, ETH_MAX_BET_CEILING_PCT, POLYMARKET_FEE_FACTOR,
    BOOK_DEPTH_SAFETY_MARGIN, MIN_BET_SIZE, FILL_PRIORITY_SPREAD, _env,
    MAX_LOSS_LOOKBACK, API_TIMEOUT_SUBMIT, POLYMARKET_CHAIN_ID,
)

TRADING_ENABLED = _env("TRADING_ENABLED", "false").lower() == "true"

# ── Startup validation ───────────────────────────────────────────────────────

if TRADING_ENABLED and not _env("POLYMARKET_PRIVATE_KEY", ""):
    raise RuntimeError(
        "TRADING_ENABLED=true but POLYMARKET_PRIVATE_KEY not set. "
        "Set the env var or disable trading."
    )


# ── Schema ────────────────────────────────────────────────────────────────────

def ensure_orders_table(db):
    """Create orders table if it doesn't exist. Enables WAL mode for concurrency."""
    db.execute("PRAGMA journal_mode=WAL")
    db.execute(f"PRAGMA busy_timeout={DB_BUSY_TIMEOUT_MS}")
    db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT,
            prediction_id INTEGER,
            direction TEXT,
            size REAL,
            price_limit REAL,
            price_filled REAL,
            slippage_pct REAL,
            status TEXT DEFAULT 'pending',
            order_id TEXT,
            mode TEXT,
            reason TEXT,
            placed_at TEXT,
            filled_at TEXT,
            settled_at TEXT,
            pnl REAL,
            cycle INTEGER,
            FOREIGN KEY (market_id) REFERENCES markets(id),
            FOREIGN KEY (prediction_id) REFERENCES predictions(id)
        )
    """)
    db.commit()


# ── Core ──────────────────────────────────────────────────────────────────────

def should_trade(prediction_row, db):
    """
    Decide if a prediction should become a live order.

    Args:
        prediction_row: dict with keys from predictions table
        db: sqlite3 connection (for daily loss check)

    Returns:
        (should_trade: bool, reason: str)
    """
    conv = prediction_row.get("conviction_score", 0)
    if conv < MIN_CONVICTION:
        return False, f"conviction_too_low ({conv})"

    estimate = prediction_row.get("estimate", 0.5)
    edge = abs(estimate - 0.5)
    if edge < EDGE_THRESHOLD:
        return False, f"edge_too_small ({edge:.3f})"

    # Daily loss limit check
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = db.execute("""
        SELECT COALESCE(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END), 0)
        FROM orders
        WHERE placed_at LIKE ? AND status IN ('filled', 'settled')
    """, (f"{today}%",)).fetchone()
    daily_loss = abs(row[0]) if row else 0

    if daily_loss >= DAILY_LOSS_LIMIT:
        return False, f"daily_loss_limit (${daily_loss:.0f} >= ${DAILY_LOSS_LIMIT:.0f})"

    # Consecutive loss breaker — halt after N losses in a row, reset on any win
    consec = _check_consecutive_losses(db)
    if consec >= CONSECUTIVE_LOSS_MAX:
        return False, f"consecutive_loss_breaker ({consec} >= {CONSECUTIVE_LOSS_MAX})"

    return True, "ok"


def _check_consecutive_losses(db):
    """Count current consecutive loss streak (most recent settled orders)."""
    rows = db.execute("""
        SELECT pnl FROM orders
        WHERE status = 'settled' AND pnl IS NOT NULL
        ORDER BY settled_at DESC LIMIT ?
    """, (MAX_LOSS_LOOKBACK,)).fetchall()
    streak = 0
    for (pnl,) in rows:
        if pnl < 0:
            streak += 1
        else:
            break
    return streak




def _agent_to_pipeline(agent: str) -> str:
    """Map prediction agent name to pipeline config key."""
    agent_lower = agent.lower()
    from config import AGENT_PIPELINE_MAP
    for key, pipeline in AGENT_PIPELINE_MAP.items():
        if key in agent_lower:
            return pipeline
    return "btc_5m"


def get_bet_size(prediction_row, liquidity=None):
    """Return bet size based on asset and conviction.

    Priority: env var override > pipelines.json > config.py defaults.
    BTC: flat $25 (medium grind phase).
    ETH: tiered by conviction, capped by book depth.
    """
    agent = prediction_row.get("agent", "")
    conviction = prediction_row.get("conviction_score", 0)

    # Check per-pipeline bet size override (from config/pipelines.json)
    try:
        from pipeline_control import get_bet_size_override
        override = get_bet_size_override(_agent_to_pipeline(agent))
        if override is not None:
            return override
    except ImportError:
        pass

    if "eth" in agent.lower():
        base = ETH_BET_SIZES.get(conviction, 0)
        if liquidity and not liquidity.get("error"):
            ceiling = liquidity.get("max_bet_2pct", float("inf")) * ETH_MAX_BET_CEILING_PCT
            return min(base, ceiling)
        return base

    return BET_SIZE  # BTC flat $25


LIVE_ORDERBOOK_PATH = Path(__file__).parent.parent / "data" / "live_orderbook.json"
LIVE_ORDERBOOK_MAX_AGE_S = 10  # ignore cache older than 10 seconds


def _get_live_token_mid(token_id: str):
    """
    Read live mid for a specific CLOB token from per-token WS cache.

    Cache format: {"tokens": {token_id: {mid, best_bid, best_ask, updated_at, ...}}}
    Written by botsy_engine.py Polymarket WS feed.

    Returns float mid if cache entry is fresh (<10s), else None.
    """
    if not token_id:
        return None
    try:
        if not LIVE_ORDERBOOK_PATH.exists():
            return None
        cache = json.loads(LIVE_ORDERBOOK_PATH.read_text())
        entry = cache.get("tokens", {}).get(token_id)
        if not entry:
            return None
        updated_at = entry.get("updated_at", "")
        if not updated_at:
            return None
        cache_dt = datetime.fromisoformat(updated_at)
        age_s = (datetime.now(timezone.utc) - cache_dt).total_seconds()
        if age_s > LIVE_ORDERBOOK_MAX_AGE_S:
            return None
        mid = entry.get("mid")
        if mid is not None and 0.01 <= mid <= 0.99:
            return mid
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        pass
    return None


def compute_order(prediction_row, market_row, liquidity=None):
    """
    Compute order parameters from a prediction.

    Returns:
        dict with direction, side, token, size, price_limit
        or None if the order can't be placed (e.g., book too thin)
    """
    estimate = prediction_row["estimate"]
    direction = "UP" if estimate > 0.5 else "DOWN"

    # We buy YES tokens for UP, NO tokens for DOWN
    # Cap limit price at market + MAX_SPREAD to avoid overpaying.
    # Without this cap, the fixed 0.62 estimate causes 12-28¢ slippage
    # when the market is at 34-49¢.
    #
    # FILL_PRIORITY_SPREAD (2¢ default): widen limit price to improve fill rate.
    # Reconciliation 2026-04-02: 53% fill rate, 8/8 expired orders were winners.
    # $165 missed profit. Trading 2¢ edge for dramatically higher fill rate is +EV.
    market_price_yes = market_row.get("price_yes") or 0.5
    if direction == "UP":
        side = "buy"
        token = "yes"
        fill_adjusted = estimate + FILL_PRIORITY_SPREAD
        max_price = market_price_yes + MAX_SLIPPAGE_SPREAD + FILL_PRIORITY_SPREAD
        price_limit = min(fill_adjusted, max_price)
    else:
        side = "buy"
        token = "no"
        # Use real CLOB NO price when available, fall back to implied
        real_no = market_row.get("price_no")
        implied_no = 1 - market_price_yes
        if real_no and abs(real_no - implied_no) > 0.005:
            market_price_no = real_no
        else:
            market_price_no = implied_no
            import logging
            logging.getLogger(__name__).info(
                f"DIAG|clob_fallback=true|side=NO|implied={implied_no:.4f}")
        fill_adjusted = (1 - estimate) + FILL_PRIORITY_SPREAD
        max_price = market_price_no + MAX_SLIPPAGE_SPREAD + FILL_PRIORITY_SPREAD
        price_limit = min(fill_adjusted, max_price)

    # Compute slippage vs market mid
    if direction == "UP":
        slippage = price_limit - market_price_yes
    else:
        slippage = price_limit - market_price_no

    # Asset-aware sizing: BTC flat $25, ETH tiered by conviction
    size = get_bet_size(prediction_row, liquidity)
    if liquidity and not liquidity.get("error"):
        max_book = liquidity.get("max_bet_2pct", float("inf"))
        if max_book < size:
            size = max(0, max_book * BOOK_DEPTH_SAFETY_MARGIN)
            if size < MIN_BET_SIZE:
                return None, f"book_too_thin (max@2%=${max_book:.0f})"

    return {
        "direction": direction,
        "side": side,
        "token": token,
        "size": round(size, 2),
        "price_limit": round(price_limit, 4),
        "slippage": round(slippage, 4),
        "market_price": round(market_price_yes, 4),
    }, "ok"


def place_order(db, market_id, prediction_id, order_params, cycle,
                clob_token_id=None):
    """
    Place an order — either log-only (paper) or live via CLOB SDK.

    Returns:
        order dict with status
    """
    now = datetime.now(timezone.utc).isoformat()
    mode = "live" if TRADING_ENABLED else "paper"

    order_record = {
        "market_id": market_id,
        "prediction_id": prediction_id,
        "direction": order_params["direction"],
        "size": order_params["size"],
        "price_limit": order_params["price_limit"],
        "slippage_pct": order_params.get("slippage", 0) * 100,  # store as percentage
        "status": "pending",
        "order_id": None,
        "mode": mode,
        "reason": None,
        "placed_at": now,
        "cycle": cycle,
    }

    if not TRADING_ENABLED:
        # Paper mode — log what we would have done
        order_record["status"] = "paper"
        order_record["reason"] = "trading_disabled"
        _store_order(db, order_record)
        return order_record

    # Live mode — submit to Polymarket CLOB
    if not clob_token_id:
        order_record["status"] = "failed"
        order_record["reason"] = "missing_clob_token_id"
        _store_order(db, order_record)
        return order_record

    try:
        # Diagnostic C: Order submission RTT (cancel-replace feasibility)
        t0 = time.monotonic()
        result = _submit_clob_order(
            token_id=clob_token_id,
            side=order_params["side"],
            size=order_params["size"],
            price=order_params["price_limit"],
        )
        rtt_ms = (time.monotonic() - t0) * 1000
        print(f"    DIAG|order_rtt_ms={rtt_ms:.0f}|status={result.get('status', 'ok')}")
        order_record["order_id"] = result.get("orderID") or result.get("order_id")
        order_record["status"] = "submitted"
        order_record["reason"] = json.dumps(result)
    except Exception as e:
        rtt_ms = (time.monotonic() - t0) * 1000
        print(f"    DIAG|order_rtt_ms={rtt_ms:.0f}|status=error")
        order_record["status"] = "failed"
        order_record["reason"] = str(e)

    _store_order(db, order_record)
    return order_record


def _store_order(db, order):
    """Insert order record into the orders table."""
    db.execute("""
        INSERT INTO orders
        (market_id, prediction_id, direction, size, price_limit, price_filled,
         slippage_pct, status, order_id, mode, reason, placed_at, filled_at,
         settled_at, pnl, cycle)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order["market_id"], order["prediction_id"], order["direction"],
        order["size"], order["price_limit"], order.get("price_filled"),
        order.get("slippage_pct"), order["status"], order.get("order_id"),
        order["mode"], order.get("reason"), order["placed_at"],
        order.get("filled_at"), order.get("settled_at"), order.get("pnl"),
        order["cycle"],
    ))
    db.commit()


def _submit_clob_order(token_id, side, size, price):
    """
    Submit a limit order to Polymarket CLOB via py-clob-client.

    Requires env var:
        POLYMARKET_PRIVATE_KEY — Polygon wallet private key (hex, 0x prefix ok)

    The SDK derives API credentials from the private key via EIP-712 signing.
    Returns API response dict: {"success": bool, "orderID": str, "status": str}
    """
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import OrderArgs
        from py_clob_client.order_builder.constants import BUY, SELL
    except ImportError:
        raise RuntimeError(
            "py-clob-client not installed. Run: pip install py-clob-client"
        )

    private_key = os.environ.get("POLYMARKET_PRIVATE_KEY")
    if not private_key:
        raise RuntimeError("POLYMARKET_PRIVATE_KEY env var not set")

    # Polygon mainnet — GNOSIS_SAFE (type 2) if proxy configured, else EOA (type 0)
    proxy_address = os.environ.get("POLYMARKET_PROXY_ADDRESS", "")
    sig_type = 2 if proxy_address else 0
    client = ClobClient(
        "https://clob.polymarket.com",
        key=private_key,
        chain_id=POLYMARKET_CHAIN_ID,
        signature_type=sig_type,
        funder=proxy_address if proxy_address else None,
    )

    # Derive API credentials from private key (EIP-712 signing)
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)

    # Convert dollars to shares: shares = dollars / price_per_share
    shares = round(size / price, 2) if price > 0 else 0
    clob_side = BUY if side.upper() == "BUY" else SELL

    order_args = OrderArgs(
        token_id=token_id,
        price=round(price, 2),
        size=shares,
        side=clob_side,
    )

    # GTC = Good-Til-Cancelled limit order, with timeout guard
    import signal as _signal

    def _timeout_handler(signum, frame):
        raise TimeoutError(f"CLOB order submission timed out after {API_TIMEOUT_SUBMIT}s")

    old_handler = _signal.signal(_signal.SIGALRM, _timeout_handler)
    _signal.alarm(API_TIMEOUT_SUBMIT)  # timeout from config
    try:
        response = client.create_and_post_order(order_args)
    finally:
        _signal.alarm(0)  # Cancel alarm
        _signal.signal(_signal.SIGALRM, old_handler)

    return response


# ── Settlement ────────────────────────────────────────────────────────────────

def settle_orders(db):
    """
    Check submitted orders and update fill status using get_trades().

    get_order() returns 404 for resolved 5-minute markets, so we use
    get_trades() which returns all historical fills for our wallet.
    We match trades to our pending orders by order_id.

    Orders not found in trades after the market has resolved are marked expired.

    Returns number of orders settled.
    """
    if not TRADING_ENABLED:
        return 0

    cursor = db.execute("""
        SELECT id, order_id, market_id FROM orders
        WHERE status = 'submitted' AND order_id IS NOT NULL
    """)
    pending = cursor.fetchall()

    if not pending:
        return 0

    settled = 0
    try:
        from py_clob_client.client import ClobClient

        proxy_address = os.environ.get("POLYMARKET_PROXY_ADDRESS", "")
        sig_type = 2 if proxy_address else 0
        client = ClobClient(
            "https://clob.polymarket.com",
            key=os.environ.get("POLYMARKET_PRIVATE_KEY"),
            chain_id=POLYMARKET_CHAIN_ID,
            signature_type=sig_type,
            funder=proxy_address if proxy_address else None,
        )
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)

        # Fetch all our trades from the CLOB
        try:
            trades = client.get_trades() or []
        except Exception as e:
            print(f"  [TRADE] get_trades() failed: {e}")
            trades = []

        # Build a lookup: order_id -> {price, actual_size}
        # Trades reference our orders in two ways:
        # 1. taker_order_id (we were the taker)
        # 2. maker_orders[].order_id (we were the maker)
        # Multiple fills per order are aggregated (order splitting is normal).
        filled_orders = {}  # order_id -> {price: float, actual_size: float}
        for trade in trades:
            trade_price = float(trade.get("price", 0))
            trade_size = float(trade.get("size", 0))  # shares filled
            trade_usdc = trade_size * trade_price if trade_size and trade_price else 0

            # Check if we were the taker
            taker_oid = trade.get("taker_order_id", "")
            if taker_oid:
                if taker_oid in filled_orders:
                    # Aggregate multiple fills: weighted avg price, sum size
                    prev = filled_orders[taker_oid]
                    total_usdc = prev["actual_size"] + trade_usdc
                    total_shares = (prev["actual_size"] / prev["price"] if prev["price"] else 0) + trade_size
                    filled_orders[taker_oid] = {
                        "price": total_usdc / total_shares if total_shares else trade_price,
                        "actual_size": total_usdc,
                    }
                else:
                    filled_orders[taker_oid] = {"price": trade_price, "actual_size": trade_usdc}

            # Check if our order appears in maker_orders
            for maker in trade.get("maker_orders", []):
                moid = maker.get("order_id", "")
                if moid:
                    maker_price = float(maker.get("price", trade_price))
                    maker_size = float(maker.get("matched_amount", trade_size))
                    maker_usdc = maker_size * maker_price if maker_size and maker_price else 0
                    if moid in filled_orders:
                        prev = filled_orders[moid]
                        total_usdc = prev["actual_size"] + maker_usdc
                        total_shares = (prev["actual_size"] / prev["price"] if prev["price"] else 0) + maker_size
                        filled_orders[moid] = {
                            "price": total_usdc / total_shares if total_shares else maker_price,
                            "actual_size": total_usdc,
                        }
                    else:
                        filled_orders[moid] = {"price": maker_price, "actual_size": maker_usdc}

        # Check which markets have resolved (to mark unfilled orders as expired)
        resolved_markets = set()
        market_ids = list(set(r[2] for r in pending))
        for mid in market_ids:
            row = db.execute(
                "SELECT resolved FROM markets WHERE id = ?", (mid,)
            ).fetchone()
            if row and row[0]:
                resolved_markets.add(mid)

        now = datetime.now(timezone.utc).isoformat()
        for order_db_id, order_id, market_id in pending:
            if order_id in filled_orders:
                fill_info = filled_orders[order_id]
                fill_price = fill_info["price"]
                actual_size = fill_info.get("actual_size", 0)
                # Update size to actual USDC spent (fixes P&L for partial fills)
                update_size = actual_size > 0
                if update_size:
                    db.execute("""
                        UPDATE orders SET status = 'filled', price_filled = ?,
                        filled_at = ?, size = ? WHERE id = ?
                    """, (fill_price, now, round(actual_size, 2), order_db_id))
                else:
                    db.execute("""
                        UPDATE orders SET status = 'filled', price_filled = ?,
                        filled_at = ? WHERE id = ?
                    """, (fill_price, now, order_db_id))
                # Compute realized slippage: how far fill_price deviated from price_limit
                limit_row = db.execute(
                    "SELECT price_limit FROM orders WHERE id = ?", (order_db_id,)
                ).fetchone()
                if limit_row and limit_row[0] and fill_price:
                    realized_slip = abs(fill_price - limit_row[0]) / limit_row[0] * 100
                    db.execute(
                        "UPDATE orders SET slippage_pct = ? WHERE id = ?",
                        (round(realized_slip, 4), order_db_id),
                    )

                settled += 1
                size_note = f", actual=${actual_size:.2f}" if update_size else ""
                print(f"  [TRADE] Order {order_id[:12]}... FILLED @ {fill_price:.3f}{size_note}")
            elif market_id in resolved_markets:
                db.execute("""
                    UPDATE orders SET status = 'expired' WHERE id = ?
                """, (order_db_id,))
                settled += 1
                print(f"  [TRADE] Order {order_id[:12]}... EXPIRED (market resolved, no fill)")

        db.commit()
    except ImportError:
        print("  [TRADE] py-clob-client not installed — can't check order status")

    return settled


def compute_order_pnl(db):
    """
    Compute P&L for filled orders whose markets have resolved.
    Updates the pnl column in orders table.

    Returns number of orders with newly computed P&L.
    """
    cursor = db.execute("""
        SELECT o.id, o.direction, o.size, o.price_filled, m.outcome
        FROM orders o
        JOIN markets m ON o.market_id = m.id
        WHERE o.status = 'filled' AND o.pnl IS NULL AND m.resolved = 1
    """)
    rows = cursor.fetchall()

    updated = 0
    for row in rows:
        order_id, direction, size, price_filled, outcome = row

        # Did we win?
        if direction == "UP":
            won = outcome == 1
        else:
            won = outcome == 0

        if won:
            # Payout is $1 per share. Profit = (1/price - 1) * size * (1 - fee)
            price = price_filled or 0.5
            pnl = size * (1.0 / price - 1) * POLYMARKET_FEE_FACTOR
        else:
            pnl = -size

        now = datetime.now(timezone.utc).isoformat()
        db.execute("""
            UPDATE orders SET pnl = ?, settled_at = ?, status = 'settled'
            WHERE id = ?
        """, (round(pnl, 2), now, order_id))
        updated += 1

    if updated:
        db.commit()
    return updated


# ── Execution hook (called from ci_run.py) ────────────────────────────────────

def execute_trades(db, cycle):
    """
    Main entry point: scan recent predictions, place orders for qualifying ones.

    Called after run_predictions() in the CI pipeline.
    Paper mode: logs what would have been traded.
    Live mode: submits CLOB limit orders.

    Returns:
        list of order dicts
    """
    ensure_orders_table(db)

    # VWAP mean-reversion: DISABLED (Decision #23 reverted 2026-04-02).
    # Shadow data showed 29.4% WR on 17 resolved ETH bets (5W-12L).
    # BTC had zero shadow predictions. Promotion was based on misread
    # daily report stat (78.6% was RSI/OBV aggregate, not VWAP-specific).
    # Shadow continues collecting via shadow_log_indicators below.

    # Find predictions from this cycle that qualify
    cursor = db.execute("""
        SELECT p.id, p.market_id, p.estimate, p.conviction_score, p.reasoning,
               p.agent, m.price_yes, m.price_no, m.end_date, m.fetched_at
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE p.cycle = ? AND p.conviction_score >= ?
        AND m.resolved = 0
        AND p.market_id NOT IN (
            SELECT market_id FROM orders WHERE cycle = ?
        )
    """, (cycle, MIN_CONVICTION, cycle))

    predictions = [dict(zip(
        ["id", "market_id", "estimate", "conviction_score", "reasoning",
         "agent", "price_yes", "price_no", "end_date", "fetched_at"],
        row
    )) for row in cursor.fetchall()]

    # Shadow indicators — run every cycle regardless of qualifying predictions.
    # This ensures data collection during MEAN_REVERTING and other low-conviction regimes.
    try:
        from shadow_indicators import shadow_log_indicators
        shadow = shadow_log_indicators(db, cycle)
        if shadow:
            print(f"    [SHADOW] {shadow.get('summary', 'logged')}")
    except Exception as e:
        print(f"    [SHADOW] skipped: {e}")

    # Shadow conviction scorer — continuous strength signal
    try:
        from shadow_conviction_scorer import shadow_log_cycle
        from btc_data import fetch_btc_candles
        btc = fetch_btc_candles(limit=DEFAULT_CANDLE_LIMIT)
        if btc and btc.get("candles"):
            shadow_log_cycle(db, cycle, btc["candles"], "btc_5m")
    except Exception as e:
        print(f"    [shadow] skipped: {e}")

    if not predictions:
        return []

    orders = []
    mode_label = "LIVE" if TRADING_ENABLED else "PAPER"
    print(f"\n  [{mode_label}] Processing {len(predictions)} qualifying prediction(s)...")

    for pred in predictions:
        # Check trade gates
        ok, reason = should_trade(pred, db)
        if not ok:
            print(f"    [{mode_label}] SKIP {pred['market_id'][:12]}... — {reason}")
            continue

        # Extract liquidity from reasoning JSON (already computed during prediction)
        liquidity = None
        try:
            reasoning = json.loads(pred.get("reasoning", "{}"))
            liquidity = reasoning.get("liquidity")
        except (json.JSONDecodeError, TypeError):
            pass

        # Resolve CLOB tokens FIRST (needed for both pricing and order submission)
        tokens = None
        try:
            from predict import _get_clob_tokens_safe
            tokens = _get_clob_tokens_safe(pred["market_id"])
        except Exception as e:
            print(f"    CLOB token lookup failed: {e}")

        # Use live WS per-token prices (replaces stale Gamma implied prices)
        market_row = {"price_yes": pred["price_yes"],
                      "price_no": pred.get("price_no", round(1 - pred["price_yes"], 4))}
        gamma_yes = pred["price_yes"]
        gamma_no = round(1 - gamma_yes, 4)
        if tokens:
            yes_mid = _get_live_token_mid(tokens.get("yes", ""))
            no_mid = _get_live_token_mid(tokens.get("no", ""))

            # WS cache miss → try CLOB REST as fallback
            if yes_mid is None or no_mid is None:
                try:
                    from clob_depth import get_order_book, analyze_depth
                    if yes_mid is None and tokens.get("yes"):
                        book = get_order_book(tokens["yes"])
                        if book:
                            yes_mid = analyze_depth(book).get("mid")
                    if no_mid is None and tokens.get("no"):
                        book = get_order_book(tokens["no"])
                        if book:
                            no_mid = analyze_depth(book).get("mid")
                except Exception as e:
                    print(f"    [CLOB_REST] Fallback failed: {e}")

            if yes_mid is not None:
                market_row["price_yes"] = yes_mid
            if no_mid is not None:
                market_row["price_no"] = no_mid

            # DIAG: log source and gap
            src_yes = "ws" if _get_live_token_mid(tokens.get("yes", "")) else ("rest" if yes_mid else "gamma")
            src_no = "ws" if _get_live_token_mid(tokens.get("no", "")) else ("rest" if no_mid else "gamma")
            print(f"    [LIVE_OB] YES={market_row['price_yes']:.4f}({src_yes}) "
                  f"NO={market_row['price_no']:.4f}({src_no}) "
                  f"(Gamma: YES={gamma_yes:.4f})")
            if yes_mid and no_mid:
                print(f"    DIAG|gamma_yes={gamma_yes:.4f}|clob_yes={yes_mid:.4f}"
                      f"|gamma_no={gamma_no:.4f}|clob_no={no_mid:.4f}"
                      f"|gap_yes={abs(yes_mid - gamma_yes):.4f}"
                      f"|gap_no={abs(no_mid - gamma_no):.4f}")
            elif not yes_mid and not no_mid:
                print(f"    WARNING: Both CLOB sources failed — using Gamma prices")
                print(f"    DIAG|clob_fallback=true|side=BOTH|gamma_yes={gamma_yes:.4f}")

        order_params, order_reason = compute_order(pred, market_row, liquidity)

        if order_params is None:
            print(f"    [{mode_label}] SKIP {pred['market_id'][:12]}... — {order_reason}")
            continue

        # CLOB token ID for order submission (already resolved above)
        clob_token_id = None
        if tokens:
            clob_token_id = tokens.get(order_params["token"])

        # ── Phase 2 Diagnostics (log-only, no execution change) ──

        # Diagnostic A: Snapshot staleness (Tension 2)
        snapshot_age_ms = None
        fetched_at_str = pred.get("fetched_at")
        if fetched_at_str:
            try:
                fetched_at_dt = datetime.fromisoformat(fetched_at_str)
                snapshot_age_ms = (datetime.now(timezone.utc) - fetched_at_dt).total_seconds() * 1000
                print(f"    DIAG|snapshot_age_ms={snapshot_age_ms:.0f}|market={pred['market_id'][:12]}")
            except (ValueError, TypeError):
                pass

        # Diagnostic B: Conviction vs. price drift (Tension 1)
        if clob_token_id:
            try:
                from clob_depth import get_order_book, analyze_depth
                book = get_order_book(clob_token_id)
                if book:
                    depth = analyze_depth(book)
                    if depth:
                        live_mid = depth["mid"]
                        price_drift = abs(live_mid - pred["price_yes"])
                        conv = pred["conviction_score"]
                        print(f"    DIAG|conv={conv}|drift={price_drift:.4f}"
                              f"|snapshot_age_ms={snapshot_age_ms or 0:.0f}"
                              f"|live_mid={live_mid:.4f}|stored={pred['price_yes']:.4f}")
            except Exception as e:
                print(f"    DIAG|drift_fetch_failed={e}")

        # Place order
        order = place_order(
            db, pred["market_id"], pred["id"], order_params, cycle,
            clob_token_id=clob_token_id,
        )

        symbol = ">" if TRADING_ENABLED else "~"
        slip_cents = order_params.get('slippage', 0) * 100
        mkt_price = order_params.get('market_price', 0)
        print(f"    [{mode_label}] {symbol} {order_params['direction']} "
              f"${order_params['size']:.0f} @ {order_params['price_limit']:.2f} "
              f"(mkt={mkt_price:.2f}, slip={slip_cents:+.0f}¢) "
              f"— {order['status']}")
        orders.append(order)

    # Check order fills from previous cycles
    if TRADING_ENABLED:
        settled = settle_orders(db)
        if settled:
            print(f"    [{mode_label}] Settled {settled} order(s)")

    # Compute P&L for resolved markets
    pnl_updated = compute_order_pnl(db)
    if pnl_updated:
        print(f"    [{mode_label}] P&L computed for {pnl_updated} order(s)")

    return orders


# ── Kill switch ───────────────────────────────────────────────────────────────

def is_kill_switched():
    """Check if trading has been manually killed."""
    kill_file = Path(__file__).parent.parent / "data" / "KILL_SWITCH"
    if kill_file.exists():
        return True
    return os.getenv("KILL_SWITCH", "false").lower() == "true"


# ── Summary ───────────────────────────────────────────────────────────────────

def get_trading_summary(db):
    """Get a summary of today's trading activity."""
    ensure_orders_table(db)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    row = db.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status IN ('filled', 'settled', 'paper') THEN 1 ELSE 0 END) as executed,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
            COALESCE(SUM(size), 0) as total_wagered,
            COALESCE(SUM(pnl), 0) as total_pnl
        FROM orders
        WHERE placed_at LIKE ?
    """, (f"{today}%",)).fetchone()

    consec_losses = _check_consecutive_losses(db)

    return {
        "total_orders": row[0],
        "executed": row[1],
        "failed": row[2],
        "total_wagered": row[3],
        "total_pnl": row[4],
        "mode": "LIVE" if TRADING_ENABLED else "PAPER",
        "bet_size": BET_SIZE,
        "daily_loss_limit": DAILY_LOSS_LIMIT,
        "consecutive_losses": consec_losses,
        "consecutive_loss_max": CONSECUTIVE_LOSS_MAX,
        "breakers": {
            "consecutive_loss": consec_losses >= CONSECUTIVE_LOSS_MAX,
        },
    }
