# Multi-Asset Expansion Plan

Last updated: 2026-04-09

---

## Context

Our BTC 5m pipeline runs at 67% WR on 227+ bets. Polymarket offers **5m and 15m "Up or Down" markets for 7+ crypto assets**.

| Asset | 5m Title Format | Kraken Pair | Coinbase |
|-------|----------------|-------------|----------|
| **Bitcoin** | `Bitcoin Up or Down - March 29, 8:20AM-8:25AM ET` | `XBTUSD` | `BTC-USD` |
| **Ethereum** | `Ethereum Up or Down - March 29, 9:00AM-9:05AM ET` | `XETHZUSD` | `ETH-USD` |
| **Solana** | `Solana Up or Down - March 29, 8:20AM-8:25AM ET` | `SOLUSD` | `SOL-USD` |
| XRP | `XRP Up or Down - ...` | `XRPUSD` | `XRP-USD` |
| Dogecoin | `Dogecoin Up or Down - ...` | `XDGUSD` | `DOGE-USD` |

Kalshi also offers similar 5m/15m crypto markets. Combined daily volume across platforms is ~$70M.

---

## Current State

### Deployed Pipelines

| Pipeline | Signal | Status | Notes |
|----------|--------|--------|-------|
| BTC 5m | Momentum | Paper (reverted from live) | 484 bets, 63.4% WR. HIGH_VOL gate added 2026-04-09. |
| BTC 15m | Momentum | Paper | 106 bets, 59.4% WR. `loose_mode=True`. |
| ETH 5m | Momentum | Paper (Phase 2 conditional GO) | 267 bets, 57.7% WR. HIGH_VOL gate added 2026-04-09. |
| Bybit BTC | Momentum | Paper (rehabilitated 2026-04-09) | 319 bets at 50.5% pre-fix. Conviction filters + dead hours added. |
| Kalshi BTC | Momentum | Paper (resolution fixed 2026-04-09) | Mock hash resolver replaced with real candle-based resolution. |

### ETH Lessons Learned

ETH was originally deployed as contrarian (fade streaks) based on pattern mining validation (54.4% WR on 1,601 historical markets). Live results told a different story:

| Strategy | 54 live predictions | WR |
|----------|--------------------|----|
| Contrarian (was live) | fade the streak | **33.3%** |
| Momentum (counterfactual) | ride the streak | **66.7%** |

Pattern mining results did not transfer to live trading. The contrarian signal was exactly inverted — same V3→V4 pattern as BTC. **Both assets now use momentum.**

---

## Architecture

Each asset gets its own isolated pipeline:

```
Coinbase (ETH-USD) ──> eth_data.py ──> predict_eth.py ──> predictions_eth.db
                                             ^                    |
                                      fetch_markets.py      dashboard.py
                                   ("Ethereum Up or Down")    score.py
```

**Isolation rules:**
- Separate databases per asset
- Separate CI workflows per asset
- Separate dashboards per asset (cross-linked via nav bar)
- Asset pipeline changes must never affect other pipelines
- BTC 5m frozen files remain frozen

---

## ETH Phased Rollout

See `docs/pipelines/eth_pipeline_acceptance_criteria.md` for full details.

### Phase 1 — Momentum Signal Validation (ACTIVE)
- Momentum signal deployed 2026-04-01
- All predictions at conv=2 (paper)
- Gate: 50 resolved predictions. Pass: WR > 55%. Fail: WR < 45%.

### Phase 2 — ETH Adaptation Layer (after Phase 1 validates)
- Recalibrate volatility regime thresholds for ETH (currently 93% land in HIGH_VOL with BTC thresholds)
- Add ETH/BTC cross-asset features (correlation, lag detection, relative strength)
- ETH-specific conviction scoring and sizing
- 50 shadow bets with adaptation features before enabling live

### Phase 3 — Full Integration (after Phase 2 validates)
- Expand conviction range (conv 4-5)
- ETH-specific dead hours (calibrated from ETH data, not copied from BTC)
- Independent circuit breaker ($150 max drawdown at conv=3 sizing)

---

## SOL Pipeline (DEFERRED)

- Phase 2 pattern mining showed contrarian_exhaust_s3 at 53.8% on 186 bets — weaker signal, smaller sample
- Given ETH contrarian's live failure (33.3% WR), pattern mining results alone are insufficient justification
- SOL deployment blocked until:
  1. ETH Phase 1 validates (momentum works on a second asset)
  2. SOL-specific live data justifies signal direction choice

---

## Future Assets (DEFERRED)

XRP, DOGE, and others are available on Polymarket. Not prioritized until:
1. ETH pipeline is profitable live
2. Generic asset framework is mature enough that adding an asset is config-only

---

## BTC 5m Pipeline Is Frozen

New assets get **new files**. BTC files don't get touched.

| BTC file | Status |
|----------|--------|
| `src/ci_run.py` | FROZEN |
| `src/btc_data.py` | FROZEN |
| `src/predict.py` | FROZEN |
| `src/score.py` | FROZEN |
| `src/clob_depth.py` | FROZEN |
| `.github/workflows/predict-and-score.yml` | FROZEN |
| `data/predictions.db` | FROZEN |
