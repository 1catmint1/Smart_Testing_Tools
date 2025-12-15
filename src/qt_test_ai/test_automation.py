from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .llm import chat_completion_text, load_llm_config_from_env, load_llm_system_prompt_from_env
from .models import Finding
from .qt_project import build_project_context


def _safe_name(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", name.strip())
    return s.strip("_.") or "project"


def _truncate(s: str, n: int = 8000) -> str:
    if s is None:
        return ""
    s = str(s)
    return s if len(s) <= n else s[:n] + "\n... (truncated)"


def _extract_json_object(text: str) -> str:
    """Best-effort extract a JSON object from LLM output.

    Handles common cases like Markdown fences:
      ```json\n{...}\n```
    """

    s = (text or "").strip()

    # Strip Markdown fenced blocks if present
    if s.startswith("```"):
        # remove first fence line
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl + 1 :]
        # remove trailing fence
        if s.rstrip().endswith("```"):
            s = s.rstrip()[: -3].strip()

    # If still not pure JSON, try to extract the first JSON object by braces
    s2 = s.lstrip("\ufeff").strip()
    if s2.startswith("{") and s2.endswith("}"):
        return s2

    start = s2.find("{")
    end = s2.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s2[start : end + 1].strip()

    return s2


def generate_qttest_via_llm(project_root: Path) -> tuple[list[Finding], dict]:
    """Read Qt project code, ask LLM to generate QtTest-based C++ test files, write them to a safe local folder.

    Env:
      - QT_TEST_AI_LLM_BASE_URL / QT_TEST_AI_LLM_MODEL / QT_TEST_AI_LLM_API_KEY
    """

    findings: list[Finding] = []
    meta: dict = {}

    cfg = load_llm_config_from_env()
    if cfg is None:
        findings.append(
            Finding(
                category="testgen",
                severity="info",
                title="未配置 LLM，跳过自动生成测试用例",
                details="请设置：QT_TEST_AI_LLM_BASE_URL / QT_TEST_AI_LLM_MODEL / (可选)QT_TEST_AI_LLM_API_KEY",
            )
        )
        meta["skipped"] = True
        return findings, meta

    ctx = build_project_context(project_root)
    meta["selected_files"] = [str(p) for p in ctx.selected_files]
    meta["model"] = cfg.model

    sys_prompt = (
        load_llm_system_prompt_from_env()
        or "你是资深 C++/Qt 测试工程师。只输出严格 JSON，不要输出多余文字。"
    )

    # 要求 LLM 输出 JSON，便于落盘生成多个文件
    messages = [
        {"role": "system", "content": sys_prompt},
        {
            "role": "user",
            "content": (
                "请基于以下 Qt/C++ 工程代码片段，生成可编译的 QtTest(QTest) 单元测试源码文件。\n"
                "要求：\n"
                "1) 只输出严格 JSON 对象（不要 Markdown）。\n"
                "2) JSON 格式：{schema, files:[{name, content}], build_hints}。\n"
                "3) files 至少 1 个 .cpp，使用 <QtTest> / QTEST_MAIN / QObject 测试类。\n"
                "4) 尽量针对可测的非 UI 逻辑（工具类/数据结构/解析/业务函数）；若只能做 smoke，也可做最小可运行的占位测试并在 build_hints 说明依赖。\n"
                "5) 不要假设存在你没看到的类/函数；若必须假设，请在 build_hints 里写清楚。\n\n"
                "工程上下文如下：\n" + ctx.prompt_text
            ),
        },
    ]

    try:
        text = chat_completion_text(cfg, messages=messages)
    except Exception as e:
        findings.append(
            Finding(
                category="testgen",
                severity="error",
                title="LLM 请求失败（可能超时/网络问题）",
                details=_truncate(str(e), 9000),
            )
        )
        meta["error"] = "llm_request_failed"
        meta["error_details"] = str(e)
        return findings, meta

    try:
        payload = json.loads(_extract_json_object(text))
    except Exception as e:
        findings.append(
            Finding(
                category="testgen",
                severity="error",
                title="LLM 返回无法解析为 JSON",
                details=_truncate(
                    f"{e}\n\n提示：请确保 LLM 只输出 JSON（不要 ```json 代码块/不要额外解释文字）。\n\n原始输出：\n{text}",
                    9000,
                ),
            )
        )
        meta["error"] = "invalid_json"
        return findings, meta

    files = (payload or {}).get("files")
    if not isinstance(files, list) or not files:
        findings.append(
            Finding(
                category="testgen",
                severity="error",
                title="LLM 未返回任何测试文件",
                details=_truncate(text, 9000),
            )
        )
        meta["error"] = "no_files"
        return findings, meta

    out_dir = Path.home() / ".qt_test_ai" / "generated_tests" / _safe_name(project_root.name) / datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for f in files:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name") or "").strip()
        content = f.get("content")
        if not name or not isinstance(content, str) or not content.strip():
            continue
        if not name.lower().endswith((".cpp", ".h", ".hpp")):
            # keep only source-like outputs
            continue
        p = out_dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        written.append(str(p))

    meta["out_dir"] = str(out_dir)
    meta["files"] = written
    meta["build_hints"] = str((payload or {}).get("build_hints") or "")

    if not written:
        findings.append(
            Finding(
                category="testgen",
                severity="error",
                title="LLM 输出中没有可写入的 .cpp/.h 文件",
                details=_truncate(text, 9000),
            )
        )
        return findings, meta

    findings.append(
        Finding(
            category="testgen",
            severity="info",
            title="已生成 QtTest 测试用例文件",
            details=_truncate(f"输出目录：{out_dir}\n文件：\n" + "\n".join(written) + ("\n\nBuild hints：\n" + meta["build_hints"] if meta["build_hints"] else "")),
        )
    )

    return findings, meta


def _run_shell_cmd(cmd: str, *, cwd: Path, timeout_s: float) -> dict:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return {
            "cmd": cmd,
            "cwd": str(cwd),
            "returncode": proc.returncode,
            "stdout": _truncate(proc.stdout or "", 12000),
            "stderr": _truncate(proc.stderr or "", 12000),
        }
    except subprocess.TimeoutExpired as e:
        return {
            "cmd": cmd,
            "cwd": str(cwd),
            "returncode": None,
            "timed_out": True,
            "timeout_s": timeout_s,
            "stdout": _truncate(getattr(e, "stdout", "") or "", 12000),
            "stderr": _truncate(getattr(e, "stderr", "") or "", 12000),
        }


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
                    severity="info",
                    title="未配置测试命令，跳过自动执行测试",
                    details="设置环境变量 QT_TEST_AI_TEST_CMD，例如：ctest -C Debug",
                )
            ],
            {"skipped": True},
        )

    meta = _run_shell_cmd(cmd, cwd=project_root, timeout_s=timeout_s)
    sev = "info" if meta.get("returncode") == 0 else "error"
    if meta.get("timed_out"):
        sev = "error"
    findings = [
        Finding(
            category="tests",
            severity=sev,  # type: ignore[arg-type]
            title="测试命令执行完成" if sev == "info" else "测试命令执行失败",
            details=_truncate((meta.get("stdout") or "") + ("\n" + (meta.get("stderr") or "") if meta.get("stderr") else ""), 9000),
        )
    ]
    return findings, meta


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
    summary = ""
    # naive: capture first percentage like 78.12%
    m = re.search(r"(\d{1,3}(?:\.\d+)?%)", combined)
    if m:
        summary = m.group(1)
    if summary:
        meta["summary"] = summary

    sev = "info" if meta.get("returncode") == 0 else "error"
    if meta.get("timed_out"):
        sev = "error"
    findings = [
        Finding(
            category="coverage",
            severity=sev,  # type: ignore[arg-type]
            title="覆盖率命令执行完成" if sev == "info" else "覆盖率命令执行失败",
            details=_truncate(combined, 9000),
        )
    ]
    return findings, meta
