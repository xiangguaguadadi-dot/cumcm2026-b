"""Rebuild the bounded, source-verified mechanism corpus and reading ledger."""
import hashlib,json,re,html
from html.parser import HTMLParser
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
CACHE=ROOT/'experiments/20260912_breakthrough/RL/sources'
class Metadata(HTMLParser):
    def __init__(self):super().__init__();self.meta={}
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=='meta' and d.get('name','').startswith('citation_'):
            self.meta.setdefault(d['name'],[]).append(d.get('content',''))

# Core means targeted methods + experimental/boundary reading, never an
# assertion that every page, proof, appendix, or bibliography was read.
SPECS=[
('maxent','belief/model adaptation','planning-only posterior reweighting','core',
 'bearing_maxent_current.html','https://arxiv.org/html/2605.11116v1',
 'II bearing FIM and two layers; IV setup; V limitations; no full proof audit',
 'Particle reweighting changes placement objective while the Bayesian observation update retains the original prior.',
 'Multi-source 2D synthetic bearing localization; Gaussian noise 8 or 15 degrees, D-optimal comparison.',
 'No guarantee on complete-task time; Gaussian independence and particle approximation differ from bounded fixed error.',
 'Separate planning estimates from reliable polygons; no direct MaxEnt reproduction.'),
('bias_registration','belief/model adaptation','shared sensor-bias estimation','core',
 'bias_registration_current.html','https://arxiv.org/abs/1603.03450',
 'PDF pages 1-6 including measurement model and likelihood; simulation setup excerpt',
 'Triangulated pseudo-measurement differences identify sensor bias, fitted with batch maximum likelihood.',
 'Distributed multisensor multitarget bearing tracking; simulations also consider missed detections and false alarms.',
 'Requires identifiable sensor geometry; independent Gaussian assumptions and moving targets differ from this problem.',
 'B1-B4 shared-angle planning hypotheses inferred from successful-clear regions; not the original estimator.'),
('vb_noise','belief/model adaptation','joint noise mean and covariance inference','core',
 'vb_noise_current.html','https://arxiv.org/abs/2305.08390',
 'PDF pages 1-4; VII setup and VIII discussion excerpts; no full VB derivation audit',
 'Normal-inverse-Wishart model jointly adapts unknown noise mean and covariance through variational filtering.',
 'Moderate/high nonlinear underwater bearing tracking, static/varying covariance, RMSE and track-loss comparisons.',
 'Gaussian noise, process model and 30-minute sensing differ; some reported metrics exclude divergent tracks.',
 'Motivates learning a noise bias instead of assuming zero mean; our grid profile likelihood is not VB.'),
('residual','controller structure','retain controller and learn residual','core',
 'residual_current.html','https://arxiv.org/abs/1812.03201v2',
 'Cached PDF pages 1-5 method, setup, real block-assembly result',
 'An additive learned control policy complements a hand-engineered controller, trained using a TD3 variant.',
 'MuJoCo and physical block assembly, including misalignment and control-noise experiments.',
 'Continuous torque/position control differs from discrete service replacement; reported sample efficiency does not transfer.',
 'R1-R6 alter narrowly defined trial/service decisions while keeping coverage and fallback.'),
('spibb','controller structure','conservative policy improvement','core',
 'spibb_current.html','https://proceedings.mlr.press/v97/laroche19a.html',
 'Cached PDF page 3 method/theorems, page 5 experimental protocol',
 'On insufficiently supported state-action pairs, retain the baseline action probabilities.',
 'Finite MDP/gridworld mean and CVaR comparisons; approximate deep variants are separate.',
 'Our empirical gates have no finite-MDP SPIBB bound or state-action count guarantee.',
 'Use fixed validation gates and keep a baseline action; do not infer mathematical safety from a model score.'),
('aggrevate','policy learning signal','cost-sensitive rollout labels','core',
 'aggrevate_current.html','https://arxiv.org/abs/1406.5979',
 'Cached PDF pages 1-3, algorithm and regression reduction; theoretical work',
 'Explore an action at a visited state, complete a reference-policy rollout, and learn from its cost-to-go.',
 'Theoretical no-regret framework; no benchmark score imported into our report.',
 'Finite feature approximation and imperfect reference do not ensure monotone real-task improvement.',
 'R2 explicitly one-action surrogate; R3-R5 actual local tails; R6 exact whole-task paired tails.'),
('catnipp','planning and representation','attention and receding-horizon IPP','core',
 'catnipp_current.html','https://proceedings.mlr.press/v205/cao23b.html',
 'Cached PDF pages 4-6 architecture/training/planning, page 8 limitations',
 'GP belief graph, attention/LSTM policy, budget mask, optional sampled receding-horizon trajectories.',
 'Information mapping and light-intensity experiment; comparison objective is covariance reduction, not full clearance time.',
 'GP-kernel sensitivity, graph discretization and substantial training budget; sensing reward mismatch matters.',
 'Supports history and macro planning alternatives; full graph PPO not repeated after repository negative result.'),
('lols','policy learning signal','mixed-reference local rollout search','extended',
 'lols_current.html','https://proceedings.mlr.press/v37/changb15.html',
 'Cached PDF page 3 algorithm; other results not deeply read',
 'One-step deviations evaluated by mixed reference/current-policy tails generate cost-sensitive examples.',
 'Structured prediction search; no numeric transfer claim.',
 'Teacher mismatch and downstream distribution shift remain.',
 'R5 changes visited-state distribution; R6 evaluates reference and two deviations.'),
('aggrevated','policy learning signal','differentiable cost-to-go imitation','extended',
 'aggrevated_current.html','https://proceedings.mlr.press/v70/sun17d.html',
 'Current primary metadata and abstract; cached repository proposal context only',
 'Differentiable policy improvement with reference cost-to-go information.',
 'Primary abstract only in this pass; no reproduced experiment or numerical claim.',
 'Neural optimization alone cannot enlarge useful actions or correct a poor target.',
 'Considered neural alternative; chose auditable ridge before a larger model.'),
('dagger','policy learning signal','on-policy data aggregation','extended',
 str(CACHE/'S01_dagger.html'),'https://proceedings.mlr.press/v15/ross11a.html',
 'Cached PDF pages 1-2 introduction; current live page not re-fetched',
 'Collect reference supervision on learner-visited states to address compounding imitation error.',
 'Imitation and sequence labeling; no exact benchmark number used.',
 'Imitating actions cannot by itself outperform a strong teacher.',
 'R5 learner-state recollection inspired by distribution correction, with cost labels instead of action agreement.'),
('offripp','planning and representation','offline support-constrained IPP','extended',
 'offripp_current.html','https://arxiv.org/abs/2409.16830',
 'Cached PDF first page and current metadata',
 'Batch-constrained offline RL limits extrapolation from pre-collected informative path data.',
 '2D light intensity and 3D fruit identification tasks stated in introduction.',
 'Dataset support and information-gain objective differ from legal clear-completion time.',
 'Did not rerun old constrained-Q route that already failed in the repository.'),
('meta_rf','planning and representation','recurrent RF adaptation','extended',
 'meta_rf_current.html','https://arxiv.org/html/2605.12569v1',
 'Current full body IV-V methods/data sections; VI results not fully audited',
 'CNN/LSTM observation encoders and meta adaptation for source-seeking from RF observations.',
 'Synthetic Sionna indoor RF environment with current and goal feature tensors.',
 'Raw multi-antenna IQ and goal observations are absent from the four contest interfaces; distance shaping differs.',
 'Rejected direct transfer of architecture/reward, retained idea of online latent-context adaptation.'),
('tdmpc2','planning and representation','latent world-model planning','extended',
 'tdmpc2_current.html','https://arxiv.org/abs/2310.16828',
 'Current primary metadata and abstract only',
 'Local trajectory optimization in a learned latent world model.',
 'Broad continuous-control benchmark in abstract; no reproduced score.',
 'Would add model error for deterministic geometry that is already available analytically.',
 'Not implemented; exact simulator tails are cheaper for this bounded experiment.'),
('fql','planning and representation','expressive offline action distribution','extended',
 'fql_current.html','https://arxiv.org/abs/2502.02538',
 'Current primary metadata and abstract only',
 'Flow-matching behavior policy guides an expressive one-step RL actor.',
 'D4RL/OGBench according to primary abstract; not compared numerically here.',
 'Useful for broad continuous action spaces; our small legal residual set does not need a generative actor.',
 'Deferred until finite alternatives show substantial verified action-space headroom.'),
('cids','planning and representation','latent-context information objective','extended',
 'cids_current.html','https://arxiv.org/abs/2602.03939',
 'Current primary metadata and abstract only',
 'Reward augmented with information about latent context in contextual POMDPs.',
 'Light-Dark experiment described in primary abstract.',
 'Mutual-information bonus is not the contest time metric; Bayesian regret assumptions need a correct context model.',
 'Shared-bias hypothesis is a context candidate; no IDS bound or bonus is claimed.'),
]

def main():
    rows=[]
    reading_sources=json.loads((HERE/'research/reading_sources.json').read_text())
    for sid,family,mechanism,tier,filename,url,read,method,bench,limit,transfer in SPECS:
        path=Path(filename) if Path(filename).is_absolute() else HERE/'research'/filename
        if sid=='dagger':path=HERE/'research/dagger_cached.html'
        raw=path.read_text();parser=Metadata();parser.feed(raw)
        meta=parser.meta
        title=meta.get('citation_title',[sid])[0]
        if title==sid:
            match=re.search(r'<h1[^>]*>(.*?)</h1>',raw,re.S|re.I) or re.search(r'<title>(.*?)</title>',raw,re.S|re.I)
            if match:title=html.unescape(' '.join(re.sub('<[^>]+>',' ',match.group(1)).split()))
        authors=meta.get('citation_author',[])
        if sid=='maxent':authors=['Raktim Bhattacharya']  # Actual primary HTML author block.
        if sid=='meta_rf':authors=['M. Shamail J. Khan','Nisha L. Raichur','Lucas Heublein','Christian Wielenberg','Alexander Mattick','Tobias Feigl','Christopher Mutschler','Felix Ott']
        rows.append(dict(id=sid,title=title,authors=authors,
            date=meta.get('citation_date',meta.get('citation_publication_date',[])),
            venue=meta.get('citation_conference_title',meta.get('citation_journal_title',['arXiv/preprint identity only'])),
            source_url=url,source_path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            tier=tier,reading_scope=read,reading_sources=reading_sources.get(sid,[]),primary_path=[family,mechanism,sid],method=method,
            benchmark_scope=bench,limitations=limit,local_transfer=transfer,
            verification='frozen cached primary page, not freshly retrieved' if sid=='dagger' else 'primary page retrieved this run'))
    assert len(rows)==len({r['id'] for r in rows})==15
    out=dict(cutoff='2026-09-12',scope='Bounded mechanism research for Q4 improvement, not an exhaustive systematic review',
        total=15,targeted_core=7,extended=8,primary_families=4,
        queries=['bearing only target localization pseudolinear least squares biased estimator',
            'Bayesian experimental design source localization bearing only active sensing',
            'residual reinforcement learning','cost-sensitive imitation rollout',
            'bearings only bias estimation'],
        access_notes='web tool and sandbox proxy failed; direct curl --noproxy with approved network access succeeded. Primary PDFs/texts from the frozen repository supplemented fresh pages.',
        entries=rows)
    (HERE/'research/corpus.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps({k:out[k] for k in ['total','targeted_core','extended','primary_families']}))
if __name__=='__main__':main()
