# Downloads the yt-dlp, ffmpeg and ffprobe sidecars into src-tauri/binaries with the
# target-triple names Tauri expects (externalBin), and checks SHA-256 against
# scripts/binaries.lock.json.
#
#   powershell -ExecutionPolicy Bypass -File scripts\fetch-binaries.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\fetch-binaries.ps1 -Triple x86_64-pc-windows-gnu
#
# A lock entry with a sha256 must match, or the script fails. An empty sha256 prints the
# computed hash and continues. The ffmpeg URL is BtbN "latest" and is not pinned yet:
# copy the hash printed by the first CI run into binaries.lock.json to pin it.
param(
  [string]$Triple = "x86_64-pc-windows-msvc"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest is very slow with the progress bar on PS 5.1
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$root = Split-Path -Parent $PSScriptRoot
$lock = Get-Content -Raw (Join-Path $PSScriptRoot "binaries.lock.json") | ConvertFrom-Json
$bin = Join-Path $root "src-tauri\binaries"
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("keepsake-bin-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force $bin, $tmp | Out-Null

function Get-Checked([string]$Name, $Entry, [string]$Dest) {
  Write-Host "Downloading $Name from $($Entry.url)"
  Invoke-WebRequest -UseBasicParsing -Uri $Entry.url -OutFile $Dest
  $hash = (Get-FileHash -Algorithm SHA256 $Dest).Hash.ToLower()
  $want = "$($Entry.sha256)".Trim().ToLower()
  if ($want -eq "") {
    Write-Host "WARNING: $Name has no pinned sha256 in binaries.lock.json. Computed sha256: $hash"
  } elseif ($hash -ne $want) {
    throw "SHA-256 mismatch for $Name. Expected $want, got $hash"
  } else {
    Write-Host "$Name sha256 OK ($hash)"
  }
}

try {
  # yt-dlp
  Get-Checked "yt-dlp" $lock.'yt-dlp'.windows (Join-Path $bin "yt-dlp-$Triple.exe")

  # ffmpeg + ffprobe from the BtbN zip
  $zip = Join-Path $tmp "ffmpeg.zip"
  Get-Checked "ffmpeg archive" $lock.ffmpeg.windows $zip
  $ext = Join-Path $tmp "x"
  Expand-Archive -Path $zip -DestinationPath $ext -Force
  foreach ($tool in "ffmpeg", "ffprobe") {
    $src = Get-ChildItem -Path $ext -Recurse -File -Filter "$tool.exe" | Select-Object -First 1
    if (-not $src) { throw "$tool.exe not found in the ffmpeg archive" }
    Copy-Item -Force $src.FullName (Join-Path $bin "$tool-$Triple.exe")
  }

  Get-ChildItem $bin | Format-Table Name, Length -AutoSize
} finally {
  Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
