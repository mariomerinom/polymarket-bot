#!/bin/bash
# check_engine_health.sh — runs every 15 min via systemd timer.
#
# 2026-04-24 incident: engine crashlooped 5 days from disk-full and no
# alarm fired. This script is the alarm. Three checks, two outputs.
#
# Checks:
#   1. Disk usage on / — WARN >85%, CRIT >95%
#   2. systemctl is-active botsy — CRIT if not active
#   3. Predictions DB freshness for every unpaused configured pipeline —
#      WARN >15min, CRIT >60min stale
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

ROOT="${BOTSY_ROOT:-/home/botuser/polymarket-bot}"
LOG_FILE="$ROOT/logs/engine_health.log"
SUMMARY_FILE="$ROOT/data/engine_health.txt"
CONFIG_PATH="$ROOT/config/pipelines.json"

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
pipeline_paths=$(
    ROOT="$ROOT" CONFIG_PATH="$CONFIG_PATH" python3 - <<'PY' 2>/dev/null
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT"])
config_path = Path(os.environ["CONFIG_PATH"])
legacy = {
    "btc_5m": "predictions.db",
    "btc_15m": "predictions_15m.db",
    "eth_5m": "predictions_eth.db",
    "kalshi": "predictions_kalshi.db",
    "bybit": "predictions_bybit.db",
}

def db_name(pipeline):
    if pipeline in legacy:
        return legacy[pipeline]
    parts = pipeline.split("_", 1)
    if len(parts) == 2:
        asset, exchange = parts
        return f"predictions_{exchange}_{asset}.db"
    return f"predictions_{pipeline}.db"

config = json.loads(config_path.read_text())
for name, cfg in sorted(config.get("pipelines", {}).items()):
    if cfg.get("mode") == "paused":
        continue
    print(f"{name}|{root / 'data' / db_name(name)}")
PY
)

if [ -z "$pipeline_paths" ]; then
    pipeline_paths="btc_5m|$ROOT/data/predictions.db"
fi

max_age_s=-1
max_age_pipeline=""
stale=()
missing=()
unknown=()
now_sql="${BOTSY_HEALTH_NOW:-$(now_utc)}"

while IFS='|' read -r pipeline db_path; do
    [ -z "$pipeline" ] && continue
    if [ ! -r "$db_path" ]; then
        missing+=("$pipeline")
        continue
    fi
    age_s=$(sqlite3 "$db_path" "SELECT CAST((julianday('$now_sql') - julianday(MAX(predicted_at))) * 86400 AS INTEGER) FROM predictions" 2>/dev/null)
    if [ -z "$age_s" ]; then
        unknown+=("$pipeline")
        continue
    fi
    if [ "$age_s" -gt "$max_age_s" ]; then
        max_age_s=$age_s
        max_age_pipeline=$pipeline
    fi
    if [ "$age_s" -ge 900 ]; then
        stale+=("$pipeline:$(((age_s + 30) / 60))m")
    fi
done <<< "$pipeline_paths"

if [ "$max_age_s" -lt 0 ]; then
    log "WARN: no readable prediction DBs"
    notes+=("preds=unknown-WARN")
    [ $worst -lt 1 ] && worst=1
elif [ "$max_age_s" -ge 3600 ]; then
    mins=$(((max_age_s + 30) / 60))
    log "CRIT: stalest unpaused pipeline ${max_age_pipeline} prediction ${mins} minutes old"
    notes+=("preds=max=${mins}m-CRIT")
    worst=2
elif [ "$max_age_s" -ge 900 ]; then
    mins=$(((max_age_s + 30) / 60))
    log "WARN: stalest unpaused pipeline ${max_age_pipeline} prediction ${mins} minutes old"
    notes+=("preds=max=${mins}m-WARN")
    [ $worst -lt 1 ] && worst=1
else
    notes+=("preds=max=$(((max_age_s + 30) / 60))m")
fi

if [ "${#stale[@]}" -gt 0 ]; then
    notes+=("stale=$(IFS=,; echo "${stale[*]}")")
fi
if [ "${#missing[@]}" -gt 0 ]; then
    log "WARN: missing prediction DBs for: $(IFS=,; echo "${missing[*]}")"
    notes+=("missing=$(IFS=,; echo "${missing[*]}")")
    [ $worst -lt 1 ] && worst=1
fi
if [ "${#unknown[@]}" -gt 0 ]; then
    log "WARN: unreadable prediction DBs for: $(IFS=,; echo "${unknown[*]}")"
    notes+=("unknown=$(IFS=,; echo "${unknown[*]}")")
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

# Out-of-band notification via healthchecks.io dead-man's-switch.
# The URL is injected via the HEALTHCHECKS_URL env var (set in the
# systemd unit override at /etc/systemd/system/botsy-health-check.
# service.d/override.conf — NOT in git). If the URL is unset, this
# whole block is a no-op so local development is unaffected.
#
# Pattern:
#   OK/WARN → ping the base URL (success). healthchecks.io marks the
#             check "up" and resets its grace timer.
#   CRIT    → ping <URL>/fail. healthchecks.io triggers immediate
#             notification (configured at the account level).
#   silence → if 20+ min pass with no ping at all (engine dead, host
#             dead, network dead), healthchecks.io alerts.
#
# curl is fire-and-forget — failures here MUST NOT change exit status
# of the health check itself. Network blips shouldn't cause spurious
# CRIT pings.
if [ -n "${HEALTHCHECKS_URL:-}" ]; then
    if [ "$worst" -eq 2 ]; then
        ping_url="${HEALTHCHECKS_URL%/}/fail"
    else
        ping_url="${HEALTHCHECKS_URL%/}"
    fi
    # -fsS: silent except errors (visible in journal); -m 10: bound runtime.
    # Append the summary as a tiny payload so the dashboard shows context.
    curl -fsS -m 10 --retry 2 --retry-delay 1 \
        --data-binary "$status ${notes[*]}" \
        -H 'Content-Type: text/plain' \
        "$ping_url" >/dev/null 2>&1 || true
fi

exit $worst
