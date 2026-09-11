# G2检查点选择结果

本报告只分析已保存的选择评估记录。先逐题检查全部96个注册world的身份、清除、异常和费用一致性，再在每个初始化的合格检查点中选择平均秒/源最小者。

这是检查点选择后的本地证据，存在选择偏差，置信区间未校正选择和多重比较。它不是新的盲测、旧暴露回归的独立复验或官方Windows验证，也不授权默认替换C7。

## 分题结论

| 算法 | 题目 | 满足选择门槛 | 同时优于C7与本初始化BC的初始化数 | 相对C7改善 | 相对BC改善 |
|---|---:|---|---:|---:|---:|
| PPO | 3 | 否 | 0/3 | -3.836% | -0.787% |
| PPO | 4 | 否 | 0/3 | -5.569% | 1.010% |
| Q | 3 | 否 | 0/3 | -3.488% | -0.449% |
| Q | 4 | 否 | 0/3 | -6.478% | 0.158% |

晋级需三个初始化均有完整可配对的选择；按同一world先平均三个初始化，再分别相对C7和对应BC检验：平均改善至少2%、配对差值95%区间上界严格小于0，并且至少两个相同初始化同时优于两种对照。未满足的题保留C7。

## 每个初始化的选择与配对比较

差值为候选减对照，负值表示更快；相对改善为`100×(对照均值−候选均值)/对照均值`。下表区间按12场景分层、world配对、10000次bootstrap，随机种子84771。精确并列时保留较早预登记检查点。

| 算法 | 题目 | 初始化 | 选择训练局数 | 候选秒/源 | 对照 | 改善% | 差值95%区间（秒/源） |
|---|---:|---:|---:|---:|---|---:|---|
| PPO | 3 | 81001 | 256 | 241.541 | original_c7 | -2.379 | [2.798, 8.517] |
| PPO | 3 | 81001 | 256 | 241.541 | corresponding_bc | 0.724 | [-4.611, 1.100] |
| PPO | 3 | 81002 | 128 | 244.802 | original_c7 | -3.762 | [6.046, 11.695] |
| PPO | 3 | 81002 | 128 | 244.802 | corresponding_bc | -0.706 | [-1.880, 5.233] |
| PPO | 3 | 81003 | 256 | 248.590 | original_c7 | -5.367 | [9.078, 16.081] |
| PPO | 3 | 81003 | 256 | 248.590 | corresponding_bc | -2.381 | [2.086, 9.378] |
| PPO | 4 | 81001 | 512 | 463.484 | original_c7 | -5.364 | [17.597, 29.656] |
| PPO | 4 | 81001 | 512 | 463.484 | corresponding_bc | 1.532 | [-13.086, -1.203] |
| PPO | 4 | 81002 | 256 | 460.600 | original_c7 | -4.708 | [14.158, 27.521] |
| PPO | 4 | 81002 | 256 | 460.600 | corresponding_bc | 1.829 | [-14.307, -2.955] |
| PPO | 4 | 81003 | 256 | 469.083 | original_c7 | -6.636 | [23.895, 34.790] |
| PPO | 4 | 81003 | 256 | 469.083 | corresponding_bc | -0.338 | [-5.847, 8.775] |
| Q | 3 | 81001 | 128 | 243.403 | original_c7 | -3.169 | [4.775, 10.308] |
| Q | 3 | 81001 | 128 | 243.403 | corresponding_bc | -0.041 | [-2.974, 3.207] |
| Q | 3 | 81002 | 128 | 243.798 | original_c7 | -3.336 | [4.873, 10.864] |
| Q | 3 | 81002 | 128 | 243.798 | corresponding_bc | -0.293 | [-2.160, 3.562] |
| Q | 3 | 81003 | 512 | 245.269 | original_c7 | -3.960 | [5.944, 12.777] |
| Q | 3 | 81003 | 512 | 245.269 | corresponding_bc | -1.013 | [-1.326, 6.200] |
| Q | 4 | 81001 | 1024 | 468.889 | original_c7 | -6.592 | [21.689, 36.230] |
| Q | 4 | 81001 | 1024 | 468.889 | corresponding_bc | 0.383 | [-8.636, 4.924] |
| Q | 4 | 81002 | 128 | 469.954 | original_c7 | -6.835 | [23.659, 36.575] |
| Q | 4 | 81002 | 128 | 469.954 | corresponding_bc | -0.165 | [-5.599, 7.135] |
| Q | 4 | 81003 | 512 | 466.313 | original_c7 | -6.007 | [19.909, 32.833] |
| Q | 4 | 81003 | 512 | 466.313 | corresponding_bc | 0.255 | [-8.363, 6.092] |

## 三个初始化按world合并后的区间

每题只有96个独立world单位；同一world的三个初始化先求平均，不把288次策略执行当作288个独立world。

| 算法 | 题目 | 对照 | 候选均值 | 对照均值 | 配对差值均值 | 差值95%区间 | 候选更慢world数 |
|---|---:|---|---:|---:|---:|---|---:|
| PPO | 3 | original_c7 | 244.977 | 235.927 | 9.050 | [6.645, 11.360] | 78/96 |
| PPO | 3 | corresponding_bc | 244.977 | 243.066 | 1.912 | [-0.376, 4.086] | 52/96 |
| PPO | 4 | original_c7 | 464.389 | 439.890 | 24.499 | [19.906, 29.434] | 81/96 |
| PPO | 4 | corresponding_bc | 464.389 | 469.126 | -4.737 | [-8.895, -0.635] | 39/96 |
| Q | 3 | original_c7 | 244.157 | 235.927 | 8.230 | [5.857, 10.632] | 75/96 |
| Q | 3 | corresponding_bc | 244.157 | 243.066 | 1.091 | [-0.885, 3.053] | 57/96 |
| Q | 4 | original_c7 | 468.386 | 439.890 | 28.496 | [23.145, 33.828] | 84/96 |
| Q | 4 | corresponding_bc | 468.386 | 469.126 | -0.741 | [-4.962, 3.353] | 51/96 |

## 全部预登记位置

下表保留6个对照位置和24个模型检查点，每题分别显示。失败、缺失和未执行的检查点不参加该题选择，也不从报告中删除；不对成功子集给出耗时排名。

| 位置 | 题目 | 状态 | 已记录/应记录 | 正常全清world | 失败行 | 无效行 | 重复ID | 缺失ID | 均值秒/源 |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| original_c7 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 235.927 |
| original_c7 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 439.890 |
| teacher_wrapper | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 235.927 |
| teacher_wrapper | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 439.890 |
| same_candidates_greedy | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 242.550 |
| same_candidates_greedy | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 479.329 |
| bc_init81001 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 243.302 |
| bc_init81001 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 470.693 |
| bc_init81002 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 243.085 |
| bc_init81002 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 469.182 |
| bc_init81003 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 242.809 |
| bc_init81003 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 467.504 |
| ppo_init81001_ep0128 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 244.943 |
| ppo_init81001_ep0128 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 471.999 |
| ppo_init81001_ep0256 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 241.541 |
| ppo_init81001_ep0256 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 469.522 |
| ppo_init81001_ep0512 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 247.816 |
| ppo_init81001_ep0512 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 463.484 |
| ppo_init81001_ep1024 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 247.556 |
| ppo_init81001_ep1024 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 484.295 |
| ppo_init81002_ep0128 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 244.802 |
| ppo_init81002_ep0128 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 461.928 |
| ppo_init81002_ep0256 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 247.309 |
| ppo_init81002_ep0256 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 460.600 |
| ppo_init81002_ep0512 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 247.110 |
| ppo_init81002_ep0512 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 482.130 |
| ppo_init81002_ep1024 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 256.748 |
| ppo_init81002_ep1024 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 493.495 |
| ppo_init81003_ep0128 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 258.852 |
| ppo_init81003_ep0128 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 484.404 |
| ppo_init81003_ep0256 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 248.590 |
| ppo_init81003_ep0256 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 469.083 |
| ppo_init81003_ep0512 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 251.294 |
| ppo_init81003_ep0512 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 483.849 |
| ppo_init81003_ep1024 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 261.988 |
| ppo_init81003_ep1024 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 497.511 |
| q_init81001_ep0128 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 243.403 |
| q_init81001_ep0128 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 479.240 |
| q_init81001_ep0256 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 246.359 |
| q_init81001_ep0256 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 472.333 |
| q_init81001_ep0512 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 246.957 |
| q_init81001_ep0512 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 475.579 |
| q_init81001_ep1024 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 245.663 |
| q_init81001_ep1024 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 468.889 |
| q_init81002_ep0128 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 243.798 |
| q_init81002_ep0128 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 469.954 |
| q_init81002_ep0256 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 246.512 |
| q_init81002_ep0256 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 475.555 |
| q_init81002_ep0512 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 247.728 |
| q_init81002_ep0512 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 486.560 |
| q_init81002_ep1024 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 251.809 |
| q_init81002_ep1024 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 470.232 |
| q_init81003_ep0128 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 245.475 |
| q_init81003_ep0128 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 468.497 |
| q_init81003_ep0256 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 246.474 |
| q_init81003_ep0256 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 466.781 |
| q_init81003_ep0512 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 245.269 |
| q_init81003_ep0512 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 466.313 |
| q_init81003_ep1024 | 3 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 247.966 |
| q_init81003_ep1024 | 4 | 完整全清 | 96/96 | 96 | 0 | 0 | 0 | 0 | 476.157 |

## 分场景配对结果

同时报告场景均值退步及单world退步。表中先按world平均三个初始化；若三初始化条件不满足，则该算法该题没有合并结果。

| 算法 | 题目 | 对照 | 场景 | world数 | 候选秒/源 | 对照秒/源 | 改善% | 候选更慢world数 |
|---|---:|---|---|---:|---:|---:|---:|---:|
| PPO | 3 | original_c7 | cell500_shared_field | 8 | 260.768 | 249.551 | -4.495 | 6 |
| PPO | 3 | original_c7 | cell50_shared_field | 8 | 250.625 | 237.802 | -5.393 | 8 |
| PPO | 3 | original_c7 | edge_mixed_min_radius | 8 | 287.329 | 282.937 | -1.552 | 6 |
| PPO | 3 | original_c7 | exactly10_sources | 8 | 298.979 | 284.645 | -5.036 | 7 |
| PPO | 3 | original_c7 | exactly16_sources | 8 | 215.668 | 202.122 | -6.702 | 7 |
| PPO | 3 | original_c7 | fixed_negative_bias | 8 | 234.064 | 223.037 | -4.944 | 7 |
| PPO | 3 | original_c7 | fixed_positive_bias | 8 | 265.088 | 255.205 | -3.873 | 7 |
| PPO | 3 | original_c7 | minimum_radius | 8 | 275.193 | 268.110 | -2.642 | 6 |
| PPO | 3 | original_c7 | offcenter_cluster | 8 | 192.987 | 189.915 | -1.618 | 6 |
| PPO | 3 | original_c7 | origin_cluster | 8 | 168.254 | 166.529 | -1.036 | 6 |
| PPO | 3 | original_c7 | reference_assumed | 8 | 225.938 | 213.202 | -5.974 | 7 |
| PPO | 3 | original_c7 | smooth_shared_field | 8 | 264.836 | 258.069 | -2.622 | 5 |
| PPO | 3 | corresponding_bc | cell500_shared_field | 8 | 260.768 | 263.876 | 1.178 | 2 |
| PPO | 3 | corresponding_bc | cell50_shared_field | 8 | 250.625 | 253.636 | 1.187 | 4 |
| PPO | 3 | corresponding_bc | edge_mixed_min_radius | 8 | 287.329 | 283.527 | -1.341 | 5 |
| PPO | 3 | corresponding_bc | exactly10_sources | 8 | 298.979 | 294.009 | -1.690 | 5 |
| PPO | 3 | corresponding_bc | exactly16_sources | 8 | 215.668 | 213.657 | -0.941 | 3 |
| PPO | 3 | corresponding_bc | fixed_negative_bias | 8 | 234.064 | 231.317 | -1.188 | 4 |
| PPO | 3 | corresponding_bc | fixed_positive_bias | 8 | 265.088 | 258.193 | -2.670 | 6 |
| PPO | 3 | corresponding_bc | minimum_radius | 8 | 275.193 | 276.039 | 0.307 | 5 |
| PPO | 3 | corresponding_bc | offcenter_cluster | 8 | 192.987 | 191.748 | -0.646 | 6 |
| PPO | 3 | corresponding_bc | origin_cluster | 8 | 168.254 | 166.841 | -0.847 | 5 |
| PPO | 3 | corresponding_bc | reference_assumed | 8 | 225.938 | 224.544 | -0.621 | 3 |
| PPO | 3 | corresponding_bc | smooth_shared_field | 8 | 264.836 | 259.400 | -2.096 | 4 |
| PPO | 4 | original_c7 | cell500_shared_field | 8 | 446.429 | 427.854 | -4.342 | 8 |
| PPO | 4 | original_c7 | cell50_shared_field | 8 | 458.129 | 428.605 | -6.888 | 8 |
| PPO | 4 | original_c7 | edge_mixed_min_radius | 8 | 550.890 | 512.543 | -7.482 | 7 |
| PPO | 4 | original_c7 | exactly10_sources | 8 | 639.580 | 603.663 | -5.950 | 8 |
| PPO | 4 | original_c7 | exactly16_sources | 8 | 334.382 | 307.695 | -8.673 | 6 |
| PPO | 4 | original_c7 | fixed_negative_bias | 8 | 467.065 | 448.470 | -4.146 | 7 |
| PPO | 4 | original_c7 | fixed_positive_bias | 8 | 456.153 | 438.013 | -4.141 | 6 |
| PPO | 4 | original_c7 | minimum_radius | 8 | 395.803 | 378.692 | -4.518 | 5 |
| PPO | 4 | original_c7 | offcenter_cluster | 8 | 472.623 | 461.761 | -2.352 | 5 |
| PPO | 4 | original_c7 | origin_cluster | 8 | 416.662 | 393.344 | -5.928 | 6 |
| PPO | 4 | original_c7 | reference_assumed | 8 | 439.270 | 411.039 | -6.868 | 7 |
| PPO | 4 | original_c7 | smooth_shared_field | 8 | 495.681 | 467.001 | -6.141 | 8 |
| PPO | 4 | corresponding_bc | cell500_shared_field | 8 | 446.429 | 463.202 | 3.621 | 1 |
| PPO | 4 | corresponding_bc | cell50_shared_field | 8 | 458.129 | 472.506 | 3.043 | 1 |
| PPO | 4 | corresponding_bc | edge_mixed_min_radius | 8 | 550.890 | 559.578 | 1.553 | 3 |
| PPO | 4 | corresponding_bc | exactly10_sources | 8 | 639.580 | 646.001 | 0.994 | 3 |
| PPO | 4 | corresponding_bc | exactly16_sources | 8 | 334.382 | 341.352 | 2.042 | 4 |
| PPO | 4 | corresponding_bc | fixed_negative_bias | 8 | 467.065 | 459.228 | -1.707 | 4 |
| PPO | 4 | corresponding_bc | fixed_positive_bias | 8 | 456.153 | 468.663 | 2.669 | 3 |
| PPO | 4 | corresponding_bc | minimum_radius | 8 | 395.803 | 401.990 | 1.539 | 4 |
| PPO | 4 | corresponding_bc | offcenter_cluster | 8 | 472.623 | 484.641 | 2.480 | 2 |
| PPO | 4 | corresponding_bc | origin_cluster | 8 | 416.662 | 388.499 | -7.249 | 8 |
| PPO | 4 | corresponding_bc | reference_assumed | 8 | 439.270 | 448.027 | 1.955 | 2 |
| PPO | 4 | corresponding_bc | smooth_shared_field | 8 | 495.681 | 495.826 | 0.029 | 4 |
| Q | 3 | original_c7 | cell500_shared_field | 8 | 257.490 | 249.551 | -3.181 | 5 |
| Q | 3 | original_c7 | cell50_shared_field | 8 | 251.385 | 237.802 | -5.712 | 7 |
| Q | 3 | original_c7 | edge_mixed_min_radius | 8 | 292.141 | 282.937 | -3.253 | 6 |
| Q | 3 | original_c7 | exactly10_sources | 8 | 296.417 | 284.645 | -4.135 | 5 |
| Q | 3 | original_c7 | exactly16_sources | 8 | 211.064 | 202.122 | -4.424 | 7 |
| Q | 3 | original_c7 | fixed_negative_bias | 8 | 230.209 | 223.037 | -3.216 | 7 |
| Q | 3 | original_c7 | fixed_positive_bias | 8 | 263.329 | 255.205 | -3.183 | 7 |
| Q | 3 | original_c7 | minimum_radius | 8 | 280.572 | 268.110 | -4.648 | 7 |
| Q | 3 | original_c7 | offcenter_cluster | 8 | 192.843 | 189.915 | -1.542 | 5 |
| Q | 3 | original_c7 | origin_cluster | 8 | 168.173 | 166.529 | -0.987 | 6 |
| Q | 3 | original_c7 | reference_assumed | 8 | 220.806 | 213.202 | -3.566 | 7 |
| Q | 3 | original_c7 | smooth_shared_field | 8 | 265.457 | 258.069 | -2.863 | 6 |
| Q | 3 | corresponding_bc | cell500_shared_field | 8 | 257.490 | 263.876 | 2.420 | 3 |
| Q | 3 | corresponding_bc | cell50_shared_field | 8 | 251.385 | 253.636 | 0.888 | 4 |
| Q | 3 | corresponding_bc | edge_mixed_min_radius | 8 | 292.141 | 283.527 | -3.038 | 7 |
| Q | 3 | corresponding_bc | exactly10_sources | 8 | 296.417 | 294.009 | -0.819 | 4 |
| Q | 3 | corresponding_bc | exactly16_sources | 8 | 211.064 | 213.657 | 1.214 | 5 |
| Q | 3 | corresponding_bc | fixed_negative_bias | 8 | 230.209 | 231.317 | 0.479 | 4 |
| Q | 3 | corresponding_bc | fixed_positive_bias | 8 | 263.329 | 258.193 | -1.989 | 5 |
| Q | 3 | corresponding_bc | minimum_radius | 8 | 280.572 | 276.039 | -1.642 | 6 |
| Q | 3 | corresponding_bc | offcenter_cluster | 8 | 192.843 | 191.748 | -0.571 | 6 |
| Q | 3 | corresponding_bc | origin_cluster | 8 | 168.173 | 166.841 | -0.798 | 5 |
| Q | 3 | corresponding_bc | reference_assumed | 8 | 220.806 | 224.544 | 1.665 | 3 |
| Q | 3 | corresponding_bc | smooth_shared_field | 8 | 265.457 | 259.400 | -2.335 | 5 |
| Q | 4 | original_c7 | cell500_shared_field | 8 | 468.478 | 427.854 | -9.495 | 8 |
| Q | 4 | original_c7 | cell50_shared_field | 8 | 471.725 | 428.605 | -10.060 | 8 |
| Q | 4 | original_c7 | edge_mixed_min_radius | 8 | 557.590 | 512.543 | -8.789 | 8 |
| Q | 4 | original_c7 | exactly10_sources | 8 | 639.286 | 603.663 | -5.901 | 8 |
| Q | 4 | original_c7 | exactly16_sources | 8 | 317.658 | 307.695 | -3.238 | 6 |
| Q | 4 | original_c7 | fixed_negative_bias | 8 | 464.674 | 448.470 | -3.613 | 5 |
| Q | 4 | original_c7 | fixed_positive_bias | 8 | 469.700 | 438.013 | -7.234 | 7 |
| Q | 4 | original_c7 | minimum_radius | 8 | 407.186 | 378.692 | -7.524 | 6 |
| Q | 4 | original_c7 | offcenter_cluster | 8 | 480.639 | 461.761 | -4.088 | 7 |
| Q | 4 | original_c7 | origin_cluster | 8 | 393.515 | 393.344 | -0.044 | 5 |
| Q | 4 | original_c7 | reference_assumed | 8 | 447.246 | 411.039 | -8.809 | 8 |
| Q | 4 | original_c7 | smooth_shared_field | 8 | 502.931 | 467.001 | -7.694 | 8 |
| Q | 4 | corresponding_bc | cell500_shared_field | 8 | 468.478 | 463.202 | -1.139 | 7 |
| Q | 4 | corresponding_bc | cell50_shared_field | 8 | 471.725 | 472.506 | 0.165 | 4 |
| Q | 4 | corresponding_bc | edge_mixed_min_radius | 8 | 557.590 | 559.578 | 0.355 | 3 |
| Q | 4 | corresponding_bc | exactly10_sources | 8 | 639.286 | 646.001 | 1.039 | 2 |
| Q | 4 | corresponding_bc | exactly16_sources | 8 | 317.658 | 341.352 | 6.941 | 1 |
| Q | 4 | corresponding_bc | fixed_negative_bias | 8 | 464.674 | 459.228 | -1.186 | 5 |
| Q | 4 | corresponding_bc | fixed_positive_bias | 8 | 469.700 | 468.663 | -0.221 | 6 |
| Q | 4 | corresponding_bc | minimum_radius | 8 | 407.186 | 401.990 | -1.293 | 5 |
| Q | 4 | corresponding_bc | offcenter_cluster | 8 | 480.639 | 484.641 | 0.826 | 5 |
| Q | 4 | corresponding_bc | origin_cluster | 8 | 393.515 | 388.499 | -1.291 | 5 |
| Q | 4 | corresponding_bc | reference_assumed | 8 | 447.246 | 448.027 | 0.174 | 3 |
| Q | 4 | corresponding_bc | smooth_shared_field | 8 | 502.931 | 495.826 | -1.433 | 5 |

## 费用与可复核范围

记录中共有5760行评估执行，业务调用1119488次，逐局现实执行耗时合计1867.881秒。费用字段无效的行数为0。这里包含失败和被拒绝检查点；缺失或无法解析的记录成本未知，不记作零。上述耗时没有包含训练或文件I/O，不能用于受控机器速度排名。

完整ID、失败原因、所有输入散列、每world配对数值、全部门槛布尔值和每初始化场景结果在`selection_summary.json`。本程序不运行环境、不训练模型、不生成世界，也不产生默认替换C7的授权。
