"""Private local target state, pinned SSH identity, bounded subprocesses."""
import hashlib
import ipaddress
import json
import re
import socket
import subprocess
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def latest_lease(leases,mac):
    matches=[]
    for index,(address,body) in enumerate(re.findall(r"lease\s+([0-9.]+)\s*\{([^}]+)\}",leases)):
        if re.search(r"hardware ethernet\s+"+re.escape(mac)+r"\s*;",body,re.I):
            started=re.search(r"starts\s+\d+\s+([0-9/]+\s+[0-9:]+)",body)
            matches.append((started[1] if started else '',index,address))
    if not matches: raise ValueError('No DHCP lease for the VM; boot it and renew VMnet8')
    # ISC lease compaction reorders records; file position is only a tie-breaker.
    return max(matches)[2]

def execute(args, timeout=120):
    try:
        result = subprocess.run([str(a) for a in args], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Operation exceeded {timeout} seconds") from exc
    if result.returncode:
        raise RuntimeError(f"Command exited {result.returncode}: {result.stderr.strip()[-1500:] or result.stdout.strip()[-1500:]}")
    return result.stdout

class Target:
    def __init__(self, workspace=ROOT, address=None):
        self.root = Path(workspace).resolve()
        self.ssh_dir = self.root / "artifacts/ssh"
        self.vmx = self.root / "artifacts/vm/local/vmware_files/vmware.vmx"
        self.identity = self.ssh_dir / "target_ed25519"
        self.known_hosts = self.ssh_dir / "known_hosts"
        self.address = str(ipaddress.IPv4Address(address or self.discover()))
        ip = ipaddress.ip_address(self.address)
        if not ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified:
            raise ValueError("Expected a private IPv4 VM address")
        if not self.identity.is_file():
            raise ValueError("Target SSH identity is missing; run scripts/Setup-Target.ps1")
        public = self.root / "artifacts/vm/local/misc_files/ssh_host_ed25519_key.pub"
        parts = public.read_text(encoding="ascii").split()
        if len(parts) < 2 or parts[0] != "ssh-ed25519":
            raise ValueError("Invalid image host public key")
        pinned=f"{self.address} {parts[0]} {parts[1]}\n"
        if not self.known_hosts.is_file() or self.known_hosts.read_text(encoding='ascii')!=pinned:
            with tempfile.NamedTemporaryFile(mode='w',encoding='ascii',newline='',dir=self.ssh_dir,delete=False) as stream:
                stream.write(pinned);temporary=stream.name
            os.replace(temporary,self.known_hosts)

    def discover(self):
        config = self.vmx.read_text(encoding="utf-8-sig")
        match = re.search(r'^ethernet0.address\s*=\s*"([0-9a-f:]+)"', config, re.M | re.I)
        if not match:
            raise ValueError("VM MAC address not found")
        leases = Path("C:/ProgramData/VMware/vmnetdhcp.leases").read_text(encoding="ascii")
        return latest_lease(leases,match[1])

    @property
    def options(self):
        return ["-i", str(self.identity), "-o", f"UserKnownHostsFile={self.known_hosts.as_posix()}",
                "-o", "StrictHostKeyChecking=yes", "-o", "BatchMode=yes",
                "-o", "MACs=hmac-sha2-256", "-o", "ConnectTimeout=5",
                "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2"]

    def ssh(self, command, timeout=90):
        return execute(["ssh", *self.options, f"root@{self.address}", command], timeout)

    def upload(self, local, remote):
        if not re.fullmatch(r"/data/[a-zA-Z0-9_.-]+", remote):
            raise ValueError("Uploads must be a simple filename under /data")
        execute(["scp", *self.options, str(Path(local).resolve()), f"root@{self.address}:{remote}"])

    def status(self):
        uname = self.ssh("uname -a").strip()
        if not uname.startswith("QNX ") or " 8.0.0 " not in uname:
            raise ValueError("Target is not QNX 8.0")
        with socket.create_connection((self.address, 8000), timeout=3) as stream:
            stream.settimeout(2)
            greeting=b""
            while len(greeting)<5:
                chunk=stream.recv(5-len(greeting))
                if not chunk: break
                greeting+=chunk
            qconn = greeting.decode("ascii", errors="replace")
        if qconn != "QCONN":
            raise ValueError("Port 8000 did not identify itself as qconn")
        return {"os": uname, "ssh": "verified", "qconn": qconn, "address": self.address}

    def deploy_agent(self):
        binary = self.root / "build/pp-agent"
        if not binary.is_file():
            raise ValueError("Build agent first: python -m pulseproof build")
        manifest = json.loads((self.root / "build/manifest.json").read_text(encoding="utf-8"))
        actual = hashlib.sha256(binary.read_bytes()).hexdigest()
        if actual != manifest["binary_sha256"]:
            raise ValueError("Agent binary changed after build")
        for name, expected in manifest["sources"].items():
            if hashlib.sha256((self.root / name).read_bytes()).hexdigest() != expected:
                raise ValueError("Agent source changed after build; rebuild required")
        self.upload(binary, "/data/pp-agent")
        self.ssh("chmod 755 /data/pp-agent")
        return actual

    def environment(self):
        data = json.loads(execute(["powershell.exe", "-NoProfile", "-File", str(self.root / "scripts/Inspect-Environment.ps1")], timeout=15))
        config = self.vmx.read_text(encoding="utf-8-sig")
        for field, key in (("numvcpus", "guest_vcpus"), ("memsize", "guest_ram_mb")):
            match = re.search(r'^' + field + r'\s*=\s*"([0-9]+)"', config, re.M)
            if not match:
                raise ValueError(f"VM configuration is missing {field}")
            data[key] = int(match[1])
        data["virtualization"] = "VMware"
        return data

    def hello(self, binary=None):
        binary = Path(binary) if binary is not None else self.root / "build/hello"
        self.upload(binary, "/data/hello-check")
        output = self.ssh("chmod 755 /data/hello-check && /data/hello-check")
        if output.strip() != "Hello from QNX SDP 8.0!":
            raise ValueError("Unexpected Hello output")
        evidence = {"target": self.status(), "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                    "stdout": output, "exit_code": 0, "binary": binary.name}
        path = self.root / "artifacts/evidence/hello.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        return evidence
