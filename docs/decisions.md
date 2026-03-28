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

---

## Action Log

| Date | Decision # | Action | Result |
|------|-----------|--------|--------|
| — | — | — | — |
