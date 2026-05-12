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
    # FOK execution layer columns (Phase 1)
    for col, typ in [("order_type", "TEXT"), ("edge", "REAL"),
                     ("best_bid", "REAL"), ("best_ask", "REAL"),
                     ("spread", "REAL"), ("action", "TEXT")]:
        try:
            db.execute(f"ALTER TABLE orders ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass  # Column already exists
    db.commit()


# ── Core ──────────────────────────────────────────────────────────────────────

def should_trade(prediction_row, db, pipeline_name="btc_5m"):
    """
    Decide if a prediction should become a live order.

    Thin wrapper around system_state.get_system_state() — the runtime
    state contract. Signal gates (conviction, edge) remain here because
    they are prediction-level, not pipeline-level.

    Args:
        prediction_row: dict with keys from predictions table
        db: sqlite3 connection
        pipeline_name: which pipeline's state to consult

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

    # Pipeline-level gates: kill switch, daily loss, consecutive losses.
    # All via the single source of truth.
    from system_state import get_system_state
    state = get_system_state(db, pipeline_name)
    if not state.can_trade:
        return False, state.blockers[0]

    return True, "ok"


def _check_consecutive_losses(db):
    """Back-compat shim — delegates to system_state contract.

    Kept only for callers that still import this symbol. New code must
    use system_state.get_system_state() instead.
    """
    from system_state import get_system_state
    return get_system_state(db, "btc_5m").consecutive_losses




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

    Uses typed OrderbookCache dataclass for safe, validated reads.
    Written by botsy_engine.py Polymarket WS feed.

    Returns float mid if cache entry is fresh (<10s), else None.
    """
    from orderbook_cache import OrderbookCache
    cache = OrderbookCache.load(LIVE_ORDERBOOK_PATH, LIVE_ORDERBOOK_MAX_AGE_S)
    return cache.get_fresh_mid(token_id, LIVE_ORDERBOOK_MAX_AGE_S)


def _get_live_token_entry(token_id: str):
    """
    Read full token entry (bid/ask/spread/mid) from WS cache.

    Returns OrderbookCache.TokenEntry if fresh, else None.
    """
    from orderbook_cache import OrderbookCache
    cache = OrderbookCache.load(LIVE_ORDERBOOK_PATH, LIVE_ORDERBOOK_MAX_AGE_S)
    return cache.get_fresh_entry(token_id, LIVE_ORDERBOOK_MAX_AGE_S)


def compute_order(prediction_row, market_row, liquidity=None):
    """
    Compute order parameters from a prediction.

    Phase 1 FOK execution: compute edge against execution price (best_ask
    for BUY, no_best_ask for SELL). If edge >= min_edge, place FOK at
    best_ask. If edge < min_edge, skip. Falls back to legacy GTC logic
    when bid/ask data is unavailable (paper pipelines without WS feed).

    Returns:
        (dict, reason) — dict with direction, side, token, size, price_limit,
        edge, spread, best_bid, best_ask, action, order_type.
        Or (None, reason_string) if order can't be placed.
    """
    from config import FOK_EDGE_BUFFER, MAX_FAK_CUSHION, MIN_POST_CUSHION_EDGE

    estimate = prediction_row["estimate"]
    direction = "UP" if estimate > 0.5 else "DOWN"

    # CLOB verification gate — no CLOB price = no trade
    clob_verified = market_row.get("_clob_verified", {})
    market_price_yes = market_row.get("price_yes") or 0.5

    if direction == "UP":
        side = "buy"
        token = "yes"
        if not clob_verified.get("yes"):
            import logging
            logging.getLogger(__name__).info(
                f"DIAG|clob_skip=true|side=YES|gamma={market_price_yes:.4f}|reason=no_clob_price")
            return None, "no CLOB price for YES token"

        # FOK path: edge against execution price (AC-1.2, AC-2.1)
        best_ask = market_row.get("_yes_best_ask")
        best_bid = market_row.get("_yes_best_bid")
        spread = market_row.get("_yes_spread")

        if best_ask is not None and spread is not None:
            edge = round(estimate - best_ask, 4)
            min_edge = spread + FOK_EDGE_BUFFER
            if edge < min_edge:
                return None, f"skipped_low_edge (edge={edge:.4f} < min={min_edge:.4f})"
            spread_cushion = min(MAX_FAK_CUSHION, spread / 2)
            alpha_cushion = max(0.0, (estimate - best_ask) - MIN_POST_CUSHION_EDGE)
            cushion = min(spread_cushion, alpha_cushion)
            if cushion <= 0:
                return None, "skipped_cushion_eats_edge"
            price_limit = best_ask + cushion
            action = "fak_take"
            order_type = "fak"
        else:
            # Legacy fallback for paper pipelines without WS feed
            cushion = None
            fill_adjusted = estimate + FILL_PRIORITY_SPREAD
            max_price = market_price_yes + MAX_SLIPPAGE_SPREAD + FILL_PRIORITY_SPREAD
            price_limit = min(fill_adjusted, max_price)
            edge = round(abs(estimate - 0.5), 4)
            best_ask = None
            best_bid = None
            spread = None
            action = "gtc_legacy"
            order_type = "gtc"

    else:
        side = "buy"
        token = "no"
        market_price_no = market_row.get("price_no")
        if not clob_verified.get("no") or market_price_no is None:
            import logging
            logging.getLogger(__name__).info(
                f"DIAG|clob_skip=true|side=NO|implied={round(1 - market_price_yes, 4):.4f}|reason=no_clob_price")
            return None, "no CLOB price for NO token"

        # FOK path: edge against NO token execution price
        no_best_ask = market_row.get("_no_best_ask")
        no_best_bid = market_row.get("_no_best_bid")
        no_spread = market_row.get("_no_spread")

        if no_best_ask is not None and no_spread is not None:
            edge = round((1 - estimate) - no_best_ask, 4)
            min_edge = no_spread + FOK_EDGE_BUFFER
            if edge < min_edge:
                return None, f"skipped_low_edge (edge={edge:.4f} < min={min_edge:.4f})"
            spread_cushion = min(MAX_FAK_CUSHION, no_spread / 2)
            alpha_cushion = max(0.0, ((1 - estimate) - no_best_ask) - MIN_POST_CUSHION_EDGE)
            cushion = min(spread_cushion, alpha_cushion)
            if cushion <= 0:
                return None, "skipped_cushion_eats_edge"
            price_limit = no_best_ask + cushion
            best_ask = no_best_ask
            best_bid = no_best_bid
            spread = no_spread
            action = "fak_take"
            order_type = "fak"
        else:
            # Legacy fallback
            cushion = None
            fill_adjusted = (1 - estimate) + FILL_PRIORITY_SPREAD
            max_price = market_price_no + MAX_SLIPPAGE_SPREAD + FILL_PRIORITY_SPREAD
            price_limit = min(fill_adjusted, max_price)
            edge = round(abs(estimate - 0.5), 4)
            best_ask = None
            best_bid = None
            spread = None
            action = "gtc_legacy"
            order_type = "gtc"

    # Compute slippage vs market mid
    if direction == "UP":
        slippage = price_limit - market_price_yes
    else:
        slippage = price_limit - (market_price_no or round(1 - market_price_yes, 4))

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
        "edge": edge,
        "spread": spread,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "action": action,
        "order_type": order_type,
        "cushion": cushion,
    }, "ok"


def place_order(db, market_id, prediction_id, order_params, cycle,
                clob_token_id=None, trading_enabled=None, pipeline_name=None):
    """
    Place an order — either log-only (paper) or live via CLOB SDK.

    Args:
        trading_enabled: If provided, overrides the global TRADING_ENABLED.
            Resolved per-pipeline by execute_trades() via pipeline_control.
            Incident #66: the global is NOT the source of truth.

    Returns:
        order dict with status
    """
    if trading_enabled is None:
        trading_enabled = TRADING_ENABLED  # Legacy fallback

    # Defense-in-depth: warn if passed mode disagrees with global (Fix 4)
    if trading_enabled != TRADING_ENABLED:
        import logging
        logging.getLogger("trade").warning(
            f"TRADING_ENABLED global ({TRADING_ENABLED}) disagrees with "
            f"passed trading_enabled ({trading_enabled}). "
            f"Using passed value. (Incident #66 guard)"
        )

    now = datetime.now(timezone.utc).isoformat()
    mode = "live" if trading_enabled else "paper"

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
        # FOK metadata
        "order_type": order_params.get("order_type"),
        "edge": order_params.get("edge"),
        "best_bid": order_params.get("best_bid"),
        "best_ask": order_params.get("best_ask"),
        "spread": order_params.get("spread"),
        "action": order_params.get("action"),
    }

    def _diag(result_code, filled_size=None, filled_avg_price=None):
        try:
            import fill_diagnostic
            fill_diagnostic.init_table(db)
            fill_diagnostic.record(
                db,
                pipeline=pipeline_name or "unknown",
                result=result_code,
                prediction_id=prediction_id,
                cycle=cycle,
                decision_best_bid=order_params.get("best_bid"),
                decision_best_ask=order_params.get("best_ask"),
                decision_spread=order_params.get("spread"),
                requested_size=order_params.get("size"),
                requested_limit=order_params.get("price_limit"),
                filled_size=filled_size,
                filled_avg_price=filled_avg_price,
                order_type=order_params.get("order_type"),
                cushion=order_params.get("cushion"),
            )
        except Exception as _e:
            import logging
            logging.getLogger("trade").warning(f"fill_diagnostic.record failed: {_e}")

    if not trading_enabled:
        # Paper mode — log what we would have done
        order_record["status"] = "paper"
        order_record["reason"] = "trading_disabled"
        _store_order(db, order_record)
        _diag("paper_would_fire")
        return order_record

    # Live mode — submit to Polymarket CLOB
    if not clob_token_id:
        order_record["status"] = "failed"
        order_record["reason"] = "missing_clob_token_id"
        _store_order(db, order_record)
        _diag("missing_token")
        return order_record

    is_fak = order_params.get("order_type") in ("fak", "fok")

    try:
        t0 = time.monotonic()
        if is_fak:
            # FAK (IOC): take available liquidity, kill remainder
            result = _submit_fak_order(
                token_id=clob_token_id,
                side=order_params["side"],
                amount=order_params["size"],  # dollars, SDK handles conversion
                price=order_params["price_limit"],
            )
        else:
            # Legacy GTC path (paper pipelines without WS bid/ask)
            result = _submit_clob_order(
                token_id=clob_token_id,
                side=order_params["side"],
                size=order_params["size"],
                price=order_params["price_limit"],
            )
        rtt_ms = (time.monotonic() - t0) * 1000

        order_id = result.get("orderID") or result.get("order_id")
        order_record["order_id"] = order_id

        if is_fak:
            # FAK (IOC): immediate take or kill, partial fills allowed.
            status = (result.get("status") or "").upper()
            if status == "MATCHED" or result.get("success"):
                order_record["status"] = "filled"
                order_record["action"] = "fak_filled"
                order_record["filled_at"] = datetime.now(timezone.utc).isoformat()
                order_record["price_filled"] = order_params["price_limit"]
                print(f"    FAK|filled|rtt={rtt_ms:.0f}ms|edge={order_params.get('edge', '?')}")
                _diag(
                    "filled_full",
                    filled_size=order_params.get("size"),
                    filled_avg_price=order_params.get("price_limit"),
                )
            else:
                order_record["status"] = "fak_rejected"
                order_record["action"] = "fak_rejected"
                print(f"    FAK|rejected|rtt={rtt_ms:.0f}ms|reason={result.get('status', 'unknown')}")
                _diag("killed_fok", filled_size=0)
        else:
            # GTC: order rests in book, settle later
            order_record["status"] = "submitted"
            print(f"    DIAG|order_rtt_ms={rtt_ms:.0f}|status={result.get('status', 'ok')}")
            _diag("gtc_submitted")

        order_record["reason"] = json.dumps(result)
    except Exception as e:
        rtt_ms = (time.monotonic() - t0) * 1000
        print(f"    {'FAK' if is_fak else 'DIAG'}|order_rtt_ms={rtt_ms:.0f}|status=error")
        order_record["status"] = "failed"
        order_record["reason"] = str(e)
        _diag("submit_error")

    _store_order(db, order_record)
    return order_record


def _store_order(db, order):
    """Insert order record into the orders table."""
    db.execute("""
        INSERT INTO orders
        (market_id, prediction_id, direction, size, price_limit, price_filled,
         slippage_pct, status, order_id, mode, reason, placed_at, filled_at,
         settled_at, pnl, cycle,
         order_type, edge, best_bid, best_ask, spread, action)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order["market_id"], order["prediction_id"], order["direction"],
        order["size"], order["price_limit"], order.get("price_filled"),
        order.get("slippage_pct"), order["status"], order.get("order_id"),
        order["mode"], order.get("reason"), order["placed_at"],
        order.get("filled_at"), order.get("settled_at"), order.get("pnl"),
        order["cycle"],
        order.get("order_type"), order.get("edge"), order.get("best_bid"),
        order.get("best_ask"), order.get("spread"), order.get("action"),
    ))
    db.commit()


def check_fok_rejection_rate(db):
    """
    Check FOK rejection rate over last 50 FOK orders (AC-3.3).

    Returns (rate, alert) — rate is float 0-1, alert is True if > 30%.
    Returns (0, False) if fewer than 50 FOK orders exist.
    """
    rows = db.execute("""
        SELECT action FROM orders
        WHERE order_type = 'fok'
        ORDER BY id DESC
        LIMIT 50
    """).fetchall()
    if len(rows) < 50:
        return 0, False
    rejected = sum(1 for r in rows if r["action"] == "fok_rejected")
    rate = rejected / len(rows)
    return rate, rate > 0.30


def _init_clob_client():
    """
    Initialize and authenticate a ClobClient instance.

    Returns (client, BUY, SELL) tuple.
    Raises RuntimeError if SDK not installed or key not set.
    """
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.order_builder.constants import BUY, SELL
    except ImportError:
        raise RuntimeError(
            "py-clob-client not installed. Run: pip install py-clob-client"
        )

    private_key = os.environ.get("POLYMARKET_PRIVATE_KEY")
    if not private_key:
        raise RuntimeError("POLYMARKET_PRIVATE_KEY env var not set")

    proxy_address = os.environ.get("POLYMARKET_PROXY_ADDRESS", "")
    sig_type = 2 if proxy_address else 0
    client = ClobClient(
        "https://clob.polymarket.com",
        key=private_key,
        chain_id=POLYMARKET_CHAIN_ID,
        signature_type=sig_type,
        funder=proxy_address if proxy_address else None,
    )

    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    return client, BUY, SELL


def _submit_clob_order(token_id, side, size, price):
    """
    Submit a GTC limit order to Polymarket CLOB (legacy path for paper pipelines).

    Returns API response dict: {"success": bool, "orderID": str, "status": str}
    """
    from py_clob_client.clob_types import OrderArgs

    client, BUY, SELL = _init_clob_client()

    shares = round(size / price, 2) if price > 0 else 0
    clob_side = BUY if side.upper() == "BUY" else SELL

    order_args = OrderArgs(
        token_id=token_id,
        price=round(price, 2),
        size=shares,
        side=clob_side,
    )

    # Thread-safe timeout (SIGALRM only works from main thread; the VPS
    # engine dispatches pipelines off the main thread).
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FTimeout
    with ThreadPoolExecutor(max_workers=1) as _ex:
        _fut = _ex.submit(client.create_and_post_order, order_args)
        try:
            response = _fut.result(timeout=API_TIMEOUT_SUBMIT)
        except _FTimeout:
            raise TimeoutError(
                f"CLOB order submission timed out after {API_TIMEOUT_SUBMIT}s"
            )

    return response


def _submit_fak_order(token_id, side, amount, price):
    """
    Submit a Fill-And-Kill (IOC) order to Polymarket CLOB.

    FAK takes whatever liquidity is available at the limit and cancels
    the unfilled remainder. Allows partial fills (unlike FOK).

    Args:
        token_id: CLOB token ID for the outcome
        side: "BUY" or "SELL"
        amount: Dollar amount (NOT shares — SDK handles conversion)
        price: Execution price (best_ask for BUY, best_bid for SELL)

    Returns:
        API response dict. FOK fills are immediate — check response for
        fill status. No pending→filled transition needed.
    """
    from py_clob_client.clob_types import MarketOrderArgs, OrderType

    client, BUY, SELL = _init_clob_client()

    clob_side = BUY if side.upper() == "BUY" else SELL

    market_order_args = MarketOrderArgs(
        token_id=token_id,
        amount=round(amount, 2),
        side=clob_side,
        price=round(price, 2),
    )

    # Thread-safe timeout (SIGALRM only works from main thread; the VPS
    # engine dispatches pipelines off the main thread).
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FTimeout

    def _submit():
        signed_order = client.create_market_order(market_order_args)
        return client.post_order(signed_order, orderType=OrderType.FAK)

    with ThreadPoolExecutor(max_workers=1) as _ex:
        _fut = _ex.submit(_submit)
        try:
            response = _fut.result(timeout=API_TIMEOUT_SUBMIT)
        except _FTimeout:
            raise TimeoutError(
                f"FOK order submission timed out after {API_TIMEOUT_SUBMIT}s"
            )

    return response


# Backward-compat alias during FOK→FAK transition.
_submit_fok_order = _submit_fak_order


# ── Settlement ────────────────────────────────────────────────────────────────

def settle_orders(db, trading_enabled=None):
    """
    Check submitted orders and update fill status using get_trades().

    get_order() returns 404 for resolved 5-minute markets, so we use
    get_trades() which returns all historical fills for our wallet.
    We match trades to our pending orders by order_id.

    Orders not found in trades after the market has resolved are marked expired.

    Returns number of orders settled.
    """
    if trading_enabled is None:
        trading_enabled = TRADING_ENABLED
    if not trading_enabled:
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
    Compute P&L for orders whose markets have resolved.

    Two paths:
      - LIVE: status='filled' → 'settled', pnl from price_filled.
      - PAPER: status='paper' → 'paper_settled', pnl assuming optimistic
        fill at price_limit. Paper P&L is the upper-bound "what the
        signal said." Real fill cost is measured separately via
        fill_diagnostic on live FAK attempts.

    Paper rows use a distinct status ('paper_settled') so they are
    naturally excluded from the live circuit breaker in
    system_state._compute_daily_loss().

    Returns number of orders with newly computed P&L.
    """
    cursor = db.execute("""
        SELECT o.id, o.direction, o.size, o.price_filled, o.price_limit,
               o.status, m.outcome
        FROM orders o
        JOIN markets m ON o.market_id = m.id
        WHERE o.status IN ('filled', 'paper')
          AND o.pnl IS NULL AND m.resolved = 1
    """)
    rows = cursor.fetchall()

    updated = 0
    for row in rows:
        order_id, direction, size, price_filled, price_limit, status, outcome = row

        # Did we win?
        if direction == "UP":
            won = outcome == 1
        else:
            won = outcome == 0

        # Paper rows assume optimistic fill at price_limit.
        is_paper = status == "paper"
        execution_price = price_limit if is_paper else (price_filled or 0.5)
        new_status = "paper_settled" if is_paper else "settled"

        if won:
            # Payout is $1 per share. Profit = (1/price - 1) * size * (1 - fee)
            pnl = size * (1.0 / execution_price - 1) * POLYMARKET_FEE_FACTOR
        else:
            pnl = -size

        now = datetime.now(timezone.utc).isoformat()
        if is_paper:
            db.execute("""
                UPDATE orders SET pnl = ?, settled_at = ?, status = ?,
                                  price_filled = ?
                WHERE id = ?
            """, (round(pnl, 2), now, new_status, execution_price, order_id))
        else:
            db.execute("""
                UPDATE orders SET pnl = ?, settled_at = ?, status = ?
                WHERE id = ?
            """, (round(pnl, 2), now, new_status, order_id))
        updated += 1

    if updated:
        db.commit()
    return updated


# ── Extracted functions (Phase B refactoring, 2026-04-05) ─────────────────────


def resolve_clob_prices(pred, tokens):
    """
    Resolve CLOB prices for a prediction's market via WS cache + REST fallback.

    Returns:
        (market_row, tokens) where market_row has price_yes, price_no,
        and _clob_verified dict. tokens is passed through for order submission.
    """
    market_row = {
        "price_yes": pred["price_yes"],
        "price_no": pred.get("price_no", round(1 - pred["price_yes"], 4)),
    }
    gamma_yes = pred["price_yes"]
    gamma_no = round(1 - gamma_yes, 4)

    if not tokens:
        market_row["_orderbook_cache"] = {"yes": "missing", "no": "missing"}
        return market_row, tokens

    # Try WS cache first — get full entry (bid/ask/spread/mid)
    yes_token = tokens.get("yes", "")
    no_token = tokens.get("no", "")
    yes_entry = _get_live_token_entry(yes_token)
    no_entry = _get_live_token_entry(no_token)
    from orderbook_cache import OrderbookCache
    cache = OrderbookCache.load(LIVE_ORDERBOOK_PATH, LIVE_ORDERBOOK_MAX_AGE_S)
    yes_status = (
        {"status": "fresh", "age_ms": yes_entry.age_ms()}
        if yes_entry else cache.entry_status(yes_token, LIVE_ORDERBOOK_MAX_AGE_S)
    )
    no_status = (
        {"status": "fresh", "age_ms": no_entry.age_ms()}
        if no_entry else cache.entry_status(no_token, LIVE_ORDERBOOK_MAX_AGE_S)
    )
    market_row["_orderbook_cache"] = {
        "yes": yes_status["status"],
        "no": no_status["status"],
        "yes_age_ms": yes_status["age_ms"],
        "no_age_ms": no_status["age_ms"],
        "rest_fallback": False,
    }

    yes_mid = yes_entry.valid_mid() if yes_entry else None
    no_mid = no_entry.valid_mid() if no_entry else None

    # Populate bid/ask/spread from WS cache
    if yes_entry:
        market_row["_yes_best_bid"] = yes_entry.best_bid
        market_row["_yes_best_ask"] = yes_entry.best_ask
        market_row["_yes_spread"] = yes_entry.spread
    if no_entry:
        market_row["_no_best_bid"] = no_entry.best_bid
        market_row["_no_best_ask"] = no_entry.best_ask
        market_row["_no_spread"] = no_entry.spread

    # WS cache miss → try CLOB REST as fallback
    if yes_mid is None or no_mid is None:
        try:
            from clob_depth import get_order_book, analyze_depth
            if yes_mid is None and tokens.get("yes"):
                book = get_order_book(tokens["yes"])
                if book:
                    depth = analyze_depth(book)
                    yes_mid = depth.get("mid")
                    if "_yes_best_ask" not in market_row:
                        market_row["_yes_best_bid"] = depth.get("best_bid")
                        market_row["_yes_best_ask"] = depth.get("best_ask")
                        market_row["_yes_spread"] = depth.get("spread")
                    market_row["_orderbook_cache"]["rest_fallback"] = True
            if no_mid is None and tokens.get("no"):
                book = get_order_book(tokens["no"])
                if book:
                    depth = analyze_depth(book)
                    no_mid = depth.get("mid")
                    if "_no_best_ask" not in market_row:
                        market_row["_no_best_bid"] = depth.get("best_bid")
                        market_row["_no_best_ask"] = depth.get("best_ask")
                        market_row["_no_spread"] = depth.get("spread")
                    market_row["_orderbook_cache"]["rest_fallback"] = True
        except Exception as e:
            print(f"    [CLOB_REST] Fallback failed: {e}")

    if yes_mid is not None:
        market_row["price_yes"] = yes_mid
    if no_mid is not None:
        market_row["price_no"] = no_mid

    # Mark which tokens have real CLOB prices — compute_order() gates on this
    market_row["_clob_verified"] = {
        "yes": yes_mid is not None,
        "no": no_mid is not None,
    }

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
    else:
        missing = []
        if not yes_mid:
            missing.append("YES")
        if not no_mid:
            missing.append("NO")
        print(f"    DIAG|clob_missing={'+'.join(missing)}|gamma_yes={gamma_yes:.4f}|gamma_no={gamma_no:.4f}")

    return market_row, tokens


def _emit_orderbook_cache_diag(market_row):
    """Log true orderbook freshness and cache coverage at consumer read time."""
    meta = market_row.get("_orderbook_cache") or {}
    ages = [
        age for age in (meta.get("yes_age_ms"), meta.get("no_age_ms"))
        if age is not None
    ]
    if ages:
        print(f"    DIAG|orderbook_age_ms={max(ages):.0f}")
    print(
        "    DIAG|orderbook_cache="
        f"yes:{meta.get('yes', 'unknown')},"
        f"no:{meta.get('no', 'unknown')},"
        f"rest_fallback:{str(bool(meta.get('rest_fallback'))).lower()}"
    )


def run_shadow_logging(db, cycle):
    """
    Run shadow indicators and shadow conviction scorer.

    Called every cycle regardless of qualifying predictions to ensure
    data collection during MEAN_REVERTING and other low-conviction regimes.
    """
    # Shadow indicators
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


def record_diagnostics(pred, clob_token_id, market_data_age_ms=None):
    """
    Log Phase 2 diagnostics: market data age and conviction-vs-drift.

    Log-only, no execution change. Helps measure CLOB price reliability
    and detect when conviction doesn't match live price movement.
    """
    # Diagnostic A: Gamma/market-row data age. This is intentionally not
    # decision_delay_ms, which is emitted by predict.py from candle close time.
    fetched_at_str = pred.get("fetched_at")
    if fetched_at_str:
        try:
            fetched_at_dt = datetime.fromisoformat(fetched_at_str)
            market_data_age_ms = (datetime.now(timezone.utc) - fetched_at_dt).total_seconds() * 1000
            print(f"    DIAG|market_data_age_ms={market_data_age_ms:.0f}|market={pred['market_id'][:12]}")
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
                          f"|market_data_age_ms={market_data_age_ms or 0:.0f}"
                          f"|live_mid={live_mid:.4f}|stored={pred['price_yes']:.4f}")
        except Exception as e:
            print(f"    DIAG|drift_fetch_failed={e}")

    return market_data_age_ms


# ── Execution hook (called from ci_run.py) ────────────────────────────────────

def execute_trades(db, cycle, pipeline_name=None):
    """
    Main entry point: scan recent predictions, place orders for qualifying ones.

    Args:
        pipeline_name: If provided, resolve trading mode from pipeline_control
            instead of the global TRADING_ENABLED. Incident #66: the global
            is NOT the source of truth.

    Returns:
        list of order dicts
    """
    # Resolve trading mode per-pipeline (Fix 1: isolation by construction)
    if pipeline_name:
        from pipeline_control import is_pipeline_live, is_pipeline_live_canary
        if is_pipeline_live_canary(pipeline_name):
            try:
                from canary_readiness import btc5m_live_canary_blockers
                blockers = btc5m_live_canary_blockers(db)
            except Exception as exc:
                blockers = [f"canary_readiness_unavailable ({exc})"]
            if blockers:
                print(
                    "  [CANARY] live_canary blocked; staying PAPER: "
                    + "; ".join(blockers[:5])
                )
                trading_enabled = False
            else:
                trading_enabled = True
        else:
            trading_enabled = is_pipeline_live(pipeline_name)
    else:
        trading_enabled = TRADING_ENABLED  # Legacy fallback

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

    run_shadow_logging(db, cycle)

    if not predictions:
        return []

    orders = []
    mode_label = "LIVE" if trading_enabled else "PAPER"
    print(f"\n  [{mode_label}] Processing {len(predictions)} qualifying prediction(s)...")

    for pred in predictions:
        # Check trade gates (but don't skip yet — shadow maker needs to fire first)
        ok, reason = should_trade(pred, db, pipeline_name=pipeline_name or "btc_5m")

        # Extract liquidity from reasoning JSON (already computed during prediction)
        liquidity = None
        try:
            reasoning = json.loads(pred.get("reasoning", "{}"))
            liquidity = reasoning.get("liquidity")
        except (json.JSONDecodeError, TypeError):
            pass

        # Resolve CLOB tokens + prices (WS cache → REST fallback → skip)
        tokens = None
        try:
            from clob_depth import get_clob_tokens_safe
            tokens = get_clob_tokens_safe(pred["market_id"])
        except Exception as e:
            print(f"    CLOB token lookup failed: {e}")

        market_row, tokens = resolve_clob_prices(pred, tokens)
        _emit_orderbook_cache_diag(market_row)

        order_params, order_reason = compute_order(pred, market_row, liquidity) if ok else (None, reason)

        # ── Shadow maker logging (Phase 1: measurement only) ──────────
        # Fires for ALL conv≥3 predictions — both traded and skipped.
        try:
            import shadow_maker
            _sm_dir = "UP" if pred["estimate"] > 0.5 else "DOWN"
            if _sm_dir == "UP":
                _sm_bid = market_row.get("_yes_best_bid")
                _sm_ask = market_row.get("_yes_best_ask")
                _sm_spr = market_row.get("_yes_spread")
            else:
                _sm_bid = market_row.get("_no_best_bid")
                _sm_ask = market_row.get("_no_best_ask")
                _sm_spr = market_row.get("_no_spread")
            _sm_mid = (_sm_bid + _sm_ask) / 2 if _sm_bid and _sm_ask else None
            _sm_price, _sm_side = shadow_maker.compute_shadow_price(
                _sm_dir, _sm_bid, _sm_ask, _sm_spr, _sm_mid)
            if _sm_price is not None:
                shadow_maker.record(
                    db,
                    prediction_id=pred["id"],
                    market_id=pred["market_id"],
                    pipeline=pipeline_name or "btc_5m",
                    cycle=cycle,
                    direction=_sm_dir,
                    estimate=pred["estimate"],
                    conviction=pred["conviction_score"],
                    regime=pred.get("regime", ""),
                    best_bid=_sm_bid, best_ask=_sm_ask,
                    spread=_sm_spr, mid=_sm_mid,
                    shadow_price=_sm_price, shadow_side=_sm_side,
                    taker_price=order_params.get("price_limit") if order_params else None,
                    taker_action="placed" if order_params else (order_reason or reason),
                )
        except Exception as _sm_err:
            print(f"    [shadow_maker] {_sm_err}")  # debug; must never break hot path

        if not ok:
            print(f"    [{mode_label}] SKIP {pred['market_id'][:12]}... — {reason}")
            continue

        if order_params is None:
            print(f"    [{mode_label}] SKIP {pred['market_id'][:12]}... — {order_reason}")
            # Record skips to fill_diagnostic for adverse-selection analysis
            try:
                import fill_diagnostic
                fill_diagnostic.init_table(db)
                if "cushion_eats_edge" in order_reason:
                    result_code = "skipped_cushion_eats_edge"
                elif "low_edge" in order_reason:
                    result_code = "skipped_low_edge"
                elif "book_too_thin" in order_reason:
                    result_code = "skipped_thin_book"
                else:
                    result_code = "skipped_other"
                fill_diagnostic.record(
                    db,
                    pipeline=pipeline_name or "unknown",
                    result=result_code,
                    prediction_id=pred["id"],
                    cycle=cycle,
                    decision_best_bid=market_row.get("_yes_best_bid"),
                    decision_best_ask=market_row.get("_yes_best_ask"),
                    decision_spread=market_row.get("_yes_spread"),
                )
            except Exception as _e:
                import logging
                logging.getLogger("trade").warning(f"fill_diagnostic skip-record failed: {_e}")
            continue

        # CLOB token ID for order submission (already resolved above)
        clob_token_id = None
        if tokens:
            clob_token_id = tokens.get(order_params["token"])

        # Phase 2 diagnostics (log-only, no execution change)
        record_diagnostics(pred, clob_token_id)

        # Place order
        order = place_order(
            db, pred["market_id"], pred["id"], order_params, cycle,
            clob_token_id=clob_token_id,
            trading_enabled=trading_enabled,
            pipeline_name=pipeline_name,
        )

        symbol = ">" if trading_enabled else "~"
        slip_cents = order_params.get('slippage', 0) * 100
        mkt_price = order_params.get('market_price', 0)
        print(f"    [{mode_label}] {symbol} {order_params['direction']} "
              f"${order_params['size']:.0f} @ {order_params['price_limit']:.2f} "
              f"(mkt={mkt_price:.2f}, slip={slip_cents:+.0f}¢) "
              f"— {order['status']}")
        orders.append(order)

    # Check order fills from previous cycles
    if trading_enabled:
        settled = settle_orders(db, trading_enabled=trading_enabled)
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

def get_trading_summary(db, pipeline_name=None):
    """Get a summary of today's trading activity.

    Thin wrapper around the system_state contract plus a few order-level
    aggregates that aren't part of the runtime state contract (total
    wagered, failed count).
    """
    ensure_orders_table(db)
    from system_state import get_system_state
    state = get_system_state(db, pipeline_name or "btc_5m")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = db.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status IN ('filled', 'settled', 'paper') THEN 1 ELSE 0 END) as executed,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
            COALESCE(SUM(size), 0) as total_wagered
        FROM orders
        WHERE placed_at LIKE ?
    """, (f"{today}%",)).fetchone()

    return {
        "total_orders": row[0],
        "executed": row[1],
        "failed": row[2],
        "total_wagered": row[3],
        "total_pnl": state.total_pnl_today,
        "mode": state.mode,
        "bet_size": BET_SIZE,
        "daily_loss_limit": state.daily_loss_limit,
        "consecutive_losses": state.consecutive_losses,
        "consecutive_loss_max": state.consecutive_loss_max,
        "breakers": {
            "consecutive_loss": state.consecutive_losses >= state.consecutive_loss_max,
        },
        "can_trade": state.can_trade,
        "blockers": state.blockers,
        "is_healthy": state.is_healthy,
        "health_warnings": state.health_warnings,
    }
