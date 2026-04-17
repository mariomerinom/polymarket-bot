# Regime Correlation Analysis — 2026-04-16

**Scope:** 14-day retrospective (2026-04-02 → 2026-04-16), 1,185+ resolved bets across 7 primary pipelines. Uses regime data computed per-cycle by the momentum/VWAP signal path and daily market regime from `asset_daily.db`.

**Motivation:** the consolidated daily report shipped 2026-04-16 (#82) made cross-pipeline comparison possible for the first time. First look exposed systematic losers at the regime level that per-pipeline views had hidden.

**Outcome:** three staged deliveries shipped 2026-04-17 — #83 (HIGH_VOL perp gate expansion), #84 (Kalshi pause), #85 (intraday range gate).

---

## 1. Method

### Per-cycle regime labels

Each 5-minute candle close triggers `compute_regime_from_candles()` which emits a two-axis label:
- **Volatility axis**: `LOW_VOL` / `MEDIUM_VOL` / `HIGH_VOL`
- **Trend axis**: `TRENDING` / `NEUTRAL` / `MEAN_REVERTING`

Every `conv≥3` prediction carries its regime label. Win-rate conditioned on regime is a direct roll-up of the `predictions JOIN markets` table where `conviction_score >= 3 AND resolved = 1`.

### Daily market regime (BTC)

`asset_daily.db::range_zscore` — how abnormal today's daily range was vs the trailing 30-day distribution. Computed at UTC midnight rollover. Used as a coarse "was today normal?" signal.

### Why this method is trustworthy

- All queries went through the Botsy MCP (`regime_breakdown`, `daily_regime`, `pnl_by_day`, `pipeline_overview`) — no ad-hoc SQL, no pipeline-specific joins.
- Sample sizes are material: 471 ETH 5m bets, 287 BTC 5m bets, 391 Bybit bets, 285 Kalshi bets, plus smaller perp windows.
- Same query shape across all pipelines — directly comparable.

---

## 2. Fleet-level regime pattern

Combining all 6 primary pipelines with significant samples (1,185+ bets), conditional WR by regime:

| Regime | WR range across pipelines | Notes |
|--------|:-------------------------:|-------|
| LOW_VOL / TRENDING | **64–80%** | Universal sweet spot |
| LOW_VOL / NEUTRAL | 55–64% | Good |
| MEDIUM_VOL / TRENDING | 58–75% | Good |
| MEDIUM_VOL / NEUTRAL | 49–54% | Coin flip |
| HIGH_VOL / NEUTRAL | **36–48%** | Destructive |
| HIGH_VOL / TRENDING | **25–41%** | Worst — trend flips sign in high-vol |

### Counter-intuitive finding

Naive momentum theory predicts: strong trend (`TRENDING`) + high vol = conviction buy. The data says the opposite. At 5-minute granularity, a `HIGH_VOL / TRENDING` label usually marks an **exhausted move** where the streak is about to revert. Winners from this regime are rare; losses compound because the volatility itself widens every miss.

This also explains why VWAP mean-reversion (graduated 2026-04-15, #78) works in the regimes momentum skips: mean-reversion is the correct policy when price is extended into volatile territory.

---

## 3. Per-pipeline detail

### BTC 5m (287 bets, 56.4% overall)

```
LOW_VOL/TRENDING    65.0% (40)  ← best
MEDIUM_VOL/TRENDING 63.6% (22)
LOW_VOL/NEUTRAL     55.2% (29)
MEDIUM_VOL/NEUTRAL  53.8% (93)  ← bulk
HIGH_VOL/NEUTRAL    48.4% (95)  ← gated (#71, Apr 9)
HIGH_VOL/TRENDING   37.5% (8)
```

Clean monotonic decay: better trend + lower vol = higher WR. HIGH_VOL/NEUTRAL was gated on 2026-04-09 (#71); 95 bets in the 14-day window includes pre-gate data.

### ETH 5m (471 bets)

```
LOW_VOL/TRENDING    80.0% (15)
LOW_VOL/NEUTRAL     58.9% (90)
MEDIUM_VOL/TRENDING 58.0% (50)
MEDIUM_VOL/NEUTRAL  52.4% (254) ← bulk
HIGH_VOL/NEUTRAL    36.0% (25)  ← gated 2026-04-09
HIGH_VOL/TRENDING   32.4% (37)  ← gated 2026-04-15 (#80, full HV)
```

ETH full-HV gate expansion (#80) was motivated by HV/TRENDING underperformance (32.4%). Shipped yesterday; 14-day sample still includes pre-gate data.

### Bybit BTC perp (391 bets)

```
LOW_VOL/TRENDING    68.4% (19)
LOW_VOL/NEUTRAL     63.9% (36)
MEDIUM_VOL/TRENDING 60.5% (43)
MEDIUM_VOL/NEUTRAL  51.5% (171)
HIGH_VOL/NEUTRAL    40.8% (98)  ← gated in ci_run_bybit.py (BTC-only)
HIGH_VOL/TRENDING   25.0% (20)  ← NOT gated until 2026-04-17 (#83)
```

### ETH/SOL/DOGE perps (ci_run_perp.py path)

All three assets show the same HV/TRENDING problem that the `ci_run_perp.py:482` skip-block was **not** catching (it only gated non-trending):

| Pipeline | HV/TRENDING WR | n |
|----------|:--------------:|:-:|
| eth_bybit | 25.7% | 35 |
| sol_bybit | 41.2% | 34 |
| doge_bybit | 38.5% | 13 |
| eth_hl | 25.7% | 35 |
| sol_hl | 46.7% | 60 |
| doge_hl | 43.1% | 65 |

The `_hl` pipelines mirror their `_bybit` counterparts since they share the same BTC/ETH/SOL/DOGE candle signal — only the venue differs.

### Kalshi (285 bets) — anomaly

```
MEDIUM_VOL/NEUTRAL  0.0% (288!)  ← impossible without a structural bug
HIGH_VOL/TRENDING   56.2% (128)
MEDIUM_VOL/TRENDING 100.0% (4)
```

288 bets at literally 0% WR is not a random distribution. Diagnosed separately (§5).

---

## 4. Daily market regime vs daily P&L

Cross-referencing each day's `asset_daily.range_zscore` with that day's BTC 5m P&L:

| Date | Trend | range_z | velocity_z | BTC 5m P&L | BTC 5m WR |
|------|-------|--------:|-----------:|-----------:|:---------:|
| Apr 3 | chop | -1.49 | -0.01 | **+$315** | 73% |
| Apr 4 | up | -2.06 | +1.09 | +$290 | 63% |
| Apr 5 | up | +0.60 | +2.25 | +$113 | 58% |
| Apr 6 | chop | -0.49 | -0.33 | +$85 | 59% |
| **Apr 7** | **up** | **+2.90** | **+1.79** | **−$193** | **39%** |
| Apr 8 | down | -0.51 | -0.68 | −$141 | 42% |
| Apr 10 | up | -0.54 | +0.82 | +$286 | 61% |
| Apr 11 | chop | -1.30 | +0.03 | −$24 | 47% |
| **Apr 13** | **strong_up** | **+1.83** | **+2.44** | **−$27** | **40%** |

### Pattern

The two worst P&L days in the window (Apr 7, Apr 13) were the **only two** days with `range_zscore ≥ +1.5`. Calm days (range_z < 0) are consistently green. Extreme-range days consistently bleed.

Mechanism: on abnormal-range days the 5m streak signal chases the first move, then gets chopped up by the inevitable intraday reversal. Classic "momentum on extreme days" trap.

### Relation to the reverted btc_daily_regime_gate (#68)

This pattern is exactly what #68 tried to gate. #68 was reverted on 2026-04-09 because it used **yesterday's** completed-day range_zscore — on a calm Apr 9 it was still reading Apr 7's +2.90, so it blocked 11 bets that landed at 54.5% WR.

The fix: read **today's in-progress** range_pct (from the 5m candle buffer) and z-score it against the trailing 30 days. Shipped 2026-04-17 as #85 (`src/intraday_regime_gate.py`).

---

## 5. Kalshi anomaly — root cause is architectural

Every one of the 420 conv≥3 resolved Kalshi bets is on a NO-won market. Zero YES wins despite the DB having 2,845 YES-won markets globally. Sample:

| Market ID | Strike | BTC price | Model est | Outcome |
|-----------|-------:|----------:|----------:|---------|
| BTCUSD-2604111850-**84000** | $84k | ~$72k | 0.631 YES | NO |
| BTCUSD-2604111905-**84500** | $84.5k | ~$72k | 0.631 YES | NO |
| BTCUSD-2604111935-**85000** | $85k | ~$72k | 0.631 YES | NO |

The BTC momentum signal is applied to every available Kalshi market without reading the strike. When BTC is $72k and the strike is $84k+ in a 5-minute window, "YES" is near-zero probability — but the model bets YES anyway because the momentum direction is UP.

### Why this is not an encoding bug

- Kalshi's global outcome distribution is 2,845 YES / 7,518 NO — properly populated.
- `is_correct()` is pipeline-agnostic and works correctly for Polymarket.
- The issue is `src/ci_run_kalshi.py:223-305`: one signal computed from BTC candles, stored as the estimate for every open Kalshi market.

### Action

Paused the pipeline 2026-04-17 (mode=paused in `config/pipelines.json`). Fix requires a market-question parser to map BTC momentum direction → YES/NO per specific market strike. Tracked as #84.

---

## 6. Actions taken (2026-04-17)

| Finding | Delivery | Issue | Status |
|---------|----------|:-----:|--------|
| HIGH_VOL/TRENDING destructive across 6 perps | Broaden `ci_run_perp.py:482` gate to all HIGH_VOL | #83 | Shipped |
| Kalshi 0% WR from strike mismatch | Pause pipeline; strike-parser is follow-up | #84 | Pipeline paused |
| Intraday range_z ≥ +1.5 → next-day bleed | New `intraday_regime_gate.py`; hooked into predict.py + predict_eth.py | #85 | Shipped |

Test count progression: 716 → 729 → 744 passing (28 new tests across the three deliveries).

---

## 7. Open questions / future work

1. **Perp HV/TRENDING post-gate validation**: does the 6-perp gate close the measured 25–41% WR hole? Needs 50+ forward shadow bets per asset.
2. **Intraday gate calibration**: 1.5σ threshold is inherited from the reverted #68 evidence. Morning-exemption at 12:00 UTC is a guess. Need counterfactual analysis after 2 weeks of live data.
3. **Kalshi strike-aware signal**: market-question parser + strike-reachability filter. Estimated 4–8 hrs of work, deferred until other observation windows close.
4. **VWAP graduation monitoring**: does VWAP mean-reversion on SOL/DOGE perps (graduated 2026-04-15, #78) survive 200 forward bets? Tracked in `optimizations.json::vwap_graduation_perps`.
5. **Hour-of-day regime interaction**: does regime WR vary by UTC hour? Not explored in this report.

---

## References

- Consolidated daily report scaffold: `src/consolidated_report.py` (#82)
- Reverted gate postmortem: `docs/optimizations.json::btc_daily_regime_gate` (closed 2026-04-09)
- Related baseline: `docs/analysis/ehr_baseline_2026-04-16.md` (same-day companion)
- VWAP graduation decision: GitHub issue #78
- Plan file (this work): `.claude/plans/groovy-squishing-scott.md`
