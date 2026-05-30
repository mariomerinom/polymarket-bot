"""Tests for BTC executable Polymarket orderbook service."""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _cache_file(tmp_path, markets):
    path = tmp_path / "btc5m_executable_orderbook.json"
    path.write_text(json.dumps({"version": 1, "markets": markets}))
    return path


def test_get_executable_book_requires_exact_side_token(tmp_path):
    from polymarket_orderbook_service import PolymarketOrderbookService

    now = datetime.now(timezone.utc).isoformat()
    cache_path = _cache_file(tmp_path, {
        "m1": {
            "yes": {
                "token_id": "yes",
                "mid": 0.53,
                "best_bid": 0.52,
                "best_ask": 0.54,
                "spread": 0.02,
                "updated_at": now,
                "status": "fresh",
            }
        }
    })
    service = PolymarketOrderbookService(executable_cache_path=cache_path)

    book = service.get_executable_book("m1", "no", {"yes": "yes", "no": "no"})

    assert book["side"] == "no"
    assert book["token_id"] == "no"
    assert book["status"] == "missing"
    assert book["best_ask"] is None


def test_get_executable_book_returns_fresh_side_book(tmp_path):
    from polymarket_orderbook_service import PolymarketOrderbookService

    now = datetime.now(timezone.utc).isoformat()
    cache_path = _cache_file(tmp_path, {
        "m1": {
            "no": {
                "token_id": "no",
                "mid": 0.47,
                "best_bid": 0.46,
                "best_ask": 0.48,
                "spread": 0.02,
                "updated_at": now,
                "status": "fresh",
                "source_ts": "1770000000123",
                "snapshot_verified": True,
            }
        }
    })
    service = PolymarketOrderbookService(executable_cache_path=cache_path)

    book = service.get_executable_book("m1", "no", {"yes": "yes", "no": "no"})

    assert book["status"] == "fresh"
    assert book["source"] == "executable_sidecar"
    assert book["best_bid"] == 0.46
    assert book["best_ask"] == 0.48
    assert book["age_ms"] is not None
    assert book["source_ts"] == "1770000000123"


def test_get_executable_book_marks_old_side_stale(tmp_path):
    from polymarket_orderbook_service import PolymarketOrderbookService

    old = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    cache_path = _cache_file(tmp_path, {
        "m1": {
            "yes": {
                "token_id": "yes",
                "mid": 0.53,
                "best_bid": 0.52,
                "best_ask": 0.54,
                "spread": 0.02,
                "updated_at": old,
                "status": "fresh",
            }
        }
    })
    service = PolymarketOrderbookService(executable_cache_path=cache_path, max_age_s=2)

    book = service.get_executable_book("m1", "yes", {"yes": "yes", "no": "no"})

    assert book["status"] == "stale"
    assert book["age_ms"] >= 29_000


def test_record_executable_read_metrics_writes_p95_and_counts(tmp_path):
    from polymarket_orderbook_service import (
        PolymarketOrderbookService,
        load_executable_metrics,
    )

    now = datetime.now(timezone.utc).isoformat()
    cache_path = _cache_file(tmp_path, {
        "m1": {
            "yes": {
                "token_id": "yes",
                "mid": 0.53,
                "best_bid": 0.52,
                "best_ask": 0.54,
                "spread": 0.02,
                "updated_at": now,
                "status": "fresh",
                "snapshot_verified": True,
            }
        }
    })
    metrics_path = tmp_path / "btc5m_exec_metrics.json"
    service = PolymarketOrderbookService(
        executable_cache_path=cache_path,
        metrics_path=metrics_path,
    )

    service.get_executable_book(
        "m1",
        "yes",
        {"yes": "yes", "no": "no"},
        record_metrics=True,
    )
    service.get_executable_book(
        "m1",
        "no",
        {"yes": "yes", "no": "no"},
        record_metrics=True,
    )

    metrics = load_executable_metrics(metrics_path)

    assert metrics["btc5m_executable_orderbook_age_ms"]["samples"] == 1
    assert metrics["btc5m_executable_book_reads"]["total"] == 2
    assert metrics["btc5m_executable_book_reads"]["fresh"] == 1
    assert metrics["btc5m_executable_book_reads"]["missing"] == 1


def test_record_executable_read_metrics_tracks_provider_breakdown(tmp_path):
    from polymarket_orderbook_service import (
        load_executable_metrics,
        record_executable_read,
    )

    metrics_path = tmp_path / "btc5m_exec_metrics.json"
    record_executable_read({
        "market_id": "m1",
        "side": "yes",
        "status": "fresh",
        "age_ms": 800,
        "source": "vendor:custom",
        "provider_mode": "vendor_primary",
        "provider_vendor": "custom",
        "provider_chosen_source": "vendor",
        "provider_vendor_status": "fresh",
        "provider_internal_status": "fresh",
        "provider_fallback_used": False,
        "provider_disagreement": True,
        "provider_vendor_feed_connected": True,
        "provider_disagreement_tolerance": 0.03,
    }, metrics_path)
    record_executable_read({
        "market_id": "m2",
        "side": "no",
        "status": "fresh",
        "age_ms": 900,
        "source": "executable_sidecar",
        "provider_mode": "vendor_primary",
        "provider_vendor": "custom",
        "provider_chosen_source": "internal",
        "provider_vendor_status": "stale",
        "provider_internal_status": "fresh",
        "provider_fallback_used": True,
        "provider_disagreement": False,
        "provider_vendor_feed_connected": False,
    }, metrics_path)

    provider = load_executable_metrics(metrics_path)["market_data_provider"]

    assert provider["mode"] == "vendor_primary"
    assert provider["vendor"] == "custom"
    assert provider["chosen_source"] == "internal"
    assert provider["vendor_feed_connected"] is False
    assert provider["fallback_count"] == 1
    assert provider["fallback_rate"] == 0.5
    assert provider["disagreement_count"] == 1
    assert provider["by_source"]["vendor"]["fresh"] == 1
    assert provider["by_source"]["vendor"]["stale"] == 1
    assert provider["by_source"]["internal"]["fresh"] == 2


def test_sample_executable_cache_metrics_records_fresh_side_ages(tmp_path):
    from polymarket_orderbook_service import (
        sample_executable_cache,
        load_executable_metrics,
    )

    now = datetime.now(timezone.utc).isoformat()
    cache_path = _cache_file(tmp_path, {
        "m1": {
            "yes": {
                "token_id": "yes",
                "side": "yes",
                "mid": 0.53,
                "best_bid": 0.52,
                "best_ask": 0.54,
                "spread": 0.02,
                "updated_at": now,
                "status": "fresh",
                "snapshot_verified": True,
            },
            "no": {
                "token_id": "no",
                "side": "no",
                "status": "missing",
            },
        }
    })
    metrics_path = tmp_path / "btc5m_exec_metrics.json"

    sample_executable_cache(cache_path, metrics_path=metrics_path)

    metrics = load_executable_metrics(metrics_path)
    assert metrics["btc5m_executable_orderbook_age_ms"]["samples"] == 1
    assert metrics["btc5m_executable_book_reads"]["total"] == 2
    assert metrics["btc5m_executable_book_reads"]["fresh"] == 1
    assert metrics["btc5m_executable_book_reads"]["missing"] == 1


def test_build_executable_cache_derives_from_token_cache_without_mirror_state():
    from polymarket_orderbook_service import build_executable_cache

    now = datetime.now(timezone.utc).isoformat()
    token_cache = {
        "yes_tok": {
            "mid": 0.53,
            "best_bid": 0.52,
            "best_ask": 0.54,
            "spread": 0.02,
            "updated_at": now,
            "source_ts": "1770000000123",
            "status": "fresh",
        },
        "no_tok": {
            "updated_at": None,
            "status": "stale",
            "stale_reason": "missing_snapshot_for_price_change",
        },
        "eth_tok": {
            "mid": 0.44,
            "best_bid": 0.43,
            "best_ask": 0.45,
            "spread": 0.02,
            "updated_at": now,
            "status": "fresh",
        },
    }
    token_context = {
        "yes_tok": {"market_id": "btc-market", "side": "YES", "pipeline": "btc_5m"},
        "no_tok": {"market_id": "btc-market", "side": "NO", "pipeline": "btc_5m"},
        "missing_tok": {"market_id": "btc-market", "side": "NO", "pipeline": "btc_5m"},
        "eth_tok": {"market_id": "eth-market", "side": "YES", "pipeline": "eth_5m"},
    }

    cache = build_executable_cache(
        token_cache,
        token_context,
        active_token_ids={"yes_tok", "no_tok", "missing_tok", "eth_tok"},
    )

    assert cache["version"] == 2
    assert set(cache["markets"]) == {"btc-market"}
    yes = cache["markets"]["btc-market"]["yes"]
    no = cache["markets"]["btc-market"]["no"]
    assert yes["token_id"] == "yes_tok"
    assert yes["status"] == "fresh"
    assert yes["best_ask"] == 0.54
    assert no["token_id"] == "no_tok"
    assert no["status"] == "stale"
    assert no["reason"] == "missing_snapshot_for_price_change"
