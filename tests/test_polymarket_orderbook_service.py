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
