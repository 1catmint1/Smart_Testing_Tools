#!/usr/bin/env python3
"""
Try multiple gcovr invocation variants to find one that can parse .gcda file paths.
Usage:
  python tools/gcovr_tester.py --project-root PATH --object-dir PATH [--gcovr PATH] [--gcov PATH]

The script will run several variants, save stdout/stderr to reports/tmp_gcovr_tests/<ts>/ and print a summary.
"""
import argparse
import subprocess
import os
import sys
from pathlib import Path
import json
from datetime import datetime

VARIANT_TEMPLATE = ["--print-summary", "--html-details", "-o", "coverage.html"]

def run_cmd(cmd, cwd, timeout=300):
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        return {'rc': -1, 'stdout': out, 'stderr': err, 'timed_out': True}
    return {'rc': proc.returncode, 'stdout': out, 'stderr': err, 'timed_out': False}


def build_variants(gcovr, project_root, object_dir, gcov):
    obj = object_dir
    proj = project_root
    variants = []
    # 1: run from project root, pass --object-directory (as current default)
    cmd1 = [gcovr, "-r", proj, "--object-directory", obj]
    if gcov:
        cmd1 += ["--gcov-executable", gcov]
    cmd1 += VARIANT_TEMPLATE
    variants.append(("root_with_objectdir", proj, cmd1))

    # 2: run from object dir, -r project root
    cmd2 = [gcovr, "-r", proj]
    if gcov:
        cmd2 += ["--gcov-executable", gcov]
    cmd2 += VARIANT_TEMPLATE
    variants.append(("objectdir_cwd", obj, cmd2))

    # 3: run from project root, object-directory=parent of obj (drop last component)
    parent_obj = str(Path(obj).parent)
    cmd3 = [gcovr, "-r", proj, "--object-directory", parent_obj]
    if gcov:
        cmd3 += ["--gcov-executable", gcov]
    cmd3 += VARIANT_TEMPLATE
    variants.append(("root_with_parent_objectdir", proj, cmd3))

    # 4: run from project root, object-directory=obj + ignore-errors
    cmd4 = [gcovr, "-r", proj, "--object-directory", obj, "--gcov-ignore-errors=no_working_dir_found"]
    if gcov:
        cmd4 += ["--gcov-executable", gcov]
    cmd4 += VARIANT_TEMPLATE
    variants.append(("root_with_ignore_errors", proj, cmd4))

    # 5: explicit root + object dir relative path
    rel_obj = os.path.relpath(obj, proj)
    cmd5 = [gcovr, "-r", proj, "--object-directory", rel_obj]
    if gcov:
        cmd5 += ["--gcov-executable", gcov]
    cmd5 += VARIANT_TEMPLATE
    variants.append(("root_with_rel_objectdir", proj, cmd5))

    return variants


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--project-root', required=True)
    p.add_argument('--object-dir', required=True)
    p.add_argument('--gcovr', default='gcovr')
    p.add_argument('--gcov', default=None)
    p.add_argument('--timeout', type=int, default=300)
    args = p.parse_args()

    project_root = os.path.abspath(args.project_root)
    object_dir = os.path.abspath(args.object_dir)
    gcovr = args.gcovr
    gcov = args.gcov

    if not os.path.exists(project_root):
        print('project_root not found:', project_root)
        sys.exit(2)
    if not os.path.exists(object_dir):
        print('object_dir not found:', object_dir)
        sys.exit(2)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir = Path('reports') / 'tmp_gcovr_tests' / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    variants = build_variants(gcovr, project_root, object_dir, gcov)

    summary = []
    for name, cwd, cmd in variants:
        print(f'Running variant: {name} (cwd={cwd})')
        try:
            res = run_cmd(cmd, cwd=cwd, timeout=args.timeout)
        except FileNotFoundError as e:
            print('Command not found:', cmd[0])
            res = {'rc': -127, 'stdout': '', 'stderr': str(e), 'timed_out': False}
        # save outputs
        fn_base = out_dir / name
        (out_dir / (name + '.cmd.txt')).write_text(' '.join(cmd))
        (fn_base.with_suffix('.stdout.txt')).write_text(res['stdout'] or '')
        (fn_base.with_suffix('.stderr.txt')).write_text(res['stderr'] or '')
        meta = {
            'name': name,
            'cwd': cwd,
            'cmd': cmd,
            'returncode': res['rc'],
            'timed_out': res['timed_out']
        }
        (fn_base.with_suffix('.meta.json')).write_text(json.dumps(meta, indent=2, ensure_ascii=False))

        ok = (res['rc'] == 0)
        summary.append({'variant': name, 'returncode': res['rc'], 'ok': ok, 'stdout_excerpt': (res['stdout'] or '')[:1000], 'stderr_excerpt': (res['stderr'] or '')[:2000]})
        print(f'  -> rc={res.get("rc")}, ok={ok}')

    # write summary
    (out_dir / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print('\nAll variants completed. Outputs written to', str(out_dir))
    print('Summary:')
    for s in summary:
        print(f" - {s['variant']}: rc={s['returncode']}, ok={s['ok']}")

if __name__ == '__main__':
    main()
