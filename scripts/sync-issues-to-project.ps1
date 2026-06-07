#!/usr/bin/env pwsh
param(
    [string]$Owner = "YAHWAN-SHOP",
    [string]$Repo = "YAHWAN-SHOP/ai-accounting-copilot",
    [int]$ProjectNumber = 1
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Get-FieldMap {
    param([string]$OwnerName, [int]$ProjNumber)
    return (gh project field-list $ProjNumber --owner $OwnerName --format json | ConvertFrom-Json)
}

# 1) Ensure Phase field exists
$fields = Get-FieldMap -OwnerName $Owner -ProjNumber $ProjectNumber
$phaseField = $fields.fields | Where-Object { $_.name -eq "Phase" }
if (-not $phaseField) {
    gh project field-create $ProjectNumber --owner $Owner --name "Phase" --data-type "SINGLE_SELECT" --single-select-options "Phase 1,Phase 2,Phase 4" | Out-Null
    $fields = Get-FieldMap -OwnerName $Owner -ProjNumber $ProjectNumber
    $phaseField = $fields.fields | Where-Object { $_.name -eq "Phase" }
}

$priorityField = $fields.fields | Where-Object { $_.name -eq "Priority" }
if (-not $priorityField) {
    throw "Priority field not found in project."
}

$project = gh project list --owner $Owner --format json | ConvertFrom-Json
$projectEntry = $project.projects | Where-Object { $_.number -eq $ProjectNumber }
if (-not $projectEntry) {
    throw "Project #$ProjectNumber not found for owner $Owner"
}
$projectId = $projectEntry.id

$phaseOptionByName = @{}
foreach ($opt in $phaseField.options) { $phaseOptionByName[$opt.name] = $opt.id }
$priorityOptionByName = @{}
foreach ($opt in $priorityField.options) { $priorityOptionByName[$opt.name] = $opt.id }

# 2) Load issues
$issues = gh issue list --repo $Repo --limit 200 --json number,title,url,labels | ConvertFrom-Json
$taskIssues = $issues | Where-Object { $_.title -match "\[TASK-\d+\]" }

# 3) Add issues to project if missing
$items = gh project item-list $ProjectNumber --owner $Owner --limit 500 --format json | ConvertFrom-Json
$existingUrls = @{}
foreach ($it in $items.items) {
    if ($it.content.url) { $existingUrls[$it.content.url] = $true }
}

$added = 0
foreach ($i in $taskIssues) {
    if (-not $existingUrls.ContainsKey($i.url)) {
        Write-Host "Adding issue #$($i.number) to project..."
        gh project item-add $ProjectNumber --owner $Owner --url $i.url | Out-Null
        $added++
    }
}

# 4) Refresh items and map URL -> itemId
$items = gh project item-list $ProjectNumber --owner $Owner --limit 800 --format json | ConvertFrom-Json
$itemIdByUrl = @{}
foreach ($it in $items.items) {
    if ($it.content.url) { $itemIdByUrl[$it.content.url] = $it.id }
}

# 5) Update Phase + Priority fields per issue labels
$updated = 0
foreach ($i in $taskIssues) {
    if (-not $itemIdByUrl.ContainsKey($i.url)) { continue }

    $itemId = $itemIdByUrl[$i.url]
    $phaseLabel = ($i.labels | Where-Object { $_.name -like "phase:*" } | Select-Object -First 1).name
    $priorityLabel = ($i.labels | Where-Object { $_.name -like "priority:*" } | Select-Object -First 1).name

    if ($phaseLabel) {
        $phaseNo = $phaseLabel.Split(':')[1]
        $phaseName = "Phase $phaseNo"
        if ($phaseOptionByName.ContainsKey($phaseName)) {
            gh project item-edit --id $itemId --project-id $projectId --field-id $phaseField.id --single-select-option-id $phaseOptionByName[$phaseName] | Out-Null
        }
    }

    if ($priorityLabel) {
        $p = $priorityLabel.Split(':')[1]
        $priorityName = (Get-Culture).TextInfo.ToTitleCase($p)
        if ($priorityOptionByName.ContainsKey($priorityName)) {
            gh project item-edit --id $itemId --project-id $projectId --field-id $priorityField.id --single-select-option-id $priorityOptionByName[$priorityName] | Out-Null
        }
    }

    $updated++
    Write-Host "Updated fields for issue #$($i.number)"
}

Write-Host "Project sync complete"
Write-Host "- Task issues found: $($taskIssues.Count)"
Write-Host "- Added to project: $added"
Write-Host "- Field updates applied: $updated"
Write-Host "- Project URL: https://github.com/orgs/$Owner/projects/$ProjectNumber"
