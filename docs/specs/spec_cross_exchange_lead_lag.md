# Spec: Cross-Exchange Lead-Lag Strategy

> **Status:** STILL RELEVANT — No lead-lag detection implemented

**Status:** Proposed
**Pipeline:** BTC 5m (primary), BTC 15m (secondary)
**Category:** New strategy — temporal arbitrage. Extends existing consensus signal.
**Problem:** The cross_exchange_consensus optimization compares Kraken vs Coinbase streaks as a binary (agree/disagree). At 43/50 bets it shows 74.4% WR — there's clearly signal in the cross-exchange relationship. But the current implementation discards the most valuable information: *which exchange moved first*. If Coinbase shows a streak 1-2 candles before Kraken, there's a predictable window where Kraken (and Polymarket, which tracks the broader market) is about to catch up.
**Goal:** Detect when one exchange leads the other and bet on the lagging exchange/market catching up.

---

## Why This Is Different from Momentum and Consensus

| Aspect | Momentum | Consensus (current) | Lead-Lag |
|--------|----------|-------------------|----------|
| Uses Coinbase | Yes (primary) | Yes (comparison) | Yes (as leader or lagger) |
| Uses Kraken | No (or secondary) | Yes (comparison) | Yes (as leader or lagger) |
| Signal | Streak on one exchange | Both agree/disagree | One leads, other follows |
| Timing | After streak forms | After both streaks form | *Before* lagging streak forms |
| Binary? | Yes (streak or not) | Yes (agree or disagree) | No — continuous (lead magnitude, lag duration) |

The consensus signal says "both exchanges see the same thing." Lead-lag says "one exchange sees it first, and the other is about to."

---

## Signal Logic

### Step 1: Compute Per-Exchange Streaks

Already partially implemented via the consensus system. Extend to track:

```
For each exchange (Coinbase, Kraken):
  - Current streak direction and length
  - Streak start time
  - Net return during streak
  - Time of last candle update
```

### Step 2: Detect Lead-Lag

```
lead_lag_score = 0

# Case 1: One exchange has a streak, the other doesn't yet
if exchange_A.streak >= 3 AND exchange_B.streak < 2:
    leader = A
    lagger = B
    lead_lag_score = exchange_A.streak - exchange_B.streak

# Case 2: Both have streaks, but one started earlier
elif exchange_A.streak_start < exchange_B.streak_start:
    leader = A
    lagger = B
    lead_lag_score = (exchange_B.streak_start - exchange_A.streak_start).minutes

# Case 3: No clear lead-lag
else:
    no signal
```

### Step 3: Signal Generation

| Condition | Signal | Confidence |
|-----------|--------|-----------|
| Coinbase leads by 2+ candles, Kraken flat | Predict direction of Coinbase streak | High — Kraken likely to follow |
| Kraken leads by 2+ candles, Coinbase flat | Predict direction of Kraken streak | High — Coinbase likely to follow |
| One leads by 1 candle | Predict leader's direction | Medium — may be noise |
| Both in sync | Defer to momentum strategy | No lead-lag signal |
| Exchanges diverge (opposite streaks) | No signal | Ambiguous — stay out |

### Step 4: Estimate Lag Duration

Historical analysis of how quickly the lagger catches up:

```
For each historical lead-lag event:
  - Time from leader streak=3 to lagger streak=2
  - Did the lagger actually follow? (boolean)
  - If yes, how many candles to catch up?
```

This determines the trade window. If historical catch-up is typically 1-3 candles (5-15 min), the contract needs to resolve within that window.

---

## Dynamic Leader Detection

Don't assume one exchange always leads. The leader can change based on:

- **Time of day:** Coinbase may lead during US hours, Kraken during European hours
- **Volatility regime:** In high-vol, the exchange with more volume may lead
- **News/events:** The exchange that lists the news-moving asset may react first

Track a rolling 1-hour leader score:

```
leader_score = (times_A_led - times_B_led) / total_lead_lag_events

If leader_score > 0.3: A is the reliable leader this hour
If leader_score < -0.3: B is the reliable leader this hour
If abs(leader_score) < 0.3: No reliable leader — reduce conviction
```

---

## Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Min leader streak | 3 | Leader must have streak ≥ 3 |
| Max lagger streak | 1 | Lagger must not have caught up yet |
| Lead gap threshold | 2 candles (10 min) | Minimum time lead to generate a signal |
| Leader score window | 1 hour | Rolling window for dynamic leader detection |
| Leader score threshold | ±0.3 | Below this = no reliable leader |
| Max trade window | 3 candles (15 min) | If lagger hasn't followed in 15 min, the lead-lag failed |
| Cooldown | 10 minutes | After a signal, wait before another lead-lag bet |

---

## Data Requirements

| Data | Source | Currently Available? |
|------|--------|---------------------|
| Coinbase 5-min candles | Coinbase API | Yes |
| Kraken 5-min candles | Kraken API | Yes |
| Per-exchange streak data | Consensus system | Partially — currently aggregated, need per-exchange time series |
| Historical lead-lag events | Derived from streak data | No — need to start logging |

### New Infrastructure Needed

1. **Per-exchange streak time series:** Store `(exchange, timestamp, streak_direction, streak_length, streak_start_time, net_return)` at every prediction cycle.
2. **Lead-lag event log:** When a lead-lag event is detected, store it with the eventual outcome (did lagger follow? how many candles?).
3. **Leader score tracker:** Rolling 1-hour tally of which exchange led.

The consensus system already fetches both exchange feeds. The extension is storing the temporal relationship, not just the agreement/disagreement.

---

## Interaction with Other Strategies

| Strategy | Relationship |
|----------|-------------|
| Momentum | **Predecessor.** Lead-lag fires before momentum's streak threshold is met on the lagging exchange. When momentum eventually fires on the lagger, lead-lag already has a position. No conflict — lead-lag is earlier entry on the same eventual trend |
| Consensus | **Direct extension.** Consensus is the binary version of lead-lag. Lead-lag replaces consensus if validated — it captures the same information plus timing |
| Order Flow | **Complementary.** Order flow watches Polymarket CLOB. Lead-lag watches exchange price feeds. Different microstructures, different information. If both signal the same direction: very high conviction |
| Dislocation | **Complementary.** Dislocation detects spot vs contract divergence. Lead-lag detects exchange vs exchange divergence. Different divergences, both profitable |

---

## Expected Impact

The consensus optimization at 74.4% WR on 43 bets suggests strong cross-exchange signal. Lead-lag should capture at least the same edge, plus additional signals from temporal analysis.

```
Current consensus boost: +1 conviction tier on ~30% of bets
Lead-lag independent signals: estimated 3-5 per day
At conv=3 ($75) × 65% WR = ~$22/day
Monthly: ~$660
```

Plus the conviction boost for momentum signals confirmed by lead-lag alignment:

```
Momentum bets with lead-lag confirmation: estimated 5-8 per day
Conviction bump +1 tier = larger bet sizes on higher-WR bets
Estimated additional: ~$30/day
Monthly: ~$900

Total estimated: ~$1,560/month
```

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Exchange feeds have different latencies | Normalize timestamps. Use candle close times, not fetch times. Account for API delay |
| Leader/lagger relationship is random | Track leader_score. If it stays near 0 over 100+ events, there's no exploitable pattern — sunset the strategy |
| Lagger doesn't follow | Max trade window of 3 candles. If lagger hasn't followed, close the mental position (contract resolves regardless). Track catch-up rate |
| Adds complexity to an already complex system | Start as Mode A (independent signals). Only integrate as Mode B (confirmation layer) after standalone validation |
| Exchange downtime creates false signals | If one exchange feed goes stale (>5 min without update), disable lead-lag signals until both feeds are live |

---

## Validation Plan

```
name: cross_exchange_lead_lag
type: data collection → shadow → small stakes

Phase 1 — Data Collection (1 week):
  - Log per-exchange streak data with timestamps at every cycle
  - Compute lead-lag events retroactively
  - Measure: catch-up rate, average lag duration, leader consistency
  - Determine: is there a reliable leader? How often does lagger follow?

Phase 2 — Shadow (50 signals):
  - Generate shadow predictions from lead-lag events
  - Compare against consensus signal performance
  - Track: WR, timing advantage vs momentum, leader score stability
  - Success: WR > 60%, lagger catch-up rate > 70%

Phase 3 — Small Stakes (50 bets):
  - Enable at conv=3 ($75)
  - Circuit breaker: $300 max drawdown
  - Success: positive P&L, timing advantage of 1+ candle vs pure momentum
```

---

## Relationship to Consensus Optimization

The cross_exchange_consensus optimization is at 43/50 bets with 74.4% WR — nearly validated. If it passes at 50 bets:

- **Short term:** Ship consensus boost to production (it's a simple +1 conviction adjustment)
- **Medium term:** Build lead-lag as a richer replacement that captures temporal information
- **Long term:** Lead-lag subsumes consensus. The binary agree/disagree becomes a special case of the temporal analysis

Do not block consensus promotion on lead-lag development. Consensus is ready now. Lead-lag is a future enhancement.
