from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


UsabilityStatus = Literal["pass", "fail", "na"]


@dataclass
class UsabilityItem:
    item_id: str
    title: str
    guidance: str = ""


def default_checklist() -> list[UsabilityItem]:
    # 适配桌面 Qt 应用的通用易用性检查项（可按课程/项目需求增删）
    return [
        UsabilityItem(
            item_id="U01",
            title="主界面入口清晰（首次打开能快速知道怎么开始）",
            guidance="检查：是否有明显的菜单/工具栏/新建按钮/空态提示。",
        ),
        UsabilityItem(
            item_id="U02",
            title="常用操作可在 2-3 次点击内完成",
            guidance="检查：创建/编辑/删除/保存等高频流程。",
        ),
        UsabilityItem(
            item_id="U03",
            title="错误提示可理解且可恢复（不只给错误防止/崩溃）",
            guidance="检查：非法输入、文件不存在、权限不足等场景。",
        ),
        UsabilityItem(
            item_id="U04",
            title="撤销/重做（如项目功能涉及编辑）可用且符合预期",
            guidance="检查：Ctrl+Z/Ctrl+Y 或菜单项；无此功能可 N/A。",
        ),
        UsabilityItem(
            item_id="U05",
            title="快捷键/菜单命名一致且符合用户习惯",
            guidance="检查：复制/粘贴/保存/关闭等是否使用常规快捷键。",
        ),
        UsabilityItem(
            item_id="U06",
            title="交互反馈及时（点击后有响应，长任务有进度/忙碌提示）",
            guidance="检查：卡顿、无响应、阻塞 UI 等。",
        ),
        UsabilityItem(
            item_id="U07",
            title="文本可读性良好（字号、对比度、信息密度）",
            guidance="检查：关键按钮/提示语是否清晰。",
        ),
        UsabilityItem(
            item_id="U08",
            title="重要状态可见（保存状态、选中状态、模式状态）",
            guidance="检查：用户是否能知道当前处于什么模式/是否已保存。",
        ),
        UsabilityItem(
            item_id="U09",
            title="对误操作有防护（确认对话框/可撤销/回收站等）",
            guidance="检查：关闭未保存、删除、覆盖等。",
        ),
        UsabilityItem(
            item_id="U10",
            title="帮助信息可获得（README/帮助菜单/关于/版本信息）",
            guidance="检查：至少能找到项目名称、版本、使用入口。",
        ),
    ]


def normalize_status(text: str) -> UsabilityStatus:
    t = (text or "").strip().lower()
    if t in {"pass", "通过", "p"}:
        return "pass"
    if t in {"fail", "不通过", "f"}:
        return "fail"
    return "na"
