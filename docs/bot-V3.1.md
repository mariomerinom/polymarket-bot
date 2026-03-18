# Polymarket 5-Min BTC Up/Down Trading Bot  
**V3.1 Regime-Filtered Contrarian — Simplified Production Plan**  
**Version date:** March 18, 2026  
**Based on:** BACKTEST_FINDINGS.md (full 14-day evolution results)  
**Core decision:** Replace XGBoost + 32 features with regime-aware contrarian rule  
**Objective:** Capture the +3.3% ROI / +$960 P&L of the plain contrarian rule while eliminating the regime-specific bleed

## Core Strategy (final)

1. Poll active 5-min BTC Up/Down markets (Gamma API)
2. Fetch last ~20 × 5-min BTC/USD candles (Kraken public REST)
3. Compute two regime indicators:
   - Volatility level (HIGH / MEDIUM / LOW) — rolling 1h ATR or std dev of returns
   - Short-term autocorrelation (lag-1 on 60–120 min returns) → mean-reverting if < −0.15
4. Skip entirely if flagged as **mean-reverting regime** (autocorrelation < −0.15)
5. Otherwise check contrarian exhaustion signal:
   - streak ≥ 3 consecutive same-direction candles
   - exhaustion confirmation (at least two of):
     - shrinking candle bodies/ranges (last 2–3 candles)
     - significant wick rejection (upper/lower wick > 1.8–2.0 × body)
     - volume ratio > 1.8× (last candle vs 12-period avg) — optional but recommended
6. If signal fires → place limit order to fade the streak ($75–$150 fixed size)
7. Log every decision + resolution outcome

## Target Characteristics (extrapolated from backtest)

- Selectivity: ~8–15% of markets (~20–45 trades/day average)
- Expected win rate (traded bets): 55–62% in allowed regimes
- Edge after friction: ~3–8% per trade (assuming 1.5% fee + 1–2 cent slippage)
- Regime skip rate: ~20–35% of periods (protects against −$1,533-style drawdowns)
- Daily runtime cost: ~$0 (free public APIs)
- Max drawdown target: <8–10% of bankroll

## Staged Implementation Plan (5 stages — minimal)

### Stage 1 – Data Pipeline (1 day)

Tasks:
- Gamma API poll → filter active “Bitcoin Up or Down – *” markets
- Kraken public REST → last 20 × interval=5 candles (BTC/USD)
- Basic SQLite storage: markets + candles + decisions
- Rate-limit & error handling

Deliverables:
- `fetch.py` (or class)
- Sample output: 5–10 markets with candles + current midpoint

Success:
- Stable polling every 30–60 s
- Captures ≥40–60 active markets in peak hours

### Stage 2 – Regime + Contrarian Signal Logic (1–2 days)

Tasks:
- Regime calculation:
  - Volatility: rolling 60-min std(returns) → HIGH if > 75th percentile (7-day lookback)
  - Autocorrelation: lag-1 on last 60–120 min log-returns → mean-reverting flag if < −0.15
- Contrarian rule:
  - streak_length ≥ 3 (same direction)
  - exhaustion: (shrinking_range_last_3 AND large_wick) OR volume_spike
  - Define thresholds (start with backtest values; allow easy tuning)
- Combine: skip if mean-reverting else check contrarian → signal = fade direction

Deliverables:
- `signals.py` (pure functions: candles → regime_flag, candles → contrarian_signal)
- Unit tests on synthetic / backtest candles

Success:
- Correctly identifies HIGH_VOL/MEAN_REVERTING cases from backtest examples
- Signal fires ~10–15% of non-skipped markets

### Stage 3 – Decision & Paper Logging Loop (1 day)

Tasks:
- Main loop (30–60 s):
  - fetch markets
  - for each new/open market:
    - get candles
    - compute regime
    - if allowed regime → compute contrarian
    - if signal → log “would bet $100 fade direction at current mid”
- Log format: timestamp, market_id, regime, streak, exhaustion_flags, decision, simulated P&L (post-resolution)

Deliverables:
- `paper_bot.py` (full loop, no real orders)

Success:
- Runs 24/7 for ≥24 hours without crash
- Logs match expected selectivity from backtest

### Stage 4 – Backtest Re-run with Regime Skip (1–2 days)

Tasks:
- Reprocess your 14-day data (March 3–17)
- Apply regime filter → skip mean-reverting periods
- Simulate trades with:
  - 1.5% round-trip fee
  - 1–2 cent random adverse slippage
  - fixed $100 bet size (or tiered $75/$150)
- Compare vs original contrarian baseline (+$960 / +3.3%)

Deliverables:
- `backtest_regime.py`
- Summary table: win rate, ROI, P&L, trades, max drawdown, regime-skip %

Success:
- P&L > original contrarian (+$960) or at least drawdown significantly reduced
- No large bleed in previously toxic regime

### Stage 5 – Live Wrapper + Risk Controls (1–2 days)

Tasks:
- Integrate py-clob-client (limit orders only)
- Fixed size: start $50–$100 per trade
- Risk rules:
  - max $1,000–$2,000 daily exposure
  - pause after 5 consecutive losses or >8% daily drawdown
  - human override file (pause / resume)
- Start in dry-run → small live bets after 48h paper confidence

Deliverables:
- `live_bot.py` (with kill switch)
- Deployment notes (VPS + systemd)

Success (first 7–14 days live):
- No catastrophic drawdown
- Positive cumulative P&L after fees/slippage
- Behavior aligns with backtest

## Quick Parameter Tuning Table (start here)

| Parameter                  | Suggested starting value       | Tune if …                                 |
|----------------------------|--------------------------------|-------------------------------------------|
| Autocorrelation threshold  | −0.15                          | Too many / too few skips                  |
| Volatility percentile      | 75th (HIGH if >)               | Adjust to 70–85th                         |
| Min streak length          | 3                              | Test 4 if too many false signals          |
| Wick ratio threshold       | 1.8–2.0 × body                 | Higher = fewer but stronger signals       |
| Volume ratio               | >1.8× (optional confirmation)  | Disable if noisy on Kraken BTC/USD        |
| Bet size                   | $75 fixed (or $75/$150 tier)   | Scale after 50+ live trades               |

This plan is now the leanest, cheapest, and — based on your own backtest — most likely to preserve / improve the edge you already found.

Would you like to:
- adjust any of the starting thresholds above?
- add one more cheap filter (e.g. time-of-day, distance from round number)?
- receive Python code snippets for Stage 2 (regime + contrarian functions)?

Or just say “start Stage 1” and I can give you the first code outline.