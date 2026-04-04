"""Dashboard V2 — Principles-first redesign with D3.js.

Drop-in replacement for dashboard.build_html().
"""

from .data import get_db, get_pipeline_summary, detect_mode, get_live_pnl, get_signal_pnl, get_conviction_breakdown, get_breaker_status, get_rolling_accuracy, get_trade_execution, get_integrity_status, get_recent_bets
from .sections import header_section, live_pnl_section, signal_pnl_section, ev_gauge_section, conviction_section, rolling_accuracy_section, breaker_section, trade_execution_section, recent_bets_section
from .layout import page_shell

DEFAULT_NAV = [
    {"label": "BTC 5m", "href": "index.html"},
    {"label": "BTC 15m", "href": "15m.html"},
    {"label": "ETH 5m", "href": "eth.html"},
    {"label": "Kalshi", "href": "kalshi.html"},
    {"label": "Bybit Perps", "href": "bybit-perps.html"},
]

# Map subtitle keywords to (pipeline_name, asset, nav_active_label)
_PIPELINE_MAP = {
    "ETH": ("ETH 5-Minute Momentum", "ETH", "ETH 5m"),
    "15": ("BTC 15-Minute Momentum", "BTC", "BTC 15m"),
    "KALSHI": ("Kalshi BTC Momentum", "KALSHI", "Kalshi"),
    "BYBIT": ("Bybit BTC Perps", "BTC", "Bybit Perps"),
}


def build_html(db_path=None, subtitle="BTC 5-Minute Momentum (Live)", nav_links=None):
    """Generate a complete static HTML dashboard.

    Signature matches the original dashboard.build_html() exactly.
    """
    if nav_links is None:
        nav_links = DEFAULT_NAV

    # Determine pipeline identity from subtitle
    sub_upper = (subtitle or "").upper()
    pipeline_name = subtitle or "BTC 5-Minute Momentum"
    asset = "BTC"
    active_label = "BTC 5m"
    for key, (name, ast, label) in _PIPELINE_MAP.items():
        if key in sub_upper:
            pipeline_name = name
            asset = ast
            active_label = label
            break

    db = get_db(db_path)
    try:
        # Gather all data
        summary = get_pipeline_summary(db)
        mode = detect_mode(db)

        # Live P&L (only for live pipelines)
        live_data = get_live_pnl(db) if mode == "live" else None

        # Signal P&L (all pipelines)
        signal_data = get_signal_pnl(db, asset=asset)

        # Conviction breakdown
        conv_breakdown = get_conviction_breakdown(db, asset=asset)

        # Rolling accuracy
        rolling_data = get_rolling_accuracy(db)

        # Trade execution (live pipelines only)
        exec_data = get_trade_execution(db) if mode == "live" else None

        # Integrity
        integrity = get_integrity_status(db)

        # Recent bets
        recent_bets = get_recent_bets(db)

        # Circuit breakers
        breakers = get_breaker_status(db, asset=asset, subtitle=subtitle)
    finally:
        db.close()

    # Assemble sections
    body_parts = [
        header_section(pipeline_name, mode, summary, integrity=integrity),
        live_pnl_section(live_data),
        trade_execution_section(exec_data),
        recent_bets_section(recent_bets),
        signal_pnl_section(signal_data, mode),
        ev_gauge_section(signal_data),
        conviction_section(conv_breakdown),
        rolling_accuracy_section(rolling_data),
        breaker_section(breakers),
    ]

    body_html = "\n".join(part for part in body_parts if part)

    title = f"BOTSY — {pipeline_name}"
    return page_shell(title, body_html, nav_links, active_label)
