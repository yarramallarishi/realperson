$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$runtimeDir = Join-Path $projectRoot ".omnibot-cloudflare"
$tunnelStdout = Join-Path $runtimeDir "cloudflared.stdout.log"
$tunnelStderr = Join-Path $runtimeDir "cloudflared.stderr.log"
$apiStdout = Join-Path $runtimeDir "api.stdout.log"
$apiStderr = Join-Path $runtimeDir "api.stderr.log"
$botStdout = Join-Path $runtimeDir "bot.stdout.log"
$botStderr = Join-Path $runtimeDir "bot.stderr.log"
$cloudflaredCommand = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflaredCommand -and (Test-Path "C:\Program Files (x86)\cloudflared\cloudflared.exe")) {
    $cloudflaredPath = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
} elseif ($cloudflaredCommand) {
    $cloudflaredPath = $cloudflaredCommand.Source
}

if (-not $cloudflaredPath) {
    throw "cloudflared is not installed. Run: winget install --id Cloudflare.cloudflared --exact"
}
if (-not (Test-Path $python)) {
    throw "Python environment is missing. Create it with: py -3.13 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

$requiredSettings = @{}
Get-Content (Join-Path $projectRoot ".env") | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)\s*=\s*(.*)\s*$') {
        $requiredSettings[$matches[1]] = $matches[2]
    }
}
foreach ($key in @("DISCORD_TOKEN", "DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET")) {
    if ([string]::IsNullOrWhiteSpace($requiredSettings[$key])) {
        throw "$key is missing from .env."
    }
}

$apiPort = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 8000)
try {
    $apiPort.Start()
} catch {
    throw "Port 8000 is already in use. Stop the existing OmniBot API before running this script."
} finally {
    $apiPort.Stop()
}

New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
foreach ($logPath in @($tunnelStdout, $tunnelStderr, $apiStdout, $apiStderr, $botStdout, $botStderr)) {
    if (Test-Path $logPath) {
        Remove-Item -LiteralPath $logPath -Force
    }
}

$apiProcess = $null
$botProcess = $null
$tunnelProcess = $null
Push-Location $projectRoot
try {
    Write-Host "Building the dashboard..." -ForegroundColor Cyan
    Push-Location (Join-Path $projectRoot "frontend")
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) {
            throw "Dashboard build failed with exit code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }

    Write-Host "Applying local database migrations..." -ForegroundColor Cyan
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Database migration failed with exit code $LASTEXITCODE."
    }

    Write-Host "Starting the Cloudflare Quick Tunnel..." -ForegroundColor Cyan
    $tunnelProcess = Start-Process -FilePath $cloudflaredPath `
        -ArgumentList @("tunnel", "--url", "http://127.0.0.1:8000", "--no-autoupdate") `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput $tunnelStdout `
        -RedirectStandardError $tunnelStderr `
        -PassThru

    $publicUrl = $null
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline -and -not $publicUrl) {
        if ($tunnelProcess.HasExited) {
            $logs = @()
            if (Test-Path $tunnelStdout) { $logs += Get-Content $tunnelStdout }
            if (Test-Path $tunnelStderr) { $logs += Get-Content $tunnelStderr }
            throw "cloudflared exited before creating a tunnel.`n$($logs -join [Environment]::NewLine)"
        }
        $logs = @()
        if (Test-Path $tunnelStdout) { $logs += Get-Content $tunnelStdout }
        if (Test-Path $tunnelStderr) { $logs += Get-Content $tunnelStderr }
        $match = [regex]::Match(($logs -join "`n"), "https://[a-z0-9-]+\.trycloudflare\.com")
        if ($match.Success) {
            $publicUrl = $match.Value
        } else {
            Start-Sleep -Seconds 1
        }
    }
    if (-not $publicUrl) {
        throw "Timed out waiting for a Quick Tunnel URL. Check .omnibot-cloudflare\cloudflared.stderr.log."
    }

    $env:DISCORD_REDIRECT_URI = "$publicUrl/auth/callback"
    $env:FRONTEND_URL = $publicUrl
    $env:ENVIRONMENT = "production"

    Write-Host ""
    Write-Host "Public dashboard:        $publicUrl" -ForegroundColor Green
    Write-Host "Discord redirect URI:    $env:DISCORD_REDIRECT_URI" -ForegroundColor Yellow
    Write-Host "Add that exact redirect URI in Discord Developer Portal > OAuth2 > Redirects." -ForegroundColor Yellow
    Write-Host "Keep this window open. The public URL expires when this script stops." -ForegroundColor Yellow
    Write-Host ""

    $apiProcess = Start-Process -FilePath $python `
        -ArgumentList @("-m", "uvicorn", "omnibot.api.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput $apiStdout `
        -RedirectStandardError $apiStderr `
        -PassThru

    $healthReady = $false
    $healthClient = New-Object System.Net.WebClient
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline -and -not $healthReady) {
        if ($apiProcess.HasExited) {
            $logs = @()
            if (Test-Path $apiStdout) { $logs += Get-Content $apiStdout }
            if (Test-Path $apiStderr) { $logs += Get-Content $apiStderr }
            throw "The API exited during startup.`n$($logs -join [Environment]::NewLine)"
        }
        try {
            $health = $healthClient.DownloadString("http://127.0.0.1:8000/health")
            $healthReady = $health -match '"status"\s*:\s*"ok"'
        } catch [System.Net.WebException] {
            $healthReady = $false
        }
        if (-not $healthReady) {
            Start-Sleep -Seconds 1
        }
    }
    $healthClient.Dispose()
    if (-not $healthReady) {
        throw "The API did not become healthy within 30 seconds."
    }

    $botProcess = Start-Process -FilePath $python `
        -ArgumentList @("-m", "omnibot.bot") `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput $botStdout `
        -RedirectStandardError $botStderr `
        -PassThru

    while ($true) {
        Start-Sleep -Seconds 2
        foreach ($process in @(
            @{ Name = "Cloudflare Tunnel"; Process = $tunnelProcess },
            @{ Name = "API"; Process = $apiProcess },
            @{ Name = "Discord bot"; Process = $botProcess }
        )) {
            if ($process.Process.HasExited) {
                $logPath = switch ($process.Name) {
                    "Cloudflare Tunnel" { $tunnelStderr }
                    "API" { $apiStderr }
                    "Discord bot" { $botStderr }
                }
                $details = if (Test-Path $logPath) { Get-Content $logPath -Tail 30 } else { @() }
                throw "$($process.Name) stopped unexpectedly.`n$($details -join [Environment]::NewLine)"
            }
        }
    }
} finally {
    foreach ($process in @($botProcess, $apiProcess, $tunnelProcess)) {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
        }
    }
    Pop-Location
}
