"""
dashboard.py — Web dashboard for the Polymarket autoresearch bot.

Run: python dashboard.py (from src/ directory)
Serves on http://localhost:5050
"""

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from flask import Flask, Response
    app = Flask(__name__)
except ImportError:
    app = None

DB_PATH = Path(__file__).parent.parent / "data" / "predictions.db"
EVOLUTION_LOG = Path(__file__).parent.parent / "data" / "evolution_log.json"

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def load_evolution_log():
    if EVOLUTION_LOG.exists():
        try:
            return json.loads(EVOLUTION_LOG.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    return []


def get_agent_scorecard(db):
    rows = db.execute("""
        SELECT p.agent,
               COUNT(*) AS num_markets,
               AVG((p.estimate - m.outcome) * (p.estimate - m.outcome)) AS avg_brier,
               AVG((p.estimate - m.outcome) * (p.estimate - m.outcome))
                 - AVG((m.price_yes - m.outcome) * (m.price_yes - m.outcome)) AS vs_market
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE m.resolved = 1
        GROUP BY p.agent
        ORDER BY avg_brier ASC
    """).fetchall()
    return rows


def get_recent_predictions(db, limit=50):
    rows = db.execute("""
        SELECT p.agent, p.estimate, p.edge, p.confidence, p.predicted_at, p.cycle,
               m.question, m.price_yes, m.resolved, m.outcome
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        ORDER BY p.predicted_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return rows


def get_markets(db):
    rows = db.execute("""
        SELECT id, question, category, end_date, volume, price_yes, price_no,
               resolved, outcome
        FROM markets
        ORDER BY resolved ASC, end_date ASC
    """).fetchall()
    return rows


def get_status(db):
    """Get bot status info for the header."""
    now = datetime.now(timezone.utc)

    # Last prediction time
    row = db.execute("SELECT MAX(predicted_at) FROM predictions").fetchone()
    last_prediction = row[0] if row and row[0] else None

    # Total markets / resolved
    total = db.execute("SELECT COUNT(*) FROM markets").fetchone()[0]
    resolved = db.execute("SELECT COUNT(*) FROM markets WHERE resolved = 1").fetchone()[0]

    # Next unresolved market
    now_iso = now.isoformat()
    row = db.execute(
        "SELECT end_date FROM markets WHERE resolved = 0 AND end_date > ? ORDER BY end_date ASC LIMIT 1",
        (now_iso,)
    ).fetchone()
    next_market_end = row[0] if row else None

    # Bot status
    status = "Idle"
    if last_prediction:
        try:
            last_dt = datetime.fromisoformat(last_prediction.replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            diff_min = (now - last_dt).total_seconds() / 60
            if diff_min <= 10:
                status = "Active"
            else:
                status = "Stale"
        except ValueError:
            status = "Unknown"

    # Total evolutions
    evolutions = len(load_evolution_log())

    return {
        "last_prediction": last_prediction[:16].replace("T", " ") if last_prediction else "Never",
        "total_markets": total,
        "resolved_markets": resolved,
        "next_market_end": next_market_end,
        "status": status,
        "evolutions": evolutions,
    }


def brier_color(score):
    """Return CSS color based on Brier score quality."""
    if score is None:
        return "#888"
    if score < 0.1:
        return "#4caf50"
    if score < 0.2:
        return "#8bc34a"
    if score < 0.3:
        return "#ffc107"
    if score < 0.5:
        return "#ff9800"
    return "#f44336"


def vs_market_color(vs):
    if vs is None:
        return "#888"
    return "#4caf50" if vs < 0 else "#f44336"


def build_html():
    db = get_db()
    try:
        status = get_status(db)
        scorecard = get_agent_scorecard(db)
        predictions = get_recent_predictions(db)
        markets = get_markets(db)
        evolution = load_evolution_log()
    finally:
        db.close()

    # -- Status Header --
    status_color = {
        "Active": "#238636", "Idle": "#8b949e", "Stale": "#da3633", "Unknown": "#484f58"
    }.get(status["status"], "#484f58")

    next_market_js = ""
    if status["next_market_end"]:
        next_market_js = f'data-next-market="{status["next_market_end"]}"'

    status_html = f"""<div class="status-bar">
        <div class="status-item">
            <span class="status-label">Status</span>
            <span class="status-value" style="color:{status_color}">{status["status"]}</span>
        </div>
        <div class="status-item">
            <span class="status-label">Last Cycle</span>
            <span class="status-value">{status["last_prediction"]} UTC</span>
        </div>
        <div class="status-item">
            <span class="status-label">Markets</span>
            <span class="status-value">{status["resolved_markets"]} / {status["total_markets"]} resolved</span>
        </div>
        <div class="status-item">
            <span class="status-label">Next Market</span>
            <span class="status-value" id="countdown" {next_market_js}>--</span>
        </div>
        <div class="status-item">
            <span class="status-label">Evolutions</span>
            <span class="status-value">{status["evolutions"]}</span>
        </div>
    </div>"""

    # -- Agent Scorecard --
    scorecard_rows = ""
    if scorecard:
        for row in scorecard:
            agent = row["agent"]
            avg_brier = row["avg_brier"]
            num = row["num_markets"]
            vs = row["vs_market"]
            bc = brier_color(avg_brier)
            vc = vs_market_color(vs)
            beating = "BEATING" if vs < 0 else "LOSING TO"
            scorecard_rows += f"""<tr>
                <td class="agent-name">{agent}</td>
                <td style="color:{bc};font-weight:600">{avg_brier:.4f}</td>
                <td>{num}</td>
                <td style="color:{vc}">{vs:+.4f} ({beating} market)</td>
            </tr>"""
    else:
        scorecard_rows = '<tr><td colspan="4" class="empty">No resolved markets yet.</td></tr>'

    # -- Recent Predictions --
    prediction_rows = ""
    if predictions:
        for row in predictions:
            outcome_str = ""
            if row["resolved"]:
                outcome_str = '<span class="badge badge-yes">UP</span>' if row["outcome"] == 1 else '<span class="badge badge-no">DOWN</span>'
            else:
                outcome_str = '<span class="badge badge-pending">Pending</span>'
            question = row["question"]
            if len(question) > 80:
                question = question[:77] + "..."
            prediction_rows += f"""<tr>
                <td class="agent-name">{row["agent"]}</td>
                <td title="{row["question"]}">{question}</td>
                <td>{row["estimate"]:.1%}</td>
                <td>{row["price_yes"]:.1%}</td>
                <td>{row["edge"]:+.1%}</td>
                <td>{row["confidence"]}</td>
                <td>{outcome_str}</td>
                <td>C{row["cycle"]}</td>
            </tr>"""
    else:
        prediction_rows = '<tr><td colspan="8" class="empty">No predictions yet.</td></tr>'

    # -- Markets --
    market_rows = ""
    if markets:
        for row in markets:
            if row["resolved"]:
                status = '<span class="badge badge-yes">UP</span>' if row["outcome"] == 1 else '<span class="badge badge-no">DOWN</span>'
            else:
                status = '<span class="badge badge-pending">Pending</span>'
            question = row["question"]
            if len(question) > 90:
                question = question[:87] + "..."
            vol = row["volume"]
            vol_str = f"${vol:,.0f}" if vol else "$0"
            market_rows += f"""<tr>
                <td title="{row["question"]}">{question}</td>
                <td>{row["category"] or "N/A"}</td>
                <td>{row["price_yes"]:.1%}</td>
                <td>{vol_str}</td>
                <td>{row["end_date"][:10] if row["end_date"] else "N/A"}</td>
                <td>{status}</td>
            </tr>"""
    else:
        market_rows = '<tr><td colspan="6" class="empty">No markets tracked yet.</td></tr>'

    # -- Evolution History --
    evolution_items = ""
    if evolution:
        for entry in reversed(evolution):
            cycle = entry.get("cycle", "?")
            ts = entry.get("timestamp", "?")
            if isinstance(ts, str) and len(ts) > 16:
                ts = ts[:16].replace("T", " ")
            agent = entry.get("agent", "?")
            brier_before = entry.get("brier_before")
            brier_after = entry.get("brier_after")
            kept = entry.get("kept")
            mod = entry.get("modification", "")
            diagnosis = "N/A"
            expected = ""
            if isinstance(mod, dict):
                diagnosis = mod.get("diagnosis", "N/A")
                expected = mod.get("expected_effect", "")
            elif isinstance(mod, str):
                for line in mod.split("\n"):
                    if line.startswith("Diagnosis: "):
                        diagnosis = line[len("Diagnosis: "):]
                    elif line.startswith("Expected effect: "):
                        expected = line[len("Expected effect: "):]

            kept_badge = ""
            if kept is True:
                kept_badge = '<span class="badge badge-yes">Kept</span>'
            elif kept is False:
                kept_badge = '<span class="badge badge-no">Reverted</span>'
            else:
                kept_badge = '<span class="badge badge-pending">Pending</span>'

            brier_before_str = f"{brier_before:.4f}" if brier_before is not None else "N/A"
            brier_after_str = f"{brier_after:.4f}" if brier_after is not None else "N/A"

            evolution_items += f"""<div class="evo-card">
                <div class="evo-header">
                    <span class="evo-cycle">Cycle {cycle}</span>
                    <span class="evo-agent agent-name">{agent}</span>
                    <span class="evo-time">{ts}</span>
                    {kept_badge}
                </div>
                <div class="evo-body">
                    <p><strong>Diagnosis:</strong> {diagnosis}</p>
                    {"<p><strong>Expected effect:</strong> " + expected + "</p>" if expected else ""}
                    <p class="evo-scores">Brier: {brier_before_str} &rarr; {brier_after_str}</p>
                </div>
            </div>"""
    else:
        evolution_items = '<p class="empty">No evolution history yet.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>Polymarket Bot Dashboard</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    line-height: 1.5;
    padding: 20px;
}}
h1 {{
    color: #58a6ff;
    font-size: 1.8rem;
    margin-bottom: 8px;
}}
.subtitle {{
    color: #8b949e;
    margin-bottom: 28px;
    font-size: 0.95rem;
}}
h2 {{
    color: #58a6ff;
    font-size: 1.25rem;
    margin: 32px 0 12px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid #21262d;
}}
.container {{
    max-width: 1200px;
    margin: 0 auto;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 16px;
    font-size: 0.9rem;
}}
th {{
    background: #161b22;
    color: #58a6ff;
    text-align: left;
    padding: 10px 12px;
    border-bottom: 2px solid #21262d;
    white-space: nowrap;
}}
td {{
    padding: 8px 12px;
    border-bottom: 1px solid #21262d;
    vertical-align: middle;
    max-width: 320px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}}
tr:hover {{
    background: #161b22;
}}
.agent-name {{
    color: #d2a8ff;
    font-weight: 600;
}}
.badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 600;
}}
.badge-yes {{
    background: #238636;
    color: #fff;
}}
.badge-no {{
    background: #da3633;
    color: #fff;
}}
.badge-pending {{
    background: #30363d;
    color: #8b949e;
    border: 1px solid #484f58;
}}
.empty {{
    text-align: center;
    color: #484f58;
    padding: 24px;
    font-style: italic;
}}
.evo-card {{
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
}}
.evo-header {{
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 8px;
}}
.evo-cycle {{
    color: #58a6ff;
    font-weight: 700;
    font-size: 0.95rem;
}}
.evo-time {{
    color: #484f58;
    font-size: 0.85rem;
    margin-left: auto;
}}
.evo-body p {{
    margin: 4px 0;
    font-size: 0.9rem;
}}
.evo-scores {{
    color: #8b949e;
    font-size: 0.85rem;
}}
.status-bar {{
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 24px;
}}
.status-item {{
    display: flex;
    flex-direction: column;
    gap: 2px;
}}
.status-label {{
    color: #484f58;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.status-value {{
    color: #c9d1d9;
    font-size: 1rem;
    font-weight: 600;
}}
.table-wrap {{
    overflow-x: auto;
}}
@media (max-width: 768px) {{
    body {{ padding: 10px; }}
    h1 {{ font-size: 1.4rem; }}
    td, th {{ padding: 6px 8px; font-size: 0.82rem; }}
    .evo-header {{ flex-direction: column; align-items: flex-start; gap: 4px; }}
    .evo-time {{ margin-left: 0; }}
}}
</style>
</head>
<body>
<div class="container">
    <h1>Polymarket Autoresearch Bot</h1>
    <p class="subtitle">BTC 5-minute candle prediction &mdash; autoresearch loop</p>

    {status_html}

    <h2>Agent Scorecard</h2>
    <div class="table-wrap">
    <table>
        <thead><tr>
            <th>Agent</th>
            <th>Avg Brier Score</th>
            <th>Resolved Markets</th>
            <th>vs Market</th>
        </tr></thead>
        <tbody>{scorecard_rows}</tbody>
    </table>
    </div>

    <h2>Recent Predictions</h2>
    <div class="table-wrap">
    <table>
        <thead><tr>
            <th>Agent</th>
            <th>Market</th>
            <th>Estimate</th>
            <th>Market Price</th>
            <th>Edge</th>
            <th>Confidence</th>
            <th>Outcome</th>
            <th>Cycle</th>
        </tr></thead>
        <tbody>{prediction_rows}</tbody>
    </table>
    </div>

    <h2>Markets</h2>
    <div class="table-wrap">
    <table>
        <thead><tr>
            <th>Question</th>
            <th>Category</th>
            <th>Price (YES)</th>
            <th>Volume</th>
            <th>End Date</th>
            <th>Status</th>
        </tr></thead>
        <tbody>{market_rows}</tbody>
    </table>
    </div>

    <h2>Evolution History</h2>
    {evolution_items}
</div>
<script>
(function() {{
    var el = document.getElementById('countdown');
    if (!el) return;
    var endStr = el.getAttribute('data-next-market');
    if (!endStr) {{ el.textContent = 'None'; return; }}
    var end = new Date(endStr.replace('Z','+00:00'));
    function update() {{
        var now = new Date();
        var diff = Math.floor((end - now) / 1000);
        if (diff <= 0) {{ el.textContent = 'Resolving...'; return; }}
        var m = Math.floor(diff / 60);
        var s = diff % 60;
        el.textContent = m + 'm ' + (s < 10 ? '0' : '') + s + 's';
    }}
    update();
    setInterval(update, 1000);
}})();
</script>
</body>
</html>"""


if app:
    @app.route("/")
    def index():
        html = build_html()
        return Response(html, mimetype="text/html")


if __name__ == "__main__":
    if app is None:
        print("Flask not installed. Use generate_dashboard.py instead.")
    else:
        print(f"Dashboard: http://localhost:5050")
        print(f"Database:  {DB_PATH}")
        app.run(host="0.0.0.0", port=5050, debug=True)
