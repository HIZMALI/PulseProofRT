"""Check the working source tree or Git index against the explicit public policy."""
import argparse
import subprocess
from pathlib import Path
from public_policy import approved_files, inspect_files, validate_paths, working_files

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--git', action='store_true', help='Check tracked paths, as used by CI')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    names = approved_files(root)
    actual = (subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().strip('\0').split('\0')
              if args.git else working_files(root))
    validate_paths(names, actual)
    inspect_files(root, names)
    print(f'Public policy verified: {len(names)} files.')

if __name__ == '__main__':
    main()
