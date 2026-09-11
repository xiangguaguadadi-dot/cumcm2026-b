# 第一轮交叉评议索引

本轮只交付供用户审阅的研究方案。评议通过不是实现或训练授权，也不是性能通过。

- [前置量表与独立检查](PRE_REVIEW.md)：在两位完整初稿前确定13项门槛及主要反例。
- [B路线R1正式评议](REVIEW_R1_B.md)：已审阅B的R0并直接发送geometry，要求B1–B6逐项修订；核心阻断为目标归一化、真实失败终端、可计算fallback合同。
- [A路线R1正式评议](REVIEW_R1_A.md)：已完整审阅A初次正式稿（自标R1，work缓存）；直接发送audit做文稿R2。要求A1–A6回应，核心为MC/PPO归一更新、真实失败终端、alive空性与整体矛盾分离。

最终复评将在两位回应至少一轮实质修改后形成REVIEW_FINAL.md与decision_matrix.json。尚未进行最终结论。

最终状态：A-R2与B-R1均已逐项实质修订并经全文复评；最终补丁统一32无进展决策/10000学习请求、按题晋级，B尾费用折叠的真实terminal标志。结论和实际输入SHA见[REVIEW_FINAL.md](REVIEW_FINAL.md)及[decision_matrix.json](decision_matrix.json)，可交用户审阅，不授权实施。
