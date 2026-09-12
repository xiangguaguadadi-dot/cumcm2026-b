#!/usr/bin/env python3
"""Read-only first-round checkpoint/gradient-ledger validation, no optimizer runs.

Uses only the accepted pure model for frozen forward passes. Independently
recomputes nested world/state/action Huber losses and checkpoint selection.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

from audit_rl_execution import read_json, require, sha256

SEEDS = (912101, 912102, 912103)
TENSOR_KEYS = {'global_features', 'channels', 'active_events', 'active_mask', 'polygon', 'actions'}


def tensor_digest(state):
    h = hashlib.sha256()
    for name, value in sorted(state.items()):
        h.update(name.encode())
        h.update(value.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def audit_update_order(journal, fit_ids):
    expected = set(fit_ids)
    require(len(expected) == 24, 'Wrong fit-world population')
    findings = {}
    for seed in SEEDS:
        rows = [r for r in journal if r['seed'] == seed]
        starts = [r for r in rows if r['event'] == 'fit_start']
        finishes = [r for r in rows if r['event'] == 'fit_finish']
        updates = [r for r in rows if r['event'] == 'optimizer_update']
        checkpoints = [r for r in rows if r['event'] == 'checkpoint_saved']
        require(len(starts) == len(finishes) == 1 and rows[0] == starts[0] and rows[-1] == finishes[0],
                'Incomplete or duplicated fit lifecycle')
        require(starts[0]['epochs'] == 20 and starts[0]['expected_updates'] == 60
                and starts[0]['fit_worlds'] == 24 and starts[0]['fit_val_worlds'] == 12, 'Fit registration changed')
        require(finishes[0]['status'] == 'complete' and finishes[0]['updates'] == 60, 'Fit did not finish 60 updates')
        require([r['update'] for r in updates] == list(range(1, 61)), 'Missing/repeated optimizer update')
        require([r['epoch'] for r in checkpoints] == [5, 10, 20], 'Unregistered checkpoint selection pool')
        expected_events = ['fit_start']
        for update in range(1, 61):
            expected_events.append('optimizer_update')
            if update in (15, 30, 60): expected_events.append('checkpoint_saved')
        expected_events.append('fit_finish')
        require([r['event'] for r in rows] == expected_events, 'Checkpoint is not recorded immediately after its fitted updates')
        require(all(r['epoch'] == (r['update'] - 1) // 3 + 1 for r in updates), 'Epoch/update chronology changed')
        for epoch in range(1, 21):
            epoch_rows = [r for r in updates if r['epoch'] == epoch]
            require(len(epoch_rows) == 3 and all(r['batch_worlds'] == 8 and len(r['fit_world_ids']) == 8
                    for r in epoch_rows), 'Wrong complete-world minibatch schedule')
            ids = [world for r in epoch_rows for world in r['fit_world_ids']]
            require(len(ids) == 24 and set(ids) == expected, 'Fit_val leakage, repeated or dropped fit world')
            for r in epoch_rows:
                require(math.isfinite(r['loss']) and r['loss'] >= 0
                        and math.isfinite(r['gradient_norm_before_clip']) and r['gradient_norm_before_clip'] >= 0,
                        'Invalid actual loss/gradient record')
        findings[seed] = dict(start=starts[0], finish=finishes[0], checkpoints=checkpoints, updates=60)
    require(set(r['seed'] for r in journal) == set(SEEDS), 'Unregistered fitted initialization')
    require([r['seed'] for r in journal] == [seed for seed in SEEDS for _ in range(65)],
            'Initialization lifecycles interleaved or reordered')
    require(all(r['event'] in {'fit_start', 'fit_finish', 'optimizer_update', 'checkpoint_saved'} for r in journal),
            'Unknown fit-journal record')
    return findings


def nested_huber(torch, model, worlds):
    """A world contributes even when empty; teacher-only states contribute zero."""
    world_rows = []
    with torch.no_grad():
        for world in worlds:
            state_losses = []
            state_rows = []
            for state in world['states']:
                raw = state['snapshot']['features']
                require(set(raw) == TENSOR_KEYS, 'Unknown raw tensor feature')
                tensors = {k: torch.tensor(v, dtype=torch.bool if k == 'active_mask' else torch.float32)
                           for k, v in raw.items()}
                scores = model(tensors)
                targets = torch.tensor(state['targets_normalized'], dtype=torch.float32)
                teacher = state['teacher_index']
                require(targets.shape == scores.shape and targets[teacher].item() == 0, 'Wrong target/reference binding')
                difference = scores - scores[teacher]
                mask = torch.arange(len(scores)) != teacher
                if len(scores) == 1:
                    loss = 0.0
                else:
                    # A separate built-in Huber implementation, not fit.state_loss.
                    z = (difference[mask] - targets[mask]) / 0.002
                    loss = float(torch.nn.functional.smooth_l1_loss(z, torch.zeros_like(z), beta=1., reduction='mean'))
                require(math.isfinite(loss), 'Nonfinite reconstructed loss')
                state_losses.append(loss)
                state_rows.append(dict(state_index=state['state_index'], candidate_ids=state['snapshot']['candidate_ids'],
                    teacher_index=teacher, raw_scores=scores.tolist(), predicted_gains=difference.tolist(), loss=loss))
            # Match the registered float32 nested reduction, not a float64
            # averaging convention that could change a nearly tied epoch.
            mean = float(torch.tensor(state_losses, dtype=torch.float32).mean()) if state_losses else 0.
            world_rows.append(dict(world_id=world['world_id'], role=world['role'], loss=mean, states=state_rows))
    return float(torch.tensor([row['loss'] for row in world_rows], dtype=torch.float32).mean()), world_rows


def audit(campaign, dataset, fit_directory):
    campaign, dataset, fit_directory = (Path(p).resolve() for p in (campaign, dataset, fit_directory))
    require(dataset.is_relative_to(campaign) and fit_directory.is_relative_to(campaign), 'Evidence outside new round')
    runtime_site = Path('/Users/t/Documents/Codex/2026-09-10/new-chat/work/rl_execution_runtime/venv/lib/python3.12/site-packages')
    require(sys.flags.no_site and sys.version_info[:2] == (3, 12), 'Use pinned Python 3.12 -S -B')
    sys.path.append(str(runtime_site))
    import torch
    require(torch.__version__ == '2.8.0', 'Torch version changed')
    torch.set_num_threads(1)
    sys.path.insert(0, str(campaign.parent))
    from training_round1_20260912.model import CounterfactualModel
    sources = {}

    def read(path):
        sources[str(path)] = sha256(path)
        return read_json(path)

    manifest = read(dataset / 'manifest.json')
    dataset_sha = sources[str(dataset / 'manifest.json')]
    roles = {'fit': [], 'fit_val': []}
    for row in manifest['worlds']:
        require(row['role'] in roles, 'Held-out development/calibration in training export')
        path = (dataset / row['path']).resolve()
        require(path.parent == dataset and sha256(path) == row['sha256'], 'Public dataset identity changed')
        roles[row['role']].append(read(path))
    require({k:len(v) for k,v in roles.items()} == {'fit':24, 'fit_val':12}, 'Wrong fit/validation role counts')
    require(len({w['world_id'] for role in roles.values() for w in role}) == 36, 'Fit/validation world overlap')
    fit_summary = read(fit_directory / 'summary.json')
    require(fit_summary['status'] == 'three_seed_fit_complete_not_calibrated'
            and fit_summary['completed_seeds'] == list(SEEDS) and fit_summary['optimizer_updates'] == 180,
            'Three-seed fit is not complete')
    journal_path = fit_directory / 'fit_journal.jsonl'
    sources[str(journal_path)] = sha256(journal_path)
    journal = [json.loads(line) for line in journal_path.read_text().splitlines() if line.strip()]
    orders = audit_update_order(journal, [w['world_id'] for w in roles['fit']])
    read_log = read(fit_directory / 'read_log.json')
    expected_paths = {str(dataset/'manifest.json')} | {str((dataset/r['path']).resolve()) for r in manifest['worlds']}
    require(set(read_log['opened_dataset_files']) == expected_paths and read_log['allowed_roles'] == ['fit','fit_val']
            and read_log['world_truth_loaded'] is False and read_log['dataset_manifest_sha256'] == dataset_sha,
            'Declared dataset read boundary differs')
    model_path = campaign / 'model.py'
    sources[str(model_path)] = sha256(model_path)
    results, initial_digests = [], set()
    for seed in SEEDS:
        reported = read(fit_directory / f'seed_{seed}_result.json')
        require(reported['seed'] == seed and reported['status'] == 'complete' and reported['updates'] == 60
                and reported['epochs'] == 20 and len(reported['checkpoints']) == 3
                and [r['epoch'] for r in reported['checkpoints']] == [5, 10, 20],
                'Reported checkpoint pool is not exactly the three registered epochs')
        initial_path = fit_directory / f'initial_{seed}.pt'
        sources[str(initial_path)] = sha256(initial_path)
        initial = torch.load(initial_path, map_location='cpu', weights_only=True)
        require(initial['seed'] == seed, 'Initial checkpoint belongs to another seed')
        initial_state = initial['model_state_dict']
        initial_digest = tensor_digest(initial_state)
        require(initial_digest == initial['parameter_sha256'] == reported['initial_parameter_sha256']
                == orders[seed]['start']['initial_parameter_sha256'], 'Initial parameter identity mismatch')
        require(initial_digest not in initial_digests, 'Three claimed initializations reuse the same initial tensors')
        initial_digests.add(initial_digest)
        torch.manual_seed(seed)
        reconstructed_initial = CounterfactualModel()
        require(tensor_digest(reconstructed_initial.state_dict()) == initial_digest,
                'Saved initial tensors do not match the registered initialization seed')
        require(initial['dataset_manifest_sha256'] == dataset_sha == orders[seed]['start']['dataset_manifest_sha256'],
                'Training used another dataset manifest')
        evaluations = []
        for row, journal_row in zip(reported['checkpoints'], orders[seed]['checkpoints']):
            path = fit_directory / row['path']
            require(path.parent == fit_directory and sha256(path) == row['sha256'] == journal_row['sha256'], 'Checkpoint bytes changed')
            sources[str(path)] = sha256(path)
            ck = torch.load(path, map_location='cpu', weights_only=True)
            require(ck['seed'] == seed and ck['epoch'] == row['epoch'] == journal_row['epoch']
                    and ck['updates'] == 3*ck['epoch'] == row['updates'] == journal_row['updates'], 'Checkpoint step/epoch mismatch')
            require(ck['dataset_manifest_sha256'] == dataset_sha and ck['loss_scale'] == .002
                    and ck['ranking_weight'] == 0 and ck['parameter_count'] == 61121, 'Checkpoint training specification changed')
            model = CounterfactualModel()
            model.load_state_dict(ck['model_state_dict'], strict=True)
            model.eval()
            require(sum(p.numel() for p in model.parameters()) == 61121
                    and all(torch.isfinite(p).all() for p in model.parameters()), 'Invalid fitted tensors')
            state_hash = tensor_digest(ck['model_state_dict'])
            require(state_hash == ck['parameter_sha256'] == row['parameter_sha256'] == journal_row['parameter_sha256']
                    and state_hash != initial_digest, 'Checkpoint claimed updates without changed parameter bytes')
            optimizer = ck['optimizer_state_dict']
            require(len(optimizer['param_groups']) == 1 and optimizer['param_groups'][0]['lr'] == 3e-4
                    and optimizer['param_groups'][0]['weight_decay'] == 1e-5, 'Actual Adam settings differ')
            parameter_ids = optimizer['param_groups'][0]['params']
            parameters = list(model.parameters())
            require(len(parameter_ids) == len(parameters) == len(set(parameter_ids))
                    and set(optimizer['state']) == set(parameter_ids), 'Adam state omits or repeats parameter tensors')
            for parameter_id, parameter in zip(parameter_ids, parameters):
                moment = optimizer['state'][parameter_id]
                require(all(moment[key].shape == parameter.shape and moment[key].dtype == parameter.dtype
                            for key in ('exp_avg', 'exp_avg_sq')), 'Adam moment shape/dtype differs from corresponding parameter')
            steps = [float(value['step']) for value in optimizer['state'].values()]
            require(steps and all(step == ck['updates'] for step in steps), 'Optimizer moment step counter mismatch')
            require(all(torch.isfinite(value[k]).all() for value in optimizer['state'].values()
                        for k in ('exp_avg','exp_avg_sq')), 'Nonfinite Adam moments')
            val_loss, val_rows = nested_huber(torch, model, roles['fit_val'])
            tolerance = 2e-5 * max(1., abs(val_loss))
            require(abs(val_loss - row['fit_val_world_equal_loss']) <= tolerance
                    and abs(val_loss - ck['fit_val_world_equal_loss']) <= tolerance,
                    'Stored fit_val loss differs from independently recomputed complete-world loss')
            prediction_path = fit_directory / row['validation_predictions_path']
            require(prediction_path.parent == fit_directory and sha256(prediction_path) == row['validation_predictions_sha256'],
                    'Validation forward-record bytes changed')
            predictions = read(prediction_path)
            require(predictions['seed'] == seed and predictions['epoch'] == ck['epoch']
                    and predictions['parameter_sha256'] == state_hash and predictions['dataset_manifest_sha256'] == dataset_sha
                    and predictions['selection_role'] == 'fit_val_only' and predictions['no_gradient'] is True,
                    'Validation prediction identity mismatch')
            require(len(predictions['worlds']) == len(val_rows) == 12, 'Validation world forward record omitted')
            for declared, recomputed in zip(predictions['worlds'], val_rows):
                require(declared['world_id'] == recomputed['world_id'] and declared['role'] == 'fit_val'
                        and len(declared['states']) == len(recomputed['states']), 'Validation prediction world/state misalignment')
                for stored, observed in zip(declared['states'], recomputed['states']):
                    require(stored['candidate_ids'] == observed['candidate_ids']
                            and stored['teacher_index'] == observed['teacher_index']
                            and stored['raw_scores_float32'] == observed['raw_scores']
                            and stored['paired_gains_float32'] == observed['predicted_gains'],
                            'Saved checkpoint scores differ from frozen forward pass')
            changes = sum(not torch.equal(value, initial_state[name]) for name, value in ck['model_state_dict'].items())
            evaluations.append(dict(epoch=ck['epoch'], updates=ck['updates'], checkpoint_sha256=row['sha256'],
                parameter_sha256=state_hash, parameter_tensors_changed=changes,
                independently_recomputed_fit_val_loss=val_loss, saved_fit_val_loss=row['fit_val_world_equal_loss'],
                numerical_tolerance=tolerance, fit_val_world_rows=val_rows))
        selected = min(reported['checkpoints'], key=lambda r:(r['fit_val_world_equal_loss'],r['epoch']))
        independently_selected = min(evaluations, key=lambda r:(r['independently_recomputed_fit_val_loss'],r['epoch']))
        require(reported['selected'] == selected and orders[seed]['finish']['selected_epoch'] == selected['epoch']
                and orders[seed]['finish']['selected_checkpoint_sha256'] == selected['sha256'], 'Checkpoint selected using another rule')
        require(selected['epoch'] == independently_selected['epoch'], 'Selected epoch differs under independent float32 validation')
        require(reported['final_parameter_sha256'] == evaluations[-1]['parameter_sha256'], 'Final tensor identity mismatch')
        results.append(dict(seed=seed, updates=60, selected_epoch=selected['epoch'],
            selected_checkpoint_sha256=selected['sha256'], checkpoints=evaluations))
    require(all(sha256(path)==value for path,value in sources.items()), 'Fitted evidence changed during audit')
    return dict(schema='bc-rpi-round1-independent-fit-audit-v1', status='three_real_fits_and_fit_val_selection_verified',
        initialization_count=3, optimizer_updates=180, checkpoints_verified=9, parameters_per_model=61121,
        actual_optimizer_updates_by_auditor=0, actual_environment_calls_by_auditor=0,
        results=results, source_sha256=sources, auditor_sha256=sha256(__file__),
        evidence_limits=['Actual journal, initial/fitted tensors, Adam states and forward validation inspected; not an independent retraining.',
                         'Public export lineage/absence of hidden features must be audited separately.',
                         'Fitting and validation loss are not deployment performance.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--campaign', type=Path, required=True)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--fit', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a=p.parse_args(); require(not a.out.exists(), 'Preserve previous audit output')
    result=audit(a.campaign,a.dataset,a.fit)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','optimizer_updates','checkpoints_verified')},indent=2))


if __name__=='__main__': main()
