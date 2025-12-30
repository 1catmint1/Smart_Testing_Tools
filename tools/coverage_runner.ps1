<# 
.SYNOPSIS
    智能覆盖率运行器 - 确保正确生成 gcda 文件并收集覆盖率数据
.DESCRIPTION
    此脚本解决了覆盖率为 0% 的常见问题：
    1. DLL 依赖问题 - 自动部署 Qt DLL
    2. 程序关闭方式 - 优雅关闭以触发 gcov atexit
    3. gcda 文件位置 - 确保在正确位置生成
    4. 编译配置 - 检查并自动添加覆盖率标志
.PARAMETER ProjectRoot
    被测项目根目录
.PARAMETER ExePath
    可执行文件路径（可选，自动检测）
.PARAMETER QtBinPath
    Qt bin 目录路径
.PARAMETER MinGWPath
    MinGW 工具链路径
.PARAMETER RunDuration
    程序运行时长（秒），默认 5 秒
.PARAMETER SkipBuild
    跳过编译步骤
.PARAMETER SkipRun
    跳过运行程序步骤（仅运行 gcovr）
#>

Param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectRoot,
    
    [string]$ExePath = '',
    [string]$QtBinPath = 'D:\Qt\6.10.1\mingw_64\bin',
    [string]$MinGWPath = 'D:\Qt\Tools\mingw1310_64\bin',
    [int]$RunDuration = 5,
    [switch]$SkipBuild,
    [switch]$SkipRun
)

$ErrorActionPreference = 'Continue'
$script:exitCode = 0

# ============================================================
# Helper Functions
# ============================================================

function Write-Step {
    param([string]$Message)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[✓] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[!] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[✗] $Message" -ForegroundColor Red
    $script:exitCode = 1
}

function Find-QtProject {
    param([string]$Root)
    
    # 查找 .pro 文件
    $proFile = Get-ChildItem -Path $Root -Filter "*.pro" -File -ErrorAction SilentlyContinue | 
               Where-Object { $_.Name -notmatch 'test' } | 
               Select-Object -First 1
    
    if ($proFile) {
        return @{
            Type = 'qmake'
            File = $proFile.FullName
            Name = $proFile.BaseName
        }
    }
    
    # 查找 CMakeLists.txt
    $cmakeFile = Join-Path $Root 'CMakeLists.txt'
    if (Test-Path $cmakeFile) {
        return @{
            Type = 'cmake'
            File = $cmakeFile
            Name = (Split-Path $Root -Leaf)
        }
    }
    
    return $null
}

function Find-Executable {
    param([string]$Root, [string]$ProjectName)
    
    $searchPaths = @(
        "$Root\debug",
        "$Root\build\debug",
        "$Root\build\*Debug*\debug",
        "$Root\release",
        "$Root\build\release"
    )
    
    foreach ($pattern in $searchPaths) {
        $exes = Get-ChildItem -Path $pattern -Filter "*.exe" -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -notmatch 'test|moc|qrc|uic' }
        if ($exes) {
            return $exes | Select-Object -First 1
        }
    }
    
    return $null
}

function Test-CoverageFlags {
    param([string]$ProFile)
    
    $content = Get-Content $ProFile -Raw -ErrorAction SilentlyContinue
    if ($content -match 'fprofile-arcs|ftest-coverage|--coverage') {
        return $true
    }
    return $false
}

function Add-CoverageFlags {
    param([string]$ProFile)
    
    $content = Get-Content $ProFile -Raw
    
    # 检查是否已有覆盖率标志
    if ($content -match 'coverage flags') {
        Write-Host "覆盖率标志已存在于 .pro 文件中"
        return
    }
    
    # 添加覆盖率标志
    $coverageBlock = @"

# --- coverage flags (auto-added by Smart Testing Tools) ---
QMAKE_CFLAGS += -fprofile-arcs -ftest-coverage
QMAKE_CXXFLAGS += -fprofile-arcs -ftest-coverage
QMAKE_LFLAGS += --coverage
# --- end coverage flags ---
"@
    
    $newContent = $content + $coverageBlock
    Set-Content -Path $ProFile -Value $newContent -Encoding UTF8
    Write-Success "已添加覆盖率编译标志到 $ProFile"
}

function Deploy-QtDlls {
    param(
        [string]$ExePath,
        [string]$QtBin
    )
    
    $exeDir = Split-Path $ExePath -Parent
    $windeployqt = Join-Path $QtBin 'windeployqt.exe'
    
    if (-not (Test-Path $windeployqt)) {
        Write-Warning "windeployqt.exe 未找到: $windeployqt"
        return $false
    }
    
    Write-Host "运行 windeployqt 部署 DLL..."
    & $windeployqt --no-translations $ExePath 2>&1 | Out-Null
    
    # 验证关键 DLL
    $requiredDlls = @('Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll')
    $missing = @()
    foreach ($dll in $requiredDlls) {
        if (-not (Test-Path (Join-Path $exeDir $dll))) {
            $missing += $dll
        }
    }
    
    if ($missing.Count -gt 0) {
        Write-Warning "缺少 DLL: $($missing -join ', ')"
        return $false
    }
    
    Write-Success "Qt DLL 部署完成"
    return $true
}

function Clear-GcdaFiles {
    param([string]$Root)
    
    $gcdaFiles = Get-ChildItem -Path $Root -Filter "*.gcda" -Recurse -ErrorAction SilentlyContinue
    if ($gcdaFiles) {
        Write-Host "清理 $($gcdaFiles.Count) 个旧的 .gcda 文件..."
        $gcdaFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

function Start-ProgramGracefully {
    param(
        [string]$ExePath,
        [string]$WorkDir,
        [int]$Duration
    )
    
    # 定义 Win32 API
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class Win32Graceful {
    [DllImport("user32.dll", SetLastError=true)]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    [DllImport("user32.dll", SetLastError=true)]
    public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
    public const uint WM_CLOSE = 0x0010;
}
"@ -Language CSharp -ErrorAction SilentlyContinue
    
    Write-Host "启动程序: $ExePath"
    $proc = Start-Process -FilePath $ExePath -WorkingDirectory $WorkDir -PassThru
    
    if (-not $proc) {
        Write-Error "无法启动程序"
        return $false
    }
    
    Write-Host "程序 PID: $($proc.Id)，等待 $Duration 秒..."
    Start-Sleep -Seconds $Duration
    
    # 尝试优雅关闭
    Write-Host "发送关闭信号..."
    
    # 方法1: 使用 CloseMainWindow
    $proc.Refresh()
    if ($proc.MainWindowHandle -ne [IntPtr]::Zero) {
        try {
            [Win32Graceful]::PostMessage($proc.MainWindowHandle, [Win32Graceful]::WM_CLOSE, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null
            Write-Host "已发送 WM_CLOSE 消息"
        } catch {
            $proc.CloseMainWindow() | Out-Null
            Write-Host "已调用 CloseMainWindow()"
        }
    } else {
        $proc.CloseMainWindow() | Out-Null
        Write-Host "已调用 CloseMainWindow()"
    }
    
    # 等待程序退出
    $exited = $proc.WaitForExit(10000)
    
    if (-not $exited) {
        Write-Warning "程序未在 10 秒内退出，尝试强制关闭..."
        # 最后手段：强制关闭，但这可能导致 gcda 不写入
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    } else {
        Write-Success "程序正常退出，退出码: $($proc.ExitCode)"
    }
    
    return $true
}

function Build-WithCoverage {
    param(
        [hashtable]$Project,
        [string]$QtBin,
        [string]$MinGW
    )
    
    $projDir = Split-Path $Project.File -Parent
    
    # 设置环境变量
    $env:PATH = "$QtBin;$MinGW;$env:PATH"
    
    Push-Location $projDir
    try {
        if ($Project.Type -eq 'qmake') {
            Write-Host "运行 qmake..."
            $qmakeExe = Join-Path $QtBin 'qmake.exe'
            & $qmakeExe $Project.File "CONFIG+=debug" "QMAKE_CXXFLAGS+=-fprofile-arcs -ftest-coverage -O0" "QMAKE_LFLAGS+=--coverage" 2>&1 | ForEach-Object { Write-Host $_ }
            
            Write-Host "运行 mingw32-make clean..."
            $makeExe = Join-Path $MinGW 'mingw32-make.exe'
            & $makeExe clean 2>&1 | Out-Null
            
            Write-Host "运行 mingw32-make..."
            & $makeExe -j4 2>&1 | ForEach-Object { Write-Host $_ }
            
            if ($LASTEXITCODE -eq 0) {
                Write-Success "编译成功"
                return $true
            }
        }
    } finally {
        Pop-Location
    }
    
    Write-Error "编译失败"
    return $false
}

function Run-Gcovr {
    param(
        [string]$ProjectRoot,
        [string]$ObjectDir,
        [string]$GcovExe
    )
    
    Write-Host "运行 gcovr..."
    
    $gcovr = "python -m gcovr"
    $args = @(
        "-r `"$ProjectRoot`"",
        "--object-directory `"$ObjectDir`"",
        "--gcov-executable `"$GcovExe`"",
        "--exclude-directories .git",
        "--exclude-directories .venv",
        "--exclude-directories build",
        "--exclude-directories tests",
        "--print-summary",
        "--html-details -o `"$ProjectRoot\coverage.html`"",
        "--json=`"$ProjectRoot\coverage.json`""
    )
    
    $cmd = "$gcovr " + ($args -join " ")
    Write-Host "命令: $cmd"
    
    $result = Invoke-Expression $cmd 2>&1
    $result | ForEach-Object { Write-Host $_ }
    
    # 解析覆盖率
    $linesMatch = $result | Select-String -Pattern 'lines:\s*(\d+\.?\d*%)'
    if ($linesMatch) {
        Write-Success "行覆盖率: $($linesMatch.Matches[0].Groups[1].Value)"
    }
    
    return ($LASTEXITCODE -eq 0)
}

# ============================================================
# Main Execution
# ============================================================

Write-Step "智能覆盖率运行器"
Write-Host "项目根目录: $ProjectRoot"
Write-Host "Qt 路径: $QtBinPath"
Write-Host "MinGW 路径: $MinGWPath"

# 验证项目根目录
if (-not (Test-Path $ProjectRoot)) {
    Write-Error "项目根目录不存在: $ProjectRoot"
    exit 1
}

# 设置 PATH
$env:PATH = "$QtBinPath;$MinGWPath;$env:PATH"

# Step 1: 查找项目类型
Write-Step "1. 检测项目类型"
$project = Find-QtProject -Root $ProjectRoot
if (-not $project) {
    Write-Error "未找到 Qt 项目文件 (.pro 或 CMakeLists.txt)"
    exit 1
}
Write-Success "检测到 $($project.Type) 项目: $($project.Name)"

# Step 2: 检查/添加覆盖率标志
Write-Step "2. 检查覆盖率编译标志"
if ($project.Type -eq 'qmake') {
    if (-not (Test-CoverageFlags -ProFile $project.File)) {
        Write-Warning "未检测到覆盖率标志，正在添加..."
        Add-CoverageFlags -ProFile $project.File
    } else {
        Write-Success "覆盖率标志已配置"
    }
}

# Step 3: 编译项目
if (-not $SkipBuild) {
    Write-Step "3. 编译项目（带覆盖率）"
    $buildOk = Build-WithCoverage -Project $project -QtBin $QtBinPath -MinGW $MinGWPath
    if (-not $buildOk) {
        Write-Error "编译失败"
        exit 1
    }
}

# Step 4: 查找可执行文件
Write-Step "4. 查找可执行文件"
if ($ExePath -and (Test-Path $ExePath)) {
    $exeFile = Get-Item $ExePath
} else {
    $exeFile = Find-Executable -Root $ProjectRoot -ProjectName $project.Name
}

if (-not $exeFile) {
    Write-Error "未找到可执行文件"
    exit 1
}
Write-Success "找到可执行文件: $($exeFile.FullName)"

$objectDir = Split-Path $exeFile.FullName -Parent

# Step 5: 部署 DLL
Write-Step "5. 部署 Qt DLL"
$dllOk = Deploy-QtDlls -ExePath $exeFile.FullName -QtBin $QtBinPath
if (-not $dllOk) {
    Write-Warning "DLL 部署可能不完整，程序可能无法启动"
}

# Step 6: 清理旧的 gcda 文件
Write-Step "6. 清理旧的覆盖率数据"
Clear-GcdaFiles -Root $ProjectRoot

# Step 7: 运行程序
if (-not $SkipRun) {
    Write-Step "7. 运行程序并生成覆盖率数据"
    $runOk = Start-ProgramGracefully -ExePath $exeFile.FullName -WorkDir $objectDir -Duration $RunDuration
    
    Start-Sleep -Seconds 1
    
    # 检查 gcda 文件
    $gcdaFiles = Get-ChildItem -Path $ProjectRoot -Filter "*.gcda" -Recurse -ErrorAction SilentlyContinue
    if ($gcdaFiles) {
        Write-Success "生成了 $($gcdaFiles.Count) 个 .gcda 文件"
    } else {
        Write-Error "未生成 .gcda 文件！可能是程序未正常退出或未启用覆盖率编译"
    }
}

# Step 8: 运行 gcovr
Write-Step "8. 收集覆盖率数据"
$gcovExe = Join-Path $MinGWPath 'gcov.exe'
$gcovrOk = Run-Gcovr -ProjectRoot $ProjectRoot -ObjectDir $objectDir -GcovExe $gcovExe

Write-Step "完成"
if ($script:exitCode -eq 0) {
    Write-Success "覆盖率收集完成！"
    Write-Host "HTML 报告: $ProjectRoot\coverage.html"
    Write-Host "JSON 报告: $ProjectRoot\coverage.json"
} else {
    Write-Error "覆盖率收集过程中出现错误"
}

exit $script:exitCode
