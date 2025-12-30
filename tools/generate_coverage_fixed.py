#!/usr/bin/env python3
"""
覆盖率报告生成脚本 - 永久修复路径问题

这个脚本确保：
1. 源文件能被正确定位
2. .gcda 文件能被正确读取
3. 覆盖率报告准确无误
"""

import os
import subprocess
from pathlib import Path
import shutil

def setup_coverage_paths():
    """设置和验证覆盖率路径"""
    
    # 检测当前目录
    cwd = Path.cwd()
    
    # 确定项目根目录
    if (cwd / "tests" / "generated").exists():
        # 在项目根目录运行
        project_root = cwd
        tests_dir = cwd / "tests" / "generated"
    elif (cwd.name == "generated" and (cwd.parent.name == "tests")):
        # 在 tests/generated 目录运行
        project_root = cwd.parent.parent
        tests_dir = cwd
    else:
        print(f"❌ 无法确定项目结构。当前目录: {cwd}")
        return None
    
    debug_dir = tests_dir / "debug"
    
    print(f"📁 项目根目录: {project_root}")
    print(f"📁 测试目录: {tests_dir}")
    print(f"📁 构建目录: {debug_dir}")
    
    # 验证目录存在
    if not debug_dir.exists():
        print(f"❌ 错误: 找不到 {debug_dir}")
        return None
    
    # 检查是否有 .gcda 文件
    gcda_files = list(debug_dir.glob("*.gcda"))
    if not gcda_files:
        print(f"⚠️ 警告: 找不到 .gcda 文件")
        print(f"   请先运行: tests/generated/debug/generated_tests.exe")
        return None
    
    print(f"✅ 找到 {len(gcda_files)} 个 .gcda 文件")
    
    # 复制源文件到调试目录（帮助 gcovr 找到）
    print(f"\n📋 复制源文件到调试目录...")
    source_extensions = [".cpp", ".h"]
    for ext in source_extensions:
        for src_file in project_root.glob(f"*{ext}"):
            if src_file.is_file():
                dst_file = debug_dir / src_file.name
                try:
                    shutil.copy2(src_file, dst_file)
                    print(f"  ✓ {src_file.name}")
                except Exception as e:
                    print(f"  ✗ {src_file.name}: {e}")
    
    return {
        "project_root": project_root,
        "tests_dir": tests_dir,
        "debug_dir": debug_dir
    }

def generate_coverage_report(paths):
    """生成覆盖率报告"""
    
    project_root = paths["project_root"]
    debug_dir = paths["debug_dir"]
    
    print(f"\n🔄 生成覆盖率报告...")
    
    # 方法 1: 从项目根目录运行 gcovr（推荐）
    cmd = [
        "gcovr",
        "-r", str(project_root),
        "--object-directory", str(debug_dir),
        "--exclude-directories", ".git",
        "--exclude-directories", ".venv",
        "--exclude-directories", "tools",
        "--print-summary",
        "--html-details", "-o", str(project_root / "coverage_report.html"),
        "--json", "-o", str(project_root / "coverage_report.json"),
        "--gcov-ignore-errors=no_working_dir_found",
    ]
    
    print(f"   命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            print(f"\n✅ 覆盖率报告生成成功！")
            
            # 解析覆盖率摘要
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if '%' in line:
                        print(f"   {line}")
            
            print(f"\n📊 报告位置:")
            print(f"   HTML: {project_root / 'coverage_report.html'}")
            print(f"   JSON: {project_root / 'coverage_report.json'}")
            
            return True
        else:
            print(f"❌ gcovr 命令失败")
            print(f"   错误: {result.stderr[:500]}")
            
            # 尝试备用方法
            print(f"\n🔄 尝试备用方法...")
            return generate_coverage_report_fallback(paths)
    
    except FileNotFoundError:
        print(f"❌ 找不到 gcovr 命令")
        print(f"   请运行: pip install gcovr")
        return False
    except subprocess.TimeoutExpired:
        print(f"❌ gcovr 执行超时")
        return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False

def generate_coverage_report_fallback(paths):
    """备用方法: 从测试目录运行 gcovr"""
    
    tests_dir = paths["tests_dir"]
    debug_dir = paths["debug_dir"]
    
    print(f"   从测试目录运行 gcovr...")
    
    cmd = [
        "gcovr",
        "-r", str(tests_dir),
        "--object-directory", str(debug_dir),
        "--print-summary",
        "--html-details", "-o", str(tests_dir / "coverage_report.html"),
        "--json", "-o", str(tests_dir / "coverage_report.json"),
        "--gcov-ignore-errors=no_working_dir_found",
    ]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(tests_dir),
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            print(f"✅ 覆盖率报告生成成功（备用方法）")
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if '%' in line:
                        print(f"   {line}")
            return True
        else:
            print(f"❌ 备用方法也失败了")
            return False
    
    except Exception as e:
        print(f"❌ 备用方法错误: {e}")
        return False

def main():
    """主函数"""
    print("="*70)
    print("📊 覆盖率报告生成 - 路径修复版")
    print("="*70)
    
    # 设置路径
    paths = setup_coverage_paths()
    if not paths:
        return 1
    
    # 生成报告
    success = generate_coverage_report(paths)
    
    print("\n" + "="*70)
    if success:
        print("✅ 完成！覆盖率已正确生成")
        return 0
    else:
        print("❌ 生成失败，请检查上述错误")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
