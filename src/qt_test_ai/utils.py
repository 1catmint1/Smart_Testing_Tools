from __future__ import annotations

import os
import re
import shutil
from pathlib import Path


def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def iter_files(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            p = Path(dirpath) / name
            if any(p.match(pattern) for pattern in patterns):
                out.append(p)
    return out


def read_text_best_effort(path: Path, max_bytes: int = 2_000_000) -> str:
    data = path.read_bytes()
    if len(data) > max_bytes:
        data = data[:max_bytes]
    for enc in ("utf-8", "utf-8-sig", "gbk", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


_QT_BUILD_HINTS = (
    "build",
    "Build",
    "out",
    "bin",
    "debug",
    "release",
)


def guess_exe_candidates(project_root: Path) -> list[Path]:
    candidates: list[Path] = []
    for hint in _QT_BUILD_HINTS:
        p = project_root / hint
        if p.exists() and p.is_dir():
            for exe in p.rglob("*.exe"):
                candidates.append(exe)
    # 常见 Qt Creator 构建目录：build-<name>-Debug/Release
    for exe in project_root.rglob("*.exe"):
        if any(part.lower().startswith("build") for part in exe.parts):
            candidates.append(exe)

    # 去重、优先较短路径
    uniq = {c.resolve(): c for c in candidates}
    return sorted(uniq.values(), key=lambda x: (len(str(x)), str(x).lower()))


def looks_like_qt_pro(project_root: Path) -> bool:
    return any(project_root.glob("*.pro"))


def extract_pro_info(pro_text: str) -> dict[str, str]:
    info: dict[str, str] = {}
    # 非严格解析：提取常用字段
    for key in ("QT", "TEMPLATE", "TARGET", "CONFIG"):
        m = re.search(rf"^\s*{re.escape(key)}\s*([+\-]?=)\s*(.+?)\s*$", pro_text, re.M)
        if m:
            info[key] = m.group(2).strip()
    return info
