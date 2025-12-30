param(
    [string]$ProjectRoot = (Get-Location).Path,
    [string]$ObjectDir = "",
    [string]$GcovPath = "D:\\Qt\\Tools\\mingw1310_64\\bin\\gcov.exe",
    [string]$GcovrCmd = "gcovr",
    [switch]$NoRunTests
)

Write-Host "ProjectRoot: $ProjectRoot"

if (-not $ObjectDir -or $ObjectDir -eq "") {
    # try to autodetect a debug object directory under tests/build
    $cand = Get-ChildItem -Path (Join-Path $ProjectRoot 'tests\build') -Directory -Recurse -ErrorAction SilentlyContinue |
           Where-Object { $_.FullName -match '[\\/](Debug|debug)[\\/]' } | Select-Object -First 1
    if ($cand) { $ObjectDir = $cand.FullName } else {
        Write-Error "--object-directory not provided and auto-detect failed. Please pass -ObjectDir"
        exit 1
    }
}

Write-Host "Using object directory: $ObjectDir"

if (-not (Test-Path $ObjectDir)) {
    Write-Error "Object directory does not exist: $ObjectDir"
    exit 1
}

# Find test executables (heuristic)
$tests = Get-ChildItem -Path $ObjectDir -Recurse -Filter *.exe -ErrorAction SilentlyContinue |
         Where-Object { $_.Name -match 'test|Test|tests|unittest' } | Select-Object -Unique

if (-not $NoRunTests) {
    if (-not $tests -or $tests.Count -eq 0) {
        Write-Warning "No test executables found by heuristic under $ObjectDir. Listing all .exe instead."
        $tests = Get-ChildItem -Path $ObjectDir -Recurse -Filter *.exe -ErrorAction SilentlyContinue | Select-Object -Unique
    }

    if ($tests.Count -eq 0) {
        Write-Warning "No executables found to run. You may need to build tests first."
    } else {
        foreach ($t in $tests) {
            Write-Host "Running test executable: $($t.FullName)"
            try {
                & "$($t.FullName)"
                Write-Host "Exit code: $LASTEXITCODE"
            } catch {
                Write-Warning "Failed to run $($t.FullName): $_"
            }
        }
    }
} else { Write-Host "Skipping running tests (--NoRunTests set)" }

# After running tests, map .gcda to source files and run gcov on each discovered source
$gcdaFiles = Get-ChildItem -Path $ObjectDir -Recurse -Filter *.gcda -ErrorAction SilentlyContinue
if (-not $gcdaFiles -or $gcdaFiles.Count -eq 0) {
    Write-Warning "No .gcda files found under $ObjectDir. Ensure tests ran with coverage instrumentation."
} else {
    Write-Host "Found $($gcdaFiles.Count) .gcda files. Attempting to map to source files..."
    foreach ($g in $gcdaFiles) {
        Write-Host "Processing $($g.FullName)"
        try {
            $bytes = [System.IO.File]::ReadAllBytes($g.FullName)
            $ascii = -join ($bytes | ForEach-Object { if ($_ -ge 32 -and $_ -le 126) {[char]$_} else {' '} })
            $cands = ($ascii -split '\s+' | Where-Object { $_ -match '\.(cpp|cxx|cc|c|h|hpp)$' }) | Select-Object -Unique
            foreach ($cand in $cands) {
                # try to locate candidate under project root
                $found = Get-ChildItem -Path $ProjectRoot -Recurse -Filter $cand -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($found) {
                    Write-Host "  Mapped $cand -> $($found.FullName). Running gcov..."
                    & "$GcovPath" -v -o $ObjectDir "$($found.FullName)"
                } else {
                    Write-Warning "  Source file not found in project for candidate: $cand"
                }
            }
        } catch {
            Write-Warning "  Error processing $($g.FullName): $_"
        }
    }

    # Finally, run gcovr to produce summary and html
    Write-Host "Running gcovr to aggregate coverage (may require gcovr in PATH)..."
    Push-Location $ProjectRoot
    try {
        & $GcovrCmd -r $ProjectRoot --object-directory $ObjectDir --print-summary --html-details -o (Join-Path $ProjectRoot 'coverage.html')
    } catch {
        Write-Warning "gcovr execution failed: $_"
    }
    Pop-Location
    Write-Host "Coverage generation finished. Output: $ProjectRoot\coverage.html"
}

Write-Host "Done."
