"""No interpolation: percentiles use the documented nearest-rank definition."""
import hashlib
import json
import math
from .scenario import integer
from .jsonio import loads

SAMPLE_FIELDS = {"type", "sequence", "latency_ns", "wake_lateness_ns", "error", "timeout", "injected", "recovery", "deadline_miss", "deadline_unobserved"}

def percentile(values, percent):
    if not values:
        return None
    if not 0 < percent <= 100:
        raise ValueError("Percentile must be in (0,100]")
    return sorted(values)[max(0, math.ceil(len(values) * percent / 100) - 1)]

def distribution(values):
    return {"count": len(values), "min_ns": min(values) if values else None,
            "p50_ns": percentile(values, 50), "p95_ns": percentile(values, 95),
            "p99_ns": percentile(values, 99), "max_ns": max(values) if values else None}

def analyze(raw, scenario, require_real=False):
    if len(raw.encode("utf-8")) > 8_000_000:
        raise ValueError("Evidence stream exceeds 8 MB")
    rows = [loads(line) for line in raw.splitlines() if line.strip()]
    if len(rows) < 3 or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Incomplete evidence stream")
    meta, end = rows[0], rows[-1]
    if meta.get("type") != "metadata" or end.get("type") != "complete":
        raise ValueError("Missing metadata or completion footer")
    if type(meta.get("schema_version")) is not int or meta["schema_version"] != 1:
        raise ValueError("Unsupported agent protocol")
    if meta.get("source") not in ("qnx-native", "synthetic"):
        raise ValueError("Unknown measurement source")
    if require_real and (meta["source"] != "qnx-native" or meta.get("os") != "QNX" or not str(meta.get("release", "")).startswith("8.")):
        raise ValueError("Real QNX 8 evidence required")
    if meta.get("mode") != scenario["mode"]:
        raise ValueError("Agent mode does not match scenario")
    if scenario['mode']=='service' and meta.get('service_build')!={'baseline':1,'regressed':2}[scenario['application']]:
        raise ValueError('Independent application build identity mismatch')
    p = scenario["parameters"]
    for key, value in p.items():
        if type(meta.get(key)) is not int or meta[key] != value:
            raise ValueError(f"Agent configuration mismatch: {key}")
    for key in ("cpu_count", "tick_ns", "clock_resolution_ns", "clock_read_min_ns", "cycles_per_second", "started_epoch"):
        integer(meta.get(key), key, 0 if key == "clock_read_min_ns" else 1, 10**15)
    if meta.get("clock") != "CLOCK_MONOTONIC" or meta.get("scheduler") != "SCHED_RR":
        raise ValueError("Unsupported clock or scheduling policy")
    samples = rows[1:-1]
    if len(samples) != p["samples"] or type(end.get("samples")) is not int or end["samples"] != len(samples):
        raise ValueError("Truncated or excess samples")
    previous_timeout = False
    timeout_errno = integer(meta.get("timeout_errno"), "timeout_errno", 1, 65535)
    for index, sample in enumerate(samples):
        if set(sample) != SAMPLE_FIELDS or sample["type"] != "sample":
            raise ValueError("Invalid sample record")
        if type(sample["sequence"]) is not int or sample["sequence"] != index:
            raise ValueError("Out-of-order or duplicated sample")
        for key in ("latency_ns", "wake_lateness_ns", "error"):
            integer(sample[key], key)
        for key in ("timeout", "injected", "recovery", "deadline_miss", "deadline_unobserved"):
            if type(sample[key]) is not bool:
                raise ValueError(f"{key} must be a boolean")
        if sample["timeout"] != (sample["error"] == timeout_errno):
            raise ValueError("Timeout flag does not match target ETIMEDOUT")
        if sample["wake_lateness_ns"] > sample["latency_ns"]:
            raise ValueError("Wake lateness exceeds response time")
        if sample["injected"] != bool(p["fault_every"] and (index + 1) % p["fault_every"] == 0):
            raise ValueError("Fault schedule mismatch")
        if sample["recovery"] != previous_timeout:
            raise ValueError("Recovery sequence mismatch")
        miss = bool(not sample["error"] and sample["latency_ns"] > p["deadline_us"] * 1000)
        if sample["deadline_miss"] != miss:
            raise ValueError("Inconsistent deadline result")
        if sample["deadline_unobserved"] != bool(sample["error"]):
            raise ValueError("Uncompleted operation must have an unobserved deadline")
        if scenario["mode"] == "timer" and (sample["error"] or sample["timeout"] or sample["recovery"]):
            raise ValueError("Unexpected timer transport outcome")
        previous_timeout = sample["timeout"]
    integer(end.get("elapsed_ns"), "elapsed_ns", 1)
    integer(end.get("process_cpu_ns"), "process_cpu_ns")
    system_busy = None
    if "system_cpu_available" in end:
        if type(end["system_cpu_available"]) is not bool:
            raise ValueError("Invalid CPU observation status")
        idle = integer(end.get("idle_cpu_ns"), "idle_cpu_ns", 0, 10**15)
        observation = integer(end.get("cpu_observation_ns"), "cpu_observation_ns")
        if end["system_cpu_available"] and observation:
            capacity = observation * meta["cpu_count"]
            # Separate per-CPU queries introduce small timestamp skew. Reject larger inconsistencies.
            if idle <= capacity * 1.01:
                system_busy = max(0.0, 1 - idle / capacity)
    success = [s["latency_ns"] for s in samples if not s["error"]]
    timeouts = sum(s["timeout"] for s in samples)
    unexpected = sum(bool(s["error"]) and not (s["timeout"] and s["injected"]) for s in samples)
    recoveries = sum(s["recovery"] and not s["error"] for s in samples)
    misses = sum(s["deadline_miss"] for s in samples)
    g = scenario["gates"]
    p99 = percentile(success, 99)
    checks = [
        {"name": "p99 successful response", "actual": p99, "limit": g["p99_success_ns"], "pass": p99 is not None and p99 <= g["p99_success_ns"]},
        {"name": "deadline misses", "actual": misses, "limit": g["max_deadline_misses"], "pass": misses <= g["max_deadline_misses"]},
        {"name": "expected timeouts", "actual": timeouts, "limit": g["expected_timeouts"], "pass": timeouts == g["expected_timeouts"]},
        {"name": "unexpected errors", "actual": unexpected, "limit": 0, "pass": unexpected == 0},
        {"name": "successful recoveries", "actual": recoveries, "limit": g["min_recoveries"], "pass": recoveries >= g["min_recoveries"]},
    ]
    identity = {key: meta.get(key) for key in ("source", "os", "release", "arch", "machine", "clock", "scheduler", "cpu_count", "tick_ns", "agent_version")}
    identity.update(parameters=p, mode=scenario["mode"])
    signature = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return {"schema_version": 1, "scenario": scenario, "metadata": meta,
            "source": meta["source"], "verdict": "PASS" if all(c["pass"] for c in checks) else "FAIL",
            "latency": distribution([s["latency_ns"] for s in samples]), "successful_latency": distribution(success),
            "wake_lateness": distribution([s["wake_lateness_ns"] for s in samples]),
            "deadline_misses": misses, "unobserved_deadlines": sum(s["deadline_unobserved"] for s in samples), "timeouts": timeouts, "unexpected_errors": unexpected,
            "recoveries": recoveries, "checks": checks, "completion": end,
            "process_cpu_equivalents": end["process_cpu_ns"] / end["elapsed_ns"],
            "system_busy_fraction": system_busy,
            "comparison_signature": signature, "samples": samples}

def compare(baseline, candidate, max_regression_percent=20):
    if type(max_regression_percent) not in (int,float) or not math.isfinite(max_regression_percent) or max_regression_percent<0:
        raise ValueError("Regression limit must be finite and nonnegative")
    if baseline["scenario"]["gates"] != candidate["scenario"]["gates"]:
        raise ValueError("Incomparable acceptance policy: gates changed")
    if baseline["comparison_signature"] != candidate["comparison_signature"]:
        raise ValueError("Incomparable configuration or target metadata")
    if baseline.get("target_os") != candidate.get("target_os"):
        raise ValueError("Incomparable QNX kernel build or target identity")
    for field in ("agent_sha256", "target_environment"):
        if baseline.get("provenance", {}).get(field) != candidate.get("provenance", {}).get(field):
            raise ValueError(f"Incomparable provenance: {field}")
    before, after = baseline["successful_latency"]["p99_ns"], candidate["successful_latency"]["p99_ns"]
    if before is None or after is None or before <= 0:
        raise ValueError("A nonzero successful baseline is required")
    change = (after - before) * 100 / before
    return {"baseline_p99_ns": before, "candidate_p99_ns": after, "change_percent": change,
            "limit_percent": max_regression_percent, "verdict": "PASS" if change <= max_regression_percent and candidate["verdict"] == "PASS" else "FAIL"}
