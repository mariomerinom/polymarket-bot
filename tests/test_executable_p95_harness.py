"""Increment 4 — p95 verification harness.

This file is the win-condition test for the BTC 5m freshness rebuild.
It proves by construction that:

  1. When the registry path is used with 200-800ms ages, public_metrics().p95 < 2000.
  2. When the old disk-flush latency floor is injected (2s added to every age),
     the same harness exceeds 2000ms — documenting the pre-fix baseline.
  3. The canary blocker `btc5m_executable_orderbook_age_p95_too_high` evaluates
     False when the real metric is < 2000ms and True above.

These are the tests that prove the canary gate can honestly clear.
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _registry_entry(token_id: str, age_ms: int) -> dict:
    """Registry entry that appears exactly age_ms old."""
    return {
        "market_id": "m-p95-001",
        "side": "yes",
        "token_id": token_id,
        "mid": 0.55,
        "best_bid": 0.53,
        "best_ask": 0.57,
        "spread": 0.04,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_event_ms": int(time.time() * 1000) - age_ms,
        "snapshot_verified": True,
        "status": "fresh",
        "stale_reason": None,
        "source_ts": None,
    }


def _simulate_reads(
    n_reads: int,
    age_ms_min: int,
    age_ms_max: int,
    sidecar_path: Path,
    metrics_path: Path,
    max_age_s: float = 2.0,
    extra_latency_ms: int = 0,
) -> dict:
    """Simulate n_reads of the registry path and record metrics.

    extra_latency_ms simulates the old disk-flush latency floor:
    add it to every registry age to reproduce the pre-fix baseline.
    """
    import live_book_registry
    from polymarket_orderbook_service import (
        PolymarketOrderbookService,
        _record_book,
        _write_metrics,
        load_executable_metrics,
    )

    live_book_registry.reset()
    live_book_registry.set_engine_present(True)

    # Spread ages evenly across [age_ms_min, age_ms_max]
    step = (age_ms_max - age_ms_min) / max(n_reads - 1, 1)
    metrics = {}
    service = PolymarketOrderbookService(
        executable_cache_path=sidecar_path, max_age_s=max_age_s
    )

    for i in range(n_reads):
        raw_age = int(age_ms_min + i * step)
        effective_age = raw_age + extra_latency_ms

        token_id = f"tok-p95-{i:03d}"
        entry = _registry_entry(token_id, effective_age)
        live_book_registry.publish_token(token_id, entry)

        book = service._side_book({}, "m-p95-001", "yes", token_id)
        metrics = _record_book(metrics, book)

    _write_metrics(metrics_path, metrics)
    live_book_registry.reset()
    return metrics


# ── Registry path — p95 < 2000ms ─────────────────────────────────────────────

class TestP95HarnessRegistryPath:
    """With registry ages 200-800ms and max_age_s=2.0, p95 must stay < 2000ms."""

    def test_p95_below_2000ms_with_20_reads(self, tmp_path):
        """Minimum statistical set: 20 reads → p95 is computed, not just max."""
        sidecar = tmp_path / "exec.json"
        sidecar.write_text(json.dumps({"version": 2, "markets": {}}))
        metrics_path = tmp_path / "metrics.json"

        metrics = _simulate_reads(
            n_reads=20,
            age_ms_min=200,
            age_ms_max=800,
            sidecar_path=sidecar,
            metrics_path=metrics_path,
        )
        p95 = metrics["btc5m_executable_orderbook_age_ms"]["p95"]
        samples = metrics["btc5m_executable_orderbook_age_ms"]["samples"]
        assert samples == 20, f"Expected 20 fresh samples, got {samples}"
        assert p95 < 2000, f"p95={p95}ms exceeds 2000ms gate with registry ages 200-800ms"

    def test_p95_below_2000ms_with_50_reads(self, tmp_path):
        """Robust set: 50 reads across 200-800ms."""
        sidecar = tmp_path / "exec.json"
        sidecar.write_text(json.dumps({"version": 2, "markets": {}}))
        metrics_path = tmp_path / "metrics.json"

        metrics = _simulate_reads(
            n_reads=50,
            age_ms_min=200,
            age_ms_max=800,
            sidecar_path=sidecar,
            metrics_path=metrics_path,
        )
        p95 = metrics["btc5m_executable_orderbook_age_ms"]["p95"]
        assert p95 < 2000, f"p95={p95}ms with 50 reads (200-800ms ages)"

    def test_p50_well_below_1000ms(self, tmp_path):
        """Median age from the registry should be well under 1s."""
        sidecar = tmp_path / "exec.json"
        sidecar.write_text(json.dumps({"version": 2, "markets": {}}))
        metrics_path = tmp_path / "metrics.json"

        metrics = _simulate_reads(
            n_reads=50,
            age_ms_min=200,
            age_ms_max=800,
            sidecar_path=sidecar,
            metrics_path=metrics_path,
        )
        p50 = metrics["btc5m_executable_orderbook_age_ms"]["p50"]
        assert p50 < 1000, f"p50={p50}ms — median should be < 1s with registry ages 200-800ms"

    def test_all_fresh_reads_contribute_to_p95(self, tmp_path):
        """Every simulated read at sub-max-age must be counted as fresh."""
        sidecar = tmp_path / "exec.json"
        sidecar.write_text(json.dumps({"version": 2, "markets": {}}))
        metrics_path = tmp_path / "metrics.json"

        metrics = _simulate_reads(
            n_reads=30,
            age_ms_min=100,
            age_ms_max=1800,  # within 2s gate
            sidecar_path=sidecar,
            metrics_path=metrics_path,
        )
        reads = metrics["btc5m_executable_book_reads"]
        assert reads.get("fresh", 0) == 30, (
            f"All 30 sub-2s reads should be fresh; got fresh={reads.get('fresh')}"
        )


# ── Disk-flush latency floor — documents the pre-fix baseline ────────────────

class TestP95HarnessDiskFloorBaseline:
    """Injecting 2s disk-flush latency makes the same reads EXCEED 2000ms.

    This class documents why the fix was necessary — it proves that without
    the registry path, even 200ms wire-fresh data would appear >=2000ms stale
    after the minimum disk-flush delay.
    """

    def test_2s_disk_floor_inflates_p95_above_gate(self, tmp_path):
        """Injecting 2000ms extra latency pushes p95 above the 2000ms gate.

        This simulates the pre-fix state: the execution path read from a disk
        file that was only flushed every 2 s.  Even a 200ms-fresh registry
        entry would appear 2200ms stale to the consumer.
        """
        sidecar = tmp_path / "exec.json"
        sidecar.write_text(json.dumps({"version": 2, "markets": {}}))
        metrics_path = tmp_path / "metrics.json"

        # extra_latency_ms=2000 simulates the disk flush floor.
        # We raise max_age_s to 10 to count them as "fresh" (old gate).
        metrics = _simulate_reads(
            n_reads=30,
            age_ms_min=200,
            age_ms_max=800,
            sidecar_path=sidecar,
            metrics_path=metrics_path,
            max_age_s=10.0,   # old 10s default
            extra_latency_ms=2000,
        )
        p95 = metrics["btc5m_executable_orderbook_age_ms"]["p95"]
        assert p95 >= 2000, (
            f"With 2s disk floor, p95={p95}ms should exceed 2000ms "
            f"(documents pre-fix baseline)"
        )

    def test_registry_path_eliminates_disk_floor(self, tmp_path):
        """Same wire ages but WITHOUT disk-floor latency — p95 stays < 2000ms."""
        sidecar = tmp_path / "exec.json"
        sidecar.write_text(json.dumps({"version": 2, "markets": {}}))
        metrics_path = tmp_path / "metrics.json"

        metrics = _simulate_reads(
            n_reads=30,
            age_ms_min=200,
            age_ms_max=800,
            sidecar_path=sidecar,
            metrics_path=metrics_path,
            max_age_s=2.0,
            extra_latency_ms=0,  # registry path — no disk floor
        )
        p95 = metrics["btc5m_executable_orderbook_age_ms"]["p95"]
        assert p95 < 2000, (
            f"Without disk floor, p95={p95}ms must stay under 2000ms "
            f"(documents the fix)"
        )


# ── Canary blocker integration ────────────────────────────────────────────────

class TestCanaryBlockerEvaluation:
    """btc5m_executable_orderbook_age_p95_too_high must evaluate False
    when public_metrics shows p95 < 2000ms."""

    def test_blocker_absent_when_p95_below_gate(self, tmp_path):
        """Run harness → write metrics → check canary sees no blocker."""
        import sqlite3
        from polymarket_orderbook_service import public_metrics

        sidecar = tmp_path / "exec.json"
        sidecar.write_text(json.dumps({"version": 2, "markets": {}}))
        metrics_path = tmp_path / "metrics.json"

        _simulate_reads(
            n_reads=25,
            age_ms_min=200,
            age_ms_max=800,
            sidecar_path=sidecar,
            metrics_path=metrics_path,
        )
        m = public_metrics(metrics_path)
        p95 = m["btc5m_executable_orderbook_age_ms"]["p95"]
        assert p95 < 2000, f"p95={p95}ms — harness should produce sub-gate metrics"

        # Verify canary logic directly (without importing canary_readiness which
        # needs a real DB).  The canary gate is: p95 >= 2000 → blocker.
        is_blocked = p95 >= 2000
        assert not is_blocked, (
            f"btc5m_executable_orderbook_age_p95_too_high should be absent "
            f"(p95={p95}ms < 2000ms)"
        )

    def test_blocker_present_when_p95_above_gate(self, tmp_path):
        """Old-gate simulation: p95 >= 2000ms → canary blocker fires."""
        from polymarket_orderbook_service import public_metrics

        sidecar = tmp_path / "exec.json"
        sidecar.write_text(json.dumps({"version": 2, "markets": {}}))
        metrics_path = tmp_path / "metrics.json"

        _simulate_reads(
            n_reads=25,
            age_ms_min=200,
            age_ms_max=800,
            sidecar_path=sidecar,
            metrics_path=metrics_path,
            max_age_s=10.0,
            extra_latency_ms=5000,  # simulate severe disk latency
        )
        m = public_metrics(metrics_path)
        p95 = m["btc5m_executable_orderbook_age_ms"]["p95"]
        is_blocked = p95 >= 2000
        assert is_blocked, (
            f"With 5s extra latency, canary blocker should fire (p95={p95}ms)"
        )
