"""Generate static HTML dashboard for GitHub Pages."""

import sqlite3
from pathlib import Path
from dashboard import build_html

DOCS_DIR = Path(__file__).parent.parent / "docs"


def generate():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

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

    output = DOCS_DIR / "index.html"
    output.write_text(build_html())
    print(f"  Dashboard written to {output}")


if __name__ == "__main__":
    generate()
