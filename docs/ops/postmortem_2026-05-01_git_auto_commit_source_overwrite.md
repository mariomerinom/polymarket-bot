# Postmortem - VPS Auto-Commit Source Overwrite (2026-05-01)

**Severity:** Sev-1 correctness / deployment integrity. No live capital loss observed, but pushed source and documentation commits were silently removed by later VPS auto-commits.
**Incident window:** 2026-05-01 16:42 UTC to 2026-05-01 18:33 UTC
**Detected by:** Local pull after pushed work disappeared from `origin/main`
**Resolved by:** `f9cdc7c1f` plus manual VPS hard reset/restart

## What Happened

Several tested commits were pushed to `main`:

- `c8619e6fd` - Kalshi strike-aware parser rebuild
- `a6a0dbf51` / `4e5b3870e` - Lab and Polymarket microstructure roadmap implementation
- `982ef8234` - 2026-05-01 session log

Within the next VPS auto-commit cycle, the engine pushed new `Auto: cycle update ...` commits that deleted those files and restored older versions of touched source files. The visible symptom was that local `git pull --rebase` after a successful push showed source/docs being deleted by a bot-authored auto-commit.

The same pattern repeated after the first attempted fix because the running VPS process still had the old Python code cached in memory.

## Impact

- Kalshi strike-aware parser work was temporarily removed from `main`.
- Lab/Microstructure roadmap work was temporarily removed from `main`.
- The daily session log was temporarily removed from `main`.
- GitHub could not be trusted as a stable source of truth during the window because the production writer was committing from a stale checkout.
- Development time was lost re-applying and validating the same work multiple times.

## Root Cause

The engine's `_git_commit_push()` recovery path handled push rejection by doing:

```bash
git reset --soft HEAD~1
git reset --soft origin/main
git add data/ docs/daily/
git commit
git push
```

That looked safe because only runtime paths were explicitly staged after the reset. It was not safe.

`git reset --soft origin/main` moves `HEAD` but intentionally preserves the old index and working tree. If the VPS checkout was stale and `origin/main` had added or changed source/docs, the old worktree still lacked those new files or still had old file contents. The next commit could therefore record deletions or reversions from the stale VPS worktree.

In plain English: the VPS was saying "I am at the new commit" while its files still looked like the old commit. The next auto-commit then made that lie permanent.

## Contributing Factors

- The running engine did not restart before its next auto-commit, so even after `109044a89` was pushed, the process kept executing the old cached `_git_commit_push()` function.
- The deploy hook did restart once, but the VPS repo was still tangled (`ahead 1, behind 2`) from the stale auto-commit path, and the source file on disk still contained the old soft-reset logic.
- Auto-commit was allowed to touch tracked source/docs indirectly via git index state, despite the intent to commit only runtime data.
- There was no regression test that specifically asserted "when behind origin, hard-reset before staging data."

## Detection

Detection was manual:

1. Pushed work disappeared on the next `git pull`.
2. A later check showed `origin/main` had advanced with bot commits that deleted source/docs.
3. Inspecting `src/botsy_engine.py` identified the `git reset --soft origin/main` recovery path as the mechanism.
4. After the first fix, watching one full auto-commit cycle showed the old running process could still revert the fix.

## Resolution

Shipped `f9cdc7c1f`:

- `_git_commit_push()` now fetches first.
- If local `HEAD` is safely behind `origin/main`, it performs `git reset --hard origin/main` before staging runtime files.
- If local and remote diverge, it writes `data/GIT_COMMIT_BAIL` and stops auto-committing until a human inspects.
- If push fails after commit, it writes `data/GIT_COMMIT_BAIL` instead of trying soft-reset recovery.
- Regression tests now assert:
  - fetch preflight occurs,
  - behind-origin recovery uses hard reset,
  - runtime paths are staged only after the hard reset,
  - no `git reset --soft` recovery is used,
  - divergence bails before staging/commit/push.

Operational repair:

1. Stopped `botsy` on the VPS.
2. Re-applied the engine fix locally and pushed it.
3. Hard-reset the VPS checkout to `origin/main`.
4. Restarted `botsy`.
5. Verified the VPS file contained the hard-reset preflight path.
6. Waited through a full auto-commit cycle.
7. Confirmed new auto-commit `f5411769b` preserved both the engine fix and session log.

## Verification

- `pytest tests/test_engine_resilience.py -q` -> 11 passed
- `pytest tests/ -v` -> 863 passed, 4 skipped
- First protected auto-commit after repair: `f5411769b Auto: cycle update 2026-05-01T18:33:05Z`
- Current VPS `src/botsy_engine.py` contains:
  - `git fetch origin`
  - `git reset --hard origin/main`
  - `_git_rev_parse()`
- Current VPS `src/botsy_engine.py` no longer contains the old `git reset --soft origin/main` recovery path.

## Prevention

1. **Never use `git reset --soft origin/main` in automation that commits from a persistent worktree.** Soft reset is for human-managed index surgery, not production sync.
2. **Automation must hard-sync code before staging generated data.** If the goal is "runtime data only," first make the worktree match `origin/main`, then stage the explicit runtime paths.
3. **On divergence, bail instead of merging.** A production bot should not invent conflict policy.
4. **Source deploys need runtime verification, not just push success.** After changing `src/`, verify the VPS process restarted and the on-disk file contains the new logic.
5. **Watch one auto-commit cycle after git-loop changes.** A git-loop fix is not done until the next bot-authored commit preserves it.
6. **Keep regression tests around git behavior concrete.** The tests must assert command ordering and forbidden commands, especially `reset --soft`.

## Follow-Ups

- Add an integrity check that alerts if an `Auto:` commit touches `src/`, `tests/`, `config/`, or `docs/plans/`.
- Consider restricting the engine auto-commit path with `git diff --cached --name-only` allowlist enforcement before commit.
- Document this incident in `docs/ops/ENGINEERING_LESSONS.md`.
- Re-apply lost feature work only after the git loop has survived a full auto-commit cycle.
