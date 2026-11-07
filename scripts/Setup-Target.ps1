param([switch]$Rebuild)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$vmrun = 'C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe'
$vmx = Join-Path $root 'artifacts/vm/local/vmware_files/vmware.vmx'
if (!(Test-Path -LiteralPath $vmrun)) { throw 'VMware Workstation is not installed at the verified path.' }
New-Item -ItemType Directory -Force "$root/artifacts/ssh", "$root/artifacts/vm", "$root/artifacts/evidence" | Out-Null
$services = Get-Service VMAuthdService,VMnetDHCP,'VMware NAT Service'
if ($services | Where-Object Status -NE 'Running') {
    # Windows presents UAC to the user. Never accept it through automation.
    $p = Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -PassThru -Wait -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSScriptRoot/Enable-VMwareServices.ps1`""
    if ($p.ExitCode -ne 0) { throw 'VMware service startup failed.' }
}
$key = Join-Path $root 'artifacts/ssh/target_ed25519'
if (!(Test-Path -LiteralPath $key)) {
    python -c "import subprocess,sys; subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-C','pulseproof-local-target','-f',sys.argv[1]],check=True)" $key
    if ($LASTEXITCODE -ne 0) { throw 'SSH key generation failed.' }
}
$running = & $vmrun -T ws list
if ($LASTEXITCODE -ne 0) { throw 'vmrun inventory failed.' }
if ($Rebuild -and ($running -contains $vmx)) { throw 'Refusing to rebuild a running VM. Shut down the QNX target first.' }
if ($Rebuild -or !(Test-Path -LiteralPath $vmx)) {
    & "$PSScriptRoot/build-target.cmd" *> "$root/artifacts/evidence/image-build.log"
    if ($LASTEXITCODE -ne 0) { throw 'Image build failed; see artifacts/evidence/image-build.log.' }
}
if (!($running -contains $vmx)) {
    & "$PSScriptRoot/Configure-VM.ps1"
    & $vmrun -T ws start $vmx nogui
    if ($LASTEXITCODE -ne 0) { throw 'VMware start failed.' }
}
# Renew only the existing VMware NAT adapter; do not touch physical networking.
ipconfig.exe /renew 'VMware Network Adapter VMnet8' | Out-Null
Push-Location $root
try {
    for ($attempt=0; $attempt -lt 30; $attempt++) {
        python -m pulseproof target status 2>$null
        if ($LASTEXITCODE -eq 0) { exit 0 }
        Start-Sleep -Seconds 1
    }
    throw 'QNX target did not become reachable; inspect the serial console log.'
} finally { Pop-Location }
