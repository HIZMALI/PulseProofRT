$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
New-Item -ItemType Directory -Force "$root/artifacts/evidence" | Out-Null
if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 8765 is already in use. Use the existing workbench or choose another CLI port.'
}
$python = (Get-Command python.exe).Source
$process = Start-Process -FilePath $python -WindowStyle Hidden -PassThru -WorkingDirectory $root -ArgumentList '-m pulseproof serve' -RedirectStandardOutput "$root/artifacts/evidence/workbench-server.log" -RedirectStandardError "$root/artifacts/evidence/workbench-server-errors.log"
$process.Id | Set-Content "$root/artifacts/evidence/workbench-server.pid"
Write-Output 'http://127.0.0.1:8765'
