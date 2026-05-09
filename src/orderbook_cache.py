"""
orderbook_cache.py — Typed reader for live_orderbook.json.

Replaces raw JSON reads scattered across trade.py with a typed dataclass.
Phase B Step 5 of TDD refactoring.

Cache format (v2):
    {"version": 2, "tokens": {token_id: {mid, best_bid, best_ask, spread, updated_at, ...}}}

Written by botsy_engine.py Polymarket WS feed.
Read by trade.py for CLOB price resolution.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DEFAULT_PATH = Path(__file__).parent.parent / "data" / "live_orderbook.json"
DEFAULT_MAX_AGE_S = 10


@dataclass
class TokenEntry:
    """A single token's orderbook snapshot."""
    mid: Optional[float] = None
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread: Optional[float] = None
    updated_at: Optional[str] = None

    def is_fresh(self, max_age_s: float = DEFAULT_MAX_AGE_S) -> bool:
        """Check if this entry is fresh enough to use."""
        age = self.age_ms()
        if age is None:
            return False
        return age <= max_age_s * 1000

    def age_ms(self) -> Optional[float]:
        """Return snapshot age in milliseconds, or None when unknown."""
        if not self.updated_at:
            return None
        try:
            cache_dt = datetime.fromisoformat(self.updated_at)
            if cache_dt.tzinfo is None:
                cache_dt = cache_dt.replace(tzinfo=timezone.utc)
            return max(
                0.0,
                (datetime.now(timezone.utc) - cache_dt).total_seconds() * 1000,
            )
        except (ValueError, TypeError):
            return None

    def valid_mid(self) -> Optional[float]:
        """Return mid if it's in valid range (0.01-0.99), else None."""
        if self.mid is not None and 0.01 <= self.mid <= 0.99:
            return self.mid
        return None


@dataclass
class OrderbookCache:
    """Typed representation of live_orderbook.json."""
    version: int = 1
    tokens: dict = field(default_factory=dict)  # token_id -> TokenEntry

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH, max_age_s: float = DEFAULT_MAX_AGE_S) -> "OrderbookCache":
        """Load cache from disk. Returns empty cache on any error."""
        try:
            if not path.exists():
                return cls()
            data = json.loads(path.read_text())
            version = data.get("version", 1)
            tokens = {}
            for token_id, entry_data in data.get("tokens", {}).items():
                tokens[token_id] = TokenEntry(
                    mid=entry_data.get("mid"),
                    best_bid=entry_data.get("best_bid"),
                    best_ask=entry_data.get("best_ask"),
                    spread=entry_data.get("spread"),
                    updated_at=entry_data.get("updated_at"),
                )
            return cls(version=version, tokens=tokens)
        except (json.JSONDecodeError, OSError, ValueError, TypeError):
            return cls()

    def get_fresh_mid(self, token_id: str, max_age_s: float = DEFAULT_MAX_AGE_S) -> Optional[float]:
        """Get mid price for a token if entry is fresh and valid. Else None."""
        if not token_id:
            return None
        entry = self.tokens.get(token_id)
        if not entry:
            return None
        if not entry.is_fresh(max_age_s):
            return None
        return entry.valid_mid()

    def get_fresh_entry(self, token_id: str, max_age_s: float = DEFAULT_MAX_AGE_S) -> Optional[TokenEntry]:
        """Get full TokenEntry if fresh, else None. Used for bid/ask/spread access."""
        if not token_id:
            return None
        entry = self.tokens.get(token_id)
        if not entry or not entry.is_fresh(max_age_s):
            return None
        return entry

    def entry_status(self, token_id: str, max_age_s: float = DEFAULT_MAX_AGE_S) -> dict:
        """Classify cache coverage for observability."""
        if not token_id:
            return {"status": "missing", "age_ms": None}
        entry = self.tokens.get(token_id)
        if not entry:
            return {"status": "missing", "age_ms": None}
        age = entry.age_ms()
        if age is None:
            return {"status": "stale", "age_ms": None}
        if age > max_age_s * 1000:
            return {"status": "stale", "age_ms": round(age)}
        return {"status": "fresh", "age_ms": round(age)}

    def save(self, path: Path = DEFAULT_PATH):
        """Write cache to disk atomically (temp file + rename)."""
        data = {
            "version": 2,
            "tokens": {
                token_id: {
                    "mid": entry.mid,
                    "best_bid": entry.best_bid,
                    "best_ask": entry.best_ask,
                    "spread": entry.spread,
                    "updated_at": entry.updated_at,
                }
                for token_id, entry in self.tokens.items()
            },
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.rename(path)
