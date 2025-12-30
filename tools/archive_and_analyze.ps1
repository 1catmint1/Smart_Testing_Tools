Param(
    [string]$ProjectRoot = 'C:\Users\lenovo\Desktop\Diagramscene_ultima-main'
)

Set-StrictMode -Version Latest
$timestamp = Get-Date -Format yyyyMMdd_HHmmss
$projName = Split-Path $ProjectRoot -Leaf
$dest = Join-Path (Join-Path $PSScriptRoot '..\reports\stage_reports\' ) $projName
$dest = Join-Path $dest $timestamp
New-Item -Path $dest -ItemType Directory -Force | Out-Null

$files = @('coverage.html','coverage.csv','coverage.json','coverage_summary.json')
foreach ($f in $files) {
    $src = Join-Path $ProjectRoot $f
    if (Test-Path $src) { Copy-Item -Path $src -Destination (Join-Path $dest $f) -Force; Write-Host "Copied $f" } else { Write-Host "Missing $f, skipping" }
}

Write-Host "Reports archived to: $dest"

# Run analyzer if present
$analyzer = Join-Path $PSScriptRoot 'analyze_and_generate.py'
if (Test-Path $analyzer) {
    $csv = Join-Path $dest 'coverage.csv'
    $out = Join-Path $dest 'generated_tests'
    if (Test-Path $csv) {
        Write-Host "Running analyzer: python $analyzer -c $csv -o $out -n 10"
        python $analyzer -c $csv -o $out -n 10
        Write-Host "Analyzer output in: $out"
    } else { Write-Host "CSV not found in $dest, analyzer skipped." }
} else {
    Write-Host "Analyzer not found: $analyzer"
}

Write-Host "archive_and_analyze finished."
