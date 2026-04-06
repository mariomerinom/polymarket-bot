"""AST invariant tests — prevent state duplication regression.

Scans src/ for code patterns that would duplicate runtime state
derivation outside system_state.py. If this test fails, a caller has
started re-deriving breaker/loss/trading-mode state with its own SQL
instead of calling get_system_state().

This is the test that would have prevented the 2026-04-06 incident.
"""

from pathlib import Path

SRC = Path(__file__).parent.parent / "src"

# Modules that are allowed to derive state directly. Everything else
# must go through system_state.get_system_state().
ALLOWED_FILES = {
    "system_state.py",          # the contract itself
    "bybit_trade.py",           # legacy — tracked for migration
    "anomaly.py",               # anomaly detection has its own window logic
    "trade.py",                 # back-compat shim + execution path
    "pipeline_integrity.py",    # wraps the contract
    "dashboard_v2/data.py",     # wraps the contract; legacy bybit path allowed
}

# Patterns that signal "I'm computing runtime state from raw DB queries".
FORBIDDEN_SNIPPETS = {
    "consecutive_loss": [
        "SELECT pnl FROM orders",
        "SELECT pnl FROM positions",
    ],
    "daily_loss_sql": [
        "SUM(CASE WHEN pnl < 0",
    ],
}


def _rel(p: Path) -> str:
    return str(p.relative_to(SRC)).replace("\\", "/")


def _iter_python_files():
    for p in SRC.rglob("*.py"):
        if any(part.startswith("__") for part in p.parts):
            continue
        yield p


def test_no_duplicate_consecutive_loss_derivation():
    """Only allowlisted modules may compute consecutive losses from DB."""
    violators = []
    for p in _iter_python_files():
        rel = _rel(p)
        if rel in ALLOWED_FILES:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for snippet in FORBIDDEN_SNIPPETS["consecutive_loss"]:
            if snippet in text:
                violators.append(f"{rel}: contains {snippet!r}")

    assert not violators, (
        "State duplication detected — these files compute consecutive "
        "loss state from raw DB queries instead of using "
        "system_state.get_system_state():\n  "
        + "\n  ".join(violators)
    )


def test_no_duplicate_daily_loss_derivation():
    """Only allowlisted modules may compute daily loss from DB."""
    violators = []
    for p in _iter_python_files():
        rel = _rel(p)
        if rel in ALLOWED_FILES:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for snippet in FORBIDDEN_SNIPPETS["daily_loss_sql"]:
            if snippet in text:
                violators.append(f"{rel}: contains {snippet!r}")

    assert not violators, (
        "State duplication detected — these files compute daily_loss "
        "from raw SQL instead of using system_state.get_system_state():\n  "
        + "\n  ".join(violators)
    )


def test_allowlist_files_actually_exist():
    """Guard: if we allowlist a file that's been renamed/deleted, fail
    loudly so the allowlist doesn't silently stop protecting us."""
    missing = []
    for f in ALLOWED_FILES:
        if not (SRC / f).exists():
            missing.append(f)
    assert not missing, (
        f"Allowlisted files no longer exist: {missing}. "
        "Update ALLOWED_FILES in test_state_invariants.py."
    )
