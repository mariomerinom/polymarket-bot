"""BTC executable Polymarket orderbook service.

This is the replacement critical path for execution freshness. The broad
token-level cache remains useful for diagnostics, but BTC promotion evidence
comes from a smaller sidecar keyed by market_id + side.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from orderbook_cache import DEFAULT_MAX_AGE_S


DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_EXECUTABLE_CACHE_PATH = DATA_DIR / "btc5m_executable_orderbook.json"
DEFAULT_METRICS_PATH = DATA_DIR / "btc5m_executable_orderbook_metrics.json"
MAX_SAMPLES = 1000


class PolymarketOrderbookService:
    """Read exact-side executable books and record BTC 5m freshness metrics."""

    def __init__(
        self,
        *,
        executable_cache_path: Path | None = None,
        cache_path: Path | None = None,
        metrics_path: Path = DEFAULT_METRICS_PATH,
        max_age_s: float = DEFAULT_MAX_AGE_S,
    ):
        # `cache_path` is accepted only for older tests/callers; it now points
        # at the executable sidecar, not the broad live_orderbook cache.
        self.executable_cache_path = Path(
            executable_cache_path or cache_path or DEFAULT_EXECUTABLE_CACHE_PATH
        )
        self.metrics_path = Path(metrics_path)
        self.max_age_s = max_age_s

    def read_market(self, market_id: str, yes_token: str | None,
                    no_token: str | None) -> dict:
        cache = load_executable_cache(self.executable_cache_path)
        market = (cache.get("markets") or {}).get(market_id) or {}
        return {
            "market_id": market_id,
            "yes": self._side_book(market, market_id, "yes", yes_token),
            "no": self._side_book(market, market_id, "no", no_token),
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

    def _side_book(self, market: dict, market_id: str,
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
        entry = market.get(side) if isinstance(market, dict) else None
        if not isinstance(entry, dict):
            return base
        if entry.get("token_id") and entry.get("token_id") != token_id:
            base["reason"] = "token_mismatch"
            return base

        age = _age_ms(entry.get("updated_at"))
        base.update({
            "age_ms": round(age) if age is not None else None,
            "mid": entry.get("mid"),
            "best_bid": entry.get("best_bid"),
            "best_ask": entry.get("best_ask"),
            "spread": entry.get("spread"),
            "source_ts": entry.get("source_ts"),
        })
        raw_status = entry.get("status")
        if raw_status == "missing":
            base.update({
                "status": "missing",
                "source": entry.get("source") or "executable_sidecar",
                "reason": entry.get("reason") or "missing_cache_entry",
            })
            return base
        if age is None:
            base.update({
                "status": "partial" if raw_status == "partial" else "stale",
                "source": entry.get("source") or "executable_sidecar",
                "reason": entry.get("stale_reason") or entry.get("reason") or "missing_updated_at",
            })
            return base
        if age > self.max_age_s * 1000:
            base.update({
                "status": "stale",
                "source": entry.get("source") or "executable_sidecar",
                "reason": "stale_updated_at",
            })
            return base
        if _valid_mid(entry.get("mid")) is None or raw_status == "partial":
            base.update({
                "status": "partial",
                "source": entry.get("source") or "executable_sidecar",
                "reason": entry.get("reason") or "partial_book",
            })
            return base
        if raw_status == "stale":
            base.update({
                "status": "stale",
                "source": entry.get("source") or "executable_sidecar",
                "reason": entry.get("stale_reason") or entry.get("reason") or "stale_entry",
            })
            return base
        base.update({
            "status": "fresh",
            "source": entry.get("source") or "executable_sidecar",
            "reason": None,
        })
        return base


def load_executable_cache(cache_path: Path = DEFAULT_EXECUTABLE_CACHE_PATH) -> dict:
    try:
        path = Path(cache_path)
        if not path.exists():
            return {"version": 1, "markets": {}}
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            return {"version": 1, "markets": {}}
        data.setdefault("markets", {})
        return data
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "markets": {}}


def sample_executable_cache(
    cache_path: Path = DEFAULT_EXECUTABLE_CACHE_PATH,
    *,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    max_age_s: float = DEFAULT_MAX_AGE_S,
) -> dict:
    """Sample current executable sidecar freshness even when no trade fires."""
    cache = load_executable_cache(cache_path)
    metrics = load_executable_metrics(metrics_path)
    for market_id, market in (cache.get("markets") or {}).items():
        if not isinstance(market, dict):
            continue
        for side in ("yes", "no"):
            entry = market.get(side)
            if not isinstance(entry, dict):
                book = {
                    "market_id": market_id,
                    "side": side,
                    "status": "missing",
                    "reason": "missing_side",
                    "age_ms": None,
                }
            else:
                token_id = entry.get("token_id")
                book = PolymarketOrderbookService(
                    executable_cache_path=cache_path,
                    metrics_path=metrics_path,
                    max_age_s=max_age_s,
                )._side_book(market, market_id, side, token_id)
            metrics = _record_book(metrics, book)
    _write_metrics(metrics_path, metrics)
    return metrics


def record_executable_read(book: dict, metrics_path: Path = DEFAULT_METRICS_PATH) -> dict:
    metrics = load_executable_metrics(metrics_path)
    metrics = _record_book(metrics, book)
    _write_metrics(metrics_path, metrics)
    return metrics


def _record_book(metrics: dict, book: dict) -> dict:
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

    return {
        "schema_version": 1,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "_age_samples_ms": samples,
        "btc5m_executable_orderbook_age_ms": _percentiles(samples),
        "btc5m_executable_book_reads": reads,
    }


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


def _age_ms(updated_at: str | None) -> float | None:
    if not updated_at:
        return None
    try:
        dt = datetime.fromisoformat(updated_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() * 1000)
    except (TypeError, ValueError):
        return None


def _valid_mid(mid) -> float | None:
    try:
        value = float(mid)
    except (TypeError, ValueError):
        return None
    if 0.01 <= value <= 0.99:
        return value
    return None


def _write_metrics(path: Path, data: dict) -> None:
    _write_json_atomic(Path(path), data)


def _write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.rename(path)
