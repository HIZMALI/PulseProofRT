# Validation

Validated on November 8, 2026 on Windows 11 x64 / Python 3.14, QNX SDP 8.0 / GCC 12.2.0 and VMware Workstation 16.2.4. Guest: QNX 8.0.0 x86-64, 2 vCPUs, 2 GiB RAM and a 1 ms tick. Windows Hyper-V remained enabled.

## Automated verification

- **57 host tests pass**, retaining the original 50 checks and adding seven packaging/portability checks. Coverage includes evidence validation, percentile boundaries, timeout/recovery populations, process exclusion, service ownership, strict comparisons, HTTP protections, byte preservation and public-file policy enforcement.
- **17 real QNX integration checks pass** after cleanup: cross-build, pinned SSH/qconn, packaged Hello execution, timer/load/IPC scenarios, expected deadline exit 1, repeated baseline, independent normal/delayed application, comparison, native input rejection and process cleanup. This retains the original native coverage and adds the independent application workflow.
- **13 actual evidence sets** retain matching raw SHA-256 values, recomputed summaries and byte-exact CSV contents. The original twelve sets are unchanged; an adverse timer run is also retained.
- JavaScript syntax and workflow static checks pass locally. Official Action revisions are pinned, permissions are read-only, credentials are not persisted and jobs are bounded. All four hosted combinations pass as recorded below. Hosted jobs do not provide native target coverage.

Repeat checks from the checkout:

```powershell
python -m unittest discover -s tests -v
python scripts/check-public-files.py
.\scripts\Verify.ps1 -Target
```

Detailed local results are written under `artifacts/evidence/`; the native verifier retains timestamped reports. Build scripts treat compiler warnings as errors. Public source archives and source-only staging directories use exactly the paths in `public-files.json`.

## Hosted CI

The [initial public source run](https://github.com/HIZMALI/PulseProofRT/actions/runs/42425411020) at commit `54d0c767e9a3c851fab1b35622608334c4c8aa33` completed successfully on November 8, 2026 (Europe/Istanbul). Each job verified the exact 129-file public policy and passed all 57 host tests; counts were checked in the job logs.

| GitHub-hosted runner | Python | Host tests | Result |
| --- | --- | ---: | --- |
| Ubuntu | 3.10 | 57/57 | PASS |
| Ubuntu | 3.14 | 57/57 | PASS |
| Windows | 3.10 | 57/57 | PASS |
| Windows | 3.14 | 57/57 | PASS |

These jobs test host behavior, labeled fixtures and the integrity of retained measurements. They do not boot a QNX guest, cross-compile with the licensed SDK or execute the native integration verifier. Those checks ran locally in the Windows/QNX environment described above. The [workflow page](https://github.com/HIZMALI/PulseProofRT/actions/workflows/host-tests.yml) shows subsequent runs.

## Retained measurements

| Collection | Sets | Purpose |
| --- | ---: | --- |
| [Native timer and IPC](../examples/real/README.md) | 5 | Earlier complete timer/load/timeout snapshots |
| [Application and native scenarios](../examples/rc/README.md) | 7 | Same-policy independent application comparison and native scenarios |
| [Observed timer failure](../examples/observed/README.md) | 1 | Unforced deadline failure under the original policy |

Each set includes raw NDJSON, CSV, summary/provenance and its original standalone HTML report. Unit fixtures are synthetic and labeled; retained timings are actual QNX measurements. The telemetry application's values are deterministic fixtures, not physical sensor readings. Hashes identify inputs and detect corruption; imported files cannot attest their own origin.

The independent application pair is unchanged:

| Observation | Normal | Delayed |
| --- | --- | --- |
| Run ID (UTC) | `20261107T210841-6a9fa0f3` | `20261107T210846-372e8638` |
| Successful p99 | 12,052 ns | 7,017,526 ns |
| Deadline | 2,000,000 ns | 2,000,000 ns |
| Completed misses | 0 | 200 |
| Verdict | PASS | FAIL |

The workflow returns exit 1. The probe, workload and policy match; application binaries differ. The internal IPC recovery example records exactly four timeouts and four successful recoveries. Successful recovery RTTs remain in its successful-response percentile population; errors leave completion deadlines unobserved.

## An adverse observation

Run `20261107T204534-3bd313f9` failed the unchanged 20 ms baseline policy: p99 **53.856802 ms**, maximum **60.410286 ms**, with **17 completed misses**. It contained no injected fault. Violations clustered around samples 134–141 and 146–154. Opening the hypervisor UI occurred during that period, but no trace established a cause; no QNX or hypervisor defect is inferred.

Three later quiet runs passed without changing the policy: p99 1.783021, 1.775292 and 1.504295 ms, with zero misses. Full verification subsequently passed. The earlier failure remains available with its original bytes and is not replaced by the passing runs.

## Target and interface checks

The licensed image booted QNX, accepted pinned SSH/SFTP, identified qconn and executed Hello. Cold restart and Hello after reboot were exercised before this source cleanup. The current bundled Hello removes a dependency on a separate developer checkout while retaining the same target-output check. No SDK installation or VM filesystem was changed by cleanup.

Real browser acquisitions, history, compatible comparison, measured-range zoom, evidence downloads and standalone report rendering were exercised. Downloaded raw bytes matched their recorded hashes. Responsive layouts were inspected at 390, 1440 and 1920 pixels. Cleanup did not change the interface or regenerate video.

Image packaging needed the installed `sshd-auth` helper; local snippets supply it without editing the SDK. Explicit SSH HMAC selection resolved a Windows client negotiation issue. Earlier Windows newline conversion and report script-order defects were fixed and remain regression-covered.

## Limits

These are single-VM observations, not WCET bounds, hard real-time guarantees, certification or long-duration confidence estimates. Physical QNX hardware, QEMU/WSL, rootless deployment, arbitrary-process instrumentation, server-crash restart and trace parsing have not been qualified. Target acquisition is verified on Windows; Linux host tests and offline analysis do not imply a validated Linux acquisition path.
