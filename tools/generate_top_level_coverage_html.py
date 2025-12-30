"""
Generate a simplified coverage HTML that only includes "top-level" files
(i.e. filenames without path separators) from a gcovr JSON file.
Usage: python generate_top_level_coverage_html.py <coverage.json> [out.html]
"""
import json
import os
import sys
from pathlib import Path


def render_html(rows, totals, out_path: Path, title: str = "Top-level Coverage"):
    out_lines = []
    out_lines.append("<!doctype html>")
    out_lines.append("<html><head><meta charset=\"utf-8\"><title>" + title + "</title>")
    out_lines.append("<style>table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px;text-align:left}th{background:#f3f3f3}</style>")
    out_lines.append("</head><body>")
    out_lines.append(f"<h1>{title}</h1>")
    out_lines.append("<h2>Totals</h2>")
    out_lines.append("<ul>")
    out_lines.append(f"<li>Lines: {totals.get('lines') or 'N/A'}</li>")
    out_lines.append(f"<li>Functions: {totals.get('functions') or 'N/A'}</li>")
    out_lines.append(f"<li>Branches: {totals.get('branches') or 'N/A'}</li>")
    out_lines.append("</ul>")
    out_lines.append("<h2>Files (top-level)</h2>")
    out_lines.append("<table>")
    out_lines.append("<thead><tr><th>Filename</th><th>Covered</th><th>Total</th><th>Percent</th></tr></thead>")
    out_lines.append("<tbody>")
    for r in rows:
        fn = r.get('filename') or r.get('file') or ''
        # Support multiple gcovr JSON schemas:
        # - lines as dict: {'covered': x, 'total': y}
        # - lines as list: [{ 'line_number': n, 'count': c }, ...]
        ln_cov = 0
        ln_tot = 0
        lines_field = r.get('lines') or {}
        if isinstance(lines_field, dict):
            ln_cov = lines_field.get('covered') or lines_field.get('covered_lines') or 0
            ln_tot = lines_field.get('total') or lines_field.get('count') or 0
        elif isinstance(lines_field, list):
            try:
                for item in lines_field:
                    if not isinstance(item, dict):
                        continue
                    # consider entries with a line_number as code lines
                    if 'line_number' in item:
                        ln_tot += 1
                        if int(item.get('count') or 0) > 0:
                            ln_cov += 1
            except Exception:
                ln_cov = 0
                ln_tot = 0
        try:
            pct = f"{(int(ln_cov)/int(ln_tot)*100):.1f}%" if int(ln_tot) > 0 else 'N/A'
        except Exception:
            pct = 'N/A'
        out_lines.append(f"<tr><td>{fn}</td><td>{ln_cov}</td><td>{ln_tot}</td><td>{pct}</td></tr>")
    out_lines.append("</tbody>")
    out_lines.append("</table>")
    out_lines.append("</body></html>")

    out_path.write_text("\n".join(out_lines), encoding="utf-8")


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_top_level_coverage_html.py <coverage.json> [out.html]")
        sys.exit(2)
    cov_json = Path(sys.argv[1])
    if not cov_json.exists():
        print(f"coverage json not found: {cov_json}")
        sys.exit(3)
    out_html = Path(sys.argv[2]) if len(sys.argv) > 2 else cov_json.parent / "coverage_top_level.html"

    try:
        parsed = json.loads(cov_json.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to read/parse coverage json: {e}")
        sys.exit(4)

    files = parsed.get('files') or parsed.get('data') or []
    top_files = []
    for ent in files:
        if not isinstance(ent, dict):
            continue
        fname = ent.get('filename') or ent.get('file') or ''
        if not fname:
            continue
        # treat top-level as filenames without any slash/backslash
        if ("/" in fname) or ("\\" in fname):
            continue
        top_files.append(ent)

    # Compute totals for top-files
    covered_lines = 0
    total_lines = 0
    covered_funcs = 0
    total_funcs = 0
    covered_branches = 0
    total_branches = 0
    for ent in top_files:
        ln = ent.get('lines') or {}
        try:
            covered_lines += int(ln.get('covered') or ln.get('covered_lines') or 0)
            total_lines += int(ln.get('total') or ln.get('count') or 0)
        except Exception:
            pass
        fu = ent.get('functions') or {}
        try:
            covered_funcs += int(fu.get('covered') or fu.get('count') or 0)
            total_funcs += int(fu.get('total') or fu.get('count') or 0)
        except Exception:
            pass
        br = ent.get('branches') or {}
        try:
            covered_branches += int(br.get('covered') or br.get('count') or 0)
            total_branches += int(br.get('total') or br.get('count') or 0)
        except Exception:
            pass

    def pct(c, t):
        try:
            return f"{(float(c)/float(t)*100):.1f}%" if t and int(t) > 0 else None
        except Exception:
            return None

    totals = {
        'lines': pct(covered_lines, total_lines),
        'functions': pct(covered_funcs, total_funcs),
        'branches': pct(covered_branches, total_branches),
    }

    render_html(top_files, totals, out_html)
    print(f"Wrote top-level coverage HTML: {out_html}")


if __name__ == '__main__':
    main()
