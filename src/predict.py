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
import math
import sqlite3
import logging
import time
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
    """Wrapper that returns tokens or None without blowing up.

    DEPRECATED: Use clob_depth.get_clob_tokens_safe() instead.
    Kept here for internal predict.py usage and backward compatibility.
    New callers should import from clob_depth directly.
    """
    if get_clob_tokens:
        return get_clob_tokens(market_id)
    return None


def _build_judge_features(signal, regime, indicators, liquidity, consensus,
                          gate_state, mkt_price, estimate, edge, conviction,
                          predicted_at, candles=None) -> dict:
    """Assemble feature dict for Judge evaluation.

    All data sources are already available at prediction time.
    Missing features default to NaN (XGBoost handles natively).
    """
    NaN = float("nan")
    f = {}

    # Pipeline metadata (BTC 5m hardcoded — Judge is BTC 5m only)
    f["pipeline_id"] = 0
    f["venue_polymarket"] = 1
    f["venue_kalshi"] = 0
    f["venue_bybit"] = 0
    f["asset_btc"] = 1
    f["asset_eth"] = 0
    f["timeframe"] = 5

    # Core prediction
    f["estimate"] = estimate
    f["edge"] = edge
    f["conviction_score"] = conviction
    f["mkt_price"] = mkt_price if mkt_price is not None else NaN

    # Signal
    f["direction_up"] = 1 if signal.get("direction") == "UP" else 0
    f["streak"] = signal.get("streak", 0)
    f["signal_estimate"] = signal.get("estimate", 0.5)
    f["should_trade"] = 1 if signal.get("should_trade") else 0
    f["conviction_tier"] = conviction
    f["would_have_bet"] = 1 if (signal.get("should_trade") and
                                signal.get("confidence") in ("medium", "high")) else 0

    # Regime
    if regime:
        f["autocorrelation"] = regime.get("autocorrelation", NaN)
        f["volatility"] = regime.get("volatility", NaN)
        f["is_mean_reverting"] = int(regime.get("is_mean_reverting", 0))
        label = regime.get("label", "")
        f["regime_high_vol"] = 1 if "HIGH_VOL" in label else 0
        f["regime_medium_vol"] = 1 if "MEDIUM_VOL" in label else 0
        f["regime_low_vol"] = 1 if "LOW_VOL" in label else 0
        f["regime_trending"] = 1 if "TRENDING" in label else 0
        f["regime_mean_rev"] = 1 if "MEAN_REVERTING" in label else 0
        f["regime_neutral"] = 1 if ("NEUTRAL" in label and "MEAN_REVERTING" not in label) else 0
    else:
        for k in ["autocorrelation", "volatility"]:
            f[k] = NaN
        f["is_mean_reverting"] = 0
        for k in ["regime_high_vol", "regime_medium_vol", "regime_low_vol",
                   "regime_trending", "regime_mean_rev", "regime_neutral"]:
            f[k] = 0

    # Temporal
    try:
        dt = datetime.fromisoformat(predicted_at) if predicted_at else datetime.now(timezone.utc)
    except Exception:
        dt = datetime.now(timezone.utc)
    hour_frac = dt.hour + dt.minute / 60.0
    f["hour_sin"] = math.sin(2 * math.pi * hour_frac / 24)
    f["hour_cos"] = math.cos(2 * math.pi * hour_frac / 24)
    dow = dt.weekday()
    f["dow_sin"] = math.sin(2 * math.pi * dow / 7)
    f["dow_cos"] = math.cos(2 * math.pi * dow / 7)

    # TA indicators from TAEngine (indicators dict from botsy_engine)
    ta_keys = ["rsi_14", "rsi_7", "vwap", "obv", "obv_slope", "rvol",
               "z_score", "ema_9", "ema_21", "ema_ratio", "bb_upper",
               "bb_lower", "bb_mid", "bb_bandwidth", "stoch_k", "stoch_d",
               "shadow_rsi_14", "vwap_zscore", "vwap_deviation"]
    if indicators:
        for key in ta_keys:
            f[key] = indicators.get(key, NaN)
    else:
        for key in ta_keys:
            f[key] = NaN

    # TA from pure_ta (top SHAP features — computed from raw candles)
    ta_pure_keys = ["rsi_14", "rsi_7", "bb_bandwidth", "bb_pctb", "z_score",
                    "rvol", "obv_slope", "ema_ratio", "stoch_k", "stoch_d"]
    if candles and len(candles) >= 21:
        try:
            from pure_ta import compute_ta
            closes = [c["close"] for c in candles[-30:]]
            highs = [c["high"] for c in candles[-30:]]
            lows = [c["low"] for c in candles[-30:]]
            volumes = [c["volume"] for c in candles[-30:]]
            ta = compute_ta(closes, highs, lows, volumes)
            if ta:
                for k in ta_pure_keys:
                    f[f"ta_{k}"] = ta.get(k, NaN)
            else:
                for k in ta_pure_keys:
                    f[f"ta_{k}"] = NaN
        except Exception:
            for k in ta_pure_keys:
                f[f"ta_{k}"] = NaN
    else:
        for k in ta_pure_keys:
            f[f"ta_{k}"] = NaN

    # Strength (shadow conviction scorer)
    if candles and strength_signal is not None:
        try:
            streak_val = signal.get("streak", 0)
            ss = strength_signal(candles[-30:], streak_val, "btc_5m")
            if ss:
                f["strength"] = ss.get("strength", NaN)
                f["length_strength"] = ss.get("length_strength", NaN)
                f["magnitude_strength"] = ss.get("magnitude_strength", NaN)
            else:
                f["strength"] = NaN
                f["length_strength"] = NaN
                f["magnitude_strength"] = NaN
        except Exception:
            f["strength"] = NaN
            f["length_strength"] = NaN
            f["magnitude_strength"] = NaN
    else:
        f["strength"] = NaN
        f["length_strength"] = NaN
        f["magnitude_strength"] = NaN

    # Liquidity
    if liquidity:
        f["spread"] = liquidity.get("spread", NaN)
        f["spread_pct"] = liquidity.get("spread_pct", NaN)
        f["max_bet_2pct"] = liquidity.get("max_bet_2pct", NaN)
        f["max_bet_5pct"] = liquidity.get("max_bet_5pct", NaN)
    else:
        for k in ["spread", "spread_pct", "max_bet_2pct", "max_bet_5pct"]:
            f[k] = NaN

    # Regime gate
    if gate_state and isinstance(gate_state, dict):
        f["daily_range_zscore"] = gate_state.get("daily_range_zscore", NaN)
        f["daily_velocity_zscore"] = gate_state.get("daily_velocity_zscore", NaN)
        f["gate_gated"] = 1 if gate_state.get("gated") else 0
    else:
        f["daily_range_zscore"] = NaN
        f["daily_velocity_zscore"] = NaN
        f["gate_gated"] = 0

    # Consensus
    if consensus:
        f["consensus_score"] = consensus.get("score", NaN)
        f["consensus_agree"] = 1 if consensus.get("agree") else 0
    else:
        f["consensus_score"] = NaN
        f["consensus_agree"] = 0

    # Venue-specific (NaN for Polymarket — model handles natively)
    for k in ["kalshi_spread", "kalshi_bid", "kalshi_ask", "kalshi_volume",
              "kalshi_oi", "funding_rate", "mark_price"]:
        f.setdefault(k, NaN)

    return f


def store_prediction(db, market_id, signal, regime, cycle, predicted_at=None,
                     mkt_price=None, loose_mode=False, sibling_context=None,
                     consensus=None, liquidity=None, indicators=None,
                     candles=None):
    """Store a prediction in the database."""
    if predicted_at is None:
        predicted_at = datetime.now(timezone.utc).isoformat()

    estimate = signal["estimate"]
    edge = abs(estimate - 0.5)
    confidence = signal.get("confidence", "low")

    if signal["should_trade"] and confidence in ("medium", "high"):
        direction = signal.get("direction", "")
        regime_label = regime.get("label", "") if regime else ""

        # HIGH_VOL non-trending gate: 54.8% WR on 126 bets — below breakeven after fees.
        # Skip for 15m (loose_mode) where HIGH_VOL actually performs better (64.3%).
        if not loose_mode and "HIGH_VOL" in regime_label and "TRENDING" not in regime_label:
            conviction = 2
        elif not loose_mode and direction == "DOWN" and "NEUTRAL" in regime_label:
            conviction = 2
        elif direction == "UP" and mkt_price is not None and PRICE_SWEET_SPOT_LOW <= mkt_price <= PRICE_SWEET_SPOT_HIGH:
            conviction = 4
        else:
            conviction = 3

        # Intraday range gate (2026-04-17): demote when today's in-progress
        # range_pct is ≥1.5σ above 30-day historical mean. Evidence:
        # Apr 7 r_z=+2.9 → btc_5m −$193 (39% WR); Apr 13 r_z=+1.8 → −$27
        # at 40% WR. Uses TODAY's candles (not yesterday's completed row,
        # which was the failure mode of reverted #68).
        if not loose_mode and conviction >= 3 and candles:
            try:
                import sqlite3
                from pathlib import Path
                from intraday_regime_gate import (
                    evaluate_intraday_range_gate, fetch_historical_ranges_pct,
                )
                _daily_db_path = (
                    Path(__file__).parent.parent / "data" / "asset_daily.db"
                )
                if _daily_db_path.exists():
                    with sqlite3.connect(str(_daily_db_path)) as _daily_db:
                        _today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                        _hist = fetch_historical_ranges_pct(
                            _daily_db, "BTC", exclude_date=_today, days=30)
                    _gate = evaluate_intraday_range_gate(
                        candles=candles, asset="BTC",
                        asof_utc=datetime.now(timezone.utc),
                        historical_ranges_pct=_hist,
                    )
                    if _gate["gated"]:
                        conviction = 2
                        print(f"    [INTRADAY_GATE] demoted to conv=2: "
                              f"{_gate['reason']}")
            except Exception as _e:
                # Safety: never break predict on gate error
                print(f"    [INTRADAY_GATE] error: {_e}")

        consensus_score = consensus.get("score", 0) if consensus else 0
        if consensus_score == 2 and conviction >= 3:
            conviction = min(conviction + 1, MAX_CONVICTION)

        # 5m confirmation boost: if 5m pipeline has 2+ recent bets in same direction
        if sibling_context and sibling_context.get("bets", 0) >= 2:
            sibling_dir = sibling_context.get("direction")
            if sibling_dir == direction and conviction >= 3:
                conviction = min(conviction + 1, MAX_CONVICTION)
    elif signal["should_trade"]:
        conviction = 2
    else:
        conviction = 0

    # ── ML Judge + Daily-regime gate (SHADOW ONLY) ─────────────────
    pre_gate_conviction = conviction
    judge_state = None
    gate_state = None

    if conviction >= 3:
        # Daily regime gate (shadow — kept for counterfactual tracking)
        try:
            from regime_gate import evaluate_btc_gate
            try:
                _asof = datetime.fromisoformat(predicted_at) if predicted_at else None
            except Exception:
                _asof = None
            gate_state = evaluate_btc_gate(asof=_asof)
            # Shadow only — do NOT demote conviction
        except Exception as _e:
            gate_state = {"gated": False, "reason": f"gate_error_{_e}"}

        # ML Judge evaluation (shadow — conviction is NOT modified)
        try:
            from judge import get_judge
            judge = get_judge()
            if judge:
                features = _build_judge_features(
                    signal, regime, indicators, liquidity, consensus,
                    gate_state, mkt_price, estimate, edge, conviction,
                    predicted_at, candles,
                )
                judge_state = judge.evaluate(features)
                # SHADOW ONLY — do NOT modify conviction
                # Promote to live veto after 200+ forward predictions validate
                # Future: if not judge_state["should_bet"]: conviction = 2
        except Exception as _e:
            judge_state = {"error": str(_e)}

    reasoning_data = {
        "signal": signal,
        "regime": regime,
        "would_have_bet": signal.get("should_trade", False) and confidence in ("medium", "high"),
        "conviction_tier": conviction,
        "pre_gate_conviction": pre_gate_conviction,
        "regime_gate": gate_state,
        "judge": judge_state,
        "mkt_price": mkt_price,
    }

    # Shadow regime relative (Phase A, added 2026-04-21): log the asset's
    # own-distribution z-score regime alongside the absolute one. Mirrors
    # SOL/DOGE pattern shipped 2026-04-19. BTC's HIGH_VOL/NEUTRAL cycles
    # may reclassify to MEDIUM or LOW under self-referential thresholds,
    # unlocking tradeable activity. After 7 days of shadow data, compare
    # counterfactual WR on reclassified cycles (Phase B).
    try:
        from relative_regime import compute_shadow_regime
        reasoning_data["shadow_regime_relative"] = compute_shadow_regime(
            candles, "BTC")
    except Exception as _e:
        reasoning_data["shadow_regime_relative"] = {"error": str(_e)}
    if sibling_context:
        reasoning_data["sibling_5m"] = sibling_context
        direction = signal.get("direction", "")
        reasoning_data["sibling_5m_boost"] = (
            sibling_context.get("bets", 0) >= 2
            and sibling_context.get("direction") == direction
        )
    if consensus: reasoning_data["consensus"] = consensus
    if liquidity: reasoning_data["liquidity"] = liquidity
    if indicators:
        # Store full indicator snapshot (flattened) for post-hoc analysis.
        # Uses indicator_snapshot() to flatten nested dicts (bbands, stoch)
        # into queryable flat keys (bb_bandwidth, stoch_k, etc.)
        try:
            from strategies.base import indicator_snapshot
            # Build a minimal context object for the snapshot helper
            class _Ctx:
                pass
            ctx = _Ctx()
            ctx.indicators = indicators
            ctx.regime = regime
            ctx.candles = candles or []
            reasoning_data["indicators"] = indicator_snapshot(ctx)
        except Exception:
            # Fallback: store compact snapshot without flattening
            reasoning_data["indicators"] = {
                k: round(v, 4) if isinstance(v, float) else v
                for k, v in indicators.items()
                if k not in ("bbands", "stoch")
            }
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


def _emit_diag(market_id, conviction, candle_ts_ms, candle_close, current_price):
    """Emit Phase 2 DIAG lines for every prediction cycle.

    Format must match validate_phase2.py regex exactly:
        DIAG|decision_delay_ms=<number>|market=<string>
        DIAG|conv=<integer>|drift=<decimal>|decision_delay_ms=<number>
    """
    now_ms = time.time() * 1000
    decision_delay_ms = now_ms - candle_ts_ms
    if decision_delay_ms < 0:
        decision_delay_ms = 0
    logger.info(f"DIAG|decision_delay_ms={decision_delay_ms:.0f}|market={market_id}")

    drift = abs(current_price - candle_close) / candle_close if candle_close > 0 else 0.0
    logger.info(f"DIAG|conv={conviction}|drift={drift:.4f}|decision_delay_ms={decision_delay_ms:.0f}")


def run_predictions(cycle=1, market_limit=5, btc_data=None, db_path=None,
                    min_streak=None, autocorr_threshold=AUTOCORR_MEAN_REVERTING_5M,
                    loose_mode=False, indicators=None):
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

            # DIAG: extract candle timestamp and close for snapshot_age/drift
            _last_candle = candles[-1] if candles else {}
            _diag_candle_close = _last_candle.get("close", 0.0)
            _diag_current_price = btc_data.get("current_price", _diag_candle_close)
            # timestamp_ms = candle OPEN time. Candle data extends to close time.
            # For confirmed candles, close_time ≈ open_time + interval.
            # Use close time for snapshot_age (how stale the data actually is).
            if "timestamp_ms" in _last_candle:
                # Estimate interval from gap between non-duplicate candles
                _interval_ms = 300_000  # default 5m
                for i in range(len(candles) - 2, -1, -1):
                    if candles[i].get("timestamp_ms", 0) < _last_candle["timestamp_ms"]:
                        _interval_ms = _last_candle["timestamp_ms"] - candles[i]["timestamp_ms"]
                        break
                _diag_candle_ts_ms = _last_candle["timestamp_ms"] + _interval_ms
            else:
                # REST candles only have "time" (HH:MM) — estimate as now (candle just closed)
                _diag_candle_ts_ms = time.time() * 1000
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
                    _emit_diag(market["id"], 2, _diag_candle_ts_ms, _diag_candle_close, _diag_current_price)
                else:
                    logger.info(f"  -> SKIP (dead hour: UTC {current_hour_utc})")
                    store_prediction(db, market["id"], {"estimate": mkt_price, "should_trade": False, "confidence": "skip", "reason": f"time_gate_dead_hour (UTC {current_hour_utc})"}, regime, cycle)
                    _emit_diag(market["id"], 0, _diag_candle_ts_ms, _diag_candle_close, _diag_current_price)
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
                    _emit_diag(market["id"], 2, _diag_candle_ts_ms, _diag_candle_close, _diag_current_price)
                else:
                    logger.info(f"  -> SKIP (price gate: {mkt_price:.0%})")
                    store_prediction(db, market["id"], {"estimate": mkt_price, "should_trade": False, "confidence": "skip", "reason": f"price_gate_extreme ({mkt_price:.0%})"}, regime, cycle)
                    _emit_diag(market["id"], 0, _diag_candle_ts_ms, _diag_candle_close, _diag_current_price)
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
                    _emit_diag(market["id"], 2, _diag_candle_ts_ms, _diag_candle_close, _diag_current_price)
                else:
                    logger.info("  -> SKIP (mean-reverting regime)")
                    store_prediction(db, market["id"], {"estimate": mkt_price, "should_trade": False, "confidence": "skip", "reason": "regime_skip_mean_reverting"}, regime, cycle)
                    _emit_diag(market["id"], 0, _diag_candle_ts_ms, _diag_candle_close, _diag_current_price)
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

                store_prediction(db, market["id"], signal, regime, cycle, mkt_price=mkt_price, loose_mode=loose_mode, sibling_context=sibling_context, consensus=consensus, liquidity=liquidity, indicators=indicators, candles=candles)
                direction = "DOWN" if signal["estimate"] < 0.5 else "UP"
                logger.info(f"  -> {direction} @ {signal['estimate']:.2f} ({signal['confidence']}, est={signal['estimate']:.4f})")
                # Query back conviction for DIAG (store_prediction computes it internally)
                _conv_row = db.execute(
                    "SELECT conviction_score FROM predictions WHERE market_id = ? AND cycle = ? ORDER BY rowid DESC LIMIT 1",
                    (market["id"], cycle)
                ).fetchone()
                _emit_diag(market["id"], _conv_row[0] if _conv_row else 0, _diag_candle_ts_ms, _diag_candle_close, _diag_current_price)
            else:
                logger.info(f"  -> SKIP ({signal.get('reason', 'no_signal')})")
                store_prediction(db, market["id"], {"estimate": mkt_price, "should_trade": False, "confidence": "skip", "reason": signal.get("reason", "no_signal")}, regime, cycle, sibling_context=sibling_context)
                _emit_diag(market["id"], 0, _diag_candle_ts_ms, _diag_candle_close, _diag_current_price)

    logger.info(f"\nDone. Predictions stored in {db_file}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", type=int, default=1, help="Cycle number")
    parser.add_argument("--markets", type=int, default=5, help="Max markets to predict")
    args = parser.parse_args()
    run_predictions(cycle=args.cycle, market_limit=args.markets)
