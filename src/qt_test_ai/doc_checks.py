from __future__ import annotations

import re
from pathlib import Path

from .models import Finding
from .utils import iter_files, read_text_best_effort


_DOC_NAMES = (
    "README.md",
    "readme.md",
    "README.txt",
    "使用说明.md",
    "用户手册.md",
)


def run_doc_checks(project_root: Path) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    meta: dict = {}

    # 找用户文档
    doc_paths: list[Path] = []
    for name in _DOC_NAMES:
        p = project_root / name
        if p.exists():
            doc_paths.append(p)

    # 也支持 docs/ 目录
    docs_dir = project_root / "docs"
    if docs_dir.exists() and docs_dir.is_dir():
        doc_paths.extend(iter_files(docs_dir, ("**/*.md", "**/*.txt")))
    
    # 查找文件名中包含"文档"的 .doc/.docx 文件
    for p in project_root.rglob("*.doc*"):
        if "文档" in p.name and p.is_file():
            doc_paths.append(p)
    
    # 也查找 project_root 下的任何 .doc/.docx 文件
    for doc_file in project_root.glob("*.doc*"):
        if doc_file.is_file() and doc_file not in doc_paths:
            doc_paths.append(doc_file)

    doc_paths = sorted({p.resolve(): p for p in doc_paths}.values(), key=lambda x: str(x).lower())
    meta["doc_files"] = [str(p) for p in doc_paths]

    if not doc_paths:
        findings.append(
            Finding(
                category="docs",
                severity="error",
                title="未发现用户文档（README/使用说明/用户手册）",
                details="建议至少提供：安装/运行/主要功能/快捷键或菜单/常见问题/联系方式。",
            )
        )
        return findings, meta

    # 简单完整性检查
    required_keywords = [
        ("安装", "安装/环境"),
        ("运行", "运行/启动"),
        ("功能", "主要功能"),
    ]

    for p in doc_paths:
        text = read_text_best_effort(p)
        lower = text.lower()

        for kw, desc in required_keywords:
            if kw.lower() not in lower and kw not in text:
                findings.append(
                    Finding(
                        category="docs",
                        severity="warning",
                        title=f"文档缺少：{desc}",
                        file=str(p),
                        details=f"未检测到关键字：{kw}",
                    )
                )

        # 检查是否有截图/示例
        if not re.search(r"!\[[^\]]*\]\([^\)]+\)", text) and "示例" not in text:
            findings.append(
                Finding(
                    category="docs",
                    severity="info",
                    title="建议增加截图或操作示例",
                    file=str(p),
                )
            )

        # 超长行（可读性）
        long_lines = [i for i, line in enumerate(text.splitlines(), start=1) if len(line) > 180]
        if long_lines:
            findings.append(
                Finding(
                    category="docs",
                    severity="info",
                    title="文档存在较长行（影响阅读）",
                    file=str(p),
                    details=f"行号示例：{', '.join(map(str, long_lines[:10]))}",
                )
            )

    return findings, meta


def run_llm_doc_checks(project_root: Path, llm_cfg, doc_content: str, project_context: str) -> list[Finding]:
    """
    Use LLM to check if project documentation is consistent with the actual project.
    
    Args:
        project_root: Path to the project root
        llm_cfg: LLM configuration from load_llm_config_from_env()
        doc_content: Combined content of all documentation files
        project_context: Project structure and source code context
        
    Returns:
        List of findings from the LLM analysis
    """
    from .llm import chat_completion_text
    
    findings: list[Finding] = []
    
    if not llm_cfg:
        return findings
    
    if not doc_content.strip():
        return findings
    
    sys_prompt = "你是文档审核专家。请检查文档与项目内容是否一致，只输出严格JSON数组。"
    user_prompt = f"""请检查以下项目文档是否与项目实际内容一致。

== 项目文档内容 ==
{doc_content[:5000]}

== 项目结构与源码概要 ==
{project_context[:5000]}

请检查并找出以下问题：
1. 文档中提到的功能，但项目代码中不存在
2. 项目代码有的功能，但文档未说明
3. 文档中的API/类/函数名称与代码不一致
4. 版本号或其他关键信息过时

只输出一个 JSON 数组，每项包含：
- severity: "error" | "warning" | "info"
- title: 问题标题
- details: 详细说明

如果没有问题，返回空数组 []。
"""

    try:
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = chat_completion_text(llm_cfg, messages=messages)
        
        import json
        import re
        
        # Try to extract JSON from markdown code blocks
        md_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
        if md_match:
            response = md_match.group(1).strip()
        
        items = json.loads(response)
        if not isinstance(items, list):
            items = []
        
        for it in items:
            if not isinstance(it, dict):
                continue
            findings.append(
                Finding(
                    category="docs",
                    severity=str(it.get("severity", "info")),
                    title=str(it.get("title", "文档一致性问题")),
                    details=str(it.get("details", "")),
                )
            )
            
    except Exception as e:
        # If LLM fails, just log it but don't block
        findings.append(
            Finding(
                category="docs",
                severity="info",
                title="LLM 文档检查失败",
                details=f"错误：{e}",
            )
        )
    
    return findings
