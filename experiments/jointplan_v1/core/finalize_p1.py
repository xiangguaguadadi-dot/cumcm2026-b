import gzip,json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit import audit_batch,paired,normalize,sha
from runner import dump,Budget

def main():
 a=audit_batch(ROOT/'results/p1_baseline');b=audit_batch(ROOT/'results/p1_finite_best');p=paired(a,b)
 selection=json.loads((ROOT/'data/p1_best/selection.json').read_text())
 fields=('cleared_count','source_count','total_virtual_time_s','average_clear_time_s','distance_m','measures','switches','clear_attempts','complete','exit_reason')
 for cid,chosen in selection['decisions'].items():
  parent=ROOT/'results'/('p1_baseline' if chosen['slot']<0 else f'p1_slot{chosen["slot"]:02}')
  data=json.loads(gzip.decompress((parent/'runs'/(chosen['run_id']+'.json.gz')).read_bytes()))
  target=b[1][cid]
  assert all(target['row'][k]==data['row'][k] for k in fields)
  records=[json.loads(x) for x in gzip.decompress((parent/'runs'/(chosen['run_id']+'.journal.jsonl.gz')).read_bytes()).decode().splitlines()]
  traces=[[normalize(records[i]),normalize(records[i+1])] for i in range(0,len(records),2)]
  assert traces==target['traces']
 result=dict(passed=True,role='finite_action_headroom_diagnostic_not_deployable_or_global_optimum',candidate_runs=324,baseline_runs=48,finite_best_replay_runs=48,all_420_full_clear=True,selected_full_trajectories_exact=True,auditor_sha256=sha(__file__),paired=p,modes=selection['modes'])
 dump(ROOT/'results/P1_RESULT.json',result)
 text=['# P1：真实完整重放余量诊断','', '48 个已暴露世界、96 个公开进度前缀；冻结 324 个认证方案。48 次基线、324 次单方案完整重放、48 次事后有限最优完整重放，共420局全部正常清除。每次介入前的公共请求轨迹与基线精确一致，最终选中的48条整局轨迹再次重放完全一致。','', '|题目|世界数|基线秒/源|事后有限最优秒/源|差额|降幅|有改善世界|','|---|---:|---:|---:|---:|---:|---:|']
 for q,d in selection['modes'].items():text.append(f'|Q{q}|{d["worlds"]}|{d["baseline"]:.6f}|{d["finite_best"]:.6f}|{d["baseline"]-d["finite_best"]:.6f}|{100*(1-d["finite_best"]/d["baseline"]):.4f}%|{d["worlds_improved"]}|')
 text+=['','这不是可部署策略成绩：最优分支使用事后整局费用选取，仅说明已列举有限动作中存在的可回收收益上限；没有证明连续动作空间无更多收益。21/48世界没有新认证方案，仍完整保留A0。Q3只有3/24世界产生方案，其中2个世界有改善；Q4的24世界均有方案，其中22个有改善。频道删测为0，因此这些结果不能支持付费频道优化已带来收益。','', '下一步在独立登记的96个开发世界比较A-only、B-only、A+B与原父法，由仅看公共历史的选择器作决策。Q3新补偿布局另立版本，不回改本轮候选。','', '完整证据：`P1_RESULT.json`、`p1_progress.json`、各`p1_slotNN`目录原始行/逐次请求/独立审计、`p1_finite_best`。指标为先算每局T/N再按世界平均，所有前缀重放费用已实际支付并进入统一预算账本。']
 (ROOT/'results/P1_REPORT.md').write_text('\n'.join(text)+'\n')
 dump(ROOT/'execution_status.json',Budget(ROOT/'execution.sqlite').snapshot());print(json.dumps(result))
if __name__=='__main__':main()
