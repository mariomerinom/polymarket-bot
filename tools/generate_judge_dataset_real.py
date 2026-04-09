"""
generate_judge_dataset_real.py — Build Judge training dataset from REAL resolved predictions.

Reads all 5 prediction databases, extracts features from the reasoning JSON,
and labels each row with the actual outcome (win=1, loss=0).

Unlike the synthetic dataset (candle direction labels), this uses real venue
outcomes — the actual question the Judge needs to answer.

Usage:
    python3 tools/generate_judge_dataset_real.py
    python3 tools/generate_judge_dataset_real.py --output data/judge_dataset_real.csv

Features are extracted at three tiers:
  Tier 1 (Universal): signal, regime, conviction, temporal — all 5 pipelines
  Tier 2 (Polymarket): TA indicators, liquidity, shadow scores — BTC/ETH 5m/15m
  Tier 3 (Venue-specific): Kalshi orderbook, Bybit funding — where available

XGBoost handles NaN natively, so missing Tier 2/3 features are fine.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent

# ── Pipeline definitions ──────────────────────────────────────────────────

PIPELINES = [
    {
        "name": "btc_5m",
        "db": ROOT / "data" / "predictions.db",
        "venue": "polymarket",
        "asset": "BTC",
        "timeframe": 5,
        "pipeline_id": 0,
    },
    {
        "name": "btc_15m",
        "db": ROOT / "data" / "predictions_15m.db",
        "venue": "polymarket",
        "asset": "BTC",
        "timeframe": 15,
        "pipeline_id": 1,
    },
    {
        "name": "eth_5m",
        "db": ROOT / "data" / "predictions_eth.db",
        "venue": "polymarket",
        "asset": "ETH",
        "timeframe": 5,
        "pipeline_id": 2,
    },
    {
        "name": "kalshi",
        "db": ROOT / "data" / "predictions_kalshi.db",
        "venue": "kalshi",
        "asset": "BTC",
        "timeframe": 5,
        "pipeline_id": 3,
    },
    {
        "name": "bybit",
        "db": ROOT / "data" / "predictions_bybit.db",
        "venue": "bybit",
        "asset": "BTC",
        "timeframe": 5,
        "pipeline_id": 4,
    },
]


# ── Feature extraction ────────────────────────────────────────────────────

def safe_float(val, default=float("nan")) -> float:
    """Safely convert to float, returning NaN on failure."""
    if val is None:
        return default
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (ValueError, TypeError):
        return default


def extract_features(row: dict, reasoning: dict, pipeline: dict) -> dict:
    """Extract all features from a prediction row + its reasoning JSON.

    Returns a flat dict of numeric features (NaN for missing).
    """
    f: dict = {}

    # ── Pipeline identity ────────────────────────────────────────────
    f["pipeline_id"] = pipeline["pipeline_id"]
    f["venue_polymarket"] = 1 if pipeline["venue"] == "polymarket" else 0
    f["venue_kalshi"] = 1 if pipeline["venue"] == "kalshi" else 0
    f["venue_bybit"] = 1 if pipeline["venue"] == "bybit" else 0
    f["asset_btc"] = 1 if pipeline["asset"] == "BTC" else 0
    f["asset_eth"] = 1 if pipeline["asset"] == "ETH" else 0
    f["timeframe"] = pipeline["timeframe"]

    # ── Core prediction columns ──────────────────────────────────────
    f["estimate"] = safe_float(row.get("estimate"))
    f["conviction_score"] = safe_float(row.get("conviction_score"), 0)
    f["edge"] = safe_float(row.get("edge"))
    f["mkt_price"] = safe_float(row.get("price_yes"))

    # Direction as numeric (1=UP, 0=DOWN)
    signal = reasoning.get("signal", {})
    if isinstance(signal, dict):
        direction = signal.get("direction", "")
        f["direction_up"] = 1 if direction == "UP" else 0
        f["streak"] = safe_float(signal.get("streak"), 0)
        f["signal_estimate"] = safe_float(signal.get("estimate"))
        f["should_trade"] = 1 if signal.get("should_trade") else 0
    else:
        f["direction_up"] = float("nan")
        f["streak"] = float("nan")
        f["signal_estimate"] = float("nan")
        f["should_trade"] = float("nan")

    # Conviction tier from reasoning
    f["conviction_tier"] = safe_float(reasoning.get("conviction_tier"), 0)
    f["would_have_bet"] = 1 if reasoning.get("would_have_bet") else 0

    # ── Regime features ──────────────────────────────────────────────
    regime = reasoning.get("regime", {})
    if isinstance(regime, dict):
        f["autocorrelation"] = safe_float(regime.get("autocorrelation"))
        f["volatility"] = safe_float(regime.get("volatility"))
        f["is_mean_reverting"] = 1 if regime.get("is_mean_reverting") else 0
    else:
        f["autocorrelation"] = float("nan")
        f["volatility"] = float("nan")
        f["is_mean_reverting"] = float("nan")

    # Regime label decomposition
    regime_label = row.get("regime", "") or ""
    f["regime_high_vol"] = 1 if "HIGH_VOL" in regime_label else 0
    f["regime_medium_vol"] = 1 if "MEDIUM_VOL" in regime_label else 0
    f["regime_low_vol"] = 1 if "LOW_VOL" in regime_label else 0
    f["regime_trending"] = 1 if "TRENDING" in regime_label else 0
    f["regime_mean_rev"] = 1 if "MEAN_REVERTING" in regime_label else 0
    f["regime_neutral"] = 1 if "NEUTRAL" in regime_label else 0

    # ── Temporal features ────────────────────────────────────────────
    predicted_at = row.get("predicted_at", "")
    try:
        if "+" in str(predicted_at) or "Z" in str(predicted_at):
            dt = datetime.fromisoformat(str(predicted_at).replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(str(predicted_at)).replace(tzinfo=timezone.utc)
        f["hour_sin"] = round(math.sin(2 * math.pi * dt.hour / 24), 6)
        f["hour_cos"] = round(math.cos(2 * math.pi * dt.hour / 24), 6)
        f["dow_sin"] = round(math.sin(2 * math.pi * dt.weekday() / 7), 6)
        f["dow_cos"] = round(math.cos(2 * math.pi * dt.weekday() / 7), 6)
    except Exception:
        f["hour_sin"] = float("nan")
        f["hour_cos"] = float("nan")
        f["dow_sin"] = float("nan")
        f["dow_cos"] = float("nan")

    # ── Tier 2: Technical indicators (Polymarket pipelines) ──────────
    indicators = reasoning.get("indicators", {})
    if isinstance(indicators, dict):
        f["rsi_14"] = safe_float(indicators.get("rsi_14"))
        f["rsi_7"] = safe_float(indicators.get("rsi_7"))
        f["vwap"] = safe_float(indicators.get("vwap"))
        f["obv"] = safe_float(indicators.get("obv"))
        f["obv_slope"] = safe_float(indicators.get("obv_slope"))
        f["rvol"] = safe_float(indicators.get("rvol"))
        f["z_score"] = safe_float(indicators.get("z_score"))
        f["ema_9"] = safe_float(indicators.get("ema_9"))
        f["ema_21"] = safe_float(indicators.get("ema_21"))
        # Derived: EMA ratio (scale-invariant)
        ema9 = safe_float(indicators.get("ema_9"))
        ema21 = safe_float(indicators.get("ema_21"))
        if math.isfinite(ema9) and math.isfinite(ema21) and ema21 != 0:
            f["ema_ratio"] = round(ema9 / ema21, 6)
        else:
            f["ema_ratio"] = float("nan")
        f["bb_upper"] = safe_float(indicators.get("bb_upper"))
        f["bb_lower"] = safe_float(indicators.get("bb_lower"))
        f["bb_mid"] = safe_float(indicators.get("bb_mid"))
        # Derived: BB bandwidth and %B (scale-invariant)
        bb_u = safe_float(indicators.get("bb_upper"))
        bb_l = safe_float(indicators.get("bb_lower"))
        bb_m = safe_float(indicators.get("bb_mid"))
        if all(math.isfinite(v) for v in [bb_u, bb_l, bb_m]) and bb_m != 0:
            f["bb_bandwidth"] = round((bb_u - bb_l) / bb_m, 6)
        else:
            f["bb_bandwidth"] = float("nan")
        f["stoch_k"] = safe_float(indicators.get("stoch_k"))
        f["stoch_d"] = safe_float(indicators.get("stoch_d"))
    else:
        for k in ["rsi_14", "rsi_7", "vwap", "obv", "obv_slope", "rvol",
                   "z_score", "ema_9", "ema_21", "ema_ratio",
                   "bb_upper", "bb_lower", "bb_mid", "bb_bandwidth",
                   "stoch_k", "stoch_d"]:
            f[k] = float("nan")

    # Shadow RSI
    f["shadow_rsi_14"] = safe_float(reasoning.get("shadow_rsi_14"))

    # Shadow VWAP zscore
    vwap_shadow = reasoning.get("shadow_vwap_zscore", {})
    if isinstance(vwap_shadow, dict):
        f["vwap_zscore"] = safe_float(vwap_shadow.get("zscore"))
        f["vwap_deviation"] = safe_float(vwap_shadow.get("deviation"))
    else:
        f["vwap_zscore"] = float("nan")
        f["vwap_deviation"] = float("nan")

    # Shadow generic scorer
    scorer = reasoning.get("shadow_generic_scorer", {})
    if isinstance(scorer, dict):
        f["strength"] = safe_float(scorer.get("strength"))
        f["length_strength"] = safe_float(scorer.get("length_strength"))
        f["magnitude_strength"] = safe_float(scorer.get("magnitude_strength"))
    else:
        f["strength"] = float("nan")
        f["length_strength"] = float("nan")
        f["magnitude_strength"] = float("nan")

    # ── Tier 2: Liquidity features (Polymarket) ─────────────────────
    liq = reasoning.get("liquidity", {})
    if isinstance(liq, dict):
        f["spread"] = safe_float(liq.get("spread"))
        f["spread_pct"] = safe_float(liq.get("spread_pct"))
        f["max_bet_2pct"] = safe_float(liq.get("max_bet_2pct"))
        f["max_bet_5pct"] = safe_float(liq.get("max_bet_5pct"))
    else:
        for k in ["spread", "spread_pct", "max_bet_2pct", "max_bet_5pct"]:
            f[k] = float("nan")

    # ── Tier 2: Regime gate (BTC 5m) ────────────────────────────────
    gate = reasoning.get("regime_gate", {})
    if isinstance(gate, dict):
        gate_regime = gate.get("regime", {})
        if isinstance(gate_regime, dict):
            f["daily_range_zscore"] = safe_float(gate_regime.get("range_zscore"))
            f["daily_velocity_zscore"] = safe_float(gate_regime.get("velocity_zscore"))
        else:
            f["daily_range_zscore"] = float("nan")
            f["daily_velocity_zscore"] = float("nan")
        f["gate_gated"] = 1 if gate.get("gated") else 0
    else:
        f["daily_range_zscore"] = float("nan")
        f["daily_velocity_zscore"] = float("nan")
        f["gate_gated"] = float("nan")

    # ── Tier 3: BTC 15m consensus ────────────────────────────────────
    consensus = reasoning.get("consensus", {})
    if isinstance(consensus, dict):
        f["consensus_score"] = safe_float(consensus.get("score"))
        f["consensus_agree"] = 1 if consensus.get("direction_agree") else 0
    else:
        f["consensus_score"] = float("nan")
        f["consensus_agree"] = float("nan")

    # ── Tier 3: Kalshi orderbook ─────────────────────────────────────
    kalshi_ob = reasoning.get("kalshi_orderbook", {})
    if isinstance(kalshi_ob, dict):
        f["kalshi_spread"] = safe_float(kalshi_ob.get("spread"))
        f["kalshi_bid"] = safe_float(kalshi_ob.get("bid"))
        f["kalshi_ask"] = safe_float(kalshi_ob.get("ask"))
        f["kalshi_volume"] = safe_float(kalshi_ob.get("volume"))
        f["kalshi_oi"] = safe_float(kalshi_ob.get("open_interest"))
    else:
        for k in ["kalshi_spread", "kalshi_bid", "kalshi_ask", "kalshi_volume", "kalshi_oi"]:
            f[k] = float("nan")

    # ── Tier 3: Bybit funding rate ──────────────────────────────────
    funding = reasoning.get("funding_rate", {})
    if isinstance(funding, dict):
        f["funding_rate"] = safe_float(funding.get("rate"))
    else:
        f["funding_rate"] = float("nan")

    # Bybit mark price
    f["mark_price"] = safe_float(reasoning.get("mark_price"))

    return f


# ── Database reading ──────────────────────────────────────────────────────

def read_pipeline(pipeline: dict) -> List[dict]:
    """Read all resolved predictions from a pipeline DB."""
    db_path = pipeline["db"]
    if not db_path.exists():
        print(f"  SKIP: {db_path.name} not found")
        return []

    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row

    rows = db.execute("""
        SELECT p.rowid as id, p.agent, p.estimate, p.confidence,
               p.predicted_at, p.market_id, p.conviction_score,
               p.regime, p.reasoning, p.edge,
               m.outcome, m.price_yes, m.resolved
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE m.resolved = 1 AND m.outcome IS NOT NULL
        ORDER BY p.predicted_at ASC
    """).fetchall()
    db.close()

    dataset = []
    for row in rows:
        row_dict = dict(row)
        try:
            reasoning = json.loads(row_dict.get("reasoning") or "{}")
        except (json.JSONDecodeError, TypeError):
            reasoning = {}

        features = extract_features(row_dict, reasoning, pipeline)

        # Label: did this prediction win?
        estimate = safe_float(row_dict.get("estimate"))
        outcome = row_dict.get("outcome")
        if outcome is None or not math.isfinite(estimate):
            continue

        predicted_up = estimate > 0.5
        actual_up = outcome == 1
        label = 1 if predicted_up == actual_up else 0

        # Also handle estimate == 0.5 (skip/abstain mapped to UP by convention)
        if estimate == 0.5:
            label = 1 if outcome == 1 else 0

        features["label"] = label
        features["predicted_at"] = row_dict.get("predicted_at", "")
        features["pipeline_name"] = pipeline["name"]
        features["prediction_id"] = row_dict.get("id")

        dataset.append(features)

    return dataset


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate Judge dataset from real predictions")
    parser.add_argument("--output", default="data/judge_dataset_real.csv",
                        help="Output CSV path")
    parser.add_argument("--pipelines", default="all",
                        help="Comma-separated pipeline names or 'all'")
    args = parser.parse_args()

    if args.pipelines == "all":
        selected = PIPELINES
    else:
        names = [n.strip() for n in args.pipelines.split(",")]
        selected = [p for p in PIPELINES if p["name"] in names]

    all_rows: List[dict] = []
    print(f"Generating Judge dataset from {len(selected)} pipelines...\n")

    for pipeline in selected:
        print(f"Reading {pipeline['name']} ({pipeline['db'].name})...")
        rows = read_pipeline(pipeline)
        if rows:
            wins = sum(1 for r in rows if r["label"] == 1)
            wr = wins / len(rows) * 100 if rows else 0
            print(f"  {len(rows)} resolved predictions, WR={wr:.1f}%")
        all_rows.extend(rows)

    if not all_rows:
        print("\nERROR: No data extracted from any pipeline.")
        sys.exit(1)

    # Sort by prediction time
    all_rows.sort(key=lambda r: r.get("predicted_at", ""))

    # Summary
    print(f"\n{'='*60}")
    print(f"Total rows: {len(all_rows)}")
    wins = sum(1 for r in all_rows if r["label"] == 1)
    losses = len(all_rows) - wins
    print(f"Class balance: {wins} wins ({wins/len(all_rows)*100:.1f}%) / "
          f"{losses} losses ({losses/len(all_rows)*100:.1f}%)")

    # Per-pipeline breakdown
    print(f"\nPer-pipeline:")
    pipeline_names = sorted(set(r["pipeline_name"] for r in all_rows))
    for pname in pipeline_names:
        p_rows = [r for r in all_rows if r["pipeline_name"] == pname]
        p_wins = sum(1 for r in p_rows if r["label"] == 1)
        p_wr = p_wins / len(p_rows) * 100 if p_rows else 0
        print(f"  {pname:<12} {len(p_rows):>6} rows  WR={p_wr:.1f}%")

    # Feature completeness
    sample = all_rows[0]
    feature_keys = [k for k in sorted(sample.keys())
                    if k not in {"label", "predicted_at", "pipeline_name", "prediction_id"}]
    nan_counts = {}
    for k in feature_keys:
        nan_count = sum(1 for r in all_rows
                        if not math.isfinite(safe_float(r.get(k))))
        nan_counts[k] = nan_count

    print(f"\nFeature completeness ({len(feature_keys)} features):")
    for k in sorted(nan_counts.keys(), key=lambda x: nan_counts[x]):
        pct = (1 - nan_counts[k] / len(all_rows)) * 100
        if pct < 100:
            print(f"  {k:<30} {pct:5.1f}% populated")

    # Write CSV
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Audit columns first, then features, then label
    audit_cols = ["predicted_at", "pipeline_name", "prediction_id"]
    fieldnames = audit_cols + feature_keys + ["label"]

    with output_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in all_rows:
            w.writerow(row)

    print(f"\n{'='*60}")
    print(f"Dataset written to {output_path}")
    print(f"  {len(all_rows)} rows, {len(fieldnames)} columns")


if __name__ == "__main__":
    main()
