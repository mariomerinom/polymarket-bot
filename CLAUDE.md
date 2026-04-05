# Project Rules

## GitHub Is the Source of Truth

1. **Always `git pull` before reading any data file** (especially `data/predictions.db`). The CI pipeline auto-commits every ~5 minutes — local state goes stale fast.
2. **Never analyze local DB without pulling first.** If you report numbers, they must match what the live dashboard shows.
3. **Always push after making changes.** A change that isn't on GitHub doesn't exist.
4. **Expect CI conflicts on push.** The self-rescheduling pipeline commits constantly. Always `git pull --rebase` before pushing. If the DB conflicts, our code changes win (CI will regenerate the DB).
5. **The dashboard (GitHub Pages) is the canonical view.** If the dashboard shows different numbers than a local query, the dashboard is right and your local data is stale.

## Development Process

- Run `pytest tests/ -v` before every commit. Tests gate CI — a broken push stops the pipeline.
- Never skip pre-commit hooks.
- Document production incidents in `docs/ops/BREAK_FIX_LOG.md`.
- Add a regression test for every fix.

## Bot Design

- **No agent bias.** The bot must not have built-in directional bias (UP or DOWN). All bias comes from human macro config, not prompts or code.
- **BTC strategy is MOMENTUM (ride streaks).** V3 contrarian lost at 37% WR on live Polymarket. Inverting to momentum validated at 63% WR. Do NOT revert BTC signal direction. Streak UP → predict UP. Streak DOWN → predict DOWN.
- **ETH strategy is MOMENTUM (ride streaks).** Contrarian validated at 54.4% in pattern mining but lost at 33.3% WR on 54 live predictions. Momentum counterfactual: 66.7% on same bets. Flipped 2026-04-01. Same V3→V4 pattern as BTC. Do NOT revert to contrarian. ETH pipeline is in `src/predict_eth.py` (paper trading, conviction=2).
- **Paper trade first.** Every new signal must accumulate 200+ resolved predictions in paper trading before risking real capital.
- **Conviction gates real money.** Only conviction >= 3 places bets. Conviction 0-2 = skip.
- **Trade execution is in `src/trade.py`.** Two modes: `TRADING_ENABLED=false` (default, paper) logs what it would do; `TRADING_ENABLED=true` places real limit orders via `py-clob-client` SDK on Polygon. Flat $25 bet size. Kill switch via `KILL_SWITCH=true` env var or `data/KILL_SWITCH` file. Daily loss circuit breaker at $300 (env `DAILY_LOSS_LIMIT`). Thin book guard caps bets at 90% of CLOB max@2% slippage.

## Multi-Pipeline Architecture

Four independent pipelines run in parallel, each with its own workflow, database, and dashboard:

| Pipeline | Workflow | DB | Dashboard | Signal | Status |
|----------|----------|----|-----------|--------|--------|
| BTC 5m | `predict-and-score.yml` | `predictions.db` | `docs/index.html` | Momentum | **Production** |
| BTC 15m | `predict-15m.yml` | `predictions_15m.db` | `docs/15m.html` | Momentum | Paper |
| ETH 5m | `predict-eth-5m.yml` | `predictions_eth.db` | `docs/eth.html` | Momentum | Paper |
| Kalshi BTC | `predict-kalshi.yml` | `predictions_kalshi.db` | `docs/kalshi.html` | Momentum | Paper (Phase 0) |

All three dashboards are cross-linked via a nav bar on GitHub Pages.

### CI Conflict Resolution

All workflows use `git pull --rebase -X theirs` with fallback to merge pull. CI-generated files (`optimizations.json`, dashboard HTML) are regenerated every cycle, so accepting the remote version on conflict is safe.

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

### Core (`docs/core/`) — project rules, strategy, roadmap

| Document | Goal |
|----------|------|
| `CLAUDE.md` | Project rules for Claude — source of truth for behavior |
| `docs/core/strategy.md` | Current trading strategy for all pipelines |
| `docs/core/PRIMER.md` | System overview, repo map, onboarding |
| `docs/core/ROADMAP.md` | Project phases and validation gates |
| `docs/core/decisions.md` | Tracked decisions with automated triggers |
| `docs/core/TESTING.md` | Test strategy, layers, CI pipeline |
| `config/macro_bias.md` | Macro overlay config (not used in V4) |

### Operations (`docs/ops/`) — incidents, lessons learned

| Document | Goal |
|----------|------|
| `docs/ops/BREAK_FIX_LOG.md` | Production incident log |
| `docs/ops/ENGINEERING_LESSONS.md` | Evergreen operational lessons |

### Plans (`docs/plans/`) — active expansion plans

| Document | Goal |
|----------|------|
| `docs/plans/KALSHI_INTEGRATION_PLAN.md` | Kalshi venue expansion (Phase 0 active) |
| `docs/plans/multi-asset-plan.md` | Multi-asset expansion status and plan |

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

Active specs addressing the adverse selection / fill rate problem (Decision #24). The signal picks winners at 65%+ but orders expire before filling.

| Document | Goal |
|----------|------|
| `docs/specs/stochastic/spec_dynamic_price_cap.md` | Dynamic slippage spread (3¢-15¢) based on depth, spread, volume |
| `docs/specs/stochastic/spec_stochastic_entry_timing.md` | Stochastic Oscillator for entry timing within 5-min windows |
| `docs/specs/stochastic/spec_fill_diagnostic.md` | Fill diagnostic instrumentation (implemented in `src/fill_diagnostic.py`) |
| `docs/specs/stochastic/fill-implementation.md` | Fix adverse selection via CLOB websocket + IOC orders |
| `docs/specs/stochastic/spec_unified_vps_websocket.md` | Unified VPS + websocket architecture for live pricing |
| `docs/specs/stochastic/spec_bybit_vps_migration.md` | Bybit/Kalshi VPS migration (Phase 1 complete) |
| `docs/specs/stochastic/claude-fill-problem-consensus.md` | Multi-agent consensus on fill problem root cause and fixes |
| `docs/specs/stochastic/fill-problem-agreement-and-tension.md` | Agreement/tension analysis across fill problem proposals |
| `docs/specs/stochastic/gemini-fill-resolution.md` | External review of fill problem proposals |
| `docs/specs/stochastic/Spec: Optimal Fill Strategy v1 — Hybrid .md` | Hybrid optimal fill strategy combining multiple approaches |

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
4. Read `docs/core/decisions.md` — has anything moved to READY?
5. Read `docs/core/ROADMAP.md` — what's the current phase, what's next?
6. `python3 -m pytest tests/ -v` — are tests passing?
7. Check GitHub Actions — are all 3 pipelines (BTC 5m, BTC 15m, ETH 5m) running green?
8. Check trade execution — is `TRADING_ENABLED`? Any kill switch or circuit breaker trips?

Report findings concisely. Flag anything that needs a decision.
