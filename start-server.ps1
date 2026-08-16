# 启动 HashRoyale 私服：MySQL -> 主服(9339/9876) -> 战斗服(9449)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$hash = Join-Path $root 'HashRoyale'
$mysqlDir = Join-Path $env:USERPROFILE 'cr-tools\mysql'
$mysqlData = Join-Path $env:USERPROFILE 'cr-tools\mysql-data'

if (-not (Get-Process mysqld -ErrorAction SilentlyContinue)) {
    Write-Host '[1/3] Starting MySQL on 3306 ...'
    Start-Process -FilePath (Join-Path $mysqlDir 'bin\mysqld.exe') -ArgumentList @('--no-defaults', "--basedir=$mysqlDir", "--datadir=$mysqlData", '--port=3306') -WindowStyle Hidden
    Start-Sleep -Seconds 6
} else {
    Write-Host '[1/3] MySQL already running.'
}

Write-Host '[2/3] Starting main server on 9339 / cluster 9876 ...'
Start-Process -FilePath (Join-Path $hash 'app\ClashRoyale.exe') -WorkingDirectory (Join-Path $hash 'app') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $hash 'main-server.log') -RedirectStandardError (Join-Path $hash 'main-server.err.log')

Write-Host '[3/3] Starting battle server (UDP 9449) ...'
$env:DOTNET_ROLL_FORWARD = 'Major'
Start-Process -FilePath (Join-Path $hash 'app_battles\ClashRoyale.Battles.exe') -WorkingDirectory (Join-Path $hash 'app_battles') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $hash 'battle-server.log') -RedirectStandardError (Join-Path $hash 'battle-server.err.log')

Start-Sleep -Seconds 10
Write-Host '--- listening ports ---'
netstat -ano | Select-String -Pattern ':9339|:9876|:9449'
