# Bybit BTCUSDT 5m — exhaustive negative result

**Date:** 2026-04-08
**Status:** Signal research on this venue/cadence complete. No edge found.

This is the consolidated finding after Phase 2 of the Bybit pivot failed,
three alternative candle-only signal families failed, a cadence sweep
failed, and two derivatives-telemetry signal families failed. Seven
signal classes tested. All dead on BTCUSDT 5m perp after fees.

## What was tested

| # | Signal class | File | Best cell |
|---|---|---|---|
| 1 | Streak momentum (ride) | `backtest_bybit.py` | 28.6% WR / 4570 trades |
| 2 | Streak fade | `backtest_bybit.py` (fade flip) | 35.5% WR |
| 3 | Volatility breakout | `signals_bybit.volbreakout_signal` | 24.4% WR / 566 trades |
| 4 | VWAP mean reversion | `signals_bybit.vwap_mr_signal` | 67.7% WR / 753 (P&L −$337 due to tail) |
| 5 | Cross-venue lead/lag (spot→perp) | `signals_bybit.xexch_leadlag_signal` | 19.3% WR (spot LAGS perp) |
| 6 | Funding rate extreme (fade) | `backtest_bybit_funding_oi.py` | 41.6% WR / 387 |
| 7 | Funding rate extreme (momentum) | `backtest_bybit_funding_oi.py` | 46.4% WR / 220 |
| 8 | OI delta (fade) | `backtest_bybit_funding_oi.py` | 44.0% WR / 402 |
| 9 | OI delta (momentum) | `backtest_bybit_funding_oi.py` | 41.3% WR / 412 |
| 10 | VWAP-MR @ 15m | `backtest_bybit_cadence.py` | 61.5% WR / 234 (P&L −$1) |
| 11 | VWAP-MR @ 1h | `backtest_bybit_cadence.py` | 55.6% WR / 81 (P&L −$116) |

Plus a stop-loss sweep on VWAP-MR at 5m (stop_sd_mult ∈ {1.0, 1.5, 2.0, 3.0}):
every stop level produced 0.00% WR on stop-outs and made total P&L
monotonically worse. The "losing half" of VWAP-MR is not a cappable
drawdown — it's the trend regime, and tightening the stop just locks
in more losses at the worst possible moment.

## What it all means

1. **The mean-reversion substrate is real.** VWAP-MR mean_revert exits
   are 99-100% WR across every cadence (5m, 15m, 1h), every entry_z
   (2.0, 2.5, 3.0), every hold. Whenever price does revert through VWAP,
   the signal was right. This is consistent with lag-1 autocorr = −0.017
   and VR(5) = 0.939 — there IS a tiny mean-reverting component in the
   tape.

2. **The mean-reversion edge is smaller than fees + the opposing trend
   regime.** The ~67% of trades that don't revert within a reasonable
   hold lose at 10-20% WR and 1.5-2x the magnitude of the winners. Those
   are not "noise" — they're the trend regime where price just keeps
   going. Total P&L is negative at every parameter combination.

3. **Cadence doesn't fix it.** At 15m the winner/loser structure is
   identical (100% mean_revert WR, 40-50% other). At 1h the sample
   drops below significance. Reversion horizon is not the constraint.

4. **Derivatives telemetry doesn't fix it either.** Funding and OI on
   both sides (fade + momentum) produce 35-46% WR on every cell tested.
   Crowding-based signals have no predictive power on this venue/cadence.

5. **Cross-venue lead/lag is anti-signal.** Bybit spot *lags* Bybit perp,
   not the other way around, so following spot gives 19% WR. This alone
   killed the "Coinbase/Kraken leads" hypothesis for this venue.

6. **Candle-only momentum is dead on this venue.** Streak ride, streak
   fade, breakout — all under 36% WR. The original Polymarket signal
   does not transfer.

## What's left to try

The options that *weren't* tested and could still produce edge:

- **Order-book imbalance.** Requires L2 snapshots (WebSocket, not REST).
  Live capture only; can't be backtested from public history.
- **Trade-flow / taker aggression.** Bybit public trade stream.
  Also live-capture only.
- **Different venue.** Coinbase perp, Deribit, Hyperliquid — each has
  different microstructure. Nothing learned here transfers automatically.
- **Different asset.** ETH, SOL perps on same venue. The mean-reversion
  substrate may be stronger or weaker; signal tuning would start fresh.
- **Different cadence class.** 1m (ultrafast) or 4h+ (daily-ish) — the
  5m-to-1h range tested here is where most retail strategies fail.

## What this means for the Bybit pipeline

The pipeline is fully instrumented (Phases 0-1, 3-10 of the pivot plan)
but has no signal worth running. The acceptance-criteria doc
(`docs/pipelines/bybit_acceptance_criteria.md`) explicitly expects this
outcome — it is aspirational, not current. Bybit stays PAPER and
collects counterfactual data against whichever signal ships next.

The honest recommendation: **do not spend more signal-research hours on
Bybit BTCUSDT 5m with public OHLCV+derivatives data.** If the pivot
continues, it should be via (a) live L2 capture on this venue, or
(b) a different venue/asset pair.

## Files produced in this run

- `tools/signals_bybit.py` — volbreakout, vwap_mr, xexch_leadlag
- `tools/backtest_bybit_alt.py` — pluggable harness (time ceiling + mean-revert exit + stop-loss)
- `tools/backtest_bybit_cadence.py` — resample 5m→15m/1h, re-sweep VWAP-MR
- `tools/backtest_bybit_funding_oi.py` — funding/OI signals
- `tools/fetch_spot_history.py` — Bybit spot 5m cache
- `tools/fetch_bybit_funding_oi.py` — funding + OI cache
- `data/spot_5m_6mo.csv` — 52k rows
- `data/funding_6mo.csv` — 600 rows (8h cadence)
- `data/oi_5m_6mo.csv` — 52k rows
- Reports: `bybit_alt_signals_backtest_2026-04.md`,
  `bybit_cadence_sweep_2026-04.md`,
  `bybit_funding_oi_backtest_2026-04.md`,
  and this doc.
