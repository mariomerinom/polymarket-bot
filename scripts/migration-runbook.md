# Migration Runbook: GitHub Actions → DigitalOcean VPS

## Risk Summary

| Risk | Impact | Mitigation |
|------|--------|------------|
| Both executors write to DB simultaneously | Binary merge conflict corrupts SQLite | Disable Actions *before* starting VPS. Zero overlap. |
| Cycle number reuse | Duplicate predictions, broken scoring | VPS pulls latest DB before first cycle (loop does this automatically) |
| Dashboard goes stale | Public page shows old data | Verify git push after first cycle, check GitHub Pages |
| Wrong trading env vars | Silent paper mode or wrong sizing | Verify `.env` matches GitHub Secrets, check first order |
| Python version mismatch | Subtle runtime bugs | Must be 3.12.x. Startup tests catch most issues. |
| VPS timezone wrong | Daily report fires at wrong time | Must be UTC (Ubuntu default). Don't change it. |

---

## Step 1: Pre-Migration (on your laptop)

```bash
# 1a. Confirm no GitHub Actions runs are in progress
gh run list --limit 5

# 1b. Disable all 4 workflows
gh workflow disable "Predict and Score"
gh workflow disable "Predict 15m"
gh workflow disable "ETH Predict and Score"
gh workflow disable "Daily Report"

# 1c. Verify they're disabled
gh workflow list
# All should show "disabled_manually"

# 1d. Wait 5 min for any in-flight cycle to finish
# Check: gh run list --limit 3 (all should be "completed")
```

---

## Step 2: VPS Setup

Follow `scripts/setup-digitalocean.md` steps 1–6.

Before starting the service, run these checks:

```bash
# 2a. Python version
python3 --version
# Must be 3.12.x

# 2b. Timezone is UTC
timedatectl | grep "Time zone"
# Should show: Time zone: Etc/UTC (UTC, +0000)

# 2c. Tests pass
source ~/polymarket-bot/venv/bin/activate
cd ~/polymarket-bot
python3 -m pytest tests/ -v

# 2d. Latest DB pulled
git pull
sqlite3 data/predictions.db "SELECT MAX(cycle) FROM predictions;"
# Note this number — next cycle should be +1

# 2e. .env is correct
cat .env
# TRADING_ENABLED=true
# POLYMARKET_PRIVATE_KEY=<not empty>
# BET_SIZE=25
# DAILY_LOSS_LIMIT=300
# KILL_SWITCH=false

# 2f. CLOB not geoblocked
curl -s ifconfig.me
# Must be a non-US IP

python3 -c "
from py_clob_client.client import ClobClient
client = ClobClient('https://clob.polymarket.com')
print('CLOB OK:', client.get_tick_size('21742633143463906290569050155826241533067272736897614950488156847949938836455'))
"
# Should print a tick size, NOT a 403 error
```

---

## Step 3: Start the Service

```bash
sudo systemctl start polymarket-bot
```

---

## Step 4: Post-First-Cycle Checks (within 5 min)

```bash
# 4a. Loop is running
tail -30 ~/polymarket-bot/logs/loop.log
# Should show "[BTC 5m] OK" and "[ETH 5m] OK"

# 4b. BTC 5m prediction stored
sqlite3 data/predictions.db \
  "SELECT cycle, agent, conviction_score FROM predictions ORDER BY id DESC LIMIT 3;"
# Cycle should be previous MAX + 1

# 4c. ETH 5m prediction stored
sqlite3 data/predictions_eth.db \
  "SELECT cycle, agent FROM predictions ORDER BY id DESC LIMIT 3;"

# 4d. Order placed (the critical test — was it 403 or success?)
sqlite3 data/predictions.db \
  "SELECT cycle, direction, size, status, reason FROM orders ORDER BY id DESC LIMIT 3;"
# status should be "placed" or "filled", NOT "failed"
# reason should NOT contain "403" or "geoblock"

# 4e. Git push succeeded
git log --oneline -3
# Should show "Auto: cycle update <timestamp>" from the VPS

# 4f. Dashboard updated (check in browser)
# https://mariomerinom.github.io/polymarket-bot/
# Timestamp should be within last 5 min
```

---

## Step 5: Post-Third-Cycle Checks (~15 min)

```bash
# 5a. BTC 15m ran
sqlite3 data/predictions_15m.db \
  "SELECT cycle FROM predictions ORDER BY id DESC LIMIT 1;"

# 5b. No push failures
grep -c "Push failed\|Push still failed" logs/loop.log
# Should be 0

# 5c. No pipeline crashes
grep -c "FAILED" logs/loop.log
# Should be 0 (or only from expected skips like "no signal")
```

---

## Step 6: Daily Report Check (after 12:00 UTC)

```bash
# 6a. Report file exists
ls -la docs/daily/$(date -u +%Y-%m-%d).md

# 6b. Report was pushed
git log --oneline -5 | grep -i "daily\|report"
```

---

## Step 7: Trading Verification (after first qualifying signal)

```bash
# 7a. First successful live order
sqlite3 data/predictions.db \
  "SELECT cycle, direction, size, price_limit, status, reason
   FROM orders WHERE mode='live' AND status != 'failed'
   ORDER BY id DESC LIMIT 1;"

# 7b. If no non-failed orders yet, check why recent ones failed
sqlite3 data/predictions.db \
  "SELECT cycle, status, reason FROM orders WHERE mode='live' ORDER BY id DESC LIMIT 5;"

# 7c. Check wallet balance moved (replace with your wallet address)
# https://polygonscan.com/address/<YOUR_WALLET>
```

---

## Rollback Procedure

If the VPS is broken and you need to go back to GitHub Actions:

```bash
# On the VPS
sudo systemctl stop polymarket-bot

# On your laptop
gh workflow enable "Predict and Score"
gh workflow enable "Predict 15m"
gh workflow enable "ETH Predict and Score"
gh workflow enable "Daily Report"

# Set TRADING_ENABLED=false in GitHub repo vars (US IP can't trade)
# Trigger first cycle manually
gh workflow run "Predict and Score"
```

Predictions and scoring resume on GitHub Actions. Trading remains broken until a non-US executor is restored.

---

## Steady-State Monitoring

Daily sanity check (run from your laptop):

```bash
ssh botuser@<DROPLET_IP> "tail -5 ~/polymarket-bot/logs/loop.log && echo '---' && sqlite3 ~/polymarket-bot/data/predictions.db \"SELECT COUNT(*) as orders_today, SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed FROM orders WHERE placed_at > datetime('now', '-24 hours');\""
```

What to watch for:
- `[BTC 5m] FAILED` appearing repeatedly → pipeline crash, check logs
- Orders all `status=failed` → CLOB issue, check reason column
- No git pushes in 30+ min → loop died, check `systemctl status`
- Dashboard stale → push failing, check `grep "Push" logs/loop.log`
