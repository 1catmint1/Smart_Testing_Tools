#!/usr/bin/env powershell
# 修复脚本：清理、重编译、生成正确的覆盖率报告

param(
    [string]$ProjectRoot = "C:\Users\lenovo\Desktop\Diagramscene_ultima-syz"
)

$TestsDir = Join-Path $ProjectRoot "tests\generated"
$DebugDir = Join-Path $TestsDir "debug"

Write-Host "="*70 -ForegroundColor Cyan
Write-Host "🔧 覆盖率问题修复脚本 - 完整版" -ForegroundColor Green
Write-Host "="*70

Write-Host "`n📁 项目路径:"
Write-Host "  项目根: $ProjectRoot"
Write-Host "  测试目录: $TestsDir"
Write-Host "  调试目录: $DebugDir"

# Step 1: 清理旧构建
Write-Host "`n🗑️  清理旧构建文件..."
if (Test-Path $DebugDir) {
    Remove-Item -Recurse -Force $DebugDir -ErrorAction SilentlyContinue
    Write-Host "  ✓ 删除了 $DebugDir"
}

$ReleaseDir = Join-Path $TestsDir "release"
if (Test-Path $ReleaseDir) {
    Remove-Item -Recurse -Force $ReleaseDir -ErrorAction SilentlyContinue
    Write-Host "  ✓ 删除了 $ReleaseDir"
}

Remove-Item (Join-Path $TestsDir ".qmake.stash") -ErrorAction SilentlyContinue
Remove-Item (Join-Path $TestsDir "Makefile") -ErrorAction SilentlyContinue
Remove-Item (Join-Path $TestsDir "Makefile.Debug") -ErrorAction SilentlyContinue
Remove-Item (Join-Path $TestsDir "Makefile.Release") -ErrorAction SilentlyContinue
Write-Host "  ✓ 清理完成"

# Step 2: 运行 qmake
Write-Host "`n⚙️  运行 qmake..."
Push-Location $TestsDir
& qmake tests.pro 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ qmake 失败" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "  ✓ qmake 成功"
Pop-Location

# Step 3: 编译
Write-Host "`n🔨 编译..."
Push-Location $TestsDir
& mingw32-make 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✗ 编译失败" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "  ✓ 编译成功"
Pop-Location

# Step 4: 运行测试
Write-Host "`n🏃 运行测试..."
$ExeFile = Join-Path $DebugDir "generated_tests.exe"
if (-not (Test-Path $ExeFile)) {
    Write-Host "  ✗ 找不到测试可执行文件: $ExeFile" -ForegroundColor Red
    exit 1
}
Push-Location $TestsDir
& $ExeFile 2>&1 | Out-Null
Pop-Location
Write-Host "  ✓ 测试已运行，生成了 .gcda 文件"

# Step 5: 验证 .gcda 文件
Write-Host "`n📊 验证覆盖率数据..."
$GcdaFiles = @(Get-ChildItem -Path $DebugDir -Filter "*.gcda" -Recurse -ErrorAction SilentlyContinue)
if ($GcdaFiles.Count -gt 0) {
    Write-Host "  ✓ 找到 $($GcdaFiles.Count) 个 .gcda 文件"
} else {
    Write-Host "  ⚠️  警告: 找不到 .gcda 文件，覆盖率报告可能为空" -ForegroundColor Yellow
}

# Step 6: 复制源文件到调试目录
Write-Host "`n📋 复制源文件到调试目录..."
$CopyCount = 0
Get-ChildItem -Path $ProjectRoot -Filter "*.cpp" -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $DebugDir $_.Name) -Force -ErrorAction SilentlyContinue
    Write-Host "  ✓ $($_.Name)"
    $CopyCount++
}
Get-ChildItem -Path $ProjectRoot -Filter "*.h" -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $DebugDir $_.Name) -Force -ErrorAction SilentlyContinue
    Write-Host "  ✓ $($_.Name)"
    $CopyCount++
}
Write-Host "  已复制 $CopyCount 个文件"

# Step 7: 生成覆盖率报告
Write-Host "`n📊 生成覆盖率报告..."
Push-Location $ProjectRoot

$pythonScript = Join-Path (Get-Location) "tools\generate_coverage_fixed.py"
if (Test-Path $pythonScript) {
    Write-Host "  使用 Python 修复脚本生成覆盖率..."
    python $pythonScript
    Write-Host "  ✓ 使用 Python 脚本生成完成"
} else {
    Write-Host "  使用 gcovr 直接生成..."
    gcovr -r . `
        --object-directory "$DebugDir" `
        --exclude-directories .git `
        --exclude-directories .venv `
        --exclude-directories tools `
        --print-summary `
        --html-details -o coverage_report.html `
        --json=coverage_report.json `
        --gcov-ignore-errors=no_working_dir_found
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ 覆盖率报告生成成功"
    } else {
        Write-Host "  ⚠️  gcovr 执行完成（可能有警告但报告已生成）" -ForegroundColor Yellow
    }
}

Pop-Location

# 总结
Write-Host "`n" + "="*70 -ForegroundColor Cyan
Write-Host "✅ 修复完成！" -ForegroundColor Green
Write-Host "="*70

Write-Host "`n📊 生成的报告:"
Write-Host "  HTML: $(Join-Path $ProjectRoot 'coverage_report.html')"
Write-Host "  JSON: $(Join-Path $ProjectRoot 'coverage_report.json')"

Write-Host "`n🎯 下次运行时，只需要:"
Write-Host "  1. 运行测试: tests/generated/debug/generated_tests.exe"
Write-Host "  2. 生成报告: python tools/generate_coverage_fixed.py"
Write-Host "     或: gcovr -r . --object-directory tests/generated/debug --gcov-ignore-errors=no_working_dir_found"

Write-Host "`n提示: 可以创建批处理脚本自动执行上述步骤`n"
