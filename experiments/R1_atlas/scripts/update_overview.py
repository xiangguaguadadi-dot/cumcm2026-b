"""Refresh only the human navigation from the existing validated graph."""
import json
from pathlib import Path


def update_overview(out, graph):
    nodes = graph['nodes']
    kinds = graph['coverage_audit']['kind_counts']
    full = kinds['completed_optimization_round'] + kinds['completed_stage3_round']
    assert len(nodes) == 70 and full == 57
    path = out / 'DIRECTION_MAP.md'
    text = path.read_text()
    intro = (
        f'截至2026-09-11，当前图谱共{len(nodes)}节点、{full}个完整回归轮次：'
        '六路线43轮＋第二阶段5轮＋第三阶段9轮。其余为1个开发止步、'
        '1个历史几何开发、1个本阶段几何诊断、3个未实施方向、6个背景与1个取消节点。'
        '全部数字为本地结果。第三阶段两条路线已完成研究，保留Q3 R2 R4与Q4 R3 R5。'
        '\n\n完整交付见[FINAL_REPORT.md](FINAL_REPORT.md)，第三阶段逐轮变化、失败与预算见'
        '[STAGE3_PROGRESS.md](STAGE3_PROGRESS.md)；本页下半部保留48轮历史详情。'
    )
    intro_start = text.index('\n\n') + 2
    intro_end = text.index('S0按题选', intro_start)
    text = text[:intro_start] + intro + '\n\n' + text[intro_end:]
    overview = '''## 总览

```mermaid
flowchart TB
  R0["R0 冻结基准"]
  R0 --> STAGE1["第一阶段：6路线 / 43轮<br/>空间、信息、协同、定向、两条学习路线"]
  STAGE1 --> C0["C0：仅取Q3 A1 R8 / Q4 A4 R6"]
  C0 --> STAGE2["第二阶段：B1、B2、B3 / 5轮<br/>协同门控、光学分区、连续覆盖"]
  STAGE2 --> S0["S0：仅取Q3 B1 R1 / Q4 B3 R1"]
  S0 --> R2_open_R4["第三阶段 Q3：R2开放研究<br/>4个完整回归轮 / 最终保留R4"]
  S0 --> R3_open_R5["第三阶段 Q4：R3开放研究<br/>5个完整回归轮 / 最终保留R5"]
  R2_open_R4 -. "迁移冻结圆弧组件" .-> R3_open_R5
  R2_open_R4 --> R2_open_R5["R2 R5：开发止步<br/>三版3456执行，未进完整回归"]
  R2_open_R5 -. "未胜父法，保留R4" .-> R2_open_R4
```

第一、二阶段方框聚合研究方向；C0与S0只采用框中标明的组件。第三阶段框聚合各自迭代链，真实逐轮设计父、融合和回退边见[第三阶段详细图](STAGE3_PROGRESS.md)及[nodes索引](exploration_index.json)。开发止步不计入57个完整回归轮次；两个最终保留框表示独立组件，统一入口与新最终验证由协调者另行登记。

'''
    start = text.index('## 总览\n')
    end = text.index('## 如何读数\n', start)
    text = text[:start] + overview + text[end:]
    text = text.replace('## 覆盖审计\n', '## 历史覆盖审计\n')
    path.write_text(text)
    return {'nodes': len(nodes), 'full_rounds': full, 'changed': str(path), 'graph_data_modified': False}


if __name__ == '__main__':
    folder = Path(__file__).resolve().parents[1]
    print(update_overview(folder, json.loads((folder / 'exploration_graph.json').read_text())))
