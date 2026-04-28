"""Tests for bybit_ws_capture retention purge.

Regression test for the 2026-04-24 incident: 16 days of unbounded capture
filled a 24G disk, crashlooped the engine for 5 days. Retention is now
self-managed at hourly rotation; these tests pin that behavior.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestPurgeOldCaptureFiles:
    def test_deletes_files_older_than_retention(self, tmp_path):
        from bybit_ws_capture import _purge_old_capture_files

        topic_dir = tmp_path / "orderbook"
        topic_dir.mkdir()

        # Older than 7 days (15 days back)
        old1 = topic_dir / "2026-04-08T20.jsonl.gz"
        old2 = topic_dir / "2026-04-09T01.jsonl.gz"
        old1.write_bytes(b"old")
        old2.write_bytes(b"old")
        old_mtime = time.time() - 15 * 86400
        os.utime(old1, (old_mtime, old_mtime))
        os.utime(old2, (old_mtime, old_mtime))

        # Within retention (2 days back)
        new1 = topic_dir / "2026-04-22T10.jsonl.gz"
        new1.write_bytes(b"new")
        os.utime(new1, (time.time() - 2 * 86400,) * 2)

        purged = _purge_old_capture_files(topic_dir, retention_days=7)

        assert purged == 2
        assert not old1.exists()
        assert not old2.exists()
        assert new1.exists()

    def test_keeps_in_flight_jsonl_within_retention(self, tmp_path):
        """The currently-being-written .jsonl file (no .gz suffix) should
        be preserved as long as it's within retention."""
        from bybit_ws_capture import _purge_old_capture_files

        topic_dir = tmp_path / "tickers"
        topic_dir.mkdir()
        active = topic_dir / "2026-04-24T00.jsonl"
        active.write_bytes(b"active")
        os.utime(active, (time.time(),) * 2)

        purged = _purge_old_capture_files(topic_dir, retention_days=7)
        assert purged == 0
        assert active.exists()

    def test_idempotent_on_repeat_call(self, tmp_path):
        from bybit_ws_capture import _purge_old_capture_files

        topic_dir = tmp_path / "publicTrade"
        topic_dir.mkdir()
        old = topic_dir / "2026-04-08T20.jsonl.gz"
        old.write_bytes(b"old")
        os.utime(old, (time.time() - 30 * 86400,) * 2)

        first = _purge_old_capture_files(topic_dir, retention_days=7)
        second = _purge_old_capture_files(topic_dir, retention_days=7)
        assert first == 1
        assert second == 0

    def test_missing_dir_returns_zero(self, tmp_path):
        from bybit_ws_capture import _purge_old_capture_files

        nonexistent = tmp_path / "no_such_topic"
        purged = _purge_old_capture_files(nonexistent, retention_days=7)
        assert purged == 0

    def test_subdirectory_is_skipped(self, tmp_path):
        """Should never recurse into subdirs — only loose files."""
        from bybit_ws_capture import _purge_old_capture_files

        topic_dir = tmp_path / "orderbook"
        topic_dir.mkdir()
        sub = topic_dir / "subdir"
        sub.mkdir()
        nested = sub / "nested.jsonl.gz"
        nested.write_bytes(b"x")
        os.utime(nested, (time.time() - 30 * 86400,) * 2)

        purged = _purge_old_capture_files(topic_dir, retention_days=7)
        assert purged == 0
        assert nested.exists()

    def test_default_retention_constant(self):
        """RETENTION_DAYS must be defined as the module default."""
        import bybit_ws_capture

        assert hasattr(bybit_ws_capture, "RETENTION_DAYS")
        assert bybit_ws_capture.RETENTION_DAYS >= 1
        assert bybit_ws_capture.RETENTION_DAYS <= 30


class TestRetentionWiredIntoRotation:
    """The purge MUST run during _open_for_hour, otherwise the bug returns."""

    def test_open_for_hour_calls_purge(self, tmp_path, monkeypatch):
        from bybit_ws_capture import RotatingJSONLWriter
        import bybit_ws_capture

        called = {"count": 0, "dirs": []}

        def _spy(topic_dir, retention_days=7):
            called["count"] += 1
            called["dirs"].append(topic_dir)
            return 0

        monkeypatch.setattr(bybit_ws_capture, "_purge_old_capture_files", _spy)

        topic_dir = tmp_path / "orderbook"
        topic_dir.mkdir()
        writer = RotatingJSONLWriter(topic_dir)
        writer.write({"ts": 1, "x": "first"})

        # First write triggers _open_for_hour, which must call the purge
        assert called["count"] >= 1
        assert called["dirs"][0] == topic_dir
        writer.close()
