#!/usr/bin/env bash
#
# vps-loop.sh — Runs all pipelines on a VPS. Sole executor — no GitHub Actions.
#
# Pipelines:
#   BTC 5m  — every cycle (predict + trade + score + dashboard)
#   BTC 15m — every 3rd cycle (predict + score + dashboard)
#   ETH 5m  — every cycle (predict + score + dashboard)
#   Bybit BTC Perps — every cycle (predict + trade + score + dashboard)
#   Kalshi BTC — every cycle (predict + score + dashboard)
#   Daily report — once per day at ~12:00 UTC
#
# GitHub is code hosting + Pages only. This script handles everything.
#
# Usage:
#   ./scripts/vps-loop.sh
#
set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/loop.log"
CYCLE_INTERVAL=300   # 5 minutes
FIFTEEN_MIN_MOD=3    # Run 15m every 3rd cycle (= 15 min)

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" | tee -a "$LOG_FILE"
}

cd "$REPO_DIR"

# Activate venv
if [ -f "$REPO_DIR/venv/bin/activate" ]; then
    source "$REPO_DIR/venv/bin/activate"
elif [ -f "$REPO_DIR/.venv/bin/activate" ]; then
    source "$REPO_DIR/.venv/bin/activate"
fi

# Load environment variables (.env file)
if [ -f "$REPO_DIR/.env" ]; then
    set -a
    source "$REPO_DIR/.env"
    set +a
fi

log "=== Polymarket bot loop starting ==="
log "Repo: $REPO_DIR"
log "Python: $(which python3)"
log "TRADING_ENABLED: ${TRADING_ENABLED:-false}"
log "Cycle interval: ${CYCLE_INTERVAL}s"

# Tests run locally before every commit (CLAUDE.md policy).
# Removed startup test gate — was blocking pipeline 28+ min on 1GB VPS.
log "Skipping startup tests (run locally before push). Starting main loop."

cycle=0
last_report_date=""

while true; do
    cycle=$((cycle + 1))
    log "--- Cycle $cycle ---"

    # Pull latest (manual pushes, code changes)
    if ! git pull --rebase 2>&1 | tee -a "$LOG_FILE"; then
        log "WARNING: git pull failed, attempting reset and retry"
        git stash 2>/dev/null || true
        git pull --rebase 2>&1 | tee -a "$LOG_FILE" || true
        git stash pop 2>/dev/null || true
    fi

    # ── Cycle timing (Phase 2 diagnostic) ──
    CYCLE_START=$(date +%s)

    # ── BTC 5m Pipeline ──
    log "[BTC 5m] Running ci_run.py..."
    if (cd src && python3 ci_run.py) 2>&1 | tee -a "$LOG_FILE"; then
        log "[BTC 5m] OK"
    else
        log "[BTC 5m] FAILED (exit $?)"
    fi

    # ── BTC 15m Pipeline (every 3rd cycle = 15 min) ──
    if [ $((cycle % FIFTEEN_MIN_MOD)) -eq 0 ]; then
        log "[BTC 15m] Running ci_run_15m.py..."
        if (cd src && python3 ci_run_15m.py) 2>&1 | tee -a "$LOG_FILE"; then
            log "[BTC 15m] OK"
        else
            log "[BTC 15m] FAILED (exit $?)"
        fi
    fi

    # ── ETH 5m Pipeline ──
    log "[ETH 5m] Running ci_run_eth.py..."
    if (cd src && python3 ci_run_eth.py) 2>&1 | tee -a "$LOG_FILE"; then
        log "[ETH 5m] OK"
    else
        log "[ETH 5m] FAILED (exit $?)"
    fi

    # ── Bybit BTC Perps Pipeline ──
    log "[Bybit] Running ci_run_bybit.py..."
    if (cd src && python3 ci_run_bybit.py) 2>&1 | tee -a "$LOG_FILE"; then
        log "[Bybit] OK"
    else
        log "[Bybit] FAILED (exit $?)"
    fi

    # ── Kalshi BTC Pipeline ──
    log "[Kalshi] Running ci_run_kalshi.py..."
    if (cd src && python3 ci_run_kalshi.py) 2>&1 | tee -a "$LOG_FILE"; then
        log "[Kalshi] OK"
    else
        log "[Kalshi] FAILED (exit $?)"
    fi

    # ── Cycle timing diagnostic ──
    CYCLE_END=$(date +%s)
    ELAPSED=$((CYCLE_END - CYCLE_START))
    log "DIAG|cycle_seconds=$ELAPSED"
    if [ $ELAPSED -gt 240 ]; then
        log "WARN: cycle exceeded 4 min (${ELAPSED}s) — consider parallelizing"
    fi

    # ── Daily Report (once per day, around 12:00 UTC) ──
    current_hour=$(date -u +%H)
    current_date=$(date -u +%Y-%m-%d)
    if [ "$current_hour" = "12" ] && [ "$current_date" != "$last_report_date" ]; then
        log "[Daily Report] Generating..."
        if (cd src && python3 daily_report.py) 2>&1 | tee -a "$LOG_FILE"; then
            last_report_date="$current_date"
            log "[Daily Report] OK"
        else
            log "[Daily Report] FAILED (exit $?)"
        fi
    fi

    # ── Commit and push ──
    log "Committing changes..."
    git add data/ 2>&1 | tee -a "$LOG_FILE"

    if git diff --cached --quiet; then
        log "No changes to commit"
    else
        COMMIT_MSG="Auto: cycle update $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        if git commit -m "$COMMIT_MSG" 2>&1 | tee -a "$LOG_FILE"; then
            log "Pushing..."
            if ! git push 2>&1 | tee -a "$LOG_FILE"; then
                log "WARNING: Push failed — retrying with pull --rebase"
                git pull --rebase 2>&1 | tee -a "$LOG_FILE" || true
                git push 2>&1 | tee -a "$LOG_FILE" || log "WARNING: Push still failed. Will retry next cycle."
            fi
        else
            log "WARNING: Commit failed"
        fi
    fi

    # ── Log rotation (keep last 10k lines) ──
    if [ -f "$LOG_FILE" ] && [ "$(wc -l < "$LOG_FILE")" -gt 50000 ]; then
        tail -10000 "$LOG_FILE" > "$LOG_FILE.tmp"
        mv "$LOG_FILE.tmp" "$LOG_FILE"
        log "Log rotated (kept last 10k lines)"
    fi

    log "Sleeping ${CYCLE_INTERVAL}s..."
    sleep "$CYCLE_INTERVAL"
done
