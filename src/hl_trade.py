"""
hl_trade.py — Order execution for Hyperliquid USDT perpetual futures.

Converts momentum predictions with conviction >= 3 into limit orders.
Two modes controlled by HL_TRADING_ENABLED env var:
  - False (default): Log what we WOULD trade, no orders placed.
  - True: Place real limit orders via hyperliquid-python-sdk.

Position lifecycle:
  1. Open on qualifying momentum signal (streak >= 3, non-mean-reverting regime)
  2. Close on: time ceiling (6 cycles / 30min), or stop-loss
  3. One position at a time.

Uses limit orders to earn maker rebate (0.02% credit).
Hyperliquid settles on-chain on Arbitrum — no counterparty risk.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import (
    HL_BET_SIZE, HL_DAILY_LOSS_LIMIT, HL_MAX_HOLD_CYCLES,
    HL_STOP_ATR_MULT, HL_FEE_RATE, HL_MIN_CONVICTION,
    CONSECUTIVE_LOSS_MAX, EDGE_THRESHOLD,
    FILL_PRIORITY_SPREAD, _env,
)
from hl_markets import (
    get_open_position, get_open_positions, get_position_by_id,
    open_position, close_position as close_position_db,
    increment_cycles_held,
)
from bybit_trade import compute_atr  # Shared utility — pure computation

HL_TRADING_ENABLED = _env("HL_TRADING_ENABLED", "false").lower() == "true"


def _fd_record(db, **kwargs):
    """Fire-and-forget fill_diagnostic.record for HL terminal events."""
    try:
        from fill_diagnostic import record
        record(db, pipeline="hl", **kwargs)
    except Exception:
        pass


# ── Risk gates ───────────────────────────────────────────────────────────────

def should_trade_hl(prediction_row, db):
    """
    Decide if a prediction should become a live order.

    Returns:
        (should_trade: bool, reason: str)
    """
    conv = prediction_row.get("conviction_score", 0)
    if conv < HL_MIN_CONVICTION:
        return False, f"conviction_too_low ({conv})"

    estimate = prediction_row.get("estimate", 0.5)
    edge = abs(estimate - 0.5)
    if edge < EDGE_THRESHOLD:
        return False, f"edge_too_small ({edge:.3f})"

    from system_state import get_system_state
    state = get_system_state(db, "hl")
    if state.kill_switch:
        return False, "kill_switch_active"
    if state.daily_loss >= HL_DAILY_LOSS_LIMIT:
        return False, f"daily_loss_limit (${state.daily_loss:.0f} >= ${HL_DAILY_LOSS_LIMIT:.0f})"
    if state.consecutive_losses >= CONSECUTIVE_LOSS_MAX:
        return False, (
            f"consecutive_loss_breaker ({state.consecutive_losses} >= {CONSECUTIVE_LOSS_MAX})"
        )

    return True, "ok"


def _check_consecutive_losses(db):
    """Delegates to system_state contract."""
    from system_state import get_system_state
    return get_system_state(db, "hl").consecutive_losses


def _check_drawdown_pct(db):
    """Compute current drawdown from peak cumulative P&L."""
    rows = db.execute("""
        SELECT pnl FROM positions
        WHERE status = 'closed' AND pnl IS NOT NULL
        ORDER BY closed_at ASC
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


# ── Order computation ────────────────────────────────────────────────────────

def compute_hl_order(prediction_row, mark_price, atr):
    """
    Compute order parameters from a prediction.

    Returns dict with: side, qty, price, stop_loss, symbol, order_type
    Uses limit orders to earn maker rebate (-0.02%).
    """
    estimate = prediction_row["estimate"]
    direction = "UP" if estimate > 0.5 else "DOWN"
    side = "Buy" if direction == "UP" else "Sell"

    qty = HL_BET_SIZE

    # Limit price: mark +/- fill priority spread
    spread_dollars = mark_price * FILL_PRIORITY_SPREAD
    if side == "Buy":
        price = round(mark_price + spread_dollars, 2)
    else:
        price = round(mark_price - spread_dollars, 2)

    # Stop-loss: entry +/- ATR * multiplier
    sl_distance = atr * HL_STOP_ATR_MULT
    if side == "Buy":
        stop_loss = round(mark_price - sl_distance, 2)
    else:
        stop_loss = round(mark_price + sl_distance, 2)

    return {
        "direction": direction,
        "side": side,
        "qty": qty,
        "price": price,
        "stop_loss": stop_loss,
        "symbol": "BTC",
        "order_type": "Limit",
        "mark_price": mark_price,
        "atr": atr,
    }


# ── Order placement ──────────────────────────────────────────────────────────

def place_hl_order(db, market_id, prediction_id, order_params, cycle):
    """
    Place a Hyperliquid order. Paper mode logs; live mode uses SDK.

    Also opens a position in the positions table.
    """
    now = datetime.now(timezone.utc).isoformat()
    mode = "live" if HL_TRADING_ENABLED else "paper"

    order_record = {
        "market_id": market_id,
        "prediction_id": prediction_id,
        "direction": order_params["direction"],
        "size": order_params["qty"],
        "price_limit": order_params["price"],
        "status": "pending",
        "mode": mode,
        "placed_at": now,
        "cycle": cycle,
    }

    hl_order_id = None

    if HL_TRADING_ENABLED:
        try:
            hl_order_id = _submit_hl_order(order_params)
            order_record["status"] = "submitted"
            order_record["order_id"] = hl_order_id
            _fd_record(
                db, result="hl_limit_submitted", cycle=cycle,
                requested_size=order_params["qty"],
                requested_limit=order_params["price"],
                order_type=order_params.get("order_type"),
            )
        except Exception as e:
            print(f"    [hl] Order failed: {e}")
            order_record["status"] = "failed"
            order_record["reason"] = str(e)
            _fd_record(
                db, result="hl_limit_rejected", cycle=cycle,
                requested_size=order_params["qty"],
                requested_limit=order_params["price"],
                order_type=order_params.get("order_type"),
            )
    else:
        order_record["status"] = "paper"
        order_record["price_filled"] = order_params["mark_price"]
        _fd_record(
            db, result="paper_would_fire", cycle=cycle,
            requested_size=order_params["qty"],
            requested_limit=order_params["price"],
            order_type=order_params.get("order_type"),
        )

    # Store order
    db.execute("""
        INSERT INTO orders (market_id, prediction_id, direction, size, price_limit,
                            price_filled, status, order_id, mode, reason, placed_at, cycle)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_record["market_id"], order_record["prediction_id"],
        order_record["direction"], order_record["size"],
        order_record["price_limit"], order_record.get("price_filled"),
        order_record["status"], order_record.get("order_id"),
        order_record["mode"], order_record.get("reason"),
        order_record["placed_at"], order_record["cycle"],
    ))
    db.commit()

    # Open position
    entry_price = order_record.get("price_filled") or order_params["mark_price"]
    open_position(
        db, market_id, order_params["side"], order_params["qty"],
        entry_price, order_params["stop_loss"], hl_order_id,
    )

    return order_record


def _submit_hl_order(order_params):
    """Submit order to Hyperliquid via SDK. Returns order response."""
    try:
        from hyperliquid.exchange import Exchange
        from eth_account import Account

        wallet = Account.from_key(os.getenv("HL_PRIVATE_KEY", ""))
        exchange = Exchange(wallet, base_url="https://api.hyperliquid.xyz")

        is_buy = order_params["side"] == "Buy"
        result = exchange.order(
            order_params["symbol"],
            is_buy,
            order_params["qty"],
            order_params["price"],
            {"limit": {"tif": "Gtc"}},
        )

        status = result.get("status", "")
        if status == "ok":
            return result.get("response", {}).get("data", {}).get("statuses", [{}])[0].get("resting", {}).get("oid", "")

        raise Exception(f"HL order error: {result}")

    except ImportError:
        raise Exception("hyperliquid-python-sdk not installed")


# ── Exit logic ───────────────────────────────────────────────────────────────

def check_exit_conditions(candles, position):
    """
    Check if the open position should be closed.

    Returns:
        (should_exit: bool, reason: str)
    """
    # Time ceiling: max hold duration
    if position["cycles_held"] >= HL_MAX_HOLD_CYCLES:
        return True, "time_ceiling"

    return False, "hold"


def close_hl_position(db, position, reason, mark_price, funding_rate=0.0):
    """Close an open position. Paper mode updates DB; live mode places closing order."""
    close_price = mark_price

    hl_order_id = None
    if HL_TRADING_ENABLED:
        try:
            from hyperliquid.exchange import Exchange
            from eth_account import Account

            wallet = Account.from_key(os.getenv("HL_PRIVATE_KEY", ""))
            exchange = Exchange(wallet, base_url="https://api.hyperliquid.xyz")

            is_buy = position["side"] != "Buy"  # Opposite side to close
            result = exchange.order(
                "BTC", is_buy, position["size"], close_price,
                {"limit": {"tif": "Ioc"}},  # IOC for immediate close
                reduce_only=True,
            )
            if result.get("status") == "ok":
                hl_order_id = "closed"
        except Exception as e:
            print(f"    [hl] Close order failed: {e}")

    funding_cost = _compute_funding_cost(
        position["side"], position["size"], position["entry_price"],
        position.get("cycles_held", 0) or 0, funding_rate,
    )
    pnl = _compute_pnl(position["side"], position["size"],
                        position["entry_price"], close_price, funding_cost)

    close_position_db(db, position["id"], close_price, pnl, reason,
                      hl_order_id, funding_cost=funding_cost)

    print(f"    [hl] Closed {position['side']} @ ${close_price:,.2f} "
          f"(reason={reason}, PnL=${pnl:.2f})")

    _fd_record(
        db, result=f"hl_exit_{reason}",
        filled_size=position["size"], filled_avg_price=close_price,
    )

    return {"pnl": pnl, "reason": reason, "close_price": close_price}


def _compute_pnl(side, size, entry_price, close_price, funding_cost=0.0):
    """Compute PnL for a position, net of fees and funding.

    Hyperliquid maker rebate: HL_FEE_RATE is negative (-0.0002),
    meaning fees reduce cost (we earn from placing limit orders).
    """
    if side == "Buy":
        raw_pnl = (close_price - entry_price) * size
    else:
        raw_pnl = (entry_price - close_price) * size

    notional = entry_price * size
    fees = notional * HL_FEE_RATE * 2  # Negative = credit
    return round(raw_pnl - fees - funding_cost, 4)


def _compute_funding_cost(side, size, entry_price, cycles_held,
                           funding_rate, cycle_minutes=5):
    """Accrue funding for a perp position.

    Hyperliquid uses 1-hour funding (vs Bybit's 8-hour).
    Longs pay when rate > 0, receive when rate < 0.
    """
    if funding_rate is None or funding_rate == 0 or cycles_held <= 0:
        return 0.0
    notional = entry_price * size
    held_hours = cycles_held * cycle_minutes / 60.0
    fraction = held_hours / 1.0  # 1-hour funding cycle
    charge = notional * funding_rate * fraction
    if side != "Buy":
        charge = -charge
    return round(charge, 6)


# ── Main entry point ─────────────────────────────────────────────────────────

def execute_hl_trades(db, cycle, candles, prediction=None, funding_rate=0.0):
    """
    Main trade execution entry point. Called from ci_run_hl.py.

    Flow:
    1. Check exit conditions on ALL open positions
    2. Enter new position if qualifying signal (max 1 concurrent)
    """
    orders = []
    mark_price = candles[-1]["close"] if candles else None

    # 1. Check exit conditions on ALL open positions
    for pos in get_open_positions(db):
        increment_cycles_held(db, pos["id"])
        pos = get_position_by_id(db, pos["id"])

        if pos and mark_price:
            should_exit, reason = check_exit_conditions(candles, pos)
            if should_exit:
                result = close_hl_position(db, pos, reason, mark_price,
                                           funding_rate=funding_rate)
                orders.append({"action": "close", **result})

    # 2. Enter new position (max 1 concurrent)
    if get_open_position(db):
        print(f"    [hl] Position already open — skipping new entry")
        return orders

    if prediction and mark_price:
        can_trade, reason = should_trade_hl(prediction, db)

        if can_trade:
            atr = compute_atr(candles)
            order_params = compute_hl_order(prediction, mark_price, atr)

            print(f"    [hl] {order_params['side']} {order_params['qty']} BTC "
                  f"@ ${order_params['price']:,.2f} "
                  f"(SL=${order_params['stop_loss']:,.2f}, ATR=${atr:.0f})")

            order = place_hl_order(db, prediction["market_id"],
                                   prediction.get("id"), order_params, cycle)
            orders.append({"action": "open", **order})
        else:
            print(f"    [hl] Skip: {reason}")

    return orders


# ── Kill switch ──────────────────────────────────────────────────────────────

def is_hl_kill_switched():
    """Check if HL trading has been manually killed."""
    kill_file = Path(__file__).parent.parent / "data" / "KILL_SWITCH_HL"
    if kill_file.exists():
        return True
    return os.getenv("KILL_SWITCH_HL", "false").lower() == "true"


# ── Summary ──────────────────────────────────────────────────────────────────

def get_hl_trading_summary(db):
    """Get a summary of today's HL trading activity."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    opened = db.execute("""
        SELECT COUNT(*) FROM positions WHERE opened_at LIKE ?
    """, (f"{today}%",)).fetchone()[0]

    closed = db.execute("""
        SELECT COUNT(*), COALESCE(SUM(pnl), 0) FROM positions
        WHERE closed_at LIKE ? AND status = 'closed'
    """, (f"{today}%",)).fetchone()

    consec = _check_consecutive_losses(db)
    dd_pct = _check_drawdown_pct(db)

    return {
        "positions_opened": opened,
        "positions_closed": closed[0],
        "total_pnl": round(closed[1], 2),
        "consecutive_losses": consec,
        "drawdown_pct": round(dd_pct, 1),
        "mode": "LIVE" if HL_TRADING_ENABLED else "PAPER",
        "kill_switched": is_hl_kill_switched(),
    }
