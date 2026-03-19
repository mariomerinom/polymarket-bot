# Deploy to Live Trading on Polymarket

> **Status: DEFERRED** — Remaining in simulation mode. This plan documents what's needed when ready to go live. No implementation until explicitly requested.

## Context
The bot is running with 82% accuracy, +57% ROI in simulation across 51 bets. This plan documents what's needed to go from simulated P&L to placing real bets on Polymarket's BTC 5-minute Up/Down markets.

## What We Have (already working)
- **Market discovery**: Gamma API fetches live BTC 5-min markets (`src/fetch_markets.py`)
- **Predictions**: 3 agents producing estimates with edge, confidence (`src/predict.py`)
- **Scoring**: Auto-resolve from Polymarket API (`src/score.py`)
- **Evolution**: Self-improving prompts (`src/evolve.py`)
- **Orchestration**: Continuous loop on GitHub Actions (`src/ci_run.py`)
- **Dashboard**: Live analytics at GitHub Pages

## What's Missing for Live Trading

### 1. Wallet & Funding
- Need a Polygon wallet with USDC (Polymarket's settlement currency)
- Private key for signing orders (EIP-712 cryptographic signatures)
- USDC approval transaction (one-time, allows Polymarket contracts to spend)

### 2. Trading SDK
- `py-clob-client` — Polymarket's official Python SDK for the CLOB (Central Limit Order Book)
- Handles order building, signing, submission, and status tracking
- Add to `requirements.txt`

### 3. New File: `src/trade.py`
Order placement logic that converts predictions → trades:
- Takes ensemble prediction (or best agent's call)
- Determines direction (buy UP or buy DOWN shares)
- Calculates order size based on confidence level and bankroll
- Submits limit order at or near market price
- Tracks order fills and positions

### 4. Risk Management
- **Position sizing**: Kelly criterion or fixed-fraction of bankroll
- **Max loss per cycle**: hard stop (e.g., don't bet more than 5% of bankroll per market)
- **Daily loss limit**: pause trading if cumulative losses exceed threshold
- **Edge threshold**: only trade when estimated edge > X% (don't bet on 50/50 calls)

### 5. Database Extensions
New table for tracking live orders:
```sql
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT,
    order_id TEXT,        -- from CLOB API
    direction TEXT,       -- "UP" or "DOWN"
    size REAL,            -- USDC amount
    price REAL,           -- limit price
    status TEXT,          -- "pending" | "filled" | "cancelled"
    pnl REAL,             -- realized P&L after settlement
    placed_at TEXT,
    filled_at TEXT,
    cycle INTEGER
)
```

### 6. Environment Variables
```
POLYMARKET_PRIVATE_KEY=0x...     # Polygon wallet private key
POLYMARKET_WALLET_ADDRESS=0x...  # Public address
POLYGON_RPC_URL=https://...      # Polygon RPC endpoint
MAX_BET_SIZE=10                   # Max USDC per bet
EDGE_THRESHOLD=0.02               # Min edge to trade (2%)
DAILY_LOSS_LIMIT=50               # Stop trading after $50 loss
```

### 7. Pipeline Changes
Update `src/ci_run.py` / `src/run_loop.py`:
```
fetch → predict → [NEW: trade if edge > threshold] → wait → resolve → score → evolve
```

## Risk Warnings
- **This is real money** — start with very small bets ($1-5) until proven over 100+ markets
- **82% accuracy on 17 markets is a tiny sample** — could regress hard to 50%
- **Market microstructure**: simulation doesn't account for slippage, fees, or liquidity
- **5-min markets have low liquidity** — large orders may not fill at expected price
- **Private key security**: never commit to git, use GitHub Secrets only

## Recommended Deployment Phases
1. **Paper trading mode**: Place orders in code but log them without submitting → validate sizing logic
2. **Micro-live**: $1-2 bets for 50+ markets → verify fill rates and actual P&L vs simulated
3. **Scale up**: Increase bet size only after 100+ live trades confirm edge holds

## Implementation Order
1. Set up Polygon wallet, fund with small USDC amount
2. Add `py-clob-client` to requirements, create `src/trade.py`
3. Add `orders` table to DB schema
4. Implement paper trading mode first (log orders, don't submit)
5. Add risk management (edge threshold, position sizing, daily limits)
6. Wire into CI pipeline with manual trigger only (not auto-cron)
7. Test with $1 bets
8. Add live P&L tracking to dashboard

## Verification
- Paper trade 20+ markets → compare paper P&L to simulation P&L
- Place 5 micro bets manually via CLI → verify fills and settlement
- Check dashboard shows live order status and real P&L
- Verify daily loss limit triggers correctly
