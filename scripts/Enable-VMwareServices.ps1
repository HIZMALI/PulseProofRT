$ErrorActionPreference = 'Stop'
# The only elevated operations: start existing VMware services. No configuration changes.
$result = foreach ($name in @('VMAuthdService', 'VMnetDHCP', 'VMware NAT Service')) {
    try {
        Start-Service -Name $name -ErrorAction Stop
        Get-Service -Name $name | Select-Object Name, Status
    } catch {
        [pscustomobject]@{ Name = $name; Status = $_.Exception.Message }
    }
}
$result | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $PSScriptRoot '../artifacts/evidence/vmware-services.json')
if (Get-Service VMAuthdService,VMnetDHCP,'VMware NAT Service' | Where-Object Status -NE 'Running') { exit 1 }
