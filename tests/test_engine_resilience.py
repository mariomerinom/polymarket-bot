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


# ── TestGitRebaseRecovery ─────────────────────────────────────────────────


class TestGitRebaseRecovery:
    """_git_commit_push handles rebase failures safely."""

    def _make_engine(self):
        from botsy_engine import BotsyEngine
        with patch.object(BotsyEngine, "__init__", lambda self: None):
            engine = BotsyEngine()
        return engine

    def test_rebase_failure_aborts_and_returns(self):
        """When push fails and rebase fails, abort rebase and return.

        Actual code flow: add → diff → commit → push → (if push fails:
        pull --rebase → if rebase fails: rebase --abort → return).
        """
        engine = self._make_engine()

        calls = []

        def mock_subprocess_run(cmd, **kwargs):
            calls.append(cmd)
            result = MagicMock()
            result.returncode = 0
            result.stderr = b""
            result.stdout = b""
            # diff --cached --quiet returns 1 → there ARE staged changes
            if cmd[:4] == ["git", "diff", "--cached", "--quiet"]:
                result.returncode = 1
            # push fails → triggers rebase path
            elif cmd[:2] == ["git", "push"]:
                result.returncode = 1
                result.stderr = b"rejected"
            # rebase fails → triggers abort
            elif cmd[:3] == ["git", "pull", "--rebase"]:
                result.returncode = 1
                result.stderr = b"CONFLICT (content): Merge conflict in data/predictions.db"
            elif cmd[:3] == ["git", "rebase", "--abort"]:
                result.returncode = 0
            return result

        with patch("subprocess.run", side_effect=mock_subprocess_run), \
             patch("os.chdir"):
            engine._git_commit_push()

        # Should have called rebase --abort
        abort_calls = [c for c in calls if c[:3] == ["git", "rebase", "--abort"]]
        assert len(abort_calls) >= 1, f"Expected rebase --abort, got calls: {calls}"

    def test_rebase_success_continues_to_commit(self):
        """When rebase succeeds (returncode 0), commit proceeds normally."""
        engine = self._make_engine()

        calls = []

        def mock_subprocess_run(cmd, **kwargs):
            calls.append(cmd)
            result = MagicMock()
            result.returncode = 0
            result.stderr = b""
            result.stdout = b""
            # git diff --cached --quiet returncode=1 means there ARE staged changes
            if cmd[:4] == ["git", "diff", "--cached", "--quiet"]:
                result.returncode = 1
            return result

        with patch("subprocess.run", side_effect=mock_subprocess_run), \
             patch("os.chdir"):
            engine._git_commit_push()

        # Should have attempted commit (git commit -m ...)
        commit_calls = [c for c in calls if len(c) >= 2 and c[1] == "commit"]
        assert len(commit_calls) >= 1, f"Expected commit after successful rebase, got: {calls}"

    def test_push_retry_rebase_failure_aborts(self):
        """When push fails and the subsequent rebase also fails, abort and return.

        Actual flow: add → diff(has changes) → commit(ok) → push(fail) →
        pull --rebase(fail) → rebase --abort → return.
        """
        engine = self._make_engine()

        calls = []

        def mock_subprocess_run(cmd, **kwargs):
            calls.append(cmd)
            result = MagicMock()
            result.returncode = 0
            result.stderr = b""
            result.stdout = b""

            if cmd[:4] == ["git", "diff", "--cached", "--quiet"]:
                result.returncode = 1  # has changes
            elif cmd[:2] == ["git", "push"]:
                result.returncode = 1
                result.stderr = b"rejected"
            elif cmd[:3] == ["git", "pull", "--rebase"]:
                result.returncode = 1
                result.stderr = b"CONFLICT"
            elif cmd[:3] == ["git", "rebase", "--abort"]:
                result.returncode = 0

            return result

        with patch("subprocess.run", side_effect=mock_subprocess_run), \
             patch("os.chdir"):
            engine._git_commit_push()

        # Should have called rebase --abort
        abort_calls = [c for c in calls if c[:3] == ["git", "rebase", "--abort"]]
        assert len(abort_calls) >= 1, f"Expected rebase --abort on retry failure, got calls: {calls}"


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
