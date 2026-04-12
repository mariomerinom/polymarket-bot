# Spec: Fix Token Pricing — Use CLOB Orderbook Instead of Gamma Implied Price

> **Status:** IMPLEMENTED — Per-token CLOB cache in botsy_engine.py

**Date:** 2026-04-05
**Status:** Proposed
**Triggered by:** Smoke test bet filled at 37¢ when system expected 79¢

---

## Problem

Production orders use Gamma API implied prices instead of actual CLOB orderbook prices. For NO tokens, the price is always derived as `1 - price_yes` — a fiction. The YES and NO tokens have **independent orderbooks** with different liquidity, spreads, and mids.

### Evidence

$5 smoke test on 2026-04-05:
- **Expected:** ~6.17 shares @ 79¢ = $5.00 traded
- **Actual:** 5.9 shares @ 37¢ = $2.18 traded
- **Root cause:** Gamma said NO = 0.79. CLOB best ask was 0.37.

### Bug locations

| Location | Code | Problem |
|----------|------|---------|
| `trade.py:240` | `market_price_no = 1 - market_price_yes` | NO price derived, never fetched |
| `trade.py:698-702` | `market_row["price_no"] = round(1 - live_mid, 4)` | Even with live WS mid, NO is still derived from YES |
| `smoke_bet.py:74` | Uses `market["price_no"]` from Gamma | Gamma implied, not CLOB |

### Impact on production

Every $25 DOWN bet is mis-sized. If CLOB NO ask is 40¢ but Gamma implies 75¢, the system sends `$25 / 0.77 = 32.5 shares` but fills at 40¢ = **$13 traded** instead of $25. The bet size is unpredictable.

YES bets have a milder version: when WS cache is stale (>10s), YES falls back to Gamma DB snapshot which may lag the real orderbook by minutes.

---

## Existing Infrastructure

The engine already has a Polymarket CLOB websocket feed:

| Component | Location | What it does |
|-----------|----------|-------------|
| WS connection | `botsy_engine.py:314-361` | `wss://ws-subscriptions-clob.polymarket.com/ws/market` |
| Token subscription | `botsy_engine.py:363-397` | Subscribes to both YES and NO token IDs for all active markets |
| Cache writer | `botsy_engine.py:399-434` | Writes `data/live_orderbook.json` on every book event |
| Cache reader | `trade.py:183-208` | `_get_live_orderbook_mid(market_id)` — reads cache, returns mid if <10s old |
| CLOB REST | `clob_depth.py:23-38` | `get_order_book(token_id)` — fetches full book on demand |
| Depth analysis | `clob_depth.py:41-106` | `analyze_depth(book)` — returns best_bid, best_ask, mid, spread |

**The WS feed already receives both YES and NO book updates.** The problem is the cache only stores the latest single update — each event overwrites the previous token's data.

---

## Fix: Per-Token Orderbook Cache

### Step 1: `src/botsy_engine.py` — Per-token cache structure

**Current** `_update_orderbook_cache()` (line 399): writes one flat dict to `live_orderbook.json`. Each WS book event overwrites the entire file.

**Change to:** Read existing cache, upsert the token entry by `asset_id`, write back.

```python
# Current cache format (single token):
{"market": "0xb13d...", "asset_id": "39748...", "mid": 0.5, ...}

# New cache format (all tokens):
{
  "tokens": {
    "39748...": {"mid": 0.37, "best_bid": 0.36, "best_ask": 0.38, "spread": 0.02,
                 "bids": [...], "asks": [...], "updated_at": "2026-04-05T22:29:05+00:00"},
    "34220...": {"mid": 0.63, "best_bid": 0.62, "best_ask": 0.64, "spread": 0.02,
                 "bids": [...], "asks": [...], "updated_at": "2026-04-05T22:29:05+00:00"}
  }
}
```

**Backward compatibility:** `_get_live_orderbook_mid()` currently reads the flat format. It will be replaced in Step 2, but during rollout both old and new trade.py may read the file. The new reader checks for `"tokens"` key and falls back gracefully.

**Performance:** One extra file read per WS event (to load existing cache before upsert). WS events arrive ~1-5/second — negligible. Atomic write via tmp+rename preserved.

### Step 2: `src/trade.py` — Token-aware price lookup

**Replace** `_get_live_orderbook_mid(market_id)` with `_get_live_token_mid(token_id)`:

```python
def _get_live_token_mid(token_id: str):
    """Read live mid for a specific CLOB token from WS cache.
    Returns float or None if stale (>10s) or missing."""
    try:
        if not LIVE_ORDERBOOK_PATH.exists():
            return None
        cache = json.loads(LIVE_ORDERBOOK_PATH.read_text())
        entry = cache.get("tokens", {}).get(token_id)
        if not entry:
            return None
        updated_at = entry.get("updated_at", "")
        if not updated_at:
            return None
        cache_dt = datetime.fromisoformat(updated_at)
        age_s = (datetime.now(timezone.utc) - cache_dt).total_seconds()
        if age_s > LIVE_ORDERBOOK_MAX_AGE_S:
            return None
        mid = entry.get("mid")
        if mid is not None and 0.01 <= mid <= 0.99:
            return mid
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        pass
    return None
```

**Keep** `_get_live_orderbook_mid()` temporarily for any other callers, but mark deprecated.

### Step 3: `src/trade.py` — Reorder `execute_trades()` flow

Currently in `execute_trades()` (line ~695-717):
1. Build `market_row` from DB prices
2. Try `_get_live_orderbook_mid()` → override `price_yes`, derive `price_no`
3. Call `compute_order()`
4. Resolve CLOB token IDs (line 712)
5. Submit order

**Change to:**
1. Resolve CLOB token IDs **first** (move from line 712 up)
2. Look up live YES mid via `_get_live_token_mid(tokens["yes"])`
3. Look up live NO mid via `_get_live_token_mid(tokens["no"])`
4. Build `market_row` with real prices (fall back to DB if WS stale)
5. Call `compute_order()`
6. Submit order (tokens already resolved)

```python
# 1. Resolve tokens FIRST
tokens = None
try:
    from predict import _get_clob_tokens_safe
    tokens = _get_clob_tokens_safe(pred["market_id"])
except Exception as e:
    print(f"    CLOB token lookup failed: {e}")

# 2. Build market_row with live WS prices when available
market_row = {"price_yes": pred["price_yes"], "price_no": pred.get("price_no", round(1 - pred["price_yes"], 4))}
if tokens:
    yes_mid = _get_live_token_mid(tokens.get("yes", ""))
    no_mid = _get_live_token_mid(tokens.get("no", ""))
    if yes_mid is not None:
        market_row["price_yes"] = yes_mid
    if no_mid is not None:
        market_row["price_no"] = no_mid
    print(f"    [LIVE_OB] YES={market_row['price_yes']:.4f} "
          f"NO={market_row['price_no']:.4f} "
          f"(DB: YES={pred['price_yes']:.4f})")

# 3. Compute order with real prices
order_params, order_reason = compute_order(pred, market_row, liquidity)
```

**Remove** the duplicate token resolution block at line ~712 (now done above).

### Step 4: `src/trade.py` — Fix `compute_order()` NO price fallback with telemetry

`compute_order()` line 240 still has `market_price_no = 1 - market_price_yes`. This is the fallback when WS cache is stale AND Gamma DB is all we have. Add telemetry:

```python
# Current (line 240):
market_price_no = 1 - market_price_yes

# New:
real_no = market_row.get("price_no")
if real_no and abs(real_no - (1 - market_price_yes)) > 0.005:
    # Real CLOB price available and differs from implied
    market_price_no = real_no
else:
    # Fallback to implied — log it
    market_price_no = 1 - market_price_yes
    logger.info(f"DIAG|clob_fallback=true|side=NO|implied={market_price_no:.4f}")
```

**Decision trigger:** If `DIAG|clob_fallback=true` fires on >20% of orders over 50+ bets, the WS feed is unreliable and needs debugging or REST fallback.

### Step 5: `src/smoke_bet.py` — Use real CLOB price for sizing

`smoke_bet.py` runs standalone (no engine WS feed running). Use a one-shot CLOB REST call via existing `clob_depth.py`:

```python
# After resolving tokens, before building order_params:
from clob_depth import get_order_book, analyze_depth
book = get_order_book(tokens[token_key])
if book:
    analysis = analyze_depth(book)
    clob_mid = analysis.get("mid")
    if clob_mid:
        print(f"  CLOB mid: {clob_mid:.4f} (Gamma implied: {mkt_price:.4f})")
        mkt_price = clob_mid
```

This is acceptable for a manual tool — one REST call, not on the hot path.

### Step 6: DIAG gap logging

In `execute_trades()`, after resolving both prices, log the gap between Gamma and CLOB:

```python
if tokens and yes_mid and no_mid:
    gamma_yes = pred["price_yes"]
    gamma_no = round(1 - gamma_yes, 4)
    print(f"    DIAG|gamma_yes={gamma_yes:.4f}|clob_yes={yes_mid:.4f}"
          f"|gamma_no={gamma_no:.4f}|clob_no={no_mid:.4f}"
          f"|gap_yes={abs(yes_mid - gamma_yes):.4f}"
          f"|gap_no={abs(no_mid - gamma_no):.4f}")
```

This data answers: "How wrong is Gamma?" and "Does the gap correlate with fill problems?"

---

## Files to modify

| File | Change | Lines affected |
|------|--------|---------------|
| `src/botsy_engine.py` | `_update_orderbook_cache()` → per-token dict instead of single-file overwrite | ~399-434 |
| `src/trade.py` | New `_get_live_token_mid(token_id)`, reorder `execute_trades()` flow, fix `compute_order()` NO fallback, DIAG logging | ~183-208, ~230-243, ~695-717 |
| `src/smoke_bet.py` | Fetch real CLOB mid via `clob_depth.py` REST before sizing | ~70-86 |

## What NOT to change

- **`fetch_markets.py`** — Gamma prices in the DB are fine for display, filtering, and dashboard. The fix is at order time only.
- **`compute_order()` signature** — stays the same. It reads `market_row["price_no"]` when available, falls back to `1 - price_yes` when not.
- **Polymarket WS subscription logic** — already subscribes to both YES and NO token IDs. No change needed.
- **`clob_depth.py`** — existing functions are sufficient. No new functions needed.

## Consequences

### Positive
- **Correct bet sizing.** $25 DOWN bet actually trades $25 (±$1), not $11.
- **Real-time pricing.** Sub-second WS data replaces hours-old Gamma snapshots.
- **Both directions fixed.** YES and NO both use live CLOB data when available.
- **Telemetry.** `DIAG|clob_fallback` and gap logging surface pricing reliability.

### Risks
- **Cache read frequency.** `_get_live_token_mid()` reads `live_orderbook.json` on every order. This is one read per 5-min cycle — negligible.
- **Cache corruption.** If `_update_orderbook_cache()` crashes mid-write, `_get_live_token_mid()` returns None and falls back to Gamma. Safe degradation.
- **WS disconnection.** If Polymarket WS drops, all token entries age out (>10s) and trade.py falls back to Gamma + logs `DIAG|clob_fallback=true`. No silent failure.

### Startup guard

Add a 60-second post-boot check in `botsy_engine.py`: if `live_orderbook.json` does not contain the `"tokens"` key structure within 60s of engine start, log a `WARNING` and emit a DIAG line. This catches the case where the cache writer update didn't deploy but `trade.py` is already expecting the new per-token format — otherwise every order silently falls back to Gamma and the fix is effectively dead with no signal.

```python
# In engine startup, after WS connections are established:
async def _verify_cache_format():
    await asyncio.sleep(60)
    try:
        cache = json.loads(LIVE_ORDERBOOK_PATH.read_text())
        if "tokens" not in cache:
            logger.warning("Cache still in legacy format after 60s — per-token pricing inactive")
            logger.info("DIAG|cache_format=legacy|age_s=60")
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning("No orderbook cache found after 60s — WS feed may not be writing")
        logger.info("DIAG|cache_format=missing|age_s=60")
```

### Tech debt note

The JSON file as IPC between the engine (writer) and trade.py (reader) works at current volume (one read per 5-min cycle, ~41 orders/day). When Phase 3 moves everything in-process, this file should be replaced with an in-memory shared dict. Until then, it's fine — but flag it so it doesn't calcify.

### What this enables next
- **Dynamic slippage formula** (`spec_dynamic_price_cap.md`) — now has a real price anchor.
- **Cancel-replace strategy** — per-token cache enables price-tracking for order amendment.
- **Fill rate analysis** — gap logging lets us measure Gamma drift and correlate with fill/expire outcomes.

---

## Verification

1. `pytest tests/ -v` — all existing tests pass (no behavioral change to compute_order when called with correct data)
2. `python src/smoke_bet.py --dry-run` — should show `CLOB mid: X.XXXX (Gamma implied: Y.YYYY)` with different values
3. Deploy to VPS, restart engine, check `data/live_orderbook.json` — should now contain `{"tokens": {...}}` with multiple entries
4. `python src/smoke_bet.py --paper` on VPS — verify correct pricing
5. Run live $5 smoke bet — verify TRADED amount ≈ $5
6. `grep "DIAG|clob_fallback" logs/loop.log` — should NOT fire while WS is connected
7. `grep "DIAG|gamma_yes" logs/loop.log` — measure the gap on real orders
8. `grep "DIAG|cache_format" logs/loop.log` — should NOT appear (means new format is live within 60s of boot)
