$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$legacyRoot = Join-Path $repoRoot "cache"
if (-not (Test-Path $legacyRoot)) {
    Write-Output "No legacy cache directory found at: $legacyRoot"
    exit 0
}

$mappings = @(
    @{ Name = "TASK-501"; File = "ocr_output.json"; TargetBase = "src/ocr/cache" },
    @{ Name = "TASK-502"; File = "extraction_output.json"; TargetBase = "src/extraction/cache" },
    @{ Name = "TASK-503"; File = "journal_output.json"; TargetBase = "src/validation/cache" }
)

$totalCopied = 0
foreach ($map in $mappings) {
    $files = Get-ChildItem -Path $legacyRoot -Recurse -File -Filter $map.File
    foreach ($file in $files) {
        $shaDir = Split-Path -Parent $file.FullName | Split-Path -Leaf
        $targetDir = Join-Path $repoRoot (Join-Path $map.TargetBase $shaDir)
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

        $targetFile = Join-Path $targetDir $map.File
        Copy-Item -Path $file.FullName -Destination $targetFile -Force
        Write-Output ("Copied {0} -> {1}" -f $file.FullName, $targetFile)
        $totalCopied++
    }
}

Write-Output ("Migration complete. Total files copied: {0}" -f $totalCopied)
