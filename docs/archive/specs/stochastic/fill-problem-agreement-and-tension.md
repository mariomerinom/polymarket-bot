# Fill Problem: Agreement & Tension Across Three Analyses

> **Status:** REDUNDANT — Debate analysis; implementation complete

**Date:** 2026-04-05
**Sources:** Grok (Hybrid Spec v1), Gemini (Synthesized Approach), Claude (Condensed Best Approach)

---

## Areas of Full Agreement

All three documents converge on the following without meaningful disagreement.

**1. The static 7-cent cap is the proximate cause of fill failure.** Every analysis identifies the hardcoded `MAX_SLIPPAGE_SPREAD (5c) + FILL_PRIORITY_SPREAD (2c)` as the mechanism that causes winning orders to expire. No document defends the status quo.

**2. Dynamic slippage based on order book microstructure is the core fix.** All three adopt the same base formula from `spec_dynamic_price_cap.md`: a 3-cent floor, 15-cent ceiling, with additive bonuses from depth, spread, and volume. The math is identical across all three documents. There is no disagreement on the structural approach.

**3. Stochastic Entry Timing should not be deployed now.** Grok defers it to "Phase 2." Gemini says "completely discard it for the time being." Claude says "do not implement yet" and lists four specific objections. The reasoning differs slightly (Grok sees it as sequencing; Gemini and Claude see it as fundamentally misguided in a broken-infrastructure context), but the practical recommendation is the same: not now.

**4. The validation framework is nearly identical.** All three propose the same success target (fill rate > 70% over 50 bets), the same revert criteria (fill rate < 50%, slippage increase > 3c, any fill > 20c above market), and the same requirement to log counterfactual data (what the static cap would have produced alongside the dynamic cap).

**5. Paying more per fill is EV-positive on the 5-minute pipelines.** All three agree that even 10-15c of slippage on a $25 bet is acceptable given 60%+ win rates. A filled winner at a worse price strictly dominates an expired winner at zero fill.

---

## Areas of Tension

### Tension 1: Role of Conviction in the Slippage Formula

This is the sharpest disagreement across the three documents.

| Position | Document |
|----------|----------|
| Conviction should be a small additive bonus (0-6c) inside the dynamic formula | Grok |
| Conviction should define the ceiling that caps the microstructure calculation | Gemini |
| Conviction should not be part of the slippage formula at all | Claude |

Grok treats conviction as a fourth bonus term alongside depth, spread, and volume. It adds 3c per tier above conv=3, capped at the same 15c ceiling as everything else.

Gemini inverts this: microstructure calculates the structural need, but conviction sets the maximum the bot is allowed to pay. Conv=3 caps at 5c, conv=4 at 10c, conv=5 at 15c. This means a thick market with a conv=3 signal would still be capped at 5c.

Claude explicitly warns against using conviction in slippage calculations at all, arguing that high conviction correlates with fast market moves, creating an inverted incentive where you pay maximum slippage in exactly the conditions where adverse selection is worst.

**The practical difference:** In a thick market (structural need ~12c) with a conv=3 signal, Grok would allow up to 12c, Gemini would cap at 5c, and Claude would allow 12c. In a thin market (structural need ~4c) with a conv=5 signal, Grok would allow up to 10c, Gemini would allow 4c, and Claude would allow 4c.

Gemini's approach is the most conservative; it uses conviction as a risk limiter. Grok's is the most aggressive; it uses conviction to push past what microstructure alone would allow. Claude treats the market as the only valid source of truth.

### Tension 2: Infrastructure Prerequisites

| Position | Document |
|----------|----------|
| Deploy the formula change immediately, no infrastructure changes required | Grok |
| Deploy the formula change immediately, no infrastructure changes mentioned | Gemini |
| Do not deploy the formula until a real-time price feed replaces the stale DB snapshot | Claude |

This is a significant architectural disagreement. Claude's analysis identifies the stale `market_price` database snapshot as the root cause and argues that any formula change is a band-aid without a live websocket feed. Claude also proposes a cancel-replace execution cycle (iterative order placement with 200-500ms retries) as a prerequisite.

Grok and Gemini both operate within the existing `compute_order()` architecture and propose modifying only the slippage constants and formula, treating the current price feed as adequate.

**The practical implication:** If Claude is correct that the price is stale by the time the order reaches the book, widening the cap may help but won't fully solve the problem. If Grok/Gemini are correct that the cap itself is the binding constraint, the formula change alone is sufficient. The daily report data (8/8 expired winners) is consistent with both interpretations; it's ambiguous whether those orders expired because the cap was too tight or because the price anchor was too stale.

### Tension 3: Scope of Recommendations

| Topic | Grok | Gemini | Claude |
|-------|------|--------|--------|
| Kill 15m pipeline | Not mentioned | Not mentioned | Yes, immediately |
| Adjust bet sizing | Not mentioned | Not mentioned | Yes, tier by Sharpe |
| Exploit 0.15-0.30 bucket | Not mentioned | Not mentioned | Yes, widen caps |
| Capital reallocation | Not mentioned | Not mentioned | Yes, $375 to BTC 5m |

Grok and Gemini scope their recommendations narrowly to the fill problem. Claude expands significantly into portfolio management — killing the 15m pipeline, reallocating capital, adjusting bet sizes, and exploiting specific price buckets.

This isn't a disagreement so much as a difference in scope. Grok and Gemini treat the fill problem as an execution issue. Claude treats it as one symptom within a broader portfolio optimization context. Whether the broader recommendations are warranted depends on whether the user wants a targeted fix or a holistic review.

### Tension 4: How Conviction and Microstructure Should Interact

Even setting aside whether conviction belongs in the formula, the three documents embed different philosophies about the relationship between model confidence and market conditions.

Grok's philosophy: conviction and microstructure are independent signals that should be combined additively. More data is better; let both contribute to the final number.

Gemini's philosophy: microstructure defines reality; conviction defines risk appetite. The market tells you what it costs to trade; conviction tells you how much you're willing to spend. Conviction is a governor, not a price input.

Claude's philosophy: the market is the only reliable signal at execution time. Model conviction is an input to the decision of whether to trade, not how to price the trade. Pricing should be purely empirical.

---

## Open Questions Neither Document Resolves

1. **How stale is the price snapshot?** No document quantifies the lag between the DB snapshot and order submission. If it's 50ms, the infrastructure argument weakens. If it's 5 seconds, it dominates. This is measurable and should be measured before choosing an approach.

2. **Is the Polymarket API capable of supporting a cancel-replace cycle?** Claude's proposal depends on sub-second cancel-and-resubmit. If the API has rate limits or latency that make this impractical, the proposal collapses to the same formula-only approach as Grok/Gemini.

3. **What is the actual fill latency distribution?** The reports show orders that expired, but not how close they were to filling. If orders missed by 1-2c, the formula change is sufficient. If they missed by 10c+, the infrastructure argument strengthens.

4. **Does conviction actually predict adverse selection severity?** Claude asserts it does (high conviction = fast market moves = worse adverse selection). This is testable with existing log data but none of the documents present the analysis.

---

## Summary Matrix

| Dimension | Grok | Gemini | Claude |
|-----------|------|--------|--------|
| Core formula | Microstructure + conviction additive | Microstructure base, conviction ceiling | Microstructure only |
| Conviction role | Bonus term (0-6c) | Risk limiter (caps at 5/10/15c) | None in pricing |
| Infrastructure changes | None required | None mentioned | Real-time feed + cancel-replace |
| Stochastic timing | Phase 2 | Discard for now | Not until infra is fixed |
| Portfolio changes | None | None | Kill 15m, resize bets, reallocate |
| Implementation complexity | Low (formula swap) | Low (formula swap) | High (new data feed + execution loop) |
| Time to deploy | Immediate | Immediate | 3 weeks phased |
| Risk profile | Moderate (conviction may overpay) | Conservative (conviction limits spend) | Low pricing risk, high engineering risk |
