# Momentum Transfer Backtest: SPY, Gold, EUR/USD

**Date:** 2026-04-11 18:00 UTC
**Signal:** `momentum_signal()` from `src/predict.py`
**Resolution:** next-candle continuation (same as BTC synthetic markets)
**Data source:** yfinance, 5-min candles, ~60 days

## Data Summary

| Asset | Ticker | Candles |
|-------|--------|---------|
| S&P 500 ETF | `SPY` | 4,558 |
| Gold Futures (XAUUSD proxy) | `GC=F` | 13,367 |
| EUR/USD | `EURUSD=X` | 16,702 |

## Win Rate by Asset and Streak Length

| Asset | Streak >= 2 | Streak >= 3 | Streak >= 4 | Streak >= 5 |
|-------|--------------|--------------|--------------|--------------|
| SPY | 49.8% (2251) | 49.0% (1122) | 50.2% (550) | 48.9% (276) |
| Gold | 47.7% (6479) | 46.5% (3087) | 44.7% (1434) | 47.0% (641) |
| EURUSD | 38.0% (4393) | 41.3% (1670) | 40.6% (690) | 41.1% (280) |

## Win Rate by Actual Streak Bucket (min_streak=3)

| Asset | Streak=3 | Streak=4 | Streak=5 | Streak 6+ |
|-------|----------|----------|----------|-----------|
| SPY | 47.9% (572) | 51.5% (274) | 48.9% (141) | 48.9% (135) |
| Gold | 48.0% (1653) | 42.9% (793) | 48.5% (340) | 45.2% (301) |
| EURUSD | 41.8% (980) | 40.2% (410) | 37.6% (165) | 46.1% (115) |

## Win Rate by Regime (min_streak=3)

Shows WR when regime filter is applied (exclude MEAN_REVERTING) vs. all signals.

| Asset | All Signals | Excl. Mean-Reverting | HIGH_VOL Only | LOW_VOL Only |
|-------|-------------|---------------------|---------------|--------------|
| SPY | 49.0% (1122) | 49.8% (838) | 51.0% (261) | 49.1% (230) |
| Gold | 46.5% (3087) | 46.4% (2316) | 44.0% (1193) | 49.0% (208) |
| EURUSD | 41.3% (1670) | 42.8% (1167) | 33.3% (6) | 41.1% (1555) |

## Regime Distribution (min_streak=3)

| Asset | LOW_VOL | MEDIUM_VOL | HIGH_VOL | TRENDING | NEUTRAL | MEAN_REV |
|-------|---------|------------|----------|----------|---------|----------|
| SPY | 20.5% (230) | 56.2% (631) | 23.3% (261) | 25.7% (288) | 49.0% (550) | 25.3% (284) |
| Gold | 6.7% (208) | 54.6% (1686) | 38.6% (1193) | 24.7% (763) | 50.3% (1553) | 25.0% (771) |
| EURUSD | 93.1% (1555) | 6.5% (109) | 0.4% (6) | 22.1% (369) | 47.8% (798) | 30.1% (503) |

## Comparison with BTC Baseline

BTC 5m momentum signal reference (from live trading):
- **BTC paper WR:** ~60-65% (streak >= 3)
- **BTC live WR:** ~55-60% (after fill/execution drag)

**Interpretation guide:**
- WR > 55%: Signal transfers, worth paper trading
- WR 50-55%: Marginal, needs regime filtering or adaptation
- WR < 50%: Signal does NOT transfer to this asset

## Key Findings

### S&P 500 ETF (SPY)
- **Overall WR (streak>=3):** 49.0% on 1122 signals
- **Filtered WR (excl. mean-rev):** 49.8% on 838 signals
- **Verdict:** DOES NOT TRANSFER

### Gold Futures (XAUUSD proxy) (Gold)
- **Overall WR (streak>=3):** 46.5% on 3087 signals
- **Filtered WR (excl. mean-rev):** 46.4% on 2316 signals
- **Verdict:** DOES NOT TRANSFER

### EUR/USD (EURUSD)
- **Overall WR (streak>=3):** 41.3% on 1670 signals
- **Filtered WR (excl. mean-rev):** 42.8% on 1167 signals
- **Verdict:** DOES NOT TRANSFER
- **Note:** EURUSD has ~29% doji candles (close == open) due to low tick granularity in yfinance data. Dojis are treated as streak-breakers. The sub-50% WR at 41% suggests FX momentum actively mean-reverts at this timeframe.

### Overall Conclusion

The 5-minute candle streak momentum signal does **not** transfer to traditional assets. All three assets show WR at or below 50%, compared to BTC's 60-65%. This is consistent with the efficient market hypothesis: BTC 5-minute markets on Polymarket have structural inefficiencies (binary resolution, prediction market mechanics) that traditional markets do not. The momentum edge appears crypto-specific, not a universal microstructure phenomenon.

**Recommendation:** Do not expand momentum signal to non-crypto assets. Focus on additional crypto pairs (ETH validated, SOL next candidate) where the same market structure inefficiency exists.

## Methodology Notes

1. **Data:** yfinance 5-min candles. Limited to ~60 days (yfinance constraint for intraday).
2. **Signal:** Identical `momentum_signal()` from `src/predict.py` with default BTC config.
3. **Resolution:** Next-candle continuation. If predicted UP and next candle close > open, it is a win.
4. **Regime:** `compute_regime_from_candles()` uses BTC-calibrated vol thresholds (BTC_VOL_LOW=0.05, BTC_VOL_HIGH=0.12). These thresholds may not be optimal for other assets.
5. **Limitations:** 60-day window is small (~50-200 signals per asset). Results should be treated as directional, not definitive. Regime thresholds need asset-specific calibration.
6. **No transaction costs.** This is a pure signal test, not a P&L simulation.
7. **Doji handling:** Production `momentum_signal()` treats dojis (close == open) as UP. This backtester treats dojis as streak-breakers (FLAT) to avoid phantom streaks, especially critical for EURUSD which has 29% doji rate in yfinance 5m data.
