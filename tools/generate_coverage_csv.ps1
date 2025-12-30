param(
    [string]$ProjectRoot = 'C:\Users\lenovo\Desktop\Diagramscene_ultima-main',
    [string]$ObjectDir = 'C:\Users\lenovo\Desktop\Diagramscene_ultima-main\tests\build\Desktop_Qt_6_10_1_MinGW_64_bit-Debug\debug',
    [string]$Gcov = 'D:/Qt/Tools/mingw1310_64/bin/gcov.exe',
    [string]$OutDir = 'C:\Users\lenovo\Desktop\Smart_Testing_Tools-syz\reports\stage_reports\Diagramscene_ultima-main\20251223_133932'
)
Set-Location $ProjectRoot
$env:PATH = 'D:\Qt\Tools\mingw1310_64\bin;D:\Qt\6.10.1\mingw_64\bin;' + $env:PATH
New-Item -Path $OutDir -ItemType Directory -Force | Out-Null
$csv = Join-Path $OutDir 'coverage.csv'
$json = Join-Path $OutDir 'coverage.json'
$summary = Join-Path $OutDir 'coverage_summary.json'
Write-Host "Generating CSV-> $csv and JSON-> $json (object-dir: $ObjectDir)"
try {
    python -m gcovr -r "$ProjectRoot" --object-directory "$ObjectDir" --gcov-executable "$Gcov" --gcov-ignore-errors=no_working_dir_found -j 1 --csv "$csv" --json "$json" --json-summary "$summary" --print-summary
    Write-Host "gcovr finished, return: $LASTEXITCODE"
} catch {
    Write-Error "gcovr failed: $_"
    exit 1
}
