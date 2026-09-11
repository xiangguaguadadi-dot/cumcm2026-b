"""Freeze the budget, disjoint data recipes and selection procedure before G2."""
from common import *
from data.worlds import recipe, GENERATOR_VERSION

def seed_values(value, in_seed_list=False):
    found=set()
    if isinstance(value,dict):
        for k,v in value.items():
            if k in ('seed','noise_seed','environment_seed') and type(v) is int:found.add(v)
            found.update(seed_values(v,in_seed_list=k in ('seeds','used_seeds')))
    elif isinstance(value,list):
        for v in value:
            if in_seed_list and type(v) is int:found.add(v)
            found.update(seed_values(v,in_seed_list))
    return found

def main():
    path=EXEC/'data/g2_plan.json'
    if path.exists():raise RuntimeError('G2 plan already registered; do not rewrite')
    g0=json.loads((EXEC/'core/g0_results_v1/summary.json').read_text())
    ga=json.loads((EXEC/'core/g0_audit_v1/summary.json').read_text())
    g1=json.loads((EXEC/'results/g1_pipeline_v1/summary.json').read_text())
    if not (g0['all_complete'] and g0['teacher_event_equality_all'] and g1['passed']):
        raise RuntimeError('Prerequisite gate failed')
    # Actual existence/completeness of the independent reordered-action audit.
    if ga.get('all_complete') is not True:raise RuntimeError('G0 action-reordering audit incomplete')
    demo=[recipe('g2_shared_c7_demo',3+i%2,i//2) for i in range(512)]
    train={str(seed):[recipe(f'g2_train_init{seed}',3+i%2,i//2) for i in range(1024)] for seed in (81001,81002,81003)}
    selection=[recipe('g2_checkpoint_selection',3+i%2,i//2) for i in range(192)]
    prior={r['seed'] for r in json.loads((EXEC/'data/initial_registry.json').read_text())['worlds']}
    references=[]
    candidates={REPO/'evaluation/cases_v1.json'}
    for name in ('cases.json','exposed_cases.json','used_seeds.json'):
        candidates.update(p for p in (REPO/'experiments').rglob(name) if EXEC not in p.parents)
    for p in sorted(candidates):
        data=json.loads(p.read_text());seeds=seed_values(data,p.name=='used_seeds.json')
        prior.update(seeds);references.append(dict(path=str(p.relative_to(REPO)),sha256=sha(p),seed_count=len(seeds)))
    records=demo+sum(train.values(),[])+selection
    seeds=[r['seed'] for r in records]
    if len(set(seeds))!=len(seeds) or prior.intersection(seeds):
        raise RuntimeError('New split namespace has a seed collision; must resolve before execution')
    hashes={str(p.relative_to(EXEC)):sha(p) for folder in ('core','ppo','q_learning','runners','data')
            for p in (EXEC/folder).glob('*.py')}
    hashes['shared.py']=sha(EXEC/'shared.py')
    plan=dict(version='g2_registered_plan_v1',generator_version=GENERATOR_VERSION,
        device='cpu',threads_per_process=1,maximum_concurrent_initializations=3,
        initialization_seeds=[81001,81002,81003],demonstrations=demo,training=train,selection=selection,
        exact_world_pairing='PPO and Q execute identical training recipes for the corresponding initialization; each execution is counted separately',
        split_overlap=0,prior_seed_count=len(prior),prior_sources=references,code_sha256=hashes,
        gates={'core_g0':sha(EXEC/'core/g0_results_v1/summary.json'),
               'core_reordered_g0':sha(EXEC/'core/g0_audit_v1/summary.json'),
               'resource_g1':sha(EXEC/'results/g1_pipeline_v1/summary.json')},
        bc={'shared_episodes':512,'passes':8,'batch_episodes':8,'epochs_per_update':1},
        ppo={'max_new_episodes_per_init':1024,'max_business_calls_per_init':1000000,
             'batch_episodes':8,'epochs_per_update':4,'checkpoint_episodes':[128,256,512,1024]},
        q={'max_new_episodes_per_init':1024,'max_business_calls_per_init':1000000,
           'mc_passes':4,'mc_batch_episodes':8,'td_batch_episodes':8,'td_updates_per_new_episode':1,
           'replay_sampling':'Uniform without replacement among completed demo and own training episode paths; failed and zero-decision episodes retained',
           'feature_range':'Cumulative shared demo and own completed training observations; physical-only clocks v2; never selection',
           'checkpoint_episodes':[128,256,512,1024]},
        complete_episode_call_reserve=COMPLETE_EPISODE_RESERVE,
        selection_protocol={'checkpoints_per_algorithm_init':4,'worlds':192,'worlds_per_question':96,
            'baselines':['original_c7','teacher_wrapper','same_candidates_greedy','bc_per_init'],
            'checkpoint_choice':'For each question and initialization, among complete checkpoints choose minimum mean seconds/source; report every planned checkpoint including failures',
            'promotion':'Question separately: all deployment evaluations for a claimed candidate complete; paired mean seconds/source >=2 percent lower than both original C7 and corresponding BC, 95 percent paired bootstrap mean-difference upper bound <0, >=2/3 initializations improve in same direction',
            'aggregate_uncertainty':'Average initialization differences within each world before bootstrap; do not count 3 repeated initializations as 3 independent worlds',
            'bootstrap':{'resamples':10000,'seed':84771,'method':'stratified by the twelve scenario groups, resample paired worlds within group'},
            'evidence':'Checkpoint-selection evidence, subject to selection bias; no final blind or official validation; no default C7 replacement'},
        final_test_worlds_generated=0)
    dump(path,plan)
    print(json.dumps({'registered_unique_world_recipes':len(records),'split_overlap':0,'prior_seeds':len(prior),'plan_sha256':sha(path)}))
if __name__=='__main__':main()
