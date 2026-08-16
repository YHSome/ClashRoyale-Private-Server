# 停止 HashRoyale 私服进程（保留 MySQL）
Get-Process | Where-Object { $_.ProcessName -match '^ClashRoyale' } | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host 'Servers stopped. MySQL is still running on 3306.'
