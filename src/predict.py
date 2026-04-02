"""
predict.py — Regime-filtered momentum predictions.

V4: No LLM agents. Pure computation from BTC candle data.
- Fetch 20 candles from Kraken/Coinbase
- Compute regime (volatility + autocorrelation)
- If mean-reverting → skip
- If streak >= 3 → RIDE the streak (momentum)
- Cost: $0/day

History: V3 contrarian (fade) lost at 37% WR on live Polymarket.
Inverting to momentum (ride) validated at 63% WR. Do NOT revert to fade.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import (
    FALLBACK_DEAD_HOURS, DEAD_HOUR_LOOKBACK_DAYS, DEAD_HOUR_MIN_BETS,
    DEAD_HOUR_MAX_WR, BTC_VOL_LOW, BTC_VOL_HIGH, AUTOCORR_TRENDING,
    PRICE_GATE_UPPER, PRICE_GATE_LOWER, PRICE_SWEET_SPOT_LOW,
    PRICE_SWEET_SPOT_HIGH, CONFIDENCE_HIGH_STREAK, MAX_CONVICTION,
)

DB_PATH = Path(__file__).parent.parent / "data" / "predictions.db"


def compute_dead_hours(db_path=None, lookback_days=DEAD_HOUR_LOOKBACK_DAYS,
                       min_bets=DEAD_HOUR_MIN_BETS, max_wr=DEAD_HOUR_MAX_WR):
    """
    Data-driven dead hour gate: query resolved predictions and return hours
    with WR below max_wr on at least min_bets samples.

    Returns (dead_hours: set, stats: list[dict]) where stats has per-hour
    breakdown for logging.

    Starts from FALLBACK_DEAD_HOURS (proven bad hours) and adds any new hours
    the data confirms. Fallback hours can be rehabilitated once they accumulate
    min_bets samples with WR >= max_wr (i.e., the gate got them wrong).

    Falls back to FALLBACK_DEAD_HOURS alone if the DB query fails or has no data.
    """
    try:
        db = sqlite3.connect(db_path or DB_PATH)
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
        db.close()
    except Exception as e:
        print(f"  [dead hours] DB query failed ({e}), using fallback {FALLBACK_DEAD_HOURS}")
        return FALLBACK_DEAD_HOURS, []

    if not rows:
        return FALLBACK_DEAD_HOURS, []

    # Start with fallback set, then adjust based on data
    dead = set(FALLBACK_DEAD_HOURS)
    stats = []
    hours_seen = set()
    for hour_utc, n, wins in rows:
        wr = wins / n if n > 0 else 0
        entry = {"hour": hour_utc, "bets": n, "wins": wins, "wr": wr}
        stats.append(entry)
        hours_seen.add(hour_utc)

        if n >= min_bets and wr < max_wr:
            # Data confirms this hour is dead
            dead.add(hour_utc)
        elif n >= min_bets and wr >= max_wr and hour_utc in dead:
            # Enough data to rehabilitate a fallback hour
            dead.discard(hour_utc)

    return dead, stats


def compute_regime_from_candles(candles, autocorr_threshold=-0.15):
    """
    Compute regime indicators from candle list.
    Returns dict with autocorrelation, volatility, and label.

    autocorr_threshold: below this → mean-reverting (default -0.15 for 5m, -0.20 for 15m)
    """
    closes = [c["close"] for c in candles]

    # Volatility: stdev of 5-min returns
    returns = [(closes[i] - closes[i-1]) / closes[i-1]
               for i in range(1, len(closes))]

    if len(returns) < 3:
        return {"autocorrelation": 0.0, "volatility": 0.0, "label": "UNKNOWN"}

    import statistics
    volatility = statistics.stdev(returns) * 100  # as percentage

    # Autocorrelation: lag-1
    n = len(returns)
    mean_r = sum(returns) / n
    var = sum((r - mean_r) ** 2 for r in returns) / n
    autocorr = 0.0
    if var > 0:
        cov = sum(
            (returns[i] - mean_r) * (returns[i-1] - mean_r)
            for i in range(1, n)
        ) / (n - 1)
        autocorr = cov / var

    # Labels
    if volatility < BTC_VOL_LOW:
        vol_label = "LOW_VOL"
    elif volatility < BTC_VOL_HIGH:
        vol_label = "MEDIUM_VOL"
    else:
        vol_label = "HIGH_VOL"

    if autocorr > AUTOCORR_TRENDING:
        trend_label = "TRENDING"
    elif autocorr < autocorr_threshold:
        trend_label = "MEAN_REVERTING"
    else:
        trend_label = "NEUTRAL"

    return {
        "autocorrelation": round(autocorr, 4),
        "volatility": round(volatility, 4),
        "label": f"{vol_label} / {trend_label}",
        "is_mean_reverting": autocorr < autocorr_threshold,
    }


def momentum_signal(candles, min_streak=3, config_key="btc_5m"):
    """
    Asset-agnostic momentum signal: ride streaks.
    1. streak >= min_streak same direction (default 3 for 5m, 2 for 15m)
    2. RIDE the streak (bet WITH it, not against it)
    3. Dynamic estimate from streak length + price magnitude + volatility

    config_key: shadow scorer config ("btc_5m", "btc_15m", "eth_5m", "kalshi")

    Returns dict with estimate, confidence, should_trade, and signal details.
    """
    if len(candles) < 5:
        return {"estimate": 0.5, "should_trade": False, "reason": "insufficient_data"}

    # Count consecutive streak (from most recent candle backward)
    last_dir = "UP" if candles[-1]["close"] >= candles[-1]["open"] else "DOWN"
    streak = 1
    for i in range(len(candles) - 2, -1, -1):
        d = "UP" if candles[i]["close"] >= candles[i]["open"] else "DOWN"
        if d == last_dir:
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

    # Dynamic estimate from streak length + price magnitude + volatility
    try:
        from shadow_conviction_scorer import strength_signal
        shadow = strength_signal(candles, signed_streak, config_key)
        estimate = shadow["estimate"] if shadow else (0.55 if direction == "UP" else 0.45)
    except Exception:
        estimate = 0.55 if direction == "UP" else 0.45

    confidence = "medium"
    if abs(signed_streak) >= CONFIDENCE_HIGH_STREAK:
        confidence = "high"

    return {
        "estimate": estimate,
        "should_trade": True,
        "direction": direction,
        "confidence": confidence,
        "streak": signed_streak,
        "reason": f"ride_streak_{direction}",
    }


def ensure_regime_column(db):
    """Add regime column to predictions table if it doesn't exist."""
    try:
        db.execute("ALTER TABLE predictions ADD COLUMN regime TEXT")
        db.commit()
    except sqlite3.OperationalError:
        pass  # already exists


def store_prediction(db, market_id, signal, regime, cycle, predicted_at=None,
                     mkt_price=None, loose_mode=False, sibling_context=None,
                     consensus=None, liquidity=None):
    """Store a prediction in the database."""
    if predicted_at is None:
        predicted_at = datetime.now(timezone.utc).isoformat()

    estimate = signal["estimate"]
    edge = abs(estimate - 0.5)
    confidence = signal.get("confidence", "low")

    # Conviction scoring — gates which predictions become bets
    # Production: flat $25/bet (Decision #14). Conv >= 3 places orders.
    if signal["should_trade"] and confidence in ("medium", "high"):
        direction = signal.get("direction", "")
        regime_label = regime.get("label", "") if regime else ""

        # DOWN in NEUTRAL regimes has no edge (52% WR on 25 bets, Mar 2026)
        # Still tracked in DB (conv=2) but no money risked
        # Derived from 5m data — disabled in loose_mode (15m)
        if not loose_mode and direction == "DOWN" and "NEUTRAL" in regime_label:
            conviction = 2
        # RIDE UP in sweet spot → high conviction ($200 bet)
        elif direction == "UP" and mkt_price is not None and PRICE_SWEET_SPOT_LOW <= mkt_price <= PRICE_SWEET_SPOT_HIGH:
            conviction = 4
        else:
            conviction = 3

        # Cross-exchange consensus boost: both Kraken + Coinbase see the same streak
        # Bump conviction by 1 (max 5) when score=2 (strong agreement)
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
    if sibling_context:
        reasoning_data["sibling_5m"] = sibling_context
    if consensus:
        reasoning_data["consensus"] = consensus
    if liquidity:
        reasoning_data["liquidity"] = liquidity
    reasoning = json.dumps(reasoning_data)

    # Store as "momentum_rule" agent
    try:
        db.execute("""
            INSERT INTO predictions
            (market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle, conviction_score, regime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            market_id, "momentum_rule", estimate, edge, confidence,
            reasoning, predicted_at, cycle, conviction, regime["label"],
        ))
    except sqlite3.OperationalError:
        # regime column might not exist yet
        db.execute("""
            INSERT INTO predictions
            (market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle, conviction_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            market_id, "momentum_rule", estimate, edge, confidence,
            reasoning, predicted_at, cycle, conviction,
        ))
    db.commit()


def _get_clob_tokens(market_id):
    """Wrapper — delegates to shared clob_depth.get_clob_tokens."""
    try:
        from clob_depth import get_clob_tokens
        return get_clob_tokens(market_id)
    except ImportError:
        return None


def get_5m_context(lookback_minutes=60):
    """
    Query the 5m DB for recent signal activity.
    Returns a summary the 15m pipeline can use for cross-timeframe awareness.
    """
    if not DB_PATH.exists():
        return None

    try:
        db5 = sqlite3.connect(DB_PATH)
        # Recent 5m bets (conv >= 3) in the lookback window
        rows = db5.execute("""
            SELECT estimate, conviction_score
            FROM predictions
            WHERE conviction_score >= 3
              AND predicted_at >= datetime('now', ?)
            ORDER BY predicted_at DESC
        """, (f"-{lookback_minutes} minutes",)).fetchall()
        db5.close()
    except Exception:
        return None

    if not rows:
        return {"bets": 0, "direction": None, "streak": 0, "message": "no recent 5m bets"}

    # Count directions
    up = sum(1 for r in rows if r[0] >= 0.5)
    down = len(rows) - up

    # Consecutive streak from most recent
    streak_dir = "UP" if rows[0][0] >= 0.5 else "DOWN"
    streak = 1
    for r in rows[1:]:
        d = "UP" if r[0] >= 0.5 else "DOWN"
        if d == streak_dir:
            streak += 1
        else:
            break

    majority = "UP" if up > down else ("DOWN" if down > up else "SPLIT")

    return {
        "bets": len(rows),
        "up": up,
        "down": down,
        "majority": majority,
        "streak_direction": streak_dir,
        "streak_length": streak,
        "direction": streak_dir if streak >= 2 else majority,
        "message": f"5m: {len(rows)} bets in last {lookback_minutes}min, "
                   f"{up}UP/{down}DN, streak={streak_dir}×{streak}",
    }


def run_predictions(cycle=1, market_limit=5, btc_data=None, db_path=None,
                    min_streak=3, autocorr_threshold=-0.15, loose_mode=False):
    """
    Main prediction loop.
    Fetch candles → compute regime → apply momentum rule → store.
    No API calls. $0 cost.

    db_path: optional override (default: data/predictions.db for 5-min)
    min_streak: minimum consecutive candles for signal (3 for 5m, 2 for 15m)
    autocorr_threshold: below this → mean-reverting skip (-0.15 for 5m, -0.20 for 15m)
    loose_mode: if True, disable 5m-derived gates (dead hours, cooldown, DOWN+NEUTRAL).
                Used by 15m pipeline to gather data without 5m-specific filters.
    """
    from btc_data import fetch_btc_candles, format_for_prompt

    db = sqlite3.connect(db_path or DB_PATH)
    ensure_regime_column(db)

    # Ensure conviction_score column exists
    try:
        db.execute("ALTER TABLE predictions ADD COLUMN conviction_score INTEGER")
        db.commit()
    except sqlite3.OperationalError:
        pass

    # Data-driven dead hour gate (replaces hardcoded set)
    # Disabled in loose_mode (15m gathers its own data)
    if not loose_mode:
        dead_hours, hour_stats = compute_dead_hours(db_path or DB_PATH)
        if hour_stats:
            dead_list = sorted(dead_hours) if dead_hours else ["none"]
            print(f"  Dead hours (auto): {dead_list}")
            for s in hour_stats:
                if s["bets"] >= 10:  # only log hours with meaningful data
                    flag = " ← DEAD" if s["hour"] in dead_hours else ""
                    print(f"    UTC {s['hour']:2d}: {s['bets']:3d} bets, {s['wr']:.0%} WR{flag}")
    else:
        dead_hours = set()

    # Fetch BTC candles
    if btc_data is None:
        btc_data = fetch_btc_candles(limit=20)

    if btc_data:
        candles = btc_data["candles"]
        consensus = btc_data.get("consensus")
        print(f"  BTC: ${btc_data['current_price']:,.0f} | 1h: {btc_data['1h_change_pct']:+.3f}%")
        # Log consensus
        if consensus and consensus.get("sources", 0) >= 2:
            k = consensus.get("streak_kraken", {})
            c = consensus.get("streak_coinbase", {})
            score = consensus.get("score", 0)
            label = {2: "STRONG", 1: "WEAK", -1: "DISAGREE"}.get(score, "?")
            print(f"  Consensus: {label} (score={score}) | Kraken: {k.get('direction','?')}x{k.get('length',0)} | Coinbase: {c.get('direction','?')}x{c.get('length',0)}")
        elif consensus:
            print(f"  Consensus: single source only ({consensus.get('sources', 0)}/2)")
        else:
            print(f"  Consensus: unavailable")
    else:
        print("  WARNING: No BTC data available — skipping predictions")
        db.close()
        return

    # Compute regime
    regime = compute_regime_from_candles(candles, autocorr_threshold=autocorr_threshold)
    print(f"  Regime: {regime['label']} (autocorr: {regime['autocorrelation']:+.4f})")

    # Check regime gate
    if regime["is_mean_reverting"]:
        print(f"  SKIP: Mean-reverting regime detected — no trades")

    # Cross-timeframe context: 15m reads what 5m has been seeing
    sibling_context = None
    if loose_mode:
        sibling_context = get_5m_context(lookback_minutes=60)
        if sibling_context and sibling_context["bets"] > 0:
            print(f"  5m sibling: {sibling_context['message']}")
        else:
            print(f"  5m sibling: no recent activity")

    # Compute momentum signal
    signal = momentum_signal(candles, min_streak=min_streak)
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
        print("  No unresolved markets found.")
        db.close()
        return

    print(f"  Markets: {len(markets)}")

    for market in markets:
        print(f"\n  Market: {market['question'][:60]}...")
        mkt_price = market['price_yes']
        print(f"  Mkt price: {mkt_price:.0%}")

        # Time-of-day gate: data-driven, recomputed each cycle from last 90 days
        current_hour_utc = datetime.now(timezone.utc).hour
        if current_hour_utc in dead_hours:
            skip_signal = {
                "estimate": mkt_price,
                "should_trade": False,
                "confidence": "skip",
                "reason": f"time_gate_dead_hour (UTC {current_hour_utc})",
            }
            store_prediction(db, market["id"], skip_signal, regime, cycle)
            print(f"    → SKIP (dead hour: UTC {current_hour_utc})")
            continue

        # Price gate: skip extreme prices (terrible risk/reward even when correct)
        # At price 0.95, need 95% WR to break even. Our signal hits ~66%. Math can't work.
        if mkt_price > PRICE_GATE_UPPER or mkt_price < PRICE_GATE_LOWER:
            skip_signal = {
                "estimate": mkt_price,
                "should_trade": False,
                "confidence": "skip",
                "reason": f"price_gate_extreme ({mkt_price:.0%})",
            }
            store_prediction(db, market["id"], skip_signal, regime, cycle)
            print(f"    → SKIP (price gate: {mkt_price:.0%})")
            continue

        # Apply regime gate: if mean-reverting, store as NO_BET (estimate=market price)
        if regime["is_mean_reverting"]:
            skip_signal = {
                "estimate": mkt_price,  # anchor to market
                "should_trade": False,
                "confidence": "skip",
                "reason": "regime_skip_mean_reverting",
            }
            store_prediction(db, market["id"], skip_signal, regime, cycle)
            print(f"    → SKIP (mean-reverting regime)")
            continue

        # Apply momentum signal
        if signal["should_trade"]:
            # Phase 6a: Query CLOB order book depth (read-only, never blocks)
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

            store_prediction(db, market["id"], signal, regime, cycle,
                             mkt_price=mkt_price, loose_mode=loose_mode,
                             sibling_context=sibling_context, consensus=consensus,
                             liquidity=liquidity)
            direction = "DOWN" if signal["estimate"] < 0.5 else "UP"
            print(f"    → {direction} @ {signal['estimate']:.2f} ({signal['confidence']}, est={signal['estimate']:.4f})")
        else:
            # No signal — store as NO_BET
            no_signal = {
                "estimate": mkt_price,
                "should_trade": False,
                "confidence": "skip",
                "reason": signal.get("reason", "no_signal"),
            }
            store_prediction(db, market["id"], no_signal, regime, cycle, sibling_context=sibling_context)
            print(f"    → SKIP ({signal.get('reason', 'no_signal')})")

    db.close()
    print(f"\nDone. Predictions stored in {db_path or DB_PATH}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", type=int, default=1, help="Cycle number")
    parser.add_argument("--markets", type=int, default=5, help="Max markets to predict")
    args = parser.parse_args()
    run_predictions(cycle=args.cycle, market_limit=args.markets)
