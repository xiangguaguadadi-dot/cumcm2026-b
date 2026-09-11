"""Measured tensor/runtime probe, explicitly not full policy/environment timing."""
from __future__ import annotations
import json
import platform
import resource
import statistics
import sys
import time
from pathlib import Path

t_import=time.perf_counter()
import torch
torch_import_s=time.perf_counter()-t_import
import numpy as np
EXEC_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(EXEC_ROOT))
from shared import CandidateNetwork

def percentile(values,p):
    return float(np.quantile(values,p))

def probe(device,k,batch_size):
    torch.manual_seed(44)
    model=CandidateNetwork().to(device)
    data=dict(global_features=torch.randn(batch_size,16,device=device),
              candidate_features=torch.randn(batch_size,k,16,device=device),
              channel_features=torch.randn(batch_size,20,12,device=device),
              mask=torch.ones(batch_size,k,dtype=torch.bool,device=device))
    def sync():
        if device=='mps':torch.mps.synchronize()
    with torch.inference_mode():
        for _ in range(10):model(**data)
        sync();durations=[]
        for _ in range(100):
            start=time.perf_counter();model(**data);sync();durations.append(time.perf_counter()-start)
    # All candidate masks have valid entries; this is not an environment sample.
    train_times=[]
    for _ in range(31):
        model.zero_grad(set_to_none=True);start=time.perf_counter()
        scores,value=model(**data)
        loss=scores.square().mean()+value.square().mean()
        loss.backward();sync();train_times.append(time.perf_counter()-start)
    assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
    return dict(device=device,candidates=k,batch=batch_size,
                forward_p50_ms=1000*percentile(durations,.5),forward_p95_ms=1000*percentile(durations,.95),
                forward_p99_ms=1000*percentile(durations,.99),
                forward_backward_first_ms=1000*train_times[0],
                forward_backward_steady_mean_ms=1000*statistics.mean(train_times[11:]),
                backward_warmup_iterations=11,backward_measured_iterations=20,
                scope='tensor forward/backward only; excludes candidate generation, snapshots and environment')

def main():
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    rows=[];errors=[]
    devices=['cpu']+(['mps'] if torch.backends.mps.is_available() else [])
    for device in devices:
        for batch,k in [(1,32),(1,64),(16,64),(1,128)]:
            try:
                row=probe(device,k,batch);rows.append(row);print(json.dumps(row),flush=True)
            except Exception as exc:
                errors.append(dict(device=device,batch=batch,candidates=k,error=repr(exc)))
    result=dict(python=sys.version,python_executable=sys.executable,platform=platform.platform(),
                torch_version=torch.__version__,numpy_version=np.__version__,torch_import_s=torch_import_s,
                mps_built=torch.backends.mps.is_built(),mps_available=torch.backends.mps.is_available(),
                threads=torch.get_num_threads(),architecture=CandidateNetwork().architecture_record(),
                tensor_results=rows,errors=errors,
                process_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024),
                worlds=0,environment_primitives=0,
                interpretation='Tensor-only diagnostic. K128 is a synthetic capacity probe, not an enabled policy candidate limit.')
    out=EXEC_ROOT/'results/g1_tensor_probe_v2';out.mkdir(parents=True,exist_ok=False)
    (out/'runtime.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
