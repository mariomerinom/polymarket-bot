# Project Rules

## GitHub Is the Source of Truth

1. **Always `git pull` before reading any data file** (especially `data/predictions.db`). The CI pipeline auto-commits every ~5 minutes — local state goes stale fast.
2. **Never analyze local DB without pulling first.** If you report numbers, they must match what the live dashboard shows.
3. **Always push after making changes.** A change that isn't on GitHub doesn't exist.
4. **Expect CI conflicts on push.** The self-rescheduling pipeline commits constantly. Always `git pull --rebase` before pushing. If the DB conflicts, our code changes win (CI will regenerate the DB).
5. **The dashboard (GitHub Pages) is the canonical view.** If the dashboard shows different numbers than a local query, the dashboard is right and your local data is stale.

## Development Process

- **TDD-first.** Write behavioral tests BEFORE writing code. Before any implementation, evaluate existing tests for gaps and drift, review relevant plans, then determine both what to test and what to code. Tests assert WHAT the system does (contracts), not HOW it's organized. See `docs/plans/tdd-plan.md` and `docs/core/TESTING.md` Layer 8.
- **Commit when work is done, not when told.** Tests pass → commit → push. Don't wait for permission.
- Run `pytest tests/ -v` before every commit. Tests gate CI — a broken push stops the pipeline.
- Never skip pre-commit hooks.
- Add a regression test for every fix.

### Board-First Workflow

The [BOTSY Kanban](https://github.com/users/mariomerinom/projects/1) is the live tracker. Keep it current as you work.

**When you fix a bug or handle an incident:**
1. `gh issue create --repo mariomerinom/polymarket-bot --label incident,<pipeline>` with symptom, root cause, fix
2. Write postmortem in `docs/ops/` as a standalone markdown file
3. Close the issue when fix is pushed

**When you ship a code change that needs validation (optimization):**
1. Register in `optimizations.json` (machine-readable for tracker)
2. `gh issue create --label optimization,<pipeline>` with baseline, revert criteria, min sample
3. Card sits in Monitoring until sample reached

**When a new decision emerges:**
1. `gh issue create --label decision,<pipeline>` with trigger condition in the body
2. Set milestone if it maps to a roadmap phase
3. Do NOT add to `decisions.md` (archived) — the board is the live tracker

**When you start/finish work:**
1. Move the card to "In Progress" when you begin: `gh project item-edit ...`
2. Move to "Done" and close the issue when shipped
3. Move to "Reverted" if the experiment fails

**During health checks (`/health-check`):**
1. Check the "Ready" column — anything there needs a human decision NOW
2. Check "Monitoring" optimizations — any revert candidates?
3. Report board state alongside pipeline health

**When reviewing decisions (`/review-decisions`):**
1. Query the board for `label:decision` + status=Monitoring
2. Cross-check triggers against current DB stats
3. Move triggered decisions to "Ready"

## Data Access — Botsy MCP Is the Source of Truth

- **Always use Botsy MCP tools for pipeline performance data.** Never write ad-hoc SQL against prediction DBs. The MCP encodes the correct joins, outcome encoding, and P&L formulas. Raw SQL gets schema differences wrong (Polymarket uses `Yes`/`No`, perps use `1`/`0`).
- **Use `pipeline_overview` first** to see all pipelines before drilling into any one.
- **If the MCP doesn't cover a pipeline, fix the MCP** — don't work around it with Bash/SQL. The MCP auto-discovers from `config/pipelines.json`, so adding a pipeline there is usually sufficient.
- **Never cite performance numbers from memory or context.** Always query fresh. Stale numbers from earlier in a conversation are wrong — the bot generates new predictions every 5 minutes.

## Bot Design

- **No agent bias.** The bot must not have built-in directional bias (UP or DOWN). All bias comes from human macro config, not prompts or code.
- **BTC strategy is MOMENTUM (ride streaks).** V3 contrarian lost at 37% WR on live Polymarket. Inverting to momentum validated at 63% WR. Do NOT revert BTC signal direction. Streak UP → predict UP. Streak DOWN → predict DOWN.
- **ETH strategy is MOMENTUM (ride streaks).** Contrarian validated at 54.4% in pattern mining but lost at 33.3% WR on 54 live predictions. Momentum counterfactual: 66.7% on same bets. Flipped 2026-04-01. Same V3→V4 pattern as BTC. Do NOT revert to contrarian. ETH pipeline is in `src/predict_eth.py` (paper trading, conviction=2).
- **Paper trade first.** Every new signal must accumulate 200+ resolved predictions in paper trading before risking real capital.
- **Conviction gates real money.** Only conviction >= 3 places bets. Conviction 0-2 = skip.
- **Trade execution is in `src/trade.py`.** Trading mode is resolved per-pipeline: `execute_trades(db, cycle, pipeline_name="btc_5m")` calls `pipeline_control.is_pipeline_live()` internally — no shared global. Paper mode logs what it would do; live mode places real limit orders via `py-clob-client` SDK on Polygon. Flat $25 bet size. Kill switch via `KILL_SWITCH=true` env var or `data/KILL_SWITCH` file. Daily loss circuit breaker at $300 (env `DAILY_LOSS_LIMIT`). Thin book guard caps bets at 90% of CLOB max@2% slippage.

## Multi-Pipeline Architecture

All pipelines run on a DigitalOcean VPS (`botsy_engine.py`) via a single async engine process. GitHub Actions are fully retired — no `.github/workflows/` directory exists. The engine dispatches pipelines on Bybit WS candle-close events, routed by the `ROUTING` table.

### Pipeline Table

| Pipeline | Entry Point | DB | Signal | Status |
|----------|-------------|----|--------|--------|
| BTC 5m | `ci_run.py` → `polymarket_pipeline` | `predictions.db` | Momentum | Paper (reverted from live 2026-04-09) |
| BTC 15m | `ci_run_15m.py` → `polymarket_pipeline` | `predictions_15m.db` | Momentum | Paper |
| ETH 5m | `ci_run_eth.py` → `polymarket_pipeline` | `predictions_eth.db` | Momentum | Paper |
| Kalshi BTC | `ci_run_kalshi.py` (standalone) | `predictions_kalshi.db` | Momentum | Paper (Phase 1 — conviction scoring) |
| Bybit BTC | `ci_run_bybit.py` (standalone) | `predictions_bybit.db` | Momentum | Paper |
| Hyperliquid BTC | `ci_run_hl.py` (standalone) | `predictions_hl.db` | Momentum | Paper (piggybacks Bybit spot candles) |
| ETH Bybit | `ci_run_perp.py` → `run_perp_pipeline` | `predictions_bybit_eth.db` | Momentum | Paper |
| ETH Hyperliquid | `ci_run_perp.py` → `run_perp_pipeline` | `predictions_hl_eth.db` | Momentum | Paper |
| SOL Bybit | `ci_run_perp.py` → `run_perp_pipeline` | `predictions_bybit_sol.db` | Momentum | Paper |
| SOL Hyperliquid | `ci_run_perp.py` → `run_perp_pipeline` | `predictions_hl_sol.db` | Momentum | Paper |
| DOGE Bybit | `ci_run_perp.py` → `run_perp_pipeline` | `predictions_bybit_doge.db` | Momentum | Paper |
| DOGE Hyperliquid | `ci_run_perp.py` → `run_perp_pipeline` | `predictions_hl_doge.db` | Momentum | Paper |

### Diagnostic Tooling

GH Pages dashboards retired 2026-04-08. The canonical view is the local Streamlit app:
`source venv/bin/activate && streamlit run tools/diag.py`. Reads live DBs after `git pull`.
Five tabs: P&L Overlay (counterfactual vs actual), Rolling WR, Regime Heatmap
(`day_type × direction`, `vol_bucket × direction`), Fill Diagnostic, Raw Query.

### Unified Pipeline (`src/polymarket_pipeline.py`)

The three Polymarket pipelines (BTC 5m, BTC 15m, ETH 5m) share a unified lifecycle via `run_polymarket_pipeline()`. Each `ci_run_*.py` is a thin config wrapper (~30 lines) that calls it with pipeline-specific parameters. Kalshi and Bybit have different enough structures to remain standalone.

### Pipeline Isolation

Trading mode is resolved per-pipeline inside `execute_trades(pipeline_name=...)` — no pipeline mutates `trade.TRADING_ENABLED`. Defense layers: (1) `pipeline_name` parameter threads mode locally, (2) PID lock prevents dual engine processes, (3) AST test guards against `TRADING_ENABLED` mutation, (4) runtime assertion logs warnings on global/local mismatch.

### VPS Engine (`src/botsy_engine.py`)

Single async process on DigitalOcean Amsterdam. Manages: Bybit WS feeds (kline events), Polymarket WS feed (orderbook), candle buffer (100-candle ring buffer), TA engine (pandas-ta indicators), pipeline dispatch on candle close, git auto-commit every ~5 minutes. Managed by systemd (`botsy.service`).

### Git Conflict Resolution

The engine's `_git_commit_push()` uses: `add → commit → push → (if rejected: pull --rebase -X theirs → push)`. CI-generated files (DBs, `optimizations.json`, dashboard HTML) are regenerated every cycle, so accepting the remote version on conflict is safe.

## Production Sizing Philosophy

Production sizing is a grind, not a gamble. The current paper-trading tiers ($75/$200/$300) revealed concentration risk: 16 bets at $219 avg carries more variance than 43 bets at $75. One bad day hurts 3x as much.

| Phase | Bet Size | Trigger to Advance | Trigger to Stop |
|-------|----------|--------------------|-----------------|
| **Phase 1 — Flat grind (CURRENT)** | $25 flat | Bankroll +$500 from grind profits | WR < 52% over 50 bets, or -$300 daily loss |
| **Phase 2 — Full grind** | $50 flat | Bankroll +$1,500 cumulative | WR < 52% over 50 bets, or -$500 daily loss |
| **Phase 3 — Kelly on house money** | Kelly fractional, CLOB-capped | Bankroll +$3,000 cumulative | Drawdown > 30% of peak bankroll |

- **Conviction still gates which bets fire.** Only conv ≥ 3 places orders. All bets are the same dollar amount within a phase.
- **Thin book constraint.** Kelly must be capped by book depth (CLOB data), not just by bankroll math. The bet size ceiling is whatever the book can absorb at ≤2% slippage.
- **Paper tiers stay as-is.** The current tiered system continues in paper trading to collect data on whether tier differentiation actually predicts performance. But production does NOT inherit paper sizing.

## Documentation Map

### Kanban Board

| Resource | URL |
|----------|-----|
| **BOTSY Kanban** (GitHub Project) | https://github.com/users/mariomerinom/projects/1 |

Tracks decisions, specs, optimizations, incidents, and infra work. All items are GitHub Issues with labels (`decision`, `spec`, `optimization`, `incident`, `infra`) and pipeline labels (`BTC-5m`, `ETH-5m`, etc.). Milestones map to roadmap phases.

### Core (`docs/core/`) — project rules, strategy, roadmap

| Document | Goal |
|----------|------|
| `CLAUDE.md` | Project rules for Claude — source of truth for behavior |
| `docs/core/strategy.md` | Current trading strategy for all pipelines |
| `docs/core/PRIMER.md` | System overview, repo map, onboarding |
| `docs/core/ROADMAP.md` | Project phases and validation gates |
| `docs/core/decisions.md` | **ARCHIVED** → `docs/archive/decisions.md`. New decisions go to GitHub Issues with `decision` label |
| `docs/core/TESTING.md` | Test strategy, layers, CI pipeline |
| `config/macro_bias.md` | Macro overlay config (not used in V4) |

### Operations (`docs/ops/`) — incidents, lessons learned

| Document | Goal |
|----------|------|
| `docs/ops/BREAK_FIX_LOG.md` | **ARCHIVED** → `docs/archive/BREAK_FIX_LOG.md`. New incidents go to GitHub Issues with `incident` label. Postmortems still written as markdown in `docs/ops/` |
| `docs/ops/ENGINEERING_LESSONS.md` | Evergreen operational lessons |

### Plans (`docs/plans/`) — active and completed plans

| Document | Goal | Status |
|----------|------|--------|
| `docs/plans/pipeline-isolation-unification.md` | Eliminate `TRADING_ENABLED` global mutation, unify ci_run files | **COMPLETE** (2026-04-06) |
| `docs/plans/event-driven-execution-plan.md` | Decouple prediction (5m) from execution (reactive to WS orderbook) | PLANNED |
| `docs/plans/tdd-plan.md` | TDD-first refactoring strategy and test layers | Reference |
| `docs/plans/KALSHI_INTEGRATION_PLAN.md` | Kalshi venue expansion (Phase 0 active) | ACTIVE |
| `docs/plans/multi-asset-plan.md` | Multi-asset expansion status and plan | ACTIVE |
| `docs/plans/refactoring-plan.md` | Code structure refactoring approach | Reference |
| `docs/plans/task_kalshi_analysis.md` | Kalshi pipeline analysis task | COMPLETE |

### Reference (`docs/reference/`) — sizing, liquidity

| Document | Goal |
|----------|------|
| `docs/reference/kelly_analysis.md` | Kelly sizing reference for Phase 3 |
| `docs/reference/liquidity_probe.md` | Multi-asset CLOB liquidity reference |

### Pipelines (`docs/pipelines/`) — pipeline-specific docs

| Document | Goal |
|----------|------|
| `docs/pipelines/eth_pipeline_acceptance_criteria.md` | Phased rollout plan: Phase 1 (validate momentum) → Phase 2 (adaptation layer) → Phase 3 (full integration) |
| `docs/pipelines/spec_eth_model_training.md` | ETH adaptation layer spec: regime recalibration, cross-asset features, conviction scoring |

### Specs (`docs/specs/`) — unimplemented feature designs

These are unimplemented feature specs. Evaluate after ETH Phase 1 validates and BTC live trading stabilizes.

| Document | Goal |
|----------|------|
| `docs/specs/spec_rsi_conviction_gate.md` | RSI as pre-bet filter to downgrade conflicting signals |
| `docs/specs/spec_obv_bucket_filter.md` | On-Balance Volume filter for 0.50-0.70 price bucket |
| `docs/specs/spec_vwap_mean_reversion.md` | VWAP deviation for mean-reverting regime bets |
| `docs/specs/spec_volatility_breakout.md` | Volatility compression→expansion breakout detection |
| `docs/specs/spec_order_flow_imbalance.md` | CLOB bid/ask imbalance as leading indicator |
| `docs/specs/spec_market_price_dislocation.md` | Polymarket price lag vs BTC spot arbitrage |
| `docs/specs/spec_cross_exchange_lead_lag.md` | Kraken/Coinbase lead-lag temporal arbitrage |
| `docs/specs/spec_dead_regime_harvesting.md` | Edge extraction from mean-reverting/dead-hour regimes |
| `docs/specs/spec_generic_conviction_engine.md` | Parameterized conviction scorer for all assets (shadow mode) |

### Fill Problem Specs (`docs/specs/stochastic/`) — execution fix designs

Specs addressing the adverse selection / fill rate problem (Decision #24). The signal picks winners at 65%+ but orders expire before filling. Some specs are now implemented; others remain planned.

| Document | Goal | Status |
|----------|------|--------|
| `docs/specs/stochastic/spec_unified_vps_websocket.md` | Unified VPS + websocket architecture for live pricing | **IMPLEMENTED** — VPS + WS live |
| `docs/specs/stochastic/spec_bybit_vps_migration.md` | Bybit/Kalshi VPS migration | **IMPLEMENTED** — fully consolidated |
| `docs/specs/stochastic/spec_fill_diagnostic.md` | Fill diagnostic instrumentation (`src/fill_diagnostic.py`) | **IMPLEMENTED** |
| `docs/specs/stochastic/spec_dynamic_price_cap.md` | Dynamic slippage spread (3¢-15¢) based on depth, spread, volume | Planned |
| `docs/specs/stochastic/spec_stochastic_entry_timing.md` | Stochastic Oscillator for entry timing within 5-min windows | Planned |
| `docs/specs/stochastic/fill-implementation.md` | Fix adverse selection via CLOB websocket + IOC orders | Planned |
| `docs/specs/stochastic/claude-fill-problem-consensus.md` | Multi-agent consensus on fill problem root cause and fixes | Reference |
| `docs/specs/stochastic/fill-problem-agreement-and-tension.md` | Agreement/tension analysis across fill problem proposals | Reference |
| `docs/specs/stochastic/gemini-fill-resolution.md` | External review of fill problem proposals | Reference |
| `docs/specs/stochastic/Spec: Optimal Fill Strategy v1 — Hybrid .md` | Hybrid optimal fill strategy combining multiple approaches | Reference |

### Research (`docs/research/`) — historical analysis, read-only reference

| Document | Goal |
|----------|------|
| `docs/research/BACKTEST_FINDINGS.md` | V1→V4 backtest results and regime analysis |
| `docs/research/outcome_analysis_bitcoin.md` | Phase 1 BTC statistical analysis (8,653 markets) |
| `docs/research/outcome_analysis_ethereum.md` | Phase 1 ETH statistical analysis (8,654 markets) |
| `docs/research/outcome_analysis_solana.md` | Phase 1 SOL statistical analysis (8,653 markets) |
| `docs/research/pattern_mining_results.md` | Phase 2 pattern mining results |

### Analysis (`docs/analysis/`) — investigations, postmortems, theses

| Document | Goal |
|----------|------|
| `docs/analysis/analysis_exhaustion_gate.md` | Analysis showing exhaustion gate filtered best predictions |
| `docs/analysis/postmortem_exhaustion_gate.md` | Postmortem on exhaustion + cooldown gate removal |
| `docs/analysis/thesis_paper_to_live_degradation.md` | Paper-to-live WR degradation thesis (Decision #17) |
| `docs/analysis/pipeline_recommendations_mar25-27.md` | Source data for decisions #1-9 |
| `docs/analysis/kalshi_pipeline_review.md` | Kalshi Phase 0 analysis: mock mode detected, all WR data invalid |

### Archived (superseded, in `docs/archive/`)

| Document | Why Archived |
|----------|-------------|
| `docs/archive/bot-V3.md` | V3 contrarian strategy — lost at 37% WR |
| `docs/archive/bot-V3.1.md` | V3.1 production plan — superseded by V4 |
| `docs/archive/bot-V3.2.md` | V3.2 iteration — superseded by V4 |
| `docs/archive/BACKTEST_RESULTS.md` | Early backtest data |
| `docs/archive/DEPLOYMENT_PLAN.md` | Pre-V4 deployment plan |
| `docs/archive/PROJECT_EVOLUTION.md` | Project history narrative |
| `docs/archive/signal-infrastructure-plan.md` | Multi-source signal exploration — useful parts in strategy.md |
| `docs/archive/acceptance_criteria_generic_conviction.md` | Duplicate of spec_generic_conviction_scorer.md |
| `program.md` | V1/V2 LLM agent system — marked LEGACY |
| `docs/archive/decisions.md` | Decision tracker — replaced by GitHub Issues + kanban board |
| `docs/archive/BREAK_FIX_LOG.md` | Incident log — replaced by GitHub Issues. Postmortems now standalone files in `docs/ops/` |

### Auto-Generated (do not edit manually)

| Document | Source |
|----------|--------|
| `docs/daily/YYYY-MM-DD.md` | Generated by `daily_report.py` via CI |
| `docs/sessions/*.md` | Working session logs |
| `docs/daily/index.md` | Daily report index |

## Validation Principles

- **Every optimization gets a baseline.** Before shipping a change, snapshot the current WR, P&L, and bet count. You can't measure improvement without a before.
- **Set revert criteria before shipping, not after.** Decide what "failure" looks like while you're still objective. Once you're watching the numbers, bias creeps in.
- **Minimum sample size is 50 bets.** Anything less is noise. A 10-bet streak means nothing — wait for the data.
- **Derived from ≠ validated by.** If you found the edge in the same dataset you'd use to confirm it, you haven't confirmed anything. Track forward performance separately.
- **Track the counterfactual.** Store filtered predictions at conviction 2 (no bet) so you can always compare "what we did" vs "what we would have done."
- **One change at a time.** If you ship two filters in the same commit, you can't attribute the result to either. Stagger when possible.

## Documentation Paradigm (Backward → Present → Future)

Every commit, plan phase, and decision must answer three questions:

1. **Backward — Does anything break?** What existing behavior depends on this change? Tests, pipelines, dashboards affected? Rollback plan?
2. **Present — What is the plan?** What exactly is changing? Files touched? Expected output? Decision gate (GO/NO-GO criteria)?
3. **Future — Where does this surface?** Where will this appear? (dashboard, daily report, docs) What downstream work does this enable/block? When do we revisit?

Apply to: commit messages (1 line each), phase summaries, decision gates, session logs.

## Project Health Check

When asked "how are we doing?", "check the project", "what's the status", or similar:

1. `git pull` — always first
2. Read the latest file in `docs/daily/` — yesterday's WR, P&L, alerts, trade execution, circuit breaker status
3. `python3 src/optimization_tracker.py summary` — are active optimizations improving or regressing?
4. Check the kanban board: `gh issue list --repo mariomerinom/polymarket-bot --state open --label decision,optimization --json number,title,labels`
   - Any cards in "Ready"? Those need action NOW
   - Any optimization revert candidates?
5. Read `docs/core/ROADMAP.md` — what's the current phase, what's next?
6. `python3 -m pytest tests/ -v` — are tests passing?
7. Check VPS engine status: `ssh root@134.209.196.239 "systemctl status botsy && tail -20 /home/botuser/polymarket-bot/logs/loop.log"`
8. Check trade execution — verify pipeline modes in logs (`mode=live` for BTC 5m, `mode=paper` for others). Check kill switch and circuit breaker status.
9. Update the board if anything changed: move cards, close resolved issues, create new ones

Report findings concisely. Flag anything that needs a decision.
