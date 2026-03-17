"""
backtest.py — Replay historical BTC 5-minute candles through the prediction pipeline.

Downloads candles from Binance, constructs synthetic markets, runs agents via Claude API,
and reports accuracy + P&L against known outcomes. Results stored in a separate SQLite DB
so live data is never polluted.

Usage:
    python src/backtest.py --start-date 2026-03-01 --end-date 2026-03-15 --sample-rate 3
    python src/backtest.py --start-date 2026-03-14 --end-date 2026-03-14 --dry-run
    python src/backtest.py --start-date 2026-03-01 --end-date 2026-03-15 --max-candles 200
"""

import argparse
import json
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic
import requests

# Reuse existing modules
sys.path.insert(0, str(Path(__file__).parent))
from btc_data import _compute_summary, format_for_prompt
from predict import load_agent_prompts, MODEL
from conviction import load_macro_bias, compute_conviction, format_macro_for_prompt

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
DEFAULT_DB = Path(__file__).parent.parent / "data" / "backtest.db"
CONTEXT_WINDOW = 12  # number of prior candles agents see


# ---------------------------------------------------------------------------
# Historical data
# ---------------------------------------------------------------------------

def fetch_historical_candles(start_dt, end_dt, interval="5m"):
    """Download historical BTC 5-min candles from Binance (paginated)."""
    candles = []
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    print(f"Downloading candles from {start_dt.date()} to {end_dt.date()} ...")
    page = 0
    while start_ms < end_ms:
        resp = requests.get(BINANCE_KLINES, params={
            "symbol": "BTCUSDT",
            "interval": interval,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 1000,
        }, timeout=15)
        resp.raise_for_status()
        raw = resp.json()
        if not raw:
            break

        for k in raw:
            open_price = float(k[1])
            high = float(k[2])
            low = float(k[3])
            close = float(k[4])
            volume = float(k[5])
            open_time_ms = k[0]
            close_time_ms = k[6]
            open_time = datetime.fromtimestamp(open_time_ms / 1000, tz=timezone.utc)
            close_time = datetime.fromtimestamp(close_time_ms / 1000, tz=timezone.utc)

            body = abs(close - open_price)
            full_range = high - low
            direction = "UP" if close >= open_price else "DOWN"
            wick_ratio = round(1.0 - (body / full_range), 2) if full_range > 0 else 0.0
            body_pct = round((close - open_price) / open_price * 100, 4) if open_price > 0 else 0.0

            candles.append({
                "time": open_time.strftime("%H:%M"),
                "time_full": open_time,
                "close_time_full": close_time,
                "open_time_ms": open_time_ms,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": round(volume, 2),
                "direction": direction,
                "body_pct": body_pct,
                "wick_ratio": wick_ratio,
            })

        # Advance past last candle
        start_ms = raw[-1][6] + 1  # close_time_ms + 1
        page += 1
        if page % 5 == 0:
            print(f"  ... {len(candles)} candles downloaded")
        time.sleep(0.5)  # polite to Binance API

    print(f"  Total: {len(candles)} candles")
    return candles


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def init_backtest_db(db_path):
    """Create backtest DB with same schema as live system (v2: includes conviction_score)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            id TEXT PRIMARY KEY,
            question TEXT,
            category TEXT,
            end_date TEXT,
            volume REAL,
            price_yes REAL,
            price_no REAL,
            fetched_at TEXT,
            resolved INTEGER DEFAULT 0,
            outcome INTEGER DEFAULT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT,
            agent TEXT,
            estimate REAL,
            edge REAL,
            confidence TEXT,
            reasoning TEXT,
            predicted_at TEXT,
            cycle INTEGER,
            conviction_score INTEGER,
            FOREIGN KEY (market_id) REFERENCES markets(id)
        )
    """)
    # Add conviction_score column if upgrading from v1 DB
    try:
        db.execute("ALTER TABLE predictions ADD COLUMN conviction_score INTEGER")
    except sqlite3.OperationalError:
        pass
    db.commit()
    return db


def market_already_predicted(db, market_id, agent_name):
    """Check if this agent already predicted this market (for resumability)."""
    row = db.execute(
        "SELECT COUNT(*) FROM predictions WHERE market_id = ? AND agent = ?",
        (market_id, agent_name)
    ).fetchone()
    return row[0] > 0


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------

def build_backtest_context(market, btc_context, historical_time, macro_context=""):
    """Same as predict.build_market_context but with historical UTC time. v2: includes macro context."""
    from predict import build_market_context
    return build_market_context(market, macro_context, btc_context, current_time=historical_time)


def build_synthetic_market(candle, context_candles, fixed_price=None):
    """Build a market dict from a historical candle."""
    if fixed_price is not None:
        price_yes = fixed_price
    else:
        # Derive from trailing window: fraction of UP candles
        ups = sum(1 for c in context_candles if c["direction"] == "UP")
        price_yes = max(0.01, min(0.99, ups / len(context_candles)))

    outcome = 1 if candle["close"] >= candle["open"] else 0
    time_str = candle["time_full"].strftime("%Y-%m-%d %H:%M UTC")

    return {
        "id": f"backtest_{candle['open_time_ms']}",
        "question": f"Will BTC close UP or DOWN for the 5-min candle at {time_str}?",
        "end_date": candle["close_time_full"].isoformat(),
        "price_yes": round(price_yes, 3),
        "price_no": round(1.0 - price_yes, 3),
        "category": "crypto",
        "volume": 0,
        "outcome": outcome,
    }


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

def call_agent(client, agent_name, agent_prompt, market_context):
    """Call Claude API for one agent prediction. Returns parsed dict or None."""
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=agent_prompt,
            messages=[{"role": "user", "content": market_context}],
        )
        text = response.content[0].text.strip()
        # Extract JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception as e:
        print(f"      {agent_name} ERROR: {e}")
        return None


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def is_correct(estimate, outcome):
    return (estimate >= 0.5 and outcome == 1) or (estimate < 0.5 and outcome == 0)


def print_summary(db):
    """Print backtest results summary. v2: includes conviction tiers and weighted ensemble."""
    rows = db.execute("""
        SELECT p.agent, p.estimate, p.confidence, p.conviction_score, p.market_id, m.outcome, m.price_yes
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE m.resolved = 1
        ORDER BY p.predicted_at ASC
    """).fetchall()

    if not rows:
        print("\nNo predictions to report.")
        return

    # Per-agent stats
    agents = defaultdict(lambda: {
        "wins": 0, "losses": 0, "total": 0,
        "brier_sum": 0.0, "pnl": 0.0, "wagered": 0.0,
    })
    confidence_multiplier = {"low": 0.5, "medium": 1.0, "high": 2.0}
    unit_bet = 100

    for row in rows:
        agent = row["agent"]
        est = row["estimate"]
        outcome = row["outcome"]
        price_yes = row["price_yes"]
        conf = (row["confidence"] or "low").lower()
        a = agents[agent]

        a["total"] += 1
        a["brier_sum"] += (est - outcome) ** 2

        correct = is_correct(est, outcome)
        if correct:
            a["wins"] += 1
        else:
            a["losses"] += 1

        # P&L
        multiplier = confidence_multiplier.get(conf, 0.5)
        bet_size = unit_bet * multiplier
        a["wagered"] += bet_size

        if est >= 0.5:
            if 0 < price_yes < 1:
                a["pnl"] += bet_size * (1.0 / price_yes - 1.0) if outcome == 1 else -bet_size
        else:
            price_no = 1.0 - price_yes
            if 0 < price_no < 1:
                a["pnl"] += bet_size * (1.0 / price_no - 1.0) if outcome == 0 else -bet_size

    # Weighted ensemble + conviction tier breakdown
    market_preds = defaultdict(list)  # market_id -> list of (agent, estimate, confidence)
    market_outcomes = {}
    market_prices = {}
    market_conviction = {}

    for row in rows:
        market_preds[row["market_id"]].append({
            "agent": row["agent"],
            "estimate": row["estimate"],
            "confidence": row["confidence"] or "low",
        })
        market_outcomes[row["market_id"]] = row["outcome"]
        market_prices[row["market_id"]] = row["price_yes"]
        if row["conviction_score"] is not None:
            market_conviction[row["market_id"]] = row["conviction_score"]

    # Conviction tier mapping
    def score_to_tier(score):
        if score is None:
            return "UNKNOWN"
        if score <= 1:
            return "NO_BET"
        elif score == 2:
            return "LOW"
        elif score == 3:
            return "MEDIUM"
        else:
            return "HIGH"

    bet_sizes = {"NO_BET": 0, "LOW": 0, "MEDIUM": 75, "HIGH": 200}

    # Weighted ensemble (2-agent: contrarian leads)
    weights = {"contrarian": 0.55, "volume_wick": 0.45}
    ensemble_wins = 0
    ensemble_total = 0
    ensemble_pnl = 0.0
    ensemble_wagered = 0.0

    # By-tier stats
    tier_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "total": 0, "pnl": 0.0, "wagered": 0.0})

    for mid, preds in market_preds.items():
        if not preds:
            continue
        outcome = market_outcomes[mid]
        price_yes = market_prices[mid]
        conv_score = market_conviction.get(mid)
        tier = score_to_tier(conv_score)

        # Weighted ensemble estimate
        total_w = 0
        weighted_sum = 0
        for p in preds:
            w = weights.get(p["agent"], 1.0 / len(preds))
            weighted_sum += w * p["estimate"]
            total_w += w
        ens_est = weighted_sum / total_w if total_w > 0 else 0.5

        ensemble_total += 1
        correct = is_correct(ens_est, outcome)
        if correct:
            ensemble_wins += 1

        # Conviction-based bet sizing
        bet_size = bet_sizes.get(tier, 0)
        if bet_size > 0:
            ensemble_wagered += bet_size
            if ens_est >= 0.5:
                if 0 < price_yes < 1:
                    ensemble_pnl += bet_size * (1.0 / price_yes - 1.0) if outcome == 1 else -bet_size
            else:
                price_no = 1.0 - price_yes
                if 0 < price_no < 1:
                    ensemble_pnl += bet_size * (1.0 / price_no - 1.0) if outcome == 0 else -bet_size

        # Tier stats
        ts = tier_stats[tier]
        ts["total"] += 1
        if correct:
            ts["wins"] += 1
        else:
            ts["losses"] += 1
        if bet_size > 0:
            ts["wagered"] += bet_size
            if ens_est >= 0.5:
                if 0 < price_yes < 1:
                    ts["pnl"] += bet_size * (1.0 / price_yes - 1.0) if outcome == 1 else -bet_size
            else:
                price_no = 1.0 - price_yes
                if 0 < price_no < 1:
                    ts["pnl"] += bet_size * (1.0 / price_no - 1.0) if outcome == 0 else -bet_size

    # Print report
    total_markets = db.execute("SELECT COUNT(*) FROM markets WHERE resolved = 1").fetchone()[0]
    total_preds = sum(a["total"] for a in agents.values())

    print("\n" + "=" * 70)
    print("  BACKTEST RESULTS (v2)")
    print("=" * 70)
    print(f"  Markets: {total_markets}  |  Predictions: {total_preds}  |  Agents: {len(agents)}")
    print("-" * 70)

    # Per-agent table
    print(f"\n  {'Agent':<20s} {'Acc%':>6s} {'W':>4s} {'L':>4s} {'Brier':>7s} {'P&L':>10s} {'ROI':>7s}")
    print(f"  {'-'*20} {'-'*6} {'-'*4} {'-'*4} {'-'*7} {'-'*10} {'-'*7}")
    for agent_name in sorted(agents.keys()):
        a = agents[agent_name]
        acc = a["wins"] / a["total"] * 100 if a["total"] > 0 else 0
        brier = a["brier_sum"] / a["total"] if a["total"] > 0 else 0
        roi = a["pnl"] / a["wagered"] * 100 if a["wagered"] > 0 else 0
        pnl_str = f"${a['pnl']:+,.0f}"
        print(f"  {agent_name:<20s} {acc:>5.1f}% {a['wins']:>4d} {a['losses']:>4d} {brier:>7.4f} {pnl_str:>10s} {roi:>+6.0f}%")

    # Weighted ensemble
    if ensemble_total > 0:
        ens_acc = ensemble_wins / ensemble_total * 100
        ens_roi = ensemble_pnl / ensemble_wagered * 100 if ensemble_wagered > 0 else 0
        print(f"\n  {'ENSEMBLE (weighted)':<20s} {ens_acc:>5.1f}% {ensemble_wins:>4d} {ensemble_total - ensemble_wins:>4d} {'':>7s} ${ensemble_pnl:>+9,.0f} {ens_roi:>+6.0f}%")

    # Conviction tier breakdown
    print(f"\n  CONVICTION BREAKDOWN")
    print(f"  {'Tier':<12s} {'Count':>6s} {'Acc%':>6s} {'W':>4s} {'L':>4s} {'P&L':>10s} {'ROI':>7s}")
    print(f"  {'-'*12} {'-'*6} {'-'*6} {'-'*4} {'-'*4} {'-'*10} {'-'*7}")
    for tier in ["HIGH", "MEDIUM", "LOW", "NO_BET", "UNKNOWN"]:
        ts = tier_stats.get(tier)
        if ts is None or ts["total"] == 0:
            continue
        acc = ts["wins"] / ts["total"] * 100 if ts["total"] > 0 else 0
        roi = ts["pnl"] / ts["wagered"] * 100 if ts["wagered"] > 0 else 0
        pnl_str = f"${ts['pnl']:+,.0f}" if ts["wagered"] > 0 else "—"
        roi_str = f"{roi:>+6.0f}%" if ts["wagered"] > 0 else "—"
        print(f"  {tier:<12s} {ts['total']:>6d} {acc:>5.1f}% {ts['wins']:>4d} {ts['losses']:>4d} {pnl_str:>10s} {roi_str:>7s}")

    # Coin flip baseline
    print(f"\n  {'Coin Flip':<20s} {'50.0%':>6s} {'':>4s} {'':>4s} {'0.2500':>7s} {'$0':>10s} {'0%':>7s}")
    print("=" * 70)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_backtest(args):
    start_dt = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt = datetime.strptime(args.end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    db_path = Path(args.db_path)
    fixed_price = args.fixed_price

    # 1. Download historical candles
    candles = fetch_historical_candles(start_dt, end_dt)
    if len(candles) < CONTEXT_WINDOW + 1:
        print(f"Not enough candles ({len(candles)}). Need at least {CONTEXT_WINDOW + 1}.")
        return

    predictable = len(candles) - CONTEXT_WINDOW
    sampled = list(range(CONTEXT_WINDOW, len(candles), args.sample_rate))
    if args.max_candles and len(sampled) > args.max_candles:
        sampled = sampled[:args.max_candles]

    # Determine which agents to run
    all_agents = load_agent_prompts()
    if args.agents:
        agent_names = [a.strip() for a in args.agents.split(",")]
        agents = {k: v for k, v in all_agents.items() if k in agent_names}
        if not agents:
            print(f"No matching agents found. Available: {list(all_agents.keys())}")
            return
    else:
        agents = all_agents

    est_calls = len(sampled) * len(agents)
    est_cost = est_calls * 0.005

    print(f"\n  Candles available: {len(candles)} ({predictable} predictable)")
    print(f"  Sample rate: every {args.sample_rate} candle(s)")
    print(f"  Candles to predict: {len(sampled)}")
    print(f"  Agents: {list(agents.keys())}")
    print(f"  API calls: {est_calls} (est. ${est_cost:.2f})")
    print(f"  DB: {db_path}")

    if args.dry_run:
        print("\n  [DRY RUN] No API calls made. Exiting.")
        # Print some candle stats
        ups = sum(1 for c in candles[CONTEXT_WINDOW:] if c["direction"] == "UP")
        downs = len(candles) - CONTEXT_WINDOW - ups
        print(f"  UP candles: {ups} ({ups/(ups+downs)*100:.1f}%)")
        print(f"  DOWN candles: {downs} ({downs/(ups+downs)*100:.1f}%)")
        return

    # 2. Initialize DB
    db = init_backtest_db(db_path)

    # Check resumability
    existing = db.execute("SELECT COUNT(DISTINCT market_id) FROM predictions").fetchone()[0]
    if existing > 0:
        print(f"\n  Resuming: {existing} markets already predicted. Skipping those.")

    # 3. Create Anthropic client
    client = anthropic.Anthropic()

    # 4. Load macro bias and compute rolling bias for v2 context
    macro_bias = load_macro_bias()
    print(f"  Macro: {macro_bias['regime']} | Bias: {macro_bias['bias']} | Prior: {macro_bias['prior']:.2f}")

    # For backtest, compute rolling bias once (approximate — uses current data, not historical)
    rolling_bias = None
    try:
        from btc_data import compute_rolling_bias
        rolling_bias = compute_rolling_bias()
        blended = rolling_bias.get("blended", 0.5)
        print(f"  Computed bias: {blended*100:.1f}% UP (blended)")
    except Exception as e:
        print(f"  Rolling bias unavailable: {e}")

    macro_context = format_macro_for_prompt(macro_bias, rolling_bias)

    # 5. Main loop
    completed = 0
    skipped = 0
    errors = 0
    running_correct = 0
    running_total = 0
    tier_counts = defaultdict(int)

    print(f"\n  Starting backtest...\n")

    try:
        for idx, i in enumerate(sampled):
            target = candles[i]
            context = candles[i - CONTEXT_WINDOW : i]
            market = build_synthetic_market(target, context, fixed_price)
            market_id = market["id"]

            # Insert market (pre-resolved)
            db.execute("""
                INSERT OR IGNORE INTO markets (id, question, category, end_date, volume, price_yes, price_no, fetched_at, resolved, outcome)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                market_id, market["question"], market["category"], market["end_date"],
                market["volume"], market["price_yes"], market["price_no"],
                target["time_full"].isoformat(), market["outcome"]
            ))
            db.commit()

            # Build context for agents (v2: includes macro context)
            clean_context = [{k: v for k, v in c.items() if k not in ("time_full", "close_time_full", "open_time_ms")} for c in context]
            btc_summary = _compute_summary(clean_context)
            btc_context_str = format_for_prompt(btc_summary)

            market_context = build_backtest_context(market, btc_context_str, target["time_full"], macro_context)

            all_skipped = True
            agent_results = []
            cycle_predictions = []
            for agent_name, agent_prompt in agents.items():
                if market_already_predicted(db, market_id, agent_name):
                    skipped += 1
                    continue

                all_skipped = False
                prediction = call_agent(client, agent_name, agent_prompt, market_context)
                if prediction is None:
                    errors += 1
                    continue

                prediction["agent"] = agent_name
                prediction["market_id"] = market_id
                est = prediction.get("estimate", 0.5)
                edge = prediction.get("edge", 0)
                conf = prediction.get("confidence", "low")

                cycle_predictions.append(prediction)
                correct = is_correct(est, market["outcome"])
                agent_results.append((agent_name, est, conf, correct))

            # Compute conviction from all agent predictions for this market
            conv = None
            if cycle_predictions:
                conv = compute_conviction(cycle_predictions, macro_bias, rolling_bias)
                tier_counts[conv["tier"]] += 1

            # Store all predictions with conviction score
            for prediction in cycle_predictions:
                est = prediction.get("estimate", 0.5)
                edge = prediction.get("edge", 0)
                conf = prediction.get("confidence", "low")
                conviction_score = conv["score"] if conv else None

                db.execute("""
                    INSERT INTO predictions (market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle, conviction_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    market_id, prediction["agent"], est, edge, conf,
                    json.dumps(prediction), target["time_full"].isoformat(), idx + 1,
                    conviction_score
                ))
                db.commit()

            if not all_skipped:
                completed += 1
                outcome_label = "UP" if market["outcome"] == 1 else "DOWN"
                hits = sum(1 for _, _, _, c in agent_results if c)
                running_correct += hits
                running_total += len(agent_results)
                running_acc = running_correct / running_total * 100 if running_total > 0 else 0

                result_str = " | ".join(
                    f"{n}:{e:.0%}{'✓' if c else '✗'}" for n, e, _, c in agent_results
                )
                tier_label = f" [{conv['tier']}({conv['score']})]" if conv else ""
                progress = f"[{completed}/{len(sampled)}]"
                print(f"  {progress:>10s}  {target['time_full'].strftime('%m-%d %H:%M')}  {outcome_label}  {result_str}{tier_label}  (acc: {running_acc:.0f}%)")

    except KeyboardInterrupt:
        print(f"\n\n  Interrupted! {completed} candles completed, DB is safe to resume.\n")

    # 5. Print summary
    print_summary(db)
    db.close()
    print(f"\n  Results saved to: {db_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest BTC 5-min prediction agents against historical data")
    parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--sample-rate", type=int, default=1, help="Predict every Nth candle (default: 1)")
    parser.add_argument("--max-candles", type=int, default=None, help="Max number of candles to predict")
    parser.add_argument("--db-path", default=str(DEFAULT_DB), help="Output database path")
    parser.add_argument("--fixed-price", type=float, default=None, help="Fixed market price_yes (e.g. 0.50)")
    parser.add_argument("--agents", default=None, help="Comma-separated agent names to run (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Download candles only, no API calls")
    args = parser.parse_args()
    run_backtest(args)
