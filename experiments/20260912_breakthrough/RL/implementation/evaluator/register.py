"""Register hashes/recipes before any local environment interaction."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from .budget import Budget, IMPL, atomic_json

REPO = IMPL.parents[3]
RL = IMPL.parent
WORLD_SOURCE = REPO / 'experiments/20260911_rl_execution/data/worlds.py'
WORLD_PIN = 'f595623edd01fbcaeefd64a05bf3905f13deb25f9508d2f813e94715a5509f80'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scan_seed_values(obj, into):
    if isinstance(obj, dict):
        if type(obj.get('seed')) is int:
            into.add(obj['seed'])
        for value in obj.values():
            scan_seed_values(value, into)
    elif isinstance(obj, list):
        for value in obj:
            scan_seed_values(value, into)


def register():
    if sha(WORLD_SOURCE) != WORLD_PIN:
        raise RuntimeError('World recipe changed')
    spec = importlib.util.spec_from_file_location('_bc_rpi_probe_recipe', WORLD_SOURCE)
    worlds = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worlds)
    paths = [REPO / 'evaluation/cases_v1.json',
             REPO / 'experiments/20260911_stage4/exposed_cases.json']
    paths += list((REPO / 'experiments/20260911_rl_execution/data').glob('*.json'))
    paths += [p for side in ('A1', 'A2') for p in (RL.parent / side).glob('*.json')]
    old_seeds = set()
    old_sources = []
    for path in sorted(set(paths)):
        value = json.loads(path.read_text())
        scan_seed_values(value, old_seeds)
        old_sources.append(dict(path=str(path.relative_to(REPO)), sha256=sha(path)))
    records = []
    for phase, modes in [('g0', (3, 4)), ('g1', (4,))]:
        split = f'bc_rpi_{phase}_20260912_v1'
        for mode in modes:
            for index in range(24):
                recipe = worlds.recipe(split, mode, index, group_index=index % 12)
                source_values = [vars(s) for s in worlds.instantiate(recipe)]
                content = dict(mode=mode, seed=recipe['seed'], noise=recipe['noise'], sources=source_values)
                record = dict(recipe, phase=phase, role='probe', sources=source_values,
                    world_sha256=hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':')).encode()).hexdigest())
                records.append(record)
    if len({r['seed'] for r in records}) != 72 or len({r['world_sha256'] for r in records}) != 72:
        raise RuntimeError('Duplicate new probe recipe')
    if old_seeds.intersection(r['seed'] for r in records):
        raise RuntimeError('New probe seed overlaps inspected previous registry; preregistration correction required')
    registry = dict(schema='bc-rpi-probe-worlds-v1', worlds=records, old_sources=old_sources,
                    old_seed_count=len(old_seeds), seed_overlap=0, total_worlds=72,
                    mode_counts={'g0_q3': 24, 'g0_q4': 24, 'g1_q4': 24},
                    role='probe: diagnostic/exposed, never blind final', source_recipe_sha256=WORLD_PIN)
    private = IMPL / 'evaluator/probes_v1.json'
    if private.exists() and json.loads(private.read_text()) != registry:
        raise RuntimeError('Existing registry differs; never silently regenerate')
    atomic_json(private, registry)
    inputs = [RL / 'PROPOSAL.md', RL / 'implementation_spec.md',
        REPO / 'experiments/20260911_stage4/combination/geometry_fusions/C7_both.py',
        RL.parent / 'A2/BEST_R2.py', REPO / 'evaluation/manifest_v1.json', REPO / 'local_env.py', WORLD_SOURCE]
    registration = dict(status='registered_before_environment_calls', scope='G0/G1 only; no neural training',
        authority='User requested the original proposal agent to execute; coordinator bounded next gate to G0/G1',
        prior_registration='../execution_20260912_g0g1/REGISTRATION.md',
        business_call_limit=350000, execution_count_limit=2000,
        world_registry_sha256=sha(private), input_sha256={str(p.relative_to(REPO)): sha(p) for p in inputs},
        world_recipe=dict(g0_namespace='bc_rpi_g0_20260912_v1', g1_namespace='bc_rpi_g1_20260912_v1',
                          per_mode_worlds=24, index_range=[0,23], group='index % 12'),
        state_sampling='Up to four source READY_PREPARE indexes: floor(k*(n-1)/(m-1)), k=0..m-1, m=min(4,n); m=1 uses index0; public trajectory only',
        stop='G0 failure stops before G1; G1 completed/negative/budget-pending stops before G2',
        g0_latest_q3_compatibility='pending coordinator freeze; C7 equivalence only')
    destination = IMPL / 'execution_registration.json'
    if destination.exists() and json.loads(destination.read_text()) != registration:
        raise RuntimeError('Execution registration differs')
    atomic_json(destination, registration)
    budget = Budget()
    budget.set_phase('implementing_g0')
    print(json.dumps(dict(registration=str(destination), status_path=str(IMPL/'execution_status.json'),
        worlds=72, g0_worlds=48, g1_worlds=24, seed_overlap=0, entered=budget.data['entered']), ensure_ascii=False))


if __name__ == '__main__':
    register()
