# Spec: Generic Conviction Scorer (Shadow Mode)

> **Status:** OBSOLETE — Replaced by Strategy Lab (strategy_lab.py + always-fire pattern)

**Status:** ACTIVE — shadow scorer built 2026-04-02, collecting data. Waiting on BTC live gate (Decision #17, 33/50) for Phase A analysis.
**Version:** 2.0 (rewritten 2026-04-01, supersedes v1.0)
**Scope:** Shadow tracking only. Zero changes to production pipelines.

---

## Problem

The current conviction system is a set of hardcoded if/else branches per asset:

- BTC: UP + price 20-70% → conv=4, DOWN + NEUTRAL → conv=2, else conv=3, consensus boost +1
- ETH: everything → conv=2 (paper trading)

This produces a coarse signal. There is no continuous strength measure — a barely-qualifying 3-candle streak gets the same conviction as a 7-candle streak with 2% net return. The estimate is always 0.62 or 0.38 regardless of how strong the underlying signal is.

## Goal

Build a parameterized scorer that produces a **continuous strength signal (0.0–1.0)** and maps it to conviction tiers. Run it in shadow mode alongside production to collect calibration data. After 100+ shadow bets per pipeline, compare shadow tiers to actual outcomes to determine whether the continuous signal outperforms the current binary logic.

## Why Shadow Mode

The scorer must not change any production behavior. Shadow mode means:
- No changes to `predict.py` conviction logic, estimates, or DB writes
- Shadow output logged in reasoning JSON under a new key, or to a separate log file
- Toggleable via `--shadow-track` flag (default: off)
- Can be enabled/disabled without any production risk

---

## Prerequisites (must be met before implementation)

| Gate | Condition | Why |
|------|-----------|-----|
| BTC live validation | 50+ live BTC bets completed (Decision #17) | Need a stable live baseline to shadow against. Shadow data collected during an unstable transition is uninterpretable. |
| ETH Phase 1 | 50+ resolved ETH momentum predictions | ETH parameters can't be calibrated without momentum-era data. Contrarian-era numbers are useless. |

**Do not implement before both gates pass.** The architecture can be designed now, but deployment must wait.

---

## Architecture

### Module: `src/shadow_conviction_scorer.py`

A standalone module with no production side effects. Two pure functions:

```python
def strength_signal(candles, signed_streak, config_key, regime=None):
    """
    Continuous signal strength from 0.0 (barely qualifies) to 1.0 (maximum conviction).

    Components:
      length_strength  = min(log(streak_len) / log(baseline_streak), 1.0)
      magnitude_strength = min(|net_return_pct| / (realized_vol × magnitude_multiplier), 1.0)
      strength = length_strength × magnitude_strength

    Returns:
      estimate: 0.50 ± (max_edge × strength)
      confidence: "high" if strength >= high_confidence_threshold, else "medium"
      strength: float 0.0–1.0
      components: {length_strength, magnitude_strength}
    """

def conviction_from_estimate(estimate, config):
    """
    Map continuous estimate to conviction tier (0, 2, 3, 4, 5)
    using parameterized edge thresholds.

    tier = highest tier where abs(estimate - 0.50) >= conv_thresholds[tier]
    """
```

### Why two components

**Length** captures how sustained the streak is. A 3-candle streak is the minimum; a 7-candle streak is rare and historically stronger. The log curve prevents over-weighting extremely long streaks (diminishing returns after ~8 candles).

**Magnitude** captures how much price actually moved during the streak, relative to current volatility. A 3-candle streak that moved 0.1% in a 2% volatility regime is weak. A 3-candle streak that moved 1.5% in a 0.5% volatility regime is strong. This is the component the current system completely lacks.

### Net return calculation

```python
# Net return over the streak period
streak_start_idx = len(candles) - abs(signed_streak)
if streak_start_idx < 0:
    streak_start_idx = 0  # streak spans entire window
start_price = candles[streak_start_idx]["open"]
end_price = candles[-1]["close"]
net_return_pct = (end_price - start_price) / start_price * 100
```

### Realized volatility floor

When `realized_vol` from `compute_regime_from_candles()` approaches zero (dead markets, tiny moves), magnitude would spike to infinity. Floor at 0.02% to prevent this.

---

## Asset Configuration

A single config dict per pipeline. **BTC values are derived from 227+ paper bets. ETH values are placeholders — must be recalibrated from Phase 1 momentum data before ETH shadow mode is enabled.**

```python
SHADOW_CONFIGS = {
    "btc_5m": {
        "min_streak": 3,
        "baseline_streak": 8,          # log(8) normalizes streak length
        "magnitude_multiplier": 2.0,   # vol-relative magnitude scaling
        "max_edge": 0.14,              # estimate range: 0.36–0.64
        "high_confidence_threshold": 0.80,
        "conv_thresholds": [0.02, 0.05, 0.08, 0.12],  # edge → tier 2/3/4/5
    },
    "btc_15m": {
        "min_streak": 2,
        "baseline_streak": 5,          # lower — fewer candles per window
        "magnitude_multiplier": 2.5,   # wider moves expected on 15m
        "max_edge": 0.14,
        "high_confidence_threshold": 0.80,
        "conv_thresholds": [0.02, 0.05, 0.08, 0.12],
    },
    "eth_5m": {
        # PLACEHOLDER — must be recalibrated from ETH momentum data (Phase 1)
        # These are NOT validated. Do not enable ETH shadow mode until recalibrated.
        "min_streak": 3,
        "baseline_streak": 6,
        "magnitude_multiplier": 2.0,
        "max_edge": 0.08,              # tighter — ETH spread eats more edge
        "high_confidence_threshold": 0.85,
        "conv_thresholds": [0.03, 0.04, 0.05, 0.07],
    },
}
```

**No dollar sizing in config.** Sizing is a production concern (currently $25 flat, advancing to $50/$Kelly per the sizing phases). The shadow scorer tracks tiers only. Dollar amounts are derived at trade time from the active sizing phase, not baked into conviction config.

---

## Integration

### Where it hooks in

Inside `predict.py` and `predict_eth.py`, at the very end of the per-market loop, after `store_prediction()`:

```python
if shadow_mode:
    try:
        from shadow_conviction_scorer import strength_signal, conviction_from_estimate
        shadow = strength_signal(candles, signal["streak"], config_key, regime)
        shadow["conviction_tier"] = conviction_from_estimate(shadow["estimate"], config_key)
        # Append to reasoning JSON — never touches conviction_score column
        # OR log to structured log file
    except Exception:
        pass  # shadow must never break production
```

### What gets logged per prediction

```json
{
    "shadow_generic_scorer": {
        "config_key": "btc_5m",
        "strength": 0.73,
        "length_strength": 0.86,
        "magnitude_strength": 0.85,
        "estimate": 0.60,
        "confidence": "medium",
        "conviction_tier": 4,
        "production_conviction": 3,
        "production_estimate": 0.62,
        "net_return_pct": 0.42,
        "realized_vol": 0.31
    }
}
```

The key comparison fields are `conviction_tier` (shadow) vs `production_conviction` (actual). When these diverge, we can measure which was right after resolution.

### Downstream overrides (logged, not applied)

These modifiers are computed and recorded for analysis but have zero production effect:

- **Consensus boost:** +1 tier (capped at 5) when both exchanges agree on streak direction
- **Liquidity cap:** If CLOB max@2% slippage < threshold, cap tier (logged as `liquidity_capped: true`)

---

## Validation Plan

### Phase A: BTC 5m Shadow (first)

```
trigger:    50+ live BTC bets completed (Decision #17 resolved)
duration:   100 shadow bets (~3-5 days at current volume)
analysis:
  1. Correlation between shadow strength and actual win rate (target: r >= 0.20)
  2. Shadow tier distribution — is it meaningfully different from production?
     (if shadow produces 95% conv=3, same as production, there's no new information)
  3. Divergence analysis: when shadow tier > production tier, is WR higher?
     When shadow tier < production tier, is WR lower?
  4. Shadow estimate calibration: bin shadow estimates into quintiles,
     compare to actual win rates per bin
success:    r >= 0.20 AND shadow tiers produce a meaningful distribution
            AND divergence analysis shows shadow outperforms on tier splits
failure:    r < 0.10 at 100+ bets → the continuous signal adds no information
```

### Phase B: BTC 15m Shadow (after Phase A)

Same analysis on 15m pipeline. Smaller sample — extend to 50 shadow bets minimum.

### Phase C: ETH 5m Shadow (after ETH Phase 1 validates)

Recalibrate ETH config from Phase 1 momentum data first. Then shadow for 100 bets.

### Migration decision (after all phases)

If shadow scoring consistently outperforms production conviction on BTC:
1. Replace production conviction logic with shadow scorer
2. Keep flat $25 sizing — conviction tiers gate which bets fire, not how much
3. Enable ETH tiers above conv=2 only after ETH shadow validates

If shadow scoring does NOT outperform:
- The current binary system is good enough. Archive the scorer.
- The data still has value — magnitude/length components may inform future filters even if the full scorer doesn't replace production.

---

## Tests

```
tests/test_shadow_conviction.py:
  - test_strength_signal_returns_valid_structure
  - test_strength_zero_for_minimum_streak    # 3-candle streak with tiny move → ~0.0
  - test_strength_one_for_max_streak         # 8+ candle streak with large move → 1.0
  - test_magnitude_floor                     # realized_vol near zero → floor applied
  - test_conviction_tier_mapping             # edge thresholds produce correct tiers
  - test_all_configs_have_required_keys
  - test_shadow_does_not_modify_production   # run full predict cycle with shadow on,
                                             # verify DB conviction_score unchanged
```

---

## Non-Functional Requirements

- Zero new external dependencies ($0/day, pure computation)
- Shadow path must be wrapped in try/except — a shadow bug must never crash production
- Toggleable via `--shadow-track` CLI flag (default: off)
- No DB schema changes, no new tables
- Must work identically across btc_5m, btc_15m, eth_5m configs
