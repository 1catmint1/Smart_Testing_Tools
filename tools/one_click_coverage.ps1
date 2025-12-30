# One-click coverage: build (MinGW+coverage), run tests, run gcovr, archive reports
param(
    [string]$ProjectRoot = 'C:\Users\lenovo\Desktop\Diagramscene_ultima-main',
    [string]$QtQmake = 'D:\Qt\6.10.1\mingw_64\bin\qmake.exe',
    [string]$Gcov = 'D:\Qt\Tools\mingw1310_64\bin\gcov.exe',
    [int]$MakeJobs = 4
)
$ErrorActionPreference = 'Stop'
Write-Host "Project root: $ProjectRoot"
Set-Location $ProjectRoot
# Prepend Qt + MinGW bins
$bins = @('D:\Qt\6.10.1\mingw_64\bin','D:\Qt\Tools\mingw1310_64\bin')
$env:PATH = ($bins -join ';') + ';' + $env:PATH
Write-Host "Prepended bins to PATH"
# Run qmake with coverage/debug config
Write-Host "Running qmake (CONFIG+=coverage CONFIG+=debug)"
& $QtQmake CONFIG+=coverage CONFIG+=debug
# Build
Write-Host "Running mingw32-make -j$MakeJobs"
& mingw32-make -j$MakeJobs
# Detect object directory
$cand = Get-ChildItem -Path (Join-Path $ProjectRoot 'tests\build') -Directory -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match '[\\/](Debug|debug)[\\/]' } | Select-Object -First 1
if ($cand) { $objdir = $cand.FullName } else { Write-Error 'Cannot detect object dir under tests/build'; exit 1 }
Write-Host "Object directory: $objdir"
# Run tests
$tests = Get-ChildItem -Path $objdir -Recurse -Filter *.exe -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'test|Test|tests|unittest' } | Select-Object -Unique
foreach ($t in $tests) {
    Write-Host "Running: $($t.FullName)"
    & "$($t.FullName)"
    Write-Host "Exit code: $LASTEXITCODE"
}
# Ensure gcov-referenced sources exist (copy missing files into expected relative paths)
$ensureScript = Join-Path $PSScriptRoot 'ensure_gcov_sources.ps1'
if (Test-Path $ensureScript) {
    Write-Host "Running ensure_gcov_sources to prepare source mapping"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $ensureScript -ProjectRoot $ProjectRoot -ObjDir $objdir -GcovExe $Gcov
} else {
    Write-Warning "ensure_gcov_sources.ps1 not found; skipping mapping step"
}

# Run gcovr (html + csv + json + summary) and save into project root
$gcovrCmd = "python -m gcovr -r . --object-directory `"$objdir`" --gcov-executable `"$Gcov`" --html-details -o coverage.html --csv coverage.csv --json coverage.json --json-summary coverage_summary.json --print-summary"
Write-Host "Running gcovr..."
Invoke-Expression $gcovrCmd
# Archive outputs to reports/stage_reports/<projectname>/<timestamp>/
$timestamp = Get-Date -Format yyyyMMdd_HHmmss
$projName = Split-Path $ProjectRoot -Leaf
$dest = Join-Path (Join-Path "$PSScriptRoot\..\reports\stage_reports\$projName" ) $timestamp
New-Item -Path $dest -ItemType Directory -Force | Out-Null
Get-ChildItem -Path $ProjectRoot -Include coverage.html,coverage.csv,coverage.json,coverage_summary.json -File -ErrorAction SilentlyContinue | ForEach-Object { Copy-Item -Path $_.FullName -Destination (Join-Path $dest $_.Name) -Force }
Write-Host "Reports archived to: $dest"
# Run analyzer to list top uncovered and generate test skeletons
$analyzer = Join-Path $PSScriptRoot 'analyze_and_generate.py'
if (Test-Path $analyzer) {
    Write-Host "Running coverage analyzer and generator"
    python $analyzer -c (Join-Path $dest 'coverage.csv') -o (Join-Path $dest 'generated_tests') -n 10
    Write-Host "Analyzer finished; generated tests (templates) in: " (Join-Path $dest 'generated_tests')
} else {
    Write-Warning "Analyzer script not found: $analyzer"
}
Write-Host "One-click coverage finished."