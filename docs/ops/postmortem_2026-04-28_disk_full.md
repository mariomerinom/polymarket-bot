# Postmortem — Engine Crashloop from Disk-Full (2026-04-24 → 2026-04-28)

**Severity:** Sev-2. No live capital lost; 5 days of paper data and the planned arb Phase 0 observation window missed.
**Outage start:** 2026-04-24 00:38:13 UTC
**Outage discovered:** 2026-04-28 12:21 UTC (user check-in after vacation gap)
**Outage end:** 2026-04-28 12:42:07 UTC
**Total duration:** ~108h 4m

## What happened

The `bybit_microstructure_feed` (a.k.a. CAPTURE) module was added recently to record four Bybit WS topics — `publicTrade`, `orderbook.50`, `liquidation`, `tickers` — to gzipped hourly JSONL files in `data/bybit_capture/`. Its docstring acknowledged retention as out of scope: *"engine process doesn't delete anything; a cron or manual policy prunes files older than N days."* The cron was never wired.

After ~16 days of operation (Apr 8 → Apr 24), capture data accumulated to 3.5 GB on a 24 GB disk that hit 100% used. At 2026-04-24 00:38:13 UTC the engine logged `[CAPTURE] write failed orderbook: [Errno 28] No space left on device` and the main process exited with status 1. systemd's `Restart=always` policy fired the unit again ~5 seconds later, which hit the same disk-full condition, exited again, and entered a tight crashloop. By the time the outage was discovered, the systemd restart counter was at **62,565** attempts.

During the outage window:
- No predictions written to any pipeline DB (last: `2026-04-24T00:30:10`)
- No daily reports generated (last: `2026-04-23.md`)
- No arb_divergence rows written (Phase 0 had been live for ~4.5 hours before the outage; the planned ≥48h + regime coverage observation window never started)
- No git auto-commits — repo went silent at `1f419c551..27ee1ed63` boundary
- VPS systemd journal alone showed the activity

## Root cause

The CAPTURE module was implemented as an unbounded writer with deferred retention discipline. The "discipline" was an unwired comment in a docstring.

## Detection failure (the real failure)

The bug was straightforward and self-evident. The deeper problem is that **nothing told us it was happening for 5 days.**

Existing observability layers and what they did:
- Deploy hook → only fires on git pulls; no pull = no fire
- Git auto-commit loop → went silent, but no detector watched for *absence* of new commits
- Daily report generator → ran inside the dead engine; can't report when it can't run
- Local browser-side checks → user was away; no out-of-band alarm wired

This is the same shape of failure as the 2026-04-21 incident (4-hour silent no-op from cached imports). Both: *engine fails, no one is told.* The earlier incident shipped a deploy-hook auto-restart on source change, which is a strong fix for *one* failure mode (stale code) but did not generalize to other failure modes (disk, OOM, WS deadlock, etc.).

## Remediation shipped (commit `828fc0f70`)

### 1. Capture retention
- New constant `RETENTION_DAYS = 7` in `src/bybit_ws_capture.py`
- New helper `_purge_old_capture_files(topic_dir, retention_days)` — idempotent, mtime-based, errors logged not raised
- Wired into `RotatingJSONLWriter._open_for_hour` so retention runs at every hourly file rotation. One cheap directory scan per topic per hour.
- 7 new tests in `tests/test_capture_retention.py` pinning the behavior, including a wired-into-rotation assertion that prevents silent regressions.

### 2. Engine health timer
- New script `tools/check_engine_health.sh` — three checks (disk, systemd state, predictions DB freshness), two outputs (local log + auto-committed summary file), exit codes 0/1/2 for OK/WARN/CRIT.
- New systemd unit `botsy-health-check.service` (oneshot) + timer `botsy-health-check.timer` (every 15 min, `OnBootSec=1min`). Installed at `/etc/systemd/system/`, enabled.
- Output: `data/engine_health.txt` is auto-committed by the engine's `git_commit_loop` while the engine is up. **If GitHub stops getting fresh lines, the engine is dead — visible from outside the host.** This pushes the alarm beyond the local box without requiring email/push wiring.

### 3. Manual one-time disk cleanup
Deleted 872 capture files dated Apr 8-17 (2,050 MB). Kept files Apr 18-24 (1,471 MB) per user direction. Disk dropped from 100% to 89% used. The retention sweep on first post-restart rotation purged 172 additional files, dropping further.

## What we lost

| Artifact | Status |
|---|---|
| Apr 24-27 daily reports | Cannot be reconstructed — predictions weren't written. Will document as `docs/daily/2026-04-24_to_27_GAP.md` rather than synthesize empty reports. |
| Apr 24-27 predictions | Permanent gap in `predictions.db`. All pipelines affected. |
| Phase 0 arb_divergence observation | The 4.5h of data from Apr 23 evening is the only artifact. The planned ≥48h + regime-coverage decision window never accumulated. Reset baseline to 2026-04-28. |
| 2026-04-28 pivot decision inputs | The decision was scheduled for today on data we don't have. Defer broader pivot ~5-7 days; btc_5m sunset call (independent of arb data) can still proceed. |

## What we did not lose

- No live capital exposure (signal-EHR gate had been blocking live orders since Apr 21 FAK pilot)
- All pre-Apr 24 data — predictions, dailies, optimization registry, etc.
- The Apr 18-24 capture data we explicitly kept

## Action items

| # | Action | Status |
|---|---|---|
| 1 | Capture retention | shipped (this commit) |
| 2 | Engine health timer | shipped (this commit) |
| 3 | Document Apr 24-27 gap explicitly | in this commit |
| 4 | Reset arb_divergence_logger baseline date in optimizations.json | follow-up |
| 5 | btc_5m sunset decision (independent of arb data) | next item in this session |
| 6 | Wire push notification (pushbullet / email) on health-check CRIT | follow-up — not strictly needed if user checks GitHub regularly |
| 7 | Add disk monitoring to consolidated_report.py footer | follow-up — surface disk usage in the daily report so the next cliff is visible |

## Lessons

1. **The docstring is not the implementation.** When a module's docstring says "out of scope: a cron will handle this," wire the cron in the same change or don't ship the feature.
2. **Detection mechanisms must work when the system is broken.** Self-reporting from a dead engine is not detection. The health timer is a separate systemd unit with its own lifecycle for exactly this reason.
3. **The deploy hook is not a general-purpose canary.** It catches one class of failure (stale code on git pull). Other failure modes need their own watchers.
4. **Single-volume hosts are fragile.** A 24 GB disk shared by code + data + logs + capture means any unbounded writer can take the whole engine down. Future: consider a separate volume for `data/bybit_capture/` and other research artifacts so a runaway writer can't starve the engine.
5. **Vacation-window risk is real.** The engine ran without supervision for 5 days. Any failure mode that doesn't self-recover gets a 5-day blast radius. Shorter check-in cadence or stronger out-of-band alarming both help.
