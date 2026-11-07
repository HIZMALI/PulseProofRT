import json
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
import urllib.error
from pulseproof.target import ROOT

class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1",0));cls.port=sock.getsockname()[1]
        cls.url=f"http://127.0.0.1:{cls.port}"
        cls.process=subprocess.Popen([sys.executable,"-m","pulseproof","serve","--port",str(cls.port)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                with urllib.request.urlopen(cls.url+"/api/state",timeout=.2) as response:
                    cls.state=json.load(response);return
            except (OSError,ValueError): time.sleep(.05)
        cls.process.terminate();raise RuntimeError("Test server did not start")

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate();cls.process.wait(timeout=5)

    def test_workbench_and_csp(self):
        with urllib.request.urlopen(self.url) as response:
            self.assertIn("frame-ancestors 'none'",response.headers["Content-Security-Policy"])
            self.assertIn("Latency workbench",response.read().decode())

    def test_reject_dns_rebinding_host(self):
        request=urllib.request.Request(self.url+"/api/state",headers={"Host":"evil.example"})
        with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code,403)
        caught.exception.close()

    def test_reject_cross_origin_execution(self):
        request=urllib.request.Request(self.url+"/api/run",data=b'{"scenario":"timer-baseline"}',headers={"Origin":"https://evil.example","X-PulseProof-Token":self.state["token"]})
        with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code,403)
        caught.exception.close()

    def test_reject_unknown_scenario(self):
        request=urllib.request.Request(self.url+"/api/run",data=b'{"scenario":"missing-scenario"}',headers={"Origin":self.url,"X-PulseProof-Token":self.state["token"]})
        with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code,400)
        caught.exception.close()

    def test_reject_path_traversal(self):
        with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(self.url+"/api/runs/../summary.json")
        self.assertEqual(caught.exception.code,404)
        caught.exception.close()
