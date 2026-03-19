# Polymarket 5-Min BTC Up/Down Prediction Bot — V3 Hybrid Quant Specification
**Target date:** March 2026  
**Goal:** Build a production-ready, low-cost, low-latency bot that beats V2.1's backtest realism by using ML + rules instead of slow/expensive LLM agents.  
**Philosophy:** 90% deterministic quant signals (fast, cheap, explainable). 10% optional daily macro bias via cheap LLM. Bet only on high-edge opportunities after fees/slippage.

## 1. Market Mechanics (Do Not Change)
- Markets: "Bitcoin Up or Down - [date time range] ET" (5-minute windows)
- Resolution: Up if end price ≥ start price (Chainlink BTC/USD Data Stream: https://data.chain.link/streams/btc-usd)
- Yes = Up, No = Down
- Prices: $0.01–$0.99 → implied prob
- Collateral: USDC on Polygon
- APIs:
  - Market discovery & metadata → **Gamma API** (public): https://gamma-api.polymarket.com
  - Order book, prices, midpoints → **CLOB API** (public reads): https://clob.polymarket.com
  - Trading (orders) → CLOB API (requires EIP-712 signing + HMAC auth or API key)
- Python clients: Use `py-clob-client` (official) or `polymarket-apis` (Pydantic-validated)

## 2. Data Sources
Primary:
- **BTC price candles (5-min OHLCV + volume)**: Kraken public REST/WebSocket (BTC/USD pair) or Coinbase (fallback). Use 12–20 lookback candles.
- **Polymarket market state**: Gamma API → fetch active 5-min BTC markets (filter by title containing "Bitcoin Up or Down" + current/open status).
- **Chainlink oracle price**: For simulation/backtest verification (not real-time needed since resolution is oracle-based).
- **Optional macro bias**: Human file or cheap daily LLM call (Haiku/Sonnet mini).

## 3. Features (20–30 total — compute fast)
Compute from last 12–20 5-min candles:
- Range position: current price in rolling 12-candle high-low (0.0 bottom → 1.0 top)
- Volume ratio: last / avg volume (last 12)
- Range ratio: last candle range / avg range
- Compression: last 3 ranges shrinking? (bool)
- Consecutive direction: streak of up/down candles (length + direction)
- Wick ratios: upper/lower wick vs body
- Body size relative to range
- Technical indicators:
  - RSI(5) or RSI(8)
  - Bollinger %B or distance from middle band
  - ATR(5) normalized
- Market signals:
  - Distance from Polymarket midpoint price (your implied prob - 0.5)
  - Recent momentum (last 3 candles delta)
  - Time features: sin/cos of hour-of-day, day-of-week

## 4. Model & Prediction
**Primary model:** XGBoost classifier or RandomForest (binary: Up=1, Down=0)
- Target: actual resolution (1=Up, 0=Down) from resolved markets
- Train: rolling window (e.g., last 500–2000 resolved markets)
- Retrain: daily or every 100 new resolutions
- Output: calibrated probability p_up (use Platt scaling or isotonic regression)
- Fallback / simple rule (for low-data periods):
  - Contrarian core: if streak ≥ 3 same direction + shrinking bodies/ranges + wick rejection → fade (predict opposite)
  - Volume confirmation: only if volume ratio > 1.8–2.0

**Predicted prob → edge**
edge = |p_model - market_midpoint| - fees_slippage_buffer
(Assume ~0.015–0.025 buffer for taker fee + 1–2 cent slippage on thin markets)

## 5. Conviction / Bet Filter (Replaces V2 tiers — stricter)
Bet ONLY if:
- edge ≥ 0.08–0.12 (8–12% after friction)
- model confidence high (e.g., p_model ≤0.35 or ≥0.65)
- volume on market > threshold (e.g., $5k–$10k 24h to avoid manipulation)
- No bet if LOW conviction signals conflict

Bet sizing (Fractional Kelly):
size = (edge / (1 - market_prob)) × bankroll × fraction (0.1–0.25)
Hard caps: max $200–500 per bet, $1000–2000 daily risk

## 6. Execution Flow (Main Loop)
1. Every 1–2 minutes (WebSocket preferred over polling):
   - Fetch active 5-min BTC markets via Gamma API (filter title/slug pattern)
   - For each open/recently started market:
     - Get current midpoint (CLOB /price or /midpoint endpoint)
     - Fetch latest BTC candles (Kraken WS)
     - Compute features
     - Run model → p_up
     - Compute edge
     - If edge > threshold → place limit order (or market if urgent)
2. Post-resolution:
   - Poll resolved markets → log outcome
   - Retrain model periodically
3. Daily: Optional macro bias update (cheap LLM: "Current BTC regime? UP/DOWN/NEUTRAL")

## 7. Risk & Safety
- Start in simulation/paper mode (log orders, no real submission)
- Position limits: max 5–10 open bets
- Daily loss stop: -5% bankroll → pause 24h
- Slippage sim: add random 0.5–2 cent adverse fill in backtest
- Logging: SQLite (same schema as V2) + CSV trades

## 8. Tech Stack
- Language: Python 3.10+
- Data: pandas, numpy
- ML: xgboost or scikit-learn RandomForest + sklearn.calibration
- API: py-clob-client (pip install py-clob-client)
- WebSocket: websocket-client or ccxt for Kraken
- Database: sqlite3
- Hosting: VPS (low-latency to Polygon RPC) or always-on machine (no GitHub Actions cron lag)
- Backtest: walk-forward on all resolved markets since Feb 2026 launch

## 9. Milestones for Implementation
1. Data pipeline: fetch active markets + candles → features DataFrame
2. Backtest harness: load historical resolved markets → simulate trades with friction
3. Train baseline XGBoost on features → target resolution
4. Add contrarian rule fallback
5. Conviction filter + sizing logic
6. Dry-run loop (log would-be bets)
7. Live trading wrapper (CLOB order placement — start with small size)
8. Dashboard: simple static HTML or Streamlit (optional)

## 10. Success Metrics (Target vs V2.1)
- Win rate on filtered bets: 58–65% realistic (not 78%)
- ROI after fees/slippage: +15–40% annualized
- Trades/day: 5–30 (very selective)
- Cost: <$0.10/day
- Latency: <500 ms per decision

Implement step-by-step. Start with data fetching + feature engineering. Show code snippets and backtest results at each stage.

Good luck — this should be faster, cheaper, and more robust than the LLM version.