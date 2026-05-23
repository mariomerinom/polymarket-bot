"""Executable orderbook evidence for Polymarket markets.

This module is intentionally small and boring: it gives execution code one
place to ask, "what do we know about the exact YES and NO token books?"
"""

from __future__ import annotations

from pathlib import Path

from orderbook_cache import DEFAULT_MAX_AGE_S, DEFAULT_PATH, OrderbookCache


def read_orderbook_evidence(
    market_id: str,
    yes_token: str | None,
    no_token: str | None,
    *,
    cache_path: Path = DEFAULT_PATH,
    max_age_s: float = DEFAULT_MAX_AGE_S,
) -> dict:
    """Return per-side cache evidence for one Polymarket market."""
    cache = OrderbookCache.load(cache_path, max_age_s)
    return {
        "market_id": market_id,
        "yes": _side_evidence(cache, yes_token, max_age_s),
        "no": _side_evidence(cache, no_token, max_age_s),
    }


def _side_evidence(cache: OrderbookCache, token_id: str | None, max_age_s: float) -> dict:
    status = cache.entry_status(token_id or "", max_age_s)
    entry = cache.tokens.get(token_id or "")
    return {
        "token_id": token_id,
        "status": status["status"],
        "age_ms": status["age_ms"],
        "mid": entry.mid if entry else None,
        "best_bid": entry.best_bid if entry else None,
        "best_ask": entry.best_ask if entry else None,
        "spread": entry.spread if entry else None,
        "source": "ws" if status["status"] == "fresh" else "missing",
    }
