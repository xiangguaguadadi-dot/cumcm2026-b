"""Recompute A2 experiment ledger from all preserved per-case files."""
import ast,hashlib,json,statistics
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def valid(r):return r['complete'] and r['cleared_count']==r['source_count'] and not r.get('error') and r['exit_reason']=='user_exit'
def compare(rows,base):
    ix={r['case_id']:r for r in base};assert len(ix)==len(base)
    out=[]
    for mode in [3,4]:
        part=[r for r in rows if r['mode']==mode]
        if not part:continue
        refs=[ix[r['case_id']] for r in part];assert all(valid(r) for r in part+refs)
        ds=[r['average_clear_time_s']-b['average_clear_time_s'] for r,b in zip(part,refs)]
        out.append(dict(mode=mode,cases=len(part),cleared=sum(r['cleared_count'] for r in part),sources=sum(r['source_count'] for r in part),
            mean_s_per_source=statistics.mean(r['average_clear_time_s'] for r in part),delta=statistics.mean(ds),
            faster=sum(x< -1e-8 for x in ds),equal=sum(abs(x)<=1e-8 for x in ds),slower=sum(x>1e-8 for x in ds),
            movement=statistics.mean(r['distance_m']/5/r['source_count'] for r in part),
            nonmovement=statistics.mean((r['total_virtual_time_s']-r['distance_m']/5)/r['source_count'] for r in part),
            max_regression=max(ds),regressions=[dict(case_id=r['case_id'],delta=d)for r,d in zip(part,ds)if d>1e-8]))
    return out

base=read(ROOT/'experiments/20260911_stage4/combination/results/c7_exposed/case_metrics.json')
names=['R1_rotation','R2_rotation_insertion','R3_deferred_rotation','R4_commit_rotation','R5_continuous_rotation']
batches=['r1_rotation_dev','r2_rotation_insertion_dev','r3_deferred_rotation_dev','r4_commit_rotation_dev','r5_continuous_rotation_dev']
ledger=[]
for i,(name,batch) in enumerate(zip(names,batches),1):
    quick=[r for r in read(HERE/f'results/r{i}_quick/case_metrics.json') if r['variant']=='candidate']
    dev=read(HERE/f'results/{batch}/summary.json')[name]
    entry=dict(round=i,name=name,sha256=sha(HERE/(name+'.py')),parent='C7' if i==1 else 'R1' if i==2 else 'R2',
        status='retained_marginal' if i<=2 else 'rejected_development_and_quick',development=dev['comparisons'][0],quick=compare(quick,base),
        note='Design recorded in plan/source and agent updates before execution; this summary ledger is reconstructed after execution')
    if i<=2:
        full=read(HERE/f'results/r{i}_exposed/case_metrics.json');entry['exposed']=compare(full,base)
        if i==2:entry['versus_R1']=compare(full,read(HERE/'results/r1_exposed/case_metrics.json'))
    ledger.append(entry)
# Count actual executions and requests, excluding cached comparisons and reused
# v1 rows. Packaging repeats are costs, not new independent worlds or rounds.
executions=[]
def add_execution(label,rows,expected,wall):
    assert len(rows)==expected,(label,len(rows),expected)
    assert all(valid(r) for r in rows),label
    executions.append(dict(batch=label,runs=len(rows),requests=sum(r['requests'] for r in rows),
        wall_seconds=wall,source_instances=sum(r['source_count'] for r in rows),
        row_runtime_seconds=sum(r.get('program_runtime_s',r.get('runtime_s',0.)) for r in rows)))
for p in sorted((HERE/'results').glob('*/summary.json')):
    data=read(p)
    if 'runs' in data or 'new_runs' in data:
        rows=[r for r in read(p.parent/'case_metrics.json') if r.get('variant')=='candidate']
        if data.get('v1_reused'):
            reused=read(Path(data['v1_reused']['path'])/'case_metrics.json')
            reused_ids={r['case_id'] for r in reused if r.get('variant')=='candidate'}
            rows=[r for r in rows if r['case_id'] not in reused_ids]
        count=data.get('runs',data.get('new_runs'))
        add_execution(p.parent.name,rows,count,data.get('wall_seconds',data.get('wall_seconds_new_runs')))
    else:
        for name,entry in data.items():
            if isinstance(entry,dict) and entry.get('runs',0)>0:
                add_execution(p.parent.name+'/'+name,read(p.parent/(name+'_rows.json')),entry['runs'],entry['wall_s'])
runs=sum(e['runs'] for e in executions)
result=dict(best='R2_rotation_insertion.py',self_contained='BEST_R2.py',rounds=ledger,
    stop=dict(rotation='3 consecutive unpromoted rounds R3/R4/R5 after R2',topology='3 bounded rounds; no novel topology obtained a complete continuous certificate'),
    actual_task_runs=runs,distinct_new_development_cases=96,new_development_seeds=[62000000,62000095],
    execution_costs=dict(batches=executions,requests=sum(e['requests'] for e in executions),
        summed_batch_wall_seconds=sum(e['wall_seconds'] for e in executions),
        semantics='Actual local requests include enter/measure/clear/exit, with repeats counted. Summed batch wall time excludes literature, geometry, rules, analysis and orchestration; not total elapsed project time.'),
    exposed_cases=4800,independent_new_final_cases=0,official_runs=0,
    hashes={p.name:sha(p) for p in HERE.glob('*.py')},frozen_manifest_sha256=sha(ROOT/'evaluation/manifest_v1.json'))
pack=HERE/'results/best_r2_packaging_exposed/case_metrics.json'
if pack.exists():
    packed=read(pack);prior=read(HERE/'results/r2_exposed/case_metrics.json')
    fields=['case_id','mode','group','cleared_count','source_count','complete','error','exit_reason','average_clear_time_s','total_virtual_time_s','requests','distance_m','clear_failures']
    assert [[r.get(k) for k in fields]for r in packed]==[[r.get(k) for k in fields]for r in prior]
    packaged_ast=ast.parse((HERE/'BEST_R2.py').read_text())
    embedded=[n.args[0].value for n in ast.walk(packaged_ast) if isinstance(n,ast.Call)
        and isinstance(n.func,ast.Name) and n.func.id=='compile'
        and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str)]
    c7=ROOT/'experiments/20260911_stage4/combination/geometry_fusions/C7_both.py'
    assert embedded==[c7.read_text()]
    component_ast=ast.parse((HERE/'retained_component.py').read_text())
    def body_from_config(tree):
        start=next(i for i,n in enumerate(tree.body) if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=='BASELINE_CONFIG' for t in n.targets))
        return ast.dump(ast.Module(body=tree.body[start:],type_ignores=[]),include_attributes=False)
    assert body_from_config(packaged_ast)==body_from_config(component_ast)
    result['packaging_parity']=dict(cases=4800,fields=fields,exact=True,
        embedded_C7_source_exact=True,embedded_C7_sha256=sha(c7),component_ast_exact=True,
        candidate_sha256=sha(HERE/'BEST_R2.py'),rows_sha256=sha(pack))
(HERE/'iteration_ledger.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['best','actual_task_runs','distinct_new_development_cases','stop']}))
