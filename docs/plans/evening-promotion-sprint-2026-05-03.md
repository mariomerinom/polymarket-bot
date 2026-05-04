# Evening Promotion Sprint - 2026-05-03

## Summary

Tonight's work keeps production capital off while turning the healthiest signal
evidence into explicit promotion, protection, rehab, and execution lanes. Fresh
pipeline evidence came from Botsy MCP after `pipeline_overview`; optimization
forward progress came from `python3 src/optimization_tracker.py check`.

## Decision Gate Register

| Gate | Posture | Current Evidence | Blocker | Next Trigger |
|------|---------|------------------|---------|--------------|
| #96 BTC 5m production readiness | Promotion candidate, not ready | 7d: 83 bets, 51.8% WR, +$106.24. 30d: 412 bets, 50.5% WR, +$148.55. Judge accepted: 73 bets, 60.3% WR, +$353.31; judge rejected: 169 bets, 45.0%, -$357.96. | #15 execution remains open; BTC5M shadows are still thin. | 50 forward observations in selected BTC5M cohorts, positive forward P&L, no staleness incident, and execution fix or explicit micro-canary bypass. |
| #99 BTC5M quiet daily tape | Best BTC terrain thesis, collecting | Baseline: 275 bets, 63.6% WR, +$1,794.61. Forward: 0/50 after registration. | Forward clock just started. | 50 forward quiet-tape observations above breakeven and not materially below baseline. |
| #85 high-range BTC/ETH protection | Protection candidate, not promotion | `intraday_range_gate`: 147 post bets, 46.9% WR, -$187.62. New `btc5m_high_range_protection_shadow`: baseline 41 bets, 39.0% WR, -$220.05; forward 0/50. | Needs forward confirmation that high-range remains toxic. | 50 forward high-range observations; if still weak, propose protection with rollback criteria. |
| #97 Bybit BTC favorable terrain | Testnet/paper promotion candidate | 7d aggregate: 71 bets, 57.7% WR, +$275. 30d terrain: MEDIUM_VOL/TRENDING 62 bets at 61.3%, LOW_VOL/NEUTRAL 28 at 67.9%, LOW_VOL/TRENDING 14 at 71.4%; HIGH_VOL/TRENDING 32 at 37.5%. New tracker baseline: 127 bets, 63.8%, +$875; forward 0/50. | No live-equivalent execution audit; forward tracker just started. | 50 forward favorable-terrain observations, positive after fees, plus testnet/live-equivalent execution audit. |
| #98 ETH 5m low-vol rehab | Rehab candidate only | 7d aggregate: 96 bets, 45.8% WR, -$51.06. 30d LOW_VOL/NEUTRAL 98 at 54.1%; LOW_VOL/TRENDING 16 at 81.2%. New tracker baseline: 129 bets, 61.2%, +$656.26; forward 0/50. | Full ETH aggregate remains weak; judge coverage is 0%. | 50 forward low-vol observations and 7d aggregate stops deteriorating. |
| #15 adverse-selection execution | Production blocker | BTC 30d orders: 185 total, 35 live, 166 settled, -$541.34 total order P&L. Fill diagnostics: 233 records, 9 filled_full, 139 paper_would_fire; current diagnostic summary does not yet compute filled WR or skipped-would-have-won %. | Old issue is descriptive, not an execution checklist. | Convert #15 into a micro-canary checklist with fill, expiry, slippage, adverse-selection, and rollback metrics. |

## Terrain Playbooks

| Terrain | Current Posture | Operating Rule |
|---------|-----------------|----------------|
| Quiet BTC daily tape with 5m streaks | Promotion lane | Keep BTC5M in paper/shadow until #99 reaches 50 forward observations; do not change signal logic while measuring. |
| BTC judge-accepted bets | Promotion lane | Treat as a candidate selector, not a live gate, until 50 forward accepted observations and execution gate clear. |
| BTC high-range days | Protection lane | Keep measuring. If forward high-range remains below breakeven, write a separate protection proposal. |
| Bybit BTC favorable regimes | Testnet lane | Continue paper/testnet study; avoid full-pipeline promotion because high-vol and neutral aggregate dilute edge. |
| ETH low-vol | Rehab lane | Study only the low-vol subset; full ETH 5m is not promotable while 7d aggregate is below breakeven. |
| ETH/SOL/DOGE perps outside favorable cohorts | Avoid/monitor | No production optimization tonight; maintain observability only. |

## Execution Canary Shape

Any live-capital canary that bypasses #15 should be small, explicit, and
instrumented before it starts:

- Scope: one selected BTC5M cohort only, preferably judge-accepted quiet-tape or
  judge-accepted trending.
- Size: $5-$10 flat canary, no scaling, no Kelly, no multi-pipeline expansion.
- Duration: fixed 24-48 hour window or 20 live attempts, whichever comes first.
- Hard stop: daily live loss <= -$50, 3 consecutive live filled losses, fill WR
  below 45% after 10 filled orders, or expired-would-have-won gap above 25pp.
- Required reporting: filled WR, expired-would-have-won WR, fill rate, rejected
  rate, average slippage, signal EHR vs executed EHR, and adverse-selection %
  if available from diagnostics.
- Rollback: return the cohort to paper immediately and leave the forward shadows
  running.

## Evening Conclusions

1. BTC5M is not broadly ready, but judge-accepted and quiet-tape cohorts are the
   highest-signal Polymarket path.
2. Bybit BTC favorable terrain is the cleanest non-Polymarket candidate, but it
   needs live-equivalent execution evidence before capital.
3. ETH 5m has a credible low-vol rehab slice but a weak full-pipeline surface.
4. High-range BTC terrain should be treated as a protection problem, not a place
   to find more edge.
5. The next real unlock is not more signal tinkering; it is making #15 measurable
   enough that a micro-canary can be approved or rejected cleanly.

## Next Morning Sweep

1. Pull from GitHub and use Botsy MCP `pipeline_overview` first.
2. Run `python3 src/optimization_tracker.py check`.
3. Update #96/#97/#98/#99/#85/#15 only with facts that changed.
4. If #15 remains open, do not promote normal live capital.
