# 复现命令

在代码仓库根目录执行，使用Python 3.10或更新版本。`-S` 排除本机site启动钩子。每次主运行的 `--out` 必须指向新目录。

```sh
/opt/homebrew/bin/python3.12 -S agent_experiments/20260913_fulltask_geometry_ablations/safe_action/run_ablation.py \
  --out agent_experiments/20260913_fulltask_geometry_ablations/safe_action/reproduction_full_new

/opt/homebrew/bin/python3.12 -S agent_experiments/20260913_fulltask_geometry_ablations/safe_action/validate_outputs.py
```

`audit_geometry_execution.py` 的封存输出已存在于 `full_1200/`，脚本为防覆盖会拒绝再写同名文件。若要重做顶点级审计，先复制脚本并把它的输出目录改为新目录，不覆盖封存产物。

