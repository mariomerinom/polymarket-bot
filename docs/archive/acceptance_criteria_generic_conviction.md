# Acceptance Criteria: Generic Conviction Scorer (Shadow Tracking Mode Only)
Status: Ready for implementation
Scope: Purely observational / shadow tracking (no changes to any production pipelines)
Version: 1.0 (adapted from spec_generic_conviction_scorer.md + dynamic estimate improvements)
Deployment Constraint: Must be built in complete isolation. No modifications to predict.py logic, momentum_signal, store_prediction, conviction calculation, DB writes, or any existing pipeline behavior. The only permitted addition is optional, non-blocking shadow logging.
1. Overall Goal & Success Definition

Implement the full generic conviction scorer exactly as specified, but exclusively for tracking and data collection.
The scorer must run in parallel (shadow mode) on every prediction cycle and record its outputs without altering any existing estimate, conviction tier, bet decision, or database row.
This allows immediate collection of shadow data for future calibration while keeping 100 % of current production logic untouched.
The scorer must still produce a continuous strength signal (0.0–1.0), estimate, confidence label, and conviction tier using the exact parameterized logic from the spec.
After 100+ shadow bets, the collected data must show estimate-to-actual-win-rate correlation ≥ 0.20 (measured retrospectively) before any future production migration is considered.

2. Asset Configuration

A single, standalone configuration dictionary must exist (e.g., in a new file conviction_config.py or at the top of a new shadow module) containing separate entries for at least btc_5m, btc_15m, and eth_5m.
Each config entry must include exactly the parameters and default values listed below. No code branches may reference asset names.





ParameterBTC 5mBTC 15mETH 5mmin_streak323baseline_streak856magnitude_multiplier2.02.52.0max_edge0.140.140.08high_confidence_threshold0.800.800.85conv_thresholds[0.02,0.05,0.08,0.12]same[0.03,0.04,0.05,0.07]bet_sizes{3:75,4:200,5:300}same{3:25,4:50,5:75}

These values must be treated as constants for the shadow phase; they exist only to enable tracking and later calibration.

3. Strength Signal Component (Shadow)

Must be implemented as a pure function strength_signal(candles, signed_streak, config_key, regime=None).
Length component must use: length_strength = min(math.log(streak_len) / math.log(baseline_streak), 1.0).
Magnitude component must be volatility-relative: magnitude_strength = min(abs(net_return_pct) / (realized_vol × magnitude_multiplier), 1.0), using realized_vol from compute_regime_from_candles() (with floor of 0.02 %).
Net-return calculation must correctly handle the edge case (use candles[0]["open"] when streak spans entire window).
Combined strength = length_strength × magnitude_strength.
Estimate must be 0.50 ± (max_edge × strength) based on direction.
Confidence label must be “high” only if strength ≥ high_confidence_threshold.
The function must work identically whether called with btc_5m, btc_15m, or eth_5m config.

4. Conviction Mapping Component (Shadow)

Must be implemented as a pure function conviction_from_estimate(estimate, config).
Tier (0, 2, 3, 4, or 5) must be derived solely from abs(estimate - 0.50) against the four conv_thresholds.
Must include the downstream overrides for tracking purposes only:
Consensus boost (+1, capped at 5) when both exchanges agree.
Liquidity cap (using CLOB data) and min-viable-bet downgrade to tier 2.

These overrides are computed and logged in shadow mode only; they have no effect on production conviction.

5. Integration & Isolation Requirements

Zero modifications to any existing function in predict.py (momentum_signal, store_prediction, run_predictions, compute_regime_from_candles, etc.).
The shadow scorer must be placed in a separate, importable module (e.g., shadow_conviction_scorer.py).
Inside predict.py, the only permitted change is an optional, non-blocking call at the very end of the per-market loop (e.g., inside an if shadow_mode: block that is off by default) to compute and log the shadow results.
Shadow results must be recorded exclusively in the existing reasoning JSON blob under a new key (e.g., "shadow_generic_scorer") or printed to a separate log file — never written to any conviction or estimate column used by production logic.
The entire shadow path must be toggleable via a command-line flag (--shadow-track) that defaults to False.
No DB schema changes, no new tables, no alteration of any stored conviction_score or estimate.

6. Shadow Tracking & Logging

For every market that reaches the prediction stage, the shadow scorer must compute and record:
config_key used
length_strength, magnitude_strength, strength
estimate, confidence label, conviction tier, final bet size (from config)
Any downstream filter adjustments (logged for future use)

All shadow data must be emitted in a machine-readable format (JSON line or structured log) that can be easily parsed later for calibration.
Logging must be silent by default and only active when --shadow-track is passed.

7. Calibration & Validation Requirements (Tracking Phase)

After 100+ shadow bets, a separate offline script (not part of this acceptance) must be able to read the shadow logs and compute:
Estimate-to-win-rate correlation (target ≥ 0.20)
Shadow P&L vs actual live P&L
Distribution of conviction tiers

Daily logs must include a “Shadow Scorer Health” section showing average estimate on eventual wins/losses and correlation.
This data collection phase must run for at least 100 bets per pipeline before any production migration discussion.

8. Non-Functional & Risk Mitigation

The implementation must remain 100 % pure computation ($0/day) with zero new external dependencies.
Full backward compatibility is mandatory — existing predict.py behavior, DB writes, and live conviction must be identical with or without the shadow flag.
When realized_vol approaches zero, magnitude calculation must apply the 0.02 % floor.
Configs must live in one central place.
The log curve must not over-weight short streaks (magnitude component must still dominate).


Acceptance Test Summary
When the shadow scorer can be enabled via --shadow-track and produces clean, parallel data for every prediction without any change to production estimates, conviction, or database behavior, it is considered accepted. This establishes a live tracking baseline for future calibration and migration.