"""
hl_data.py — Minimal data layer for Hyperliquid perpetual futures pipeline.

Candle data comes from the engine (piggybacking on Bybit spot WS events).
This module only provides:
  - Mark price fetch (for accurate limit order placement)
  - Funding rate fetch (for logging / position cost calculation)

Uses the Hyperliquid public REST API (no auth needed for reads).
"""

import requests
from config import _env

HL_BASE_URL = _env("HL_BASE_URL", "https://api.hyperliquid.xyz")
HL_INFO_URL = f"{HL_BASE_URL}/info"
API_TIMEOUT_HL = 10


def fetch_hl_mark_price(coin="BTC"):
    """Fetch current mark price from Hyperliquid for order placement.

    Uses the /info endpoint with allMids action — no auth required.
    """
    try:
        resp = requests.post(HL_INFO_URL, json={
            "type": "allMids",
        }, timeout=API_TIMEOUT_HL)
        resp.raise_for_status()
        data = resp.json()

        # allMids returns {"BTC": "84123.5", "ETH": "3456.7", ...}
        if isinstance(data, dict) and coin in data:
            return float(data[coin])

        return None
    except Exception as e:
        print(f"  [hl_data] Mark price error: {e}")
        return None


def fetch_hl_funding_rate(coin="BTC"):
    """Fetch latest funding rate from Hyperliquid.

    Hyperliquid uses 1-hour funding (vs Bybit's 8-hour).
    """
    try:
        resp = requests.post(HL_INFO_URL, json={
            "type": "meta",
        }, timeout=API_TIMEOUT_HL)
        resp.raise_for_status()
        data = resp.json()

        # Meta returns universe with funding info per asset
        universe = data.get("universe", [])
        for asset in universe:
            if asset.get("name") == coin:
                return {
                    "rate": float(asset.get("funding", 0)),
                    "interval_hours": 1,  # Hyperliquid uses 1h funding
                }

        return None
    except Exception as e:
        print(f"  [hl_data] Funding rate error: {e}")
        return None


if __name__ == "__main__":
    print("Hyperliquid Data — test")
    mark = fetch_hl_mark_price()
    print(f"  Mark price: ${mark:,.2f}" if mark else "  Mark price: N/A")
    funding = fetch_hl_funding_rate()
    if funding:
        print(f"  Funding rate: {funding['rate']:.6f} (1h)")
