$ErrorActionPreference = 'Stop'
$vmx = Join-Path $PSScriptRoot '../artifacts/vm/local/vmware_files/vmware.vmx'
$text = Get-Content -Raw -LiteralPath $vmx
$text = $text -replace 'vhv.enable = "TRUE"', 'vhv.enable = "FALSE"'
$text = $text -replace 'mks.enable3d = "TRUE"', 'mks.enable3d = "FALSE"'
$text = $text -replace 'memsize = "1024"', 'memsize = "2048"'
[IO.File]::WriteAllText([IO.Path]::GetFullPath($vmx), $text, [Text.UTF8Encoding]::new($false))
