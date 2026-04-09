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
    ;;
esac
