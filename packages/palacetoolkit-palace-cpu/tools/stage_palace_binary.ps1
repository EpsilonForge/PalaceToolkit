param(
    [Parameter(Mandatory=$true)]
    [string]$BinDir,
    [Parameter(Mandatory=$false)]
    [string[]]$LibDirs = @()
)

$ErrorActionPreference = "Stop"

$srcBinDir = $BinDir
if (-not (Test-Path $srcBinDir)) {
    Write-Error "Binary directory not found: $srcBinDir"
    exit 1
}

$srcLauncher = Join-Path $srcBinDir "palace.exe"
$srcEngine = Join-Path $srcBinDir "palace-x86_64.exe"

if (-not (Test-Path $srcLauncher)) {
    Write-Error "Binary not found: $srcLauncher"
    exit 1
}
if (-not (Test-Path $srcEngine)) {
    Write-Error "Binary not found: $srcEngine"
    exit 1
}

$pkgDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$dstBinDir = Join-Path $pkgDir "src" "palacetoolkit_palace_cpu" "bin"
$dstLibDir = Join-Path $pkgDir "src" "palacetoolkit_palace_cpu" "lib"

New-Item -ItemType Directory -Force -Path $dstBinDir | Out-Null
Copy-Item $srcLauncher (Join-Path $dstBinDir "palace.exe") -Force
Copy-Item $srcEngine (Join-Path $dstBinDir "palace-x86_64.exe") -Force

if (Test-Path $dstLibDir) {
    Remove-Item -Recurse -Force $dstLibDir
}
New-Item -ItemType Directory -Force -Path $dstLibDir | Out-Null

$validLibDirs = @()
foreach ($dir in $LibDirs) {
    if (Test-Path $dir) {
        $validLibDirs += $dir
    }
}

if ($validLibDirs.Count -eq 0) {
    Write-Error "No valid library directory found in arguments: $($LibDirs -join ', ')"
    exit 1
}

function IsRuntimeLib {
    param([string]$DepPath)
    foreach ($root in $validLibDirs) {
        if ($DepPath.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Get-DllDependencies {
    param([string]$TargetPath)
    $output = & dumpbin /dependents $TargetPath 2>$null
    $inDeps = $false
    $deps = @()
    foreach ($line in $output) {
        if ($line -match "^Image has the following dependencies:$") {
            $inDeps = $true
            continue
        }
        if ($inDeps) {
            if ($line -match "^\s+(.+\.dll)$") {
                $deps += $matches[1]
            }
            elseif ($line -match "^\s*$") {
                break
            }
        }
    }
    return $deps
}

$queued = @{}
$queue = @($srcEngine)

while ($queue.Count -gt 0) {
    $target = $queue[0]
    $queue = $queue[1..($queue.Count - 1)]

    $dllNames = Get-DllDependencies $target
    foreach ($dllName in $dllNames) {
        $found = $false
        foreach ($libRoot in $validLibDirs) {
            $candidate = Join-Path $libRoot $dllName
            if (Test-Path $candidate) {
                $found = $true
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
    Write-Error "No runtime DLLs were discovered from provided library directories."
    exit 1
}

Write-Output "Staged binaries in $dstBinDir and $($queued.Count) runtime libraries in $dstLibDir"