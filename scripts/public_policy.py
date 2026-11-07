"""Explicit source-distribution policy shared by packaging and repository checks."""
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

PRIVATE_NAMES = {
    'agents.md', 'progress.md', 'audit.md', 'devpost.md', 'demo.md',
    'submission_plan.md', 'submission_matrix.md', 'ci_review.md',
    'competitive.md', 'validation_rc.md',
}
GENERATED = {'.git', '.venv', 'artifacts', 'build', 'dist', 'node_modules', '__pycache__'}
SECRET_PATTERNS = {
    'private key': rb'-----BEGIN (?:OPENSSH |RSA |EC |DSA |ENCRYPTED )?PRIVATE KEY-----',
    'access token': rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16})',
    'API key': rb'sk-[A-Za-z0-9]{32,}',
    'personal profile path': rb'(?i)(?:[A-Z]:[\\/]Users[\\/][A-Za-z0-9_.-]+|/home/[A-Za-z0-9_.-]+|/Users/[A-Za-z0-9_.-]+)',
}

def approved_files(root):
    root = Path(root).resolve()
    policy = json.loads((root / 'public-files.json').read_text(encoding='utf-8'))
    names = policy.get('files')
    if set(policy) != {'schema_version', 'files'} or policy['schema_version'] != 1:
        raise ValueError('Unsupported public file policy')
    if not isinstance(names, list) or not all(isinstance(x, str) for x in names):
        raise ValueError('Public file policy must contain a list of paths')
    if names != sorted(set(names)) or 'public-files.json' not in names:
        raise ValueError('Public paths must be sorted, unique and include the policy')
    for name in names:
        path = PurePosixPath(name)
        if not re.fullmatch(r'[A-Za-z0-9_./-]+', name) or path.is_absolute() or '..' in path.parts or str(path) != name:
            raise ValueError('Unsafe public path: ' + name)
        if any(x.lower() in PRIVATE_NAMES for x in path.parts) or any(x in GENERATED for x in path.parts):
            raise ValueError('Private or generated path in public policy: ' + name)
        file = root / name
        if file.is_symlink() or not file.resolve().is_relative_to(root) or not file.is_file():
            raise ValueError('Missing or unsafe approved file: ' + name)
    return names

def validate_paths(approved, actual):
    missing = sorted(set(approved) - set(actual))
    extra = sorted(set(actual) - set(approved))
    if missing or extra:
        raise ValueError(f'Public file set differs: missing={missing}, unapproved={extra}')

def inspect_files(root, names):
    account = os.environ.get('USERNAME', '').encode()
    for name in names:
        data = (Path(root) / name).read_bytes()
        if data.startswith((b'\x7fELF', b'MZ', b'KDMV')):
            raise ValueError('Compiled/runtime file in source: ' + name)
        if name.endswith(('.jpg', '.png')):
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if re.search(pattern, data):
                raise ValueError(f'{label} detected in {name}')
        if len(account) >= 4 and account.lower() in data.lower():
            raise ValueError('Local account name detected in ' + name)

def working_files(root):
    root = Path(root)
    found = []
    for parent, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in GENERATED and not x.endswith('.egg-info')]
        for name in files:
            if not name.endswith('.pyc'):
                found.append((Path(parent) / name).relative_to(root).as_posix())
    return found

def write_archive(root, output, stage=None):
    root, output = Path(root).resolve(), Path(output).resolve()
    names = approved_files(root)
    inspect_files(root, names)
    if output.exists() or (stage is not None and Path(stage).exists()):
        raise ValueError('Output already exists; choose a new path')
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(suffix='.zip', dir=output.parent)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in names:
                archive.write(root / name, 'PulseProofRT/' + name)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ValueError('Source ZIP CRC failed')
            validate_paths(names, [x.removeprefix('PulseProofRT/') for x in archive.namelist()])
        os.replace(temporary, output)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()
    if stage is not None:
        stage = Path(stage).resolve()
        stage.mkdir(parents=True, exist_ok=False)
        for name in names:
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, target)
        validate_paths(names, working_files(stage))
    return {'archive': output.name, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
            'files': {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}}
