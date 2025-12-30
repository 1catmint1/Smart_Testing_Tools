from pathlib import Path
import os
import sys
# ensure repo root on sys.path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

os.environ['QT_TEST_AI_COVERAGE_CMD'] = 'gcovr -r . --object-directory tests/build/Desktop_Qt_6_10_1_MinGW_64_bit-Debug/debug --gcov-executable D:/Qt/Tools/mingw1310_64/bin/gcov.exe --exclude-directories .git --exclude-directories .venv --exclude-directories tools --exclude-directories generated_tests --print-summary --html-details -o coverage.html'

from src.qt_test_ai.test_automation import run_coverage_command
proj = Path(r'C:/Users/lenovo/Desktop/Diagramscene_ultima-main')
findings, meta = run_coverage_command(proj)
print('returncode:', meta.get('returncode'))
print('summary:', meta.get('summary'))
print('coverage_summary:', meta.get('coverage_summary'))
# write meta to file for inspection
out = Path(__file__).parent / 'tmp_coverage_meta.json'
import json
out.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
print('wrote', out)
