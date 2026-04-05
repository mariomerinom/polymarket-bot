"""
dashboard_server.py — Flask server for all polymarket-bot dashboards.

Serves dashboards dynamically from SQLite databases.
Replaces static HTML generation + GitHub Pages hosting.

Run: python src/dashboard_server.py
Serves on http://127.0.0.1:5050
"""

import sys
import os
import time
import threading
from pathlib import Path

# Ensure src/ is on the path for dashboard_v2 and config imports
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, Response, jsonify
from dashboard_v2 import build_html

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Route table — matches exact CI runner calls
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent / "data"

DASHBOARDS = {
    "btc_5m": {
        "db": str(DATA_DIR / "predictions.db"),
        "subtitle": "BTC 5-Minute Momentum (Live)",
    },
    "btc_15m": {
        "db": str(DATA_DIR / "predictions_15m.db"),
        "subtitle": "BTC 15-Minute Momentum",
    },
    "eth_5m": {
        "db": str(DATA_DIR / "predictions_eth.db"),
        "subtitle": "ETH 5-Minute Momentum",
    },
    "kalshi": {
        "db": str(DATA_DIR / "predictions_kalshi.db"),
        "subtitle": "Kalshi BTC (Phase 0 \u2014 Paper)",
    },
    "bybit": {
        "db": str(DATA_DIR / "predictions_bybit.db"),
        "subtitle": "Bybit BTCUSDT Perps",
    },
}

# ---------------------------------------------------------------------------
# TTL cache — 60s per dashboard, thread-safe
# ---------------------------------------------------------------------------

CACHE_TTL = 60
_cache = {}  # key -> (html_str, expire_time)
_cache_lock = threading.Lock()


def _get_html(key):
    """Return cached HTML or regenerate."""
    now = time.time()
    with _cache_lock:
        if key in _cache and _cache[key][1] > now:
            return _cache[key][0]

    # Generate outside lock to avoid blocking other routes
    cfg = DASHBOARDS[key]
    html = build_html(db_path=cfg["db"], subtitle=cfg["subtitle"])

    with _cache_lock:
        _cache[key] = (html, time.time() + CACHE_TTL)
    return html


def _serve(key):
    return Response(_get_html(key), mimetype="text/html")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
@app.route("/index.html")
def btc_5m():
    return _serve("btc_5m")


@app.route("/15m.html")
def btc_15m():
    return _serve("btc_15m")


@app.route("/eth.html")
def eth_5m():
    return _serve("eth_5m")


@app.route("/kalshi.html")
def kalshi():
    return _serve("kalshi")


@app.route("/bybit-perps.html")
def bybit():
    return _serve("bybit")


@app.route("/health")
def health():
    """Health check — returns DB file status and cache state."""
    dbs = {}
    for key, cfg in DASHBOARDS.items():
        p = Path(cfg["db"])
        dbs[key] = {
            "exists": p.exists(),
            "size_kb": round(p.stat().st_size / 1024) if p.exists() else 0,
            "cached": key in _cache and _cache[key][1] > time.time(),
        }
    return jsonify({"status": "ok", "databases": dbs})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("DASHBOARD_PORT", "5050"))
    print(f"Dashboard server: http://127.0.0.1:{port}")
    print(f"Data dir: {DATA_DIR}")
    app.run(host="127.0.0.1", port=port, debug=False)
