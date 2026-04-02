---
name: review-specs
description: >
  Systematic evaluation of unimplemented feature specs using an agent team.
  Spawns 4 specialized reviewers who critique specs from different angles and
  debate each other before the lead synthesizes a ranked priority matrix.
  Use when: user says "review specs", "spec critique", "which spec next",
  "prioritize specs", "evaluate specs", "spec triage", or "/review-specs".
---

# Review Specs — Agent Team

Evaluate all unimplemented feature specs in `docs/specs/` using a team of specialized reviewers. Each reviewer brings a different lens; they read the specs independently, then challenge each other's assessments before the lead synthesizes the final priority matrix.

This uses Claude Code's [agent teams](https://code.claude.com/docs/en/agent-teams) feature. Each reviewer is a full Claude Code session with its own context window.

## Prerequisites

- **Agent teams must be enabled.** The `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` env var must be set to `1` in settings or environment.
- **Always `git pull` first.**
- Specs live in `docs/specs/`. There are currently 10 unimplemented specs.

## Team Structure

Create an agent team with **4 teammates** plus the lead (you). Each teammate reviews ALL specs but through a specific lens:

```
Create an agent team to review all feature specs in docs/specs/.
Spawn 4 reviewer teammates. Require plan approval before they write any files.

Teammate 1 — "data-analyst": Your job is to evaluate each spec's DATA READINESS.
  Read docs/specs/*.md, then query the databases and daily reports to check
  whether shadow indicator data exists to validate each spec's hypothesis.
  Key questions: Is shadow data already collecting? How many samples? Does the
  data actually support the spec's premise, or is it pure theory?
  Read: docs/daily/ (latest 3 reports), data/predictions.db (shadow indicators
  in reasoning column), docs/optimizations.json.

Teammate 2 — "engineer": Your job is to evaluate each spec's IMPLEMENTATION
  COMPLEXITY and ISOLATION. Read docs/specs/*.md and the source code it would
  touch. Key questions: Which files need to change? Does it touch a frozen file
  (src/predict.py, src/ci_run.py, src/btc_data.py, src/score.py, src/clob_depth.py)?
  Can it be toggled independently? Does it conflict with any other spec?
  How many lines of code? Shadow mode first or direct?
  Read: src/predict.py, src/predict_eth.py, src/trade.py, src/conviction.py,
  src/shadow_indicators.py, CLAUDE.md (frozen files list).

Teammate 3 — "strategist": Your job is to evaluate each spec's EDGE HYPOTHESIS
  and strategic fit. Read docs/specs/*.md plus the current strategy and research.
  Key questions: Does this spec address a known weakness in our current strategy?
  Does it align with the current roadmap phase? Does it address a tracked decision?
  What's the expected WR improvement if the hypothesis holds? Is the hypothesis
  falsifiable within 50 bets?
  Read: docs/core/strategy.md, docs/core/ROADMAP.md, docs/core/decisions.md,
  docs/research/BACKTEST_FINDINGS.md, docs/research/pattern_mining_results.md.

Teammate 4 — "devil-advocate": Your job is to CHALLENGE the other reviewers'
  assessments and find reasons NOT to build each spec. Key questions: What could
  go wrong? Is this premature optimization? Does the sample size actually support
  the claim? Are we overfitting to recent data? Would the simplest version of
  this spec be good enough, or is the spec over-engineered?
  Read all specs, then wait for the other 3 reviewers to share findings.
  Actively challenge their highest-rated specs — your job is to prevent
  false positives.
```

## Process

### 1. Pull latest

```bash
cd /Users/mrmrnm-max/polymarket-bot
git pull --rebase || git pull
```

### 2. Spawn the agent team

Ask Claude to create the team with the structure above. The lead coordinates, assigns the initial task ("review all specs in docs/specs/"), and ensures each teammate has the right context.

Key coordination instructions for the lead:

```
After all 4 reviewers finish their independent analysis, have them share
findings with each other. Specifically:

1. data-analyst shares which specs have data and which don't
2. engineer shares which specs are easy/hard to build and frozen file conflicts
3. strategist shares which specs address real weaknesses
4. devil-advocate challenges the top 3 specs the others want to build

Then synthesize all 4 perspectives into a single priority matrix.
```

### 3. Scoring framework

Each spec is scored on 5 axes (1-5 each, 25 max):

| Axis | Owner | 1 (Bad) | 5 (Great) |
|------|-------|---------|-----------|
| **Data Readiness** | data-analyst | No data, need new API | Shadow data collecting, 100+ samples |
| **Implementation Complexity** | engineer | New deps, frozen files, multi-pipeline | Single file, conviction demotion |
| **Edge Hypothesis Strength** | strategist | No supporting data, pure theory | Shadow data shows clear signal |
| **Isolation** | engineer | Interacts with other filters | Fully independent, toggleable |
| **Reversibility** | engineer | Code surgery to undo | Flip a conviction number back |

The devil-advocate can propose **score adjustments** (±1) on any axis for any spec, with justification. The lead decides whether to accept.

### 4. Debate phase

After independent reviews, teammates debate via direct messaging:

- devil-advocate challenges the top 3 specs (highest combined scores)
- Other reviewers can defend or concede
- Lead mediates and captures the strongest arguments on each side

This is the key advantage of agent teams over a single-pass review: competing perspectives surface blind spots.

### 5. Lead synthesizes the final matrix

The lead produces the final output using findings from all 4 reviewers:

#### Tier 1 — Ready Now
Specs where: data-analyst confirms shadow data, engineer confirms low complexity and no frozen files, strategist confirms strategic fit, and devil-advocate couldn't find a fatal flaw.

#### Tier 2 — Needs More Data
Specs where: hypothesis is promising but data-analyst found insufficient shadow samples (< 100), or data collection hasn't started. Action: ensure shadow tracking is active.

#### Tier 3 — Needs Redesign
Specs where: engineer found frozen file violations without justification, devil-advocate found fatal flaws, or strategist says it doesn't fit the current roadmap phase.

#### Per-Spec Entry Format

```markdown
### spec_name (Tier X) — Total Score: NN/25

| Axis | Score | Reviewer | Notes |
|------|-------|----------|-------|
| Data Readiness | X/5 | data-analyst | ... |
| Complexity | X/5 | engineer | ... |
| Hypothesis | X/5 | strategist | ... |
| Isolation | X/5 | engineer | ... |
| Reversibility | X/5 | engineer | ... |

**Devil's advocate**: [Key challenge raised and whether it was addressed]
**Frozen files**: PASS / FAIL (list affected files)
**Related decisions**: #N, #M
**Shadow data**: Collecting (N samples) / Not collecting / N/A
**Consensus**: Build now / Wait for data / Redesign spec / Rejected
```

### 6. Clean up the team

After the matrix is synthesized:

```
Ask all teammates to shut down, then clean up the team.
```

## Specs to Review

All files in `docs/specs/`:

| Spec | Focus |
|------|-------|
| `spec_rsi_conviction_gate.md` | RSI as pre-bet filter to downgrade conflicting signals |
| `spec_obv_bucket_filter.md` | On-Balance Volume filter for 0.50-0.70 price bucket |
| `spec_vwap_mean_reversion.md` | VWAP deviation for mean-reverting regime bets |
| `spec_volatility_breakout.md` | Volatility compression→expansion breakout detection |
| `spec_stochastic_entry_timing.md` | Stochastic Oscillator for entry timing |
| `spec_order_flow_imbalance.md` | CLOB bid/ask imbalance as leading indicator |
| `spec_market_price_dislocation.md` | Polymarket price lag vs BTC spot arbitrage |
| `spec_cross_exchange_lead_lag.md` | Kraken/Coinbase lead-lag temporal arbitrage |
| `spec_dead_regime_harvesting.md` | Edge extraction from mean-reverting/dead-hour regimes |
| `spec_generic_conviction_engine.md` | Parameterized conviction scorer for all assets |

## Shadow Indicator Mapping

The daily report already tracks shadow indicators that map to specific specs:

| Shadow Indicator | Related Spec | DB Query |
|-----------------|--------------|----------|
| RSI(14) | `spec_rsi_conviction_gate` | `SELECT COUNT(*) FROM predictions WHERE reasoning LIKE '%RSI%'` |
| OBV slope | `spec_obv_bucket_filter` | `SELECT COUNT(*) FROM predictions WHERE reasoning LIKE '%OBV%'` |
| VWAP deviation | `spec_vwap_mean_reversion` | `SELECT COUNT(*) FROM predictions WHERE reasoning LIKE '%VWAP%'` |
| Spread % | `spec_order_flow_imbalance` | `SELECT AVG(slippage_pct) FROM orders WHERE mode='live'` |

## Key Rules

- **Score honestly.** A spec with a great idea but no data is Tier 2, not Tier 1. The devil-advocate exists to prevent hype.
- **Frozen files are a hard constraint.** The engineer must flag frozen file violations — these require explicit user approval.
- **One change at a time.** Even if 3 specs are Tier 1, they ship sequentially with separate optimization registrations.
- **Shadow mode first.** Any spec that can be shadow-tested before going live should be.
- **Connect to decisions.** If a spec addresses a tracked decision in `docs/core/decisions.md`, the strategist should call it out.
- **The debate matters.** If the devil-advocate raises a legitimate concern and no one can refute it, the spec drops a tier. The point of the team is adversarial review, not consensus bias.
- **Teammates are read-only.** Require plan approval — no teammate should modify any project files. This is a review skill, not an implementation skill.

## Fallback: Single-Agent Mode

If agent teams are not enabled or the user prefers a lighter-weight review, fall back to a single-session review using Explore subagents:

1. Launch 3 Explore agents in parallel (data readiness, implementation complexity, strategic fit)
2. Synthesize findings yourself using the same scoring framework
3. Note in the output that this was a single-agent review (no adversarial debate phase)
