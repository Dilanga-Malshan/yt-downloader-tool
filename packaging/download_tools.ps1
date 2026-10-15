$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force vendor, security | Out-Null
$records = @()
function Assert-Checksum($Path, $Expected) {
    if ($Expected -notmatch '^[a-fA-F0-9]{64}$') { throw "Invalid SHA256 for $Path" }
    $actual = (Get-FileHash $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $Expected.ToLowerInvariant()) { throw "SHA256 mismatch for $Path" }
    return $actual
}
$ffmpegUrl = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
Invoke-WebRequest "$ffmpegUrl.sha256" -OutFile ffmpeg.sha256
$match = [regex]::Match((Get-Content ffmpeg.sha256 -Raw), '(?i)\b[a-f0-9]{64}\b')
if (-not $match.Success) { throw 'FFmpeg publisher checksum missing' }
Invoke-WebRequest $ffmpegUrl -OutFile ffmpeg.zip
$hash = Assert-Checksum 'ffmpeg.zip' $match.Value
$records += @{ tool = 'FFmpeg'; source = $ffmpegUrl; sha256 = $hash; verified = $true }
Expand-Archive ffmpeg.zip -DestinationPath ffmpeg-extracted
$ffmpeg = Get-ChildItem ffmpeg-extracted -Directory | Select-Object -First 1
Copy-Item "$($ffmpeg.FullName)/bin/ffmpeg.exe" vendor/
Copy-Item "$($ffmpeg.FullName)/bin/ffprobe.exe" vendor/
Copy-Item "$($ffmpeg.FullName)/LICENSE" vendor/FFmpeg-LICENSE.txt
$release = Invoke-RestMethod 'https://api.github.com/repos/denoland/deno/releases/latest' -Headers @{ 'User-Agent' = 'YT-Downloader-Pro-Build' }
$asset = $release.assets | Where-Object name -eq 'deno-x86_64-pc-windows-msvc.zip' | Select-Object -First 1
if (-not $asset -or $asset.digest -notmatch '^sha256:[a-fA-F0-9]{64}$') { throw 'Deno release SHA256 missing' }
Invoke-WebRequest $asset.browser_download_url -OutFile deno.zip
$hash = Assert-Checksum 'deno.zip' $asset.digest.Substring(7)
$records += @{ tool = 'Deno'; version = $release.tag_name; source = $asset.browser_download_url; sha256 = $hash; verified = $true }
Expand-Archive deno.zip -DestinationPath vendor
Invoke-WebRequest "https://raw.githubusercontent.com/denoland/deno/$($release.tag_name)/LICENSE.md" -OutFile vendor/Deno-LICENSE.txt
$records | ConvertTo-Json -Depth 4 | Out-File security/tool-checksums.json -Encoding utf8
