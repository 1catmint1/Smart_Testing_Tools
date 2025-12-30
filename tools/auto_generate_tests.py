#!/usr/bin/env python3
"""
自动化 LLM 测试生成工具

直接调用 LLM API，自动生成并保存测试代码
"""

import json
import os
from pathlib import Path


def load_prompts():
    """加载 LLM 提示词库"""
    prompts_file = Path(__file__).parent / "llm_prompts.json"
    with open(prompts_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_tests_with_openai(prompt_text: str, output_file: str):
    """
    使用 OpenAI API 生成测试代码
    
    使用方法:
        设置环境变量: set OPENAI_API_KEY=your_key
        或在代码中直接设置
    """
    try:
        from openai import OpenAI
    except ImportError:
        print("❌ 需要安装 openai: pip install openai")
        return False
    
    # 读取 API Key（优先级：环境变量 > 硬编码）
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("⚠️  未设置 OPENAI_API_KEY 环境变量")
        print("   方法 1: set OPENAI_API_KEY=your_key")
        print("   方法 2: 在代码中设置 api_key = 'your_key'")
        return False
    
    try:
        client = OpenAI(api_key=api_key)
        
        print(f"\n🤖 正在调用 OpenAI API...")
        print(f"📝 生成文件: {output_file}")
        
        response = client.chat.completions.create(
            model="gpt-4",  # 或 "gpt-3.5-turbo"
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的 C++ Qt Test 框架测试代码生成专家。生成的代码必须符合项目要求，能够直接编译和运行。"
                },
                {
                    "role": "user",
                    "content": prompt_text
                }
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        # 提取生成的代码
        generated_code = response.choices[0].message.content
        
        # 保存到文件
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(generated_code)
        
        print(f"✅ 测试代码已生成并保存到: {output_file}")
        print(f"📊 生成的代码行数: {len(generated_code.splitlines())}")
        return True
        
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return False


def generate_tests_with_claude(prompt_text: str, output_file: str):
    """
    使用 Claude API 生成测试代码
    
    使用方法:
        set ANTHROPIC_API_KEY=your_key
    """
    try:
        import anthropic
    except ImportError:
        print("❌ 需要安装 anthropic: pip install anthropic")
        return False
    
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("⚠️  未设置 ANTHROPIC_API_KEY 环境变量")
        print("   set ANTHROPIC_API_KEY=your_key")
        return False
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        print(f"\n🤖 正在调用 Claude API...")
        print(f"📝 生成文件: {output_file}")
        
        message = client.messages.create(
            model="claude-3-opus-20240229",  # 或其他模型
            max_tokens=4000,
            messages=[
                {
                    "role": "user",
                    "content": prompt_text
                }
            ]
        )
        
        generated_code = message.content[0].text
        
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(generated_code)
        
        print(f"✅ 测试代码已生成并保存到: {output_file}")
        print(f"📊 生成的代码行数: {len(generated_code.splitlines())}")
        return True
        
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 80)
    print("🚀 自动化 LLM 测试生成工具")
    print("=" * 80)
    print()
    
    prompts = load_prompts()
    
    # 第一阶段的三个主要任务
    tasks = [
        {
            "name": "DiagramItem 扩展测试",
            "key": "phase1_diagram_item",
            "output": "../Diagramscene_ultima-syz/tests/generated/test_diagram_item_extended.cpp",
            "coverage_target": "6.1% → 45%"
        },
        {
            "name": "DiagramPath 完整测试",
            "key": "phase1_diagram_path",
            "output": "../Diagramscene_ultima-syz/tests/generated/test_diagram_path_complete.cpp",
            "coverage_target": "0% → 50%"
        },
        {
            "name": "DiagramItemGroup 扩展测试",
            "key": "phase1_diagram_item_group",
            "output": "../Diagramscene_ultima-syz/tests/generated/test_diagram_item_group_extended.cpp",
            "coverage_target": "8.9% → 40%"
        }
    ]
    
    print("📋 可生成的任务列表:\n")
    for i, task in enumerate(tasks, 1):
        print(f"{i}. {task['name']:30} ({task['coverage_target']})")
    print()
    
    # 让用户选择
    choice = input("选择任务编号 (1-3) 或 'all' 生成所有 [默认 1]: ").strip() or "1"
    
    # 选择 LLM 服务
    print("\n🤖 选择 LLM 服务:")
    print("1. OpenAI (GPT-4 / GPT-3.5)")
    print("2. Claude (Anthropic)")
    print("3. 手动复制粘贴 (不调用 API)")
    
    service = input("\n选择 [默认 1]: ").strip() or "1"
    
    # 选择 API Key
    if service in ["1", "2"]:
        print("\n🔐 API Key 设置:")
        
        if service == "1":
            print("方法 1: 设置环境变量")
            print("   set OPENAI_API_KEY=sk-...")
            print("\n方法 2: 在脚本中设置")
            print("   请修改此脚本，在 generate_tests_with_openai() 中设置 api_key")
            
            api_key = input("\n是否已设置 API Key? (y/n) [默认 n]: ").strip().lower()
            if api_key != 'y':
                print("❌ 请先设置 OPENAI_API_KEY 环境变量")
                return
        else:
            print("方法: 设置环境变量")
            print("   set ANTHROPIC_API_KEY=sk-ant-...")
            api_key = input("\n是否已设置 API Key? (y/n) [默认 n]: ").strip().lower()
            if api_key != 'y':
                print("❌ 请先设置 ANTHROPIC_API_KEY 环境变量")
                return
    
    # 生成测试
    if choice.lower() == 'all':
        selected_tasks = tasks
    else:
        try:
            idx = int(choice) - 1
            selected_tasks = [tasks[idx]]
        except (ValueError, IndexError):
            print("❌ 无效的选择")
            return
    
    print("\n" + "=" * 80)
    print(f"🚀 正在生成 {len(selected_tasks)} 个测试文件...")
    print("=" * 80)
    
    success_count = 0
    for task in selected_tasks:
        print(f"\n📌 任务: {task['name']}")
        print(f"   目标覆盖: {task['coverage_target']}")
        print(f"   输出文件: {task['output']}")
        
        prompt = prompts[task['key']]['prompt']
        
        if service == "1":
            if generate_tests_with_openai(prompt, task['output']):
                success_count += 1
        elif service == "2":
            if generate_tests_with_claude(prompt, task['output']):
                success_count += 1
        elif service == "3":
            print(f"\n📋 提示词已复制（手动模式）")
            print("-" * 80)
            print(prompt[:500] + "...")
            print("-" * 80)
            print("\n请复制完整提示词到 ChatGPT/Claude 并粘贴生成的代码")
    
    # 总结
    print("\n" + "=" * 80)
    print(f"✅ 完成: {success_count}/{len(selected_tasks)} 个任务成功")
    print("=" * 80)
    
    if success_count == len(selected_tasks):
        print("\n🎉 现在你需要:")
        print("1. 编译新的测试代码")
        print("   cd tests\\generated")
        print("   qmake tests.pro && mingw32-make")
        print("\n2. 运行测试")
        print("   .\\debug\\generated_tests.exe")
        print("\n3. 生成覆盖率报告")
        print("   gcovr --html-details reports/coverage_report.html")


if __name__ == "__main__":
    main()
