#!/usr/bin/env python3
"""
自动检测项目编译输出目录并生成覆盖率命令
Usage: python auto_detect_coverage_cmd.py <project_root> [--print-only]
"""

import sys
import os
from pathlib import Path


def find_build_dir(project_root: str) -> str:
    """尝试检测项目的编译输出目录"""
    project_path = Path(project_root)
    
    # 检查顺序：最常见的输出目录
    candidates = [
        "debug",           # Qt Creator MinGW debug 输出
        "build/debug",     # CMake debug 输出
        "build",           # 一般 build 目录
        "Release",         # Visual Studio Release
        "Debug",           # Visual Studio Debug
        "cmake-build-debug",  # CLion debug 输出
    ]
    
    for candidate in candidates:
        full_path = project_path / candidate
        # 检查目录是否存在且包含 .gcda 文件（覆盖率数据）
        if full_path.exists() and full_path.is_dir():
            gcda_files = list(full_path.glob("*.gcda"))
            if gcda_files:
                return str(candidate)  # 返回相对路径
    
    # 如果没找到有 .gcda 的目录，返回默认的
    if (project_path / "debug").exists():
        return "debug"
    
    return "debug"  # 最后的默认值


def generate_coverage_cmd(project_root: str, build_dir: str = None) -> str:
    """生成完整的覆盖率命令"""
    
    if build_dir is None:
        build_dir = find_build_dir(project_root)
    
    # 覆盖率命令模板
    cmd = (
        "gcovr -r . "
        f"--object-directory {build_dir} "
        "--exclude-directories .git "
        "--exclude-directories .venv "
        "--exclude-directories tools "
        "--exclude-directories generated_tests "
        "--print-summary "
        "--html-details "
        "-o coverage.html "
        "--json=coverage.json"
    )
    
    return cmd


def main():
    if len(sys.argv) < 2:
        print("Usage: python auto_detect_coverage_cmd.py <project_root> [--print-only]")
        print("\nExample:")
        print('  python auto_detect_coverage_cmd.py "C:\\Users\\...\\Diagramscene_ultima-syz"')
        sys.exit(1)
    
    project_root = sys.argv[1]
    print_only = "--print-only" in sys.argv
    
    if not os.path.isdir(project_root):
        print(f"ERROR: Project directory not found: {project_root}", file=sys.stderr)
        sys.exit(1)
    
    # 检测编译输出目录
    build_dir = find_build_dir(project_root)
    print(f"[INFO] Detected build directory: {build_dir}", file=sys.stderr)
    
    # 生成覆盖率命令
    coverage_cmd = generate_coverage_cmd(project_root, build_dir)
    
    if print_only:
        # 仅打印命令到标准输出
        print(coverage_cmd)
    else:
        # 设置环境变量
        os.environ["QT_TEST_AI_COVERAGE_CMD"] = coverage_cmd
        print(f"[OK] Coverage command set:", file=sys.stderr)
        print(f"     {coverage_cmd}", file=sys.stderr)
        print(coverage_cmd)  # 也打印到标准输出以便脚本使用


if __name__ == "__main__":
    main()
