"""Minimal markdown → HTML renderer (no dependencies).

Used for any reflective doc that needs to be readable on a phone without
opening a markdown viewer. Handles ATX headers, paragraphs, lists, GFM
tables, bold/italic, inline code, blockquotes, hr, checkboxes, details.

Not a full CommonMark implementation — just the subset our docs actually
use. Output is a single self-contained HTML file with light/dark CSS.

Usage: python3 tools/render_md_to_html.py <src.md> <dst.html>
"""

import html
import re
import sys


def _inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"<em>\1</em>", text)
    text = text.replace("[ ]", "☐").replace("[x]", "☑").replace("[X]", "☑")
    return text


def render_table(rows):
    header = [c.strip() for c in rows[0].strip().strip("|").split("|")]
    body = rows[2:]
    out = ["<table>", "<thead><tr>"]
    for c in header:
        out.append(f"<th>{_inline(c)}</th>")
    out.append("</tr></thead><tbody>")
    for line in body:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        out.append("<tr>")
        for c in cells:
            out.append(f"<td>{_inline(c)}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def render(md: str) -> str:
    lines = md.split("\n")
    out = []
    i = 0
    in_para = []

    def flush_para():
        if in_para:
            out.append(f"<p>{_inline(' '.join(in_para))}</p>")
            in_para.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped == "---":
            flush_para()
            out.append("<hr />")
            i += 1
            continue
        if not stripped:
            flush_para()
            i += 1
            continue
        # Pass-through HTML (e.g., <details>, <summary>)
        if stripped.startswith("<") and not stripped.startswith("<!--"):
            flush_para()
            out.append(stripped)
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_para()
            level = len(m.group(1))
            out.append(
                f"<h{level}>{_inline(m.group(2).strip())}</h{level}>"
            )
            i += 1
            continue

        if line.lstrip().startswith("|") and i + 1 < len(lines):
            sep = lines[i + 1].strip()
            if re.match(
                r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?$", sep
            ):
                flush_para()
                table_lines = [line]
                i += 1
                table_lines.append(lines[i])
                i += 1
                while i < len(lines) and lines[i].lstrip().startswith("|"):
                    table_lines.append(lines[i])
                    i += 1
                out.append(render_table(table_lines))
                continue

        m_ul = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m_ul:
            flush_para()
            out.append("<ul>")
            while i < len(lines):
                m2 = re.match(r"^(\s*)[-*]\s+(.*)$", lines[i])
                if not m2:
                    break
                out.append(f"<li>{_inline(m2.group(2))}</li>")
                i += 1
            out.append("</ul>")
            continue

        m_ol = re.match(r"^(\s*)\d+\.\s+(.*)$", line)
        if m_ol:
            flush_para()
            out.append("<ol>")
            while i < len(lines):
                m2 = re.match(r"^(\s*)\d+\.\s+(.*)$", lines[i])
                if not m2:
                    break
                out.append(f"<li>{_inline(m2.group(2))}</li>")
                i += 1
            out.append("</ol>")
            continue

        if stripped.startswith(">"):
            flush_para()
            content = stripped.lstrip(">").strip()
            out.append(f"<blockquote>{_inline(content)}</blockquote>")
            i += 1
            continue

        if stripped.startswith("*") and stripped.endswith("*") and len(stripped) > 2:
            flush_para()
            out.append(f"<p><em>{_inline(stripped[1:-1])}</em></p>")
            i += 1
            continue

        in_para.append(stripped)
        i += 1

    flush_para()
    return "\n".join(out)


_CSS = """
:root { color-scheme: light dark;
  --bg:#fafaf7; --fg:#1a1a1a; --muted:#666; --accent:#8b5a3c;
  --border:#d9d4ca; --code-bg:#f0ece5; --table-alt:#f4f0e8; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#1a1a1a; --fg:#e8e4da; --muted:#999; --accent:#c89878;
    --border:#3a3a3a; --code-bg:#2a2a2a; --table-alt:#222; } }
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  font-size: 17px; line-height: 1.65; color: var(--fg); background: var(--bg);
  margin: 0 auto; max-width: 760px; padding: 1.5em 1em; }
h1 { font-size: 2em; border-bottom: 2px solid var(--accent); padding-bottom: 0.3em; margin-top: 0; }
h2 { font-size: 1.5em; margin-top: 2em; border-bottom: 1px solid var(--border); padding-bottom: 0.2em; }
h3 { font-size: 1.2em; margin-top: 1.6em; }
h4 { font-size: 1.05em; color: var(--muted); }
p, ul, ol { margin: 0.9em 0; }
ul, ol { padding-left: 1.6em; }
li { margin: 0.3em 0; }
code { font-family: "SF Mono", Monaco, Menlo, Consolas, monospace;
  background: var(--code-bg); padding: 0.1em 0.35em; border-radius: 3px; font-size: 0.88em; }
blockquote { border-left: 3px solid var(--accent); margin: 1.2em 0;
  padding: 0.4em 1em; color: var(--muted); background: var(--code-bg); }
hr { border: none; border-top: 1px solid var(--border); margin: 2.5em 0; }
table { border-collapse: collapse; width: 100%; margin: 1.2em 0; font-size: 0.95em; }
th, td { border: 1px solid var(--border); padding: 0.5em 0.75em; text-align: left; vertical-align: top; }
th { background: var(--code-bg); font-weight: 600; }
tr:nth-child(even) td { background: var(--table-alt); }
em { color: var(--muted); }
strong { color: var(--fg); }
details { margin: 1em 0; }
summary { cursor: pointer; color: var(--accent); font-weight: 600; }
@media (max-width: 600px) {
  body { font-size: 16px; padding: 1em 0.75em; }
  h1 { font-size: 1.6em; } h2 { font-size: 1.3em; }
  table { font-size: 0.85em; } th, td { padding: 0.35em 0.5em; } }
"""


def main(src_path: str, dst_path: str) -> None:
    with open(src_path) as f:
        md = f.read()
    body = render(md)
    m = re.search(r"<h1>(.*?)</h1>", body)
    title = re.sub(r"<[^>]+>", "", m.group(1)) if m else "Document"
    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>{_CSS}</style></head>
<body>
{body}
</body></html>
"""
    with open(dst_path, "w") as f:
        f.write(doc)
    print(f"wrote {dst_path} ({len(doc)} bytes)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: render_md_to_html.py <src.md> <dst.html>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
