# Spec: Fill-Side Adverse Selection on FOK Orders

> **Status:** IMPLEMENTED — FOK adverse selection handling in trade.py

**Status:** ACTIVE — consolidates fill problem across prior specs
**Pipeline:** BTC 5m (initial), applies to all Polymarket FOK paths
**Date opened:** 2026-04-06
**Author:** Post-incident analysis (SIGALRM fix + adverse-selection surfacing)
**Supersedes nothing. Consolidates:** `spec_dynamic_price_cap.md`,
`spec_stochastic_entry_timing.md`, `spec_unified_vps_websocket.md`,
`fill-implementation.md`, `claude-fill-problem-consensus.md`.

---

## TL;DR

We are losing money on BTC 5m not because our signal is wrong, but because
the order execution layer is systematically adverse-selected: **the orders
that would win get killed; the orders that get filled tend to lose.**
Tonight (2026-04-06) the pattern became unambiguous for the first time
because the pipeline was finally running cleanly end-to-end after the
SIGALRM fix.

- Pipeline is CLOB-WS-connected (`botsy_engine.py:362` → `live_orderbook.json`)
- Trade path reads fresh WS book (`trade.py:828` via `_get_live_token_entry`)
- We still lose the race because order submission is **not atomic** with
  the book read. Market makers see the same spot tick we do, and pull the
  ask in the RTT window of our FOK POST.
- Live evidence: 6 orders killed (all would-have-won), 1 order filled
  (loss). Fill rate is **anti-correlated** with outcome.

BTC 5m is paused to paper mode effective 2026-04-06 until this is fixed
in paper with a measurable fill-rate + outcome-correlation improvement.

---

## The Evidence (2026-04-06 evening)

Two incidents in one evening, same root class, different failure modes.

### Phase 1 — SIGALRM masked the problem entirely (4 bets, ~22:55–23:15 UTC)

Every bet failed with `ValueError: signal only works in main thread of
the main interpreter` before ever reaching CLOB. 4 of 4 would have won.
Root cause was a `signal.SIGALRM` timeout guard in worker-thread context.
Fix shipped (`8fe0b4ba`) — see `docs/ops/postmortem_sigalrm_thread_bug_2026-04-06.md`.

| Order | Dir  | Limit | Best ask | Δ | Status | Would-P&L |
|-------|------|-------|----------|---|--------|-----------|
| 70    | DOWN | 0.51  | 0.51     | 0 | killed | +$24.02   |
| 71    | DOWN | 0.50  | 0.50     | 0 | killed | +$25.00   |
| 72    | DOWN | 0.49  | 0.49     | 0 | killed | +$26.02   |
| 73    | DOWN | 0.37  | 0.37     | 0 | killed | +$22.03   |

### Phase 2 — Real adverse selection, SIGALRM fixed (3 bets, ~01:05–01:20 UTC)

With the pipeline hardened, the next three orders revealed the underlying
fill pathology:

| Order | Dir  | Size    | Limit | Best ask | Outcome         | Notes |
|-------|------|---------|-------|----------|-----------------|-------|
| 76    | DOWN | $25.00  | 0.45  | 0.45     | killed → WIN    | ask pulled in flight |
| 77    | DOWN | $22.47  | 0.44  | 0.44     | killed → WIN    | top-of-book depth ≈ $25 |
| 78    | DOWN | $25.00  | 0.42  | 0.42     | filled → LOSS   | −$25.00 realized |

Order 77's prediction-time depth snapshot:
```json
"liquidity": {
  "token": "NO", "best_bid": 0.43, "best_ask": 0.44,
  "spread": 0.01, "max_bet_2pct": 24.97,
  "depth_levels": 56,
  "slippage_at_50": {"avg_price": 0.4449, "slippage_pct": 1.114}
}
```
`max_bet_2pct = $24.97` — we tried to take $22.47. Razor's edge.
Any other taker in the flight window, or a single cancelled ask from the
MM, kills us. The next level up (0.45) has multiple-X the depth.

### Combined scoreboard for the evening

| Category                      | Count | P&L       |
|-------------------------------|-------|-----------|
| Killed orders that would win  | 6     | ≈ +$116   |
| Killed orders that would lose | 0     | $0        |
| Filled orders that won        | 1     | +$19.35   |
| Filled orders that lost       | 2     | −$50.00   |
| **Realized**                  | **3 filled** | **−$30.65** |
| **Counterfactual**            | **9 would-bets** | **≈ +$85**  |
| **Delta cost of AS (1 evening)** | — | **≈ $116** |

Fill rate: **3/9 = 33%**.
Win rate among fills: **1/3 = 33%**.
Win rate among kills: **6/6 = 100%**.

That's not noise. That's the exploit working.

---

## Root Cause: The Write-Side Race

Here is the exact mechanical picture:

```
t-0ms    5m candle closes on Bybit
t+200ms  Multiple MMs' own feeds see the close + next spot ticks
t+300ms  MMs decide: "taker flow will come from TA bots; are we
         going to be on the right side of this move?"
         If spot is still running same direction as the taker's
         implied bet → pull quotes on that side.
         If spot is reversing → hold quotes, happily fill taker.
t+800ms  Our pipeline finishes candle → indicators → prediction
         → signal fires → compute_order starts
t+850ms  compute_order reads live_orderbook.json WS cache.
         Cache is genuinely current (<1s old). ask = 0.45.
t+900ms  _submit_fok_order POSTs to CLOB REST with FOK at 0.45.
         Flight time ~150-300ms.
t+1150ms CLOB matching engine receives our order.
         By now the MM has already pulled 0.45 (reacting to the
         same spot tick our signal is reacting to).
         No resting ask at our limit → FOK killed.
         ---
         Meanwhile, when the move is about to reverse, the MM
         holds their ask. Our order lands. Filled. We now own a
         DOWN token at the local minimum of the down move.
         We lose.
```

### Why live WS subscription doesn't save us

We already do `wss://ws-subscriptions-clob.polymarket.com/ws/market`.
The cache is genuinely live. **It doesn't matter**, because:

1. **Read-atomicity ≠ write-atomicity.** A fresh read at t=850ms cannot
   prevent a book change at t=1000ms before our write lands at t=1150ms.
2. **We can't withdraw our FOK mid-flight.** Once POSTed, it's committed.
3. **Top-of-book is a signal to the MM**, not a commitment from them.
   They can and do pull it any time.

### Why 2-second-old REST snapshot would be even worse

Just flagging: before the WS subscription shipped, we were reading book
via REST at prediction time (~2s before order). Switching to live WS
was a real improvement — it got us to "see the book at decision time."
The remaining gap is from decision time to order-lands time.

### The MM's edge, sized

- **Latency advantage:** MMs co-locate near CLOB matching. Their
  book-update → order-action cycle is probably 10-50ms. Ours is
  150-300ms REST RTT. That's 5-10x.
- **Symmetry of information:** They see the same Bybit/Binance/Coinbase
  spot feed we do, sometimes faster, rarely slower.
- **Filter rule they apply to us:** "Incoming taker on the ask at the
  5m candle boundary + direction matches just-observed spot move →
  probably a TA bot → pull and re-quote higher."
- **No alpha required.** They're running a mechanical stale-quote
  protection rule. We are the stale quote to them, even though we're
  right 65% of the time in outcome space — because they have the
  faster clock.

We are not fighting a model. We are fighting a clock and a rule.

---

## Strategy: Don't Beat Them. Change the Game.

Three independent levers. Each is independently shippable. Each can be
A/B measured against the counterfactual. Listed cheapest first.

### Lever A — Break timing predictability (~1 hour)

**Change:** Randomize order submission within each 5-minute window
by `random.uniform(5, 25)` seconds after candle close (current: ~1s).

**Mechanism:** The MM filter rule almost certainly includes "orders
arriving within 2s of a 5m candle boundary" as a classifier for
TA-bot flow. Desynchronizing us from that cohort makes the rule
fire less often on us. We become noise in their queue instead of a
labeled signal.

**Cost:** Consumes part of the 5-min window. If we delay to t+25s,
our bet is about a 4-minute bet, not 5. Slightly reduces expected
edge per bet (~3-5%).

**Expected effect:** Fill rate 33% → ~50%. It's a distraction tactic,
not a cure. But it's 4 lines of code.

**Measurement:** 20 paper bets post-change. Compare
  - fill rate before (33%) vs after (target ≥50%)
  - outcome correlation: kills still 100% winners, fills still anti-correlated?

### Lever B — Switch FOK → IOC + 1¢ cushion (~2 hours)

**Change:** Replace `_submit_fok_order` with `_submit_ioc_order`.
Limit price becomes `best_ask + 0.01` instead of `best_ask`. Partial
fills are accepted; unfilled remainder cancels immediately.

**Mechanism:** This is the direct attack on the write-side race.
- **IOC vs FOK:** IOC takes whatever is available at our limit *right
  now* and cancels the rest. FOK requires the entire order to fill at
  our limit, or nothing. In a thin top-of-book + MM-pulling regime,
  FOK is strictly worse: any partial pull kills the whole order.
- **+1¢ cushion:** At order 77, `max_bet_2pct=$24.97` at 0.44 but
  the next level up (0.45) has multiples of that. A cushion buys us
  the ability to walk into the second level when the first level
  gets pulled in flight. The cost of the cushion is ~2% of notional
  (~$0.50 per bet at $25 size) — trivial compared to the −$25 of a
  filled losing bet or the +$25 of a missed winning bet.

**Cost:** ~2% of edge per bet, paid in cash. Zero complexity added.

**Expected effect:** Fill rate 33% → 70-80%. This is the primary
mechanical fix. Everything else is refinement.

**Measurement:** 30 paper bets post-change. Same comparison as A.
Plus: **slippage diagnostic** — record (requested_limit, effective_fill_price,
shares_filled, shares_requested) on every IOC.

### Lever C — Reactive execution: book-watch + withdraw (~1-2 days)

**Change:** Execution becomes event-driven instead of snapshot-driven.

```python
def submit_reactive_ioc(token_id, side, size, target_price, timeout_s=10):
    """
    Wait for book state to be favorable, then fire IOC.
    Withdraw if book moves against us before we fire.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        entry = get_live_entry(token_id)  # WS cache
        if entry.best_ask <= target_price and entry.ask_size >= size:
            return submit_ioc(token_id, side, size, target_price + 0.01)
        if entry.best_ask > target_price + 0.02:
            return None, "book_ran_away_pre_submit"
        time.sleep(0.05)  # 50ms polling
    return None, "timeout"
```

**Mechanism:**
1. Don't submit blind. Hold.
2. Watch the WS cache at 50ms intervals.
3. Fire **only** when the book shows our target is currently fillable
   (price ≤ target, size ≥ our order).
4. If the book moves against us (ask > target + 0.02), **don't submit
   at all**. Withdraw pre-submit. Record the would-be-order as a
   `skipped_book_moved` diagnostic instead of an actual loss.

This is us using the MM's own weapon: observe the book and only act
when conditions favor us. They watch for TA takers and pull; we watch
for holdouts and fire. Same game, we play both sides.

**Cost:** Moderate engineering. New execution path, new diagnostic
table, ~40% of orders will "skip" instead of fire (but those would
have been losses anyway).

**Expected effect:** Fill rate 70% (of bets that fire, ~60% of
signals). Critically: the correlation between fills and outcomes
should flip from negative to positive, because we're only firing
when the book is stable enough for our signal to survive the RTT.

**Measurement:** 50 paper bets. Primary KPI:
  - `corr(filled, won) > 0` — fills should correlate with wins,
    not anti-correlate
  - `fill_rate_of_fired_orders ≥ 70%`
  - `skipped_book_moved` counts as "correctly not taken" — sanity
    check that the skips are actually losing bets

### Lever D (rejected) — Wider cushions only

We considered just widening the limit to `best_ask + 0.03` without
going IOC. Rejected because:
- Pays 6% of notional per bet in cost
- Doesn't fix the "MM pulled the whole level" failure mode; a wide
  FOK still dies if the *entire* top-of-book side gets pulled
- Doesn't give us partial fills, which is where the survivable flow is

### Lever E (rejected) — Stop trading 5m, move to 15m

Tempting (slower candle, less competition), but it sidesteps instead of
solving. The 15m market has its own MMs. And BTC 5m has the highest
signal validation in our dataset. Don't abandon the asset that works.

---

## Recommended Sequence

1. **NOW:** BTC 5m → paper mode (DONE, `config/pipelines.json`)
2. **Tonight/tomorrow:** Ship Lever B (FOK → IOC + 1¢ cushion) in paper.
   Instrument fill diagnostic table. Collect 30 bets.
3. **If B gets fill rate ≥70% and flips outcome correlation:**
   add Lever A (timing randomization) as polish, re-arm live with
   a low bet size (e.g. $15 flat for the first 30 live bets).
4. **If B is insufficient:** ship Lever C (reactive execution) in paper.
   50-bet validation before re-arming live.
5. **Never skip the counterfactual measurement.** Every cycle that
   doesn't fire an order still records `would_have_fired`, `would_have_won`,
   so we can keep sizing the gap between signal quality and execution
   quality.

---

## Instrumentation (must-ship with Lever B)

New table `fill_diagnostic`:

```sql
CREATE TABLE fill_diagnostic (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,
    timestamp TEXT,
    cycle INTEGER,
    pipeline TEXT,
    -- Book state at decision time (from WS cache)
    decision_best_bid REAL,
    decision_best_ask REAL,
    decision_spread REAL,
    decision_top_ask_size REAL,
    decision_max_bet_2pct REAL,
    -- Book state at response time (re-read post-CLOB-response)
    response_best_bid REAL,
    response_best_ask REAL,
    -- Order execution
    requested_size REAL,
    requested_limit REAL,
    filled_size REAL,
    filled_avg_price REAL,
    order_type TEXT,  -- 'fok' | 'ioc' | 'gtc'
    result TEXT,      -- 'filled_full' | 'filled_partial' | 'killed_fok' |
                      -- 'cancelled_ioc_residual' | 'book_moved_skipped'
    -- Post-hoc
    outcome INTEGER,   -- 1 = win, 0 = loss, NULL = unresolved
    resolved_at TEXT
);
```

This is the dataset we need to answer, definitively, across a sample:
- Are fills anti-correlated with outcomes? (AS hypothesis)
- Did the book move against us in the RTT window? (race hypothesis)
- Was the fill rate limited by top-of-book depth? (thin book hypothesis)
- Did timing randomization change any of the above? (MM filter hypothesis)

Without this table, every iteration is vibes.

---

## What This Does NOT Do

- Does NOT touch the prediction model. Signal quality is fine (65%+ in
  outcome space). This is a pure execution-layer fix.
- Does NOT change pipeline architecture (still per-cycle dispatch,
  still ThreadPoolExecutor timeout).
- Does NOT add concurrency / threading changes beyond what the
  reactive execution path in Lever C introduces.
- Does NOT affect ETH, BTC 15m, Kalshi, or Bybit pipelines. All
  already in paper mode.

---

## Definition of Done

The fix is done when, over 50 paper-mode bets on BTC 5m:

1. Fill rate of fired orders ≥ 70%
2. Win rate among fills ≥ 55% (in line with paper-trading baseline)
3. Pearson correlation between `filled` and `won` is **non-negative**
   (ideally ≥ +0.1)
4. `fill_diagnostic` table populated on every attempt
5. Average cushion cost per bet ≤ 3% of notional

Only then does BTC 5m go back to live mode, and only at reduced bet
size ($15 flat) for the first 30 live bets to validate the paper→live
translation.

---

## References

- **Postmortem of the SIGALRM bug that exposed this:** `docs/ops/postmortem_sigalrm_thread_bug_2026-04-06.md`
- **Pipeline isolation (prevents related class of bugs):** `docs/plans/pipeline-isolation-unification.md`
- **Runtime state contract (catches silent failure):** `docs/plans/runtime-state-contract.md`
- **Prior fill specs (now consolidated here):**
  - `docs/specs/stochastic/spec_dynamic_price_cap.md` → subsumed into Lever B
  - `docs/specs/stochastic/spec_stochastic_entry_timing.md` → Lever A
  - `docs/specs/stochastic/spec_unified_vps_websocket.md` → IMPLEMENTED (already live)
  - `docs/specs/stochastic/fill-implementation.md` → Lever C
  - `docs/specs/stochastic/claude-fill-problem-consensus.md` → evidence consolidated
- **Kanban:** file a `spec` + `BTC-5m` issue linking to this doc.

---

## Closing Note

These really are good problems to have. The signal works. The pipeline
works. We had to fix four silent-failure bugs in 24 hours just to *see*
this problem clearly. It took live-fire incidents to surface it. And
now that it's visible it's a clean, bounded engineering problem with
three independent knobs, each with measurable outcomes.

The hardest thing about adverse selection on Polymarket is that the
counterparty isn't smarter than you — they're just faster and more
willing to say "no thanks" on the bets where they know they'll lose.
The response is symmetric: we get faster, we get choosier, and we
stop saying "yes please" to bets the MM is thrilled to take.
