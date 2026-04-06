"""
ci_run_15m.py — BTC 15-minute pipeline (thin wrapper).

Delegates to polymarket_pipeline.run_polymarket_pipeline() for the
shared lifecycle. Pipeline-specific config is passed as parameters.

Uses 5m candles as atomic signal source with loose_mode=True for
higher-resolution streak detection and 5m sibling confirmation.
"""

from fetch_markets import init_db_15m, fetch_active_markets_15m, DB_PATH_15M
from predict import run_predictions
from btc_data import fetch_btc_candles
from polymarket_pipeline import run_polymarket_pipeline


def _demote_down_neutral(db, cycle):
    """DOWN+NEUTRAL has no edge on 15m (48% WR on 27 bets, Apr 2026).
    Demote post-prediction. Symmetric with 5m.
    HIGH_VOL/NEUTRAL+DOWN allowed through (64% WR on 50 bets on 5m).
    """
    demoted = db.execute("""
        UPDATE predictions SET conviction_score = 2
        WHERE cycle = ? AND conviction_score >= 3
        AND regime LIKE '%NEUTRAL%'
        AND regime NOT LIKE 'HIGH_VOL%'
        AND json_extract(reasoning, '$.signal.direction') = 'DOWN'
    """, (cycle,)).rowcount
    db.commit()
    if demoted:
        print(f"  [15m] Demoted {demoted} DOWN+MEDIUM_VOL/NEUTRAL prediction(s) to conv=2")


def main(candle_data=None, indicators=None):
    run_polymarket_pipeline(
        pipeline_name="btc_15m",
        db_init_fn=init_db_15m,
        db_path=DB_PATH_15M,
        market_fetch_fn=fetch_active_markets_15m,
        candle_fetch_fn=fetch_btc_candles,
        predict_fn=run_predictions,
        predict_kwargs={"loose_mode": True, "db_path": str(DB_PATH_15M)},
        post_predict_hook=_demote_down_neutral,
        asset_label="BTC 15m",
        price_fmt=",.0f",
        candle_data=candle_data,
        indicators=indicators,
    )


if __name__ == "__main__":
    main()
