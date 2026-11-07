# Actual QNX 8.0 RC snapshot

Captured November 7, 2026 UTC. Service payload values are deterministic fixtures; all timings are actual QNX observations. Each summary and raw SHA-256 is verified. Additional timer and IPC measurements are preserved in [real](../real/). Target details and limits are in [validation](../../docs/VALIDATION.md).

| Scenario | Run ID (UTC) | p99 (ms) | Misses | Timeouts / recoveries | Verdict |
| --- | --- | ---: | ---: | --- | --- |
| deadline-violation | `20261107T210825-4f8e58f6` | 32.660595 | 31 | 0 / 0 | FAIL |
| ipc-baseline | `20261107T205350-6dcaacea` | 0.127169 | 0 | 0 / 0 | PASS |
| ipc-recovery | `20261107T210810-167bfecb` | 15.287564 | 0 | 4 / 4 | PASS |
| service-baseline | `20261107T210841-6a9fa0f3` | 0.012052 | 0 | 0 / 0 | PASS |
| service-regression | `20261107T210846-372e8638` | 7.017526 | 200 | 0 / 0 | FAIL |
| timer-baseline | `20261107T210757-cde1b209` | 2.235267 | 0 | 0 / 0 | PASS |
| timer-loaded | `20261107T211323-e7ec21f0` | 4.323147 | 0 | 0 / 0 | PASS |

Single-guest samples are not timing guarantees. Deliberate deadline and service-regression failures must remain FAIL.
