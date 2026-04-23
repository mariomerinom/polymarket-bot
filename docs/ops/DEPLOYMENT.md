# Deployment

How code gets from a commit to production.

## The problem this solves

**Python caches imports at process start.** When a commit changes `src/*.py`, pushing the commit to GitHub is not enough — the running engine on the VPS still holds the OLD modules in memory until the process restarts. We learned this on **2026-04-21** when a protective signal-EHR gate and shadow regime logging shipped but silently no-op'd for ~4 hours because the engine was started before the deploy.

The fix is automatic restart on source changes via a VPS-side `post-merge` git hook.

---

## How it works

```
┌──────────────┐     git push          ┌────────────────┐
│  local dev   │ ────────────────────► │   origin/main  │
└──────────────┘                       └────────┬───────┘
                                                │
                   engine's git_commit_loop     │ pulls every few minutes
                   or manual git pull           ▼
                                        ┌────────────────┐
                                        │   VPS repo     │
                                        └────────┬───────┘
                                                 │ merge lands
                                                 ▼
                                        ┌──────────────────────┐
                                        │ post-merge hook fires│
                                        │  (see below)         │
                                        └────────┬─────────────┘
                                                 │ changed files touch src/ or config/?
                                          ┌──────┴──────┐
                                         yes            no
                                          │             │
                                          ▼             ▼
                                ┌─────────────────┐  continue normally
                                │ systemctl       │  (data-only / doc merges)
                                │ restart botsy   │
                                └─────────────────┘
```

### The hook script

Source-of-truth: `tools/git-hooks/post-merge` (tracked in repo). Symlinked into `.git/hooks/post-merge` on the VPS by the installer.

Decision logic:

| Files changed touch | Restart? |
|---|---|
| `src/` | yes — Python imports cached |
| `config/` | yes — pipeline modes, bet sizes |
| `requirements*` | yes — dependency changes |
| `data/` | no — engine writes these every cycle |
| `docs/` | no — pure documentation |
| `tests/` | no — not imported by engine |
| `.github/` | no — CI only |
| `CLAUDE.md`, `README*` | no — documentation |

### What triggers the hook

The `post-merge` hook fires when `git merge` (or `git pull`, which does a merge) completes. It runs in two real scenarios on the VPS:

1. **Engine auto-pull** — the engine's `git_commit_loop` runs `git pull --rebase` after every cycle. When upstream has new commits, this triggers the hook.
2. **Manual pull** — `ssh root@... "su - botuser -c 'cd /home/botuser/polymarket-bot && git pull'"` during an explicit deploy.

Does NOT fire on:
- The engine's own auto-commits (those are local; pull is a no-op)
- `git fetch` without merge
- Rebases that don't complete with a merge (post-rewrite hook handles those — not currently wired)

### What gets logged

Every hook invocation writes to `logs/deploy_hook.log` with a UTC timestamp:

```
[deploy-hook 2026-04-21T23:55:12Z] source changes detected (a895de8d6..488145b71):
  src/system_state.py
  src/predict.py
  src/predict_eth.py
  tests/test_system_state.py
[deploy-hook 2026-04-21T23:55:12Z] restarting botsy...
[deploy-hook 2026-04-21T23:55:12Z] botsy restart issued
```

Tail the log to verify deploys: `ssh root@VPS "tail /home/botuser/polymarket-bot/logs/deploy_hook.log"`

---

## Installation

One-time setup per VPS clone. The hook itself is tracked in the repo; installation means symlinking it into `.git/hooks/` (which is not tracked).

```bash
# On the VPS, as botuser:
cd /home/botuser/polymarket-bot
bash tools/install_deploy_hook.sh
```

The installer:
1. Symlinks `.git/hooks/post-merge` → `tools/git-hooks/post-merge`
2. Makes the hook executable
3. Creates `logs/` if missing
4. Verifies passwordless sudo works for `systemctl restart botsy`
5. Prints verification output

If the installer reports "WARNING: passwordless sudo failed," add to `/etc/sudoers.d/botuser`:

```
botuser ALL=(ALL) NOPASSWD:/bin/systemctl restart botsy
```

Or grant full NOPASSWD (as this repo currently does):

```
botuser ALL=(ALL) NOPASSWD:ALL
```

---

## Uninstalling / bypassing

### Remove the hook

```bash
rm /home/botuser/polymarket-bot/.git/hooks/post-merge
```

Next merge will not auto-restart. Manual `systemctl restart botsy` is then required after every source change.

### Skip the hook for a single pull

`git -c core.hooksPath=/dev/null pull` — runs the pull without firing hooks.

### Skip the restart for a specific commit

If a commit touches `src/` but genuinely doesn't need a restart (rare — typo fix in a comment, for example), there's no in-band way to skip. Options:
- Split the change so the non-restart-triggering file lands in a separate commit in `docs/` etc.
- Manually edit the hook to ignore a specific file
- Accept the restart

Prefer the first option.

---

## Deployment workflow

### Standard change (source code, config)

```bash
# 1. Local: test + commit + push
pytest tests/ -v
git add ...
git commit -m "..."
git push

# 2. Wait. Within 5 min the engine pulls and the hook restarts botsy.
#    Verify via:
ssh root@134.209.196.239 "tail /home/botuser/polymarket-bot/logs/deploy_hook.log"
ssh root@134.209.196.239 "ps -o pid,etime -p \$(pgrep -f botsy_engine | head -1)"
```

### Urgent deploy (can't wait for auto-pull)

```bash
# After push, force the pull immediately:
ssh root@134.209.196.239 "su - botuser -c 'cd /home/botuser/polymarket-bot && git pull --rebase -X theirs'"
# The pull triggers the hook, which restarts botsy if source changed.
```

**⚠️ `git reset --hard` bypasses hooks.** If you've been using reset-to-origin
as a deploy step (e.g., after stashing local data-file changes), the hook
will NOT fire. Use `git pull --rebase -X theirs` OR trigger the hook
explicitly after the reset:

```bash
ssh root@VPS "su - botuser -c 'cd /home/botuser/polymarket-bot && bash tools/git-hooks/post-merge <old-sha>'"
```

where `<old-sha>` is the commit HEAD was at before the reset. The hook's
stdout shows what it decided and whether it triggered a restart.

### Data/docs-only change

No action needed. Commit, push. Engine pulls on its own cycle. No restart, no hook noise.

### Revert a bad deploy

```bash
git revert <bad-sha>
git push
# Hook auto-restarts with the reverted code. Typical end-to-end: ~5 min.
```

---

## Monitoring

### Is the engine running stale code?

The engine's process start time should be newer than the last source-changing commit. Quick check:

```bash
ssh root@134.209.196.239 'echo "engine started: $(ps -o lstart= -p $(pgrep -f botsy_engine | head -1))"; echo "last src commit: $(cd /home/botuser/polymarket-bot && git log -1 --format="%ci %h %s" -- src/ config/ | head -1)"'
```

If the last source commit is newer than the engine start, the hook didn't fire (or failed) — manual restart needed.

### Hook health checks

- `logs/deploy_hook.log` — every hook invocation (or lack thereof on a merge)
- `systemctl status botsy` — is the service running at all?
- `journalctl -u botsy -n 50` — recent systemd events including restarts

### What if the hook fails?

The hook exits 0 even on sudo failure (to avoid aborting the merge). The error gets logged:

```
[deploy-hook ...] ERROR: sudo systemctl restart botsy failed — manual restart needed
```

So check `logs/deploy_hook.log` after any source deploy. If the error line appears, run `sudo systemctl restart botsy` manually and then diagnose why sudo failed (expired credential? sudoers changed?).

---

## Design notes

### Why a hook and not a deploy script?

Both have merit. A deploy script is explicit and easy to reason about but requires discipline — you can forget to run it. A hook is automatic but can surprise you (engine restarts that you didn't ask for).

We picked the hook because:
- The VPS is the authoritative production — automation belongs there
- The engine already pulls regularly for its own auto-commits — piggybacking on that is natural
- The failure mode (silent no-op after deploy) is what actually bit us on 2026-04-21 — invisible-by-default is exactly what we wanted to fix

A deploy script at `tools/deploy.sh` could be added as a belt-and-suspenders layer if the hook proves insufficient. Not needed today.

### Why restart instead of SIGHUP / hot reload?

Python doesn't have a clean built-in hot-reload for multi-module changes. Third-party options (`importlib.reload`, `Watchdog`-based reloaders) are fragile when state (WS connections, async tasks, in-memory caches like orderbook snapshot) lives across the reload boundary.

A full `systemctl restart`:
- Takes ~30 seconds end-to-end (shutdown, WS reconnect, candle buffer reseed)
- Predictable state — fresh Python process every time
- Uses existing supervision (systemd restarts on crash anyway)
- Minor cost: one missed 5m cycle if restart lands mid-cycle

### Why ignore data/ and tests/?

- `data/` — the engine writes these every cycle (auto-commits). Every pull includes data file updates. Restarting on those would cause restart-thrashing every few minutes.
- `tests/` — not imported by the engine. Test changes don't affect runtime.
- `docs/` — obviously no runtime impact.

### Why not use pre-push?

Pre-push fires on the local machine before pushing. Can warn but can't actually restart the remote engine. The authoritative place for deployment is where the code runs — the VPS.

---

## Historical context

- **2026-04-21**: Silent no-op deploy caught. Signal-EHR gate + shadow regime shipped at 19:30 UTC; engine had cached the pre-deploy code since 19:04 UTC. Restart issued manually at 23:48 UTC. ~4-hour window where the protections were inactive. No actual harm because the market stayed in HIGH_VOL and no conv≥3 signals triggered, but the principle was clear: **runtime behavior changes require restart, always.**
- **2026-04-21 (later)**: This hook built in response. Installed on VPS. No more silent-no-op deploys.
- **Daily restart cron (04:00 UTC)**: Still in place as a belt-and-suspenders for memory hygiene. Works alongside the hook — they don't conflict.

## Related

- `tools/git-hooks/post-merge` — the hook itself
- `tools/install_deploy_hook.sh` — one-time installer
- `logs/deploy_hook.log` — activity log (VPS only)
- `docs/ops/ENGINEERING_LESSONS.md` — broader production lessons
- `CLAUDE.md` — project rules that reference this doc
