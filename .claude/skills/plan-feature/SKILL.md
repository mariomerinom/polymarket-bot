---
name: plan-feature
description: >
  Design detailed implementation plans for features, specs, or code changes.
  Use when: user says "plan this", "design implementation", "how would we build",
  "plan feature", "implementation plan", "plan spec", or "/plan-feature".
  Follows the backward-present-future documentation paradigm from CLAUDE.md.
  Produces a plan file at docs/plans/<feature-name>-plan.md.
---

# Plan Feature

Design a step-by-step implementation plan for a specific feature, spec, or code change. Every plan follows the project's backward→present→future framework and enforces frozen file rules.

## Prerequisites

- **Always `git pull` first.**
- The user must specify a target: a spec name (from `docs/specs/`), a feature description, or a decision number (from `docs/core/decisions.md`).

## Process

### 1. Pull latest and identify target

```bash
cd /Users/mrmrnm-max/polymarket-bot
git pull --rebase || git pull
```

Identify what the user wants to plan:
- If a spec name → read from `docs/specs/<spec_name>.md`
- If a decision number → read from `docs/core/decisions.md`, find the decision
- If a feature description → no existing doc, plan from scratch

### 2. Read context files

Always read:
- `CLAUDE.md` — frozen files list, validation principles, development process
- `docs/core/strategy.md` — current signal logic
- `docs/core/ROADMAP.md` — current phase and gates
- `docs/ops/ENGINEERING_LESSONS.md` — past mistakes to avoid

Read the source files that the feature would modify:
- `src/predict.py` / `src/predict_eth.py` — prediction logic
- `src/trade.py` — trade execution
- `src/conviction.py` — conviction scoring (if it exists)
- `src/shadow_indicators.py` — shadow mode indicators
- `src/shadow_conviction_scorer.py` — shadow conviction scoring
- Relevant test files in `tests/`
- Relevant CI workflow in `.github/workflows/`

### 3. Frozen file check

Check if the plan requires changes to ANY frozen file:

| Frozen File | Can't Touch Unless Explicitly Approved |
|-------------|---------------------------------------|
| `src/ci_run.py` | BTC 5m pipeline entry point |
| `src/btc_data.py` | BTC candle data fetcher |
| `src/predict.py` | BTC 5m prediction logic |
| `src/score.py` | Scoring module |
| `src/clob_depth.py` | CLOB depth analysis |
| `.github/workflows/predict-and-score.yml` | BTC 5m CI workflow |
| `data/predictions.db` | BTC 5m production database |

If the plan touches any frozen file, flag it as **FROZEN FILE VIOLATION** at the top of the plan. The user must explicitly approve before proceeding.

### 4. Apply backward-present-future framework

#### Backward — Does anything break?
- What existing behavior depends on the files being changed?
- Which pipelines are affected? (BTC 5m, BTC 15m, ETH 5m, Kalshi)
- What tests currently pass that might break?
- Rollback plan: how do we undo this if it fails?

#### Present — What is the plan?
- Step-by-step implementation sequence
- Each step = one atomic commit (testable independently)
- For each step: file paths, code approach (pseudocode or key logic), commit message
- Shadow mode first? Or direct implementation?
- Tests to add for each step

#### Future — Where does this surface?
- What does success look like? (specific WR target, P&L improvement, etc.)
- Validation criteria for `validate-optimization` registration:
  - `--name`: snake_case name
  - `--revert-if`: Python expression (e.g., `"post_wr < baseline_wr - 2"`)
  - `--min-sample`: number of bets (default 50)
- How long until 50 bets? (based on current bet frequency per pipeline)
- What dashboard/report changes are needed to surface the results?
- What downstream work does this enable or block?

### 5. Write the plan file

Write to `docs/plans/<feature-name>-plan.md`:

```markdown
# Plan: <Feature Name>

## Context
Why this change? What problem does it solve? What prompted it?

## Frozen File Check
✅ PASS — No frozen files affected
OR
🚫 FAIL — Requires changes to: `src/predict.py` (explicit approval needed)

## Prerequisites
- [ ] Shadow data collecting (N samples available)
- [ ] Current phase allows this change (ROADMAP check)
- [ ] No conflicting optimizations active

## Backward — What Breaks?
- Affected pipelines: ...
- Affected tests: ...
- Rollback plan: ...

## Implementation Steps

### Step 1: <description>
**Files**: `src/foo.py`, `tests/test_foo.py`
**Change**: <what to do>
**Commit**: `<commit message>`
**Tests**: <what tests to add/modify>

### Step 2: ...

## Test Plan
- [ ] New unit tests for ...
- [ ] Existing tests still pass (`pytest tests/ -v`)
- [ ] CI pipeline runs green after push

## Validation Plan
- Register with: `python3 src/optimization_tracker.py register --name <name> --description "<desc>" --revert-if "<expr>" --min-sample 50`
- Baseline snapshot: <current WR, P&L, bet count>
- Expected validation timeline: ~N days at current bet frequency

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ... | Low/Med/High | Low/Med/High | ... |

## Estimated Timeline
- Implementation: ~N hours
- Data collection: ~N days to 50 bets
- Validation gate: ~N days after 50 bets
```

### 6. Commit the plan

```bash
git add docs/plans/<feature-name>-plan.md
git commit -m "Add implementation plan: <feature-name>"
git pull --rebase || git pull
git push
```

## Key Rules

- **One plan per feature.** Don't combine multiple specs into one plan.
- **Shadow mode is the default.** Unless the feature is purely mechanical (e.g., dashboard change), plan for shadow tracking first, live activation second.
- **Include the optimization registration command.** The plan should specify the exact CLI command to register the optimization, including the revert condition. This forces the user to commit to failure criteria before building.
- **Reference existing code.** Don't propose new utilities when existing functions in the codebase already do the job. Cite file paths and function names.
- **Engineering lessons apply.** Read `docs/ops/ENGINEERING_LESSONS.md` and check if any past mistake is relevant to this plan.
