---
name: review-decisions
description: >
  Audit the decision tracker against current data. Use when: user says
  "check decisions", "decision audit", "what's ready", "decision review",
  "any decisions triggered", or "/review-decisions". Queries pipeline databases
  to check which MONITORING decisions have crossed their thresholds, audits
  ACTIONED decisions for outcomes, and suggests new decisions for untracked patterns.
---

# Review Decisions

Audit `docs/core/decisions.md` against live data. Check which decisions have crossed their trigger thresholds, whether actioned decisions achieved their goals, and whether new patterns need tracking.

## Prerequisites

- **Always `git pull` first.**
- Decision tracker lives at `docs/core/decisions.md`.
- Each decision has a status: MONITORING, READY, ACTIONED, REVERTED, DEFERRED.

## Process

### 1. Pull latest and read decisions

```bash
cd /Users/mrmrnm-max/polymarket-bot
git pull --rebase || git pull
```

Read `docs/core/decisions.md` in full. Parse every decision entry, noting:
- Decision number and name
- Current status (MONITORING / READY / ACTIONED / etc.)
- Trigger condition (what data threshold promotes it to READY)
- Related pipeline and database

### 2. Query databases for each MONITORING decision

For each decision in MONITORING status, run the specific query against the appropriate database:

**Decision #2 — 0.50-0.70 price bucket WR**
```sql
-- data/predictions.db
SELECT COUNT(*) as bets,
  SUM(CASE WHEN (estimate>=0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0) THEN 1 ELSE 0 END) as wins
FROM predictions p JOIN markets m ON p.market_id=m.id
WHERE p.conviction_score>=3 AND m.resolved=1
  AND m.price_yes >= 0.50 AND m.price_yes < 0.70;
```

**Decision #4 — 15m UP direction WR**
```sql
-- data/predictions_15m.db
SELECT COUNT(*) as bets,
  SUM(CASE WHEN estimate>=0.5 AND outcome=1 THEN 1 ELSE 0 END) as wins
FROM predictions p JOIN markets m ON p.market_id=m.id
WHERE p.conviction_score>=3 AND m.resolved=1 AND p.estimate >= 0.5;
```

**Decision #5 — Sunset 15m pipeline**
```sql
-- data/predictions_15m.db
SELECT COUNT(*) as total_bets,
  MIN(predicted_at) as first_bet, MAX(predicted_at) as last_bet
FROM predictions WHERE conviction_score >= 3;
```

**Decision #11 — ATR/volatility filter**
```sql
-- data/predictions.db
SELECT p.regime, COUNT(*) as bets,
  SUM(CASE WHEN (estimate>=0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0) THEN 1 ELSE 0 END) as wins
FROM predictions p JOIN markets m ON p.market_id=m.id
WHERE p.conviction_score>=3 AND m.resolved=1
GROUP BY p.regime;
```

**Decision #16 — ETH regime thresholds**
```sql
-- data/predictions_eth.db
SELECT p.regime, COUNT(*) as total,
  ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM predictions), 1) as pct
FROM predictions p
GROUP BY p.regime;
```

**Decision #17 — Paper-to-live WR degradation**
```sql
-- data/predictions.db (orders table)
SELECT COUNT(*) as live_bets,
  SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
  SUM(pnl) as total_pnl
FROM orders WHERE mode='live' AND status IN ('won', 'lost', 'filled');
```

For any other MONITORING decisions not listed above, construct the appropriate query based on the decision's trigger condition.

### 3. Evaluate ACTIONED decisions

For each decision in ACTIONED status:
- What was the expected outcome?
- Has enough time/data passed to evaluate?
- Did the action achieve the expected result?
- If not, should it be reverted or re-monitored?

### 4. Cross-reference with optimizations

```bash
python3 src/optimization_tracker.py summary
```

Check if any active optimization maps to a decision. If an optimization's revert condition is triggered, that may also trigger the related decision.

### 5. Produce the audit report

#### Newly READY
Decisions that have crossed their trigger threshold. Include:
- Decision number and name
- Trigger condition and current value
- Data query and results
- Recommended action

#### Progress Report
MONITORING decisions with current data vs threshold:

```
| # | Decision | Threshold | Current | Progress | ETA |
|---|----------|-----------|---------|----------|-----|
| 2 | 0.50-0.70 bucket | WR < 55% at 50 bets | 57% at 38 bets | 76% | ~3 days |
```

#### Post-Action Audit
ACTIONED decisions with outcome:

```
| # | Decision | Action Taken | Expected | Actual | Verdict |
|---|----------|-------------|----------|--------|---------|
| 7 | Dead hours | Filtered UTC 3,21 | WR +3% | WR +4.2% | ✅ Validated |
```

#### Suggested New Decisions
Patterns observed in the data that don't have a decision yet. For each:
- What the pattern is
- What data supports it
- Proposed trigger condition
- Proposed action

## Key Rules

- **Data, not feelings.** Every claim must have a SQL query and result.
- **Respect sample size.** If a decision's data pool is < 50 bets, report progress but don't declare it READY.
- **Don't action decisions unilaterally.** This skill REPORTS which decisions are ready. The user decides whether to act.
- **Update decisions.md only when asked.** The audit output is informational. Changing decision statuses requires explicit user approval.
- **Connect to optimizations.** If a decision and an optimization track the same metric, flag the overlap.
