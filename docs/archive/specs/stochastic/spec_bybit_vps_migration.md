# Spec: Migrate Bybit to VPS Loop

> **Status:** IMPLEMENTED — VPS consolidated, systemd live

**Status:** Proposed
**Priority:** High — every 7-8 min cycle is a ~40% throughput loss vs. the 5-min target
**Risk:** Low — pattern is identical to the three pipelines already running on the VPS

---

## Problem

Bybit BTC Perps runs on GitHub Actions with three compounding penalties:

| Penalty | Impact |
|---------|--------|
| Cold start (checkout, pip install, tests) | +2-3 min overhead per cycle |
| `sleep 300` after run completes | True cadence is ~7-8 min, not 5 |
| `*/30` cron fallback on broken dispatch chain | Up to 30 min gaps on any single failure |

Net effect: a pipeline showing 64.9% WR and +$700 simulated P&L is running at roughly 60-70% of its intended prediction throughput. Missed cycles are predictions that never fire.

The VPS already runs BTC 5m, ETH 5m, and BTC 15m without these problems.

---

## Change

### 1. Add Bybit to `vps-loop.sh`

One block, same pattern as existing pipelines:

```bash
# Bybit BTC Perps — every cycle (5 min)
python src/predict.py --pipeline bybit_btc_perps
git add -A && git commit -m "bybit predict $(date -u +%H:%M)" && git push || true
```

Place it after the existing BTC 5m / ETH 5m blocks, before the sleep.

### 2. Move Bybit API Keys to VPS

```bash
# Add to .env on VPS (or export in the loop script)
BYBIT_API_KEY=<from GitHub Secrets>
BYBIT_API_SECRET=<from GitHub Secrets>
```

Remove from GitHub Secrets after confirming VPS execution works.

### 3. Disable GitHub Actions for Bybit

- Remove or disable the `repository_dispatch` self-rescheduling workflow
- Remove the `*/30` cron fallback
- Keep the workflow file in repo but set `workflow_dispatch` only (manual trigger for emergencies)

---

## What About Kalshi?

Same problem, same fix, but Kalshi has zero live predictions and zero bets. Migrate it to VPS at the same time if convenient, or defer. No P&L at stake either way.

If migrating both:

```bash
# Kalshi — every cycle (5 min)
python src/predict.py --pipeline kalshi_btc
git add -A && git commit -m "kalshi predict $(date -u +%H:%M)" && git push || true
```

---

## Validation

| Check | Method |
|-------|--------|
| Bybit predictions appearing every 5 min | `git log --oneline --since="1 hour ago"` on VPS |
| No more GitHub Actions runs | Check Actions tab — should show no triggered runs |
| API keys working on VPS | First cycle logs successful API response |
| VPS loop timing still holds | Confirm total cycle time (all pipelines + sleep) stays under 5 min |

### Timing Budget

Current VPS cycle runs 3 pipelines. Adding Bybit (and optionally Kalshi) adds ~30-60s of predict time per pipeline. Verify total execution stays under ~3 min to preserve the 5-min cadence with the sleep.

```bash
# Add to loop for monitoring
CYCLE_START=$(date +%s)
# ... all pipelines ...
CYCLE_END=$(date +%s)
echo "DIAG|cycle_seconds=$((CYCLE_END - CYCLE_START))"
```

If total cycle time exceeds 4 min, run Bybit and Kalshi in parallel with `&` and `wait`.

---

## Revert

Re-enable the GitHub Actions workflow dispatch. No data is lost — predictions commit to the same repo regardless of where they run.
