#!/usr/bin/env pwsh
param(
    [string]$Owner = "YAHWAN-SHOP",
    [string]$Repo = "YAHWAN-SHOP/ai-accounting-copilot",
    [int]$ProjectNumber = 1,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$taskMeta = @{
    'TASK-501' = @{ rag = 'Red';   owner = 'backend-extraction-agent'; eta = 'Day 2' }
    'TASK-502' = @{ rag = 'Red';   owner = 'backend-extraction-agent'; eta = 'Day 4' }
    'TASK-503' = @{ rag = 'Red';   owner = 'dba-agent';                eta = 'Day 5' }
    'TASK-504' = @{ rag = 'Red';   owner = 'data-science-agent';       eta = 'Day 6' }
    'TASK-505' = @{ rag = 'Green'; owner = 'data-science-agent';       eta = 'Day 1' }
    'TASK-506' = @{ rag = 'Green'; owner = 'data-science-agent';       eta = 'Day 2' }
    'TASK-507' = @{ rag = 'Amber'; owner = 'backend-extraction-agent'; eta = 'Day 3' }
    'TASK-508' = @{ rag = 'Amber'; owner = 'backend-extraction-agent'; eta = 'Day 4' }
    'TASK-509' = @{ rag = 'Red';   owner = 'qa-risk-agent';            eta = 'Day 3' }
    'TASK-510' = @{ rag = 'Amber'; owner = 'data-science-agent';       eta = 'Day 7' }
    'TASK-511' = @{ rag = 'Green'; owner = 'data-science-agent';       eta = 'Day 1' }
    'TASK-512' = @{ rag = 'Amber'; owner = 'qa-risk-agent';            eta = 'Day 3' }
    'TASK-513' = @{ rag = 'Green'; owner = 'frontend-ux-agent';        eta = 'Day 8' }
    'TASK-514' = @{ rag = 'Amber'; owner = 'frontend-ux-agent';        eta = 'Day 9' }
    'TASK-515' = @{ rag = 'Amber'; owner = 'data-science-agent';       eta = 'Day 10' }
}

$ownerOptions = @(
    'backend-extraction-agent',
    'data-science-agent',
    'dba-agent',
    'qa-risk-agent',
    'frontend-ux-agent'
)

function Get-Project {
    param([string]$OwnerName, [int]$Number)
    $project = gh project list --owner $OwnerName --format json | ConvertFrom-Json
    $entry = $project.projects | Where-Object { $_.number -eq $Number }
    if (-not $entry) {
        throw "Project #$Number not found for owner $OwnerName"
    }
    return $entry
}

function Get-Fields {
    param([string]$OwnerName, [int]$Number)
    return (gh project field-list $Number --owner $OwnerName --format json | ConvertFrom-Json).fields
}

function Get-OrCreateSingleSelectField {
    param(
        [string]$OwnerName,
        [int]$Number,
        [string]$FieldName,
        [string[]]$Options
    )

    $fields = Get-Fields -OwnerName $OwnerName -Number $Number
    $field = $fields | Where-Object { $_.name -eq $FieldName }
    if (-not $field) {
        $optArg = ($Options -join ',')
        if (-not $DryRun) {
            gh project field-create $Number --owner $OwnerName --name $FieldName --data-type SINGLE_SELECT --single-select-options $optArg | Out-Null
        }
        $fields = Get-Fields -OwnerName $OwnerName -Number $Number
        $field = $fields | Where-Object { $_.name -eq $FieldName }
    }
    return $field
}

function Get-OrCreateTextField {
    param(
        [string]$OwnerName,
        [int]$Number,
        [string]$FieldName
    )

    $fields = Get-Fields -OwnerName $OwnerName -Number $Number
    $field = $fields | Where-Object { $_.name -eq $FieldName }
    if (-not $field) {
        if (-not $DryRun) {
            gh project field-create $Number --owner $OwnerName --name $FieldName --data-type TEXT | Out-Null
        }
        $fields = Get-Fields -OwnerName $OwnerName -Number $Number
        $field = $fields | Where-Object { $_.name -eq $FieldName }
    }
    return $field
}

$project = Get-Project -OwnerName $Owner -Number $ProjectNumber
$projectId = $project.id

$phaseField = Get-OrCreateSingleSelectField -OwnerName $Owner -Number $ProjectNumber -FieldName 'Phase' -Options @('Phase 1','Phase 2','Phase 4')
$priorityField = Get-OrCreateSingleSelectField -OwnerName $Owner -Number $ProjectNumber -FieldName 'Priority' -Options @('Low','Medium','High','Critical')
$ragField = Get-OrCreateSingleSelectField -OwnerName $Owner -Number $ProjectNumber -FieldName 'RAG' -Options @('Red','Amber','Green')
$ownerField = Get-OrCreateSingleSelectField -OwnerName $Owner -Number $ProjectNumber -FieldName 'Owner Agent' -Options $ownerOptions
$etaField = Get-OrCreateTextField -OwnerName $Owner -Number $ProjectNumber -FieldName 'ETA'

if (-not $phaseField -or -not $priorityField -or -not $ragField -or -not $ownerField -or -not $etaField) {
    throw "One or more required fields are missing and could not be ensured"
}

$phaseOptionByName = @{}
foreach ($opt in $phaseField.options) { $phaseOptionByName[$opt.name] = $opt.id }
$priorityOptionByName = @{}
foreach ($opt in $priorityField.options) { $priorityOptionByName[$opt.name] = $opt.id }
$ragOptionByName = @{}
foreach ($opt in $ragField.options) { $ragOptionByName[$opt.name] = $opt.id }
$ownerOptionByName = @{}
foreach ($opt in $ownerField.options) { $ownerOptionByName[$opt.name] = $opt.id }

$issues = gh issue list --repo $Repo --limit 200 --label "epic:5" --json number,title,url,labels | ConvertFrom-Json

$items = gh project item-list $ProjectNumber --owner $Owner --limit 800 --format json | ConvertFrom-Json
$itemIdByUrl = @{}
foreach ($it in $items.items) {
    if ($it.content.url) { $itemIdByUrl[$it.content.url] = $it.id }
}

$added = 0
foreach ($i in $issues) {
    if (-not $itemIdByUrl.ContainsKey($i.url)) {
        if ($DryRun) {
            Write-Host "[DRY-RUN] Would add issue #$($i.number)"
        } else {
            gh project item-add $ProjectNumber --owner $Owner --url $i.url | Out-Null
            Write-Host "Added issue #$($i.number)"
        }
        $added++
    }
}

$items = gh project item-list $ProjectNumber --owner $Owner --limit 800 --format json | ConvertFrom-Json
$itemIdByUrl = @{}
foreach ($it in $items.items) {
    if ($it.content.url) { $itemIdByUrl[$it.content.url] = $it.id }
}

$updated = 0
$skipped = 0

foreach ($i in $issues) {
    if (-not $itemIdByUrl.ContainsKey($i.url)) {
        $skipped++
        continue
    }

    $taskId = $null
    if ($i.title -match '(TASK-\d{3})') {
        $taskId = $Matches[1]
    }

    if (-not $taskId -or -not $taskMeta.ContainsKey($taskId)) {
        $skipped++
        continue
    }

    $itemId = $itemIdByUrl[$i.url]

    $phaseLabel = ($i.labels | Where-Object { $_.name -like 'phase:*' } | Select-Object -First 1).name
    if ($phaseLabel) {
        $phaseNo = $phaseLabel.Split(':')[1]
        $phaseName = "Phase $phaseNo"
        if ($phaseOptionByName.ContainsKey($phaseName)) {
            if ($DryRun) {
                Write-Host "[DRY-RUN] Issue #$($i.number) set Phase=$phaseName"
            } else {
                gh project item-edit --id $itemId --project-id $projectId --field-id $phaseField.id --single-select-option-id $phaseOptionByName[$phaseName] | Out-Null
            }
        }
    }

    $priorityLabel = ($i.labels | Where-Object { $_.name -like 'priority:*' } | Select-Object -First 1).name
    if ($priorityLabel) {
        $p = $priorityLabel.Split(':')[1]
        $priorityName = (Get-Culture).TextInfo.ToTitleCase($p)
        if ($priorityOptionByName.ContainsKey($priorityName)) {
            if ($DryRun) {
                Write-Host "[DRY-RUN] Issue #$($i.number) set Priority=$priorityName"
            } else {
                gh project item-edit --id $itemId --project-id $projectId --field-id $priorityField.id --single-select-option-id $priorityOptionByName[$priorityName] | Out-Null
            }
        }
    }

    $meta = $taskMeta[$taskId]
    if ($ragOptionByName.ContainsKey($meta.rag)) {
        if ($DryRun) {
            Write-Host "[DRY-RUN] Issue #$($i.number) set RAG=$($meta.rag)"
        } else {
            gh project item-edit --id $itemId --project-id $projectId --field-id $ragField.id --single-select-option-id $ragOptionByName[$meta.rag] | Out-Null
        }
    }

    if ($ownerOptionByName.ContainsKey($meta.owner)) {
        if ($DryRun) {
            Write-Host "[DRY-RUN] Issue #$($i.number) set Owner Agent=$($meta.owner)"
        } else {
            gh project item-edit --id $itemId --project-id $projectId --field-id $ownerField.id --single-select-option-id $ownerOptionByName[$meta.owner] | Out-Null
        }
    }

    if ($DryRun) {
        Write-Host "[DRY-RUN] Issue #$($i.number) set ETA=$($meta.eta)"
    } else {
        gh project item-edit --id $itemId --project-id $projectId --field-id $etaField.id --text $meta.eta | Out-Null
        Write-Host "Updated issue #$($i.number) metadata"
    }

    $updated++
}

Write-Host "Done. Added=$added Updated=$updated Skipped=$skipped"
