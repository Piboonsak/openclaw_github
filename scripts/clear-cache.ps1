[CmdletBinding()]
param(
    [switch]$RestartServer,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$cacheDirs = @(
    "src/backend/ml/cache",
    "src/backend/services/cache",
    "tmp/stage_c_images"
)

function Reset-Directory {
    param([string]$Path)

    $fullPath = Join-Path $repoRoot $Path
    if (Test-Path $fullPath) {
        $deleted = $false
        for ($attempt = 1; $attempt -le 5; $attempt++) {
            try {
                Remove-Item -Path $fullPath -Recurse -Force -ErrorAction Stop
                $deleted = $true
                break
            } catch {
                if ($attempt -lt 5) {
                    Start-Sleep -Seconds 1
                }
            }
        }

        if (-not $deleted) {
            # Fallback: best-effort remove children so most cache entries are cleared.
            Get-ChildItem -Path $fullPath -Force -ErrorAction SilentlyContinue |
                ForEach-Object {
                    try {
                        Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction Stop
                    } catch {
                        Write-Warning ("LOCKED|{0}" -f $_.FullName)
                    }
                }
        }
    }
    New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    Write-Output ("CLEARED|{0}" -f $Path)
}

function Stop-ServerByPort {
    param([int]$ListenPort)

    $listeners = Get-NetTCPConnection -LocalPort $ListenPort -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique

    if (-not $listeners) {
        Write-Output ("SERVER|No listener on port {0}" -f $ListenPort)
        return
    }

    foreach ($processId in $listeners) {
        if ($processId -and $processId -gt 0) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            Write-Output ("SERVER|Stopped process {0} on port {1}" -f $processId, $ListenPort)
        }
    }
}

function Start-Server {
    param([int]$ListenPort)

    $pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) {
        throw ".venv python not found at $pythonExe"
    }

    $command = "$env:PYTHONPATH = '$repoRoot'; & '$pythonExe' -m uvicorn src.backend.app.main:app --host 127.0.0.1 --port $ListenPort"
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "Set-Location '$repoRoot'; $command" | Out-Null
    Write-Output ("SERVER|Started uvicorn on 127.0.0.1:{0}" -f $ListenPort)
}

if ($RestartServer) {
    Stop-ServerByPort -ListenPort $Port
}

foreach ($dir in $cacheDirs) {
    Reset-Directory -Path $dir
}

if ($RestartServer) {
    Start-Server -ListenPort $Port
    Write-Output "NEXT|Run: curl.exe -sS http://127.0.0.1:$Port/api/health"
} else {
    Write-Output "NEXT|If needed, restart server manually after cache clear"
}
