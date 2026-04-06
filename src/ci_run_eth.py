"""
ci_run_eth.py — ETH 5-minute pipeline (thin wrapper).

Delegates to polymarket_pipeline.run_polymarket_pipeline() for the
shared lifecycle. Pipeline-specific config is passed as parameters.
"""

from fetch_markets import init_db_eth, fetch_active_markets_eth, DB_PATH_ETH
from predict_eth import run_predictions_eth
from eth_data import fetch_eth_candles
from polymarket_pipeline import run_polymarket_pipeline


def main(candle_data=None, indicators=None):
    run_polymarket_pipeline(
        pipeline_name="eth_5m",
        db_init_fn=init_db_eth,
        db_path=DB_PATH_ETH,
        market_fetch_fn=fetch_active_markets_eth,
        candle_fetch_fn=fetch_eth_candles,
        predict_fn=run_predictions_eth,
        predict_kwargs={"db_path": DB_PATH_ETH},
        asset_label="ETH",
        price_fmt=",.2f",
        candle_data=candle_data,
        indicators=indicators,
    )


if __name__ == "__main__":
    main()
