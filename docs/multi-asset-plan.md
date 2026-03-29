# Multi-Asset Expansion Plan (SOL & ETH)

Last updated: 2026-03-29

---

## Context

Our BTC 5m pipeline runs at 67% WR on 217+ bets. The architecture is fully BTC-hardcoded across 7 files. Polymarket now offers **5m and 15m "Up or Down" markets for 7+ crypto assets** — confirmed via Gamma API:

| Asset | 5m Title Format | 15m? | Kraken Pair | Coinbase |
|-------|----------------|------|-------------|----------|
| **Bitcoin** | `Bitcoin Up or Down - March 29, 8:20AM-8:25AM ET` | Yes | `XBTUSD` | `BTC-USD` |
| **Solana** | `Solana Up or Down - March 29, 8:20AM-8:25AM ET` | Yes | `SOLUSD` | `SOL-USD` |
| **Ethereum** | `Ethereum Up or Down - March 29, 9:00AM-9:05AM ET` | Yes | `XETHZUSD` | `ETH-USD` |
| XRP | `XRP Up or Down - ...` | Yes | `XRPUSD` | `XRP-USD` |
| Dogecoin | `Dogecoin Up or Down - ...` | Yes | `XDGUSD` | `DOGE-USD` |
| BNB | `BNB Up or Down - ...` | Yes | — | — |
| Hyperliquid | `Hyperliquid Up or Down - ...` | ? | — | — |

Kalshi also offers similar 5m/15m crypto markets. Drift BET (Solana-native) is another venue. Combined daily volume across platforms is ~$70M.

## Goals

1. Refactor BTC-specific code into asset-generic framework
2. Deploy SOL and ETH pipelines (paper trading, `loose_mode=True`)
3. Make adding any new asset a config change, not a code change
4. Follow validation principles: new assets start loose, 200+ predictions before tuning

---

## Current Architecture (BTC-only)

```
Kraken (XBTUSD) ──> btc_data.py ──> predict.py ──> predictions.db
Coinbase (BTC-USD) ─┘                    ^                |
                              fetch_markets.py      dashboard.py
                           ("Bitcoin Up or Down")    score.py
```

**BTC hardcoding in 7 files:**
- `src/btc_data.py` — Kraken pair `XBTUSD`, Coinbase URL `BTC-USD`, prompt text "BTC"
- `src/fetch_markets.py` — Title filter `"Bitcoin Up or Down"` (line 171)
- `src/predict.py` — `from btc_data import fetch_btc_candles` (line 339), dead hours (BTC-calibrated)
- `src/ci_run.py` / `ci_run_15m.py` — Call `fetch_btc_candles()` directly
- `src/daily_report.py` — Hardcoded DB paths for BTC 5m/15m only
- `src/dashboard.py` — Single-asset DB path

**Already asset-agnostic (no changes needed):**
- Signal logic: `momentum_signal()`, `detect_regime()` — work on any candle data
- Conviction scoring structure — parameterized by thresholds
- DB schema — `markets` and `predictions` tables have no asset-specific columns
- Scoring logic — `score.py` is pure math
- Dashboard rendering — accepts any `db_path`

---

## Phase 0: Refactor to Asset-Generic (no behavior change)

### 0.1 Create `src/asset_config.py` — central asset registry

Single source of truth for all asset-specific parameters:

```python
ASSETS = {
    "BTC": {
        "kraken_pair": "XBTUSD",
        "coinbase_product": "BTC-USD",
        "polymarket_title": "Bitcoin Up or Down",
        "label": "Bitcoin",
        "db_5m": "data/predictions.db",
        "db_15m": "data/predictions_15m.db",
        "dashboard_5m": "docs/index.html",
        "dashboard_15m": "docs/15m.html",
        "min_streak_5m": 3,
        "min_streak_15m": 2,
        "autocorr_5m": -0.15,
        "autocorr_15m": -0.20,
        "dead_hours_utc": {3, 21},
        "loose_mode": False,
    },
    "SOL": {
        "kraken_pair": "SOLUSD",
        "coinbase_product": "SOL-USD",
        "polymarket_title": "Solana Up or Down",
        "label": "Solana",
        "db_5m": "data/predictions_sol_5m.db",
        "db_15m": "data/predictions_sol_15m.db",
        "dashboard_5m": "docs/sol-5m.html",
        "dashboard_15m": "docs/sol-15m.html",
        "min_streak_5m": 3,
        "min_streak_15m": 2,
        "autocorr_5m": -0.15,
        "autocorr_15m": -0.20,
        "dead_hours_utc": set(),
        "loose_mode": True,
    },
    "ETH": {
        "kraken_pair": "XETHZUSD",
        "coinbase_product": "ETH-USD",
        "polymarket_title": "Ethereum Up or Down",
        "label": "Ethereum",
        "db_5m": "data/predictions_eth_5m.db",
        "db_15m": "data/predictions_eth_15m.db",
        "dashboard_5m": "docs/eth-5m.html",
        "dashboard_15m": "docs/eth-15m.html",
        "min_streak_5m": 3,
        "min_streak_15m": 2,
        "autocorr_5m": -0.15,
        "autocorr_15m": -0.20,
        "dead_hours_utc": set(),
        "loose_mode": True,
    },
}
```

### 0.2 Create `src/candle_data.py` — asset-generic candle fetcher

Extract from `btc_data.py`:
- `fetch_candles(asset="BTC", interval="5m", limit=12)` replaces `fetch_btc_candles()`
- `_fetch_kraken(limit, interval_minutes, pair)` — parameterize pair
- `_fetch_coinbase(limit, interval_minutes, product)` — parameterize URL
- `format_for_prompt(data, asset="BTC")` — parameterize header text
- `_compute_summary()` and `_compute_consensus()` — zero changes (already generic)

`btc_data.py` becomes a thin backward-compat shim.

### 0.3 Parameterize `src/fetch_markets.py`

Add `fetch_active_markets_asset(asset, timeframe)` that takes the title pattern from config instead of hardcoded `"Bitcoin Up or Down"`. Keep existing functions as shims.

### 0.4 Parameterize `src/predict.py` import

Line 339: `from btc_data import fetch_btc_candles` becomes `from candle_data import fetch_candles`. Since CI runners always pass candle data explicitly, this only affects manual invocation.

### 0.5 Create `src/ci_run_asset.py` — generic pipeline runner

```python
def run_asset_pipeline(asset, timeframe):
    config = ASSETS[asset]
    candles = fetch_candles(asset=asset, interval=timeframe, limit=20)
    markets = fetch_active_markets_asset(asset, timeframe)
    run_predictions(
        btc_data=candles,
        db_path=config[f"db_{timeframe}"],
        min_streak=config[f"min_streak_{timeframe}"],
        autocorr_threshold=config[f"autocorr_{timeframe}"],
        loose_mode=config["loose_mode"],
    )
```

### 0.6 Tests

- `tests/test_candle_data.py` — verify SOL/ETH pair URL construction
- `tests/test_asset_config.py` — verify all assets have required keys
- Existing tests pass unchanged via backward-compat shims

---

## Phase 1: Deploy SOL Pipeline (immediately after Phase 0)

Markets are live. Deploy as soon as refactoring is done.

1. Create CI workflows: `predict-sol-5m.yml`, `predict-sol-15m.yml`
2. Create entry points: `ci_run_sol_5m.py`, `ci_run_sol_15m.py`
3. Both start in `loose_mode=True` — paper trading, all gates disabled
4. Expand daily report with SOL sections
5. Snapshot BTC baseline before deployment
6. Register optimizations: `sol_5m_paper_trade`, `sol_15m_paper_trade`

## Phase 2: Deploy ETH Pipeline (after SOL reaches 50+ bets)

Same as Phase 1, staggered. One asset at a time per validation principles.

## Phase 3: Asset-Specific Tuning (after 200+ predictions per asset)

1. Analyze per-asset dead hours, regime splits, streak sweet spots
2. Tune thresholds one at a time, tracked as separate optimizations
3. Migrate from `loose_mode=True` to calibrated gates
4. Each change gets its own 50-bet validation window

## Phase 4: Cross-Asset Signals (optional, after Phase 3)

Explore whether BTC momentum is a leading indicator for SOL/ETH (like the 5m-to-15m sibling context). Only after individual pipelines are validated.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| SOL/ETH momentum doesn't exist | `loose_mode=True` paper trading. 200+ predictions before tuning. Revert if WR < 50% at 100 bets. |
| BTC thresholds wrong for altcoins | Start with no gates (loose_mode), let data reveal asset-specific patterns. |
| CI resource limits (6 pipelines) | Each workflow has its own concurrency group. ~1,152 dispatches/day total (within GitHub limits). |
| Git conflicts from 6 pipelines committing | Each pipeline commits only its own DB + dashboard. Existing `git pull --rebase` handles it. |
| Kraken pair name variants | Code already handles Kraken's variable key names (btc_data.py lines 79-82). Verify SOL/ETH on first run. |
| SOL/ETH lower Polymarket liquidity | Monitor volume in daily report. Low volume = wider spreads = worse execution when live. |

---

## File Change Summary

| File | Action | Phase |
|------|--------|-------|
| `src/asset_config.py` | NEW — central asset registry | 0 |
| `src/candle_data.py` | NEW — asset-generic candle fetcher | 0 |
| `src/btc_data.py` | MODIFY — backward-compat shim | 0 |
| `src/fetch_markets.py` | MODIFY — parameterize title filter | 0 |
| `src/predict.py` | MODIFY — 2 lines (import path) | 0 |
| `src/ci_run_asset.py` | NEW — generic pipeline runner | 0 |
| `src/daily_report.py` | MODIFY — multi-asset sections | 0 |
| `tests/test_candle_data.py` | NEW | 0 |
| `tests/test_asset_config.py` | NEW | 0 |
| `src/ci_run_sol_5m.py` | NEW | 1 |
| `src/ci_run_sol_15m.py` | NEW | 1 |
| `.github/workflows/predict-sol-5m.yml` | NEW | 1 |
| `.github/workflows/predict-sol-15m.yml` | NEW | 1 |
| `src/ci_run_eth_5m.py` | NEW | 2 |
| `src/ci_run_eth_15m.py` | NEW | 2 |
| `.github/workflows/predict-eth-5m.yml` | NEW | 2 |
| `.github/workflows/predict-eth-15m.yml` | NEW | 2 |
