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


def test_pnl_asymmetry_tracking():
    """Win/loss breakdown shows the binary options asymmetry.
    Wins are variable (depends on entry price), losses are fixed.
    """
    rows = [
        _make_resolved("contrarian_rule", 0.62, 0.20, 1, conviction=3),  # win big: 75*(1/0.2-1) = 300
        _make_resolved("contrarian_rule", 0.62, 0.80, 1, conviction=3),  # win small: 75*(1/0.8-1) = 18.75
        _make_resolved("contrarian_rule", 0.62, 0.50, 0, conviction=3),  # lose: -75
        _make_resolved("contrarian_rule", 0.62, 0.30, 0, conviction=3),  # lose: -75
    ]
    rows[0]["market_id"] = "m1"
    rows[1]["market_id"] = "m2"
    rows[2]["market_id"] = "m3"
    rows[3]["market_id"] = "m4"
    result = compute_pnl(rows)
    a = result["contrarian_rule"]

    # Check decomposition
    assert a["num_wins"] == 2
    assert a["num_losses"] == 2
    assert a["gross_wins"] > 0  # positive
    assert a["gross_losses"] < 0  # negative
    assert abs(a["gross_wins"] - (300 + 18.75)) < 0.1  # variable wins
    assert a["gross_losses"] == -150  # fixed losses: 2 × -75

    # Average win >> average loss (that's the asymmetry)
    assert a["avg_win"] > abs(a["avg_loss"])  # $159.38 avg win vs $75 avg loss

    # Max drawdown tracked
    assert a["max_drawdown"] >= 0

    # Bet results list has per-bet detail
    assert len(a["bet_results"]) == 4
    assert a["bet_results"][0]["won"] is True
    assert a["bet_results"][2]["won"] is False
