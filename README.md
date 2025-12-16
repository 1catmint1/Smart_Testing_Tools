# Qt 项目测试智能化工具（桌面版）

本工具面向 **Qt（qmake `.pro` / C++）桌面项目**的测试实践与“测试智能化辅助”。它把你课程要求的三类测试内容做成“可操作、可留证、可导出报告、可入库留档”的闭环：

- **功能度测试**：可配置“用例库”（步骤/预期/实际/证据/结果），每次运行形成一次用例执行记录
- **用户文档检查**：自动检查 README/使用说明的基本完整性
- **静态测试方法**：规则扫描（可选自动调用 `cppcheck`）
- **动态测试方法**：启动被测 exe 做检测（进程存活/输出采集），可选 Windows UI 探测（`pywinauto`）
- **自动化测试/覆盖率（可选）**：读取 Qt 工程代码片段 → 调用 LLM 生成 QtTest(QTest) 用例文件 → 调用你配置的测试/覆盖率命令并采集输出

可选的智能化能力（接入 LLM 后开启）：

- **用例生成**：一键生成“功能用例库”初稿（可继续手动编辑/增删）
- **单元测试生成（QtTest）**：自动读取工程代码片段并生成 QtTest 源码文件（输出到本机 `~/.qt_test_ai/generated_tests/...`）
- **结果总结**：对本次运行的结果做自动总结，写入导出报告

> 你要测的项目（例如 `C:\Users\dell\Desktop\diagramscene_ultima`）不需要改代码；本工具以“外部黑盒 + 半自动记录”为主。

---

## 0. 你需要准备什么（非常重要）

### 0.1 操作系统

- 推荐：Windows 10/11

### 0.2 Python 环境

- 推荐 Python 3.10+（本项目在 Windows + venv 下使用）

如果你不确定自己用的是不是虚拟环境，建议统一用以下方式：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 0.3 被测 Qt 工程需要“能生成 exe”

动态测试依赖被测程序 `.exe`。你至少需要在 Qt Creator / 命令行把工程构建出可执行文件：

- Debug 或 Release 都可以
- 确保能在本机双击运行（或命令行运行）

---

## 1. 安装与启动（从零开始）

在本仓库根目录（有 `main.py` / `requirements.txt`）打开 PowerShell：

### 1.1 安装依赖

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 1.2 启动工具

```powershell
.\.venv\Scripts\python.exe main.py
```

> 提示：你也可以在仓库根目录创建 `.env` 文件来配置环境变量（推荐），这样每次启动无需在终端手动 `$env:...`。

启动后你会看到一个桌面窗口，包含：

- 项目目录/被测 exe 选择区
- 自动化测试/覆盖率（可选）
- 功能度测试用例表格（用例库）
- 发现项（自动检测输出）
- 日志
- 右侧历史记录（SQLite）

---

## 2. 一次“完整测试闭环”的推荐流程（照做即可）

下面的步骤按顺序做，最终你会拿到：

1) 一份 HTML 报告（适合交作业/展示）
2) 一份 JSON 报告（适合存档/二次分析）
3) 一条 SQLite 历史记录（可追溯）

### 2.1 选择被测项目目录（必做）

1. 点击按钮：`选择项目目录`
2. 在弹出的文件夹选择框中，选择 **Qt 工程根目录**（包含 `.pro` 的目录）
	 - 例：`C:\Users\dell\Desktop\diagramscene_ultima`
3. 选择成功后，路径会出现在输入框中

**你应该看到什么：**

- 如果工程根目录包含 `*.pro`：静态检查会提取 `.pro` 的基本信息
- 如果不包含 `*.pro`：静态检查会提示“未发现 .pro 文件”（不一定是错，但会提示你确认工程类型）

### 2.2 选择被测 exe（强烈建议做）

1. 点击按钮：`选择 exe（可选）`
2. 选择你构建出来的被测程序 `.exe`

**不选 exe 会怎样：**

- 工具会尝试在常见目录自动搜索（例如 `build/`、`debug/`、`release/` 等）
- 若找不到，就会在“发现项”里给出 `dynamic` 类别的 `error`，提示你需要先构建

### 2.3 功能度测试（用例库 + 执行记录）

“功能度测试用例”区域是一个 8 列表格：

1. `ID`：用例编号，例如 `F01`
2. `用例`：用例名称
3. `步骤`：多行文本，每行一个步骤
4. `预期`：期望结果
5. `实际`：你本次执行观察到的结果（每次运行都要填）
6. `结果`：下拉选择
	 - `通过` / `失败` / `阻塞` / `不适用`
7. `证据`：建议填写证据路径或关键日志位置
8. `备注`：补充说明

你可以用按钮快速维护用例：

- `新增用例`：添加一条空用例
- `删除选中`：删除当前选中用例
- `LLM 生成用例`：用 LLM 生成一版用例库初稿（可选）

#### 2.3.1 维护用例库（可配置）

如果你们团队要维护自己的用例库：

1. 直接在表格里编辑 `ID/用例/步骤/预期`
2. 点击 `保存用例库(JSON)`
3. 选择一个保存路径，例如 `D:\test\case_library.json`

之后任何人都可以：

1. 点击 `加载用例库(JSON)`
2. 选择该 JSON 文件
3. 表格会被用例库内容刷新

#### 2.3.2 填写执行记录（每次测试都要填）

在你们执行测试时，建议每条用例都至少填写：

- `实际`：如“启动后 2 秒出现主窗口；无崩溃；可拖拽图元”
- `结果`：通过/失败/阻塞/不适用
- `证据`：如 `D:\evidence\functional\F01.mp4` 或 `日志：D:\logs\run_1213.txt L120-L170`

**关于“失败/阻塞”的建议：**

- `失败`：功能行为与预期不一致（属于缺陷）
- `阻塞`：无法执行该用例（例如环境缺少文件、入口不可达、程序崩溃导致后续用例无法继续）

> 你选择“失败”的用例，会在“发现项”里生成 `functional` 类别的 `error`，便于报告里一眼看到问题。

### 2.4 一键运行（静态/动态/文档/自动化）

1. 点击按钮：`一键运行（静态/动态/文档/自动化）`
2. 等待运行结束（看“日志”区域的进度提示）

这一按钮会做两类事情：

**A. 自动化检查（静态/动态/文档）**

- 静态：规则扫描；如系统已安装 `cppcheck` 并加入 PATH，会自动调用增强
- 动态：尝试启动被测 exe，做通用检测（进程存活/输出采集）
- 可选：Windows UI 探测（依赖 `pywinauto`，尝试识别是否出现可见窗口）
- 文档：检查 README/使用说明是否覆盖安装/运行/功能等关键内容

**B. 可选的自动化测试/覆盖率（需要你配置命令）**

- 开关：设置环境变量 `QT_TEST_AI_ENABLE_AUTOMATION=1`
- 自动生成 QtTest 用例文件（输出到本机 `~/.qt_test_ai/generated_tests/...`）
- 自动执行测试命令（可选）：`QT_TEST_AI_TEST_CMD`
- 自动执行覆盖率命令（可选）：`QT_TEST_AI_COVERAGE_CMD`

> 说明：覆盖率依赖你们的构建方式与工具链（例如 gcovr/llvm-cov/OpenCppCoverage 等）。本工具只负责“调度命令 + 采集输出 + 写入报告”。

#### 2.4.1 qmake + MinGW + gcovr（可直接用的示例）

覆盖率要生效，必须满足两点：

1) 用 `--coverage`（或 `-fprofile-arcs -ftest-coverage`）重新编译工程
2) 先运行测试，生成 `.gcda` 文件，然后再跑 `gcovr`

另外你需要理解：

- **QtTest 可执行文件**：指你们 tests 工程编译出来的 `tst_xxx.exe`（或类似名字）。它不是主程序 exe，而是“运行后自动执行测试并以退出码表示通过/失败”的测试程序。
- **gcov vs gcovr**：
	- `gcov` 通常随 MinGW 的 GCC 一起提供（负责读取/生成覆盖率数据）
	- `gcovr` 是额外的汇总工具（负责生成摘要/HTML/XML），通常需要 `pip install gcovr`

本工具在 Windows 上执行命令通常走 `cmd.exe`，所以示例用 `cmd /c "..."`。

先确认你的环境里 `gcovr` 可用（推荐装在本工具的 venv 里）：

```powershell
.\.venv\Scripts\python.exe -m pip install gcovr
gcovr --version
```

在仓库根目录复制 `.env.example` 为 `.env` 后，填入类似：

```dotenv
# 先覆盖率编译 + 跑 QtTest（把 .\tests\tst_all.exe 换成你实际的测试可执行文件）
QT_TEST_AI_ENABLE_AUTOMATION=1
QT_TEST_AI_TEST_CMD=cmd /c "qmake -r QMAKE_CXXFLAGS+=-O0 QMAKE_CXXFLAGS+=-g QMAKE_CXXFLAGS+=--coverage QMAKE_LFLAGS+=--coverage && mingw32-make clean && mingw32-make -j && .\\tests\\tst_all.exe"

# 再用 gcovr 汇总覆盖率并输出 HTML
QT_TEST_AI_COVERAGE_CMD=cmd /c "gcovr -r . --gcov-executable gcov --exclude-directories .git --exclude-directories build --exclude-directories .venv --exclude-directories generated_tests --print-summary --html-details -o coverage.html"
```

如果你使用 shadow build（比如编译输出在 `build_debug/`），给 gcovr 增加对象目录：

```dotenv
QT_TEST_AI_COVERAGE_CMD=cmd /c "gcovr -r . --object-directory build_debug --gcov-executable gcov --print-summary --html-details -o coverage.html"
```

如果你的 tests 工程已经在本机编译好，并且你只想“直接运行测试 exe”（不在命令里重新编译），也可以写成绝对路径：

```dotenv
QT_TEST_AI_TEST_CMD=D:\\qt_project\\Diagramscene_ultima\\tests\\build\\Desktop_Qt_6_10_1_MinGW_64_bit-Debug\\debug\\test_diagramitems.exe
QT_TEST_AI_COVERAGE_CMD=gcovr -r . --object-directory tests\\build\\Desktop_Qt_6_10_1_MinGW_64_bit-Debug\\debug --gcov-executable gcov --print-summary --html-details -o coverage.html
```

注意：若你当前这个 `test_diagramitems.exe` 不是用 `--coverage` 编译出来的，运行后不会产生 `.gcda`，那 `gcovr` 只能得到 0% 或找不到数据。此时需要按上面的方式“清理 + 覆盖率参数重新编译 + 再运行测试”。

如果 `gcovr` 找不到：

- 推荐：在系统 Python/你启动工具用的 Python 环境里安装 `gcovr`（`pip install gcovr`），并确保其在 PATH
- 或者：把 `gcovr.exe` 写成绝对路径放进 `QT_TEST_AI_COVERAGE_CMD`

**C. 记录你填写的“功能用例结果”**

- 将当前表格内容写入：
	- SQLite 历史记录
	- HTML/JSON 报告（导出时）

### 2.5 导出报告（HTML + JSON）

1. 点击：`导出报告`
2. 选择一个导出目录（例如 `D:\reports`）

导出后会生成两份文件：

- `qt_test_report_YYYYMMDD_HHMMSS.html`：适合直接提交/展示
- `qt_test_report_YYYYMMDD_HHMMSS.json`：结构化数据（便于后续统计/归档）

### 2.7 查看历史记录（SQLite）

右侧“历史记录（SQLite）”区域会自动保存每次运行。

你可以：

1. 在列表中点选一条记录
2. 点击：`加载选中记录`

加载后会：

- 回显当次“发现项”
- 回填当次“功能用例执行记录”

数据库默认位置：

- `%USERPROFILE%\.qt_test_ai\runs.sqlite3`

---

## 3. 功能用例库 JSON 格式（可直接复制使用）

你们团队可以把用例库统一维护成一个 JSON 文件，格式如下（v1）：

```json
{
	"schema": "qt_test_ai.functional_cases.v1",
	"cases": [
		{
			"case_id": "F01",
			"title": "程序可正常启动并显示主窗口",
			"steps": [
				"启动程序",
				"观察是否出现主窗口"
			],
			"expected": "主窗口在合理时间内出现；无崩溃；界面可交互。",
			"tags": ["smoke"]
		}
	]
}
```

说明：

- `case_id/title/steps/expected` 是核心字段
- `tags` 可选（用于你们自己分类/统计；工具不会强依赖它）

---

## 4. 外部工具（可选增强）

### 4.1 cppcheck（静态增强）

- 若已安装并加入 PATH，静态检查会自动调用
- 你可以在 PowerShell 验证：

```powershell
cppcheck --version
```

### 4.2 pywinauto（Windows UI 探测）

- 默认依赖已在 `requirements.txt` 中
- 若你不想使用 UI 探测，可以在界面里取消勾选“启用 Windows UI 探测（pywinauto）”

### 4.3 LLM（可选：让工具更智能）

本工具的 LLM 按钮默认是“可选能力”：

- **不配置**：工具仍可完整使用（只是 LLM 相关按钮不可用）
- **配置后**：可使用“生成清单/用例”和“总结本次结果”

你需要设置以下环境变量（OpenAI 兼容接口）：

- `QT_TEST_AI_LLM_BASE_URL`：例如 `https://api.openai.com` 或你自己的网关地址
- `QT_TEST_AI_LLM_MODEL`：例如 `gpt-4o-mini`（以你的服务端实际支持为准）
- `QT_TEST_AI_LLM_API_KEY`：可选（本地网关可能不需要）
- `QT_TEST_AI_LLM_SYSTEM_PROMPT`：可选（自定义系统提示词；不设置也能用）

PowerShell 示例：

```powershell
$env:QT_TEST_AI_LLM_BASE_URL="https://api.openai.com"
$env:QT_TEST_AI_LLM_MODEL="gpt-4o-mini"
$env:QT_TEST_AI_LLM_API_KEY="你的key"
.\.venv\Scripts\python.exe main.py
```

更推荐的方式：使用 `.env` 文件（无需每次手动设置）。

1) 将仓库根目录的 `.env.example` 复制为 `.env`
2) 编辑 `.env` 填入你的配置
3) 正常启动 `main.py` 即可（启动时会自动加载 `.env`）

如何使用：

1) 在“功能测试用例”页点击 `LLM 生成用例`
2) （可选）启用自动化：设置 `QT_TEST_AI_ENABLE_AUTOMATION=1`，并配置 `QT_TEST_AI_TEST_CMD` / `QT_TEST_AI_COVERAGE_CMD`
3) 完成一次“一键运行”后，在“发现项”页点击 `LLM 总结本次结果`（总结会写入日志并随 HTML 报告导出）

是否需要你自己写提示词？

- **一般不需要**：工具内置了提示词，确保“生成用例”返回严格 JSON，方便自动导入表格。
- 如果你想让 LLM 更贴合你们项目（例如强调某些业务/评分点），可以设置 `QT_TEST_AI_LLM_SYSTEM_PROMPT`，示例：
	- `你是软件测试助手。只输出严格JSON，不要输出多余文字。优先覆盖Qt桌面应用的功能度/用户文档检查，并给出可复现的步骤。`

---

## 4.4 覆盖率（qmake + MinGW + gcovr）常见问题

### 4.4.1 我有 `test_diagramitems.exe`，但不是用 `--coverage` 编译的

这很常见：**只有用 `--coverage` 重新编译出来的测试程序**，运行后才会生成 `.gcda`，`gcovr` 才能统计到覆盖率。

你可以用“在 shadow build 目录里重新 qmake + make，然后再运行测试 exe”的方式解决。

以你的路径为例（tests 工程 `.pro`：`D:\qt_project\Diagramscene_ultima\tests\tests.pro`；shadow build：`...\tests\build\Desktop_Qt_6_10_1_MinGW_64_bit-Debug\debug`）：

```powershell
cmd /c cd /d D:\qt_project\Diagramscene_ultima\tests\build\Desktop_Qt_6_10_1_MinGW_64_bit-Debug\debug ^
	&& qmake D:\qt_project\Diagramscene_ultima\tests\tests.pro -r QMAKE_CXXFLAGS+=-O0 QMAKE_CXXFLAGS+=-g QMAKE_CXXFLAGS+=--coverage QMAKE_LFLAGS+=--coverage ^
	&& mingw32-make clean ^
	&& mingw32-make -j ^
	&& .\test_diagramitems.exe
```

随后在项目根目录运行 gcovr（或配置到本工具的 `QT_TEST_AI_COVERAGE_CMD`）：

```powershell
gcovr -r D:\qt_project\Diagramscene_ultima --object-directory D:\qt_project\Diagramscene_ultima\tests\build\Desktop_Qt_6_10_1_MinGW_64_bit-Debug\debug --gcov-executable gcov --print-summary --html-details -o coverage.html
```

提示：如果 `mingw32-make`/`gcov` 找不到，请确保 Qt 的 MinGW 工具链在 PATH（通常打开 Qt Creator 的 Kit 环境或把对应 `...\mingw_64\bin` 加入 PATH）。

---

## 5. 常见问题排查（按现象对照）

### 5.1 启动工具时报 `ModuleNotFoundError: No module named 'PySide6'`

原因：依赖没装到你正在用的 Python 环境里。

解决：务必用同一个解释器安装与运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

### 5.2 动态测试提示“未找到可执行文件 .exe”

原因：被测 Qt 工程还没构建出 exe，或构建目录不在常见位置。

解决：

1. 先在 Qt Creator 完成一次构建，找到生成的 `.exe`
2. 在工具里点 `选择 exe（可选）` 手动选择该 exe

### 5.3 动态检测启动失败/一闪而退

常见原因：

- exe 依赖的 DLL/插件路径缺失
- 工作目录不正确导致找不到资源文件

建议：

- 先在命令行/双击确认 exe 能独立运行
- 若依赖 Qt 运行时，确保使用 Qt Creator 生成的运行环境或正确部署（如 windeployqt）

### 5.4 报告里“功能用例”显示未记录

原因：

- 你没有点击“一键运行”（该按钮会把当前表格内容写入一次 TestRun）

解决：

- 填完表格后，点击“一键运行（静态/动态/文档/自动化）”，再导出报告

### 5.5 LLM 按钮不可用

原因：未配置 LLM 环境变量。

解决：设置 `QT_TEST_AI_LLM_BASE_URL` 和 `QT_TEST_AI_LLM_MODEL`（如需要再加 `QT_TEST_AI_LLM_API_KEY`），然后重新启动工具。

---

## 6. 针对你的 Qt 项目（示例）

被测项目目录示例：

- `C:\Users\dell\Desktop\diagramscene_ultima`

建议：先在 Qt Creator 里完成一次构建，确保生成 `.exe`（Debug/Release 都可以），然后在本工具里：

1. 选择项目目录
2. 选择 exe
3. 填写功能用例实际/证据
4. （可选）配置自动化测试/覆盖率命令
5. 一键运行
6. 导出 HTML/JSON
