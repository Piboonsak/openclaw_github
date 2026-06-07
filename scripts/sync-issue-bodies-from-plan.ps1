#!/usr/bin/env pwsh
param(
    [string]$Repo = "YAHWAN-SHOP/ai-accounting-copilot"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$taskFiles = @(
    @{ epic = 1; path = "docs/PoC/plan/epic-1/EPIC-1-TASKS-DETAIL.md" },
    @{ epic = 2; path = "docs/PoC/plan/epic-2/EPIC-2-TASKS-DETAIL.md" },
    @{ epic = 3; path = "docs/PoC/plan/epic-3/EPIC-3-TASKS-DETAIL.md" },
    @{ epic = 4; path = "docs/PoC/plan/epic-4/EPIC-4-TASKS-DETAIL.md" },
    @{ epic = 5; path = "docs/PoC/plan/epic-5/EPIC-5-TASKS-DETAIL.md" },
    @{ epic = 6; path = "docs/PoC/plan/epic-6/EPIC-6-TASKS-DETAIL.md" },
    @{ epic = 7; path = "docs/PoC/plan/epic-7/EPIC-7-TASKS-DETAIL.md" }
)

$issues = gh issue list --repo $Repo --limit 200 --json number,title,labels | ConvertFrom-Json
$issueByTask = @{}
foreach ($i in $issues) {
    if ($i.title -match "\[TASK-(\d+)\]") {
        $taskNo = [int]$Matches[1]
        $issueByTask[$taskNo] = $i
    }
}

$tasks = @{}
foreach ($f in $taskFiles) {
    if (-not (Test-Path $f.path)) { continue }
    $raw = Get-Content -Raw -Path $f.path

    $regexMatches = [regex]::Matches($raw, "(?ms)^##\s+TASK-(\d+):\s*(.*?)\r?\n(.*?)(?=^##\s+TASK-\d+:|\z)")
    foreach ($m in $regexMatches) {
        $taskNo = [int]$m.Groups[1].Value
        $taskTitle = $m.Groups[2].Value.Trim()
        $section = $m.Groups[3].Value.Trim()

        # Keep detailed content from plan doc directly in issue body.
        $body = @"
## Task TASK-${taskNo}: $taskTitle

### Epic
- Epic: $($f.epic)
- Timeline: 2-week accelerated plan

### Details
$section

### CI/CD Checklist
- [ ] Review related docs and CI/CD procedure
- [ ] Implement feature/fix per acceptance criteria
- [ ] Add/update tests
- [ ] Verify lint/typecheck/test pass
- [ ] Prepare PR with deployment notes
"@

        $tasks[$taskNo] = @{
            title = $taskTitle
            body  = $body
            epic  = $f.epic
        }
    }
}

$updated = 0
$missing = 0

foreach ($taskNo in ($tasks.Keys | Sort-Object)) {
    if (-not $issueByTask.ContainsKey($taskNo)) {
        Write-Host "Missing issue for TASK-$taskNo" -ForegroundColor Yellow
        $missing++
        continue
    }

    $issue = $issueByTask[$taskNo]
    $tmp = [System.IO.Path]::GetTempFileName()
    Set-Content -Path $tmp -Value $tasks[$taskNo].body -Encoding UTF8

    try {
        gh issue edit $issue.number --repo $Repo --body-file $tmp | Out-Null
        Write-Host "Updated issue #$($issue.number) for TASK-$taskNo" -ForegroundColor Green
        $updated++
    }
    finally {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "--------------------------------------"
Write-Host "Updated: $updated issues"
Write-Host "Missing: $missing tasks"
