"""
shadow_maker.py — Phase 1 shadow maker logging and fill simulation.

Logs hypothetical maker orders for every conv≥3 prediction. Measures
whether passive fills would close the 13¢/dollar gap between signal
EHR (+0.102) and execution EHR (-0.028).

Spec: docs/specs/spec_maker_mode.md (AC-SM-1 through AC-SM-5)
Baseline: docs/analysis/ehr_baseline_2026-04-16.md
"""

from datetime import datetime, timezone


# ── Schema ───────────────────────────────────────────────────────────


def init_table(db):
    """Create shadow_maker table if not exists. Idempotent."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS shadow_maker (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id INTEGER,
            market_id TEXT NOT NULL,
            pipeline TEXT NOT NULL,
            cycle INTEGER,
            timestamp TEXT NOT NULL,
            direction TEXT NOT NULL,
            estimate REAL,
            conviction INTEGER,
            regime TEXT,
            best_bid REAL,
            best_ask REAL,
            spread REAL,
            mid REAL,
            shadow_price REAL NOT NULL,
            shadow_side TEXT NOT NULL,
            taker_price REAL,
            taker_action TEXT,
            filled INTEGER,
            fill_candle_low REAL,
            fill_candle_high REAL,
            fill_candle_close REAL,
            adverse INTEGER,
            outcome INTEGER,
            resolved_at TEXT
        )
    """)
    db.commit()


# ── Core Functions ───────────────────────────────────────────────────


def compute_shadow_price(direction, best_bid, best_ask, spread, mid):
    """AC-SM-1: compute hypothetical maker price.

    BUY (UP direction):  shadow_bid = mid - (spread * 0.25)
    SELL (DOWN direction): shadow_ask = mid + (spread * 0.25)

    Posts inside the spread — better than best bid/ask but not at mid.

    Returns:
        (shadow_price, shadow_side) or (None, None) if book data missing.
    """
    if mid is None or spread is None:
        return None, None

    if direction == "UP":
        shadow_price = mid - (spread * 0.25)
        return shadow_price, "BUY"
    else:
        shadow_price = mid + (spread * 0.25)
        return shadow_price, "SELL"


def record(
    db,
    *,
    prediction_id,
    market_id,
    pipeline,
    cycle,
    direction,
    estimate,
    conviction,
    regime,
    best_bid,
    best_ask,
    spread,
    mid,
    shadow_price,
    shadow_side,
    taker_price=None,
    taker_action=None,
):
    """Insert one shadow maker row. Fire-and-forget."""
    init_table(db)
    db.execute(
        """
        INSERT INTO shadow_maker (
            prediction_id, market_id, pipeline, cycle, timestamp,
            direction, estimate, conviction, regime,
            best_bid, best_ask, spread, mid,
            shadow_price, shadow_side,
            taker_price, taker_action
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            prediction_id, market_id, pipeline, cycle,
            datetime.now(timezone.utc).isoformat(),
            direction, estimate, conviction, regime,
            best_bid, best_ask, spread, mid,
            shadow_price, shadow_side,
            taker_price, taker_action,
        ),
    )
    db.commit()


# ── Fill Simulation (AC-SM-3) ────────────────────────────────────────


def resolve_shadow_fills(db, pipeline, candle_low, candle_high,
                         candle_close, cycle):
    """Batch-resolve pending shadow orders using candle high/low.

    A shadow BUY at price P is 'filled' if candle_low <= P.
    A shadow SELL at price P is 'filled' if candle_high >= P.

    Adverse selection: for BUY, close < shadow_price = adverse.
    For SELL, close > shadow_price = adverse.

    Only resolves rows where filled IS NULL (pending).
    """
    init_table(db)
    pending = db.execute(
        "SELECT id, shadow_price, shadow_side, direction FROM shadow_maker "
        "WHERE pipeline = ? AND filled IS NULL",
        (pipeline,),
    ).fetchall()

    for row in pending:
        sid = row[0]
        shadow_price = row[1]
        shadow_side = row[2]
        direction = row[3]

        if shadow_side == "BUY":
            filled = 1 if candle_low <= shadow_price else 0
        else:  # SELL
            filled = 1 if candle_high >= shadow_price else 0

        adverse = None
        if filled:
            if shadow_side == "BUY":
                adverse = 1 if candle_close < shadow_price else 0
            else:
                adverse = 1 if candle_close > shadow_price else 0

        db.execute(
            "UPDATE shadow_maker SET filled=?, fill_candle_low=?, "
            "fill_candle_high=?, fill_candle_close=?, adverse=? WHERE id=?",
            (filled, candle_low, candle_high, candle_close, adverse, sid),
        )
    db.commit()


# ── Stats (AC-SM-4) ─────────────────────────────────────────────────


def shadow_stats(db, pipeline, days=7):
    """Compute shadow maker metrics for daily report.

    Returns dict with: n_logged, n_filled, fill_rate, adverse_pct,
    shadow_ehr, or None if no data.
    """
    init_table(db)

    # Count totals
    row = db.execute(
        "SELECT COUNT(*) as n_logged, "
        "SUM(CASE WHEN filled = 1 THEN 1 ELSE 0 END) as n_filled, "
        "SUM(CASE WHEN filled IS NOT NULL THEN 1 ELSE 0 END) as n_resolved "
        "FROM shadow_maker WHERE pipeline = ? "
        "AND timestamp >= datetime('now', ?)",
        (pipeline, f"-{days} days"),
    ).fetchone()

    n_logged = row[0] or 0
    n_filled = row[1] or 0
    n_resolved = row[2] or 0

    if n_resolved == 0:
        return None

    fill_rate = n_filled / n_resolved if n_resolved else 0

    # Adverse selection rate (among fills)
    adv_row = db.execute(
        "SELECT SUM(CASE WHEN adverse = 1 THEN 1 ELSE 0 END) as n_adverse "
        "FROM shadow_maker WHERE pipeline = ? AND filled = 1 "
        "AND timestamp >= datetime('now', ?)",
        (pipeline, f"-{days} days"),
    ).fetchone()
    n_adverse = adv_row[0] or 0
    adverse_pct = n_adverse / n_filled if n_filled else 0

    # Shadow EHR: for filled orders, compute (outcome - shadow_price) weighted
    # Need to join with markets table for outcome resolution
    ehr_row = db.execute(
        "SELECT AVG("
        "  CASE WHEN s.direction = 'UP' THEN (1.0 * m.outcome - s.shadow_price) "
        "       ELSE ((1.0 - m.outcome) - s.shadow_price) END"
        ") as shadow_ehr, "
        "COUNT(*) as n_ehr "
        "FROM shadow_maker s "
        "JOIN markets m ON s.market_id = m.id "
        "WHERE s.pipeline = ? AND s.filled = 1 AND m.resolved = 1 "
        "AND s.timestamp >= datetime('now', ?)",
        (pipeline, f"-{days} days"),
    ).fetchone()

    shadow_ehr = ehr_row[0] if ehr_row and ehr_row[1] > 0 else None

    return {
        "n_logged": n_logged,
        "n_filled": n_filled,
        "n_resolved": n_resolved,
        "fill_rate": round(fill_rate, 3),
        "adverse_pct": round(adverse_pct, 3),
        "shadow_ehr": round(shadow_ehr, 4) if shadow_ehr is not None else None,
    }
