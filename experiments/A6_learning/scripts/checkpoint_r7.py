"""Preserve the already selected R7 candidate and local file provenance."""
import datetime, hashlib, json
from pathlib import Path

B=Path(__file__).resolve().parents[1]
R=B.parents[1]
paths=[B/'training/r7/budget.json',B/'training/r7/selected.json',
       B/'snapshots/r7_training_architecture.py',B/'snapshots/r7_solver.py']
entries=[]
for p in paths:
    stat=p.stat()
    entries.append(dict(path=str(p.relative_to(R)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        modified_utc=datetime.datetime.fromtimestamp(stat.st_mtime,datetime.timezone.utc).isoformat(),
        created_utc=datetime.datetime.fromtimestamp(stat.st_birthtime,datetime.timezone.utc).isoformat()))
result=dict(recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=entries,
    scope='R7 architecture, training and development selection completed before accidental access to shared campaign status. After access, selected.json and training architecture were only read; the selected candidate was frozen and evaluated without parameter changes.',
    timestamp_limit='Filesystem times are local provenance evidence, not an independent trusted timestamp.',
    next_step='No R8 design in this context. Continue from own-route-only checkpoint in a clean context as coordinated by root.')
(B/'r7_provenance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
log=B/'iteration_log.md'
with log.open('a') as f:
    f.write('''

### 第7轮结果：刷新最佳

- 训练/开发共6336局，开发均值534.7874814166242，相对输入539.4368914509976改善0.8619%，超过预先0.5%门槛；selected.json与训练架构在本轮恢复前已完成。
- 候选SHA256：`7603ac0512b834d85ac499c1c5ce9da454d7f1f64bd8d368c5fe96b30d0b3138`。
- 规则、79/79 nominal、冻结散列及受保护函数AST审查通过；quick120、full2400全部清除且正常退出，无异常。
- quick Q4 577.277668198秒/源，仍比原基准572.490925060更慢；full Q3 306.30043421816345、Q4 548.5156891280411秒/源，现实25.39秒。
- full相对R5 Q4进一步改善约0.0572%，相对原版改善约3.9181%；Q3保持原版。刷新最佳为R7，连续未刷新计数重置0，不能按“第7轮”自行停止。
- 独立性记录：训练和开发选择完成后，整理状态时意外读到共享协调记录中的其他路线摘要。本轮随后只执行预先已选候选的冻结和验证，没有调整参数或设计新动作。`r7_provenance.json`保存文件时间与散列；文件时间不是独立可信时间戳。主协调已要求后续用仅本路线检查点的干净上下文接续；本上下文不设计R8。这是调度暂停，不是研究完成。
''')
print(json.dumps(result,ensure_ascii=False,indent=2))
