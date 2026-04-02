---
name: health-check
description: >
  Quick operational health check of all trading pipelines. Use when: user says
  "health check", "is the bot running", "pipeline status", "system check",
  "any errors", "is it working", or "/health-check". Checks CI freshness,
  prediction recency, order fills, circuit breaker proximity, and test status.
  Produces a compact status dashboard in under 60 seconds.
---

# Health Check

Quick operational pulse across all 4 pipelines. Is the bot running? Are orders filling? Is the circuit breaker close? Any errors? This is the "is everything okay right now?" skill.

## Prerequisites

- **Always `git pull` first.**

## Process

### 1. Pull latest

```bash
cd /Users/mrmrnm-max/polymarket-bot
git pull --rebase || git pull
```

### 2. Check CI pipeline freshness

```bash
git log --oneline -10 --format="%H %ai %s" | head -10
```

Look for the most recent `Auto:` commit. Calculate how many minutes ago it was.
- BTC 5m: stale if > 10 minutes since last Auto commit
- BTC 15m: stale if > 20 minutes
- ETH 5m: stale if > 10 minutes
- Kalshi: stale if > 10 minutes

If the last Auto commit is >15 minutes old, check GitHub Actions:
```bash
gh run list --limit 5
```

### 3. Check prediction freshness per pipeline

```sql
-- For each database:
-- data/predictions.db (BTC 5m)
SELECT MAX(predicted_at) as last_prediction, COUNT(*) as total FROM predictions;

-- data/predictions_15m.db (BTC 15m)
SELECT MAX(predicted_at) as last_prediction, COUNT(*) as total FROM predictions;

-- data/predictions_eth.db (ETH 5m)
SELECT MAX(predicted_at) as last_prediction, COUNT(*) as total FROM predictions;

-- data/predictions_kalshi.db (Kalshi)
SELECT MAX(predicted_at) as last_prediction, COUNT(*) as total FROM predictions;
```

### 4. Check trade execution (BTC 5m + ETH 5m)

```sql
-- data/predictions.db — BTC 5m orders
SELECT
  COUNT(*) as total_orders,
  SUM(CASE WHEN mode='live' THEN 1 ELSE 0 END) as live_orders,
  SUM(CASE WHEN mode='live' AND status='filled' THEN 1 ELSE 0 END) as fills,
  SUM(CASE WHEN mode='live' AND status='pending' THEN 1 ELSE 0 END) as pending
FROM orders;

-- Today's live P&L
SELECT SUM(pnl) as daily_pnl FROM orders
WHERE mode='live' AND date(placed_at) = date('now');

-- Any orders stuck pending > 30 minutes?
SELECT COUNT(*) FROM orders
WHERE mode='live' AND status='pending'
  AND placed_at < datetime('now', '-30 minutes');
```

Repeat for ETH 5m (`data/predictions_eth.db`) if it has an orders table.

### 5. Check circuit breaker and kill switch

```bash
# Kill switch file check
test -f data/KILL_SWITCH && echo "KILL SWITCH ACTIVE" || echo "Kill switch: OFF"
```

Circuit breaker proximity:
- Daily P&L from step 4 vs $300 daily loss limit
- If P&L < -$200: CAUTION
- If P&L < -$250: CRITICAL

### 6. Check experiments

```bash
python3 src/optimization_tracker.py summary
```

Note: how many active, how many need attention (validated or revert candidate).

### 7. Run quick test

```bash
python3 -m pytest tests/ -v --tb=short 2>&1 | tail -5
```

### 8. Produce compact status dashboard

Format the output as:

```
Pipeline Health — YYYY-MM-DD HH:MM CST
═══════════════════════════════════════

BTC 5m  (PROD):   ✅ OK    Last: HH:MM UTC  |  Orders today: N  |  Fills: X/Y
BTC 15m (paper):  ✅ OK    Last: HH:MM UTC
ETH 5m  (paper):  ✅ OK    Last: HH:MM UTC  |  Orders today: N  |  Fills: X/Y
Kalshi  (paper):  ✅ OK    Last: HH:MM UTC

Circuit Breaker:  $X.XX / $300  (Y%)   ✅ OK
Kill Switch:      OFF
Consecutive Loss: N / 5                 ✅ OK
Tests:            NNN passed            ✅ OK
Experiments:      N active (M need attention)
Last CI Commit:   N min ago             ✅ OK
```

Status indicators:
- ✅ **OK** — normal operation
- ⚠️ **WARN** — stale data (>10 min), approaching limits (P&L < -$200), or pending orders stuck
- 🔴 **DOWN** — no predictions in expected window, kill switch active, or circuit breaker tripped
- 🧪 **ATTENTION** — experiment needs validation decision

### 9. Route to other skills if needed

If the health check finds issues, suggest the appropriate next step:
- Edge problems → "Run `/critique-performance` for a deep dive"
- Decision thresholds → "Run `/review-decisions` to check triggers"
- Experiment alerts → "Run `/validate-optimization` to check status"
- Pipeline down → Check GitHub Actions for errors, check `docs/ops/BREAK_FIX_LOG.md`

## Key Rules

- **Speed over depth.** This should take < 60 seconds. If something needs investigation, flag it and suggest the deeper skill.
- **Always show all 4 pipelines.** Even if the user only cares about BTC 5m, show the full picture.
- **UTC and CST.** Show prediction timestamps in UTC (what the DB stores) and the report header in CST (user's timezone, GMT-6).
- **Don't fix things.** This skill diagnoses. It does not make changes, commit code, or modify databases.
