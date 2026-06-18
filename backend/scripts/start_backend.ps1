param(
    [int]$ApiPort = 8000,
    [string]$ApiHost = "127.0.0.1",
    [int]$RedisPort = 6379,
    [switch]$NoRedis,
    [switch]$Visible
)

$ErrorActionPreference = "Stop"

function Test-TcpPort {
    param(
        [string]$HostName,
        [int]$Port
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne(700, $false)) {
            return $false
        }
        $client.EndConnect($connect)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Start-BackendProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory,
        [string]$StdOut,
        [string]$StdErr,
        [bool]$ShowWindow
    )

    $windowStyle = if ($ShowWindow) { "Normal" } else { "Hidden" }
    Write-Host "Starting $Name ..."
    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle $windowStyle `
        -RedirectStandardOutput $StdOut `
        -RedirectStandardError $StdErr `
        -PassThru

    Write-Host "$Name pid: $($process.Id)"
    return $process
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendRoot = Resolve-Path (Join-Path $scriptDir "..")
$logRoot = Join-Path $backendRoot "logs"
$runStamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runLogRoot = Join-Path $logRoot $runStamp

New-Item -ItemType Directory -Force -Path $runLogRoot | Out-Null

Write-Host "Backend root: $backendRoot"
Write-Host "Logs: $runLogRoot"

$started = [ordered]@{}

if (-not $NoRedis) {
    if (Test-TcpPort -HostName "127.0.0.1" -Port $RedisPort) {
        Write-Host "Redis is already listening on 127.0.0.1:$RedisPort"
        $started.redis = "already-running"
    }
    else {
        $redisCommand = Get-Command "redis-server" -ErrorAction SilentlyContinue
        if ($null -eq $redisCommand) {
            Write-Warning "redis-server was not found in PATH. Start Redis manually or run this script with -NoRedis."
            $started.redis = "not-found"
        }
        else {
            $redisProcess = Start-BackendProcess `
                -Name "Redis" `
                -FilePath $redisCommand.Source `
                -ArgumentList @("--port", "$RedisPort") `
                -WorkingDirectory $backendRoot `
                -StdOut (Join-Path $runLogRoot "redis.out.log") `
                -StdErr (Join-Path $runLogRoot "redis.err.log") `
                -ShowWindow:$Visible.IsPresent
            $started.redis = $redisProcess.Id
            Start-Sleep -Seconds 1
        }
    }
}

$celeryProcess = Start-BackendProcess `
    -Name "Celery worker" `
    -FilePath "uv" `
    -ArgumentList @("run", "celery", "-A", "app.workers.celery_app.celery_app", "worker", "--loglevel=info", "--pool=solo") `
    -WorkingDirectory $backendRoot `
    -StdOut (Join-Path $runLogRoot "celery.out.log") `
    -StdErr (Join-Path $runLogRoot "celery.err.log") `
    -ShowWindow:$Visible.IsPresent
$started.celery = $celeryProcess.Id

if (Test-TcpPort -HostName $ApiHost -Port $ApiPort) {
    Write-Host "FastAPI is already listening on ${ApiHost}:$ApiPort"
    $apiProcess = $null
    $started.api = "already-running"
}
else {
    $apiProcess = Start-BackendProcess `
        -Name "FastAPI" `
        -FilePath "uv" `
        -ArgumentList @("run", "uvicorn", "app.main:app", "--reload", "--host", $ApiHost, "--port", "$ApiPort") `
        -WorkingDirectory $backendRoot `
        -StdOut (Join-Path $runLogRoot "uvicorn.out.log") `
        -StdErr (Join-Path $runLogRoot "uvicorn.err.log") `
        -ShowWindow:$Visible.IsPresent
    $started.api = $apiProcess.Id
}

$pidFile = Join-Path $runLogRoot "pids.json"
[pscustomobject]$started | ConvertTo-Json | Set-Content -LiteralPath $pidFile -Encoding UTF8

Write-Host "Waiting for FastAPI health check ..."
$healthUrl = "http://${ApiHost}:${ApiPort}/health"
$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $healthy = $true
            break
        }
    }
    catch {
        if ($null -ne $apiProcess -and $apiProcess.HasExited) {
            break
        }
    }
}

if ($healthy) {
    Write-Host "Backend is ready: $healthUrl"
    Write-Host "API docs: http://${ApiHost}:${ApiPort}/docs"
}
else {
    Write-Warning "FastAPI did not pass health check. Check logs under $runLogRoot"
}

Write-Host "PID file: $pidFile"
