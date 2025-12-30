$qtBin = 'D:\\Qt\\Tools\\mingw1310_64\\bin'
$env:PATH = "$qtBin;$env:PATH"
Write-Host "Prepended Qt bin: $qtBin to PATH"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDir 'run_tests_and_coverage.ps1') -ProjectRoot 'C:\\Users\\lenovo\\Desktop\\Diagramscene_ultima-main' -ObjectDir 'C:\\Users\\lenovo\\Desktop\\Diagramscene_ultima-main\\tests\\build\\Desktop_Qt_6_10_1_MinGW_64_bit-Debug\\debug'
