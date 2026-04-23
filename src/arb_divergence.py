"""
arb_divergence.py — Phase 0 of Polymarket ↔ Bybit cross-venue arbitrage.

Logs every divergence between Polymarket's implied UP/DOWN probability
and the Bybit-derived fair probability, on every cycle, for all eligible
open markets. Zero trading, zero capital, pure observation.

MARKET MODEL — important correction to the plan:

Polymarket's crypto 5m/15m markets are "Up or Down" direction markets,
NOT "above $X strike" markets. A market like "Bitcoin Up or Down -
April 23, 10:55AM-11:00AM ET" resolves YES if the close at 11:00 is
greater than the open at 10:55.

The fair probability of YES at observation time t within a window
[t_open, t_close] is:

    fair_p_YES = Φ( r_so_far / (σ × √(ttm_remaining / window_total)) )

where:
    r_so_far = (current_spot - open_spot) / open_spot   (log-return)
    σ        = realized vol at appropriate timescale
    ttm_remaining = seconds until window close
    window_total  = total window length (300s for 5m, 900s for 15m)

Near window open, fair_p ≈ 0.5. Near window close, fair_p is a near-step
function around sign(r_so_far).

REGIME CONTEXT: every row records both the 5m regime (from predict's
compute_regime_from_candles) and the daily regime (from asset_daily.db)
so decisions can be sliced by market-state. The plan's regime-aware
observation gate is enforced at the decision step, not at logging.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from statistics import stdev
from typing import Optional

# ── Schema ──────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS arb_divergence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    cycle INTEGER,
    pipeline TEXT NOT NULL,
    market_id TEXT NOT NULL,
    market_class TEXT,
    asset TEXT,
    direction_sense TEXT,
    window_open_at TEXT,
    window_close_at TEXT,
    window_total_seconds REAL,
    time_to_expiry_seconds REAL,
    window_has_opened INTEGER,
    bybit_spot REAL,
    bybit_source TEXT,
    open_spot REAL,
    r_so_far REAL,
    realized_vol_annual REAL,
    sigma_window REAL,
    fair_p REAL,
    mkt_mid REAL,
    mkt_best_bid REAL,
    mkt_best_ask REAL,
    mkt_spread REAL,
    orderbook_age_ms INTEGER,
    divergence REAL,
    abs_divergence REAL,
    would_arb_side TEXT,
    would_arb_edge REAL,
    regime_label TEXT,
    regime_autocorr REAL,
    regime_vol REAL,
    daily_regime_label TEXT,
    daily_range_zscore REAL
);
CREATE INDEX IF NOT EXISTS idx_arb_divergence_timestamp
    ON arb_divergence(timestamp);
CREATE INDEX IF NOT EXISTS idx_arb_divergence_market
    ON arb_divergence(market_id, timestamp);
"""


def init_table(db) -> None:
    """Create arb_divergence table if not present. Idempotent."""
    for stmt in SCHEMA_SQL.strip().split(";"):
        s = stmt.strip()
        if s:
            db.execute(s)
    db.commit()


# ── Question parsing ────────────────────────────────────────────────

# Matches: "Bitcoin Up or Down - April 23, 10:55AM-11:00AM ET"
# Groups: asset, month, day, h1, m1, ampm1, h2, m2, ampm2
_QUESTION_RE = re.compile(
    r"^(Bitcoin|Ethereum) Up or Down - "
    r"(?P<month>\w+) (?P<day>\d+), "
    r"(?P<h1>\d+):(?P<m1>\d+)(?P<ampm1>AM|PM)-"
    r"(?P<h2>\d+):(?P<m2>\d+)(?P<ampm2>AM|PM) ET$"
)

_MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11,
    "December": 12,
}


def _ampm_to_24h(hour: int, ampm: str) -> int:
    if ampm == "AM":
        return 0 if hour == 12 else hour
    return hour if hour == 12 else hour + 12


def parse_polymarket_market(question: str, end_date: str) -> Optional[dict]:
    """Parse an "Up or Down" Polymarket market.

    Returns a dict with keys:
        asset: "BTC" | "ETH"
        market_class: "5m" | "15m" | None
        window_open_at: datetime UTC
        window_close_at: datetime UTC (matches end_date for sanity)
        window_total_seconds: 300 | 900

    Returns None on parse failure. Implementation is defensive — partial
    matches fall through to None so the caller can log a NULL-class row
    for audit without crashing the pipeline.
    """
    if not question or not end_date:
        return None

    m = _QUESTION_RE.match(question)
    if not m:
        return None

    asset_raw = m.group(1)
    asset = "BTC" if asset_raw == "Bitcoin" else "ETH"

    # Derive year from end_date (Polymarket markets don't repeat dates
    # within a year, and parsing without year is ambiguous)
    try:
        end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None

    month = _MONTHS.get(m.group("month"))
    if not month:
        return None
    day = int(m.group("day"))

    h1 = _ampm_to_24h(int(m.group("h1")), m.group("ampm1"))
    m1 = int(m.group("m1"))
    h2 = _ampm_to_24h(int(m.group("h2")), m.group("ampm2"))
    m2 = int(m.group("m2"))

    # ET is UTC-5 (standard) or UTC-4 (daylight). We approximate using end_date
    # as truth: compute window from end_date backward.
    # Window total = end - start in minutes
    et_close_minutes = h2 * 60 + m2
    et_open_minutes = h1 * 60 + m1
    # Handle AM-to-PM spans; assume close > open in same day ET
    if et_close_minutes < et_open_minutes:
        # AM-PM boundary — shouldn't happen for 5m/15m windows but be safe
        et_close_minutes += 24 * 60
    window_total_seconds = (et_close_minutes - et_open_minutes) * 60

    if window_total_seconds <= 0 or window_total_seconds > 3600:
        return None

    window_close = end_dt.astimezone(timezone.utc)
    window_open = window_close - timedelta(seconds=window_total_seconds)

    market_class = None
    if window_total_seconds == 300:
        market_class = "5m"
    elif window_total_seconds == 900:
        market_class = "15m"
    elif window_total_seconds == 3600:
        market_class = "hourly"

    return {
        "asset": asset,
        "market_class": market_class,
        "window_open_at": window_open,
        "window_close_at": window_close,
        "window_total_seconds": float(window_total_seconds),
    }


# ── Fair-p computation ─────────────────────────────────────────────


def _norm_cdf(x: float) -> float:
    """Standard normal CDF. Uses math.erf for stdlib-only dependency."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def compute_realized_vol(closes: list, periods_per_year: float = 52_560.0) -> Optional[float]:
    """Annualized realized vol from a list of 5m closes.

    periods_per_year default 52_560 = 288 × 365 (5m per day × days).

    Returns None if insufficient data (< 5 closes) or zero variance.
    """
    closes = [float(c) for c in closes if c is not None and c > 0]
    if len(closes) < 5:
        return None
    try:
        log_returns = [
            math.log(closes[i] / closes[i - 1])
            for i in range(1, len(closes))
        ]
        if len(log_returns) < 2:
            return None
        per_period_sd = stdev(log_returns)
        if per_period_sd <= 0:
            return None
        return per_period_sd * math.sqrt(periods_per_year)
    except (ValueError, ZeroDivisionError):
        return None


def compute_fair_p_up_down(
    open_spot: float,
    current_spot: float,
    ttm_remaining_seconds: float,
    window_total_seconds: float,
    realized_vol_annual: float,
) -> Optional[float]:
    """P(close > open) at observation time, given intra-window progress.

    Uses geometric-Brownian no-drift approximation:
        close ~ current_spot × exp(σ × √(ttm/1yr) × Z)
        Want: P(close > open) = Φ( ln(current/open) / (σ × √(ttm/1yr)) )

    Returns None on degenerate inputs.

    Clips output to [0.001, 0.999] to avoid degenerate divergences.
    """
    # Validate required numeric inputs (but allow negative ttm_remaining —
    # that's a valid "already past expiry" state handled below).
    if (
        open_spot is None
        or current_spot is None
        or realized_vol_annual is None
        or open_spot <= 0
        or current_spot <= 0
        or realized_vol_annual <= 0
        or window_total_seconds <= 0
    ):
        return None

    # If window has closed (ttm_remaining <= 0), return step function
    if ttm_remaining_seconds <= 0:
        return 1.0 if current_spot > open_spot else 0.0

    # If window hasn't opened yet, r_so_far is undefined — return 0.5 as the
    # uninformative prior. Caller decides whether to log.
    if ttm_remaining_seconds >= window_total_seconds:
        return 0.5

    seconds_per_year = 365.0 * 24.0 * 3600.0
    ttm_years = ttm_remaining_seconds / seconds_per_year
    sigma_window = realized_vol_annual * math.sqrt(ttm_years)

    if sigma_window <= 0:
        return None

    r_so_far = math.log(current_spot / open_spot)
    z = r_so_far / sigma_window
    p = _norm_cdf(z)
    return max(0.001, min(0.999, p))


# ── Arb-side + edge helpers ────────────────────────────────────────


def compute_arb_side_and_edge(
    fair_p: float,
    mkt_mid: float,
    mkt_spread: Optional[float],
    fee_rate: float = 0.02,
) -> tuple:
    """Given fair and market, compute which side to take and the net edge.

    Returns (side, edge) where:
        side = "buy_poly" (YES is underpriced) |
               "sell_poly" (YES is overpriced) |
               None (not actionable)
        edge = |fair_p - mkt_mid| - spread/2 - fee_rate
               (None if not actionable)

    fee_rate is a conservative fixed taker-fee proxy (Polymarket's formula
    is more complex; 2¢ is close for 0.30-0.70 range).
    """
    if fair_p is None or mkt_mid is None:
        return None, None
    diff = fair_p - mkt_mid
    half_spread = (mkt_spread or 0.0) / 2.0
    net = abs(diff) - half_spread - fee_rate
    if net <= 0:
        return None, net
    return ("buy_poly" if diff > 0 else "sell_poly"), net


# ── Record ──────────────────────────────────────────────────────────


def record(db, **kwargs) -> None:
    """Insert one arb_divergence row. Fire-and-forget."""
    init_table(db)
    cols = [
        "timestamp", "cycle", "pipeline", "market_id",
        "market_class", "asset", "direction_sense",
        "window_open_at", "window_close_at", "window_total_seconds",
        "time_to_expiry_seconds", "window_has_opened",
        "bybit_spot", "bybit_source",
        "open_spot", "r_so_far",
        "realized_vol_annual", "sigma_window",
        "fair_p",
        "mkt_mid", "mkt_best_bid", "mkt_best_ask", "mkt_spread",
        "orderbook_age_ms",
        "divergence", "abs_divergence",
        "would_arb_side", "would_arb_edge",
        "regime_label", "regime_autocorr", "regime_vol",
        "daily_regime_label", "daily_range_zscore",
    ]
    placeholders = ",".join("?" * len(cols))
    values = tuple(kwargs.get(c) for c in cols)
    db.execute(
        f"INSERT INTO arb_divergence ({','.join(cols)}) VALUES ({placeholders})",
        values,
    )
    db.commit()
