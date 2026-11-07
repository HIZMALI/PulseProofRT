$ErrorActionPreference = 'Stop'
$vmrun = 'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'
$vmx = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../artifacts/vm/local/vmware_files/vmware.vmx'))
$running = & $vmrun -T ws list
if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect VMware state; refusing to overwrite disks.' }
if ($running -contains $vmx) { throw 'Target is running. Shut it down before rebuilding its image.' }
