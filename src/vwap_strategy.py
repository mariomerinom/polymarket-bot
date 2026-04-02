"""
vwap_strategy.py — VWAP mean-reversion predictions for MEAN_REVERTING regimes.

Fills the gap where the momentum model skips: when the regime is mean-reverting,
price deviations from VWAP tend to revert. Signal: z-score of (price - VWAP).

Shadow validation: 42/50 bets at 78.6% WR (gate: 50 at >58%).
Promoted to production per Decision #23.

Only fires for BTC 5m pipeline. Does NOT touch frozen files.
"""

import json
from datetime import datetime, timezone

from config import VWAP_ZSCORE_STRONG, VWAP_ZSCORE_MODERATE, VWAP_EDGE_MULTIPLIER, VWAP_MAX_EDGE
from shadow_indicators import compute_vwap_zscore


def generate_vwap_predictions(db, cycle, candles, regime):
    """
    Generate VWAP mean-reversion predictions for MEAN_REVERTING regime markets.

    Scans this cycle's predictions for markets in MEAN_REVERTING regime,
    computes VWAP z-score, and inserts vwap_rule predictions for strong signals.

    Args:
        db: sqlite3 connection (predictions.db)
        cycle: current prediction cycle number
        candles: list of candle dicts (from btc_data)
        regime: regime dict with 'label' key

    Returns:
        int: number of VWAP predictions generated
    """
    # Only fire in MEAN_REVERTING regime
    if not regime or "MEAN_REVERTING" not in regime.get("label", ""):
        return 0

    if not candles or len(candles) < 5:
        return 0

    # Compute VWAP z-score
    vwap_data = compute_vwap_zscore(candles)
    zscore = vwap_data.get("zscore", 0)

    # Determine conviction from z-score magnitude
    abs_z = abs(zscore)
    if abs_z >= VWAP_ZSCORE_STRONG:
        conviction = 3  # Live $25 bet
    elif abs_z >= VWAP_ZSCORE_MODERATE:
        conviction = 2  # Tracked, no bet (building data for lower threshold)
    else:
        return 0  # No signal

    # Determine direction (mean reversion)
    if zscore < -VWAP_ZSCORE_MODERATE:
        direction = "UP"  # Price below VWAP → expect reversion up
    else:
        direction = "DOWN"  # Price above VWAP → expect reversion down

    # Dynamic estimate from z-score magnitude
    edge = min(abs_z * VWAP_EDGE_MULTIPLIER, VWAP_MAX_EDGE)
    estimate = 0.5 + edge if direction == "UP" else 0.5 - edge

    # Find markets in this cycle with MEAN_REVERTING regime (momentum skipped them)
    rows = db.execute(
        "SELECT DISTINCT market_id, regime FROM predictions "
        "WHERE cycle = ? AND regime LIKE '%MEAN_REVERTING%'",
        (cycle,),
    ).fetchall()

    if not rows:
        return 0

    count = 0
    now = datetime.now(timezone.utc).isoformat()

    for market_id, mkt_regime in rows:
        # Deduplication: skip if vwap_rule already predicted this market+cycle
        existing = db.execute(
            "SELECT id FROM predictions WHERE market_id = ? AND cycle = ? AND agent = ?",
            (market_id, cycle, "vwap_rule"),
        ).fetchone()
        if existing:
            continue

        reasoning = json.dumps({
            "signal": "vwap_mean_reversion",
            "vwap": vwap_data["vwap"],
            "zscore": vwap_data["zscore"],
            "deviation": vwap_data["deviation"],
            "direction": direction,
            "conviction_tier": conviction,
            "asset": "BTC",
        })

        db.execute(
            "INSERT INTO predictions (market_id, agent, estimate, edge, confidence, "
            "reasoning, predicted_at, cycle, conviction_score, regime) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (market_id, "vwap_rule", round(estimate, 4), round(edge, 4),
             "medium" if conviction >= 3 else "shadow",
             reasoning, now, cycle, conviction, mkt_regime),
        )
        count += 1

    if count:
        db.commit()

    return count
