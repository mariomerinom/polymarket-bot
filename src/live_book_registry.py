"""Process-global in-memory orderbook registry for the btc_5m execution path.

Architecture
------------
This singleton eliminates the disk round-trip that was the residual freshness
floor after Increment 1.  Before this change, the execution path read the book
from data/btc5m_executable_orderbook.json — a file the engine flushed at most
every ORDERBOOK_CACHE_FLUSH_INTERVAL_S=2 s.  The floor was therefore

    freshness = flush_interval + disk-write latency + disk-read latency ≥ 2 s

With the registry the engine publishes directly to an RLock-protected dict in
the same process.  The consumer (PolymarketOrderbookService._side_book) reads
from the registry when engine_is_live() is True; if False it falls back to the
existing disk sidecar so CLI / test / replay modes are unaffected.

API
---
publish_token(token_id, entry)  — engine calls on every handler that updates
                                   _orderbook_cache (publish a copy).
read_token(token_id)            — consumer calls; returns a copy or None.
engine_is_live()                — True iff engine registered in this process.
set_engine_present(bool)        — called from BotsyEngine.__init__ / reset().
reset()                         — test / standalone teardown; clears everything.
all_tokens()                    — snapshot copy of the whole registry.

Thread safety
-------------
RLock throughout; publish_token and read_token both copy the entry dict so
engine and consumer operate on independent objects.
"""

from __future__ import annotations

import copy
import threading

# ── Module-level singleton state ─────────────────────────────────────────────

_lock: threading.RLock = threading.RLock()
_registry: dict[str, dict] = {}
_engine_present: bool = False


# ── Public API ────────────────────────────────────────────────────────────────

def publish_token(token_id: str, entry: dict) -> None:
    """Publish a token book entry to the registry.

    Stores a shallow copy of *entry* so subsequent mutations by the engine
    do not silently corrupt the published view.
    """
    if not token_id:
        return
    with _lock:
        _registry[token_id] = dict(entry)


def read_token(token_id: str) -> dict | None:
    """Return a copy of the stored entry for *token_id*, or None if absent."""
    with _lock:
        entry = _registry.get(token_id)
        if entry is None:
            return None
        return dict(entry)


def drop_token(token_id: str) -> None:
    """Remove *token_id* from the registry (called on prune/resubscribe)."""
    with _lock:
        _registry.pop(token_id, None)


def engine_is_live() -> bool:
    """Return True iff a BotsyEngine instance has registered in this process."""
    with _lock:
        return _engine_present


def set_engine_present(present: bool) -> None:
    """Signal that an engine is (or is no longer) running in this process."""
    global _engine_present
    with _lock:
        _engine_present = present


def all_tokens() -> dict[str, dict]:
    """Return a shallow copy of the entire registry (for diagnostics / tests)."""
    with _lock:
        return {tid: dict(entry) for tid, entry in _registry.items()}


def reset() -> None:
    """Clear all state.  Intended for test isolation and standalone teardown."""
    global _engine_present
    with _lock:
        _registry.clear()
        _engine_present = False
