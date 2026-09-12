"""Evaluator-only whole-task counterfactual rollout at prepared READY boundary.

The original run's while-loop and exit logic are reused verbatim through AST
extraction, without its enter/reset prefix. Teacher branch must match the
original complete episode's exact microsecond cost and clear set on every
sampled state before any label is accepted. No in-progress Python stack is
resumed. Source-service alternatives finish one complete original macro, then
return to this original loop with the identical pre-macro todo set.
"""
import ast,copy,hashlib,json,math,statistics,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
from local_env import LocalEnv,InterfaceOnly
from train_gate import fit,load

def resume_function(policy,out):
    # Same bytes as the original inspection source recorded in model.json;
    # vendored here so a fresh checkout does not need an untracked source.
    path=HERE/'training_sources/q4_parent_for_resume.py'
    tree=ast.parse(path.read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='_di_Solver')
    run=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='run')
    assert run.lineno==policy.ObservationResidualDirectional.run.__code__.co_firstlineno
    assert isinstance(run.body[6],ast.While)
    resume=copy.deepcopy(run);resume.name='resume'
    resume.args.args.extend([ast.arg(arg='todo'),ast.arg(arg='visited')])
    resume.body=[run.body[0]]+run.body[6:]
    module=ast.fix_missing_locations(ast.Module(body=[resume],type_ignores=[]))
    source=ast.unparse(module);(out/'resume_generated.py').write_text(source+'\n')
    namespace=dict(policy._C7._Q4.__dict__)
    exec(compile(module,'<a3-exact-resume>','exec'),namespace)
    return namespace['resume'],dict(source_path=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        resume_sha256=hashlib.sha256((source+'\n').encode()).hexdigest())

def main():
    out=HERE/'results/r6_training';out.mkdir(exist_ok=False)
    policy=load(HERE/'snapshots/r3.py','a3_whole_task_teacher')
    worlds=load(ROOT/'experiments/20260911_rl_execution/data/worlds.py','a3_whole_worlds')
    resume,provenance=resume_function(policy,out)
    registry=[worlds.recipe('parallel_v2_a3_r6_'+split,4,i)
        for split,count in [('fit',96),('calibration',48)] for i in range(count)]
    old=set()
    for p in [ROOT/'evaluation/cases_v1.json',ROOT/'experiments/20260911_stage4/exposed_cases.json']:
        old.update(c['seed'] for c in json.loads(p.read_text()))
    for p in (HERE/'results').glob('*training/registry.json'):
        if p.parent==out:continue
        old.update(c['seed'] for c in json.loads(p.read_text()))
    assert not old&{r['seed'] for r in registry}
    (out/'registry.json').write_text(json.dumps(registry,indent=2))
    original_next=policy.ObservationResidualDirectional.spatial_next_task
    original_localize=policy.ObservationResidualDirectional.localize
    original_scan=policy.ObservationResidualDirectional.scan_station
    def next_task(s,todo):
        result=original_next(s,todo)
        s._a3_eval_todo=tuple(sorted(todo))
        return result
    def scan(s,index,defer=False):
        result=original_scan(s,index,defer=defer)
        s._a3_eval_visited=getattr(s,'_a3_eval_visited',[])+[index]
        return result
    policy.ObservationResidualDirectional.spatial_next_task=next_task
    policy.ObservationResidualDirectional.scan_station=scan
    samples=[];episodes=[];started=time.monotonic()
    for ix,recipe in enumerate(registry):
        backend=LocalEnv(worlds.instantiate(recipe),recipe['seed'],recipe['noise'],keep_log=False)
        chosen=[]
        def instrument(s,ch):
            if not getattr(s,'_a3_training_branch',False) and len(chosen)<2 and len(s.observations[ch])>=2:
                center,radius=policy._C7._Q4._di_enclosing_circle(s.polygons[ch])
                if 20.<radius<=100. and s._e2_progress.get(ch,0)<9:
                    assert s._active_target is None and not s._sharing
                    proposal=policy._a3_estimate(s.observations[ch],center,s.polygons[ch])
                    if math.dist(center,proposal)>.01:
                        features=policy._a3_features(s,ch,center,radius,proposal)
                        branches=[]
                        for style in ['reference','off','wls']:
                            fork=copy.deepcopy(backend);clone=object.__new__(type(s))
                            clone.__dict__=copy.deepcopy({k:v for k,v in vars(s).items() if k!='env'})
                            clone.env=InterfaceOnly(fork);clone._a3_training_branch=True
                            assert clone.position==fork.position and abs(clone.virtual_time-fork.virtual_time_s)<1e-7
                            prefix_time=clone.virtual_time;before=fork.measures+fork.clear_attempts
                            saved_config=dict(clone.config)
                            if style!='reference':clone.config['a3_style']=style
                            original_localize(clone,ch)
                            clone.config=saved_config
                            resume(clone,set(s._a3_eval_todo),list(getattr(s,'_a3_eval_visited',[])))
                            stats=fork.stats();complete=stats['cleared']==stats['n'] and fork.exit_reason=='user_exit'
                            assert complete and stats['accounting_error_s']<1e-5
                            branches.append(dict(style=style,complete=complete,average_s=stats['average_s'],
                                total_virtual_s=stats['time_s'],prefix_virtual_s=prefix_time,
                                continuation_virtual_s=stats['time_s']-prefix_time,source_count=stats['n'],
                                cleared_channels=sorted(clone.cleared),requests=fork.measures+fork.clear_attempts-before+1))
                        chosen.append(dict(world_id=recipe['world_id'],split=recipe['split'],features=features,
                            channel=ch,radius=radius,branch_results=branches))
            return original_localize(s,ch)
        policy.ObservationResidualDirectional.localize=instrument
        s=policy.Solver(InterfaceOnly(backend),mode=4)
        assert s.config['spatial_route'] and s.config['spatial_ready_radius']>2000.
        s.run();stats=backend.stats();assert stats['cleared']==stats['n'] and backend.exit_reason=='user_exit'
        for row in chosen:
            reference=row['branch_results'][0]
            # Strong no-op equivalence assertion, not merely equal clearance.
            assert reference['total_virtual_s']==stats['time_s'],(recipe['world_id'],reference['total_virtual_s'],stats['time_s'])
            assert reference['cleared_channels']==sorted(s.cleared)
            row['teacher_full_return_exactly_matches']=True
            row['targets']={b['style']:reference['average_s']-b['average_s'] for b in row['branch_results'][1:]}
        samples.extend(chosen);episodes.append(dict(world_id=recipe['world_id'],complete=True,
            average_s=stats['average_s'],actual_requests=stats['measures']+stats['clear_attempts']+2,
            counterfactual_requests=sum(o['requests'] for r in chosen for o in r['branch_results'])))
        if (ix+1)%24==0:print('whole tails',ix+1,'worlds',len(samples),'states',round(time.monotonic()-started,2),flush=True)
    train=[r for r in samples if r['split'].endswith('_fit')];cal=[r for r in samples if r['split'].endswith('_calibration')]
    heads={style:fit([dict(r,target_proxy_s=r['targets'][style]) for r in train]) for style in ['off','wls']}
    scores=[]
    for r in cal:
        pred={style:sum(a*b for a,b in zip(heads[style],r['features'])) for style in heads}
        r['choice']=max(pred,key=pred.get);r['prediction_s_per_source']=pred[r['choice']]
    for threshold in [0.,.01,.03,.1,.25]:
        perworld=[sum(r['targets'][r['choice']] for r in cal if r['world_id']==w and r['prediction_s_per_source']>threshold)/
            sum(r['world_id']==w for r in cal) for w in {r['world_id'] for r in cal}]
        scores.append(dict(threshold=threshold,mean_actual_advantage_s_per_source=statistics.mean(perworld),
            selected=sum(r['prediction_s_per_source']>threshold for r in cal)))
    selected=max(scores,key=lambda r:(r['mean_actual_advantage_s_per_source'],r['threshold']))
    model=dict(schema='a3-whole-task-rollout-gate-v1',heads=heads,threshold=selected['threshold'],features=15,ridge=1.,
        target='actual whole-episode seconds/source difference to frozen R3, terminal N only in evaluator label',
        source_policy='r3',reference_exact_matches=sum(r['teacher_full_return_exactly_matches'] for r in samples),
        fit_worlds=96,calibration_worlds=48,fit_samples=len(train),calibration_samples=len(cal),
        calibration_scores=scores,provenance=provenance,wall_s=time.monotonic()-started)
    for name,obj in [('samples',samples),('episodes',episodes),('model',model)]:
        (out/f'{name}.json').write_text(json.dumps(obj,indent=2))
    print(json.dumps(model,indent=2))
if __name__=='__main__':main()
