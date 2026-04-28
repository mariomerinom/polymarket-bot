#!/bin/bash
# check_engine_health.sh — runs every 15 min via systemd timer.
#
# 2026-04-24 incident: engine crashlooped 5 days from disk-full and no
# alarm fired. This script is the alarm. Three checks, two outputs.
#
# Checks:
#   1. Disk usage on / — WARN >85%, CRIT >95%
#   2. systemctl is-active botsy — CRIT if not active
#   3. Predictions DB freshness — WARN >15min, CRIT >60min stale
#
# Outputs:
#   - logs/engine_health.log   — full local log (rotated by log_rotator)
#   - data/engine_health.txt   — single-line summary, auto-committed to
#                                GitHub by git_commit_loop. If GitHub
#                                stops getting fresh lines, the engine
#                                itself is dead — visible from outside.
#
# Exit codes: 0=OK, 1=WARN, 2=CRIT (so a future push-notification layer
# can react without re-parsing).
#
# Non-destructive: read-only checks + append-only writes. Never restarts,
# never modifies engine state.

set -u

ROOT="/home/botuser/polymarket-bot"
LOG_FILE="$ROOT/logs/engine_health.log"
SUMMARY_FILE="$ROOT/data/engine_health.txt"
DB_PATH="$ROOT/data/predictions.db"

now_utc() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "[$(now_utc)] $*" | tee -a "$LOG_FILE" >&2; }

worst=0   # 0=OK, 1=WARN, 2=CRIT
notes=()

# 1. Disk usage on /
disk_pct=$(df / | awk 'NR==2 {gsub("%",""); print $5+0}')
if [ "$disk_pct" -ge 95 ]; then
    log "CRIT: disk ${disk_pct}% used"
    notes+=("disk=${disk_pct}%-CRIT")
    worst=2
elif [ "$disk_pct" -ge 85 ]; then
    log "WARN: disk ${disk_pct}% used"
    notes+=("disk=${disk_pct}%-WARN")
    [ $worst -lt 1 ] && worst=1
else
    notes+=("disk=${disk_pct}%")
fi

# 2. systemd unit state
if systemctl is-active --quiet botsy; then
    notes+=("botsy=active")
else
    state=$(systemctl is-active botsy 2>&1 || true)
    log "CRIT: botsy not active (state=$state)"
    notes+=("botsy=$state-CRIT")
    worst=2
fi

# 3. Predictions DB freshness
if [ -r "$DB_PATH" ]; then
    age_s=$(sqlite3 "$DB_PATH" "SELECT CAST((julianday('now') - julianday(MAX(predicted_at))) * 86400 AS INTEGER) FROM predictions" 2>/dev/null)
    if [ -z "$age_s" ] || [ "$age_s" = "" ]; then
        log "WARN: predictions table empty or unreadable"
        notes+=("preds=unknown-WARN")
        [ $worst -lt 1 ] && worst=1
    elif [ "$age_s" -ge 3600 ]; then
        mins=$((age_s / 60))
        log "CRIT: most recent prediction ${mins} minutes old"
        notes+=("preds=${mins}m-CRIT")
        worst=2
    elif [ "$age_s" -ge 900 ]; then
        mins=$((age_s / 60))
        log "WARN: most recent prediction ${mins} minutes old"
        notes+=("preds=${mins}m-WARN")
        [ $worst -lt 1 ] && worst=1
    else
        notes+=("preds=$((age_s / 60))m")
    fi
else
    log "WARN: $DB_PATH not readable"
    notes+=("preds=db-unreadable-WARN")
    [ $worst -lt 1 ] && worst=1
fi

# Single-line summary that the git_commit_loop will sync to GitHub.
# Pattern: timestamp + worst-status + space-joined notes.
case $worst in
    0) status="OK" ;;
    1) status="WARN" ;;
    2) status="CRIT" ;;
esac
mkdir -p "$(dirname "$SUMMARY_FILE")"
echo "$(now_utc) $status ${notes[*]}" >> "$SUMMARY_FILE"

# Keep only last 500 lines in the summary file (~5 days at 15-min cadence)
if [ -f "$SUMMARY_FILE" ]; then
    tail -n 500 "$SUMMARY_FILE" > "$SUMMARY_FILE.tmp" && mv "$SUMMARY_FILE.tmp" "$SUMMARY_FILE"
fi

exit $worst
