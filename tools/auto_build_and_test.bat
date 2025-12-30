@echo off
REM 自动化测试生成和编译脚本

setlocal enabledelayedexpansion

echo.
echo ================================================================================
echo                  自动化 LLM 测试生成和编译
echo ================================================================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Python 未安装或不在 PATH 中
    pause
    exit /b 1
)

echo [信息] 检测到 Python
echo.

REM 设置路径
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
set DIAGRAM_ROOT=%PROJECT_ROOT%\..\Diagramscene_ultima-syz
set TESTS_DIR=%DIAGRAM_ROOT%\tests\generated

echo [路径信息]
echo   脚本目录: %SCRIPT_DIR%
echo   项目根目录: %PROJECT_ROOT%
echo   图表项目: %DIAGRAM_ROOT%
echo   测试目录: %TESTS_DIR%
echo.

REM 检查 API Key
echo [API 配置]
if defined OPENAI_API_KEY (
    echo   ✓ OPENAI_API_KEY 已设置
) else if defined ANTHROPIC_API_KEY (
    echo   ✓ ANTHROPIC_API_KEY 已设置
) else (
    echo   [警告] 未设置 API Key，将使用手动模式
    echo   要启用自动生成，请设置以下之一:
    echo     set OPENAI_API_KEY=your_key
    echo     set ANTHROPIC_API_KEY=your_key
)
echo.

REM 运行生成脚本
echo [执行] 运行自动化生成工具...
python "%SCRIPT_DIR%auto_generate_tests.py"

if errorlevel 1 (
    echo [错误] 生成失败
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo                        现在编译生成的测试代码
echo ================================================================================
echo.

REM 编译
echo [编译] 进入测试目录...
cd /d "%TESTS_DIR%"

if errorlevel 1 (
    echo [错误] 无法进入测试目录: %TESTS_DIR%
    pause
    exit /b 1
)

echo [编译] 运行 qmake...
qmake "tests.pro" "CONFIG+=coverage" "CONFIG+=debug"

if errorlevel 1 (
    echo [错误] qmake 失败
    pause
    exit /b 1
)

echo [编译] 运行 mingw32-make...
mingw32-make -f Makefile.Debug -j 6

if errorlevel 1 (
    echo [错误] 编译失败
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo                        运行生成的测试
echo ================================================================================
echo.

echo [执行] 运行测试可执行文件...
if exist "debug\generated_tests.exe" (
    debug\generated_tests.exe
) else (
    echo [错误] 找不到生成的可执行文件
    pause
    exit /b 1
)

echo.
echo ================================================================================
echo                        生成覆盖率报告
echo ================================================================================
echo.

cd /d "%DIAGRAM_ROOT%"

echo [报告] 生成 HTML 覆盖率报告...
gcovr --root . --filter ".*\.(cpp|h)$" --exclude ".*tests.*" --html-details "reports/coverage_report.html"

if errorlevel 1 (
    echo [警告] 覆盖率报告生成失败（不影响主要功能）
) else (
    echo [成功] 覆盖率报告已生成: reports/coverage_report.html
)

echo.
echo ================================================================================
echo                              ✅ 全部完成！
echo ================================================================================
echo.
echo [结果] 新的测试已生成、编译、执行并生成覆盖率报告
echo [下一步] 打开 reports/coverage_report.html 查看覆盖率改进
echo.
pause
