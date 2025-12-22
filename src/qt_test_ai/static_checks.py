from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from .models import Finding
from .utils import extract_pro_info, iter_files, read_text_best_effort, which


def _repo_root() -> Path:
    # src/qt_test_ai/static_checks.py -> repo root
    return Path(__file__).resolve().parents[2]


def _build_tool_env(*, cppcheck_path: str | None) -> dict[str, str]:
    """
    Prepare PATH for bundled tools (optional) and cppcheck itself.
    """
    env = os.environ.copy()
    repo = _repo_root()
    tools = repo / "tools"
    extra: list[str] = []

    mingw_bin = tools / "mingw64" / "mingw64" / "bin"
    if mingw_bin.exists():
        extra.append(str(mingw_bin))

    if cppcheck_path:
        extra.append(str(Path(cppcheck_path).parent))

    if extra:
        env["PATH"] = os.pathsep.join(extra + [env.get("PATH", "")])
    return env


def _try_qmake_query(qmake_path: str, key: str) -> str | None:
    try:
        p = subprocess.run(
            [qmake_path, "-query", key],
            capture_output=True,
            text=True,
            timeout=10,
            errors="replace",
        )
        v = (p.stdout or "").strip()
        return v if v else None
    except Exception:
        return None


def _detect_qt_include_dir(project_root: Path, meta: dict) -> Path | None:
    """
    Try to find Qt headers directory for cppcheck includes.
    Priority:
      1) QT_TEST_AI_QT_INCLUDE env
      2) qmake -query QT_INSTALL_HEADERS
      3) common env vars (QTDIR, Qt6_DIR) heuristic
    """
    env_v = (os.getenv("QT_TEST_AI_QT_INCLUDE") or "").strip()
    if env_v:
        p = Path(env_v)
        if p.exists():
            meta["qt_include_dir"] = str(p)
            meta["qt_include_source"] = "env:QT_TEST_AI_QT_INCLUDE"
            return p

    qmake = which("qmake") or which("qmake.exe")
    if qmake:
        h = _try_qmake_query(qmake, "QT_INSTALL_HEADERS")
        if h and Path(h).exists():
            meta["qt_include_dir"] = h
            meta["qt_include_source"] = "qmake -query QT_INSTALL_HEADERS"
            meta["qt_qmake"] = qmake
            return Path(h)

    # heuristic: QTDIR points to Qt root, headers often under <QTDIR>/include
    for k in ("QTDIR", "Qt6_DIR", "Qt_DIR"):
        v = (os.getenv(k) or "").strip()
        if not v:
            continue
        root = Path(v)
        cand = root / "include"
        if cand.exists():
            meta["qt_include_dir"] = str(cand)
            meta["qt_include_source"] = f"env:{k}"
            return cand

    return None


_CPPHECK_GCC_LINE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?:(?P<col>\d+):)?\s*(?P<sev>error|warning|style|performance|portability|information):\s*(?P<msg>.*?)(?:\s*\[(?P<id>[^\]]+)\])?$",
    re.IGNORECASE,
)


def _parse_cppcheck_output_to_findings(out: str, project_root: Path, max_items: int = 200) -> tuple[list[Finding], dict]:
    """
    Parse --template=gcc output into structured findings.
    Returns (findings, stats).
    """
    stats: dict[str, Any] = {"parsed": 0, "dropped": 0, "by_severity": {}}
    findings: list[Finding] = []

    for raw in (out or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _CPPHECK_GCC_LINE.match(line)
        if not m:
            continue

        sev_raw = (m.group("sev") or "").lower()
        if sev_raw == "error":
            sev = "error"
        elif sev_raw == "warning":
            sev = "warning"
        else:
            sev = "info"

        fpath = (m.group("file") or "").strip()
        try:
            f_rel = str(Path(fpath).resolve().relative_to(project_root.resolve()))
        except Exception:
            f_rel = fpath

        line_no = int(m.group("line")) if m.group("line") else None
        col_no = int(m.group("col")) if m.group("col") else None
        msg = (m.group("msg") or "").strip()
        rule_id = (m.group("id") or "").strip() or "cppcheck"

        if stats["parsed"] < max_items:
            detail = raw
            if col_no is not None:
                detail = f"(col {col_no}) {raw}"

            findings.append(
                Finding(
                    category="static",
                    severity=sev,
                    title=msg[:120] if msg else "cppcheck issue",
                    details=detail,
                    file=f_rel,
                    line=line_no,
                    rule_id=rule_id,
                )
            )

        else:
            stats["dropped"] += 1

        stats["parsed"] += 1
        stats["by_severity"][sev_raw] = stats["by_severity"].get(sev_raw, 0) + 1

    return findings, stats


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def run_static_checks(project_root: Path) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    meta: dict = {}

    tests_dir = project_root / "tests"

    # -----------------------------------------------------
    # 1) Basic qmake (.pro) sanity (root *.pro only)
    # -----------------------------------------------------
    pro_files = list(project_root.glob("*.pro"))
    if not pro_files:
        findings.append(
            Finding(
                category="static",
                severity="warning",
                title="未发现 .pro 文件（可能不是 qmake 工程）",
                details="在项目根目录未找到 *.pro；若是 CMake/其他结构可忽略。",
            )
        )
    else:
        meta["pro"] = []
        for pro in pro_files:
            txt = read_text_best_effort(pro)
            info = extract_pro_info(txt)
            meta["pro"].append({"file": str(pro), "info": info})

            if "TEMPLATE" not in info:
                findings.append(
                    Finding(
                        category="static",
                        severity="warning",
                        title=f".pro 未声明 TEMPLATE：{pro.name}",
                        details="可能导致构建/测试生成不稳定（可忽略，视课程要求）。",
                        file=str(pro),
                    )
                )

    # -----------------------------------------------------
    # 2) Simple custom static rules (lightweight) - skip tests/
    # -----------------------------------------------------
    for p in iter_files(project_root, ("**/*.h", "**/*.hpp", "**/*.cpp", "**/*.cc", "**/*.cxx")):
        if tests_dir.exists() and _is_under(p, tests_dir):
            continue  # ✅ 不扫描 tests/

        text = read_text_best_effort(p)

        # rule: TODO/FIXME
        for m in re.finditer(r"\b(TODO|FIXME)\b(.{0,80})", text):
            findings.append(
                Finding(
                    category="static",
                    severity="info",
                    title=f"发现 {m.group(1)}",
                    details=m.group(0).strip(),
                    file=str(p),
                )
            )

        # rule: using namespace std;
        if re.search(r"^\s*using\s+namespace\s+std\s*;", text, re.M):
            findings.append(
                Finding(
                    category="static",
                    severity="warning",
                    title="不建议在头/源文件中使用 using namespace std;",
                    details="建议使用 std:: 前缀，或在更小作用域内 using。",
                    file=str(p),
                )
            )

    # -----------------------------------------------------
    # 3) cppcheck (structured output) - skip tests/ via -i
    # -----------------------------------------------------
    cppcheck = which("cppcheck") or which("cppcheck.exe")
    meta["cppcheck_found"] = bool(cppcheck)
    meta["cppcheck_path"] = cppcheck

    if not cppcheck:
        findings.append(
            Finding(
                category="static",
                severity="warning",
                title="未找到 cppcheck（静态分析将跳过）",
                details="请安装 cppcheck 或将其加入 PATH。",
            )
        )
        return findings, meta

    # gather include/define hints from .pro
    include_dirs: list[str] = []
    defines: list[str] = []
    for item in meta.get("pro", []) if isinstance(meta.get("pro"), list) else []:
        info = (item or {}).get("info") or {}
        for k in ("INCLUDEPATH", "INCLUDEPATH+=", "INCLUDEPATH +="):
            vals = info.get(k)
            if isinstance(vals, list):
                include_dirs.extend([str(x) for x in vals if str(x).strip()])
        vals = info.get("DEFINES")
        if isinstance(vals, list):
            defines.extend([str(x) for x in vals if str(x).strip()])

    qt_inc = _detect_qt_include_dir(project_root, meta)
    if qt_inc:
        include_dirs.extend(
            [
                str(qt_inc),
                str(qt_inc / "QtCore"),
                str(qt_inc / "QtGui"),
                str(qt_inc / "QtWidgets"),
            ]
        )

    # de-dup, normalize
    def _norm(p: str) -> str:
        try:
            pp = Path(p)
            if pp.is_absolute():
                return str(pp.resolve())
            return str((project_root / p).resolve())
        except Exception:
            return p

    include_dirs = list(dict.fromkeys([_norm(p) for p in include_dirs if p]))
    defines = list(dict.fromkeys([d.strip() for d in defines if d.strip()]))

    meta["cppcheck_includes"] = include_dirs
    meta["cppcheck_defines"] = defines

    # ignore paths (cppcheck cross-version compatible): use -i <path>
    ignore_paths: list[Path] = []
    for name in (
        "build",
        "Build",
        "cmake-build-debug",
        "cmake-build-release",
        ".qt",
        ".qtc_clangd",
    ):
        p = project_root / name
        if p.exists():
            ignore_paths.append(p)

    # ✅ 你要求：不要检查 tests 文件夹
    if tests_dir.exists():
        ignore_paths.append(tests_dir)
        tb1 = tests_dir / "build"
        if tb1.exists():
            ignore_paths.append(tb1)

    cmd: list[str] = [
        cppcheck,
        "--enable=warning,style,performance,portability",
        "--inconclusive",
        "--std=c++17",
        "--force",
        "--inline-suppr",
        "--template=gcc",
        "--suppress=missingIncludeSystem",
        "--suppress=unmatchedSuppression",
    ]

    for d in defines:
        cmd.append(f"-D{d}")

    for inc in include_dirs:
        cmd.append(f"-I{inc}")

    # ✅ 用 -i 忽略目录，替代不兼容的 --exclude=
    for ip in ignore_paths:
        cmd += ["-i", str(ip)]

    # analyze whole project root, but tests/ 被 -i 排除
    cmd.append(str(project_root))

    meta["cppcheck_cmd"] = " ".join(cmd)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            env=_build_tool_env(cppcheck_path=cppcheck),
            errors="replace",
        )

        out = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()
        meta["cppcheck_returncode"] = proc.returncode

        # Save full report to tool-root ./reports with timestamp
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = _repo_root() / "reports" / "cppcheck" / project_root.name
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"cppcheck_{ts}.txt"
        try:
            report_path.write_text(out, encoding="utf-8")
            meta["cppcheck_report_path"] = str(report_path)
        except Exception:
            pass

        parsed_findings, stats = _parse_cppcheck_output_to_findings(out, project_root)
        meta["cppcheck_parsed"] = stats

        # Summary finding
        if stats.get("parsed", 0) == 0:
            findings.append(
                Finding(
                    category="static",
                    severity="warning" if proc.returncode != 0 else "info",
                    title="cppcheck 已运行，但未解析到结构化问题",
                    details=(
                        "可能原因：缺少 Qt include/defines 或 cppcheck 输出格式变化。\n"
                        f"完整输出已保存到：{meta.get('cppcheck_report_path','')}\n"
                        "你可以打开报告搜索关键字：noValidConfiguration / missingIncludeSystem。"
                    ),
                    rule_id="cppcheck",
                )
            )
        else:
            findings.append(
                Finding(
                    category="static",
                    severity="info",
                    title=f"cppcheck 解析到 {stats.get('parsed')} 条问题（展示前 {min(stats.get('parsed'), 200)} 条）",
                    details=f"完整输出已保存到：{meta.get('cppcheck_report_path','')}",
                    rule_id="cppcheck",
                )
            )
            findings.extend(parsed_findings)

    except Exception as e:
        findings.append(
            Finding(
                category="static",
                severity="warning",
                title="cppcheck 执行失败",
                details=str(e),
                rule_id="cppcheck",
            )
        )

    return findings, meta
