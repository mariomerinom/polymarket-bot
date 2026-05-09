"""
fill_diagnostic.py — Two complementary tools.

(1) Lever B `fill_diagnostic` SQLite TABLE — `init_table`, `record`,
    `fill_rate`, `fill_outcome_correlation`. Records every order attempt
    (filled, killed, partial, skipped) so we can measure fill rate,
    fill↔outcome correlation, and which failure mode dominates.
    Reference: docs/specs/stochastic/spec_fill_adverse_selection.md

(2) Phase-2 LOG PARSER — parses DIAG| lines emitted by trade.py and
    produces decision_delay, orderbook_age, order_rtt, and
    conviction-vs-drift verdicts. Legacy snapshot_age_ms lines are still
    accepted as decision_delay_ms for backward compatibility.

CLI usage (log parser):
    python src/fill_diagnostic.py --log-file logs/loop.log
"""

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover — optional dep for CLI analysis
    np = None


# ═══════════════════════════════════════════════════════════════════════════
# (1) Lever B — fill_diagnostic SQLite table
# ═══════════════════════════════════════════════════════════════════════════

# Allowed result codes. Anything outside this set is rejected at insert time
# to prevent silent corruption from typos.
RESULT_CODES = frozenset({
    # Filled paths (denominator + numerator of fill_rate)
    "filled_full",
    "filled_partial",
    # Failed paths (denominator only)
    "killed_fok",
    "cancelled_ioc_residual",
    # Skipped paths (excluded from fill_rate denominator)
    "skipped_cushion_eats_edge",
    "skipped_low_edge",
    "skipped_thin_book",
    "skipped_book_moved",
    "skipped_ghost_liquidity",
    "skipped_other",
    # Pipeline-level pause (Lever C)
    "paused_adverse_microstructure",
    # Catch-all for unexpected exceptions during submission
    "submit_error",
    # Paper-mode placeholder (would have fired in live)
    "paper_would_fire",
    # Infrastructure failures
    "missing_token",
    # Legacy GTC path still in use for paper pipelines w/o WS bid/ask
    "gtc_submitted",
    # ── Bybit (perp) terminal events ─────────────────────────────────────
    # Live limit order accepted by Bybit (confirms submission, not fill)
    "bybit_limit_submitted",
    # Live limit order rejected by Bybit API (retCode != 0, non-margin)
    "bybit_limit_rejected",
    # Server-side stop-loss fired (detected via REST reconcile)
    "bybit_stop_triggered",
    # Position closed by REST reconcile without stop — e.g. manual/web close
    "bybit_reconciled_closed",
    # Margin / funds insufficient at order time
    "bybit_margin_insufficient",
    # WS feed stale; forced-closed local position based on last known mark
    "bybit_ws_stale_close",
    # Local exit: signal reversed mid-hold
    "bybit_exit_streak_break",
    # Local exit: max hold cycles reached
    "bybit_exit_time_ceiling",
})


def init_table(db):
    """Create the fill_diagnostic table if it does not exist. Idempotent.

    Also migrates existing tables to add the `prediction_id` column
    (added 2026-04-19 to let the pipeline_integrity orphan check
    distinguish genuinely-silent-fail predictions from predictions
    consciously skipped for recorded reasons like thin-book/low-edge).
    """
    db.execute("""
        CREATE TABLE IF NOT EXISTS fill_diagnostic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            prediction_id INTEGER,
            timestamp TEXT NOT NULL,
            cycle INTEGER,
            pipeline TEXT NOT NULL,
            decision_best_bid REAL,
            decision_best_ask REAL,
            decision_spread REAL,
            decision_top_ask_size REAL,
            decision_max_bet_2pct REAL,
            response_best_bid REAL,
            response_best_ask REAL,
            requested_size REAL,
            requested_limit REAL,
            filled_size REAL,
            filled_avg_price REAL,
            order_type TEXT,
            cushion REAL,
            result TEXT NOT NULL,
            outcome INTEGER,
            resolved_at TEXT
        )
    """)
    # Migration for pre-existing tables that lack prediction_id
    try:
        db.execute("ALTER TABLE fill_diagnostic ADD COLUMN prediction_id INTEGER")
    except Exception:
        pass  # column already exists
    db.commit()


def record(
    db,
    *,
    pipeline,
    result,
    order_id=None,
    prediction_id=None,
    cycle=None,
    decision_best_bid=None,
    decision_best_ask=None,
    decision_spread=None,
    decision_top_ask_size=None,
    decision_max_bet_2pct=None,
    response_best_bid=None,
    response_best_ask=None,
    requested_size=None,
    requested_limit=None,
    filled_size=None,
    filled_avg_price=None,
    order_type=None,
    cushion=None,
    outcome=None,
    resolved_at=None,
):
    """Insert one diagnostic row. Required: pipeline, result. Other fields nullable."""
    if result not in RESULT_CODES:
        raise ValueError(
            f"unknown fill_diagnostic result code: {result!r}. "
            f"Allowed: {sorted(RESULT_CODES)}"
        )
    init_table(db)
    db.execute("""
        INSERT INTO fill_diagnostic (
            order_id, prediction_id, timestamp, cycle, pipeline,
            decision_best_bid, decision_best_ask, decision_spread,
            decision_top_ask_size, decision_max_bet_2pct,
            response_best_bid, response_best_ask,
            requested_size, requested_limit,
            filled_size, filled_avg_price,
            order_type, cushion, result,
            outcome, resolved_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_id,
        prediction_id,
        datetime.now(timezone.utc).isoformat(),
        cycle,
        pipeline,
        decision_best_bid, decision_best_ask, decision_spread,
        decision_top_ask_size, decision_max_bet_2pct,
        response_best_bid, response_best_ask,
        requested_size, requested_limit,
        filled_size, filled_avg_price,
        order_type, cushion, result,
        outcome, resolved_at,
    ))
    db.commit()


# Result codes that count as "fired" (i.e. went to CLOB)
FIRED_CODES = ("filled_full", "filled_partial", "killed_fok",
               "cancelled_ioc_residual", "submit_error")
FILLED_CODES = ("filled_full", "filled_partial")


def fill_rate(db, pipeline):
    """Fraction of fired orders that filled (full or partial). Skips excluded."""
    placeholders = ",".join("?" * len(FIRED_CODES))
    fired = db.execute(
        f"SELECT COUNT(*) FROM fill_diagnostic WHERE pipeline = ? AND result IN ({placeholders})",
        (pipeline, *FIRED_CODES),
    ).fetchone()[0]
    if fired == 0:
        return 0.0
    placeholders_filled = ",".join("?" * len(FILLED_CODES))
    filled = db.execute(
        f"SELECT COUNT(*) FROM fill_diagnostic WHERE pipeline = ? AND result IN ({placeholders_filled})",
        (pipeline, *FILLED_CODES),
    ).fetchone()[0]
    return filled / fired


def fill_outcome_correlation(db, pipeline):
    """Pearson corr(filled, won) on fired+resolved rows. None if n<10."""
    placeholders = ",".join("?" * len(FIRED_CODES))
    rows = db.execute(
        f"""SELECT result, outcome
            FROM fill_diagnostic
            WHERE pipeline = ? AND result IN ({placeholders}) AND outcome IS NOT NULL""",
        (pipeline, *FIRED_CODES),
    ).fetchall()
    if len(rows) < 10:
        return None
    pairs = [(1 if r[0] in FILLED_CODES else 0, int(r[1])) for r in rows]
    n = len(pairs)
    sum_x = sum(p[0] for p in pairs)
    sum_y = sum(p[1] for p in pairs)
    sum_xy = sum(p[0] * p[1] for p in pairs)
    sum_x2 = sum(p[0] ** 2 for p in pairs)
    sum_y2 = sum(p[1] ** 2 for p in pairs)
    num = n * sum_xy - sum_x * sum_y
    den_sq = (n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)
    if den_sq <= 0:
        return 0.0
    return num / (den_sq ** 0.5)


# ═══════════════════════════════════════════════════════════════════════════
# (2) Legacy log parser — DIAG line analysis
# ═══════════════════════════════════════════════════════════════════════════


def parse_diag_lines(log_path):
    """Parse all DIAG| lines from a log file into structured data."""
    decision_delays = []
    orderbook_ages = []
    rtt_values = []
    drift_by_conv = defaultdict(list)

    with open(log_path, "r") as f:
        for line in f:
            if "DIAG|" not in line:
                continue

            # Diagnostic A: decision delay from candle close to decision time.
            m = re.search(r"DIAG\|decision_delay_ms=(\d+)", line)
            if not m:
                # Backward compatibility: old name measured the same thing.
                m = re.search(r"DIAG\|snapshot_age_ms=(\d+)", line)
            if m and "conv=" not in line and "order_rtt" not in line:
                decision_delays.append(float(m.group(1)))

            # Diagnostic A2: true orderbook age from token updated_at.
            m = re.search(r"DIAG\|orderbook_age_ms=(\d+)", line)
            if m:
                orderbook_ages.append(float(m.group(1)))

            # Diagnostic B: conviction + drift
            m = re.search(
                r"DIAG\|conv=(\d+)\|drift=([\d.]+)",
                line,
            )
            if m:
                conv = int(m.group(1))
                drift = float(m.group(2))
                drift_by_conv[conv].append(drift)

            # Diagnostic C: order_rtt_ms
            m = re.search(r"DIAG\|order_rtt_ms=(\d+)", line)
            if m:
                rtt_values.append(float(m.group(1)))

    return decision_delays, orderbook_ages, rtt_values, drift_by_conv


def percentiles(values, label=""):
    """Compute p50, p95, p99 for a list of values."""
    if not values:
        return {"p50": None, "p95": None, "p99": None, "count": 0}
    if np is None:
        arr = sorted(values)
        n = len(arr)

        def pick(p):
            idx = min(n - 1, max(0, round((p / 100) * (n - 1))))
            return float(arr[idx])

        return {
            "p50": pick(50),
            "p95": pick(95),
            "p99": pick(99),
            "count": n,
        }
    arr = np.array(values)
    return {
        "p50": float(np.percentile(arr, 50)),
        "p95": float(np.percentile(arr, 95)),
        "p99": float(np.percentile(arr, 99)),
        "count": len(arr),
    }


def mann_whitney_test(a, b):
    """Run Mann-Whitney U test. Returns (U statistic, p-value) or None."""
    if len(a) < 5 or len(b) < 5:
        return None
    try:
        from scipy.stats import mannwhitneyu
        stat, p = mannwhitneyu(a, b, alternative="two-sided")
        return {"U": float(stat), "p": float(p)}
    except ImportError:
        # scipy not available — skip statistical test
        return None


def decision_delay_verdict(p95):
    """Apply decision-delay rule."""
    if p95 is None:
        return "insufficient data"
    if p95 < 30_000:
        return "acceptable for paper promotion review"
    return "root cause — dispatch/pipeline fanout is delaying decisions"


def conviction_verdict(mw_result, drift_by_conv):
    """Apply spec decision rule for conviction vs drift."""
    if mw_result is None:
        return "insufficient data"
    median_3 = float(np.median(drift_by_conv.get(3, [0]))) if drift_by_conv.get(3) else None
    median_5 = float(np.median(drift_by_conv.get(5, [0]))) if drift_by_conv.get(5) else None
    if mw_result["p"] < 0.05 and median_5 and median_3 and median_5 > median_3:
        return "exclude conviction from pricing — use microstructure only"
    if mw_result["p"] >= 0.05:
        return "no significant difference — use conviction as ceiling/governor"
    return "conviction additive bonus is defensible"


def rtt_verdict(p95):
    """Apply spec decision rule for cancel-replace feasibility."""
    if p95 is None:
        return "insufficient data"
    if p95 < 500:
        return "cancel-replace cycles are viable — build into Phase 3"
    if p95 <= 1000:
        return "possible but tight — limit to 2 cycles max"
    return "impractical on this API — skip cancel-replace"


def generate_report(decision_delays, orderbook_ages, rtt_values, drift_by_conv, min_samples=20):
    """Generate the full diagnostic report as markdown."""
    delay_stats = percentiles(decision_delays)
    ob_stats = percentiles(orderbook_ages)
    rtt_stats = percentiles(rtt_values)

    lines = []
    lines.append("## Fill Diagnostic (Phase 2)\n")

    # Decision delay + true orderbook freshness + RTT table
    lines.append("| Metric | p50 | p95 | p99 | Samples |")
    lines.append("|--------|-----|-----|-----|---------|")
    if delay_stats["count"] > 0:
        lines.append(f"| Decision delay (ms) | {delay_stats['p50']:.0f} | {delay_stats['p95']:.0f} | {delay_stats['p99']:.0f} | {delay_stats['count']} |")
    else:
        lines.append("| Decision delay (ms) | — | — | — | 0 |")
    if ob_stats["count"] > 0:
        lines.append(f"| Orderbook age at read (ms) | {ob_stats['p50']:.0f} | {ob_stats['p95']:.0f} | {ob_stats['p99']:.0f} | {ob_stats['count']} |")
    else:
        lines.append("| Orderbook age at read (ms) | — | — | — | 0 |")
    if rtt_stats["count"] > 0:
        lines.append(f"| Order RTT (ms) | {rtt_stats['p50']:.0f} | {rtt_stats['p95']:.0f} | {rtt_stats['p99']:.0f} | {rtt_stats['count']} |")
    else:
        lines.append("| Order RTT (ms) | — | — | — | 0 |")
    lines.append("")

    # Conviction drift table
    lines.append("| Conv Tier | Median Drift | Mean Drift | Std | Samples |")
    lines.append("|-----------|-------------|------------|-----|---------|")
    for conv in sorted(drift_by_conv.keys()):
        vals = drift_by_conv[conv]
        if np is None:
            ordered = sorted(vals)
            mid = ordered[len(ordered) // 2]
            mean = sum(vals) / len(vals)
            variance = sum((v - mean) ** 2 for v in vals) / len(vals)
            std = variance ** 0.5
            lines.append(f"| {conv} | {mid:.4f} | {mean:.4f} | {std:.4f} | {len(vals)} |")
        else:
            arr = np.array(vals)
            lines.append(f"| {conv} | {np.median(arr):.4f} | {np.mean(arr):.4f} | {np.std(arr):.4f} | {len(vals)} |")
    if not drift_by_conv:
        lines.append("| — | — | — | — | 0 |")
    lines.append("")

    # Mann-Whitney test
    mw = mann_whitney_test(
        drift_by_conv.get(3, []),
        drift_by_conv.get(5, []),
    )
    if mw:
        lines.append(f"Mann-Whitney U (conv=3 vs conv=5): U={mw['U']:.1f}, p={mw['p']:.4f}\n")
    else:
        n3 = len(drift_by_conv.get(3, []))
        n5 = len(drift_by_conv.get(5, []))
        lines.append(f"Mann-Whitney U: insufficient data (conv=3: {n3} samples, conv=5: {n5} samples, need >= 5 each)\n")

    # Decision verdicts
    lines.append("### Decisions")
    total_samples = delay_stats["count"] + ob_stats["count"] + rtt_stats["count"] + sum(len(v) for v in drift_by_conv.values())
    if total_samples < min_samples:
        lines.append(f"Collecting data ({total_samples} samples so far, need >= {min_samples})\n")
    else:
        dv = decision_delay_verdict(delay_stats["p95"])
        cv = conviction_verdict(mw, drift_by_conv)
        rv = rtt_verdict(rtt_stats["p95"])
        lines.append(f"- Decision delay p95={delay_stats['p95']:.0f}ms: **{dv}**" if delay_stats["p95"] else "- Decision delay: **insufficient data**")
        if ob_stats["p95"] is not None:
            lines.append(f"- Orderbook age p95={ob_stats['p95']:.0f}ms: **true cache freshness at read time**")
        else:
            lines.append("- Orderbook age: **insufficient data**")
        lines.append(f"- Conviction vs drift: **{cv}**")
        lines.append(f"- Order RTT p95={rtt_stats['p95']:.0f}ms: **{rv}**" if rtt_stats["p95"] else f"- Order RTT: **{rv}**")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Phase 2 fill diagnostic analysis")
    parser.add_argument("--log-file", required=True, help="Path to VPS log file")
    parser.add_argument("--min-samples", type=int, default=20, help="Min samples before generating verdicts")
    parser.add_argument("--markdown", action="store_true", help="Output as markdown (default: text)")
    args = parser.parse_args()

    log_path = Path(args.log_file)
    if not log_path.exists():
        print(f"Log file not found: {log_path}")
        sys.exit(1)

    decision_delays, orderbook_ages, rtt_values, drift_by_conv = parse_diag_lines(log_path)

    print(f"Parsed: {len(decision_delays)} decision_delay, "
          f"{len(orderbook_ages)} orderbook_age, {len(rtt_values)} rtt, "
          f"{sum(len(v) for v in drift_by_conv.values())} drift samples")
    print()

    report = generate_report(
        decision_delays, orderbook_ages, rtt_values, drift_by_conv, args.min_samples
    )
    print(report)


if __name__ == "__main__":
    main()
