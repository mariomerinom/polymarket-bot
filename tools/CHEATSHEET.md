# BOTSY Cheat Sheet

## MCP Tools (inside Claude Code)

| Tool | What it does | Key args |
|------|-------------|----------|
| `botsy.win_rate` | WR% for any pipeline/date range | `pipeline`, `start_date`, `end_date`, `min_conviction` |
| `botsy.recent_predictions` | Last N predictions with details | `pipeline`, `limit` |
| `botsy.judge_performance` | Shadow Judge verdicts vs outcomes | `start_date` |
| `botsy.pnl_by_day` | Daily P&L breakdown | `pipeline`, `days` |
| `botsy.order_summary` | Order stats (fills, skips, modes) | `pipeline`, `start_date` |
| `botsy.regime_breakdown` | WR by regime (vol bucket, day type) | `pipeline`, `start_date` |
| `botsy.pipeline_overview` | All 5 pipelines at a glance | _(none)_ |
| `botsy.fill_diagnostics` | Fill rate, slippage, adverse selection | `pipeline`, `start_date` |
| `botsy.daily_regime` | Regime classification per day | `pipeline`, `start_date` |
| `botsy.streak_analysis` | Win/loss streaks | `pipeline`, `min_streak` |
| `botsy.query` | Raw SQL against any DB | `pipeline`, `sql` |

**Pipelines:** `btc_5m` (default), `btc_15m`, `eth_5m`, `kalshi`, `bybit`

## Terminal Script

```bash
./tools/cheatsheet.sh wr         # 7-day win rate
./tools/cheatsheet.sh today      # today's predictions
./tools/cheatsheet.sh pnl        # 14-day P&L table
./tools/cheatsheet.sh overview   # all 5 pipelines summary
./tools/cheatsheet.sh judge      # Judge shadow verdicts
./tools/cheatsheet.sh regime     # WR by regime
./tools/cheatsheet.sh orders     # recent orders
./tools/cheatsheet.sh streaks    # current streak
```

## Streamlit Dashboard

```bash
git pull                                        # always pull first — DB updates every ~5 min
source venv/bin/activate                        # activate project venv
streamlit run tools/diag.py                     # launch dashboard
```

Tabs: P&L Overlay, Rolling WR, Regime Heatmap, Fill Diagnostic, Raw Query.

## Quick DB Pulls

```bash
# Pull latest data and open a DB shell
git pull && sqlite3 data/predictions.db

# One-liner: pull + win rate
git pull && sqlite3 data/predictions.db "SELECT COUNT(*) as bets, SUM(CASE WHEN correct=1 THEN 1 ELSE 0 END) as wins, ROUND(100.0*SUM(CASE WHEN correct=1 THEN 1 ELSE 0 END)/COUNT(*),1) as wr FROM predictions WHERE conviction_score>=3 AND resolved=1 AND date(predicted_at)>=date('now','-7 days');"

# Pull + P&L
git pull && sqlite3 -header -column data/predictions.db "SELECT date(placed_at) as day, COUNT(*) as bets, SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) as wins, ROUND(SUM(pnl),2) as pnl FROM orders WHERE placed_at IS NOT NULL GROUP BY day ORDER BY day DESC LIMIT 7;"
```
