from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


CaseStatus = Literal["pass", "fail", "blocked", "na"]


@dataclass
class FunctionalCase:
    case_id: str
    title: str
    steps: list[str]
    expected: str
    tags: list[str] | None = None


@dataclass
class FunctionalCaseResult:
    case_id: str
    title: str
    steps: list[str]
    expected: str
    actual: str
    status: CaseStatus
    evidence: str = ""
    note: str = ""


def default_case_library() -> list[FunctionalCase]:
    return [
        FunctionalCase(
            case_id="F01",
            title="程序可正常启动并显示主窗口",
            steps=["启动程序", "观察是否出现主窗口"],
            expected="主窗口在合理时间内出现；无崩溃；界面可交互。",
            tags=["smoke"],
        ),
        FunctionalCase(
            case_id="F02",
            title="菜单栏/工具栏基础操作可用",
            steps=["点击主要菜单项", "尝试常用按钮"],
            expected="菜单/按钮可响应；无异常提示或崩溃。",
            tags=["ui"],
        ),
        FunctionalCase(
            case_id="F03",
            title="打开/保存（若项目具备）",
            steps=["执行打开/保存流程", "选择文件路径"],
            expected="文件选择对话框正常；保存后可再次打开并保持内容。",
            tags=["io"],
        ),
    ]


def library_to_json(cases: list[FunctionalCase]) -> dict[str, Any]:
    return {
        "schema": "qt_test_ai.functional_cases.v1",
        "cases": [asdict(c) for c in cases],
    }


def library_from_json(payload: dict[str, Any]) -> list[FunctionalCase]:
    raw_cases = payload.get("cases") or []
    out: list[FunctionalCase] = []
    for rc in raw_cases:
        out.append(
            FunctionalCase(
                case_id=str(rc.get("case_id") or rc.get("id") or "").strip(),
                title=str(rc.get("title") or "").strip(),
                steps=[str(s).strip() for s in (rc.get("steps") or []) if str(s).strip()],
                expected=str(rc.get("expected") or "").strip(),
                tags=list(rc.get("tags") or []) or None,
            )
        )
    # 过滤无 ID/标题
    return [c for c in out if c.case_id and c.title]


def load_case_library(path: Path) -> list[FunctionalCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = library_from_json(payload)
    return cases


def save_case_library(path: Path, cases: list[FunctionalCase]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = library_to_json(cases)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
