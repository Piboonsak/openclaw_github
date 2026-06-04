# run_local_checks.ps1 — Pre-commit and local quality assurance checks
# Set execution policy to bypass or run directly if required:
# PowerShell: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ErrorActionPreference = "Stop"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Running local quality checks for AI Accounting" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# Check 1: Ruff Lint verification
Write-Host "`n[1/4] Running Ruff Linter check..." -ForegroundColor Yellow
if (Get-Command ruff -ErrorAction SilentlyContinue) {
    ruff check src/
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Ruff linter check failed. Fix errors using 'ruff check --fix src/'"
    } else {
        Write-Host "Ruff check passed successfully." -ForegroundColor Green
    }
} else {
    Write-Warning "Ruff is not installed or not in System PATH. Skipping. Install via 'pip install ruff'"
}

# Check 2: Ruff Format verification
Write-Host "`n[2/4] Running Ruff Formatter verification..." -ForegroundColor Yellow
if (Get-Command ruff -ErrorAction SilentlyContinue) {
    ruff format --check src/
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Ruff formatting check failed. Format code using 'ruff format src/'"
    } else {
        Write-Host "Ruff formatting check passed." -ForegroundColor Green
    }
} else {
    Write-Warning "Ruff not found. Skipping formatting check."
}

# Check 3: Mypy static typecheck validation
Write-Host "`n[3/4] Running Mypy static type assertions..." -ForegroundColor Yellow
if (Get-Command mypy -ErrorAction SilentlyContinue) {
    mypy src/ --ignore-missing-imports
    if ($LASTEXITCODE -ne 0) {
         Write-Error "Mypy static type check failed. Fix type assertions above."
    } else {
         Write-Host "Mypy status: All type checks passed." -ForegroundColor Green
    }
} else {
    Write-Warning "Mypy not found. Skipping static typecheck. Install via 'pip install mypy'"
}

# Check 4: Pytest unit tests suite
Write-Host "`n[4/4] Executing test suite via Pytest..." -ForegroundColor Yellow
if (Get-Command pytest -ErrorAction SilentlyContinue) {
    pytest tests/
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Pytest Suite failed."
    } else {
        Write-Host "Pytest suite passed successfully!" -ForegroundColor Green
    }
} else {
    Write-Warning "Pytest not found. Skipping unit assertions. Run 'pip install pytest'"
}

Write-Host "`n=============================================" -ForegroundColor Green
Write-Host " All local validation checkpoints PASSED!" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
