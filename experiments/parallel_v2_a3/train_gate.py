"""Evaluator-only counterfactual data collection and pure-Python ridge fit.

The policy hook emits detached public features; this evaluator privately
forks LocalEnv and issues one lawful clear per branch. No source coordinate
or scenario label enters features or fitting. Targets are explicitly a
one-action cost proxy, not whole-task cost-to-go or an optimal RL Q value.
"""
import argparse,copy,hashlib,importlib.util,json,statistics,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
from local_env import LocalEnv,InterfaceOnly

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def solve(A,b):
    A=[r[:]+[v] for r,v in zip(A,b)];n=len(b)
    for i in range(n):
        pivot=max(range(i,n),key=lambda j:abs(A[j][i]));A[i],A[pivot]=A[pivot],A[i]
        scale=A[i][i]
        if abs(scale)<1e-14:raise ValueError('singular ridge')
        A[i]=[x/scale for x in A[i]]
        for j in range(n):
            if j==i:continue
            scale=A[j][i];A[j]=[x-scale*y for x,y in zip(A[j],A[i])]
    return [row[-1] for row in A]

def fit(rows,ridge=1.):
    n=len(rows[0]['features']);A=[[0.]*n for _ in range(n)];b=[0.]*n
    counts={w:sum(r['world_id']==w for r in rows) for w in {r['world_id'] for r in rows}}
    for r in rows:
        weight=1./counts[r['world_id']];x=r['features'];y=r['target_proxy_s']
        for i in range(n):
            b[i]+=weight*x[i]*y
            for j in range(n):A[i][j]+=weight*x[i]*x[j]
    for i in range(n):A[i][i]+=ridge if i else ridge*.01
    return solve(A,b)

def main():
    p=argparse.ArgumentParser();p.add_argument('--round',default='r2');p.add_argument('--candidate',default='r1')
    p.add_argument('--fit-worlds',type=int,default=192);p.add_argument('--cal-worlds',type=int,default=96);a=p.parse_args()
    out=HERE/'results'/f'{a.round}_training';out.mkdir(exist_ok=False)
    policy=load(HERE/'snapshots'/f'{a.candidate}.py','a3_collect')
    worlds=load(ROOT/'experiments/20260911_rl_execution/data/worlds.py','a3_worlds')
    registry=[worlds.recipe(f'parallel_v2_a3_{a.round}_{split}',4,i)
        for split,count in [('fit',a.fit_worlds),('calibration',a.cal_worlds)] for i in range(count)]
    assert len({r['seed'] for r in registry})==len(registry)
    old=[]
    for path in [ROOT/'evaluation/cases_v1.json',ROOT/'experiments/20260911_stage4/exposed_cases.json']:
        old.extend(c['seed'] for c in json.loads(path.read_text()))
    assert not set(old)&{r['seed'] for r in registry}
    (out/'registry.json').write_text(json.dumps(registry,indent=2))
    samples=[];episodes=[];started=time.monotonic()
    for ix,recipe in enumerate(registry):
        env=LocalEnv(worlds.instantiate(recipe),recipe['seed'],recipe['noise'],keep_log=False)
        chosen=[]
        def observe(public):
            if len(chosen)>=6 or __import__('math').dist(public['center'],public['proposal'])<.01:return
            fork_results=[]
            for target in [public['center'],public['proposal']]:
                fork=copy.deepcopy(env);before=fork.virtual_time_s
                result=InterfaceOnly(fork).clear(target[0],target[1],public['channel'])
                assert result.get('accepted') is True
                fork_results.append({'success':result['clear_result']=='success',
                    'cost_s':result['virtual_time_s']-before,'action':'clear','point':target})
            ref,alt=fork_results
            # Preregistered 30 s proxy for recovery following failed clear.
            # Real episode validation below must establish any actual saving.
            target=ref['cost_s']-alt['cost_s']+30.*(int(alt['success'])-int(ref['success']))
            chosen.append(dict(public,world_id=recipe['world_id'],split=recipe['split'],
                branch_results=fork_results,target_proxy_s=target))
        policy._A3_TRAIN_HOOK=observe
        solver=policy.Solver(InterfaceOnly(env),mode=4,a3_style='off')
        result=solver.run();stats=env.stats()
        ok=stats['cleared']==stats['n'] and env.exit_reason=='user_exit'
        assert ok
        samples.extend(chosen);episodes.append(dict(world_id=recipe['world_id'],split=recipe['split'],complete=ok,
            average_s=stats['average_s'],total_virtual_time_s=stats['time_s'],samples=len(chosen),
            actual_requests=stats['measures']+stats['clear_attempts']+2,counterfactual_requests=2*len(chosen)))
        if (ix+1)%48==0:print('collected',ix+1,'worlds',len(samples),'samples',round(time.monotonic()-started,2),flush=True)
    policy._A3_TRAIN_HOOK=None
    train=[r for r in samples if r['split'].endswith('_fit')];cal=[r for r in samples if r['split'].endswith('_calibration')]
    weights=fit(train)
    for r in cal:r['prediction_s']=sum(a*b for a,b in zip(weights,r['features']))
    # Threshold selected only on independent calibration branch costs, before
    # running development episodes. Fixed 5-option policy class, no test tuning.
    scores=[]
    for threshold in [0.,1.,2.,5.,10.]:
        perworld=[]
        for world in {r['world_id'] for r in cal}:
            z=[r for r in cal if r['world_id']==world]
            perworld.append(sum(r['target_proxy_s'] for r in z if r['prediction_s']>threshold)/len(z))
        scores.append(dict(threshold=threshold,mean_proxy_advantage_s=statistics.mean(perworld),
            selected=sum(r['prediction_s']>threshold for r in cal)))
    selected=max(scores,key=lambda r:(r['mean_proxy_advantage_s'],r['threshold']))
    model=dict(schema='a3-linear-cost-gate-v1',weights=weights,threshold=selected['threshold'],
        features=15,ridge=1.,target='cost_ref-cost_alt+30*(success_alt-success_ref), seconds; one-action surrogate',
        fit_worlds=a.fit_worlds,calibration_worlds=a.cal_worlds,fit_samples=len(train),calibration_samples=len(cal),
        calibration_scores=scores,wall_s=time.monotonic()-started)
    for name,obj in [('samples',samples),('episodes',episodes),('model',model)]:
        (out/f'{name}.json').write_text(json.dumps(obj,indent=2))
    print(json.dumps(model,indent=2))
if __name__=='__main__':main()
