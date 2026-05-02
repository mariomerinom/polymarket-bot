# Pipeline Integrity and Performance Review - 2026-05-02

Fresh review after `git pull --rebase --autostash` on 2026-05-02. Initial data
sources were Botsy MCP, `data/ws_metrics.json`, `config/pipelines.json`, and the
latest daily reports. No prediction logic was changed.

**Correction added 2026-05-02T13:45Z:** the initial MCP/local DB view was stale
because `data/*.db` files are intentionally untracked after the 2026-04-28 DB
bloat cleanup and must be refreshed from the VPS with `tools/sync_data.sh`.
Direct VPS checks showed live prediction DBs were fresh. Incident #94 was
closed as a local-analysis freshness issue, not a live pipeline outage.

## Executive Summary

- **Primary corrected integrity finding:** the live fleet was not stale. Direct
  VPS SQLite checks around 2026-05-02T13:15Z-13:19Z showed fresh predictions
  across BTC/ETH/perps/Kalshi. The stale MCP output came from local ignored DB
  files that had not been synced from the VPS.
- **Reporting/process finding:** MCP-backed reviews need an explicit DB sync
  step after `git pull`: `tools/sync_data.sh` or targeted `tools/sync_data.sh
  predictions.db`. GitHub is still source of truth for code/runtime JSON, but
  operational SQLite DBs now live on the VPS and sync by rsync.
- **Runtime finding:** the engine was active and dispatching. A manual fleet
  health check after the health-script fix reported `OK disk=36% botsy=active
  preds=max=4m`.
- **Performance finding:** after sync, BTC 5m remained the useful control group
  but with slightly updated numbers: 73 7d bets, 52.1% WR, +$107.80 estimated
  P&L. ETH 5m remained weak: 82 7d bets, 42.7% WR, -$117.06 estimated P&L.

## Integrity Review

| Area | Status | Evidence | Action |
|------|--------|----------|--------|
| Prediction recency | OK after sync | Direct VPS DB latest rows: `btc_5m` 2026-05-02T13:17Z, `eth_5m` 2026-05-02T13:18Z, `bybit` 2026-05-02T13:17Z, `sol_bybit` 2026-05-02T13:18Z, `kalshi` 2026-05-02T13:18Z | Do not use local MCP numbers until DBs are synced from VPS. |
| Websocket feeds | OK/noisy | Runtime JSON showed feeds connected after later pull; reconnect counts remained high | Monitor reconnect churn separately from prediction recency. |
| BTC 5m integrity log | WARN | Historical local log included stale warnings from the unsynced view plus `db_health` noise | Keep `foreign_keys=OFF` cleanup separate; do not treat the stale warnings as current outage evidence. |
| ETH 5m integrity log | WARN | 7d: `db_health` 462 WARN, `expired_would_win` 177 WARN, `orphaned_predictions` 18 WARN | Integrity noise remains high; report grouping reduces noise but root causes remain. |
| Auto-commit safety | IMPROVED | `Auto:` commits now block forbidden staged paths before commit | Watch next auto-commit cycle after source deploy. |

## Performance Review

| Pipeline | Verdict | Evidence | Interpretation |
|----------|---------|----------|----------------|
| `btc_5m` | Control, not live-ready | 73 7d bets, 38W-35L, 52.1% WR, +$107.80. 30d: 451 bets, 53.2% WR, +$886.60. | Directional signal is not dead, but edge is uneven. Continue BTC5M signal triage/shadow validation. |
| `eth_5m` | Weak | 82 7d bets, 42.7% WR, -$117.06 | ETH should not be promoted. Treat as separate signal rehab after BTC triage. |
| `bybit` | Active/positive | 65 7d bets, 56.9% WR after sync | Worth separate perp review; do not mix with BTC5M Polymarket conclusions. |
| `eth_bybit` / `eth_hl` | Active/weak | 97 7d bets each, 41.2% / 40.2% WR | Weak; defer optimization until BTC5M control triage is underway. |
| `sol_bybit` / `sol_hl` | Active/weak | 83-87 7d bets, ~39% WR | Weak; likely needs asset-relative regime work, not immediate promotion. |
| DOGE perps | Active/small sample | 4 7d bets each after sync | Sample too small for conclusion. |
| `kalshi` | Active parser validation | 12 7d bets, 100% WR after parser restart; still very small | Continue parser-versioned forward validation; old history remains contaminated. |

## Component Findings

- **Regime:** BTC 5m 30d edge is concentrated in TRENDING regimes:
  140 bets, 60.7% WR. NEUTRAL regimes are 311 bets, 49.8% WR.
- **Direction:** BTC 30d conv>=3 is modestly better DOWN than UP:
  DOWN 59/104 = 56.7%, UP 181/347 = 52.2%.
- **Conviction:** BTC 30d conv=5 is meaningfully different: 41/57 = 71.9%.
  Conv=3 and conv=4 overall are near coin-flip. The biggest weak bucket is
  conv=4 UP: 138/287 = 48.1%.
- **Skipped/low conviction:** BTC conv=0 is 1867/3563 = 52.4%, but this is
  mostly no-trade observations and should not be treated as executable edge
  without price/liquidity validation. ETH conv=0 is 2335/4465 = 52.3%.
- **Hour coverage:** both BTC and ETH have predictions but zero bets at 03:00
  and 21:00 UTC in the 30d MCP query. This is a coverage clue, not a promotion
  rule; outcome quality by hour still needs validation.

## Execution Review

- Current orders are paper. `btc_5m` has 37 7d paper-settled orders with
  +$110.56 order P&L. `eth_5m` has 16 7d paper orders, 15 settled, +$5.64
  order P&L.
- Fill diagnostics show no live fill/adverse-selection metrics for current
  paper rows. BTC: 58 records (`paper_would_fire` 37, `skipped_low_edge` 16,
  `skipped_thin_book` 5). ETH: 30 records (`paper_would_fire` 16,
  `skipped_low_edge` 10, `skipped_thin_book` 4).
- Microstructure snapshot freshness should be reviewed separately. It was not
  evidence of prediction staleness after VPS DB recency was verified.

## Recommendations

1. **Require VPS DB sync before MCP-backed analysis.** Run `tools/sync_data.sh`
   or targeted DB syncs before citing pipeline recency or WR.
2. **Keep BTC 5m as paper control.** Do not promote live; use it as the first
   signal-triage sprint lane.
3. **Track BTC5M signal-triage shadows.** Issue #95 / commit `e0823e416` now
   tags TRENDING-only, weak-hour, conv4-UP, and judge-accepted cohorts forward
   without changing behavior.
4. **Open a follow-up cleanup for `foreign_keys=OFF` integrity spam.** It is
   high-volume and obscures more urgent warnings.
5. **Investigate why Polymarket microstructure snapshots are empty.** If the
   orderbook feed is disconnected, this should resolve with #94; if not, file a
   separate capture-path bug.

## Non-Actions

- No prediction logic or hard thresholds changed in this review.
- No paper pipeline paused from this review.
- No live-capital state changed.
