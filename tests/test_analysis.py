import copy
import json
import unittest
import tempfile
from pathlib import Path
from pulseproof.analysis import analyze, compare, percentile
from pulseproof.scenario import validate, load
from pulseproof.target import ROOT, Target
from pulseproof.report import report_html
from pulseproof.jsonio import loads
from pulseproof.runner import atomic_write, csv_text

def fixture():
    """Synthetic test-only data; never presented as QNX acquisition."""
    scenario = load(ROOT / "scenarios/timer-baseline.json")
    scenario["parameters"].update(samples=5, deadline_us=1000)
    scenario["gates"]["p99_success_ns"] = 500
    meta = dict(scenario["parameters"], type="metadata", schema_version=1, source="synthetic",
                os="QNX", release="8.0.0", arch="x86_64", machine="x86pc", clock="CLOCK_MONOTONIC",
                mode="timer", scheduler="SCHED_RR", cpu_count=2, tick_ns=1000000,
                clock_resolution_ns=1000000, clock_read_min_ns=10, cycles_per_second=3500000000,
                started_epoch=1794000000, agent_version="test-fixture", timeout_errno=260)
    samples = [dict(type="sample", sequence=i, latency_ns=(i+1)*100, wake_lateness_ns=0,
                    error=0, timeout=False, injected=False, recovery=False, deadline_miss=False, deadline_unobserved=False) for i in range(5)]
    return scenario, [meta, *samples, dict(type="complete", samples=5, elapsed_ns=10000, process_cpu_ns=5000)]

def stream(rows):
    return "\n".join(json.dumps(row) for row in rows) + "\n"

class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.scenario, self.rows = fixture()

    def result(self):
        return analyze(stream(self.rows), self.scenario)

    def test_nearest_rank(self):
        self.assertEqual(percentile(list(range(1,101)),99),99)
        self.assertEqual(percentile([7],95),7)
        self.assertIsNone(percentile([],99))
        with self.assertRaises(ValueError): percentile([1],0)

    def test_gate_boundary_and_percentiles(self):
        result = self.result()
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["successful_latency"]["p50_ns"],300)
        self.assertEqual(result["successful_latency"]["p99_ns"],500)
        self.assertEqual(result["source"],"synthetic")

    def test_reject_synthetic_as_real(self):
        with self.assertRaisesRegex(ValueError,"Real QNX"):
            analyze(stream(self.rows),self.scenario,require_real=True)

    def test_missing_footer(self):
        with self.assertRaises(ValueError): analyze(stream(self.rows[:-1]),self.scenario)

    def test_truncated_samples(self):
        self.rows.pop(2)
        with self.assertRaises(ValueError): self.result()

    def test_duplicate_sequence(self):
        self.rows[2]["sequence"]=0
        with self.assertRaises(ValueError): self.result()

    def test_negative_latency(self):
        self.rows[1]["latency_ns"]=-1
        with self.assertRaises(ValueError): self.result()

    def test_boolean_not_integer(self):
        self.rows[0]["samples"]=True
        with self.assertRaises(ValueError): self.result()

    def test_configuration_mismatch(self):
        self.rows[0]["priority"]=10
        with self.assertRaises(ValueError): self.result()

    def test_false_deadline_flag(self):
        self.rows[1]["latency_ns"]=1000001
        with self.assertRaises(ValueError): self.result()

    def test_real_deadline_failure(self):
        self.rows[1].update(latency_ns=1000001,deadline_miss=True)
        self.assertEqual(self.result()["verdict"],"FAIL")

    def test_forged_timeout_flag(self):
        self.rows[1].update(error=13,timeout=True,deadline_miss=True)
        with self.assertRaises(ValueError): self.result()

    def test_incorrect_recovery(self):
        self.rows[2]["recovery"]=True
        with self.assertRaises(ValueError): self.result()

    def test_fault_schedule_mismatch(self):
        self.rows[2]["injected"]=True
        with self.assertRaises(ValueError): self.result()

    def test_no_success_cannot_pass_percentile_gate(self):
        self.scenario["mode"]="ipc";self.rows[0]["mode"]="ipc"
        self.scenario["gates"].update(expected_timeouts=5,max_deadline_misses=5)
        for index,row in enumerate(self.rows[1:-1]):
            row.update(error=260,timeout=True,deadline_miss=False,deadline_unobserved=True,recovery=index>0)
        result=self.result()
        self.assertIsNone(result["successful_latency"]["p99_ns"])
        self.assertEqual(result["verdict"],"FAIL")
        self.assertEqual(result["deadline_misses"],0)
        self.assertEqual(result["unobserved_deadlines"],5)

    def test_compare_and_regression(self):
        a=self.result();b=copy.deepcopy(a)
        b["successful_latency"]["p99_ns"]=700
        result=compare(a,b)
        self.assertEqual(result["change_percent"],40)
        self.assertEqual(result["verdict"],"FAIL")

    def test_compare_configuration_rejected(self):
        a=self.result();b=copy.deepcopy(a);b["comparison_signature"]="different"
        with self.assertRaises(ValueError): compare(a,b)

    def test_compare_binary_change_rejected(self):
        a=self.result();b=copy.deepcopy(a);b["provenance"]={"agent_sha256":"changed"}
        with self.assertRaises(ValueError): compare(a,b)

    def test_compare_kernel_build_change_rejected(self):
        a=self.result();b=copy.deepcopy(a);a["target_os"]="QNX build one";b["target_os"]="QNX build two"
        with self.assertRaises(ValueError): compare(a,b)

    def test_report_cannot_close_script_element(self):
        result=self.result();result["scenario"]["description"]="</script><script>alert(1)</script>"
        report=report_html(result)
        self.assertNotIn("</script><script>alert(1)",report)
        self.assertIn("\\u003c/script\\u003e",report)
        self.assertNotIn('src="/app.js"',report)
        self.assertGreater(report.rfind('<script>'),report.index('<body>'))

class InputTests(unittest.TestCase):
    def test_evidence_bytes_preserve_line_endings(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"raw.ndjson"
            atomic_write(path,'{"a":1}\n{"a":2}\n')
            self.assertEqual(path.read_bytes(),b'{"a":1}\n{"a":2}\n')

    def test_csv_has_no_doubled_carriage_returns(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"samples.csv"
            atomic_write(path,csv_text([{"sequence":0,"latency_ns":10}]))
            self.assertNotIn(b'\r\r\n',path.read_bytes())
            self.assertEqual(path.read_bytes().count(b'\r\n'),2)
    def test_all_scenarios_validate(self):
        for file in (ROOT/"scenarios").glob("*.json"): validate(load(file))

    def test_unknown_parameter(self):
        scenario,_=fixture();scenario["parameters"]["command"]="whoami"
        with self.assertRaises(ValueError): validate(scenario)

    def test_shell_characters_in_id(self):
        scenario,_=fixture();scenario["id"]="test;shutdown"
        with self.assertRaises(ValueError): validate(scenario)

    def test_workload_bounded(self):
        scenario,_=fixture();scenario["parameters"].update(samples=10000,work_us=100000,period_us=1)
        with self.assertRaises(ValueError): validate(scenario)

    def test_duplicate_json_keys(self):
        with self.assertRaises(ValueError): loads('{"a":1,"a":2}')

    def test_nonfinite_json(self):
        for word in ["NaN","Infinity","-Infinity"]:
            with self.assertRaises(ValueError): loads('{"a":'+word+'}')

    def test_remote_upload_path_injection(self):
        target=object.__new__(Target)
        with self.assertRaises(ValueError): target.upload("anything","/data/file;shutdown")

    def test_public_target_rejected(self):
        with self.assertRaises(ValueError): Target(address="8.8.8.8")

if __name__ == "__main__": unittest.main()
