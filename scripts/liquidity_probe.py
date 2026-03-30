"""
liquidity_probe.py — One-shot CLOB liquidity comparison for BTC, SOL, ETH.

Answers: can we trade these assets at meaningful size on Polymarket?

Usage: python3 scripts/liquidity_probe.py
Output: docs/liquidity_probe.md + console summary

Zero changes to the BTC pipeline. Read-only diagnostic.
"""

import sys
import os
import json
import requests
from datetime import datetime, timedelta, timezone

# Add src to path for clob_depth imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clob_depth import get_order_book, analyze_depth, format_liquidity_log

GAMMA_API = "https://gamma-api.polymarket.com"

ASSETS = [
    {"key": "BTC", "label": "Bitcoin", "title_filter": "Bitcoin Up or Down"},
    {"key": "SOL", "label": "Solana", "title_filter": "Solana Up or Down"},
    {"key": "ETH", "label": "Ethereum", "title_filter": "Ethereum Up or Down"},
]


def fetch_markets_for_asset(title_filter, limit=5):
    """Fetch active 5m 'Up or Down' markets for a given asset from Gamma API."""
    now = datetime.now(timezone.utc)
    params = {
        "limit": 200,
        "order": "endDate",
        "ascending": "true",
        "end_date_min": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    try:
        resp = requests.get(f"{GAMMA_API}/events", params=params, timeout=10)
        resp.raise_for_status()
        events = resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"  [ERROR] Gamma API failed: {e}")
        return []

    markets = []
    for event in events:
        title = event.get("title", "")
        if title_filter not in title:
            continue

        for market in event.get("markets", []):
            try:
                if market.get("resolved", False):
                    continue

                end_date = market.get("endDate") or market.get("end_date_iso")
                if not end_date:
                    continue
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                if end_dt <= now or end_dt > now + timedelta(hours=24):
                    continue

                outcomes = market.get("outcomes", "[]")
                if isinstance(outcomes, str):
                    outcomes = json.loads(outcomes)
                if outcomes != ["Up", "Down"]:
                    continue

                raw_clob = market.get("clobTokenIds", "[]")
                if isinstance(raw_clob, str):
                    clob_ids = json.loads(raw_clob)
                else:
                    clob_ids = raw_clob

                if len(clob_ids) < 2:
                    continue

                raw_prices = market.get("outcomePrices", '[\"0\",\"0\"]')
                if isinstance(raw_prices, str):
                    prices = json.loads(raw_prices)
                else:
                    prices = raw_prices

                volume = float(market.get("volume", 0) or 0)

                markets.append({
                    "id": market["id"],
                    "question": market.get("question", title),
                    "end_date": end_date,
                    "volume": volume,
                    "price_yes": float(prices[0]),
                    "price_no": float(prices[1]) if len(prices) > 1 else 0,
                    "clob_token_yes": clob_ids[0],
                    "clob_token_no": clob_ids[1],
                })
            except (ValueError, KeyError, IndexError, json.JSONDecodeError):
                continue

    markets.sort(key=lambda m: m["end_date"])
    return markets[:limit]


def probe_asset(asset_info):
    """Probe CLOB liquidity for one asset. Returns dict of results."""
    key = asset_info["key"]
    label = asset_info["label"]
    title_filter = asset_info["title_filter"]

    print(f"\n{'='*60}")
    print(f"  {label} ({key})")
    print(f"{'='*60}")

    markets = fetch_markets_for_asset(title_filter)
    print(f"  Found {len(markets)} active 5m markets")

    if not markets:
        return {
            "key": key,
            "label": label,
            "markets_found": 0,
            "error": "no_markets",
        }

    # Probe the first available market
    market = markets[0]
    print(f"  Probing: {market['question'][:80]}")
    print(f"  Volume: ${market['volume']:,.0f}")
    print(f"  Price: UP {market['price_yes']:.1%} / DOWN {market['price_no']:.1%}")

    # Query YES book (buy side — hitting asks)
    print(f"  Fetching YES order book...")
    book_yes = get_order_book(market["clob_token_yes"])
    depth_yes = None
    if book_yes:
        depth_yes = analyze_depth(book_yes, side="buy")
        if "error" not in depth_yes:
            print(f"    YES: {format_liquidity_log(_depth_to_summary(depth_yes, 'YES'))}")
        else:
            print(f"    YES: empty book")

    # Query NO book (buy side — hitting asks)
    print(f"  Fetching NO order book...")
    book_no = get_order_book(market["clob_token_no"])
    depth_no = None
    if book_no:
        depth_no = analyze_depth(book_no, side="buy")
        if "error" not in depth_no:
            print(f"    NO:  {format_liquidity_log(_depth_to_summary(depth_no, 'NO'))}")
        else:
            print(f"    NO:  empty book")

    # Also probe multiple markets to check consistency
    additional = []
    for m in markets[1:3]:  # up to 2 more
        b = get_order_book(m["clob_token_yes"])
        if b:
            d = analyze_depth(b, side="buy")
            if "error" not in d:
                additional.append({
                    "question": m["question"][:60],
                    "spread_pct": d["spread_pct"],
                    "max_bet_2pct": d["max_bet_2pct"],
                    "depth_levels": d["depth_levels"],
                })

    return {
        "key": key,
        "label": label,
        "markets_found": len(markets),
        "market_question": market["question"],
        "volume": market["volume"],
        "price_yes": market["price_yes"],
        "price_no": market["price_no"],
        "yes": _extract_depth(depth_yes),
        "no": _extract_depth(depth_no),
        "additional_markets": additional,
        "raw_yes": _raw_book_summary(book_yes),
        "raw_no": _raw_book_summary(book_no),
    }


def _depth_to_summary(depth, token):
    """Convert analyze_depth result to format_liquidity_log input."""
    return {
        "token": token,
        "best_bid": depth.get("best_bid", 0),
        "best_ask": depth.get("best_ask", 0),
        "spread": depth.get("spread", 0),
        "spread_pct": depth.get("spread_pct", 0),
        "mid": depth.get("mid", 0),
        "max_bet_2pct": depth.get("max_bet_2pct", 0),
        "max_bet_5pct": depth.get("max_bet_5pct", 0),
        "depth_levels": depth.get("depth_levels", 0),
        "slippage_at_50": depth.get("slippage_curve", {}).get(50, {}),
        "slippage_at_200": depth.get("slippage_curve", {}).get(200, {}),
        "slippage_at_500": depth.get("slippage_curve", {}).get(500, {}),
    }


def _extract_depth(depth):
    """Extract key metrics from depth analysis, or return None."""
    if not depth or "error" in depth:
        return None
    curve = depth.get("slippage_curve", {})
    return {
        "best_bid": depth["best_bid"],
        "best_ask": depth["best_ask"],
        "spread_pct": depth["spread_pct"],
        "mid": depth["mid"],
        "max_bet_2pct": depth["max_bet_2pct"],
        "max_bet_5pct": depth["max_bet_5pct"],
        "depth_levels": depth["depth_levels"],
        "slip_50": curve.get(50, {}).get("slippage_pct"),
        "slip_200": curve.get(200, {}).get("slippage_pct"),
        "slip_500": curve.get(500, {}).get("slippage_pct"),
    }


def _raw_book_summary(book):
    """Compact raw book summary for the report."""
    if not book:
        return None
    bids = book.get("bids", [])
    asks = book.get("asks", [])
    return {
        "num_bids": len(bids),
        "num_asks": len(asks),
        "top_5_bids": [{"price": b["price"], "size": b["size"]} for b in sorted(bids, key=lambda x: -float(x["price"]))[:5]],
        "top_5_asks": [{"price": a["price"], "size": a["size"]} for a in sorted(asks, key=lambda x: float(x["price"]))[:5]],
    }


def go_no_go(result):
    """Determine go/no-go status for an asset."""
    if result.get("error"):
        return "NO-GO", "no markets found"

    yes = result.get("yes")
    no = result.get("no")

    # Use the better of YES/NO book
    max_bet = 0
    if yes:
        max_bet = max(max_bet, yes["max_bet_2pct"])
    if no:
        max_bet = max(max_bet, no["max_bet_2pct"])

    if max_bet >= 50:
        return "GO", f"max_bet_2pct ${max_bet:,.0f} >= $50 threshold"
    elif max_bet >= 20:
        return "MARGINAL", f"max_bet_2pct ${max_bet:,.0f} — tight but possible with small sizing"
    else:
        return "NO-GO", f"max_bet_2pct ${max_bet:,.0f} — too thin to trade"


def generate_report(results):
    """Generate markdown comparison report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Liquidity Probe — {now}",
        "",
        "Side-by-side CLOB order book comparison for multi-asset expansion decision.",
        "",
        "## Side-by-Side Comparison (YES token, buy side)",
        "",
    ]

    # Build comparison table
    headers = ["Metric"] + [r["key"] for r in results]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["--------"] * len(headers)) + "|")

    def val(result, field, fmt=None):
        if result.get("error"):
            return "—"
        yes = result.get("yes")
        if not yes:
            return "—"
        v = yes.get(field)
        if v is None:
            return "—"
        if fmt == "pct":
            return f"{v:.2f}%"
        if fmt == "dollar":
            return f"${v:,.0f}"
        if fmt == "price":
            return f"{v:.4f}"
        if fmt == "int":
            return str(int(v))
        return str(v)

    rows = [
        ("Markets found", lambda r: str(r.get("markets_found", 0)), None),
        ("Volume", lambda r: f"${r.get('volume', 0):,.0f}" if not r.get("error") else "—", None),
        ("Market price (UP)", lambda r: f"{r.get('price_yes', 0):.1%}" if not r.get("error") else "—", None),
        ("Best bid / ask", lambda r: f"{r['yes']['best_bid']:.3f} / {r['yes']['best_ask']:.3f}" if r.get("yes") else "—", None),
        ("Spread %", lambda r: val(r, "spread_pct", "pct"), None),
        ("Max bet @2% slip", lambda r: val(r, "max_bet_2pct", "dollar"), None),
        ("Max bet @5% slip", lambda r: val(r, "max_bet_5pct", "dollar"), None),
        ("Depth levels", lambda r: val(r, "depth_levels", "int"), None),
        ("$50 slippage", lambda r: f"{r['yes']['slip_50']:.2f}%" if r.get("yes") and r["yes"].get("slip_50") is not None else "—", None),
        ("$200 slippage", lambda r: f"{r['yes']['slip_200']:.2f}%" if r.get("yes") and r["yes"].get("slip_200") is not None else "—", None),
        ("$500 slippage", lambda r: f"{r['yes']['slip_500']:.2f}%" if r.get("yes") and r["yes"].get("slip_500") is not None else "—", None),
    ]

    for label, fn, _ in rows:
        cells = [label] + [fn(r) for r in results]
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")

    # Go/No-Go
    lines.extend(["## Go/No-Go Assessment", ""])
    for r in results:
        status, reason = go_no_go(r)
        emoji = {"GO": "✅", "MARGINAL": "⚠️", "NO-GO": "❌"}.get(status, "?")
        lines.append(f"- **{r['key']}:** {emoji} **{status}** — {reason}")
    lines.append("")

    # Additional markets sampled
    has_additional = any(r.get("additional_markets") for r in results)
    if has_additional:
        lines.extend(["## Additional Markets Sampled", ""])
        for r in results:
            if r.get("additional_markets"):
                lines.append(f"### {r['label']}")
                lines.append("")
                lines.append("| Market | Spread % | Max Bet @2% | Depth |")
                lines.append("|--------|----------|-------------|-------|")
                for m in r["additional_markets"]:
                    lines.append(f"| {m['question']} | {m['spread_pct']:.2f}% | ${m['max_bet_2pct']:,.0f} | {m['depth_levels']} |")
                lines.append("")

    # Raw data
    lines.extend([
        "## Raw Order Book Snapshots",
        "",
        "<details>",
        "<summary>Click to expand</summary>",
        "",
        "```json",
    ])
    raw = {}
    for r in results:
        raw[r["key"]] = {
            "yes_book": r.get("raw_yes"),
            "no_book": r.get("raw_no"),
        }
    lines.append(json.dumps(raw, indent=2))
    lines.extend([
        "```",
        "",
        "</details>",
        "",
        "---",
        f"*Generated by `scripts/liquidity_probe.py` at {now}*",
    ])

    return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 60)
    print("  MULTI-ASSET LIQUIDITY PROBE")
    print("  BTC vs SOL vs ETH — Polymarket CLOB")
    print("=" * 60)

    results = []
    for asset in ASSETS:
        result = probe_asset(asset)
        results.append(result)

    # Console summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    for r in results:
        status, reason = go_no_go(r)
        emoji = {"GO": "✅", "MARGINAL": "⚠️", "NO-GO": "❌"}.get(status, "?")
        print(f"  {r['key']:>4}: {emoji} {status} — {reason}")

    # Write report
    report = generate_report(results)
    output_path = os.path.join(os.path.dirname(__file__), "..", "docs", "liquidity_probe.md")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(report)
    print(f"\n  Report written to: {output_path}")
