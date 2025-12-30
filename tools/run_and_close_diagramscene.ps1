$ErrorActionPreference = 'Stop'
$projRoot = 'C:\Users\lenovo\Desktop\Diagramscene_ultima-syz'
$buildDebug = Join-Path $projRoot 'build-mingw\debug'
$qtBin = 'D:\Qt\6.10.1\mingw_64\bin'
$gcovExe = 'D:\Qt\Tools\mingw1310_64\bin\gcov.exe'

Write-Host "CD to $buildDebug"
Set-Location $buildDebug
$env:Path = "$qtBin;" + $env:Path
if (-not (Test-Path '.\diagramscene.exe')) { Write-Error "diagramscene.exe not found in $buildDebug"; exit 2 }

Write-Host "Starting diagramscene.exe..."
$p = Start-Process -FilePath '.\diagramscene.exe' -PassThru

# Define PostMessage/FindWindow helper class once
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class Win32User {
    [DllImport("user32.dll", SetLastError=true)]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    [DllImport("user32.dll", SetLastError=true)]
    public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
}
"@ -Language CSharp

# Wait up to 20s for main window handle
$maxWait = 20
$waited = 0
while ($waited -lt $maxWait) {
    $p.Refresh()
    if ($p.MainWindowHandle -ne 0) { break }
    Start-Sleep -Seconds 1
    $waited += 1
}

if ($p.MainWindowHandle -ne 0) {
    Write-Host "Found MainWindowHandle, posting WM_CLOSE"
    [Win32User]::PostMessage($p.MainWindowHandle,0x0010,[IntPtr]0,[IntPtr]0) | Out-Null
    # wait up to 10s for process to exit
    $p.WaitForExit(10000) | Out-Null
} else {
    Write-Host "MainWindowHandle not found, attempting CloseMainWindow"
    try { $p.CloseMainWindow() | Out-Null; Start-Sleep -Seconds 3 } catch {}
}
# If still alive, force stop
$p.Refresh()
if (-not $p.HasExited) {
    Write-Host "Process still running; forcing Stop-Process"
    Stop-Process -Id $p.Id -Force
}

Start-Sleep -Seconds 1

Write-Host "Listing all .gcda files under project root:"
Get-ChildItem -Path $projRoot -Recurse -Include *.gcda -File | Select-Object FullName, Length | Format-Table -AutoSize

Write-Host "Running ensure_gcov_sources.ps1"
& "$PSScriptRoot\ensure_gcov_sources.ps1" -ProjectRoot $projRoot -ObjDir $buildDebug -GcovExe $gcovExe

Write-Host "Running gcovr (verbose)"
$gcovrCmd = 'D:\Anaconda\envs\py312_env\python.exe -m gcovr -r "' + $projRoot + '" --object-directory "' + $buildDebug + '" --gcov-executable D:/Qt/Tools/mingw1310_64/bin/gcov.exe --exclude-directories .git --exclude-directories .venv --exclude-directories tools --exclude-directories generated_tests --print-summary --html-details --verbose -o "' + (Join-Path $projRoot 'coverage.html') + '" --json="' + (Join-Path $projRoot 'coverage.json') + '"'
Write-Host $gcovrCmd
Invoke-Expression $gcovrCmd | Tee-Object -FilePath (Join-Path $projRoot 'gcovr_run.txt')
Write-Host "Finished gcovr run, tailing gcovr_run.txt"
Get-Content (Join-Path $projRoot 'gcovr_run.txt') -Tail 200

Write-Host "Script finished."