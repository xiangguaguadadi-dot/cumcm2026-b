"""One registered independent BC -> PPO/Q initialization, with durable resume.

Full immutable trajectories live in gzip files. Replay samples whole episode
paths, never a transition-weighted population. Every actual execution is saved
before a trainer can reject it. No selection world is instantiated here.
"""
from __future__ import annotations
import argparse
import random
import time
from common import *
import torch
from shared import CandidateNetwork
from ppo.trainer import BCTrainer, BCConfig, PPOTrainer, episode_from_core
from q_learning.trainer import QTrainer
from q_learning.replay import replay_from_episode

EXPECTED_ARCHIVES={}

def verified_read(path):
    key=str(Path(path).resolve())
    if key not in EXPECTED_ARCHIVES:raise RuntimeError('Trajectory is outside the verified training ledger: '+key)
    return read_episode(path,expected_sha256=EXPECTED_ARCHIVES[key])

def save_state(path,state):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp');torch.save(state,temp);temp.replace(path)

def load_state(path):
    # Only checkpoints produced by this local, explicitly registered runner.
    return torch.load(path,map_location='cpu',weights_only=False)

def tuple_tree(value):
    return tuple(tuple_tree(v) for v in value) if isinstance(value,(list,tuple)) else value

def rows_at(out):
    p=Path(out)/'rows.jsonl'
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

def recover_update(out,resume):
    """Recover committed metric logs and account for an interrupted compute attempt."""
    out=Path(out)
    state=load_state(resume) if Path(resume).exists() else {}
    last=state.get('last_update')
    if last:
        log=out/last['log'];seen={json.loads(l).get('commit_id') for l in log.read_text().splitlines()} if log.exists() else set()
        if last['record']['commit_id'] not in seen:append(log,last['record'])
    pending=out/'pending_update.json'
    if pending.exists():
        record=json.loads(pending.read_text())
        if not last or record['commit_id']!=last['record']['commit_id']:
            append(out/'interrupted_compute.jsonl',{**record,
                'actual_optimizer_steps':'unknown between 0 and registered upper bound',
                'compute_wall_s':'unavailable after interruption',
                'environment_reexecution':False,'recovery':'Restore pre-update checkpoint and recompute saved batch'})
        pending.unlink()

def start_update(out,commit_id,optimizer_steps_upper_bound):
    dump(Path(out)/'pending_update.json',dict(commit_id=commit_id,
        optimizer_steps_upper_bound=optimizer_steps_upper_bound,started_unix_s=time.time()))

def commit_update(out,resume,state,log,record):
    state['last_update']={'log':log,'record':record}
    save_state(resume,state)
    append(Path(out)/log,record)
    (Path(out)/'pending_update.json').unlink(missing_ok=True)

def read_replay(path):
    entry=verified_read(path);labels=entry['terminal_labels']
    return replay_from_episode(entry['raw'],labels['true_n'],success=labels['success'],episode_id=entry['world_id'])

def check_saved_integrity(row):
    if row.get('validation_errors'):
        raise RuntimeError('Executed integrity failure retained; training stopped: '+str(row['validation_errors']))
    if row['business_primitives']>COMPLETE_EPISODE_RESERVE:
        raise RuntimeError('Executed episode exceeded the pre-reserved call bound; evidence retained')

def train_bc(base,seed,demos):
    out=base/'bc';out.mkdir(parents=True,exist_ok=True)
    torch.manual_seed(seed);bc=BCTrainer(CandidateNetwork(),config=BCConfig(epochs=1),seed=seed+10)
    cursor=0;measured=0.;steps=0
    recover_update(out,out/'resume.pt')
    if (out/'resume.pt').exists():
        state=load_state(out/'resume.pt');bc.load_state_dict(state['trainer'])
        cursor=state['cursor'];measured=state['training_wall_s'];steps=state['optimizer_steps']
    for epoch in range(8):
        order=list(demos);random.Random(seed+100+epoch).shuffle(order)
        for offset in range(0,len(order),8):
            index=epoch*(len(order)//8)+offset//8
            if index<cursor:continue
            start=time.perf_counter();batch=[verified_read(p)['raw'] for p in order[offset:offset+8]]
            loaded=time.perf_counter();start_update(out,f'bc_{index}',1);metrics=bc.update(batch);elapsed=time.perf_counter()-start
            measured+=elapsed;steps+=metrics['optimizer_steps'];cursor=index+1
            commit_update(out,out/'resume.pt',dict(trainer=bc.state_dict(),cursor=cursor,
                training_wall_s=measured,optimizer_steps=steps),'updates.jsonl',
                dict(commit_id=f'bc_{index}',batch_index=index,epoch=epoch,load_s=loaded-start,
                load_and_update_s=elapsed,peak_process_mib=peak_mib(),**metrics))
            del batch
        print(json.dumps({'seed':seed,'stage':'bc','completed_passes':epoch+1,'optimizer_steps':steps}),flush=True)
    if not (out/'final.pt').exists():save_state(out/'final.pt',dict(seed=seed,algorithm='bc',trainer=bc.state_dict()))
    dump(out/'summary.json',dict(seed=seed,shared_demonstrations=len(demos),new_episodes=0,
        optimizer_steps=steps,passes=8,load_and_training_wall_s=measured,peak_process_mib=peak_mib(),
        checkpoint='final.pt',sha256=sha(out/'final.pt')))
    return bc

def checkpoint(out,algorithm,seed,completed,trainer_state):
    path=out/'checkpoints'/f'episode_{completed:04d}.pt'
    if not path.exists():save_state(path,dict(algorithm=algorithm,seed=seed,
        completed_new_episodes=completed,trainer=trainer_state))
    records=json.loads((out/'checkpoints.json').read_text()) if (out/'checkpoints.json').exists() else []
    if not any(r['episodes']==completed for r in records):
        records.append(dict(algorithm=algorithm,seed=seed,episodes=completed,
            path=str(path.relative_to(EXEC)),sha256=sha(path)))
        dump(out/'checkpoints.json',records)

def collected_episode(out,w,label,selector,after_rng):
    path=out/'episodes'/f"q{w['mode']}_{w['index']:04d}.json.gz"
    if path.exists():
        matching=[r for r in rows_at(out) if r['world_id']==w['world_id']]
        if len(matching)>1:raise RuntimeError('Duplicate completed episode in row ledger')
        if matching:
            row=matching[0];entry=read_episode(path,expected_sha256=row['storage']['sha256'])
        else:
            entry=read_episode(path)
            if entry['world_id']!=w['world_id'] or entry['recipe']!=w or entry['label']!=label:
                raise RuntimeError('Orphan trajectory does not match its registered recipe')
            row=row_of(entry,recover_storage(path));append(out/'rows.jsonl',row)
    else:
        started=path.with_suffix('.started.json')
        if started.exists():raise RuntimeError('Recorded interrupted execution: original call cost must be reconciled before any new execution')
        dump(started,dict(world_id=w['world_id'],label=label,status='execution_started',
            reserved_calls=COMPLETE_EPISODE_RESERVE,started_unix_s=time.time()))
        entry=execute(w,selector,label)
        entry['collector_rng_after']=after_rng()
        storage=save_episode(path,entry);row=row_of(entry,storage)
        append(out/'rows.jsonl',row)
        dump(started,dict(world_id=w['world_id'],status='completed_and_saved',
            actual_calls=entry['business_primitives'],trajectory_sha256=storage['sha256']))
    check_saved_integrity(row)
    EXPECTED_ARCHIVES[str(path.resolve())]=row['storage']['sha256']
    return entry,path

def train_ppo(base,seed,demos,bc,worlds,plan):
    out=base/'ppo';out.mkdir(parents=True,exist_ok=True)
    if (out/'summary.json').exists():return
    model=CandidateNetwork();model.load_state_dict(bc.model.state_dict())
    trainer=PPOTrainer(model,seed=seed+200);completed=0;training_wall=0.;optimizer_steps=0
    recover_update(out,out/'resume.pt')
    if (out/'resume.pt').exists():
        state=load_state(out/'resume.pt');trainer.load_state_dict(state['trainer'])
        completed=state['completed'];training_wall=state['training_wall_s'];optimizer_steps=state['optimizer_steps']
    else:save_state(out/'resume.pt',dict(trainer=trainer.state_dict(),completed=0,training_wall_s=0.,optimizer_steps=0))
    points=plan['ppo']['checkpoint_episodes'];reason='episode_cap'
    if completed in points:checkpoint(out,'ppo',seed,completed,trainer.state_dict())
    while completed<len(worlds):
        batch=[];count=0
        for i in range(completed,min(completed+8,len(worlds))):
            spent=sum(r['business_primitives'] for r in rows_at(out))
            w=worlds[i];expected=out/'episodes'/f"q{w['mode']}_{w['index']:04d}.json.gz"
            if not expected.exists() and spent+COMPLETE_EPISODE_RESERVE>1000000:
                reason='primitive_cap_with_complete_episode_reserve';break
            entry,path=collected_episode(out,w,f'ppo_init{seed}',lambda s:trainer.select(s).as_core_choice(),
                lambda:trainer.generator.get_state().tolist())
            trainer.generator.set_state(torch.tensor(entry['collector_rng_after'],dtype=torch.uint8))
            batch.append(episode_from_core(entry['raw'],true_n=entry['terminal_labels']['true_n']))
            count+=1;del entry
        if not batch:break
        start=time.perf_counter();commit_id=f'ppo_{completed+count}';start_update(out,commit_id,4)
        metrics=trainer.update(batch);elapsed=time.perf_counter()-start
        training_wall+=elapsed;optimizer_steps+=metrics['optimizer_steps'];completed+=count
        commit_update(out,out/'resume.pt',dict(trainer=trainer.state_dict(),completed=completed,
            training_wall_s=training_wall,optimizer_steps=optimizer_steps),'updates.jsonl',
            dict(commit_id=commit_id,completed_new_episodes=completed,update_s=elapsed,peak_process_mib=peak_mib(),**metrics))
        if completed in points:checkpoint(out,'ppo',seed,completed,trainer.state_dict())
        if completed%32==0 or count<8:
            print(json.dumps({'seed':seed,'stage':'ppo','episodes':completed,'calls':sum(r['business_primitives'] for r in rows_at(out))}),flush=True)
        del batch
        if count<8:break
    rows=rows_at(out);summary=aggregate(rows)
    summary.update(seed=seed,algorithm='ppo',completed_training_episodes=completed,
        optimizer_steps=optimizer_steps,optimizer_wall_s=training_wall,stop_reason=reason,
        checkpoint_positions=[r['episodes'] for r in json.loads((out/'checkpoints.json').read_text())] if (out/'checkpoints.json').exists() else [],
        partial_final_batch=completed%8,final_state_sha256=sha(out/'resume.pt'))
    dump(out/'summary.json',summary)

def initialize_q(out,seed,demos,bc):
    network=CandidateNetwork();network.load_state_dict(bc.model.state_dict())
    q=QTrainer(network,bc.model);cursor=0;measured=0.;steps=0
    recover_update(out,out/'mc_resume.pt')
    if (out/'mc_resume.pt').exists():
        state=load_state(out/'mc_resume.pt');q=QTrainer.from_checkpoint(state['trainer'])
        cursor=state['cursor'];measured=state['training_wall_s'];steps=state['optimizer_steps']
    else:
        start=time.perf_counter()
        for p in demos:
            entry=verified_read(p)
            q.register_training_snapshots((d['snapshot'] for d in entry['raw']['decisions']),source='shared_c7_demo')
            del entry
        dump(out/'range_registration.json',dict(shared_demo_episodes=len(demos),wall_time_s=time.perf_counter()-start,
            bounds=q.feature_bounds.to_dict(),source='shared_c7_demo'))
        save_state(out/'mc_resume.pt',dict(trainer=q.checkpoint(),cursor=0,training_wall_s=0.,optimizer_steps=0))
    for epoch in range(4):
        order=list(demos);random.Random(seed+300+epoch).shuffle(order)
        for offset in range(0,len(order),8):
            index=epoch*(len(order)//8)+offset//8
            if index<cursor:continue
            start=time.perf_counter();batch=[read_replay(p) for p in order[offset:offset+8]];loaded=time.perf_counter()
            start_update(out,f'q_mc_{index}',1);metrics=q.update(batch,kind='mc');elapsed=time.perf_counter()-start
            measured+=elapsed;steps+=int(metrics['optimizer_step']);cursor=index+1
            commit_update(out,out/'mc_resume.pt',dict(trainer=q.checkpoint(),cursor=cursor,
                training_wall_s=measured,optimizer_steps=steps),'mc_updates.jsonl',
                dict(commit_id=f'q_mc_{index}',batch_index=index,epoch=epoch,load_convert_s=loaded-start,
                load_and_update_s=elapsed,peak_process_mib=peak_mib(),**metrics))
            del batch
        print(json.dumps({'seed':seed,'stage':'q_mc','completed_passes':epoch+1,'optimizer_steps':steps}),flush=True)
    q.sync_target()
    dump(out/'mc_summary.json',dict(shared_demo_episodes=len(demos),passes=4,optimizer_steps=steps,
        load_and_update_wall_s=measured,peak_process_mib=peak_mib()))
    return q

def train_q(base,seed,demos,bc,worlds,plan):
    out=base/'q';out.mkdir(parents=True,exist_ok=True)
    if (out/'summary.json').exists():return
    completed=0;training_wall=0.;optimizer_steps=0;rng=random.Random(seed+400)
    if (out/'resume.pt').exists():
        recover_update(out,out/'resume.pt')
        state=load_state(out/'resume.pt');q=QTrainer.from_checkpoint(state['trainer'])
        completed=state['completed'];training_wall=state['training_wall_s'];optimizer_steps=state['optimizer_steps']
        rng.setstate(state['replay_rng']);explorer=q.make_selector(training=True,seed=seed+500)
        explorer.rng.setstate(state['explorer_rng'])
    else:
        q=initialize_q(out,seed,demos,bc);explorer=q.make_selector(training=True,seed=seed+500)
        save_state(out/'resume.pt',dict(trainer=q.checkpoint(),completed=0,training_wall_s=0.,optimizer_steps=0,
            replay_rng=rng.getstate(),explorer_rng=explorer.rng.getstate()))
    points=plan['q']['checkpoint_episodes'];reason='episode_cap'
    if completed in points:checkpoint(out,'q',seed,completed,q.checkpoint())
    prior_rows=rows_at(out)
    buffer=list(demos)+[EXEC/r['storage']['path'] for r in prior_rows[:completed]]
    for i in range(completed,len(worlds)):
        spent=sum(r['business_primitives'] for r in rows_at(out));w=worlds[i]
        expected=out/'episodes'/f"q{w['mode']}_{w['index']:04d}.json.gz"
        if not expected.exists() and spent+COMPLETE_EPISODE_RESERVE>1000000:
            reason='primitive_cap_with_complete_episode_reserve';break
        explorer.start_episode(i)
        entry,path=collected_episode(out,w,f'q_init{seed}',explorer,lambda:explorer.rng.getstate())
        explorer.rng.setstate(tuple_tree(entry['collector_rng_after']))
        q.register_training_snapshots((d['snapshot'] for d in entry['raw']['decisions']),source='q_training')
        del entry;buffer.append(path)
        sampled=rng.sample(buffer,min(8,len(buffer)))
        start=time.perf_counter();batch=[read_replay(p) for p in sampled];loaded=time.perf_counter()
        start_update(out,f'q_td_{i+1}',1);metrics=q.update(batch,kind='td');elapsed=time.perf_counter()-start
        completed=i+1;training_wall+=elapsed;optimizer_steps+=int(metrics['optimizer_step'])
        update_record=dict(commit_id=f'q_td_{completed}',completed_new_episodes=completed,
            sampled_episode_paths=[str(p.relative_to(EXEC)) for p in sampled],
            load_convert_s=loaded-start,load_and_update_s=elapsed,peak_process_mib=peak_mib(),**metrics)
        commit_update(out,out/'resume.pt',dict(trainer=q.checkpoint(),completed=completed,
            training_wall_s=training_wall,optimizer_steps=optimizer_steps,
            replay_rng=rng.getstate(),explorer_rng=explorer.rng.getstate()),'updates.jsonl',update_record)
        if completed in points:checkpoint(out,'q',seed,completed,q.checkpoint())
        if completed%32==0:
            print(json.dumps({'seed':seed,'stage':'q','episodes':completed,'calls':sum(r['business_primitives'] for r in rows_at(out))}),flush=True)
        del batch
    rows=rows_at(out);summary=aggregate(rows)
    summary.update(seed=seed,algorithm='q',completed_training_episodes=completed,
        td_optimizer_steps=optimizer_steps,load_convert_optimizer_wall_s=training_wall,stop_reason=reason,
        checkpoint_positions=[r['episodes'] for r in json.loads((out/'checkpoints.json').read_text())] if (out/'checkpoints.json').exists() else [],
        range_revision=q.feature_bounds.revision,range_snapshot_count=q.feature_bounds.snapshot_count,
        final_state_sha256=sha(out/'resume.pt'))
    dump(out/'summary.json',summary)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seed',type=int,required=True);args=ap.parse_args()
    plan=json.loads((EXEC/'data/g2_plan.json').read_text())
    if args.seed not in plan['initialization_seeds']:raise ValueError('Unregistered initialization')
    corpus=json.loads((EXEC/'results/g2_shared_demo/summary.json').read_text())
    if corpus['episode_executions']!=512 or not corpus['all_pure_teacher'] or corpus['failures']:
        raise RuntimeError('Shared demonstration gate incomplete')
    demo_rows=rows_at(EXEC/'results/g2_shared_demo')
    if [r['world_id'] for r in demo_rows]!=[w['world_id'] for w in plan['demonstrations']]:
        raise RuntimeError('Shared demonstration IDs/order do not match the registered recipes')
    demos=[EXEC/r['storage']['path'] for r in demo_rows]
    if len(demos)!=512 or len(set(demos))!=512:raise RuntimeError('Demonstrations are not the one shared corpus')
    torch.set_num_threads(1);base=EXEC/f'results/g2/init_{args.seed}';base.mkdir(parents=True,exist_ok=True)
    for row in demo_rows+rows_at(base/'ppo')+rows_at(base/'q'):
        EXPECTED_ARCHIVES[str((EXEC/row['storage']['path']).resolve())]=row['storage']['sha256']
    runtime_files=[Path(__file__),Path(__file__).with_name('common.py'),EXEC/'shared.py']
    runtime_files += [p for folder in ('core','ppo','q_learning') for p in (EXEC/folder).glob('*.py')]
    expected_manifest=dict(seed=args.seed,plan_sha256=sha(EXEC/'data/g2_plan.json'),
            demonstration_summary_sha256=sha(EXEC/'results/g2_shared_demo/summary.json'),
            demonstration_rows_sha256=sha(EXEC/'results/g2_shared_demo/rows.jsonl'),
            runtime_sha256={str(p.relative_to(EXEC)):sha(p) for p in runtime_files},
            shared_corpus=True,selection_worlds_read=0)
    if (base/'manifest.json').exists():
        if json.loads((base/'manifest.json').read_text())!=expected_manifest:
            raise RuntimeError('Plan, demonstration summary, or runtime source changed; do not resume silently')
    else:dump(base/'manifest.json',expected_manifest)
    start=time.perf_counter()
    try:
        bc=train_bc(base,args.seed,demos)
        train_ppo(base,args.seed,demos,bc,plan['training'][str(args.seed)],plan)
        train_q(base,args.seed,demos,bc,plan['training'][str(args.seed)],plan)
    except Exception as exc:
        dump(base/'execution_error.json',dict(error=type(exc).__name__+': '+str(exc),
            wall_time_this_invocation_s=time.perf_counter()-start,actual_rows_are_retained=True))
        raise
    dump(base/'complete.json',dict(seed=args.seed,wall_time_this_invocation_s=time.perf_counter()-start,
        peak_process_mib=peak_mib(),local_only=True,selection_performed=False,
        interrupted_compute_records=sum(len(p.read_text().splitlines()) for p in base.rglob('interrupted_compute.jsonl'))))
    print(json.dumps({'seed':args.seed,'stage':'complete','wall_time_this_invocation_s':time.perf_counter()-start}),flush=True)
if __name__=='__main__':main()
