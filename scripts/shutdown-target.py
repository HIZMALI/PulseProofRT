"""Authorize power removal only after a verified target accepts an orderly shutdown."""
import socket
import subprocess
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from pulseproof.target import Target
target=Target()
target.status()
result=subprocess.run(["ssh",*target.options,"root@"+target.address,
                       "command -v shutdown >/dev/null && sync && echo PULSEPROOF_SHUTDOWN_REQUESTED && shutdown -b"],
                      capture_output=True,text=True,timeout=20)
if "PULSEPROOF_SHUTDOWN_REQUESTED" not in result.stdout:
    raise SystemExit("Target did not confirm shutdown; refusing power removal")
for _ in range(20):
    try:
        with socket.create_connection((target.address,22),timeout=.3): pass
        time.sleep(.5)
    except OSError:
        break
else:
    raise SystemExit("SSH remained active; refusing power removal")
time.sleep(8)
print("Verified target accepted sync/shutdown; SSH is stopped.")
