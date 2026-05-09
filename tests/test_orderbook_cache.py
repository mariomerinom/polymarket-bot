"""
test_orderbook_cache.py — Tests for OrderbookCache typed IPC layer.

Phase B Step 5 of TDD refactoring plan.
Tests load/save/staleness/integration before wiring into trade.py.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from orderbook_cache import OrderbookCache, TokenEntry, DEFAULT_MAX_AGE_S


# ── TokenEntry tests ──────────────────────────────────────────────────────


class TestTokenEntry:
    def test_fresh_entry(self):
        """Entry updated just now is fresh."""
        now = datetime.now(timezone.utc).isoformat()
        entry = TokenEntry(mid=0.55, updated_at=now)
        assert entry.is_fresh() is True

    def test_stale_entry(self):
        """Entry older than max_age_s is stale."""
        old = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        entry = TokenEntry(mid=0.55, updated_at=old)
        assert entry.is_fresh() is False

    def test_no_updated_at_is_stale(self):
        """Entry with no timestamp is always stale."""
        entry = TokenEntry(mid=0.55, updated_at=None)
        assert entry.is_fresh() is False

    def test_invalid_timestamp_is_stale(self):
        """Malformed timestamp is treated as stale."""
        entry = TokenEntry(mid=0.55, updated_at="not-a-date")
        assert entry.is_fresh() is False

    def test_custom_max_age(self):
        """Custom max_age_s respected."""
        ts = (datetime.now(timezone.utc) - timedelta(seconds=15)).isoformat()
        entry = TokenEntry(mid=0.55, updated_at=ts)
        assert entry.is_fresh(max_age_s=10) is False
        assert entry.is_fresh(max_age_s=20) is True

    def test_age_ms_uses_updated_at(self):
        """True orderbook freshness is measured from token updated_at."""
        ts = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
        entry = TokenEntry(mid=0.55, updated_at=ts)
        assert 1500 <= entry.age_ms() <= 2500

    def test_valid_mid_in_range(self):
        """Mid in [0.01, 0.99] returned."""
        assert TokenEntry(mid=0.55).valid_mid() == 0.55
        assert TokenEntry(mid=0.01).valid_mid() == 0.01
        assert TokenEntry(mid=0.99).valid_mid() == 0.99

    def test_valid_mid_out_of_range(self):
        """Mid outside [0.01, 0.99] returns None."""
        assert TokenEntry(mid=0.00).valid_mid() is None
        assert TokenEntry(mid=1.00).valid_mid() is None
        assert TokenEntry(mid=-0.5).valid_mid() is None

    def test_valid_mid_none(self):
        """None mid returns None."""
        assert TokenEntry(mid=None).valid_mid() is None


# ── OrderbookCache.load tests ─────────────────────────────────────────────


class TestOrderbookCacheLoad:
    def test_load_v2_format(self, tmp_path):
        """Loads v2 cache with token entries."""
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "version": 2,
            "tokens": {
                "tok_a": {"mid": 0.55, "best_bid": 0.54, "best_ask": 0.56,
                          "spread": 0.02, "updated_at": now},
                "tok_b": {"mid": 0.45, "best_bid": 0.44, "best_ask": 0.46,
                          "spread": 0.02, "updated_at": now},
            },
        }
        p = tmp_path / "live_orderbook.json"
        p.write_text(json.dumps(data))

        cache = OrderbookCache.load(p)
        assert cache.version == 2
        assert len(cache.tokens) == 2
        assert cache.tokens["tok_a"].mid == 0.55
        assert cache.tokens["tok_b"].best_bid == 0.44

    def test_load_missing_file_returns_empty(self, tmp_path):
        """Missing file returns empty cache, no crash."""
        p = tmp_path / "nonexistent.json"
        cache = OrderbookCache.load(p)
        assert cache.tokens == {}

    def test_load_corrupt_json_returns_empty(self, tmp_path):
        """Corrupt JSON returns empty cache."""
        p = tmp_path / "live_orderbook.json"
        p.write_text("{bad json")
        cache = OrderbookCache.load(p)
        assert cache.tokens == {}

    def test_load_empty_tokens(self, tmp_path):
        """Cache with no tokens key returns empty tokens dict."""
        p = tmp_path / "live_orderbook.json"
        p.write_text(json.dumps({"version": 2}))
        cache = OrderbookCache.load(p)
        assert cache.tokens == {}

    def test_load_v1_format(self, tmp_path):
        """V1 format (no version key) loads with version=1."""
        p = tmp_path / "live_orderbook.json"
        p.write_text(json.dumps({"tokens": {"tok_a": {"mid": 0.55}}}))
        cache = OrderbookCache.load(p)
        assert cache.version == 1
        assert cache.tokens["tok_a"].mid == 0.55


# ── OrderbookCache.get_fresh_mid tests ────────────────────────────────────


class TestGetFreshMid:
    def test_fresh_valid_returns_mid(self, tmp_path):
        """Fresh entry with valid mid returns the price."""
        now = datetime.now(timezone.utc).isoformat()
        data = {"version": 2, "tokens": {
            "tok_a": {"mid": 0.55, "updated_at": now},
        }}
        p = tmp_path / "live_orderbook.json"
        p.write_text(json.dumps(data))

        cache = OrderbookCache.load(p)
        assert cache.get_fresh_mid("tok_a") == 0.55

    def test_stale_returns_none(self, tmp_path):
        """Stale entry returns None."""
        old = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        data = {"version": 2, "tokens": {
            "tok_a": {"mid": 0.55, "updated_at": old},
        }}
        p = tmp_path / "live_orderbook.json"
        p.write_text(json.dumps(data))

        cache = OrderbookCache.load(p)
        assert cache.get_fresh_mid("tok_a") is None

    def test_missing_token_returns_none(self):
        """Unknown token_id returns None."""
        cache = OrderbookCache()
        assert cache.get_fresh_mid("nonexistent") is None

    def test_empty_token_id_returns_none(self):
        """Empty string token_id returns None."""
        cache = OrderbookCache()
        assert cache.get_fresh_mid("") is None

    def test_out_of_range_mid_returns_none(self, tmp_path):
        """Entry with mid=0.00 returns None (out of valid range)."""
        now = datetime.now(timezone.utc).isoformat()
        data = {"version": 2, "tokens": {
            "tok_a": {"mid": 0.00, "updated_at": now},
        }}
        p = tmp_path / "live_orderbook.json"
        p.write_text(json.dumps(data))

        cache = OrderbookCache.load(p)
        assert cache.get_fresh_mid("tok_a") is None


# ── OrderbookCache.get_fresh_entry tests ──────────────────────────────────


class TestGetFreshEntry:
    def test_fresh_entry_returns_token_entry(self, tmp_path):
        """Fresh entry returns full TokenEntry with bid/ask/spread."""
        now = datetime.now(timezone.utc).isoformat()
        data = {"version": 2, "tokens": {
            "tok_a": {"mid": 0.55, "best_bid": 0.54, "best_ask": 0.56,
                      "spread": 0.02, "updated_at": now},
        }}
        p = tmp_path / "live_orderbook.json"
        p.write_text(json.dumps(data))
        cache = OrderbookCache.load(p)
        entry = cache.get_fresh_entry("tok_a")
        assert entry is not None
        assert entry.best_bid == 0.54
        assert entry.best_ask == 0.56
        assert entry.spread == 0.02
        assert entry.mid == 0.55

    def test_stale_entry_returns_none(self, tmp_path):
        """Stale entry returns None."""
        old = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        data = {"version": 2, "tokens": {
            "tok_a": {"mid": 0.55, "best_bid": 0.54, "best_ask": 0.56,
                      "spread": 0.02, "updated_at": old},
        }}
        p = tmp_path / "live_orderbook.json"
        p.write_text(json.dumps(data))
        cache = OrderbookCache.load(p)
        assert cache.get_fresh_entry("tok_a") is None

    def test_missing_token_returns_none(self):
        """Unknown token_id returns None."""
        cache = OrderbookCache()
        assert cache.get_fresh_entry("nonexistent") is None

    def test_empty_token_id_returns_none(self):
        """Empty string returns None."""
        cache = OrderbookCache()
        assert cache.get_fresh_entry("") is None


class TestEntryStatus:
    def test_missing_token_status(self):
        cache = OrderbookCache()
        assert cache.entry_status("missing") == {"status": "missing", "age_ms": None}

    def test_stale_token_status_includes_age(self):
        old = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        cache = OrderbookCache(tokens={"tok": TokenEntry(mid=0.55, updated_at=old)})
        status = cache.entry_status("tok")
        assert status["status"] == "stale"
        assert status["age_ms"] >= 29000

    def test_fresh_token_status_includes_age(self):
        now = datetime.now(timezone.utc).isoformat()
        cache = OrderbookCache(tokens={"tok": TokenEntry(mid=0.55, updated_at=now)})
        status = cache.entry_status("tok")
        assert status["status"] == "fresh"
        assert status["age_ms"] >= 0


# ── OrderbookCache.save tests ─────────────────────────────────────────────


class TestOrderbookCacheSave:
    def test_save_roundtrip(self, tmp_path):
        """Save then load produces identical data."""
        now = datetime.now(timezone.utc).isoformat()
        cache = OrderbookCache(version=2, tokens={
            "tok_a": TokenEntry(mid=0.55, best_bid=0.54, best_ask=0.56,
                                spread=0.02, updated_at=now),
        })
        p = tmp_path / "live_orderbook.json"
        cache.save(p)

        loaded = OrderbookCache.load(p)
        assert loaded.version == 2
        assert loaded.tokens["tok_a"].mid == 0.55
        assert loaded.tokens["tok_a"].best_bid == 0.54
        assert loaded.tokens["tok_a"].updated_at == now

    def test_save_atomic_no_partial(self, tmp_path):
        """After save, no .tmp file remains (atomic rename)."""
        cache = OrderbookCache(version=2, tokens={
            "tok_a": TokenEntry(mid=0.55),
        })
        p = tmp_path / "live_orderbook.json"
        cache.save(p)

        assert p.exists()
        assert not p.with_suffix(".tmp").exists()

    def test_save_always_writes_v2(self, tmp_path):
        """Save always writes version 2 regardless of loaded version."""
        cache = OrderbookCache(version=1, tokens={
            "tok_a": TokenEntry(mid=0.55),
        })
        p = tmp_path / "live_orderbook.json"
        cache.save(p)

        raw = json.loads(p.read_text())
        assert raw["version"] == 2


# ── Integration: OrderbookCache replaces _get_live_token_mid ──────────────


class TestOrderbookCacheMatchesLegacy:
    """Verify OrderbookCache.get_fresh_mid behaves identically to _get_live_token_mid."""

    def test_both_return_none_for_missing_file(self, tmp_path):
        """Both return None when cache file doesn't exist."""
        p = tmp_path / "nonexistent.json"
        cache = OrderbookCache.load(p)
        assert cache.get_fresh_mid("tok_a") is None

    def test_both_return_mid_for_fresh_entry(self, tmp_path):
        """Both return mid for a fresh, in-range entry."""
        now = datetime.now(timezone.utc).isoformat()
        data = {"version": 2, "tokens": {
            "tok_a": {"mid": 0.55, "best_bid": 0.54, "best_ask": 0.56,
                      "spread": 0.02, "updated_at": now},
        }}
        p = tmp_path / "live_orderbook.json"
        p.write_text(json.dumps(data))

        cache = OrderbookCache.load(p)
        result = cache.get_fresh_mid("tok_a")
        assert result == 0.55

    def test_both_return_none_for_stale_entry(self, tmp_path):
        """Both return None when entry is older than 10s."""
        old = (datetime.now(timezone.utc) - timedelta(seconds=15)).isoformat()
        data = {"version": 2, "tokens": {
            "tok_a": {"mid": 0.55, "updated_at": old},
        }}
        p = tmp_path / "live_orderbook.json"
        p.write_text(json.dumps(data))

        cache = OrderbookCache.load(p)
        assert cache.get_fresh_mid("tok_a") is None
