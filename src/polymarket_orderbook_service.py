"""BTC executable Polymarket orderbook service.

This is the replacement critical path for execution freshness. Global cache
health can still be useful, but execution asks this service for the exact side
book it would trade.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from orderbook_cache import DEFAULT_MAX_AGE_S, DEFAULT_PATH, OrderbookCache


DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_METRICS_PATH = DATA_DIR / "btc5m_executable_orderbook_metrics.json"
MAX_SAMPLES = 1000


class PolymarketOrderbookService:
    """Read exact-side executable books and record BTC 5m freshness metrics."""

    def __init__(
        self,
        *,
        cache_path: Path = DEFAULT_PATH,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        max_age_s: float = DEFAULT_MAX_AGE_S,
    ):
        self.cache_path = Path(cache_path)
        self.metrics_path = Path(metrics_path)
        self.max_age_s = max_age_s

    def read_market(self, market_id: str, yes_token: str | None,
                    no_token: str | None) -> dict:
        cache = OrderbookCache.load(self.cache_path, self.max_age_s)
        return {
            "market_id": market_id,
            "yes": self._side_book(cache, market_id, "yes", yes_token),
            "no": self._side_book(cache, market_id, "no", no_token),
        }

    def get_executable_book(
        self,
        market_id: str,
        side: str,
        tokens: dict | None,
        *,
        record_metrics: bool = False,
    ) -> dict:
        side_key = (side or "").lower()
        if side_key not in {"yes", "no"}:
            raise ValueError(f"unknown Polymarket side: {side!r}")
        evidence = self.read_market(
            market_id,
            (tokens or {}).get("yes"),
            (tokens or {}).get("no"),
        )
        book = evidence[side_key]
        if record_metrics:
            record_executable_read(book, self.metrics_path)
        return book

    def _side_book(self, cache: OrderbookCache, market_id: str,
                   side: str, token_id: str | None) -> dict:
        base = {
            "market_id": market_id,
            "side": side,
            "token_id": token_id,
            "status": "missing",
            "source": "missing",
            "age_ms": None,
            "mid": None,
            "best_bid": None,
            "best_ask": None,
            "spread": None,
            "source_ts": None,
            "reason": "missing_token" if not token_id else "missing_cache_entry",
        }
        if not token_id:
            return base
        entry = cache.tokens.get(token_id)
        if not entry:
            return base

        age = entry.age_ms()
        base.update({
            "age_ms": round(age) if age is not None else None,
            "mid": entry.mid,
            "best_bid": entry.best_bid,
            "best_ask": entry.best_ask,
            "spread": entry.spread,
            "source_ts": getattr(entry, "source_ts", None),
        })
        raw_status = getattr(entry, "status", None)
        if age is None:
            base.update({
                "status": "partial" if raw_status == "partial" else "stale",
                "source": "ws_bbo" if raw_status == "partial" else "missing",
                "reason": getattr(entry, "stale_reason", None) or "missing_updated_at",
            })
            return base
        if age > self.max_age_s * 1000:
            base.update({
                "status": "stale",
                "source": "ws_bbo",
                "reason": "stale_updated_at",
            })
            return base
        if entry.valid_mid() is None:
            base.update({
                "status": "partial",
                "source": "ws_bbo",
                "reason": "partial_book",
            })
            return base
        base.update({
            "status": "fresh",
            "source": "ws_bbo",
            "reason": None,
        })
        return base


def record_executable_read(book: dict, metrics_path: Path = DEFAULT_METRICS_PATH) -> dict:
    metrics_path = Path(metrics_path)
    metrics = load_executable_metrics(metrics_path)
    samples = list(metrics.get("_age_samples_ms") or [])
    status = book.get("status") or "missing"
    if status == "fresh" and book.get("age_ms") is not None:
        samples.append(int(book["age_ms"]))
        samples = samples[-MAX_SAMPLES:]

    reads = metrics.get("btc5m_executable_book_reads") or {}
    reads["total"] = int(reads.get("total") or 0) + 1
    reads[status] = int(reads.get(status) or 0) + 1
    side = book.get("side") or "unknown"
    by_side = reads.get("by_side") or {}
    side_counts = by_side.get(side) or {}
    side_counts["total"] = int(side_counts.get("total") or 0) + 1
    side_counts[status] = int(side_counts.get(status) or 0) + 1
    by_side[side] = side_counts
    reads["by_side"] = by_side
    reads["latest_status"] = status
    reads["latest_side"] = side
    reads["latest_reason"] = book.get("reason")
    reads["latest_market_id"] = book.get("market_id")

    metrics = {
        "schema_version": 1,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "_age_samples_ms": samples,
        "btc5m_executable_orderbook_age_ms": _percentiles(samples),
        "btc5m_executable_book_reads": reads,
    }
    _write_json_atomic(metrics_path, metrics)
    return metrics


def load_executable_metrics(metrics_path: Path = DEFAULT_METRICS_PATH) -> dict:
    try:
        path = Path(metrics_path)
        if not path.exists():
            return _empty_metrics()
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            return _empty_metrics()
        return data
    except (OSError, json.JSONDecodeError):
        return _empty_metrics()


def public_metrics(metrics_path: Path = DEFAULT_METRICS_PATH) -> dict:
    data = load_executable_metrics(metrics_path)
    return {
        "btc5m_executable_orderbook_age_ms": (
            data.get("btc5m_executable_orderbook_age_ms") or _percentiles([])
        ),
        "btc5m_executable_book_reads": (
            data.get("btc5m_executable_book_reads") or {}
        ),
    }


def _empty_metrics() -> dict:
    return {
        "schema_version": 1,
        "written_at": None,
        "_age_samples_ms": [],
        "btc5m_executable_orderbook_age_ms": _percentiles([]),
        "btc5m_executable_book_reads": {
            "total": 0,
            "fresh": 0,
            "stale": 0,
            "missing": 0,
            "partial": 0,
            "by_side": {},
        },
    }


def _percentiles(samples: list[int]) -> dict:
    if not samples:
        return {"p50": 0, "p95": 0, "samples": 0}
    values = sorted(int(v) for v in samples)
    n = len(values)
    return {
        "p50": values[n // 2],
        "p95": values[int(n * 0.95)] if n >= 20 else values[-1],
        "samples": n,
    }


def _write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(path)
