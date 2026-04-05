Spec: Optimal Fill Strategy v1 — Hybrid Dynamic Slippage + Phased Stochastic Timing
Status: Proposed
Pipeline: All live pipelines (BTC 5m, ETH 5m)
Author: Grok
Date: 2026-04-05
Problem
From the 2026-04-04 daily report:

BTC 5m: 0% fill rate on 9 orders, with expired orders that would have won.
ETH 5m: 4 expired orders would have won.
Static 7¢ price cap causes good signals to expire while losers get filled.
Adverse selection is killing P&L.

Goal
Combine the best parts of the three existing specs into one clean, effective solution that dramatically improves fill rate while controlling slippage.
Final Hybrid Formula
PythonBASE = 0.03          # 3¢ floor
CEILING = 0.15       # 15¢ hard max

conviction = prediction_row.get("conviction_score", 3)

depth_bonus   = min(max_bet_2pct / bet_size, 4) / 4 * 0.06      # 0–6¢
spread_bonus  = max(0, 1 - spread_pct / 5) * 0.03               # 0–3¢
volume_bonus  = min(volume / 50000, 1) * 0.03                   # 0–3¢
conviction_bonus = max(0, conviction - 3) * 0.03                # 0–6¢ (extra for Tier 4 & 5)

dynamic_slippage = max(BASE, min(BASE + depth_bonus + spread_bonus + volume_bonus + conviction_bonus, CEILING))

price_limit = min(estimate + 0.02, market + dynamic_slippage + 0.02)
Key Features

Liquidity (depth, spread, volume) is the main driver.
Small conviction bonus gives high-confidence Tier 4 & 5 bets extra room when needed.
Always stays between 3¢ and 15¢ slippage.
Falls back safely to old 5¢ behavior if liquidity data is missing.
Size is calculated before price (required for depth bonus).

Phase 2: Stochastic Entry Timing
After the hybrid slippage is live, add stochastic timing (60-second max window) as the final step before placing the order. This improves entry price without changing the limit price logic.
Implementation (Minimal)
Files to change:

src/config.py → Add the constants (BASE, CEILING, bonuses)
src/trade.py → Add compute_dynamic_slippage() function + update compute_order() + add volume to SQL query + add counterfactual logging
tests/test_trade.py → Add tests for the new logic

Validation Plan
Before deploying: Record current fill rate, expired-would-win count, and average slippage.
Success targets (after 50 bets):

Fill rate > 70%
Much fewer expired winners
Average slippage per filled bet increases by no more than 3¢
No order fills more than 20¢ above market

Revert if:

Fill rate drops below 50%
Slippage cost rises more than 3¢ per bet
Any fill >20¢ above market

Recommended rollout:

Deploy Hybrid Dynamic Slippage first (immediate fix)
Add Stochastic Timing later as Phase 2

This approach directly solves the fill problem shown in the April 4 report while taking the strongest elements from all previous specs.
Signed: Grok