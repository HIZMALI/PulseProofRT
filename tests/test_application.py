import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from pulseproof import scenario
from pulseproof.analysis import analyze
from pulseproof.evidence import read_summary
from pulseproof.target import ROOT
from pulseproof.application import ManagedService
from pulseproof.cli import main
from test_analysis import fixture,stream

class ApplicationTests(unittest.TestCase):
    def test_failed_baseline_cannot_claim_controlled_regression(self):
        selected,rows=fixture();saved=analyze(stream(rows),selected);saved['verdict']='FAIL'
        with patch('pulseproof.cli.run',return_value=(saved,None)),patch('sys.stderr'):
            self.assertEqual(main(['app-demo']),2)
    def test_cleanup_rejects_reused_pid_and_never_signals_it(self):
        class Target:
            def __init__(self):self.commands=[]
            def ssh(self,command):self.commands.append(command);return '42 /bin/sh -c echo /data/pp-telemetry-abc'
        target=Target();service=ManagedService(target,'baseline');service.pid=42;service.remote='/data/pp-telemetry-abc'
        with self.assertRaisesRegex(RuntimeError,'identity changed'):service.__exit__(None,None,None)
        self.assertFalse(any(c.startswith('kill -TERM') for c in target.commands))

    def test_cleanup_does_not_signal_already_exited_service(self):
        class Target:
            def __init__(self):self.commands=[]
            def ssh(self,command):self.commands.append(command);return ''
        target=Target();service=ManagedService(target,'baseline');service.pid=42;service.remote='/data/pp-telemetry-abc'
        service.__exit__(None,None,None);self.assertEqual(len(target.commands),1)
    def test_two_application_builds_share_policy_and_parameters(self):
        a=scenario.load(ROOT/'scenarios/service-baseline.json');b=scenario.load(ROOT/'scenarios/service-regression.json')
        self.assertEqual(a['parameters'],b['parameters']);self.assertEqual(a['gates'],b['gates'])
        self.assertNotEqual(a['application'],b['application'])

    def test_arbitrary_application_command_is_rejected(self):
        selected=scenario.load(ROOT/'scenarios/service-baseline.json');selected['application']='baseline;shutdown'
        with self.assertRaises(ValueError):scenario.validate(selected)

    def test_wrong_service_build_identity_is_rejected(self):
        selected,rows=fixture();selected['mode']='service';selected['application']='baseline';rows[0].update(mode='service',service_build=2)
        with self.assertRaisesRegex(ValueError,'build identity'):analyze(stream(rows),selected)

    def test_summary_metrics_are_recomputed(self):
        selected,rows=fixture();saved=analyze(stream(rows),selected)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'summary.json';path.write_text(json.dumps(saved),encoding='utf-8')
            self.assertEqual(read_summary(path)['verdict'],'PASS')
            saved['successful_latency']['p99_ns']=1
            path.write_text(json.dumps(saved),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'inconsistent'):read_summary(path)

    def test_raw_digest_failure_rejects_comparison_input(self):
        selected,rows=fixture();saved=analyze(stream(rows),selected);saved['provenance']={'raw_sha256':'bad'}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'summary.json';path.write_text(json.dumps(saved),encoding='utf-8')
            path.with_name('raw.ndjson').write_text(stream(rows),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'SHA-256'):read_summary(path)
