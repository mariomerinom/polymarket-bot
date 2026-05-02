from config import SHADOW_CANDLE_LIMIT
from config import DEFAULT_CANDLE_LIMIT
"""
shadow_indicators.py — Shadow logging of technical indicators alongside predictions.

Computes RSI(14), OBV slope, and VWAP z-score for every prediction cycle.
Values are logged into the reasoning JSON blob but never affect trading decisions.

Called from trade.py after all orders are placed. Failures are caught and logged,
never blocking trade execution.
"""

import json
import statistics
from datetime import datetime, timezone

from config import OBV_WINDOW, OBV_PRICE_BUCKET_LOW, OBV_PRICE_BUCKET_HIGH


BTC5M_TRIAGE_WEAK_HOURS_UTC = {1, 2, 12, 13, 19}
BTC5M_TRIAGE_AGENT = "momentum_rule"


def compute_rsi(closes, period=14):
    """Wilder-smoothed RSI. Returns 0-100 float, or 50.0 if insufficient data."""
    if len(closes) < period + 1:
        return 50.0

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

    gains = [max(d, 0) for d in deltas[:period]]
    losses = [max(-d, 0) for d in deltas[:period]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    for d in deltas[period:]:
        avg_gain = (avg_gain * (period - 1) + max(d, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-d, 0)) / period

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0

    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def compute_obv_slope(candles, window=10):
    """OBV linear regression slope, normalized. Returns float."""
    if len(candles) < 2:
        return 0.0

    obv = [0.0]
    for i in range(1, len(candles)):
        if candles[i]["close"] > candles[i - 1]["close"]:
            obv.append(obv[-1] + candles[i]["volume"])
        elif candles[i]["close"] < candles[i - 1]["close"]:
            obv.append(obv[-1] - candles[i]["volume"])
        else:
            obv.append(obv[-1])

    recent = obv[-window:] if len(obv) >= window else obv
    n = len(recent)
    if n < 2:
        return 0.0

    x_mean = (n - 1) / 2.0
    y_mean = sum(recent) / n

    num = sum((i - x_mean) * (recent[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))

    slope = num / den if den > 0 else 0.0

    mean_abs = sum(abs(v) for v in recent) / n if n > 0 else 1.0
    return round(slope / mean_abs, 4) if mean_abs > 0 else 0.0


def compute_vwap_zscore(candles):
    """VWAP deviation z-score. Returns dict with vwap, deviation, zscore, signal."""
    if len(candles) < 5:
        return {"vwap": None, "deviation": 0.0, "zscore": 0.0, "signal": None}

    cum_tpv = 0.0
    cum_vol = 0.0

    for c in candles:
        typical = (c["high"] + c["low"] + c["close"]) / 3.0
        cum_tpv += typical * c["volume"]
        cum_vol += c["volume"]

    if cum_vol == 0:
        return {"vwap": None, "deviation": 0.0, "zscore": 0.0, "signal": None}

    vwap = cum_tpv / cum_vol
    current_close = candles[-1]["close"]
    deviation = current_close - vwap

    closes = [c["close"] for c in candles]
    std = statistics.stdev(closes) if len(closes) >= 2 else 1.0
    zscore = deviation / std if std > 0 else 0.0

    signal = None
    if zscore < -2.0:
        signal = "UP"
    elif zscore > 2.0:
        signal = "DOWN"

    return {
        "vwap": round(vwap, 2),
        "deviation": round(deviation, 2),
        "zscore": round(zscore, 4),
        "signal": signal,
    }


def compute_btc5m_signal_triage(reasoning, *, predicted_at, regime, estimate,
                                conviction, agent):
    """Return shadow-only BTC5M signal triage cohort tags.

    These flags are observation-only. They deliberately do not change estimate,
    conviction, order routing, or any production gate.
    """
    if agent != BTC5M_TRIAGE_AGENT or conviction is None or conviction < 3:
        return {}

    direction = "UP" if estimate is not None and estimate >= 0.5 else "DOWN"
    tags = {}

    if "TRENDING" in (regime or ""):
        tags["shadow_btc5m_trending_only"] = {
            "candidate": "btc5m_trending_only_shadow",
            "would_keep": True,
            "regime": regime,
            "conviction": conviction,
            "direction": direction,
        }

    hour_utc = _hour_utc(predicted_at)
    if hour_utc in BTC5M_TRIAGE_WEAK_HOURS_UTC:
        tags["shadow_btc5m_weak_hour_filter"] = {
            "candidate": "btc5m_weak_hour_shadow",
            "would_filter": True,
            "hour_utc": hour_utc,
            "weak_hours_utc": sorted(BTC5M_TRIAGE_WEAK_HOURS_UTC),
            "conviction": conviction,
            "direction": direction,
        }

    if conviction == 4 and direction == "UP":
        tags["shadow_btc5m_conv4_up_recalibration"] = {
            "candidate": "btc5m_conv4_up_recalibration_shadow",
            "would_demote": True,
            "production_conviction": conviction,
            "direction": direction,
            "regime": regime,
        }

    judge = reasoning.get("judge") if isinstance(reasoning, dict) else None
    if isinstance(judge, dict) and judge.get("should_bet") is True:
        tags["shadow_btc5m_judge_accept"] = {
            "candidate": "btc5m_judge_accept_shadow",
            "would_keep": True,
            "p_success": judge.get("p_success"),
            "threshold": judge.get("threshold"),
            "conviction": conviction,
            "direction": direction,
        }

    return tags


def _hour_utc(value):
    if not value:
        return None
    try:
        normalized = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).hour
    except (TypeError, ValueError):
        return None


def shadow_log_indicators(db, cycle, candles=None):
    """Main entry point. Compute indicators and attach to this cycle's predictions.

    Called from execute_trades() AFTER all orders are placed.
    Never raises — all errors caught and logged.

    Args:
        db: sqlite3 connection
        cycle: prediction cycle number
        candles: optional list of candle dicts. When None, falls back to
                 _fetch_candles() (BTC 5m default). Pass candles directly
                 for ETH or BTC 15m pipelines.
    """
    try:
        return _shadow_log_impl(db, cycle, candles=candles)
    except Exception as e:
        print(f"    [SHADOW] error: {e}")
        return {}


def _fetch_candles(limit=SHADOW_CANDLE_LIMIT):
    """Lazy import to avoid circular imports and allow test mocking."""
    from btc_data import fetch_btc_candles
    return fetch_btc_candles(limit=limit)


def _shadow_log_impl(db, cycle, candles=None):
    if candles is None:
        btc = _fetch_candles(limit=SHADOW_CANDLE_LIMIT)
        if not btc or not btc.get("candles"):
            return {"summary": "no candle data"}
        candles = btc["candles"]

    if not candles:
        return {"summary": "no candle data"}

    closes = [c["close"] for c in candles]

    # Compute all 3 indicators once
    rsi_val = compute_rsi(closes, period=14)
    obv_val = compute_obv_slope(candles, window=OBV_WINDOW)
    vwap_data = compute_vwap_zscore(candles)

    # Fetch this cycle's predictions
    rows = db.execute(
        "SELECT id, market_id, reasoning, regime, estimate, conviction_score, "
        "predicted_at, agent "
        "FROM predictions WHERE cycle = ?",
        (cycle,),
    ).fetchall()

    if not rows:
        return {"summary": "no predictions this cycle"}

    updated = 0
    vwap_preds = 0

    for row in rows:
        pred_id = row[0]
        market_id = row[1]
        reasoning_raw = row[2]
        regime = row[3] or ""
        estimate = row[4]
        conviction = row[5]
        predicted_at = row[6]
        agent = row[7]

        # Parse existing reasoning
        try:
            reasoning = json.loads(reasoning_raw) if reasoning_raw else {}
        except (json.JSONDecodeError, TypeError):
            reasoning = {}

        # Spec 1: RSI — always attach
        reasoning["shadow_rsi_14"] = rsi_val

        # Spec 2: OBV — only for 0.50-0.70 price bucket
        mkt_price = reasoning.get("mkt_price")
        if mkt_price is not None and OBV_PRICE_BUCKET_LOW <= mkt_price <= OBV_PRICE_BUCKET_HIGH:
            reasoning["shadow_obv_slope"] = obv_val

        # Spec 3: VWAP z-score — attach to MEAN_REVERTING predictions
        if "MEAN_REVERTING" in regime:
            reasoning["shadow_vwap_zscore"] = vwap_data

        reasoning.update(compute_btc5m_signal_triage(
            reasoning,
            predicted_at=predicted_at,
            regime=regime,
            estimate=estimate,
            conviction=conviction,
            agent=agent,
        ))

        # Update reasoning JSON
        db.execute(
            "UPDATE predictions SET reasoning = ? WHERE id = ?",
            (json.dumps(reasoning), pred_id),
        )
        updated += 1

        # Spec 3: Generate VWAP mean-reversion prediction for strong signals
        if "MEAN_REVERTING" in regime and vwap_data["signal"] is not None:
            _insert_vwap_prediction(
                db, market_id, cycle, vwap_data, regime
            )
            vwap_preds += 1

    db.commit()

    summary = f"rsi={rsi_val}, obv={obv_val}, vwap_z={vwap_data['zscore']:.2f}"
    if vwap_preds:
        summary += f", vwap_preds={vwap_preds}"

    return {"summary": summary, "rsi_14": rsi_val, "obv_slope": obv_val,
            "vwap_zscore": vwap_data["zscore"], "vwap_predictions": vwap_preds,
            "updated": updated}


def _insert_vwap_prediction(db, market_id, cycle, vwap_data, regime):
    """Insert a paper prediction for VWAP mean-reversion signal."""
    # Check for duplicate — don't insert if vwap_meanrev already predicted this market+cycle
    existing = db.execute(
        "SELECT id FROM predictions WHERE market_id = ? AND cycle = ? AND agent = ?",
        (market_id, cycle, "vwap_meanrev"),
    ).fetchone()
    if existing:
        return

    if vwap_data["signal"] == "UP":
        estimate = 0.55
    else:
        estimate = 0.45

    reasoning = json.dumps({
        "signal": "vwap_mean_reversion",
        "vwap": vwap_data["vwap"],
        "zscore": vwap_data["zscore"],
        "deviation": vwap_data["deviation"],
        "direction": vwap_data["signal"],
        "observation_mode": True,
        "would_have_bet": True,
        "shadow_only": True,
    })

    now = datetime.now(timezone.utc).isoformat()

    db.execute(
        "INSERT INTO predictions (market_id, agent, estimate, edge, confidence, "
        "reasoning, predicted_at, cycle, conviction_score, regime) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (market_id, "vwap_meanrev", estimate, abs(estimate - 0.5), "shadow",
         reasoning, now, cycle, 2, regime),
    )
