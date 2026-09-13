# 实际执行命令

工作目录均为`/Users/t/ai project/数学建模2026/代码`。

```bash
python3 -m py_compile agent_experiments/20260913_highlights_round2/information_control/*.py

/opt/homebrew/bin/python3.12 agent_experiments/20260913_highlights_round2/information_control/run_ablation.py --candidate agent_experiments/20260913_highlights_round2/information_control/gate_off.py --suite quick --out agent_experiments/20260913_highlights_round2/information_control/quick_gate_off

/opt/homebrew/bin/python3.12 agent_experiments/20260913_highlights_round2/information_control/run_ablation.py --candidate agent_experiments/20260913_highlights_round2/information_control/replan_off.py --suite quick --out agent_experiments/20260913_highlights_round2/information_control/quick_replan_off

PYTHONNOUSERSITE=1 /opt/homebrew/bin/python3.12 -S agent_experiments/20260913_highlights_round2/information_control/run_ablation.py --candidate agent_experiments/20260913_highlights_round2/information_control/gate_off.py --suite full --out agent_experiments/20260913_highlights_round2/information_control/full_gate_off

PYTHONNOUSERSITE=1 /opt/homebrew/bin/python3.12 -S agent_experiments/20260913_highlights_round2/information_control/run_ablation.py --candidate agent_experiments/20260913_highlights_round2/information_control/replan_off.py --suite full --out agent_experiments/20260913_highlights_round2/information_control/full_replan_off

PYTHONNOUSERSITE=1 /opt/homebrew/bin/python3.12 -S agent_experiments/20260913_highlights_round2/information_control/finalize.py
```

最初两次quick未使用`-S`，本机残留的第三方`hostile.pth`在启动时尝试写一个已删除的pytest临时路径，产生非致命stderr；解释器忽略该pth后两次quick均完成且60/60全清。full与最终汇总使用`-S`隔离用户site-packages，无该启动噪声。
