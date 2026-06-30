$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Url = "http://127.0.0.1:8000"
$HealthUrl = "$Url/api/health"
$PidFile = Join-Path $Root ".ep_creative_os.pid"
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$LogDir = Join-Path $Root "storage"
$StdoutLog = Join-Path $LogDir "ep_creative_os_server.out.log"
$StderrLog = Join-Path $LogDir "ep_creative_os_server.err.log"

function Test-EpServer {
    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

Set-Location $Root
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (Test-EpServer) {
    Start-Process $Url
    exit 0
}

function Test-PythonDeps {
    param([string]$PythonPath)
    if (-not $PythonPath) {
        return $false
    }
    try {
        & $PythonPath -c "import fastapi, uvicorn, sqlalchemy, pydantic, httpx" | Out-Null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

$SystemPython = $null
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) {
    $SystemPython = $pythonCommand.Source
}

$PythonExe = $null
if (Test-PythonDeps $SystemPython) {
    $PythonExe = $SystemPython
}

if (-not $PythonExe) {
    if (-not (Test-Path $VenvPython)) {
        Write-Host "Creating local Python environment..."
        python -m venv (Join-Path $Root ".venv")
    }

    if (-not (Test-PythonDeps $VenvPython)) {
        Write-Host "Installing EP Creative OS dependencies..."
        & $VenvPython -m pip install -r (Join-Path $Root "requirements.txt")
    }

    $PythonExe = $VenvPython
}

Write-Host "Starting EP Creative OS..."
$process = Start-Process `
    -FilePath $PythonExe `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $StdoutLog `
    -RedirectStandardError $StderrLog `
    -PassThru

Set-Content -LiteralPath $PidFile -Value $process.Id -Encoding ASCII

$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-EpServer) {
        $ready = $true
        break
    }
}

if (-not $ready) {
    Write-Host "EP Creative OS did not start. Run this command in PowerShell to inspect errors:"
    Write-Host "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
    Write-Host "Server stdout log: $StdoutLog"
    Write-Host "Server stderr log: $StderrLog"
    Read-Host "Press Enter to close"
    exit 1
}

Start-Process $Url
