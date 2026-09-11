#!/usr/bin/env python3
"""Build the standalone RL atlas increment from completed, saved evidence.

Standard library only. No policy, environment, torch, analysis-module import,
checkpoint deserialization, old-atlas mutation, research-status mutation or Git.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys

SCHEMA = 'rl-atlas-increment-v1'
POINTS = [128, 256, 512, 1024]
ALGORITHMS = ('ppo', 'q')
C7_NODE = 'S4_ROOT_C7_both'
C7_REL = 'experiments/20260911_stage4/combination/geometry_fusions/C7_both.py'


class NotReady(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise NotReady(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def same_number(a, b):
    if a is None or b is None:
        return a is b
    return finite(a) and finite(b) and math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-8)


class Builder:
    def __init__(self, repo, execution, output):
        self.repo = Path(repo).resolve()
        self.execution = Path(execution).resolve()
        self.output = Path(output).resolve()
        self.atlas = self.repo / 'experiments/R1_atlas'
        self.sources = {}
        self.read_bytes = {}
        self.raw_rows = {}
        self.initializations = {}
        self.checkpoint_records = {}
        self.freeze_models = {}
        require(self.execution.is_relative_to(self.repo), 'Execution root must be inside the repository.')
        require(self.output.is_relative_to(self.atlas / 'rl_increment'), 'Output must stay inside R1_atlas/rl_increment; old atlas locations are not writable targets.')

    def path(self, value, base=None):
        path = Path(value)
        path = path if path.is_absolute() else (base or self.repo) / path
        path = path.resolve()
        require(path.is_relative_to(self.repo), 'Source path escapes repository: ' + str(path))
        return path

    def source(self, value, role, expected=None):
        path = self.path(value)
        require(path.is_file(), 'Required source missing: ' + str(path))
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
            'Source changed while reading: ' + str(path))
        actual = sha(data)
        if expected is not None:
            require(actual == expected, 'Source SHA differs from saved evidence: ' + str(path))
        relative = str(path.relative_to(self.repo))
        key = 'rlsrc_' + sha(relative.encode())[:16]
        if key not in self.sources:
            self.sources[key] = dict(id=key, repo_relative_path=relative,
                href_from_increment=os.path.relpath(path, self.output), sha256=actual, bytes=len(data),
                roles=[], actual_processing='read_saved_file_and_sha256; no environment/model execution')
        require(self.sources[key]['sha256'] == actual, 'Source changed during this build: ' + str(path))
        if role not in self.sources[key]['roles']:
            self.sources[key]['roles'].append(role)
        self.read_bytes[path] = actual
        return key, data

    def json(self, value, role, expected=None):
        key, data = self.source(value, role, expected)
        try:
            record = json.loads(data, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        except (ValueError, UnicodeError) as exc:
            raise NotReady('Invalid saved JSON: ' + str(value) + ': ' + str(exc)) from exc
        return key, record

    def artifact(self, value, role, expected=None):
        key, _ = self.source(value, role, expected)
        record = self.sources[key]
        return dict(source=key, path=record['repo_relative_path'], sha256=record['sha256'], bytes=record['bytes'])

    def load(self):
        required = [self.execution / name for name in ('IMPLEMENTATION.md',
            'analysis/selection_result/selection_summary.json', 'data/g2_plan.json', 'data/selection_freeze.json')]
        missing = [str(path) for path in required if not path.is_file()]
        require(not missing, 'Final inputs are not ready: ' + ', '.join(missing))
        report_path = self.execution / 'REPORT.md'
        self.report_ref = None
        self.report_artifact = dict(path=str(report_path.relative_to(self.repo)), source=None, sha256=None,
            status='pending_coordinator_report_not_required_for_this_increment')
        if report_path.is_file():
            self.report_artifact = self.artifact(report_path, 'execution_report_available_at_build_time')
            self.report_artifact['status'] = 'available_and_hashed_at_build_time'
            self.report_ref = self.report_artifact['source']
        self.builder_ref, _ = self.source(Path(__file__), 'this_read_only_increment_builder')
        self.implementation_ref, _ = self.source(self.execution / 'IMPLEMENTATION.md', 'implementation_description')
        self.proposal_ref, _ = self.source(self.repo / 'experiments/20260911_rl_research/RESEARCH_PROPOSAL.md',
            'historical_research_proposal_link_only_no_status_edit')
        self.summary_ref, self.summary = self.json(self.execution / 'analysis/selection_result/selection_summary.json', 'final_saved_selection_analysis')
        provenance = self.summary.get('provenance', {})
        self.plan_ref, self.plan = self.json(self.execution / 'data/g2_plan.json', 'registered_training_selection_plan', provenance.get('plan_sha256'))
        require(provenance.get('plan_sha256') == self.sources[self.plan_ref]['sha256'], 'Selection summary must bind the registered plan SHA.')
        require(self.path(provenance.get('plan_path', '')) == self.execution / 'data/g2_plan.json', 'Saved analysis plan path differs from this execution.')
        require(self.path(provenance.get('results_root', '')) == self.execution / 'results/g2_selection', 'Saved analysis results root differs from this execution.')
        self.analysis_ref, _ = self.source(self.execution / 'analysis/analyze_selection.py', 'saved_analysis_implementation', provenance.get('analysis_sha256'))
        self.freeze_ref, self.freeze = self.json(self.execution / 'data/selection_freeze.json', 'frozen_evaluation_models_and_worlds')
        require(self.freeze.get('plan_sha256') == self.sources[self.plan_ref]['sha256'], 'Selection freeze plan SHA differs.')
        require(self.freeze.get('selection_worlds') == self.plan.get('selection'), 'Selection freeze recipes differ from the plan.')
        self.seeds = self.plan.get('initialization_seeds', [])
        require(len(self.seeds) == len(set(self.seeds)) == 3, 'Expected three registered initializations.')
        require(all(self.plan.get(a, {}).get('checkpoint_episodes') == POINTS for a in ALGORITHMS), 'Expected four fixed checkpoint positions for both routes.')
        worlds = self.plan.get('selection', [])
        require(len(worlds) == 192 and len({w['world_id'] for w in worlds}) == 192, 'Expected 192 unique registered selection worlds.')
        require(Counter(w['mode'] for w in worlds) == {3: 96, 4: 96}, 'Expected 96 unique worlds per question.')
        self.worlds = {w['world_id']: w for w in worlds}
        require(self.summary.get('planned_model_checkpoints') == 24, 'Saved analysis must retain all 24 planned checkpoint positions.')
        boundary = self.summary.get('evidence_boundary', {})
        require(boundary.get('final_blind_validation') is False and boundary.get('official_validation') is False
            and boundary.get('default_c7_replacement_authorized') is False, 'Saved analysis evidence boundary is missing or incompatible.')
        require(self.summary.get('protocol', {}).get('mean_gate_percent') == 2.0,
            'Mean improvement threshold differs from the displayed registered 2 percent gate.')
        self.legacy_index_ref, old_index = self.json(self.atlas / 'stage4_increment/index.json', 'unchanged_stage4_increment_index')
        require(any(n.get('id') == C7_NODE for n in old_index.get('nodes', [])), 'Historical C7 parent is absent.')
        self.c7_node_ref, old_c7 = self.json(self.atlas / f'stage4_increment/nodes/{C7_NODE}.json', 'unchanged_historical_c7_parent_node')
        old_hashes = {c.get('sha256') for c in old_c7.get('candidates', []) if c.get('name') == 'C7_both'}
        require(len(old_hashes) == 1, 'Historical C7 parent has ambiguous candidate SHA.')
        self.c7_artifact = self.artifact(C7_REL, 'c7_candidate_and_candidate_execution_parent', next(iter(old_hashes)))
        for name in ('AI_README.md', 'DIRECTION_MAP.md'):
            self.source(self.atlas / name, 'preserved_atlas_entry_no_automatic_edit')
        for record in self.freeze.get('baselines', []) + self.freeze.get('models', []):
            key = record.get('model_id')
            require(key not in self.freeze_models, 'Duplicate model ID in selection freeze: ' + str(key))
            self.freeze_models[key] = record
        for seed in self.seeds:
            self.load_initialization(seed)
        self.load_parts()
        self.validate_route_choices()

    def load_initialization(self, seed):
        base = self.execution / f'results/g2/init_{seed}'
        complete_ref, complete = self.json(base / 'complete.json', 'completed_training_initialization')
        require(complete.get('seed') == seed, 'Initialization complete marker has wrong seed.')
        manifest_ref, manifest = self.json(base / 'manifest.json', 'actual_training_runtime_and_shared_demo_provenance')
        require(manifest.get('seed') == seed and manifest.get('shared_corpus') is True and manifest.get('selection_worlds_read') == 0,
            'Initialization manifest scope is incompatible.')
        require(manifest.get('plan_sha256') == self.sources[self.plan_ref]['sha256'], 'Training initialization used a different plan.')
        code_sources = []
        for file, expected in manifest.get('runtime_sha256', {}).items():
            code_sources.append(self.artifact(self.path(file, self.execution), 'actual_training_runtime_source', expected))
        require(code_sources, 'Initialization runtime source manifest is empty.')
        for key, file in [('demonstration_summary_sha256', 'results/g2_shared_demo/summary.json'),
            ('demonstration_rows_sha256', 'results/g2_shared_demo/rows.jsonl')]:
            self.source(self.execution / file, 'one_shared_512_episode_teacher_corpus', manifest.get(key))
        bc_ref, bc = self.json(base / 'bc/summary.json', 'corresponding_bc_parent_training_summary')
        require(bc.get('shared_demonstrations') == 512 and bc.get('new_episodes') == 0 and bc.get('seed') == seed,
            'BC parent does not use the one shared 512-episode corpus.')
        weight = self.artifact(base / 'bc' / bc.get('checkpoint', 'final.pt'), 'corresponding_bc_parent_weights', bc.get('sha256'))
        expected_bc = self.freeze_models.get(f'bc_init{seed}', {})
        require(expected_bc.get('checkpoint', {}).get('sha256') == weight['sha256'], 'Selected BC differs from training parent.')
        record = dict(seed=seed, complete_source=complete_ref, manifest_source=manifest_ref,
            runtime_sources=code_sources, bc_summary_source=bc_ref, bc_summary=bc,
            bc_parent_id=f'RL_BC_INIT{seed}', bc_model_id=f'bc_init{seed}', bc_weights=weight, algorithms={})
        for algorithm in ALGORITHMS:
            directory = base / algorithm
            summary_ref, summary = self.json(directory / 'summary.json', 'final_training_summary_' + algorithm)
            count, calls = summary.get('completed_training_episodes'), summary.get('business_primitives')
            require(type(count) is int and 0 <= count <= 1024 and type(calls) is int and 0 <= calls <= 1000000,
                'Training budget or completion summary is invalid.')
            require(summary.get('seed') == seed and summary.get('algorithm') == algorithm, 'Training summary identity mismatch.')
            ledger = self.artifact(directory / 'rows.jsonl', 'new_training_episode_cost_ledger_' + algorithm)
            checkpoints_ref = None
            checkpoints = []
            if (directory / 'checkpoints.json').is_file():
                checkpoints_ref, checkpoints = self.json(directory / 'checkpoints.json', 'retained_checkpoint_index_' + algorithm)
            positions = [r['episodes'] for r in checkpoints]
            require(len(positions) <= 4 and len(positions) == len(set(positions)) and set(positions) <= set(POINTS), 'Invalid retained checkpoint positions.')
            require(summary.get('checkpoint_positions') == positions, 'Training summary differs from retained checkpoint index.')
            require(all(point in positions for point in POINTS if point <= count), 'A reached checkpoint is not retained; reconcile evidence before atlas build.')
            for checkpoint in checkpoints:
                require(checkpoint.get('algorithm') == algorithm and checkpoint.get('seed') == seed, 'Checkpoint identity mismatch.')
                model_id = f"{algorithm}_init{seed}_ep{checkpoint['episodes']:04d}"
                require(self.freeze_models.get(model_id, {}).get('checkpoint') == checkpoint, 'Frozen selection model differs from retained checkpoint.')
                self.checkpoint_records[model_id] = dict(index_record=checkpoint,
                    weights=self.artifact(self.path(checkpoint['path'], self.execution), 'retained_' + algorithm + '_checkpoint_weights', checkpoint['sha256']))
            record['algorithms'][algorithm] = dict(summary_source=summary_ref, summary=summary,
                training_rows=ledger, checkpoint_index_source=checkpoints_ref, checkpoint_positions=positions)
        self.initializations[seed] = record

    def load_parts(self):
        expected = {'original_c7', 'teacher_wrapper', 'same_candidates_greedy'} | {f'bc_init{s}' for s in self.seeds}
        expected |= {f'{algorithm}_init{seed}_ep{point:04d}' for algorithm in ALGORITHMS for seed in self.seeds for point in POINTS}
        parts = self.summary.get('parts', {})
        require(set(parts) == expected, 'Saved analysis must contain exactly all baselines and 24 registered checkpoint positions.')
        for key, part in parts.items():
            category = 'models' if part.get('algorithm') in ALGORITHMS else 'baselines'
            require(part.get('category') == category and part.get('key') == key, 'Analysis part identity is inconsistent: ' + key)
            directory = self.execution / 'results/g2_selection' / category / key
            path = directory / 'rows.jsonl'
            source = part.get('input', {})
            require(self.path(source.get('path', '')) == path, 'Analysis ledger path differs: ' + key)
            if not source.get('exists'):
                reason = part.get('missing_reason', {})
                require(not path.exists() and category == 'models' and key not in self.freeze_models
                    and reason.get('status') == 'not_executed_checkpoint_unavailable',
                    'Selection result is still pending, not a completed unavailable checkpoint: ' + key)
                seed, algorithm, point = part['seed'], part['algorithm'], part['episodes']
                training = self.initializations[seed]['algorithms'][algorithm]['summary']
                require(point not in training['checkpoint_positions'] and point > training['completed_training_episodes'],
                    'Missing checkpoint is not explained by final training stop: ' + key)
                self.raw_rows[key] = []
                continue
            require(key in self.freeze_models, 'Available evaluation model is absent from freeze: ' + key)
            source_ref, data = self.source(path, 'selection_raw_metric_rows_' + key, source.get('sha256'))
            rows = []
            for line in data.decode().splitlines():
                require(bool(line.strip()), 'Blank or partial ledger line: ' + key)
                rows.append(json.loads(line))
            require(len(rows) == 192 and len({r.get('world_id') for r in rows}) == 192
                and {r.get('world_id') for r in rows} == set(self.worlds), 'Selection part is not complete: ' + key)
            summary_ref, saved = self.json(directory / 'summary.json', 'completed_selection_model_summary_' + key)
            manifest_ref, manifest = self.json(directory / 'manifest.json', 'frozen_selection_model_manifest_' + key)
            frozen = self.freeze_models[key]
            require(all(manifest.get(k) == v for k, v in frozen.items()), 'Selection manifest differs from freeze: ' + key)
            require(manifest.get('selection_freeze_sha256') == self.sources[self.freeze_ref]['sha256'], 'Selection model freeze SHA mismatch: ' + key)
            require(saved.get('episode_executions') == 192 and part.get('rows_recorded') == 192, 'Saved execution counts differ: ' + key)
            self.raw_rows[key] = rows
            part['_atlas_sources'] = dict(rows=source_ref, completed_summary=summary_ref, model_manifest=manifest_ref)
            for mode in (3, 4):
                group = [row for row in rows if row.get('mode') == mode]
                question = part['questions'][str(mode)]
                require(len(group) == 96 and question.get('collection_complete') is True,
                    'Question is incomplete or invalid in saved analysis: ' + key)
                require(all(row.get('mode') == self.worlds[row['world_id']]['mode']
                    and row.get('group') == self.worlds[row['world_id']]['group'] for row in group), 'Recipe metadata differs: ' + key)
                failures = [row for row in group if row.get('success') is not True or row.get('cleared') != row.get('n') or row.get('error')]
                require({r['world_id'] for r in question.get('failed_rows', [])} == {r['world_id'] for r in failures}, 'Saved failure rows differ: ' + key)
                require(question.get('eligible_for_selection') == (not failures), 'Completion gate differs: ' + key)
                for row in group:
                    n, cleared, total = row.get('n'), row.get('cleared'), row.get('virtual_time_s')
                    require(type(n) is int and 10 <= n <= 16 and type(cleared) is int and 0 <= cleared <= n and finite(total) and total >= 0,
                        'Invalid source denominator or time in saved row: ' + key)
                    require(same_number(row.get('average_s'), total / cleared if cleared else None), 'Saved per-source time disagrees with raw row: ' + key)
                mean = math.fsum(row['average_s'] for row in group) / 96 if not failures else None
                require(same_number(question.get('mean_seconds_per_source'), mean), 'Saved checkpoint mean disagrees with raw metric rows: ' + key)
        # All completed, available models must be represented by retained files.
        require(set(self.freeze_models) == {key for key, rows in self.raw_rows.items() if rows}, 'Frozen model set and completed selection rows differ.')

    def validate_route_choices(self):
        for algorithm in ALGORITHMS:
            modes = self.summary.get('algorithms', {}).get(algorithm, {})
            require(set(modes) == {'3', '4'}, 'Route question summary missing: ' + algorithm)
            for mode in (3, 4):
                result = modes[str(mode)]
                choices = result.get('initialization_choices', {})
                require(set(choices) == {str(seed) for seed in self.seeds}, 'Initialization choice records are incomplete.')
                for seed in self.seeds:
                    choice = choices[str(seed)]
                    candidates = [f'{algorithm}_init{seed}_ep{point:04d}' for point in POINTS]
                    eligible = [key for key in candidates if self.summary['parts'][key]['questions'][str(mode)]['eligible_for_selection']]
                    expected = min(eligible, key=lambda key: self.summary['parts'][key]['questions'][str(mode)]['mean_seconds_per_source']) if eligible else None
                    require(choice.get('selected_part') == expected, 'Saved checkpoint choice violates the registered complete-checkpoint minimum rule.')
                checks = result.get('promotion_checks', {})
                required_checks = [value for key, value in checks.items() if key != 'initializations_improving_both_baselines']
                require(required_checks and all(type(value) is bool for value in required_checks), 'Promotion checks are not explicit booleans.')
                require(result.get('meets_preregistered_selection_gate') == all(required_checks), 'Saved route gate differs from its component checks.')
                if result.get('aggregate'):
                    aggregate = result['aggregate']
                    require(aggregate.get('independent_worlds') == 96 and aggregate.get('initializations') == 3
                        and aggregate.get('initialization_evaluations') == 288
                        and aggregate.get('candidate_and_bc_averaged_within_each_world_before_bootstrap') is True,
                        'Cross-initialization denominator is not the registered 96 paired worlds.')

    def checkpoint_node(self, algorithm, seed, point):
        key = f'{algorithm}_init{seed}_ep{point:04d}'
        part = self.summary['parts'][key]
        checkpoint = self.checkpoint_records.get(key)
        questions = {}
        for mode in (3, 4):
            question = part['questions'][str(mode)]
            route = self.summary['algorithms'][algorithm][str(mode)]
            chosen = route['initialization_choices'][str(seed)]
            selected = chosen['selected_part'] == key
            questions[str(mode)] = dict(
                status=question['status'], recorded_mean_seconds_per_source=question['mean_seconds_per_source'],
                expected_worlds=question['expected_rows'], observed_unique_worlds=question['unique_expected_worlds'],
                successful_worlds=question['successful_worlds'], failed_worlds=len(question['failed_rows']),
                failures=question['failed_rows'], missing_world_ids=question['missing_world_ids'],
                invalid_rows=question['invalid_rows'], duplicate_world_ids=question['duplicate_world_ids'],
                fallback_worlds=question['fallback_worlds'], clear_fraction=question['clear_fraction'],
                completion_gate_passed=question['eligible_for_selection'], selected_for_this_question=selected,
                selected_checkpoint_comparisons=chosen.get('comparisons') if selected else None,
                selected_route_gate_reference=dict(algorithm=algorithm, question=mode,
                    meets_preregistered_selection_gate=route['meets_preregistered_selection_gate'],
                    applies_to='Three selected initialization checkpoints jointly, not this checkpoint in isolation'),
                groups=question['groups'])
        return dict(model_id=key, initialization_seed=seed, training_episode_position=point,
            kind='registered_training_checkpoint_not_optimization_round',
            parents=[dict(id=C7_NODE, relationship='shared_candidate_and_execution_component_parent', source=self.c7_node_ref),
                dict(id=f'RL_BC_INIT{seed}', relationship='corresponding_initial_parameters_and_bc_comparator')],
            weights=checkpoint['weights'] if checkpoint else None,
            checkpoint_index_record=checkpoint['index_record'] if checkpoint else None,
            availability='retained_and_evaluated' if checkpoint else 'not_reached_before_final_training_stop',
            missing_reason=part.get('missing_reason'), questions=questions,
            saved_selection_sources=part.get('_atlas_sources'), recorded_evaluation_cost=part['recorded_cost'],
            analysis_json_pointer=f'/parts/{key}')

    def route_node(self, algorithm):
        descriptions = {
            'ppo': '共同C7候选和执行器上的BC初始化、完整episode Monte Carlo PPO调度。',
            'q': '共同C7候选和执行器上的BC支持约束Q调度；共享示范MC初始化后，使用自身训练轨迹作TD更新。'}
        checkpoints = [self.checkpoint_node(algorithm, seed, point) for seed in self.seeds for point in POINTS]
        modes = self.summary['algorithms'][algorithm]
        return dict(id='RL_' + algorithm.upper(), schema_version=SCHEMA,
            title=algorithm.upper() + '：C7候选上的学习调度', kind='rl_route_training_and_checkpoint_selection',
            status='completed_saved_selection_evidence', description=descriptions[algorithm],
            parents=[dict(id=C7_NODE, relationship='shared_candidate_and_execution_component_parent', source=self.c7_node_ref)] +
                [dict(id=f'RL_BC_INIT{seed}', initialization_seed=seed,
                    relationship='corresponding_bc_initial_parameters_and_comparator') for seed in self.seeds],
            round=None, optimization_round_count=None,
            count_semantics='One learning route, three independent training initializations and four registered checkpoint positions each; 12 checkpoint positions are not 12 optimization rounds.',
            initialization_seeds=self.seeds, registered_checkpoint_positions=POINTS,
            actual_retained_checkpoints=sum(c['weights'] is not None for c in checkpoints),
            training=[dict(seed=seed, **self.initializations[seed]['algorithms'][algorithm]) for seed in self.seeds],
            runtime_sources_by_initialization={str(seed): self.initializations[seed]['runtime_sources'] for seed in self.seeds},
            c7_candidate=self.c7_artifact, checkpoints=checkpoints,
            question_outcomes={mode: dict(**result, saved_analysis_json_pointer=f'/algorithms/{algorithm}/{mode}')
                for mode, result in modes.items()},
            evidence=dict(selection_summary=self.summary_ref, execution_report=self.report_artifact,
                implementation=self.implementation_ref, registered_plan=self.plan_ref, selection_freeze=self.freeze_ref,
                independent_worlds_total=192, independent_worlds_per_question=96,
                new_environment_executions_by_builder=0, raw_metric_means_recomputed=True,
                bootstrap_recomputed=False, source_archive_bodies_reopened=False,
                checkpoint_tensors_deserialized=False, final_blind_validation=False, official_validation=False),
            literature_relationship=dict(research_proposal=self.proposal_ref,
                original_review_status_preserved=True, new_paper_adoption_claims=[],
                note='Document-level link only. This increment does not infer that any of the 41 reviewed papers was implemented or adopted.'),
            failure_policy='All registered checkpoints, failed rows and unavailable positions remain listed. A failed/incomplete checkpoint has null ranked mean; no successful-only average is substituted.')

    def artifacts(self):
        route_nodes = [self.route_node(algorithm) for algorithm in ALGORITHMS]
        bc_parents = []
        for seed in self.seeds:
            record = self.initializations[seed]
            bc_part = self.summary['parts'][record['bc_model_id']]
            bc_parents.append(dict(id=record['bc_parent_id'], kind='supporting_behavior_clone_parent_not_new_rl_route',
                initialization_seed=seed, model_id=record['bc_model_id'],
                parents=[dict(id=C7_NODE, relationship='teacher_demonstration_source', source=self.c7_node_ref)],
                shared_demonstration_episodes=512, training_summary=record['bc_summary'],
                training_summary_source=record['bc_summary_source'], weights=record['bc_weights'],
                selection_questions=bc_part['questions'], selection_sources=bc_part['_atlas_sources']))
        edges = [dict(source=C7_NODE, target=record['id'], relationship='teacher_demonstration_source') for record in bc_parents]
        for node in route_nodes:
            edges.extend(dict(source=parent['id'], target=node['id'], relationship=parent['relationship']) for parent in node['parents'])
        sources = [self.sources[key] for key in sorted(self.sources)]
        index = dict(schema_version=SCHEMA, built_utc=datetime.now(timezone.utc).isoformat(), generation_complete=True,
            legacy=dict(stage4_index_source=self.legacy_index_ref, c7_parent_node=C7_NODE,
                legacy_nodes_unchanged=True, old_readmes_and_direction_maps_unchanged=True),
            counts=dict(new_learning_routes=2, supporting_bc_parents=3, initializations_per_route=3,
                planned_checkpoints_per_initialization=4, planned_model_checkpoint_positions=24,
                actual_retained_and_evaluated_model_checkpoints=len(self.checkpoint_records),
                registered_unique_selection_worlds=192, unique_selection_worlds_per_question=96,
                actual_saved_selection_episode_rows=self.summary['recorded_evaluation_cost']['episode_rows'],
                new_world_executions_by_builder=0, new_optimization_round_count=None),
            count_semantics='24 = 2 routes × 3 initializations × 4 registered training positions. It is not 24 optimization rounds, research rounds, independent training runs or independent validation populations.',
            read_order='Read unchanged stage4_increment/index.json for C7 history, then this index and the two route detail files.',
            nodes=[dict(id=node['id'], title=node['title'], kind=node['kind'], status=node['status'],
                details=f"nodes/{node['id']}.json", parents=node['parents'],
                question_gates={mode: result['meets_preregistered_selection_gate'] for mode, result in node['question_outcomes'].items()},
                selected_checkpoints={mode: {seed: choice['selected_episode_count'] for seed, choice in result['initialization_choices'].items()}
                    for mode, result in node['question_outcomes'].items()}) for node in route_nodes],
            supporting_parents=bc_parents, edges=edges, source_manifest='source_manifest.json',
            evidence_boundary=self.summary['evidence_boundary'], recorded_selection_cost=self.summary['recorded_evaluation_cost'],
            links=dict(execution_report=self.report_artifact, implementation=self.implementation_ref,
                research_proposal=self.proposal_ref, selection_summary=self.summary_ref),
            builder_source=self.builder_ref,
            literature_review_status_unchanged=True, new_paper_adoption_claims=[],
            gate_scope='Per question, aggregate the three selected initialization checkpoints by world before inference; checkpoint completion gates are separate from the joint route promotion gate.')
        return {'index.json': index, 'source_manifest.json': dict(schema_version=SCHEMA, files=sources,
            processing='Saved JSON/rows normalized, means/failures cross-checked, sources/weights SHA256 hashed; no model execution or bootstrap recomputation.'),
            **{f"nodes/{node['id']}.json": node for node in route_nodes}, 'README.md': self.readme(index, route_nodes)}

    def link(self, source, label):
        if source is None:
            return '本轮主报告由协调者随后写入；本增量未绑定其内容散列'
        return f"[{label}](<{self.sources[source]['href_from_increment']}>)"

    def readme(self, index, nodes):
        def number(value):
            return '—' if value is None else f'{value:.3f}'
        lines = ['# RL 学习路线增量', '',
            '本增量只追加 PPO、Q 两条学习路线及三份对应 BC 父模型。第四阶段及更早节点、原图和原研究审阅状态保持不变。', '',
            '**24 个 checkpoint 位置 = 2 条路线 × 3 次初始化 × 4 个训练位置，不是 24 轮优化。** 每题独立选择场景为 96 个；同一 world 的三次初始化结果先在 world 内合并，不增加独立样本数。', '',
            '先读 [index.json](index.json)，再读 [PPO 节点](nodes/RL_PPO.json) 或 [Q 节点](nodes/RL_Q.json)。C7 父节点来自未修改的 ' + self.link(self.c7_node_ref, C7_NODE) + '。', '',
            self.link(self.report_ref, '本轮最终报告') + ' · ' + self.link(self.implementation_ref, '共同实现说明') + ' · ' +
            self.link(self.summary_ref, '完整选择分析') + ' · ' + self.link(self.proposal_ref, '原研究审阅稿'), '',
            '## 逐题选择门槛', '', '| 路线 | 题 | 达到登记门槛 | 同时优于 C7 与自身 BC 的初始化 | 相对 C7 | 相对 BC |',
            '|---|---:|---|---:|---:|---:|']
        for node in nodes:
            for mode, result in node['question_outcomes'].items():
                comparisons = (result.get('aggregate') or {}).get('comparisons', {})
                c7 = comparisons.get('original_c7', {}).get('improvement_percent')
                bc = comparisons.get('corresponding_bc', {}).get('improvement_percent')
                lines.append(f"| {node['id'][3:]} | {mode} | {'是' if result['meets_preregistered_selection_gate'] else '否'} | {result['promotion_checks']['initializations_improving_both_baselines']}/3 | {number(c7)}% | {number(bc)}% |")
        lines += ['', '门槛针对每题选出的三份初始化模型：全清、相对 C7 和对应 BC 的均值各改善至少 2%、两项配对差值 95% 区间上界小于 0、至少 2/3 初始化同时改善。不是每一个 checkpoint 的独立晋级结论。完整布尔条件和区间来自已保存分析，节点保留全部值。', '',
            '## 全部登记 checkpoint', '',
            '| 路线 | 初始化 | 训练局位置 | Q3 秒/源 | Q3 失败/缺失 | Q4 秒/源 | Q4 失败/缺失 | 被选用于题 |',
            '|---|---:|---:|---:|---|---:|---|---|']
        for node in nodes:
            for cp in node['checkpoints']:
                a, b = cp['questions']['3'], cp['questions']['4']
                failures = lambda q: f"{q['failed_worlds']}/{len(q['missing_world_ids'])}"
                selected = ', '.join(mode for mode, q in cp['questions'].items() if q['selected_for_this_question']) or '—'
                lines.append(f"| {node['id'][3:]} | {cp['initialization_seed']} | {cp['training_episode_position']} | {number(a['recorded_mean_seconds_per_source'])} | {failures(a)} | {number(b['recorded_mean_seconds_per_source'])} | {failures(b)} | {selected} |")
        lines += ['', '失败/缺失为 world 数。均值缺失保持为“—”；未达到的训练位置仍列出原因，不填入推测成绩，不使用成功子集替代失败 checkpoint 的结果。每个初始化 checkpoint 的参数父是同一初始化的 BC；C7 提供候选与执行组件，不能声称网络从零发现完整策略。', '',
            '## 可复核范围', '',
            '- 来源、权重、逐局结果路径和 SHA256 见 [source_manifest.json](source_manifest.json)；节点引用对应 source ID。权重只做文件散列核验，不反序列化。',
            '- 此构建读取保存的选择逐局行，核对每题 96 个 ID、失败、分母与均值；沿用已保存的 checkpoint 选择和区间，不重新运行策略或 bootstrap。',
            '- 选择集已用于挑 checkpoint，区间仍受选择和多重比较影响；这不是 blind final 或官方测试，也不构成自动替换 C7 的授权。',
            '- 原 41 篇文献的阅读/审阅/修订状态不回写。本增量只链接研究和实现文档，不自动指派论文采纳关系。',
            '- 构建不改 AI_README.md、DIRECTION_MAP.md、旧图或旧节点；入口顶部链接由协调者在最终资料齐备后另行添加。', '',
            f"本次保存的选择执行行数为 {index['counts']['actual_saved_selection_episode_rows']}，不同选择 world 仍为 192；构建脚本新增环境执行为 0。", '']
        return '\n'.join(lines)

    def unchanged(self):
        for path, expected in self.read_bytes.items():
            require(path.is_file() and sha(path.read_bytes()) == expected, 'Input changed before output sealing: ' + str(path))

    def write(self, artifacts):
        for name in artifacts:
            require(not (self.output / name).exists(), 'Refusing to overwrite an existing increment artifact: ' + str(self.output / name))
        self.unchanged()
        self.output.mkdir(parents=True, exist_ok=True)
        # Index is written last and is the completion marker. The builder only
        # creates the explicitly listed files inside the independent increment.
        names = [name for name in artifacts if name != 'index.json'] + ['index.json']
        for name in names:
            path = self.output / name
            path.parent.mkdir(parents=True, exist_ok=True)
            value = artifacts[name]
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
            with path.open('x', encoding='utf-8') as stream:
                stream.write(text)
        return {name: sha((self.output / name).read_bytes()) for name in names}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--execution-root', type=Path)
    parser.add_argument('--out', type=Path, help='Must be inside experiments/R1_atlas/rl_increment; defaults to that directory.')
    parser.add_argument('--write', action='store_true', help='Generate the increment only after all final input checks pass.')
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    execution = args.execution_root or repo / 'experiments/20260911_rl_execution'
    output = args.out or repo / 'experiments/R1_atlas/rl_increment'
    try:
        builder = Builder(repo, execution, output)
        builder.load()
        artifacts = builder.artifacts()
        builder.unchanged()
        hashes = builder.write(artifacts) if args.write else None
        print(json.dumps(dict(status='written' if args.write else 'ready_no_outputs_written',
            output=str(output.resolve()), files=hashes, routes=2,
            planned_checkpoint_positions=24, actual_checkpoint_weights=len(builder.checkpoint_records),
            actual_new_world_executions=0, old_atlas_modified=False, research_review_status_modified=False), ensure_ascii=False))
        return 0
    except (NotReady, OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        print(json.dumps(dict(status='not_ready_or_inconsistent', reason=str(exc),
            actual_new_world_executions=0, note='No final increment should be claimed until this check passes.'), ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
