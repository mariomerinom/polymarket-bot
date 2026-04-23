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


def _get_candle_buffer_candles(asset: str):
    """Return the engine's rolling 5m candles for the asset. Empty on miss.

    We import lazily because the engine constructs the buffer at boot;
    importing at module load would fail in unit tests.
    """
    try:
        # The engine stores the candle buffer as a global-ish singleton.
        # Find it via the engine module if available.
        import sys
        engine_mod = sys.modules.get("botsy_engine")
        if engine_mod is None:
            return []
        engine_obj = getattr(engine_mod, "_engine_singleton", None)
        if engine_obj is None:
            return []
        symbol = _CANDLE_BUFFER_SYMBOLS.get(asset)
        if symbol is None:
            return []
        return engine_obj.candle_buffer.get_candles(symbol, "5")
    except Exception:
        return []


def _get_pending_candle(asset: str):
    """Return the engine's in-progress 5m candle (open, high, low, latest close).

    The in-progress candle is the right source for `current_spot` — it
    carries the live price updated by WS ticks. Returns None on miss.
    """
    try:
        import sys
        engine_mod = sys.modules.get("botsy_engine")
        if engine_mod is None:
            return None
        engine_obj = getattr(engine_mod, "_engine_singleton", None)
        if engine_obj is None:
            return None
        symbol = _CANDLE_BUFFER_SYMBOLS.get(asset)
        if symbol is None:
            return None
        return engine_obj.candle_buffer._pending.get((symbol, "5"))
    except Exception:
        return None


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
        return entry.mid, entry.best_bid, entry.best_ask, entry.spread, entry.age_ms
    except Exception:
        return None, None, None, None, None


def _get_clob_tokens(market_id: str):
    """Return {yes, no} token ids for a Polymarket market, or None."""
    try:
        from clob_depth import get_clob_tokens_safe
        return get_clob_tokens_safe(market_id)
    except Exception:
        return None


def _get_candle_open_at(candles: list, window_open: datetime) -> Optional[float]:
    """Find the candle whose timestamp matches the window open.

    Polymarket 5m markets align to clock minutes (e.g., open = :00, :05,
    :10...). The Bybit 5m candle with the same start timestamp gives us
    the "open price" reference for the Polymarket settlement.

    Returns the open price of that candle, or None if not found.
    """
    if not candles:
        return None
    target_ms = int(window_open.timestamp() * 1000)
    for c in candles:
        cts = c.get("timestamp_ms")
        if cts is None:
            continue
        # Tolerance of a few seconds for clock alignment
        if abs(int(cts) - target_ms) < 60_000:
            return float(c.get("open", 0)) or None
    return None


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
                              cycle: int) -> int:
    """Iterate markets, log an arb_divergence row for each eligible one.

    Returns the number of rows inserted. Swallows all errors — this is a
    fire-and-forget observability logger that must never break the
    prediction or trade path.

    Args:
        db: the pipeline's predictions.db sqlite3 connection
        pipeline_name: e.g. "btc_5m", "eth_5m"
        markets: list of market dicts (id, question, end_date, price_yes, ...)
        cycle: current cycle number
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

    # Precompute shared state once per cycle
    candles = _get_candle_buffer_candles(asset)
    pending = _get_pending_candle(asset)

    # Build a combined candle list that includes the pending candle. The
    # in-progress 5m candle aligns to the just-started window; its `open`
    # IS the window-open price we need for currently-in-flight markets.
    candles_with_pending = list(candles) if candles else []
    if pending is not None:
        try:
            # Only append if pending has a timestamp and it's newer than
            # the last confirmed candle (avoid duplicates)
            p_ts = pending.get("timestamp_ms")
            last_ts = (candles_with_pending[-1].get("timestamp_ms")
                       if candles_with_pending else None)
            if p_ts and (last_ts is None or int(p_ts) > int(last_ts)):
                candles_with_pending.append(pending)
        except Exception:
            pass

    current_spot = None
    bybit_source = None
    if pending is not None:
        try:
            current_spot = float(pending.get("close") or pending.get("open"))
            bybit_source = "pending"
        except Exception:
            pass
    if current_spot is None and candles:
        try:
            current_spot = float(candles[-1].get("close"))
            bybit_source = "last_confirmed"
        except Exception:
            pass

    closes = [c.get("close") for c in candles if c.get("close") is not None]
    realized_vol = arb_divergence.compute_realized_vol(closes)

    regime_label, regime_autocorr, regime_vol = _get_5m_regime(candles)
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

            # Open spot from the aligned Bybit 5m candle. Check both
            # confirmed candles AND the pending in-progress candle — for
            # windows that just opened, the aligned candle is still pending.
            open_spot = _get_candle_open_at(candles_with_pending, window_open)

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
