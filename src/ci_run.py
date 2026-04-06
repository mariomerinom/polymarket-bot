"""
ci_run.py — BTC 5-minute pipeline (thin wrapper).

Delegates to polymarket_pipeline.run_polymarket_pipeline() for the
shared lifecycle. Pipeline-specific config is passed as parameters.
"""

from fetch_markets import init_db, fetch_active_markets, DB_PATH
from predict import run_predictions
from btc_data import fetch_btc_candles
from polymarket_pipeline import run_polymarket_pipeline


def _generate_dashboard():
    from generate_dashboard import generate
    generate()


def main(candle_data=None, indicators=None):
    run_polymarket_pipeline(
        pipeline_name="btc_5m",
        db_init_fn=init_db,
        db_path=DB_PATH,
        market_fetch_fn=fetch_active_markets,
        candle_fetch_fn=fetch_btc_candles,
        predict_fn=run_predictions,
        dashboard_fn=_generate_dashboard,
        asset_label="BTC",
        price_fmt=",.0f",
        candle_data=candle_data,
        indicators=indicators,
    )


if __name__ == "__main__":
    main()
