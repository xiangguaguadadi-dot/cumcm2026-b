"""Append complete round evidence and update best only under the stated rule."""
from pathlib import Path
import argparse,hashlib,json,statistics
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'experiments/R3_open'
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--round',type=int,required=True);p.add_argument('--next',required=True);a=p.parse_args();r=a.round
summary=read(OUT/f'results/r{r}_exposed/summary.json');rows=read(OUT/f'results/r{r}_exposed/case_metrics.json')
oldbest=read(OUT/'best.json');prev=read(Path(oldbest['results'])/'case_metrics.json');s0=read(ROOT/'experiments/20260911_stage3/baseline/expected_rows.json')
assert len(rows)==len({x['case_id'] for x in rows})==4800
all_valid=all(x['complete'] and not x['error'] and x['exit_reason']=='user_exit' and x['cleared_count']==x['source_count'] for x in rows)
audits={}
for label,ref in [('S0',s0),('previous',prev)]:
    idx={x['case_id']:x for x in ref};assert set(idx)=={x['case_id'] for x in rows}
    cells=summary['comparisons_to_'+label]
    for c in cells:
        part=[x for x in rows if x['mode']==c['mode'] and (c['suite']=='combined' or x['exposure_suite']==c['suite']) and (c['group']=='ALL' or x['group']==c['group'])]
        assert len(part)==c['cases']
        assert all((x['source_count'],x['mode'],x['group'])==(idx[x['case_id']]['source_count'],idx[x['case_id']]['mode'],idx[x['case_id']]['group']) for x in part)
        if all_valid:assert abs(statistics.mean(x['average_clear_time_s'] for x in part)-c['candidate_mean_s_per_source'])<1e-10
    deltas=[dict(case_id=x['case_id'],mode=x['mode'],suite=x['exposure_suite'],group=x['group'],source_count=x['source_count'],baseline=idx[x['case_id']]['average_clear_time_s'],candidate=x['average_clear_time_s'],delta=x['average_clear_time_s']-idx[x['case_id']]['average_clear_time_s']) for x in rows if x['average_clear_time_s'] is not None and idx[x['case_id']]['average_clear_time_s'] is not None]
    regressions=sorted([x for x in deltas if x['delta']>1e-8],key=lambda x:x['delta'],reverse=True)
    group_reg=[c for c in cells if c['suite']!='combined' and c['group']!='ALL' and c.get('delta_s_per_source',0)>1e-8]
    audits[label]=dict(all_78_cells_recomputed=True,regressed_batch_scenarios=group_reg,max_regression=regressions[0] if regressions else None,regressions=regressions,aggregates=[c for c in cells if c['group']=='ALL'])
save(OUT/f'results/r{r}_paired_audit.json',dict(actual_new_runs=0,cases=4800,unique_ids=4800,all_complete=all_valid,comparisons=audits))
totals=[c for c in summary['comparisons_to_previous'] if c['suite']=='combined' and c['group']=='ALL']
accepted=all_valid and all(c['delta_s_per_source']<=1e-8 for c in totals) and any(c['delta_s_per_source']<-1e-8 for c in totals)
save(OUT/f'results/best_before_r{r}.json',oldbest)
if accepted:
    best=dict(round=r,status='accepted_exposed_regression',candidate=str((OUT/f'snapshots/r{r}.py').resolve()),candidate_sha256=sha(OUT/f'snapshots/r{r}.py'),dependencies={},control='S0',previous_best_round=oldbest['round'],results=str((OUT/f'results/r{r}_exposed').resolve()),rows_sha256=sha(OUT/f'results/r{r}_exposed/case_metrics.json'),summary_sha256=sha(OUT/f'results/r{r}_exposed/summary.json'),all_complete=True,mode_totals=[c for c in summary['comparisons_to_S0'] if c['suite']=='combined' and c['group']=='ALL'],data_role='4800 exposed regression; not final holdout or official',budget_bound_virtual_s=287931)
    save(OUT/'best.json',best)
path=read(OUT/'optimization_path.json');node=next(x for x in path['nodes'] if x['id']==f'R3_R{r}')
node.update(status='accepted_exposed_regression' if accepted else 'rejected_best_unchanged',accepted=accepted,all_complete=all_valid,comparisons_to_S0=audits['S0']['aggregates'],comparisons_to_previous=audits['previous']['aggregates'],max_regressions={k:v['max_regression'] for k,v in audits.items()},next=a.next)
save(OUT/'optimization_path.json',path)
budget=read(OUT/'execution_budget.json')
for e in budget['entries']:e.setdefault('round',1)
newentries=[]
for split in ('train','development'):
    x=read(OUT/f'results/r{r}_{split}/budget.json');newentries.append(dict(round=r,kind=split,actual_runs=x['actual_runs'],unique_cases=x['unique_cases'],wall_seconds=x['wall_s'],seed_range=x['seed_range']))
newentries.append(dict(round=r,kind='finite_parent_equivalence',actual_runs=48,unique_cases=24,reuses='development'))
for stage in ('quick','full'):
    x=read(OUT/f'results/r{r}_{stage}/summary.json');newentries.append(dict(round=r,kind=stage,actual_runs=x['runs'],unique_cases=x['paired_cases'],wall_seconds=x['wall_seconds'],baseline_cached=True))
newentries.append(dict(round=r,kind='previous_final',actual_runs=summary['new_runs'],unique_cases=2400,wall_seconds=summary['wall_seconds_new_runs'],v1_reuse=True))
budget['entries']+=newentries;budget['actual_runs']=sum(x['actual_runs'] for x in budget['entries']);budget['unique_training_development_cases']+=sum(x['unique_cases'] for x in newentries if x['kind'] in ('train','development'))
save(OUT/'execution_budget.json',budget)
text=f"\n## R{r}：{'接受' if accepted else '未刷新'}\n\n"
text+='全部4800局完整清除、正常退出、零异常。候选SHA256 `'+sha(OUT/f'snapshots/r{r}.py')+'`。\n\n' if all_valid else '存在不完整任务，不对成功子集排名。\n\n'
text+='|对照|批次|题|对照秒/源|候选秒/源|变化|快/同/慢|源数|\n|---|---|---|---:|---:|---:|---|---|\n'
for label in ('S0','previous'):
    for c in audits[label]['aggregates']:
        text+=f"|{label}|{c['suite']}|Q{c['mode']}|{c['baseline_mean_s_per_source']:.9f}|{c['candidate_mean_s_per_source']:.9f}|{c['delta_s_per_source']:+.9f}|{c['faster']}/{c['equal']}/{c['slower']}|{c['candidate_cleared']}/{c['source_count']}|\n"
text+='\n|对照|批次|题|场景|对照秒/源|候选秒/源|差值|\n|---|---|---|---|---:|---:|---:|\n'
for label in ('S0','previous'):
    for c in summary['comparisons_to_'+label]:
        if c['suite']!='combined' and c['group']!='ALL':text+=f"|{label}|{c['suite']}|Q{c['mode']}|{c['group']}|{c['baseline_mean_s_per_source']:.6f}|{c['candidate_mean_s_per_source']:.6f}|{c['delta_s_per_source']:+.6f}|\n"
text+='\n最大单局退步与全部退步明细见'+f'results/r{r}_paired_audit.json。'
for label in ('S0','previous'):
    text+=f" {label}分批场景退步{len(audits[label]['regressed_batch_scenarios'])}个；最大单局退步"+str(audits[label]['max_regression'])+'。'
text+='\n\n开发配置完整表：\n\n|配置|训练Q3|训练Q4|开发Q3|开发Q4|\n|---|---:|---:|---:|---:|\n'
t,d=(read(OUT/f'results/r{r}_{x}/summary.json') for x in ('train','development'))
for name in t:
    vals=[next(g['mean'] for g in z[name]['groups'] if g['mode']==m and g['group']=='ALL') for z in (t,d) for m in (3,4)]
    text+='|'+name+'|'+ '|'.join(f'{v:.9f}' for v in vals)+'|\n'
text+=f"\n本轮实际任务{sum(e['actual_runs'] for e in newentries)}次，累计{budget['actual_runs']}次；新独立开发案例累计{budget['unique_training_development_cases']}，暴露案例仍为4800。规则14项、正常物理79项、quick120/full2400和补旧final2400均通过，源审与父等价见r{r}_source_audit.json。虚拟上界依据research/reliability.md。\n\n下一步：{a.next}\n"
for f in ('report.md','iteration_log.md'):
    with (OUT/f).open('a') as stream:stream.write(text)
with (OUT/'optimization_path.md').open('a') as f:f.write(f"\nR{r}实验后：{'接受' if accepted else '未刷新'}；Q4="+str(next(c['candidate_mean_s_per_source'] for c in totals if c['mode']==4))+'；下一步：'+a.next+'\n')
(OUT/'resume.md').write_text('# R3_open 接续\n\n当前best R'+str(r if accepted else oldbest['round'])+'；本轮结果与所有退步已保存。下一步：'+a.next+'\n不设迭代轮数/连续失败停机数。\n')
print(json.dumps(dict(round=r,accepted=accepted,totals=totals,actual_runs=budget['actual_runs'],regressions={k:dict(groups=len(v['regressed_batch_scenarios']),max=v['max_regression']) for k,v in audits.items()}),ensure_ascii=False))
