param(
    [Parameter(Mandatory=$true)]
    [string]$BinDir,
    [Parameter(Mandatory=$false)]
    [string[]]$LibDirs = @()
)

$ErrorActionPreference = "Stop"

# ── Locate the Palace engine binary ──────────────────────────────────────
# Palace's CMakeLists.txt sets OUTPUT_NAME "palace-x86_64" SUFFIX ".bin"
# so the built binary is palace-x86_64.bin.  We rename it to .exe for
# Windows so subprocess.run() and Windows loader both handle it correctly.
$srcEngine = Join-Path $BinDir "palace-x86_64.bin"
if (-not (Test-Path $srcEngine)) {
    Write-Error "Palace engine binary not found: $srcEngine"
    exit 1
}

# ── Compute package destination paths ─────────────────────────────────────
$pkgDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$dstBinDir = Join-Path $pkgDir "src" "palacetoolkit_palace_cpu" "bin"
$dstLibDir = Join-Path $pkgDir "src" "palacetoolkit_palace_cpu" "lib"

New-Item -ItemType Directory -Force -Path $dstBinDir | Out-Null
$dstEngine = Join-Path $dstBinDir "palace-x86_64.exe"
Copy-Item $srcEngine $dstEngine -Force

if (Test-Path $dstLibDir) {
    Remove-Item -Recurse -Force $dstLibDir
}
New-Item -ItemType Directory -Force -Path $dstLibDir | Out-Null

# ── Collect valid library directories ─────────────────────────────────────
$validLibDirs = @()
foreach ($dir in $LibDirs) {
    if (Test-Path $dir) {
        $validLibDirs += $dir
    }
}
if ($validLibDirs.Count -eq 0) {
    Write-Error "No valid library directory found in: $($LibDirs -join ', ')"
    exit 1
}

# ── DLL dependency resolution via objdump (MinGW, always in PATH) ─────────
function Get-DllDependencies {
    param([string]$TargetPath)
    # objdump -p prints "DLL Name: foo.dll" lines for PE binaries
    $output = & objdump -p $TargetPath 2>$null
    $deps = @()
    foreach ($line in $output) {
        if ($line -match "^\s*DLL Name:\s+(.+\.dll)$") {
            $deps += $matches[1]
        }
    }
    return $deps
}

# ── BFS: copy transitive DLL closure ──────────────────────────────────────
$queued = @{}
$queue = @($dstEngine)

while ($queue.Count -gt 0) {
    $target = $queue[0]
    $queue = $queue[1..($queue.Count - 1)]

    $dllNames = Get-DllDependencies $target
    foreach ($dllName in $dllNames) {
        foreach ($libRoot in $validLibDirs) {
            $candidate = Join-Path $libRoot $dllName
            if (Test-Path $candidate) {
                $realPath = (Resolve-Path $candidate).Path
                if (-not $queued.ContainsKey($realPath)) {
                    $queued[$realPath] = $true
                    Copy-Item $realPath (Join-Path $dstLibDir $dllName) -Force
                    $queue += $realPath
                }
                break
            }
        }
    }
}

if ($queued.Count -eq 0) {
    Write-Error "No runtime DLLs discovered from: $($validLibDirs -join ', ')"
    exit 1
}

# ── Also copy MSYS2 system DLLs that Palace needs ─────────────────────────
# These are common MinGW runtime DLLs that may not be in the install tree
$mingwBin = "C:\msys64\mingw64\bin"
$systemDlls = @(
    "libgomp-1.dll",
    "libwinpthread-1.dll",
    "libgcc_s_seh-1.dll",
    "libstdc++-6.dll"
)
foreach ($dll in $systemDlls) {
    $src = Join-Path $mingwBin $dll
    $dst = Join-Path $dstLibDir $dll
    if ((Test-Path $src) -and -not (Test-Path $dst)) {
        Copy-Item $src $dst -Force
        Write-Output "Copied system DLL: $dll"
    }
}

Write-Output "Staged palace-x86_64.exe and $($queued.Count) runtime DLLs in $dstLibDir"
