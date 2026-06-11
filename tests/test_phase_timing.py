"""Behavioral contract for src/phase_timing.py.

Dispatch p95 (32s) is dominated by per-pipeline runtime (10-16s p50), but
nothing measures WHERE inside a pipeline the time goes. The contract:

1. A PhaseTimer measures named phases and reports milliseconds.
2. flush() appends exactly one JSON line per pipeline run to a JSONL file
   with timestamp, pipeline name, total, and per-phase ms.
3. The JSONL file is trimmed so it can never grow unbounded.
4. Recording failures never propagate — instrumentation must not be able
   to break a pipeline cycle.
"""
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from phase_timing import PhaseTimer, MAX_LINES


def test_phase_timer_measures_named_phases():
    timer = PhaseTimer("doge_hl")
    with timer.phase("scoring"):
        time.sleep(0.02)
    with timer.phase("funding"):
        time.sleep(0.01)

    phases = timer.phases_ms()
    assert phases["scoring"] >= 15
    assert phases["funding"] >= 5
    # Phases must be measured independently.
    assert phases["scoring"] > phases["funding"]


def test_same_phase_name_accumulates():
    timer = PhaseTimer("doge_hl")
    for _ in range(2):
        with timer.phase("rest"):
            time.sleep(0.01)
    assert timer.phases_ms()["rest"] >= 15


def test_flush_appends_one_json_line(tmp_path):
    out = tmp_path / "phase_timings.jsonl"
    timer = PhaseTimer("sol_bybit")
    with timer.phase("predict"):
        pass
    timer.flush(path=out)

    lines = out.read_text().strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["pipeline"] == "sol_bybit"
    assert "ts" in row
    assert "total_ms" in row
    assert "predict" in row["phases"]


def test_flush_appends_not_overwrites(tmp_path):
    out = tmp_path / "phase_timings.jsonl"
    for name in ("a", "b"):
        timer = PhaseTimer(name)
        with timer.phase("x"):
            pass
        timer.flush(path=out)
    lines = out.read_text().strip().splitlines()
    assert [json.loads(l)["pipeline"] for l in lines] == ["a", "b"]


def test_file_is_trimmed_to_max_lines(tmp_path):
    out = tmp_path / "phase_timings.jsonl"
    rows = "\n".join(
        json.dumps({"pipeline": f"p{i}", "phases": {}}) for i in range(MAX_LINES + 50)
    )
    out.write_text(rows + "\n")

    timer = PhaseTimer("latest")
    with timer.phase("x"):
        pass
    timer.flush(path=out)

    lines = out.read_text().strip().splitlines()
    assert len(lines) <= MAX_LINES
    # Newest record must survive the trim.
    assert json.loads(lines[-1])["pipeline"] == "latest"


def test_phase_exception_propagates_but_is_still_timed(tmp_path):
    """A failing phase must not swallow the pipeline's exception, but the
    time spent before the failure must still be recorded."""
    timer = PhaseTimer("btc_5m")
    with pytest.raises(ValueError):
        with timer.phase("trade"):
            time.sleep(0.01)
            raise ValueError("boom")
    assert timer.phases_ms()["trade"] >= 5


def test_flush_never_raises(tmp_path, monkeypatch):
    """Instrumentation must be fail-safe: an unwritable path is swallowed."""
    timer = PhaseTimer("doge_hl")
    with timer.phase("x"):
        pass
    # Directory used as file path → open() raises; flush must not.
    timer.flush(path=tmp_path)
