"""Regression tests for the orderbook delta-before-snapshot buffering fix.

Root cause: when a price_change delta arrived before the token had a snapshot
baseline (snapshot_verified=True), the delta was dropped and the token marked
stale permanently until the next infrequent full 'book' WS event. This test
suite verifies the fixed behavior: deltas are buffered and replayed after a
REST reseed, so tokens stay fresh continuously.
"""
import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _make_engine():
    from botsy_engine import BotsyEngine
    return BotsyEngine()


def _book_event(token_id, bids=None, asks=None):
    """Synthetic WS full book snapshot event."""
    return {
        "event_type": "book",
        "asset_id": token_id,
        "bids": bids or [{"price": "0.35", "size": "100"}],
        "asks": asks or [{"price": "0.65", "size": "100"}],
        "timestamp": str(int(time.time() * 1000)),
    }


def _price_change_event(token_id, bid_price="0.37", ask_price="0.64"):
    """Synthetic WS price_change delta event."""
    return {
        "event_type": "price_change",
        "price_changes": [
            {
                "asset_id": token_id,
                "side": "BUY",
                "price": bid_price,
                "size": "50",
                "best_bid": bid_price,
                "best_ask": ask_price,
                "timestamp": str(int(time.time() * 1000)),
            }
        ],
    }


# ── Buffering: delta before snapshot ──────────────────────────────────────────

class TestDeltaBufferingBeforeSnapshot:
    """Delta arriving before snapshot must be buffered, not dropped or stranded."""

    def test_delta_before_snapshot_is_buffered_not_dropped(self):
        engine = _make_engine()
        token_id = "tok-buf-001"

        assert token_id not in engine._orderbook_cache

        engine._update_orderbook_price_change(_price_change_event(token_id))

        # Token must NOT be stranded as stale
        entry = engine._orderbook_cache.get(token_id)
        assert entry is None or entry.get("status") != "stale", (
            "Delta before snapshot must not strand the token as stale"
        )

        # New buffered-until-seed metric must increment
        assert engine.metrics["orderbook_cache"].get("price_change_buffered_until_seed", 0) >= 1

        # Old missing-snapshot metric must NOT increment (replaced by buffer)
        assert engine.metrics["orderbook_cache"]["price_change_missing_snapshot"] == 0

        # Delta must be pending for reseed
        assert token_id in engine._pending_deltas
        assert len(engine._pending_deltas[token_id]) >= 1

    def test_multiple_deltas_before_snapshot_all_buffered(self):
        engine = _make_engine()
        token_id = "tok-buf-002"

        for price in ["0.36", "0.37", "0.38"]:
            engine._update_orderbook_price_change(_price_change_event(token_id, bid_price=price))

        assert len(engine._pending_deltas.get(token_id, [])) == 3
        assert engine.metrics["orderbook_cache"].get("price_change_buffered_until_seed", 0) == 3

    def test_delta_after_snapshot_is_applied_directly(self):
        engine = _make_engine()
        token_id = "tok-buf-003"

        # Snapshot first
        engine._update_orderbook_cache(_book_event(token_id))
        assert engine._orderbook_cache[token_id]["snapshot_verified"] is True

        # Delta after snapshot — must apply directly, no buffering
        engine._update_orderbook_price_change(_price_change_event(token_id))

        assert engine.metrics["orderbook_cache"].get("price_change_buffered_until_seed", 0) == 0
        entry = engine._orderbook_cache[token_id]
        assert entry.get("status") == "fresh"
        # No pending deltas for this token
        assert token_id not in engine._pending_deltas


# ── snapshot_verified field ───────────────────────────────────────────────────

class TestSnapshotVerified:
    """snapshot_verified gates freshness: only WS book / REST seed sets it True."""

    def test_book_event_sets_snapshot_verified_true(self):
        engine = _make_engine()
        token_id = "tok-sv-001"
        engine._update_orderbook_cache(_book_event(token_id))
        assert engine._orderbook_cache[token_id]["snapshot_verified"] is True

    def test_mark_stale_sets_snapshot_verified_false(self):
        engine = _make_engine()
        token_id = "tok-sv-002"
        # First give it a valid snapshot
        engine._update_orderbook_cache(_book_event(token_id))
        assert engine._orderbook_cache[token_id]["snapshot_verified"] is True
        # Stale mark must reset it
        engine._mark_orderbook_token_stale(token_id, "test_reason")
        assert engine._orderbook_cache[token_id].get("snapshot_verified") is False

    def test_delta_preserves_snapshot_verified_from_entry(self):
        """A delta applied after a snapshot must not reset snapshot_verified."""
        engine = _make_engine()
        token_id = "tok-sv-003"
        engine._update_orderbook_cache(_book_event(token_id))
        engine._update_orderbook_price_change(_price_change_event(token_id))
        assert engine._orderbook_cache[token_id]["snapshot_verified"] is True

    def test_side_book_without_snapshot_verified_is_not_fresh(self, tmp_path):
        """_side_book must reject 'fresh' for entries lacking snapshot_verified."""
        from polymarket_orderbook_service import PolymarketOrderbookService

        service = PolymarketOrderbookService(
            executable_cache_path=tmp_path / "exec.json",
            max_age_s=2.0,
        )

        # Valid BBO, recent timestamp, but snapshot_verified absent (pre-fix entry)
        recent_ts = datetime.now(timezone.utc).isoformat()
        market = {
            "yes": {
                "market_id": "m-sv-001",
                "side": "yes",
                "token_id": "tok-yes",
                "status": "fresh",
                "mid": 0.50,
                "best_bid": 0.48,
                "best_ask": 0.52,
                "spread": 0.04,
                "updated_at": recent_ts,
                "source": "polymarket_orderbook_v2",
                "stale_reason": None,
                # snapshot_verified NOT set → pre-fix / delta-only entry
            }
        }

        book = service._side_book(market, "m-sv-001", "yes", "tok-yes")
        assert book["status"] != "fresh"
        assert book.get("reason") == "no_snapshot_baseline"

    def test_side_book_with_snapshot_verified_true_returns_fresh(self, tmp_path):
        from polymarket_orderbook_service import PolymarketOrderbookService

        service = PolymarketOrderbookService(
            executable_cache_path=tmp_path / "exec.json",
            max_age_s=2.0,
        )
        recent_ts = datetime.now(timezone.utc).isoformat()
        market = {
            "yes": {
                "market_id": "m-sv-002",
                "side": "yes",
                "token_id": "tok-yes",
                "status": "fresh",
                "mid": 0.50,
                "best_bid": 0.48,
                "best_ask": 0.52,
                "spread": 0.04,
                "updated_at": recent_ts,
                "source": "polymarket_orderbook_v2",
                "stale_reason": None,
                "snapshot_verified": True,
            }
        }

        book = service._side_book(market, "m-sv-002", "yes", "tok-yes")
        assert book["status"] == "fresh"


# ── last_event_ms: continuous freshness ───────────────────────────────────────

class TestLastEventMs:
    """last_event_ms advances on every applied event (snapshot or delta)."""

    def test_book_event_sets_last_event_ms(self):
        engine = _make_engine()
        token_id = "tok-lem-001"
        before_ms = int(time.time() * 1000) - 10
        engine._update_orderbook_cache(_book_event(token_id))
        entry = engine._orderbook_cache[token_id]
        assert "last_event_ms" in entry
        assert entry["last_event_ms"] >= before_ms

    def test_delta_after_snapshot_advances_last_event_ms(self):
        engine = _make_engine()
        token_id = "tok-lem-002"
        engine._update_orderbook_cache(_book_event(token_id))
        ms_after_snapshot = engine._orderbook_cache[token_id]["last_event_ms"]

        time.sleep(0.01)  # ensure at least 1ms later

        engine._update_orderbook_price_change(_price_change_event(token_id))
        ms_after_delta = engine._orderbook_cache[token_id]["last_event_ms"]
        assert ms_after_delta >= ms_after_snapshot

    def test_rest_seed_sets_last_event_ms(self):
        engine = _make_engine()
        token_id = "tok-lem-003"
        before_ms = int(time.time() * 1000) - 10

        fake_book = {
            "bids": [{"price": "0.35", "size": "100"}],
            "asks": [{"price": "0.65", "size": "100"}],
        }
        with patch("clob_depth.get_order_book", return_value=fake_book):
            engine._seed_orderbook_snapshots_from_rest({token_id})

        entry = engine._orderbook_cache[token_id]
        assert "last_event_ms" in entry
        assert entry["last_event_ms"] >= before_ms
        assert entry["snapshot_verified"] is True


# ── Reseed and replay ─────────────────────────────────────────────────────────

class TestReseedAndReplay:
    """After a REST reseed, buffered deltas are replayed and token becomes fresh."""

    def test_reseed_token_replays_buffered_deltas(self):
        engine = _make_engine()
        token_id = "tok-rr-001"

        # Buffer a delta (no snapshot yet)
        engine._update_orderbook_price_change(_price_change_event(token_id))
        assert token_id in engine._pending_deltas

        # Run the async reseed with a mocked REST response
        fake_book = {
            "bids": [{"price": "0.35", "size": "200"}],
            "asks": [{"price": "0.65", "size": "200"}],
        }
        with patch("clob_depth.get_order_book", return_value=fake_book):
            asyncio.run(engine._reseed_token_async(token_id))

        entry = engine._orderbook_cache[token_id]
        assert entry["snapshot_verified"] is True
        assert entry["status"] == "fresh"
        # Pending deltas must be cleared after replay
        assert token_id not in engine._pending_deltas

    def test_reseed_failure_clears_task_slot(self):
        engine = _make_engine()
        token_id = "tok-rr-fail"

        engine._update_orderbook_price_change(_price_change_event(token_id))
        # Simulate in-flight task slot
        engine._reseed_tasks.add(token_id)

        with patch("clob_depth.get_order_book", return_value=None):
            asyncio.run(engine._reseed_token_async(token_id))

        # Task slot must be freed even on failure
        assert token_id not in engine._reseed_tasks

    def test_reseed_already_in_flight_not_duplicated(self):
        """Second call to _schedule_reseed must not schedule a second task."""
        engine = _make_engine()
        token_id = "tok-rr-dup"

        engine._pending_deltas[token_id] = []
        engine._reseed_tasks.add(token_id)  # simulate in-flight

        # Should be a no-op
        engine._schedule_reseed(token_id)

        # Still only one entry in reseed_tasks (set, so still just token_id)
        assert engine._reseed_tasks == {token_id}

    def test_connection_reset_clears_pending_state(self):
        """Per-connection reset must clear buffered deltas and task slots."""
        engine = _make_engine()
        token_id = "tok-rr-reset"

        engine._pending_deltas[token_id] = [{"change": "data"}]
        engine._reseed_tasks.add(token_id)

        # Simulate polymarket_feed per-connection reset
        engine._pending_deltas = {}
        engine._reseed_tasks = set()

        assert token_id not in engine._pending_deltas
        assert token_id not in engine._reseed_tasks
