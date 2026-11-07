"""Integration checks execute real binaries on QNX. No synthetic fallback."""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from pulseproof.target import Target
from pulseproof.runner import history
from pulseproof.analysis import compare

checks=[]
def command(name,args,expected=0):
    result=subprocess.run([sys.executable,"-m","pulseproof",*args],cwd=ROOT,capture_output=True,text=True,timeout=120)
    okay=result.returncode==expected
    checks.append({"name":name,"pass":okay,"exit_code":result.returncode,"expected_exit":expected,"stdout":result.stdout,"stderr":result.stderr})
    print(("PASS" if okay else "FAIL")+" "+name,flush=True)
    if not okay: print(result.stderr or result.stdout,flush=True)

command("build",["build"])
command("target SSH and qconn",["target","status"])
command("packaged Hello on QNX",["target","hello"])
for name in ("timer-baseline","timer-loaded","ipc-baseline","ipc-recovery"):
    command(name,["run",f"scenarios/{name}.json"])
command("deadline failure exits 1",["run","scenarios/deadline-violation.json"],1)
command("repeat baseline",["run","scenarios/timer-baseline.json"])
command('independent service baseline',['run','scenarios/service-baseline.json'])
command('independent service regression exits 1',['run','scenarios/service-regression.json'],1)
command('independent application workflow exits 1',['app-demo'],1)
workflow=json.loads((ROOT/'artifacts/evidence/application-workflow.json').read_text(encoding='utf-8'))
checks.append({'name':'application workflow establishes PASS baseline and FAIL candidate',
               'pass':workflow.get('baseline_verdict')=='PASS' and workflow.get('candidate_verdict')=='FAIL' and workflow.get('verdict')=='FAIL',
               'result':workflow})
runs=[r for r in history(ROOT) if r["scenario"]["id"]=="timer-baseline"]
try:
    result=compare(runs[1],runs[0])
    checks.append({"name":"real-run comparison","pass":True,"result":result})
    print("PASS real-run comparison (policy verdict: "+result["verdict"]+")",flush=True)
except Exception as error:
    checks.append({"name":"real-run comparison","pass":False,"error":str(error)})
target=Target()
for name,args in (("reject oversized sample count","timer 10001 5000 20000 100 0 0 0 5000 20 1"),
                  ("reject unsupported protocol","timer 10 5000 20000 100 0 0 0 5000 20 99")):
    try:
        # Capture exit status in the same shell without losing the original error.
        status=target.ssh(f"/data/pp-agent {args} >/dev/null 2>/dev/null; echo $?").strip()
        checks.append({"name":name,"pass":status=="2","target_exit":status})
    except Exception as error:
        checks.append({"name":name,"pass":False,"error":str(error)})
remaining=target.ssh("pidin ar")
leaked=any(("/data/pp-agent" in line or '/data/pp-telemetry-' in line) for line in remaining.splitlines() if "sh -c" not in line)
checks.append({"name":"no agent or server process leaked","pass":not leaked})
evidence={"source":"real QNX integration","created_at":datetime.now(timezone.utc).isoformat(),"checks":checks,"pass":all(c["pass"] for c in checks)}
file=ROOT/"artifacts/evidence/integration-rc.json"
archive=file.with_name('integration-rc-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'.json')
archive.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
file.write_text(json.dumps(evidence,indent=2),encoding="utf-8")
print(f"Integration: {sum(c['pass'] for c in checks)}/{len(checks)} passed. {file}")
raise SystemExit(0 if evidence["pass"] else 1)
