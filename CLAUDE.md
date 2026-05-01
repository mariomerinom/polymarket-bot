# Project Rules

## GitHub Is the Source of Truth (for code, not data)

1. **Code: GitHub canonical.** Always `git pull --rebase` before pushing. The deployed system is canonical for runtime state — if a local query disagrees with live, live is right.
2. **Data: VPS canonical.** As of 2026-04-28, `data/*.db` files are no longer tracked in git (history rewrite reclaimed ~16 GB of binary auto-commit bloat). The engine writes DBs to the VPS only. Pull fresh state to local for analysis with **`tools/sync_data.sh`** (rsync from VPS over SSH). `engine_health.txt` is the single auto-committed data artifact (out-of-band monitoring).
3. **Always push after making changes.** A change that isn't on GitHub doesn't exist.
4. **Source changes need an engine restart — automated via the post-merge hook.** See `docs/ops/DEPLOYMENT.md`. Python caches imports at process start; pushing code is not enough. The VPS-side `post-merge` hook auto-restarts botsy when `src/` or `config/` change. Data-only commits do not trigger restart. Check `logs/deploy_hook.log` on VPS to verify.
5. **Never `git reset --hard` on a tracking flip without backing up `data/` first.** A target HEAD that doesn't track the formerly-tracked DBs will DELETE them from the working tree on reset. See `docs/ops/postmortem_2026-04-28_data_loss_during_rewrite.md` for the canonical incident.

## Development Process

- **TDD-first.** Write behavioral tests BEFORE code. Tests assert WHAT the system does (contracts), not HOW. See `docs/core/TESTING.md`.
- **Commit when work is done, not when told.** Tests pass → commit → push.
- Run `pytest tests/ -v` before every commit. Never skip pre-commit hooks.
- Add a regression test for every fix.

### Board-First Workflow

The [BOTSY Kanban](https://github.com/users/mariomerinom/projects/1) is the live tracker.

**Incidents:** `gh issue create --label incident,<pipeline>` → postmortem in `docs/ops/` → close when pushed.

**Optimizations:** Register in `optimizations.json` → `gh issue create --label optimization,<pipeline>` with baseline + revert criteria → Monitoring until sample reached.

**Decisions:** `gh issue create --label decision,<pipeline>` with trigger condition → Monitoring → "Ready" when triggered.

**Work tracking:** Move cards to "In Progress" when starting, "Done" when shipped, "Reverted" if failed.

## Data Access — Botsy MCP Is the Source of Truth

- **Always use Botsy MCP tools for pipeline data.** Never ad-hoc SQL. The MCP encodes correct joins, outcome encoding, and P&L formulas.
- **Use `pipeline_overview` first** to see all pipelines before drilling in.
- **If the MCP doesn't cover it, fix the MCP** — don't work around with Bash/SQL.
- **Never cite numbers from memory.** Always query fresh — predictions generate every 5 minutes.

## Strategy Lab (Parameter Optimization)

- **Always-fire pattern.** Lab strategies fire EVERY cycle, storing 27-param indicator snapshots in metadata. Post-hoc analysis finds edge. Do NOT add hard thresholds.
- **Tools:** `lab_param_sweep` (1D bucketing) and `lab_param_matrix` (2D cross-tab). Min 30-50 observations per bucket.
- **Scope resolution by symbol.** `_auto_resolve()` MUST filter by symbol. Never resolve one asset's predictions with another's candle.
- **Check timestamps before acting.** Partition data by deploy date. Pre-change data dilutes post-change metrics.
- **Graduation:** 200 resolved predictions with WR > breakeven → `gh issue create --label decision,strategy-lab`.

## Shadow Experiments

Low-risk experimentation pattern. Log what the alternative WOULD have done alongside real behavior, accumulate N observations, then decide whether to promote or revert. Dominant pattern in the codebase (7 instances as of Apr 2026).

- **When to use, storage decisions, the five-step template, anti-patterns:** `docs/core/SHADOW_FRAMEWORK.md`
- **Registration:** `docs/optimizations.json` with `status: "shadow"` — single source of truth for experiment lifecycle.
- **Promotion gate:** 50-bet minimum (200+ for conviction-structure changes), pre-registered revert criteria, one-week minimum shadow duration, apples-to-apples comparison function defined before shipping.
- **Learning from failures:** Four thin-sample over-promotions reverted in April 2026 (`mr_shadow_extreme`, `eth_mr_shadow_extreme`, `unified_extreme_estimate_shadow`, `shadow_vwap_meanrev`). Follow the doc.

## Bot Design

- **No agent bias.** All directional bias from human macro config, not code.
- **BTC + ETH = MOMENTUM (ride streaks).** V3 contrarian lost at 37% WR. Momentum validated at 63%. Do NOT revert. Streak UP → predict UP.
- **Paper trade first.** 200+ resolved predictions before real capital.
- **Conviction ≥ 3 gates real money.** Conv 0-2 = skip. Flat $25 bet size (Phase 1).
- **Trade execution:** `execute_trades(db, cycle, pipeline_name="btc_5m")` resolves mode per-pipeline. Kill switch: `KILL_SWITCH=true` or `data/KILL_SWITCH`. Daily loss breaker: $300.

## Architecture

**Engine:** Single async process on DigitalOcean VPS (`botsy_engine.py`). Bybit WS → candle buffer → TA engine → pipeline dispatch → git auto-commit. Managed by systemd (`botsy.service`).

**Pipelines:** 12 pipelines, all paper, all momentum. See `config/pipelines.json`. Polymarket pipelines share `polymarket_pipeline.py`; perps use `ci_run_perp.py`. Trading mode resolved per-pipeline — no global mutation.

**Diagnostics:** `streamlit run tools/diag.py` after `git pull`. Five tabs: P&L Overlay, Rolling WR, Regime Heatmap, Fill Diagnostic, Raw Query.

**Sizing phases:** $25 flat (current) → $50 at +$500 → Kelly at +$3,000. CLOB depth caps all bets at ≤2% slippage.

## Quick Reference

- **Terminal cheatsheet:** `./tools/cheatsheet.sh skills` — all skills, hooks, MCP tools, architecture rules
- **Engineering lessons:** `docs/ops/ENGINEERING_LESSONS.md` — 15 rules from production incidents
- **Deployment & auto-restart hook:** `docs/ops/DEPLOYMENT.md` — how source changes reach the engine
- **Shadow experiment guide:** `docs/core/SHADOW_FRAMEWORK.md` — pattern, storage options, promotion criteria
- **Pivot options / strategic direction:** `docs/core/PIVOT_OPTIONS.md` — where the system can go when the current thesis decays
- **Full doc map:** `docs/core/PRIMER.md` — system overview, repo map, all document locations
- **Health check:** Use `/health-check` skill — checks CI, predictions, orders, circuit breaker, board state

## Validation Principles

- **Every optimization gets a baseline.** Snapshot WR, P&L, bet count before shipping.
- **Set revert criteria before shipping.** Define failure while still objective.
- **Minimum sample: 50 bets.** Anything less is noise.
- **Derived from ≠ validated by.** Track forward performance separately from discovery dataset.
- **Track the counterfactual.** Store filtered predictions at conv 2 for comparison.
- **One change at a time.** Stagger when possible.

## Documentation Paradigm (Backward → Present → Future)

Every commit, plan, and decision answers:

1. **Backward** — Does anything break? Rollback plan?
2. **Present** — What exactly changes? GO/NO-GO criteria?
3. **Future** — Where does this surface? When do we revisit?
