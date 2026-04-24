# Session Logs

Working session summaries — what was built, shipped, learned, and kicked forward.

- [2026-04-23](2026-04-23.md) — V4 thesis decay documented, Phase 0 cross-venue arb shadow logger shipped, DO Inference LLM client + arb_classifier + v4_diagnosis (11 commits)
- [2026-04-21](2026-04-21.md) — FAK pilot day-1 postmortem (−$159, 11% WR), signal-EHR live gate added (layer 4), auto-restart hook deployed, shadow regime extended to BTC/ETH spot (3 commits)
- [2026-04-20](2026-04-20.md) — FAK live pilot activated on btc_5m, ETH VWAP graduated, SOL relative regime shadow shipped, shadow framework formalized (4 commits)
- [2026-04-18](2026-04-18.md) — btc_15m sunset (decision #7 executed), orphan alert made circuit-breaker-aware, Polymarket shadow resolver shipped
- [2026-04-17](2026-04-17.md) — Kalshi paused (architectural strike-reachability bug), perp HIGH_VOL gate expanded, intraday range gate shipped for BTC+ETH 5m
- [2026-04-16](2026-04-16.md) — Memory leak root-caused (glibc arenas), shadow maker Phase 1 shipped, EHR baseline (BTC +0.102 top 2%), consolidated 12-pipeline report
- [2026-04-15](2026-04-15.md) — VWAP mean-reversion graduated to perps (SOL/DOGE primary), ETH HIGH_VOL gate expanded to block all HV regimes
- [2026-04-14](2026-04-14.md) — P0 incident fix: SQLite WAL race condition corrupted 3 DBs; checkpoint-before-commit + gitignore WAL/SHM + DB restoration
- [2026-04-13](2026-04-13.md) — Data unification: Kraken→Coinbase swap, z-score fix, indicator snapshots across all pipelines, 6,306 predictions backfilled
- [2026-04-12](2026-04-12.md) — Strategy Lab parameter optimization: always-fire redesign, cross-symbol resolution bug fix, 3 new engineering lessons, HV/N gate modeling
- [2026-04-09](2026-04-09.md) — Biggest improvement day: Bybit rehabilitation, Kalshi resolution fix, HIGH_VOL gate across all 5m pipelines, 12 issues closed, full doc sweep (12 commits)
- [2026-04-07](2026-04-07.md) — Fill problem: Lever B (FOK→FAK + alpha cushion), fill_diagnostic wired, paper settlement fix, signal_pnl counterfactual tool, asset_daily regime metrics (5 commits)
- [2026-04-06](2026-04-06.md) — Incident response + major hardening: FOK execution, pipeline isolation, runtime state contract, breaker deadlock fix, dashboard health surfacing (22 commits)
- [2026-04-05](2026-04-05.md) — Massive build day: VPS websocket engine (38 commits), CLOB pricing fix, TDD refactoring Phase B complete, GitHub Actions retired
- [2026-04-04](2026-04-04.md) — Activity digest (auto-digest)
- [2026-04-03](2026-04-03-0902.md) — Unified completion of dynamic pipeline constants (timeouts, limits, SQLite configuration delays) & complete removal of legacy conviction.py architecture.
- [2026-04-02](2026-04-02.md) — Config centralization, fill rate fix, VWAP postmortem, pipeline control config (live/paper/paused), ETH moved to paper
- [2026-04-01](2026-04-01.md) — P0 break-fix day: CLOB SDK order_type removal killed 13 live orders; daily report git hardened with backup/reset/restore
- [2026-03-30](2026-03-30.md) — Full Part 6 build day: ETH pipeline, trade execution module, anomaly/Monte Carlo, shadow indicators, 15 commits
- [2026-03-29](2026-03-29.md) — Massive build day: Phase 6a CLOB, Kelly analysis, 15m CI fix, multi-asset plan, backtester, 17 commits
