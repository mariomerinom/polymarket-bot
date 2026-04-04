"""
predict.py — Regime-filtered momentum predictions.

V4: No LLM agents. Pure computation from BTC candle data.
- Fetch 20 candles from Kraken/Coinbase
- Compute regime (volatility + autocorrelation)
- If mean-reverting → skip
- If streak >= 3 → RIDE the streak (momentum)
- Cost: $0/day
"""

import json
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
import statistics

from config import (
    FALLBACK_DEAD_HOURS, DEAD_HOUR_LOOKBACK_DAYS, DEAD_HOUR_MIN_BETS,
    DEAD_HOUR_MAX_WR, BTC_VOL_LOW, BTC_VOL_HIGH, AUTOCORR_TRENDING,
    PRICE_GATE_UPPER, PRICE_GATE_LOWER, PRICE_SWEET_SPOT_LOW,
    PRICE_SWEET_SPOT_HIGH, CONFIDENCE_HIGH_STREAK, MAX_CONVICTION,
    AUTOCORR_MEAN_REVERTING_5M, AUTOCORR_MEAN_REVERTING_15M,
    SHADOW_CONFIGS, ESTIMATE_FALLBACK_UP, ESTIMATE_FALLBACK_DOWN,
    DEFAULT_CANDLE_LIMIT, CONTEXT_LOOKBACK_MINUTES,
    EXTREME_ESTIMATE_UPPER, EXTREME_ESTIMATE_LOWER,
)

# Optional dependencies handled gracefully
try:
    from shadow_conviction_scorer import strength_signal
except ImportError:
    strength_signal = None

try:
    from clob_depth import get_liquidity_summary, format_liquidity_log, get_clob_tokens
except ImportError:
    get_liquidity_summary = None
    format_liquidity_log = lambda x: ""
    get_clob_tokens = None

try:
    from btc_data import fetch_btc_candles
except ImportError:
    fetch_btc_candles = None


# Setup formal logging framework (replaces print statements)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("predict")

DB_PATH = Path(__file__).parent.parent / "data" / "predictions.db"


def initialize_schema(db):
    """Ensure required tables and columns exist using explicitly safe PRAGMA checks."""
    try:
        columns = [row[1] for row in db.execute("PRAGMA table_info(predictions)").fetchall()]
        if "regime" not in columns:
            db.execute("ALTER TABLE predictions ADD COLUMN regime TEXT")
        if "conviction_score" not in columns:
            db.execute("ALTER TABLE predictions ADD COLUMN conviction_score INTEGER")
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to initialize schema: {e}")


def compute_dead_hours(db_path=None, lookback_days=DEAD_HOUR_LOOKBACK_DAYS,
                       min_bets=DEAD_HOUR_MIN_BETS, max_wr=DEAD_HOUR_MAX_WR):
    """Data-driven dead hour gate: query resolved predictions and return hours."""
    try:
        # Isolated connection to query dead hours
        with sqlite3.connect(db_path or DB_PATH) as db:
            rows = db.execute("""
                SELECT
                    CAST(strftime('%H', p.predicted_at) AS INTEGER) as hour_utc,
                    COUNT(*) as n,
                    SUM(CASE
                        WHEN (p.estimate >= 0.5 AND m.outcome = 1)
                          OR (p.estimate < 0.5 AND m.outcome = 0)
                        THEN 1 ELSE 0
                    END) as wins
                FROM predictions p
                JOIN markets m ON p.market_id = m.id
                WHERE m.resolved = 1
                  AND p.conviction_score >= 3
                  AND p.predicted_at >= datetime('now', ?)
                GROUP BY hour_utc
                ORDER BY hour_utc
            """, (f"-{lookback_days} days",)).fetchall()
    except Exception as e:
        logger.warning(f"DB query failed ({e}), using fallback {FALLBACK_DEAD_HOURS}")
        return FALLBACK_DEAD_HOURS, []

    if not rows:
        return FALLBACK_DEAD_HOURS, []

    dead = set(FALLBACK_DEAD_HOURS)
    stats = []
    for hour_utc, n, wins in rows:
        wr = wins / n if n > 0 else 0
        stats.append({"hour": hour_utc, "bets": n, "wins": wins, "wr": wr})
        if n >= min_bets and wr < max_wr:
            dead.add(hour_utc)
        elif n >= min_bets and wr >= max_wr and hour_utc in dead:
            dead.discard(hour_utc)

    return dead, stats


def _compute_autocorrelation(returns):
    """Pure mathematical function to compute lag-1 autocorrelation for a series."""
    n = len(returns)
    if n < 2:
        return 0.0
    mean_r = sum(returns) / n
    var = sum((r - mean_r) ** 2 for r in returns) / n
    if var == 0:
        return 0.0
    cov = sum((returns[i] - mean_r) * (returns[i-1] - mean_r) for i in range(1, n)) / (n - 1)
    return cov / var


def compute_regime_from_candles(candles, autocorr_threshold=AUTOCORR_MEAN_REVERTING_5M):
    """Compute regime indicators from candle list."""
    closes = [c["close"] for c in candles]
    if len(closes) < 3:
        return {
            "autocorrelation": 0.0, 
            "volatility": 0.0, 
            "label": "UNKNOWN / NEUTRAL", 
            "is_mean_reverting": False
        }

    returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
    
    try:
        volatility = statistics.stdev(returns) * 100
    except statistics.StatisticsError:
        volatility = 0.0

    autocorr = _compute_autocorrelation(returns)

    vol_label = "LOW_VOL" if volatility < BTC_VOL_LOW else ("MEDIUM_VOL" if volatility < BTC_VOL_HIGH else "HIGH_VOL")
    trend_label = "TRENDING" if autocorr > AUTOCORR_TRENDING else ("MEAN_REVERTING" if autocorr < autocorr_threshold else "NEUTRAL")

    return {
        "autocorrelation": round(autocorr, 4),
        "volatility": round(volatility, 4),
        "label": f"{vol_label} / {trend_label}",
        "is_mean_reverting": autocorr < autocorr_threshold,
    }


def momentum_signal(candles, min_streak=None, config_key="btc_5m"):
    """Asset-agnostic momentum signal: ride streaks."""
    if len(candles) < 5:
        return {"estimate": 0.5, "should_trade": False, "reason": "insufficient_data"}

    # Dynamically pull streak logic from config instead of old hardcoded args
    if min_streak is None:
        min_streak = SHADOW_CONFIGS.get(config_key, {}).get("min_streak", 3)

    last_dir = "UP" if candles[-1]["close"] >= candles[-1]["open"] else "DOWN"
    streak = 1
    for i in range(len(candles) - 2, -1, -1):
        if ("UP" if candles[i]["close"] >= candles[i]["open"] else "DOWN") == last_dir:
            streak += 1
        else:
            break

    signed_streak = streak if last_dir == "UP" else -streak

    if abs(signed_streak) < min_streak:
        return {
            "estimate": 0.5, "should_trade": False,
            "reason": f"streak_too_short ({signed_streak})",
            "streak": signed_streak,
        }

    direction = "UP" if signed_streak >= min_streak else "DOWN"

    try:
        if strength_signal is not None:
            shadow = strength_signal(candles, signed_streak, config_key)
            estimate = shadow["estimate"] if shadow else (ESTIMATE_FALLBACK_UP if direction == "UP" else ESTIMATE_FALLBACK_DOWN)
        else:
            estimate = ESTIMATE_FALLBACK_UP if direction == "UP" else ESTIMATE_FALLBACK_DOWN
    except Exception:
        estimate = ESTIMATE_FALLBACK_UP if direction == "UP" else ESTIMATE_FALLBACK_DOWN

    confidence = "high" if abs(signed_streak) >= CONFIDENCE_HIGH_STREAK else "medium"

    return {
        "estimate": estimate,
        "should_trade": True,
        "direction": direction,
        "confidence": confidence,
        "streak": signed_streak,
        "reason": f"ride_streak_{direction}",
    }


def _get_clob_tokens_safe(market_id):
    """Wrapper that returns tokens or None without blowing up."""
    if get_clob_tokens:
        return get_clob_tokens(market_id)
    return None


def store_prediction(db, market_id, signal, regime, cycle, predicted_at=None,
                     mkt_price=None, loose_mode=False, sibling_context=None,
                     consensus=None, liquidity=None):
    """Store a prediction in the database."""
    if predicted_at is None:
        predicted_at = datetime.now(timezone.utc).isoformat()

    estimate = signal["estimate"]
    edge = abs(estimate - 0.5)
    confidence = signal.get("confidence", "low")

    if signal["should_trade"] and confidence in ("medium", "high"):
        direction = signal.get("direction", "")
        regime_label = regime.get("label", "") if regime else ""

        if not loose_mode and direction == "DOWN" and "NEUTRAL" in regime_label and "HIGH_VOL" not in regime_label:
            conviction = 2
        elif direction == "UP" and mkt_price is not None and PRICE_SWEET_SPOT_LOW <= mkt_price <= PRICE_SWEET_SPOT_HIGH:
            conviction = 4
        else:
            conviction = 3

        consensus_score = consensus.get("score", 0) if consensus else 0
        if consensus_score == 2 and conviction >= 3:
            conviction = min(conviction + 1, MAX_CONVICTION)
    elif signal["should_trade"]:
        conviction = 2
    else:
        conviction = 0

    reasoning_data = {
        "signal": signal,
        "regime": regime,
        "would_have_bet": signal.get("should_trade", False) and confidence in ("medium", "high"),
        "conviction_tier": conviction,
        "mkt_price": mkt_price,
    }
    if sibling_context: reasoning_data["sibling_5m"] = sibling_context
    if consensus: reasoning_data["consensus"] = consensus
    if liquidity: reasoning_data["liquidity"] = liquidity
    reasoning = json.dumps(reasoning_data)

    db.execute("""
        INSERT INTO predictions
        (market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle, conviction_score, regime)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        market_id, "momentum_rule", estimate, edge, confidence,
        reasoning, predicted_at, cycle, conviction, regime["label"] if regime else "UNKNOWN",
    ))
    db.commit()


def get_5m_context(lookback_minutes=CONTEXT_LOOKBACK_MINUTES):
    """Query the 5m DB for recent signal activity."""
    if not DB_PATH.exists():
        return None

    try:
        with sqlite3.connect(DB_PATH) as db5:
            rows = db5.execute("""
                SELECT estimate, conviction_score
                FROM predictions
                WHERE conviction_score >= 3
                  AND predicted_at >= datetime('now', ?)
                ORDER BY predicted_at DESC
            """, (f"-{lookback_minutes} minutes",)).fetchall()
    except Exception:
        return None

    if not rows:
        return {"bets": 0, "direction": None, "streak": 0, "message": "no recent 5m bets"}

    up = sum(1 for r in rows if r[0] >= 0.5)
    down = len(rows) - up

    streak_dir = "UP" if rows[0][0] >= 0.5 else "DOWN"
    streak = 1
    for r in rows[1:]:
        if ("UP" if r[0] >= 0.5 else "DOWN") == streak_dir: streak += 1
        else: break

    majority = "UP" if up > down else ("DOWN" if down > up else "SPLIT")

    return {
        "bets": len(rows),
        "up": up,
        "down": down,
        "majority": majority,
        "streak_direction": streak_dir,
        "streak_length": streak,
        "direction": streak_dir if streak >= 2 else majority,
        "message": f"5m: {len(rows)} bets in last {lookback_minutes}min, {up}UP/{down}DN, streak={streak_dir}×{streak}",
    }


# Standalone pure gate logic
def is_dead_hour(current_hour_utc, dead_hours):
    return current_hour_utc in dead_hours

def is_price_extreme(mkt_price):
    return mkt_price > PRICE_GATE_UPPER or mkt_price < PRICE_GATE_LOWER


def run_predictions(cycle=1, market_limit=5, btc_data=None, db_path=None,
                    min_streak=None, autocorr_threshold=AUTOCORR_MEAN_REVERTING_5M, loose_mode=False):
    """Main prediction loop setup with database context manager."""
    db_file = db_path or DB_PATH
    
    with sqlite3.connect(db_file) as db:
        initialize_schema(db)

        if not loose_mode:
            dead_hours, hour_stats = compute_dead_hours(db_file)
            if hour_stats:
                dead_list = sorted(dead_hours) if dead_hours else ["none"]
                logger.info(f"Dead hours (auto): {dead_list}")
                for s in hour_stats:
                    if s["bets"] >= 10:
                        flag = " <-- DEAD" if s["hour"] in dead_hours else ""
                        # Adjust to logger.info so it is visible in dry-run
                        logger.info(f"  UTC {s['hour']:2d}: {s['bets']:3d} bets, {s['wr']:.0%} WR{flag}")
        else:
            dead_hours = set()

        if btc_data is None:
            if fetch_btc_candles:
                btc_data = fetch_btc_candles(limit=DEFAULT_CANDLE_LIMIT)
            else:
                logger.error("No BTC data provider available (fetch_btc_candles failed to import)")
                return

        if btc_data:
            candles = btc_data["candles"]
            consensus = btc_data.get("consensus")
            logger.info(f"BTC: ${btc_data['current_price']:,.0f} | 1h: {btc_data.get('1h_change_pct',0):+.3f}%")
            if consensus and consensus.get("sources", 0) >= 2:
                k = consensus.get("streak_kraken", {})
                c = consensus.get("streak_coinbase", {})
                score = consensus.get("score", 0)
                label = {2: "STRONG", 1: "WEAK", -1: "DISAGREE"}.get(score, "?")
                logger.info(f"Consensus: {label} (score={score}) | Kraken: {k.get('direction','?')}x{k.get('length',0)} | Coinbase: {c.get('direction','?')}x{c.get('length',0)}")
        else:
            logger.warning("No BTC data available — skipping predictions")
            return

        regime = compute_regime_from_candles(candles, autocorr_threshold=autocorr_threshold)
        logger.info(f"Regime: {regime['label']} (autocorr: {regime['autocorrelation']:+.4f})")

        if regime["is_mean_reverting"]:
            logger.info("SKIP: Mean-reverting regime detected — no trades")

        sibling_context = None
        if loose_mode:
            sibling_context = get_5m_context(lookback_minutes=CONTEXT_LOOKBACK_MINUTES)
            if sibling_context and sibling_context["bets"] > 0:
                logger.info(f"5m sibling: {sibling_context['message']}")

        signal = momentum_signal(candles, min_streak=min_streak)
        if signal["should_trade"]:
            logger.info(f"Signal: RIDE {signal['direction']} (streak={signal['streak']}, conf={signal['confidence']})")
        else:
            logger.info(f"Signal: NONE ({signal['reason']})")

        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = db.execute("""
            SELECT id, question, category, end_date, volume, price_yes
            FROM markets WHERE resolved = 0 AND end_date > ?
            AND id NOT IN (SELECT DISTINCT market_id FROM predictions)
            ORDER BY end_date ASC LIMIT ?
        """, (now_iso, market_limit))
        markets = [dict(zip(["id", "question", "category", "end_date", "volume", "price_yes"], row)) for row in cursor.fetchall()]

        if not markets:
            logger.info("No unresolved markets found.")
            return

        logger.info(f"Markets: {len(markets)}")

        for market in markets:
            logger.info(f"\nMarket: {market['question'][:60]}...")
            mkt_price = market['price_yes']
            logger.info(f"Mkt price: {mkt_price:.0%}")

            current_hour_utc = datetime.now(timezone.utc).hour
            if is_dead_hour(current_hour_utc, dead_hours):
                # Extreme-estimate override: estimates >0.65/<0.35 win at 80%+ WR regardless of gate
                if signal["should_trade"] and (signal["estimate"] > EXTREME_ESTIMATE_UPPER or signal["estimate"] < EXTREME_ESTIMATE_LOWER):
                    shadow_signal = dict(signal, confidence="medium", reason=f"shadow_extreme_dead_hour (UTC {current_hour_utc})")
                    store_prediction(db, market["id"], shadow_signal, regime, cycle, mkt_price=mkt_price)
                    db.execute("""
                        UPDATE predictions SET conviction_score = 2
                        WHERE market_id = ? AND cycle = ? AND conviction_score >= 3
                    """, (market["id"], cycle))
                    db.commit()
                    logger.info(f"  -> DEAD HOUR SHADOW: {signal['direction']} @ {signal['estimate']:.3f} (extreme estimate, tracked at conv=2)")
                else:
                    logger.info(f"  -> SKIP (dead hour: UTC {current_hour_utc})")
                    store_prediction(db, market["id"], {"estimate": mkt_price, "should_trade": False, "confidence": "skip", "reason": f"time_gate_dead_hour (UTC {current_hour_utc})"}, regime, cycle)
                continue

            if is_price_extreme(mkt_price):
                # Extreme-estimate override: estimates >0.65/<0.35 win at 80%+ WR regardless of gate
                if signal["should_trade"] and (signal["estimate"] > EXTREME_ESTIMATE_UPPER or signal["estimate"] < EXTREME_ESTIMATE_LOWER):
                    shadow_signal = dict(signal, confidence="medium", reason=f"shadow_extreme_price_gate ({mkt_price:.0%})")
                    store_prediction(db, market["id"], shadow_signal, regime, cycle, mkt_price=mkt_price)
                    db.execute("""
                        UPDATE predictions SET conviction_score = 2
                        WHERE market_id = ? AND cycle = ? AND conviction_score >= 3
                    """, (market["id"], cycle))
                    db.commit()
                    logger.info(f"  -> PRICE GATE SHADOW: {signal['direction']} @ {signal['estimate']:.3f} (extreme estimate, tracked at conv=2)")
                else:
                    logger.info(f"  -> SKIP (price gate: {mkt_price:.0%})")
                    store_prediction(db, market["id"], {"estimate": mkt_price, "should_trade": False, "confidence": "skip", "reason": f"price_gate_extreme ({mkt_price:.0%})"}, regime, cycle)
                continue

            if regime["is_mean_reverting"]:
                # Shadow mode: extreme estimates in MR have 82.5% WR on 303 bets (Phase 1 analysis).
                # Track them at conv=2 for forward validation. Coin-flip zone (0.35-0.65) is 46% WR — skip.
                if signal["should_trade"] and (signal["estimate"] > EXTREME_ESTIMATE_UPPER or signal["estimate"] < EXTREME_ESTIMATE_LOWER):
                    mr_signal = dict(signal, confidence="medium", reason="mr_shadow_extreme_estimate")
                    store_prediction(db, market["id"], mr_signal, regime, cycle, mkt_price=mkt_price)
                    # Force conv=2 (shadow) — store_prediction sets conv=3 for medium+should_trade,
                    # so override it after the fact
                    db.execute("""
                        UPDATE predictions SET conviction_score = 2
                        WHERE market_id = ? AND cycle = ? AND conviction_score >= 3
                        AND regime LIKE '%MEAN_REVERTING%'
                    """, (market["id"], cycle))
                    db.commit()
                    logger.info(f"  -> MR SHADOW: {signal['direction']} @ {signal['estimate']:.3f} (extreme estimate, tracked at conv=2)")
                else:
                    logger.info("  -> SKIP (mean-reverting regime)")
                    store_prediction(db, market["id"], {"estimate": mkt_price, "should_trade": False, "confidence": "skip", "reason": "regime_skip_mean_reverting"}, regime, cycle)
                continue

            if signal["should_trade"]:
                liquidity = None
                if get_clob_tokens and get_liquidity_summary:
                    try:
                        clob_tokens = _get_clob_tokens_safe(market["id"])
                        if clob_tokens:
                            liquidity = get_liquidity_summary(clob_tokens["yes"], clob_tokens["no"], "UP" if signal["estimate"] > 0.5 else "DOWN")
                            if format_liquidity_log:
                                logger.info(f"  {format_liquidity_log(liquidity)}")
                    except Exception as e:
                        logger.debug(f"[CLOB] skipped: {e}")

                store_prediction(db, market["id"], signal, regime, cycle, mkt_price=mkt_price, loose_mode=loose_mode, sibling_context=sibling_context, consensus=consensus, liquidity=liquidity)
                direction = "DOWN" if signal["estimate"] < 0.5 else "UP"
                logger.info(f"  -> {direction} @ {signal['estimate']:.2f} ({signal['confidence']}, est={signal['estimate']:.4f})")
            else:
                logger.info(f"  -> SKIP ({signal.get('reason', 'no_signal')})")
                store_prediction(db, market["id"], {"estimate": mkt_price, "should_trade": False, "confidence": "skip", "reason": signal.get("reason", "no_signal")}, regime, cycle, sibling_context=sibling_context)

    logger.info(f"\nDone. Predictions stored in {db_file}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", type=int, default=1, help="Cycle number")
    parser.add_argument("--markets", type=int, default=5, help="Max markets to predict")
    args = parser.parse_args()
    run_predictions(cycle=args.cycle, market_limit=args.markets)
