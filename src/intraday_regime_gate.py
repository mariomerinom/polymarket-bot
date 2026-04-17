"""
intraday_regime_gate.py — Throttle conviction on abnormal-range intraday days.

Evidence (docs/analysis/regime_correlation_2026-04-16.md):
  Apr 7: BTC range_zscore +2.90 → btc_5m −$193 at 39% WR on 36 bets
  Apr 13: BTC range_zscore +1.83 → btc_5m −$27 at 40% WR on 5 bets
  Apr 11: BTC range_zscore −1.30 → btc_5m −$24 at 47% WR (low-range day)

Pattern: when intraday range is ≥1.5σ above the 30-day historical mean,
5m momentum signals get chopped up by intraday reversals. Systematic
net loss.

This gate uses TODAY's in-progress range (not yesterday's completed row,
which was the failure mode of the reverted btc_daily_regime_gate #68).
Morning exemption prevents premature gating before enough candles form.

Usage in predict():
    from intraday_regime_gate import evaluate_intraday_range_gate
    result = evaluate_intraday_range_gate(
        candles=recent_candles,      # list of candle dicts from buffer
        asset="BTC",
        asof_utc=datetime.now(timezone.utc),
        historical_ranges_pct=[...], # last 30 days from asset_daily
    )
    if result["gated"]:
        conviction = 2  # demote
"""

from __future__ import annotations

from datetime import datetime
from statistics import mean, stdev
from typing import Optional


# ── Defaults (tunable via env or caller) ────────────────────────────

DEFAULT_THRESHOLD_Z = 1.5
DEFAULT_MORNING_CUTOFF_UTC_HOUR = 12  # no gating before 12:00 UTC
MIN_CANDLES_REQUIRED = 5              # need at least 5 candles of today's data
MIN_HISTORY_SAMPLES = 5               # need at least 5 prior days of range_pct


def evaluate_intraday_range_gate(
    candles: list,
    asset: str,
    asof_utc: datetime,
    historical_ranges_pct: list,
    threshold_z: float = DEFAULT_THRESHOLD_Z,
    morning_cutoff_utc_hour: int = DEFAULT_MORNING_CUTOFF_UTC_HOUR,
) -> dict:
    """Return gate decision for today's in-progress intraday range.

    Args:
        candles: today's 5m candle dicts (chronological, each with
                 high/low/open); typically the engine's ring buffer
                 filtered to asof_utc.date()
        asset: "BTC" or "ETH" (for log messages)
        asof_utc: current UTC time (used for morning exemption)
        historical_ranges_pct: last 30 days of `range_pct` from asset_daily,
                               excluding today
        threshold_z: gate trips when in-progress range_z ≥ this
        morning_cutoff_utc_hour: no gating before this hour (UTC)

    Returns:
        dict with:
          gated (bool)
          reason (str) — why gated or not
          range_z (float | None) — computed z-score, or None if unavailable
    """
    # Morning exemption — not enough intraday data yet
    if asof_utc.hour < morning_cutoff_utc_hour:
        return {
            "gated": False,
            "reason": f"morning_exemption (utc_hour={asof_utc.hour}<{morning_cutoff_utc_hour})",
            "range_z": None,
        }

    if not candles or len(candles) < MIN_CANDLES_REQUIRED:
        return {
            "gated": False,
            "reason": f"insufficient_candles ({len(candles) if candles else 0}<{MIN_CANDLES_REQUIRED})",
            "range_z": None,
        }

    # Filter historical list — defensive: drop None, keep positive
    hist = [r for r in (historical_ranges_pct or []) if r is not None and r > 0]
    if len(hist) < MIN_HISTORY_SAMPLES:
        return {
            "gated": False,
            "reason": f"insufficient_history ({len(hist)}<{MIN_HISTORY_SAMPLES})",
            "range_z": None,
        }

    # Today's in-progress range (intraday high - intraday low, pct of open)
    try:
        range_high = max(float(c["high"]) for c in candles)
        range_low = min(float(c["low"]) for c in candles)
        open_price = float(candles[0]["open"])
    except (KeyError, TypeError, ValueError) as e:
        return {
            "gated": False,
            "reason": f"candle_parse_error ({e})",
            "range_z": None,
        }

    if open_price <= 0:
        return {"gated": False, "reason": "bad_open_price", "range_z": None}

    range_pct_so_far = (range_high - range_low) / open_price

    # Z-score vs 30-day historical distribution
    mu = mean(hist)
    try:
        sd = stdev(hist)
    except Exception:
        sd = 0.0
    if sd <= 0:
        return {
            "gated": False,
            "reason": "zero_std_in_history",
            "range_z": None,
        }

    z = (range_pct_so_far - mu) / sd

    if z >= threshold_z:
        return {
            "gated": True,
            "reason": f"range_z_{z:+.2f}>=+{threshold_z:.1f}",
            "range_z": round(z, 3),
        }
    return {
        "gated": False,
        "reason": f"range_z_{z:+.2f}<+{threshold_z:.1f}",
        "range_z": round(z, 3),
    }


def fetch_historical_ranges_pct(
    db, asset: str, exclude_date: Optional[str] = None, days: int = 30,
) -> list:
    """Read last `days` rows of range_pct from asset_daily for `asset`.

    Excludes the current date (so today's partial row doesn't contaminate
    the historical reference). Returns a list of floats; empty on error
    or missing table.

    Args:
        db: sqlite3.Connection to predictions.db (where asset_daily lives)
            OR to asset_daily.db if separate — caller decides
        asset: "BTC", "ETH"
        exclude_date: YYYY-MM-DD — omit rows at this date
        days: how many trailing rows to return
    """
    try:
        params = [asset]
        where = "WHERE asset = ?"
        if exclude_date:
            where += " AND date != ?"
            params.append(exclude_date)
        sql = (
            f"SELECT range_pct FROM asset_daily {where} "
            f"ORDER BY date DESC LIMIT ?"
        )
        params.append(days)
        rows = db.execute(sql, tuple(params)).fetchall()
        return [r[0] for r in rows if r[0] is not None]
    except Exception:
        return []
