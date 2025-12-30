Param(
    [string]$ProjectRoot = 'C:\Users\lenovo\Desktop\Diagramscene_ultima-main',
    [string]$ObjDir = 'C:\Users\lenovo\Desktop\Diagramscene_ultima-main\tests\build\Desktop_Qt_6_10_1_MinGW_64_bit-Debug\debug\debug'
)

Set-StrictMode -Version Latest
Write-Host "Running gcovr in project: $ProjectRoot"
Set-Location $ProjectRoot

# Ensure MinGW gcov is in PATH
$bins = @('D:\Qt\Tools\mingw1310_64\bin','D:\Qt\6.10.1\mingw_64\bin')
$env:PATH = ($bins -join ';') + ';' + $env:PATH

Write-Host "Using object directory: $ObjDir"
python -m gcovr -r . --object-directory "$ObjDir" --html-details -o coverage.html --csv coverage.csv --json coverage.json --json-summary coverage_summary.json --print-summary

Write-Host "gcovr run finished."
