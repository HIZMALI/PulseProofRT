"""Recompute imported summaries; verify the original raw bytes when present."""
import hashlib
import json
from pathlib import Path
from .analysis import analyze
from .jsonio import loads
from .scenario import validate

def read_summary(path):
    path=Path(path)
    saved=loads(path.read_text(encoding='utf-8'))
    if not isinstance(saved,dict): raise ValueError('Summary must be an object')
    selected=validate(saved['scenario'])
    raw_file=path.with_name('raw.ndjson')
    if raw_file.is_file():
        raw=raw_file.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=saved.get('provenance',{}).get('raw_sha256'):
            raise ValueError('Raw evidence SHA-256 does not match summary')
        stream=raw.decode('utf-8')
    else:
        stream='\n'.join(json.dumps(item) for item in [saved['metadata'],*saved['samples'],saved['completion']])+'\n'
    calculated=analyze(stream,selected,require_real=saved.get('source')=='qnx-native')
    for key,value in calculated.items():
        if saved.get(key)!=value:
            raise ValueError(f'Summary is inconsistent with its evidence: {key}')
    return saved
