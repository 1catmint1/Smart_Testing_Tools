from __future__ import annotations

import re
import subprocess
import os
from pathlib import Path

from .models import Finding
from .utils import extract_pro_info, iter_files, read_text_best_effort, which


def _repo_root() -> Path:
    # src/qt_test_ai/static_checks.py -> repo root
    return Path(__file__).resolve().parents[2]


def _find_cppcheck_in_tools() -> str | None:
    tools = _repo_root() / "tools"
    if not tools.exists():
        return None

    candidates: list[Path] = []
    for base in (tools / "cppcheck", tools / "mingw64"):
        if base.exists():
            candidates.extend(list(base.rglob("cppcheck.exe")))

    if not candidates:
        return None

    best = min(candidates, key=lambda p: (len(str(p)), str(p).lower()))
    return str(best)


def _build_tool_env(*, cppcheck_path: str | None) -> dict[str, str]:
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


def run_static_checks(project_root: Path) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    meta: dict = {}

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
        for pro in pro_files:
            txt = read_text_best_effort(pro)
            info = extract_pro_info(txt)
            meta.setdefault("pro", []).append({"file": str(pro), "info": info})

            if "TEMPLATE" not in info:
                findings.append(
                    Finding(
                        category="static",
                        severity="info",
                        title=f"{pro.name} 未显式声明 TEMPLATE",
                        file=str(pro),
                    )
                )

    # 基础规则扫描（无外部依赖）
    sources = iter_files(project_root, ("**/*.h", "**/*.hpp", "**/*.cpp", "**/*.cxx"))
    meta["source_file_count"] = len(sources)

    for p in sources:
        text = read_text_best_effort(p)

        # 规则：疑似未关闭的 TODO/FIXME
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

        # 规则：using namespace std（示例规则，可按课程要求调整）
        if re.search(r"^\s*using\s+namespace\s+std\s*;", text, re.M):
            findings.append(
                Finding(
                    category="static",
                    severity="warning",
                    title="使用 using namespace std;（建议限定作用域）",
                    file=str(p),
                )
            )

        # 规则：Q_OBJECT 缺少 moc 相关 include 的常见误用（弱提示）
        if "Q_OBJECT" in text and p.suffix in {".cpp", ".cxx"}:
            findings.append(
                Finding(
                    category="static",
                    severity="info",
                    title="在 .cpp 中检测到 Q_OBJECT（确认 moc 配置正常）",
                    file=str(p),
                )
            )

        # 规则：异常捕获裸 catch(...)（弱提示）
        if re.search(r"catch\s*\(\s*\.\.\.\s*\)", text):
            findings.append(
                Finding(
                    category="static",
                    severity="warning",
                    title="检测到 catch(...)（建议记录并分类处理）",
                    file=str(p),
                )
            )

    # 可选：cppcheck
    cppcheck = _find_cppcheck_in_tools() or which("cppcheck")
    meta["cppcheck_found"] = bool(cppcheck)
    meta["cppcheck_path"] = cppcheck
    if cppcheck:
        try:
            proc = subprocess.run(
                [cppcheck, "--enable=all", "--inconclusive", "--quiet", str(project_root)],
                capture_output=True,
                text=True,
                timeout=180,
                env=_build_tool_env(cppcheck_path=cppcheck),
            )
            # cppcheck 输出在 stderr
            out = (proc.stderr or "").strip()
            if out:
                # 落盘完整报告，便于定位与提交作业
                report_dir = Path.home() / ".qt_test_ai" / "cppcheck_reports" / project_root.name
                report_dir.mkdir(parents=True, exist_ok=True)
                report_path = report_dir / "cppcheck.txt"
                try:
                    report_path.write_text(out, encoding="utf-8")
                    meta["cppcheck_report_path"] = str(report_path)
                except Exception:
                    # ignore file write issues; keep in meta only
                    pass

                # 避免 UI/报告被刷爆：只展示前 N 行，并提示已落盘
                max_lines = 200
                lines = out.splitlines()
                shown = lines[:max_lines]
                if meta.get("cppcheck_report_path"):
                    findings.append(
                        Finding(
                            category="static",
                            severity="warning",
                            title="cppcheck 报告已生成",
                            details=f"已保存到：{meta['cppcheck_report_path']}\n\n以下仅展示前 {min(len(lines), max_lines)} 行：",
                            rule_id="cppcheck",
                        )
                    )

                for line in shown:
                    findings.append(
                        Finding(
                            category="static",
                            severity="warning",
                            title="cppcheck 报告",
                            details=line,
                            rule_id="cppcheck",
                        )
                    )
                if len(lines) > max_lines:
                    findings.append(
                        Finding(
                            category="static",
                            severity="info",
                            title="cppcheck 输出过长已截断",
                            details=f"共 {len(lines)} 行，界面仅展示前 {max_lines} 行；完整内容见 cppcheck_report_path。",
                            rule_id="cppcheck",
                        )
                    )
        except Exception as e:
            findings.append(
                Finding(
                    category="static",
                    severity="warning",
                    title="cppcheck 执行失败",
                    details=str(e),
                )
            )

    return findings, meta
