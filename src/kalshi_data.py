"""
kalshi_data.py — BTC candle data for Kalshi pipeline.

Thin wrapper around btc_data.fetch_btc_candles(). BTC is BTC regardless of
venue — the momentum signal was trained on Kraken/Coinbase candles and must
see the same data distribution.

Optionally attaches Kalshi orderbook metadata for Phase 0 analysis logging
(does NOT affect predictions).
"""

from btc_data import fetch_btc_candles
from kalshi_markets import fetch_kalshi_orderbook, _is_mock_mode


def fetch_kalshi_candles(interval="15m", limit=20, kalshi_ticker=None):
    """
    Fetch BTC candles for the Kalshi pipeline.

    Returns the same dict as btc_data.fetch_btc_candles() with an optional
    'kalshi_orderbook' key for analysis logging.
    """
    data = fetch_btc_candles(interval=interval, limit=limit)
    if not data:
        return None

    # Attach Kalshi orderbook metadata if a ticker is provided
    if kalshi_ticker:
        ob = fetch_kalshi_orderbook(kalshi_ticker)
        if ob:
            data["kalshi_orderbook"] = ob

    return data


if __name__ == "__main__":
    print("Kalshi Data — candle fetch test")
    data = fetch_kalshi_candles(interval="15m", limit=12)
    if data:
        print(f"  BTC: ${data['current_price']:,.2f}")
        print(f"  1h change: {data['1h_change_pct']:+.3f}%")
        print(f"  Trend: {data['trend']}")
        print(f"  Candles: {len(data['candles'])}")
    else:
        print("  No data returned")
