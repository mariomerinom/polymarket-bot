# Decision Tracker

Pending optimization decisions with automated triggers. The daily report checks these conditions and alerts when a decision becomes READY.

Status flow: `MONITORING` → `READY` → `ACTIONED` or `DEFERRED`

Source: [Pipeline Recommendations Mar 25–27](daily/pipeline_recommendations_mar25-27.md)

---

| # | Decision | Trigger | Pipeline | Status | Notes |
|---|----------|---------|----------|--------|-------|
| 1 | Demote conv=4 to flat $75 | conv=4 WR < 60% at 50+ resolved bets | 5m | MONITORING | conv=3 profitable every day ($2,551); conv=4 lost $60 at 50% WR on only active day |
| 2 | Tighten 0.50-0.70 price bucket | 0.50-0.70 WR < 55% over 7-day rolling window | 5m | MONITORING | WR declining: 75% → 52% → 56%. Highest-volume bucket but worst returns |
| 3 | Add regime-aware sizing | 3+ consecutive NEUTRAL-majority days with WR < 58% | 5m | MONITORING | Model performs best aligned with BTC macro trend; weakest in range-bound |
| 4 | Filter 15m RIDE UP signals | 15m UP WR < 55% at 30+ resolved bets | 15m | MONITORING | DOWN 83% WR (+$124), UP 57% WR (-$90). Model may only have edge on short side at 15m |
| 5 | Sunset or retrain 15m pipeline | 15m avg < 5 bets/day over 14+ days AND ROI < 5% | 15m | MONITORING | Only 12 bets in 3 days, $33 total P&L. Not contributing meaningfully |
| 6 | Explore 0.15-0.30 bucket expansion | 0.15-0.30 WR > 65% at 20+ resolved bets | 5m | MONITORING | Small sample (5 bets, 80% WR). Edge looks real but volume minimal |
| 7 | Demote conv=4 to flat $75 (15m) | conv=4 WR < 60% at 20+ resolved bets | 15m | MONITORING | Same inversion as 5m: conv=3 at 75% WR, conv=4 at 50% WR |
| 8 | Filter DOWN in NEUTRAL regimes | Immediate — data shows 52% WR on 25 bets | 5m | ACTIONED | DOWN+NEUTRAL demoted to conv=2 (tracked, no money). UP+NEUTRAL untouched (86.7% WR) |
| 9 | Time-of-day gate: skip dead hours | Immediate — 3 UTC (41.7%) and 21 UTC (37.5%) | 5m+15m | ACTIONED | DEAD_HOURS_UTC = {3, 21}. Predictions stored as skip with reason |
| 10 | Review conv=5 ($300) sizing | After 20+ conv=5 bets: if WR < 65% or max drawdown > $900 | 5m | MONITORING | Peer review flagged $300 as aggressive. 5-loss streak = -$1,500. Consider capping at $200 until live execution data exists. Source: external review 2026-03-29 |
| 11 | Add ATR/volatility filter | After 100+ regime-tagged bets: compare HIGH_VOL WR vs overall | 5m | MONITORING | Peer review: very high vol periods may amplify losses. Check if HIGH_VOL regime underperforms. |
| 12 | Audit candle-to-resolution timing | Before Part 6 (live trading) | 5m | MONITORING | Peer review: timing drift between candle fetch and Polymarket resolution could hurt. Need to verify CI execution happens early enough in the 5-min window, not at the boundary. |
| 13 | Surface Brier score in daily report | Next daily report iteration | 5m+15m | MONITORING | Peer review: WR alone hides calibration problems. Brier is computed (score.py) but not prominently surfaced in reports. |
| 14 | Production sizing: flat grind, not tiered | Before live trading launch | 5m+15m+ETH | READY | Concentration risk: last 50 bets avg $215 (35 at $200, 8 at $300) vs early $75 flat. Production launches with flat small bets (e.g. $25). Kelly only after bankroll builds from profits. Thin book caps max size via CLOB depth. Paper tiers stay for data collection. |
| 15 | ETH model: deploy adapted model | ETH shadow WR > 55% at 50+ shadow-logged predictions with RSI/OBV/VWAP | ETH | MONITORING | Spec: docs/daily/spec_eth_model_training.md. Option B (adaptation layer) first. Regime recalibration + correlation features + ETH conviction scorer. Do not deploy live ETH bets until shadow clears 50 bets > 55% WR. ETH sizing codified: $25/$50/$75 by conviction, capped at 50% of CLOB max@2%. |
| 16 | Recalibrate ETH regime thresholds | ETH HIGH_VOL predictions > 80% of total for 7+ days | ETH | MONITORING | 93% of ETH predictions land in HIGH_VOL — BTC thresholds don't fit ETH's higher baseline vol. Proposed shift: LOW 0→1.2, MEDIUM 1.2→2.2, HIGH 2.2+. Blocked on: 50+ shadow predictions for before/after comparison. |
| 17 | Validate paper-to-live degradation thesis | 50 live bets completed | 5m | MONITORING | Thesis: docs/daily/thesis_paper_to_live_degradation.md. Expected -5 to -9pp WR drop from paper. Revert if live WR < 55% at 50 bets or < 50% at 30 bets. |

---

## Action Log

| Date | Decision # | Action | Result |
|------|-----------|--------|--------|
| 2026-03-28 | #8 | DOWN+NEUTRAL → conv=2 in store_prediction() | Filters ~13% of bets (25/193), saves ~$200 in coin-flip losses |
| 2026-03-28 | #9 | DEAD_HOURS_UTC gate in run_predictions() | Filters ~10% of bets (20/193), saves ~$150 from 40% WR hours |
| 2026-03-29 | #10-13 | Registered 4 decisions from external peer review | Edge decay, sizing risk, timing audit, calibration surfacing |
