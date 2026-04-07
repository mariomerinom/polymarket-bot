"""
test_alpha_cushion.py — Lever B: alpha-capped dynamic cushion in compute_order.

TDD: written BEFORE the implementation.

Behavioral contract for the new cushion logic:

  spread_cushion  = min(0.01, spread / 2)
  alpha_cushion   = max(0.0, (estimate - best_ask) - MIN_POST_CUSHION_EDGE)
                    (for UP; symmetric for DOWN against no_best_ask)
  cushion         = min(spread_cushion, alpha_cushion)
  price_limit     = best_ask + cushion         (UP)
                  = no_best_ask + cushion      (DOWN)

If cushion <= 0  →  return None, "skipped_cushion_eats_edge"

Plus: order_type becomes "fak" (Fill-And-Kill = IOC), action becomes "fak_take".
The dict carries a new "cushion" key.

Reference: docs/specs/stochastic/spec_fill_adverse_selection.md (Lever B)
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _market(yes_ask=0.45, yes_bid=0.44, no_ask=0.55, no_bid=0.54, spread=None):
    """Helper: build a market_row dict with the WS-cache fields populated."""
    yes_spread = spread if spread is not None else round(yes_ask - yes_bid, 4)
    no_spread = spread if spread is not None else round(no_ask - no_bid, 4)
    return {
        "price_yes": (yes_ask + yes_bid) / 2,
        "price_no": (no_ask + no_bid) / 2,
        "_clob_verified": {"yes": True, "no": True},
        "_yes_best_ask": yes_ask,
        "_yes_best_bid": yes_bid,
        "_yes_spread": yes_spread,
        "_no_best_ask": no_ask,
        "_no_best_bid": no_bid,
        "_no_spread": no_spread,
    }


# ── Cushion application ──────────────────────────────────────────────────────


class TestAlphaCushionApplication:

    def test_buy_applies_cushion_above_best_ask(self):
        """UP order with healthy edge: price_limit = best_ask + cushion (cushion > 0)."""
        from trade import compute_order
        pred = {"estimate": 0.65, "conviction_score": 4, "agent": "momentum_rule"}
        market = _market(yes_ask=0.50, yes_bid=0.48)  # spread 0.02
        order, _ = compute_order(pred, market)
        assert order is not None, "healthy edge should produce an order"
        # spread_cushion = min(0.01, 0.02/2) = 0.01
        # alpha_cushion  = (0.65 - 0.50) - 0.02 = 0.13
        # cushion        = min(0.01, 0.13) = 0.01
        assert order["price_limit"] == pytest.approx(0.51, abs=1e-4), \
            f"price_limit should be 0.50 + 0.01 cushion, got {order['price_limit']}"
        assert order.get("cushion") == pytest.approx(0.01, abs=1e-4)
        assert order["action"] == "fak_take"
        assert order["order_type"] == "fak"

    def test_sell_applies_cushion_above_no_best_ask(self):
        """DOWN order: price_limit = no_best_ask + cushion."""
        from trade import compute_order
        pred = {"estimate": 0.30, "conviction_score": 4, "agent": "momentum_rule"}
        market = _market(no_ask=0.40, no_bid=0.38)  # NO spread 0.02
        order, _ = compute_order(pred, market)
        assert order is not None
        # For DOWN: estimate is for UP=0.30, so DOWN edge = (1-0.30) - 0.40 = 0.30
        # alpha_cushion = 0.30 - 0.02 = 0.28; spread_cushion = 0.01; min = 0.01
        assert order["price_limit"] == pytest.approx(0.41, abs=1e-4)
        assert order.get("cushion") == pytest.approx(0.01, abs=1e-4)
        assert order["direction"] == "DOWN"

    def test_tight_spread_caps_cushion_at_half_spread(self):
        """If spread is 1¢, cushion is half (0.5¢), not the 1¢ ceiling."""
        from trade import compute_order
        pred = {"estimate": 0.65, "conviction_score": 4, "agent": "momentum_rule"}
        market = _market(yes_ask=0.50, yes_bid=0.495)  # spread 0.005
        order, _ = compute_order(pred, market)
        assert order is not None
        # spread_cushion = min(0.01, 0.005/2) = 0.0025
        # alpha_cushion is large, so cushion = 0.0025
        assert order.get("cushion") == pytest.approx(0.0025, abs=1e-4)
        assert order["price_limit"] == pytest.approx(0.5025, abs=1e-4)


# ── Alpha cap (the user's #1 concern) ────────────────────────────────────────


class TestAlphaCushionCap:

    def test_thin_edge_cushion_capped_to_preserve_min_edge(self):
        """If 1¢ cushion would push post-cushion edge below 2¢, cap the cushion."""
        from trade import compute_order
        pred = {"estimate": 0.475, "conviction_score": 4, "agent": "momentum_rule"}
        # estimate=0.475, best_ask=0.45 → raw edge = 2.5¢
        # After 1¢ cushion: edge=1.5¢. That's below 2¢ floor. cushion must cap.
        # alpha_cushion = (0.475 - 0.45) - 0.02 = 0.005
        # spread_cushion = 0.005 (spread=0.01)
        # cushion = min(0.005, 0.005) = 0.005
        # but wait — DOWN, since 0.475 < 0.5
        # For DOWN: (1-0.475) - no_best_ask = 0.525 - 0.55 = -0.025 (no edge on NO)
        # So this would skip via the existing FOK_EDGE_BUFFER gate. Bad test setup.
        # Use UP-side instead:
        pred = {"estimate": 0.525, "conviction_score": 4, "agent": "momentum_rule"}
        market = _market(yes_ask=0.50, yes_bid=0.49)  # spread 0.01
        order, reason = compute_order(pred, market)
        # Existing FOK_EDGE_BUFFER gate: edge=0.025 vs min_edge=0.01+0.02=0.03 → skipped
        # That's the existing skipped_low_edge guard. Different from the new alpha-cap.
        # We need an example where the existing gate passes but the alpha-cap fires.
        # Make spread tiny so min_edge is small: spread=0.002 → min_edge=0.022
        market = _market(yes_ask=0.50, yes_bid=0.498)  # spread 0.002
        # estimate=0.525: edge = 0.025; min_edge = 0.022 → passes existing gate
        # alpha_cushion = 0.025 - 0.02 = 0.005
        # spread_cushion = min(0.01, 0.001) = 0.001
        # cushion = min(0.001, 0.005) = 0.001 (positive — order placed)
        order, reason = compute_order(pred, market)
        assert order is not None, f"expected order, got skip: {reason}"
        assert order["cushion"] == pytest.approx(0.001, abs=1e-4)

    def test_cushion_zero_or_negative_skips_with_named_reason(self):
        """If alpha_cushion <= 0, skip the bet with skipped_cushion_eats_edge."""
        from trade import compute_order
        # estimate=0.515, best_ask=0.50 → raw edge = 1.5¢
        # alpha_cushion = 0.015 - 0.02 = -0.005 → would-be negative → cushion≤0
        pred = {"estimate": 0.515, "conviction_score": 4, "agent": "momentum_rule"}
        market = _market(yes_ask=0.50, yes_bid=0.498)  # spread 0.002, passes existing gate
        # existing FOK gate: edge=0.015, min_edge=0.022 → would already skip
        # We need something that passes existing gate but fails alpha-cap.
        # Lower FOK_EDGE_BUFFER assumption is fragile. Easier: use a market where
        # the existing edge gate passes (edge >= spread + 0.02) but alpha edge after
        # cushion would be negative.
        # If existing gate requires edge >= 2¢, and our floor is also 2¢, then any
        # edge that passes the existing gate also passes the alpha cap (0¢ cushion
        # minimum, no skip).
        # Conclusion: with current FOK_EDGE_BUFFER=0.02 and MIN_POST_CUSHION_EDGE=0.02,
        # the alpha cap is mostly redundant with the existing gate. The cap matters
        # when FOK_EDGE_BUFFER < MIN_POST_CUSHION_EDGE in future tuning.
        # Test the contract directly: monkeypatch MIN_POST_CUSHION_EDGE high.
        import config
        original = getattr(config, "MIN_POST_CUSHION_EDGE", 0.02)
        try:
            config.MIN_POST_CUSHION_EDGE = 0.05  # require 5¢ post-cushion
            market = _market(yes_ask=0.50, yes_bid=0.495)  # spread 0.005
            # estimate=0.56: edge=0.06, passes existing gate (min_edge=0.025)
            # alpha_cushion = 0.06 - 0.05 = 0.01 → fine, cushion positive
            pred = {"estimate": 0.56, "conviction_score": 4, "agent": "momentum_rule"}
            order, _ = compute_order(pred, market)
            assert order is not None

            # Now estimate=0.535: edge=0.035, passes existing gate (min_edge=0.025)
            # alpha_cushion = 0.035 - 0.05 = -0.015 → cushion ≤ 0 → skip
            pred = {"estimate": 0.535, "conviction_score": 4, "agent": "momentum_rule"}
            order, reason = compute_order(pred, market)
            assert order is None
            assert "cushion" in reason.lower() and "edge" in reason.lower(), \
                f"expected skipped_cushion_eats_edge, got: {reason}"
        finally:
            config.MIN_POST_CUSHION_EDGE = original


# ── Backwards compatibility ──────────────────────────────────────────────────


class TestBackwardCompatibility:

    def test_legacy_gtc_path_unchanged_when_no_ws_cache(self):
        """If best_ask is missing (paper pipeline without WS), legacy GTC still fires."""
        from trade import compute_order
        pred = {"estimate": 0.65, "conviction_score": 4, "agent": "momentum_rule"}
        market = {
            "price_yes": 0.50, "price_no": 0.50,
            "_clob_verified": {"yes": True, "no": True},
            # Note: no _yes_best_ask, no _yes_spread → triggers GTC fallback
        }
        order, _ = compute_order(pred, market)
        assert order is not None
        assert order["order_type"] == "gtc"
        assert order["action"] == "gtc_legacy"
        # No cushion field for the GTC fallback
        assert order.get("cushion") in (None, 0.0)
