"""Tests for pluggable executable orderbook evidence providers."""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _write_cache(path, markets, *, status="connected"):
    path.write_text(json.dumps({
        "version": 1,
        "provider": "custom",
        "status": status,
        "markets": markets,
    }))
    return path


def _side(token_id, *, bid=0.51, ask=0.53, updated_at=None, status="fresh"):
    updated_at = updated_at or datetime.now(timezone.utc).isoformat()
    return {
        "token_id": token_id,
        "best_bid": bid,
        "best_ask": ask,
        "mid": round((bid + ask) / 2, 4),
        "spread": round(ask - bid, 4),
        "updated_at": updated_at,
        "source_ts": updated_at,
        "status": status,
        # snapshot_verified=True: entries represent properly initialized tokens
        # (WS book or REST seed applied).  Required by _side_book since the
        # freshness-contract fix (root cause 2 / snapshot_verified gate).
        "snapshot_verified": True,
    }


def test_vendor_fresh_evidence_wins_over_internal(monkeypatch, tmp_path):
    from orderbook_evidence import read_orderbook_evidence

    vendor = _write_cache(tmp_path / "vendor.json", {
        "m1": {"yes": _side("yes", bid=0.61, ask=0.63)}
    })
    internal = _write_cache(tmp_path / "internal.json", {
        "m1": {"yes": _side("yes", bid=0.51, ask=0.53)}
    })
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "vendor_primary")
    monkeypatch.setenv("MARKET_DATA_VENDOR_CACHE", str(vendor))

    evidence = read_orderbook_evidence("m1", "yes", "no", cache_path=internal)

    assert evidence["yes"]["status"] == "fresh"
    assert evidence["yes"]["source"] == "vendor:custom"
    assert evidence["yes"]["best_bid"] == 0.61
    assert evidence["yes"]["provider_chosen_source"] == "vendor"
    assert evidence["_provider"]["chosen_source"] == "vendor"


def test_vendor_stale_falls_back_to_internal(monkeypatch, tmp_path):
    from orderbook_evidence import read_orderbook_evidence

    old = (datetime.now(timezone.utc) - timedelta(seconds=45)).isoformat()
    vendor = _write_cache(tmp_path / "vendor.json", {
        "m1": {"yes": _side("yes", updated_at=old)}
    })
    internal = _write_cache(tmp_path / "internal.json", {
        "m1": {"yes": _side("yes", bid=0.54, ask=0.56)}
    })
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "vendor_primary")
    monkeypatch.setenv("MARKET_DATA_VENDOR_CACHE", str(vendor))

    evidence = read_orderbook_evidence("m1", "yes", "no", cache_path=internal, max_age_s=2)

    assert evidence["yes"]["status"] == "fresh"
    assert evidence["yes"]["source"] == "executable_sidecar"
    assert evidence["yes"]["best_bid"] == 0.54
    assert evidence["yes"]["provider_fallback_used"] is True
    assert evidence["_provider"]["fallback_used"] is True


def test_both_providers_unavailable_fail_closed(monkeypatch, tmp_path):
    from orderbook_evidence import read_orderbook_evidence

    vendor = _write_cache(tmp_path / "vendor.json", {"m1": {}})
    internal = _write_cache(tmp_path / "internal.json", {"m1": {}})
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "vendor_primary")
    monkeypatch.setenv("MARKET_DATA_VENDOR_CACHE", str(vendor))

    evidence = read_orderbook_evidence("m1", "yes", "no", cache_path=internal)

    assert evidence["yes"]["status"] == "missing"
    assert evidence["yes"]["reason"] == "missing_cache_entry"
    assert evidence["yes"]["provider_chosen_source"] == "none"
    assert evidence["_provider"]["chosen_source"] == "none"


def test_vendor_side_token_lookup_cannot_cross_contaminate(monkeypatch, tmp_path):
    from orderbook_evidence import read_orderbook_evidence

    vendor = _write_cache(tmp_path / "vendor.json", {
        "m1": {
            "yes": _side("no", bid=0.62, ask=0.64),
            "no": _side("no", bid=0.36, ask=0.38),
        }
    })
    internal = _write_cache(tmp_path / "internal.json", {"m1": {}})
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "vendor_primary")
    monkeypatch.setenv("MARKET_DATA_VENDOR_CACHE", str(vendor))

    evidence = read_orderbook_evidence("m1", "yes", "no", cache_path=internal)

    assert evidence["yes"]["status"] == "missing"
    assert evidence["yes"]["reason"] == "token_mismatch"
    assert evidence["no"]["status"] == "fresh"
    assert evidence["no"]["token_id"] == "no"


def test_invalid_vendor_bbo_is_rejected(monkeypatch, tmp_path):
    from orderbook_evidence import read_orderbook_evidence

    vendor = _write_cache(tmp_path / "vendor.json", {
        "m1": {"yes": _side("yes", bid=0.64, ask=0.62)}
    })
    internal = _write_cache(tmp_path / "internal.json", {"m1": {}})
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "vendor_primary")
    monkeypatch.setenv("MARKET_DATA_VENDOR_CACHE", str(vendor))

    evidence = read_orderbook_evidence("m1", "yes", "no", cache_path=internal)

    assert evidence["yes"]["status"] == "stale"
    assert evidence["yes"]["reason"] == "invalid_bbo"
    assert evidence["yes"]["provider_chosen_source"] == "none"


def test_dual_shadow_audits_vendor_but_chooses_internal(monkeypatch, tmp_path):
    from orderbook_evidence import read_orderbook_evidence

    vendor = _write_cache(tmp_path / "vendor.json", {
        "m1": {"yes": _side("yes", bid=0.62, ask=0.64)}
    })
    internal = _write_cache(tmp_path / "internal.json", {
        "m1": {"yes": _side("yes", bid=0.52, ask=0.54)}
    })
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "dual_shadow")
    monkeypatch.setenv("MARKET_DATA_VENDOR_CACHE", str(vendor))

    evidence = read_orderbook_evidence("m1", "yes", "no", cache_path=internal)

    assert evidence["yes"]["source"] == "executable_sidecar"
    assert evidence["yes"]["provider_chosen_source"] == "internal"
    assert evidence["_provider"]["mode"] == "dual_shadow"
    assert evidence["_provider"]["disagreement_count"] == 1
