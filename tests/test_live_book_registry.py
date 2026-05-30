"""Tests for src/live_book_registry.py — process-global in-memory orderbook registry.

Red phase: all tests should FAIL until live_book_registry.py is implemented.

Schema mirrors _orderbook_cache entries in botsy_engine.py:
    mid, spread, best_bid, best_ask, updated_at, last_event_ms,
    snapshot_verified, status
"""

import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_entry(token_id: str = "0xabc", mid: float = 0.55) -> dict:
    """Return a realistic orderbook cache entry for testing."""
    return {
        "mid": mid,
        "spread": 0.02,
        "best_bid": mid - 0.01,
        "best_ask": mid + 0.01,
        "updated_at": "2026-05-30T00:00:00+00:00",
        "last_event_ms": 1_748_563_200_000,
        "snapshot_verified": True,
        "status": "fresh",
        "token_id": token_id,
    }


# ---------------------------------------------------------------------------
# TestPublishAndRead
# ---------------------------------------------------------------------------

class TestPublishAndRead:
    """publish_token / read_token round-trip and copy semantics."""

    def setup_method(self):
        import live_book_registry
        live_book_registry.reset()

    def test_published_token_can_be_read_back(self):
        import live_book_registry

        entry = _sample_entry("0xaaa", mid=0.60)
        live_book_registry.publish_token("0xaaa", entry)

        result = live_book_registry.read_token("0xaaa")
        assert result is not None
        assert result["mid"] == 0.60
        assert result["status"] == "fresh"
        assert result["snapshot_verified"] is True

    def test_read_returns_all_published_fields(self):
        import live_book_registry

        entry = _sample_entry("0xbbb", mid=0.45)
        live_book_registry.publish_token("0xbbb", entry)
        result = live_book_registry.read_token("0xbbb")

        for key in ("mid", "spread", "best_bid", "best_ask", "updated_at",
                    "last_event_ms", "snapshot_verified", "status"):
            assert key in result, f"Missing field: {key}"

    def test_read_missing_token_returns_none(self):
        import live_book_registry

        result = live_book_registry.read_token("0xDEADBEEF")
        assert result is None

    def test_publish_stores_copy_not_reference(self):
        """Engine mutations after publish must NOT alter the registry."""
        import live_book_registry

        entry = _sample_entry("0xccc", mid=0.50)
        live_book_registry.publish_token("0xccc", entry)

        # Mutate the original dict after publishing
        entry["mid"] = 0.99
        entry["status"] = "stale"

        stored = live_book_registry.read_token("0xccc")
        assert stored["mid"] == 0.50, "Registry was mutated by post-publish change to source dict"
        assert stored["status"] == "fresh"

    def test_read_returns_copy_not_reference(self):
        """Caller mutations to the returned dict must NOT corrupt the registry."""
        import live_book_registry

        live_book_registry.publish_token("0xddd", _sample_entry("0xddd", mid=0.70))
        result = live_book_registry.read_token("0xddd")

        # Mutate the returned dict
        result["mid"] = 0.00
        result["status"] = "corrupted"

        # Second read must still see original values
        second = live_book_registry.read_token("0xddd")
        assert second["mid"] == 0.70, "Registry was corrupted by caller mutation of returned dict"
        assert second["status"] == "fresh"

    def test_publish_overwrites_previous_entry(self):
        """A second publish for the same token replaces the first."""
        import live_book_registry

        live_book_registry.publish_token("0xeee", _sample_entry("0xeee", mid=0.30))
        live_book_registry.publish_token("0xeee", _sample_entry("0xeee", mid=0.80))

        result = live_book_registry.read_token("0xeee")
        assert result["mid"] == 0.80

    def test_multiple_tokens_stored_independently(self):
        import live_book_registry

        live_book_registry.publish_token("0x111", _sample_entry("0x111", mid=0.10))
        live_book_registry.publish_token("0x222", _sample_entry("0x222", mid=0.90))

        assert live_book_registry.read_token("0x111")["mid"] == 0.10
        assert live_book_registry.read_token("0x222")["mid"] == 0.90


# ---------------------------------------------------------------------------
# TestEnginePresence
# ---------------------------------------------------------------------------

class TestEnginePresence:
    """engine_is_live / set_engine_present behaviour."""

    def setup_method(self):
        import live_book_registry
        live_book_registry.reset()

    def test_engine_is_live_starts_false(self):
        import live_book_registry

        assert live_book_registry.engine_is_live() is False

    def test_set_engine_present_true_makes_live(self):
        import live_book_registry

        live_book_registry.set_engine_present(True)
        assert live_book_registry.engine_is_live() is True

    def test_set_engine_present_false_makes_not_live(self):
        import live_book_registry

        live_book_registry.set_engine_present(True)
        live_book_registry.set_engine_present(False)
        assert live_book_registry.engine_is_live() is False

    def test_set_engine_present_idempotent_true(self):
        """Calling set_engine_present(True) twice should not error."""
        import live_book_registry

        live_book_registry.set_engine_present(True)
        live_book_registry.set_engine_present(True)
        assert live_book_registry.engine_is_live() is True

    def test_engine_presence_independent_of_registry_contents(self):
        """Publishing tokens must not change engine_is_live()."""
        import live_book_registry

        assert live_book_registry.engine_is_live() is False
        live_book_registry.publish_token("0xfff", _sample_entry())
        assert live_book_registry.engine_is_live() is False


# ---------------------------------------------------------------------------
# TestReset
# ---------------------------------------------------------------------------

class TestReset:
    """reset() clears all state."""

    def setup_method(self):
        import live_book_registry
        live_book_registry.reset()

    def test_reset_clears_published_tokens(self):
        import live_book_registry

        live_book_registry.publish_token("0x001", _sample_entry())
        live_book_registry.publish_token("0x002", _sample_entry())
        live_book_registry.reset()

        assert live_book_registry.read_token("0x001") is None
        assert live_book_registry.read_token("0x002") is None

    def test_reset_sets_engine_present_false(self):
        import live_book_registry

        live_book_registry.set_engine_present(True)
        live_book_registry.reset()

        assert live_book_registry.engine_is_live() is False

    def test_reset_clears_all_tokens_via_all_tokens(self):
        import live_book_registry

        live_book_registry.publish_token("0x003", _sample_entry())
        live_book_registry.reset()

        assert live_book_registry.all_tokens() == {}

    def test_module_starts_clean_on_fresh_import(self):
        """A freshly imported module (post-reset) has no tokens and engine=False."""
        import live_book_registry

        # reset() called in setup_method — no publish has happened yet
        assert live_book_registry.read_token("any") is None
        assert live_book_registry.engine_is_live() is False

    def test_state_after_reset_is_fully_usable(self):
        """After reset, publish/read should work normally."""
        import live_book_registry

        live_book_registry.publish_token("0xaaa", _sample_entry("0xaaa", mid=0.40))
        live_book_registry.reset()

        live_book_registry.publish_token("0xbbb", _sample_entry("0xbbb", mid=0.55))
        assert live_book_registry.read_token("0xaaa") is None
        assert live_book_registry.read_token("0xbbb")["mid"] == 0.55


# ---------------------------------------------------------------------------
# TestConcurrentAccess
# ---------------------------------------------------------------------------

class TestConcurrentAccess:
    """Thread-safety smoke test: 10 threads publish and read concurrently."""

    def setup_method(self):
        import live_book_registry
        live_book_registry.reset()

    def test_concurrent_publish_read_no_race(self):
        """10 threads writing and reading concurrently must not crash or corrupt."""
        import live_book_registry

        errors: list[Exception] = []
        results: list[dict | None] = []
        lock = threading.Lock()

        def worker(tid: int):
            token = f"0x{tid:04x}"
            try:
                for i in range(20):
                    live_book_registry.publish_token(
                        token,
                        _sample_entry(token, mid=round(0.01 * (i + 1), 4)),
                    )
                    entry = live_book_registry.read_token(token)
                    with lock:
                        results.append(entry)
            except Exception as exc:  # noqa: BLE001
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Exceptions in threads: {errors}"
        # Every non-None result must be a dict with expected keys
        for entry in results:
            if entry is not None:
                assert isinstance(entry, dict)
                assert "mid" in entry
                assert "status" in entry

    def test_concurrent_readers_get_valid_dicts(self):
        """Pre-populate 5 tokens then read them from 10 threads simultaneously."""
        import live_book_registry

        token_ids = [f"0xR{i:03x}" for i in range(5)]
        for tid in token_ids:
            live_book_registry.publish_token(tid, _sample_entry(tid, mid=0.50))

        bad_reads: list[str] = []
        lock = threading.Lock()

        def reader(tid: str):
            for _ in range(50):
                entry = live_book_registry.read_token(tid)
                if entry is None or not isinstance(entry, dict) or "mid" not in entry:
                    with lock:
                        bad_reads.append(tid)

        threads = [
            threading.Thread(target=reader, args=(tid,))
            for tid in token_ids
            for _ in range(2)  # 2 reader threads per token = 10 total
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert bad_reads == [], f"Bad reads on tokens: {bad_reads}"

    def test_concurrent_publish_no_cross_contamination(self):
        """Two threads publishing different tokens must not mix entries."""
        import live_book_registry

        token_a = "0xAAAA"
        token_b = "0xBBBB"
        errors: list[str] = []
        lock = threading.Lock()

        def publish_a():
            for _ in range(100):
                live_book_registry.publish_token(token_a, _sample_entry(token_a, mid=0.11))

        def publish_b():
            for _ in range(100):
                live_book_registry.publish_token(token_b, _sample_entry(token_b, mid=0.99))

        def reader():
            for _ in range(200):
                ea = live_book_registry.read_token(token_a)
                eb = live_book_registry.read_token(token_b)
                if ea is not None and abs(ea["mid"] - 0.11) > 1e-9:
                    with lock:
                        errors.append(f"token_a contaminated: mid={ea['mid']}")
                if eb is not None and abs(eb["mid"] - 0.99) > 1e-9:
                    with lock:
                        errors.append(f"token_b contaminated: mid={eb['mid']}")

        threads = [
            threading.Thread(target=publish_a),
            threading.Thread(target=publish_b),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Cross-contamination detected: {errors[:5]}"


# ---------------------------------------------------------------------------
# TestAllTokens
# ---------------------------------------------------------------------------

class TestAllTokens:
    """all_tokens() returns a snapshot of the full registry."""

    def setup_method(self):
        import live_book_registry
        live_book_registry.reset()

    def test_all_tokens_empty_when_nothing_published(self):
        import live_book_registry

        assert live_book_registry.all_tokens() == {}

    def test_all_tokens_contains_published_entries(self):
        import live_book_registry

        live_book_registry.publish_token("0xP1", _sample_entry("0xP1", mid=0.20))
        live_book_registry.publish_token("0xP2", _sample_entry("0xP2", mid=0.80))

        snapshot = live_book_registry.all_tokens()
        assert "0xP1" in snapshot
        assert "0xP2" in snapshot
        assert snapshot["0xP1"]["mid"] == 0.20
        assert snapshot["0xP2"]["mid"] == 0.80

    def test_all_tokens_count_matches_published_count(self):
        import live_book_registry

        tokens = [f"0xT{i:02x}" for i in range(7)]
        for t in tokens:
            live_book_registry.publish_token(t, _sample_entry(t))

        assert len(live_book_registry.all_tokens()) == 7

    def test_modifying_all_tokens_result_does_not_affect_registry(self):
        """Caller mutation of the all_tokens() snapshot must not corrupt stored entries."""
        import live_book_registry

        live_book_registry.publish_token("0xQ1", _sample_entry("0xQ1", mid=0.33))
        snapshot = live_book_registry.all_tokens()

        # Mutate the snapshot
        snapshot["0xQ1"]["mid"] = 9999.0
        snapshot["0xNEW"] = {"mid": 0.0}

        # Registry must be unaffected
        stored = live_book_registry.read_token("0xQ1")
        assert stored["mid"] == 0.33
        assert "0xNEW" not in live_book_registry.all_tokens()

    def test_all_tokens_after_overwrite_reflects_latest(self):
        """all_tokens() must show the latest published value for a token."""
        import live_book_registry

        live_book_registry.publish_token("0xW1", _sample_entry("0xW1", mid=0.10))
        live_book_registry.publish_token("0xW1", _sample_entry("0xW1", mid=0.90))

        snapshot = live_book_registry.all_tokens()
        assert snapshot["0xW1"]["mid"] == 0.90

    def test_all_tokens_does_not_include_reset_entries(self):
        """Entries published before reset must not appear in all_tokens() after reset."""
        import live_book_registry

        live_book_registry.publish_token("0xZ1", _sample_entry("0xZ1"))
        live_book_registry.reset()

        assert "0xZ1" not in live_book_registry.all_tokens()
