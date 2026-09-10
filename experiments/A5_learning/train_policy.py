"""Reproducible CEM policy search using generated TRAIN/DEV data only.

Truth exists only in make_training_case and evaluator. A policy receives the
same InterfaceOnly four-call wrapper as deployment; no privileged teacher.
"""
import argparse, copy, hashlib, importlib.util, json, math, random, statistics, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from local_env import Source, LocalEnv, InterfaceOnly


def load_solver(path):
    spec=importlib.util.spec_from_file_location('learned_candidate',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


def make_training_case(seed,mode,index):
    r=random.Random(seed)
    n=r.randint(10,16);chs=r.sample(range(1,21),n)
    nd=0 if mode==3 else r.randint(1,n-1)
    family=index%6
    ca=r.uniform(-math.pi,math.pi);cr=r.uniform(100,1250)
    cx,cy=cr*math.cos(ca),cr*math.sin(ca)
    sources=[]
    for i,ch in enumerate(chs):
        a=r.uniform(-math.pi,math.pi);rad=1800*math.sqrt(r.random())
        if family==1:rad=r.uniform(1680,1800)
        if family==2:
            x,y=cx+r.gauss(0,180),cy+r.gauss(0,180)
            dd=math.hypot(x,y)
            if dd>1799:x,y=x*1799/dd,y*1799/dd
        elif family==3:
            rad=170*math.sqrt(r.random());x,y=rad*math.cos(a),rad*math.sin(a)
        else:x,y=rad*math.cos(a),rad*math.sin(a)
        rx=1000 if family in (1,4) else r.uniform(1000,1500)
        direction=r.uniform(-math.pi,math.pi) if i<nd else None
        if family==1 and direction is not None:direction=math.atan2(y,x)+r.uniform(-.15,.15)
        sources.append(dict(channel=ch,x=x,y=y,radius=rx,direction=direction))
    noise=['uniform','positive','negative','smooth_shared','cell_50','cell_500','smooth'][(index//6)%7]
    return dict(seed=seed,mode=mode,training_family=family,noise=noise,sources=sources)


def run_config(mod,mode,config,cases):
    rows=[];started=time.perf_counter()
    for case in cases:
        env=LocalEnv([Source(**s) for s in case['sources']],case['seed'],case['noise'],keep_log=False)
        error=None;result={}
        try:result=mod.Solver(InterfaceOnly(env),mode=mode,**{**mod.OPTIMIZED_CONFIGS[mode],**config}).run()
        except Exception as e:error=f'{type(e).__name__}: {e}'
        complete=(env.successes==len(case['sources']) and env.exit_reason=='user_exit' and error is None)
        rows.append(dict(seed=case['seed'],mode=mode,noise=case['noise'],family=case['training_family'],complete=complete,
                         cleared=env.successes,n=len(case['sources']),seconds_per_source=env.virtual_time_s/env.successes if env.successes else None,
                         virtual_time_s=env.virtual_time_s,distance_m=env.distance,measures=env.measures,
                         failed_clear=env.clear_attempts-env.successes,error=error))
    complete=all(r['complete'] for r in rows)
    mean=statistics.mean(r['seconds_per_source'] for r in rows) if complete else None
    return dict(complete=complete,mean_s_per_source=mean,wall_s=time.perf_counter()-started,rows=rows)


def search(args):
    mod=load_solver(ROOT/args.solver);out=ROOT/args.out;out.mkdir(parents=True,exist_ok=False)
    bounds={'advance_fraction':(.2,.95),'lateral_fraction':(.015,.35),
            'clear_trial_radius':(20,240),'source_priority':(.4,3.)}
    if args.round>=2:
        bounds.update(priority_uncertainty=(-1.5,1.5),priority_pending=(-1.,1.),source_uncertainty_cost=(-.7,.7))
    if args.round>=3:
        bounds.update(advance_range_slope=(-.45,.45),lateral_range_slope=(-.22,.22))
    names=list(bounds);rng=random.Random(920000+args.round)
    allout=dict(round=args.round,solver_path=args.solver,solver_sha256=hashlib.sha256((ROOT/args.solver).read_bytes()).hexdigest(),
                bounds=bounds,generations=args.generations,population=args.population,elite=3,smoothing=.65,
                training_episodes_per_mode=args.train,development_episodes_per_mode=args.dev,
                split_policy='generated only; fixed v1 never imported; truth evaluator-only',selection_z=args.selection_z,modes={})
    (out/'spec.json').write_text(json.dumps(allout,indent=2))
    for mode in (3,4):
        offset=700000+args.round*100000+mode*10000
        train=[make_training_case(offset+i,mode,i) for i in range(args.train)]
        dev=[make_training_case(offset+20000+i,mode,i+13) for i in range(args.dev)]
        (out/f'cases_m{mode}.json').write_text(json.dumps(dict(train=train,dev=dev),indent=2))
        base={name:mod.OPTIMIZED_CONFIGS[mode].get(name,0.) for name in names}
        def normalize(config):return [(config[k]-bounds[k][0])/(bounds[k][1]-bounds[k][0]) for k in names]
        def unpack(x):return {k:bounds[k][0]+v*(bounds[k][1]-bounds[k][0]) for k,v in zip(names,x)}
        mu=normalize(base);sig=[.22]*len(names);attempts=[]
        log=(out/f'attempts_m{mode}.jsonl').open('w')
        def attempt(config,generation,kind='train',tid=None):
            tid=tid if tid is not None else len(attempts)
            result=run_config(mod,mode,config,train if kind=='train' else dev)
            rec=dict(attempt=tid,mode=mode,generation=generation,split=kind,config=config,**result)
            log.write(json.dumps(rec)+'\n');log.flush()
            if kind=='train':attempts.append(rec)
            return rec
        current=attempt(base,-1)
        print(f'm{mode} baseline train {current["mean_s_per_source"]:.4f}, {current["wall_s"]:.2f}s',flush=True)
        if args.baseline_only:
            allout['modes'][mode]=dict(baseline=current)
            log.close();continue
        for generation in range(args.generations):
            fresh=[]
            for j in range(args.population):
                x=[max(0.,min(1.,rng.gauss(m,s))) for m,s in zip(mu,sig)]
                fresh.append(attempt(unpack(x),generation))
            ranked=sorted([x for x in fresh+[current] if x['complete']],key=lambda z:z['mean_s_per_source'])
            if not ranked:raise RuntimeError('No complete training candidate')
            elite=ranked[:3];current=ranked[0]
            elite_x=[normalize(x['config']) for x in elite]
            next_mu=[statistics.mean(v[i] for v in elite_x) for i in range(len(mu))]
            next_sig=[statistics.pstdev(v[i] for v in elite_x) for i in range(len(mu))]
            mu=[.65*n+.35*m for n,m in zip(next_mu,mu)]
            sig=[max(.035,.65*n+.35*s) for n,s in zip(next_sig,sig)]
            print(f'm{mode} generation {generation+1} best_train {current["mean_s_per_source"]:.4f} params {current["config"]}',flush=True)
        unique=[];seen=set()
        for x in sorted([x for x in attempts if x['complete']],key=lambda z:z['mean_s_per_source']):
            key=json.dumps(x['config'],sort_keys=True)
            if key in seen:continue
            seen.add(key);unique.append(x)
            if len(unique)>=5:break
        if not any(x['config']==base for x in unique):unique.append(attempts[0])
        validations=[attempt(x['config'],x['generation'],'dev',x['attempt']) for x in unique]
        viable=[x for x in validations if x['complete']]
        if not viable:raise RuntimeError('No complete development candidate')
        baseline_dev=next(v for v in validations if v['config']==base)
        for v in validations:
            if v['complete'] and baseline_dev['complete']:
                differences=[b['seconds_per_source']-c['seconds_per_source'] for b,c in zip(baseline_dev['rows'],v['rows'])]
                advantage=statistics.mean(differences)
                se=statistics.stdev(differences)/math.sqrt(len(differences)) if len(differences)>1 else 0.
                v['paired_advantage_s']=advantage;v['paired_standard_error_s']=se
                v['passes_development_gate']=v['config']==base or advantage>args.selection_z*se
            else:v['passes_development_gate']=False
        viable=[v for v in viable if v['passes_development_gate']]
        best=min(viable,key=lambda z:z['mean_s_per_source'])
        allout['modes'][mode]=dict(config=best['config'],selected_attempt=best['attempt'],dev_mean_s_per_source=best['mean_s_per_source'],
                                  train_attempts=len(attempts),dev_attempts=len(validations),total_task_runs=len(attempts)*len(train)+len(validations)*len(dev),
                                  baseline_dev_mean_s_per_source=next((v['mean_s_per_source'] for v in validations if v['config']==base),None),
                                  validation_summary=[{k:v for k,v in x.items() if k!='rows'} for x in validations])
        print(f'm{mode} SELECTED development {best["mean_s_per_source"]:.4f} {best["config"]}',flush=True)
        log.close()
        (out/'selected.json').write_text(json.dumps(allout,indent=2))
    (out/'selected.json').write_text(json.dumps(allout,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--round',type=int,default=1);p.add_argument('--solver',default='solver.py')
    p.add_argument('--out',required=True);p.add_argument('--generations',type=int,default=4);p.add_argument('--population',type=int,default=12)
    p.add_argument('--train',type=int,default=48);p.add_argument('--dev',type=int,default=72);p.add_argument('--baseline-only',action='store_true');p.add_argument('--selection-z',type=float,default=0.)
    search(p.parse_args())
