import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from pulseproof.analysis import analyze, compare
from pulseproof.locking import acquisition_lock
from pulseproof.runner import history
from pulseproof.target import ROOT,latest_lease
from test_analysis import fixture, stream

class AuditTests(unittest.TestCase):
    def test_compacted_leases_are_selected_by_time_not_file_order(self):
        leases='lease 192.168.1.129 { starts 6 2026/11/07 20:38:23; hardware ethernet aa:bb:cc:dd:ee:ff; }\nlease 192.168.1.128 { starts 6 2026/11/07 19:32:54; hardware ethernet aa:bb:cc:dd:ee:ff; }'
        self.assertEqual(latest_lease(leases,'aa:bb:cc:dd:ee:ff'),'192.168.1.129')
        with self.assertRaises(ValueError):latest_lease(leases,'ff:ff:ff:ff:ff:ff')
    def test_changed_policy_is_not_comparable(self):
        scenario,rows=fixture();a=analyze(stream(rows),scenario);b=copy.deepcopy(a)
        b['scenario']['gates']['max_deadline_misses']=999
        with self.assertRaisesRegex(ValueError,'policy'): compare(a,b)

    def test_compare_rejects_nonfinite_limit(self):
        scenario,rows=fixture();a=analyze(stream(rows),scenario)
        for limit in (float('nan'),float('inf'),-1,True):
            with self.assertRaises(ValueError): compare(a,a,limit)

    def test_process_lock_excludes_other_process_and_releases(self):
        with tempfile.TemporaryDirectory() as folder:
            code="from pulseproof.locking import acquisition_lock; import sys;\nwith acquisition_lock(sys.argv[1]): print('acquired')"
            with acquisition_lock(folder):
                result=subprocess.run([sys.executable,'-c',code,folder],cwd=ROOT,capture_output=True,text=True,timeout=5)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('Another experiment',result.stderr)
            result=subprocess.run([sys.executable,'-c',code,folder],cwd=ROOT,capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0)

    def test_corrupt_history_cannot_break_workbench(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'artifacts/runs/bad';p.mkdir(parents=True)
            for data in ('[]','null','{"scenario":null}','{broken'):
                (p/'summary.json').write_text(data,encoding='utf-8')
                self.assertEqual(history(folder),[])

    def test_preserved_mvp_examples_are_consistent(self):
        for path in (ROOT/'examples/real').glob('*/summary.json'):
            saved=json.loads(path.read_text(encoding='utf-8'));raw=path.with_name('raw.ndjson').read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),saved['provenance']['raw_sha256'])
            actual=analyze(raw.decode('utf-8'),saved['scenario'],require_real=True)
            for field in ('verdict','successful_latency','deadline_misses','timeouts','recoveries','comparison_signature'):
                self.assertEqual(saved[field],actual[field])

    def test_git_archive_preserves_raw_evidence(self):
        # Attributes themselves are regression checked; a real clean checkout is verified separately.
        attrs=(ROOT/'.gitattributes').read_text(encoding='utf-8')
        self.assertIn('*.ndjson -text',attrs)
        self.assertIn('*.csv -text',attrs)
