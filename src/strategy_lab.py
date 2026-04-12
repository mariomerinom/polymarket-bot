"""
strategy_lab.py — Multi-strategy shadow testing framework.

Parasitic on production pipeline dispatch: runs lightweight signal functions
on the same candle data already in memory, writes predictions to a single
shared DB, auto-resolves them, and tracks per-strategy WR/P&L.

Never affects production pipelines. All exceptions caught and logged.

Hook point: botsy_engine.py calls strategy_lab_run() after each candle-close
dispatch cycle.
"""

import importlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from strategies.base import StrategyContext, StrategySignal

# ── Paths ────────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent.parent
STRATEGY_LAB_CONFIG = ROOT_DIR / "config" / "strategy_lab.json"
STRATEGY_LAB_DB = ROOT_DIR / "data" / "strategy_lab.db"


# ── Database ─────────────────────────────────────────────────────────────

def _init_db(db: sqlite3.Connection):
    """Create the lab_predictions table if it doesn't exist."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS lab_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT NOT NULL,
            pipeline TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            estimate REAL NOT NULL,
            conviction INTEGER NOT NULL,
            reason TEXT,
            metadata TEXT,
            regime TEXT,
            entry_price REAL,
            predicted_at TEXT NOT NULL,
            resolved_at TEXT,
            outcome INTEGER,
            pnl REAL
        )
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_lab_strategy
        ON lab_predictions(strategy)
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_lab_pending
        ON lab_predictions(outcome, symbol) WHERE outcome IS NULL
    """)
    db.commit()


def _write_prediction(db, strategy_name, pipeline, symbol, signal, regime_label,
                       entry_price, timestamp):
    """Insert a lab prediction into the database."""
    db.execute("""
        INSERT INTO lab_predictions
            (strategy, pipeline, symbol, direction, estimate, conviction,
             reason, metadata, regime, entry_price, predicted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        strategy_name,
        pipeline,
        symbol,
        signal.direction,
        signal.estimate,
        signal.conviction,
        signal.reason,
        json.dumps(signal.metadata) if signal.metadata else None,
        regime_label,
        entry_price,
        timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp),
    ))
    db.commit()


# ── Auto-Resolution ─────────────────────────────────────────────────────

def _auto_resolve(db, next_candle, resolve_time, symbol=None):
    """Resolve pending predictions using the next candle's direction.

    next_candle: dict with 'open' and 'close' keys.
    symbol: if provided, only resolve predictions for this symbol.
            CRITICAL: must be provided to avoid resolving ETH predictions
            with BTC candle data (or vice versa).
    Returns number of predictions resolved.
    """
    if symbol:
        pending = db.execute("""
            SELECT id, direction FROM lab_predictions
            WHERE outcome IS NULL AND symbol = ?
        """, (symbol,)).fetchall()
    else:
        pending = db.execute("""
            SELECT id, direction FROM lab_predictions WHERE outcome IS NULL
        """).fetchall()

    if not pending:
        return 0

    candle_went_up = next_candle["close"] >= next_candle["open"]
    resolved_count = 0

    for row_id, predicted_direction in pending:
        if predicted_direction == "UP":
            outcome = 1 if candle_went_up else 0
        else:
            outcome = 1 if not candle_went_up else 0

        # Simple paper P&L: +$25 win, -$25 loss
        pnl = 25.0 if outcome == 1 else -25.0

        db.execute("""
            UPDATE lab_predictions
            SET outcome = ?, pnl = ?, resolved_at = ?
            WHERE id = ?
        """, (outcome, pnl, resolve_time.isoformat(), row_id))
        resolved_count += 1

    db.commit()
    return resolved_count


# ── Config Loading ───────────────────────────────────────────────────────

def _load_strategies():
    """Load enabled strategies from config/strategy_lab.json.

    Returns dict of {name: {fn, assets, timeframes, ...}}.
    """
    if not STRATEGY_LAB_CONFIG.exists():
        return {}

    config = json.loads(STRATEGY_LAB_CONFIG.read_text())
    strategies = {}

    for name, cfg in config.get("strategies", {}).items():
        if not cfg.get("enabled", True):
            continue

        try:
            mod = importlib.import_module(cfg["module"])
            fn = getattr(mod, cfg["function"])
            strategies[name] = {
                "fn": fn,
                "assets": cfg.get("assets", []),
                "timeframes": cfg.get("timeframes", []),
                "min_sample": cfg.get("min_sample", 200),
            }
        except Exception as e:
            print(f"  [STRATEGY_LAB] Failed to load {name}: {e}")

    return strategies


# ── Dispatch ─────────────────────────────────────────────────────────────

def _dispatch_strategies(db, strategies, ctx):
    """Run all matching strategies and write signals to DB.

    A strategy matches if its assets include ctx.symbol
    and its timeframes include ctx.timeframe.
    """
    for name, strat in strategies.items():
        # Check asset + timeframe match
        if ctx.symbol not in strat["assets"]:
            continue
        if ctx.timeframe not in strat["timeframes"]:
            continue

        try:
            result = strat["fn"](ctx)
            if result is not None and isinstance(result, StrategySignal):
                regime_label = ctx.regime.get("label", "") if ctx.regime else ""
                _write_prediction(
                    db, name, ctx.pipeline, ctx.symbol,
                    result, regime_label, ctx.current_price, ctx.timestamp,
                )
        except Exception as e:
            print(f"  [STRATEGY_LAB] {name} error: {e}")


# ── Context Builder ──────────────────────────────────────────────────────

def _build_context(pipeline, symbol, timeframe, candle_data, indicators):
    """Build a StrategyContext from engine dispatch data."""
    candles = []
    current_price = 0.0
    if candle_data:
        candles = candle_data.get("candles", [])
        current_price = candle_data.get("current_price", 0.0)

    # Compute regime from candles
    regime = None
    if len(candles) >= 10:
        try:
            from predict import compute_regime_from_candles
            regime = compute_regime_from_candles(candles)
        except Exception:
            pass

    # Load orderbook if available
    orderbook = None
    orderbook_path = ROOT_DIR / "data" / "live_orderbook.json"
    if orderbook_path.exists():
        try:
            orderbook = json.loads(orderbook_path.read_text())
        except Exception:
            pass

    return StrategyContext(
        symbol=symbol,
        timeframe=timeframe,
        pipeline=pipeline,
        candles=candles,
        indicators=indicators,
        regime=regime,
        current_price=current_price,
        timestamp=datetime.now(timezone.utc),
        orderbook=orderbook,
    )


# ── Main Entry Point ────────────────────────────────────────────────────

def strategy_lab_run(pipelines, symbol, interval, candle_data, indicators):
    """Run all matching lab strategies for this candle event.

    Called from botsy_engine.py after production pipeline dispatch.
    NEVER raises — all exceptions caught.

    Args:
        pipelines: list of pipeline names dispatched this cycle
        symbol: e.g. "BTCUSDT"
        interval: e.g. "5"
        candle_data: dict with candles, current_price, etc.
        indicators: dict from TAEngine
    """
    try:
        strategies = _load_strategies()
        if not strategies:
            return

        db = sqlite3.connect(str(STRATEGY_LAB_DB))
        try:
            _init_db(db)

            # Auto-resolve pending predictions from previous cycle
            if candle_data and candle_data.get("candles"):
                last_candle = candle_data["candles"][-1]
                resolved = _auto_resolve(db, last_candle, datetime.now(timezone.utc), symbol=symbol)
                if resolved > 0:
                    print(f"  [STRATEGY_LAB] Resolved {resolved} prediction(s)")

            # Build context and dispatch for each pipeline
            for pipeline in (pipelines if pipelines else []):
                ctx = _build_context(pipeline, symbol, interval,
                                     candle_data, indicators)
                _dispatch_strategies(db, strategies, ctx)

        finally:
            db.close()

    except Exception as e:
        print(f"  [STRATEGY_LAB] run error: {e}")
