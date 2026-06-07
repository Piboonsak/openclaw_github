#!/usr/bin/env pwsh
# Create GitHub issues for all 33 PoC project tasks

param(
    [switch]$DryRun = $false,
    [string]$Repo = "YAHWAN-SHOP/ai-accounting-copilot"
)

# Task definitions
$tasks = @(
    # Epic 1: Governance
    @{ epic=1; number=101; title="Agent state tracking"; priority="high"; phase=1 }
    @{ epic=1; number=102; title="Evidence validation gate"; priority="high"; phase=1 }
    @{ epic=1; number=103; title="Pre-commit hooks (4 gates)"; priority="high"; phase=1 }
    # Epic 2: COA Selectors
    @{ epic=2; number=201; title="COA dictionary and search"; priority="high"; phase=2 }
    @{ epic=2; number=202; title="Dropdown UI in Step 5"; priority="high"; phase=2 }
    @{ epic=2; number=203; title="Balance calculation"; priority="high"; phase=2 }
    # Epic 3: Export
    @{ epic=3; number=301; title="Rename to Export"; priority="medium"; phase=2 }
    @{ epic=3; number=302; title="Config panel with presets"; priority="high"; phase=2 }
    @{ epic=3; number=303; title="exportCSV with templates"; priority="high"; phase=2 }
    # Epic 4: Deployment
    @{ epic=4; number=401; title="deploy-demo.ps1 script"; priority="high"; phase=4 }
    @{ epic=4; number=402; title="Docker networking and volumes"; priority="high"; phase=4 }
    # Epic 5: Parser (15 tasks)
    @{ epic=5; number=501; title="OCR processor"; priority="critical"; phase=1 }
    @{ epic=5; number=502; title="Claude extraction with routing"; priority="critical"; phase=1 }
    @{ epic=5; number=503; title="Journal routing with COA"; priority="critical"; phase=1 }
    @{ epic=5; number=504; title="Ground truth schema"; priority="high"; phase=1 }
    @{ epic=5; number=505; title="Labeling SOP"; priority="high"; phase=1 }
    @{ epic=5; number=506; title="Multi-page handling"; priority="medium"; phase=1 }
    @{ epic=5; number=507; title="Low-confidence escalation"; priority="high"; phase=1 }
    @{ epic=5; number=508; title="KPI reporting"; priority="medium"; phase=1 }
    @{ epic=5; number=509; title="Quality gate (accuracy >= 95%)"; priority="critical"; phase=1 }
    @{ epic=5; number=510; title="Field-level accuracy metrics"; priority="medium"; phase=1 }
    @{ epic=5; number=511; title="Cohort tracking"; priority="medium"; phase=1 }
    @{ epic=5; number=512; title="Test split management"; priority="medium"; phase=1 }
    @{ epic=5; number=513; title="Accuracy report generation"; priority="medium"; phase=1 }
    @{ epic=5; number=514; title="Cohort infographic"; priority="medium"; phase=1 }
    @{ epic=5; number=515; title="Baseline benchmarking"; priority="high"; phase=1 }
    # Epic 6: HEAL Loop
    @{ epic=6; number=601; title="SHA-256 caching registry"; priority="high"; phase=2 }
    @{ epic=6; number=602; title="SQLite feedback DB"; priority="high"; phase=2 }
    @{ epic=6; number=603; title="Few-shot prompt injection"; priority="high"; phase=2 }
    # Epic 7: Master Sync
    @{ epic=7; number=701; title="Import parser"; priority="high"; phase=4 }
    @{ epic=7; number=702; title="Express master upsert"; priority="critical"; phase=4 }
    @{ epic=7; number=703; title="Pre-export validation"; priority="critical"; phase=4 }
    @{ epic=7; number=704; title="Audit report and retry"; priority="high"; phase=4 }
)

Write-Host ("Creating {0} GitHub issues..." -f $tasks.Count) -ForegroundColor Cyan

$successCount = 0
$failCount = 0

foreach ($task in $tasks) {
    $num = $task.number
    $title = "[TASK-{0}] {1}" -f $num, $task.title
    $epic = $task.epic
    $phase = $task.phase
    $priority = $task.priority
    
    $labels = @(
        "type:task",
        ("epic:{0}" -f $epic),
        ("phase:{0}" -f $phase),
        ("priority:{0}" -f $priority)
    )
    
    $body = @"
## Task TASK-$num - $($task.title)

Epic $epic | Phase $phase | Priority $priority

See full specs in docs/PoC/plan/epic-$epic/EPIC-$epic-TASKS-DETAIL.md
"@

    $labelStr = ($labels | ForEach-Object { "--label `"$_`"" }) -join " "
    
    if ($DryRun) {
        Write-Host ("`n[TASK-{0}]" -f $num) -ForegroundColor Yellow
        Write-Host ("  Title: {0}" -f $title)
        Write-Host ("  Labels: {0}" -f ($labels -join ", "))
    } else {
        try {
            Write-Host ("Creating TASK-{0}..." -f $num) -ForegroundColor Green
            $cmd = "gh issue create --repo $Repo --title `"$title`" --body `"$body`" $labelStr"
            Invoke-Expression $cmd | Out-Null
            $successCount++
        } catch {
            Write-Host ("ERROR on TASK-{0}: {1}" -f $num, $_) -ForegroundColor Red
            $failCount++
        }
    }
}

Write-Host "`n==========================================" -ForegroundColor Cyan
if ($DryRun) {
    Write-Host "DRY RUN: 33 issues ready to create" -ForegroundColor Yellow
    Write-Host "Run without -DryRun to create actual issues" -ForegroundColor Yellow
} else {
    Write-Host ("Created {0} issues, {1} failed" -f $successCount, $failCount) -ForegroundColor Green
    Write-Host ("Check: https://github.com/{0}/issues" -f $Repo) -ForegroundColor Cyan
}
