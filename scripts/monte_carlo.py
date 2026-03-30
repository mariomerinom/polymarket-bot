"""
monte_carlo.py — Statistical robustness validation for prediction signals.

Ported from arbitrageur's Monte Carlo validation system.
Two tests:
  1. Trade Sequence Shuffle — shuffle trade order 10K times, compute ruin
     probability + Sharpe distribution. Tests: is the edge real or order-dependent?
  2. Parameter Noise — perturb signal parameters ±10%, verify edge survives.
     Tests: is the edge robust or brittle on specific tuning?

Gate criteria (all must pass for a signal to graduate from paper → production):
  - Median Sharpe > 0.5
  - Ruin probability < 5%
  - Parameter robustness >= 80% of variants profitable

Usage:
    python scripts/monte_carlo.py [--asset BTC|ETH] [--db path] [--iterations 10000]
"""

import argparse
import random
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

DB_PATH = Path(__file__).parent.parent / "data" / "predictions.db"
DB_PATH_ETH = Path(__file__).parent.parent / "data" / "predictions_eth.db"


@dataclass
class MonteCarloResult:
    """Results from trade sequence shuffle."""
    iterations: int = 0
    median_sharpe: float = 0.0
    p5_drawdown: float = 0.0
    p50_drawdown: float = 0.0
    p95_drawdown: float = 0.0
    ruin_probability: float = 0.0  # % of iterations that go below -50% of peak
    sharpe_distribution: list = field(default_factory=list)
    drawdown_distribution: list = field(default_factory=list)
    gate_pass: bool = False


@dataclass
class ParameterNoiseResult:
    """Results from parameter perturbation test."""
    iterations: int = 0
    pct_profitable: float = 0.0
    median_sharpe: float = 0.0
    median_pf: float = 0.0
    gate_pass: bool = False


def _compute_equity_curve(pnls):
    """Build cumulative equity curve from P&L sequence."""
    curve = [0.0]
    for pnl in pnls:
        curve.append(curve[-1] + pnl)
    return curve


def _compute_sharpe(pnls, risk_free=0):
    """Annualized Sharpe ratio (assuming 5-min bets, ~105K per year)."""
    if len(pnls) < 2:
        return 0.0
    import statistics
    mean = statistics.mean(pnls)
    stdev = statistics.stdev(pnls)
    if stdev == 0:
        return 0.0
    # ~288 bets per day (24h * 60min / 5min), ~252 trading days
    periods_per_year = 288 * 252
    return (mean - risk_free) / stdev * (periods_per_year ** 0.5)


def _compute_max_drawdown(curve):
    """Max drawdown in absolute dollars from peak."""
    peak = curve[0]
    max_dd = 0.0
    for val in curve:
        if val > peak:
            peak = val
        dd = peak - val
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _is_ruined(curve, bankroll=500):
    """
    Did equity ever drop below -bankroll (wiped the seed)?

    Uses absolute threshold, not relative-to-peak, because early peaks
    are tiny and any dip looks catastrophic as a percentage.
    """
    for val in curve:
        if val < -bankroll:
            return True
    return False


def trade_sequence_shuffle(pnls, iterations=10000, seed=42):
    """
    Shuffle trade order N times and compute statistics.

    If the strategy is robust, shuffling order shouldn't destroy the edge.
    If Sharpe collapses or ruin probability is high, the edge was order-dependent.
    """
    rng = random.Random(seed)
    sharpes = []
    drawdowns = []
    ruins = 0

    for _ in range(iterations):
        shuffled = pnls.copy()
        rng.shuffle(shuffled)
        curve = _compute_equity_curve(shuffled)
        sharpes.append(_compute_sharpe(shuffled))
        drawdowns.append(_compute_max_drawdown(curve))
        if _is_ruined(curve):
            ruins += 1

    sharpes.sort()
    drawdowns.sort()
    n = len(sharpes)

    result = MonteCarloResult(
        iterations=iterations,
        median_sharpe=sharpes[n // 2],
        p5_drawdown=drawdowns[int(n * 0.05)],
        p50_drawdown=drawdowns[n // 2],
        p95_drawdown=drawdowns[int(n * 0.95)],
        ruin_probability=(ruins / iterations) * 100,
        sharpe_distribution=sharpes,
        drawdown_distribution=drawdowns,
    )
    result.gate_pass = (
        result.median_sharpe > 0.5
        and result.ruin_probability < 5.0
    )
    return result


def parameter_noise_test(pnls, base_wr, noise_pct=0.10, iterations=200, seed=42):
    """
    Perturb the effective win rate ±noise_pct and simulate P&L.

    For each perturbation:
      - Randomly flip a fraction of trades (win→loss or loss→win)
      - Compute whether the variant is still profitable

    Tests: is the edge robust to parameter drift?
    """
    rng = random.Random(seed)
    profitable_count = 0
    sharpes = []
    pfs = []

    for _ in range(iterations):
        # Perturb: flip some trades randomly based on noise
        perturbed = pnls.copy()
        n_flips = max(1, int(len(perturbed) * noise_pct * rng.random()))
        flip_indices = rng.sample(range(len(perturbed)), min(n_flips, len(perturbed)))
        for idx in flip_indices:
            perturbed[idx] = -perturbed[idx]

        total_pnl = sum(perturbed)
        wins = sum(1 for p in perturbed if p > 0)
        losses = sum(1 for p in perturbed if p < 0)

        sharpe = _compute_sharpe(perturbed)
        pf = sum(p for p in perturbed if p > 0) / abs(sum(p for p in perturbed if p < 0)) if losses > 0 else float("inf")

        if total_pnl > 0:
            profitable_count += 1
        sharpes.append(sharpe)
        pfs.append(pf)

    sharpes.sort()
    pfs.sort()

    result = ParameterNoiseResult(
        iterations=iterations,
        pct_profitable=(profitable_count / iterations) * 100,
        median_sharpe=sharpes[len(sharpes) // 2],
        median_pf=pfs[len(pfs) // 2],
    )
    result.gate_pass = result.pct_profitable >= 80.0
    return result


def load_pnls(db_path):
    """Load resolved prediction P&Ls from database."""
    db = sqlite3.connect(str(db_path))
    rows = db.execute("""
        SELECT p.estimate, m.outcome
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE m.resolved = 1 AND m.outcome IS NOT NULL
          AND p.conviction_score >= 3
        ORDER BY p.predicted_at ASC
    """).fetchall()
    db.close()

    pnls = []
    for estimate, outcome in rows:
        direction_up = estimate >= 0.5
        won = (direction_up and outcome == 1) or (not direction_up and outcome == 0)
        # Approximate P&L: flat $25 bet
        if won:
            price = estimate if direction_up else (1 - estimate)
            pnl = 25 * (1.0 / price - 1) * 0.985
        else:
            pnl = -25
        pnls.append(round(pnl, 2))

    return pnls


def run_full_validation(db_path, iterations=10000):
    """Run complete Monte Carlo validation and return report."""
    pnls = load_pnls(db_path)

    if len(pnls) < 30:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": f"Need 30+ resolved bets, have {len(pnls)}",
            "count": len(pnls),
        }

    wins = sum(1 for p in pnls if p > 0)
    wr = wins / len(pnls) * 100

    mc = trade_sequence_shuffle(pnls, iterations=iterations)
    pn = parameter_noise_test(pnls, base_wr=wr)

    overall_pass = mc.gate_pass and pn.gate_pass

    return {
        "status": "PASS" if overall_pass else "FAIL",
        "count": len(pnls),
        "win_rate": round(wr, 1),
        "total_pnl": round(sum(pnls), 2),
        "monte_carlo": {
            "median_sharpe": round(mc.median_sharpe, 2),
            "ruin_probability": round(mc.ruin_probability, 1),
            "p5_drawdown": round(mc.p5_drawdown, 1),
            "p50_drawdown": round(mc.p50_drawdown, 1),
            "p95_drawdown": round(mc.p95_drawdown, 1),
            "gate_pass": mc.gate_pass,
        },
        "parameter_noise": {
            "pct_profitable": round(pn.pct_profitable, 1),
            "median_sharpe": round(pn.median_sharpe, 2),
            "median_pf": round(pn.median_pf, 2),
            "gate_pass": pn.gate_pass,
        },
        "gates": {
            "sharpe_gt_0.5": mc.median_sharpe > 0.5,
            "ruin_lt_5pct": mc.ruin_probability < 5.0,
            "robustness_ge_80pct": pn.pct_profitable >= 80.0,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Monte Carlo validation for prediction signals")
    parser.add_argument("--asset", default="BTC", choices=["BTC", "ETH"],
                        help="Asset to validate")
    parser.add_argument("--db", type=str, default=None,
                        help="Path to predictions DB (overrides --asset)")
    parser.add_argument("--iterations", type=int, default=10000,
                        help="Number of MC iterations")
    args = parser.parse_args()

    if args.db:
        db_path = Path(args.db)
    elif args.asset == "ETH":
        db_path = DB_PATH_ETH
    else:
        db_path = DB_PATH

    print(f"Monte Carlo Validation — {args.asset} ({db_path.name})")
    print("=" * 60)

    result = run_full_validation(db_path, iterations=args.iterations)

    if result["status"] == "INSUFFICIENT_DATA":
        print(f"\n  {result['message']}")
        print("  Collect more data before validating.")
        return

    print(f"\n  Resolved bets: {result['count']}")
    print(f"  Win rate: {result['win_rate']}%")
    print(f"  Total P&L: ${result['total_pnl']:+,.2f}")

    mc = result["monte_carlo"]
    print(f"\n  Trade Sequence Shuffle ({args.iterations} iterations):")
    print(f"    Median Sharpe: {mc['median_sharpe']:.2f} {'PASS' if mc['gate_pass'] else 'FAIL'}")
    print(f"    Ruin probability: {mc['ruin_probability']:.1f}%")
    print(f"    Drawdown (P5/P50/P95): ${mc['p5_drawdown']:.0f} / ${mc['p50_drawdown']:.0f} / ${mc['p95_drawdown']:.0f}")

    pn = result["parameter_noise"]
    print(f"\n  Parameter Noise Test (200 iterations):")
    print(f"    Profitable variants: {pn['pct_profitable']:.1f}% {'PASS' if pn['gate_pass'] else 'FAIL'}")
    print(f"    Median Sharpe: {pn['median_sharpe']:.2f}")
    print(f"    Median Profit Factor: {pn['median_pf']:.2f}")

    status = result["status"]
    emoji = "PASS" if status == "PASS" else "FAIL"
    print(f"\n  Overall: {emoji}")
    for gate, passed in result["gates"].items():
        mark = "PASS" if passed else "FAIL"
        print(f"    {gate}: {mark}")


if __name__ == "__main__":
    main()
