"""Regression tests for the registry-first in-process orderbook read (root cause 1).

Root cause 1: the pipeline ran in-process (asyncio.to_thread(ci_run.main,...))
but the decision path read the book from disk (data/btc5m_executable_orderbook.json)
because the in-memory _orderbook_cache had no way to reach ci_run.main without
passing the engine handle.  The disk file was only flushed every 2 s, so the
freshness floor was at least 2 s regardless of how fresh the in-memory data was.

The fix: live_book_registry.py — a process-global singleton the engine publishes
to after every handler.  PolymarketOrderbookService._side_book checks
engine_is_live() and, when True, reads from the registry using last_event_ms
(local apply-time) instead of the disk-file updated_at.

These tests document the win: with an engine present and a deliberately stale
disk sidecar, the read reflects the *registry* age, not the disk age.
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fresh_registry_entry(token_id: str) -> dict:
    """Build a registry entry that is genuinely fresh (< 100 ms old)."""
    return {
        "market_id": "m-ipr-001",
        "side": "yes",
        "token_id": token_id,
        "mid": 0.55,
        "best_bid": 0.53,
        "best_ask": 0.57,
        "spread": 0.04,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_event_ms": int(time.time() * 1000),
        "snapshot_verified": True,
        "status": "fresh",
        "stale_reason": None,
        "source_ts": None,
    }


def _write_stale_sidecar(path: Path, market_id: str, token_id: str) -> None:
    """Write a sidecar whose updated_at is 30 s in the past (stale by any gate)."""
    from datetime import timedelta
    old = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    sidecar = {
        "version": 2,
        "markets": {
            market_id: {
                "yes": {
                    "market_id": market_id,
                    "side": "yes",
                    "token_id": token_id,
                    "mid": 0.40,
                    "best_bid": 0.38,
                    "best_ask": 0.42,
                    "spread": 0.04,
                    "updated_at": old,
                    "snapshot_verified": True,
                    "status": "fresh",
                    "stale_reason": None,
                    "source_ts": None,
                }
            }
        },
    }
    path.write_text(json.dumps(sidecar))


# ── Registry-first read ───────────────────────────────────────────────────────

class TestRegistryFirstRead:
    """With engine present + fresh registry + stale sidecar → registry wins."""

    def setup_method(self):
        import live_book_registry
        live_book_registry.reset()

    def teardown_method(self):
        import live_book_registry
        live_book_registry.reset()

    def test_registry_read_returns_fresh_when_sidecar_is_stale(self, tmp_path):
        """Primary regression: registry age beats stale disk sidecar."""
        import live_book_registry
        from polymarket_orderbook_service import PolymarketOrderbookService

        token_id = "tok-ipr-001"
        market_id = "m-ipr-001"
        sidecar = tmp_path / "exec.json"
        _write_stale_sidecar(sidecar, market_id, token_id)

        # Signal engine presence and publish a fresh entry.
        live_book_registry.set_engine_present(True)
        live_book_registry.publish_token(token_id, _fresh_registry_entry(token_id))

        service = PolymarketOrderbookService(
            executable_cache_path=sidecar, max_age_s=2.0
        )
        book = service._side_book({}, market_id, "yes", token_id)

        assert book["status"] == "fresh", (
            f"Expected fresh from registry, got {book['status']!r}: {book}"
        )
        assert book["source"] == "live_registry"
        assert book["age_ms"] is not None
        assert book["age_ms"] < 500, "Registry read should reflect sub-second age"

    def test_registry_age_used_not_disk_age(self, tmp_path):
        """age_ms in the returned book must come from last_event_ms, not updated_at."""
        import live_book_registry
        from polymarket_orderbook_service import PolymarketOrderbookService

        token_id = "tok-ipr-002"
        market_id = "m-ipr-002"
        sidecar = tmp_path / "exec.json"
        _write_stale_sidecar(sidecar, market_id, token_id)

        entry = _fresh_registry_entry(token_id)
        entry["market_id"] = market_id

        live_book_registry.set_engine_present(True)
        live_book_registry.publish_token(token_id, entry)

        service = PolymarketOrderbookService(
            executable_cache_path=sidecar, max_age_s=2.0
        )
        book = service._side_book({}, market_id, "yes", token_id)

        # If disk age were used (30 s old), status would be stale.
        # Registry age is < 500 ms, so status must be fresh.
        assert book["status"] == "fresh"
        assert book["age_ms"] < 2000

    def test_no_engine_falls_back_to_disk_sidecar(self, tmp_path):
        """Without engine_is_live(), the disk sidecar is the source."""
        import live_book_registry
        from polymarket_orderbook_service import PolymarketOrderbookService

        token_id = "tok-ipr-003"
        market_id = "m-ipr-003"
        sidecar = tmp_path / "exec.json"

        # Disk sidecar has a fresh entry.
        fresh = datetime.now(timezone.utc).isoformat()
        sidecar.write_text(json.dumps({
            "version": 2,
            "markets": {
                market_id: {
                    "yes": {
                        "market_id": market_id,
                        "side": "yes",
                        "token_id": token_id,
                        "mid": 0.50,
                        "best_bid": 0.48,
                        "best_ask": 0.52,
                        "spread": 0.04,
                        "updated_at": fresh,
                        "snapshot_verified": True,
                        "status": "fresh",
                        "stale_reason": None,
                    }
                }
            }
        }))

        # Engine NOT live → disk path.
        assert not live_book_registry.engine_is_live()

        service = PolymarketOrderbookService(
            executable_cache_path=sidecar, max_age_s=2.0
        )
        cache = __import__(
            "polymarket_orderbook_service"
        ).load_executable_cache(sidecar)
        market = (cache.get("markets") or {}).get(market_id) or {}
        book = service._side_book(market, market_id, "yes", token_id)

        assert book["status"] == "fresh"
        # Disk path uses 'executable_sidecar' source.
        assert book["source"] == "executable_sidecar"

    def test_registry_miss_falls_back_to_sidecar(self, tmp_path):
        """Engine live but token not in registry → fall back to sidecar."""
        import live_book_registry
        from polymarket_orderbook_service import PolymarketOrderbookService

        token_id = "tok-ipr-004"
        market_id = "m-ipr-004"

        # Engine live but registry is empty for this token.
        live_book_registry.set_engine_present(True)

        fresh = datetime.now(timezone.utc).isoformat()
        sidecar = tmp_path / "exec.json"
        sidecar.write_text(json.dumps({
            "version": 2,
            "markets": {
                market_id: {
                    "yes": {
                        "market_id": market_id,
                        "side": "yes",
                        "token_id": token_id,
                        "mid": 0.50,
                        "best_bid": 0.48,
                        "best_ask": 0.52,
                        "spread": 0.04,
                        "updated_at": fresh,
                        "snapshot_verified": True,
                        "status": "fresh",
                        "stale_reason": None,
                    }
                }
            }
        }))

        service = PolymarketOrderbookService(
            executable_cache_path=sidecar, max_age_s=2.0
        )
        cache = __import__(
            "polymarket_orderbook_service"
        ).load_executable_cache(sidecar)
        market = (cache.get("markets") or {}).get(market_id) or {}
        book = service._side_book(market, market_id, "yes", token_id)

        # Should fall back to sidecar and return fresh.
        assert book["status"] == "fresh"
        assert book["source"] == "executable_sidecar"


# ── Age metric — registry vs disk ─────────────────────────────────────────────

class TestAgeMetricSource:
    """age_ms must reflect the correct source depending on the active path."""

    def setup_method(self):
        import live_book_registry
        live_book_registry.reset()

    def teardown_method(self):
        import live_book_registry
        live_book_registry.reset()

    def test_p95_samples_registry_age_not_disk_age(self, tmp_path):
        """When registry is active, age_ms in p95 samples uses last_event_ms."""
        import live_book_registry
        from polymarket_orderbook_service import (
            PolymarketOrderbookService,
            _record_book,
        )

        token_id = "tok-age-001"
        market_id = "m-age-001"
        sidecar = tmp_path / "exec.json"
        _write_stale_sidecar(sidecar, market_id, token_id)

        live_book_registry.set_engine_present(True)
        live_book_registry.publish_token(token_id, _fresh_registry_entry(token_id))

        service = PolymarketOrderbookService(
            executable_cache_path=sidecar, max_age_s=2.0
        )
        book = service._side_book({}, market_id, "yes", token_id)
        assert book["status"] == "fresh"

        # _record_book samples fresh books; age must be sub-second from registry.
        metrics = _record_book({}, book)
        samples = metrics.get("_age_samples_ms") or []
        assert len(samples) == 1
        # Disk sidecar age would be ~30,000 ms; registry age is < 500 ms.
        assert samples[0] < 2000, (
            f"age_ms {samples[0]} ms exceeds 2 s — registry age not used"
        )
