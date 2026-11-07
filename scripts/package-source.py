"""Package only the paths explicitly approved in public-files.json."""
import argparse
import json
import re
from pathlib import Path
from public_policy import write_archive

def main():
    root = Path(__file__).resolve().parent.parent
    version = re.search(r'^version = "([0-9a-z.]+)"', (root / 'pyproject.toml').read_text(), re.M)[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=root / f'artifacts/dist/PulseProofRT-{version}-public-source.zip')
    parser.add_argument('--stage', type=Path, help='Create a new source-only directory without Git history')
    args = parser.parse_args()
    manifest = write_archive(root, args.output, args.stage)
    args.output.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    args.output.with_suffix('.files.txt').write_text('\n'.join(manifest['files']) + '\n', encoding='utf-8')
    print(json.dumps({'archive': str(args.output.resolve()), 'sha256': manifest['sha256'], 'files': len(manifest['files'])}, indent=2))

if __name__ == '__main__':
    main()
