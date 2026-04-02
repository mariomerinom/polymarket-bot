---
name: critique-performance
description: >
  Deep trading performance analysis across all pipelines. Use when: user says
  "critique performance", "how are we doing", "performance review", "analyze trading",
  "edge check", "WR analysis", "what's working", or "/critique-performance".
  Goes beyond the daily report by identifying trends, regime shifts, edge decay,
  and producing ranked actionable recommendations.
---

# Critique Performance

Deep analytical critique of trading performance across all pipelines. The daily report gives you numbers — this skill tells you what they mean and what to do about them.

## Prerequisites

- **Always `git pull` first.** CI auto-commits every ~5 minutes. Stale data = wrong conclusions.
- All 4 pipeline DBs must exist (they're committed to the repo).

## Process

### 1. Pull latest data

```bash
cd /Users/mrmrnm-max/polymarket-bot
git pull --rebase || git pull
```

### 2. Query all 4 pipeline databases

For each database, run the same core queries:

| Pipeline | DB Path | Status |
|----------|---------|--------|
| BTC 5m | `data/predictions.db` | **Production** (real money) |
| BTC 15m | `data/predictions_15m.db` | Paper |
| ETH 5m | `data/predictions_eth.db` | Paper |
| Kalshi | `data/predictions_kalshi.db` | Paper |

**Core queries per pipeline:**

```sql
-- Overall stats (conviction >= 3 = bets)
SELECT COUNT(*) as bets,
  SUM(CASE WHEN (estimate>=0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0) THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN (estimate>=0.5 AND outcome=0) OR (estimate<0.5 AND outcome=1) THEN 1 ELSE 0 END) as losses
FROM predictions p JOIN markets m ON p.market_id=m.id
WHERE p.conviction_score>=3 AND m.resolved=1;

-- Rolling 7-day WR
SELECT date(predicted_at) as d, COUNT(*) as n,
  SUM(CASE WHEN (estimate>=0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0) THEN 1 ELSE 0 END) as wins
FROM predictions p JOIN markets m ON p.market_id=m.id
WHERE p.conviction_score>=3 AND m.resolved=1
GROUP BY d ORDER BY d DESC LIMIT 7;

-- Regime breakdown
SELECT p.regime,
  COUNT(*) as bets,
  SUM(CASE WHEN (estimate>=0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0) THEN 1 ELSE 0 END) as wins
FROM predictions p JOIN markets m ON p.market_id=m.id
WHERE p.conviction_score>=3 AND m.resolved=1
GROUP BY p.regime;

-- Direction breakdown
SELECT CASE WHEN estimate>=0.5 THEN 'UP' ELSE 'DOWN' END as direction,
  COUNT(*) as bets,
  SUM(CASE WHEN (estimate>=0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0) THEN 1 ELSE 0 END) as wins
FROM predictions p JOIN markets m ON p.market_id=m.id
WHERE p.conviction_score>=3 AND m.resolved=1
GROUP BY direction;

-- Price bucket breakdown
SELECT CASE
  WHEN m.price_yes < 0.30 THEN '0.15-0.30'
  WHEN m.price_yes < 0.50 THEN '0.30-0.50'
  WHEN m.price_yes < 0.70 THEN '0.50-0.70'
  ELSE '0.70-0.85' END as bucket,
  COUNT(*) as bets,
  SUM(CASE WHEN (estimate>=0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0) THEN 1 ELSE 0 END) as wins
FROM predictions p JOIN markets m ON p.market_id=m.id
WHERE p.conviction_score>=3 AND m.resolved=1
GROUP BY bucket;

-- Conviction tier breakdown
SELECT p.conviction_score,
  COUNT(*) as bets,
  SUM(CASE WHEN (estimate>=0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0) THEN 1 ELSE 0 END) as wins
FROM predictions p JOIN markets m ON p.market_id=m.id
WHERE m.resolved=1
GROUP BY p.conviction_score;

-- Hour-of-day WR (UTC)
SELECT CAST(strftime('%H', predicted_at) AS INTEGER) as hour_utc,
  COUNT(*) as bets,
  SUM(CASE WHEN (estimate>=0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0) THEN 1 ELSE 0 END) as wins
FROM predictions p JOIN markets m ON p.market_id=m.id
WHERE p.conviction_score>=3 AND m.resolved=1
GROUP BY hour_utc ORDER BY hour_utc;

-- Brier score
SELECT AVG((estimate - outcome) * (estimate - outcome)) as avg_brier
FROM predictions p JOIN markets m ON p.market_id=m.id
WHERE p.conviction_score>=3 AND m.resolved=1;
```

### 3. BTC 5m production-specific analysis

For the live trading pipeline only:

```sql
-- Slippage analysis from orders table
SELECT COUNT(*) as orders,
  AVG(slippage_pct) as avg_slippage,
  MAX(slippage_pct) as max_slippage,
  SUM(CASE WHEN status='filled' THEN 1 ELSE 0 END) as fills,
  SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending
FROM orders WHERE mode='live';

-- Today's P&L vs circuit breaker
SELECT SUM(pnl) as daily_pnl FROM orders
WHERE mode='live' AND date(placed_at) = date('now');
```

Also fetch real USDC P&L:
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

### 4. Gather context

```bash
python3 src/optimization_tracker.py summary
```

Read these files for trend context:
- Last 3-5 files in `docs/daily/` (sorted by date)
- `docs/core/decisions.md` — check for threshold crossings
- `docs/core/strategy.md` — current signal logic for reference

### 5. Produce the critique

Structure the output with these sections:

#### Edge Status
- Is the edge holding? Compare current 7d rolling WR to the 67% paper baseline.
- WR trend direction: improving, stable, or decaying?
- Sample size: is it large enough to trust? (50-bet minimum per CLAUDE.md)

#### What's Working
- Best-performing regimes, directions, price buckets, conviction tiers
- Any segments significantly above average?

#### What's Failing
- Worst segments (WR < 50% in any slice = losing money there)
- Dead hours (UTC hours with WR < 50%)
- Edge decay signals (rolling WR declining 3+ consecutive days)

#### Live vs Paper Gap (BTC 5m only)
- Paper WR vs live WR
- Simulated P&L vs real USDC P&L
- Slippage impact: avg slippage × bet count = total slippage cost
- Fill rate: what % of placed orders actually fill?

#### Risk Check
- Today's P&L vs $300 daily loss limit
- Consecutive losses (max 5 before circuit breaker)
- Drawdown % from peak equity
- Concentration risk: are too many bets in one regime/direction?

#### Decision Triggers
- Which decisions in `docs/core/decisions.md` have crossed their thresholds?
- Reference specific decision numbers and current data vs trigger value.

#### Recommendations
- Ranked list of 1-3 actionable next steps
- Each recommendation should reference: the data that supports it, the specific action, and the expected impact
- If a recommendation maps to an existing spec in `docs/specs/`, link it

## Key Rules

- **No agent bias.** Report numbers honestly. Don't spin bad results as good.
- **Minimum 50 bets before declaring anything.** Per CLAUDE.md validation principles.
- **Compare to baseline, not to zero.** The BTC 5m paper baseline is ~67% WR. An edge is only an edge if it beats the market.
- **Flag counterfactual data.** Conviction 2 (skip) predictions are the control group — include their WR when relevant.
- **Be specific.** "WR is down" is useless. "UP direction WR dropped from 72% to 58% over 7 days in HIGH_VOL regime" is actionable.
