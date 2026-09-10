"""Resolve each source to implemented functions and actual evidence after experiments."""
import json
from pathlib import Path
B=Path(__file__).resolve().parents[1];p=B/'literature.json';x=json.loads(p.read_text());best=json.loads((B/'best.json').read_text())
functions={
 'ars':['scripts/train_policy.py:main','scripts/train_policy.py:evaluate','solver.py:Solver.learned_source_cost'],
 'dagger':['scripts/train_policy.py:episode (induced-policy trajectories; NOT DAgger)'],
 'attention':['solver.py:Solver.learned_source_cost','solver.py:Solver.run','scripts/train_policy.py:main (paired development)'],
 'shield':['solver.py:certified_points','solver.py:Solver.cover_polygon','solver.py:Solver.run (unchanged exit certificate)','scripts/audit_policy.py'],
 'es':['scripts/train_policy.py:main (parameter-space search inspiration only)'],
 'ppo':[], 'bo':[], 'pilco':[],
 'neural_co':['scripts/train_policy.py:episode','scripts/train_policy.py:evaluate (whole-episode objective only)'],
 'gp_sensor':['scripts/train_policy.py:make_training_case (correlated noise coverage)']}
implemented={'ars','attention','shield','es','neural_co','gp_sensor'}
for paper in x['papers']:
 id=paper['id'];paper['implementation_functions']=functions[id]
 paper['implemented_as_paper_algorithm']=False
 paper['principle_or_mechanism_adopted']=id in implemented or id=='dagger'
 links=[]
 if id in ('ars','es','neural_co','dagger','gp_sensor'):
  for h in best['history']:
   n=h['round'];links.append(dict(round=n,training_path=f'experiments/A6_learning/training/r{n}',full_path=f'results/A6_learning_r{n}_full',decision=h['decision'],role='training/search/evaluation principle, not original algorithm replication'))
 elif id=='attention':
  for h in best['history']:
   if h['round']>=2:links.append(dict(round=h['round'],function='Solver.learned_source_cost',full_path=f'results/A6_learning_r{h["round"]}_full',decision=h['decision'],role='observation-set context, no attention network'))
 elif id=='shield':
  for h in best['history']:links.append(dict(round=h['round'],function='certified_points / cover_polygon / run exit certificate',full_path=f'results/A6_learning_r{h["round"]}_full',role='all full runs complete; geometric argument and preserved-code audit, not synthesized LTL shield'))
 paper['round_links']=links
 if id in ('ppo','bo','pilco'):
  paper['empirical_support']='未实现原论文算法，没有同预算本题对照；仅做机制适配分析，不能声称本方案实测优于它。'
 elif id=='dagger':
  paper['empirical_support']='未训练DAgger或行为克隆，无教师对照。实际执行的是每个参数候选自己的整局轨迹，避免只在原专家轨迹评价；这是协议启发，不检验DAgger定理。'
 elif id=='shield':
  paper['empirical_support']=f'全部{len(best["history"])}轮full分别2400/2400完整清除；核心覆盖/清除/终止函数保留并做AST审查。可靠性解析依据写于report第6节；没有LTL自动合成实验。'
 elif id=='attention':
  paper['empirical_support']='第2轮上下文调度：Q3 306.814064472退步、Q4 552.956003578改善；第3轮恢复Q3后取得联合改进。整体候选比较支持Q4调度有效，但不等于attention网络复现或单一特征因果证明。'
 elif id=='gp_sensor':
  paper['empirical_support']='所有训练轮包含自行生成的不同相关误差场；没有训练GP地图、信息增益控制器或验证其子模近似界。源场景退步在report逐项列出。'
 else:
  paper['empirical_support']='参数空间整局搜索实际完成；第1轮静态参数失败，第2轮形成Q3/Q4取舍，第3轮组合成为联合改进。每轮的全部尝试数、开发与full数据可追溯；不把原论文跨任务成绩移植到本题。'
for paper in x['papers']:
 if paper['id'] in ('ars','es','neural_co','attention'):
  trace='；'.join(f'R{h["round"]}: Q3={h["means_s_per_source"]["3"]:.6f}, Q4={h["means_s_per_source"]["4"]:.6f}, {h["decision"]}' for h in best['history'])
  paper['empirical_support']+=' 全轮full轨迹（秒/源）：'+trace+'。交互特征等后续扩展仍是原创特征搜索，不能归因于论文原算法。'
  paper['implementation_mapping']=paper['implementation_mapping'].replace('直接进入三轮训练器','进入各轮训练器')
for paper in x['papers']:
 paper['diagnostic_links']=[]
 if (B/'development_ablation/summary.json').exists() and paper['id'] in ('ars','attention','es','neural_co','shield'):
  paper['diagnostic_links']=[dict(path='experiments/A6_learning/development_ablation/summary.json',scope='post-selection exposed R7 development; 9 variants x 288 cases; no tuning',purpose='conditional single-feature removal diagnostic, not a new holdout')]
  paper['empirical_support']+=' 停止后的开发诊断2592/2592全清；移除station_gain、workload、boundary在该已暴露开发集反而更快，不能给每个学得特征都分配正收益；未据此再调参。'
x['coverage_limits']='核心4篇为实际正文深读，扩展6篇为明确范围的正文节选；并未完整阅读所有附录，亦未做这些论文算法的同预算实现对照。'
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
