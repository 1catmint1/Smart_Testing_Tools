$orig = $env:PATH
$roots = @('C:\Qt','D:\Qt')
$success = $false
$outFile = Join-Path $PSScriptRoot 'try_main_output.txt'
if (Test-Path $outFile) { Remove-Item $outFile -Force }
foreach ($r in $roots) {
    if (Test-Path $r) {
        Get-ChildItem $r -Directory | ForEach-Object {
            $bin = Join-Path $_.FullName 'bin'
            if (Test-Path $bin) {
                Write-Host "--- Trying Qt bin: $bin"
                $env:PATH = $bin + ';' + $orig
                python.exe main.py 2>&1 | Tee-Object -FilePath $outFile -Append
                $exit = $LASTEXITCODE
                Write-Host "ExitCode=$exit"
                if ($exit -eq 0) { $success = $true; exit 0 }
            }
        }
    }
}
if (-not $success) { Write-Host "All attempts failed"; exit 1 }
