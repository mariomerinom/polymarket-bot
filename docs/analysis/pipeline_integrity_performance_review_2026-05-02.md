# Pipeline Integrity and Performance Review - 2026-05-02

Fresh review after `git pull --rebase --autostash` on 2026-05-02. Data sources:
Botsy MCP, `data/ws_metrics.json`, `config/pipelines.json`, and the latest daily
reports. No prediction logic was changed.

## Executive Summary

- **Primary integrity finding:** the fleet is stale. `btc_5m` last predicted at
  2026-05-01T12:50:30Z, while the review was run at 2026-05-02T12:56Z.
  `btc_5m` integrity logs confirm `system_state_health` warnings: "STALE: last
  prediction was 1438m ago." Opened incident:
  https://github.com/mariomerinom/polymarket-bot/issues/94
- **Runtime finding:** all websocket feeds are reported disconnected in
  `data/ws_metrics.json`: `bybit_spot`, `bybit_linear`, and `polymarket`.
  Reconnects over 24h are 133, 174, and 139 respectively. Dispatch latency is
  high: p50 50.5s, p95 146.4s.
- **Performance finding:** `btc_5m` remains the only useful control group:
  65 7d bets, 52.3% WR, +$136.90 estimated P&L. `eth_5m` is weak:
  48 7d bets, 43.8% WR, -$129.91 estimated P&L, and 0% judge coverage.
- **Do not infer current edge from stale perps/SOL/DOGE.** Most perp/alt
  pipelines last predicted on 2026-04-28 and have too little fresh 7d activity.

## Integrity Review

| Area | Status | Evidence | Action |
|------|--------|----------|--------|
| Prediction recency | FAIL | `btc_5m` stale ~24h; ETH stale since 2026-04-30; most perps stale since 2026-04-28 | Incident #94 opened. Inspect VPS service/websocket dispatch before signal work. |
| Websocket feeds | FAIL | all three feeds disconnected; reconnects_24h 133/174/139 | Check service logs and reconnect loop. Confirm confirmed candle-close events reach dispatch. |
| BTC 5m integrity log | WARN/FAIL | 7d: `db_health` 626 WARN, `expired_would_win` 167 WARN, `system_state_health` 28 WARN, `api_health` 8 FAIL, `orphaned_predictions` 7 WARN | Treat stale/API failures as incident. `db_health` foreign-key warnings need separate cleanup. |
| ETH 5m integrity log | WARN | 7d: `db_health` 462 WARN, `expired_would_win` 177 WARN, `orphaned_predictions` 18 WARN | Integrity noise remains high; report grouping reduces noise but root causes remain. |
| Auto-commit safety | IMPROVED | `Auto:` commits now block forbidden staged paths before commit | Watch next auto-commit cycle after source deploy. |

## Performance Review

| Pipeline | Verdict | Evidence | Interpretation |
|----------|---------|----------|----------------|
| `btc_5m` | Control, not live-ready | 65 7d bets, 34W-31L, 52.3% WR, +$136.90. Judge-accepted subset: 10 bets, 70.0% WR, +$111.64. | Directional signal is not dead, but runtime staleness blocks conclusions. Judge subset deserves forward monitoring, not promotion. |
| `eth_5m` | Weak | 48 7d bets, 43.8% WR, -$129.91. Current streak: 2 losses. Judge coverage: 0%. | ETH should not be promoted. First fix judge coverage/data freshness, then revisit. |
| `bybit` | Stale/low sample | 1 7d bet, 100% WR; last prediction 2026-04-28T23:15Z | Ignore WR. Runtime recency first. |
| `eth_bybit` / `eth_hl` | Stale/low sample | 4 7d bets each, 50% WR; last prediction 2026-04-28T23:15Z | Not enough current data. |
| `sol_bybit` / `sol_hl` | Stale/no fresh bets | 0 7d bets; last prediction 2026-04-28T23:15Z | Treat May 1 loss snapshot as historical, not current live signal. |
| DOGE perps | Stale/no fresh bets | 0 7d bets; last prediction 2026-04-28T23:15Z | Monitor only after runtime recovers. |
| `kalshi` | Stale experiment | last prediction 2026-04-17T14:30Z | Historical parser-contaminated data remains excluded from edge claims. |

## Component Findings

- **Regime:** BTC 5m 7d edge is concentrated in `MEDIUM_VOL / TRENDING`:
  30 bets, 66.7% WR. BTC `MEDIUM_VOL / NEUTRAL` is poor: 34 bets, 41.2% WR.
  ETH does not share the same pattern: `MEDIUM_VOL / TRENDING` is 1/4 over 7d.
- **Direction:** BTC 30d conv>=3 is slightly better DOWN than UP:
  DOWN 58/103 = 56.3%, UP 178/340 = 52.4%. ETH is roughly flat:
  DOWN 160/314 = 51.0%, UP 175/336 = 52.1%.
- **Conviction:** BTC 30d conv=5 is strong but small: 40/55 = 72.7%.
  BTC conv=2 is weak: 178/376 = 47.3%. ETH conv=2 is also weak:
  183/376 = 48.7%.
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
- `polymarket_microstructure_summary(days=1)` returns 0 snapshots. The capture
  path should be checked as part of incident #94 because it may be another
  symptom of the disconnected feed/runtime recency issue.

## Recommendations

1. **Resolve incident #94 before any signal changes.** A stale engine makes all
   performance review second-order. Confirm websocket reconnect, candle close
   dispatch, and prediction writes.
2. **Keep BTC 5m as paper control.** Do not promote live; use it as the only
   current signal yardstick once recency is restored.
3. **Do not act on ETH/perp/SOL performance until freshness returns.** ETH is
   weak, but stale/partial data and missing judge coverage mean the immediate
   action is instrumentation repair, not a new filter.
4. **Open a follow-up cleanup for `foreign_keys=OFF` integrity spam.** It is
   high-volume and obscures more urgent warnings.
5. **Investigate why Polymarket microstructure snapshots are empty.** If the
   orderbook feed is disconnected, this should resolve with #94; if not, file a
   separate capture-path bug.

## Non-Actions

- No prediction logic or hard thresholds changed.
- No paper pipeline paused from this review.
- No live-capital state changed.
