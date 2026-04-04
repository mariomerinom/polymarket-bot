from config import DEFAULT_CANDLE_LIMIT
from config import SHADOW_CANDLE_LIMIT
"""
predict_eth.py — Regime-filtered MOMENTUM predictions for ETH.

PARALLEL PIPELINE — does NOT touch predict.py (BTC momentum).

ETH uses the SAME signal direction as BTC:
- BTC: streak UP → predict UP (ride/momentum). Validated 63% WR.
- ETH: streak UP → predict UP (ride/momentum). Flipped 2026-04-01.

History: contrarian_s3_RF validated at 54.4% WR on 1,601 historical markets,
but live contrarian signal hit 33.3% WR on 54 resolved predictions.
Momentum counterfactual on the same 54 bets: 66.7% WR (exact complement).
Same V3→V4 pattern as BTC. Do NOT revert to contrarian.

Phase 1 validated: 36 momentum predictions at 66.7% WR (threshold 55%).
Medium confidence (streak 3-4) promoted to conv=3 ($25 bets).
High confidence (streak >= 5) stays conv=2 (paper) — 20% WR on 5 bets.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import ETH_VOL_LOW, ETH_VOL_HIGH, PRICE_GATE_UPPER, PRICE_GATE_LOWER, EXTREME_ESTIMATE_UPPER, EXTREME_ESTIMATE_LOWER, DB_BUSY_TIMEOUT_MS

# Import regime computation from BTC predict
from predict import compute_regime_from_candles as _btc_regime

# Import data-driven dead hours from predict.py (shared logic)
from predict import compute_dead_hours


def compute_regime_eth(candles, autocorr_threshold=-0.15):
    """ETH-specific regime with recalibrated volatility thresholds."""
    regime = _btc_regime(candles, autocorr_threshold=autocorr_threshold)
    vol = regime["volatility"]
    if vol < ETH_VOL_LOW:
        vol_label = "LOW_VOL"
    elif vol < ETH_VOL_HIGH:
        vol_label = "MEDIUM_VOL"
    else:
        vol_label = "HIGH_VOL"
    # Preserve trend label from BTC function, only override vol
    trend_label = regime["label"].split(" / ")[-1] if " / " in regime["label"] else "NEUTRAL"
    regime["label"] = f"{vol_label} / {trend_label}"
    return regime

DB_PATH_ETH = Path(__file__).parent.parent / "data" / "predictions_eth.db"


def momentum_signal_eth(candles, min_streak=3):
    """ETH momentum signal — delegates to shared momentum_signal with ETH config."""
    from predict import momentum_signal
    return momentum_signal(candles, min_streak=min_streak, config_key="eth_5m")


def ensure_schema(db):
    """Create tables if they don't exist."""
    db.execute("PRAGMA journal_mode=WAL")
    db.execute(f"PRAGMA busy_timeout={DB_BUSY_TIMEOUT_MS}")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            id TEXT PRIMARY KEY,
            question TEXT,
            category TEXT,
            end_date TEXT,
            volume REAL,
            price_yes REAL,
            price_no REAL,
            fetched_at TEXT,
            resolved INTEGER DEFAULT 0,
            outcome INTEGER DEFAULT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT,
            agent TEXT,
            estimate REAL,
            edge REAL,
            confidence TEXT,
            reasoning TEXT,
            predicted_at TEXT,
            cycle INTEGER,
            conviction_score INTEGER,
            regime TEXT,
            FOREIGN KEY (market_id) REFERENCES markets(id)
        )
    """)
    db.commit()


def store_prediction_eth(db, market_id, signal, regime, cycle, predicted_at=None,
                         mkt_price=None, consensus=None, liquidity=None):
    """Store an ETH prediction in the database.

    Conviction scoring calibrated from 36 momentum_eth predictions:
    - medium confidence (streak 3-4) → conv=3 ($25 bets)
    - high confidence (streak >= 5) → conv=2 (paper — insufficient data)
    """
    if predicted_at is None:
        predicted_at = datetime.now(timezone.utc).isoformat()

    estimate = signal["estimate"]
    edge = abs(estimate - 0.5)
    confidence = signal.get("confidence", "low")

    # ETH conviction scoring — calibrated from 36 momentum_eth predictions
    # medium (streak 3-4): 74.2% WR on 31 bets → fire
    # high (streak >= 5): 20% WR on 5 bets → keep paper until more data
    if signal["should_trade"] and confidence == "medium":
        conviction = 3  # $25 flat bet
    elif signal["should_trade"] and confidence == "high":
        conviction = 2  # Paper only — long streaks reverse on ETH
    elif signal["should_trade"]:
        conviction = 2
    else:
        conviction = 0

    reasoning_data = {
        "signal": signal,
        "regime": regime,
        "paper_trading": conviction < 3,
        "asset": "ETH",
        "signal_type": "momentum",
        "would_have_bet": signal.get("should_trade", False) and confidence in ("medium", "high"),
        "conviction_tier": conviction,
        "mkt_price": mkt_price,
    }
    if consensus:
        reasoning_data["consensus"] = consensus
    if liquidity:
        reasoning_data["liquidity"] = liquidity
    reasoning = json.dumps(reasoning_data)

    # Store as "momentum_eth" agent (distinct from BTC's "momentum_rule")
    db.execute("""
        INSERT INTO predictions
        (market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle, conviction_score, regime)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        market_id, "momentum_eth", estimate, edge, confidence,
        reasoning, predicted_at, cycle, conviction, regime["label"],
    ))
    db.commit()


def run_predictions_eth(cycle=1, market_limit=1, eth_data=None, db_path=None,
                        min_streak=3, autocorr_threshold=-0.15):
    """
    Main ETH prediction loop.
    Fetch candles → compute regime → apply MOMENTUM rule → store.
    No API calls. $0 cost.
    """
    from eth_data import fetch_eth_candles

    db = sqlite3.connect(db_path or DB_PATH_ETH)
    ensure_schema(db)

    # Fetch ETH candles
    if eth_data is None:
        eth_data = fetch_eth_candles(limit=DEFAULT_CANDLE_LIMIT)

    if eth_data:
        candles = eth_data["candles"]
        consensus = eth_data.get("consensus")
        print(f"  ETH: ${eth_data['current_price']:,.2f} | 1h: {eth_data['1h_change_pct']:+.3f}%")
    else:
        print("  WARNING: No ETH data available — skipping predictions")
        db.close()
        return

    # Data-driven dead hours from ETH data
    dead_hours, hour_stats = compute_dead_hours(db_path or DB_PATH_ETH)
    if hour_stats:
        dead_list = sorted(dead_hours) if dead_hours else ["none"]
        print(f"  Dead hours (auto): {dead_list}")

    # Compute regime with ETH-calibrated volatility thresholds (Decision #16)
    regime = compute_regime_eth(candles, autocorr_threshold=autocorr_threshold)
    print(f"  Regime: {regime['label']} (autocorr: {regime['autocorrelation']:+.4f})")

    if regime["is_mean_reverting"]:
        print(f"  SKIP: Mean-reverting regime detected — no trades")

    # Compute MOMENTUM signal (same direction as BTC)
    signal = momentum_signal_eth(candles, min_streak=min_streak)
    if signal["should_trade"]:
        print(f"  Signal: RIDE {signal['direction']} (streak={signal['streak']}, conf={signal['confidence']})")
    else:
        print(f"  Signal: NONE ({signal['reason']})")

    # Get markets to predict
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor = db.execute("""
        SELECT id, question, category, end_date, volume, price_yes
        FROM markets WHERE resolved = 0 AND end_date > ?
        AND id NOT IN (SELECT DISTINCT market_id FROM predictions)
        ORDER BY end_date ASC LIMIT ?
    """, (now_iso, market_limit))
    markets = [dict(zip(["id", "question", "category", "end_date", "volume", "price_yes"], row))
               for row in cursor.fetchall()]

    if not markets:
        print("  No unresolved ETH markets found.")
        db.close()
        return

    print(f"  Markets: {len(markets)}")

    for market in markets:
        print(f"\n  Market: {market['question'][:60]}...")
        mkt_price = market['price_yes']
        print(f"  Mkt price: {mkt_price:.0%}")

        # Dead hours gate — data-driven from ETH predictions
        current_hour_utc = datetime.now(timezone.utc).hour
        if current_hour_utc in dead_hours:
            # Extreme-estimate override: estimates >0.65/<0.35 win at 80%+ WR regardless of gate
            if signal["should_trade"] and (signal["estimate"] > EXTREME_ESTIMATE_UPPER or signal["estimate"] < EXTREME_ESTIMATE_LOWER):
                shadow_signal = dict(signal, confidence="medium", reason=f"shadow_extreme_dead_hour (UTC {current_hour_utc})")
                store_prediction_eth(db, market["id"], shadow_signal, regime, cycle, mkt_price=mkt_price)
                db.execute("""
                    UPDATE predictions SET conviction_score = 2
                    WHERE market_id = ? AND cycle = ? AND conviction_score >= 3
                """, (market["id"], cycle))
                db.commit()
                direction = "UP" if signal["estimate"] > 0.5 else "DOWN"
                print(f"    → DEAD HOUR SHADOW: {direction} @ {signal['estimate']:.3f} (extreme estimate, tracked at conv=2)")
            else:
                skip_signal = {
                    "estimate": mkt_price,
                    "should_trade": False,
                    "confidence": "skip",
                    "reason": f"time_gate_dead_hour (UTC {current_hour_utc})",
                }
                store_prediction_eth(db, market["id"], skip_signal, regime, cycle)
                print(f"    → SKIP (dead hour: UTC {current_hour_utc})")
            continue

        # Price gate: skip extreme prices
        if mkt_price > PRICE_GATE_UPPER or mkt_price < PRICE_GATE_LOWER:
            # Extreme-estimate override: estimates >0.65/<0.35 win at 80%+ WR regardless of gate
            if signal["should_trade"] and (signal["estimate"] > EXTREME_ESTIMATE_UPPER or signal["estimate"] < EXTREME_ESTIMATE_LOWER):
                shadow_signal = dict(signal, confidence="medium", reason=f"shadow_extreme_price_gate ({mkt_price:.0%})")
                store_prediction_eth(db, market["id"], shadow_signal, regime, cycle, mkt_price=mkt_price)
                db.execute("""
                    UPDATE predictions SET conviction_score = 2
                    WHERE market_id = ? AND cycle = ? AND conviction_score >= 3
                """, (market["id"], cycle))
                db.commit()
                direction = "UP" if signal["estimate"] > 0.5 else "DOWN"
                print(f"    → PRICE GATE SHADOW: {direction} @ {signal['estimate']:.3f} (extreme estimate, tracked at conv=2)")
            else:
                skip_signal = {
                    "estimate": mkt_price,
                    "should_trade": False,
                    "confidence": "skip",
                    "reason": f"price_gate_extreme ({mkt_price:.0%})",
                }
                store_prediction_eth(db, market["id"], skip_signal, regime, cycle)
                print(f"    → SKIP (price gate: {mkt_price:.0%})")
            continue

        # Regime gate — MR shadow mode for extreme estimates
        if regime["is_mean_reverting"]:
            # Extreme estimates (>0.65/<0.35) win at 80%+ WR regardless of regime (Phase 1 analysis).
            # Track at conv=2 for forward validation. Coin-flip zone skipped as before.
            if signal["should_trade"] and (signal["estimate"] > EXTREME_ESTIMATE_UPPER or signal["estimate"] < EXTREME_ESTIMATE_LOWER):
                mr_signal = dict(signal, confidence="medium", reason="mr_shadow_extreme_estimate")
                store_prediction_eth(db, market["id"], mr_signal, regime, cycle, mkt_price=mkt_price)
                # Force conv=2 (shadow) — store_prediction_eth sets conv=3 for medium+should_trade
                db.execute("""
                    UPDATE predictions SET conviction_score = 2
                    WHERE market_id = ? AND cycle = ? AND conviction_score >= 3
                    AND regime LIKE '%MEAN_REVERTING%'
                """, (market["id"], cycle))
                db.commit()
                direction = "UP" if signal["estimate"] > 0.5 else "DOWN"
                print(f"    → MR SHADOW: {direction} @ {signal['estimate']:.3f} (extreme estimate, tracked at conv=2)")
            else:
                skip_signal = {
                    "estimate": mkt_price,
                    "should_trade": False,
                    "confidence": "skip",
                    "reason": "regime_skip_mean_reverting",
                }
                store_prediction_eth(db, market["id"], skip_signal, regime, cycle)
                print(f"    → SKIP (mean-reverting regime)")
            continue

        # Apply momentum signal
        if signal["should_trade"]:
            # CLOB depth query (read-only, never blocks)
            liquidity = None
            try:
                from clob_depth import get_liquidity_summary, format_liquidity_log
                clob_tokens = _get_clob_tokens(market["id"])
                if clob_tokens:
                    direction_for_clob = "UP" if signal["estimate"] > 0.5 else "DOWN"
                    liquidity = get_liquidity_summary(
                        clob_tokens["yes"], clob_tokens["no"], direction_for_clob
                    )
                    print(f"    {format_liquidity_log(liquidity)}")
            except Exception as e:
                print(f"    [CLOB] skipped: {e}")

            store_prediction_eth(db, market["id"], signal, regime, cycle,
                                 mkt_price=mkt_price, consensus=consensus,
                                 liquidity=liquidity)
            direction = "UP" if signal["estimate"] > 0.5 else "DOWN"
            conv = 3 if signal.get("confidence") == "medium" else 2
            conv_label = f"conv={conv}" + (" LIVE" if conv >= 3 else " paper")
            print(f"    → RIDE {direction} @ {signal['estimate']:.0%} ({signal['confidence']}, {conv_label})")
        else:
            no_signal = {
                "estimate": mkt_price,
                "should_trade": False,
                "confidence": "skip",
                "reason": signal.get("reason", "no_signal"),
            }
            store_prediction_eth(db, market["id"], no_signal, regime, cycle)
            print(f"    → SKIP ({signal.get('reason', 'no_signal')})")

    db.close()
    print(f"\nDone. ETH predictions stored in {db_path or DB_PATH_ETH}")


def _get_clob_tokens(market_id):
    """Wrapper — delegates to shared clob_depth.get_clob_tokens."""
    try:
        from clob_depth import get_clob_tokens
        return get_clob_tokens(market_id)
    except ImportError:
        return None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", type=int, default=1, help="Cycle number")
    parser.add_argument("--markets", type=int, default=5, help="Max markets to predict")
    args = parser.parse_args()
    run_predictions_eth(cycle=args.cycle, market_limit=args.markets)
