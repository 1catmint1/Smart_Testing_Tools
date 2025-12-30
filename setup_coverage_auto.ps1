param(
    [string]$ProjectRoot = (Read-Host "Enter project path")
)

if (-not (Test-Path $ProjectRoot -PathType Container)) {
    Write-Host "ERROR: Project directory not found: $ProjectRoot" -ForegroundColor Red
    exit 1
}

Write-Host "Detecting project build output directory..." -ForegroundColor Cyan

$PythonPath = "D:\Anaconda\envs\py312_env\python.exe"
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$AutoDetectScript = Join-Path $ScriptPath "auto_detect_coverage_cmd.py"

$CoverageCmd = & $PythonPath $AutoDetectScript $ProjectRoot --print-only

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Coverage command generated:" -ForegroundColor Green
    Write-Host ""
    Write-Host $CoverageCmd -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Steps:" -ForegroundColor Green
    Write-Host "1. Copy the command above"
    Write-Host "2. Go to Smart_Testing_Tools > Automation tab"
    Write-Host "3. Paste into Coverage Command field"
    Write-Host "4. Click Save"
} else {
    Write-Host "ERROR: Failed to generate coverage command" -ForegroundColor Red
    exit 1
}
