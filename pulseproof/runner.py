"""A run is published to history only after a complete, validated acquisition."""
import csv
import hashlib
import io
import json
import os
import uuid
import contextlib
from datetime import datetime, timezone
from pathlib import Path
from .analysis import analyze
from .scenario import arguments
from .target import Target, ROOT
from .locking import acquisition_lock

def csv_text(samples):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(samples[0]))
    writer.writeheader()
    writer.writerows(samples)
    return buffer.getvalue()

def atomic_write(path, content):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as stream:
        stream.write(content)
    os.replace(temp, path)

def run(scenario, workspace=ROOT, address=None):
    with acquisition_lock(workspace):
        return _acquire(scenario,workspace,address)

def _acquire(scenario, workspace=ROOT, address=None):
    root = Path(workspace)
    target = Target(root, address)
    status = target.status()
    environment = target.environment()
    agent_hash = target.deploy_agent()
    from .application import ManagedService
    service=ManagedService(target,scenario['application']) if scenario['mode']=='service' else contextlib.nullcontext(None)
    with service as application:
        prefix=('PP_SERVICE_INSTANCE='+application['instance']+' ') if application else ''
        raw = target.ssh(prefix+"/data/pp-agent " + " ".join(arguments(scenario)), timeout=90)
    summary = analyze(raw, scenario, require_real=True)
    if summary["metadata"].get("arch") != "x86_64":
        raise ValueError("Expected x86_64 build metadata")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    summary.update(run_id=run_id, created_at=datetime.now(timezone.utc).isoformat(),
                   provenance={"agent_sha256": agent_hash, "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                               "scenario_sha256": hashlib.sha256(json.dumps(scenario, sort_keys=True).encode()).hexdigest(),
                               "transport": "SSH, image-pinned Ed25519 host key",
                               "target_environment": environment,
                               "build_manifest": json.loads((root / "build/manifest.json").read_text(encoding="utf-8"))})
    # Exclude private connection addresses and credentials from exportable results.
    summary["target_os"] = status["os"]
    if application: summary['provenance']['application']=application
    folder = root / "artifacts/runs" / run_id
    folder.mkdir(parents=True, exist_ok=False)
    atomic_write(folder / "raw.ndjson", raw)
    atomic_write(folder / "samples.csv", csv_text(summary["samples"]))
    from .report import report_html
    atomic_write(folder / "report.html", report_html(summary))
    atomic_write(folder / "summary.json", json.dumps(summary, indent=2))
    return summary, folder

def history(workspace=ROOT):
    runs = []
    for path in sorted((Path(workspace) / "artifacts/runs").glob("*/summary.json"), reverse=True):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(item,dict) or not isinstance(item.get("scenario"),dict) or not isinstance(item.get("metadata"),dict):
                continue
            if item.get("run_id")!=path.parent.name or item.get("verdict") not in ("PASS","FAIL"):
                continue
            runs.append({k: v for k, v in item.items() if k != "samples"})
        except (ValueError, OSError):
            continue
    return runs
