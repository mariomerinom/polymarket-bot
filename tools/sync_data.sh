#!/bin/bash
# sync_data.sh — pull fresh SQLite DBs from the VPS to the local Mac.
#
# After 2026-04-28: data/*.db files are no longer tracked in git
# (history rewrite reclaimed ~14 GB of binary bloat). The engine on
# the VPS keeps writing them locally; this script syncs them down
# when a local analysis session needs current state.
#
# Usage:
#   tools/sync_data.sh                  # all DBs
#   tools/sync_data.sh predictions.db   # one DB only
#
# Idempotent — rsync only transfers changed bytes.

set -euo pipefail

VPS="${BOTSY_VPS:-root@134.209.196.239}"
REMOTE_DIR="/home/botuser/polymarket-bot/data"
LOCAL_DIR="$(cd "$(dirname "$0")"/../data && pwd)"

if [ "$#" -gt 0 ]; then
    # One specific file
    target="$1"
    echo "Syncing $target from $VPS..."
    rsync -avz --progress \
        "$VPS:$REMOTE_DIR/$target" \
        "$LOCAL_DIR/$target"
else
    # All .db files
    echo "Syncing all *.db from $VPS..."
    rsync -avz --progress \
        --include='*.db' \
        --exclude='*.db-wal' \
        --exclude='*.db-shm' \
        --exclude='*.db-journal' \
        --exclude='*.db.corrupt-*' \
        --exclude='bybit_capture/' \
        --exclude='bybit_capture/**' \
        --exclude='*' \
        "$VPS:$REMOTE_DIR/" \
        "$LOCAL_DIR/"
fi

echo "Done."
echo "Local DBs:"
ls -lah "$LOCAL_DIR"/*.db 2>/dev/null | awk '{print "  " $9, $5}' | head -10
