# 2) Start debug Chrome — log into DistroKid AND Bandcamp once
# Profile: %LOCALAPPDATA%\DK-BC-Uploader\chrome-debug-profile
#
#   .\2_start_chrome.ps1

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_chrome_session.ps1")

$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path $chrome)) {
  $chrome = "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
}
if (-not (Test-Path $chrome)) {
  throw "Chrome not found. Install Google Chrome first."
}

Remove-DkBcLegacyLocalSecrets -Roots @($PSScriptRoot, (Join-Path $PSScriptRoot "app\DK-BC-Uploader"))

$userData = Ensure-DkBcChromeProfileWritable
Clear-DkBcChromeLocks

try {
  $null = Invoke-WebRequest -Uri "http://127.0.0.1:9222/json/version" -UseBasicParsing -TimeoutSec 2
  Write-Host "CDP already up on 9222 - using existing debug Chrome."
  Write-Host "Each DK-BC instance opens its own DistroKid + Bandcamp tabs when it starts."
} catch {
  Write-Host "Starting debug Chrome..."
  Write-Host "  --remote-debugging-port=9222"
  Write-Host "  --remote-allow-origins=*"
  Write-Host "  --user-data-dir=$userData"
  Write-Host "  opens DistroKid + Bandcamp login"

  Start-Process -FilePath $chrome -ArgumentList @(
    "--remote-debugging-port=9222",
    "--remote-allow-origins=*",
    "--user-data-dir=$userData",
    "https://distrokid.com/",
    "https://bandcamp.com/login"
  )

  Start-Sleep -Seconds 2
  $ver = (Invoke-WebRequest -Uri "http://127.0.0.1:9222/json/version" -UseBasicParsing -TimeoutSec 5).Content
  Write-Host "OK CDP:" $ver
}

Write-Host ""
Write-Host "Log into BOTH DistroKid and Bandcamp in that Chrome window"
Write-Host "(login kept under %LOCALAPPDATA%\DK-BC-Uploader)."
Write-Host "Optional title check:  .\3_check_titles.bat"
Write-Host "Upload both:           .\4_dk_bc_uploader.bat"
Write-Host "Smoke (open pages):    .\4_dk_bc_uploader.bat --smoke"
