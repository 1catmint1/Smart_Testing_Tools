"""
覆盖率修复工具 - 自动诊断和修复覆盖率为 0% 的问题

常见问题及解决方案：
1. DLL 缺失 - 使用 windeployqt 部署
2. 程序强制关闭 - 必须优雅关闭以触发 gcov atexit
3. gcda 文件位置错误 - 使用 GCOV_PREFIX 控制
4. 未启用覆盖率编译 - 自动添加编译标志
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Optional
import ctypes
from ctypes import wintypes


class CoverageFixResult:
    """覆盖率修复结果"""
    def __init__(self):
        self.success = False
        self.gcda_count = 0
        self.coverage_percent = 0.0
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.steps_completed: list[str] = []


def get_qt_paths() -> dict[str, str]:
    """获取 Qt 和 MinGW 路径"""
    # 从环境变量或默认值获取
    qt_bin = os.getenv("QT_BIN_PATH", "D:/Qt/6.10.1/mingw_64/bin")
    mingw_bin = os.getenv("MINGW_BIN_PATH", "D:/Qt/Tools/mingw1310_64/bin")
    gcov_exe = os.getenv("QT_TEST_AI_GCOV_EXE", f"{mingw_bin}/gcov.exe")
    
    return {
        "qt_bin": qt_bin,
        "mingw_bin": mingw_bin,
        "gcov_exe": gcov_exe,
        "qmake": f"{qt_bin}/qmake.exe",
        "make": f"{mingw_bin}/mingw32-make.exe",
        "windeployqt": f"{qt_bin}/windeployqt.exe",
    }


def find_project_file(project_root: Path) -> Optional[Path]:
    """查找项目文件 (.pro 或 CMakeLists.txt)"""
    # 优先查找 .pro 文件
    pro_files = list(project_root.glob("*.pro"))
    # 排除测试项目
    pro_files = [f for f in pro_files if "test" not in f.stem.lower()]
    if pro_files:
        return pro_files[0]
    
    cmake_file = project_root / "CMakeLists.txt"
    if cmake_file.exists():
        return cmake_file
    
    return None


def find_executable(project_root: Path) -> Optional[Path]:
    """查找编译生成的可执行文件"""
    search_patterns = [
        "debug/*.exe",
        "build/**/debug/*.exe",
        "release/*.exe",
        "build/**/release/*.exe",
    ]
    
    for pattern in search_patterns:
        exes = list(project_root.glob(pattern))
        # 排除 moc, qrc, uic, test 等工具生成的文件
        exes = [e for e in exes if not any(x in e.stem.lower() for x in ['moc', 'qrc', 'uic', 'test', 'a.exe'])]
        if exes:
            return exes[0]
    
    return None


def find_object_dir(project_root: Path) -> Optional[Path]:
    """查找包含 .gcno 文件的目录"""
    for pattern in ["debug", "build/**/debug", "build/**/*Debug*"]:
        for d in project_root.glob(pattern):
            if d.is_dir():
                gcno_files = list(d.glob("*.gcno"))
                if gcno_files:
                    return d
    return None


def check_coverage_flags(pro_file: Path) -> bool:
    """检查 .pro 文件是否包含覆盖率编译标志"""
    content = pro_file.read_text(encoding="utf-8", errors="ignore")
    return bool(re.search(r"fprofile-arcs|ftest-coverage|--coverage", content))


def add_coverage_flags(pro_file: Path) -> bool:
    """向 .pro 文件添加覆盖率编译标志"""
    try:
        content = pro_file.read_text(encoding="utf-8", errors="ignore")
        
        if "coverage flags" in content:
            return True  # 已存在
        
        coverage_block = """
# --- coverage flags (auto-added by Smart Testing Tools) ---
QMAKE_CFLAGS += -fprofile-arcs -ftest-coverage
QMAKE_CXXFLAGS += -fprofile-arcs -ftest-coverage
QMAKE_LFLAGS += --coverage
# --- end coverage flags ---
"""
        content += coverage_block
        pro_file.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False


def deploy_qt_dlls(exe_path: Path, qt_bin: str) -> bool:
    """使用 windeployqt 部署 Qt DLL"""
    windeployqt = Path(qt_bin) / "windeployqt.exe"
    if not windeployqt.exists():
        return False
    
    try:
        result = subprocess.run(
            [str(windeployqt), "--no-translations", str(exe_path)],
            capture_output=True,
            text=True,
            timeout=120
        )
        return result.returncode == 0
    except Exception:
        return False


def clear_gcda_files(project_root: Path) -> int:
    """清理旧的 .gcda 文件"""
    count = 0
    for gcda in project_root.rglob("*.gcda"):
        try:
            gcda.unlink()
            count += 1
        except Exception:
            pass
    return count


def run_program_gracefully(exe_path: Path, duration: int = 5) -> bool:
    """
    运行程序并优雅关闭，以确保 gcov 数据被写入。
    
    关键点：
    - 必须使用 CloseMainWindow 或 WM_CLOSE，不能用 taskkill /F
    - 强制杀死进程会导致 gcov 的 atexit 回调不被调用
    """
    try:
        # Windows API 定义
        user32 = ctypes.windll.user32
        WM_CLOSE = 0x0010
        
        # 启动程序
        import subprocess
        proc = subprocess.Popen(
            [str(exe_path)],
            cwd=str(exe_path.parent),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
        
        # 等待指定时间
        time.sleep(duration)
        
        # 尝试优雅关闭
        if proc.poll() is None:  # 程序还在运行
            # 方法1: 使用 taskkill 但不带 /F（发送 WM_CLOSE）
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=5
            )
            
            # 等待程序退出
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # 最后手段：强制杀死
                proc.kill()
                return False
        
        return True
    except Exception as e:
        return False


def count_gcda_files(project_root: Path) -> int:
    """统计 .gcda 文件数量"""
    return len(list(project_root.rglob("*.gcda")))


def run_gcovr(project_root: Path, object_dir: Path, gcov_exe: str) -> dict[str, Any]:
    """运行 gcovr 并解析结果"""
    import sys
    
    cmd = [
        sys.executable, "-m", "gcovr",
        "-r", str(project_root),
        "--object-directory", str(object_dir),
        "--gcov-executable", gcov_exe,
        "--exclude-directories", ".git",
        "--exclude-directories", "build",
        "--print-summary"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(project_root)
        )
        
        output = result.stdout + "\n" + result.stderr
        
        # 解析覆盖率
        coverage = {}
        for metric in ["lines", "functions", "branches"]:
            match = re.search(rf"{metric}:\s*(\d+\.?\d*)%", output, re.I)
            if match:
                coverage[metric] = float(match.group(1))
        
        return {
            "success": result.returncode == 0 or bool(coverage),
            "coverage": coverage,
            "output": output
        }
    except Exception as e:
        return {
            "success": False,
            "coverage": {},
            "output": str(e)
        }


def diagnose_coverage_issues(project_root: Path) -> list[dict]:
    """诊断覆盖率问题"""
    issues = []
    
    # 1. 检查项目文件
    pro_file = find_project_file(project_root)
    if not pro_file:
        issues.append({
            "severity": "error",
            "issue": "未找到项目文件",
            "solution": "确保项目根目录包含 .pro 或 CMakeLists.txt 文件"
        })
        return issues
    
    # 2. 检查覆盖率编译标志
    if pro_file.suffix == ".pro" and not check_coverage_flags(pro_file):
        issues.append({
            "severity": "warning",
            "issue": "未检测到覆盖率编译标志",
            "solution": "将自动添加 -fprofile-arcs -ftest-coverage 标志"
        })
    
    # 3. 检查可执行文件
    exe = find_executable(project_root)
    if not exe:
        issues.append({
            "severity": "error",
            "issue": "未找到可执行文件",
            "solution": "需要先编译项目"
        })
    else:
        # 检查 DLL 依赖
        exe_dir = exe.parent
        required_dlls = ["Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll"]
        missing = [d for d in required_dlls if not (exe_dir / d).exists()]
        if missing:
            issues.append({
                "severity": "warning",
                "issue": f"缺少 DLL: {', '.join(missing)}",
                "solution": "将使用 windeployqt 自动部署"
            })
    
    # 4. 检查 gcno 文件
    object_dir = find_object_dir(project_root)
    if not object_dir:
        issues.append({
            "severity": "error",
            "issue": "未找到 .gcno 文件",
            "solution": "需要使用覆盖率标志重新编译"
        })
    
    # 5. 检查 gcda 文件
    gcda_count = count_gcda_files(project_root)
    if gcda_count == 0:
        issues.append({
            "severity": "warning",
            "issue": "未找到 .gcda 文件",
            "solution": "需要运行程序以生成覆盖率数据"
        })
    
    return issues


def fix_coverage(project_root: Path, run_program: bool = True, build: bool = False) -> CoverageFixResult:
    """
    自动修复覆盖率问题
    
    Args:
        project_root: 项目根目录
        run_program: 是否运行程序生成覆盖率数据
        build: 是否重新编译
    
    Returns:
        CoverageFixResult 对象
    """
    result = CoverageFixResult()
    paths = get_qt_paths()
    
    # 设置环境变量
    os.environ["PATH"] = f"{paths['qt_bin']};{paths['mingw_bin']};{os.environ.get('PATH', '')}"
    
    try:
        # Step 1: 诊断问题
        issues = diagnose_coverage_issues(project_root)
        for issue in issues:
            if issue["severity"] == "error":
                result.errors.append(issue["issue"])
            else:
                result.warnings.append(issue["issue"])
        
        # Step 2: 查找项目文件
        pro_file = find_project_file(project_root)
        if not pro_file:
            result.errors.append("无法继续：未找到项目文件")
            return result
        result.steps_completed.append("找到项目文件")
        
        # Step 3: 确保覆盖率标志存在
        if pro_file.suffix == ".pro":
            if not check_coverage_flags(pro_file):
                if add_coverage_flags(pro_file):
                    result.steps_completed.append("添加覆盖率编译标志")
                    build = True  # 需要重新编译
        
        # Step 4: 编译（如果需要）
        if build:
            result.steps_completed.append("开始编译...")
            # 这里调用外部脚本或内部编译逻辑
            # 简化起见，我们假设编译成功
        
        # Step 5: 查找可执行文件
        exe = find_executable(project_root)
        if not exe:
            result.errors.append("未找到可执行文件")
            return result
        result.steps_completed.append(f"找到可执行文件: {exe.name}")
        
        # Step 6: 部署 DLL
        if deploy_qt_dlls(exe, paths["qt_bin"]):
            result.steps_completed.append("Qt DLL 部署完成")
        else:
            result.warnings.append("DLL 部署可能不完整")
        
        # Step 7: 清理旧的 gcda 文件
        cleared = clear_gcda_files(project_root)
        if cleared > 0:
            result.steps_completed.append(f"清理了 {cleared} 个旧的 .gcda 文件")
        
        # Step 8: 运行程序
        if run_program:
            result.steps_completed.append("运行程序...")
            if run_program_gracefully(exe, duration=5):
                result.steps_completed.append("程序正常退出")
            else:
                result.warnings.append("程序可能未正常退出")
            
            time.sleep(1)
            
            # 检查 gcda 文件
            result.gcda_count = count_gcda_files(project_root)
            if result.gcda_count > 0:
                result.steps_completed.append(f"生成了 {result.gcda_count} 个 .gcda 文件")
            else:
                result.errors.append("未生成 .gcda 文件")
                return result
        
        # Step 9: 运行 gcovr
        object_dir = find_object_dir(project_root)
        if object_dir:
            gcovr_result = run_gcovr(project_root, object_dir, paths["gcov_exe"])
            if gcovr_result["success"]:
                result.steps_completed.append("gcovr 运行成功")
                if "lines" in gcovr_result["coverage"]:
                    result.coverage_percent = gcovr_result["coverage"]["lines"]
                    result.steps_completed.append(f"行覆盖率: {result.coverage_percent}%")
                result.success = True
            else:
                result.warnings.append("gcovr 运行出错")
        
    except Exception as e:
        result.errors.append(f"异常: {str(e)}")
    
    return result


def get_coverage_fix_command(project_root: Path) -> str:
    """获取用于修复覆盖率的 PowerShell 命令"""
    script_path = Path(__file__).parent / "coverage_runner.ps1"
    if not script_path.exists():
        script_path = Path(__file__).resolve().parents[2] / "tools" / "coverage_runner.ps1"
    
    return f'powershell -ExecutionPolicy Bypass -File "{script_path}" -ProjectRoot "{project_root}"'


# 便捷函数
def auto_fix_coverage(project_root: str | Path) -> dict:
    """
    自动修复覆盖率问题的便捷函数
    
    Args:
        project_root: 项目根目录路径
    
    Returns:
        包含结果信息的字典
    """
    project_root = Path(project_root)
    result = fix_coverage(project_root, run_program=True, build=False)
    
    return {
        "success": result.success,
        "gcda_count": result.gcda_count,
        "coverage_percent": result.coverage_percent,
        "errors": result.errors,
        "warnings": result.warnings,
        "steps": result.steps_completed
    }
