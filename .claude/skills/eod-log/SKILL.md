---
name: eod-log
description: >
  End-of-day session log generator. Use when: user says "end of day", "eod",
  "wrap up", "close the day", "session summary", "what did we do today",
  "daily log", "/eod-log", or at the end of a long working session.
  Produces a structured markdown file capturing what was built, shipped,
  kicked forward, learned, and links to all relevant project docs.
---

# End-of-Day Session Log

Generate a structured end-of-day session log at `docs/sessions/YYYY-MM-DD.md`.

## Process

### 1. Pull latest and gather context

```bash
cd /Users/mrmrnm-max/polymarket-bot
git pull --rebase || true
```

Read these files for current state:
- `docs/ROADMAP.md` — current phase, what's active/next
- `docs/decisions.md` — any decisions that moved status today
- `docs/BREAK_FIX_LOG.md` — any new incidents
- Latest file in `docs/daily/` — today's pipeline performance
- `docs/optimizations.json` — any active optimizations registered/closed today

### 2. Review git history for today's work

```bash
git log --since="midnight" --oneline --all
git log --since="midnight" --stat --all
```

This shows every commit made today — code changes, CI auto-commits, etc. Filter out the CI `Auto:` commits to find human/Claude work.

### 3. Generate the session log

Write to `docs/sessions/YYYY-MM-DD.md` using this template:

```markdown
# Session Log — YYYY-MM-DD

## What We Built
<!-- New code, features, modules shipped today. Each item = file path + 1-line description -->

- `src/foo.py` — Description of what was added/changed
- `tests/test_foo.py` — Tests added

## What We Shipped
<!-- Commits pushed to main. Include commit hash + message -->

- `abc1234` — Commit message here
- `def5678` — Another commit

## What We Learned
<!-- Insights, findings, data points discovered during the session -->

- Finding 1
- Finding 2

## What Got Kicked Forward
<!-- Decisions deferred, tasks not started, things to pick up next session -->

- Task 1 — why it was deferred
- Task 2 — blocked on X

## Pipeline Health Today
<!-- From the daily report — quick snapshot -->

| Pipeline | Predictions | Bets | WR | P&L |
|----------|-------------|------|----|-----|
| 5m       | X           | Y    | Z% | $+N |
| 15m      | X           | Y    | Z% | $+N |

## Decision Tracker Movement
<!-- Any decisions.md changes today -->

| # | Decision | Old Status | New Status |
|---|----------|-----------|------------|

## Active Optimizations
<!-- From optimizations.json — anything registered, monitoring, or closed today -->

## References
<!-- Links to all relevant docs touched or referenced today -->

- [Daily Report](../daily/YYYY-MM-DD.md)
- [Roadmap](../ROADMAP.md) — Current phase: Part X
- [Decisions](../decisions.md) — N active monitors
- [Break-Fix Log](../BREAK_FIX_LOG.md)
- [Plan file](link-if-applicable)
```

### 4. Update the sessions index

Create or update `docs/sessions/index.md`:

```markdown
# Session Logs

Working session summaries — what was built, shipped, learned, and kicked forward.

- [YYYY-MM-DD](YYYY-MM-DD.md) — 1-line summary of the day
```

Most recent sessions first.

### 5. Commit and push

```bash
git add docs/sessions/
git commit -m "Add session log for YYYY-MM-DD"
git stash --include-untracked || true
git pull --rebase
git stash pop || true
git push
```

## Key Rules

- **Be honest about what got kicked forward.** The whole point is to track momentum AND drag.
- **Link everything.** Every claim should have a file path, commit hash, or doc reference.
- **Don't pad it.** If the session was short, the log should be short.
- **Include the pipeline health snapshot** even if the session wasn't about trading — it's the heartbeat.
- **Git commits are the source of truth** for "what was shipped." Parse `git log`, don't rely on memory.
