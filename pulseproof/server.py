"""Loopback-only workbench. Runs only allowlisted, validated local scenarios."""
import json
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from . import scenario
from .analysis import compare
from .runner import history, run
from .target import ROOT
from .report import WEB
from .jsonio import loads

RUN_ID = re.compile(r"[0-9]{8}T[0-9]{6}-[a-f0-9]{8}")

def serve(workspace=ROOT, port=8765):
    root = Path(workspace).resolve()
    token = secrets.token_urlsafe(32)
    lock = threading.Lock()
    job = {"running": False, "error": None, "run_id": None}

    def experiment(selected):
        try:
            summary, _ = run(selected, root)
            job.update(run_id=summary["run_id"], error=None)
        except Exception as error:
            job.update(error=str(error), run_id=None)
        finally:
            job["running"] = False
            lock.release()

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass

        def valid_host(self):
            return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def reply(self, data, code=200, content_type="application/json"):
            if isinstance(data, (dict, list)):
                data = json.dumps(data).encode()
            elif isinstance(data, str):
                data = data.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if content_type != "text/html" or self.path == "/":
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            else:
                self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.valid_host():
                return self.reply({"error": "Invalid Host"}, 403)
            path = urlparse(self.path).path
            if path in ("/", "/app.js", "/style.css"):
                filename = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}[path]
                mime = {"/": "text/html", "/app.js": "application/javascript", "/style.css": "text/css"}[path]
                return self.reply((WEB / filename).read_bytes(), content_type=mime)
            if path == "/api/state":
                choices,errors=[],[]
                for p in sorted((root/"scenarios").glob("*.json")):
                    try: choices.append(scenario.load(p))
                    except (OSError,ValueError) as error: errors.append({"file":p.name,"error":str(error)})
                return self.reply({"runs": history(root), "scenarios": choices, "scenario_errors":errors,"token": token, "job": dict(job)})
            if path == "/api/target":
                from .target import Target
                from datetime import datetime,timezone
                checked=datetime.now(timezone.utc).isoformat()
                try:
                    status=Target(root).status()
                    return self.reply({"connected":True,"checked_at":checked,"os":status["os"],"ssh":status["ssh"],"qconn":status["qconn"]})
                except (OSError,ValueError,RuntimeError) as error:
                    return self.reply({"connected":False,"checked_at":checked,"error":str(error)})
            if path=='/api/compare':
                from .evidence import read_summary
                try:
                    query=parse_qs(urlparse(self.path).query)
                    if set(query)!={'baseline','candidate'} or any(len(v)!=1 or not RUN_ID.fullmatch(v[0]) for v in query.values()):
                        raise ValueError('Expected two valid run IDs')
                    a,b=[read_summary(root/'artifacts/runs'/query[key][0]/'summary.json') for key in ('baseline','candidate')]
                    return self.reply(compare(a,b))
                except (ValueError,OSError,KeyError) as error:
                    return self.reply({'error':str(error)},400)
            match = re.fullmatch(r"/api/runs/([^/]+)/(summary.json|samples.csv|raw.ndjson|report.html)", path)
            if match and RUN_ID.fullmatch(match[1]):
                file = root / "artifacts/runs" / match[1] / match[2]
                if file.is_file():
                    mime = {"summary.json": "application/json", "samples.csv": "text/csv", "raw.ndjson": "application/x-ndjson", "report.html": "text/html"}[match[2]]
                    return self.reply(file.read_bytes(), content_type=mime)
            return self.reply({"error": "Not found"}, 404)

        def do_POST(self):
            origin = self.headers.get("Origin")
            if not self.valid_host() or origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}") or self.headers.get("X-PulseProof-Token") != token:
                return self.reply({"error": "Invalid origin or token"}, 403)
            if self.path != "/api/run":
                return self.reply({"error": "Not found"}, 404)
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 1024:
                    raise ValueError("Invalid body size")
                body = loads(self.rfile.read(size))
                if not isinstance(body, dict) or set(body) != {"scenario"} or not isinstance(body["scenario"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", body["scenario"]):
                    raise ValueError("Invalid scenario")
                file = root / "scenarios" / (body["scenario"] + ".json")
                selected = scenario.load(file)
                if not lock.acquire(blocking=False):
                    return self.reply({"error": "An experiment is already running"}, 409)
                job.update(running=True, error=None, run_id=None)
                threading.Thread(target=experiment, args=(selected,), daemon=True).start()
                return self.reply({"running": True}, 202)
            except (ValueError, OSError) as error:
                return self.reply({"error": str(error)}, 400)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    print(f"PulseProof RT: http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
