param([string]$Python)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    $Python = Join-Path $repoRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Builder Python not found: $Python"
}

$auditBase = Join-Path $repoRoot "work\release-audit"
$runRoot = Join-Path $auditBase ([guid]::NewGuid().ToString("N"))
$wheelDirectory = Join-Path $runRoot "wheel"
$environment = Join-Path $runRoot "venv"
New-Item -ItemType Directory -Force -Path $wheelDirectory | Out-Null

try {
    & $Python -m pip wheel $repoRoot --no-deps --wheel-dir $wheelDirectory --quiet
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $wheel = Get-ChildItem -LiteralPath $wheelDirectory -Filter "*.whl" | Select-Object -First 1
    if (-not $wheel) { throw "Wheel build produced no artifact" }

    & $Python -m venv $environment
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $freshPython = Join-Path $environment "Scripts\python.exe"
    $wheelWithUi = "$($wheel.FullName)[ui]"
    & $freshPython -m pip install $wheelWithUi --quiet
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $freshUi = Join-Path $environment "Scripts\ado-ui.exe"
    $freshOrganizer = Join-Path $environment "Scripts\ado-organize.exe"
    & $freshUi --help | Out-Null
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $freshOrganizer --help | Out-Null
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $wheelHash = (Get-FileHash -LiteralPath $wheel.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Output "wheel=$($wheel.Name)"
    Write-Output "wheel_sha256=$wheelHash"
    & $freshPython (Join-Path $PSScriptRoot "release_audit.py")
    exit $LASTEXITCODE
}
finally {
    $resolvedBase = [IO.Path]::GetFullPath($auditBase).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $resolvedRun = [IO.Path]::GetFullPath($runRoot)
    $requiredPrefix = $resolvedBase + [IO.Path]::DirectorySeparatorChar
    if ($resolvedRun.StartsWith($requiredPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedRun -Recurse -Force -ErrorAction SilentlyContinue
    }
}
