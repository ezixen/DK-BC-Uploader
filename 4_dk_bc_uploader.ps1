# 4) Dual upload: Bandcamp draft + DistroKid form (never publishes either)
#   .\4_dk_bc_uploader.ps1
#   .\4_dk_bc_uploader.ps1 "d:\music\album"
#   .\4_dk_bc_uploader.ps1 --smoke

param(
  [Parameter(Mandatory = $false, Position = 0)]
  [string]$AlbumFolder
)

$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "_common.ps1")

$python = Resolve-PythonExe
$script = Get-UploaderPy

# Smoke mode: open both sites only
if ($AlbumFolder -eq "--smoke" -or $args -contains "--smoke") {
  try {
    $null = Invoke-WebRequest -Uri "http://127.0.0.1:9222/json/version" -UseBasicParsing -TimeoutSec 2
  } catch {
    Write-Host "ERROR: Chrome CDP not on 9222. Run .\2_start_chrome.ps1 first." -ForegroundColor Red
    exit 1
  }
  & $python -u $script --smoke
  exit $LASTEXITCODE
}

$resolved = Resolve-AlbumFolders $AlbumFolder

try {
  $null = Invoke-WebRequest -Uri "http://127.0.0.1:9222/json/version" -UseBasicParsing -TimeoutSec 2
} catch {
  Write-Host "ERROR: Chrome CDP not on 9222. Run .\2_start_chrome.ps1 and log into BOTH sites first." -ForegroundColor Red
  exit 1
}

if ($resolved.Folders.Count -eq 0) {
  Write-Host "ERROR: No valid album folders." -ForegroundColor Red
  exit 1
}

Write-Host "Python: $python"
Write-Host "PARALLEL dual upload: DistroKid (first) + Bandcamp same time. Never publishes."
Write-Host "Review DistroKid while Bandcamp uploads; then check Bandcamp; next album if both OK."
Write-Host "Settings: upload-settings.txt (Bandcamp uses album=/track= prices only)"

$failed = New-Object System.Collections.Generic.List[string]
$succeeded = New-Object System.Collections.Generic.List[string]
$i = 0
foreach ($folder in $resolved.Folders) {
  $i++
  Write-Host ""
  Write-Host "======== DUAL UPLOAD $i / $($resolved.Folders.Count): $folder ========" -ForegroundColor Cyan
  try {
    & $python -u $script $folder
    if ($LASTEXITCODE -ne 0) {
      $failed.Add("FAILED (exit $LASTEXITCODE): $folder") | Out-Null
      Write-Host "ERROR: exit $LASTEXITCODE" -ForegroundColor Red
    } else {
      $succeeded.Add($folder) | Out-Null
      Write-Host "OK: both steps finished for $folder" -ForegroundColor Green
    }
  } catch {
    $failed.Add("FAILED: $folder - $($_.Exception.Message)") | Out-Null
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
  }
}

Write-Host ""
Write-Host "======== SUMMARY ========"
Write-Host ("Succeeded: {0}" -f $succeeded.Count) -ForegroundColor Green
$succeeded | ForEach-Object { Write-Host "  + $_" -ForegroundColor Green }
if ($failed.Count -gt 0) {
  Write-Host ("Failures: {0}" -f $failed.Count) -ForegroundColor Red
  $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
}

. (Join-Path $PSScriptRoot "_chrome_session.ps1")
Write-Host ""
Write-Host "Review BOTH sites in Chrome, then press Enter to stop debug Chrome and clean temp"
Write-Host "(logins kept under %LOCALAPPDATA%\DK-BC-Uploader)."
try { $null = Read-Host } catch {}
$n = Invoke-DkBcSessionCleanup -AppRoots @($PSScriptRoot, (Join-Path $PSScriptRoot "app\DK-BC-Uploader"))
Write-Host "Cleanup done (stopped $n Chrome process(es); login kept)."

if ($succeeded.Count -eq 0) { exit 1 }
if ($failed.Count -gt 0) { exit 2 }
exit 0
