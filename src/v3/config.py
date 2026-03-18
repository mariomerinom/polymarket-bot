"""
V3 configuration — API endpoints, thresholds, constants.
"""

# --- API Endpoints ---
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
KRAKEN_OHLC = "https://api.kraken.com/0/public/OHLC"
COINBASE_CANDLES = "https://api.exchange.coinbase.com/products/BTC-USD/candles"

# --- Polling ---
POLL_INTERVAL_S = 60
CANDLE_LOOKBACK = 20

# --- Filters ---
MIN_MARKET_VOLUME = 10_000  # $10K 24h volume to avoid manipulation
MIN_DEPTH_USD = 5_000       # $5K depth within ±5% of mid
MAX_SIZE_PCT_DEPTH = 0.005  # Max 0.5% of visible depth per trade

# --- Fees & Friction ---
ROUND_TRIP_FEE = 0.015      # 1.5% taker fee round trip
SLIPPAGE_BUFFER = 0.02      # 1-3 cent adverse slippage (use 2 cent avg)
MIN_EDGE = 0.05             # 5% minimum edge after friction

# --- Database ---
DB_NAME = "v3.db"
