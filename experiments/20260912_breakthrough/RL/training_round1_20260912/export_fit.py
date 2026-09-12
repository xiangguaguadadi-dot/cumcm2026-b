"""Trusted exporter: private collection artifacts -> fit/val-only public dataset.

This process may inspect evaluator handles; the neural fit process never does.
No calibration/development world content is exported or loaded by the fitter.
"""
from __future__ import annotations
import argparse
from .common import ROOT,load,save_new,sha,digest
from .features import build_snapshot
from .collect import terminal_cost,classify_outcome
from implementation.deploy.state import decode
from implementation.evaluator.runtime import ForkHandle

def export(collection,out):
    collection=ROOT/collection;out=ROOT/out
    if out.exists():raise FileExistsError('Use a fresh public fit dataset directory')
    summary=load(collection/'summary.json')
    if summary['status']!='labels_complete_no_fit_yet' or summary['completed_worlds']!=36:
        raise RuntimeError('All 36 complete registered worlds are required before fitting')
    if summary['unknown_cost_calls'] or summary['current_run'] is not None:raise RuntimeError('Collection has unresolved cost')
    manifest=load(ROOT/'world_manifest.json')
    worlds={w['world_id']:w for w in manifest['worlds'] if w['role'] in ('fit','fit_val')}
    rows=load(collection/'world_results.json')['worlds']
    if len(rows)!=36 or {r['world_id'] for r in rows}!=set(worlds):raise ValueError('Fit/val registration mismatch')
    entries=[];bundle_count=0;nonref_count=0;teacher_only=0;zero_worlds=0
    for row in rows:
        world=worlds[row['world_id']]
        if row['status']!='complete' or row['role']!=world['role']:raise ValueError('Incomplete/mixed-role world')
        exported=[]
        for state in row['states']:
            bundle=load(ROOT/state['path']);handle=ForkHandle.from_json(load(ROOT/state['handle_path']));handle.verify(world)
            if bundle['status']!='complete' or bundle['world_sha256']!=world['world_sha256']:
                raise ValueError('Incomplete/misbound bundle')
            if bundle['continuation_policy_sha256']!=summary['continuation_policy_sha256']:
                raise ValueError('Mixed continuation-policy labels')
            snapshot=build_snapshot(handle.prepared,decode(handle.token.interface_public_state)['events'])
            ids=snapshot['candidate_ids'];teacher=snapshot['teacher_id']
            if ids!=bundle['candidate_ids'] or teacher!=bundle['teacher_id']:
                raise ValueError('Public candidate/terminal label alignment differs')
            outcomes=bundle['outcomes']
            if [r['action_id'] for r in outcomes]!=ids:raise ValueError('Incomplete or reordered action bundle')
            costs=[];origins=[]
            for label in outcomes:
                result=load(ROOT/label['path']);classify_outcome(result)
                if result['run_id']!=label['run_id'] or result['true_terminal_n']!=bundle['terminal_n']:
                    raise ValueError('Outcome origin/terminal denominator differs')
                cost=terminal_cost(result,bundle['prefix_virtual_us'])
                if cost!=label['terminal_normalized_suffix_cost']:raise ValueError('Stored complete label cost differs')
                costs.append(cost);origins.append(result['run_id'])
            ref=ids.index(teacher);gains=[costs[ref]-c for c in costs]
            if gains!=[r['paired_gain_to_A0'] for r in outcomes]:raise ValueError('Stored paired gains differ')
            exported.append(dict(snapshot=snapshot,targets_normalized=gains,teacher_index=ref,
                origin_run_ids=origins,reference_origin_run_id=origins[ref],choice_id=bundle['choice_id'],
                source_index=bundle['source_index'],state_index=bundle['state_index'],
                complete_bundle=True,continuation_policy_sha256=summary['continuation_policy_sha256']))
            bundle_count+=1;nonref_count+=len(ids)-1;teacher_only+=len(ids)==1
        if len(exported)!=row['state_count']:raise ValueError('State denominator changed')
        zero_worlds+=not exported
        public=dict(schema='bc-rpi-round1-public-fit-world-v1',world_id=world['world_id'],world_sha256=world['world_sha256'],
            role=world['role'],states=exported,state_count=len(exported),complete=True,
            no_world_truth=True,empty_state_and_world_weight='retained with zero loss')
        path=out/f'{world["role"]}_w{world["index"]:03d}.json.gz';save_new(path,public)
        entries.append(dict(role=world['role'],world_id=world['world_id'],world_sha256=world['world_sha256'],
            path=path.name,sha256=sha(path),states=len(exported)))
    save_new(out/'manifest.json',dict(schema='bc-rpi-round1-public-fit-manifest-v1',worlds=entries,
        counts={'fit':24,'fit_val':12},state_bundles=bundle_count,nonreference_labels=nonref_count,
        teacher_only_states=teacher_only,zero_state_worlds=zero_worlds,
        label_scale=0.002,continuation_policy_sha256=summary['continuation_policy_sha256'],
        shared_for_three_independent_initializations=True,
        trusted_exporter_sha256=sha(__file__),feature_implementation_sha256=sha(ROOT/'features.py'),
        source_collection_summary_sha256=sha(collection/'summary.json'),
        source_world_results_sha256=sha(collection/'world_results.json'),
        read_boundary='Fitter reads only this manifest and these 36 public fit/fit_val exports. No calibration/development source config, handle, N or true geometry is exported.'))
    print({'public_dataset':str(out),'worlds':36,'bundles':bundle_count,'nonref_labels':nonref_count,'new_calls':0})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--collection',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();export(a.collection,a.out)
