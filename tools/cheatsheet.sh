#!/usr/bin/env bash
# BOTSY terminal cheat sheet — quick sqlite3 queries for all pipelines
# Usage: ./tools/cheatsheet.sh [command]
# Commands: wr, today, pnl, overview, judge, regime, orders, streaks

set -euo pipefail
DB_DIR="$(cd "$(dirname "$0")/.." && pwd)/data"

cmd="${1:-help}"

case "$cmd" in
  wr)
    # Win rate (BTC 5m, last 7 days)
    sqlite3 "$DB_DIR/predictions.db" "
      SELECT COUNT(*) as bets,
             SUM(CASE WHEN correct=1 THEN 1 ELSE 0 END) as wins,
             ROUND(100.0*SUM(CASE WHEN correct=1 THEN 1 ELSE 0 END)/COUNT(*),1) as wr_pct
      FROM predictions
      WHERE conviction_score>=3 AND resolved=1
        AND date(predicted_at)>=date('now','-7 days');"
    ;;

  today)
    # Today's predictions
    sqlite3 -header -column "$DB_DIR/predictions.db" "
      SELECT substr(predicted_at,12,5) as time, direction, conviction_score as conv,
             ROUND(estimate,3) as est, correct
      FROM predictions
      WHERE date(predicted_at)=date('now')
      ORDER BY predicted_at DESC;"
    ;;

  pnl)
    # P&L by day (last 14 days)
    sqlite3 -header -column "$DB_DIR/predictions.db" "
      SELECT date(placed_at) as day,
             COUNT(*) as bets,
             SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) as wins,
             ROUND(SUM(pnl),2) as pnl
      FROM orders
      WHERE placed_at IS NOT NULL
      GROUP BY day ORDER BY day DESC LIMIT 14;"
    ;;

  overview)
    # All pipelines at a glance
    for db in predictions predictions_15m predictions_eth predictions_kalshi predictions_bybit; do
      name="${db#predictions}"
      name="${name:-_btc5m}"
      name="${name#_}"
      printf "%-12s " "$name"
      sqlite3 "$DB_DIR/${db}.db" "
        SELECT COUNT(*) || ' preds, latest: ' || MAX(predicted_at)
        FROM predictions;" 2>/dev/null || echo "(no DB)"
    done
    ;;

  judge)
    # Judge shadow verdicts
    sqlite3 -header -column "$DB_DIR/predictions.db" "
      SELECT json_extract(reasoning_data,'\$.judge.verdict') as verdict, COUNT(*) as n
      FROM predictions
      WHERE json_extract(reasoning_data,'\$.judge') IS NOT NULL
      GROUP BY verdict;"
    ;;

  regime)
    # WR by regime
    sqlite3 -header -column "$DB_DIR/predictions.db" "
      SELECT regime, COUNT(*) as n,
             ROUND(100.0*SUM(CASE WHEN correct=1 THEN 1 ELSE 0 END)/COUNT(*),1) as wr_pct
      FROM predictions
      WHERE conviction_score>=3 AND resolved=1
      GROUP BY regime;"
    ;;

  orders)
    # Recent orders
    sqlite3 -header -column "$DB_DIR/predictions.db" "
      SELECT substr(placed_at,1,16) as placed, direction, status, mode,
             ROUND(size,2) as size, ROUND(pnl,2) as pnl
      FROM orders ORDER BY placed_at DESC LIMIT 15;"
    ;;

  streaks)
    # Current streak
    sqlite3 "$DB_DIR/predictions.db" "
      WITH recent AS (
        SELECT correct, ROW_NUMBER() OVER (ORDER BY predicted_at DESC) as rn
        FROM predictions WHERE conviction_score>=3 AND resolved=1
      ), streak AS (
        SELECT correct, rn FROM recent
        WHERE rn <= (SELECT MIN(rn) FROM recent r2
                     WHERE r2.correct != (SELECT correct FROM recent WHERE rn=1))
      )
      SELECT CASE WHEN (SELECT correct FROM recent WHERE rn=1)=1
             THEN 'WIN' ELSE 'LOSS' END || ' streak: ' || COUNT(*) as current_streak
      FROM streak;"
    ;;

  lab)
    # Strategy Lab performance
    sqlite3 -header -column "$DB_DIR/strategy_lab.db" "
      SELECT strategy, symbol, COUNT(*) as preds,
             SUM(CASE WHEN outcome=1 THEN 1 ELSE 0 END) as wins,
             ROUND(100.0*SUM(CASE WHEN outcome=1 THEN 1 ELSE 0 END)/
               NULLIF(SUM(CASE WHEN outcome IS NOT NULL THEN 1 ELSE 0 END),0),1) as wr_pct,
             ROUND(SUM(CASE WHEN pnl IS NOT NULL THEN pnl ELSE 0 END),2) as pnl
      FROM lab_predictions
      GROUP BY strategy, symbol
      ORDER BY strategy, symbol;" 2>/dev/null || echo "(no lab DB)"
    ;;

  lab-pending)
    # Strategy Lab pending predictions
    sqlite3 -header -column "$DB_DIR/strategy_lab.db" "
      SELECT strategy, symbol, COUNT(*) as pending
      FROM lab_predictions WHERE outcome IS NULL
      GROUP BY strategy, symbol;" 2>/dev/null || echo "(no lab DB)"
    ;;

  skills)
    echo "=== Claude Code Skills (slash commands) ==="
    echo ""
    echo "  /health-check          Quick operational status of all pipelines"
    echo "                         Checks: CI freshness, prediction recency, order fills,"
    echo "                         circuit breaker, test status, kanban board 'Ready' column"
    echo ""
    echo "  /validate-optimization Register/monitor/close optimization experiments"
    echo "                         Enforces: baseline, revert criteria, 50-bet minimum"
    echo ""
    echo "  /plan-feature          Design implementation plans (backward→present→future)"
    echo "                         Output: docs/plans/<feature-name>-plan.md"
    echo ""
    echo "  /review-decisions      Audit GitHub Issues decision tracker against live data"
    echo "                         Checks thresholds, suggests new decisions for patterns"
    echo ""
    echo "  /critique-performance  Deep analysis via 4 specialized agent analysts"
    echo "                         Dimensions: WR, regime, execution, edge decay"
    echo ""
    echo "  /review-specs          Evaluate unimplemented specs with agent reviewers"
    echo "                         Output: ranked priority matrix"
    echo ""
    echo "  /backtest              Run native Polymarket backtests (5m/15m pipelines)"
    echo ""
    echo "  /eod-log               Generate end-of-day session log"
    echo "                         Output: docs/sessions/YYYY-MM-DD.md"
    echo ""
    echo "=== Engine Hooks (botsy_engine.py) ==="
    echo ""
    echo "  strategy_lab_run()     Line ~643. After production pipeline dispatch."
    echo "                         Runs all matching lab strategies on same candle data."
    echo "                         Called via asyncio.to_thread (non-blocking)."
    echo ""
    echo "  Planned Phase 3 hooks (not yet implemented):"
    echo "    _update_orderbook_cache() — CLOB event hook for order flow strategies"
    echo "    bybit_ws_capture.py       — Microstructure hook (liquidations, CVD)"
    echo "    Ticker stream             — Funding rate hook for contrarian strategies"
    echo ""
    echo "=== MCP Tools (tools/botsy_mcp.py) ==="
    echo ""
    echo "  pipeline_overview      All pipelines at a glance (auto-discovers from config)"
    echo "  recent_predictions     Last N predictions for any pipeline"
    echo "  win_rate               WR with filters (pipeline, days, direction)"
    echo "  pnl_by_day             Daily P&L breakdown"
    echo "  regime_breakdown       WR by regime"
    echo "  streak_analysis        Current/longest streaks"
    echo "  judge_performance      XGBoost judge accuracy"
    echo "  daily_regime           Today's regime classification"
    echo "  order_summary          Recent orders and fills"
    echo "  fill_diagnostics       Fill rate analysis"
    echo "  lab_performance        Strategy Lab results (WR, P&L per strategy)"
    echo "  lab_param_sweep        1D parameter bucketing (WR by any metadata param)"
    echo "  lab_param_matrix       2D cross-tab (interaction effects)"
    echo "  query                  Raw SQL (read-only) against any pipeline DB"
    echo ""
    echo "=== Key Architecture Rules ==="
    echo ""
    echo "  - MCP is source of truth for pipeline data. Never ad-hoc SQL."
    echo "  - Always scope DB operations by entity (symbol, pipeline)."
    echo "  - Check timestamps before acting on aggregate metrics."
    echo "  - Strategy Lab: always-fire, log everything, optimize post-hoc."
    echo "  - 200-bet gate before graduation. Min 30-50 per bucket for sweeps."
    echo "  - One change at a time. Stagger optimizations."
    ;;

  *)
    echo "BOTSY Cheat Sheet"
    echo "Usage: ./tools/cheatsheet.sh [command]"
    echo ""
    echo "  wr        Win rate (7d)"
    echo "  today     Today's predictions"
    echo "  pnl       P&L by day (14d)"
    echo "  overview  All pipelines summary"
    echo "  judge     Judge shadow verdicts"
    echo "  regime    WR by regime"
    echo "  orders    Recent orders"
    echo "  streaks   Current streak"
    echo "  lab       Strategy Lab performance"
    echo "  lab-pending  Lab pending predictions"
    echo "  skills    Skills, hooks, MCP tools, architecture rules"
    ;;
esac
