from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .llm import chat_completion_text, load_llm_config_from_env, load_llm_system_prompt_from_env
from .models import Finding
from .qt_project import build_project_context


# =========================================================
# Helpers
# =========================================================
def _truncate(s: str, max_len: int = 6000) -> str:
    s = s or ""
    if len(s) <= max_len:
        return s
    return s[: max_len - 20] + "\n...(truncated)...\n"


def _safe_name(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^\w\-.]+", "_", s)
    return s or "project"


def _extract_json_object(text: str) -> str:
    """
    Extract the first {...} JSON object from LLM output.
    """
    if not text:
        return "{}"
    m = re.search(r"\{.*\}", text, flags=re.S)
    return m.group(0) if m else "{}"


def _run_shell_cmd(cmd: str, cwd: Path, timeout_s: float = 600.0) -> dict:
    """
    Run a shell command and capture stdout/stderr. Works on Windows and POSIX.
    """
    meta: dict = {"cmd": cmd, "cwd": str(cwd), "timeout_s": timeout_s}
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            errors="replace",
        )
        meta["returncode"] = p.returncode
        meta["stdout"] = p.stdout or ""
        meta["stderr"] = p.stderr or ""
        meta["timed_out"] = False
    except subprocess.TimeoutExpired as e:
        meta["returncode"] = -1
        meta["stdout"] = (getattr(e, "stdout", "") or "")
        meta["stderr"] = (getattr(e, "stderr", "") or "") + "\nTIMEOUT"
        meta["timed_out"] = True
    except Exception as e:
        meta["returncode"] = -1
        meta["stdout"] = ""
        meta["stderr"] = str(e)
        meta["timed_out"] = False
        meta["error"] = "exception"
    return meta


# =========================================================
# Stage report (saved under tool root ./reports)
# =========================================================
def _tool_root_dir() -> Path:
    """
    test_automation.py is under: <tool_root>/src/qt_test_ai/test_automation.py
    so parents[2] is <tool_root>.
    """
    return Path(__file__).resolve().parents[2]


def _finding_to_dict(f: Any) -> dict:
    # dataclass safe
    try:
        if hasattr(f, "__dataclass_fields__"):
            return asdict(f)
    except Exception:
        pass
    d = {}
    for k in ("category", "severity", "title", "details", "file", "line", "col", "rule_id"):
        if hasattr(f, k):
            d[k] = getattr(f, k)
    return d


def save_stage_report(
    *,
    project_root: Path,
    stage: str,
    findings: list[Finding],
    meta: dict,
    run_ts: str | None = None,
) -> dict:
    """
    Save per-stage report to:
      <tool_root>/reports/stage_reports/<project>/<run_ts>/<stage>_report.json|txt
    """
    ts = run_ts or datetime.now().strftime("%Y%m%d_%H%M%S")

    tool_root = _tool_root_dir()
    base_dir = tool_root / "reports"

    out_dir = base_dir / "stage_reports" / _safe_name(project_root.name) / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "stage": stage,
        "project_root": str(project_root),
        "created_at": ts,
        "meta": meta or {},
        "findings": [_finding_to_dict(f) for f in (findings or [])],
    }

    json_path = out_dir / f"{stage}_report.json"
    txt_path = out_dir / f"{stage}_report.txt"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # txt: human-friendly
    lines: list[str] = []
    lines.append(f"[stage] {stage}")
    lines.append(f"[project] {project_root}")
    lines.append(f"[time] {ts}")
    if meta:
        for k in ("cmd", "cwd", "returncode", "timed_out", "timeout_s", "summary", "coverage_summary", "out_dir", "files"):
            if k in meta:
                lines.append(f"[meta] {k}: {meta.get(k)}")
    lines.append("")
    lines.append("== findings ==")
    for f in (findings or []):
        fd = _finding_to_dict(f)
        lines.append(f"- {fd.get('category')} | {fd.get('severity')} | {fd.get('title')}")
    lines.append("")

    # truncate stdout/stderr in txt (full already in json)
    if meta:
        if meta.get("stdout"):
            lines.append("== stdout (truncated) ==")
            lines.append(_truncate(str(meta.get("stdout")), 6000))
        if meta.get("stderr"):
            lines.append("== stderr (truncated) ==")
            lines.append(_truncate(str(meta.get("stderr")), 6000))

    txt_path.write_text("\n".join(lines), encoding="utf-8")

    return {"out_dir": str(out_dir), "json": str(json_path), "txt": str(txt_path), "ts": ts}


# =========================================================
# Automation: generate QtTest via LLM
# =========================================================
def generate_qttest_via_llm(project_root: Path) -> tuple[list[Finding], dict]:
    import re  # Import at function level to avoid UnboundLocalError
    findings: list[Finding] = []
    meta: dict = {"project_root": str(project_root)}

    cfg = load_llm_config_from_env()
    if cfg is None:
        findings.append(
            Finding(
                category="testgen",
                severity="warning",
                title="未配置 LLM，无法生成 QtTest 用例",
                details="请设置 QT_TEST_AI_LLM_BASE_URL / QT_TEST_AI_LLM_MODEL / (可选)QT_TEST_AI_LLM_API_KEY",
            )
        )
        meta["skipped"] = True
        return findings, meta

    # Configurable limits
    try:
        limit_files = int(os.getenv("QT_TEST_AI_TESTGEN_FILE_LIMIT", "2"))
    except ValueError:
        limit_files = 2
        
    try:
        limit_cases = int(os.getenv("QT_TEST_AI_TESTGEN_CASE_LIMIT", "10"))
    except ValueError:
        limit_cases = 10

    sys_prompt = load_llm_system_prompt_from_env() or (
        "你是软件测试助手。请只输出严格 JSON，不要输出多余文字。"
    )

    # ==========================
    # STAGE 1: PLANNING
    # ==========================
    # For planning, only send file paths (not content) to keep prompt small
    ctx_obj = build_project_context(project_root)
    file_list_str = "\n".join([f"  - {p.name}" for p in ctx_obj.selected_files[:20]])
    
    plan_prompt = (
        "你是一个高级 Qt 测试架构师。请根据下面的 Qt 项目文件列表，规划一个 QtTest 测试套件。\n"
        f"目标：生成 {limit_files} 个测试文件（测试类），总计覆盖约 {limit_cases} 个测试用例。\n"
        "‼️ 关键要求：\n"
        "1. 必须包含一个工程文件，路径必须是 tests/generated/tests.pro（不能用其他名称！）\n"
        "2. 测试 .cpp 文件放在 tests/generated/ 目录下（不要放到 tests/ 根目录，避免与原有测试混淆）\n"
        "请只输出一个 JSON 对象，包含字段 `files`，它是要生成的测试文件路径列表。\n"
        "例如：{\"files\": [\"tests/generated/test_foo.cpp\", \"tests/generated/tests.pro\"]}\n"
        "注意：只列出路径，不要生成代码！回复尽量简短。\n\n"
        f"项目名称：{project_root.name}\n"
        f"主要源文件：\n{file_list_str}\n"
    )
    
    plan_messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": plan_prompt},
    ]

    plan_text = ""
    try:
        plan_text = chat_completion_text(cfg, messages=plan_messages)
        try:
            plan_json = _parse_json_from_llm(plan_text)
            target_files = plan_json.get("files", [])
        except Exception:
            # Fallback: regex extraction for paths found in text
            # Look for strings like "tests/generated/test_foo.cpp"
            # Matches quoted strings containing "tests/" and ending in .cpp/.pro
            fallback_pattern = r'["\'](tests/(?:generated/)?[^"\']+\.(?:cpp|pro))["\']'
            target_files = re.findall(fallback_pattern, plan_text)
            if not target_files:
                # Try simpler pattern without quotes if it's a list
                fallback_pattern_simple = r'(tests/(?:generated/)?[\w\-/]+\.(?:cpp|pro))'
                target_files = re.findall(fallback_pattern_simple, plan_text)
            
            # De-dupe
            target_files = list(set(target_files))
            
        if not isinstance(target_files, list) or not target_files:
            raise ValueError("Could not extract any file paths from LLM response (JSON failed, regex failed).")
        
        # CRITICAL: Always ensure tests/generated/tests.pro is in the list (LLM often forgets)
        pro_file = "tests/generated/tests.pro"
        if pro_file not in target_files:
            target_files.append(pro_file)
            
        # Enforce limit just in case LLM ignored it
        target_files = target_files[:limit_files]
        
        # But always keep .pro file even if over limit
        if pro_file not in target_files:
            target_files.append(pro_file)
        
    except Exception as e:
        error_detail = str(e)
        if plan_text:
            # Truncate manually (first 500 chars)
            preview = plan_text[:500] + "..." if len(plan_text) > 500 else plan_text
            error_detail = f"{error_detail}\nLLM Response Preview: {preview}"
        findings.append(Finding("testgen", "error", "测试规划阶段失败", error_detail))
        meta["error"] = f"Plan failed: {e}"
        return findings, meta

    # ==========================
    # STAGE 2: GENERATION (Iterative)
    # ==========================
    generated_patches = []
    
    for i, file_path in enumerate(target_files):
        # Progress (estimated)
        # In a real async worker we'd emit signals, but here we run blocking in the worker thread.
        
        file_prompt = (
            f"你是 Qt 测试专家。请为 {file_path} 生成完整的 C++ 测试代码。\n"
            f"这是计划中的第 {i+1}/{len(target_files)} 个文件。\n"
            "‼️ 关键要求：\n"
            "1. 如果是 .pro 文件：\n"
            "   - 必须使用 QT += testlib widgets（不是 gui！QGraphicsItem 类在 QtWidgets 模块）\n"
            "   - 必须显式包含源文件路径（SOURCES += ../xxx.cpp）和 INCLUDEPATH += ..\n"
            "2. 如果是 .cpp 测试文件：\n"
            "   - 必须包含 QTEST_MAIN 和所有必要的 #include\n"
            "   - 必须包含完整的 Qt 头文件，例如 #include <QMenu>, #include <QGraphicsScene> 等\n"
            "   - 不要依赖前向声明，直接 #include 完整头文件\n"
            "3. 只输出一个 JSON 对象：{ \"path\": \"...\", \"content\": \"...\" }。\n"
            f"项目上下文：\n{ctx_obj.prompt_text}\n"
        )
        
        file_msgs = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": file_prompt},
        ]
        
        try:
            gen_text = chat_completion_text(cfg, messages=file_msgs)
            gen_json = _parse_json_from_llm(gen_text)
            
            # Allow LLM to return a list of files (e.g. .cpp + .pro) or a single object
            if isinstance(gen_json, list):
                generated_patches.extend(gen_json)
            elif isinstance(gen_json, dict) and "path" in gen_json and "content" in gen_json:
                generated_patches.append(gen_json)
            else:
                 # Fallback if LLM returns structure from previous prompt version
                if "patches" in gen_json:
                     generated_patches.extend(gen_json["patches"])
                elif "files" in gen_json: # Handle case where it returns {"files": [...]}
                     generated_patches.extend(gen_json["files"])
                else:
                    findings.append(Finding("testgen", "warning", f"生成文件结构无法识别: {file_path}", f"Keys found: {list(gen_json.keys()) if isinstance(gen_json, dict) else type(gen_json)}"))

        except Exception as e:
            findings.append(Finding("testgen", "warning", f"生成文件失败: {file_path}", str(e)))

    # ==========================
    # FINALIZE
    # ==========================
    out_dir = Path("tests/generated")  # Generated tests go to tests/generated/ to avoid mixing with existing tests
    
    # Normalize patches: ensure each has 'path' and 'content' keys
    normalized_patches = []
    for patch in generated_patches:
        if isinstance(patch, dict):
            # Try different key names for path
            file_path = patch.get("path") or patch.get("name") or patch.get("file") or "unknown"
            content = patch.get("content") or patch.get("code") or patch.get("body") or ""
            normalized_patches.append({"path": file_path, "content": content})
    
    # CRITICAL: If no tests/tests.pro was generated, create a fallback one
    pro_files = [p for p in normalized_patches if p["path"].endswith(".pro")]
    cpp_files = [p for p in normalized_patches if p["path"].endswith(".cpp")]
    
    has_tests_pro = any(p["path"] == "tests/generated/tests.pro" or p["path"] == "tests/tests.pro" for p in pro_files)
    
    if not has_tests_pro and cpp_files:
        # Generate a minimal but valid tests.pro
        cpp_sources = " \\\n           ".join([Path(p["path"]).name for p in cpp_files])
        fallback_pro = f"""QT += testlib widgets
TEMPLATE = app
TARGET = test_generated
CONFIG += console c++17
CONFIG -= app_bundle

SOURCES += {cpp_sources}

# Include project source files (two levels up from tests/generated/)
SOURCES += ../../diagramitem.cpp \\
           ../../diagramtextitem.cpp \\
           ../../diagramitemgroup.cpp \\
           ../../deletecommand.cpp \\
           ../../arrow.cpp \\
           ../../diagrampath.cpp \\
           ../../diagramscene.cpp \\
           ../../findreplacedialog.cpp

INCLUDEPATH += ../..
DEFINES += QT_DEPRECATED_WARNINGS
"""
        normalized_patches.append({"path": "tests/generated/tests.pro", "content": fallback_pro})
        findings.append(Finding("testgen", "info", "已自动生成 tests.pro 兜底文件", 
                                 f"包含 {len(cpp_files)} 个测试文件"))
    
    # Analyze generated files for stats
    total_cases_approx = 0
    for patch in normalized_patches:
        content = patch.get("content", "")
        # Count "private slots:" ... "void test..."
        # Simplified regex for QQtTest slots
        total_cases_approx += len(re.findall(r"void\s+test\w+\s*\(\s*\)", content))

    report = {
        "out_dir": str(out_dir),
        "files": [p["path"] for p in normalized_patches],
        "patches": normalized_patches,
        "stats": {
            "files_generated": len(normalized_patches),
            "cases_approx": total_cases_approx
        }
    }
    
    meta["llm_output"] = report
    patches = normalized_patches  # Use normalized patches with guaranteed 'path' and 'content' keys

    # Apply patches and count stats
    applied: list[str] = []
    total_cases_count = 0
    
    out_abs = project_root / out_dir
    out_abs.mkdir(parents=True, exist_ok=True)

    # ===========================
    # POST-PROCESSING: Fix common LLM errors in test code
    # ===========================
    def _postprocess_test_code(content: str, file_path: str) -> str:
        """Fix common LLM-generated test code errors."""
        if not file_path.endswith(".cpp"):
            return content
        
        lines = content.split('\n')
        processed_lines = []
        includes_added = set()
        
        # Check what includes are needed
        needs_qmenu = "QMenu" in content and "#include <QMenu>" not in content
        needs_qstyleoption = "QStyleOptionGraphicsItem" in content and "#include <QStyleOptionGraphicsItem>" not in content
        needs_qpixmap = "QPixmap" in content and "#include <QPixmap>" not in content
        
        for i, line in enumerate(lines):
            # Add missing includes after #include <QtTest>
            if line.strip().startswith("#include <QtTest>"):
                processed_lines.append(line)
                if needs_qmenu and "QMenu" not in includes_added:
                    processed_lines.append("#include <QMenu>")
                    includes_added.add("QMenu")
                if needs_qstyleoption and "QStyleOptionGraphicsItem" not in includes_added:
                    processed_lines.append("#include <QStyleOptionGraphicsItem>")
                    includes_added.add("QStyleOptionGraphicsItem")
                if needs_qpixmap and "QPixmap" not in includes_added:
                    processed_lines.append("#include <QPixmap>")
                    includes_added.add("QPixmap")
                continue
            
            # Fix member variable used as function: item->textItem() -> item->textItem
            # Pattern: ->memberName() where memberName is a known member variable
            fixed_line = line
            for member_var in ["textItem", "myContextMenu", "myDiagramType", "myColor", "m_color", "m_scene", "m_item"]:
                # Fix pattern: ->member() with no arguments (accessing as function)
                pattern = rf"->{member_var}\(\s*\)"  # Matches ->textItem()
                replacement = f"->{member_var}"
                fixed_line = re.sub(pattern, replacement, fixed_line)
            
            processed_lines.append(fixed_line)
        
        return '\n'.join(processed_lines)
    
    # Apply post-processing to all patches
    for patch in patches:
        if "content" in patch and "path" in patch:
            patch["content"] = _postprocess_test_code(patch["content"], patch["path"])

    if isinstance(patches, list):
        for it in patches:
            if not isinstance(it, dict):
                continue
            p = str(it.get("path") or "").strip()

            c = str(it.get("content") or "")
            if not p:
                continue
            
            # Count test cases in this file (approximate regex for QtTest slots)
            # Matches: void test...(); or void test...() {
            case_matches = re.findall(r"void\s+test\w+\s*\(\s*\)", c, re.IGNORECASE)
            num_cases = len(case_matches)
            total_cases_count += num_cases
            
            try:
                abs_path = (project_root / p).resolve()
                # ensure inside project_root
                try:
                    abs_path.relative_to(project_root.resolve())
                except Exception:
                    pass # Allow flexible paths if needed, or enforce strict check
                
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                abs_path.write_text(c, encoding="utf-8", errors="replace")
                applied.append(f"{p} ({num_cases} cases)")
            except Exception as e:
                applied.append(f"{p} [Error: {e}]")

    if applied:
        findings.append(
            Finding(
                category="testgen",
                severity="info",
                title=f"已生成 QtTest：{len(applied)} 个文件，共约 {total_cases_count} 个用例",
                details="生成文件明细：\n" + "\n".join(applied),
            )
        )
    else:
        findings.append(
            Finding(
                category="testgen",
                severity="warning",
                title="未写入任何 QtTest 文件（LLM 输出为空或不合法）",
                details=_truncate(meta.get("llm_raw") or "", 9000),
            )
        )

    meta["applied"] = applied
    meta["total_cases_count"] = total_cases_count
    return findings, meta


def _parse_json_from_llm(text: str):
    """
    Robustly extract and parse JSON from LLM output.
    Handles markdown code blocks and extra text before/after JSON.
    """
    import json
    
    text = text.strip()
    
    # Remove markdown code blocks
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    # Find the first { or [ and extract balanced JSON
    start_idx = -1
    open_char = None
    close_char = None
    
    for i, c in enumerate(text):
        if c == '{':
            start_idx = i
            open_char, close_char = '{', '}'
            break
        elif c == '[':
            start_idx = i
            open_char, close_char = '[', ']'
            break
    
    if start_idx == -1:
        raise ValueError("No JSON object or array found in LLM response")
    
    # Count balanced braces/brackets to find end
    depth = 0
    in_string = False
    escape_next = False
    end_idx = start_idx
    
    for i in range(start_idx, len(text)):
        c = text[i]
        
        if escape_next:
            escape_next = False
            continue
        
        if c == '\\':
            escape_next = True
            continue
        
        if c == '"':
            in_string = not in_string
            continue
        
        if in_string:
            continue
        
        if c == open_char:
            depth += 1
        elif c == close_char:
            depth -= 1
            if depth == 0:
                end_idx = i + 1
                break
    
    json_str = text[start_idx:end_idx]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parse failed: {e}. Extracted string: {repr(json_str)}")


# =========================================================
# Automation: run tests
# =========================================================
def run_test_command(project_root: Path) -> tuple[list[Finding], dict]:
    cmd = (os.getenv("QT_TEST_AI_TEST_CMD") or "").strip()
    timeout_raw = (os.getenv("QT_TEST_AI_TEST_TIMEOUT_S") or "600").strip() or "600"
    try:
        timeout_s = float(timeout_raw)
    except Exception:
        timeout_s = 600.0

    if not cmd:
        return (
            [
                Finding(
                    category="tests",
                    severity="warning",
                    title="未配置测试命令，跳过测试执行",
                    details="设置环境变量 QT_TEST_AI_TEST_CMD，例如：ctest -C Debug",
                )
            ],
            {"skipped": True},
        )

    meta = _run_shell_cmd(cmd, cwd=project_root, timeout_s=timeout_s)

    combined = (meta.get("stdout") or "") + "\n" + (meta.get("stderr") or "")
    sev = "info" if meta.get("returncode") == 0 else "error"
    if meta.get("timed_out"):
        sev = "error"
    findings = [
        Finding(
            category="tests",
            severity=sev,  # type: ignore[arg-type]
            title="测试命令执行完成" if sev == "info" else "测试命令执行失败",
            details=_truncate(combined, 9000),
        )
    ]
    return findings, meta


# =========================================================
# Automation: run coverage + extract summary
# =========================================================
def _parse_gcovr_summary(text: str) -> dict:
    """
    Parse common gcovr --txt output.
    Example lines:
      lines: 85.7% (1234 out of 1440)
      functions: 90.0% (90 out of 100)
      branches: 70.0% (140 out of 200)
    """
    out: dict[str, Any] = {}

    def grab(key: str) -> str | None:
        m = re.search(rf"{key}\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*%", text, flags=re.I)
        return m.group(1) + "%" if m else None

    out["lines"] = grab("lines")
    out["functions"] = grab("functions")
    out["branches"] = grab("branches")
    return out


def run_coverage_command(project_root: Path) -> tuple[list[Finding], dict]:
    cmd = (os.getenv("QT_TEST_AI_COVERAGE_CMD") or "").strip()
    timeout_raw = (os.getenv("QT_TEST_AI_COVERAGE_TIMEOUT_S") or "600").strip() or "600"
    try:
        timeout_s = float(timeout_raw)
    except Exception:
        timeout_s = 600.0

    if not cmd:
        return (
            [
                Finding(
                    category="coverage",
                    severity="info",
                    title="未配置覆盖率命令，跳过覆盖率检测",
                    details="设置环境变量 QT_TEST_AI_COVERAGE_CMD，例如：gcovr -r . --txt",
                )
            ],
            {"skipped": True},
        )

    meta = _run_shell_cmd(cmd, cwd=project_root, timeout_s=timeout_s)

    combined = (meta.get("stdout") or "") + "\n" + (meta.get("stderr") or "")

    # --- Extract coverage summary (prefer gcovr style) ---
    cov = _parse_gcovr_summary(combined)
    if any(v for v in cov.values()):
        meta["coverage_summary"] = cov
        # prioritize lines as "summary"
        if cov.get("lines"):
            meta["summary"] = cov["lines"]
    else:
        # fallback: first percentage
        m = re.search(r"(\d{1,3}(?:\.\d+)?%)", combined)
        if m:
            meta["summary"] = m.group(1)

    sev = "info" if meta.get("returncode") == 0 else "error"
    if meta.get("timed_out"):
        sev = "error"

    findings: list[Finding] = []

    # ✅ 关键：把汇总作为一条 Finding，让 UI 表格直接显示
    cov_sum = meta.get("coverage_summary") or {}
    if cov_sum and sev == "info":
        parts = []
        if cov_sum.get("lines"):
            parts.append(f"lines {cov_sum['lines']}")
        if cov_sum.get("branches"):
            parts.append(f"branches {cov_sum['branches']}")
        if cov_sum.get("functions"):
            parts.append(f"functions {cov_sum['functions']}")
        title = "覆盖率汇总：" + (" | ".join(parts) if parts else str(meta.get("summary") or ""))
        findings.append(
            Finding(
                category="coverage",
                severity="info",
                title=title,
                details="（来自覆盖率命令输出解析）",
            )
        )
    elif meta.get("summary") and sev == "info":
        findings.append(
            Finding(
                category="coverage",
                severity="info",
                title=f"覆盖率汇总：{meta.get('summary')}",
                details="（来自覆盖率命令输出解析）",
            )
        )

    # 原始执行结果 Finding
    findings.append(
        Finding(
            category="coverage",
            severity=sev,  # type: ignore[arg-type]
            title="覆盖率命令执行完成" if sev == "info" else "覆盖率命令执行失败",
            details=_truncate(combined, 9000),
        )
    )

    return findings, meta
