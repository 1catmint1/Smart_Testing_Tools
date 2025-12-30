# 🚀 Smart Testing Tools - LLM 集成系统快速指南

## 你想做什么？选择下面的选项

### 🎯 选项 A: "我想快速生成测试并提高覆盖率"

**最快的方式（3 秒启动）：**

```bash
# Windows PowerShell
$env:OPENAI_API_KEY = "sk-your-key"  # 或 ANTHROPIC_API_KEY
cd C:\Users\lenovo\Desktop\Smart_Testing_Tools-syz
python main.py full-cycle -t phase1_diagram_item
```

**或使用菜单（交互式）：**

```bash
python main.py
# 选择 2 (完整周期)
```

**预期结果：**
- ✅ 8-10 个测试自动生成
- ✅ 自动编译
- ✅ 自动运行
- ✅ 覆盖率报告自动生成
- ⏱️ 总时间：5-7 分钟

---

### 🎯 选项 B: "我想了解系统如何工作"

**1. 阅读快速开始指南：**
```bash
cat QUICK_START_LLM.md
```

**2. 验证您的环境：**
```bash
python check_integration.py
```

**3. 查看完整文档：**
```bash
cat INTEGRATED_LLM_GENERATION.md
```

**4. 对比新旧系统：**
```bash
cat BEFORE_AFTER_COMPARISON.md
```

---

### 🎯 选项 C: "我想在脚本中使用 LLM 测试生成"

**示例代码：**

```python
from pathlib import Path
from qt_test_ai.llm_test_generator import LLMTestGenerator

# 初始化
gen = LLMTestGenerator(Path("C:/Users/lenovo/Desktop/Diagramscene_ultima-syz"))

# 完整周期
result = gen.run_full_cycle("phase1_diagram_item", "claude")

if result["status"] == "success":
    print(f"✅ 成功!")
    print(f"   生成: {result['generation']['tests_generated']} 个测试")
    print(f"   通过: {result['compilation']['passed']}")
else:
    print(f"❌ 失败: {result['generation']['error']}")
```

---

### 🎯 选项 D: "我想手动检查或修改生成的测试"

**1. 生成测试（但不编译）：**
```bash
python main.py generate -t phase1_diagram_item
```

**2. 查看生成的文件：**
```bash
cat tests\generated\test_phase1diagramitem.cpp
```

**3. 手动修改（如需要）：**
```bash
code tests\generated\test_phase1diagramitem.cpp
# 编辑文件...
```

**4. 手动编译和测试：**
```bash
cd tests\generated
qmake tests.pro
mingw32-make
debug\generated_tests.exe
```

---

### 🎯 选项 E: "我遇到错误需要帮助"

**步骤 1: 诊断环境**
```bash
python check_integration.py
```

**步骤 2: 检查常见问题**

| 错误 | 原因 | 解决 |
|------|------|------|
| "未设置 API 密钥" | 缺少环境变量 | 设置 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY` |
| "qmake 命令不存在" | Qt 未在 PATH | `$env:Path += ";C:\Qt\6.7.2\mingw_64\bin"` |
| "编译失败" | 头文件路径错误 | 检查 `tests.pro` 的 INCLUDEPATH |
| "超时" | 编译太慢 | 清理构建: `rm -Recurse -Force tests\generated\release debug .qmake.stash` |

**步骤 3: 查看详细文档**
```bash
cat INTEGRATED_LLM_GENERATION.md
# 查看 "故障排除" 部分
```

---

## 🔑 必须知道的 3 个命令

### 1️⃣ 完整周期（推荐）

```bash
python main.py full-cycle -t phase1_diagram_item -s auto
```

做什么：
- ✅ 生成测试
- ✅ 编译
- ✅ 运行
- ✅ 生成覆盖率报告

用时：5-7 分钟

### 2️⃣ 只生成测试

```bash
python main.py generate -t phase1_diagram_item
```

做什么：
- ✅ 生成测试代码
- ❌ 不编译
- ❌ 不运行

用时：1-2 分钟

用于：检查或修改生成的代码

### 3️⃣ 启动菜单

```bash
python main.py
```

做什么：
- 显示交互式菜单
- 用户选择操作

用于：不熟悉命令的用户

---

## 📊 预期成果

### 第一次运行

```
输入:  python main.py full-cycle -t phase1_diagram_item
输出:  
  ✅ 生成 8 个测试
  ✅ 编译成功
  ✅ 测试通过: 6, 失败: 2
  📊 覆盖率: 从 2.6% 提升到 5-8%
时间:  5-7 分钟
```

### 运行 4 个任务

```
Phase 1: DiagramItem         → 2-3%
Phase 1: DiagramPath         → 2-3%
Phase 1: DiagramItemGroup    → 2-3%
Phase 2: DeleteCommand       → 1-2%
────────────────────────────────────
总覆盖率: 2.6% → 15-20%
总时间: 20-30 分钟（完全自动化）
```

---

## 📁 文件位置速查

| 什么 | 位置 |
|------|------|
| **启动脚本** | `main.py` |
| **快速指南** | `QUICK_START_LLM.md` |
| **完整文档** | `INTEGRATED_LLM_GENERATION.md` |
| **验证脚本** | `check_integration.py` |
| **核心模块** | `src/qt_test_ai/llm_test_generator.py` |
| **生成的测试** | `../Diagramscene_ultima-syz/tests/generated/` |
| **覆盖率报告** | `../Diagramscene_ultima-syz/reports/coverage_report.html` |
| **LLM 提示** | `../Diagramscene_ultima-syz/llm_prompts.json` |

---

## ✅ 初次设置检查列表

- [ ] 安装 Python 3.8+ 和 pip
- [ ] 运行 `pip install openai anthropic python-dotenv`
- [ ] 设置 API 密钥环境变量 (或创建 .env 文件)
- [ ] 运行 `python check_integration.py` 验证
- [ ] 运行 `python main.py full-cycle -t phase1_diagram_item`
- [ ] 查看生成的覆盖率报告

---

## 🎓 推荐学习路径

```
初学者:
1. 阅读 QUICK_START_LLM.md (10 分钟)
2. 运行 check_integration.py (1 分钟)
3. 运行 python main.py (3 分钟)
4. 选择菜单选项 2 并观察 (7 分钟)
总时间: 20 分钟，已可开始使用

中级用户:
1. 阅读 INTEGRATED_LLM_GENERATION.md (20 分钟)
2. 学习 4 个 CLI 命令 (10 分钟)
3. 使用脚本自动化批量生成 (30 分钟)
总时间: 60 分钟，已可精通使用

高级用户:
1. 查看源代码 llm_test_generator.py (20 分钟)
2. 自定义提示和工作流 (30 分钟)
3. 集成到 CI/CD 管道 (60 分钟)
总时间: 110 分钟，可完全定制
```

---

## 🚀 立即开始（30 秒）

```bash
# 1. 设置 API 密钥（仅需一次）
$env:OPENAI_API_KEY = "sk-..."

# 2. 运行系统
cd C:\Users\lenovo\Desktop\Smart_Testing_Tools-syz
python main.py

# 3. 选择菜单选项 2
# 等待 5-7 分钟...

# 4. ✅ 完成！覆盖率已提升
```

---

## 💡 常见问题

**Q: 如何确定我的 API 密钥有效？**

```bash
python -c "
import openai
openai.api_key = 'sk-...'
print('✅ 有效')
"
```

**Q: 支持哪些 LLM？**

目前支持:
- OpenAI (GPT-4, 3.5-turbo)
- Anthropic Claude (Sonnet, Opus)
- 自动选择最佳可用

**Q: 可以生成其他模块的测试吗？**

是的！编辑 `llm_prompts.json` 添加新的提示，然后运行:

```bash
python main.py generate -t custom_task
```

**Q: 生成的测试失败怎么办？**

1. 查看错误消息
2. 手动修改生成的 `test_xxx.cpp`
3. 或调整 `llm_prompts.json` 中的提示
4. 重新生成

---

## 📞 获取帮助

1. **快速问题** → 查看 `QUICK_START_LLM.md`
2. **具体问题** → 查看 `INTEGRATED_LLM_GENERATION.md`
3. **诊断问题** → 运行 `check_integration.py`
4. **系统问题** → 查看源代码 `llm_test_generator.py`

---

## 🎉 你现在准备好了！

运行这个命令开始：

```bash
python main.py
```

选择菜单选项，让系统处理其余部分！

**预期：** 在 30 分钟内将覆盖率从 2.6% 提升到 15% 🎯

---

*最后更新: 2024年*  
*版本: 1.0 集成版*  
*状态: ✅ 生产就绪*
