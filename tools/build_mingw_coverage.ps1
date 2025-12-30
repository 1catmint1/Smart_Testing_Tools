$qtQmake = 'D:\\Qt\\6.10.1\\mingw_64\\bin\\qmake.exe'
$qtBin = 'D:\\Qt\\Tools\\mingw1310_64\\bin'
$env:PATH = "$qtBin;$env:PATH"
Write-Host "Using qmake: $qtQmake"

$proj = 'C:\\Users\\lenovo\\Desktop\\Diagramscene_ultima-main'
Push-Location $proj
try {
    Write-Host "Running: $qtQmake CONFIG+=coverage"
    & $qtQmake CONFIG+=coverage
    Write-Host "Running: mingw32-make clean"
    & mingw32-make clean
    Write-Host "Running: mingw32-make -j4"
    & mingw32-make -j4
} finally {
    Pop-Location
}

Write-Host "Mingw coverage build finished."
