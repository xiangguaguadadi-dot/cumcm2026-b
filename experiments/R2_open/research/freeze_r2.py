from pathlib import Path
import json,hashlib,datetime,ast
out=Path('experiments/R2_open');folder=out/'results/r2_development'
def read(p):return json.loads(p.read_text())
s=read(folder/'summary.json');means={name:next(g['mean'] for g in v['groups'] if g['mode']==3 and g['group']=='ALL') for name,v in s.items()};selected=min(means,key=means.get);assert selected=='same_location'
fields=['cleared_count','source_count','complete','exit_reason','error','average_clear_time_s','total_virtual_time_s','distance_m','requests','clear_failures']
p=read(folder/'parent_rows.json');idx={r['case_id']:r for r in p}
assert all(r['complete'] and all(r[k]==idx[r['case_id']][k] for k in fields) for name in s for r in read(folder/(name+'_rows.json')) if r['mode']==4)
src=(out/'snapshots/r2_development.py').read_text().replace('active_information=False, same_location_clear=False),','active_information=False, same_location_clear=True),')
(out/'snapshots/r2_solver.py').write_text(src)
result=dict(selected=selected,development_means=means,geometry_checks=sum(v['geometry_checks'] for v in s.values()),same_location_clears=sum(r['counters'].get('same_location_clears',0) for r in read(folder/'same_location_rows.json')),q4_task_fields_equal=True,candidate_sha256=hashlib.sha256(src.encode()).hexdigest(),data_role='development selection, not holdout',active_negative_result='Active component increases Q3 mean 1.253634336s/source with 3 extra requests/episode despite 20.337m lower distance. Same-location improvement is extremely small; awaiting full exposed test.')
(out/'research/r2_selection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
data=read(out/'optimization_path.json');data['rounds'][-1].update(status='frozen_awaiting_regression',after_development=result);(out/'optimization_path.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
(out/'research/r2_reliability.md').write_text('''# R2 同址认证服务与不采纳的主动测点\n\n开发选择只打开same_location_clear，active_information关闭。R1认证多边形保持不变。设当前位置p，若多边形全部顶点v满足距离(p,v)≤20−1e−6，则任意凸组合x由范数凸性也满足距离(p,x)≤20−1e−6，因此其中真源可直接clear认证成功。空多边形不由有效流程产生，非空约束沿用R1。只清除已发现且未清的源，成功记录后不重复；_servicing锁阻止递归。clear不切换频道、无位移，后续测向的信道状态不变。父测向包装结束后可能另一个源被清，父所有localize进入/动作后均查cleared，发现与退出证书不削弱。每个源最多一次附加成功clear，共≤16×5=80秒；合成R1宽松283011秒界变为283091秒<360000秒。共享费用记账可能把嵌套成功clear纳入预算，更早停止共享仍保守。\n\n主动测点仅属于开发负结果与源码可重现配置：19候选×9位置假设×3误差的代理没有捕捉与协同补测重叠的后续代价，开发增加请求数；不能从A2原有独立收益推出与B1融合必有收益。假想观测不写入真实集合。未改变HTTP/并发/重试。\n''')
print(json.dumps(result,ensure_ascii=False))
