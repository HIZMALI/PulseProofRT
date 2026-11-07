param([switch]$PowerOffAfterShutdown)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$vmx = Join-Path $root 'artifacts/vm/local/vmware_files/vmware.vmx'
Push-Location $root
try {
    # Request an orderly QNX shutdown first. SSH disconnect during shutdown is expected.
    python scripts/shutdown-target.py
    if ($LASTEXITCODE -ne 0) { throw 'Orderly shutdown was not confirmed; refusing to power off.' }
    # SSH closure confirms the shutdown request, not a completed kernel/filesystem halt.
    if ($PowerOffAfterShutdown) {
        & 'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe' -T ws stop $vmx hard
        if ($LASTEXITCODE -ne 0) { throw 'VM power-off failed.' }
    } else { Write-Output 'Orderly shutdown requested. VM power remains on; inspect the console before power removal.' }
} finally { Pop-Location }
