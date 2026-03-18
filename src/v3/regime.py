"""
V3 Stage 2 — Regime Detection

Classifies current BTC market regime from candle data:
1. Volatility regime: Low / Medium / High (based on ATR percentile)
2. Autocorrelation: trending vs mean-reverting

Used as features and as a filter (some strategies only work in certain regimes).
"""

import statistics


def compute_regime(candle_data):
    """
    Compute regime from candle data.

    Args:
        candle_data: dict from btc_data.fetch_btc_candles() with candles + summary

    Returns:
        dict with:
            volatility_state: 0=low, 1=medium, 2=high
            volatility_raw: raw volatility value
            autocorrelation: lag-1 return autocorrelation
            label: human-readable string
    """
    if not candle_data:
        return {
            "volatility_state": 1,
            "volatility_raw": 0.0,
            "autocorrelation": 0.0,
            "label": "UNKNOWN (no data)",
        }

    candles = candle_data.get("candles", [])
    closes = [c["close"] for c in candles]
    volatility = candle_data.get("volatility", 0.0)

    # ── Volatility regime ───────────────────────────────────────────
    # Use percentile thresholds calibrated to 5-min BTC candles
    # Typical 5-min BTC volatility: 0.02-0.15% per candle
    # Low: < 0.05%, Medium: 0.05-0.12%, High: > 0.12%
    if volatility < 0.05:
        vol_state = 0
        vol_label = "LOW"
    elif volatility < 0.12:
        vol_state = 1
        vol_label = "MEDIUM"
    else:
        vol_state = 2
        vol_label = "HIGH"

    # ── Autocorrelation ─────────────────────────────────────────────
    autocorr = 0.0
    if len(closes) >= 5:
        returns = [(closes[i] - closes[i - 1]) / closes[i - 1]
                   for i in range(1, len(closes))]
        n = len(returns)
        if n >= 3:
            mean_r = sum(returns) / n
            var = sum((r - mean_r) ** 2 for r in returns) / n
            if var > 0:
                cov = sum(
                    (returns[i] - mean_r) * (returns[i - 1] - mean_r)
                    for i in range(1, n)
                ) / (n - 1)
                autocorr = cov / var

    if autocorr > 0.15:
        trend_label = "TRENDING"
    elif autocorr < -0.15:
        trend_label = "MEAN_REVERTING"
    else:
        trend_label = "NEUTRAL"

    label = f"{vol_label}_VOL / {trend_label}"

    return {
        "volatility_state": vol_state,
        "volatility_raw": round(volatility, 6),
        "autocorrelation": round(autocorr, 4),
        "label": label,
    }


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from src.btc_data import fetch_btc_candles

    print("V3 Regime Detection Demo\n")
    btc = fetch_btc_candles(limit=20)
    if btc:
        regime = compute_regime(btc)
        print(f"BTC: ${btc['current_price']:,.0f}")
        print(f"Volatility: {btc['volatility']:.4f}% per 5-min candle")
        print(f"Regime: {regime['label']}")
        print(f"  vol_state: {regime['volatility_state']} (0=low, 1=med, 2=high)")
        print(f"  autocorr:  {regime['autocorrelation']:+.4f} (>0.15=trending, <-0.15=reverting)")
    else:
        print("Failed to fetch candle data")
