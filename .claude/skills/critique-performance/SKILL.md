---
name: critique-performance
description: >
  Deep trading performance analysis using an agent team. Spawns 4 specialized
  analysts who each investigate a different dimension of performance and then
  share findings. Use when: user says "critique performance", "how are we doing",
  "performance review", "analyze trading", "edge check", "WR analysis",
  "what's working", or "/critique-performance".
---

# Critique Performance — Agent Team

Deep analytical critique of trading performance using a team of 4 specialized analysts. Each analyst investigates a different dimension of performance independently, then they share and challenge findings before the lead synthesizes recommendations.

This uses Claude Code's [agent teams](https://code.claude.com/docs/en/agent-teams) feature.

## Prerequisites

- **Agent teams must be enabled.** `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in settings or env.
- **Always `git pull` first.** CI auto-commits every ~5 minutes. Stale data = wrong conclusions.
- All 4 pipeline DBs must exist (committed to repo).

## Team Structure

Create an agent team with **4 analyst teammates**. Each analyzes ALL pipelines but through their specific lens.

```
Create an agent team to do a deep performance critique of our trading bot.
Spawn 4 analyst teammates:

Teammate 1 — "edge-optimizer": Your job is to extract maximum value from what's
  CURRENTLY WORKING. Audit every component in the bet pipeline end-to-end:
  prediction signal quality, regime classification accuracy, conviction scoring
  calibration, direction bias, price bucket performance, and hour-of-day patterns.

  For each component, answer: Is this adding edge or destroying it?

  Break down WR by every dimension available:
  - Regime (TRENDING/NEUTRAL/MEAN_REVERTING × LOW/MEDIUM/HIGH_VOL)
  - Direction (UP vs DOWN)
  - Price bucket (0.15-0.30, 0.30-0.50, 0.50-0.70, 0.70-0.85)
  - Conviction tier (0-5)
  - Hour of day (UTC)
  - Rolling 7d and 30d WR trends
  - Brier score (prediction calibration)

  Compare across pipelines — is BTC 5m edge holding while 15m decays?
  Does ETH show different regime patterns than BTC?

  Query ALL 4 databases:
  - data/predictions.db (BTC 5m — PRODUCTION)
  - data/predictions_15m.db (BTC 15m — paper)
  - data/predictions_eth.db (ETH 5m — paper)
  - data/predictions_kalshi.db (Kalshi — paper)

  Key SQL patterns:
  ```sql
  -- Per-regime WR
  SELECT p.regime, COUNT(*) as bets,
    SUM(CASE WHEN (estimate>=0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0) THEN 1 ELSE 0 END) as wins
  FROM predictions p JOIN markets m ON p.market_id=m.id
  WHERE p.conviction_score>=3 AND m.resolved=1
  GROUP BY p.regime;

  -- Rolling 7d WR
  SELECT date(predicted_at) as d, COUNT(*) as n,
    SUM(CASE WHEN (estimate>=0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0) THEN 1 ELSE 0 END) as wins
  FROM predictions p JOIN markets m ON p.market_id=m.id
  WHERE p.conviction_score>=3 AND m.resolved=1
  GROUP BY d ORDER BY d DESC LIMIT 7;

  -- Brier score
  SELECT AVG((estimate - outcome) * (estimate - outcome)) as avg_brier
  FROM predictions p JOIN markets m ON p.market_id=m.id
  WHERE p.conviction_score>=3 AND m.resolved=1;
  ```

  Also read: docs/core/strategy.md, docs/optimizations.json,
  last 3 daily reports from docs/daily/.

  Deliverable: Component-by-component scorecard showing where edge comes from
  and where it leaks. Identify the TOP 3 value drivers and TOP 3 value destroyers.

Teammate 2 — "conviction-analyst": Your job is to analyze MEDIUM CONVICTION
  bets (conviction_score = 2) that we currently SKIP. The question is: is there
  real signal hiding in the conv-2 pool that we're leaving on the table?

  THIS IS NOT ABOUT FORCING AN ANSWER. If conv-2 bets are genuinely noise,
  say so. Objectiveness is the only thing that matters here. Spotting real
  signal — or confirming its absence — is the secret.

  Analysis:
  1. What is the WR of conviction=2 predictions? (These are our counterfactual)
  2. Break down conv-2 WR by regime, direction, price bucket, hour
  3. Are there SPECIFIC SUBSETS of conv-2 that perform like conv-3+?
     Example: conv=2 in TRENDING+HIGH_VOL might be 65% WR while
     conv=2 in NEUTRAL is 48%. That's actionable.
  4. What additional signals would promote a conv-2 to conv-3?
     Check shadow indicators (RSI, OBV, VWAP) in the reasoning column.
  5. Compare conv-2 WR to conv-3 WR within each regime.
     If they're nearly equal in some regime, the conviction gate is miscalibrated there.
  6. What's the P&L impact if we promoted the best conv-2 subset to bets?

  Key queries:
  ```sql
  -- Conv-2 overall WR (counterfactual)
  SELECT COUNT(*) as skipped,
    SUM(CASE WHEN (estimate>=0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0) THEN 1 ELSE 0 END) as would_have_won
  FROM predictions p JOIN markets m ON p.market_id=m.id
  WHERE p.conviction_score=2 AND m.resolved=1;

  -- Conv-2 vs Conv-3+ by regime
  SELECT p.regime, p.conviction_score,
    COUNT(*) as n,
    SUM(CASE WHEN (estimate>=0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0) THEN 1 ELSE 0 END) as wins
  FROM predictions p JOIN markets m ON p.market_id=m.id
  WHERE p.conviction_score IN (2, 3, 4, 5) AND m.resolved=1
  GROUP BY p.regime, p.conviction_score;

  -- Conv-2 by direction × regime
  SELECT p.regime,
    CASE WHEN estimate>=0.5 THEN 'UP' ELSE 'DOWN' END as direction,
    COUNT(*) as n,
    SUM(CASE WHEN (estimate>=0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0) THEN 1 ELSE 0 END) as wins
  FROM predictions p JOIN markets m ON p.market_id=m.id
  WHERE p.conviction_score=2 AND m.resolved=1
  GROUP BY p.regime, direction;

  -- Shadow indicators in conv-2 reasoning
  SELECT COUNT(*) FROM predictions WHERE conviction_score=2 AND reasoning LIKE '%RSI%';
  SELECT COUNT(*) FROM predictions WHERE conviction_score=2 AND reasoning LIKE '%OBV%';
  ```

  Also read: docs/core/strategy.md (current conviction logic),
  docs/specs/spec_generic_conviction_engine.md (planned conviction redesign).

  Deliverable: Honest assessment of conv-2 signal quality. If there ARE
  promotable subsets, specify exact criteria. If not, say "conv-2 is correctly
  filtered" with data proof. Include sample sizes for every claim.

Teammate 3 — "opportunity-scout": Your job is to find MISSED OPPORTUNITIES.
  Look at bets we passed on entirely — not just conv-2 (that's the conviction-analyst's
  job), but predictions we never even made. Gaps in coverage.

  Questions to investigate:
  1. Are there market hours where we make NO predictions but outcomes are predictable?
  2. Are there regimes we filter out that actually have edge?
     Query predictions with conv=0 and conv=1 — what's their WR?
  3. What do the specs in docs/specs/ promise? Is there shadow data supporting
     any of them? (This is different from review-specs — you're looking at this
     through a performance lens, not a spec quality lens.)
  4. Cross-pipeline comparison: Does ETH show edge where BTC doesn't, or vice versa?
     Any patterns in one pipeline that could transfer to another?
  5. Are there market conditions (time of day, day of week, volatility events)
     where we consistently sit out but shouldn't?
  6. Read docs/research/pattern_mining_results.md — are there validated patterns
     we're not exploiting?

  Key queries:
  ```sql
  -- Conv 0-1 WR (things we completely skip)
  SELECT p.conviction_score,
    COUNT(*) as n,
    SUM(CASE WHEN (estimate>=0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0) THEN 1 ELSE 0 END) as wins
  FROM predictions p JOIN markets m ON p.market_id=m.id
  WHERE p.conviction_score IN (0, 1) AND m.resolved=1
  GROUP BY p.conviction_score;

  -- Skip reasons from orders table
  SELECT reason, COUNT(*) as skips
  FROM orders WHERE status='skipped'
  GROUP BY reason ORDER BY skips DESC;

  -- Hour coverage gaps (hours with 0 bets but predictions exist)
  SELECT CAST(strftime('%H', predicted_at) AS INTEGER) as hour_utc,
    COUNT(*) as predictions,
    SUM(CASE WHEN conviction_score >= 3 THEN 1 ELSE 0 END) as bets
  FROM predictions
  GROUP BY hour_utc ORDER BY hour_utc;

  -- Filtered regimes WR
  SELECT p.regime,
    COUNT(*) as n,
    SUM(CASE WHEN (estimate>=0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0) THEN 1 ELSE 0 END) as wins
  FROM predictions p JOIN markets m ON p.market_id=m.id
  WHERE p.conviction_score < 3 AND m.resolved=1
  GROUP BY p.regime;
  ```

  Also read: docs/specs/ (all spec files), docs/research/pattern_mining_results.md,
  docs/research/outcome_analysis_bitcoin.md, docs/research/outcome_analysis_ethereum.md,
  docs/core/decisions.md (any decisions about coverage expansion).

  Deliverable: List of specific missed opportunities ranked by estimated impact,
  with data backing each claim. For each opportunity: what it is, how much edge
  exists (with sample size), and what it would take to capture it.

Teammate 4 — "execution-auditor": Your job is to analyze the gap between
  PREDICTION QUALITY and TRADING PROFIT. A perfect prediction that executes
  poorly is still a losing trade.

  Focus areas:
  1. Slippage cost analysis — how much edge do we give away on execution?
     - Average slippage per order (slippage_pct column in orders table)
     - Total slippage cost = avg_slippage × num_orders × avg_size
     - Slippage by direction (UP vs DOWN — do we overpay more on one side?)
     - Slippage before vs after the MAX_SLIPPAGE_SPREAD cap (recent change)
  2. Fill rate — what percentage of placed orders actually fill?
     - Orders placed vs filled vs expired vs failed
     - Are we pricing too tight (no fills) or too loose (slippage)?
  3. Paper-to-live degradation (Decision #17)
     - Paper WR vs live WR on the same markets
     - If there's a gap: is it slippage, timing, or selection?
  4. Partial fill analysis — are we getting full size or fragments?
  5. Order timing — any correlation between time-to-fill and outcome?
  6. Circuit breaker proximity — how close have we gotten to limits?
     - Daily P&L trajectory toward $300 daily loss limit
     - Consecutive loss streaks (max 5 before halt)
     - Max drawdown % from peak
  7. Real USDC P&L from Polymarket wallet vs simulated P&L in DB

  Key queries:
  ```sql
  -- Slippage analysis
  SELECT COUNT(*) as orders,
    ROUND(AVG(slippage_pct), 4) as avg_slippage,
    ROUND(MAX(slippage_pct), 4) as max_slippage,
    ROUND(MIN(slippage_pct), 4) as min_slippage
  FROM orders WHERE mode='live';

  -- Fill rate
  SELECT status, COUNT(*) as n FROM orders WHERE mode='live' GROUP BY status;

  -- Slippage by direction
  SELECT direction,
    COUNT(*) as n,
    ROUND(AVG(slippage_pct), 4) as avg_slip
  FROM orders WHERE mode='live'
  GROUP BY direction;

  -- Daily P&L trajectory
  SELECT date(placed_at) as d,
    SUM(pnl) as daily_pnl,
    COUNT(*) as trades
  FROM orders WHERE mode='live' AND pnl IS NOT NULL
  GROUP BY d ORDER BY d;

  -- Consecutive losses
  SELECT placed_at, pnl FROM orders
  WHERE mode='live' AND pnl IS NOT NULL
  ORDER BY placed_at;
  ```

  Also run:
  ```bash
  python3 -c "
  import sys; sys.path.insert(0, 'src')
  from polymarket_pnl import fetch_real_pnl
  import sqlite3
  db = sqlite3.connect('data/predictions.db'); db.row_factory = sqlite3.Row
  result = fetch_real_pnl(db)
  print(result)
  db.close()
  "
  ```

  Also read: docs/analysis/thesis_paper_to_live_degradation.md (if it exists),
  docs/core/decisions.md (Decision #17 specifically).

  Deliverable: Execution quality report with: total slippage cost in dollars,
  fill rate percentage, paper-to-live WR gap (with sample sizes), risk
  exposure summary, and 1-3 specific execution improvements ranked by
  dollar impact.
```

## Process

### 1. Pull latest

```bash
cd /Users/mrmrnm-max/polymarket-bot
git pull --rebase || git pull
```

### 2. Spawn the agent team

Create the team with the 4 analysts above. Key coordination instructions:

```
After all 4 analysts complete their independent investigation, have them
share findings with each other in this order:

1. edge-optimizer shares: which components are adding vs destroying edge
2. execution-auditor shares: how much edge is lost to execution
3. conviction-analyst shares: whether conv-2 has real signal or not
4. opportunity-scout shares: what opportunities we're missing

Then have each analyst respond to the others' findings:
- edge-optimizer: does the execution audit explain any of my "edge destroyers"?
- conviction-analyst: do the opportunity scout's missed patterns overlap with conv-2 subsets?
- opportunity-scout: do any of my missed opportunities conflict with what's currently working?
- execution-auditor: would capturing more opportunities (scout/conviction) make execution worse?

Finally, synthesize all 4 perspectives into a unified critique.
```

### 3. Databases and Data Sources

| Pipeline | DB Path | Status | Orders Table? |
|----------|---------|--------|--------------|
| BTC 5m | `data/predictions.db` | **Production** | Yes (live orders) |
| BTC 15m | `data/predictions_15m.db` | Paper | No |
| ETH 5m | `data/predictions_eth.db` | Paper | Yes (live orders starting Apr 2) |
| Kalshi | `data/predictions_kalshi.db` | Paper | No |

Additional data sources:
- Real USDC P&L: `src/polymarket_pnl.py` → Polymarket Data API
- Optimization status: `python3 src/optimization_tracker.py summary`
- Daily reports: `docs/daily/` (last 3-5 files)
- Decision tracker: `docs/core/decisions.md`
- Strategy reference: `docs/core/strategy.md`
- Research: `docs/research/pattern_mining_results.md`, `docs/research/outcome_analysis_*.md`

### 4. Cross-Analysis Phase

After independent investigations, the analysts cross-pollinate. This is where agent teams shine — the edge-optimizer might identify a "value destroyer" that the execution-auditor explains as slippage, or the conviction-analyst might find a conv-2 subset that the opportunity-scout also identified as a gap.

Key cross-analysis questions:
- **Edge × Execution**: Are our best-performing regimes also our best-executing? Or are we winning despite bad execution?
- **Conviction × Opportunity**: Is the conv-2 pool hiding the same patterns the opportunity-scout found?
- **Execution × Opportunity**: If we expanded coverage, would execution quality degrade (more bets = more slippage)?
- **Edge × Conviction**: Are conv-3 bets uniformly better than conv-2, or only in specific regimes?

### 5. Lead Synthesizes Final Critique

The lead produces a structured critique with these sections:

#### Edge Status
Overall health of the trading edge across all pipelines. 7d/30d trends. Sample size adequacy.

#### Component Scorecard (from edge-optimizer)
| Component | Status | Edge Impact | Notes |
|-----------|--------|-------------|-------|
| Regime classification | ✅/⚠️/🔴 | +X% / -X% | ... |
| Direction signal | ✅/⚠️/🔴 | +X% / -X% | ... |
| Conviction scoring | ✅/⚠️/🔴 | +X% / -X% | ... |
| Price bucket gate | ✅/⚠️/🔴 | +X% / -X% | ... |
| Hour-of-day gate | ✅/⚠️/🔴 | +X% / -X% | ... |

#### Conviction Gate Analysis (from conviction-analyst)
- Conv-2 overall WR vs conv-3+ WR
- Promotable subsets (if any) with exact criteria and sample sizes
- Verdict: "Conv-2 is correctly filtered" OR "These specific conv-2 subsets deserve promotion"

#### Missed Opportunities (from opportunity-scout)
Ranked list with estimated impact and data proof. Each entry:
- What it is
- WR data (with sample size)
- What it would take to capture
- Whether it conflicts with current edge

#### Execution Quality (from execution-auditor)
- Total slippage cost ($)
- Fill rate (%)
- Paper-to-live WR gap
- Risk exposure (circuit breaker proximity, consecutive losses, drawdown)

#### Cross-Analysis Insights
Key findings that only emerged from the analysts comparing notes.

#### Recommendations
Ranked list of 1-5 actionable next steps. Each must include:
- Which analyst surfaced it
- Supporting data (with sample sizes)
- Expected impact (WR change or $ impact)
- Implementation path (link to spec if applicable)
- Risk if we DON'T act

### 6. Clean up the team

```
Ask all teammates to shut down, then clean up the team.
```

## Key Rules

- **No agent bias.** Report numbers honestly. Don't spin bad results as good.
- **No forced answers.** Especially for conviction-analyst — "no actionable signal found" is a valid and valuable conclusion. Better to say nothing than to manufacture a false positive.
- **Minimum 50 bets before declaring anything.** Per CLAUDE.md validation principles. If a slice has < 50 bets, report it as "insufficient data" not "promising trend."
- **Compare to baseline, not to zero.** The BTC 5m paper baseline is ~67% WR.
- **Sample sizes on every claim.** "65% WR" means nothing without "(on N bets)."
- **Be specific.** "WR is down" is useless. "UP direction WR dropped from 72% to 58% over 7 days in HIGH_VOL regime (23 bets)" is actionable.
- **Dollar impact > percentage points.** A 2% WR improvement on 200 bets at $25 = $100. A 10% improvement on 5 bets = $12.50. Prioritize by dollar impact.
- **Analysts are read-only.** No teammate should modify any files. This is analysis, not implementation.

## Fallback: Single-Agent Mode

If agent teams are not enabled, fall back to sequential analysis:

1. Launch 3 Explore subagents in parallel:
   - Agent 1: edge + execution analysis (combines teammates 1 and 4)
   - Agent 2: conviction analysis (teammate 2)
   - Agent 3: opportunity analysis (teammate 3)
2. Synthesize findings yourself
3. Note in output that cross-analysis phase was limited (no inter-agent debate)
