$ErrorActionPreference = 'Stop'
$os = Get-CimInstance Win32_OperatingSystem
$system = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$vmware = 'C:\Program Files (x86)\VMware\VMware Workstation\vmware.exe'
[ordered]@{
    host_os = $os.Caption
    host_version = $os.Version
    host_build = $os.BuildNumber
    cpu_model = $cpu.Name.Trim()
    logical_cpus = $cpu.NumberOfLogicalProcessors
    physical_ram_bytes = $system.TotalPhysicalMemory
    windows_hypervisor_present = $system.HypervisorPresent
    vmware_version = (Get-Item -LiteralPath $vmware).VersionInfo.ProductVersion
} | ConvertTo-Json -Compress
