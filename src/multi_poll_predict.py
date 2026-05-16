"""
multi_poll_predict.py — Phase A of the in-cycle prediction-timing study.

After each Bybit 5m candle close, fire N additional predict() calls at
fixed offsets (T+30s through T+270s). Each is computed against the live
WS-cached price at that moment and logged to a separate table. Pure
shadow — does not affect production prediction, conviction gating, or
trade execution.

Why this exists: commit f79e56f21 (2026-04-05) moved dispatch from
GitHub Actions cron (~2:30 natural delay) to VPS WS (~6s latency). Both
BTC and ETH lab WR dropped ~10pp the same week. The lost edge was the
in-flight price information GHA had been picking up. This module makes
that edge measurable so we can decide whether it's worth recovering.

See docs/plans/multi_poll_predict_plan.md for the full plan and
docs/analysis/signal_rehab_2026-04-28.md for the diagnosis that led here.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_log = logging.getLogger("multi_poll_predict")


# ── Configuration ──────────────────────────────────────────────────

# 9 polls spanning a 5-minute cycle. Avoids T+0 (covered by existing
# immediate-dispatch path) and T+300 (next cycle's close).
POLL_OFFSETS_S = [30, 60, 90, 120, 150, 180, 210, 240, 270]

RETENTION_DAYS = 30


# ── Schema ─────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS multi_poll_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle INTEGER,
    cycle_close_at TEXT NOT NULL,
    offset_seconds INTEGER NOT NULL,
    predicted_at TEXT NOT NULL,
    market_id TEXT NOT NULL,
    asset TEXT,
    estimate REAL,
    regime TEXT,
    spot_at_poll REAL,
    in_flight_return_pct REAL,
    poll_succeeded INTEGER DEFAULT 1,
    conviction_score INTEGER,
    market_resolved INTEGER,
    market_outcome INTEGER,
    won INTEGER,
    mkt_mid REAL,
    mkt_best_bid REAL,
    mkt_best_ask REAL,
    mkt_spread REAL,
    orderbook_age_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_mpp_cycle ON multi_poll_predictions(cycle);
CREATE INDEX IF NOT EXISTS idx_mpp_offset
    ON multi_poll_predictions(offset_seconds);
CREATE INDEX IF NOT EXISTS idx_mpp_market_time
    ON multi_poll_predictions(market_id, predicted_at);
"""

# Columns added 2026-04-30 to capture realistic-entry orderbook context
# at poll time. Previously polls only logged the SIGNAL; now they also
# log the price the signal would have transacted against. Phase B's
# realistic-entry P&L analysis depends on these.
_MIGRATION_COLUMNS = [
    ("conviction_score", "INTEGER"),
    ("mkt_mid", "REAL"),
    ("mkt_best_bid", "REAL"),
    ("mkt_best_ask", "REAL"),
    ("mkt_spread", "REAL"),
    ("orderbook_age_ms", "INTEGER"),
]


def init_table(db) -> None:
    """Create multi_poll_predictions table + indexes if not present.

    Idempotent. Also runs forward-migration for the 5 orderbook columns
    added 2026-04-30 — pre-existing rows on the VPS keep NULL values for
    those columns, new rows are written with full context.
    """
    for stmt in SCHEMA_SQL.strip().split(";"):
        s = stmt.strip()
        if s:
            db.execute(s)
    # Forward-migration: add columns to pre-existing tables. SQLite has
    # no "ADD COLUMN IF NOT EXISTS"; we rely on try/except matching the
    # codebase pattern (see src/fill_diagnostic.py:117).
    for col_name, col_type in _MIGRATION_COLUMNS:
        try:
            db.execute(
                f"ALTER TABLE multi_poll_predictions "
                f"ADD COLUMN {col_name} {col_type}"
            )
        except Exception:
            pass  # column already exists
    db.commit()


# ── Retention ──────────────────────────────────────────────────────

def purge_old_polls(
    db,
    retention_days: int = RETENTION_DAYS,
    now_iso: Optional[str] = None,
) -> int:
    """Delete rows older than retention_days. Idempotent.

    `now_iso` is injectable for tests. Defaults to current UTC time.
    Lessons from 2026-04-24 disk-full incident: retention is in code
    next to the writer, not in a never-wired cron.
    """
    if now_iso is None:
        now_iso = datetime.now(timezone.utc).isoformat()
    # Compute cutoff
    try:
        now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
    except Exception as e:
        _log.warning("purge_old_polls: bad now_iso %r: %s", now_iso, e)
        return 0
    from datetime import timedelta

    cutoff = (now - timedelta(days=retention_days)).isoformat()

    cur = db.execute(
        "DELETE FROM multi_poll_predictions WHERE predicted_at < ?",
        (cutoff,),
    )
    db.commit()
    return cur.rowcount or 0


# ── Logging ────────────────────────────────────────────────────────

def log_poll(
    db,
    *,
    cycle: int,
    cycle_close_at: str,
    offset_seconds: int,
    market_id: str,
    asset: str,
    estimate: Optional[float],
    regime_label: Optional[str],
    spot_at_poll: Optional[float],
    in_flight_return_pct: Optional[float] = None,
    poll_succeeded: bool = True,
    predicted_at: Optional[str] = None,
    mkt_mid: Optional[float] = None,
    mkt_best_bid: Optional[float] = None,
    mkt_best_ask: Optional[float] = None,
    mkt_spread: Optional[float] = None,
    orderbook_age_ms: Optional[int] = None,
    conviction_score: Optional[int] = None,
) -> int:
    """Write a single poll row. Pure DB call, no signal computation.

    Orderbook fields (mkt_*, orderbook_age_ms) are optional — write
    NULL when the orderbook cache has no fresh entry for the market's
    YES token. Phase B's realistic-entry analysis filters those out.
    """
    if predicted_at is None:
        predicted_at = datetime.now(timezone.utc).isoformat()
    db.execute(
        """INSERT INTO multi_poll_predictions
           (cycle, cycle_close_at, offset_seconds, predicted_at,
            market_id, asset, estimate, regime, spot_at_poll,
            in_flight_return_pct, poll_succeeded,
            conviction_score,
            mkt_mid, mkt_best_bid, mkt_best_ask, mkt_spread,
            orderbook_age_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            cycle,
            cycle_close_at,
            offset_seconds,
            predicted_at,
            market_id,
            asset,
            estimate,
            regime_label,
            spot_at_poll,
            in_flight_return_pct,
            1 if poll_succeeded else 0,
            conviction_score,
            mkt_mid,
            mkt_best_bid,
            mkt_best_ask,
            mkt_spread,
            orderbook_age_ms,
        ),
    )
    poll_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.commit()
    return poll_id


# ── Signal computation (pure, reuses predict.py functions) ─────────

def compute_poll_predictions(
    candles: list,
    asset: str,
    offset_seconds: int,
    cycle_open_spot: Optional[float] = None,
) -> dict:
    """Compute signal + regime for one poll, given current candles.

    Returns:
      {
        "estimate": float | None,
        "regime_label": str | None,
        "spot_at_poll": float | None,
        "in_flight_return_pct": float | None,  # vs cycle_open_spot
      }

    Uses predict.momentum_signal (BTC) or predict_eth.momentum_signal
    (ETH). Pure function — no DB writes, no network. Suitable to call
    from inside an asyncio task.
    """
    if not candles:
        return {
            "estimate": None,
            "regime_label": None,
            "spot_at_poll": None,
            "in_flight_return_pct": None,
        }

    spot = float(candles[-1]["close"]) if "close" in candles[-1] else None

    # Reuse the signal/regime functions from the per-asset predict modules
    estimate = None
    regime_label = None
    try:
        # Asset-specific signal/regime function names. predict.py uses
        # `compute_regime_from_candles` + `momentum_signal`; predict_eth.py
        # uses `compute_regime_eth` + `momentum_signal_eth` (different
        # vol thresholds calibrated to ETH).
        if asset == "ETH":
            from predict_eth import (
                compute_regime_eth as regime_fn,
                momentum_signal_eth as signal_fn,
            )
        else:  # BTC and any other asset fall through to the BTC functions
            from predict import (
                compute_regime_from_candles as regime_fn,
                momentum_signal as signal_fn,
            )

        regime = regime_fn(candles)
        regime_label = regime.get("label") if regime else None

        signal = signal_fn(candles)
        estimate = signal.get("estimate") if signal else None
    except Exception as e:
        _log.warning(
            "compute_poll_predictions failed for asset=%s offset=%s: %s",
            asset, offset_seconds, e,
        )

    in_flight = None
    if cycle_open_spot and spot:
        try:
            in_flight = (spot - cycle_open_spot) / cycle_open_spot
        except Exception:
            pass

    return {
        "estimate": estimate,
        "regime_label": regime_label,
        "spot_at_poll": spot,
        "in_flight_return_pct": in_flight,
        "signal": signal if "signal" in locals() else None,
        "regime": regime if "regime" in locals() else None,
    }


def compute_poll_conviction(
    signal: Optional[dict],
    regime: Optional[dict],
    *,
    mkt_price: Optional[float] = None,
    asset: str = "BTC",
) -> int:
    """Mirror the existing BTC/ETH conviction gate for multi-poll snapshots.

    This does not change signal logic. It captures the conviction tier the
    delayed execution path needs in order to distinguish executable timing
    evidence from research-grid directional polls.
    """
    if not signal:
        return 0
    if signal.get("conviction_score") is not None:
        return int(signal["conviction_score"])
    if signal.get("conviction_tier") is not None:
        return int(signal["conviction_tier"])

    should_trade = bool(signal.get("should_trade"))
    confidence = signal.get("confidence", "low")
    if should_trade and confidence not in ("medium", "high"):
        return 2
    if not should_trade:
        return 0

    direction = signal.get("direction", "")
    regime_label = (regime or {}).get("label", "")

    if asset == "ETH":
        # Keep ETH conservative; delayed execution promotion is BTC-only.
        return 3 if direction == "UP" else 2

    if "HIGH_VOL" in regime_label and "TRENDING" not in regime_label:
        return 2
    if direction == "DOWN" and "NEUTRAL" in regime_label:
        return 2
    if direction == "UP" and mkt_price is not None:
        try:
            from predict import PRICE_SWEET_SPOT_HIGH, PRICE_SWEET_SPOT_LOW
            if PRICE_SWEET_SPOT_LOW <= float(mkt_price) <= PRICE_SWEET_SPOT_HIGH:
                return 4
        except Exception:
            pass
    return 3


# ── Async orchestrator ─────────────────────────────────────────────

def _get_market_orderbook(market_id: str, db_path: Optional[str] = None):
    """Return (mid, best_bid, best_ask, spread, age_ms) for the YES token
    of a Polymarket market.

    Two-tier lookup, mirrors src/arb_loggers.py:
      1. Live WS OrderbookCache.get_fresh_entry() — best granularity
         (real best_bid/best_ask/spread + sub-second age) but only
         covers the ~50 tokens the WS feed currently subscribes to.
      2. Fallback to markets.price_yes from the gamma snapshot — covers
         every market in the DB (gamma fetch every 5 min) but only
         gives mid; bid/ask/spread stay None.

    Returns (None, None, None, None, None) only if BOTH tiers miss
    (e.g. market not yet in the gamma snapshot, db unavailable, etc).
    Pulled out so tests can monkey-patch a single function.
    """
    # Tier 1: live WS cache (rich data when available)
    yes_token = None
    try:
        from clob_depth import get_clob_tokens_safe
        tokens = get_clob_tokens_safe(market_id)
        if tokens:
            yes_token = tokens.get("yes")
    except Exception:
        tokens = None

    if yes_token:
        try:
            from orderbook_cache import OrderbookCache
            cache = OrderbookCache.load()
            entry = cache.get_fresh_entry(yes_token)
            if entry is not None:
                return (
                    entry.mid,
                    entry.best_bid,
                    entry.best_ask,
                    entry.spread,
                    entry.age_ms(),
                )
        except Exception:
            pass

    # Tier 2: gamma snapshot fallback (mid only, no bid/ask granularity)
    if db_path is None:
        return None, None, None, None, None
    try:
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT price_yes FROM markets WHERE id = ?",
                (market_id,),
            ).fetchone()
        finally:
            conn.close()
        if row and row[0] is not None:
            return float(row[0]), None, None, None, None
    except Exception:
        pass

    return None, None, None, None, None


def _get_active_market_ids(db_path: str, limit: int = 50) -> list[tuple]:
    """Read currently unresolved markets, return list of (id, asset)."""
    db = sqlite3.connect(db_path)
    try:
        rows = db.execute(
            "SELECT id, COALESCE(question, '') FROM markets "
            "WHERE resolved = 0 ORDER BY fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        db.close()

    out = []
    for mid, question in rows:
        # Cheap asset detection from the question text. Multi-poll is
        # asset-aware so each cycle we only process markets matching the
        # closing asset (BTC for BTCUSDT, ETH for ETHUSDT).
        q = question.upper()
        if "BITCOIN" in q or "BTC" in q:
            asset = "BTC"
        elif "ETHEREUM" in q or "ETH" in q:
            asset = "ETH"
        else:
            asset = None
        out.append((mid, asset))
    return out


async def schedule_polls(
    engine,
    db_path: str,
    cycle: int,
    cycle_close_at: str,
    asset: str,
    symbol: str,
    interval: str,
) -> None:
    """Fire len(POLL_OFFSETS_S) polls at fixed offsets after cycle close.

    Runs as a non-awaiting background task spawned from the WS feed —
    failures here MUST NOT propagate to the WS feed loop. All branches
    are wrapped in try/except.

    For each offset:
      1. asyncio.sleep until that offset is reached
      2. Read fresh candles from engine.candle_buffer
      3. compute_poll_predictions() → signal + regime + spot
      4. For each currently-active market matching `asset`, log_poll(...)
    """
    # Ensure schema exists (idempotent). Cheap; mirrors arb_divergence pattern.
    try:
        db = sqlite3.connect(db_path)
        try:
            init_table(db)
        finally:
            db.close()
    except Exception as e:
        _log.warning("schedule_polls: init_table failed: %s", e)
        return  # Without the table, polls would crash on every offset

    try:
        active = [
            (mid, mkt_asset)
            for mid, mkt_asset in _get_active_market_ids(db_path)
            if mkt_asset == asset
        ]
    except Exception as e:
        _log.warning("schedule_polls: _get_active_market_ids failed: %s", e)
        active = []

    cycle_open_spot: Optional[float] = None

    for offset_s in POLL_OFFSETS_S:
        try:
            await asyncio.sleep(offset_s if offset_s > 0 else 0.001)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _log.warning("schedule_polls: sleep failed: %s", e)
            continue

        # One DB connection per poll (cheap) — keeps WAL writers happy
        try:
            db = sqlite3.connect(db_path)
        except Exception as e:
            _log.warning(
                "schedule_polls: db open failed at offset=%s: %s",
                offset_s, e,
            )
            continue

        try:
            try:
                candles = engine.candle_buffer.get_candles(symbol, interval)
            except Exception as e:
                _log.warning(
                    "schedule_polls: candle read failed: %s", e
                )
                candles = []

            if cycle_open_spot is None and candles:
                # The cycle-open spot is the close of the candle that
                # closed at cycle_close_at — i.e., the last confirmed
                # candle when we entered this cycle.
                try:
                    cycle_open_spot = float(candles[-1].get("close"))
                except Exception:
                    cycle_open_spot = None

            try:
                computed = compute_poll_predictions(
                    candles=candles,
                    asset=asset,
                    offset_seconds=offset_s,
                    cycle_open_spot=cycle_open_spot,
                )
                ok = True
            except Exception as e:
                _log.warning(
                    "schedule_polls: compute failed at offset=%s: %s",
                    offset_s, e,
                )
                computed = {
                    "estimate": None,
                    "regime_label": None,
                    "spot_at_poll": None,
                    "in_flight_return_pct": None,
                }
                ok = False

            for market_id, _market_asset in active:
                # Capture orderbook context per market at THIS poll moment.
                # Realistic-entry P&L analysis (Phase B) needs the YES token's
                # best_ask at the time the signal would have triggered an
                # order. Failures fall through to NULL columns; the analyzer
                # filters those out.
                try:
                    mkt_mid, mkt_bid, mkt_ask, mkt_spread, ob_age = (
                        _get_market_orderbook(market_id, db_path=db_path)
                    )
                except Exception as e:
                    _log.warning(
                        "schedule_polls: orderbook read failed for %s: %s",
                        market_id, e,
                    )
                    mkt_mid = mkt_bid = mkt_ask = mkt_spread = ob_age = None

                try:
                    conviction = compute_poll_conviction(
                        computed.get("signal"),
                        computed.get("regime"),
                        mkt_price=mkt_mid,
                        asset=asset,
                    )
                    poll_id = log_poll(
                        db,
                        cycle=cycle,
                        cycle_close_at=cycle_close_at,
                        offset_seconds=offset_s,
                        market_id=market_id,
                        asset=asset,
                        estimate=computed["estimate"],
                        regime_label=computed["regime_label"],
                        spot_at_poll=computed["spot_at_poll"],
                        in_flight_return_pct=computed[
                            "in_flight_return_pct"
                        ],
                        poll_succeeded=ok,
                        mkt_mid=mkt_mid,
                        mkt_best_bid=mkt_bid,
                        mkt_best_ask=mkt_ask,
                        mkt_spread=mkt_spread,
                        orderbook_age_ms=ob_age,
                        conviction_score=conviction,
                    )
                    try:
                        import delayed_execution
                        if asset == "BTC":
                            delayed_execution.process_delayed_poll(
                                db, poll_id, pipeline_name="btc_5m"
                            )
                    except Exception as e:
                        try:
                            row = db.execute(
                                "SELECT * FROM multi_poll_predictions WHERE id = ?",
                                (poll_id,),
                            ).fetchone()
                            if row is not None:
                                delayed_execution.record_unexpected_error(
                                    db,
                                    row,
                                    policy=delayed_execution.current_policy("btc_5m"),
                                    error=e,
                                )
                        except Exception:
                            pass
                        _log.warning(
                            "schedule_polls: delayed candidate failed for %s: %s",
                            market_id, e,
                        )
                except Exception as e:
                    _log.warning(
                        "schedule_polls: log_poll failed for %s: %s",
                        market_id, e,
                    )
        finally:
            try:
                db.close()
            except Exception:
                pass

    _log.debug(
        "schedule_polls done: cycle=%s asset=%s n_offsets=%d n_markets=%d",
        cycle, asset, len(POLL_OFFSETS_S), len(active),
    )
