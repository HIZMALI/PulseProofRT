"""Install and cross-build an approved source ZIP in a fresh Windows directory."""
import argparse
import hashlib
import json
import subprocess
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from public_policy import approved_files, inspect_files, validate_paths

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('archive', type=Path)
archive = parser.parse_args().archive.resolve()
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:6]
destination = ROOT / 'artifacts/cleanroom' / ('Source With Spaces ' + stamp)
destination.mkdir(parents=True, exist_ok=False)
checks = []

def command(name, arguments, cwd):
    result = subprocess.run([str(x) for x in arguments], cwd=cwd, capture_output=True, text=True, timeout=180)
    checks.append({'name': name, 'pass': result.returncode == 0, 'exit_code': result.returncode,
                   'stdout': result.stdout, 'stderr': result.stderr})
    print(('PASS ' if result.returncode == 0 else 'FAIL ') + name, flush=True)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)

try:
    approved = approved_files(ROOT)
    with zipfile.ZipFile(archive) as source_zip:
        names = source_zip.namelist()
        if len(names) != len(set(names)) or any(not x.startswith('PulseProofRT/') for x in names):
            raise ValueError('Invalid source ZIP paths')
        validate_paths(approved, [x.removeprefix('PulseProofRT/') for x in names])
        if source_zip.testzip() is not None:
            raise ValueError('Source ZIP CRC failed')
        source_zip.extractall(destination)
    source = destination / 'PulseProofRT'
    inspect_files(source, approved)
    venv = destination / 'venv'
    python = venv / 'Scripts/python.exe'
    command('create isolated venv', [sys.executable, '-m', 'venv', venv], destination)
    command('install build dependency', [python, '-m', 'pip', '--disable-pip-version-check', 'install', '--index-url', 'https://pypi.org/simple', 'setuptools>=77'], source)
    command('install source', [python, '-m', 'pip', '--disable-pip-version-check', 'install', '--no-build-isolation', '--no-deps', '-e', '.'], source)
    command('host tests', [python, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], source)
    command('installed CLI', [venv / 'Scripts/pulseproof.exe', '--help'], source)
    command('QNX agent and examples', [python, '-m', 'pulseproof', '--workspace', source, 'build'], source)
    command('JavaScript syntax', ['node', '--check', 'pulseproof/web/app.js'], source)
    command('public source policy', [python, 'scripts/check-public-files.py'], source)
    code = "from pathlib import Path;from pulseproof.evidence import read_summary;from pulseproof.runner import csv_text;p=list(Path('examples').glob('*/*/summary.json'));assert len(p)>=13;[(read_summary(x),None if x.with_name('samples.csv').read_bytes()==csv_text(read_summary(x)['samples']).encode() else (_ for _ in ()).throw(ValueError('CSV mismatch'))) for x in p];print(str(len(p))+' actual evidence sets verified')"
    command('retained measurements', [python, '-c', code], source)
finally:
    report = {'archive': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
              'source_directory': str(destination / 'PulseProofRT'), 'checks': checks,
              'pass': len(checks) == 9 and all(x['pass'] for x in checks)}
    log = ROOT / 'artifacts/evidence' / ('source-package-' + stamp + '.json')
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Evidence: ' + str(log), flush=True)
if not report['pass']:
    raise SystemExit(1)
