# Postmortem — Data Loss During History Rewrite (2026-04-28)

**Severity:** Sev-3. ~6 hours of paper observation data lost; no live capital affected.
**Window:** 2026-04-28 22:30 UTC (engine stopped for maintenance) → 2026-04-28 23:30 UTC (engine running on recovered DB state from 16:14 UTC commit)
**Total data lost:** ~6h of multi_poll_predictions, arb_divergence rows, and resolved-market context across the BTC+ETH pipelines

## What happened

Disk-full incident from 2026-04-24/28 resolved by mid-day 2026-04-28. As part of the cleanup, pivoted to fixing the underlying cause of the disk pressure: the engine had been auto-committing binary `data/*.db` files every 5 minutes since launch, accumulating ~17 GB of `.git/` history on the VPS.

User and operator agreed to a `git filter-repo` history rewrite to strip `data/*.db` blobs from history (Step B), preceded by gitignoring + untracking the live DB files (Step A). The plan worked as designed for the rewrite itself — `.git/` dropped from 17 GB to 166 MB on the VPS, freeing 16.8 GB.

Where it went wrong: the deployment of the rewritten history. Sequence:

1. Local force-push of rewritten history to origin
2. VPS engine stopped for maintenance
3. VPS `git fetch origin` + `git reset --hard origin/main`

The reset deleted the formerly-tracked-now-untracked `data/*.db` files from the working tree. **`git reset --hard` removes files that are tracked in current HEAD but absent from target HEAD, regardless of `.gitignore` status.** The new origin/main HEAD didn't track the DBs (Step A), so reset deleted them.

Engine restarted with empty schemas, began writing fresh predictions and multi-poll rows from a clean slate.

## Recovery

Recovered from a safety clone (`/Users/mrmrnm-max/polymarket-bot-rewrite/`) created before the rewrite. The clone retained full pre-rewrite pack history.

- Checked out `5b3b0285d:data/` (the most recent pre-rewrite auto-commit, 16:14 UTC) into the clone's working tree
- Verified DB integrity: `predictions_eth.db`, `predictions_hl.db`, `predictions_kalshi.db`, `strategy_lab.db` all clean
- `predictions.db` from that exact commit was **malformed** — caught mid-write by the auto-commit. `sqlite3 .recover` extracted only 172 bytes (no usable schema)
- Tried earlier commit `5b3b0285d~1` (~5 min older). Clean. 6,384 predictions + 2,129 multi_poll + 1,937 arb_divergence rows
- scp'd recovered DBs to VPS `/tmp/`, replaced empty post-restart DBs, restarted engine

Net loss: ~6 hours of multi_poll/arb_divergence/predictions data between 16:14 UTC (recovered commit) and 22:30 UTC (engine stop for maintenance). Plus ~30 minutes of post-restart fresh data overwritten by the recovery.

## Why this happened

Three failure modes stacked:

1. **`git reset --hard` semantics on tracking flips.** Files removed from index in a target commit but still present in working tree get DELETED from the working tree on `reset --hard`. This is correct git behavior; we relied on a wrong mental model where "gitignored = safe."
2. **Auto-committed binary SQLite is non-atomically captured.** SQLite writes pages incrementally. If `git add data/predictions.db` runs while a write is mid-flight, the captured blob is corrupt at the schema level (looks like SQLite, doesn't parse). Even with `_checkpoint_all_dbs()` flushing WALs before commit, single-page writes can still tear if they coincide with the add.
3. **No pre-rewrite data backup.** We had a safety clone of the repo (which preserved the pack history), but no separate backup of the live DB working-tree files at maintenance start. The clone's most-recent commit was several hours stale by the time we needed it.

## What we kept that helped

- The polymarket-bot-rewrite/ safety clone preserved enough history to recover ~94% of what was at risk.
- The recovery DBs didn't need to be byte-identical to the live state — paper observation tolerates a 6-hour gap as long as the schema and prior data are intact.
- The engine's `init_table` calls are idempotent, so post-recovery the engine resumed writing on top of the recovered state cleanly without manual schema migration.

## What we should change

1. **Always backup `data/*` to `/tmp/data_backup_<timestamp>/` before any destructive git op.** A `cp -a data /tmp/data_backup_pre_rewrite` immediately before `git reset --hard` would have preserved everything. This is a one-liner addition to the maintenance checklist; it just wasn't documented.
2. **Stop the engine ≥30s before the snapshot.** Gives in-flight WAL checkpoints time to settle. Then snapshot the DB files atomically via `cp` before any git operation touches them. Prevents the mid-write corruption pattern at root.
3. **Document the maintenance flow.** A short `docs/ops/MAINTENANCE_PROCEDURES.md` covering destructive git ops + DB backups would have caught both failure modes pre-incident.

## Action items

| # | Action | Status |
|---|---|---|
| 1 | `tools/sync_data.sh` exists | shipped same day (general-purpose VPS→local sync, doubles as pre-maintenance backup) |
| 2 | Document destructive-op checklist | in this postmortem |
| 3 | (optional) `tools/backup_data.sh` for one-shot timestamped DB snapshots | not done; one-liner via `tar czf /tmp/data_backup_$(date +%s).tgz data/*.db` is sufficient if remembered |

## Lessons (for the maintenance procedures doc)

When doing destructive git ops on a live repo with co-located data:

1. **`git reset --hard` deletes formerly-tracked-now-untracked files.** The target HEAD's index is what determines what stays in the working tree. `.gitignore` only protects files that were never tracked; it does NOT protect files being untracked-by-this-commit.
2. **Backup `data/` to `/tmp/` before any of: `reset --hard`, `clean -fdx`, `checkout` of a destructive ref, `filter-repo`.** Always. The VPS's 24G disk has enough headroom; the cost of the backup is seconds, the cost of recovery is hours.
3. **Stop the engine first.** Live writers + git operations on the same files = race risk for mid-write corruption.
4. **Verify recovery assumptions before destructive ops.** Specifically: does our safety clone actually have the data we'd need? When was it taken? `git log <safety-clone>/refs/origin/main -- data/predictions.db` shows the commits that touched the file.

## Related

- Disk-full root cause: `docs/ops/postmortem_2026-04-28_disk_full.md`
- The git_commit_push fetch+ancestor-check fix shipped same day (commit `875dbea3e`) addresses a different failure mode (rebase-abort silently clobbering local commits) discovered alongside this one.
