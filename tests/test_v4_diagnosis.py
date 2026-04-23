"""Tests for v4_diagnosis.py — one-shot LLM diagnosis of momentum decay.

Tests the bundle-builder and markdown renderer directly (deterministic).
The LLM call path is mocked — we verify the client receives the right
prompt shape, not what the model says back.
"""

import sys
import os
import sqlite3
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest


def _init_test_predictions_db(path: str) -> sqlite3.Connection:
    """Minimal schema matching the real predictions.db for v4_diagnosis queries."""
    db = sqlite3.connect(path)
    db.executescript("""
    CREATE TABLE markets (
        id TEXT PRIMARY KEY,
        question TEXT,
        end_date TEXT,
        resolved INTEGER DEFAULT 0,
        outcome INTEGER DEFAULT NULL
    );
    CREATE TABLE predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        market_id TEXT,
        agent TEXT,
        estimate REAL,
        predicted_at TEXT,
        regime TEXT,
        conviction_score INTEGER
    );
    """)
    db.commit()
    return db


def _seed_predictions(db, rows):
    """rows: list of dicts with date, estimate, regime, conviction, outcome."""
    for i, r in enumerate(rows):
        mid = f"m{i}"
        db.execute(
            "INSERT INTO markets (id, question, resolved, outcome) VALUES (?, ?, ?, ?)",
            (mid, f"q{i}", 1, r["outcome"]),
        )
        db.execute(
            "INSERT INTO predictions (market_id, agent, estimate, predicted_at, "
            "regime, conviction_score) VALUES (?, ?, ?, ?, ?, ?)",
            (mid, "btc", r["estimate"], f"{r['date']}T12:00:00+00:00",
             r["regime"], r["conviction"]),
        )
    db.commit()


# ── bundle builder ─────────────────────────────────────────────────


class TestBuildBundle:
    def test_returns_per_day_per_regime_aggregates(self, tmp_path):
        from v4_diagnosis import build_bundle

        db = _init_test_predictions_db(str(tmp_path / "t.db"))
        _seed_predictions(db, [
            # 2026-04-20: 2 wins / 0 losses in MED/NEUTRAL
            {"date": "2026-04-20", "estimate": 0.7, "regime": "MEDIUM_VOL / NEUTRAL",
             "conviction": 3, "outcome": 1},
            {"date": "2026-04-20", "estimate": 0.7, "regime": "MEDIUM_VOL / NEUTRAL",
             "conviction": 3, "outcome": 1},
            # 2026-04-21: 0 wins / 2 losses in MED/NEUTRAL (collapse day)
            {"date": "2026-04-21", "estimate": 0.7, "regime": "MEDIUM_VOL / NEUTRAL",
             "conviction": 3, "outcome": 0},
            {"date": "2026-04-21", "estimate": 0.7, "regime": "MEDIUM_VOL / NEUTRAL",
             "conviction": 3, "outcome": 0},
            # 2026-04-21: 1 win / 0 losses in HIGH_VOL/TRENDING
            {"date": "2026-04-21", "estimate": 0.3, "regime": "HIGH_VOL / TRENDING",
             "conviction": 3, "outcome": 0},
        ])

        bundle = build_bundle(db, start="2026-04-20", end="2026-04-21")

        assert bundle["window"] == {"start": "2026-04-20", "end": "2026-04-21"}
        # Per-day aggregation
        by_day = {d["date"]: d for d in bundle["per_day"]}
        assert by_day["2026-04-20"]["wins"] == 2
        assert by_day["2026-04-20"]["total"] == 2
        assert by_day["2026-04-21"]["wins"] == 1
        assert by_day["2026-04-21"]["total"] == 3
        # Per-regime-per-day cell exists
        cells = bundle["per_day_per_regime"]
        assert any(c["date"] == "2026-04-20" and
                   "MEDIUM_VOL" in c["regime"] and c["wins"] == 2 for c in cells)

    def test_excludes_low_conviction_bets(self, tmp_path):
        from v4_diagnosis import build_bundle

        db = _init_test_predictions_db(str(tmp_path / "t.db"))
        _seed_predictions(db, [
            # conv=2 — should be excluded (not a real bet)
            {"date": "2026-04-20", "estimate": 0.7, "regime": "MEDIUM_VOL / NEUTRAL",
             "conviction": 2, "outcome": 1},
            # conv=3 — included
            {"date": "2026-04-20", "estimate": 0.7, "regime": "MEDIUM_VOL / NEUTRAL",
             "conviction": 3, "outcome": 1},
        ])
        bundle = build_bundle(db, start="2026-04-20", end="2026-04-20",
                              min_conviction=3)
        per_day = {d["date"]: d for d in bundle["per_day"]}
        assert per_day["2026-04-20"]["total"] == 1

    def test_respects_date_window(self, tmp_path):
        from v4_diagnosis import build_bundle

        db = _init_test_predictions_db(str(tmp_path / "t.db"))
        _seed_predictions(db, [
            {"date": "2026-04-15", "estimate": 0.7, "regime": "MEDIUM_VOL / NEUTRAL",
             "conviction": 3, "outcome": 1},
            {"date": "2026-04-22", "estimate": 0.7, "regime": "MEDIUM_VOL / NEUTRAL",
             "conviction": 3, "outcome": 0},
        ])
        bundle = build_bundle(db, start="2026-04-20", end="2026-04-25")
        dates = {d["date"] for d in bundle["per_day"]}
        assert "2026-04-15" not in dates
        assert "2026-04-22" in dates

    def test_empty_window_returns_empty_bundle(self, tmp_path):
        from v4_diagnosis import build_bundle

        db = _init_test_predictions_db(str(tmp_path / "t.db"))
        bundle = build_bundle(db, start="2026-04-20", end="2026-04-25")
        assert bundle["per_day"] == []
        assert bundle["per_day_per_regime"] == []
        assert bundle["summary"]["total_bets"] == 0


# ── diagnose_momentum_decay ─────────────────────────────────────────


class TestDiagnoseMomentumDecay:
    def _fake_llm(self, payload):
        def _classify_structured(prompt, schema=None, **kw):
            self._last_prompt = prompt
            self._last_schema = schema
            return payload
        return _classify_structured

    def test_calls_llm_with_schema_enforcing_required_keys(self, monkeypatch, tmp_path):
        from v4_diagnosis import diagnose_momentum_decay
        import llm_inference

        db = _init_test_predictions_db(str(tmp_path / "t.db"))
        _seed_predictions(db, [
            {"date": "2026-04-21", "estimate": 0.7, "regime": "MEDIUM_VOL / NEUTRAL",
             "conviction": 3, "outcome": 0},
        ])

        fake_output = {
            "onset_date_hypothesis": "2026-04-08",
            "regime_correlation": {"MEDIUM_VOL / NEUTRAL": "sharp drop"},
            "news_correlation": None,
            "decay_vs_reverting": "decaying",
            "confidence": "medium",
            "recommended_action": "pivot",
        }
        monkeypatch.setattr(llm_inference, "classify_structured",
                            self._fake_llm(fake_output))

        out = diagnose_momentum_decay(
            db, start="2026-04-21", end="2026-04-21",
            output_path=str(tmp_path / "out.md"),
        )

        assert out["llm_output"] == fake_output
        # The schema must enforce the critical decision-gate keys
        required = self._last_schema.get("required", [])
        for key in ("onset_date_hypothesis", "decay_vs_reverting", "confidence"):
            assert key in required

    def test_writes_markdown_report(self, monkeypatch, tmp_path):
        from v4_diagnosis import diagnose_momentum_decay
        import llm_inference

        db = _init_test_predictions_db(str(tmp_path / "t.db"))
        _seed_predictions(db, [
            {"date": "2026-04-21", "estimate": 0.7, "regime": "MEDIUM_VOL / NEUTRAL",
             "conviction": 3, "outcome": 0},
        ])

        payload = {
            "onset_date_hypothesis": "2026-04-08",
            "regime_correlation": {"MEDIUM_VOL / NEUTRAL": "dropped"},
            "news_correlation": None,
            "decay_vs_reverting": "decaying",
            "confidence": "medium",
            "recommended_action": "pivot",
        }
        monkeypatch.setattr(llm_inference, "classify_structured",
                            self._fake_llm(payload))

        out_path = tmp_path / "v4_diag.md"
        diagnose_momentum_decay(
            db, start="2026-04-21", end="2026-04-21",
            output_path=str(out_path),
        )
        assert out_path.exists()
        text = out_path.read_text()
        assert "2026-04-08" in text  # onset hypothesis surfaced
        assert "decaying" in text
        assert "MEDIUM_VOL / NEUTRAL" in text

    def test_prompt_mentions_regime_timeline(self, monkeypatch, tmp_path):
        """The prompt must include the bundle content, not just the window bounds."""
        from v4_diagnosis import diagnose_momentum_decay
        import llm_inference

        db = _init_test_predictions_db(str(tmp_path / "t.db"))
        _seed_predictions(db, [
            {"date": "2026-04-21", "estimate": 0.7,
             "regime": "DIAGNOSTIC_MARKER_REGIME",
             "conviction": 3, "outcome": 0},
        ])

        payload = {
            "onset_date_hypothesis": None,
            "regime_correlation": {},
            "news_correlation": None,
            "decay_vs_reverting": "ambiguous",
            "confidence": "low",
            "recommended_action": "wait",
        }
        monkeypatch.setattr(llm_inference, "classify_structured",
                            self._fake_llm(payload))

        diagnose_momentum_decay(
            db, start="2026-04-21", end="2026-04-21",
            output_path=str(tmp_path / "o.md"),
        )
        assert "DIAGNOSTIC_MARKER_REGIME" in self._last_prompt
