# push.ps1: commit and push the voice clips and manifest made by run.ps1 (only .ogg; .gitignore keeps .wav out).
# Ends by copying the result (commit id) to the clipboard.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw 'ffmpeg not found: these clips may be stale .wav runs. Install it (winget install Gyan.FFmpeg), re-run run.ps1, then push.' }
$sum = if (Test-Path 'tmp\last-summary.txt') { (Get-Content 'tmp\last-summary.txt' -Raw).Trim() } else { 'Voice clips updated' }
git add -A -- lines names common reactions interjections manifest
$staged = git diff --cached --name-only
if (-not $staged) { $msg = 'Nothing new to push.'; Write-Host $msg; $msg | Set-Clipboard; exit 0 }
$count = ($staged | Measure-Object).Count
git commit --quiet -m "Voice clips ($count files changed)" -m $sum
if ($LASTEXITCODE -ne 0) { throw 'Commit failed (see above).' }
git pull --quiet --rebase origin main
if ($LASTEXITCODE -ne 0) { throw 'Pull failed (see above). Nothing was pushed. Fix: git rebase --abort, then run push.ps1 again.' }
git push --quiet origin HEAD:main
if ($LASTEXITCODE -ne 0) { throw 'Push failed (see above).' }
$c = (git rev-parse --short HEAD).Trim()
$msg = "Pushed $count clip/manifest files to citadel-sports-voice main @ $c. $sum"
Write-Host $msg
$msg | Set-Clipboard
