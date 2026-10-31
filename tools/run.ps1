# run.ps1: make the Corvus and Bastion voice clips on Jordan's PC.
# Gets the latest booth-lines.js from citadel-sports (branch preview), runs tools/generate.py, checks the manifest,
# prints a summary and copies it to the clipboard. Re-running only makes new or changed clips.
#
#   .\tools\run.ps1                         everything (lines, tiers, reactions, interjections, numbers, teams)
#   .\tools\run.ps1 -Only idle              just the idle lines (also: events, tiers, reactions, interjections, numbers, teams)
#   .\tools\run.ps1 -Names roster.json      just player names, from [{ "id": "...", "name": "Josh Jacobs", "team": "GB" }]
#   .\tools\run.ps1 -DryRun                 count what would be made, render nothing
#   .\tools\run.ps1 -Limit 10               first 10 lines only (a quick listen test)
param(
  [string]$Only = '',
  [string]$Names = '',
  [switch]$DryRun,
  [int]$Limit = 0,
  [string]$Branch = 'preview',
  [string]$Venv = 'A:\Citadel\voice-test\venv'
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$tmp = Join-Path $repo 'tmp'
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$start = Get-Date
$log = @()
function Say($s) { Write-Host $s; $script:log += $s }

# 1. tools we need
foreach ($c in 'git', 'node') { if (-not (Get-Command $c -ErrorAction SilentlyContinue)) { throw "$c is not installed (needed to read booth-lines.js)." } }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { Say 'WARNING: ffmpeg not found. Clips will be .wav, not .ogg. Fix: winget install Gyan.FFmpeg  (then open a new PowerShell)' }
$py = Join-Path $Venv 'Scripts\python.exe'
if (-not (Test-Path $py)) { throw "No Python venv at $Venv. Pass -Venv <folder>." }

# 2. latest booth lines from citadel-sports (a small cached clone in tmp\, only the newest commit)
$src = Join-Path $tmp 'citadel-sports'
if (-not (Test-Path (Join-Path $src '.git'))) {
  git clone --quiet --depth 1 --filter=blob:none --no-checkout https://github.com/mrfaceman23/citadel-sports $src
}
$linesFile = Join-Path $tmp 'booth-lines.js'
$exportJson = Join-Path $tmp 'lines.json'
function Get-Lines($b) {
  # (native output goes to Out-Host so it never mixes into this function's $true / $false)
  git -C $src fetch --quiet --depth 1 origin "+refs/heads/${b}:refs/remotes/origin/$b" | Out-Host
  if ($LASTEXITCODE -ne 0) { return $false }
  $commit = (git -C $src rev-parse --short "origin/$b").Trim()
  # cmd's > keeps the file byte-for-byte (a PowerShell pipe would re-encode it)
  cmd /c "git -C `"$src`" show origin/${b}:App/assets/booth-lines.js > `"$linesFile`"" | Out-Host
  if ($LASTEXITCODE -ne 0) { return $false }
  node (Join-Path $PSScriptRoot 'export-lines.mjs') $linesFile $exportJson | Out-Host
  if ($LASTEXITCODE -ne 0) { return $false }
  Say "Lines: citadel-sports $b @ $commit"
  return $true
}
if (-not (Get-Lines $Branch)) {
  # preview gets the speech-ready lines (v9.3.2+) once booth-lines-speech is merged; until then use voice-director
  Say "Branch $Branch has no speech-ready booth lines yet; using voice-director instead."
  if (-not (Get-Lines 'voice-director')) { throw 'Could not read booth-lines.js.' }
}

# 3. generate
$genArgs = @((Join-Path $PSScriptRoot 'generate.py'), '--lines', $exportJson, '--repo', $repo)
if ($Only) { $genArgs += @('--only', $Only) }
if ($Names) { $genArgs += @('--names', (Resolve-Path $Names).Path) }
if ($Limit -gt 0) { $genArgs += @('--limit', "$Limit") }
if ($DryRun) { $genArgs += '--dry-run' }
& $py @genArgs
if ($LASTEXITCODE -ne 0) { throw 'generate.py failed (see above).' }
$sumFile = Join-Path $tmp 'last-summary.txt'
if (-not $DryRun -and (Test-Path $sumFile)) { Say (Get-Content $sumFile -Raw).Trim() }

# 4. check the manifest
if (-not $DryRun) {
  $v = node (Join-Path $PSScriptRoot 'validate-manifest.mjs') (Join-Path $repo 'manifest\manifest.json') --files --lines $linesFile
  $v | ForEach-Object { Write-Host $_ }
  Say ("Manifest check: " + ($(if ($LASTEXITCODE -eq 0) { 'OK' } else { 'FAILED' })) + " (" + (($v | Select-String -Pattern 'ERROR|warn' | Measure-Object).Count) + " notes)")
}

$mins = [math]::Round(((Get-Date) - $start).TotalMinutes, 1)
Say "Total time: $mins min. Next: .\tools\push.ps1 to commit and push the clips."
($log -join "`n") | Set-Clipboard
Write-Host '(summary copied to clipboard)'
