# Setup

## Requirements

The verified target route uses Windows 11 x64, QNX SDP 8.0 / GCC 12.2.0, VMware Workstation 16.2.4, Python 3.10+ and Windows OpenSSH. The guest is QNX 8.0.0 x86-64 with 2 vCPUs, 2 GiB RAM and a 1 ms tick. Allow additional memory for the host. A licensed SDK and permission to use the virtualizer are required; neither is distributed here.

The QNX [image generator](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/m/mkqnximage.html) supports VMware/Windows/x86-64. QEMU/Ubuntu is a separate route and has not been tested with this project. Windows Hyper-V remained enabled in the verified environment.

## Install the host package

From a source checkout or extracted archive:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --index-url https://pypi.org/simple "setuptools>=77"
.\.venv\Scripts\python -m pip install --no-build-isolation --no-deps -e .
```

Use that Python interpreter for the commands below. An editable install resolves scripts and scenarios from the checkout. A non-editable installation needs `pulseproof --workspace <source-directory> ...`. The runtime has no third-party Python dependencies; setuptools is a build dependency.

## Build and boot QNX

Set the process environment variable `QNX_SDP` to your installed SDP directory. Each build script calls its `qnxsdp-env.bat`; no SDK download or global environment change is performed.

```powershell
python -m pulseproof build
.\scripts\Setup-Target.ps1
python -m pulseproof target status
python -m pulseproof target hello
```

The build creates the native agent, normal/delayed telemetry executables, a portable Hello example and a source/binary manifest under `build/`. Compiler warnings are errors. Hello is built from [the included source](../examples/hello/hello.c); `target hello --binary <file>` can verify another executable with the same expected output.

`Setup-Target.ps1` generates a local Ed25519 identity, builds a missing image from installed licensed QNX components, configures the project's VM and waits for SSH/qconn. It uses the standard VMware Workstation installation path. If existing authorization, DHCP or NAT services are stopped, Windows requests UAC approval to start only those services. The script does not install VMware or weaken Windows security settings.

Re-running setup preserves a running guest. `-Rebuild` is refused while powered on; an explicit rebuild replaces the development image's filesystems, so preserve guest data first. Nested virtualization and 3D acceleration are disabled only in this VM. The headless graphics console is expected to be black; OS identity and execution are verified over SSH.

Expected Hello output:

```text
Hello from QNX SDP 8.0!
```

## Connection and private state

Keep the guest on private VMware NAT. Discovery selects the matching VM MAC's latest lease by start time. DHCP addresses are not portable configuration values. `--target <private-ip>` overrides discovery while retaining pinned host-key verification.

- `artifacts/ssh/`: private development identity and image-derived public host pin.
- `artifacts/vm/`: proprietary image, VM configuration and serial log.
- `artifacts/runs/`: completed local measurements.
- `artifacts/evidence/`: local diagnostics and verification results.
- `build/`: executables and build manifest.

The default guest account is root for scheduling and idle-thread inspection. This is an isolated development setup, not a hardened production deployment. No public listener or firewall rule is needed for the workbench.

## Run and stop

```powershell
python -m pulseproof run scenarios/timer-baseline.json
python -m pulseproof serve
```

The browser interface listens on [127.0.0.1:8765](http://127.0.0.1:8765/). `Start-Workbench.ps1` is an optional background-server helper; it records its PID and logs locally.

`Stop-Target.ps1` requests an orderly shutdown. By default it leaves VM power on because SSH closure cannot prove a completed kernel/filesystem halt. Inspect the console before explicitly using `-PowerOffAfterShutdown`. Unrelated VMs are not controlled by these helpers.

## Verification and source distributions

```powershell
.\scripts\Verify.ps1
.\scripts\Verify.ps1 -Target
python scripts/check-public-files.py
python scripts/package-source.py --output artifacts/dist/source.zip --stage artifacts/exported-source
python scripts/verify-source-package.py artifacts/dist/source.zip
```

The host suite needs Python; `Verify.ps1` also uses Node for a JavaScript syntax check. Native verification requires the running licensed target and `QNX_SDP`. Intentional failures must exit 1; invalid input/acquisition exits 2. Verifier reports are timestamped rather than discarded.

The explicit `public-files.json` policy governs ZIP contents and tracked-file CI checks. `--stage` creates a new source-only directory without `.git`. Existing outputs are preserved; choose a new path for another package. Do not push a private repository whose older commits contain material you intend to exclude.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Build cannot find the SDK | Set `QNX_SDP` to the licensed directory containing `qnxsdp-env.bat` |
| SSH fails after boot | Inspect the serial log and private NAT lease; do not disable host-key verification |
| OpenSSH authentication helper missing | The image snippets include the installed `sshd-auth` helper and IFS symlink |
| Windows SSH MAC negotiation fails | The host uses explicit `hmac-sha2-256` with strict checking |
| VMnet8 has an APIPA address | Start VMware DHCP/NAT and renew that adapter; leave physical networking unchanged |
| Source/binary manifest mismatch | Rebuild the intended checkout before deployment |
| Baseline fails during contention | Preserve it and investigate; do not relax the budget automatically |
| Workspace busy | Wait for the existing acquisition to finish |

See the [tutorial](TUTORIAL.md) for experiments and [validation](VALIDATION.md) for observed limits.
