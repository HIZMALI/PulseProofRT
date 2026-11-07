# Independent QNX telemetry service

`service.c` is a separate application executable, not a thread inside the timing agent. It registers a local QNX named channel, validates versioned requests, returns deterministic telemetry values, and handles connect/disconnect/unblock events. It has no dependency on PulseProof's Python analysis layer.

The build produces two executables from the same application source:

| Build | Change | Same client policy |
| --- | --- | --- |
| `telemetry-baseline` | No blocking delay on the request path | 2 ms response deadline; zero misses |
| `telemetry-regressed` | Compile-time 5 ms blocking delay | Exactly the same policy |

Run `python -m pulseproof app-demo` after building. It acquires actual timings for both versions, evaluates both, compares compatible evidence, and exits **1** when the regression is detected. The baseline should pass and the candidate should fail. That nonzero status is the intended CI demonstration.

The service payload is explicitly a deterministic fixture, not a physical sensor measurement. Latencies, kernel messages, processes, timeouts and OS counters are real QNX observations. A per-launch instance ID echoed by the application prevents the probe from accepting a stale service instance. The host records application binary hashes and never changes the policy between versions.

To adapt this pattern to an application, keep its message contract and real work, replace this request handler with the application operation, and justify its timing policy. The current adapter intentionally supports this fixed protocol rather than claiming arbitrary application instrumentation.
