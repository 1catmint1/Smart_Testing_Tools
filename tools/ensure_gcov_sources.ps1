Param(
    [string]$ProjectRoot = 'C:\Users\lenovo\Desktop\Diagramscene_ultima-main',
    [string]$ObjDir = '',
    [string]$GcovExe = 'D:\Qt\Tools\mingw1310_64\bin\gcov.exe'
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path $ProjectRoot)) { Write-Error "ProjectRoot not found: $ProjectRoot"; exit 1 }
if ([string]::IsNullOrWhiteSpace($ObjDir)) {
    $cand = Get-ChildItem -Path (Join-Path $ProjectRoot 'tests\build') -Directory -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match '[\\/](Debug|debug)[\\/]' } | Select-Object -First 1
    if ($cand) { $ObjDir = $cand.FullName } else { Write-Error 'Cannot detect object dir under tests/build'; exit 1 }
}

Write-Host "Ensuring gcov-referenced sources exist for object dir: $ObjDir"

if (-not (Test-Path -Path $ObjDir -PathType Container)) {
    Write-Host "ObjDir not found: $ObjDir"
    $candidates = @(
        "$ProjectRoot\tests\build\Desktop_Qt_6_10_1_MinGW_64_bit-Debug\debug",
        "$ProjectRoot\tests\build\Desktop_Qt_6_10_1_MinGW_64_bit-Debug\debug\debug",
        "$ProjectRoot\tests\generated\debug",
        "$ProjectRoot\tests\build\debug",
        "$ProjectRoot\tests\build\Desktop_Qt_6_10_1_MinGW_64_bit-Debug"
    )
    $found = $null
    foreach ($cand in $candidates) {
        if (Test-Path -Path $cand -PathType Container) {
            Write-Host "Found candidate ObjDir: $cand"
            $found = $cand
            break
        }
    }
    if ($found) {
        $ObjDir = $found
    } else {
        Write-Host "No candidate object directories found. Searching project for any .gcda files..."
        $anyGcda = Get-ChildItem -Path $ProjectRoot -Recurse -Include *.gcda -File -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($anyGcda) {
            $gcdaDir = Split-Path $anyGcda.FullName -Parent
            Write-Host "Found .gcda under project: $($anyGcda.FullName). Using object dir: $gcdaDir"
            $ObjDir = $gcdaDir
        } else {
            Write-Host "No .gcda files found under project. Attempting to build project to generate coverage data (qmake + mingw32-make) if possible..."
            # Only attempt automatic build if a .pro file exists in project root (qmake project)
            $proFile = Get-ChildItem -Path $ProjectRoot -Recurse -Include *.pro -File -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($proFile) {
                Write-Host "Found project file: $($proFile.FullName). Running qmake + mingw32-make (may take a while)..."
                Push-Location $ProjectRoot
                try {
                    # Attempt qmake then mingw32-make. Assume qmake and mingw32-make are in PATH.
                    & qmake $proFile.FullName CONFIG+=coverage CONFIG+=debug 2>&1 | ForEach-Object { Write-Host $_ }
                    & mingw32-make clean 2>&1 | ForEach-Object { Write-Host $_ }
                    & mingw32-make -j4 2>&1 | ForEach-Object { Write-Host $_ }
                } catch {
                    Write-Warning "Automatic build failed: $($_.Exception.Message)"
                } finally {
                    Pop-Location
                }
                Write-Host "Re-scanning project for .gcda files after build..."
                $anyGcda = Get-ChildItem -Path $ProjectRoot -Recurse -Include *.gcda -File -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($anyGcda) {
                    $gcdaDir = Split-Path $anyGcda.FullName -Parent
                    Write-Host "Found .gcda after build: $($anyGcda.FullName). Using object dir: $gcdaDir"
                    $ObjDir = $gcdaDir
                } else {
                    Write-Host "Still no .gcda files found after attempted build. Exiting."
                    exit 1
                }
            } else {
                Write-Host "No .pro file found; cannot attempt automatic qmake build. Exiting."
                exit 1
            }
        }
    }
}

$gcdaFiles = Get-ChildItem -Path $ObjDir -Recurse -Include *.gcda -File -ErrorAction SilentlyContinue
if (-not $gcdaFiles) { Write-Host 'No .gcda files found; nothing to do.'; exit 0 }

$copied = 0
foreach ($g in $gcdaFiles) {
    $gdir = Split-Path $g.FullName -Parent
    Write-Host "Processing .gcda: $($g.FullName)"
    # Run gcov on the .gcda to let it print referenced File paths; capture stdout/stderr
    $args = "-o", "$gdir", "$($g.FullName)"
    # run gcov but do not let its non-zero exit abort the script; capture stdout/stderr
    $prevError = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & $GcovExe @args 2>&1
    } catch {
        $out = $_.Exception.Message
    }
    $ErrorActionPreference = $prevError
    foreach ($line in $out) {
        # match patterns like: File '../../../diagramitem.cpp' or Cannot open source file ../../../diagramitem.cpp
        if ($line -match "File '([^']+)'" -or $line -match "Cannot open source file (.+)") {
            $m = $matches[1]
            if (-not $m) { continue }
            $refPath = $m.Trim()
            # if path is absolute, just check exists; if relative, combine with gcda dir and also project root
            if ([System.IO.Path]::IsPathRooted($refPath)) {
                $expected = $refPath
            } else {
                $expected = Join-Path $gdir $refPath
            }
            $expected = [System.IO.Path]::GetFullPath($expected)
            if (Test-Path $expected) { continue }
            # try to find a source file with same file name under project root
            $base = Split-Path $refPath -Leaf
            Write-Host "Missing referenced file: $refPath -> $expected"
            $found = Get-ChildItem -Path $ProjectRoot -Recurse -Include $base -File -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($found) {
                # Only copy typical source file extensions
                $ext = [System.IO.Path]::GetExtension($found.FullName).ToLower()
                $allowedExt = @('.cpp', '.c', '.cc', '.cxx', '.h', '.hpp')
                if (-not ($allowedExt -contains $ext)) {
                    Write-Host "Skipping copy of non-source file type: $($found.FullName)"
                    continue
                }

                # Skip files that live in excluded subdirectories under project root
                # PS 5.1 compatible relative path calculation (GetRelativePath doesn't exist in .NET < 4.7)
                $rel = $found.FullName
                if ($rel.StartsWith($ProjectRoot)) {
                    $rel = $rel.Substring($ProjectRoot.Length).TrimStart([System.IO.Path]::DirectorySeparatorChar)
                }
                $excludeDirs = @('build', 'build-mingw', 'tests', 'tools', '.git', 'generated_tests', 'googletest', 'images')
                $isExcluded = $false
                foreach ($ex in $excludeDirs) {
                    if ($rel -match "(^|[\\/])$ex($|[\\/])") { $isExcluded = $true; break }
                }
                if ($isExcluded) {
                    Write-Host "Skipping copy from excluded subdir: $rel"
                    continue
                }

                # Copy preserving the expected destination path
                $destDir = Split-Path $expected -Parent
                if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
                Copy-Item -Path $found.FullName -Destination $expected -Force
                Write-Host "Copied: $($found.FullName) -> $expected"
                $copied++
            } else {
                Write-Warning "Could not find a source file matching '$base' in project root"
            }
        }
    }
}

Write-Host "ensure_gcov_sources finished; files copied: $copied"
