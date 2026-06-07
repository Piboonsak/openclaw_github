$ErrorActionPreference = 'Stop'

$root = 'D:\01_gitrepo\ai-accounting-copilot\private_data\poc\Comp_1'
$pdfs = Get-ChildItem -Path $root -Recurse -File -Filter *.pdf | Sort-Object FullName
if (-not $pdfs) { throw 'No PDF found in Comp_1' }

# Exclude known non-transaction reference docs by stable hash
$excludedSha256 = @(
  'ba1aedd99e24f991f213b7d6c33d9525ce2557613f3b02f90c3d40d31dcade5a'
)

$docMeta = @()
foreach ($f in $pdfs) {
  $sha = (Get-FileHash -Path $f.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  $isExcluded = $excludedSha256 -contains $sha
  $docMeta += [pscustomobject]@{
    File = $f
    Sha256 = $sha
    Include = (-not $isExcluded)
    ExclusionReason = if ($isExcluded) { 'non_transaction_reference_doc' } else { '' }
  }
}

# deterministic random shuffle (normal random with fixed seed)
$seed = 20260604
$rand = [System.Random]::new($seed)
$includedDocs = $docMeta | Where-Object { $_.Include }
$shuffled = $includedDocs | Sort-Object { $rand.Next() }

$total = $shuffled.Count
$trainCount = [int][math]::Floor($total * 0.70)
$valCount = [int][math]::Floor($total * 0.15)
$testCount = $total - $trainCount - $valCount

$train = $shuffled[0..($trainCount - 1)]
$val = $shuffled[$trainCount..($trainCount + $valCount - 1)]
$test = $shuffled[($trainCount + $valCount)..($total - 1)]

$splitMap = @{}
$train | ForEach-Object { $splitMap[$_.File.FullName] = 'train' }
$val | ForEach-Object { $splitMap[$_.File.FullName] = 'val' }
$test | ForEach-Object { $splitMap[$_.File.FullName] = 'test' }

function Get-DocTypeGuess([string]$name, [string]$dir) {
  $s = ($name + ' ' + $dir).ToLower()
  if ($s -match 'purchase|ap|vendor|bill-buy') { return 'purchase' }
  if ($s -match 'sale|ar|customer|bill-sale|invoice') { return 'sale' }
  if ($s -match 'receipt|receive|cash-in') { return 'receipt' }
  if ($s -match 'payment|pay|cash-out') { return 'payment' }
  return 'unknown'
}

$manifestPath = Join-Path $root 'manifest.jsonl'
$expectPath = Join-Path $root 'expectations.template.jsonl'
$splitPath = Join-Path $root 'split.json'

$manifestLines = New-Object System.Collections.Generic.List[string]
$expectLines = New-Object System.Collections.Generic.List[string]

$metaByPath = @{}
$docMeta | ForEach-Object { $metaByPath[$_.File.FullName] = $_ }

$idx = 1
foreach ($f in $pdfs) {
  $docId = ('comp1-{0:d4}' -f $idx)
  $rel = $f.FullName
  if ($rel.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
    $rel = $rel.Substring($root.Length).TrimStart('\', '/')
  }
  $rel = $rel -replace '\\', '/'
  $docType = Get-DocTypeGuess $f.Name $f.DirectoryName
  $partyType = if ($docType -eq 'sale' -or $docType -eq 'receipt') { 'customer' } elseif ($docType -eq 'purchase' -or $docType -eq 'payment') { 'vendor' } else { 'unknown' }
  $meta = $metaByPath[$f.FullName]
  $sha = $meta.Sha256
  $include = $meta.Include
  $exclusionReason = $meta.ExclusionReason
  $split = if ($include) { $splitMap[$f.FullName] } else { 'excluded' }

  $manifestObj = [ordered]@{
    doc_id = $docId
    company_id = 'comp_1'
    file_name = $f.Name
    relative_path = $rel
    file_path = $f.FullName
    file_size_bytes = $f.Length
    sha256 = $sha
    include_in_training = $include
    exclusion_reason = $exclusionReason
    split = $split
    doc_type_guess = $docType
    party_type_guess = $partyType
    language_hint = 'tha+eng'
    is_multi_page = $null
    notes = ''
  }
  $manifestLines.Add(($manifestObj | ConvertTo-Json -Compress))

  $expObj = [ordered]@{
    doc_id = $docId
    split = $split
    include_in_training = $include
    exclusion_reason = $exclusionReason
    file_name = $f.Name
    relative_path = $rel
    labeling_status = if ($include) { 'pending' } else { 'excluded' }
    doc_type = ''
    party_type = ''
    invoice_number = ''
    invoice_date = ''
    due_date = ''
    seller_name = ''
    seller_tax_id = ''
    buyer_name = ''
    buyer_tax_id = ''
    branch_code = ''
    currency = 'THB'
    net_amount = ''
    vat_rate = ''
    vat_amount = ''
    wht_rate = ''
    wht_amount = ''
    total_amount = ''
    payment_terms = ''
    po_number = ''
    reference_number = ''
    page_count = ''
    is_multi_page = ''
    reviewer = ''
    review_note = ''
  }
  $expectLines.Add(($expObj | ConvertTo-Json -Compress))
  $idx++
}

Set-Content -Path $manifestPath -Value $manifestLines -Encoding UTF8
Set-Content -Path $expectPath -Value $expectLines -Encoding UTF8

$splitObj = [ordered]@{
  seed = $seed
  strategy = 'random'
  total_pdfs = $pdfs.Count
  total_included = $total
  total_excluded = ($pdfs.Count - $total)
  counts = [ordered]@{ train = $trainCount; val = $valCount; test = $testCount; excluded = ($pdfs.Count - $total) }
  train = ($train | ForEach-Object {
    $p = $_.File.FullName
    if ($p.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) { $p = $p.Substring($root.Length).TrimStart('\', '/') }
    $p -replace '\\', '/'
  })
  val = ($val | ForEach-Object {
    $p = $_.File.FullName
    if ($p.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) { $p = $p.Substring($root.Length).TrimStart('\', '/') }
    $p -replace '\\', '/'
  })
  test = ($test | ForEach-Object {
    $p = $_.File.FullName
    if ($p.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) { $p = $p.Substring($root.Length).TrimStart('\', '/') }
    $p -replace '\\', '/'
  })
  excluded = (($docMeta | Where-Object { -not $_.Include }) | ForEach-Object {
    $p = $_.File.FullName
    if ($p.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) { $p = $p.Substring($root.Length).TrimStart('\', '/') }
    [ordered]@{
      relative_path = ($p -replace '\\', '/')
      sha256 = $_.Sha256
      reason = $_.ExclusionReason
    }
  })
}
$splitObj | ConvertTo-Json -Depth 5 | Set-Content -Path $splitPath -Encoding UTF8

Write-Output "created: $manifestPath"
Write-Output "created: $expectPath"
Write-Output "created: $splitPath"
Write-Output "counts train=$trainCount val=$valCount test=$testCount included=$total excluded=$($pdfs.Count-$total) total_pdfs=$($pdfs.Count)"
