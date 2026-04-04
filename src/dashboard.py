"""
dashboard.py — Web dashboard for the Polymarket autoresearch bot.

Run: python dashboard.py (from src/ directory)
Serves on http://localhost:5050

This is a shim that re-exports build_html() from dashboard_v2.
All CI runners import `from dashboard import build_html`.
"""

from pathlib import Path
from dashboard_v2 import build_html  # noqa: F401
from dashboard_v2.compat import (  # noqa: F401
    compute_pnl, compute_ensemble_pnl, compute_ev_breakeven,
    build_distribution_svg, is_correct,
)
from dashboard_v2.data import get_db, get_pipeline_summary as get_status  # noqa: F401

DB_PATH = Path(__file__).parent.parent / "data" / "predictions.db"

try:
    from flask import Flask, Response
    app = Flask(__name__)
except ImportError:
    app = None

if app:
    @app.route("/")
    def index():
        html = build_html()
        return Response(html, mimetype="text/html")

if __name__ == "__main__":
    if app is None:
        print("Flask not installed. Use generate_dashboard.py instead.")
    else:
        print(f"Dashboard: http://localhost:5050")
        print(f"Database:  {DB_PATH}")
        app.run(host="0.0.0.0", port=5050, debug=True)
