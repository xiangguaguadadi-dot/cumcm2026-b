"""Evaluator-side public decision telemetry; never supplied to the strategy.

Replays quick only to resolve trigger/outcome diagnostics omitted by the frozen
common metrics. The original second_point and measure each execute once.
"""
import argparse,hashlib,importlib.util,json,math,pathlib,sys,time,collections
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from local_env import LocalEnv,Source,InterfaceOnly

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',required=True);ap.add_argument('--out',required=True);args=ap.parse_args()
    path=HERE/args.candidate;mod=load(path,'diagnostic_candidate')
    cases=json.loads((ROOT/'evaluation/cases_v1.json').read_text());cases=[c for c in cases if c['quick']]
    out=HERE/args.out;out.mkdir(parents=True,exist_ok=False)
    summary=[];calls=[];active=[]
    original_second=mod._Q2ATransfer.second_point
    def second(self,ch):
        before=dict(self.counters)
        record={'call_index':len(active),'mode':self.mode,'channel':ch,'position_before':self.position,'observations':len(self.observations[ch]),'polygon_vertices':len(self.polygons[ch]),'prior_radius':mod._q2a_circle(self.polygons[ch])[1],'measurement_result':None}
        q=original_second(self,ch)
        record.update(proposal=q,selected=self.counters.get('q2a_selected',0)>before.get('q2a_selected',0),geometry_evaluations=self.counters.get('q2a_geometry_evals',0)-before.get('q2a_geometry_evals',0))
        active.append(record)
        return q
    mod._Q2ATransfer.second_point=second
    for cls in (mod._Q2ASpatial,mod._Q2ADirectional):
        original_measure=cls.measure
        def measure(self,p,ch,_original=original_measure):
            pending=next((r for r in reversed(active) if r['measurement_result'] is None and r['channel']==ch and math.dist(p,r['proposal'])<1e-5),None)
            start=len(self.trace);kind=_original(self,p,ch)
            if pending is not None:
                events=[r for r in self.trace[start:] if r.get('action')=='measure' and r.get('channel')==ch and math.dist((r['x'],r['y']),pending['proposal'])<1e-5]
                pending.update(measurement_result=kind,cleared_by_return=ch in self.cleared,observations_after=len(self.observations[ch]),posterior_radius=mod._q2a_circle(self.polygons[ch])[1] if kind=='direction' else None,actual_measurement_event=events[0] if events else None)
            return kind
        cls.measure=measure
    started=time.perf_counter()
    with (out/'second_point_calls.jsonl').open('w') as stream:
        for case in cases:
            active.clear()
            env=LocalEnv([Source(**s) for s in case['sources']],case['seed'],case['noise'],keep_log=False)
            solver=mod.Solver(InterfaceOnly(env),mode=case['mode'],**mod.OPTIMIZED_CONFIGS[case['mode']])
            error=None
            try:solver.run()
            except Exception as e:error=repr(e)
            stats=env.stats()
            row={'case_id':case['case_id'],'mode':case['mode'],'group':case['group'],'error':error,'exit_reason':env.exit_reason,'stats':stats,'q2a_counters':{k:v for k,v in solver.counters.items() if k.startswith('q2a_')},'second_point_calls':len(active),'selected_calls':sum(r['selected'] for r in active)}
            summary.append(row)
            for record in active:
                record={'case_id':case['case_id'],'group':case['group'],**record};calls.append(record);stream.write(json.dumps(record)+'\n')
            stream.flush()
    modes=[]
    for mode in (3,4):
        rr=[r for r in calls if r['mode']==mode];selected=[r for r in rr if r['selected']]
        modes.append({'mode':mode,'cases':sum(r['mode']==mode for r in summary),'calls':len(rr),'selected_calls':len(selected),'cases_selected':len({r['case_id'] for r in selected}),'all_outcomes':dict(collections.Counter(r['measurement_result'] for r in rr)),'selected_outcomes':dict(collections.Counter(r['measurement_result'] for r in selected)),'geometry_evaluations':sum(r['geometry_evaluations'] for r in rr),'unmatched_measurements':sum(r['measurement_result'] is None for r in rr)})
    report={'candidate_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'diagnostic_actual_runs':len(cases),'purpose':'public trigger and actual second-observation outcomes; not additional selection set','elapsed_seconds':time.perf_counter()-started,'modes':modes,'cases':summary}
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(modes,indent=2))
if __name__=='__main__':main()
