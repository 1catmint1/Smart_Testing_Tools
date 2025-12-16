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

    sys_prompt = load_llm_system_prompt_from_env() or (
        "你是软件测试助手。请只输出严格 JSON，不要输出多余文字。"
    )

    ctx = build_project_context(project_root)
    prompt = (
        "请为该 Qt 项目生成 QtTest 单元测试/GUI 测试用例（尽量采用黑盒定位控件方式）。\n"
        "输出 JSON 对象，包含字段：\n"
        "- out_dir: 生成的测试目录（相对 project_root）\n"
        "- files: 生成/修改的文件路径列表（相对 project_root）\n"
        "- build_hints: 编译/运行提示\n"
        "- patches: 数组，每项包含 path 和 content（文件内容全文）\n\n"
        f"项目上下文：\n{ctx}\n"
    )

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        text = chat_completion_text(cfg, messages=messages)
        meta["llm_raw"] = _truncate(text, 9000)
    except Exception as e:
        findings.append(
            Finding(
                category="testgen",
                severity="error",
                title="LLM 调用失败",
                details=str(e),
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
                details=_truncate(str(e) + "\n\nRAW:\n" + (meta.get("llm_raw") or ""), 9000),
            )
        )
        meta["error"] = "llm_json_parse_failed"
        return findings, meta

    out_dir = str(payload.get("out_dir") or "tests/auto").strip()
    patches = payload.get("patches") or []

    # ✅ 兼容 LLM 输出 files[]
    if not patches and isinstance(payload.get("files"), list):
        for f in payload["files"]:
            if not isinstance(f, dict):
                continue
            name = f.get("name")
            content = f.get("content")
            if name and content:
                patches.append({
                    "path": name,
                    "content": content
                })

    files = payload.get("files") or []
    build_hints = payload.get("build_hints") or ""

    meta["out_dir"] = out_dir
    meta["files"] = files
    meta["build_hints"] = build_hints

    # Apply patches
    applied: list[str] = []
    out_abs = project_root / out_dir
    out_abs.mkdir(parents=True, exist_ok=True)

    if isinstance(patches, list):
        for it in patches:
            if not isinstance(it, dict):
                continue
            p = str(it.get("path") or "").strip()
            c = str(it.get("content") or "")
            if not p:
                continue
            abs_path = (project_root / p).resolve()
            # ensure inside project_root
            try:
                abs_path.relative_to(project_root.resolve())
            except Exception:
                continue
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(c, encoding="utf-8", errors="replace")
            applied.append(p)

    if applied:
        findings.append(
            Finding(
                category="testgen",
                severity="info",
                title=f"已生成/更新 QtTest 文件：{len(applied)} 个",
                details="\n".join(applied),
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
    return findings, meta


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
