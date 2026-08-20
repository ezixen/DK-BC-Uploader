# 3) Optional â€” preview titles / cover / prices (no upload)
#   .\3_check_titles.ps1
#   .\3_check_titles.ps1 "d:\music\a; d:\music\b"

param(
  [Parameter(Mandatory = $false, Position = 0)]
  [string]$AlbumFolder
)

$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "_common.ps1")

$resolved = Resolve-AlbumFolders $AlbumFolder
$python = Resolve-PythonExe
$script = Get-UploaderPy

Write-Host "Python: $python"
Write-Host ("Albums to check: {0}" -f $resolved.Folders.Count)

$failed = New-Object System.Collections.Generic.List[string]
$i = 0
foreach ($folder in $resolved.Folders) {
  $i++
  Write-Host ""
  Write-Host "======== CHECK $i / $($resolved.Folders.Count): $folder ========" -ForegroundColor Cyan
  try {
    & $python -u $script $folder --dry-run
    if ($LASTEXITCODE -ne 0) {
      $failed.Add("CHECK FAILED (exit $LASTEXITCODE): $folder") | Out-Null
    }
  } catch {
    $failed.Add("CHECK FAILED: $folder - $($_.Exception.Message)") | Out-Null
  }
}

Write-Host ""
Write-Host "======== CHECK SUMMARY ========"
if ($failed.Count -gt 0) {
  $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
  exit 1
}
Write-Host "OK. Next: .\4_dk_bc_uploader.bat `"path`""
exit 0
