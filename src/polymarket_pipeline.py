"""
polymarket_pipeline.py — Unified lifecycle for all Polymarket pipelines.

Extracted from ci_run.py, ci_run_eth.py, ci_run_15m.py which were 90%
identical. Each ci_run file becomes a thin config wrapper calling this.

Pipeline isolation: trading mode is resolved per-pipeline via pipeline_name,
never from the trade.TRADING_ENABLED global. (Incident #66, 2026-04-06)
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import DEFAULT_CANDLE_LIMIT, SHADOW_CANDLE_LIMIT
from score import auto_resolve, calculate_brier_scores, print_scorecard
from trade import execute_trades, is_kill_switched, get_trading_summary, ensure_orders_table
from pipeline_utils import get_next_cycle, has_unpredicted_market
from pipeline_control import load_pipeline_config, is_pipeline_live
from fetch_markets import store_markets


def run_polymarket_pipeline(
    pipeline_name,          # "btc_5m", "btc_15m", "eth_5m"
    db_init_fn,             # init_db / init_db_15m / init_db_eth
    db_path,                # DB_PATH / DB_PATH_15M / DB_PATH_ETH
    market_fetch_fn,        # fetch_active_markets / _15m / _eth
    candle_fetch_fn,        # fetch_btc_candles / fetch_eth_candles
    predict_fn,             # run_predictions / run_predictions_eth
    predict_kwargs=None,    # extra kwargs: loose_mode, db_path
    post_predict_hook=None, # e.g. 15m DOWN+NEUTRAL demotion
    shadow_pipeline_tag=None,
    dashboard_fn=None,      # generate() or None
    price_fmt=",.0f",       # ",.0f" for BTC, ",.2f" for ETH
    asset_label="BTC",      # for log messages
    candle_data=None,       # engine-provided candle data
    indicators=None,        # engine-provided TA indicators
):
    """Run one cycle of a Polymarket pipeline.

    This is the shared lifecycle for BTC 5m, BTC 15m, and ETH 5m.
    Pipeline-specific behavior is injected via function parameters.
    """
    if predict_kwargs is None:
        predict_kwargs = {}
    if shadow_pipeline_tag is None:
        shadow_pipeline_tag = pipeline_name

    label = pipeline_name.upper().replace("_", " ")

    # 0. Pipeline control
    cfg = load_pipeline_config(pipeline_name)
    if cfg["mode"] == "paused":
        print(f"{label} pipeline PAUSED: {cfg['notes']}")
        return

    # 1. Init DB
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = db_init_fn()

    # 2. Fetch markets
    print(f"[{label} 1/5] Fetching markets...")
    try:
        markets = market_fetch_fn()
        store_markets(db, markets)
        print(f"  {len(markets)} active {asset_label} markets")
    except Exception as e:
        print(f"  Fetch error: {e}")
        markets = []

    # 3. Auto-resolve
    print(f"[{label} 2/5] Auto-resolving...")
    resolved = auto_resolve(db)
    if resolved:
        print(f"  Resolved {resolved} market(s)")

    if not markets and not has_unpredicted_market(db):
        print(f"No active {asset_label} markets. Exiting early.")
        db.close()
        if dashboard_fn:
            dashboard_fn()
        return

    # 4. Predict
    cycle = get_next_cycle(db)
    print(f"[{label} 3/5] Predictions (cycle {cycle})...")
    price_data = candle_data
    if price_data is None:
        price_data = candle_fetch_fn(limit=DEFAULT_CANDLE_LIMIT)
    if price_data:
        price = price_data['current_price']
        change = price_data.get('1h_change_pct', 0)
        trend = price_data.get('trend', '?')
        print(f"  {asset_label}: ${price:{price_fmt}} | 1h: {change:+.3f}% | Trend: {trend}")
    else:
        print(f"  Warning: {asset_label} price data unavailable")

    if has_unpredicted_market(db):
        db.close()
        try:
            predict_fn(cycle=cycle, market_limit=1,
                       indicators=indicators,
                       **_resolve_predict_data_kwarg(predict_fn, price_data, asset_label),
                       **predict_kwargs)
        except Exception as e:
            print(f"  Prediction error: {e}")
        db = sqlite3.connect(db_path)

        # Post-prediction hook (e.g. 15m DOWN+NEUTRAL demotion)
        if post_predict_hook:
            post_predict_hook(db, cycle)
    else:
        print(f"  No unpredicted {asset_label} markets")

    # 5. Shadow indicators
    try:
        from shadow_indicators import shadow_log_indicators
        shadow_candles = candle_fetch_fn(limit=SHADOW_CANDLE_LIMIT)
        if shadow_candles and shadow_candles.get("candles"):
            shadow = shadow_log_indicators(db, cycle, candles=shadow_candles["candles"])
            if shadow:
                print(f"    [SHADOW] {shadow.get('summary', 'logged')}")
    except Exception as e:
        print(f"    [SHADOW] skipped: {e}")

    # 6. Shadow conviction scorer
    try:
        from shadow_conviction_scorer import shadow_log_cycle
        if price_data and price_data.get("candles"):
            shadow_log_cycle(db, cycle, price_data["candles"], shadow_pipeline_tag)
    except Exception as e:
        print(f"    [shadow] skipped: {e}")

    # 7. Trade execution — mode resolved per-pipeline, NOT from global
    if is_kill_switched():
        print(f"[{label} 3b/5] Trading KILLED — kill switch active")
    else:
        print(f"[{label} 3b/5] Trade execution...")
        try:
            ensure_orders_table(db)
            orders = execute_trades(db, cycle, pipeline_name=pipeline_name)
            summary = get_trading_summary(db, pipeline_name=pipeline_name)
            print(f"  Mode: {summary['mode']} | Bet size: ${summary['bet_size']:.0f} | "
                  f"Today: {summary['total_orders']} orders, ${summary['total_wagered']:.0f} wagered, "
                  f"${summary['total_pnl']:+.0f} P&L")
        except Exception as e:
            print(f"  Trade execution error: {e}")

    # 8. Score
    print(f"[{label} 4/5] Scoring...")
    results = calculate_brier_scores(db)
    if results:
        print_scorecard(results)
    else:
        print("  No resolved markets to score yet")

    # 9. Integrity checks
    try:
        from pipeline_integrity import run_integrity_checks
        results = run_integrity_checks(db, pipeline=pipeline_name, cycle=cycle,
                                       api_ok=price_data is not None,
                                       data_fetched=bool(price_data))
        if isinstance(results, list):
            for r in results:
                if r["status"] != "OK":
                    print(f"  [{r['status']}] {r['check_name']}: {r['detail']}")
        elif results:
            print(f"  Integrity: {results}")
    except Exception as e:
        print(f"  [INTEGRITY] check failed: {e}")

    db.close()

    # 10. Dashboard
    print(f"[{label} 5/5] Generating dashboard...")
    if dashboard_fn:
        dashboard_fn()
    else:
        print("  Dashboard served dynamically — skipping static HTML generation")

    print(f"\n{label} CI run complete.")


def _resolve_predict_data_kwarg(predict_fn, price_data, asset_label):
    """Resolve the data kwarg name for the prediction function.

    BTC pipelines use btc_data=, ETH uses eth_data=.
    """
    import inspect
    sig = inspect.signature(predict_fn)
    if "eth_data" in sig.parameters:
        return {"eth_data": price_data}
    elif "btc_data" in sig.parameters:
        return {"btc_data": price_data}
    else:
        return {}
