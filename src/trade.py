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
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "predictions.db"

# ── Configuration (env vars, overridable) ─────────────────────────────────────

def _env(name, default):
    """Get env var, treating empty string same as unset."""
    val = os.getenv(name, "")
    return val if val else default

TRADING_ENABLED = _env("TRADING_ENABLED", "false").lower() == "true"
BET_SIZE = float(_env("BET_SIZE", "25"))  # Flat $25 medium grind
DAILY_LOSS_LIMIT = float(_env("DAILY_LOSS_LIMIT", "300"))
CONSECUTIVE_LOSS_MAX = int(_env("CONSECUTIVE_LOSS_MAX", "5"))  # Halt after 5 in a row
MAX_DRAWDOWN_PCT = float(_env("MAX_DRAWDOWN_PCT", "15"))  # 15% from peak equity
MIN_CONVICTION = int(_env("MIN_CONVICTION", "3"))
MAX_SLIPPAGE_PCT = float(_env("MAX_SLIPPAGE_PCT", "2.0"))  # 2% max
EDGE_THRESHOLD = float(_env("EDGE_THRESHOLD", "0.05"))  # 5% min edge

# ETH sizing — thinner book requires smaller bets
# ETH avg spread: 3.98%, max bet @2% slippage: $149
# Activates when trade.py handles ETH markets (conv≥3)
ETH_BET_SIZES = {3: 25, 4: 50, 5: 75}
ETH_MAX_BET_CEILING_PCT = 0.50  # Never exceed 50% of available liquidity @2%

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
    db.execute("PRAGMA busy_timeout=5000")
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

    # Max drawdown breaker — halt if drawdown from peak exceeds threshold
    dd_pct = _check_drawdown_pct(db)
    if dd_pct >= MAX_DRAWDOWN_PCT:
        return False, f"max_drawdown_breaker ({dd_pct:.1f}% >= {MAX_DRAWDOWN_PCT}%)"

    return True, "ok"


def _check_consecutive_losses(db):
    """Count current consecutive loss streak (most recent settled orders)."""
    rows = db.execute("""
        SELECT pnl FROM orders
        WHERE status = 'settled' AND pnl IS NOT NULL
        ORDER BY settled_at DESC LIMIT 50
    """).fetchall()
    streak = 0
    for (pnl,) in rows:
        if pnl < 0:
            streak += 1
        else:
            break
    return streak


def _check_drawdown_pct(db):
    """Compute current drawdown from peak cumulative P&L."""
    rows = db.execute("""
        SELECT pnl FROM orders
        WHERE status = 'settled' AND pnl IS NOT NULL
        ORDER BY settled_at ASC
    """).fetchall()
    if not rows:
        return 0.0

    cumulative = 0.0
    peak = 0.0
    for (pnl,) in rows:
        cumulative += pnl
        if cumulative > peak:
            peak = cumulative

    if peak <= 0:
        return 0.0

    drawdown = peak - cumulative
    return (drawdown / peak) * 100


def get_bet_size(prediction_row, liquidity=None):
    """Return bet size based on asset and conviction.

    BTC: flat $25 (medium grind phase).
    ETH: tiered by conviction, capped by book depth.
    """
    agent = prediction_row.get("agent", "")
    conviction = prediction_row.get("conviction_score", 0)

    if "eth" in agent.lower():
        base = ETH_BET_SIZES.get(conviction, 0)
        if liquidity and not liquidity.get("error"):
            ceiling = liquidity.get("max_bet_2pct", float("inf")) * ETH_MAX_BET_CEILING_PCT
            return min(base, ceiling)
        return base

    return BET_SIZE  # BTC flat $25


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
    # On 5-minute markets, being filled matters more than saving a few cents.
    # Price at estimate (our fair value) to aggressively cross the spread.
    if direction == "UP":
        side = "buy"
        token = "yes"
        price_limit = estimate
    else:
        side = "buy"
        token = "no"
        price_limit = 1 - estimate

    # Asset-aware sizing: BTC flat $25, ETH tiered by conviction
    size = get_bet_size(prediction_row, liquidity)
    if liquidity and not liquidity.get("error"):
        max_book = liquidity.get("max_bet_2pct", float("inf"))
        if max_book < size:
            size = max(0, max_book * 0.9)  # 90% of max to leave margin
            if size < 5:  # Not worth it below $5
                return None, f"book_too_thin (max@2%=${max_book:.0f})"

    return {
        "direction": direction,
        "side": side,
        "token": token,
        "size": round(size, 2),
        "price_limit": round(price_limit, 4),
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
        result = _submit_clob_order(
            token_id=clob_token_id,
            side=order_params["side"],
            size=order_params["size"],
            price=order_params["price_limit"],
        )
        order_record["order_id"] = result.get("orderID") or result.get("order_id")
        order_record["status"] = "submitted"
        order_record["reason"] = json.dumps(result)
    except Exception as e:
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
        chain_id=137,
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
        raise TimeoutError("CLOB order submission timed out after 10s")

    old_handler = _signal.signal(_signal.SIGALRM, _timeout_handler)
    _signal.alarm(10)  # 10-second hard timeout
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
            chain_id=137,
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

        # Build a lookup: order_id -> trade info
        # Trades reference our orders in two ways:
        # 1. taker_order_id (we were the taker)
        # 2. maker_orders[].order_id (we were the maker)
        filled_orders = {}  # order_id -> fill_price
        for trade in trades:
            # Check if we were the taker
            taker_oid = trade.get("taker_order_id", "")
            if taker_oid:
                filled_orders[taker_oid] = float(trade.get("price", 0))
            # Check if our order appears in maker_orders
            for maker in trade.get("maker_orders", []):
                moid = maker.get("order_id", "")
                if moid:
                    filled_orders[moid] = float(maker.get("price", 0))

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
                fill_price = filled_orders[order_id]
                db.execute("""
                    UPDATE orders SET status = 'filled', price_filled = ?,
                    filled_at = ? WHERE id = ?
                """, (fill_price, now, order_db_id))
                settled += 1
                print(f"  [TRADE] Order {order_id[:12]}... FILLED @ {fill_price:.3f}")
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
            pnl = size * (1.0 / price - 1) * 0.985  # 1.5% round-trip fee
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

    # Find predictions from this cycle that qualify
    cursor = db.execute("""
        SELECT p.id, p.market_id, p.estimate, p.conviction_score, p.reasoning,
               p.agent, m.price_yes, m.price_no, m.end_date
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
         "agent", "price_yes", "price_no", "end_date"],
        row
    )) for row in cursor.fetchall()]

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

        # Compute order params
        market_row = {"price_yes": pred["price_yes"], "price_no": pred["price_no"]}
        order_params, order_reason = compute_order(pred, market_row, liquidity)

        if order_params is None:
            print(f"    [{mode_label}] SKIP {pred['market_id'][:12]}... — {order_reason}")
            continue

        # Get CLOB token ID for live orders
        clob_token_id = None
        if TRADING_ENABLED:
            try:
                from predict import _get_clob_tokens
                tokens = _get_clob_tokens(pred["market_id"])
                if tokens:
                    clob_token_id = tokens[order_params["token"]]
            except Exception:
                pass

        # Place order
        order = place_order(
            db, pred["market_id"], pred["id"], order_params, cycle,
            clob_token_id=clob_token_id,
        )

        symbol = ">" if TRADING_ENABLED else "~"
        print(f"    [{mode_label}] {symbol} {order_params['direction']} "
              f"${order_params['size']:.0f} @ {order_params['price_limit']:.2f} "
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

    # Shadow indicators — compute and log (never blocks trades)
    try:
        from shadow_indicators import shadow_log_indicators
        shadow = shadow_log_indicators(db, cycle)
        if shadow:
            print(f"    [SHADOW] {shadow.get('summary', 'logged')}")
    except Exception as e:
        print(f"    [SHADOW] skipped: {e}")

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
    drawdown_pct = _check_drawdown_pct(db)

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
        "drawdown_pct": drawdown_pct,
        "max_drawdown_pct": MAX_DRAWDOWN_PCT,
        "breakers": {
            "consecutive_loss": consec_losses >= CONSECUTIVE_LOSS_MAX,
            "max_drawdown": drawdown_pct >= MAX_DRAWDOWN_PCT,
        },
    }
