"""
backtest_native.py — Backtest V4 momentum signal against historical Polymarket markets.

Pure Polymarket data — no external candle sources. The sequence of resolved
"Bitcoin Up or Down" market outcomes IS the streak signal.

Usage:
    # Fetch and backtest last 7 days of 5m markets
    python3 src/backtest_native.py --days 7

    # Fetch last 30 days, 15m markets
    python3 src/backtest_native.py --days 30 --window 15m

    # Fetch a specific date range
    python3 src/backtest_native.py --start 2026-03-01 --end 2026-03-28

    # Just fetch markets (no replay)
    python3 src/backtest_native.py --days 14 --fetch-only

    # Replay against already-fetched data
    python3 src/backtest_native.py --replay-only
"""

import json
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

GAMMA_API = "https://gamma-api.polymarket.com"
DB_PATH = Path(__file__).parent.parent / "data" / "backtest.db"

# Conviction tier → bet size (must match live pipeline)
CONVICTION_BETS = {0: 0, 1: 0, 2: 0, 3: 75, 4: 200, 5: 300}

# Regex to capture time range in market titles
TIME_RANGE_RE = re.compile(r"(\d{1,2}:\d{2}[AP]M)\s*-\s*(\d{1,2}:\d{2}[AP]M)")


# ── Database ──────────────────────────────────────────────────────────

def init_db(db_path=None):
    """Initialize the backtest database."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            id TEXT PRIMARY KEY,
            question TEXT,
            end_date TEXT,
            volume REAL,
            price_yes REAL,
            outcome INTEGER,
            window TEXT DEFAULT '5m'
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS backtest_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT,
            predicted_direction TEXT,
            actual_outcome INTEGER,
            correct INTEGER,
            conviction INTEGER,
            bet_size REAL,
            pnl REAL,
            price_yes REAL,
            streak_length INTEGER,
            streak_direction TEXT,
            has_exhaustion INTEGER,
            exhaustion_type TEXT,
            regime TEXT,
            FOREIGN KEY (market_id) REFERENCES markets(id)
        )
    """)
    db.commit()
    return db


# ── Fetch historical resolved markets ────────────────────────────────

def _parse_window(title):
    """Return window duration in seconds, or None if not parseable."""
    match = TIME_RANGE_RE.search(title)
    if not match:
        return None
    try:
        t1 = datetime.strptime(match.group(1), "%I:%M%p")
        t2 = datetime.strptime(match.group(2), "%I:%M%p")
        diff = (t2 - t1).total_seconds()
        if diff < 0:
            diff += 12 * 3600
        return diff
    except ValueError:
        return None


def fetch_resolved_markets(start_date, end_date, window="5m", db=None):
    """
    Fetch resolved "Bitcoin Up or Down" markets from Gamma API.
    Paginates through all results in the date range.
    """
    target_seconds = 300 if window == "5m" else 900
    offset = 0
    limit = 500  # Max allowed by Gamma API
    total_fetched = 0
    all_markets = []

    print(f"Fetching resolved {window} markets from {start_date} to {end_date}...")

    while True:
        params = {
            "limit": limit,
            "offset": offset,
            "order": "endDate",
            "ascending": "true",
            "closed": "true",
            "end_date_min": f"{start_date}T00:00:00Z",
            "end_date_max": f"{end_date}T23:59:59Z",
        }

        try:
            resp = requests.get(f"{GAMMA_API}/markets", params=params, timeout=30)
            resp.raise_for_status()
            markets = resp.json()
        except Exception as e:
            print(f"  API error at offset {offset}: {e}")
            break

        if not markets:
            break

        batch_count = 0
        for m in markets:
            question = m.get("question", "")
            if "Bitcoin" not in question or "Up or Down" not in question:
                continue

            # Check window size
            window_secs = _parse_window(question)
            if window_secs != target_seconds:
                continue

            # Must be resolved with outcome prices
            raw_prices = m.get("outcomePrices", "")
            if not raw_prices:
                continue
            try:
                if isinstance(raw_prices, str):
                    prices = json.loads(raw_prices)
                else:
                    prices = raw_prices
                price_up = float(prices[0])
            except (json.JSONDecodeError, ValueError, IndexError):
                continue

            # Determine outcome: price snaps to 0 or 1 on resolution
            if price_up > 0.9:
                outcome = 1  # UP won
            elif price_up < 0.1:
                outcome = 0  # DOWN won
            else:
                continue  # Not fully resolved

            # NOTE: lastTradePrice is the POST-resolution price (0.01 or 0.99),
            # not the pre-resolution entry price. The Gamma API doesn't expose
            # historical mid-market prices. We store 0.50 as a neutral default
            # for P&L estimation (assumes fair-value entry). The backtest's
            # primary metric is WIN RATE (signal accuracy), not P&L.
            volume = float(m.get("volume", 0) or 0)
            end_date_val = m.get("endDate") or m.get("end_date_iso", "")

            market_data = {
                "id": m["id"],
                "question": question,
                "end_date": end_date_val,
                "volume": volume,
                "price_yes": 0.50,  # Fair-value assumption (no pre-resolution price available)
                "outcome": outcome,
                "window": window,
            }
            all_markets.append(market_data)
            batch_count += 1

        total_fetched += len(markets)
        print(f"  Fetched {total_fetched} total, {len(all_markets)} BTC {window} markets so far...")

        if len(markets) < limit:
            break

        offset += limit
        time.sleep(0.05)  # Gentle rate limiting

    # Store in DB
    if db:
        for m in all_markets:
            db.execute("""
                INSERT OR IGNORE INTO markets (id, question, end_date, volume, price_yes, outcome, window)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (m["id"], m["question"], m["end_date"], m["volume"],
                  m["price_yes"], m["outcome"], m["window"]))
        db.commit()

    print(f"  Total: {len(all_markets)} resolved BTC {window} markets")
    return all_markets


# ── Native momentum signal (Polymarket-only) ─────────────────────────

def native_momentum_signal(outcomes, volumes, prices, min_streak=3):
    """
    Momentum signal using only Polymarket market sequence data.

    outcomes: list of recent outcomes (1=UP, 0=DOWN), most recent last
    volumes: list of market volumes, aligned with outcomes
    prices: list of price_yes values, aligned with outcomes

    Returns signal dict matching the live signal format.
    """
    if len(outcomes) < min_streak + 2:
        return {"should_trade": False, "reason": "insufficient_history",
                "estimate": 0.5, "direction": None, "streak": 0}

    # Count consecutive streak from the end
    last_dir = "UP" if outcomes[-1] == 1 else "DOWN"
    streak = 1
    for i in range(len(outcomes) - 2, -1, -1):
        d = "UP" if outcomes[i] == 1 else "DOWN"
        if d == last_dir:
            streak += 1
        else:
            break

    signed_streak = streak if last_dir == "UP" else -streak

    if abs(signed_streak) < min_streak:
        return {"should_trade": False, "reason": f"streak_too_short ({signed_streak})",
                "estimate": 0.5, "direction": None, "streak": signed_streak}

    # Native exhaustion signals (Polymarket data only)
    exhaustion_types = []

    # 1. Volume spike: last market volume > 1.8x average of recent markets
    if len(volumes) >= 5:
        avg_vol = sum(volumes[-5:]) / 5
        if avg_vol > 0 and volumes[-1] / avg_vol > 1.8:
            exhaustion_types.append("volume_spike")

    # 2. Price compression: last 3 markets' price_yes converging toward 0.50
    #    (market uncertainty increasing = exhaustion of the trend's conviction)
    if len(prices) >= 3:
        dist_from_50 = [abs(p - 0.5) for p in prices[-3:]]
        if dist_from_50[0] > dist_from_50[1] > dist_from_50[2]:
            exhaustion_types.append("price_compression")

    # 3. Volume decline: last 3 markets show declining volume
    #    (participation fading = trend losing steam, but may continue one more)
    if len(volumes) >= 3:
        if volumes[-3] > volumes[-2] > volumes[-1] and volumes[-1] > 0:
            exhaustion_types.append("volume_decline")

    has_exhaustion = len(exhaustion_types) > 0

    if not has_exhaustion:
        return {"should_trade": False, "reason": f"no_exhaustion (streak={signed_streak})",
                "estimate": 0.5, "direction": None, "streak": signed_streak,
                "exhaustion_types": []}

    # RIDE the streak (momentum)
    if signed_streak >= min_streak:
        estimate = 0.62
        direction = "UP"
    else:
        estimate = 0.38
        direction = "DOWN"

    confidence = "medium"
    if abs(signed_streak) >= 5:
        confidence = "high"
    if len(exhaustion_types) >= 2:
        confidence = "high"

    return {
        "should_trade": True,
        "estimate": estimate,
        "direction": direction,
        "confidence": confidence,
        "streak": signed_streak,
        "exhaustion_types": exhaustion_types,
        "reason": f"ride_streak_{direction}",
    }


# ── Regime detection (from outcome sequence) ─────────────────────────

def native_regime(outcomes, autocorr_threshold=-0.15):
    """
    Compute regime from sequence of market outcomes.
    Uses autocorrelation of the outcome sequence (1=UP, 0=DOWN).
    """
    if len(outcomes) < 10:
        return {"label": "UNKNOWN", "is_mean_reverting": False, "autocorrelation": 0.0}

    # Convert to returns-like: +1 for UP, -1 for DOWN
    series = [1 if o == 1 else -1 for o in outcomes]
    n = len(series)
    mean = sum(series) / n
    var = sum((s - mean) ** 2 for s in series) / n

    if var == 0:
        return {"label": "LOW_VOL / NEUTRAL", "is_mean_reverting": False, "autocorrelation": 0.0}

    # Lag-1 autocorrelation
    cov = sum((series[i] - mean) * (series[i-1] - mean) for i in range(1, n)) / (n - 1)
    autocorr = cov / var

    # Volatility proxy: how often does direction flip?
    flips = sum(1 for i in range(1, n) if series[i] != series[i-1])
    flip_rate = flips / (n - 1)

    if flip_rate > 0.6:
        vol_label = "HIGH_VOL"
    elif flip_rate > 0.4:
        vol_label = "MEDIUM_VOL"
    else:
        vol_label = "LOW_VOL"

    if autocorr > 0.15:
        trend_label = "TRENDING"
    elif autocorr < autocorr_threshold:
        trend_label = "MEAN_REVERTING"
    else:
        trend_label = "NEUTRAL"

    return {
        "label": f"{vol_label} / {trend_label}",
        "is_mean_reverting": autocorr < autocorr_threshold,
        "autocorrelation": round(autocorr, 4),
        "flip_rate": round(flip_rate, 4),
    }


# ── Replay engine ────────────────────────────────────────────────────

def replay(db, window="5m", min_streak=3, autocorr_threshold=-0.15, lookback=20):
    """
    Replay the momentum signal against all fetched resolved markets.
    Uses a sliding window of recent outcomes as context.
    """
    rows = db.execute("""
        SELECT id, end_date, volume, price_yes, outcome
        FROM markets
        WHERE window = ? AND outcome IS NOT NULL
        ORDER BY end_date ASC
    """, (window,)).fetchall()

    if not rows:
        print("No markets to replay.")
        return

    print(f"\nReplaying {len(rows)} resolved {window} markets (lookback={lookback}, min_streak={min_streak})...")

    # Clear previous results for this window
    db.execute("DELETE FROM backtest_results WHERE market_id IN (SELECT id FROM markets WHERE window = ?)", (window,))
    db.commit()

    outcomes_window = []
    volumes_window = []
    prices_window = []

    total = 0
    bets = 0
    wins = 0
    total_pnl = 0.0
    total_wagered = 0.0
    skips_no_signal = 0
    skips_regime = 0
    skips_price = 0

    for row in rows:
        market_id, end_date, volume, price_yes, outcome = row

        # We need at least lookback markets before we can predict
        if len(outcomes_window) < lookback:
            outcomes_window.append(outcome)
            volumes_window.append(volume)
            prices_window.append(price_yes)
            continue

        total += 1

        # Compute regime from recent outcomes
        regime = native_regime(outcomes_window[-lookback:], autocorr_threshold=autocorr_threshold)

        # Price gate — effectively disabled in backtest since we use 0.50
        # (pre-resolution prices not available from Gamma API)
        if price_yes > 0.85 or price_yes < 0.15:
            skips_price += 1
            outcomes_window.append(outcome)
            volumes_window.append(volume)
            prices_window.append(price_yes)
            continue

        # Regime gate
        if regime["is_mean_reverting"]:
            skips_regime += 1
            db.execute("""
                INSERT INTO backtest_results
                (market_id, predicted_direction, actual_outcome, correct, conviction, bet_size, pnl,
                 price_yes, streak_length, streak_direction, has_exhaustion, exhaustion_type, regime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (market_id, None, outcome, None, 0, 0, 0,
                  price_yes, 0, None, 0, "regime_skip", regime["label"]))
            outcomes_window.append(outcome)
            volumes_window.append(volume)
            prices_window.append(price_yes)
            continue

        # Compute signal
        signal = native_momentum_signal(
            outcomes_window[-lookback:],
            volumes_window[-lookback:],
            prices_window[-lookback:],
            min_streak=min_streak,
        )

        predicted_dir = signal.get("direction")
        streak = signal.get("streak", 0)
        exhaustion_types = signal.get("exhaustion_types", [])
        has_exhaustion = 1 if exhaustion_types else 0

        if signal["should_trade"]:
            # Determine conviction
            conviction = 3
            if predicted_dir == "UP" and 0.20 <= price_yes <= 0.70:
                conviction = 4

            bet_size = CONVICTION_BETS.get(conviction, 75)
            bets += 1

            # Evaluate
            correct = (predicted_dir == "UP" and outcome == 1) or \
                      (predicted_dir == "DOWN" and outcome == 0)

            # P&L
            if predicted_dir == "UP":
                pnl = bet_size * (1.0 / price_yes - 1.0) if outcome == 1 else -bet_size
            else:
                price_no = 1.0 - price_yes
                pnl = bet_size * (1.0 / price_no - 1.0) if outcome == 0 else -bet_size

            if correct:
                wins += 1
            total_pnl += pnl
            total_wagered += bet_size
        else:
            skips_no_signal += 1
            correct = None
            conviction = 0
            bet_size = 0
            pnl = 0

        db.execute("""
            INSERT INTO backtest_results
            (market_id, predicted_direction, actual_outcome, correct, conviction, bet_size, pnl,
             price_yes, streak_length, streak_direction, has_exhaustion, exhaustion_type, regime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (market_id, predicted_dir, outcome, 1 if correct else (0 if correct is not None else None),
              conviction, bet_size, round(pnl, 2),
              price_yes, abs(streak), "UP" if streak > 0 else ("DOWN" if streak < 0 else None),
              has_exhaustion, ",".join(exhaustion_types) if exhaustion_types else None,
              regime["label"]))

        # Slide window
        outcomes_window.append(outcome)
        volumes_window.append(volume)
        prices_window.append(price_yes)

    db.commit()

    # Report
    wr = (wins / bets * 100) if bets > 0 else 0
    roi = (total_pnl / total_wagered * 100) if total_wagered > 0 else 0

    print(f"\n{'='*60}")
    print(f"BACKTEST RESULTS — {window} (min_streak={min_streak})")
    print(f"{'='*60}")
    print(f"  Markets analyzed:  {total}")
    print(f"  Bets placed:       {bets} ({bets/total*100:.1f}% of markets)" if total > 0 else "")
    print(f"  Wins:              {wins}")
    print(f"  Win rate:          {wr:.1f}%")
    print(f"  P&L:               ${total_pnl:+,.2f}")
    print(f"  Wagered:           ${total_wagered:,.2f}")
    print(f"  ROI:               {roi:+.1f}%")
    print(f"\n  Skips:")
    print(f"    No signal:       {skips_no_signal}")
    print(f"    Regime gate:     {skips_regime}")
    print(f"    Price gate:      {skips_price}")

    # Breakdown by direction
    print(f"\n  Direction breakdown:")
    for direction in ["UP", "DOWN"]:
        d_rows = db.execute("""
            SELECT COUNT(*), SUM(correct), SUM(pnl)
            FROM backtest_results
            WHERE predicted_direction = ? AND conviction >= 3
        """, (direction,)).fetchone()
        if d_rows[0] > 0:
            d_wr = d_rows[1] / d_rows[0] * 100
            print(f"    {direction}: {d_rows[0]} bets, {d_wr:.1f}% WR, ${d_rows[2]:+,.2f} P&L")

    # Breakdown by regime
    print(f"\n  Regime breakdown:")
    regime_rows = db.execute("""
        SELECT regime, COUNT(*), SUM(CASE WHEN correct=1 THEN 1 ELSE 0 END), SUM(pnl)
        FROM backtest_results
        WHERE conviction >= 3
        GROUP BY regime
        ORDER BY COUNT(*) DESC
    """).fetchall()
    for r in regime_rows:
        r_wr = r[2] / r[1] * 100 if r[1] > 0 else 0
        print(f"    {r[0]}: {r[1]} bets, {r_wr:.1f}% WR, ${r[3]:+,.2f} P&L")

    # Breakdown by streak length
    print(f"\n  Streak length breakdown:")
    streak_rows = db.execute("""
        SELECT streak_length, COUNT(*), SUM(CASE WHEN correct=1 THEN 1 ELSE 0 END), SUM(pnl)
        FROM backtest_results
        WHERE conviction >= 3
        GROUP BY streak_length
        ORDER BY streak_length
    """).fetchall()
    for s in streak_rows:
        s_wr = s[2] / s[1] * 100 if s[1] > 0 else 0
        print(f"    streak={s[0]}: {s[1]} bets, {s_wr:.1f}% WR, ${s[3]:+,.2f} P&L")

    # Breakdown by exhaustion type
    print(f"\n  Exhaustion type breakdown:")
    ex_rows = db.execute("""
        SELECT exhaustion_type, COUNT(*), SUM(CASE WHEN correct=1 THEN 1 ELSE 0 END), SUM(pnl)
        FROM backtest_results
        WHERE conviction >= 3 AND exhaustion_type IS NOT NULL
        GROUP BY exhaustion_type
        ORDER BY COUNT(*) DESC
    """).fetchall()
    for e in ex_rows:
        e_wr = e[2] / e[1] * 100 if e[1] > 0 else 0
        print(f"    {e[0]}: {e[1]} bets, {e_wr:.1f}% WR, ${e[3]:+,.2f} P&L")

    return {
        "total": total, "bets": bets, "wins": wins, "wr": wr,
        "pnl": total_pnl, "wagered": total_wagered, "roi": roi,
    }


# ── CLI ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backtest V4 momentum against historical Polymarket data")
    parser.add_argument("--days", type=int, default=7, help="Days of history to fetch (default 7)")
    parser.add_argument("--start", type=str, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--window", type=str, default="5m", choices=["5m", "15m"], help="Market window")
    parser.add_argument("--min-streak", type=int, default=None, help="Override min streak (default: 3 for 5m, 2 for 15m)")
    parser.add_argument("--fetch-only", action="store_true", help="Only fetch markets, don't replay")
    parser.add_argument("--replay-only", action="store_true", help="Only replay, don't fetch")
    parser.add_argument("--db", type=str, default=None, help="Override DB path")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else DB_PATH
    db = init_db(db_path)

    # Date range
    if args.start and args.end:
        start_date = args.start
        end_date = args.end
    else:
        end_dt = datetime.now(timezone.utc) - timedelta(days=1)
        start_dt = end_dt - timedelta(days=args.days)
        start_date = start_dt.strftime("%Y-%m-%d")
        end_date = end_dt.strftime("%Y-%m-%d")

    # Default min_streak
    min_streak = args.min_streak
    if min_streak is None:
        min_streak = 2 if args.window == "15m" else 3

    # Fetch
    if not args.replay_only:
        fetch_resolved_markets(start_date, end_date, window=args.window, db=db)

    # Replay
    if not args.fetch_only:
        autocorr_threshold = -0.20 if args.window == "15m" else -0.15
        replay(db, window=args.window, min_streak=min_streak,
               autocorr_threshold=autocorr_threshold)

    db.close()
