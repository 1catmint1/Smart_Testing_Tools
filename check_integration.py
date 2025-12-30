#!/usr/bin/env python3
"""
集成验证脚本 - 检查所有依赖和配置
"""

import sys
import os
from pathlib import Path

def check_environment():
    """检查开发环境"""
    print("\n" + "="*60)
    print("🔍 检查环境配置")
    print("="*60)
    
    checks = {
        "Python 3.8+": sys.version_info >= (3, 8),
        "项目根目录": Path("main.py").exists(),
        "qt_test_ai 模块": Path("src/qt_test_ai").exists(),
        "llm_test_generator": Path("src/qt_test_ai/llm_test_generator.py").exists(),
    }
    
    all_pass = True
    for check_name, result in checks.items():
        status = "✅" if result else "❌"
        print(f"{status} {check_name}")
        if not result:
            all_pass = False
    
    return all_pass

def check_dependencies():
    """检查 Python 依赖"""
    print("\n" + "="*60)
    print("📦 检查 Python 依赖")
    print("="*60)
    
    dependencies = {
        "requests": "HTTP 请求",
        "PySide6": "Qt GUI 框架",
    }
    
    optional = {
        "openai": "OpenAI API",
        "anthropic": "Anthropic Claude API",
        "python-dotenv": "环境变量加载",
    }
    
    all_pass = True
    
    print("\n必需依赖:")
    for pkg, desc in dependencies.items():
        try:
            __import__(pkg)
            print(f"✅ {pkg:15} ({desc})")
        except ImportError:
            print(f"❌ {pkg:15} ({desc}) - 缺失")
            all_pass = False
    
    print("\n可选依赖:")
    for pkg, desc in optional.items():
        try:
            __import__(pkg)
            print(f"✅ {pkg:15} ({desc})")
        except ImportError:
            print(f"⚠️  {pkg:15} ({desc}) - 缺失 (需要用于LLM功能)")
    
    return all_pass

def check_api_keys():
    """检查 API 密钥配置"""
    print("\n" + "="*60)
    print("🔑 检查 API 密钥")
    print("="*60)
    
    env_vars = {
        "OPENAI_API_KEY": "OpenAI",
        "ANTHROPIC_API_KEY": "Anthropic Claude",
    }
    
    configured = False
    
    for env_var, service in env_vars.items():
        key = os.getenv(env_var)
        if key:
            # 显示部分密钥
            masked = key[:10] + "..." + key[-4:] if len(key) > 14 else "***"
            print(f"✅ {env_var:20} ({service:20}) = {masked}")
            configured = True
        else:
            print(f"⚠️  {env_var:20} ({service:20}) - 未设置")
    
    # 检查 .env 文件
    if Path(".env").exists():
        print(f"✅ .env 文件存在")
        configured = True
    
    if not configured:
        print(f"\n⚠️  警告: 未配置任何 API 密钥")
        print(f"   请设置 OPENAI_API_KEY 或 ANTHROPIC_API_KEY 环境变量")
    
    return configured

def check_qt_tools():
    """检查 Qt 工具"""
    print("\n" + "="*60)
    print("🔧 检查 Qt 工具")
    print("="*60)
    
    import subprocess
    
    tools = {
        "qmake": "Qt 项目配置工具",
        "mingw32-make": "GNU Make 编译工具",
    }
    
    all_found = True
    
    for tool, desc in tools.items():
        try:
            result = subprocess.run(
                f"{tool} -version",
                shell=True,
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"✅ {tool:20} ({desc})")
            else:
                print(f"⚠️  {tool:20} ({desc}) - 命令失败")
                all_found = False
        except Exception as e:
            print(f"❌ {tool:20} ({desc}) - {str(e)}")
            all_found = False
    
    return all_found

def check_project_structure():
    """检查项目结构"""
    print("\n" + "="*60)
    print("📁 检查项目结构")
    print("="*60)
    
    paths = {
        "C:/Users/lenovo/Desktop/Smart_Testing_Tools-syz": "Smart Testing Tools",
        "C:/Users/lenovo/Desktop/Diagramscene_ultima-syz": "Diagram Scene 项目",
        "C:/Users/lenovo/Desktop/Diagramscene_ultima-syz/tests/generated": "生成的测试目录",
        "C:/Users/lenovo/Desktop/Diagramscene_ultima-syz/llm_prompts.json": "LLM 提示文件",
    }
    
    all_found = True
    
    for path_str, desc in paths.items():
        path = Path(path_str)
        if path.exists():
            if path.is_file():
                size = path.stat().st_size
                print(f"✅ {desc:30} ({size:,} bytes)")
            else:
                print(f"✅ {desc:30} (目录)")
        else:
            print(f"⚠️  {desc:30} - 不存在")
            all_found = False
    
    return all_found

def test_imports():
    """测试 Python 导入"""
    print("\n" + "="*60)
    print("🐍 测试 Python 导入")
    print("="*60)
    
    try:
        sys.path.insert(0, str(Path("src").absolute()))
        
        from qt_test_ai.llm_test_generator import LLMTestGenerator, interactive_llm_test_generation
        print(f"✅ 导入 LLMTestGenerator")
        
        from qt_test_ai.llm import load_llm_config_from_env, generate_tests_with_llm
        print(f"✅ 导入 llm 模块")
        
        print(f"\n✅ 所有导入成功!")
        return True
    
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False

def main():
    """主函数"""
    print("\n" + "="*70)
    print("🚀 Smart Testing Tools - 集成验证")
    print("="*70)
    
    results = []
    
    # 检查环境
    results.append(("环境配置", check_environment()))
    
    # 检查依赖
    results.append(("Python 依赖", check_dependencies()))
    
    # 检查 API 密钥
    results.append(("API 密钥", check_api_keys()))
    
    # 检查 Qt 工具
    results.append(("Qt 工具", check_qt_tools()))
    
    # 检查项目结构
    results.append(("项目结构", check_project_structure()))
    
    # 测试导入
    results.append(("Python 导入", test_imports()))
    
    # 汇总
    print("\n" + "="*70)
    print("✅ 验证汇总")
    print("="*70)
    
    all_pass = True
    for check_name, result in results:
        status = "✅" if result else "⚠️ "
        print(f"{status} {check_name}")
        if not result:
            all_pass = False
    
    print("\n" + "="*70)
    if all_pass:
        print("✅ 所有检查通过! 你可以开始使用 LLM 测试生成系统")
        print("\n推荐命令:")
        print("  python main.py                        # 交互式菜单")
        print("  python main.py full-cycle -s auto     # 完整周期")
        print("  python main.py generate -s claude     # 生成测试")
        return 0
    else:
        print("⚠️  有些检查失败，请解决上述问题后再试")
        print("\n问题排查:")
        print("  1. 确保 OPENAI_API_KEY 或 ANTHROPIC_API_KEY 已设置")
        print("  2. 运行 pip install openai anthropic 来安装 API 库")
        print("  3. 确保 Qt 和 MinGW 已添加到 PATH")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
