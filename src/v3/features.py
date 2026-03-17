"""
V3 Stage 2 — Feature Engineering

Computes ~30 raw features from:
1. BTC candle data (micro-TA signals)
2. Polymarket order book (microstructure)
3. Time features
4. Regime context

Returns a flat dict of features ready for ML model input.
"""

import math
import statistics
from datetime import datetime, timezone


def compute_features(candle_data, book_snapshot, market, regime=None):
    """
    Compute all features for one market at one point in time.

    Args:
        candle_data: dict from btc_data.fetch_btc_candles() with candles + summary
        book_snapshot: dict from data_fetch.fetch_clob_book() with midpoint, spread, depth
        market: dict with end_date, price_yes, etc.
        regime: dict from compute_regime() or None

    Returns:
        dict of feature_name -> float value
    """
    features = {}

    # ── BTC Candle Features ─────────────────────────────────────────
    if candle_data:
        candles = candle_data.get("candles", [])
        closes = [c["close"] for c in candles]

        # Already computed by btc_data._compute_summary()
        features["range_position"] = candle_data.get("range_position", 0.5)
        features["volume_ratio"] = candle_data.get("last_volume_ratio", 1.0)
        features["range_ratio"] = candle_data.get("last_range_ratio", 1.0)
        features["compression"] = 1.0 if candle_data.get("last_3_range_shrinking") else 0.0
        features["volatility"] = candle_data.get("volatility", 0.0)
        features["hour_change_pct"] = candle_data.get("1h_change_pct", 0.0)

        # Consecutive streak (signed: positive=UP, negative=DOWN)
        consec = candle_data.get("consecutive_direction", 0)
        direction = candle_data.get("consecutive_dir_label", "UP")
        features["consecutive_streak"] = consec if direction == "UP" else -consec

        # Wick ratios
        features["wick_upper_ratio"] = candle_data.get("last_wick_upper_ratio", 0.0)
        features["wick_lower_ratio"] = candle_data.get("last_wick_lower_ratio", 0.0)

        # Candle pattern (one-hot encode the most common)
        pattern = candle_data.get("last_candle_pattern", "none")
        features["pattern_doji"] = 1.0 if pattern == "doji" else 0.0
        features["pattern_hammer"] = 1.0 if pattern in ("hammer", "inv_hammer") else 0.0
        features["pattern_engulfing_bull"] = 1.0 if pattern == "engulfing_bull" else 0.0
        features["pattern_engulfing_bear"] = 1.0 if pattern == "engulfing_bear" else 0.0
        features["pattern_inside_bar"] = 1.0 if pattern == "inside_bar" else 0.0

        # RSI(5) — compute from last 5 closes
        if len(closes) >= 6:
            features["rsi_5"] = _compute_rsi(closes, period=5)
        else:
            features["rsi_5"] = 50.0

        # Bollinger %B (20-period is too long for 12-20 candles, use available)
        if len(closes) >= 5:
            features["bollinger_pct_b"] = _compute_bollinger_pct_b(closes)
        else:
            features["bollinger_pct_b"] = 0.5

        # ATR(5) normalized by price
        if len(candles) >= 5:
            features["atr_5_norm"] = _compute_atr_normalized(candles, period=5)
        else:
            features["atr_5_norm"] = 0.0

        # Recent momentum: sum of last 3 candle body_pct
        if len(candles) >= 3:
            features["momentum_3"] = sum(c["body_pct"] for c in candles[-3:])
        else:
            features["momentum_3"] = 0.0

        # Up count ratio in window
        ups = candle_data.get("up_count", 0)
        downs = candle_data.get("down_count", 0)
        total = ups + downs
        features["up_ratio"] = ups / total if total > 0 else 0.5

        # Autocorrelation of returns (trending vs mean-reverting)
        if len(closes) >= 5:
            features["return_autocorr"] = _compute_return_autocorr(closes)
        else:
            features["return_autocorr"] = 0.0

    else:
        # No candle data — fill with neutral defaults
        for key in ["range_position", "volume_ratio", "range_ratio", "compression",
                     "volatility", "hour_change_pct", "consecutive_streak",
                     "wick_upper_ratio", "wick_lower_ratio",
                     "pattern_doji", "pattern_hammer", "pattern_engulfing_bull",
                     "pattern_engulfing_bear", "pattern_inside_bar",
                     "rsi_5", "bollinger_pct_b", "atr_5_norm", "momentum_3",
                     "up_ratio", "return_autocorr"]:
            features[key] = 0.5 if key in ("range_position", "up_ratio", "rsi_5", "bollinger_pct_b") else 0.0

    # ── Polymarket Microstructure Features ──────────────────────────
    if book_snapshot:
        features["spread_pct"] = book_snapshot.get("spread_pct", 0.0)
        features["depth_imbalance"] = book_snapshot.get("depth_imbalance", 0.0)
        features["bid_depth"] = book_snapshot.get("bid_depth_5pct", 0.0)
        features["ask_depth"] = book_snapshot.get("ask_depth_5pct", 0.0)

        midpoint = book_snapshot.get("midpoint", 0.5)
        features["midpoint_distance_from_half"] = midpoint - 0.5
    else:
        features["spread_pct"] = 0.0
        features["depth_imbalance"] = 0.0
        features["bid_depth"] = 0.0
        features["ask_depth"] = 0.0
        features["midpoint_distance_from_half"] = 0.0

    # Time remaining until market close (minutes)
    if market and market.get("end_date"):
        try:
            end_dt = datetime.fromisoformat(
                market["end_date"].replace("Z", "+00:00")
            )
            now = datetime.now(timezone.utc)
            remaining = (end_dt - now).total_seconds() / 60.0
            features["time_remaining_min"] = max(0, remaining)
        except (ValueError, TypeError):
            features["time_remaining_min"] = 2.5  # default mid-window
    else:
        features["time_remaining_min"] = 2.5

    # ── Time Features ───────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    hour_frac = now.hour + now.minute / 60.0
    features["hour_sin"] = math.sin(2 * math.pi * hour_frac / 24)
    features["hour_cos"] = math.cos(2 * math.pi * hour_frac / 24)
    features["day_of_week"] = now.weekday()  # 0=Mon, 6=Sun
    features["is_weekend"] = 1.0 if now.weekday() >= 5 else 0.0

    # ── Regime ──────────────────────────────────────────────────────
    if regime:
        features["regime_volatility"] = regime.get("volatility_state", 1)  # 0=low, 1=med, 2=high
        features["regime_autocorr"] = regime.get("autocorrelation", 0.0)
    else:
        features["regime_volatility"] = 1
        features["regime_autocorr"] = 0.0

    return features


# ── Technical Indicator Helpers ─────────────────────────────────────────

def _compute_rsi(closes, period=5):
    """Compute RSI from closes."""
    if len(closes) < period + 1:
        return 50.0

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = deltas[-period:]

    gains = [d for d in recent if d > 0]
    losses = [-d for d in recent if d < 0]

    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _compute_bollinger_pct_b(closes, period=None):
    """Compute Bollinger %B. Uses all available closes if period not specified."""
    if period is None:
        period = len(closes)
    window = closes[-period:]
    if len(window) < 2:
        return 0.5

    sma = sum(window) / len(window)
    std = statistics.stdev(window) if len(window) >= 2 else 0
    if std == 0:
        return 0.5

    upper = sma + 2 * std
    lower = sma - 2 * std
    band_width = upper - lower
    if band_width == 0:
        return 0.5

    return (closes[-1] - lower) / band_width


def _compute_atr_normalized(candles, period=5):
    """Compute ATR normalized by current price."""
    recent = candles[-period:]
    if not recent:
        return 0.0

    true_ranges = []
    for i, c in enumerate(recent):
        high_low = c["high"] - c["low"]
        if i > 0:
            prev_close = recent[i - 1]["close"]
            high_prev = abs(c["high"] - prev_close)
            low_prev = abs(c["low"] - prev_close)
            tr = max(high_low, high_prev, low_prev)
        else:
            tr = high_low
        true_ranges.append(tr)

    atr = sum(true_ranges) / len(true_ranges)
    price = candles[-1]["close"]
    return atr / price if price > 0 else 0.0


def _compute_return_autocorr(closes):
    """Compute lag-1 autocorrelation of returns. Positive = trending, negative = mean-reverting."""
    if len(closes) < 4:
        return 0.0

    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
    n = len(returns)
    if n < 3:
        return 0.0

    mean_r = sum(returns) / n
    var = sum((r - mean_r) ** 2 for r in returns) / n
    if var == 0:
        return 0.0

    cov = sum((returns[i] - mean_r) * (returns[i - 1] - mean_r) for i in range(1, n)) / (n - 1)
    return cov / var


# ── Feature List ────────────────────────────────────────────────────────

def feature_names():
    """Return ordered list of all feature names."""
    return [
        # BTC candle (20 features)
        "range_position", "volume_ratio", "range_ratio", "compression",
        "volatility", "hour_change_pct", "consecutive_streak",
        "wick_upper_ratio", "wick_lower_ratio",
        "pattern_doji", "pattern_hammer", "pattern_engulfing_bull",
        "pattern_engulfing_bear", "pattern_inside_bar",
        "rsi_5", "bollinger_pct_b", "atr_5_norm", "momentum_3",
        "up_ratio", "return_autocorr",
        # Polymarket microstructure (5 features)
        "spread_pct", "depth_imbalance", "bid_depth", "ask_depth",
        "midpoint_distance_from_half",
        # Time (5 features)
        "time_remaining_min", "hour_sin", "hour_cos", "day_of_week", "is_weekend",
        # Regime (2 features)
        "regime_volatility", "regime_autocorr",
    ]


def features_to_row(features):
    """Convert features dict to ordered list for ML model input."""
    return [features.get(name, 0.0) for name in feature_names()]


# ── CLI ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from src.btc_data import fetch_btc_candles
    from src.v3.data_fetch import fetch_active_markets, fetch_clob_book
    from src.v3.regime import compute_regime

    print("V3 Feature Engineering — Stage 2 Demo\n")

    # Fetch live data
    btc = fetch_btc_candles(limit=20)
    markets = fetch_active_markets()
    regime = compute_regime(btc)

    print(f"BTC: ${btc['current_price']:,.0f} | Regime: {regime}")
    print(f"Markets: {len(markets)}\n")

    print(f"{'Feature':<30s} {'Value':>10s}")
    print("-" * 42)

    # Compute features for first active near-50/50 market
    for m in markets:
        if 0.35 < m["price_yes"] < 0.65:
            book = fetch_clob_book(m["clob_token_yes"])
            feats = compute_features(btc, book, m, regime)

            for name in feature_names():
                val = feats.get(name, 0.0)
                if isinstance(val, float):
                    print(f"  {name:<28s} {val:>10.4f}")
                else:
                    print(f"  {name:<28s} {val:>10}")

            print(f"\nTotal features: {len(feats)}")
            print(f"Market: {m['question'][:60]}")
            break
