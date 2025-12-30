$project = 'C:\Users\lenovo\Desktop\Diagramscene_ultima-main'
$objectDir = Join-Path $project 'tests\build\Desktop_Qt_6_10_1_MinGW_64_bit-Debug\debug'
$bins = 'D:\Qt\Tools\mingw1310_64\bin;D:\Qt\6.10.1\mingw_64\bin;'
$env:PATH = $bins + $env:PATH
Write-Host "Using object dir: $objectDir"
if (-not (Test-Path $objectDir)) { Write-Error "Object dir not found: $objectDir"; exit 1 }
$tests = Get-ChildItem -Path $objectDir -Recurse -Filter *.exe | Where-Object { $_.Name -match 'test|Test|tests|unittest' }
foreach ($t in $tests) {
    Write-Host "Running: $($t.FullName)"
    & "$($t.FullName)"
    Write-Host "Exit code: $LASTEXITCODE"
}
Write-Host "Done running tests."