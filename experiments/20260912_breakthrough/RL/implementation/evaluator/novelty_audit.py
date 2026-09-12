"""Read-only probe overlap check against concrete and recipe-based prior worlds."""
import hashlib
import importlib.util
import json
from .register import REPO,WORLD_SOURCE,WORLD_PIN,sha
from .runtime import worlds


def audit():
    if sha(WORLD_SOURCE)!=WORLD_PIN:raise RuntimeError('Prior recipe module changed')
    spec=importlib.util.spec_from_file_location('_bc_rpi_readonly_old_recipes',WORLD_SOURCE)
    recipe_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe_module)
    paths=[REPO/'evaluation/cases_v1.json',REPO/'experiments/20260911_stage4/exposed_cases.json']
    paths+=list((REPO/'experiments/20260911_rl_execution/data').glob('*.json'))
    paths+=[p for name in ('A1','A2') for p in (REPO/'experiments/20260912_breakthrough'/name).rglob('*.json')]
    seeds=set();hashes=set();files=[];recipes=0;concrete=0
    def visit(value):
        nonlocal recipes,concrete
        if type(value) is list:
            for item in value:visit(item)
        elif type(value) is dict:
            if type(value.get('seed')) is int:seeds.add(value['seed'])
            for key,v in value.items():
                if 'seed' in key.lower() and type(v) is list:
                    seeds.update(x for x in v if type(x) is int)
            if all(k in value for k in ('mode','seed','noise','sources')) and type(value['sources']) is list:
                content={k:value[k] for k in ('mode','seed','noise','sources')}
                hashes.add(hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':')).encode()).hexdigest());concrete+=1
            elif (str(value.get('world_id','')).startswith('rl-new-world-recipe-v1:') and
                    all(k in value for k in ('mode','seed','noise','scenario','group'))):
                content=dict(mode=value['mode'],seed=value['seed'],noise=value['noise'],
                             sources=[vars(s) for s in recipe_module.instantiate(value)])
                hashes.add(hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':')).encode()).hexdigest());recipes+=1
            for item in value.values():visit(item)
    for path in sorted(set(paths)):
        visit(json.loads(path.read_text()))
        files.append(dict(path=str(path.relative_to(REPO)),sha256=sha(path)))
    new=worlds('g0')+worlds('g1')
    overlap_seeds=sorted(seeds&{w['seed'] for w in new})
    overlap_worlds=sorted(hashes&{w['world_sha256'] for w in new})
    return dict(status='pass' if not overlap_seeds and not overlap_worlds else 'overlap_detected',
        checked_files=files,old_unique_seeds=len(seeds),old_unique_world_hashes=len(hashes),
        old_concrete_records=concrete,old_recipe_records=recipes,new_worlds=len(new),
        seed_overlap=overlap_seeds,world_content_hash_overlap=overlap_worlds,
        evidence_boundary='Probe/exposed diagnostic only; scanned frozen v1/stage4/old-RL data and all current A1/A2 JSON, not a claim of universal historical or official novelty.')
