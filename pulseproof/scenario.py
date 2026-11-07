"""Strict, versioned scenarios; remote shell arguments are never free-form."""
import re
from pathlib import Path
from .jsonio import loads

BOUNDS = {
    "samples": (1, 10000), "period_us": (1, 1000000),
    "deadline_us": (1, 1000000), "work_us": (0, 100000),
    "load_threads": (0, 8), "fault_every": (0, 10000),
    "fault_delay_us": (0, 100000), "timeout_us": (1, 1000000),
    "priority": (1, 50),
}
GATES = {"p99_success_ns", "max_deadline_misses", "expected_timeouts", "min_recoveries"}

def integer(value, label, minimum=0, maximum=60_000_000_000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{label}: expected integer in [{minimum}, {maximum}]")
    return value

def validate(data):
    fields={"schema_version", "id", "description", "mode", "parameters", "gates"}
    if isinstance(data,dict) and data.get('mode')=='service': fields.add('application')
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError("Scenario fields do not match schema version 1")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("Unsupported scenario schema")
    if not isinstance(data["id"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", data["id"]):
        raise ValueError("Invalid scenario id")
    if not isinstance(data["description"], str) or len(data["description"]) > 1000:
        raise ValueError("Invalid scenario description")
    if data["mode"] not in ("timer", "ipc", "service"):
        raise ValueError("Mode must be timer, ipc or service")
    if data['mode']=='service' and data['application'] not in ('baseline','regressed'):
        raise ValueError('Only built-in telemetry service variants are allowed')
    p, g = data["parameters"], data["gates"]
    if not isinstance(p, dict) or set(p) != set(BOUNDS):
        raise ValueError("Missing or unknown scenario parameters")
    for key, bounds in BOUNDS.items():
        integer(p[key], key, *bounds)
    if p["samples"] * p["period_us"] > 30_000_000:
        raise ValueError("Nominal timer duration exceeds 30 seconds")
    planned_work = p["samples"] * max(p["period_us"] if data["mode"] == "timer" else 0, p["work_us"])
    planned_work += (p["samples"] // p["fault_every"] if p["fault_every"] else 0) * p["fault_delay_us"]
    if planned_work > 30_000_000:
        raise ValueError("Planned workload exceeds 30 seconds")
    if p["fault_every"] == 1:
        raise ValueError("Fault interval must leave space for recovery")
    if not isinstance(g, dict) or set(g) != GATES:
        raise ValueError("Missing or unknown gate")
    for key in GATES:
        integer(g[key], key, 1 if key == "p99_success_ns" else 0)
    if data["mode"] == "timer" and (g["expected_timeouts"] or g["min_recoveries"]):
        raise ValueError("Timer scenarios cannot expect IPC outcomes")
    if data['mode']=='service' and (p['fault_every'] or p['fault_delay_us'] or p['work_us'] or p['load_threads']):
        raise ValueError('Service probe workload belongs to the independent application')
    return data

def load(path):
    return validate(loads(Path(path).read_text(encoding="utf-8")))

def arguments(scenario):
    return [scenario["mode"]] + [str(scenario["parameters"][key]) for key in BOUNDS] + ["1"]
