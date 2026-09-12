"""Public-only subprocess client; does not import Torch, fitting or evaluator."""
from __future__ import annotations
import json
from pathlib import Path
import selectors
import subprocess
import sys
import time
from .common import ROOT,sha
from .features import validate_snapshot
from .selection import predicted_choice

class InferenceWorker:
    def __init__(self,checkpoint,checkpoint_sha,*,seed,epoch,parameter_sha):
        self.checkpoint_sha=checkpoint_sha;self.sequence=0;self.disabled=False
        start=time.monotonic();rl=Path(__file__).resolve().parent.parent
        self.process=subprocess.Popen([sys.executable,'-S','-B','-m','training_round1_20260912.actor_worker',
            '--checkpoint',str(Path(checkpoint).resolve()),'--sha256',checkpoint_sha],cwd=rl,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        try:
            ready=json.loads(self._readline(30.))
            expected=dict(ready=True,checkpoint_sha256=checkpoint_sha,seed=seed,epoch=epoch,
                parameter_count=61121,device='cpu',threads=1,parameter_sha256=parameter_sha,
                model_source_sha256=sha(ROOT/'model.py'),feature_implementation_sha256=sha(ROOT/'features.py'))
            if ready!=expected:
                raise RuntimeError('Frozen neural worker readiness mismatch')
            self.identity=ready;self.startup_wall_s=time.monotonic()-start
        except BaseException:
            self.disable();self.close();raise

    def _readline(self,timeout):
        watch=selectors.DefaultSelector();watch.register(self.process.stdout,selectors.EVENT_READ)
        try:
            if not watch.select(timeout):raise TimeoutError('Neural worker response deadline')
            line=self.process.stdout.readline()
            if not line:raise RuntimeError('Neural worker ended: '+self.process.stderr.read()[-2000:])
            return line
        finally:watch.close()

    def disable(self):
        self.disabled=True
        if self.process.poll() is None:
            self.process.kill();self.process.wait(timeout=2)

    def score(self,snapshot):
        if self.disabled:raise RuntimeError('Neural worker disabled after prior protocol failure')
        validate_snapshot(snapshot);self.sequence+=1;request_id=str(self.sequence);start=time.monotonic()
        try:
            self.process.stdin.write(json.dumps(dict(request_id=request_id,snapshot=snapshot),allow_nan=False,separators=(',',':'))+'\n')
            self.process.stdin.flush();response=json.loads(self._readline(10.))
            if response.get('request_id')!=request_id:raise ValueError('Neural response request-ID mismatch')
            if not response.get('ok'):
                if response.get('resource_failure') is True:
                    raise MemoryError(response.get('error','Neural worker resource failure'))
                raise ValueError(response.get('error','Neural worker failed'))
            expected={'ok','candidate_ids','teacher_id','scores','choice','checkpoint_sha256','tensor_build_wall_s',
                'tensor_build_cpu_s','forward_wall_s','forward_cpu_s','batch_size','request_id'}
            if set(response)!=expected:raise ValueError('Unknown neural response fields')
            if response['candidate_ids']!=snapshot['candidate_ids'] or response['teacher_id']!=snapshot['teacher_id']:
                raise ValueError('Neural response candidate alignment differs')
            if response['checkpoint_sha256']!=self.checkpoint_sha or response['batch_size']!=1:
                raise ValueError('Neural response policy/batch differs')
            expected_choice=predicted_choice(snapshot['candidate_ids'],snapshot['teacher_id'],response['scores'])
            if response['choice']!=expected_choice:raise ValueError('Neural argmax/gains are inconsistent')
            for key in ('tensor_build_wall_s','tensor_build_cpu_s','forward_wall_s','forward_cpu_s'):
                if type(response[key]) not in (float,int) or not 0<=response[key]<float('inf'):
                    raise ValueError('Invalid neural timing')
            response['roundtrip_wall_s']=time.monotonic()-start;return response
        except BaseException:
            self.disable();raise

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:self.disable()
        for stream in (self.process.stdin,self.process.stdout,self.process.stderr):
            if not stream.closed:stream.close()
