param([string]$Python)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $repoRoot ".venv\Scripts\python.exe" }
if (-not (Test-Path -LiteralPath $Python)) { throw "Builder Python not found: $Python" }
if (-not (Test-Path -LiteralPath (Join-Path $env:WINDIR "System32\icuuc.dll"))) {
    throw "Windows system ICU is required for the Qt 6 distribution"
}
$version = (& $Python -c "from asset_delivery_organizer.version import __version__; print(__version__)").Trim()
if ($LASTEXITCODE -ne 0 -or $version -ne "1.1.0") { throw "Expected release version 1.1.0, got $version" }

$buildRoot = Join-Path $repoRoot "work\windows-build"
$pyiDist = Join-Path $buildRoot "pyinstaller-dist"
$pyiWork = Join-Path $buildRoot "pyinstaller-work"
$specRoot = Join-Path $buildRoot "spec"
$stageName = "AssetDeliveryOrganizer-$version-windows-x64"
$stage = Join-Path $buildRoot $stageName
$artifact = Join-Path $repoRoot "dist\$stageName.zip"
$versionFile = Join-Path $repoRoot "packaging\windows-version-info.txt"

$resolvedBuild = [IO.Path]::GetFullPath($buildRoot)
$expectedBuild = [IO.Path]::GetFullPath((Join-Path $repoRoot "work\windows-build"))
if ($resolvedBuild -ne $expectedBuild) { throw "Unexpected build root: $resolvedBuild" }
if (Test-Path -LiteralPath $buildRoot) { Remove-Item -LiteralPath $buildRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $pyiDist, $pyiWork, $specRoot | Out-Null

function Invoke-PyInstaller([string]$Name, [string]$Entry, [switch]$Windowed, [switch]$OneFile) {
    $arguments = @(
        "-m", "PyInstaller", "--noconfirm", "--clean", "--noupx",
        "--name", $Name,
        "--distpath", $pyiDist,
        "--workpath", (Join-Path $pyiWork $Name),
        "--specpath", $specRoot,
        "--version-file", $versionFile
    )
    if ($Windowed) { $arguments += "--windowed" } else { $arguments += "--console" }
    if ($OneFile) { $arguments += "--onefile" } else { $arguments += "--onedir" }
    $arguments += (Join-Path $repoRoot $Entry)
    & $Python @arguments
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed for $Name" }
}

Invoke-PyInstaller "AssetDeliveryOrganizer" "packaging\ado_ui_entry.py" -Windowed
Invoke-PyInstaller "ado" "packaging\ado_cli_entry.py" -OneFile
Invoke-PyInstaller "ado-organize" "packaging\ado_organize_entry.py" -OneFile
Invoke-PyInstaller "ado-capabilities" "packaging\ado_capabilities_entry.py" -OneFile

Copy-Item -LiteralPath (Join-Path $pyiDist "AssetDeliveryOrganizer") -Destination $stage -Recurse
# Some developer PATHs expose Poppler's version-suffixed ICU under the generic
# icuuc.dll name. PyInstaller can collect that unrelated DLL beside Qt and shadow
# the Windows system ICU that Qt for Python targets. Remove only those two known
# contaminated filenames from the staged app; the build preflight above proves
# the intended Windows ICU is present.
$stagedInternal = Join-Path $stage "_internal"
foreach ($name in @("icuuc.dll", "icudt78.dll")) {
    $contaminated = Join-Path $stagedInternal $name
    if (Test-Path -LiteralPath $contaminated) {
        Remove-Item -LiteralPath $contaminated -Force
    }
}
foreach ($name in @("ado.exe", "ado-organize.exe", "ado-capabilities.exe")) {
    Copy-Item -LiteralPath (Join-Path $pyiDist $name) -Destination (Join-Path $stage $name)
}
Copy-Item -LiteralPath (Join-Path $repoRoot "profiles") -Destination (Join-Path $stage "profiles") -Recurse
New-Item -ItemType Directory -Force -Path (Join-Path $stage "demo") | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot "demo\scenarios") -Destination (Join-Path $stage "demo\scenarios") -Recurse
foreach ($name in @("assets-manifest.json", "expected-results.json", "LICENSE.md", "README.md")) {
    Copy-Item -LiteralPath (Join-Path $repoRoot "demo\$name") -Destination (Join-Path $stage "demo\$name")
}
Copy-Item -LiteralPath (Join-Path $repoRoot "LICENSE") -Destination (Join-Path $stage "LICENSE.txt")
Copy-Item -LiteralPath (Join-Path $repoRoot "packaging\PORTABLE_README.txt") -Destination (Join-Path $stage "README-首次使用.txt")
Copy-Item -LiteralPath (Join-Path $repoRoot "packaging\THIRD_PARTY_NOTICES.md") -Destination (Join-Path $stage "THIRD_PARTY_NOTICES.md")

& $Python (Join-Path $repoRoot "scripts\create_release_archive.py") --source $stage --output $artifact --version $version
exit $LASTEXITCODE
