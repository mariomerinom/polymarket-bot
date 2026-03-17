"""
V3 Stage 4 — Model Training & Calibration

XGBoost primary + Logistic Regression secondary.
Only trades when both models agree on direction.
Calibrated probabilities via isotonic regression.
"""

import math
import random
import statistics
import numpy as np
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression

from src.v3.features import compute_features, feature_names, features_to_row


class V3Model:
    """
    Walk-forward model with expanding window training.

    Uses XGBoost (primary) + LogReg (secondary) agreement.
    Only predicts when both agree on direction.
    """

    def __init__(self, retrain_every=50):
        self.xgb_model = None
        self.lr_model = None
        self.calibrator = None
        self.retrain_every = retrain_every
        self.train_X = []
        self.train_y = []
        self.markets_since_train = 0
        self.is_trained = False

    def add_training_sample(self, features, outcome):
        """Add a resolved market to training data."""
        row = features_to_row(features)
        self.train_X.append(row)
        self.train_y.append(outcome)
        self.markets_since_train += 1

    def should_retrain(self):
        """Check if we have enough new data to retrain."""
        return self.markets_since_train >= self.retrain_every and len(self.train_y) >= 100

    def train(self):
        """Train both models on accumulated data."""
        X = np.array(self.train_X)
        y = np.array(self.train_y)
        n = len(y)

        # Time-series split: 80% train, 15% calibration, 5% test
        train_end = int(n * 0.80)
        cal_end = int(n * 0.95)

        X_train, y_train = X[:train_end], y[:train_end]
        X_cal, y_cal = X[train_end:cal_end], y[train_end:cal_end]

        if len(y_train) < 50 or len(y_cal) < 10:
            return False

        # XGBoost
        self.xgb_model = xgb.XGBClassifier(
            max_depth=3,
            n_estimators=150,
            learning_rate=0.1,
            reg_lambda=2.0,  # L2 regularization
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=42,
            verbosity=0,
        )
        self.xgb_model.fit(X_train, y_train)

        # Logistic Regression
        self.lr_model = LogisticRegression(
            max_iter=1000,
            C=1.0,
            random_state=42,
        )
        self.lr_model.fit(X_train, y_train)

        # Calibrate XGBoost probabilities using isotonic regression
        xgb_cal_probs = self.xgb_model.predict_proba(X_cal)[:, 1]
        if len(set(y_cal)) >= 2:
            self.calibrator = IsotonicRegression(
                y_min=0.01, y_max=0.99, out_of_bounds="clip"
            )
            self.calibrator.fit(xgb_cal_probs, y_cal)
        else:
            self.calibrator = None

        self.markets_since_train = 0
        self.is_trained = True
        return True

    def predict(self, features):
        """
        Predict probability of UP.

        Returns: (calibrated_prob_up, should_trade)
        should_trade = True only when XGBoost and LogReg agree on direction.
        """
        if not self.is_trained:
            return 0.5, False

        row = np.array([features_to_row(features)])

        # XGBoost raw probability
        xgb_prob = self.xgb_model.predict_proba(row)[0, 1]

        # Calibrate
        if self.calibrator is not None:
            cal_prob = float(self.calibrator.predict([xgb_prob])[0])
        else:
            cal_prob = float(xgb_prob)

        # LogReg prediction
        lr_prob = float(self.lr_model.predict_proba(row)[0, 1])

        # Agreement check: both must predict same direction
        xgb_up = cal_prob > 0.5
        lr_up = lr_prob > 0.5
        agree = xgb_up == lr_up

        # Conviction check: calibrated probability must be decisive
        decisive = cal_prob <= 0.38 or cal_prob >= 0.62

        should_trade = agree and decisive

        return cal_prob, should_trade

    def get_brier(self, features, outcome):
        """Compute Brier score for a single prediction."""
        if not self.is_trained:
            return 0.25
        prob, _ = self.predict(features)
        return (prob - outcome) ** 2


def run_ml_backtest(markets, warm_up=500, retrain_every=50, bet_size=75, min_edge=0.05):
    """
    Run walk-forward ML backtest.

    1. Accumulate warm_up markets as training data
    2. Train model
    3. For each subsequent market: predict, decide, accumulate, retrain periodically
    """
    from src.btc_data import _compute_summary
    from src.v3.backtest import candles_to_btc_format, simulate_fill, ROUND_TRIP_FEE
    from src.v3.regime import compute_regime

    model = V3Model(retrain_every=retrain_every)
    trades = []
    skipped = 0
    train_count = 0

    for i, market in enumerate(markets):
        # Compute features
        context_formatted = candles_to_btc_format(market["context_candles"])
        btc_summary = _compute_summary(context_formatted)
        regime = compute_regime(btc_summary)

        fake_book = {
            "midpoint": market["implied_price_yes"],
            "spread_pct": 0.02,
            "depth_imbalance": 0.0,
            "bid_depth_5pct": 2000,
            "ask_depth_5pct": 2000,
        }
        market_info = {
            "end_date": datetime.fromtimestamp(
                market["timestamp"], tz=timezone.utc
            ).isoformat(),
            "price_yes": market["implied_price_yes"],
        }

        features = compute_features(btc_summary, fake_book, market_info, regime)

        # Warm-up phase: just collect training data
        if i < warm_up:
            model.add_training_sample(features, market["outcome"])
            if i == warm_up - 1:
                print(f"  Training initial model on {warm_up} markets...")
                model.train()
                train_count += 1
            continue

        # Predict
        prob_up, should_trade = model.predict(features)

        if should_trade:
            midpoint = market["implied_price_yes"]
            edge = abs(prob_up - midpoint)
            slippage = random.uniform(0.01, 0.03)
            net_edge = edge - ROUND_TRIP_FEE - slippage

            if net_edge >= min_edge:
                predicted_up = prob_up > 0.5
                actual_up = market["outcome"] == 1
                correct = predicted_up == actual_up
                pnl = bet_size * 0.96 if correct else -bet_size

                trades.append({
                    "index": market["index"],
                    "timestamp": market["timestamp"],
                    "prob_up": prob_up,
                    "midpoint": midpoint,
                    "edge": edge,
                    "net_edge": net_edge,
                    "predicted_up": predicted_up,
                    "actual_up": actual_up,
                    "correct": correct,
                    "pnl": pnl,
                    "regime": regime["label"],
                })
            else:
                skipped += 1
        else:
            skipped += 1

        # Add to training data (after prediction, no look-ahead)
        model.add_training_sample(features, market["outcome"])

        # Retrain periodically
        if model.should_retrain():
            model.train()
            train_count += 1

    # Summary
    from src.v3.backtest import _summarize_trades
    results = _summarize_trades(trades, skipped, "XGBoost+LogReg", len(markets) - warm_up)
    results["retrains"] = train_count

    return results, model


# ── Calibration Validation ──────────────────────────────────────────────

def validate_calibration(model, markets, start_idx):
    """
    Check calibration: for each probability bin, does actual win rate match?
    Returns dict of bin -> {predicted_avg, actual_avg, count, pass}
    """
    from src.btc_data import _compute_summary
    from src.v3.backtest import candles_to_btc_format
    from src.v3.regime import compute_regime

    bins = defaultdict(lambda: {"preds": [], "actuals": []})

    for market in markets[start_idx:]:
        context_formatted = candles_to_btc_format(market["context_candles"])
        btc_summary = _compute_summary(context_formatted)
        regime = compute_regime(btc_summary)
        fake_book = {
            "midpoint": market["implied_price_yes"],
            "spread_pct": 0.02, "depth_imbalance": 0.0,
            "bid_depth_5pct": 2000, "ask_depth_5pct": 2000,
        }
        market_info = {
            "end_date": datetime.fromtimestamp(
                market["timestamp"], tz=timezone.utc
            ).isoformat(),
            "price_yes": market["implied_price_yes"],
        }
        features = compute_features(btc_summary, fake_book, market_info, regime)
        prob, _ = model.predict(features)

        # Bin by predicted probability
        bin_key = f"{int(prob * 10) / 10:.1f}-{int(prob * 10) / 10 + 0.1:.1f}"
        bins[bin_key]["preds"].append(prob)
        bins[bin_key]["actuals"].append(market["outcome"])

    results = {}
    for bin_key, data in sorted(bins.items()):
        if len(data["preds"]) < 5:
            continue
        pred_avg = sum(data["preds"]) / len(data["preds"])
        actual_avg = sum(data["actuals"]) / len(data["actuals"])
        gap = abs(pred_avg - actual_avg)
        results[bin_key] = {
            "predicted_avg": round(pred_avg, 3),
            "actual_avg": round(actual_avg, 3),
            "count": len(data["preds"]),
            "gap": round(gap, 3),
            "pass": gap <= 0.10,  # within ±10pp
        }

    return results


# ── CLI ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    from src.v3.backtest import (
        download_historical_candles, build_synthetic_markets,
        run_walkforward, contrarian_rule_predict, print_results,
    )

    parser = argparse.ArgumentParser(description="V3 Model Training & Backtest")
    parser.add_argument("--days", type=int, default=14, help="Days of history")
    parser.add_argument("--warm-up", type=int, default=500, help="Warm-up markets")
    parser.add_argument("--retrain-every", type=int, default=50, help="Retrain frequency")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    print("V3 Stage 4: Model Training & Walk-Forward Backtest\n")

    # Download data
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=args.days)
    print(f"Downloading {args.days} days of BTC candles...")
    candles = download_historical_candles(start_date, end_date)

    markets = build_synthetic_markets(candles, lookback=20)
    print(f"Markets: {len(markets)} (warm-up={args.warm_up})\n")

    # Run contrarian baseline
    print("--- Contrarian Rule Baseline ---")
    cr_results = run_walkforward(
        markets, contrarian_rule_predict, name="Contrarian Rule",
        warm_up=args.warm_up,
    )
    print_results(cr_results)

    # Run ML model
    print("--- XGBoost + LogReg (V3.2) ---")
    ml_results, model = run_ml_backtest(
        markets, warm_up=args.warm_up,
        retrain_every=args.retrain_every,
    )
    ml_results["name"] = "XGBoost+LogReg"
    print_results(ml_results)
    print(f"  Retrains: {ml_results['retrains']}")

    # Comparison
    print(f"\n{'='*60}")
    print(f"  COMPARISON: ML vs Contrarian Rule Baseline")
    print(f"{'='*60}")
    print(f"  {'Metric':<25s} {'Contrarian':>12s} {'ML':>12s} {'Delta':>10s}")
    print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*10}")

    for metric, fmt in [("win_rate", ".1f"), ("roi", ".1f"), ("pnl", ",.0f"),
                         ("trades", "d"), ("sharpe", ".2f"), ("max_drawdown", ",.0f")]:
        cv = cr_results[metric]
        mv = ml_results[metric]
        if fmt == "d":
            print(f"  {metric:<25s} {cv:>12d} {mv:>12d} {mv-cv:>+10d}")
        elif fmt == ",.0f":
            print(f"  {metric:<25s} ${cv:>11,.0f} ${mv:>11,.0f} ${mv-cv:>+9,.0f}")
        else:
            print(f"  {metric:<25s} {cv:>11{fmt}}% {mv:>11{fmt}}% {mv-cv:>+9{fmt}}pp")

    # Decision gate
    wr_delta = ml_results["win_rate"] - cr_results["win_rate"]
    roi_delta = ml_results["roi"] - cr_results["roi"]
    gate_pass = wr_delta >= 3 or roi_delta >= 5

    print(f"\n  Decision Gate (Stage 3.5):")
    print(f"    Win rate delta: {wr_delta:+.1f}pp (need ≥3pp)")
    print(f"    ROI delta:      {roi_delta:+.1f}pp (need ≥5pp)")
    print(f"    Gate: {'PASS ✓' if gate_pass else 'FAIL ✗'}")

    # Calibration check
    if model.is_trained:
        print(f"\n--- Calibration Validation ---")
        cal = validate_calibration(model, markets, args.warm_up)
        all_pass = True
        for bin_key, data in sorted(cal.items()):
            status = "OK" if data["pass"] else "FAIL"
            if not data["pass"]:
                all_pass = False
            print(f"  {bin_key}: predicted={data['predicted_avg']:.3f} "
                  f"actual={data['actual_avg']:.3f} "
                  f"gap={data['gap']:.3f} n={data['count']} [{status}]")
        print(f"\n  Calibration gate: {'PASS' if all_pass else 'FAIL — retune before Kelly'}")
