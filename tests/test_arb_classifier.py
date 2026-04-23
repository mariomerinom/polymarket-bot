"""Tests for arb_classifier.py — LLM classification of arb divergences.

The LLM call is mocked. We assert: row sampling, bundle shape, DB writes,
calibration logging, and class-distribution aggregation.
"""

import sys
import os
import sqlite3
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest


def _init_arb_tables(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    # Real arb_divergence schema (subset sufficient for classifier)
    db.executescript("""
    CREATE TABLE arb_divergence (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        cycle INTEGER,
        pipeline TEXT NOT NULL,
        market_id TEXT NOT NULL,
        market_class TEXT,
        asset TEXT,
        direction_sense TEXT,
        window_open_at TEXT,
        window_close_at TEXT,
        window_total_seconds REAL,
        time_to_expiry_seconds REAL,
        window_has_opened INTEGER,
        bybit_spot REAL,
        open_spot REAL,
        r_so_far REAL,
        realized_vol_annual REAL,
        sigma_window REAL,
        fair_p REAL,
        mkt_mid REAL,
        mkt_best_bid REAL,
        mkt_best_ask REAL,
        mkt_spread REAL,
        orderbook_age_ms INTEGER,
        divergence REAL,
        abs_divergence REAL,
        would_arb_side TEXT,
        would_arb_edge REAL,
        regime_label TEXT,
        daily_regime_label TEXT
    );
    """)
    db.commit()
    return db


def _insert_div(db, **overrides):
    defaults = {
        "timestamp": "2026-04-23T16:15:00+00:00",
        "cycle": 6200,
        "pipeline": "btc_5m",
        "market_id": "0xabc",
        "market_class": "5m",
        "asset": "BTC",
        "direction_sense": "up",
        "window_has_opened": 1,
        "bybit_spot": 78400.0,
        "open_spot": 78380.0,
        "r_so_far": 0.00025,
        "realized_vol_annual": 0.5,
        "fair_p": 0.55,
        "mkt_mid": 0.50,
        "mkt_best_bid": 0.49,
        "mkt_best_ask": 0.51,
        "mkt_spread": 0.02,
        "divergence": 0.05,
        "abs_divergence": 0.05,
        "would_arb_side": "buy_poly",
        "would_arb_edge": 0.03,
        "regime_label": "MEDIUM_VOL / NEUTRAL",
        "daily_regime_label": "chop",
    }
    defaults.update(overrides)
    cols = ", ".join(defaults.keys())
    qs = ", ".join(["?"] * len(defaults))
    db.execute(
        f"INSERT INTO arb_divergence ({cols}) VALUES ({qs})",
        list(defaults.values()),
    )
    db.commit()


# ── table init ─────────────────────────────────────────────────────


class TestInitTable:
    def test_creates_classifications_table(self, tmp_path):
        import arb_classifier
        import llm_inference

        db = _init_arb_tables(str(tmp_path / "t.db"))
        llm_inference.init_table(db)  # calibration_log
        arb_classifier.init_table(db)

        cols = {
            r[1]
            for r in db.execute(
                "PRAGMA table_info(arb_divergence_classifications)"
            ).fetchall()
        }
        assert {"divergence_id", "class", "rationale", "confidence",
                "llm_model", "classified_at"}.issubset(cols)

    def test_is_idempotent(self, tmp_path):
        import arb_classifier

        db = _init_arb_tables(str(tmp_path / "t.db"))
        arb_classifier.init_table(db)
        arb_classifier.init_table(db)


# ── row sampling ───────────────────────────────────────────────────


class TestSampling:
    def test_picks_rows_above_min_edge(self, tmp_path):
        import arb_classifier

        db = _init_arb_tables(str(tmp_path / "t.db"))
        _insert_div(db, would_arb_edge=0.005, abs_divergence=0.005)  # below
        _insert_div(db, would_arb_edge=0.03, abs_divergence=0.05)    # above
        _insert_div(db, would_arb_edge=0.10, abs_divergence=0.12)    # above

        rows = arb_classifier.sample_high_divergence_rows(
            db, n=10, min_edge=0.02
        )
        assert len(rows) == 2
        # Ordered by abs_divergence desc
        assert rows[0]["abs_divergence"] >= rows[1]["abs_divergence"]

    def test_respects_regime_filter(self, tmp_path):
        import arb_classifier

        db = _init_arb_tables(str(tmp_path / "t.db"))
        _insert_div(db, regime_label="MEDIUM_VOL / NEUTRAL", would_arb_edge=0.05)
        _insert_div(db, regime_label="HIGH_VOL / TRENDING", would_arb_edge=0.08)

        rows = arb_classifier.sample_high_divergence_rows(
            db, n=10, min_edge=0.02, regime_filter="MEDIUM_VOL / NEUTRAL"
        )
        assert len(rows) == 1
        assert rows[0]["regime_label"] == "MEDIUM_VOL / NEUTRAL"

    def test_limits_to_n(self, tmp_path):
        import arb_classifier

        db = _init_arb_tables(str(tmp_path / "t.db"))
        for i in range(10):
            _insert_div(db, would_arb_edge=0.03 + i * 0.01,
                        abs_divergence=0.03 + i * 0.01)

        rows = arb_classifier.sample_high_divergence_rows(db, n=3, min_edge=0.02)
        assert len(rows) == 3


# ── classify_one ───────────────────────────────────────────────────


class TestClassifyOne:
    def _fake_llm_returning(self, payload):
        def _classify_structured(prompt, schema=None, **kw):
            self._last_prompt = prompt
            self._last_schema = schema
            return payload
        return _classify_structured

    def test_writes_classification_row(self, monkeypatch, tmp_path):
        import arb_classifier
        import llm_inference

        db = _init_arb_tables(str(tmp_path / "t.db"))
        llm_inference.init_table(db)
        arb_classifier.init_table(db)
        _insert_div(db, would_arb_edge=0.05, abs_divergence=0.05)

        payload = {
            "class": "lag",
            "rationale": "polymarket hadn't repriced",
            "confidence": "medium",
        }
        monkeypatch.setattr(
            llm_inference, "classify_structured",
            self._fake_llm_returning(payload),
        )

        rows = arb_classifier.sample_high_divergence_rows(db, n=1, min_edge=0.02)
        arb_classifier.classify_one(db, rows[0])

        result = db.execute(
            "SELECT divergence_id, class, rationale, confidence "
            "FROM arb_divergence_classifications"
        ).fetchone()
        assert result[0] == rows[0]["id"]
        assert result[1] == "lag"
        assert result[2] == "polymarket hadn't repriced"
        assert result[3] == "medium"

    def test_logs_to_calibration(self, monkeypatch, tmp_path):
        import arb_classifier
        import llm_inference

        db = _init_arb_tables(str(tmp_path / "t.db"))
        llm_inference.init_table(db)
        arb_classifier.init_table(db)
        _insert_div(db, would_arb_edge=0.05, abs_divergence=0.05)

        payload = {"class": "adverse_selection", "rationale": "x",
                   "confidence": "high"}
        monkeypatch.setattr(
            llm_inference, "classify_structured",
            self._fake_llm_returning(payload),
        )

        rows = arb_classifier.sample_high_divergence_rows(db, n=1, min_edge=0.02)
        arb_classifier.classify_one(db, rows[0])

        cal = db.execute(
            "SELECT task_name, input_ref FROM llm_calibration_log"
        ).fetchone()
        assert cal[0] == "arb_classifier"
        assert str(rows[0]["id"]) in cal[1]

    def test_prompt_contains_core_divergence_fields(self, monkeypatch, tmp_path):
        import arb_classifier
        import llm_inference

        db = _init_arb_tables(str(tmp_path / "t.db"))
        llm_inference.init_table(db)
        arb_classifier.init_table(db)
        _insert_div(
            db,
            would_arb_edge=0.05,
            abs_divergence=0.05,
            regime_label="MEDIUM_VOL / NEUTRAL",
            fair_p=0.66,
            mkt_mid=0.50,
        )

        payload = {"class": "lag", "rationale": "x", "confidence": "low"}
        monkeypatch.setattr(
            llm_inference, "classify_structured",
            self._fake_llm_returning(payload),
        )

        rows = arb_classifier.sample_high_divergence_rows(db, n=1, min_edge=0.02)
        arb_classifier.classify_one(db, rows[0])

        # The prompt must carry enough data for classification
        assert "0.66" in self._last_prompt or "fair_p" in self._last_prompt
        assert "MEDIUM_VOL / NEUTRAL" in self._last_prompt

    def test_schema_enforces_class_rationale_confidence(self, monkeypatch, tmp_path):
        import arb_classifier
        import llm_inference

        db = _init_arb_tables(str(tmp_path / "t.db"))
        llm_inference.init_table(db)
        arb_classifier.init_table(db)
        _insert_div(db, would_arb_edge=0.05, abs_divergence=0.05)

        payload = {"class": "lag", "rationale": "x", "confidence": "low"}
        monkeypatch.setattr(
            llm_inference, "classify_structured",
            self._fake_llm_returning(payload),
        )

        rows = arb_classifier.sample_high_divergence_rows(db, n=1, min_edge=0.02)
        arb_classifier.classify_one(db, rows[0])

        required = self._last_schema.get("required", [])
        assert "class" in required
        assert "rationale" in required
        assert "confidence" in required


# ── orchestrator ───────────────────────────────────────────────────


class TestClassifyDivergences:
    def test_aggregates_class_distribution(self, monkeypatch, tmp_path):
        import arb_classifier
        import llm_inference

        db = _init_arb_tables(str(tmp_path / "t.db"))
        llm_inference.init_table(db)
        arb_classifier.init_table(db)

        # 3 high-divergence rows
        for i in range(3):
            _insert_div(db, would_arb_edge=0.05 + i * 0.01,
                        abs_divergence=0.05 + i * 0.01)

        # LLM returns "lag" for first call, "adverse_selection" for next two
        call_count = [0]

        def _fake_classify(prompt, schema=None, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"class": "lag", "rationale": "r", "confidence": "medium"}
            return {"class": "adverse_selection", "rationale": "r",
                    "confidence": "high"}

        monkeypatch.setattr(llm_inference, "classify_structured", _fake_classify)

        result = arb_classifier.classify_divergences(
            db, n=10, min_edge=0.02
        )

        assert result["n_classified"] == 3
        assert result["class_counts"]["lag"] == 1
        assert result["class_counts"]["adverse_selection"] == 2
        assert call_count[0] == 3

    def test_handles_empty_sample(self, monkeypatch, tmp_path):
        import arb_classifier
        import llm_inference

        db = _init_arb_tables(str(tmp_path / "t.db"))
        llm_inference.init_table(db)
        arb_classifier.init_table(db)
        # No rows inserted

        monkeypatch.setattr(
            llm_inference, "classify_structured",
            lambda *a, **kw: {"class": "x", "rationale": "", "confidence": "low"},
        )

        result = arb_classifier.classify_divergences(db, n=10, min_edge=0.02)
        assert result["n_classified"] == 0
        assert result["class_counts"] == {}
