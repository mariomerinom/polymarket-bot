"""
regime_gate.py — Daily-regime pre-bet gate for BTC 5m Polymarket signal.

Reads the most recent BTC `range_zscore` (and `velocity_zscore`) from
`data/asset_daily.db` and decides whether the current cycle should be
allowed to land at conv >= 3, or downgraded to conv 2 (shadow / no bet).

Why this exists: a join of 484 resolved BTC 5m conv>=3 bets against the
180-day backfilled `asset_daily` table showed a perfectly monotonic
4-bucket WR decay by `range_zscore`:

    r_z < -0.5  → 72.7% WR (N=194)
    -0.5..0.5   → 64.7% WR (N=136)
     0.5..1.5   → 58.8% WR (N=80)
    r_z >= 1.5  → 38.9% WR (N=36)

The gate threshold `r_z < 0.5` lifts kept WR from 65% baseline to 69.4%
(N=330) while skipping 116 bets that average 52.6%. Same gate fails on
the Bybit perp simulator, so the edge is Polymarket-specific (mispricing
on calm vs violent days), not a property of the underlying tape.

The gate uses the *prior* UTC day's zscore — today's full-day stats
aren't known until midnight UTC, so we lag by one day. This is
conservative but honest: no peeking at the day in progress.

Counterfactual logging: gated predictions still record `would_have_bet`
in reasoning_data with the gate metadata, so 30 days from now we can
measure whether the rule was real or week-of-April overfit.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
DAILY_DB = ROOT / "data" / "asset_daily.db"

# Threshold derived from the 484-bet OOS join (2026-04-08), then
# revalidated under the prior-day lag (the live gate uses yesterday's
# zscore because today's full-day stats aren't known until midnight UTC).
#
# Same-day join: monotonic 4-bucket WR decay 72.7→64.7→58.8→38.9 by r_z.
# Lagged join:   only the extreme bucket separates — calm/norm/wide all
#                cluster at 63-66% WR, but r_z >= 1.5 collapses to 42.1%
#                (N=38). The honest gate is "skip only extreme range
#                aftershock days," not "skip everything above normal."
#
# Tighten or loosen only after a forward-shadow window confirms.
RANGE_Z_GATE = 1.5
VELOCITY_Z_GATE = 1.0  # not currently enforced; reserved for future tightening


def get_btc_regime(asset: str = "BTC", asof: Optional[datetime] = None) -> Optional[dict]:
    """Return the most recent (date, v_z, r_z) row for `asset` from
    asset_daily.db, or None if the table is empty / missing.

    `asof` defaults to now-UTC. Tests / historical replay can pass a
    fixed datetime so the gate evaluates against that point in time
    instead of wall-clock now.

    Walks back from `asof - 1 day` up to 7 days to tolerate one or two
    missed daily-rollup runs without disabling the gate entirely.
    """
    if not DAILY_DB.exists():
        return None
    try:
        db = sqlite3.connect(DAILY_DB)
        ref = (asof or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
        for offset in range(1, 8):
            d = (ref - timedelta(days=offset)).isoformat()
            row = db.execute(
                "SELECT date, velocity_zscore, range_zscore, trend_label "
                "FROM asset_daily WHERE asset=? AND date=?",
                (asset, d),
            ).fetchone()
            if row and row[1] is not None and row[2] is not None:
                return {
                    "asof_date": row[0],
                    "velocity_zscore": row[1],
                    "range_zscore": row[2],
                    "trend_label": row[3],
                }
        db.close()
    except Exception:
        return None
    return None


def evaluate_btc_gate(asof: Optional[datetime] = None) -> dict:
    """Compute the gate state at the given moment (default: now-UTC).

    Returns a dict with:
        gated: bool — True if conv >= 3 should be blocked
        reason: short string for logging
        regime: the underlying asset_daily row (or None if no data)

    If asset_daily has no recent row, the gate is OPEN (fail-open). This
    means a missed daily backfill cannot silently halt the live pipeline.
    """
    if os.environ.get("BTC_REGIME_GATE_DISABLED") == "1":
        return {
            "gated": False, "reason": "gate_disabled_env", "regime": None,
            "r_z_gate": RANGE_Z_GATE,
        }
    regime = get_btc_regime("BTC", asof=asof)
    if regime is None:
        return {
            "gated": False, "reason": "no_regime_data", "regime": None,
            "r_z_gate": RANGE_Z_GATE,
        }
    r_z = regime["range_zscore"]
    if r_z >= RANGE_Z_GATE:
        return {
            "gated": True,
            "reason": f"range_zscore_{r_z:.2f}>={RANGE_Z_GATE}",
            "regime": regime,
            "r_z_gate": RANGE_Z_GATE,
        }
    return {
        "gated": False,
        "reason": f"range_zscore_{r_z:.2f}<{RANGE_Z_GATE}",
        "regime": regime,
        "r_z_gate": RANGE_Z_GATE,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(evaluate_btc_gate(), indent=2, default=str))
