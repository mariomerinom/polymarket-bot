# Fill Problem Resolution: Synthesized Approach

**Date:** 2026-04-05
**Author:** Gemini (AI Assistant)
**Context:** Resolving the adverse selection and 0% fill rates on winning trades identified in 2026-04-04 analysis.

To solve the catastrophic adverse selection issue (expired winners, fully-filled losers), I convened a panel of specialized subagents to review the three proposals in the `stochastic` folder (`fill-implementation.md`, `spec_dynamic_price_cap.md`, and `spec_stochastic_entry_timing.md`).

---

## Subagent Perspectives

### 1. The Contrarian
*"Blindly tethering slippage limits to our internal conviction score (`fill-implementation.md`) is a dangerous act of hubris. The model is not the market. If we allow up to a 15¢ spread purely because our model feels confident, we are volunteering to overpay for toxic flow. The market depth is reality; our conviction is a hypothesis. `spec_dynamic_price_cap.md` relies on empirical facts (volume, spread, depth) and is therefore the only sane path to adapt pricing."*

### 2. The Veteran HFT Engineer
*"The `spec_stochastic_entry_timing.md` proposal is mathematically suicidal in a toxic flow regime. The core issue is that the momentum signal is late relative to the fastest market participants, which is why our winners expire and losers fill. Delaying execution by up to 60 seconds to manually poll a Stochastic oscillator will guarantee we miss our winners entirely. We need speed and microstructure-aware aggression. Drop the timing delay completely and focus purely on the dynamic price cap."*

### 3. The Opportunity Scout
*"We are leaving massive edge on the table by treating all markets the same. But the `spec_dynamic_price_cap.md` is too agnostic—it doesn't care whether our model screams "BUY" (Tier 5) or whispers it (Tier 3), which restricts our flexibility. We need a hybrid. The smartest approach is to be highly aggressive *only* when the book is deep enough to absorb it AND our internal conviction dictates the opportunity is generational."*

### 4. The Return Optimizer
*"Our EV strictly increases by avoiding expired winners, even if we pay 10¢ more for them, because a win at 65¢ is infinitely better than an expired order at 50¢. To maximize ROI and limit drawdown, the optimal algorithm takes the structural awareness of the Dynamic Price Cap and layers it under the Conviction Caps. We let the liquidity define our *dynamic baseline requirements*, but let our conviction define our *ultimate ceiling*."*

---

## The Best Approach (The Hybrid Model)

The best approach is to **merge `spec_dynamic_price_cap.md` with `fill-implementation.md`** while **completely discarding `spec_stochastic_entry_timing.md`** for the time being.

### The Algorithm

1. **Calculate Microstructure Spread** (from `spec_dynamic_price_cap.md`):
   Evaluate real-time liquidity to determine how much spread the market structurally requires.
   ```text
   BASE = 0.03
   depth_bonus  = min(max_bet_2pct / bet_size, 4) / 4 × 0.06
   spread_bonus = max(0, 1 - spread_pct / 5) × 0.03
   volume_bonus = min(volume / 50000, 1) × 0.03
   
   structural_need = BASE + depth_bonus + spread_bonus + volume_bonus
   ```

2. **Define Conviction Ceiling** (from `fill-implementation.md`):
   Set the absolute maximum ceiling we are willing to pay based entirely on signal strength, thereby protecting low-conviction plays from overpaying in thick but toxic markets.
   ```text
   If Conviction = 3: CEILING = 0.05
   If Conviction = 4: CEILING = 0.10
   If Conviction = 5: CEILING = 0.15
   ```

3. **Final Dynamic Slippage Calculation**:
   Clamp the structural need by our conviction ceiling.
   ```text
   dynamic_slippage = min(structural_need, CEILING)
   
   price_limit = min(estimate + 0.02, market + dynamic_slippage + FILL_PRIORITY_SPREAD)
   ```

### Why this solves the issue:
- **No More Expired Winners**: High conviction signals (Tier 5) can automatically stretch up to 15¢ if the book's microstructure demands it, securing the win.
- **Safety Valve**: We will never pay a 15¢ slippage in a thin, low-volume book because the `structural_need` calculation prevents it.
- **No Self-Imposed Delay**: We instantly hit the book aggressively when the signal fires, completely side-stepping the adverse effects proposed in the Stochastic timing spec.

*— Gemini*
