# One-click start: MySQL + main server + battle server, then install & launch the game on a connected Android phone.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$hash = Join-Path $root 'HashRoyale'
$mysqlDir = Join-Path $env:USERPROFILE 'cr-tools\mysql'
$mysqlData = Join-Path $env:USERPROFILE 'cr-tools\mysql-data'
$apk = Join-Path $root 'clients\retroroyale-1.9.2-phone.apk'
$pkg = 'com.retrocell.clashroyale'

$adbCandidates = @(
    (Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'),
    (Join-Path $env:USERPROFILE 'AppData\Local\Android\Sdk\platform-tools\adb.exe'),
    (Join-Path $env:USERPROFILE 'cr-tools\platform-tools\adb.exe')
)
$adb = $null
foreach ($c in $adbCandidates) { if (Test-Path $c) { $adb = $c; break } }
if (-not $adb) {
    $cmd = Get-Command adb -ErrorAction SilentlyContinue
    if ($cmd) { $adb = $cmd.Source }
}

function Is-Listening([int]$port, [string]$proto = 'TCP') {
    if ($proto -eq 'UDP') {
        return [bool](Get-NetUDPEndpoint -LocalPort $port -ErrorAction SilentlyContinue)
    }
    return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

Write-Host '[1/4] MySQL ...'
if (-not (Get-Process mysqld -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath (Join-Path $mysqlDir 'bin\mysqld.exe') -ArgumentList @('--no-defaults', "--basedir=$mysqlDir", "--datadir=$mysqlData", '--port=3306') -WindowStyle Hidden
    Start-Sleep -Seconds 6
} else { Write-Host '  already running.' }

Write-Host '[2/4] Main server (TCP 9339 / 9876) ...'
if (-not (Is-Listening 9339)) {
    Start-Process -FilePath (Join-Path $hash 'app\ClashRoyale.exe') -WorkingDirectory (Join-Path $hash 'app') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $hash 'main-server.log') -RedirectStandardError (Join-Path $hash 'main-server.err.log')
    Start-Sleep -Seconds 12
} else { Write-Host '  already listening.' }

Write-Host '[3/4] Battle server (UDP 9449) ...'
if (-not (Is-Listening 9449 'UDP')) {
    $env:DOTNET_ROLL_FORWARD = 'Major'
    Start-Process -FilePath (Join-Path $hash 'app_battles\ClashRoyale.Battles.exe') -WorkingDirectory (Join-Path $hash 'app_battles') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $hash 'battle-server.log') -RedirectStandardError (Join-Path $hash 'battle-server.err.log')
    Start-Sleep -Seconds 8
} else { Write-Host '  already listening.' }

Write-Host '[3b/4] Matchmaking bot ...'
$botProc = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -gt (Get-Date).AddMinutes(-2) }
if (-not $botProc) {
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $py) { $py = 'python' }
    Start-Process -FilePath $py -ArgumentList @((Join-Path $root 'tools\cr_bot.py')) -WindowStyle Hidden -RedirectStandardOutput (Join-Path $root 'tools\cr_bot.log') -RedirectStandardError (Join-Path $root 'tools\cr_bot.err.log')
    Write-Host "  bot started via $py (always searching for 1v1 opponents)."
} else { Write-Host '  bot already running.' }

Write-Host ''
Write-Host '--- Server ports ---'
netstat -ano | Select-String -Pattern ':9339|:9876|:9449'

Write-Host ''
Write-Host '--- Firewall (TCP 9339) ---'
try {
    $null = netsh advfirewall firewall show rule name="HashRoyale 9339" 2>$null
    if ($LASTEXITCODE -ne 0) {
        $null = netsh advfirewall firewall add rule name="HashRoyale 9339" dir=in action=allow protocol=TCP localport=9339
        if ($LASTEXITCODE -eq 0) { Write-Host '  Firewall rule added for TCP 9339.' }
        else { Write-Host '  Firewall rule NOT added (needs admin). If the phone cannot connect, right-click this bat and Run as administrator once.' }
    } else { Write-Host '  Firewall rule already exists.' }

    $null = netsh advfirewall firewall show rule name="HashRoyale 9449" 2>$null
    if ($LASTEXITCODE -ne 0) {
        $null = netsh advfirewall firewall add rule name="HashRoyale 9449" dir=in action=allow protocol=UDP localport=9449
        if ($LASTEXITCODE -eq 0) { Write-Host '  Firewall rule added for UDP 9449 (battle server).' }
    }
} catch { Write-Host '  Firewall check skipped.' }

Write-Host ''
if (-not $adb) {
    Write-Host '[4/4] adb not found. Install Android platform-tools, then run again.'
} else {
    $devs = & $adb devices | Select-String -Pattern '^\S+\s+device$'
    if (-not $devs) {
        Write-Host '[4/4] No phone detected. Connect the phone via USB, enable USB debugging, then run again.'
        Write-Host "  adb path: $adb"
    } else {
        Write-Host '[4/4] Phone detected, installing patched APK ...'
        $installJob = Start-Job -ScriptBlock {
            param($adbPath, $apkPath)
            & $adbPath install -r --bypass-low-target-sdk-block $apkPath 2>&1 | Out-String
        } -ArgumentList $adb, $apk
        # MIUI/HyperOS shows a "USB安装提示" confirmation dialog; tap 继续安装 when it appears.
        for ($i = 0; $i -lt 12; $i++) {
            Start-Sleep -Seconds 2
            $dump = & $adb shell uiautomator dump /sdcard/ui_install.xml 2>$null
            $xml = & $adb shell cat /sdcard/ui_install.xml 2>$null
            $m = [regex]::Match($xml, 'text="继续安装"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')
            if ($m.Success) {
                $tx = [int](($m.Groups[1].Value + $m.Groups[3].Value) / 2)
                $ty = [int](($m.Groups[2].Value + $m.Groups[4].Value) / 2)
                Write-Host "  Tapping '继续安装' at $tx,$ty ..."
                & $adb shell input tap $tx $ty
                break
            }
        }
        $installOut = Receive-Job $installJob
        Remove-Job $installJob -Force -ErrorAction SilentlyContinue
        if ($installOut -match 'Success') {
            Write-Host '  Install OK. Launching Clash Royale ...'
            & $adb shell monkey -p $pkg -c android.intent.category.LAUNCHER 1
        } else {
            Write-Host "  Install may have failed: $installOut"
        }
    }
}

Write-Host ''
Write-Host 'Done. Server address baked into the APK: 192.168.3.65:9339'
Write-Host "Client package: $pkg (RetroRoyale patched 1.9.2)"
Write-Host 'Requirements: phone on the same Wi-Fi as the PC; allow the firewall prompt if shown.'
