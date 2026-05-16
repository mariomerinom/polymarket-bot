"""
arb_loggers.py — Per-cycle orchestrator for arb_divergence logging.

Called once per polymarket cycle after the prediction + trade steps have
completed. Iterates open Polymarket markets, pulls Bybit live price +
realized vol from the candle buffer, computes fair_p, compares to the
Polymarket orderbook mid, records a row per market.

Safety: all work wrapped in try/except. Never raise to the caller — the
hot path must stay clean even if arb logging fails.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import arb_divergence

_log = logging.getLogger("arb_loggers")

# Lazy imports to avoid cost if arb logger is never called
_CANDLE_BUFFER_SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
}


def _get_candles_from_disk_snapshot(asset: str):
    """Read the engine's persisted candle buffer from disk.

    The engine saves `data/candle_buffer.json` every 60 seconds. For arb
    logging (observational, not trading-path), up-to-60s staleness is
    acceptable. Cleaner than reaching into engine module state.

    Returns a list of candle dicts (oldest first). Empty on miss.
    """
    try:
        import json
        snap_path = Path(__file__).parent.parent / "data" / "candle_buffer.json"
        if not snap_path.exists():
            return []
        snap = json.loads(snap_path.read_text())
        symbol = _CANDLE_BUFFER_SYMBOLS.get(asset)
        if symbol is None:
            return []
        # Key format: "{symbol}:{tf}" per candle_buffer.save_to_disk
        bufs = snap.get("buffers", {})
        return bufs.get(f"{symbol}:5", [])
    except Exception:
        return []


def _get_orderbook_mid(token_id: str):
    """Return (mid, best_bid, best_ask, spread, age_ms) for a Polymarket token.
    (None, None, None, None, None) on miss.
    """
    try:
        from orderbook_cache import OrderbookCache
        cache = OrderbookCache.load()
        entry = cache.get_fresh_entry(token_id)
        if entry is None:
            return None, None, None, None, None
        return entry.mid, entry.best_bid, entry.best_ask, entry.spread, entry.age_ms()
    except Exception:
        return None, None, None, None, None


def _get_clob_tokens(market_id: str):
    """Return {yes, no} token ids for a Polymarket market, or None."""
    try:
        from clob_depth import get_clob_tokens_safe
        return get_clob_tokens_safe(market_id)
    except Exception:
        return None


def _get_candle_open_at(candles: list, window_open: datetime,
                        max_staleness_seconds: int = 15 * 60) -> Optional[float]:
    """Approximate price at window_open from confirmed Bybit 5m candles.

    Ideal: the 5m candle starting at (window_open - 5min) has `close`
    equal to price at window_open. In continuous trading, close of
    candle N = open of candle N+1, minus sub-second microstructure noise.

    Reality: the disk snapshot has gaps — engine restarts drop the
    then-pending candle, leaving missing slots. So exact-prior lookup
    fails ~30% of the time.

    Workaround: find the most recent confirmed candle with
    `timestamp_ms <= window_open - 5min`, and use its close. Within
    max_staleness_seconds of the target, accept it. This trades a bit
    of price accuracy (a few minutes of staleness) for much higher
    coverage — fine for Phase 0 observation.

    Returns None if no candle within the staleness window exists.
    """
    if not candles:
        return None
    target_ms = int(window_open.timestamp() * 1000)
    # Candles at or before window_open. We sort descending by timestamp
    # and take the first whose timestamp is <= target_ms.
    candidates = []
    for c in candles:
        cts = c.get("timestamp_ms")
        if cts is None:
            continue
        cts_int = int(cts)
        # The candle's CLOSE corresponds to (timestamp_ms + 300_000). We
        # want candles whose close was at or before window_open.
        if cts_int + 300_000 <= target_ms + 60_000:  # 60s tolerance
            candidates.append((cts_int, c))
    if not candidates:
        return None
    # Pick the one whose close is closest to (i.e., just before) window_open
    candidates.sort(key=lambda x: x[0], reverse=True)
    latest_ts, latest_c = candidates[0]
    # Staleness check: don't use a candle more than 15 min old
    close_ms = latest_ts + 300_000
    if target_ms - close_ms > max_staleness_seconds * 1000:
        return None
    return float(latest_c.get("close", 0)) or None


def _get_daily_regime(asset: str):
    """Return (daily_regime_label, daily_range_zscore) from asset_daily.db.

    Looks up today's UTC row. Returns (None, None) on miss.
    """
    try:
        import sqlite3
        daily_db_path = Path(__file__).parent.parent / "data" / "asset_daily.db"
        if not daily_db_path.exists():
            return None, None
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with sqlite3.connect(f"file:{daily_db_path}?mode=ro", uri=True) as conn:
            row = conn.execute(
                "SELECT trend_label, range_zscore FROM asset_daily "
                "WHERE asset = ? AND date = ?",
                (asset, today),
            ).fetchone()
        if not row:
            return None, None
        return row[0], row[1]
    except Exception:
        return None, None


def _get_5m_regime(candles: list):
    """Compute 5m regime from candle buffer. Returns (label, autocorr, vol).

    Delegates to predict.compute_regime_from_candles if available.
    """
    if not candles or len(candles) < 10:
        return None, None, None
    try:
        from predict import compute_regime_from_candles
        regime = compute_regime_from_candles(candles)
        return (
            regime.get("label"),
            regime.get("autocorrelation"),
            regime.get("volatility"),
        )
    except Exception:
        return None, None, None


# ── Main orchestrator ──────────────────────────────────────────────


def log_divergences_for_cycle(db, pipeline_name: str, markets: list,
                              cycle: int, candles: Optional[list] = None) -> int:
    """Iterate markets, log an arb_divergence row for each eligible one.

    Returns the number of rows inserted. Swallows all errors — this is a
    fire-and-forget observability logger that must never break the
    prediction or trade path.

    Args:
        db: the pipeline's predictions.db sqlite3 connection
        pipeline_name: e.g. "btc_5m", "eth_5m"
        markets: list of market dicts (id, question, end_date, price_yes, ...)
        cycle: current cycle number
        candles: optional list of candle dicts to use. If None, fall back
                 to reading the engine's persisted candle_buffer.json
                 snapshot (up-to-60s stale, acceptable for observational
                 logging).
    """
    if not markets:
        return 0

    # Determine asset from pipeline name (btc_5m → BTC, eth_5m → ETH)
    asset = "BTC" if "btc" in pipeline_name.lower() else "ETH"
    try:
        arb_divergence.init_table(db)
    except Exception as e:
        _log.debug(f"arb_divergence.init_table failed: {e}")
        return 0

    # Dual candle sources with different schemas:
    #
    # (a) caller-passed `candles` (Kraken/Coinbase via candle_fetch_fn in
    #     the prediction pipeline): have `time` as HH:MM string but NO
    #     `timestamp_ms`. Good for regime + realized_vol (which use
    #     sequential closes, not absolute timestamps).
    #
    # (b) engine's persisted Bybit buffer (data/candle_buffer.json): has
    #     `timestamp_ms` at 5m boundaries, exactly what _get_candle_open_at
    #     needs for window-aligned open_spot lookup.
    #
    # Use both: (a) for stats, (b) for the open_spot alignment.
    stats_candles = candles if candles else _get_candles_from_disk_snapshot(asset)
    aligned_candles = _get_candles_from_disk_snapshot(asset)

    current_spot = None
    bybit_source = None
    if stats_candles:
        try:
            current_spot = float(stats_candles[-1].get("close"))
            bybit_source = "caller" if candles else "disk_snapshot"
        except Exception:
            pass

    closes = [c.get("close") for c in stats_candles if c.get("close") is not None]
    realized_vol = arb_divergence.compute_realized_vol(closes)

    regime_label, regime_autocorr, regime_vol = _get_5m_regime(stats_candles)
    daily_regime_label, daily_range_zscore = _get_daily_regime(asset)

    now = datetime.now(timezone.utc)
    n_logged = 0

    for market in markets:
        try:
            market_id = market.get("id")
            question = market.get("question")
            end_date = market.get("end_date")
            if not market_id or not question or not end_date:
                continue

            parsed = arb_divergence.parse_polymarket_market(question, end_date)
            if parsed is None:
                # Log a NULL-class row for audit
                arb_divergence.record(
                    db,
                    timestamp=now.isoformat(),
                    cycle=cycle,
                    pipeline=pipeline_name,
                    market_id=market_id,
                    market_class=None,
                    asset=asset,
                    direction_sense=None,
                    window_open_at=None,
                    window_close_at=None,
                    window_total_seconds=None,
                    time_to_expiry_seconds=None,
                    window_has_opened=None,
                    bybit_spot=current_spot,
                    bybit_source=bybit_source,
                    open_spot=None,
                    r_so_far=None,
                    realized_vol_annual=realized_vol,
                    sigma_window=None,
                    fair_p=None,
                    mkt_mid=None,
                    mkt_best_bid=None,
                    mkt_best_ask=None,
                    mkt_spread=None,
                    orderbook_age_ms=None,
                    divergence=None,
                    abs_divergence=None,
                    would_arb_side=None,
                    would_arb_edge=None,
                    regime_label=regime_label,
                    regime_autocorr=regime_autocorr,
                    regime_vol=regime_vol,
                    daily_regime_label=daily_regime_label,
                    daily_range_zscore=daily_range_zscore,
                )
                n_logged += 1
                continue

            window_open = parsed["window_open_at"]
            window_close = parsed["window_close_at"]
            window_total = parsed["window_total_seconds"]
            ttm_remaining = (window_close - now).total_seconds()
            window_has_opened = 1 if ttm_remaining < window_total else 0

            # Open spot from the aligned Bybit 5m candle (has timestamp_ms).
            open_spot = _get_candle_open_at(aligned_candles, window_open)

            # Compute fair_p
            fair_p = None
            r_so_far = None
            sigma_window = None
            if (
                open_spot and current_spot and realized_vol
                and window_has_opened and ttm_remaining > 0
            ):
                import math
                r_so_far = math.log(current_spot / open_spot) if open_spot > 0 else None
                seconds_per_year = 365.0 * 24.0 * 3600.0
                sigma_window = realized_vol * math.sqrt(
                    ttm_remaining / seconds_per_year
                )
                fair_p = arb_divergence.compute_fair_p_up_down(
                    open_spot=open_spot,
                    current_spot=current_spot,
                    ttm_remaining_seconds=ttm_remaining,
                    window_total_seconds=window_total,
                    realized_vol_annual=realized_vol,
                )

            # Market orderbook
            tokens = _get_clob_tokens(market_id)
            yes_token = tokens.get("yes") if tokens else None
            mkt_mid, mkt_bid, mkt_ask, mkt_spread, orderbook_age_ms = (
                _get_orderbook_mid(yes_token) if yes_token
                else (None, None, None, None, None)
            )
            # Fallback to market.price_yes if WS cache missed
            if mkt_mid is None:
                try:
                    mkt_mid = float(market.get("price_yes")) if market.get("price_yes") is not None else None
                except Exception:
                    mkt_mid = None

            # Divergence + arb side
            divergence = None
            abs_divergence = None
            would_arb_side = None
            would_arb_edge = None
            if fair_p is not None and mkt_mid is not None:
                divergence = fair_p - mkt_mid
                abs_divergence = abs(divergence)
                would_arb_side, would_arb_edge = arb_divergence.compute_arb_side_and_edge(
                    fair_p, mkt_mid, mkt_spread
                )

            arb_divergence.record(
                db,
                timestamp=now.isoformat(),
                cycle=cycle,
                pipeline=pipeline_name,
                market_id=market_id,
                market_class=parsed["market_class"],
                asset=parsed["asset"],
                direction_sense="up_or_down",
                window_open_at=window_open.isoformat(),
                window_close_at=window_close.isoformat(),
                window_total_seconds=window_total,
                time_to_expiry_seconds=ttm_remaining,
                window_has_opened=window_has_opened,
                bybit_spot=current_spot,
                bybit_source=bybit_source,
                open_spot=open_spot,
                r_so_far=r_so_far,
                realized_vol_annual=realized_vol,
                sigma_window=sigma_window,
                fair_p=fair_p,
                mkt_mid=mkt_mid,
                mkt_best_bid=mkt_bid,
                mkt_best_ask=mkt_ask,
                mkt_spread=mkt_spread,
                orderbook_age_ms=orderbook_age_ms,
                divergence=divergence,
                abs_divergence=abs_divergence,
                would_arb_side=would_arb_side,
                would_arb_edge=would_arb_edge,
                regime_label=regime_label,
                regime_autocorr=regime_autocorr,
                regime_vol=regime_vol,
                daily_regime_label=daily_regime_label,
                daily_range_zscore=daily_range_zscore,
            )
            n_logged += 1
        except Exception as e:
            _log.debug(f"arb_divergence row failed for {market.get('id')}: {e}")
            continue

    return n_logged
