import argparse
import json
import math
import sys
from pathlib import Path
from . import scenario
from .analysis import analyze, compare
from .runner import run, atomic_write
from .target import ROOT, Target, execute
from .evidence import read_summary

def main(argv=None):
    parser = argparse.ArgumentParser(prog="pulseproof", description="QNX 8 timing and IPC evidence gates")
    parser.add_argument("--workspace", type=Path, default=ROOT)
    parser.add_argument("--target", help="Override discovered private IPv4 address")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="Cross-compile QNX native agent")
    sub.add_parser('app-demo',help='Run the normal and regressed independent application with the same policy; expected exit 1')
    target = sub.add_parser("target").add_subparsers(dest="action", required=True)
    target.add_parser("status")
    hello = target.add_parser("hello")
    hello.add_argument("--binary", type=Path)
    runner = sub.add_parser("run")
    runner.add_argument("scenario", type=Path)
    analyzer = sub.add_parser("analyze")
    analyzer.add_argument("raw", type=Path)
    analyzer.add_argument("scenario", type=Path)
    analyzer.add_argument("--output", type=Path)
    comparison = sub.add_parser("compare")
    comparison.add_argument("baseline", type=Path)
    comparison.add_argument("candidate", type=Path)
    comparison.add_argument("--max-regression-percent", type=float, default=20)
    server = sub.add_parser("serve")
    server.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            print(execute(["cmd.exe", "/d", "/c", str(args.workspace / "scripts/build-agent.cmd")]))
            print("QNX x86_64 agent built with warnings treated as errors.")
            return 0
        if args.command=='app-demo':
            baseline,_=run(scenario.load(args.workspace/'scenarios/service-baseline.json'),args.workspace,args.target)
            candidate,_=run(scenario.load(args.workspace/'scenarios/service-regression.json'),args.workspace,args.target)
            if baseline['verdict']!='PASS':
                raise ValueError('Application baseline failed its policy; investigate it before claiming a controlled regression')
            result=compare(baseline,candidate)
            result.update(baseline_run=baseline['run_id'],candidate_run=candidate['run_id'],baseline_verdict=baseline['verdict'],candidate_verdict=candidate['verdict'])
            atomic_write(args.workspace/'artifacts/evidence/application-workflow.json',json.dumps(result,indent=2))
        elif args.command == "target":
            target = Target(args.workspace, args.target)
            result = target.status() if args.action == "status" else target.hello(args.binary)
        elif args.command == "run":
            result, folder = run(scenario.load(args.scenario), args.workspace, args.target)
            print(f"Evidence: {folder}")
            print(f"{result['verdict']} | {result['scenario']['id']} | p99 successful={result['successful_latency']['p99_ns']} ns | deadline misses={result['deadline_misses']} | timeouts={result['timeouts']} | recoveries={result['recoveries']}")
            return 0 if result["verdict"] == "PASS" else 1
        elif args.command == "analyze":
            result = analyze(args.raw.read_text(encoding="utf-8"), scenario.load(args.scenario))
            if args.output:
                atomic_write(args.output, json.dumps(result, indent=2))
        elif args.command == "compare":
            if not math.isfinite(args.max_regression_percent) or args.max_regression_percent < 0:
                raise ValueError("Regression limit must be finite and nonnegative")
            result = compare(read_summary(args.baseline), read_summary(args.candidate), args.max_regression_percent)
        else:
            if not 1024 <= args.port <= 65535:
                raise ValueError("Port must be between 1024 and 65535")
            from .server import serve
            serve(args.workspace, args.port)
            return 0
        print(json.dumps(result, indent=2))
        return 0 if result.get("verdict", "PASS") == "PASS" else 1
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
