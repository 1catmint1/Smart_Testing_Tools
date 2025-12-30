param(
    [string]$ProjectRoot = 'C:\Users\lenovo\Desktop\Diagramscene_ultima-main',
    [string]$GeneratedDir = '',
    [switch]$CopyOnly
)
if (-not $GeneratedDir -or $GeneratedDir -eq '') { Write-Error 'Please pass -GeneratedDir pointing to generated tests folder'; exit 1 }
Write-Host "Copying generated tests from $GeneratedDir into $ProjectRoot\tests"
$dest = Join-Path $ProjectRoot 'tests'
Get-ChildItem -Path $GeneratedDir -Filter *.cpp -File | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination (Join-Path $dest $_.Name) -Force
    Write-Host "Copied $_.Name -> $dest"
}
if (-not $CopyOnly) {
    Write-Host 'Running qmake && mingw32-make to pick up new tests'
    & 'D:\Qt\6.10.1\mingw_64\bin\qmake.exe' CONFIG+=coverage CONFIG+=debug
    & mingw32-make -j4
    Write-Host 'Build finished'
}
Write-Host 'Done.'
