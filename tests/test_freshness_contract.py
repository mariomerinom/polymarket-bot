"""Regression tests for the unified BTC5M_EXECUTABLE_MAX_AGE_S freshness contract.

Root cause 3: LIVE_ORDERBOOK_MAX_AGE_S=10s in trade.py admitted 2-10s books as
'fresh' while the canary gate uses <2s. The fix: one env variable drives both
thresholds, preventing 2-10s books from being sampled as 'fresh' and polluting
the p95 metric.
"""
import importlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _sidecar_entry_with_age(age_ms: float, snapshot_verified: bool = True) -> dict:
    """Build a minimal sidecar entry whose updated_at is exactly age_ms old."""
    ts = (datetime.now(timezone.utc) - timedelta(milliseconds=age_ms)).isoformat()
    return {
        "market_id": "m-fc-001",
        "side": "yes",
        "token_id": "tok-fc-001",
        "status": "fresh",
        "mid": 0.50,
        "best_bid": 0.48,
        "best_ask": 0.52,
        "spread": 0.04,
        "updated_at": ts,
        "source": "polymarket_orderbook_v2",
        "stale_reason": None,
        "snapshot_verified": snapshot_verified,
    }


# ── Env variable drives trade.py threshold ────────────────────────────────────

class TestTradeMaxAge:
    """LIVE_ORDERBOOK_MAX_AGE_S in trade.py must derive from env var."""

    def test_default_is_2_seconds(self, monkeypatch):
        monkeypatch.delenv("BTC5M_EXECUTABLE_MAX_AGE_S", raising=False)
        import trade
        importlib.reload(trade)
        assert trade.LIVE_ORDERBOOK_MAX_AGE_S == pytest.approx(2.0)

    def test_env_overrides_value(self, monkeypatch):
        monkeypatch.setenv("BTC5M_EXECUTABLE_MAX_AGE_S", "3.5")
        import trade
        importlib.reload(trade)
        assert trade.LIVE_ORDERBOOK_MAX_AGE_S == pytest.approx(3.5)

    def test_old_hardwired_value_10_no_longer_default(self, monkeypatch):
        monkeypatch.delenv("BTC5M_EXECUTABLE_MAX_AGE_S", raising=False)
        import trade
        importlib.reload(trade)
        assert trade.LIVE_ORDERBOOK_MAX_AGE_S != 10, (
            "Default must not be 10s any more — that was the freshness mismatch bug"
        )


# ── Env variable drives delayed_execution.py threshold ───────────────────────

class TestDelayedExecutionMaxAge:
    """MAX_ORDERBOOK_AGE_MS in delayed_execution.py must derive from the same env var."""

    def test_default_is_2000ms(self, monkeypatch):
        monkeypatch.delenv("BTC5M_EXECUTABLE_MAX_AGE_S", raising=False)
        import delayed_execution
        importlib.reload(delayed_execution)
        assert delayed_execution.MAX_ORDERBOOK_AGE_MS == 2000

    def test_env_overrides_value(self, monkeypatch):
        monkeypatch.setenv("BTC5M_EXECUTABLE_MAX_AGE_S", "3.5")
        import delayed_execution
        importlib.reload(delayed_execution)
        assert delayed_execution.MAX_ORDERBOOK_AGE_MS == 3500

    def test_unification_both_modules_agree(self, monkeypatch):
        """The critical contract: trade and delayed_execution share the same threshold."""
        monkeypatch.setenv("BTC5M_EXECUTABLE_MAX_AGE_S", "4.0")
        import trade, delayed_execution
        importlib.reload(trade)
        importlib.reload(delayed_execution)
        assert int(trade.LIVE_ORDERBOOK_MAX_AGE_S * 1000) == delayed_execution.MAX_ORDERBOOK_AGE_MS


# ── _side_book respects max_age_s ────────────────────────────────────────────

class TestSidebookFreshnessMaxAge:
    """PolymarketOrderbookService._side_book uses max_age_s to gate freshness."""

    def _service(self, tmp_path, max_age_s: float):
        from polymarket_orderbook_service import PolymarketOrderbookService
        return PolymarketOrderbookService(
            executable_cache_path=tmp_path / "exec.json",
            max_age_s=max_age_s,
        )

    def test_book_within_max_age_is_fresh(self, tmp_path):
        service = self._service(tmp_path, max_age_s=2.0)
        market = {"yes": _sidecar_entry_with_age(1500)}  # 1.5s, under 2s gate
        book = service._side_book(market, "m-fc-001", "yes", "tok-fc-001")
        assert book["status"] == "fresh"

    def test_book_exceeding_max_age_is_stale(self, tmp_path):
        service = self._service(tmp_path, max_age_s=2.0)
        market = {"yes": _sidecar_entry_with_age(2500)}  # 2.5s, over 2s gate
        book = service._side_book(market, "m-fc-001", "yes", "tok-fc-001")
        assert book["status"] == "stale"

    def test_1s_env_makes_1500ms_book_stale(self, tmp_path):
        """A 1.5s book is fresh at max_age=2.0 but stale at max_age=1.0."""
        service = self._service(tmp_path, max_age_s=1.0)
        market = {"yes": _sidecar_entry_with_age(1500)}
        book = service._side_book(market, "m-fc-001", "yes", "tok-fc-001")
        assert book["status"] == "stale"

    def test_p95_samples_only_fresh_books(self, tmp_path):
        """Only books with status=='fresh' contribute to the p95 metric.
        With max_age_s=2.0, a 2.5s book is stale and must not be sampled."""
        from polymarket_orderbook_service import PolymarketOrderbookService, _record_book

        stale_book = {
            "market_id": "m-fc-001",
            "side": "yes",
            "token_id": "tok-fc-001",
            "status": "stale",
            "age_ms": 2500,
            "reason": "stale_updated_at",
        }
        metrics = _record_book({}, stale_book)
        samples = metrics.get("_age_samples_ms") or []
        assert 2500 not in samples, "Stale book must not appear in fresh-only p95 samples"
