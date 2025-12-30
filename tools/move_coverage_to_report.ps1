$src = 'C:\Users\lenovo\Desktop\Diagramscene_ultima-main\coverage.html'
$destDir = 'C:\Users\lenovo\Desktop\Smart_Testing_Tools-syz\reports\stage_reports\Diagramscene_ultima-main\20251223_133932'
if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
if (Test-Path $src) {
    Copy-Item -Path $src -Destination (Join-Path $destDir 'coverage.html') -Force
    Write-Host "Copied coverage.html to $destDir"
    Remove-Item $src -Force
    Write-Host "Removed original coverage.html"
} else {
    Write-Host "Source coverage.html not found: $src"
}
