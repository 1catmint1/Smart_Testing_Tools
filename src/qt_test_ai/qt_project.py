from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from .utils import read_text_best_effort


_EXCLUDE_DIR_NAMES = {
    ".git",
    ".svn",
    ".hg",
    ".idea",
    ".vscode",
    ".vs",
    "__pycache__",
    "build",
    "Build",
    "out",
    "bin",
    "debug",
    "release",
}


@dataclass(frozen=True)
class ProjectContext:
    project_root: Path
    pro_files: list[Path]
    selected_files: list[Path]
    prompt_text: str


def _iter_files_pruned(project_root: Path, *, suffixes: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(project_root):
        # prune
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDE_DIR_NAMES and not d.lower().startswith("build")]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() in suffixes:
                out.append(p)
    return out


def _parse_pro_file_list(text: str) -> dict[str, list[str]]:
    """Very small .pro parser for SOURCES/HEADERS/FORMS.

    Supports line continuation with '\\'. Ignores comments starting with '#'.
    """

    # strip comments
    lines = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if line.strip():
            lines.append(line)

    # join line continuation
    joined: list[str] = []
    buf = ""
    for line in lines:
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        if buf:
            joined.append((buf + line).strip())
            buf = ""
        else:
            joined.append(line.strip())
    if buf:
        joined.append(buf.strip())

    out: dict[str, list[str]] = {"SOURCES": [], "HEADERS": [], "FORMS": [], "RESOURCES": []}
    for line in joined:
        m = re.match(r"^(SOURCES|HEADERS|FORMS|RESOURCES)\s*[+\-]?=\s*(.+)$", line)
        if not m:
            continue
        key = m.group(1)
        rhs = m.group(2).strip()
        parts = [p.strip() for p in rhs.split() if p.strip()]
        out[key].extend(parts)

    # de-dupe while keeping order
    for k, vals in out.items():
        seen: set[str] = set()
        uniq: list[str] = []
        for v in vals:
            if v not in seen:
                uniq.append(v)
                seen.add(v)
        out[k] = uniq
    return out


def build_project_context(project_root: Path, *, max_files: int = 12, max_chars: int = 40_000, top_level_only: bool = False) -> ProjectContext:
    # Allow env var override
    if "QT_TEST_AI_CTX_MAX_FILES" in os.environ:
        try:
            max_files = int(os.environ["QT_TEST_AI_CTX_MAX_FILES"])
        except ValueError:
            pass
    
    if "QT_TEST_AI_CTX_MAX_CHARS" in os.environ:
        try:
            max_chars = int(os.environ["QT_TEST_AI_CTX_MAX_CHARS"])
        except ValueError:
            pass

    pro_files = sorted(project_root.glob("*.pro"), key=lambda p: p.name.lower())

    # Prefer files referenced by .pro
    preferred: list[Path] = []
    for pro in pro_files:
        pro_text = read_text_best_effort(pro)
        lst = _parse_pro_file_list(pro_text)
        for rel in (lst.get("SOURCES") or []) + (lst.get("HEADERS") or []) + (lst.get("FORMS") or []):
            cand = (project_root / rel).resolve()
            if cand.exists() and cand.is_file():
                preferred.append(cand)

    # Fallback scan
    if top_level_only:
        # only consider files directly under project_root (non-recursive)
        scanned = []
        try:
            for p in project_root.iterdir():
                if p.is_file() and p.suffix.lower() in (".h", ".hpp", ".cpp", ".cxx", ".ui"):
                    scanned.append(p)
        except Exception:
            scanned = []
    else:
        scanned = _iter_files_pruned(project_root, suffixes=(".h", ".hpp", ".cpp", ".cxx", ".ui"))

    # Merge + de-dupe
    merged: list[Path] = []
    seen: set[Path] = set()
    for p in preferred + scanned:
        try:
            rp = p.resolve()
        except Exception:
            rp = p
        if rp in seen:
            continue
        seen.add(rp)
        merged.append(p)

    selected = merged[:max_files]

    chunks: list[str] = []
    chunks.append(f"项目根目录：{project_root}")
    if pro_files:
        chunks.append(".pro 文件：" + ", ".join([p.name for p in pro_files]))
    chunks.append("选取的源文件片段（可能截断）：")

    used = 0
    for p in selected:
        try:
            txt = read_text_best_effort(p)
        except Exception:
            continue
        # Truncate per file
        snippet = txt
        if len(snippet) > 6000:
            snippet = snippet[:6000] + "\n/* ... truncated ... */\n"
        block = f"\n--- FILE: {p.relative_to(project_root)} ---\n{snippet}"
        if used + len(block) > max_chars:
            break
        chunks.append(block)
        used += len(block)

    prompt_text = "\n".join(chunks)
    return ProjectContext(project_root=project_root, pro_files=pro_files, selected_files=selected, prompt_text=prompt_text)
