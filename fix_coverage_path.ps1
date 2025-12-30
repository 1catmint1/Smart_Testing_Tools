# 快速修复 Smart_Testing_Tools 覆盖率命令路径
# 解决：覆盖率命令中的 object-directory 路径不存在问题

$ProjectRoot = "C:\Users\lenovo\Desktop\Diagramscene_ultima-syz"
$PyPath = "D:\Anaconda\envs\py312_env\python.exe"
$GcovExe = "D:/Qt/Tools/mingw1310_64/bin/gcov.exe"

# 正确的覆盖率命令（指向实际的编译输出目录）
$CorrectCmd = "$PyPath -m gcovr -r `"$ProjectRoot`" --object-directory debug --gcov-executable $GcovExe --exclude-directories .git --exclude-directories .venv --exclude-directories tools --exclude-directories generated_tests --print-summary --html-details -o coverage.html --json=coverage.json"

Write-Host "========== 覆盖率命令修复 ==========" -ForegroundColor Green
Write-Host ""
Write-Host "✓ 项目路径: $ProjectRoot" -ForegroundColor Cyan
Write-Host "✓ 编译输出目录: debug (而不是 tests/build/...)" -ForegroundColor Cyan
Write-Host "✓ Python 路径: $PyPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "正确的覆盖率命令:" -ForegroundColor Yellow
Write-Host $CorrectCmd
Write-Host ""
Write-Host "操作说明:" -ForegroundColor Green
Write-Host "1. 打开 Smart_Testing_Tools (main.py)"
Write-Host "2. 进入 Settings -> Automation -> 覆盖率命令"
Write-Host "3. 清空现有命令"
Write-Host "4. 复制下方命令粘贴到输入框"
Write-Host "5. 点击 '保存命令配置'"
Write-Host ""
Write-Host "════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "【复制此命令到 Smart_Testing_Tools UI】:" -ForegroundColor Yellow
Write-Host ""

# 简化版本用于复制
$SimpleCmd = "python -m gcovr -r . --object-directory debug --gcov-executable D:/Qt/Tools/mingw1310_64/bin/gcov.exe --exclude-directories .git --exclude-directories .venv --exclude-directories tools --exclude-directories generated_tests --print-summary --html-details -o coverage.html --json=coverage.json"
Write-Host $SimpleCmd
Write-Host ""
Write-Host "════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "注意事项:" -ForegroundColor Magenta
Write-Host "• --object-directory debug 指向项目根目录下的 debug/ 文件夹"
Write-Host "• 该目录包含编译生成的 .gcda 和 .gcno 覆盖率数据文件"
Write-Host "• 确保项目编译后再运行覆盖率检测"
Write-Host ""
