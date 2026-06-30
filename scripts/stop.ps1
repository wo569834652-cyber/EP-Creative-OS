$ErrorActionPreference = "SilentlyContinue"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$HealthUrl = "http://127.0.0.1:8000/api/health"
$ShutdownUrl = "http://127.0.0.1:8000/api/system/shutdown"
$PidFile = Join-Path $Root ".ep_creative_os.pid"

function Test-EpServer {
    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

if (Test-EpServer) {
    Invoke-RestMethod -Uri $ShutdownUrl -Method Post -TimeoutSec 2 | Out-Null
    Start-Sleep -Seconds 1
}

if (Test-EpServer) {
    if (Test-Path $PidFile) {
        $storedPid = Get-Content -LiteralPath $PidFile | Select-Object -First 1
        if ($storedPid) {
            Stop-Process -Id ([int]$storedPid) -Force
        }
    }

    if (Test-EpServer) {
        $connections = Get-NetTCPConnection -LocalPort 8000 -State Listen
        foreach ($connection in $connections) {
            $serverPid = $connection.OwningProcess
            $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $serverPid"
            if ($proc.CommandLine -like "*uvicorn*" -and $proc.CommandLine -like "*app.main:app*") {
                Stop-Process -Id $serverPid -Force
            }
        }
    }
}

if (Test-Path $PidFile) {
    Remove-Item -LiteralPath $PidFile -Force
}

Write-Host "EP Creative OS service is closed."
