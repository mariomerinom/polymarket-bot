"""
Unit tests for P&L calculation.
Prevents Incident 2 recurrence (inverted conviction math).
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dashboard import compute_pnl, compute_ensemble_pnl


def _make_resolved(agent, estimate, price_yes, outcome, conviction=3):
    """Helper: create a resolved prediction row."""
    return {
        "market_id": f"test_{id(agent)}_{estimate}",
        "agent": agent,
        "estimate": estimate,
        "price_yes": price_yes,
        "outcome": outcome,
        "conviction_score": conviction,
    }


def test_winning_up_bet_positive_pnl():
    """Predict UP, outcome UP → positive profit."""
    rows = [_make_resolved("contrarian_rule", 0.62, 0.50, 1, conviction=3)]
    result = compute_pnl(rows)
    agent = result["contrarian_rule"]
    assert agent["total_pnl"] > 0, f"Expected positive P&L, got {agent['total_pnl']}"
    assert agent["num_bets"] == 1


def test_losing_up_bet_negative_pnl():
    """Predict UP, outcome DOWN → lose bet."""
    rows = [_make_resolved("contrarian_rule", 0.62, 0.50, 0, conviction=3)]
    result = compute_pnl(rows)
    agent = result["contrarian_rule"]
    assert agent["total_pnl"] == -75, f"Expected -75, got {agent['total_pnl']}"


def test_winning_down_bet_positive_pnl():
    """Predict DOWN, outcome DOWN → positive profit."""
    rows = [_make_resolved("contrarian_rule", 0.38, 0.50, 0, conviction=3)]
    result = compute_pnl(rows)
    agent = result["contrarian_rule"]
    assert agent["total_pnl"] > 0


def test_losing_down_bet_negative_pnl():
    """Predict DOWN, outcome UP → lose bet."""
    rows = [_make_resolved("contrarian_rule", 0.38, 0.50, 1, conviction=3)]
    result = compute_pnl(rows)
    agent = result["contrarian_rule"]
    assert agent["total_pnl"] == -75


def test_conviction_0_no_bet():
    """Conviction 0 → $0 wagered, $0 P&L."""
    rows = [_make_resolved("contrarian_rule", 0.55, 0.55, 1, conviction=0)]
    result = compute_pnl(rows)
    agent = result["contrarian_rule"]
    assert agent["total_wagered"] == 0
    assert agent["total_pnl"] == 0
    assert agent["num_bets"] == 0


def test_conviction_3_bets_75():
    """Conviction 3 → $75 bet."""
    rows = [_make_resolved("contrarian_rule", 0.62, 0.50, 1, conviction=3)]
    result = compute_pnl(rows)
    agent = result["contrarian_rule"]
    assert agent["total_wagered"] == 75


def test_conviction_4_bets_200():
    """Conviction 4 → $200 bet."""
    rows = [_make_resolved("contrarian_rule", 0.62, 0.50, 1, conviction=4)]
    result = compute_pnl(rows)
    agent = result["contrarian_rule"]
    assert agent["total_wagered"] == 200


def test_pnl_at_extreme_prices():
    """P&L math works at edge prices (0.10, 0.90)."""
    # Buy UP at price 0.10, win → big payout
    rows = [_make_resolved("contrarian_rule", 0.62, 0.10, 1, conviction=3)]
    result = compute_pnl(rows)
    pnl = result["contrarian_rule"]["total_pnl"]
    assert pnl > 0
    # profit = 75 * (1/0.10 - 1) = 75 * 9 = 675
    assert abs(pnl - 675) < 0.01

    # Buy UP at price 0.90, win → small payout
    rows2 = [_make_resolved("contrarian_rule", 0.62, 0.90, 1, conviction=3)]
    result2 = compute_pnl(rows2)
    pnl2 = result2["contrarian_rule"]["total_pnl"]
    # profit = 75 * (1/0.90 - 1) ≈ 8.33
    assert abs(pnl2 - 8.33) < 0.1


def test_roi_calculation():
    """ROI = total_pnl / total_wagered * 100."""
    rows = [
        _make_resolved("contrarian_rule", 0.62, 0.50, 1, conviction=3),  # win: +75
        _make_resolved("contrarian_rule", 0.62, 0.50, 0, conviction=3),  # lose: -75
    ]
    # Need unique market_ids
    rows[0]["market_id"] = "m1"
    rows[1]["market_id"] = "m2"
    result = compute_pnl(rows)
    agent = result["contrarian_rule"]
    assert agent["total_wagered"] == 150
    # ROI = pnl / wagered * 100
    expected_roi = agent["total_pnl"] / agent["total_wagered"] * 100
    assert abs(agent["roi"] - expected_roi) < 0.01


def test_ensemble_only_bets_medium_plus():
    """Ensemble skips conviction < 3."""
    rows = [
        {"market_id": "m1", "agent": "contrarian_rule", "estimate": 0.62,
         "price_yes": 0.50, "outcome": 1, "conviction_score": 0},
        {"market_id": "m2", "agent": "contrarian_rule", "estimate": 0.62,
         "price_yes": 0.50, "outcome": 1, "conviction_score": 3},
    ]
    result = compute_ensemble_pnl(rows)
    assert result["num_bets"] == 1  # only m2
    assert result["num_skipped"] == 1  # m1 skipped
