"""Registered <=24-world, <=100000-call complete pipeline resource diagnosis."""
from __future__ import annotations
import argparse
import json
import random
import time
from pathlib import Path
from common import *
import torch
from shared import CandidateNetwork
from ppo.trainer import BCTrainer, BCConfig, PPOTrainer, episode_from_core
from q_learning.trainer import QTrainer
from q_learning.replay import replay_from_episode

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--resume',action='store_true');a=ap.parse_args()
    out=Path(a.out).resolve()
    if out.exists() and not a.resume: raise RuntimeError('Use a new output directory or explicit resume')
    out.mkdir(parents=True,exist_ok=True)
    if (out/'summary.json').exists():raise RuntimeError('This diagnostic is already complete')
    torch.set_num_threads(1);torch.manual_seed(71101)
    worlds=[r for r in json.loads((EXEC/'data/initial_registry.json').read_text())['worlds'] if r['split']=='g1_resource']
    dump(out/'manifest.json',dict(worlds=worlds,primitive_cap=100000,
        admission_reserve_per_episode=COMPLETE_EPISODE_RESERVE,bc_train_worlds=[w['world_id'] for w in worlds[:12]],
        bc_diagnostic_holdout=[w['world_id'] for w in worlds[12:]],
        bc_config={'epochs':1,'passes':8,'batch_episodes':4},seed=71101,
        scope='G1 diagnostic only; no G2 data or final test; holdout becomes exposed diagnostic after reading',
        resource_gate='All planned complete, finite updates, peak RSS <16 GiB and observed max episode <120s; empirical engineering screen, not deadline theorem'))
    rows=[];paths=[];timings={k:[] for k in ('snapshot_build_s','selector_s','prepare_to_macro_s')}
    previous_rows={r['storage']['path']:r for r in (json.loads(l) for l in (out/'rows.jsonl').read_text().splitlines())} if (out/'rows.jsonl').exists() else {}
    spent=sum(read_episode(p)['business_primitives'] for p in (out/'episodes').glob('*.json.gz'))
    stage_start=time.perf_counter()
    def collect(w,sel,label):
        nonlocal spent
        path=out/'episodes'/f"{label}_q{w['mode']}_{w['index']:03d}.json.gz"
        key=str(path.relative_to(EXEC))
        if path.exists():
            entry=read_episode(path)
            stored=previous_rows.get(key,{}).get('storage')
            if stored is None:
                data=gzip.decompress(path.read_bytes())
                stored=dict(path=key,sha256=sha(path),content_sha256=hashlib.sha256(data).hexdigest(),
                    raw_json_bytes=len(data),gzip_bytes=path.stat().st_size,json_encode_s=0,gzip_s=0,write_s=0,
                    storage_timing_unavailable='First episode saved before path-display exception; recovered without reexecution')
        else:
            if spent+COMPLETE_EPISODE_RESERVE>100000:
                raise RuntimeError('G1 admission stopped to retain complete-episode reserve')
            entry=execute(w,sel,label);spent+=entry['business_primitives']
            stored=save_episode(path,entry)
        row=row_of(entry,stored);rows.append(row)
        if key not in previous_rows:append(out/'rows.jsonl',row)
        for d in (entry['raw'] or {}).get('decisions',[]):
            for key in timings:timings[key].append(d[key])
        return entry,EXEC/stored['path']
    for i,w in enumerate(worlds):
        entry,path=collect(w,teacher_selector,'teacher');paths.append(path)
        if not rows[-1]['success']:raise RuntimeError('Teacher diagnostic failure saved')
        del entry
    bc=BCTrainer(CandidateNetwork(),config=BCConfig(epochs=1),seed=71101)
    def imitation_accuracy(selected_paths):
        correct=total=0
        for p in selected_paths:
            raw=read_episode(p)['raw']
            for d in raw['decisions']:
                correct+=bc.select(d['snapshot']).index==d['snapshot']['teacher_index'];total+=1
        return {'correct':correct,'decisions':total,'accuracy':correct/total if total else None}
    before=imitation_accuracy(paths[12:]);train_log=[];start=time.perf_counter();rng=random.Random(71102)
    for epoch in range(8):
        order=list(paths[:12]);rng.shuffle(order)
        for i in range(0,len(order),4):
            load_start=time.perf_counter();batch=[read_episode(p)['raw'] for p in order[i:i+4]]
            loaded=time.perf_counter();metrics=bc.update(batch)
            train_log.append(dict(epoch=epoch,load_s=loaded-load_start,update_s=time.perf_counter()-loaded,**metrics))
            del batch
    bc_wall=time.perf_counter()-start;after=imitation_accuracy(paths[12:])
    dump(out/'bc_diagnostic.json',dict(before=before,after=after,training_wall_s=bc_wall,updates=train_log))
    # Eight complete saved episodes validate load -> immutable Q replay -> MC/TD
    # update, without generating any additional world or interface request.
    qnet=CandidateNetwork();qnet.load_state_dict(bc.model.state_dict())
    q=QTrainer(qnet,bc.model);q_replay=[];replay_start=time.perf_counter()
    for p in paths[:8]:
        entry=read_episode(p);raw=entry['raw'];labels=entry['terminal_labels']
        q.register_training_snapshots((d['snapshot'] for d in raw['decisions']),source='shared_c7_demo')
        q_replay.append(replay_from_episode(raw,labels['true_n'],success=labels['success'],episode_id=entry['world_id']))
        del entry,raw
    replay_ready=time.perf_counter();mc=q.update(q_replay,kind='mc');q.sync_target();td=q.update(q_replay,kind='td')
    dump(out/'q_replay_probe.json',dict(load_and_conversion_s=replay_ready-replay_start,
        two_update_s=time.perf_counter()-replay_ready,mc=mc,td=td,peak_process_mib=peak_mib(),
        scope='8 reused G1 teacher episodes; 2 diagnostic optimizer steps; zero additional interactions'))
    del q_replay,q,qnet
    for i,w in enumerate(worlds):
        for label,sel in [('bc',lambda s:bc.select(s).as_core_choice()),('greedy',greedy_selector)]:
            entry,path=collect(w,sel,label);del entry
        if (i+1)%4==0:print(json.dumps({'stage':'g1','worlds':i+1,'executions':len(rows),'calls':sum(r['business_primitives'] for r in rows)}),flush=True)
    # PPO actual on-policy rollout/update on an already registered world.
    # This diagnostic counts its repeated execution and is not reused by G2.
    pnet=CandidateNetwork();pnet.load_state_dict(bc.model.state_dict());ppo=PPOTrainer(pnet,seed=71103)
    entry,path=collect(worlds[0],lambda s:ppo.select(s).as_core_choice(),'ppo_update_probe')
    begin=time.perf_counter();pe=episode_from_core(entry['raw'],true_n=entry['terminal_labels']['true_n']);pm=ppo.update([pe])
    dump(out/'ppo_update_probe.json',dict(update=pm,conversion_and_update_s=time.perf_counter()-begin,
        scope='one repeated registered G1 world; on-policy diagnostic; not G2 training'))
    summary=aggregate(rows)
    summary.update(wall_time_this_invocation_s=time.perf_counter()-stage_start,complete_pipeline_timings_ms={k:distribution(v,1000) for k,v in timings.items()},
        bc_holdout_before=before,bc_holdout_after=after,peak_process_mib=peak_mib(),
        actual_optimizer_steps={'bc':sum(x.get('optimizer_steps',1) for x in train_log),'q_mc':1,'q_td':1,'ppo':pm.get('optimizer_steps',4)},
        local_only=True,selected_device='cpu',g2_data_generated=0)
    summary['passed']=bool(not summary['failures'] and len(rows)==73 and summary['business_primitives']<=100000 and peak_mib()<16384 and max(r['execution_wall_s'] for r in rows)<120)
    dump(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
    return 0 if summary['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
