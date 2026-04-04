"""D3 chart data preparation.

Each function returns a JSON-serializable list/dict that gets embedded
as a data-chart-data attribute on the chart container div.
"""

import json


def prepare_cumulative_pnl(pnl_series):
    """Prepare data for the cumulative P&L area chart.

    Input: list of {"date": "ISO", "value": float}
    Output: same shape, JSON-safe.
    """
    if not pnl_series:
        return []
    return pnl_series


def prepare_waterfall(bet_results):
    """Prepare data for the per-bet waterfall bar chart.

    Input: list of {"date": "ISO", "profit": float, "won": bool, ...}
    Output: same shape with running total added.
    """
    if not bet_results:
        return []
    running = 0
    out = []
    for b in bet_results:
        running += b["profit"]
        out.append({
            "date": b["date"],
            "profit": b["profit"],
            "won": b["won"],
            "cumulative": round(running, 2),
        })
    return out


def prepare_rolling_accuracy(rolling_series):
    """Prepare data for rolling accuracy line chart.

    Input: list of {"date": "ISO", "value": float (0-100)}
    Output: same.
    """
    return rolling_series or []


def to_json(data):
    """Compact JSON for embedding in HTML attributes."""
    return json.dumps(data, separators=(",", ":"))
