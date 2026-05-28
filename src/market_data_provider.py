"""Pluggable market-data providers for executable Polymarket evidence."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from orderbook_cache import DEFAULT_MAX_AGE_S
from polymarket_orderbook_service import (
    DEFAULT_EXECUTABLE_CACHE_PATH,
    PolymarketOrderbookService,
)


DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_VENDOR_CACHE_PATH = DATA_DIR / "vendor_orderbook.json"
DEFAULT_DISAGREEMENT_TOLERANCE = 0.03


@dataclass(frozen=True)
class ProviderConfig:
    mode: str
    vendor: str
    vendor_cache_path: Path
    vendor_rest_url: str | None
    vendor_ws_url: str | None
    vendor_api_key_present: bool
    disagreement_tolerance: float

    @classmethod
    def from_env(cls) -> "ProviderConfig":
        return cls(
            mode=(os.getenv("MARKET_DATA_PROVIDER") or "vendor_primary").strip().lower(),
            vendor=(os.getenv("MARKET_DATA_VENDOR") or "custom").strip().lower(),
            vendor_cache_path=Path(
                os.getenv("MARKET_DATA_VENDOR_CACHE") or DEFAULT_VENDOR_CACHE_PATH
            ),
            vendor_rest_url=os.getenv("MARKET_DATA_VENDOR_REST_URL"),
            vendor_ws_url=os.getenv("MARKET_DATA_VENDOR_WS_URL"),
            vendor_api_key_present=bool(os.getenv("MARKET_DATA_VENDOR_API_KEY")),
            disagreement_tolerance=_float_env(
                "MARKET_DATA_BBO_DISAGREE_TOLERANCE",
                DEFAULT_DISAGREEMENT_TOLERANCE,
            ),
        )


def read_provider_orderbook_evidence(
    market_id: str,
    yes_token: str | None,
    no_token: str | None,
    *,
    cache_path: Path = DEFAULT_EXECUTABLE_CACHE_PATH,
    max_age_s: float = DEFAULT_MAX_AGE_S,
    config: ProviderConfig | None = None,
) -> dict:
    """Return chosen executable evidence plus vendor/internal audit details."""
    cfg = config or ProviderConfig.from_env()
    if cfg.mode not in {"polymarket", "vendor_primary", "dual_shadow"}:
        cfg = ProviderConfig(
            mode="polymarket",
            vendor=cfg.vendor,
            vendor_cache_path=cfg.vendor_cache_path,
            vendor_rest_url=cfg.vendor_rest_url,
            vendor_ws_url=cfg.vendor_ws_url,
            vendor_api_key_present=cfg.vendor_api_key_present,
            disagreement_tolerance=cfg.disagreement_tolerance,
        )

    internal = PolymarketOrderbookService(
        executable_cache_path=cache_path,
        max_age_s=max_age_s,
    ).read_market(market_id, yes_token, no_token)
    vendor_cache = _load_vendor_cache(cfg.vendor_cache_path)
    vendor = _read_vendor_market(
        vendor_cache,
        market_id,
        yes_token,
        no_token,
        max_age_s=max_age_s,
        vendor=cfg.vendor,
    )

    chosen = {"market_id": market_id}
    disagreements = {}
    chosen_sources = set()
    fallback_used = False
    for side in ("yes", "no"):
        vendor_side = vendor[side]
        internal_side = internal[side]
        disagreement = _books_disagree(
            vendor_side,
            internal_side,
            cfg.disagreement_tolerance,
        )
        disagreements[side] = disagreement

        chosen_side, chosen_source, side_fallback = _choose_side(
            cfg.mode,
            vendor_side,
            internal_side,
        )
        fallback_used = fallback_used or side_fallback
        chosen_sources.add(chosen_source)
        chosen[side] = _with_provider_metadata(
            dict(chosen_side),
            mode=cfg.mode,
            vendor=cfg.vendor,
            chosen_source=chosen_source,
            vendor_status=vendor_side.get("status") or "missing",
            internal_status=internal_side.get("status") or "missing",
            fallback_used=side_fallback,
            disagreement=disagreement,
            vendor_feed_connected=_vendor_feed_connected(vendor_cache),
            disagreement_tolerance=cfg.disagreement_tolerance,
        )

    chosen_source = _market_chosen_source(chosen_sources)
    chosen["_provider"] = {
        "mode": cfg.mode,
        "vendor": cfg.vendor,
        "chosen_source": chosen_source,
        "fallback_used": fallback_used,
        "vendor_feed_connected": _vendor_feed_connected(vendor_cache),
        "vendor_rest_configured": bool(cfg.vendor_rest_url),
        "vendor_ws_configured": bool(cfg.vendor_ws_url),
        "vendor_api_key_present": cfg.vendor_api_key_present,
        "vendor_status": _market_status(vendor),
        "internal_status": _market_status(internal),
        "disagreement_count": sum(1 for v in disagreements.values() if v),
        "disagreement_by_side": disagreements,
        "disagreement_tolerance": cfg.disagreement_tolerance,
        "vendor": {"yes": vendor["yes"], "no": vendor["no"]},
        "internal": {"yes": internal["yes"], "no": internal["no"]},
    }
    return chosen


def _choose_side(mode: str, vendor: dict, internal: dict) -> tuple[dict, str, bool]:
    vendor_fresh = vendor.get("status") == "fresh"
    internal_fresh = internal.get("status") == "fresh"
    if mode == "polymarket":
        return internal, "internal" if internal_fresh else "none", False
    if mode == "dual_shadow":
        return internal, "internal" if internal_fresh else "none", False
    if vendor_fresh:
        return vendor, "vendor", False
    if internal_fresh:
        return internal, "internal", True
    if vendor.get("reason") == "token_mismatch":
        return vendor, "none", False
    if vendor.get("status") not in {None, "missing"}:
        return vendor, "none", False
    return internal, "none", False


def _with_provider_metadata(book: dict, **metadata) -> dict:
    book["provider_mode"] = metadata["mode"]
    book["provider_vendor"] = metadata["vendor"]
    book["provider_chosen_source"] = metadata["chosen_source"]
    book["provider_vendor_status"] = metadata["vendor_status"]
    book["provider_internal_status"] = metadata["internal_status"]
    book["provider_fallback_used"] = metadata["fallback_used"]
    book["provider_disagreement"] = metadata["disagreement"]
    book["provider_vendor_feed_connected"] = metadata["vendor_feed_connected"]
    book["provider_disagreement_tolerance"] = metadata["disagreement_tolerance"]
    return book


def _load_vendor_cache(path: Path) -> dict:
    try:
        if not Path(path).exists():
            return {"version": 1, "status": "disconnected", "markets": {}}
        data = json.loads(Path(path).read_text())
        if not isinstance(data, dict):
            return {"version": 1, "status": "disconnected", "markets": {}}
        data.setdefault("markets", {})
        return data
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "status": "disconnected", "markets": {}}


def _read_vendor_market(
    cache: dict,
    market_id: str,
    yes_token: str | None,
    no_token: str | None,
    *,
    max_age_s: float,
    vendor: str,
) -> dict:
    market = (cache.get("markets") or {}).get(market_id) or {}
    tokens = cache.get("tokens") or {}
    return {
        "market_id": market_id,
        "yes": _vendor_side_book(
            market.get("yes") or tokens.get(yes_token),
            market_id,
            "yes",
            yes_token,
            max_age_s=max_age_s,
            vendor=vendor,
        ),
        "no": _vendor_side_book(
            market.get("no") or tokens.get(no_token),
            market_id,
            "no",
            no_token,
            max_age_s=max_age_s,
            vendor=vendor,
        ),
    }


def _vendor_side_book(
    entry: dict | None,
    market_id: str,
    side: str,
    token_id: str | None,
    *,
    max_age_s: float,
    vendor: str,
) -> dict:
    base = {
        "market_id": market_id,
        "side": side,
        "token_id": token_id,
        "status": "missing",
        "source": f"vendor:{vendor}",
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
    if not isinstance(entry, dict):
        return base
    if entry.get("token_id") and entry.get("token_id") != token_id:
        base["reason"] = "token_mismatch"
        return base

    bid = _num(entry.get("best_bid"))
    ask = _num(entry.get("best_ask"))
    mid = _num(entry.get("mid"))
    if mid is None and bid is not None and ask is not None:
        mid = round((bid + ask) / 2, 6)
    spread = _num(entry.get("spread"))
    if spread is None and bid is not None and ask is not None:
        spread = round(ask - bid, 6)

    updated_at = entry.get("updated_at") or entry.get("source_ts")
    age = _age_ms(updated_at)
    base.update({
        "age_ms": round(age) if age is not None else None,
        "mid": mid,
        "best_bid": bid,
        "best_ask": ask,
        "spread": spread,
        "source_ts": entry.get("source_ts") or updated_at,
    })
    if not _valid_bbo(bid, ask, mid):
        base.update({"status": "stale", "reason": "invalid_bbo"})
        return base
    if age is None:
        base.update({"status": "stale", "reason": "missing_updated_at"})
        return base
    if age > max_age_s * 1000:
        base.update({"status": "stale", "reason": "stale_updated_at"})
        return base
    if entry.get("status") in {"missing", "stale", "partial"}:
        base.update({
            "status": entry.get("status"),
            "reason": entry.get("reason") or entry.get("stale_reason") or entry.get("status"),
        })
        return base
    base.update({"status": "fresh", "reason": None})
    return base


def _valid_bbo(bid, ask, mid) -> bool:
    if bid is None or ask is None or mid is None:
        return False
    if not (0 < bid < 1 and 0 < ask < 1 and 0 < mid < 1):
        return False
    return bid <= mid <= ask and bid < ask


def _books_disagree(vendor: dict, internal: dict, tolerance: float) -> bool:
    if vendor.get("status") != "fresh" or internal.get("status") != "fresh":
        return False
    for key in ("best_bid", "best_ask", "mid"):
        left = _num(vendor.get(key))
        right = _num(internal.get(key))
        if left is None or right is None:
            continue
        if abs(left - right) > tolerance:
            return True
    return False


def _market_status(evidence: dict) -> str:
    statuses = {
        (evidence.get("yes") or {}).get("status") or "missing",
        (evidence.get("no") or {}).get("status") or "missing",
    }
    if "fresh" in statuses:
        return "fresh"
    if "partial" in statuses:
        return "partial"
    if "stale" in statuses:
        return "stale"
    return "missing"


def _market_chosen_source(sources: set[str]) -> str:
    live = {s for s in sources if s != "none"}
    if not live:
        return "none"
    if len(live) == 1:
        return next(iter(live))
    return "mixed"


def _vendor_feed_connected(cache: dict) -> bool:
    return (cache.get("status") or "disconnected") == "connected"


def _age_ms(value: str | None) -> float | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() * 1000)
    except (TypeError, ValueError):
        return None


def _num(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default
