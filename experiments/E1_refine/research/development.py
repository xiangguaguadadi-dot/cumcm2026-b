from pathlib import Path
import ast,hashlib,json,math,random,statistics,sys,time,importlib.util
ROOT=Path(__file__).resolve().parents[3];OWN=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from local_env import Source
import evaluate

def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def generate(label,start,count,modes):
    parsed=ast.parse((ROOT/'evaluation/generate_cases.py').read_text())
    fn=next(x for x in parsed.body if isinstance(x,ast.FunctionDef)and x.name=='sources')
    groups=ast.literal_eval(next(x.value for x in parsed.body if isinstance(x,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='groups'for t in x.targets)))
    namespace={'Source':Source,'random':random,'math':math}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'frozen_sources_function','exec'),namespace)
    sources=namespace['sources'];seeds=list(range(start,start+count));cases=[]
    for mode in modes:
      for group,scenario,noise in groups:
       for seed in seeds:
        values=sources(seed,mode,scenario)
        cases.append(dict(case_id=f'DEV-E1-{label}-q{mode}-{group}-{seed}',mode=mode,group=group,noise=noise,seed=seed,sources=[vars(x)for x in values]))
    return cases,seeds

def main():
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--label',required=True);a.add_argument('--start',type=int,required=True);a.add_argument('--count',type=int,required=True);a.add_argument('--modes',default='4');a.add_argument('--candidates',required=True);args=a.parse_args()
    folder=OWN/'development'/args.label;folder.mkdir(exist_ok=False)
    cases,seeds=generate(args.label,args.start,args.count,list(map(int,args.modes.split(','))))
    assert 44000000<=min(seeds)<=max(seeds)<45000000
    ledger=read(OWN/'used_seeds.json')if(OWN/'used_seeds.json').exists()else{'range':[44000000,45000000],'rounds':[]}
    old={v for x in ledger['rounds']for v in x['seeds']};assert not old.intersection(seeds)
    candidates=read(OWN/args.candidates)
    registration={'label':args.label,'observation':'Conditional completion of discovery after 16 distinct channels can cancel future stations; route proxy previously charged all stations.','selection_rule':'All cases complete, then minimum mode-wise mean seconds/source; retain parent if no improvement.','cases':len(cases),'seeds':seeds,'candidate_identity':candidates,'source_generator_sha256':sha(ROOT/'evaluation/generate_cases.py'),'role':'new development, not holdout'}
    save(folder/'registration.json',registration);save(folder/'cases.json',cases)
    ledger['rounds'].append({'label':args.label,'seeds':seeds,'modes':args.modes,'case_count':len(cases),'cases_file':str((folder/'cases.json').relative_to(ROOT))});save(OWN/'used_seeds.json',ledger)
    results=[]
    for candidate in candidates:
      path=ROOT/candidate['file'];assert sha(path)==candidate['sha256'];start=time.perf_counter()
      rows=evaluate.run_cases(cases,path,False);elapsed=time.perf_counter()-start;save(folder/(candidate['name']+'_rows.json'),rows)
      result={'candidate':candidate['name'],'actual_runs':len(rows),'wall_seconds':elapsed,'all_complete':all(r.get('complete')for r in rows),'modes':[]}
      for mode in sorted({r['mode']for r in rows}):
        z=[r for r in rows if r['mode']==mode];good=all(r.get('complete')for r in z)
        result['modes'].append({'mode':mode,'cases':len(z),'complete':sum(bool(r.get('complete'))for r in z),'mean_s_per_source':statistics.mean(r['average_clear_time_s']for r in z)if good else None,'mean_distance_m':statistics.mean(r['distance_m']for r in z)if good else None,'mean_requests':statistics.mean(r['requests']for r in z)if good else None,'mean_failed_clear':statistics.mean(r['clear_failures']for r in z)if good else None,'max_runtime_s':max(r['program_runtime_s']for r in z)})
      results.append(result);save(folder/'summary.json',results);print(json.dumps(result),flush=True)
    budget=read(OWN/'execution_budget.json')if(OWN/'execution_budget.json').exists()else{'policy_task_runs':0,'new_unique_development_cases':0,'runs':[]}
    budget['policy_task_runs']+=sum(x['actual_runs']for x in results);budget['new_unique_development_cases']+=len(cases);budget['runs'].append({'label':args.label,'type':'development','actual_runs':sum(x['actual_runs']for x in results),'unique_cases':len(cases),'wall_seconds':sum(x['wall_seconds']for x in results)});save(OWN/'execution_budget.json',budget)
if __name__=='__main__':main()
