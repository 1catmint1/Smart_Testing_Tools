$qtQmake = 'D:\\Qt\\6.10.1\\mingw_64\\bin\\qmake.exe'
$qtBin = 'D:\\Qt\\Tools\\mingw1310_64\\bin'
$env:PATH = "$qtBin;$env:PATH"

$testsDir = 'c:\Users\lenovo\Desktop\Diagramscene_ultima-syz\tests\generated'
$debugDir = Join-Path $testsDir 'debug'
$projectRoot = 'c:\Users\lenovo\Desktop\Diagramscene_ultima-syz'

Write-Host "Coverage Generation Pipeline"
Write-Host "=============================="

# Step 1: Wait for exe
Write-Host "`nWaiting for executable..."
$exe = Join-Path $debugDir 'generated_tests.exe'
$timeout = 120
$elapsed = 0
while (-not (Test-Path $exe) -and $elapsed -lt $timeout) {
    Start-Sleep -Seconds 2
    $elapsed += 2
    Write-Host "  Waiting... ($elapsed s)"
}

if (-not (Test-Path $exe)) {
    Write-Host "ERROR: Executable not found after $timeout seconds"
    exit 1
}
Write-Host "  OK: Executable ready"

# Step 2: Run tests
Write-Host "`nRunning tests..."
Push-Location $testsDir
& $exe 2>&1 | Out-Null
Pop-Location
Write-Host "  OK: Tests completed"

# Step 3: Check .gcda files
Write-Host "`nChecking coverage data..."
$gcda = Get-ChildItem -Path $debugDir -Filter "*.gcda" -Recurse -ErrorAction SilentlyContinue
if ($gcda.Count -gt 0) {
    Write-Host "  OK: Found $($gcda.Count) .gcda files"
} else {
    Write-Host "  WARNING: No .gcda files found"
}

# Step 4: Copy sources
Write-Host "`nCopying source files..."
Get-ChildItem -Path $projectRoot -Filter "*.cpp" -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $debugDir $_.Name) -Force -ErrorAction SilentlyContinue
}
Get-ChildItem -Path $projectRoot -Filter "*.h" -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $debugDir $_.Name) -Force -ErrorAction SilentlyContinue
}
Write-Host "  OK: Source files copied"

# Step 5: Generate report
Write-Host "`nGenerating coverage report..."
Push-Location $projectRoot
python -m gcovr -r . `
    --object-directory "$debugDir" `
    --exclude-directories .git `
    --exclude-directories .venv `
    --exclude-directories tools `
    --print-summary `
    --html-details -o coverage_report.html `
    --json=coverage_report.json `
    --gcov-ignore-errors=no_working_dir_found 2>&1 | Select-Object -Last 10
Pop-Location

Write-Host "`nDone!"
Write-Host "Reports: $projectRoot\coverage_report.html"
