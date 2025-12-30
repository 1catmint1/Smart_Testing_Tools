# 🚀 快速开始 - LLM 测试生成 (集成版)

## 最简单的方式: 3步启动

### 步骤 1: 设置 API 密钥

```powershell
# PowerShell (Windows)
$env:OPENAI_API_KEY = "sk-your-key-here"
# 或
$env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```

### 步骤 2: 运行主程序

```bash
cd C:\Users\lenovo\Desktop\Smart_Testing_Tools-syz
python main.py
```

### 步骤 3: 选择选项

```
主菜单:
  1. 生成测试 (LLM)
  2. 完整周期 (生成 -> 编译 -> 测试 -> 报告) ← 推荐
  3. 启动GUI应用
  0. 退出

请选择 [1-3, 0]: 2
```

**完成!** 10 分钟后你会得到:
- ✅ 生成的测试代码
- ✅ 编译后的测试可执行文件
- ✅ 测试结果 (通过/失败)
- ✅ 覆盖率报告

---

## 进阶用法: 命令行快速执行

### 最快的一行命令

```bash
# 完整周期 (推荐使用 Claude - 质量更好)
python main.py full-cycle -t phase1_diagram_item -s claude

# 或使用 OpenAI
python main.py full-cycle -t phase1_diagram_item -s openai

# 或自动选择
python main.py full-cycle -t phase1_diagram_item -s auto
```

### 生成多个任务

```bash
# 一键生成所有 Phase 1 任务
python main.py generate -t phase1_diagram_item -s auto
python main.py generate -t phase1_diagram_path -s auto
python main.py generate -t phase1_diagram_item_group -s auto

# 然后生成 Phase 2
python main.py generate -t phase2_delete_command -s auto
```

---

## 📊 覆盖率改进预期

使用本系统，你可以期望:

| 阶段 | 覆盖率 | 通过率 | 时间 |
|------|--------|--------|------|
| 开始 | 2.6% | N/A | N/A |
| Phase 1 完成 | 15-20% | 85%+ | ~1-2 小时 |
| Phase 2 完成 | 25-30% | 80%+ | ~2-3 小时 |
| Phase 3+ | 40%+ | 75%+ | 持续迭代 |

---

## 🔧 如果出现问题

### API 密钥错误

```bash
# 验证 API 密钥是否设置
echo $env:OPENAI_API_KEY

# 如果为空，重新设置
$env:OPENAI_API_KEY = "sk-..."

# 验证它有效
python -c "import openai; print('✅ API 配置正确')"
```

### 编译失败

```bash
# 清理旧的构建文件
cd C:\Users\lenovo\Desktop\Diagramscene_ultima-syz\tests\generated
rm -Recurse -Force release debug .qmake.stash Makefile*

# 重新运行生成
cd C:\Users\lenovo\Desktop\Smart_Testing_Tools-syz
python main.py full-cycle -t phase1_diagram_item
```

### 找不到 qmake

```bash
# 添加 Qt 到 PATH
$env:Path += ";C:\Qt\6.7.2\mingw_64\bin"

# 验证
qmake -version

# 重新运行
python main.py full-cycle -t phase1_diagram_item
```

---

## 📈 预期结果示例

```
============================================================
🚀 完整测试生成周期
============================================================

📝 生成测试: phase1_diagram_item...
✅ 生成 8 个测试

🔨 编译测试...
✅ 编译成功

🏃 运行测试...
✅ 测试通过: 6, 失败: 2

✅ 周期完成！
   任务: phase1_diagram_item
   生成测试数: 8
   通过: 6
   失败: 2

📊 覆盖率报告: C:\Users\lenovo\Desktop\Diagramscene_ultima-syz\reports\coverage_report.html
```

---

## 🎯 优化建议

1. **第一次运行**
   - 使用 `phase1_diagram_item` (有现成提示)
   - 使用 Claude API (质量更好)
   - 预计: 8-10 个测试, 80%+ 通过率

2. **逐步扩展**
   - 完成 phase1_diagram_item 后运行 phase1_diagram_path
   - 持续生成新的测试覆盖模块
   - 每个模块 3-4 个迭代改进

3. **监控覆盖率**
   - 每次生成后查看 `reports/coverage_report.html`
   - 跟踪覆盖率改进趋势
   - 识别仍然未覆盖的代码

4. **质量改进**
   - 保存失败测试用例
   - 分析失败原因 (编译错误 vs 运行时错误)
   - 调整提示以改进生成质量

---

## 📝 提示: 保存生成的代码

所有生成的测试代码自动保存到:

```
C:\Users\lenovo\Desktop\Diagramscene_ultima-syz\tests\generated\
├── test_phase1diagramitem.cpp
├── test_phase1diagrampath.cpp
├── test_phase1diagramitemgroup.cpp
└── test_phase2deletecommand.cpp
```

你可以：
- 手动检查和修改代码
- 添加更多测试用例
- 改进失败的测试

---

## 💡 高级用法

### 在脚本中集成

```python
from pathlib import Path
from qt_test_ai.llm_test_generator import LLMTestGenerator

# 创建生成器
gen = LLMTestGenerator(Path("C:/Users/lenovo/Desktop/Diagramscene_ultima-syz"))

# 生成单个任务
result = gen.generate_tests("phase1_diagram_item", llm_service="claude")

# 完整周期
full_result = gen.run_full_cycle("phase1_diagram_item", "auto")

# 检查结果
if full_result["status"] == "success":
    print(f"✅ 生成 {full_result['generation']['tests_generated']} 个测试")
```

### 自定义提示

编辑 `llm_prompts.json` 以自定义测试生成提示：

```json
{
  "phase1_diagram_item": "你自定义的提示文本...",
  "custom_task": "为 MyClass 生成测试..."
}
```

然后运行:
```bash
python main.py generate -t custom_task -s auto
```

---

## 📞 获取帮助

1. **查看完整文档**: `INTEGRATED_LLM_GENERATION.md`
2. **查看生成日志**: 检查控制台输出中的错误消息
3. **验证 API**: 运行 `python main.py generate` 然后查看交互式菜单

---

**使用本系统，你应该在 1-2 小时内将覆盖率从 2.6% 提升到 15%+!** 🎉
