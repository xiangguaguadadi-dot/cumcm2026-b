# 新文献支援报告

研究截止2026-09-11；两批4个论文家族、5份版本PDF。实际正文阅读深度逐篇记录，没有把下载等同全文深读。目的为支援当前S0及第三阶段已冻结进展，按信息收费、连续发现、完成动作三个决策对象筛选；不是领域全量综述，也不评SOTA。

当前反馈已经区分三个方向：R2将首批DRD启发转成动作费用代理并在R3冻结回归中保留，但只买“一步可clear”的门槛开发失败；第二批DIRECt提供可给中间决策进展连续得分的后续假设。R3对动态覆盖做有限轨迹诊断，当前没有充分证据支持在线版。这些结果分别保存在研究者文件，本路线只读取与重算，不运行策略；论文不能直接证明本题退步的原因。

## 机制分类树

```mermaid
flowchart TD
  T["完整清除下的任务时间"] --> I["付费信息决策"]
  I --> D["重叠成功动作区域"]
  D --> DRD["Javdani 2014：Decision Region / HEC"]
  I --> E["连续决策区切边进展"]
  E --> DIRECT["Chen 2015：DIRECt / Noisy-OR"]
  I --> A["完成进度与识别收益联合计价"]
  A --> ASR["Navidi 2019v2/2020：ASR/ASP"]
  T --> C["连续方向发现"]
  C --> G["角缺口与子区域边界证书"]
  G --> FV["Wang/Cao 2013：Full-View Coverage"]
```

|主路径|关键原文与实际阅读|本题可试机制|未迁移的保证|
|---|---|---|---|
|付费信息→重叠动作区域|[DRD 2014](https://proceedings.mlr.press/v33/javdani14.html)，PDF 1–8/9页|候选clear点20米圆作为重叠决策区；一步决策成本与radius_gain对照|有限确定假说、HEC近似界、离散假说全覆盖不能代替连续真值证书|
|付费信息→连续决策切边进展|[DIRECt 2015](https://ojs.aaai.org/index.php/AAAI/article/view/9694)，PDF 1–7/8页|共享多位置假说、clear候选；连续剩余边权与当前费用代理独立对照|特定EC² Noisy-OR构造；有限先验和固定测试费用；一般乘积不保证自适应次模|
|付费信息→相对完成收益和识别收益|[ASR/ASP](https://arxiv.org/abs/1606.01530v2)，1–7、12–13、18–19、22–25/28页|信息代理必须改变完成动作；移动费用另计|已知场景概率、次模完成函数、固定测试成本/度量路径条件|
|连续方向发现→角缺口/区域边界|[Full-view 2013](https://mcn.cse.psu.edu/paper/yiwang/tosn-wang13.pdf)，1、4–11、26–28/31页|B3叶格证书按频道加入实际测点，验证未来站是否冗余|θ<π/2相机模型、随机部署密度和barrier覆盖不能直接覆盖本题θ=π/2与静止源|

## 可直接实施与验收

完整参数边界、步骤、反例风险和验证方案见[第1批备忘](research_updates/001_decision_value_and_dynamic_cover.md)及[第2批中间决策进展](research_updates/002_intermediate_decision_progress.md)。第2批同时保存R2 R3开发的1536行复算和失败解释的证据边界；新文章在该冻结轮之后读到，不反向归因。建议先保持父法候选点和假说数量，单独换收益函数；动态覆盖先统计真实未知频道测点数量与删除潜力，再付费新增扫描。开发和全任务结果须分开，不把基线轨迹上的离线评分当新策略真实运行。

## 阅读路线与范围

优化者先读备忘中对应任务，再读DRD第2–4与8页、DIRECt第3–5页、Full-view第5–8页；理论审查读ASR第6–7、12–13及18–19页。全部文章的原文问题、效果、边界、缓存SHA与实际页范围见[literature.json](literature.json)。公式页另外做图像核对，但完整PDF及其逐页文本只留本地忽略缓存，不上传到私有代码仓库。

检索词包含adaptive submodular ranking/routing、decision region determination、full-view coverage、redundant sensors、online coverage waypoints。搜索服务多次连接失败；原站arXiv、PMLR、AAAI OJS、作者实验室和Crossref成功，OpenAlex返回429；未据失败结果虚构检索覆盖。扩展发现集记录ASR引用的相关材料，但没有假装已深读。以后按实际反馈继续补充，首批不是研究结束。
