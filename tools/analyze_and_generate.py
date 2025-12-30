#!/usr/bin/env python3
"""Analyze gcovr CSV and generate GoogleTest skeletons for top N uncovered files.
Usage: analyze_and_generate.py -c coverage.csv -o outdir -n 10
"""
import argparse
import csv
import os
from pathlib import Path

def parse_csv(csvpath):
    rows = []
    with open(csvpath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows
#!/usr/bin/env python3
"""Analyze gcovr CSV and generate GoogleTest skeletons for top N uncovered files.
Usage: analyze_and_generate.py -c coverage.csv -o outdir -n 10
"""
import argparse
import csv
import os
from pathlib import Path

def parse_csv(csvpath):
    rows = []
    with open(csvpath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def score_row(r):
    # try common keys
    for key in ['Lines', 'lines', 'line_percent', 'line%','Line %','Line']:
        if key in r and r[key] is not None and r[key] != '':
            try:
                # remove %
                v = r[key].strip().rstrip('%')
                return float(v)
            except:
                pass
    # fallback: find any percent-like field
    for k,v in r.items():
        if v and '%' in v:
            try:
                return float(v.strip().rstrip('%'))
            except:
                pass
    return 100.0


def generate_test_stub(srcfile, outpath):
    # srcfile: path to source relative to project root
    base = Path(srcfile).stem
    testname = f"test_{base}_generated.cpp"
    out = Path(outpath) / testname
    header = (
        f"// Auto-generated test skeleton for {srcfile}\n"
        "// TODO: implement meaningful tests to increase coverage\n"
        "#include <gtest/gtest.h>\n"
        f"#include \"{Path(srcfile).with_suffix('.h').name}\"\n\n"
        "using namespace std;\n\n"
        f"TEST({base.capitalize()}Generated, Basic) {{\n"
        "    // Arrange\n"
        f"    // TODO: create objects and call functions from {srcfile}\n"
        "    EXPECT_TRUE(true);\n"
        "}\n"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(header)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('-c','--csv', required=True, help='gcovr CSV file')
    p.add_argument('-o','--out', required=True, help='output directory for generated tests')
    p.add_argument('-n','--num', type=int, default=10, help='number of files to generate')
    args = p.parse_args()

    rows = parse_csv(args.csv)
    if not rows:
        print('No CSV rows found in', args.csv)
        return
    # Try to find filename column
    filename_key = None
    for k in rows[0].keys():
        if 'file' in k.lower():
            filename_key = k
            break
    if not filename_key:
        print('Could not find filename column in CSV; headers:', list(rows[0].keys()))
        return
    # Score and sort ascending (lowest coverage first)
    scored = []
    for r in rows:
        pct = score_row(r)
        scored.append((pct, r))
    scored.sort(key=lambda x: x[0])
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    generated = []
    for pct, r in scored[:args.num]:
        src = r[filename_key]
        # make a best-effort relative path
        stub = generate_test_stub(src, outdir)
        generated.append((src, pct, str(stub)))
    # Write summary
    summary = outdir / 'generation_summary.txt'
    with open(summary, 'w', encoding='utf-8') as f:
        for src,pct,stub in generated:
            f.write(f"{src}\t{pct}%\t{stub}\n")
    print('Generated', len(generated), 'test stubs into', outdir)

if __name__ == '__main__':
    main()
