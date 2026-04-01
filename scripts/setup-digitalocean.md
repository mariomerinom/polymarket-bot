# DigitalOcean VPS Setup — Polymarket Bot

Run everything on a single DigitalOcean droplet. No GitHub Actions. GitHub is code hosting + Pages only.

The VPS handles: predictions, trading, scoring, dashboards, daily reports, git push.

## Why

- Polymarket CLOB API returns 403 for US-based IPs (GitHub Actions runners)
- Tighter cycle timing (exact 5-min intervals vs GitHub's 1-30 min cron drift)
- Single executor — no split-brain between CI and local
- $6/mo

---

## 1. Create Droplet

**Region:** Amsterdam (AMS3), Frankfurt (FRA1), or Singapore (SGP1) — any non-US
**Image:** Ubuntu 24.04 LTS
**Size:** Basic, $6/mo (1 vCPU, 1GB RAM, 25GB SSD)
**Auth:** SSH key

```bash
doctl compute droplet create polymarket-bot \
  --region ams3 \
  --size s-1vcpu-1gb \
  --image ubuntu-24-04-x64 \
  --ssh-keys $(doctl compute ssh-key list --format ID --no-header | head -1)
```

---

## 2. Server Setup

```bash
ssh root@<DROPLET_IP>

# Create non-root user
adduser botuser
usermod -aG sudo botuser
su - botuser

# Install deps
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
```

---

## 3. Clone and Install

```bash
cd ~
git clone https://github.com/mariomerinom/polymarket-bot.git
cd polymarket-bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt pytest

# Verify
python3 -m pytest tests/ -v
```

---

## 4. Git Push Access

The bot pushes after every cycle. Set up a deploy key:

```bash
ssh-keygen -t ed25519 -C "polymarket-bot-vps" -f ~/.ssh/polymarket_deploy
cat ~/.ssh/polymarket_deploy.pub
```

Add the public key as a **Deploy Key** in GitHub repo Settings (enable write access).

```bash
cat >> ~/.ssh/config << 'EOF'
Host github.com
  IdentityFile ~/.ssh/polymarket_deploy
  IdentitiesOnly yes
EOF

cd ~/polymarket-bot
git remote set-url origin git@github.com:mariomerinom/polymarket-bot.git
git config user.name "polymarket-bot[vps]"
git config user.email "bot@polymarket-vps"

# Test
git push --dry-run
```

---

## 5. Environment Variables

```bash
cat > ~/polymarket-bot/.env << 'EOF'
TRADING_ENABLED=true
POLYMARKET_PRIVATE_KEY=<your-polygon-wallet-private-key>
BET_SIZE=25
DAILY_LOSS_LIMIT=300
KILL_SWITCH=false
EOF

chmod 600 ~/polymarket-bot/.env
```

---

## 6. Test CLOB Connectivity

Before going live, verify the API doesn't geoblock this IP:

```bash
source ~/polymarket-bot/venv/bin/activate
curl -s ifconfig.me    # Should show a non-US IP

python3 -c "
from py_clob_client.client import ClobClient
client = ClobClient('https://clob.polymarket.com')
print('CLOB OK:', client.get_tick_size('21742633143463906290569050155826241533067272736897614950488156847949938836455'))
"
```

If you see a tick size (e.g., `0.01`), you're good. If you see a 403, try a different region.

---

## 7. Install systemd Service

```bash
sudo tee /etc/systemd/system/polymarket-bot.service << 'EOF'
[Unit]
Description=Polymarket Bot — BTC/ETH prediction + trading pipeline
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/polymarket-bot
ExecStart=/home/botuser/polymarket-bot/scripts/vps-loop.sh
Restart=always
RestartSec=30

EnvironmentFile=/home/botuser/polymarket-bot/.env

StandardOutput=append:/home/botuser/polymarket-bot/logs/systemd.log
StandardError=append:/home/botuser/polymarket-bot/logs/systemd.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable polymarket-bot
sudo systemctl start polymarket-bot
```

---

## 8. Disable GitHub Actions

Once the VPS is running and you've confirmed cycles are working:

```bash
# From your local machine, disable all pipeline workflows:
gh workflow disable "Predict and Score"
gh workflow disable "Predict 15m"
gh workflow disable "ETH Predict and Score"
gh workflow disable "Daily Report"
```

Or via GitHub UI: Actions → each workflow → `...` → Disable workflow.

**Keep `workflow_dispatch` triggers** in the YAML files so you can manually re-enable if the VPS goes down.

GitHub Pages continues serving dashboards automatically — the VPS pushes updated HTML to `docs/`.

---

## 9. Verify Everything Works

```bash
# Watch the first few cycles
tail -f ~/polymarket-bot/logs/loop.log

# After 1-2 cycles, check:
# 1. Predictions appearing in DB
sqlite3 ~/polymarket-bot/data/predictions.db "SELECT cycle, agent, conviction_score FROM predictions ORDER BY id DESC LIMIT 5;"

# 2. Orders being placed (not 403)
sqlite3 ~/polymarket-bot/data/predictions.db "SELECT cycle, status, reason FROM orders ORDER BY id DESC LIMIT 5;"

# 3. Dashboard pushed to GitHub (check GitHub Pages)

# 4. ETH predictions in separate DB
sqlite3 ~/polymarket-bot/data/predictions_eth.db "SELECT cycle, agent FROM predictions ORDER BY id DESC LIMIT 5;"
```

---

## Managing the Service

```bash
sudo systemctl status polymarket-bot    # Status
sudo systemctl stop polymarket-bot      # Stop
sudo systemctl start polymarket-bot     # Start
sudo systemctl restart polymarket-bot   # Restart
journalctl -u polymarket-bot -f         # Live logs
tail -100 ~/polymarket-bot/logs/loop.log  # App logs
```

---

## Kill Switch

Emergency stop from anywhere:

```bash
# Option 1: Stop the service
ssh botuser@<DROPLET_IP> "sudo systemctl stop polymarket-bot"

# Option 2: Kill switch file (trading stops, predictions continue)
ssh botuser@<DROPLET_IP> "touch ~/polymarket-bot/data/KILL_SWITCH"

# Option 3: Kill switch via .env (requires restart)
ssh botuser@<DROPLET_IP> "sed -i 's/KILL_SWITCH=false/KILL_SWITCH=true/' ~/polymarket-bot/.env && sudo systemctl restart polymarket-bot"
```

---

## What Runs Where

| Component | Where | Why |
|-----------|-------|-----|
| BTC 5m predictions + trading | VPS | Non-US IP for CLOB, exact 5-min timing |
| BTC 15m predictions | VPS | Same loop, every 3rd cycle |
| ETH 5m predictions | VPS | Same loop |
| Scoring + dashboards | VPS | Runs after predictions, pushes HTML to GitHub |
| Daily report | VPS | Runs at 12:00 UTC (06:00 CST) |
| GitHub Pages | GitHub | Serves `docs/*.html` — auto-updates on push |
| Code hosting | GitHub | PRs, issues, history |
| GitHub Actions | **Disabled** | Re-enable via `workflow_dispatch` if VPS goes down |

---

## Cost

| Item | Cost |
|------|------|
| DigitalOcean Basic Droplet | $6/mo |
| Everything else | $0 |

---

## Monitoring

**DigitalOcean uptime alert (free):**
1. Console → Monitoring → Create Alert
2. Droplet unreachable > 5 min → email notification

**Process-level:**
- systemd `Restart=always` auto-restarts crashed loops
- Individual pipeline failures don't stop the loop (each is wrapped in if/else)
- Log rotation keeps disk usage bounded

**Manual check:**
```bash
# From your laptop
ssh botuser@<DROPLET_IP> "tail -20 ~/polymarket-bot/logs/loop.log"
```

---

## Rollback to GitHub Actions

If the VPS goes down and you need to revert:

```bash
# Re-enable workflows
gh workflow enable "Predict and Score"
gh workflow enable "Predict 15m"
gh workflow enable "ETH Predict and Score"
gh workflow enable "Daily Report"

# Set TRADING_ENABLED=false in GitHub vars (US IP can't trade)
# Manually trigger first cycle
gh workflow run "Predict and Score"
```

Predictions and scoring resume immediately. Trading requires a non-US IP.
