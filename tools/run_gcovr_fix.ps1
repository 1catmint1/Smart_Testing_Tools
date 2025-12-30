$env:PATH = 'D:\Qt\Tools\mingw1310_64\bin;D:\Qt\6.10.1\mingw_64\bin;' + $env:PATH
$project = 'C:\Users\lenovo\Desktop\Diagramscene_ultima-main'
$objdir = Join-Path $project 'tests\build\Desktop_Qt_6_10_1_MinGW_64_bit-Debug\debug'
Push-Location $project
Write-Host "Running gcovr with gcov in PATH and object-dir: $objdir"
python -m gcovr -r . --object-directory $objdir --gcov-executable 'D:\\Qt\\Tools\\mingw1310_64\\bin\\gcov.exe' --gcov-ignore-errors=no_working_dir_found --print-summary --html-details -o coverage.html
$rc = $LASTEXITCODE
Pop-Location
Write-Host "gcovr exit code: $rc"