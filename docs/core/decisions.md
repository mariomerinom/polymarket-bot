# Decision Tracker

Pending optimization decisions with automated triggers. The daily report checks these conditions and alerts when a decision becomes READY.

Status flow: `MONITORING` → `READY` → `ACTIONED` or `DEFERRED`

Source: [Pipeline Recommendations Mar 25–27](../analysis/pipeline_recommendations_mar25-27.md)

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
| 9 | Time-of-day gate: skip dead hours | Immediate — 3 UTC (41.7%) and 21 UTC (37.5%) | 5m+15m | ACTIONED | Originally hardcoded {3, 21}. Now data-driven: compute_dead_hours() queries last 90 days, gates hours with WR < 50% on 30+ bets. Fallback {3, 21} preserved until data rehabilitates them. ETH uses same function against its own DB. |
| 10 | Review conv=5 ($300) sizing | After 20+ conv=5 bets: if WR < 65% or max drawdown > $900 | 5m | SUPERSEDED | Superseded by #14 — production uses flat $25 regardless of conviction tier. |
| 11 | Add ATR/volatility filter | After 100+ regime-tagged bets: compare HIGH_VOL WR vs overall | 5m | MONITORING | Peer review: very high vol periods may amplify losses. Check if HIGH_VOL regime underperforms. |
| 12 | Audit candle-to-resolution timing | Before Part 6 (live trading) | 5m | MONITORING | Peer review: timing drift between candle fetch and Polymarket resolution could hurt. |
| 13 | Surface Brier score in daily report | Next daily report iteration | 5m+15m | MONITORING | Peer review: WR alone hides calibration problems. Brier is computed but not prominently surfaced. |
| 14 | Production sizing: flat grind | Before live trading launch | All | ACTIONED | Flat $25/bet in production. Paper tiers stay for data collection. Kelly only after bankroll grows from profits. Deployed 2026-03-31. |
| 15 | ETH model: validate momentum signal | ETH momentum WR > 55% at 50+ resolved predictions | ETH | ACTIONED | 66.7% WR on 36 resolved momentum predictions (threshold 55%). Medium confidence (streak 3-4) promoted to conv=3 ($25 bets). High confidence (streak ≥ 5) stays conv=2 (20% WR on 5 bets). |
| 16 | Recalibrate ETH regime thresholds | ETH HIGH_VOL predictions > 80% of total for 7+ days | ETH | ACTIONED | Was 83% HIGH_VOL with BTC thresholds (LOW<0.05, HIGH≥0.12). Recalibrated: LOW<0.10, HIGH≥0.20. Expected ~31/46/22% split. Revert if ETH WR drops below 55% on 50+ post-change bets. |
| 17 | Validate paper-to-live degradation thesis | 50 live bets completed | 5m | MONITORING | Thesis: docs/analysis/thesis_paper_to_live_degradation.md. Expected -5 to -9pp WR drop from paper. Revert if live WR < 55% at 50 bets or < 50% at 30 bets. |
| 18 | ETH momentum Phase 1 gate | 50 resolved ETH momentum predictions | ETH | ACTIONED | 36 resolved at 66.7% WR (well above 55% pass threshold). Medium confidence promoted to conv=3. Gate passed early — WR 12pp above threshold made waiting for 50 unnecessary. Optimization tracker registered with revert at WR < 55% on 50 post-change bets. |
| 19 | Time-of-day gate: monitor hour 16 UTC | Hour 16 WR < 50% at 30+ bets | 5m | MONITORING | 10 bets, 40% WR at hour 16. Below 30-bet threshold. Now auto-gated by compute_dead_hours() — will be added automatically when threshold is reached. No manual intervention needed. |
| 20 | Demote 15m conv=4 to conv=3 | 15m conv=4 WR < 60% at 30+ resolved bets | 15m | REVERTED | Implemented 2026-04-02, reverted 2026-04-03. Cap demoted conv>3→3 in ci_run_15m.py. Conv=3 WR collapsed from 75%→33%→22% over 3 days (2W-7L on 2026-04-03). Cap removed natural quality filter without improving accuracy. Conv=4 at 61% (28 bets) was functioning — 59.3% trigger was noise at 27 bets. |
| 21 | Dynamic estimates replace hardcoded 0.62/0.38 | Immediate — fundamental calibration fix | All | ACTIONED | Estimates now computed from streak length + price magnitude + volatility via strength_signal(). BTC: 0.50-0.64 range (max_edge=0.14). ETH: 0.50-0.60 (max_edge=0.10). Edge gate in trade.py now functional. Revert if WR < 55% on 50 post-change bets. |
| 22 | Unify confidence from scorer | After 50 dynamic-estimate bets resolve | ETH | MONITORING | momentum_signal uses abs(streak)>=5 for "high" confidence, shadow scorer uses strength>=0.80. They can disagree (streak=4 + big magnitude = high strength but medium confidence). Matters for ETH where high→conv=2 (no bet). Harmless for BTC. Revisit after dynamic estimates prove out. |
| 23 | VWAP mean-reversion promotion | Shadow: 50 bets at >58% WR | 5m | **REVERTED** | Promoted based on misread daily report stat: "42/50 at 78.6%" was RSI/OBV aggregate, NOT VWAP-specific WR. Actual VWAP shadow: **17 resolved, 5W-12L, 29.4% WR** on ETH. BTC had zero shadow VWAP predictions. Production code disabled in trade.py before any real orders fired. Shadow continues collecting data. See `docs/analysis/postmortem_vwap_promotion.md`. |
| 24 | Adverse selection: fix fill rate or change venue | Immediate — fill rate destroying live edge | All live | **ACTIONED** | Settled orders: 5W-9L (36% WR). Expired orders: 11W-0L (100% WR). Failed orders (Incident 8/9): 24W-4L (86% WR). +64pp adverse selection gap. Static 7¢ price cap causes winners to expire and losers to fill. $846 in missed winning bets. Three paths under evaluation: dynamic price cap (`docs/specs/stochastic/spec_dynamic_price_cap.md`), websocket live pricing (`docs/specs/stochastic/spec_unified_vps_websocket.md`), venue shift to Bybit perps. Fill diagnostics deployed (`src/fill_diagnostic.py`) to collect data. ETH moved to paper (Decision #25). |
| 25 | ETH 5m: revert to paper | Immediate — adverse selection bleeding unfilled winners | ETH | **ACTIONED** | ETH went live 2026-04-04 (conv=3, $25 flat). Reverted to paper 2026-04-05. Same fill rate problem as BTC — winners expire, losers fill. Paper until execution problem (Decision #24) is resolved. Signal remains strong (62.1% WR paper). |

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
| 2026-04-02 | #19 | Registered hour 16 UTC monitoring | 8 bets, 25% WR — below 50-bet minimum. Monitor only, no code change yet. |
| 2026-04-02 | #20 | Registered 15m conv=4 demotion decision + implemented cap | 59.3% WR on 27 bets. Post-prediction cap in ci_run_15m.py (predict.py is frozen). Conv>3 → conv=3. |
| 2026-04-02 | #16 | ETH regime thresholds recalibrated | LOW<0.10, HIGH≥0.20 in predict_eth.py. Was 83% HIGH_VOL → expected ~31/46/22% split. Shadow contamination audit: clean — shadow scorer only writes reasoning JSON, never affects conviction_score. |
| 2026-04-02 | #21 | Dynamic estimates in predict.py + predict_eth.py | Replaced hardcoded 0.62/0.38 with strength_signal() from shadow_conviction_scorer. Also cleaned stale $75/$200/$300 comments, removed contrarian_signal alias, removed observation_mode flag. |
| 2026-04-02 | #9 | Dead hours now data-driven | compute_dead_hours() queries last 90 days, 30-bet minimum, WR < 50% threshold. Fallback {3, 21} preserved. ETH uses same function. New hours auto-added when data confirms. Decision #19 (hour 16) now auto-tracked. |
| 2026-04-02 | #23 | VWAP promotion REVERTED — misread stat, actual 29.4% WR | "78.6%" was RSI/OBV shadow aggregate, not VWAP. Actual: 5W-12L (29.4%) on 17 ETH bets. BTC had 0 shadow VWAP predictions. Disabled in trade.py before any real money lost. Postmortem: docs/analysis/postmortem_vwap_promotion.md. |
| 2026-04-03 | #20 | Conv=4→3 cap REVERTED | Conv=3 WR collapsed to 22% (2W-7L). Cap removed natural quality filter. Conv=4 at 61% (28 bets) was functioning. |
| 2026-04-03 | #8 | DOWN+NEUTRAL filter extended to 15m | 15m DOWN at 48% WR on 27 bets — same no-edge pattern as 5m. Post-prediction demotion in ci_run_15m.py (predict.py frozen). Symmetric with 5m. |
| 2026-04-04 | #25 | ETH 5m pipeline set to live | ETH conv=3 enabled, $25 flat bets via pipelines.json. Signal validated at 66.7% WR. |
| 2026-04-05 | #24 | Adverse selection quantified, fill diagnostics deployed | Settled 5W-9L (36%), Expired 11W-0L (100%), Failed 24W-4L (86%). $846 missed. `src/fill_diagnostic.py` + trade.py DIAG lines deployed. |
| 2026-04-05 | #25 | ETH 5m reverted to paper | Same adverse selection as BTC. Winners expire, losers fill. Paper until execution fixed (Decision #24). |
