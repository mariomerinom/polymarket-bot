"""phase_timing.py — Per-phase wall-time instrumentation for pipelines.

Motivation (June 2026 dispatch triage): dispatch p95 sits at ~32s vs the
30s canary gate, dominated by per-pipeline runtimes of 10-16s p50. The
engine measures pipeline TOTAL runtime (`pipeline_runtime_ms`) but nothing
shows where the time goes inside a run (REST fetches vs scoring vs trade
execution). This module records that breakdown.

Usage (inside a pipeline run):

    from phase_timing import PhaseTimer
    timer = PhaseTimer("doge_hl")
    with timer.phase("funding"):
        fetch_funding_rate(...)
    ...
    timer.flush()   # appends one JSON line to data/phase_timings.jsonl

Design constraints:
- Fail-safe: flush() never raises. Instrumentation must not be able to
  break a pipeline cycle.
- Bounded: the JSONL file is trimmed to MAX_LINES on every flush, so it
  cannot grow without limit under 12 pipelines x 288 cycles/day.
- data/ location means the engine's git auto-commit publishes it, so the
  breakdown is queryable from any checkout after `git pull`.
"""
import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent
DEFAULT_PATH = REPO_DIR / "data" / "phase_timings.jsonl"
MAX_LINES = 4000  # ~ one day of 12 pipelines x 288 cycles


class PhaseTimer:
    """Accumulates named phase durations for a single pipeline run."""

    def __init__(self, pipeline: str):
        self.pipeline = pipeline
        self._started = time.time()
        self._phases_ms: dict[str, float] = {}

    @contextmanager
    def phase(self, name: str):
        """Time a named phase. Re-entering the same name accumulates.

        Exceptions propagate (the pipeline's error handling stays in
        charge) but the elapsed time is recorded either way.
        """
        start = time.time()
        try:
            yield
        finally:
            elapsed = (time.time() - start) * 1000
            self._phases_ms[name] = self._phases_ms.get(name, 0.0) + elapsed

    def phases_ms(self) -> dict[str, float]:
        return dict(self._phases_ms)

    def flush(self, path: Path = DEFAULT_PATH) -> None:
        """Append one JSON line; trim file to MAX_LINES. Never raises."""
        try:
            row = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "pipeline": self.pipeline,
                "total_ms": round((time.time() - self._started) * 1000, 1),
                "phases": {k: round(v, 1) for k, v in self._phases_ms.items()},
            }
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = []
            if path.exists():
                existing = path.read_text().splitlines()
            existing.append(json.dumps(row))
            if len(existing) > MAX_LINES:
                existing = existing[-MAX_LINES:]
            path.write_text("\n".join(existing) + "\n")
        except Exception:
            # Fail-safe by contract: instrumentation must never break a run.
            pass
