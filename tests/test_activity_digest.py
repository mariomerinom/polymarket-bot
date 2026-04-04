"""Tests for activity_digest.py — auto-generated session safety net."""
import os
import sys
import tempfile
import sqlite3
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _create_test_db(db_path, date_str="2026-04-03"):
    """Create a minimal test database with predictions and markets."""
    db = sqlite3.connect(str(db_path))
    db.execute("""CREATE TABLE predictions (
        id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT, estimate REAL,
        edge REAL, confidence TEXT, reasoning TEXT, predicted_at TEXT,
        cycle INTEGER, conviction_score INTEGER, regime TEXT
    )""")
    db.execute("""CREATE TABLE markets (
        id TEXT PRIMARY KEY, question TEXT, end_date TEXT, resolved INTEGER DEFAULT 0,
        outcome TEXT, slug TEXT
    )""")
    # 3 predictions: 2 wins, 1 loss
    db.execute("INSERT INTO markets VALUES ('m1','Q1','2099-01-01',1,'Yes',NULL)")
    db.execute("INSERT INTO markets VALUES ('m2','Q2','2099-01-01',1,'No',NULL)")
    db.execute("INSERT INTO markets VALUES ('m3','Q3','2099-01-01',1,'Yes',NULL)")

    db.execute(f"""INSERT INTO predictions VALUES
        (1,'m1','momentum_rule',0.65,0.15,'medium','{{}}','{date_str}T10:00:00Z',1,3,'HIGH_VOL / TRENDING')""")
    db.execute(f"""INSERT INTO predictions VALUES
        (2,'m2','momentum_rule',0.35,0.15,'medium','{{}}','{date_str}T11:00:00Z',2,3,'MEDIUM_VOL / NEUTRAL')""")
    db.execute(f"""INSERT INTO predictions VALUES
        (3,'m3','momentum_rule',0.70,0.20,'medium','{{}}','{date_str}T12:00:00Z',3,4,'HIGH_VOL / TRENDING')""")
    db.commit()
    db.close()


def test_session_exists_detection(tmp_path):
    """Detects existing session logs by date prefix."""
    from activity_digest import session_exists

    import activity_digest
    orig = activity_digest.SESSIONS_DIR
    activity_digest.SESSIONS_DIR = tmp_path

    # No session yet
    assert not session_exists("2026-04-03")

    # Create a session file
    (tmp_path / "2026-04-03.md").write_text("# Session")
    assert session_exists("2026-04-03")

    # Timestamped variant
    (tmp_path / "2026-04-04-0902.md").write_text("# Session")
    assert session_exists("2026-04-04")

    # index.md should NOT count as a session
    (tmp_path / "2026-04-05").mkdir(exist_ok=True)  # just in case
    assert not session_exists("2026-04-05")

    activity_digest.SESSIONS_DIR = orig


def test_skips_when_session_exists(tmp_path):
    """Does not overwrite manual session logs."""
    import activity_digest
    orig = activity_digest.SESSIONS_DIR
    activity_digest.SESSIONS_DIR = tmp_path

    (tmp_path / "2026-04-03.md").write_text("# Manual session log")
    result = activity_digest.generate_digest("2026-04-03")
    assert result is None

    # Original content preserved
    assert "Manual session log" in (tmp_path / "2026-04-03.md").read_text()

    activity_digest.SESSIONS_DIR = orig


def test_generates_digest(tmp_path):
    """Produces a well-formatted digest when no session exists."""
    import activity_digest
    orig_sessions = activity_digest.SESSIONS_DIR
    orig_5m = activity_digest.DB_5M

    activity_digest.SESSIONS_DIR = tmp_path
    db_path = tmp_path / "test.db"
    _create_test_db(db_path, "2026-04-03")
    activity_digest.DB_5M = db_path

    result = activity_digest.generate_digest("2026-04-03")
    assert result is not None
    assert result.exists()

    content = result.read_text()
    assert "Activity Digest" in content
    assert "Auto-generated" in content
    assert "Pipeline Health" in content
    assert "Active Optimizations" in content
    assert "Decision Tracker" in content

    activity_digest.SESSIONS_DIR = orig_sessions
    activity_digest.DB_5M = orig_5m


def test_index_update(tmp_path):
    """Updates session index with new digest entry."""
    import activity_digest
    orig = activity_digest.SESSIONS_DIR
    activity_digest.SESSIONS_DIR = tmp_path

    # Create initial index
    index_path = tmp_path / "index.md"
    index_path.write_text(
        "# Session Logs\n\n"
        "Working session summaries.\n\n"
        "- [2026-04-02](2026-04-02.md) — Manual session\n"
    )

    activity_digest.update_index("2026-04-03", is_digest=True)
    content = index_path.read_text()

    # New entry should be before existing
    assert content.index("2026-04-03") < content.index("2026-04-02")
    assert "(auto-digest)" in content

    # Should not duplicate on re-run
    activity_digest.update_index("2026-04-03", is_digest=True)
    assert content.count("2026-04-03") == index_path.read_text().count("2026-04-03")

    activity_digest.SESSIONS_DIR = orig


def test_format_digest_no_data():
    """Handles empty data gracefully."""
    from activity_digest import format_digest

    result = format_digest("2026-04-03", [], [], [], [])
    assert "Activity Digest" in result
    assert "No non-CI commits" in result
    assert "No pipeline data" in result
    assert "No active optimizations" in result
    assert "No tracked decisions" in result


def test_pipeline_health_query(tmp_path):
    """Queries pipeline database correctly."""
    import activity_digest
    orig = activity_digest.DB_5M

    db_path = tmp_path / "test.db"
    _create_test_db(db_path, "2026-04-03")
    activity_digest.DB_5M = db_path

    pipelines = activity_digest.get_pipeline_health("2026-04-03")
    assert len(pipelines) >= 1
    p = pipelines[0]
    assert p["label"] == "BTC 5m"
    assert p["predictions"] == 3
    assert p["bets"] == 3
    # m1: UP predicted, Yes outcome = win
    # m2: DOWN predicted (0.35), No outcome = win
    # m3: UP predicted, Yes outcome = win
    assert p["wr"] == 100.0

    activity_digest.DB_5M = orig
