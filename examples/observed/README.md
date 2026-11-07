# An observed timing failure

`timer-baseline-noise/` preserves run `20261107T204534-3bd313f9` without injected faults. The unchanged 20 ms policy failed: successful p99 **53.856802 ms**, maximum **60.410286 ms**, and **17 completed deadline misses**.

Later quiet runs passed the same policy. No host/kernel trace established the cause, so the observation is not attributed to a proven QNX or hypervisor defect. It illustrates the limits of a shared-host VM measurement. Raw bytes, CSV, summary/provenance and the original report are retained and verified by the test suite. See [validation](../../docs/VALIDATION.md).
