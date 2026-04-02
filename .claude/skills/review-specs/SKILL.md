---
name: review-specs
description: >
  Systematic evaluation of unimplemented feature specs for quality, feasibility,
  and priority. Use when: user says "review specs", "spec critique", "which spec next",
  "prioritize specs", "evaluate specs", "spec triage", or "/review-specs".
  Produces a ranked priority matrix with per-spec scorecards.
---

# Review Specs

Evaluate all unimplemented feature specs in `docs/specs/` and produce a ranked priority matrix. Answers the question: "Which spec should we build next?"

## Prerequisites

- **Always `git pull` first.**
- Specs live in `docs/specs/`. There are currently 10 unimplemented specs.

## Process

### 1. Pull latest and read all specs

```bash
cd /Users/mrmrnm-max/polymarket-bot
git pull --rebase || git pull
```

Read every file in `docs/specs/`:
- `spec_rsi_conviction_gate.md` — RSI as pre-bet filter
- `spec_obv_bucket_filter.md` — On-Balance Volume for 0.50-0.70 bucket
- `spec_vwap_mean_reversion.md` — VWAP deviation for mean-reverting bets
- `spec_volatility_breakout.md` — Volatility compression→expansion detection
- `spec_stochastic_entry_timing.md` — Stochastic Oscillator entry timing
- `spec_order_flow_imbalance.md` — CLOB bid/ask imbalance
- `spec_market_price_dislocation.md` — Polymarket price lag vs BTC spot
- `spec_cross_exchange_lead_lag.md` — Kraken/Coinbase lead-lag arbitrage
- `spec_dead_regime_harvesting.md` — Edge extraction from mean-reverting/dead-hour regimes
- `spec_generic_conviction_engine.md` — Parameterized conviction scorer for all assets

### 2. Read context for priority calibration

- `docs/core/strategy.md` — current signal logic (what the system does now)
- `docs/core/ROADMAP.md` — current phase, what gates exist
- `docs/core/decisions.md` — which decisions relate to these specs
- Latest daily report from `docs/daily/` — current shadow indicator data (RSI, OBV, VWAP)
- `docs/optimizations.json` — any shadow experiments already tracking spec signals
- `CLAUDE.md` — frozen files list, validation principles

### 3. Score each spec on 5 axes

Rate 1-5 for each:

| Axis | 1 (Bad) | 5 (Great) |
|------|---------|-----------|
| **Data Readiness** | No data exists, would need new API | Shadow data already collecting, 100+ samples |
| **Implementation Complexity** | New dependencies, touches frozen files, multi-pipeline | Single file change, conviction demotion only |
| **Edge Hypothesis Strength** | No supporting data, pure theory | Shadow indicator data shows clear signal |
| **Isolation** | Interacts with other filters, can't A/B test | Fully independent, can toggle without side effects |
| **Reversibility** | Requires code surgery to undo | Conviction demotion = flip a number back |

### 4. Cross-reference shadow indicator data

The daily report tracks shadow indicators that map to specific specs:

| Shadow Indicator | Related Spec | What to Check |
|-----------------|--------------|---------------|
| RSI(14) | `spec_rsi_conviction_gate` | Does RSI divergence correlate with bet outcomes? |
| OBV slope | `spec_obv_bucket_filter` | Does OBV slope predict 0.50-0.70 bucket outcomes? |
| VWAP deviation | `spec_vwap_mean_reversion` | Does VWAP > 1σ predict mean reversion? |
| Spread % | `spec_order_flow_imbalance` | Does wide spread predict poor fills? |

Query the DB for shadow indicator correlation if data exists:
```sql
-- Check if shadow indicators are stored (depends on pipeline version)
SELECT COUNT(*) FROM predictions WHERE reasoning LIKE '%RSI%';
SELECT COUNT(*) FROM predictions WHERE reasoning LIKE '%OBV%';
```

### 5. Check for conflicts and frozen file violations

- Two specs that touch the same code path cannot ship simultaneously (violates "one change at a time" rule)
- Any spec requiring changes to frozen files (`src/predict.py`, `src/ci_run.py`, `src/btc_data.py`, `src/score.py`, `src/clob_depth.py`, `.github/workflows/predict-and-score.yml`) must be flagged prominently

For each spec, identify:
- Which source files it would modify
- Whether it conflicts with any other spec
- Whether it touches a frozen file (requires explicit user approval)

### 6. Produce the priority matrix

#### Tier 1 — Ready Now
Specs where: shadow data validates the hypothesis, complexity is low, fully isolated, easily reversible. These can be planned and implemented this session.

#### Tier 2 — Needs More Data
Specs where: hypothesis is promising but shadow sample is too small (< 100 data points), or data collection hasn't started yet. Action: ensure shadow tracking is active, check back in N days.

#### Tier 3 — Needs Redesign
Specs where: quality issues in the spec itself (unclear hypothesis, no success criteria, conflicts with other specs), or would require frozen file changes without clear justification.

#### Per-Spec Entry Format

```
### spec_name (Tier X) — Total Score: NN/25

| Axis | Score | Notes |
|------|-------|-------|
| Data Readiness | X/5 | ... |
| Complexity | X/5 | ... |
| Hypothesis | X/5 | ... |
| Isolation | X/5 | ... |
| Reversibility | X/5 | ... |

**Assessment**: 1 paragraph — what the spec does, whether data supports it, blocking issues.
**Frozen files**: PASS / FAIL (list affected files)
**Related decisions**: #N, #M
**Shadow data status**: Collecting (N samples) / Not collecting / N/A
**Recommendation**: Build now / Wait for data / Redesign spec
```

## Key Rules

- **Score honestly.** A spec with a great idea but no data is Tier 2, not Tier 1.
- **Frozen files are a hard constraint.** A spec that requires changing `src/predict.py` is automatically higher complexity and needs explicit approval — flag it, don't hide it.
- **One change at a time.** If the user wants to build two specs, they ship sequentially with separate optimization registrations.
- **Shadow mode first.** Any spec that can be shadow-tested before going live should be. This is the project's validation philosophy.
- **Connect to decisions.** If a spec addresses a tracked decision in `docs/core/decisions.md`, call it out — it may already have monitoring data.
