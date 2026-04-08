> **NOTE (2026-04-08):** GH Pages dashboards retired. Canonical view is local Streamlit (`streamlit run tools/diag.py`). Dashboard mentions below are historical.

# Plan: Runtime State Contract

## Context

This session exposed a pattern that no existing plan addresses: **state duplication**. The same runtime fact (`consecutive_losses`, `trading_enabled`, `breaker_tripped`, `daily_loss`) is re-derived in multiple places with subtly different logic. When any two diverge, the bot silently lies to itself.

### Evidence

**Today's incident (2026-04-06):**
- `trade.py::_check_consecutive_losses` — no date filter → returned 5 → breaker tripped → blocked all trades
- `dashboard_v2/data.py::get_breaker_status` — `WHERE settled_at LIKE 'today%'` → returned 0 → dashboard showed green
- Result: BTC 5m deadlocked for 30+ hours while the dashboard cheerfully showed "0/5 Consec Losses" ✔

**Historical pattern (same root cause, different symptoms):**
- Incident #66: `trade.TRADING_ENABLED` global vs `pipeline_control.is_pipeline_live()` — two sources of truth for "are we trading?"
- `ps aux` vs `systemctl` vs PID file — three answers to "is the engine alive?"
- `logs/loop.log [btc_5m] OK` — says OK even when no trades executed against qualifying signals

### The disease vs the symptom

The existing plans (`pipeline-isolation-unification.md`, `refactoring-plan.md`) treat **code duplication** as the problem. Today proved it's only a symptom. The real disease is **state duplication** — the same fact computed by independent implementations.

Code duplication is easy to detect (grep, AST). State duplication is invisible: two functions that look completely different can claim to answer the same question with different answers, and nothing fails until money is lost.

### Why this matters for event-driven execution

The next planned feature (`event-driven-execution-plan.md`) adds a `ReactiveExecutor` that will need to answer: "can I trade right now?" If we ship it without a state contract, it becomes a **third** place that re-derives `is_pipeline_live`, `consecutive_losses`, `daily_loss`, and `kill_switch` — guaranteed to drift from both the engine and the dashboard. This plan must land **before** event-driven execution.

## Frozen File Check

🚫 FAIL — Requires changes to:
- `src/trade.py` (not frozen but core) — `should_trade()` rewritten as thin wrapper
- `src/ci_run.py` (frozen) — no changes; it already delegates to `polymarket_pipeline.py`
- `src/predict.py` (frozen) — no changes; prediction logic is untouched

Core changes are all in new or non-frozen files. Frozen file BTC pipeline is not affected in signal logic — only the downstream "can we trade?" answer gets a new implementation path.

## Prerequisites

- [x] Pipeline isolation landed (pipeline_name threaded through execute_trades)
- [x] Today's breaker deadlock fixed (8h cooldown, commit `76ac5473`)
- [ ] Runtime state contract (this plan)
- [ ] Event-driven execution plan (depends on this)

## Backward — What Breaks?

### Affected Code
- `src/trade.py::should_trade()` — rewritten to call `get_system_state()`
- `src/trade.py::_check_consecutive_losses()` — deleted, moved to `system_state.py`
- `src/trade.py::get_trading_summary()` — rewritten as thin wrapper
- `src/dashboard_v2/data.py::get_breaker_status()` — rewritten as thin wrapper (no more divergent SQL)
- `src/daily_report.py` — reads from `get_system_state()` instead of re-querying DB
- `src/integrity_check.py` (or wherever `run_integrity_checks` lives) — augmented with silent-failure check

### Affected Tests
- `tests/test_trade.py::TestShouldTrade` — still valid, thin wrapper keeps same contract
- New file: `tests/test_system_state.py` — ~15 tests for the contract itself
- New file: `tests/test_state_transitions.py` — temporal tests (the missing layer)
- New file: `tests/test_state_invariants.py` — AST scan for duplicate derivations

### Rollback Plan
1. `system_state.py` is additive; thin wrappers preserve existing contracts
2. If something breaks, revert the wrappers to inline logic (15-minute revert)
3. Existing tests act as regression gate — if they break, the contract is wrong

## Present — The Plan

### Module: `src/system_state.py`

One dataclass, one function. Every caller that needs runtime state imports from here and only here.

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional

@dataclass(frozen=True)
class SystemState:
    """Authoritative runtime state snapshot for a pipeline. Immutable."""

    pipeline_name: str
    computed_at: datetime

    # Trading mode
    trading_enabled: bool          # from pipeline_control.is_pipeline_live
    kill_switch: bool              # from env/file check
    mode: str                      # "LIVE" | "PAPER" — derived, for display

    # Financial state
    daily_loss: float              # today's realized losses
    daily_loss_limit: float
    total_pnl_today: float

    # Breaker state
    consecutive_losses: int
    consecutive_loss_max: int
    breaker_cooldown_hours: int
    seconds_since_last_settled: Optional[float]

    # Activity state
    last_settled_at: Optional[datetime]
    last_prediction_at: Optional[datetime]
    last_qualifying_signal_at: Optional[datetime]  # conv >= min
    orders_today: int
    qualifying_signals_today: int

    # Final answers — the ONLY fields callers should branch on
    can_trade: bool
    blockers: List[str]            # human-readable reasons if can_trade is False
    is_healthy: bool               # higher bar than can_trade — checks silent failures
    health_warnings: List[str]     # non-blocking but concerning


def get_system_state(db, pipeline_name: str) -> SystemState:
    """The ONE authoritative state function. No caller is allowed to
    recompute any of these fields from the DB independently."""
    ...


def pipeline_is_healthy(state: SystemState) -> tuple[bool, List[str]]:
    """Health check beyond 'cycle ran without exception'. Returns
    (healthy, warnings). Warnings feed the daily report and dashboard."""
    warnings = []

    # Silent failure: qualifying signals but no orders
    if (state.qualifying_signals_today >= 3
        and state.orders_today == 0
        and state.trading_enabled):
        warnings.append(
            f"SILENT FAILURE: {state.qualifying_signals_today} qualifying "
            f"signals today but 0 orders placed")

    # Breaker lockout
    if state.consecutive_losses >= state.consecutive_loss_max:
        if state.seconds_since_last_settled and state.seconds_since_last_settled > 6 * 3600:
            warnings.append(
                f"BREAKER LOCKED: {state.consecutive_losses} losses, "
                f"{state.seconds_since_last_settled / 3600:.1f}h since last trade")

    # Stale predictions
    if state.last_prediction_at:
        age = (state.computed_at - state.last_prediction_at).total_seconds()
        if age > 15 * 60:
            warnings.append(f"STALE: last prediction was {age/60:.0f}m ago")

    return (len(warnings) == 0, warnings)
```

### Migration of existing callers

| Caller | Before | After |
|--------|--------|-------|
| `trade.py::should_trade()` | 40 lines of DB queries + logic | `state = get_system_state(db, pipeline_name); return state.can_trade, state.blockers[0] if state.blockers else "ok"` |
| `trade.py::get_trading_summary()` | 50 lines, its own SQL | `state = get_system_state(db, pipeline_name); return {...state fields...}` |
| `dashboard_v2/data.py::get_breaker_status()` | 60 lines of its own SQL (the lying one) | `state = get_system_state(db, pipeline_name); return {...}` |
| `daily_report.py` | Direct DB queries for daily loss, breaker status | Read from `get_system_state()` |
| `integrity_check.py` | 6 narrow checks | Add `check_silent_failure` that uses `pipeline_is_healthy()` |

After migration: **zero other places in the codebase query `orders.pnl` or `is_pipeline_live` or `daily_loss` directly.**

## Implementation Steps

### Step 1: Write the contract tests first (TDD)
**Files:** `tests/test_system_state.py` (NEW)
**Tests (~15):**
- `test_get_system_state_returns_frozen_dataclass` — immutability check
- `test_trading_enabled_matches_pipeline_control` — source of truth
- `test_consecutive_losses_uses_trade_py_logic` — same answer as the existing `_check_consecutive_losses`
- `test_consecutive_losses_auto_resets_after_8h` — incident regression
- `test_kill_switch_file_detected`
- `test_kill_switch_env_detected`
- `test_daily_loss_only_today` — date window correct
- `test_can_trade_false_when_breaker_tripped`
- `test_can_trade_false_when_kill_switch`
- `test_can_trade_false_when_daily_loss_exceeded`
- `test_blockers_list_human_readable`
- `test_qualifying_signals_today_counts_conv_ge_3`
- `test_seconds_since_last_settled_computed_correctly`
- `test_no_settled_orders_returns_none_not_error`
- `test_per_pipeline_isolation` — BTC 5m state independent of ETH 5m state

**Commit:** `Add system_state contract tests (failing)`

### Step 2: Implement `src/system_state.py`
**Files:** `src/system_state.py` (NEW)
**Change:** Implement `SystemState` dataclass + `get_system_state()` + `pipeline_is_healthy()`. All reads from DB happen here. No mutation.
**Commit:** `Add runtime state contract: single source of truth for pipeline state`

### Step 3: State-transition test layer
**Files:** `tests/test_state_transitions.py` (NEW)
**Change:** Temporal tests that advance `now()` and re-check state. The test layer that would have caught today's deadlock.

```python
def test_breaker_tripped_then_silence_auto_unlocks():
    """5 losses at T0 → state.can_trade=False.
       9 hours later (no trades) → state.can_trade=True (auto-reset)."""

def test_breaker_tripped_then_silence_surfaces_health_warning():
    """5 losses + 6h silence → is_healthy=False with
       'BREAKER LOCKED' warning (before auto-reset kicks in)."""

def test_qualifying_signals_without_orders_is_unhealthy():
    """3 conv=4 predictions + 0 orders → is_healthy=False
       with 'SILENT FAILURE' warning."""

def test_stale_predictions_flagged():
    """Last prediction > 15m ago → health_warnings includes 'STALE'."""

def test_kill_switch_toggle_surfaces_immediately():
    """State at T0 with no kill switch → can_trade=True.
       Touch KILL_SWITCH file → state at T0+1s → can_trade=False."""
```

**Commit:** `Add state-transition test layer`

### Step 4: Migrate callers
**Files:** `src/trade.py`, `src/dashboard_v2/data.py`, `src/daily_report.py`, `src/integrity_check.py` (if separate)
**Change:** Each caller becomes a thin wrapper around `get_system_state()`. Delete the duplicate SQL. Ensure all existing tests still pass — they should, because the contract is preserved.
**Commit:** `Migrate should_trade/get_breaker_status/daily_report to system_state contract`

### Step 5: Silent-failure integrity check
**Files:** `src/integrity_check.py` (or wherever checks live)
**Change:** Add `check_silent_failure(state)` that reports when `qualifying_signals_today >= 3 AND orders_today == 0 AND trading_enabled`. Wire into the existing check pipeline. Surface in daily report header: `"BTC 5m: ❌ UNHEALTHY — 4 qualifying signals, 0 orders"`.
**Commit:** `Add silent failure integrity check`

### Step 6: AST invariant test
**Files:** `tests/test_state_invariants.py` (NEW)
**Change:** AST scan of `src/` (excluding `system_state.py` and test files):

```python
FORBIDDEN_PATTERNS = {
    # Nobody outside system_state.py may compute these
    "consecutive_loss": ["SELECT pnl FROM orders"],
    "daily_loss":       ["SUM(CASE WHEN pnl < 0"],
    "trading_enabled":  ["is_pipeline_live("],  # except in system_state.py
}

def test_no_duplicate_state_derivation():
    """Fail CI if any file outside system_state.py re-derives
    breaker/loss/trading-mode state from raw DB queries."""
```

This catches a future contributor (or AI assistant) who writes new code that bypasses the contract. The test FAILS loudly with: `src/foo.py:42 computes consecutive_loss from DB; use system_state.get_system_state() instead.`

**Commit:** `Add AST invariant test to prevent state duplication regression`

### Step 7: Dashboard surface
**Files:** `src/dashboard_v2/sections.py`
**Change:** Display `state.is_healthy` status and `state.health_warnings` in the dashboard header. Red banner when unhealthy. This is where the "silent failure" becomes visible.
**Commit:** `Surface health status and warnings in dashboard header`

## Test Plan

- [ ] Step 1: ~15 contract tests written, all failing
- [ ] Step 2: Contract tests passing
- [ ] Step 3: ~6 state-transition tests, all passing
- [ ] Step 4: All existing tests (`pytest tests/ -v`) still pass after migration
- [ ] Step 5: New silent-failure integrity check has its own test
- [ ] Step 6: AST invariant test passes on current codebase, fails deliberately when a duplicate is planted
- [ ] Step 7: Dashboard renders without errors in a test cycle

## Validation Plan

### Shadow Phase
Not applicable — this is pure refactoring. Behavior preserved by contract tests.

### Live Phase
- Deploy to VPS, verify:
  - `logs/loop.log` still shows `[btc_5m] OK` on healthy cycles
  - Dashboard now shows correct breaker status (matches engine)
  - Daily report header shows health status
- Plant a synthetic test: set consec_losses to 5 with recent timestamps → verify dashboard AND engine AND daily report all agree within the next cycle
- Monitor 24h: any `SILENT FAILURE` warning fires? investigate each.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Contract tests don't match existing behavior | Medium | Medium | TDD Step 1 forces explicit contract; diff against current outputs on real DB |
| Migration breaks existing tests | Low | Medium | Thin wrappers preserve return types; run full suite at each step |
| AST invariant is too strict | Medium | Low | Allowlist exceptions (e.g., migration scripts); exclude `tests/` |
| `get_system_state()` becomes a performance hotspot | Low | Low | It's the same 3-5 queries we already run; cache per-cycle if needed |
| Frozen file interaction | Low | Low | No signal logic touched; frozen files only call `execute_trades()` which internally calls the contract |

## Estimated Timeline

- Step 1 (contract tests): 1 hour
- Step 2 (implementation): 1.5 hours
- Step 3 (transition tests): 1 hour
- Step 4 (migrate callers): 1.5 hours
- Step 5 (silent failure check): 30 min
- Step 6 (AST invariant): 45 min
- Step 7 (dashboard surface): 30 min
- **Total: ~6.5 hours**

No data collection needed — pure refactoring. Ships in one session.

## What This Does NOT Do

- Does NOT change signal logic (streak detection, regime filter, conviction scoring)
- Does NOT change bet sizing
- Does NOT change prediction or trade execution logic — only **reads** are unified
- Does NOT remove `TRADING_ENABLED` from `trade.py` — it remains as legacy fallback
- Does NOT touch Kalshi (custom structure; migrate in a follow-up)
- Does NOT add new trading features — all new features (reactive executor) depend on this landing first

## Dependency Chain

```
┌──────────────────────────────────────┐
│ Pipeline Isolation & Unification     │  ← COMPLETE (2026-04-06)
│ (pipeline_name threading)            │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ Runtime State Contract (THIS PLAN)   │  ← NEXT
│ (single source of truth)             │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ Event-Driven Trade Execution         │  ← BLOCKED on this
│ (reactive executor uses contract)    │
└──────────────────────────────────────┘
```

## Success Criteria

1. Zero other places in `src/` query `orders.pnl` directly (AST test enforces)
2. `pytest tests/ -v` green with the new test layers
3. Dashboard and engine agree on consecutive_losses within the same second
4. Daily report header flags any pipeline where signals fired but no orders placed
5. Today's incident (breaker deadlock + dashboard lie) is structurally impossible to ship again
