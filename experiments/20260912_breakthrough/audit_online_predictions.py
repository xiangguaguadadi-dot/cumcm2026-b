#!/usr/bin/env python3
"""Rebuild all saved online model inputs/scores without optimizer or environment."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from audit_rl_execution import read_json,require,sha256
from audit_g1_headroom import digest
from audit_calibration import argmax


def audit(campaign,stage,fit_audit_path,calibration_audit_path):
    campaign,stage=(Path(p).resolve() for p in (campaign,stage))
    require(stage.is_relative_to(campaign/'results'),'Online evidence outside round')
    require(sys.flags.no_site,'Use pinned Python -S')
    sys.path.append('/Users/t/Documents/Codex/2026-09-10/new-chat/work/rl_execution_runtime/venv/lib/python3.12/site-packages')
    import torch
    require(torch.__version__=='2.8.0','Pinned Torch version changed');torch.set_num_threads(1)
    sys.path.insert(0,str(campaign.parent))
    from training_round1_20260912.features import build_snapshot
    from training_round1_20260912.model import CounterfactualModel
    sources={}
    def read(path):sources[str(path)]=sha256(path);return read_json(path)
    fit=read(Path(fit_audit_path).resolve());cal=read(Path(calibration_audit_path).resolve())
    require(fit['status']=='three_real_fits_and_fit_val_selection_verified'
            and cal['status']=='24_world_three_model_calibration_verified','Missing independent upstream acceptance')
    for audit_row in (fit,cal):
        for path,expected in audit_row['source_sha256'].items():
            require(sha256(path)==expected,'Upstream verified artifact changed');sources[path]=expected
    registration=read(stage/'registration.json');models={};counts=Counter();checks=[]
    for spec in registration['models']:
        accepted=next(r for r in fit['results'] if r['seed']==spec['seed'])
        margin=next(r for r in cal['margin_checks'] if r['seed']==spec['seed'])
        path=(campaign/spec['path']).resolve()
        require(path.is_relative_to(campaign) and sha256(path)==spec['sha256']==accepted['selected_checkpoint_sha256']
                and spec['margin']==margin['margin'],'Online model/threshold differs from accepted fit and calibration')
        sources[str(path)]=sha256(path);checkpoint=torch.load(path,map_location='cpu',weights_only=True)
        model=CounterfactualModel();model.load_state_dict(checkpoint['model_state_dict'],strict=True);model.eval()
        models[spec['sha256']]=(spec,model)
    for entry in read(stage/'index.json')['runs']:
        if not entry['actual_policy_id'].startswith('neural_'):continue
        path=(campaign/entry['path']).resolve();require(path.is_relative_to(stage),'Online run path escaped stage')
        result=read(path);extra=result['extra'];spec,model=models[extra['checkpoint_sha256']]
        decisions=extra['selector_decisions'];inputs=extra['selector_public_input_audit'];events=result['episode']['events']
        by_choice={d['choice_id']:d for d in decisions}
        require(len(by_choice)==len(decisions),'Repeated online selector choice ID')
        scored={d['choice_id'] for d in decisions if d['model_scored']};observed=set();interventions=0
        for record in inputs:
            choice=record['choice_id'];require(choice in by_choice and choice not in observed,'Unaligned online forward record')
            observed.add(choice);decision=by_choice[choice]
            prefix=record['public_prefix_event_count']
            require(type(prefix) is int and 1<=prefix<=len(events),'Invalid online observation prefix')
            prepared=record['prepared_public'];snapshot=record['public_snapshot']
            require(prepared['choice_id']==choice and record['prepared_public_sha256']==digest(prepared)
                    and record['public_snapshot_sha256']==digest(snapshot),'Online prepared/snapshot hash mismatch')
            require(build_snapshot(prepared,events[:prefix])==snapshot,'Online numerical input differs from actual public history')
            if not record['success']:
                require(not decision['model_scored'] and decision['selected_id']==decision['teacher_id'],'Failed inference changed the selected action')
                counts['failed_forward_records']+=1;continue
            require(choice in scored and decision['checkpoint_sha256']==record['checkpoint_sha256']==spec['sha256'], 'Online score model identity differs')
            tensors={k:torch.tensor(v,dtype=torch.bool if k=='active_mask' else torch.float32) for k,v in snapshot['features'].items()}
            with torch.no_grad():scores=model(tensors).tolist()
            selected,gain,gains=argmax(snapshot['candidate_ids'],snapshot['teacher_id'],scores)
            threshold=spec['margin']+.0005
            gated=selected if gain>threshold else snapshot['teacher_id']
            expected=snapshot['teacher_id'] if extra['force_teacher_probe'] else gated
            require(scores==record['raw_scores_float32']==decision['scores'] and gains==decision['gains']
                    and gain==decision['predicted_gain'] and selected==decision['predicted_candidate_id']
                    and decision['strict_threshold']==threshold and decision['selected_id']==expected,
                    'Online output/strict threshold differs from independent frozen forward')
            require(decision['slots_before'] in (1,2),'Model scored without a remaining intervention')
            interventions+=expected!=snapshot['teacher_id'];counts['successful_forwards']+=1
        require(scored=={r['choice_id'] for r in inputs if r['success']},'Missing recorded successful neural input')
        require(interventions<=2,'More than two selected neural interventions')
        counts['neural_episodes']+=1;counts['selected_interventions']+=interventions
        checks.append(dict(run_id=result['run_id'],seed=spec['seed'],forwards=len(scored),selected_interventions=interventions))
    require(all(sha256(p)==s for p,s in sources.items()),'Online evidence changed during audit')
    return dict(status='all_saved_public_online_inputs_and_frozen_forwards_verified',counts=dict(counts),episode_checks=checks,
        source_sha256=sources,auditor_sha256=sha256(__file__),actual_environment_calls=0,actual_optimizer_updates=0,
        evidence_limits=['Accepted model/feature implementations reused for independent frozen forward; no retraining.',
            'Only fully saved stage outcomes are checked; pair with complete-population and physical-ledger audits.'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('campaign','stage','fit-audit','calibration-audit','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();require(not a.out.exists(),'Preserve previous audit')
    result=audit(a.campaign,a.stage,a.fit_audit,a.calibration_audit)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','counts')},indent=2))
