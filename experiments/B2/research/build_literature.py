from pathlib import Path
import json,hashlib,re
base=Path(__file__).resolve().parents[1]
old=Path('/Users/t/ai project/数学建模2026/agent_experiments/20260911')
ledgers=json.loads((base/'research/prior_literature_complete.json').read_text())
readings=[
 ('A1_space','2207.06209','research/cache/2207.06209.txt',[2,3],['几何覆盖','凸块分解与采样点','Boustrophedon cellular decomposition'],'论文按障碍连通拓扑分块并栅扫，逐格采样且可从四角进入；B2只借分区覆盖与进入相位这一原则。','R1/R3 partition_points、PhaseSolver.optical_points','论文环境采样不提供B2连续20米清除覆盖证明；B2贪心最小圆分区是本题自拟。'),
 ('A2_information','2603.04867','research/2603.04867.txt',[3,7],['几何可靠性','集合成员外包','差分距离凸外包'],'原文区分中心估计与保证包含真值的外包；差分距离方程是其特有机制。','R2 residual_components保守排除；R1全凸块最小包围圆认证','本题没有距离读数，不复现SOCP/SDP；R2碎片机制正确但本地任务更慢。'),
 ('A4_directional','2011.10474v2','research/2011.10474v2.txt',[3],['动作规划','多模态观测与无检测','贝叶斯射频视觉似然'],'公式15按可见域内外给未检测不同似然，公式16联合两模态；控制目标为MAP接近且正文承认纯利用。','继承A4 visibility_hypotheses；R3仅失败clear修正有限位置权重再比较两个完整覆盖','发射端半圆与相机视域模型不同，B2是离散近似排序而非校准后验；不声称概率最优或原论文复现。')]
papers=[]
for agent,id,rel,pages,classification,mechanism,impl,boundary in readings:
 ledger=next(x['records'] for x in ledgers if x['agent']==agent)
 items=ledger.get('papers',ledger.get('sources',[]))
 p=next(p for p in items if p.get('id')==id or p.get('arxiv')==id)
 source=old/agent/'experiments'/agent/rel
 txt=source.read_text();parts=re.split(r'=+ PAGE (\d+) =+',txt)
 actual={int(parts[i]):parts[i+1] for i in range(1,len(parts),2) if int(parts[i]) in pages}
 assert set(actual)==set(pages)
 papers.append(dict(id=id,title=p['title'],authors=p['authors'],year=int(id[:2])+2000,url=p['url'],pdf_url=p['pdf_url'],publication_status='此前原路线核验arXiv正文；B2本轮未联网重验会议/出版身份，不使用获奖或近期SOTA声明',awards='not_checked',project_url=p.get('project_url'),code_url=p.get('code_url'),dataset_url=p.get('dataset_url'),source_level='cached_primary_text_sections_re_read',primary_classification=classification,secondary_tags=[],classification_confidence='high',actual_b2_reading_scope={'pages':pages,'source_path':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'characters':sum(len(x) for x in actual.values()),'scope':'仅列明正文页；其余逐篇信息是旧路线文献账本，不能继承其阅读范围'},problem=p.get('problem',p.get('mechanism')),mechanism=mechanism,inspiration_to_implementation=impl,limits=boundary,original_empirical_evidence=p.get('evidence'),evidence_boundary='旧路线记录的论文实验在B2没有复现，不作为本题性能数值依据'))
out=dict(agent='B2',cutoff='2026-09-11',scope='读取全部六路线既有文献账本，按当前几何子问题重读3篇缓存正文的指定页。不新增论文检索、不声称全面领域综述或全部论文深读。',search_window='既有语料，不建立新的时间窗口',queries=[],search_channels=['prior campaign literature ledgers','cached primary paper text'],core_section_reread_count=3,extended_ledger='research/prior_literature_complete.json',dedup='稳定arxiv号忽略版本；主分类每篇只有一条',papers=papers)
(base/'literature.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
