# Postmortem: SIGALRM Thread-Safety Bug — 2026-04-06

## TL;DR

A `signal.SIGALRM` timeout guard around CLOB order submission only
works from the main thread. The VPS engine dispatches pipelines off
the main thread, so every qualifying BTC 5m bet for ~20 minutes
failed with `ValueError: signal only works in main thread of the
main interpreter`. The dashboard showed all breakers green; the
engine cycle logs showed `[btc_5m] OK`; nothing screamed.

**Impact:** 4 dropped bets that all would have won. Counterfactual
P&L ≈ **+$97** of missed profit in a single 20-minute window.

## Timeline (UTC)

| Time | Event |
|---|---|
| ~22:55 | Cycle places first DOWN bet, `signal.signal()` raises, order logged `FAILED` |
| 23:00 | Same failure |
| 23:05 | Same failure |
| 23:10 | Same failure |
| 23:15 | User noticed the `FAILED signal only works in main thread of the` rows on dashboard |
| ~23:18 | Root cause identified in `src/trade.py:586,632` |
| ~23:20 | Fix pushed (`ThreadPoolExecutor.result(timeout=...)`) and deployed; engine restarted |
| 23:25 | First bet through hardened path — order #74, filled clean, won +$19.35 |
| 23:55 | Order #75 filled clean, lost −$25 (signal loss, not execution) |

## Root cause

`src/trade.py::_submit_limit_order` and `_submit_fok_order` both
wrapped the CLOB API call in a SIGALRM-based timeout:

```python
old_handler = _signal.signal(_signal.SIGALRM, _timeout_handler)
_signal.alarm(API_TIMEOUT_SUBMIT)
try:
    response = client.create_and_post_order(order_args)
finally:
    _signal.alarm(0)
    _signal.signal(_signal.SIGALRM, old_handler)
```

Python's `signal` module only operates on the main thread. The VPS
engine (`botsy_engine.py`) uses `asyncio` and dispatches pipelines
via worker threads. On every live order attempt, `signal.signal()`
raised `ValueError: signal only works in main thread of the main
interpreter` before the order ever reached the CLOB.

The try/finally caught it indirectly — the exception bubbled up out
of `_submit_*` and was logged as `FAILED: signal only works in main
thread of the` (truncated by the log formatter). The rest of the
pipeline continued normally, so the cycle still reported `[btc_5m] OK`.

## Fix

Replaced both call sites with `concurrent.futures.ThreadPoolExecutor`
timeouts:

```python
with ThreadPoolExecutor(max_workers=1) as _ex:
    _fut = _ex.submit(client.create_and_post_order, order_args)
    try:
        response = _fut.result(timeout=API_TIMEOUT_SUBMIT)
    except _FTimeout:
        raise TimeoutError(...)
```

Thread-safe from any calling context. Same timeout semantics.

- Commit: `8fe0b4ba` — "Fix: use ThreadPoolExecutor timeout in CLOB submit (thread-safe)"
- Tests: `tests/test_trade.py` — 45/45 green

## Counterfactual

All 4 failed orders were DOWN bets on the same BTC momentum streak.
All 4 markets resolved DOWN.

| Order | Window | Dir | Size | Limit | Outcome | Would-have P&L |
|---|---|---|---|---|---|---|
| 70 | 6:55–7:00PM ET | DOWN | $25 | 0.51 | DOWN ✓ | +$24.02 |
| 71 | 7:00–7:05PM ET | DOWN | $25 | 0.50 | DOWN ✓ | +$25.00 |
| 72 | 7:05–7:10PM ET | DOWN | $25 | 0.49 | DOWN ✓ | +$26.02 |
| 73 | 7:10–7:15PM ET | DOWN | $12.94 | 0.37 | DOWN ✓ | +$22.03 |
| | | | | | **Gross** | **≈ +$97** |

The signal was hot. The momentum strategy correctly caught a
−8-candle streak and would have ridden it for 4 consecutive wins.
The next cycle (order #74) fired on the same streak through the
fixed code and booked +$19.35. The cycle after that (#75) was the
expected reversal loss on a streak=+5 bet.

**What happened:** −$5.65 net (1W, 1L)
**What should have happened:** ≈ +$92 net (5W, 1L)
**Delta cost of the bug in one 20-minute window:** ≈ $97

## Lessons

### 1. Silent failure is the most expensive class of bug

The entire system was green from the outside. `mode=LIVE`,
`kill_switch=OFF`, `consecutive_losses=0/5`, `[btc_5m] OK` on every
cycle. There was no anomaly, no retry, no alert. Only the dashboard
"Recent Bets" table showed the `FAILED` status, and only because
the user happened to look at it.

Bugs that are loud are cheap. Bugs that are invisible cost money
proportional to how long they stay invisible times how strong your
signal happens to be during that window. Tonight the signal was
strong; the cost was steep.

### 2. The runtime state contract was built for exactly this

The state contract shipped in the same session now includes a
`SILENT FAILURE` check:

```
if qualifying_signals_today >= 3
   and orders_today == 0
   and trading_enabled:
    warnings.append("SILENT FAILURE: ...")
```

Wired into `pipeline_integrity.check_system_state_health`. Under
the post-fix system, this exact scenario (4 qualifying signals in
20 minutes, 0 orders placed, trading enabled) would have fired a
FAIL status on the *first* cycle and shown a red banner on the
dashboard breaker section within ~5 minutes.

The class of bug is structurally harder to hide now. Not impossible —
but harder. The cost of $97 in 20 minutes is the number we should
point to next time someone asks "is the hardening work worth it?"

### 3. Thread-safety is a contract, not a library feature

`signal.signal()` doesn't document its main-thread requirement
loudly, and Python doesn't warn when you violate it outside the
main thread until the call itself raises. Any primitive that touches
process-level state (signals, `os.chdir`, some `gc` hooks) is a
hidden coupling between "where this code runs" and "whether it
works". The async engine introduced the coupling months ago; the
trade path introduced SIGALRM later; nobody caught the interaction
because neither side knew about the other.

**Rule of thumb going forward:** in any code path that can be
dispatched from an async worker, avoid process-global primitives.
Use `concurrent.futures` timeouts, context managers, or asyncio-
native patterns. Flag any `import signal` in PR review.

### 4. Pre-emptive fill-strategy optimization was a distraction

Half of `docs/specs/stochastic/` proposes making FOK smarter:
dynamic slippage caps, stochastic entry timing, IOC retry logic.
Tonight's evidence says the base FOK strategy is fine — **when it
runs**. In 2 real trades and 4 counterfactuals, FOK would have
filled 6 for 6 at the quoted ask with ≤2.5¢ slippage. The fill
problem wasn't a strategy problem; it was a "the wrapper around
the strategy throws a ValueError before the CLOB ever sees the
request" problem.

This is exactly the principle CLAUDE.md already states in a
different form: *"before you optimize a mechanism, verify it can
actually run."* The fill specs get reviewed only after ~50 bets
accumulate through the hardened pipeline so we have a real baseline
to measure against.

## Action items

- [x] Fix the SIGALRM bug (commit `8fe0b4ba`)
- [x] Ship runtime state contract with silent-failure detection
- [x] Update `docs/ops/ENGINEERING_LESSONS.md` with the thread-safety rule (follow-up)
- [ ] Add a regression test: `_submit_limit_order` must work from a worker thread (mocked CLOB client, thread pool executor invocation, assert no ValueError)
- [ ] PR-review checklist: flag any new `import signal` in trade/execution code
- [ ] Wait for 50 bets through hardened pipeline before touching any fill-strategy spec

## References

- Fix commit: `8fe0b4ba`
- Runtime state contract plan: `docs/plans/runtime-state-contract.md`
- Fill-problem specs (unchanged, to reassess post-baseline): `docs/specs/stochastic/`
- Dashboard/engine divergence incident (same evening): incident resolved via state contract migration
