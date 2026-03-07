param(
  [Parameter(Mandatory = $true)]
  [int]$Count,
  [string]$OutputDir = (Join-Path $env:USERPROFILE "Desktop\chatmock-auths"),
  [string]$RepoDir = ""
)

if ($Count -lt 1) {
  throw "Count must be at least 1."
}

if ([string]::IsNullOrWhiteSpace($RepoDir)) {
  $scriptDir = Split-Path -Parent $PSCommandPath
  $RepoDir = Split-Path -Parent $scriptDir
}

$chatmockPy = Join-Path $RepoDir "chatmock.py"
if (-not (Test-Path $chatmockPy)) {
  throw "chatmock.py not found: $chatmockPy"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$existingIndexes = @()
Get-ChildItem -Path $OutputDir -File -ErrorAction SilentlyContinue | ForEach-Object {
  if ($_.Name -match "^auth(\d+)\.json$") {
    $existingIndexes += [int]$Matches[1]
  }
}
Get-ChildItem -Path $OutputDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
  if ($_.Name -match "^acc(\d+)$") {
    $existingIndexes += [int]$Matches[1]
  }
}

$startIndex = 1
if ($existingIndexes.Count -gt 0) {
  $startIndex = (($existingIndexes | Measure-Object -Maximum).Maximum) + 1
}

$created = @()
$oldChatgptLocalHome = $env:CHATGPT_LOCAL_HOME
$oldCodexHome = $env:CODEX_HOME
$captureRoot = Join-Path $OutputDir ".capture"

New-Item -ItemType Directory -Force -Path $captureRoot | Out-Null

Push-Location $RepoDir
try {
  for ($offset = 0; $offset -lt $Count; $offset++) {
    $index = $startIndex + $offset
    $label = "auth{0:D2}" -f $index
    $targetDir = Join-Path $captureRoot $label
    $authPath = Join-Path $targetDir "auth.json"
    $savedAuthPath = Join-Path $OutputDir ($label + ".json")

    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    $env:CHATGPT_LOCAL_HOME = $targetDir
    Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "[$label] Starting login flow"
    Write-Host "[$label] Capture path: $savedAuthPath"

    python $chatmockPy login
    if ($LASTEXITCODE -ne 0) {
      throw "Login failed for $label"
    }

    if (-not (Test-Path $authPath)) {
      throw "auth.json was not created for $label"
    }

    Copy-Item -Path $authPath -Destination $savedAuthPath -Force
    Remove-Item -Recurse -Force $targetDir

    $created += $savedAuthPath
    Write-Host "[$label] Saved: $savedAuthPath"
  }
}
finally {
  if ([string]::IsNullOrWhiteSpace($oldChatgptLocalHome)) {
    Remove-Item Env:CHATGPT_LOCAL_HOME -ErrorAction SilentlyContinue
  } else {
    $env:CHATGPT_LOCAL_HOME = $oldChatgptLocalHome
  }

  if ([string]::IsNullOrWhiteSpace($oldCodexHome)) {
    Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue
  } else {
    $env:CODEX_HOME = $oldCodexHome
  }

  Pop-Location
}

if (Test-Path $captureRoot) {
  Remove-Item -Recurse -Force $captureRoot -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Done. Auth files:"
$created | ForEach-Object { Write-Host $_ }
