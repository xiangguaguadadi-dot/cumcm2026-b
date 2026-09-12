"""Independent round budget; G0/G1 counters, clocks and source stay read-only.

Journal event schema retains the already independently audited G0/G1 protocol.
Fit updates use a separate journal, never fabricated business-call events.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
import resource
import subprocess
import time
from .common import ROOT,LIMITS,CARRY_IN,atomic_json

class BudgetStop(RuntimeError):pass

class Budget:
    def __init__(self,*,directory=ROOT,now=time.time,monotonic=time.monotonic,
                 limits=None,resource_probe=None):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.status_path=self.directory/'execution_status.json'
        self.journal_path=self.directory/'execution_calls.jsonl'
        self.now=now;self.monotonic=monotonic;self.worker_pids=set()
        self.resource_probe=resource_probe
        wanted=deepcopy(limits or LIMITS)
        if self.status_path.exists():
            self.data=json.loads(self.status_path.read_text())
            if self.data['limits']!=wanted:raise BudgetStop('Existing round limits differ; no silent quota change')
        else:
            self.data=dict(schema='bc-rpi-round1-budget-v1',status='registered_before_calls',phase=None,
                campaign_start_epoch=now(),carry_in=deepcopy(CARRY_IN),limits=wanted,
                entered=0,full_runs=0,suffix_runs=0,fixture_runs=0,executions_started=0,
                executions_completed=0,business_calls=0,accepted_calls=0,failed_calls=0,
                rejected_calls=0,exception_calls=0,unknown_cost_calls=0,failed_runs=0,
                unknown_cost_runs=0,network_training_runs=0,reserved_calls=0,current_run=None,
                stopped_for_unknown_acceptance=False,runs=[],
                phase_calls={k:0 for k in wanted['phase_calls']},
                phase_executions={k:0 for k in wanted['phase_calls']},
                observed_combined_rss_bytes=0)
            self.save()
        if self.data['current_run'] is not None:raise BudgetStop('Previous actual run unsettled; audit before resuming')
        if self.journal_path.exists():
            open_runs=set()
            for line in self.journal_path.read_text().splitlines():
                row=json.loads(line)
                if row['event']=='run_start':open_runs.add(row['run_id'])
                elif row['event']=='run_finish':open_runs.discard(row['run_id'])
            if open_runs:raise BudgetStop('Journal has an unsettled run; no automatic restart')

    def save(self):
        d=self.data
        d['updated_utc']=datetime.fromtimestamp(self.now(),timezone.utc).isoformat()
        d['wall_since_registration_s']=max(0.,self.now()-d['campaign_start_epoch'])
        d['historical_total_business_calls']=d['carry_in']['business_calls']+d['business_calls']
        d['historical_total_executions']=d['carry_in']['executions_started']+d['executions_started']
        atomic_json(self.status_path,d)

    def append(self,row):
        value=dict(row,recorded_utc=datetime.fromtimestamp(self.now(),timezone.utc).isoformat())
        with self.journal_path.open('a') as f:
            f.write(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')

    def set_phase(self,phase,status=None):
        if phase not in self.data['limits']['phase_calls']:raise ValueError('Unknown authorized phase')
        if self.data['current_run'] is not None:raise BudgetStop('Cannot change phase during an actual run')
        self.data['phase']=phase;self.data['status']=status or 'running_'+phase;self.save()

    def set_status(self,status):self.data['status']=status;self.save()
    def register_worker(self,pid):self.worker_pids.add(int(pid))
    def unregister_worker(self,pid):self.worker_pids.discard(int(pid))

    def resources(self):
        if self.resource_probe is not None:return self.resource_probe()
        own_peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        child_rss=0
        if self.worker_pids:
            result=subprocess.run(['/bin/ps','-o','rss=','-p',','.join(str(p) for p in sorted(self.worker_pids))],
                                  capture_output=True,text=True,check=False)
            if result.returncode not in (0,1):raise BudgetStop('Cannot inspect controlled worker RSS')
            child_rss=sum(int(v)*1024 for v in result.stdout.split())
        raw=sum(p.stat().st_size for p in self.directory.rglob('*') if p.is_file())
        return own_peak+child_rss,raw

    def check_resources(self):
        d=self.data
        if self.now()-d['campaign_start_epoch']>=d['limits']['campaign_wall_s']:
            raise BudgetStop('Round wall-time cap reached')
        rss,raw=self.resources();d['observed_combined_rss_bytes']=max(d['observed_combined_rss_bytes'],rss)
        if rss>d['limits']['rss_bytes']:raise BudgetStop('Combined main/controlled-worker RSS cap reached')
        if raw>=d['limits']['raw_bytes']:raise BudgetStop('Round raw-data cap reached')

    def start(self,run_id,kind,metadata=None):
        d=self.data;phase=d['phase'];reserve=d['limits']['run_call_reserve']
        if d['current_run'] is not None:raise BudgetStop('Only one active actual run allowed')
        if d['stopped_for_unknown_acceptance']:raise BudgetStop('Unknown acceptance requires independent audit')
        if phase not in d['limits']['phase_calls']:raise BudgetStop('Register an authorized phase before execution')
        if kind not in ('full','suffix','fixture'):raise ValueError('Unknown execution kind')
        if any(r['run_id']==run_id for r in d['runs']):raise BudgetStop('Run ID already executed; no hidden replay')
        if d['business_calls']+reserve>d['limits']['business_calls']:raise BudgetStop('Insufficient total full-tail reserve')
        if d['phase_calls'][phase]+reserve>d['limits']['phase_calls'][phase]:raise BudgetStop('Insufficient phase full-tail reserve')
        if d['executions_started']>=d['limits']['executions']:raise BudgetStop('Round execution cap reached')
        if phase=='compatibility' and d['phase_executions'][phase]>=d['limits']['compatibility_executions']:
            raise BudgetStop('Registered compatibility execution cap reached')
        self.check_resources()
        d['executions_started']+=1;d[kind+'_runs']+=1;d['phase_executions'][phase]+=1
        d['reserved_calls']=reserve
        d['current_run']=dict(run_id=run_id,kind=kind,attempted=0,accepted=0,failed=0,
            metadata=dict(metadata or {},stage=phase),started_monotonic=self.monotonic(),pending_call=None,
            unknown_acceptance_calls=[])
        self.append(dict(event='run_start',**d['current_run']));self.save()

    def call(self,action,function,args,exception_evidence=None):
        d=self.data;r=d['current_run'];phase=d['phase']
        if r is None:raise RuntimeError('Actual interface call without registered run')
        if d['stopped_for_unknown_acceptance']:raise BudgetStop('Unknown acceptance forbids fallback or retry')
        if (r['attempted']>=d['limits']['run_call_reserve'] or d['business_calls']>=d['limits']['business_calls']
                or d['phase_calls'][phase]>=d['limits']['phase_calls'][phase]):
            raise BudgetStop('Hard per-run, round or phase actual-call cap reached')
        sequence=d['business_calls'];d['business_calls']+=1;d['phase_calls'][phase]+=1
        r['attempted']+=1;d['reserved_calls']-=1;r['pending_call']=sequence
        self.append(dict(event='call_start',run_id=r['run_id'],sequence=sequence,action=action,args=list(args)))
        started=self.monotonic()
        try:response=function(*args)
        except BaseException as exc:
            d['exception_calls']+=1
            evidence=exception_evidence() if exception_evidence else {'acceptance':'unknown'}
            self.append(dict(event='call_exception',run_id=r['run_id'],sequence=sequence,
                             error=type(exc).__name__+': '+str(exc),**evidence))
            if evidence['acceptance']=='unknown':
                r['unknown_acceptance_calls'].append(sequence);d['unknown_cost_calls']+=1
                d['stopped_for_unknown_acceptance']=True;d['status']='stopped_unknown_acceptance'
            else:r['failed']+=1;d['rejected_calls']+=1;d['failed_calls']+=1
            r['pending_call']=None;self.save();raise
        accepted=response.get('accepted') is True
        if accepted:
            d['accepted_calls']+=1;r['accepted']+=1
            if action=='enter':d['entered']+=1
        else:d['failed_calls']+=1;d['rejected_calls']+=1;r['failed']+=1
        self.append(dict(event='call_response',run_id=r['run_id'],sequence=sequence,accepted=accepted,
                         response=response,backend_wall_s=self.monotonic()-started))
        r['pending_call']=None
        if d['business_calls']%25==0:self.save()
        return response

    def finish(self,success,details=None,unknown_cost=False):
        d=self.data;r=d['current_run']
        if r is None or r['pending_call'] is not None:raise BudgetStop('Cannot settle unknown in-flight request')
        unknown=bool(unknown_cost or r['unknown_acceptance_calls']);success=bool(success and not unknown)
        row={k:v for k,v in r.items() if k not in ('started_monotonic','pending_call')}
        row.update(success=success,unknown_cost=unknown,details=details or {},actual_wall_s=self.monotonic()-r['started_monotonic'])
        d['runs'].append(row);d['executions_completed']+=1;d['failed_runs']+=not success
        d['unknown_cost_runs']+=unknown;d['reserved_calls']=0;d['current_run']=None
        if d['business_calls']!=d['accepted_calls']+d['rejected_calls']+d['unknown_cost_calls']:
            raise BudgetStop('Attempted accepted/rejected/unknown partition failed')
        if d['business_calls']!=sum(d['phase_calls'].values()):raise BudgetStop('Phase call partition failed')
        self.append(dict(event='run_finish',**row));self.save();return row
