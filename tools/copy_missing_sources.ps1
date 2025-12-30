$root = 'C:\Users\lenovo\Desktop\Diagramscene_ultima-main'
$dest = Join-Path $root 'tests'
New-Item -Path $dest -ItemType Directory -Force | Out-Null
foreach ($fname in @('diagramitem.cpp','diagramitem.h','arrow.h')) {
    $src = Join-Path $root $fname
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dest -Force
        Write-Host "Copied $src -> $dest"
    } else {
        Write-Warning "$src not found"
    }
}
