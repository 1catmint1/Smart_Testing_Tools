#!/usr/bin/env python3
"""
测试 Smart_Testing_Tools 的自动覆盖率命令检测功能
"""

import subprocess
import sys
from pathlib import Path

def test_auto_detect():
    """测试自动检测脚本"""
    print("=" * 60)
    print("Smart_Testing_Tools 自动覆盖率命令检测 - 测试演示")
    print("=" * 60)
    print()
    
    project_root = r"C:\Users\lenovo\Desktop\Diagramscene_ultima-syz"
    tools_dir = Path(r"C:\Users\lenovo\Desktop\Smart_Testing_Tools-syz\tools")
    detect_script = tools_dir / "auto_detect_coverage_cmd.py"
    
    print(f"📁 项目路径: {project_root}")
    print(f"🔍 检测脚本: {detect_script}")
    print()
    
    if not detect_script.exists():
        print(f"❌ 脚本不存在: {detect_script}")
        return False
    
    try:
        # 运行检测脚本
        print("⏳ 正在执行自动检测...")
        result = subprocess.run(
            [sys.executable, str(detect_script), project_root, "--print-only"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            print(f"❌ 脚本执行失败:")
            print(result.stderr)
            return False
        
        # 解析输出
        lines = result.stdout.strip().split('\n')
        print(f"✅ 自动检测成功!")
        print()
        
        # 显示检测信息
        if len(lines) >= 2:
            info_line = lines[0]
            cmd_line = lines[-1]
            print(f"📋 检测信息: {info_line}")
            print()
            print(f"🎯 生成的覆盖率命令:")
            print(f"   {cmd_line}")
            print()
        
        # 验证命令格式
        coverage_cmd = lines[-1]
        if coverage_cmd.startswith("gcovr"):
            print("✅ 命令格式正确 (以 'gcovr' 开头)")
            print()
            print("📝 在 Smart_Testing_Tools 中:")
            print("   1. 点击 '选择项目目录' 按钮")
            print("   2. 选择项目后，覆盖率命令会自动填充")
            print("   3. 无需手动输入！")
            return True
        else:
            print(f"⚠️  命令格式异常: {coverage_cmd[:50]}...")
            return False
    
    except subprocess.TimeoutExpired:
        print("❌ 脚本执行超时")
        return False
    except Exception as e:
        print(f"❌ 执行出错: {e}")
        return False


if __name__ == "__main__":
    success = test_auto_detect()
    sys.exit(0 if success else 1)
