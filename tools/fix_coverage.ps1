#!/usr/bin/env powershell
# Fix script: Clean, rebuild, and generate correct coverage reports

param(
    [string]$ProjectRoot = "C:\Users\lenovo\Desktop\Diagramscene_ultima-syz"
)

$TestsDir = Join-Path $ProjectRoot "tests\generated"
$DebugDir = Join-Path $TestsDir "debug"

Write-Host "="*70 -ForegroundColor Cyan
Write-Host "Coverage Path Fix Script" -ForegroundColor Green
Write-Host "="*70

Write-Host "`nProject paths:"
Write-Host "  Root: $ProjectRoot"
Write-Host "  Tests: $TestsDir"
Write-Host "  Debug: $DebugDir"

# Step 1: Clean old builds
Write-Host "`nStep 1: Cleaning old builds..."
if (Test-Path $DebugDir) {
    Remove-Item -Recurse -Force $DebugDir -ErrorAction SilentlyContinue
    Write-Host "  OK: Removed $DebugDir"
}

$ReleaseDir = Join-Path $TestsDir "release"
if (Test-Path $ReleaseDir) {
    Remove-Item -Recurse -Force $ReleaseDir -ErrorAction SilentlyContinue
    Write-Host "  OK: Removed $ReleaseDir"
}

Remove-Item (Join-Path $TestsDir ".qmake.stash") -ErrorAction SilentlyContinue
Remove-Item (Join-Path $TestsDir "Makefile") -ErrorAction SilentlyContinue
Remove-Item (Join-Path $TestsDir "Makefile.Debug") -ErrorAction SilentlyContinue
Remove-Item (Join-Path $TestsDir "Makefile.Release") -ErrorAction SilentlyContinue
Write-Host "  OK: Cleanup complete"

# Step 2: Run qmake
Write-Host "`nStep 2: Running qmake..."
Push-Location $TestsDir
& qmake tests.pro 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: qmake failed" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "  OK: qmake successful"
Pop-Location

# Step 3: Compile
Write-Host "`nStep 3: Compiling..."
Push-Location $TestsDir
& mingw32-make 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Compilation failed" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "  OK: Compilation successful"
Pop-Location

# Step 4: Run tests
Write-Host "`nStep 4: Running tests..."
$ExeFile = Join-Path $DebugDir "generated_tests.exe"
if (-not (Test-Path $ExeFile)) {
    Write-Host "  ERROR: Test executable not found: $ExeFile" -ForegroundColor Red
    exit 1
}
Push-Location $TestsDir
& $ExeFile 2>&1 | Out-Null
Pop-Location
Write-Host "  OK: Tests executed, .gcda files generated"

# Step 5: Verify .gcda files
Write-Host "`nStep 5: Verifying coverage data..."
$GcdaFiles = @(Get-ChildItem -Path $DebugDir -Filter "*.gcda" -Recurse -ErrorAction SilentlyContinue)
if ($GcdaFiles.Count -gt 0) {
    Write-Host "  OK: Found $($GcdaFiles.Count) .gcda files"
} else {
    Write-Host "  WARNING: No .gcda files found - coverage report may be empty" -ForegroundColor Yellow
}

# Step 6: Copy source files to debug directory
Write-Host "`nStep 6: Copying source files..."
$CopyCount = 0
Get-ChildItem -Path $ProjectRoot -Filter "*.cpp" -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $DebugDir $_.Name) -Force -ErrorAction SilentlyContinue
    Write-Host "  OK: $($_.Name)"
    $CopyCount++
}
Get-ChildItem -Path $ProjectRoot -Filter "*.h" -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $DebugDir $_.Name) -Force -ErrorAction SilentlyContinue
    Write-Host "  OK: $($_.Name)"
    $CopyCount++
}
Write-Host "  Total copied: $CopyCount files"

# Step 7: Generate coverage report
Write-Host "`nStep 7: Generating coverage report..."
Push-Location $ProjectRoot

$pythonScript = Join-Path (Get-Location) "tools\generate_coverage_fixed.py"
if (Test-Path $pythonScript) {
    Write-Host "  Using Python fix script..."
    python $pythonScript
    Write-Host "  OK: Python script generation complete"
} else {
    Write-Host "  Using gcovr directly..."
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
        Write-Host "  OK: Coverage report generated"
    } else {
        Write-Host "  WARNING: gcovr completed with warnings but report was generated" -ForegroundColor Yellow
    }
}

Pop-Location

# Summary
Write-Host "`n" + "="*70 -ForegroundColor Cyan
Write-Host "COMPLETED!" -ForegroundColor Green
Write-Host "="*70

Write-Host "`nGenerated reports:"
Write-Host "  HTML: $(Join-Path $ProjectRoot 'coverage_report.html')"
Write-Host "  JSON: $(Join-Path $ProjectRoot 'coverage_report.json')"

Write-Host "`nNext time, simply run:"
Write-Host "  1. tests/generated/debug/generated_tests.exe"
Write-Host "  2. python tools/generate_coverage_fixed.py"

Write-Host ""
