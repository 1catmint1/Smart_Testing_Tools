```powershell
$qtBins = @('D:\Qt\6.10.1\mingw_64\bin', 'D:\Qt\Tools\mingw1310_64\bin')
$env:PATH = ($qtBins -join ';') + ';' + $env:PATH
Write-Host "Prepended bins: $($qtBins -join ';') to PATH"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDir 'run_tests_and_coverage.ps1') -ProjectRoot 'C:\Users\lenovo\Desktop\Diagramscene_ultima-main' -ObjectDir 'C:\Users\lenovo\Desktop\Diagramscene_ultima-main\tests\build\Desktop_Qt_6_10_1_MinGW_64_bit-Debug\debug'

```