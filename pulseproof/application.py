"""Lifecycle for the independently compiled QNX telemetry reference application."""
import hashlib
import json
import re
import time
import secrets

class ManagedService:
    def __init__(self,target,variant):
        if variant not in ('baseline','regressed'): raise ValueError('Unknown application variant')
        self.target,self.variant,self.pid=target,variant,None
        self.instance=secrets.token_hex(8)

    def __enter__(self):
        manifest=json.loads((self.target.root/'build/manifest.json').read_text(encoding='utf-8'))
        binary=self.target.root/'build'/('telemetry-'+self.variant)
        digest=hashlib.sha256(binary.read_bytes()).hexdigest()
        if digest!=manifest['applications'][self.variant]['binary_sha256']:
            raise ValueError('Application binary changed after build')
        self.remote='/data/pp-telemetry-'+digest[:16]
        self.target.upload(binary,self.remote)
        self.target.ssh('chmod 755 '+self.remote)
        output=self.target.ssh(f'nohup {self.remote} {self.instance} >{self.remote}.log 2>&1 < /dev/null & echo $!').strip()
        if not re.fullmatch(r'[1-9][0-9]*',output): raise RuntimeError('Application launch did not return a PID')
        self.pid=int(output)
        return {'name':'telemetry-service','protocol_version':1,'variant':self.variant,
                'binary_sha256':digest,'build_id':manifest['applications'][self.variant]['build_id'],
                'server_delay_us':manifest['applications'][self.variant]['delay_us'],
                'instance':self.instance,
                'payload':'deterministic fixture; timing is measured on QNX'}

    def __exit__(self,*unused):
        if self.pid is None: return
        identity=self.target.ssh(f'if kill -0 {self.pid} 2>/dev/null; then pidin -p {self.pid} ar; fi')
        if not identity.strip(): return
        if not re.search(r'^\s*'+str(self.pid)+r'\s+'+re.escape(self.remote)+r'(?:\s|$)',identity,re.M):
            raise RuntimeError('Application PID identity changed; refusing to signal it')
        self.target.ssh(f'kill -TERM {self.pid}')
        for _ in range(30):
            active=self.target.ssh(f'if kill -0 {self.pid} 2>/dev/null; then echo active; fi').strip()
            if not active: return
            time.sleep(.05)
        raise RuntimeError('Application did not terminate after SIGTERM')
