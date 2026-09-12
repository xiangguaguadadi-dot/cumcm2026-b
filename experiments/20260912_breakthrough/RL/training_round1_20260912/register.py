"""Freeze new split identities before interactions; constructing Source is not a run."""
from __future__ import annotations
from collections import Counter
from datetime import datetime,timezone
import importlib.util
import math
from pathlib import Path
from .common import ROOT,RL,REPO,BASE,WORLD_SOURCE,WORLD_PIN,ROLES,SEEDS,LIMITS,CARRY_IN,load,save_new,sha,digest

def recipe_module():
    if sha(WORLD_SOURCE)!=WORLD_PIN:raise RuntimeError('Frozen world generator differs')
    spec=importlib.util.spec_from_file_location('_bc_rpi_r1_private_recipe',WORLD_SOURCE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def identities(world):
    sources=[{k:s[k] for k in ('channel','x','y','radius','direction')} for s in world['sources']]
    physical=dict(mode=world['mode'],seed=world['seed'],noise=world['noise'],
                  sources=[dict(s,cleared=False) for s in sources])
    layout=sorted((s['x'],s['y'],s['radius']) for s in sources)
    # Conservative necessary rotation/mode-invariant layout signature. It ignores
    # channel, orientation, noise and seed; equal signatures stop registration.
    # Rounded invariants are not a proof covering all arbitrary historical transforms.
    radii=sorted(round(s['radius'],6) for s in sources)
    origin=sorted(round(s['x']**2+s['y']**2,6) for s in sources)
    pairwise=sorted(round((a['x']-b['x'])**2+(a['y']-b['y'])**2,6)
                    for i,a in enumerate(sources) for b in sources[i+1:])
    return dict(world_sha256=digest(physical),layout_without_mode_seed_sha256=digest(layout),
                rotation_mode_family_sha256=digest(dict(radii=radii,origin_squared=origin,pair_squared=pairwise)))

def prior_paths():
    paths={REPO/'evaluation/cases_v1.json',REPO/'experiments/20260911_stage4/exposed_cases.json',
           BASE/'evaluator/probes_v1.json'}
    paths.update((REPO/'experiments/20260911_rl_execution/data').glob('*.json'))
    for side in ('A1','A2'):paths.update((RL.parent/side).rglob('*.json'))
    for p in (REPO/'experiments').rglob('*.json'):
        if ROOT in p.parents:continue
        if any(word in p.name.lower() for word in ('cases','worlds','registry','registration','manifest','plan')):
            paths.add(p)
    return sorted(p for p in paths if p.is_file())

def novelty(new,recipes):
    seeds=set();worlds=set();layouts=set();families=set();seen_recipe=set();records=0
    paths=prior_paths();files=[]
    def add(world):
        nonlocal records
        ids=identities(world);worlds.add(ids['world_sha256']);layouts.add(ids['layout_without_mode_seed_sha256'])
        families.add(ids['rotation_mode_family_sha256']);records+=1
    def visit(value):
        if type(value) is list:
            for v in value:visit(v)
        elif type(value) is dict:
            if type(value.get('seed')) is int:seeds.add(value['seed'])
            for k,v in value.items():
                if 'seed' in k.lower() and type(v) is list:seeds.update(x for x in v if type(x) is int)
            if (all(k in value for k in ('mode','seed','noise','sources')) and
                    type(value['sources']) is list and value['sources'] and
                    all(type(s) is dict and all(k in s for k in ('channel','x','y','radius','direction')) for s in value['sources'])):
                add(value)
            elif (str(value.get('world_id','')).startswith('rl-new-world-recipe-v1:') and
                    all(k in value for k in ('mode','seed','noise','scenario','group'))):
                key=(value['seed'],value['mode'],value['noise'],value['scenario'])
                if key not in seen_recipe:
                    seen_recipe.add(key);add(dict(value,sources=[vars(s) for s in recipes.instantiate(value)]))
            for v in value.values():visit(v)
    for path in paths:
        visit(load(path));files.append(dict(path=str(path.relative_to(REPO)),sha256=sha(path)))
    fields={'seed':seeds,'world_sha256':worlds,'layout_without_mode_seed_sha256':layouts,'rotation_mode_family_sha256':families}
    overlaps={k:sorted(old&{w[k] for w in new}) for k,old in fields.items()}
    within={k:len(new)-len({w[k] for w in new}) for k in fields}
    passed=not any(overlaps.values()) and not any(within.values())
    return dict(schema='bc-rpi-r1-novelty-v1',status='pass' if passed else 'collision_stop',
        checked_files=files,old_concrete_or_reconstructed_records=records,
        old_unique_seeds=len(seeds),old_unique_worlds=len(worlds),old_unique_layouts=len(layouts),
        old_unique_rotation_mode_families=len(families),overlap_with_prior=overlaps,
        duplicate_counts_within_new_roles=within,new_worlds=len(new),
        family_definition='Conservative rounded source radii, origin squared distances and pairwise squared distance multiset; ignores mode/channel/direction/noise/seed',
        evidence_boundary='Fresh development is not sealed final. Exact and necessary invariant screening covers only listed files/reconstructable registered recipes, not every possible historical transformed world or official distribution.')

def register():
    if (ROOT/'world_manifest.json').exists():raise FileExistsError('World registration already exists; do not regenerate')
    old=load(RL.parent/'RL_EXECUTION_RESULT.json')
    if not (old['g1_complete'] and old['cumulative_counts']['business_calls']==197456 and
            old['cumulative_counts']['executions_started']==1696):raise RuntimeError('Accepted G0/G1 carry-in changed')
    recipes=recipe_module();records=[]
    for role,count in ROLES.items():
        namespace='bc_rpi_r1_20260912_v1_'+role
        for index in range(count):
            recipe=recipes.recipe(namespace,4,index,group_index=index%12)
            record=dict(recipe,role=role,sources=[vars(s) for s in recipes.instantiate(recipe)])
            record.update(identities(record));records.append(record)
    audit=novelty(records,recipes);save_new(ROOT/'novelty_audit.json',audit)
    if audit['status']!='pass':raise RuntimeError('New-world collision; preserve audit and stop before any interaction')
    role_counts=Counter(w['role'] for w in records)
    if dict(role_counts)!=ROLES:raise AssertionError('World-role count differs')
    save_new(ROOT/'world_manifest.json',dict(schema='bc-rpi-r1-world-manifest-v1',worlds=records,
        role_counts=dict(role_counts),source_recipe_sha256=WORLD_PIN,unique_worlds=180,
        roles_locked=True,no_final_worlds=True,no_rotation_augmentation=True))
    probes=load(BASE/'evaluator/probes_v1.json')['worlds']
    compatibility=[w for w in probes if w['phase']=='g0' and w['mode']==4 and w['index']<12]
    save_new(ROOT/'compatibility_registration.json',dict(worlds=compatibility,
        maximum_executions=24,plan='For each of 12 fixed old G0 Q4 worlds: direct C7 and new selector pinned to teacher; compare exact events/cost',
        role='old exposed interface probes, never fitted or calibrated',source_sha256=sha(BASE/'evaluator/probes_v1.json')))
    save_new(ROOT/'registration.json',dict(schema='bc-rpi-round1-registration-v1',status='registered_no_actual_calls',
        registered_utc=datetime.now(timezone.utc).isoformat(),approved_scope='One first-round counterfactual-supervised neural fit, 3 seeds, independent calibration and complete development; old headroom gate overridden by explicit user request',
        neural_seeds=SEEDS,limits=LIMITS,carry_in=CARRY_IN,role_counts=ROLES,
        manifest_sha256=sha(ROOT/'world_manifest.json'),novelty_sha256=sha(ROOT/'novelty_audit.json'),
        plan_sha256=sha(ROOT/'EXECUTION_PLAN.md'),prior_result_sha256=sha(RL.parent/'RL_EXECUTION_RESULT.json'),
        compatibility_sha256=sha(ROOT/'compatibility_registration.json'),
        clock_start='Independent Budget initialized after coordinator collection acceptance, before first new actual call',
        labels_shared_across_initializations=True,label_continuation='Same frozen C7 pi0 for every action and reference',
        state_sampling='public source-entry index; m=min(4,n); floor(k*(n-1)/(m-1)); m=1 -> index0',
        empty_action_state_loss='0, retained in fixed state denominator; malformed/failed data is not empty',
        no_further_rounds=True,no_sealed_final=True,no_official=True))
    print({'registered_worlds':len(records),'roles':dict(role_counts),'novelty':'pass','actual_calls':0})

if __name__=='__main__':register()
