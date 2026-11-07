import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock
from scripts.public_policy import approved_files, validate_paths, write_archive
from pulseproof.evidence import read_summary
from pulseproof.runner import csv_text
from pulseproof.target import ROOT, Target

class PackagingTests(unittest.TestCase):
    def fixture(self, root):
        names = ['LICENSE', 'README.md', 'public-files.json']
        (root / 'LICENSE').write_text('MIT License', encoding='utf-8')
        (root / 'README.md').write_text('Test source fixture.', encoding='utf-8')
        (root / 'public-files.json').write_text(json.dumps({'schema_version': 1, 'files': names}), encoding='utf-8')
        return names

    def test_unlisted_internal_documents_never_enter_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); names = self.fixture(root)
            (root / 'AGENTS.md').write_text('Private fixture', encoding='utf-8')
            (root / 'docs').mkdir()
            (root / 'docs' / 'future-notes.md').write_text('Private fixture', encoding='utf-8')
            output = root / 'source.zip'; write_archive(root, output)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(sorted(archive.namelist()), ['PulseProofRT/' + x for x in names])

    def test_tracked_unknown_file_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unapproved'):
            validate_paths(['README.md'], ['README.md', 'AGENTS.md'])

    def test_manifest_rejects_private_and_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); self.fixture(root)
            for name in ('AGENTS.md', 'docs/PROGRESS.md', '../outside', 'C:/outside', 'x\\secret'):
                names = sorted(['LICENSE', 'README.md', 'public-files.json', name])
                (root / 'public-files.json').write_text(json.dumps({'schema_version': 1, 'files': names}), encoding='utf-8')
                with self.subTest(name=name), self.assertRaises(ValueError): approved_files(root)

    def test_missing_approved_file_prevents_partial_export(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); self.fixture(root); (root / 'LICENSE').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing'):
                write_archive(root, root / 'source.zip')
            self.assertFalse((root / 'source.zip').exists())

    def test_secret_in_approved_file_prevents_export(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); self.fixture(root)
            (root / 'README.md').write_text('-----BEGIN' + ' OPENSSH PRIVATE KEY-----', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'private key'):
                write_archive(root, root / 'source.zip')

    def test_all_retained_measurements_match_raw_and_csv(self):
        names = [x for x in approved_files(ROOT) if x.endswith('/summary.json')]
        self.assertGreaterEqual(len(names), 13)
        for name in names:
            path = ROOT / name
            saved = read_summary(path)
            self.assertEqual(path.with_name('samples.csv').read_bytes(), csv_text(saved['samples']).encode())

    def test_hello_defaults_to_built_workspace_example(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'build').mkdir()
            binary = root / 'build/hello'; binary.write_bytes(b'synthetic executable fixture')
            target = object.__new__(Target); target.root = root
            target.upload = Mock(); target.ssh = Mock(return_value='Hello from QNX SDP 8.0!\n')
            target.status = Mock(return_value={'os': 'synthetic fixture'})
            result = target.hello()
            self.assertEqual(target.upload.call_args.args[0], binary)
            self.assertEqual(result['exit_code'], 0)
