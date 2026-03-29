---
name: validate-optimization
description: >
  Register, monitor, and close optimization experiments for the polymarket-bot prediction pipeline.
  Use this skill whenever: a commit touches src/predict.py (proactively suggest registration),
  the user says "register this optimization", "track this change", "validate optimization",
  "how are optimizations doing", "check optimizations", "revert optimization", or
  asks about any active experiment's performance. Also trigger on "/validate-optimization".
  This skill enforces the validation principles in CLAUDE.md — every optimization gets a
  baseline, pre-set revert criteria, and a 50-bet minimum before declaring victory.
---

# Validate Optimization

This skill manages the lifecycle of prediction pipeline optimizations: **register → monitor → close**.

The goal is to ensure every code change to the prediction logic is tracked with a baseline, monitored automatically, and either validated or reverted based on data — not feelings.

## Prerequisites

- **Always `git pull` first.** The CI pipeline auto-commits every ~5 minutes. Stale data breaks everything.
- **Always `git push` after changes.** A change that isn't on GitHub doesn't exist.
- The tracker lives at `src/optimization_tracker.py`. The data lives at `docs/optimizations.json`. Do not modify these files by hand — use the CLI or Python API.

## Commands

### 1. Register (after shipping a code change)

When a commit touches `src/predict.py`, proactively ask the user if they want to register it as an optimization. If they say yes:

```bash
git pull

python3 src/optimization_tracker.py register \
  --name "<short_snake_case_name>" \
  --description "<what changed and why>" \
  --revert-if "<python expression>" \
  --min-sample 50 \
  --pipeline 5m   # or 15m
```

**Choosing a revert condition:**
- Default: `"post_wr < baseline_wr - 2"` (WR drops more than 2 percentage points)
- For aggressive filters: `"post_wr < baseline_wr - 5"` (more tolerance)
- For critical changes: `"post_wr < 60"` (absolute floor)
- The expression has access to: `post_wr`, `baseline_wr`, `post_bets`, `post_pnl`, `baseline_pnl`

After registration, **add an entry to `docs/decisions.md`** action log with the date, decision number, action taken, and expected result. Then commit and push:

```bash
git add docs/optimizations.json docs/decisions.md
git commit -m "Register optimization: <name>"
git push
```

### 2. Status (check progress)

```bash
git pull
python3 src/optimization_tracker.py summary
```

For detailed per-optimization stats:

```bash
python3 src/optimization_tracker.py check
```

This shows:
- **Progress alerts** if under min_sample: "10/50 bets collected (90.0% WR vs 66.3% baseline)"
- **Validation alerts** if sample met and WR improved: "VALIDATED — 70% WR vs 66% baseline"
- **Revert alerts** if sample met and revert condition triggered: "REVERT CANDIDATE — 58% WR vs 66% baseline"

The daily report (06:00 CST) runs this automatically and includes alerts in the GitHub notification.

### 3. Close (validate, revert, or defer)

When an optimization has enough data:

```bash
git pull

# If validated (WR improved or held)
python3 src/optimization_tracker.py close --name "<name>" --status validated --reason "WR improved X% → Y% on Z bets"

# If reverting (WR dropped)
python3 src/optimization_tracker.py close --name "<name>" --status reverted --reason "WR dropped to X%, reverting code change"

# If deferring (inconclusive)
python3 src/optimization_tracker.py close --name "<name>" --status deferred --reason "WR flat, need more data or different approach"
```

**If reverting**, also:
1. Identify the commit that introduced the optimization (`git log --oneline src/predict.py`)
2. Revert the code change
3. Run tests: `python3 -m pytest tests/ -v`
4. Update `docs/decisions.md` — change status from ACTIONED to REVERTED with the date and reason
5. Commit and push

## Validation Principles (from CLAUDE.md)

These are non-negotiable:

1. **Every optimization gets a baseline.** The tracker snapshots WR, P&L, and bet count at registration time.
2. **Set revert criteria before shipping, not after.** The `--revert-if` flag forces this.
3. **Minimum sample size is 50 bets.** The tracker won't declare validation until this threshold is met.
4. **Derived from ≠ validated by.** The baseline is computed from historical data. Post-change stats are computed only from predictions made after registration.
5. **Track the counterfactual.** Filtered predictions are stored at conviction 2 (no bet) so we can compare.
6. **One change at a time.** If two changes ship in the same commit, register them as one optimization — you can't separate the signal.

## Proactive Behavior

If you see a commit that modified `src/predict.py` and no optimization was registered for it:

> "I see you changed the prediction logic. Want me to register this as an optimization so we can track whether it helps? I'll snapshot the current baseline (X bets, Y% WR, $Z P&L) and set up automatic monitoring."

This is the most important behavior of the skill — catching unregistered changes before they go dark.

## API Reference

For deeper integration, see `references/tracker-api.md` which documents the Python functions in `src/optimization_tracker.py`.
