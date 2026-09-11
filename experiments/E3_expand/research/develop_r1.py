from pathlib import Path
import sys,json,time,importlib.util,hashlib
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
def load(p):
    s=importlib.util.spec_from_file_location('e3_'+hashlib.sha256(p.read_bytes()).hexdigest()[:12],p)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
D=load(ROOT/'experiments/R3_open/research/develop_r4.py')
OUT=ROOT/'experiments/E3_expand'
folder=OUT/'results/r1_development';folder.mkdir(exist_ok=False)
seeds=list(range(46000000,46000008))
cases=[D.make_case(seed,4,g,s,n) for g,s,n in D.GROUPS for seed in seeds]
for c in cases:c['case_id']=c['case_id'].replace('B1-dev','E3-r1-dev')
(folder/'cases.json').write_text(json.dumps(cases,indent=2))
variants=[('S1',ROOT/'experiments/20260911_stage4/baseline/S1.py',{}),
          ('clear600',OUT/'snapshots/r1_development.py',{}),
          ('clear1000',OUT/'snapshots/r1_development.py',{'initialization_spacing_m':1000.}),
          ('stop600',OUT/'snapshots/r1_development.py',{'initialization_on':'stop'}),
          ('stop1000',OUT/'snapshots/r1_development.py',{'initialization_on':'stop','initialization_spacing_m':1000.})]
summary={};st=time.perf_counter()
for label,path,config in variants:
    module=load(path);vt=time.perf_counter();rows=[]
    for case in cases:rows.append(dict(D.run_case(module,case,config),variant=label))
    (folder/(label+'_rows.json')).write_text(json.dumps(rows,indent=2))
    summary[label]=dict(source=str(path.relative_to(ROOT)),sha256=D.sha(path),config=config,runs=len(rows),wall_s=time.perf_counter()-vt,groups=D.summarize(rows))
    print(label,[x for x in summary[label]['groups'] if x['group']=='ALL'],flush=True)
    (folder/'summary.json').write_text(json.dumps(summary,indent=2))
(folder/'budget.json').write_text(json.dumps(dict(actual_runs=len(cases)*len(variants),unique_cases=len(cases),seeds=seeds,wall_s=time.perf_counter()-st),indent=2))
(OUT/'used_seeds.json').write_text(json.dumps(dict(allocated_interval=[46000000,47000000],next_seed=46000008,sets=[dict(purpose='r1_development',seeds=seeds,cases=96)]),indent=2))
