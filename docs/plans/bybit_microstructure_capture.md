# Bybit microstructure capture — plan, retention, decision gate

**Date:** 2026-04-08
**Status:** Phase A shipped (capture running under engine supervision).
Phase B in progress (waiting for data). Phase C harness built; runs as
soon as capture is non-empty. Phase D is this document.

## Why this exists

Seven signal classes derived from Bybit public REST data failed on
BTCUSDT 5m perps (see `docs/research/bybit_exhaustive_negative_2026-04.md`).
Every class that failed used OHLCV-derivable features or 8h funding
snapshots — in other words, data that any retail account anywhere can
pull on a 5-minute schedule. The entire VPS+WebSocket architecture was
built precisely so we would not be limited to that data class, but the
Bybit WS subscriptions only included `kline.*` topics. This plan closes
that gap: capture the four microstructure tapes Bybit publishes for
free, backtest the signals derived from them, and decide in writing
whether Bybit can carry paper → live on this pipeline at all.

## Phase A — Capture (shipped)

### Files

- `src/bybit_ws_capture.py` — `BybitMicrostructureCapture` class. Opens
  a dedicated WS connection to `wss://stream.bybit.com/v5/public/linear`,
  subscribes to four topics, writes each message to a topic-scoped
  rotating JSONL file. Rotation is hourly (UTC), and the previous hour
  is gzipped in place on rotation. Periodic flush every 5s so a crash
  loses at most ~5s of tape.
- `src/botsy_engine.py` — adds `bybit_microstructure_feed` coroutine
  under the existing supervisor so reconnects/restarts are handled
  identically to the kline feeds. Crash on the capture path cannot
  starve the kline dispatch path because they're separate tasks.

### Topics captured

| Label | Topic | Cadence | Purpose |
|---|---|---|---|
| publicTrade | `publicTrade.BTCUSDT` | every taker print | CVD, taker aggression, trade imbalance |
| orderbook | `orderbook.50.BTCUSDT` | ~20ms snapshots + deltas | Book imbalance, depth-at-price, spoof detection |
| liquidation | `allLiquidation.BTCUSDT` | event-driven | Liquidation cascade fade (Bybit-specific edge) |
| tickers | `tickers.BTCUSDT` | ~100ms | Live funding, mark, index, OI |

Note: `liquidation.*` was deprecated in Bybit v5; new name is
`allLiquidation.*`. An earlier version of this capture used the old
name and was silently rejected — fix is in the current module.

### Verified end-to-end on 2026-04-08

30-second smoke test against live Bybit WS produced (approximate rates
for BTCUSDT during US afternoon):

- `publicTrade`: ~2 msgs/s, ~1.7 KB/s
- `orderbook`: ~37 msgs/s, ~12 KB/s
- `tickers`: ~7 msgs/s, ~1.5 KB/s
- `liquidation`: 0 in 30s (expected — rare events)

Projected daily volume (uncompressed):
- publicTrade: ~150 MB/day
- orderbook: ~1 GB/day (worst case; book is chatty at BTCUSDT depth)
- tickers: ~130 MB/day
- liquidation: <10 MB/day
**Total: ~1.3 GB/day uncompressed, ~150–250 MB/day after gzip rotation.**

Orderbook is the large one. If the VPS disk pressure becomes real, the
options are:
1. Narrow to `orderbook.25` or `orderbook.1` (top-of-book only).
2. Downsample — emit one snapshot per second instead of every delta.
3. Skip orderbook capture entirely and rely on publicTrade + liquidation
   + tickers, which are the signals with the strongest published edge
   on Bybit specifically.

**Current decision:** capture all four at full fidelity for the first
14 days. Revisit on day 7 based on actual disk consumption.

## Phase B — Capture window (waiting)

### Minimum-data thresholds per signal

These are how much elapsed capture is required before the corresponding
backtest cell is interpretable:

| Signal | Min capture | Justification |
|---|---|---|
| CVD divergence | ~3 days (~860 5m bars) | Need ~200+ divergence events for N≥100 trades after the walk harness filters |
| Book imbalance | ~7 days | Imbalance signals have very high noise; need broad sampling across regimes |
| Taker aggression | ~3 days | Tail events (ratio≥3) are rare; need time to accumulate |
| Liquidation cascade | ~14 days | Liquidation clusters are the rarest events; may need multiple sessions with volatility |

**Recommended minimum before first serious run:** 7 days.
**Recommended minimum before final decision:** 14 days.

### Retention policy

The engine process writes only — it never deletes. Disk management is
a separate concern:

- **VPS-side cron (to be added):** `find data/bybit_capture -name '*.jsonl.gz' -mtime +30 -delete`
  keeps 30 days rolling.
- **Hot window:** last 14 days untouched.
- **Warm window (day 15-30):** gzipped only; no further processing.
- **Cold (day 31+):** deleted unless a signal from Phase C triggers
  archival of a specific window for re-analysis.
- **Uncompressed rotation lag:** at any moment, one hour per topic is
  uncompressed (the current file). Everything else is gzipped.

No retention cron is installed yet — that's a TODO when capture goes
live on the VPS. For the first 14 days the volume is small enough that
no cleanup is required.

## Phase C — Backtest harness (shipped)

### File

`tools/backtest_bybit_microstructure.py` — reads the capture dir, bins
events into 5m buckets aligned to `data/bybit_5m_6mo.csv`, enriches
each candle with microstructure fields, then walks the tape through
the existing `backtest_bybit_alt.walk()` harness with four signal
families.

### Signals implemented

1. **`cvd_div` (CVD divergence)** — bar makes new N-bar high/low but
   cumulative volume delta does not confirm. Fade the move.
2. **`liq_cascade_{min_usd}` (Liquidation cascade fade)** — trailing 3
   bars accumulate > $min_usd in long (or short) liquidation volume,
   with the liquidated side dominating by 2x. Take the opposite side
   of the forced flow. Swept at $250k / $500k / $1M thresholds.
3. **`book_imb_{thresh}` (Book imbalance)** — sustained bid/ask imbalance
   above threshold for 3 bars. Lean with the imbalance. Swept at
   20% / 30% / 40% thresholds.
4. **`taker_agg_{ratio}` (Taker aggression)** — current-bar taker buy
   count to taker sell count ratio ≥ threshold. Momentum trigger earlier
   than kline-derived streaks. Swept at 2.5 / 3.0 / 4.0.

### Graceful degradation

The script handles three degenerate cases:

- **No capture dir**: prints a not-ready notice, writes a minimal report
  pointing at `src/bybit_ws_capture.py`, exits 0.
- **Zero files**: same.
- **Short coverage window (<100 bars in overlap with CSV)**: writes a
  not-ready report with the elapsed hours, exits 0.

This means the script can be run at any time — it will self-report
"not ready yet" until there's enough data, and self-upgrade to full
results once there is.

### Runtime cost

With 7 days of capture the uncompressed inputs are ~10 GB; the walk
loop itself is O(n_candles × n_signals) ≈ ~20k operations, negligible.
The bottleneck is JSONL parsing; expect ~2-5 minutes for a 14-day run.

## Phase D — Decision gate

The script writes its report to
`docs/research/bybit_microstructure_backtest_2026-04.md`. The decision
rule is identical to every other Bybit experiment this session:

**Pass (one or more signals):**
- N ≥ 100 trades in the covered window
- WR ≥ 55%
- Net P&L positive after `_compute_pnl` round-trip fees

If any signal cell passes, it becomes the candidate for the
`bybit_acceptance_criteria.md` forward-test gate. Forward test requires
30 days of paper bets at the existing conv=3 threshold before live
consideration.

**Fail (no signal passes after ≥14 days capture):**

This is the strongest negative result we can generate on Bybit BTCUSDT
5m perps. It extends the seven-class REST negative (streak momentum,
streak fade, volatility breakout, VWAP mean-reversion, cross-venue
lead/lag, funding extreme, OI delta) with a four-class microstructure
negative (CVD divergence, liquidation cascade fade, book imbalance,
taker aggression). Eleven classes across two data tiers.

At that point the honest conclusion is:
**Bybit BTCUSDT 5m perp is not edge-extractable by retail infrastructure
on any combination of publicly available data.**

The remaining options, in rough order of increasing cost and decreasing
reusability of the existing code:

1. **Different asset, same venue (ETH, SOL perps on Bybit).** Reuses
   the entire capture + backtest harness; just change `BTCUSDT` to the
   new symbol. Cheapest next experiment if Bybit-the-venue is still in
   scope. Starts with ~1 week of fresh capture.
2. **Different cadence (1m or 4h+).** The 5m-to-1h range was tested
   exhaustively. 1m needs a new candle CSV and a recalibration of every
   signal. 4h+ reduces sample sizes to daily-strategy territory.
3. **Different venue (Hyperliquid, Deribit, Coinbase perp).** Nothing
   in the capture module transfers automatically; each venue has its
   own WS schema. 1-2 days of engineering per venue + fresh capture.
4. **Different product shape entirely.** Funding carry / basis arb is
   delta-neutral, uses the funding data we already have, and has
   published retail edge. This is a completely different code path
   from "directional bot on 5m candles" but it's the single retail-
   accessible strategy on Bybit with a defensible Sharpe in the public
   literature. Worth a separate plan if all directional efforts fail.

### Who flips the switch

Not the agent. The decision rule is mechanical: the backtest report
either has a ✅ line in the Verdict section or it doesn't. If it does,
a human reads the cell, reviews OOS halving, and decides on a
forward-test window. If it doesn't, the paper pipeline stays as is and
the project pivots to one of the four options above.

The decision does NOT fire automatically; there is no cron or bot
pulling the trigger. The criteria exist so the decision is reviewable
after the fact, not so it is made for us.

## Open tasks

- [ ] Deploy to VPS (pull + `systemctl restart botsy`). Verify the new
      supervised coroutine starts cleanly and capture files begin
      appearing under `data/bybit_capture/`.
- [ ] Day-1 check: 24h after deploy, confirm all four topic dirs have
      non-empty files and disk usage is within the ~1.5 GB/day estimate.
- [ ] Day-7 check: run the backtest for the first time. Read the
      not-ready report or preliminary numbers. Decide whether to wait
      for day-14 or to tune signal thresholds based on early data.
- [ ] Day-14 decision: run the backtest and apply Phase D gate.
- [ ] Add retention cron to the VPS once the capture path is proven.
- [ ] If any signal passes: draft a `bybit_microstructure_forward_test.md`
      plan mirroring BTC 5m's Phase 1 re-arm criteria.
- [ ] If all signals fail: open an issue on the kanban with label
      `decision,BTC-perp` proposing one of the four next options above.

## Changes this session did NOT make

- No deletion or modification of existing kline-based signals, tests,
  or pipeline logic. The capture path is additive.
- No changes to the Bybit order path, fills, or paper trading — still
  paper, still conv≥3 gated.
- No changes to the acceptance-criteria doc. That doc defines the bar
  for live re-arm; this plan defines the bar for "is there any signal
  worth forward-testing in the first place," which is a strictly
  earlier gate.
