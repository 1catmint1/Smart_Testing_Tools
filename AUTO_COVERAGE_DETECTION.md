# Smart_Testing_Tools 自动覆盖率命令配置

## ✨ 新功能说明

Smart_Testing_Tools 现已支持**自动检测并配置覆盖率命令**。

### 工作流程

```
用户点击 "选择项目目录"
    ↓
自动执行检测脚本
    ↓
识别编译输出目录（debug、build 等）
    ↓
自动生成覆盖率命令
    ↓
自动填充到 UI 的 "覆盖率命令" 字段
    ↓
用户无需手动输入！
```

---

## 🚀 使用方法

### 步骤1：打开 Smart_Testing_Tools

```powershell
cd C:\Users\lenovo\Desktop\Smart_Testing_Tools-syz
python main.py
```

### 步骤2：进入 "项目配置" 页面

点击导航栏中的 **"项目配置"** 标签页。

### 步骤3：点击 "选择项目目录"

- 点击项目目录旁的 **"选择项目目录"** 按钮
- 选择您的 Qt 项目根目录（例如 Diagramscene_ultima-syz）
- 确定

### 步骤4：自动配置完成 ✅

您会看到：
1. 项目路径被填充
2. 弹出提示信息："覆盖率命令已自动配置"
3. 进入 **"自动化测试"** 页面，您会看到覆盖率命令已自动填充！

```
覆盖率命令: gcovr -r . --object-directory debug --exclude-directories ...
```

---

## 🔍 自动检测的逻辑

脚本会按优先级检测以下编译输出目录：

1. `debug/` ← 最常见（Qt Creator MinGW）
2. `build/debug/` ← CMake Debug
3. `build/` ← 一般 build 目录
4. `Release/` ← Visual Studio Release
5. `Debug/` ← Visual Studio Debug
6. `cmake-build-debug/` ← CLion Debug

如果上述目录都不存在，默认使用 `debug/`。

---

## 🛠️ 技术细节

### 涉及的文件

| 文件 | 说明 |
|------|------|
| `src/qt_test_ai/app.py` | 主应用，包含自动检测逻辑 |
| `tools/auto_detect_coverage_cmd.py` | 检测脚本，识别编译输出目录 |

### 修改内容

在 `app.py` 的 `_pick_project()` 方法中添加了：
- 调用 `_auto_detect_coverage_cmd()` 方法
- 自动运行检测脚本
- 自动填充 UI 字段
- 保存到环境变量

---

## ✅ 测试验证

运行测试脚本验证功能：

```powershell
D:\Anaconda\envs\py312_env\python.exe "C:\Users\lenovo\Desktop\Smart_Testing_Tools-syz\test_auto_coverage.py"
```

输出示例：
```
✅ 自动检测成功!
✅ 命令格式正确 (以 'gcovr' 开头)

在 Smart_Testing_Tools 中:
   1. 点击 '选择项目目录' 按钮
   2. 选择项目后，覆盖率命令会自动填充
   3. 无需手动输入！
```

---

## 💡 故障排除

### 问题：覆盖率命令没有自动填充

**原因1**：检测脚本执行失败
- 检查 `auto_detect_coverage_cmd.py` 是否存在
- 检查项目路径是否正确

**原因2**：编译输出目录不是标准位置
- 脚本检测不到您的自定义编译目录
- 解决：手动复制检测脚本的输出到覆盖率命令字段

**原因3**：没有编译产物
- 确保项目已编译过（存在 `.gcda` 覆盖率数据文件）

### 问题：检测脚本报错 "File not found"

**解决**：
```powershell
# 手动运行检测脚本
D:\Anaconda\envs\py312_env\python.exe `
  "C:\Users\lenovo\Desktop\Smart_Testing_Tools-syz\tools\auto_detect_coverage_cmd.py" `
  "C:\Users\lenovo\Desktop\Diagramscene_ultima-syz" `
  --print-only
```

---

## 🎯 下一步

现在您可以：
1. ✅ 选择项目后自动获得覆盖率命令
2. ✅ 进入 "自动化测试" 页面查看
3. ✅ 无需手动修改，直接使用
4. ✅ 一键运行生成测试和覆盖率报告

系统已完全自动化！
