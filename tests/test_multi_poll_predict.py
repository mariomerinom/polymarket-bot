"""Tests for multi_poll_predict — Phase A of in-cycle prediction-timing study.

Asserts the contract: schedule N polls at fixed offsets after a candle
close, log each to multi_poll_predictions, retention-prune in place.
External price/signal computation is mocked.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── init_table + schema ────────────────────────────────────────────


class TestInitTable:
    def test_creates_required_columns(self, tmp_path):
        import multi_poll_predict

        db = sqlite3.connect(str(tmp_path / "t.db"))
        multi_poll_predict.init_table(db)
        cols = {
            r[1]
            for r in db.execute(
                "PRAGMA table_info(multi_poll_predictions)"
            ).fetchall()
        }
        required = {
            "cycle",
            "cycle_close_at",
            "offset_seconds",
            "predicted_at",
            "market_id",
            "asset",
            "estimate",
            "regime",
            "spot_at_poll",
            "in_flight_return_pct",
            "poll_succeeded",
            "market_resolved",
            "market_outcome",
            "won",
        }
        assert required.issubset(cols)

    def test_idempotent(self, tmp_path):
        import multi_poll_predict

        db = sqlite3.connect(str(tmp_path / "t.db"))
        multi_poll_predict.init_table(db)
        multi_poll_predict.init_table(db)
        # No exception, table still queryable
        db.execute("SELECT COUNT(*) FROM multi_poll_predictions").fetchone()

    def test_module_exports_poll_offsets(self):
        import multi_poll_predict

        assert hasattr(multi_poll_predict, "POLL_OFFSETS_S")
        offsets = multi_poll_predict.POLL_OFFSETS_S
        assert isinstance(offsets, (list, tuple))
        assert len(offsets) >= 5
        # All offsets must be within a single 5m cycle
        assert all(0 < o < 300 for o in offsets)
        # Must be sorted ascending
        assert list(offsets) == sorted(offsets)


# ── log_poll ───────────────────────────────────────────────────────


class TestLogPoll:
    def test_writes_one_row_with_metadata(self, tmp_path):
        import multi_poll_predict

        db = sqlite3.connect(str(tmp_path / "t.db"))
        multi_poll_predict.init_table(db)

        multi_poll_predict.log_poll(
            db,
            cycle=42,
            cycle_close_at="2026-04-28T12:00:00+00:00",
            offset_seconds=120,
            market_id="0xabc",
            asset="BTC",
            estimate=0.62,
            regime_label="MEDIUM_VOL / NEUTRAL",
            spot_at_poll=78400.0,
            in_flight_return_pct=0.025,
        )

        row = db.execute(
            "SELECT cycle, offset_seconds, market_id, asset, estimate, "
            "regime, spot_at_poll, in_flight_return_pct, poll_succeeded "
            "FROM multi_poll_predictions"
        ).fetchone()
        assert row[0] == 42
        assert row[1] == 120
        assert row[2] == "0xabc"
        assert row[3] == "BTC"
        assert row[4] == 0.62
        assert row[5] == "MEDIUM_VOL / NEUTRAL"
        assert row[6] == 78400.0
        assert row[7] == 0.025
        assert row[8] == 1  # default success

    def test_log_poll_with_orderbook_fields(self, tmp_path):
        """Realistic-shadow extension (2026-04-30): log orderbook context
        at poll time so Phase B can compute realistic-entry P&L."""
        import multi_poll_predict

        db = sqlite3.connect(str(tmp_path / "t.db"))
        multi_poll_predict.init_table(db)
        multi_poll_predict.log_poll(
            db,
            cycle=1,
            cycle_close_at="2026-04-30T12:00:00+00:00",
            offset_seconds=180,
            market_id="0xabc",
            asset="BTC",
            estimate=0.65,
            regime_label="MEDIUM_VOL / NEUTRAL",
            spot_at_poll=78400.0,
            mkt_mid=0.52,
            mkt_best_bid=0.51,
            mkt_best_ask=0.53,
            mkt_spread=0.02,
            orderbook_age_ms=250,
        )
        row = db.execute(
            "SELECT mkt_mid, mkt_best_bid, mkt_best_ask, mkt_spread, "
            "orderbook_age_ms FROM multi_poll_predictions"
        ).fetchone()
        assert row == (0.52, 0.51, 0.53, 0.02, 250)

    def test_log_poll_orderbook_optional(self, tmp_path):
        """When orderbook unavailable, columns must be NULL — never block
        the row write. Mirrors arb_divergence pattern."""
        import multi_poll_predict

        db = sqlite3.connect(str(tmp_path / "t.db"))
        multi_poll_predict.init_table(db)
        multi_poll_predict.log_poll(
            db,
            cycle=1,
            cycle_close_at="2026-04-30T12:00:00+00:00",
            offset_seconds=180,
            market_id="0xabc",
            asset="BTC",
            estimate=0.65,
            regime_label="MEDIUM_VOL / NEUTRAL",
            spot_at_poll=78400.0,
            # No orderbook fields supplied
        )
        row = db.execute(
            "SELECT estimate, mkt_mid, mkt_best_ask FROM multi_poll_predictions"
        ).fetchone()
        assert row == (0.65, None, None)  # signal stored, orderbook NULL

    def test_get_market_orderbook_falls_back_to_price_yes(
        self, tmp_path, monkeypatch
    ):
        """Regression for 2026-05-01 bug: WS cache only covers ~50 tokens,
        so most market lookups returned all-None. Fallback to gamma
        snapshot's markets.price_yes was missing. With the fix, when WS
        miss happens, we return (price_yes, None, None, None, None)."""
        import multi_poll_predict

        # Build a minimal predictions.db with a markets row
        db_path = str(tmp_path / "p.db")
        db = sqlite3.connect(db_path)
        db.execute(
            "CREATE TABLE markets (id TEXT PRIMARY KEY, price_yes REAL, "
            "price_no REAL, fetched_at TEXT, resolved INTEGER)"
        )
        db.execute(
            "INSERT INTO markets (id, price_yes, price_no, fetched_at, resolved) "
            "VALUES ('mkt1', 0.62, 0.38, '2026-05-01T12:00:00Z', 0)"
        )
        db.commit()
        db.close()

        # Make the WS cache path return None (simulates the bug condition).
        # We do this by simulating a missing token so the path falls through.
        monkeypatch.setattr(
            "clob_depth.get_clob_tokens_safe",
            lambda mid: None,
        )

        result = multi_poll_predict._get_market_orderbook(
            "mkt1", db_path=db_path
        )
        # Mid = 0.62 from gamma snapshot; bid/ask/spread/age all None
        assert result == (0.62, None, None, None, None)

    def test_get_market_orderbook_returns_all_none_when_market_unknown(
        self, tmp_path, monkeypatch
    ):
        """If neither cache nor markets table has the row, all-None."""
        import multi_poll_predict

        db_path = str(tmp_path / "p.db")
        db = sqlite3.connect(db_path)
        db.execute(
            "CREATE TABLE markets (id TEXT PRIMARY KEY, price_yes REAL, "
            "price_no REAL, fetched_at TEXT, resolved INTEGER)"
        )
        db.commit()
        db.close()

        monkeypatch.setattr(
            "clob_depth.get_clob_tokens_safe",
            lambda mid: None,
        )

        result = multi_poll_predict._get_market_orderbook(
            "missing_mkt", db_path=db_path
        )
        assert result == (None, None, None, None, None)

    def test_get_market_orderbook_calls_age_ms_method(self, monkeypatch):
        """Regression: orderbook_age_ms must be a number, not TokenEntry.age_ms."""
        import multi_poll_predict
        import orderbook_cache

        class Entry:
            mid = 0.54
            best_bid = 0.53
            best_ask = 0.55
            spread = 0.02

            def age_ms(self):
                return 321

        class Cache:
            def get_fresh_entry(self, token_id):
                return Entry()

        monkeypatch.setattr(
            "clob_depth.get_clob_tokens_safe",
            lambda mid: {"yes": "yes-token", "no": "no-token"},
        )
        monkeypatch.setattr(orderbook_cache.OrderbookCache, "load", lambda: Cache())

        result = multi_poll_predict._get_market_orderbook("mkt1")

        assert result == (0.54, 0.53, 0.55, 0.02, 321)

    def test_init_table_migration_adds_orderbook_columns(self, tmp_path):
        """Pre-existing tables (from before 2026-04-30) get the new
        orderbook columns added via ALTER TABLE on next init_table call."""
        db = sqlite3.connect(str(tmp_path / "t.db"))
        # Simulate a pre-2026-04-30 table missing the new columns
        db.execute("""
            CREATE TABLE multi_poll_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle INTEGER,
                cycle_close_at TEXT NOT NULL,
                offset_seconds INTEGER NOT NULL,
                predicted_at TEXT NOT NULL,
                market_id TEXT NOT NULL,
                asset TEXT,
                estimate REAL,
                regime TEXT,
                spot_at_poll REAL,
                in_flight_return_pct REAL,
                poll_succeeded INTEGER DEFAULT 1,
                market_resolved INTEGER,
                market_outcome INTEGER,
                won INTEGER
            )
        """)
        db.commit()

        import multi_poll_predict
        multi_poll_predict.init_table(db)

        cols = {
            r[1]
            for r in db.execute(
                "PRAGMA table_info(multi_poll_predictions)"
            ).fetchall()
        }
        assert "mkt_mid" in cols
        assert "mkt_best_bid" in cols
        assert "mkt_best_ask" in cols
        assert "mkt_spread" in cols
        assert "orderbook_age_ms" in cols
        assert "conviction_score" in cols
        # And idempotent: second call shouldn't error
        multi_poll_predict.init_table(db)

    def test_log_poll_stores_conviction_score(self, tmp_path):
        import multi_poll_predict

        db = sqlite3.connect(str(tmp_path / "t.db"))
        multi_poll_predict.init_table(db)
        poll_id = multi_poll_predict.log_poll(
            db,
            cycle=1,
            cycle_close_at="2026-05-13T12:00:00+00:00",
            offset_seconds=180,
            market_id="0xabc",
            asset="BTC",
            estimate=0.64,
            regime_label="MEDIUM_VOL / NEUTRAL",
            spot_at_poll=100000.0,
            conviction_score=4,
        )
        row = db.execute(
            "SELECT id, conviction_score FROM multi_poll_predictions"
        ).fetchone()
        assert row == (poll_id, 4)

    def test_compute_poll_conviction_uses_market_price_sweet_spot(self):
        import multi_poll_predict

        signal = {
            "estimate": 0.64,
            "should_trade": True,
            "confidence": "medium",
            "direction": "UP",
        }
        regime = {"label": "MEDIUM_VOL / NEUTRAL"}

        assert multi_poll_predict.compute_poll_conviction(
            signal, regime, mkt_price=0.55
        ) == 4

    def test_log_poll_failure_marks_succeeded_zero(self, tmp_path):
        import multi_poll_predict

        db = sqlite3.connect(str(tmp_path / "t.db"))
        multi_poll_predict.init_table(db)
        multi_poll_predict.log_poll(
            db,
            cycle=1,
            cycle_close_at="2026-04-28T12:00:00+00:00",
            offset_seconds=30,
            market_id="0xabc",
            asset="BTC",
            estimate=None,
            regime_label=None,
            spot_at_poll=None,
            poll_succeeded=False,
        )
        row = db.execute(
            "SELECT poll_succeeded, estimate FROM multi_poll_predictions"
        ).fetchone()
        assert row[0] == 0
        assert row[1] is None


# ── retention ──────────────────────────────────────────────────────


class TestPurgeOldPolls:
    def test_deletes_rows_older_than_retention(self, tmp_path):
        import multi_poll_predict

        db = sqlite3.connect(str(tmp_path / "t.db"))
        multi_poll_predict.init_table(db)

        # Old row (60d)
        old_ts = "2026-02-28T00:00:00+00:00"
        # Recent row (1d)
        recent_ts = "2026-04-27T12:00:00+00:00"

        for ts in (old_ts, recent_ts):
            db.execute(
                "INSERT INTO multi_poll_predictions "
                "(cycle, cycle_close_at, offset_seconds, predicted_at, "
                " market_id, asset, estimate) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (1, ts, 30, ts, "m", "BTC", 0.5),
            )
        db.commit()

        # Cutoff "now" relative to test data: pretend it's 2026-04-28
        purged = multi_poll_predict.purge_old_polls(
            db, retention_days=30, now_iso="2026-04-28T12:00:00+00:00"
        )
        assert purged == 1
        rows = db.execute(
            "SELECT predicted_at FROM multi_poll_predictions"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == recent_ts

    def test_idempotent_on_no_old_rows(self, tmp_path):
        import multi_poll_predict

        db = sqlite3.connect(str(tmp_path / "t.db"))
        multi_poll_predict.init_table(db)

        purged = multi_poll_predict.purge_old_polls(
            db, retention_days=30, now_iso="2026-04-28T12:00:00+00:00"
        )
        assert purged == 0


# ── schedule_polls (async orchestrator) ────────────────────────────


class TestSchedulePolls:
    def _make_fake_engine(self, candles, active_markets):
        """Minimal mock with just the bits multi_poll uses."""

        class _CandleBuffer:
            def get_candles(self, symbol, interval):
                return candles

        class _FakeEngine:
            candle_buffer = _CandleBuffer()

        return _FakeEngine()

    def _fake_candles(self, n=20, base=78000):
        """Synthetic up-trending candles for predictable signal output."""
        return [
            {
                "open": base + i * 10,
                "close": base + (i + 1) * 10,
                "high": base + (i + 1) * 10 + 5,
                "low": base + i * 10 - 5,
                "volume": 100,
                "direction": "UP",
                "body_pct": 0.0001,
                "wick_ratio": 0.5,
                "time": f"00:{i:02d}",
                "timestamp_ms": 1000000 + i * 60_000,
            }
            for i in range(n)
        ]

    def test_fires_one_poll_per_offset(self, tmp_path, monkeypatch):
        """Each offset in POLL_OFFSETS_S yields exactly one row per market."""
        import multi_poll_predict

        db_path = str(tmp_path / "t.db")
        db = sqlite3.connect(db_path)
        multi_poll_predict.init_table(db)
        # Two active markets in the markets table
        db.execute(
            "CREATE TABLE markets (id TEXT PRIMARY KEY, question TEXT, "
            "end_date TEXT, fetched_at TEXT, resolved INTEGER DEFAULT 0)"
        )
        db.execute(
            "INSERT INTO markets (id, question, end_date, resolved) "
            "VALUES ('m1', 'Will BTC be Up at 12:05?', '2026-04-28T12:05:00+00:00', 0)"
        )
        db.execute(
            "INSERT INTO markets (id, question, end_date, resolved) "
            "VALUES ('m2', 'Will BTC be Up at 12:10?', '2026-04-28T12:10:00+00:00', 0)"
        )
        db.commit()
        db.close()

        engine = self._make_fake_engine(self._fake_candles(), [])

        async def run():
            with patch(
                "multi_poll_predict.asyncio.sleep", new_callable=AsyncMock
            ):
                await multi_poll_predict.schedule_polls(
                    engine,
                    db_path=db_path,
                    cycle=42,
                    cycle_close_at="2026-04-28T12:00:00+00:00",
                    asset="BTC",
                    symbol="BTCUSDT",
                    interval="5",
                )

        run_async(run())

        db = sqlite3.connect(db_path)
        rows = db.execute(
            "SELECT offset_seconds, market_id FROM multi_poll_predictions "
            "ORDER BY offset_seconds, market_id"
        ).fetchall()
        # Expect len(POLL_OFFSETS_S) * 2 markets rows
        expected_rows = len(multi_poll_predict.POLL_OFFSETS_S) * 2
        assert len(rows) == expected_rows
        offsets_seen = sorted(set(r[0] for r in rows))
        assert offsets_seen == list(multi_poll_predict.POLL_OFFSETS_S)

    def test_failure_in_one_poll_doesnt_kill_others(
        self, tmp_path, monkeypatch
    ):
        """Raising in compute_poll_predictions for ONE offset should
        leave all others working — with a row marked poll_succeeded=0."""
        import multi_poll_predict

        db_path = str(tmp_path / "t.db")
        db = sqlite3.connect(db_path)
        multi_poll_predict.init_table(db)
        db.execute(
            "CREATE TABLE markets (id TEXT PRIMARY KEY, question TEXT, "
            "end_date TEXT, fetched_at TEXT, resolved INTEGER DEFAULT 0)"
        )
        db.execute(
            "INSERT INTO markets (id, question, end_date, resolved) "
            "VALUES ('m1', 'BTC Up?', '2026-04-28T12:05:00+00:00', 0)"
        )
        db.commit()
        db.close()

        engine = self._make_fake_engine(self._fake_candles(), [])

        target_offset = multi_poll_predict.POLL_OFFSETS_S[3]
        original_compute = multi_poll_predict.compute_poll_predictions

        def flaky_compute(*args, **kwargs):
            if kwargs.get("offset_seconds") == target_offset:
                raise RuntimeError("synthetic failure")
            return original_compute(*args, **kwargs)

        monkeypatch.setattr(
            multi_poll_predict, "compute_poll_predictions", flaky_compute
        )

        async def run():
            with patch(
                "multi_poll_predict.asyncio.sleep", new_callable=AsyncMock
            ):
                await multi_poll_predict.schedule_polls(
                    engine,
                    db_path=db_path,
                    cycle=42,
                    cycle_close_at="2026-04-28T12:00:00+00:00",
                    asset="BTC",
                    symbol="BTCUSDT",
                    interval="5",
                )

        run_async(run())

        db = sqlite3.connect(db_path)
        rows = db.execute(
            "SELECT offset_seconds, poll_succeeded "
            "FROM multi_poll_predictions ORDER BY offset_seconds"
        ).fetchall()

        # All offsets must have a row, even the failing one
        offsets = sorted(set(r[0] for r in rows))
        assert offsets == list(multi_poll_predict.POLL_OFFSETS_S)
        # Failing one is logged with poll_succeeded=0
        for off, ok in rows:
            if off == target_offset:
                assert ok == 0
            else:
                assert ok == 1


# ── compute_poll_predictions (signal logic) ────────────────────────


class TestComputePollPredictions:
    def test_returns_signal_and_regime_from_candles(self):
        import multi_poll_predict

        # 20 monotonically up candles → momentum signal should be UP
        candles = [
            {
                "open": 100 + i * 0.1,
                "close": 100 + (i + 1) * 0.1,
                "high": 100 + (i + 1) * 0.1 + 0.05,
                "low": 100 + i * 0.1 - 0.05,
                "volume": 100,
                "direction": "UP",
                "body_pct": 0.0001,
                "wick_ratio": 0.5,
                "time": f"00:{i:02d}",
                "timestamp_ms": 1000000 + i * 60_000,
            }
            for i in range(20)
        ]

        result = multi_poll_predict.compute_poll_predictions(
            candles=candles,
            asset="BTC",
            offset_seconds=60,
        )
        # Returns a dict-like with the keys we need to log
        assert "estimate" in result
        assert "regime_label" in result
        assert "spot_at_poll" in result
        assert isinstance(result["estimate"], (int, float))
        # Spot at poll is the most recent close
        assert result["spot_at_poll"] == candles[-1]["close"]
