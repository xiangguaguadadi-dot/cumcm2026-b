"""Freeze all trained checkpoints, then evaluate the registered selection worlds.

This script never trains, extends Q feature ranges, or creates a final-test set.
Complete raw trajectories and failed runs are saved before any integrity stop.
"""
from __future__ import annotations
import argparse
import platform
from common import *
import torch
from shared import CandidateNetwork
from ppo.trainer import BCTrainer, BCConfig, PPOTrainer
from q_learning.trainer import QTrainer

FREEZE=EXEC/'data/selection_freeze.json'

def verify_physics():
    record=json.loads((EXEC/'data/runtime_dependency_freeze.json').read_text())
    bad=[p for p,h in record['files'].items() if sha(REPO/p)!=h]
    if bad:raise RuntimeError('Physical environment/data dependency changed: '+str(bad))

def runtime_hashes():
    paths=[EXEC/'shared.py',EXEC/'runners/common.py',Path(__file__),EXEC/'data/worlds.py',REPO/'local_env.py',
        REPO/'experiments/20260911_stage4/combination/geometry_fusions/C7_both.py']
    paths += [p for folder in ('core','ppo','q_learning') for p in (EXEC/folder).glob('*.py')]
    return {str(p.relative_to(REPO)):sha(p) for p in paths}

def software_identity():
    return {'python':sys.version,'torch':str(torch.__version__),'platform':platform.platform(),
        'torch_threads':torch.get_num_threads(),'device':'cpu'}

def verify_selection_freeze(freeze):
    if sha(EXEC/'data/runtime_dependency_freeze.json')!=freeze['physics_freeze_sha256']:
        raise RuntimeError('Frozen physical dependency record changed')
    verify_physics()
    if sha(EXEC/'data/g2_plan.json')!=freeze['plan_sha256'] or runtime_hashes()!=freeze['runtime_sha256']:
        raise RuntimeError('Selection freeze no longer matches the implementation/plan')
    if software_identity()!=freeze['software_identity']:
        raise RuntimeError('Python/PyTorch/platform selection runtime changed')

def freeze_all(plan):
    verify_physics()
    if FREEZE.exists():raise RuntimeError('Selection freeze already exists; never overwrite it')
    models=[];baselines=[dict(model_id=name,algorithm=name,seed=None,checkpoint=None)
        for name in ('original_c7','teacher_wrapper','same_candidates_greedy')]
    training_summaries={}
    for seed in plan['initialization_seeds']:
        base=EXEC/f'results/g2/init_{seed}'
        if not (base/'complete.json').exists():raise RuntimeError('Training is not complete for seed '+str(seed))
        manifest=json.loads((base/'manifest.json').read_text())
        if manifest['plan_sha256']!=sha(EXEC/'data/g2_plan.json'):raise RuntimeError('Training plan changed')
        for p,h in manifest['runtime_sha256'].items():
            if sha(EXEC/p)!=h:raise RuntimeError('Training runtime changed after collection: '+p)
        bcpath=base/'bc/final.pt'
        bcsummary=json.loads((base/'bc/summary.json').read_text())
        if sha(bcpath)!=bcsummary['sha256']:raise RuntimeError('BC checkpoint changed')
        baselines.append(dict(model_id=f'bc_init{seed}',algorithm='bc',seed=seed,
            checkpoint={'path':str(bcpath.relative_to(EXEC)),'sha256':sha(bcpath),'episodes':0}))
        for algorithm in ('ppo','q'):
            directory=base/algorithm;summary=json.loads((directory/'summary.json').read_text())
            if summary['episode_executions']>1024 or summary['business_primitives']>1000000:
                raise RuntimeError('Training budget exceeded')
            index=json.loads((directory/'checkpoints.json').read_text()) if (directory/'checkpoints.json').exists() else []
            if len(index)>4 or len({r['episodes'] for r in index})!=len(index):raise RuntimeError('Too many checkpoint evaluations proposed')
            for r in index:
                if r['episodes'] not in plan[algorithm]['checkpoint_episodes'] or sha(EXEC/r['path'])!=r['sha256']:
                    raise RuntimeError('Unregistered or changed checkpoint')
                models.append(dict(model_id=f"{algorithm}_init{seed}_ep{r['episodes']:04d}",
                    algorithm=algorithm,seed=seed,checkpoint=r))
            training_summaries[f'{algorithm}_init{seed}']={'summary':summary,'sha256':sha(directory/'summary.json'),
                'rows_sha256':sha(directory/'rows.jsonl'),'missing_planned_checkpoints':sorted(set(plan[algorithm]['checkpoint_episodes'])-{r['episodes'] for r in index})}
    freeze=dict(version='registered_selection_freeze_v1',plan_sha256=sha(EXEC/'data/g2_plan.json'),
        baselines=baselines,models=models,training_summaries=training_summaries,
        selection_worlds=plan['selection'],runtime_sha256=runtime_hashes(),
        software_identity=software_identity(),
        physics_freeze_sha256=sha(EXEC/'data/runtime_dependency_freeze.json'),
        frozen_unix_s=time.time(),final_test_worlds=0,default_solver_replacement=False)
    dump(FREEZE,freeze);print(json.dumps({'models':len(models),'baselines':len(baselines),'worlds_each':192,'freeze_sha256':sha(FREEZE)}),flush=True)

def load_selector(record):
    algorithm=record['algorithm']
    if algorithm=='original_c7':return None,True
    if algorithm=='teacher_wrapper':return teacher_selector,False
    if algorithm=='same_candidates_greedy':return greedy_selector,False
    cp=record['checkpoint'];path=EXEC/cp['path']
    if sha(path)!=cp['sha256']:raise RuntimeError('Frozen checkpoint hash changed')
    state=torch.load(path,map_location='cpu',weights_only=False)
    if state['algorithm']!=algorithm or state['seed']!=record['seed']:raise RuntimeError('Checkpoint algorithm/initialization mismatch')
    if algorithm in ('ppo','q') and state.get('completed_new_episodes')!=cp['episodes']:
        raise RuntimeError('Checkpoint internal training position disagrees with index')
    if algorithm=='q':
        trainer=QTrainer.from_checkpoint(state['trainer'],device='cpu')
        return trainer.make_selector(training=False),False
    if algorithm=='ppo':
        trainer=PPOTrainer(CandidateNetwork(),seed=0)
        trainer.load_state_dict(state['trainer'])
        return lambda s:trainer.select(s,deterministic=True).as_core_choice(),False
    trainer=BCTrainer(CandidateNetwork(),config=BCConfig(epochs=1),seed=0)
    trainer.load_state_dict(state['trainer'])
    return lambda s:trainer.select(s).as_core_choice(),False

def execute_logged_c7(w,label):
    """Keep the original baseline's public request log as well as its summary.

    This evaluator-specific adapter leaves the running training runtime intact.
    The original solver still receives only its four interface callables.
    """
    env=LocalEnv(instantiate(w),seed=w['seed'],noise=w['noise'],keep_log=True)
    calls={k:0 for k in ('enter','measure','clear','exit')}
    class Backend:
        def enter(self):calls['enter']+=1;return env.enter()
        def measure(self,x,y,ch):calls['measure']+=1;return env.measure(x,y,ch)
        def clear(self,x,y,ch):calls['clear']+=1;return env.clear(x,y,ch)
        def exit(self):calls['exit']+=1;return env.exit()
    start=time.perf_counter();error=None;raw=None
    try:raw=load_c7().Solver(InterfaceOnly(Backend()),mode=w['mode']).run()
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    elapsed=time.perf_counter()-start
    stats=env.stats()  # first terminal truth read, after the original policy ends
    success=bool(error is None and env.finished and env.exit_reason=='user_exit' and stats['cleared']==stats['n'])
    return dict(world_id=w['world_id'],recipe=w,label=label,raw=raw,
        terminal_labels=dict(true_n=stats['n'],success=success,stats=stats,exit_reason=env.exit_reason,
            error=error,validation_errors=[],integrity_valid=True),
        actual_calls=calls,business_primitives=sum(calls.values()),execution_wall_s=elapsed,
        peak_process_mib=peak_mib(),baseline_primitive_log=env.log,
        baseline_log_scope='All accepted original-C7 public business requests; no fabricated macro decisions')

def evaluate_one(record,freeze):
    verify_selection_freeze(freeze)
    base=EXEC/'results/g2_selection'/('models' if record['algorithm'] in ('q','ppo') else 'baselines')/record['model_id']
    base.mkdir(parents=True,exist_ok=True)
    expected=dict(**record,selection_freeze_sha256=sha(FREEZE),world_count=192,
        deployment=True,training_exploration=False,feature_range_extended=False)
    if (base/'manifest.json').exists():
        if json.loads((base/'manifest.json').read_text())!=expected:raise RuntimeError('Selection resume manifest changed')
    else:dump(base/'manifest.json',expected)
    if record['checkpoint'] and sha(EXEC/record['checkpoint']['path'])!=record['checkpoint']['sha256']:
        raise RuntimeError('Checkpoint changed before selection part/resume')
    if (base/'summary.json').exists():
        completed=json.loads((base/'summary.json').read_text())
        if sha(base/'rows.jsonl')!=completed['rows_sha256']:
            raise RuntimeError('Completed selection ledger changed')
        return
    oldrows=[json.loads(l) for l in (base/'rows.jsonl').read_text().splitlines()] if (base/'rows.jsonl').exists() else []
    wanted={w['world_id'] for w in freeze['selection_worlds']}
    if len({r['world_id'] for r in oldrows})!=len(oldrows) or any(r['world_id'] not in wanted or r['label']!=record['model_id'] for r in oldrows):
        raise RuntimeError('Duplicate, unregistered, or wrong-model saved selection row')
    previous={r['world_id']:r for r in oldrows}
    selector,original=load_selector(record);rows=[];start=time.perf_counter()
    timing={k:[] for k in ('snapshot_build_s','selector_s','prepare_to_macro_s','compute_since_previous_response_s','backend_call_s')}
    for i,w in enumerate(freeze['selection_worlds']):
        path=base/'episodes'/f"q{w['mode']}_{w['index']:04d}.json.gz";marker=path.with_suffix('.started.json')
        if w['world_id'] in previous:
            row=previous[w['world_id']];entry=read_episode(path,expected_sha256=row['storage']['sha256'])
        elif path.exists():
            entry=read_episode(path)
            if entry['world_id']!=w['world_id'] or entry['recipe']!=w or entry['label']!=record['model_id'] or entry.get('frozen_model')!=record:
                raise RuntimeError('Orphan selection archive identity mismatch')
            row=row_of(entry,recover_storage(path));append(base/'rows.jsonl',row)
        else:
            if marker.exists():raise RuntimeError('Interrupted selection execution has unresolved cost; refuse silent reexecution')
            dump(marker,dict(world_id=w['world_id'],status='started',reserved_call_bound=COMPLETE_EPISODE_RESERVE if not original else None))
            entry=(execute_logged_c7(w,record['model_id']) if original
                   else execute(w,selector,record['model_id']))
            entry['frozen_model']=record
            storage=save_episode(path,entry);row=row_of(entry,storage);append(base/'rows.jsonl',row)
            dump(marker,dict(world_id=w['world_id'],status='completed_and_saved',actual_calls=row['business_primitives']))
        if entry['world_id']!=w['world_id'] or entry['recipe']!=w or entry['label']!=record['model_id'] or entry.get('frozen_model')!=record:
            raise RuntimeError('Saved trajectory is not bound to this exact world, recipe and frozen model')
        rows.append(row)
        raw=entry['raw'] or {}
        for d in raw.get('decisions',[]):
            for k in ('snapshot_build_s','selector_s','prepare_to_macro_s'):timing[k].append(d[k])
        for event in raw.get('events',[]):
            for k in ('compute_since_previous_response_s','backend_call_s'):timing[k].append(event[k])
        del entry
        if row.get('validation_errors'):
            dump(base/'integrity_failure.json',row);raise RuntimeError('Selection integrity failure saved before stopping')
        if (i+1)%32==0:print(json.dumps({'model':record['model_id'],'selection_episodes':i+1,
            'failures':sum(not r['success'] for r in rows),'calls':sum(r['business_primitives'] for r in rows)}),flush=True)
    if len(rows)!=192 or {r['world_id'] for r in rows}!=wanted:
        raise RuntimeError('Final selection world coverage is not exactly the registered 192 IDs')
    summary=aggregate(rows);summary.update(**record,wall_time_this_invocation_s=time.perf_counter()-start,
        rows_sha256=sha(base/'rows.jsonl'),
        timing_ms={k:distribution(v,1000) for k,v in timing.items()},
        selection_only=True,official_validation=False,final_blind_validation=False)
    verify_selection_freeze(freeze)
    if record['checkpoint'] and sha(EXEC/record['checkpoint']['path'])!=record['checkpoint']['sha256']:
        raise RuntimeError('Model checkpoint changed during selection')
    dump(base/'summary.json',summary)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--part',choices=['freeze','baselines','initialization'],required=True)
    ap.add_argument('--seed',type=int);args=ap.parse_args();torch.set_num_threads(1)
    plan=json.loads((EXEC/'data/g2_plan.json').read_text())
    if args.part=='freeze':freeze_all(plan);return
    freeze=json.loads(FREEZE.read_text());verify_selection_freeze(freeze)
    if args.part=='baselines':records=freeze['baselines']
    else:
        if args.seed not in plan['initialization_seeds']:raise ValueError('Unregistered initialization')
        records=[r for r in freeze['models'] if r['seed']==args.seed]
    for record in records:evaluate_one(record,freeze)
    print(json.dumps({'part':args.part,'seed':args.seed,'model_count':len(records),'completed':True}),flush=True)
if __name__=='__main__':main()
