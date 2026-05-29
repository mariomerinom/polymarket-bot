# Postmortem - BOTSY Project Stand-Down (2026-05-29)

**Severity:** Sev-1 strategy / production-readiness failure. No confirmed live-capital loss in this stand-down window, but the system is not safe to promote.
**Status:** Standing down. Do not promote any pipeline to live capital from the current evidence base.
**Decision date:** 2026-05-29
**Primary impact:** BOTSY will stop being treated as an active production-candidate trading system until signal quality, execution evidence, and infrastructure contracts are rebuilt.
**Affected paths:** BTC 5m Polymarket execution, BTC/ETH/SOL/DOGE perp paper pipelines, Kalshi, daily/consolidated reporting, MCP evidence, orderbook freshness, readiness gates.

## Executive Summary

BOTSY is being stood down because the project no longer has a trustworthy path from signal to execution to promotion.

The immediate blocker is still the BTC 5m executable orderbook p95 problem. We improved diagnostics, added incremental Polymarket orderbook handling, REST snapshot seeding, dynamic subscription repair, provider-primary evidence plumbing, and readiness/reporting guardrails. Those changes improved visibility and safety, but they did not clear the execution freshness gate. The May 28 daily still showed BTC 5m executable orderbook age p95 at **8,783ms** against a **<2,000ms** promotion gate.

The broader reason is more important: the signal portfolio degraded while execution evidence stayed unresolved. Month-to-date MCP-canonical paper P&L was approximately **-$3,697.77** across 3,414 bets, and the main BTC 5m line was approximately **-$629.00** MTD on 354 bets. DOGE perps and Bybit were positive, but not enough to offset the broad negative cluster, and none should be promoted without a rebuilt execution evidence chain.

Standing down is the correct risk decision. The system produced useful research, tests, and operational lessons, but it is not a robust trading pipeline today.

## What Happened

The project began with a plausible BTC 5m thesis: a simple momentum rule had previously outperformed a failed contrarian version, and the system had a paper-first discipline. Over time, BOTSY expanded into several related surfaces:

- BTC 5m Polymarket.
- ETH 5m Polymarket.
- BTC 15m.
- Kalshi.
- Bybit and Hyperliquid perp-style paper pipelines for BTC, ETH, SOL, and DOGE.
- Shadow maker, delayed timing replay, Strategy Lab, and regime/signal cohorts.

The system generated a large amount of evidence, but the evidence chain was uneven. Signal metrics, paper P&L, order records, delayed candidates, orderbook freshness, and readiness verdicts often improved separately rather than proving one end-to-end production contract.

By late May, the clearest production candidate was still BTC 5m, but it remained blocked:

- 7-day signal EHR had turned negative in daily reporting.
- Execution sample was insufficient or unstable.
- Delayed FAK evidence had not accumulated enough paper attempts.
- True executable orderbook age p95 remained above the live canary gate.
- There were still orphan/integrity warnings.
- MCP and daily-report freshness did not fully agree.

Meanwhile, MTD performance showed broad negative drift:

| Group | MCP-canonical MTD P&L |
|---|---:|
| BTC-linked: `btc_5m`, `bybit`, `hl`, `kalshi`, `btc_15m` | -$1,892.47 |
| ETH: `eth_5m`, `eth_bybit`, `eth_hl` | -$1,405.30 |
| SOL: `sol_bybit`, `sol_hl` | -$1,150.00 |
| DOGE: `doge_bybit`, `doge_hl` | +$750.00 |
| **Total** | **-$3,697.77** |

The project had enough negative evidence to stop, but not enough clean execution evidence to promote anything.

## Evidence Snapshot

### May 28 Daily Report

The May 28 consolidated daily reported:

| Metric | Value |
|---|---:|
| Total bets | 40 |
| Aggregate WR | 45.0% |
| Total P&L | -$129.70 |
| Total wagered | $1,000.00 |
| Pipelines with resolved bets | 6 of 12 |

By asset:

| Asset | Bets | WR | P&L |
|---|---:|---:|---:|
| BTC | 22 | 45.5% | -$58.68 |
| ETH | 10 | 40.0% | -$71.02 |
| SOL | 8 | 50.0% | $0.00 |

BTC 5m itself was positive on the day:

| Metric | Value |
|---|---:|
| Bets | 5 |
| WR | 60.0% |
| P&L | +$16.32 |
| Signal EHR today | +0.1350 |
| Execution EHR today | -0.0350 |
| Signal EHR 7-day | -0.0216 |
| Execution EHR 7-day | +0.0296 |

But the readiness verdict remained blocked:

- `signal_ehr_not_positive (-0.0200)`
- `execution_ehr_insufficient_sample (0/10)`
- `btc5m_executable_orderbook_age_p95_too_high (8783)`
- `delayed_ehr_insufficient_sample (0/50)`
- `promotion_signal_ehr_below_threshold (-0.0200 < +0.0200)`

### Engine Health

The May 28 consolidated report showed:

| Metric | p95 |
|---|---:|
| Production dispatch latency | 23,539ms |
| Pipeline fanout | 23,420ms |
| Strategy Lab runtime | 1,532ms |
| True orderbook age | 84,434ms |
| BTC 5m executable orderbook age | 8,783ms |

Polymarket itself was visibly active:

- `book_events_24h`: 1,654,718
- `price_change_events_24h`: 45,881,260
- fresh/stale tokens now: 34/0
- tokens updated last 60s/5m: 34/34
- REST snapshot seed: 9,748/9,768 successful

The report's dominant freshness cause was still **missing snapshots before price_change**. That means the feed was not simply dead; the execution evidence lifecycle was still failing to prove a valid baseline snapshot plus fresh side-specific BBO at consumer-read time.

### Month-To-Date MCP Read

Using Botsy MCP daily rows summed for May only:

| Pipeline | MTD P&L |
|---|---:|
| `doge_bybit` | +$400.00 |
| `doge_hl` | +$350.00 |
| `bybit` | +$250.00 |
| `eth_5m` | -$155.30 |
| `hl` | -$500.00 |
| `sol_bybit` | -$550.00 |
| `eth_hl` | -$575.00 |
| `sol_hl` | -$600.00 |
| `btc_5m` | -$629.00 |
| `eth_bybit` | -$675.00 |
| `kalshi` | -$1,013.47 |
| `btc_15m` | $0.00 |

Overall:

- Bets: 3,414
- Wins / losses: 1,626W / 1,788L
- WR: 47.6%
- P&L: -$3,697.77

Important caveat: MCP pipeline overview showed several last prediction timestamps around 2026-05-26 while daily documents included 2026-05-28. That freshness mismatch is itself part of the stand-down rationale: promotion decisions cannot depend on evidence surfaces that disagree about recency.

## Impact

### What We Lost

- Time spent repeatedly patching the Polymarket freshness path without clearing the production gate.
- Confidence that paper signal results can be promoted through the current execution evidence chain.
- A clean BTC 5m production path for this project as currently designed.
- Confidence in cross-surface reporting when MCP and daily docs disagree about freshness.
- Operational simplicity; the project now has too many coupled surfaces for the level of evidence quality achieved.

### What We Did Not Lose

- No confirmed live-capital loss from the current stand-down decision.
- Historical paper data and daily reports remain useful research artifacts.
- Regression tests and guardrails remain useful.
- The orderbook/provider/readiness work remains salvageable as infrastructure learning.
- DOGE/bybit-positive signals remain research candidates, but not production candidates.

## Root Cause

The root cause is that BOTSY never achieved a robust execution evidence chain.

A production trading system needs one continuous proof:

> A prediction was eligible, the exact side-token executable book was fresh at decision time, the order path used that book, the terminal execution result was classified exactly once, and fresh runtime metrics surfaced the promotion verdict.

BOTSY had many parts of that chain, but not a reliable end-to-end invariant. The system could generate predictions, paper orders, daily reports, and freshness counters while still failing the exact proof needed for live promotion.

## Contributing Factors

1. **Execution evidence was treated as an observability problem for too long.** We added metrics and reports, but the core question remained unresolved: can the exact side-token book be proven fresh at the moment execution reads it?

2. **Paper performance and execution performance were allowed to drift apart.** Paper bets can validate signal shape, but they do not validate live CLOB liquidity, adverse selection, FAK fill semantics, or stale-book risk.

3. **The Polymarket orderbook path became too complicated to reason about confidently.** The system accumulated websocket events, snapshots, REST seeding, sidecars, disk IPC, delayed replay, vendor fallback, and readiness metrics. Each patch had local logic, but the overall lifecycle remained fragile.

4. **Signal expansion outpaced promotion discipline.** Perps, Kalshi, ETH/SOL/DOGE, Strategy Lab, timing replay, and shadow maker produced useful data, but they also widened the blast radius and review burden before one production-quality path had been proven.

5. **MCP/report freshness disagreement weakened trust.** The project rules correctly say MCP is source of truth, but daily docs contained newer-looking rows than MCP overview timestamps. That must be treated as an evidence integrity issue, not a minor reporting wrinkle.

6. **Weak lines were kept alive as research after their story was already clear.** Kalshi, ETH/SOL perps, HL, and ETH 5m had enough negative evidence to stop consuming operator attention earlier.

7. **Readiness was blocked, but the project kept optimizing around the block.** The system did fail closed, which is good. But repeated attempts to clear the p95 blocker did not produce a simpler architecture.

## Anti-Practices To Stop

| Anti-practice | Why it hurt | Replacement |
|---|---|---|
| Treating paper orders as promotion evidence | Paper cannot prove executable liquidity or fill quality | Require exact-side fresh book, FAK outcome, and reconciliation evidence |
| Continuing broad research while the primary execution path is red | More surfaces dilute attention from the critical blocker | Freeze expansions until one production path is proven |
| Patching freshness symptoms instead of replacing the lifecycle | Each fix improved one metric but left the end-to-end contract unclear | Rebuild the market-data/execution chain around explicit state transitions |
| Allowing evidence surfaces to disagree on recency | Operators cannot know which numbers are valid | Make MCP, daily reports, and runtime metrics share one freshness contract |
| Keeping stale or weak pipelines active by default | They consume review time and create false optionality | Pause weak lines aggressively; require reactivation criteria |
| Optimizing signal before execution is trustworthy | A better prediction still loses if execution evidence is stale | Gate all signal promotion on execution-chain health |
| Treating vendor data as a magic fix | Vendor data may improve freshness but does not solve evidence integrity alone | Use vendors only behind the same audit/fallback/readiness contract |
| Letting generated runtime state and source state coexist without friction | Auto-generated data can obscure source changes and evidence freshness | Separate runtime artifacts from source, or keep strict allowlists and freshness checks |

## Practices To Keep

- Paper-first discipline.
- Live canary gates that fail closed.
- Explicit kill switch and daily loss breaker.
- One regression test per incident.
- Daily and consolidated reporting.
- MCP-first evidence policy.
- Shadow experiments with registered baselines and revert criteria.
- The git auto-commit allowlist and bail marker guardrail.
- The instinct to stand down rather than promote through uncertainty.

## Final Decision

BOTSY should be stood down as a production-candidate trading project.

Until a restart decision is explicitly made:

- Do not promote BTC 5m to live canary.
- Do not promote DOGE, Bybit, Kalshi, ETH, SOL, or HL lines to live capital.
- Do not treat positive MTD pockets as production evidence.
- Do not add new signal optimizations to the current architecture.
- Preserve reports and data for research.
- Keep kill switches and paused modes in force.

## What Would Be Required To Resume

Resume only if the project is reframed as a rebuild, not a continuation.

### Minimum Architecture Requirements

1. One authoritative market-data service, not multiple loosely synchronized cache surfaces.
2. Explicit state machine for every executable opportunity:
   - prediction eligible
   - market/token resolved
   - provider evidence selected
   - exact side book fresh
   - order computed
   - order submitted or skipped
   - terminal result classified
   - P&L/outcome reconciled
3. Exact side-token evidence for YES and NO. No synthetic opposite-side execution proof.
4. Freshness measured at consumer-read time and attached to the order/candidate.
5. MCP, daily report, and readiness metrics all backed by the same freshness timestamp contract.
6. Runtime metrics schema versioning and fail-closed stale metrics checks.
7. Vendor data allowed only as a provider behind the same audit and disagreement gates.
8. Live canary separated from paper and shadow by explicit mode and hard stop criteria.

### Minimum Evidence Gates

Before any live canary:

- Full test suite green.
- MCP and daily reports agree on latest prediction recency.
- No unexplained conv>=3 orphan predictions.
- BTC 5m or chosen candidate line has positive signal EHR over a registered forward cohort.
- Execution EHR is non-negative over a meaningful sample.
- Exact chosen-source executable orderbook age p95 <2s.
- Vendor fallback and vendor/internal disagreement are below configured thresholds.
- Delayed or reactive FAK paper sample reaches its registered minimum.
- Feed status, disk, and deploy hook health are green.

### Restart Scope

A restart should pick one narrow lane:

- BTC 5m with rebuilt market-data/execution chain; or
- DOGE perp research promoted only to a new paper/canary design; or
- pure research archive with no production ambition.

Do not restart all pipelines at once.

## Follow-Up Actions

| Action | Owner | Status |
|---|---|---|
| Pause all pipelines / keep live canary disabled | Operator | Required |
| Preserve May daily and MCP evidence | Repo | Done by current reports |
| Resolve MCP vs daily freshness mismatch before future analysis | Future rebuild | Required |
| Archive or mark weak lines as stood down | Future cleanup | Required |
| Decide whether to rebuild one execution lane or archive project | Operator | Open |
| If rebuilding, write a new architecture design before code | Future rebuild | Required |

## Lesson

The most important lesson is simple:

> A signal is not a trading system. A trading system is a signal plus a trustworthy execution evidence chain.

BOTSY got much better at observing itself, but it did not prove that chain. Standing down preserves the learning and prevents a paper-research system from being mistaken for a production-ready one.
