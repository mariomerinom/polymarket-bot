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


def build_executable_cache(
    token_cache: dict,
    token_context: dict,
    *,
    active_token_ids: set | None = None,
) -> dict:
    """Build the BTC 5m executable sidecar from canonical token state.

    This is intentionally derived, not mirrored. The engine owns one mutable
    orderbook cache keyed by token id; the executable sidecar is rebuilt from
    that cache plus token context at flush time.
    """
    active = set(active_token_ids) if active_token_ids is not None else None
    markets: dict = {}
    for token_id, ctx in sorted((token_context or {}).items()):
        if active is not None and token_id not in active:
            continue
        if not isinstance(ctx, dict) or ctx.get("pipeline") != "btc_5m":
            continue
        market_id = ctx.get("market_id")
        side = str(ctx.get("side") or "").lower()
        if not market_id or side not in {"yes", "no"}:
            continue
        token_entry = (token_cache or {}).get(token_id)
        side_entry = _side_entry_from_token(token_id, market_id, side, token_entry)
        market = markets.setdefault(market_id, {})
        current = market.get(side)
        if current is None or _status_rank(side_entry) > _status_rank(current):
            market[side] = side_entry

    return {
        "version": 2,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "markets": markets,
    }


def write_executable_cache(cache: dict, path: Path = DEFAULT_EXECUTABLE_CACHE_PATH) -> None:
    _write_json_atomic(Path(path), cache)


def _side_entry_from_token(
    token_id: str,
    market_id: str,
    side: str,
    entry: dict | None,
) -> dict:
    base = {
        "market_id": market_id,
        "side": side,
        "token_id": token_id,
        "status": "missing",
        "source": "polymarket_orderbook_v2",
        "reason": "missing_cache_entry",
        "stale_reason": None,
        "mid": None,
        "best_bid": None,
        "best_ask": None,
        "spread": None,
        "updated_at": None,
        "source_ts": None,
    }
    if not isinstance(entry, dict):
        return base

    status = entry.get("status") or "missing"
    reason = entry.get("stale_reason") or entry.get("reason")
    base.update({
        "status": status,
        "source": entry.get("source") or "polymarket_orderbook_v2",
        "reason": reason,
        "stale_reason": entry.get("stale_reason"),
        "mid": entry.get("mid"),
        "best_bid": entry.get("best_bid"),
        "best_ask": entry.get("best_ask"),
        "spread": entry.get("spread"),
        "updated_at": entry.get("updated_at"),
        "source_ts": entry.get("source_ts"),
        # Freshness-contract fields — carried through so _side_book can gate on them.
        "snapshot_verified": entry.get("snapshot_verified", False),
        "last_event_ms": entry.get("last_event_ms"),
    })
    if status == "missing" and not base["reason"]:
        base["reason"] = "missing_cache_entry"
    return base


def _status_rank(entry: dict) -> int:
    return {
        "missing": 0,
        "stale": 1,
        "partial": 2,
        "fresh": 3,
    }.get(entry.get("status"), 0)


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

        # Registry-first: when the engine is live in this process, read
        # directly from the in-process live_book_registry instead of the disk
        # sidecar.  This removes the 2 s disk-flush latency floor (root cause 1).
        # On registry miss or engine-not-live, fall through to the sidecar path.
        try:
            from live_book_registry import engine_is_live, read_token as _reg_read
            if engine_is_live():
                reg_entry = _reg_read(token_id)
                if reg_entry is not None:
                    return self._side_book_from_registry(
                        reg_entry, market_id, side, token_id
                    )
        except ImportError:
            pass  # registry module not available in standalone / replay contexts

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
        # Freshness contract: a "fresh" book must have a verified snapshot baseline.
        # Entries built from deltas only (no WS `book` or REST seed) are rejected
        # here so stale delta-only books cannot pollute the p95 metric.
        if not entry.get("snapshot_verified"):
            base.update({
                "status": "stale",
                "source": entry.get("source") or "executable_sidecar",
                "reason": "no_snapshot_baseline",
            })
            return base
        base.update({
            "status": "fresh",
            "source": entry.get("source") or "executable_sidecar",
            "reason": None,
        })
        return base

    def _side_book_from_registry(
        self,
        entry: dict,
        market_id: str,
        side: str,
        token_id: str,
    ) -> dict:
        """Build a side-book result from a live registry entry.

        Uses last_event_ms (local apply-time) instead of updated_at so the
        age reflects the true in-process freshness, not the disk-flush epoch.
        Applies the same gates as _side_book: max_age_s, snapshot_verified,
        valid BBO, and explicit stale status.
        """
        import time as _time
        now_ms = int(_time.time() * 1000)
        last_event_ms = entry.get("last_event_ms")
        age_ms = (now_ms - last_event_ms) if last_event_ms is not None else None

        base = {
            "market_id": market_id,
            "side": side,
            "token_id": token_id,
            "age_ms": round(age_ms) if age_ms is not None else None,
            "mid": entry.get("mid"),
            "best_bid": entry.get("best_bid"),
            "best_ask": entry.get("best_ask"),
            "spread": entry.get("spread"),
            "source_ts": entry.get("source_ts"),
            "reason": None,
        }

        if age_ms is None:
            base.update({"status": "stale", "source": "live_registry",
                         "reason": "no_last_event_ms"})
            return base
        if age_ms > self.max_age_s * 1000:
            base.update({"status": "stale", "source": "live_registry",
                         "reason": "stale_last_event_ms"})
            return base
        raw_status = entry.get("status")
        if raw_status == "stale":
            base.update({"status": "stale", "source": "live_registry",
                         "reason": entry.get("stale_reason") or "stale_entry"})
            return base
        mid = entry.get("mid")
        if mid is None or not (0 < mid < 1):
            base.update({"status": "partial", "source": "live_registry",
                         "reason": "invalid_mid"})
            return base
        if not entry.get("snapshot_verified"):
            base.update({"status": "stale", "source": "live_registry",
                         "reason": "no_snapshot_baseline"})
            return base
        base.update({"status": "fresh", "source": "live_registry"})
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

    provider = _record_provider_metrics(
        metrics.get("market_data_provider") or {},
        book,
    )

    return {
        "schema_version": 1,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "_age_samples_ms": samples,
        "btc5m_executable_orderbook_age_ms": _percentiles(samples),
        "btc5m_executable_book_reads": reads,
        "market_data_provider": provider,
    }


def _record_provider_metrics(provider: dict, book: dict) -> dict:
    mode = book.get("provider_mode")
    if not mode:
        return provider
    total = int(provider.get("total") or 0) + 1
    fallback_count = int(provider.get("fallback_count") or 0)
    if book.get("provider_fallback_used"):
        fallback_count += 1
    disagreement_count = int(provider.get("disagreement_count") or 0)
    if book.get("provider_disagreement"):
        disagreement_count += 1

    by_source = provider.get("by_source") or {}
    by_source = _increment_source_status(
        by_source,
        "vendor",
        book.get("provider_vendor_status") or "missing",
    )
    by_source = _increment_source_status(
        by_source,
        "internal",
        book.get("provider_internal_status") or "missing",
    )
    return {
        "mode": mode,
        "vendor": book.get("provider_vendor") or provider.get("vendor") or "custom",
        "chosen_source": book.get("provider_chosen_source") or "none",
        "vendor_feed_connected": bool(book.get("provider_vendor_feed_connected")),
        "disagreement_tolerance": (
            book.get("provider_disagreement_tolerance")
            if book.get("provider_disagreement_tolerance") is not None
            else provider.get("disagreement_tolerance")
        ),
        "total": total,
        "fallback_count": fallback_count,
        "fallback_rate": round(fallback_count / total, 4) if total else 0,
        "disagreement_count": disagreement_count,
        "by_source": by_source,
        "latest_market_id": book.get("market_id"),
        "latest_side": book.get("side"),
    }


def _increment_source_status(by_source: dict, source: str, status: str) -> dict:
    source_counts = by_source.get(source) or {}
    source_counts["total"] = int(source_counts.get("total") or 0) + 1
    source_counts[status] = int(source_counts.get(status) or 0) + 1
    by_source[source] = source_counts
    return by_source


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
        "market_data_provider": data.get("market_data_provider") or {},
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
        "market_data_provider": {},
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
