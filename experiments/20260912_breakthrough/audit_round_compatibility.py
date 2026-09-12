#!/usr/bin/env python3
"""Independent saved 12-world exact-teacher compatibility check, no execution."""
import argparse
import json
from pathlib import Path
from audit_rl_execution import read_json,require,sha256,canonical_log
from audit_g1_headroom import decoded,digest
from audit_training_labels import verify_world_sources,terminal_cost


def audit(campaign,stage,ledger,records_audit_path,online_audit_path):
    campaign,stage,ledger=(Path(p).resolve() for p in (campaign,stage,ledger))
    sources={}
    def read(path):sources[str(path)]=sha256(path);return read_json(path)
    status=read(ledger/'execution_status.json')
    require(status['current_run'] is None and status['reserved_calls']==0,'Active compatibility ledger')
    record_audit=read(Path(records_audit_path).resolve());online_audit=read(Path(online_audit_path).resolve())
    require(record_audit['status']=='all_recorded_business_calls_and_saved_outcomes_reconciled'
            and record_audit['outcomes_checked']==status['executions_completed']
            and record_audit['source_sha256'].get(str(ledger/'execution_status.json'))==sha256(ledger/'execution_status.json'),
            'Compatibility physical-record audit missing or bound to another ledger')
    require(online_audit['status']=='all_saved_public_online_inputs_and_frozen_forwards_verified'
            and online_audit['counts']['neural_episodes']==12
            and online_audit['counts']['selected_interventions']==0
            and online_audit['source_sha256'].get(str(stage/'index.json'))==sha256(stage/'index.json'),
            'Compatibility public-forward audit missing or bound to another stage')
    for accepted in (record_audit,online_audit):
        for path,expected in accepted['source_sha256'].items():
            require(sha256(path)==expected,'Previously audited compatibility evidence changed');sources[path]=expected
    paid_rows=[r for r in status['runs'] if r['metadata']['stage']=='compatibility']
    paid={r['run_id']:r for r in paid_rows}
    require(len(paid)==len(paid_rows),'Repeated compatibility run in status')
    worlds=read(campaign/'compatibility_registration.json')['worlds'];registration=read(stage/'registration.json')
    require(len(worlds)==12 and len({w['world_sha256'] for w in worlds})==12
            and len({w['world_id'] for w in worlds})==12 and len(paid)==24,'Wrong compatibility population')
    require(registration['world_ids']==[w['world_id'] for w in worlds]
            and registration['policy_order']==['c7','neural_912101_teacher_forced'],'Changed probe order')
    index=read(stage/'index.json')['runs'];rows=read(stage/'world_results.json')['worlds'];used=set();checks=[]
    require(len(rows)==12 and len(index)==24,'Missing compatibility outputs')
    require(len({r['run_id'] for r in index})==24,'Repeated compatibility index run')
    neural_ids={r['run_id'] for r in index if r['actual_policy_id']=='neural_912101_teacher_forced'}
    online_checks=online_audit['episode_checks']
    require(len(online_checks)==12 and {r['run_id'] for r in online_checks}==neural_ids
            and all(r['seed']==912101 and r['forwards']>0 and r['selected_interventions']==0 for r in online_checks),
            'Online side audit does not cover each exact neural episode')
    model=registration['models'][0]
    require(model['seed']==912101 and digest(model['policy_definition'])==model['policy_sha256'],'Probe model identity differs')
    for world,row in zip(worlds,rows):
        require(all(row[k]==world[k] for k in ('world_id','world_sha256','role','index','group'))
                and row['status']=='complete' and len(row['runs'])==2,'Incomplete or misbound probe world')
        require([r['actual_policy_id'] for r in row['runs']]==['c7','neural_912101_teacher_forced'], 'Probe arm order changed')
        results=[]
        for entry in row['runs']:
            run_id=entry['run_id'];require(run_id not in used and run_id in paid and entry in index,'Unpaid/duplicated probe run')
            used.add(run_id);path=(campaign/entry['path']).resolve();require(path.is_relative_to(stage),'Probe path escaped stage')
            require(record_audit['source_sha256'].get(str(path))==sha256(path),'Paid outcome missing from physical side audit')
            if run_id in neural_ids:
                require(online_audit['source_sha256'].get(str(path))==sha256(path),'Neural outcome missing from online side audit')
            result=read(path);run=paid[run_id]
            require(result['run_id']==run_id and result['kind']==run['kind']=='full'
                    and result['success'] is True and result['normal_exit'] is True,'Probe not normally all clear')
            require(run['success'] is True and run['unknown_cost'] is False,'Paid probe failed or has unresolved cost')
            require(run['metadata']['world_sha256']==world['world_sha256'] and run['metadata']['mode']==4,'Probe paid on another world/mode')
            require(all(entry[k]==world[k] for k in ('world_id','world_sha256','role','index','group'))
                    and entry['mode']==4 and entry['success'] is True and entry['normal_exit'] is True
                    and entry['kind']=='full' and entry['n']==result['true_terminal_n']==entry['cleared']==len(world['sources'])
                    and entry['modeled_full_virtual_us']==result['modeled_full_virtual_us']
                    and entry['seconds_per_source']==result['modeled_full_virtual_us']/1e6/result['true_terminal_n']
                    and entry['actual_execution_wall_s']==result['actual_execution_wall_s']
                    and entry['fallback_reason']==result['episode'].get('fallback_reason')
                    and entry['error']==result['episode'].get('error'), 'Probe index metrics or identity differs')
            terminal_cost(result);verify_world_sources(result,world);results.append(result)
        direct,neural=results
        require(paid[direct['run_id']]['metadata']['entry_sha256']==row['runs'][0]['entry_sha256']==registration['c7_sha256']
                and paid[direct['run_id']]['metadata']['policy']=='original_c7','Compatibility original entry changed')
        extra=neural['extra'];decisions=extra['selector_decisions'];final=decoded(neural['episode']['engine_final'])
        require(extra['force_teacher_probe'] is True and extra['checkpoint_sha256']==model['sha256']
                and extra['policy_sha256']==row['runs'][1]['policy_sha256']==model['policy_sha256']
                and extra['margin']==model['margin'] and neural['episode']['mode']==4,'Wrong forced probe policy')
        require(final['used_operation_ids']==[] and final['interventions_remaining']==2
                and neural['episode']['slots_remaining']==2,'Probe spent intervention quota')
        actual=paid[neural['run_id']]['metadata']
        require(actual['policy_sha256']==model['policy_sha256'] and actual['checkpoint_sha256']==model['sha256']
                and actual['force_teacher_probe'] is True and actual['policy']=='round1_neural_912101', 'Paid probe policy differs from result')
        require(decisions and all(d['selected_id']==d['teacher_id'] and d['force_teacher_probe'] is True for d in decisions)
                and any(d['model_scored'] for d in decisions),'Probe did not execute real neural forward with teacher override')
        require(canonical_log(direct['environment_log'])==canonical_log(neural['environment_log'])
                and direct['modeled_full_virtual_us']==neural['modeled_full_virtual_us']
                and direct['true_terminal_n']==neural['true_terminal_n'],'Probe differs in actual requests/observations/cost')
        saved=read(stage/'checks'/f'w{world["index"]:03d}.json')
        require(saved['world_id']==world['world_id'] and all(v is True for v in saved['checks'].values()),'Saved exact probe check failed')
        checks.append(dict(world_id=world['world_id'],matched_calls=len(direct['environment_log']),
            neural_forwards=sum(d['model_scored'] for d in decisions),normal_allclear=True,exact_trace=True))
    summary=read(stage/'summary.json')
    require(used==set(paid) and summary['status']=='compatibility_complete_exact_teacher_equivalence'
            and summary['completed_worlds']==12 and summary['actual_executions']==24
            and summary['actual_calls']==sum(r['attempted'] for r in paid.values())
            and summary['unknown_cost_calls']==0 and summary['current_run'] is None,'Incomplete compatibility settlement')
    require(all(sha256(p)==s for p,s in sources.items()),'Compatibility evidence changed during audit')
    return dict(status='12_world_24_full_exact_teacher_equivalence_verified',world_checks=checks,
        source_sha256=sources,auditor_sha256=sha256(__file__),summary_sha256=sha256(stage/'summary.json'),
        source_freeze_sha256=registration['source_freeze_sha256'],calibration_margins_sha256=registration['calibration_margins_sha256'],
        actual_environment_calls_by_auditor=0,actual_optimizer_updates_by_auditor=0,
        evidence_limits=['Saved exact trace comparison, not an additional simulator replay.',
            'Actual neural scores in probes do not imply any learned intervention benefit.'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('campaign','stage','ledger','records-audit','online-audit','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();require(not a.out.exists(),'Preserve previous audit')
    result=audit(a.campaign,a.stage,a.ledger,a.records_audit,a.online_audit);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(result['status'])
