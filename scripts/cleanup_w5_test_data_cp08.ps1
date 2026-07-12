$ErrorActionPreference = 'Stop'

function New-Stamp {
  return (Get-Date).ToString('yyyy-MM-ddTHH-mm-ss-fffK').Replace(':','-')
}

function Import-DotEnv {
  param([string]$Path)

  if (-not (Test-Path $Path)) { return }
  $lines = Get-Content -Path $Path
  foreach ($raw in $lines) {
    $line = $raw.Trim()
    if (-not $line -or $line.StartsWith('#')) { continue }
    $idx = $line.IndexOf('=')
    if ($idx -lt 1) { continue }
    $key = $line.Substring(0, $idx).Trim()
    $val = $line.Substring($idx + 1).Trim().Trim('"')
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($key))) {
      [Environment]::SetEnvironmentVariable($key, $val)
    }
  }
}

function Get-RequiredEnv {
  param([Parameter(Mandatory = $true)][string]$Name)
  $value = [Environment]::GetEnvironmentVariable($Name)
  if ([string]::IsNullOrWhiteSpace($value)) {
    throw "Missing required environment variable: $Name"
  }
  return $value
}

function Test-W5ProofUserMatch {
  param($User)

  $email = ([string]$User.email).ToLowerInvariant()
  $username = ([string]$User.username).ToLowerInvariant()
  $displayName = ([string]$User.display_name).ToLowerInvariant()
  $emailLocal = ''
  $emailDomain = ''

  if ($email.Contains('@')) {
    $parts = $email.Split('@', 2)
    $emailLocal = $parts[0]
    $emailDomain = $parts[1]
  }

  $patterns = @(
    '^w5h06[-_]',
    '^w5-proof[-_]',
    '^w5-sysadmin-',
    '^w5-h06-',
    '^sit-verify[-_]',
    '^cp-?08[-_]'
  )

  $isMatch = $false
  foreach ($rx in $patterns) {
    if ($username -match $rx -or $displayName -match $rx) {
      $isMatch = $true
      break
    }
    if (-not [string]::IsNullOrWhiteSpace($emailLocal) -and $emailLocal -match $rx) {
      $isMatch = $true
      break
    }
  }

  # Guard against accidental deactivation of non-proof accounts.
  if ($isMatch -and -not [string]::IsNullOrWhiteSpace($emailDomain)) {
    return $emailDomain -eq 'ledgerflow.local'
  }
  return $isMatch
}

function Invoke-JsonApi {
  param(
    [Parameter(Mandatory = $true)][string]$Method,
    [Parameter(Mandatory = $true)][string]$Url,
    [Parameter(Mandatory = $true)][hashtable]$Headers,
    $Body = $null
  )

  if ($null -eq $Body) {
    return Invoke-RestMethod -Method $Method -Uri $Url -Headers $Headers
  }

  return Invoke-RestMethod -Method $Method -Uri $Url -Headers $Headers -ContentType 'application/json' -Body ($Body | ConvertTo-Json -Depth 30)
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $repoRoot

Import-DotEnv -Path (Join-Path $repoRoot '.env.sit.local')
Import-DotEnv -Path (Join-Path $repoRoot '.env.local')

$baseUrl = Get-RequiredEnv -Name 'POC_URL'
$sysUser = Get-RequiredEnv -Name 'SIT_SYS_ADMIN_USER'
$sysPass = Get-RequiredEnv -Name 'SIT_SYS_ADMIN_PASS'

$prefixes = @('W5H06', 'W5 Proof', 'SIT Verify', 'CP-08')
$userSelectorVersion = 'strict-v2'

$stamp = New-Stamp
$outDir = Join-Path $repoRoot "test-results/w5-copilot-human-review-deploy-proof-08/$stamp"
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

$login = Invoke-RestMethod -Method POST -Uri "$baseUrl/api/v1/auth/login" -ContentType 'application/json' -Body ((@{
  username = $sysUser
  password = $sysPass
} | ConvertTo-Json -Depth 5))

$headers = @{ Authorization = "Bearer $($login.access_token)" }

$me = Invoke-JsonApi -Method 'GET' -Url "$baseUrl/api/v1/auth/me" -Headers $headers

$allCompanies = Invoke-JsonApi -Method 'GET' -Url "$baseUrl/api/v1/admin/companies" -Headers $headers
$targetCompanies = @($allCompanies | Where-Object {
  $name = [string]$_.name
  $prefixes | Where-Object { $name.StartsWith($_) }
})

$allUsers = Invoke-JsonApi -Method 'GET' -Url "$baseUrl/api/v1/admin/users" -Headers $headers
$targetUsers = @($allUsers | Where-Object { Test-W5ProofUserMatch -User $_ })

$summary = [ordered]@{
  generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
  base_url = $baseUrl
  actor = @{
    id = $me.id
    email = $me.email
    role = $me.role
  }
  prefixes = $prefixes
  user_selector_version = $userSelectorVersion
  before = @{
    company_match_count = $targetCompanies.Count
    user_match_count = $targetUsers.Count
    company_matches = @()
    user_matches = @()
  }
  actions = @{
    companies_soft_deleted = @()
    users_deactivated = @()
    document_counts_by_company = @()
    errors = @()
  }
  after = @{
    active_company_match_count = 0
    active_user_match_count = 0
  }
}

foreach ($c in $targetCompanies) {
  $summary.before.company_matches += [ordered]@{
    id = $c.id
    name = $c.name
    is_active = $c.is_active
  }
}

foreach ($u in $targetUsers) {
  $summary.before.user_matches += [ordered]@{
    id = $u.id
    email = $u.email
    username = $u.username
    role = $u.role
    is_active = $u.is_active
  }
}

foreach ($c in $targetCompanies) {
  try {
    $docs = Invoke-JsonApi -Method 'GET' -Url "$baseUrl/api/v1/companies/$($c.id)/documents" -Headers $headers
    $summary.actions.document_counts_by_company += [ordered]@{
      company_id = $c.id
      company_name = $c.name
      document_count = @($docs).Count
    }
  }
  catch {
    $summary.actions.errors += "list documents failed for company $($c.id): $($_.Exception.Message)"
  }

  if ($c.is_active) {
    try {
      Invoke-RestMethod -Method DELETE -Uri "$baseUrl/api/v1/admin/companies/$($c.id)" -Headers $headers | Out-Null
      $summary.actions.companies_soft_deleted += $c.id
    }
    catch {
      $summary.actions.errors += "delete company failed $($c.id): $($_.Exception.Message)"
    }
  }
}

foreach ($u in $targetUsers) {
  if ($u.is_active) {
    try {
      $body = @{
        is_active = $false
        role = $u.role
        company_ids = @($u.company_ids)
      }
      Invoke-JsonApi -Method 'PUT' -Url "$baseUrl/api/v1/admin/users/$($u.id)" -Headers $headers -Body $body | Out-Null
      $summary.actions.users_deactivated += $u.id
    }
    catch {
      $summary.actions.errors += "deactivate user failed $($u.id): $($_.Exception.Message)"
    }
  }
}

$allCompaniesAfter = Invoke-JsonApi -Method 'GET' -Url "$baseUrl/api/v1/admin/companies" -Headers $headers
$allUsersAfter = Invoke-JsonApi -Method 'GET' -Url "$baseUrl/api/v1/admin/users" -Headers $headers

$summary.after.active_company_match_count = @($allCompaniesAfter | Where-Object {
  $name = [string]$_.name
  ($prefixes | Where-Object { $name.StartsWith($_) }).Count -gt 0 -and $_.is_active
}).Count

$summary.after.active_user_match_count = @($allUsersAfter | Where-Object {
  (Test-W5ProofUserMatch -User $_) -and $_.is_active
}).Count

$summaryPath = Join-Path $outDir 'cleanup-summary.json'
$summary | ConvertTo-Json -Depth 100 | Set-Content -Path $summaryPath -Encoding UTF8

Write-Host ($summary | ConvertTo-Json -Depth 8)
Write-Host "cleanup_summary=$summaryPath"
