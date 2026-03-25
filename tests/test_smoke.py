"""
Smoke tests — fast sanity checks that the pipeline isn't broken.
Run before every CI commit. ~5 seconds total.
"""
import sys
import os

# Add src/ to path so imports work like they do in CI
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_predict_imports():
    """Can we import predict.py without errors?"""
    from predict import momentum_signal, contrarian_signal, compute_regime_from_candles, run_predictions
    assert callable(momentum_signal)
    assert callable(contrarian_signal)  # backward compat alias
    assert callable(compute_regime_from_candles)
    assert callable(run_predictions)


def test_btc_data_imports():
    """Can we import btc_data.py without errors?"""
    from btc_data import fetch_btc_candles, format_for_prompt, compute_rolling_bias
    assert callable(fetch_btc_candles)
    assert callable(format_for_prompt)
    assert callable(compute_rolling_bias)


def test_dashboard_imports():
    """Can we import dashboard.py without errors?"""
    from dashboard import compute_pnl, compute_ensemble_pnl, get_status, get_db
    assert callable(compute_pnl)
    assert callable(compute_ensemble_pnl)
    assert callable(get_status)
    assert callable(get_db)


def test_fetch_markets_imports():
    """Can we import fetch_markets.py without errors?"""
    from fetch_markets import fetch_active_markets, init_db
    assert callable(fetch_active_markets)
    assert callable(init_db)


def test_score_imports():
    """Can we import score.py without errors?"""
    from score import calculate_brier_scores, auto_resolve
    assert callable(calculate_brier_scores)
    assert callable(auto_resolve)


def test_momentum_signal_returns_valid_structure():
    """momentum_signal returns expected keys."""
    from predict import momentum_signal

    # Minimal candle data — no signal expected
    candles = [
        {"open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 10}
        for _ in range(10)
    ]
    result = momentum_signal(candles)
    assert "estimate" in result
    assert "should_trade" in result
    assert "reason" in result
    assert 0 <= result["estimate"] <= 1


def test_regime_returns_valid_structure():
    """compute_regime_from_candles returns expected keys."""
    from predict import compute_regime_from_candles

    candles = [
        {"open": 100, "high": 101, "low": 99, "close": 100 + i * 0.1}
        for i in range(20)
    ]
    result = compute_regime_from_candles(candles)
    assert "autocorrelation" in result
    assert "volatility" in result
    assert "label" in result
    assert "is_mean_reverting" in result
    assert isinstance(result["is_mean_reverting"], bool)


def test_dashboard_pnl_on_empty_data():
    """compute_pnl handles empty input gracefully."""
    from dashboard import compute_pnl, compute_ensemble_pnl
    result = compute_pnl([])
    assert result == {}
    ens = compute_ensemble_pnl([])
    assert ens["total_pnl"] == 0
    assert ens["num_bets"] == 0
