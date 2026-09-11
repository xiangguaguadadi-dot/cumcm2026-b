# E2 迭代路径与状态

四轮已在本次方法范围内收束。固定父候选S1，当前单独最佳r3_failure_cells；主收益组件r1_station_only、r2_one_round。

- r1_off: parent=S1; rejected_development_quick
- r1_cost_opportunity: parent=S1; rejected_development_quick
- r1_cost_all: parent=S1; full_dominated_by_r1_station_only
- r1_station_only: parent=S1; accepted_R1_major_component
- r1_station_uncertified: parent=S1; simpler_control_inferior
- r2_here: parent=r1_station_only; rejected_development_quick
- r2_one_round: parent=r1_station_only; accepted_R2_major_component
- r3_failure_hull: parent=r2_one_round; rejected_development_quick
- r3_failure_cells: parent=r2_one_round; accepted_R3_small_component
- r4_optical_1: parent=r2_one_round; bounded_development_only_tiny_gain
- r4_optical_3: parent=r2_one_round; bounded_development_only_tiny_gain

完整数值、局限与停止理由见[报告](report.md)。R4仅开发+quick；没有冒称full。
