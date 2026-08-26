param(
    [ValidateSet("Resume", "Doctor", "Audit", "Status")]
    [string]$Action = "Status"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $repoRoot "config\goal-state.json"
$state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json

if ($Action -in @("Doctor", "Audit")) {
    & python (Join-Path $PSScriptRoot "validate_goal_state.py")
    exit $LASTEXITCODE
}

if ($Action -eq "Resume") {
    $checkpoint = Join-Path $repoRoot ($state.lastCheckpoint -replace "/", "\")
    Write-Output "Goal: $($state.goalId) revision $($state.stateRevision)"
    Write-Output "Current milestone: $($state.currentMilestone)"
    if ($state.nextSlice) {
        Write-Output "Next slice: $($state.nextSlice.id) - $($state.nextSlice.outcome)"
    } else {
        Write-Output "Next slice: none (goal $($state.status))"
    }
    Write-Output "Checkpoint: $checkpoint"
    exit 0
}

$state | Select-Object goalId,status,stateRevision,currentMilestone,@{Name="nextSlice";Expression={$_.nextSlice.id}},lastCheckpoint | Format-List
