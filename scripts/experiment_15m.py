"""
experiment_15m.py — Karpathy-style auto-research for 15m momentum signal.

Systematically tests improvements against 2,754 resolved 15m markets.
Each experiment runs 10 chronological windows for variance estimation.

Usage:
    python3 scripts/experiment_15m.py
"""

import sqlite3
import json
import math
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "data" / "backtest.db"
RESULTS_PATH = Path(__file__).parent.parent / "docs" / "experiment_results_15m.md"

# Conviction → bet size (match live pipeline)
CONVICTION_BETS = {0: 0, 1: 0, 2: 0, 3: 75, 4: 200, 5: 300}


# ── Signal Variants ──────────────────────────────────────────────────

def baseline_signal(outcomes, volumes, prices, lookback=20, **kwargs):
    """V4 baseline: streak>=2, autocorr regime gate, native exhaustion."""
    min_streak = kwargs.get("min_streak", 2)
    autocorr_threshold = kwargs.get("autocorr_threshold", -0.20)

    if len(outcomes) < lookback:
        return {"should_trade": False, "reason": "insufficient", "conviction": 0}

    recent = outcomes[-lookback:]
    regime = _regime(recent, autocorr_threshold)

    if regime["is_mean_reverting"]:
        return {"should_trade": False, "reason": "regime_skip", "conviction": 0,
                "regime": regime["label"]}

    signal = _momentum(recent, volumes[-lookback:], prices[-lookback:], min_streak)
    signal["regime"] = regime["label"]
    return signal


def exp_no_regime_gate(outcomes, volumes, prices, lookback=20, **kwargs):
    """Experiment: Remove regime gate entirely — always check momentum."""
    min_streak = kwargs.get("min_streak", 2)

    if len(outcomes) < lookback:
        return {"should_trade": False, "reason": "insufficient", "conviction": 0}

    recent = outcomes[-lookback:]
    regime = _regime(recent, -0.20)
    signal = _momentum(recent, volumes[-lookback:], prices[-lookback:], min_streak)
    signal["regime"] = regime["label"]
    return signal


def exp_strict_regime(outcomes, volumes, prices, lookback=20, **kwargs):
    """Experiment: Stricter regime gate (autocorr < -0.10 → skip)."""
    min_streak = kwargs.get("min_streak", 2)

    if len(outcomes) < lookback:
        return {"should_trade": False, "reason": "insufficient", "conviction": 0}

    recent = outcomes[-lookback:]
    regime = _regime(recent, -0.10)  # Stricter

    if regime["is_mean_reverting"]:
        return {"should_trade": False, "reason": "regime_skip", "conviction": 0,
                "regime": regime["label"]}

    signal = _momentum(recent, volumes[-lookback:], prices[-lookback:], min_streak)
    signal["regime"] = regime["label"]
    return signal


def exp_min_streak_3(outcomes, volumes, prices, lookback=20, **kwargs):
    """Experiment: Require streak>=3 instead of 2 (more selective)."""
    autocorr_threshold = kwargs.get("autocorr_threshold", -0.20)

    if len(outcomes) < lookback:
        return {"should_trade": False, "reason": "insufficient", "conviction": 0}

    recent = outcomes[-lookback:]
    regime = _regime(recent, autocorr_threshold)

    if regime["is_mean_reverting"]:
        return {"should_trade": False, "reason": "regime_skip", "conviction": 0,
                "regime": regime["label"]}

    signal = _momentum(recent, volumes[-lookback:], prices[-lookback:], min_streak=3)
    signal["regime"] = regime["label"]
    return signal


def exp_min_streak_4(outcomes, volumes, prices, lookback=20, **kwargs):
    """Experiment: Require streak>=4 (very selective)."""
    if len(outcomes) < lookback:
        return {"should_trade": False, "reason": "insufficient", "conviction": 0}

    recent = outcomes[-lookback:]
    regime = _regime(recent, -0.20)

    if regime["is_mean_reverting"]:
        return {"should_trade": False, "reason": "regime_skip", "conviction": 0,
                "regime": regime["label"]}

    signal = _momentum(recent, volumes[-lookback:], prices[-lookback:], min_streak=4)
    signal["regime"] = regime["label"]
    return signal


def exp_lookback_10(outcomes, volumes, prices, lookback=20, **kwargs):
    """Experiment: Shorter lookback (10 instead of 20)."""
    return baseline_signal(outcomes, volumes, prices, lookback=10, **kwargs)


def exp_lookback_30(outcomes, volumes, prices, lookback=20, **kwargs):
    """Experiment: Longer lookback (30 instead of 20)."""
    return baseline_signal(outcomes, volumes, prices, lookback=30, **kwargs)


def exp_no_exhaustion(outcomes, volumes, prices, lookback=20, **kwargs):
    """Experiment: Remove exhaustion requirement — streak alone is enough."""
    min_streak = kwargs.get("min_streak", 2)

    if len(outcomes) < lookback:
        return {"should_trade": False, "reason": "insufficient", "conviction": 0}

    recent = outcomes[-lookback:]
    regime = _regime(recent, -0.20)

    if regime["is_mean_reverting"]:
        return {"should_trade": False, "reason": "regime_skip", "conviction": 0,
                "regime": regime["label"]}

    # Just check streak, skip exhaustion
    last_dir = "UP" if recent[-1] == 1 else "DOWN"
    streak = 1
    for i in range(len(recent) - 2, -1, -1):
        d = "UP" if recent[i] == 1 else "DOWN"
        if d == last_dir:
            streak += 1
        else:
            break

    signed = streak if last_dir == "UP" else -streak

    if abs(signed) < min_streak:
        return {"should_trade": False, "reason": f"streak_too_short ({signed})",
                "conviction": 0, "regime": regime["label"]}

    direction = "UP" if signed > 0 else "DOWN"
    confidence = "high" if abs(signed) >= 4 else "medium"
    conviction = 4 if direction == "UP" else 3

    return {
        "should_trade": True, "direction": direction, "confidence": confidence,
        "conviction": conviction, "streak": signed,
        "estimate": 0.62 if direction == "UP" else 0.38,
        "regime": regime["label"],
    }


def exp_flip_rate_regime(outcomes, volumes, prices, lookback=20, **kwargs):
    """Experiment: Use flip rate instead of autocorrelation for regime."""
    min_streak = kwargs.get("min_streak", 2)

    if len(outcomes) < lookback:
        return {"should_trade": False, "reason": "insufficient", "conviction": 0}

    recent = outcomes[-lookback:]

    # Flip rate: how often does direction change?
    series = [1 if o == 1 else -1 for o in recent]
    flips = sum(1 for i in range(1, len(series)) if series[i] != series[i-1])
    flip_rate = flips / (len(series) - 1)

    # High flip rate = choppy = skip
    if flip_rate > 0.65:
        return {"should_trade": False, "reason": "choppy_regime", "conviction": 0,
                "regime": f"FLIP_{flip_rate:.2f}"}

    signal = _momentum(recent, volumes[-lookback:], prices[-lookback:], min_streak)
    signal["regime"] = f"FLIP_{flip_rate:.2f}"
    return signal


def exp_hurst_regime(outcomes, volumes, prices, lookback=20, **kwargs):
    """Experiment: Use Hurst exponent for regime detection."""
    min_streak = kwargs.get("min_streak", 2)

    if len(outcomes) < lookback:
        return {"should_trade": False, "reason": "insufficient", "conviction": 0}

    recent = outcomes[-lookback:]

    # Simplified Hurst via R/S method
    series = [1 if o == 1 else -1 for o in recent]
    n = len(series)
    mean_s = sum(series) / n
    Y = []
    cumsum = 0
    for s in series:
        cumsum += (s - mean_s)
        Y.append(cumsum)
    R = max(Y) - min(Y)
    S = (sum((s - mean_s)**2 for s in series) / n) ** 0.5

    if S > 0 and R > 0 and n > 2:
        hurst = math.log(R / S) / math.log(n)
    else:
        hurst = 0.5

    # H < 0.4 = mean-reverting, skip
    if hurst < 0.4:
        return {"should_trade": False, "reason": "hurst_mean_reverting",
                "conviction": 0, "regime": f"HURST_{hurst:.3f}"}

    signal = _momentum(recent, volumes[-lookback:], prices[-lookback:], min_streak)
    signal["regime"] = f"HURST_{hurst:.3f}"
    return signal


def exp_volume_weighted_conviction(outcomes, volumes, prices, lookback=20, **kwargs):
    """Experiment: Boost conviction when volume is high during streak."""
    min_streak = kwargs.get("min_streak", 2)

    if len(outcomes) < lookback:
        return {"should_trade": False, "reason": "insufficient", "conviction": 0}

    recent = outcomes[-lookback:]
    regime = _regime(recent, -0.20)

    if regime["is_mean_reverting"]:
        return {"should_trade": False, "reason": "regime_skip", "conviction": 0,
                "regime": regime["label"]}

    signal = _momentum(recent, volumes[-lookback:], prices[-lookback:], min_streak)

    # Volume boost: if recent volume is > 1.5x average, boost conviction
    if signal["should_trade"] and len(volumes) >= 5:
        avg_vol = sum(volumes[-5:]) / 5
        if avg_vol > 0 and volumes[-1] / avg_vol > 1.5:
            signal["conviction"] = min(signal.get("conviction", 3) + 1, 5)

    signal["regime"] = regime["label"]
    return signal


def exp_streak_direction_filter(outcomes, volumes, prices, lookback=20, **kwargs):
    """Experiment: Only bet UP (skip DOWN bets entirely)."""
    min_streak = kwargs.get("min_streak", 2)

    if len(outcomes) < lookback:
        return {"should_trade": False, "reason": "insufficient", "conviction": 0}

    recent = outcomes[-lookback:]
    regime = _regime(recent, -0.20)

    if regime["is_mean_reverting"]:
        return {"should_trade": False, "reason": "regime_skip", "conviction": 0,
                "regime": regime["label"]}

    signal = _momentum(recent, volumes[-lookback:], prices[-lookback:], min_streak)

    # Only take UP bets
    if signal["should_trade"] and signal.get("direction") == "DOWN":
        signal["should_trade"] = False
        signal["reason"] = "down_filter"
        signal["conviction"] = 0

    signal["regime"] = regime["label"]
    return signal


def exp_allow_down_bets(outcomes, volumes, prices, lookback=20, **kwargs):
    """Experiment: Full conviction on DOWN bets too (no direction penalty)."""
    min_streak = kwargs.get("min_streak", 2)

    if len(outcomes) < lookback:
        return {"should_trade": False, "reason": "insufficient", "conviction": 0}

    recent = outcomes[-lookback:]
    regime = _regime(recent, -0.20)

    if regime["is_mean_reverting"]:
        return {"should_trade": False, "reason": "regime_skip", "conviction": 0,
                "regime": regime["label"]}

    signal = _momentum(recent, volumes[-lookback:], prices[-lookback:], min_streak)

    # Give DOWN same conviction as UP
    if signal["should_trade"] and signal.get("direction") == "DOWN":
        signal["conviction"] = 4  # Same as UP sweet spot

    signal["regime"] = regime["label"]
    return signal


# ── Shared helpers ───────────────────────────────────────────────────

def _regime(outcomes, autocorr_threshold):
    """Compute regime from outcome sequence."""
    series = [1 if o == 1 else -1 for o in outcomes]
    n = len(series)
    mean = sum(series) / n
    var = sum((s - mean) ** 2 for s in series) / n

    if var == 0:
        return {"label": "NEUTRAL", "is_mean_reverting": False, "autocorrelation": 0.0}

    cov = sum((series[i] - mean) * (series[i-1] - mean) for i in range(1, n)) / (n - 1)
    autocorr = cov / var

    flips = sum(1 for i in range(1, n) if series[i] != series[i-1])
    flip_rate = flips / (n - 1)

    vol_label = "HIGH_VOL" if flip_rate > 0.6 else ("MEDIUM_VOL" if flip_rate > 0.4 else "LOW_VOL")
    trend_label = "TRENDING" if autocorr > 0.15 else ("MEAN_REVERTING" if autocorr < autocorr_threshold else "NEUTRAL")

    return {
        "label": f"{vol_label} / {trend_label}",
        "is_mean_reverting": autocorr < autocorr_threshold,
        "autocorrelation": round(autocorr, 4),
    }


def _momentum(outcomes, volumes, prices, min_streak):
    """Core momentum signal from outcome sequence."""
    last_dir = "UP" if outcomes[-1] == 1 else "DOWN"
    streak = 1
    for i in range(len(outcomes) - 2, -1, -1):
        d = "UP" if outcomes[i] == 1 else "DOWN"
        if d == last_dir:
            streak += 1
        else:
            break

    signed = streak if last_dir == "UP" else -streak

    if abs(signed) < min_streak:
        return {"should_trade": False, "reason": f"streak_too_short ({signed})",
                "conviction": 0, "streak": signed}

    # Exhaustion checks
    exhaustion = []
    if len(volumes) >= 5:
        avg_vol = sum(volumes[-5:]) / 5
        if avg_vol > 0 and volumes[-1] / avg_vol > 1.8:
            exhaustion.append("volume_spike")

    if len(prices) >= 3:
        dist = [abs(p - 0.5) for p in prices[-3:]]
        if dist[0] > dist[1] > dist[2]:
            exhaustion.append("price_compression")

    if len(volumes) >= 3:
        if volumes[-3] > volumes[-2] > volumes[-1] and volumes[-1] > 0:
            exhaustion.append("volume_decline")

    if not exhaustion:
        return {"should_trade": False, "reason": f"no_exhaustion (streak={signed})",
                "conviction": 0, "streak": signed}

    direction = "UP" if signed > 0 else "DOWN"
    confidence = "high" if abs(signed) >= 4 else "medium"
    conviction = 4 if direction == "UP" else 3

    return {
        "should_trade": True, "direction": direction, "confidence": confidence,
        "conviction": conviction, "streak": signed,
        "estimate": 0.62 if direction == "UP" else 0.38,
        "exhaustion": exhaustion,
    }


# ── Replay Engine ────────────────────────────────────────────────────

def replay_experiment(db, signal_fn, name, window="15m", lookback=20):
    """Run a signal function against all resolved markets, split into 10 windows."""
    rows = db.execute("""
        SELECT id, end_date, volume, price_yes, outcome
        FROM markets WHERE window = ? AND outcome IS NOT NULL
        ORDER BY end_date ASC
    """, (window,)).fetchall()

    if not rows:
        return None

    # Split into 10 chronological windows
    n = len(rows)
    window_size = n // 10
    windows = []
    for i in range(10):
        start = i * window_size
        end = (i + 1) * window_size if i < 9 else n
        windows.append(rows[start:end])

    # Global tracking
    all_results = {
        "name": name,
        "total_markets": 0,
        "total_bets": 0,
        "total_wins": 0,
        "total_pnl": 0.0,
        "total_wagered": 0.0,
        "window_results": [],
    }

    # Process all windows
    outcomes_hist = []
    volumes_hist = []
    prices_hist = []

    for w_idx, w_rows in enumerate(windows):
        w_bets = 0
        w_wins = 0
        w_pnl = 0.0
        w_wagered = 0.0
        w_total = 0

        for row in w_rows:
            market_id, end_date, volume, price_yes, outcome = row

            # Build up history
            if len(outcomes_hist) < lookback:
                outcomes_hist.append(outcome)
                volumes_hist.append(volume)
                prices_hist.append(price_yes)
                continue

            w_total += 1
            all_results["total_markets"] += 1

            # Run signal
            signal = signal_fn(outcomes_hist, volumes_hist, prices_hist,
                               lookback=lookback, min_streak=2, autocorr_threshold=-0.20)

            if signal.get("should_trade"):
                direction = signal["direction"]
                conviction = signal.get("conviction", 3)
                bet_size = CONVICTION_BETS.get(conviction, 75)

                correct = (direction == "UP" and outcome == 1) or \
                          (direction == "DOWN" and outcome == 0)

                if direction == "UP":
                    pnl = bet_size * (1.0 / price_yes - 1.0) if outcome == 1 else -bet_size
                else:
                    price_no = 1.0 - price_yes
                    pnl = bet_size * (1.0 / price_no - 1.0) if outcome == 0 else -bet_size

                w_bets += 1
                all_results["total_bets"] += 1
                w_wagered += bet_size
                all_results["total_wagered"] += bet_size

                if correct:
                    w_wins += 1
                    all_results["total_wins"] += 1

                w_pnl += pnl
                all_results["total_pnl"] += pnl

            # Slide window
            outcomes_hist.append(outcome)
            volumes_hist.append(volume)
            prices_hist.append(price_yes)

        w_wr = (w_wins / w_bets * 100) if w_bets > 0 else 0
        all_results["window_results"].append({
            "window": w_idx + 1,
            "markets": w_total,
            "bets": w_bets,
            "wins": w_wins,
            "wr": round(w_wr, 1),
            "pnl": round(w_pnl, 2),
        })

    # Compute overall stats
    total_bets = all_results["total_bets"]
    total_wins = all_results["total_wins"]
    all_results["overall_wr"] = round(total_wins / total_bets * 100, 1) if total_bets > 0 else 0
    all_results["overall_roi"] = round(all_results["total_pnl"] / all_results["total_wagered"] * 100, 1) if all_results["total_wagered"] > 0 else 0

    # Variance across windows
    wrs = [w["wr"] for w in all_results["window_results"] if w["bets"] > 0]
    if len(wrs) >= 2:
        mean_wr = sum(wrs) / len(wrs)
        var_wr = sum((w - mean_wr)**2 for w in wrs) / (len(wrs) - 1)
        all_results["wr_std"] = round(var_wr ** 0.5, 1)
    else:
        all_results["wr_std"] = 0

    return all_results


# ── Combination experiments ──────────────────────────────────────────

def exp_combo_hurst_no_exhaustion(outcomes, volumes, prices, lookback=20, **kwargs):
    """Combo: Hurst regime + no exhaustion requirement."""
    min_streak = kwargs.get("min_streak", 2)

    if len(outcomes) < lookback:
        return {"should_trade": False, "reason": "insufficient", "conviction": 0}

    recent = outcomes[-lookback:]

    # Hurst regime
    series = [1 if o == 1 else -1 for o in recent]
    n = len(series)
    mean_s = sum(series) / n
    Y = []
    cumsum = 0
    for s in series:
        cumsum += (s - mean_s)
        Y.append(cumsum)
    R = max(Y) - min(Y)
    S = (sum((s - mean_s)**2 for s in series) / n) ** 0.5
    hurst = math.log(R / S) / math.log(n) if S > 0 and R > 0 and n > 2 else 0.5

    if hurst < 0.4:
        return {"should_trade": False, "reason": "hurst_skip", "conviction": 0,
                "regime": f"HURST_{hurst:.3f}"}

    # Streak only (no exhaustion)
    last_dir = "UP" if recent[-1] == 1 else "DOWN"
    streak = 1
    for i in range(len(recent) - 2, -1, -1):
        d = "UP" if recent[i] == 1 else "DOWN"
        if d == last_dir:
            streak += 1
        else:
            break

    signed = streak if last_dir == "UP" else -streak

    if abs(signed) < min_streak:
        return {"should_trade": False, "reason": f"streak_too_short ({signed})",
                "conviction": 0, "regime": f"HURST_{hurst:.3f}"}

    direction = "UP" if signed > 0 else "DOWN"
    conviction = 4 if direction == "UP" else 3

    return {
        "should_trade": True, "direction": direction, "confidence": "medium",
        "conviction": conviction, "streak": signed,
        "estimate": 0.62 if direction == "UP" else 0.38,
        "regime": f"HURST_{hurst:.3f}",
    }


def exp_combo_strict_streak3_vol(outcomes, volumes, prices, lookback=20, **kwargs):
    """Combo: Strict regime + streak>=3 + volume-weighted conviction."""
    if len(outcomes) < lookback:
        return {"should_trade": False, "reason": "insufficient", "conviction": 0}

    recent = outcomes[-lookback:]
    regime = _regime(recent, -0.10)  # Strict

    if regime["is_mean_reverting"]:
        return {"should_trade": False, "reason": "regime_skip", "conviction": 0,
                "regime": regime["label"]}

    signal = _momentum(recent, volumes[-lookback:], prices[-lookback:], min_streak=3)

    # Volume boost
    if signal["should_trade"] and len(volumes) >= 5:
        avg_vol = sum(volumes[-5:]) / 5
        if avg_vol > 0 and volumes[-1] / avg_vol > 1.5:
            signal["conviction"] = min(signal.get("conviction", 3) + 1, 5)

    signal["regime"] = regime["label"]
    return signal


def exp_combo_best(outcomes, volumes, prices, lookback=20, **kwargs):
    """Combo: Best individual winners combined (will be determined after Phase 2)."""
    # This will be filled in after analyzing Phase 2 results
    # For now: Hurst + streak>=2 + volume boost + allow DOWN
    min_streak = kwargs.get("min_streak", 2)

    if len(outcomes) < lookback:
        return {"should_trade": False, "reason": "insufficient", "conviction": 0}

    recent = outcomes[-lookback:]

    # Hurst regime
    series = [1 if o == 1 else -1 for o in recent]
    n = len(series)
    mean_s = sum(series) / n
    Y = []
    cumsum = 0
    for s in series:
        cumsum += (s - mean_s)
        Y.append(cumsum)
    R = max(Y) - min(Y)
    S = (sum((s - mean_s)**2 for s in series) / n) ** 0.5
    hurst = math.log(R / S) / math.log(n) if S > 0 and R > 0 and n > 2 else 0.5

    if hurst < 0.4:
        return {"should_trade": False, "reason": "hurst_skip", "conviction": 0,
                "regime": f"HURST_{hurst:.3f}"}

    signal = _momentum(recent, volumes[-lookback:], prices[-lookback:], min_streak)

    # Allow DOWN at full conviction
    if signal["should_trade"] and signal.get("direction") == "DOWN":
        signal["conviction"] = 4

    # Volume boost
    if signal["should_trade"] and len(volumes) >= 5:
        avg_vol = sum(volumes[-5:]) / 5
        if avg_vol > 0 and volumes[-1] / avg_vol > 1.5:
            signal["conviction"] = min(signal.get("conviction", 3) + 1, 5)

    signal["regime"] = f"HURST_{hurst:.3f}"
    return signal


# ── Main ─────────────────────────────────────────────────────────────

EXPERIMENTS = {
    # Phase 1: Baseline
    "baseline": baseline_signal,

    # Phase 2: Individual ablations
    "no_regime_gate": exp_no_regime_gate,
    "strict_regime": exp_strict_regime,
    "min_streak_3": exp_min_streak_3,
    "min_streak_4": exp_min_streak_4,
    "lookback_10": exp_lookback_10,
    "lookback_30": exp_lookback_30,
    "no_exhaustion": exp_no_exhaustion,
    "flip_rate_regime": exp_flip_rate_regime,
    "hurst_regime": exp_hurst_regime,
    "volume_weighted": exp_volume_weighted_conviction,
    "only_up_bets": exp_streak_direction_filter,
    "full_down_conviction": exp_allow_down_bets,

    # Phase 3: Combinations
    "combo_hurst_no_exhaustion": exp_combo_hurst_no_exhaustion,
    "combo_strict_streak3_vol": exp_combo_strict_streak3_vol,
    "combo_best": exp_combo_best,
}


def main():
    db = sqlite3.connect(DB_PATH)

    # Check data
    total = db.execute("SELECT COUNT(*) FROM markets WHERE window = '15m' AND outcome IS NOT NULL").fetchone()[0]
    print(f"Dataset: {total} resolved 15m markets\n")

    all_results = []

    for name, fn in EXPERIMENTS.items():
        print(f"Running: {name}...")
        result = replay_experiment(db, fn, name, window="15m")
        if result:
            all_results.append(result)
            print(f"  WR: {result['overall_wr']}% | Bets: {result['total_bets']} | "
                  f"P&L: ${result['total_pnl']:+,.0f} | Std: {result['wr_std']}%")
        print()

    db.close()

    # Generate report
    _write_report(all_results, total)
    print(f"\nReport written to {RESULTS_PATH}")


def _write_report(results, total_markets):
    """Write markdown report with all experiment results."""
    # Sort by WR for ranking
    baseline = next((r for r in results if r["name"] == "baseline"), None)
    baseline_wr = baseline["overall_wr"] if baseline else 0

    lines = [
        "# Experiment Results: 15m Momentum Signal Improvements",
        "",
        f"> **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> **Dataset:** {total_markets} resolved 15m Polymarket BTC markets (28 days)",
        f"> **Method:** 10 chronological windows per experiment for variance estimation",
        f"> **Baseline WR:** {baseline_wr}%",
        "",
        "---",
        "",
        "## Summary Table (sorted by Win Rate)",
        "",
        "| # | Experiment | WR % | +/- Baseline | Bets | P&L | ROI % | WR Std | Consistent? |",
        "|---|-----------|------|-------------|------|-----|-------|--------|------------|",
    ]

    ranked = sorted(results, key=lambda r: r["overall_wr"], reverse=True)
    for i, r in enumerate(ranked):
        delta = r["overall_wr"] - baseline_wr
        delta_str = f"{delta:+.1f}%" if delta != 0 else "---"
        consistent = "Yes" if r["wr_std"] < 15 else "No"
        lines.append(
            f"| {i+1} | **{r['name']}** | {r['overall_wr']}% | {delta_str} | "
            f"{r['total_bets']} | ${r['total_pnl']:+,.0f} | {r['overall_roi']:+.1f}% | "
            f"{r['wr_std']}% | {consistent} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Per-Window Breakdown",
        "",
    ]

    for r in ranked[:5]:  # Top 5 only for detail
        lines.append(f"### {r['name']} (Overall: {r['overall_wr']}% WR)")
        lines.append("")
        lines.append("| Window | Markets | Bets | Wins | WR % | P&L |")
        lines.append("|--------|---------|------|------|------|-----|")
        for w in r["window_results"]:
            lines.append(
                f"| {w['window']} | {w['markets']} | {w['bets']} | {w['wins']} | "
                f"{w['wr']}% | ${w['pnl']:+,.0f} |"
            )
        lines.append("")

    lines += [
        "---",
        "",
        "## Key Findings",
        "",
        "*(Auto-generated — review manually)*",
        "",
    ]

    # Auto-generate findings
    if ranked:
        best = ranked[0]
        worst = ranked[-1]
        lines.append(f"1. **Best performer:** {best['name']} at {best['overall_wr']}% WR "
                     f"({best['total_bets']} bets, ${best['total_pnl']:+,.0f} P&L)")
        lines.append(f"2. **Worst performer:** {worst['name']} at {worst['overall_wr']}% WR")

        # Most bets
        most_bets = max(results, key=lambda r: r["total_bets"])
        lines.append(f"3. **Most trades:** {most_bets['name']} with {most_bets['total_bets']} bets")

        # Best P&L
        best_pnl = max(results, key=lambda r: r["total_pnl"])
        lines.append(f"4. **Best P&L:** {best_pnl['name']} at ${best_pnl['total_pnl']:+,.0f}")

        # Most consistent
        most_consistent = min([r for r in results if r["total_bets"] > 10],
                              key=lambda r: r["wr_std"], default=None)
        if most_consistent:
            lines.append(f"5. **Most consistent:** {most_consistent['name']} "
                         f"(WR std: {most_consistent['wr_std']}%)")

    lines.append("")
    lines.append("---")
    lines.append(f"*Generated by experiment_15m.py on {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    RESULTS_PATH.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
