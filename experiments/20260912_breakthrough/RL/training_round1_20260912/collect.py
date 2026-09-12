"""One shared pi0=C7 full-tail label collection; no neural imports or fitting."""
from __future__ import annotations
import argparse
from copy import deepcopy
import sys
import time
from .common import ROOT,BASE,load,save_new,atomic_json,sha,digest
from .budget import Budget,BudgetStop
from .freeze import verify_sources,verify_inputs
from implementation.deploy import vendor,operations
from implementation.deploy.engine import CandidateWorker
from implementation.evaluator.runtime import run_full,run_suffix,sample_handles
from implementation.evaluator.g0_fixtures import expand_handle
from implementation.evaluator.g1 import verify_replay,continuation_identity

class IncompleteOutcome(RuntimeError):
    def __init__(self,kind,reason):
        super().__init__(reason);self.kind=kind

def classify_outcome(result,unknown_acceptance=False):
    """Do not turn a research/engineering interruption into a cheap failed label.

    The old runtime does not persist env.finished/exit_reason. Only an accepted
    terminal user_exit supplies affirmative terminal evidence here; all other
    unsuccessful results stop this collection pending independent evidence.
    """
    error=str(result.get('episode',{}).get('error') or '')
    lowered=error.lower()
    if unknown_acceptance:raise IncompleteOutcome('engineering','Unknown actual acceptance')
    if any(word in lowered for word in ('memoryerror','budgetstop','oserror','ioerror','resource','disk','rss','quota')):
        raise IncompleteOutcome('resource','Research resource/budget interruption: '+error)
    if result.get('ledger_error'):raise IncompleteOutcome('engineering','Private/public ledger mismatch')
    events=result.get('environment_log',[]);last=events[-1] if events else {}
    terminal=(result.get('normal_exit') is True and last.get('action')=='exit' and
        last.get('response',{}).get('accepted') is True and last.get('response',{}).get('exit_reason')=='user_exit')
    if error:raise IncompleteOutcome('engineering','Unclassified controller/interface error: '+error)
    if not terminal:raise IncompleteOutcome('engineering','No affirmative accepted-terminal evidence')
    n=result.get('true_terminal_n');cleared=result.get('cleared')
    if type(n) is not int or not 10<=n<=16 or type(cleared) is not int or not 0<=cleared<=n:
        raise IncompleteOutcome('engineering','Invalid terminal denominator')
    if result.get('success') is True and cleared==n:return 'normal_complete_success'
    if result.get('success') is False and cleared<n:return 'proven_normal_exit_incomplete_clear_failure'
    raise IncompleteOutcome('engineering','Success/clear/terminal flags inconsistent')

def terminal_cost(result,prefix_us=0):
    classify_outcome(result)
    n=result['true_terminal_n']
    if type(n) is not int or not 10<=n<=16:raise ValueError('Invalid terminal-only N')
    if result['modeled_full_virtual_us']<prefix_us:raise ValueError('Negative suffix virtual cost')
    return (result['modeled_full_virtual_us']-prefix_us)/(1_000_000_000*n)+(0. if result['success'] else 100.)

class Recorder:
    def __init__(self,out,budget,freeze,continuation_sha):
        self.out=out;self.budget=budget;self.freeze=freeze;self.pi_sha=continuation_sha
        self.rows=[];self.worlds=[]

    def record(self,result,world,family,**metadata):
        path=self.out/'runs'/(result['run_id']+'.json.gz')
        save_new(path,result)
        row=dict(run_id=result['run_id'],path=str(path.relative_to(ROOT)),world_id=world['world_id'],
            world_sha256=world['world_sha256'],role=world['role'],mode=4,group=world['group'],index=world['index'],
            kind=result['kind'],family=family,actual_policy_id='c7_pi0',continuation_policy_sha256=self.pi_sha,
            success=result['success'],n=result['true_terminal_n'],modeled_full_virtual_us=result['modeled_full_virtual_us'],
            actual_execution_wall_s=result['actual_execution_wall_s'],**metadata)
        self.rows.append(row);atomic_json(self.out/'index.json',dict(schema='bc-rpi-round1-label-runs-v1',runs=self.rows))
        verify_sources(self.freeze)
        if self.budget.data['stopped_for_unknown_acceptance']:
            raise BudgetStop('Unknown actual acceptance retained; collection cannot continue')
        return row

    def progress(self):
        atomic_json(self.out/'world_results.json',dict(schema='bc-rpi-round1-label-worlds-v1',worlds=self.worlds))
        atomic_json(self.out/'progress.json',dict(completed_worlds=sum(w['status']=='complete' for w in self.worlds),
            actual_calls=self.budget.data['business_calls'],executions=self.budget.data['executions_started'],
            current_run=self.budget.data['current_run'],network_training_runs=0))

def world_labels(recorder,world,worker):
    role,index=world['role'],world['index'];prefix=f'r1_labels_v1_{role}_w{index:03d}'
    directory=recorder.out/'worlds'/f'{role}_w{index:03d}'
    baseline,handles=run_full(world,recorder.budget,prefix+'_rollin',worker=worker,capture=True)
    recorder.record(baseline,world,'c7_rollin')
    classify_outcome(baseline,recorder.budget.data['stopped_for_unknown_acceptance'])
    if not baseline['success']:
        raise RuntimeError('C7 roll-in did not finish normally; preserve failed world and stop, not a selected successful subset')
    selected=sample_handles(handles,4)
    save_new(directory/'sampling.json',dict(world_id=world['world_id'],world_sha256=world['world_sha256'],
        role=role,rollin_run_id=baseline['run_id'],all_public_source_boundary_count=len(handles),
        all_public_boundaries=[dict(source_index=h.source_index,choice_id=h.prepared.choice_id,
            prefix_virtual_us=h.token.prefix_virtual_us,teacher_task=h.prepared.meta['teacher_task']) for h in handles],
        selected_source_indexes=[h.source_index for h in selected],
        sampling='m=min(4,n); floor(k*(n-1)/(m-1)); m=1 ->0; public sequence only',
        zero_states_are_retained=True))
    states=[];failed=0
    for state_index,handle in enumerate(selected):
        expand_started=time.monotonic();expand_cpu=time.process_time();expand_handle(handle,worker);handle.verify(world)
        feature_wall=time.monotonic()-expand_started;feature_cpu=time.process_time()-expand_cpu
        dest=directory/f's{state_index:02d}';save_new(dest/'handle.json.gz',handle.to_json())
        choices=handle.prepared.choices;ids=choices['candidate_ids'];teacher=choices['teacher_id']
        if not 1<=len(ids)<=9 or len(set(ids))!=len(ids) or teacher not in ids or ids!=sorted(ids):
            raise ValueError('Malformed retained candidate set')
        bundle=dict(schema='bc-rpi-round1-complete-label-bundle-v1',status='registered_not_complete',
            world_id=world['world_id'],world_sha256=world['world_sha256'],role=role,state_index=state_index,
            source_index=handle.source_index,choice_id=handle.prepared.choice_id,
            origin_rollin_run_id=baseline['run_id'],continuation_policy_sha256=recorder.pi_sha,
            candidate_ids=ids,teacher_id=teacher,candidate_count=len(ids),
            prefix_virtual_us=handle.token.prefix_virtual_us,prefix_event_count=handle.token.accepted_event_count,
            feature_generation_wall_s=feature_wall,feature_generation_main_cpu_s=feature_cpu,
            worker_cpu_s=None,shared_across_initializations=True,initialization_seeds=[912101,912102,912103],outcomes=[])
        save_new(dest/'registration.json',deepcopy(bundle))
        try:
            for action_index,action_id in enumerate(ids):
                verify_sources(recorder.freeze)
                result,_=run_suffix(world,recorder.budget,prefix+f'_s{state_index:02d}_a{action_index:02d}',
                                    handle,action_id,worker=worker)
                row=recorder.record(result,world,'counterfactual_suffix',state_index=state_index,
                    source_index=handle.source_index,choice_id=handle.prepared.choice_id,action_id=action_id,teacher_id=teacher)
                outcome_class=classify_outcome(result,recorder.budget.data['stopped_for_unknown_acceptance'])
                failed+=not result['success']
                if action_id==teacher:
                    check=verify_replay(baseline,result,[])
                    save_new(dest/'a0_replay_check.json',check)
                    if not all(check.values()):raise AssertionError('A0 complete tail differs from actual C7 roll-in')
                bundle['outcomes'].append(dict(row,terminal_normalized_suffix_cost=terminal_cost(result,handle.token.prefix_virtual_us),
                    terminal_normalized_full_cost=terminal_cost(result),actual_slot_cost=int(action_id!=teacher),
                    terminal_classification=outcome_class,
                    labels=choices['candidates'][action_index].get('labels',[])))
                atomic_json(dest/'labels.json',bundle)
            reference=next(r for r in bundle['outcomes'] if r['action_id']==teacher)
            for row in bundle['outcomes']:
                row['paired_gain_to_A0']=reference['terminal_normalized_suffix_cost']-row['terminal_normalized_suffix_cost']
                row['reference_origin_run_id']=reference['run_id']
            bundle['status']='complete';bundle['terminal_n']=baseline['true_terminal_n']
            bundle['label_units']='normalized gain: 1 unit = 1000 seconds/source; true failed branch cost +100'
            atomic_json(dest/'labels.json',bundle)
        except BudgetStop:
            bundle['status']='incomplete_budget_or_unknown_acceptance';atomic_json(dest/'labels.json',bundle);raise
        except IncompleteOutcome as exc:
            bundle['status']='incomplete_'+exc.kind;bundle['stop_reason']=str(exc)
            atomic_json(dest/'labels.json',bundle);raise
        except BaseException:
            bundle['status']='incomplete_engineering';atomic_json(dest/'labels.json',bundle);raise
        states.append(dict(state_index=state_index,source_index=handle.source_index,candidate_count=len(ids),
            path=str((dest/'labels.json').relative_to(ROOT)),handle_path=str((dest/'handle.json.gz').relative_to(ROOT)),
            status='complete',teacher_only=len(ids)==1))
        print({'role':role,'world':index,'state':state_index,'candidates':len(ids),
               'calls':recorder.budget.data['business_calls'],'runs':recorder.budget.data['executions_started']},flush=True)
    return dict(status='complete',world_id=world['world_id'],world_sha256=world['world_sha256'],role=role,
        index=index,group=world['group'],states=states,state_count=len(states),
        candidate_count=sum(s['candidate_count'] for s in states),n=baseline['true_terminal_n'],
        c7_rollin_run_id=baseline['run_id'],failed_branches=failed,zero_states_retained=len(states)==0)

def run(out,preflight,acceptance_path):
    if sys.version_info<(3,10) or not sys.flags.no_site:raise RuntimeError('Use Python >=3.10 -S -B')
    out=ROOT/out;preflight=ROOT/preflight;acceptance=load(acceptance_path)
    if acceptance.get('collection_accepted') is not True:raise RuntimeError('Coordinator collection acceptance required')
    if acceptance.get('source_freeze_sha256')!=sha(preflight/'source_freeze.json'):
        raise RuntimeError('Accepted collection source identity differs')
    if acceptance.get('world_manifest_sha256')!=sha(ROOT/'world_manifest.json'):
        raise RuntimeError('Accepted world manifest differs')
    freeze=load(preflight/'source_freeze.json');verify_sources(freeze);verify_inputs(preflight)
    if out.exists():raise FileExistsError('Use a fresh collection output directory; never repeat paid IDs')
    out.mkdir(parents=True)
    registered=[w for w in load(ROOT/'world_manifest.json')['worlds'] if w['role'] in ('fit','fit_val')]
    if len(registered)!=36 or len({w['world_sha256'] for w in registered})!=36:raise ValueError('Invalid fit/val world set')
    pi_identity=continuation_identity();pi_sha=digest(pi_identity)
    save_new(out/'registration.json',dict(schema='bc-rpi-round1-label-collection-v1',world_ids=[w['world_id'] for w in registered],
        continuation_policy=pi_identity,continuation_policy_sha256=pi_sha,
        preflight_source_sha256=sha(preflight/'source_freeze.json'),coordinator_acceptance_sha256=sha(acceptance_path),
        shared_label_dataset_for_seeds=[912101,912102,912103],reference_is_A0=True,
        features_export='After complete collection; raw legacy prepared features are not yet training tensors',
        actual_calls_before_start=0,network_training_runs=0))
    budget=Budget();budget.set_phase('labels');worker=CandidateWorker();budget.register_worker(worker.process.pid)
    recorder=Recorder(out,budget,freeze,pi_sha);status='collecting';reason=None;active=None
    try:
        for world in registered:
            active=world['world_id'];verify_sources(freeze)
            row=world_labels(recorder,world,worker);recorder.worlds.append(row);recorder.progress()
            print({'world':world['world_id'],'status':'complete','calls':budget.data['business_calls']},flush=True)
        status='labels_complete_no_fit_yet'
    except BudgetStop as exc:status='labels_incomplete_budget';reason=str(exc)
    except IncompleteOutcome as exc:status='labels_incomplete_'+exc.kind;reason=str(exc)
    except BaseException as exc:
        status='labels_incomplete_engineering';reason=type(exc).__name__+': '+str(exc);raise
    finally:
        budget.unregister_worker(worker.process.pid);worker.close()
        completed={w['world_id'] for w in recorder.worlds}
        for world in registered:
            if world['world_id'] not in completed:
                recorder.worlds.append(dict(world_id=world['world_id'],world_sha256=world['world_sha256'],
                    role=world['role'],index=world['index'],group=world['group'],
                    status='incomplete' if world['world_id']==active else 'not_started_after_stop'))
        recorder.progress();budget.set_status(status)
        save_new(out/'summary.json',dict(status=status,stop_reason=reason,registered_worlds=36,
            completed_worlds=sum(w['status']=='complete' for w in recorder.worlds),
            actual_calls=budget.data['business_calls'],actual_executions=budget.data['executions_started'],
            accepted_calls=budget.data['accepted_calls'],known_rejected_calls=budget.data['rejected_calls'],
            unknown_cost_calls=budget.data['unknown_cost_calls'],current_run=budget.data['current_run'],
            network_training_runs=0,continuation_policy_sha256=pi_sha,
            real_failure_branches_retained=sum(w.get('failed_branches',0) for w in recorder.worlds)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--preflight',required=True)
    p.add_argument('--acceptance',required=True);a=p.parse_args();run(a.out,a.preflight,a.acceptance)
