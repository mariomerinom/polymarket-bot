# BOTSY Decommission TODO - 2026-07-16

BOTSY has been intentionally decommissioned after deletion of the DigitalOcean
droplet. This TODO closes operational loose ends and preserves restart
requirements if the project is ever revived.

## Immediate

- [ ] Confirm DigitalOcean has no remaining billable droplets, volumes,
  snapshots, reserved IPs, firewalls, load balancers, or backups for BOTSY.
- [ ] Revoke or rotate all keys that were present on the VPS:
  Polymarket/CLOB, Bybit, Hyperliquid, Kalshi, GitHub deploy credentials,
  OpenAI/DigitalOcean inference keys, and any dashboard credentials.
- [ ] Disable or remove monitors, browser bookmarks, dashboards, cron jobs, or
  automations that point at `134.209.196.239`.
- [ ] Preserve the GitHub repo as the archival source of truth.
- [ ] Do not regenerate missing post-2026-06-24 dailies unless rebuilding from a
  verified external data source.

## Documentation

- [ ] Link `docs/ops/decommission_2026-07-16.md` from the project primer or
  README so future agents see the decommission state before suggesting VPS
  checks.
- [ ] Mark production promotion/readiness as closed-not-pursued in the relevant
  decision/incident records.
- [ ] Record that delayed timing / Phase C was rejected by executable replay,
  not merely deferred.
- [ ] Add a short note that post-2026-06-24 report gaps are expected because the
  engine host no longer exists.

## Archive Hygiene

- [ ] Decide whether to keep or revert the local change to
  `docs/daily/2026-06-24.md`.
- [ ] Decide whether any local `docs/optimizations.json` edits should be
  committed as final archival state or discarded.
- [ ] If committing documentation updates, run the required test suite first,
  then commit and push.
- [ ] Tag the final archive commit if desired, e.g. `archive/botsy-standdown`.

## If Restarted

- [ ] Treat restart as a new deployment, not a continuation.
- [ ] Provision a fresh VPS or alternative host.
- [ ] Restore only code/config from GitHub; do not assume missing runtime data
  can be recovered.
- [ ] Recreate `.env` from rotated secrets.
- [ ] Install `botsy.service`, dashboard service, health timer, and deploy hook.
- [ ] Start with kill switch present and all pipelines in paper mode.
- [ ] Verify one full reporting cycle before removing the kill switch.
- [ ] Reopen readiness only after fresh forward samples:
  50+ signal bets, 10+ executable fills, 50+ delayed FAK attempts if that path is
  reconsidered, zero unexplained orphans, and passing health gates.

