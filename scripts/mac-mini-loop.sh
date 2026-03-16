#!/usr/bin/env bash
#
# mac-mini-loop.sh — Runs ci_run.py in a loop, commits & pushes after each cycle.
# Designed to be invoked by launchd (see com.polymarket.bot.plist).
#
set -euo pipefail

REPO_DIR="/Users/mrmrnm-max/polymarket-bot"
LOG_DIR="$HOME/Library/Logs/polymarket-bot"
LOG_FILE="$LOG_DIR/loop.log"
SLEEP_SECONDS=300  # 5 minutes between cycles

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" | tee -a "$LOG_FILE"
}

cd "$REPO_DIR"

# Activate venv if it exists
if [ -f "$REPO_DIR/venv/bin/activate" ]; then
    source "$REPO_DIR/venv/bin/activate"
elif [ -f "$REPO_DIR/.venv/bin/activate" ]; then
    source "$REPO_DIR/.venv/bin/activate"
fi

log "=== Polymarket bot loop starting ==="
log "Repo: $REPO_DIR"
log "Python: $(which python3)"
log "Sleep between cycles: ${SLEEP_SECONDS}s"

cycle=0
while true; do
    cycle=$((cycle + 1))
    log "--- Cycle $cycle ---"

    # Pull latest to avoid conflicts (rebase to keep history clean)
    log "Pulling latest..."
    if ! git pull --rebase 2>&1 | tee -a "$LOG_FILE"; then
        log "WARNING: git pull failed, attempting to continue anyway"
    fi

    # Run the prediction cycle
    log "Running ci_run.py..."
    if (cd src && python3 ci_run.py) 2>&1 | tee -a "$LOG_FILE"; then
        log "Cycle $cycle completed successfully"
    else
        log "ERROR: Cycle $cycle failed (exit code $?). Will retry next cycle."
        sleep "$SLEEP_SECONDS"
        continue
    fi

    # Commit and push changes (same as GitHub Actions workflow)
    log "Committing changes..."
    git add data/ docs/ prompts/ 2>&1 | tee -a "$LOG_FILE"

    if git diff --cached --quiet; then
        log "No changes to commit"
    else
        COMMIT_MSG="Auto: cycle update $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        if git commit -m "$COMMIT_MSG" 2>&1 | tee -a "$LOG_FILE"; then
            log "Pushing to remote..."
            if git push 2>&1 | tee -a "$LOG_FILE"; then
                log "Push successful"
            else
                log "WARNING: Push failed. Will retry next cycle."
                # Don't reset — the commit is still local and will be pushed next time
            fi
        else
            log "WARNING: Commit failed"
        fi
    fi

    log "Sleeping ${SLEEP_SECONDS}s until next cycle..."
    sleep "$SLEEP_SECONDS"
done
