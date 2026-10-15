$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force security | Out-Null
$report = @{ scanner = 'Microsoft Defender'; timestampUtc = [DateTime]::UtcNow.ToString('o'); status = 'failed'; scans = @() }
try {
    $service = Get-Service WinDefend
    if ($service.StartType -eq 'Disabled') { Set-Service WinDefend -StartupType Manual }
    if ($service.Status -ne 'Running') { Start-Service WinDefend }
    Update-MpSignature -ErrorAction Stop
    $status = Get-MpComputerStatus
    if (-not $status.AMServiceEnabled -or -not $status.AntivirusEnabled) { throw 'Defender antivirus is unavailable or disabled' }
    if ($status.AntivirusSignatureLastUpdated -lt (Get-Date).AddDays(-7)) { throw 'Defender signatures are too old' }
    $report.signatureVersion = $status.AntivirusSignatureVersion
    $report.signatureUpdated = $status.AntivirusSignatureLastUpdated.ToUniversalTime().ToString('o')
    $scanner = Get-ChildItem "$env:ProgramData/Microsoft/Windows Defender/Platform/*/MpCmdRun.exe" | Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $scanner) { throw 'Defender scanner was not found' }
    foreach ($target in @('dist/YT-Downloader-Pro', 'installer/YT-Downloader-Pro-Setup.exe')) {
        $resolved = (Resolve-Path $target).Path
        $output = & $scanner.FullName -Scan -ScanType 3 -File $resolved -DisableRemediation 2>&1 | Out-String
        $code = $LASTEXITCODE
        $report.scans += @{ path = $target; exitCode = $code; output = $output }
        if ($code -ne 0) { throw "Defender scan failed or detected a threat in $target (exit $code)" }
    }
    $report.status = 'passed'
} catch {
    $report.error = $_.Exception.Message
    throw
} finally {
    $report | ConvertTo-Json -Depth 6 | Out-File security/malware-scan.json -Encoding utf8
}
