"""Generate dashboard — now a no-op since dashboards are served dynamically.

The Flask server (dashboard_server.py) on the VPS serves dashboards live.
Static HTML files are no longer committed to docs/.

Integrity checks are preserved — they run during each CI cycle.
"""

import sqlite3
from pathlib import Path


def generate():
    # BTC 5m integrity checks (ci_run.py is frozen — this is the hook)
    try:
        from pipeline_integrity import run_integrity_checks
        db_path = Path(__file__).parent.parent / "data" / "predictions.db"
        if db_path.exists():
            db = sqlite3.connect(str(db_path))
            results = run_integrity_checks(db, pipeline="btc_5m")
            for r in results:
                if r["status"] != "OK":
                    print(f"  [INTEGRITY btc_5m] [{r['status']}] {r['check_name']}: {r['detail']}")
            db.close()
    except Exception as e:
        print(f"  [INTEGRITY btc_5m] check failed: {e}")

    print("  Dashboard served dynamically — skipping static HTML generation")


if __name__ == "__main__":
    generate()
