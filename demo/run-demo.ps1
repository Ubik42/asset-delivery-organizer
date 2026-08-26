param(
    [switch]$Verify,
    [switch]$Reset
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$ado = Join-Path $repoRoot ".venv\Scripts\ado.exe"
if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $ado)) {
    throw "Install the project first: .\.venv\Scripts\python.exe -m pip install -e '.[dev]'"
}

$generator = Join-Path $repoRoot "scripts\generate_demo_assets.py"
if ($Reset) {
    & $python $generator --write
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if ($Verify) {
    & $python $generator --check
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$expectations = Get-Content -LiteralPath (Join-Path $PSScriptRoot "expected-results.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$profile = Join-Path $repoRoot ($expectations.profile -replace "/", "\")
$output = Join-Path $PSScriptRoot "output"
New-Item -ItemType Directory -Force -Path $output | Out-Null
$rows = @()

foreach ($expected in $expectations.scenarios) {
    $scenario = Join-Path $PSScriptRoot ("scenarios\" + $expected.scenario_id)
    $reportPath = Join-Path $output ($expected.scenario_id + ".audit.json")
    & $ado $scenario --profile $profile --output $reportPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $report = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $ruleCounts = @{}
    foreach ($group in ($report.issues | Group-Object rule_id)) {
        $ruleCounts[$group.Name] = $group.Count
    }
    $expectedRuleTable = @{}
    foreach ($property in $expected.rule_counts.PSObject.Properties) {
        $expectedRuleTable[$property.Name] = [int]$property.Value
    }
    $rulesPassed = $ruleCounts.Count -eq $expectedRuleTable.Count
    foreach ($ruleId in $expectedRuleTable.Keys) {
        if (-not $ruleCounts.ContainsKey($ruleId) -or [int]$ruleCounts[$ruleId] -ne [int]$expectedRuleTable[$ruleId]) {
            $rulesPassed = $false
        }
    }
    $passed = (
        [int]$report.summary.file_count -eq [int]$expected.file_count -and
        [int]$report.summary.issue_count -eq [int]$expected.issue_count -and
        [int]$report.summary.blocker_count -eq [int]$expected.blocker_count -and
        [int]$report.summary.error_count -eq [int]$expected.error_count -and
        [int]$report.summary.warning_count -eq [int]$expected.warning_count -and
        $rulesPassed -and
        [int]$report.summary.write_count -eq 0
    )
    $rows += [PSCustomObject]@{
        Scenario = $expected.scenario_id
        Files = $report.summary.file_count
        Issues = $report.summary.issue_count
        Blockers = $report.summary.blocker_count
        Errors = $report.summary.error_count
        Warnings = $report.summary.warning_count
        ReadOnly = ($report.summary.write_count -eq 0)
        Status = $(if ($passed) { "PASS" } else { "FAIL" })
    }
    if (-not $passed) {
        Write-Error "Scenario expectation mismatch: $($expected.scenario_id) files=$($report.summary.file_count)/$($expected.file_count) issues=$($report.summary.issue_count)/$($expected.issue_count) rules_ok=$rulesPassed"
        exit 1
    }
}

$rows | Format-Table -AutoSize
Write-Output "Reports: $output"
if ($Verify) {
    & $python $generator --check
    exit $LASTEXITCODE
}
