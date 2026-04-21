#!/bin/bash
# install_deploy_hook.sh — install the post-merge auto-restart hook on VPS.
#
# Idempotent: safe to run multiple times. Always replaces the symlink to
# point at the latest tools/git-hooks/post-merge in the repo.
#
# Usage (run from repo root on the VPS, as botuser):
#   bash tools/install_deploy_hook.sh
#
# To remove: `rm .git/hooks/post-merge`

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_SRC="$REPO_ROOT/tools/git-hooks/post-merge"
HOOK_DEST="$REPO_ROOT/.git/hooks/post-merge"

if [ ! -f "$HOOK_SRC" ]; then
    echo "ERROR: hook source not found at $HOOK_SRC"
    exit 1
fi

if [ ! -x "$HOOK_SRC" ]; then
    echo "Making hook source executable..."
    chmod +x "$HOOK_SRC"
fi

# Backup existing hook if it's a real file (not a symlink)
if [ -f "$HOOK_DEST" ] && [ ! -L "$HOOK_DEST" ]; then
    backup="${HOOK_DEST}.bak.$(date -u +%Y%m%dT%H%M%SZ)"
    echo "Backing up existing non-symlink hook to $backup"
    mv "$HOOK_DEST" "$backup"
fi

# Create / replace symlink
ln -sf "$HOOK_SRC" "$HOOK_DEST"

# Ensure logs/ exists and is writable
mkdir -p "$REPO_ROOT/logs"
touch "$REPO_ROOT/logs/deploy_hook.log"

# Verify sudoers allows restart without password
if ! sudo -n /bin/systemctl is-active botsy >/dev/null 2>&1; then
    echo "WARNING: 'sudo -n systemctl is-active botsy' failed."
    echo "Passwordless sudo for systemctl is required. Check /etc/sudoers.d/"
else
    echo "OK: passwordless sudo verified for systemctl"
fi

echo ""
echo "post-merge hook installed:"
ls -la "$HOOK_DEST"
echo ""
echo "Next merge that touches src/ or config/ will auto-restart botsy."
echo "Hook activity is logged to: $REPO_ROOT/logs/deploy_hook.log"
