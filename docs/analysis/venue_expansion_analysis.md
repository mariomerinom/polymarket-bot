# Venue Expansion Analysis — Where Does the Signal Work?

Date: 2026-04-10
Context: Polymarket edge is being competed away (adverse selection on fill). The momentum signal validates at 64-70% WR across multiple pipelines but can't execute profitably on Polymarket's thin CLOB. Where else can we take it?

---

## The Asset We Actually Have

Before looking at new venues, inventory what exists:

- **Momentum signal** — streak detection on 5-minute candles, 64-67% WR paper across BTC and ETH
- **Regime classification** — volatility + autocorrelation filter that correctly skips mean-reverting and HIGH_VOL non-trending markets
- **Conviction scoring** — 0-5 tier system gating which signals become bets
- **Risk infrastructure** — circuit breakers, kill switch, daily loss limits, consecutive loss breaker
- **Real-time websocket engine** — Bybit WS feeds, candle buffer, TA engine, pipeline dispatch on candle close
- **Validation discipline** — paper-first, 50-bet minimum, forward-only validation, one change at a time

The signal is asset-agnostic. The infrastructure is crypto-native but adaptable. The discipline is portable everywhere.

---

## Tier 1: Already Built — Just Flip the Switch

### Bybit BTCUSDT Perpetual

| Dimension | Detail |
|-----------|--------|
| Current WR | **70.0% on 20 bets** (first day post-rehabilitation) |
| Baseline | 50.5% on 319 bets (pre-fix) |
| Infrastructure | Fully built — `ci_run_bybit.py`, `bybit_trade.py`, `bybit_score.py` |
| Execution | Limit orders on Bybit central order book. Deep liquidity. Maker fee 0.02%. |
| Fill problem? | **No.** Perpetual futures fill instantly on a central matching engine. No adverse selection. |
| What's needed | API credentials with trading permission. Flip `BYBIT_TRADING_ENABLED=true`. |
| Risk | Small position size (0.005 BTC ~ $360). Stop-loss + time ceiling already implemented. |
| Timeline | **Hours.** |

**Recommendation: This is the single most obvious move.** The signal works. The infrastructure exists. The fill problem that killed Polymarket doesn't exist on perps. The only reason we're not live is that we haven't flipped the switch.

Wait for 50-bet validation (Issue #70, ~2 more days), then go live.

### Kalshi BTC Strike Markets

| Dimension | Detail |
|-----------|--------|
| Current WR | Data accumulating (resolution fixed 2026-04-09) |
| Infrastructure | Fully built — `ci_run_kalshi.py`, `kalshi_score.py`, `kalshi_markets.py` |
| Execution | Kalshi central matching. CFTC-regulated. USD settlement. |
| Fill problem? | **No.** Centralized matching, sub-second fills. |
| What's needed | Kalshi API credentials (account + API key). |
| Risk | Regulated US venue. Lower risk profile than crypto DEXs. |
| Timeline | **Days** (account setup + 50-bet validation). |

**Recommendation:** Get API credentials. Let 200+ predictions accumulate with the new candle-based resolution. If WR > 55%, go live. This is a parallel revenue stream with zero signal development cost.

---

## Tier 2: Same Signal, New Exchange (Days of Work)

These are all BTC/ETH perpetual futures on different exchanges. The signal is identical — only the execution layer changes.

### OKX Perpetual Futures

| Dimension | Detail |
|-----------|--------|
| Liquidity | #2 perp exchange by volume after Binance. BTC/USDT perps do $5-10B daily. |
| Fees | Maker: 0.02%, Taker: 0.05%. Same as Bybit. |
| API | REST + WebSocket. Well-documented. Python SDK available. |
| Why | Execution diversification. If Bybit goes down, OKX keeps running. Different user base may create different microstructure. |
| What's needed | `okx_trade.py` (order placement), `ci_run_okx.py` (pipeline wrapper), WS subscription in engine. |
| Timeline | **2-3 days** of development. |

### Hyperliquid

| Dimension | Detail |
|-----------|--------|
| Liquidity | Fastest-growing perp DEX. BTC does $1-3B daily. |
| Fees | Maker rebate up to 0.02%. Taker: 0.035%. Net positive to provide liquidity. |
| API | REST + WebSocket. Python SDK (`hyperliquid-python-sdk`). |
| Why | No KYC. On-chain settlement. Maker rebates mean we get *paid* to provide liquidity. |
| Differentiator | Decentralized — no counterparty risk (unlike CEX). Funds stay in your wallet. |
| What's needed | Similar to OKX — trade module, pipeline wrapper, WS subscription. |
| Timeline | **2-3 days** of development. |

### Bitget Perpetual Futures

| Dimension | Detail |
|-----------|--------|
| Liquidity | #3-4 perp exchange. BTC/USDT does $3-5B daily. |
| Fees | Maker: 0.02%, Taker: 0.06%. |
| Why | Copy-trading feature means retail flow creates exploitable microstructure. Momentum may perform even better here. |
| What's needed | Same pattern — trade module + pipeline wrapper. |
| Timeline | **2-3 days.** |

**Recommendation for Tier 2:** Pick one (OKX or Hyperliquid) after Bybit goes live and validates for 1-2 weeks. Running the same signal on two exchanges doubles revenue with minimal additional risk. Hyperliquid's maker rebates are interesting — we'd get paid to place orders that already win.

---

## Tier 3: Same Concept, Different Asset Class (Weeks of Work)

### 0DTE SPY/QQQ Options

| Dimension | Detail |
|-----------|--------|
| Concept | "Will SPY be above $520 by 4PM?" — exact same binary bet structure as Polymarket |
| Liquidity | **Massive.** 0DTE SPY options trade $1T+ notional daily. No fill problem possible. |
| Fees | $0.65/contract on IBKR. At $1 wide strikes, that's ~1.3% round-trip. |
| Signal transfer | SPY has intraday momentum patterns. Regime detection (VIX = volatility, sector rotation = trend) maps directly. |
| Why | Same intellectual framework, completely different market. No crypto correlation. Real diversification. |
| What's needed | Interactive Brokers account. New data source (polygon.io or IBKR market data). `spy_data.py`, `spy_trade.py`. Adapt regime thresholds for equity vol. |
| Risk | Options expire worthless (max loss = premium). No leverage blowup risk if buying only. |
| Timeline | **1-2 weeks.** Signal validation on historical data first. |

**Recommendation:** This is the most interesting Tier 3 option. Same binary bet concept, infinite liquidity, no adverse selection, uncorrelated to crypto. The hardest part is calibrating regime thresholds for equity markets — but the framework is the same.

### Forex (EUR/USD, GBP/USD, USD/JPY)

| Dimension | Detail |
|-----------|--------|
| Liquidity | $7 trillion daily. Deepest market on earth. |
| Fees | Sub-pip spreads on majors. ~0.01% round-trip on IBKR. Essentially free. |
| Signal transfer | FX momentum is a documented academic anomaly at daily/weekly horizons. At 5-minute, unclear. |
| Why | Zero execution risk. The fill problem cannot exist. If momentum transfers to 5-min FX, the infrastructure is printing money. |
| What's needed | Forex broker (IBKR, OANDA). New data source. Regime calibration for FX volatility (very different from crypto). |
| Risk | Leverage. Forex brokers offer 50:1 by default. Must cap at 2-5x or the circuit breakers are meaningless. |
| Concern | **5-minute FX momentum may not exist.** Academic evidence is at daily+ horizons. HFT firms dominate sub-minute. The 5-min window might be a dead zone — too fast for macro momentum, too slow for microstructure alpha. |
| Timeline | **2-3 weeks.** Research spike needed before building. |

**Recommendation:** Worth a research spike — download 6 months of 5-min EUR/USD candles and run the momentum signal against it. If streak-3 momentum shows > 53% WR after spread, build it. If not, the signal doesn't transfer to this timeframe in FX. A weekend of backtesting answers the question before writing any infrastructure.

### CME Micro Futures (Micro BTC, Micro ETH, Micro Gold, Micro Oil)

| Dimension | Detail |
|-----------|--------|
| Concept | Same BTC/ETH momentum, but on a regulated US exchange. Also opens gold and oil. |
| Liquidity | Micro BTC does ~$500M daily. Gold micros do ~$2B. Deep enough. |
| Fees | $1.25 per contract per side. ~0.03% on micro BTC. |
| Why | Regulated venue. Same BTC signal on different market microstructure. Gold/oil are bonus — commodity momentum is well-documented. |
| What's needed | CME-capable broker (IBKR, TradeStation). Market data subscription ($10-30/mo). New trade module. |
| Timeline | **1-2 weeks** for BTC. Additional calibration for gold/oil. |

---

## Tier 4: Interesting but Needs New Signal Work

### Sports Live Betting (Momentum on Score Changes)

When a team scores twice in 5 minutes, live odds overreact. Same momentum concept — ride the streak. But requires domain knowledge per sport. Very different data pipeline. **Months of work.**

### Equity Sector Momentum

Monthly rebalancing of sector ETFs based on momentum (buy winners, sell losers). Well-documented factor. But operates at monthly scale — completely different from our 5-minute infrastructure. **Different project entirely.**

### Crypto Funding Rate Arbitrage

We already proved funding rate has no edge at 5-min (18-month backtest). At 8-hour windows it shows 89% WR but that's a different strategy requiring capital to sit in positions for hours. **Possible future project, not a port.**

---

## Priority Ranking (Updated 2026-04-11)

| Priority | Action | Expected Return | Effort | When |
|----------|--------|-----------------|--------|------|
| **1** | Go live on Bybit | Immediate revenue | Hours | After 50-bet gate (~2 days) |
| **2** | Get Kalshi API credentials | Second revenue stream | Days | Now (account setup) |
| **3** | ~~Research spike: 5-min momentum on EUR/USD and SPY~~ | ~~Determines if Tier 3 is viable~~ | ~~Weekend~~ | **DONE — signal does NOT transfer** |
| **4** | Hyperliquid as second perp exchange | 2x Bybit revenue | ✅ Built | Pipeline deployed, paper mode |
| **5** | ~~Build 0DTE options pipeline~~ | ~~Uncorrelated revenue~~ | — | **CANCELLED — SPY WR = 49%** |
| **6** | ~~Build forex pipeline~~ | ~~Deepest liquidity~~ | — | **CANCELLED — EUR/USD WR = 41%** |
| **7** | Add crypto pairs (SOL, others) | Same structural edge | 2-3 days each | After Bybit + HL validate |

**Research spike results (2026-04-11):** SPY 49.0% WR, Gold 46.5% WR, EUR/USD 41.3% WR on 5-min momentum. None transfer. The edge is crypto-specific. See `docs/research/momentum_transfer_backtest.md`.

---

## The Core Insight

The signal works. The Polymarket execution doesn't. Instead of fixing Polymarket's structural limitations (thin CLOB, adverse selection, 5-min expiry), go where the execution problem doesn't exist.

Bybit is already there. It's running at 70% WR with infrastructure that's fully built. Everything else on this list is upside on top of that.
