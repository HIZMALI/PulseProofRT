param([switch]$Target)
$ErrorActionPreference = 'Stop'
Push-Location ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')))
try {
    python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Host regression tests failed.' }
    node --check pulseproof/web/app.js
    if ($LASTEXITCODE -ne 0) { throw 'Browser JavaScript syntax check failed.' }
    if ($Target) {
        python scripts/verify-target.py
        if ($LASTEXITCODE -ne 0) { throw 'Real QNX integration verification failed.' }
    }
} finally { Pop-Location }
