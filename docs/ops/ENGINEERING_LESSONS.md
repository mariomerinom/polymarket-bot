# Engineering Lessons Learned

**Purpose:** Agnostic scaffolding for getting a project operational, minimizing errors, and producing results. Extracted from a live autonomous system that runs 24/7, makes decisions, and tracks outcomes. Every lesson comes from something that broke or something that worked.

---

## 1. Establish a Single Source of Truth

**Problem:** When CI auto-commits every few minutes, local state drifts within seconds. Two people (or one person and a bot) looking at the same project see different numbers.

**What we learned:**
- Always pull before reading data. If the system writes to a shared store on every cycle, your local copy is stale by the time you look at it.
- Always push after making changes. A change that exists only locally doesn't exist.
- The deployed view (dashboard, API, production DB) is canonical. If a local query disagrees with the live system, the live system is right.

**Remediation:**
- Codified as the first rule in the project config: "pull before read, push after write."
- CI conflicts are expected, not exceptional. Always rebase before pushing. If the data file conflicts, code changes win — CI regenerates the data.

**Best practice:** Treat the repository as the single source of truth. Local machines are caches, not sources.

---

## 2. Test Data Providers from the Deployment Environment

**Incident:** Primary data API returned HTTP 451 (geo-blocked) from CI servers running on US IPs. The fallback API returned data at the wrong granularity with missing fields. The system ran "successfully" for 48 hours on garbage data.

**What went wrong:**
- The primary provider worked locally (developer machine) but was geo-blocked from CI (cloud datacenter)
- The fallback provider returned *something* — but at 6x the expected time granularity and with zero volume data
- No validation checked whether fallback data was *usable*, only whether it was *present*

**Remediation:**
- Replaced both providers with US-regulated alternatives that work from any IP
- Added data quality assertions: volume > 0, correct number of data points, expected time intervals
- Regression test: parse a known-good response and assert all required fields are present and valid

**Best practice:** Test every external dependency from the actual deployment environment, not just the developer's machine. Validate that fallback data is usable, not just non-empty.

---

## 3. Validate on Real Conditions, Not Simulations

**Incident:** A strategy backtested at 53% accuracy on synthetic data. When deployed against real market conditions, it hit 37% accuracy — losing $1,021 in 24 hours. The synthetic test data didn't reflect how the real environment had already priced in the signal.

**What went wrong:**
- Backtests used fabricated inputs where the key variable (market price) was centered at 50%
- In reality, the market had already moved to reflect the same pattern the strategy was trying to exploit
- The strategy was arriving late — "fading" a move the market had already faded
- Skip accuracy was artificially high (62.6%) because skips defaulted to the market price, mechanically matching outcomes

**Remediation:**
- Switched to paper trading: full logic runs, outcomes tracked, but no real capital at risk
- Established a gate: 200+ resolved observations in paper mode before deploying capital
- Discovered that inverting the strategy (riding momentum instead of fading it) produced 63% accuracy

**Best practice:** Synthetic backtests validate logic, not edge. Real-world validation (paper trading, shadow mode, A/B testing) must gate production deployment. Define explicit pass/fail criteria before starting.

---

## 4. When a Signal Fails, Inversion Can Reveal the True Edge

**What happened:** A "contrarian" signal (bet against streaks) consistently lost at 37%. The inverse — a "momentum" signal (bet with streaks) — hit 63%.

**The insight:** A reliably wrong signal is as valuable as a reliably right one. If your model is confidently predicting the wrong direction, the information is there — the sign is just flipped.

**Remediation:**
- Inverted the signal direction (2-line code change)
- Added a permanent guardrail in the project config: "The strategy is X. Do NOT revert to Y. Y was tried and failed at Z% accuracy."
- Renamed all functions, labels, and documentation to match the new direction — preventing a future contributor from "fixing" it back

**Best practice:** When something fails reliably, check the inverse before discarding. Document the failure prominently so no one re-introduces it.

---

## 5. Simple Rules Beat Complex Models on Noisy Data

**What we tried:**
- 32-feature ML model (gradient boosting + logistic regression, agreement gate)
- Result: 51.3% accuracy, failed calibration on 6/8 bins, +0.5% ROI

**What beat it:**
- 3-line rule: if streak ≥ 3 AND exhaustion signal present → trade
- Result: 58% accuracy, +14% ROI after adding one regime filter

**Why:**
- Too many features (32) for too few samples (500). Rule of thumb: need 10–50× samples per feature.
- High-frequency data is inherently noisy. Simple rules capture the signal; ML overfits the noise.
- A single well-chosen filter (regime detection: skip when autocorrelation < -0.15) removed 81 toxic trades and tripled the Sharpe ratio.

**Best practice:** Start with the simplest rule that captures the signal. Add complexity only when simple rules demonstrably fail, and only one variable at a time. One good filter is worth more than 32 features.

---

## 6. Testing is Insurance — One Test Per Incident

**Context:** Three production incidents in one week. $1,021 in losses, 12+ hours of CI downtime. After that, every incident got a regression test. No incident has recurred.

**Test layer architecture:**

| Layer | Purpose | When it catches problems |
|-------|---------|------------------------|
| **Smoke** | Imports load, basic I/O works | Immediately — broken syntax, deleted modules |
| **Unit** | Core logic produces correct outputs | Before deploy — logic regressions |
| **Regression** | Specific past incidents don't recur | Before deploy — known failure modes |
| **Integration** | Full pipeline runs end-to-end | After deploy — environment mismatches |

**Key patterns:**
- **Tests gate CI.** If any test fails, the pipeline stops. Broken code never reaches the production database.
- **One regression test per incident.** Not aspirational — mandatory. The test encodes the exact failure mode.
- **Test the contract, not the implementation.** Check that outputs have required fields, values are in valid ranges, and math is correct. Don't test internal variable names.

**Examples of tests that have paid for themselves:**
- "CI workflows do not reference deleted directories" — caught after a cleanup broke the pipeline for 12 hours
- "Winning predictions always produce positive P&L at any entry price" — caught inverted conviction scoring
- "Data provider responses contain volume > 0" — caught useless fallback data

**Best practice:** Don't write tests for coverage metrics. Write tests because something broke and you never want it to break again. The test suite is a living record of everything that went wrong.

---

## 7. CI/CD: Self-Rescheduling with Guard Rails

**Pattern:** The system needs to run a cycle every N minutes, indefinitely. Cloud CI cron jobs are unreliable (1–30 minute delays on free tiers). Solution: self-rescheduling via API dispatch.

```
Cycle completes → sleep N minutes → trigger next cycle via API
```

**Guard rails that matter:**
- **Max dispatches per day.** Without a cap, a bug in the trigger logic creates an infinite loop that burns through CI minutes. We cap at 300/day.
- **Cron fallback.** If the self-rescheduling chain breaks (API error, rate limit), a cron schedule restarts it. Belt and suspenders.
- **Isolated pipelines.** When adding a second pipeline (different cadence, different data), give it its own workflow, its own database, its own dispatch event. If pipeline B crashes, pipeline A is untouched.

**What went wrong without isolation:** A second pipeline wrote to the same database as the first. Predictions from different cadences contaminated each other. The dashboard showed blended data that didn't match either pipeline's actual performance.

**Best practice:** Parallel pipelines must share nothing but the repository. Separate databases, separate workflows, separate dispatch events. The blast radius of a failure should be exactly one pipeline.

---

## 8. Pre-Change Checklist

Derived from three incidents that each could have been prevented by a 30-second check.

**Before deleting any file or directory:**
```bash
# Check for references in CI workflows
grep -rn "deleted_thing/" .github/workflows/

# Check for imports in production code
grep -rn "from deleted_module import" src/

# Check for references in tests
grep -rn "deleted_thing" tests/
```

**Before every commit:**
```bash
# Run the full test suite
pytest tests/ -v

# If changing business logic: run the specific regression tests
pytest tests/test_regression.py -v

# If changing data providers: test from a clean environment
# (don't rely on local cache or stored credentials)
```

**Before deploying a new strategy or signal:**
```
1. Paper trade for 200+ resolved observations
2. Compare against baseline (is it actually better?)
3. Define pass/fail gate BEFORE starting (WR ≥ X%, ROI ≥ Y%)
4. Document the gate criteria so you can't move the goalposts
```

**Best practice:** Checklists prevent the incidents you've already seen. They cost 30 seconds and save hours.

---

## 9. Documentation as Defense

**Problem:** Code was changed to do the opposite of what documentation said. A function named `contrarian_signal` actually implemented a momentum strategy. Documentation said "fade the streak" but code said "ride the streak." The risk: a future contributor reads the docs, sees a "bug," and "fixes" the code back to the version that lost money.

**What we did:**
- Renamed every function, variable, label, and comment to match actual behavior
- Added a permanent guardrail in the project config file (read by every contributor and every AI assistant): "The strategy is X. Do NOT revert to Y."
- Kept a backward-compatibility alias so old references still work during transition
- Updated every test description to describe the actual behavior

**Separate lesson — the break-fix log:**
- Every production incident is documented: date, duration, root cause, impact, fix, regression test added
- This prevents the same mistake from being made by a different person (or the same person 3 months later)
- The log also serves as the strongest argument for why the test suite exists

**Best practice:** Naming is a contract. If code does X but is named Y, someone will eventually "fix" it to do Y. Rename aggressively. Document failures prominently. Add guardrails that are read automatically, not just stored in a wiki.

---

## 10. Staged Rollout with Kill Switches

**Pattern that works:**

| Stage | What | Gate to next stage |
|-------|------|-------------------|
| 1. Build | Core logic + data pipeline | Runs without crashing for 24h |
| 2. Backtest | Test on historical data | Beats baseline by defined margin |
| 3. Paper trade | Full logic, no real stakes | 200+ observations, WR ≥ threshold |
| 4. Micro-deploy | Smallest possible real stakes | Positive cumulative outcome after N events |
| 5. Scale | Increase stakes gradually | Continued performance at each tier |

**What makes this work:**
- **Gates are defined before the stage starts.** You can't move the goalposts mid-stage.
- **Each stage has a kill switch.** If paper trading shows the signal doesn't work, you stop before losing money.
- **Conviction tiers control exposure.** Not every signal gets the same stake. Weak signals get $0. Strong signals get more. The tier boundaries are fixed, not vibes-based.

**What we learned the hard way:**
- Skipping paper trading cost $1,021 in one day
- A strategy that "works" in backtests may fail live because the environment has already priced in the signal
- The strongest defense against large losses is simply: don't bet when you're not confident

**Best practice:** Never skip a stage because you're excited about backtest results. The stages exist to catch the gap between simulation and reality. That gap has historically been the most expensive lesson.

---

## 11. Module-Level Constants Are Import-Time Landmines

**Incident:** BTC 5m pipeline ran as PAPER for ~24 hours on VPS despite `TRADING_ENABLED=true` in `.env`. The engine loaded `.env` into `os.environ` correctly, but `trade.py` had already evaluated `TRADING_ENABLED = os.environ.get("TRADING_ENABLED", "false") == "true"` at import time — before `.env` was loaded. Once Python cached the module, the constant was locked to `False` forever.

**What made it worse:** Two separate systemd services (`botsy.service` and `polymarket-bot.service`) ran the same engine process. One got `True`, the other got `False`. The dashboard showed alternating LIVE/PAPER rows — confusing because the bug was intermittent by design.

**Why it wasn't caught sooner:** Fail-closed design meant the bug produced paper orders, not errors. Everything "worked" — just in the wrong mode. No alert fires on paper orders.

**Remediation (v1 — initial):**
- Every pipeline overrode `trade.TRADING_ENABLED` from `pipeline_control.is_pipeline_live()` at the start of `main()` — evaluated at runtime, not import time
- Disabled the duplicate systemd service

**Remediation (v2 — permanent fix, 2026-04-06):**
The v1 fix still used a writable global, making the same class of bug inevitable. Replaced with pipeline isolation by construction:
- `execute_trades(db, cycle, pipeline_name="btc_5m")` resolves `trading_enabled = is_pipeline_live(pipeline_name)` internally — no pipeline ever writes to `trade.TRADING_ENABLED`
- `place_order()` and `settle_orders()` accept `trading_enabled` as a parameter, threaded from `execute_trades()`
- PID lock file (`data/engine.pid`) prevents dual engine processes
- AST test (`test_pipeline_isolation.py`) fails CI if any pipeline file assigns `trade.TRADING_ENABLED`
- Runtime assertion in `place_order()` logs WARNING if passed mode disagrees with the global (passed value always wins)
- Three `ci_run_*.py` files unified into `polymarket_pipeline.py` — eliminated the code duplication that spread the mutation to 3 files

**Best practice:** Never rely on module-level constants derived from environment variables when the env may be set after import. More importantly, never rely on a writable global that multiple callers mutate — pass the value as a parameter so corruption is impossible by construction. And always check `systemctl list-units` after deploying a new service — name collisions hide duplicate processes.

---

## 12. Check for Duplicate Processes After Every Deployment

**Incident:** Two systemd services — created at different times, with different names, but identical `ExecStart` commands — ran the same trading engine simultaneously. Each produced predictions and orders independently, doubling output and creating confusing interleaved results.

**Why it's easy to miss:** `systemctl restart botsy` correctly restarts one service. But `polymarket-bot.service` was never touched and kept running. No error, no log collision, no crash. Just silent duplication.

**Remediation:**
- Post-deployment check: `ps aux | grep <engine_name> | grep -v grep` — count must be 1
- `systemctl list-units --type=service | grep -i <project>` — count must be 1
- If migrating service names, always `systemctl stop && systemctl disable` the old one

**Best practice:** Treat process count as a deployment invariant. One engine, one process, one service. Verify after every restart, migration, or service rename.

---

## 13. Always Scope Database Operations by Entity

**Incident:** Strategy Lab's `_auto_resolve()` resolved ALL pending predictions regardless of symbol. When a BTCUSDT candle closed, it resolved ETHUSDT, SOLUSDT, and DOGEUSDT predictions using BTC's candle direction. 1,600 predictions were corrupted with wrong outcomes before the bug was caught.

**Why it's subtle:** The function "worked" — it resolved predictions and set outcomes. No errors, no crashes. The corruption was invisible unless you checked whether ETH predictions were being resolved by ETH candles (they weren't).

**The pattern:** Any time you have a shared table with records belonging to different entities (symbols, users, pipelines), every UPDATE/DELETE query must scope by the entity. "Resolve all pending" is always wrong when the table holds data for multiple entities.

**Remediation:**
- Added `symbol` parameter to `_auto_resolve()` — only resolves predictions matching the candle's symbol
- Deleted the corrupted DB and reset (1,600 tainted rows were unrecoverable)
- Added regression test: `test_resolve_scoped_by_symbol`

**Best practice:** When a shared table stores data for multiple entities, every write operation must include a WHERE clause scoping to the entity being processed. If you find yourself writing `WHERE outcome IS NULL` without an entity filter, you almost certainly have a cross-contamination bug.

---

## 14. Historical Data Pollutes Analysis — Always Check the Timestamp

**Incident:** BTC 5m showed 101 HIGH_VOL/NEUTRAL bets at 49.5% WR. This looked like the HV/N gate (added Apr 9) wasn't working. Investigation revealed those 101 bets were ALL from before Apr 9 — the gate was working perfectly, but the MCP returned historical + post-gate data mixed together.

**Why it matters:** Acting on this mixed data would have led to removing a filter that was already working. The data was factually correct but temporally misleading.

**The pattern:** Any time you add a gate/filter to production, all historical data predating the gate will dilute your performance metrics. If you don't partition by "before" and "after," you'll conclude the gate doesn't work when it does.

**Remediation:**
- Always query with a date filter: "show me results SINCE the gate was deployed"
- The gate's commit timestamp is the partition point, not arbitrary calendar dates
- Added this as a mental check before any "this isn't working" conclusion

**Best practice:** Before acting on any aggregate metric, ask: "When was this data generated?" If it spans a code change you're evaluating, partition it. Pre-change data tells you what WAS happening, not what IS happening.

---

## 15. Log Everything, Optimize Post-Hoc (Always-Fire Pattern)

**Context:** Strategy Lab initially used hard thresholds (e.g., "only fire if z-score > 2.0 AND regime is mean-reverting"). This bakes in assumptions about which parameters matter before you have data.

**The better pattern:** Make strategies "always-fire" — return a signal for EVERY candle, storing the full indicator snapshot (27 parameters) in metadata. The signal itself becomes a data collection exercise. Post-hoc analysis determines which parameter ranges have edge.

**Why this is better:**
- Hard thresholds are premature optimization — you don't know which z-score cutoff is optimal until you have 500+ observations
- Always-fire generates 10x more data (every cycle vs. 10-30% of cycles), reaching statistical significance faster
- You discover interaction effects you never would have hypothesized (e.g., VWAP z-score only matters in mean-reverting regimes with RSI < 30)
- You never wonder "what would have happened if I'd used threshold X?" — the data for every threshold is already there

**Risks:**
- 27 parameters × 200 predictions = massive overfitting potential. Require min 30-50 observations per bucket.
- Most bucketed results will be noise. The discipline is requiring statistical significance, not just "bucket X shows 60%."
- The real payoff is refining 1-2 production filters, not spawning 15 new strategies.

**Best practice:** When you don't know which thresholds matter, log everything and decide later. The cost of storing metadata is near-zero. The cost of choosing wrong thresholds early is months of wasted data.

---

## 16. Hard-Sync Code Before Auto-Committing Data

**Incident:** On 2026-05-01, the VPS auto-commit loop repeatedly deleted freshly-pushed source and documentation commits. Kalshi parser work, Lab/Microstructure work, and the session log were all pushed successfully, then removed by later `Auto:` commits from the engine.

**Root cause:** `_git_commit_push()` used `git reset --soft origin/main` in its push-recovery path. Soft reset moves `HEAD` but preserves the old index and worktree. The VPS could therefore claim to be at the new remote commit while its files still looked like the stale checkout, then commit source/doc deletions in the next runtime-data snapshot.

**Why it is subtle:** The code only ran `git add data/ docs/daily/`, so it looked scoped. But git index state survives soft reset. The staging allowlist was not enough once the worktree and `HEAD` disagreed.

**Remediation:**
- `_git_commit_push()` now fetches before committing.
- If local `HEAD` is safely behind `origin/main`, it uses `git reset --hard origin/main` before staging runtime data.
- If local and remote diverge, it writes `data/GIT_COMMIT_BAIL` and stops auto-committing.
- If push fails after a commit, it bails instead of trying soft-reset recovery.
- Regression tests assert hard reset before staging and forbid `git reset --soft`.

**Best practice:** Production automation that commits generated data must hard-sync code first, then stage only generated paths. Never use soft reset in an unattended writer. If histories diverge, bail and ask for human inspection.

---

## Summary: The 16 Rules

1. **One source of truth.** The deployed system is canonical. Local state is a cache.
2. **Test from deployment.** If it works on your machine but not in CI, it doesn't work.
3. **Validate on real data.** Synthetic tests validate logic. Real-world tests validate edge.
4. **Check the inverse.** A reliably wrong signal is a signal.
5. **Start simple.** One good filter beats 32 features.
6. **One test per incident.** The test suite is a scar tissue map.
7. **Isolate parallel systems.** Share nothing but the repository.
8. **Checklist before change.** 30 seconds prevents 12-hour outages.
9. **Names are contracts.** If the code does X, name it X.
10. **Stage everything.** Define the gate before you start. Never skip a stage.
11. **No import-time env.** Override module constants at runtime, not import time.
12. **One process per engine.** Verify process count after every deployment.
13. **Scope every DB write.** Shared tables need entity filters on every UPDATE/DELETE.
14. **Check the timestamp.** Historical data dilutes post-change metrics. Partition by deploy date.
15. **Log everything, optimize later.** Hard thresholds are premature. Store full state, decide post-hoc.
16. **Hard-sync before auto-commit.** Generated-data writers must hard-reset to remote code before staging runtime files.
