"""Frozen neural forward worker. JSON public features in; scores out; no evaluator."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from .torch_runtime import configure
torch=configure()
from .model import CounterfactualModel,EXPECTED_PARAMETER_COUNT
from .features import validate_snapshot,TENSOR_KEYS
from .selection import predicted_choice

def main(checkpoint,expected_sha):
    path=Path(checkpoint).resolve()
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected_sha:raise RuntimeError('Frozen neural checkpoint changed')
    payload=torch.load(path,map_location='cpu',weights_only=True)
    if payload.get('schema')!='bc-rpi-r1-neural-checkpoint-v1':raise ValueError('Unexpected checkpoint schema')
    if payload.get('parameter_count')!=EXPECTED_PARAMETER_COUNT:raise ValueError('Unexpected trainable parameter count')
    root=Path(__file__).resolve().parent
    for key,name in [('model_source_sha256','model.py'),('feature_implementation_sha256','features.py')]:
        if payload.get(key)!=hashlib.sha256((root/name).read_bytes()).hexdigest():
            raise ValueError('Checkpoint fitted under different model/feature implementation')
    model=CounterfactualModel();model.load_state_dict(payload['model_state_dict'],strict=True);model.eval()
    hasher=hashlib.sha256()
    for name,value in sorted(model.state_dict().items()):
        hasher.update(name.encode());hasher.update(value.detach().cpu().contiguous().numpy().tobytes())
    parameter_sha=hasher.hexdigest()
    if parameter_sha!=payload['parameter_sha256']:raise ValueError('Checkpoint tensor/metadata parameter identity differs')
    print(json.dumps(dict(ready=True,checkpoint_sha256=expected_sha,seed=payload['seed'],epoch=payload['epoch'],
        parameter_count=EXPECTED_PARAMETER_COUNT,device='cpu',threads=torch.get_num_threads(),parameter_sha256=parameter_sha,
        model_source_sha256=payload['model_source_sha256'],feature_implementation_sha256=payload['feature_implementation_sha256'])),flush=True)
    for line in sys.stdin:
        request_id=None
        try:
            request=json.loads(line)
            if set(request)!={'request_id','snapshot'}:raise ValueError('Unknown neural request envelope')
            request_id=request['request_id'];snapshot=validate_snapshot(request['snapshot'])
            tensor_start=time.monotonic();tensor_cpu=time.process_time()
            batch={key:torch.tensor(snapshot['features'][key],dtype=torch.bool if key=='active_mask' else torch.float32)
                   for key in TENSOR_KEYS}
            tensor_wall=time.monotonic()-tensor_start;tensor_cpu=time.process_time()-tensor_cpu
            forward_start=time.monotonic();forward_cpu=time.process_time()
            with torch.inference_mode():scores=model(batch).tolist()
            forward_wall=time.monotonic()-forward_start;forward_cpu=time.process_time()-forward_cpu
            choice=predicted_choice(snapshot['candidate_ids'],snapshot['teacher_id'],scores)
            response=dict(ok=True,candidate_ids=snapshot['candidate_ids'],teacher_id=snapshot['teacher_id'],scores=scores,
                choice=choice,checkpoint_sha256=expected_sha,tensor_build_wall_s=tensor_wall,tensor_build_cpu_s=tensor_cpu,
                forward_wall_s=forward_wall,forward_cpu_s=forward_cpu,batch_size=1)
        except MemoryError as exc:response=dict(ok=False,error_type='MemoryError',resource_failure=True,
            error='MemoryError: '+str(exc))
        except Exception as exc:response=dict(ok=False,error_type=type(exc).__name__,resource_failure=False,
            error=type(exc).__name__+': '+str(exc))
        response['request_id']=request_id
        print(json.dumps(response,allow_nan=False,separators=(',',':')),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--sha256',required=True)
    a=p.parse_args();main(a.checkpoint,a.sha256)
