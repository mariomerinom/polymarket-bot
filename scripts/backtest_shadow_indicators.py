"""
Backtest shadow indicators against historical resolved predictions.

For each resolved bet, fetch the BTC candles at prediction time,
compute RSI(14), OBV slope, VWAP z-score, and correlate with outcomes.
"""

import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shadow_indicators import compute_rsi, compute_obv_slope, compute_vwap_zscore
from btc_data import fetch_btc_candles

DB_PATH = Path(__file__).parent.parent / "data" / "predictions.db"


def get_resolved_bets(db):
    """Get all resolved predictions with conviction >= 3."""
    rows = db.execute("""
        SELECT p.id, p.estimate, p.conviction_score, p.predicted_at, p.reasoning,
               p.regime, m.outcome, m.price_yes
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE m.resolved = 1 AND p.conviction_score >= 3
        ORDER BY p.predicted_at ASC
    """).fetchall()
    return rows


def determine_win(estimate, outcome):
    if estimate >= 0.5 and outcome == 1:
        return True
    if estimate < 0.5 and outcome == 0:
        return True
    return False


def main():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    bets = get_resolved_bets(db)
    db.close()

    print(f"Backtest Shadow Indicators — {len(bets)} resolved bets")
    print("=" * 60)

    # We can't fetch historical candles per-timestamp easily from Kraken
    # (would need exact Unix timestamps). Instead, fetch current candles ONCE
    # and use the reasoning JSON which may already contain candle context.
    #
    # Better approach: fetch candles once with a large lookback and compute
    # indicators on the current state. But for a TRUE historical backtest,
    # we need per-prediction candle snapshots.
    #
    # PRAGMATIC approach: Use the reasoning JSON which stores signal data
    # (streak, exhaustion, regime) at prediction time. We can extract
    # price context from there. For RSI/OBV/VWAP we need actual OHLCV —
    # let's check if any candle data is stored in reasoning.

    # First pass: check what data is available in reasoning
    has_candle_data = 0
    has_mkt_price = 0

    for bet in bets:
        try:
            reasoning = json.loads(bet["reasoning"]) if bet["reasoning"] else {}
        except (json.JSONDecodeError, TypeError):
            reasoning = {}
        if "mkt_price" in reasoning:
            has_mkt_price += 1

    print(f"Bets with mkt_price in reasoning: {has_mkt_price}/{len(bets)}")
    print()

    # Since we don't have stored candles per prediction, we'll do the next
    # best thing: fetch current candles and compute indicators to establish
    # the METHODOLOGY, then batch-fetch historical data.
    #
    # Actually, Kraken supports historical OHLC via the `since` parameter.
    # Let's batch by unique 5-minute windows.

    # Group predictions by their 5-minute window
    from collections import defaultdict
    windows = defaultdict(list)
    for bet in bets:
        # Round predicted_at to 5-minute window
        predicted_at = bet["predicted_at"]
        try:
            dt = datetime.fromisoformat(predicted_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            # Round down to 5-minute boundary
            minute = (dt.minute // 5) * 5
            window_key = dt.strftime(f"%Y-%m-%d %H:{minute:02d}")
        except (ValueError, AttributeError):
            window_key = predicted_at[:16]
        windows[window_key].append(bet)

    print(f"Unique 5-minute windows: {len(windows)}")
    print(f"Fetching historical candles from Kraken...")
    print()

    # Fetch candles for each unique window
    import requests

    results = []
    errors = 0

    # Sort windows chronologically
    sorted_windows = sorted(windows.keys())

    for i, window_key in enumerate(sorted_windows):
        window_bets = windows[window_key]

        # Parse window timestamp
        try:
            parts = window_key.split(" ")
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else "00:00"
            dt = datetime.fromisoformat(f"{date_part}T{time_part}:00+00:00")
        except (ValueError, IndexError):
            errors += 1
            continue

        # Fetch 30 candles ending at this time from Coinbase (supports date ranges)
        from datetime import timedelta
        start = dt - timedelta(minutes=30 * 5)
        end = dt

        try:
            resp = requests.get(
                "https://api.exchange.coinbase.com/products/BTC-USD/candles",
                params={
                    "granularity": 300,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                },
                timeout=10,
            )

            if resp.status_code != 200:
                errors += 1
                continue

            raw_candles = resp.json()
            if not isinstance(raw_candles, list) or not raw_candles:
                errors += 1
                continue

            # Coinbase returns [time, low, high, open, close, volume] in REVERSE order
            candles = []
            for c in sorted(raw_candles, key=lambda x: x[0]):
                candles.append({
                    "time": datetime.fromtimestamp(c[0], tz=timezone.utc).strftime("%H:%M"),
                    "open": float(c[3]),
                    "high": float(c[2]),
                    "low": float(c[1]),
                    "close": float(c[4]),
                    "volume": float(c[5]),
                })

            candles = candles[-30:]

            if len(candles) < 15:
                errors += 1
                continue

            # Compute indicators
            closes = [c["close"] for c in candles]
            rsi = compute_rsi(closes, period=14)
            obv = compute_obv_slope(candles, window=10)
            vwap = compute_vwap_zscore(candles)

            # Attach results to each bet in this window
            for bet in window_bets:
                won = determine_win(bet["estimate"], bet["outcome"])
                direction = "UP" if bet["estimate"] >= 0.5 else "DOWN"

                try:
                    reasoning = json.loads(bet["reasoning"]) if bet["reasoning"] else {}
                except (json.JSONDecodeError, TypeError):
                    reasoning = {}

                mkt_price = reasoning.get("mkt_price", bet["price_yes"])

                results.append({
                    "id": bet["id"],
                    "direction": direction,
                    "conviction": bet["conviction_score"],
                    "won": won,
                    "rsi": rsi,
                    "obv_slope": obv,
                    "vwap_zscore": vwap["zscore"],
                    "vwap_signal": vwap["signal"],
                    "mkt_price": mkt_price,
                    "regime": bet["regime"] or "",
                    "predicted_at": bet["predicted_at"],
                })

        except requests.RequestException:
            errors += 1
            continue

        # Rate limit: ~10 req/sec for Coinbase
        if (i + 1) % 10 == 0:
            time.sleep(1.2)

        # Progress
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(sorted_windows)} windows processed, {len(results)} results so far")

    print(f"\nProcessed: {len(results)} bets, {errors} errors")
    print()

    if not results:
        print("No results to analyze.")
        return

    # ── Analysis ──────────────────────────────────────────────────────────

    wins = [r for r in results if r["won"]]
    losses = [r for r in results if not r["won"]]
    total_wr = len(wins) / len(results) * 100

    print(f"Overall: {len(results)} bets, {len(wins)}W / {len(losses)}L = {total_wr:.1f}% WR")
    print()

    # ── RSI Analysis ──────────────────────────────────────────────────────
    print("=" * 60)
    print("RSI(14) ANALYSIS")
    print("=" * 60)

    avg_rsi_wins = sum(r["rsi"] for r in wins) / len(wins) if wins else 0
    avg_rsi_losses = sum(r["rsi"] for r in losses) / len(losses) if losses else 0
    print(f"Avg RSI on wins:   {avg_rsi_wins:.1f}")
    print(f"Avg RSI on losses: {avg_rsi_losses:.1f}")
    print(f"Separation:        {abs(avg_rsi_wins - avg_rsi_losses):.1f}pp")
    print()

    # RSI buckets
    rsi_buckets = [
        ("< 30 (oversold)", lambda r: r["rsi"] < 30),
        ("30-50", lambda r: 30 <= r["rsi"] < 50),
        ("50-70", lambda r: 50 <= r["rsi"] < 70),
        ("> 70 (overbought)", lambda r: r["rsi"] >= 70),
    ]

    print(f"{'RSI Bucket':<22} {'Bets':>5} {'Wins':>5} {'WR%':>7}")
    print("-" * 42)
    for label, filt in rsi_buckets:
        bucket = [r for r in results if filt(r)]
        if bucket:
            w = sum(1 for r in bucket if r["won"])
            wr = w / len(bucket) * 100
            print(f"{label:<22} {len(bucket):>5} {w:>5} {wr:>6.1f}%")
    print()

    # RSI × Direction
    print("RSI × Direction:")
    print(f"{'Condition':<35} {'Bets':>5} {'Wins':>5} {'WR%':>7}")
    print("-" * 55)
    for dir_label in ["UP", "DOWN"]:
        for rsi_label, filt in rsi_buckets:
            bucket = [r for r in results if filt(r) and r["direction"] == dir_label]
            if bucket:
                w = sum(1 for r in bucket if r["won"])
                wr = w / len(bucket) * 100
                marker = " ← SKIP?" if (
                    (dir_label == "UP" and "overbought" in rsi_label and wr < 55) or
                    (dir_label == "DOWN" and "oversold" in rsi_label and wr < 55)
                ) else ""
                print(f"  {dir_label} + RSI {rsi_label:<22} {len(bucket):>5} {w:>5} {wr:>6.1f}%{marker}")
    print()

    # ── OBV Analysis ──────────────────────────────────────────────────────
    print("=" * 60)
    print("OBV SLOPE ANALYSIS (0.50-0.70 bucket)")
    print("=" * 60)

    obv_bucket = [r for r in results if r["mkt_price"] and 0.50 <= r["mkt_price"] <= 0.70]
    if obv_bucket:
        obv_pos = [r for r in obv_bucket if r["obv_slope"] > 0]
        obv_neg = [r for r in obv_bucket if r["obv_slope"] < 0]
        obv_flat = [r for r in obv_bucket if r["obv_slope"] == 0]

        for label, group in [("Positive slope", obv_pos), ("Negative slope", obv_neg), ("Flat", obv_flat)]:
            if group:
                w = sum(1 for r in group if r["won"])
                wr = w / len(group) * 100
                print(f"{label}: {len(group)} bets, {w}W, {wr:.1f}% WR")

        print()
        # OBV agreement with direction
        print("OBV × Direction agreement (0.50-0.70 bucket):")
        print(f"{'Condition':<40} {'Bets':>5} {'Wins':>5} {'WR%':>7}")
        print("-" * 55)

        agree = [r for r in obv_bucket if
                 (r["direction"] == "UP" and r["obv_slope"] > 0) or
                 (r["direction"] == "DOWN" and r["obv_slope"] < 0)]
        disagree = [r for r in obv_bucket if
                    (r["direction"] == "UP" and r["obv_slope"] < 0) or
                    (r["direction"] == "DOWN" and r["obv_slope"] > 0)]

        for label, group in [("Direction agrees with OBV", agree), ("Direction contradicts OBV", disagree)]:
            if group:
                w = sum(1 for r in group if r["won"])
                wr = w / len(group) * 100
                print(f"  {label:<38} {len(group):>5} {w:>5} {wr:>6.1f}%")
    else:
        print("No bets in 0.50-0.70 price bucket.")
    print()

    # ── VWAP Analysis ─────────────────────────────────────────────────────
    print("=" * 60)
    print("VWAP Z-SCORE ANALYSIS")
    print("=" * 60)

    # VWAP on mean-reverting regime predictions
    mr_preds = [r for r in results if "MEAN_REVERTING" in r["regime"]]
    non_mr = [r for r in results if "MEAN_REVERTING" not in r["regime"]]

    print(f"Mean-reverting regime bets: {len(mr_preds)}")
    print(f"Non mean-reverting bets:    {len(non_mr)}")
    print()

    # VWAP z-score buckets (all bets)
    vwap_buckets = [
        ("z < -2 (strong UP signal)", lambda r: r["vwap_zscore"] < -2),
        ("-2 < z < -1", lambda r: -2 <= r["vwap_zscore"] < -1),
        ("-1 < z < 1 (near VWAP)", lambda r: -1 <= r["vwap_zscore"] <= 1),
        ("1 < z < 2", lambda r: 1 < r["vwap_zscore"] <= 2),
        ("z > 2 (strong DOWN signal)", lambda r: r["vwap_zscore"] > 2),
    ]

    print(f"{'VWAP Z-Score Bucket':<32} {'Bets':>5} {'Wins':>5} {'WR%':>7}")
    print("-" * 50)
    for label, filt in vwap_buckets:
        bucket = [r for r in results if filt(r)]
        if bucket:
            w = sum(1 for r in bucket if r["won"])
            wr = w / len(bucket) * 100
            print(f"{label:<32} {len(bucket):>5} {w:>5} {wr:>6.1f}%")
    print()

    # VWAP mean-reversion simulation: what if we traded AGAINST the deviation?
    print("VWAP Mean-Reversion Simulation (all regimes):")
    print("If z > 2 → bet DOWN, if z < -2 → bet UP:")
    vwap_trades = [r for r in results if abs(r["vwap_zscore"]) > 2]
    if vwap_trades:
        vwap_correct = 0
        for r in vwap_trades:
            # Mean reversion: z > 2 → expect DOWN, z < -2 → expect UP
            if r["vwap_zscore"] > 2 and r["won"] and r["direction"] == "DOWN":
                vwap_correct += 1
            elif r["vwap_zscore"] < -2 and r["won"] and r["direction"] == "UP":
                vwap_correct += 1
            elif r["vwap_zscore"] > 2 and not r["won"] and r["direction"] == "UP":
                vwap_correct += 1  # Would have been correct to fade
            elif r["vwap_zscore"] < -2 and not r["won"] and r["direction"] == "DOWN":
                vwap_correct += 1  # Would have been correct to fade

        print(f"  Trades with |z| > 2: {len(vwap_trades)}")
        print(f"  VWAP reversion correct: {vwap_correct}/{len(vwap_trades)} = {vwap_correct/len(vwap_trades)*100:.1f}%")
    else:
        print("  No trades with |z| > 2")
    print()

    # ── Summary ───────────────────────────────────────────────────────────
    print("=" * 60)
    print("VERDICT")
    print("=" * 60)

    # RSI verdict
    rsi_sep = abs(avg_rsi_wins - avg_rsi_losses)
    if rsi_sep > 5:
        print(f"RSI(14): SIGNAL — {rsi_sep:.1f}pp separation between wins/losses")
    else:
        print(f"RSI(14): NOISE — only {rsi_sep:.1f}pp separation")

    # OBV verdict
    if obv_bucket:
        if agree and disagree:
            agree_wr = sum(1 for r in agree if r["won"]) / len(agree) * 100
            disagree_wr = sum(1 for r in disagree if r["won"]) / len(disagree) * 100
            obv_sep = agree_wr - disagree_wr
            if obv_sep > 5:
                print(f"OBV: SIGNAL — {obv_sep:.1f}pp WR advantage when direction agrees with volume")
            else:
                print(f"OBV: NOISE — only {obv_sep:.1f}pp separation")

    # VWAP verdict
    if vwap_trades:
        vwap_wr = vwap_correct / len(vwap_trades) * 100
        if vwap_wr > 55:
            print(f"VWAP: SIGNAL — {vwap_wr:.1f}% mean-reversion accuracy on {len(vwap_trades)} trades")
        else:
            print(f"VWAP: NOISE — {vwap_wr:.1f}% accuracy (below threshold)")

    print()


if __name__ == "__main__":
    main()
