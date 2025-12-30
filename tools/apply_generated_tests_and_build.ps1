Param(
    [string]$ProjectRoot = "C:\Users\lenovo\Desktop\Diagramscene_ultima-main",
    [string]$ReportGeneratedTests = "reports\stage_reports\Diagramscene_ultima-main\20251223_133932\generated_tests"
)

Write-Host "Applying generated tests from: $ReportGeneratedTests"

if (-not (Test-Path $ReportGeneratedTests)) {
    Write-Error "Generated tests folder not found: $ReportGeneratedTests"
    exit 1
}

$destTests = Join-Path $ProjectRoot "tests"
if (-not (Test-Path $destTests)) {
    Write-Host "Creating tests directory: $destTests"
    New-Item -ItemType Directory -Path $destTests | Out-Null
}

Get-ChildItem -Path $ReportGeneratedTests -Filter "test_*_generated.cpp" -File | ForEach-Object {
    $src = $_.FullName
    $dest = Join-Path $destTests $_.Name
    Copy-Item -Path $src -Destination $dest -Force
    Write-Host "Copied $($_.Name) -> $dest"
}

# If we have the one-click coverage script in tools, run it to rebuild/run/collect coverage.
$oneClick = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Definition) "one_click_coverage.ps1"
if (Test-Path $oneClick) {
    Write-Host "Running one-click coverage script: $oneClick"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $oneClick
} else {
    Write-Host "one_click_coverage.ps1 not found in tools; copy completed. Please build and run coverage in $ProjectRoot manually."
}

Write-Host "Done."
