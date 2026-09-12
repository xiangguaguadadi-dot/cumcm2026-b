"""Evaluator-only measured source-completion rollouts for local action labels.

Both alternatives start from identical detached public controller state and
private simulator forks. Each executes clear(target), measure(target) upon
failure, then the original finite source-service controller until that source
is cleared. This is a LOCAL continuation policy, not the original whole-task
continuation; future routing and incidental source clear value are unmodelled.
Every measure/clear in both tails is charged by the frozen LocalEnv.
"""
import argparse,copy,importlib.util,json,math,statistics,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
from local_env import LocalEnv,InterfaceOnly
from train_gate import fit,load

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--round',default='r3');parser.add_argument('--policy',default='r2')
    parser.add_argument('--rollin',choices=['parent','configured'],default='parent');args=parser.parse_args()
    out=HERE/'results'/f'{args.round}_training';out.mkdir(exist_ok=False)
    policy=load(HERE/'snapshots'/f'{args.policy}.py','a3_collect_'+args.round)
    worlds=load(ROOT/'experiments/20260911_rl_execution/data/worlds.py','a3_worlds_r3')
    registry=[worlds.recipe('parallel_v2_a3_'+args.round+'_'+split,4,i)
        for split,count in [('fit',192),('calibration',96)] for i in range(count)]
    assert len({r['seed'] for r in registry})==len(registry)
    old=set()
    for p in [ROOT/'evaluation/cases_v1.json',ROOT/'experiments/20260911_stage4/exposed_cases.json']:
        old.update(c['seed'] for c in json.loads(p.read_text()))
    for p in (HERE/'results').glob('*training/registry.json'):
        if p.parent==out:continue
        old.update(c['seed'] for c in json.loads(p.read_text()))
    assert not old&{r['seed'] for r in registry}
    (out/'registry.json').write_text(json.dumps(registry,indent=2))
    original_clear=policy.ObservationResidualDirectional.clear
    samples=[];episodes=[];started=time.monotonic()
    for ix,recipe in enumerate(registry):
        backend=LocalEnv(worlds.instantiate(recipe),recipe['seed'],recipe['noise'],keep_log=False)
        chosen=[]
        def instrument(s,p,ch,certified=False):
            if (not getattr(s,'_a3_training_branch',False) and not certified and
                    ch==s._active_target and len(s.observations[ch])>=2 and len(chosen)<4):
                center,radius=policy._C7._Q4._di_enclosing_circle(s.polygons[ch])
                if 20.<radius<=100. and math.dist(p,center)<1e-4:
                    proposal=policy._a3_estimate(s.observations[ch],center,s.polygons[ch])
                    if math.dist(proposal,center)>.01:
                        features=policy._a3_features(s,ch,center,radius,proposal)
                        outcomes=[]
                        for target in [center,proposal]:
                            fork=copy.deepcopy(backend)
                            clone=object.__new__(type(s))
                            clone.__dict__=copy.deepcopy({k:v for k,v in vars(s).items() if k!='env'})
                            clone.env=InterfaceOnly(fork);clone._a3_training_branch=True
                            clone.config['a3_style']='off';before=clone.virtual_time
                            requests_before=fork.measures+fork.clear_attempts
                            cleared_before=set(clone.cleared)
                            # Capture actual public microsecond prefix equality.
                            assert clone.position==fork.position and abs(before-fork.virtual_time_s)<1e-7
                            success=original_clear(clone,target,ch,certified=False)
                            if not success:clone.measure(target,ch)
                            rounds=0
                            while ch not in clone.cleared and rounds<12:
                                clone.localize(ch);rounds+=1
                            complete=ch in clone.cleared
                            outcomes.append(dict(cost_s=clone.virtual_time-before,source_complete=complete,
                                requests=fork.measures+fork.clear_attempts-requests_before,
                                other_channels_cleared=len(clone.cleared-cleared_before-{ch}),rounds=rounds,
                                point=target,accounting_error_s=fork.stats()['accounting_error_s']))
                        assert all(o['source_complete'] and o['accounting_error_s']<1e-5 for o in outcomes)
                        chosen.append(dict(world_id=recipe['world_id'],split=recipe['split'],features=features,
                            channel=ch,radius=radius,branch_results=outcomes,
                            target_proxy_s=outcomes[0]['cost_s']-outcomes[1]['cost_s']))
            return original_clear(s,p,ch,certified=certified)
        policy.ObservationResidualDirectional.clear=instrument
        # R3 roll-in remains the frozen parent, so data changes are attributed
        # to measured source-completion labels, not a hidden on-policy switch.
        config={'a3_style':'off'} if args.rollin=='parent' else {}
        s=policy.Solver(InterfaceOnly(backend),mode=4,**config)
        s.run();stats=backend.stats();assert stats['cleared']==stats['n'] and backend.exit_reason=='user_exit'
        samples.extend(chosen);episodes.append(dict(world_id=recipe['world_id'],complete=True,
            average_s=stats['average_s'],actual_requests=stats['measures']+stats['clear_attempts']+2,
            counterfactual_requests=sum(o['requests'] for r in chosen for o in r['branch_results'])))
        if (ix+1)%48==0:print('source tails',ix+1,'worlds',len(samples),'samples',round(time.monotonic()-started,2),flush=True)
    train=[r for r in samples if r['split'].endswith('_fit')];cal=[r for r in samples if r['split'].endswith('_calibration')]
    weights=fit(train);scores=[]
    for r in cal:r['prediction_s']=sum(a*b for a,b in zip(weights,r['features']))
    for threshold in [0.,1.,2.,5.,10.]:
        perworld=[sum(r['target_proxy_s'] for r in cal if r['world_id']==w and r['prediction_s']>threshold)/
            sum(r['world_id']==w for r in cal) for w in {r['world_id'] for r in cal}]
        scores.append(dict(threshold=threshold,mean_local_advantage_s=statistics.mean(perworld),
            selected=sum(r['prediction_s']>threshold for r in cal)))
    selected=max(scores,key=lambda r:(r['mean_local_advantage_s'],r['threshold']))
    model=dict(schema='a3-local-rollout-ridge-v1',weights=weights,threshold=selected['threshold'],features=15,ridge=1.,
        target='actual virtual seconds(ref local source-completion tail) - seconds(alt tail)',
        tail='clear(target); measure(target) on fail; frozen parent localize until chosen channel success, max12 rounds',
        limitations='Not whole-task rollout; no claim of policy improvement guarantee; incidental other clear value not adjusted',
        fit_worlds=192,calibration_worlds=96,fit_samples=len(train),calibration_samples=len(cal),
        calibration_scores=scores,rollin=args.rollin,rollin_candidate=args.policy,wall_s=time.monotonic()-started)
    for name,obj in [('samples',samples),('episodes',episodes),('model',model)]:
        (out/f'{name}.json').write_text(json.dumps(obj,indent=2))
    print(json.dumps(model,indent=2))
if __name__=='__main__':main()
