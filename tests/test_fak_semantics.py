"""
test_fak_semantics.py — Lever B: FOK → FAK (Fill-And-Kill = IOC) submission.

TDD: written BEFORE the rename of _submit_fok_order → _submit_fak_order.

FAK is Polymarket's IOC order type:
  - Takes whatever liquidity is currently available at the limit price
  - Cancels (kills) the unfilled remainder immediately
  - Allows partial fills (unlike FOK which is all-or-nothing)

Reference: docs/specs/stochastic/spec_fill_adverse_selection.md (Lever B)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestFAKSubmission:

    def test_submit_uses_fak_order_type(self):
        """The submit function must call post_order with OrderType.FAK, not FOK."""
        from trade import _submit_fak_order

        mock_client = MagicMock()
        mock_client.create_market_order.return_value = "signed_order_blob"
        mock_client.post_order.return_value = {
            "success": True, "status": "matched", "orderID": "0xabc"
        }

        with patch("trade._init_clob_client", return_value=(mock_client, "BUY", "SELL")):
            # Need a stub OrderType so the import inside _submit_fak_order works
            with patch("py_clob_client.clob_types.OrderType") as mock_ot:
                mock_ot.FAK = "FAK"
                mock_ot.FOK = "FOK"
                _submit_fak_order(token_id="t", side="BUY", amount=25.0, price=0.51)

        # post_order must have been called with orderType=OrderType.FAK
        kwargs = mock_client.post_order.call_args.kwargs
        assert "orderType" in kwargs
        assert kwargs["orderType"] == "FAK", \
            f"expected OrderType.FAK, got {kwargs['orderType']}"

    def test_partial_fill_response_handled(self):
        """A partial fill (filled_size < requested) should still report success."""
        from trade import _submit_fak_order

        mock_client = MagicMock()
        mock_client.create_market_order.return_value = "signed_order_blob"
        mock_client.post_order.return_value = {
            "success": True, "status": "matched", "orderID": "0xabc",
            "takingAmount": "12.50", "makingAmount": "25.00",  # partial
        }

        with patch("trade._init_clob_client", return_value=(mock_client, "BUY", "SELL")):
            with patch("py_clob_client.clob_types.OrderType") as mock_ot:
                mock_ot.FAK = "FAK"
                response = _submit_fak_order(
                    token_id="t", side="BUY", amount=25.0, price=0.51
                )

        assert response.get("success") is True
        # Caller (place_order) is responsible for interpreting partial vs full
        assert "takingAmount" in response


class TestFAKBackcompat:

    def test_old_submit_fok_order_name_still_callable(self):
        """During transition, _submit_fok_order should still work as an alias."""
        from trade import _submit_fok_order
        # The function exists. Whether it's an alias or kept as-is is impl detail.
        assert callable(_submit_fok_order)
