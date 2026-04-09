"""
train_judge.py — Walk-forward XGBoost training for the ML Judge meta-classifier.

Supports two dataset formats:
  - Synthetic (from generate_judge_dataset.py): monthly folds, feature_ts column
  - Real (from generate_judge_dataset_real.py): daily folds, predicted_at column

Auto-detects format from column names.

Decision gates:
  - Mean test-fold AUC < 0.55 → model learns nothing beyond rules. Do not ship.
  - Accepted-bet WR < baseline WR → model is anticorrelated. Do not ship.
  - Accepted-bet WR > baseline WR by ≥ 3pp AND volume retention > 50% → ship to shadow.

Usage:
    python3 tools/train_judge.py --dataset data/judge_dataset_real.csv
    python3 tools/train_judge.py --dataset data/judge_dataset.csv --threshold 0.55
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

try:
    import xgboost as xgb
except ImportError:
    print("ERROR: xgboost not installed. Run: pip install xgboost>=2.0.0")
    sys.exit(1)

try:
    from sklearn.metrics import (
        roc_auc_score,
        accuracy_score,
        brier_score_loss,
        log_loss,
    )
    from sklearn.calibration import calibration_curve
except ImportError:
    print("ERROR: scikit-learn not installed. Run: pip install scikit-learn>=1.3.0")
    sys.exit(1)

try:
    import joblib
except ImportError:
    print("ERROR: joblib not installed. Run: pip install joblib")
    sys.exit(1)


ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
RESULTS_DIR = ROOT / "docs" / "research"


# ── Audit columns by dataset format ──────────────────────────────────────

AUDIT_COLS_SYNTHETIC = {"feature_ts", "label_ts", "source", "direction", "streak", "label"}
AUDIT_COLS_REAL = {"predicted_at", "pipeline_name", "prediction_id", "label"}


def load_dataset(path: Path) -> Tuple[List[dict], List[str], str]:
    """Load CSV dataset. Returns (rows, feature_cols, format).

    format is 'synthetic' or 'real' based on column detection.
    """
    rows = []
    with path.open() as f:
        reader = csv.DictReader(f)
        headers = set(reader.fieldnames or [])
        for row in reader:
            parsed = {}
            for k, v in row.items():
                if v in ("", "nan", "NaN", "None"):
                    parsed[k] = float("nan")
                else:
                    try:
                        parsed[k] = float(v)
                    except ValueError:
                        parsed[k] = v  # keep strings
            rows.append(parsed)

    # Auto-detect format
    if "predicted_at" in headers:
        fmt = "real"
        audit = AUDIT_COLS_REAL
    else:
        fmt = "synthetic"
        audit = AUDIT_COLS_SYNTHETIC

    feature_cols = sorted(headers - audit)
    return rows, feature_cols, fmt


def rows_to_arrays(rows: List[dict], feature_cols: List[str]) -> Tuple[np.ndarray, np.ndarray]:
    """Convert rows to X (features) and y (labels) numpy arrays."""
    X = np.array([[r.get(c, float("nan")) for c in feature_cols] for r in rows], dtype=np.float32)
    y = np.array([r["label"] for r in rows], dtype=np.float32)
    return X, y


# ── Timestamp helpers ─────────────────────────────────────────────────────

def row_date(row: dict, fmt: str) -> str:
    """Extract YYYY-MM-DD date string from a row."""
    if fmt == "real":
        pa = str(row.get("predicted_at", ""))
        return pa[:10]  # "2026-04-09T..." → "2026-04-09"
    else:
        ts = row.get("feature_ts", 0)
        dt = datetime.fromtimestamp(float(ts) / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")


def row_month(row: dict, fmt: str) -> str:
    """Extract YYYY-MM from a row."""
    return row_date(row, fmt)[:7]


# ── Walk-forward folds ────────────────────────────────────────────────────

FOLD_TEST_MONTHS_SYNTHETIC = [
    "2025-04", "2025-07", "2025-10",
    "2026-01", "2026-02", "2026-03", "2026-04",
]


def generate_daily_folds(rows: List[dict], fmt: str, min_train: int = 500,
                         test_days: int = 2) -> List[Tuple[str, str]]:
    """Generate expanding-window daily folds for short-history datasets.

    Returns list of (fold_label, test_start_date) tuples.
    Uses 2-day test windows with expanding training.
    """
    dates = sorted(set(row_date(r, fmt) for r in rows))
    if len(dates) < 5:
        return []

    folds = []
    # Start testing after we have enough training data
    for i in range(len(dates) - test_days):
        test_start = dates[i + 1]
        test_end = dates[min(i + test_days, len(dates) - 1)]
        train_rows_count = sum(1 for r in rows if row_date(r, fmt) <= dates[i])
        if train_rows_count >= min_train:
            folds.append((f"{test_start}", test_start))

    # Subsample to ~7-10 folds (every N-th fold)
    if len(folds) > 10:
        step = len(folds) // 8
        folds = folds[::step]
        # Always include the last fold
        last_fold = (dates[-1], dates[-1])
        if folds[-1] != last_fold:
            folds.append(last_fold)

    return folds


def split_fold_daily(rows: List[dict], test_date: str, fmt: str,
                     test_days: int = 2) -> Tuple[List[dict], List[dict]]:
    """Split for daily folds: train on all before test_date, test on test_date + next day."""
    from datetime import timedelta
    test_start = datetime.strptime(test_date, "%Y-%m-%d").date()
    test_end = test_start + timedelta(days=test_days - 1)

    train = [r for r in rows if row_date(r, fmt) < test_date]
    test = [r for r in rows
            if test_start.isoformat() <= row_date(r, fmt) <= test_end.isoformat()]
    return train, test


def split_fold_monthly(rows: List[dict], test_month: str, fmt: str) -> Tuple[List[dict], List[dict]]:
    """Split for monthly folds."""
    train = [r for r in rows if row_month(r, fmt) < test_month]
    test = [r for r in rows if row_month(r, fmt) == test_month]
    return train, test


# ── Training ──────────────────────────────────────────────────────────────

def train_fold(
    train_rows: List[dict],
    test_rows: List[dict],
    feature_cols: List[str],
    threshold: float = 0.55,
) -> dict:
    """Train XGBoost on train, evaluate on test. Returns metrics dict."""
    X_train, y_train = rows_to_arrays(train_rows, feature_cols)
    X_test, y_test = rows_to_arrays(test_rows, feature_cols)

    # Class balance
    pos = y_train.sum()
    neg = len(y_train) - pos
    spw = neg / pos if pos > 0 else 1.0

    # Holdout for early stopping (last 15% of train)
    split_idx = int(len(X_train) * 0.85)
    X_tr, X_val = X_train[:split_idx], X_train[split_idx:]
    y_tr, y_val = y_train[:split_idx], y_train[split_idx:]

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        min_child_weight=10,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=spw,
        eval_metric="logloss",
        early_stopping_rounds=20,
        verbosity=0,
        random_state=42,
    )

    model.fit(
        X_tr, y_tr,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    # Predictions
    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)

    # Metrics
    auc = roc_auc_score(y_test, y_prob) if len(set(y_test)) > 1 else 0.5
    acc = accuracy_score(y_test, y_pred)
    brier = brier_score_loss(y_test, y_prob)
    ll = log_loss(y_test, y_prob) if len(set(y_test)) > 1 else 999.0

    # Baseline WR (all bets)
    baseline_wr = y_test.mean()

    # Accepted / rejected split
    accepted_mask = y_prob >= threshold
    rejected_mask = ~accepted_mask
    accepted_wr = y_test[accepted_mask].mean() if accepted_mask.sum() > 0 else float("nan")
    rejected_wr = y_test[rejected_mask].mean() if rejected_mask.sum() > 0 else float("nan")
    accepted_n = int(accepted_mask.sum())
    rejected_n = int(rejected_mask.sum())
    total_n = len(y_test)
    volume_retention = accepted_n / total_n if total_n > 0 else 0.0

    # Calibration (5 bins to handle small test sets)
    n_bins = min(5, max(2, max(1, accepted_n // 10)))
    try:
        frac_pos, mean_pred = calibration_curve(y_test, y_prob, n_bins=n_bins, strategy="quantile")
        calibration = list(zip(mean_pred.tolist(), frac_pos.tolist()))
    except Exception:
        calibration = []

    return {
        "model": model,
        "auc": round(auc, 4),
        "accuracy": round(acc, 4),
        "brier": round(brier, 4),
        "log_loss": round(ll, 4),
        "baseline_wr": round(baseline_wr, 4),
        "accepted_wr": round(accepted_wr, 4) if not math.isnan(accepted_wr) else None,
        "rejected_wr": round(rejected_wr, 4) if not math.isnan(rejected_wr) else None,
        "accepted_n": accepted_n,
        "rejected_n": rejected_n,
        "total_n": total_n,
        "volume_retention": round(volume_retention, 4),
        "calibration": calibration,
        "train_size": len(X_train),
        "best_iteration": model.best_iteration if hasattr(model, "best_iteration") else None,
        "y_prob": y_prob,
        "y_test": y_test,
        "X_test": X_test,
    }


# ── SHAP ──────────────────────────────────────────────────────────────────

def compute_shap(model, X_test: np.ndarray, feature_cols: List[str], top_n: int = 15) -> List[Tuple[str, float]]:
    """Compute SHAP feature importance. Returns [(feature_name, mean_abs_shap), ...]."""
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_test)
        mean_abs = np.abs(shap_values).mean(axis=0)
        pairs = list(zip(feature_cols, mean_abs.tolist()))
        pairs.sort(key=lambda x: x[1], reverse=True)
        return pairs[:top_n]
    except ImportError:
        print("  WARN: shap not installed, skipping SHAP analysis")
        return []
    except Exception as e:
        print(f"  WARN: SHAP failed: {e}")
        return []


# ── Results report ────────────────────────────────────────────────────────

def generate_report(
    fold_results: List[dict],
    fold_labels: List[str],
    shap_results: List[Tuple[str, float]],
    threshold: float,
    ship_decision: str,
    feature_cols: List[str],
    dataset_info: str = "",
) -> str:
    """Generate markdown report."""
    lines = [
        "# ML Judge Walk-Forward Results",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Dataset:** {dataset_info}",
        f"**Threshold:** P >= {threshold} -> accept bet",
        f"**Folds:** {len(fold_results)} test periods",
        f"**Features:** {len(feature_cols)}",
        "",
        "## Per-Fold Metrics",
        "",
        "| Fold | Test Period | Train N | Test N | AUC | Acc | Brier | Baseline WR | Accepted WR | Rejected WR | Accepted N | Vol Retention |",
        "|------|-----------|---------|--------|-----|-----|-------|-------------|-------------|-------------|------------|---------------|",
    ]

    aucs = []
    accepted_wrs = []
    baseline_wrs = []
    vol_retentions = []

    for i, (result, label) in enumerate(zip(fold_results, fold_labels)):
        aucs.append(result["auc"])
        if result["accepted_wr"] is not None:
            accepted_wrs.append(result["accepted_wr"])
        baseline_wrs.append(result["baseline_wr"])
        vol_retentions.append(result["volume_retention"])

        wr_str = f"{result['accepted_wr']:.1%}" if result["accepted_wr"] is not None else "N/A"
        rej_str = f"{result['rejected_wr']:.1%}" if result["rejected_wr"] is not None else "N/A"

        lines.append(
            f"| {i+1} | {label} | {result['train_size']:,} | {result['total_n']:,} "
            f"| {result['auc']:.3f} | {result['accuracy']:.3f} | {result['brier']:.3f} "
            f"| {result['baseline_wr']:.1%} | {wr_str} | {rej_str} "
            f"| {result['accepted_n']:,} | {result['volume_retention']:.1%} |"
        )

    mean_auc = np.mean(aucs) if aucs else 0
    mean_accepted_wr = np.mean(accepted_wrs) if accepted_wrs else 0
    mean_baseline_wr = np.mean(baseline_wrs) if baseline_wrs else 0
    mean_vol = np.mean(vol_retentions) if vol_retentions else 0

    lines.extend([
        "",
        "## Summary Statistics",
        "",
        f"- **Mean AUC:** {mean_auc:.4f}",
        f"- **Mean Baseline WR:** {mean_baseline_wr:.1%}",
        f"- **Mean Accepted WR:** {mean_accepted_wr:.1%}",
        f"- **WR Improvement:** {(mean_accepted_wr - mean_baseline_wr)*100:+.1f}pp",
        f"- **Mean Volume Retention:** {mean_vol:.1%}",
        "",
    ])

    # SHAP
    if shap_results:
        lines.extend([
            "## Top Features (SHAP -- Final Fold)",
            "",
            "| Rank | Feature | Mean |SHAP| |",
            "|------|---------|-------------|",
        ])
        for rank, (feat, val) in enumerate(shap_results, 1):
            lines.append(f"| {rank} | `{feat}` | {val:.4f} |")
        lines.append("")

    # Decision
    lines.extend([
        "## Decision Gate",
        "",
        f"- Mean AUC {'PASS' if mean_auc >= 0.55 else 'FAIL'} >= 0.55: **{mean_auc:.4f}**",
        f"- Accepted WR > Baseline {'PASS' if mean_accepted_wr > mean_baseline_wr else 'FAIL'}: "
        f"**{mean_accepted_wr:.1%}** vs **{mean_baseline_wr:.1%}**",
        f"- WR improvement >= 3pp {'PASS' if (mean_accepted_wr - mean_baseline_wr) >= 0.03 else 'FAIL'}: "
        f"**{(mean_accepted_wr - mean_baseline_wr)*100:+.1f}pp**",
        f"- Volume retention > 50% {'PASS' if mean_vol > 0.5 else 'FAIL'}: **{mean_vol:.1%}**",
        "",
        f"### **{ship_decision}**",
        "",
        "## Calibration (Final Fold)",
        "",
    ])

    last = fold_results[-1]
    if last["calibration"]:
        lines.extend([
            "| Predicted P | Observed WR |",
            "|------------|-------------|",
        ])
        for pred, obs in last["calibration"]:
            lines.append(f"| {pred:.3f} | {obs:.3f} |")
    else:
        lines.append("_Calibration data not available._")

    lines.append("")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train ML Judge via walk-forward validation")
    parser.add_argument("--dataset", default="data/judge_dataset_real.csv",
                        help="Path to judge dataset CSV")
    parser.add_argument("--threshold", type=float, default=0.55,
                        help="Acceptance threshold (default 0.55)")
    parser.add_argument("--output-model", default="models/judge_btc_5m.joblib",
                        help="Path for final model")
    parser.add_argument("--output-report", default="docs/research/judge_walkforward_results.md",
                        help="Path for results report")
    args = parser.parse_args()

    dataset_path = ROOT / args.dataset
    if not dataset_path.exists():
        print(f"ERROR: Dataset not found at {dataset_path}")
        print("Run: python3 tools/generate_judge_dataset_real.py")
        sys.exit(1)

    print(f"Loading dataset from {dataset_path}...")
    rows, feature_cols, fmt = load_dataset(dataset_path)
    print(f"  {len(rows)} rows, {len(feature_cols)} features, format={fmt}")
    print(f"  Features: {', '.join(feature_cols[:10])}{'...' if len(feature_cols) > 10 else ''}")

    # ── Determine fold strategy ──────────────────────────────────────────
    if fmt == "real":
        # Daily folds for short-history real data
        dates = sorted(set(row_date(r, fmt) for r in rows))
        print(f"  Dates in data: {dates[0]} -> {dates[-1]} ({len(dates)} days)")

        folds = generate_daily_folds(rows, fmt, min_train=500, test_days=2)
        if not folds:
            print("  ERROR: not enough data for daily walk-forward folds")
            sys.exit(1)

        print(f"\n  Walk-forward folds ({len(folds)} daily):")
        for label, _ in folds:
            print(f"    test: {label}")

        # Run folds
        fold_results = []
        fold_labels = []
        last_shap = []

        for i, (label, test_date) in enumerate(folds):
            print(f"\n{'='*60}")
            print(f"Fold {i+1}/{len(folds)}: test = {label}")

            train_rows, test_rows = split_fold_daily(rows, test_date, fmt, test_days=2)
            if not test_rows:
                print(f"  SKIP: no test data for {label}")
                continue
            if len(train_rows) < 100:
                print(f"  SKIP: only {len(train_rows)} training rows (need >= 100)")
                continue

            print(f"  Train: {len(train_rows)} rows | Test: {len(test_rows)} rows")

            # Verify no leakage
            max_train_date = max(row_date(r, fmt) for r in train_rows)
            min_test_date = min(row_date(r, fmt) for r in test_rows)
            assert max_train_date < min_test_date, \
                f"LEAKAGE: train max date {max_train_date} >= test min {min_test_date}"

            result = train_fold(train_rows, test_rows, feature_cols, args.threshold)
            fold_results.append(result)
            fold_labels.append(label)

            print(f"  AUC: {result['auc']:.4f} | Acc: {result['accuracy']:.4f} | Brier: {result['brier']:.4f}")
            print(f"  Baseline WR: {result['baseline_wr']:.1%}")
            if result["accepted_wr"] is not None:
                print(f"  Accepted WR (P>={args.threshold}): {result['accepted_wr']:.1%} "
                      f"({result['accepted_n']} bets, {result['volume_retention']:.0%} retention)")
            if result["rejected_wr"] is not None:
                print(f"  Rejected WR (P<{args.threshold}): {result['rejected_wr']:.1%} "
                      f"({result['rejected_n']} bets)")

            # SHAP on last fold
            if i == len(folds) - 1:
                print("  Computing SHAP values...")
                last_shap = compute_shap(result["model"], result["X_test"], feature_cols)
                if last_shap:
                    print("  Top 15 features by mean |SHAP|:")
                    for rank, (feat, val) in enumerate(last_shap, 1):
                        print(f"    {rank:2d}. {feat:30s} {val:.4f}")

        dataset_info = f"Real predictions ({len(rows)} rows, {len(dates)} days, {fmt})"

    else:
        # Monthly folds for synthetic candle data
        months_in_data = sorted(set(row_month(r, fmt) for r in rows))
        print(f"  Months in data: {months_in_data[0]} -> {months_in_data[-1]}")

        available_folds = [m for m in FOLD_TEST_MONTHS_SYNTHETIC if m in months_in_data]
        if not available_folds:
            if len(months_in_data) < 3:
                print("  ERROR: need at least 3 months of data for walk-forward")
                sys.exit(1)
            available_folds = months_in_data[-min(7, len(months_in_data) - 2):]

        print(f"\n  Walk-forward folds: {available_folds}")

        fold_results = []
        fold_labels = available_folds
        last_shap = []

        for i, test_month in enumerate(available_folds):
            print(f"\n{'='*60}")
            print(f"Fold {i+1}/{len(available_folds)}: test month = {test_month}")

            train_rows, test_rows = split_fold_monthly(rows, test_month, fmt)
            if not test_rows:
                print(f"  SKIP: no test data for {test_month}")
                continue
            if len(train_rows) < 100:
                print(f"  SKIP: only {len(train_rows)} training rows (need >= 100)")
                continue

            print(f"  Train: {len(train_rows)} rows | Test: {len(test_rows)} rows")

            # Verify no leakage
            max_train = max(row_date(r, fmt) for r in train_rows)
            min_test = min(row_date(r, fmt) for r in test_rows)
            assert max_train < min_test, f"LEAKAGE: {max_train} >= {min_test}"

            result = train_fold(train_rows, test_rows, feature_cols, args.threshold)
            fold_results.append(result)

            print(f"  AUC: {result['auc']:.4f} | Acc: {result['accuracy']:.4f} | Brier: {result['brier']:.4f}")
            print(f"  Baseline WR: {result['baseline_wr']:.1%}")
            if result["accepted_wr"] is not None:
                print(f"  Accepted WR (P>={args.threshold}): {result['accepted_wr']:.1%} "
                      f"({result['accepted_n']} bets, {result['volume_retention']:.0%} retention)")
            if result["rejected_wr"] is not None:
                print(f"  Rejected WR (P<{args.threshold}): {result['rejected_wr']:.1%} "
                      f"({result['rejected_n']} bets)")

            if i == len(available_folds) - 1:
                print("  Computing SHAP values...")
                last_shap = compute_shap(result["model"], result["X_test"], feature_cols)
                if last_shap:
                    print("  Top 15 features by mean |SHAP|:")
                    for rank, (feat, val) in enumerate(last_shap, 1):
                        print(f"    {rank:2d}. {feat:30s} {val:.4f}")

        fold_labels = available_folds[:len(fold_results)]
        dataset_info = f"Synthetic candles ({len(rows)} rows, {len(months_in_data)} months, {fmt})"

    if not fold_results:
        print("\nERROR: No folds produced results.")
        sys.exit(1)

    # ── Decision gate ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("DECISION GATE")

    mean_auc = np.mean([r["auc"] for r in fold_results])
    accepted_wrs = [r["accepted_wr"] for r in fold_results if r["accepted_wr"] is not None]
    mean_accepted = np.mean(accepted_wrs) if accepted_wrs else 0
    mean_baseline = np.mean([r["baseline_wr"] for r in fold_results])
    mean_vol = np.mean([r["volume_retention"] for r in fold_results])
    wr_improvement = mean_accepted - mean_baseline

    auc_pass = mean_auc >= 0.55
    wr_pass = mean_accepted > mean_baseline
    wr_3pp = wr_improvement >= 0.03
    vol_pass = mean_vol > 0.5

    print(f"  Mean AUC:            {mean_auc:.4f}  {'PASS' if auc_pass else 'FAIL'}")
    print(f"  Mean Accepted WR:    {mean_accepted:.1%}  (baseline: {mean_baseline:.1%})")
    print(f"  WR improvement:      {wr_improvement*100:+.1f}pp  {'PASS' if wr_3pp else 'FAIL'}")
    print(f"  Volume retention:    {mean_vol:.1%}  {'PASS' if vol_pass else 'FAIL'}")

    if auc_pass and wr_pass and wr_3pp and vol_pass:
        ship_decision = "SHIP TO SHADOW — All gates pass"
    elif auc_pass and wr_pass:
        ship_decision = "MARGINAL — AUC and WR pass but improvement < 3pp or volume too low"
    elif not auc_pass:
        ship_decision = "DO NOT SHIP — AUC < 0.55, model learns nothing beyond rules"
    elif not wr_pass:
        ship_decision = "DO NOT SHIP — Accepted WR < baseline, model is anticorrelated"
    else:
        ship_decision = "DO NOT SHIP — Gates failed"

    print(f"\n  >>> {ship_decision}")

    # ── Train final model on full data ──────────────────────────────────────
    print(f"\n{'='*60}")
    print("Training final model on full dataset...")

    X_all, y_all = rows_to_arrays(rows, feature_cols)
    pos = y_all.sum()
    neg = len(y_all) - pos
    spw = neg / pos if pos > 0 else 1.0

    # 85/15 split for early stopping
    split_idx = int(len(X_all) * 0.85)
    X_tr, X_val = X_all[:split_idx], X_all[split_idx:]
    y_tr, y_val = y_all[:split_idx], y_all[split_idx:]

    final_model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        min_child_weight=10,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=spw,
        eval_metric="logloss",
        early_stopping_rounds=20,
        verbosity=0,
        random_state=42,
    )
    final_model.fit(
        X_tr, y_tr,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    # Save model + metadata
    model_path = ROOT / args.output_model
    model_path.parent.mkdir(parents=True, exist_ok=True)

    model_artifact = {
        "model": final_model,
        "feature_cols": feature_cols,
        "threshold": args.threshold,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset_rows": len(rows),
        "dataset_format": fmt,
        "n_features": len(feature_cols),
        "ship_decision": ship_decision,
    }
    joblib.dump(model_artifact, model_path)
    print(f"  Saved model -> {model_path}")

    # ── Generate report ─────────────────────────────────────────────────────
    report = generate_report(
        fold_results=fold_results,
        fold_labels=fold_labels,
        shap_results=last_shap,
        threshold=args.threshold,
        ship_decision=ship_decision,
        feature_cols=feature_cols,
        dataset_info=dataset_info,
    )

    report_path = ROOT / args.output_report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)
    print(f"  Saved report -> {report_path}")

    print(f"\n{'='*60}")
    print("Done.")


if __name__ == "__main__":
    main()
