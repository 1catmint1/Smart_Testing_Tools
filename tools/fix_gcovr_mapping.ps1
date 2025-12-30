Param(
    [string]$ProjectRoot = 'C:\Users\lenovo\Desktop\Diagramscene_ultima-main',
    [string]$ObjDir = 'C:\Users\lenovo\Desktop\Diagramscene_ultima-main\tests\build\Desktop_Qt_6_10_1_MinGW_64_bit-Debug\debug\debug',
    [int]$LevelsUp = 4
)

Write-Host "Fixing gcovr mapping by copying source files into object dir parents"
if (-not (Test-Path $ProjectRoot)) { Write-Error "ProjectRoot not found: $ProjectRoot"; exit 1 }
if (-not (Test-Path $ObjDir)) { Write-Error "ObjDir not found: $ObjDir"; exit 1 }

$srcFiles = Get-ChildItem -Path $ProjectRoot -Recurse -Include *.cpp,*.h,*.moc,*.ui -File
for ($i = 0; $i -lt $LevelsUp; $i++) {
    $targetBase = (Get-Item $ObjDir).FullName
    for ($j = 0; $j -lt $i; $j++) { $targetBase = Split-Path $targetBase -Parent }
    $destRoot = Join-Path $targetBase (Split-Path $ProjectRoot -Leaf)
    Write-Host "Copying sources to: $destRoot"
    if (-not (Test-Path $destRoot)) { New-Item -ItemType Directory -Path $destRoot -Force | Out-Null }
    foreach ($f in $srcFiles) {
        $rel = $f.FullName.Substring($ProjectRoot.Length).TrimStart('\')
        $dest = Join-Path $destRoot $rel
        $dird = Split-Path $dest -Parent
        if (-not (Test-Path $dird)) { New-Item -ItemType Directory -Path $dird -Force | Out-Null }
        Copy-Item -Path $f.FullName -Destination $dest -Force
    }
}

Write-Host "Source copy complete. Please re-run gcovr."
