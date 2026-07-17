# BOTSY Decommission Note - 2026-07-16

**Status:** Decommissioned / archived.
**Decision date:** 2026-07-16
**Runtime host:** Deleted DigitalOcean droplet.
**Former host:** `134.209.196.239`
**Former runtime path:** `/home/botuser/polymarket-bot`
**Former services:** `botsy.service`, `polymarket-dashboard.service`
**Last committed daily report:** 2026-06-24

## Summary

BOTSY is no longer running. The DigitalOcean droplet that hosted the engine
was intentionally deleted, so there is no active VPS, no live process, no
paper data collection, and no dashboard at the former host.

This is a planned decommission rather than an unexplained production outage.
The gap after the final committed health/reporting data should not be read as
market performance, signal inactivity, or a failed strategy day. There was no
engine left to collect or publish those rows.

The GitHub repository remains the archive and source of truth for code,
committed daily reports, tests, plans, and postmortems through the final pushed
state. Any future restart should be treated as a fresh deployment decision, not
a continuation of the old production-readiness clock.

## Final Runtime Evidence

Local reachability checks against the former VPS IP on 2026-07-16 showed:

| Check | Result |
|---|---|
| `ping 134.209.196.239` | 100% packet loss |
| `curl http://134.209.196.239:5050` | connection timeout |
| SSH/dashboard ports | no service response |

The last committed `data/engine_health.txt` lines stop on 2026-06-25. The
last committed daily/consolidated reports stop at 2026-06-24.

## Final Operational State

| Area | Final state |
|---|---|
| Engine | Stopped; host deleted |
| Trading mode | No active trading |
| Paper collection | Stopped |
| Dashboard | Offline |
| Daily reports | Archived through 2026-06-24 |
| Live promotion | Not pursued |
| BTC 5m canary | Not started |
| Delayed FAK / Phase C | Not shipped |
| Kill switch / breakers | Historical only; no runtime exists |

## Final Readiness Decision

No pipeline was promoted to production from the final evidence base.

BTC 5m had intermittent positive paper/report periods, but the project never
cleared the production-readiness chain:

- insufficient executable/live-canary-style execution sample;
- delayed FAK sample remained below gate;
- orphan/integrity issues still appeared in reports;
- timing replay did not validate the raw multi-poll timing cells;
- final reports showed the promotion signal threshold below gate.

The June 23 timing section is the clearest example of why raw research cells
cannot justify promotion. The research grid showed attractive T+180/T+240
cells, but executable replay with conviction, freshness, valid price,
resolution, and one-order-per-cycle gates applied was negative:

| Policy | Fired | WR | P&L | EHR |
|---|---:|---:|---:|---:|
| `delay_180` | 41 | 36.6% | -$306.87 | -0.1476 |
| `delay_240` | 39 | 38.5% | -$232.74 | -0.1123 |
| `immediate_actual` | 5 | 0.0% | -$75.00 | -0.4240 |

Therefore Phase C / delayed timing execution should remain rejected unless a
future rebuilt system collects new executable evidence.

## Historical Report Rollups

These rollups are from committed consolidated daily reports only. They are
paper/report evidence, not live order evidence.

### Full Committed Report Archive

Coverage: 2026-04-15 through 2026-06-24.

| Bets | WR | P&L |
|---:|---:|---:|
| 7,147 | 46.3% | -$11,975.54 |

By asset:

| Asset | Bets | WR | P&L |
|---|---:|---:|---:|
| DOGE | 736 | 49.7% | -$100.00 |
| SOL | 1,200 | 45.2% | -$2,850.00 |
| ETH | 1,741 | 45.4% | -$3,544.94 |
| BTC | 3,470 | 46.4% | -$5,480.60 |

Best and worst pipeline rollups:

| Pipeline | Bets | WR | P&L |
|---|---:|---:|---:|
| `bybit` | 879 | 51.5% | +$675.00 |
| `doge_bybit` | 367 | 50.4% | +$75.00 |
| `btc_5m` | 809 | 48.7% | -$121.60 |
| `sol_bybit` | 599 | 45.2% | -$1,425.00 |
| `sol_hl` | 601 | 45.3% | -$1,425.00 |
| `eth_hl` | 445 | 43.4% | -$1,475.00 |
| `eth_bybit` | 449 | 43.0% | -$1,575.00 |
| `kalshi` | 545 | 28.4% | -$5,567.19 |

### June Through Final Report

Coverage: 2026-06-01 through 2026-06-24.

| Bets | WR | P&L |
|---:|---:|---:|
| 1,149 | 48.4% | -$508.05 |

By asset:

| Asset | Bets | WR | P&L |
|---|---:|---:|---:|
| BTC | 708 | 50.4% | +$403.92 |
| ETH | 147 | 47.6% | -$11.97 |
| SOL | 78 | 39.7% | -$400.00 |
| DOGE | 216 | 45.4% | -$500.00 |

### Final Available Week

Coverage: 2026-06-18 through 2026-06-24.

| Bets | WR | P&L |
|---:|---:|---:|
| 522 | 45.4% | -$1,140.83 |

By asset:

| Asset | Bets | WR | P&L |
|---|---:|---:|---:|
| SOL | 8 | 50.0% | $0.00 |
| ETH | 67 | 43.3% | -$190.73 |
| BTC | 311 | 47.3% | -$400.10 |
| DOGE | 136 | 41.9% | -$550.00 |

## Data Caveats

- The numbers above are generated from committed daily/consolidated Markdown
  reports, not a fresh Botsy MCP query.
- Daily/report rows are paper/report artifacts unless explicitly marked as live
  execution elsewhere.
- Missing reports after 2026-06-24 are expected after decommission and must not
  be treated as zero-bet performance days.
- Any future restart needs new runtime evidence from the rebuilt host.

## Restart Rule

If BOTSY is ever restarted, do not resume from old readiness state. Start with:

1. fresh host provisioning;
2. fresh secrets and key rotation;
3. paper-only operation;
4. health/reporting verification;
5. new forward sample gates;
6. explicit decision issue before any live canary.

