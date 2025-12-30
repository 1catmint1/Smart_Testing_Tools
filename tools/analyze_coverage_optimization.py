#!/usr/bin/env python3
"""
覆盖率分析和对比工具

分析当前覆盖率报告，生成详细的改进建议和追踪报告
"""

import re
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple


class CoverageAnalyzer:
    """覆盖率分析工具"""
    
    def __init__(self, coverage_report_path: str = None):
        self.coverage_report_path = coverage_report_path
        self.file_coverages = {}
        self.baseline = {}
    
    def parse_html_report(self, html_path: str) -> Dict:
        """解析 HTML 覆盖率报告"""
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取文件覆盖率数据
        # 格式: <a href="...">filename</a> ... 19.3% ... 11/57
        pattern = r'<a href="[^"]+">([^<]+)</a>\s*</th>.*?<td[^>]*>([0-9.]+)%</td>.*?<td[^>]*>(\d+) / 0 / (\d+)</td>'
        
        coverages = {}
        for match in re.finditer(pattern, content, re.DOTALL):
            filename = match.group(1)
            percentage = float(match.group(2))
            executed = int(match.group(3))
            total = int(match.group(4))
            
            coverages[filename] = {
                'percentage': percentage,
                'executed': executed,
                'total': total,
                'uncovered': total - executed
            }
        
        return coverages
    
    def generate_optimization_report(self, coverages: Dict) -> str:
        """生成优化建议报告"""
        
        # 分类文件
        high_coverage = {}      # >= 30%
        medium_coverage = {}    # 10-30%
        low_coverage = {}       # 1-10%
        zero_coverage = {}      # 0%
        
        for filename, stats in coverages.items():
            pct = stats['percentage']
            if pct >= 30:
                high_coverage[filename] = stats
            elif pct >= 10:
                medium_coverage[filename] = stats
            elif pct > 0:
                low_coverage[filename] = stats
            else:
                zero_coverage[filename] = stats
        
        # 按未覆盖行数排序（未覆盖行数最多的优先）
        priority_zero = sorted(
            zero_coverage.items(), 
            key=lambda x: x[1]['total'], 
            reverse=True
        )
        priority_low = sorted(
            low_coverage.items(), 
            key=lambda x: x[1]['uncovered'], 
            reverse=True
        )
        
        report = []
        report.append("=" * 100)
        report.append("📊 代码覆盖率优化分析报告")
        report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 100)
        report.append("")
        
        # 汇总统计
        total_lines = sum(s['total'] for s in coverages.values())
        total_executed = sum(s['executed'] for s in coverages.values())
        total_coverage = (total_executed / total_lines * 100) if total_lines > 0 else 0
        
        report.append(f"📈 整体覆盖率: {total_coverage:.1f}% ({total_executed}/{total_lines} 行)")
        report.append("")
        
        # 优先级 1: 零覆盖模块（最高优先级）
        report.append("🔴 【优先级 1】零覆盖模块 - 立即优化")
        report.append("-" * 100)
        if priority_zero:
            for filename, stats in priority_zero:
                report.append(f"  ❌ {filename:45} {stats['total']:4} 行 (0%)")
                report.append(f"      → 需要新增 {stats['total']} 行的测试覆盖")
        else:
            report.append("  ✅ 无零覆盖模块")
        report.append("")
        
        # 优先级 2: 低覆盖模块
        report.append("🟡 【优先级 2】低覆盖模块 (1-10%) - 快速提升")
        report.append("-" * 100)
        if priority_low:
            for filename, stats in priority_low:
                pct = stats['percentage']
                uncovered = stats['uncovered']
                report.append(f"  ⚠️  {filename:45} {pct:5.1f}% ({stats['executed']:2}/{stats['total']:3} 行)")
                report.append(f"      → 需要新增 {uncovered} 行的测试，可提升至 50-60%")
        else:
            report.append("  ✅ 无低覆盖模块")
        report.append("")
        
        # 优先级 3: 中等覆盖模块
        report.append("🟠 【优先级 3】中等覆盖模块 (10-30%) - 逐步优化")
        report.append("-" * 100)
        if medium_coverage:
            sorted_medium = sorted(
                medium_coverage.items(),
                key=lambda x: x[1]['uncovered'],
                reverse=True
            )
            for filename, stats in sorted_medium:
                pct = stats['percentage']
                uncovered = stats['uncovered']
                report.append(f"  🟡 {filename:45} {pct:5.1f}% ({stats['executed']:2}/{stats['total']:3} 行)")
                report.append(f"      → 需要新增 {uncovered} 行的测试")
        else:
            report.append("  ✅ 无中等覆盖模块")
        report.append("")
        
        # 优先级 4: 高覆盖模块
        report.append("✅ 【优先级 4】高覆盖模块 (>=30%) - 维持或进一步优化")
        report.append("-" * 100)
        if high_coverage:
            sorted_high = sorted(
                high_coverage.items(),
                key=lambda x: x[1]['percentage'],
                reverse=True
            )
            for filename, stats in sorted_high:
                pct = stats['percentage']
                report.append(f"  ✅ {filename:45} {pct:5.1f}%")
        else:
            report.append("  ℹ️  无高覆盖模块")
        report.append("")
        
        return "\n".join(report)
    
    def generate_actionable_plan(self) -> str:
        """生成可执行的优化计划"""
        plan = []
        plan.append("=" * 100)
        plan.append("🎯 可执行优化计划")
        plan.append("=" * 100)
        plan.append("")
        
        plan.append("【第 1 周 - 数据模型快速提升】")
        plan.append("-" * 100)
        plan.append("目标: 2.6% → 15%")
        plan.append("")
        plan.append("任务 1.1: DiagramItem 扩展测试")
        plan.append("  • 文件: tests/generated/test_diagram_item_extended.cpp")
        plan.append("  • 使用提示词: phase1_diagram_item")
        plan.append("  • 目标覆盖: 6.1% → 45% (+350行)")
        plan.append("  • 关键方法: setFont, setScene, isMoving, contextMenuEvent, itemChange, mouse events")
        plan.append("")
        
        plan.append("任务 1.2: DiagramPath 完整测试")
        plan.append("  • 文件: tests/generated/test_diagram_path_complete.cpp")
        plan.append("  • 使用提示词: phase1_diagram_path")
        plan.append("  • 目标覆盖: 0% → 50% (+80行)")
        plan.append("  • 关键方法: addPoint, boundingRect, paint, shape")
        plan.append("")
        
        plan.append("任务 1.3: DiagramItemGroup 扩展测试")
        plan.append("  • 文件: tests/generated/test_diagram_item_group_extended.cpp")
        plan.append("  • 使用提示词: phase1_diagram_item_group")
        plan.append("  • 目标覆盖: 8.9% → 40% (+120行)")
        plan.append("  • 关键方法: addItem, removeItem, boundingRect, items, transforms")
        plan.append("")
        
        plan.append("【第 2 周 - 编译和验证】")
        plan.append("-" * 100)
        plan.append("1. 在 LLM 中运行生成的提示词")
        plan.append("2. 将生成的 .cpp 文件添加到 tests/generated/")
        plan.append("3. 更新 tests/generated/tests.pro 的 SOURCES 和 HEADERS")
        plan.append("4. 编译: cd tests\\generated && qmake tests.pro && mingw32-make -f Makefile.Debug")
        plan.append("5. 运行测试: .\\debug\\generated_tests.exe")
        plan.append("6. 生成报告: gcovr --root . --html-details reports/coverage_report.html")
        plan.append("")
        
        plan.append("【成功标准】")
        plan.append("-" * 100)
        plan.append("✅ 所有新测试编译通过（无错误，警告 <= 2 个）")
        plan.append("✅ 所有新测试执行通过（失败数 <= 原有失败数）")
        plan.append("✅ 覆盖率提升至 15%+ (427+/2848 行)")
        plan.append("✅ DiagramItem >= 35%、DiagramPath >= 40%、DiagramItemGroup >= 35%")
        plan.append("")
        
        return "\n".join(plan)


def main():
    """主函数"""
    
    # 查找覆盖率报告 - 寻找两个可能的位置
    report_paths = [
        Path("../Diagramscene_ultima-syz/reports/coverage_report.html"),
        Path("C:/Users/lenovo/Desktop/Diagramscene_ultima-syz/reports/coverage_report.html"),
    ]
    
    report_path = None
    for path in report_paths:
        if path.exists():
            report_path = path
            break
    
    if not report_path or not report_path.exists():
        print(f"❌ 找不到覆盖率报告: {report_path}")
        return
    
    analyzer = CoverageAnalyzer(str(report_path))
    
    # 解析报告
    print("📊 正在分析覆盖率报告...")
    coverages = analyzer.parse_html_report(str(report_path))
    
    # 生成报告
    optimization_report = analyzer.generate_optimization_report(coverages)
    action_plan = analyzer.generate_actionable_plan()
    
    # 输出到控制台
    print("\n" + optimization_report)
    print("\n" + action_plan)
    
    # 保存报告
    output_dir = Path("../Diagramscene_ultima-syz/reports").resolve()
    output_dir.mkdir(exist_ok=True)
    
    report_file = output_dir / "optimization_analysis.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(optimization_report)
        f.write("\n\n")
        f.write(action_plan)
    
    print(f"\n✅ 分析报告已保存到: {report_file}")


if __name__ == "__main__":
    main()
