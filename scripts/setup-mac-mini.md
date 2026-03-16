# Mac Mini Setup — Polymarket Bot Daemon

Run the polymarket-bot as an always-on daemon on a Mac Mini, replacing the GitHub Actions cron.

## Prerequisites

- macOS with Homebrew
- Python 3.12+
- Git configured with push access to the repo (SSH key or credential helper)
- An Anthropic API key

## 1. Clone and install

```bash
cd ~
git clone git@github.com:<your-user>/polymarket-bot.git
cd polymarket-bot

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Set your API key in the plist

Edit the launchd plist and replace `REPLACE_WITH_YOUR_API_KEY` with your actual key:

```bash
nano scripts/com.polymarket.bot.plist
```

Find this line and paste your key:
```xml
<string>REPLACE_WITH_YOUR_API_KEY</string>
```

## 3. Create the log directory

```bash
mkdir -p ~/Library/Logs/polymarket-bot
```

## 4. Make the loop script executable

```bash
chmod +x scripts/mac-mini-loop.sh
```

## 5. Install the launchd plist

```bash
cp scripts/com.polymarket.bot.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.polymarket.bot.plist
```

The bot will start immediately and auto-start on every login.

## 6. Disable the GitHub Actions cron

Since the Mac Mini is now running cycles, disable the Actions workflow to avoid conflicts:

1. Go to the repo on GitHub > Actions > "Predict and Score"
2. Click the `...` menu > "Disable workflow"

Or comment out the cron trigger in `.github/workflows/predict-and-score.yml`:
```yaml
on:
  # schedule:
  #   - cron: '*/5 * * * *'
  workflow_dispatch: {}
```

## Managing the daemon

**Check if running:**
```bash
launchctl list | grep polymarket
```

**Stop:**
```bash
launchctl unload ~/Library/LaunchAgents/com.polymarket.bot.plist
```

**Start:**
```bash
launchctl load ~/Library/LaunchAgents/com.polymarket.bot.plist
```

**Restart:**
```bash
launchctl unload ~/Library/LaunchAgents/com.polymarket.bot.plist
launchctl load ~/Library/LaunchAgents/com.polymarket.bot.plist
```

## Checking logs

**Main loop log (timestamped cycle output):**
```bash
tail -f ~/Library/Logs/polymarket-bot/loop.log
```

**Raw stdout/stderr (launchd captures):**
```bash
tail -f ~/Library/Logs/polymarket-bot/stdout.log
tail -f ~/Library/Logs/polymarket-bot/stderr.log
```

**Last 50 lines:**
```bash
tail -50 ~/Library/Logs/polymarket-bot/loop.log
```

## How it works

1. `mac-mini-loop.sh` runs `ci_run.py` (fetch markets, auto-resolve, predict, score, generate dashboard)
2. After each cycle, it commits changes to `data/`, `docs/`, and `prompts/` and pushes to GitHub
3. GitHub Pages picks up the updated `docs/index.html` and the dashboard goes live
4. Sleeps 5 minutes, then repeats
5. If a cycle fails, the error is logged and the loop continues with the next cycle
6. If the script crashes, launchd restarts it automatically

## Troubleshooting

**Bot not running after reboot:**
- launchd agents only run after login. If the Mac Mini restarts without auto-login, the agent won't start.
- Enable auto-login: System Settings > Users & Groups > Login Options > Automatic login.

**Push failures:**
- Make sure SSH keys are loaded: `ssh-add -l`
- Or use HTTPS with a credential helper: `git config credential.helper osxkeychain`

**Python not found:**
- The plist sets PATH to include `/opt/homebrew/bin` and `/usr/local/bin`. If your Python is elsewhere, update the PATH in the plist.
- If using a venv, the loop script auto-activates `.venv/` if it exists.
