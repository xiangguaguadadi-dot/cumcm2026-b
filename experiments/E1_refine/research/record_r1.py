from pathlib import Path
import json
P=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2))
s=read(P/'results/r1_exposed/summary.json')
b=read(P/'execution_budget.json')
for name,n in [('r1_full',2400),('r2_quick',120),('r1_exposed',2400)]:
    if any(x['label']==name for x in b['runs']):continue
    z=read(P/'results'/name/'summary.json')
    info=z.get('execution',z)
    b['runs'].append(dict(label=name,type='exposed_regression',actual_runs=n,unique_new_cases=0,wall_seconds=info.get('wall_seconds_new_runs',info.get('wall_seconds'))))
    b['policy_task_runs']+=n
save(P/'execution_budget.json',b)
save(P/'best.json',dict(round='R1',candidate='experiments/E1_refine/snapshots/r1_posterior.py',candidate_sha256='d3112c89a555c13b589d01f4de9aa952dc3c5d89299845e4f0e2aff21d5fbe82',results='experiments/E1_refine/results/r1_exposed',all_complete=True,Q3=235.87694581189243,Q4=471.470944912203,comparison='fixed S1; 4800 exposed cases',status='current own best; ongoing research'))
text='''# E1 第四阶段结果（研究继续中）

R1条件发现路线在4800个已暴露回归任务全部清除：Q3逐局等于S1；Q4为471.470944912秒/源，相对S1 473.897492999秒/源减少2.426548087（0.51204%）。Q4 2400案例30970源，867快、790同、743慢。v1批次减少2.323615428，旧final批次减少2.529480747。本地假设案例结果，不是官方运行或新留出。

机制只改完整任务访问顺序。离散几何假说估计真实扫过的站点对未知频道的覆盖，以10至16个源的显式均匀先验估计到16频道时取消剩余站点的期望路线成本；该概率仅排序，真实退出仍要求完整原覆盖或实际观察到16个互异频道，未清源仍须清除。假说不读取测试标签、种子、真值或缓存成绩。候选内嵌两个父源码，单文件可部署，SHA见best.json。

开发存在明显排序波动：最初144 Q4案例原代理慢1.895750秒/源，乐观代理慢2.866983；另288案例原代理快1.099561，仅15频道代理快0.152853，15频道乐观代理慢0.481255。所有尝试全清且保留，不能把开发收益称稳定。R2收尾代理仅完成quick120，未用微小开发收益追加full。R1 quick120、full2400、补旧final2400均完成；补测复用相同候选v1结果2400，不再执行一次基线。

完整分批、场景、退步和身份见results/r1_exposed/summary.json及case_metrics.json，原开发见development/；真实执行预算见execution_budget.json。已有12规则检查通过，冻结环境未改变。下一机制是固定任务序下联合优化多个认证20m清除区域的落点，尚无结果。
'''
(P/'report.md').write_text(text)
with (P/'resume.md').open('a')as f:f.write('\nR1 exposed已经完成（勿重跑），全4800清；Q3原样，Q4=471.470944912203；结果results/r1_exposed，best已更新。当前开始R3联合认证区域落点。\n')
with (P/'optimization_path.md').open('a')as f:f.write('\nR1 full+旧final4800全部清，Q4比S1快2.426548087秒/源，当前保留；R2仅15频道版本开发收益小，未追加full。R3准备联合已认证清除落点，固定原任务序，不涉及第二测点信息效用。\n')
