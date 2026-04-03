"""Tests for Phase 6a CLOB order book depth queries."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_clob_depth_imports():
    """clob_depth module imports without errors."""
    from clob_depth import get_order_book, analyze_depth, get_liquidity_summary, format_liquidity_log


def test_analyze_depth_buy_side():
    """analyze_depth correctly computes slippage for buy orders."""
    from clob_depth import analyze_depth

    book = {
        "bids": [
            {"price": "0.50", "size": "200"},
            {"price": "0.49", "size": "300"},
        ],
        "asks": [
            {"price": "0.51", "size": "100"},
            {"price": "0.52", "size": "200"},
            {"price": "0.55", "size": "500"},
        ],
    }

    result = analyze_depth(book, side="buy")

    assert result["best_bid"] == 0.50
    assert result["best_ask"] == 0.51
    assert result["spread"] == 0.01
    assert result["mid"] == 0.505
    assert result["depth_levels"] == 3
    assert result["max_bet_2pct"] > 0
    assert 25 in result["slippage_curve"]
    assert 50 in result["slippage_curve"]

    # $25 should fill at best ask (0.51) with ~0% slippage
    s25 = result["slippage_curve"][25]
    assert s25["avg_price"] == 0.51
    assert s25["slippage_pct"] == 0.0

    # $100 should eat into second level (0.52), slippage > 0
    s100 = result["slippage_curve"][100]
    assert s100["avg_price"] > 0.51


def test_analyze_depth_sell_side():
    """analyze_depth works for sell side (hitting bids)."""
    from clob_depth import analyze_depth

    book = {
        "bids": [
            {"price": "0.50", "size": "100"},
            {"price": "0.48", "size": "200"},
        ],
        "asks": [
            {"price": "0.52", "size": "100"},
        ],
    }

    result = analyze_depth(book, side="sell")
    assert result["best_bid"] == 0.50
    assert result["depth_levels"] == 2


def test_analyze_depth_empty_book():
    """Empty book returns error."""
    from clob_depth import analyze_depth

    result = analyze_depth({"bids": [], "asks": []})
    assert "error" in result


def test_format_liquidity_log():
    """format_liquidity_log produces a readable string."""
    from clob_depth import format_liquidity_log

    summary = {
        "token": "YES",
        "best_bid": 0.50,
        "best_ask": 0.51,
        "spread": 0.01,
        "spread_pct": 1.98,
        "mid": 0.505,
        "max_bet_2pct": 150.0,
        "max_bet_5pct": 800.0,
        "depth_levels": 30,
        "slippage_at_50": {"dollars": 50, "avg_price": 0.51, "shares": 98.0, "slippage_pct": 0.0},
        "slippage_at_200": {"dollars": 200, "avg_price": 0.52, "shares": 384.6, "slippage_pct": 1.96},
        "slippage_at_500": {"dollars": 500, "avg_price": 0.55, "shares": 909.1, "slippage_pct": 7.84},
    }

    log = format_liquidity_log(summary)
    assert "[CLOB]" in log
    assert "spread=" in log
    assert "max@2%=" in log


def test_format_liquidity_log_error():
    """Error summaries produce readable output."""
    from clob_depth import format_liquidity_log

    log = format_liquidity_log({"error": "book_unavailable"})
    assert "book_unavailable" in log


def test_max_bet_respects_slippage():
    """max_bet_2pct is within 2% of reference price."""
    from clob_depth import analyze_depth

    # Deep book with lots of liquidity at tight prices
    book = {
        "bids": [{"price": "0.50", "size": "10000"}],
        "asks": [
            {"price": "0.51", "size": "5000"},   # reference price
            {"price": "0.515", "size": "5000"},   # ~1% above 0.51 → within 2%
            {"price": "0.525", "size": "5000"},   # ~3% above 0.51 → within 5%, outside 2%
            {"price": "0.55", "size": "5000"},    # ~8% above 0.51 → outside both
        ],
    }

    result = analyze_depth(book, side="buy")
    # 2% includes 0.51 + 0.515, 5% also includes 0.525
    assert result["max_bet_2pct"] > 0
    assert result["max_bet_2pct"] < result["max_bet_5pct"]


def test_store_prediction_accepts_liquidity():
    """store_prediction accepts and stores liquidity data in reasoning JSON."""
    from predict import store_prediction
    import sqlite3
    import tempfile
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = sqlite3.connect(db_path)
        db.execute("""CREATE TABLE predictions (
            market_id TEXT, agent TEXT, estimate REAL, edge REAL,
            confidence TEXT, reasoning TEXT, predicted_at TEXT,
            cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")
        db.commit()

        regime = {"label": "HIGH_VOL / TRENDING", "autocorrelation": 0.2,
                  "volatility": 0.15, "is_mean_reverting": False}
        signal = {"estimate": 0.62, "should_trade": True,
                  "confidence": "medium", "direction": "UP"}
        liquidity = {"spread_pct": 1.5, "max_bet_2pct": 200, "token": "YES"}

        store_prediction(db, "m1", signal, regime, 1, mkt_price=0.50,
                         liquidity=liquidity)

        row = db.execute("SELECT reasoning FROM predictions WHERE market_id='m1'").fetchone()
        reasoning = json.loads(row[0])
        assert "liquidity" in reasoning
        assert reasoning["liquidity"]["max_bet_2pct"] == 200
        db.close()


def test_get_clob_tokens_function_exists():
    """_get_clob_tokens_safe is importable and callable."""
    from predict import _get_clob_tokens_safe
    # Don't actually call it (would hit API), just verify it exists
    assert callable(_get_clob_tokens_safe)


def test_analyze_liquidity_with_data():
    """analyze_liquidity extracts liquidity stats from reasoning JSON."""
    import json
    from daily_report import analyze_liquidity

    predictions = [
        {
            "reasoning": json.dumps({
                "liquidity": {
                    "token": "YES",
                    "spread_pct": 1.5,
                    "max_bet_2pct": 200,
                    "max_bet_5pct": 800,
                    "depth_levels": 30,
                    "slippage_at_200": {"slippage_pct": 1.2},
                }
            }),
            "conviction_score": 4,
        },
        {
            "reasoning": json.dumps({
                "liquidity": {
                    "token": "NO",
                    "spread_pct": 2.5,
                    "max_bet_2pct": 100,
                    "max_bet_5pct": 500,
                    "depth_levels": 20,
                    "slippage_at_200": {"slippage_pct": 3.0},
                }
            }),
            "conviction_score": 3,
        },
    ]

    result = analyze_liquidity(predictions)
    assert result is not None
    assert result["count"] == 2
    assert result["avg_spread"] == 2.0
    assert result["avg_max_bet_2pct"] == 150.0
    assert result["avg_max_bet_5pct"] == 650.0
    assert result["avg_depth_levels"] == 25.0
    assert result["avg_slip_200"] == 2.1
    assert "YES" in result["by_direction"]
    assert "NO" in result["by_direction"]


def test_analyze_liquidity_no_data():
    """analyze_liquidity returns None when no liquidity data exists."""
    from daily_report import analyze_liquidity

    predictions = [
        {"reasoning": '{"some_key": "value"}', "conviction_score": 3},
        {"reasoning": None, "conviction_score": 3},
    ]
    result = analyze_liquidity(predictions)
    assert result is None


def test_analyze_liquidity_exceeded_count():
    """analyze_liquidity counts bets that exceed the 2% slippage ceiling."""
    import json
    from daily_report import analyze_liquidity

    predictions = [
        {
            "reasoning": json.dumps({
                "liquidity": {
                    "token": "YES",
                    "spread_pct": 1.0,
                    "max_bet_2pct": 50,  # conv=4 bets $200, exceeds $50 ceiling
                    "max_bet_5pct": 300,
                    "depth_levels": 10,
                }
            }),
            "conviction_score": 4,
        },
    ]

    result = analyze_liquidity(predictions)
    assert result is not None
    assert result["exceeded_2pct"] == 1
