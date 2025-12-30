import json
import sys
from pathlib import Path

# Usage: python coverage_extractor.py <coverage.json> [out_dir]

def compute_totals(data):
    # gcovr 0.14 format: top-level may include totals/metrics, but older versions only have files
    totals = {
        'lines': {'total': 0, 'covered': 0},
        'functions': {'total': 0, 'covered': 0},
        'branches': {'total': 0, 'covered': 0},
    }

    # If gcovr already provided totals/metrics, prefer those
    if isinstance(data, dict):
        if 'totals' in data and isinstance(data['totals'], dict):
            t = data['totals']
            # expected keys may vary
            for key in ['lines', 'functions', 'branches']:
                if key in t:
                    totals[key]['total'] = t[key].get('total', 0)
                    totals[key]['covered'] = t[key].get('covered', 0)
            return totals

    # Otherwise, compute from files
    files = data.get('files', []) if isinstance(data, dict) else []
    for f in files:
        lines = f.get('lines', [])
        for ln in lines:
            totals['lines']['total'] += 1
            if ln.get('count', 0) > 0:
                totals['lines']['covered'] += 1
        funcs = f.get('functions', [])
        for fn in funcs:
            totals['functions']['total'] += 1
            if fn.get('count', 0) > 0:
                totals['functions']['covered'] += 1
        branches = f.get('branches', [])
        for br in branches:
            totals['branches']['total'] += 1
            if br.get('taken', 0) > 0:
                totals['branches']['covered'] += 1
    return totals


def percent(covered, total):
    if total <= 0:
        return 0.0
    return round(100.0 * covered / total, 2)


def main():
    if len(sys.argv) < 2:
        print("Usage: coverage_extractor.py <coverage.json> [out_dir]")
        sys.exit(2)
    cov_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else cov_path.parent
    if not cov_path.exists():
        print(f"coverage file not found: {cov_path}")
        sys.exit(2)
    data = json.loads(cov_path.read_text(encoding='utf-8'))
    totals = compute_totals(data)
    report = {
        'summary': {
            'lines': {
                'total': totals['lines']['total'],
                'covered': totals['lines']['covered'],
                'percent': percent(totals['lines']['covered'], totals['lines']['total'])
            },
            'functions': {
                'total': totals['functions']['total'],
                'covered': totals['functions']['covered'],
                'percent': percent(totals['functions']['covered'], totals['functions']['total'])
            },
            'branches': {
                'total': totals['branches']['total'],
                'covered': totals['branches']['covered'],
                'percent': percent(totals['branches']['covered'], totals['branches']['total'])
            }
        }
    }
    out_json = out_dir / 'coverage_report.json'
    out_txt = out_dir / 'coverage_report.txt'
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    with out_txt.open('w', encoding='utf-8') as f:
        f.write('Coverage Summary\n')
        f.write('Lines: {covered}/{total} ({pct}%)\n'.format(covered=report['summary']['lines']['covered'], total=report['summary']['lines']['total'], pct=report['summary']['lines']['percent']))
        f.write('Functions: {covered}/{total} ({pct}%)\n'.format(covered=report['summary']['functions']['covered'], total=report['summary']['functions']['total'], pct=report['summary']['functions']['percent']))
        f.write('Branches: {covered}/{total} ({pct}%)\n'.format(covered=report['summary']['branches']['covered'], total=report['summary']['branches']['total'], pct=report['summary']['branches']['percent']))
    print('Wrote', out_json, out_txt)

if __name__ == '__main__':
    main()
