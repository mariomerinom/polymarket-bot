# Decision Tracker

Pending optimization decisions with automated triggers. The daily report checks these conditions and alerts when a decision becomes READY.

Status flow: `MONITORING` → `READY` → `ACTIONED` or `DEFERRED`

Source: [Pipeline Recommendations Mar 25–27](daily/pipeline_recommendations_mar25-27.md)

---

| # | Decision | Trigger | Pipeline | Status | Notes |
|---|----------|---------|----------|--------|-------|
| 1 | Demote conv=4 to flat $75 | conv=4 WR < 60% at 50+ resolved bets | 5m | SUPERSEDED | Superseded by #14 — production uses flat $25. Paper tiers remain for data collection. |
| 2 | Tighten 0.50-0.70 price bucket | 0.50-0.70 WR < 55% over 7-day rolling window | 5m | MONITORING | WR declining: 75% → 52% → 56%. Highest-volume bucket but worst returns |
| 3 | Add regime-aware sizing | 3+ consecutive NEUTRAL-majority days with WR < 58% | 5m | MONITORING | Model performs best aligned with BTC macro trend; weakest in range-bound |
| 4 | Filter 15m RIDE UP signals | 15m UP WR < 55% at 30+ resolved bets | 15m | MONITORING | DOWN 83% WR (+$124), UP 57% WR (-$90). Model may only have edge on short side at 15m |
| 5 | Sunset or retrain 15m pipeline | 15m avg < 5 bets/day over 14+ days AND ROI < 5% | 15m | MONITORING | Only 12 bets in 3 days, $33 total P&L. Not contributing meaningfully |
| 6 | Explore 0.15-0.30 bucket expansion | 0.15-0.30 WR > 65% at 20+ resolved bets | 5m | MONITORING | Small sample (5 bets, 80% WR). Edge looks real but volume minimal |
| 7 | Demote conv=4 to flat $75 (15m) | conv=4 WR < 60% at 20+ resolved bets | 15m | SUPERSEDED | Superseded by #14 — production uses flat $25. |
| 8 | Filter DOWN in NEUTRAL regimes | Immediate — data shows 52% WR on 25 bets | 5m | ACTIONED | DOWN+NEUTRAL demoted to conv=2 (tracked, no money). UP+NEUTRAL untouched (86.7% WR) |
| 9 | Time-of-day gate: skip dead hours | Immediate — 3 UTC (41.7%) and 21 UTC (37.5%) | 5m+15m | ACTIONED | DEAD_HOURS_UTC = {3, 21}. Predictions stored as skip with reason |
| 10 | Review conv=5 ($300) sizing | After 20+ conv=5 bets: if WR < 65% or max drawdown > $900 | 5m | SUPERSEDED | Superseded by #14 — production uses flat $25 regardless of conviction tier. |
| 11 | Add ATR/volatility filter | After 100+ regime-tagged bets: compare HIGH_VOL WR vs overall | 5m | MONITORING | Peer review: very high vol periods may amplify losses. Check if HIGH_VOL regime underperforms. |
| 12 | Audit candle-to-resolution timing | Before Part 6 (live trading) | 5m | MONITORING | Peer review: timing drift between candle fetch and Polymarket resolution could hurt. |
| 13 | Surface Brier score in daily report | Next daily report iteration | 5m+15m | MONITORING | Peer review: WR alone hides calibration problems. Brier is computed but not prominently surfaced. |
| 14 | Production sizing: flat grind | Before live trading launch | All | ACTIONED | Flat $25/bet in production. Paper tiers stay for data collection. Kelly only after bankroll grows from profits. Deployed 2026-03-31. |
| 15 | ETH model: validate momentum signal | ETH momentum WR > 55% at 50+ resolved predictions | ETH | ACTIONED | 66.7% WR on 36 resolved momentum predictions (threshold 55%). Medium confidence (streak 3-4) promoted to conv=3 ($25 bets). High confidence (streak ≥ 5) stays conv=2 (20% WR on 5 bets). |
| 16 | Recalibrate ETH regime thresholds | ETH HIGH_VOL predictions > 80% of total for 7+ days | ETH | MONITORING | 93% of ETH predictions land in HIGH_VOL — BTC thresholds don't fit ETH's higher baseline vol. Blocked on Phase 1 validation. |
| 17 | Validate paper-to-live degradation thesis | 50 live bets completed | 5m | MONITORING | Thesis: docs/daily/thesis_paper_to_live_degradation.md. Expected -5 to -9pp WR drop from paper. Revert if live WR < 55% at 50 bets or < 50% at 30 bets. |
| 18 | ETH momentum Phase 1 gate | 50 resolved ETH momentum predictions | ETH | ACTIONED | 36 resolved at 66.7% WR (well above 55% pass threshold). Medium confidence promoted to conv=3. Gate passed early — WR 12pp above threshold made waiting for 50 unnecessary. Optimization tracker registered with revert at WR < 55% on 50 post-change bets. |

---

## Action Log

| Date | Decision # | Action | Result |
|------|-----------|--------|--------|
| 2026-03-28 | #8 | DOWN+NEUTRAL → conv=2 in store_prediction() | Filters ~13% of bets (25/193), saves ~$200 in coin-flip losses |
| 2026-03-28 | #9 | DEAD_HOURS_UTC gate in run_predictions() | Filters ~10% of bets (20/193), saves ~$150 from 40% WR hours |
| 2026-03-29 | #10-13 | Registered 4 decisions from external peer review | Edge decay, sizing risk, timing audit, calibration surfacing |
| 2026-03-31 | #14 | Flat $25 production sizing deployed in trade.py | Live trading started. Paper tiers continue for data collection. |
| 2026-04-01 | #15 | ETH flipped from contrarian to momentum | Contrarian: 33.3% WR on 54 bets. Momentum counterfactual: 66.7%. Same V3→V4 pattern as BTC. |
| 2026-04-01 | #1,7,10 | Marked SUPERSEDED by #14 | Tiered sizing decisions no longer applicable — production uses flat $25. |
| 2026-04-01 | #18 | Added ETH momentum Phase 1 validation gate | 50 resolved predictions needed before Phase 2 adaptation layer. |
| 2026-04-02 | #15,18 | ETH momentum Phase 1 validated, conv=3 enabled | 36 resolved at 66.7% WR. Medium confidence (streak 3-4) → conv=3 ($25). High confidence (streak ≥ 5) → conv=2 (paper). Revert gate: WR < 55% at 50 post-change bets. |
