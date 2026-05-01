# Pivot Options — Where BOTSY Can Go

> **🪦 RETIRED 2026-05-01.**
>
> This document was a 2026-04-23 strategic snapshot framing the V4-decay pivot question. It is preserved as historical context; it is NOT a current source of truth. Several of its assumptions are now stale:
>
> - btc_5m sunset trigger fired 2026-04-28 (live → paper); the doc treats this as a pending decision.
> - The Apr 5 dispatch-timing root cause was discovered 2026-04-28 (see `docs/analysis/signal_rehab_2026-04-28.md`); the doc's framing of the decay as opaque is superseded.
> - The Apr 28 disk-full incident, history rewrite, and ~6h data loss are not reflected; see `docs/ops/postmortem_2026-04-28_disk_full.md` and `docs/ops/postmortem_2026-04-28_data_loss_during_rewrite.md`.
> - Multi-poll Phase A is now the active experiment; this doc precedes it. See `docs/plans/multi_poll_predict_plan.md`.
> - Kalshi rebuild is now estimated at ~4h (not ~2 days) because the strike-aware fair-p machinery already exists in `src/arb_divergence.py`; this doc's costing is wrong.
>
> **For current state:** `~/.claude/plans/groovy-squishing-scott.md` (active plan, rebased 2026-05-01).
>
> **For active experiments:** `docs/optimizations.json` and the per-experiment plans in `docs/plans/`.
>
> The body below is preserved verbatim from the 2026-04-23 cut. Treat it as a snapshot of the question framing at that moment, not as a list of current options.

---

**Date of this cut:** 2026-04-23
**Status:** Retired 2026-05-01 (see banner above)
**Related:** `docs/core/strategy.md` (current strategy), `docs/core/ROADMAP.md`, `docs/ops/DEPLOYMENT.md`

---

## Why this document exists

The V4 momentum thesis on 5-minute crypto Polymarket markets has decayed. Multiple independent indicators over the past two weeks point the same direction:

- **Signal EHR drift:** BTC 5m 7d signal EHR went from +0.035 to −0.086 over ~5 days. Not single-day noise.
- **Regime-level WR collapse:** MEDIUM_VOL/NEUTRAL (dominant regime) dropped from 65.9% WR to 40.4% WR on 57 bets in one week.
- **Shadow Maker reversal:** BTC shadow EHR swung from +0.023 to −0.1024 in 3 days on 42 cumulative fills; ETH swung −0.099 → +0.065 → −0.118. Neither pipeline shows durable positive passive-mode edge.
- **Lab-vs-production disconnect:** Lab measures 57.6% WR on btc_5m over 14 days; production was −$159 in 9 live fills when we tried it. The Lab-to-production translation is lying.
- **FAK pilot (2026-04-21):** 90% fill rate (execution works), 11% filled WR on 9 fills (signal didn't), −$159 net.
- **Consecutive-loss breaker + signal-EHR gate** are now the primary protections keeping btc_5m from bleeding further. When a signal needs six protection layers to avoid losing money, it may not be a signal.

**Simultaneously**, the operational infrastructure is **solid**: engine uptime, memory fix, deploy hook, multi-pipeline dispatch, protection layers, consolidated reporting, strategy lab, shadow experiment framework. Roughly 15 months of engineering that is venue- and signal-agnostic.

The question: **given the infrastructure is an asset and the specific thesis is a liability, where do we go next?**

---

## What's portable

Everything in this list works today and is independent of what we predict or where we trade:

- Multi-pipeline dispatch (N pipelines, shared engine, per-pipeline mode/breakers/DB)
- Shadow experiment framework (`docs/core/SHADOW_FRAMEWORK.md`) — log alternative → compare → promote/revert
- Strategy Lab always-fire — discover edge post-hoc from logged predictions
- Daily and consolidated reporting across all pipelines
- Regime classification (absolute + asset-relative z-score)
- Protection layers: kill switch, daily loss cap, consecutive loss breaker, signal-EHR live gate, edge cushion
- Deploy hook: auto-restart on source-change merges (`docs/ops/DEPLOYMENT.md`)
- MCP tooling for structured queries

## What's not portable (specific to current thesis)

- Momentum signal logic (`predict.py`, `predict_eth.py`) — 5m streak detection, Kraken/Coinbase consensus
- Polymarket CLOB order submission + fill tracking (FAK / GTD / maker)
- Asset-specific regime thresholds (BTC/ETH/SOL/DOGE volatility calibration)
- VWAP mean-reversion strategy (currently live on eth_5m, lab-validated but short sample)

---

## Context: who makes money on Polymarket

Per Akey et al. (2026), ~2% of Polymarket traders are profitable. That profitable cohort almost certainly trades **different products** than we do:

- **Event markets** — elections, sports, geopolitics, pop culture. Longer time horizons, real information integration, domain expertise.
- **Long-duration crypto markets** — daily, weekly, event-based rather than 5m direction. Less replicated.
- **Liquidity provision on illiquid markets** — market making where spreads compensate for inventory risk.
- **Cross-venue arbitrage** — Polymarket vs Kalshi vs CME pricing on the same event.
- **Domain-specific expertise** — weather, FDA approvals, macro data releases.

Our current stack targets none of those. **5m crypto price direction on Polymarket is the single most-crowded algorithmic strategy in prediction markets**, and the "top 2% per Akey" citation is historical — measured over months ending before participant adaptation caught up.

---

## Options, ranked by fit with existing infrastructure

### High fit — reuse the stack mostly as-is

**1. Longer-duration Polymarket crypto markets (daily / weekly / event)**
- Same CLOB, same API, same pipelines
- Switch: new market-selector, different contract expiry filter. Everything else unchanged.
- 5m is the worst timeframe: most crowded, highest noise-to-signal ratio
- Daily markets: "BTC above $X by Friday," "ETH up this week" — longer info integration
- Switching cost: ~3-5 days
- Risk: may still be crowded. Needs a small Lab-scale pilot first.

**2. Cross-venue crypto arbitrage (Polymarket ↔ Kalshi ↔ exchange)**
- Already have Polymarket WS + Kalshi DB + Bybit/Hyperliquid WS connections
- Arb on same event priced differently across venues is edge-bearing when it exists
- Fixed edge (spread capture) rather than decaying alpha — doesn't decay with participant adaptation
- Requires: atomic cross-venue execution, capital held on both sides
- Kalshi was paused (2026-04-17) for architectural bug; fix takes ~2 days
- Risk: capital inefficient, fees eat thin arbs; atomic execution across venues is non-trivial

**3. Market making on longer-duration markets (Phase 2 maker, pointed elsewhere)**
- Maker mode on 5m binary shows no durable edge (shadow EHR oscillates ±10pp)
- Maker on a daily market is a different game: wider spreads, less-replicated, inventory risk is manageable
- Same Phase 2 design already drafted (`docs/plans/shadow_maker_phase_2_plan.md`) — just pointed at different contracts
- Could be the first honest test of the maker hypothesis

### Medium fit — new ingestion, reuse execution + monitoring

**4. Polymarket non-crypto markets**
- Sports (NFL, NBA, soccer) — huge volume, mature betting markets, but requires sport-specific models
- Elections / political — longer horizon, news-flow edge possible
- Weather / energy — numerical weather models reliably beat market prior
- Sentiment / news-driven — LLM + news ingestion as novel signal generator
- Switching cost: 2-4 weeks per market class (new signal generators). Reuse engine, reporting, gates.

**5. Kalshi rebuild**
- Paused after finding market-question parser missing (the BTC momentum signal was being applied to strike-priced binary markets without checking strike reachability — all 420 conv≥3 bets lost)
- Kalshi crypto is less crowded than Polymarket
- Maker fees are a rebate on Kalshi, not a cost
- Fix the parser (~1-2 days), run for a week, measure. Orthogonal venue with our infra intact.

**6. Statistical arbitrage across correlated Polymarket markets**
- "BTC-up-at-10:05" and "BTC-above-$84k-at-10:05" have mathematical relationships
- Cross-market mispricings exist, especially around round numbers and time-to-expiry inflection points
- Requires a relationship model, not just a per-market signal — more complex system design
- Infrastructure reuse: high (same venue, same execution plumbing)

### Low fit — essentially a new system

**7. Porting to Betfair / PredictIt / Manifold**
- Different APIs, market structures, liquidity profiles
- ~2 months to rebuild pipeline architecture per venue
- Only worth it with a specific product advantage there

**8. Stop trading — repurpose infrastructure as research platform**
- Strategy Lab + shadow framework + consolidated reporting is a legitimate research substrate
- Could generate structured signal data, sell access, or publish findings
- No trading P&L but also no execution costs
- Most honest response to "the edge isn't here" if we genuinely can't find one

**9. LLM-augmented event prediction**
- LLM reads news/docs → generates probabilistic event forecasts
- Humans bet selectively on high-confidence divergences from market
- Fundamentally different stack; more research project than trading system

---

## Leading candidates

If forced to pick, the two strongest pivots:

### (A) Longer-duration Polymarket markets

**Thesis:** "5m timeframe is the problem, not crypto." Lab-test it cheaply before committing.

**Plan shape:** Lab-scale always-fire on daily crypto markets, 2-3 weeks. If shadow EHR on daily crypto trends positive, graduate one strategy to paper trading. If not, 5m wasn't the problem — crypto momentum on prediction markets is genuinely dead for us.

**Why it's attractive:** Minimum switching cost. Tests the specific variable (timeframe) that changed. Uses existing infrastructure wholesale.

**Why it might fail:** Daily markets are also crowded. The signal may be equally absent. Acceptable: we learn fast and move on.

### (B) Cross-venue arbitrage (Polymarket ↔ Kalshi)

**Thesis:** "Alpha is dead; capture spread." Stop competing with smart adversaries; collect pricing inefficiencies between venues.

**Plan shape:** Fix Kalshi market-question parser (~2 days), build a price-divergence monitor, small pilot on cross-venue spread trades with tight sizing.

**Why it's attractive:** Fixed edge (spread capture), not decaying alpha. Doesn't require beating anyone. Uses infrastructure we've already built.

**Why it might fail:** Capital inefficient — need funds on both sides. Thin spreads after fees. Atomic execution across venues is non-trivial.

---

## What to explicitly NOT do

- **Do not invest further in Shadow Maker Phase 2 on btc_5m or eth_5m.** The design doc (`docs/plans/shadow_maker_phase_2_plan.md`) was written on Apr 21 assuming BTC shadow EHR was durably positive. It isn't. The plan should explicitly pivot to whatever pipeline has durable shadow EHR when we're ready, or be shelved.
- **Do not try harder on 5m crypto momentum.** Four independent indicators have failed. Adding a fifth fix won't change the outcome.
- **Do not build new infrastructure before testing the pivot cheaply.** Run a Lab always-fire on the new target first. If Lab shows edge, invest. If not, move on.
- **Do not pour engineering into simultaneously exploring 3+ pivots.** Pick one, run it for 2-3 weeks, decide.

---

## The honest uncomfortable question

**Is the 2% of profitable Polymarket traders doing things we could do, or doing things we structurally can't?**

| Cohort | Can we replicate? |
|--------|------------------|
| Sharp sports bettors | Unlikely — domain expertise we don't have |
| Political insiders with information | No |
| Market makers on illiquid markets | Technically yes, but requires manual market curation |
| Cross-venue arbitrageurs | **Yes — pure infrastructure game** |
| Long-horizon macro/fundamental | Possible, with LLM + news ingestion |

Best answer: some combination of (A) longer-duration + (B) cross-venue, probably over the next 2-3 weeks as structured exploration before committing to either.

---

## Sunset candidates (what to pause/kill if pivoting)

If we commit to a pivot, these pipelines should be sunset or explicitly marked research-only:

- **btc_5m** — 8 consecutive fleet-losing days, signal EHR −0.064, Shadow EHR −0.102. Gate-blocked now; flip to `paused` unless 7d EHR crosses +0.02 sustained by **2026-04-28**.
- **eth_bybit / eth_hl** — signal EHR −0.084, consistently losing. Same as BTC perps were.
- **sol_bybit / sol_hl** — 91% HIGH_VOL exposure, effectively idle. Shadow regime data still accumulating toward Phase B decision.
- **doge_bybit / doge_hl** — marginal activity, signal EHR −0.028.

What to keep regardless:
- **Engine + monitoring infrastructure** — works regardless of what we trade
- **eth_5m** — last pipeline with positive 7d signal EHR (+0.013)
- **Shadow Maker Phase 1 logging** — cheap data collection; decision deferred
- **Strategy Lab always-fire** — the edge-discovery engine, venue-agnostic

---

## Decision checkpoints

- **2026-04-28** — btc_5m sunset trigger (if 7d EHR not ≥ +0.02)
- **2026-04-28 (week end)** — 2-week observation of current state complete; pivot commitment decision
- **2026-05-07 or later** — if pivot committed, first Lab-scale always-fire results on new target

---

## Historical context

- **Mar 2026** — V4 momentum launched. Initial paper WR 66-77%. FOK live, then FAK. Reverted to paper Apr 6 after adverse selection.
- **Apr 16-19** — Consolidated report, shadow maker Phase 1, FAK pilot, signal-EHR gate all shipped in rapid succession.
- **Apr 21** — FAK pilot went live, lost $159 on day 1, signal-EHR gate auto-blocked further live trading.
- **Apr 23 (today)** — This document. Acknowledge the specific thesis isn't recovering; consider pivots.

## Changelog

- **2026-04-23** — Initial cut. Framed the pivot question, catalogued options, identified leading candidates and sunset criteria.
