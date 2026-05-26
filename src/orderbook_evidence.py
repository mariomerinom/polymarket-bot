"""Executable orderbook evidence for Polymarket markets.

This module is intentionally small and boring: it gives execution code one
place to ask, "what do we know about the exact YES and NO token books?"
"""

from __future__ import annotations

from pathlib import Path

from orderbook_cache import DEFAULT_MAX_AGE_S
from polymarket_orderbook_service import (
    DEFAULT_EXECUTABLE_CACHE_PATH,
    PolymarketOrderbookService,
)


def read_orderbook_evidence(
    market_id: str,
    yes_token: str | None,
    no_token: str | None,
    *,
    cache_path: Path = DEFAULT_EXECUTABLE_CACHE_PATH,
    max_age_s: float = DEFAULT_MAX_AGE_S,
) -> dict:
    """Return per-side cache evidence for one Polymarket market."""
    return PolymarketOrderbookService(
        executable_cache_path=cache_path,
        max_age_s=max_age_s,
    ).read_market(market_id, yes_token, no_token)
