# 最终种子源码独立复核

结论：给定冻结清单中的 10466 个具体种子必须全部保留为排除项；仅排除 `[0, 100000000)` 不够。建议额外排除两个完整百万区间 `[721000000, 722000000)`、`[731000000, 732000000)`。本审计没有生成案例、抽取随机数、导入任务代码或运行策略。

清单：`/Users/t/Documents/Codex/2026-09-10/new-chat/work/stage3/coordinator/experiments/20260911_stage3/audit/seed_inventory_final/inventory.json`，SHA256 `1c0c03bdad7cb9167147d9564932150e976dd6198d6def441795263d66545c05`。它包含3279文件、1421种内容、10466个抽取值，扫描错误0。审计覆盖89份有seed文本的不同Python源码，补充6份仅有Random字面量的几何/路线源码，再补1份默认seed=0规则测试。全部265份不同Python内容做了静态补查，其余169份未发现额外随机/环境种子调用或高段整数。已逐一核验96份源码及其全部别名；94份与清单SHA一致，2份协调期间发生明确记录的不新增种子修订（final_review.py与build_graph.py），旧/新SHA及静态调用证据均在JSON保留。主协调会在审查提交后刷新清单。

## 高段773个值全部有来源

| 来源 | 不同种子 | 已核验事实 |
|---|---:|---|
| 第一阶段旧final |100|manifest与2400案例一致，每种子24案例，全部已在排除清单|
| B2 R2开发 |336|721400000–721406507，逐场景/误差/槽位公式完全匹配|
| B2 R3开发 |336|731400000–731406507，逐场景/误差/槽位公式完全匹配|
| B2残差几何检查 |1|Random(998211234)，仅几何；仍保守排除|

四类并集与清单中全部773个≥1亿的种子精确相等，未解释的高段种子0、公式漏项0。旧final生成器的潜在域是`[1亿, 2**31)`，应排除已实际保存的100次抽取，不能把整个潜在域视为全部暴露。

## B2公式核验

`seed = start + mode*100000 + i*1000 + j*100 + k`。源码固定7场景、6误差，保存数据每槽8种子且mode=4。由保存案例重建的start分别为92100000、721000000、731000000；这是公式反推的调用参数，不冒称命令日志。每轮336个完整(种子,题号,场景,误差)元组均与公式相同，episodes文件种子集合也相同。R1全部低于1亿；R2/R3所建议百万区间是主动扩大排除，区间空隙并不代表曾实际运行。

## 未运行生成器与证据边界

第二阶段与本阶段的最终生成器源码均抽取高段种子。协调记录说明第二阶段最终验证已取消，本阶段尚未启动；冻结清单也没有这两阶段的final_validation案例/manifest。仅凭文件不存在不能证明过去某个进程从未抽取未保存的整数，因此这个状态明确依赖协调记录。此次审计不运行生成器、不读取新final、不修改已冻结策略。

任意CLI脚本理论上可以被未保存命令传入其他范围；静态源码与现存记录不能证明不存在被删除或未保存的运行。此处结论限于完整保留的清单与已记录公式，不作无限范围证明。几何RNG、优化器RNG和bootstrap RNG即使不是任务种子，也保守排除。

## 逐源码复核索引

完整源码行证据、SHA256、别名数、分类及种子公式均在同名JSON中。下表的编号1–89与原始抽取列表完全对应，90–95是额外字面量来源，96是默认环境规则测试。

| ID | 分类 | 源码 | 公式/状态 |
|---:|---|---|---|
| 1 | existing_case_runner | `coordinator/evaluate.py` | Uses case[seed] from saved frozen cases. |
| 2 | fixed_case_generator | `evaluation/generate_cases.py` | range(5000,5100); sources(seed,mode,scenario). |
| 3 | saved_evidence_audit | `20260911_agent_campaign/audit/delivery_independent_audit.py` | Inspects seed fields/identifiers in saved data or source AST. |
| 4 | saved_bootstrap_audit | `20260911_agent_campaign/audit/final_delivery_review.py` | random.Random(110926) draws bootstrap indices from saved clusters. |
| 5 | saved_evidence_audit | `20260911_agent_campaign/audit_final_results.py` | Inspects seed fields/identifiers in saved data or source AST. |
| 6 | saved_report_or_finalization | `20260911_agent_campaign/build_campaign_report.py` | Copies or summarizes recorded seeds; no new seed draw. |
| 7 | historical_system_random_generator | `20260911_agent_campaign/final_review.py` | SystemRandom().sample(range(10**8,2**31),args.seeds), default 100. |
| 8 | saved_evidence_audit | `20260911_breakthrough/audit/audit_exposed_results.py` | Inspects seed fields/identifiers in saved data or source AST. |
| 9 | existing_case_runner | `20260911_breakthrough/evaluate_exposed.py` | Uses case[seed] from saved frozen cases. |
| 10 | unused_later_final_generator | `20260911_breakthrough/generate_final.py` | SystemRandom().randrange(10**8,2**31) until requested distinct seeds outside exclusion. |
| 11 | saved_evidence_audit | `20260911_stage3/audit/audit_exposed_results.py` | Inspects seed fields/identifiers in saved data or source AST. |
| 12 | existing_case_pipeline_check | `20260911_stage3/audit/check_final_review.py` | Reuses first v1 seed (5000) for 24 smoke tasks; synthetic paired row arithmetic. |
| 13 | inventory_scanner | `20260911_stage3/audit/collect_seed_inventory.py` | Parses recorded seed fields and Python expressions as data. |
| 14 | existing_case_runner | `20260911_stage3/evaluate_exposed.py` | Uses case[seed] from saved frozen cases. |
| 15 | existing_case_runner_and_bootstrap | `20260911_stage3/final_review.py` | Accepts cases file; analysis RNG random.Random(110926) samples cluster indices. |
| 16 | not_yet_run_final_generator | `20260911_stage3/generate_final.py` | SystemRandom().randrange(10**8,2**31), rejects exact seeds and half-open ranges. |
| 17 | task_case_generator | `B1/research/develop.py` | train start=3101000; development start=3102000; range(start,start+6). |
| 18 | existing_case_replay | `B1/research/freeze_r1.py` | Selects saved B1 train case seed==3101000. |
| 19 | saved_report_or_finalization | `B1/research/report_r1.py` | Copies or summarizes recorded seeds; no new seed draw. |
| 20 | task_case_generator_high_offsets | `B2/develop.py` | a.start+mode*100000+i*1000+j*100+k; 7 scenes,6 noises,k in range(a.seeds), default8. |
| 21 | saved_evidence_audit | `B2/research/audit_prior.py` | Inspects seed fields/identifiers in saved data or source AST. |
| 22 | task_case_generator_cli | `B3/development/evaluate_dev.py` | range(a.start,a.start+a.seeds); defaults start33001000,seeds12. |
| 23 | saved_report_or_finalization | `R1_atlas/scripts/build_graph.py` | Copies or summarizes recorded seeds; no new seed draw. |
| 24 | geometry_rng | `R2_open/research/audit_r1.py` | random.Random(42000999); 2000 synthetic geometric regions. |
| 25 | geometry_rng | `R2_open/research/check_r4_geometry.py` | random.Random(42001999); 1000 synthetic action regions. |
| 26 | deterministic_geometry_check | `R2_open/research/check_r5_cache.py` | No RNG and no task source generation. |
| 27 | deterministic_geometry_check | `R2_open/research/check_r5_graph.py` | No RNG and no task source generation. |
| 28 | task_case_generator_cli | `R2_open/research/develop.py` | range(a.start,a.start+a.seeds); defaults42000000 and8. |
| 29 | saved_report_or_finalization | `R2_open/research/finalize_study.py` | Copies or summarizes recorded seeds; no new seed draw. |
| 30 | saved_report_or_finalization | `R2_open/research/finish_round.py` | Copies or summarizes recorded seeds; no new seed draw. |
| 31 | inventory_scanner | `R2_open/research/read_corpus.py` | Parses recorded seed fields and Python expressions as data. |
| 32 | preregistration_writer | `R2_open/research/setup_r2.py` | Writes planned seed endpoints to experiment metadata. |
| 33 | preregistration_writer | `R2_open/research/setup_r3.py` | Writes planned seed endpoints to experiment metadata. |
| 34 | preregistration_writer | `R2_open/research/setup_r4.py` | Writes planned seed endpoints to experiment metadata. |
| 35 | preregistration_writer | `R2_open/research/setup_r5.py` | Writes planned seed endpoints to experiment metadata. |
| 36 | saved_evidence_audit | `R3_open/research/audit_r1.py` | Inspects seed fields/identifiers in saved data or source AST. |
| 37 | saved_evidence_audit | `R3_open/research/audit_r2.py` | Inspects seed fields/identifiers in saved data or source AST. |
| 38 | saved_evidence_audit | `R3_open/research/audit_r3.py` | Inspects seed fields/identifiers in saved data or source AST. |
| 39 | saved_evidence_audit | `R3_open/research/audit_r4.py` | Inspects seed fields/identifiers in saved data or source AST. |
| 40 | saved_evidence_audit | `R3_open/research/audit_r5.py` | Inspects seed fields/identifiers in saved data or source AST. |
| 41 | preregistration_writer | `R3_open/research/build_r3.py` | Writes planned seed endpoints to experiment metadata. |
| 42 | preregistration_writer | `R3_open/research/build_r4.py` | Writes planned seed endpoints to experiment metadata. |
| 43 | preregistration_writer | `R3_open/research/build_r5.py` | Writes planned seed endpoints to experiment metadata. |
| 44 | geometry_rng | `R3_open/research/check_lens_transfer.py` | random.Random(9531); 1000 synthetic lens transfer states. |
| 45 | task_case_generator | `R3_open/research/develop_r1.py` | train 43000000..43000011; development 43001000..43001011. |
| 46 | task_case_generator | `R3_open/research/develop_r2.py` | train 43002000..43002011; development 43003000..43003011. |
| 47 | task_case_generator | `R3_open/research/develop_r3.py` | train 43004000..43004011; development 43005000..43005011. |
| 48 | task_case_generator | `R3_open/research/develop_r4.py` | train 43006000..43006011; development 43007000..43007011. |
| 49 | task_case_generator | `R3_open/research/develop_r5.py` | train 43008000..43008011; development 43009000..43009011. |
| 50 | existing_case_diagnostic_replay | `R3_open/research/dynamic_coverage_probe.py` | Reads r3_development/cases.json; selects one Q4 case per group, 12 in total. |
| 51 | existing_case_diagnostic_replay | `R3_open/research/dynamic_coverage_probe_v2.py` | Reads r3_development/cases.json; selects one Q4 case per group, 12 in total. |
| 52 | existing_case_diagnostic_replay | `R3_open/research/dynamic_coverage_probe_v3.py` | Reads r3_development/cases.json; selects one Q4 case per group, 12 in total. |
| 53 | saved_report_or_finalization | `R3_open/research/finalize_stage.py` | Copies or summarizes recorded seeds; no new seed draw. |
| 54 | saved_report_or_finalization | `R3_open/research/report_r1.py` | Copies or summarizes recorded seeds; no new seed draw. |
| 55 | saved_report_or_finalization | `R3_open/research/save_iteration.py` | Copies or summarizes recorded seeds; no new seed draw. |
| 56 | caller_seed_case_factory_and_environment | `coordinator/local_env.py` | make_case(seed,...) uses Random(seed); LocalEnv default seed=0; noise hashes seed/coordinates. |
| 57 | fixed_environment_rule_check | `tests/check_nominal.py` | LocalEnv handcrafted source with keyword seed=719. |
| 58 | saved_report_or_finalization | `A1_space/build_report.py` | Copies or summarizes recorded seeds; no new seed draw. |
| 59 | geometry_and_handcrafted_environment | `A1_space/check_spatial_geometry.py` | random.Random(928631) synthetic route disks; handcrafted LocalEnv(seed=781243). |
| 60 | task_case_generator_cli | `A1_space/develop.py` | a.seed+i, i in range(a.n); defaults62000 and20. |
| 61 | geometry_rng | `A2_information/check_optical_exclusion.py` | random.Random(831148); synthetic optical exclusion polygons. |
| 62 | geometry_rng | `A2_information/check_prediction.py` | random.Random(831150); hypothetical target/prediction containment checks. |
| 63 | geometry_rng | `A2_information/check_tightening.py` | random.Random(931204); synthetic tightening checks. |
| 64 | task_case_generator_cli | `A2_information/dev_eval.py` | a.start+k, k in range(a.n); defaults910000 and10. |
| 65 | fixed_task_diagnostic_generator | `A2_information/dev_watchdog.py` | range(910300,910310). |
| 66 | task_case_generator_cli | `A3_coordination/dev_evaluate.py` | range(a.start,a.start+a.count); defaults62000 and5. |
| 67 | task_case_generator_cli | `A4_directional/develop.py` | range(a.start,a.start+a.seeds); defaults81000 and6. |
| 68 | saved_report_or_finalization | `A4_directional/finalize_report.py` | Copies or summarizes recorded seeds; no new seed draw. |
| 69 | saved_report_or_finalization | `A4_directional/summarize_results.py` | Copies or summarizes recorded seeds; no new seed draw. |
| 70 | geometry_rng | `A4_directional/validate_geometry.py` | random.Random(91004); synthetic station geometry. |
| 71 | literature_metadata_writer | `A5_learning/build_literature.py` | Mentions external-paper seeds or case function names in citation text. |
| 72 | saved_report_or_finalization | `A5_learning/build_report.py` | Copies or summarizes recorded seeds; no new seed draw. |
| 73 | training_case_generator | `A5_learning/train_policy.py` | offset=700000+round*100000+mode*10000; train offset+i; dev offset+20000+i; optimizer Random(920000+round). |
| 74 | saved_evidence_audit | `A5_learning/validate_delivery.py` | Inspects seed fields/identifiers in saved data or source AST. |
| 75 | saved_evidence_audit | `A6_learning/scripts/final_audit.py` | Inspects seed fields/identifiers in saved data or source AST. |
| 76 | literature_metadata_writer | `A6_learning/scripts/finalize_literature.py` | Mentions external-paper seeds or case function names in citation text. |
| 77 | saved_report_or_finalization | `A6_learning/scripts/render_report.py` | Copies or summarizes recorded seeds; no new seed draw. |
| 78 | training_case_generator | `A6_learning/scripts/train_policy.py` | 6600000+round*100000+mode*10000+off+i; off=0(train),5000(dev); optimizer Random(660000+round). |
| 79 | training_case_generator | `A6_learning/scripts/train_policy_r1_r2.py` | 6600000+round*100000+mode*10000+off+i; off=0(train),5000(dev); optimizer Random(660000+round). |
| 80 | initial_benchmark_generator | `work/benchmark.py` | range(1000,1000+args.count); stress range(2000,2000+args.stress_count); defaults200/30. |
| 81 | case_generator_code_builder | `work/build_frozen.py` | Writes source code containing range(5000,5100) to evaluation/generate_cases.py; does not itself invoke that generated script. |
| 82 | geometry_and_fixed_environment_probes | `coverage_audit/final_implementation_checks.py` | Random(seed), seed in range100; one-source fallback LocalEnv seeds0..15. |
| 83 | fixed_adversarial_task_generator | `coverage_audit/final_transport_and_adversarial.py` | noise maps positive->0, negative->1, smooth->2, uniform->3, passed into make_case. |
| 84 | geometry_and_fixed_environment_probes | `coverage_audit/implementation_checks.py` | Random(seed), seed in range100; one-source fallback LocalEnv seeds0..15. |
| 85 | fixed_adversarial_task_generator | `coverage_audit/transport_and_adversarial.py` | noise maps positive->0, negative->1, smooth->2, uniform->3, passed into make_case. |
| 86 | caller_seed_case_factory_and_environment | `work/local_env.py` | make_case(seed,...) uses Random(seed); LocalEnv default seed=0; noise hashes seed/coordinates. |
| 87 | fixed_environment_rule_check | `simulator_review/audit_conformance.py` | LocalEnv handcrafted source with keyword seed=719. |
| 88 | sensitivity_task_generator_cli | `bundle/sensitivity.py` | range(5000,5000+args.count), default100. |
| 89 | geometry_and_fixed_environment_probes | `audit/implementation_checks.py` | Random(seed), seed in range100; one-source fallback LocalEnv seeds0..15. |
| 90 | geometry_or_route_rng_without_seed_text | `B2/check_geometry.py` | random.Random(92271031) |
| 91 | geometry_or_route_rng_without_seed_text | `B2/check_phase_geometry.py` | random.Random(92271031) |
| 92 | geometry_or_route_rng_without_seed_text | `B2/check_residual_geometry.py` | random.Random(998211234) |
| 93 | geometry_or_route_rng_without_seed_text | `A2_information/check_exclusion.py` | random.Random(831146) |
| 94 | geometry_or_route_rng_without_seed_text | `A2_information/check_geometry.py` | random.Random(991720) |
| 95 | geometry_or_route_rng_without_seed_text | `coverage_audit/build_coverage.py` | random.Random(726) |
| 96 | fixed_default_environment_rule_check | `tests/test_rules.py` | LocalEnv(items) or LocalEnv([]), no explicit seed; default0 from local_env.py. |
