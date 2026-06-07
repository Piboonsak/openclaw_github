param(
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$taskMeta = @{
    'TASK-501' = @{ rag = 'Red';   owner = 'backend-extraction-agent'; eta = 'Day 2';  dependency = 'TASK-505'; action = 'Lock OCR stack and cache contract' }
    'TASK-502' = @{ rag = 'Red';   owner = 'backend-extraction-agent'; eta = 'Day 4';  dependency = 'TASK-501'; action = 'Freeze schema, routing, and confidence design' }
    'TASK-503' = @{ rag = 'Red';   owner = 'dba-agent';                eta = 'Day 5';  dependency = 'TASK-502, TASK-504'; action = 'Finalize rule engine and Dr/Cr balancing contract' }
    'TASK-504' = @{ rag = 'Red';   owner = 'data-science-agent';       eta = 'Day 6';  dependency = 'TASK-505, TASK-509'; action = 'Lock truth schema and reviewer workflow' }
    'TASK-505' = @{ rag = 'Green'; owner = 'data-science-agent';       eta = 'Day 1';  dependency = 'None'; action = 'Generate deterministic manifest and split baseline' }
    'TASK-506' = @{ rag = 'Green'; owner = 'data-science-agent';       eta = 'Day 2';  dependency = 'TASK-505'; action = 'Freeze expectations template schema' }
    'TASK-507' = @{ rag = 'Amber'; owner = 'backend-extraction-agent'; eta = 'Day 3';  dependency = 'TASK-501'; action = 'Decide delimiter and per-page artifact retention' }
    'TASK-508' = @{ rag = 'Amber'; owner = 'backend-extraction-agent'; eta = 'Day 4';  dependency = 'TASK-501, TASK-502'; action = 'Implement observable primary/fallback policy' }
    'TASK-509' = @{ rag = 'Red';   owner = 'qa-risk-agent';            eta = 'Day 3';  dependency = 'TASK-506'; action = 'Approve labeling normalization and discrepancy policy' }
    'TASK-510' = @{ rag = 'Amber'; owner = 'data-science-agent';       eta = 'Day 7';  dependency = 'TASK-504'; action = 'Set release-gate thresholds and regression rule' }
    'TASK-511' = @{ rag = 'Green'; owner = 'data-science-agent';       eta = 'Day 1';  dependency = 'TASK-505'; action = 'Enforce hash exclusion fail-closed checks' }
    'TASK-512' = @{ rag = 'Amber'; owner = 'qa-risk-agent';            eta = 'Day 3';  dependency = 'TASK-505, TASK-511'; action = 'Finalize quality gate checks and report format' }
    'TASK-513' = @{ rag = 'Green'; owner = 'frontend-ux-agent';        eta = 'Day 8';  dependency = 'TASK-510'; action = 'Deliver stakeholder infographic layout and narrative' }
    'TASK-514' = @{ rag = 'Amber'; owner = 'frontend-ux-agent';        eta = 'Day 9';  dependency = 'TASK-513, TASK-505'; action = 'Define generator architecture and CI trigger' }
    'TASK-515' = @{ rag = 'Amber'; owner = 'data-science-agent';       eta = 'Day 10'; dependency = 'TASK-504, TASK-510'; action = 'Publish benchmark mismatch taxonomy and priorities' }
}

$issues = gh issue list --limit 200 --label "epic:5" --json number,title,body,url | ConvertFrom-Json
$startMarker = '<!-- SPRINT-META:START -->'
$endMarker = '<!-- SPRINT-META:END -->'

$updated = 0
$skipped = 0

foreach ($issue in $issues) {
    $taskId = $null

    if ($issue.title -match '(TASK-\d{3})') {
        $taskId = $Matches[1]
    } elseif ($issue.body -match '(TASK-\d{3})') {
        $taskId = $Matches[1]
    }

    if (-not $taskId -or -not $taskMeta.ContainsKey($taskId)) {
        $skipped++
        continue
    }

    $meta = $taskMeta[$taskId]
    $section = @"
$startMarker
## Sprint Execution Metadata

- RAG: **$($meta.rag)**
- Owner: **$($meta.owner)**
- ETA: **$($meta.eta)**
- Primary dependency: **$($meta.dependency)**
- Discussion focus: $($meta.action)

$endMarker
"@

    $newBody = $issue.body
    if ($newBody -match [regex]::Escape($startMarker) -and $newBody -match [regex]::Escape($endMarker)) {
        $pattern = [regex]::Escape($startMarker) + '[\s\S]*?' + [regex]::Escape($endMarker)
        $newBody = [regex]::Replace($newBody, $pattern, $section.Trim())
    } else {
        $newBody = ($newBody.TrimEnd() + "`n`n" + $section.Trim() + "`n")
    }

    if ($DryRun) {
        Write-Host "[DRY-RUN] Would update issue #$($issue.number) ($taskId)"
        $updated++
        continue
    }

    $tmp = New-TemporaryFile
    Set-Content -Path $tmp -Value $newBody -Encoding UTF8
    gh issue edit $issue.number --body-file $tmp | Out-Null
    Remove-Item $tmp -Force

    Write-Host "Updated issue #$($issue.number) ($taskId)"
    $updated++
}

Write-Host "Done. Updated=$updated Skipped=$skipped"
