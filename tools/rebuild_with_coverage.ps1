$qtBin = 'D:\\Qt\\Tools\\mingw1310_64\\bin'
$env:PATH = "$qtBin;$env:PATH"
Write-Host "Prepended Qt bin: $qtBin to PATH"

$proj = 'C:\\Users\\lenovo\\Desktop\\Diagramscene_ultima-main'
Push-Location $proj
try {
    Write-Host "Running qmake CONFIG+=coverage in $proj"
    & qmake CONFIG+=coverage
    Write-Host "Running mingw32-make clean"
    & mingw32-make clean
    Write-Host "Running mingw32-make -j4"
    & mingw32-make -j4
} finally {
    Pop-Location
}

Write-Host "Build script finished."
