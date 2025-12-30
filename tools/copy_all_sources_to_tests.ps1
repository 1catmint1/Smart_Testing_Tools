$root = 'C:\\Users\\lenovo\\Desktop\\Diagramscene_ultima-main'
$dest = Join-Path $root 'tests'
New-Item -Path $dest -ItemType Directory -Force | Out-Null
Get-ChildItem -Path $root -Recurse -Include *.cpp,*.c,*.h,*.hpp -File | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $dest -Force
    Write-Host "Copied $($_.Name)"
}
