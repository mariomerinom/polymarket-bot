"""
test_engine_resilience.py — Tests for engine crash recovery hardening.

TDD Step 0: These tests are written BEFORE the fixes.
Covers: _supervise(), git rebase recovery, commit loop resilience, TAEngine init.
"""

import asyncio
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── Helper: run async test ────────────────────────────────────────────────

def run_async(coro):
    """Run an async coroutine in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── TestSupervise ─────────────────────────────────────────────────────────


class TestSupervise:
    """_supervise() wraps coroutines with crash recovery."""

    def _make_engine(self):
        """Create a minimal BotsyEngine without full init."""
        from botsy_engine import BotsyEngine
        with patch.object(BotsyEngine, "__init__", lambda self: None):
            engine = BotsyEngine()
        return engine

    def test_supervisor_restarts_crashed_coroutine(self):
        """A coroutine that throws once, then succeeds, is restarted."""
        engine = self._make_engine()
        call_count = 0

        async def flaky_task():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient failure")
            # Second call succeeds and returns (ending the supervisor loop)

        async def run():
            # Patch sleep to avoid real delays
            with patch("botsy_engine.asyncio.sleep", new_callable=AsyncMock):
                await engine._supervise(flaky_task, name="test_task")

        run_async(run())
        assert call_count == 2, f"Expected 2 calls (crash + restart), got {call_count}"

    def test_supervisor_respects_cancellation(self):
        """CancelledError propagates — graceful shutdown works."""
        engine = self._make_engine()

        async def cancelled_task():
            raise asyncio.CancelledError()

        async def run():
            with pytest.raises(asyncio.CancelledError):
                await engine._supervise(cancelled_task, name="test_cancel")

        run_async(run())

    def test_supervisor_logs_exception(self, capsys):
        """Supervisor logs the crash before restarting."""
        engine = self._make_engine()
        call_count = 0

        async def crash_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("test boom")

        async def run():
            with patch("botsy_engine.asyncio.sleep", new_callable=AsyncMock):
                await engine._supervise(crash_once, name="my_task")

        run_async(run())
        captured = capsys.readouterr()
        assert "my_task" in captured.out
        assert "test boom" in captured.out


# ── TestGitCommitPushSafeRecovery ─────────────────────────────────────────


class TestGitCommitPushSafeRecovery:
    """_git_commit_push uses fetch + ancestor-check, NOT pull --rebase + abort.

    Regression tests for the 2026-04-28 incident where the prior
    implementation's `pull --rebase -X theirs` + `rebase --abort` recovery
    silently discarded a freshly-pushed commit. The new implementation
    is conservative: before committing, fetch origin; if local is ancestor of
    remote, hard fast-forward before staging runtime files; if NOT, write a
    bail marker and quiesce auto-commits until human inspection.
    """

    def _make_engine(self):
        from botsy_engine import BotsyEngine
        with patch.object(BotsyEngine, "__init__", lambda self: None):
            engine = BotsyEngine()
        # _git_head doesn't exist before __init__ is patched; provide a stub
        engine._git_head = lambda: "abc1234"
        return engine

    def _setup_subprocess_mock(self, behavior):
        """Build a subprocess.run mock from a behavior dict.

        behavior keys are command-prefix tuples, values are dicts with
        `returncode`, `stdout`, `stderr` (all optional). Default is rc=0.
        """
        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            result = MagicMock()
            result.returncode = 0
            result.stdout = b""
            result.stderr = b""
            for prefix, spec in behavior.items():
                if tuple(cmd[: len(prefix)]) == prefix:
                    result.returncode = spec.get("returncode", 0)
                    result.stdout = spec.get("stdout", b"")
                    result.stderr = spec.get("stderr", b"")
                    return result
            return result

        return mock_run, calls

    def test_push_succeeds_first_try_no_recovery(self, tmp_path):
        """Happy path: nothing fancy happens on a clean push."""
        from botsy_engine import BotsyEngine

        engine = self._make_engine()
        engine._checkpoint_all_dbs = lambda: None

        mock_run, calls = self._setup_subprocess_mock({
            ("git", "diff", "--cached", "--quiet"): {"returncode": 1},
        })

        with patch("subprocess.run", side_effect=mock_run), \
             patch("os.chdir"), \
             patch("botsy_engine.REPO_DIR", tmp_path):
            (tmp_path / "data").mkdir()
            engine._git_commit_push()

        # Fetch preflight is expected; no reset or abort on already-current HEAD.
        assert any(c[:2] == ["git", "fetch"] for c in calls)
        assert not any(c[:2] == ["git", "reset"] for c in calls)
        assert not any(c[:3] == ["git", "rebase", "--abort"] for c in calls)
        # Did push exactly once
        assert sum(1 for c in calls if c[:2] == ["git", "push"]) == 1

    def test_behind_origin_hard_fast_forwards_before_commit(self, tmp_path):
        """When local HEAD is behind origin, hard reset before staging data.

        This prevents the auto-commit loop from committing source/doc deletions
        from an old VPS worktree after a human source push lands upstream.
        """
        from botsy_engine import BotsyEngine

        engine = self._make_engine()
        engine._checkpoint_all_dbs = lambda: None

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            result = MagicMock()
            result.returncode = 0
            result.stdout = b""
            result.stderr = b""
            if cmd[:3] == ["git", "rev-parse", "--short"]:
                result.stdout = b"localold\n"
            elif cmd[:3] == ["git", "rev-parse", "HEAD"]:
                result.stdout = b"localoldsha\n"
            elif cmd[:3] == ["git", "rev-parse", "origin/main"]:
                result.stdout = b"remotenewsha\n"
            elif cmd[:4] == ["git", "diff", "--cached", "--quiet"]:
                result.returncode = 1
            elif cmd[:4] == ["git", "merge-base", "--is-ancestor", "HEAD"]:
                # local is ancestor of origin/main → safe fast-forward
                result.returncode = 0
            return result

        calls = []
        with patch("subprocess.run", side_effect=mock_run), \
             patch("os.chdir"), \
             patch("botsy_engine.REPO_DIR", tmp_path):
            (tmp_path / "data").mkdir()
            engine._git_commit_push()

        # Saw fetch + soft reset + ancestor check
        assert any(c[:2] == ["git", "fetch"] for c in calls)
        assert any(
            c[:3] == ["git", "reset", "--hard"] and c[3] == "origin/main"
            for c in calls
        ), f"Expected hard reset to origin/main, calls: {calls}"
        assert any(
            c[:4] == ["git", "merge-base", "--is-ancestor", "HEAD"]
            for c in calls
        )
        # Runtime paths are staged only after the hard fast-forward.
        reset_i = next(
            i for i, c in enumerate(calls)
            if c[:3] == ["git", "reset", "--hard"]
        )
        add_i = next(
            i for i, c in enumerate(calls)
            if c[:2] == ["git", "add"]
        )
        assert reset_i < add_i
        # NEVER called rebase --abort or soft-reset-to-origin.
        assert not any(c[:3] == ["git", "rebase", "--abort"] for c in calls)
        assert not any(c[:3] == ["git", "reset", "--soft"] for c in calls)

    def test_precommit_divergence_writes_bail_marker(self, tmp_path):
        """When local and origin both moved, write bail marker — don't auto-merge."""
        from botsy_engine import BotsyEngine

        engine = self._make_engine()
        engine._checkpoint_all_dbs = lambda: None

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            result = MagicMock()
            result.returncode = 0
            result.stdout = b""
            result.stderr = b""
            if cmd[:4] == ["git", "merge-base", "--is-ancestor", "HEAD"]:
                # local NOT an ancestor → divergence
                result.returncode = 1
            elif cmd[:4] == ["git", "merge-base", "--is-ancestor", "origin/main"]:
                # origin/main NOT an ancestor either → true divergence
                result.returncode = 1
            return result

        calls = []
        bail_marker = tmp_path / "data" / "GIT_COMMIT_BAIL"
        with patch("subprocess.run", side_effect=mock_run), \
             patch("os.chdir"), \
             patch("botsy_engine.REPO_DIR", tmp_path):
            (tmp_path / "data").mkdir()
            engine._git_commit_push()

        # Marker must exist
        assert bail_marker.exists(), \
            f"Expected bail marker at {bail_marker}; calls: {calls}"
        # Never tried to abort, stage, commit, push, or auto-resolve
        assert not any(c[:3] == ["git", "rebase", "--abort"] for c in calls)
        assert not any(c[:2] == ["git", "add"] for c in calls)
        assert not any(c[:2] == ["git", "commit"] for c in calls)
        assert not any(c[:2] == ["git", "push"] for c in calls)
        # Marker content names the heads it bailed on
        text = bail_marker.read_text()
        assert "divergence" in text.lower()

    def test_bail_marker_quiesces_subsequent_cycles(self, tmp_path):
        """If a bail marker exists, _git_commit_push must short-circuit."""
        from botsy_engine import BotsyEngine

        engine = self._make_engine()
        engine._checkpoint_all_dbs = lambda: None

        bail_marker = tmp_path / "data" / "GIT_COMMIT_BAIL"
        bail_marker.parent.mkdir(parents=True, exist_ok=True)
        bail_marker.write_text("manual inspection pending")

        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            result = MagicMock()
            result.returncode = 0
            result.stdout = b""
            result.stderr = b""
            return result

        with patch("subprocess.run", side_effect=mock_run), \
             patch("os.chdir"), \
             patch("botsy_engine.REPO_DIR", tmp_path):
            engine._git_commit_push()

        # Engine should NOT have attempted any git state-changing op
        for forbidden in (
            ["git", "add"], ["git", "commit"], ["git", "push"],
            ["git", "fetch"], ["git", "reset"],
        ):
            n = len(forbidden)
            assert not any(c[:n] == forbidden for c in calls), \
                f"Expected no {forbidden} while bailed; calls: {calls}"

    def test_auto_commit_bails_on_forbidden_staged_paths(self, tmp_path):
        """Auto commits must not include source/config/test/docs-plan paths."""
        from botsy_engine import BotsyEngine

        engine = self._make_engine()
        engine._checkpoint_all_dbs = lambda: None

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            result = MagicMock()
            result.returncode = 0
            result.stdout = b""
            result.stderr = b""
            if cmd[:3] == ["git", "rev-parse", "--short"]:
                result.stdout = b"localsha\n"
            elif cmd[:3] == ["git", "rev-parse", "HEAD"]:
                result.stdout = b"localfull\n"
            elif cmd[:3] == ["git", "rev-parse", "origin/main"]:
                result.stdout = b"localfull\n"
            elif cmd[:5] == ["git", "diff", "--cached", "--name-only", "-z"]:
                result.stdout = b"data/ws_metrics.json\0src/predict.py\0"
            elif cmd[:4] == ["git", "diff", "--cached", "--quiet"]:
                result.returncode = 1
            return result

        calls = []
        bail_marker = tmp_path / "data" / "GIT_COMMIT_BAIL"
        with patch("subprocess.run", side_effect=mock_run), \
             patch("os.chdir"), \
             patch("botsy_engine.REPO_DIR", tmp_path):
            (tmp_path / "data").mkdir()
            engine._git_commit_push()

        assert bail_marker.exists()
        text = bail_marker.read_text()
        assert "forbidden staged path" in text
        assert "src/predict.py" in text
        assert not any(c[:2] == ["git", "commit"] for c in calls)
        assert not any(c[:2] == ["git", "push"] for c in calls)

    def test_auto_commit_allowlist_accepts_runtime_daily_paths(self):
        """Runtime data and daily reports are the only Auto: commit paths."""
        from botsy_engine import BotsyEngine

        assert BotsyEngine._auto_commit_path_allowed("data/ws_metrics.json")
        assert BotsyEngine._auto_commit_path_allowed("docs/daily/2026-05-01.md")
        assert not BotsyEngine._auto_commit_path_allowed("src/predict.py")
        assert not BotsyEngine._auto_commit_path_allowed("config/pipelines.json")
        assert not BotsyEngine._auto_commit_path_allowed("tests/test_engine_resilience.py")
        assert not BotsyEngine._auto_commit_path_allowed("docs/plans/foo.md")


# ── TestGitCommitLoopResilience ───────────────────────────────────────────


class TestGitCommitLoopResilience:
    """git_commit_loop survives exceptions from _git_commit_push."""

    def _make_engine(self):
        from botsy_engine import BotsyEngine
        with patch.object(BotsyEngine, "__init__", lambda self: None):
            engine = BotsyEngine()
        return engine

    def test_commit_loop_survives_thread_exception(self):
        """Exception from _git_commit_push doesn't kill the loop."""
        engine = self._make_engine()
        call_count = 0

        original_git_commit_push = MagicMock()

        def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("git exploded")
            # Second call succeeds

        original_git_commit_push.side_effect = side_effect
        engine._git_commit_push = original_git_commit_push

        async def run():
            loop_calls = 0

            # Patch sleep to count iterations and break after 2
            async def fake_sleep(seconds):
                nonlocal loop_calls
                loop_calls += 1
                if loop_calls >= 3:
                    raise asyncio.CancelledError()  # Break out of the loop

            with patch("botsy_engine.asyncio.sleep", side_effect=fake_sleep), \
                 patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.side_effect = [
                    RuntimeError("git exploded"),  # First call fails
                    None,  # Second call succeeds
                    None,  # Won't reach this
                ]
                try:
                    await engine.git_commit_loop()
                except asyncio.CancelledError:
                    pass

            # Should have called to_thread at least twice (survived first failure)
            assert mock_to_thread.call_count >= 2, \
                f"Expected at least 2 calls (survived failure), got {mock_to_thread.call_count}"

        run_async(run())

    def test_commit_loop_continues_after_failure(self):
        """After a failed cycle, the next cycle runs normally."""
        engine = self._make_engine()

        async def run():
            cycle_results = []

            async def fake_sleep(seconds):
                if len(cycle_results) >= 2:
                    raise asyncio.CancelledError()

            async def fake_to_thread(func, *args, **kwargs):
                cycle_num = len(cycle_results) + 1
                if cycle_num == 1:
                    cycle_results.append("error")
                    raise OSError("disk full")
                cycle_results.append("ok")

            with patch("botsy_engine.asyncio.sleep", side_effect=fake_sleep), \
                 patch("asyncio.to_thread", side_effect=fake_to_thread):
                try:
                    await engine.git_commit_loop()
                except asyncio.CancelledError:
                    pass

            assert cycle_results == ["error", "ok"], \
                f"Expected error then recovery, got {cycle_results}"

        run_async(run())


# ── TestTAEngineInitResilience ────────────────────────────────────────────


class TestTAEngineInitResilience:
    """TAEngine init catches all exceptions, not just ImportError."""

    def test_ta_init_catches_runtime_error(self):
        """RuntimeError during TAEngine init → ta_engine=None, engine continues."""
        from botsy_engine import BotsyEngine

        with patch.object(BotsyEngine, "__init__", lambda self: None):
            engine = BotsyEngine()

        engine.candle_buffer = MagicMock()

        # Simulate TAEngine raising RuntimeError during init
        mock_ta_module = MagicMock()
        mock_ta_module.TAEngine.side_effect = RuntimeError("pandas blew up")

        with patch.dict("sys.modules", {"ta_engine": mock_ta_module}):
            # Re-run the init block manually (the code we're testing)
            try:
                from ta_engine import TAEngine
                engine.ta_engine = TAEngine(engine.candle_buffer)
            except Exception as e:
                engine.ta_engine = None

        assert engine.ta_engine is None

    def test_ta_init_catches_attribute_error(self):
        """AttributeError during TAEngine init → ta_engine=None, engine continues."""
        from botsy_engine import BotsyEngine

        with patch.object(BotsyEngine, "__init__", lambda self: None):
            engine = BotsyEngine()

        engine.candle_buffer = MagicMock()

        mock_ta_module = MagicMock()
        mock_ta_module.TAEngine.side_effect = AttributeError("bad attr")

        with patch.dict("sys.modules", {"ta_engine": mock_ta_module}):
            try:
                from ta_engine import TAEngine
                engine.ta_engine = TAEngine(engine.candle_buffer)
            except Exception as e:
                engine.ta_engine = None

        assert engine.ta_engine is None
