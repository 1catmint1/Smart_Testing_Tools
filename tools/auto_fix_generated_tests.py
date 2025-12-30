#!/usr/bin/env python3
"""
Auto-fix LLM-generated QtTest sources under a project.

Features:
- Backup existing `tests/generated` directory.
- Fix common issues in generated .cpp files:
  - Normalize include paths (replace occurrences of "../" with "../../" when appropriate).
  - Deduplicate top `#include` lines while preserving order.
  - Remove extra `QTEST_MAIN(...)` occurrences leaving only the first.
  - Remove duplicate `#include "*.moc"` occurrences leaving only one.
  - If a file contains `Q_OBJECT` but no moc include, append a moc include at the end.

Usage:
  python tools/auto_fix_generated_tests.py --project <path-to-Diagramscene_ultima-main> [--apply]

By default the script prints proposed changes. Pass `--apply` to modify files in-place.
"""
import argparse
import shutil
import sys
from pathlib import Path
import datetime
import re


def backup_generated(generated_dir: Path, backup_root: Path) -> Path:
    backup_root.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = backup_root / f"tests_generated_backup_{ts}"
    print(f"Backing up {generated_dir} -> {dst}")
    shutil.copytree(generated_dir, dst)
    return dst


def normalize_includes(content: str) -> str:
    # Simple heuristic: when file is under tests/generated, includes for project headers
    # often need one more ../ than generated tests path. We'll replace '../' with '../../' for includes that
    # reference project headers (not system includes).
    lines = content.splitlines()
    new_lines = []
    include_set = []
    for ln in lines:
        if ln.strip().startswith('#include') and '"' in ln:
            # extract path inside quotes
            m = re.search(r'#include\s+"([^"]+)"', ln)
            if m:
                inc = m.group(1)
                # skip system or absolute includes
                if inc.startswith('..'):
                    # if it is ../something and has only one ../, promote to ../../
                    # avoid making too many changes; only change if starts with '../' but not '../../'
                    if inc.startswith('../') and not inc.startswith('../../'):
                        new_inc = '../../' + inc[3:] if inc.startswith('../') else inc
                        new_ln = ln.replace(inc, new_inc)
                        ln = new_ln
        new_lines.append(ln)

    # Deduplicate include lines while preserving order
    final_lines = []
    seen_includes = set()
    for ln in new_lines:
        if ln.strip().startswith('#include'):
            key = ln.strip()
            if key in seen_includes:
                continue
            seen_includes.add(key)
        final_lines.append(ln)

    return "\n".join(final_lines) + ("\n" if content.endswith("\n") else "")


def fix_qtest_main_and_moc(content: str) -> str:
    # Keep only the first QTEST_MAIN occurrence
    parts = re.split(r'(QTEST_MAIN\s*\([^)]*\))', content)
    if parts and len(parts) > 1:
        # parts will contain splits; keep first occurrence and remove subsequent ones
        new = []
        seen_main = False
        for p in parts:
            if p.strip().startswith('QTEST_MAIN'):
                if not seen_main:
                    new.append(p)
                    seen_main = True
                else:
                    # drop this token
                    continue
            else:
                new.append(p)
        content = "".join(new)

    # Ensure only one moc include ("*.moc") present
    moc_lines = re.findall(r'#include\s+"([^"]+\.moc)"', content)
    if len(moc_lines) > 1:
        # remove all moc includes and re-add a single one at end
        content = re.sub(r'#include\s+"[^"]+\.moc"\s*', '', content)
        content = content.rstrip() + '\n\n#include "' + moc_lines[0].split('/')[-1] + '"\n'

    # If Q_OBJECT present and no moc include at end, append a moc include matching filename
    if 'Q_OBJECT' in content and re.search(r'#include\s+"[^"]+\.moc"', content) is None:
        # attempt to find the source filename from a comment or fallback to test_*.moc
        # We'll append a generic moc include 'test_generated.moc' if unable to determine
        moc_name = None
        # try to find the C++ filename from a pragma or comment - fallback: get first identifier after QTEST_MAIN
        m = re.search(r'QTEST_MAIN\s*\(\s*([A-Za-z0-9_]+)\s*\)', content)
        if m:
            moc_name = f"test_{m.group(1).lower()}.moc"
        else:
            moc_name = 'test_generated.moc'
        content = content.rstrip() + '\n\n#include "' + moc_name + '"\n'

    return content


def remove_duplicate_entire_half(content: str) -> str:
    # Heuristic: if file consists of two identical halves, keep only the first half.
    s = content
    n = len(s)
    if n > 200 and n % 2 == 0:
        half = n // 2
        if s[:half] == s[half:]:
            print('Detected duplicated full-half content; trimming to first half')
            return s[:half]
    return s


def process_file(path: Path, apply: bool = False) -> bool:
    txt = path.read_text(encoding='utf-8')
    orig = txt
    txt = normalize_includes(txt)
    txt = fix_qtest_main_and_moc(txt)
    txt = remove_duplicate_entire_half(txt)

    changed = (txt != orig)
    if changed:
        print(f"Changes proposed for: {path}")
        if apply:
            path.write_text(txt, encoding='utf-8')
            print(f"Applied changes to {path}")
        else:
            print(f"(dry-run) file would be modified: {path}")
    return changed


def ensure_tests_pro(pro_path: Path, apply: bool = False):
    if not pro_path.exists():
        print(f"projects file not found: {pro_path}")
        return
    txt = pro_path.read_text(encoding='utf-8')
    changed = False
    # ensure includepath contains ../.. line
    if 'INCLUDEPATH += ../..' not in txt:
        txt = txt + '\nINCLUDEPATH += ../..\n'
        changed = True
    # ensure diagramscene.cpp is in SOURCES
    if '../../diagramscene.cpp' not in txt:
        txt = txt.replace('SOURCES =', 'SOURCES =')
        txt = txt + '\nSOURCES += \\\n+    ../../diagramscene.cpp\n'
        changed = True

    if changed:
        print(f"tests.pro would be updated: {pro_path}")
        if apply:
            pro_path.write_text(txt, encoding='utf-8')
            print(f"Updated {pro_path}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--project', '-p', type=Path, default=Path('..') / 'Diagramscene_ultima-main', help='Project root containing tests/generated')
    p.add_argument('--generated', '-g', type=Path, default=Path('tests') / 'generated', help='Relative path to generated tests from project root')
    p.add_argument('--backup', '-b', type=Path, default=Path('tools') / 'backups', help='Where to store backups (under Smart tools folder)')
    p.add_argument('--apply', action='store_true', help='Apply fixes in-place (default: dry-run)')
    args = p.parse_args()

    project_root = args.project.resolve()
    generated_dir = (project_root / args.generated).resolve()
    backup_root = (Path.cwd() / args.backup).resolve()

    if not generated_dir.exists():
        print(f"Generated tests directory not found: {generated_dir}")
        sys.exit(2)

    # Backup
    bak = backup_generated(generated_dir, backup_root)

    # Process .cpp files
    modified = []
    for cpp in sorted(generated_dir.glob('*.cpp')):
        try:
            if process_file(cpp, apply=args.apply):
                modified.append(cpp)
        except Exception as e:
            print(f"Error processing {cpp}: {e}")

    # Ensure tests.pro
    pro_path = generated_dir / 'tests.pro'
    ensure_tests_pro(pro_path, apply=args.apply)

    print('\nSummary:')
    print(f'Backup created at: {bak}')
    print(f'Files modified: {len(modified)} (apply={args.apply})')
    if not args.apply and modified:
        print('Run with --apply to persist the proposed changes.')


if __name__ == '__main__':
    main()
