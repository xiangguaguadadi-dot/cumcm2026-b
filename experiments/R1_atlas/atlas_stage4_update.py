#!/usr/bin/env python3
"""Read-only by default: build a separate, repeatable fourth-stage atlas increment.

Usage (also works after copying this script into the repository):
  python3 -B atlas_stage4_update.py --stage4-root /absolute/work/stage4 --dry-run
  python3 -B atlas_stage4_update.py --stage4-root /absolute/work/stage4 --write
  python3 -B atlas_stage4_update.py --repo-root /absolute/cloned/repository --write

Writes only <coordinator>/experiments/R1_atlas/stage4_increment by default.
Never imports policies, runs evaluations, rebuilds old history, changes old
nodes, edits Git, or treats saved summaries as independently recomputed rows.
The parent coordinator should run --write after current experiments finish.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re

SCHEMA = 'stage4-increment-1.0'
AGENTS = ('E1_refine', 'E2_refine', 'E3_expand')
SHORT = dict(zip(AGENTS, ('E1', 'E2', 'E3')))
# Active component parents, explicitly supplied by the coordinator. Source
# extraction from a later file does not imply activation of all embedded code.
ROOT_PARENTS = {
    'C1_combined': ['E1_R1', 'E2_r1_station_only'],
    'C2_conditional_round': ['ROOT_C1_combined', 'E2_r2_one_round'],
    'C3_entry_station': ['E1_R5', 'E2_r1_station_only'],
    'C4_entry_round': ['ROOT_C3_entry_station', 'E2_r2_one_round'],
    'C5_cells': ['ROOT_C2_conditional_round', 'E2_r3_failure_cells'],
    'C6_wedge': ['ROOT_C2_conditional_round', 'E3_R3'],
    'C7_both': ['ROOT_C2_conditional_round', 'E2_r3_failure_cells', 'E3_R3'],
}
ROOT_CONTROL_BASES = {
    'C1_gate_off': 'ROOT_C1_combined', 'C1_route_off': 'ROOT_C1_combined',
    'C2_route_off': 'ROOT_C2_conditional_round', 'C3_gate_off': 'ROOT_C3_entry_station',
    'C7_off': 'ROOT_C7_both',
}
ROOT_CONTROL_TARGETS = {
    'C1_gate_off': 'E1_R1', 'C1_route_off': 'E2_r1_station_only',
    'C2_route_off': 'E2_r2_one_round', 'C3_gate_off': 'E1_R5',
    'C7_off': 'ROOT_C2_conditional_round',
}
E1_PRIMARY = {1: 'r1_posterior', 2: 'r2_lastsource', 4: 'r4_blocks', 5: 'r5_immediate_block'}
E1_PARENTS = {1: 'S1', 2: 'E1_R1', 3: 'S1', 4: 'S1', 5: 'E1_R4'}
E1_IDEAS = {1: 'CONDITIONAL_DISCOVERY_ROUTE_PROPOSED', 3: 'JOINT_CLEAR_ROUTE_PROPOSED', 4: 'S4_E1_R3'}


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def rnd(value):
    m = re.search(r'(?:^|[_/])r(\d+)', str(value), re.I)
    return int(m.group(1)) if m else None


def stage_id(value):
    return value if value.startswith('S4_') else 'S4_' + value


class Builder:
    def __init__(self, root, out, repo=None):
        self.root, self.out = root, out
        self.coord = repo or root / 'coordinator'
        self.atlas = self.coord / 'experiments/R1_atlas'
        self.stage = self.coord / 'experiments/20260911_stage4'
        self.sources, self.blobs, self.warnings = {}, {}, []
        self.nodes, self.labels, self.hash_nodes = {}, {}, defaultdict(list)
        self.old = self.read(self.atlas / 'exploration_index.json')
        self.old_ids = {x['id'] for x in self.old['nodes']}
        self.registries = []

    def source(self, path, role='evidence'):
        p = Path(path).resolve()
        if p not in self.blobs:
            try:
                self.blobs[p] = p.read_bytes()
            except (OSError, ValueError) as exc:
                self.blobs[p] = None
                self.warnings.append({'path': str(p), 'problem': 'missing_or_unreadable', 'detail': str(exc)})
        b = self.blobs[p]
        digest = hashlib.sha256(b).hexdigest() if b is not None else None
        sid = 's4src_' + hashlib.sha256((str(p) + ':' + str(digest)).encode()).hexdigest()[:16]
        if sid not in self.sources:
            repo_rel = None
            if p.is_relative_to(self.coord):
                repo_rel = str(p.relative_to(self.coord))
            elif 'experiments' in p.parts:
                repo_rel = str(Path(*p.parts[p.parts.index('experiments'):]))
            repo_target = self.coord / repo_rel if repo_rel else None
            self.sources[sid] = dict(id=sid, absolute_path=str(p),
                stage4_relative_path=os.path.relpath(p, self.root),
                repo_relative_path=repo_rel,
                href_from_increment=os.path.relpath(repo_target, self.out) if repo_target else None,
                repository_file_available_now=repo_target.is_file() if repo_target else False,
                sha256=digest, bytes=len(b) if b is not None else None,
                exists=b is not None, roles=[])
        if role not in self.sources[sid]['roles']:
            self.sources[sid]['roles'].append(role)
        return sid

    def read(self, path, optional=False, role='structured_metadata'):
        sid = self.source(path, role)
        b = self.blobs[Path(path).resolve()]
        if b is None:
            if optional:
                return None
            raise FileNotFoundError(str(path))
        try:
            return json.loads(b)
        except (ValueError, UnicodeError) as exc:
            if not optional:
                raise
            self.warnings.append({'source': sid, 'problem': 'incomplete_or_invalid_json', 'detail': str(exc)})
            return None

    def resolve(self, raw, tree, base):
        p = Path(raw)
        if p.is_absolute():
            # Prefer merged repository files even when original sibling paths
            # still exist, so an ordinary repository clone remains sufficient.
            if 'experiments' in p.parts:
                relocated = tree.joinpath(*p.parts[p.parts.index('experiments'):])
                if relocated.exists():
                    return relocated
            return p
        return (tree / p) if p.parts and p.parts[0] == 'experiments' else (base / p)

    def agent_tree(self, owner):
        merged = self.coord / 'experiments' / owner / 'optimization_path.json'
        return self.coord if merged.exists() else self.root / owner

    def node(self, nid, owner, number=None, title=None, metadata=None, control=False):
        nid = stage_id(nid)
        if nid not in self.nodes:
            self.nodes[nid] = dict(id=nid, stage=4, direction_tags=[owner], round=number,
                round_key=f'{owner}_R{number}' if owner != 'ROOT' and number else None,
                title=title or nid, status='implemented_evidence_pending', kind='implemented_no_completed_result',
                control_or_wiring=control, parents=[], design_parent=None,
                candidates=[], effects=[], development_effects=[], control_executions=[],
                result_records=[], negative_examples=[], sources=[],
                evidence_level='saved_summary_and_live_file_identities; no policy execution or raw-metric recomputation',
                online_policy_implemented=True, unimplemented=False)
        n = self.nodes[nid]
        if metadata is not None:
            n['reported_metadata'] = metadata
            n['reported_status'] = metadata.get('status')
        return n

    def parent(self, n, parent, relationship='code_or_active_component_parent', source=None):
        pid = parent if parent in self.old_ids or parent.startswith('S4_') else stage_id(parent)
        value = dict(id=pid, relationship=relationship)
        if source:
            value['evidence_source'] = source
        if value not in n['parents']:
            n['parents'].append(value)
        if n['design_parent'] is None and relationship == 'code_or_active_component_parent':
            n['design_parent'] = pid

    def candidate(self, n, path, expected=None, config=None, name=None):
        sid = self.source(path, 'candidate_source')
        s = self.sources[sid]
        item = dict(name=name or Path(path).stem, source=sid,
            path=s['absolute_path'], sha256=s['sha256'], expected_sha256=expected,
            matches_registered_sha256=(expected == s['sha256']) if expected else None,
            deployment_config=config or {})
        if item not in n['candidates']:
            n['candidates'].append(item)
        if sid not in n['sources']:
            n['sources'].append(sid)
        if s['sha256'] and n['id'] not in self.hash_nodes[s['sha256']]:
            self.hash_nodes[s['sha256']].append(n['id'])
        if expected and expected != s['sha256']:
            self.warnings.append({'node': n['id'], 'source': sid, 'problem': 'candidate_sha_mismatch'})
        return item

    def load_baseline(self):
        p = self.stage / 'baseline/provenance.json'
        d = self.read(p)
        n = self.node('S1', 'background', title='第四阶段固定S1：Q3 R2R4 / Q4 R3R5', metadata=d)
        n.update(kind='background', status='previously_executed_control_reused', online_policy_implemented=False)
        n['sources'].append(self.source(p))
        for old, mode in [('R2_open_R4', 3), ('R3_open_R5', 4)]:
            self.parent(n, old, f'mode_{mode}_dispatch_component', self.source(p))
        for file, digest in d['files'].items():
            self.candidate(n, p.parent / file, digest)
        n['baseline_means_reported'] = d['baseline_mean_s_per_source']
        n['sources'].append(self.source(p.parent / 'expected_rows.json', 'previously_executed_baseline_rows_not_rerun'))

    def load_agents(self):
        for owner in AGENTS:
            tree = self.agent_tree(owner)
            own = tree / 'experiments' / owner
            path = own / 'optimization_path.json'
            d = self.read(path, optional=True)
            if d is None:
                continue
            sid = self.source(path)
            records = d if isinstance(d, list) else d.get('nodes', [])
            if owner == 'E1_refine':
                for r in records:
                    number = rnd(r['id'])
                    n = self.node(f'E1_R{number}', owner, number, r.get('mechanism'), r)
                    n['sources'].append(sid)
                    self.parent(n, E1_PARENTS.get(number, 'S1'), source=sid)
                    if number in E1_IDEAS:
                        self.parent(n, E1_IDEAS[number], 'mechanism_inspiration_not_whole_code_parent', sid)
                for p in sorted((own / 'research').glob('r*_candidates.json')):
                    for r in self.read(p):
                        name = r['name']
                        if name.endswith('_parent'):
                            self.labels[(owner, name)] = 'S4_S1'
                            continue
                        number = rnd(name)
                        n = self.nodes.get(f'S4_E1_R{number}') or self.node(f'E1_R{number}', owner, number)
                        self.labels[(owner, name)] = n['id']
                        self.candidate(n, self.resolve(r['file'], tree, own), r.get('sha256'), r.get('config'), name)
                        registration_source = self.source(p, 'candidate_registration')
                        if registration_source not in n['sources']:
                            n['sources'].append(registration_source)
                        if name == E1_PRIMARY.get(number):
                            n['primary_candidate_name'] = name
            elif owner == 'E2_refine':
                for r in records:
                    label = r['id']
                    control = label == 'r1_off' or 'control' in r.get('status', '')
                    n = self.node('E2_' + label, owner, rnd(label), label, r, control)
                    self.labels[(owner, label)] = n['id']
                    self.parent(n, 'S1' if r.get('parent') == 'S1' else 'E2_' + r['parent'], source=sid)
                    n['sources'].append(sid)
                    cp = self.resolve(r['candidate'], tree, own)
                    self.candidate(n, cp, r.get('sha256'), r.get('config'), label)
                    provenance = cp.with_suffix('.provenance.json')
                    if provenance.exists():
                        n['candidate_provenance'] = self.read(provenance)
                        n['sources'].append(self.source(provenance))
            else:
                for r in records:
                    number = rnd(r['id'])
                    n = self.node(f'E3_R{number}', owner, number, r.get('mechanism'), r)
                    n['sources'].append(sid)
                    parent_text = r.get('parent', '')
                    parent_id = parent_text.split(';', 1)[0].strip()
                    if parent_id:
                        self.parent(n, parent_id, source=sid)
                    if ';' in parent_text:
                        n['parent_family_note'] = parent_text.split(';', 1)[1].strip()
                    if r.get('snapshot'):
                        cp = self.resolve(r['snapshot'], tree, own)
                        self.candidate(n, cp, r.get('sha256'))
                        self.labels[(owner, cp.stem)] = n['id']
            for filename in ('report.md', 'execution_budget.json', 'best.json', 'literature.json'):
                p = own / filename
                if p.exists():
                    self.source(p, 'route_context_no_new_policy_execution')

    def load_combinations(self):
        base = self.stage / 'combination'
        pending, wiring = [], []
        for path in sorted(base.rglob('*registry.json')):
            d = self.read(path, optional=True)
            if not isinstance(d, dict):
                continue
            candidates = d.get('candidates', d)
            if not isinstance(candidates, dict):
                continue
            sid = self.source(path)
            self.registries.append(sid)
            for label, r in candidates.items():
                if not isinstance(r, dict) or not (r.get('file') or r.get('candidate')):
                    continue
                pending.append((label, r, path, sid))
            wiring.extend((pair[0], pair[1], sid) for pair in d.get('wiring_pairs', []))
            for key in ('wiring_pairs', 'hypothesis', 'selection'):
                if key in d:
                    self.sources[sid][key] = d[key]
        # Register actual active combinations before byte-identical controls,
        # irrespective of registry directory names or filesystem discovery order.
        pending.sort(key=lambda x: (x[0] not in ROOT_PARENTS, x[0]))
        for label, r, path, sid in pending:
                raw = r.get('file', r.get('candidate'))
                cp = self.resolve(raw, self.coord, base)
                if not cp.exists() and not Path(raw).is_absolute():
                    cp = self.resolve(raw, self.coord, path.parent)
                expected = r.get('sha256', r.get('candidate_sha256'))
                aliases = [x for x in self.hash_nodes.get(expected, []) if not self.nodes[x]['control_or_wiring']]
                role = r.get('role', '')
                declared_replay = 'wiring' in role or 'previous' in role or role == 'current best' or role == 'current Q4 best'
                control = label.endswith('_off') or label.endswith('_parent') or bool(aliases) or declared_replay
                n = self.node('ROOT_' + label, 'ROOT', title=label, metadata=r, control=control)
                self.labels[('ROOT', label)] = n['id']
                n['sources'].append(sid)
                if aliases:
                    n['alias_of'] = aliases[0]
                    self.parent(n, aliases[0], 'byte_identical_replay_or_wiring_control', sid)
                elif label in ROOT_CONTROL_BASES:
                    self.parent(n, ROOT_CONTROL_BASES[label], 'ablation_of_not_all_components_active', sid)
                    self.parent(n, ROOT_CONTROL_TARGETS[label], 'wiring_comparison_target_not_active_mechanism', sid)
                elif label in ROOT_PARENTS:
                    for parent in ROOT_PARENTS[label]:
                        self.parent(n, parent, source=sid)
                    n['parent_mapping_basis'] = 'Coordinator-declared active components; inactive embedded source is not counted.'
                elif r.get('parents'):
                    parents = r['parents']
                    for parent in (parents if isinstance(parents, (list, dict)) else [parents]):
                        named = self.labels.get(('ROOT', parent), stage_id(parent))
                        self.parent(n, named, source=sid)
                self.candidate(n, cp, expected, r.get('settings', r.get('config')), label)
                if control:
                    n['status'] = 'control_or_wiring_only_not_new_research_round'
        for source, target, sid in wiring:
            node_id = self.labels.get(('ROOT', source))
            target_id = self.labels.get(('ROOT', target))
            if node_id and target_id:
                target_id = self.nodes[target_id].get('alias_of', target_id)
                self.parent(self.nodes[node_id], target_id, 'wiring_comparison_target_not_active_mechanism', sid)
        for p in sorted(base.glob('build*.py')):
            self.source(p, 'combination_construction_context_not_executed')

    @staticmethod
    def effect(item, suite, mode=None):
        q = item.get('mode', mode)
        count = item.get('cases', item.get('actual_runs', item.get('runs')))
        complete = item.get('candidate_complete', item.get('complete_cases', item.get('complete')))
        explicit = item.get('valid_comparison', item.get('valid', item.get('all_clear_and_normal', item.get('all_complete'))))
        valid = explicit if isinstance(explicit, bool) else None
        if isinstance(complete, int) and not isinstance(complete, bool) and count is not None:
            valid = complete == count if valid is None else valid and complete == count
        mean = item.get('candidate_mean_s_per_source', item.get('mean_s_per_source', item.get('mean')))
        return dict(suite=item.get('suite', suite), mode=q, group=item.get('group', 'ALL'),
            cases=count, complete_cases=complete,
            error_cases=item.get('candidate_errors', item.get('error_cases')),
            source_count=item.get('source_count'),
            cleared_count=item.get('candidate_cleared', item.get('cleared_count')),
            all_clear_and_normal=valid, mean_s_per_source=mean if valid is not False else None,
            reported_mean_before_completeness_gate=mean,
            baseline_mean_s_per_source=item.get('baseline_mean_s_per_source'),
            delta_s_per_source=item.get('delta_s_per_source') if valid is not False else None,
            faster=item.get('faster'), equal=item.get('equal'), slower=item.get('slower'),
            largest_regressions=item.get('largest_regressions'),
            worst_s_per_source=item.get('worst_s_per_source'))

    def lookup(self, owner, label=None, digest=None, candidate_path=None, batch=None):
        if (owner, label) in self.labels:
            return self.nodes[self.labels[(owner, label)]]
        # Ignore replay/control aliases when matching the deployed identity.
        choices = [self.nodes[x] for x in self.hash_nodes.get(digest, [])
                   if self.nodes[x]['direction_tags'] == [owner] and not self.nodes[x]['control_or_wiring']]
        if choices:
            return choices[0]
        controls = [self.nodes[x] for x in self.hash_nodes.get(digest, [])
                    if self.nodes[x]['direction_tags'] == [owner]]
        if controls:
            return controls[0]
        if label == 'S1' or (label and label.endswith('_parent')):
            return self.nodes['S4_S1']
        if owner == 'E3_expand':
            number = rnd(Path(candidate_path).stem) if candidate_path else None
            number = number or rnd(batch)
            if number:
                return self.node(f'E3_R{number}', owner, number,
                    title=f'E3 R{number}：开发已出现，正式元数据待更新')
        if owner == 'ROOT' and label:
            return self.node('ROOT_' + label, 'ROOT', title=label)
        self.warnings.append({'owner': owner, 'label': label, 'sha256': digest,
                              'problem': 'unmatched_result_candidate_not_silently_assigned'})
        return None

    def collect_development(self, owner, tree, own):
        paths = sorted(set(own.glob('development/*/summary.json')) | set(own.glob('results/*/summary.json')) |
                       set(own.glob('development_*/summary.json')))
        for path in paths:
            data = self.read(path, optional=True)
            if data is None or (isinstance(data, dict) and ('candidate_sha256' in data or 'suite' in data)):
                continue
            entries = data if isinstance(data, list) else [dict(v, candidate=k) for k, v in data.items()
                         if isinstance(v, dict) and ('source' in v or 'groups' in v or 'comparisons_to_S1' in v)]
            if not entries or not all(isinstance(x, dict) for x in entries):
                continue
            batch = path.parent.name
            sid = self.source(path, 'development_summary_not_independent_holdout')
            controls = [x for x in entries if x.get('candidate') in ('S1', 'r1_parent', 'r3_parent')]
            reference = controls[0] if controls else next((x for x in entries if x.get('candidate') == 'E2_R2'), entries[0])
            reference_name = reference.get('candidate', 'first_reported_candidate')
            modes = None
            def effects(entry):
                nonlocal modes
                rows = entry.get('comparisons_to_S1', entry.get('groups', entry.get('modes')))
                if rows is None:
                    if modes is None:
                        cases = self.read(path.parent / 'cases.json', optional=True, role='development_case_identity')
                        modes = sorted({x['mode'] for x in cases}) if isinstance(cases, list) else []
                    return [self.effect(entry, 'development', modes[0] if len(modes) == 1 else None)]
                return [self.effect(x, 'development') for x in rows]
            reference_effects = {(x['mode'], x['group']): x for x in effects(reference)}
            for entry in entries:
                label = entry.get('candidate', entry.get('name'))
                rawcp = entry.get('source', entry.get('file'))
                cp = self.resolve(rawcp, tree, own) if rawcp else None
                digest = entry.get('sha256')
                n = self.lookup(owner, label, digest, cp, batch)
                if n is None:
                    continue
                identity = self.candidate(n, cp, digest, entry.get('config'), label) if cp else None
                ef = effects(entry)
                for x in ef:
                    control = reference_effects.get((x['mode'], x['group']))
                    if x['delta_s_per_source'] is None and control and x['all_clear_and_normal'] and control['all_clear_and_normal']:
                        if x['mean_s_per_source'] is not None and control['mean_s_per_source'] is not None:
                            x['baseline_mean_s_per_source'] = control['mean_s_per_source']
                            x['delta_s_per_source'] = x['mean_s_per_source'] - control['mean_s_per_source']
                raw = path.parent / f'{label}_rows.json'
                item = dict(batch=batch, variant=label, config=entry.get('config', {}),
                    candidate_identity=identity, comparison_reference=reference_name,
                    effects=ef, summary_source=sid, raw_rows_source=self.source(raw, 'development_rows_hashed_not_recomputed'),
                    actual_runs_reported=entry.get('actual_runs', entry.get('runs')),
                    record_role='control_replay' if n['id'] == 'S4_S1' or n['control_or_wiring'] else 'development',
                    data_role='exposed_development_not_holdout')
                key = 'control_executions' if item['record_role'] == 'control_replay' else 'development_effects'
                n[key].append(item)
                n['sources'].extend(x for x in (sid, item['raw_rows_source']) if x not in n['sources'])
                n['negative_examples'].extend(dict(batch=batch, variant=label, **x) for x in ef
                    if x['all_clear_and_normal'] is False or (x.get('delta_s_per_source') or 0) > 1e-9)

    def collect_completed_results(self, owner, tree, own):
        for path in sorted(own.glob('results/*/summary.json')):
            d = self.read(path, optional=True)
            if not isinstance(d, dict) or 'candidate_sha256' not in d:
                continue
            cp = self.resolve(d['candidate'], tree, own) if d.get('candidate') else None
            n = self.lookup(owner, digest=d['candidate_sha256'], candidate_path=cp, batch=path.parent.name)
            if n is None:
                continue
            identity = self.candidate(n, cp, d['candidate_sha256']) if cp else next(
                (x for x in n['candidates'] if x['sha256'] == d['candidate_sha256']), None)
            sid = self.source(path, 'saved_evaluation_summary')
            rawsid = self.source(path.parent / 'case_metrics.json', 'evaluation_rows_hashed_not_recomputed')
            deps = []
            for raw, expected in d.get('dependencies', {}).items():
                target = self.resolve(raw, tree, own)
                dsid = self.source(target, 'runtime_dependency')
                deps.append(dict(source=dsid, expected_sha256=expected,
                                 matches=self.sources[dsid]['sha256'] == expected))
            matches = bool(identity and identity['sha256'] == d['candidate_sha256']) and all(x['matches'] for x in deps)
            comparisons = d.get('comparisons_to_S1')
            role = 'completed_4800_exposed' if d.get('compared_cases') == 4800 and comparisons is not None else 'v1_' + d.get('suite', 'unclassified')
            ef = [self.effect(x, 'exposed') for x in comparisons] if comparisons is not None else []
            combined = [x for x in ef if x['suite'] == 'combined' and x['group'] == 'ALL']
            full_record = role == 'completed_4800_exposed' and matches and self.sources[rawsid]['exists'] and sum(x['cases'] or 0 for x in combined) == 4800
            item = dict(data_role=role, summary_source=sid, raw_rows_source=rawsid,
                candidate_identity=identity, dependencies=deps, current_deployment_identity_matches=matches,
                recorded_candidate_path=d.get('candidate'),
                saved_all_complete=d.get('all_complete'), compared_cases_reported=d.get('compared_cases', d.get('paired_cases')),
                actual_new_runs_reported=d.get('new_runs', d.get('runs')), v1_reused=d.get('v1_reused'),
                recorded_complete_4800=full_record, effects=ef,
                comparison_baseline='S1' if comparisons is not None else 'historical_v1_baseline_not_S1')
            n['result_records'].append(item)
            n['sources'].extend(x for x in (sid, rawsid) if x not in n['sources'])
            if full_record:
                n['effects'].extend(ef)
            n['negative_examples'].extend(dict(result_source=sid, **x) for x in ef
                if x['all_clear_and_normal'] is False or (x.get('delta_s_per_source') or 0) > 1e-9)

    def finish(self):
        for n in self.nodes.values():
            if n['id'] == 'S4_S1':
                continue
            full = [x for x in n['result_records'] if x['recorded_complete_4800']]
            if n['control_or_wiring']:
                n['kind'], n['status'] = 'control_or_wiring', 'not_counted_as_new_research_round'
            elif full:
                n['kind'] = 'completed_stage4_candidate'
                n['status'] = 'completed_4800_all_clear' if all(x['saved_all_complete'] is True for x in full) else 'completed_4800_with_failures'
            elif n['development_effects']:
                n['kind'], n['status'] = 'development_only', 'no_completed_4800_record_for_this_deployment'
            elif n['result_records']:
                n['kind'], n['status'] = 'partial_regression', 'quick_or_v1_only_no_completed_4800'
            n['parent_status'] = 'documented' if n['parents'] else 'pending_documentation_do_not_infer'
            if not n['parents']:
                self.warnings.append({'node': n['id'], 'problem': 'parent_documentation_pending'})
        allids = self.old_ids | set(self.nodes)
        edges = [dict(source=p['id'], target=n['id'], type=p['relationship'], evidence_source=p.get('evidence_source'))
                 for n in self.nodes.values() for p in n['parents']]
        for edge in edges:
            if edge['source'] not in allids:
                self.warnings.append({'edge': edge, 'problem': 'unresolved_parent_id'})
        research = [n for n in self.nodes.values() if n['direction_tags'][0] in AGENTS and not n['control_or_wiring']]
        full = [n for n in self.nodes.values() if n['kind'] == 'completed_stage4_candidate']
        counts = dict(legacy_nodes=len(self.old['nodes']), new_nodes=len(self.nodes),
            nodes_by_kind=dict(Counter(n['kind'] for n in self.nodes.values())),
            author_research_rounds=len({n['round_key'] for n in research if n['round_key']}),
            author_rounds_with_completed_4800=len({n['round_key'] for n in full if n['round_key']}),
            completed_4800_candidate_nodes=len(full),
            root_combination_variants=sum(n['direction_tags'] == ['ROOT'] and not n['control_or_wiring'] for n in self.nodes.values()),
            control_or_wiring_nodes=sum(n['control_or_wiring'] for n in self.nodes.values()),
            new_policy_executions_by_this_script=0)
        compact = []
        for n in self.nodes.values():
            item = {k: n[k] for k in ('id', 'kind', 'title', 'status', 'direction_tags', 'round', 'round_key', 'parents', 'design_parent', 'control_or_wiring')}
            item.update(details=f'nodes/{n["id"]}.json',
                primary_effects=[x for x in n['effects'] if x['suite'] == 'combined' and x['group'] == 'ALL'],
                development_summary=[dict(batch=x['batch'], variant=x['variant'], comparison_reference=x['comparison_reference'],
                    effects=[e for e in x['effects'] if e['group'] == 'ALL']) for x in n['development_effects']])
            compact.append(item)
        index = dict(schema_version=SCHEMA, legacy_index_source=self.source(self.atlas / 'exploration_index.json'),
            legacy_node_ids=sorted(self.old_ids), legacy_records_unchanged=True, counts=counts,
            evidence_boundary='Saved summaries are normalized and files SHA256-hashed. No old graph rebuild, Git-blob audit, raw-metric recomputation, new holdout or policy execution.',
            read_order='Read the referenced legacy index, then this increment; only current index-listed S4 nodes are active.',
            nodes=sorted(compact, key=lambda x: x['id']), edges=edges,
            source_manifest='manifest.json', warnings=self.warnings)
        current = self.stage / 'CURRENT_BEST.json'
        if current.exists():
            index['current_best_reported'] = self.read(current, role='coordinator_current_selection')
            index['current_best_source'] = self.source(current)
        return index

    def build(self):
        self.source(Path(__file__), 'increment_generator_not_a_policy')
        self.load_baseline()
        self.load_agents()
        self.load_combinations()
        for owner in AGENTS:
            tree = self.agent_tree(owner)
            own = tree / 'experiments' / owner
            self.collect_development(owner, tree, own)
            self.collect_completed_results(owner, tree, own)
        own = self.stage / 'combination'
        self.collect_development('ROOT', self.coord, own)
        self.collect_completed_results('ROOT', self.coord, own)
        return self.finish()

    def write(self, index):
        if self.out.resolve() == self.atlas.resolve() or self.out.resolve() in (self.root.resolve(), self.coord.resolve()):
            raise ValueError('Output must be a separate increment directory, not an existing atlas/worktree root')
        files = {self.out / 'index.json': dump(index)}
        files.update({self.out / 'nodes' / f'{nid}.json': dump(n) for nid, n in self.nodes.items()})
        files[self.out / 'manifest.json'] = dump(dict(schema_version=SCHEMA,
            stage4_root=str(self.root), repository_root=str(self.coord), sources=list(self.sources.values()),
            generated_node_files=[f'nodes/{nid}.json' for nid in sorted(self.nodes)],
            snapshot_semantics='File bytes captured during this run. Unfinished files remain missing/pending; rerun after closure.',
            policy_executions=0, historical_records_modified=0))
        files[self.out / 'README.md'] = (
            '# 第四阶段方向图增量\n\n'
            '先读上一级原有 exploration_index.json，再读本目录 index.json；旧节点与旧结论保留。'
            '所有新ID用S4_前缀。关闭开关、原样父法回放和接线检查不计新研究轮次。\n\n'
            'completed_stage4_candidate表示已保存4800回归记录且当前候选/依赖身份匹配；'
            '发展性变体只列development_effects，未完成部分标pending。失败和场景退步保留，'
            '未知清除数不会补成零或成功。均值来自保存的summary，脚本没有重算全量指标或运行策略。\n\n'
            'manifest.json保留每个原始文件路径、SHA256和作用。原始文件后续变化时重跑可更新此增量；'
            '只以当前index列出的节点为准，脚本不删除先前生成而本次未列出的文件。\n\n'
            '脚本移动到repo后仍可显式运行：\n\n'
            '`python3 -B atlas_stage4_update.py --repo-root /absolute/repository --write`\n\n'
            '优先使用仓库中已合并的experiments/E1_refine、E2_refine、E3_expand；'
            '显式--stage4-root时才有原并行目录作为缺失路线的备选。绝对路径保留本次来源，'
            'repo_relative_path与href_from_increment用于下载仓库后的定位。\n')
        inputs = {Path(x['absolute_path']).resolve() for x in self.sources.values()}
        if any(p.resolve() in inputs for p in files):
            raise ValueError('Refusing to overwrite an input source')
        for p, text in files.items():
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists() or p.read_text() != text:
                p.write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--stage4-root', type=Path)
    parser.add_argument('--repo-root', type=Path, help='Ordinary merged repository clone; sibling worktrees are not required')
    parser.add_argument('--out', type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--write', action='store_true')
    group.add_argument('--dry-run', action='store_true', help='Default: inspect and print plan without writing any artifact')
    args = parser.parse_args()
    if not args.stage4_root and not args.repo_root:
        parser.error('Pass --repo-root or --stage4-root')
    repo = args.repo_root.expanduser().resolve() if args.repo_root else None
    root = args.stage4_root.expanduser().resolve() if args.stage4_root else repo.parent
    coordinator = repo or root / 'coordinator'
    out = (args.out.expanduser().resolve() if args.out else coordinator / 'experiments/R1_atlas/stage4_increment')
    builder = Builder(root, out, repo=coordinator)
    index = builder.build()
    if args.write:
        builder.write(index)
    print(dump(dict(mode='write' if args.write else 'dry-run', output=str(out), counts=index['counts'],
                    sources=len(builder.sources), warnings=index['warnings'], node_ids=[n['id'] for n in index['nodes']])).strip())


if __name__ == '__main__':
    main()
