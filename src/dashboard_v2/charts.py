"""D3 chart data preparation.

Each function returns a JSON-serializable list/dict that gets embedded
as a data-chart-data attribute on the chart container div.
"""

import json

# Max data points per chart — keeps HTML attributes under ~20KB
MAX_CHART_POINTS = 200


def _downsample(series, max_points=MAX_CHART_POINTS):
    """Downsample a time series to at most max_points using LTTB-like selection.

    Always keeps first and last points. For the middle, selects evenly
    spaced points plus any local extrema (peaks/valleys) to preserve shape.
    """
    if not series or len(series) <= max_points:
        return series

    n = len(series)
    step = (n - 2) / (max_points - 2)
    result = [series[0]]

    for i in range(1, max_points - 1):
        idx = int(1 + i * step)
        idx = min(idx, n - 2)
        result.append(series[idx])

    result.append(series[-1])
    return result


def prepare_cumulative_pnl(pnl_series):
    """Prepare data for the cumulative P&L area chart."""
    return _downsample(pnl_series or [])


def prepare_waterfall(bet_results):
    """Prepare data for the per-bet waterfall bar chart."""
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
    return _downsample(out)


def prepare_rolling_accuracy(rolling_series):
    """Prepare data for rolling accuracy line chart."""
    return _downsample(rolling_series or [])


def to_json(data):
    """Compact JSON for embedding in HTML attributes."""
    return json.dumps(data, separators=(",", ":"))
