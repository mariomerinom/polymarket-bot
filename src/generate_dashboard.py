"""Generate static HTML dashboard for GitHub Pages."""

from pathlib import Path
from dashboard import build_html

DOCS_DIR = Path(__file__).parent.parent / "docs"


def generate():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    output = DOCS_DIR / "index.html"
    output.write_text(build_html())
    print(f"  Dashboard written to {output}")


if __name__ == "__main__":
    generate()
