# Codelab: build an evidence-based QNX timing gate

**Audience:** developers comfortable with C and a command line, including first-time QNX users. **Time:** 60–75 minutes after installing a licensed QNX SDP. **Outcome:** boot QNX 8.0, run native timing/fault experiments, detect a regression in an independent application using an unchanged policy, and export evidence suitable for a build gate.

Prerequisites: Windows 11 x64, Python 3.10+, Windows OpenSSH, licensed QNX SDP 8.0 and VMware Workstation. Allow approximately 2 GiB guest RAM plus host headroom. Keep the guest on private NAT. Clone/extract the source into a writable local folder; never copy someone else's private identity or licensed VM. [Clean installation and setup](SETUP.md) covers paths and entitlement. Source is MIT; SDK and runtime licensing remain separate.

The verified environment is Windows 11 x64 with QNX SDP 8.0 and VMware Workstation 16.2.4. Set `QNX_SDP` to your licensed SDK directory. Host analysis uses Python's standard library; no cloud account, database, IDE extension or npm installation is needed.

## 1. Understand the host/target split

Windows runs the cross-compiler and the PulseProof interface. The produced ELF executable runs on QNX, not Windows. The target is a licensed QNX image generated from your installed SDP. VMware provides virtual hardware; QNX still runs its own kernel and native messaging API.

The [QNX image generator documentation](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/m/mkqnximage.html) lists VMware on Windows for x86-64 targets. QEMU is listed with Ubuntu. This codelab reuses the installed VMware route rather than adding another host layer.

## 2. Boot and identify a real target

From the project directory:

```powershell
.\scripts\Setup-Target.ps1
python -m pulseproof target status
python -m pulseproof build
python -m pulseproof target hello
```

The setup script generates a private SSH identity, builds an image if missing, applies project-local image extensions, and boots the guest. If VMware services are stopped, Windows asks for UAC approval. Re-running the script preserves a running target. It does not reinstall QNX, disable Windows security features, or overwrite a powered-on VM image.

**Checkpoint:** status must identify QNX 8.0.0, verify SSH using the image's pinned Ed25519 host key, and receive `QCONN` from port 8000. Hello must print:

```text
Hello from QNX SDP 8.0!
```

`artifacts/evidence/hello.json` records the target output, binary hash and exit code. The build uses the included `examples/hello/hello.c` and writes `build/hello`; no separate Hello project is needed. `--binary` accepts another executable with the same expected output.

If boot succeeds but SSH does not, inspect the serial log. This installation needed an `sshd-auth` helper omitted from its image template. The supplied local snippets add the installed helper without modifying the SDK. A Windows OpenSSH MAC failure is addressed by explicit `hmac-sha2-256`, while retaining host-key verification. [Setup troubleshooting](SETUP.md) describes these observed issues.

## 3. Cross-compile and inspect the first baseline

```powershell
python -m pulseproof build
python -m pulseproof run scenarios/timer-baseline.json
```

Compilation treats all warnings as errors. A source/binary manifest prevents deployment after an unbuilt source change. The run uploads the actual QNX ELF file and invokes it through authenticated SSH.

The timer scenario schedules 300 jobs at 5 ms intervals. Each job performs approximately 100 µs of CPU work. Releases use an absolute monotonic clock, so a late job does not silently reset the schedule.

For release `r`, wake `w`, and completion `c`:

```text
wake lateness = max(w - r, 0)
response time = c - r
deadline miss = completed successfully AND response time > deadline
```

The baseline's 20 ms deadline is an explicit VM example budget, not a QNX real-time guarantee. Choose an application budget from its requirements rather than copying this value.

**Checkpoint:** a run prints its policy verdict and evidence directory. In one verified run, p99 was 1.652213 ms and completed deadline misses were zero. Your numbers will vary with host contention. Do not replace real results with these example numbers.

## 4. Inspect the evidence rather than trusting a chart

Open the new run directory under `artifacts/runs/`:

| File | Purpose |
| --- | --- |
| `raw.ndjson` | Agent metadata, every sample, completion footer |
| `summary.json` | Policies, statistics, provenance, and embedded samples |
| `samples.csv` | Tabular samples for other analysis tools |
| `report.html` | Standalone, embedded-data browser report |

The analyzer requires the exact sample count, contiguous sequence numbers, matching scenario parameters, coherent timeout/deadline flags, and a completion footer. Truncating a stream produces an acquisition error, not a partial PASS.

Percentiles use nearest rank: sort `n` values, choose element `ceil(p*n/100)`, using one-based indexing. For 300 values, p99 selects the 297th. The UI's main percentiles describe successful responses. All-attempt durations, timeouts, errors, and recoveries remain visible separately.

## 5. Add controlled CPU pressure

```powershell
python -m pulseproof run scenarios/timer-loaded.json
```

Two same-priority workers alternate roughly 8 ms of busy work with 2 ms of sleep. Actual CPU load is measured. PulseProof verifies the QNX idle thread names, reads their execution clocks with `ClockId`/`ClockTime`, and estimates guest-wide busy fraction over the experiment interval.

One validated pair observed approximately 3.1% guest CPU busy without load and 74.8% with two workers. Loaded p99 increased to 4.584392 ms. These observations describe this guest, not a universal load-to-latency law. The agent process's CPU equivalents exclude the separate IPC server; the guest estimate includes it.

## 6. Challenge native messaging and recovery

```powershell
python -m pulseproof run scenarios/ipc-baseline.json
python -m pulseproof run scenarios/ipc-recovery.json
```

The IPC server is a separate process. It receives native messages on a QNX channel and echoes sequence numbers in replies. Before each send, the client arms a kernel timeout for both SEND and REPLY states. [QNX TimerTimeout](https://qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/t/timertimeout.html) documents these blocking states.

The recovery scenario delays every twenty-fifth reply by 20 ms against a 5 ms timeout. The next request uses a 250 ms recovery budget. Over 120 requests, the policy requires four timeouts and four successful recoveries. It also requires zero unexpected errors.

**Checkpoint:** the real target should report four timeouts and four recoveries. Each timeout has an unobserved completion deadline. Do not interpret its 5 ms error-return time as the completed service latency. Successful recovery RTTs remain in the successful-response percentile distribution, which explains the approximately 15 ms tail.

This is stall recovery, not automatic server restart after a crash. Naming that limit makes the experiment reproducible and defensible.

## 7. Prove that failure is visible to CI

```powershell
python -m pulseproof run scenarios/deadline-violation.json
$LASTEXITCODE
```

The scenario adds a 30 ms stall every twentieth job and keeps the deadline at 5 ms. The expected command exit is **1**, with a FAIL verdict. Invalid input, transport failure, or corrupt evidence instead returns **2**.

One recorded run detected 31 deadline misses from six injected stalls. Why more than six? The absolute release schedule preserves backlog: jobs following a long stall can also finish after their own deadlines. Resetting the next release to “now” would hide that behavior.

For an application policy, version a copied scenario, justify its budget and preserve failed runs.

## 8. Detect an independent application's regression

The useful daily question is: **did this application change break the same acceptance policy?** The example under `examples/telemetry-service/` is a separate native QNX executable. It registers a named channel and returns a versioned telemetry response. The client validates protocol, sequence, build and a unique launch ID. Payload values are deterministic fixtures; message durations are actual QNX measurements.

The build creates `telemetry-baseline` and `telemetry-regressed`. The only intended performance change is a compile-time 5 ms blocking delay in the request path. Both scenarios request 200 measured exchanges, exclude 20 warmups, and require p99 ≤2 ms with zero completed misses. The 50 ms transport timeout is distinct from the 2 ms application deadline. Do not edit the policy between versions.

```powershell
python -m pulseproof build
python -m pulseproof app-demo
$LASTEXITCODE
```

**Checkpoint:** normal build PASS; delayed build FAIL; comparison FAIL; exit **1**. The captured RC pair measured 0.012052 ms versus 7.017526 ms p99, with 200 misses in the candidate. These are one guest's observations, not expected exact output. The measured increase exceeds the source's 5 ms delay because sleeping and scheduling add overhead.

`artifacts/evidence/application-workflow.json` contains both run IDs and verdicts. Follow those IDs into `artifacts/runs/` and inspect each `summary.json`. Confirm equal `scenario.parameters` and `scenario.gates`, matching probe hash/environment and different application binary hashes. JSON keys for lifecycle/provenance are documented in the actual summaries; the [RC snapshot](../examples/rc/README.md) gives a concrete pair.

If the normal reference itself fails, `app-demo` exits **2** and refuses to call the pair a controlled regression. Preserve both raw runs, reduce unrelated host activity, and investigate. It never retries automatically or relaxes the deadline. The service is stopped after each run using owned PID/executable checks. This is one explicit protocol adapter; adapting a real application requires implementing its message contract and justifying its budget.

**Exercise:** locate the application's `SERVICE_DELAY_US` setting in `service.c` and `scripts/build-agent.cmd`. Explain why changing the application binary is allowed in this comparison while changing the probe or acceptance gates is rejected. Keep source changes versioned, rebuild and retain the new hashes before using a new variant.

## 9. Use history, reports, and regression automation

```powershell
python -m pulseproof serve
.\scripts\Verify.ps1 -Target
```

At [the local workbench](http://127.0.0.1:8765), run a scenario, select previous evidence, inspect the response timeline/CDF, compare compatible baselines, and download raw files. Comparisons require matching target, clock, scheduler, workload, agent hash, and host/VM identity. A different loaded scenario is deliberately not treated as a comparable regression baseline.

The target status is a live SSH/qconn check. Browsing old data does not establish a live connection. Use **Zoom measured range** to inspect small changes while retaining the real budget label; it changes only the visualization. The empirical CDF is a step distribution. On the candidate application result, select the normal application as baseline and choose **Compare P99**; the backend revalidates the evidence before comparing.

The real integration verifier compiles, checks SSH/qconn and Hello, runs all scenarios, confirms the intentional failing exit, compares separate baselines, rejects invalid native inputs, and checks process cleanup. Host-only CI runs on ordinary systems using explicitly synthetic unit fixtures; it does not claim QNX target coverage.

Before sharing a result, verify the downloaded raw file's SHA-256 against `provenance.raw_sha256`. PulseProof preserves LF bytes consistently on Windows; a regression test guards against newline translation. Hashes detect corruption and identify inputs. They do not attest that an arbitrary imported file was produced by a trusted target.

For offline reanalysis using the included RC snapshot:

```powershell
python -m pulseproof analyze examples/rc/service-baseline/raw.ndjson scenarios/service-baseline.json
# Expected 0: retained normal application evidence passes.
python -m pulseproof compare examples/rc/service-baseline/summary.json examples/rc/service-regression/summary.json
# Expected 1: retained application regression, without needing a live guest.
Get-FileHash examples/rc/service-regression/raw.ndjson -Algorithm SHA256
```

Offline commands inspect retained measurements; they do not execute QNX again. Compare the hash with the summary. Altering an aggregate metric or raw byte makes verified comparison reject the file. Report exports are self-contained and do not fetch external scripts.

## 10. A build gate you can explain

On a private licensed Windows runner, build and run the application's **candidate scenario** as a normal pipeline step. Propagate its exit status: 0 accepts the measured policy, 1 rejects it, 2 requires acquisition/setup investigation. Archive `raw.ndjson`, `summary.json`, `samples.csv` and `report.html` from that run; exclude SDK, private identities and VM files. `app-demo` is a teaching workflow with an intentional failing candidate, so it should not be used as an always-green CI check.

GitHub Actions checks the public-file policy and runs host tests on Windows/Linux with Python 3.10/3.14. All four combinations passed 57 tests; [validation](VALIDATION.md#hosted-ci) links to the run and records the platform split. Action revisions are pinned, permissions are read-only, checkout credentials are not persisted and jobs have a five-minute timeout. A hosted runner without a licensed QNX target does not provide native coverage.

## Troubleshooting and interpretation

| Symptom | What to inspect / do |
| --- | --- |
| Compiler unavailable | Set `QNX_SDP` to the licensed installation; use `python -m pulseproof build` to activate its environment |
| SSH fails after DHCP renewal | Discovery selects lease start time, not file order; verify private networking and the pinned image key |
| Workbench says target unavailable | Use **Check connection**; retained history is still valid but is not live target status |
| Workspace busy | Another process owns acquisition; let it finish instead of running overlapping experiments |
| Comparison rejected | Check agent hash, target/kernel, gates, workload and environment; do not override compatibility |
| Baseline exceeds deadline | Preserve evidence; inspect wake/backlog and ambient host activity; use tracing for cause |
| Kernel timeout count differs | Check the exact scenario and delayed-server contract; timeout and completed latency are different |
| Source manifest mismatch | Rebuild from the intended source; never rewrite the recorded hash to suppress the check |

A real adverse baseline observed p99 53.856802 ms and 17 misses; later quiet runs passed without changing thresholds. No trace established the cause. The [raw failure record](../examples/observed/README.md) is retained. A single passing run does not establish a hard upper bound.

**Completion check:** identify QNX, run a passing baseline, produce four timeout/recovery pairs, obtain intentional exit 1, reproduce the independent application's PASS → FAIL, verify raw hash, and open the standalone report. Explain which measurements include backlog, which deadlines are unobserved, and why VM results need physical-hardware follow-up.

## Next investigation

If a gate regresses, reproduce it under controlled host load and use QNX System Profiler to inspect kernel-event causes. PulseProof supplies the acceptance experiment and evidence trail; tracing explains the cause. Hardware qualification, additional application adapters, `.kev` integration and confidence estimates across long campaigns remain future extensions.

The project is MIT-licensed. QNX/VMware software, VM images, licenses and private keys are not part of the source distribution.
