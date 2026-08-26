param([ValidateSet("quick")][string]$Tier = "quick")

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = "python" }

& $python (Join-Path $PSScriptRoot "validate_goal_state.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python (Join-Path $PSScriptRoot "export_contract_schemas.py") --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python (Join-Path $PSScriptRoot "export_organization_schemas.py") --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python (Join-Path $PSScriptRoot "export_capabilities.py") --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python (Join-Path $PSScriptRoot "generate_demo_assets.py") --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m pytest (Join-Path $repoRoot "tests") (Join-Path $repoRoot "scripts\tests") -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m ruff check (Join-Path $repoRoot "src") (Join-Path $repoRoot "tests") (Join-Path $repoRoot "scripts")
exit $LASTEXITCODE
