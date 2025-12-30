$root = 'C:\\Users\\lenovo\\Desktop\\Diagramscene_ultima-main'
$obj = 'C:\\Users\\lenovo\\Desktop\\Diagramscene_ultima-main\\tests\\build\\Desktop_Qt_6_10_1_MinGW_64_bit-Debug\\debug'
$gcov = 'D:\\Qt\\Tools\\mingw1310_64\\bin\\gcov.exe'
$names = @('diagramitem.cpp','diagrampath.cpp','diagramscene.cpp','mainwindow.cpp','arrow.cpp')
foreach ($n in $names) {
    $f = Get-ChildItem -Path $root -Recurse -Filter $n -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($f) {
        Write-Host "Running gcov for $($f.FullName)"
        & $gcov -v -o $obj $f.FullName
    } else {
        Write-Warning "Not found: $n"
    }
}
