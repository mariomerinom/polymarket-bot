# Polymarket 5-Min BTC Up/Down Trading Bot
**V3.2 Complete Staged Implementation Plan**
**Version date:** March 18, 2026
**Based on:** V3.1 + critique from V2.1 implementation experience
**Objective:** Build a selective, high-frequency bot that only trades when it has a genuine >=5% edge after realistic fees & slippage.
**Market focus:** All active "Bitcoin Up or Down - [time] ET" 5-minute contracts (288 markets/day, Chainlink resolution, ~$60M+ aggregate daily volume in March 2026)

## Changes from V3.1

| Area | V3.1 | V3.2 | Why |
|------|------|------|-----|
| Warm-up | 300 markets (~1 day) | 1000 markets (~3.5 days) | 1 day of data memorizes one regime |
| Features | BTC candles only | + order-book microstructure (spread, depth imbalance, time remaining) | Polymarket-specific signal is free alpha |
| Baseline | None | Stage 3.5: contrarian rule baseline | ML must beat a 3-line rule or it's not worth the complexity |
| Model | XGBoost alone | XGBoost + Logistic Regression agreement | Filters XGBoost overfitting, same principle as V2.1 agent agreement |
| Calibration | Aspirational | Hard gate: reliability diagram must pass before advancing | Miscalibrated Kelly is how quant funds blow up |
| Sizing | Kelly from day 1 | Fixed tiers for first 500 trades, Kelly only after validation | Robust to miscalibration during cold start |
| Edge chasing | Not addressed | Skip if midpoint moved >3% toward your signal since last poll | Avoid buying stale edge |
| Forward validation | "Aligns with backtest" | Quantitative: win rate within 5pp, edge within 2pp, frequency within 30% | Catches look-ahead bias |
| Drift detection | None (lagging Brier only) | PSI on features + decile calibration tracking (leading indicators) | Detect regime change before losing money |
| Backtest reporting | Aggregate only | Regime-stratified: report per Low/Med/High vol separately | Prevents hiding losses in one regime behind gains in another |

## Core Principles (must be respected in every stage)
- Trade only on real edge (>=5% after 1.5% round-trip fees + 1-3 cent adverse slippage)
- High selectivity: 10-40 trades/day target (not 100+)
- Microstructure awareness: depth checks, size limits, limit orders only
- Start in paper mode -> live only after rigorous validation
- **No bias from the model itself** -- all directional bias comes from data signals, never from hardcoded priors
- Tech stack: Python 3.10+, pandas/numpy/xgboost/scikit-learn, official py-clob-client, SQLite
- Hosting target: cheap VPS (Hetzner / AWS us-east), polling every 30-60 s (WebSocket optional later)

---

## Stage 1 -- Data Pipeline (Goal: 1-2 days)
**Purpose:** Fetch live & historical market data reliably.

Tasks:
- Use **Gamma API** (`https://gamma-api.polymarket.com`) to list active markets
  -> filter titles containing "Bitcoin Up or Down" + active=true
- Fetch last 20 x 5-min BTC/USD candles from **Kraken** public REST (fallback: Coinbase)
- Fetch current midpoint price & order-book summary from **CLOB API** (`/midpoint`, `/book`)
  -> capture: midpoint, best bid, best ask, bid depth within +/-5%, ask depth within +/-5%
- Create SQLite tables: `markets`, `candles`, `order_book_snapshots`, `resolved_outcomes`
- Implement basic rate limiting, retries, error logging

Deliverables:
- `data_fetch.py` (main script or class)
- Runnable example that prints 5-10 active markets with candles + current mid-price + book summary

Success criteria:
- Runs every 30-60 s without crashing
- Captures >=50 active markets per cycle during US/EU hours
- Latency < 2 seconds per full fetch
- Order book snapshots stored for later feature computation

---

## Stage 2 -- Feature Engineering & Regime Detection (Goal: 1-2 days)
**Purpose:** Create clean, non-redundant features from both BTC candles and Polymarket order book.

Tasks:

**BTC candle features** (from last 12-20 candles):
- consecutive streak (length + direction)
- range position (0-1)
- volume ratio (last / avg)
- upper/lower wick ratios
- compression (last 3 ranges shrinking?)
- RSI(5), Bollinger %B, ATR(5) normalized
- recent momentum (last 3 candles delta)

**Polymarket microstructure features** (new in V3.2):
- bid/ask spread as % of midpoint
- depth imbalance: (bid_depth - ask_depth) / (bid_depth + ask_depth) within +/-5% of mid
- midpoint velocity: delta over last 2-3 polls (is market moving toward your signal?)
- time_remaining: minutes until market close (markets behave differently near expiry)
- distance from midpoint to 0.50 (market's current directional lean)

**Time features:**
- sin/cos of hour-of-day (UTC)
- day-of-week (weekend BTC behavior differs)

**Regime detection:**
- 1-hour rolling volatility -> 3-state flag (Low / Med / High) using percentiles on last 7 days
- Autocorrelation of last 20 returns (trending vs mean-reverting regime)

**Feature selection pipeline:**
- Compute ~30 raw features
- Correlation filter: drop features with |corr| > 0.90
- Feature selection: SHAP importance on initial XGBoost -> keep top 12-15 features
- Document which features survived and why

Deliverables:
- `features.py` (function: candles + market_state + book_snapshot -> feature row)
- `regime.py`
- Sample output DataFrame + correlation heatmap (saved PNG)
- Feature selection report: which 12-15 survived, SHAP rankings

Success criteria:
- Produces 12-15 low-correlation features per market
- Regime flag changes sensibly across different BTC volatility periods
- Order-book features show non-zero SHAP importance in initial analysis

---

## Stage 3 -- Walk-Forward Backtest with Friction (Goal: 2-3 days)
**Purpose:** Prove historical profitability under realistic conditions.

Tasks:
- Download all resolved 5-min BTC markets since Feb 2026 launch (Gamma historical endpoint)
- Implement expanding-window walk-forward:
  - **Warm-up: first 1000 resolved markets -> no trades** (V3.2 change: up from 300)
  - Retrain frequency: every 50 new resolutions
- Simulate realistic fills:
  - 1-3 cent adverse slippage (randomized)
  - 1.5% round-trip fee
  - max size = 0.5% of visible depth at time of decision
- Log every simulated trade (entry price, size, outcome, P&L, regime at time of trade)

**Regime-stratified reporting** (V3.2 addition):
- Report results SEPARATELY per regime (Low / Med / High volatility):
  - Win rate, ROI after friction, trade count, max drawdown per regime
  - If any regime is net negative after friction -> flag it, consider excluding that regime from trading

Deliverables:
- `backtest.py` (full script)
- CSV of all simulated trades (including regime column)
- Summary table: win rate, ROI after friction, Sharpe, max drawdown, avg trades/day
- **Regime breakdown table** (win rate + ROI per regime)

Success criteria:
- Positive ROI after all costs (aggregate)
- No single regime with >-5% ROI (losses must not be concentrated)
- Realistic selectivity (10-40 trades/day average)
- Win rate on filtered bets >=57%

---

## Stage 3.5 -- Contrarian Rule Baseline (Goal: 0.5 days)
**Purpose:** Establish the minimum bar that ML must beat. (V3.2 addition)

The V2.1 system's entire edge reduced to one rule: fade exhaustion after consecutive candles with volume confirmation. Before investing in ML complexity, prove it's worth it.

Tasks:
- Run the same walk-forward backtest (Stage 3 infrastructure) with ONLY the contrarian rule:
  - streak >= 3 same direction + shrinking bodies/ranges -> fade (predict opposite)
  - volume ratio > 1.8 required for confirmation
  - Fixed $75 bet size
  - Same friction model (1.5% fees + 1-3 cent slippage)
- Compare against XGBoost backtest from Stage 3

Deliverables:
- Contrarian rule baseline results: win rate, ROI, trades/day, max drawdown
- Comparison table: rule-based vs ML on same markets

Success criteria:
- Document the baseline number. This is what Stage 4's model must beat.
- If the contrarian rule alone produces >+15% ROI after friction, the bar for ML is high -- it must meaningfully exceed this, not just match it.

**Decision gate:** If XGBoost from Stage 3 does NOT beat the contrarian rule by at least 3pp in win rate or 5pp in ROI, reconsider whether ML complexity is justified. The right answer might be a tuned rule-based system with better features.

---

## Stage 4 -- Model Training & Calibration (Goal: 1-2 days)
**Purpose:** Build reliable, well-calibrated probabilities.

Tasks:
- **Primary model:** XGBoost binary classifier (target = actual resolution Up/Down)
  - max_depth=3, n_estimators=100-200, L2 regularization
  - Use expanding history + regime feature
- **Secondary model:** Logistic Regression on same features (V3.2 addition)
  - Serves as sanity check against XGBoost overfitting
  - **Agreement rule: only trade when both models predict the same direction**
  - This mirrors V2.1's agent agreement principle -- diversity in model type filters noise
- Calibration:
  - Time-series split: 80% train, 15% isotonic calibration, 5% test
  - Output calibrated p_up from XGBoost (primary probability)
- Fallback rule when training data < 1000 samples:
  -> contrarian rule from Stage 3.5 (not ML)
- Compute daily Brier score on new resolutions

**Calibration gate** (V3.2 addition -- hard requirement):
- Plot reliability diagram on held-out test set
- For each probability bin (0.3-0.4, 0.4-0.5, 0.5-0.6, 0.6-0.7):
  - Actual win rate must be within +/-10pp of predicted probability
  - Example: if model says 60-70%, actual must be 50-80%
- **If calibration fails: DO NOT advance to Stage 5.** Retune hyperparameters, add more training data, or simplify model. Kelly sizing on miscalibrated probabilities is the single biggest risk in this system.

Deliverables:
- `model.py` (train, predict, calibrate functions -- both XGBoost and LogReg)
- Calibration reliability diagram + Brier score report
- Model agreement analysis: how often do XGBoost and LogReg disagree? What happens when they disagree?

Success criteria:
- Brier score < 0.22 on hold-out
- High-conviction calls (p <=0.38 or >=0.62) show edge in backtest
- **Calibration reliability diagram passes the +/-10pp gate**
- XGBoost + LogReg agreement trades outperform XGBoost-alone trades

---

## Stage 5 -- Edge Filter & Microstructure Safety (Goal: 1 day)
**Purpose:** Enforce strict "no edge -> no trade" rule.

Tasks:
- Edge = |calibrated_p - midpoint| - 0.015 (fees) - dynamic_slippage_buffer
- Mandatory conditions for any trade:
  - Edge >= 5.0%
  - calibrated_p <= 0.38 or >= 0.62
  - **Both XGBoost and LogReg agree on direction** (V3.2 addition)
  - 24h market volume > $10,000
  - Desired-side depth >= $5,000 within +/-2% of mid
  - Proposed size <= 0.5% of visible depth

**Market movement filter** (V3.2 addition):
- If midpoint has moved >3% toward your predicted direction since last poll:
  -> SKIP (market already priced in the signal, edge is shrinking)
- Rationale: by the time you compute and decide, other participants may have moved the market. Chasing a moving midpoint buys stale edge.

**Phased sizing** (V3.2 change -- replaces Kelly from day 1):

Phase A (first 500 paper trades):
- Fixed tiers based on edge:
  - Edge 5-8%: $50 bet
  - Edge 8-12%: $100 bet
  - Edge 12%+: $150 bet
- Hard cap: $1,500 daily risk

Phase B (after 500 paper trades with positive ROI AND calibration validated):
- Switch to Fractional Kelly (0.15x) with $300 max per trade, $1,500 daily risk
- Monitor continuously: if actual win rate deviates >5pp from model's predicted probability over any 100-trade window, revert to Phase A tiers and force recalibration

Deliverables:
- `decision.py` (edge calculation + model agreement check + market movement filter + phased sizing)

Success criteria:
- Backtest shows only high-edge, model-agreement opportunities are taken
- No simulated bets on thin books
- Market movement filter reduces trade count by 5-15% (confirms it's filtering something)

---

## Stage 6 -- Paper Trading Loop & Logging (Goal: 1-2 days)
**Purpose:** Safe real-time forward simulation.

Tasks:
- Main loop: poll every 30-60 seconds
  -> fetch active markets -> compute features -> run model -> check agreement -> apply decision -> log "would trade"
- Never place real orders in this stage
- Log to SQLite + daily CSV export
- Basic console / HTML summary dashboard

**Forward-vs-backtest validation** (V3.2 addition):
After 48 hours of paper trading, compute:
- Paper win rate vs backtest win rate (must be within 5pp)
- Paper average edge vs backtest average edge (must be within 2pp)
- Paper trade frequency vs backtest frequency (must be within 30%)

If any metric deviates beyond threshold:
- Investigate before proceeding
- Common causes: look-ahead bias in backtest, stale feature computation, timing differences between poll interval and market resolution, order-book data availability differences

Deliverables:
- `paper_bot.py` (full runnable loop)
- Forward-vs-backtest comparison report (after 48h)

Success criteria:
- Stable 24/7 operation for >=48 hours
- Forward paper metrics within thresholds of backtest (5pp win rate, 2pp edge, 30% frequency)
- If forward performance significantly exceeds backtest -> investigate (likely bug, not skill)

---

## Stage 7 -- Monitoring, A/B Testing & Safety Controls (Goal: 2-3 days)
**Purpose:** Production-grade reliability & validation.

Tasks:

**Monitoring:**
- Daily Brier + accuracy on last 50 resolutions
- Alert (print / Discord / Slack) if Brier worsens >10%

**Feature drift detection** (V3.2 addition):
- Every 100 new resolutions, compute PSI (Population Stability Index) on each feature vs training distribution
- If any feature PSI > 0.25 -> force retrain immediately (don't wait for 50-resolution cadence)
- If 3+ features drift simultaneously -> flag as regime change, log, alert
- Track model's predicted probability vs actual outcome per decile
- If any decile deviates >10pp for 2 consecutive days -> force retrain + recalibrate

**A/B test:**
- Run original V2.1 LLM system in parallel shadow mode for >=200 markets
- Compare: ROI after friction, Brier, number of trades, drawdown
- Run contrarian rule baseline in parallel too (3-way comparison)

**Safety triggers:**
- Drawdown >8% -> auto-pause 24h
- 7 consecutive losses -> pause
- Daily loss >$1,500 -> pause
- Human override file (pause / resume flag)
- **Calibration drift: if actual win rate deviates >5pp from predicted over 100 trades -> pause and recalibrate** (V3.2 addition)

Deliverables:
- `monitor.py` (includes PSI drift detection + decile tracking)
- `ab_test.py` (3-way: V3.2 ML vs V2.1 LLM vs contrarian rule)
- A/B comparison report

Success criteria:
- V3.2 outperforms BOTH V2.1 and contrarian rule on >=2 of 3 metrics (ROI, Brier, risk-adjusted return)
- Paper Sharpe >0.8 over 200+ markets
- No feature drift alerts during validation period (or if alerts fire, retraining resolves them)

---

## Stage 8 -- Live Trading & Scaling (Goal: 1-2 days + ongoing tuning)
**Purpose:** Controlled real-money deployment.

Tasks:
- Integrate py-clob-client authenticated trading (limit orders only)
- Start very small: $25-$50 max bet for first 100 live trades
- Scale to Phase A tiers ($50/$100/$150) after 100 profitable live trades
- Scale to Phase B Kelly only after 500 live trades with validated calibration
- Optional later upgrades:
  - WebSocket for <30 s freshness
  - Market-making mode for rebates
- Continuous monitoring & manual review

**Scaling gates:**
- 100 live trades profitable -> increase to Phase A tier sizes
- 500 live trades + calibration validated -> switch to Phase B Kelly
- 1000 live trades + Sharpe >1.0 -> consider increasing Kelly fraction from 0.15 to 0.20

Deliverables:
- `live_bot.py` (with emergency kill-switch)
- Deployment instructions (systemd / Docker)

Success criteria (30+ days live):
- Positive cumulative ROI after all costs
- Max drawdown <10% of bankroll
- Realistic annualized ROI target: 12-35%

---

## Final Target Metrics
- Win rate on traded markets: 57-63%
- Trades per day: 10-40 (very selective)
- ROI after fees & slippage: +12-35% annualized (realistic 2026 expectation)
- Max daily cost: <$0.10 (compute) + trading fees
- Max drawdown: <10% of starting bankroll

## Rollout Rule
Only advance to the next stage after:
- Success criteria of current stage are clearly met
- You have reviewed & approved the code & output
- **Decision gates (Stages 3.5, 4 calibration) are explicitly passed**

## Key V3.2 Decision Gates (Summary)

| Gate | Location | Condition | If Fails |
|------|----------|-----------|----------|
| ML vs Rule | Stage 3.5 | XGBoost must beat contrarian rule by 3pp win rate or 5pp ROI | Reconsider ML, tune rule-based system instead |
| Calibration | Stage 4 | Reliability diagram within +/-10pp per bin | Do not advance. Retune or simplify model |
| Forward Match | Stage 6 | Paper within 5pp/2pp/30% of backtest | Investigate look-ahead bias before proceeding |
| Calibration Drift | Stage 7 | Actual vs predicted within 5pp over 100 trades | Pause trading, force recalibrate |
| Live Scale | Stage 8 | 100/500/1000 trade gates for size increases | Stay at current size tier |

Start with **Stage 1**.
