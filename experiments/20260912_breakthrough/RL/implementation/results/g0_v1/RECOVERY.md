# G0 v1 输出路径错误恢复说明

首个 original C7 Q3 index 0 实际执行完成并完整保存，142 个调用均已接受，1 个 full 已结算，unknown cost 为 0。随后 Recorder 对相对输出路径使用绝对 IMPL.relative_to，索引与 finally summary 写入失败；没有执行 teacher0。此轮失败属于输出工程，不是算法或环境正确性结论。

原始证据 `runs/g0_v1_q3_w00_original_c7.json.gz`、调用流水及 source_freeze 保留。恢复索引由保存结果和已结算流水补建，没有重跑或改变原始结果。之后将输出根目录规范为绝对路径，另以 g0_v2 冻结执行；v1 的 142 调用和 1 个执行继续包含在统一预算中。
