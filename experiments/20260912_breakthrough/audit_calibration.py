#!/usr/bin/env python3
"""Independent saved-trajectory, frozen-forward and empirical-margin audit.

No environment or optimizer is run. Reuses only accepted public feature/model
modules for deterministic forward checks, with independently computed labels,
float32 argmax, cache bindings and world-level order statistic.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

from audit_g1_headroom import decoded, digest, public_boundaries
from audit_rl_execution import canonical_log, read_json, require, sha256
from audit_training_labels import terminal_cost, verify_handle, verify_label, verify_world_sources

SEEDS = (912101,912102,912103)
TENSOR_KEYS = {'global_features','channels','active_events','active_mask','polygon','actions'}


def f32(value):
    require(type(value) in (int,float) and math.isfinite(value), 'Nonfinite model score')
    result=struct.unpack('!f',struct.pack('!f',value))[0]
    require(math.isfinite(result), 'Float32 score/difference overflow')
    return result


def argmax(ids, teacher, scores):
    require(1 <= len(ids) <= 9 and ids == sorted(set(ids)) and teacher in ids and len(scores) == len(ids),
            'Invalid retained action/score alignment')
    require(all(v == f32(v) for v in scores), 'Scores are not exact float32')
    reference=scores[ids.index(teacher)]
    gains=[f32(v-reference) for v in scores]
    index=min(range(len(ids)),key=lambda i:(-gains[i],ids[i]))
    return ids[index],gains[index],gains


def empirical_margin(world_rows, expected_ids):
    require(len(expected_ids) == len(set(expected_ids)) == 24 and len(world_rows) == 24
            and {r['world_id'] for r in world_rows} == set(expected_ids), 'Incomplete/duplicated 24-world calibration')
    values=[]
    for row in world_rows:
        require(row['status'] == 'complete' and 1 <= len(row['states']) <= 2, 'Incomplete calibration state bundle')
        residuals=[]
        for state in row['states']:
            predicted,realized=state['predicted_gain'],state['realized_gain']
            require(all(type(x) in (int,float) and math.isfinite(x) for x in (predicted,realized)), 'Nonfinite calibration gain')
            residual=predicted-realized
            require(math.isfinite(residual), 'Nonfinite residual difference')
            if state['candidate_id'] == state['teacher_id']:
                require(predicted == realized == 0., 'A0 residual is not exactly zero')
            require(abs(state['optimistic_residual']-residual)<1e-12, 'Stored residual differs')
            residuals.append(residual)
        maximum=max(residuals)
        require(abs(maximum-row['world_max_optimistic_residual'])<1e-12, 'Wrong within-world maximum')
        values.append(maximum)
    ordered=sorted(values)
    return max(0.,ordered[21]),ordered


def verify_selected_models(models, fit_audit):
    require(fit_audit['status']=='three_real_fits_and_fit_val_selection_verified'
            and [r['seed'] for r in fit_audit['results']]==list(SEEDS), 'Missing accepted three-seed fit audit')
    require([r['seed'] for r in models]==list(SEEDS), 'Calibration changed selected seed set/order')
    for model, accepted in zip(models,fit_audit['results']):
        require(model['sha256']==accepted['selected_checkpoint_sha256']
                and model['epoch']==accepted['selected_epoch'], 'Calibration checkpoint was not selected by audited fit_val')
        selected=next(r for r in accepted['checkpoints'] if r['epoch']==accepted['selected_epoch'])
        require(model['parameter_sha256']==selected['parameter_sha256'], 'Calibration selected parameter identity changed')


def verify_prelabel_freeze(fixed, unique, calls_before, runs_before):
    require(unique and len({r['run_id'] for r in unique})==len(unique), 'Missing/duplicated unique tail run')
    first=min((r['run_id'] for r in unique),key=lambda run:runs_before[run])
    require(fixed['calls_at_selection_freeze']==calls_before[first]
            and fixed['executions_at_selection_freeze']==runs_before[first], 'Argmax was not frozen before state label calls')


def audit(campaign, stage, ledger, fit_audit_path):
    campaign,stage,ledger=(Path(p).resolve() for p in (campaign,stage,ledger))
    require(stage.is_relative_to(campaign/'results'), 'Calibration outside new round')
    sys.path.append('/Users/t/Documents/Codex/2026-09-10/new-chat/work/rl_execution_runtime/venv/lib/python3.12/site-packages')
    import torch
    require(sys.flags.no_site and torch.__version__=='2.8.0', 'Use pinned -S Torch runtime')
    torch.set_num_threads(1)
    sys.path.insert(0,str(campaign.parent))
    from training_round1_20260912.model import CounterfactualModel
    from training_round1_20260912.features import build_snapshot
    sources={}
    def read(path):
        sources[str(path)]=sha256(path)
        return read_json(path)
    def artifact(name):
        path=(campaign/name).resolve()
        require(path.is_relative_to(stage),'Calibration artifact path escaped dataset')
        return path
    status=read(ledger/'execution_status.json')
    require(status['current_run'] is None and status['reserved_calls']==0,'Calibration has an active paid run')
    paid={r['run_id']:r for r in status['runs'] if r['metadata'].get('stage')=='calibration'}
    calls_before={};runs_before={};calls=0
    for i,row in enumerate(status['runs']):
        calls_before[row['run_id']]=calls;runs_before[row['run_id']]=i;calls+=row['attempted']
    worlds=[w for w in read(campaign/'world_manifest.json')['worlds'] if w['role']=='calibration']
    require(len(worlds)==24 and len({w['world_sha256'] for w in worlds})==24,'Wrong calibration world registry')
    registration=read(stage/'registration.json');pi=digest(registration['continuation_policy'])
    require(registration['world_ids']==[w['world_id'] for w in worlds]
            and registration['continuation_policy_sha256']==pi,'Calibration registration changed')
    require([m['seed'] for m in registration['models']]==list(SEEDS),'Calibration missing or reordering initialization')
    fit_audit=read(Path(fit_audit_path).resolve())
    verify_selected_models(registration['models'],fit_audit)
    for path, expected in fit_audit['source_sha256'].items():
        require(sha256(path)==expected,'Previously audited fit evidence changed')
        sources[path]=expected
    models={}
    for row in registration['models']:
        path=(campaign/row['path']).resolve()
        require(path.is_relative_to(campaign) and sha256(path)==row['sha256'],'Selected calibration model changed')
        sources[str(path)]=sha256(path)
        checkpoint=torch.load(path,map_location='cpu',weights_only=True)
        require(checkpoint['seed']==row['seed'] and checkpoint['epoch']==row['epoch']
                and checkpoint['parameter_sha256']==row['parameter_sha256'],'Calibration model identity mismatch')
        require(checkpoint['dataset_manifest_sha256']==row['dataset_manifest_sha256']
                and checkpoint['model_source_sha256']==row['model_source_sha256']==sha256(campaign/'model.py')
                and checkpoint['feature_implementation_sha256']==row['feature_implementation_sha256']==sha256(campaign/'features.py'),
                'Calibration changes fitted dataset/model/feature semantics')
        for name in ('model.py','features.py'):
            sources[str(campaign/name)]=sha256(campaign/name)
        model=CounterfactualModel();model.load_state_dict(checkpoint['model_state_dict'],strict=True);model.eval()
        models[row['seed']]=(row,model)
    index=read(stage/'index.json')['runs'];results={};indexed={};by_world={w['world_sha256']:w for w in worlds}
    for row in index:
        run_id=row['run_id'];require(run_id not in results and run_id in paid,'Duplicate/unpaid calibration outcome')
        result=read(artifact(row['path']));actual=paid[run_id];world=by_world[row['world_sha256']]
        require(result['run_id']==run_id and result['kind']==row['kind']==actual['kind']
                and actual['metadata']['world_sha256']==world['world_sha256'] and actual['metadata']['mode']==4,
                'Calibration index/journal world mismatch')
        require(row['role']=='calibration' and all(row[k]==world[k] for k in ('world_id','index','group'))
                and row['success'] is result['success'] and row['n']==result['true_terminal_n']==len(world['sources'])
                and row['modeled_full_virtual_us']==result['modeled_full_virtual_us'],'Calibration index changed metrics')
        if result['kind']=='suffix':
            require(actual['metadata']['policy']=='one_retained_operation_then_frozen_c7'
                    and all(actual['metadata'][k]==row[k] for k in ('action_id','choice_id')),'Actual calibration action differs')
        else:require(actual['metadata']['policy']=='teacher0','Calibration roll-in changed policy')
        terminal_cost(result);verify_world_sources(result,world)
        results[run_id]=result;indexed[run_id]=row
    require(set(results)==set(paid),'Calibration omitted a paid outcome')
    used=set();world_seed_rows=[];cache_keys=set();branch_count=state_count=0
    for world in worlds:
        directory=stage/'worlds'/f'w{world["index"]:03d}';sample=read(directory/'sampling.json')
        parent_id=sample['rollin_run_id'];parent=results[parent_id]
        require(parent_id not in used and indexed[parent_id]['family']=='shared_c7_rollin'
                and indexed[parent_id]['world_sha256']==world['world_sha256'] and parent['success'], 'Wrong shared C7 roll-in')
        used.add(parent_id)
        boundaries=public_boundaries(parent,after_intervention=False);count=len(boundaries)
        expected=[] if not count else [0] if count==1 else [0,count-1]
        require(sample['world_id']==world['world_id'] and sample['world_sha256']==world['world_sha256']
                and sample['all_public_source_boundary_count']==count and len(sample['all_public_boundaries'])==count
                and sample['selected_source_indexes']==expected and sample['max_sampled_states']==2 and expected,
                'Wrong public calibration sampling or omitted empty world')
        for actual,boundary in zip(sample['all_public_boundaries'],boundaries):
            require(all(actual[k]==boundary[k] for k in ('source_index','choice_id','prefix_virtual_us'))
                    and actual['teacher_task']['kind']=='source' and actual['teacher_task']['key']==boundary['channel'],
                    'Calibration source boundary changed')
        per_seed={seed:[] for seed in SEEDS}
        for state_index,source_index in enumerate(expected):
            dest=directory/f's{state_index:02d}';handle=read(dest/'handle.json.gz')
            prepared,token,ids,teacher=verify_handle(handle,world,boundaries[source_index],source_index)
            snapshot=read(dest/'public_snapshot.json')
            require(snapshot==build_snapshot(prepared,decoded(token['interface_public_state'])['events']),
                    'Stored calibration features differ from actual public handle')
            fixed=read(dest/'selection_before_labels.json');complete=read(dest/'complete_labels.json')
            require(fixed['world_id']==world['world_id'] and fixed['world_sha256']==world['world_sha256']
                    and fixed['state_index']==state_index and fixed['source_index']==source_index
                    and fixed['choice_id']==prepared['choice_id'] and fixed['teacher_id']==teacher
                    and fixed['all_retained_candidate_ids']==ids and fixed['all_seed_choices_frozen_before_any_state_tail'] is True,
                    'Selected calibration state identity mismatch')
            require([c['seed'] for c in fixed['selected_by_seed']]==list(SEEDS),'Missing pre-label initialization decision')
            for choice in fixed['selected_by_seed']:
                spec,model=models[choice['seed']]
                raw=snapshot['features'];tensors={k:torch.tensor(raw[k],dtype=torch.bool if k=='active_mask' else torch.float32) for k in TENSOR_KEYS}
                with torch.no_grad():scores=model(tensors).tolist()
                action,gain,gains=argmax(ids,teacher,scores)
                require(choice['checkpoint_sha256']==spec['sha256'] and choice['epoch']==spec['epoch']
                        and choice['candidate_ids']==ids and choice['teacher_id']==teacher and choice['raw_scores_float32']==scores
                        and choice['candidate_id']==action and choice['predicted_gain']==gain and choice['gains']==gains,
                        'Calibration selection differs from frozen neural argmax')
            wanted=sorted({teacher,*[c['candidate_id'] for c in fixed['selected_by_seed']]})
            unique=complete['unique_action_outcomes']
            require(fixed['evaluated_unique_action_ids']==wanted and [r['action_id'] for r in unique]==wanted
                    and complete['status']=='complete' and complete['selection_before_labels_sha256']==sha256(dest/'selection_before_labels.json'),
                    'Missing/reordered/changed unique calibration action bundle')
            verify_prelabel_freeze(fixed,unique,calls_before,runs_before)
            reference_row=next(r for r in unique if r['action_id']==teacher);reference=results[reference_row['run_id']]
            require(reference['success'] and canonical_log(reference['environment_log'])==canonical_log(parent['environment_log'])
                    and reference['modeled_full_virtual_us']==parent['modeled_full_virtual_us'],'Calibration A0 tail differs from C7')
            by_action={r['action_id']:r for r in unique}
            for row in unique:
                run_id=row['run_id'];require(run_id not in used,'Cache reuses a paid execution across different states/actions')
                used.add(run_id);result=results[run_id];action=row['action_id'];payload=prepared['choices']['candidates'][ids.index(action)]
                require(all(row[k]==indexed[run_id][k] for k in indexed[run_id]) and indexed[run_id]['family']=='unique_selected_or_a0_tail',
                        'Unique calibration outcome differs from actual indexed run')
                cache=fixed['cache_identities'][action];identity=cache['identity']
                require(cache['key_sha256']==digest(identity)==row['cache_key_sha256'] and cache['key_sha256'] not in cache_keys,
                        'Invalid or cross-state cache key reuse')
                cache_keys.add(cache['key_sha256'])
                require(identity['world_sha256']==world['world_sha256'] and identity['world_id']==world['world_id']
                        and identity['fork_bundle_sha256']==handle['bundle_integrity_sha256']
                        and identity['private_integrity_sha256']==handle['private_integrity_sha256']
                        and identity['resume_token_sha256']==digest(token) and identity['prepared_sha256']==digest(prepared)
                        and identity['choice_id']==prepared['choice_id'] and identity['action_id']==action
                        and identity['continuation_policy_sha256']==pi
                        and identity['stage_source_freeze_sha256']==registration['source_freeze_sha256']
                        and identity['environment_sha256']=='99587518fa378e1bef2fbbaa9425ee907bea80885a69666b3765311cbcf4f42a',
                        'Cache eligibility does not bind world/action/continuation/source/physics')
                cost=terminal_cost(result,token['prefix_virtual_us']);ref_cost=terminal_cost(reference,token['prefix_virtual_us'])
                require(abs(row['normalized_suffix_cost']-cost)<1e-12,'Wrong unique branch normalized cost')
                # Verify the actual suffix, without treating synthesized fields as
                # stored evidence of gain: declared gains are checked separately below.
                verify_label(result,dict(row,reference_origin_run_id=reference['run_id'],actual_slot_cost=int(action!=teacher),
                    terminal_normalized_suffix_cost=cost,terminal_normalized_full_cost=terminal_cost(result),
                    paired_gain_to_A0=ref_cost-cost,terminal_classification='normal_complete_success' if result['success']
                    else 'proven_normal_exit_incomplete_clear_failure',labels=payload.get('labels',[])),reference,token,payload,teacher)
                branch_count+=1
            require([r['seed'] for r in complete['seeds']]==list(SEEDS),'Missing calibration label consumer')
            for fixed_choice,row in zip(fixed['selected_by_seed'],complete['seeds']):
                require(all(row[k]==fixed_choice[k] for k in fixed_choice),'Post-label model selection changed')
                selected=by_action[row['candidate_id']];result=results[selected['run_id']]
                gain=terminal_cost(reference,token['prefix_virtual_us'])-terminal_cost(result,token['prefix_virtual_us'])
                require(row['selected_origin_run_id']==result['run_id'] and row['reference_origin_run_id']==reference['run_id']
                        and row['selected_cache_key_sha256']==selected['cache_key_sha256']
                        and row['reference_cache_key_sha256']==reference_row['cache_key_sha256']
                        and abs(row['realized_gain']-gain)<1e-12 and row['terminal_n']==len(world['sources'])
                        and row['actual_new_calls_for_this_read']==0 and row['origin_actual_execution_counted_once'] is True,
                        'Per-initialization label/origin/cache reuse mismatch')
                per_seed[row['seed']].append(row)
            for row in unique:
                consumers=[]
                for r in complete['seeds']:
                    if r['candidate_id']==row['action_id']:consumers.append(dict(seed=r['seed'],role='selected'))
                    if teacher==row['action_id']:consumers.append(dict(seed=r['seed'],role='reference'))
                require(row['consumers']==consumers,'Cached branch consumer map differs')
            state_count+=1
        for seed in SEEDS:
            states=per_seed[seed]
            world_seed_rows.append(dict(seed=seed,world_id=world['world_id'],states=states,
                status='complete',world_max_optimistic_residual=max(r['predicted_gain']-r['realized_gain'] for r in states)))
    require(used==set(results),'Calibration has orphan outcomes')
    saved_worlds=read(stage/'world_results.json')['rows']
    require(len(saved_worlds)==72,'Missing world-level calibration rows')
    for saved,actual in zip(saved_worlds,world_seed_rows):
        require(all(saved[k]==actual[k] for k in actual),'Saved world/seed calibration residual differs')
    margins=read(stage/'margins.json');checks=[]
    require(margins['models']==registration['models'] and margins['world_results_sha256']==sha256(stage/'world_results.json')
            and margins['registration_sha256']==sha256(stage/'registration.json')
            and [r['seed'] for r in margins['margins']]==list(SEEDS),'Frozen margin identity mismatch')
    for row in margins['margins']:
        q,ordered=empirical_margin([r for r in world_seed_rows if r['seed']==row['seed']],[w['world_id'] for w in worlds])
        require(row['margin']==q and row['nearest_rank']==22 and row['world_count']==24
                and row['raw_rank_value']==ordered[21] and row['sorted_world_residuals']==ordered
                and row['strict_extra_gain']==.0005 and row['checkpoint_sha256']==models[row['seed']][0]['sha256'],
                'Empirical margin differs from the registered 22nd world maximum')
        checks.append(dict(seed=row['seed'],margin=q,seconds_per_source_margin=1000*q,worlds=24,rank=22))
    summary=read(stage/'summary.json')
    require(summary['status']=='calibration_complete_three_frozen_margins' and summary['completed_worlds']==24
            and summary['actual_executions']==len(results) and summary['actual_calls']==sum(r['attempted'] for r in paid.values())
            and summary['current_run'] is None and summary['unknown_cost_calls']==0,'Calibration did not settle complete')
    require(all(sha256(p)==s for p,s in sources.items()),'Calibration evidence changed during audit')
    return dict(schema='bc-rpi-round1-independent-calibration-audit-v1',status='24_world_three_model_calibration_verified',
        world_count=24,state_count=state_count,unique_suffix_executions=branch_count,actual_executions=len(results),
        actual_environment_calls_by_auditor=0,actual_optimizer_updates_by_auditor=0,margin_checks=checks,
        source_sha256=sources,auditor_sha256=sha256(__file__),
        evidence_limits=['Accepted public feature/model forward reused; full-tail labels, argmax, cache and margin independently recomputed.',
                         'Empirical C7-state calibration, not a full-trajectory or out-of-distribution safety guarantee.',
                         'Must be paired with full physical business-record accounting and source archive audit.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('campaign','stage','ledger','fit-audit','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();require(not a.out.exists(),'Preserve prior audit')
    result=audit(a.campaign,a.stage,a.ledger,a.fit_audit);a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','margin_checks','unique_suffix_executions')},indent=2))

if __name__=='__main__':main()
