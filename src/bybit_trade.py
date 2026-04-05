"""
bybit_trade.py — Order execution for Bybit USDT perpetual futures.

Converts momentum predictions with conviction >= 3 into limit orders.
Two modes controlled by BYBIT_TRADING_ENABLED env var:
  - False (default): Log what we WOULD trade, no orders placed.
  - True: Place real limit orders via pybit SDK.

Position lifecycle:
  1. Open on qualifying momentum signal (streak >= 3, non-mean-reverting regime)
  2. Close on: streak break, time ceiling (6 cycles / 30min), or server-side stop-loss
  3. One position at a time. Opposite signal → close then reverse.

Uses limit orders (0.02% maker) not market orders (0.055% taker).
Stop-loss is server-side (Bybit trading-stop API) — executes even if CI is down.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import (
    BYBIT_BET_SIZE, BYBIT_DAILY_LOSS_LIMIT, BYBIT_MAX_HOLD_CYCLES,
    BYBIT_STOP_ATR_MULT, BYBIT_FEE_RATE, BYBIT_MIN_CONVICTION,
    CONSECUTIVE_LOSS_MAX, EDGE_THRESHOLD,
    FILL_PRIORITY_SPREAD, API_TIMEOUT_BYBIT, _env,
)
from bybit_markets import (
    get_open_position, get_open_positions, get_position_by_id,
    open_position, close_position as close_position_db,
    increment_cycles_held,
)

BYBIT_TRADING_ENABLED = _env("BYBIT_TRADING_ENABLED", "false").lower() == "true"
BYBIT_BASE_URL = _env("BYBIT_BASE_URL", "https://api.bybit.com")


# ── Risk gates ───────────────────────────────────────────────────────────────

def should_trade_bybit(prediction_row, db):
    """
    Decide if a prediction should become a live order.

    Returns:
        (should_trade: bool, reason: str)
    """
    conv = prediction_row.get("conviction_score", 0)
    if conv < BYBIT_MIN_CONVICTION:
        return False, f"conviction_too_low ({conv})"

    estimate = prediction_row.get("estimate", 0.5)
    edge = abs(estimate - 0.5)
    if edge < EDGE_THRESHOLD:
        return False, f"edge_too_small ({edge:.3f})"

    # Kill switch
    if is_bybit_kill_switched():
        return False, "kill_switch_active"

    # Daily loss limit
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = db.execute("""
        SELECT COALESCE(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END), 0)
        FROM positions
        WHERE closed_at LIKE ? AND status = 'closed'
    """, (f"{today}%",)).fetchone()
    daily_loss = abs(row[0]) if row else 0

    if daily_loss >= BYBIT_DAILY_LOSS_LIMIT:
        return False, f"daily_loss_limit (${daily_loss:.0f} >= ${BYBIT_DAILY_LOSS_LIMIT:.0f})"

    # Consecutive loss breaker
    consec = _check_consecutive_losses(db)
    if consec >= CONSECUTIVE_LOSS_MAX:
        return False, f"consecutive_loss_breaker ({consec} >= {CONSECUTIVE_LOSS_MAX})"

    return True, "ok"


def _check_consecutive_losses(db):
    """Count current consecutive loss streak from today's closed positions.

    Resets daily at midnight UTC — yesterday's losses don't carry over.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = db.execute("""
        SELECT pnl FROM positions
        WHERE status = 'closed' AND pnl IS NOT NULL
          AND closed_at LIKE ?
        ORDER BY closed_at DESC LIMIT 50
    """, (f"{today}%",)).fetchall()
    streak = 0
    for row in rows:
        if row[0] < 0:
            streak += 1
        else:
            break
    return streak


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


# ── ATR computation ──────────────────────────────────────────────────────────

def compute_atr(candles, period=14):
    """
    Average True Range for stop-loss placement.
    TR = max(high-low, abs(high-prev_close), abs(low-prev_close))
    """
    if len(candles) < 2:
        # Fallback: use range of last candle
        c = candles[-1]
        return c["high"] - c["low"]

    trs = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    # Use last `period` TRs
    trs = trs[-period:]
    return sum(trs) / len(trs) if trs else candles[-1]["high"] - candles[-1]["low"]


# ── Order computation ────────────────────────────────────────────────────────

def compute_bybit_order(prediction_row, mark_price, atr):
    """
    Compute order parameters from a prediction.

    Returns dict with: side, qty, price, stop_loss, symbol, order_type
    Uses limit orders (0.02% maker fee) with fill priority spread.
    """
    estimate = prediction_row["estimate"]
    direction = "UP" if estimate > 0.5 else "DOWN"
    side = "Buy" if direction == "UP" else "Sell"

    qty = BYBIT_BET_SIZE

    # Limit price: mark ± fill priority spread (favor fills, pay maker fee)
    spread_dollars = mark_price * FILL_PRIORITY_SPREAD  # FILL_PRIORITY_SPREAD is ratio
    if side == "Buy":
        price = round(mark_price + spread_dollars, 2)
    else:
        price = round(mark_price - spread_dollars, 2)

    # Stop-loss: entry ± ATR * multiplier
    sl_distance = atr * BYBIT_STOP_ATR_MULT
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
        "symbol": "BTCUSDT",
        "order_type": "Limit",
        "mark_price": mark_price,
        "atr": atr,
    }


# ── Order placement ──────────────────────────────────────────────────────────

def place_bybit_order(db, market_id, prediction_id, order_params, cycle):
    """
    Place a Bybit order. Paper mode logs; live mode uses pybit SDK.

    Also opens a position in the positions table and sets server-side stop-loss.
    """
    now = datetime.now(timezone.utc).isoformat()
    mode = "live" if BYBIT_TRADING_ENABLED else "paper"

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

    bybit_order_id = None

    if BYBIT_TRADING_ENABLED:
        try:
            bybit_order_id = _submit_bybit_order(order_params)
            order_record["status"] = "submitted"
            order_record["order_id"] = bybit_order_id

            # Set server-side stop-loss
            _set_stop_loss(order_params["symbol"], order_params["side"],
                           order_params["stop_loss"])
        except Exception as e:
            print(f"    [bybit] Order failed: {e}")
            order_record["status"] = "failed"
            order_record["reason"] = str(e)
    else:
        order_record["status"] = "paper"
        order_record["price_filled"] = order_params["mark_price"]

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

    # Open position in positions table
    entry_price = order_record.get("price_filled") or order_params["mark_price"]
    open_position(
        db, market_id, order_params["side"], order_params["qty"],
        entry_price, order_params["stop_loss"], bybit_order_id,
    )

    return order_record


def _submit_bybit_order(order_params):
    """Submit order to Bybit via pybit SDK. Returns order_id."""
    from pybit.unified_trading import HTTP

    session = HTTP(
        api_key=os.getenv("BYBIT_API_KEY", ""),
        api_secret=os.getenv("BYBIT_API_SECRET", ""),
        testnet="testnet" in BYBIT_BASE_URL,
    )

    result = session.place_order(
        category="linear",
        symbol=order_params["symbol"],
        side=order_params["side"],
        orderType=order_params["order_type"],
        qty=str(order_params["qty"]),
        price=str(order_params["price"]),
        timeInForce="GTC",
    )

    if result.get("retCode") != 0:
        raise Exception(f"Bybit order error: {result.get('retMsg', 'unknown')}")

    return result.get("result", {}).get("orderId", "")


def _set_stop_loss(symbol, side, stop_loss_price):
    """Set server-side stop-loss via Bybit trading-stop API."""
    from pybit.unified_trading import HTTP

    session = HTTP(
        api_key=os.getenv("BYBIT_API_KEY", ""),
        api_secret=os.getenv("BYBIT_API_SECRET", ""),
        testnet="testnet" in BYBIT_BASE_URL,
    )

    session.set_trading_stop(
        category="linear",
        symbol=symbol,
        stopLoss=str(stop_loss_price),
        positionIdx=0,  # One-way mode
    )


# ── Exit logic ───────────────────────────────────────────────────────────────

def check_exit_conditions(candles, position):
    """
    Check if the open position should be closed.

    Returns:
        (should_exit: bool, reason: str)
    """
    from predict import momentum_signal

    # Time ceiling: max hold duration
    if position["cycles_held"] >= BYBIT_MAX_HOLD_CYCLES:
        return True, "time_ceiling"

    # Streak break: momentum signal reversed
    signal = momentum_signal(candles, min_streak=3)
    if signal["should_trade"]:
        signal_side = "Buy" if signal["direction"] == "UP" else "Sell"
        if signal_side != position["side"]:
            return True, "streak_break"

    return False, "hold"


def sync_position_status(db):
    """
    Sync DB position status with Bybit.

    If Bybit shows no position but DB shows open → stop-loss triggered.
    Queries Bybit execution history for actual close price and PnL.
    """
    pos = get_open_position(db)
    if not pos:
        return

    if not BYBIT_TRADING_ENABLED:
        return  # Paper mode — no sync needed

    try:
        from pybit.unified_trading import HTTP

        session = HTTP(
            api_key=os.getenv("BYBIT_API_KEY", ""),
            api_secret=os.getenv("BYBIT_API_SECRET", ""),
            testnet="testnet" in BYBIT_BASE_URL,
        )

        result = session.get_positions(
            category="linear",
            symbol="BTCUSDT",
        )

        positions = result.get("result", {}).get("list", [])
        has_position = any(
            float(p.get("size", 0)) > 0 for p in positions
        )

        if not has_position:
            # Position was closed (stop-loss triggered or manual)
            # Get execution history for close price
            executions = session.get_executions(
                category="linear",
                symbol="BTCUSDT",
                limit=5,
            )
            exec_list = executions.get("result", {}).get("list", [])

            close_price = pos["entry_price"]  # Fallback
            if exec_list:
                close_price = float(exec_list[0].get("execPrice", close_price))

            pnl = _compute_pnl(pos["side"], pos["size"], pos["entry_price"], close_price)
            close_position_db(db, pos["id"], close_price, pnl, "stop_loss")
            print(f"    [bybit] Stop-loss triggered: PnL=${pnl:.2f}")

    except Exception as e:
        print(f"    [bybit] Position sync error: {e}")


def close_bybit_position(db, position, reason, mark_price):
    """
    Close an open position.

    Places a reduce-only closing order (opposite side), updates positions table.
    """
    close_side = "Sell" if position["side"] == "Buy" else "Buy"

    bybit_order_id = None
    close_price = mark_price

    if BYBIT_TRADING_ENABLED:
        try:
            from pybit.unified_trading import HTTP

            session = HTTP(
                api_key=os.getenv("BYBIT_API_KEY", ""),
                api_secret=os.getenv("BYBIT_API_SECRET", ""),
                testnet="testnet" in BYBIT_BASE_URL,
            )

            result = session.place_order(
                category="linear",
                symbol="BTCUSDT",
                side=close_side,
                orderType="Market",  # Market for immediate close
                qty=str(position["size"]),
                reduceOnly=True,
            )

            if result.get("retCode") == 0:
                bybit_order_id = result.get("result", {}).get("orderId", "")
        except Exception as e:
            print(f"    [bybit] Close order failed: {e}")

    pnl = _compute_pnl(position["side"], position["size"],
                        position["entry_price"], close_price)

    close_position_db(db, position["id"], close_price, pnl, reason, bybit_order_id)

    print(f"    [bybit] Closed {position['side']} @ ${close_price:,.2f} "
          f"(reason={reason}, PnL=${pnl:.2f})")

    return {"pnl": pnl, "reason": reason, "close_price": close_price}


def _compute_pnl(side, size, entry_price, close_price):
    """Compute PnL for a position, net of fees."""
    if side == "Buy":
        raw_pnl = (close_price - entry_price) * size
    else:
        raw_pnl = (entry_price - close_price) * size

    # Subtract fees (round-trip: entry + exit)
    notional = entry_price * size
    fees = notional * BYBIT_FEE_RATE * 2
    return round(raw_pnl - fees, 4)


# ── Main entry point ─────────────────────────────────────────────────────────

def execute_bybit_trades(db, cycle, candles, prediction=None):
    """
    Main trade execution entry point. Called from ci_run_bybit.py.

    Flow:
    1. Sync position status (stop-loss check)
    2. Check exit conditions on ALL open positions
    3. Enter new position if qualifying signal (concurrent positions allowed)
    """
    orders = []
    mark_price = candles[-1]["close"] if candles else None

    # 1. Sync with Bybit (catch stop-loss triggers)
    if BYBIT_TRADING_ENABLED:
        sync_position_status(db)

    # 2. Check exit conditions on ALL open positions
    for pos in get_open_positions(db):
        increment_cycles_held(db, pos["id"])
        pos = get_position_by_id(db, pos["id"])  # Re-fetch after increment

        if pos and mark_price:
            should_exit, reason = check_exit_conditions(candles, pos)
            if should_exit:
                result = close_bybit_position(db, pos, reason, mark_price)
                orders.append({"action": "close", **result})

    # 3. Enter new position if qualifying signal (no single-position gate)
    if prediction and mark_price:
        can_trade, reason = should_trade_bybit(prediction, db)

        if can_trade:
            atr = compute_atr(candles)
            order_params = compute_bybit_order(prediction, mark_price, atr)

            print(f"    [bybit] {order_params['side']} {order_params['qty']} BTC "
                  f"@ ${order_params['price']:,.2f} "
                  f"(SL=${order_params['stop_loss']:,.2f}, ATR=${atr:.0f})")

            order = place_bybit_order(db, prediction["market_id"],
                                      prediction.get("id"), order_params, cycle)
            orders.append({"action": "open", **order})
        else:
            print(f"    [bybit] Skip: {reason}")

    return orders


# ── Kill switch ──────────────────────────────────────────────────────────────

def is_bybit_kill_switched():
    """Check if Bybit trading has been manually killed."""
    kill_file = Path(__file__).parent.parent / "data" / "KILL_SWITCH_BYBIT"
    if kill_file.exists():
        return True
    return os.getenv("KILL_SWITCH_BYBIT", "false").lower() == "true"


# ── Summary ──────────────────────────────────────────────────────────────────

def get_bybit_trading_summary(db):
    """Get a summary of today's Bybit trading activity."""
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
        "mode": "LIVE" if BYBIT_TRADING_ENABLED else "PAPER",
        "kill_switched": is_bybit_kill_switched(),
    }
