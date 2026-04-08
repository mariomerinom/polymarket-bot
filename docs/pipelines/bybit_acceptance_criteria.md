# Bybit BTCUSDT Perp — Live Re-arm Acceptance Criteria

**Status:** PAPER (as of 2026-04-08)
**Author:** Phase 10 of the Bybit pivot plan (`~/.claude/plans/groovy-squishing-scott.md`)
**Pipeline config:** `config/pipelines.json` — key `bybit`, field `mode`

## Why this document exists

The Bybit pipeline can be flipped to live by changing a single line in
`config/pipelines.json`. That is precisely the kind of decision that
should not be reversible by vibes. This document defines the checklist
that must be satisfied **in writing, with data in `tools/diag.py`**
before that flip happens.

## Current reality check (2026-04-08)

The Phase 2 backtest, sweep, and OOS validation all failed on BTCUSDT
5m perps:

- Base ride: **28.6% WR** over 4,570 trades (6 months).
- Sweep: no parameter combination cleared 52% WR on N≥100.
- Best sweep cell (1h / hold=24 / fade / time_only, 56.3% WR on N=126)
  collapsed to 41.9% WR in Q4 and −$115 in odd months — curve-fit.
- Phase 5 conviction calibration: top tier (conv=5) has N=2. Conv=3
  vol_low cell shows 71.2% WR on N=66, but the top-tier-discrimination
  hypothesis is disproved.
- Phase 6 consensus boost: boosted sample too small (N=4) to validate.

**Conclusion:** The momentum signal as currently configured does not
clear the live re-arm bar. This document is therefore aspirational —
it defines the bar a future signal iteration must clear, not one the
current signal is close to clearing.

## Criteria (all must be met)

| # | Criterion | Measured from | Threshold |
|---|-----------|---------------|-----------|
| 1 | Paper bet sample size | `diag.py` → Rolling WR (conv≥3, 30d) | N ≥ 50 resolved |
| 2 | Paper win rate | `diag.py` → Rolling WR (conv≥3, 30d) | WR ≥ 55% |
| 3 | Paper counterfactual P&L | `diag.py` → P&L Overlay | Positive over 30d |
| 4 | Fill-rate proxy (paper) | `fill_diagnostic` → paper_would_fire rate | ≥ 70% |
| 5 | No failing integrity checks | `predictions_bybit.db` → `integrity_log` | 0 rows with status='FAIL' in last 7d |
| 6 | Max drawdown on paper P&L | `daily_report.py` Bybit block, 30d | < $300 |
| 7 | All Bybit tests green | `pytest tests/test_bybit.py -q` | 59/59 pass |
| 8 | No parallel state sources | Static check | `_check_consecutive_losses` resolves via `system_state.get_system_state` only (Phase 0 shim still in place) |
| 9 | Bybit signal confirmed on OOS | `docs/research/bybit_backtest_oos_2026-04.md` | Top cell ≥ 52% WR on all halves and ≥ 3/4 quarters |

### How to check each criterion

1. **Sample + WR + P&L**: `streamlit run tools/diag.py`, select Bybit
   BTC pipeline only, min_conviction=3, days=30. Record N, WR, P&L
   counterfactual.
2. **Fill-rate proxy**: In the Fill Diagnostic tab of `diag.py`,
   filter pipeline=bybit. Count `paper_would_fire` vs total terminal
   events in the last 30 days; paper_would_fire / total ≥ 0.70.
3. **Integrity**: `sqlite3 data/predictions_bybit.db "SELECT COUNT(*)
   FROM integrity_log WHERE status='FAIL' AND timestamp >= datetime('now','-7 days')"`
   must return 0.
4. **Drawdown**: In the daily report (`docs/daily/YYYY-MM-DD.md`)
   Bybit section "Position Lifecycle", compute trough-to-peak on the
   30d rolling P&L series.
5. **Tests**: `source venv/bin/activate && python -m pytest tests/test_bybit.py -q`.
6. **State source**: `grep -n "_check_consecutive_losses" src/bybit_trade.py` —
   should resolve to a single shim that calls `system_state.get_system_state`.
7. **Signal OOS**: open `docs/research/bybit_backtest_oos_2026-04.md`
   and confirm the verdict clears 52% — **currently fails**.

## Sizing gate (post-flip)

Even after all criteria pass, the first 10 live bets must be at $25
flat (Phase 1 sizing), with kill-switch active at −$300 daily or a
single WR measurement below 50% over N ≥ 20. This mirrors the BTC 5m
re-arm gate.

## Who flips the switch

Not the agent. A human reads this document, confirms all criteria
against the current `diag.py` view, and edits `config/pipelines.json`
manually. The agent's job is to keep the criteria measurable and the
data honest.

## Revisit cadence

If Bybit remains PAPER after 30 days of fresh data, this document
must be re-opened and the criteria re-examined. Either the thresholds
are wrong or the signal is wrong — both outcomes are decisions, not
drift.
