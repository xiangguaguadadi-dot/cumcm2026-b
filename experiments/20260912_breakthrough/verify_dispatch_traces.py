"""Re-execute 24 exposed cases to verify task-dispatch request/response parity."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from local_env import InterfaceOnly, LocalEnv, Source
import evaluate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_trace(log):
    return [dict(action=x['action'], request=x['request'],
                 response={k:v for k,v in x['response'].items()
                           if k not in ('real_timestamp_ms', 'remaining_real_duration_s')},
                 error=x.get('error'))
            for x in log]


class RecordingInterface:
    """Record attempted calls too: LocalEnv.log itself omits rejected calls."""
    def __init__(self, backend):
        self.backend=backend
        self.calls=[]

    def invoke(self, action, request):
        record=dict(action=action,request=request,response={},error=None)
        self.calls.append(record)
        try:
            response=getattr(self.backend,action)(**request)
            record['response']=dict(response)
            return response
        except Exception as exc:
            record['error']=type(exc).__name__+': '+str(exc)
            raise

    def enter(self):return self.invoke('enter',{})
    def measure(self,x,y,channel):return self.invoke('measure',dict(x=x,y=y,channel=channel))
    def clear(self,x,y,channel):return self.invoke('clear',dict(x=x,y=y,channel=channel))
    def exit(self):return self.invoke('exit',{})


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--q3', type=Path, required=True)
    p.add_argument('--q4', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    assert not a.out.exists()
    evaluate.verify()
    cases = json.loads((ROOT/'evaluation/cases_v1.json').read_text())
    selected = {}
    for case in cases:
        selected.setdefault((case['mode'],case['group']), case)
    assert len(selected) == 24
    paths = {'final': a.candidate, 'q3': a.q3, 'q4': a.q4}
    modules = {}
    for name, path in paths.items():
        spec = importlib.util.spec_from_file_location(name, path)
        modules[name] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modules[name])
    results = []
    start = time.perf_counter()
    for (mode, group), case in sorted(selected.items()):
        pair = []
        for name in ('final', 'q3' if mode == 3 else 'q4'):
            env = LocalEnv([Source(**s) for s in case['sources']],
                           case['seed'],case['noise'],keep_log=True)
            recorder=RecordingInterface(env)
            error = None
            try:
                modules[name].Solver(InterfaceOnly(recorder),mode=mode,
                                    **modules[name].OPTIMIZED_CONFIGS[mode]).run()
            except Exception as exc:
                error = type(exc).__name__+': '+str(exc)
            if env.started and not env.finished:
                env._finish('strategy_exception' if error else 'missing_exit')
            stats = env.stats()
            trace = canonical_trace(recorder.calls)
            pair.append(dict(name=name, trace=trace, error=error,
                             exit_reason=env.exit_reason,
                             complete=stats['n']==stats['cleared'] and env.exit_reason=='user_exit' and error is None,
                             requests=len(trace),
                             accepted_requests=sum(x['response'].get('accepted') is True for x in trace),
                             stats=stats))
        exact = pair[0]['trace'] == pair[1]['trace']
        results.append(dict(case_id=case['case_id'],mode=mode,group=group,exact_trace=exact,
            all_complete=all(x['complete'] for x in pair),
            runs=[{k:v for k,v in x.items() if k!='trace'} | {
                'trace_sha256':hashlib.sha256(json.dumps(x['trace'],sort_keys=True).encode()).hexdigest()}
                for x in pair], mismatch_traces=None if exact else [x['trace'] for x in pair]))
    result = dict(evidence='Re-executed exposed interface parity sample; not a new holdout',
        selection='first stored case in each of 12 v1 groups per mode, fixed before execution',
        cases=24,actual_runs=48,all_exact=all(r['exact_trace'] for r in results),
        all_complete=all(r['all_complete'] for r in results),
        requests=sum(x['requests'] for r in results for x in r['runs']),
        accepted_requests=sum(x['accepted_requests'] for r in results for x in r['runs']),
        wall_s=time.perf_counter()-start,rows=results,
        excluded_response_fields=['real_timestamp_ms','remaining_real_duration_s'],
        hashes={str(path):sha(path) for path in [*paths.values(),Path(__file__),ROOT/'evaluation/manifest_v1.json']})
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False,indent=2))
    assert result['all_exact'] and result['all_complete']
    evaluate.verify()


if __name__ == '__main__':
    main()
