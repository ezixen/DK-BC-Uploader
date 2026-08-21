# Build DK-BC-Uploader.exe (onedir) into app\DK-BC-Uploader\
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File app\build_exe.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $root "dk_bc_upload_album.py"))) {
  throw "Run from DK-BC-Uploader folder (dk_bc_upload_album.py missing)."
}

$py = "C:\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  $py = (Get-Command python -ErrorAction Stop).Source
}

Write-Host "Build Python: $py"
& $py -c "import sys; print(sys.version)"
& $py -m pip install -q "pyinstaller>=6.0" "websocket-client>=1.6.0"

$env:PYTHONPATH = $root
$env:PYTHONDONTWRITEBYTECODE = "1"
& $py -c "import chrome_debug, album_media, bandcamp_upload_album, distrokid_upload_album, dk_bc_upload_album; print('imports OK')"

$appPy = Join-Path $PSScriptRoot "dk_bc_app.py"
$settings = Join-Path $root "upload-settings.txt"
$prices = Join-Path $root "prices.txt"
if (-not (Test-Path $settings)) { throw "Missing upload-settings.txt" }
if (-not (Test-Path $prices)) { throw "Missing prices.txt" }
$outRoot = Join-Path $PSScriptRoot "_build_out"
$distName = "DK-BC-Uploader"
$final = Join-Path $PSScriptRoot $distName
$work = Join-Path $PSScriptRoot "_pyi_work"
$spec = Join-Path $PSScriptRoot "_pyi_spec"
$versionFile = Join-Path $PSScriptRoot "version_info.txt"
$iconFile = Join-Path $PSScriptRoot "uploader.ico"
if (-not (Test-Path $iconFile)) { $iconFile = Join-Path $root "images\uploader-logo.ico" }
if (-not (Test-Path $iconFile)) { throw "Missing uploader.ico / images\uploader-logo.ico" }

foreach ($p in @($outRoot, $work, $spec)) {
  if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}

& $py -m PyInstaller `
  --noconfirm `
  --clean `
  --console `
  --name $distName `
  --paths $root `
  --distpath $outRoot `
  --workpath $work `
  --specpath $spec `
  --version-file $versionFile `
  --icon $iconFile `
  --add-data "$settings;." `
  --add-data "$prices;." `
  --hidden-import websocket `
  --hidden-import chrome_debug `
  --hidden-import album_media `
  --hidden-import upload_settings `
  --hidden-import bandcamp_upload_album `
  --hidden-import distrokid_upload_album `
  --hidden-import distrokid_form `
  --hidden-import distrokid_stores `
  --hidden-import distrokid_tracks `
  --hidden-import distrokid_dialogs `
  --hidden-import distrokid_finish `
  --hidden-import dk_bc_upload_album `
  --hidden-import cdp_owned_tab `
  $appPy

if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }

$built = Join-Path $outRoot $distName
$outExe = Join-Path $built "DK-BC-Uploader.exe"
if (-not (Test-Path $outExe)) { throw "Missing $outExe" }

Copy-Item $settings (Join-Path $built "upload-settings.txt") -Force
Copy-Item $prices (Join-Path $built "prices.txt") -Force
@"
DK-BC Uploader (EXE)
====================

Latest: https://github.com/ezixen/DK-BC-Uploader

1. Edit upload-settings.txt (Bandcamp uses album=/track= only)
2. Double-click DK-BC-Uploader.exe
3. Log into DistroKid AND Bandcamp in Chrome (once)
4. Paste album folder path — both fill in parallel (DistroKid first)
5. Review DistroKid, then Bandcamp; next album if both OK
6. Never auto-publishes

Chrome login: %LOCALAPPDATA%\DK-BC-Uploader\
"@ | Set-Content (Join-Path $built "HOW_TO_RUN.txt") -Encoding UTF8

New-Item -ItemType Directory -Force -Path $final | Out-Null
& robocopy $built $final /E /XD local-secrets /NFL /NDL /NJH /NJS /nc /ns /np /R:2 /W:1 | Out-Null
Copy-Item (Join-Path $built "DK-BC-Uploader.exe") (Join-Path $final "DK-BC-Uploader.exe") -Force
Copy-Item (Join-Path $built "upload-settings.txt") (Join-Path $final "upload-settings.txt") -Force
Copy-Item (Join-Path $built "prices.txt") (Join-Path $final "prices.txt") -Force
Copy-Item (Join-Path $built "HOW_TO_RUN.txt") (Join-Path $final "HOW_TO_RUN.txt") -Force

. (Join-Path $PSScriptRoot "sign_exe.ps1")
Invoke-EzixenSign -ExePath (Join-Path $final "DK-BC-Uploader.exe")

& $py -c @"
import sys
from pathlib import Path
sys.path.insert(0, r'$root')
from chrome_debug import scrub_app_folder_side_effects, stop_chrome_using_profile
stop_chrome_using_profile()
scrub_app_folder_side_effects(Path(r'$final'))
print('scrubbed', r'$final')
"@

Write-Host "OK built: $(Join-Path $final 'DK-BC-Uploader.exe')"
Get-ChildItem $final | Select-Object Name, Length | Format-Table -AutoSize
