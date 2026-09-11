"""Collect the single shared pure-C7 corpus once; resume durable episodes."""
from common import *

def main():
    plan=json.loads((EXEC/'data/g2_plan.json').read_text());out=EXEC/'results/g2_shared_demo'
    out.mkdir(parents=True,exist_ok=True);rows=[];start=time.perf_counter()
    existing={r['world_id']:r for r in (json.loads(l) for l in (out/'rows.jsonl').read_text().splitlines())} if (out/'rows.jsonl').exists() else {}
    for i,w in enumerate(plan['demonstrations']):
        path=out/'episodes'/f"q{w['mode']}_{w['index']:04d}.json.gz"
        if w['world_id'] in existing:
            row=existing[w['world_id']]
            if sha(path)!=row['storage']['sha256']:raise RuntimeError('Shared demonstration hash changed')
        else:
            if path.exists():raise RuntimeError('Orphan completed demonstration requires ledger recovery, never blind reexecution')
            started=path.with_suffix('.started.json')
            if started.exists():raise RuntimeError('An interrupted execution is recorded; do not reexecute with unknown original cost')
            dump(started,dict(world_id=w['world_id'],status='execution_started',reserved_calls=COMPLETE_EPISODE_RESERVE))
            entry=execute(w,teacher_selector,'g2_shared_c7_teacher')
            stored=save_episode(path,entry);row=row_of(entry,stored)
            append(out/'rows.jsonl',row);del entry
            dump(started,dict(world_id=w['world_id'],status='completed_and_saved',actual_calls=row['business_primitives']))
        rows.append(row)
        if not row['success'] or row['fallback_reason'] or row['teacher_matches']!=row['decisions'] or row.get('validation_errors'):
            dump(out/'failure.json',row)
            raise RuntimeError('Shared demonstration was not a pure successful C7 trajectory; retained, stop G2')
        if (i+1)%32==0:print(json.dumps({'stage':'shared_demo','episodes':i+1,'calls':sum(r['business_primitives'] for r in rows)}),flush=True)
    summary=aggregate(rows);summary.update(plan_sha256=sha(EXEC/'data/g2_plan.json'),wall_time_this_invocation_s=time.perf_counter()-start,
        all_pure_teacher=True,source_truth_used_only_after_terminal=True,corpus_collections=1)
    dump(out/'summary.json',summary);print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
