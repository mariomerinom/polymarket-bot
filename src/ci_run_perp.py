from config import DEFAULT_CANDLE_LIMIT
from config import SHADOW_CANDLE_LIMIT
"""
ci_run_perp.py — Generic perpetual futures pipeline for any symbol/exchange.

Parameterized version of ci_run_bybit.py / ci_run_hl.py. Handles ETH, SOL,
DOGE (and any future pair) on Bybit and Hyperliquid without copy-pasting.

Each pair+exchange combo is a thin wrapper calling run_perp_pipeline() with
the right config dict. The engine imports these wrappers via the runners dict.
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from perp_markets import (
    init_db_perp, create_synthetic_market, get_db_path,
    get_open_position, get_open_positions, get_position_by_id,
    open_position, close_position as close_position_db,
    increment_cycles_held,
)
from perp_score import auto_resolve_perp
from predict import compute_regime_from_candles, momentum_signal
from score import calculate_brier_scores, print_scorecard
from config import MAX_CONVICTION, EDGE_THRESHOLD, CONSECUTIVE_LOSS_MAX
from pipeline_utils import get_next_cycle
from bybit_trade import compute_atr


# ── Per-pair pipeline configs ───────────────────────────────────────────────

def _make_config(symbol, exchange, config_key, regime_fn, bet_size,
                 daily_loss_limit=50, max_hold_cycles=6, stop_atr_mult=1.5,
                 fee_rate=0.0002, min_conviction=3, min_streak=3,
                 dead_hours=None, funding_interval_hours=8):
    """Build a config dict for a symbol/exchange pair."""
    return {
        "symbol": symbol,
        "exchange": exchange,
        "min_streak": min_streak,
        "dead_hours": dead_hours or set(),
        "config_key": config_key,
        "regime_fn": regime_fn,
        "bet_size": bet_size,
        "daily_loss_limit": daily_loss_limit,
        "max_hold_cycles": max_hold_cycles,
        "stop_atr_mult": stop_atr_mult,
        "fee_rate": fee_rate,
        "min_conviction": min_conviction,
        "funding_interval_hours": funding_interval_hours,
    }


def _get_regime_fn(symbol):
    """Return the right regime function for a symbol."""
    if "ETH" in symbol:
        from predict_eth import compute_regime_eth
        return compute_regime_eth
    return compute_regime_from_candles


# Import config values
from config import (
    PERP_ETH_BET_SIZE, PERP_SOL_BET_SIZE, PERP_DOGE_BET_SIZE,
    BYBIT_FEE_RATE, HL_FEE_RATE,
)

# Bybit configs (0.02% maker fee)
ETH_BYBIT_CONFIG = _make_config(
    "ETHUSDT", "bybit", "eth_bybit_5m", _get_regime_fn("ETHUSDT"),
    bet_size=PERP_ETH_BET_SIZE, fee_rate=BYBIT_FEE_RATE,
    funding_interval_hours=8,
)
SOL_BYBIT_CONFIG = _make_config(
    "SOLUSDT", "bybit", "sol_bybit_5m", _get_regime_fn("SOLUSDT"),
    bet_size=PERP_SOL_BET_SIZE, fee_rate=BYBIT_FEE_RATE,
    funding_interval_hours=8,
)
DOGE_BYBIT_CONFIG = _make_config(
    "DOGEUSDT", "bybit", "doge_bybit_5m", _get_regime_fn("DOGEUSDT"),
    bet_size=PERP_DOGE_BET_SIZE, fee_rate=BYBIT_FEE_RATE,
    funding_interval_hours=8,
)

# Hyperliquid configs (-0.02% maker rebate, 1h funding)
ETH_HL_CONFIG = _make_config(
    "ETHUSDT", "hl", "eth_hl_5m", _get_regime_fn("ETHUSDT"),
    bet_size=PERP_ETH_BET_SIZE, fee_rate=HL_FEE_RATE,
    funding_interval_hours=1,
)
SOL_HL_CONFIG = _make_config(
    "SOLUSDT", "hl", "sol_hl_5m", _get_regime_fn("SOLUSDT"),
    bet_size=PERP_SOL_BET_SIZE, fee_rate=HL_FEE_RATE,
    funding_interval_hours=1,
)
DOGE_HL_CONFIG = _make_config(
    "DOGEUSDT", "hl", "doge_hl_5m", _get_regime_fn("DOGEUSDT"),
    bet_size=PERP_DOGE_BET_SIZE, fee_rate=HL_FEE_RATE,
    funding_interval_hours=1,
)

# All configs for test introspection
ALL_CONFIGS = {
    "eth_bybit": ETH_BYBIT_CONFIG,
    "eth_hl": ETH_HL_CONFIG,
    "sol_bybit": SOL_BYBIT_CONFIG,
    "sol_hl": SOL_HL_CONFIG,
    "doge_bybit": DOGE_BYBIT_CONFIG,
    "doge_hl": DOGE_HL_CONFIG,
}


# ── Conviction scoring ──────────────────────────────────────────────────────

def compute_conviction(signal, regime, consensus=None):
    """Compute conviction score using the same logic as bybit/hl pipelines.

    Returns conviction integer (0-5).
    """
    if not signal["should_trade"]:
        return 0

    direction = signal.get("direction", "")
    regime_label = regime.get("label", "")

    # DOWN+NEUTRAL demotion (port from ci_run_bybit.py)
    if (direction == "DOWN" and "NEUTRAL" in regime_label
            and "HIGH_VOL" not in regime_label):
        conviction = 2  # Logged, not traded
    elif abs(signal.get("streak", 0)) >= 5:
        conviction = 4
    else:
        conviction = 3

    # Perps-vs-spot consensus boost
    consensus_score = consensus.get("score", 0) if consensus else 0
    if consensus_score == 2 and conviction >= 3:
        conviction = min(conviction + 1, MAX_CONVICTION)

    return conviction


# ── PnL computation ─────────────────────────────────────────────────────────

def compute_pnl(side, size, entry_price, close_price, fee_rate,
                funding_cost=0.0):
    """Compute PnL for a position, net of fees and funding."""
    if side == "Buy":
        raw_pnl = (close_price - entry_price) * size
    else:
        raw_pnl = (entry_price - close_price) * size

    notional = entry_price * size
    fees = notional * fee_rate * 2  # Round-trip
    return round(raw_pnl - fees - funding_cost, 4)


def compute_funding_cost(side, size, entry_price, cycles_held,
                         funding_rate, funding_interval_hours=8,
                         cycle_minutes=5):
    """Accrue funding for a perp position, prorated by hold time."""
    if funding_rate is None or funding_rate == 0 or cycles_held <= 0:
        return 0.0
    notional = entry_price * size
    held_hours = cycles_held * cycle_minutes / 60.0
    fraction = held_hours / funding_interval_hours
    charge = notional * funding_rate * fraction
    if side != "Buy":
        charge = -charge
    return round(charge, 6)


# ── Trade execution (generic) ──────────────────────────────────────────────

def execute_perp_trades(db, cycle, candles, prediction, config,
                        funding_rate=0.0, pipeline_name=None):
    """Execute trades for any perp pipeline. Paper-only for now.

    Mirrors execute_bybit_trades / execute_hl_trades logic:
    1. Check exit conditions on open positions
    2. Enter new position if qualifying signal
    """
    orders = []
    mark_price = candles[-1]["close"] if candles else None

    # 1. Check exit conditions on ALL open positions
    for pos in get_open_positions(db):
        increment_cycles_held(db, pos["id"])
        pos = get_position_by_id(db, pos["id"])  # Re-fetch

        if pos and mark_price:
            should_exit, reason = _check_exit(pos, config)
            if should_exit:
                fc = compute_funding_cost(
                    pos["side"], pos["size"], pos["entry_price"],
                    pos.get("cycles_held", 0) or 0, funding_rate,
                    funding_interval_hours=config["funding_interval_hours"],
                )
                pnl = compute_pnl(
                    pos["side"], pos["size"], pos["entry_price"],
                    mark_price, config["fee_rate"], fc,
                )
                close_position_db(db, pos["id"], mark_price, pnl, reason,
                                  funding_cost=fc)
                orders.append({"action": "close", "pnl": pnl,
                               "reason": reason, "close_price": mark_price})
                print(f"    [{pipeline_name}] Closed {pos['side']} "
                      f"@ ${mark_price:,.2f} (reason={reason}, PnL=${pnl:.2f})")

    # 2. Enter new position (max 1 concurrent)
    if get_open_position(db):
        print(f"    [{pipeline_name}] Position already open -- skipping new entry")
        return orders

    if prediction and mark_price:
        can_trade, reason = _should_trade(prediction, db, config, pipeline_name)

        if can_trade:
            atr = compute_atr(candles)
            order_params = _compute_order(prediction, mark_price, atr, config)

            print(f"    [{pipeline_name}] {order_params['side']} "
                  f"{order_params['qty']} {config['symbol'].replace('USDT','')} "
                  f"@ ${order_params['price']:,.2f} "
                  f"(SL=${order_params['stop_loss']:,.2f}, ATR=${atr:.2f})")

            order = _place_order(db, prediction["market_id"],
                                 prediction.get("id"), order_params, cycle,
                                 pipeline_name)
            orders.append({"action": "open", **order})
        else:
            print(f"    [{pipeline_name}] Skip: {reason}")

    return orders


def _check_exit(position, config):
    """Check if position should be closed."""
    if position["cycles_held"] >= config["max_hold_cycles"]:
        return True, "time_ceiling"
    return False, "hold"


def _should_trade(prediction_row, db, config, pipeline_name):
    """Risk gate check."""
    conv = prediction_row.get("conviction_score", 0)
    if conv < config["min_conviction"]:
        return False, f"conviction_too_low ({conv})"

    estimate = prediction_row.get("estimate", 0.5)
    edge = abs(estimate - 0.5)
    if edge < EDGE_THRESHOLD:
        return False, f"edge_too_small ({edge:.3f})"

    from system_state import get_system_state
    state = get_system_state(db, pipeline_name or config["config_key"])
    if state.kill_switch:
        return False, "kill_switch_active"
    if state.daily_loss >= config["daily_loss_limit"]:
        return False, (f"daily_loss_limit (${state.daily_loss:.0f} "
                       f">= ${config['daily_loss_limit']:.0f})")
    if state.consecutive_losses >= CONSECUTIVE_LOSS_MAX:
        return False, (f"consecutive_loss_breaker "
                       f"({state.consecutive_losses} >= {CONSECUTIVE_LOSS_MAX})")

    return True, "ok"


def _compute_order(prediction_row, mark_price, atr, config):
    """Compute order parameters from a prediction."""
    from config import FILL_PRIORITY_SPREAD
    estimate = prediction_row["estimate"]
    direction = "UP" if estimate > 0.5 else "DOWN"
    side = "Buy" if direction == "UP" else "Sell"
    qty = config["bet_size"]

    spread_dollars = mark_price * FILL_PRIORITY_SPREAD
    if side == "Buy":
        price = round(mark_price + spread_dollars, 2)
    else:
        price = round(mark_price - spread_dollars, 2)

    sl_distance = atr * config["stop_atr_mult"]
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
        "symbol": config["symbol"],
        "order_type": "Limit",
        "mark_price": mark_price,
        "atr": atr,
    }


def _place_order(db, market_id, prediction_id, order_params, cycle,
                 pipeline_name):
    """Place a paper order and open a position."""
    now = datetime.now(timezone.utc).isoformat()

    order_record = {
        "market_id": market_id,
        "prediction_id": prediction_id,
        "direction": order_params["direction"],
        "size": order_params["qty"],
        "price_limit": order_params["price"],
        "status": "paper",
        "price_filled": order_params["mark_price"],
        "mode": "paper",
        "placed_at": now,
        "cycle": cycle,
    }

    db.execute("""
        INSERT INTO orders (market_id, prediction_id, direction, size,
                            price_limit, price_filled, status, order_id,
                            mode, reason, placed_at, cycle)
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
    entry_price = order_params["mark_price"]
    open_position(
        db, market_id, order_params["side"], order_params["qty"],
        entry_price, order_params["stop_loss"],
    )

    return order_record


# ── Kill switch ─────────────────────────────────────────────────────────────

def is_perp_kill_switched(pipeline_name):
    """Check kill switch via system_state (single source of truth)."""
    from system_state import _check_kill_switch
    return _check_kill_switch(pipeline_name)


# ── Generic pipeline runner ─────────────────────────────────────────────────

def run_perp_pipeline(symbol, exchange, candle_data, indicators, config,
                      pipeline_name=None):
    """Run a complete perp pipeline cycle for any symbol/exchange.

    Steps:
    1. Init DB
    2. Sync positions
    3. Auto-resolve markets
    4. Compute regime + momentum signal
    5. Apply conviction scoring
    6. Execute trades
    7. Shadow scorer
    8. Score
    """
    if pipeline_name is None:
        pipeline_name = f"{symbol.replace('USDT','').lower()}_{exchange}"

    db_path = get_db_path(symbol, exchange)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = init_db_perp(symbol, exchange)

    # Pipeline control check
    from pipeline_control import load_pipeline_config, is_pipeline_live
    cfg = load_pipeline_config(pipeline_name)
    if cfg["mode"] == "paused":
        print(f"{pipeline_name} pipeline PAUSED: {cfg['notes']}")
        db.close()
        return

    short = symbol.replace("USDT", "")
    mode_label = "LIVE" if is_pipeline_live(pipeline_name) else "PAPER"
    print(f"=== {short} {exchange.upper()} Perps ({mode_label}) ===\n")

    # [1/7] Sync position status
    print("[1/7] Syncing position status...")
    pos = get_open_position(db)
    if pos:
        print(f"  Open position: {pos['side']} {pos['size']} {short} "
              f"@ ${pos['entry_price']:,.2f} (held {pos['cycles_held']} cycles)")
    else:
        print("  No open position")

    # [2/7] Auto-resolve expired synthetic markets
    print("[2/7] Auto-resolving synthetic markets...")
    resolved = auto_resolve_perp(db, symbol, exchange)
    if resolved:
        print(f"  Resolved {resolved} market(s)")

    # [3/7] Fetch candles -> regime -> signal -> synthetic market
    cycle = get_next_cycle(db)
    print(f"[3/7] Predictions -- {pipeline_name} momentum (cycle {cycle})...")

    data = candle_data
    if data is None:
        from bybit_data import fetch_bybit_candles
        data = fetch_bybit_candles(symbol=symbol, interval="5",
                                   limit=DEFAULT_CANDLE_LIMIT)

    if not data:
        print(f"  WARNING: No {short} data available -- skipping cycle")
        db.close()
        return

    candles = data["candles"]
    current_price = data["current_price"]
    consensus = data.get("consensus")
    print(f"  {short}: ${current_price:,.2f} | "
          f"1h: {data.get('1h_change_pct',0):+.3f}% | "
          f"Trend: {data.get('trend','?')}")

    # Fetch mark price for HL (for accurate order placement)
    mark_price = current_price
    if exchange == "hl":
        from hl_data import fetch_hl_mark_price
        coin = symbol.replace("USDT", "")
        hl_mark = fetch_hl_mark_price(coin=coin)
        if hl_mark:
            print(f"  HL mark: ${hl_mark:,.2f} "
                  f"(delta: ${hl_mark - current_price:+.2f})")
            mark_price = hl_mark

    # Create synthetic market
    market_id = create_synthetic_market(db, symbol, exchange, current_price)

    # Compute regime using the right function for this asset
    regime_fn = config["regime_fn"]
    regime = regime_fn(candles)
    print(f"  Regime: {regime['label']} "
          f"(autocorr: {regime['autocorrelation']:+.4f})")

    # Fetch funding rate for logging
    funding_rate = 0.0
    if exchange == "bybit":
        try:
            from bybit_data import fetch_bybit_funding_rate
            fr_data = fetch_bybit_funding_rate(symbol=symbol)
            if isinstance(fr_data, dict):
                funding_rate = fr_data.get("rate", 0.0)
        except Exception:
            pass
    elif exchange == "hl":
        try:
            from hl_data import fetch_hl_funding_rate
            coin = symbol.replace("USDT", "")
            fr_data = fetch_hl_funding_rate(coin=coin)
            if isinstance(fr_data, dict):
                funding_rate = fr_data.get("rate", 0.0)
        except Exception:
            pass

    # Gates
    prediction = None
    current_hour_utc = datetime.now(timezone.utc).hour

    if config["dead_hours"] and current_hour_utc in config["dead_hours"]:
        skip_signal = {
            "estimate": 0.5, "should_trade": False, "confidence": "skip",
            "reason": f"time_gate_dead_hour (UTC {current_hour_utc})",
        }
        _store_prediction(db, market_id, skip_signal, regime, cycle, config,
                          mark_price=mark_price, consensus=consensus,
                          indicators=indicators, candles=candles)
        print(f"  -> SKIP (dead hour: UTC {current_hour_utc})")

    elif "HIGH_VOL" in regime["label"]:
        # Expanded 2026-04-16: gate ALL HIGH_VOL regimes on perps (previously
        # only non-trending). Evidence: eth_bybit HV/TRENDING 25.7% WR (35 bets),
        # sol_bybit 41.2% (34), doge_bybit 38.5% (13). Mirrors eth_highvol_full_gate
        # (#80) shipped for eth_5m spot 2026-04-15. HV/NEUTRAL already gated
        # effectively — no samples in 14d perp data.
        skip_signal = {
            "estimate": 0.5, "should_trade": False, "confidence": "skip",
            "reason": "regime_gate_high_vol",
        }
        _store_prediction(db, market_id, skip_signal, regime, cycle, config,
                          mark_price=mark_price, consensus=consensus,
                          indicators=indicators, candles=candles)
        print(f"  -> SKIP (HIGH_VOL {regime['label']})")

    elif regime["is_mean_reverting"]:
        # VWAP mean-reversion: fire in regimes momentum skips
        # Lab: SOL 55.2% WR (531 bets), DOGE 53.4% (532 bets). Decision #TBD.
        vwap_result = None
        try:
            from strategies.vwap_meanrev import signal as vwap_signal
            from strategies.base import StrategyContext
            vwap_ctx = StrategyContext(
                symbol=config["symbol"], timeframe="5",
                pipeline=pipeline_name, candles=candles,
                indicators=indicators, regime=regime,
                current_price=mark_price,
                timestamp=datetime.now(timezone.utc),
            )
            vwap_result = vwap_signal(vwap_ctx)
        except Exception as e:
            print(f"  VWAP signal error: {e}")

        if vwap_result and vwap_result.conviction >= 3:
            # Convert StrategySignal to momentum-compatible dict
            signal = {
                "estimate": vwap_result.estimate,
                "should_trade": True,
                "confidence": "medium",
                "direction": vwap_result.direction,
                "streak": 0,
                "reason": vwap_result.reason,
            }
            print(f"  Signal: VWAP {vwap_result.direction} "
                  f"(z={vwap_result.metadata.get('zscore', 0):+.2f}, "
                  f"conv={vwap_result.conviction})")
            prediction = _store_prediction(
                db, market_id, signal, regime, cycle, config,
                mark_price=mark_price, consensus=consensus,
                indicators=indicators, candles=candles,
            )
        else:
            skip_signal = {
                "estimate": 0.5, "should_trade": False, "confidence": "skip",
                "reason": "regime_skip_mean_reverting_no_vwap",
            }
            _store_prediction(db, market_id, skip_signal, regime, cycle, config,
                              mark_price=mark_price, consensus=consensus,
                              indicators=indicators, candles=candles)
            z_info = f" (z={vwap_result.metadata.get('zscore', 0):+.2f})" if vwap_result else ""
            print(f"  -> SKIP (mean-reverting, VWAP conv<3{z_info})")

    else:
        signal = momentum_signal(candles, min_streak=config["min_streak"],
                                 config_key=config["config_key"])
        if signal["should_trade"]:
            print(f"  Signal: RIDE {signal['direction']} "
                  f"(streak={signal['streak']}, conf={signal['confidence']})")
        else:
            print(f"  Signal: NONE ({signal['reason']})")

        prediction = _store_prediction(
            db, market_id, signal, regime, cycle, config,
            mark_price=mark_price, consensus=consensus,
            indicators=indicators, candles=candles,
        )

        direction = signal.get("direction", "?")
        est = signal["estimate"]
        conv = prediction["conviction_score"]
        print(f"  -> {direction} @ {est:.0%} (conv={conv})")

    # [4/7] Execute trades
    print(f"[4/7] Trade execution...")

    if is_perp_kill_switched(pipeline_name):
        print("  KILL SWITCH ACTIVE -- skipping trades")
    else:
        orders = execute_perp_trades(db, cycle, candles, prediction, config,
                                     funding_rate=funding_rate,
                                     pipeline_name=pipeline_name)
        if orders:
            for o in orders:
                action = o.get("action", "?")
                if action == "open":
                    print(f"  Opened {o.get('direction', '?')} position")
                elif action == "close":
                    print(f"  Closed position: {o.get('reason', '?')} "
                          f"(PnL=${o.get('pnl', 0):.2f})")
        else:
            print("  No trade action this cycle")

    # [5/7] Shadow conviction scorer
    try:
        from shadow_conviction_scorer import shadow_log_cycle
        if candles:
            shadow_log_cycle(db, cycle, candles, config["config_key"])
    except Exception as e:
        print(f"  [shadow] skipped: {e}")

    # [6/7] Score
    print("[6/7] Scoring...")
    results = calculate_brier_scores(db)
    if results:
        print_scorecard(results)
    else:
        print("  No resolved markets to score yet")

    # [7/7] Trading summary
    _print_summary(db, pipeline_name)

    # [INTEGRITY] Per-cycle checks
    try:
        from pipeline_integrity import run_integrity_checks
        results = run_integrity_checks(db, pipeline=pipeline_name, cycle=cycle,
                                       api_ok=data is not None,
                                       data_fetched=bool(data))
        for r in results:
            if r["status"] != "OK":
                print(f"  [{r['status']}] {r['check_name']}: {r['detail']}")
    except Exception as e:
        print(f"  [INTEGRITY] check failed: {e}")

    db.close()
    print(f"\n{pipeline_name} CI run complete.")


def _store_prediction(db, market_id, signal, regime, cycle, config,
                      mark_price=None, consensus=None, indicators=None,
                      candles=None):
    """Store a prediction in the database."""
    predicted_at = datetime.now(timezone.utc).isoformat()

    estimate = signal["estimate"]
    edge = abs(estimate - 0.5)
    confidence = signal.get("confidence", "low")
    conviction = compute_conviction(signal, regime, consensus)

    short = config["symbol"].replace("USDT", "")
    agent_name = f"momentum_{config['exchange']}_{short.lower()}"

    reasoning_data = {
        "signal": signal,
        "regime": regime,
        "asset": short,
        "venue": config["exchange"],
        "instrument": f"{config['symbol']}_perp",
        "signal_type": "momentum",
        "conviction_tier": conviction,
        "mark_price": mark_price,
    }
    if consensus:
        reasoning_data["consensus"] = consensus
    if indicators:
        try:
            from strategies.base import indicator_snapshot
            class _Ctx:
                pass
            ctx = _Ctx()
            ctx.indicators = indicators
            ctx.regime = regime
            ctx.candles = candles or []
            reasoning_data["indicators"] = indicator_snapshot(ctx)
        except Exception:
            reasoning_data["indicators"] = {
                k: round(v, 4) if isinstance(v, float) else v
                for k, v in indicators.items()
                if k not in ("bbands", "stoch")
            }
    reasoning = json.dumps(reasoning_data)

    db.execute("""
        INSERT INTO predictions
        (market_id, agent, estimate, edge, confidence, reasoning,
         predicted_at, cycle, conviction_score, regime)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        market_id, agent_name, estimate, edge, confidence,
        reasoning, predicted_at, cycle, conviction, regime["label"],
    ))
    db.commit()

    return {
        "id": db.execute("SELECT last_insert_rowid()").fetchone()[0],
        "market_id": market_id,
        "agent": agent_name,
        "estimate": estimate,
        "edge": edge,
        "confidence": confidence,
        "conviction_score": conviction,
        "regime": regime["label"],
    }


def _print_summary(db, pipeline_name):
    """Print today's trading summary."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    opened = db.execute("""
        SELECT COUNT(*) FROM positions WHERE opened_at LIKE ?
    """, (f"{today}%",)).fetchone()[0]

    closed = db.execute("""
        SELECT COUNT(*), COALESCE(SUM(pnl), 0) FROM positions
        WHERE closed_at LIKE ? AND status = 'closed'
    """, (f"{today}%",)).fetchone()

    print(f"\n  Today: {opened} opened, {closed[0]} closed, "
          f"PnL=${closed[1]:.2f} (PAPER)")


# ── Thin wrappers -- engine calls these via runners dict ────────────────────

def main_eth_bybit(candle_data=None, indicators=None):
    run_perp_pipeline("ETHUSDT", "bybit", candle_data, indicators,
                      ETH_BYBIT_CONFIG, pipeline_name="eth_bybit")

def main_eth_hl(candle_data=None, indicators=None):
    run_perp_pipeline("ETHUSDT", "hl", candle_data, indicators,
                      ETH_HL_CONFIG, pipeline_name="eth_hl")

def main_sol_bybit(candle_data=None, indicators=None):
    run_perp_pipeline("SOLUSDT", "bybit", candle_data, indicators,
                      SOL_BYBIT_CONFIG, pipeline_name="sol_bybit")

def main_sol_hl(candle_data=None, indicators=None):
    run_perp_pipeline("SOLUSDT", "hl", candle_data, indicators,
                      SOL_HL_CONFIG, pipeline_name="sol_hl")

def main_doge_bybit(candle_data=None, indicators=None):
    run_perp_pipeline("DOGEUSDT", "bybit", candle_data, indicators,
                      DOGE_BYBIT_CONFIG, pipeline_name="doge_bybit")

def main_doge_hl(candle_data=None, indicators=None):
    run_perp_pipeline("DOGEUSDT", "hl", candle_data, indicators,
                      DOGE_HL_CONFIG, pipeline_name="doge_hl")
