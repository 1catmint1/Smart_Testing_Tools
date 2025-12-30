#!/usr/bin/env python3
"""
改进的 LLM 测试生成提示词生成工具

分析覆盖率报告，为每个未充分覆盖的类生成具体的 LLM 提示词
"""

import json
import os
import sys
from pathlib import Path


def generate_prompts_for_optimization():
    """为覆盖率优化生成精准的 LLM 提示词"""
    
    prompts = {
        "phase1_diagram_item": {
            "priority": "立即",
            "current_coverage": "6.1%",
            "target_coverage": "45%",
            "prompt": """请为 Diagramscene 项目的 DiagramItem 类生成企业级单元测试。

【项目信息】
- 框架: Qt 6.10.1
- 测试框架: Qt Test
- 编译器: MinGW 13.1.0
- 现有覆盖: 6.1% (33/538 行)
- 目标覆盖: 45%+ (240+ 行)

【已有测试（跳过）】
- testDiagramItemDefaultProperties: 基础属性测试（brush, pen）
- testDiagramItemTypeEnum: 类型枚举测试
- testDiagramItemSetBrush: 笔刷设置
- testDiagramItemSetFixedSize: 固定大小

【未覆盖的关键功能（必须测试）】
1. setFont(QFont font) - 字体管理
   - 应测试: 字体设置、获取、更新
   
2. setScene(QGraphicsScene *scene) - 场景关联
   - 应测试: 场景注册、移除、NULL 场景
   
3. isMoving() / setMoving(bool) - 移动状态机
   - 应测试: 状态转换、事件期间的状态变化
   
4. contextMenuEvent() - 右键菜单事件
   - 应测试: 菜单触发、菜单项处理
   
5. itemChange() - 项目变更通知
   - 应测试: 位置变更、选择状态变更、其他属性变更
   
6. mousePressEvent() - 鼠标按下
   - 应测试: 选择、移动启动、冲突处理
   
7. mouseReleaseEvent() - 鼠标释放
   - 应测试: 移动停止、信号发送

【生成要求】
1. 创建新的 test_diagram_item_extended.cpp 文件
2. 每个测试函数应测试单一功能
3. 包含边界条件和错误路径
4. 测试应该是独立的、可重复的
5. 使用 Qt Test 的 QVERIFY、QCOMPARE、QSIGNAL_SPY 等
6. 包含覆盖率高的注释

【输出格式】
完整的可编译 QtTest 源文件，包含：
#include <QtTest>
#include "../diagramitem.h"

class TestDiagramItemExtended : public QObject { ... };
QTEST_APPLESS_MAIN(TestDiagramItemExtended)

【成功标准】
- 编译通过（无错误或警告）
- 所有测试通过
- 代码覆盖率提升到 40%+
""",
        },
        
        "phase1_diagram_path": {
            "priority": "立即",
            "current_coverage": "0%",
            "target_coverage": "50%+",
            "prompt": """请为 Diagramscene 项目的 DiagramPath 类生成完整的单元测试。

【项目信息】
- 框架: Qt 6.10.1
- 测试框架: Qt Test
- 编译器: MinGW 13.1.0
- 现有覆盖: 0% (0/80 行)
- 目标覆盖: 50%+ (40+ 行)

【类功能概述】
DiagramPath 是一个自定义的图形路径类，用于绘制连接图中的路径/线条。

【必须测试的所有公共方法】
1. DiagramPath() 构造函数
   - 应测试: 默认初始化、成员变量初值
   
2. void addPoint(const QPointF &point)
   - 应测试: 单点添加、多点添加、重复点、NULL 点
   
3. QRectF boundingRect() const
   - 应测试: 空路径边界、单点边界、多点边界、边界正确性
   
4. QPainterPath shape() const
   - 应测试: 形状生成、路径正确性
   
5. void paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget)
   - 应测试: 绘制调用、笔触设置、颜色应用
   
6. 其他属性方法（如有）

【生成要求】
1. 创建 test_diagram_path_complete.cpp
2. 覆盖所有公共方法
3. 包含边界条件（空、单点、多点）
4. 测试数学精度（边界计算）
5. 测试绘制操作

【输出格式】
完整的可编译 QtTest 源文件

【成功标准】
- 编译通过
- 所有测试通过
- 覆盖所有 public 方法
- 代码覆盖率达到 50%+
""",
        },
        
        "phase1_diagram_item_group": {
            "priority": "立即",
            "current_coverage": "8.9%",
            "target_coverage": "40%",
            "prompt": """请为 Diagramscene 项目的 DiagramItemGroup 类生成扩展单元测试。

【项目信息】
- 框架: Qt 6.10.1
- 测试框架: Qt Test
- 现有覆盖: 8.9% (15/168 行)
- 目标覆盖: 40%+ (67 行)

【已有测试（跳过）】
- testDiagramItemGroupConstruction: 构造函数
- testDiagramItemGroupDefaultProperties: 基础属性

【未覆盖的关键功能】
1. void addItem(DiagramItem *item)
   - 应测试: 添加单个项、多个项、重复添加、NULL 项
   
2. void removeItem(DiagramItem *item)
   - 应测试: 移除存在的项、移除不存在的项、移除 NULL
   
3. QRectF boundingRect() const
   - 应测试: 空组、单项组、多项组、边界正确性
   
4. QList<DiagramItem*> items()
   - 应测试: 返回列表正确性、修改后的更新

5. 变换操作
   - 应测试: 旋转、缩放、移动

【输出格式】
完整的可编译 QtTest 源文件

【成功标准】
- 编译通过
- 代码覆盖率提升到 40%+
""",
        },
        
        "phase2_delete_command": {
            "priority": "高",
            "current_coverage": "0%",
            "target_coverage": "40%",
            "prompt": """请为 Diagramscene 项目的 DeleteCommand 类生成完整的单元测试。

【类功能】
DeleteCommand 实现了撤销/重做的删除命令模式。

【测试需求】
1. 命令构造和初始化
2. execute() 方法执行删除操作
3. undo() 方法撤销删除
4. redo() 方法重做删除

【输出格式】
完整的可编译 QtTest 源文件，test_delete_command.cpp

【成功标准】
- 编译通过
- 覆盖所有 public 方法
- 代码覆盖率达到 40%+
""",
        },
        
        "system_summary": """
【覆盖率优化整体策略】

当前状态: 2.6% (73/2848 行)
第一阶段目标: 15% (427/2848 行)

优先级排序:
1. 🔴 立即 (第 1-2 周):
   - DiagramItem: 6.1% → 45% (+350行)
   - DiagramPath: 0% → 50% (+80行)
   - DiagramItemGroup: 8.9% → 40% (+120行)
   - 预期总提升: +550 行 → 2.6% → 21%

2. 🟡 高优先级 (第 3-4 周):
   - DeleteCommand: 0% → 40% (+5行)
   - FindReplaceDialog: 0% → 50% (+18行)
   - Arrow: 19.3% → 80% (+40行)
   - 预期总提升: +63 行

3. 🟠 中等 (第 5-8 周):
   - DiagramScene: 0% → 20% (GUI测试)
   - MainWindow: 0% → 15% (集成测试)

【实施步骤】
1. 使用上述提示词指导 LLM 生成每个模块的完整测试
2. 将生成的代码添加到 tests/generated/ 目录
3. 编译: qmake "tests.pro" && mingw32-make
4. 运行: .\tests\\generated\\debug\\generated_tests.exe
5. 验证: gcovr --html-details reports/coverage_report.html

【预期时间表】
- Week 1-2: 15-21% (数据模型)
- Week 3-4: 22-25% (命令+对话)
- Week 5-8: 35-40% (GUI集成)

【成功指标】
✅ 所有新测试编译通过
✅ 所有新测试执行通过  
✅ 覆盖率逐周提升
✅ 无编译警告
✅ 代码质量维持或改进
"""
    }
    
    return prompts


def main():
    """主函数"""
    print("=" * 80)
    print("LLM 测试生成提示词生成工具")
    print("=" * 80)
    print()
    
    prompts = generate_prompts_for_optimization()
    
    # 显示所有提示词
    for key, content in prompts.items():
        if key == "system_summary":
            print("\n" + "=" * 80)
            print(content)
            print("=" * 80)
        else:
            print(f"\n【{key}】")
            print(f"优先级: {content.get('priority', 'N/A')}")
            print(f"当前覆盖: {content.get('current_coverage', 'N/A')}")
            print(f"目标覆盖: {content.get('target_coverage', 'N/A')}")
            print("\n" + "-" * 80)
            print(content.get('prompt', ''))
            print("-" * 80)
    
    # 保存为 JSON 便于进一步处理
    output_path = Path(__file__).parent / "llm_prompts.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 提示词已保存到: {output_path}")
    print("\n使用方式:")
    print("1. 复制相应的 prompt 文本")
    print("2. 粘贴到 LLM（ChatGPT/Claude）")
    print("3. 生成代码后添加到 tests/generated/")
    print("4. 编译并验证")


if __name__ == "__main__":
    main()
